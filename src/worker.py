import time
import sqlite3
import os
import uuid
import json
from datetime import datetime, timedelta

def get_db_connection():
    """Получить соединение с SQLite базой данных"""
    from safe_db_utils import get_db_connection as _get_db_connection
    return _get_db_connection()

def _is_parsing_successful(card_data: dict, business_id: str = None) -> tuple:
    """
    Проверяет, успешен ли парсинг.
    
    Returns:
        (is_successful: bool, reason: str)
    """
    # Проверка на капчу
    if card_data.get("error") == "captcha_detected":
        return False, "captcha_detected"
    
    # Проверка на ошибку
    if card_data.get("error"):
        return False, f"error: {card_data.get('error')}"
    
    # Проверка критичных полей
    title = card_data.get('title') or card_data.get('overview', {}).get('title')
    address = card_data.get('address') or card_data.get('overview', {}).get('address')
    
    if not title:
        return False, "missing_title"
    
    if not address:
        return False, "missing_address"
    
    return True, "success"

def _has_cabinet_account(business_id: str) -> tuple:
    """
    Проверяет, есть ли у бизнеса аккаунт в личном кабинете.
    
    Returns:
        (has_account: bool, account_id: str)
    """
    if not business_id:
        return False, None
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT id 
            FROM ExternalBusinessAccounts 
            WHERE business_id = ? 
              AND source = 'yandex_business' 
              AND is_active = 1
            LIMIT 1
        """, (business_id,))
        
        row = cursor.fetchone()
        if row:
            return True, row[0]
        return False, None
    finally:
        cursor.close()
        conn.close()

def _ensure_column_exists(cursor, conn, table_name, column_name, column_type="TEXT"):
    """Проверяет и добавляет колонку если её нет"""
    try:
        # PRAGMA не поддерживает параметризованные запросы, используем f-string с проверкой
        ALLOWED_TABLES = {'ParseQueue', 'MapParseResults'}
        if table_name not in ALLOWED_TABLES:
            raise ValueError(f"Неразрешенная таблица: {table_name}")
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]
        
        if column_name not in columns:
            print(f"📝 Добавляю поле {column_name} в {table_name}...")
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
            conn.commit()
    except Exception as e:
        print(f"⚠️ Ошибка проверки колонки {column_name} в {table_name}: {e}")

# Используем parser_config для автоматического выбора парсера (interception или legacy)
from parser_config import parse_yandex_card
from gigachat_analyzer import analyze_business_data

def process_queue():
    """Обрабатывает очередь парсинга из SQLite базы данных"""
    queue_dict = None
    
    # ШАГ 1: Получаем задачу из очереди и обновляем статус (закрываем соединение сразу)
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Проверяем, существует ли таблица ParseQueue
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ParseQueue'")
        if not cursor.fetchone():
            print("⚠️ Таблица ParseQueue не найдена. Инициализирую схему БД...")
            conn.close()
            # Импортируем и вызываем инициализацию
            from init_database_schema import init_database_schema
            init_database_schema()
            # Открываем новое соединение после инициализации
            conn = get_db_connection()
            cursor = conn.cursor()
        
        # Проверяем и добавляем недостающие поля в ParseQueue
        _ensure_column_exists(cursor, conn, "ParseQueue", "retry_after")
        _ensure_column_exists(cursor, conn, "ParseQueue", "business_id")
        _ensure_column_exists(cursor, conn, "ParseQueue", "task_type", "TEXT DEFAULT 'parse_card'")
        _ensure_column_exists(cursor, conn, "ParseQueue", "account_id")
        _ensure_column_exists(cursor, conn, "ParseQueue", "source")
        _ensure_column_exists(cursor, conn, "ParseQueue", "error_message")
        _ensure_column_exists(cursor, conn, "ParseQueue", "updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        
        # Получаем заявки из очереди (обрабатываем и parse_card, и sync задачи)
        now = datetime.now().isoformat()
        cursor.execute("""
            SELECT * FROM ParseQueue 
            WHERE status = 'pending' 
               OR (status = 'captcha' AND (retry_after IS NULL OR retry_after <= ?))
            ORDER BY 
                CASE WHEN status = 'pending' THEN 1 ELSE 2 END,
                created_at ASC 
            LIMIT 1
        """, (now,))
        queue_item = cursor.fetchone()
        
        if not queue_item:
            return
        
        # Преобразуем Row в словарь (row_factory уже установлен в safe_db_utils)
        queue_dict = dict(queue_item)
        
        # Обновляем статус на "processing"
        cursor.execute("UPDATE ParseQueue SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", ("processing", queue_dict["id"]))
        conn.commit()
    finally:
        # ВАЖНО: Закрываем соединение перед долгим парсингом
        cursor.close()
        conn.close()
    
    if not queue_dict:
        return
    
    # Определяем тип задачи (по умолчанию parse_card для обратной совместимости)
    task_type = queue_dict.get("task_type") or "parse_card"
    
    print(f"Обрабатываю заявку: {queue_dict.get('id')}, тип: {task_type}")
    
    # Обрабатываем в зависимости от типа задачи
    if task_type == "sync_yandex_business":
        # Синхронизация Яндекс.Бизнес
        _process_sync_yandex_business_task(queue_dict)
        return
    elif task_type == "parse_cabinet_fallback":
        # Fallback парсинг через кабинет
        _process_cabinet_fallback_task(queue_dict)
        return
    elif task_type in ["sync_google_business", "sync_2gis"]:
        # Другие источники (будущее)
        print(f"⚠️ Тип задачи {task_type} пока не реализован")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE ParseQueue 
            SET status = 'error', 
                error_message = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (f"Тип задачи {task_type} пока не реализован", queue_dict["id"]))
        conn.commit()
        cursor.close()
        conn.close()
        return
    
    # Обычный парсинг карт (task_type = 'parse_card' или NULL)
    # ШАГ 2: Парсим данные (БЕЗ открытого соединения с БД)
    try:
        if not queue_dict.get("url"):
            raise ValueError("URL не указан для задачи парсинга")
        
        card_data = parse_yandex_card(queue_dict["url"])
        
        # Проверяем успешность парсинга
        business_id = queue_dict.get("business_id")
        is_successful, reason = _is_parsing_successful(card_data, business_id)
        
        if not is_successful and business_id:
            # Проверяем, есть ли кабинет для fallback
            has_account, account_id = _has_cabinet_account(business_id)
            
            if has_account:
                print(f"⚠️ Парсинг неполный ({reason}), создаю задачу fallback через кабинет")
                
                # Создаем задачу fallback
                fallback_task_id = str(uuid.uuid4())
                conn = get_db_connection()
                cursor = conn.cursor()
                
                try:
                    cursor.execute("""
                        INSERT INTO ParseQueue (
                            id, business_id, account_id, task_type, source,
                            status, user_id, url, created_at, updated_at
                        )
                        VALUES (?, ?, ?, 'parse_cabinet_fallback', 'yandex_business',
                                'pending', ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """, (fallback_task_id, business_id, account_id, queue_dict["user_id"], queue_dict["url"]))
                    conn.commit()
                    print(f"✅ Создана задача fallback: {fallback_task_id}")
                finally:
                    cursor.close()
                    conn.close()
        
        if card_data.get("error") == "captcha_detected":
            # Открываем новое соединение только для обновления статуса капчи
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                retry_after = datetime.now() + timedelta(hours=2)
                cursor.execute("SELECT COUNT(*) FROM ParseQueue WHERE status = 'pending' AND id != ?", (queue_dict["id"],))
                pending_count = cursor.fetchone()[0]
                
                # Обновляем статус капчи (created_at обновляем только если есть pending задачи)
                if pending_count > 0:
                    cursor.execute("UPDATE ParseQueue SET status = ?, retry_after = ?, created_at = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                                 ("captcha", retry_after.isoformat(), datetime.now().isoformat(), queue_dict["id"]))
                else:
                    cursor.execute("UPDATE ParseQueue SET status = ?, retry_after = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                                 ("captcha", retry_after.isoformat(), queue_dict["id"]))
                conn.commit()
            finally:
                cursor.close()
                conn.close()
            return
        
        # ШАГ 3: Сохраняем результаты (открываем новое соединение)
        business_id = queue_dict.get("business_id")
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            if business_id:
                # Новая логика: сохраняем в MapParseResults
                print(f"📊 Сохраняю результаты в MapParseResults для business_id={business_id}")
                
                try:
                    from analyzer import analyze_card
                    from report import generate_html_report
                    
                    analysis = analyze_card(card_data)
                    report_path = generate_html_report(card_data, analysis, {})
                    
                    # Сохраняем анализ для использования в рекомендациях
                    analysis_json = json.dumps(analysis, ensure_ascii=False)
                    
                    rating = card_data.get('overview', {}).get('rating', '') or ''
                    reviews_count = card_data.get('reviews_count') or card_data.get('overview', {}).get('reviews_count') or 0
                    news_count = len(card_data.get('news') or [])
                    photos_count = card_data.get('photos_count') or 0
                    
                    # Подсчитываем неотвеченные отзывы
                    reviews = card_data.get('reviews', [])
                    if isinstance(reviews, dict) and 'items' in reviews:
                        reviews_list = reviews['items']
                    elif isinstance(reviews, list):
                        reviews_list = reviews
                    else:
                        reviews_list = []
                    
                    unanswered_reviews_count = sum(1 for r in reviews_list if not r.get('org_reply') or r.get('org_reply', '').strip() == '' or r.get('org_reply', '').strip() == '—')
                    
                    url_lower = (queue_dict["url"] or '').lower()
                    map_type = 'yandex' if 'yandex' in url_lower else ('google' if 'google' in url_lower else 'other')
                    
                    parse_result_id = str(uuid.uuid4())
                    
                    # Убеждаемся, что колонка unanswered_reviews_count существует
                    _ensure_column_exists(cursor, conn, "MapParseResults", "unanswered_reviews_count", "INTEGER")
                    
                    # Всегда используем колонку (она будет создана если её нет)
                    cursor.execute("""
                        INSERT INTO MapParseResults
                        (id, business_id, url, map_type, rating, reviews_count, unanswered_reviews_count, news_count, photos_count, report_path, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, (
                        parse_result_id,
                        business_id,
                        queue_dict["url"],
                        map_type,
                        str(rating),
                        int(reviews_count or 0),
                        int(unanswered_reviews_count),
                        int(news_count or 0),
                        int(photos_count or 0),
                        report_path
                    ))
                    
                    print(f"✅ Результаты сохранены в MapParseResults: {parse_result_id}")
                    
                    # Сохраняем отзывы в ExternalBusinessReviews с датами и ответами организации
                    if reviews_list:
                        try:
                            from external_sources import ExternalReview, ExternalSource
                            from yandex_business_sync_worker import YandexBusinessSyncWorker
                            from dateutil import parser as date_parser
                            import re
                            
                            external_reviews = []
                            for review in reviews_list:
                                if not review.get('text'):
                                    continue
                                
                                # Генерируем ID отзыва
                                review_id = str(uuid.uuid4())
                                external_review_id = review.get('id') or f"html_{review_id}"
                                
                                # Парсим дату
                                published_at = None
                                date_str = review.get('date', '').strip()
                                if date_str:
                                    try:
                                        # Пробуем разные форматы дат
                                        # "2 дня назад", "неделю назад", "15 января 2024", "2024-01-15"
                                        if 'дня' in date_str or 'день' in date_str or 'дней' in date_str:
                                            # Относительная дата
                                            days_match = re.search(r'(\d+)', date_str)
                                            if days_match:
                                                days_ago = int(days_match.group(1))
                                                published_at = datetime.now() - timedelta(days=days_ago)
                                        elif 'неделю' in date_str or 'недели' in date_str or 'недель' in date_str:
                                            weeks_match = re.search(r'(\d+)', date_str)
                                            if weeks_match:
                                                weeks_ago = int(weeks_match.group(1))
                                                published_at = datetime.now() - timedelta(weeks=weeks_ago)
                                            else:
                                                published_at = datetime.now() - timedelta(weeks=1)
                                        elif 'месяц' in date_str or 'месяца' in date_str or 'месяцев' in date_str:
                                            months_match = re.search(r'(\d+)', date_str)
                                            if months_match:
                                                months_ago = int(months_match.group(1))
                                                published_at = datetime.now() - timedelta(days=months_ago * 30)
                                            else:
                                                published_at = datetime.now() - timedelta(days=30)
                                        elif 'год' in date_str or 'года' in date_str or 'лет' in date_str:
                                            years_match = re.search(r'(\d+)', date_str)
                                            if years_match:
                                                years_ago = int(years_match.group(1))
                                                published_at = datetime.now() - timedelta(days=years_ago * 365)
                                            else:
                                                published_at = datetime.now() - timedelta(days=365)
                                        else:
                                            # Пробуем распарсить как обычную дату
                                            published_at = date_parser.parse(date_str, fuzzy=True)
                                    except Exception as date_err:
                                        print(f"⚠️ Не удалось распарсить дату '{date_str}': {date_err}")
                                
                                # Извлекаем ответ организации
                                response_text = review.get('org_reply') or review.get('response_text') or ''
                                response_text = response_text.strip() if response_text else None
                                response_at = None
                                
                                # Парсим дату ответа (если есть)
                                response_date_str = review.get('response_date')
                                if response_date_str:
                                    try:
                                        response_at = date_parser.parse(response_date_str, fuzzy=True)
                                    except:
                                        pass
                                
                                # Конвертируем рейтинг
                                rating = review.get('score') or review.get('rating')
                                if rating:
                                    try:
                                        rating = int(rating)
                                    except:
                                        rating = None
                                
                                external_review = ExternalReview(
                                    id=review_id,
                                    business_id=business_id,
                                    source=ExternalSource.YANDEX_MAPS,
                                    external_review_id=external_review_id,
                                    rating=rating,
                                    author_name=review.get('author') or 'Анонимный пользователь',
                                    text=review.get('text'),
                                    published_at=published_at,
                                    response_text=response_text,
                                    response_at=response_at,
                                    raw_payload=review
                                )
                                external_reviews.append(external_review)
                            
                            # Сохраняем в БД
                            if external_reviews:
                                db = DatabaseManager()
                                worker = YandexBusinessSyncWorker()
                                worker._upsert_reviews(db, external_reviews)
                                print(f"💾 Сохранено {len(external_reviews)} отзывов в ExternalBusinessReviews с датами и ответами")
                        except Exception as review_err:
                            print(f"⚠️ Ошибка сохранения отзывов в ExternalBusinessReviews: {review_err}")
                            import traceback
                            traceback.print_exc()
                    
                except Exception as e:
                    print(f"⚠️ Ошибка сохранения в MapParseResults: {e}")
                    import traceback
                    traceback.print_exc()
                    try:
                        from user_api import send_email
                        send_email(
                            "demyanovap@yandex.ru",
                            "Ошибка парсинга карты",
                            f"URL: {queue_dict['url']}\nBusiness ID: {business_id}\nОшибка: {e}"
                        )
                    except:
                        pass
                    raise
            else:
                # Старая логика: сохраняем в Cards
                card_id = str(uuid.uuid4())
                
                rating = card_data.get("rating")
                if rating == "" or rating is None:
                    rating = None
                else:
                    try:
                        rating = float(rating)
                    except (ValueError, TypeError):
                        rating = None
                        
                reviews_count = card_data.get("reviews_count")
                if reviews_count == "" or reviews_count is None:
                    reviews_count = None
                else:
                    try:
                        reviews_count = int(reviews_count)
                    except (ValueError, TypeError):
                        reviews_count = None
                
                cursor.execute("""
                    INSERT INTO Cards (
                        id, user_id, url, title, address, phone, site, rating, 
                        reviews_count, categories, overview, products, news, 
                        photos, features_full, competitors, hours, hours_full,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    card_id,
                    queue_dict["user_id"],
                    queue_dict["url"],
                    card_data.get("title"),
                    card_data.get("address"),
                    card_data.get("phone"),
                    card_data.get("site"),
                    rating,
                    reviews_count,
                    str(card_data.get("categories", [])),
                    str(card_data.get("overview", {})),
                    str(card_data.get("products", [])),
                    str(card_data.get("news", [])),
                    str(card_data.get("photos", [])),
                    str(card_data.get("features_full", {})),
                    str(card_data.get("competitors", [])),
                    card_data.get("hours"),
                    str(card_data.get("hours_full", [])),
                    datetime.now().isoformat()
                ))
                
                print(f"Выполняем ИИ-анализ для карточки {card_id}...")
                
                try:
                    analysis_result = analyze_business_data(card_data)
                    
                    cursor.execute("""
                        UPDATE Cards SET 
                            ai_analysis = ?, 
                            seo_score = ?, 
                            recommendations = ?
                        WHERE id = ?
                    """, (
                        str(analysis_result.get('analysis', {})),
                        analysis_result.get('score', 50),
                        str(analysis_result.get('recommendations', [])),
                        card_id
                    ))
                    
                    print(f"ИИ-анализ завершён для карточки {card_id}")
                    
                    try:
                        from report import generate_html_report
                        analysis_data = {
                            'score': analysis_result.get('score', 50),
                            'recommendations': analysis_result.get('recommendations', []),
                            'ai_analysis': analysis_result.get('analysis', {})
                        }
                        report_path = generate_html_report(card_data, analysis_data)
                        print(f"HTML отчёт сгенерирован: {report_path}")
                        cursor.execute("UPDATE Cards SET report_path = ? WHERE id = ?", (report_path, card_id))
                    except Exception as report_error:
                        print(f"Ошибка при генерации отчёта для карточки {card_id}: {report_error}")
                        
                except Exception as analysis_error:
                    print(f"Ошибка при ИИ-анализе карточки {card_id}: {analysis_error}")
            
            # Обновляем статус на "done" и удаляем заявку из очереди
            cursor.execute("UPDATE ParseQueue SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", ("done", queue_dict["id"]))
            cursor.execute("DELETE FROM ParseQueue WHERE id = ?", (queue_dict["id"],))
            conn.commit()
            
            print(f"✅ Заявка {queue_dict['id']} обработана и удалена из очереди.")
            
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        queue_id = queue_dict.get('id', 'unknown') if queue_dict else 'unknown'
        print(f"❌ Ошибка при обработке заявки {queue_id}: {e}")
        import traceback
        traceback.print_exc()
        
        # Обновляем статус ошибки
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE ParseQueue SET status = ?, error_message = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                         ("error", str(e), queue_id))
            conn.commit()
            print(f"⚠️ Заявка {queue_id} помечена как ошибка.")
        except Exception as update_error:
            print(f"❌ Не удалось обновить статус заявки {queue_id}: {update_error}")
        finally:
            cursor.close()
            conn.close()
        
        # Отправляем email (ошибка не критична)
        try:
            from user_api import send_email
            send_email(
                "demyanovap@yandex.ru",
                "Ошибка парсинга карты",
                f"URL: {queue_dict.get('url', 'unknown') if queue_dict else 'unknown'}\nОшибка: {e}"
            )
        except Exception as email_error:
            print(f"⚠️ Не удалось отправить email: {email_error}")

def _process_sync_yandex_business_task(queue_dict):
    """Обработка синхронизации Яндекс.Бизнес через кабинет"""
    business_id = queue_dict.get("business_id")
    account_id = queue_dict.get("account_id")
    
    if not business_id or not account_id:
        print(f"❌ Отсутствует business_id или account_id для задачи {queue_dict.get('id')}")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE ParseQueue 
            SET status = 'error', 
                error_message = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, ("Отсутствует business_id или account_id", queue_dict["id"]))
        conn.commit()
        cursor.close()
        conn.close()
        return
    
    print(f"🔄 Синхронизация Яндекс.Бизнес для бизнеса {business_id}", flush=True)
    
    try:
        from yandex_business_parser import YandexBusinessParser
        from yandex_business_sync_worker import YandexBusinessSyncWorker
        from auth_encryption import decrypt_auth_data
        from database_manager import DatabaseManager
        import json
        import traceback
        
        # Получаем auth_data
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        try:
            cursor.execute("""
                SELECT auth_data_encrypted, external_id 
                FROM ExternalBusinessAccounts 
                WHERE id = ? AND business_id = ?
            """, (account_id, business_id))
            account_row = cursor.fetchone()
            
            if not account_row:
                raise Exception("Аккаунт не найден")
            
            auth_data_encrypted, external_id = account_row
            auth_data_plain = decrypt_auth_data(auth_data_encrypted)
            
            if not auth_data_plain:
                raise Exception("Не удалось расшифровать auth_data")
            
            # Парсим auth_data
            try:
                auth_data_dict = json.loads(auth_data_plain)
            except json.JSONDecodeError:
                auth_data_dict = {"cookies": auth_data_plain}
            
            # Создаем парсер
            parser = YandexBusinessParser(auth_data_dict)
            account_data = {
                "id": account_id,
                "business_id": business_id,
                "external_id": external_id
            }
            
            # Получаем данные из кабинета
            print(f"📥 Получение отзывов из кабинета...")
            reviews = parser.fetch_reviews(account_data)
            print(f"✅ Получено отзывов: {len(reviews)}")
            
            print(f"📥 Получение статистики из кабинета...")
            stats = parser.fetch_stats(account_data)
            print(f"✅ Получено точек статистики: {len(stats)}")
            
            print(f"📥 Получение публикаций из кабинета...")
            posts = parser.fetch_posts(account_data)
            print(f"✅ Получено публикаций: {len(posts)}")
            
            print(f"📥 Получение информации об организации из кабинета...")
            org_info = parser.fetch_organization_info(account_data)
            
            # Сохраняем отзывы и статистику
            worker = YandexBusinessSyncWorker()
            if reviews:
                worker._upsert_reviews(db, reviews)
                print(f"💾 Сохранено отзывов: {len(reviews)}")
            
            if stats:
                worker._upsert_stats(db, stats)
                print(f"💾 Сохранено точек статистики: {len(stats)}")
            
            if posts:
                worker._upsert_posts(db, posts)
                print(f"💾 Сохранено публикаций: {len(posts)}")
            
            # Получаем существующие данные из MapParseResults (если есть)
            cursor.execute("""
                SELECT rating, reviews_count, unanswered_reviews_count, news_count, photos_count
                FROM MapParseResults
                WHERE business_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (business_id,))
            existing_data = cursor.fetchone()
            
            # Используем данные из кабинета (приоритет кабинету)
            rating = org_info.get('rating') if org_info and org_info.get('rating') else (existing_data[0] if existing_data and existing_data[0] else None)
            reviews_count = len(reviews) if reviews else (existing_data[1] if existing_data and existing_data[1] else 0)
            reviews_without_response = sum(1 for r in reviews if not r.response_text) if reviews else (existing_data[2] if existing_data and existing_data[2] else 0)
            news_count = len(posts) if posts else (existing_data[3] if existing_data and existing_data[3] else 0)
            photos_count = org_info.get('photos_count', 0) if org_info else (existing_data[4] if existing_data and existing_data[4] else 0)
            
            # Сохраняем в MapParseResults
            parse_id = str(uuid.uuid4())
            url = f"https://yandex.ru/sprav/{external_id or 'unknown'}"
            cursor.execute("""
                INSERT INTO MapParseResults (
                    id, business_id, url, map_type, rating, reviews_count, 
                    unanswered_reviews_count, news_count, photos_count, 
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                parse_id,
                business_id,
                url,
                'yandex',
                rating,
                reviews_count,
                reviews_without_response,
                news_count,
                photos_count,
            ))
            
            db.conn.commit()
            db.close()
            
            # Обновляем статус задачи
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE ParseQueue 
                SET status = 'done', 
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (queue_dict["id"],))
            conn.commit()
            cursor.close()
            conn.close()
            
            print(f"✅ Синхронизация завершена для бизнеса {business_id}", flush=True)
            
        except Exception as e:
            print(f"❌ Ошибка синхронизации: {e}", flush=True)
            import traceback
            traceback.print_exc(file=sys.stdout)
            sys.stdout.flush()
            db.close()
            
            # Обновляем статус ошибки
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE ParseQueue 
                SET status = 'error', 
                    error_message = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (str(e), queue_dict["id"]))
            conn.commit()
            cursor.close()
            conn.close()
            
    except Exception as e:
        print(f"❌ Критическая ошибка синхронизации: {e}")
        import traceback
        traceback.print_exc()
        
        # Обновляем статус ошибки
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE ParseQueue 
            SET status = 'error', 
                error_message = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (str(e), queue_dict["id"]))
        conn.commit()
        cursor.close()
        conn.close()

def _process_cabinet_fallback_task(queue_dict):
    """Обработка fallback парсинга через кабинет"""
    business_id = queue_dict.get("business_id")
    account_id = queue_dict.get("account_id")
    url = queue_dict.get("url")
    
    if not business_id or not account_id:
        print(f"❌ Отсутствует business_id или account_id для задачи {queue_dict.get('id')}")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE ParseQueue 
            SET status = 'error', 
                error_message = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, ("Отсутствует business_id или account_id", queue_dict["id"]))
        conn.commit()
        cursor.close()
        conn.close()
        return
    
    print(f"🔄 Fallback парсинг через кабинет для бизнеса {business_id}")
    
    try:
        from yandex_business_parser import YandexBusinessParser
        from yandex_business_sync_worker import YandexBusinessSyncWorker
        from auth_encryption import decrypt_auth_data
        from database_manager import DatabaseManager
        import json
        import traceback
        
        # Получаем auth_data
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        try:
            cursor.execute("""
                SELECT auth_data_encrypted, external_id 
                FROM ExternalBusinessAccounts 
                WHERE id = ? AND business_id = ?
            """, (account_id, business_id))
            account_row = cursor.fetchone()
            
            if not account_row:
                raise Exception("Аккаунт не найден")
            
            auth_data_encrypted, external_id = account_row
            auth_data_plain = decrypt_auth_data(auth_data_encrypted)
            
            if not auth_data_plain:
                raise Exception("Не удалось расшифровать auth_data")
            
            # Парсим auth_data
            try:
                auth_data_dict = json.loads(auth_data_plain)
            except json.JSONDecodeError:
                auth_data_dict = {"cookies": auth_data_plain}
            
            # Создаем парсер
            parser = YandexBusinessParser(auth_data_dict)
            account_data = {
                "id": account_id,
                "business_id": business_id,
                "external_id": external_id
            }
            
            # Получаем данные из кабинета
            print(f"📥 Получение отзывов из кабинета...")
            reviews = parser.fetch_reviews(account_data)
            print(f"✅ Получено отзывов: {len(reviews)}")
            
            print(f"📥 Получение статистики из кабинета...")
            stats = parser.fetch_stats(account_data)
            print(f"✅ Получено точек статистики: {len(stats)}")
            
            print(f"📥 Получение публикаций из кабинета...")
            posts = parser.fetch_posts(account_data)
            print(f"✅ Получено публикаций: {len(posts)}")
            
            print(f"📥 Получение информации об организации из кабинета...")
            org_info = parser.fetch_organization_info(account_data)
            
            # Сохраняем отзывы и статистику
            worker = YandexBusinessSyncWorker()
            if reviews:
                worker._upsert_reviews(db, reviews)
                print(f"💾 Сохранено отзывов: {len(reviews)}")
            
            if stats:
                worker._upsert_stats(db, stats)
                print(f"💾 Сохранено точек статистики: {len(stats)}")
            
            if posts:
                worker._upsert_posts(db, posts)
                print(f"💾 Сохранено публикаций: {len(posts)}")
            
            # Получаем существующие данные из MapParseResults (если есть)
            cursor.execute("""
                SELECT rating, reviews_count, unanswered_reviews_count, news_count, photos_count
                FROM MapParseResults
                WHERE business_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (business_id,))
            existing_data = cursor.fetchone()
            
            # Используем данные из кабинета (приоритет кабинету)
            # Если данных нет в кабинете, используем существующие (если есть)
            rating = org_info.get('rating') if org_info and org_info.get('rating') else (existing_data[0] if existing_data and existing_data[0] else None)
            reviews_count = len(reviews) if reviews else (existing_data[1] if existing_data and existing_data[1] else 0)
            reviews_without_response = sum(1 for r in reviews if not r.response_text) if reviews else (existing_data[2] if existing_data and existing_data[2] else 0)
            news_count = len(posts) if posts else (existing_data[3] if existing_data and existing_data[3] else 0)
            photos_count = org_info.get('photos_count', 0) if org_info else (existing_data[4] if existing_data and existing_data[4] else 0)
            
            # Сохраняем в MapParseResults
            parse_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO MapParseResults (
                    id, business_id, url, map_type, rating, reviews_count, 
                    unanswered_reviews_count, news_count, photos_count, 
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                parse_id,
                business_id,
                url or f"https://yandex.ru/sprav/{external_id or 'unknown'}",
                'yandex',
                rating,
                reviews_count,
                reviews_without_response,
                news_count,
                photos_count,
            ))
            
            db.conn.commit()
            db.close()
            
            # Обновляем статус задачи
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE ParseQueue 
                SET status = 'completed', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (queue_dict["id"],))
            conn.commit()
            cursor.close()
            conn.close()
            
            print(f"✅ Fallback парсинг завершен для бизнеса {business_id}")
            
        except Exception as e:
            error_details = traceback.format_exc()
            print(f"❌ Ошибка fallback парсинга: {e}")
            print(f"❌ Детали ошибки:\n{error_details}")
            db.close()
            
            # Обновляем статус на error
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE ParseQueue 
                SET status = 'error', 
                    error_message = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (str(e), queue_dict["id"]))
            conn.commit()
            cursor.close()
            conn.close()
    except Exception as e:
        print(f"❌ Критическая ошибка при обработке fallback парсинга {queue_dict.get('id', 'unknown')}: {e}")
        import traceback
        traceback.print_exc()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE ParseQueue 
                SET status = 'error', 
                    error_message = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (str(e), queue_dict["id"]))
            conn.commit()
        except Exception as update_error:
            print(f"❌ Не удалось обновить статус fallback парсинга: {update_error}")
        finally:
            cursor.close()
            conn.close()

def process_sync_queue():
    """Обрабатывает очередь синхронизации внешних источников"""
    sync_dict = None
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='SyncQueue'")
        if not cursor.fetchone():
            conn.close()
            return
        
        cursor.execute("""
            SELECT * FROM SyncQueue 
            WHERE status = 'pending'
            ORDER BY created_at ASC 
            LIMIT 1
        """)
        sync_item = cursor.fetchone()
        
        if not sync_item:
            return
        
        sync_dict = dict(sync_item)
        
        cursor.execute("UPDATE SyncQueue SET status = ? WHERE id = ?", ("processing", sync_dict["id"]))
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    
    if not sync_dict:
        return
    
    print(f"🔄 Обрабатываю синхронизацию: {sync_dict['id']} для бизнеса {sync_dict['business_id']}")
    
    try:
        if sync_dict['source'] == 'yandex_business':
            from yandex_business_sync_worker import YandexBusinessSyncWorker
            from yandex_business_parser import YandexBusinessParser
            from auth_encryption import decrypt_auth_data
            import json
            import uuid
            import traceback
            
            db = DatabaseManager()
            cursor = db.conn.cursor()
            
            try:
                cursor.execute("""
                    SELECT auth_data_encrypted, external_id 
                    FROM ExternalBusinessAccounts 
                    WHERE id = ?
                """, (sync_dict['account_id'],))
                account_row = cursor.fetchone()
                
                if not account_row:
                    print(f"❌ Аккаунт {sync_dict['account_id']} не найден")
                    cursor.execute("UPDATE SyncQueue SET status = 'error', error_message = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                                 ("Аккаунт не найден", sync_dict['id']))
                    db.conn.commit()
                    db.close()
                    return
                
                auth_data_encrypted = account_row[0]
                external_id = account_row[1] if len(account_row) > 1 else None
                
                cursor.execute("SELECT name FROM Businesses WHERE id = ?", (sync_dict['business_id'],))
                business_row = cursor.fetchone()
                business_name = business_row[0] if business_row else 'Unknown'
                
                db.close()
                
                auth_data_plain = decrypt_auth_data(auth_data_encrypted)
                if not auth_data_plain:
                    print(f"❌ Не удалось расшифровать auth_data для аккаунта {sync_dict['account_id']}")
                    db = DatabaseManager()
                    cursor = db.conn.cursor()
                    cursor.execute("UPDATE SyncQueue SET status = 'error', error_message = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                                 ("Не удалось расшифровать данные авторизации", sync_dict['id']))
                    db.conn.commit()
                    db.close()
                    return
                
                try:
                    auth_data_dict = json.loads(auth_data_plain)
                except json.JSONDecodeError:
                    auth_data_dict = {"cookies": auth_data_plain}
                
                parser = YandexBusinessParser(auth_data_dict)
                account_data = {
                    "id": sync_dict['account_id'],
                    "business_id": sync_dict['business_id'],
                    "external_id": external_id
                }
                
                print(f"📥 Получение отзывов...")
                reviews = parser.fetch_reviews(account_data)
                print(f"✅ Получено отзывов: {len(reviews)}")
                
                print(f"📥 Получение статистики...")
                stats = parser.fetch_stats(account_data)
                print(f"✅ Получено точек статистики: {len(stats)}")
                
                print(f"📥 Получение публикаций...")
                posts = parser.fetch_posts(account_data)
                print(f"✅ Получено публикаций: {len(posts)}")
                
                print(f"📥 Получение услуг/прайс-листа...")
                services = parser.fetch_services(account_data)
                print(f"✅ Получено услуг: {len(services)}")
                
                print(f"📥 Получение информации об организации...")
                org_info = parser.fetch_organization_info(account_data)
                
                db = DatabaseManager()
                worker = YandexBusinessSyncWorker()
                
                if reviews:
                    worker._upsert_reviews(db, reviews)
                    print(f"💾 Сохранено отзывов: {len(reviews)}")
                
                if not stats and org_info:
                    from external_sources import ExternalStatsPoint, make_stats_id
                    from datetime import date
                    today_str = date.today().isoformat()
                    stat_id = make_stats_id(sync_dict['business_id'], "yandex_business", today_str)
                    stat = ExternalStatsPoint(
                        id=stat_id,
                        business_id=sync_dict['business_id'],
                        source="yandex_business",
                        date=today_str,
                        views_total=0,
                        clicks_total=0,
                        actions_total=0,
                        rating=org_info.get('rating'),
                        reviews_total=org_info.get('reviews_count') or len(reviews),
                        raw_payload=org_info,
                    )
                    stats = [stat]
                
                if stats:
                    if org_info and stats:
                        last_stat = stats[-1]
                        if last_stat.raw_payload:
                            last_stat.raw_payload.update(org_info)
                        else:
                            last_stat.raw_payload = org_info
                        if org_info.get('rating'):
                            last_stat.rating = org_info.get('rating')
                        if org_info.get('reviews_count'):
                            last_stat.reviews_total = org_info.get('reviews_count')
                    
                    worker._upsert_stats(db, stats)
                    print(f"💾 Сохранено точек статистики: {len(stats)}")
                
                if posts:
                    worker._upsert_posts(db, posts)
                    print(f"💾 Сохранено публикаций: {len(posts)}")
                
                if services:
                    try:
                        cursor = db.conn.cursor()
                        cursor.execute("SELECT owner_id FROM Businesses WHERE id = ?", (sync_dict['business_id'],))
                        owner_row = cursor.fetchone()
                        user_id = owner_row[0] if owner_row else None
                        
                        if user_id:
                            saved_count = 0
                            updated_count = 0
                            for service in services:
                                try:
                                    if not isinstance(service, dict) or "name" not in service or not service["name"]:
                                        continue
                                    
                                    cursor.execute("""
                                        SELECT id FROM UserServices 
                                        WHERE business_id = ? AND name = ? 
                                        LIMIT 1
                                    """, (sync_dict['business_id'], service["name"]))
                                    existing = cursor.fetchone()
                                    
                                    description = service.get("description", "")
                                    if isinstance(description, dict):
                                        description = description.get("text") or description.get("value") or description.get("content") or str(description)
                                    elif not isinstance(description, str):
                                        description = str(description) if description else ""
                                    
                                    category = service.get("category", "Общие услуги")
                                    if isinstance(category, dict):
                                        category = category.get("name") or category.get("title") or str(category)
                                    elif not isinstance(category, str):
                                        category = str(category) if category else "Общие услуги"
                                    
                                    if not existing:
                                        service_id = str(uuid.uuid4())
                                        cursor.execute("""
                                            INSERT INTO UserServices (id, user_id, business_id, category, name, description, keywords, price, created_at, updated_at)
                                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                                        """, (
                                            service_id,
                                            user_id,
                                            sync_dict['business_id'],
                                            category,
                                            service["name"],
                                            description,
                                            json.dumps(service.get("keywords", [])),
                                            service.get("price", "")
                                        ))
                                        saved_count += 1
                                    else:
                                        cursor.execute("""
                                            UPDATE UserServices 
                                            SET category = ?, description = ?, keywords = ?, price = ?, updated_at = CURRENT_TIMESTAMP
                                            WHERE business_id = ? AND name = ?
                                        """, (
                                            category,
                                            description,
                                            json.dumps(service.get("keywords", [])),
                                            service.get("price", ""),
                                            sync_dict['business_id'],
                                            service["name"]
                                        ))
                                        updated_count += 1
                                except Exception as e:
                                    print(f"⚠️ Ошибка сохранения услуги '{service.get('name', 'unknown')}': {e}")
                                    continue
                            
                            db.conn.commit()
                            print(f"💾 Сохранено услуг: {saved_count} новых, {updated_count} обновлено")
                    except Exception as e:
                        print(f"❌ Критическая ошибка при сохранении услуг: {e}")
                
                cursor = db.conn.cursor()
                cursor.execute("""
                    UPDATE ExternalBusinessAccounts 
                    SET last_sync_at = CURRENT_TIMESTAMP, last_error = NULL
                    WHERE id = ?
                """, (sync_dict['account_id'],))
                
                try:
                    cursor.execute("SELECT yandex_url FROM Businesses WHERE id = ?", (sync_dict['business_id'],))
                    yandex_url_row = cursor.fetchone()
                    yandex_url = yandex_url_row[0] if yandex_url_row else None
                    
                    if not yandex_url and external_id:
                        yandex_url = f"https://yandex.ru/sprav/{external_id}"
                    
                    parse_id = str(uuid.uuid4())
                    reviews_without_response = sum(1 for r in reviews if not r.response_text) if reviews else 0
                    
                    cursor.execute("""
                        INSERT INTO MapParseResults (
                            id, business_id, url, map_type, rating, reviews_count, 
                            unanswered_reviews_count, news_count, photos_count, 
                            created_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, (
                        parse_id,
                        sync_dict['business_id'],
                        yandex_url or f"https://yandex.ru/sprav/{external_id or 'unknown'}",
                        'yandex',
                        org_info.get('rating') if org_info else None,
                        len(reviews) if reviews else 0,
                        reviews_without_response,
                        len(posts) if posts else 0,
                        org_info.get('photos_count', 0) if org_info else 0,
                    ))
                    db.conn.commit()
                    print(f"💾 Сохранена история парсинга: {parse_id}")
                except Exception as e:
                    print(f"⚠️ Ошибка сохранения истории парсинга: {e}")
                
                cursor.execute("UPDATE SyncQueue SET status = 'completed', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (sync_dict['id'],))
                db.conn.commit()
                db.close()
                
                print(f"✅ Синхронизация {sync_dict['id']} завершена успешно для бизнеса {business_name}")
            except Exception as e:
                error_details = traceback.format_exc()
                print(f"❌ Ошибка при синхронизации: {e}")
                print(f"❌ Детали ошибки:\n{error_details}")
                
                db = DatabaseManager()
                cursor = db.conn.cursor()
                cursor.execute("UPDATE SyncQueue SET status = 'error', error_message = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                             (str(e), sync_dict['id']))
                cursor.execute("UPDATE ExternalBusinessAccounts SET last_error = ? WHERE id = ?", (str(e), sync_dict['account_id']))
                db.conn.commit()
                db.close()
        else:
            print(f"⚠️ Неизвестный source: {sync_dict['source']}")
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE SyncQueue SET status = 'error', error_message = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                         (f"Неизвестный source: {sync_dict['source']}", sync_dict['id']))
            conn.commit()
            cursor.close()
            conn.close()
    except Exception as e:
        print(f"❌ Ошибка при обработке синхронизации {sync_dict.get('id', 'unknown')}: {e}")
        import traceback
        traceback.print_exc()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE SyncQueue SET status = 'error', error_message = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                         (str(e), sync_dict['id']))
            conn.commit()
        except Exception as update_error:
            print(f"❌ Не удалось обновить статус синхронизации: {update_error}")
        finally:
            cursor.close()
            conn.close()

if __name__ == "__main__":
    print("Worker запущен. Проверка очереди каждые 5 минут...")
    while True:
        process_queue()  # Теперь обрабатывает и parse_card, и sync задачи
        time.sleep(300)  # 5 минут = 300 секунд
