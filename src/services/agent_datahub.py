from __future__ import annotations

from typing import Any, Dict, List


AGENT_DATAHUB_SOURCES = [
    {
        "key": "business_profile",
        "title": "Профиль бизнеса",
        "description": "Название, тип, город и адрес бизнеса.",
        "query": "SELECT id, name, business_type, city, address FROM businesses WHERE id = %s",
    },
    {
        "key": "services",
        "title": "Услуги",
        "description": "Текущий список услуг, цены и длительность.",
        "query": "SELECT id, name, price, description FROM userservices WHERE business_id = %s ORDER BY name ASC LIMIT 20",
    },
    {
        "key": "reviews",
        "title": "Отзывы",
        "description": "Последние отзывы из подключённых внешних карточек.",
        "query": "SELECT id, author_name, rating, text FROM externalbusinessreviews WHERE business_id = %s ORDER BY created_at DESC LIMIT 20",
    },
    {
        "key": "prospectingleads",
        "title": "Лиды",
        "description": "Лиды из текущего outreach/prospecting pipeline.",
        "query": "SELECT id, name, city, category, status FROM prospectingleads WHERE business_id = %s ORDER BY updated_at DESC NULLS LAST LIMIT 20",
    },
    {
        "key": "outreach_drafts",
        "title": "Черновики outreach",
        "description": "Подготовленные черновики сообщений по лидам.",
        "query": "SELECT d.id, d.channel, d.status, d.generated_text FROM outreachmessagedrafts d JOIN prospectingleads l ON l.id = d.lead_id WHERE l.business_id = %s ORDER BY d.updated_at DESC LIMIT 20",
    },
]


def build_agent_datahub_catalog(cursor: Any, business_id: str, connected_sources: List[Dict[str, Any]] | None = None) -> List[Dict[str, Any]]:
    connected_keys = {
        _clean_text(item.get("internal_source"))
        for item in (connected_sources or [])
        if isinstance(item, dict) and _clean_text(item.get("source_type")) == "internal"
    }
    catalog = []
    for definition in AGENT_DATAHUB_SOURCES:
        key = _clean_text(definition.get("key"))
        rows = _safe_catalog_rows(cursor, _clean_text(definition.get("query")), (business_id,))
        catalog.append(
            {
                "key": key,
                "title": _clean_text(definition.get("title")),
                "description": _clean_text(definition.get("description")),
                "available_count": len(rows),
                "connected": key in connected_keys,
                "preview": [_row_summary(row) for row in rows[:3]],
                "state": "available" if rows else "empty",
            }
        )
    return catalog


def _safe_catalog_rows(cursor: Any, query: str, params: tuple[Any, ...]) -> List[Dict[str, Any]]:
    if not query:
        return []
    try:
        cursor.execute(query, params)
        return [dict(row) for row in (cursor.fetchall() or [])]
    except Exception:
        return []


def _row_summary(row: Dict[str, Any]) -> str:
    preferred_keys = ("name", "title", "author_name", "rating", "city", "category", "status", "generated_text", "text")
    parts = []
    for key in preferred_keys:
        value = _clean_text(row.get(key))
        if value:
            parts.append(value[:120])
        if len(parts) >= 3:
            break
    if not parts:
        for key, value in row.items():
            text = _clean_text(value)
            if text:
                parts.append(f"{key}: {text[:80]}")
            if len(parts) >= 3:
                break
    return " · ".join(parts)


def _clean_text(value: Any) -> str:
    return str(value or "").strip()
