from __future__ import annotations

import sys

from flask import Blueprint, jsonify, request

from auth_system import verify_session
from services.content_voice_service import (
    add_content_voice_example,
    delete_content_voice_example,
    get_content_voice,
    update_content_voice,
)


content_voice_bp = Blueprint("content_voice", __name__, url_prefix="/api/content-voice")


def _require_auth():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, (jsonify({"success": False, "error": "Требуется авторизация"}), 401)
    user_data = verify_session(auth_header.split(" ", 1)[1])
    if not user_data:
        return None, (jsonify({"success": False, "error": "Недействительный токен"}), 401)
    return user_data, None


@content_voice_bp.route("", methods=["GET", "PATCH"])
def content_voice_profile():
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    data = request.get_json(silent=True) or {} if request.method == "PATCH" else {}
    business_id = str(request.args.get("business_id") or data.get("business_id") or "").strip()
    if not business_id:
        return jsonify({"success": False, "error": "business_id обязателен"}), 400
    try:
        user_id = str(user_data.get("user_id") or "")
        profile = update_content_voice(user_id, business_id, data) if request.method == "PATCH" else get_content_voice(user_id, business_id)
        return jsonify({"success": True, "profile": profile})
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 400
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500


@content_voice_bp.route("/examples", methods=["POST"])
def content_voice_example_create():
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    data = request.get_json(silent=True) or {}
    business_id = str(data.get("business_id") or "").strip()
    if not business_id:
        return jsonify({"success": False, "error": "business_id обязателен"}), 400
    try:
        example = add_content_voice_example(
            str(user_data.get("user_id") or ""),
            business_id,
            str(data.get("text") or ""),
            platform=str(data.get("platform") or ""),
            origin=str(data.get("origin") or "manual"),
            quality_status=str(data.get("quality_status") or "reference"),
        )
        return jsonify({"success": True, "example": example}), 201
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 400
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500


@content_voice_bp.route("/examples/<example_id>", methods=["DELETE"])
def content_voice_example_delete(example_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    try:
        delete_content_voice_example(str(user_data.get("user_id") or ""), example_id)
        return jsonify({"success": True})
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 404
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
