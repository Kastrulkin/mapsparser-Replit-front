from __future__ import annotations

from datetime import datetime, timezone
import os
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
    if not _table_exists(cursor, "businesses"):
        return []
    platform, business_ids = _business_filter(scope)
    has_schedule = _table_exists(cursor, "businesscardautomationsettings")
    schedule_select = """
               automation.review_sync_enabled, automation.review_sync_interval_hours,
               automation.review_sync_schedule_mode, automation.review_sync_schedule_days,
               automation.review_sync_schedule_time, automation.review_sync_next_run_at,
               automation.review_sync_last_run_at, automation.review_sync_last_status,
    """ if has_schedule else """
               FALSE AS review_sync_enabled, 24 AS review_sync_interval_hours,
               'interval' AS review_sync_schedule_mode, NULL AS review_sync_schedule_days,
               NULL AS review_sync_schedule_time, NULL AS review_sync_next_run_at,
               NULL AS review_sync_last_run_at, NULL AS review_sync_last_status,
    """
    schedule_join = "LEFT JOIN businesscardautomationsettings automation ON automation.business_id = b.id" if has_schedule else ""
    cursor.execute(
        f"""
        SELECT b.id, b.id AS business_id, b.name AS business_name,
               COALESCE(c.title, b.name) AS title, COALESCE(c.address, b.address) AS subtitle,
               c.rating, c.reviews_count, c.seo_score,
               {schedule_select}
               COALESCE(q.updated_at, c.updated_at, links.updated_at) AS updated_at,
               COALESCE(links.provider_sources, '[]'::jsonb) AS provider_sources,
               q.status AS parse_status, q.source AS parse_source, q.updated_at AS parse_updated_at
        FROM businesses b
        LEFT JOIN LATERAL (
            SELECT title, address, rating, reviews_count, seo_score, updated_at
            FROM cards WHERE business_id = b.id
            ORDER BY is_latest DESC NULLS LAST, updated_at DESC LIMIT 1
        ) c ON TRUE
        LEFT JOIN LATERAL (
            SELECT jsonb_agg(DISTINCT LOWER(COALESCE(map_type, ''))) AS provider_sources,
                   MAX(created_at) AS updated_at
            FROM businessmaplinks WHERE business_id = b.id
        ) links ON TRUE
        LEFT JOIN LATERAL (
            SELECT status, source, updated_at FROM parsequeue
            WHERE business_id = b.id ORDER BY updated_at DESC LIMIT 1
        ) q ON TRUE
        {schedule_join}
        WHERE (%s OR b.id = ANY(%s))
        ORDER BY COALESCE(q.updated_at, c.updated_at, links.updated_at) DESC NULLS LAST, b.name
        LIMIT 200
        """,
        (platform, business_ids),
    )
    items = []
    for value in cursor.fetchall() or []:
        item = _row(cursor, value)
        parse_status = str(item.get("parse_status") or "").lower()
        status = "running" if parse_status in {"pending", "processing"} else "error" if parse_status in {"failed", "error", "captcha_required"} else "fresh"
        items.append({
            **item,
            "kind": "card",
            "status": status,
            "refresh_cost_credits": int(os.getenv("OPERATOR_MAP_REFRESH_ESTIMATED_CREDITS", "10") or "10"),
            "scheduled_refresh_cost_credits": 0,
        })
    return items


def _content(cursor: Any, scope: dict[str, Any]) -> list[dict[str, Any]]:
    if not _table_exists(cursor, "contentplans") or not _table_exists(cursor, "contentplanitems"):
        return []
    platform, business_ids = _business_filter(scope)
    cursor.execute(
        """
        SELECT i.id, i.business_id, b.name AS business_name,
               COALESCE(NULLIF(TRIM(i.theme), ''), 'Элемент контент-плана') AS title,
               COALESCE(NULLIF(TRIM(i.draft_text), ''), NULLIF(TRIM(i.goal), ''), 'Черновик ещё не подготовлен') AS subtitle,
               i.status, i.updated_at, i.plan_id, p.title AS plan_title,
               i.scheduled_for, i.content_type, i.draft_text
        FROM contentplanitems i
        JOIN contentplans p ON p.id = i.plan_id
        JOIN businesses b ON b.id = i.business_id
        WHERE (%s OR i.business_id = ANY(%s))
        ORDER BY i.scheduled_for ASC, i.updated_at DESC LIMIT 200
        """,
        (platform, business_ids),
    )
    return [{**_row(cursor, item), "kind": "content_plan_item"} for item in cursor.fetchall() or []]


def _services(cursor: Any, scope: dict[str, Any]) -> list[dict[str, Any]]:
    if not _table_exists(cursor, "userservices"):
        return []
    platform, business_ids = _business_filter(scope)
    columns: set[str] = set()
    try:
        cursor.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'userservices'
            """
        )
        columns = {str(_row(cursor, value).get("column_name") or "") for value in cursor.fetchall() or []}
    except (TypeError, ValueError):
        columns = set()
    source_select = "s.source" if "source" in columns else "NULL::text AS source"
    cursor.execute(
        f"""
        SELECT s.id, s.business_id, b.name AS business_name, s.name AS title,
               COALESCE(NULLIF(TRIM(s.description), ''), s.category, 'Без описания') AS subtitle,
               s.price, s.category, CASE WHEN COALESCE(s.is_active, TRUE) THEN 'active' ELSE 'archived' END AS status,
               s.updated_at, {source_select}
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
    available_actions = {
        "content": [
            {"key": "content.item.generate_draft", "label": "Подготовить черновик"},
            {"key": "content.item.update", "label": "Редактировать"},
        ],
        "services": [
            {"key": "services.update", "label": "Изменить услугу"},
            {"key": "services.optimize", "label": "Улучшить услуги"},
            {"key": "services.compress", "label": "Сократить меню"},
        ],
        "cards": [{"key": "cards.schedule.update", "label": "Настроить график"}],
        "finance": [{"key": "finance.sales_import", "label": "Загрузить продажи"}],
    }.get(module, [])
    return {
        "status": "available" if available_actions else "read_only",
        "scope": scope,
        "items": items,
        "counts": {"total": len(items)},
        "cursor": None,
        "as_of": datetime.now(timezone.utc).isoformat(),
        "freshness": {"status": "live"},
        "data_warnings": [],
        "available_actions": available_actions,
        "filters": {},
    }
