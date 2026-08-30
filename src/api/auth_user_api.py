import logging
import os
import uuid

from flask import Blueprint, current_app, g, jsonify, request

from auth_system import logout_session, verify_session
from core.browser_session import browser_cookie_auth_enabled, clear_browser_session
from database_manager import DatabaseManager


logger = logging.getLogger(__name__)
auth_user_bp = Blueprint("auth_user_api", __name__)


def _internal_error(message):
    request_id = str(getattr(g, "request_id", "") or request.headers.get("X-Request-ID") or uuid.uuid4())
    logger.exception("Auth API request failed request_id=%s", request_id)
    return jsonify({
        "code": "internal_error",
        "message": message,
        "request_id": request_id,
    }), 500


def _safe_get(data, key, default=None):
    if isinstance(data, dict):
        return data.get(key, default)
    if hasattr(data, "keys") and key in data.keys():
        return data[key]
    return default


def _auth_token_from_request():
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    return auth_header.split(" ")[1]


def _user_id_from_session(user_data):
    if isinstance(user_data, dict):
        return user_data.get("user_id") or user_data.get("id")
    if hasattr(user_data, "keys"):
        if "user_id" in user_data.keys():
            return user_data["user_id"]
        if "id" in user_data.keys():
            return user_data["id"]
    return None


def _filter_demo_businesses(businesses, scope_business_id):
    normalized_scope = str(scope_business_id or "").strip()
    if not normalized_scope:
        return []
    return [
        business
        for business in businesses
        if str(_safe_get(business, "id") or "") == normalized_scope
        or str(_safe_get(business, "network_id") or "") == normalized_scope
    ]


def _web_tracking_available_for_business(business_id):
    enabled = os.getenv("WEB_TRACKING_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return False
    configured = {
        item.strip()
        for item in os.getenv("WEB_TRACKING_BUSINESS_IDS", "").split(",")
        if item.strip()
    }
    return not configured or str(business_id or "") in configured


def _creator_promotion_available_for_business(business_id):
    enabled = os.getenv("PROMOTION_HUB_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return False
    configured = {
        item.strip()
        for item in os.getenv("INFLUENCER_BUSINESS_IDS", "").split(",")
        if item.strip()
    }
    return not configured or str(business_id or "") in configured


def _attach_business_capabilities(businesses):
    result = []
    for business in businesses:
        business_payload = dict(business)
        business_payload["web_tracking_available"] = _web_tracking_available_for_business(
            _safe_get(business, "id")
        )
        business_payload["creator_promotion_available"] = _creator_promotion_available_for_business(
            _safe_get(business, "id")
        )
        result.append(business_payload)
    return result


@auth_user_bp.route("/api/auth/me", methods=["GET"])
def get_user_info():
    """Получить информацию о текущем пользователе."""
    try:
        token = _auth_token_from_request()
        if not token:
            return jsonify({"error": "Требуется авторизация"}), 401

        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        if user_data.get("is_active") is False:
            return jsonify({"error": "account_blocked", "message": "user is blocked"}), 403

        db = DatabaseManager()
        user_id = _user_id_from_session(user_data)
        if not user_id:
            db.close()
            print(f"❌ Ошибка: не удалось определить user_id из user_data: {user_data}")
            return jsonify({"error": "Не удалось определить ID пользователя"}), 500

        print(f"🔍 DEBUG get_user_info: user_id = {user_id}")
        session_kind = str(_safe_get(user_data, "session_kind", "standard") or "standard")
        is_superadmin = db.is_superadmin(user_id) and session_kind != "demo"
        if is_superadmin:
            businesses = db.get_all_businesses()
        else:
            businesses = db.get_businesses_for_user_access(user_id)

        scope_business_id = _safe_get(user_data, "scope_business_id")
        if session_kind == "demo":
            businesses = _filter_demo_businesses(businesses, scope_business_id)

        businesses = _attach_business_capabilities(businesses)

        if not is_superadmin and len(businesses) == 0:
            db.close()
            return jsonify({"error": "Все ваши бизнесы заблокированы. Обратитесь к администратору."}), 403

        db.close()
        return jsonify(
            {
                "success": True,
                "user": {
                    "id": user_id,
                    "email": _safe_get(user_data, "email"),
                    "name": _safe_get(user_data, "name"),
                    "phone": _safe_get(user_data, "phone"),
                    "is_superadmin": is_superadmin,
                    "session_kind": session_kind,
                    "demo_mode": session_kind == "demo",
                    "demo_scope_business_id": scope_business_id,
                    "demo_room_slug": (
                        current_app.config.get("PUBLIC_DEMO_ROOM_SLUG")
                        or os.getenv("PUBLIC_DEMO_ROOM_SLUG", "")
                    ) if session_kind == "demo" else "",
                },
                "businesses": businesses,
            }
        )

    except Exception:
        return _internal_error("Не удалось получить информацию о пользователе")


@auth_user_bp.route("/api/auth/logout", methods=["POST"])
def logout():
    """Выход пользователя."""
    try:
        token = _auth_token_from_request()
        if not token:
            return jsonify({"error": "Требуется авторизация"}), 401

        success = logout_session(token)
        if success:
            response = jsonify({"success": True, "message": "Выход выполнен успешно"})
            if browser_cookie_auth_enabled():
                clear_browser_session(response)
            return response
        return jsonify({"error": "Ошибка выхода"}), 500

    except Exception:
        return _internal_error("Не удалось завершить сессию")


@auth_user_bp.route("/api/users/profile", methods=["PUT"])
def update_user_profile():
    """Обновить профиль пользователя."""
    try:
        token = _auth_token_from_request()
        if not token:
            return jsonify({"error": "Требуется авторизация"}), 401

        user = verify_session(token)
        if not user:
            return jsonify({"error": "Неверный токен"}), 401

        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({"error": "Invalid JSON"}), 400

        updates = {}
        if "name" in data:
            updates["name"] = data["name"]
        if "phone" in data:
            updates["phone"] = data["phone"]

        if not updates:
            return jsonify({"error": "Нет данных для обновления"}), 400

        db = DatabaseManager()
        cursor = db.conn.cursor()
        set_clause = ", ".join([f"{key} = %s" for key in updates.keys()])
        values = list(updates.values()) + [user["user_id"]]

        cursor.execute(f"UPDATE Users SET {set_clause} WHERE id = %s", values)
        db.conn.commit()
        db.close()

        updated_user = {**user, **updates}
        return jsonify({"success": True, "user": updated_user})

    except Exception:
        return _internal_error("Не удалось обновить профиль")
