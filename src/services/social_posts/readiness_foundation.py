from __future__ import annotations

import json
import os
import sys
import ipaddress
import urllib.error
import urllib.request
import urllib.parse
import uuid
from datetime import date, datetime, timezone
from typing import Any

from auth_encryption import decrypt_auth_data
from database_manager import DatabaseManager
from core.outbound_network import outbound_urlopen
from core.telegram_network import telegram_urlopen
from core.telegram_token_store import decode_telegram_bot_token
from core.helpers import get_business_owner_id
from services.media_file_storage import load_media_file
from services.openclaw_capability_catalog import get_openclaw_capability_catalog


SOCIAL_POST_PLATFORMS = [
    "yandex_maps",
    "two_gis",
    "google_business",
    "telegram",
    "vk",
    "instagram",
    "facebook",
]

API_PLATFORMS = {"google_business", "telegram", "vk", "instagram", "facebook"}
BROWSER_OR_MANUAL_PLATFORMS = {"yandex_maps", "two_gis"}
FIRST_API_PROOF_PLATFORMS = ("telegram", "vk")

SOCIAL_POST_STATUSES = {
    "draft",
    "needs_review",
    "approved",
    "queued",
    "publishing",
    "published",
    "failed",
    "needs_manual_publish",
    "needs_supervised_publish",
}

SOCIAL_POST_TABLES = (
    "social_posts",
    "social_post_metrics",
    "social_post_attribution_events",
)

SOCIAL_QUEUE_GROUPS = (
    {
        "key": "needs_review",
        "label_ru": "Нужно проверить",
        "label_en": "Needs review",
        "next_action_ru": "Проверить тексты и подтвердить публикации.",
        "next_action_en": "Review copy and approve posts.",
    },
    {
        "key": "api_ready",
        "label_ru": "Готово к API",
        "label_en": "API ready",
        "next_action_ru": "Поставить подтверждённые API-каналы в очередь публикации.",
        "next_action_en": "Queue approved API channels for publishing.",
    },
    {
        "key": "scheduled",
        "label_ru": "Запланировано",
        "label_en": "Scheduled",
        "next_action_ru": "Ждёт даты публикации. Исполнитель выполнит API-публикацию или создаст контролируемое размещение.",
        "next_action_en": "Waiting for schedule. The worker will publish via API or create supervised placement.",
    },
    {
        "key": "needs_supervised_publish",
        "label_ru": "Нужно контролируемое размещение",
        "label_en": "Needs supervised placement",
        "next_action_ru": "Открыть контролируемое размещение для Яндекс/2ГИС и остановиться перед финальной публикацией.",
        "next_action_en": "Open supervised Yandex/2GIS placement and stop before final publishing.",
    },
    {
        "key": "needs_manual_publish",
        "label_ru": "Нужно вручную / подключить канал",
        "label_en": "Manual / connection needed",
        "next_action_ru": "Подключить ключи или права, либо разместить вручную и отметить результат.",
        "next_action_en": "Connect keys or permissions, or publish manually and mark the result.",
    },
    {
        "key": "published",
        "label_ru": "Опубликовано",
        "label_en": "Published",
        "next_action_ru": "Собрать реакции и отметить заявки/обращения.",
        "next_action_en": "Collect reactions and record leads/inquiries.",
    },
    {
        "key": "failed",
        "label_ru": "Ошибка",
        "label_en": "Failed",
        "next_action_ru": "Исправить подключение, повторить публикацию или перевести в ручной режим.",
        "next_action_en": "Fix connection, retry, or move to manual publishing.",
    },
)

def ensure_social_post_tables(cursor: Any) -> None:
    missing_tables = []
    for table_name in SOCIAL_POST_TABLES:
        cursor.execute("SELECT to_regclass(%s)", (f"public.{table_name}",))
        row = cursor.fetchone()
        exists = bool(_row_get(row, "to_regclass", 0))
        if not exists:
            missing_tables.append(table_name)
    if missing_tables:
        raise RuntimeError(
            "social post tables are not migrated: "
            + ", ".join(missing_tables)
            + ". Run Alembic migration 20260619_001 before using social post endpoints."
        )

def prepare_social_posts_for_item(
    user_id: str,
    item_id: str,
    platforms: list[str] | None = None,
    replace_platforms: bool = False,
) -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_social_post_tables(cursor)
        item = _load_plan_item_for_user(cursor, user_id, item_id)
        requested_platforms = _normalize_platforms(platforms)
        base_text = _base_text_from_item(item)
        created_or_updated = []
        for platform in requested_platforms:
            post = _upsert_social_post(cursor, user_id, item, platform, base_text)
            created_or_updated.append(post)
        removed_platforms: list[str] = []
        preserved_platforms: list[str] = []
        if replace_platforms:
            removed_platforms, preserved_platforms = _remove_unselected_social_posts(
                cursor,
                item_id=item_id,
                selected_platforms=requested_platforms,
            )
        db.conn.commit()
        return {
            "posts": created_or_updated,
            "summary": _summary_for_posts(created_or_updated),
            "selected_platforms": requested_platforms,
            "removed_platforms": removed_platforms,
            "preserved_platforms": preserved_platforms,
        }
    except Exception:
        db.conn.rollback()
        raise sys.exc_info()[1]
    finally:
        db.close()

def preview_social_posts_for_item(user_id: str, item_id: str, platforms: list[str] | None = None) -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_social_post_tables(cursor)
        item = _load_plan_item_for_user(cursor, user_id, item_id)
        requested_platforms = _normalize_platforms(platforms)
        base_text = _base_text_from_item(item)
        existing_by_platform = _existing_social_posts_for_item(cursor, item_id)
        previews = [
            _preview_social_post_for_platform(item, platform, base_text, existing_by_platform.get(platform))
            for platform in requested_platforms
        ]
        summary = _summary_for_posts(previews)
        summary["would_create"] = sum(1 for post in previews if post.get("prepare_action") == "would_create")
        summary["would_update"] = sum(1 for post in previews if post.get("prepare_action") == "would_update")
        summary["would_preserve"] = sum(1 for post in previews if str(post.get("prepare_action") or "").startswith("preserve_"))
        return {
            "read_only": True,
            "database_write_performed": False,
            "external_publish_performed": False,
            "item": {
                "id": str(item.get("id") or "").strip(),
                "content_plan_id": str(item.get("plan_id") or item.get("parent_plan_id") or "").strip(),
                "business_id": str(item.get("business_id") or item.get("plan_business_id") or "").strip(),
                "scheduled_for": item.get("scheduled_for"),
                "theme": str(item.get("theme") or "").strip(),
                "goal": str(item.get("goal") or "").strip(),
            },
            "base_text": base_text,
            "posts": previews,
            "summary": summary,
            "next_action_ru": (
                "Если предпросмотр устраивает, нажмите “Подготовить каналы”. Это создаст черновики, но не опубликует наружу."
            ),
            "next_action_en": (
                "If the preview looks right, click Prepare channels. This creates drafts but does not publish externally."
            ),
        }
    finally:
        db.close()

def list_social_posts_for_plan(user_id: str, plan_id: str) -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_social_post_tables(cursor)
        plan = _load_plan_for_user(cursor, user_id, plan_id)
        cursor.execute(
            """
            SELECT
                sp.*,
                COALESCE(ms.views, 0) AS views,
                COALESCE(ms.impressions, 0) AS impressions,
                COALESCE(ms.reach, 0) AS reach,
                COALESCE(ms.likes, 0) AS likes,
                COALESCE(ms.comments, 0) AS comments,
                COALESCE(ms.shares, 0) AS shares,
                COALESCE(ms.clicks, 0) AS clicks,
                COALESCE(ms.inquiries, 0) AS inquiries,
                COALESCE(ms.leads, 0) AS leads
            FROM social_posts sp
            LEFT JOIN (
                SELECT
                    social_post_id,
                    SUM(views) AS views,
                    SUM(impressions) AS impressions,
                    SUM(reach) AS reach,
                    SUM(likes) AS likes,
                    SUM(comments) AS comments,
                    SUM(shares) AS shares,
                    SUM(clicks) AS clicks,
                    SUM(inquiries) AS inquiries,
                    SUM(leads) AS leads
                FROM social_post_metrics
                GROUP BY social_post_id
            ) ms ON ms.social_post_id = sp.id
            WHERE sp.content_plan_id = %s
            ORDER BY sp.scheduled_for ASC NULLS LAST, sp.created_at ASC, sp.platform ASC
            """,
            (plan_id,),
        )
        posts = [_serialize_social_post(cursor, row) for row in cursor.fetchall() or []]
        plan_item_count = _content_plan_item_count(cursor, plan_id)
        channel_readiness = _build_channel_readiness(cursor, str(plan.get("business_id") or ""))
        return {
            "posts": posts,
            "summary": _summary_for_posts(posts),
            "queue_groups": build_social_queue_groups(posts),
            "recommendation": _build_plan_recommendation(posts),
            "learning_readiness": _social_learning_readiness(posts),
            "goal_progress": _social_goal_progress(posts, plan_item_count),
            "channel_readiness": channel_readiness,
            "first_api_proof_dossier": _social_first_api_proof_dossier(posts, channel_readiness, plan_item_count),
            "openclaw_browser_readiness": _social_openclaw_browser_readiness(),
        }
    finally:
        db.close()

def get_social_channel_readiness(user_id: str, business_id: str) -> dict[str, Any]:
    normalized_business_id = str(business_id or "").strip()
    if not normalized_business_id:
        raise ValueError("Бизнес не выбран")
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        _require_business_access(cursor, user_id, normalized_business_id)
        readiness = _build_channel_readiness(cursor, normalized_business_id)
        api_channels = [item for item in readiness if str(item.get("publish_mode") or "") == "api"]
        return {
            "channel_readiness": readiness,
            "openclaw_browser_readiness": _social_openclaw_browser_readiness(cursor=cursor),
            "summary": {
                "total": len(readiness),
                "api_total": len(api_channels),
                "api_ready": sum(1 for item in api_channels if bool(item.get("ready"))),
                "api_needs_attention": sum(1 for item in api_channels if not bool(item.get("ready"))),
                "controlled_or_manual": sum(1 for item in readiness if str(item.get("publish_mode") or "") != "api"),
            },
        }
    finally:
        db.close()

def check_social_api_channel_preflight(user_id: str, business_id: str) -> dict[str, Any]:
    normalized_business_id = str(business_id or "").strip()
    if not normalized_business_id:
        raise ValueError("Бизнес не выбран")
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        _require_business_access(cursor, user_id, normalized_business_id)
        api_preflight = [
            _telegram_api_channel_preflight(cursor, normalized_business_id),
            _vk_api_channel_preflight(cursor, normalized_business_id),
            _google_business_api_channel_preflight(cursor, normalized_business_id),
            _meta_api_channel_preflight(cursor, normalized_business_id, "instagram"),
            _meta_api_channel_preflight(cursor, normalized_business_id, "facebook"),
        ]
        return {
            "business_id": normalized_business_id,
            "api_preflight": api_preflight,
            "read_only": True,
            "external_publish_performed": False,
            "human_approval_required_for_publish": True,
            "summary": {
                "checked": len(api_preflight),
                "ready": sum(1 for item in api_preflight if bool(item.get("ready"))),
                "needs_attention": sum(1 for item in api_preflight if not bool(item.get("ready"))),
            },
        }
    finally:
        db.close()

def check_social_openclaw_browser_readiness(user_id: str, business_id: str) -> dict[str, Any]:
    normalized_business_id = str(business_id or "").strip()
    if not normalized_business_id:
        raise ValueError("Бизнес не выбран")
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        _require_business_access(cursor, user_id, normalized_business_id)
        return {
            "business_id": normalized_business_id,
            "openclaw_browser_readiness": _social_openclaw_browser_readiness(cursor=cursor),
            "read_only": True,
            "external_publish_performed": False,
            "browser_final_click_allowed": False,
            "capability_checked": "social.post.publish_supervised_browser",
            "safety_contract": _social_supervised_safety_contract(),
            "owner_next_action_ru": "Если статус готов, подготовьте контролируемое размещение у поста карты. Если нет, используйте ручное размещение с готовым текстом и чеклистом.",
            "owner_next_action_en": "If the check is ready, create supervised placement on the map post. If not, use manual placement with the prepared copy and checklist.",
        }
    finally:
        db.close()

def get_social_launch_preflight(user_id: str, business_id: str, batch_size: int = 10) -> dict[str, Any]:
    normalized_business_id = str(business_id or "").strip()
    if not normalized_business_id:
        raise ValueError("Бизнес не выбран")
    channel_payload = get_social_channel_readiness(user_id, normalized_business_id)
    dispatch_preview = preview_due_social_post_dispatch(
        user_id,
        batch_size=max(1, min(int(batch_size or 10), 50)),
        business_id=normalized_business_id,
    )
    api_preflight_payload = check_social_api_channel_preflight(user_id, normalized_business_id)
    channel_readiness = channel_payload.get("channel_readiness")
    channel_summary = channel_payload.get("summary")
    launch_rehearsal = _social_launch_rehearsal_from_preview(user_id, dispatch_preview)
    workflow_stage_counts = _social_post_workflow_stage_counts(user_id, normalized_business_id)
    return _build_social_launch_preflight_payload(
        normalized_business_id,
        channel_readiness if isinstance(channel_readiness, list) else [],
        channel_summary if isinstance(channel_summary, dict) else {},
        dispatch_preview,
        api_preflight_payload.get("api_preflight") if isinstance(api_preflight_payload.get("api_preflight"), list) else [],
        api_preflight_payload.get("summary") if isinstance(api_preflight_payload.get("summary"), dict) else {},
        launch_rehearsal,
        workflow_stage_counts,
    )

def _social_post_workflow_stage_counts(user_id: str, business_id: str) -> dict[str, Any]:
    normalized_business_id = str(business_id or "").strip()
    if not normalized_business_id:
        return _empty_social_post_workflow_stage_counts()
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_social_post_tables(cursor)
        _require_business_access(cursor, user_id, normalized_business_id)
        cursor.execute(
            """
            SELECT
              COUNT(*) AS total,
              COUNT(*) FILTER (WHERE status = 'draft') AS draft,
              COUNT(*) FILTER (WHERE status = 'needs_review') AS needs_review,
              COUNT(*) FILTER (WHERE status = 'approved') AS approved_not_queued,
              COUNT(*) FILTER (WHERE status = 'queued') AS queued_total,
              COUNT(*) FILTER (
                WHERE status = 'queued'
                  AND COALESCE(scheduled_for, NOW()) <= NOW()
              ) AS queued_due,
              COUNT(*) FILTER (
                WHERE status = 'queued'
                  AND scheduled_for > NOW()
              ) AS queued_future,
              COUNT(*) FILTER (WHERE status = 'publishing') AS publishing,
              COUNT(*) FILTER (WHERE status = 'published') AS published,
              COUNT(*) FILTER (WHERE status = 'needs_supervised_publish') AS needs_supervised_publish,
              COUNT(*) FILTER (WHERE status = 'needs_manual_publish') AS needs_manual_publish,
              COUNT(*) FILTER (WHERE status = 'failed') AS failed
            FROM social_posts
            WHERE business_id = %s
            """,
            (normalized_business_id,),
        )
        row = _row_to_dict(cursor, cursor.fetchone())
    finally:
        db.close()
    counts = _empty_social_post_workflow_stage_counts()
    for key in _social_post_workflow_count_keys():
        counts[key] = int(row.get(key) or 0)
    counts["business_id"] = normalized_business_id
    counts["schema"] = "localos_social_post_workflow_stage_counts_v1"
    counts["worker_idle_reason"] = _social_worker_idle_reason(counts)
    return counts

def _social_post_workflow_count_keys() -> tuple[str, ...]:
    return (
        "total",
        "draft",
        "needs_review",
        "approved_not_queued",
        "queued_total",
        "queued_due",
        "queued_future",
        "publishing",
        "published",
        "needs_supervised_publish",
        "needs_manual_publish",
        "failed",
    )

def _empty_social_post_workflow_stage_counts() -> dict[str, Any]:
    return {
        "schema": "localos_social_post_workflow_stage_counts_v1",
        "business_id": "",
        "total": 0,
        "draft": 0,
        "needs_review": 0,
        "approved_not_queued": 0,
        "queued_total": 0,
        "queued_due": 0,
        "queued_future": 0,
        "publishing": 0,
        "published": 0,
        "needs_supervised_publish": 0,
        "needs_manual_publish": 0,
        "failed": 0,
        "worker_idle_reason": {},
    }

def _build_social_launch_preflight_payload(
    business_id: str,
    channel_readiness: list[dict[str, Any]],
    channel_summary: dict[str, Any],
    dispatch_preview: dict[str, Any],
    api_preflight: list[dict[str, Any]] | None = None,
    api_preflight_summary: dict[str, Any] | None = None,
    launch_rehearsal: dict[str, Any] | None = None,
    workflow_stage_counts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    readiness = dispatch_preview.get("readiness") if isinstance(dispatch_preview.get("readiness"), dict) else {}
    workflow_counts = workflow_stage_counts if isinstance(workflow_stage_counts, dict) else _empty_social_post_workflow_stage_counts()
    dispatch_items = dispatch_preview.get("items") if isinstance(dispatch_preview.get("items"), list) else []
    due_count = int(readiness.get("due_count") or dispatch_preview.get("picked") or 0)
    external_publish_count = int(readiness.get("external_publish_count") or 0)
    controlled_count = int(readiness.get("controlled_count") or 0)
    manual_count = int(readiness.get("manual_count") or 0)
    skipped_no_access = int(readiness.get("skipped_no_access") or dispatch_preview.get("skipped_no_access") or 0)
    api_preflight_items = api_preflight if isinstance(api_preflight, list) else []
    api_preflight_summary_payload = api_preflight_summary if isinstance(api_preflight_summary, dict) else {}
    launch_rehearsal_payload = launch_rehearsal if isinstance(launch_rehearsal, dict) else _empty_social_launch_rehearsal()
    launch_rehearsal_summary = (
        launch_rehearsal_payload.get("summary")
        if isinstance(launch_rehearsal_payload.get("summary"), dict)
        else {}
    )
    api_preflight_blocked_due_posts = _api_preflight_blocked_due_posts(dispatch_items, api_preflight_items)
    blocked_api_channels = [
        item for item in channel_readiness
        if str(item.get("publish_mode") or "") == "api" and not bool(item.get("ready"))
    ]
    controlled_channels = [
        item for item in channel_readiness
        if str(item.get("publish_mode") or "") != "api"
    ]
    first_api_publish_readiness = _social_first_api_publish_readiness(channel_readiness, api_preflight_items)
    status = "no_due_posts"
    if external_publish_count > 0:
        status = "ready_for_api_dispatch"
    elif controlled_count > 0:
        status = "ready_for_controlled_handoff"
    elif manual_count > 0:
        status = "manual_or_connection_needed"
    elif skipped_no_access > 0:
        status = "access_limited"
    if api_preflight_blocked_due_posts:
        status = "api_preflight_blocked"
    safe_to_enable = (
        bool(str(business_id or "").strip())
        and due_count > 0
        and skipped_no_access == 0
        and not api_preflight_blocked_due_posts
    )
    scope = str(business_id or "").strip()
    first_cycle_verification = _social_worker_first_cycle_verification(
        external_publish_count,
        controlled_count,
        manual_count,
        skipped_no_access,
        scope,
    )
    runtime_alignment = _social_launch_runtime_alignment(scope)
    production_readiness = _social_production_readiness(
        status,
        safe_to_enable,
        due_count,
        external_publish_count,
        controlled_count,
        manual_count,
        skipped_no_access,
        api_preflight_blocked_due_posts,
        first_api_publish_readiness,
        runtime_alignment,
        workflow_counts,
    )
    launch_gate = _social_first_cycle_launch_gate(
        production_readiness,
        due_count,
        external_publish_count,
        controlled_count,
        manual_count,
        skipped_no_access,
    )
    first_api_proof_gate = _social_first_api_proof_gate(
        launch_gate,
        readiness.get("first_api_proof_candidate") if isinstance(readiness.get("first_api_proof_candidate"), dict) else {},
        api_preflight_blocked_due_posts,
        runtime_alignment,
    )
    live_validation_checklist = _social_live_validation_checklist(
        production_readiness,
        launch_gate,
        first_api_proof_gate,
        due_count,
        external_publish_count,
        controlled_count,
        manual_count,
    )
    recommended_env = {
        "dispatch": _dispatch_preview_recommended_env(str(business_id or "").strip()),
        "metrics": _metrics_preview_recommended_env(str(business_id or "").strip()),
    }
    launch_runbook = _social_launch_runbook(
        status,
        scope,
        due_count,
        external_publish_count,
        controlled_count,
        manual_count,
        skipped_no_access,
        first_cycle_verification,
    )
    first_cycle_proof_packet = _social_first_cycle_proof_packet(
        launch_gate,
        first_api_proof_gate,
        live_validation_checklist,
        recommended_env,
        launch_runbook,
        runtime_alignment,
    )
    proof_requirements = _social_proof_requirements(
        first_api_publish_readiness,
        first_api_proof_gate,
        launch_gate,
        channel_readiness,
        runtime_alignment,
        workflow_counts,
        due_count,
        external_publish_count,
        controlled_count,
        manual_count,
    )
    return {
        "business_id": scope,
        "status": status,
        "safe_to_enable_scoped_dispatch": safe_to_enable,
        "production_readiness": production_readiness,
        "launch_gate": launch_gate,
        "first_api_proof_gate": first_api_proof_gate,
        "live_validation_checklist": live_validation_checklist,
        "first_cycle_proof_packet": first_cycle_proof_packet,
        "proof_requirements": proof_requirements,
        "channel_readiness": channel_readiness,
        "channel_summary": channel_summary,
        "dispatch_preview": dispatch_preview,
        "dispatch_readiness": readiness,
        "api_preflight": api_preflight_items,
        "api_preflight_summary": api_preflight_summary_payload,
        "launch_rehearsal": launch_rehearsal_payload,
        "workflow_stage_counts": workflow_counts,
        "worker_idle_reason": _social_worker_idle_reason(workflow_counts),
        "api_preflight_blocked_due_posts": api_preflight_blocked_due_posts,
        "blocked_api_channels": blocked_api_channels,
        "controlled_channels": controlled_channels,
        "first_api_publish_readiness": first_api_publish_readiness,
        "recommended_env": recommended_env,
        "safety": {
            "approval_required": True,
            "scoped_dispatch_required": True,
            "external_publish_only_after_approval": True,
            "browser_final_click_allowed": False,
            "maps_are_supervised_or_manual": True,
            "api_preflight_required_before_first_cycle": True,
        },
        "summary": {
            "due_posts": due_count,
            "api_due_posts": external_publish_count,
            "controlled_due_posts": controlled_count,
            "manual_due_posts": manual_count,
            "api_ready_channels": len(first_api_publish_readiness.get("ready_platforms") or []),
            "api_blocked_channels": len(first_api_publish_readiness.get("blocked_platforms") or []),
            "blocked_api_channels": len(blocked_api_channels),
            "api_preflight_blocked_due_posts": len(api_preflight_blocked_due_posts),
            "launch_rehearsal_ready_posts": int(launch_rehearsal_summary.get("ready") or 0),
            "launch_rehearsal_blocked_posts": int(launch_rehearsal_summary.get("manual_or_blocked") or 0),
            "controlled_channels": len(controlled_channels),
            "skipped_no_access": skipped_no_access,
            "workflow_total_posts": int(workflow_counts.get("total") or 0),
            "workflow_needs_review": int(workflow_counts.get("needs_review") or 0),
            "workflow_approved_not_queued": int(workflow_counts.get("approved_not_queued") or 0),
            "workflow_queued_future": int(workflow_counts.get("queued_future") or 0),
        },
        "first_cycle_verification": first_cycle_verification,
        "runtime_alignment": runtime_alignment,
        "launch_runbook": launch_runbook,
        "message_ru": _social_launch_preflight_message(status, True),
        "message_en": _social_launch_preflight_message(status, False),
        "next_action_ru": _social_launch_preflight_next_action(status, scope, True),
        "next_action_en": _social_launch_preflight_next_action(status, scope, False),
    }

def _social_proof_requirements(
    first_api_publish_readiness: dict[str, Any],
    first_api_proof_gate: dict[str, Any],
    launch_gate: dict[str, Any],
    channel_readiness: list[dict[str, Any]],
    runtime_alignment: dict[str, Any],
    workflow_counts: dict[str, Any],
    due_count: int,
    external_publish_count: int,
    controlled_count: int,
    manual_count: int,
) -> dict[str, Any]:
    api_status = _social_api_proof_requirement_status(
        first_api_publish_readiness,
        first_api_proof_gate,
        workflow_counts,
        due_count,
        external_publish_count,
    )
    maps_status = _social_maps_proof_requirement_status(channel_readiness, controlled_count, manual_count)
    metrics_status = _social_metrics_proof_requirement_status(runtime_alignment, workflow_counts)
    groups = [
        _social_proof_requirement_group(
            "telegram_vk_api_proof",
            api_status,
            "Telegram/VK API proof",
            "Telegram/VK API proof",
            _social_api_proof_requirement_summary(api_status, first_api_publish_readiness, first_api_proof_gate, True),
            _social_api_proof_requirement_summary(api_status, first_api_publish_readiness, first_api_proof_gate, False),
            _social_api_proof_requirement_next_action(api_status, first_api_publish_readiness, first_api_proof_gate, True),
            _social_api_proof_requirement_next_action(api_status, first_api_publish_readiness, first_api_proof_gate, False),
            _social_api_proof_requirement_steps(api_status, first_api_publish_readiness, True),
            _social_api_proof_requirement_steps(api_status, first_api_publish_readiness, False),
        ),
        _social_proof_requirement_group(
            "maps_supervised_handoff",
            maps_status,
            "Яндекс/2ГИС handoff",
            "Yandex/2GIS handoff",
            _social_maps_proof_requirement_summary(maps_status, channel_readiness, controlled_count, manual_count, True),
            _social_maps_proof_requirement_summary(maps_status, channel_readiness, controlled_count, manual_count, False),
            _social_maps_proof_requirement_next_action(maps_status, True),
            _social_maps_proof_requirement_next_action(maps_status, False),
            _social_maps_proof_requirement_steps(maps_status, True),
            _social_maps_proof_requirement_steps(maps_status, False),
        ),
        _social_proof_requirement_group(
            "metrics_and_recommendation",
            metrics_status,
            "Метрики и заявки",
            "Metrics and leads",
            _social_metrics_proof_requirement_summary(metrics_status, runtime_alignment, workflow_counts, True),
            _social_metrics_proof_requirement_summary(metrics_status, runtime_alignment, workflow_counts, False),
            _social_metrics_proof_requirement_next_action(metrics_status, runtime_alignment, True),
            _social_metrics_proof_requirement_next_action(metrics_status, runtime_alignment, False),
            _social_metrics_proof_requirement_steps(metrics_status, True),
            _social_metrics_proof_requirement_steps(metrics_status, False),
        ),
    ]
    ready_groups = sum(1 for group in groups if str(group.get("state") or "") in {"ready", "complete"})
    attention_groups = sum(1 for group in groups if str(group.get("state") or "") in {"needs_setup", "needs_channel", "needs_manual_fallback"})
    if ready_groups == len(groups):
        status = "ready_for_live_proof"
    elif attention_groups:
        status = "needs_setup"
    else:
        status = "in_progress"
    return {
        "schema": "localos_social_proof_requirements_v1",
        "status": status,
        "ready_groups": ready_groups,
        "total_groups": len(groups),
        "groups": groups,
        "title_ru": "Что осталось для живого теста",
        "title_en": "What remains for the live proof",
        "summary_ru": _social_proof_requirements_summary(status, ready_groups, len(groups), True),
        "summary_en": _social_proof_requirements_summary(status, ready_groups, len(groups), False),
        "next_action_ru": _social_proof_requirements_next_action(groups, True),
        "next_action_en": _social_proof_requirements_next_action(groups, False),
        "external_publish_requires_approval": True,
        "browser_final_click_allowed": False,
        "maps_are_supervised_or_manual": True,
        "primary_metric_ru": "Заявки и обращения",
        "primary_metric_en": "Leads and inquiries",
    }

def _social_proof_requirement_group(
    key: str,
    state: str,
    title_ru: str,
    title_en: str,
    summary_ru: str,
    summary_en: str,
    next_action_ru: str,
    next_action_en: str,
    checklist_ru: list[str],
    checklist_en: list[str],
) -> dict[str, Any]:
    return {
        "key": key,
        "state": state,
        "title_ru": title_ru,
        "title_en": title_en,
        "summary_ru": summary_ru,
        "summary_en": summary_en,
        "next_action_ru": next_action_ru,
        "next_action_en": next_action_en,
        "checklist_ru": checklist_ru,
        "checklist_en": checklist_en,
    }

def _social_api_proof_requirement_status(
    first_api_publish_readiness: dict[str, Any],
    first_api_proof_gate: dict[str, Any],
    workflow_counts: dict[str, Any],
    due_count: int,
    external_publish_count: int,
) -> str:
    if bool(first_api_proof_gate.get("allowed")) and int(external_publish_count or 0) > 0:
        return "ready"
    if int(external_publish_count or 0) > 0 or int(due_count or 0) > 0:
        return "needs_run_once"
    if int(workflow_counts.get("queued_total") or 0) > 0:
        return "waiting_for_due_time"
    if int(workflow_counts.get("approved_not_queued") or 0) > 0:
        return "needs_queue"
    if int(workflow_counts.get("needs_review") or 0) > 0:
        return "needs_approval"
    if bool(first_api_publish_readiness.get("ready")):
        return "needs_post"
    return "needs_channel"

def _social_api_proof_requirement_summary(
    state: str,
    first_api_publish_readiness: dict[str, Any],
    first_api_proof_gate: dict[str, Any],
    is_ru: bool,
) -> str:
    platform = _social_proof_platform_label(first_api_publish_readiness, first_api_proof_gate)
    if state == "ready":
        return (
            f"{platform}: есть due API-пост, можно запускать один scoped цикл и проверять provider_post_id/provider_post_url."
            if is_ru
            else f"{platform}: a due API post exists; run one scoped cycle and verify provider_post_id/provider_post_url."
        )
    if state == "needs_run_once":
        return (
            "Есть due-публикации, но перед запуском проверьте live preflight и явное подтверждение."
            if is_ru
            else "There are due posts, but check live preflight and explicit confirmation before running."
        )
    if state == "waiting_for_due_time":
        return (
            "Пост уже в расписании, ждёт даты публикации или ручного scoped run-once."
            if is_ru
            else "A post is queued and waits for its due time or a manual scoped run-once."
        )
    if state == "needs_queue":
        return "Текст утверждён, но ещё не поставлен в расписание." if is_ru else "Copy is approved but not queued yet."
    if state == "needs_approval":
        return "Есть черновики: сначала preview, правки и human approval." if is_ru else "Drafts exist: first preview, edit, and human approval."
    if state == "needs_post":
        return (
            f"{platform} готов по ключам; подготовьте первый пост из контент-плана."
            if is_ru
            else f"{platform} is ready by keys; prepare the first content-plan post."
        )
    return (
        "Для первого proof подключите Telegram или VK: нужны token/chat_id или VK token/group_id/wall.post."
        if is_ru
        else "For the first proof, connect Telegram or VK: token/chat_id or VK token/group_id/wall.post are required."
    )

def _social_api_proof_requirement_next_action(
    state: str,
    first_api_publish_readiness: dict[str, Any],
    first_api_proof_gate: dict[str, Any],
    is_ru: bool,
) -> str:
    if state == "ready":
        return (
            "Запустите один scoped worker/run-once после подтверждения и проверьте provider proof."
            if is_ru
            else "Run one scoped worker/run-once after confirmation and check provider proof."
        )
    if state == "needs_run_once":
        return (
            "Откройте проверку запуска и выполните ограниченный run-once только для этого бизнеса."
            if is_ru
            else "Open launch check and run one scoped cycle only for this business."
        )
    if state == "waiting_for_due_time":
        return "Дождитесь scheduled_for или запустите scoped run-once." if is_ru else "Wait for scheduled_for or run a scoped cycle."
    if state == "needs_queue":
        return "Нажмите “Поставить в расписание” для утверждённого API-поста." if is_ru else "Click Queue for the approved API post."
    if state == "needs_approval":
        return "Откройте preview, сохраните правки и подтвердите текст." if is_ru else "Open preview, save edits, and approve the copy."
    if state == "needs_post":
        return str(first_api_publish_readiness.get("next_action_ru" if is_ru else "next_action_en") or "").strip()
    gate_action = str(first_api_proof_gate.get("next_action_ru" if is_ru else "next_action_en") or "").strip()
    return gate_action or (
        "Подключите Telegram/VK и повторите live API-проверку без публикации."
        if is_ru
        else "Connect Telegram/VK and rerun live API preflight without publishing."
    )

def _social_api_proof_requirement_steps(
    state: str,
    first_api_publish_readiness: dict[str, Any],
    is_ru: bool,
) -> list[str]:
    if state in {"ready", "needs_run_once"}:
        return [
            "Проверить launch preflight и business scope.",
            "Запустить один цикл только после явного подтверждения.",
            "Проверить provider_post_id/provider_post_url после публикации.",
        ] if is_ru else [
            "Check launch preflight and business scope.",
            "Run one cycle only after explicit confirmation.",
            "Verify provider_post_id/provider_post_url after publishing.",
        ]
    checklist = first_api_publish_readiness.get("first_post_checklist_ru" if is_ru else "first_post_checklist_en")
    if isinstance(checklist, list) and checklist:
        return [str(item or "").strip() for item in checklist if str(item or "").strip()]
    return [
        "Подключить Telegram или VK.",
        "Подготовить первый пост.",
        "Preview → approval → queue → proof.",
    ] if is_ru else [
        "Connect Telegram or VK.",
        "Prepare the first post.",
        "Preview → approval → queue → proof.",
    ]

def _social_maps_proof_requirement_status(
    channel_readiness: list[dict[str, Any]],
    controlled_count: int,
    manual_count: int,
) -> str:
    if int(controlled_count or 0) > 0:
        return "ready"
    map_channels = [
        item for item in channel_readiness
        if str(item.get("platform") or "").strip() in BROWSER_OR_MANUAL_PLATFORMS
    ]
    if any(str(item.get("status") or "").strip() == "supervised_ready" for item in map_channels):
        return "needs_map_post"
    if int(manual_count or 0) > 0:
        return "needs_manual_fallback"
    return "manual_available"

def _social_maps_proof_requirement_summary(
    state: str,
    channel_readiness: list[dict[str, Any]],
    controlled_count: int,
    manual_count: int,
    is_ru: bool,
) -> str:
    if state == "ready":
        return (
            f"Готово к controlled handoff: due задач для карт {int(controlled_count or 0)}."
            if is_ru
            else f"Ready for controlled handoff: due map tasks {int(controlled_count or 0)}."
        )
    if state == "needs_map_post":
        return (
            "OpenClaw browser-use выглядит доступным: подготовьте и поставьте в расписание пост для Яндекс/2ГИС."
            if is_ru
            else "OpenClaw browser-use looks available: prepare and queue a Yandex/2GIS post."
        )
    if state == "needs_manual_fallback":
        return (
            f"Есть ручные/заблокированные размещения: {int(manual_count or 0)}. Это не ломает весь план."
            if is_ru
            else f"Manual or blocked placements: {int(manual_count or 0)}. This does not break the whole plan."
        )
    labels = [
        str(item.get("platform_label") or "").strip()
        for item in channel_readiness
        if str(item.get("platform") or "").strip() in BROWSER_OR_MANUAL_PLATFORMS
    ]
    joined = ", ".join([label for label in labels if label])
    return (
        f"{joined or 'Яндекс/2ГИС'} пока в ручном/контролируемом режиме; финальный клик остаётся за человеком."
        if is_ru
        else f"{joined or 'Yandex/2GIS'} stays manual/supervised for now; the final click remains human-owned."
    )

def _social_maps_proof_requirement_next_action(state: str, is_ru: bool) -> str:
    if state == "ready":
        return (
            "Откройте controlled placement и проверьте, что задача останавливается перед финальной кнопкой."
            if is_ru
            else "Open controlled placement and verify that the task stops before final publish."
        )
    if state == "needs_map_post":
        return (
            "Подготовьте пост для Яндекс/2ГИС и поставьте его в расписание."
            if is_ru
            else "Prepare a Yandex/2GIS post and queue it."
        )
    if state == "needs_manual_fallback":
        return (
            "Используйте copy-ready текст, разместите вручную и отметьте публикацию в LocalOS."
            if is_ru
            else "Use the copy-ready text, publish manually, and mark it in LocalOS."
        )
    return (
        "Проверьте OpenClaw browser-use; если capability нет, продолжайте через manual handoff."
        if is_ru
        else "Check OpenClaw browser-use; if capability is absent, continue with manual handoff."
    )

def _social_maps_proof_requirement_steps(state: str, is_ru: bool) -> list[str]:
    if state == "ready":
        return [
            "Открыть controlled handoff.",
            "Проверить текст/медиа и target URL.",
            "Остановиться перед финальной кнопкой; финальный шаг подтверждает человек.",
        ] if is_ru else [
            "Open controlled handoff.",
            "Check copy/media and target URL.",
            "Stop before the final button; a human confirms the final step.",
        ]
    return [
        "Проверить OpenClaw browser-use capability.",
        "Подготовить map-specific текст.",
        "При сбое captcha/login/changed UI перейти в manual fallback.",
    ] if is_ru else [
        "Check OpenClaw browser-use capability.",
        "Prepare map-specific copy.",
        "If captcha/login/changed UI blocks the flow, move to manual fallback.",
    ]

def _social_metrics_proof_requirement_status(runtime_alignment: dict[str, Any], workflow_counts: dict[str, Any]) -> str:
    metrics_alignment = _json_dict(runtime_alignment.get("metrics"))
    published = int(workflow_counts.get("published") or 0)
    if published > 0 and bool(metrics_alignment.get("can_collect_this_business")):
        return "ready"
    if published > 0:
        return "needs_metrics_scope"
    return "waiting_for_publish"

def _social_metrics_proof_requirement_summary(
    state: str,
    runtime_alignment: dict[str, Any],
    workflow_counts: dict[str, Any],
    is_ru: bool,
) -> str:
    published = int(workflow_counts.get("published") or 0)
    if state == "ready":
        return (
            f"Есть опубликованные посты ({published}) и metrics worker может собирать этот бизнес."
            if is_ru
            else f"Published posts exist ({published}) and the metrics worker can collect this business."
        )
    if state == "needs_metrics_scope":
        return (
            f"Опубликовано постов: {published}. Осталось настроить scoped сбор метрик и отметить заявки/обращения."
            if is_ru
            else f"Published posts: {published}. Configure scoped metrics collection and record leads/inquiries."
        )
    metrics_alignment = _json_dict(runtime_alignment.get("metrics"))
    if bool(metrics_alignment.get("enabled")):
        return (
            "Сбор метрик включён, но сначала нужен опубликованный пост с provider proof."
            if is_ru
            else "Metrics collection is enabled, but first a published post with provider proof is needed."
        )
    return (
        "После первого proof включите сбор метрик и ручную разметку заявок/обращений."
        if is_ru
        else "After the first proof, enable metrics collection and manual lead/inquiry attribution."
    )

def _social_metrics_proof_requirement_next_action(
    state: str,
    runtime_alignment: dict[str, Any],
    is_ru: bool,
) -> str:
    if state == "ready":
        return (
            "Запустите сбор метрик, отметьте заявки/обращения и сформируйте рекомендацию на следующую неделю."
            if is_ru
            else "Run metrics collection, record leads/inquiries, and generate next-week recommendations."
        )
    if state == "needs_metrics_scope":
        alignment = _json_dict(runtime_alignment.get("metrics"))
        message = str(alignment.get("message_ru" if is_ru else "message_en") or "").strip()
        return message or (
            "Настройте SOCIAL_POST_METRICS_BUSINESS_ID для этого бизнеса."
            if is_ru
            else "Set SOCIAL_POST_METRICS_BUSINESS_ID for this business."
        )
    return (
        "Сначала доведите один API или supervised пост до published."
        if is_ru
        else "First get one API or supervised post to published."
    )

def _social_metrics_proof_requirement_steps(state: str, is_ru: bool) -> list[str]:
    if state == "ready":
        return [
            "Собрать API/manual metrics snapshot.",
            "Отметить lead или inquiry как главный сигнал.",
            "Сгенерировать next-week recommendation без авто-применения.",
        ] if is_ru else [
            "Collect an API/manual metrics snapshot.",
            "Record a lead or inquiry as the primary signal.",
            "Generate next-week recommendation without auto-apply.",
        ]
    return [
        "Дождаться первого published поста.",
        "Включить scoped metrics collector.",
        "Заявки/обращения учитывать выше охвата и лайков.",
    ] if is_ru else [
        "Wait for the first published post.",
        "Enable scoped metrics collector.",
        "Rank leads/inquiries above reach and likes.",
    ]

def _social_proof_platform_label(
    first_api_publish_readiness: dict[str, Any],
    first_api_proof_gate: dict[str, Any],
) -> str:
    candidate = _json_dict(first_api_proof_gate.get("candidate"))
    candidate_label = str(candidate.get("platform_label") or "").strip()
    if candidate_label:
        return candidate_label
    platform = first_api_publish_readiness.get("recommended_start_platform")
    if isinstance(platform, dict):
        label = str(platform.get("platform_label") or platform.get("platform") or "").strip()
        if label:
            return label
    return "Telegram/VK"

def _social_proof_requirements_summary(status: str, ready_groups: int, total_groups: int, is_ru: bool) -> str:
    if status == "ready_for_live_proof":
        return (
            "Все блоки готовы к живому proof-loop: публикация, handoff карт и сбор результата."
            if is_ru
            else "All blocks are ready for the live proof loop: publish, map handoff, and result collection."
        )
    if status == "needs_setup":
        return (
            f"Готово {int(ready_groups or 0)} из {int(total_groups or 0)} блоков; начните с Telegram/VK и не скрывайте ручной режим карт."
            if is_ru
            else f"{int(ready_groups or 0)} of {int(total_groups or 0)} blocks are ready; start with Telegram/VK and keep map manual mode explicit."
        )
    return (
        f"Готово {int(ready_groups or 0)} из {int(total_groups or 0)} блоков; следующий шаг зависит от текущей очереди."
        if is_ru
        else f"{int(ready_groups or 0)} of {int(total_groups or 0)} blocks are ready; the next step depends on the current queue."
    )

def _social_proof_requirements_next_action(groups: list[dict[str, Any]], is_ru: bool) -> str:
    for group in groups:
        if str(group.get("state") or "") not in {"ready", "complete"}:
            return str(group.get("next_action_ru" if is_ru else "next_action_en") or "").strip()
    return (
        "Запустите один scoped цикл, затем соберите метрики и заявки."
        if is_ru
        else "Run one scoped cycle, then collect metrics and leads."
    )

def _social_first_cycle_proof_packet(
    launch_gate: dict[str, Any],
    first_api_proof_gate: dict[str, Any],
    live_validation_checklist: list[dict[str, Any]],
    recommended_env: dict[str, Any],
    launch_runbook: dict[str, Any],
    runtime_alignment: dict[str, Any],
) -> dict[str, Any]:
    dispatch_env = _json_dict(recommended_env.get("dispatch"))
    metrics_env = _json_dict(recommended_env.get("metrics"))
    launch_allowed = bool(launch_gate.get("allowed"))
    api_proof_allowed = bool(first_api_proof_gate.get("allowed"))
    background_aligned = bool(first_api_proof_gate.get("background_worker_aligned"))
    checklist_total = len(live_validation_checklist or [])
    checklist_done = len([item for item in live_validation_checklist or [] if str(item.get("status") or "") == "done"])
    candidate = _json_dict(first_api_proof_gate.get("candidate"))
    dispatch_alignment = _json_dict(runtime_alignment.get("dispatch"))
    status = "ready_for_one_cycle" if launch_allowed else "not_ready"
    if launch_allowed and not api_proof_allowed:
        status = "ready_without_api_proof"
    if launch_allowed and api_proof_allowed and background_aligned:
        status = "ready_for_worker_or_button"
    return {
        "schema": "localos_social_first_cycle_proof_packet_v1",
        "status": status,
        "ready_to_run_once": launch_allowed,
        "api_proof_ready": api_proof_allowed,
        "background_worker_aligned": background_aligned,
        "ui_run_once_allowed": bool(first_api_proof_gate.get("ui_run_once_allowed")),
        "requires_human_confirmation": True,
        "external_publish_requires_approval": True,
        "external_publish_confirmation_phrase": _social_external_publish_confirmation_phrase(),
        "external_publish_confirmation_ru": (
            f"Если цикл может опубликовать API-посты, перед запуском нужно ввести фразу: {_social_external_publish_confirmation_phrase()}."
        ),
        "external_publish_confirmation_en": (
            f"If the cycle can publish API posts, type this phrase before running it: {_social_external_publish_confirmation_phrase()}."
        ),
        "browser_final_click_allowed": False,
        "maps_are_supervised_or_manual": True,
        "dispatch_business_id": str(dispatch_env.get("SOCIAL_POST_DISPATCH_BUSINESS_ID") or "").strip(),
        "metrics_business_id": str(metrics_env.get("SOCIAL_POST_METRICS_BUSINESS_ID") or "").strip(),
        "dispatch_env": dispatch_env,
        "metrics_env": metrics_env,
        "candidate_platform": str(candidate.get("platform") or "").strip(),
        "candidate_platform_label": str(candidate.get("platform_label") or "").strip(),
        "required_proof_fields": candidate.get("required_proof_fields") or ["provider_post_id", "provider_post_url"],
        "checklist_done": checklist_done,
        "checklist_total": checklist_total,
        "run_once_action_ru": (
            "Нажмите «Запустить один цикл сейчас» только после проверки: посты подтверждены, business scope указан, блокеров нет."
            if launch_allowed
            else "Сначала подготовьте due-посты, снимите блокеры и повторите проверку запуска."
        ),
        "run_once_action_en": (
            "Click “Run one cycle now” only after checking: posts are approved, business scope is set, and blockers are gone."
            if launch_allowed
            else "Prepare due posts, resolve blockers, and run launch preflight again first."
        ),
        "after_run_checks_ru": [
            "Проверьте логи [SOCIAL_POST_DISPATCH] и количество picked/published/supervised/manual/failed.",
            "Для API-поста проверьте provider_post_id/provider_post_url или понятную ошибку.",
            "Для Яндекс/2ГИС проверьте пакет контролируемого размещения; финальный клик остаётся за человеком.",
            "После публикации соберите реакции и отметьте заявки/обращения перед изменением следующего плана.",
        ],
        "after_run_checks_en": [
            "Check [SOCIAL_POST_DISPATCH] logs and picked/published/supervised/manual/failed counts.",
            "For the API post, verify provider_post_id/provider_post_url or a clear error.",
            "For Yandex/2GIS, check the supervised placement packet; the final click stays human-controlled.",
            "After publishing, collect reactions and record leads/inquiries before changing the next plan.",
        ],
        "blocked_reason_ru": "" if launch_allowed else str(launch_runbook.get("blocked_reason_ru") or launch_gate.get("next_action_ru") or "").strip(),
        "blocked_reason_en": "" if launch_allowed else str(launch_runbook.get("blocked_reason_en") or launch_gate.get("next_action_en") or "").strip(),
        "runtime_status": str(dispatch_alignment.get("status") or "").strip(),
    }

def _social_live_validation_checklist(
    production_readiness: dict[str, Any],
    launch_gate: dict[str, Any],
    first_api_proof_gate: dict[str, Any],
    due_count: int,
    external_publish_count: int,
    controlled_count: int,
    manual_count: int,
) -> list[dict[str, Any]]:
    ready_for_cycle = bool(production_readiness.get("ready_for_first_scoped_cycle"))
    safe_to_enable = bool(production_readiness.get("safe_to_enable_scoped_dispatch"))
    launch_allowed = bool(launch_gate.get("allowed"))
    api_ready = bool(first_api_proof_gate.get("allowed"))
    has_due = int(due_count or 0) > 0
    has_api = int(external_publish_count or 0) > 0
    has_maps_or_manual = int(controlled_count or 0) > 0 or int(manual_count or 0) > 0
    return [
        {
            "key": "open_real_plan",
            "status": "done" if has_due else "current",
            "label_ru": "Открыт реальный контент-план",
            "label_en": "Real content plan is open",
            "detail_ru": (
                f"На текущую дату найдено постов: {int(due_count or 0)}."
                if has_due
                else "Подготовьте, подтвердите и поставьте в расписание 1-2 темы из реального плана."
            ),
            "detail_en": (
                f"Due posts found: {int(due_count or 0)}."
                if has_due
                else "Prepare, approve, and queue 1-2 topics from a real plan."
            ),
        },
        {
            "key": "ready_to_run_one_cycle",
            "status": "done" if ready_for_cycle else ("current" if safe_to_enable and launch_allowed else "pending"),
            "label_ru": "Можно проверить один цикл",
            "label_en": "One-cycle check is possible",
            "detail_ru": (
                "Исполнитель уже ограничен этим бизнесом; можно запускать один цикл после подтверждения."
                if ready_for_cycle
                else "Перед запуском ограничьте исполнителя текущим бизнесом и проверьте блокеры."
            ),
            "detail_en": (
                "The worker is already scoped to this business; one cycle can run after confirmation."
                if ready_for_cycle
                else "Before launch, scope the worker to this business and check blockers."
            ),
        },
        {
            "key": "api_proof_after_run",
            "status": "current" if api_ready and has_api else ("pending" if has_api else "attention"),
            "label_ru": "API-proof после запуска",
            "label_en": "API proof after launch",
            "detail_ru": (
                "После цикла проверьте provider_post_id/provider_post_url или понятную ошибку."
                if has_api
                else "В первом живом прогоне нет API-поста; подключите Telegram/VK или другой API-канал."
            ),
            "detail_en": (
                "After the cycle, check provider_post_id/provider_post_url or a clear error."
                if has_api
                else "There is no API post in the first live run; connect Telegram/VK or another API channel."
            ),
        },
        {
            "key": "maps_supervised_not_autopublish",
            "status": "current" if has_maps_or_manual else "pending",
            "label_ru": "Карты не автопубликуются",
            "label_en": "Maps do not autopublish",
            "detail_ru": (
                f"Контролируемо: {int(controlled_count or 0)}, вручную: {int(manual_count or 0)}. Финальный клик остаётся за человеком."
                if has_maps_or_manual
                else "Добавьте Яндекс/2ГИС в выбранный план, чтобы проверить контролируемое или ручное размещение."
            ),
            "detail_en": (
                f"Supervised: {int(controlled_count or 0)}, manual: {int(manual_count or 0)}. The final click stays human-controlled."
                if has_maps_or_manual
                else "Add Yandex/2GIS to the selected plan to verify supervised or manual placement."
            ),
        },
        {
            "key": "collect_results_next",
            "status": "pending",
            "label_ru": "После публикации собрать результат",
            "label_en": "Collect results after publishing",
            "detail_ru": "После первого цикла отметьте заявки/обращения и пересчитайте рекомендации следующего плана.",
            "detail_en": "After the first cycle, record leads/inquiries and recalculate next-plan recommendations.",
        },
    ]

def _empty_social_launch_rehearsal() -> dict[str, Any]:
    return {
        "schema": "localos_social_publish_rehearsal_bulk_v1",
        "dry_run": True,
        "external_publish_performed": False,
        "provider_write_performed": False,
        "rehearsals": [],
        "failed": [],
        "summary": {
            "status": "empty",
            "total": 0,
            "ready": 0,
            "blocked": 0,
            "failed": 0,
            "api_ready": 0,
            "supervised_ready": 0,
            "manual_or_blocked": 0,
            "external_publish_performed": False,
            "provider_write_performed": False,
            "browser_final_click_allowed": False,
            "message_ru": "Нет запланированных постов на текущую дату для проверки запуска.",
            "message_en": "No due queued posts to rehearse.",
            "next_action_ru": "Сначала подтвердите посты, поставьте их в расписание и дождитесь даты публикации.",
            "next_action_en": "Approve posts, queue them, and wait for the due date first.",
        },
    }

def _social_launch_rehearsal_from_preview(user_id: str, dispatch_preview: dict[str, Any]) -> dict[str, Any]:
    items = dispatch_preview.get("items") if isinstance(dispatch_preview.get("items"), list) else []
    post_ids = [
        str(item.get("id") or "").strip()
        for item in items
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    ]
    if not post_ids:
        return _empty_social_launch_rehearsal()
    try:
        return rehearse_social_posts_publish(user_id, post_ids)
    except Exception:
        error = str(sys.exc_info()[1])
        payload = _empty_social_launch_rehearsal()
        payload["failed"] = [{"id": "", "error": error}]
        payload["summary"] = {
            **payload["summary"],
            "status": "error",
            "failed": 1,
            "manual_or_blocked": 1,
            "message_ru": f"Проверка постов на текущую дату не прошла: {error}",
            "message_en": f"Due-post rehearsal failed: {error}",
            "next_action_ru": "Проверьте доступ к постам на текущую дату и повторите проверку запуска.",
            "next_action_en": "Check access to due posts and run launch preflight again.",
        }
        return payload

def _social_first_cycle_launch_gate(
    production_readiness: dict[str, Any],
    due_count: int,
    external_publish_count: int,
    controlled_count: int,
    manual_count: int,
    skipped_no_access: int,
) -> dict[str, Any]:
    blockers = production_readiness.get("blockers") if isinstance(production_readiness.get("blockers"), list) else []
    allowed = int(due_count or 0) > 0 and int(skipped_no_access or 0) == 0 and not blockers
    if allowed and int(external_publish_count or 0) > 0:
        status = "ready_with_api_publish"
    elif allowed and int(controlled_count or 0) > 0:
        status = "ready_for_supervised_only"
    elif allowed and int(manual_count or 0) > 0:
        status = "ready_for_manual_only"
    elif int(due_count or 0) <= 0:
        status = "no_due_posts"
    else:
        status = "blocked"
    return {
        "schema": "localos_social_first_cycle_launch_gate_v1",
        "status": status,
        "allowed": bool(allowed),
        "requires_human_confirmation": True,
        "dry_run_completed": True,
        "external_publish_requires_approval": True,
        "external_publish_confirmation_phrase": _social_external_publish_confirmation_phrase(),
        "browser_final_click_allowed": False,
        "maps_are_supervised_or_manual": True,
        "due_posts": int(due_count or 0),
        "api_posts": int(external_publish_count or 0),
        "supervised_posts": int(controlled_count or 0),
        "manual_posts": int(manual_count or 0),
        "blocked_posts": len(blockers) + int(skipped_no_access or 0),
        "title_ru": _social_first_cycle_launch_gate_title(status, True),
        "title_en": _social_first_cycle_launch_gate_title(status, False),
        "summary_ru": _social_first_cycle_launch_gate_summary(
            status,
            external_publish_count,
            controlled_count,
            manual_count,
            True,
        ),
        "summary_en": _social_first_cycle_launch_gate_summary(
            status,
            external_publish_count,
            controlled_count,
            manual_count,
            False,
        ),
        "next_action_ru": _social_first_cycle_launch_gate_next_action(status, blockers, True),
        "next_action_en": _social_first_cycle_launch_gate_next_action(status, blockers, False),
    }

def _social_first_cycle_launch_gate_title(status: str, is_ru: bool) -> str:
    if status == "ready_with_api_publish":
        return "Можно запускать: есть API-публикации" if is_ru else "Ready to run: API posts included"
    if status == "ready_for_supervised_only":
        return "Можно запускать: только контролируемые задачи" if is_ru else "Ready to run: supervised tasks only"
    if status == "ready_for_manual_only":
        return "Можно запускать: только ручной режим" if is_ru else "Ready to run: manual fallback only"
    if status == "no_due_posts":
        return "Нет постов на текущую дату для запуска" if is_ru else "No due posts to run"
    return "Запуск пока заблокирован" if is_ru else "Launch is blocked"

def _social_first_cycle_launch_gate_summary(
    status: str,
    external_publish_count: int,
    controlled_count: int,
    manual_count: int,
    is_ru: bool,
) -> str:
    if status == "ready_with_api_publish":
        return (
            f"После подтверждения один ограниченный цикл может опубликовать API-посты: {int(external_publish_count or 0)}; карты останутся контролируемыми или ручными."
            if is_ru
            else f"After confirmation, one scoped cycle may publish API posts: {int(external_publish_count or 0)}; maps stay supervised/manual."
        )
    if status == "ready_for_supervised_only":
        return (
            f"API-публикаций нет; цикл создаст контролируемые задачи: {int(controlled_count or 0)}."
            if is_ru
            else f"No API publishing; the cycle will create supervised tasks: {int(controlled_count or 0)}."
        )
    if status == "ready_for_manual_only":
        return (
            f"API и browser-use не готовы; цикл переведёт посты в ручной режим: {int(manual_count or 0)}."
            if is_ru
            else f"API and browser-use are not ready; the cycle will move posts to manual fallback: {int(manual_count or 0)}."
        )
    if status == "no_due_posts":
        return (
            "Сначала утвердите посты, поставьте их в расписание и дождитесь даты публикации."
            if is_ru
            else "Approve posts, queue them, and wait for the due date first."
        )
    return (
        "Снимите блокеры preflight: запуск не должен обходить ключи, права или business scope."
        if is_ru
        else "Resolve preflight blockers: launch must not bypass keys, permissions, or business scope."
    )

def _social_first_cycle_launch_gate_next_action(status: str, blockers: list[Any], is_ru: bool) -> str:
    if status in {"ready_with_api_publish", "ready_for_supervised_only", "ready_for_manual_only"}:
        return (
            "Нажимайте запуск только после проверки dry-run; затем сверяйте логи и статусы постов."
            if is_ru
            else "Run only after checking the dry-run; then verify logs and post statuses."
        )
    if blockers:
        first = blockers[0] if isinstance(blockers[0], dict) else {}
        return str(first.get("action_ru" if is_ru else "action_en") or "").strip()
    return (
        "Подготовьте, подтвердите и поставьте хотя бы один пост в расписание."
        if is_ru
        else "Prepare, approve, and queue at least one post."
    )

def _social_first_api_proof_gate(
    launch_gate: dict[str, Any],
    candidate: dict[str, Any],
    api_preflight_blocked_due_posts: list[dict[str, Any]],
    runtime_alignment: dict[str, Any],
) -> dict[str, Any]:
    candidate_ready = bool(candidate.get("ready"))
    launch_allowed = bool(launch_gate.get("allowed"))
    api_blocked = len(api_preflight_blocked_due_posts or []) > 0
    dispatch_alignment = (
        runtime_alignment.get("dispatch")
        if isinstance(runtime_alignment.get("dispatch"), dict)
        else {}
    )
    background_worker_aligned = bool(dispatch_alignment.get("can_process_this_business"))
    ui_run_once_allowed = bool(candidate_ready and launch_allowed and not api_blocked)
    if api_blocked:
        status = "api_preflight_blocked"
    elif not candidate_ready:
        status = "no_due_api_candidate"
    elif not launch_allowed:
        status = "launch_gate_blocked"
    elif not background_worker_aligned:
        status = "ready_for_ui_run_once"
    else:
        status = "ready_for_worker_or_ui"
    return {
        "schema": "localos_social_first_api_proof_gate_v1",
        "status": status,
        "allowed": ui_run_once_allowed,
        "ui_run_once_allowed": ui_run_once_allowed,
        "background_worker_aligned": background_worker_aligned,
        "requires_human_confirmation": True,
        "external_publish_requires_approval": True,
        "external_publish_performed": False,
        "browser_final_click_allowed": False,
        "candidate": candidate,
        "blocked_posts": len(api_preflight_blocked_due_posts or []),
        "title_ru": _social_first_api_proof_gate_title(status, True),
        "title_en": _social_first_api_proof_gate_title(status, False),
        "summary_ru": _social_first_api_proof_gate_summary(status, candidate, True),
        "summary_en": _social_first_api_proof_gate_summary(status, candidate, False),
        "next_action_ru": _social_first_api_proof_gate_next_action(
            status,
            launch_gate,
            api_preflight_blocked_due_posts,
            True,
        ),
        "next_action_en": _social_first_api_proof_gate_next_action(
            status,
            launch_gate,
            api_preflight_blocked_due_posts,
            False,
        ),
    }

def _social_first_api_proof_gate_title(status: str, is_ru: bool) -> str:
    if status == "ready_for_worker_or_ui":
        return "API-proof готов к запуску" if is_ru else "API proof is ready to run"
    if status == "ready_for_ui_run_once":
        return "Можно запустить из LocalOS" if is_ru else "Can run from LocalOS"
    if status == "api_preflight_blocked":
        return "API-proof заблокирован preflight" if is_ru else "API proof is blocked by preflight"
    if status == "no_due_api_candidate":
        return "Нет API-поста для proof" if is_ru else "No API post for proof"
    return "Сначала откройте общий запуск" if is_ru else "Open the general launch gate first"

def _social_first_api_proof_gate_summary(
    status: str,
    candidate: dict[str, Any],
    is_ru: bool,
) -> str:
    label = str(candidate.get("platform_label") or candidate.get("platform") or "").strip()
    if status == "ready_for_worker_or_ui":
        return (
            f"{label}: можно дождаться исполнителя или запустить один ограниченный цикл из LocalOS; подтверждение должно появиться как provider_post_id/provider_post_url."
            if is_ru
            else f"{label}: wait for the worker or run one scoped cycle from LocalOS; proof must appear as provider_post_id/provider_post_url."
        )
    if status == "ready_for_ui_run_once":
        return (
            f"{label}: можно запустить один ограниченный цикл из LocalOS; после запуска нужен provider_post_id/provider_post_url. Фоновый исполнитель для этого бизнеса ещё не выровнен."
            if is_ru
            else f"{label}: one scoped cycle can run from LocalOS; provider_post_id/provider_post_url is required after launch. The background worker is not aligned to this business yet."
        )
    if status == "api_preflight_blocked":
        return (
            "Live API-проверка нашла API-пост на текущую дату с неготовым каналом; публикация не должна стартовать."
            if is_ru
            else "Live API preflight found a due API post with a channel that is not ready; publishing must not start."
        )
    if status == "no_due_api_candidate":
        return (
            "Чтобы доказать API-loop, нужен Telegram/VK/API-пост на текущую дату: подтверждённый, в расписании и с готовым каналом."
            if is_ru
            else "To prove the API loop, create a due Telegram/VK/API post: approved, queued, and with a ready channel."
        )
    return (
        "Общий launch gate пока закрыт; API-proof нельзя запускать отдельно."
        if is_ru
        else "The general launch gate is closed; API proof cannot run separately."
    )

def _social_first_api_proof_gate_next_action(
    status: str,
    launch_gate: dict[str, Any],
    api_preflight_blocked_due_posts: list[dict[str, Any]],
    is_ru: bool,
) -> str:
    if status == "ready_for_worker_or_ui":
        return (
            "Запустите один ограниченный цикл или дождитесь исполнителя, затем проверьте provider_post_id/provider_post_url и соберите реакции/заявки."
            if is_ru
            else "Run one scoped cycle or wait for the worker, then check provider_post_id/provider_post_url and collect reactions/leads."
        )
    if status == "ready_for_ui_run_once":
        return (
            "Нажмите запуск одного ограниченного цикла; для фонового режима отдельно выровняйте SOCIAL_POST_DISPATCH_BUSINESS_ID."
            if is_ru
            else "Run one scoped cycle; for background mode, align SOCIAL_POST_DISPATCH_BUSINESS_ID separately."
        )
    if status == "api_preflight_blocked":
        first = api_preflight_blocked_due_posts[0] if api_preflight_blocked_due_posts else {}
        action = str(first.get("next_action_ru" if is_ru else "next_action_en") or "").strip()
        return action or (
            "Исправьте ключи, права или локацию канала и повторите live API-проверку."
            if is_ru
            else "Fix channel keys/permissions/location and rerun live API preflight."
        )
    if status == "no_due_api_candidate":
        return (
            "Подготовьте один Telegram/VK/API-пост, подтвердите текст и поставьте его в расписание на сейчас или ближайшее время."
            if is_ru
            else "Prepare one Telegram/VK/API post, approve the copy, and queue it for now or the nearest time."
        )
    return str(launch_gate.get("next_action_ru" if is_ru else "next_action_en") or "").strip()

def _social_production_readiness(
    status: str,
    safe_to_enable: bool,
    due_count: int,
    external_publish_count: int,
    controlled_count: int,
    manual_count: int,
    skipped_no_access: int,
    api_preflight_blocked_due_posts: list[dict[str, Any]],
    first_api_publish_readiness: dict[str, Any],
    runtime_alignment: dict[str, Any],
    workflow_stage_counts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    workflow_counts = workflow_stage_counts if isinstance(workflow_stage_counts, dict) else {}

    if int(due_count or 0) <= 0:
        blockers.append(_social_no_due_posts_readiness_issue(workflow_counts))
    if int(skipped_no_access or 0) > 0:
        blockers.append(
            _social_readiness_issue(
                "skipped_no_access",
                "Есть посты вне доступа",
                "Some posts are outside access",
                "Запустите проверку пользователем с доступом к бизнесу или уточните business scope.",
                "Run the check as a user with business access or narrow the business scope.",
                "permissions",
                int(skipped_no_access or 0),
            )
        )
    if api_preflight_blocked_due_posts:
        blockers.append(
            _social_readiness_issue(
                "api_preflight_blocked",
                "API-канал не готов",
                "API channel is not ready",
                "Исправьте ключи, права или локацию у заблокированного API-поста на текущую дату.",
                "Fix keys, permissions, or location for the blocked due API post.",
                "channels",
                len(api_preflight_blocked_due_posts),
            )
        )
    if not bool(first_api_publish_readiness.get("ready")):
        warnings.append(
            _social_readiness_issue(
                "no_api_channel_ready",
                "Нет готового API-канала",
                "No API channel is ready",
                str(first_api_publish_readiness.get("next_action_ru") or "").strip()
                or "Подключите Telegram или VK для первого API-поста.",
                str(first_api_publish_readiness.get("next_action_en") or "").strip()
                or "Connect Telegram or VK for the first API post.",
                "channels",
            )
        )
    dispatch_alignment = _json_dict(runtime_alignment.get("dispatch"))
    if not bool(dispatch_alignment.get("can_process_this_business")):
        warnings.append(
            _social_readiness_issue(
                "dispatch_runtime_not_aligned",
                "Worker ещё не настроен на этот бизнес",
                "Worker is not aligned to this business yet",
                str(runtime_alignment.get("next_action_ru") or "").strip(),
                str(runtime_alignment.get("next_action_en") or "").strip(),
                "исполнитель",
            )
        )
    metrics_alignment = _json_dict(runtime_alignment.get("metrics"))
    if not bool(metrics_alignment.get("can_collect_this_business")):
        warnings.append(
            _social_readiness_issue(
                "metrics_runtime_not_aligned",
                "Сбор реакций ещё не замкнут",
                "Metrics collection is not aligned yet",
                "Для learning loop включите сбор реакций с тем же business scope.",
                "For the learning loop, enable metrics with the same business scope.",
                "metrics",
            )
        )
    if int(controlled_count or 0) > 0:
        warnings.append(
            _social_readiness_issue(
                "maps_supervised_required",
                "Карты пойдут через контроль",
                "Maps require supervised placement",
                "Яндекс/2ГИС не автопубликуются: проверьте supervised/manual задачу перед финальным размещением.",
                "Yandex/2GIS do not autopublish: review supervised/manual placement before the final action.",
                "maps",
                int(controlled_count or 0),
            )
        )
    if int(manual_count or 0) > 0:
        warnings.append(
            _social_readiness_issue(
                "manual_handoff_exists",
                "Есть ручной режим",
                "Manual fallback exists",
                "Откройте ручные посты, разместите их вручную или подключите нужный канал.",
                "Open manual posts, publish manually, or connect the required channel.",
                "manual",
                int(manual_count or 0),
            )
        )

    if blockers:
        readiness_status = "blocked"
    elif safe_to_enable and bool(dispatch_alignment.get("can_process_this_business")):
        readiness_status = "ready"
    elif safe_to_enable:
        readiness_status = "ready_after_worker_scope"
    else:
        readiness_status = "prepare_first"

    return {
        "schema": "localos_social_production_readiness_v1",
        "status": readiness_status,
        "ready_for_first_scoped_cycle": readiness_status == "ready",
        "safe_to_enable_scoped_dispatch": bool(safe_to_enable),
        "due_posts": int(due_count or 0),
        "api_due_posts": int(external_publish_count or 0),
        "controlled_due_posts": int(controlled_count or 0),
        "manual_due_posts": int(manual_count or 0),
        "workflow_stage_counts": workflow_counts,
        "worker_idle_reason": _social_worker_idle_reason(workflow_counts),
        "blockers": blockers,
        "warnings": warnings[:6],
        "title_ru": _social_production_readiness_title(readiness_status, True),
        "title_en": _social_production_readiness_title(readiness_status, False),
        "summary_ru": _social_production_readiness_summary(readiness_status, blockers, warnings, True),
        "summary_en": _social_production_readiness_summary(readiness_status, blockers, warnings, False),
        "next_action_ru": _social_production_readiness_next_action(readiness_status, blockers, warnings, True),
        "next_action_en": _social_production_readiness_next_action(readiness_status, blockers, warnings, False),
        "external_publish_requires_approval": True,
        "browser_final_click_allowed": False,
        "maps_are_supervised_or_manual": True,
}

def _social_no_due_posts_readiness_issue(workflow_counts: dict[str, Any]) -> dict[str, Any]:
    counts = workflow_counts if isinstance(workflow_counts, dict) else {}
    if int(counts.get("needs_review") or 0) > 0:
        return _social_readiness_issue(
            "posts_need_review",
            "Посты ждут проверки",
            "Posts need review",
            "Откройте предпросмотр, проверьте тексты и нажмите «Подтвердить». После этого поставьте их в расписание.",
            "Open preview, review the copy, and click Approve. Then queue them on schedule.",
            "review",
            int(counts.get("needs_review") or 0),
        )
    if int(counts.get("approved_not_queued") or 0) > 0:
        return _social_readiness_issue(
            "posts_approved_not_queued",
            "Посты утверждены, но не в расписании",
            "Posts are approved but not queued",
            "Поставьте утверждённые посты в расписание; worker возьмёт только queued-публикации по дате.",
            "Queue approved posts on schedule; the worker only picks queued due publications.",
            "queue",
            int(counts.get("approved_not_queued") or 0),
        )
    if int(counts.get("queued_future") or 0) > 0:
        return _social_readiness_issue(
            "posts_queued_for_future",
            "Посты запланированы на будущую дату",
            "Posts are queued for a future date",
            "Дождитесь даты публикации или измените расписание у тестового поста перед proof-запуском.",
            "Wait for the publish date or adjust the test post schedule before the proof run.",
            "schedule",
            int(counts.get("queued_future") or 0),
        )
    if int(counts.get("total") or 0) > 0:
        return _social_readiness_issue(
            "posts_not_ready_for_worker",
            "Посты есть, но worker их не берёт",
            "Posts exist, but the worker cannot pick them",
            "Проверьте статусы постов: для worker нужны approved → queued и scheduled_for <= now.",
            "Check post statuses: the worker needs approved → queued and scheduled_for <= now.",
            "queue",
            int(counts.get("total") or 0),
        )
    return _social_readiness_issue(
        "no_due_posts",
        "Нет постов на текущую дату",
        "No due posts",
        "Подготовьте посты, утвердите их и поставьте в расписание.",
        "Prepare posts, approve them, and queue them on schedule.",
        "queue",
    )

def _social_worker_idle_reason(workflow_counts: dict[str, Any]) -> dict[str, Any]:
    counts = workflow_counts if isinstance(workflow_counts, dict) else {}
    if int(counts.get("queued_due") or 0) > 0:
        return {
            "schema": "localos_social_worker_idle_reason_v1",
            "status": "has_due_queued_posts",
            "title_ru": "Worker должен подобрать due-посты",
            "title_en": "Worker should pick due posts",
            "next_action_ru": "Проверьте dispatch dry-run и worker logs.",
            "next_action_en": "Check dispatch dry-run and worker logs.",
            "count": int(counts.get("queued_due") or 0),
        }
    if int(counts.get("needs_review") or 0) > 0:
        return {
            "schema": "localos_social_worker_idle_reason_v1",
            "status": "waiting_for_review",
            "title_ru": "Worker ждёт проверки текстов",
            "title_en": "Worker is waiting for copy review",
            "next_action_ru": "Откройте предпросмотр, проверьте тексты и подтвердите посты.",
            "next_action_en": "Open preview, review copy, and approve posts.",
            "count": int(counts.get("needs_review") or 0),
        }
    if int(counts.get("approved_not_queued") or 0) > 0:
        return {
            "schema": "localos_social_worker_idle_reason_v1",
            "status": "waiting_for_queue",
            "title_ru": "Worker ждёт постановки в расписание",
            "title_en": "Worker is waiting for queueing",
            "next_action_ru": "Поставьте утверждённые посты в расписание.",
            "next_action_en": "Queue approved posts on schedule.",
            "count": int(counts.get("approved_not_queued") or 0),
        }
    if int(counts.get("queued_future") or 0) > 0:
        return {
            "schema": "localos_social_worker_idle_reason_v1",
            "status": "waiting_for_publish_date",
            "title_ru": "Worker ждёт дату публикации",
            "title_en": "Worker is waiting for the publish date",
            "next_action_ru": "Дождитесь scheduled_for или измените дату у тестовой публикации.",
            "next_action_en": "Wait for scheduled_for or adjust the test post date.",
            "count": int(counts.get("queued_future") or 0),
        }
    if int(counts.get("total") or 0) > 0:
        return {
            "schema": "localos_social_worker_idle_reason_v1",
            "status": "no_pickable_posts",
            "title_ru": "Worker не видит подходящих постов",
            "title_en": "Worker has no pickable posts",
            "next_action_ru": "Проверьте статусы: нужны approved → queued и дата не позже текущей.",
            "next_action_en": "Check statuses: posts need approved → queued and a due date not later than now.",
            "count": int(counts.get("total") or 0),
        }
    return {
        "schema": "localos_social_worker_idle_reason_v1",
        "status": "no_posts",
        "title_ru": "Посты ещё не подготовлены",
        "title_en": "Posts are not prepared yet",
        "next_action_ru": "Подготовьте каналы из контент-плана.",
        "next_action_en": "Prepare channels from the content plan.",
        "count": 0,
    }

def _social_readiness_issue(
    key: str,
    label_ru: str,
    label_en: str,
    action_ru: str,
    action_en: str,
    area: str,
    count: int = 0,
) -> dict[str, Any]:
    return {
        "key": key,
        "area": area,
        "count": int(count or 0),
        "label_ru": label_ru,
        "label_en": label_en,
        "action_ru": action_ru,
        "action_en": action_en,
    }
