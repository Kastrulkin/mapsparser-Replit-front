from database_manager import DatabaseManager
from core.db_helpers import assert_schema_columns


DEFAULT_BUSINESS_TYPES = [
    ("beauty_salon", "Салон красоты", "Салон красоты с полным спектром услуг"),
    ("barbershop", "Барбершоп", "Мужской барбершоп"),
    ("spa", "SPA/Wellness", "SPA и wellness центр"),
    ("nail_studio", "Ногтевая студия", "Студия маникюра и педикюра"),
    ("cosmetology", "Косметология", "Косметологический кабинет"),
    ("massage", "Массаж", "Массажный салон"),
    ("brows_lashes", "Брови и ресницы", "Студия бровей и ресниц"),
    ("makeup", "Макияж", "Студия макияжа"),
    ("tanning", "Солярий", "Студия загара"),
    ("other", "Другое", "Другой тип бизнеса"),
]


def ensure_growth_schema(db: DatabaseManager) -> None:
    cursor = db.conn.cursor()
    assert_schema_columns(
        cursor,
        "businesstypes",
        (
            "id", "type_key", "label", "description", "is_active", "updated_at",
            "alert_threshold_news_days", "alert_threshold_photos_days", "alert_threshold_reviews_days",
        ),
    )
    assert_schema_columns(
        cursor,
        "growthstages",
        ("id", "business_type_id", "stage_number", "title", "tasks", "created_at", "updated_at"),
    )
    assert_schema_columns(
        cursor,
        "growthtasks",
        (
            "id", "stage_id", "task_number", "task_text", "check_logic", "reward_value",
            "reward_type", "tooltip", "link_url", "link_text", "is_auto_verifiable", "updated_at",
        ),
    )
    assert_schema_columns(
        cursor,
        "businessoptimizationwizard",
        ("id", "business_id", "step", "data", "completed", "updated_at"),
    )
