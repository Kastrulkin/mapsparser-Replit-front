from __future__ import annotations

import sys

from flask import Blueprint, jsonify, request

from auth_system import verify_session
from services.content_plan_service import (
    create_generated_content_plan,
    create_news_from_plan_item,
    delete_content_plan,
    delete_content_plan_item,
    duplicate_content_plan_item,
    duplicate_content_plan_item_to_locations,
    generate_draft_for_plan_item,
    get_content_plan,
    get_content_plan_learning_metrics,
    list_content_plans,
    load_plan_context_for_business,
    update_content_plan_item,
)


content_plans_bp = Blueprint("content_plans", __name__, url_prefix="/api/content-plans")


def _require_auth():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, (jsonify({"success": False, "error": "Требуется авторизация"}), 401)
    user_data = verify_session(auth_header.split(" ", 1)[1])
    if not user_data:
        return None, (jsonify({"success": False, "error": "Недействительный токен"}), 401)
    return user_data, None


@content_plans_bp.route("/context", methods=["GET"])
def content_plan_context():
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    business_id = str(request.args.get("business_id") or "").strip()
    scope_type = str(request.args.get("scope_type") or "single_business").strip()
    scope_target_id = str(request.args.get("scope_target_id") or "").strip() or None
    if not business_id:
        return jsonify({"success": False, "error": "business_id обязателен"}), 400
    try:
        payload = load_plan_context_for_business(
            str(user_data.get("user_id") or ""),
            business_id,
            scope_type,
            scope_target_id,
        )
        return jsonify({"success": True, "context": payload})
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 404
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500


@content_plans_bp.route("", methods=["GET"])
def content_plan_list():
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    business_id = str(request.args.get("business_id") or "").strip()
    if not business_id:
        return jsonify({"success": False, "error": "business_id обязателен"}), 400
    try:
        plans = list_content_plans(str(user_data.get("user_id") or ""), business_id)
        return jsonify({"success": True, "plans": plans})
    except PermissionError as exc:
        return jsonify({"success": False, "error": str(exc)}), 403
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@content_plans_bp.route("/learning-metrics", methods=["GET"])
def content_plan_learning_metrics():
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    business_id = str(request.args.get("business_id") or "").strip()
    if not business_id:
        return jsonify({"success": False, "error": "business_id обязателен"}), 400
    try:
        window_days = int(request.args.get("window_days") or 30)
    except Exception:
        window_days = 30
    try:
        metrics = get_content_plan_learning_metrics(
            str(user_data.get("user_id") or ""),
            business_id,
            window_days,
        )
        return jsonify({"success": True, **metrics})
    except PermissionError as exc:
        return jsonify({"success": False, "error": str(exc)}), 403
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@content_plans_bp.route("/generate", methods=["POST"])
def content_plan_generate():
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    data = request.get_json(silent=True) or {}
    business_id = str(data.get("business_id") or "").strip()
    if not business_id:
        return jsonify({"success": False, "error": "business_id обязателен"}), 400
    try:
        plan = create_generated_content_plan(
            str(user_data.get("user_id") or ""),
            business_id,
            scope_type=str(data.get("scope_type") or "single_business"),
            scope_target_id=str(data.get("scope_target_id") or "").strip() or None,
            period_days=int(data.get("period_days") or 30),
            density=str(data.get("density") or "standard"),
            content_mix=data.get("content_mix") if isinstance(data.get("content_mix"), dict) else {},
        )
        return jsonify({"success": True, "plan": plan})
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 404
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500


@content_plans_bp.route("/<plan_id>", methods=["GET"])
def content_plan_get(plan_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    try:
        plan = get_content_plan(str(user_data.get("user_id") or ""), plan_id)
        return jsonify({"success": True, "plan": plan})
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 404
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500


@content_plans_bp.route("/<plan_id>", methods=["DELETE"])
def content_plan_delete(plan_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    try:
        delete_content_plan(str(user_data.get("user_id") or ""), plan_id)
        return jsonify({"success": True})
    except PermissionError as exc:
        return jsonify({"success": False, "error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@content_plans_bp.route("/items/<item_id>", methods=["PUT"])
def content_plan_item_update(item_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    data = request.get_json(silent=True) or {}
    try:
        plan = update_content_plan_item(str(user_data.get("user_id") or ""), item_id, data)
        return jsonify({"success": True, "plan": plan})
    except PermissionError as exc:
        return jsonify({"success": False, "error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@content_plans_bp.route("/items/<item_id>", methods=["DELETE"])
def content_plan_item_delete(item_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    try:
        plan = delete_content_plan_item(str(user_data.get("user_id") or ""), item_id)
        return jsonify({"success": True, "plan": plan})
    except PermissionError as exc:
        return jsonify({"success": False, "error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@content_plans_bp.route("/items/<item_id>/generate-draft", methods=["POST"])
def content_plan_item_generate_draft(item_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    data = request.get_json(silent=True) or {}
    try:
        result = generate_draft_for_plan_item(
            str(user_data.get("user_id") or ""),
            item_id,
            language=str(data.get("language") or "").strip() or None,
        )
        return jsonify(
            {
                "success": True,
                "plan": result.get("plan"),
                "generation": result.get("generation") or {"success": True, "source": "ai"},
            }
        )
    except PermissionError as exc:
        return jsonify({"success": False, "error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@content_plans_bp.route("/items/<item_id>/create-news", methods=["POST"])
def content_plan_item_create_news(item_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    data = request.get_json(silent=True) or {}
    try:
        plan = create_news_from_plan_item(
            str(user_data.get("user_id") or ""),
            item_id,
            language=str(data.get("language") or "").strip() or None,
        )
        return jsonify({"success": True, "plan": plan})
    except PermissionError as exc:
        return jsonify({"success": False, "error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@content_plans_bp.route("/items/<item_id>/duplicate", methods=["POST"])
def content_plan_item_duplicate(item_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    try:
        plan = duplicate_content_plan_item(str(user_data.get("user_id") or ""), item_id)
        return jsonify({"success": True, "plan": plan})
    except PermissionError as exc:
        return jsonify({"success": False, "error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@content_plans_bp.route("/items/<item_id>/duplicate-to-locations", methods=["POST"])
def content_plan_item_duplicate_to_locations(item_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    data = request.get_json(silent=True) or {}
    try:
        plan = duplicate_content_plan_item_to_locations(
            str(user_data.get("user_id") or ""),
            item_id,
            data,
        )
        return jsonify({"success": True, "plan": plan})
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 404
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
