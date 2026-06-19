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
            "channel_readiness": _build_channel_readiness(cursor, str(plan.get("business_id") or "")),
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


def publish_social_post(user_id: str, post_id: str) -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_social_post_tables(cursor)
        post = _load_post_for_user(cursor, user_id, post_id)
        if not post.get("approved_at") and str(post.get("status") or "") not in {"approved", "queued"}:
            raise PermissionError("Перед внешней публикацией нужно подтверждение человека")
        platform = str(post.get("platform") or "").strip()
        publish_mode = str(post.get("publish_mode") or "").strip()
        metadata = _json_dict(post.get("metadata_json"))
        if platform in BROWSER_OR_MANUAL_PLATFORMS:
            automation_task_id = str(post.get("automation_task_id") or "").strip() or _new_id()
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
        if normalized_event_type not in {"lead", "inquiry", "comment", "share", "click"}:
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
        db.conn.commit()
        return {
            "event": event,
            "post": post,
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
            cursor.execute(
                """
                INSERT INTO social_post_metrics (
                    id, social_post_id, metric_date, views, impressions, reach, likes, comments, shares, clicks, inquiries, leads, raw_json, captured_at
                )
                VALUES (%s, %s, %s, 0, 0, 0, 0, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (social_post_id, metric_date)
                DO UPDATE SET
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
                    attribution_metrics.get("comments", 0),
                    attribution_metrics.get("shares", 0),
                    attribution_metrics.get("clicks", 0),
                    attribution_metrics.get("inquiries", 0),
                    attribution_metrics.get("leads", 0),
                    _json_dumps({"collector": "manual_attribution_v1", "attribution": attribution_metrics}),
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


def dispatch_due_social_posts(batch_size: int = 20) -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    picked: list[dict[str, Any]] = []
    try:
        ensure_social_post_tables(cursor)
        cursor.execute(
            """
            SELECT sp.id, sp.business_id, sp.platform, sp.status, sp.scheduled_for
            FROM social_posts sp
            WHERE sp.status = 'queued'
              AND sp.approved_at IS NOT NULL
              AND COALESCE(sp.scheduled_for, NOW()) <= NOW()
            ORDER BY sp.scheduled_for ASC NULLS FIRST, sp.updated_at ASC
            LIMIT %s
            """,
            (max(1, min(int(batch_size or 20), 200)),),
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
    }


def preview_due_social_post_dispatch(user_id: str, batch_size: int = 20) -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_social_post_tables(cursor)
        cursor.execute(
            """
            SELECT sp.*
            FROM social_posts sp
            WHERE sp.status = 'queued'
              AND sp.approved_at IS NOT NULL
              AND COALESCE(sp.scheduled_for, NOW()) <= NOW()
            ORDER BY sp.scheduled_for ASC NULLS FIRST, sp.updated_at ASC
            LIMIT %s
            """,
            (max(1, min(int(batch_size or 20), 200)),),
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
        readiness = _dispatch_preview_readiness(preview_items, counts, skipped)
        return {
            "dry_run": True,
            "picked": len(preview_items),
            "skipped_no_access": skipped,
            "batch_size": max(1, min(int(batch_size or 20), 200)),
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


def collect_due_social_post_metrics(batch_size: int = 50) -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    picked: list[dict[str, Any]] = []
    try:
        ensure_social_post_tables(cursor)
        cursor.execute(
            """
            SELECT sp.id, sp.business_id
            FROM social_posts sp
            LEFT JOIN social_post_metrics m
              ON m.social_post_id = sp.id
             AND m.metric_date = CURRENT_DATE
            WHERE sp.status = 'published'
              AND m.id IS NULL
            ORDER BY sp.published_at ASC NULLS LAST, sp.updated_at ASC
            LIMIT %s
            """,
            (max(1, min(int(batch_size or 50), 500)),),
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
    }


def recommend_next_plan_from_social_posts(user_id: str, plan_id: str) -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_social_post_tables(cursor)
        _load_plan_for_user(cursor, user_id, plan_id)
        posts_payload = list_social_posts_for_plan(user_id, plan_id)
        performance_rows = _social_plan_performance_rows(cursor, plan_id)
        proposed_changes = _build_next_plan_changes(performance_rows)
        recommendation = dict(posts_payload.get("recommendation") or {})
        recommendation.update(
            _build_social_learning_insights(
                performance_rows,
                list(posts_payload.get("posts") or []),
            )
        )
        return {
            "recommendation": recommendation,
            "proposed_changes": proposed_changes,
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
        browser_ready = publish_mode == "openclaw_browser" and openclaw_browser_available()
        return {
            **item,
            "dispatch_action": "create_supervised_task" if browser_ready else "manual_handoff",
            "would_status": "needs_supervised_publish" if browser_ready else "needs_manual_publish",
            "reason": "openclaw_browser_ready" if browser_ready else "openclaw_browser_unavailable",
            "external_publish": False,
            "approval_required": True,
            "stop_before_final_publish": True,
        }
    if publish_mode != "api":
        return {
            **item,
            "dispatch_action": "manual_handoff",
            "would_status": "needs_manual_publish",
            "reason": "publish_mode_not_api",
            "external_publish": False,
            "approval_required": True,
        }
    queue_block = _queue_preflight_block(cursor, post)
    if queue_block:
        return {
            **item,
            "dispatch_action": "manual_handoff",
            "would_status": str(queue_block.get("status") or "needs_manual_publish"),
            "reason": str(queue_block.get("last_error") or "channel_not_ready"),
            "external_publish": False,
            "approval_required": True,
            "metadata_json": queue_block.get("metadata_json") or {},
        }
    return {
        **item,
        "dispatch_action": "publish_api",
        "would_status": "published_or_failed",
        "reason": "channel_ready",
        "external_publish": True,
        "approval_required": True,
    }


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
    return {
        "automation_task_id": automation_task_id,
        "openclaw_task": task_payload,
        "supervised_publish": {
            "mode": str(post.get("publish_mode") or "manual"),
            "platform": platform,
            "platform_label": platform_label(platform),
            "target_url": target.get("target_url", ""),
            "target_url_source": target.get("target_url_source", ""),
            "instruction_ru": "Открыть площадку, вставить текст и медиа, показать предпросмотр, остановиться перед финальной публикацией до подтверждения.",
            "instruction_en": "Open the platform, fill text and media, show preview, and stop before final publish until explicit approval.",
            "stop_before_final_publish": True,
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
                return {
                    "status": "failed",
                    "last_error": str(parsed.get("description") or body or f"Telegram HTTP {status_code}")[:1000],
                    "metadata_json": {"provider_status": "telegram_api_error", "status_code": status_code},
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
        return {
            "status": "failed",
            "last_error": body or str(error),
            "metadata_json": {"provider_status": "telegram_http_error"},
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
        VALUES (%s, %s, %s, 0, 0, 0, 0, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (social_post_id, metric_date)
        DO UPDATE SET
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
        return {"comments": 0, "shares": 0, "clicks": 0, "inquiries": 0, "leads": 0}
    cursor.execute(
        """
        SELECT event_type, COALESCE(SUM(value), 0) AS total
        FROM social_post_attribution_events
        WHERE social_post_id = %s
        GROUP BY event_type
        """,
        (post_id,),
    )
    result = {"comments": 0, "shares": 0, "clicks": 0, "inquiries": 0, "leads": 0}
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
    telegram_ready = bool(decode_telegram_bot_token(business.get("telegram_bot_token"))) and bool(
        str(business.get("telegram_chat_id") or "").strip()
    )
    vk_account = _find_active_external_account(cursor, business_id, ("vk", "vk_group", "vk_business"))
    vk_auth = _external_account_auth_data(vk_account)
    vk_binding = _vk_publish_binding(vk_account, vk_auth)
    google_account = _find_active_external_account(cursor, business_id, ("google_business",))
    meta_account = _find_active_external_account(cursor, business_id, ("meta", "facebook", "instagram"))
    meta_auth = _external_account_auth_data(meta_account)
    instagram_readiness = _meta_channel_readiness(meta_account, meta_auth, "instagram")
    facebook_readiness = _meta_channel_readiness(meta_account, meta_auth, "facebook")
    browser_ready = openclaw_browser_available()
    return [
        _channel_readiness("telegram", "api", telegram_ready, "ready" if telegram_ready else "missing_keys"),
        _channel_readiness("vk", "api", bool(vk_binding.get("ready")), str(vk_binding.get("status") or "missing_keys")),
        _channel_readiness("google_business", "api", bool(google_account), "ready" if google_account else "missing_connection"),
        _channel_readiness(
            "instagram",
            "api",
            bool(instagram_readiness.get("ready")),
            str(instagram_readiness.get("status") or "missing_connection"),
        ),
        _channel_readiness(
            "facebook",
            "api",
            bool(facebook_readiness.get("ready")),
            str(facebook_readiness.get("status") or "missing_connection"),
        ),
        _channel_readiness(
            "yandex_maps",
            "openclaw_browser" if browser_ready else "manual",
            browser_ready,
            "supervised_ready" if browser_ready else "manual_fallback",
        ),
        _channel_readiness(
            "two_gis",
            "openclaw_browser" if browser_ready else "manual",
            browser_ready,
            "supervised_ready" if browser_ready else "manual_fallback",
        ),
    ]


def _channel_readiness(platform: str, publish_mode: str, ready: bool, status: str) -> dict[str, Any]:
    return {
        "platform": platform,
        "platform_label": platform_label(platform),
        "publish_mode": publish_mode,
        "ready": bool(ready),
        "status": status,
        "message_ru": _channel_readiness_message(platform, status, True),
        "message_en": _channel_readiness_message(platform, status, False),
    }


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
    }


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
    return data


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
