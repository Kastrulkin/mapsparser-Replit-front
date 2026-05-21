from __future__ import annotations

import uuid
from typing import Any


OPERATOR_APIFY_REFRESH_ENABLED = False
OPERATOR_MAP_REFRESH_SOURCE = "apify_yandex"


def _row_to_dict(cursor: Any, row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    if isinstance(row, dict):
        return dict(row)
    if hasattr(row, "keys"):
        try:
            return dict(row)
        except Exception:
            pass
    description = getattr(cursor, "description", None) or []
    columns = [col[0] for col in description]
    if isinstance(row, (list, tuple)) and columns:
        return {columns[idx]: row[idx] for idx in range(min(len(columns), len(row)))}
    return None


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _load_latest_map_url(cursor: Any, *, business_id: str) -> str:
    cursor.execute(
        """
        SELECT url
        FROM businessmaplinks
        WHERE business_id = %s
          AND COALESCE(BTRIM(url), '') <> ''
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (business_id,),
    )
    row = _row_to_dict(cursor, cursor.fetchone()) or {}
    return _clean_text(row.get("url"))


def build_operator_map_refresh_plan(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    explicit_url: Any = None,
) -> dict[str, Any]:
    blocked: list[str] = []
    url = _clean_text(explicit_url) or _load_latest_map_url(cursor, business_id=business_id)
    if not url:
        blocked.append("map_link_required")
    if not OPERATOR_APIFY_REFRESH_ENABLED:
        blocked.append("operator_apify_refresh_disabled")

    return {
        "status": "ready" if not blocked else "blocked",
        "business_id": business_id,
        "user_id": user_id,
        "url": url,
        "source": OPERATOR_MAP_REFRESH_SOURCE,
        "task_type": "parse_card",
        "blocked_reasons": blocked,
        "side_effects": {
            "parsequeue_jobs_created": False,
            "external_calls_performed": False,
            "external_writes_performed": False,
            "credit_charged": False,
        },
    }


def enqueue_operator_map_refresh(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    explicit_url: Any = None,
) -> dict[str, Any]:
    plan = build_operator_map_refresh_plan(
        cursor,
        business_id=business_id,
        user_id=user_id,
        explicit_url=explicit_url,
    )
    if plan["status"] != "ready":
        return plan

    queue_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO parsequeue (
            id, url, user_id, business_id, status, task_type, source, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, 'pending', %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        RETURNING id, status, source, task_type
        """,
        (
            queue_id,
            plan["url"],
            user_id,
            business_id,
            plan["task_type"],
            plan["source"],
        ),
    )
    row = _row_to_dict(cursor, cursor.fetchone()) or {}
    result = dict(plan)
    result.update(
        {
            "status": "queued",
            "queue_id": _clean_text(row.get("id")) or queue_id,
            "queue_status": _clean_text(row.get("status")) or "pending",
            "side_effects": {
                "parsequeue_jobs_created": True,
                "external_calls_performed": False,
                "external_writes_performed": False,
                "credit_charged": False,
            },
        }
    )
    return result
