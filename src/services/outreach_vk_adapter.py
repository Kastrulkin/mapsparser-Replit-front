from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlsplit

import requests
from cryptography.fernet import Fernet, InvalidToken

from core.telegram_network import build_requests_proxy_kwargs
from services.vk_oauth_service import oauth_token_expiry, refresh_vk_oauth_tokens


VK_OUTREACH_CREDENTIAL_PREFIX = "localos-outreach-vk-v1:"
VK_OUTREACH_SCOPES = ("messages",)


class VkOutreachAdapterError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


def _text(value: Any) -> str:
    return str(value or "").strip()


def _credential_cipher() -> Fernet:
    secret = _text(os.getenv("OUTREACH_VK_SECRET_KEY"))
    if len(secret) < 32:
        raise VkOutreachAdapterError(
            "outreach_vk_secret_missing",
            "OUTREACH_VK_SECRET_KEY must contain at least 32 characters",
        )
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_vk_outreach_config(config: dict[str, Any]) -> str:
    payload = json.dumps(config, ensure_ascii=False, separators=(",", ":"))
    token = _credential_cipher().encrypt(payload.encode("utf-8")).decode("ascii")
    return f"{VK_OUTREACH_CREDENTIAL_PREFIX}{token}"


def load_vk_outreach_config(sender_account: dict[str, Any]) -> dict[str, Any]:
    encrypted = _text(sender_account.get("auth_data_encrypted"))
    if not encrypted.startswith(VK_OUTREACH_CREDENTIAL_PREFIX):
        raise VkOutreachAdapterError(
            "vk_credentials_missing",
            "VK outreach credentials are unavailable",
        )
    token = encrypted[len(VK_OUTREACH_CREDENTIAL_PREFIX):]
    try:
        decoded = _credential_cipher().decrypt(token.encode("ascii")).decode("utf-8")
        payload = json.loads(decoded)
    except (InvalidToken, UnicodeError, ValueError, TypeError) as exc:
        raise VkOutreachAdapterError(
            "vk_credentials_invalid",
            "VK outreach credentials cannot be decrypted",
        ) from exc
    if not isinstance(payload, dict) or not _text(payload.get("access_token")):
        raise VkOutreachAdapterError("vk_credentials_invalid", "VK outreach credentials are invalid")
    return payload


def refresh_vk_outreach_config(sender_account: dict[str, Any]) -> tuple[dict[str, Any], str]:
    current = load_vk_outreach_config(sender_account)
    refreshed = refresh_vk_oauth_tokens(
        refresh_token=_text(current.get("refresh_token")),
        device_id=_text(current.get("device_id")),
        scopes=VK_OUTREACH_SCOPES,
    )
    next_config = {
        **current,
        "access_token": _text(refreshed.get("access_token")),
        "refresh_token": _text(refreshed.get("refresh_token")) or _text(current.get("refresh_token")),
        "expires_in": refreshed.get("expires_in"),
        "expires_at": oauth_token_expiry(refreshed.get("expires_in")),
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
    }
    if not next_config["access_token"]:
        raise VkOutreachAdapterError("vk_auth_invalid", "VK did not renew authorization")
    return next_config, encrypt_vk_outreach_config(next_config)


def ensure_vk_outreach_config(sender_account: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    current = load_vk_outreach_config(sender_account)
    if _text(current.get("account_kind")) == "community":
        return current, None
    expires_at_raw = _text(current.get("expires_at"))
    if not expires_at_raw:
        return current, None
    try:
        expires_at = datetime.fromisoformat(expires_at_raw.replace("Z", "+00:00"))
    except ValueError:
        return current, None
    if expires_at > datetime.now(timezone.utc) + timedelta(minutes=2):
        return current, None
    return refresh_vk_outreach_config(sender_account)


def _vk_api_version() -> str:
    return _text(os.getenv("VK_API_VERSION")) or "5.199"


def classify_vk_api_error(error: dict[str, Any]) -> VkOutreachAdapterError:
    try:
        code = int(error.get("error_code") or 0)
    except (TypeError, ValueError):
        code = 0
    provider_message = _text(error.get("error_msg"))
    mapping = {
        5: ("vk_auth_invalid", "VK authorization expired", False),
        6: ("vk_rate_limit", "VK temporarily limited API requests", True),
        9: ("vk_flood_control", "VK flood control blocked the request", True),
        14: ("vk_captcha_required", "VK requires an account check", False),
        901: ("vk_recipient_permission_required", "Recipient does not allow this message", False),
        902: ("vk_recipient_privacy", "Recipient privacy settings block this message", False),
        932: ("vk_peer_unavailable", "VK account cannot interact with this recipient", False),
        939: ("vk_message_request_exists", "A VK message request already exists", False),
        950: ("vk_reply_window_closed", "VK reply window is closed", False),
        987: ("vk_message_request_required", "VK requires a message request", False),
        988: ("vk_message_request_pending", "A VK message request is pending", False),
        1051: (
            "vk_profile_type_unsupported",
            "VK авторизовал профиль, но этот тип токена не даёт LocalOS доступ к разделу личных сообщений. "
            "Автоматический аутрич от личного профиля VK сейчас недоступен. Сообщения не отправлялись.",
            False,
        ),
        1117: ("vk_auth_expired", "VK authorization expired", False),
    }
    reason_code, message, retryable = mapping.get(
        code,
        ("vk_provider_failed", provider_message or "VK API request failed", code in {1, 10, 29}),
    )
    return VkOutreachAdapterError(reason_code, message, retryable=retryable)


def vk_api_call(method: str, access_token: str, params: dict[str, Any]) -> Any:
    token = _text(access_token)
    if not token:
        raise VkOutreachAdapterError("vk_auth_invalid", "VK access token is missing")
    request_params = dict(params)
    request_params["access_token"] = token
    request_params["v"] = _vk_api_version()
    try:
        response = requests.post(
            f"https://api.vk.com/method/{method}",
            data=request_params,
            timeout=20,
            **build_requests_proxy_kwargs(),
        )
        body = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise VkOutreachAdapterError(
            "vk_transport_failed",
            "VK did not answer the connection check",
            retryable=True,
        ) from exc
    if response.status_code >= 500 or not isinstance(body, dict):
        raise VkOutreachAdapterError(
            "vk_transport_failed",
            "VK did not answer the connection check",
            retryable=True,
        )
    error = body.get("error")
    if isinstance(error, dict):
        raise classify_vk_api_error(error)
    return body.get("response")


def verify_vk_outreach_access(access_token: str) -> dict[str, Any]:
    if _text(access_token).startswith("vk2."):
        raise classify_vk_api_error({"error_code": 1051})
    users = vk_api_call("users.get", access_token, {"fields": "screen_name"})
    user = users[0] if isinstance(users, list) and users and isinstance(users[0], dict) else {}
    user_id = _text(user.get("id"))
    if not user_id:
        raise VkOutreachAdapterError("vk_identity_missing", "VK did not return the account identity")
    # Count zero proves that the token can read the messages surface without
    # importing personal dialogs during connection.
    vk_api_call("messages.getConversations", access_token, {"count": 0})
    first_name = _text(user.get("first_name"))
    last_name = _text(user.get("last_name"))
    display_name = " ".join(item for item in (first_name, last_name) if item) or f"VK ID {user_id}"
    screen_name = _text(user.get("screen_name"))
    return {
        "user_id": user_id,
        "screen_name": screen_name or f"id{user_id}",
        "display_name": display_name,
        "profile_url": f"https://vk.com/{screen_name or f'id{user_id}'}",
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "capabilities": {
            "direct_send": True,
            "reply_sync": True,
            "provider": "vk_user_api",
        },
    }


def normalize_vk_community_reference(value: Any) -> str:
    raw = _text(value)
    if not raw:
        raise VkOutreachAdapterError("vk_group_required", "Укажите ссылку на сообщество VK")
    candidate = raw
    if "://" in raw:
        parsed = urlsplit(raw)
        host = parsed.netloc.lower().removeprefix("www.")
        if host not in {"vk.com", "m.vk.com", "vk.ru", "m.vk.ru"}:
            raise VkOutreachAdapterError("vk_group_invalid", "Укажите ссылку на сообщество VK")
        candidate = parsed.path.strip("/").split("/", 1)[0]
    candidate = candidate.split("?", 1)[0].split("#", 1)[0].strip().lstrip("@")
    if candidate.startswith("-"):
        candidate = candidate[1:]
    if candidate.lower().startswith("club") and candidate[4:].isdigit():
        candidate = candidate[4:]
    if candidate.lower().startswith("public") and candidate[6:].isdigit():
        candidate = candidate[6:]
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,64}", candidate):
        raise VkOutreachAdapterError("vk_group_invalid", "Не удалось распознать сообщество VK")
    return candidate


def _vk_group_items(response: Any) -> list[dict[str, Any]]:
    items = response.get("groups") if isinstance(response, dict) else response
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def verify_vk_community_access(access_token: str, community_reference: Any) -> dict[str, Any]:
    token = _text(access_token)
    if not token:
        raise VkOutreachAdapterError("vk_group_token_required", "Вставьте ключ доступа сообщества VK")
    reference = normalize_vk_community_reference(community_reference)
    permissions_response = vk_api_call("groups.getTokenPermissions", token, {})
    permissions = permissions_response.get("permissions") if isinstance(permissions_response, dict) else []
    permission_names = {
        _text(item.get("name"))
        for item in permissions if isinstance(item, dict)
    }
    if "messages" not in permission_names:
        raise VkOutreachAdapterError(
            "vk_group_messages_permission_required",
            "Создайте ключ VK с доступом к сообщениям сообщества",
        )
    groups = _vk_group_items(vk_api_call(
        "groups.getById",
        token,
        {"group_ids": reference, "fields": "screen_name,photo_200"},
    ))
    group = groups[0] if groups else {}
    group_id = _text(group.get("id"))
    if not group_id:
        raise VkOutreachAdapterError("vk_group_not_found", "VK не нашёл указанное сообщество")
    # This call binds the supplied community token to the selected group without
    # reading dialogs or sending a message. A token from another group is denied.
    vk_api_call("groups.getLongPollSettings", token, {"group_id": group_id})
    vk_api_call("messages.getConversations", token, {"count": 0})
    screen_name = _text(group.get("screen_name")) or reference
    return {
        "group_id": group_id,
        "screen_name": screen_name,
        "display_name": _text(group.get("name")) or f"VK {group_id}",
        "profile_url": f"https://vk.ru/{screen_name}",
        "avatar_url": _text(group.get("photo_200")) or None,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "capabilities": {
            "direct_send": True,
            "reply_sync": True,
            "provider": "vk_community_api",
            "account_kind": "community",
            "group_id": group_id,
            "profile_url": f"https://vk.ru/{screen_name}",
            "avatar_url": _text(group.get("photo_200")) or None,
        },
    }


def normalize_vk_recipient(value: Any) -> dict[str, str] | None:
    raw = _text(value)
    if not raw:
        return None
    candidate = raw
    if "://" in raw:
        parsed = urlsplit(raw)
        if parsed.netloc.lower().removeprefix("www.") not in {"vk.com", "m.vk.com"}:
            return None
        candidate = parsed.path.strip("/").split("/", 1)[0]
    candidate = candidate.split("?", 1)[0].split("#", 1)[0].strip().lstrip("@")
    if not candidate or candidate.lower() in {"feed", "im", "mail", "messages"}:
        return None
    if candidate.lower().startswith("id") and candidate[2:].isdigit():
        return {"recipient_kind": "user_id", "recipient_value": candidate[2:]}
    if candidate.isdigit():
        return {"recipient_kind": "user_id", "recipient_value": candidate}
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,64}", candidate):
        return None
    return {"recipient_kind": "domain", "recipient_value": candidate}


def resolve_vk_peer(access_token: str, recipient: dict[str, str]) -> dict[str, str]:
    if recipient.get("recipient_kind") == "user_id":
        return {**recipient, "peer_id": recipient["recipient_value"]}
    resolved = vk_api_call("utils.resolveScreenName", access_token, {"screen_name": recipient["recipient_value"]})
    if not isinstance(resolved, dict) or resolved.get("type") != "user" or not resolved.get("object_id"):
        raise VkOutreachAdapterError("vk_recipient_invalid", "VK recipient is not a personal profile")
    return {**recipient, "peer_id": _text(resolved.get("object_id"))}


def _random_id(idempotency_key: str) -> int:
    digest = hashlib.sha256(_text(idempotency_key).encode("utf-8")).digest()
    return max(1, int.from_bytes(digest[:4], "big") & 0x7FFFFFFF)


def preflight_vk_sender(sender_account: dict[str, Any]) -> dict[str, Any]:
    config = load_vk_outreach_config(sender_account)
    if _text(config.get("account_kind")) == "community":
        verification = verify_vk_community_access(
            _text(config.get("access_token")),
            config.get("group_id") or config.get("screen_name"),
        )
    else:
        verification = verify_vk_outreach_access(_text(config.get("access_token")))
    return {
        "ready": True,
        "sender_identity": verification["profile_url"],
        "display_name": verification["display_name"],
        "capabilities": verification["capabilities"],
        "messages_sent": 0,
    }


def send_vk_message(
    sender_account: dict[str, Any],
    *,
    recipient_value: str,
    body: str,
    idempotency_key: str,
) -> dict[str, Any]:
    recipient = normalize_vk_recipient(recipient_value)
    if not recipient:
        raise VkOutreachAdapterError("vk_recipient_invalid", "VK recipient is invalid")
    config = load_vk_outreach_config(sender_account)
    access_token = _text(config.get("access_token"))
    resolved = resolve_vk_peer(access_token, recipient)
    send_params = {
        "peer_id": resolved["peer_id"],
        "random_id": _random_id(idempotency_key),
        "message": _text(body),
    }
    if _text(config.get("account_kind")) == "community":
        send_params["group_id"] = _text(config.get("group_id"))
    response = vk_api_call(
        "messages.send",
        access_token,
        send_params,
    )
    provider_message_id = _text(response)
    if not provider_message_id:
        raise VkOutreachAdapterError("vk_send_failed", "VK did not confirm the message")
    return {
        "success": True,
        "provider_name": "vk_community_api" if _text(config.get("account_kind")) == "community" else "vk_user_api",
        "provider_account_id": _text(sender_account.get("id")),
        "provider_message_id": provider_message_id,
        "recipient_kind": "peer_id",
        "recipient_value": resolved["peer_id"],
    }


def fetch_vk_replies(
    sender_account: dict[str, Any],
    *,
    peer_id: str,
    sent_after: datetime | None,
    after_message_id: str | None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    config = load_vk_outreach_config(sender_account)
    response = vk_api_call(
        "messages.getHistory",
        _text(config.get("access_token")),
        {"peer_id": _text(peer_id), "count": max(1, min(int(limit or 50), 200))},
    )
    items = response.get("items") if isinstance(response, dict) else []
    try:
        minimum_message_id = int(after_message_id or 0)
    except (TypeError, ValueError):
        minimum_message_id = 0
    replies: list[dict[str, Any]] = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict) or bool(item.get("out")):
            continue
        try:
            message_id = int(item.get("id") or 0)
            occurred_at = datetime.fromtimestamp(int(item.get("date") or 0), tz=timezone.utc)
        except (TypeError, ValueError, OSError, OverflowError):
            continue
        if minimum_message_id and message_id <= minimum_message_id:
            continue
        if sent_after and occurred_at < sent_after:
            continue
        replies.append({
            "provider_event_id": f"vk:{sender_account.get('id')}:{message_id}"[:255],
            "message_id": str(message_id),
            "peer_id": _text(item.get("peer_id") or peer_id),
            "from_id": _text(item.get("from_id")),
            "body": _text(item.get("text"))[:10000],
            "occurred_at": occurred_at,
        })
    return sorted(replies, key=lambda item: item["occurred_at"])
