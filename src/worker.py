import time
from supabase import create_client, Client
import os
from dotenv import load_dotenv

# Загружаем .env файл
load_dotenv()

# Читаем переменные окружения
url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_KEY')

print(f"DEBUG: URL из переменных окружения: {url}")
print(f"DEBUG: KEY из переменных окружения: {key[:20] if key else 'None'}...")

# Проверяем, что переменные загружены
if not url or not key:
    print("ERROR: SUPABASE_URL или SUPABASE_KEY не найдены!")
    print(f"DEBUG: URL = {url}")
    print(f"DEBUG: KEY = {key[:20] if key else 'None'}...")
    raise Exception("SUPABASE_URL и SUPABASE_KEY должны быть установлены")

print(f"Supabase URL: {url[:30]}...")
print(f"Supabase Key: {key[:20]}...")

# Проверяем формат URL
if not url.startswith('https://'):
    print(f"ERROR: Неверный формат URL: {url}")
    raise Exception("SUPABASE_URL должен начинаться с https://")

supabase: Client = create_client(url, key)

from parser import parse_yandex_card
from simple_ai_analyzer import analyze_business_data

def process_queue():
    result = supabase.table("ParseQueue").select("*").execute()
    for row in result.data:
        print("Обрабатываю заявку:", row)
        try:
            card_data = parse_yandex_card(row["url"])
            if card_data.get("error") == "captcha_detected":
                print(f"Обнаружена капча для заявки {row['id']}! Помечаю как требующую ручной обработки...")
                
                # Обновляем статус заявки в ParseQueue
                supabase.table("ParseQueue").update({
                    "status": "captcha_required"
                }).eq("id", row["id"]).execute()
                
                print(f"Заявка {row['id']} помечена как требующая ручной обработки капчи.")
                continue  # Переходим к следующей заявке
            # Сохраняем результат в Cards (только нужные поля)
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
            
            card_insert_result = supabase.table("Cards").insert({
                "user_id": row["user_id"],
                "url": row["url"],
                "title": card_data.get("title"),
                "address": card_data.get("address"),
                "phone": card_data.get("phone"),
                "site": card_data.get("site"),
                "rating": rating,
                "reviews_count": reviews_count,
                "categories": card_data.get("categories"),
                "overview": card_data.get("overview"),
                "products": card_data.get("products"),
                "news": card_data.get("news"),
                "photos": card_data.get("photos"),
                "features_full": card_data.get("features_full"),
                "competitors": card_data.get("competitors"),
                "hours": card_data.get("hours"),
                "hours_full": card_data.get("hours_full"),
            }).execute()
            
            # Выполняем ИИ-анализ данных
            if card_insert_result.data:
                card_id = card_insert_result.data[0]['id']
                print(f"Выполняем ИИ-анализ для карточки {card_id}...")
                
                try:
                    # Получаем полные данные карточки
                    card_full_data = supabase.table("Cards").select("*").eq("id", card_id).execute()
                    
                    if card_full_data.data:
                        # Выполняем анализ
                        analysis_result = analyze_business_data(card_full_data.data[0])
                        
                        # Сохраняем результат анализа
                        supabase.table("Cards").update({
                            "ai_analysis": analysis_result['analysis'],
                            "seo_score": analysis_result['score'],
                            "recommendations": analysis_result['recommendations']
                        }).eq("id", card_id).execute()
                        
                        print(f"ИИ-анализ завершён для карточки {card_id}")
                        
                        # Генерируем HTML отчёт
                        try:
                            from report import generate_html_report
                            
                            # Получаем обновлённые данные карточки
                            updated_card = supabase.table("Cards").select("*").eq("id", card_id).execute()
                            
                            if updated_card.data:
                                # Подготавливаем данные для отчёта
                                card_data = updated_card.data[0]
                                analysis_data = {
                                    'score': card_data.get('seo_score', 50),
                                    'recommendations': card_data.get('recommendations', []),
                                    'ai_analysis': card_data.get('ai_analysis', {})
                                }
                                report_path = generate_html_report(card_data, analysis_data)
                                print(f"HTML отчёт сгенерирован: {report_path}")
                                
                                # Сохраняем путь к отчёту в базу данных
                                supabase.table("Cards").update({
                                    "report_path": report_path
                                }).eq("id", card_id).execute()
                            else:
                                print(f"Не удалось получить данные карточки {card_id} для генерации отчёта")
                                
                        except Exception as report_error:
                            print(f"Ошибка при генерации отчёта для карточки {card_id}: {report_error}")
                    else:
                        print(f"Не удалось получить данные карточки {card_id} для анализа")
                        
                except Exception as analysis_error:
                    print(f"Ошибка при ИИ-анализе карточки {card_id}: {analysis_error}")
            supabase.table("ParseQueue").delete().eq("id", row["id"]).execute()
            print(f"Заявка {row['id']} обработана и удалена из очереди.")
        except Exception as e:
            print(f"Ошибка при обработке заявки {row['id']}: {e}")
            
            # Обновляем статус заявки в ParseQueue при ошибке
            try:
                supabase.table("ParseQueue").update({
                    "status": "error"
                }).eq("id", row["id"]).execute()
                print(f"Заявка {row['id']} помечена как ошибка.")
            except Exception as update_error:
                print(f"Не удалось обновить статус заявки {row['id']}: {update_error}")

if __name__ == "__main__":
    print("Worker запущен. Проверка очереди каждые 5 минут...")
    while True:
        process_queue()
        time.sleep(300)  # 5 минут = 300 секунд 