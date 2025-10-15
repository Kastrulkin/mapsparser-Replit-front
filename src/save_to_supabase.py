import sqlite3
import json
import uuid


def _get_connection():
    conn = sqlite3.connect("reports.db")
    conn.row_factory = sqlite3.Row
    return conn


def check_competitor_exists(competitor_url):
    """Проверяет, существует ли конкурент в локальной SQLite базе данных"""
    try:
        if not competitor_url:
            return False
        conn = _get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM Cards WHERE url = ? LIMIT 1", (competitor_url,))
        row = cur.fetchone()
        conn.close()
        return row is not None
    except Exception as e:
        print(f"Ошибка при проверке конкурента в SQLite: {e}")
        return False


def get_next_available_competitor(competitors):
    """Возвращает первого конкурента, которого нет в базе данных"""
    for competitor in competitors:
        if not check_competitor_exists(competitor.get('url', '')):
            return competitor
    return None


def _extract_overview(overview):
    if isinstance(overview, dict):
        return {
            "title": overview.get("title"),
            "address": overview.get("address"),
            "phone": overview.get("phone"),
            "site": overview.get("site"),
            "rating": overview.get("rating"),
            "reviews_count": overview.get("reviews_count"),
            "hours": overview.get("hours"),
            "hours_full": overview.get("hours_full"),
            "description": overview.get("description"),
        }
    return {}


def _json_or_none(value):
    try:
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return None


def save_card_to_supabase(card_data):
    """Сохраняет карточку в SQLite (замена Supabase). Возвращает id."""
    try:
        overview = _extract_overview(card_data.get("overview"))
        card_id = str(uuid.uuid4())

        # Поля по схеме Cards
        payload = {
            "id": card_id,
            "url": card_data.get("url"),
            "title": overview.get("title") or card_data.get("title"),
            "address": overview.get("address") or card_data.get("address"),
            "phone": overview.get("phone") or card_data.get("phone"),
            "site": overview.get("site") or card_data.get("site"),
            "rating": float(overview.get("rating") or 0) if overview.get("rating") not in (None, "") else None,
            "reviews_count": int(overview.get("reviews_count") or 0) if overview.get("reviews_count") not in (None, "") else None,
            "categories": _json_or_none(card_data.get("product_categories") or card_data.get("categories")),
            "overview": _json_or_none(card_data.get("overview")),
            "products": _json_or_none(card_data.get("products")),
            "news": _json_or_none(card_data.get("news")),
            "photos": _json_or_none(card_data.get("photos")),
            "features_full": _json_or_none(card_data.get("features_full")),
            "competitors": _json_or_none(card_data.get("competitors") or []),
            "hours": overview.get("hours"),
            "hours_full": _json_or_none(overview.get("hours_full")),
            "report_path": card_data.get("report_path"),
            "user_id": None,
            "seo_score": card_data.get("seo_score"),
            "ai_analysis": _json_or_none(card_data.get("ai_analysis")),
            "recommendations": _json_or_none(card_data.get("recommendations")),
        }

        fields = ", ".join(payload.keys())
        placeholders = ", ".join(["?" for _ in payload])
        values = list(payload.values())

        conn = _get_connection()
        cur = conn.cursor()
        cur.execute(f"INSERT INTO Cards ({fields}) VALUES ({placeholders})", values)
        conn.commit()
        conn.close()

        print(f"Карточка сохранена в SQLite с ID: {card_id}")
        return card_id
    except Exception as e:
        print(f"Ошибка при сохранении в SQLite: {type(e).__name__}: {str(e)}")
        return None


def save_competitor_to_supabase(competitor_data, main_card_id, main_card_url):
    """Сохраняет данные конкурента в SQLite. Возвращает id."""
    try:
        competitor_data = dict(competitor_data or {})
        competitor_data['competitors'] = []
        return save_card_to_supabase(competitor_data)
    except Exception as e:
        print(f"Ошибка при сохранении конкурента в SQLite: {e}")
        return None