from supabase import create_client, Client
import os

# Удаляю захардкоженные ключи SUPABASE_URL и SUPABASE_KEY, убираю глобальный supabase

def check_competitor_exists(competitor_url):
    """Проверяет, существует ли конкурент в базе данных"""
    try:
        from supabase import create_client, Client
        import os
        url = os.getenv('SUPABASE_URL')
        key = os.getenv('SUPABASE_KEY')
        if not url or not key:
            print("Предупреждение: переменные окружения SUPABASE_URL или SUPABASE_KEY не установлены")
            return False
        supabase: Client = create_client(url, key)
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
    try:
        from supabase import create_client, Client
        import os
        url = os.getenv('SUPABASE_URL')
        key = os.getenv('SUPABASE_KEY')
        if not url or not key:
            print("Предупреждение: Переменные окружения SUPABASE_URL или SUPABASE_KEY не установлены")
            print("Данные не будут сохранены в базу данных")
            return None
        supabase: Client = create_client(url, key)
        data = {
            "url": card_data.get("url"),
            "title": card_data.get("overview", {}).get("title"),
            "address": card_data.get("overview", {}).get("address"),
            "phone": card_data.get("overview", {}).get("phone"),
            "site": card_data.get("overview", {}).get("site"),
            "rating": float(card_data.get("overview", {}).get("rating") or 0),
            "ratings_count": int(card_data.get("overview", {}).get("ratings_count") or 0),
            "reviews_count": int(card_data.get("overview", {}).get("reviews_count") or 0),
            "rubric": card_data.get("rubric"),
            "categories": card_data.get("product_categories"),
            "categories_full": card_data.get("categories_full"),
            "features_bool": card_data.get("features_bool"),
            "features_valued": card_data.get("features_valued"),
            "features_prices": card_data.get("features_prices"),
            "features_full": card_data.get("features_full"),
            "overview": card_data.get("overview"),
            "products": card_data.get("products"),
            "news": card_data.get("news"),
            "photos": card_data.get("photos"),
            "reviews": card_data.get("reviews"),
            "hours": card_data.get("overview", {}).get("hours"),
            "hours_full": card_data.get("overview", {}).get("hours_full"),
            "competitors": card_data.get("competitors", []),
            "main_card_url": None,
        }
        result = supabase.table("Cards").insert(data).execute()
        print(f"Карточка сохранена с ID: {result.data[0]['id']}")
        return result.data[0]['id']
    except Exception as e:
        print(f"Ошибка при сохранении в Supabase: {type(e).__name__}: {str(e)}")
        return None

def save_competitor_to_supabase(competitor_data, main_card_id, main_card_url):
    """Сохраняет данные конкурента с привязкой к основной карточке"""
    from supabase import create_client, Client
    import os
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_KEY')
    if not url or not key:
        print("Предупреждение: переменные окружения SUPABASE_URL или SUPABASE_KEY не установлены")
        return None
    supabase: Client = create_client(url, key)
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