from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Any

import requests

from core.telegram_network import build_requests_proxy_kwargs


META_OAUTH_SCOPES = (
    "business_management",
    "pages_show_list",
    "pages_read_engagement",
    "pages_manage_posts",
    "instagram_basic",
    "instagram_content_publish",
)
META_OAUTH_STATE_TTL_SECONDS = 15 * 60


class MetaOAuthError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _base64url_decode(value: str) -> bytes:
    clean = str(value or "").strip()
    return base64.urlsafe_b64decode((clean + ("=" * (-len(clean) % 4))).encode("ascii"))


def _state_secret() -> bytes:
    secret = str(os.getenv("META_OAUTH_STATE_SECRET") or "").strip()
    if not secret:
        raise MetaOAuthError(
            "oauth_not_configured",
            "Подключение Facebook и Instagram ещё не настроено администратором LocalOS.",
        )
    return secret.encode("utf-8")


def meta_oauth_app_id() -> str:
    app_id = str(os.getenv("META_OAUTH_APP_ID") or "").strip()
    if not app_id:
        raise MetaOAuthError(
            "oauth_not_configured",
            "Подключение Facebook и Instagram ещё не настроено администратором LocalOS.",
        )
    return app_id


def meta_oauth_app_secret() -> str:
    app_secret = str(os.getenv("META_OAUTH_APP_SECRET") or "").strip()
    if not app_secret:
        raise MetaOAuthError(
            "oauth_not_configured",
            "Подключение Facebook и Instagram ещё не настроено администратором LocalOS.",
        )
    return app_secret


def meta_oauth_configuration_id() -> str:
    configuration_id = str(os.getenv("META_OAUTH_CONFIG_ID") or "").strip()
    if not configuration_id:
        raise MetaOAuthError(
            "oauth_not_configured",
            "Подключение Facebook и Instagram ещё не настроено администратором LocalOS.",
        )
    return configuration_id


def meta_oauth_redirect_uri() -> str:
    return str(
        os.getenv("META_OAUTH_REDIRECT_URI")
        or "https://localos.pro/api/meta/oauth/callback"
    ).strip()


def meta_graph_api_version() -> str:
    return str(os.getenv("META_GRAPH_API_VERSION") or "v25.0").strip().strip("/")


def decode_meta_data_deletion_request(signed_request: Any) -> dict[str, Any]:
    raw = str(signed_request or "").strip()
    parts = raw.split(".")
    if len(parts) != 2:
        raise MetaOAuthError(
            "invalid_deletion_request",
            "Meta передала некорректный запрос на удаление данных.",
        )
    encoded_signature, encoded_payload = parts
    try:
        signature = _base64url_decode(encoded_signature)
        payload_bytes = _base64url_decode(encoded_payload)
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        raise MetaOAuthError(
            "invalid_deletion_request",
            "Meta передала некорректный запрос на удаление данных.",
        )
    expected_signature = hmac.new(
        meta_oauth_app_secret().encode("utf-8"),
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(expected_signature, signature):
        raise MetaOAuthError(
            "invalid_deletion_signature",
            "Не удалось подтвердить запрос Meta на удаление данных.",
        )
    if not isinstance(payload, dict):
        raise MetaOAuthError(
            "invalid_deletion_request",
            "Meta передала некорректный запрос на удаление данных.",
        )
    algorithm = str(payload.get("algorithm") or "").strip().upper()
    if algorithm and algorithm != "HMAC-SHA256":
        raise MetaOAuthError(
            "unsupported_deletion_signature",
            "Meta использовала неподдерживаемую подпись запроса.",
        )
    if not str(payload.get("user_id") or "").strip():
        raise MetaOAuthError(
            "missing_meta_user",
            "Meta не передала пользователя для удаления данных.",
        )
    return payload


def encode_meta_oauth_state(payload: dict[str, Any]) -> str:
    state_payload = dict(payload)
    state_payload["version"] = 1
    state_payload["expires_at"] = int(time.time()) + META_OAUTH_STATE_TTL_SECONDS
    state_payload["nonce"] = secrets.token_urlsafe(18)
    encoded = _base64url_encode(
        json.dumps(state_payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    )
    signature = _base64url_encode(
        hmac.new(_state_secret(), encoded.encode("ascii"), hashlib.sha256).digest()
    )
    return f"v1.{encoded}.{signature}"


def decode_meta_oauth_state(state: Any) -> dict[str, Any]:
    raw = str(state or "").strip()
    parts = raw.split(".")
    if len(parts) != 3 or parts[0] != "v1":
        raise MetaOAuthError("invalid_state", "Подключение Meta устарело. Начните ещё раз.")
    encoded = parts[1]
    signature = parts[2]
    expected = _base64url_encode(
        hmac.new(_state_secret(), encoded.encode("ascii"), hashlib.sha256).digest()
    )
    if not hmac.compare_digest(expected, signature):
        raise MetaOAuthError("invalid_state", "Не удалось проверить подключение Meta. Начните ещё раз.")
    try:
        payload = json.loads(_base64url_decode(encoded).decode("utf-8"))
    except Exception:
        raise MetaOAuthError("invalid_state", "Не удалось прочитать подключение Meta. Начните ещё раз.")
    if not isinstance(payload, dict):
        raise MetaOAuthError("invalid_state", "Не удалось прочитать подключение Meta. Начните ещё раз.")
    if int(payload.get("expires_at") or 0) < int(time.time()):
        raise MetaOAuthError("expired_state", "Время подключения Meta истекло. Начните ещё раз.")
    return payload


def build_meta_authorization_url(*, state: str) -> str:
    query = urllib.parse.urlencode(
        {
            "client_id": meta_oauth_app_id(),
            "config_id": meta_oauth_configuration_id(),
            "redirect_uri": meta_oauth_redirect_uri(),
            "state": state,
            "response_type": "code",
            "scope": ",".join(META_OAUTH_SCOPES),
            "auth_type": "rerequest",
        }
    )
    return f"https://www.facebook.com/{meta_graph_api_version()}/dialog/oauth?{query}"


def _graph_request(
    path: str,
    *,
    params: dict[str, Any],
    access_token: str | None = None,
) -> dict[str, Any]:
    request_params = dict(params)
    if access_token:
        request_params["access_token"] = access_token
    clean_path = str(path or "").strip().lstrip("/")
    response = requests.get(
        f"https://graph.facebook.com/{meta_graph_api_version()}/{clean_path}",
        params=request_params,
        timeout=20,
        **build_requests_proxy_kwargs(),
    )
    try:
        body = response.json()
    except ValueError:
        body = {}
    graph_error = body.get("error") if isinstance(body, dict) else None
    if response.status_code != 200 or not isinstance(body, dict) or isinstance(graph_error, dict):
        message = ""
        code = "graph_error"
        if isinstance(graph_error, dict):
            message = str(graph_error.get("message") or "").strip()
            code = str(graph_error.get("code") or code)
        raise MetaOAuthError(code, message or "Meta не ответила на проверку подключения.")
    return body


def exchange_meta_authorization_code(code: str) -> dict[str, Any]:
    clean_code = str(code or "").strip()
    if not clean_code:
        raise MetaOAuthError("missing_callback_data", "Meta не вернула код подключения. Начните ещё раз.")
    short_lived = _graph_request(
        "oauth/access_token",
        params={
            "client_id": meta_oauth_app_id(),
            "client_secret": meta_oauth_app_secret(),
            "redirect_uri": meta_oauth_redirect_uri(),
            "code": clean_code,
        },
    )
    short_token = str(short_lived.get("access_token") or "").strip()
    if not short_token:
        raise MetaOAuthError("token_exchange_failed", "Meta не выдала доступ. Повторите подключение.")
    long_lived = _graph_request(
        "oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": meta_oauth_app_id(),
            "client_secret": meta_oauth_app_secret(),
            "fb_exchange_token": short_token,
        },
    )
    access_token = str(long_lived.get("access_token") or short_token).strip()
    expires_in = int(long_lived.get("expires_in") or short_lived.get("expires_in") or 0)
    return {
        "access_token": access_token,
        "token_type": str(long_lived.get("token_type") or short_lived.get("token_type") or "bearer"),
        "expires_at": int(time.time()) + expires_in if expires_in > 0 else None,
    }


def inspect_meta_access_token(access_token: str) -> dict[str, Any]:
    clean_token = str(access_token or "").strip()
    if not clean_token:
        raise MetaOAuthError("missing_access_token", "Meta не выдала токен доступа.")
    app_access_token = f"{meta_oauth_app_id()}|{meta_oauth_app_secret()}"
    body = _graph_request(
        "debug_token",
        params={"input_token": clean_token},
        access_token=app_access_token,
    )
    data = body.get("data") if isinstance(body.get("data"), dict) else {}
    if not data.get("is_valid"):
        raise MetaOAuthError("invalid_access_token", "Доступ Meta недействителен. Подключите аккаунт заново.")
    scopes = [str(item) for item in data.get("scopes") or [] if str(item).strip()]
    missing = [scope for scope in META_OAUTH_SCOPES if scope not in scopes]
    return {
        "user_id": str(data.get("user_id") or ""),
        "app_id": str(data.get("app_id") or ""),
        "expires_at": int(data.get("expires_at") or 0) or None,
        "scopes": scopes,
        "missing_scopes": missing,
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }


def list_meta_assets(user_access_token: str) -> list[dict[str, Any]]:
    token = str(user_access_token or "").strip()
    if not token:
        raise MetaOAuthError("missing_access_token", "Подключите Meta заново, чтобы получить список страниц.")
    body = _graph_request(
        "me/accounts",
        params={
            "fields": "id,name,access_token,tasks,instagram_business_account{id,username,name,profile_picture_url}",
            "limit": "200",
        },
        access_token=token,
    )
    assets = []
    for item in body.get("data") or []:
        if not isinstance(item, dict):
            continue
        page_id = str(item.get("id") or "").strip()
        page_token = str(item.get("access_token") or "").strip()
        if not page_id or not page_token:
            continue
        ig_account = item.get("instagram_business_account")
        if not isinstance(ig_account, dict):
            ig_account = {}
        tasks = [str(task) for task in item.get("tasks") or [] if str(task).strip()]
        assets.append(
            {
                "page_id": page_id,
                "page_name": str(item.get("name") or f"Facebook Page {page_id}").strip(),
                "page_access_token": page_token,
                "tasks": tasks,
                "ig_user_id": str(ig_account.get("id") or "").strip(),
                "ig_username": str(ig_account.get("username") or "").strip(),
                "ig_name": str(ig_account.get("name") or "").strip(),
                "ig_profile_picture_url": str(ig_account.get("profile_picture_url") or "").strip(),
            }
        )
    return assets


def public_meta_asset(asset: dict[str, Any]) -> dict[str, Any]:
    return {
        "page_id": str(asset.get("page_id") or ""),
        "page_name": str(asset.get("page_name") or ""),
        "tasks": asset.get("tasks") or [],
        "ig_user_id": str(asset.get("ig_user_id") or ""),
        "ig_username": str(asset.get("ig_username") or ""),
        "ig_name": str(asset.get("ig_name") or ""),
        "ig_profile_picture_url": str(asset.get("ig_profile_picture_url") or ""),
    }
