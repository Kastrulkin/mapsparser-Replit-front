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
        resp = outbound_urlopen(req, timeout=15)
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
    if platforms is None:
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
    rules_readiness = evaluate_social_post_publish_rules(cursor, post)
    blocking_rule = next(
        (
            item
            for item in rules_readiness
            if str(item.get("severity") or "").strip() == "blocking" and not bool(item.get("ready"))
        ),
        {},
    )
    if blocking_rule:
        return _queue_preflight_block_from_readiness(blocking_rule)
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

def evaluate_social_post_publish_rules(cursor: Any, post: dict[str, Any]) -> list[dict[str, Any]]:
    platform = str(post.get("platform") or "").strip()
    text = str(post.get("platform_text") or post.get("base_text") or "").strip()
    text_len = len(text)
    has_media = _social_post_has_selected_media(cursor, post)
    rules: list[dict[str, Any]] = []
    if platform == "telegram":
        if has_media and text_len > 1024:
            rules.append(
                _platform_rule_readiness(
                    platform,
                    ready=True,
                    status="text_will_follow_media",
                    label="Готово к отправке",
                    message="Фото выйдет первым, а длинный текст — следующим сообщением.",
                    action_label="Запланировать отправку",
                    severity="info",
                )
            )
        elif not has_media and text_len > 4096:
            rules.append(
                _platform_rule_readiness(
                    platform,
                    ready=False,
                    status="text_too_long",
                    label="Сократите текст",
                    message="Telegram принимает текстовый пост до 4096 символов.",
                    action_label="Сократить текст",
                    severity="blocking",
                )
            )
        else:
            rules.append(
                _platform_rule_readiness(
                    platform,
                    ready=True,
                    status="content_ready",
                    label="Готово к отправке",
                    message="Telegram готов принять этот текст.",
                    action_label="Запланировать отправку",
                    severity="info",
                )
            )
    elif platform == "instagram":
        if not has_media:
            rules.append(
                _platform_rule_readiness(
                    platform,
                    ready=False,
                    status="media_required",
                    label="Нужно фото",
                    message="Instagram не публикует текст без изображения.",
                    action_label="Добавить фото",
                    severity="blocking",
                )
            )
        elif not _social_post_media_is_instagram_ready(post):
            rules.append(
                _platform_rule_readiness(
                    platform,
                    ready=False,
                    status="media_format_required",
                    label="Нужен другой формат",
                    message="Для Instagram лучше выбрать JPEG-фото подходящего формата.",
                    action_label="Заменить фото",
                    severity="blocking",
                )
            )
        else:
            rules.append(
                _platform_rule_readiness(
                    platform,
                    ready=True,
                    status="content_ready",
                    label="Готово к отправке",
                    message="Фото и текст подходят для Instagram.",
                    action_label="Запланировать отправку",
                    severity="info",
                )
            )
    elif platform in {"yandex_maps", "two_gis"}:
        rules.append(
            _platform_rule_readiness(
                platform,
                ready=True,
                status="manual_or_supervised",
                label="Будет размещено вручную",
                message=f"{platform_label(platform)} размещается через контролируемое или ручное действие.",
                action_label="Открыть размещение",
                severity="info",
            )
        )
    elif platform in {"google_business"} and not has_media:
        rules.append(
            _platform_rule_readiness(
                platform,
                ready=True,
                status="media_recommended",
                label="Фото лучше добавить",
                message="Для карт лучше добавить фото входа, интерьера, услуги или результата.",
                action_label="Выбрать фото",
                severity="warning",
            )
        )
    elif platform in {"vk", "facebook"} and not has_media:
        rules.append(
            _platform_rule_readiness(
                platform,
                ready=True,
                status="media_optional",
                label="Фото можно добавить",
                message=f"{platform_label(platform)} может принять текст, но фото повысит заметность публикации.",
                action_label="Выбрать фото",
                severity="info",
            )
        )
    return rules

def _platform_rule_readiness(
    platform: str,
    *,
    ready: bool,
    status: str,
    label: str,
    message: str,
    action_label: str,
    severity: str,
) -> dict[str, Any]:
    return {
        "schema": "localos_social_platform_rule_readiness_v1",
        "platform": str(platform or "").strip(),
        "platform_label": platform_label(platform),
        "ready": bool(ready),
        "status": str(status or "").strip(),
        "label": str(label or "").strip(),
        "message": str(message or "").strip(),
        "message_en": str(message or "").strip(),
        "action_label": str(action_label or "").strip(),
        "severity": str(severity or "info").strip(),
        "user_fixable": str(severity or "").strip() == "blocking",
    }

def _queue_preflight_block_from_readiness(readiness: dict[str, Any]) -> dict[str, Any]:
    platform = str(readiness.get("platform") or "").strip()
    status = str(readiness.get("status") or "platform_rule_blocked").strip()
    message = str(readiness.get("message") or readiness.get("label") or "").strip()
    review_statuses = {"caption_too_long", "text_too_long", "media_required", "media_format_required"}
    return {
        "status": "needs_review" if status in review_statuses else "needs_manual_publish",
        "last_error": message or _queue_preflight_error(platform, status),
        "metadata_json": {
            "queue_preflight_status": status,
            "provider_status": status,
            "queue_preflight_ready": False,
            "platform_rule_readiness": readiness,
            "queue_preflight_message_ru": message,
            "queue_preflight_message_en": str(readiness.get("message_en") or message).strip(),
            "queue_preflight_action_label": str(readiness.get("action_label") or "").strip(),
        },
    }

def _social_post_has_selected_media(cursor: Any, post: dict[str, Any]) -> bool:
    media = post.get("media_json")
    if isinstance(media, list) and len(media) > 0:
        return True
    if isinstance(media, dict) and bool(media):
        return True
    if not hasattr(cursor, "execute"):
        return False
    business_id = str(post.get("business_id") or "").strip()
    item_id = str(post.get("content_plan_item_id") or "").strip()
    post_id = str(post.get("id") or "").strip()
    target_ids = [value for value in (post_id, item_id) if value]
    if not business_id or not target_ids:
        return False
    try:
        cursor.execute(
            """
            SELECT 1
            FROM photo_asset_usage_events
            WHERE business_id = %s
              AND usage_type = 'publication'
              AND target_id = ANY(%s)
            LIMIT 1
            """,
            (business_id, target_ids),
        )
        return bool(cursor.fetchone())
    except Exception:
        return False

def _social_post_media_is_instagram_ready(post: dict[str, Any]) -> bool:
    media = post.get("media_json")
    if not media:
        return True
    items = media if isinstance(media, list) else [media]
    for item in items:
        if not isinstance(item, dict):
            continue
        mime_type = str(item.get("mime_type") or item.get("content_type") or "").lower()
        url = str(item.get("url") or item.get("original_url") or item.get("public_url") or "").lower()
        if mime_type and mime_type not in {"image/jpeg", "image/jpg"}:
            return False
        if not mime_type and url and not (url.endswith(".jpg") or url.endswith(".jpeg")):
            return False
    return True

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
    google_has_location = bool(str(google_account.get("external_id") or "").strip()) if google_account else False
    google_ready = bool(google_account) and google_has_location
    google_status = "ready" if google_ready else ("missing_binding" if google_account else "missing_connection")
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
            google_ready,
            google_status,
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
