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

from auth_encryption import decrypt_auth_data, encrypt_auth_data
from database_manager import DatabaseManager
from core.outbound_network import outbound_urlopen
from core.telegram_network import telegram_urlopen
from core.telegram_token_store import decode_telegram_bot_token
from core.helpers import get_business_owner_id
from services.media_file_storage import load_media_file
from services.openclaw_capability_catalog import get_openclaw_capability_catalog
from services.vk_oauth_service import oauth_token_expiry, refresh_vk_oauth_tokens


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

from functools import wraps

from services.social_posts import readiness_foundation as _chunk_readiness_foundation
from services.social_posts import launch_proof as _chunk_launch_proof
from services.social_posts import workflow as _chunk_workflow
from services.social_posts import dispatch_reports as _chunk_dispatch_reports
from services.social_posts import recommendations_handoff as _chunk_recommendations_handoff
from services.social_posts import provider_adapters as _chunk_provider_adapters
from services.social_posts import metrics_policy as _chunk_metrics_policy

_CHUNK_MODULES = (
    _chunk_readiness_foundation,
    _chunk_launch_proof,
    _chunk_workflow,
    _chunk_dispatch_reports,
    _chunk_recommendations_handoff,
    _chunk_provider_adapters,
    _chunk_metrics_policy,
)
_IMPLEMENTATIONS = {
    name: value
    for module in _CHUNK_MODULES
    for name, value in vars(module).items()
    if callable(value) and getattr(value, "__module__", "") == module.__name__
}


def _bind_runtime_namespace() -> None:
    namespace = globals()
    for module in _CHUNK_MODULES:
        vars(module).update(namespace)


def _compatibility_wrapper(name: str, implementation: Any):
    @wraps(implementation)
    def wrapper(*args: Any, **kwargs: Any):
        _bind_runtime_namespace()
        return _IMPLEMENTATIONS[name](*args, **kwargs)

    return wrapper


for _name, _implementation in _IMPLEMENTATIONS.items():
    globals()[_name] = _compatibility_wrapper(_name, _implementation)

_bind_runtime_namespace()
