import time
import sqlite3
import os
import uuid
import json
import re
from datetime import datetime, timedelta
import signal
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# New imports
from database_manager import DatabaseManager
from yandex_business_sync_worker import YandexBusinessSyncWorker
# from google_business_sync_worker import GoogleBusinessSyncWorker  # Uncomment when ready

def get_db_connection():
    """Получить соединение с SQLite базой данных"""
    from safe_db_utils import get_db_connection as _get_db_connection
    return _get_db_connection()

def _handle_worker_error(queue_id: str, error_msg: str):
    """Обновить статус задачи на error с сообщением"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE ParseQueue 
            SET status = 'error', 
                error_message = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (error_msg, queue_id))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as ex:
        print(f"❌ Не удалось обновить статус ошибки для {queue_id}: {ex}")

def _extract_date_from_review(review: dict) -> str | int | float | None:
    """Извлечь дату из отзыва, проверяя различные поля"""
    date_fields = ['date', 'published_at', 'publishedAt', 'created_at', 'createdAt', 'time', 'timestamp']
    date_value = review.get('date')
    
    if date_value:
        if isinstance(date_value, str):
            return date_value.strip()
        return date_value
    
    # Пробуем другие поля
    for field in date_fields[1:]:
        date_value = review.get(field)
        if date_value:
            if isinstance(date_value, str):
                return date_value.strip()
            return date_value
    
    return None

def _parse_timestamp_to_datetime(timestamp: int | float) -> datetime | None:
    """Парсить timestamp в datetime (миллисекунды или секунды)"""
    try:
        if timestamp > 1e10:  # Миллисекунды
            return datetime.fromtimestamp(timestamp / 1000.0)
        return datetime.fromtimestamp(timestamp)  # Секунды
    except Exception:
        return None

def _parse_relative_date(date_str: str) -> datetime | None:
    """Парсить относительные даты: 'сегодня', 'вчера', '2 дня назад' и т.д."""
    date_lower = date_str.lower()
    
    if 'сегодня' in date_lower or 'today' in date_lower:
        return datetime.now()
    if 'вчера' in date_lower or 'yesterday' in date_lower:
        return datetime.now() - timedelta(days=1)
    
    # Дни назад
    if any(word in date_str for word in ['дня', 'день', 'дней']):
        days_match = re.search(r'(\d+)', date_str)
        if days_match:
            return datetime.now() - timedelta(days=int(days_match.group(1)))
    
    # Недели назад
    if any(word in date_str for word in ['неделю', 'недели', 'недель']):
        weeks_match = re.search(r'(\d+)', date_str)
        weeks_ago = int(weeks_match.group(1)) if weeks_match else 1
        return datetime.now() - timedelta(weeks=weeks_ago)
    
    # Месяцы назад
    if any(word in date_str for word in ['месяц', 'месяца', 'месяцев']):
        months_match = re.search(r'(\d+)', date_str)
        months_ago = int(months_match.group(1)) if months_match else 1
        return datetime.now() - timedelta(days=months_ago * 30)
    
    # Годы назад
    if any(word in date_str for word in ['год', 'года', 'лет']):
        years_match = re.search(r'(\d+)', date_str)
        years_ago = int(years_match.group(1)) if years_match else 1
        return datetime.now() - timedelta(days=years_ago * 365)
    
    return None

def _parse_russian_date(date_str: str) -> datetime | None:
    """Парсинг русских дат типа '27 января 2026' или '10 октября'"""
    try:
        months = {
            'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4, 'мая': 5, 'июня': 6,
            'июля': 7, 'августа': 8, 'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12,
            'янв': 1, 'фев': 2, 'мар': 3, 'апр': 4, 'май': 5, 'июн': 6,
            'июл': 7, 'авг': 8, 'сен': 9, 'окт': 10, 'ноя': 11, 'дек': 12
        }
        
        parts = date_str.lower().split()
        if len(parts) >= 2:
            day_str = parts[0]
            month_str = parts[1]
            year_str = parts[2] if len(parts) > 2 else str(datetime.now().year)
            
            # Очистка от лишних символов
            day_str = re.sub(r'\D', '', day_str)
            year_str = re.sub(r'\D', '', year_str)
            
            if not day_str or not month_str:
                return None
                
            day = int(day_str)
            month = months.get(month_str)
            year = int(year_str)
            
            if month:
                return datetime(year, month, day)
                
    except Exception:
        pass
    return None

def _parse_date_string(date_str: str) -> datetime | None:
    """Парсить строку даты в datetime"""
    if not date_str or not isinstance(date_str, str):
        return None
    
    date_str = date_str.strip()
    if not date_str:
        return None
    
    # Пробуем относительные даты
    relative = _parse_relative_date(date_str)
    if relative:
        return relative
    
    # Пробуем русские даты (27 января 2026)
    russian_date = _parse_russian_date(date_str)
    if russian_date:
        return russian_date
    
    # Пробуем русские даты (27 января 2026)
    russian_date = _parse_russian_date(date_str)
    if russian_date:
        return russian_date
    
    # Пробуем ISO формат
    try:
        if 'T' in date_str or 'Z' in date_str or date_str.count('-') >= 2:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except Exception:
        pass
    
    # Пробуем dateutil для других форматов
    try:
        from dateutil import parser as date_parser
        return date_parser.parse(date_str, fuzzy=True)
    except Exception:
        return None

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
    # Устанавливаем таймаут 10 минут
    def timeout_handler(signum, frame):
        raise TimeoutError("Parsing task timed out after 10 minutes")
    
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(600)
    
    try:
        if not queue_dict.get("url"):
            raise ValueError("URL не указан для задачи парсинга")
        
        url = queue_dict["url"]
        
        # --- АВТОМАТИЧЕСКОЕ ИСПРАВЛЕНИЕ ССЫЛОК (SPRAV -> MAPS) ---
        if '/sprav/' in url:
            import re
            # Ищем ID организации (цифры)
            sprav_match = re.search(r'/sprav/(\d+)', url)
            if sprav_match:
                org_id = sprav_match.group(1)
                # Конвертируем в публичную ссылку карт
                new_url = f"https://yandex.ru/maps/org/redirect/{org_id}"
                print(f"⚠️ ОБНАРУЖЕНА ССЫЛКА НА ЛИЧНЫЙ КАБИНЕТ: {url}")
                print(f"🔄 АВТОМАТИЧЕСКАЯ ЗАМЕНА НА: {new_url}")
                url = new_url
                queue_dict['url'] = new_url # Обновляем и в словаре

        card_data = parse_yandex_card(url)
        
        # Проверяем успешность парсинга
        business_id = queue_dict.get("business_id")
        is_successful, reason = _is_parsing_successful(card_data, business_id)
        
        fallback_created = False
        if not is_successful and business_id:
            # DISABLE AUTOMATIC FALLBACK (User Request 2026-01-23)
            # Fallback to cabinet parsing should be manual only.
            # has_account, account_id = _has_cabinet_account(business_id)
            # if has_account: ...
            
            # Проверяем, есть ли кабинет для fallback
            # has_account, account_id = _has_cabinet_account(business_id)
            
            # if has_account:
            #     print(f"⚠️ Парсинг неполный ({reason}), создаю задачу fallback через кабинет")
                
            #     # Создаем задачу fallback
            #     fallback_task_id = str(uuid.uuid4())
            #     conn = get_db_connection()
            #     cursor = conn.cursor()
                
            #     try:
            #         cursor.execute("""
            #             INSERT INTO ParseQueue (
            #                 id, business_id, account_id, task_type, source,
            #                 status, user_id, url, created_at, updated_at
            #             )
            #             VALUES (?, ?, ?, 'parse_cabinet_fallback', 'yandex_business',
            #                     'pending', ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            #         """, (fallback_task_id, business_id, account_id, queue_dict["user_id"], queue_dict["url"]))
            #         conn.commit()
            #         print(f"✅ Создана задача fallback: {fallback_task_id}")
            #         fallback_created = True
            #     finally:
            #         cursor.close()
            #         conn.close()
            print(f"⚠️ Парсинг неполный ({reason}). Автоматический fallback отключен.")
        
        if card_data.get("error") == "captcha_detected":
            # Если был создан фоллбэк, то считаем задачу выполненной, не уходим в цикл
            if fallback_created:
                print(f"✅ Капча обнаружена, но создан фоллбэк. Помечаю задачу как выполненную, чтобы не зацикливать.")
                conn = get_db_connection()
                cursor = conn.cursor()
                try:
                    cursor.execute("UPDATE ParseQueue SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", ("done", queue_dict["id"]))
                    cursor.execute("DELETE FROM ParseQueue WHERE id = ?", (queue_dict["id"],))
                    conn.commit()
                finally:
                    cursor.close()
                    conn.close()
                return

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
        if not is_successful and card_data.get("error") != "captcha_detected":
            print(f"❌ Парсинг неуспешен: {reason}. Сохранение отменено.")
            
            # Обновляем статус задачи на error
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE ParseQueue 
                SET status = 'error', 
                    error_message = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (f"Parsing failed: {reason}", queue_dict["id"]))
            conn.commit()
            cursor.close()
            conn.close()
            return

        business_id = queue_dict.get("business_id")
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            if business_id:
                # Новая логика: сохраняем в MapParseResults
                print(f"📊 Сохраняю результаты в MapParseResults для business_id={business_id}")
                
                try:
                    # Используем GigaChat для анализа, как и в старой логике
                    from gigachat_analyzer import analyze_business_data
                    from report import generate_html_report
                    
                    print(f"🤖 Запускаем GigaChat анализ для {business_id}...")
                    analysis_result = analyze_business_data(card_data)
                    
                    # Формируем данные для отчета
                    analysis_data = {
                        'score': analysis_result.get('score', 50),
                        'recommendations': analysis_result.get('recommendations', []),
                        'ai_analysis': analysis_result.get('analysis', {})
                    }
                    
                    # Генерируем отчет
                    report_path = generate_html_report(card_data, analysis_data, {})
                    print(f"📄 Отчет сгенерирован: {report_path}")
                    
                    # Сохраняем анализ для использования в рекомендациях (JSON)
                    analysis_json = json.dumps(analysis_data['ai_analysis'], ensure_ascii=False)
                    
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
                    
                    # Sync reviews_count with parsed count if parsed is higher (fixing UI inconsistency)
                    parsed_reviews_count = len(reviews_list)
                    if parsed_reviews_count > int(reviews_count):
                        print(f"⚠️ Parsed more reviews ({parsed_reviews_count}) than header count ({reviews_count}). Updating count.")
                        reviews_count = parsed_reviews_count

                    url_lower = (queue_dict["url"] or '').lower()
                    map_type = 'yandex' if 'yandex' in url_lower else ('google' if 'google' in url_lower else 'other')
                    
                    parse_result_id = str(uuid.uuid4())
                    
                    # Убеждаемся, что колонка unanswered_reviews_count существует
                    _ensure_column_exists(cursor, conn, "MapParseResults", "unanswered_reviews_count", "INTEGER")
                    
                    # Убеждаемся, что колонки для профайла бизнеса существуют
                    profile_columns = [
                        ("is_verified", "INTEGER DEFAULT 0"),
                        ("phone", "TEXT"),
                        ("website", "TEXT"),
                        ("messengers", "TEXT"),  # JSON
                        ("working_hours", "TEXT"),  # JSON
                        ("services_count", "INTEGER DEFAULT 0"),
                        ("profile_completeness", "INTEGER DEFAULT 0"),
                    ]
                    for col_name, col_type in profile_columns:
                        _ensure_column_exists(cursor, conn, "MapParseResults", col_name, col_type)
                    
                    # Извлекаем данные профайла из card_data
                    phone = card_data.get('phone', '') or ''
                    website = card_data.get('site', '') or card_data.get('website', '') or ''
                    
                    # Messengers (собираем из social_links)
                    messengers = []
                    social_links = card_data.get('social_links', [])
                    for link in social_links:
                        link_lower = link.lower()
                        if 'whatsapp' in link_lower or 'wa.me' in link_lower:
                            messengers.append({'type': 'whatsapp', 'url': link})
                        elif 't.me' in link_lower or 'telegram' in link_lower:
                            messengers.append({'type': 'telegram', 'url': link})
                        elif 'viber' in link_lower:
                            messengers.append({'type': 'viber', 'url': link})
                    messengers_json = json.dumps(messengers, ensure_ascii=False) if messengers else None
                    
                    # Working hours (преобразуем в структурированный JSON)
                    hours_full = card_data.get('hours_full', [])
                    hours_json = json.dumps({'schedule': hours_full}, ensure_ascii=False) if hours_full else None
                    
                    # Services count
                    products = card_data.get('products', [])
                    services_count = sum(len(cat.get('items', [])) for cat in products)
                    
                    # Ensure numeric values are integers
                    try:
                        photos_count = int(photos_count)
                    except (ValueError, TypeError):
                        photos_count = 0
                        
                    try:
                        reviews_count = int(reviews_count)
                    except (ValueError, TypeError):
                        reviews_count = 0
                        
                    try:
                        news_count = int(news_count)
                    except (ValueError, TypeError):
                        news_count = 0
                    
                    # Verification badge
                    is_verified = 1 if card_data.get('is_verified') else 0
                    
                    # Profile completeness calculation (Service Call)
                    try:
                        from services.analytics_service import calculate_profile_completeness
                        
                        # Prepare data for analysis
                        analysis_data = {
                            'phone': phone,
                            'website': website,
                            'schedule': hours_json,
                            'photos_count': photos_count,
                            'services_count': services_count,
                            'description': card_data.get('description'),
                            'messengers': messengers,
                            'is_verified': is_verified
                        }
                        
                        profile_completeness = calculate_profile_completeness(analysis_data)
                        print(f"   📊 Расчет completed service: {profile_completeness}%")
                        
                    except ImportError:
                         print("⚠️ Не удалось импортировать services.analytics_service")
                         profile_completeness = 0
                    except Exception as comp_err:
                        print(f"⚠️ Ошибка расчета заполненности профиля (worker): {comp_err}")
                        profile_completeness = 0
                    
                    # Всегда используем колонки (они будут созданы если их нет)
                    cursor.execute("""
                        INSERT INTO MapParseResults
                        (id, business_id, url, map_type, rating, reviews_count, unanswered_reviews_count, 
                         news_count, photos_count, report_path, 
                         is_verified, phone, website, messengers, working_hours, services_count, profile_completeness,
                         title, address,
                         created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
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
                        report_path,
                        is_verified,
                        phone,
                        website,
                        messengers_json,
                        hours_json,
                        services_count,
                        profile_completeness,
                        card_data.get('name', ''),
                        card_data.get('address', '')
                    ))
                    
                    print(f"✅ Результаты сохранены в MapParseResults: {parse_result_id}")
                    print(f"   📊 Профайл: телефон={bool(phone)}, сайт={bool(website)}, часы={bool(hours_json)}, услуг={services_count}, заполненность={profile_completeness}%")
                    
                    # Commit main connection to release write lock for DatabaseManager
                    conn.commit()
                    
                    # --- ИНИЦИАЛИЗАЦИЯ SyncWorker ДЛЯ СОХРАНЕНИЯ ДЕТАЛЬНЫХ ДАННЫХ ---
                    try:
                        from external_sources import ExternalReview, ExternalSource, ExternalPost, ExternalStatsPoint, make_stats_id
                        from yandex_business_sync_worker import YandexBusinessSyncWorker
                        from dateutil import parser as date_parser
                        import re
                        
                        db_manager = None
                        try:
                            # Используем DatabaseManager для работы с репозиториями
                            db_manager = DatabaseManager()
                            sync_worker = YandexBusinessSyncWorker()
                            
                            # DEBUG LOGGING
                            try:
                                from worker_debug_helper import debug_log
                                from safe_db_utils import get_db_path
                                db_path_debug = get_db_path()
                                r_len = len(reviews_list) if reviews_list else 0
                                debug_log(f"Worker DB Path: {db_path_debug}")
                                debug_log(f"Reviews in list: {r_len}")
                                debug_log(f"Unanswered calc: {unanswered_reviews_count}")
                            except Exception as e:
                                print(f"Debug log fail: {e}")
                            
                            # 1. СОХРАНЕНИЕ ОТЗЫВОВ (С ДЕДУПЛИКАЦИЕЙ)
                            if reviews_list:
                                external_reviews = []
                                seen_review_ids = set()
                                
                                for review in reviews_list:
                                    if not review.get('text'):
                                        continue
                                    
                                    # Дедупликация: используем ID отзыва или хеш от текста+автора
                                    raw_id = review.get('id')
                                    if raw_id:
                                        unique_key = str(raw_id)
                                    else:
                                        author = review.get('author') or 'Anon'
                                        text_snippet = (review.get('text') or '')[:50]
                                        unique_key = f"{author}_{text_snippet}"
                                        
                                    if unique_key in seen_review_ids:
                                        continue
                                    seen_review_ids.add(unique_key)
                                    
                                    # Генерируем ID для нашей БД (детерминированный, чтобы избегать дублей)
                                    # Используем business_id + author + text snippet (без ответа, чтобы ответ обновлял запись, а не создавал новую)
                                    text_part = (review.get('text') or '').strip()
                                    unique_string = f"{business_id}_{review.get('author')}_{text_part}"
                                    review_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, unique_string))
                                    external_review_id = raw_id or f"html_{review_id}"
                                    
                                    # Парсим дату
                                    published_at = None
                                    date_value = _extract_date_from_review(review)
                                    
                                    if date_value:
                                        if isinstance(date_value, (int, float)):
                                            published_at = _parse_timestamp_to_datetime(date_value)
                                        elif isinstance(date_value, str):
                                            published_at = _parse_date_string(date_value)
                                    
                                    # Ответ организации
                                    response_text = review.get('org_reply') or review.get('response_text') or ''
                                    response_text = response_text.strip() if response_text else None
                                    response_at = None
                                    
                                    if review.get('response_date'):
                                        response_at = _parse_date_string(str(review.get('response_date')))
                                    
                                    # Рейтинг
                                    r_val = review.get('score') or review.get('rating')
                                    try:
                                        r_val = int(r_val) if r_val else None
                                    except:
                                        r_val = None
                                    
                                    external_review = ExternalReview(
                                        id=review_id,
                                        business_id=business_id,
                                        source=ExternalSource.YANDEX_MAPS,
                                        external_review_id=external_review_id,
                                        rating=r_val,
                                        author_name=review.get('author') or 'Анонимный пользователь',
                                        text=review.get('text'),
                                        published_at=published_at,
                                        response_text=response_text,
                                        response_at=response_at,
                                        raw_payload=review
                                    )
                                    external_reviews.append(external_review)
                                
                                if external_reviews:
                                    sync_worker._upsert_reviews(db_manager, external_reviews)
                                    print(f"💾 Сохранено {len(external_reviews)} уникальных отзывов (было {len(reviews_list)})")

                            # 2. СОХРАНЕНИЕ НОВОСТЕЙ (Posts)
                            news_items = card_data.get('news', [])
                            if news_items:
                                external_posts = []
                                for item in news_items:
                                    post_text = item.get('text')
                                    if not post_text:
                                        continue
                                        
                                    post_id = str(uuid.uuid4())
                                    # Пытаемся дату достать
                                    pub_at = None
                                    if item.get('date'):
                                        pub_at = _parse_date_string(item['date'])
                                        
                                    ext_post = ExternalPost(
                                        id=post_id,
                                        business_id=business_id,
                                        source=ExternalSource.YANDEX_MAPS,
                                        external_post_id=f"html_{post_id}", # Нет реального ID в HTML
                                        title=item.get('title') or (post_text[:30] + '...'),
                                        text=post_text,
                                        published_at=pub_at or datetime.now(), # Fallback to now if no date
                                        image_url=None, # HTML scraper rarely gets clean image URLs for news context
                                        raw_payload=item
                                    )
                                    external_posts.append(ext_post)
                                
                                if external_posts:
                                    sync_worker._upsert_posts(db_manager, external_posts)
                                    print(f"💾 Сохранено {len(external_posts)} новостей")

                            # 3. СОХРАНЕНИЕ УСЛУГ (Services)
                            products = card_data.get('products')
                            if products:
                                services_count = len(products)
                                sync_worker._sync_services_to_db(db_manager.conn, business_id, products)
                                print(f"💾 Синхронизировано {services_count} услуг")

                            # 4. СОХРАНЕНИЕ СТАТИСТИКИ (Rating History)
                            if rating and reviews_count is not None:
                                today = datetime.now().strftime('%Y-%m-%d')
                                stats_id = make_stats_id(business_id, ExternalSource.YANDEX_MAPS, today)
                                
                                try:
                                    rating_val = float(rating)
                                except:
                                    rating_val = 0.0
                                    
                                stat_point = ExternalStatsPoint(
                                    id=stats_id,
                                    business_id=business_id,
                                    source=ExternalSource.YANDEX_MAPS,
                                    date=today,
                                    rating=rating_val,
                                    reviews_total=reviews_count,
                                    # Остальные поля None, так как публичные карты их не дают
                                    views_total=None,
                                    actions_total=None
                                )
                                sync_worker._upsert_stats(db_manager, [stat_point])
                                print(f"💾 Сохранена статистика (Рейтинг: {rating_val}, Отзывов: {reviews_count})")

                            # Commit changes to External Data tables
                            if db_manager and db_manager.conn:
                                db_manager.conn.commit()
                                print("💾 Detailed data committed successfully")

                        finally:
                            if db_manager:
                                db_manager.close()
                                
                    except Exception as det_err:
                        print(f"⚠️ Ошибка сохранения детальных данных (reviews/posts/stats): {det_err}")
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
                
                # Попытка синхронизации сервисов даже для старой схемы (если есть owner_id)
                # Но у нас нет business_id здесь, поэтому пропускаем
                pass
                
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
            
            # --- SYNC SERVICES AFTER PARSING (NEW) ---
            if business_id and card_data.get('products'):
                try:
                    print(f"🔄 Синхронизация услуг для business_id={business_id}...")
                    _sync_parsed_services_to_db(business_id, card_data.get('products'), conn)
                    print(f"✅ Услуги успешно синхронизированы.")
                except Exception as sync_error:
                    print(f"⚠️ Ошибка синхронизации услуг: {sync_error}")
                    import traceback
                    traceback.print_exc()
            
            # Обновляем статус на "done" и удаляем заявку из очереди
            # Обновляем статус на "completed" (чтобы задача осталась в списке)
            cursor.execute("UPDATE ParseQueue SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", ("completed", queue_dict["id"]))
            # cursor.execute("DELETE FROM ParseQueue WHERE id = ?", (queue_dict["id"],)) -> Удаление отключено по просьбе пользователя
            conn.commit()
            
            print(f"✅ Заявка {queue_dict['id']} обработана и удалена из очереди.")
            signal.alarm(0)  # Отключаем таймаут при успехе
            
        finally:
            try:
                if 'cursor' in locals() and cursor:
                    cursor.close()
            except:
                pass
            try:
                if 'conn' in locals() and conn:
                    conn.close()
            except:
                pass
            
    except Exception as e:
        signal.alarm(0)  # Отключаем таймаут при ошибке
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

def _sync_parsed_services_to_db(business_id: str, products: list, conn: sqlite3.Connection):
    """
    Синхронизирует распаршенные услуги в таблицу UserServices.
    Добавляет новые, обновляет цены существующих.
    """
    if not products:
        return

    cursor = conn.cursor()
    
    # 1. Проверяем наличие таблицы UserServices и нужных колонок
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='UserServices'")
    if not cursor.fetchone():
        # Если таблицы нет, создаём (должна быть, но на всякий случай)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS UserServices (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                category TEXT,
                price INTEGER, -- цена в копейках
                duration INTEGER DEFAULT 60,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES Businesses(id) ON DELETE CASCADE
            )
        """)
    
    count_new = 0
    count_updated = 0
    
    for category_data in products:
        category_name = category_data.get('category', 'Разное')
        items = category_data.get('items', [])
        
        for item in items:
            name = item.get('name')
            if not name:
                continue
                
            raw_price = item.get('price', '')
            description = item.get('description', '')
            
            # Парсинг цены
            price_cents = None
            if raw_price:
                # Удаляем все нецифровые символы кроме разделителей
                try:
                    # Ищем числа в строке
                    import re
                    # "от 1 500 ₽" -> "1500"
                    digits = re.sub(r'[^0-9]', '', str(raw_price))
                    if digits:
                        price_cents = int(digits) * 100 # В копейки
                except:
                    pass
            
            # Ищем существующую услугу по имени и business_id
            cursor.execute("""
                SELECT id FROM UserServices 
                WHERE business_id = ? AND name = ?
            """, (business_id, name))
            
            row = cursor.fetchone()
            
            if row:
                # Обновляем существующую
                service_id = row[0]
                cursor.execute("""
                    UPDATE UserServices 
                    SET price = ?, description = ?, category = ?, updated_at = CURRENT_TIMESTAMP, is_active = 1
                    WHERE id = ?
                """, (price_cents, description, category_name, service_id))
                count_updated += 1
            else:
                # Создаем новую
                service_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO UserServices (id, business_id, name, description, category, price, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, 1)
                """, (service_id, business_id, name, description, category_name, price_cents))
                count_new += 1
                
    conn.commit()
    print(f"📊 Синхронизация услуг завершена: {count_new} новых, {count_updated} обновлено.")

def _process_sync_yandex_business_task(queue_dict):
    """Обработка синхронизации Яндекс.Бизнес через кабинет"""
    import signal
    import sys
    
    # Устанавливаем таймаут 10 минут для задачи
    def timeout_handler(signum, frame):
        raise TimeoutError("Задача синхронизации превысила таймаут 10 минут")
    
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(600)  # 10 минут
    
    try:
        business_id = queue_dict.get("business_id")
        account_id = queue_dict.get("account_id")
        
        if not business_id or not account_id:
            print(f"❌ Отсутствует business_id или account_id для задачи {queue_dict.get('id')}", flush=True)
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
            signal.alarm(0)  # Отменяем таймаут
            return
        
        print(f"🔄 Синхронизация Яндекс.Бизнес для бизнеса {business_id}", flush=True)
        
        from yandex_business_parser import YandexBusinessParser
        from yandex_business_sync_worker import YandexBusinessSyncWorker
        from auth_encryption import decrypt_auth_data
        from database_manager import DatabaseManager
        import json
        import traceback
        
        # Получаем auth_data
        db = None  # Initialize to None for safe cleanup
        try:
            db = DatabaseManager()
            cursor = db.conn.cursor()
        

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
            # Проверяем наличие колонки unanswered_reviews_count
            cursor.execute("PRAGMA table_info(MapParseResults)")
            columns = [row[1] for row in cursor.fetchall()]
            has_unanswered = 'unanswered_reviews_count' in columns
            
            if has_unanswered:
                cursor.execute("""
                    SELECT rating, reviews_count, unanswered_reviews_count, news_count, photos_count
                    FROM MapParseResults
                    WHERE business_id = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (business_id,))
            else:
                cursor.execute("""
                    SELECT rating, reviews_count, news_count, photos_count
                    FROM MapParseResults
                    WHERE business_id = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (business_id,))
            existing_data = cursor.fetchone()
            
            # Используем данные из кабинета (приоритет кабинету)
            # Используем данные из кабинета, но с защитой от перезаписи нулями
            # Рейтинг
            rating = org_info.get('rating')
            if not rating and existing_data and existing_data[0]:
                rating = existing_data[0]
            
            # Отзывы
            current_reviews_count = len(reviews) if reviews else 0
            if current_reviews_count == 0 and existing_data:
                # Определяем индекс reviews_count в existing_data
                # Запрос: rating (0), reviews_count (1), ...
                if existing_data[1] and existing_data[1] > 0:
                    reviews_count = existing_data[1]
                else:
                    reviews_count = 0
            else:
                reviews_count = current_reviews_count

            # Неотвеченные
            current_unanswered = sum(1 for r in reviews if not r.response_text) if reviews else 0
            if current_reviews_count == 0 and existing_data and has_unanswered:
                # rating(0), reviews(1), unanswered(2)
                if existing_data[2] is not None:
                     reviews_without_response = existing_data[2]
                else:
                     reviews_without_response = 0
            else:
                reviews_without_response = current_unanswered
                
            # Новости (posts)
            current_news = len(posts) if posts else 0
            if current_news == 0 and existing_data:
                # Индекс зависит от has_unanswered
                idx = 3 if has_unanswered else 2
                if existing_data[idx] and existing_data[idx] > 0:
                    news_count = existing_data[idx]
                else:
                    news_count = 0
            else:
                 news_count = current_news
                 
            # Фото
            current_photos = org_info.get('photos_count', 0) if org_info else 0
            if current_photos == 0 and existing_data:
                idx = 4 if has_unanswered else 3
                if existing_data[idx] and existing_data[idx] > 0:
                     photos_count = existing_data[idx]
                else:
                     photos_count = 0
            else:
                photos_count = current_photos
            
            # Сохраняем в MapParseResults
            parse_id = str(uuid.uuid4())
            url = f"https://yandex.ru/sprav/{external_id or 'unknown'}"
            
            if has_unanswered:
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
            else:
                cursor.execute("""
                    INSERT INTO MapParseResults (
                        id, business_id, url, map_type, rating, reviews_count, 
                        news_count, photos_count, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    parse_id,
                    business_id,
                    url,
                    'yandex',
                    rating,
                    reviews_count,
                    news_count,
                    photos_count,
                ))
            
            # Также сохраняем в историю метрик для графиков
            try:
                metric_history_id = str(uuid.uuid4())
                current_date = datetime.now().strftime('%Y-%m-%d')
                
                # Проверяем, есть ли уже запись за сегодня от парсинга
                cursor.execute("""
                    SELECT id FROM BusinessMetricsHistory 
                    WHERE business_id = ? AND metric_date = ? AND source = 'parsing'
                """, (business_id, current_date))
                
                existing_metric = cursor.fetchone()
                
                if existing_metric:
                    cursor.execute("""
                        UPDATE BusinessMetricsHistory 
                        SET rating = ?, reviews_count = ?, photos_count = ?, news_count = ?
                        WHERE id = ?
                    """, (rating, reviews_count, photos_count, news_count, existing_metric[0]))
                else:
                    cursor.execute("""
                        INSERT INTO BusinessMetricsHistory (
                            id, business_id, metric_date, rating, reviews_count, 
                            photos_count, news_count, source
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, 'parsing')
                    """, (
                        metric_history_id, 
                        business_id, 
                        current_date, 
                        rating, 
                        reviews_count, 
                        photos_count, 
                        news_count
                    ))
            except Exception as e:
                print(f"Error saving metrics history: {e}")
            
            db.conn.commit()
            # Safely close db and connections
            try:
                if 'db' in locals() and db:
                    db.close()
            except Exception:
                pass
            
            # The cursor and conn here refer to the ones created within the try block
            # associated with the DatabaseManager instance.
            # The subsequent conn/cursor are for the ParseQueue update.
            try:
                if 'cursor' in locals() and cursor and not cursor.closed: # Check if cursor is not already closed by db.close()
                    cursor.close()
            except Exception:
                pass
                
            try:
                if 'conn' in locals() and conn and not conn.closed: # Check if conn is not already closed by db.close()
                    conn.close()
            except Exception:
                pass
            
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
            try:
                if cursor:
                    cursor.close()
            except Exception:
                pass
            try:
                if conn:
                    conn.close()
            except Exception:
                pass
            
            print(f"✅ Синхронизация завершена для бизнеса {business_id}", flush=True)
            signal.alarm(0)  # Отменяем таймаут при успехе
            
        except TimeoutError as e:
            print(f"⏱️ Таймаут синхронизации: {e}", flush=True)
            signal.alarm(0)
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
            try:
                if cursor:
                    cursor.close()
            except:
                pass
            try:
                if conn:
                    conn.close()
            except:
                pass
            
        except Exception as e:
            print(f"❌ Ошибка синхронизации: {e}", flush=True)
            import traceback
            traceback.print_exc(file=sys.stdout)
            sys.stdout.flush()
            signal.alarm(0)  # Отменяем таймаут при ошибке
            
            # Safely close db if it was created
            try:
                if 'db' in locals() and db:
                    db.close()
            except:
                pass
            
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
            try:
                if cursor:
                    cursor.close()
            except:
                pass
            try:
                if conn:
                    conn.close()
            except:
                pass
            
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
        try:
            if cursor:
                cursor.close()
        except:
            pass
        try:
            if conn:
                conn.close()
        except:
            pass

def _process_cabinet_fallback_task(queue_dict):
    """Обработка fallback парсинга через кабинет"""
    business_id = queue_dict.get("business_id")
    account_id = queue_dict.get("account_id")
    
    if not business_id or not account_id:
        print(f"❌ Отсутствует business_id или account_id для задачи {queue_dict.get('id')}", flush=True)
        _handle_worker_error(queue_dict["id"], "Отсутствует business_id или account_id")
        return
    
    print(f"🔄 Fallback парсинг через кабинет для бизнеса {business_id}", flush=True)
    
    try:
        from yandex_business_sync_worker import YandexBusinessSyncWorker
        
        # Используем sync_account для получения данных из кабинета
        worker = YandexBusinessSyncWorker()
        worker.sync_account(account_id)
        
        # Обновляем статус задачи в ParseQueue
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE ParseQueue 
            SET status = 'completed', 
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (queue_dict["id"],))
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"✅ Fallback парсинг завершен для бизнеса {business_id}", flush=True)
        
    except Exception as e:
        print(f"❌ Ошибка fallback парсинга: {e}", flush=True)
        import traceback
        traceback.print_exc(file=sys.stdout)
        sys.stdout.flush()
        _handle_worker_error(queue_dict["id"], str(e))


if __name__ == "__main__":
    print("Worker запущен. Проверка очереди каждые 5 минут...")
    while True:
        try:
            process_queue()
        except Exception as e:
            print(f"❌ Критическая ошибка worker loop: {e}", flush=True)
            import traceback
            traceback.print_exc(file=sys.stdout)
            sys.stdout.flush()
        
        try:    
            time.sleep(10)  # 10 секунд
        except Exception as e:
             # Если sleep прерван сигналом или ошибкой, просто логируем и продолжаем
             print(f"⚠️ Sleep interrupted: {e}", flush=True)
