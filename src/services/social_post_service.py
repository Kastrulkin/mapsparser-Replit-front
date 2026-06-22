from __future__ import annotations

import json
import os
import sys
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
        "next_action_ru": "Ждёт даты публикации. Worker выполнит API publish или создаст controlled task.",
        "next_action_en": "Waiting for schedule. The worker will publish via API or create a controlled task.",
    },
    {
        "key": "needs_supervised_publish",
        "label_ru": "Нужно контролируемое размещение",
        "label_en": "Needs supervised placement",
        "next_action_ru": "Открыть controlled-задачу для Яндекс/2ГИС и остановиться перед финальной публикацией.",
        "next_action_en": "Open the controlled Yandex/2GIS task and stop before final publishing.",
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
        return {
            "posts": posts,
            "summary": _summary_for_posts(posts),
            "queue_groups": build_social_queue_groups(posts),
            "recommendation": _build_plan_recommendation(posts),
            "learning_readiness": _social_learning_readiness(posts),
            "channel_readiness": _build_channel_readiness(cursor, str(plan.get("business_id") or "")),
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
            "openclaw_browser_readiness": _social_openclaw_browser_readiness(),
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
            "openclaw_browser_readiness": _social_openclaw_browser_readiness(),
            "read_only": True,
            "external_publish_performed": False,
            "browser_final_click_allowed": False,
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
    channel_readiness = channel_payload.get("channel_readiness")
    channel_summary = channel_payload.get("summary")
    return _build_social_launch_preflight_payload(
        normalized_business_id,
        channel_readiness if isinstance(channel_readiness, list) else [],
        channel_summary if isinstance(channel_summary, dict) else {},
        dispatch_preview,
    )


def _build_social_launch_preflight_payload(
    business_id: str,
    channel_readiness: list[dict[str, Any]],
    channel_summary: dict[str, Any],
    dispatch_preview: dict[str, Any],
) -> dict[str, Any]:
    readiness = dispatch_preview.get("readiness") if isinstance(dispatch_preview.get("readiness"), dict) else {}
    due_count = int(readiness.get("due_count") or dispatch_preview.get("picked") or 0)
    external_publish_count = int(readiness.get("external_publish_count") or 0)
    controlled_count = int(readiness.get("controlled_count") or 0)
    manual_count = int(readiness.get("manual_count") or 0)
    skipped_no_access = int(readiness.get("skipped_no_access") or dispatch_preview.get("skipped_no_access") or 0)
    blocked_api_channels = [
        item for item in channel_readiness
        if str(item.get("publish_mode") or "") == "api" and not bool(item.get("ready"))
    ]
    controlled_channels = [
        item for item in channel_readiness
        if str(item.get("publish_mode") or "") != "api"
    ]
    status = "no_due_posts"
    if external_publish_count > 0:
        status = "ready_for_api_dispatch"
    elif controlled_count > 0:
        status = "ready_for_controlled_handoff"
    elif manual_count > 0:
        status = "manual_or_connection_needed"
    elif skipped_no_access > 0:
        status = "access_limited"
    safe_to_enable = bool(str(business_id or "").strip()) and due_count > 0 and skipped_no_access == 0
    scope = str(business_id or "").strip()
    first_cycle_verification = _social_worker_first_cycle_verification(
        external_publish_count,
        controlled_count,
        manual_count,
        skipped_no_access,
        scope,
    )
    runtime_alignment = _social_launch_runtime_alignment(scope)
    return {
        "business_id": scope,
        "status": status,
        "safe_to_enable_scoped_dispatch": safe_to_enable,
        "channel_readiness": channel_readiness,
        "channel_summary": channel_summary,
        "dispatch_preview": dispatch_preview,
        "dispatch_readiness": readiness,
        "blocked_api_channels": blocked_api_channels,
        "controlled_channels": controlled_channels,
        "recommended_env": {
            "dispatch": _dispatch_preview_recommended_env(str(business_id or "").strip()),
            "metrics": _metrics_preview_recommended_env(str(business_id or "").strip()),
        },
        "safety": {
            "approval_required": True,
            "scoped_dispatch_required": True,
            "external_publish_only_after_approval": True,
            "browser_final_click_allowed": False,
            "maps_are_supervised_or_manual": True,
        },
        "summary": {
            "due_posts": due_count,
            "api_due_posts": external_publish_count,
            "controlled_due_posts": controlled_count,
            "manual_due_posts": manual_count,
            "blocked_api_channels": len(blocked_api_channels),
            "controlled_channels": len(controlled_channels),
            "skipped_no_access": skipped_no_access,
        },
        "first_cycle_verification": first_cycle_verification,
        "runtime_alignment": runtime_alignment,
        "launch_runbook": _social_launch_runbook(
            status,
            scope,
            due_count,
            external_publish_count,
            controlled_count,
            manual_count,
            skipped_no_access,
            first_cycle_verification,
        ),
        "message_ru": _social_launch_preflight_message(status, True),
        "message_en": _social_launch_preflight_message(status, False),
        "next_action_ru": _social_launch_preflight_next_action(status, scope, True),
        "next_action_en": _social_launch_preflight_next_action(status, scope, False),
    }


def _social_launch_preflight_message(status: str, is_ru: bool) -> str:
    if status == "ready_for_api_dispatch":
        return (
            "Есть due API-публикации: scoped worker сможет отправить их только после уже полученного approval."
            if is_ru
            else "Due API posts exist: the scoped worker can publish them only after existing approval."
        )
    if status == "ready_for_controlled_handoff":
        return (
            "Есть due публикации для карт: worker создаст controlled/manual задачи без финального клика."
            if is_ru
            else "Due map posts exist: the worker will create controlled/manual tasks without the final click."
        )
    if status == "manual_or_connection_needed":
        return (
            "Due-посты есть, но сейчас они требуют ручного fallback или подключения каналов."
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
    if status in {"ready_for_api_dispatch", "ready_for_controlled_handoff", "manual_or_connection_needed"}:
        return (
            f"Для первого запуска включайте worker только с SOCIAL_POST_DISPATCH_BUSINESS_ID={business_id} и проверьте логи после одного цикла."
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
        "Следующий шаг в интерфейсе: подготовить каналы, проверить preview, утвердить и поставить посты в расписание."
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
        raise PermissionError("Для создания controlled-задачи нужно явное подтверждение")
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
        raise ValueError("Controlled-задача доступна только для Яндекс/2ГИС")
    if status == "published":
        raise ValueError("Публикация уже опубликована")
    if not post.get("approved_at") and status not in {"approved", "queued", "needs_supervised_publish", "needs_manual_publish"}:
        raise PermissionError("Перед controlled-размещением нужно подтверждение человека")
    if not _social_post_has_text(post):
        raise ValueError("Перед controlled-размещением нужно заполнить текст")

    automation_task_id = str(post.get("automation_task_id") or "").strip() or _new_id()
    metadata = _json_dict(post.get("metadata_json"))
    metadata.update(_supervised_publish_metadata(cursor, post, automation_task_id))
    supervised_state = _supervised_publish_state(post)
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
    if ledger_id:
        metadata = _json_dict(updated.get("metadata_json"))
        metadata["agent_action_ledger_id"] = ledger_id
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


def mark_manual_published(user_id: str, post_id: str, provider_post_url: str = "", provider_post_id: str = "") -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_social_post_tables(cursor)
        post = _load_post_for_user(cursor, user_id, post_id)
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
            raise ValueError("Этот пост не является controlled/browser-use публикацией")
        if status not in {"needs_supervised_publish", "needs_manual_publish", "queued"}:
            raise ValueError("Controlled fallback доступен только для запланированных или controlled публикаций")

        blocked_reason = str(reason or "").strip()
        if not blocked_reason:
            blocked_reason = (
                "Контролируемое размещение заблокировано: нужен ручной fallback "
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
        if normalized_event_type not in {"lead", "inquiry", "comment", "share", "click", "like", "view"}:
            raise ValueError("Неподдерживаемый тип события")
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
        for post in posts:
            attribution_metrics = _attribution_metrics_for_post(cursor, str(post.get("id") or ""))
            provider_metrics = _collect_provider_metrics_for_post(cursor, post)
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
            f"Добавьте SOCIAL_POST_DISPATCH_BUSINESS_ID={business_scope}, иначе worker не начнёт внешние действия."
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
        "Runtime совпадает с текущим бизнесом: после approval и расписания worker может выполнить первый цикл."
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
            post = publish_social_post(owner_id, post_id)
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
    }


def run_scoped_social_dispatch_once(
    user_id: str,
    business_id: str,
    batch_size: int = 10,
    approved: bool = False,
) -> dict[str, Any]:
    if not approved:
        raise PermissionError("Для запуска первого цикла публикаций нужно явное подтверждение")
    normalized_business_id = str(business_id or "").strip()
    if not normalized_business_id:
        raise ValueError("Бизнес не выбран")
    clean_batch_size = max(1, min(int(batch_size or 10), 50))
    preflight = get_social_launch_preflight(user_id, normalized_business_id, batch_size=clean_batch_size)
    summary = preflight.get("summary") if isinstance(preflight.get("summary"), dict) else {}
    if int(summary.get("skipped_no_access") or 0) > 0:
        raise PermissionError("Есть due-посты вне доступа текущего пользователя; проверьте business scope")
    dispatch_result = dispatch_due_social_posts(
        batch_size=clean_batch_size,
        business_id=normalized_business_id,
    )
    return {
        "approved": True,
        "business_id": normalized_business_id,
        "batch_size": clean_batch_size,
        "preflight": preflight,
        "dispatch_result": dispatch_result,
        "external_publish_only_after_approval": True,
        "browser_final_click_allowed": False,
        "maps_are_supervised_or_manual": True,
        "message_ru": _social_dispatch_once_message(dispatch_result, True),
        "message_en": _social_dispatch_once_message(dispatch_result, False),
    }


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
            f"controlled {supervised}, вручную {manual}, ошибок {failed}."
        )
    return (
        f"First scoped cycle finished: picked {picked}, published {published}, "
        f"controlled {supervised}, manual {manual}, failed {failed}."
    )


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
        "safety_notes_ru": [
            "Внешние публикации уходят только из approved/queued постов.",
            "Яндекс/2ГИС остаются controlled/manual: финальный клик публикации не выполняется worker.",
            "Dry-run ничего не отправляет наружу и нужен для проверки первого цикла.",
        ],
        "safety_notes_en": [
            "External publishing runs only for approved/queued posts.",
            "Yandex/2GIS stay controlled/manual: the worker does not perform the final publish click.",
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
            "label_ru": "API: публикация после approval",
            "label_en": "API: publish after approval",
            "count": int(external_publish_count or 0),
            "external_publish": True,
            "requires_approval": True,
            "stop_before_final_publish": False,
            "expected_status_ru": "published или failed с понятной причиной",
            "expected_status_en": "published or failed with a clear reason",
            "description_ru": "Telegram/VK/Google/Meta уйдут наружу только если пост уже approved, queued и канал готов.",
            "description_en": "Telegram/VK/Google/Meta publish externally only when the post is already approved, queued, and the channel is ready.",
        },
        {
            "key": "maps_controlled_without_final_click",
            "label_ru": "Карты: controlled/manual без финального клика",
            "label_en": "Maps: controlled/manual without final click",
            "count": int(controlled_count or 0),
            "external_publish": False,
            "requires_approval": True,
            "stop_before_final_publish": True,
            "expected_status_ru": "needs_supervised_publish",
            "expected_status_en": "needs_supervised_publish",
            "description_ru": "Яндекс/2ГИС получают supervised task для OpenClaw, но финальная публикация остаётся за человеком.",
            "description_en": "Yandex/2GIS receive an OpenClaw supervised task, while final publishing stays human-controlled.",
        },
        {
            "key": "manual_handoff_or_connection",
            "label_ru": "Ручной fallback или подключение канала",
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
                "label_ru": "Ручной fallback",
                "label_en": "Manual fallback",
                "expected_ru": "needs_manual_publish с инструкцией и copy-ready текстом",
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
            "Если есть manual/supervised: завершить размещение из карточки поста и отметить ссылку/ID.",
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
            "Есть due карты: worker создаст controlled/manual задачи, финальная публикация остаётся за человеком."
            if is_ru
            else "Due map posts exist: the worker will create controlled/manual tasks, while final publishing stays human-controlled."
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
            "Можно запускать scoped dispatch: карты перейдут в controlled/manual задачи без финального клика."
            if is_ru
            else "Scoped dispatch can run: map posts will move to controlled/manual tasks without a final click."
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
    can_launch = bool(scope) and due > 0 and skipped == 0
    return {
        "ready": can_launch,
        "scope": scope,
        "status": str(status or "").strip(),
        "title_ru": "Runbook первого цикла dispatch",
        "title_en": "First-cycle dispatch runbook",
        "summary_ru": (
            f"Due {due}: API {external}, controlled {controlled}, manual {manual}. "
            f"Scope: {scope or 'не задан'}."
        ),
        "summary_en": (
            f"Due {due}: API {external}, controlled {controlled}, manual {manual}. "
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
            False,
        ),
        "success_criteria_ru": _social_launch_runbook_success_criteria(external, controlled, manual, skipped, True),
        "success_criteria_en": _social_launch_runbook_success_criteria(external, controlled, manual, skipped, False),
        "blocked_reason_ru": _social_launch_runbook_blocked_reason(scope, due, skipped, True),
        "blocked_reason_en": _social_launch_runbook_blocked_reason(scope, due, skipped, False),
    }


def _social_launch_runbook_steps(
    scope: str,
    due_count: int,
    external_publish_count: int,
    controlled_count: int,
    manual_count: int,
    skipped_no_access: int,
    log_filter: str,
    is_ru: bool,
) -> list[str]:
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
            "Для Яндекс/2ГИС проверьте supervised/manual задачу: финальный клик не должен быть выполнен worker."
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


def _social_launch_runbook_blocked_reason(scope: str, due_count: int, skipped_no_access: int, is_ru: bool) -> str:
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
    for item in picked:
        post_id = str(item.get("id") or "").strip()
        try:
            owner_id = _owner_id_for_business(str(item.get("business_id") or "").strip())
            if not owner_id:
                raise RuntimeError("business owner not found")
            payload = collect_social_post_metrics(owner_id, post_id=post_id)
            collected += int(payload.get("collected") or 0)
        except Exception:
            failed += 1
            errors.append({"id": post_id, "error": str(sys.exc_info()[1])})
    return {
        "picked": len(picked),
        "collected": collected,
        "failed": failed,
        "errors": errors,
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
        return {
            "recommendation": recommendation,
            "proposed_changes": proposed_changes,
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
            "recommendation": recommendation_payload,
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
            "recommendation": recommendation_payload.get("recommendation") or {},
            "proposed_changes": proposed_changes,
        }
    except Exception:
        db.conn.rollback()
        raise sys.exc_info()[1]
    finally:
        db.close()


def _social_openclaw_browser_readiness(status: dict[str, Any] | None = None) -> dict[str, Any]:
    capability_status = status if isinstance(status, dict) else openclaw_browser_capability_status()
    ready = bool(capability_status.get("ready"))
    return {
        "ready": ready,
        "status": "ready" if ready else "manual_fallback",
        "capability": str(capability_status.get("capability") or "social.post.publish_supervised_browser").strip(),
        "action_ref": str(capability_status.get("action_ref") or "").strip(),
        "source": str(capability_status.get("source") or "").strip(),
        "provider_status": str(capability_status.get("status") or "").strip(),
        "reason": str(capability_status.get("reason") or "").strip(),
        "browser_final_click_allowed": False,
        "message_ru": (
            "OpenClaw browser-use готов: Яндекс/2ГИС можно вести как controlled-задачи без финального клика."
            if ready
            else "OpenClaw browser-use не подтверждён: Яндекс/2ГИС останутся в ручном fallback."
        ),
        "message_en": (
            "OpenClaw browser-use is ready: Yandex/2GIS can use controlled tasks without the final click."
            if ready
            else "OpenClaw browser-use is not confirmed: Yandex/2GIS will stay in manual fallback."
        ),
        "next_action_ru": (
            "Создайте controlled задачу у поста карты и проверьте preview перед финальным размещением."
            if ready
            else "Проверьте capability catalog/OpenClaw настройки или используйте ручное размещение."
        ),
        "next_action_en": (
            "Create a controlled task on the map post and review the preview before final placement."
            if ready
            else "Check the capability catalog/OpenClaw settings or use manual placement."
        ),
    }


def openclaw_browser_capability_status(fetcher: Any = None) -> dict[str, Any]:
    env_value = str(os.getenv("OPENCLAW_BROWSER_USE_ENABLED") or os.getenv("OPENCLAW_BROWSER_USE_AVAILABLE") or "").strip().lower()
    if env_value in {"1", "true", "yes", "on"}:
        return {
            "ready": True,
            "source": "env_override",
            "status": "available",
            "reason": "browser_use_enabled_by_env",
            "action_ref": "openclaw.browser.supervised_publish",
            "capability": "social.post.publish_supervised_browser",
        }
    if env_value in {"0", "false", "no", "off"}:
        return {
            "ready": False,
            "source": "env_override",
            "status": "disabled",
            "reason": "browser_use_disabled_by_env",
            "action_ref": "",
            "capability": "social.post.publish_supervised_browser",
        }
    if not fetcher and not (os.getenv("OPENCLAW_CAPABILITY_CATALOG_URL") or os.getenv("OPENCLAW_BASE_URL")):
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
        browser_ready = publish_mode == "openclaw_browser" and openclaw_browser_available()
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


def _dispatch_preview_action_label(action: str, is_ru: bool) -> str:
    clean = str(action or "").strip()
    if clean == "publish_api":
        return "API-публикация" if is_ru else "API publish"
    if clean == "create_supervised_task":
        return "Controlled task" if is_ru else "Controlled task"
    if clean == "manual_handoff":
        return "Ручной fallback" if is_ru else "Manual fallback"
    return "Без действия" if is_ru else "No action"


def _dispatch_preview_reason_label(reason: str, is_ru: bool) -> str:
    clean = str(reason or "").strip()
    if clean == "channel_ready":
        return "Канал готов, есть approval и расписание." if is_ru else "Channel is ready, approved, and scheduled."
    if clean == "openclaw_browser_ready":
        return "OpenClaw browser-use доступен; будет создана supervised задача." if is_ru else "OpenClaw browser-use is available; a supervised task will be created."
    if clean == "openclaw_browser_unavailable":
        return "OpenClaw browser-use не подтверждён; нужен ручной fallback." if is_ru else "OpenClaw browser-use is not confirmed; manual fallback is required."
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
            "Worker создаст controlled задачу и не нажмёт финальную кнопку публикации."
            if is_ru
            else "The worker will create a controlled task and will not click the final publish button."
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
            "manual_checklist_ru": manual_handoff["checklist_ru"],
            "manual_checklist_en": manual_handoff["checklist_en"],
            "manual_handoff": manual_handoff,
            "stop_before_final_publish": True,
            "final_publish_policy": "human_final_click_required",
            "safety_contract": safety_contract,
            "fallback_reasons": ["captcha", "login_required", "changed_ui", "browser_capability_unavailable"],
            "openclaw_capability_status": capability_status,
        },
    }


def _supervised_publish_state(post: dict[str, Any]) -> dict[str, str | None]:
    publish_mode = str(post.get("publish_mode") or "").strip()
    browser_ready = publish_mode == "openclaw_browser" and openclaw_browser_available()
    return {
        "status": "needs_supervised_publish" if browser_ready else "needs_manual_publish",
        "last_error": None if browser_ready else "OpenClaw browser-use недоступен; используйте ручное контролируемое размещение.",
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


def _publish_telegram_post(cursor: Any, post: dict[str, Any]) -> dict[str, Any]:
    business = _load_business_publish_context(cursor, str(post.get("business_id") or ""))
    bot_token = decode_telegram_bot_token(business.get("telegram_bot_token"))
    chat_id = str(business.get("telegram_chat_id") or "").strip()
    if not bot_token or not chat_id:
        return {
            "status": "needs_manual_publish",
            "last_error": "Для Telegram нужны telegram_bot_token и telegram_chat_id бизнеса.",
            "metadata_json": {"provider_status": "telegram_connection_missing"},
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
                "metadata_json": {"provider_status": "telegram_published", "telegram_response": parsed},
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
    bot_token = decode_telegram_bot_token(business.get("telegram_bot_token"))
    chat_id = str(business.get("telegram_chat_id") or "").strip()
    checks = _telegram_connection_checks(bool(bot_token), bool(chat_id))
    if not bot_token or not chat_id:
        return _api_channel_preflight_result(
            "telegram",
            False,
            "missing_keys",
            checks,
            "Для Telegram нужны telegram_bot_token и telegram_chat_id бизнеса.",
            "Telegram needs business telegram_bot_token and telegram_chat_id.",
        )
    bot_probe = _telegram_safe_api_probe(bot_token, "getMe")
    chat_probe = _telegram_safe_api_probe(bot_token, "getChat", {"chat_id": chat_id})
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
    ]
    ready = bool(bot_probe.get("ok")) and bool(chat_probe.get("ok"))
    return _api_channel_preflight_result(
        "telegram",
        ready,
        "ready" if ready else "live_probe_failed",
        checks,
        "Telegram готов к API-публикации после approval." if ready else "Telegram ключи заполнены, но live-проверка не прошла.",
        "Telegram is ready for API publishing after approval." if ready else "Telegram keys exist, but live preflight failed.",
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
        return {"ok": True, "status": "ok"}
    return _api_probe_error("telegram", status_code, str(parsed.get("description") or body or "Telegram API error"))


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
            "wall.get прошёл; wall.post всё равно выполняется только после approval" if read_probe.get("ok") else str(read_probe.get("error_ru") or "VK live-проверка не прошла"),
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
        "VK готов к API-публикации после approval." if ready else "VK binding найден, но live-проверка API не прошла.",
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


def _api_channel_preflight_result(
    platform: str,
    ready: bool,
    status: str,
    checks: list[dict[str, Any]],
    message_ru: str,
    message_en: str,
) -> dict[str, Any]:
    return {
        "platform": platform,
        "platform_label": platform_label(platform),
        "publish_mode": "api",
        "ready": bool(ready),
        "status": str(status or "").strip(),
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
    select_parts = ["id", "name"]
    for column in ("telegram_bot_token", "telegram_chat_id"):
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
        return "VK token найден, но в permissions/scope нет wall.post."
    if normalized == "missing_binding":
        return "Для VK нужен group_id или owner_id группы/страницы."
    if normalized == "missing_connection":
        return "VK аккаунт/группа не подключены."
    return "Для VK нужны access_token и group_id/owner_id с правом wall.post."


def _collect_provider_metrics_for_post(cursor: Any, post: dict[str, Any]) -> dict[str, Any]:
    platform = str(post.get("platform") or "").strip()
    if platform == "vk":
        return _collect_vk_post_metrics(cursor, post)
    return {"source": "manual_attribution_only", "provider": platform or "unknown"}


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
    telegram_token_present = bool(decode_telegram_bot_token(business.get("telegram_bot_token")))
    telegram_chat_present = bool(str(business.get("telegram_chat_id") or "").strip())
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
            _telegram_connection_checks(telegram_token_present, telegram_chat_present),
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
) -> dict[str, Any]:
    return {
        "platform": platform,
        "platform_label": platform_label(platform),
        "publish_mode": publish_mode,
        "ready": bool(ready),
        "status": status,
        "message_ru": _channel_readiness_message(platform, status, True),
        "message_en": _channel_readiness_message(platform, status, False),
        "next_action_ru": _channel_readiness_next_action(platform, status, True),
        "next_action_en": _channel_readiness_next_action(platform, status, False),
        "setup_steps_ru": _channel_readiness_setup_steps(platform, status, True),
        "setup_steps_en": _channel_readiness_setup_steps(platform, status, False),
        "missing_fields": _channel_readiness_missing_fields(platform, status),
        "settings_path": _channel_readiness_settings_path(platform),
        "connection_checks": connection_checks or [],
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


def _telegram_connection_checks(token_present: bool, chat_present: bool) -> list[dict[str, Any]]:
    return [
        _connection_check(
            "telegram_bot_token",
            token_present,
            "Токен бота",
            "Bot token",
            "токен найден" if token_present else "добавьте telegram_bot_token",
            "token found" if token_present else "add telegram_bot_token",
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
            "проверится при первом publish" if token_present and chat_present else "проверка невозможна без токена и chat_id",
            "checked on first publish" if token_present and chat_present else "cannot check without token and chat_id",
            "deferred" if token_present and chat_present else "blocked",
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
            "capability подтверждена" if browser_ready else "capability не подтверждена, будет ручной fallback",
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
    if status == "ready":
        return f"{label}: готов к публикации после approval." if is_ru else f"{label}: ready to publish after approval."
    if status == "supervised_ready":
        return (
            f"{label}: доступно контролируемое размещение через OpenClaw."
            if is_ru
            else f"{label}: supervised placement through OpenClaw is available."
        )
    if status == "manual_fallback":
        return (
            f"{label}: OpenClaw browser-use не подтверждён, будет ручной fallback."
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
    return f"{label}: нужны ключи или настройки канала." if is_ru else f"{label}: keys or channel settings are required."


def _channel_readiness_next_action(platform: str, status: str, is_ru: bool) -> str:
    platform_key = str(platform or "").strip()
    status_key = str(status or "").strip()
    if status_key == "ready":
        return (
            "После проверки текста поставьте пост в расписание."
            if is_ru
            else "After reviewing copy, queue the post on schedule."
        )
    if status_key == "supervised_ready":
        return (
            "Поставьте пост в расписание: LocalOS создаст controlled задачу, финальная кнопка останется за человеком."
            if is_ru
            else "Queue the post: LocalOS will create a controlled task and the final click remains human-owned."
        )
    if status_key == "manual_fallback":
        return (
            "Используйте copy-ready текст и отметьте публикацию размещённой после ручного действия."
            if is_ru
            else "Use the copy-ready text and mark the post as published after the manual step."
        )
    if platform_key == "telegram" and status_key == "missing_keys":
        return (
            "Добавьте telegram_bot_token и telegram_chat_id в настройках бизнеса."
            if is_ru
            else "Add telegram_bot_token and telegram_chat_id in business settings."
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
            "Подключите Google Business Profile и выберите location для публикации."
            if is_ru
            else "Connect Google Business Profile and select the location for publishing."
        )
    if platform_key in {"instagram", "facebook"}:
        if status_key == "adapter_pending":
            return (
                "Пока используйте manual handoff; включайте API только после проверки Meta permissions."
                if is_ru
                else "Use manual handoff for now; enable API only after Meta permissions are verified."
            )
        if status_key == "missing_permissions":
            return (
                "Проверьте Meta Graph permissions и привязку Page/IG business account."
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


def _channel_readiness_setup_steps(platform: str, status: str, is_ru: bool) -> list[str]:
    platform_key = str(platform or "").strip()
    status_key = str(status or "").strip()
    if status_key == "ready":
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
            "Откройте controlled task и подтвердите финальный шаг вручную.",
        ] if is_ru else [
            "Review copy and media.",
            "Queue the post on schedule.",
            "Open the controlled task and confirm the final step manually.",
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
            "Выберите business location.",
            "Проверьте, что Google publish доступен для аккаунта.",
        ] if is_ru else [
            "Connect Google Business Profile.",
            "Select the business location.",
            "Check that Google publishing is available for the account.",
        ]
    if platform_key in {"instagram", "facebook"}:
        if status_key == "adapter_pending":
            return [
                "Оставьте канал в manual handoff.",
                "Проверьте Meta Page/IG business binding.",
                "Включайте API publish только после подтверждения permissions.",
            ] if is_ru else [
                "Keep the channel in manual handoff.",
                "Verify Meta Page/IG business binding.",
                "Enable API publish only after permissions are confirmed.",
            ]
        return [
            "Подключите Meta account.",
            "Выберите Page или Instagram business account.",
            "Проверьте permissions для публикации.",
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
        return "/dashboard/settings?focus=channels"
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
        "safe_to_apply_recommendation": status in {"ready_from_leads", "early_signals_only"},
    }


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
            "Нажмите «Предложить изменения», проверьте preview и применяйте только после подтверждения."
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
            "Сначала завершите manual/supervised публикации или исправьте failed-каналы."
            if is_ru
            else "Finish manual/supervised posts or recover failed channels first."
        )
    return (
        "Подготовьте, подтвердите и опубликуйте первые посты, затем соберите реакции."
        if is_ru
        else "Prepare, approve, and publish the first posts, then collect reactions."
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
    return {
        "winning_topics": winning_topics,
        "weak_channels": weak_channels,
        "no_result_topics": no_result_topics,
        "cta_suggestions": _cta_suggestions(winning_topics, weak_channels, no_result_topics),
        "frequency_suggestions": _frequency_suggestions(winning_topics, weak_channels, no_result_topics),
    }


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
    return data


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
            }
        )
        return base

    if status == "needs_supervised_publish":
        base.update(
            {
                "tone": "warning",
                "title_ru": f"{provider_label}: нужно контролируемое размещение",
                "title_en": f"{provider_label}: supervised placement needed",
                "summary_ru": "LocalOS подготовил controlled/manual задачу; финальный клик публикации остаётся за человеком.",
                "summary_en": "LocalOS prepared a controlled/manual task; the final publish click stays with a human.",
                "next_action_ru": "Откройте контролируемое размещение, проверьте предпросмотр и отметьте результат.",
                "next_action_en": "Open supervised placement, review the preview, and record the result.",
            }
        )
        return base

    if status == "needs_manual_publish":
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
