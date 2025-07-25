import time
from supabase import create_client, Client
import os
from dotenv import load_dotenv
load_dotenv()
from parser import parse_yandex_card

url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_KEY')
supabase: Client = create_client(url, key)

def process_queue():
    result = supabase.table("ParseQueue").select("*").execute()
    for row in result.data:
        print("Обрабатываю заявку:", row)
        try:
            card_data = parse_yandex_card(row["url"])
            # Сохраняем результат в Cards (только нужные поля)
            supabase.table("Cards").insert({
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
            supabase.table("ParseQueue").delete().eq("id", row["id"]).execute()
            print(f"Заявка {row['id']} обработана и удалена из очереди.")
        except Exception as e:
            print(f"Ошибка при обработке заявки {row['id']}: {e}")

if __name__ == "__main__":
    print("Worker запущен. Проверка очереди каждую минуту...")
    while True:
        process_queue()
        time.sleep(60) 