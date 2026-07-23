#!/usr/bin/env python3
"""
API эндпоинты для Google Business Profile интеграции
"""
import os
import json
import uuid
from flask import Blueprint, request, jsonify, redirect
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from database_manager import DatabaseManager
from auth_system import verify_session
from google_business_auth import GoogleBusinessAuth
from google_sheets_auth import GOOGLE_SHEETS_SCOPE, GoogleSheetsAuth
from google_business_api import GoogleBusinessAPIError
from google_business_sync_worker import GoogleBusinessSyncWorker
from auth_encryption import encrypt_auth_data, decrypt_auth_data
from core.helpers import get_business_owner_id

google_business_bp = Blueprint('google_business', __name__)

DEFAULT_GOOGLE_RETURN_PATH = "/dashboard/settings/integrations?focus=google_business"
DEFAULT_GOOGLE_SHEETS_RETURN_PATH = "/dashboard/settings/integrations?focus=google_sheets"
GOOGLE_OAUTH_STATE_MAX_AGE_SECONDS = 600

def _row_value(row, key: str, index: int = 0):
    if row is None:
        return None
    if hasattr(row, "get"):
        return row.get(key)
    try:
        return row[index]
    except Exception:
        return None

def _auth_data_column(cursor) -> str:
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'externalbusinessaccounts'
          AND column_name IN ('auth_data_encrypted', 'auth_data')
        """
    )
    columns = {_row_value(row, "column_name", 0) for row in cursor.fetchall()}
    return "auth_data_encrypted" if "auth_data_encrypted" in columns else "auth_data"

def _google_business_error_response(error: Exception):
    message = str(error)
    if "SERVICE_DISABLED" in message or "mybusinessaccountmanagement.googleapis.com" in message:
        return jsonify({
            "success": False,
            "status": "google_business_api_disabled",
            "error": "В Google Cloud project LocalOS не включён или не одобрен My Business Account Management API. Карточки в Google аккаунте есть, но LocalOS пока не может прочитать их через API.",
            "next_action": "Откройте Google Cloud Console project totemic-union-440908-s8 и проверьте My Business Account Management API / quota.",
            "activation_url": "https://console.developers.google.com/apis/api/mybusinessaccountmanagement.googleapis.com/overview?project=totemic-union-440908-s8",
        }), 502
    return jsonify({
        "success": False,
        "status": "google_business_api_error",
        "error": message or "Не удалось получить карточки Google Business Profile",
    }), 502


def _safe_google_return_path(value: str | None) -> str:
    clean = str(value or "").strip()
    if not clean:
        return DEFAULT_GOOGLE_RETURN_PATH
    if clean.startswith("//") or "\r" in clean or "\n" in clean:
        return DEFAULT_GOOGLE_RETURN_PATH
    if not clean.startswith("/dashboard/"):
        return DEFAULT_GOOGLE_RETURN_PATH
    return clean[:500]


def _append_google_auth_status(path: str, status: str, purpose: str = "google_business") -> str:
    safe_path = _safe_google_return_path(path)
    separator = "&" if "?" in safe_path else "?"
    return f"{safe_path}{separator}google_auth={status}&google_auth_purpose={purpose}"


def _google_oauth_state_serializer() -> URLSafeTimedSerializer:
    secret = str(
        os.getenv("GOOGLE_OAUTH_STATE_SECRET")
        or os.getenv("EXTERNAL_AUTH_SECRET_KEY")
        or ""
    ).strip()
    if not secret:
        raise RuntimeError("GOOGLE_OAUTH_STATE_SECRET or EXTERNAL_AUTH_SECRET_KEY must be configured")
    return URLSafeTimedSerializer(secret, salt="localos-google-oauth-state-v3")


def _encode_google_oauth_state(
    user_id: str,
    business_id: str,
    return_to: str | None,
    purpose: str = "google_business",
) -> str:
    payload = {
        "user_id": str(user_id or ""),
        "business_id": str(business_id or ""),
        "return_to": _safe_google_return_path(return_to),
        "purpose": str(purpose or "google_business"),
    }
    return "v3:" + _google_oauth_state_serializer().dumps(payload)


def _decode_google_oauth_state(state: str | None, expected_purpose: str = "google_business") -> dict:
    raw = str(state or "").strip()
    if not raw.startswith("v3:"):
        return {}
    try:
        payload = _google_oauth_state_serializer().loads(
            raw[3:],
            max_age=GOOGLE_OAUTH_STATE_MAX_AGE_SECONDS,
        )
    except (BadSignature, SignatureExpired):
        return {}
    if not isinstance(payload, dict):
        return {}
    purpose = str(payload.get("purpose") or "")
    if purpose != expected_purpose:
        return {}
    return {
        "user_id": str(payload.get("user_id") or ""),
        "business_id": str(payload.get("business_id") or ""),
        "return_to": _safe_google_return_path(str(payload.get("return_to") or "")),
        "purpose": purpose,
    }

def _public_location(location: dict) -> dict:
    address = location.get("storefrontAddress") if isinstance(location.get("storefrontAddress"), dict) else {}
    lines = address.get("addressLines") if isinstance(address.get("addressLines"), list) else []
    category = location.get("primaryCategory") if isinstance(location.get("primaryCategory"), dict) else {}
    metadata = location.get("metadata") if isinstance(location.get("metadata"), dict) else {}
    title = location.get("title") or location.get("locationName") or location.get("name")
    account_name = str(location.get("accountName") or "").strip()
    location_name = str(location.get("name") or "").strip()
    public_name = location_name
    if account_name and location_name.startswith("locations/"):
        public_name = f"{account_name}/{location_name}"
    return {
        "name": public_name,
        "raw_name": location_name,
        "title": title,
        "address": ", ".join([line for line in lines if line]),
        "locality": address.get("locality"),
        "region": address.get("administrativeArea"),
        "postal_code": address.get("postalCode"),
        "primary_category": category.get("displayName") or category.get("categoryId"),
        "place_id": metadata.get("placeId"),
        "maps_uri": metadata.get("mapsUri"),
        "account_name": account_name,
        "account_display_name": location.get("accountDisplayName"),
    }

def _verify_auth_and_access(business_id: str) -> tuple[dict, DatabaseManager] | tuple[None, None]:
    """Проверить авторизацию и доступ к бизнесу. Возвращает (user_data, db) или (None, None)"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None, None
    
    token = auth_header.split(' ')[1]
    user_data = verify_session(token)
    if not user_data:
        return None, None
    
    db = DatabaseManager()
    cursor = db.conn.cursor()
    owner_id = get_business_owner_id(cursor, business_id)
    
    if not owner_id:
        db.close()
        return None, None
    
    if owner_id != user_data['user_id'] and not user_data.get('is_superadmin'):
        db.close()
        return None, None
    
    return user_data, db

def _get_google_account(cursor, business_id: str, account_id: str = None) -> dict | None:
    """Получить Google аккаунт для бизнеса"""
    if account_id:
        cursor.execute("""
            SELECT * FROM externalbusinessaccounts
            WHERE id = %s AND business_id = %s AND source = 'google_business' AND is_active = TRUE
        """, (account_id, business_id))
    else:
        cursor.execute("""
            SELECT * FROM externalbusinessaccounts
            WHERE business_id = %s AND source = 'google_business' AND is_active = TRUE
            LIMIT 1
        """, (business_id,))
    
    account_row = cursor.fetchone()
    return dict(account_row) if account_row else None


def _get_google_sheets_account(cursor, business_id: str) -> dict | None:
    cursor.execute(
        """
        SELECT * FROM externalbusinessaccounts
        WHERE business_id = %s AND source = 'google_sheets' AND is_active = TRUE
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (business_id,),
    )
    account_row = cursor.fetchone()
    return dict(account_row) if account_row else None


def _credentials_payload(cursor, account: dict) -> dict:
    auth_column = _auth_data_column(cursor)
    encrypted_auth = str(account.get(auth_column) or "")
    if not encrypted_auth:
        return {}
    try:
        payload = json.loads(decrypt_auth_data(encrypted_auth) or "{}")
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _get_legacy_sheets_account(cursor, business_id: str) -> dict | None:
    account = _get_google_account(cursor, business_id)
    if not account:
        return None
    credentials = _credentials_payload(cursor, account)
    scopes = credentials.get("scopes") if isinstance(credentials.get("scopes"), list) else []
    return account if GOOGLE_SHEETS_SCOPE in [str(scope) for scope in scopes] else None


def _sync_google_sheets_agent_auth_refs(cursor, business_id: str, auth_ref: str) -> int:
    normalized_business_id = str(business_id or "").strip()
    normalized_auth_ref = str(auth_ref or "").strip()
    if not normalized_business_id or not normalized_auth_ref:
        return 0
    cursor.execute(
        """
        UPDATE agent_integrations integration
        SET auth_ref = %s, updated_at = CURRENT_TIMESTAMP
        WHERE integration.business_id = %s
          AND integration.provider = 'google_sheets'
          AND integration.status = 'active'
          AND (
            COALESCE(integration.auth_ref, '') = ''
            OR EXISTS (
                SELECT 1
                FROM externalbusinessaccounts account
                WHERE account.id = integration.auth_ref
                  AND account.business_id = integration.business_id
                  AND (account.is_active = FALSE OR account.source = 'google_business')
            )
          )
        """,
        (normalized_auth_ref, normalized_business_id),
    )
    return int(getattr(cursor, "rowcount", 0) or 0)

@google_business_bp.route('/api/google/oauth/authorize', methods=['GET', 'OPTIONS'])
def google_oauth_authorize():
    """
    Начать OAuth авторизацию
    
    Query параметры:
    - business_id: ID бизнеса для подключения Google
    
    Returns:
    - auth_url: URL для редиректа пользователя на авторизацию Google
    """
    if request.method == 'OPTIONS':
        return ('', 204)
    
    try:
        # Проверка авторизации
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        business_id = request.args.get('business_id')
        if not business_id:
            return jsonify({"error": "business_id обязателен"}), 400
        
        # Проверяем доступ к бизнесу
        db = DatabaseManager()
        cursor = db.conn.cursor()
        owner_id = get_business_owner_id(cursor, business_id)
        db.close()
        
        if not owner_id:
            return jsonify({"error": "Бизнес не найден"}), 404
        
        if owner_id != user_data['user_id'] and not user_data.get('is_superadmin'):
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403
        
        state = _encode_google_oauth_state(
            str(user_data['user_id']),
            str(business_id),
            request.args.get("return_to"),
            "google_business",
        )
        
        auth = GoogleBusinessAuth()
        auth_url = auth.get_authorization_url(state)
        
        return jsonify({
            "success": True,
            "auth_url": auth_url
        })
    except Exception as e:
        print(f"❌ Ошибка OAuth авторизации: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@google_business_bp.route('/api/google/oauth/callback', methods=['GET'])
def google_oauth_callback():
    """
    Обработка OAuth callback от Google
    
    Query параметры:
    - code: Authorization code от Google
    - state: State для проверки (user_id_business_id)
    
    Returns:
    - HTML страница с редиректом на фронтенд или сообщение об успехе
    """
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')
    
    frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')
    
    state_payload = _decode_google_oauth_state(state, "google_business")
    return_to = str(state_payload.get("return_to") or DEFAULT_GOOGLE_RETURN_PATH)

    if error:
        # Пользователь отменил авторизацию
        return redirect(f"{frontend_url}{_append_google_auth_status(return_to, 'error')}")
    
    if not code or not state:
        return redirect(f"{frontend_url}{_append_google_auth_status(return_to, 'error')}")
    
    user_id = str(state_payload.get("user_id") or "")
    business_id = str(state_payload.get("business_id") or "")
    if not user_id or not business_id:
        return redirect(f"{frontend_url}{_append_google_auth_status(return_to, 'error')}")
    
    try:
        auth = GoogleBusinessAuth()
        credentials = auth.get_credentials_from_code(code)
        
        # Преобразуем credentials в словарь
        creds_dict = auth.credentials_to_dict(credentials)
        creds_json = json.dumps(creds_dict)
        
        # Шифруем credentials
        encrypted_creds = encrypt_auth_data(creds_json)
        
        # Сохраняем или обновляем аккаунт в ExternalBusinessAccounts
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Проверяем, есть ли уже аккаунт для этого бизнеса
        cursor.execute("""
            SELECT id FROM externalbusinessaccounts
            WHERE business_id = %s AND source = 'google_business'
        """, (business_id,))
        existing = cursor.fetchone()
        auth_column = _auth_data_column(cursor)
        
        if existing:
            # Обновляем существующий аккаунт
            account_id = str(_row_value(existing, "id", 0) or "")
            cursor.execute("""
                UPDATE externalbusinessaccounts
                SET """ + auth_column + """ = %s, is_active = TRUE, last_sync_at = CURRENT_TIMESTAMP, last_error = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (encrypted_creds, account_id))
        else:
            # Создаем новый аккаунт
            account_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO externalbusinessaccounts
                (id, business_id, source, external_id, display_name, """ + auth_column + """, is_active, created_at, updated_at)
                VALUES (%s, %s, 'google_business', %s, %s, %s, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (account_id, business_id, None, 'Google Business', encrypted_creds))
        db.conn.commit()
        db.close()
        
        # Редиректим в исходный пользовательский сценарий с успешным статусом
        return redirect(f"{frontend_url}{_append_google_auth_status(return_to, 'success')}")
        
    except Exception as e:
        print(f"❌ Ошибка обработки OAuth callback: {e}")
        import traceback
        traceback.print_exc()
        return redirect(f"{frontend_url}{_append_google_auth_status(return_to, 'error')}")


@google_business_bp.route('/api/google/sheets/oauth/authorize', methods=['GET', 'OPTIONS'])
def google_sheets_oauth_authorize():
    """Start the dedicated Google Sheets OAuth flow."""
    if request.method == 'OPTIONS':
        return ('', 204)
    business_id = str(request.args.get('business_id') or '').strip()
    if not business_id:
        return jsonify({"error": "business_id обязателен"}), 400
    user_data, db = _verify_auth_and_access(business_id)
    if not user_data:
        return jsonify({"error": "Требуется авторизация или нет доступа к бизнесу"}), 401
    db.close()
    try:
        return_to = request.args.get("return_to") or DEFAULT_GOOGLE_SHEETS_RETURN_PATH
        state = _encode_google_oauth_state(
            str(user_data.get('user_id') or ''),
            business_id,
            return_to,
            "google_sheets",
        )
        auth_url = GoogleSheetsAuth().get_authorization_url(state)
        return jsonify({"success": True, "auth_url": auth_url, "scope": GOOGLE_SHEETS_SCOPE})
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@google_business_bp.route('/api/google/sheets/oauth/callback', methods=['GET'])
def google_sheets_oauth_callback():
    """Store a Sheets-only credential independently from Google Business."""
    code = request.args.get('code')
    state_payload = _decode_google_oauth_state(request.args.get('state'), "google_sheets")
    return_to = str(state_payload.get("return_to") or DEFAULT_GOOGLE_SHEETS_RETURN_PATH)
    frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')
    if request.args.get('error') or not code:
        return redirect(f"{frontend_url}{_append_google_auth_status(return_to, 'error', 'google_sheets')}")
    business_id = str(state_payload.get("business_id") or "")
    user_id = str(state_payload.get("user_id") or "")
    if not business_id or not user_id:
        return redirect(f"{frontend_url}{_append_google_auth_status(return_to, 'error', 'google_sheets')}")
    db = None
    try:
        auth = GoogleSheetsAuth()
        credentials = auth.get_credentials_from_code(code)
        account_identity = auth.get_account_identity(credentials)
        account_email = str(account_identity.get("email") or "").strip().lower() or None
        account_name = str(account_identity.get("name") or "").strip()
        account_display_name = account_email or account_name or "Google Таблицы"
        encrypted_creds = encrypt_auth_data(json.dumps(auth.credentials_to_dict(credentials)))
        db = DatabaseManager()
        cursor = db.conn.cursor()
        cursor.execute(
            "SELECT id FROM externalbusinessaccounts WHERE business_id = %s AND source = 'google_sheets'",
            (business_id,),
        )
        existing = cursor.fetchone()
        auth_column = _auth_data_column(cursor)
        if existing:
            account_id = str(_row_value(existing, "id", 0) or "")
            cursor.execute(
                "UPDATE externalbusinessaccounts SET " + auth_column + " = %s, display_name = %s, "
                "external_id = %s, is_active = TRUE, last_sync_at = CURRENT_TIMESTAMP, last_error = NULL, updated_at = CURRENT_TIMESTAMP "
                "WHERE id = %s AND business_id = %s AND source = 'google_sheets'",
                (encrypted_creds, account_display_name, account_email, account_id, business_id),
            )
        else:
            account_id = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO externalbusinessaccounts "
                "(id, business_id, source, external_id, display_name, " + auth_column + ", is_active, created_at, updated_at) "
                "VALUES (%s, %s, 'google_sheets', %s, %s, %s, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                (account_id, business_id, account_email, account_display_name, encrypted_creds),
            )
        rebound_count = _sync_google_sheets_agent_auth_refs(cursor, business_id, account_id)
        db.conn.commit()
        return redirect(
            f"{frontend_url}{_append_google_auth_status(return_to, 'success', 'google_sheets')}&rebound={rebound_count}"
        )
    except Exception as error:
        if db:
            db.conn.rollback()
        print(f"Google Sheets OAuth callback failed: {error}")
        return redirect(f"{frontend_url}{_append_google_auth_status(return_to, 'error', 'google_sheets')}")
    finally:
        if db:
            db.close()


@google_business_bp.route('/api/business/<business_id>/google-sheets/status', methods=['GET', 'OPTIONS'])
def google_sheets_status(business_id):
    """Return dedicated Sheets status without conflating it with GBP."""
    if request.method == 'OPTIONS':
        return ('', 204)
    user_data, db = _verify_auth_and_access(business_id)
    if not user_data:
        return jsonify({"error": "Требуется авторизация или нет доступа к бизнесу"}), 401
    try:
        cursor = db.conn.cursor()
        account = _get_google_sheets_account(cursor, business_id)
        legacy_account = _get_legacy_sheets_account(cursor, business_id) if not account else None
        credentials = _credentials_payload(cursor, account) if account else {}
        scopes = credentials.get("scopes") if isinstance(credentials.get("scopes"), list) else []
        scope_values = [str(scope) for scope in scopes]
        token_ready = bool(credentials.get("token") or credentials.get("refresh_token"))
        connected = bool(account and GOOGLE_SHEETS_SCOPE in scope_values and token_ready)
        return jsonify({
            "success": True,
            "connected": connected,
            "needs_auth": not connected,
            "scopes": scope_values,
            "read_check": {
                "status": "credentials_ready" if connected else "not_connected",
                "checked_at": account.get("last_sync_at") if account else None,
                "last_error": account.get("last_error") if account else None,
            },
            "account": {
                "id": account.get("id"),
                "external_id": account.get("external_id"),
                "display_name": account.get("display_name"),
                "last_sync_at": account.get("last_sync_at"),
                "last_error": account.get("last_error"),
            } if account else None,
            "legacy_token": bool(legacy_account),
            "legacy_account_id": legacy_account.get("id") if legacy_account else None,
            "needs_separate_reconnect": bool(legacy_account and not connected),
            "capabilities": {
                "read_rows": connected,
                "append_rows_with_approval": connected,
                "update_cells_with_approval": connected,
            },
            "approval_required_for_writes": True,
        })
    finally:
        db.close()

@google_business_bp.route('/api/business/<business_id>/google/status', methods=['GET', 'OPTIONS'])
def google_status(business_id):
    """Показать статус подключения Google Business Profile для бизнеса."""
    if request.method == 'OPTIONS':
        return ('', 204)

    user_data, db = _verify_auth_and_access(business_id)
    if not user_data:
        return jsonify({"error": "Требуется авторизация или нет доступа к бизнесу"}), 401

    try:
        cursor = db.conn.cursor()
        account = _get_google_account(cursor, business_id)
        if not account:
            return jsonify({
                "success": True,
                "connected": False,
                "needs_auth": True,
                "approval_required_for_writes": True,
            })
        return jsonify({
            "success": True,
            "connected": True,
            "account": {
                "id": account.get("id"),
                "external_id": account.get("external_id"),
                "display_name": account.get("display_name"),
                "last_sync_at": account.get("last_sync_at"),
                "last_error": account.get("last_error"),
            },
            "needs_location_binding": not bool(account.get("external_id")),
            "approval_required_for_writes": True,
        })
    finally:
        db.close()

@google_business_bp.route('/api/business/<business_id>/google/locations', methods=['GET', 'OPTIONS'])
def google_locations(business_id):
    """Получить доступные Google Business Profile локации после OAuth."""
    if request.method == 'OPTIONS':
        return ('', 204)

    user_data, db = _verify_auth_and_access(business_id)
    if not user_data:
        return jsonify({"error": "Требуется авторизация или нет доступа к бизнесу"}), 401

    try:
        cursor = db.conn.cursor()
        account = _get_google_account(cursor, business_id, request.args.get("account_id"))
        if not account:
            return jsonify({"error": "Google аккаунт не найден или не активен"}), 404
        worker = GoogleBusinessSyncWorker()
        try:
            locations = [_public_location(item) for item in worker.list_locations(account)]
        except GoogleBusinessAPIError as error:
            return _google_business_error_response(error)
        return jsonify({"success": True, "locations": locations})
    finally:
        db.close()

@google_business_bp.route('/api/business/<business_id>/google/bind-location', methods=['POST', 'OPTIONS'])
def google_bind_location(business_id):
    """Привязать выбранную GBP локацию к бизнесу LocalOS."""
    if request.method == 'OPTIONS':
        return ('', 204)

    user_data, db = _verify_auth_and_access(business_id)
    if not user_data:
        return jsonify({"error": "Требуется авторизация или нет доступа к бизнесу"}), 401

    try:
        data = request.get_json() or {}
        location_name = str(data.get("location_name") or "").strip()
        display_name = str(data.get("display_name") or data.get("title") or "Google Business Profile").strip()
        account_id = data.get("account_id")
        if not location_name.startswith("accounts/") or "/locations/" not in location_name:
            return jsonify({"error": "location_name должен быть GBP resource name"}), 400

        cursor = db.conn.cursor()
        account = _get_google_account(cursor, business_id, account_id)
        if not account:
            return jsonify({"error": "Google аккаунт не найден или не активен"}), 404
        cursor.execute(
            """
            UPDATE externalbusinessaccounts
            SET external_id = %s,
                display_name = %s,
                updated_at = CURRENT_TIMESTAMP,
                last_error = NULL
            WHERE id = %s AND business_id = %s AND source = 'google_business'
            """,
            (location_name, display_name, account.get("id"), business_id),
        )
        db.conn.commit()
        return jsonify({"success": True, "account_id": account.get("id"), "external_id": location_name})
    finally:
        db.close()

@google_business_bp.route('/api/business/<business_id>/google/sync', methods=['POST', 'OPTIONS'])
def google_sync(business_id):
    """Запустить ручную синхронизацию отзывов/статистики GBP."""
    if request.method == 'OPTIONS':
        return ('', 204)

    user_data, db = _verify_auth_and_access(business_id)
    if not user_data:
        return jsonify({"error": "Требуется авторизация или нет доступа к бизнесу"}), 401

    try:
        cursor = db.conn.cursor()
        account = _get_google_account(cursor, business_id, (request.get_json() or {}).get("account_id"))
        if not account:
            return jsonify({"error": "Google аккаунт не найден или не активен"}), 404
        if not account.get("external_id"):
            return jsonify({"error": "Сначала выберите Google локацию", "code": "location_binding_required"}), 400
        account_id = account.get("id")
    finally:
        db.close()

    worker = GoogleBusinessSyncWorker()
    worker.sync_account(account_id)
    return jsonify({"success": True, "account_id": account_id, "status": "sync_completed"})

@google_business_bp.route('/api/business/<business_id>/google/publish-review-reply', methods=['POST', 'OPTIONS'])
def publish_review_reply(business_id):
    """Опубликовать ответ на отзыв в Google"""
    if request.method == 'OPTIONS':
        return ('', 204)
    
    try:
        # Проверка авторизации и доступа
        user_data, db = _verify_auth_and_access(business_id)
        if not user_data:
            return jsonify({"error": "Требуется авторизация или нет доступа к бизнесу"}), 401
        
        cursor = db.conn.cursor()
        
        data = request.get_json()
        if not data or data.get("approved") is not True:
            db.close()
            return jsonify({
                "error": "Публикация ответа требует ручного подтверждения",
                "code": "manual_approval_required",
                "pending_human": True,
            }), 409
        review_id = data.get('review_id')
        reply_text = data.get('reply_text')
        account_id = data.get('account_id')
        
        if not review_id or not reply_text:
            db.close()
            return jsonify({"error": "review_id и reply_text обязательны"}), 400
        
        # Получаем аккаунт
        account = _get_google_account(cursor, business_id, account_id)
        db.close()
        
        if not account:
            return jsonify({"error": "Google аккаунт не найден или не активен"}), 404
        
        worker = GoogleBusinessSyncWorker()
        success = worker._publish_review_reply(account, review_id, reply_text)
        
        return jsonify({"success": success})
    except Exception as e:
        print(f"❌ Ошибка публикации ответа на отзыв: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@google_business_bp.route('/api/business/<business_id>/google/publish-post', methods=['POST', 'OPTIONS'])
def publish_post(business_id):
    """Опубликовать пост/новость в Google"""
    if request.method == 'OPTIONS':
        return ('', 204)
    
    try:
        # Проверка авторизации и доступа
        user_data, db = _verify_auth_and_access(business_id)
        if not user_data:
            return jsonify({"error": "Требуется авторизация или нет доступа к бизнесу"}), 401
        
        cursor = db.conn.cursor()
        
        data = request.get_json()
        if not data or data.get("approved") is not True:
            db.close()
            return jsonify({
                "error": "Публикация новости требует ручного подтверждения",
                "code": "manual_approval_required",
                "pending_human": True,
            }), 409
        post_data = {
            'topicType': data.get('topic_type', 'STANDARD'),
            'summary': data.get('summary') or data.get('title', ''),
            'callToAction': {
                'actionType': data.get('action_type', 'CALL'),
                'url': data.get('url', '')
            }
        }
        if data.get('media'):
            post_data['media'] = data.get('media')
        
        account_id = data.get('account_id')
        
        # Получаем аккаунт
        account = _get_google_account(cursor, business_id, account_id)
        db.close()
        
        if not account:
            return jsonify({"error": "Google аккаунт не найден или не активен"}), 404
        
        worker = GoogleBusinessSyncWorker()
        post_id = worker._publish_post(account, post_data)
        
        if post_id:
            return jsonify({"success": True, "post_id": post_id})
        else:
            return jsonify({"error": "Не удалось опубликовать пост"}), 500
    except Exception as e:
        print(f"❌ Ошибка публикации поста: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
