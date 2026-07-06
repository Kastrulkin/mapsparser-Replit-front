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
    collect_keywords_from_sources,
    ingest_opportunity,
    list_opportunities,
    list_sources,
    normalize_keywords,
    notify_owner_for_opportunity,
    update_status,
    update_business_keywords,
    upsert_source,
)


LOCALOS_PLATFORM_RADAR_ALIASES = {"__localos__", "localos", "локалос"}
LOCALOS_PLATFORM_RADAR_BUSINESS_ID = "localos-platform-telegram-radar"


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


def _is_localos_platform_alias(value: str | None) -> bool:
    return str(value or "").strip().lower() in LOCALOS_PLATFORM_RADAR_ALIASES


def _ensure_localos_platform_business(cursor: Any, owner_id: str | None = None) -> str:
    cursor.execute("SELECT id FROM businesses WHERE id = %s LIMIT 1", (LOCALOS_PLATFORM_RADAR_BUSINESS_ID,))
    row = cursor.fetchone()
    if row:
        if hasattr(row, "get"):
            return str(row.get("id") or LOCALOS_PLATFORM_RADAR_BUSINESS_ID)
        return str(row[0] or LOCALOS_PLATFORM_RADAR_BUSINESS_ID)

    platform_owner_id = str(owner_id or os.getenv("LOCALOS_PLATFORM_OWNER_ID") or "").strip()
    if not platform_owner_id:
        cursor.execute(
            """
            SELECT id
            FROM users
            WHERE is_superadmin = TRUE
            ORDER BY created_at ASC NULLS LAST
            LIMIT 1
            """
        )
        owner_row = cursor.fetchone()
        if hasattr(owner_row, "get"):
            platform_owner_id = str(owner_row.get("id") or "").strip()
        elif owner_row:
            platform_owner_id = str(owner_row[0] or "").strip()
    if not platform_owner_id:
        raise ValueError("Не найден superadmin для системного бизнеса ЛокалОС")

    cursor.execute(
        """
        INSERT INTO businesses (
            id, owner_id, name, business_type, description,
            is_active, created_at, updated_at
        )
        VALUES (%s, %s, 'ЛокалОС', 'platform', 'System business for LocalOS Telegram radar', TRUE, NOW(), NOW())
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            updated_at = NOW()
        """,
        (LOCALOS_PLATFORM_RADAR_BUSINESS_ID, platform_owner_id),
    )
    return LOCALOS_PLATFORM_RADAR_BUSINESS_ID


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
    if _is_localos_platform_alias(business_id):
        if not db.is_superadmin(user_data["user_id"]):
            db.close()
            return None, None, user_data, business_id, (jsonify({"error": "Нет доступа"}), 403)
        try:
            business_id = _ensure_localos_platform_business(cursor, user_data["user_id"])
            db.conn.commit()
        except Exception as exc:
            db.conn.rollback()
            db.close()
            return None, None, user_data, business_id, (jsonify({"error": str(exc)}), 500)

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
        if _is_localos_platform_alias(payload.get("business_id")):
            payload = {**payload, "business_id": _ensure_localos_platform_business(cursor)}
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


@telegram_opportunity_radar_bp.route("/sources/keywords", methods=["PATCH"])
def source_keywords():
    db, cursor, _user_data, business_id, error = _require_business_access()
    if error:
        return error
    assert db is not None and cursor is not None and business_id is not None
    payload = request.get_json(silent=True) or {}
    try:
        keywords = normalize_keywords(payload.get("keywords"))
        result = update_business_keywords(cursor, business_id, keywords)
        db.conn.commit()
        sources = list_sources(cursor, business_id)
        return jsonify({
            "success": True,
            **result,
            "keywords": collect_keywords_from_sources(sources),
            "sources": sources,
        })
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
