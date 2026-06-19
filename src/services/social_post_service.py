from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import date, datetime, timezone
from typing import Any

from database_manager import DatabaseManager
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
            "recommendation": _build_plan_recommendation(posts),
        }
    finally:
        db.close()


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
        metadata["provider_status"] = "queued_for_native_adapter"
        metadata["provider_note"] = "API publish adapter requires connected account and channel-specific preflight."
        cursor.execute(
            """
            UPDATE social_posts
            SET status = 'queued',
                metadata_json = %s,
                last_error = NULL,
                updated_at = NOW()
            WHERE id = %s
            RETURNING *
            """,
            (_json_dumps(metadata), post_id),
        )
        updated = _serialize_social_post(cursor, cursor.fetchone())
        db.conn.commit()
        return updated
    except Exception:
        db.conn.rollback()
        raise sys.exc_info()[1]
    finally:
        db.close()


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
            cursor.execute(
                """
                INSERT INTO social_post_metrics (
                    id, social_post_id, metric_date, views, impressions, reach, likes, comments, shares, clicks, inquiries, leads, raw_json, captured_at
                )
                VALUES (%s, %s, %s, 0, 0, 0, 0, 0, 0, 0, 0, 0, %s, NOW())
                ON CONFLICT (social_post_id, metric_date)
                DO UPDATE SET captured_at = NOW()
                """,
                (_new_id(), post.get("id"), today, _json_dumps({"collector": "manual_or_adapter_pending"})),
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
