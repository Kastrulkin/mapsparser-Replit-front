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


def _finance(cursor: Any, scope: dict[str, Any]) -> list[dict[str, Any]]:
    if not _table_exists(cursor, "financialtransactions"):
        return []
    platform, business_ids = _business_filter(scope)
    cursor.execute(
        """
        SELECT t.id, t.business_id, b.name AS business_name,
               CASE WHEN t.transaction_type = 'income' THEN 'Поступление' ELSE 'Расход' END AS title,
               COALESCE(NULLIF(TRIM(t.description), ''), 'Без комментария') AS subtitle,
               t.amount, t.transaction_type, t.transaction_date, t.created_at AS updated_at,
               CASE WHEN t.transaction_type = 'income' THEN 'completed' ELSE 'attention' END AS status
        FROM financialtransactions t JOIN businesses b ON b.id = t.business_id
        WHERE (%s OR t.business_id = ANY(%s))
        ORDER BY COALESCE(t.transaction_date, t.created_at::date) DESC, t.created_at DESC LIMIT 200
        """,
        (platform, business_ids),
    )
    return [{**_row(cursor, item), "kind": "finance_transaction"} for item in cursor.fetchall() or []]


def _partnerships(cursor: Any, scope: dict[str, Any]) -> list[dict[str, Any]]:
    if not _table_exists(cursor, "prospectingleads"):
        return []
    platform, business_ids = _business_filter(scope)
    cursor.execute(
        """
        SELECT l.id, l.business_id, b.name AS business_name, l.name AS title,
               COALESCE(NULLIF(TRIM(l.address), ''), NULLIF(TRIM(l.city), ''), 'Адрес не указан') AS subtitle,
               l.status, l.selected_channel, l.rating, l.reviews_count, l.updated_at
        FROM prospectingleads l LEFT JOIN businesses b ON b.id = l.business_id
        WHERE (%s OR l.business_id = ANY(%s))
        ORDER BY l.updated_at DESC LIMIT 200
        """,
        (platform, business_ids),
    )
    return [{**_row(cursor, item), "kind": "partnership_lead"} for item in cursor.fetchall() or []]


def _agents(cursor: Any, scope: dict[str, Any]) -> list[dict[str, Any]]:
    if not _table_exists(cursor, "agent_blueprints"):
        return []
    platform, business_ids = _business_filter(scope)
    cursor.execute(
        """
        SELECT bp.id, bp.business_id, b.name AS business_name, bp.name AS title,
               COALESCE(NULLIF(TRIM(bp.description), ''), bp.category) AS subtitle,
               bp.category, bp.status, bp.updated_at,
               run.id AS run_id, run.status AS run_status, run.started_at, run.completed_at, run.error_text
        FROM agent_blueprints bp JOIN businesses b ON b.id = bp.business_id
        LEFT JOIN LATERAL (
            SELECT id, status, started_at, completed_at, error_text
            FROM agent_runs WHERE blueprint_id = bp.id ORDER BY started_at DESC LIMIT 1
        ) run ON TRUE
        WHERE (%s OR bp.business_id = ANY(%s))
        ORDER BY bp.updated_at DESC LIMIT 200
        """,
        (platform, business_ids),
    )
    items = []
    for value in cursor.fetchall() or []:
        item = _row(cursor, value)
        items.append({**item, "kind": "agent", "status": item.get("run_status") or item.get("status")})
    return items


def _diagnostics(cursor: Any, scope: dict[str, Any]) -> list[dict[str, Any]]:
    if scope.get("kind") != "platform" or not _table_exists(cursor, "parsequeue"):
        return []
    cursor.execute(
        """
        SELECT q.id, q.business_id, b.name AS business_name,
               COALESCE(q.task_type, 'Задача интеграции') AS title,
               COALESCE(NULLIF(TRIM(q.error_message), ''), q.source, q.url, 'Требует проверки') AS subtitle,
               q.status, q.source, q.updated_at
        FROM parsequeue q LEFT JOIN businesses b ON b.id = q.business_id
        WHERE q.status IN ('error', 'failed', 'stuck', 'captcha_required') OR COALESCE(q.captcha_required, 0) = 1
        ORDER BY q.updated_at DESC LIMIT 200
        """
    )
    return [{**_row(cursor, item), "kind": "diagnostic_job"} for item in cursor.fetchall() or []]


LOADERS = {
    "cards": _cards,
    "content": _content,
    "services": _services,
    "finance": _finance,
    "partnerships": _partnerships,
    "agents": _agents,
    "diagnostics": _diagnostics,
}


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
