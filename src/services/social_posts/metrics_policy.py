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
        if status_key == "missing_binding":
            return ["google_business_location"]
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
    elif posts_with_early_signal and published_posts >= 3:
        status = "early_signals_only"
        confidence = "medium"
    elif posts_with_early_signal:
        status = "collect_more_data"
        confidence = "low"
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
    if status == "collect_more_data":
        return (
            "Появились первые реакции, но данных пока мало для изменения плана."
            if is_ru
            else "Early reactions exist, but there is not enough data to change the plan yet."
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
    if status == "collect_more_data":
        return (
            "Опубликуйте минимум три поста или отметьте заявку/обращение, затем пересчитайте рекомендации."
            if is_ru
            else "Publish at least three posts or record a lead/inquiry, then recalculate recommendations."
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
    if status == "collect_more_data":
        return (
            "Применение заблокировано: дождитесь результатов минимум трёх постов или отметьте заявку/обращение."
            if is_ru
            else "Apply is blocked: wait for results from at least three posts or record a lead/inquiry."
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
