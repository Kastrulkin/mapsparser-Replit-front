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
        "key": "needs_supervised_publish",
        "label_ru": "Нужно контролируемое размещение",
        "label_en": "Needs supervised placement",
        "next_action_ru": "Открыть контролируемое размещение или передать человеку ручную инструкцию.",
        "next_action_en": "Open supervised placement or hand off manual instructions.",
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
        _load_plan_for_user(cursor, user_id, plan_id)
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
            metadata.update(_supervised_publish_metadata(post, automation_task_id))
            cursor.execute(
                """
                UPDATE social_posts
                SET status = 'needs_supervised_publish',
                    automation_task_id = %s,
                    metadata_json = %s,
                    last_error = NULL,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING *
                """,
                (automation_task_id, _json_dumps(metadata), post_id),
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
        db.conn.commit()
        return {
            "collected": len(posts),
            "posts": posts,
            "recommendation": _build_plan_recommendation(posts),
        }
    except Exception:
        db.conn.rollback()
        raise sys.exc_info()[1]
    finally:
        db.close()


def openclaw_browser_available(fetcher: Any = None) -> bool:
    env_value = str(os.getenv("OPENCLAW_BROWSER_USE_ENABLED") or os.getenv("OPENCLAW_BROWSER_USE_AVAILABLE") or "").strip().lower()
    if env_value in {"1", "true", "yes", "on"}:
        return True
    if env_value in {"0", "false", "no", "off"}:
        return False
    if not fetcher and not (os.getenv("OPENCLAW_CAPABILITY_CATALOG_URL") or os.getenv("OPENCLAW_BASE_URL")):
        return False
    try:
        catalog = get_openclaw_capability_catalog(fetcher=fetcher)
    except Exception:
        return False
    for action in catalog.get("actions", []) if isinstance(catalog, dict) else []:
        if not isinstance(action, dict):
            continue
        blob = " ".join(
            str(action.get(key) or "")
            for key in ("openclaw_action_ref", "title", "service", "localos_capability", "status")
        ).lower()
        if "browser" in blob and "available" in blob:
            return True
    return False


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
    if status in {"approved", "queued"} and platform in BROWSER_OR_MANUAL_PLATFORMS:
        return "start_supervised_publish"
    if status in {"approved", "queued"}:
        return "wait_for_api_publish"
    if status == "needs_supervised_publish":
        return "open_supervised_publish"
    if status == "needs_manual_publish":
        return "manual_publish"
    if status == "failed":
        return "retry_or_manual"
    if status == "published":
        return "collect_metrics"
    return "none"


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
    if status == "published":
        return "published"
    if status == "failed":
        return "failed"
    if platform in BROWSER_OR_MANUAL_PLATFORMS or status in {"needs_supervised_publish", "needs_manual_publish"}:
        return "needs_supervised_publish"
    if platform in API_PLATFORMS and status in {"approved", "queued", "publishing"}:
        return "api_ready"
    return "needs_review"


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


def _supervised_publish_metadata(post: dict[str, Any], automation_task_id: str) -> dict[str, Any]:
    platform = str(post.get("platform") or "").strip()
    return {
        "automation_task_id": automation_task_id,
        "supervised_publish": {
            "mode": str(post.get("publish_mode") or "manual"),
            "platform": platform,
            "platform_label": platform_label(platform),
            "instruction_ru": "Открыть площадку, вставить текст и медиа, показать предпросмотр, остановиться перед финальной публикацией до подтверждения.",
            "instruction_en": "Open the platform, fill text and media, show preview, and stop before final publish until explicit approval.",
        },
    }


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
    token = str(auth_data.get("access_token") or auth_data.get("token") or "").strip()
    group_id = str(auth_data.get("group_id") or auth_data.get("community_id") or account.get("external_id") or "").strip()
    owner_id = str(auth_data.get("owner_id") or "").strip()
    if not owner_id and group_id:
        clean_group_id = group_id[1:] if group_id.startswith("-") else group_id
        owner_id = f"-{clean_group_id}"
    if not token or not owner_id:
        return {
            "status": "needs_manual_publish",
            "last_error": "Для VK нужны access_token и group_id/owner_id с правом wall.post.",
            "metadata_json": {
                "provider_status": "vk_credentials_missing",
                "external_account_id": account.get("id"),
            },
        }
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
    return {
        "status": "queued",
        "metadata_json": {
            "provider_status": ready_status,
            "external_account_id": account.get("id"),
            "external_account_source": account.get("source"),
            "provider_note": "Adapter preflight passed; native provider publish worker is the next execution boundary.",
        },
    }


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
        "needs_supervised_publish": by_status.get("needs_supervised_publish", 0),
        "published": by_status.get("published", 0),
        "failed": by_status.get("failed", 0),
    }


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
