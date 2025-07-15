from supabase import create_client, Client
import os

SUPABASE_URL = "https://bvhpvzcvcuswiozhyqlk.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJ2aHB2emN2Y3Vzd2lvemh5cWxrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTI0OTk4NTksImV4cCI6MjA2ODA3NTg1OX0.WN6Yig4ruyDmSDwX12vlZlzRaCOsekXC_WNdtwpeXqE"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

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
    }
    supabase.table("Cards").insert(data).execute() 