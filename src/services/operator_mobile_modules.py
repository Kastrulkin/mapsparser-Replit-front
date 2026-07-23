from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _row(cursor: Any, value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "keys"):
        return dict(value)
    columns = [item[0] for item in (getattr(cursor, "description", None) or [])]
    return {columns[index]: value[index] for index in range(min(len(columns), len(value)))}


def _table_exists(cursor: Any, table_name: str) -> bool:
    cursor.execute("SELECT to_regclass(%s) AS table_ref", (f"public.{table_name}",))
    return bool(_row(cursor, cursor.fetchone()).get("table_ref"))


def _business_filter(scope: dict[str, Any]) -> tuple[bool, list[str]]:
    return scope.get("kind") == "platform", [str(item) for item in scope.get("business_ids") or []]


def _cards(cursor: Any, scope: dict[str, Any]) -> list[dict[str, Any]]:
    if not _table_exists(cursor, "cards"):
        return []
    platform, business_ids = _business_filter(scope)
    cursor.execute(
        """
        SELECT DISTINCT ON (c.business_id) c.id, c.business_id, b.name AS business_name,
               COALESCE(c.title, b.name) AS title, COALESCE(c.address, b.address) AS subtitle,
               c.rating, c.reviews_count, c.seo_score, c.updated_at
        FROM cards c JOIN businesses b ON b.id = c.business_id
        WHERE (%s OR c.business_id = ANY(%s))
        ORDER BY c.business_id, c.is_latest DESC NULLS LAST, c.updated_at DESC
        LIMIT 200
        """,
        (platform, business_ids),
    )
    return [{**_row(cursor, item), "kind": "card", "status": "fresh"} for item in cursor.fetchall() or []]


def _content(cursor: Any, scope: dict[str, Any]) -> list[dict[str, Any]]:
    if not _table_exists(cursor, "usernews"):
        return []
    platform, business_ids = _business_filter(scope)
    cursor.execute(
        """
        SELECT n.id, n.business_id, b.name AS business_name,
               COALESCE(NULLIF(TRIM(n.source_text), ''), 'Черновик публикации') AS title,
               n.generated_text AS subtitle,
               CASE WHEN COALESCE(n.approved, 0) = 1 THEN 'approved' ELSE 'draft' END AS status,
               n.created_at AS updated_at
        FROM usernews n LEFT JOIN businesses b ON b.id = n.business_id
        WHERE (%s OR n.business_id = ANY(%s))
        ORDER BY n.created_at DESC LIMIT 100
        """,
        (platform, business_ids),
    )
    return [{**_row(cursor, item), "kind": "content"} for item in cursor.fetchall() or []]


def _services(cursor: Any, scope: dict[str, Any]) -> list[dict[str, Any]]:
    if not _table_exists(cursor, "userservices"):
        return []
    platform, business_ids = _business_filter(scope)
    cursor.execute(
        """
        SELECT s.id, s.business_id, b.name AS business_name, s.name AS title,
               COALESCE(NULLIF(TRIM(s.description), ''), s.category, 'Без описания') AS subtitle,
               s.price, s.category, CASE WHEN COALESCE(s.is_active, TRUE) THEN 'active' ELSE 'archived' END AS status,
               s.updated_at
        FROM userservices s JOIN businesses b ON b.id = s.business_id
        WHERE (%s OR s.business_id = ANY(%s))
        ORDER BY COALESCE(s.is_active, TRUE) DESC, s.updated_at DESC LIMIT 200
        """,
        (platform, business_ids),
    )
    return [{**_row(cursor, item), "kind": "service"} for item in cursor.fetchall() or []]


LOADERS = {"cards": _cards, "content": _content, "services": _services}


def list_operator_mobile_module(cursor: Any, *, module: str, scope: dict[str, Any]) -> dict[str, Any]:
    loader = LOADERS.get(module)
    if not loader:
        return {"status": "hidden", "items": []}
    items = loader(cursor, scope)
    return {
        "status": "read_only",
        "scope": scope,
        "items": items,
        "counts": {"total": len(items)},
        "cursor": None,
        "as_of": datetime.now(timezone.utc).isoformat(),
        "freshness": {"status": "live"},
        "data_warnings": [],
        "available_actions": [],
        "filters": {},
    }
