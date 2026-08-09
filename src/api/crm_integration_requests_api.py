from __future__ import annotations

import re
import uuid

from flask import Blueprint, jsonify, request

from core.auth_helpers import require_auth_from_request, verify_business_access
from database_manager import DatabaseManager


crm_integration_requests_bp = Blueprint("crm_integration_requests_api", __name__)


def _normalize_crm_name(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def _authorized(business_id: str):
    user_data = require_auth_from_request()
    if not user_data:
        return None, (jsonify({"success": False, "error": "Требуется авторизация"}), 401)
    db = DatabaseManager()
    cursor = db.conn.cursor()
    has_access, owner_id = verify_business_access(cursor, business_id, user_data)
    if not has_access:
        db.close()
        return None, (jsonify({"success": False, "error": "Нет доступа к бизнесу" if owner_id else "Бизнес не найден"}), 403 if owner_id else 404)
    return (user_data, db, cursor), None


def _serialize(row):
    return dict(row) if hasattr(row, "keys") else row


@crm_integration_requests_bp.route("/api/business/<business_id>/crm-integration-requests", methods=["GET"])
def list_crm_integration_requests(business_id: str):
    auth, error = _authorized(business_id)
    if error:
        return error
    _, db, cursor = auth
    try:
        cursor.execute(
            """
            SELECT id, business_id, requested_by, crm_name, note, status, created_at, updated_at
            FROM crm_integration_requests WHERE business_id = %s
            ORDER BY created_at DESC LIMIT 100
            """,
            (business_id,),
        )
        return jsonify({"success": True, "requests": [_serialize(row) for row in cursor.fetchall() or []]})
    finally:
        db.close()


@crm_integration_requests_bp.route("/api/business/<business_id>/crm-integration-requests", methods=["POST"])
def create_crm_integration_request(business_id: str):
    auth, error = _authorized(business_id)
    if error:
        return error
    user_data, db, cursor = auth
    try:
        payload = request.get_json(silent=True) or {}
        crm_name = re.sub(r"\s+", " ", str(payload.get("crm_name") or "").strip())
        normalized = _normalize_crm_name(crm_name)
        note = str(payload.get("note") or "").strip()[:2000]
        if not normalized or len(crm_name) > 160:
            return jsonify({"success": False, "error": "Укажите название CRM до 160 символов"}), 400
        cursor.execute(
            """
            SELECT id, business_id, requested_by, crm_name, note, status, created_at, updated_at
            FROM crm_integration_requests
            WHERE business_id = %s AND crm_name_normalized = %s
              AND status IN ('open', 'reviewing', 'planned')
            ORDER BY created_at DESC LIMIT 1
            """,
            (business_id, normalized),
        )
        existing = cursor.fetchone()
        if existing:
            return jsonify({"success": True, "deduplicated": True, "request": _serialize(existing)})
        request_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO crm_integration_requests
                (id, business_id, requested_by, crm_name, crm_name_normalized, note)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (business_id, crm_name_normalized)
                WHERE status IN ('open', 'reviewing', 'planned') DO NOTHING
            RETURNING id, business_id, requested_by, crm_name, note, status, created_at, updated_at
            """,
            (request_id, business_id, str(user_data.get("user_id") or user_data.get("id") or "") or None, crm_name, normalized, note),
        )
        created = cursor.fetchone()
        if not created:
            cursor.execute(
                """
                SELECT id, business_id, requested_by, crm_name, note, status, created_at, updated_at
                FROM crm_integration_requests
                WHERE business_id = %s AND crm_name_normalized = %s
                  AND status IN ('open', 'reviewing', 'planned')
                ORDER BY created_at DESC LIMIT 1
                """,
                (business_id, normalized),
            )
            existing = cursor.fetchone()
            db.conn.commit()
            return jsonify({"success": True, "deduplicated": True, "request": _serialize(existing)})
        db.conn.commit()
        return jsonify({"success": True, "deduplicated": False, "request": _serialize(created)}), 201
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()
