from flask import Blueprint, jsonify

from core.auth_helpers import require_auth_from_request, verify_business_access
from database_manager import DatabaseManager
from services.growth_overview_service import load_growth_overview


growth_overview_bp = Blueprint("growth_overview_api", __name__)


@growth_overview_bp.route("/api/business/<business_id>/growth-overview", methods=["GET"])
def get_growth_overview(business_id: str):
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        has_access, owner_id = verify_business_access(cursor, business_id, user_data)
    finally:
        db.close()
    if not has_access:
        status = 403 if owner_id else 404
        message = "Нет доступа к бизнесу" if owner_id else "Бизнес не найден"
        return jsonify({"success": False, "error": message}), status

    try:
        overview = load_growth_overview(business_id)
        return jsonify({"success": True, **overview})
    except ValueError as error:
        return jsonify({"success": False, "error": str(error)}), 404
    except Exception:
        return jsonify({"success": False, "error": "Не удалось собрать прогресс бизнеса"}), 500
