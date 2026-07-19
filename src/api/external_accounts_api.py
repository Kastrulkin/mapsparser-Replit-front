"""External account and YCLIENTS API routes.

This blueprint keeps the historical route paths while main.py is split by domain.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import sys
import urllib.parse
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from flask import Blueprint, current_app, jsonify, redirect, request

from auth_encryption import decrypt_auth_data, encrypt_auth_data
from auth_system import verify_session
from core.helpers import get_business_owner_id
from core.map_url_normalizer import is_google_map_url
from core.parsing_runtime_config import resolve_map_source_for_queue
from core.telegram_network import build_requests_proxy_kwargs
from database_manager import DatabaseManager
from parsequeue_status import STATUS_COMPLETED, STATUS_ERROR
from services.vk_oauth_service import (
    VkOAuthError,
    build_vk_authorization_url,
    decode_vk_oauth_state,
    encode_vk_oauth_state,
    exchange_vk_authorization_code,
    normalize_vk_group_id,
    oauth_token_expiry,
    validate_vk_pkce_value,
    verify_vk_oauth_access,
    vk_api_version,
    vk_pkce_challenge,
)
from services.meta_oauth_service import (
    META_OAUTH_SCOPES,
    MetaOAuthError,
    build_meta_authorization_url,
    decode_meta_data_deletion_request,
    decode_meta_oauth_state,
    encode_meta_oauth_state,
    exchange_meta_authorization_code,
    inspect_meta_access_token,
    list_meta_assets,
    meta_graph_api_version,
    public_meta_asset,
)


logger = logging.getLogger(__name__)
external_accounts_bp = Blueprint("external_accounts_api", __name__)

DEFAULT_VK_RETURN_PATH = "/dashboard/settings/integrations?focus=vk"
DEFAULT_META_RETURN_PATH = "/dashboard/settings/integrations?focus=meta"


try:
    from yandex_business_parser import YandexBusinessParser
    from yandex_business_sync_worker import YandexBusinessSyncWorker
except ImportError:
    YandexBusinessParser = None
    YandexBusinessSyncWorker = None


def _row_to_dict(cursor, row):
    if row is None:
        return None
    if hasattr(row, "keys"):
        return {k: row[k] for k in row.keys()}
    cols = [d[0] for d in cursor.description]
    return dict(zip(cols, row))


def _table_columns(cursor, table_name: str) -> set:
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        """,
        (table_name.lower(),),
    )
    cols = set()
    for row in cursor.fetchall() or []:
        if hasattr(row, "get"):
            name = row.get("column_name")
        else:
            name = row[0] if row else None
        if name:
            cols.add(str(name).lower())
    return cols


def _safe_vk_return_path(value: Any) -> str:
    clean = str(value or "").strip()
    if not clean or clean.startswith("//") or "\r" in clean or "\n" in clean:
        return DEFAULT_VK_RETURN_PATH
    if not clean.startswith("/dashboard/"):
        return DEFAULT_VK_RETURN_PATH
    return clean[:500]


def _append_vk_auth_params(path: str, params: dict[str, Any]) -> str:
    safe_path = _safe_vk_return_path(path)
    parsed = urllib.parse.urlsplit(safe_path)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    for key, value in params.items():
        query.append((str(key), str(value or "")))
    return urllib.parse.urlunsplit(("", "", parsed.path, urllib.parse.urlencode(query), ""))


def _safe_meta_return_path(value: Any) -> str:
    clean = str(value or "").strip()
    if not clean or clean.startswith("//") or "\r" in clean or "\n" in clean:
        return DEFAULT_META_RETURN_PATH
    if not clean.startswith("/dashboard/"):
        return DEFAULT_META_RETURN_PATH
    return clean[:500]


def _append_meta_auth_params(path: str, params: dict[str, Any]) -> str:
    safe_path = _safe_meta_return_path(path)
    parsed = urllib.parse.urlsplit(safe_path)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    for key, value in params.items():
        query.append((str(key), str(value or "")))
    return urllib.parse.urlunsplit(("", "", parsed.path, urllib.parse.urlencode(query), ""))


def _require_vk_business_access(business_id: str):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None, None, (jsonify({"error": "Требуется авторизация"}), 401)
    token = auth_header.split(" ", 1)[1]
    user_data = verify_session(token)
    if not user_data:
        return None, None, (jsonify({"error": "Недействительный токен"}), 401)
    db = DatabaseManager()
    cursor = db.conn.cursor()
    owner_id = get_business_owner_id(cursor, business_id)
    if not owner_id:
        db.close()
        return None, None, (jsonify({"error": "Бизнес не найден"}), 404)
    if owner_id != user_data["user_id"] and not db.is_superadmin(user_data["user_id"]):
        db.close()
        return None, None, (jsonify({"error": "Нет доступа к этому бизнесу"}), 403)
    return user_data, db, None


def _vk_oauth_error_response(default_status: int = 400):
    error = sys.exc_info()[1]
    if isinstance(error, VkOAuthError):
        status = 503 if error.code == "oauth_not_configured" else default_status
        return jsonify({"success": False, "status": error.code, "error": str(error)}), status
    logger.exception("VK OAuth request failed")
    return jsonify({"success": False, "status": "oauth_failed", "error": "Не удалось подключить VK. Повторите позже."}), 502


def _meta_oauth_error_response(default_status: int = 400):
    error = sys.exc_info()[1]
    if isinstance(error, MetaOAuthError):
        status = 503 if error.code == "oauth_not_configured" else default_status
        return jsonify({"success": False, "status": error.code, "error": str(error)}), status
    logger.exception("Meta OAuth request failed")
    return jsonify({"success": False, "status": "oauth_failed", "error": "Не удалось подключить Facebook и Instagram. Повторите позже."}), 502


def _meta_account_auth_data(account: dict[str, Any] | None) -> dict[str, Any]:
    if not account:
        return {}
    decrypted = decrypt_auth_data(str(account.get("auth_data_encrypted") or "")) or ""
    try:
        parsed = json.loads(decrypted) if decrypted else {}
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _load_meta_account(cursor: Any, business_id: str, *, lock: bool = False) -> dict[str, Any] | None:
    lock_clause = " FOR UPDATE" if lock else ""
    cursor.execute(
        f"""
        SELECT id, business_id, source, external_id, display_name,
               auth_data_encrypted, is_active, last_error, created_at, updated_at
        FROM externalbusinessaccounts
        WHERE business_id = %s
          AND source IN ('meta', 'facebook', 'instagram')
        ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST
        LIMIT 1{lock_clause}
        """,
        (business_id,),
    )
    row = cursor.fetchone()
    return _row_to_dict(cursor, row) if row else None


def _upsert_meta_oauth_account(
    cursor: Any,
    *,
    business_id: str,
    user_token_payload: dict[str, Any],
    token_inspection: dict[str, Any],
    page_asset: dict[str, Any] | None = None,
    available_page_count: int | None = None,
) -> dict[str, Any]:
    existing = _load_meta_account(cursor, business_id, lock=True)
    existing_auth = _meta_account_auth_data(existing)
    account_id = str((existing or {}).get("id") or uuid.uuid4())
    auth_data = dict(existing_auth)
    auth_data.update(
        {
            "user_access_token": str(user_token_payload.get("access_token") or "").strip(),
            "user_token_expires_at": user_token_payload.get("expires_at"),
            "user_id": str(token_inspection.get("user_id") or "").strip(),
            "scope": token_inspection.get("scopes") or [],
            "missing_scopes": token_inspection.get("missing_scopes") or [],
            "api_version": meta_graph_api_version(),
            "auth_mode": "meta_oauth",
            "oauth_verified_at": token_inspection.get("verified_at"),
        }
    )
    if available_page_count is not None:
        auth_data["available_page_count"] = int(available_page_count)
    external_id = str((existing or {}).get("external_id") or "").strip() or None
    display_name = str((existing or {}).get("display_name") or "").strip() or "Meta: выберите страницу"
    if page_asset:
        page_id = str(page_asset.get("page_id") or "").strip()
        page_name = str(page_asset.get("page_name") or f"Facebook Page {page_id}").strip()
        ig_user_id = str(page_asset.get("ig_user_id") or "").strip()
        ig_username = str(page_asset.get("ig_username") or "").strip()
        auth_data.update(
            {
                "access_token": str(page_asset.get("page_access_token") or "").strip(),
                "page_id": page_id,
                "page_name": page_name,
                "page_tasks": page_asset.get("tasks") or [],
                "ig_user_id": ig_user_id,
                "instagram_business_account_id": ig_user_id,
                "ig_username": ig_username,
                "ig_name": str(page_asset.get("ig_name") or "").strip(),
                "ig_profile_picture_url": str(page_asset.get("ig_profile_picture_url") or "").strip(),
                "bound_at": datetime.utcnow().isoformat(),
            }
        )
        external_id = page_id
        display_name = f"{page_name} · @{ig_username}" if ig_username else page_name
    encrypted = encrypt_auth_data(json.dumps(auth_data, ensure_ascii=False))
    if existing:
        cursor.execute(
            """
            UPDATE externalbusinessaccounts
            SET source = 'meta', external_id = %s, display_name = %s,
                auth_data_encrypted = %s, is_active = TRUE,
                last_error = NULL, last_sync_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (external_id, display_name, encrypted, account_id),
        )
    else:
        cursor.execute(
            """
            INSERT INTO externalbusinessaccounts (
                id, business_id, source, external_id, display_name,
                auth_data_encrypted, is_active, last_sync_at, created_at, updated_at
            ) VALUES (
                %s, %s, 'meta', %s, %s, %s, TRUE,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            """,
            (account_id, business_id, external_id, display_name, encrypted),
        )
    return {
        "id": account_id,
        "source": "meta",
        "external_id": external_id,
        "display_name": display_name,
        "is_active": True,
    }


def _upsert_vk_oauth_account(
    cursor: Any,
    *,
    business_id: str,
    verification: dict[str, Any],
    token_payload: dict[str, Any],
    device_id: str,
) -> str:
    group_id = str(verification.get("group_id") or "").strip()
    account_id = ""
    cursor.execute(
        """
        SELECT id
        FROM externalbusinessaccounts
        WHERE business_id = %s
          AND source IN ('vk', 'vk_group', 'vk_business')
        ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST
        LIMIT 1
        FOR UPDATE
        """,
        (business_id,),
    )
    existing = cursor.fetchone()
    if existing:
        existing_dict = _row_to_dict(cursor, existing) or {}
        account_id = str(existing_dict.get("id") or "")
    if not account_id:
        account_id = str(uuid.uuid4())

    auth_data = {
        "access_token": str(token_payload.get("access_token") or "").strip(),
        "refresh_token": str(token_payload.get("refresh_token") or "").strip(),
        "token_type": str(token_payload.get("token_type") or "Bearer").strip(),
        "expires_at": oauth_token_expiry(token_payload.get("expires_in")),
        "device_id": str(device_id or "").strip(),
        "user_id": str(verification.get("user_id") or "").strip(),
        "group_id": group_id,
        "owner_id": f"-{group_id}",
        "scope": verification.get("scope") or [],
        "permissions": int(verification.get("permissions") or 0),
        "api_version": vk_api_version(),
        "auth_mode": "vk_id_oauth",
        "verified_at": verification.get("verified_at"),
    }
    encrypted = encrypt_auth_data(json.dumps(auth_data, ensure_ascii=False))
    display_name = str(verification.get("group_name") or f"VK {group_id}").strip()
    if existing:
        cursor.execute(
            """
            UPDATE externalbusinessaccounts
            SET source = 'vk', external_id = %s, display_name = %s,
                auth_data_encrypted = %s, is_active = TRUE,
                last_error = NULL, last_sync_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (group_id, display_name, encrypted, account_id),
        )
    else:
        cursor.execute(
            """
            INSERT INTO externalbusinessaccounts (
                id, business_id, source, external_id, display_name,
                auth_data_encrypted, is_active, last_sync_at, created_at, updated_at
            ) VALUES (
                %s, %s, 'vk', %s, %s, %s, TRUE,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            """,
            (account_id, business_id, group_id, display_name, encrypted),
        )
    return account_id


def _resolve_network_scope_for_business(cursor, business_id, requested_scope):
    cursor.execute(
        """
        SELECT id, network_id, owner_id, name
        FROM businesses
        WHERE id = %s
        LIMIT 1
        """,
        (business_id,),
    )
    raw_business = cursor.fetchone()
    business = _row_to_dict(cursor, raw_business) if raw_business else None
    network_id = (business or {}).get("network_id")
    aggregate_network = bool(network_id and str(requested_scope or "").strip().lower() == "network")
    return business, network_id, aggregate_network


def _network_business_filter(column_name):
    return f"{column_name} IN (SELECT id FROM businesses WHERE network_id = %s OR id = %s)"


def _map_source_filter_sql(column_name: str, source_filter_raw: str) -> str:
    source = str(source_filter_raw or "").strip().lower()
    if source in {"yandex", "yandex_maps", "yandex_business"}:
        return f"LOWER(COALESCE({column_name}, '')) IN ('yandex_maps', 'yandex_business', 'apify_yandex')"
    if source in {"2gis", "two_gis"}:
        return f"LOWER(COALESCE({column_name}, '')) IN ('2gis', 'apify_2gis', 'two_gis')"
    if source in {"google", "google_maps", "google_business"}:
        return f"LOWER(COALESCE({column_name}, '')) IN ('google_maps', 'google_business', 'apify_google')"
    if source in {"apple", "apple_maps", "apple_business"}:
        return f"LOWER(COALESCE({column_name}, '')) IN ('apple_maps', 'apple_business', 'apify_apple')"
    return ""


@external_accounts_bp.route("/api/yclients/marketplace/disconnect", methods=["POST", "GET"])
def yclients_marketplace_disconnect():
    """
    Receive YCLIENTS marketplace integration disconnect callbacks.

    The full YCLIENTS account binding table is added separately; this endpoint
    intentionally returns 200 so marketplace disconnect events do not fail while
    the first integration flow is being reviewed.
    """
    try:
        payload = request.get_json(silent=True)
        if payload is None:
            payload = request.form.to_dict() or request.args.to_dict()
        logger.info("YCLIENTS marketplace disconnect callback received: %s", payload)
        return jsonify({"success": True, "status": "received"})
    except Exception as e:
        logger.exception("YCLIENTS marketplace disconnect callback failed")
        return jsonify({"success": False, "error": str(e)}), 500

def _yclients_partner_token() -> str:
    return str(os.getenv("YCLIENTS_PARTNER_TOKEN") or "").strip()

def _yclients_user_token() -> str:
    return str(os.getenv("YCLIENTS_USER_TOKEN") or "").strip()

def _yclients_application_id() -> str:
    return str(os.getenv("YCLIENTS_APPLICATION_ID") or "45102").strip()

def _yclients_api_base_url() -> str:
    return str(os.getenv("YCLIENTS_API_BASE_URL") or "https://api.yclients.com/api/v1").rstrip("/")

def _yclients_auth_headers() -> Dict[str, str]:
    partner_token = _yclients_partner_token()
    user_token = _yclients_user_token()
    headers = {
        "Accept": "application/vnd.yclients.v2+json",
        "Content-Type": "application/json",
        "User-Agent": "LocalOS-YCLIENTS-Marketplace/1.0",
    }
    if partner_token and user_token:
        headers["Authorization"] = f"Bearer {partner_token}, User {user_token}"
    elif partner_token:
        headers["Authorization"] = f"Bearer {partner_token}"
    return headers

def _extract_yclients_salon_ids(args_source: Any, payload: Optional[Dict[str, Any]] = None) -> List[str]:
    ids: List[str] = []
    if hasattr(args_source, "getlist"):
        for key in ("salon_ids[]", "salon_ids", "salon_id", "company_id"):
            for value in args_source.getlist(key):
                if isinstance(value, list):
                    ids.extend(str(item).strip() for item in value)
                else:
                    ids.append(str(value).strip())
    payload = payload or {}
    for key in ("salon_ids", "salon_ids[]", "salon_id", "company_id"):
        value = payload.get(key)
        if isinstance(value, list):
            ids.extend(str(item).strip() for item in value)
        elif value not in (None, ""):
            ids.append(str(value).strip())
    seen = set()
    clean_ids = []
    for item in ids:
        if item and item not in seen:
            seen.add(item)
            clean_ids.append(item)
    return clean_ids

def _decode_yclients_user_data(user_data: str, user_data_sign: str) -> Dict[str, Any]:
    raw_user_data = str(user_data or "").strip()
    if not raw_user_data:
        return {"data": {}, "signature_valid": None, "signature_checked": False}
    decoded_bytes = base64.b64decode(raw_user_data + "=" * (-len(raw_user_data) % 4))
    decoded_text = decoded_bytes.decode("utf-8")
    parsed = json.loads(decoded_text)
    partner_token = _yclients_partner_token()
    signature_valid = None
    signature_checked = False
    if partner_token and user_data_sign:
        expected = hmac.new(partner_token.encode("utf-8"), decoded_text.encode("utf-8"), hashlib.sha256).hexdigest()
        signature_valid = hmac.compare_digest(expected, str(user_data_sign).strip())
        signature_checked = True
    return {
        "data": parsed if isinstance(parsed, dict) else {},
        "signature_valid": signature_valid,
        "signature_checked": signature_checked,
    }

def _require_yclients_business_access() -> tuple[Optional[DatabaseManager], Optional[Any], Optional[Dict[str, Any]], Optional[str], Optional[Any]]:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None, None, None, None, (jsonify({"error": "Требуется авторизация"}), 401)
    token = auth_header.split(" ", 1)[1]
    user_data = verify_session(token)
    if not user_data:
        return None, None, None, None, (jsonify({"error": "Недействительный токен"}), 401)
    payload = request.get_json(silent=True) or {}
    business_id = str(payload.get("business_id") or request.args.get("business_id") or "").strip()
    if not business_id:
        return None, None, user_data, None, (jsonify({"error": "business_id обязателен"}), 400)
    db = DatabaseManager()
    cursor = db.conn.cursor()
    owner_id = get_business_owner_id(cursor, business_id, include_active_check=True)
    if not owner_id:
        db.close()
        return None, None, user_data, business_id, (jsonify({"error": "Бизнес не найден"}), 404)
    if owner_id != user_data["user_id"] and not db.is_superadmin(user_data["user_id"]):
        db.close()
        return None, None, user_data, business_id, (jsonify({"error": "Нет доступа к бизнесу"}), 403)
    return db, cursor, user_data, business_id, None

def _public_yclients_account(row_dict: Dict[str, Any]) -> Dict[str, Any]:
    auth_data = {}
    encrypted = row_dict.get("auth_data_encrypted")
    if encrypted:
        try:
            auth_data = decrypt_auth_data(encrypted) or {}
        except Exception:
            auth_data = {}
    return {
        "id": row_dict.get("id"),
        "business_id": row_dict.get("business_id"),
        "salon_id": row_dict.get("external_id") or auth_data.get("salon_id"),
        "display_name": row_dict.get("display_name"),
        "is_active": bool(row_dict.get("is_active")),
        "status": auth_data.get("status") or "connected",
        "activation_status": auth_data.get("activation_status") or "not_requested",
        "activation_error": auth_data.get("activation_error"),
        "last_import_at": auth_data.get("last_import_at"),
        "last_import_count": auth_data.get("last_import_count"),
        "user_data": auth_data.get("user_data") or {},
        "created_at": str(row_dict.get("created_at") or "") or None,
        "updated_at": str(row_dict.get("updated_at") or "") or None,
    }

def _load_yclients_accounts(cursor: Any, business_id: str, salon_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    params: list[Any] = [business_id]
    where = "business_id = %s AND source = 'yclients' AND is_active = TRUE"
    if salon_ids:
        where += " AND external_id = ANY(%s)"
        params.append(salon_ids)
    cursor.execute(
        f"""
        SELECT id, business_id, external_id, display_name, auth_data_encrypted, is_active, created_at, updated_at
        FROM externalbusinessaccounts
        WHERE {where}
        ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST
        """,
        tuple(params),
    )
    rows = cursor.fetchall() or []
    return [_row_to_dict(cursor, row) for row in rows]

def _upsert_yclients_account(
    cursor: Any,
    *,
    business_id: str,
    salon_id: str,
    user_id: str,
    user_payload: Dict[str, Any],
    activation: Dict[str, Any],
) -> Dict[str, Any]:
    account_id = str(uuid.uuid4())
    display_name = str(user_payload.get("salon_name") or user_payload.get("company_title") or f"YCLIENTS {salon_id}")
    auth_payload = {
        "salon_id": salon_id,
        "status": "connected",
        "user_data": user_payload,
        "connected_by": user_id,
        "connected_at": datetime.utcnow().isoformat(),
        **activation,
    }
    encrypted = encrypt_auth_data(auth_payload)
    cursor.execute(
        """
        SELECT id FROM externalbusinessaccounts
        WHERE business_id = %s AND source = 'yclients' AND external_id = %s
        LIMIT 1
        """,
        (business_id, salon_id),
    )
    existing = cursor.fetchone()
    if existing:
        existing_id = _row_to_dict(cursor, existing).get("id")
        cursor.execute(
            """
            UPDATE externalbusinessaccounts
            SET display_name = %s,
                auth_data_encrypted = %s,
                is_active = TRUE,
                last_error = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (display_name, encrypted, existing_id),
        )
        account_id = str(existing_id)
    else:
        cursor.execute(
            """
            INSERT INTO externalbusinessaccounts
                (id, business_id, source, external_id, display_name, auth_data_encrypted, is_active, created_at, updated_at)
            VALUES (%s, %s, 'yclients', %s, %s, %s, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (account_id, business_id, salon_id, display_name, encrypted),
        )
    cursor.execute(
        """
        SELECT id, business_id, external_id, display_name, auth_data_encrypted, is_active, created_at, updated_at
        FROM externalbusinessaccounts
        WHERE id = %s
        """,
        (account_id,),
    )
    return _row_to_dict(cursor, cursor.fetchone())

def _activate_yclients_integration(salon_ids: List[str]) -> Dict[str, Any]:
    if not salon_ids:
        return {"activation_status": "skipped", "activation_error": "no_salon_ids"}
    activation_url = str(os.getenv("YCLIENTS_ACTIVATION_URL") or "").strip()
    partner_token = _yclients_partner_token()
    if not activation_url or not partner_token:
        return {
            "activation_status": "pending_configuration",
            "activation_error": "YCLIENTS_ACTIVATION_URL or YCLIENTS_PARTNER_TOKEN is not configured",
        }
    payload = {
        "application_id": _yclients_application_id(),
        "salon_ids": salon_ids,
    }
    try:
        response = requests.post(
            activation_url,
            headers=_yclients_auth_headers(),
            json=payload,
            timeout=20,
        )
        if 200 <= response.status_code < 300:
            return {"activation_status": "activated", "activated_at": datetime.utcnow().isoformat()}
        return {"activation_status": "failed", "activation_error": f"{response.status_code}: {response.text[:500]}"}
    except Exception as e:
        return {"activation_status": "failed", "activation_error": str(e)}

def _yclients_request_json(path: str, salon_id: str) -> Any:
    partner_token = _yclients_partner_token()
    user_token = _yclients_user_token()
    if not partner_token or not user_token:
        raise RuntimeError("YCLIENTS_PARTNER_TOKEN and YCLIENTS_USER_TOKEN must be configured on server")
    clean_path = path if path.startswith("/") else f"/{path}"
    response = requests.get(
        f"{_yclients_api_base_url()}{clean_path}",
        headers=_yclients_auth_headers(),
        timeout=25,
    )
    if not (200 <= response.status_code < 300):
        raise RuntimeError(f"YCLIENTS API error for salon {salon_id}: {response.status_code} {response.text[:500]}")
    return response.json() if response.text else {}

def _extract_yclients_items(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("data", "items", "services"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("items", "services"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []

def _first_item_value(item: Dict[str, Any], keys: List[str], default: Any = "") -> Any:
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return default

def _service_price_value(item: Dict[str, Any]) -> str:
    value = _first_item_value(item, ["price", "cost", "price_min", "price_max"], "")
    if isinstance(value, dict):
        value = _first_item_value(value, ["amount", "value", "from"], "")
    return str(value or "")

def _service_duration_minutes(item: Dict[str, Any]) -> Optional[int]:
    value = _first_item_value(item, ["duration", "duration_minutes", "seance_length"], "")
    try:
        number = int(float(str(value).replace(",", ".")))
        return int(number / 60) if number > 600 else number
    except Exception:
        return None

def _normalize_yclients_service(item: Dict[str, Any], salon_id: str) -> Dict[str, Any]:
    category = item.get("category")
    category_name = ""
    if isinstance(category, dict):
        category_name = str(_first_item_value(category, ["title", "name"], ""))
    elif category not in (None, ""):
        category_name = str(category)
    external_id = str(_first_item_value(item, ["id", "service_id"], "") or "").strip()
    title = str(_first_item_value(item, ["title", "name", "service_name"], "") or "").strip()
    return {
        "external_id": external_id or f"{salon_id}:{title}",
        "name": title,
        "description": str(_first_item_value(item, ["description", "comment"], "") or ""),
        "category": category_name or "YCLIENTS",
        "price": _service_price_value(item),
        "duration_minutes": _service_duration_minutes(item),
        "raw": item,
    }

@external_accounts_bp.route("/api/yclients/marketplace/status", methods=["GET"])
def yclients_marketplace_status():
    db, cursor, user_data, business_id, error_response = _require_yclients_business_access()
    if error_response:
        return error_response
    try:
        salon_ids = _extract_yclients_salon_ids(request.args)
        accounts = _load_yclients_accounts(cursor, business_id, salon_ids or None)
        db.close()
        return jsonify({
            "success": True,
            "business_id": business_id,
            "salon_ids": salon_ids,
            "accounts": [_public_yclients_account(item) for item in accounts],
            "server": {
                "has_partner_token": bool(_yclients_partner_token()),
                "has_user_token": bool(_yclients_user_token()),
                "has_activation_url": bool(str(os.getenv("YCLIENTS_ACTIVATION_URL") or "").strip()),
            },
        })
    except Exception as e:
        db.close()
        return jsonify({"success": False, "error": str(e)}), 500

@external_accounts_bp.route("/api/yclients/marketplace/connect", methods=["POST", "OPTIONS"])
def yclients_marketplace_connect():
    if request.method == "OPTIONS":
        return ("", 204)
    db, cursor, user_data, business_id, error_response = _require_yclients_business_access()
    if error_response:
        return error_response
    try:
        payload = request.get_json(silent=True) or {}
        salon_ids = _extract_yclients_salon_ids(request.args, payload)
        if not salon_ids:
            db.close()
            return jsonify({"success": False, "error": "salon_id или salon_ids[] обязательны"}), 400
        user_data_result = _decode_yclients_user_data(
            str(payload.get("user_data") or request.args.get("user_data") or ""),
            str(payload.get("user_data_sign") or request.args.get("user_data_sign") or ""),
        )
        if user_data_result.get("signature_checked") and not user_data_result.get("signature_valid"):
            db.close()
            return jsonify({"success": False, "error": "Некорректная подпись user_data"}), 400
        activation = _activate_yclients_integration(salon_ids)
        accounts = []
        for salon_id in salon_ids:
            account_row = _upsert_yclients_account(
                cursor,
                business_id=business_id,
                salon_id=salon_id,
                user_id=user_data["user_id"],
                user_payload=user_data_result.get("data") or {},
                activation=activation,
            )
            accounts.append(_public_yclients_account(account_row))
        db.conn.commit()
        db.close()
        return jsonify({
            "success": True,
            "business_id": business_id,
            "salon_ids": salon_ids,
            "accounts": accounts,
            "activation": activation,
            "server": {
                "has_partner_token": bool(_yclients_partner_token()),
                "has_user_token": bool(_yclients_user_token()),
                "has_activation_url": bool(str(os.getenv("YCLIENTS_ACTIVATION_URL") or "").strip()),
            },
            "user_data_signature": {
                "checked": user_data_result.get("signature_checked"),
                "valid": user_data_result.get("signature_valid"),
            },
        })
    except Exception as e:
        db.conn.rollback()
        db.close()
        logger.exception("YCLIENTS marketplace connect failed")
        return jsonify({"success": False, "error": str(e)}), 500

@external_accounts_bp.route("/api/yclients/marketplace/import-services", methods=["POST", "OPTIONS"])
def yclients_marketplace_import_services():
    if request.method == "OPTIONS":
        return ("", 204)
    db, cursor, user_data, business_id, error_response = _require_yclients_business_access()
    if error_response:
        return error_response
    try:
        payload = request.get_json(silent=True) or {}
        requested_salon_ids = _extract_yclients_salon_ids(request.args, payload)
        accounts = _load_yclients_accounts(cursor, business_id, requested_salon_ids or None)
        if not accounts:
            db.close()
            return jsonify({"success": False, "error": "Сначала подключите филиал YCLIENTS к бизнесу LocalOS"}), 404
        columns = _table_columns(cursor, "userservices")
        imported = []
        for account in accounts:
            salon_id = str(account.get("external_id") or "").strip()
            payload_json = _yclients_request_json(f"/company/{salon_id}/services", salon_id)
            services = [_normalize_yclients_service(item, salon_id) for item in _extract_yclients_items(payload_json)]
            for service in services:
                if not service["name"]:
                    continue
                service_id = str(uuid.uuid4())
                external_id = str(service["external_id"])
                raw_json = json.dumps(service.get("raw") or {}, ensure_ascii=False)
                keywords_json = json.dumps([], ensure_ascii=False)
                if {"source", "external_id", "raw"}.issubset(columns):
                    cursor.execute(
                        """
                        INSERT INTO userservices
                            (id, user_id, business_id, category, name, description, keywords, price, source, external_id, duration_minutes, raw, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, 'yclients', %s, %s, %s::jsonb, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        ON CONFLICT (business_id, source, external_id)
                        WHERE external_id IS NOT NULL
                        DO UPDATE SET
                            category = EXCLUDED.category,
                            name = EXCLUDED.name,
                            description = EXCLUDED.description,
                            price = EXCLUDED.price,
                            duration_minutes = EXCLUDED.duration_minutes,
                            raw = EXCLUDED.raw,
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (
                            service_id,
                            user_data["user_id"],
                            business_id,
                            service["category"],
                            service["name"],
                            service["description"],
                            keywords_json,
                            service["price"],
                            external_id,
                            service["duration_minutes"],
                            raw_json,
                        ),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO userservices
                            (id, user_id, business_id, category, name, description, keywords, price, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        """,
                        (
                            service_id,
                            user_data["user_id"],
                            business_id,
                            service["category"],
                            service["name"],
                            service["description"],
                            keywords_json,
                            service["price"],
                        ),
                    )
                imported.append({
                    "salon_id": salon_id,
                    "external_id": external_id,
                    "name": service["name"],
                    "price": service["price"],
                    "category": service["category"],
                })
            auth_data = {}
            try:
                auth_data = decrypt_auth_data(account.get("auth_data_encrypted")) or {}
            except Exception:
                auth_data = {}
            auth_data["last_import_at"] = datetime.utcnow().isoformat()
            auth_data["last_import_count"] = len([item for item in imported if item.get("salon_id") == salon_id])
            cursor.execute(
                """
                UPDATE externalbusinessaccounts
                SET auth_data_encrypted = %s,
                    last_error = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (encrypt_auth_data(auth_data), account.get("id")),
            )
        db.conn.commit()
        db.close()
        return jsonify({
            "success": True,
            "business_id": business_id,
            "imported_count": len(imported),
            "services": imported[:50],
        })
    except Exception as e:
        db.conn.rollback()
        db.close()
        logger.exception("YCLIENTS services import failed")
        return jsonify({"success": False, "error": str(e)}), 500

@external_accounts_bp.route("/api/business/<business_id>/vk/oauth/start", methods=["POST"])
def start_vk_oauth(business_id):
    user_data, db, access_error = _require_vk_business_access(business_id)
    if access_error:
        return access_error
    try:
        payload = request.get_json(silent=True) or {}
        group_id = normalize_vk_group_id(payload.get("group_id"))
        code_challenge = validate_vk_pkce_value(payload.get("code_challenge"), "code_challenge")
        client_state = str(payload.get("client_state") or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{20,160}", client_state):
            return jsonify({"success": False, "error": "Не удалось начать безопасное подключение VK."}), 400
        state = encode_vk_oauth_state(
            {
                "user_id": str(user_data.get("user_id") or ""),
                "business_id": str(business_id),
                "group_id": group_id,
                "code_challenge": code_challenge,
                "client_state": client_state,
                "return_to": _safe_vk_return_path(payload.get("return_to")),
            }
        )
        auth_url = build_vk_authorization_url(state=state, code_challenge=code_challenge)
        return jsonify(
            {
                "success": True,
                "auth_url": auth_url,
                "external_publish_performed": False,
            }
        )
    except VkOAuthError:
        return _vk_oauth_error_response()
    except Exception:
        return _vk_oauth_error_response(502)
    finally:
        db.close()


@external_accounts_bp.route("/api/vk/oauth/callback", methods=["GET"])
def vk_oauth_callback():
    frontend_url = str(os.getenv("FRONTEND_URL") or "http://localhost:3000").rstrip("/")
    state = str(request.args.get("state") or "").strip()
    try:
        state_payload = decode_vk_oauth_state(state)
        return_to = _safe_vk_return_path(state_payload.get("return_to"))
        if request.args.get("error"):
            return redirect(
                f"{frontend_url}{_append_vk_auth_params(return_to, {'vk_auth': 'cancelled'})}"
            )
        code = str(request.args.get("code") or "").strip()
        device_id = str(request.args.get("device_id") or "").strip()
        if not code or not device_id:
            return redirect(
                f"{frontend_url}{_append_vk_auth_params(return_to, {'vk_auth': 'error'})}"
            )
        callback_params = {
            "vk_auth": "pending",
            "vk_code": code,
            "vk_device_id": device_id,
            "vk_state": state,
            "vk_client_state": str(state_payload.get("client_state") or ""),
        }
        return redirect(f"{frontend_url}{_append_vk_auth_params(return_to, callback_params)}")
    except Exception:
        logger.info("VK OAuth callback state validation failed")
        return redirect(
            f"{frontend_url}{_append_vk_auth_params(DEFAULT_VK_RETURN_PATH, {'vk_auth': 'expired'})}"
        )


@external_accounts_bp.route("/api/business/<business_id>/vk/oauth/complete", methods=["POST"])
def complete_vk_oauth(business_id):
    user_data, db, access_error = _require_vk_business_access(business_id)
    if access_error:
        return access_error
    try:
        payload = request.get_json(silent=True) or {}
        state = str(payload.get("state") or "").strip()
        state_payload = decode_vk_oauth_state(state)
        state_user_id = str(state_payload.get("user_id") or "")
        state_business_id = str(state_payload.get("business_id") or "")
        if state_user_id != str(user_data.get("user_id") or "") or state_business_id != str(business_id):
            return jsonify({"success": False, "status": "state_mismatch", "error": "Это подключение VK относится к другому аккаунту."}), 403

        code_verifier = validate_vk_pkce_value(payload.get("code_verifier"), "code_verifier")
        expected_challenge = str(state_payload.get("code_challenge") or "")
        if not hmac.compare_digest(vk_pkce_challenge(code_verifier), expected_challenge):
            return jsonify({"success": False, "status": "pkce_mismatch", "error": "Не удалось проверить подключение VK. Начните ещё раз."}), 400

        token_payload = exchange_vk_authorization_code(
            code=str(payload.get("code") or ""),
            device_id=str(payload.get("device_id") or ""),
            code_verifier=code_verifier,
        )
        access_token = str(token_payload.get("access_token") or "").strip()
        verification = verify_vk_oauth_access(
            access_token,
            str(state_payload.get("group_id") or ""),
        )
        cursor = db.conn.cursor()
        account_id = _upsert_vk_oauth_account(
            cursor,
            business_id=str(business_id),
            verification=verification,
            token_payload=token_payload,
            device_id=str(payload.get("device_id") or ""),
        )
        db.conn.commit()
        return jsonify(
            {
                "success": True,
                "status": "connected",
                "account": {
                    "id": account_id,
                    "source": "vk",
                    "external_id": verification.get("group_id"),
                    "display_name": verification.get("group_name"),
                    "is_active": True,
                },
                "message": "VK подключён. LocalOS подтвердил сообщество и права публикации.",
                "external_publish_performed": False,
            }
        )
    except VkOAuthError:
        db.conn.rollback()
        return _vk_oauth_error_response()
    except Exception:
        db.conn.rollback()
        return _vk_oauth_error_response(502)
    finally:
        db.close()


@external_accounts_bp.route("/api/business/<business_id>/meta/oauth/start", methods=["POST"])
def start_meta_oauth(business_id):
    user_data, db, access_error = _require_vk_business_access(business_id)
    if access_error:
        return access_error
    try:
        payload = request.get_json(silent=True) or {}
        state = encode_meta_oauth_state(
            {
                "user_id": str(user_data.get("user_id") or ""),
                "business_id": str(business_id),
                "return_to": _safe_meta_return_path(payload.get("return_to")),
            }
        )
        return jsonify(
            {
                "success": True,
                "auth_url": build_meta_authorization_url(state=state),
                "external_publish_performed": False,
            }
        )
    except MetaOAuthError:
        return _meta_oauth_error_response()
    except Exception:
        return _meta_oauth_error_response(502)
    finally:
        db.close()


@external_accounts_bp.route("/api/meta/oauth/callback", methods=["GET"])
def meta_oauth_callback():
    frontend_url = str(os.getenv("FRONTEND_URL") or "http://localhost:3000").rstrip("/")
    state = str(request.args.get("state") or "").strip()
    db = None
    try:
        state_payload = decode_meta_oauth_state(state)
        return_to = _safe_meta_return_path(state_payload.get("return_to"))
        if request.args.get("error"):
            return redirect(
                f"{frontend_url}{_append_meta_auth_params(return_to, {'meta_auth': 'cancelled'})}"
            )
        business_id = str(state_payload.get("business_id") or "").strip()
        state_user_id = str(state_payload.get("user_id") or "").strip()
        db = DatabaseManager()
        cursor = db.conn.cursor()
        owner_id = get_business_owner_id(cursor, business_id)
        if not owner_id or (owner_id != state_user_id and not db.is_superadmin(state_user_id)):
            raise MetaOAuthError("state_mismatch", "Это подключение Meta относится к другому аккаунту.")
        token_payload = exchange_meta_authorization_code(str(request.args.get("code") or ""))
        token_inspection = inspect_meta_access_token(str(token_payload.get("access_token") or ""))
        assets = list_meta_assets(str(token_payload.get("access_token") or ""))
        _upsert_meta_oauth_account(
            cursor,
            business_id=business_id,
            user_token_payload=token_payload,
            token_inspection=token_inspection,
            available_page_count=len(assets),
        )
        db.conn.commit()
        params = {
            "meta_auth": "connected",
            "meta_pages": str(len(assets)),
        }
        return redirect(f"{frontend_url}{_append_meta_auth_params(return_to, params)}")
    except MetaOAuthError:
        if db:
            db.conn.rollback()
        error = sys.exc_info()[1]
        logger.info("Meta OAuth callback failed: %s", error)
        return redirect(
            f"{frontend_url}{_append_meta_auth_params(DEFAULT_META_RETURN_PATH, {'meta_auth': getattr(error, 'code', 'error')})}"
        )
    except Exception:
        if db:
            db.conn.rollback()
        logger.exception("Meta OAuth callback failed")
        return redirect(
            f"{frontend_url}{_append_meta_auth_params(DEFAULT_META_RETURN_PATH, {'meta_auth': 'error'})}"
        )
    finally:
        if db:
            db.close()


@external_accounts_bp.route("/api/meta/data-deletion", methods=["POST"])
def meta_data_deletion_callback():
    db = None
    try:
        payload = request.get_json(silent=True) or {}
        signed_request = str(
            request.form.get("signed_request")
            or payload.get("signed_request")
            or ""
        ).strip()
        deletion_request = decode_meta_data_deletion_request(signed_request)
        meta_user_id = str(deletion_request.get("user_id") or "").strip()
        confirmation_code = secrets.token_urlsafe(18)

        db = DatabaseManager()
        cursor = db.conn.cursor()
        cursor.execute(
            """
            SELECT id, auth_data_encrypted
            FROM externalbusinessaccounts
            WHERE source IN ('meta', 'facebook', 'instagram')
            FOR UPDATE
            """
        )
        matching_ids = []
        for row in cursor.fetchall() or []:
            account = _row_to_dict(cursor, row) or {}
            auth_data = _meta_account_auth_data(account)
            if str(auth_data.get("user_id") or "").strip() == meta_user_id:
                matching_ids.append(str(account.get("id") or ""))

        for account_id in matching_ids:
            cursor.execute(
                """
                UPDATE externalbusinessaccounts
                SET external_id = NULL,
                    display_name = 'Meta отключена',
                    auth_data_encrypted = %s,
                    is_active = FALSE,
                    last_error = 'Доступ удалён по запросу пользователя Meta',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (encrypt_auth_data("{}"), account_id),
            )
        db.conn.commit()
        frontend_url = str(os.getenv("FRONTEND_URL") or "https://localos.pro").rstrip("/")
        status_url = (
            f"{frontend_url}/data-deletion?"
            f"confirmation_code={urllib.parse.quote(confirmation_code)}"
        )
        logger.info(
            "Meta data deletion completed user=%s disconnected_accounts=%s",
            meta_user_id,
            len(matching_ids),
        )
        response = jsonify(
            {
                "url": status_url,
                "confirmation_code": confirmation_code,
            }
        )
        response.headers["Cache-Control"] = "no-store"
        return response
    except MetaOAuthError as error:
        if db:
            db.conn.rollback()
        logger.warning("Meta data deletion request rejected: %s", error)
        return jsonify({"error": "Не удалось подтвердить запрос Meta."}), 400
    except Exception:
        if db:
            db.conn.rollback()
        logger.exception("Meta data deletion callback failed")
        return jsonify({"error": "Не удалось обработать удаление данных Meta."}), 500
    finally:
        if db:
            db.close()


@external_accounts_bp.route("/api/business/<business_id>/meta/assets", methods=["GET"])
def get_meta_assets(business_id):
    user_data, db, access_error = _require_vk_business_access(business_id)
    if access_error:
        return access_error
    try:
        cursor = db.conn.cursor()
        account = _load_meta_account(cursor, business_id)
        auth_data = _meta_account_auth_data(account)
        user_access_token = str(auth_data.get("user_access_token") or "").strip()
        if not account or not user_access_token:
            return jsonify(
                {
                    "success": False,
                    "status": "missing_connection",
                    "error": "Сначала подключите аккаунт Facebook.",
                }
            ), 409
        assets = list_meta_assets(user_access_token)
        return jsonify(
            {
                "success": True,
                "assets": [public_meta_asset(asset) for asset in assets],
                "selected_page_id": str(account.get("external_id") or ""),
                "external_publish_performed": False,
            }
        )
    except MetaOAuthError:
        return _meta_oauth_error_response()
    except Exception:
        return _meta_oauth_error_response(502)
    finally:
        db.close()


@external_accounts_bp.route("/api/business/<business_id>/meta/bind", methods=["POST"])
def bind_meta_asset(business_id):
    user_data, db, access_error = _require_vk_business_access(business_id)
    if access_error:
        return access_error
    try:
        payload = request.get_json(silent=True) or {}
        page_id = str(payload.get("page_id") or "").strip()
        if not page_id:
            return jsonify({"success": False, "status": "missing_page", "error": "Выберите страницу Facebook."}), 400
        cursor = db.conn.cursor()
        account = _load_meta_account(cursor, business_id, lock=True)
        auth_data = _meta_account_auth_data(account)
        user_access_token = str(auth_data.get("user_access_token") or "").strip()
        if not account or not user_access_token:
            return jsonify({"success": False, "status": "missing_connection", "error": "Сначала подключите аккаунт Facebook."}), 409
        assets = list_meta_assets(user_access_token)
        selected_asset = next(
            (asset for asset in assets if str(asset.get("page_id") or "") == page_id),
            None,
        )
        if not selected_asset:
            return jsonify({"success": False, "status": "page_unavailable", "error": "Выбранная страница больше недоступна. Обновите список."}), 404
        token_payload = {
            "access_token": user_access_token,
            "expires_at": auth_data.get("user_token_expires_at"),
        }
        token_inspection = {
            "user_id": auth_data.get("user_id"),
            "scopes": auth_data.get("scope") or list(META_OAUTH_SCOPES),
            "missing_scopes": auth_data.get("missing_scopes") or [],
            "verified_at": auth_data.get("oauth_verified_at"),
        }
        account_summary = _upsert_meta_oauth_account(
            cursor,
            business_id=business_id,
            user_token_payload=token_payload,
            token_inspection=token_inspection,
            page_asset=selected_asset,
            available_page_count=len(assets),
        )
        db.conn.commit()
        ig_username = str(selected_asset.get("ig_username") or "").strip()
        return jsonify(
            {
                "success": True,
                "status": "connected",
                "account": account_summary,
                "facebook_ready": True,
                "instagram_ready": bool(selected_asset.get("ig_user_id")),
                "message": (
                    f"Подключены Facebook Page и Instagram @{ig_username}."
                    if ig_username
                    else "Facebook Page подключена. Для Instagram свяжите с ней профессиональный аккаунт."
                ),
                "external_publish_performed": False,
            }
        )
    except MetaOAuthError:
        db.conn.rollback()
        return _meta_oauth_error_response()
    except Exception:
        db.conn.rollback()
        return _meta_oauth_error_response(502)
    finally:
        db.close()


@external_accounts_bp.route("/api/business/<business_id>/external-accounts", methods=["GET"])
def get_external_accounts(business_id):
    """
    Получить все подключённые внешние аккаунты (Яндекс.Бизнес, Google Business, 2ГИС)
    для конкретного бизнеса. Всегда возвращает JSON: 200 { "success": true, "accounts": [] } или список.
    """
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(" ")[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        cursor = db.conn.cursor()

        owner_id = get_business_owner_id(cursor, business_id)
        if not owner_id:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404

        if owner_id != user_data["user_id"] and not db.is_superadmin(user_data["user_id"]):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403

        # Таблица из миграции 20250207_008: externalbusinessaccounts (lowercase)
        try:
            cursor.execute(
                """
                SELECT id, source, external_id, display_name, is_active,
                       last_sync_at, last_error, created_at, updated_at,
                       auth_data_encrypted
                FROM externalbusinessaccounts
                WHERE business_id = %s
                ORDER BY source, created_at DESC
                """,
                (business_id,),
            )
            rows = cursor.fetchall()
        except Exception as table_err:
            db.close()
            err_str = str(table_err)
            is_missing_relation = "does not exist" in err_str or "relation" in err_str.lower()
            if is_missing_relation and getattr(current_app, "debug", False):
                print(f"⚠️ GET external-accounts: таблица отсутствует, возвращаем [] (dev): {table_err}")
                return jsonify({"success": True, "accounts": [], "_debug": {"tableMissing": True, "tableName": "externalbusinessaccounts"}})
            if is_missing_relation:
                import traceback
                print(f"❌ GET external-accounts: таблица externalbusinessaccounts не найдена: {table_err}\n{traceback.format_exc()}")
                return jsonify({"error": "Schema error: external accounts table missing", "detail": "get_external_accounts"}), 500
            raise

        accounts = []
        for r in rows:
            row_dict = _row_to_dict(cursor, r)
            if not row_dict:
                continue
            connection_mode = None
            if str(row_dict.get("source") or "") in {
                "vk", "vk_group", "vk_business", "meta", "facebook", "instagram"
            }:
                try:
                    raw_auth_data = decrypt_auth_data(row_dict.get("auth_data_encrypted")) or ""
                    parsed_auth_data = json.loads(raw_auth_data) if raw_auth_data else {}
                    if isinstance(parsed_auth_data, dict):
                        default_mode = (
                            "legacy_token"
                            if str(row_dict.get("source") or "") in {"vk", "vk_group", "vk_business"}
                            else "manual_token"
                        )
                        connection_mode = str(parsed_auth_data.get("auth_mode") or default_mode)
                except (TypeError, ValueError, json.JSONDecodeError):
                    connection_mode = "legacy_token"
            accounts.append({
                "id": row_dict.get("id"),
                "source": row_dict.get("source"),
                "external_id": row_dict.get("external_id"),
                "display_name": row_dict.get("display_name"),
                "is_active": row_dict.get("is_active"),
                "last_sync_at": row_dict.get("last_sync_at"),
                "last_error": row_dict.get("last_error"),
                "created_at": row_dict.get("created_at"),
                "updated_at": row_dict.get("updated_at"),
                "connection_mode": connection_mode,
            })
        db.close()
        resp = {"success": True, "accounts": accounts}
        if getattr(current_app, "debug", False):
            resp["_debug"] = {"tableName": "externalbusinessaccounts"}
        return jsonify(resp)

    except Exception as e:
        import traceback
        err_tb = traceback.format_exc()
        print(f"❌ Ошибка GET external-accounts: {e}\n{err_tb}")
        payload = {"error": str(e), "detail": "get_external_accounts"}
        if getattr(current_app, "debug", False):
            payload["traceback"] = err_tb
        return jsonify(payload), 500

@external_accounts_bp.route("/api/business/<business_id>/external-accounts", methods=["POST"])
def upsert_external_account(business_id):
    """
    Создать или обновить внешний аккаунт источника для бизнеса.

    Body:
      - source: 'yandex_business' | 'google_business' | '2gis' | 'telegram_app' | 'vk' | 'vk_group' | 'vk_business' | 'meta' | 'facebook' | 'instagram'
      - external_id: string (опционально)
      - display_name: string (опционально)
      - auth_data: string (cookie / refresh_token / token) - будет зашифрован позже
      - is_active: bool (опционально, по умолчанию True)
    """
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(" ")[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        data = request.get_json() or {}
        source = (data.get("source") or "").strip()
        external_id = (data.get("external_id") or "").strip() or None
        display_name = (data.get("display_name") or "").strip() or None
        is_active = data.get("is_active", True)

        # Нормализация auth_data: строка или объект → строка для шифрования; валидация JSON при необходимости
        raw_auth = data.get("auth_data")
        auth_data_str = None
        if raw_auth is not None:
            if isinstance(raw_auth, dict):
                try:
                    auth_data_str = json.dumps(raw_auth)
                except (TypeError, ValueError) as e:
                    return jsonify({"error": "auth_data: объект не сериализуется в JSON", "field": "auth_data", "detail": str(e)}), 400
            elif isinstance(raw_auth, str):
                s = raw_auth.strip() or None
                if s:
                    if s.startswith("{") or s.startswith("["):
                        try:
                            json.loads(s)
                        except json.JSONDecodeError as e:
                            return jsonify({"error": "auth_data: некорректный JSON", "field": "auth_data", "detail": str(e)}), 400
                    auth_data_str = s
            else:
                return jsonify({"error": "auth_data должен быть строкой или объектом", "field": "auth_data"}), 400

        if source not in (
            "yandex_business",
            "google_business",
            "2gis",
            "telegram_app",
            "vk",
            "vk_group",
            "vk_business",
            "meta",
            "facebook",
            "instagram",
        ):
            return jsonify({"error": "Некорректный source"}), 400

        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Проверяем, что пользователь владелец бизнеса или суперадмин
        owner_id = get_business_owner_id(cursor, business_id)
        if not owner_id:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404

        if owner_id != user_data["user_id"] and not db.is_superadmin(user_data["user_id"]):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403

        # Проверяем, существует ли таблица externalbusinessaccounts (Postgres)
        cursor.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'externalbusinessaccounts'
        """)
        table_exists = cursor.fetchone()

        if not table_exists:
            db.close()
            return jsonify({
                "error": "Таблица externalbusinessaccounts не существует. Необходимо применить миграцию."
            }), 500

        import uuid
        from datetime import datetime
        from auth_encryption import encrypt_auth_data

        now = datetime.utcnow().isoformat()
        print(f"🔍 POST /api/business/{business_id}/external-accounts: source={source}, external_id={external_id}, display_name={display_name}, auth_data length={len(auth_data_str) if auth_data_str else 0}")

        # Шифруем auth_data перед сохранением (auth_data_str уже нормализован)
        auth_data_encrypted = None
        if auth_data_str:
            try:
                auth_data_encrypted = encrypt_auth_data(auth_data_str)
            except Exception as e:
                import traceback
                traceback.print_exc()
                db.close()
                return jsonify({"error": f"Ошибка шифрования данных: {str(e)}", "field": "auth_data"}), 500

        # SELECT с блокировкой при наличии строки, чтобы избежать гонки update/create
        cursor.execute(
            """
            SELECT id, external_id, display_name, is_active
            FROM externalbusinessaccounts
            WHERE business_id = %s AND source = %s
            FOR UPDATE
            """,
            (business_id, source),
        )
        existing_row = cursor.fetchone()
        existing_dict = _row_to_dict(cursor, existing_row) if existing_row else None
        account_id = (existing_dict.get("id") if existing_dict else None)

        if existing_dict:
            # Update: считаем реально изменённые поля для saved_fields
            action = "updated"
            old_ext = existing_dict.get("external_id")
            old_name = existing_dict.get("display_name")
            old_active = existing_dict.get("is_active")
            new_active = bool(is_active)
            saved_fields = []
            if (external_id or None) != (old_ext or None):
                saved_fields.append("external_id")
            if (display_name or None) != (old_name or None):
                saved_fields.append("display_name")
            if new_active != (bool(old_active) if old_active is not None else True):
                saved_fields.append("is_active")
            if auth_data_encrypted is not None:
                saved_fields.append("auth_data_updated")

            if auth_data_encrypted is not None:
                cursor.execute(
                    """
                    UPDATE externalbusinessaccounts
                    SET external_id = %s, display_name = %s, auth_data_encrypted = %s, is_active = %s, updated_at = %s
                    WHERE id = %s
                    """,
                    (external_id, display_name, auth_data_encrypted, new_active, now, account_id),
                )
            else:
                cursor.execute(
                    """
                    UPDATE externalbusinessaccounts
                    SET external_id = %s, display_name = %s, is_active = %s, updated_at = %s
                    WHERE id = %s
                    """,
                    (external_id, display_name, new_active, now, account_id),
                )
        else:
            # Create: auth_data может отсутствовать для всех источников.
            # Это позволяет сохранять "минимальную" конфигурацию и запускать публичный парсинг по map URL.
            action = "created"
            new_active = bool(is_active)
            insert_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO externalbusinessaccounts (id, business_id, source, external_id, display_name, auth_data_encrypted, is_active, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (insert_id, business_id, source, external_id, display_name, auth_data_encrypted, new_active, now, now),
            )
            # Повторный SELECT по (business_id, source): при конкурентном create может быть несколько строк
            cursor.execute(
                """
                SELECT id, created_at FROM externalbusinessaccounts
                WHERE business_id = %s AND source = %s
                ORDER BY created_at ASC
                """,
                (business_id, source),
            )
            rows_after = cursor.fetchall()
            if len(rows_after) > 1:
                print(f"⚠️ Дубликаты externalbusinessaccounts (business_id={business_id}, source={source}): записей={len(rows_after)}, используем с min(created_at)")
            # Канонический id — запись с минимальным created_at (стабильный выбор при дублях)
            row0 = _row_to_dict(cursor, rows_after[0]) if rows_after else None
            account_id = row0.get("id") if row0 else insert_id
            saved_fields = ["external_id", "display_name", "is_active", "auth_data_updated"]

        db.conn.commit()
        db.close()

        resp = {"success": True, "account_id": account_id}
        if getattr(current_app, "debug", False):
            resp["_debug"] = {
                "action": action,
                "business_id": business_id,
                "source": source,
                "saved_fields": saved_fields,
                "returned_id": account_id,
            }
        return jsonify(resp)

    except Exception as e:
        print(f"❌ Ошибка сохранения внешнего аккаунта: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@external_accounts_bp.route("/api/external-accounts/<account_id>", methods=["DELETE"])
def delete_external_account(account_id):
    """Отключить внешний аккаунт (делаем is_active = 0, но не удаляем записи отзывов/статистики)."""
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(" ")[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Находим аккаунт и соответствующий бизнес
        cursor.execute(
            "SELECT business_id FROM externalbusinessaccounts WHERE id = %s", (account_id,)
        )
        row = cursor.fetchone()
        if not row:
            db.close()
            return jsonify({"error": "Аккаунт не найден"}), 404

        business_id = row[0]

        # Проверяем, что пользователь владелец бизнеса или суперадмин
        owner_id = get_business_owner_id(cursor, business_id)
        if not owner_id:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404

        if owner_id != user_data["user_id"] and not db.is_superadmin(user_data["user_id"]):
            db.close()
            return jsonify({"error": "Нет доступа"}), 403

        cursor.execute(
            """
            UPDATE externalbusinessaccounts
            SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (account_id,),
        )
        db.conn.commit()
        db.close()

        return jsonify({"success": True})

    except Exception as e:
        print(f"❌ Ошибка отключения внешнего аккаунта: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@external_accounts_bp.route("/api/business/<business_id>/external-accounts/test", methods=["POST"])
def test_external_account_cookies(business_id):
    """
    Тестирует cookies для внешнего аккаунта без сохранения.

    Body:
      - source: 'yandex_business' | '2gis'
      - auth_data: string (cookies в формате строки)
      - external_id: string (опционально, для Яндекс.Бизнес)
    """
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(" ")[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        data = request.get_json() or {}
        source = (data.get("source") or "").strip()
        auth_data = (data.get("auth_data") or "").strip()
        external_id = (data.get("external_id") or "").strip() or None

        if not source:
            return jsonify({"error": "source обязателен"}), 400

        if source not in ("yandex_business", "2gis"):
            return jsonify({"error": "Некорректный source"}), 400

        if source == "yandex_business" and not auth_data:
            return jsonify({"error": "source и auth_data обязательны"}), 400
        if source == "2gis" and not auth_data:
            return jsonify({
                "success": True,
                "message": "auth_data не указан: для 2ГИС будет использован публичный парсинг по ссылке/ID",
                "mode": "public_parse",
            }), 200

        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Проверяем доступ к бизнесу
        owner_id = get_business_owner_id(cursor, business_id)
        if not owner_id:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404

        if owner_id != user_data["user_id"] and not db.is_superadmin(user_data["user_id"]):
            db.close()
            return jsonify({"error": "Нет доступа"}), 403

        db.close()

        # Парсим auth_data
        try:
            auth_data_dict = json.loads(auth_data)
            cookies_str = auth_data_dict.get("cookies", auth_data)
        except json.JSONDecodeError:
            cookies_str = auth_data

        # Парсим cookies в словарь
        cookies_dict = {}
        for item in cookies_str.split(";"):
            item = item.strip()
            if "=" in item:
                key, value = item.split("=", 1)
                cookies_dict[key.strip()] = value.strip()

        if not cookies_dict:
            return jsonify({
                "success": False,
                "error": "Не удалось распарсить cookies",
                "message": "Проверьте формат cookies. Должен быть: key1=value1; key2=value2; ..."
            }), 200

        # Проверяем наличие критичных cookies для Яндекс.Бизнес
        required_cookies = ["Session_id", "yandexuid", "sessionid2"]
        missing_cookies = [cookie for cookie in required_cookies if cookie not in cookies_dict]

        if missing_cookies:
            return jsonify({
                "success": False,
                "error": "Отсутствуют обязательные cookies",
                "message": f"Не найдены критичные cookies: {', '.join(missing_cookies)}. Эти cookies обязательны для доступа к личному кабинету Яндекс.Бизнес. Скопируйте их из DevTools → Application → Cookies → yandex.ru",
                "missing_cookies": missing_cookies,
            }), 200

        # Тестируем cookies в зависимости от source
        if source == "yandex_business":
            # Для Яндекс.Бизнес тестируем простой запрос к API отзывов
            if not external_id:
                return jsonify({"error": "external_id обязателен для Яндекс.Бизнес"}), 400

            test_url = f"https://yandex.ru/sprav/api/{external_id}/reviews"
            test_params = {"ranking": "by_time"}

            try:
                # Импортируем requests (должен быть установлен)
                try:
                    import requests
                except ImportError:
                    return jsonify({
                        "success": False,
                        "error": "Библиотека requests не установлена",
                        "message": "Установите библиотеку requests: pip install requests",
                    }), 500

                headers = {
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "Accept": "application/json",
                    "Referer": f"https://yandex.ru/sprav/{external_id}/p/edit/reviews/",
                }
                response = requests.get(test_url, params=test_params, cookies=cookies_dict, headers=headers, timeout=10, allow_redirects=False)

                # Логируем для отладки
                print(f"🔍 Тест cookies: URL={test_url}, статус={response.status_code}, content-type={response.headers.get('Content-Type', 'N/A')}")
                if response.status_code != 200:
                    print(f"   Ответ (первые 200 символов): {response.text[:200]}")

                # Проверяем content-type ответа
                content_type = response.headers.get('Content-Type', '').lower()

                # Если получили HTML вместо JSON - это признак того, что cookies устарели
                if 'text/html' in content_type or 'html' in response.text[:100].lower():
                    # Проверяем, есть ли в ответе признаки капчи или авторизации
                    response_text_lower = response.text.lower()
                    if 'captcha' in response_text_lower or 'робот' in response_text_lower:
                        return jsonify({
                            "success": False,
                            "error": "Капча",
                            "message": "Яндекс показал капчу. Cookies могут быть недействительны или запросы похожи на автоматические.",
                            "status_code": 200,
                        }), 200
                    elif 'авторизац' in response_text_lower or 'login' in response_text_lower or 'passport.yandex.ru' in response.text:
                        return jsonify({
                            "success": False,
                            "error": "Требуется авторизация",
                            "message": "Cookies устарели. Яндекс перенаправляет на страницу авторизации. Обновите cookies в личном кабинете.",
                            "status_code": 401,
                        }), 200
                    else:
                        return jsonify({
                            "success": False,
                            "error": "HTML ответ вместо JSON",
                            "message": "Сервер вернул HTML вместо JSON. Cookies устарели или требуется авторизация.",
                            "status_code": response.status_code,
                        }), 200

                if response.status_code == 200:
                    try:
                        data = response.json()
                        # Проверяем, что это не ошибка
                        if "error" in data:
                            error_msg = data.get("error", {}).get("message", "Неизвестная ошибка")
                            if error_msg == "NEED_RESET":
                                return jsonify({
                                    "success": False,
                                    "error": "Сессия истекла (NEED_RESET)",
                                    "message": "Cookies устарели. Обновите cookies в личном кабинете Яндекс.Бизнес.",
                                    "status_code": 401,
                                }), 200
                            return jsonify({
                                "success": False,
                                "error": error_msg,
                                "status_code": response.status_code,
                            }), 200
                        return jsonify({
                            "success": True,
                            "message": "Cookies работают корректно!",
                            "status_code": 200,
                        }), 200
                    except json.JSONDecodeError as e:
                        # Если не JSON, проверяем, что это за ответ
                        content_type = response.headers.get('Content-Type', '').lower()
                        response_text = response.text[:500]  # Первые 500 символов

                        # Проверяем на капчу или HTML
                        if 'captcha' in response_text.lower() or 'робот' in response_text.lower():
                            return jsonify({
                                "success": False,
                                "error": "Капча",
                                "message": "Яндекс показал капчу. Cookies могут быть недействительны или запросы похожи на автоматические.",
                                "status_code": 200,
                            }), 200

                        return jsonify({
                            "success": False,
                            "error": "Получен не JSON ответ",
                            "message": f"Сервер вернул {content_type}. Возможно, требуется авторизация или cookies устарели.",
                            "status_code": response.status_code,
                            "content_type": content_type,
                        }), 200
                    except Exception as e:
                        return jsonify({
                            "success": False,
                            "error": f"Ошибка парсинга ответа: {str(e)}",
                            "status_code": response.status_code,
                        }), 200
                elif response.status_code == 401:
                    return jsonify({
                        "success": False,
                        "error": "Не авторизован (401)",
                        "message": "Cookies устарели или недействительны. Обновите cookies.",
                        "status_code": 401,
                    }), 200
                elif response.status_code == 302:
                    return jsonify({
                        "success": False,
                        "error": "Редирект (302)",
                        "message": "Cookies устарели. Яндекс перенаправляет на страницу авторизации.",
                        "status_code": 302,
                    }), 200
                else:
                    return jsonify({
                        "success": False,
                        "error": f"Ошибка {response.status_code}",
                        "status_code": response.status_code,
                    }), 200
            except requests.exceptions.RequestException as e:
                error_msg = str(e)
                # Определяем тип ошибки для более понятного сообщения
                if "Exceeded" in error_msg and "redirects" in error_msg:
                    return jsonify({
                        "success": False,
                        "error": "Редирект (302)",
                        "message": "Cookies устарели. Яндекс перенаправляет на страницу авторизации (слишком много редиректов).",
                        "status_code": 302,
                    }), 200
                elif "timeout" in error_msg.lower():
                    return jsonify({
                        "success": False,
                        "error": "Таймаут",
                        "message": "Превышено время ожидания ответа от сервера Яндекс.",
                    }), 200
                else:
                    return jsonify({
                        "success": False,
                        "error": f"Ошибка запроса: {error_msg}",
                        "message": "Не удалось выполнить запрос к API Яндекс.Бизнес.",
                    }), 200
        elif source == "2gis":
            # Для 2ГИС можно добавить тестирование позже
            return jsonify({
                "success": True,
                "message": "Cookies приняты (тестирование 2ГИС пока не реализовано)",
            }), 200

        return jsonify({"error": "Неизвестный source"}), 400

    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ Ошибка в test_external_account_cookies: {e}")
        print(error_trace)
        return jsonify({
            "success": False,
            "error": f"Внутренняя ошибка сервера: {str(e)}",
            "message": "Произошла ошибка при тестировании cookies. Проверьте логи сервера.",
        }), 500

@external_accounts_bp.route("/api/business/<business_id>/external/reviews", methods=["GET"])
def get_external_reviews(business_id):
    """
    Получить все спарсенные отзывы из внешних источников (Яндекс.Бизнес, Google Business, 2ГИС)
    для конкретного бизнеса.
    """
    try:
        # Авторизация: владелец бизнеса или суперадмин
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(" ")[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Проверяем, что пользователь владелец бизнеса или суперадмин
        owner_id = get_business_owner_id(cursor, business_id)
        if not owner_id:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404

        if owner_id != user_data["user_id"] and not db.is_superadmin(user_data["user_id"]):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403

        # Проверяем, существует ли таблица externalbusinessreviews (Postgres)
        cursor.execute("SELECT to_regclass('public.externalbusinessreviews')")
        table_exists = cursor.fetchone()
        if not table_exists or (table_exists and (table_exists[0] if isinstance(table_exists, (list, tuple)) else table_exists) is None):
            db.close()
            return jsonify({"success": True, "reviews": [], "total": 0, "with_response": 0, "without_response": 0})

        requested_scope = str(request.args.get("scope") or "").strip().lower()
        source_filter_raw = str(request.args.get("source") or "").strip().lower()
        business_row, network_id, aggregate_network = _resolve_network_scope_for_business(cursor, business_id, requested_scope)

        review_query = """
            SELECT r.id, r.source, r.external_review_id, r.rating, r.author_name, r.text,
                   r.response_text, r.response_at, r.published_at, r.created_at,
                   d.id AS reply_draft_id, d.generated_text AS reply_draft_text, d.status AS reply_draft_status,
                   b.id AS location_business_id, b.name AS location_name, b.address AS location_address
            FROM externalbusinessreviews r
            LEFT JOIN reviewreplydrafts d ON d.review_id = r.id
            LEFT JOIN businesses b ON b.id = r.business_id
        """
        review_params = []
        if aggregate_network:
            review_query += """
            WHERE {network_filter}
            """
            review_query = review_query.replace("{network_filter}", _network_business_filter("r.business_id"))
            review_params.extend([network_id, network_id])
        else:
            review_query += " WHERE r.business_id = %s "
            review_params.append(business_id)
        source_filter_sql = _map_source_filter_sql("r.source", source_filter_raw)
        if source_filter_sql:
            review_query += f" AND {source_filter_sql} "

        review_query += " ORDER BY COALESCE(r.published_at, r.created_at) DESC, r.created_at DESC "
        cursor.execute(review_query, tuple(review_params))
        rows = cursor.fetchall()
        db.close()

        reviews = []
        for r in rows:
            rd = _row_to_dict(cursor, r)
            if not rd:
                continue
            resp_text = rd.get("response_text")
            reviews.append({
                "id": rd.get("id"),
                "source": rd.get("source"),
                "external_review_id": rd.get("external_review_id"),
                "rating": rd.get("rating"),
                "author_name": rd.get("author_name") or "Анонимный пользователь",
                "text": rd.get("text") or "",
                "response_text": resp_text,
                "response_at": rd.get("response_at"),
                "reply_draft_id": rd.get("reply_draft_id"),
                "reply_draft_text": rd.get("reply_draft_text"),
                "reply_draft_status": rd.get("reply_draft_status"),
                "published_at": rd.get("published_at"),
                "created_at": rd.get("created_at"),
                "has_response": bool(resp_text),
                "location_business_id": rd.get("location_business_id"),
                "location_name": rd.get("location_name"),
                "location_address": rd.get("location_address"),
            })

        return jsonify({
            "success": True,
            "reviews": reviews,
            "total": len(reviews),
            "with_response": sum(1 for x in reviews if x["has_response"]),
            "without_response": sum(1 for x in reviews if not x["has_response"]),
            "scope": "network" if aggregate_network else "business",
            "network_id": network_id if aggregate_network else None,
            "source": source_filter_raw or "all",
        })

    except Exception as e:
        import traceback
        err_tb = traceback.format_exc()
        print(f"❌ get_external_reviews: {e}\n{err_tb}")
        payload = {"success": False, "where": "get_external_reviews", "error": str(e)}
        if getattr(current_app, "debug", False):
            payload["traceback"] = err_tb
        return jsonify(payload), 500

@external_accounts_bp.route("/api/business/<business_id>/external/summary", methods=["GET"])
def get_external_summary(business_id):
    """
    Получить сводку данных из внешних источников (рейтинг, количество отзывов, статистика).
    """
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(" ")[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Проверяем доступ
        owner_id = get_business_owner_id(cursor, business_id)
        if not owner_id:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404

        if owner_id != user_data["user_id"] and not db.is_superadmin(user_data["user_id"]):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403

        # Проверяем, существуют ли таблицы (Postgres)
        cursor.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name IN ('externalbusinessstats', 'externalbusinessreviews')
        """)
        tables = {row['table_name'] if isinstance(row, dict) else row[0] for row in cursor.fetchall()}

        if 'externalbusinessstats' not in tables or 'externalbusinessreviews' not in tables:
            # Таблицы не существуют — отдаём хотя бы данные из cards (парсинг)
            cursor.execute("""
                SELECT created_at, rating, reviews_count, competitors
                FROM cards WHERE business_id = %s ORDER BY created_at DESC LIMIT 1
            """, (business_id,))
            raw = cursor.fetchone()
            card_row = _row_to_dict(cursor, raw) if raw else None
            db.close()
            rating = None
            reviews_total = 0
            last_parse_date = None
            competitors = None
            if card_row:
                try:
                    rating = float(card_row.get("rating")) if card_row.get("rating") is not None else None
                except (TypeError, ValueError):
                    pass
                reviews_total = int(card_row.get("reviews_count") or 0)
                last_parse_date = card_row.get("created_at")
                competitors = card_row.get("competitors")
            return jsonify({
                "success": True,
                "rating": rating,
                "reviews_total": reviews_total,
                "reviews_with_response": 0,
                "reviews_without_response": reviews_total,
                "last_sync_date": None,
                "last_parse_date": last_parse_date,
                "competitors": competitors,
                "scope": "business",
                "network_id": None,
            })

        requested_scope = str(request.args.get("scope") or "").strip().lower()
        source_filter_raw = str(request.args.get("source") or "").strip().lower()
        business_row, network_id, aggregate_network = _resolve_network_scope_for_business(cursor, business_id, requested_scope)

        stats_query = """
            SELECT business_id, source, rating, reviews_total, date
            FROM externalbusinessstats
            WHERE 1 = 1
        """
        stats_params = []
        stats_source_filter = _map_source_filter_sql("source", source_filter_raw)
        if stats_source_filter:
            stats_query += f" AND {stats_source_filter} "
        if aggregate_network:
            stats_query += """
              AND {network_filter}
            ORDER BY business_id, date DESC
            """
            stats_query = stats_query.replace("{network_filter}", _network_business_filter("business_id"))
            stats_params.extend([network_id, network_id])
        else:
            stats_query += """
              AND business_id = %s
            ORDER BY date DESC
            LIMIT 1
            """
            stats_params.append(business_id)

        cursor.execute(stats_query, tuple(stats_params))
        stats_rows = cursor.fetchall()
        stats_dicts = [_row_to_dict(cursor, row) for row in stats_rows]

        def _stats_source_priority(source_value):
            source_name = str(source_value or "").strip().lower()
            if source_name == "google_maps":
                return 3
            if source_name in {"yandex_maps", "yandex_business"}:
                return 2
            return 1

        def _pick_best_stat(rows):
            best_item = None
            best_key = (datetime.min.date(), -1, -1)
            for item in rows:
                item_date = item.get("date") or datetime.min.date()
                reviews_total = int(item.get("reviews_total") or 0)
                priority = _stats_source_priority(item.get("source"))
                key = (item_date, reviews_total, priority)
                if best_item is None or key > best_key:
                    best_item = item
                    best_key = key
            return best_item

        if aggregate_network:
            grouped_stats = {}
            for item in stats_dicts:
                business_stat_id = str(item.get("business_id") or "").strip()
                if not business_stat_id:
                    continue
                grouped_stats.setdefault(business_stat_id, []).append(item)
            stats_dicts = []
            for items in grouped_stats.values():
                best_item = _pick_best_stat(items)
                if best_item:
                    stats_dicts.append(best_item)

        stats_row = _pick_best_stat(stats_dicts) if stats_dicts else None

        if aggregate_network and stats_dicts:
            weighted_sum = 0.0
            weighted_count = 0
            latest_sync_date = None
            for item in stats_dicts:
                item_rating = item.get("rating")
                item_reviews_total = item.get("reviews_total")
                item_date = item.get("date")
                if latest_sync_date is None or (item_date and item_date > latest_sync_date):
                    latest_sync_date = item_date
                try:
                    rating_value = float(item_rating) if item_rating is not None else None
                except (TypeError, ValueError):
                    rating_value = None
                reviews_value = int(item_reviews_total or 0)
                if rating_value is not None and reviews_value > 0:
                    weighted_sum += rating_value * reviews_value
                    weighted_count += reviews_value
            aggregated_rating = None
            if weighted_count > 0:
                aggregated_rating = weighted_sum / weighted_count
            stats_row = {
                "rating": aggregated_rating,
                "reviews_total": weighted_count,
                "date": latest_sync_date,
            }

        reviews_summary_query = """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN response_text IS NOT NULL AND response_text != '' THEN 1 ELSE 0 END) AS with_response,
                   SUM(CASE WHEN response_text IS NULL OR response_text = '' THEN 1 ELSE 0 END) AS without_response
            FROM externalbusinessreviews
            WHERE 1 = 1
        """
        reviews_summary_params = []
        reviews_source_filter = _map_source_filter_sql("source", source_filter_raw)
        if reviews_source_filter:
            reviews_summary_query += f" AND {reviews_source_filter} "
        if aggregate_network:
            reviews_summary_query += """
              AND {network_filter}
            """
            reviews_summary_query = reviews_summary_query.replace("{network_filter}", _network_business_filter("business_id"))
            reviews_summary_params.extend([network_id, network_id])
        else:
            reviews_summary_query += " AND business_id = %s "
            reviews_summary_params.append(business_id)

        cursor.execute(reviews_summary_query, tuple(reviews_summary_params))
        raw_reviews = cursor.fetchone()
        reviews_row = _row_to_dict(cursor, raw_reviews) if raw_reviews else None

        # Карточка для UI:
        # full_card  — последняя snapshot_type='full' (богатый слепок)
        # metrics_card — последняя is_latest (может быть metrics_update или full)

        # 1) full_card: последняя полноценная карточка
        # overview исторически хранится как TEXT/JSON, поэтому фильтруем snapshot_type в Python
        cursor.execute(
            """
            SELECT *
            FROM cards
            WHERE business_id = %s
            ORDER BY created_at DESC
            LIMIT 50
            """,
            (business_id,),
        )
        raw_cards = cursor.fetchall()
        all_cards = [_row_to_dict(cursor, row) for row in raw_cards]

        # 2) metrics_card: последняя is_latest (она может быть metrics_update или full)
        cursor.execute(
            """
            SELECT *
            FROM cards
            WHERE business_id = %s AND is_latest = TRUE
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (business_id,),
        )
        raw_latest = cursor.fetchone()
        metrics_card = _row_to_dict(cursor, raw_latest) if raw_latest else None

        def _as_dict_obj(value):
            if isinstance(value, dict):
                return value
            if isinstance(value, str):
                try:
                    parsed = json.loads(value)
                    return parsed if isinstance(parsed, dict) else {}
                except Exception:
                    return {}
            return {}

        full_card = next((card for card in all_cards if _as_dict_obj(card.get("overview")).get("snapshot_type") == "full"), None)

        # 3) chosen_card: источник rich-контента (предпочитаем full, иначе metrics_card)
        chosen_card = full_card or metrics_card
        parse_row = chosen_card
        last_parse_date = (
            metrics_card.get("created_at")
            if metrics_card and metrics_card.get("created_at")
            else (parse_row.get("created_at") if parse_row else None)
        )

        db.close()

        # Метрики: сначала внешние источники, затем cards (metrics_card / chosen_card)
        rating = stats_row.get("rating") if stats_row else None
        reviews_total = (reviews_row.get("total") or 0) if reviews_row else 0
        reviews_with_response = (reviews_row.get("with_response") or 0) if reviews_row else 0
        reviews_without_response = (reviews_row.get("without_response") or 0) if reviews_row else 0

        # 4) Fallback по метрикам:
        #   - сначала metrics_card, если это metrics_update
        #   - затем chosen_card (обычно full)
        metrics_overview = _as_dict_obj(metrics_card.get("overview")) if metrics_card else {}
        if rating is None:
            if metrics_card and metrics_overview.get("snapshot_type") == "metrics_update" and metrics_card.get("rating") is not None:
                try:
                    rating = float(metrics_card.get("rating"))
                except (TypeError, ValueError):
                    rating = None
            elif parse_row and parse_row.get("rating") is not None:
                try:
                    rating = float(parse_row.get("rating"))
                except (TypeError, ValueError):
                    rating = None

        if reviews_total == 0:
            if metrics_card and metrics_overview.get("snapshot_type") == "metrics_update" and (metrics_card.get("reviews_count") or 0) != 0:
                reviews_total = int(metrics_card.get("reviews_count") or 0)
            elif parse_row and (parse_row.get("reviews_count") or 0) != 0:
                reviews_total = int(parse_row.get("reviews_count") or 0)

        return jsonify({
            "success": True,
            "rating": float(rating) if rating is not None else None,
            "reviews_total": reviews_total,
            "reviews_with_response": reviews_with_response,
            "reviews_without_response": reviews_without_response,
            "last_sync_date": stats_row.get("date") if stats_row else None,
            "last_parse_date": last_parse_date,
            "competitors": parse_row.get("competitors") if parse_row else None,
            "scope": "network" if aggregate_network else "business",
            "network_id": network_id if aggregate_network else None,
            "source": source_filter_raw or "all",
        })

    except Exception as e:
        import traceback
        err_tb = traceback.format_exc()
        print(f"❌ get_external_summary: {e}\n{err_tb}")
        payload = {"success": False, "where": "get_external_summary", "error_type": type(e).__name__, "error": str(e)}
        if getattr(current_app, "debug", False):
            payload["traceback"] = err_tb
        return jsonify(payload), 500

@external_accounts_bp.route("/api/business/<business_id>/external/posts", methods=["GET"])
def get_external_posts(business_id):
    """
    Получить все спарсенные посты/новости из внешних источников.
    """
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(" ")[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Проверяем доступ
        owner_id = get_business_owner_id(cursor, business_id)
        if not owner_id:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404

        if owner_id != user_data["user_id"] and not db.is_superadmin(user_data["user_id"]):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403

        requested_scope = str(request.args.get("scope") or "").strip().lower()
        business_row, network_id, aggregate_network = _resolve_network_scope_for_business(cursor, business_id, requested_scope)

        def _is_placeholder_post(title_value, text_value):
            title_text = str(title_value or "").strip().lower()
            body_text = str(text_value or "").strip().lower()
            combined_text = " ".join(part for part in [title_text, body_text] if part).strip()
            if not combined_text:
                return True
            placeholder_patterns = [
                "business update: we updated our service information",
                "ready to help you choose the right visit format",
                "for details or booking, contact us by phone or message",
            ]
            return any(pattern in combined_text for pattern in placeholder_patterns)

        # Сначала пробуем externalbusinessposts (Postgres)
        cursor.execute("SELECT to_regclass('public.externalbusinessposts') AS table_ref")
        table_exists_row = cursor.fetchone()
        table_exists_data = _row_to_dict(cursor, table_exists_row) if table_exists_row else {}
        table_ref = table_exists_data.get("table_ref")
        posts = []
        if table_ref:
            posts_query = """
                SELECT p.id, p.source, p.external_post_id, p.title, p.text, p.published_at, p.created_at,
                       b.id AS location_business_id, b.name AS location_name, b.address AS location_address
                FROM externalbusinessposts p
                LEFT JOIN businesses b ON b.id = p.business_id
                WHERE (p.title IS NULL OR p.title NOT IN ('working_intervals', 'urls', 'phone', 'photos', 'price_lists', 'logo', 'features', 'english_name'))
                AND (p.title IS NOT NULL OR p.text IS NOT NULL)
                AND (COALESCE(p.title, '') != '' OR COALESCE(p.text, '') != '')
            """
            posts_params = []
            if aggregate_network:
                posts_query += """
                AND {network_filter}
                """
                posts_query = posts_query.replace("{network_filter}", _network_business_filter("p.business_id"))
                posts_params.extend([network_id, network_id])
            else:
                posts_query += " AND p.business_id = %s "
                posts_params.append(business_id)

            posts_query += " ORDER BY COALESCE(p.published_at, p.created_at) DESC, p.created_at DESC "
            cursor.execute(posts_query, tuple(posts_params))
            for r in cursor.fetchall():
                rd = _row_to_dict(cursor, r)
                if not rd:
                    continue
                title = rd.get("title") or ""
                text = rd.get("text") or ""
                if _is_placeholder_post(title, text):
                    continue
                posts.append({
                    "id": rd.get("id"),
                    "source": rd.get("source") or "external",
                    "external_post_id": rd.get("external_post_id"),
                    "title": title,
                    "text": text,
                    "published_at": rd.get("published_at"),
                    "created_at": rd.get("created_at"),
                    "location_business_id": rd.get("location_business_id"),
                    "location_name": rd.get("location_name"),
                    "location_address": rd.get("location_address"),
                })

        # Если постов нет — временно отдаём новости из последней карточки (cards.news)
        if not posts:
            fallback_query = """
                SELECT DISTINCT ON (c.business_id)
                       c.business_id,
                       c.news,
                       c.created_at,
                       b.name AS location_name,
                       b.address AS location_address
                FROM cards c
                LEFT JOIN businesses b ON b.id = c.business_id
            """
            fallback_params = []
            if aggregate_network:
                fallback_query += """
                WHERE {network_filter}
                """
                fallback_query = fallback_query.replace("{network_filter}", _network_business_filter("c.business_id"))
                fallback_params.extend([network_id, network_id])
            else:
                fallback_query += " WHERE c.business_id = %s "
                fallback_params.append(business_id)

            fallback_query += " ORDER BY c.business_id, c.created_at DESC "
            cursor.execute(fallback_query, tuple(fallback_params))
            for card_row in cursor.fetchall():
                rd = _row_to_dict(cursor, card_row)
                news_raw = rd.get("news") if rd else None
                if news_raw is None:
                    continue
                if isinstance(news_raw, list):
                    news_list = news_raw
                elif isinstance(news_raw, str):
                    try:
                        news_list = json.loads(news_raw) if news_raw.strip() else []
                    except Exception:
                        news_list = []
                else:
                    news_list = []
                for i, entry in enumerate(news_list):
                    if not isinstance(entry, dict):
                        continue
                    title = entry.get("title") or entry.get("name") or ""
                    text = entry.get("text") or entry.get("content") or ""
                    if _is_placeholder_post(title, text):
                        continue
                    posts.append({
                        "id": f"card_news_{rd.get('business_id')}_{i}",
                        "source": "yandex_maps",
                        "external_post_id": None,
                        "title": title,
                        "text": text,
                        "published_at": entry.get("published_at") or entry.get("date"),
                        "created_at": rd.get("created_at"),
                        "location_business_id": rd.get("business_id"),
                        "location_name": rd.get("location_name"),
                        "location_address": rd.get("location_address"),
                    })

        db.close()
        return jsonify({
            "success": True,
            "posts": posts,
            "total": len(posts),
            "scope": "network" if aggregate_network else "business",
            "network_id": network_id if aggregate_network else None,
        })

    except Exception as e:
        import traceback
        err_tb = traceback.format_exc()
        print(f"❌ get_external_posts: {e}\n{err_tb}")
        payload = {"success": False, "where": "get_external_posts", "error": str(e)}
        if getattr(current_app, "debug", False):
            payload["traceback"] = err_tb
        return jsonify(payload), 500
