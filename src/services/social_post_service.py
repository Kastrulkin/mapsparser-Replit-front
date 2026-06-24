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
from core.telegram_network import telegram_urlopen
from core.telegram_token_store import decode_telegram_bot_token
from core.helpers import get_business_owner_id
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


def prepare_social_posts_for_item(user_id: str, item_id: str, platforms: list[str] | None = None) -> dict[str, Any]:
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
        db.conn.commit()
        return {
            "posts": created_or_updated,
            "summary": _summary_for_posts(created_or_updated),
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


def _social_production_readiness_title(status: str, is_ru: bool) -> str:
    if status == "ready":
        return "Можно запускать первый ограниченный цикл" if is_ru else "Ready for the first scoped cycle"
    if status == "ready_after_worker_scope":
        return "Посты готовы, настройте бизнес для исполнителя" if is_ru else "Posts are ready; set worker scope"
    if status == "blocked":
        return "Сначала снять блокеры запуска" if is_ru else "Resolve launch blockers first"
    return "Сначала подготовить очередь" if is_ru else "Prepare the queue first"


def _social_production_readiness_summary(
    status: str,
    blockers: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    is_ru: bool,
) -> str:
    if status == "ready":
        return (
            "Посты на текущую дату готовы: API выйдет только после подтверждения, карты останутся контролируемыми или ручными."
            if is_ru
            else "Due posts are ready: API publishes only after approval, maps stay supervised/manual."
        )
    if status == "ready_after_worker_scope":
        return (
            "Очередь готова, но исполнитель ещё не смотрит на этот бизнес. Включите ограниченный запуск перед первым циклом."
            if is_ru
            else "The queue is ready, but runtime is not scoped to this business yet. Enable scoped worker before the first cycle."
        )
    if status == "blocked":
        first = blockers[0] if blockers else {}
        return (
            f"Запуск остановлен: {first.get('label_ru') or 'есть блокер'}."
            if is_ru
            else f"Launch is blocked: {first.get('label_en') or 'there is a blocker'}."
        )
    if warnings:
        first = warnings[0]
        return (
            f"Пока не готово к production loop: {first.get('label_ru') or 'нужна настройка'}."
            if is_ru
            else f"Not ready for the production loop yet: {first.get('label_en') or 'setup is needed'}."
        )
    return (
        "Подготовьте посты из контент-плана, проверьте предпросмотр, утвердите и поставьте в расписание."
        if is_ru
        else "Prepare posts from the content plan, review preview, approve, and queue them."
    )


def _social_production_readiness_next_action(
    status: str,
    blockers: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    is_ru: bool,
) -> str:
    if blockers:
        return str(blockers[0].get("action_ru" if is_ru else "action_en") or "").strip()
    if status == "ready_after_worker_scope":
        return (
            "Включите исполнителя только с SOCIAL_POST_DISPATCH_BUSINESS_ID текущего бизнеса и проверьте один цикл."
            if is_ru
            else "Enable the worker only with this business SOCIAL_POST_DISPATCH_BUSINESS_ID and check one cycle."
        )
    if status == "ready":
        return (
            "Запустите один ограниченный цикл, затем проверьте подтверждение провайдера, контролируемые задачи и ручной режим."
            if is_ru
            else "Run one scoped cycle, then check provider proof, supervised tasks, and manual fallback."
        )
    if warnings:
        return str(warnings[0].get("action_ru" if is_ru else "action_en") or "").strip()
    return (
        "Начните с подготовки каналов из выбранных тем контент-плана."
        if is_ru
        else "Start by preparing channels from selected content-plan topics."
    )


def _social_first_api_publish_readiness(
    channel_readiness: list[dict[str, Any]],
    api_preflight: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    live_items = [
        item for item in (api_preflight or [])
        if str(item.get("platform") or "").strip()
    ]
    if live_items:
        api_items = live_items
        source = "live_api_preflight"
    else:
        api_items = [
            item for item in channel_readiness
            if str(item.get("publish_mode") or "").strip() == "api"
        ]
        source = "channel_readiness"

    ready_items = [item for item in api_items if bool(item.get("ready"))]
    blocked_items = [item for item in api_items if not bool(item.get("ready"))]
    ready_platforms = [
        {
            "platform": str(item.get("platform") or "").strip(),
            "platform_label": str(item.get("platform_label") or platform_label(str(item.get("platform") or ""))).strip(),
            "status": str(item.get("status") or "ready").strip(),
        }
        for item in ready_items
    ]
    blocked_platforms = [
        {
            "platform": str(item.get("platform") or "").strip(),
            "platform_label": str(item.get("platform_label") or platform_label(str(item.get("platform") or ""))).strip(),
            "status": str(item.get("status") or "needs_attention").strip(),
            "message_ru": str(item.get("message_ru") or "").strip(),
            "message_en": str(item.get("message_en") or "").strip(),
            "next_action_ru": str(item.get("next_action_ru") or "").strip(),
            "next_action_en": str(item.get("next_action_en") or "").strip(),
        }
        for item in blocked_items
    ]

    if not api_items:
        status = "no_api_channels"
    elif ready_items and not blocked_items:
        status = "all_api_channels_ready"
    elif ready_items:
        status = "partial_api_ready"
    else:
        status = "no_api_ready"
    fast_start_ready_platforms = [
        item for item in ready_platforms
        if str(item.get("platform") or "").strip() in FIRST_API_PROOF_PLATFORMS
    ]
    fast_start_blocked_platforms = [
        item for item in blocked_platforms
        if str(item.get("platform") or "").strip() in FIRST_API_PROOF_PLATFORMS
    ]
    recommended_start_platform = _social_preferred_first_api_platform(ready_platforms, blocked_platforms)

    return {
        "schema": "localos_social_first_api_publish_readiness_v1",
        "source": source,
        "status": status,
        "ready": bool(ready_items),
        "all_api_channels_ready": bool(api_items) and not blocked_items,
        "recommended_start_platform": recommended_start_platform,
        "ready_platforms": ready_platforms,
        "blocked_platforms": blocked_platforms,
        "fast_start_platforms": list(FIRST_API_PROOF_PLATFORMS),
        "fast_start_ready_platforms": fast_start_ready_platforms,
        "fast_start_blocked_platforms": fast_start_blocked_platforms,
        "fast_start_message_ru": _social_first_api_fast_start_message(status, fast_start_ready_platforms, fast_start_blocked_platforms, True),
        "fast_start_message_en": _social_first_api_fast_start_message(status, fast_start_ready_platforms, fast_start_blocked_platforms, False),
        "safe_path_ru": _social_first_api_safe_path(True),
        "safe_path_en": _social_first_api_safe_path(False),
        "pre_proof_checks": _social_first_api_pre_proof_checks(recommended_start_platform),
        "message_ru": _social_first_api_publish_message(status, ready_platforms, blocked_platforms, True),
        "message_en": _social_first_api_publish_message(status, ready_platforms, blocked_platforms, False),
        "next_action_ru": _social_first_api_publish_next_action(status, blocked_platforms, True),
        "next_action_en": _social_first_api_publish_next_action(status, blocked_platforms, False),
        "first_post_checklist_ru": _social_first_api_post_checklist(status, recommended_start_platform, True),
        "first_post_checklist_en": _social_first_api_post_checklist(status, recommended_start_platform, False),
        "first_api_launch_plan_ru": _social_first_api_launch_plan(status, recommended_start_platform, True),
        "first_api_launch_plan_en": _social_first_api_launch_plan(status, recommended_start_platform, False),
        "recommended_start_reason_ru": _social_first_api_start_reason(status, recommended_start_platform, True),
        "recommended_start_reason_en": _social_first_api_start_reason(status, recommended_start_platform, False),
        "proof_check_ru": _social_first_api_proof_check(status, recommended_start_platform, True),
        "proof_check_en": _social_first_api_proof_check(status, recommended_start_platform, False),
        "metrics_followup_ru": _social_first_api_metrics_followup(status, recommended_start_platform, True),
        "metrics_followup_en": _social_first_api_metrics_followup(status, recommended_start_platform, False),
        "external_publish_requires_approval": True,
        "publish_path_ru": "Только после предпросмотра, подтверждения, расписания и наступления даты.",
        "publish_path_en": "Only after preview, human approval, queueing, and the due date.",
    }


def _social_first_api_pre_proof_checks(recommended_platform: dict[str, Any]) -> list[dict[str, Any]]:
    platform = str(recommended_platform.get("platform") or "").strip()
    if platform == "telegram":
        return [
            {
                "key": "telegram_publish_target_probe",
                "platform": "telegram",
                "label_ru": "Проверить цель публикации Telegram",
                "label_en": "Check Telegram publish target",
                "status": "recommended_before_first_proof",
                "message_ru": "Перед первым API-proof выполните read-only проверку: getMe, getChat и getChatMember. Она не отправляет social post наружу.",
                "message_en": "Before the first API proof, run the read-only check: getMe, getChat, and getChatMember. It does not send a social post externally.",
                "action_ru": "Откройте настройки Telegram и нажмите “Проверить цель публикации”.",
                "action_en": "Open Telegram settings and click “Check publish target”.",
                "settings_path": "/dashboard/settings?focus=telegram",
                "endpoint": "/api/business/telegram-bot/publish-target-probe",
                "external_post_published": False,
                "required_before_first_publish": True,
            }
        ]
    if platform == "vk":
        return [
            {
                "key": "vk_wall_post_preflight",
                "platform": "vk",
                "label_ru": "Проверить VK перед первым постом",
                "label_en": "Check VK before the first post",
                "status": "recommended_before_first_proof",
                "message_ru": "Перед первым API-proof проверьте токен, group_id/owner_id и право wall.post через live API-preflight без публикации.",
                "message_en": "Before the first API proof, check token, group_id/owner_id, and wall.post permission through live API preflight without publishing.",
                "action_ru": "Откройте настройки VK или выполните live API-проверку в контент-плане.",
                "action_en": "Open VK settings or run the live API check in the content plan.",
                "settings_path": "/dashboard/settings?focus=vk",
                "endpoint": "/api/business/<business_id>/social-posts/api-channel-preflight",
                "external_post_published": False,
                "required_before_first_publish": True,
            }
        ]
    return [
        {
            "key": "live_api_preflight",
            "platform": platform,
            "label_ru": "Проверить API-канал без публикации",
            "label_en": "Check API channel without publishing",
            "status": "recommended_before_first_proof",
            "message_ru": "Перед первым API-proof выполните live preflight: он проверяет готовность канала и ничего не публикует.",
            "message_en": "Before the first API proof, run a live preflight: it checks channel readiness and publishes nothing.",
            "action_ru": "Нажмите “Проверить API” в контент-плане.",
            "action_en": "Click “Check API” in the content plan.",
            "settings_path": "",
            "endpoint": "/api/business/<business_id>/social-posts/api-channel-preflight",
            "external_post_published": False,
            "required_before_first_publish": bool(platform),
        }
    ] if platform else []


def _social_preferred_first_api_platform(
    ready_platforms: list[dict[str, Any]],
    blocked_platforms: list[dict[str, Any]],
) -> dict[str, Any]:
    for collection in (ready_platforms, blocked_platforms):
        for preferred in FIRST_API_PROOF_PLATFORMS:
            for item in collection:
                if str(item.get("platform") or "").strip() == preferred:
                    return item
    if ready_platforms:
        return ready_platforms[0]
    if blocked_platforms:
        return blocked_platforms[0]
    return {}


def _social_first_api_fast_start_message(
    status: str,
    ready_platforms: list[dict[str, Any]],
    blocked_platforms: list[dict[str, Any]],
    is_ru: bool,
) -> str:
    ready_labels = [
        str(item.get("platform_label") or item.get("platform") or "").strip()
        for item in ready_platforms
        if str(item.get("platform_label") or item.get("platform") or "").strip()
    ]
    blocked_labels = [
        str(item.get("platform_label") or item.get("platform") or "").strip()
        for item in blocked_platforms
        if str(item.get("platform_label") or item.get("platform") or "").strip()
    ]
    if ready_labels:
        joined = ", ".join(ready_labels)
        blocked_joined = ", ".join(blocked_labels)
        if blocked_joined:
            return (
                f"Самый быстрый API-proof можно начать через {joined}; параллельно доведите {blocked_joined} до готовности."
                if is_ru
                else f"The fastest API proof can start with {joined}; in parallel, make {blocked_joined} ready."
            )
        return (
            f"Самый быстрый API-proof можно начать через {joined}: проверьте текст, подтвердите и поставьте в расписание."
            if is_ru
            else f"The fastest API proof can start with {joined}: review copy, approve it, and queue it."
        )
    if blocked_labels:
        joined = ", ".join(blocked_labels)
        return (
            f"Быстрый старт ждёт подключения {joined}. Meta/Google можно подключать позже, но первый proof быстрее получить через Telegram или VK."
            if is_ru
            else f"Fast start is waiting for {joined}. Meta/Google can follow later, but the first proof is usually fastest through Telegram or VK."
        )
    if status == "no_api_channels":
        return (
            "Добавьте хотя бы Telegram или VK, чтобы получить первый доказанный API-пост."
            if is_ru
            else "Add Telegram or VK to get the first proven API post."
        )
    return (
        "Telegram/VK сейчас не участвуют в проверке; можно продолжить с готовым API-каналом, но для MVP они остаются приоритетом."
        if is_ru
        else "Telegram/VK are not in this check; you can continue with a ready API channel, but they remain the MVP priority."
    )


def _social_first_api_safe_path(is_ru: bool) -> list[str]:
    if is_ru:
        return [
            "Проверить API-каналы без публикации.",
            "Открыть предпросмотр и сохранить правки текста.",
            "Подтвердить текст человеком.",
            "Поставить пост в расписание.",
            "После worker проверить provider_post_id/provider_post_url, затем собрать реакции и отметить заявки.",
        ]
    return [
        "Check API channels without publishing.",
        "Open preview and save copy edits.",
        "Approve the copy with a human.",
        "Queue the post on schedule.",
        "After the worker runs, verify provider_post_id/provider_post_url, then collect reactions and record leads.",
    ]


def _social_first_api_publish_message(
    status: str,
    ready_platforms: list[dict[str, Any]],
    blocked_platforms: list[dict[str, Any]],
    is_ru: bool,
) -> str:
    ready_labels = [str(item.get("platform_label") or item.get("platform") or "").strip() for item in ready_platforms]
    blocked_labels = [str(item.get("platform_label") or item.get("platform") or "").strip() for item in blocked_platforms]
    ready_text = ", ".join(label for label in ready_labels if label)
    blocked_text = ", ".join(label for label in blocked_labels if label)
    if status == "all_api_channels_ready":
        return (
            f"API-каналы готовы к первому реальному посту: {ready_text}."
            if is_ru
            else f"API channels are ready for the first real post: {ready_text}."
        )
    if status == "partial_api_ready":
        return (
            f"Можно начинать с готовых API-каналов: {ready_text}. Остальные требуют настройки: {blocked_text}."
            if is_ru
            else f"You can start with ready API channels: {ready_text}. The rest need setup: {blocked_text}."
        )
    if status == "no_api_ready":
        return (
            f"Пока нет готового API-канала для первого реального поста. Требуют настройки: {blocked_text}."
            if is_ru
            else f"No API channel is ready for the first real post yet. Needs setup: {blocked_text}."
        )
    return (
        "API-каналы ещё не настроены для публикаций."
        if is_ru
        else "API channels are not configured for publishing yet."
    )


def _social_first_api_publish_next_action(
    status: str,
    blocked_platforms: list[dict[str, Any]],
    is_ru: bool,
) -> str:
    first_blocked = blocked_platforms[0] if blocked_platforms else {}
    label = str(first_blocked.get("platform_label") or first_blocked.get("platform") or "").strip()
    next_action = str(first_blocked.get("next_action_ru" if is_ru else "next_action_en") or "").strip()
    if status == "all_api_channels_ready":
        return (
            "Проверьте тексты, подтвердите их и поставьте публикации в расписание."
            if is_ru
            else "Review copy, approve it, and queue posts on schedule."
        )
    if status == "partial_api_ready":
        return (
            f"Для первого запуска можно использовать готовые каналы; затем настройте {label}: {next_action or 'подключите ключи и права'}."
            if is_ru
            else f"For the first launch, use ready channels; then set up {label}: {next_action or 'connect keys and permissions'}."
        )
    if status == "no_api_ready":
        return (
            f"Сначала настройте {label}: {next_action or 'подключите ключи и права'}, затем повторите live API-проверку."
            if is_ru
            else f"Set up {label} first: {next_action or 'connect keys and permissions'}, then rerun the live API check."
        )
    return (
        "Подключите хотя бы один API-канал: Telegram или VK быстрее всего дадут первый production-value."
        if is_ru
        else "Connect at least one API channel: Telegram or VK will unlock the fastest production value."
    )


def _social_first_api_post_checklist(
    status: str,
    recommended_platform: dict[str, Any],
    is_ru: bool,
) -> list[str]:
    label = str(
        recommended_platform.get("platform_label")
        or recommended_platform.get("platform")
        or ("API-канал" if is_ru else "API channel")
    ).strip()
    next_action = str(
        recommended_platform.get("next_action_ru" if is_ru else "next_action_en")
        or ""
    ).strip()
    if status in {"all_api_channels_ready", "partial_api_ready"}:
        return [
            (
                f"Выберите первый готовый канал: {label}."
                if is_ru
                else f"Choose the first ready channel: {label}."
            ),
            (
                "Откройте предпросмотр, проверьте текст и сохраните правки."
                if is_ru
                else "Open preview, review copy, and save edits."
            ),
            (
                "Подтвердите текст человеком: подтверждение не публикует наружу."
                if is_ru
                else "Approve the copy with a human: approval does not publish externally."
            ),
            (
                "Поставьте пост в расписание и дождитесь даты публикации или одного ограниченного цикла исполнителя."
                if is_ru
                else "Queue the post and wait for the due date or a scoped worker cycle."
            ),
            (
                "После публикации проверьте provider_post_id/provider_post_url и отметьте заявки."
                if is_ru
                else "After publishing, check provider_post_id/provider_post_url and record leads."
            ),
        ]
    if status == "no_api_ready":
        setup_step = next_action or (
            "подключите ключи, права и привязку аккаунта"
            if is_ru
            else "connect keys, permissions, and account binding"
        )
        return [
            (
                f"Начните с канала {label}: {setup_step}."
                if is_ru
                else f"Start with {label}: {setup_step}."
            ),
            (
                "Повторите live API-проверку без публикации."
                if is_ru
                else "Rerun the live API check without publishing."
            ),
            (
                "Когда канал станет готов, пройдите: предпросмотр → подтверждение → расписание."
                if is_ru
                else "Once the channel is ready, go through preview → approval → queue."
            ),
        ]
    return [
        (
            "Подключите Telegram или VK как первый API-канал."
            if is_ru
            else "Connect Telegram or VK as the first API channel."
        ),
        (
            "После подключения повторите live API-проверку и подготовьте первый пост."
            if is_ru
            else "After connecting it, rerun the live API check and prepare the first post."
        ),
    ]


def _social_first_api_launch_plan(
    status: str,
    recommended_platform: dict[str, Any],
    is_ru: bool,
) -> list[str]:
    label = str(
        recommended_platform.get("platform_label")
        or recommended_platform.get("platform")
        or ("API-канал" if is_ru else "API channel")
    ).strip()
    next_action = str(
        recommended_platform.get("next_action_ru" if is_ru else "next_action_en")
        or ""
    ).strip()
    if status in {"all_api_channels_ready", "partial_api_ready"}:
        return [
            (
                f"Начните с одного готового канала: {label}."
                if is_ru
                else f"Start with one ready channel: {label}."
            ),
            (
                "Возьмите ближайшую тему контент-плана и подготовьте версии текста под каналы."
                if is_ru
                else "Use the nearest content-plan topic and prepare platform-specific copy."
            ),
            (
                "Покажите предпросмотр владельцу и сохраните правки до подтверждения."
                if is_ru
                else "Show the preview to the owner and save edits before approval."
            ),
            (
                "После подтверждения поставьте пост в расписание; исполнитель публикует только API-посты с наступившей датой."
                if is_ru
                else "After approval, queue the post; the worker publishes only the due API post."
            ),
            (
                "Зафиксируйте proof публикации и сразу отметьте заявки/обращения, если они появились."
                if is_ru
                else "Record publish proof and immediately mark leads/inquiries if they appear."
            ),
        ]
    if status == "no_api_ready":
        setup_step = next_action or (
            "подключите ключи, права и аккаунт"
            if is_ru
            else "connect keys, permissions, and account binding"
        )
        return [
            (
                f"Сначала доведите {label} до готовности: {setup_step}."
                if is_ru
                else f"First make {label} ready: {setup_step}."
            ),
            (
                "Повторите live API-проверку без публикации."
                if is_ru
                else "Rerun live API-preflight without publishing."
            ),
            (
                "Когда появится готовый канал, пройдите: предпросмотр → подтверждение → расписание для одного поста."
                if is_ru
                else "When a ready channel appears, run preview → approval → queue for one post."
            ),
            (
                "Не включайте внешнюю публикацию, пока нет явной готовности и подтверждения."
                if is_ru
                else "Do not enable external publish until ready and approval are explicit."
            ),
        ]
    return [
        (
            "Подключите Telegram или VK как первый API-канал."
            if is_ru
            else "Connect Telegram or VK as the first API channel."
        ),
        (
            "После подключения повторите live API-проверку и подготовьте один пост из контент-плана."
            if is_ru
            else "After connecting it, rerun live API-preflight and prepare one content-plan post."
        ),
        (
            "Дальше идите только через предпросмотр, подтверждение человека и расписание."
            if is_ru
            else "Then proceed only through preview, human approval, and queue."
        ),
    ]


def _social_first_api_start_reason(
    status: str,
    recommended_platform: dict[str, Any],
    is_ru: bool,
) -> str:
    label = str(
        recommended_platform.get("platform_label")
        or recommended_platform.get("platform")
        or ("API-канал" if is_ru else "API channel")
    ).strip()
    if status in {"all_api_channels_ready", "partial_api_ready"}:
        return (
            f"{label} выбран как самый короткий путь к первому проверенному API-посту: канал уже ready, поэтому риск только в тексте, approval и due-времени."
            if is_ru
            else f"{label} is the shortest path to the first proven API post: the channel is ready, so the remaining risk is copy, approval, and due time."
        )
    if status == "no_api_ready":
        return (
            f"{label} выбран как первый блокер: без ключей/прав LocalOS не должен пытаться публиковать наружу."
            if is_ru
            else f"{label} is the first blocker: without keys/permissions LocalOS must not try to publish externally."
        )
    return (
        "Telegram или VK обычно быстрее всего дают первый проверенный API-пост."
        if is_ru
        else "Telegram or VK usually unlock the first proven API post fastest."
    )


def _social_first_api_proof_check(
    status: str,
    recommended_platform: dict[str, Any],
    is_ru: bool,
) -> str:
    label = str(
        recommended_platform.get("platform_label")
        or recommended_platform.get("platform")
        or ("API-канал" if is_ru else "API channel")
    ).strip()
    if status in {"all_api_channels_ready", "partial_api_ready"}:
        return (
            f"После первого запуска откройте {label}: у опубликованного social_post должны быть provider_post_id/provider_post_url; без этого цикл не доказан."
            if is_ru
            else f"After the first run, open {label}: the published social_post must have provider_post_id/provider_post_url; without that, the loop is not proven."
        )
    return (
        "Сначала добейтесь ready в live API-проверке; provider_post_id/provider_post_url проверяются только после реальной approved/queued публикации."
        if is_ru
        else "First get live API-preflight to ready; provider_post_id/provider_post_url are checked only after a real approved/queued publish."
    )


def _social_first_api_metrics_followup(
    status: str,
    recommended_platform: dict[str, Any],
    is_ru: bool,
) -> str:
    if status in {"all_api_channels_ready", "partial_api_ready"}:
        return (
            "После первого подтверждённого запуска соберите реакции/заявки и отметьте обращения; следующий план не меняется автоматически без подтверждения."
            if is_ru
            else "After proof, collect reactions/leads and mark inquiries; the next plan is not changed automatically without approval."
        )
    return (
        "Метрики появятся после первого доказанного API-поста; до этого цель — подключить канал и не имитировать success."
        if is_ru
        else "Metrics come after the first proven API post; until then, the goal is to connect a channel and avoid fake success."
    )


def _api_preflight_blocked_due_posts(
    dispatch_items: list[dict[str, Any]],
    api_preflight: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    readiness_by_platform = {
        str(item.get("platform") or "").strip(): item
        for item in api_preflight or []
        if str(item.get("platform") or "").strip()
    }
    blocked: list[dict[str, Any]] = []
    for item in dispatch_items or []:
        if str(item.get("dispatch_action") or "").strip() != "publish_api":
            continue
        platform = str(item.get("platform") or "").strip()
        preflight = readiness_by_platform.get(platform)
        if not preflight or bool(preflight.get("ready")):
            continue
        status = str(preflight.get("status") or "not_ready").strip()
        label = str(item.get("platform_label") or platform_label(platform)).strip()
        message_ru = str(preflight.get("message_ru") or "").strip()
        message_en = str(preflight.get("message_en") or "").strip()
        next_action_ru = _api_preflight_block_next_action(platform, status, True)
        next_action_en = _api_preflight_block_next_action(platform, status, False)
        blocked.append(
            {
                "id": str(item.get("id") or "").strip(),
                "content_plan_item_id": str(item.get("content_plan_item_id") or "").strip(),
                "platform": platform,
                "platform_label": label,
                "status": status,
                "message_ru": message_ru,
                "message_en": message_en,
                "next_action_ru": next_action_ru,
                "next_action_en": next_action_en,
                "settings_path": _api_preflight_settings_path(platform),
                "recoverable": True,
                "safety_summary_ru": (
                    "Worker не будет публиковать этот due-пост, пока канал не пройдёт live API-проверку. "
                    "Approval сохранён, но внешний publish остановлен безопасно."
                ),
                "safety_summary_en": (
                    "The worker will not publish this due post until the channel passes live API preflight. "
                    "Approval is kept, but external publishing is safely stopped."
                ),
            }
        )
    return blocked


def _api_preflight_settings_path(platform: str) -> str:
    normalized = str(platform or "").strip()
    if normalized == "telegram":
        return "/dashboard/settings?focus=channels"
    return "/dashboard/settings?focus=integrations"


def _api_preflight_block_next_action(platform: str, status: str, is_ru: bool) -> str:
    normalized_platform = str(platform or "").strip()
    normalized_status = str(status or "").strip()
    label = platform_label(normalized_platform)
    if normalized_platform == "telegram":
        if normalized_status in {"missing_keys", "telegram_connection_missing"}:
            return (
                "Откройте настройки Telegram, добавьте telegram_bot_token и telegram_chat_id, затем повторите live API-проверку."
                if is_ru
                else "Open Telegram settings, add telegram_bot_token and telegram_chat_id, then rerun live API preflight."
            )
        return (
            "Проверьте, что бот доступен, добавлен в канал/чат и имеет права писать; затем повторите live API-проверку."
            if is_ru
            else "Check that the bot is reachable, added to the channel/chat, and can post; then rerun live API preflight."
        )
    if normalized_platform == "vk":
        if normalized_status == "missing_permissions":
            return (
                "Откройте интеграции VK и выдайте токену право wall.post; затем повторите live API-проверку."
                if is_ru
                else "Open VK integrations and grant wall.post to the token; then rerun live API preflight."
            )
        if normalized_status in {"missing_binding", "missing_keys"}:
            return (
                "Откройте интеграции VK, добавьте access_token и group_id/owner_id; затем повторите live API-проверку."
                if is_ru
                else "Open VK integrations, add access_token and group_id/owner_id, then rerun live API preflight."
            )
        return (
            "Проверьте VK token, группу и доступ API; затем повторите live API-проверку."
            if is_ru
            else "Check the VK token, group, and API access; then rerun live API preflight."
        )
    if normalized_platform == "google_business":
        return (
            "Откройте интеграции Google Business Profile, проверьте OAuth и location для публикации."
            if is_ru
            else "Open Google Business Profile integrations and check OAuth plus the publishing location."
        )
    if normalized_platform in {"instagram", "facebook"}:
        return (
            f"Откройте подключение Meta для {label}, проверьте Page/IG business и права; без них используйте ручной режим."
            if is_ru
            else f"Open the Meta integration for {label}, check Page/IG business binding and permissions; use manual fallback until ready."
        )
    return (
        f"Откройте настройки канала {label}, исправьте подключение и повторите live API-проверку."
        if is_ru
        else f"Open {label} channel settings, fix the connection, and rerun live API preflight."
    )


def _social_launch_preflight_message(status: str, is_ru: bool) -> str:
    if status == "api_preflight_blocked":
        return (
            "Есть API-посты на текущую дату, но проверка нашла канал без ключей, прав или готового адаптера. Сначала исправьте канал или переведите пост в ручной режим."
            if is_ru
            else "Due API posts exist, but live API preflight found a channel without keys, permissions, or a ready adapter. Fix the channel or move the post to manual fallback first."
        )
    if status == "ready_for_api_dispatch":
        return (
            "Есть API-публикации на текущую дату: ограниченный исполнитель сможет отправить их только после уже полученного подтверждения."
            if is_ru
            else "Due API posts exist: the scoped worker can publish them only after existing approval."
        )
    if status == "ready_for_controlled_handoff":
        return (
            "Есть публикации для карт на текущую дату: исполнитель создаст контролируемое или ручное размещение без финального клика."
            if is_ru
            else "Due map posts exist: the worker will create supervised placement or manual handoff without the final click."
        )
    if status == "manual_or_connection_needed":
        return (
            "Посты на текущую дату есть, но сейчас они требуют ручного режима или подключения каналов."
            if is_ru
            else "Due posts exist, but they currently require manual fallback or channel connections."
        )
    if status == "access_limited":
        return (
            "Часть due-постов вне доступа текущего пользователя; scoped запуск нужно сузить или проверить права."
            if is_ru
            else "Some due posts are outside this user's access; narrow the scoped launch or check permissions."
        )
    return (
        "Due-постов нет: сначала подготовьте, подтвердите и поставьте публикации в расписание."
        if is_ru
        else "No due posts: prepare, approve, and queue publications first."
    )


def _social_launch_preflight_next_action(status: str, business_id: str, is_ru: bool) -> str:
    if status == "api_preflight_blocked":
        return (
            "Откройте готовность каналов, исправьте ключи/permissions или используйте ручное размещение для заблокированного поста; затем повторите preflight."
            if is_ru
            else "Open channel readiness, fix keys/permissions, or use manual placement for the blocked post; then run preflight again."
        )
    if status in {"ready_for_api_dispatch", "ready_for_controlled_handoff", "manual_or_connection_needed"}:
        return (
            f"Для первого запуска включайте исполнителя только с SOCIAL_POST_DISPATCH_BUSINESS_ID={business_id} и проверьте логи после одного цикла."
            if is_ru
            else f"For the first launch, enable the worker only with SOCIAL_POST_DISPATCH_BUSINESS_ID={business_id} and check logs after one cycle."
        )
    if status == "access_limited":
        return (
            "Запустите preflight пользователем с доступом к бизнесу или выберите другой business scope."
            if is_ru
            else "Run preflight as a user with access to the business or choose another business scope."
        )
    return (
        "Следующий шаг в интерфейсе: подготовить каналы, проверить предпросмотр, утвердить и поставить посты в расписание."
        if is_ru
        else "Next in the UI: prepare channels, review preview, approve, and queue posts on schedule."
    )


def _metrics_preview_recommended_env(business_scope: str) -> dict[str, str]:
    scope = str(business_scope or "").strip()
    return {
        "SOCIAL_POST_METRICS_ENABLED": "true",
        "SOCIAL_POST_METRICS_INTERVAL_SEC": "3600",
        "SOCIAL_POST_METRICS_BATCH_SIZE": "50",
        "SOCIAL_POST_METRICS_BUSINESS_ID": scope,
    }


def prepare_social_posts_for_items(user_id: str, item_ids: list[str], platforms: list[str] | None = None) -> dict[str, Any]:
    posts: list[dict[str, Any]] = []
    failed: list[dict[str, str]] = []
    for item_id in _normalize_ids(item_ids):
        try:
            payload = prepare_social_posts_for_item(user_id, item_id, platforms)
            posts.extend(payload.get("posts") or [])
        except Exception:
            failed.append({"id": item_id, "error": str(sys.exc_info()[1])})
    return {
        "posts": posts,
        "failed": failed,
        "summary": _summary_for_posts(posts),
        "queue_groups": build_social_queue_groups(posts),
    }


def approve_social_post(user_id: str, post_id: str) -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_social_post_tables(cursor)
        post = _load_post_for_user(cursor, user_id, post_id)
        status = str(post.get("status") or "").strip()
        if status == "published":
            raise ValueError("Публикация уже опубликована")
        if not _social_post_has_text(post):
            raise ValueError("Перед подтверждением нужно заполнить текст публикации")
        now = datetime.now(timezone.utc)
        cursor.execute(
            """
            UPDATE social_posts
            SET status = 'approved',
                approved_at = COALESCE(approved_at, %s),
                approval_id = COALESCE(NULLIF(approval_id, ''), %s),
                last_error = NULL,
                updated_at = NOW()
            WHERE id = %s
            RETURNING *
            """,
            (now, _new_id(), post_id),
        )
        updated = _serialize_social_post(cursor, cursor.fetchone())
        db.conn.commit()
        return updated
    except Exception:
        db.conn.rollback()
        raise sys.exc_info()[1]
    finally:
        db.close()


def approve_social_posts(user_id: str, post_ids: list[str]) -> dict[str, Any]:
    posts: list[dict[str, Any]] = []
    failed: list[dict[str, str]] = []
    for post_id in _normalize_ids(post_ids):
        try:
            posts.append(approve_social_post(user_id, post_id))
        except Exception:
            failed.append({"id": post_id, "error": str(sys.exc_info()[1])})
    return {
        "posts": posts,
        "failed": failed,
        "summary": _summary_for_posts(posts),
        "queue_groups": build_social_queue_groups(posts),
    }


def update_social_post_text(
    user_id: str,
    post_id: str,
    platform_text: str,
    base_text: str = "",
) -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_social_post_tables(cursor)
        post = _load_post_for_user(cursor, user_id, post_id)
        current_status = str(post.get("status") or "").strip()
        if current_status in {"queued", "publishing", "published"}:
            raise ValueError("Нельзя менять текст после постановки в расписание или публикации")
        next_text = str(platform_text or "").strip()
        next_base_text = str(base_text or post.get("base_text") or "").strip()
        metadata = _json_dict(post.get("metadata_json"))
        metadata["last_text_edit"] = {
            "edited_by": user_id,
            "edited_at": datetime.now(timezone.utc).isoformat(),
            "approval_reset": current_status == "approved",
        }
        next_status = _status_after_social_text_edit(current_status, next_text)
        cursor.execute(
            """
            UPDATE social_posts
            SET base_text = %s,
                platform_text = %s,
                status = %s,
                approved_at = NULL,
                approval_id = NULL,
                metadata_json = %s,
                last_error = NULL,
                updated_at = NOW()
            WHERE id = %s
            RETURNING *
            """,
            (
                next_base_text,
                next_text,
                next_status,
                _json_dumps(metadata),
                post_id,
            ),
        )
        updated = _serialize_social_post(cursor, cursor.fetchone())
        db.conn.commit()
        return updated
    except Exception:
        db.conn.rollback()
        raise sys.exc_info()[1]
    finally:
        db.close()


def queue_social_post(user_id: str, post_id: str) -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_social_post_tables(cursor)
        post = _load_post_for_user(cursor, user_id, post_id)
        status = str(post.get("status") or "").strip()
        if status == "published":
            raise ValueError("Публикация уже опубликована")
        if status not in {"approved", "queued"} or not post.get("approved_at"):
            raise PermissionError("Перед постановкой в расписание нужно подтверждение человека")
        platform = str(post.get("platform") or "").strip()
        if platform in BROWSER_OR_MANUAL_PLATFORMS:
            updated = _create_supervised_publish_task(cursor, post)
            db.conn.commit()
            return updated
        queue_block = _queue_preflight_block(cursor, post)
        if queue_block:
            metadata = _json_dict(post.get("metadata_json"))
            metadata.update(_json_dict(queue_block.get("metadata_json")))
            cursor.execute(
                """
                UPDATE social_posts
                SET status = 'needs_manual_publish',
                    metadata_json = %s,
                    last_error = %s,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING *
                """,
                (
                    _json_dumps(metadata),
                    str(queue_block.get("last_error") or "").strip(),
                    post_id,
                ),
            )
            updated = _serialize_social_post(cursor, cursor.fetchone())
            db.conn.commit()
            return updated
        cursor.execute(
            """
            UPDATE social_posts
            SET status = 'queued',
                last_error = NULL,
                updated_at = NOW()
            WHERE id = %s
            RETURNING *
            """,
            (post_id,),
        )
        updated = _serialize_social_post(cursor, cursor.fetchone())
        db.conn.commit()
        return updated
    except Exception:
        db.conn.rollback()
        raise sys.exc_info()[1]
    finally:
        db.close()


def queue_social_posts(user_id: str, post_ids: list[str]) -> dict[str, Any]:
    posts: list[dict[str, Any]] = []
    failed: list[dict[str, str]] = []
    for post_id in _normalize_ids(post_ids):
        try:
            posts.append(queue_social_post(user_id, post_id))
        except Exception:
            failed.append({"id": post_id, "error": str(sys.exc_info()[1])})
    return {
        "posts": posts,
        "failed": failed,
        "summary": _summary_for_posts(posts),
        "queue_groups": build_social_queue_groups(posts),
    }


def create_supervised_publish_task(user_id: str, post_id: str, approved: bool = False) -> dict[str, Any]:
    if not approved:
        raise PermissionError("Для подготовки контролируемого размещения нужно явное подтверждение")
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_social_post_tables(cursor)
        post = _load_post_for_user(cursor, user_id, post_id)
        updated = _create_supervised_publish_task(cursor, post)
        db.conn.commit()
        return updated
    except Exception:
        db.conn.rollback()
        raise sys.exc_info()[1]
    finally:
        db.close()


def _create_supervised_publish_task(cursor: Any, post: dict[str, Any]) -> dict[str, Any]:
    post_id = str(post.get("id") or "").strip()
    platform = str(post.get("platform") or "").strip()
    status = str(post.get("status") or "").strip()
    if platform not in BROWSER_OR_MANUAL_PLATFORMS:
        raise ValueError("Контролируемое размещение доступно только для Яндекс/2ГИС")
    if status == "published":
        raise ValueError("Публикация уже опубликована")
    if not post.get("approved_at") and status not in {"approved", "queued", "needs_supervised_publish", "needs_manual_publish"}:
        raise PermissionError("Перед контролируемым размещением нужно подтверждение человека")
    if not _social_post_has_text(post):
        raise ValueError("Перед контролируемым размещением нужно заполнить текст")

    automation_task_id = str(post.get("automation_task_id") or "").strip() or _new_id()
    metadata = _json_dict(post.get("metadata_json"))
    metadata.update(_supervised_publish_metadata(cursor, post, automation_task_id))
    supervised_state = _supervised_publish_state(post, cursor)
    cursor.execute(
        """
        UPDATE social_posts
        SET status = %s,
            automation_task_id = %s,
            metadata_json = %s,
            last_error = %s,
            updated_at = NOW()
        WHERE id = %s
        RETURNING *
        """,
        (
            supervised_state["status"],
            automation_task_id,
            _json_dumps(metadata),
            supervised_state["last_error"],
            post_id,
        ),
    )
    updated = _serialize_social_post(cursor, cursor.fetchone())
    ledger_id = _record_social_supervised_handoff_ledger(cursor, post, updated, automation_task_id)
    outbox_id = ""
    if ledger_id:
        metadata = _json_dict(updated.get("metadata_json"))
        metadata["agent_action_ledger_id"] = ledger_id
        supervised_payload = _json_dict(metadata.get("supervised_publish"))
        handoff_state = _json_dict(supervised_payload.get("handoff_state"))
        handoff_state["ledger_recorded"] = True
        handoff_state["ledger_id"] = ledger_id
        supervised_payload["handoff_state"] = handoff_state
        metadata["supervised_publish"] = supervised_payload
        cursor.execute(
            """
            UPDATE social_posts
            SET metadata_json = %s,
                updated_at = NOW()
            WHERE id = %s
            RETURNING *
            """,
            (_json_dumps(metadata), post_id),
        )
        updated = _serialize_social_post(cursor, cursor.fetchone())
    if str(updated.get("status") or "").strip() == "needs_supervised_publish":
        outbox_id = _enqueue_social_supervised_openclaw_outbox(cursor, updated, automation_task_id, ledger_id)
    if outbox_id:
        metadata = _json_dict(updated.get("metadata_json"))
        supervised_payload = _json_dict(metadata.get("supervised_publish"))
        handoff_state = _json_dict(supervised_payload.get("handoff_state"))
        handoff_state["openclaw_task_requested"] = True
        handoff_state["openclaw_outbox_id"] = outbox_id
        handoff_state["owner_status_ru"] = "Задача передана в outbox для контролируемого OpenClaw browser-use."
        handoff_state["owner_status_en"] = "Task was queued in the outbox for supervised OpenClaw browser-use."
        handoff_state["owner_next_action_ru"] = "Проверьте задачу OpenClaw, дождитесь предпросмотра и подтвердите финальное действие человеком."
        handoff_state["owner_next_action_en"] = "Check the OpenClaw task, wait for preview, and let a human confirm the final action."
        supervised_payload["handoff_state"] = handoff_state
        supervised_payload["openclaw_outbox_id"] = outbox_id
        metadata["supervised_publish"] = supervised_payload
        cursor.execute(
            """
            UPDATE social_posts
            SET metadata_json = %s,
                updated_at = NOW()
            WHERE id = %s
            RETURNING *
            """,
            (_json_dumps(metadata), post_id),
        )
        updated = _serialize_social_post(cursor, cursor.fetchone())
    return updated


def publish_social_post(user_id: str, post_id: str) -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_social_post_tables(cursor)
        post = _load_post_for_user(cursor, user_id, post_id)
        if not post.get("approved_at") and str(post.get("status") or "") not in {"approved", "queued"}:
            raise PermissionError("Перед внешней публикацией нужно подтверждение человека")
        if not _social_post_has_text(post):
            cursor.execute(
                """
                UPDATE social_posts
                SET status = 'needs_review',
                    approved_at = NULL,
                    approval_id = NULL,
                    last_error = %s,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING *
                """,
                ("Перед публикацией нужно заполнить текст и заново подтвердить preview", post_id),
            )
            updated = _serialize_social_post(cursor, cursor.fetchone())
            db.conn.commit()
            return updated
        platform = str(post.get("platform") or "").strip()
        publish_mode = str(post.get("publish_mode") or "").strip()
        metadata = _json_dict(post.get("metadata_json"))
        if platform in BROWSER_OR_MANUAL_PLATFORMS:
            updated = _create_supervised_publish_task(cursor, post)
            db.conn.commit()
            return updated
        if publish_mode != "api":
            cursor.execute(
                """
                UPDATE social_posts
                SET status = 'needs_manual_publish',
                    last_error = %s,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING *
                """,
                ("Для канала не настроен API-адаптер", post_id),
            )
            updated = _serialize_social_post(cursor, cursor.fetchone())
            db.conn.commit()
            return updated
        cursor.execute(
            """
            UPDATE social_posts
            SET status = 'publishing',
                metadata_json = %s,
                last_error = NULL,
                updated_at = NOW()
            WHERE id = %s
            RETURNING *
            """,
            (_json_dumps(metadata), post_id),
        )
        post = _serialize_social_post(cursor, cursor.fetchone())
        publish_result = _publish_api_post(cursor, post)
        metadata.update(_json_dict(post.get("metadata_json")))
        metadata.update(_json_dict(publish_result.get("metadata_json")))
        next_status = str(publish_result.get("status") or "failed")
        if next_status not in SOCIAL_POST_STATUSES:
            next_status = "failed"
        published_at = datetime.now(timezone.utc) if next_status == "published" else None
        cursor.execute(
            """
            UPDATE social_posts
            SET status = %s,
                published_at = COALESCE(published_at, %s),
                provider_post_id = COALESCE(NULLIF(%s, ''), provider_post_id),
                provider_post_url = COALESCE(NULLIF(%s, ''), provider_post_url),
                metadata_json = %s,
                last_error = %s,
                updated_at = NOW()
            WHERE id = %s
            RETURNING *
            """,
            (
                next_status,
                published_at,
                str(publish_result.get("provider_post_id") or "").strip(),
                str(publish_result.get("provider_post_url") or "").strip(),
                _json_dumps(metadata),
                str(publish_result.get("last_error") or "").strip() or None,
                post_id,
            ),
        )
        updated = _serialize_social_post(cursor, cursor.fetchone())
        db.conn.commit()
        return updated
    except Exception:
        db.conn.rollback()
        raise sys.exc_info()[1]
    finally:
        db.close()


def publish_social_posts(user_id: str, post_ids: list[str]) -> dict[str, Any]:
    posts: list[dict[str, Any]] = []
    failed: list[dict[str, str]] = []
    for post_id in _normalize_ids(post_ids):
        try:
            posts.append(publish_social_post(user_id, post_id))
        except Exception:
            failed.append({"id": post_id, "error": str(sys.exc_info()[1])})
    return {
        "posts": posts,
        "failed": failed,
        "summary": _summary_for_posts(posts),
        "queue_groups": build_social_queue_groups(posts),
    }


def rehearse_social_post_publish(user_id: str, post_id: str) -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_social_post_tables(cursor)
        post = _load_post_for_user(cursor, user_id, post_id)
        return _build_social_post_publish_rehearsal(cursor, post)
    finally:
        db.close()


def rehearse_social_posts_publish(user_id: str, post_ids: list[str]) -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    rehearsals: list[dict[str, Any]] = []
    failed: list[dict[str, str]] = []
    try:
        ensure_social_post_tables(cursor)
        for post_id in _normalize_ids(post_ids):
            try:
                post = _load_post_for_user(cursor, user_id, post_id)
                rehearsals.append(_build_social_post_publish_rehearsal(cursor, post))
            except Exception:
                failed.append({"id": post_id, "error": str(sys.exc_info()[1])})
        summary = _social_publish_rehearsal_summary(rehearsals, failed)
        return {
            "schema": "localos_social_publish_rehearsal_bulk_v1",
            "dry_run": True,
            "external_publish_performed": False,
            "provider_write_performed": False,
            "rehearsals": rehearsals,
            "failed": failed,
            "summary": summary,
        }
    finally:
        db.close()


def mark_manual_published(user_id: str, post_id: str, provider_post_url: str = "", provider_post_id: str = "") -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_social_post_tables(cursor)
        post = _load_post_for_user(cursor, user_id, post_id)
        status = str(post.get("status") or "").strip()
        if status not in {"needs_supervised_publish", "needs_manual_publish"}:
            raise ValueError("Ручная отметка публикации доступна только для ручного или контролируемого размещения")
        metadata = _json_dict(post.get("metadata_json"))
        metadata["published_source"] = "manual_confirmation"
        cursor.execute(
            """
            UPDATE social_posts
            SET status = 'published',
                published_at = COALESCE(published_at, %s),
                provider_post_url = COALESCE(NULLIF(%s, ''), provider_post_url),
                provider_post_id = COALESCE(NULLIF(%s, ''), provider_post_id),
                metadata_json = %s,
                last_error = NULL,
                updated_at = NOW()
            WHERE id = %s
            RETURNING *
            """,
            (datetime.now(timezone.utc), provider_post_url, provider_post_id, _json_dumps(metadata), post_id),
        )
        updated = _serialize_social_post(cursor, cursor.fetchone())
        db.conn.commit()
        return updated
    except Exception:
        db.conn.rollback()
        raise sys.exc_info()[1]
    finally:
        db.close()


def mark_supervised_publish_blocked(
    user_id: str,
    post_id: str,
    reason: str = "",
    blocked_source: str = "manual",
) -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_social_post_tables(cursor)
        post = _load_post_for_user(cursor, user_id, post_id)
        platform = str(post.get("platform") or "").strip()
        status = str(post.get("status") or "").strip()
        if platform not in BROWSER_OR_MANUAL_PLATFORMS and status != "needs_supervised_publish":
            raise ValueError("Этот пост не является контролируемой browser-use публикацией")
        if status not in {"needs_supervised_publish", "needs_manual_publish", "queued"}:
            raise ValueError("Ручной режим доступен только для запланированных или контролируемых публикаций")

        blocked_reason = str(reason or "").strip()
        if not blocked_reason:
            blocked_reason = (
                "Контролируемое размещение заблокировано: нужен ручной режим "
                "(логин, капча или изменённый интерфейс площадки)."
            )
        metadata = _social_supervised_blocked_metadata(
            _json_dict(post.get("metadata_json")),
            blocked_reason,
            str(blocked_source or "manual").strip() or "manual",
        )
        cursor.execute(
            """
            UPDATE social_posts
            SET status = 'needs_manual_publish',
                metadata_json = %s,
                last_error = %s,
                updated_at = NOW()
            WHERE id = %s
            RETURNING *
            """,
            (_json_dumps(metadata), blocked_reason, post_id),
        )
        updated = _serialize_social_post(cursor, cursor.fetchone())
        db.conn.commit()
        return updated
    except Exception:
        db.conn.rollback()
        raise sys.exc_info()[1]
    finally:
        db.close()


def mark_manual_published_posts(
    user_id: str,
    post_ids: list[str],
    provider_post_url: str = "",
    provider_post_id: str = "",
) -> dict[str, Any]:
    posts: list[dict[str, Any]] = []
    failed: list[dict[str, str]] = []
    for post_id in _normalize_ids(post_ids):
        try:
            posts.append(mark_manual_published(user_id, post_id, provider_post_url, provider_post_id))
        except Exception:
            failed.append({"id": post_id, "error": str(sys.exc_info()[1])})
    return {
        "posts": posts,
        "failed": failed,
        "summary": _summary_for_posts(posts),
        "queue_groups": build_social_queue_groups(posts),
    }


def _social_supervised_blocked_metadata(metadata: dict[str, Any], reason: str, blocked_source: str) -> dict[str, Any]:
    payload = dict(metadata or {})
    supervised = _json_dict(payload.get("supervised_publish"))
    blocked_at = datetime.now(timezone.utc).isoformat()
    manual_handoff = _manual_publish_handoff_payload(
        {
            "platform": supervised.get("platform", ""),
            "platform_text": supervised.get("copy_ready_text", ""),
        },
        {
            "target_url": supervised.get("target_url", ""),
            "target_url_source": supervised.get("target_url_source", ""),
            "profile_hint": supervised.get("profile_hint", ""),
        },
        reason,
    )
    supervised.update(
        {
            "task_status": "blocked_needs_manual_publish",
            "blocked_reason": str(reason or "").strip(),
            "blocked_source": str(blocked_source or "manual").strip() or "manual",
            "blocked_at": blocked_at,
            "manual_fallback_required": True,
            "final_publish_policy": "human_final_click_required",
            "stop_before_final_publish": True,
            "manual_handoff": manual_handoff,
            "manual_checklist_ru": manual_handoff["checklist_ru"],
            "manual_checklist_en": manual_handoff["checklist_en"],
        }
    )
    payload["supervised_publish"] = supervised
    payload["manual_fallback"] = {
        "required": True,
        "reason": str(reason or "").strip(),
        "source": str(blocked_source or "manual").strip() or "manual",
        "blocked_at": blocked_at,
        "handoff": manual_handoff,
    }
    payload["browser_final_click_allowed"] = False
    payload["human_final_approval_required"] = True
    return payload


def record_social_post_attribution_event(
    user_id: str,
    post_id: str,
    event_type: str,
    value: int = 1,
    event_source: str = "manual",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_social_post_tables(cursor)
        post = _load_post_for_user(cursor, user_id, post_id)
        normalized_event_type = str(event_type or "").strip().lower()
        event, metrics = _record_social_post_attribution_event_in_cursor(
            cursor,
            post,
            normalized_event_type,
            value,
            event_source,
            metadata or {},
        )
        updated_post = {
            **post,
            **metrics,
        }
        db.conn.commit()
        return {
            "event": event,
            "post": updated_post,
            "metrics": metrics,
        }
    except Exception:
        db.conn.rollback()
        raise sys.exc_info()[1]
    finally:
        db.close()


def record_social_post_attribution_events(
    user_id: str,
    post_ids: list[str],
    event_type: str,
    value: int = 1,
    event_source: str = "manual",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    requested_ids = [str(post_id or "").strip() for post_id in post_ids if str(post_id or "").strip()]
    if not requested_ids:
        raise ValueError("Нет выбранных публикаций")
    normalized_event_type = str(event_type or "").strip().lower()
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_social_post_tables(cursor)
        events = []
        posts = []
        metrics_by_post = {}
        for post_id in requested_ids:
            post = _load_post_for_user(cursor, user_id, post_id)
            event, metrics = _record_social_post_attribution_event_in_cursor(
                cursor,
                post,
                normalized_event_type,
                value,
                event_source,
                {
                    **(metadata or {}),
                    "bulk": True,
                    "post_id": post_id,
                    "platform": str(post.get("platform") or "").strip(),
                    "content_plan_item_id": str(post.get("content_plan_item_id") or "").strip(),
                },
            )
            events.append(event)
            posts.append({**post, **metrics})
            metrics_by_post[str(post.get("id") or post_id)] = metrics
        db.conn.commit()
        return {
            "events": events,
            "posts": posts,
            "metrics_by_post": metrics_by_post,
            "summary": {
                "requested": len(requested_ids),
                "recorded": len(events),
                "event_type": normalized_event_type,
                "external_publish_performed": False,
                "provider_write_performed": False,
                "recommendation_should_refresh": True,
            },
        }
    except Exception:
        db.conn.rollback()
        raise sys.exc_info()[1]
    finally:
        db.close()


def _record_social_post_attribution_event_in_cursor(
    cursor: Any,
    post: dict[str, Any],
    event_type: str,
    value: int = 1,
    event_source: str = "manual",
    metadata: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, int]]:
    normalized_event_type = str(event_type or "").strip().lower()
    if normalized_event_type not in {"lead", "inquiry", "comment", "share", "click", "like", "view"}:
        raise ValueError("Неподдерживаемый тип события")
    if str(post.get("status") or "").strip() != "published":
        raise ValueError("Результаты можно отмечать только после публикации")
    event_value = max(int(value or 1), 1)
    event_id = _new_id()
    cursor.execute(
        """
        INSERT INTO social_post_attribution_events (
            id, social_post_id, business_id, event_type, event_source, value, metadata_json, event_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        RETURNING *
        """,
        (
            event_id,
            post.get("id"),
            post.get("business_id"),
            normalized_event_type,
            str(event_source or "manual").strip() or "manual",
            event_value,
            _json_dumps(metadata or {}),
        ),
    )
    event = _row_to_dict(cursor, cursor.fetchone())
    for key, item in list(event.items()):
        if isinstance(item, (datetime, date)):
            event[key] = item.isoformat()
    _upsert_manual_attribution_metrics(cursor, str(post.get("id") or ""))
    metrics = _attribution_metrics_for_post(cursor, str(post.get("id") or ""))
    return event, metrics


def collect_social_post_metrics(user_id: str, business_id: str = "", post_id: str = "") -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_social_post_tables(cursor)
        filters = ["sp.status = 'published'"]
        params: list[Any] = []
        if post_id:
            post = _load_post_for_user(cursor, user_id, post_id)
            filters.append("sp.id = %s")
            params.append(post.get("id"))
        elif business_id:
            _require_business_access(cursor, user_id, business_id)
            filters.append("sp.business_id = %s")
            params.append(business_id)
        else:
            raise ValueError("Нужен business_id или post_id")
        cursor.execute(
            f"""
            SELECT sp.*
            FROM social_posts sp
            WHERE {' AND '.join(filters)}
            """,
            tuple(params),
        )
        posts = [_serialize_social_post(cursor, row) for row in cursor.fetchall() or []]
        today = date.today()
        metric_details: list[dict[str, Any]] = []
        for post in posts:
            attribution_metrics = _attribution_metrics_for_post(cursor, str(post.get("id") or ""))
            provider_metrics = _collect_provider_metrics_for_post(cursor, post)
            metric_details.append(
                {
                    "id": str(post.get("id") or "").strip(),
                    "platform": str(post.get("platform") or "").strip(),
                    "provider": str(provider_metrics.get("provider") or post.get("platform") or "").strip(),
                    "source": str(provider_metrics.get("source") or "manual_attribution_only").strip(),
                    "status": str(provider_metrics.get("status") or "manual_attribution_only").strip(),
                    "views": max(int(attribution_metrics.get("views", 0) or 0), int(provider_metrics.get("views", 0) or 0)),
                    "likes": max(int(attribution_metrics.get("likes", 0) or 0), int(provider_metrics.get("likes", 0) or 0)),
                    "comments": max(int(attribution_metrics.get("comments", 0) or 0), int(provider_metrics.get("comments", 0) or 0)),
                    "shares": max(int(attribution_metrics.get("shares", 0) or 0), int(provider_metrics.get("shares", 0) or 0)),
                    "clicks": int(attribution_metrics.get("clicks", 0) or 0),
                    "inquiries": int(attribution_metrics.get("inquiries", 0) or 0),
                    "leads": int(attribution_metrics.get("leads", 0) or 0),
                    "error": str(provider_metrics.get("error") or "").strip()[:500],
                }
            )
            cursor.execute(
                """
                INSERT INTO social_post_metrics (
                    id, social_post_id, metric_date, views, impressions, reach, likes, comments, shares, clicks, inquiries, leads, raw_json, captured_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (social_post_id, metric_date)
                DO UPDATE SET
                    views = GREATEST(social_post_metrics.views, EXCLUDED.views),
                    impressions = GREATEST(social_post_metrics.impressions, EXCLUDED.impressions),
                    reach = GREATEST(social_post_metrics.reach, EXCLUDED.reach),
                    likes = GREATEST(social_post_metrics.likes, EXCLUDED.likes),
                    comments = GREATEST(social_post_metrics.comments, EXCLUDED.comments),
                    shares = GREATEST(social_post_metrics.shares, EXCLUDED.shares),
                    clicks = GREATEST(social_post_metrics.clicks, EXCLUDED.clicks),
                    inquiries = GREATEST(social_post_metrics.inquiries, EXCLUDED.inquiries),
                    leads = GREATEST(social_post_metrics.leads, EXCLUDED.leads),
                    raw_json = EXCLUDED.raw_json,
                    captured_at = NOW()
                """,
                (
                    _new_id(),
                    post.get("id"),
                    today,
                    max(int(attribution_metrics.get("views", 0) or 0), int(provider_metrics.get("views", 0) or 0)),
                    max(int(attribution_metrics.get("views", 0) or 0), int(provider_metrics.get("impressions", 0) or 0)),
                    max(int(attribution_metrics.get("views", 0) or 0), int(provider_metrics.get("reach", 0) or 0)),
                    max(int(attribution_metrics.get("likes", 0) or 0), int(provider_metrics.get("likes", 0) or 0)),
                    max(int(attribution_metrics.get("comments", 0) or 0), int(provider_metrics.get("comments", 0) or 0)),
                    max(int(attribution_metrics.get("shares", 0) or 0), int(provider_metrics.get("shares", 0) or 0)),
                    attribution_metrics.get("clicks", 0),
                    attribution_metrics.get("inquiries", 0),
                    attribution_metrics.get("leads", 0),
                    _json_dumps(
                        {
                            "collector": "provider_metrics_v1",
                            "attribution": attribution_metrics,
                            "provider_metrics": provider_metrics,
                        }
                    ),
                ),
            )
        posts_with_metrics = _merge_metric_totals_into_posts(cursor, posts)
        db.conn.commit()
        return {
            "collected": len(posts_with_metrics),
            "posts": posts_with_metrics,
            "metric_details": metric_details,
            "recommendation": _build_plan_recommendation(posts_with_metrics),
        }
    except Exception:
        db.conn.rollback()
        raise sys.exc_info()[1]
    finally:
        db.close()


def _social_dispatch_business_scope(business_id: str = "") -> str:
    return str(business_id or os.getenv("SOCIAL_POST_DISPATCH_BUSINESS_ID") or "").strip()


def _social_metrics_business_scope(business_id: str = "") -> str:
    return str(business_id or os.getenv("SOCIAL_POST_METRICS_BUSINESS_ID") or "").strip()


def _social_dispatch_allow_unscoped() -> bool:
    return str(os.getenv("SOCIAL_POST_DISPATCH_ALLOW_UNSCOPED") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
        "enabled",
    }


def _social_metrics_allow_unscoped() -> bool:
    return str(os.getenv("SOCIAL_POST_METRICS_ALLOW_UNSCOPED") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
        "enabled",
    }


def _social_bool_env(name: str) -> bool:
    return str(os.getenv(name) or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
        "enabled",
    }


def _social_launch_runtime_alignment(business_id: str) -> dict[str, Any]:
    scope = str(business_id or "").strip()
    dispatch_scope = str(os.getenv("SOCIAL_POST_DISPATCH_BUSINESS_ID") or "").strip()
    dispatch_enabled = _social_bool_env("SOCIAL_POST_DISPATCH_ENABLED")
    dispatch_allow_unscoped = _social_dispatch_allow_unscoped()
    metrics_scope = str(os.getenv("SOCIAL_POST_METRICS_BUSINESS_ID") or "").strip()
    metrics_enabled = _social_bool_env("SOCIAL_POST_METRICS_ENABLED")
    metrics_allow_unscoped = _social_metrics_allow_unscoped()

    if not dispatch_enabled:
        dispatch_status = "dispatch_disabled"
    elif dispatch_scope and dispatch_scope == scope:
        dispatch_status = "ready"
    elif dispatch_scope and dispatch_scope != scope:
        dispatch_status = "scope_mismatch"
    elif dispatch_allow_unscoped:
        dispatch_status = "unscoped_allowed"
    else:
        dispatch_status = "blocked_without_scope"

    if not metrics_enabled:
        metrics_status = "metrics_disabled"
    elif metrics_scope and metrics_scope == scope:
        metrics_status = "ready"
    elif metrics_scope and metrics_scope != scope:
        metrics_status = "scope_mismatch"
    elif metrics_allow_unscoped:
        metrics_status = "unscoped_allowed"
    else:
        metrics_status = "blocked_without_scope"

    dispatch_can_process_this_business = dispatch_status in {"ready", "unscoped_allowed"}
    metrics_can_collect_this_business = metrics_status in {"ready", "unscoped_allowed"}
    return {
        "schema": "localos_social_launch_runtime_alignment_v1",
        "business_id": scope,
        "dispatch": {
            "enabled": dispatch_enabled,
            "business_scope": dispatch_scope,
            "allow_unscoped": dispatch_allow_unscoped,
            "status": dispatch_status,
            "can_process_this_business": dispatch_can_process_this_business,
            "message_ru": _social_launch_runtime_message("dispatch", dispatch_status, dispatch_scope, scope, True),
            "message_en": _social_launch_runtime_message("dispatch", dispatch_status, dispatch_scope, scope, False),
        },
        "metrics": {
            "enabled": metrics_enabled,
            "business_scope": metrics_scope,
            "allow_unscoped": metrics_allow_unscoped,
            "status": metrics_status,
            "can_collect_this_business": metrics_can_collect_this_business,
            "message_ru": _social_launch_runtime_message("metrics", metrics_status, metrics_scope, scope, True),
            "message_en": _social_launch_runtime_message("metrics", metrics_status, metrics_scope, scope, False),
        },
        "next_action_ru": _social_launch_runtime_next_action(dispatch_status, metrics_status, scope, True),
        "next_action_en": _social_launch_runtime_next_action(dispatch_status, metrics_status, scope, False),
    }


def _social_launch_runtime_message(kind: str, status: str, runtime_scope: str, business_scope: str, is_ru: bool) -> str:
    label_ru = "Dispatch" if kind == "dispatch" else "Сбор реакций"
    label_en = "Dispatch" if kind == "dispatch" else "Metrics"
    label = label_ru if is_ru else label_en
    if status in {"dispatch_disabled", "metrics_disabled"}:
        return (
            f"{label} выключен: можно готовить и ставить посты в расписание, но внешний цикл сам не стартует."
            if is_ru
            else f"{label} is disabled: posts can be prepared and queued, but the external loop will not start by itself."
        )
    if status == "ready":
        return (
            f"{label} включён для этого бизнеса ({business_scope})."
            if is_ru
            else f"{label} is enabled for this business ({business_scope})."
        )
    if status == "scope_mismatch":
        return (
            f"{label} включён для другого бизнеса ({runtime_scope}); текущий бизнес {business_scope} не будет обработан."
            if is_ru
            else f"{label} is scoped to another business ({runtime_scope}); current business {business_scope} will not be processed."
        )
    if status == "unscoped_allowed":
        return (
            f"{label} включён без scope через явный allow-all; для первого запуска безопаснее указать business scope."
            if is_ru
            else f"{label} is enabled without a scope via explicit allow-all; a business scope is safer for the first launch."
        )
    return (
        f"{label} включён, но заблокирован защитой: нужен business scope."
        if is_ru
        else f"{label} is enabled but guarded: a business scope is required."
    )


def _social_launch_runtime_next_action(dispatch_status: str, metrics_status: str, business_scope: str, is_ru: bool) -> str:
    if dispatch_status == "dispatch_disabled":
        return (
            f"Для автозапуска включите SOCIAL_POST_DISPATCH_ENABLED=true и SOCIAL_POST_DISPATCH_BUSINESS_ID={business_scope}."
            if is_ru
            else f"To auto-run, enable SOCIAL_POST_DISPATCH_ENABLED=true and SOCIAL_POST_DISPATCH_BUSINESS_ID={business_scope}."
        )
    if dispatch_status == "blocked_without_scope":
        return (
            f"Добавьте SOCIAL_POST_DISPATCH_BUSINESS_ID={business_scope}, иначе исполнитель не начнёт внешние действия."
            if is_ru
            else f"Add SOCIAL_POST_DISPATCH_BUSINESS_ID={business_scope}; otherwise the worker will not start external actions."
        )
    if dispatch_status == "scope_mismatch":
        return (
            f"Смените SOCIAL_POST_DISPATCH_BUSINESS_ID на {business_scope} или запускайте другой бизнес."
            if is_ru
            else f"Change SOCIAL_POST_DISPATCH_BUSINESS_ID to {business_scope} or run the other business."
        )
    if metrics_status in {"metrics_disabled", "blocked_without_scope", "scope_mismatch"}:
        return (
            "Публикации можно исполнять, но для learning loop отдельно включите сбор реакций с тем же business scope."
            if is_ru
            else "Publishing can run, but enable metrics with the same business scope to close the learning loop."
        )
    return (
        "Исполнитель совпадает с текущим бизнесом: после подтверждения и расписания он может выполнить первый цикл."
        if is_ru
        else "Runtime matches this business: after approval and queueing, the worker can run the first cycle."
    )


def dispatch_due_social_posts(batch_size: int = 20, business_id: str = "") -> dict[str, Any]:
    picked: list[dict[str, Any]] = []
    business_scope = _social_dispatch_business_scope(business_id)
    if not business_scope and not _social_dispatch_allow_unscoped():
        return {
            "picked": 0,
            "published": 0,
            "supervised": 0,
            "manual": 0,
            "failed": 0,
            "by_status": {},
            "by_action": {"blocked_without_scope": 1},
            "details": [],
            "errors": [],
            "posts": [],
            "business_scope": "",
            "blocked": True,
            "blocked_reason": "business_scope_required",
            "message": "SOCIAL_POST_DISPATCH_BUSINESS_ID is required unless SOCIAL_POST_DISPATCH_ALLOW_UNSCOPED=true.",
        }
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_social_post_tables(cursor)
        scope_clause = "AND sp.business_id = %s" if business_scope else ""
        params: list[Any] = []
        if business_scope:
            params.append(business_scope)
        params.append(max(1, min(int(batch_size or 20), 200)))
        cursor.execute(
            f"""
            SELECT sp.id, sp.business_id, sp.platform, sp.status, sp.scheduled_for
            FROM social_posts sp
            WHERE sp.status = 'queued'
              AND sp.approved_at IS NOT NULL
              AND COALESCE(sp.scheduled_for, NOW()) <= NOW()
              {scope_clause}
            ORDER BY sp.scheduled_for ASC NULLS FIRST, sp.updated_at ASC
            LIMIT %s
            """,
            tuple(params),
        )
        picked = [_row_to_dict(cursor, row) for row in cursor.fetchall() or []]
    finally:
        db.close()

    published = 0
    supervised = 0
    manual = 0
    failed = 0
    errors: list[dict[str, str]] = []
    posts: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []
    by_status: dict[str, int] = {}
    by_action: dict[str, int] = {}
    for item in picked:
        post_id = str(item.get("id") or "").strip()
        business_id = str(item.get("business_id") or "").strip()
        owner_id = ""
        try:
            owner_id = _owner_id_for_business(business_id)
            if not owner_id:
                raise RuntimeError("business owner not found")
            post = _dispatch_live_api_preflight_block(owner_id, post_id) or publish_social_post(owner_id, post_id)
            posts.append(post)
            status = str(post.get("status") or "").strip()
            action = _dispatch_action_for_status(status)
            by_status[status or "unknown"] = by_status.get(status or "unknown", 0) + 1
            by_action[action] = by_action.get(action, 0) + 1
            details.append(
                {
                    "id": post_id,
                    "business_id": business_id,
                    "platform": str(post.get("platform") or item.get("platform") or "").strip(),
                    "status": status,
                    "action": action,
                    "automation_task_id": str(post.get("automation_task_id") or "").strip(),
                    "provider_post_id": str(post.get("provider_post_id") or "").strip(),
                    "provider_post_url": str(post.get("provider_post_url") or "").strip(),
                    "last_error": str(post.get("last_error") or "").strip(),
                }
            )
            if status == "published":
                published += 1
            elif status == "needs_supervised_publish":
                supervised += 1
            elif status == "needs_manual_publish":
                manual += 1
            elif status == "failed":
                failed += 1
        except Exception:
            failed += 1
            message = str(sys.exc_info()[1])
            errors.append({"id": post_id, "error": message})
            by_status["failed"] = by_status.get("failed", 0) + 1
            by_action["failed"] = by_action.get("failed", 0) + 1
            details.append(
                {
                    "id": post_id,
                    "business_id": business_id,
                    "platform": str(item.get("platform") or "").strip(),
                    "status": "failed",
                    "action": "failed",
                    "automation_task_id": "",
                    "provider_post_id": "",
                    "provider_post_url": "",
                    "last_error": message,
                }
            )
            _mark_dispatch_failure(post_id, message)
    return {
        "picked": len(picked),
        "published": published,
        "supervised": supervised,
        "manual": manual,
        "failed": failed,
        "by_status": by_status,
        "by_action": by_action,
        "details": details,
        "errors": errors,
        "posts": posts,
        "business_scope": business_scope,
        "followup_actions_ru": _social_dispatch_followup_actions(
            len(picked), published, supervised, manual, failed, errors, True
        ),
        "followup_actions_en": _social_dispatch_followup_actions(
            len(picked), published, supervised, manual, failed, errors, False
        ),
        "result_summaries_ru": _social_dispatch_result_summaries(details, True),
        "result_summaries_en": _social_dispatch_result_summaries(details, False),
    }


def _dispatch_live_api_preflight_block(user_id: str, post_id: str) -> dict[str, Any] | None:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_social_post_tables(cursor)
        post = _load_post_for_user(cursor, user_id, post_id)
        platform = str(post.get("platform") or "").strip()
        publish_mode = str(post.get("publish_mode") or "").strip()
        if platform not in API_PLATFORMS or publish_mode != "api":
            return None
        preflight = _api_channel_preflight_for_platform(cursor, str(post.get("business_id") or ""), platform)
        if bool(preflight.get("ready")):
            return None
        status = str(preflight.get("status") or "not_ready").strip()
        metadata = _json_dict(post.get("metadata_json"))
        metadata.update(
            {
                "provider_status": status,
                "queue_preflight_status": status,
                "queue_preflight_ready": False,
                "queue_preflight_live_checked_at": datetime.now(timezone.utc).isoformat(),
                "queue_preflight_source": "worker_dispatch_live_api_preflight",
                "queue_preflight_message_ru": str(preflight.get("message_ru") or "").strip(),
                "queue_preflight_message_en": str(preflight.get("message_en") or "").strip(),
            }
        )
        cursor.execute(
            """
            UPDATE social_posts
            SET status = 'needs_manual_publish',
                metadata_json = %s,
                last_error = %s,
                updated_at = NOW()
            WHERE id = %s
            RETURNING *
            """,
            (
                _json_dumps(metadata),
                _queue_preflight_error(platform, status),
                post_id,
            ),
        )
        updated = _serialize_social_post(cursor, cursor.fetchone())
        db.conn.commit()
        return updated
    except Exception:
        db.conn.rollback()
        raise sys.exc_info()[1]
    finally:
        db.close()


def run_scoped_social_dispatch_once(
    user_id: str,
    business_id: str,
    batch_size: int = 10,
    approved: bool = False,
    approval_text: str = "",
) -> dict[str, Any]:
    if not approved:
        raise PermissionError("Для запуска первого цикла публикаций нужно явное подтверждение")
    normalized_business_id = str(business_id or "").strip()
    if not normalized_business_id:
        raise ValueError("Бизнес не выбран")
    clean_batch_size = max(1, min(int(batch_size or 10), 50))
    preflight = get_social_launch_preflight(user_id, normalized_business_id, batch_size=clean_batch_size)
    launch_gate = preflight.get("launch_gate") if isinstance(preflight.get("launch_gate"), dict) else {}
    if launch_gate and not bool(launch_gate.get("allowed")):
        raise PermissionError(
            str(launch_gate.get("next_action_ru") or "").strip()
            or "Preflight не разрешил запуск первого scoped цикла"
        )
    summary = preflight.get("summary") if isinstance(preflight.get("summary"), dict) else {}
    if int(summary.get("skipped_no_access") or 0) > 0:
        raise PermissionError("Есть посты на текущую дату вне доступа текущего пользователя; проверьте бизнес для запуска")
    if int(summary.get("api_preflight_blocked_due_posts") or 0) > 0:
        raise PermissionError("Live API-проверка нашла неготовый канал; исправьте ключи/права или переведите пост в ручной режим")
    api_due_posts = int(summary.get("api_due_posts") or launch_gate.get("api_posts") or 0)
    if api_due_posts > 0 and not _social_external_publish_confirmation_matches(approval_text):
        phrase = _social_external_publish_confirmation_phrase()
        raise PermissionError(f"Для API-публикации подтвердите внешний запуск фразой: {phrase}")
    dispatch_result = dispatch_due_social_posts(
        batch_size=clean_batch_size,
        business_id=normalized_business_id,
    )
    execution_report = _social_dispatch_execution_report(dispatch_result)
    return {
        "approved": True,
        "business_id": normalized_business_id,
        "batch_size": clean_batch_size,
        "preflight": preflight,
        "dispatch_result": dispatch_result,
        "execution_report": execution_report,
        "external_publish_only_after_approval": True,
        "external_publish_confirmation_phrase": _social_external_publish_confirmation_phrase() if api_due_posts > 0 else "",
        "browser_final_click_allowed": False,
        "maps_are_supervised_or_manual": True,
        "message_ru": _social_dispatch_once_message(dispatch_result, True),
        "message_en": _social_dispatch_once_message(dispatch_result, False),
    }


def _social_external_publish_confirmation_phrase() -> str:
    return "ПУБЛИКУЮ"


def _social_external_publish_confirmation_matches(value: str) -> bool:
    return str(value or "").strip().upper() == _social_external_publish_confirmation_phrase()


def run_scoped_social_metrics_once(
    user_id: str,
    business_id: str,
    batch_size: int = 25,
    approved: bool = False,
) -> dict[str, Any]:
    if not approved:
        raise PermissionError("Для сбора реакций нужно явное подтверждение")
    normalized_business_id = str(business_id or "").strip()
    if not normalized_business_id:
        raise ValueError("Бизнес не выбран")
    clean_batch_size = max(1, min(int(batch_size or 25), 100))
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_social_post_tables(cursor)
        _require_business_access(cursor, user_id, normalized_business_id)
    finally:
        db.close()
    metrics_result = collect_due_social_post_metrics(
        batch_size=clean_batch_size,
        business_id=normalized_business_id,
    )
    return {
        "approved": True,
        "business_id": normalized_business_id,
        "batch_size": clean_batch_size,
        "metrics_result": metrics_result,
        "metrics_learning_packet": _social_metrics_learning_packet(metrics_result),
        "external_publish_performed": False,
        "message_ru": _social_metrics_once_message(metrics_result, True),
        "message_en": _social_metrics_once_message(metrics_result, False),
    }


def _social_dispatch_once_message(result: dict[str, Any], is_ru: bool) -> str:
    picked = int(result.get("picked") or 0)
    published = int(result.get("published") or 0)
    supervised = int(result.get("supervised") or 0)
    manual = int(result.get("manual") or 0)
    failed = int(result.get("failed") or 0)
    if picked <= 0:
        return (
            "Due-постов для этого бизнеса нет; внешний запуск ничего не отправил."
            if is_ru
            else "There are no due posts for this business; no external action was sent."
        )
    if is_ru:
        return (
            f"Первый scoped цикл выполнен: взято {picked}, опубликовано {published}, "
            f"контролируемое размещение {supervised}, вручную {manual}, ошибок {failed}."
        )
    return (
        f"First scoped cycle finished: picked {picked}, published {published}, "
        f"supervised {supervised}, manual {manual}, failed {failed}."
    )


def _social_dispatch_execution_report(dispatch_result: dict[str, Any]) -> dict[str, Any]:
    details = dispatch_result.get("details") if isinstance(dispatch_result.get("details"), list) else []
    by_status = dispatch_result.get("by_status") if isinstance(dispatch_result.get("by_status"), dict) else {}
    by_action = dispatch_result.get("by_action") if isinstance(dispatch_result.get("by_action"), dict) else {}
    errors = dispatch_result.get("errors") if isinstance(dispatch_result.get("errors"), list) else []
    picked = int(dispatch_result.get("picked") or 0)
    published = int(dispatch_result.get("published") or 0)
    supervised = int(dispatch_result.get("supervised") or 0)
    manual = int(dispatch_result.get("manual") or 0)
    failed = int(dispatch_result.get("failed") or 0)
    status = "empty"
    if failed > 0:
        status = "attention"
    elif manual > 0:
        status = "manual_action_needed"
    elif picked > 0:
        status = "completed"
    first_api_proof_summary = _social_dispatch_first_api_proof_summary(details)
    post_publish_learning_gate = _social_post_publish_learning_gate(details, first_api_proof_summary)
    return {
        "schema": "localos_social_dispatch_execution_report_v1",
        "status": status,
        "picked": picked,
        "published": published,
        "supervised": supervised,
        "manual": manual,
        "failed": failed,
        "business_scope": str(dispatch_result.get("business_scope") or "").strip(),
        "by_status": by_status,
        "by_action": by_action,
        "details": details,
        "errors": errors,
        "external_publish_only_after_approval": True,
        "maps_are_supervised_or_manual": True,
        "browser_final_click_allowed": False,
        "provider_write_summary": {
            "api_publish_attempted": published > 0 or bool(by_action.get("failed")),
            "published_with_provider_proof": len(
                [
                    item for item in details
                    if str(item.get("status") or "").strip() == "published"
                    and (
                        str(item.get("provider_post_id") or "").strip()
                        or str(item.get("provider_post_url") or "").strip()
                    )
                ]
            ),
            "supervised_tasks_created": len(
                [
                    item for item in details
                    if str(item.get("status") or "").strip() == "needs_supervised_publish"
                    and str(item.get("automation_task_id") or "").strip()
                ]
            ),
        },
        "first_api_proof_summary": first_api_proof_summary,
        "post_publish_learning_gate": post_publish_learning_gate,
        "after_run_proof_packet": _social_after_run_proof_packet(
            status,
            picked,
            published,
            supervised,
            manual,
            failed,
            first_api_proof_summary,
            post_publish_learning_gate,
        ),
        "title_ru": _social_dispatch_execution_title(status, True),
        "title_en": _social_dispatch_execution_title(status, False),
        "summary_ru": _social_dispatch_execution_summary(picked, published, supervised, manual, failed, True),
        "summary_en": _social_dispatch_execution_summary(picked, published, supervised, manual, failed, False),
        "next_action_ru": _social_dispatch_execution_next_action(status, errors, True),
        "next_action_en": _social_dispatch_execution_next_action(status, errors, False),
    }


def _social_after_run_proof_packet(
    status: str,
    picked: int,
    published: int,
    supervised: int,
    manual: int,
    failed: int,
    first_api_proof_summary: dict[str, Any],
    post_publish_learning_gate: dict[str, Any],
) -> dict[str, Any]:
    api_proof_ready = bool(first_api_proof_summary.get("ready"))
    can_collect = bool(post_publish_learning_gate.get("can_collect_metrics"))
    has_maps_handoff = int(supervised or 0) > 0 or int(manual or 0) > 0
    has_failures = int(failed or 0) > 0
    if has_failures:
        proof_status = "needs_recovery"
    elif api_proof_ready and can_collect:
        proof_status = "loop_proven_collect_results"
    elif can_collect:
        proof_status = "published_collect_results"
    elif has_maps_handoff:
        proof_status = "finish_maps_handoff"
    elif int(picked or 0) <= 0:
        proof_status = "no_due_posts"
    else:
        proof_status = "check_details"
    return {
        "schema": "localos_social_after_run_proof_packet_v1",
        "status": proof_status,
        "dispatch_status": str(status or "").strip(),
        "picked": int(picked or 0),
        "published": int(published or 0),
        "supervised": int(supervised or 0),
        "manual": int(manual or 0),
        "failed": int(failed or 0),
        "api_proof_ready": api_proof_ready,
        "can_collect_results": can_collect,
        "maps_handoff_created": has_maps_handoff,
        "browser_final_click_allowed": False,
        "primary_metric_ru": "Заявки и обращения",
        "primary_metric_en": "Leads and inquiries",
        "title_ru": _social_after_run_proof_title(proof_status, True),
        "title_en": _social_after_run_proof_title(proof_status, False),
        "next_action_ru": _social_after_run_proof_next_action(proof_status, True),
        "next_action_en": _social_after_run_proof_next_action(proof_status, False),
        "checks_ru": _social_after_run_proof_checks(proof_status, True),
        "checks_en": _social_after_run_proof_checks(proof_status, False),
    }


def _social_after_run_proof_title(status: str, is_ru: bool) -> str:
    if status == "loop_proven_collect_results":
        return "Цикл доказан: собирайте результат" if is_ru else "Loop proven: collect results"
    if status == "published_collect_results":
        return "Пост опубликован: добавьте proof и результат" if is_ru else "Post published: add proof and results"
    if status == "finish_maps_handoff":
        return "Карты ждут контролируемое размещение" if is_ru else "Maps wait for supervised placement"
    if status == "needs_recovery":
        return "Есть ошибки запуска" if is_ru else "Launch has errors"
    if status == "no_due_posts":
        return "На текущую дату нечего запускать" if is_ru else "No due posts to run"
    return "Проверьте детали запуска" if is_ru else "Check launch details"


def _social_after_run_proof_next_action(status: str, is_ru: bool) -> str:
    if status == "loop_proven_collect_results":
        return (
            "Нажмите “Собрать реакции”, отметьте заявки/обращения и откройте предложения следующего плана."
            if is_ru
            else "Click “Collect reactions”, record leads/inquiries, and open next-plan suggestions."
        )
    if status == "published_collect_results":
        return (
            "Сохраните provider_post_id/provider_post_url, затем соберите реакции и отметьте заявки."
            if is_ru
            else "Save provider_post_id/provider_post_url, then collect reactions and record leads."
        )
    if status == "finish_maps_handoff":
        return (
            "Откройте пакет размещения Яндекс/2ГИС, завершите публикацию человеком и отметьте размещённым."
            if is_ru
            else "Open the Yandex/2GIS placement packet, finish publishing as a human, and mark it published."
        )
    if status == "needs_recovery":
        return (
            "Откройте ошибочные посты, исправьте ключи/права или переведите в ручной режим."
            if is_ru
            else "Open failed posts, fix keys/permissions, or move them to manual mode."
        )
    if status == "no_due_posts":
        return (
            "Подтвердите посты, поставьте их в расписание на текущую дату и повторите запуск."
            if is_ru
            else "Approve posts, queue them for the current date, and run again."
        )
    return (
        "Сверьте статусы published/failed/needs_supervised_publish и обновите результат."
        if is_ru
        else "Check published/failed/needs_supervised_publish statuses and update results."
    )


def _social_after_run_proof_checks(status: str, is_ru: bool) -> list[str]:
    if is_ru:
        return [
            "Сверьте provider_post_id/provider_post_url для API-поста.",
            "Проверьте, что Яндекс/2ГИС не были автопубликованы без человека.",
            "Соберите реакции и вручную отметьте заявки/обращения.",
            "Откройте рекомендации следующего плана только после результата.",
        ]
    return [
        "Verify provider_post_id/provider_post_url for the API post.",
        "Confirm Yandex/2GIS were not autopublished without a human.",
        "Collect reactions and manually record leads/inquiries.",
        "Open next-plan recommendations only after results exist.",
    ]


def _social_post_publish_learning_gate(
    details: list[dict[str, Any]],
    first_api_proof_summary: dict[str, Any],
) -> dict[str, Any]:
    published_items = [
        item for item in details or []
        if str(item.get("status") or "").strip() == "published"
    ]
    failed_items = [
        item for item in details or []
        if str(item.get("status") or "").strip() == "failed"
    ]
    manual_or_supervised = [
        item for item in details or []
        if str(item.get("status") or "").strip() in {"needs_manual_publish", "needs_supervised_publish"}
    ]
    proof_ready = bool(first_api_proof_summary.get("ready"))
    can_collect = len(published_items) > 0
    if proof_ready:
        status = "ready_for_metrics_and_attribution"
    elif can_collect:
        status = "published_without_api_proof"
    elif manual_or_supervised:
        status = "finish_supervised_or_manual_publish"
    elif failed_items:
        status = "fix_failed_publish"
    else:
        status = "publish_first"
    return {
        "schema": "localos_social_post_publish_learning_gate_v1",
        "status": status,
        "allowed": can_collect,
        "can_collect_metrics": can_collect,
        "can_record_attribution": can_collect,
        "api_proof_ready": proof_ready,
        "published_posts": len(published_items),
        "published_with_api_proof": int(first_api_proof_summary.get("published_with_provider_proof") or 0),
        "manual_or_supervised_posts": len(manual_or_supervised),
        "failed_posts": len(failed_items),
        "primary_metric_ru": "Заявки и обращения",
        "primary_metric_en": "Leads and inquiries",
        "external_publish_performed": False,
        "summary_ru": _social_post_publish_learning_gate_summary(status, True),
        "summary_en": _social_post_publish_learning_gate_summary(status, False),
        "next_action_ru": _social_post_publish_learning_gate_next_action(status, True),
        "next_action_en": _social_post_publish_learning_gate_next_action(status, False),
        "learning_actions": _social_post_publish_learning_actions(status),
    }


def _social_post_publish_learning_actions(status: str) -> list[dict[str, Any]]:
    if status in {"ready_for_metrics_and_attribution", "published_without_api_proof"}:
        return [
            {
                "key": "collect_reactions",
                "order": 1,
                "enabled": True,
                "label_ru": "Собрать реакции",
                "label_en": "Collect reactions",
                "summary_ru": "Обновить просмотры, комментарии и доступные provider-метрики без новой публикации.",
                "summary_en": "Update views, comments, and available provider metrics without publishing again.",
                "primary_metric": False,
            },
            {
                "key": "record_leads",
                "order": 2,
                "enabled": True,
                "label_ru": "Отметить заявки/обращения",
                "label_en": "Record leads/inquiries",
                "summary_ru": "Главный KPI: заявки и обращения важнее охватов и лайков.",
                "summary_en": "Main KPI: leads and inquiries matter more than reach and likes.",
                "primary_metric": True,
            },
            {
                "key": "recommend_next_plan",
                "order": 3,
                "enabled": True,
                "label_ru": "Предложить изменения следующего плана",
                "label_en": "Suggest next-plan changes",
                "summary_ru": "LocalOS предлагает изменения, но не применяет их без подтверждения.",
                "summary_en": "LocalOS suggests changes but does not apply them without approval.",
                "primary_metric": False,
            },
        ]
    if status == "finish_supervised_or_manual_publish":
        return [
            {
                "key": "finish_manual_or_supervised_publish",
                "order": 1,
                "enabled": True,
                "label_ru": "Завершить ручное/контролируемое размещение",
                "label_en": "Finish manual/supervised placement",
                "summary_ru": "Сначала разместите пост на площадке человеком и сохраните ссылку или ID.",
                "summary_en": "Publish on the platform as a human first and save the URL or ID.",
                "primary_metric": False,
            }
        ]
    if status == "fix_failed_publish":
        return [
            {
                "key": "recover_failed_publish",
                "order": 1,
                "enabled": True,
                "label_ru": "Исправить ошибку публикации",
                "label_en": "Recover failed publish",
                "summary_ru": "Проверьте ключи, права или переведите пост в ручной режим.",
                "summary_en": "Check keys, permissions, or move the post to manual flow.",
                "primary_metric": False,
            }
        ]
    return [
        {
            "key": "publish_first",
            "order": 1,
            "enabled": False,
            "label_ru": "Сначала опубликовать пост",
            "label_en": "Publish a post first",
            "summary_ru": "Сбор результата появится после published или ручной отметки размещения.",
            "summary_en": "Result collection appears after published status or manual publish marking.",
            "primary_metric": False,
        }
    ]


def _social_post_publish_learning_gate_summary(status: str, is_ru: bool) -> str:
    if status == "ready_for_metrics_and_attribution":
        return (
            "API-публикация доказана: можно собирать реакции и отмечать заявки/обращения."
            if is_ru
            else "API publishing is proven: collect reactions and record leads/inquiries."
        )
    if status == "published_without_api_proof":
        return (
            "Есть опубликованные посты, но первый API-proof неполный: сохраните ссылку или provider ID, затем собирайте реакции."
            if is_ru
            else "Published posts exist, but first API proof is incomplete: save URL or provider ID, then collect reactions."
        )
    if status == "finish_supervised_or_manual_publish":
        return (
            "Сначала завершите контролируемое или ручное размещение и отметьте публикацию."
            if is_ru
            else "Finish supervised/manual placement and mark the post as published first."
        )
    if status == "fix_failed_publish":
        return (
            "Публикация упала: исправьте канал или переведите пост в ручной режим."
            if is_ru
            else "Publishing failed: fix the channel or move the post to manual flow."
        )
    return (
        "Сначала опубликуйте хотя бы один approved/queued пост."
        if is_ru
        else "Publish at least one approved/queued post first."
    )


def _social_post_publish_learning_gate_next_action(status: str, is_ru: bool) -> str:
    if status == "ready_for_metrics_and_attribution":
        return (
            "Нажмите “Собрать реакции”, затем отметьте заявки/обращения и откройте рекомендации следующего плана."
            if is_ru
            else "Click “Collect reactions”, then mark leads/inquiries and open next-plan recommendations."
        )
    if status == "published_without_api_proof":
        return (
            "Сохраните provider_post_id/provider_post_url или отметьте публикацию вручную, чтобы proof был проверяемым."
            if is_ru
            else "Save provider_post_id/provider_post_url or mark the publish manually so proof is verifiable."
        )
    if status == "finish_supervised_or_manual_publish":
        return (
            "Откройте контролируемое размещение или ручной режим; после фактической публикации сохраните ссылку/ID."
            if is_ru
            else "Open supervised placement or manual fallback; after the real publish, save URL/ID."
        )
    if status == "fix_failed_publish":
        return (
            "Откройте ошибочный пост, исправьте ключи/права или повторите публикацию после подтверждения."
            if is_ru
            else "Open the failed post, fix keys/permissions, or retry publishing after approval."
        )
    return (
        "Подготовьте, подтвердите и поставьте пост в расписание, затем запустите ограниченный цикл."
        if is_ru
        else "Prepare, approve, and queue a post, then run a scoped cycle."
    )


def _social_dispatch_first_api_proof_summary(details: list[dict[str, Any]]) -> dict[str, Any]:
    api_details = [
        item for item in details or []
        if str(item.get("platform") or "").strip() in API_PLATFORMS
    ]
    published_api = [
        item for item in api_details
        if str(item.get("status") or "").strip() == "published"
    ]
    proof_items = [
        item for item in published_api
        if str(item.get("provider_post_id") or "").strip()
        or str(item.get("provider_post_url") or "").strip()
    ]
    first = proof_items[0] if proof_items else (published_api[0] if published_api else (api_details[0] if api_details else {}))
    platform = str(first.get("platform") or "").strip()
    label = str(first.get("platform_label") or platform_label(platform)).strip() if platform else ""
    ready = bool(proof_items)
    return {
        "schema": "localos_social_first_api_proof_summary_v1",
        "ready": ready,
        "api_posts_checked": len(api_details),
        "published_api_posts": len(published_api),
        "published_with_provider_proof": len(proof_items),
        "platform": platform,
        "platform_label": label,
        "post_id": str(first.get("id") or "").strip(),
        "provider_post_id": str(first.get("provider_post_id") or "").strip(),
        "provider_post_url": str(first.get("provider_post_url") or "").strip(),
        "last_error": str(first.get("last_error") or "").strip(),
        "required_proof_fields": ["provider_post_id", "provider_post_url"],
        "summary_ru": (
            f"Первый API-loop доказан: {label} сохранил provider_post_id/provider_post_url."
            if ready
            else "Первый API-loop ещё не доказан: нет published API-поста с provider_post_id/provider_post_url."
        ),
        "summary_en": (
            f"First API loop is proven: {label} saved provider_post_id/provider_post_url."
            if ready
            else "First API loop is not proven yet: no published API post has provider_post_id/provider_post_url."
        ),
        "next_action_ru": (
            "Соберите реакции/заявки и отметьте обращения перед корректировкой следующего плана."
            if ready
            else "Откройте details dispatch: если есть failed, исправьте канал; если published без proof, сохраните ссылку/ID вручную."
        ),
        "next_action_en": (
            "Collect reactions/leads and mark inquiries before adjusting the next plan."
            if ready
            else "Open dispatch details: if failed, fix the channel; if published without proof, save the URL/ID manually."
        ),
    }


def _social_dispatch_execution_title(status: str, is_ru: bool) -> str:
    if status == "completed":
        return "Цикл выполнен" if is_ru else "Cycle completed"
    if status == "manual_action_needed":
        return "Цикл выполнен, нужен ручной шаг" if is_ru else "Cycle completed, manual step needed"
    if status == "attention":
        return "Цикл выполнен с ошибками" if is_ru else "Cycle completed with errors"
    return "Due-постов не было" if is_ru else "No due posts"


def _social_dispatch_execution_summary(
    picked: int,
    published: int,
    supervised: int,
    manual: int,
    failed: int,
    is_ru: bool,
) -> str:
    if is_ru:
        return (
            f"Взято {picked}: опубликовано {published}, контролируемое размещение {supervised}, "
            f"вручную {manual}, ошибок {failed}."
        )
    return (
        f"Picked {picked}: published {published}, supervised {supervised}, manual {manual}, failed {failed}."
    )


def _social_dispatch_execution_next_action(status: str, errors: list[Any], is_ru: bool) -> str:
    if status == "completed":
        return (
            "Проверьте provider ID/URL у API-постов, завершите supervised preview для карт и затем соберите реакции."
            if is_ru
            else "Check provider IDs/URLs for API posts, finish supervised map previews, then collect reactions."
        )
    if status == "manual_action_needed":
        return (
            "Откройте ручные/контролируемые публикации, разместите их и отметьте результат."
            if is_ru
            else "Open manual/supervised posts, publish them, and mark the result."
        )
    if status == "attention":
        first_error = ""
        if errors and isinstance(errors[0], dict):
            first_error = str(errors[0].get("error") or "").strip()
        return (
            f"Разберите первую ошибку и повторите запуск для оставшихся постов на текущую дату: {first_error}".strip()
            if is_ru
            else f"Review the first error and rerun for remaining due posts: {first_error}".strip()
        )
    return (
        "Сначала поставьте утверждённые посты в расписание и дождитесь даты публикации."
        if is_ru
        else "Queue approved posts and wait for the due date first."
    )


def _social_dispatch_followup_actions(
    picked: int,
    published: int,
    supervised: int,
    manual: int,
    failed: int,
    errors: list[dict[str, str]] | None,
    is_ru: bool,
) -> list[str]:
    if picked <= 0:
        return [
            "Постов на текущую дату нет: сначала подготовьте, подтвердите и поставьте публикации в расписание."
            if is_ru
            else "No due posts: prepare, approve, and queue posts first."
        ]

    actions: list[str] = []
    if published > 0:
        actions.append(
            "Проверьте опубликованные API-посты: в карточке должны быть ссылка или provider ID."
            if is_ru
            else "Check published API posts: each card should have a URL or provider ID."
        )
    if supervised > 0:
        actions.append(
            "Завершите контролируемое размещение для Яндекс/2ГИС: финальный клик остаётся за человеком."
            if is_ru
            else "Finish supervised placement for Yandex/2GIS: the final click stays with a human."
        )
    if manual > 0:
        actions.append(
            "Откройте посты в ручном режиме: подключите ключи/права или разместите вручную и сохраните ссылку."
            if is_ru
            else "Open manual posts: connect keys/permissions or publish manually and save the URL."
        )
    if failed > 0:
        sample_error = ""
        if errors:
            sample_error = str((errors[0] or {}).get("error") or "").strip()
        if sample_error:
            actions.append(
                f"Есть ошибки запуска: {sample_error[:180]}. Исправьте причину и повторите ограниченный цикл."
                if is_ru
                else f"Dispatch has failures: {sample_error[:180]}. Fix the cause and rerun the scoped cycle."
            )
        else:
            actions.append(
                "Есть ошибки запуска: откройте карточки с ошибкой и выберите повтор или ручной режим."
                if is_ru
                else "Dispatch has failures: open failed cards and choose retry or manual fallback."
            )
    if not actions:
        actions.append(
            "Цикл завершён без внешних изменений: обновите очередь и проверьте даты публикаций."
            if is_ru
            else "The cycle finished without external changes: refresh the queue and check due dates."
        )
    actions.append(
        "После публикаций соберите реакции и отметьте заявки/обращения для корректировки следующего плана."
        if is_ru
        else "After publishing, collect reactions and mark leads/inquiries for next-plan correction."
    )
    return actions[:5]


def _social_dispatch_result_summaries(details: list[dict[str, Any]], is_ru: bool) -> list[str]:
    summaries: list[str] = []
    for item in (details or [])[:5]:
        platform = str(item.get("platform") or "").strip()
        label = platform_label(platform) if platform else ("Канал" if is_ru else "Channel")
        status = str(item.get("status") or "").strip()
        provider_url = str(item.get("provider_post_url") or "").strip()
        provider_id = str(item.get("provider_post_id") or "").strip()
        automation_task_id = str(item.get("automation_task_id") or "").strip()
        last_error = str(item.get("last_error") or "").strip()
        if status == "published":
            proof = provider_url or provider_id
            summaries.append(
                f"{label}: опубликовано" + (f", proof {proof}." if proof else ".")
                if is_ru
                else f"{label}: published" + (f", proof {proof}." if proof else ".")
            )
        elif status == "needs_supervised_publish":
            summaries.append(
                f"{label}: контролируемое размещение готово" + (f" ({automation_task_id})." if automation_task_id else ".")
                if is_ru
                else f"{label}: supervised placement is ready" + (f" ({automation_task_id})." if automation_task_id else ".")
            )
        elif status == "needs_manual_publish":
            reason = f": {last_error}" if last_error else ""
            summaries.append(
                f"{label}: нужен ручной шаг или подключение канала{reason}."
                if is_ru
                else f"{label}: manual step or channel connection is needed{reason}."
            )
        elif status == "failed":
            reason = f": {last_error}" if last_error else ""
            summaries.append(
                f"{label}: ошибка публикации{reason}."
                if is_ru
                else f"{label}: publishing failed{reason}."
            )
        else:
            summaries.append(
                f"{label}: статус после dispatch - {status or 'unknown'}."
                if is_ru
                else f"{label}: status after dispatch is {status or 'unknown'}."
            )
    if len(details or []) > 5:
        remaining = len(details or []) - 5
        summaries.append(
            f"Ещё {remaining} результатов смотрите в карточках постов."
            if is_ru
            else f"See {remaining} more results in post cards."
        )
    return summaries


def _social_metrics_once_message(result: dict[str, Any], is_ru: bool) -> str:
    if result.get("blocked"):
        return (
            "Сбор реакций заблокирован: нужен явный business scope."
            if is_ru
            else "Metrics collection is blocked: an explicit business scope is required."
        )
    picked = int(result.get("picked") or 0)
    collected = int(result.get("collected") or 0)
    failed = int(result.get("failed") or 0)
    if picked <= 0:
        return (
            "Новых опубликованных постов для сбора реакций нет."
            if is_ru
            else "There are no new published posts to collect reactions for."
        )
    if is_ru:
        return f"Сбор реакций выполнен: проверено {picked}, обновлено {collected}, ошибок {failed}."
    return f"Metrics collection finished: checked {picked}, updated {collected}, failed {failed}."


def _social_metrics_learning_packet(result: dict[str, Any]) -> dict[str, Any]:
    details = result.get("metric_details") if isinstance(result.get("metric_details"), list) else []
    leads = sum(int(item.get("leads") or 0) for item in details if isinstance(item, dict))
    inquiries = sum(int(item.get("inquiries") or 0) for item in details if isinstance(item, dict))
    comments = sum(int(item.get("comments") or 0) for item in details if isinstance(item, dict))
    shares = sum(int(item.get("shares") or 0) for item in details if isinstance(item, dict))
    clicks = sum(int(item.get("clicks") or 0) for item in details if isinstance(item, dict))
    likes = sum(int(item.get("likes") or 0) for item in details if isinstance(item, dict))
    views = sum(int(item.get("views") or 0) for item in details if isinstance(item, dict))
    failed = int(result.get("failed") or 0)
    collected = int(result.get("collected") or 0)
    primary_total = leads + inquiries
    early_total = comments + shares + clicks + likes + views
    if primary_total > 0:
        status = "ready_from_leads"
    elif early_total > 0:
        status = "early_signals_only"
    elif collected > 0:
        status = "collected_without_signals"
    elif failed > 0:
        status = "metrics_failed"
    else:
        status = "no_metrics_yet"
    return {
        "schema": "localos_social_metrics_learning_packet_v1",
        "status": status,
        "collected_posts": collected,
        "failed_posts": failed,
        "primary_metric_ru": "Заявки и обращения",
        "primary_metric_en": "Leads and inquiries",
        "primary_result_total": primary_total,
        "early_signal_total": early_total,
        "leads": leads,
        "inquiries": inquiries,
        "comments": comments,
        "shares": shares,
        "clicks": clicks,
        "likes": likes,
        "views": views,
        "safe_to_recommend_next_plan": primary_total > 0 or early_total > 0,
        "safe_to_apply_without_approval": False,
        "external_publish_performed": False,
        "summary_ru": _social_metrics_learning_summary(status, True),
        "summary_en": _social_metrics_learning_summary(status, False),
        "next_action_ru": _social_metrics_learning_next_action(status, True),
        "next_action_en": _social_metrics_learning_next_action(status, False),
    }


def _social_metrics_learning_summary(status: str, is_ru: bool) -> str:
    if status == "ready_from_leads":
        return (
            "Есть заявки или обращения: можно предлагать изменения следующего плана по главной метрике."
            if is_ru
            else "Leads or inquiries exist: next-plan changes can be suggested from the primary metric."
        )
    if status == "early_signals_only":
        return (
            "Есть ранние сигналы, но перед применением изменений проверьте заявки и обращения."
            if is_ru
            else "Early signals exist, but check leads and inquiries before applying changes."
        )
    if status == "collected_without_signals":
        return (
            "Метрики обновлены, но результата пока не видно: отметьте заявки/обращения вручную, если они были."
            if is_ru
            else "Metrics were updated, but no result is visible yet: manually record leads/inquiries if they happened."
        )
    if status == "metrics_failed":
        return (
            "Сбор реакций завершился с ошибками: исправьте доступы или используйте ручную разметку результата."
            if is_ru
            else "Metrics collection had errors: fix access or use manual result attribution."
        )
    return (
        "Сначала опубликуйте посты или отметьте результат вручную."
        if is_ru
        else "Publish posts or record results manually first."
    )


def _social_metrics_learning_next_action(status: str, is_ru: bool) -> str:
    if status == "ready_from_leads":
        return (
            "Откройте предложения следующего плана; применять их можно только после подтверждения."
            if is_ru
            else "Open next-plan suggestions; apply them only after approval."
        )
    if status == "early_signals_only":
        return (
            "Проверьте, были ли заявки/обращения, затем откройте рекомендации как предварительные."
            if is_ru
            else "Check whether leads/inquiries happened, then open recommendations as preliminary."
        )
    if status == "collected_without_signals":
        return (
            "Отметьте заявку, обращение или ранний сигнал на опубликованных постах."
            if is_ru
            else "Record a lead, inquiry, or early signal on published posts."
        )
    if status == "metrics_failed":
        return (
            "Откройте ошибки сбора метрик и исправьте канал или права."
            if is_ru
            else "Open metric collection errors and fix the channel or permissions."
        )
    return (
        "Подготовьте публикацию, дождитесь результата и повторите сбор реакций."
        if is_ru
        else "Prepare a post, wait for results, and collect reactions again."
    )


def _social_metrics_result_summaries(details: list[dict[str, Any]], is_ru: bool) -> list[str]:
    summaries: list[str] = []
    for item in (details or [])[:5]:
        platform = str(item.get("platform") or "").strip()
        label = platform_label(platform) if platform else ("Пост" if is_ru else "Post")
        source = str(item.get("source") or "").strip()
        status = str(item.get("status") or "").strip()
        error = str(item.get("error") or "").strip()
        leads = int(item.get("leads") or 0)
        inquiries = int(item.get("inquiries") or 0)
        comments = int(item.get("comments") or 0)
        reach = int(item.get("views") or item.get("reach") or 0)
        if status == "failed" or source == "collector_error":
            summaries.append(
                f"{label}: реакции не обновились" + (f": {error}." if error else ".")
                if is_ru
                else f"{label}: reactions were not updated" + (f": {error}." if error else ".")
            )
        elif source == "vk_api":
            summaries.append(
                f"{label}: API-снимок обновлён; заявки {leads}, обращения {inquiries}, комментарии {comments}, охват {reach}."
                if is_ru
                else f"{label}: API snapshot updated; leads {leads}, inquiries {inquiries}, comments {comments}, reach {reach}."
            )
        elif source == "telegram_bot_api":
            summaries.append(
                f"{label}: Bot API опубликовал пост, но не отдаёт просмотры/реакции; отмечайте заявки и обращения вручную. Заявки {leads}, обращения {inquiries}."
                if is_ru
                else f"{label}: Bot API published the post but does not expose views/reactions; mark leads and inquiries manually. Leads {leads}, inquiries {inquiries}."
            )
        elif source == "google_business_api":
            summaries.append(
                f"{label}: публикация учтена, но сбор реакций через Google Business пока не включён; заявки и обращения отмечаются вручную. Заявки {leads}, обращения {inquiries}."
                if is_ru
                else f"{label}: publishing is tracked, but Google Business reaction collection is not enabled yet; mark leads and inquiries manually. Leads {leads}, inquiries {inquiries}."
            )
        elif source == "meta_graph_api":
            summaries.append(
                f"{label}: Meta Graph метрики требуют готовых прав; пока используйте ручную разметку заявок/обращений. Заявки {leads}, обращения {inquiries}."
                if is_ru
                else f"{label}: Meta Graph metrics require ready permissions; use manual lead/inquiry marking for now. Leads {leads}, inquiries {inquiries}."
            )
        elif source == "manual_or_supervised_map":
            summaries.append(
                f"{label}: реакции с карт собираются вручную после контролируемого размещения; заявки {leads}, обращения {inquiries}."
                if is_ru
                else f"{label}: map reactions are collected manually after supervised placement; leads {leads}, inquiries {inquiries}."
            )
        elif source == "manual_attribution_only":
            summaries.append(
                f"{label}: доступна ручная разметка; заявки {leads}, обращения {inquiries}, реакции {comments}, просмотры {reach}."
                if is_ru
                else f"{label}: manual result marking is available; leads {leads}, inquiries {inquiries}, reactions {comments}, views {reach}."
            )
        else:
            summaries.append(
                f"{label}: метрики обновлены из {source or status or 'collector'}; заявки {leads}, обращения {inquiries}."
                if is_ru
                else f"{label}: metrics updated from {source or status or 'collector'}; leads {leads}, inquiries {inquiries}."
            )
    if len(details or []) > 5:
        remaining = len(details or []) - 5
        summaries.append(
            f"Ещё {remaining} результатов смотрите в карточках постов."
            if is_ru
            else f"See {remaining} more results in post cards."
        )
    return summaries


def preview_due_social_post_dispatch(user_id: str, batch_size: int = 20, business_id: str = "") -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    business_scope = _social_dispatch_business_scope(business_id)
    try:
        ensure_social_post_tables(cursor)
        scope_clause = "AND sp.business_id = %s" if business_scope else ""
        params: list[Any] = []
        if business_scope:
            params.append(business_scope)
        params.append(max(1, min(int(batch_size or 20), 200)))
        cursor.execute(
            f"""
            SELECT sp.*
            FROM social_posts sp
            WHERE sp.status = 'queued'
              AND sp.approved_at IS NOT NULL
              AND COALESCE(sp.scheduled_for, NOW()) <= NOW()
              {scope_clause}
            ORDER BY sp.scheduled_for ASC NULLS FIRST, sp.updated_at ASC
            LIMIT %s
            """,
            tuple(params),
        )
        due_posts = [_serialize_social_post(cursor, row) for row in cursor.fetchall() or []]
        preview_items: list[dict[str, Any]] = []
        skipped = 0
        for post in due_posts:
            try:
                _require_business_access(cursor, user_id, str(post.get("business_id") or ""))
            except PermissionError:
                skipped += 1
                continue
            preview_items.append(_preview_dispatch_decision(cursor, post))
        counts: dict[str, int] = {}
        for item in preview_items:
            action = str(item.get("dispatch_action") or "unknown")
            counts[action] = counts.get(action, 0) + 1
        readiness = _dispatch_preview_readiness(preview_items, counts, skipped, business_scope)
        return {
            "dry_run": True,
            "picked": len(preview_items),
            "skipped_no_access": skipped,
            "batch_size": max(1, min(int(batch_size or 20), 200)),
            "business_scope": business_scope,
            "by_action": counts,
            "readiness": readiness,
            "items": preview_items,
        }
    finally:
        db.close()


def _dispatch_action_for_status(status: str) -> str:
    clean_status = str(status or "").strip()
    if clean_status == "published":
        return "published"
    if clean_status == "needs_supervised_publish":
        return "supervised"
    if clean_status == "needs_manual_publish":
        return "manual"
    if clean_status == "failed":
        return "failed"
    if clean_status == "publishing":
        return "publishing"
    return "other"


def _dispatch_preview_readiness(
    preview_items: list[dict[str, Any]],
    counts: dict[str, int],
    skipped_no_access: int = 0,
    business_scope: str = "",
) -> dict[str, Any]:
    external_publish_count = int(counts.get("publish_api") or 0)
    controlled_count = int(counts.get("create_supervised_task") or 0)
    manual_count = int(counts.get("manual_handoff") or 0)
    due_count = len(preview_items)
    has_due_work = due_count > 0
    has_only_manual_work = has_due_work and external_publish_count == 0 and controlled_count == 0 and manual_count > 0
    status = "no_due_posts"
    if external_publish_count > 0:
        status = "external_publish_ready"
    elif controlled_count > 0:
        status = "controlled_tasks_ready"
    elif has_only_manual_work:
        status = "manual_only"
    elif skipped_no_access > 0:
        status = "access_limited"
    return {
        "status": status,
        "due_count": due_count,
        "external_publish_count": external_publish_count,
        "controlled_count": controlled_count,
        "manual_count": manual_count,
        "skipped_no_access": int(skipped_no_access or 0),
        "has_external_publish": external_publish_count > 0,
        "has_controlled_tasks": controlled_count > 0,
        "has_manual_fallback": manual_count > 0,
        "safe_dry_run": True,
        "external_publish_requires_approval": True,
        "browser_final_click_allowed": False,
        "message_ru": _dispatch_preview_readiness_message(status, True),
        "message_en": _dispatch_preview_readiness_message(status, False),
        "next_action_ru": _dispatch_preview_next_action(status, business_scope, True),
        "next_action_en": _dispatch_preview_next_action(status, business_scope, False),
        "recommended_dispatch_env": _dispatch_preview_recommended_env(business_scope),
        "first_cycle_steps": _dispatch_preview_first_cycle_steps(
            external_publish_count,
            controlled_count,
            manual_count,
            skipped_no_access,
        ),
        "first_cycle_verification": _social_worker_first_cycle_verification(
            external_publish_count,
            controlled_count,
            manual_count,
            skipped_no_access,
            business_scope,
        ),
        "first_api_proof_candidate": _dispatch_first_api_proof_candidate(preview_items),
        "safety_notes_ru": [
            "Внешние публикации уходят только из подтверждённых постов в расписании.",
            "Яндекс/2ГИС остаются контролируемыми или ручными: финальный клик публикации не выполняется исполнителем.",
            "Проверка ничего не отправляет наружу и нужна для первого цикла.",
        ],
        "safety_notes_en": [
            "External publishing runs only for approved/queued posts.",
            "Yandex/2GIS stay supervised/manual: the worker does not perform the final publish click.",
            "Dry-run sends nothing externally and exists to verify the first cycle.",
        ],
    }


def _dispatch_preview_first_cycle_steps(
    external_publish_count: int,
    controlled_count: int,
    manual_count: int,
    skipped_no_access: int = 0,
) -> list[dict[str, Any]]:
    steps = [
        {
            "key": "api_publish_after_approval",
            "label_ru": "API: публикация после подтверждения",
            "label_en": "API: publish after approval",
            "count": int(external_publish_count or 0),
            "external_publish": True,
            "requires_approval": True,
            "stop_before_final_publish": False,
            "expected_status_ru": "published или failed с понятной причиной",
            "expected_status_en": "published or failed with a clear reason",
            "description_ru": "Telegram/VK/Google/Meta уйдут наружу только если пост уже подтверждён, стоит в расписании и канал готов.",
            "description_en": "Telegram/VK/Google/Meta publish externally only when the post is already approved, queued, and the channel is ready.",
        },
        {
            "key": "maps_controlled_without_final_click",
            "label_ru": "Карты: контроль/вручную без финального клика",
            "label_en": "Maps: supervised/manual without final click",
            "count": int(controlled_count or 0),
            "external_publish": False,
            "requires_approval": True,
            "stop_before_final_publish": True,
            "expected_status_ru": "needs_supervised_publish",
            "expected_status_en": "needs_supervised_publish",
            "description_ru": "Яндекс/2ГИС получают контролируемую задачу для OpenClaw, но финальная публикация остаётся за человеком.",
            "description_en": "Yandex/2GIS receive an OpenClaw supervised task, while final publishing stays human-controlled.",
        },
        {
            "key": "manual_handoff_or_connection",
            "label_ru": "Ручной режим или подключение канала",
            "label_en": "Manual fallback or channel connection",
            "count": int(manual_count or 0),
            "external_publish": False,
            "requires_approval": True,
            "stop_before_final_publish": True,
            "expected_status_ru": "needs_manual_publish",
            "expected_status_en": "needs_manual_publish",
            "description_ru": "Посты без ключей, browser-use или готового текста не будут скрыто публиковаться.",
            "description_en": "Posts without credentials, browser-use, or ready copy will not publish silently.",
        },
    ]
    if int(skipped_no_access or 0) > 0:
        steps.append(
            {
                "key": "skipped_no_access",
                "label_ru": "Пропущено без доступа",
                "label_en": "Skipped without access",
                "count": int(skipped_no_access or 0),
                "external_publish": False,
                "requires_approval": True,
                "stop_before_final_publish": True,
                "expected_status_ru": "без изменений",
                "expected_status_en": "unchanged",
                "description_ru": "Эти посты не попали в первый цикл для текущего пользователя или business scope.",
                "description_en": "These posts are outside the current user or business scope for the first cycle.",
            }
        )
    return steps


def _dispatch_first_api_proof_candidate(preview_items: list[dict[str, Any]]) -> dict[str, Any]:
    for item in preview_items or []:
        if str(item.get("dispatch_action") or "").strip() != "publish_api":
            continue
        platform = str(item.get("platform") or "").strip()
        label = str(item.get("platform_label") or platform_label(platform)).strip()
        return {
            "schema": "localos_social_first_api_proof_candidate_v1",
            "ready": True,
            "id": str(item.get("id") or "").strip(),
            "business_id": str(item.get("business_id") or "").strip(),
            "content_plan_id": str(item.get("content_plan_id") or "").strip(),
            "content_plan_item_id": str(item.get("content_plan_item_id") or "").strip(),
            "platform": platform,
            "platform_label": label,
            "scheduled_for": item.get("scheduled_for"),
            "required_proof_fields": ["provider_post_id", "provider_post_url"],
            "expected_status_ru": "published с provider_post_id/provider_post_url или failed с понятной причиной",
            "expected_status_en": "published with provider_post_id/provider_post_url or failed with a clear reason",
            "proof_check_ru": f"После worker откройте {label}: у этого post должен появиться provider_post_id/provider_post_url.",
            "proof_check_en": f"After the worker runs, open {label}: this post must get provider_post_id/provider_post_url.",
            "metrics_followup_ru": "Если proof есть, сразу соберите реакции/заявки и отметьте обращения.",
            "metrics_followup_en": "If proof exists, immediately collect reactions/leads and mark inquiries.",
            "external_publish_requires_approval": True,
            "external_publish_performed": False,
            "dry_run": True,
        }
    return {
        "schema": "localos_social_first_api_proof_candidate_v1",
        "ready": False,
        "required_proof_fields": ["provider_post_id", "provider_post_url"],
        "expected_status_ru": "нет due API-поста для доказательства первого API-loop",
        "expected_status_en": "no due API post is available to prove the first API loop",
        "proof_check_ru": "Сначала подготовьте, подтвердите и поставьте в расписание один Telegram/VK/API-пост.",
        "proof_check_en": "First prepare, approve, and queue one Telegram/VK/API post.",
        "metrics_followup_ru": "Метрики и заявки появятся после первого доказанного API-поста.",
        "metrics_followup_en": "Metrics and leads come after the first proven API post.",
        "external_publish_requires_approval": True,
        "external_publish_performed": False,
        "dry_run": True,
    }


def _social_worker_first_cycle_verification(
    external_publish_count: int,
    controlled_count: int,
    manual_count: int,
    skipped_no_access: int = 0,
    business_scope: str = "",
) -> dict[str, Any]:
    expected_statuses = []
    if int(external_publish_count or 0) > 0:
        expected_statuses.append(
            {
                "key": "api_channels",
                "label_ru": "API-каналы",
                "label_en": "API channels",
                "expected_ru": "published или failed с понятной причиной",
                "expected_en": "published or failed with a clear reason",
            }
        )
    if int(controlled_count or 0) > 0:
        expected_statuses.append(
            {
                "key": "maps_controlled",
                "label_ru": "Яндекс/2ГИС",
                "label_en": "Yandex/2GIS",
                "expected_ru": "needs_supervised_publish или needs_manual_publish; финального клика нет",
                "expected_en": "needs_supervised_publish or needs_manual_publish; no final click",
            }
        )
    if int(manual_count or 0) > 0:
        expected_statuses.append(
            {
                "key": "manual_fallback",
                "label_ru": "Ручной режим",
                "label_en": "Manual fallback",
                "expected_ru": "needs_manual_publish с инструкцией и готовым текстом",
                "expected_en": "needs_manual_publish with instructions and copy-ready text",
            }
        )
    if int(skipped_no_access or 0) > 0:
        expected_statuses.append(
            {
                "key": "skipped_no_access",
                "label_ru": "Нет доступа",
                "label_en": "No access",
                "expected_ru": "без изменений; проверить права или business scope",
                "expected_en": "unchanged; check permissions or business scope",
            }
        )
    if not expected_statuses:
        expected_statuses.append(
            {
                "key": "noop",
                "label_ru": "Нет due-постов",
                "label_en": "No due posts",
                "expected_ru": "worker не должен ничего отправить",
                "expected_en": "worker should not send anything",
            }
        )
    log_filter = "[SOCIAL_POST_DISPATCH]"
    return {
        "log_filter": log_filter,
        "business_scope": str(business_scope or "").strip(),
        "expected_statuses": expected_statuses,
        "checks_ru": [
            f"В логах worker найти строку {log_filter}.",
            "Сверить picked/published/supervised/manual/failed с dry-run перед запуском.",
            "Если есть failed: открыть карточку поста, last_error и readiness канала.",
            "Если есть ручное или контролируемое размещение: завершить его из карточки поста и отметить ссылку/ID.",
        ],
        "checks_en": [
            f"Find the {log_filter} line in worker logs.",
            "Compare picked/published/supervised/manual/failed with the pre-launch dry-run.",
            "If failed exists: open the post card, last_error, and channel readiness.",
            "If manual/supervised exists: complete placement from the post card and record URL/ID.",
        ],
    }


def _dispatch_preview_readiness_message(status: str, is_ru: bool) -> str:
    if status == "external_publish_ready":
        return (
            "Есть due API-посты: после включения dispatch они смогут уйти наружу только потому, что уже approved."
            if is_ru
            else "Due API posts exist: after dispatch is enabled they can publish externally only because they are already approved."
        )
    if status == "controlled_tasks_ready":
        return (
            "Есть due карты: worker создаст контролируемое или ручное размещение, финальная публикация остаётся за человеком."
            if is_ru
            else "Due map posts exist: the worker will create supervised placement or manual handoff, while final publishing stays human-controlled."
        )
    if status == "manual_only":
        return (
            "Все due-посты сейчас требуют ручного fallback или подключения канала; автопубликации не будет."
            if is_ru
            else "All due posts currently require manual fallback or channel connection; no autopublish will happen."
        )
    if status == "access_limited":
        return (
            "Есть due-посты вне доступа текущего пользователя; dry-run их пропустил."
            if is_ru
            else "Some due posts are outside the current user's access; the dry-run skipped them."
        )
    return (
        "Due-постов нет: включение dispatch сейчас ничего не отправит."
        if is_ru
        else "There are no due posts: enabling dispatch now would not send anything."
    )


def _dispatch_preview_next_action(status: str, business_scope: str, is_ru: bool) -> str:
    scope = str(business_scope or "").strip()
    if status == "external_publish_ready":
        if scope:
            return (
                f"Можно включать scoped dispatch для бизнеса {scope}: проверьте ключи и логи после первого цикла."
                if is_ru
                else f"You can enable scoped dispatch for business {scope}: check credentials and logs after the first cycle."
            )
        return (
            "Перед включением реального dispatch задайте SOCIAL_POST_DISPATCH_BUSINESS_ID."
            if is_ru
            else "Set SOCIAL_POST_DISPATCH_BUSINESS_ID before enabling real dispatch."
        )
    if status == "controlled_tasks_ready":
        return (
            "Можно запускать scoped dispatch: карты перейдут в контролируемое или ручное размещение без финального клика."
            if is_ru
            else "Scoped dispatch can run: map posts will move to supervised placement or manual handoff without a final click."
        )
    if status == "manual_only":
        return (
            "Сначала подключите каналы или подготовьте ручное размещение; API-публикации в этом dry-run нет."
            if is_ru
            else "Connect channels or prepare manual placement first; this dry-run has no API publishing."
        )
    if status == "access_limited":
        return (
            "Запустите dry-run пользователем с доступом к нужному бизнесу или сузьте business scope."
            if is_ru
            else "Run the dry-run as a user with access to the business or narrow the business scope."
        )
    return (
        "Новых due-постов нет: продолжайте готовить, утверждать и ставить публикации в расписание."
        if is_ru
        else "No due posts yet: continue preparing, approving, and queueing posts."
    )


def _social_launch_runbook(
    status: str,
    business_scope: str,
    due_count: int,
    external_publish_count: int,
    controlled_count: int,
    manual_count: int,
    skipped_no_access: int,
    first_cycle_verification: dict[str, Any],
) -> dict[str, Any]:
    scope = str(business_scope or "").strip()
    log_filter = str(first_cycle_verification.get("log_filter") or "[SOCIAL_POST_DISPATCH]").strip()
    due = int(due_count or 0)
    external = int(external_publish_count or 0)
    controlled = int(controlled_count or 0)
    manual = int(manual_count or 0)
    skipped = int(skipped_no_access or 0)
    normalized_status = str(status or "").strip()
    can_launch = bool(scope) and due > 0 and skipped == 0 and normalized_status != "api_preflight_blocked"
    return {
        "ready": can_launch,
        "scope": scope,
        "status": normalized_status,
        "title_ru": "Runbook первого цикла dispatch",
        "title_en": "First-cycle dispatch runbook",
        "summary_ru": (
            f"Due {due}: API {external}, контролируемо {controlled}, вручную {manual}. "
            f"Scope: {scope or 'не задан'}."
        ),
        "summary_en": (
            f"Due {due}: API {external}, supervised {controlled}, manual {manual}. "
            f"Scope: {scope or 'not set'}."
        ),
        "steps_ru": _social_launch_runbook_steps(
            scope,
            due,
            external,
            controlled,
            manual,
            skipped,
            log_filter,
            normalized_status,
            True,
        ),
        "steps_en": _social_launch_runbook_steps(
            scope,
            due,
            external,
            controlled,
            manual,
            skipped,
            log_filter,
            normalized_status,
            False,
        ),
        "success_criteria_ru": _social_launch_runbook_success_criteria(external, controlled, manual, skipped, True),
        "success_criteria_en": _social_launch_runbook_success_criteria(external, controlled, manual, skipped, False),
        "blocked_reason_ru": _social_launch_runbook_blocked_reason(scope, due, skipped, normalized_status, True),
        "blocked_reason_en": _social_launch_runbook_blocked_reason(scope, due, skipped, normalized_status, False),
    }


def _social_launch_runbook_steps(
    scope: str,
    due_count: int,
    external_publish_count: int,
    controlled_count: int,
    manual_count: int,
    skipped_no_access: int,
    log_filter: str,
    status: str,
    is_ru: bool,
) -> list[str]:
    if str(status or "").strip() == "api_preflight_blocked":
        return [
            "Исправьте live API-проверку: ключи, права, локацию или адаптер для заблокированного канала."
            if is_ru
            else "Fix live API preflight first: keys, permissions, location, or native adapter for the blocked channel.",
            "Если канал пока нельзя подключить, переведите конкретный пост в ручной режим и повторите проверку."
            if is_ru
            else "If the channel cannot be connected yet, move that specific post to manual fallback and run preflight again.",
        ]
    if int(due_count or 0) <= 0:
        return [
            "Подготовьте посты, утвердите их и поставьте в расписание."
            if is_ru
            else "Prepare posts, approve them, and queue them on schedule.",
            "Запустите preflight снова перед включением worker."
            if is_ru
            else "Run preflight again before enabling the worker.",
        ]
    steps = [
        (
            f"Включите dispatch только со scope: SOCIAL_POST_DISPATCH_BUSINESS_ID={scope}."
            if is_ru
            else f"Enable dispatch only with scope: SOCIAL_POST_DISPATCH_BUSINESS_ID={scope}."
        )
        if scope
        else (
            "Сначала задайте SOCIAL_POST_DISPATCH_BUSINESS_ID для тестового бизнеса."
            if is_ru
            else "Set SOCIAL_POST_DISPATCH_BUSINESS_ID for the test business first."
        ),
        (
            f"Дождитесь одного цикла worker и найдите в логах {log_filter}."
            if is_ru
            else f"Wait for one worker cycle and find {log_filter} in logs."
        ),
        (
            "Сверьте picked/published/supervised/manual/failed с dry-run."
            if is_ru
            else "Compare picked/published/supervised/manual/failed with the dry-run."
        ),
    ]
    if int(external_publish_count or 0) > 0:
        steps.append(
            "Для API-постов проверьте provider_post_id/provider_post_url или понятный last_error."
            if is_ru
            else "For API posts, check provider_post_id/provider_post_url or a clear last_error."
        )
    if int(controlled_count or 0) > 0:
        steps.append(
            "Для Яндекс/2ГИС проверьте контролируемое или ручное размещение: финальный клик не должен быть выполнен worker."
            if is_ru
            else "For Yandex/2GIS, check the supervised/manual task: the worker must not perform the final click."
        )
    if int(manual_count or 0) > 0:
        steps.append(
            "Для manual fallback откройте карточку поста, скопируйте текст и отметьте размещение вручную."
            if is_ru
            else "For manual fallback, open the post card, copy text, and mark placement manually."
        )
    if int(skipped_no_access or 0) > 0:
        steps.append(
            "Есть skipped_no_access: сузьте scope или проверьте права перед запуском."
            if is_ru
            else "skipped_no_access exists: narrow scope or check permissions before launch."
        )
    return steps


def _social_launch_runbook_success_criteria(
    external_publish_count: int,
    controlled_count: int,
    manual_count: int,
    skipped_no_access: int,
    is_ru: bool,
) -> list[str]:
    criteria = []
    if int(external_publish_count or 0) > 0:
        criteria.append(
            "API-каналы стали published или failed с recoverable причиной."
            if is_ru
            else "API channels become published or failed with a recoverable reason."
        )
    if int(controlled_count or 0) > 0:
        criteria.append(
            "Яндекс/2ГИС перешли в needs_supervised_publish/needs_manual_publish без финального клика."
            if is_ru
            else "Yandex/2GIS move to needs_supervised_publish/needs_manual_publish without the final click."
        )
    if int(manual_count or 0) > 0:
        criteria.append(
            "Manual fallback показывает инструкцию и copy-ready текст."
            if is_ru
            else "Manual fallback shows instructions and copy-ready text."
        )
    if int(skipped_no_access or 0) > 0:
        criteria.append(
            "Skipped posts остались без изменений и требуют проверки прав/scope."
            if is_ru
            else "Skipped posts remain unchanged and require permission/scope review."
        )
    if not criteria:
        criteria.append(
            "Worker не отправил ничего наружу, потому что due-постов нет."
            if is_ru
            else "The worker sends nothing externally because there are no due posts."
        )
    return criteria


def _social_launch_runbook_blocked_reason(
    scope: str,
    due_count: int,
    skipped_no_access: int,
    status: str,
    is_ru: bool,
) -> str:
    if str(status or "").strip() == "api_preflight_blocked":
        return (
            "Live API-preflight заблокировал первый цикл: есть due API-пост по каналу без готового подключения."
            if is_ru
            else "Live API preflight blocked the first cycle: a due API post targets a channel without a ready connection."
        )
    if not str(scope or "").strip():
        return (
            "Нельзя включать production dispatch без SOCIAL_POST_DISPATCH_BUSINESS_ID."
            if is_ru
            else "Do not enable production dispatch without SOCIAL_POST_DISPATCH_BUSINESS_ID."
        )
    if int(due_count or 0) <= 0:
        return (
            "Нет due-постов: сначала подготовьте, утвердите и поставьте публикации в расписание."
            if is_ru
            else "No due posts: prepare, approve, and queue publications first."
        )
    if int(skipped_no_access or 0) > 0:
        return (
            "Есть skipped_no_access: сначала проверьте права или business scope."
            if is_ru
            else "skipped_no_access exists: check permissions or business scope first."
        )
    return ""


def _dispatch_preview_recommended_env(business_scope: str) -> dict[str, str]:
    scope = str(business_scope or "").strip()
    return {
        "SOCIAL_POST_DISPATCH_ENABLED": "true",
        "SOCIAL_POST_DISPATCH_INTERVAL_SEC": "60",
        "SOCIAL_POST_DISPATCH_BATCH_SIZE": "10",
        "SOCIAL_POST_DISPATCH_BUSINESS_ID": scope,
    }


def collect_due_social_post_metrics(batch_size: int = 50, business_id: str = "") -> dict[str, Any]:
    picked: list[dict[str, Any]] = []
    business_scope = _social_metrics_business_scope(business_id)
    if not business_scope and not _social_metrics_allow_unscoped():
        return {
            "picked": 0,
            "collected": 0,
            "failed": 0,
            "errors": [],
            "business_scope": "",
            "blocked": True,
            "blocked_reason": "business_scope_required",
            "message": "SOCIAL_POST_METRICS_BUSINESS_ID is required unless SOCIAL_POST_METRICS_ALLOW_UNSCOPED=true.",
        }
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_social_post_tables(cursor)
        scope_clause = "AND sp.business_id = %s" if business_scope else ""
        params: list[Any] = []
        if business_scope:
            params.append(business_scope)
        params.append(max(1, min(int(batch_size or 50), 500)))
        cursor.execute(
            f"""
            SELECT sp.id, sp.business_id
            FROM social_posts sp
            LEFT JOIN social_post_metrics m
              ON m.social_post_id = sp.id
             AND m.metric_date = CURRENT_DATE
            WHERE sp.status = 'published'
              AND m.id IS NULL
              {scope_clause}
            ORDER BY sp.published_at ASC NULLS LAST, sp.updated_at ASC
            LIMIT %s
            """,
            tuple(params),
        )
        picked = [_row_to_dict(cursor, row) for row in cursor.fetchall() or []]
    finally:
        db.close()

    collected = 0
    failed = 0
    errors: list[dict[str, str]] = []
    details: list[dict[str, Any]] = []
    for item in picked:
        post_id = str(item.get("id") or "").strip()
        try:
            owner_id = _owner_id_for_business(str(item.get("business_id") or "").strip())
            if not owner_id:
                raise RuntimeError("business owner not found")
            payload = collect_social_post_metrics(owner_id, post_id=post_id)
            collected += int(payload.get("collected") or 0)
            if isinstance(payload.get("metric_details"), list):
                details.extend([detail for detail in payload.get("metric_details") or [] if isinstance(detail, dict)])
        except Exception:
            failed += 1
            errors.append({"id": post_id, "error": str(sys.exc_info()[1])})
            details.append({"id": post_id, "status": "failed", "source": "collector_error", "error": str(sys.exc_info()[1])})
    return {
        "picked": len(picked),
        "collected": collected,
        "failed": failed,
        "errors": errors,
        "details": details,
        "result_summaries_ru": _social_metrics_result_summaries(details, True),
        "result_summaries_en": _social_metrics_result_summaries(details, False),
        "business_scope": business_scope,
    }


def recommend_next_plan_from_social_posts(user_id: str, plan_id: str) -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_social_post_tables(cursor)
        _load_plan_for_user(cursor, user_id, plan_id)
        posts_payload = list_social_posts_for_plan(user_id, plan_id)
        performance_rows = _social_plan_performance_rows(cursor, plan_id)
        posts = list(posts_payload.get("posts") or [])
        proposed_changes = _add_channel_breakdown_to_changes(
            _build_next_plan_changes(performance_rows),
            posts,
        )
        recommendation = dict(posts_payload.get("recommendation") or {})
        recommendation.update(
            _build_social_learning_insights(
                performance_rows,
                posts,
            )
        )
        application_preview = _social_recommendation_application_preview(cursor, plan_id, proposed_changes)
        return {
            "recommendation": recommendation,
            "proposed_changes": proposed_changes,
            "application_preview": application_preview,
            "learning_readiness": _social_learning_readiness(posts),
            "applies_automatically": False,
            "approval_required": True,
        }
    finally:
        db.close()


def apply_social_post_recommendation(user_id: str, plan_id: str, approved: bool = False) -> dict[str, Any]:
    if not approved:
        raise PermissionError("Для изменения контент-плана нужно явное подтверждение")
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_social_post_tables(cursor)
        plan = _load_plan_for_user(cursor, user_id, plan_id)
        recommendation_payload = recommend_next_plan_from_social_posts(user_id, plan_id)
        proposed_changes = [
            item for item in recommendation_payload.get("proposed_changes", [])
            if str(item.get("item_id") or "").strip() and str(item.get("proposed_goal") or "").strip()
        ]
        applied: list[dict[str, Any]] = []
        for change in proposed_changes:
            cursor.execute(
                """
                UPDATE contentplanitems
                SET goal = %s,
                    updated_at = NOW()
                WHERE id = %s
                  AND plan_id = %s
                  AND COALESCE(usernews_id, '') = ''
                  AND COALESCE(status, '') NOT IN ('skipped', 'published')
                  AND scheduled_for >= CURRENT_DATE
                RETURNING id, theme, goal
                """,
                (
                    str(change.get("proposed_goal") or "").strip(),
                    str(change.get("item_id") or "").strip(),
                    plan_id,
                ),
            )
            row = _row_to_dict(cursor, cursor.fetchone())
            if row:
                applied.append(row)
        edited_plan_json = _json_dict(plan.get("edited_plan_json"))
        history = edited_plan_json.get("social_recommendation_history")
        if not isinstance(history, list):
            history = []
        approval_record = {
            "source": "social_post_recommendation",
            "approved_by": user_id,
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "human_approved": True,
            "scope": "future_unpublished_content_plan_items",
            "recommendation": recommendation_payload,
            "proposed_count": len(proposed_changes),
            "applied_item_ids": [str(item.get("id") or "") for item in applied],
            "applied_count": len(applied),
        }
        edited_plan_json["last_social_recommendation_apply"] = approval_record
        edited_plan_json["social_recommendation_history"] = [*history, approval_record][-20:]
        cursor.execute(
            """
            UPDATE contentplans
            SET edited_plan_json = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (_json_dumps(edited_plan_json), plan_id),
        )
        db.conn.commit()
        return {
            "applied_count": len(applied),
            "applied_items": applied,
            "approval_record": approval_record,
            "applies_automatically": False,
            "application_preview": recommendation_payload.get("application_preview") or {},
            "recommendation": recommendation_payload.get("recommendation") or {},
            "proposed_changes": proposed_changes,
        }
    except Exception:
        db.conn.rollback()
        raise sys.exc_info()[1]
    finally:
        db.close()


def _social_recommendation_application_preview(
    cursor: Any,
    plan_id: str,
    proposed_changes: list[dict[str, Any]],
) -> dict[str, Any]:
    item_ids = [
        str(item.get("item_id") or "").strip()
        for item in proposed_changes
        if str(item.get("item_id") or "").strip()
    ]
    if not item_ids:
        return {
            "schema": "localos_social_recommendation_application_preview_v1",
            "scope": "future_unpublished_content_plan_items",
            "total": 0,
            "applicable_count": 0,
            "skipped_count": 0,
            "items": [],
            "summary_ru": "Нет изменений для применения.",
            "summary_en": "There are no changes to apply.",
        }
    cursor.execute(
        """
        SELECT id, theme, scheduled_for, status, usernews_id
        FROM contentplanitems
        WHERE plan_id = %s
          AND id = ANY(%s)
        """,
        (plan_id, item_ids),
    )
    rows = [_row_to_dict(cursor, row) for row in cursor.fetchall()]
    rows_by_id = {str(row.get("id") or "").strip(): row for row in rows}
    preview_items: list[dict[str, Any]] = []
    for change in proposed_changes:
        item_id = str(change.get("item_id") or "").strip()
        if not item_id:
            continue
        row = rows_by_id.get(item_id) or {}
        eligible, reason = _social_recommendation_application_eligibility(row)
        preview_items.append(
            {
                "item_id": item_id,
                "theme": str(change.get("theme") or row.get("theme") or "").strip(),
                "applicable": eligible,
                "skip_reason": "" if eligible else reason,
                "status": str(row.get("status") or "").strip(),
                "scheduled_for": _iso_or_empty(row.get("scheduled_for")),
                "has_news": bool(str(row.get("usernews_id") or "").strip()),
                "label_ru": "Будет изменён" if eligible else _social_recommendation_skip_reason_label(reason, True),
                "label_en": "Will be changed" if eligible else _social_recommendation_skip_reason_label(reason, False),
            }
        )
    applicable = sum(1 for item in preview_items if bool(item.get("applicable")))
    skipped = len(preview_items) - applicable
    return {
        "schema": "localos_social_recommendation_application_preview_v1",
        "scope": "future_unpublished_content_plan_items",
        "total": len(preview_items),
        "applicable_count": applicable,
        "skipped_count": skipped,
        "items": preview_items,
        "summary_ru": (
            f"Можно применить: {applicable}; будет пропущено: {skipped}. Меняются только будущие неопубликованные пункты."
        ),
        "summary_en": (
            f"Applicable: {applicable}; skipped: {skipped}. Only future unpublished items are changed."
        ),
    }


def _social_recommendation_application_eligibility(row: dict[str, Any]) -> tuple[bool, str]:
    if not row:
        return False, "missing_or_no_access"
    if str(row.get("usernews_id") or "").strip():
        return False, "already_has_news"
    status = str(row.get("status") or "").strip()
    if status in {"skipped", "published"}:
        return False, f"status_{status}"
    scheduled_for = row.get("scheduled_for")
    scheduled_date = scheduled_for.date() if isinstance(scheduled_for, datetime) else scheduled_for
    if isinstance(scheduled_date, str):
        try:
            scheduled_date = date.fromisoformat(scheduled_date[:10])
        except ValueError:
            scheduled_date = None
    if isinstance(scheduled_date, date) and scheduled_date < date.today():
        return False, "past_item"
    return True, ""


def _iso_or_empty(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value or "").strip()


def _social_recommendation_skip_reason_label(reason: str, is_ru: bool) -> str:
    normalized = str(reason or "").strip()
    if normalized == "already_has_news":
        return "Уже создана новость" if is_ru else "News already exists"
    if normalized == "status_published":
        return "Уже опубликован" if is_ru else "Already published"
    if normalized == "status_skipped":
        return "Пропущен" if is_ru else "Skipped"
    if normalized == "past_item":
        return "Прошлая дата" if is_ru else "Past date"
    if normalized == "missing_or_no_access":
        return "Не найден в плане" if is_ru else "Not found in plan"
    return "Будет пропущен" if is_ru else "Will be skipped"


def _social_openclaw_browser_readiness(status: dict[str, Any] | None = None, cursor: Any | None = None) -> dict[str, Any]:
    capability_status = status if isinstance(status, dict) else openclaw_browser_capability_status()
    ready = bool(capability_status.get("ready"))
    delivery_readiness = _social_openclaw_handoff_delivery_readiness(cursor)
    handoff_ready = ready and bool(delivery_readiness.get("ready"))
    safety_contract = _social_supervised_safety_contract()
    missing_reason = str(capability_status.get("reason") or "").strip()
    catalog_error = missing_reason == "openclaw_catalog_error" or str(capability_status.get("source") or "").strip() == "catalog_error"
    private_sandbox_bridge = missing_reason == "sandbox_bridge_private_host" or str(capability_status.get("source") or "").strip() == "sandbox_bridge_private_host"
    if ready and handoff_ready:
        message_ru = "OpenClaw browser-use готов: Яндекс/2ГИС можно вести как контролируемое размещение без финального клика."
        message_en = "OpenClaw browser-use is ready: Yandex/2GIS can use supervised placement without the final click."
        next_action_ru = "Подготовьте контролируемое размещение у поста карты и проверьте предпросмотр перед финальным размещением."
        next_action_en = "Create supervised placement on the map post and review the preview before final placement."
    elif ready:
        message_ru = "OpenClaw browser-use найден, но доставка контролируемой задачи не готова: LocalOS подготовит ручной режим вместо внешней задачи."
        message_en = "OpenClaw browser-use is available, but supervised task delivery is not ready: LocalOS will prepare manual fallback instead of an external task."
        next_action_ru = str(delivery_readiness.get("next_action_ru") or "Настройте доставку задачи OpenClaw или используйте ручное размещение.").strip()
        next_action_en = str(delivery_readiness.get("next_action_en") or "Configure the OpenClaw callback/outbox or use manual placement.").strip()
    elif private_sandbox_bridge:
        message_ru = "OpenClaw browser-use не подтверждён: настроен только приватный sandbox bridge, поэтому Яндекс/2ГИС останутся в ручном режиме."
        message_en = "OpenClaw browser-use is not confirmed: only a private sandbox bridge is configured, so Yandex/2GIS will stay in manual fallback."
        next_action_ru = "Настройте публичный OPENCLAW_BASE_URL или OPENCLAW_SOCIAL_SUPERVISED_CALLBACK_URL для production handoff; до этого используйте ручное размещение."
        next_action_en = "Set a public OPENCLAW_BASE_URL or OPENCLAW_SOCIAL_SUPERVISED_CALLBACK_URL for production handoff; use manual placement until then."
    elif catalog_error:
        message_ru = "OpenClaw browser-use не подтверждён: LocalOS не смог прочитать capability catalog, поэтому Яндекс/2ГИС останутся в ручном режиме."
        message_en = "OpenClaw browser-use is not confirmed: LocalOS could not read the capability catalog, so Yandex/2GIS will stay in manual fallback."
        next_action_ru = "Проверьте доступность OPENCLAW_BASE_URL или OPENCLAW_SANDBOX_BRIDGE_URL с production VPS; до этого используйте ручное размещение."
        next_action_en = "Check that OPENCLAW_BASE_URL or OPENCLAW_SANDBOX_BRIDGE_URL is reachable from the production VPS; use manual placement until then."
    else:
        message_ru = "OpenClaw browser-use не подтверждён: Яндекс/2ГИС останутся в ручном fallback."
        message_en = "OpenClaw browser-use is not confirmed: Yandex/2GIS will stay in manual fallback."
        next_action_ru = "Проверьте capability catalog/OpenClaw настройки или используйте ручное размещение."
        next_action_en = "Check the capability catalog/OpenClaw settings or use manual placement."
    return {
        "ready": ready,
        "handoff_ready": handoff_ready,
        "status": "ready" if handoff_ready else "manual_fallback",
        "delivery_readiness": delivery_readiness,
        "capability": str(capability_status.get("capability") or "social.post.publish_supervised_browser").strip(),
        "action_ref": str(capability_status.get("action_ref") or "").strip(),
        "source": str(capability_status.get("source") or "").strip(),
        "provider_status": str(capability_status.get("status") or "").strip(),
        "reason": missing_reason,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "external_publish_performed": False,
        "browser_final_click_allowed": False,
        "stop_before_final_publish": True,
        "requires_final_human_confirmation": True,
        "side_effect_policy": str(safety_contract.get("side_effect_policy") or "fill_preview_only"),
        "final_publish_policy": str(safety_contract.get("final_publish_policy") or "human_final_click_required"),
        "allowed_actions": safety_contract.get("allowed_actions") if isinstance(safety_contract.get("allowed_actions"), list) else [],
        "forbidden_actions": safety_contract.get("forbidden_actions") if isinstance(safety_contract.get("forbidden_actions"), list) else [],
        "manual_fallback_triggers": safety_contract.get("manual_fallback_triggers") if isinstance(safety_contract.get("manual_fallback_triggers"), list) else [],
        "diagnostics_ru": _social_openclaw_browser_diagnostics(capability_status, True),
        "diagnostics_en": _social_openclaw_browser_diagnostics(capability_status, False),
        "message_ru": message_ru,
        "message_en": message_en,
        "next_action_ru": next_action_ru,
        "next_action_en": next_action_en,
    }


def _social_openclaw_handoff_delivery_readiness(cursor: Any | None = None) -> dict[str, Any]:
    callback_url = _social_supervised_openclaw_callback_url()
    callback_configured = bool(callback_url)
    suggested_callback_url = _social_supervised_openclaw_suggested_callback_url()
    suggestion_blocked_reason = _social_supervised_openclaw_suggested_callback_blocked_reason()
    outbox_available: bool | None = None
    if cursor is not None:
        try:
            outbox_available = _table_exists(cursor, "action_callback_outbox")
        except Exception:
            outbox_available = False
    ready = callback_configured and outbox_available is not False
    if ready:
        status = "ready"
        message_ru = "Доставка OpenClaw task готова: LocalOS сможет поставить controlled task в outbox."
        message_en = "OpenClaw task delivery is ready: LocalOS can enqueue a controlled task in the outbox."
        next_action_ru = "После approval создайте контролируемое размещение у поста Яндекс/2ГИС."
        next_action_en = "After approval, create supervised placement for the Yandex/2GIS post."
    elif not callback_configured:
        status = "callback_missing"
        message_ru = "Callback для OpenClaw supervised task не настроен; внешняя задача не будет отправлена."
        message_en = "The OpenClaw supervised task callback is not configured; no external task will be sent."
        if suggested_callback_url:
            next_action_ru = f"Добавьте OPENCLAW_SOCIAL_SUPERVISED_CALLBACK_URL={suggested_callback_url} или используйте ручное размещение."
            next_action_en = f"Set OPENCLAW_SOCIAL_SUPERVISED_CALLBACK_URL={suggested_callback_url} or use manual placement."
        elif suggestion_blocked_reason:
            next_action_ru = (
                "Укажите публичный/доступный OPENCLAW_SOCIAL_SUPERVISED_CALLBACK_URL или OPENCLAW_BASE_URL; "
                "текущий sandbox bridge не годится для доставки task из production."
            )
            next_action_en = (
                "Set a public/reachable OPENCLAW_SOCIAL_SUPERVISED_CALLBACK_URL or OPENCLAW_BASE_URL; "
                "the current sandbox bridge is not suitable for production task delivery."
            )
        else:
            next_action_ru = "Добавьте OPENCLAW_SOCIAL_SUPERVISED_CALLBACK_URL или используйте ручное размещение."
            next_action_en = "Set OPENCLAW_SOCIAL_SUPERVISED_CALLBACK_URL or use manual placement."
    else:
        status = "outbox_missing"
        message_ru = "Callback настроен, но action_callback_outbox недоступен; task не будет поставлена на доставку."
        message_en = "The callback is configured, but action_callback_outbox is unavailable; the task will not be queued for delivery."
        next_action_ru = "Проверьте миграции/outbox таблицу или используйте ручное размещение."
        next_action_en = "Check migrations/the outbox table or use manual placement."
    return {
        "ready": ready,
        "status": status,
        "callback_configured": callback_configured,
        "callback_url_configured": callback_configured,
        "callback_env_var": "OPENCLAW_SOCIAL_SUPERVISED_CALLBACK_URL",
        "suggested_callback_url": suggested_callback_url,
        "suggested_callback_blocked_reason": suggestion_blocked_reason,
        "outbox_available": outbox_available,
        "read_only": True,
        "external_publish_performed": False,
        "message_ru": message_ru,
        "message_en": message_en,
        "next_action_ru": next_action_ru,
        "next_action_en": next_action_en,
    }


def _social_openclaw_browser_diagnostics(capability_status: dict[str, Any], is_ru: bool) -> list[str]:
    source = str(capability_status.get("source") or "").strip()
    provider_status = str(capability_status.get("status") or "").strip()
    reason = str(capability_status.get("reason") or "").strip()
    action_ref = str(capability_status.get("action_ref") or "").strip()
    error = str(capability_status.get("error") or "").strip()
    ready = bool(capability_status.get("ready"))
    if is_ru:
        lines = [
            "Безопасная проверка: LocalOS только читает каталог возможностей OpenClaw и ничего не публикует.",
            f"Проверяемая возможность: {str(capability_status.get('capability') or 'social.post.publish_supervised_browser').strip()}.",
            "Финальная кнопка публикации запрещена до отдельного подтверждения человека.",
        ]
        if source:
            lines.append(f"Источник проверки: {source}.")
        if provider_status:
            lines.append(f"Статус провайдера: {provider_status}.")
        if action_ref:
            lines.append(f"Действие OpenClaw: {action_ref}.")
        if reason and not ready:
            lines.append(f"Причина ручного режима: {reason}.")
        if error and not ready and reason == "sandbox_bridge_private_host":
            lines.append("Sandbox bridge указывает на приватный или локальный адрес; production handoff через него не включается.")
        elif error and not ready:
            lines.append(f"Ошибка каталога OpenClaw: {error}.")
        if ready:
            lines.append("Следующий шаг: создать контролируемую задачу у поста Яндекс/2ГИС и проверить предпросмотр.")
        elif reason == "sandbox_bridge_private_host" or source == "sandbox_bridge_private_host":
            lines.append("Следующий шаг: настроить публичный OPENCLAW_BASE_URL/callback или использовать ручной режим.")
        elif reason == "openclaw_catalog_error" or source == "catalog_error":
            lines.append("Следующий шаг: сделать OpenClaw catalog доступным с production VPS или оставить ручной режим.")
        else:
            lines.append("Следующий шаг: проверить OPENCLAW_BASE_URL/catalog или использовать ручной режим.")
        return lines
    lines = [
        "Read-only check: LocalOS only reads the capability catalog and publishes nothing.",
        f"Capability: {str(capability_status.get('capability') or 'social.post.publish_supervised_browser').strip()}.",
        "The final publish button is forbidden until separate human confirmation.",
    ]
    if source:
        lines.append(f"Check source: {source}.")
    if provider_status:
        lines.append(f"Provider status: {provider_status}.")
    if action_ref:
        lines.append(f"OpenClaw action: {action_ref}.")
    if reason and not ready:
        lines.append(f"Fallback reason: {reason}.")
    if error and not ready and reason == "sandbox_bridge_private_host":
        lines.append("The sandbox bridge points to a private or local host; production handoff is not enabled through it.")
    elif error and not ready:
        lines.append(f"OpenClaw catalog error: {error}.")
    if ready:
        lines.append("Next step: create supervised Yandex/2GIS placement and review the preview.")
    elif reason == "sandbox_bridge_private_host" or source == "sandbox_bridge_private_host":
        lines.append("Next step: set a public OPENCLAW_BASE_URL/callback or use manual fallback.")
    elif reason == "openclaw_catalog_error" or source == "catalog_error":
        lines.append("Next step: make the OpenClaw catalog reachable from the production VPS or keep manual fallback.")
    else:
        lines.append("Next step: check OPENCLAW_BASE_URL/catalog or use manual fallback.")
    return lines


def openclaw_browser_capability_status(fetcher: Any = None) -> dict[str, Any]:
    env_value = str(os.getenv("OPENCLAW_BROWSER_USE_ENABLED") or os.getenv("OPENCLAW_BROWSER_USE_AVAILABLE") or "").strip().lower()
    if env_value in {"1", "true", "yes", "on", "enabled", "available"}:
        return {
            "ready": True,
            "source": "env_override",
            "status": "available",
            "reason": "browser_use_enabled_by_env",
            "action_ref": "openclaw.browser.supervised_publish",
            "capability": "social.post.publish_supervised_browser",
        }
    if env_value in {"0", "false", "no", "off", "disabled", "unavailable"}:
        return {
            "ready": False,
            "source": "env_override",
            "status": "disabled",
            "reason": "browser_use_disabled_by_env",
            "action_ref": "",
            "capability": "social.post.publish_supervised_browser",
        }
    sandbox_bridge_url = str(os.getenv("OPENCLAW_SANDBOX_BRIDGE_URL") or "").strip()
    if (
        not fetcher
        and sandbox_bridge_url
        and not (os.getenv("OPENCLAW_CAPABILITY_CATALOG_URL") or os.getenv("OPENCLAW_BASE_URL"))
        and _url_uses_private_or_local_host(sandbox_bridge_url)
        and not _env_flag_enabled("OPENCLAW_SOCIAL_SUPERVISED_ALLOW_SANDBOX_CALLBACK")
    ):
        return {
            "ready": False,
            "source": "sandbox_bridge_private_host",
            "status": "unreachable_from_production",
            "reason": "sandbox_bridge_private_host",
            "error": "OPENCLAW_SANDBOX_BRIDGE_URL points to a private/local host and is not allowed for production social browser-use.",
            "action_ref": "",
            "capability": "social.post.publish_supervised_browser",
        }
    if not fetcher and not (
        os.getenv("OPENCLAW_CAPABILITY_CATALOG_URL")
        or os.getenv("OPENCLAW_BASE_URL")
        or os.getenv("OPENCLAW_SANDBOX_BRIDGE_URL")
    ):
        return {
            "ready": False,
            "source": "not_configured",
            "status": "missing_catalog",
            "reason": "openclaw_catalog_not_configured",
            "action_ref": "",
            "capability": "social.post.publish_supervised_browser",
        }
    try:
        catalog = get_openclaw_capability_catalog(fetcher=fetcher)
    except Exception:
        return {
            "ready": False,
            "source": "catalog_error",
            "status": "error",
            "reason": "openclaw_catalog_error",
            "error": str(sys.exc_info()[1]),
            "action_ref": "",
            "capability": "social.post.publish_supervised_browser",
        }
    if isinstance(catalog, dict) and str(catalog.get("source") or "").strip() == "static_fallback" and str(catalog.get("error") or "").strip():
        return {
            "ready": False,
            "source": "catalog_error",
            "status": "error",
            "reason": "openclaw_catalog_error",
            "error": str(catalog.get("error") or "").strip(),
            "action_ref": "",
            "capability": "social.post.publish_supervised_browser",
        }
    for action in catalog.get("actions", []) if isinstance(catalog, dict) else []:
        if not isinstance(action, dict):
            continue
        action_status = str(action.get("status") or "").strip().lower()
        action_ref = str(action.get("openclaw_action_ref") or "").strip()
        capability = str(action.get("localos_capability") or "").strip()
        blob = " ".join(
            str(action.get(key) or "")
            for key in ("openclaw_action_ref", "title", "service", "localos_capability", "status")
        ).lower()
        supervised_browser = capability == "social.post.publish_supervised_browser" or (
            "browser" in blob and ("supervised" in blob or "fill_form" in blob or "publish" in blob)
        )
        if supervised_browser and action_status == "available":
            return {
                "ready": True,
                "source": str(catalog.get("source") or "openclaw") if isinstance(catalog, dict) else "openclaw",
                "status": "available",
                "reason": "openclaw_supervised_browser_available",
                "action_ref": action_ref,
                "capability": capability or "social.post.publish_supervised_browser",
            }
    return {
        "ready": False,
        "source": str(catalog.get("source") or "openclaw") if isinstance(catalog, dict) else "openclaw",
        "status": str(catalog.get("status") or "unavailable") if isinstance(catalog, dict) else "unavailable",
        "reason": "openclaw_supervised_browser_missing",
        "action_ref": "",
        "capability": "social.post.publish_supervised_browser",
        "error": str(catalog.get("error") or "") if isinstance(catalog, dict) else "",
    }


def openclaw_browser_available(fetcher: Any = None) -> bool:
    return bool(openclaw_browser_capability_status(fetcher=fetcher).get("ready"))


def default_publish_mode(platform: str, browser_available: bool | None = None) -> str:
    platform_key = str(platform or "").strip()
    if platform_key in API_PLATFORMS:
        return "api"
    if platform_key in BROWSER_OR_MANUAL_PLATFORMS:
        is_browser_available = openclaw_browser_available() if browser_available is None else bool(browser_available)
        return "openclaw_browser" if is_browser_available else "manual"
    return "manual"


def next_action_for_social_post(post: dict[str, Any]) -> str:
    status = str(post.get("status") or "").strip()
    platform = str(post.get("platform") or "").strip()
    if status in {"draft", "needs_review"}:
        return "review_required"
    if status == "approved" and platform in BROWSER_OR_MANUAL_PLATFORMS:
        return "start_supervised_publish"
    if status == "approved":
        return "wait_for_api_publish"
    if status == "queued" and platform in BROWSER_OR_MANUAL_PLATFORMS:
        return "wait_for_scheduled_supervised_publish"
    if status == "queued":
        return "wait_for_scheduled_publish"
    if status == "needs_supervised_publish":
        return "open_supervised_publish"
    if status == "needs_manual_publish":
        return "manual_publish"
    if status == "failed":
        return "retry_or_manual"
    if status == "published":
        return "collect_metrics"
    return "none"


def _status_after_social_text_edit(current_status: str, platform_text: str) -> str:
    if not str(platform_text or "").strip():
        return "draft"
    if str(current_status or "").strip() == "published":
        return "published"
    return "needs_review"


def _social_post_has_text(post: dict[str, Any]) -> bool:
    return bool(str(post.get("platform_text") or post.get("base_text") or "").strip())


def build_social_queue_groups(posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {str(group["key"]): [] for group in SOCIAL_QUEUE_GROUPS}
    for post in posts:
        key = _queue_group_key(post)
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(post)
    result = []
    for group in SOCIAL_QUEUE_GROUPS:
        key = str(group["key"])
        group_posts = grouped.get(key, [])
        result.append(
            {
                **group,
                "count": len(group_posts),
                "post_ids": [str(post.get("id") or "") for post in group_posts if str(post.get("id") or "").strip()],
                "item_ids": sorted(
                    {
                        str(post.get("content_plan_item_id") or "").strip()
                        for post in group_posts
                        if str(post.get("content_plan_item_id") or "").strip()
                    }
                ),
                "platforms": _summary_for_posts(group_posts).get("by_platform", {}),
            }
        )
    return result


def _queue_group_key(post: dict[str, Any]) -> str:
    status = str(post.get("status") or "").strip()
    platform = str(post.get("platform") or "").strip()
    if status in {"draft", "needs_review"}:
        return "needs_review"
    if status == "queued":
        return "scheduled"
    if status == "published":
        return "published"
    if status == "failed":
        return "failed"
    if status == "needs_manual_publish":
        return "needs_manual_publish"
    if platform in BROWSER_OR_MANUAL_PLATFORMS or status == "needs_supervised_publish":
        return "needs_supervised_publish"
    if platform in API_PLATFORMS and status in {"approved", "publishing"}:
        return "api_ready"
    return "needs_review"


def _preview_dispatch_decision(cursor: Any, post: dict[str, Any]) -> dict[str, Any]:
    platform = str(post.get("platform") or "").strip()
    publish_mode = str(post.get("publish_mode") or "").strip()
    scheduled_for = post.get("scheduled_for")
    approved_at = post.get("approved_at")
    item = {
        "id": str(post.get("id") or "").strip(),
        "business_id": str(post.get("business_id") or "").strip(),
        "content_plan_id": str(post.get("content_plan_id") or "").strip(),
        "content_plan_item_id": str(post.get("content_plan_item_id") or "").strip(),
        "platform": platform,
        "platform_label": platform_label(platform),
        "publish_mode": publish_mode,
        "scheduled_for": scheduled_for.isoformat() if isinstance(scheduled_for, (datetime, date)) else scheduled_for,
        "approved_at": approved_at.isoformat() if isinstance(approved_at, (datetime, date)) else approved_at,
        "current_status": str(post.get("status") or "").strip(),
        "dry_run": True,
    }
    if platform in BROWSER_OR_MANUAL_PLATFORMS:
        if not _social_post_has_text(post):
            return _with_dispatch_preview_labels(
                {
                    **item,
                    "dispatch_action": "manual_handoff",
                    "would_status": "needs_review",
                    "reason": "empty_post_copy",
                    "external_publish": False,
                    "approval_required": True,
                    "stop_before_final_publish": True,
                }
            )
        browser_ready = (
            publish_mode == "openclaw_browser"
            and openclaw_browser_available()
            and bool(_social_openclaw_handoff_delivery_readiness(cursor).get("ready"))
        )
        return _with_dispatch_preview_labels(
            {
                **item,
                "dispatch_action": "create_supervised_task" if browser_ready else "manual_handoff",
                "would_status": "needs_supervised_publish" if browser_ready else "needs_manual_publish",
                "reason": "openclaw_browser_ready" if browser_ready else "openclaw_browser_unavailable",
                "external_publish": False,
                "approval_required": True,
                "stop_before_final_publish": True,
            }
        )
    if publish_mode != "api":
        return _with_dispatch_preview_labels(
            {
                **item,
                "dispatch_action": "manual_handoff",
                "would_status": "needs_manual_publish",
                "reason": "publish_mode_not_api",
                "external_publish": False,
                "approval_required": True,
            }
        )
    if not _social_post_has_text(post):
        return _with_dispatch_preview_labels(
            {
                **item,
                "dispatch_action": "manual_handoff",
                "would_status": "needs_review",
                "reason": "empty_post_copy",
                "external_publish": False,
                "approval_required": True,
            }
        )
    queue_block = _queue_preflight_block(cursor, post)
    if queue_block:
        return _with_dispatch_preview_labels(
            {
                **item,
                "dispatch_action": "manual_handoff",
                "would_status": str(queue_block.get("status") or "needs_manual_publish"),
                "reason": str(queue_block.get("last_error") or "channel_not_ready"),
                "external_publish": False,
                "approval_required": True,
                "metadata_json": queue_block.get("metadata_json") or {},
            }
        )
    return _with_dispatch_preview_labels(
        {
            **item,
            "dispatch_action": "publish_api",
            "would_status": "published_or_failed",
            "reason": "channel_ready",
            "external_publish": True,
            "approval_required": True,
        }
    )


def _with_dispatch_preview_labels(item: dict[str, Any]) -> dict[str, Any]:
    action = str(item.get("dispatch_action") or "").strip()
    reason = str(item.get("reason") or "").strip()
    would_status = str(item.get("would_status") or "").strip()
    item["action_label_ru"] = _dispatch_preview_action_label(action, True)
    item["action_label_en"] = _dispatch_preview_action_label(action, False)
    item["reason_label_ru"] = _dispatch_preview_reason_label(reason, True)
    item["reason_label_en"] = _dispatch_preview_reason_label(reason, False)
    item["safety_summary_ru"] = _dispatch_preview_safety_summary(action, would_status, bool(item.get("external_publish")), True)
    item["safety_summary_en"] = _dispatch_preview_safety_summary(action, would_status, bool(item.get("external_publish")), False)
    return item


def _build_social_post_publish_rehearsal(cursor: Any, post: dict[str, Any]) -> dict[str, Any]:
    decision = _preview_dispatch_decision(cursor, post)
    current_status = str(post.get("status") or "").strip()
    platform = str(post.get("platform") or "").strip()
    has_approval = bool(post.get("approved_at")) or current_status in {"approved", "queued", "needs_supervised_publish"}
    has_text = _social_post_has_text(post)
    allowed_status = current_status in {"approved", "queued", "needs_supervised_publish"}
    blockers: list[dict[str, str]] = []
    if current_status == "published":
        blockers.append(
            {
                "code": "already_published",
                "message_ru": "Пост уже опубликован; следующий шаг - сбор реакций и заявок.",
                "message_en": "The post is already published; the next step is collecting reactions and leads.",
            }
        )
    elif not has_text:
        blockers.append(
            {
                "code": "missing_text",
                "message_ru": "Сначала заполните и сохраните текст поста.",
                "message_en": "Fill and save the post copy first.",
            }
        )
    elif not has_approval:
        blockers.append(
            {
                "code": "missing_approval",
                "message_ru": "Перед запуском человек должен подтвердить preview.",
                "message_en": "A human must approve the preview before launch.",
            }
        )
    elif not allowed_status:
        blockers.append(
            {
                "code": "not_queued_or_approved",
                "message_ru": "Пост ещё не утверждён и не поставлен в расписание.",
                "message_en": "The post is not approved or queued yet.",
            }
        )
    metadata = _json_dict(decision.get("metadata_json"))
    provider_status = str(metadata.get("provider_status") or metadata.get("queue_preflight_status") or "").strip()
    if provider_status:
        blockers.append(
            {
                "code": provider_status,
                "message_ru": str(metadata.get("queue_preflight_message_ru") or decision.get("reason_label_ru") or "").strip(),
                "message_en": str(metadata.get("queue_preflight_message_en") or decision.get("reason_label_en") or "").strip(),
            }
        )
    ready_for_execution = not blockers and str(decision.get("dispatch_action") or "") in {
        "publish_api",
        "create_supervised_task",
    }
    return {
        "schema": "localos_social_publish_rehearsal_v1",
        "dry_run": True,
        "post_id": str(post.get("id") or "").strip(),
        "platform": platform,
        "platform_label": platform_label(platform),
        "publish_mode": str(post.get("publish_mode") or "").strip(),
        "current_status": current_status,
        "scheduled_for": decision.get("scheduled_for"),
        "approved_at": decision.get("approved_at"),
        "has_text": has_text,
        "has_approval": has_approval,
        "ready_for_execution": ready_for_execution,
        "external_publish_performed": False,
        "provider_write_performed": False,
        "would_external_publish": bool(decision.get("external_publish")) and ready_for_execution,
        "would_create_supervised_task": str(decision.get("dispatch_action") or "") == "create_supervised_task" and ready_for_execution,
        "browser_final_click_allowed": False,
        "stop_before_final_publish": bool(decision.get("stop_before_final_publish")) or platform in BROWSER_OR_MANUAL_PLATFORMS,
        "dispatch_decision": decision,
        "blockers": blockers,
        "summary_ru": _publish_rehearsal_summary(ready_for_execution, decision, blockers, True),
        "summary_en": _publish_rehearsal_summary(ready_for_execution, decision, blockers, False),
        "next_action_ru": _publish_rehearsal_next_action(ready_for_execution, decision, blockers, True),
        "next_action_en": _publish_rehearsal_next_action(ready_for_execution, decision, blockers, False),
        "publish_evidence": _social_publish_evidence(post),
    }


def _social_publish_rehearsal_summary(rehearsals: list[dict[str, Any]], failed: list[dict[str, str]]) -> dict[str, Any]:
    total = len(rehearsals) + len(failed)
    ready = [item for item in rehearsals if bool(item.get("ready_for_execution"))]
    blocked = [item for item in rehearsals if not bool(item.get("ready_for_execution"))]
    api_ready = [item for item in ready if bool(item.get("would_external_publish"))]
    supervised_ready = [item for item in ready if bool(item.get("would_create_supervised_task"))]
    manual_or_blocked = len(blocked) + len(failed)
    status = "empty"
    if total > 0 and not ready:
        status = "blocked"
    elif total > 0 and manual_or_blocked > 0:
        status = "partial"
    elif total > 0:
        status = "ready"
    return {
        "status": status,
        "total": total,
        "ready": len(ready),
        "blocked": len(blocked),
        "failed": len(failed),
        "api_ready": len(api_ready),
        "supervised_ready": len(supervised_ready),
        "manual_or_blocked": manual_or_blocked,
        "external_publish_performed": False,
        "provider_write_performed": False,
        "browser_final_click_allowed": False,
        "message_ru": _social_publish_rehearsal_bulk_message(status, len(ready), len(api_ready), len(supervised_ready), manual_or_blocked, True),
        "message_en": _social_publish_rehearsal_bulk_message(status, len(ready), len(api_ready), len(supervised_ready), manual_or_blocked, False),
        "next_action_ru": _social_publish_rehearsal_bulk_next_action(status, blocked, failed, True),
        "next_action_en": _social_publish_rehearsal_bulk_next_action(status, blocked, failed, False),
    }


def _social_publish_rehearsal_bulk_message(
    status: str,
    ready: int,
    api_ready: int,
    supervised_ready: int,
    manual_or_blocked: int,
    is_ru: bool,
) -> str:
    if status == "ready":
        return (
            f"Проверка пройдена: готово {ready}, API {api_ready}, контролируемое размещение {supervised_ready}."
            if is_ru
            else f"Check passed: ready {ready}, API {api_ready}, supervised placement {supervised_ready}."
        )
    if status == "partial":
        return (
            f"Часть постов готова: {ready}. Требуют внимания: {manual_or_blocked}."
            if is_ru
            else f"Some posts are ready: {ready}. Need attention: {manual_or_blocked}."
        )
    if status == "blocked":
        return (
            f"Запуск пока заблокирован: требуют внимания {manual_or_blocked}."
            if is_ru
            else f"Launch is blocked for now: {manual_or_blocked} need attention."
        )
    return "Выберите посты для проверки запуска." if is_ru else "Select posts to check launch readiness."


def _social_publish_rehearsal_bulk_next_action(
    status: str,
    blocked: list[dict[str, Any]],
    failed: list[dict[str, str]],
    is_ru: bool,
) -> str:
    if status == "ready":
        return (
            "Можно ставить в расписание: API выйдет только по approval/дате, карты останутся контролируемыми."
            if is_ru
            else "You can queue them: API publishes only after approval/date, maps stay supervised."
        )
    if blocked:
        first = blocked[0]
        return str(first.get("next_action_ru" if is_ru else "next_action_en") or "").strip() or (
            "Исправьте первый блокер и повторите проверку."
            if is_ru
            else "Fix the first blocker and run the check again."
        )
    if failed:
        return (
            "Проверьте доступ к выбранным постам и повторите проверку."
            if is_ru
            else "Check access to the selected posts and run the check again."
        )
    return "Выберите посты и повторите проверку." if is_ru else "Select posts and run the check again."


def _publish_rehearsal_summary(
    ready_for_execution: bool,
    decision: dict[str, Any],
    blockers: list[dict[str, str]],
    is_ru: bool,
) -> str:
    action = str(decision.get("dispatch_action") or "").strip()
    if ready_for_execution and action == "publish_api":
        return (
            "Проверка пройдена: канал готов, при запуске worker сможет опубликовать пост по API."
            if is_ru
            else "Check passed: the channel is ready and the worker can publish this post through the API."
        )
    if ready_for_execution and action == "create_supervised_task":
        return (
            "Проверка пройдена: LocalOS создаст контролируемую задачу, финальная публикация останется за человеком."
            if is_ru
            else "Check passed: LocalOS will create a supervised task and final publishing stays human-controlled."
        )
    if blockers:
        message = str(blockers[0].get("message_ru" if is_ru else "message_en") or "").strip()
        return message or (
            "Проверка нашла блокер перед запуском."
            if is_ru
            else "The check found a launch blocker."
        )
    return (
        "Проверка выполнена: наружу ничего не отправлено."
        if is_ru
        else "Check completed: nothing was sent externally."
    )


def _publish_rehearsal_next_action(
    ready_for_execution: bool,
    decision: dict[str, Any],
    blockers: list[dict[str, str]],
    is_ru: bool,
) -> str:
    action = str(decision.get("dispatch_action") or "").strip()
    if ready_for_execution and action == "publish_api":
        return (
            "Поставьте пост в расписание или дождитесь worker’а, если он уже queued."
            if is_ru
            else "Queue the post or wait for the worker if it is already queued."
        )
    if ready_for_execution and action == "create_supervised_task":
        return (
            "Создайте контролируемое размещение и проверьте preview перед финальным действием."
            if is_ru
            else "Create supervised placement and review the preview before the final action."
        )
    if blockers:
        code = str(blockers[0].get("code") or "").strip()
        if code == "missing_text":
            return "Сохраните текст и повторите проверку." if is_ru else "Save the copy and run the check again."
        if code == "missing_approval":
            return "Откройте preview и подтвердите пост." if is_ru else "Open the preview and approve the post."
        if code in {"missing_connection", "missing_binding", "missing_permissions", "adapter_pending"}:
            return (
                "Подключите канал или используйте ручное размещение."
                if is_ru
                else "Connect the channel or use manual placement."
            )
        if code == "already_published":
            return "Соберите реакции и отметьте заявки." if is_ru else "Collect reactions and record leads."
    return (
        str(decision.get("safety_summary_ru") or "Проверьте статус поста и повторите запуск.")
        if is_ru
        else str(decision.get("safety_summary_en") or "Check the post status and try again.")
    )


def _dispatch_preview_action_label(action: str, is_ru: bool) -> str:
    clean = str(action or "").strip()
    if clean == "publish_api":
        return "API-публикация" if is_ru else "API publish"
    if clean == "create_supervised_task":
        return "Контролируемое размещение" if is_ru else "Supervised placement"
    if clean == "manual_handoff":
        return "Ручной режим" if is_ru else "Manual fallback"
    return "Без действия" if is_ru else "No action"


def _dispatch_preview_reason_label(reason: str, is_ru: bool) -> str:
    clean = str(reason or "").strip()
    if clean == "channel_ready":
        return "Канал готов, есть подтверждение и расписание." if is_ru else "Channel is ready, approved, and scheduled."
    if clean == "openclaw_browser_ready":
        return "OpenClaw browser-use доступен; будет создана контролируемая задача." if is_ru else "OpenClaw browser-use is available; a supervised task will be created."
    if clean == "openclaw_browser_unavailable":
        return "OpenClaw browser-use не подтверждён; нужен ручной режим." if is_ru else "OpenClaw browser-use is not confirmed; manual fallback is required."
    if clean == "empty_post_copy":
        return "Текст пустой: сначала верните пост на проверку и заполните copy." if is_ru else "Copy is empty: send the post back to review and fill it first."
    if clean == "publish_mode_not_api":
        return "Канал не настроен как API-публикация." if is_ru else "The channel is not configured for API publishing."
    if clean:
        return clean
    return "Причина не указана." if is_ru else "No reason provided."


def _dispatch_preview_safety_summary(action: str, would_status: str, external_publish: bool, is_ru: bool) -> str:
    clean_action = str(action or "").strip()
    clean_status = str(would_status or "").strip()
    if bool(external_publish):
        return (
            "Worker может отправить наружу только этот API-пост; итог будет published или failed."
            if is_ru
            else "The worker may send only this API post externally; result will be published or failed."
        )
    if clean_action == "create_supervised_task":
        return (
            "Worker создаст контролируемое размещение и не нажмёт финальную кнопку публикации."
            if is_ru
            else "The worker will create supervised placement and will not click the final publish button."
        )
    if clean_status == "needs_review":
        return (
            "Worker не будет публиковать: сначала нужен текст и повторное подтверждение."
            if is_ru
            else "The worker will not publish: copy and another review are required first."
        )
    return (
        "Worker не будет публиковать наружу; пост перейдёт в ручной понятный статус."
        if is_ru
        else "The worker will not publish externally; the post will move to a clear manual status."
    )


def _load_plan_item_for_user(cursor: Any, user_id: str, item_id: str) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT
            i.*,
            p.business_id AS plan_business_id,
            p.id AS parent_plan_id,
            p.title AS plan_title
        FROM contentplanitems i
        JOIN contentplans p ON p.id = i.plan_id
        WHERE i.id = %s
        """,
        (item_id,),
    )
    item = _row_to_dict(cursor, cursor.fetchone())
    if not item:
        raise ValueError("Пункт контент-плана не найден")
    business_id = str(item.get("business_id") or item.get("plan_business_id") or "").strip()
    _require_business_access(cursor, user_id, business_id)
    return item


def _load_plan_for_user(cursor: Any, user_id: str, plan_id: str) -> dict[str, Any]:
    cursor.execute("SELECT * FROM contentplans WHERE id = %s", (plan_id,))
    plan = _row_to_dict(cursor, cursor.fetchone())
    if not plan:
        raise ValueError("Контент-план не найден")
    _require_business_access(cursor, user_id, str(plan.get("business_id") or ""))
    return plan


def _content_plan_item_count(cursor: Any, plan_id: str) -> int:
    cursor.execute("SELECT COUNT(*) AS item_count FROM contentplanitems WHERE plan_id = %s", (plan_id,))
    row = cursor.fetchone()
    return int(_row_get(row, "item_count", 0, 0) or 0)


def _load_post_for_user(cursor: Any, user_id: str, post_id: str) -> dict[str, Any]:
    cursor.execute("SELECT * FROM social_posts WHERE id = %s", (post_id,))
    post = _serialize_social_post(cursor, cursor.fetchone())
    if not post:
        raise ValueError("Публикация не найдена")
    _require_business_access(cursor, user_id, str(post.get("business_id") or ""))
    return post


def _require_business_access(cursor: Any, user_id: str, business_id: str) -> None:
    owner_id = get_business_owner_id(cursor, business_id)
    if str(owner_id or "").strip() == str(user_id or "").strip():
        return
    cursor.execute("SELECT COALESCE(is_superadmin, FALSE) FROM users WHERE id = %s", (user_id,))
    row = cursor.fetchone()
    if bool(_row_get(row, "coalesce", 0, False)):
        return
    raise PermissionError("Нет доступа к бизнесу")


def _upsert_social_post(cursor: Any, user_id: str, item: dict[str, Any], platform: str, base_text: str) -> dict[str, Any]:
    item_id = str(item.get("id") or "").strip()
    plan_id = str(item.get("plan_id") or item.get("parent_plan_id") or "").strip()
    business_id = str(item.get("business_id") or item.get("plan_business_id") or "").strip()
    scheduled_for = item.get("scheduled_for")
    publish_mode = default_publish_mode(platform)
    platform_text = _platform_text(platform, base_text)
    status = "needs_review" if platform_text.strip() else "draft"
    cursor.execute(
        """
        INSERT INTO social_posts (
            id, business_id, content_plan_id, content_plan_item_id, platform, publish_mode, status,
            scheduled_for, base_text, platform_text, media_json, metadata_json, created_by, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, '[]', %s, %s, NOW(), NOW())
        ON CONFLICT (content_plan_item_id, platform)
        DO UPDATE SET
            scheduled_for = EXCLUDED.scheduled_for,
            base_text = CASE WHEN social_posts.status = 'published' THEN social_posts.base_text ELSE EXCLUDED.base_text END,
            platform_text = CASE WHEN social_posts.status = 'published' THEN social_posts.platform_text ELSE EXCLUDED.platform_text END,
            publish_mode = EXCLUDED.publish_mode,
            status = CASE
                WHEN social_posts.status IN ('published', 'queued', 'publishing') THEN social_posts.status
                ELSE EXCLUDED.status
            END,
            metadata_json = EXCLUDED.metadata_json,
            updated_at = NOW()
        RETURNING *
        """,
        (
            _new_id(),
            business_id,
            plan_id,
            item_id,
            platform,
            publish_mode,
            status,
            scheduled_for,
            base_text,
            platform_text,
            _json_dumps(_initial_metadata(platform, publish_mode)),
            user_id,
        ),
    )
    return _serialize_social_post(cursor, cursor.fetchone())


def _existing_social_posts_for_item(cursor: Any, item_id: str) -> dict[str, dict[str, Any]]:
    cursor.execute(
        """
        SELECT *
        FROM social_posts
        WHERE content_plan_item_id = %s
        """,
        (item_id,),
    )
    result: dict[str, dict[str, Any]] = {}
    for row in cursor.fetchall() or []:
        post = _serialize_social_post(cursor, row)
        platform = str(post.get("platform") or "").strip()
        if platform:
            result[platform] = post
    return result


def _preview_social_post_for_platform(
    item: dict[str, Any],
    platform: str,
    base_text: str,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    item_id = str(item.get("id") or "").strip()
    plan_id = str(item.get("plan_id") or item.get("parent_plan_id") or "").strip()
    business_id = str(item.get("business_id") or item.get("plan_business_id") or "").strip()
    publish_mode = default_publish_mode(platform)
    platform_text = _platform_text(platform, base_text)
    status = "needs_review" if platform_text.strip() else "draft"
    existing_post = existing if isinstance(existing, dict) else {}
    existing_status = str(existing_post.get("status") or "").strip()
    prepare_action = "would_create"
    preview_status = status
    preview_base_text = base_text
    preview_platform_text = platform_text
    if existing_post:
        prepare_action = "would_update"
        if existing_status in {"published", "queued", "publishing"}:
            prepare_action = f"preserve_{existing_status}"
            preview_status = existing_status
            preview_base_text = str(existing_post.get("base_text") or base_text or "").strip()
            preview_platform_text = str(existing_post.get("platform_text") or platform_text or "").strip()
    metadata = _initial_metadata(platform, publish_mode)
    metadata["prepare_preview"] = True
    metadata["read_only"] = True
    return {
        "id": str(existing_post.get("id") or "").strip(),
        "business_id": business_id,
        "content_plan_id": plan_id,
        "content_plan_item_id": item_id,
        "platform": platform,
        "platform_label": platform_label(platform),
        "publish_mode": publish_mode,
        "status": preview_status,
        "scheduled_for": item.get("scheduled_for"),
        "base_text": preview_base_text,
        "platform_text": preview_platform_text,
        "media_json": existing_post.get("media_json") if existing_post else [],
        "metadata_json": metadata,
        "prepare_action": prepare_action,
        "existing_status": existing_status,
        "read_only": True,
        "external_publish_performed": False,
    }


def _initial_metadata(platform: str, publish_mode: str) -> dict[str, Any]:
    data = {
        "platform_label": platform_label(platform),
        "approval_required": True,
        "source": "localos_content_plan",
    }
    if platform in BROWSER_OR_MANUAL_PLATFORMS:
        data["supervised_notice"] = "Канал требует ручного или контролируемого размещения; это не production API."
        data["browser_mode_available"] = publish_mode == "openclaw_browser"
    if platform in {"instagram", "facebook"}:
        data["permissions_notice"] = "Публикация зависит от Meta Graph permissions и подключенной страницы/аккаунта."
    return data


def _supervised_publish_metadata(cursor: Any, post: dict[str, Any], automation_task_id: str) -> dict[str, Any]:
    platform = str(post.get("platform") or "").strip()
    target = _map_publish_target(cursor, str(post.get("business_id") or ""), platform)
    task_payload = _build_openclaw_supervised_task_payload(post, automation_task_id, target)
    capability_status = openclaw_browser_capability_status()
    manual_handoff = _manual_publish_handoff_payload(post, target, "browser_capability_unavailable")
    safety_contract = _social_supervised_safety_contract()
    completion_contract = _social_supervised_completion_contract()
    handoff_checklist = _social_supervised_handoff_checklist()
    handoff_state = _social_supervised_handoff_state(post, task_payload, capability_status)
    return {
        "automation_task_id": automation_task_id,
        "openclaw_task": task_payload,
        "supervised_publish": {
            "mode": str(post.get("publish_mode") or "manual"),
            "platform": platform,
            "platform_label": platform_label(platform),
            "capability": str(task_payload.get("capability") or "social.post.publish_supervised_browser").strip(),
            "openclaw_action_ref": str(task_payload.get("openclaw_action_ref") or "openclaw.browser.supervised_publish").strip(),
            "task_status": str(task_payload.get("status") or "ready_for_supervised_or_manual_handoff").strip(),
            "target_url": target.get("target_url", ""),
            "target_url_source": target.get("target_url_source", ""),
            "profile_hint": target.get("profile_hint", ""),
            "copy_ready_text": str(post.get("platform_text") or post.get("base_text") or "").strip(),
            "instruction_ru": "Открыть площадку, вставить текст и медиа, показать предпросмотр, остановиться перед финальной публикацией до подтверждения.",
            "instruction_en": "Open the platform, fill text and media, show preview, and stop before final publish until explicit approval.",
            "manual_instruction_ru": manual_handoff["instruction_ru"],
            "manual_instruction_en": manual_handoff["instruction_en"],
            "handoff_checklist_ru": handoff_checklist["ru"],
            "handoff_checklist_en": handoff_checklist["en"],
            "manual_checklist_ru": manual_handoff["checklist_ru"],
            "manual_checklist_en": manual_handoff["checklist_en"],
            "manual_handoff": manual_handoff,
            "stop_before_final_publish": True,
            "final_publish_policy": "human_final_click_required",
            "handoff_state": handoff_state,
            "safety_contract": safety_contract,
            "completion_contract": completion_contract,
            "operator_next_action_ru": str(task_payload.get("operator_next_action_ru") or "").strip(),
            "operator_next_action_en": str(task_payload.get("operator_next_action_en") or "").strip(),
            "fallback_reasons": ["captcha", "login_required", "changed_ui", "browser_capability_unavailable"],
            "openclaw_capability_status": capability_status,
        },
    }


def _supervised_publish_state(post: dict[str, Any], cursor: Any | None = None) -> dict[str, str | None]:
    publish_mode = str(post.get("publish_mode") or "").strip()
    browser_ready = (
        publish_mode == "openclaw_browser"
        and openclaw_browser_available()
        and bool(_social_openclaw_handoff_delivery_readiness(cursor).get("ready"))
    )
    return {
        "status": "needs_supervised_publish" if browser_ready else "needs_manual_publish",
        "last_error": None if browser_ready else "OpenClaw browser-use или доставка supervised task недоступны; используйте ручное контролируемое размещение.",
    }


def _social_supervised_handoff_state(
    post: dict[str, Any],
    task_payload: dict[str, Any],
    capability_status: dict[str, Any],
    ledger_id: str = "",
) -> dict[str, Any]:
    publish_mode = str(post.get("publish_mode") or "").strip()
    openclaw_ready = publish_mode == "openclaw_browser" and bool(capability_status.get("ready"))
    state = "ready_for_openclaw_handoff" if openclaw_ready else "manual_fallback_required"
    if openclaw_ready:
        owner_status_ru = "Задача готова для контролируемого OpenClaw browser-use."
        owner_status_en = "Task is ready for supervised OpenClaw browser-use."
        owner_next_action_ru = "Откройте контролируемое размещение, проверьте предпросмотр и подтвердите финальное действие человеком."
        owner_next_action_en = "Open supervised placement, review the preview, and let a human confirm the final action."
    else:
        owner_status_ru = "OpenClaw browser-use не подтверждён; включён ручной режим."
        owner_status_en = "OpenClaw browser-use is not confirmed; manual fallback is active."
        owner_next_action_ru = "Скопируйте готовый текст, разместите пост вручную и отметьте публикацию размещённой."
        owner_next_action_en = "Copy the prepared text, publish it manually, and mark the post as published."
    return {
        "schema": "localos_social_supervised_handoff_state_v1",
        "state": state,
        "publish_mode": publish_mode,
        "openclaw_ready": openclaw_ready,
        "task_payload_ready": bool(task_payload.get("task_id")),
        "openclaw_task_requested": False,
        "ledger_recorded": bool(str(ledger_id or "").strip()),
        "ledger_id": str(ledger_id or "").strip(),
        "owner_status_ru": owner_status_ru,
        "owner_status_en": owner_status_en,
        "owner_next_action_ru": owner_next_action_ru,
        "owner_next_action_en": owner_next_action_en,
        "stop_before_final_publish": True,
        "final_publish_policy": "human_final_click_required",
        "browser_final_click_allowed": False,
    }


def _build_openclaw_supervised_task_payload(
    post: dict[str, Any],
    automation_task_id: str,
    target: dict[str, Any] | None = None,
) -> dict[str, Any]:
    platform = str(post.get("platform") or "").strip()
    target_payload = target if isinstance(target, dict) else {}
    text = str(post.get("platform_text") or post.get("base_text") or "").strip()
    safety_contract = _social_supervised_safety_contract()
    completion_contract = _social_supervised_completion_contract()
    done_criteria = _social_supervised_done_criteria()
    handoff_checklist = _social_supervised_handoff_checklist()
    return {
        "schema": "localos_social_supervised_publish_task_v1",
        "task_id": str(automation_task_id or "").strip(),
        "capability": "social.post.publish_supervised_browser",
        "openclaw_action_ref": "openclaw.browser.supervised_publish",
        "risk_class": "external_publish",
        "approval_class": "external_publish",
        "approval_required": True,
        "stop_before_final_publish": True,
        "auto_final_click_allowed": False,
        "safety_contract": safety_contract,
        "completion_contract": completion_contract,
        "handoff_checklist_ru": handoff_checklist["ru"],
        "handoff_checklist_en": handoff_checklist["en"],
        "done_criteria_ru": done_criteria["ru"],
        "done_criteria_en": done_criteria["en"],
        "operator_next_action_ru": "Заполнить форму, показать предпросмотр и остановиться до финальной публикации; результат вернуть как preview_ready или manual_fallback.",
        "operator_next_action_en": "Fill the form, show the preview, and stop before final publishing; return preview_ready or manual_fallback.",
        "status": "ready_for_supervised_or_manual_handoff",
        "platform": platform,
        "platform_label": platform_label(platform),
        "business": {
            "id": str(post.get("business_id") or "").strip(),
            "name": str(target_payload.get("business_name") or "").strip(),
            "location_label": str(target_payload.get("location_label") or "").strip(),
        },
        "target": {
            "url": str(target_payload.get("target_url") or "").strip(),
            "url_source": str(target_payload.get("target_url_source") or "").strip(),
            "profile_hint": str(target_payload.get("profile_hint") or "").strip(),
        },
        "content": {
            "text": text,
            "media": post.get("media_json") if isinstance(post.get("media_json"), list) else [],
        },
        "approval_evidence": {
            "social_post_id": str(post.get("id") or "").strip(),
            "content_plan_id": str(post.get("content_plan_id") or "").strip(),
            "content_plan_item_id": str(post.get("content_plan_item_id") or "").strip(),
            "approved_at": str(post.get("approved_at") or "").strip(),
            "approval_id": str(post.get("approval_id") or "").strip(),
        },
        "instructions": {
            "ru": [
                "Открыть целевую площадку или профиль бизнеса.",
                "Вставить подготовленный текст и медиа.",
                "Показать предпросмотр человеку.",
                "Остановиться перед финальной кнопкой публикации.",
                "Если логин, капча или интерфейс изменился, вернуть manual fallback.",
            ],
            "en": [
                "Open the target platform or business profile.",
                "Fill the prepared text and media.",
                "Show preview to a human.",
                "Stop before the final publish button.",
                "If login, captcha, or UI changed, return manual fallback.",
            ],
        },
        "fallback": {
            "status": "needs_manual_publish",
            "reasons": ["captcha", "login_required", "changed_ui", "browser_capability_unavailable"],
            "manual_instruction_ru": "Скопируйте текст из LocalOS, разместите его на площадке вручную и отметьте публикацию размещённой.",
            "manual_instruction_en": "Copy the text from LocalOS, publish it manually on the platform, and mark the post as published.",
        },
    }


def _social_supervised_completion_contract() -> dict[str, Any]:
    done_criteria = _social_supervised_done_criteria()
    return {
        "schema": "localos_social_supervised_completion_contract_v1",
        "success_state": "preview_ready",
        "fallback_state": "manual_fallback_required",
        "preview_required": True,
        "final_publish_click_owner": "human",
        "browser_final_click_allowed": False,
        "external_publish_performed_by_task": False,
        "required_result_fields": [
            "status",
            "preview_available",
            "target_url",
            "filled_text",
            "blocked_reason",
        ],
        "allowed_result_statuses": [
            "preview_ready",
            "manual_fallback_required",
            "blocked_by_login",
            "blocked_by_captcha",
            "blocked_by_changed_ui",
            "blocked_by_missing_target",
        ],
        "manual_fallback_triggers": [
            "captcha",
            "login_required",
            "changed_ui",
            "missing_target_url",
            "browser_capability_unavailable",
            "unexpected_external_prompt",
        ],
        "done_criteria_ru": done_criteria["ru"],
        "done_criteria_en": done_criteria["en"],
        "owner_completion_instruction_ru": "После предпросмотра человек сам нажимает финальную публикацию и отмечает пост размещённым в LocalOS.",
        "owner_completion_instruction_en": "After preview, a human clicks the final publish button and marks the post as published in LocalOS.",
    }


def _social_supervised_done_criteria() -> dict[str, list[str]]:
    return {
        "ru": [
            "Предпросмотр на площадке показан человеку.",
            "Финальную публикацию нажал человек, не браузер-автоматизация.",
            "В LocalOS внесена ссылка или ID опубликованного поста, если площадка их даёт.",
            "Пост отмечен размещённым, чтобы реакции и заявки попали в следующий план.",
        ],
        "en": [
            "The platform preview was shown to a human.",
            "The final publish click was made by a human, not browser automation.",
            "LocalOS has the published post URL or ID if the platform provides one.",
            "The post is marked as published so reactions and leads can inform the next plan.",
        ],
    }


def _social_supervised_handoff_checklist() -> dict[str, list[str]]:
    return {
        "ru": [
            "Открыть профиль нужной точки на площадке.",
            "Вставить подготовленный текст и медиа из LocalOS.",
            "Показать предпросмотр человеку и сверить, что площадка/точка выбраны верно.",
            "Остановиться перед финальной кнопкой публикации.",
            "После ручного финального клика сохранить ссылку или ID и отметить пост размещённым.",
        ],
        "en": [
            "Open the correct location profile on the platform.",
            "Paste the prepared LocalOS copy and media.",
            "Show the preview to a human and verify the platform/location.",
            "Stop before the final publish button.",
            "After the human final click, save the URL or ID and mark the post as published.",
        ],
    }


def _social_supervised_safety_contract() -> dict[str, Any]:
    return {
        "schema": "localos_social_supervised_safety_contract_v1",
        "risk_class": "external_publish",
        "approval_class": "external_publish",
        "side_effect_policy": "fill_preview_only",
        "final_publish_policy": "human_final_click_required",
        "provider_write_performed_by_localos": False,
        "external_publish_performed_by_openclaw": False,
        "stop_before_final_publish": True,
        "auto_final_click_allowed": False,
        "requires_final_human_confirmation": True,
        "allowed_actions": [
            "open_platform",
            "fill_text",
            "attach_media",
            "show_preview",
            "return_task_status",
        ],
        "forbidden_actions": [
            "click_final_publish",
            "bypass_login",
            "solve_captcha_without_user",
            "change_business_profile_data",
            "publish_without_human_confirmation",
        ],
        "manual_fallback_triggers": [
            "captcha",
            "login_required",
            "changed_ui",
            "missing_target_url",
            "browser_capability_unavailable",
            "unexpected_external_prompt",
        ],
    }


def _manual_publish_handoff_payload(post: dict[str, Any], target: dict[str, Any], reason: str = "") -> dict[str, Any]:
    platform = str(post.get("platform") or "").strip()
    text = str(post.get("platform_text") or post.get("base_text") or "").strip()
    target_url = str(target.get("target_url") or "").strip()
    reason_text = str(reason or "").strip()
    checklist_ru = [
        "Скопировать готовый текст из LocalOS.",
        "Открыть профиль площадки для нужной точки бизнеса.",
        "Вставить текст и медиа в форму публикации.",
        "Проверить предпросмотр и не публиковать без финального подтверждения.",
        "После размещения вставить ссылку или ID поста и нажать «Отметить размещённым».",
    ]
    checklist_en = [
        "Copy the prepared text from LocalOS.",
        "Open the platform profile for the right business location.",
        "Paste text and media into the post form.",
        "Review the preview and do not publish without final confirmation.",
        "After publishing, paste the post URL or ID and click Mark published.",
    ]
    return {
        "schema": "localos_social_manual_publish_handoff_v1",
        "platform": platform,
        "platform_label": platform_label(platform),
        "target_url": target_url,
        "target_url_source": str(target.get("target_url_source") or "").strip(),
        "profile_hint": str(target.get("profile_hint") or "").strip(),
        "copy_ready_text": text,
        "reason": reason_text,
        "instruction_ru": "Разместите этот пост вручную или под контролем OpenClaw. LocalOS хранит текст, ссылку на площадку и чеклист, а финальная публикация остаётся за человеком.",
        "instruction_en": "Publish this post manually or with OpenClaw supervision. LocalOS keeps the copy, platform link, and checklist, while final publishing stays human-controlled.",
        "checklist_ru": checklist_ru,
        "checklist_en": checklist_en,
        "final_publish_policy": "human_final_click_required",
        "stop_before_final_publish": True,
        "browser_final_click_allowed": False,
    }


def _record_social_supervised_handoff_ledger(
    cursor: Any,
    original_post: dict[str, Any],
    updated_post: dict[str, Any],
    automation_task_id: str,
) -> str:
    try:
        if not _table_exists(cursor, "agent_action_ledger"):
            return ""
        metadata = _json_dict(updated_post.get("metadata_json"))
        task_payload = _json_dict(metadata.get("openclaw_task"))
        supervised_payload = _json_dict(metadata.get("supervised_publish"))
        safety_contract = _json_dict(
            supervised_payload.get("safety_contract")
            or task_payload.get("safety_contract")
            or _social_supervised_safety_contract()
        )
        status = str(updated_post.get("status") or "").strip()
        ledger_id = _new_id()
        cursor.execute(
            """
            INSERT INTO agent_action_ledger (
                id, agent_client_id, business_id, action_type, capability, required_scope,
                risk_level, input_summary, output_summary, approval_id, status,
                reason_code, ip, user_agent, metadata_json
            )
            VALUES (%s, NULL, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL, NULL, %s)
            """,
            (
                ledger_id,
                str(updated_post.get("business_id") or original_post.get("business_id") or "").strip(),
                "social_post_supervised_handoff",
                "social.post.publish_supervised_browser",
                "external_publish",
                "high",
                _json_dumps(
                    {
                        "social_post_id": str(updated_post.get("id") or original_post.get("id") or "").strip(),
                        "platform": str(updated_post.get("platform") or original_post.get("platform") or "").strip(),
                        "publish_mode": str(updated_post.get("publish_mode") or original_post.get("publish_mode") or "").strip(),
                        "automation_task_id": str(automation_task_id or "").strip(),
                    }
                ),
                _json_dumps(
                    {
                        "status": status,
                        "next_action": next_action_for_social_post(updated_post),
                        "stop_before_final_publish": bool(supervised_payload.get("stop_before_final_publish", True)),
                        "target_url": str(supervised_payload.get("target_url") or task_payload.get("target", {}).get("url") or "").strip()
                        if isinstance(task_payload.get("target"), dict)
                        else str(supervised_payload.get("target_url") or "").strip(),
                    }
                ),
                str(updated_post.get("approval_id") or original_post.get("approval_id") or "").strip() or None,
                "queued_for_supervised_handoff" if status == "needs_supervised_publish" else "manual_handoff_required",
                "OPENCLAW_SUPERVISED_READY" if status == "needs_supervised_publish" else "MANUAL_FALLBACK_REQUIRED",
                _json_dumps(
                    {
                        "schema": "localos_social_supervised_handoff_ledger_v1",
                        "automation_task_id": str(automation_task_id or "").strip(),
                        "content_plan_id": str(updated_post.get("content_plan_id") or original_post.get("content_plan_id") or "").strip(),
                        "content_plan_item_id": str(updated_post.get("content_plan_item_id") or original_post.get("content_plan_item_id") or "").strip(),
                        "execution_contract": {
                            "capability": "social.post.publish_supervised_browser",
                            "openclaw_action_ref": str(task_payload.get("openclaw_action_ref") or "openclaw.browser.supervised_publish").strip(),
                            "delivery_status": "pending_openclaw_supervised_task"
                            if status == "needs_supervised_publish"
                            else "manual_fallback_required",
                            "side_effect_policy": str(safety_contract.get("side_effect_policy") or "fill_preview_only"),
                            "final_publish_policy": str(safety_contract.get("final_publish_policy") or "human_final_click_required"),
                            "fallback_policy": "login_captcha_changed_ui_to_manual",
                            "allowed_actions": safety_contract.get("allowed_actions") if isinstance(safety_contract.get("allowed_actions"), list) else [],
                            "forbidden_actions": safety_contract.get("forbidden_actions") if isinstance(safety_contract.get("forbidden_actions"), list) else [],
                            "manual_fallback_triggers": safety_contract.get("manual_fallback_triggers")
                            if isinstance(safety_contract.get("manual_fallback_triggers"), list)
                            else [],
                        },
                        "provider_write_performed": False,
                        "external_publish_performed": False,
                        "human_final_approval_required": True,
                        "browser_final_click_allowed": False,
                        "openclaw_task": task_payload,
                    }
                ),
            ),
        )
        return ledger_id
    except Exception:
        return ""


def _enqueue_social_supervised_openclaw_outbox(
    cursor: Any,
    updated_post: dict[str, Any],
    automation_task_id: str,
    ledger_id: str = "",
) -> str:
    try:
        callback_url = _social_supervised_openclaw_callback_url()
        if not callback_url:
            return ""
        if not _table_exists(cursor, "action_callback_outbox"):
            return ""
        metadata = _json_dict(updated_post.get("metadata_json"))
        task_payload = _json_dict(metadata.get("openclaw_task"))
        supervised_payload = _json_dict(metadata.get("supervised_publish"))
        handoff_state = _json_dict(supervised_payload.get("handoff_state"))
        safety_contract = _json_dict(
            supervised_payload.get("safety_contract")
            or task_payload.get("safety_contract")
            or _social_supervised_safety_contract()
        )
        completion_contract = _json_dict(
            supervised_payload.get("completion_contract")
            or task_payload.get("completion_contract")
            or _social_supervised_completion_contract()
        )
        post_id = str(updated_post.get("id") or "").strip()
        business_id = str(updated_post.get("business_id") or "").strip()
        outbox_id = _new_id()
        event_type = "social.post.publish_supervised_browser.requested"
        payload = {
            "schema": "localos_social_supervised_openclaw_request_v1",
            "event_type": event_type,
            "social_post_id": post_id,
            "business_id": business_id,
            "automation_task_id": str(automation_task_id or "").strip(),
            "agent_action_ledger_id": str(ledger_id or "").strip(),
            "openclaw_task": task_payload,
            "handoff_state": handoff_state,
            "safety_contract": safety_contract,
            "completion_contract": completion_contract,
            "handoff_checklist_ru": supervised_payload.get("handoff_checklist_ru")
            if isinstance(supervised_payload.get("handoff_checklist_ru"), list)
            else task_payload.get("handoff_checklist_ru", []),
            "handoff_checklist_en": supervised_payload.get("handoff_checklist_en")
            if isinstance(supervised_payload.get("handoff_checklist_en"), list)
            else task_payload.get("handoff_checklist_en", []),
            "operator_next_action_ru": str(
                supervised_payload.get("operator_next_action_ru")
                or task_payload.get("operator_next_action_ru")
                or "Заполнить форму, показать предпросмотр и остановиться до финальной публикации; результат вернуть как preview_ready или manual_fallback."
            ).strip(),
            "operator_next_action_en": str(
                supervised_payload.get("operator_next_action_en")
                or task_payload.get("operator_next_action_en")
                or "Fill the form, show the preview, and stop before final publishing; return preview_ready or manual_fallback."
            ).strip(),
            "external_publish_performed": False,
            "provider_write_performed": False,
            "browser_final_click_allowed": False,
            "stop_before_final_publish": True,
            "final_publish_policy": "human_final_click_required",
        }
        dedupe_key = f"social-supervised:{post_id}:{automation_task_id}"
        cursor.execute(
            """
            INSERT INTO action_callback_outbox
                (id, action_id, tenant_id, callback_url, event_type, payload_json, status, attempts, max_attempts, next_attempt_at, dedupe_key)
            VALUES (%s, %s, %s, %s, %s, %s, 'pending', 0, %s, NOW(), %s)
            ON CONFLICT (dedupe_key) DO NOTHING
            RETURNING id
            """,
            (
                outbox_id,
                str(automation_task_id or post_id or outbox_id).strip(),
                business_id,
                callback_url,
                event_type,
                _json_dumps(payload),
                _social_supervised_openclaw_max_attempts(),
                dedupe_key,
            ),
        )
        row = cursor.fetchone()
        return str(_row_get(row, "id", 0, "") or "").strip()
    except Exception:
        return ""


def _social_supervised_openclaw_callback_url() -> str:
    return str(
        os.getenv("OPENCLAW_SOCIAL_SUPERVISED_CALLBACK_URL")
        or os.getenv("OPENCLAW_SUPERVISED_CALLBACK_URL")
        or ""
    ).strip()


def _social_supervised_openclaw_suggested_callback_url() -> str:
    explicit = _social_supervised_openclaw_callback_url()
    if explicit:
        return explicit
    base_url = str(os.getenv("OPENCLAW_BASE_URL") or "").strip()
    source = "base_url" if base_url else ""
    if not base_url:
        catalog_url = str(os.getenv("OPENCLAW_CAPABILITY_CATALOG_URL") or "").strip()
        base_url = catalog_url
        source = "catalog_url" if catalog_url else ""
    if not base_url:
        sandbox_url = str(os.getenv("OPENCLAW_SANDBOX_BRIDGE_URL") or "").strip()
        if sandbox_url and (
            _env_flag_enabled("OPENCLAW_SOCIAL_SUPERVISED_ALLOW_SANDBOX_CALLBACK")
            or not _url_uses_private_or_local_host(sandbox_url)
        ):
            base_url = sandbox_url
            source = "sandbox_bridge"
    if not base_url:
        return ""
    if (
        source == "sandbox_bridge"
        and _url_uses_private_or_local_host(base_url)
        and not _env_flag_enabled("OPENCLAW_SOCIAL_SUPERVISED_ALLOW_SANDBOX_CALLBACK")
    ):
        return ""
    try:
        parsed = urllib.parse.urlsplit(base_url)
        if not parsed.scheme or not parsed.netloc:
            return ""
        return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "/m2m/localos/callbacks", "", ""))
    except Exception:
        return ""


def _social_supervised_openclaw_suggested_callback_blocked_reason() -> str:
    if _social_supervised_openclaw_callback_url():
        return ""
    if os.getenv("OPENCLAW_BASE_URL") or os.getenv("OPENCLAW_CAPABILITY_CATALOG_URL"):
        return ""
    sandbox_url = str(os.getenv("OPENCLAW_SANDBOX_BRIDGE_URL") or "").strip()
    if not sandbox_url:
        return ""
    if _env_flag_enabled("OPENCLAW_SOCIAL_SUPERVISED_ALLOW_SANDBOX_CALLBACK"):
        return ""
    if _url_uses_private_or_local_host(sandbox_url):
        return "sandbox_bridge_private_host"
    return ""


def _url_uses_private_or_local_host(url: str) -> bool:
    try:
        parsed = urllib.parse.urlsplit(str(url or "").strip())
        host = str(parsed.hostname or "").strip().lower()
        if not host:
            return False
        if host in {"localhost", "127.0.0.1", "::1"}:
            return True
        ip = ipaddress.ip_address(host)
        return bool(ip.is_private or ip.is_loopback or ip.is_link_local)
    except ValueError:
        return False
    except Exception:
        return False


def _env_flag_enabled(name: str) -> bool:
    return str(os.getenv(name) or "").strip().lower() in {"1", "true", "yes", "on", "enabled", "available"}


def _social_supervised_openclaw_max_attempts() -> int:
    try:
        return max(1, min(int(os.getenv("OPENCLAW_SOCIAL_SUPERVISED_MAX_ATTEMPTS") or 5), 20))
    except Exception:
        return 5


def _publish_api_post(cursor: Any, post: dict[str, Any]) -> dict[str, Any]:
    platform = str(post.get("platform") or "").strip()
    if platform == "telegram":
        return _publish_telegram_post(cursor, post)
    if platform == "vk":
        return _publish_vk_post(cursor, post)
    if platform == "google_business":
        return _publish_google_business_post(cursor, post)
    if platform in {"instagram", "facebook"}:
        return _publish_external_account_post(
            cursor,
            post,
            ("meta", "facebook", "instagram"),
            "Meta Graph permissions или бизнес-аккаунт ещё не подтверждены.",
            "meta_graph_permissions_required",
        )
    return {
        "status": "needs_manual_publish",
        "last_error": "Для канала не настроен API-адаптер",
        "metadata_json": {"provider_status": "unsupported_api_platform"},
    }


def _telegram_publish_error_state(status_code: int = 0, description: str = "") -> tuple[str, str]:
    clean_description = str(description or "").strip()
    normalized = clean_description.lower()
    recoverable_connection_markers = (
        "unauthorized",
        "forbidden",
        "chat not found",
        "bot was blocked",
        "not enough rights",
        "have no rights",
        "need administrator",
        "group chat was upgraded",
        "peer_id_invalid",
    )
    if int(status_code or 0) in {400, 401, 403} and any(marker in normalized for marker in recoverable_connection_markers):
        return "needs_manual_publish", "telegram_connection_invalid"
    if int(status_code or 0) in {401, 403}:
        return "needs_manual_publish", "telegram_connection_invalid"
    return "failed", "telegram_api_error"


def _resolve_telegram_publish_transport(business: dict[str, Any]) -> dict[str, Any]:
    business_token = decode_telegram_bot_token(business.get("telegram_bot_token"))
    if business_token:
        return {
            "bot_token": business_token,
            "token_present": True,
            "token_source": "business_bot",
            "token_label_ru": "бот бизнеса",
            "token_label_en": "business bot",
        }
    global_token = str(os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if global_token:
        return {
            "bot_token": global_token,
            "token_present": True,
            "token_source": "global_owner_bot",
            "token_label_ru": "глобальный бот LocalOS",
            "token_label_en": "global LocalOS bot",
        }
    return {
        "bot_token": "",
        "token_present": False,
        "token_source": "missing",
        "token_label_ru": "бот не найден",
        "token_label_en": "bot not found",
    }


def _publish_telegram_post(cursor: Any, post: dict[str, Any]) -> dict[str, Any]:
    business = _load_business_publish_context(cursor, str(post.get("business_id") or ""))
    transport = _resolve_telegram_publish_transport(business)
    bot_token = str(transport.get("bot_token") or "").strip()
    chat_id = str(business.get("telegram_chat_id") or "").strip()
    if not bot_token or not chat_id:
        return {
            "status": "needs_manual_publish",
            "last_error": "Для Telegram нужен бот LocalOS или telegram_bot_token бизнеса и telegram_chat_id цели публикации.",
            "metadata_json": {
                "provider_status": "telegram_connection_missing",
                "telegram_transport": str(transport.get("token_source") or "missing"),
            },
        }
    text = str(post.get("platform_text") or post.get("base_text") or "").strip()
    if not text:
        return {
            "status": "failed",
            "last_error": "Пустой текст нельзя отправить в Telegram.",
            "metadata_json": {"provider_status": "telegram_empty_text"},
        }
    try:
        payload = json.dumps(
            {
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": True,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        resp = telegram_urlopen(req, timeout=15)
        try:
            body = resp.read().decode("utf-8", errors="ignore")
            parsed = _json_dict(body)
            status_code = int(getattr(resp, "status", 500))
            if not (200 <= status_code < 300) or not bool(parsed.get("ok")):
                description = str(parsed.get("description") or body or f"Telegram HTTP {status_code}")[:1000]
                status, provider_status = _telegram_publish_error_state(status_code, description)
                return {
                    "status": status,
                    "last_error": description,
                    "metadata_json": {"provider_status": provider_status, "status_code": status_code},
                }
            result = parsed.get("result") if isinstance(parsed.get("result"), dict) else {}
            message_id = str(result.get("message_id") or "").strip()
            return {
                "status": "published",
                "provider_post_id": message_id,
                "provider_post_url": _telegram_post_url(chat_id, message_id),
                "metadata_json": {
                    "provider_status": "telegram_published",
                    "telegram_transport": str(transport.get("token_source") or ""),
                    "provider_write_performed": True,
                    "external_publish_performed": True,
                    "telegram_response": parsed,
                },
            }
        finally:
            resp.close()
    except urllib.error.HTTPError:
        error = sys.exc_info()[1]
        body = ""
        try:
            body = error.read().decode("utf-8", errors="ignore")
        except Exception:
            body = str(error)
        status_code = int(getattr(error, "code", 0) or 0)
        description = str(_json_dict(body).get("description") or body or str(error))[:1000]
        status, provider_status = _telegram_publish_error_state(status_code, description)
        return {
            "status": status,
            "last_error": description,
            "metadata_json": {"provider_status": provider_status, "status_code": status_code},
        }
    except (urllib.error.URLError, TimeoutError):
        error = sys.exc_info()[1]
        return {
            "status": "failed",
            "last_error": str(error),
            "metadata_json": {"provider_status": "telegram_network_error"},
        }
    except Exception:
        error = sys.exc_info()[1]
        return {
            "status": "failed",
            "last_error": str(error),
            "metadata_json": {"provider_status": "telegram_unexpected_error"},
        }


def _publish_vk_post(cursor: Any, post: dict[str, Any]) -> dict[str, Any]:
    account = _find_active_external_account(cursor, str(post.get("business_id") or ""), ("vk", "vk_group", "vk_business"))
    if not account:
        return {
            "status": "needs_manual_publish",
            "last_error": "VK аккаунт/группа не подключены или не выданы права wall.post.",
            "metadata_json": {"provider_status": "vk_connection_missing"},
        }
    auth_data = _external_account_auth_data(account)
    vk_binding = _vk_publish_binding(account, auth_data)
    if not vk_binding.get("ready"):
        return {
            "status": "needs_manual_publish",
            "last_error": _vk_readiness_error(str(vk_binding.get("status") or "")),
            "metadata_json": {
                "provider_status": str(vk_binding.get("status") or "vk_not_ready"),
                "external_account_id": account.get("id"),
            },
        }
    token = str(vk_binding.get("token") or "").strip()
    owner_id = str(vk_binding.get("owner_id") or "").strip()
    text = str(post.get("platform_text") or post.get("base_text") or "").strip()
    if not text:
        return {
            "status": "failed",
            "last_error": "Пустой текст нельзя отправить во VK.",
            "metadata_json": {"provider_status": "vk_empty_text"},
        }
    payload = urllib.parse.urlencode(
        {
            "access_token": token,
            "owner_id": owner_id,
            "message": text,
            "from_group": "1",
            "v": str(auth_data.get("api_version") or "5.199"),
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.vk.com/method/wall.post",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        try:
            body = resp.read().decode("utf-8", errors="ignore")
            parsed = _json_dict(body)
        finally:
            resp.close()
    except urllib.error.HTTPError:
        error = sys.exc_info()[1]
        body = ""
        try:
            body = error.read().decode("utf-8", errors="ignore")
        except Exception:
            body = str(error)
        return {
            "status": "failed",
            "last_error": body or str(error),
            "metadata_json": {"provider_status": "vk_http_error", "external_account_id": account.get("id")},
        }
    except (urllib.error.URLError, TimeoutError):
        error = sys.exc_info()[1]
        return {
            "status": "failed",
            "last_error": str(error),
            "metadata_json": {"provider_status": "vk_network_error", "external_account_id": account.get("id")},
        }
    except Exception:
        error = sys.exc_info()[1]
        return {
            "status": "failed",
            "last_error": str(error),
            "metadata_json": {"provider_status": "vk_unexpected_error", "external_account_id": account.get("id")},
        }
    if isinstance(parsed.get("error"), dict):
        vk_error = parsed.get("error") or {}
        return {
            "status": "needs_manual_publish" if int(vk_error.get("error_code") or 0) in {5, 7, 15, 27} else "failed",
            "last_error": str(vk_error.get("error_msg") or "VK API error"),
            "metadata_json": {
                "provider_status": "vk_api_error",
                "external_account_id": account.get("id"),
                "vk_error": vk_error,
            },
        }
    response = parsed.get("response") if isinstance(parsed.get("response"), dict) else {}
    post_id = str(response.get("post_id") or "").strip()
    provider_url = _vk_post_url(owner_id, post_id)
    if not post_id:
        return {
            "status": "failed",
            "last_error": "VK не вернул post_id.",
            "metadata_json": {"provider_status": "vk_missing_post_id", "external_account_id": account.get("id"), "vk_response": parsed},
        }
    return {
        "status": "published",
        "provider_post_id": post_id,
        "provider_post_url": provider_url,
        "metadata_json": {
            "provider_status": "vk_published",
            "provider_write_performed": True,
            "external_publish_performed": True,
            "external_account_id": account.get("id"),
            "vk_response": parsed,
        },
    }


def _publish_google_business_post(cursor: Any, post: dict[str, Any]) -> dict[str, Any]:
    account = _find_active_external_account(cursor, str(post.get("business_id") or ""), ("google_business",))
    if not account:
        return {
            "status": "needs_manual_publish",
            "last_error": "Google Business Profile не подключен или не готов к публикации.",
            "metadata_json": {"provider_status": "google_business_connection_missing"},
        }
    summary = str(post.get("platform_text") or post.get("base_text") or "").strip()
    if not summary:
        return {
            "status": "failed",
            "last_error": "Пустой текст нельзя отправить в Google Business Profile.",
            "metadata_json": {"provider_status": "google_business_empty_text", "external_account_id": account.get("id")},
        }
    post_data = {
        "topicType": "STANDARD",
        "summary": summary[:1500],
        "callToAction": {
            "actionType": "CALL",
            "url": "",
        },
    }
    try:
        from google_business_sync_worker import GoogleBusinessSyncWorker
        worker = GoogleBusinessSyncWorker()
        provider_post_id = worker._publish_post(account, post_data)
    except ImportError:
        error = sys.exc_info()[1]
        return {
            "status": "needs_manual_publish",
            "last_error": f"Google Business adapter dependency is unavailable: {error}",
            "metadata_json": {"provider_status": "google_business_dependency_missing", "external_account_id": account.get("id")},
        }
    except Exception:
        error = sys.exc_info()[1]
        return {
            "status": "failed",
            "last_error": str(error),
            "metadata_json": {"provider_status": "google_business_exception", "external_account_id": account.get("id")},
        }
    if not provider_post_id:
        return {
            "status": "needs_manual_publish",
            "last_error": "Google Business Profile не принял публикацию. Проверьте OAuth, location и разрешения.",
            "metadata_json": {"provider_status": "google_business_publish_failed", "external_account_id": account.get("id")},
        }
    return {
        "status": "published",
        "provider_post_id": str(provider_post_id),
        "provider_post_url": "",
        "metadata_json": {
            "provider_status": "google_business_published",
            "external_account_id": account.get("id"),
        },
    }


def _telegram_api_channel_preflight(cursor: Any, business_id: str) -> dict[str, Any]:
    business = _load_business_publish_context(cursor, business_id)
    transport = _resolve_telegram_publish_transport(business)
    bot_token = str(transport.get("bot_token") or "").strip()
    chat_id = str(business.get("telegram_chat_id") or "").strip()
    checks = _telegram_connection_checks(bool(bot_token), bool(chat_id), str(transport.get("token_source") or ""))
    if not bot_token or not chat_id:
        global_bot_missing_chat = bool(bot_token) and not chat_id and str(transport.get("token_source")) == "global_owner_bot"
        message_ru = (
            "Telegram: глобальный бот LocalOS доступен, осталось указать telegram_chat_id цели публикации."
            if global_bot_missing_chat
            else "Для Telegram нужен бот LocalOS или telegram_bot_token бизнеса и telegram_chat_id цели публикации."
        )
        message_en = (
            "Telegram: the global LocalOS bot is available; set the publish-target telegram_chat_id."
            if global_bot_missing_chat
            else "Telegram needs the LocalOS bot or a business telegram_bot_token plus the publish-target telegram_chat_id."
        )
        return _api_channel_preflight_result(
            "telegram",
            False,
            "missing_keys",
            checks,
            message_ru,
            message_en,
            ["telegram_chat_id"] if global_bot_missing_chat else None,
        )
    bot_probe = _telegram_safe_api_probe(bot_token, "getMe")
    chat_probe = _telegram_safe_api_probe(bot_token, "getChat", {"chat_id": chat_id})
    permission_probe = _telegram_publish_permission_probe(bot_token, chat_id, bot_probe, chat_probe)
    checks = checks + [
        _connection_check(
            "telegram_get_me",
            bool(bot_probe.get("ok")),
            "Бот отвечает",
            "Bot responds",
            "getMe прошёл" if bot_probe.get("ok") else str(bot_probe.get("error_ru") or "Telegram getMe не прошёл"),
            "getMe passed" if bot_probe.get("ok") else str(bot_probe.get("error_en") or "Telegram getMe failed"),
            "ok" if bot_probe.get("ok") else str(bot_probe.get("status") or "failed"),
        ),
        _connection_check(
            "telegram_get_chat",
            bool(chat_probe.get("ok")),
            "Чат доступен",
            "Chat is reachable",
            "getChat прошёл" if chat_probe.get("ok") else str(chat_probe.get("error_ru") or "Telegram getChat не прошёл"),
            "getChat passed" if chat_probe.get("ok") else str(chat_probe.get("error_en") or "Telegram getChat failed"),
            "ok" if chat_probe.get("ok") else str(chat_probe.get("status") or "failed"),
        ),
        _connection_check(
            "telegram_publish_permission_live",
            bool(permission_probe.get("ok")),
            "Право публикации",
            "Publishing permission",
            str(permission_probe.get("detail_ru") or ""),
            str(permission_probe.get("detail_en") or ""),
            str(permission_probe.get("status") or "failed"),
        ),
    ]
    ready = bool(bot_probe.get("ok")) and bool(chat_probe.get("ok")) and bool(permission_probe.get("ok"))
    failed_status = "missing_permissions" if bot_probe.get("ok") and chat_probe.get("ok") else "live_probe_failed"
    return _api_channel_preflight_result(
        "telegram",
        ready,
        "ready" if ready else failed_status,
        checks,
        f"Telegram готов к API-публикации через {transport.get('token_label_ru')} после подтверждения." if ready else str(permission_probe.get("message_ru") or "Telegram ключи заполнены, но live-проверка не прошла."),
        f"Telegram is ready for API publishing through the {transport.get('token_label_en')} after approval." if ready else str(permission_probe.get("message_en") or "Telegram keys exist, but live preflight failed."),
    )


def _telegram_safe_api_probe(bot_token: str, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    query = urllib.parse.urlencode(params or {})
    suffix = f"?{query}" if query else ""
    req = urllib.request.Request(f"https://api.telegram.org/bot{bot_token}/{method}{suffix}", method="GET")
    try:
        resp = telegram_urlopen(req, timeout=10)
        try:
            body = resp.read().decode("utf-8", errors="ignore")
            parsed = _json_dict(body)
            status_code = int(getattr(resp, "status", 500))
        finally:
            resp.close()
    except urllib.error.HTTPError:
        error = sys.exc_info()[1]
        body = ""
        try:
            body = error.read().decode("utf-8", errors="ignore")
        except Exception:
            body = str(error)
        return _api_probe_error("telegram", int(getattr(error, "code", 0) or 0), body or str(error))
    except (urllib.error.URLError, TimeoutError):
        return _api_probe_error("telegram", 0, str(sys.exc_info()[1]), "network_error")
    except Exception:
        return _api_probe_error("telegram", 0, str(sys.exc_info()[1]), "unexpected_error")
    if 200 <= status_code < 300 and bool(parsed.get("ok")):
        result = parsed.get("result")
        return {"ok": True, "status": "ok", "result": result if isinstance(result, dict) else result}
    return _api_probe_error("telegram", status_code, str(parsed.get("description") or body or "Telegram API error"))


def _telegram_publish_permission_probe(
    bot_token: str,
    chat_id: str,
    bot_probe: dict[str, Any],
    chat_probe: dict[str, Any],
) -> dict[str, Any]:
    if not bot_probe.get("ok") or not chat_probe.get("ok"):
        return {
            "ok": False,
            "status": "blocked",
            "message_ru": "Telegram: сначала должны пройти getMe и getChat.",
            "message_en": "Telegram: getMe and getChat must pass first.",
            "detail_ru": "проверка прав невозможна без доступного бота и чата",
            "detail_en": "permission check requires a reachable bot and chat",
        }
    bot_result = bot_probe.get("result") if isinstance(bot_probe.get("result"), dict) else {}
    chat_result = chat_probe.get("result") if isinstance(chat_probe.get("result"), dict) else {}
    bot_id = str(bot_result.get("id") or "").strip()
    chat_type = str(chat_result.get("type") or "").strip()
    if not bot_id:
        return {
            "ok": False,
            "status": "missing_bot_identity",
            "message_ru": "Telegram: getMe не вернул id бота для проверки прав.",
            "message_en": "Telegram: getMe did not return the bot id needed for the permission check.",
            "detail_ru": "id бота не найден в ответе getMe",
            "detail_en": "bot id is missing from getMe response",
        }
    member_probe = _telegram_safe_api_probe(bot_token, "getChatMember", {"chat_id": chat_id, "user_id": bot_id})
    if not member_probe.get("ok"):
        return {
            "ok": False,
            "status": str(member_probe.get("status") or "permission_probe_failed"),
            "message_ru": "Telegram: бот или chat_id найдены, но право публикации не подтвердилось.",
            "message_en": "Telegram: bot and chat exist, but publishing permission was not confirmed.",
            "detail_ru": str(member_probe.get("error_ru") or "getChatMember не прошёл"),
            "detail_en": str(member_probe.get("error_en") or "getChatMember failed"),
        }
    member_result = member_probe.get("result") if isinstance(member_probe.get("result"), dict) else {}
    member_status = str(member_result.get("status") or "").strip()
    can_post_messages = bool(member_result.get("can_post_messages"))
    if chat_type == "channel":
        allowed = member_status == "creator" or (member_status == "administrator" and can_post_messages)
        return {
            "ok": allowed,
            "status": "ok" if allowed else "missing_permissions",
            "message_ru": "Telegram: бот не имеет права публиковать в выбранный канал." if not allowed else "Telegram: бот может публиковать в выбранный канал.",
            "message_en": "Telegram: bot cannot publish to the selected channel." if not allowed else "Telegram: bot can publish to the selected channel.",
            "detail_ru": "бот администратор канала с правом публикации" if allowed else f"статус бота: {member_status or 'unknown'}, can_post_messages={can_post_messages}",
            "detail_en": "bot is channel admin with posting permission" if allowed else f"bot status: {member_status or 'unknown'}, can_post_messages={can_post_messages}",
        }
    allowed = member_status in {"creator", "administrator", "member"}
    return {
        "ok": allowed,
        "status": "ok" if allowed else "missing_permissions",
        "message_ru": "Telegram: бот может писать в выбранный чат/группу." if allowed else "Telegram: бот не состоит в выбранном чате или не может писать туда.",
        "message_en": "Telegram: bot can post to the selected chat/group." if allowed else "Telegram: bot is not an active member of the selected chat or cannot post there.",
        "detail_ru": f"статус бота: {member_status or 'unknown'}",
        "detail_en": f"bot status: {member_status or 'unknown'}",
    }


def _vk_api_channel_preflight(cursor: Any, business_id: str) -> dict[str, Any]:
    account = _find_active_external_account(cursor, business_id, ("vk", "vk_group", "vk_business"))
    auth_data = _external_account_auth_data(account)
    binding = _vk_publish_binding(account, auth_data)
    checks = _vk_connection_checks(account, auth_data, binding)
    if not binding.get("ready"):
        return _api_channel_preflight_result(
            "vk",
            False,
            str(binding.get("status") or "missing_keys"),
            checks,
            _vk_readiness_error(str(binding.get("status") or "")),
            _vk_readiness_error(str(binding.get("status") or "")),
        )
    token = str(binding.get("token") or "").strip()
    owner_id = str(binding.get("owner_id") or "").strip()
    read_probe = _vk_safe_wall_read_probe(token, owner_id, str(auth_data.get("api_version") or "5.199"))
    checks = checks + [
        _connection_check(
            "vk_wall_read_probe",
            bool(read_probe.get("ok")),
            "VK API отвечает",
            "VK API responds",
            "wall.get прошёл; wall.post всё равно выполняется только после подтверждения" if read_probe.get("ok") else str(read_probe.get("error_ru") or "VK live-проверка не прошла"),
            "wall.get passed; wall.post still runs only after approval" if read_probe.get("ok") else str(read_probe.get("error_en") or "VK live preflight failed"),
            "ok" if read_probe.get("ok") else str(read_probe.get("status") or "failed"),
        )
    ]
    ready = bool(read_probe.get("ok"))
    return _api_channel_preflight_result(
        "vk",
        ready,
        "ready" if ready else "live_probe_failed",
        checks,
        "VK готов к API-публикации после подтверждения." if ready else "VK binding найден, но live-проверка API не прошла.",
        "VK is ready for API publishing after approval." if ready else "VK binding exists, but live API preflight failed.",
    )


def _vk_safe_wall_read_probe(token: str, owner_id: str, api_version: str) -> dict[str, Any]:
    query = urllib.parse.urlencode(
        {
            "access_token": token,
            "owner_id": owner_id,
            "count": "1",
            "filter": "owner",
            "v": api_version or "5.199",
        }
    )
    req = urllib.request.Request(f"https://api.vk.com/method/wall.get?{query}", method="GET")
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        try:
            body = resp.read().decode("utf-8", errors="ignore")
            parsed = _json_dict(body)
            status_code = int(getattr(resp, "status", 500))
        finally:
            resp.close()
    except urllib.error.HTTPError:
        error = sys.exc_info()[1]
        body = ""
        try:
            body = error.read().decode("utf-8", errors="ignore")
        except Exception:
            body = str(error)
        return _api_probe_error("vk", int(getattr(error, "code", 0) or 0), body or str(error))
    except (urllib.error.URLError, TimeoutError):
        return _api_probe_error("vk", 0, str(sys.exc_info()[1]), "network_error")
    except Exception:
        return _api_probe_error("vk", 0, str(sys.exc_info()[1]), "unexpected_error")
    if not (200 <= status_code < 300):
        return _api_probe_error("vk", status_code, body or f"VK HTTP {status_code}")
    if isinstance(parsed.get("error"), dict):
        error = parsed.get("error") or {}
        return _api_probe_error("vk", int(error.get("error_code") or 0), str(error.get("error_msg") or "VK API error"))
    return {"ok": True, "status": "ok"}


def _api_channel_preflight_for_platform(cursor: Any, business_id: str, platform: str) -> dict[str, Any]:
    normalized = str(platform or "").strip()
    if normalized == "telegram":
        return _telegram_api_channel_preflight(cursor, business_id)
    if normalized == "vk":
        return _vk_api_channel_preflight(cursor, business_id)
    if normalized == "google_business":
        return _google_business_api_channel_preflight(cursor, business_id)
    if normalized in {"instagram", "facebook"}:
        return _meta_api_channel_preflight(cursor, business_id, normalized)
    return _api_channel_preflight_result(
        normalized,
        False,
        "unsupported_api_platform",
        [],
        "Для канала нет live API-preflight.",
        "This channel has no live API preflight.",
    )


def _google_business_api_channel_preflight(cursor: Any, business_id: str) -> dict[str, Any]:
    account = _find_active_external_account(cursor, business_id, ("google_business",))
    checks = _google_business_connection_checks(account)
    has_account = bool(account)
    has_location = bool(str(account.get("external_id") or "").strip()) if account else False
    ready = has_account and has_location
    status = "ready" if ready else ("missing_binding" if has_account else "missing_connection")
    return _api_channel_preflight_result(
        "google_business",
        ready,
        status,
        checks,
        "Google Business Profile готов к API-публикации после подтверждения." if ready else _google_business_readiness_error(status),
        "Google Business Profile is ready for API publishing after approval." if ready else _google_business_readiness_error(status),
    )


def _meta_api_channel_preflight(cursor: Any, business_id: str, platform: str) -> dict[str, Any]:
    account = _find_active_external_account(cursor, business_id, ("meta", "facebook", "instagram"))
    auth_data = _external_account_auth_data(account)
    readiness = _meta_channel_readiness(account, auth_data, platform)
    status = str(readiness.get("status") or "missing_connection").strip()
    checks = _meta_connection_checks(account, auth_data, platform, status)
    return _api_channel_preflight_result(
        platform,
        bool(readiness.get("ready")),
        status,
        checks,
        _meta_readiness_error(platform, status, True),
        _meta_readiness_error(platform, status, False),
    )


def _api_channel_preflight_result(
    platform: str,
    ready: bool,
    status: str,
    checks: list[dict[str, Any]],
    message_ru: str,
    message_en: str,
    missing_fields: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "platform": platform,
        "platform_label": platform_label(platform),
        "publish_mode": "api",
        "ready": bool(ready),
        "status": str(status or "").strip(),
        "settings_path": _channel_readiness_settings_path(platform),
        "missing_fields": missing_fields if missing_fields is not None else _channel_readiness_missing_fields(platform, status),
        "message_ru": str(message_ru or "").strip(),
        "message_en": str(message_en or "").strip(),
        "connection_checks": checks,
        "read_only": True,
        "external_publish_performed": False,
    }


def _api_probe_error(provider: str, status_code: int, error: str, status: str = "api_error") -> dict[str, Any]:
    clean_error = str(error or "").strip()[:500]
    return {
        "ok": False,
        "provider": str(provider or "").strip(),
        "status": str(status or "api_error").strip(),
        "status_code": int(status_code or 0),
        "error_ru": clean_error,
        "error_en": clean_error,
    }


def _publish_external_account_post(
    cursor: Any,
    post: dict[str, Any],
    sources: tuple[str, ...],
    missing_message: str,
    ready_status: str,
) -> dict[str, Any]:
    account = _find_active_external_account(cursor, str(post.get("business_id") or ""), sources)
    if not account:
        return {
            "status": "needs_manual_publish",
            "last_error": missing_message,
            "metadata_json": {"provider_status": "connection_missing", "expected_sources": list(sources)},
        }
    auth_data = _external_account_auth_data(account)
    if not auth_data and sources != ("google_business",):
        return {
            "status": "needs_manual_publish",
            "last_error": missing_message,
            "metadata_json": {
                "provider_status": "credentials_missing",
                "external_account_id": account.get("id"),
                "expected_sources": list(sources),
            },
        }
    # Meta/other external-account adapters are preflight-only until a native
    # provider publish implementation is explicitly enabled. Returning queued
    # here would make the worker pick the same post forever without publishing.
    return {
        "status": "needs_manual_publish",
        "last_error": "API-публикация для канала ещё не включена; используйте ручное размещение или подключите native adapter.",
        "metadata_json": {
            "provider_status": ready_status,
            "external_account_id": account.get("id"),
            "external_account_source": account.get("source"),
            "provider_note": "Adapter preflight passed, but native provider publish is not enabled; manual handoff is required.",
        },
    }


def _owner_id_for_business(business_id: str) -> str:
    if not business_id:
        return ""
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        return str(get_business_owner_id(cursor, business_id) or "").strip()
    finally:
        db.close()


def _mark_dispatch_failure(post_id: str, message: str) -> None:
    if not post_id:
        return
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE social_posts
            SET status = 'failed',
                last_error = %s,
                updated_at = NOW()
            WHERE id = %s
              AND status IN ('queued', 'publishing')
            """,
            (str(message or "Social post dispatch failed").strip()[:1000], post_id),
        )
        db.conn.commit()
    except Exception:
        db.conn.rollback()
    finally:
        db.close()


def _load_business_publish_context(cursor: Any, business_id: str) -> dict[str, Any]:
    if not business_id:
        return {}
    columns = _table_columns(cursor, "businesses")
    select_parts = ["businesses.id id", "businesses.name name"]
    for column in ("owner_id", "telegram_bot_token", "telegram_chat_id"):
        if column in columns:
            select_parts.append(f"businesses.{column} {column}")
        else:
            select_parts.append(f"NULL {column}")
    owner_join = ""
    if "owner_id" in columns:
        select_parts.append("u.telegram_id owner_telegram_id")
        owner_join = "LEFT JOIN users u ON u.id = businesses.owner_id"
    else:
        select_parts.append("NULL owner_telegram_id")
    cursor.execute(
        f"""
        SELECT {", ".join(select_parts)}
        FROM businesses
        {owner_join}
        WHERE businesses.id = %s
        LIMIT 1
        """,
        (business_id,),
    )
    return _row_to_dict(cursor, cursor.fetchone())


def _map_publish_target(cursor: Any, business_id: str, platform: str) -> dict[str, Any]:
    business = _load_business_publish_target_context(cursor, business_id)
    target = {
        "business_name": str(business.get("name") or "").strip(),
        "location_label": _location_label_from_business(business),
        "target_url": "",
        "target_url_source": "",
        "profile_hint": "",
    }
    platform_key = str(platform or "").strip()
    if platform_key == "yandex_maps":
        target["profile_hint"] = "Яндекс Бизнес / Яндекс Карты"
        yandex_url = str(business.get("yandex_url") or "").strip()
        if yandex_url:
            target["target_url"] = yandex_url
            target["target_url_source"] = "businesses.yandex_url"
            return target
    elif platform_key == "two_gis":
        target["profile_hint"] = "2ГИС профиль бизнеса"
    if not business_id or not _table_exists(cursor, "businessmaplinks"):
        return target
    map_types = ("yandex", "yandex_maps", "yandex_business") if platform_key == "yandex_maps" else ("2gis", "two_gis", "apify_2gis")
    try:
        cursor.execute(
            """
            SELECT url, map_type
            FROM businessmaplinks
            WHERE business_id = %s
              AND (
                LOWER(COALESCE(map_type, '')) = ANY(%s)
                OR (%s = 'yandex_maps' AND LOWER(COALESCE(url, '')) LIKE '%%yandex%%')
                OR (%s = 'two_gis' AND (LOWER(COALESCE(url, '')) LIKE '%%2gis.ru%%' OR LOWER(COALESCE(url, '')) LIKE '%%2gis.com%%'))
              )
            ORDER BY created_at DESC NULLS LAST
            LIMIT 1
            """,
            (business_id, list(map_types), platform_key, platform_key),
        )
        row = _row_to_dict(cursor, cursor.fetchone())
    except Exception:
        row = {}
    url = str(row.get("url") or "").strip()
    if url:
        target["target_url"] = url
        target["target_url_source"] = f"businessmaplinks.{row.get('map_type') or platform_key}"
    return target


def _load_business_publish_target_context(cursor: Any, business_id: str) -> dict[str, Any]:
    if not business_id:
        return {}
    columns = _table_columns(cursor, "businesses")
    select_parts = ["id"]
    for column in ("name", "city", "address", "yandex_url"):
        if column in columns:
            select_parts.append(column)
        else:
            select_parts.append(f"NULL AS {column}")
    cursor.execute(
        f"""
        SELECT {", ".join(select_parts)}
        FROM businesses
        WHERE id = %s
        LIMIT 1
        """,
        (business_id,),
    )
    return _row_to_dict(cursor, cursor.fetchone())


def _location_label_from_business(business: dict[str, Any]) -> str:
    parts = [
        str(business.get("city") or "").strip(),
        str(business.get("address") or "").strip(),
    ]
    return ", ".join([part for part in parts if part])


def _find_active_external_account(cursor: Any, business_id: str, sources: tuple[str, ...]) -> dict[str, Any]:
    if not business_id or not sources:
        return {}
    if not _table_exists(cursor, "externalbusinessaccounts"):
        return {}
    columns = _table_columns(cursor, "externalbusinessaccounts")
    if not {"business_id", "source"}.issubset(columns):
        return {}
    select_parts = ["id", "business_id", "source"]
    for column in ("external_id", "display_name", "auth_data_encrypted", "last_error"):
        if column in columns:
            select_parts.append(column)
        else:
            select_parts.append(f"NULL AS {column}")
    is_active_sql = "COALESCE(is_active, TRUE)" if "is_active" in columns else "TRUE"
    order_sql = "updated_at DESC NULLS LAST, created_at DESC NULLS LAST" if "updated_at" in columns else "id DESC"
    cursor.execute(
        f"""
        SELECT {", ".join(select_parts)}
        FROM externalbusinessaccounts
        WHERE business_id = %s
          AND source = ANY(%s)
          AND {is_active_sql}
        ORDER BY {order_sql}
        LIMIT 1
        """,
        (business_id, list(sources)),
    )
    return _row_to_dict(cursor, cursor.fetchone())


def _external_account_auth_data(account: dict[str, Any]) -> dict[str, Any]:
    encrypted = str(account.get("auth_data_encrypted") or "").strip()
    if not encrypted:
        return {}
    try:
        decrypted = decrypt_auth_data(encrypted)
        parsed = _json_value(decrypted, {})
        return parsed if isinstance(parsed, dict) else {"raw": str(decrypted or "").strip()}
    except Exception:
        return {}


def _vk_publish_binding(account: dict[str, Any], auth_data: dict[str, Any]) -> dict[str, Any]:
    if not account:
        return {"ready": False, "status": "missing_connection"}
    token = str(auth_data.get("access_token") or auth_data.get("token") or "").strip()
    group_id = str(auth_data.get("group_id") or auth_data.get("community_id") or account.get("external_id") or "").strip()
    owner_id = str(auth_data.get("owner_id") or "").strip()
    if not owner_id and group_id:
        clean_group_id = group_id[1:] if group_id.startswith("-") else group_id
        owner_id = f"-{clean_group_id}"
    if not token:
        return {"ready": False, "status": "missing_keys", "owner_id": owner_id}
    if not owner_id:
        return {"ready": False, "status": "missing_binding", "token": token}
    if _auth_scope_is_explicit(auth_data) and not _auth_scope_allows(auth_data, {"wall", "wall.post"}):
        return {"ready": False, "status": "missing_permissions", "token": token, "owner_id": owner_id}
    return {
        "ready": True,
        "status": "ready",
        "token": token,
        "owner_id": owner_id,
    }


def _meta_publish_status(account: dict[str, Any], auth_data: dict[str, Any], platform: str) -> str:
    if not account:
        return "missing_connection"
    if not str(auth_data.get("access_token") or auth_data.get("token") or "").strip():
        return "missing_keys"
    has_page_binding = bool(str(auth_data.get("page_id") or account.get("external_id") or "").strip())
    has_ig_binding = bool(str(auth_data.get("ig_user_id") or auth_data.get("instagram_business_account_id") or "").strip())
    if platform == "instagram" and not has_ig_binding:
        return "missing_binding"
    if platform == "facebook" and not has_page_binding:
        return "missing_binding"
    if _auth_scope_is_explicit(auth_data):
        required = {"pages_manage_posts", "pages_read_engagement"}
        if platform == "instagram":
            required = {"instagram_content_publish"}
        if not _auth_scope_allows(auth_data, required):
            return "missing_permissions"
    return "ready"


def _meta_channel_readiness(account: dict[str, Any], auth_data: dict[str, Any], platform: str) -> dict[str, Any]:
    status = _meta_publish_status(account, auth_data, platform)
    if status == "ready":
        return {
            "ready": False,
            "status": "adapter_pending",
        }
    return {
        "ready": False,
        "status": status,
    }


def _auth_scope_is_explicit(auth_data: dict[str, Any]) -> bool:
    for key in ("scope", "scopes", "permissions", "granted_scopes", "granted_permissions"):
        if key in auth_data and auth_data.get(key):
            return True
    return False


def _auth_scope_allows(auth_data: dict[str, Any], accepted: set[str]) -> bool:
    tokens = _auth_scope_tokens(auth_data)
    if not tokens:
        return False
    accepted_normalized = {str(item or "").strip().lower() for item in accepted if str(item or "").strip()}
    return bool(tokens.intersection(accepted_normalized))


def _auth_scope_tokens(auth_data: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for key in ("scope", "scopes", "permissions", "granted_scopes", "granted_permissions"):
        _collect_scope_tokens(auth_data.get(key), tokens)
    return tokens


def _collect_scope_tokens(value: Any, tokens: set[str]) -> None:
    if value is None:
        return
    if isinstance(value, dict):
        for nested_value in value.values():
            _collect_scope_tokens(nested_value, tokens)
        return
    if isinstance(value, (list, tuple, set)):
        for nested_value in value:
            _collect_scope_tokens(nested_value, tokens)
        return
    raw = str(value or "").replace(",", " ").replace(";", " ")
    for token in raw.split():
        normalized = token.strip().lower()
        if normalized:
            tokens.add(normalized)


def _vk_readiness_error(status: str) -> str:
    normalized = str(status or "").strip()
    if normalized == "missing_permissions":
        return "VK token найден, но в правах нет wall.post."
    if normalized == "missing_binding":
        return "Для VK нужен group_id или owner_id группы/страницы."
    if normalized == "missing_connection":
        return "VK аккаунт/группа не подключены."
    return "Для VK нужны access_token и group_id/owner_id с правом wall.post."


def _google_business_readiness_error(status: str) -> str:
    normalized = str(status or "").strip()
    if normalized == "missing_binding":
        return "Google Business Profile подключен, но локация для публикации не выбрана."
    if normalized == "missing_connection":
        return "Google Business Profile не подключен."
    return "Проверьте Google Business Profile OAuth, локацию и разрешения."


def _meta_readiness_error(platform: str, status: str, is_ru: bool) -> str:
    label = platform_label(platform)
    normalized = str(status or "").strip()
    if normalized == "adapter_pending":
        return (
            f"{label}: подключение выглядит готовым, но native Meta publish ещё не включён; используйте ручной режим."
            if is_ru
            else f"{label}: connection looks ready, but native Meta publish is not enabled yet; use manual fallback."
        )
    if normalized == "missing_permissions":
        return (
            f"{label}: не хватает Meta permissions для публикации."
            if is_ru
            else f"{label}: Meta publishing permissions are missing."
        )
    if normalized == "missing_binding":
        return (
            f"{label}: выберите Facebook Page или Instagram business account."
            if is_ru
            else f"{label}: choose a Facebook Page or Instagram business account."
        )
    if normalized == "missing_keys":
        return (
            f"{label}: нужен Meta access token."
            if is_ru
            else f"{label}: Meta access token is required."
        )
    return (
        f"{label}: Meta account не подключён."
        if is_ru
        else f"{label}: Meta account is not connected."
    )


def _collect_provider_metrics_for_post(cursor: Any, post: dict[str, Any]) -> dict[str, Any]:
    platform = str(post.get("platform") or "").strip()
    if platform == "telegram":
        return _collect_telegram_post_metrics(post)
    if platform == "vk":
        return _collect_vk_post_metrics(cursor, post)
    if platform == "google_business":
        return _provider_metrics_placeholder(
            platform,
            "google_business_api",
            "google_business_metrics_not_enabled",
        )
    if platform in {"instagram", "facebook"}:
        return _provider_metrics_placeholder(
            platform,
            "meta_graph_api",
            "meta_graph_metrics_permissions_required",
        )
    if platform in BROWSER_OR_MANUAL_PLATFORMS:
        return _provider_metrics_placeholder(
            platform,
            "manual_or_supervised_map",
            "map_metrics_manual_input_required",
        )
    return {"source": "manual_attribution_only", "provider": platform or "unknown"}


def _provider_metrics_placeholder(platform: str, source: str, status: str) -> dict[str, Any]:
    return {
        "source": str(source or "manual_attribution_only").strip(),
        "provider": str(platform or "unknown").strip(),
        "status": str(status or "manual_metrics_required").strip(),
        "views": 0,
        "likes": 0,
        "comments": 0,
        "shares": 0,
        "clicks": 0,
    }


def _collect_telegram_post_metrics(post: dict[str, Any]) -> dict[str, Any]:
    message_id = str(post.get("provider_post_id") or "").strip()
    if not message_id:
        return {
            "source": "telegram_bot_api",
            "provider": "telegram",
            "status": "missing_provider_post_binding",
        }
    return {
        "source": "telegram_bot_api",
        "provider": "telegram",
        "status": "telegram_bot_api_metrics_unavailable",
        "provider_post_id": message_id,
        "views": 0,
        "likes": 0,
        "comments": 0,
        "shares": 0,
        "clicks": 0,
    }


def _collect_vk_post_metrics(cursor: Any, post: dict[str, Any]) -> dict[str, Any]:
    account = _find_active_external_account(cursor, str(post.get("business_id") or ""), ("vk", "vk_group", "vk_business"))
    auth_data = _external_account_auth_data(account)
    binding = _vk_publish_binding(account, auth_data)
    if not binding.get("ready"):
        return {"source": "vk_api", "provider": "vk", "status": str(binding.get("status") or "vk_not_ready")}
    token = str(binding.get("token") or "").strip()
    owner_id = _vk_metrics_owner_id(post, binding)
    post_id = str(post.get("provider_post_id") or "").strip()
    if not token or not owner_id or not post_id:
        return {"source": "vk_api", "provider": "vk", "status": "missing_provider_post_binding"}
    query = urllib.parse.urlencode(
        {
            "access_token": token,
            "posts": f"{owner_id}_{post_id}",
            "v": str(auth_data.get("api_version") or "5.199"),
        }
    )
    req = urllib.request.Request(f"https://api.vk.com/method/wall.getById?{query}", method="GET")
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        try:
            body = resp.read().decode("utf-8", errors="ignore")
            parsed = _json_dict(body)
        finally:
            resp.close()
    except Exception:
        return {"source": "vk_api", "provider": "vk", "status": "vk_metrics_network_error", "error": str(sys.exc_info()[1])}
    if isinstance(parsed.get("error"), dict):
        return {"source": "vk_api", "provider": "vk", "status": "vk_metrics_api_error", "error": parsed.get("error")}
    response = parsed.get("response")
    item = response[0] if isinstance(response, list) and response else {}
    if not isinstance(item, dict):
        return {"source": "vk_api", "provider": "vk", "status": "vk_metrics_empty_response", "response": parsed}
    views = int(_json_dict(item.get("views")).get("count") or 0)
    likes = int(_json_dict(item.get("likes")).get("count") or 0)
    comments = int(_json_dict(item.get("comments")).get("count") or 0)
    shares = int(_json_dict(item.get("reposts")).get("count") or 0)
    return {
        "source": "vk_api",
        "provider": "vk",
        "status": "vk_metrics_collected",
        "views": views,
        "impressions": views,
        "reach": views,
        "likes": likes,
        "comments": comments,
        "shares": shares,
        "clicks": 0,
        "provider_post_id": post_id,
        "owner_id": owner_id,
    }


def _vk_metrics_owner_id(post: dict[str, Any], binding: dict[str, Any]) -> str:
    provider_url = str(post.get("provider_post_url") or "").strip()
    if "wall" in provider_url:
        tail = provider_url.rsplit("wall", 1)[-1]
        owner = tail.split("_", 1)[0].strip()
        if owner:
            return owner
    return str(binding.get("owner_id") or "").strip()


def _telegram_post_url(chat_id: str, message_id: str) -> str:
    chat = str(chat_id or "").strip()
    message = str(message_id or "").strip()
    if not chat or not message:
        return ""
    if chat.startswith("@"):
        return f"https://t.me/{chat[1:]}/{message}"
    normalized = chat[4:] if chat.startswith("-100") else ""
    if normalized:
        return f"https://t.me/c/{normalized}/{message}"
    return ""


def _vk_post_url(owner_id: str, post_id: str) -> str:
    owner = str(owner_id or "").strip()
    post = str(post_id or "").strip()
    if not owner or not post:
        return ""
    return f"https://vk.com/wall{owner}_{post}"


def _upsert_manual_attribution_metrics(cursor: Any, post_id: str) -> None:
    metrics = _attribution_metrics_for_post(cursor, post_id)
    cursor.execute(
        """
        INSERT INTO social_post_metrics (
            id, social_post_id, metric_date, views, impressions, reach, likes, comments, shares, clicks, inquiries, leads, raw_json, captured_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (social_post_id, metric_date)
        DO UPDATE SET
            views = GREATEST(social_post_metrics.views, EXCLUDED.views),
            impressions = GREATEST(social_post_metrics.impressions, EXCLUDED.impressions),
            reach = GREATEST(social_post_metrics.reach, EXCLUDED.reach),
            likes = GREATEST(social_post_metrics.likes, EXCLUDED.likes),
            comments = GREATEST(social_post_metrics.comments, EXCLUDED.comments),
            shares = GREATEST(social_post_metrics.shares, EXCLUDED.shares),
            clicks = GREATEST(social_post_metrics.clicks, EXCLUDED.clicks),
            inquiries = GREATEST(social_post_metrics.inquiries, EXCLUDED.inquiries),
            leads = GREATEST(social_post_metrics.leads, EXCLUDED.leads),
            raw_json = EXCLUDED.raw_json,
            captured_at = NOW()
        """,
        (
            _new_id(),
            post_id,
            date.today(),
            metrics.get("views", 0),
            metrics.get("views", 0),
            metrics.get("views", 0),
            metrics.get("likes", 0),
            metrics.get("comments", 0),
            metrics.get("shares", 0),
            metrics.get("clicks", 0),
            metrics.get("inquiries", 0),
            metrics.get("leads", 0),
            _json_dumps({"collector": "manual_attribution_v1", "attribution": metrics}),
        ),
    )


def _merge_metric_totals_into_posts(cursor: Any, posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    post_ids = [str(post.get("id") or "").strip() for post in posts if str(post.get("id") or "").strip()]
    if not post_ids:
        return posts
    cursor.execute(
        """
        SELECT
            social_post_id,
            COALESCE(SUM(views), 0) AS views,
            COALESCE(SUM(impressions), 0) AS impressions,
            COALESCE(SUM(reach), 0) AS reach,
            COALESCE(SUM(likes), 0) AS likes,
            COALESCE(SUM(comments), 0) AS comments,
            COALESCE(SUM(shares), 0) AS shares,
            COALESCE(SUM(clicks), 0) AS clicks,
            COALESCE(SUM(inquiries), 0) AS inquiries,
            COALESCE(SUM(leads), 0) AS leads
        FROM social_post_metrics
        WHERE social_post_id = ANY(%s)
        GROUP BY social_post_id
        """,
        (post_ids,),
    )
    totals_by_post_id: dict[str, dict[str, int]] = {}
    for row in cursor.fetchall() or []:
        data = _row_to_dict(cursor, row)
        social_post_id = str(data.get("social_post_id") or "").strip()
        if not social_post_id:
            continue
        totals_by_post_id[social_post_id] = {
            "views": int(data.get("views") or 0),
            "impressions": int(data.get("impressions") or 0),
            "reach": int(data.get("reach") or 0),
            "likes": int(data.get("likes") or 0),
            "comments": int(data.get("comments") or 0),
            "shares": int(data.get("shares") or 0),
            "clicks": int(data.get("clicks") or 0),
            "inquiries": int(data.get("inquiries") or 0),
            "leads": int(data.get("leads") or 0),
        }
    enriched_posts = []
    for post in posts:
        post_id = str(post.get("id") or "").strip()
        enriched_posts.append({**post, **totals_by_post_id.get(post_id, {})})
    return enriched_posts


def _attribution_metrics_for_post(cursor: Any, post_id: str) -> dict[str, int]:
    if not post_id:
        return {"views": 0, "likes": 0, "comments": 0, "shares": 0, "clicks": 0, "inquiries": 0, "leads": 0}
    cursor.execute(
        """
        SELECT event_type, COALESCE(SUM(value), 0) AS total
        FROM social_post_attribution_events
        WHERE social_post_id = %s
        GROUP BY event_type
        """,
        (post_id,),
    )
    result = {"views": 0, "likes": 0, "comments": 0, "shares": 0, "clicks": 0, "inquiries": 0, "leads": 0}
    for row in cursor.fetchall() or []:
        event_type = str(_row_get(row, "event_type", 0) or "").strip()
        total = int(_row_get(row, "total", 1, 0) or 0)
        if event_type == "lead":
            result["leads"] += total
        elif event_type == "inquiry":
            result["inquiries"] += total
        elif event_type == "comment":
            result["comments"] += total
        elif event_type == "share":
            result["shares"] += total
        elif event_type == "click":
            result["clicks"] += total
        elif event_type == "like":
            result["likes"] += total
        elif event_type == "view":
            result["views"] += total
    return result


def _base_text_from_item(item: dict[str, Any]) -> str:
    draft = str(item.get("draft_text") or "").strip()
    if draft:
        return draft
    theme = str(item.get("theme") or "").strip()
    goal = str(item.get("goal") or "").strip()
    parts = [value for value in [theme, goal] if value]
    return "\n\n".join(parts)


def _platform_text(platform: str, base_text: str) -> str:
    text = str(base_text or "").strip()
    if not text:
        return ""
    if platform == "telegram":
        return text
    if platform == "vk":
        return text
    if platform in {"instagram", "facebook"}:
        return text
    if platform == "google_business":
        return text[:1500]
    if platform in BROWSER_OR_MANUAL_PLATFORMS:
        return text[:1200]
    return text


def _normalize_platforms(platforms: list[str] | None) -> list[str]:
    if not platforms:
        return list(SOCIAL_POST_PLATFORMS)
    result = []
    seen = set()
    for value in platforms:
        platform = str(value or "").strip()
        if platform not in SOCIAL_POST_PLATFORMS or platform in seen:
            continue
        seen.add(platform)
        result.append(platform)
    if not result:
        raise ValueError("Не выбраны поддерживаемые каналы публикации")
    return result


def _normalize_ids(values: list[str], limit: int = 100) -> list[str]:
    result = []
    seen = set()
    for value in values or []:
        item_id = str(value or "").strip()
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        result.append(item_id)
        if len(result) >= limit:
            break
    if not result:
        raise ValueError("Не выбраны элементы для действия")
    return result


def _table_exists(cursor: Any, table_name: str) -> bool:
    cursor.execute("SELECT to_regclass(%s)", (f"public.{table_name}",))
    row = cursor.fetchone()
    return bool(_row_get(row, "to_regclass", 0))


def _table_columns(cursor: Any, table_name: str) -> set[str]:
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = %s
        """,
        (str(table_name or "").strip().lower(),),
    )
    columns = set()
    for row in cursor.fetchall() or []:
        value = _row_get(row, "column_name", 0)
        if value:
            columns.add(str(value).lower())
    return columns


def _summary_for_posts(posts: list[dict[str, Any]]) -> dict[str, Any]:
    by_status: dict[str, int] = {}
    by_platform: dict[str, int] = {}
    for post in posts:
        status = str(post.get("status") or "draft")
        platform = str(post.get("platform") or "unknown")
        by_status[status] = by_status.get(status, 0) + 1
        by_platform[platform] = by_platform.get(platform, 0) + 1
    return {
        "total": len(posts),
        "by_status": by_status,
        "by_platform": by_platform,
        "needs_review": by_status.get("needs_review", 0) + by_status.get("draft", 0),
        "scheduled": by_status.get("queued", 0),
        "needs_supervised_publish": by_status.get("needs_supervised_publish", 0),
        "needs_manual_publish": by_status.get("needs_manual_publish", 0),
        "published": by_status.get("published", 0),
        "failed": by_status.get("failed", 0),
    }


def _social_first_api_proof_dossier(
    posts: list[dict[str, Any]],
    channel_readiness: list[dict[str, Any]],
    plan_item_count: int = 0,
) -> dict[str, Any]:
    api_channels = [
        item for item in channel_readiness
        if str(item.get("publish_mode") or "").strip() == "api"
    ]
    ready_channels = sorted(
        [item for item in api_channels if bool(item.get("ready"))],
        key=lambda item: _social_first_api_priority_rank(str(item.get("platform") or "")),
    )
    blocked_channels = sorted(
        [item for item in api_channels if not bool(item.get("ready"))],
        key=lambda item: _social_first_api_priority_rank(str(item.get("platform") or "")),
    )
    ready_platforms = {
        str(item.get("platform") or "").strip()
        for item in ready_channels
        if str(item.get("platform") or "").strip()
    }
    api_posts = [
        post for post in posts
        if str(post.get("platform") or "").strip() in API_PLATFORMS
    ]
    published_with_proof = sorted([
        post for post in api_posts
        if str(post.get("status") or "").strip() == "published"
        and (
            str(post.get("provider_post_id") or "").strip()
            or str(post.get("provider_post_url") or "").strip()
        )
    ], key=_social_first_api_post_priority)
    proof_candidate_posts = [
        post for post in api_posts
        if str(post.get("platform") or "").strip() in ready_platforms
    ]
    queued_posts = sorted(
        [post for post in proof_candidate_posts if str(post.get("status") or "").strip() == "queued"],
        key=_social_first_api_post_priority,
    )
    approved_posts = sorted(
        [post for post in proof_candidate_posts if str(post.get("status") or "").strip() == "approved"],
        key=_social_first_api_post_priority,
    )
    review_posts = sorted([
        post for post in api_posts
        if str(post.get("status") or "").strip() in {"draft", "needs_review"}
        and str(post.get("platform") or "").strip() in ready_platforms
    ], key=_social_first_api_post_priority)
    failed_or_manual_posts = sorted([
        post for post in api_posts
        if str(post.get("status") or "").strip() in {"failed", "needs_manual_publish"}
        and str(post.get("platform") or "").strip() in ready_platforms
    ], key=_social_first_api_post_priority)

    candidate: dict[str, Any] = {}
    if published_with_proof:
        status = "proof_complete"
        candidate = published_with_proof[0]
    elif queued_posts:
        status = "wait_for_worker_or_run_once"
        candidate = queued_posts[0]
    elif approved_posts:
        status = "queue_approved_post"
        candidate = approved_posts[0]
    elif review_posts:
        status = "review_and_approve"
        candidate = review_posts[0]
    elif failed_or_manual_posts:
        status = "fix_or_manual_fallback"
        candidate = failed_or_manual_posts[0]
    elif ready_channels and int(plan_item_count or 0) > 0:
        status = "prepare_first_post"
    elif int(plan_item_count or 0) > 0:
        status = "connect_first_api_channel"
    else:
        status = "create_content_plan"

    recommended_channel = ready_channels[0] if ready_channels else (blocked_channels[0] if blocked_channels else {})
    platform = str(candidate.get("platform") or recommended_channel.get("platform") or "").strip()
    label = str(
        candidate.get("platform_label")
        or recommended_channel.get("platform_label")
        or platform_label(platform)
        or "API"
    ).strip()
    provider_post_id = str(candidate.get("provider_post_id") or "").strip()
    provider_post_url = str(candidate.get("provider_post_url") or "").strip()

    return {
        "schema": "localos_social_first_api_proof_dossier_v1",
        "status": status,
        "ready": status == "proof_complete",
        "candidate_post_id": str(candidate.get("id") or "").strip(),
        "candidate_status": str(candidate.get("status") or "").strip(),
        "recommended_platform": platform,
        "recommended_platform_label": label,
        "ready_api_channels": [
            {
                "platform": str(item.get("platform") or "").strip(),
                "platform_label": str(item.get("platform_label") or platform_label(str(item.get("platform") or ""))).strip(),
                "status": str(item.get("status") or "ready").strip(),
            }
            for item in ready_channels
        ],
        "blocked_api_channels": [
            {
                "platform": str(item.get("platform") or "").strip(),
                "platform_label": str(item.get("platform_label") or platform_label(str(item.get("platform") or ""))).strip(),
                "status": str(item.get("status") or "needs_attention").strip(),
                "next_action_ru": str(item.get("next_action_ru") or "").strip(),
                "next_action_en": str(item.get("next_action_en") or "").strip(),
                "settings_path": str(item.get("settings_path") or _api_preflight_settings_path(str(item.get("platform") or ""))).strip(),
            }
            for item in blocked_channels
        ],
        "provider_post_id": provider_post_id,
        "provider_post_url": provider_post_url,
        "external_publish_requires_approval": True,
        "external_publish_performed": False,
        "browser_final_click_allowed": False,
        "maps_are_supervised_or_manual": True,
        "primary_metric_ru": "Заявки и обращения",
        "primary_metric_en": "Leads and inquiries",
        "title_ru": _social_first_api_proof_dossier_title(status, True),
        "title_en": _social_first_api_proof_dossier_title(status, False),
        "summary_ru": _social_first_api_proof_dossier_summary(status, label, candidate, True),
        "summary_en": _social_first_api_proof_dossier_summary(status, label, candidate, False),
        "next_action_ru": _social_first_api_proof_dossier_next_action(status, label, recommended_channel, True),
        "next_action_en": _social_first_api_proof_dossier_next_action(status, label, recommended_channel, False),
        "steps_ru": _social_first_api_proof_dossier_steps(status, label, True),
        "steps_en": _social_first_api_proof_dossier_steps(status, label, False),
    }


def _social_first_api_priority_rank(platform: str) -> int:
    priority = {
        "telegram": 0,
        "vk": 1,
        "google_business": 2,
        "instagram": 3,
        "facebook": 4,
    }
    return priority.get(str(platform or "").strip(), 99)


def _social_first_api_post_priority(post: dict[str, Any]) -> tuple[int, str]:
    platform = str(post.get("platform") or "").strip()
    scheduled_for = str(post.get("scheduled_for") or "").strip()
    created_at = str(post.get("created_at") or "").strip()
    post_id = str(post.get("id") or "").strip()
    return (_social_first_api_priority_rank(platform), scheduled_for or created_at or post_id)


def _social_first_api_proof_dossier_title(status: str, is_ru: bool) -> str:
    if status == "proof_complete":
        return "Первый API-proof готов" if is_ru else "First API proof is ready"
    if status == "wait_for_worker_or_run_once":
        return "Первый API-пост ждёт worker" if is_ru else "First API post is waiting for the worker"
    if status == "queue_approved_post":
        return "Утверждённый API-пост нужно поставить в расписание" if is_ru else "Approved API post needs queueing"
    if status == "review_and_approve":
        return "Первый API-пост нужно проверить" if is_ru else "First API post needs review"
    if status == "fix_or_manual_fallback":
        return "Первый API-пост требует исправления" if is_ru else "First API post needs recovery"
    if status == "prepare_first_post":
        return "Готов канал для первого API-поста" if is_ru else "A channel is ready for the first API post"
    if status == "connect_first_api_channel":
        return "Сначала подключите API-канал" if is_ru else "Connect an API channel first"
    return "Сначала нужен контент-план" if is_ru else "Create a content plan first"


def _social_first_api_proof_dossier_summary(
    status: str,
    label: str,
    candidate: dict[str, Any],
    is_ru: bool,
) -> str:
    if status == "proof_complete":
        proof = str(candidate.get("provider_post_url") or candidate.get("provider_post_id") or "").strip()
        return (
            f"{label} уже дал proof публикации: {proof}. Теперь можно собирать реакции и заявки."
            if is_ru
            else f"{label} already has publish proof: {proof}. Now collect reactions and leads."
        )
    if status == "wait_for_worker_or_run_once":
        return (
            f"{label}: пост уже в queue. Следующий безопасный шаг — scoped worker или ручной run-once из LocalOS."
            if is_ru
            else f"{label}: the post is queued. The next safe step is a scoped worker cycle or manual LocalOS run-once."
        )
    if status == "queue_approved_post":
        return (
            f"{label}: текст подтверждён, но ещё не поставлен в расписание."
            if is_ru
            else f"{label}: copy is approved but not queued yet."
        )
    if status == "review_and_approve":
        return (
            f"{label}: есть черновик для проверки. Подтверждение не публикует наружу."
            if is_ru
            else f"{label}: a draft is ready for review. Approval does not publish externally."
        )
    if status == "fix_or_manual_fallback":
        return (
            f"{label}: пост заблокирован ошибкой или подключением. Исправьте канал или используйте ручной режим."
            if is_ru
            else f"{label}: the post is blocked by an error or connection issue. Fix the channel or use manual fallback."
        )
    if status == "prepare_first_post":
        return (
            f"{label} готов к первому proof: возьмите ближайшую тему плана и подготовьте канал."
            if is_ru
            else f"{label} is ready for the first proof: take the nearest plan topic and prepare the channel."
        )
    if status == "connect_first_api_channel":
        return (
            "План есть, но ни один API-канал ещё не готов. Быстрее всего начать с Telegram или VK."
            if is_ru
            else "A plan exists, but no API channel is ready yet. Telegram or VK is the fastest start."
        )
    return (
        "Откройте или создайте контент-план, затем подготовьте посты по каналам."
        if is_ru
        else "Open or create a content plan, then prepare channel posts."
    )


def _social_first_api_proof_dossier_next_action(
    status: str,
    label: str,
    recommended_channel: dict[str, Any],
    is_ru: bool,
) -> str:
    setup_action = str(recommended_channel.get("next_action_ru" if is_ru else "next_action_en") or "").strip()
    if status == "proof_complete":
        return (
            "Соберите реакции/заявки и предложите корректировку следующего плана."
            if is_ru
            else "Collect reactions/leads and suggest the next plan adjustment."
        )
    if status == "wait_for_worker_or_run_once":
        return (
            "Проверьте launch preflight, затем запустите scoped worker/run-once с явным подтверждением."
            if is_ru
            else "Check launch preflight, then run the scoped worker/run-once with explicit confirmation."
        )
    if status == "queue_approved_post":
        return "Нажмите “Поставить в расписание” для этого API-поста." if is_ru else "Click Queue on schedule for this API post."
    if status == "review_and_approve":
        return "Откройте preview, сохраните правки и нажмите “Подтвердить”." if is_ru else "Open preview, save edits, and click Approve."
    if status == "fix_or_manual_fallback":
        return (
            "Откройте настройку канала, повторите live API-проверку или отметьте ручной режим."
            if is_ru
            else "Open channel setup, rerun live API preflight, or mark manual fallback."
        )
    if status == "prepare_first_post":
        return (
            f"Подготовьте первый пост для {label}, затем пройдите preview → approval → queue."
            if is_ru
            else f"Prepare the first {label} post, then go through preview → approval → queue."
        )
    if status == "connect_first_api_channel":
        return setup_action or (
            "Подключите Telegram или VK и повторите live API-проверку."
            if is_ru
            else "Connect Telegram or VK and rerun live API preflight."
        )
    return "Создайте контент-план на неделю." if is_ru else "Create a weekly content plan."


def _social_first_api_proof_dossier_steps(status: str, label: str, is_ru: bool) -> list[str]:
    if status == "proof_complete":
        return [
            "Проверьте provider_post_id/provider_post_url.",
            "Соберите реакции и отметьте заявки/обращения.",
            "Предложите изменения следующего плана, но применяйте только после подтверждения.",
        ] if is_ru else [
            "Check provider_post_id/provider_post_url.",
            "Collect reactions and mark leads/inquiries.",
            "Suggest next-plan changes, but apply only after approval.",
        ]
    if status == "wait_for_worker_or_run_once":
        return [
            "Проверьте, что пост подтверждён, стоит в расписании и его дата уже наступила.",
            "Запустите ограниченный цикл исполнителя только после явного подтверждения.",
            "После публикации проверьте provider_post_id/provider_post_url.",
        ] if is_ru else [
            "Check that the post is approved, queued, and due.",
            "Run scoped worker/run-once only after explicit confirmation.",
            "After publishing, check provider_post_id/provider_post_url.",
        ]
    if status == "queue_approved_post":
        return [
            "Откройте предпросмотр поста.",
            "Проверьте дату и канал.",
            "Поставьте в расписание; это ещё не отправляет наружу до даты публикации и запуска исполнителя.",
        ] if is_ru else [
            "Open the post preview.",
            "Check date and channel.",
            "Queue it; this still does not send externally until the due worker cycle.",
        ]
    if status == "review_and_approve":
        return [
            "Проверьте текст под конкретную площадку.",
            "Сохраните правки.",
            "Подтвердите текст; подтверждение отделено от публикации.",
        ] if is_ru else [
            "Review platform-specific copy.",
            "Save edits.",
            "Approve copy; approval is separate from publishing.",
        ]
    if status == "fix_or_manual_fallback":
        return [
            "Откройте готовность канала.",
            "Исправьте ключи/права или переведите в ручной режим.",
            "Повторите live API-проверку без публикации.",
        ] if is_ru else [
            "Open channel readiness.",
            "Fix keys/permissions or move to manual fallback.",
            "Rerun live API preflight without publishing.",
        ]
    if status == "prepare_first_post":
        return [
            f"Выберите ближайшую тему и канал {label}.",
            "Создайте черновик и проверьте предпросмотр.",
            "Дальше: подтверждение → расписание → проверка результата после даты публикации.",
        ] if is_ru else [
            f"Choose the nearest topic and {label} channel.",
            "Create a draft and review preview.",
            "Then: approval → queue → due worker proof.",
        ]
    if status == "connect_first_api_channel":
        return [
            "Подключите Telegram или VK.",
            "Запустите live API-проверку без публикации.",
            "Когда канал готов, подготовьте один пост из плана.",
        ] if is_ru else [
            "Connect Telegram or VK.",
            "Run live API preflight without publishing.",
            "When the channel is ready, prepare one post from the plan.",
        ]
    return [
        "Создайте недельный контент-план.",
        "Подготовьте каналы для первой темы.",
        "Начните с Telegram/VK для первого API-proof.",
    ] if is_ru else [
        "Create a weekly content plan.",
        "Prepare channels for the first topic.",
        "Start with Telegram/VK for the first API proof.",
    ]


def _social_goal_progress(posts: list[dict[str, Any]], plan_item_count: int = 0) -> dict[str, Any]:
    summary = _summary_for_posts(posts)
    by_status = summary.get("by_status") if isinstance(summary.get("by_status"), dict) else {}
    total_posts = int(summary.get("total") or 0)
    needs_review = int(summary.get("needs_review") or 0)
    approved = int(by_status.get("approved", 0) or 0)
    scheduled = int(summary.get("scheduled") or 0)
    supervised = int(summary.get("needs_supervised_publish") or 0)
    manual = int(summary.get("needs_manual_publish") or 0)
    published = int(summary.get("published") or 0)
    failed = int(summary.get("failed") or 0)
    learning = _social_learning_readiness(posts)
    has_plan = int(plan_item_count or 0) > 0
    has_learning_signal = int(learning.get("posts_with_primary_result") or 0) > 0 or int(
        learning.get("posts_with_early_signal") or 0
    ) > 0
    learning_ready = str(learning.get("status") or "").strip() in {"ready_from_leads", "early_signals_only"}

    stages = [
        _social_goal_stage(
            "content_plan",
            "Контент-план",
            "Content plan",
            "done" if has_plan else "current",
            f"Тем в плане: {int(plan_item_count or 0)}." if has_plan else "Сначала создайте или откройте контент-план.",
            f"Plan topics: {int(plan_item_count or 0)}." if has_plan else "Create or open a content plan first.",
            int(plan_item_count or 0),
        ),
        _social_goal_stage(
            "channel_posts",
            "Посты по каналам",
            "Channel posts",
            "done" if total_posts > 0 else ("current" if has_plan else "pending"),
            f"Подготовлено публикаций: {total_posts}." if total_posts > 0 else "Подготовьте каналы из тем плана.",
            f"Prepared posts: {total_posts}." if total_posts > 0 else "Prepare channel posts from plan topics.",
            total_posts,
        ),
        _social_goal_stage(
            "review_approval",
            "Проверка и approval",
            "Review and approval",
            "pending" if total_posts == 0 else ("current" if needs_review > 0 else "done"),
            (
                f"Нужно проверить перед исполнением: {needs_review}."
                if needs_review > 0
                else "Тексты готовы к расписанию: approval отделён от публикации."
            ),
            (
                f"Needs review before execution: {needs_review}."
                if needs_review > 0
                else "Copy is ready for queueing: approval is separate from publishing."
            ),
            needs_review,
        ),
        _social_goal_stage(
            "schedule",
            "Расписание",
            "Schedule",
            "current" if approved > 0 else ("done" if scheduled > 0 or published > 0 or supervised > 0 or manual > 0 else "pending"),
            (
                f"Утверждено, но ещё не в очереди: {approved}."
                if approved > 0
                else (
                    f"В расписании: {scheduled}."
                    if scheduled > 0
                    else "После approval поставьте публикации в расписание."
                )
            ),
            (
                f"Approved but not queued: {approved}."
                if approved > 0
                else (
                    f"Queued: {scheduled}."
                    if scheduled > 0
                    else "After approval, queue posts on schedule."
                )
            ),
            approved or scheduled,
        ),
        _social_goal_stage(
            "execution",
            "Исполнение",
            "Execution",
            (
                "attention"
                if failed > 0
                else (
                    "current"
                    if scheduled > 0 or supervised > 0 or manual > 0
                    else ("done" if published > 0 else "pending")
                )
            ),
            _social_goal_execution_detail(failed, scheduled, supervised, manual, published, True),
            _social_goal_execution_detail(failed, scheduled, supervised, manual, published, False),
            failed or scheduled or supervised or manual or published,
        ),
        _social_goal_stage(
            "learning",
            "Результаты и следующий план",
            "Results and next plan",
            "done" if learning_ready else ("current" if published > 0 or has_learning_signal else "pending"),
            str(learning.get("next_action_ru") or "").strip(),
            str(learning.get("next_action_en") or "").strip(),
            int(learning.get("primary_signal_total") or 0) + int(learning.get("secondary_signal_total") or 0),
        ),
    ]
    done = sum(1 for stage in stages if stage.get("status") == "done")
    attention = sum(1 for stage in stages if stage.get("status") == "attention")
    current = next((stage for stage in stages if stage.get("status") == "attention"), None)
    if not current:
        current = next((stage for stage in stages if stage.get("status") == "current"), None)
    if not current:
        current = next((stage for stage in stages if stage.get("status") == "pending"), stages[-1])
    return {
        "schema": "localos_social_goal_progress_v1",
        "goal_ru": "Контент-план → посты → подтверждение → расписание → исполнение → реакции → корректировка следующего плана.",
        "goal_en": "Content plan → posts → approval → schedule → execution → reactions → next-plan correction.",
        "stages": stages,
        "summary": {
            "done": done,
            "total": len(stages),
            "attention": attention,
            "current_key": str(current.get("key") or "").strip(),
            "current_label_ru": str(current.get("label_ru") or "").strip(),
            "current_label_en": str(current.get("label_en") or "").strip(),
        },
        "next_action_ru": str(current.get("detail_ru") or "").strip(),
        "next_action_en": str(current.get("detail_en") or "").strip(),
        "primary_metric_ru": "Заявки и обращения",
        "primary_metric_en": "Leads and inquiries",
        "approval_required": True,
        "maps_are_supervised_or_manual": True,
    }


def _social_goal_stage(
    key: str,
    label_ru: str,
    label_en: str,
    status: str,
    detail_ru: str,
    detail_en: str,
    count: int = 0,
) -> dict[str, Any]:
    return {
        "key": key,
        "label_ru": label_ru,
        "label_en": label_en,
        "status": status,
        "detail_ru": detail_ru,
        "detail_en": detail_en,
        "count": int(count or 0),
    }


def _social_goal_execution_detail(
    failed: int,
    scheduled: int,
    supervised: int,
    manual: int,
    published: int,
    is_ru: bool,
) -> str:
    if int(failed or 0) > 0:
        return (
            f"Есть ошибки публикации: {int(failed or 0)}. Исправьте канал, повторите или переведите в ручной режим."
            if is_ru
            else f"Publish failures: {int(failed or 0)}. Fix the channel, retry, or move to manual mode."
        )
    if int(supervised or 0) > 0:
        return (
            f"Контролируемое размещение Яндекс/2ГИС: {int(supervised or 0)}."
            if is_ru
            else f"Supervised Yandex/2GIS placement: {int(supervised or 0)}."
        )
    if int(manual or 0) > 0:
        return (
            f"Нужен ручной режим или подключение: {int(manual or 0)}."
            if is_ru
            else f"Manual fallback or connection needed: {int(manual or 0)}."
        )
    if int(scheduled or 0) > 0:
        return (
            f"Ждёт даты публикации или ограниченного цикла исполнителя: {int(scheduled or 0)}."
            if is_ru
            else f"Waiting for the due date or scoped worker cycle: {int(scheduled or 0)}."
        )
    if int(published or 0) > 0:
        return (
            f"Опубликовано: {int(published or 0)}. Соберите реакции и заявки."
            if is_ru
            else f"Published: {int(published or 0)}. Collect reactions and leads."
        )
    return (
        "API публикуются только после подтверждения и расписания; карты остаются контролируемыми или ручными."
        if is_ru
        else "API publishes only after approval and queueing; maps stay supervised/manual."
    )


def _queue_preflight_block(cursor: Any, post: dict[str, Any]) -> dict[str, Any]:
    platform = str(post.get("platform") or "").strip()
    if platform not in API_PLATFORMS:
        return {}
    business_id = str(post.get("business_id") or "").strip()
    readiness_items = _build_channel_readiness(cursor, business_id)
    channel = next(
        (item for item in readiness_items if str(item.get("platform") or "").strip() == platform),
        {},
    )
    if bool(channel.get("ready")):
        return {}
    status = str(channel.get("status") or "missing_connection").strip()
    return {
        "status": "needs_manual_publish",
        "last_error": _queue_preflight_error(platform, status),
        "metadata_json": {
            "queue_preflight_status": status,
            "provider_status": status,
            "queue_preflight_ready": False,
            "queue_preflight_message_ru": _channel_readiness_message(platform, status, True),
            "queue_preflight_message_en": _channel_readiness_message(platform, status, False),
        },
    }


def _queue_preflight_error(platform: str, status: str) -> str:
    label = platform_label(platform)
    normalized = str(status or "").strip()
    if normalized == "adapter_pending":
        return f"{label}: API-публикация ещё не включена; используйте ручное размещение."
    if normalized == "missing_permissions":
        return f"{label}: не хватает прав/permissions для публикации."
    if normalized == "missing_binding":
        return f"{label}: не выбрана группа, страница или бизнес-аккаунт для публикации."
    if normalized == "missing_connection":
        return f"{label}: аккаунт не подключен."
    return f"{label}: нужны ключи или настройки канала перед постановкой в расписание."


def _build_channel_readiness(cursor: Any, business_id: str) -> list[dict[str, Any]]:
    business = _load_business_publish_context(cursor, business_id)
    telegram_transport = _resolve_telegram_publish_transport(business)
    telegram_token_present = bool(telegram_transport.get("token_present"))
    telegram_chat_present = bool(str(business.get("telegram_chat_id") or "").strip())
    owner_telegram_present = bool(str(business.get("owner_telegram_id") or "").strip())
    telegram_app_account = _find_active_external_account(cursor, business_id, ("telegram_app",))
    telegram_app_present = bool(telegram_app_account)
    telegram_ready = telegram_token_present and telegram_chat_present
    vk_account = _find_active_external_account(cursor, business_id, ("vk", "vk_group", "vk_business"))
    vk_auth = _external_account_auth_data(vk_account)
    vk_binding = _vk_publish_binding(vk_account, vk_auth)
    google_account = _find_active_external_account(cursor, business_id, ("google_business",))
    meta_account = _find_active_external_account(cursor, business_id, ("meta", "facebook", "instagram"))
    meta_auth = _external_account_auth_data(meta_account)
    instagram_readiness = _meta_channel_readiness(meta_account, meta_auth, "instagram")
    facebook_readiness = _meta_channel_readiness(meta_account, meta_auth, "facebook")
    browser_ready = openclaw_browser_available()
    yandex_target = _map_publish_target(cursor, business_id, "yandex_maps")
    two_gis_target = _map_publish_target(cursor, business_id, "two_gis")
    return [
        _channel_readiness(
            "telegram",
            "api",
            telegram_ready,
            "ready" if telegram_ready else "missing_keys",
            _telegram_connection_checks(
                telegram_token_present,
                telegram_chat_present,
                str(telegram_transport.get("token_source") or ""),
            ),
            {
                "owner_telegram_present": owner_telegram_present,
                "telegram_app_present": telegram_app_present,
                "telegram_transport": str(telegram_transport.get("token_source") or ""),
            },
        ),
        _channel_readiness(
            "vk",
            "api",
            bool(vk_binding.get("ready")),
            str(vk_binding.get("status") or "missing_keys"),
            _vk_connection_checks(vk_account, vk_auth, vk_binding),
        ),
        _channel_readiness(
            "google_business",
            "api",
            bool(google_account),
            "ready" if google_account else "missing_connection",
            _google_business_connection_checks(google_account),
        ),
        _channel_readiness(
            "instagram",
            "api",
            bool(instagram_readiness.get("ready")),
            str(instagram_readiness.get("status") or "missing_connection"),
            _meta_connection_checks(meta_account, meta_auth, "instagram", str(instagram_readiness.get("status") or "")),
        ),
        _channel_readiness(
            "facebook",
            "api",
            bool(facebook_readiness.get("ready")),
            str(facebook_readiness.get("status") or "missing_connection"),
            _meta_connection_checks(meta_account, meta_auth, "facebook", str(facebook_readiness.get("status") or "")),
        ),
        _channel_readiness(
            "yandex_maps",
            "openclaw_browser" if browser_ready else "manual",
            browser_ready,
            "supervised_ready" if browser_ready else "manual_fallback",
            _maps_connection_checks(browser_ready, yandex_target),
        ),
        _channel_readiness(
            "two_gis",
            "openclaw_browser" if browser_ready else "manual",
            browser_ready,
            "supervised_ready" if browser_ready else "manual_fallback",
            _maps_connection_checks(browser_ready, two_gis_target),
        ),
    ]


def _channel_readiness(
    platform: str,
    publish_mode: str,
    ready: bool,
    status: str,
    connection_checks: list[dict[str, Any]] | None = None,
    target_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    target_setup = _channel_readiness_target_setup(platform, status, ready, target_context)
    missing_fields = _channel_readiness_missing_fields(platform, status)
    if (
        str(platform or "").strip() == "telegram"
        and not ready
        and isinstance(target_setup.get("required_fields"), list)
        and target_setup.get("required_fields")
    ):
        missing_fields = [str(field) for field in target_setup.get("required_fields") or []]
    message_ru = _channel_readiness_message(platform, status, True)
    message_en = _channel_readiness_message(platform, status, False)
    next_action_ru = _channel_readiness_next_action(platform, status, True)
    next_action_en = _channel_readiness_next_action(platform, status, False)
    setup_summary_ru = _channel_readiness_setup_summary(platform, status, True)
    setup_summary_en = _channel_readiness_setup_summary(platform, status, False)
    setup_steps_ru = _channel_readiness_setup_steps(platform, status, True)
    setup_steps_en = _channel_readiness_setup_steps(platform, status, False)
    if (
        str(platform or "").strip() == "telegram"
        and str(status or "").strip() == "missing_keys"
        and str(target_setup.get("telegram_transport") or "") == "global_owner_bot"
    ):
        message_ru = "Telegram: глобальный бот LocalOS доступен; осталось указать chat_id канала или чата для поста."
        message_en = "Telegram: the global LocalOS bot is available; set the channel or chat chat_id for the post."
        next_action_ru = "Укажите telegram_chat_id цели публикации, затем запустите проверку Telegram без отправки сообщения."
        next_action_en = "Set the publish-target telegram_chat_id, then run the Telegram check without sending a message."
        setup_summary_ru = "Для Telegram осталось указать chat_id канала/группы, куда должен выйти пост."
        setup_summary_en = "For Telegram, only the channel/group chat_id remains before the first proof."
        setup_steps_ru = [str(item) for item in target_setup.get("steps_ru") or setup_steps_ru]
        setup_steps_en = [str(item) for item in target_setup.get("steps_en") or setup_steps_en]
    return {
        "platform": platform,
        "platform_label": platform_label(platform),
        "publish_mode": publish_mode,
        "ready": bool(ready),
        "status": status,
        "message_ru": message_ru,
        "message_en": message_en,
        "next_action_ru": next_action_ru,
        "next_action_en": next_action_en,
        "setup_summary_ru": setup_summary_ru,
        "setup_summary_en": setup_summary_en,
        "setup_steps_ru": setup_steps_ru,
        "setup_steps_en": setup_steps_en,
        "missing_fields": missing_fields,
        "settings_path": _channel_readiness_settings_path(platform),
        "connection_checks": connection_checks or [],
        "target_setup": target_setup,
    }


def _channel_readiness_target_setup(
    platform: str,
    status: str,
    ready: bool,
    target_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    platform_key = str(platform or "").strip()
    status_key = str(status or "").strip()
    if platform_key != "telegram":
        return {}
    context = target_context or {}
    owner_telegram_present = bool(context.get("owner_telegram_present"))
    telegram_app_present = bool(context.get("telegram_app_present"))
    telegram_transport = str(context.get("telegram_transport") or "").strip()
    not_a_target_ru = (
        "Владелец уже привязан в Telegram для управления LocalOS и уведомлений, но это не цель публикации поста."
        if owner_telegram_present and not telegram_app_present
        else (
            "Telegram app/miniapp подключён как supervised transport для управления и сообщений, но пост из контент-плана всё равно публикуется в выбранный chat_id."
            if telegram_app_present
            else "Owner-bot и миниапп нужны для управления LocalOS и уведомлений; они не являются целью публикации поста."
        )
    )
    not_a_target_en = (
        "The owner is already linked in Telegram for LocalOS control and notifications, but that is not the post publish target."
        if owner_telegram_present and not telegram_app_present
        else (
            "Telegram app/mini app is connected as a supervised transport for control and messages, but content-plan posts still publish to the selected chat_id."
            if telegram_app_present
            else "The owner bot and mini app manage LocalOS and notifications; they are not the post publish target."
        )
    )
    return {
        "schema": "localos_social_channel_target_setup_v1",
        "platform": "telegram",
        "status": status_key,
        "ready": bool(ready),
        "owner_telegram_present": owner_telegram_present,
        "telegram_app_present": telegram_app_present,
        "supervised_transport_present": telegram_app_present,
        "telegram_transport": telegram_transport,
        "target_kind": "publish_target_chat",
        "target_label_ru": "Канал или группа для поста",
        "target_label_en": "Post target channel or group",
        "required_fields": ["telegram_chat_id"] if telegram_transport == "global_owner_bot" else ["telegram_bot_token", "telegram_chat_id"],
        "not_a_target_ru": not_a_target_ru,
        "not_a_target_en": not_a_target_en,
        "summary_ru": (
            "Telegram готов: перед первым постом запустите live API-проверку без публикации."
            if ready
            else "До первого Telegram-поста укажите bot token и chat_id канала или группы, куда должен выйти пост."
        ),
        "summary_en": (
            "Telegram is ready: run the live API check without publishing before the first post."
            if ready
            else "Before the first Telegram post, set the bot token and the channel or group chat_id where the post should appear."
        ),
        "steps_ru": (
            [
                "Запустите live API-проверку без публикации.",
                "Проверьте preview поста.",
                "Утвердите и поставьте пост в расписание.",
            ]
            if ready
            else [
                "Добавьте бота в канал или группу, где должен выйти пост.",
                "Дайте боту право отправлять сообщения или публиковать в канал.",
                (
                    "Укажите telegram_chat_id в настройках бизнеса; глобальный бот LocalOS уже может быть transport."
                    if telegram_transport == "global_owner_bot"
                    else "Укажите telegram_bot_token и telegram_chat_id в настройках бизнеса."
                ),
                "Запустите live API-проверку без отправки поста.",
            ]
        ),
        "steps_en": (
            [
                "Run the live API check without publishing.",
                "Review the post preview.",
                "Approve and queue the post.",
            ]
            if ready
            else [
                "Add the bot to the channel or group where the post should appear.",
                "Give the bot permission to send messages or publish to the channel.",
                (
                    "Set telegram_chat_id in business settings; the global LocalOS bot can already be the transport."
                    if telegram_transport == "global_owner_bot"
                    else "Set telegram_bot_token and telegram_chat_id in business settings."
                ),
                "Run the live API check without sending a post.",
            ]
        ),
        "proof_ru": "Первый настоящий proof: published social_post с provider_post_id/provider_post_url.",
        "proof_en": "First real proof: a published social_post with provider_post_id/provider_post_url.",
    }


def _connection_check(
    key: str,
    ok: bool,
    label_ru: str,
    label_en: str,
    detail_ru: str = "",
    detail_en: str = "",
    state: str = "",
) -> dict[str, Any]:
    resolved_state = str(state or ("ok" if ok else "missing")).strip()
    return {
        "key": str(key or "").strip(),
        "ok": bool(ok),
        "state": resolved_state,
        "label_ru": str(label_ru or "").strip(),
        "label_en": str(label_en or "").strip(),
        "detail_ru": str(detail_ru or "").strip(),
        "detail_en": str(detail_en or "").strip(),
    }


def _telegram_connection_checks(token_present: bool, chat_present: bool, token_source: str = "") -> list[dict[str, Any]]:
    source = str(token_source or "").strip()
    token_detail_ru = "токен найден" if token_present else "добавьте telegram_bot_token"
    token_detail_en = "token found" if token_present else "add telegram_bot_token"
    if token_present and source == "global_owner_bot":
        token_detail_ru = "доступен глобальный бот LocalOS"
        token_detail_en = "global LocalOS bot is available"
    elif token_present and source == "business_bot":
        token_detail_ru = "токен бота бизнеса найден"
        token_detail_en = "business bot token found"
    return [
        _connection_check(
            "telegram_bot_token",
            token_present,
            "Токен бота",
            "Bot token",
            token_detail_ru,
            token_detail_en,
            source or ("ok" if token_present else "missing"),
        ),
        _connection_check(
            "telegram_chat_id",
            chat_present,
            "Канал или чат",
            "Channel or chat",
            "chat_id найден" if chat_present else "укажите telegram_chat_id",
            "chat_id found" if chat_present else "set telegram_chat_id",
        ),
        _connection_check(
            "telegram_publish_probe",
            token_present and chat_present,
            "Права на публикацию",
            "Publishing permission",
            "проверьте live API-проверкой без публикации" if token_present and chat_present else "проверка невозможна без токена и chat_id",
            "run the live API check without publishing" if token_present and chat_present else "cannot check without token and chat_id",
            "needs_live_probe" if token_present and chat_present else "blocked",
        ),
    ]


def _vk_connection_checks(
    account: dict[str, Any],
    auth_data: dict[str, Any],
    binding: dict[str, Any],
) -> list[dict[str, Any]]:
    has_account = bool(account)
    has_token = bool(str(binding.get("token") or auth_data.get("access_token") or auth_data.get("token") or "").strip())
    has_owner = bool(str(binding.get("owner_id") or auth_data.get("owner_id") or account.get("external_id") or "").strip())
    explicit_scope = _auth_scope_is_explicit(auth_data)
    has_wall_permission = (not explicit_scope and has_token) or _auth_scope_allows(auth_data, {"wall", "wall.post"})
    return [
        _connection_check(
            "vk_account",
            has_account,
            "VK подключение",
            "VK connection",
            "аккаунт найден" if has_account else "подключите VK account/token",
            "account found" if has_account else "connect VK account/token",
        ),
        _connection_check(
            "vk_access_token",
            has_token,
            "Access token",
            "Access token",
            "токен найден" if has_token else "добавьте access_token",
            "token found" if has_token else "add access_token",
        ),
        _connection_check(
            "vk_owner_id",
            has_owner,
            "Группа/owner_id",
            "Group/owner_id",
            "цель публикации выбрана" if has_owner else "укажите group_id или owner_id",
            "posting target selected" if has_owner else "set group_id or owner_id",
        ),
        _connection_check(
            "vk_wall_permission",
            has_wall_permission,
            "Право wall.post",
            "wall.post permission",
            "scope разрешает wall.post" if has_wall_permission and explicit_scope else (
                "scope не указан, проверится при publish" if has_wall_permission else "обновите token с правом wall.post"
            ),
            "scope allows wall.post" if has_wall_permission and explicit_scope else (
                "scope is absent, checked on publish" if has_wall_permission else "refresh token with wall.post"
            ),
            "ok" if has_wall_permission and explicit_scope else ("deferred" if has_wall_permission else "missing"),
        ),
    ]


def _google_business_connection_checks(account: dict[str, Any]) -> list[dict[str, Any]]:
    has_account = bool(account)
    has_location = bool(str(account.get("external_id") or "").strip())
    return [
        _connection_check(
            "google_business_account",
            has_account,
            "Google Business Profile",
            "Google Business Profile",
            "аккаунт подключен" if has_account else "подключите Google Business Profile",
            "account connected" if has_account else "connect Google Business Profile",
        ),
        _connection_check(
            "google_business_location",
            has_location,
            "Location",
            "Location",
            "location выбрана" if has_location else "выберите location для публикации",
            "location selected" if has_location else "select a location for publishing",
        ),
    ]


def _meta_connection_checks(
    account: dict[str, Any],
    auth_data: dict[str, Any],
    platform: str,
    status: str,
) -> list[dict[str, Any]]:
    platform_key = str(platform or "").strip()
    has_account = bool(account)
    has_token = bool(str(auth_data.get("access_token") or auth_data.get("token") or "").strip())
    has_binding = bool(str(auth_data.get("page_id") or account.get("external_id") or "").strip())
    permission_key = "pages_manage_posts"
    if platform_key == "instagram":
        has_binding = bool(str(auth_data.get("ig_user_id") or auth_data.get("instagram_business_account_id") or "").strip())
        permission_key = "instagram_content_publish"
    has_permission = (not _auth_scope_is_explicit(auth_data) and has_token) or _auth_scope_allows(auth_data, {permission_key})
    adapter_enabled = str(status or "").strip() != "adapter_pending"
    return [
        _connection_check(
            "meta_account",
            has_account,
            "Meta подключение",
            "Meta connection",
            "аккаунт найден" if has_account else "подключите Meta account",
            "account found" if has_account else "connect Meta account",
        ),
        _connection_check(
            "meta_token",
            has_token,
            "Access token",
            "Access token",
            "токен найден" if has_token else "добавьте access_token",
            "token found" if has_token else "add access_token",
        ),
        _connection_check(
            "meta_binding",
            has_binding,
            "Page/IG binding",
            "Page/IG binding",
            "asset выбран" if has_binding else "выберите Page или IG business account",
            "asset selected" if has_binding else "choose Page or IG business account",
        ),
        _connection_check(
            "meta_permission",
            has_permission,
            "Permission",
            "Permission",
            f"permission {permission_key} доступен" if has_permission else f"нужен permission {permission_key}",
            f"permission {permission_key} available" if has_permission else f"permission {permission_key} required",
            "ok" if has_permission and _auth_scope_is_explicit(auth_data) else ("deferred" if has_permission else "missing"),
        ),
        _connection_check(
            "meta_native_publish",
            adapter_enabled,
            "API publish",
            "API publish",
            "native adapter включен" if adapter_enabled else "пока manual handoff до проверки Meta publish",
            "native adapter enabled" if adapter_enabled else "manual handoff until Meta publish is verified",
            "ok" if adapter_enabled else "blocked",
        ),
    ]


def _maps_connection_checks(browser_ready: bool, target: dict[str, Any]) -> list[dict[str, Any]]:
    target_url = str(target.get("target_url") or "").strip()
    return [
        _connection_check(
            "openclaw_browser_use",
            browser_ready,
            "OpenClaw browser-use",
            "OpenClaw browser-use",
            "capability подтверждена" if browser_ready else "capability не подтверждена, будет ручной режим",
            "capability confirmed" if browser_ready else "capability is not confirmed; manual fallback will be used",
            "ok" if browser_ready else "manual",
        ),
        _connection_check(
            "map_profile_url",
            bool(target_url),
            "Ссылка на профиль",
            "Profile URL",
            "ссылка найдена" if target_url else "добавьте ссылку на карточку, чтобы открыть площадку быстрее",
            "URL found" if target_url else "add the listing URL to open the platform faster",
            "ok" if target_url else "recommended",
        ),
        _connection_check(
            "final_publish_policy",
            True,
            "Финальный клик",
            "Final click",
            "всегда остаётся за человеком",
            "always remains human-owned",
            "human_approval",
        ),
    ]


def _channel_readiness_message(platform: str, status: str, is_ru: bool) -> str:
    label = platform_label(platform)
    platform_key = str(platform or "").strip()
    if status == "ready":
        if platform_key in {"telegram", "vk"}:
            return (
                f"{label}: ключи заполнены; перед первым API-постом запустите live API-проверку без публикации."
                if is_ru
                else f"{label}: keys are set; run the live API check before the first API post."
            )
        return f"{label}: готов к публикации после подтверждения." if is_ru else f"{label}: ready to publish after approval."
    if status == "supervised_ready":
        return (
            f"{label}: доступно контролируемое размещение через OpenClaw."
            if is_ru
            else f"{label}: supervised placement through OpenClaw is available."
        )
    if status == "manual_fallback":
        return (
            f"{label}: OpenClaw browser-use не подтверждён, будет ручной режим."
            if is_ru
            else f"{label}: OpenClaw browser-use is not confirmed; manual fallback will be used."
        )
    if status == "missing_permissions":
        return (
            f"{label}: подключение найдено, но нужны permissions/account binding."
            if is_ru
            else f"{label}: connection exists, but permissions/account binding are required."
        )
    if status == "missing_binding":
        return (
            f"{label}: ключ найден, но не выбрана группа, страница или бизнес-аккаунт."
            if is_ru
            else f"{label}: key exists, but group, page, or business account binding is missing."
        )
    if status == "missing_connection":
        return f"{label}: нужно подключить аккаунт." if is_ru else f"{label}: connect an account first."
    if status == "adapter_pending":
        return (
            f"{label}: подключение выглядит готовым, но API-публикация ещё не включена; будет ручное размещение."
            if is_ru
            else f"{label}: connection looks ready, but API publishing is not enabled yet; manual placement will be used."
        )
    if platform_key == "telegram" and status == "missing_keys":
        return (
            "Telegram: укажите bot token и chat_id цели публикации. Owner-bot/миниапп подходят для управления LocalOS, но не заменяют канал или чат для поста."
            if is_ru
            else "Telegram: set the bot token and publish-target chat_id. The owner bot/mini app can manage LocalOS, but does not replace the channel or chat for the post."
        )
    return f"{label}: нужны ключи или настройки канала." if is_ru else f"{label}: keys or channel settings are required."


def _channel_readiness_next_action(platform: str, status: str, is_ru: bool) -> str:
    platform_key = str(platform or "").strip()
    status_key = str(status or "").strip()
    if status_key == "ready":
        if platform_key in {"telegram", "vk"}:
            return (
                "Перед расписанием нажмите «Проверить API-каналы», затем проверьте preview и утвердите текст."
                if is_ru
                else "Before queueing, click Check API channels, then review the preview and approve the copy."
            )
        return (
            "После проверки текста поставьте пост в расписание."
            if is_ru
            else "After reviewing copy, queue the post on schedule."
        )
    if status_key == "supervised_ready":
        return (
            "Поставьте пост в расписание: LocalOS создаст контролируемое размещение, финальная кнопка останется за человеком."
            if is_ru
            else "Queue the post: LocalOS will create supervised placement and the final click remains human-owned."
        )
    if status_key == "manual_fallback":
        return (
            "Используйте copy-ready текст и отметьте публикацию размещённой после ручного действия."
            if is_ru
            else "Use the copy-ready text and mark the post as published after the manual step."
        )
    if platform_key == "telegram" and status_key == "missing_keys":
        return (
            "Добавьте telegram_bot_token и telegram_chat_id канала/группы, куда должен выйти пост."
            if is_ru
            else "Add telegram_bot_token and the channel/group telegram_chat_id where the post should appear."
        )
    if platform_key == "vk":
        if status_key == "missing_permissions":
            return (
                "Обновите VK token с правом wall.post и проверьте group_id/owner_id."
                if is_ru
                else "Refresh the VK token with wall.post permission and verify group_id/owner_id."
            )
        if status_key == "missing_binding":
            return (
                "Укажите VK group_id или owner_id для публикации от имени сообщества."
                if is_ru
                else "Set VK group_id or owner_id for posting as the community."
            )
        return (
            "Подключите VK account/token и группу с правом публикации на стене."
            if is_ru
            else "Connect a VK account/token and a group with wall posting permission."
        )
    if platform_key == "google_business":
        return (
            "Подключите Google Business Profile и выберите локацию для публикации."
            if is_ru
            else "Connect Google Business Profile and select the location for publishing."
        )
    if platform_key in {"instagram", "facebook"}:
        if status_key == "adapter_pending":
            return (
                "Пока используйте ручной режим; включайте API только после проверки прав Meta."
                if is_ru
                else "Use manual handoff for now; enable API only after Meta permissions are verified."
            )
        if status_key == "missing_permissions":
            return (
                "Проверьте права Meta Graph и привязку Page/IG business account."
                if is_ru
                else "Check Meta Graph permissions and Page/IG business account binding."
            )
        if status_key == "missing_binding":
            return (
                "Выберите Facebook Page или Instagram business account для публикации."
                if is_ru
                else "Choose the Facebook Page or Instagram business account for publishing."
            )
        return (
            "Подключите Meta account и нужные Page/IG assets."
            if is_ru
            else "Connect a Meta account and the required Page/IG assets."
        )
    if status_key == "missing_permissions":
        return "Обновите права подключения." if is_ru else "Update connection permissions."
    if status_key == "missing_binding":
        return "Выберите аккаунт или страницу для публикации." if is_ru else "Choose the account or page for publishing."
    if status_key == "missing_connection":
        return "Подключите аккаунт канала." if is_ru else "Connect the channel account."
    return "Проверьте ключи и настройки канала." if is_ru else "Check channel keys and settings."


def _channel_readiness_setup_summary(platform: str, status: str, is_ru: bool) -> str:
    platform_key = str(platform or "").strip()
    status_key = str(status or "").strip()
    if status_key == "ready":
        if platform_key in {"telegram", "vk"}:
            return (
                "Ключи заполнены: перед первым реальным API-постом выполните live API-проверку без публикации, затем подтверждение и расписание."
                if is_ru
                else "Keys are set: before the first real API post, run the live API check without publishing, then approve and queue."
            )
        return (
            "Канал готов: проверьте preview, утвердите текст и ставьте пост в расписание."
            if is_ru
            else "Channel is ready: review the preview, approve the copy, and queue the post."
        )
    if status_key == "supervised_ready":
        return (
            "Контролируемый режим готов: LocalOS создаст задачу, а финальный клик останется за человеком."
            if is_ru
            else "Supervised mode is ready: LocalOS will create a placement task and the final click remains human-owned."
        )
    if status_key == "manual_fallback":
        return (
            "Автопубликации нет: используйте готовый текст, разместите вручную и отметьте результат."
            if is_ru
            else "No autopublish: use the prepared copy, publish manually, and record the result."
        )
    if platform_key == "telegram":
        return (
            "Чтобы включить Telegram, добавьте bot token, chat_id и право бота писать в канал."
            if is_ru
            else "To enable Telegram, add the bot token, chat_id, and bot posting permission."
        )
    if platform_key == "vk":
        if status_key == "missing_permissions":
            return (
                "VK почти готов: обновите token с правом wall.post и проверьте группу."
                if is_ru
                else "VK is almost ready: refresh the token with wall.post and verify the group."
            )
        if status_key == "missing_binding":
            return (
                "Для VK выберите group_id или owner_id, откуда LocalOS будет публиковать."
                if is_ru
                else "For VK, choose the group_id or owner_id LocalOS will post from."
            )
        return (
            "Чтобы включить VK, подключите token, группу и право wall.post."
            if is_ru
            else "To enable VK, connect the token, group, and wall.post permission."
        )
    if platform_key == "google_business":
        return (
                "Чтобы включить Google, подключите Business Profile и выберите локацию."
            if is_ru
            else "To enable Google, connect Business Profile and select the location."
        )
    if platform_key in {"instagram", "facebook"}:
        if status_key == "adapter_pending":
            return (
                "Meta пока в ручном режиме: API включается только после проверки прав Page/IG."
                if is_ru
                else "Meta stays manual for now: API is enabled only after Page/IG permissions are verified."
            )
        if status_key == "missing_permissions":
            return (
                "Meta почти готов: проверьте права для публикации и привязку Page/IG."
                if is_ru
                else "Meta is almost ready: verify publishing permissions and Page/IG binding."
            )
        if status_key == "missing_binding":
            return (
                "Для Meta выберите Facebook Page или Instagram business account."
                if is_ru
                else "For Meta, choose the Facebook Page or Instagram business account."
            )
        return (
            "Чтобы включить Meta, подключите аккаунт, Page/IG asset и права публикации."
            if is_ru
            else "To enable Meta, connect the account, Page/IG asset, and publish permissions."
        )
    if status_key == "missing_permissions":
        return "Обновите права подключения перед расписанием." if is_ru else "Update connection permissions before queueing."
    if status_key == "missing_binding":
        return "Выберите аккаунт или страницу перед расписанием." if is_ru else "Choose the account or page before queueing."
    if status_key == "missing_connection":
        return "Подключите аккаунт канала перед расписанием." if is_ru else "Connect the channel account before queueing."
    return "Проверьте настройки канала перед расписанием." if is_ru else "Check channel settings before queueing."


def _channel_readiness_setup_steps(platform: str, status: str, is_ru: bool) -> list[str]:
    platform_key = str(platform or "").strip()
    status_key = str(status or "").strip()
    if status_key == "ready":
        if platform_key in {"telegram", "vk"}:
            return [
                "Запустите live API-проверку без публикации.",
                "Проверьте preview поста.",
                "Утвердите текст и поставьте в расписание.",
            ] if is_ru else [
                "Run the live API check without publishing.",
                "Review the post preview.",
                "Approve the copy and queue it on schedule.",
            ]
        return [
            "Проверьте preview поста.",
            "Утвердите текст.",
            "Поставьте в расписание.",
        ] if is_ru else [
            "Review the post preview.",
            "Approve the copy.",
            "Queue it on schedule.",
        ]
    if status_key == "supervised_ready":
        return [
            "Проверьте текст и медиа.",
            "Поставьте пост в расписание.",
            "Откройте контролируемое размещение и подтвердите финальный шаг вручную.",
        ] if is_ru else [
            "Review copy and media.",
            "Queue the post on schedule.",
            "Open supervised placement and confirm the final step manually.",
        ]
    if status_key == "manual_fallback":
        return [
            "Скопируйте подготовленный текст.",
            "Разместите пост на площадке вручную.",
            "Отметьте публикацию размещённой в LocalOS.",
        ] if is_ru else [
            "Copy the prepared text.",
            "Publish it on the platform manually.",
            "Mark the post as published in LocalOS.",
        ]
    if platform_key == "telegram":
        return [
            "Добавьте токен Telegram-бота бизнеса.",
            "Укажите chat_id канала или чата.",
            "Проверьте, что бот имеет право писать в этот канал.",
        ] if is_ru else [
            "Add the business Telegram bot token.",
            "Set the channel or chat chat_id.",
            "Check that the bot can post to that channel.",
        ]
    if platform_key == "vk":
        if status_key == "missing_permissions":
            return [
                "Обновите VK access_token.",
                "Добавьте permission wall.post.",
                "Проверьте group_id или owner_id сообщества.",
            ] if is_ru else [
                "Refresh the VK access_token.",
                "Add the wall.post permission.",
                "Verify the group_id or owner_id.",
            ]
        return [
            "Подключите VK account/token.",
            "Укажите group_id или owner_id.",
            "Проверьте право wall.post.",
        ] if is_ru else [
            "Connect the VK account/token.",
            "Set group_id or owner_id.",
            "Verify wall.post permission.",
        ]
    if platform_key == "google_business":
        return [
            "Подключите Google Business Profile.",
            "Выберите локацию бизнеса.",
            "Проверьте, что Google publish доступен для аккаунта.",
        ] if is_ru else [
            "Connect Google Business Profile.",
            "Select the business location.",
            "Check that Google publishing is available for the account.",
        ]
    if platform_key in {"instagram", "facebook"}:
        if status_key == "adapter_pending":
            return [
                "Оставьте канал в ручном режиме.",
                "Проверьте Meta Page/IG business binding.",
                "Включайте API-публикацию только после подтверждения прав.",
            ] if is_ru else [
                "Keep the channel in manual handoff.",
                "Verify Meta Page/IG business binding.",
                "Enable API publish only after permissions are confirmed.",
            ]
        return [
            "Подключите Meta account.",
            "Выберите Page или Instagram business account.",
            "Проверьте права для публикации.",
        ] if is_ru else [
            "Connect the Meta account.",
            "Choose the Page or Instagram business account.",
            "Verify publishing permissions.",
        ]
    if status_key == "missing_permissions":
        return ["Обновите права подключения."] if is_ru else ["Update connection permissions."]
    if status_key == "missing_binding":
        return ["Выберите аккаунт или страницу для публикации."] if is_ru else ["Choose the account or page for publishing."]
    if status_key == "missing_connection":
        return ["Подключите аккаунт канала."] if is_ru else ["Connect the channel account."]
    return ["Проверьте ключи и настройки канала."] if is_ru else ["Check channel keys and settings."]


def _channel_readiness_missing_fields(platform: str, status: str) -> list[str]:
    platform_key = str(platform or "").strip()
    status_key = str(status or "").strip()
    if status_key in {"ready", "supervised_ready", "manual_fallback", "adapter_pending"}:
        return []
    if platform_key == "telegram":
        return ["telegram_bot_token", "telegram_chat_id"]
    if platform_key == "vk":
        if status_key == "missing_permissions":
            return ["vk_access_token.wall_post_scope"]
        if status_key == "missing_binding":
            return ["vk_group_id_or_owner_id"]
        return ["vk_access_token", "vk_group_id_or_owner_id", "wall.post"]
    if platform_key == "google_business":
        return ["google_business_account", "google_business_location"]
    if platform_key == "instagram":
        if status_key == "missing_permissions":
            return ["meta_permissions.instagram_content_publish"]
        if status_key == "missing_binding":
            return ["instagram_business_account"]
        return ["meta_account", "instagram_business_account", "instagram_content_publish"]
    if platform_key == "facebook":
        if status_key == "missing_permissions":
            return ["meta_permissions.pages_manage_posts"]
        if status_key == "missing_binding":
            return ["facebook_page"]
        return ["meta_account", "facebook_page", "pages_manage_posts"]
    if status_key == "missing_permissions":
        return ["permissions"]
    if status_key == "missing_binding":
        return ["account_binding"]
    if status_key == "missing_connection":
        return ["account_connection"]
    return ["channel_settings"]


def _channel_readiness_settings_path(platform: str) -> str:
    platform_key = str(platform or "").strip()
    if platform_key == "telegram":
        return "/dashboard/settings?focus=telegram"
    if platform_key == "vk":
        return "/dashboard/settings?focus=vk"
    if platform_key == "google_business":
        return "/dashboard/settings?focus=google_business"
    if platform_key in {"instagram", "facebook"}:
        return f"/dashboard/settings?focus={platform_key}"
    if platform_key in {"yandex_maps", "two_gis"}:
        return "/dashboard/card?tab=news&mode=plan"
    return "/dashboard/settings?focus=integrations"


def _build_plan_recommendation(posts: list[dict[str, Any]]) -> dict[str, Any]:
    leads = sum(int(post.get("leads") or 0) for post in posts)
    inquiries = sum(int(post.get("inquiries") or 0) for post in posts)
    comments = sum(int(post.get("comments") or 0) for post in posts)
    reach = sum(int(post.get("reach") or post.get("views") or 0) for post in posts)
    return {
        "primary_metric": "leads_and_inquiries",
        "leads": leads,
        "inquiries": inquiries,
        "comments": comments,
        "reach": reach,
        "text_ru": _recommendation_text(leads, inquiries, comments, reach, True),
        "text_en": _recommendation_text(leads, inquiries, comments, reach, False),
        "signal_priority": _recommendation_signal_priority(leads, inquiries, comments, reach),
    }


def _social_learning_readiness(posts: list[dict[str, Any]]) -> dict[str, Any]:
    total_posts = len(posts)
    published_posts = sum(1 for post in posts if str(post.get("status") or "").strip() == "published")
    failed_posts = sum(1 for post in posts if str(post.get("status") or "").strip() == "failed")
    manual_posts = sum(
        1
        for post in posts
        if str(post.get("status") or "").strip() in {"needs_manual_publish", "needs_supervised_publish"}
    )
    posts_with_primary_result = sum(
        1
        for post in posts
        if int(post.get("leads") or 0) > 0 or int(post.get("inquiries") or 0) > 0
    )
    posts_with_early_signal = sum(
        1
        for post in posts
        if int(post.get("comments") or 0) > 0
        or int(post.get("shares") or 0) > 0
        or int(post.get("clicks") or 0) > 0
        or int(post.get("reach") or post.get("views") or 0) > 0
    )
    total_leads = sum(int(post.get("leads") or 0) for post in posts)
    total_inquiries = sum(int(post.get("inquiries") or 0) for post in posts)
    total_comments = sum(int(post.get("comments") or 0) for post in posts)
    total_shares = sum(int(post.get("shares") or 0) for post in posts)
    total_clicks = sum(int(post.get("clicks") or 0) for post in posts)
    total_likes = sum(int(post.get("likes") or 0) for post in posts)
    total_reach = sum(int(post.get("reach") or post.get("views") or 0) for post in posts)
    primary_signal_total = total_leads + total_inquiries
    secondary_signal_total = total_comments + total_shares + total_clicks

    if posts_with_primary_result:
        status = "ready_from_leads"
        confidence = "high"
    elif posts_with_early_signal:
        status = "early_signals_only"
        confidence = "medium"
    elif published_posts:
        status = "published_without_signals"
        confidence = "low"
    elif manual_posts or failed_posts:
        status = "finish_pending_publish"
        confidence = "low"
    else:
        status = "not_enough_data"
        confidence = "none"

    return {
        "schema": "localos_social_learning_readiness_v1",
        "status": status,
        "confidence": confidence,
        "total_posts": total_posts,
        "published_posts": published_posts,
        "posts_with_primary_result": posts_with_primary_result,
        "posts_with_early_signal": posts_with_early_signal,
        "primary_signal_total": primary_signal_total,
        "secondary_signal_total": secondary_signal_total,
        "early_signal_total": total_likes + total_reach,
        "leads": total_leads,
        "inquiries": total_inquiries,
        "comments": total_comments,
        "shares": total_shares,
        "clicks": total_clicks,
        "likes": total_likes,
        "reach": total_reach,
        "pending_manual_or_supervised_posts": manual_posts,
        "failed_posts": failed_posts,
        "primary_metric_ru": "Заявки и обращения",
        "primary_metric_en": "Leads and inquiries",
        "secondary_metric_ru": "Комментарии, репосты и клики",
        "secondary_metric_en": "Comments, shares, and clicks",
        "early_metric_ru": "Охват, просмотры и лайки",
        "early_metric_en": "Reach, views, and likes",
        "summary_ru": _social_learning_readiness_summary(status, True),
        "summary_en": _social_learning_readiness_summary(status, False),
        "next_action_ru": _social_learning_readiness_next_action(status, True),
        "next_action_en": _social_learning_readiness_next_action(status, False),
        "apply_blocked_reason_ru": _social_learning_apply_blocked_reason(status, True),
        "apply_blocked_reason_en": _social_learning_apply_blocked_reason(status, False),
        "checklist": _social_learning_readiness_checklist(
            status,
            total_posts,
            published_posts,
            manual_posts,
            failed_posts,
            posts_with_primary_result,
            posts_with_early_signal,
        ),
        "safe_to_apply_recommendation": status in {"ready_from_leads", "early_signals_only"},
    }


def _social_learning_readiness_checklist(
    status: str,
    total_posts: int,
    published_posts: int,
    manual_posts: int,
    failed_posts: int,
    posts_with_primary_result: int,
    posts_with_early_signal: int,
) -> list[dict[str, Any]]:
    pending_publish = int(manual_posts or 0) + int(failed_posts or 0)
    has_result = int(posts_with_primary_result or 0) > 0 or int(posts_with_early_signal or 0) > 0
    can_apply = status in {"ready_from_leads", "early_signals_only"}
    return [
        {
            "key": "publish_first",
            "status": "done" if int(published_posts or 0) > 0 else ("current" if int(total_posts or 0) > 0 else "pending"),
            "label_ru": "Есть опубликованные посты",
            "label_en": "Published posts exist",
            "detail_ru": f"Опубликовано: {int(published_posts or 0)} из {int(total_posts or 0)}.",
            "detail_en": f"Published: {int(published_posts or 0)} of {int(total_posts or 0)}.",
        },
        {
            "key": "finish_manual_or_failed",
            "status": "attention" if pending_publish > 0 else "done",
            "label_ru": "Ручные задачи и ошибки разобраны",
            "label_en": "Manual tasks and failures are handled",
            "detail_ru": (
                f"Нужно внимание: ручные/контролируемые {int(manual_posts or 0)}, ошибки {int(failed_posts or 0)}."
                if pending_publish > 0
                else "Нет ручных задач или ошибок, которые мешают обучению."
            ),
            "detail_en": (
                f"Needs attention: manual/supervised {int(manual_posts or 0)}, failed {int(failed_posts or 0)}."
                if pending_publish > 0
                else "No manual tasks or failures block learning."
            ),
        },
        {
            "key": "record_results",
            "status": "done" if has_result else ("current" if int(published_posts or 0) > 0 else "pending"),
            "label_ru": "Результат отмечен",
            "label_en": "Results are recorded",
            "detail_ru": (
                f"Постов с заявками/обращениями: {int(posts_with_primary_result or 0)}; с ранними сигналами: {int(posts_with_early_signal or 0)}."
                if has_result
                else "Соберите реакции или отметьте заявку/обращение вручную."
            ),
            "detail_en": (
                f"Posts with leads/inquiries: {int(posts_with_primary_result or 0)}; with early signals: {int(posts_with_early_signal or 0)}."
                if has_result
                else "Collect reactions or record a lead/inquiry manually."
            ),
        },
        {
            "key": "apply_with_confirmation",
            "status": "current" if can_apply else "pending",
            "label_ru": "Можно применять только после подтверждения",
            "label_en": "Apply only after confirmation",
            "detail_ru": (
                "Можно открыть предпросмотр изменений и применить после подтверждения."
                if can_apply
                else "Сначала нужен опубликованный результат: заявки/обращения или хотя бы ранние сигналы."
            ),
            "detail_en": (
                "Open the change preview and apply after confirmation."
                if can_apply
                else "Published results are needed first: leads/inquiries or at least early signals."
            ),
        },
    ]


def _social_learning_readiness_summary(status: str, is_ru: bool) -> str:
    if status == "ready_from_leads":
        return (
            "Есть заявки или обращения: рекомендации можно использовать для следующего плана."
            if is_ru
            else "Leads or inquiries exist: recommendations can guide the next plan."
        )
    if status == "early_signals_only":
        return (
            "Есть ранние сигналы, но заявок пока нет: рекомендации полезны, но их стоит применять осторожно."
            if is_ru
            else "Early signals exist, but no leads yet: recommendations are useful, but apply them carefully."
        )
    if status == "published_without_signals":
        return (
            "Посты опубликованы, но результата ещё не видно: сначала соберите реакции или отметьте заявки вручную."
            if is_ru
            else "Posts are published, but no result is visible yet: collect reactions or record leads manually first."
        )
    if status == "finish_pending_publish":
        return (
            "Часть публикаций ещё ждёт ручного/контролируемого размещения или исправления ошибки."
            if is_ru
            else "Some posts still need manual/supervised placement or error recovery."
        )
    return (
        "Данных для обучения пока мало: сначала опубликуйте посты и отметьте реакции/заявки."
        if is_ru
        else "There is not enough learning data yet: publish posts and record reactions/leads first."
    )


def _social_learning_readiness_next_action(status: str, is_ru: bool) -> str:
    if status == "ready_from_leads":
        return (
            "Нажмите «Предложить изменения», проверьте предпросмотр и применяйте только после подтверждения."
            if is_ru
            else "Click “Suggest changes”, review the preview, and apply only after approval."
        )
    if status == "early_signals_only":
        return (
            "Отметьте заявки/обращения, если они были, затем пересчитайте рекомендации."
            if is_ru
            else "Record leads/inquiries if any happened, then recalculate recommendations."
        )
    if status == "published_without_signals":
        return (
            "Нажмите «Собрать реакции» или отметьте обращения вручную, затем пересчитайте рекомендации."
            if is_ru
            else 'Click "Collect reactions" or record inquiries manually, then recalculate recommendations.'
        )
    if status == "finish_pending_publish":
        return (
            "Сначала завершите ручные/контролируемые публикации или исправьте failed-каналы."
            if is_ru
            else "Finish manual/supervised posts or recover failed channels first."
        )
    return (
        "Подготовьте, подтвердите и опубликуйте первые посты, затем соберите реакции."
        if is_ru
        else "Prepare, approve, and publish the first posts, then collect reactions."
    )


def _social_learning_apply_blocked_reason(status: str, is_ru: bool) -> str:
    if status in {"ready_from_leads", "early_signals_only"}:
        return ""
    if status == "published_without_signals":
        return (
            "Применение заблокировано: сначала соберите реакции или отметьте заявку/обращение вручную."
            if is_ru
            else "Apply is blocked: collect reactions or record a lead/inquiry manually first."
        )
    if status == "finish_pending_publish":
        return (
            "Применение заблокировано: сначала завершите контролируемое/ручное размещение или исправьте ошибки публикации."
            if is_ru
            else "Apply is blocked: finish supervised/manual placement or recover publishing errors first."
        )
    return (
        "Применение заблокировано: сначала опубликуйте посты и соберите результат."
        if is_ru
        else "Apply is blocked: publish posts and collect results first."
    )


def _recommendation_signal_priority(leads: int, inquiries: int, comments: int, reach: int) -> list[dict[str, Any]]:
    return [
        {
            "key": "leads",
            "rank": 1,
            "value": int(leads or 0),
            "label_ru": "Заявки",
            "label_en": "Leads",
            "role_ru": "главный KPI",
            "role_en": "primary KPI",
        },
        {
            "key": "inquiries",
            "rank": 2,
            "value": int(inquiries or 0),
            "label_ru": "Обращения",
            "label_en": "Inquiries",
            "role_ru": "главный KPI",
            "role_en": "primary KPI",
        },
        {
            "key": "comments",
            "rank": 3,
            "value": int(comments or 0),
            "label_ru": "Комментарии",
            "label_en": "Comments",
            "role_ru": "ранний сигнал",
            "role_en": "early signal",
        },
        {
            "key": "reach",
            "rank": 4,
            "value": int(reach or 0),
            "label_ru": "Охват",
            "label_en": "Reach",
            "role_ru": "ранний сигнал",
            "role_en": "early signal",
        },
    ]


def _recommendation_text(leads: int, inquiries: int, comments: int, reach: int, is_ru: bool) -> str:
    if leads or inquiries:
        return (
            "Следующий план усиливаем темами, которые дали заявки и обращения; охват используем только как ранний сигнал."
            if is_ru
            else "Next plan should amplify topics that produced leads and inquiries; reach is only an early signal."
        )
    if comments:
        return (
            "Заявок пока нет, но есть комментарии. Следующая неделя должна добавить более явный CTA и оффер."
            if is_ru
            else "No leads yet, but comments exist. Next week should add clearer CTAs and offers."
        )
    if reach:
        return (
            "Есть охват без обращений. План стоит сместить к коммерческим темам, акциям и конкретным услугам."
            if is_ru
            else "There is reach without inquiries. Shift toward commercial topics, offers, and concrete services."
        )
    return (
        "После публикаций LocalOS будет ранжировать темы по заявкам и обращениям, затем по комментариям и охвату."
        if is_ru
        else "After publishing, LocalOS will rank topics by leads and inquiries first, then comments and reach."
    )


def _social_plan_performance_rows(cursor: Any, plan_id: str) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT
            i.id AS item_id,
            i.theme,
            i.goal,
            i.scheduled_for,
            COALESCE(SUM(m.leads), 0) AS leads,
            COALESCE(SUM(m.inquiries), 0) AS inquiries,
            COALESCE(SUM(m.comments), 0) AS comments,
            COALESCE(SUM(m.shares), 0) AS shares,
            COALESCE(SUM(m.clicks), 0) AS clicks,
            COALESCE(SUM(m.reach), 0) AS reach,
            COALESCE(SUM(m.views), 0) AS views
        FROM contentplanitems i
        LEFT JOIN social_posts sp ON sp.content_plan_item_id = i.id
        LEFT JOIN social_post_metrics m ON m.social_post_id = sp.id
        WHERE i.plan_id = %s
        GROUP BY i.id, i.theme, i.goal, i.scheduled_for
        ORDER BY i.scheduled_for ASC, i.created_at ASC
        """,
        (plan_id,),
    )
    return [_row_to_dict(cursor, row) for row in cursor.fetchall() or []]


def _build_next_plan_changes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scored: list[dict[str, Any]] = [_score_performance_row(row) for row in rows]
    scored.sort(key=lambda item: int(item.get("_score") or 0), reverse=True)
    if not scored:
        return []
    has_business_result = any(int(item.get("leads") or 0) or int(item.get("inquiries") or 0) for item in scored)
    changes: list[dict[str, Any]] = []
    for item in scored[:5]:
        item_id = str(item.get("item_id") or "").strip()
        if not item_id:
            continue
        theme = str(item.get("theme") or "").strip()
        goal = str(item.get("goal") or "").strip()
        leads = int(item.get("leads") or 0)
        inquiries = int(item.get("inquiries") or 0)
        comments = int(item.get("comments") or 0)
        reach = int(item.get("reach") or item.get("views") or 0)
        if leads or inquiries:
            action = "repeat_winning_topic"
            reason_ru = "Тема дала заявки или обращения, поэтому её стоит повторить и усилить CTA."
            proposed_goal = _append_goal_cta(goal, "Повторить тему с прямым призывом записаться или написать.")
        elif comments:
            action = "strengthen_cta"
            reason_ru = "Есть обсуждение без заявки: нужно сделать оффер и следующий шаг понятнее."
            proposed_goal = _append_goal_cta(goal, "Добавить конкретный оффер и призыв к записи.")
        elif reach:
            action = "commercialize_reach"
            reason_ru = "Есть охват без обращений: тему нужно приблизить к услуге, акции или записи."
            proposed_goal = _append_goal_cta(goal, "Сместить текст к услуге, акции и записи.")
        elif not has_business_result:
            action = "add_clear_offer"
            reason_ru = "Пока нет результата: следующая версия должна быть более прикладной и коммерческой."
            proposed_goal = _append_goal_cta(goal, "Сделать понятный оффер и следующий шаг для клиента.")
        else:
            continue
        changes.append(
            {
                "item_id": item_id,
                "theme": theme,
                "action": action,
                "reason_ru": reason_ru,
                "reason_en": _recommendation_reason_en(action),
                "current_goal": goal,
                "proposed_goal": proposed_goal,
                "metrics": {
                    "leads": leads,
                    "inquiries": inquiries,
                    "comments": comments,
                    "reach": reach,
                },
            }
        )
    return changes


def _add_channel_breakdown_to_changes(
    changes: list[dict[str, Any]],
    posts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    posts_by_item_id: dict[str, list[dict[str, Any]]] = {}
    for post in posts:
        item_id = str(post.get("content_plan_item_id") or "").strip()
        if not item_id:
            continue
        posts_by_item_id.setdefault(item_id, []).append(post)

    enriched: list[dict[str, Any]] = []
    for change in changes:
        item_id = str(change.get("item_id") or "").strip()
        item_posts = posts_by_item_id.get(item_id, [])
        breakdown = _channel_breakdown_for_posts(item_posts)
        enriched.append({**change, "channel_breakdown": breakdown})
    return enriched


def _channel_breakdown_for_posts(posts: list[dict[str, Any]]) -> dict[str, Any]:
    best_channels: list[dict[str, Any]] = []
    weak_channels: list[dict[str, Any]] = []
    for post in posts:
        platform = str(post.get("platform") or "").strip()
        if not platform:
            continue
        metrics = {
            "leads": int(post.get("leads") or 0),
            "inquiries": int(post.get("inquiries") or 0),
            "comments": int(post.get("comments") or 0),
            "reach": int(post.get("reach") or post.get("views") or 0),
        }
        status = str(post.get("status") or "").strip()
        item = {
            "platform": platform,
            "platform_label": platform_label(platform),
            "status": status,
            "metrics": metrics,
        }
        if metrics["leads"] or metrics["inquiries"]:
            item["reason_ru"] = "Канал дал заявку или обращение; повторить тему здесь в первую очередь."
            item["reason_en"] = "This channel produced a lead or inquiry; repeat the topic here first."
            best_channels.append(item)
        elif status in {"published", "failed", "needs_manual_publish", "needs_supervised_publish"}:
            item["reason_ru"] = _channel_breakdown_weak_reason(status, metrics, True)
            item["reason_en"] = _channel_breakdown_weak_reason(status, metrics, False)
            weak_channels.append(item)

    best_channels.sort(
        key=lambda item: (
            int(item.get("metrics", {}).get("leads") or 0),
            int(item.get("metrics", {}).get("inquiries") or 0),
            int(item.get("metrics", {}).get("comments") or 0),
            int(item.get("metrics", {}).get("reach") or 0),
        ),
        reverse=True,
    )
    weak_channels.sort(
        key=lambda item: (
            1 if str(item.get("status") or "") in {"failed", "needs_manual_publish", "needs_supervised_publish"} else 0,
            int(item.get("metrics", {}).get("reach") or 0),
            int(item.get("metrics", {}).get("comments") or 0),
        ),
        reverse=True,
    )
    summary_ru = "Канальных данных пока нет: сначала опубликуйте посты и отметьте заявки/обращения."
    summary_en = "No channel data yet: publish posts first and record leads/inquiries."
    if best_channels:
        labels = ", ".join(str(item.get("platform_label") or "") for item in best_channels[:2] if item.get("platform_label"))
        summary_ru = f"Повторить тему в каналах, где были заявки/обращения: {labels}."
        summary_en = f"Repeat the topic in channels that produced leads/inquiries: {labels}."
    elif weak_channels:
        labels = ", ".join(str(item.get("platform_label") or "") for item in weak_channels[:2] if item.get("platform_label"))
        summary_ru = f"Сначала поправить слабые каналы: {labels}."
        summary_en = f"Fix weak channels first: {labels}."
    return {
        "best_channels": best_channels[:3],
        "weak_channels": weak_channels[:3],
        "summary_ru": summary_ru,
        "summary_en": summary_en,
    }


def _channel_breakdown_weak_reason(status: str, metrics: dict[str, int], is_ru: bool) -> str:
    if status == "failed":
        return (
            "Публикация не вышла: сначала исправить подключение или запустить ручной сценарий."
            if is_ru
            else "Publishing failed: fix the connection or run the manual flow first."
        )
    if status in {"needs_manual_publish", "needs_supervised_publish"}:
        return (
            "Пост ждёт ручное/контролируемое размещение; без этого канал нельзя оценить по результату."
            if is_ru
            else "The post awaits manual/supervised placement; the channel cannot be judged until it is published."
        )
    if int(metrics.get("reach") or 0) or int(metrics.get("comments") or 0):
        return (
            "Есть ранние сигналы без заявки: усилить оффер и следующий шаг."
            if is_ru
            else "Early signals exist without a lead: strengthen the offer and next step."
        )
    return (
        "Пост опубликован, но результата пока нет: проверить тему, время и CTA."
        if is_ru
        else "The post is published but has no result yet: check topic, timing, and CTA."
    )


def _build_social_learning_insights(rows: list[dict[str, Any]], posts: list[dict[str, Any]]) -> dict[str, Any]:
    scored_rows = [_score_performance_row(row) for row in rows]
    scored_rows.sort(key=lambda item: int(item.get("_score") or 0), reverse=True)
    winning_topics = [
        _topic_insight(item, "repeat")
        for item in scored_rows
        if int(item.get("leads") or 0) or int(item.get("inquiries") or 0)
    ][:3]
    no_result_topics = [
        _topic_insight(item, "rewrite")
        for item in scored_rows
        if not _row_has_any_signal(item)
    ][:5]
    weak_channels = _weak_channel_insights(posts)
    owner_next_steps = _owner_next_steps_for_social_learning(winning_topics, weak_channels, no_result_topics, posts)
    return {
        "winning_topics": winning_topics,
        "weak_channels": weak_channels,
        "no_result_topics": no_result_topics,
        "owner_next_steps": owner_next_steps,
        "cta_suggestions": _cta_suggestions(winning_topics, weak_channels, no_result_topics),
        "frequency_suggestions": _frequency_suggestions(winning_topics, weak_channels, no_result_topics),
    }


def _owner_next_steps_for_social_learning(
    winning_topics: list[dict[str, Any]],
    weak_channels: list[dict[str, Any]],
    no_result_topics: list[dict[str, Any]],
    posts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    published_posts = sum(1 for post in posts if str(post.get("status") or "").strip() == "published")
    primary_results = sum(int(post.get("leads") or 0) + int(post.get("inquiries") or 0) for post in posts)
    steps: list[dict[str, Any]] = []
    if winning_topics:
        topic = str(winning_topics[0].get("theme") or "").strip()
        topic_ru = f": {topic}" if topic else ""
        topic_en = f": {topic}" if topic else ""
        steps.append(
            {
                "key": "repeat_winner",
                "priority": 1,
                "ru": f"Повторить выигравшую тему{topic_ru} с прямым CTA на запись или сообщение.",
                "en": f"Repeat the winning topic{topic_en} with a direct CTA to book or message.",
            }
        )
    if weak_channels:
        channel = str(weak_channels[0].get("platform_label") or "").strip()
        channel_ru = f": {channel}" if channel else ""
        channel_en = f": {channel}" if channel else ""
        steps.append(
            {
                "key": "fix_weak_channel",
                "priority": 2,
                "ru": f"Разобрать слабый канал{channel_ru}: ошибка, ручное размещение или охват без заявки.",
                "en": f"Fix the weak channel{channel_en}: error, manual placement, or reach without leads.",
            }
        )
    if no_result_topics and not winning_topics:
        steps.append(
            {
                "key": "rewrite_no_result_topic",
                "priority": 3,
                "ru": "Переписать темы без результата от проблемы клиента к конкретной услуге, офферу и записи.",
                "en": "Rewrite no-result topics from customer problem to concrete service, offer, and booking.",
            }
        )
    if published_posts and primary_results <= 0:
        steps.append(
            {
                "key": "record_primary_result",
                "priority": 4,
                "ru": "Проверить, были ли заявки или обращения, и отметить их вручную перед применением изменений.",
                "en": "Check whether leads or inquiries happened and record them manually before applying changes.",
            }
        )
    if not steps:
        steps.append(
            {
                "key": "publish_and_measure",
                "priority": 1,
                "ru": "Опубликовать первые посты, собрать реакции и отметить заявки/обращения как главный результат.",
                "en": "Publish the first posts, collect reactions, and record leads/inquiries as the main result.",
            }
        )
    return steps[:4]


def _score_performance_row(row: dict[str, Any]) -> dict[str, Any]:
    leads = int(row.get("leads") or 0)
    inquiries = int(row.get("inquiries") or 0)
    comments = int(row.get("comments") or 0)
    shares = int(row.get("shares") or 0)
    clicks = int(row.get("clicks") or 0)
    reach = int(row.get("reach") or row.get("views") or 0)
    score = leads * 100 + inquiries * 60 + comments * 15 + shares * 12 + clicks * 10 + min(reach, 1000) // 100
    return {**row, "_score": score}


def _row_has_any_signal(row: dict[str, Any]) -> bool:
    for key in ("leads", "inquiries", "comments", "shares", "clicks", "reach", "views"):
        if int(row.get(key) or 0) > 0:
            return True
    return False


def _topic_insight(row: dict[str, Any], action: str) -> dict[str, Any]:
    return {
        "item_id": str(row.get("item_id") or "").strip(),
        "theme": str(row.get("theme") or "").strip(),
        "action": action,
        "metrics": {
            "leads": int(row.get("leads") or 0),
            "inquiries": int(row.get("inquiries") or 0),
            "comments": int(row.get("comments") or 0),
            "shares": int(row.get("shares") or 0),
            "clicks": int(row.get("clicks") or 0),
            "reach": int(row.get("reach") or row.get("views") or 0),
        },
    }


def _weak_channel_insights(posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_platform: dict[str, dict[str, int]] = {}
    for post in posts:
        platform = str(post.get("platform") or "").strip()
        if not platform:
            continue
        bucket = by_platform.setdefault(
            platform,
            {
                "posts": 0,
                "published": 0,
                "failed": 0,
                "manual": 0,
                "leads": 0,
                "inquiries": 0,
                "comments": 0,
                "reach": 0,
            },
        )
        bucket["posts"] += 1
        status = str(post.get("status") or "").strip()
        if status == "published":
            bucket["published"] += 1
        elif status == "failed":
            bucket["failed"] += 1
        elif status in {"needs_manual_publish", "needs_supervised_publish"}:
            bucket["manual"] += 1
        bucket["leads"] += int(post.get("leads") or 0)
        bucket["inquiries"] += int(post.get("inquiries") or 0)
        bucket["comments"] += int(post.get("comments") or 0)
        bucket["reach"] += int(post.get("reach") or post.get("views") or 0)
    result: list[dict[str, Any]] = []
    for platform, stats in by_platform.items():
        if stats["leads"] or stats["inquiries"]:
            continue
        if not (stats["published"] or stats["failed"] or stats["manual"]):
            continue
        result.append(
            {
                "platform": platform,
                "platform_label": platform_label(platform),
                "reason_ru": _weak_channel_reason(stats, True),
                "reason_en": _weak_channel_reason(stats, False),
                "metrics": stats,
            }
        )
    result.sort(
        key=lambda item: (
            int(item.get("metrics", {}).get("failed") or 0) + int(item.get("metrics", {}).get("manual") or 0),
            int(item.get("metrics", {}).get("reach") or 0),
        ),
        reverse=True,
    )
    return result[:5]


def _weak_channel_reason(stats: dict[str, int], is_ru: bool) -> str:
    if int(stats.get("failed") or 0):
        return (
            "Есть ошибки публикации: сначала исправить подключение или перевести канал в ручной сценарий."
            if is_ru
            else "Publishing errors exist: fix the connection or move this channel to manual flow first."
        )
    if int(stats.get("manual") or 0):
        return (
            "Канал требует ручного/контролируемого размещения: не считать его автопубликацией."
            if is_ru
            else "This channel requires manual/supervised placement; do not treat it as autopublish."
        )
    if int(stats.get("reach") or 0):
        return (
            "Есть охват без заявок: нужен более прямой оффер и понятный следующий шаг."
            if is_ru
            else "There is reach without leads: use a clearer offer and next step."
        )
    return (
        "Нет бизнес-результата: проверить тему, время публикации и CTA."
        if is_ru
        else "No business result: check topic, timing, and CTA."
    )


def _cta_suggestions(
    winning_topics: list[dict[str, Any]],
    weak_channels: list[dict[str, Any]],
    no_result_topics: list[dict[str, Any]],
) -> list[dict[str, str]]:
    if winning_topics:
        return [
            {
                "ru": "Повторить выигравшие темы с прямым CTA: записаться, написать, получить консультацию.",
                "en": "Repeat winning topics with a direct CTA: book, message, or request a consultation.",
            },
            {
                "ru": "В первом экране поста держать услугу, выгоду и действие клиента.",
                "en": "Keep service, benefit, and customer action in the first screen of the post.",
            },
        ]
    if weak_channels:
        return [
            {
                "ru": "Для слабых каналов добавить конкретный оффер, срок действия и понятную кнопку/контакт.",
                "en": "For weak channels, add a concrete offer, deadline, and clear contact/action.",
            }
        ]
    if no_result_topics:
        return [
            {
                "ru": "Темы без результата переписать от проблемы клиента к конкретной услуге и записи.",
                "en": "Rewrite no-result topics from customer problem to concrete service and booking.",
            }
        ]
    return [
        {
            "ru": "Соберите первые заявки/обращения, затем LocalOS предложит точечные CTA.",
            "en": "Record initial leads/inquiries, then LocalOS will suggest targeted CTAs.",
        }
    ]


def _frequency_suggestions(
    winning_topics: list[dict[str, Any]],
    weak_channels: list[dict[str, Any]],
    no_result_topics: list[dict[str, Any]],
) -> list[dict[str, str]]:
    if winning_topics:
        return [
            {
                "ru": "На следующей неделе повторить 1-2 выигравшие темы в разных каналах.",
                "en": "Next week, repeat 1-2 winning topics across different channels.",
            }
        ]
    if no_result_topics and not weak_channels:
        return [
            {
                "ru": "Не увеличивать частоту: сначала переписать темы и CTA, потом масштабировать.",
                "en": "Do not increase frequency yet: rewrite topics and CTAs before scaling.",
            }
        ]
    return [
        {
            "ru": "Держать текущую частоту, но проверять результат по заявкам и обращениям.",
            "en": "Keep current frequency, but judge results by leads and inquiries.",
        }
    ]


def _append_goal_cta(goal: str, cta: str) -> str:
    base = str(goal or "").strip()
    addition = str(cta or "").strip()
    if not base:
        return addition
    if addition.lower() in base.lower():
        return base
    return f"{base}\n\n{addition}"


def _recommendation_reason_en(action: str) -> str:
    if action == "repeat_winning_topic":
        return "The topic produced leads or inquiries, so repeat it with a stronger CTA."
    if action == "strengthen_cta":
        return "There is discussion without a lead; make the offer and next step clearer."
    if action == "commercialize_reach":
        return "There is reach without inquiries; move the topic closer to a service, offer, or booking."
    return "No business result yet; make the next version more practical and commercial."


def platform_label(platform: str) -> str:
    labels = {
        "yandex_maps": "Яндекс Карты",
        "two_gis": "2ГИС",
        "google_business": "Google Business",
        "telegram": "Telegram",
        "vk": "VK",
        "instagram": "Instagram",
        "facebook": "Facebook",
    }
    return labels.get(str(platform or "").strip(), str(platform or "").strip())


def _serialize_social_post(cursor: Any, row: Any) -> dict[str, Any]:
    data = _row_to_dict(cursor, row)
    if not data:
        return {}
    for key in ("media_json", "metadata_json", "raw_json"):
        if key in data:
            data[key] = _json_value(data.get(key), {} if key != "media_json" else [])
    for key, value in list(data.items()):
        if isinstance(value, (datetime, date)):
            data[key] = value.isoformat()
    data["platform_label"] = platform_label(str(data.get("platform") or ""))
    data["next_action"] = next_action_for_social_post(data)
    data["publish_evidence"] = _social_publish_evidence(data)
    data["schedule_attention"] = _social_schedule_attention(data)
    return data


def _social_schedule_attention(post: dict[str, Any]) -> dict[str, Any]:
    status = str(post.get("status") or "").strip()
    scheduled_at = _parse_social_scheduled_at(post.get("scheduled_for"))
    if not scheduled_at:
        return {
            "schema": "localos_social_schedule_attention_v1",
            "status": "unscheduled",
            "requires_attention": status in {"approved", "queued"},
            "scheduled_for_is_past": False,
            "message_ru": "Дата публикации не задана.",
            "message_en": "No scheduled publish date is set.",
            "next_action_ru": "Укажите дату перед постановкой в расписание.",
            "next_action_en": "Set a publish date before queueing.",
        }
    now = datetime.now(timezone.utc)
    is_past = scheduled_at <= now
    if is_past and status in {"draft", "needs_review", "approved"}:
        return {
            "schema": "localos_social_schedule_attention_v1",
            "status": "overdue_before_queue",
            "requires_attention": True,
            "scheduled_for_is_past": True,
            "message_ru": "Дата публикации уже в прошлом.",
            "message_en": "The scheduled publish date is already in the past.",
            "next_action_ru": "Перед постановкой в очередь перенесите дату или осознанно запускайте как немедленную публикацию.",
            "next_action_en": "Move the date forward before queueing, or intentionally run it as an immediate publish.",
        }
    if is_past and status == "queued":
        return {
            "schema": "localos_social_schedule_attention_v1",
            "status": "due_now",
            "requires_attention": False,
            "scheduled_for_is_past": True,
            "message_ru": "Пост уже due: worker может взять его в ближайший цикл.",
            "message_en": "This post is due: the worker can pick it up on the next cycle.",
            "next_action_ru": "Проверьте readiness канала перед запуском worker dispatch.",
            "next_action_en": "Check channel readiness before running worker dispatch.",
        }
    return {
        "schema": "localos_social_schedule_attention_v1",
        "status": "scheduled",
        "requires_attention": False,
        "scheduled_for_is_past": False,
        "message_ru": "Дата публикации в будущем.",
        "message_en": "The publish date is in the future.",
        "next_action_ru": "Проверьте текст, подтвердите и поставьте в расписание.",
        "next_action_en": "Review the copy, approve it, and queue the post.",
    }


def _parse_social_scheduled_at(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, datetime.min.time())
    else:
        raw = str(value or "").strip()
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            try:
                parsed = datetime.combine(date.fromisoformat(raw[:10]), datetime.min.time())
            except ValueError:
                return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _social_publish_evidence(post: dict[str, Any]) -> dict[str, Any]:
    status = str(post.get("status") or "").strip()
    platform = str(post.get("platform") or "").strip()
    provider_label = platform_label(platform)
    provider_post_url = str(post.get("provider_post_url") or "").strip()
    provider_post_id = str(post.get("provider_post_id") or "").strip()
    automation_task_id = str(post.get("automation_task_id") or "").strip()
    last_error = str(post.get("last_error") or "").strip()
    metadata = _json_dict(post.get("metadata_json"))
    provider_status = str(metadata.get("provider_status") or metadata.get("queue_preflight_status") or "").strip()
    proof_source = _social_publish_proof_source(provider_status, metadata)
    proof_quality = _social_publish_proof_quality(status, provider_post_url, provider_post_id, automation_task_id, last_error)

    base: dict[str, Any] = {
        "schema": "localos_social_publish_evidence_v1",
        "platform": platform,
        "platform_label": provider_label,
        "status": status,
        "provider_status": provider_status,
        "proof_url": provider_post_url,
        "proof_id": provider_post_id,
        "automation_task_id": automation_task_id,
        "last_error": last_error,
        "recoverable": status in {"failed", "needs_manual_publish", "needs_supervised_publish"},
        "proof_source": proof_source,
        "proof_quality": proof_quality,
        "ready_for_metrics": status == "published",
        "ready_for_attribution": status == "published",
        "external_publish_proven": status == "published" and proof_quality in {"url", "provider_id"},
        "manual_confirmation": proof_source == "manual_confirmation",
    }

    if status == "published":
        if provider_post_url:
            summary_ru = "Пост опубликован, ссылка сохранена."
            summary_en = "The post is published and the URL is saved."
        elif provider_post_id:
            summary_ru = "Пост опубликован, ID публикации сохранён."
            summary_en = "The post is published and the provider ID is saved."
        else:
            summary_ru = "Пост отмечен опубликованным; добавьте ссылку или ID, если они есть."
            summary_en = "The post is marked published; add a URL or ID if available."
        base.update(
            {
                "tone": "success",
                "title_ru": f"{provider_label}: опубликовано",
                "title_en": f"{provider_label}: published",
                "summary_ru": summary_ru,
                "summary_en": summary_en,
                "next_action_ru": "Обновите реакции и отметьте заявки, если они пришли с этой публикации.",
                "next_action_en": "Update reactions and record leads if they came from this post.",
                "result_packet": _social_result_collection_packet(post),
            }
        )
        return base

    if status == "needs_supervised_publish":
        supervised = _json_dict(metadata.get("supervised_publish"))
        manual_handoff = _json_dict(supervised.get("manual_handoff"))
        target_url = str(supervised.get("target_url") or manual_handoff.get("target_url") or "").strip()
        profile_hint = str(supervised.get("profile_hint") or manual_handoff.get("profile_hint") or "").strip()
        copy_ready_text = str(supervised.get("copy_ready_text") or manual_handoff.get("copy_ready_text") or "").strip()
        checklist_ru = supervised.get("manual_checklist_ru") or manual_handoff.get("checklist_ru") or []
        checklist_en = supervised.get("manual_checklist_en") or manual_handoff.get("checklist_en") or []
        if not isinstance(checklist_ru, list):
            checklist_ru = []
        if not isinstance(checklist_en, list):
            checklist_en = []
        base.update(
            {
                "tone": "warning",
                "title_ru": f"{provider_label}: нужно контролируемое размещение",
                "title_en": f"{provider_label}: supervised placement needed",
                "summary_ru": "LocalOS подготовил контролируемое или ручное размещение; финальный клик публикации остаётся за человеком.",
                "summary_en": "LocalOS prepared supervised/manual placement; the final publish click stays with a human.",
                "next_action_ru": "Откройте контролируемое размещение, проверьте предпросмотр и отметьте результат.",
                "next_action_en": "Open supervised placement, review the preview, and record the result.",
                "target_url": target_url,
                "profile_hint": profile_hint,
                "copy_ready_text": copy_ready_text,
                "manual_checklist_ru": [str(item) for item in checklist_ru if str(item or "").strip()][:5],
                "manual_checklist_en": [str(item) for item in checklist_en if str(item or "").strip()][:5],
                "stop_before_final_publish": bool(supervised.get("stop_before_final_publish", True)),
                "browser_final_click_allowed": False,
                "placement_packet": _social_supervised_placement_packet(post, supervised, manual_handoff),
            }
        )
        return base

    if status == "needs_manual_publish":
        supervised = _json_dict(metadata.get("supervised_publish"))
        manual_handoff = _json_dict(supervised.get("manual_handoff") or metadata.get("manual_handoff"))
        summary_ru = last_error or "Канал требует ручного размещения или подключения ключей."
        summary_en = last_error or "The channel needs manual placement or connected credentials."
        base.update(
            {
                "tone": "warning",
                "title_ru": f"{provider_label}: нужно действие человека",
                "title_en": f"{provider_label}: human action needed",
                "summary_ru": summary_ru,
                "summary_en": summary_en,
                "next_action_ru": "Подключите канал или разместите пост вручную и сохраните ссылку/ID.",
                "next_action_en": "Connect the channel or publish manually, then save the URL/ID.",
                "placement_packet": _social_supervised_placement_packet(post, supervised, manual_handoff),
            }
        )
        return base

    if status == "failed":
        base.update(
            {
                "tone": "danger",
                "title_ru": f"{provider_label}: публикация не выполнена",
                "title_en": f"{provider_label}: publishing failed",
                "summary_ru": last_error or "Проверьте подключение канала и повторите публикацию.",
                "summary_en": last_error or "Check the channel connection and retry publishing.",
                "next_action_ru": "Исправьте причину, повторите отправку или переведите пост в ручной режим.",
                "next_action_en": "Fix the cause, retry publishing, or move the post to manual flow.",
            }
        )
        return base

    if status == "queued":
        base.update(
            {
                "tone": "info",
                "title_ru": f"{provider_label}: в расписании",
                "title_en": f"{provider_label}: queued",
                "summary_ru": "Пост утверждён и ждёт даты публикации; worker выполнит его по расписанию.",
                "summary_en": "The post is approved and waiting for its scheduled time; the worker will dispatch it.",
                "next_action_ru": "Дождитесь времени публикации или запустите scoped dispatch вручную.",
                "next_action_en": "Wait for the scheduled time or run scoped dispatch manually.",
            }
        )
        return base

    if status == "publishing":
        base.update(
            {
                "tone": "info",
                "title_ru": f"{provider_label}: публикуется",
                "title_en": f"{provider_label}: publishing",
                "summary_ru": "LocalOS сейчас выполняет отправку в канал.",
                "summary_en": "LocalOS is sending this post to the channel now.",
                "next_action_ru": "Проверьте итог после завершения worker dispatch.",
                "next_action_en": "Check the result after worker dispatch finishes.",
            }
        )
        return base

    return {
        **base,
        "tone": "neutral",
        "title_ru": f"{provider_label}: результат ещё не зафиксирован",
        "title_en": f"{provider_label}: no publish result yet",
        "summary_ru": "Сначала проверьте текст, подтвердите его и поставьте публикацию в расписание.",
        "summary_en": "Review the copy, approve it, and queue the post first.",
        "next_action_ru": "Подготовьте preview и подтвердите публикацию.",
        "next_action_en": "Prepare the preview and approve the post.",
    }


def _social_supervised_placement_packet(
    post: dict[str, Any],
    supervised: dict[str, Any],
    manual_handoff: dict[str, Any],
) -> dict[str, Any]:
    platform = str(post.get("platform") or supervised.get("platform") or "").strip()
    status = str(post.get("status") or "").strip()
    target_url = str(supervised.get("target_url") or manual_handoff.get("target_url") or "").strip()
    profile_hint = str(supervised.get("profile_hint") or manual_handoff.get("profile_hint") or "").strip()
    copy_ready_text = str(supervised.get("copy_ready_text") or manual_handoff.get("copy_ready_text") or "").strip()
    checklist_ru = supervised.get("manual_checklist_ru") or manual_handoff.get("checklist_ru") or []
    checklist_en = supervised.get("manual_checklist_en") or manual_handoff.get("checklist_en") or []
    handoff_checklist_ru = supervised.get("handoff_checklist_ru") or []
    handoff_checklist_en = supervised.get("handoff_checklist_en") or []
    if not isinstance(checklist_ru, list):
        checklist_ru = []
    if not isinstance(checklist_en, list):
        checklist_en = []
    if not isinstance(handoff_checklist_ru, list):
        handoff_checklist_ru = []
    if not isinstance(handoff_checklist_en, list):
        handoff_checklist_en = []
    handoff_state = _json_dict(supervised.get("handoff_state"))
    completion_contract = _json_dict(supervised.get("completion_contract") or _social_supervised_completion_contract())
    done_criteria_ru = completion_contract.get("done_criteria_ru") or supervised.get("done_criteria_ru") or []
    done_criteria_en = completion_contract.get("done_criteria_en") or supervised.get("done_criteria_en") or []
    if not isinstance(done_criteria_ru, list):
        done_criteria_ru = []
    if not isinstance(done_criteria_en, list):
        done_criteria_en = []
    return {
        "schema": "localos_social_supervised_placement_packet_v1",
        "platform": platform,
        "platform_label": platform_label(platform),
        "status": status,
        "mode": str(supervised.get("mode") or post.get("publish_mode") or "manual").strip(),
        "target_url": target_url,
        "target_ready": bool(target_url),
        "profile_hint": profile_hint,
        "copy_ready": bool(copy_ready_text),
        "copy_ready_text": copy_ready_text,
        "checklist_ru": [str(item) for item in checklist_ru if str(item or "").strip()][:5],
        "checklist_en": [str(item) for item in checklist_en if str(item or "").strip()][:5],
        "handoff_checklist_ru": [str(item) for item in handoff_checklist_ru if str(item or "").strip()][:5],
        "handoff_checklist_en": [str(item) for item in handoff_checklist_en if str(item or "").strip()][:5],
        "checklist_count": len([item for item in checklist_ru if str(item or "").strip()]),
        "automation_task_id": str(post.get("automation_task_id") or "").strip(),
        "openclaw_task_requested": bool(handoff_state.get("openclaw_task_requested")),
        "openclaw_outbox_id": str(handoff_state.get("openclaw_outbox_id") or "").strip(),
        "agent_action_ledger_id": str(_json_dict(post.get("metadata_json")).get("agent_action_ledger_id") or "").strip(),
        "manual_fallback_required": status == "needs_manual_publish" or bool(supervised.get("manual_fallback_required")),
        "stop_before_final_publish": bool(supervised.get("stop_before_final_publish", True)),
        "browser_final_click_allowed": False,
        "final_publish_policy": "human_final_click_required",
        "completion_contract": completion_contract,
        "completion_required_fields": completion_contract.get("required_result_fields")
        if isinstance(completion_contract.get("required_result_fields"), list)
        else [],
        "done_criteria_ru": [str(item) for item in done_criteria_ru if str(item or "").strip()][:5],
        "done_criteria_en": [str(item) for item in done_criteria_en if str(item or "").strip()][:5],
        "preview_required": bool(completion_contract.get("preview_required", True)),
        "operator_next_action_ru": str(supervised.get("operator_next_action_ru") or "").strip(),
        "operator_next_action_en": str(supervised.get("operator_next_action_en") or "").strip(),
        "owner_next_action_ru": (
            "Откройте площадку, вставьте готовый текст, проверьте предпросмотр и нажмите финальную публикацию только сами."
        ),
        "owner_next_action_en": (
            "Open the platform, paste the prepared copy, review the preview, and make the final publish click yourself."
        ),
    }


def _social_result_collection_packet(post: dict[str, Any]) -> dict[str, Any]:
    leads = int(post.get("leads") or 0)
    inquiries = int(post.get("inquiries") or 0)
    comments = int(post.get("comments") or 0)
    shares = int(post.get("shares") or 0)
    clicks = int(post.get("clicks") or 0)
    likes = int(post.get("likes") or 0)
    views = int(post.get("views") or 0)
    reach = int(post.get("reach") or 0)
    primary_total = leads + inquiries
    early_total = comments + shares + clicks + likes + views + reach
    if primary_total > 0:
        status = "primary_result_recorded"
    elif early_total > 0:
        status = "early_signals_only"
    else:
        status = "needs_result_input"
    return {
        "schema": "localos_social_result_collection_packet_v1",
        "status": status,
        "primary_metric_ru": "Заявки и обращения",
        "primary_metric_en": "Leads and inquiries",
        "primary_result_total": primary_total,
        "early_signal_total": early_total,
        "leads": leads,
        "inquiries": inquiries,
        "comments": comments,
        "shares": shares,
        "clicks": clicks,
        "likes": likes,
        "views": views,
        "reach": reach,
        "recommendation_priority": [
            "leads",
            "inquiries",
            "comments",
            "shares",
            "clicks",
            "reach",
            "views",
            "likes",
        ],
        "ready_for_recommendation": primary_total > 0 or early_total > 0,
        "owner_next_action_ru": _social_result_collection_next_action(status, True),
        "owner_next_action_en": _social_result_collection_next_action(status, False),
    }


def _social_result_collection_next_action(status: str, is_ru: bool) -> str:
    if status == "primary_result_recorded":
        return (
            "Заявки/обращения отмечены. Можно предлагать изменения следующего плана и проверять их перед применением."
            if is_ru
            else "Leads/inquiries are recorded. You can suggest next-plan changes and review them before applying."
        )
    if status == "early_signals_only":
        return (
            "Есть ранние сигналы. Перед применением изменений проверьте, были ли заявки или обращения."
            if is_ru
            else "Early signals exist. Before applying changes, check whether leads or inquiries happened."
        )
    return (
        "Сначала отметьте заявку, обращение или ранний сигнал, чтобы LocalOS понял результат публикации."
        if is_ru
        else "Record a lead, inquiry, or early signal first so LocalOS can learn from the post."
    )


def _social_publish_proof_source(provider_status: str, metadata: dict[str, Any]) -> str:
    normalized = str(provider_status or "").strip()
    if normalized.startswith("telegram_"):
        return "telegram_bot_api"
    if normalized.startswith("vk_"):
        return "vk_api"
    if normalized.startswith("google_"):
        return "google_business_api"
    if normalized.startswith("meta_"):
        return "meta_graph_api"
    if str(metadata.get("published_source") or "").strip() == "manual_confirmation":
        return "manual_confirmation"
    if normalized:
        return normalized
    return "not_published_yet"


def _social_publish_proof_quality(
    status: str,
    provider_post_url: str,
    provider_post_id: str,
    automation_task_id: str,
    last_error: str,
) -> str:
    if str(status or "").strip() == "published":
        if str(provider_post_url or "").strip():
            return "url"
        if str(provider_post_id or "").strip():
            return "provider_id"
        return "published_without_provider_ref"
    if str(status or "").strip() == "needs_supervised_publish" and str(automation_task_id or "").strip():
        return "supervised_task"
    if str(last_error or "").strip():
        return "error"
    return "pending"


def _row_to_dict(cursor: Any, row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, dict):
        return dict(row)
    if hasattr(row, "keys"):
        try:
            return {key: row[key] for key in row.keys()}
        except Exception:
            return {}
    description = getattr(cursor, "description", None) or []
    if description and isinstance(row, (tuple, list)):
        return {
            str(column[0]): row[index]
            for index, column in enumerate(description)
            if index < len(row)
        }
    return {}


def _row_get(row: Any, key: str, index: int = 0, default: Any = None) -> Any:
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    if hasattr(row, "keys"):
        try:
            return row[key]
        except Exception:
            return default
    try:
        return row[index]
    except Exception:
        return default


def _json_value(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return default
    return default


def _json_dict(value: Any) -> dict[str, Any]:
    parsed = _json_value(value, {})
    return parsed if isinstance(parsed, dict) else {}


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _new_id() -> str:
    return str(uuid.uuid4())
