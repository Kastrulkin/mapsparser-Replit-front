from __future__ import annotations

import json
from typing import Any

from core.industry_patterns import detect_industry_key, normalize_pattern_text


DEFAULT_SOURCE_ROLES = {"community", "expert", "vendor", "salon", "unknown"}
INDUSTRY_LABELS = {
    "beauty": "Бьюти-индустрия",
}
BEAUTY_SOURCE_MARKERS = (
    "beauty", "бьюти", "салон", "парикмах", "колорист", "маник", "педик",
    "космет", "бров", "ресниц", "барбер", "нейл", "nail", "spa", "спа",
)


def _row(cursor: Any, value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "keys"):
        try:
            return dict(value)
        except Exception:
            return {}
    columns = [item[0] for item in (getattr(cursor, "description", None) or [])]
    if isinstance(value, (list, tuple)):
        return {columns[index]: value[index] for index in range(min(len(columns), len(value)))}
    return {}


def _metadata(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def source_industry_key(source: dict[str, Any]) -> str:
    metadata = _metadata(source.get("metadata_json"))
    explicit = str(metadata.get("industry_key") or "").strip().lower()
    if explicit:
        return explicit
    detected = detect_industry_key(
        business_name=source.get("title"),
        business_type=source.get("source_role"),
    )
    if detected != "local_business":
        return detected
    title = normalize_pattern_text(source.get("title"))
    if any(marker in title for marker in BEAUTY_SOURCE_MARKERS):
        return "beauty"
    return "local_business"


def is_default_industry_source(source: dict[str, Any], industry_keys: set[str]) -> bool:
    if not industry_keys:
        return False
    metadata = _metadata(source.get("metadata_json"))
    if metadata.get("community_default") is False:
        return False
    if metadata.get("submitted_by_business_id") and metadata.get("community_default") is not True:
        return False
    role = str(source.get("source_role") or "unknown").strip().lower()
    if role not in DEFAULT_SOURCE_ROLES and metadata.get("community_default") is not True:
        return False
    return source_industry_key(source) in industry_keys


def load_business_industry_keys(cursor: Any, business_ids: list[str]) -> set[str]:
    clean_ids = [str(item) for item in business_ids if str(item)]
    if not clean_ids:
        return set()
    cursor.execute(
        """
        SELECT name, business_type, industry, categories
        FROM businesses
        WHERE id = ANY(%s)
        """,
        (clean_ids,),
    )
    keys = set()
    for value in cursor.fetchall() or []:
        item = _row(cursor, value)
        key = detect_industry_key(
            business_name=item.get("name"),
            business_type=item.get("business_type"),
            industry=item.get("industry"),
            categories=item.get("categories"),
        )
        if key != "local_business":
            keys.add(key)
    return keys


def load_default_industry_sources(
    cursor: Any,
    industry_keys: set[str],
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    if not industry_keys:
        return []
    cursor.execute(
        """
        SELECT id, title, canonical_url, source_role, metadata_json,
               last_collected_at, next_sync_at, sync_status
        FROM knowledge_sources
        WHERE source_type = 'telegram'
          AND visibility = 'public'
          AND status = 'active'
        ORDER BY last_collected_at DESC NULLS LAST, title
        """
    )
    matched = []
    for value in cursor.fetchall() or []:
        item = _row(cursor, value)
        if not is_default_industry_source(item, industry_keys):
            continue
        item["industry_key"] = source_industry_key(item)
        item["is_industry_default"] = True
        matched.append(item)
        if limit is not None and len(matched) >= limit:
            break
    return matched


def industry_label(industry_keys: set[str]) -> str:
    if len(industry_keys) == 1:
        key = next(iter(industry_keys))
        return INDUSTRY_LABELS.get(key, "Отраслевые источники")
    return "Отраслевые источники"
