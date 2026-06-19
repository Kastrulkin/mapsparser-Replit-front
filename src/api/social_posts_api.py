from __future__ import annotations

import sys

from flask import Blueprint, jsonify, request

from auth_system import verify_session
from services.social_post_service import (
    approve_social_post,
    collect_social_post_metrics,
    list_social_posts_for_plan,
    mark_manual_published,
    prepare_social_posts_for_item,
    publish_social_post,
)


social_posts_bp = Blueprint("social_posts", __name__)


def _require_auth():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, (jsonify({"success": False, "error": "Требуется авторизация"}), 401)
    user_data = verify_session(auth_header.split(" ", 1)[1])
    if not user_data:
        return None, (jsonify({"success": False, "error": "Недействительный токен"}), 401)
    return user_data, None


@social_posts_bp.route("/api/content-plans/items/<item_id>/social-posts/prepare", methods=["POST"])
def social_posts_prepare(item_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    data = request.get_json(silent=True) or {}
    platforms = data.get("platforms") if isinstance(data.get("platforms"), list) else None
    try:
        payload = prepare_social_posts_for_item(str(user_data.get("user_id") or ""), item_id, platforms)
        return jsonify({"success": True, **payload})
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 400
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500


@social_posts_bp.route("/api/content-plans/<plan_id>/social-posts", methods=["GET"])
def social_posts_list(plan_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    try:
        payload = list_social_posts_for_plan(str(user_data.get("user_id") or ""), plan_id)
        return jsonify({"success": True, **payload})
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 404
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500


@social_posts_bp.route("/api/social-posts/<post_id>/approve", methods=["POST"])
def social_posts_approve(post_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    try:
        post = approve_social_post(str(user_data.get("user_id") or ""), post_id)
        return jsonify({"success": True, "post": post})
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 400
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500


@social_posts_bp.route("/api/social-posts/<post_id>/publish", methods=["POST"])
def social_posts_publish(post_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    try:
        post = publish_social_post(str(user_data.get("user_id") or ""), post_id)
        return jsonify({"success": True, "post": post})
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 400
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500


@social_posts_bp.route("/api/social-posts/<post_id>/mark-manual-published", methods=["POST"])
def social_posts_mark_manual_published(post_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    data = request.get_json(silent=True) or {}
    try:
        post = mark_manual_published(
            str(user_data.get("user_id") or ""),
            post_id,
            provider_post_url=str(data.get("provider_post_url") or "").strip(),
            provider_post_id=str(data.get("provider_post_id") or "").strip(),
        )
        return jsonify({"success": True, "post": post})
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 400
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500


@social_posts_bp.route("/api/social-posts/metrics/collect", methods=["POST"])
def social_posts_metrics_collect():
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    data = request.get_json(silent=True) or {}
    try:
        payload = collect_social_post_metrics(
            str(user_data.get("user_id") or ""),
            business_id=str(data.get("business_id") or "").strip(),
            post_id=str(data.get("post_id") or "").strip(),
        )
        return jsonify({"success": True, **payload})
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 400
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
