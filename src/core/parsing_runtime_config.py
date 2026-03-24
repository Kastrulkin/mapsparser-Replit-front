import os
from typing import Optional


RUNTIME_SETTING_KEY_USE_APIFY_MAP_PARSING = "use_apify_map_parsing"


def _env_default_use_apify() -> bool:
    raw = str(os.getenv("PARSING_USE_APIFY_DEFAULT", "0")).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _ensure_runtime_settings_table(conn) -> None:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS parsingruntimeconfig (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
    finally:
        cur.close()


def get_use_apify_map_parsing(conn) -> bool:
    _ensure_runtime_settings_table(conn)
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT value
            FROM parsingruntimeconfig
            WHERE key = %s
            LIMIT 1
            """,
            (RUNTIME_SETTING_KEY_USE_APIFY_MAP_PARSING,),
        )
        row = cur.fetchone()
        if not row:
            return _env_default_use_apify()
        value = ""
        if isinstance(row, dict):
            value = str(row.get("value") or "").strip().lower()
        else:
            value = str(row[0] or "").strip().lower()
        return value in {"1", "true", "yes", "on", "apify"}
    finally:
        cur.close()


def set_use_apify_map_parsing(conn, enabled: bool) -> bool:
    _ensure_runtime_settings_table(conn)
    serialized_value = "1" if enabled else "0"
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO parsingruntimeconfig (key, value, updated_at)
            VALUES (%s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (key) DO UPDATE
            SET value = EXCLUDED.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (RUNTIME_SETTING_KEY_USE_APIFY_MAP_PARSING, serialized_value),
        )
        conn.commit()
        return enabled
    finally:
        cur.close()


def resolve_map_source_for_queue(source: str, use_apify_map_parsing: bool) -> str:
    normalized_source = str(source or "").strip().lower()
    if normalized_source in {"google", "google_maps", "google_business", "apify_google"}:
        return "apify_google"
    if normalized_source in {"apple", "apple_maps", "apify_apple"}:
        return "apify_apple"
    if not use_apify_map_parsing:
        return normalized_source or source
    if normalized_source == "yandex_maps":
        return "apify_yandex"
    if normalized_source in {"2gis", "two_gis"}:
        return "apify_2gis"
    return normalized_source or source
