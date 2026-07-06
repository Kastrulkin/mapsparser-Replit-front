from __future__ import annotations

import hashlib
import hmac
import os
from typing import Any

from flask import Blueprint, jsonify, request

from auth_system import verify_session
from core.helpers import get_business_owner_id
from database_manager import DatabaseManager
from services.telegram_opportunity_radar import (
    ingest_opportunity,
    list_opportunities,
    list_sources,
    notify_owner_for_opportunity,
    update_status,
    upsert_source,
)


telegram_opportunity_radar_bp = Blueprint(
    "telegram_opportunity_radar_api",
    __name__,
    url_prefix="/api/telegram-opportunity-radar",
)


def _verify_openclaw_signature(raw_body: bytes) -> bool:
    secret = str(os.getenv("OPENCLAW_WEBHOOK_SECRET") or "").strip()
    if not secret:
        return False
    provided = str(
        request.headers.get("X-OpenClaw-Signature")
        or request.headers.get("X-Openclaw-Signature")
        or ""
    ).strip()
    if provided.startswith("sha256="):
        provided = provided.split("=", 1)[1]
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, provided)


def _require_business_access() -> tuple[DatabaseManager | None, Any | None, dict[str, Any] | None, str | None, Any | None]:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None, None, None, None, (jsonify({"error": "Требуется авторизация"}), 401)
    user_data = verify_session(auth_header.split(" ", 1)[1])
    if not user_data:
        return None, None, None, None, (jsonify({"error": "Недействительный токен"}), 401)

    payload = request.get_json(silent=True) or {}
    business_id = str(payload.get("business_id") or request.args.get("business_id") or "").strip()
    if not business_id:
        return None, None, user_data, None, (jsonify({"error": "business_id обязателен"}), 400)

    db = DatabaseManager()
    cursor = db.conn.cursor()
    owner_id = get_business_owner_id(cursor, business_id, include_active_check=True)
    if not owner_id:
        db.close()
        return None, None, user_data, business_id, (jsonify({"error": "Бизнес не найден"}), 404)
    if owner_id != user_data["user_id"] and not db.is_superadmin(user_data["user_id"]):
        db.close()
        return None, None, user_data, business_id, (jsonify({"error": "Нет доступа"}), 403)
    return db, cursor, user_data, business_id, None


@telegram_opportunity_radar_bp.route("/ingest", methods=["POST"])
def ingest_from_openclaw():
    raw_body = request.get_data(cache=True)
    if not _verify_openclaw_signature(raw_body):
        return jsonify({"success": False, "error": "invalid_openclaw_signature"}), 401
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"success": False, "error": "json body must be object"}), 400

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        result = ingest_opportunity(cursor, payload)
        alert_result = None
        if result.get("created") and result.get("opportunity"):
            alert_result = notify_owner_for_opportunity(cursor, result["opportunity"])
        db.conn.commit()
        return jsonify({"success": True, **result, "alert": alert_result})
    except ValueError as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 500
    finally:
        db.close()


@telegram_opportunity_radar_bp.route("/sources", methods=["GET", "POST"])
def sources():
    db, cursor, user_data, business_id, error = _require_business_access()
    if error:
        return error
    assert db is not None and cursor is not None and user_data is not None and business_id is not None
    try:
        if request.method == "GET":
            return jsonify({"success": True, "sources": list_sources(cursor, business_id)})
        payload = request.get_json(silent=True) or {}
        source = upsert_source(cursor, {**payload, "business_id": business_id, "user_id": user_data["user_id"]})
        db.conn.commit()
        return jsonify({"success": True, "source": source})
    except Exception as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    finally:
        db.close()


@telegram_opportunity_radar_bp.route("/opportunities", methods=["GET"])
def opportunities():
    db, cursor, _user_data, business_id, error = _require_business_access()
    if error:
        return error
    assert db is not None and cursor is not None and business_id is not None
    try:
        status = str(request.args.get("status") or "").strip() or None
        limit = int(request.args.get("limit") or 50)
        return jsonify({"success": True, "opportunities": list_opportunities(cursor, business_id, status=status, limit=limit)})
    finally:
        db.close()


@telegram_opportunity_radar_bp.route("/opportunities/<opportunity_id>/status", methods=["POST"])
def set_opportunity_status(opportunity_id: str):
    db, cursor, user_data, business_id, error = _require_business_access()
    if error:
        return error
    assert db is not None and cursor is not None and user_data is not None and business_id is not None
    payload = request.get_json(silent=True) or {}
    try:
        opportunity = update_status(
            cursor,
            opportunity_id,
            business_id,
            str(payload.get("status") or "").strip(),
            user_id=user_data["user_id"],
            note=str(payload.get("note") or "").strip() or None,
        )
        db.conn.commit()
        return jsonify({"success": True, "opportunity": opportunity})
    except LookupError as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    except ValueError as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 500
    finally:
        db.close()
