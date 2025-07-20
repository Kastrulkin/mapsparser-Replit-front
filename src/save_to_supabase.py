from supabase import create_client, Client
import os

SUPABASE_URL = "https://bvhpvzcvcuswiozhyqlk.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJ2aHB2emN2Y3Vzd2lvemh5cWxrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTI0OTk4NTksImV4cCI6MjA2ODA3NTg1OX0.WN6Yig4ruyDmSDwX12vlZlzRaCOsekXC_WNdtwpeXqE"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def check_competitor_exists(competitor_url):
    """Проверяет, существует ли конкурент в базе данных"""
    try:
        result = supabase.table("Cards").select("id").eq("url", competitor_url).execute()
        return len(result.data) > 0
    except Exception as e:
        print(f"Ошибка при проверке конкурента: {e}")
        return False

def get_next_available_competitor(competitors):
    """Возвращает первого конкурента, которого нет в базе данных"""
    for competitor in competitors:
        if not check_competitor_exists(competitor.get('url', '')):
            return competitor
    return None

def save_card_to_supabase(card_data):
    data = {
        "url": card_data.get("url"),
        "title": card_data.get("overview", {}).get("title"),
        "address": card_data.get("overview", {}).get("address"),
        "phone": card_data.get("overview", {}).get("phone"),
        "site": card_data.get("overview", {}).get("site"),
        "rating": float(card_data.get("overview", {}).get("rating") or 0),
        "ratings_count": int(card_data.get("overview", {}).get("ratings_count") or 0),
        "reviews_count": int(card_data.get("overview", {}).get("reviews_count") or 0),
        # Сохраняем product_categories в поле categories
        "categories": card_data.get("product_categories"),
        "categories_full": card_data.get("categories_full"),
        "features_bool": card_data.get("features_bool"),
        "features_valued": card_data.get("features_valued"),
        "features_prices": card_data.get("features_prices"),
        "features_full": card_data.get("features_full"),  # Новое поле для Supabase
        "overview": card_data.get("overview"),
        "products": card_data.get("products"),
        "news": card_data.get("news"),
        "photos": card_data.get("photos"),
        "reviews": card_data.get("reviews"),
        "hours": card_data.get("overview", {}).get("hours"),
        "hours_full": card_data.get("overview", {}).get("hours_full"),
        "competitors": card_data.get("competitors", []),
        "main_card_url": None,  # Для основных карточек это поле пустое
    }
    
    result = supabase.table("Cards").insert(data).execute()
    return result.data[0]['id'] if result.data else None

def save_competitor_to_supabase(competitor_data, main_card_id, main_card_url):
    """Сохраняет данные конкурента с привязкой к основной карточке"""
    data = {
        "url": competitor_data.get("url"),
        "title": competitor_data.get("overview", {}).get("title"),
        "address": competitor_data.get("overview", {}).get("address"),
        "phone": competitor_data.get("overview", {}).get("phone"),
        "site": competitor_data.get("overview", {}).get("site"),
        "rating": float(competitor_data.get("overview", {}).get("rating") or 0),
        "ratings_count": int(competitor_data.get("overview", {}).get("ratings_count") or 0),
        "reviews_count": int(competitor_data.get("overview", {}).get("reviews_count") or 0),
        "categories": competitor_data.get("product_categories"),
        "categories_full": competitor_data.get("categories_full"),
        "features_bool": competitor_data.get("features_bool"),
        "features_valued": competitor_data.get("features_valued"),
        "features_prices": competitor_data.get("features_prices"),
        "features_full": competitor_data.get("features_full"),
        "overview": competitor_data.get("overview"),
        "products": competitor_data.get("products"),
        "news": competitor_data.get("news"),
        "photos": competitor_data.get("photos"),
        "reviews": competitor_data.get("reviews"),
        "hours": competitor_data.get("overview", {}).get("hours"),
        "hours_full": competitor_data.get("overview", {}).get("hours_full"),
        "competitors": [],
        "main_card_url": main_card_url,  # Привязка к основной карточке
    }
    
    result = supabase.table("Cards").insert(data).execute()
    return result.data[0]['id'] if result.data else None 