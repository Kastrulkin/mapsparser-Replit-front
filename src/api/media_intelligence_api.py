from __future__ import annotations

import sys

from flask import Blueprint, jsonify, request

from core.auth_helpers import require_auth_from_request, verify_business_access
from database_manager import DatabaseManager
from services.ai_runtime import (
    VISION_CAPABILITY,
    analyze_photo_runtime,
    list_capability_settings,
    set_capability_enabled,
)
from services.media_intelligence import (
    build_photo_coverage,
    list_photo_assets,
    load_business,
    recommend_media_for_post,
    upsert_photo_asset,
)


media_intelligence_bp = Blueprint("media_intelligence", __name__, url_prefix="/api/media-intelligence")


def _user_id(user_data: dict) -> str:
    return str(user_data.get("user_id") or user_data.get("id") or "").strip()


def _require_business(cursor, business_id: str, user_data: dict):
    if not business_id:
        return False, (jsonify({"success": False, "error": "business_id обязателен"}), 400)
    has_access, _owner_id = verify_business_access(cursor, business_id, user_data)
    if not has_access:
        return False, (jsonify({"success": False, "error": "Нет доступа к бизнесу"}), 403)
    return True, None


@media_intelligence_bp.route("/settings", methods=["GET"])
def media_settings_get():
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    business_id = str(request.args.get("business_id") or "").strip()
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        ok, error_response = _require_business(cursor, business_id, user_data)
        if not ok:
            return error_response
        settings = list_capability_settings(cursor, business_id)
        return jsonify(
            {
                "success": True,
                "settings": settings,
                "photo_intelligence": {
                    "enabled": bool(settings.get(VISION_CAPABILITY, {}).get("enabled")),
                    "estimated_credits_per_photo": 2,
                    "copy": "LocalOS сможет выбирать лучшие фото, подсказывать что снять и готовить визуал для каналов.",
                },
            }
        )
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
    finally:
        db.close()


@media_intelligence_bp.route("/settings", methods=["POST"])
def media_settings_post():
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    payload = request.get_json(silent=True) or {}
    business_id = str(payload.get("business_id") or "").strip()
    enabled = bool(payload.get("vision_enabled"))
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        ok, error_response = _require_business(cursor, business_id, user_data)
        if not ok:
            return error_response
        setting = set_capability_enabled(
            cursor,
            business_id=business_id,
            user_id=_user_id(user_data),
            capability=VISION_CAPABILITY,
            enabled=enabled,
            metadata={"source": "profile_settings", "consent": bool(enabled)},
        )
        db.conn.commit()
        return jsonify({"success": True, "setting": setting})
    except Exception:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
    finally:
        db.close()


@media_intelligence_bp.route("/photos", methods=["GET"])
def media_photos_list():
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    business_id = str(request.args.get("business_id") or "").strip()
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        ok, error_response = _require_business(cursor, business_id, user_data)
        if not ok:
            return error_response
        return jsonify({"success": True, "photos": list_photo_assets(cursor, business_id), "coverage": build_photo_coverage(cursor, business_id)})
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
    finally:
        db.close()


@media_intelligence_bp.route("/photos", methods=["POST"])
def media_photos_create():
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    payload = request.get_json(silent=True) or {}
    business_id = str(payload.get("business_id") or "").strip()
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        ok, error_response = _require_business(cursor, business_id, user_data)
        if not ok:
            return error_response
        photo = upsert_photo_asset(
            cursor,
            business_id=business_id,
            user_id=_user_id(user_data),
            original_url=str(payload.get("original_url") or "").strip(),
            source=str(payload.get("source") or "manual"),
            metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        )
        db.conn.commit()
        return jsonify({"success": True, "photo": photo})
    except ValueError:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 400
    except Exception:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
    finally:
        db.close()


@media_intelligence_bp.route("/photos/<asset_id>/analyze", methods=["POST"])
def media_photo_analyze(asset_id: str):
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    payload = request.get_json(silent=True) or {}
    business_id = str(payload.get("business_id") or "").strip()
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        ok, error_response = _require_business(cursor, business_id, user_data)
        if not ok:
            return error_response
        business = load_business(cursor, business_id)
        context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
        context = {**context, "business_type": business.get("business_type") or business.get("industry") or business.get("name")}
        result = analyze_photo_runtime(
            cursor,
            business_id=business_id,
            user_id=_user_id(user_data),
            asset_id=str(asset_id or "").strip(),
            image_base64=str(payload.get("image_base64") or "").strip(),
            image_url=str(payload.get("image_url") or "").strip(),
            context=context,
        )
        if result.get("success"):
            db.conn.commit()
            return jsonify(result)
        db.conn.rollback()
        status_code = 402 if result.get("status") == "insufficient_credits" else 400
        if result.get("status") == "vision_disabled":
            status_code = 409
        return jsonify(result), status_code
    except Exception:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
    finally:
        db.close()


@media_intelligence_bp.route("/coverage", methods=["GET"])
def media_coverage_get():
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    business_id = str(request.args.get("business_id") or "").strip()
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        ok, error_response = _require_business(cursor, business_id, user_data)
        if not ok:
            return error_response
        return jsonify({"success": True, "coverage": build_photo_coverage(cursor, business_id)})
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
    finally:
        db.close()


@media_intelligence_bp.route("/posts/<item_id>/recommendation", methods=["GET"])
def media_post_recommendation(item_id: str):
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    business_id = str(request.args.get("business_id") or "").strip()
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        ok, error_response = _require_business(cursor, business_id, user_data)
        if not ok:
            return error_response
        recommendation = recommend_media_for_post(cursor, business_id=business_id, content_plan_item_id=str(item_id or "").strip())
        return jsonify({"success": True, "recommendation": recommendation})
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 404
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
    finally:
        db.close()
