from __future__ import annotations

import sys

from flask import Blueprint, jsonify, request

from core.auth_helpers import require_auth_from_request, verify_business_access
from database_manager import DatabaseManager
from services.bot_feature_requests import save_bot_feature_request


dashboard_feedback_bp = Blueprint("dashboard_feedback_api", __name__, url_prefix="/api/dashboard-feedback")


@dashboard_feedback_bp.route("", methods=["POST"])
def create_dashboard_feedback():
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401

    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"success": False, "error": "Некорректный JSON"}), 400

    message = str(payload.get("message") or "").strip()
    if not message:
        return jsonify({"success": False, "error": "message is required"}), 400

    business_id = str(payload.get("business_id") or "").strip() or None
    area = str(payload.get("area") or payload.get("section") or "dashboard").strip() or "dashboard"
    page_path = str(payload.get("page_path") or "").strip()
    current_business_name = str(payload.get("business_name") or "").strip()

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        if business_id:
            has_access, owner_id = verify_business_access(cursor, business_id, user_data)
            if not has_access:
                status_code = 403 if owner_id else 404
                message_text = "Нет доступа" if owner_id else "Бизнес не найден"
                return jsonify({"success": False, "error": message_text}), status_code

        user_id = str(user_data.get("user_id") or user_data.get("id") or "").strip() or None
        telegram_id = str(user_data.get("telegram_id") or "").strip()
        user_name = str(user_data.get("name") or "").strip()
        user_email = str(user_data.get("email") or "").strip()

        saved = save_bot_feature_request(
            db.conn,
            telegram_id=telegram_id,
            user_id=user_id,
            business_id=business_id,
            source="dashboard_beta",
            category="bug",
            request_text=message,
            metadata={
                "area": area,
                "page_path": page_path,
                "business_name": current_business_name,
                "user_name": user_name,
                "user_email": user_email,
                "user_agent": str(request.headers.get("User-Agent") or "").strip(),
            },
        )
        return jsonify({"success": True, "request_id": saved.get("id")})
    except Exception:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
    finally:
        db.close()
