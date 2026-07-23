from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Any

import requests

from core.telegram_network import build_requests_proxy_kwargs


VK_OAUTH_SCOPES = ("wall", "photos", "groups")
VK_OAUTH_STATE_TTL_SECONDS = 15 * 60
VK_API_PERMISSION_PHOTOS = 4
VK_API_PERMISSION_WALL = 8192
VK_API_PERMISSION_GROUPS = 262144


class VkOAuthError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _base64url_decode(value: str) -> bytes:
    clean = str(value or "").strip()
    return base64.urlsafe_b64decode((clean + ("=" * (-len(clean) % 4))).encode("ascii"))


def _state_secret() -> bytes:
    secret = str(os.getenv("VK_OAUTH_STATE_SECRET") or "").strip()
    if not secret:
        raise VkOAuthError(
            "oauth_not_configured",
            "Подключение VK ещё не настроено администратором LocalOS.",
        )
    return secret.encode("utf-8")


def vk_oauth_client_id() -> str:
    client_id = str(os.getenv("VK_OAUTH_CLIENT_ID") or "").strip()
    if not client_id:
        raise VkOAuthError(
            "oauth_not_configured",
            "Подключение VK ещё не настроено администратором LocalOS.",
        )
    return client_id


def vk_oauth_redirect_uri() -> str:
    return str(
        os.getenv("VK_OAUTH_REDIRECT_URI")
        or "https://localos.pro/api/vk/oauth/callback"
    ).strip()


def vk_api_version() -> str:
    return str(os.getenv("VK_API_VERSION") or "5.199").strip()


def normalize_vk_group_id(value: Any) -> str:
    clean = str(value or "").strip()
    if clean.startswith("-"):
        clean = clean[1:]
    if not clean or not clean.isdigit():
        raise VkOAuthError(
            "invalid_group_id",
            "Укажите числовой ID сообщества VK.",
        )
    return clean


def validate_vk_pkce_value(value: Any, field_name: str) -> str:
    clean = str(value or "").strip()
    if not 43 <= len(clean) <= 128 or not re.fullmatch(r"[A-Za-z0-9_-]+", clean):
        raise VkOAuthError("invalid_pkce", f"Некорректное поле {field_name}.")
    return clean


def encode_vk_oauth_state(payload: dict[str, Any]) -> str:
    state_payload = dict(payload)
    state_payload["version"] = 1
    state_payload["expires_at"] = int(time.time()) + VK_OAUTH_STATE_TTL_SECONDS
    state_payload["nonce"] = secrets.token_urlsafe(18)
    encoded = _base64url_encode(
        json.dumps(state_payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    )
    signature = _base64url_encode(
        hmac.new(_state_secret(), encoded.encode("ascii"), hashlib.sha256).digest()
    )
    return f"v1{encoded}{signature}"


def decode_vk_oauth_state(state: Any) -> dict[str, Any]:
    raw = str(state or "").strip()
    if raw.startswith("v1."):
        parts = raw.split(".")
        if len(parts) != 3:
            raise VkOAuthError("invalid_state", "Подключение VK устарело. Начните ещё раз.")
        encoded = parts[1]
        signature = parts[2]
    elif raw.startswith("v1") and len(raw) > 45:
        encoded = raw[2:-43]
        signature = raw[-43:]
    else:
        raise VkOAuthError("invalid_state", "Подключение VK устарело. Начните ещё раз.")
    expected = _base64url_encode(
        hmac.new(_state_secret(), encoded.encode("ascii"), hashlib.sha256).digest()
    )
    if not hmac.compare_digest(expected, signature):
        raise VkOAuthError("invalid_state", "Не удалось проверить подключение VK. Начните ещё раз.")
    try:
        payload = json.loads(_base64url_decode(encoded).decode("utf-8"))
    except Exception:
        raise VkOAuthError("invalid_state", "Не удалось прочитать подключение VK. Начните ещё раз.")
    if not isinstance(payload, dict):
        raise VkOAuthError("invalid_state", "Не удалось прочитать подключение VK. Начните ещё раз.")
    if int(payload.get("expires_at") or 0) < int(time.time()):
        raise VkOAuthError("expired_state", "Время подключения VK истекло. Начните ещё раз.")
    return payload


def vk_pkce_challenge(code_verifier: str) -> str:
    verifier = validate_vk_pkce_value(code_verifier, "code_verifier")
    return _base64url_encode(hashlib.sha256(verifier.encode("ascii")).digest())


def build_vk_authorization_url(
    *,
    state: str,
    code_challenge: str,
    scopes: tuple[str, ...] | None = None,
) -> str:
    challenge = validate_vk_pkce_value(code_challenge, "code_challenge")
    requested_scopes = scopes or VK_OAUTH_SCOPES
    query = urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": vk_oauth_client_id(),
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "redirect_uri": vk_oauth_redirect_uri(),
            "scope": " ".join(requested_scopes),
            "state": state,
            "prompt": "consent",
            "provider": "vkid",
            "lang_id": "0",
            "scheme": "light",
        }
    )
    return f"https://id.vk.com/authorize?{query}"


def _oauth_request(payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(
        "https://id.vk.com/oauth2/auth",
        data=payload,
        timeout=20,
        **build_requests_proxy_kwargs(),
    )
    try:
        body = response.json()
    except ValueError:
        body = {}
    if response.status_code != 200 or not isinstance(body, dict) or body.get("error"):
        error_description = ""
        if isinstance(body, dict):
            error_description = str(body.get("error_description") or body.get("error") or "").strip()
        raise VkOAuthError(
            "token_exchange_failed",
            error_description or "VK не выдал доступ. Повторите подключение.",
        )
    return body


def exchange_vk_authorization_code(
    *,
    code: str,
    device_id: str,
    code_verifier: str,
) -> dict[str, Any]:
    verifier = validate_vk_pkce_value(code_verifier, "code_verifier")
    clean_code = str(code or "").strip()
    clean_device_id = str(device_id or "").strip()
    if not clean_code or not clean_device_id:
        raise VkOAuthError("missing_callback_data", "VK не вернул данные подключения. Начните ещё раз.")
    return _oauth_request(
        {
            "grant_type": "authorization_code",
            "client_id": vk_oauth_client_id(),
            "code_verifier": verifier,
            "redirect_uri": vk_oauth_redirect_uri(),
            "code": clean_code,
            "device_id": clean_device_id,
        }
    )


def refresh_vk_oauth_tokens(
    *,
    refresh_token: str,
    device_id: str,
    scopes: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    clean_refresh_token = str(refresh_token or "").strip()
    clean_device_id = str(device_id or "").strip()
    if not clean_refresh_token or not clean_device_id:
        raise VkOAuthError("refresh_unavailable", "Нужно заново подключить VK.")
    return _oauth_request(
        {
            "grant_type": "refresh_token",
            "client_id": vk_oauth_client_id(),
            "refresh_token": clean_refresh_token,
            "device_id": clean_device_id,
            "scope": " ".join(scopes or VK_OAUTH_SCOPES),
        }
    )


def _vk_api_call(method: str, access_token: str, params: dict[str, Any]) -> Any:
    request_params = dict(params)
    request_params["access_token"] = access_token
    request_params["v"] = vk_api_version()
    response = requests.get(
        f"https://api.vk.com/method/{method}",
        params=request_params,
        timeout=15,
        **build_requests_proxy_kwargs(),
    )
    try:
        body = response.json()
    except ValueError:
        body = {}
    if response.status_code != 200 or not isinstance(body, dict):
        raise VkOAuthError("vk_api_unavailable", "VK не ответил на проверку подключения.")
    error = body.get("error")
    if isinstance(error, dict):
        message = str(error.get("error_msg") or "VK API error").strip()
        raise VkOAuthError("vk_api_denied", message)
    return body.get("response")


def verify_vk_oauth_access(access_token: str, group_id: str) -> dict[str, Any]:
    token = str(access_token or "").strip()
    normalized_group_id = normalize_vk_group_id(group_id)
    if not token:
        raise VkOAuthError("missing_access_token", "VK не выдал токен доступа.")
    if token.startswith("vk2."):
        raise VkOAuthError(
            "vk_id_publish_unsupported",
            "VK ID подходит для входа, но не даёт права публикации в сообществе. Подключите ключ сообщества VK.",
        )

    permissions_response = _vk_api_call("account.getAppPermissions", token, {})
    permissions = int(permissions_response or 0)
    required_permissions = VK_API_PERMISSION_PHOTOS | VK_API_PERMISSION_WALL | VK_API_PERMISSION_GROUPS
    if permissions & required_permissions != required_permissions:
        raise VkOAuthError(
            "missing_permissions",
            "Разрешите LocalOS публиковать записи и фотографии и видеть ваши сообщества.",
        )

    admin_groups_response = _vk_api_call(
        "groups.get",
        token,
        {"filter": "admin", "extended": "1", "count": "1000"},
    )
    admin_items = admin_groups_response.get("items") if isinstance(admin_groups_response, dict) else []
    matched_group = {}
    for item in admin_items if isinstance(admin_items, list) else []:
        if isinstance(item, dict) and str(item.get("id") or "") == normalized_group_id:
            matched_group = item
            break
    if not matched_group:
        raise VkOAuthError(
            "not_group_admin",
            "Этот аккаунт VK не управляет указанным сообществом.",
        )

    _vk_api_call(
        "wall.get",
        token,
        {"owner_id": f"-{normalized_group_id}", "count": "1", "filter": "owner"},
    )
    users_response = _vk_api_call("users.get", token, {})
    user = users_response[0] if isinstance(users_response, list) and users_response else {}
    user_id = str(user.get("id") or "") if isinstance(user, dict) else ""
    group_name = str(matched_group.get("name") or "").strip()
    return {
        "group_id": normalized_group_id,
        "owner_id": f"-{normalized_group_id}",
        "group_name": group_name or f"VK {normalized_group_id}",
        "user_id": user_id,
        "permissions": permissions,
        "scope": list(VK_OAUTH_SCOPES),
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }


def oauth_token_expiry(expires_in: Any) -> str | None:
    try:
        lifetime = int(expires_in or 0)
    except (TypeError, ValueError):
        lifetime = 0
    if lifetime <= 0:
        return None
    return datetime.fromtimestamp(time.time() + lifetime, tz=timezone.utc).isoformat()
