import logging
import sys

from flask import Blueprint, current_app, jsonify, request

from auth_system import logout_session, verify_session
from database_manager import DatabaseManager


logger = logging.getLogger(__name__)
auth_user_bp = Blueprint("auth_user_api", __name__)


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
        is_superadmin = db.is_superadmin(user_id)
        if is_superadmin:
            businesses = db.get_all_businesses()
        elif db.is_network_owner(user_id):
            businesses = db.get_businesses_by_network_owner(user_id)
        else:
            businesses = db.get_businesses_by_owner(user_id)

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
                },
                "businesses": businesses,
            }
        )

    except Exception:
        exc = sys.exc_info()[1]
        logger.warning("User info endpoint failed: %s", type(exc).__name__)
        payload = {"error": "Ошибка получения информации о пользователе"}
        if current_app.debug:
            payload["details"] = str(exc)
        return jsonify(payload), 500


@auth_user_bp.route("/api/auth/logout", methods=["POST"])
def logout():
    """Выход пользователя."""
    try:
        token = _auth_token_from_request()
        if not token:
            return jsonify({"error": "Требуется авторизация"}), 401

        success = logout_session(token)
        if success:
            return jsonify({"success": True, "message": "Выход выполнен успешно"})
        return jsonify({"error": "Ошибка выхода"}), 500

    except Exception:
        exc = sys.exc_info()[1]
        print(f"❌ Ошибка выхода: {exc}")
        return jsonify({"error": str(exc)}), 500


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
        exc = sys.exc_info()[1]
        print(f"❌ Ошибка обновления профиля: {exc}")
        return jsonify({"error": str(exc)}), 500
