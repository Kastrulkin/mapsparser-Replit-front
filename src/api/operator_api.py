from __future__ import annotations

import sys

from flask import Blueprint, jsonify, request

from core.auth_helpers import require_auth_from_request, verify_business_access
from database_manager import DatabaseManager
from services.operator_attention import build_attention_brief


operator_bp = Blueprint("operator_api", __name__, url_prefix="/api/operator")


@operator_bp.route("/attention-brief", methods=["GET"])
def operator_attention_brief():
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401

    business_id = str(request.args.get("business_id") or "").strip()
    if not business_id:
        return jsonify({"success": False, "error": "business_id обязателен"}), 400

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        has_access, owner_id = verify_business_access(cursor, business_id, user_data)
        if not has_access:
            status_code = 403 if owner_id else 404
            message = "Нет доступа" if owner_id else "Бизнес не найден"
            return jsonify({"success": False, "error": message}), status_code

        user_id = str(user_data.get("user_id") or user_data.get("id") or "")
        brief = build_attention_brief(cursor, business_id, user_id)
        return jsonify({"success": True, "brief": brief})
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
    finally:
        db.close()
