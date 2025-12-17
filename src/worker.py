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
    
    # Получаем заявки из очереди с учетом отсрочки и приоритета
    # 1. Сначала pending без отсрочки
    # 2. Потом captcha, у которых истекла отсрочка
    # 3. captcha с отсрочкой идут в конец очереди
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
        conn.close()
        return
    
    # Преобразуем Row в словарь для удобства
    try:
        columns = [description[0] for description in cursor.description]
        queue_dict = {columns[i]: queue_item[i] for i in range(len(columns))}
    except:
        # Если не удалось получить columns, используем прямые индексы
        queue_dict = {
            'id': queue_item[0],
            'url': queue_item[1],
            'user_id': queue_item[2],
            'status': queue_item[3],
            'created_at': queue_item[4] if len(queue_item) > 4 else None,
            'business_id': queue_item[5] if len(queue_item) > 5 else None
        }
    
    print("Обрабатываю заявку:", queue_dict)
    
    # Обновляем статус на "processing"
    try:
        cursor.execute("UPDATE ParseQueue SET status = ? WHERE id = ?", ("processing", queue_dict["id"]))
        conn.commit()
    except Exception as e:
        print(f"⚠️ Не удалось обновить статус на processing: {e}")
    
    try:
        # Парсим данные с Яндекс.Карт
        card_data = parse_yandex_card(queue_dict["url"])
        
        if card_data.get("error") == "captcha_detected":
            print(f"Обнаружена капча для заявки {queue_dict['id']}! Устанавливаю отсрочку на 2 часа...")
            
            # Устанавливаем отсрочку на 2 часа
            retry_after = datetime.now() + timedelta(hours=2)
            
            # Проверяем, есть ли другие pending задачи
            cursor.execute("SELECT COUNT(*) FROM ParseQueue WHERE status = 'pending' AND id != ?", (queue_dict["id"],))
            pending_count = cursor.fetchone()[0]
            
            if pending_count > 0:
                print(f"Найдено {pending_count} других pending задач. Задача с капчей перемещается в конец очереди.")
                # Обновляем created_at, чтобы задача встала в конец очереди
                cursor.execute("UPDATE ParseQueue SET status = ?, retry_after = ?, created_at = ? WHERE id = ?", 
                             ("captcha", retry_after.isoformat(), datetime.now().isoformat(), queue_dict["id"]))
            else:
                # Если других задач нет, просто устанавливаем отсрочку
                cursor.execute("UPDATE ParseQueue SET status = ?, retry_after = ? WHERE id = ?", 
                             ("captcha", retry_after.isoformat(), queue_dict["id"]))
            
            conn.commit()
            conn.close()
            return
        
        # Проверяем, есть ли business_id (новая логика для MapParseResults)
        business_id = queue_dict.get("business_id")
        
        if business_id:
            # Новая логика: сохраняем в MapParseResults
            print(f"📊 Сохраняю результаты в MapParseResults для business_id={business_id}")
            
            try:
                from analyzer import analyze_card
                from report import generate_html_report
                
                # Выполняем анализ
                analysis = analyze_card(card_data)
                
                # Генерируем отчёт
                report_path = generate_html_report(card_data, analysis, {})
                
                # Извлекаем данные
                rating = card_data.get('overview', {}).get('rating', '') or ''
                reviews_count = card_data.get('reviews_count') or card_data.get('overview', {}).get('reviews_count') or 0
                news_count = len(card_data.get('news') or [])
                photos_count = card_data.get('photos_count') or 0
                
                # Определяем тип карты
                url_lower = (queue_item["url"] or '').lower()
                map_type = 'yandex' if 'yandex' in url_lower else ('google' if 'google' in url_lower else 'other')
                
                # Сохраняем в MapParseResults
                parse_result_id = str(uuid.uuid4())
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
                # Отправляем email об ошибке
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
            # Старая логика: сохраняем в Cards (для обратной совместимости)
            card_id = str(uuid.uuid4())
            
            # Обрабатываем пустые значения для числовых полей
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
            
            # Вставляем данные в Cards
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
                # Выполняем анализ
                analysis_result = analyze_business_data(card_data)
                
                # Обновляем результат анализа
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
                
                # Генерируем HTML отчёт
                try:
                    from report import generate_html_report
                    
                    # Подготавливаем данные для отчёта
                    analysis_data = {
                        'score': analysis_result.get('score', 50),
                        'recommendations': analysis_result.get('recommendations', []),
                        'ai_analysis': analysis_result.get('analysis', {})
                    }
                    report_path = generate_html_report(card_data, analysis_data)
                    print(f"HTML отчёт сгенерирован: {report_path}")
                    
                    # Сохраняем путь к отчёту
                    cursor.execute("UPDATE Cards SET report_path = ? WHERE id = ?", (report_path, card_id))
                    
                except Exception as report_error:
                    print(f"Ошибка при генерации отчёта для карточки {card_id}: {report_error}")
                    
            except Exception as analysis_error:
                print(f"Ошибка при ИИ-анализе карточки {card_id}: {analysis_error}")
        
        # Обновляем статус на "done" и удаляем заявку из очереди
        cursor.execute("UPDATE ParseQueue SET status = ? WHERE id = ?", ("done", queue_dict["id"]))
        cursor.execute("DELETE FROM ParseQueue WHERE id = ?", (queue_dict["id"],))
        conn.commit()
        conn.close()
        
        print(f"✅ Заявка {queue_dict['id']} обработана и удалена из очереди.")
        
    except Exception as e:
        queue_id = queue_dict.get('id', 'unknown')
        print(f"❌ Ошибка при обработке заявки {queue_id}: {e}")
        import traceback
        traceback.print_exc()
        
        # Обновляем статус заявки при ошибке
        try:
            cursor.execute("UPDATE ParseQueue SET status = ? WHERE id = ?", ("error", queue_id))
            conn.commit()
            print(f"⚠️ Заявка {queue_id} помечена как ошибка.")
            
            # Отправляем email об ошибке
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
            conn.close()

if __name__ == "__main__":
    print("Worker запущен. Проверка очереди каждые 5 минут...")
    while True:
        process_queue()
        time.sleep(300)  # 5 минут = 300 секунд 