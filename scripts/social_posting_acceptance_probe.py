#!/usr/bin/env python3
"""Read-only acceptance probe for the LocalOS Social Posting Agent.

Run inside the app container or any environment with the production DATABASE_URL.
It does not prepare posts, approve, queue, publish, or write metrics. The goal is
to prove the selected business is ready for the next human-approved step.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from database_manager import DatabaseManager
from services.social_post_service import (
    check_social_api_channel_preflight,
    get_social_channel_readiness,
    get_social_launch_preflight,
    preview_due_social_post_dispatch,
    rehearse_social_posts_publish,
)


def _one(cursor: Any, query: str, params: tuple[Any, ...]) -> dict[str, Any]:
    cursor.execute(query, params)
    row = cursor.fetchone()
    return dict(row or {})


def _many(cursor: Any, query: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    cursor.execute(query, params)
    return [dict(row) for row in cursor.fetchall() or []]


def _business_snapshot(cursor: Any, business_id: str) -> dict[str, Any]:
    return _one(
        cursor,
        """
        SELECT b.id, b.name, b.owner_id
        FROM businesses b
        WHERE b.id = %s
        """,
        (business_id,),
    )


def _latest_plan_snapshot(cursor: Any, business_id: str) -> dict[str, Any]:
    plan = _one(
        cursor,
        """
        SELECT cp.id, cp.business_id, cp.title, cp.period_start, cp.period_end, cp.updated_at
        FROM contentplans cp
        WHERE cp.business_id = %s
        ORDER BY cp.updated_at DESC NULLS LAST, cp.created_at DESC NULLS LAST
        LIMIT 1
        """,
        (business_id,),
    )
    plan_id = str(plan.get("id") or "").strip()
    if not plan_id:
        return {"plan": {}, "summary": {}, "ready_items_without_social_posts": []}

    summary = _one(
        cursor,
        """
        SELECT COUNT(cpi.id) AS items,
               COUNT(cpi.id) FILTER (WHERE length(trim(coalesce(cpi.draft_text, %s))) > 0) AS ready_texts,
               COUNT(cpi.id) FILTER (WHERE length(trim(coalesce(cpi.draft_text, %s))) = 0) AS missing_texts,
               COUNT(DISTINCT sp.id) AS social_posts,
               COUNT(DISTINCT sp.id) FILTER (WHERE sp.status = %s) AS queued_posts,
               COUNT(DISTINCT sp.id) FILTER (
                   WHERE sp.status = %s
                     AND sp.approved_at IS NOT NULL
                     AND COALESCE(sp.scheduled_for, NOW()) <= NOW()
               ) AS due_queued_posts
        FROM contentplanitems cpi
        LEFT JOIN social_posts sp ON sp.content_plan_item_id = cpi.id
        WHERE cpi.plan_id = %s
        """,
        ("", "", "queued", "queued", plan_id),
    )
    ready_items_without_posts = _many(
        cursor,
        """
        SELECT cpi.id, cpi.scheduled_for, cpi.theme, cpi.goal
        FROM contentplanitems cpi
        LEFT JOIN social_posts sp ON sp.content_plan_item_id = cpi.id
        WHERE cpi.plan_id = %s
          AND length(trim(coalesce(cpi.draft_text, %s))) > 0
          AND sp.id IS NULL
        ORDER BY cpi.scheduled_for ASC NULLS LAST, cpi.updated_at DESC NULLS LAST
        LIMIT 10
        """,
        (plan_id, ""),
    )
    return {
        "plan": plan,
        "summary": summary,
        "ready_items_without_social_posts": ready_items_without_posts,
    }


def _status_counts(cursor: Any, business_id: str) -> list[dict[str, Any]]:
    return _many(
        cursor,
        """
        SELECT platform, publish_mode, status, COUNT(*) AS count
        FROM social_posts
        WHERE business_id = %s
        GROUP BY platform, publish_mode, status
        ORDER BY platform, publish_mode, status
        """,
        (business_id,),
    )


def _due_queued_post_ids(cursor: Any, business_id: str, batch_size: int) -> list[str]:
    rows = _many(
        cursor,
        """
        SELECT sp.id
        FROM social_posts sp
        WHERE sp.business_id = %s
          AND sp.status = %s
          AND sp.approved_at IS NOT NULL
          AND COALESCE(sp.scheduled_for, NOW()) <= NOW()
        ORDER BY sp.scheduled_for ASC NULLS FIRST, sp.updated_at ASC
        LIMIT %s
        """,
        (business_id, "queued", max(1, min(int(batch_size or 10), 50))),
    )
    return [str(row.get("id") or "").strip() for row in rows if str(row.get("id") or "").strip()]


def build_probe(business_id: str, batch_size: int) -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        business = _business_snapshot(cursor, business_id)
        if not business:
            return {
                "success": False,
                "business_id": business_id,
                "error": "business_not_found",
            }
        owner_id = str(business.get("owner_id") or "").strip()
        if not owner_id:
            return {
                "success": False,
                "business": business,
                "error": "business_owner_missing",
            }

        plan_payload = _latest_plan_snapshot(cursor, business_id)
        status_counts = _status_counts(cursor, business_id)
        due_queued_post_ids = _due_queued_post_ids(cursor, business_id, batch_size)
    finally:
        db.close()

    channel_readiness = get_social_channel_readiness(owner_id, business_id)
    api_preflight = check_social_api_channel_preflight(owner_id, business_id)
    launch_preflight = get_social_launch_preflight(owner_id, business_id, batch_size=batch_size)
    dispatch_preview = preview_due_social_post_dispatch(owner_id, batch_size=batch_size, business_id=business_id)
    launch_rehearsal = _build_launch_rehearsal(owner_id, due_queued_post_ids)
    plan_summary = plan_payload.get("summary") if isinstance(plan_payload.get("summary"), dict) else {}
    ready_candidates = plan_payload.get("ready_items_without_social_posts")
    if not isinstance(ready_candidates, list):
        ready_candidates = []
    safety = launch_preflight.get("safety") if isinstance(launch_preflight.get("safety"), dict) else {}
    first_cycle_verification = (
        launch_preflight.get("first_cycle_verification")
        if isinstance(launch_preflight.get("first_cycle_verification"), dict)
        else {}
    )
    dispatch_readiness = (
        launch_preflight.get("dispatch_readiness")
        if isinstance(launch_preflight.get("dispatch_readiness"), dict)
        else {}
    )
    acceptance_ready = (
        dispatch_preview.get("dry_run") is True
        and launch_rehearsal.get("dry_run") is True
        and launch_rehearsal.get("external_publish_performed") is False
        and launch_rehearsal.get("provider_write_performed") is False
        and safety.get("approval_required") is True
        and safety.get("browser_final_click_allowed") is False
        and safety.get("maps_are_supervised_or_manual") is True
        and str(dispatch_preview.get("business_scope") or "").strip() == business_id
    )

    return {
        "success": True,
        "read_only": True,
        "external_publish_performed": False,
        "database_write_performed": False,
        "acceptance_ready": bool(acceptance_ready),
        "business": business,
        "latest_plan": plan_payload.get("plan") if isinstance(plan_payload.get("plan"), dict) else {},
        "plan_summary": plan_summary,
        "ready_items_without_social_posts": ready_candidates,
        "social_post_status_counts": status_counts,
        "channel_readiness_summary": channel_readiness.get("summary", {}),
        "api_preflight_summary": api_preflight.get("summary", {}),
        "launch_status": launch_preflight.get("status"),
        "launch_safe_to_enable_scoped_dispatch": launch_preflight.get("safe_to_enable_scoped_dispatch"),
        "launch_summary": launch_preflight.get("summary", {}),
        "first_api_publish_readiness": launch_preflight.get("first_api_publish_readiness", {}),
        "dispatch_readiness": dispatch_readiness,
        "first_cycle_verification": first_cycle_verification,
        "due_queued_post_ids": due_queued_post_ids,
        "launch_rehearsal": launch_rehearsal,
        "safety": {
            "approval_required": safety.get("approval_required") is True,
            "browser_final_click_allowed": safety.get("browser_final_click_allowed") is True,
            "maps_are_supervised_or_manual": safety.get("maps_are_supervised_or_manual") is True,
            "external_publish_requires_approval": True,
        },
        "dispatch_preview": {
            "dry_run": dispatch_preview.get("dry_run"),
            "picked": dispatch_preview.get("picked"),
            "business_scope": dispatch_preview.get("business_scope"),
            "readiness": dispatch_preview.get("readiness", {}),
            "by_action": dispatch_preview.get("by_action", {}),
        },
        "next_required_human_step": _next_required_human_step(plan_summary, ready_candidates, launch_rehearsal),
    }


def _build_launch_rehearsal(owner_id: str, post_ids: list[str]) -> dict[str, Any]:
    if not post_ids:
        return {
            "schema": "localos_social_publish_rehearsal_bulk_v1",
            "dry_run": True,
            "external_publish_performed": False,
            "provider_write_performed": False,
            "summary": {
                "status": "empty",
                "total": 0,
                "ready": 0,
                "api_ready": 0,
                "supervised_ready": 0,
                "manual_or_blocked": 0,
                "message_ru": "Нет due queued постов для rehearsal.",
                "message_en": "No due queued posts for rehearsal.",
            },
            "rehearsals": [],
            "failed": [],
        }
    return rehearse_social_posts_publish(owner_id, post_ids)


def _next_required_human_step(
    plan_summary: dict[str, Any],
    ready_candidates: list[dict[str, Any]],
    launch_rehearsal: dict[str, Any],
) -> dict[str, str]:
    ready_count = int(plan_summary.get("ready_texts") or 0)
    social_posts = int(plan_summary.get("social_posts") or 0)
    due_posts = int(plan_summary.get("due_queued_posts") or 0)
    rehearsal_summary = launch_rehearsal.get("summary") if isinstance(launch_rehearsal.get("summary"), dict) else {}
    rehearsal_ready = int(rehearsal_summary.get("ready") or 0)
    rehearsal_blocked = int(rehearsal_summary.get("manual_or_blocked") or 0)
    if due_posts > 0:
        if rehearsal_blocked > 0:
            return {
                "ru": "Исправьте блокеры rehearsal у due-постов, затем повторите preflight перед dispatch.",
                "en": "Fix due-post rehearsal blockers, then rerun preflight before dispatch.",
            }
        if rehearsal_ready > 0:
            return {
                "ru": "Due-посты прошли rehearsal: проверьте live API-preflight и запускайте scoped dispatch только после явного подтверждения.",
                "en": "Due posts passed rehearsal: check live API preflight and run scoped dispatch only after explicit approval.",
            }
        return {
            "ru": "Запустите scoped launch preflight и проверьте ключи перед первым dispatch.",
            "en": "Run scoped launch preflight and verify credentials before the first dispatch.",
        }
    if social_posts > 0:
        return {
            "ru": "Откройте preview, проверьте тексты, подтвердите и поставьте публикации в расписание.",
            "en": "Open preview, review copy, approve, and queue the posts.",
        }
    if ready_count > 0 and ready_candidates:
        return {
            "ru": "В UI нажмите “Подготовить каналы” для готовой темы. Это создаст drafts, но не опубликует наружу.",
            "en": "In the UI, click Prepare channels for a ready topic. This creates drafts but does not publish externally.",
        }
    return {
        "ru": "Сначала допишите текст хотя бы для одной темы контент-плана.",
        "en": "First, add copy to at least one content plan item.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Social Posting Agent acceptance probe.")
    parser.add_argument("business_id")
    parser.add_argument("--batch-size", type=int, default=10)
    args = parser.parse_args()
    try:
        payload = build_probe(str(args.business_id or "").strip(), max(1, min(int(args.batch_size or 10), 50)))
    except Exception:
        print(json.dumps({"success": False, "error": str(sys.exc_info()[1])}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str))
    return 0 if payload.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
