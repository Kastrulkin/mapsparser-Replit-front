from flask import Blueprint, jsonify, request

from core.auth_helpers import require_auth_from_request, verify_business_access
from database_manager import DatabaseManager
from services.knowledge_graph_service import (
    knowledge_layer_enabled,
    list_content_foundations,
    serialize_for_json,
)


knowledge_bp = Blueprint("knowledge", __name__)


@knowledge_bp.get("/api/business/<business_id>/knowledge/content-foundations")
def content_foundations(business_id):
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    if not knowledge_layer_enabled():
        return jsonify({"success": True, "enabled": False, "foundations": []})

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        has_access, owner_id = verify_business_access(cursor, business_id, user_data)
        if not has_access:
            status = 403 if owner_id else 404
            return jsonify({"success": False, "error": "Нет доступа к бизнесу"}), status
        cursor.execute("SELECT COALESCE(NULLIF(industry, ''), 'beauty') AS industry FROM businesses WHERE id = %s", (business_id,))
        row = cursor.fetchone()
        industry_value = row.get("industry") if hasattr(row, "get") else (row[0] if row else "beauty")
        industry = str(industry_value or "beauty")
        payload = list_content_foundations(
            db.conn,
            industry=industry or "beauty",
            limit_per_type=int(request.args.get("limit") or 3),
        )
        return jsonify({"success": True, "enabled": True, **serialize_for_json(payload)})
    finally:
        db.close()
