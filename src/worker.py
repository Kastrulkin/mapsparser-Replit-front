import time
from supabase import create_client, Client
import os
from dotenv import load_dotenv
load_dotenv()
from parser import parse_yandex_card
from ai_analyzer import analyze_business_data

url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_KEY')
supabase: Client = create_client(url, key)

def process_queue():
    result = supabase.table("ParseQueue").select("*").execute()
    for row in result.data:
        print("Обрабатываю заявку:", row)
        try:
            card_data = parse_yandex_card(row["url"])
            if card_data.get("error") == "captcha_detected":
                print("Обнаружена капча! Останавливаю парсинг на 5 минут...")
                time.sleep(300)
                return  # Прерываем обработку очереди, чтобы не парсить другие заявки
            # Сохраняем результат в Cards (только нужные поля)
            card_insert_result = supabase.table("Cards").insert({
                "user_id": row["user_id"],
                "url": row["url"],
                "title": card_data.get("title"),
                "address": card_data.get("address"),
                "phone": card_data.get("phone"),
                "site": card_data.get("site"),
                "rating": card_data.get("rating"),
                "reviews_count": card_data.get("reviews_count"),
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
                                report_path = generate_html_report(updated_card.data[0])
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

if __name__ == "__main__":
    print("Worker запущен. Проверка очереди каждую минуту...")
    while True:
        process_queue()
        time.sleep(60) 