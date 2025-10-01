import time
import sqlite3
import os
import uuid
from datetime import datetime

def get_db_connection():
    """Получить соединение с SQLite базой данных"""
    conn = sqlite3.connect("reports.db")
    conn.row_factory = sqlite3.Row
    return conn

from parser import parse_yandex_card
from gigachat_analyzer import analyze_business_data

def process_queue():
    """Обрабатывает очередь парсинга из SQLite базы данных"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Получаем заявки из очереди
    cursor.execute("SELECT * FROM ParseQueue WHERE status = 'pending' ORDER BY created_at ASC LIMIT 1")
    queue_item = cursor.fetchone()
    
    if not queue_item:
        conn.close()
        return
    
    print("Обрабатываю заявку:", dict(queue_item))
    
    try:
        # Парсим данные с Яндекс.Карт
        card_data = parse_yandex_card(queue_item["url"])
        
        if card_data.get("error") == "captcha_detected":
            print(f"Обнаружена капча для заявки {queue_item['id']}! Помечаю как требующую ручной обработки...")
            
            # Обновляем статус заявки
            cursor.execute("UPDATE ParseQueue SET status = ? WHERE id = ?", ("captcha_required", queue_item["id"]))
            conn.commit()
            conn.close()
            return
        
        # Создаем новую запись в Cards
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
            queue_item["user_id"],
            queue_item["url"],
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
        
        # Удаляем заявку из очереди
        cursor.execute("DELETE FROM ParseQueue WHERE id = ?", (queue_item["id"],))
        conn.commit()
        conn.close()
        
        print(f"Заявка {queue_item['id']} обработана и удалена из очереди.")
        
    except Exception as e:
        print(f"Ошибка при обработке заявки {queue_item['id']}: {e}")
        
        # Обновляем статус заявки при ошибке
        try:
            cursor.execute("UPDATE ParseQueue SET status = ? WHERE id = ?", ("error", queue_item["id"]))
            conn.commit()
            print(f"Заявка {queue_item['id']} помечена как ошибка.")
        except Exception as update_error:
            print(f"Не удалось обновить статус заявки {queue_item['id']}: {update_error}")
        finally:
            conn.close()

if __name__ == "__main__":
    print("Worker запущен. Проверка очереди каждые 5 минут...")
    while True:
        process_queue()
        time.sleep(300)  # 5 минут = 300 секунд 