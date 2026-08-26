from __future__ import annotations

from flask import Blueprint, jsonify, request

from core.auth_helpers import require_auth_from_request, verify_business_access
from database_manager import DatabaseManager
from services.product_telemetry_service import record_product_event, validate_product_event


product_events_bp = Blueprint("product_events_api", __name__)


@product_events_bp.route("/api/product/events", methods=["POST"])
def create_product_event():
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    payload = request.get_json(silent=True) or {}
    event_name, surface, validation_error = validate_product_event(payload.get("event_name"), payload.get("surface"))
    if validation_error:
        return jsonify({"success": False, "error": validation_error}), 400
    business_id = str(payload.get("business_id") or "").strip()
    if not business_id:
        return jsonify({"success": False, "error": "Укажите бизнес"}), 400
    properties = payload.get("properties")
    if properties is not None and not isinstance(properties, dict):
        return jsonify({"success": False, "error": "Свойства события должны быть объектом"}), 400
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        has_access, owner_id = verify_business_access(cursor, business_id, user_data)
        if not has_access:
            return jsonify({"success": False, "error": "Нет доступа к бизнесу" if owner_id else "Бизнес не найден"}), 403 if owner_id else 404
        event_id = record_product_event(
            cursor,
            event_name=event_name or "",
            surface=surface or "",
            business_id=business_id,
            user_id=str(user_data.get("user_id") or user_data.get("id") or "") or None,
            target=str(payload.get("object_id") or ""),
            properties={
                **(properties or {}),
                "object_type": str(payload.get("object_type") or "")[:100],
            },
            lead_id=str(payload.get("lead_id") or "") or None,
            journey_id=str(payload.get("journey_id") or "") or None,
            action_id=str(payload.get("action_id") or "") or None,
            flow_type=str(payload.get("flow_type") or "") or None,
            entity_type=str(payload.get("entity_type") or "") or None,
            entity_id=str(payload.get("entity_id") or "") or None,
        )
        db.conn.commit()
        return jsonify({"success": True, "event_id": event_id}), 201
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()
