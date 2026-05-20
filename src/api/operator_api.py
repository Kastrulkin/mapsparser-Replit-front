from __future__ import annotations

import sys

from flask import Blueprint, jsonify, request

from core.auth_helpers import require_auth_from_request, verify_business_access
from database_manager import DatabaseManager
from services.operator_consent_policy import list_consent_policies, upsert_consent_policy
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


@operator_bp.route("/consent-policy", methods=["GET"])
def operator_consent_policy_list():
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

        policies = list_consent_policies(cursor, business_id)
        return jsonify({"success": True, "policies": policies})
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
    finally:
        db.close()


@operator_bp.route("/consent-policy/<action_key>", methods=["PUT"])
def operator_consent_policy_update(action_key: str):
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401

    payload = request.get_json(silent=True) or {}
    business_id = str(payload.get("business_id") or "").strip()
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
        policy, errors = upsert_consent_policy(cursor, business_id, action_key, user_id, payload)
        if errors or policy is None:
            return jsonify({"success": False, "error": "invalid_consent_policy", "details": errors}), 400
        return jsonify({"success": True, "policy": policy})
    except Exception:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
    finally:
        db.close()
