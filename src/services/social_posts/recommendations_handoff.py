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
from functools import wraps
from typing import Any

from auth_encryption import decrypt_auth_data
from database_manager import DatabaseManager
from core.outbound_network import outbound_urlopen
from core.telegram_network import telegram_urlopen
from core.telegram_token_store import decode_telegram_bot_token
from core.helpers import get_business_owner_id
from services.media_file_storage import load_media_file
from services.openclaw_capability_catalog import get_openclaw_capability_catalog
from services.social_posts.approval_binding import (
    approval_binding_drift_result,
    frozen_external_account,
    meta_channel_readiness,
    meta_publish_status,
    snapshot_is_sendable,
    snapshot_is_well_formed,
    vk_publish_binding,
    vk_uses_community_token,
)


SOCIAL_POST_PLATFORMS = [
    "yandex_maps",
    "two_gis",
    "google_business",
    "telegram",
    "vk",
    "max",
    "instagram",
    "facebook",
]

API_PLATFORMS = {"google_business", "telegram", "vk", "instagram", "facebook"}
BROWSER_OR_MANUAL_PLATFORMS = {"yandex_maps", "two_gis", "max"}
FIRST_API_PROOF_PLATFORMS = ("telegram", "vk")
PUBLISH_OUTCOMES = {"accepted", "not_attempted", "rejected", "uncertain"}


def _json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return {}
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _telegram_post_url(chat_id: str, message_id: str) -> str:
    chat = str(chat_id or "").strip()
    message = str(message_id or "").strip()
    if not chat or not message:
        return ""
    if chat.startswith("@"):
        return f"https://t.me/{chat[1:]}/{message}"
    normalized = chat[4:] if chat.startswith("-100") else ""
    return f"https://t.me/c/{normalized}/{message}" if normalized else ""


def _vk_post_url(owner_id: str, post_id: str) -> str:
    owner = str(owner_id or "").strip()
    post = str(post_id or "").strip()
    return f"https://vk.com/wall{owner}_{post}" if owner and post else ""


def _publish_platform_label(platform: str) -> str:
    labels = {
        "facebook": "Facebook",
        "google_business": "Google Business Profile",
        "instagram": "Instagram",
        "telegram": "Telegram",
        "vk": "VK",
    }
    return labels.get(str(platform or "").strip(), "канал")

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

def _valid_provider_receipt(result: dict[str, Any]) -> bool:
    receipt = str(result.get("provider_post_id") or "").strip()
    if not receipt or receipt.lower() in {"0", "false", "none", "null"}:
        return False
    provider_status = str(_json_dict(result.get("metadata_json")).get("provider_status") or "").strip()
    if provider_status.startswith(("telegram_", "vk_")):
        return receipt.isdigit() and int(receipt) > 0
    return True


def _publish_outcome_result(result: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(result)
    explicit_outcome = str(normalized.get("publish_outcome") or "").strip()
    if explicit_outcome in PUBLISH_OUTCOMES:
        if explicit_outcome == "accepted" and not _valid_provider_receipt(normalized):
            normalized["publish_outcome"] = "uncertain"
        return normalized
    if _valid_provider_receipt(normalized):
        normalized["publish_outcome"] = "accepted"
    elif str(normalized.get("status") or "").strip() in {"needs_manual_publish", "needs_review"}:
        normalized["publish_outcome"] = "not_attempted"
    else:
        normalized["publish_outcome"] = "uncertain"
    return normalized


def _publish_adapter(function: Any) -> Any:
    @wraps(function)
    def wrapped(*args: Any, **kwargs: Any) -> dict[str, Any]:
        result = function(*args, **kwargs)
        if not isinstance(result, dict):
            return {
                "status": "failed",
                "last_error": "Провайдер не вернул результат публикации.",
                "metadata_json": {"provider_status": "provider_result_missing"},
                "publish_outcome": "uncertain",
            }
        return _publish_outcome_result(result)
    return wrapped


def _http_publish_outcome(status_code: int) -> str:
    if 400 <= int(status_code or 0) < 500 and int(status_code or 0) not in {408, 409}:
        return "rejected"
    return "uncertain"


def _provider_json_object(body: str) -> tuple[dict[str, Any], bool]:
    try:
        value = json.loads(body)
    except (TypeError, ValueError):
        return {}, False
    return (value, True) if isinstance(value, dict) else ({}, False)


@_publish_adapter
def _publish_api_post(cursor: Any, post: dict[str, Any], approval_snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    from services.disk_import_media import selected
    if selected(cursor, post.get("business_id"), post.get("content_plan_item_id")):
        return {
            "status": "needs_manual_publish",
            "last_error": "Видео с Диска размещается вручную.",
            "metadata_json": {"external_video_manual": True},
            "publish_outcome": "not_attempted",
        }
    platform = str(post.get("platform") or "").strip()
    if platform not in API_PLATFORMS:
        return {
            "status": "needs_manual_publish",
            "last_error": "Для канала не настроен API-адаптер",
            "metadata_json": {"provider_status": "unsupported_api_platform"},
            "publish_outcome": "not_attempted",
        }
    if not snapshot_is_well_formed(approval_snapshot, post) or not snapshot_is_sendable(approval_snapshot, post):
        return approval_binding_drift_result("approval_binding_missing_or_invalid")
    if platform == "telegram":
        return _publish_telegram_post(cursor, post, approval_snapshot)
    if platform == "vk":
        return _publish_vk_post(cursor, post, approval_snapshot)
    if platform == "google_business":
        return _publish_google_business_post(cursor, post, approval_snapshot)
    if platform in {"instagram", "facebook"}:
        return _publish_meta_post(cursor, post, approval_snapshot)
    return approval_binding_drift_result("approval_binding_platform_invalid")

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

@_publish_adapter
def _publish_telegram_post(cursor: Any, post: dict[str, Any], approval_snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    if not snapshot_is_well_formed(approval_snapshot, post) or not snapshot_is_sendable(approval_snapshot, post):
        return approval_binding_drift_result("telegram_approval_binding_missing_or_invalid")
    business = _load_business_publish_context(cursor, str(post.get("business_id") or ""))
    transport = _resolve_telegram_publish_transport(business)
    bot_token = str(transport.get("bot_token") or "").strip()
    binding = _json_dict((approval_snapshot or {}).get("binding"))
    recipient = _json_dict(binding.get("recipient"))
    sender = _json_dict(binding.get("sender"))
    chat_id = str(recipient.get("chat_id") or "").strip()
    expected_source = str(sender.get("transport_source") or "").strip()
    expected_bot_id = str(sender.get("bot_numeric_id") or "").strip()
    current_bot_id = str(bot_token).partition(":")[0].strip()
    if (
        not chat_id
        or str(transport.get("token_source") or "") != expected_source
        or not expected_bot_id
        or current_bot_id != expected_bot_id
    ):
        return {
            "status": "needs_review",
            "last_error": "Привязка Telegram изменилась после подтверждения.",
            "metadata_json": {"provider_status": "telegram_approval_binding_drift"},
            "publish_outcome": "not_attempted",
        }
    if not bot_token or not chat_id:
        return {
            "status": "needs_manual_publish",
            "last_error": "Для Telegram нужен бот LocalOS или telegram_bot_token бизнеса и telegram_chat_id цели публикации.",
            "metadata_json": {
                "provider_status": "telegram_connection_missing",
                "telegram_transport": str(transport.get("token_source") or "missing"),
            },
            "publish_outcome": "not_attempted",
        }
    text = str(post.get("platform_text") or post.get("base_text") or "").strip()
    if not text:
        return {
            "status": "failed",
            "last_error": "Пустой текст нельзя отправить в Telegram.",
            "metadata_json": {"provider_status": "telegram_empty_text"},
            "publish_outcome": "not_attempted",
        }
    from services.social_posts.media_delivery import _approved_media_assets

    media_assets = _approved_media_assets(cursor, post, approval_snapshot or {})
    if media_assets is None:
        return approval_binding_drift_result("telegram_approval_media_drift")
    if media_assets:
        return _publish_telegram_media_post(
            bot_token=bot_token,
            chat_id=chat_id,
            text=text,
            media_assets=media_assets,
            transport_source=str(transport.get("token_source") or ""),
        )
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
            parsed, parsed_ok = _provider_json_object(body)
            status_code = int(getattr(resp, "status", 500))
            if not parsed_ok:
                return {
                    "status": "failed",
                    "last_error": "Telegram вернул непонятный ответ после попытки публикации.",
                    "metadata_json": {"provider_status": "telegram_response_parse_failed", "status_code": status_code},
                    "publish_outcome": "uncertain",
                }
            if not (200 <= status_code < 300) or not bool(parsed.get("ok")):
                description = str(parsed.get("description") or body or f"Telegram HTTP {status_code}")[:1000]
                status, provider_status = _telegram_publish_error_state(status_code, description)
                return {
                    "status": status,
                    "last_error": description,
                    "metadata_json": {"provider_status": provider_status, "status_code": status_code},
                    "publish_outcome": "rejected" if 200 <= status_code < 300 else _http_publish_outcome(status_code),
                }
            result = parsed.get("result") if isinstance(parsed.get("result"), dict) else {}
            message_id = str(result.get("message_id") or "").strip()
            return {
                "status": "published",
                "provider_post_id": message_id,
                "provider_post_url": _telegram_post_url(chat_id, message_id),
                "publish_outcome": "accepted" if message_id.isdigit() and int(message_id) > 0 else "uncertain",
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
            "publish_outcome": _http_publish_outcome(status_code),
        }
    except (urllib.error.URLError, TimeoutError):
        error = sys.exc_info()[1]
        return {
            "status": "failed",
            "last_error": str(error),
            "metadata_json": {"provider_status": "telegram_network_error"},
            "publish_outcome": "uncertain",
        }
    except Exception:
        error = sys.exc_info()[1]
        return {
            "status": "failed",
            "last_error": str(error),
            "metadata_json": {"provider_status": "telegram_unexpected_error"},
            "publish_outcome": "uncertain",
        }

@_publish_adapter
def _publish_vk_post(cursor: Any, post: dict[str, Any], approval_snapshot: dict[str, Any]) -> dict[str, Any]:
    if not snapshot_is_well_formed(approval_snapshot, post) or not snapshot_is_sendable(approval_snapshot, post):
        return approval_binding_drift_result("vk_approval_binding_missing_or_invalid")
    account, binding = frozen_external_account(cursor, post, approval_snapshot, "vk")
    if not account:
        return approval_binding_drift_result("vk_approval_account_drift")
    auth_data = _external_account_auth_data(account)
    frozen_owner_id = str(_json_dict(binding.get("recipient")).get("id") or "").strip()
    original_binding = vk_publish_binding(account, auth_data)
    if not frozen_owner_id or not original_binding.get("ready") or str(original_binding.get("owner_id") or "").strip() != frozen_owner_id:
        return approval_binding_drift_result("vk_approval_binding_drift")
    auth_data = _vk_auth_data_with_fresh_token(cursor, account, auth_data)
    if auth_data.get("_oauth_refresh_error"):
        return {
            "status": "needs_manual_publish",
            "last_error": "Доступ VK устарел. Подключите сообщество заново.",
            "metadata_json": {
                "provider_status": "vk_token_expired",
                "external_account_id": account.get("id"),
            },
            "publish_outcome": "not_attempted",
        }
    vk_binding = vk_publish_binding(account, auth_data)
    if not vk_binding.get("ready"):
        return {
            "status": "needs_manual_publish",
            "last_error": _vk_readiness_error(str(vk_binding.get("status") or "")),
            "metadata_json": {
                "provider_status": str(vk_binding.get("status") or "vk_not_ready"),
                "external_account_id": account.get("id"),
            },
            "publish_outcome": "not_attempted",
        }
    token = str(vk_binding.get("token") or "").strip()
    owner_id = frozen_owner_id
    text = str(post.get("platform_text") or post.get("base_text") or "").strip()
    if not text:
        return {
            "status": "failed",
            "last_error": "Пустой текст нельзя отправить во VK.",
            "metadata_json": {"provider_status": "vk_empty_text"},
            "publish_outcome": "not_attempted",
        }
    from services.social_posts.media_delivery import _approved_media_assets

    media_assets = _approved_media_assets(cursor, post, approval_snapshot)
    if media_assets is None:
        return approval_binding_drift_result("vk_approval_media_drift")
    attachments: list[str] = []
    if media_assets and vk_uses_community_token(auth_data):
        return {
            "status": "needs_manual_publish",
            "last_error": "Для публикации фото в VK откройте контролируемое размещение.",
            "metadata_json": {
                "provider_status": "vk_community_media_requires_manual",
                "external_account_id": account.get("id"),
                "media_attachment_count": len(media_assets),
            },
            "publish_outcome": "not_attempted",
        }
    if media_assets:
        upload_result = _upload_vk_wall_photos(
            token=token,
            owner_id=owner_id,
            api_version=str(auth_data.get("api_version") or "5.199"),
            media_assets=media_assets,
        )
        if not bool(upload_result.get("success")):
            return {
                "status": "needs_review",
                "last_error": str(upload_result.get("error") or "Не удалось подготовить фото для VK."),
                "metadata_json": {
                    "provider_status": str(upload_result.get("status") or "vk_media_upload_failed"),
                    "external_account_id": account.get("id"),
                },
                "publish_outcome": "uncertain",
            }
        attachments = [str(item) for item in upload_result.get("attachments") or [] if str(item or "").strip()]
    payload = urllib.parse.urlencode(
        {
            "access_token": token,
            "owner_id": owner_id,
            "message": text,
            "attachments": ",".join(attachments),
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
        resp = outbound_urlopen(req, timeout=15)
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
            "publish_outcome": _http_publish_outcome(int(getattr(error, "code", 0) or 0)),
        }
    except (urllib.error.URLError, TimeoutError):
        error = sys.exc_info()[1]
        return {
            "status": "failed",
            "last_error": str(error),
            "metadata_json": {"provider_status": "vk_network_error", "external_account_id": account.get("id")},
            "publish_outcome": "uncertain",
        }
    except Exception:
        error = sys.exc_info()[1]
        return {
            "status": "failed",
            "last_error": str(error),
            "metadata_json": {"provider_status": "vk_unexpected_error", "external_account_id": account.get("id")},
            "publish_outcome": "uncertain",
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
            "publish_outcome": "rejected",
        }
    response = parsed.get("response") if isinstance(parsed.get("response"), dict) else {}
    post_id = str(response.get("post_id") or "").strip()
    provider_url = _vk_post_url(owner_id, post_id)
    if not post_id:
        return {
            "status": "failed",
            "last_error": "VK не вернул post_id.",
            "metadata_json": {"provider_status": "vk_missing_post_id", "external_account_id": account.get("id"), "vk_response": parsed},
            "publish_outcome": "uncertain",
        }
    return {
        "status": "published",
        "provider_post_id": post_id,
        "provider_post_url": provider_url,
        "publish_outcome": "accepted",
        "metadata_json": {
            "provider_status": "vk_published",
            "provider_write_performed": True,
            "external_publish_performed": True,
            "external_account_id": account.get("id"),
            "media_attachment_count": len(attachments),
            "vk_response": parsed,
        },
    }

@_publish_adapter
def _publish_google_business_post(cursor: Any, post: dict[str, Any], approval_snapshot: dict[str, Any]) -> dict[str, Any]:
    if not snapshot_is_well_formed(approval_snapshot, post) or not snapshot_is_sendable(approval_snapshot, post):
        return approval_binding_drift_result("google_business_approval_binding_missing_or_invalid")
    account, binding = frozen_external_account(cursor, post, approval_snapshot, "google_business")
    if not account:
        return approval_binding_drift_result("google_business_approval_account_drift")
    if str(_json_dict(binding.get("recipient")).get("id") or "").strip() != str(account.get("external_id") or "").strip():
        return approval_binding_drift_result("google_business_approval_binding_drift")
    summary = str(post.get("platform_text") or post.get("base_text") or "").strip()
    if not summary:
        return {
            "status": "failed",
            "last_error": "Пустой текст нельзя отправить в Google Business Profile.",
            "metadata_json": {"provider_status": "google_business_empty_text", "external_account_id": account.get("id")},
            "publish_outcome": "not_attempted",
        }
    post_data = {
        "topicType": "STANDARD",
        "summary": summary[:1500],
        "callToAction": {
            "actionType": "CALL",
            "url": "",
        },
    }
    from services.social_posts.media_delivery import _approved_media_assets

    media_assets = _approved_media_assets(cursor, post, approval_snapshot)
    if media_assets is None:
        return approval_binding_drift_result("google_business_approval_media_drift")
    media_assets = media_assets[:1]
    media_url = str(media_assets[0].get("public_url") or "").strip() if media_assets else ""
    if media_url.startswith("https://") or media_url.startswith("http://"):
        post_data["media"] = [{"mediaFormat": "PHOTO", "sourceUrl": media_url}]
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
            "publish_outcome": "not_attempted",
        }
    except Exception:
        error = sys.exc_info()[1]
        return {
            "status": "failed",
            "last_error": str(error),
            "metadata_json": {"provider_status": "google_business_exception", "external_account_id": account.get("id")},
            "publish_outcome": "uncertain",
        }
    if not provider_post_id:
        return {
            "status": "needs_manual_publish",
            "last_error": "Google Business Profile не принял публикацию. Проверьте OAuth, location и разрешения.",
            "metadata_json": {"provider_status": "google_business_publish_failed", "external_account_id": account.get("id")},
            "publish_outcome": "uncertain",
        }
    return {
        "status": "published",
        "provider_post_id": str(provider_post_id),
        "provider_post_url": "",
        "publish_outcome": "accepted",
        "metadata_json": {
            "provider_status": "google_business_published",
            "external_account_id": account.get("id"),
            "media_attached": bool(post_data.get("media")),
        },
    }

def _meta_graph_post(path: str, access_token: str, params: dict[str, Any]) -> dict[str, Any]:
    api_version = str(os.getenv("META_GRAPH_API_VERSION") or "v25.0").strip().strip("/")
    clean_path = str(path or "").strip().lstrip("/")
    payload = dict(params)
    payload["access_token"] = access_token
    request = urllib.request.Request(
        f"https://graph.facebook.com/{api_version}/{clean_path}",
        data=urllib.parse.urlencode(payload).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        response = outbound_urlopen(request, timeout=20)
        try:
            body = response.read().decode("utf-8", errors="ignore")
            status_code = int(getattr(response, "status", 500))
        finally:
            response.close()
    except urllib.error.HTTPError:
        error = sys.exc_info()[1]
        body = ""
        try:
            body = error.read().decode("utf-8", errors="ignore")
        except Exception:
            body = str(error)
        parsed_error = _json_dict(body)
        graph_error = _json_dict(parsed_error.get("error"))
        return {
            "success": False,
            "status_code": int(getattr(error, "code", 0) or 0),
            "error": str(graph_error.get("message") or body or error)[:1000],
            "error_code": str(graph_error.get("code") or "").strip(),
            "response": parsed_error,
            "publish_outcome": _http_publish_outcome(int(getattr(error, "code", 0) or 0)),
        }
    except (urllib.error.URLError, TimeoutError):
        return {"success": False, "status_code": 0, "error": str(sys.exc_info()[1]), "response": {}, "publish_outcome": "uncertain"}
    except Exception:
        return {"success": False, "status_code": 0, "error": str(sys.exc_info()[1]), "response": {}, "publish_outcome": "uncertain"}
    parsed, parsed_ok = _provider_json_object(body)
    if not parsed_ok:
        return {
            "success": False,
            "status_code": status_code,
            "error": "Meta Graph вернул непонятный ответ после попытки публикации.",
            "error_code": "",
            "response": {},
            "publish_outcome": "uncertain",
        }
    if not (200 <= status_code < 300) or isinstance(parsed.get("error"), dict):
        graph_error = _json_dict(parsed.get("error"))
        return {
            "success": False,
            "status_code": status_code,
            "error": str(graph_error.get("message") or body or f"Meta Graph HTTP {status_code}")[:1000],
            "error_code": str(graph_error.get("code") or "").strip(),
            "response": parsed,
            "publish_outcome": "rejected" if 200 <= status_code < 300 else _http_publish_outcome(status_code),
        }
    return {"success": True, "status_code": status_code, "response": parsed, "publish_outcome": "uncertain"}

def _meta_publish_error_result(platform: str, result: dict[str, Any], account_id: Any) -> dict[str, Any]:
    status_code = int(result.get("status_code") or 0)
    error_code = str(result.get("error_code") or "").strip()
    needs_connection = status_code in {400, 401, 403} or error_code in {"10", "100", "190", "200"}
    return {
        "status": "needs_manual_publish" if needs_connection else "failed",
        "last_error": str(result.get("error") or "Meta Graph не принял публикацию."),
        "metadata_json": {
            "provider_status": "meta_connection_invalid" if needs_connection else "meta_graph_error",
            "platform": platform,
            "status_code": status_code,
            "error_code": error_code,
            "external_account_id": account_id,
        },
        "publish_outcome": str(result.get("publish_outcome") or "uncertain"),
    }

@_publish_adapter
def _publish_meta_post(cursor: Any, post: dict[str, Any], approval_snapshot: dict[str, Any]) -> dict[str, Any]:
    platform = str(post.get("platform") or "").strip()
    if not snapshot_is_well_formed(approval_snapshot, post) or not snapshot_is_sendable(approval_snapshot, post):
        return approval_binding_drift_result("meta_approval_binding_missing_or_invalid")
    account, binding = frozen_external_account(cursor, post, approval_snapshot, platform)
    if not account:
        return approval_binding_drift_result("meta_approval_account_drift")
    auth_data = _external_account_auth_data(account)
    publish_status = meta_publish_status(account, auth_data, platform)
    if publish_status != "ready":
        return {
            "status": "needs_manual_publish",
            "last_error": _meta_readiness_error(platform, publish_status, True),
            "metadata_json": {
                "provider_status": publish_status,
                "external_account_id": account.get("id") if account else None,
            },
            "publish_outcome": "not_attempted",
        }
    access_token = str(auth_data.get("access_token") or auth_data.get("token") or "").strip()
    text = str(post.get("platform_text") or post.get("base_text") or "").strip()
    from services.social_posts.media_delivery import _approved_media_assets

    media_assets = _approved_media_assets(cursor, post, approval_snapshot)
    if media_assets is None:
        return approval_binding_drift_result("meta_approval_media_drift")
    media_assets = media_assets[:1]
    media_url = str(media_assets[0].get("public_url") or "").strip() if media_assets else ""
    account_id = account.get("id") if account else None

    if not text and not media_url:
        return {
            "status": "failed",
            "last_error": f"Для {_publish_platform_label(platform)} нужен текст или доступное медиа.",
            "metadata_json": {"provider_status": "meta_empty_content", "external_account_id": account_id},
            "publish_outcome": "not_attempted",
        }

    if platform == "instagram":
        ig_user_id = str(auth_data.get("ig_user_id") or auth_data.get("instagram_business_account_id") or "").strip()
        if ig_user_id != str(_json_dict(binding.get("recipient")).get("id") or "").strip():
            return approval_binding_drift_result("instagram_approval_binding_drift")
        if not media_url.startswith(("https://", "http://")):
            return {
                "status": "needs_review",
                "last_error": "Instagram: выерите фото, доступное для публикации.",
                "metadata_json": {"provider_status": "media_public_url_required", "external_account_id": account_id},
                "publish_outcome": "not_attempted",
            }
        created = _meta_graph_post(
            f"{ig_user_id}/media",
            access_token,
            {"image_url": media_url, "caption": text},
        )
        if not created.get("success"):
            return _meta_publish_error_result(platform, created, account_id)
        creation_id = str(_json_dict(created.get("response")).get("id") or "").strip()
        if not creation_id:
            return {
                "status": "failed",
                "last_error": "Instagram не вернул ID подготовленной публикации.",
                "metadata_json": {"provider_status": "instagram_creation_id_missing", "external_account_id": account_id},
                "publish_outcome": "uncertain",
            }
        published = _meta_graph_post(
            f"{ig_user_id}/media_publish",
            access_token,
            {"creation_id": creation_id},
        )
        if not published.get("success"):
            return _meta_publish_error_result(platform, published, account_id)
        provider_post_id = str(_json_dict(published.get("response")).get("id") or "").strip()
        provider_post_url = ""
        provider_status = "instagram_published"
    else:
        page_id = str(auth_data.get("page_id") or (account.get("external_id") if account else "") or "").strip()
        if page_id != str(_json_dict(binding.get("recipient")).get("id") or "").strip():
            return approval_binding_drift_result("facebook_approval_binding_drift")
        if media_url.startswith(("https://", "http://")):
            published = _meta_graph_post(f"{page_id}/photos", access_token, {"url": media_url, "caption": text})
        else:
            published = _meta_graph_post(f"{page_id}/feed", access_token, {"message": text})
        if not published.get("success"):
            return _meta_publish_error_result(platform, published, account_id)
        response = _json_dict(published.get("response"))
        provider_post_id = str(response.get("post_id") or response.get("id") or "").strip()
        provider_post_url = f"https://www.facebook.com/{provider_post_id}" if provider_post_id else ""
        provider_status = "facebook_published"

    if not provider_post_id:
        return {
            "status": "failed",
            "last_error": f"{_publish_platform_label(platform)} не вернул ID публикации.",
            "metadata_json": {"provider_status": "meta_post_id_missing", "external_account_id": account_id},
            "publish_outcome": "uncertain",
        }
    return {
        "status": "published",
        "provider_post_id": provider_post_id,
        "provider_post_url": provider_post_url,
        "publish_outcome": "accepted",
        "metadata_json": {
            "provider_status": provider_status,
            "provider_write_performed": True,
            "external_publish_performed": True,
            "external_account_id": account_id,
            "media_attached": bool(media_url),
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
    auth_data = _vk_auth_data_with_fresh_token(cursor, account, auth_data)
    if auth_data.get("_oauth_refresh_error"):
        return _api_channel_preflight_result(
            "vk",
            False,
            "token_expired",
            _vk_connection_checks(account, auth_data, {"ready": False, "status": "token_expired"}),
            "Доступ VK устарел. Подключите сообщество заново.",
            "VK access expired. Reconnect the community.",
        )
    binding = vk_publish_binding(account, auth_data)
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
    api_version = str(auth_data.get("api_version") or "5.199")
    group_id = owner_id.lstrip("-")
    permissions_probe = _vk_safe_group_token_permissions_probe(token, api_version)
    if permissions_probe.get("ok"):
        permission_names = {
            str(item.get("name") or "").strip()
            for item in permissions_probe.get("permissions") or []
            if isinstance(item, dict)
        }
        has_wall_permission = "wall" in permission_names
        group_probe = _vk_safe_group_identity_probe(token, group_id, api_version)
        checks = checks + [
            _connection_check(
                "vk_group_token_live",
                has_wall_permission,
                "Ключ сообщества",
                "Community token",
                "VK подтвердил право публикации на стене" if has_wall_permission else "VK не подтвердил право публикации на стене",
                "VK confirmed wall publishing permission" if has_wall_permission else "VK did not confirm wall publishing permission",
                "ok" if has_wall_permission else "missing_permissions",
            ),
            _connection_check(
                "vk_group_identity_live",
                bool(group_probe.get("ok")),
                "Сообщество VK",
                "VK community",
                str(group_probe.get("detail_ru") or "сообщество найдено"),
                str(group_probe.get("detail_en") or "community found"),
                "ok" if group_probe.get("ok") else str(group_probe.get("status") or "failed"),
            ),
        ]
        ready = bool(has_wall_permission and group_probe.get("ok"))
        status = "ready" if ready else ("missing_permissions" if not has_wall_permission else "live_probe_failed")
        return _api_channel_preflight_result(
            "vk",
            ready,
            status,
            checks,
            "VK готов к отправке текстовых публикаций после подтверждения." if ready else "Не удалось подтвердить право сообщества на публикацию.",
            "VK is ready for text publishing after approval." if ready else "The community publishing permission could not be confirmed.",
        )

    # Legacy user tokens do not support groups.getTokenPermissions. Keep the
    # previous read-only wall probe for those connections.
    read_probe = _vk_safe_wall_read_probe(token, owner_id, api_version)
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

def _vk_safe_group_token_permissions_probe(token: str, api_version: str) -> dict[str, Any]:
    query = urllib.parse.urlencode(
        {
            "access_token": token,
            "v": api_version or "5.199",
        }
    )
    req = urllib.request.Request(f"https://api.vk.com/method/groups.getTokenPermissions?{query}", method="GET")
    try:
        resp = outbound_urlopen(req, timeout=10)
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
    response = parsed.get("response") if isinstance(parsed.get("response"), dict) else {}
    return {
        "ok": True,
        "status": "ok",
        "permissions": response.get("permissions") if isinstance(response.get("permissions"), list) else [],
    }

def _vk_safe_group_identity_probe(token: str, group_id: str, api_version: str) -> dict[str, Any]:
    query = urllib.parse.urlencode(
        {
            "access_token": token,
            "group_id": group_id,
            "v": api_version or "5.199",
        }
    )
    req = urllib.request.Request(f"https://api.vk.com/method/groups.getById?{query}", method="GET")
    try:
        resp = outbound_urlopen(req, timeout=10)
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
    response = parsed.get("response")
    groups = response.get("groups") if isinstance(response, dict) else response
    group = groups[0] if isinstance(groups, list) and groups and isinstance(groups[0], dict) else {}
    actual_group_id = str(group.get("id") or "").strip()
    if not actual_group_id or actual_group_id != str(group_id or "").strip():
        return {
            "ok": False,
            "status": "missing_binding",
            "detail_ru": "VK не подтвердил выбранное сообщество",
            "detail_en": "VK did not confirm the selected community",
        }
    group_name = str(group.get("name") or "").strip()
    return {
        "ok": True,
        "status": "ok",
        "detail_ru": f"сообщество найдено: {group_name}" if group_name else "сообщество найдено",
        "detail_en": f"community found: {group_name}" if group_name else "community found",
    }

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
        resp = outbound_urlopen(req, timeout=10)
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
    readiness = meta_channel_readiness(account, auth_data, platform)
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
        "platform_label": _publish_platform_label(platform),
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
              AND status = 'queued'
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

def _vk_auth_data_with_fresh_token(
    cursor: Any,
    account: dict[str, Any],
    auth_data: dict[str, Any],
) -> dict[str, Any]:
    if str(auth_data.get("auth_mode") or "") != "vk_id_oauth":
        return auth_data
    expires_at_raw = str(auth_data.get("expires_at") or "").strip()
    if not expires_at_raw:
        return auth_data
    try:
        expires_at = datetime.fromisoformat(expires_at_raw.replace("Z", "+00:00"))
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at.timestamp() > datetime.now(timezone.utc).timestamp() + 120:
            return auth_data
    except (TypeError, ValueError):
        pass
    try:
        refreshed = refresh_vk_oauth_tokens(
            refresh_token=str(auth_data.get("refresh_token") or ""),
            device_id=str(auth_data.get("device_id") or ""),
        )
        next_auth_data = dict(auth_data)
        next_auth_data["access_token"] = str(refreshed.get("access_token") or "").strip()
        next_auth_data["refresh_token"] = str(
            refreshed.get("refresh_token") or auth_data.get("refresh_token") or ""
        ).strip()
        next_auth_data["token_type"] = str(
            refreshed.get("token_type") or auth_data.get("token_type") or "Bearer"
        ).strip()
        next_auth_data["expires_at"] = oauth_token_expiry(refreshed.get("expires_in"))
        next_auth_data["refreshed_at"] = datetime.now(timezone.utc).isoformat()
        if not next_auth_data["access_token"]:
            raise RuntimeError("VK did not return access_token")
        account_id = str(account.get("id") or "").strip()
        if account_id:
            cursor.execute(
                """
                UPDATE externalbusinessaccounts
                SET auth_data_encrypted = %s, last_error = NULL,
                    last_sync_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (encrypt_auth_data(json.dumps(next_auth_data, ensure_ascii=False)), account_id),
            )
            connection = getattr(cursor, "connection", None)
            if connection is not None:
                connection.commit()
        return next_auth_data
    except Exception:
        failed_auth_data = dict(auth_data)
        failed_auth_data["_oauth_refresh_error"] = str(sys.exc_info()[1] or "refresh_failed")
        return failed_auth_data

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
