import time
import sqlite3
import os
import uuid
from datetime import datetime, timedelta

def get_db_connection():
    """Получить соединение с SQLite базой данных"""
    from safe_db_utils import get_db_connection as _get_db_connection
    return _get_db_connection()

from parser import parse_yandex_card
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
        try:
            cursor.execute("PRAGMA table_info(ParseQueue)")
            columns = [row[1] for row in cursor.fetchall()]
            
            if 'retry_after' not in columns:
                print("📝 Добавляю поле retry_after в ParseQueue...")
                cursor.execute("ALTER TABLE ParseQueue ADD COLUMN retry_after TEXT")
                conn.commit()
            
            if 'business_id' not in columns:
                print("📝 Добавляю поле business_id в ParseQueue...")
                cursor.execute("ALTER TABLE ParseQueue ADD COLUMN business_id TEXT")
                conn.commit()
        except Exception as e:
            print(f"⚠️ Ошибка проверки структуры ParseQueue: {e}")
        
        # Получаем заявки из очереди
        cursor.execute("""
            SELECT * FROM ParseQueue 
            WHERE status = 'pending' 
            OR (status = 'captcha' AND (retry_after IS NULL OR retry_after <= ?))
            ORDER BY 
                CASE 
                    WHEN status = 'pending' THEN 1
                    WHEN status = 'captcha' AND (retry_after IS NULL OR retry_after <= ?) THEN 2
                    ELSE 3
                END,
                created_at ASC 
            LIMIT 1
        """, (datetime.now().isoformat(), datetime.now().isoformat()))
        queue_item = cursor.fetchone()
        
        if not queue_item:
            return
        
        # Преобразуем Row в словарь
        try:
            columns = [description[0] for description in cursor.description]
            queue_dict = {columns[i]: queue_item[i] for i in range(len(columns))}
        except:
            queue_dict = {
                'id': queue_item[0],
                'url': queue_item[1],
                'user_id': queue_item[2],
                'status': queue_item[3],
                'created_at': queue_item[4] if len(queue_item) > 4 else None,
                'business_id': queue_item[5] if len(queue_item) > 5 else None
            }
        
        # Обновляем статус на "processing"
        cursor.execute("UPDATE ParseQueue SET status = ? WHERE id = ?", ("processing", queue_dict["id"]))
        conn.commit()
    finally:
        # ВАЖНО: Закрываем соединение перед долгим парсингом
        cursor.close()
        conn.close()
    
    if not queue_dict:
        return
    
    print("Обрабатываю заявку:", queue_dict)
    
    # ШАГ 2: Парсим данные (БЕЗ открытого соединения с БД)
    try:
        card_data = parse_yandex_card(queue_dict["url"])
        
        if card_data.get("error") == "captcha_detected":
            # Открываем новое соединение только для обновления статуса капчи
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                retry_after = datetime.now() + timedelta(hours=2)
                cursor.execute("SELECT COUNT(*) FROM ParseQueue WHERE status = 'pending' AND id != ?", (queue_dict["id"],))
                pending_count = cursor.fetchone()[0]
                
                if pending_count > 0:
                    cursor.execute("UPDATE ParseQueue SET status = ?, retry_after = ?, created_at = ? WHERE id = ?", 
                                 ("captcha", retry_after.isoformat(), datetime.now().isoformat(), queue_dict["id"]))
                else:
                    cursor.execute("UPDATE ParseQueue SET status = ?, retry_after = ? WHERE id = ?", 
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
                    
                    # Проверяем наличие колонки unanswered_reviews_count
                    cursor.execute("PRAGMA table_info(MapParseResults)")
                    columns = [row[1] for row in cursor.fetchall()]
                    has_unanswered_col = 'unanswered_reviews_count' in columns
                    
                    if has_unanswered_col:
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
                    else:
                        cursor.execute("""
                            INSERT INTO MapParseResults
                            (id, business_id, url, map_type, rating, reviews_count, news_count, photos_count, report_path, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """, (
                            parse_result_id,
                            business_id,
                            queue_dict["url"],
                            map_type,
                            str(rating),
                            int(reviews_count or 0),
                            int(news_count or 0),
                            int(photos_count or 0),
                            report_path
                        ))
                    
                    print(f"✅ Результаты сохранены в MapParseResults: {parse_result_id}")
                    
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
            cursor.execute("UPDATE ParseQueue SET status = ? WHERE id = ?", ("done", queue_dict["id"]))
            cursor.execute("DELETE FROM ParseQueue WHERE id = ?", (queue_dict["id"],))
            conn.commit()
            
            print(f"✅ Заявка {queue_dict['id']} обработана и удалена из очереди.")
            
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        queue_id = queue_dict.get('id', 'unknown')
        print(f"❌ Ошибка при обработке заявки {queue_id}: {e}")
        import traceback
        traceback.print_exc()
        
        # Открываем новое соединение для обновления статуса ошибки
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE ParseQueue SET status = ? WHERE id = ?", ("error", queue_id))
            conn.commit()
            print(f"⚠️ Заявка {queue_id} помечена как ошибка.")
            
            try:
                from user_api import send_email
                send_email(
                    "demyanovap@yandex.ru",
                    "Ошибка парсинга карты",
                    f"URL: {queue_dict.get('url', 'unknown')}\nОшибка: {e}"
                )
            except:
                pass
        except Exception as update_error:
            print(f"❌ Не удалось обновить статус заявки {queue_id}: {update_error}")
        finally:
            cursor.close()
            conn.close()

if __name__ == "__main__":
    print("Worker запущен. Проверка очереди каждые 5 минут...")
    while True:
        process_queue()
        time.sleep(300)  # 5 минут = 300 секунд
