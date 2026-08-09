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


def _superadmin():
    user_data = require_auth_from_request()
    if not user_data:
        return None, (jsonify({"success": False, "error": "Требуется авторизация"}), 401)
    if not bool(user_data.get("is_superadmin")):
        return None, (jsonify({"success": False, "error": "Раздел доступен только суперадмину"}), 403)
    return user_data, None


def _can_manage_network(cursor, network_id: str, user_data: dict) -> bool:
    if bool(user_data.get("is_superadmin")):
        return True
    user_id = str(user_data.get("user_id") or user_data.get("id") or "")
    if not user_id:
        return False
    cursor.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM networks n
            LEFT JOIN network_members nm
              ON nm.network_id = n.id
             AND nm.user_id = %s
             AND nm.status = 'active'
            WHERE n.id = %s
              AND (n.owner_id = %s OR nm.user_id IS NOT NULL)
        ) AS allowed
        """,
        (user_id, network_id, user_id),
    )
    row = cursor.fetchone()
    if hasattr(row, "get"):
        return bool(row.get("allowed"))
    return bool(row[0]) if row else False


@crm_integration_requests_bp.route("/api/business/<business_id>/crm-integration-requests", methods=["GET"])
def list_crm_integration_requests(business_id: str):
    auth, error = _authorized(business_id)
    if error:
        return error
    _, db, cursor = auth
    try:
        cursor.execute(
            """
            SELECT id, business_id, requested_by, crm_name, crm_url, contact, scope_type,
                   scope_id, note, status, created_at, updated_at
            FROM crm_integration_requests WHERE business_id = %s
            ORDER BY CASE status
                       WHEN 'open' THEN 1 WHEN 'reviewing' THEN 2 WHEN 'planned' THEN 3
                       WHEN 'connected' THEN 4 ELSE 5 END,
                     created_at DESC
            LIMIT 100
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
        crm_url = str(payload.get("crm_url") or "").strip()[:500]
        contact = str(payload.get("contact") or "").strip()[:300]
        scope_type = str(payload.get("scope_type") or "business").strip().lower()
        scope_id = str(payload.get("scope_id") or business_id).strip()
        if not normalized or len(crm_name) > 160:
            return jsonify({"success": False, "error": "Укажите название CRM до 160 символов"}), 400
        if scope_type not in {"business", "network"}:
            return jsonify({"success": False, "error": "Некорректный масштаб подключения"}), 400
        if scope_type == "business":
            scope_id = business_id
        else:
            cursor.execute("SELECT network_id FROM businesses WHERE id = %s", (business_id,))
            business_row = cursor.fetchone()
            business_network_id = str((business_row or {}).get("network_id") or "") if hasattr(business_row, "get") else ""
            if not business_network_id or business_network_id != scope_id:
                return jsonify({"success": False, "error": "Точка не относится к выбранной сети"}), 403
            if not _can_manage_network(cursor, scope_id, user_data):
                return jsonify({"success": False, "error": "Нет доступа к управлению сетью"}), 403
        cursor.execute(
            """
            SELECT id, business_id, requested_by, crm_name, crm_url, contact, scope_type,
                   scope_id, note, status, created_at, updated_at
            FROM crm_integration_requests
            WHERE business_id = %s AND crm_name_normalized = %s
              AND status IN ('open', 'reviewing', 'planned', 'connected')
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
                (id, business_id, requested_by, crm_name, crm_name_normalized, crm_url,
                 contact, scope_type, scope_id, note)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (business_id, crm_name_normalized)
                WHERE status IN ('open', 'reviewing', 'planned', 'connected') DO NOTHING
            RETURNING id, business_id, requested_by, crm_name, crm_url, contact, scope_type,
                      scope_id, note, status, created_at, updated_at
            """,
            (
                request_id,
                business_id,
                str(user_data.get("user_id") or user_data.get("id") or "") or None,
                crm_name,
                normalized,
                crm_url,
                contact,
                scope_type,
                scope_id,
                note,
            ),
        )
        created = cursor.fetchone()
        if not created:
            cursor.execute(
                """
                SELECT id, business_id, requested_by, crm_name, crm_url, contact, scope_type,
                       scope_id, note, status, created_at, updated_at
                FROM crm_integration_requests
                WHERE business_id = %s AND crm_name_normalized = %s
                  AND status IN ('open', 'reviewing', 'planned', 'connected')
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


@crm_integration_requests_bp.route("/api/admin/crm-integration-requests", methods=["GET"])
def admin_list_crm_integration_requests():
    _, error = _superadmin()
    if error:
        return error
    status = str(request.args.get("status") or "").strip().lower()
    if status and status not in {"open", "reviewing", "planned", "connected", "closed", "declined"}:
        return jsonify({"success": False, "error": "Некорректный статус"}), 400
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        cursor.execute(
            """
            SELECT r.id, r.business_id, b.name AS business_name, r.requested_by,
                   r.crm_name, r.crm_url, r.contact, r.scope_type, r.scope_id,
                   r.note, r.status, r.created_at, r.updated_at,
                   COUNT(*) OVER (PARTITION BY r.crm_name_normalized) AS demand_count
            FROM crm_integration_requests r
            JOIN businesses b ON b.id = r.business_id
            WHERE (%s = '' OR r.status = %s)
            ORDER BY CASE r.status
                       WHEN 'open' THEN 1 WHEN 'reviewing' THEN 2 WHEN 'planned' THEN 3
                       WHEN 'connected' THEN 4 ELSE 5 END,
                     demand_count DESC, r.created_at DESC
            LIMIT 500
            """,
            (status, status),
        )
        return jsonify({"success": True, "requests": [_serialize(row) for row in cursor.fetchall() or []]})
    finally:
        db.close()


@crm_integration_requests_bp.route("/api/admin/crm-integration-requests/<request_id>", methods=["PATCH"])
def admin_update_crm_integration_request(request_id: str):
    _, error = _superadmin()
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    status = str(payload.get("status") or "").strip().lower()
    allowed = {"open", "reviewing", "planned", "connected", "closed", "declined"}
    if status not in allowed:
        return jsonify({"success": False, "error": "Некорректный статус"}), 400
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE crm_integration_requests
            SET status = %s, updated_at = NOW()
            WHERE id = %s
            RETURNING id, business_id, requested_by, crm_name, crm_url, contact,
                      scope_type, scope_id, note, status, created_at, updated_at
            """,
            (status, request_id),
        )
        updated = cursor.fetchone()
        if not updated:
            db.conn.rollback()
            return jsonify({"success": False, "error": "Запрос не найден"}), 404
        db.conn.commit()
        return jsonify({"success": True, "request": _serialize(updated)})
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()
