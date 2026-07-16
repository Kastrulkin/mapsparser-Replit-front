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

def prepare_social_posts_for_items(
    user_id: str,
    item_ids: list[str],
    platforms: list[str] | None = None,
    replace_platforms: bool = False,
) -> dict[str, Any]:
    posts: list[dict[str, Any]] = []
    failed: list[dict[str, str]] = []
    removed_platforms: list[str] = []
    preserved_platforms: list[str] = []
    for item_id in _normalize_ids(item_ids):
        try:
            payload = prepare_social_posts_for_item(user_id, item_id, platforms, replace_platforms=replace_platforms)
            posts.extend(payload.get("posts") or [])
            removed_platforms.extend([str(item) for item in payload.get("removed_platforms") or [] if str(item or "").strip()])
            preserved_platforms.extend([str(item) for item in payload.get("preserved_platforms") or [] if str(item or "").strip()])
        except Exception:
            failed.append({"id": item_id, "error": str(sys.exc_info()[1])})
    return {
        "posts": posts,
        "failed": failed,
        "summary": _summary_for_posts(posts),
        "queue_groups": build_social_queue_groups(posts),
        "removed_platforms": sorted(set(removed_platforms)),
        "preserved_platforms": sorted(set(preserved_platforms)),
    }

def _remove_unselected_social_posts(
    cursor: Any,
    *,
    item_id: str,
    selected_platforms: list[str],
) -> tuple[list[str], list[str]]:
    cursor.execute(
        """
        SELECT id, platform, status
        FROM social_posts
        WHERE content_plan_item_id = %s
          AND NOT (platform = ANY(%s))
        """,
        (item_id, selected_platforms),
    )
    removable_statuses = {"draft", "needs_review", "approved", "failed", "needs_manual_publish", "needs_supervised_publish"}
    removable_ids: list[str] = []
    removed_platforms: list[str] = []
    preserved_platforms: list[str] = []
    for row in cursor.fetchall() or []:
        data = _row_to_dict(cursor, row)
        post_id = str(data.get("id") or "").strip()
        platform = str(data.get("platform") or "").strip()
        status = str(data.get("status") or "").strip()
        if status in removable_statuses and post_id:
            removable_ids.append(post_id)
            if platform:
                removed_platforms.append(platform)
        elif platform:
            preserved_platforms.append(platform)
    if removable_ids:
        cursor.execute("DELETE FROM social_posts WHERE id = ANY(%s)", (removable_ids,))
    return removed_platforms, preserved_platforms

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

def _record_knowledge_publish_event(cursor: Any, post: dict[str, Any], user_id: str, confirmation_mode: str) -> None:
    if str(post.get("status") or "") != "published":
        return
    try:
        from services.knowledge_graph_service import knowledge_layer_enabled, record_action_event
    except Exception:
        return
    if not knowledge_layer_enabled():
        return
    cursor.execute("SAVEPOINT knowledge_content_publish")
    try:
        metadata = _json_dict(post.get("metadata_json"))
        record_action_event(
            cursor.connection,
            business_id=str(post.get("business_id") or ""),
            action_type="content_published",
            source_type="social_post",
            source_id=str(post.get("id") or ""),
            status="confirmed",
            hypothesis_id=str(metadata.get("hypothesis_id") or "").strip() or None,
            approval_id=str(post.get("approval_id") or "").strip() or f"explicit:{user_id}:{post.get('id')}",
            before={"status": "approved"},
            after={
                "status": "published",
                "platform": post.get("platform"),
                "provider_post_id": post.get("provider_post_id"),
            },
            limitations=["Публикация подтверждена; влияние на метрики ещё не оценено"],
            metadata={
                "confirmation_mode": confirmation_mode,
                "knowledge_assertion_ids": metadata.get("knowledge_assertion_ids") or [],
                "analysis_version": metadata.get("analysis_version"),
            },
        )
        cursor.execute("RELEASE SAVEPOINT knowledge_content_publish")
    except Exception:
        cursor.execute("ROLLBACK TO SAVEPOINT knowledge_content_publish")
        cursor.execute("RELEASE SAVEPOINT knowledge_content_publish")


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
        _record_knowledge_publish_event(cursor, updated, user_id, "provider_api")
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
        _record_knowledge_publish_event(cursor, updated, user_id, "manual_confirmation")
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
    explicit_scope = str(business_id or "").strip()
    if explicit_scope:
        return explicit_scope
    if _social_dispatch_multi_tenant():
        return ""
    return str(os.getenv("SOCIAL_POST_DISPATCH_BUSINESS_ID") or "").strip()

def _social_metrics_business_scope(business_id: str = "") -> str:
    explicit_scope = str(business_id or "").strip()
    if explicit_scope:
        return explicit_scope
    if _social_metrics_multi_tenant():
        return ""
    return str(os.getenv("SOCIAL_POST_METRICS_BUSINESS_ID") or "").strip()

def _social_dispatch_multi_tenant() -> bool:
    return str(os.getenv("SOCIAL_POST_DISPATCH_MODE") or "").strip().lower() == "multi_tenant"

def _social_metrics_multi_tenant() -> bool:
    return str(os.getenv("SOCIAL_POST_METRICS_MODE") or "").strip().lower() == "multi_tenant"

def _social_dispatch_allow_unscoped() -> bool:
    return _social_dispatch_multi_tenant() or str(os.getenv("SOCIAL_POST_DISPATCH_ALLOW_UNSCOPED") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
        "enabled",
    }

def _social_metrics_allow_unscoped() -> bool:
    return _social_metrics_multi_tenant() or str(os.getenv("SOCIAL_POST_METRICS_ALLOW_UNSCOPED") or "").strip().lower() in {
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
