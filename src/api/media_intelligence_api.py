from __future__ import annotations

import sys

from flask import Blueprint, Response, jsonify, request

from core.auth_helpers import require_auth_from_request, verify_business_access
from database_manager import DatabaseManager
from services.ai_runtime import (
    VISION_CAPABILITY,
    analyze_photo_runtime,
    estimate_photo_analysis_economics,
    is_capability_enabled,
    list_capability_settings,
    set_capability_enabled,
)
from services.media_intelligence import (
    build_photo_coverage,
    create_uploaded_photo_asset,
    create_photo_asset_version,
    list_photo_assets,
    load_business,
    record_photo_usage,
    recommend_media_for_post,
    upsert_photo_asset,
)
from services.media_file_storage import load_media_file


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


def _invalidate_social_approvals_for_photo_usage(
    cursor,
    *,
    business_id: str,
    content_plan_item_id: str,
    photo_asset_id: str,
    target_platform: str = "",
) -> int:
    if not business_id or not content_plan_item_id or not photo_asset_id:
        return 0
    platform_clause = "AND platform = %s" if target_platform else ""
    params = [photo_asset_id, business_id, content_plan_item_id]
    if target_platform:
        params.append(target_platform)
    cursor.execute(
        f"""
        UPDATE social_posts
        SET status = 'needs_review',
            approved_at = NULL,
            approval_id = NULL,
            automation_task_id = NULL,
            last_error = NULL,
            metadata_json = COALESCE(metadata_json, '{{}}'::jsonb) || jsonb_build_object(
                'selected_photo_asset_id', %s,
                'media_selection_changed_at', NOW(),
                'media_requires_review', TRUE
            ),
            updated_at = NOW()
        WHERE business_id = %s
          AND content_plan_item_id = %s
          AND status NOT IN ('published', 'publishing')
          {platform_clause}
        """,
        tuple(params),
    )
    return max(int(getattr(cursor, "rowcount", 0) or 0), 0)


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
        if not is_capability_enabled(cursor, business_id, VISION_CAPABILITY):
            return jsonify(
                {
                    "success": False,
                    "status": "vision_disabled",
                    "error": "Работа с фотографиями выключена.",
                    "next_action": "Включите интеллектуальную работу с фотографиями в настройках ИИ.",
                }
            ), 409
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


@media_intelligence_bp.route("/photos/upload", methods=["POST"])
def media_photo_upload():
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    business_id = str(request.form.get("business_id") or "").strip()
    uploaded_file = request.files.get("file")
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        ok, error_response = _require_business(cursor, business_id, user_data)
        if not ok:
            return error_response
        if not is_capability_enabled(cursor, business_id, VISION_CAPABILITY):
            return jsonify(
                {
                    "success": False,
                    "status": "vision_disabled",
                    "error": "Работа с фотографиями выключена.",
                    "next_action": "Включите интеллектуальную работу с фотографиями в настройках ИИ.",
                }
            ), 409
        if uploaded_file is None:
            return jsonify({"success": False, "error": "Выберите фото для загрузки"}), 400
        content = uploaded_file.read()
        photo = create_uploaded_photo_asset(
            cursor,
            business_id=business_id,
            user_id=_user_id(user_data),
            content=content,
            original_name=str(uploaded_file.filename or "photo"),
            mime_type=str(uploaded_file.mimetype or ""),
            metadata={"consent": "photo_intelligence_enabled"},
        )
        db.conn.commit()
        return jsonify({"success": True, "photo": photo, "coverage": build_photo_coverage(cursor, business_id)})
    except ValueError:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 400
    except Exception:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
    finally:
        db.close()


@media_intelligence_bp.route("/photos/<asset_id>/file", methods=["GET"])
def media_photo_file(asset_id: str):
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    variant = str(request.args.get("variant") or "original").strip() or "original"
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        cursor.execute(
            """
            SELECT business_id, storage_key, versions_json
            FROM photo_assets
            WHERE id = %s
            LIMIT 1
            """,
            (str(asset_id or "").strip(),),
        )
        row = cursor.fetchone()
        photo = dict(row) if hasattr(row, "keys") else None
        if not photo:
            columns = [col[0] for col in (getattr(cursor, "description", None) or [])]
            if isinstance(row, (list, tuple)) and columns:
                photo = {columns[idx]: row[idx] for idx in range(min(len(columns), len(row)))}
        if not photo:
            return jsonify({"success": False, "error": "Фото не найдено"}), 404
        ok, error_response = _require_business(cursor, str(photo.get("business_id") or ""), user_data)
        if not ok:
            return error_response
        versions = photo.get("versions_json") if isinstance(photo.get("versions_json"), dict) else {}
        variant_data = versions.get(variant) if isinstance(versions.get(variant), dict) else {}
        storage_path = str(variant_data.get("storage_path") or photo.get("storage_key") or "").strip()
        content = load_media_file(storage_path)
        if content is None:
            return jsonify({"success": False, "error": "Файл не найден"}), 404
        mime_type = str(variant_data.get("mime_type") or "image/jpeg")
        return Response(content, mimetype=mime_type)
    except Exception:
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
        if result.get("status") in {"analysis_failed", "image_required"}:
            db.conn.commit()
        else:
            db.conn.rollback()
        status_code = 402 if result.get("status") == "insufficient_credits" else 400
        if result.get("status") == "vision_disabled":
            status_code = 409
        if result.get("status") == "analysis_failed":
            status_code = 502
        return jsonify(result), status_code
    except Exception:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
    finally:
        db.close()


@media_intelligence_bp.route("/photos/<asset_id>/version", methods=["POST"])
def media_photo_new_version(asset_id: str):
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
        photo = create_photo_asset_version(
            cursor,
            business_id=business_id,
            photo_asset_id=str(asset_id or "").strip(),
            user_id=_user_id(user_data),
            original_url=str(payload.get("original_url") or "").strip(),
            content_hash=str(payload.get("content_hash") or "").strip(),
            metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        )
        db.conn.commit()
        return jsonify({"success": True, "photo": photo})
    except ValueError:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 404
    except Exception:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
    finally:
        db.close()


@media_intelligence_bp.route("/photos/<asset_id>/usage", methods=["POST"])
def media_photo_usage(asset_id: str):
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
        usage_type = str(payload.get("usage_type") or "publication")
        target_id = str(payload.get("target_id") or "").strip()
        target_platform = str(payload.get("target_platform") or "").strip()
        record_photo_usage(
            cursor,
            business_id=business_id,
            photo_asset_id=str(asset_id or "").strip(),
            usage_type=usage_type,
            target_id=target_id,
            target_platform=target_platform,
            metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        )
        approvals_reset = 0
        if usage_type == "publication":
            approvals_reset = _invalidate_social_approvals_for_photo_usage(
                cursor,
                business_id=business_id,
                content_plan_item_id=target_id,
                photo_asset_id=str(asset_id or "").strip(),
                target_platform=target_platform,
            )
        db.conn.commit()
        return jsonify(
            {
                "success": True,
                "approvals_reset": approvals_reset,
                "requires_review": approvals_reset > 0,
            }
        )
    except Exception:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
    finally:
        db.close()


@media_intelligence_bp.route("/economics/photo-analysis", methods=["POST"])
def media_photo_economics():
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    payload = request.get_json(silent=True) or {}
    economics = estimate_photo_analysis_economics(
        photo_count=payload.get("photo_count"),
        provider_total_cost=payload.get("provider_total_cost"),
        credit_price=payload.get("credit_price"),
        multiplier=payload.get("multiplier") or 10,
    )
    return jsonify({"success": True, "economics": economics})


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
