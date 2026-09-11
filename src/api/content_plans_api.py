from __future__ import annotations

import sys
import os

from flask import Blueprint, jsonify, request, current_app, send_file
from itsdangerous import URLSafeTimedSerializer, BadSignature
from services.content_plan_export import fingerprint, render_export

from auth_system import verify_session
from core.auth_helpers import verify_business_access
from database_manager import DatabaseManager
from subscription_manager import get_capability_access
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


def _export_signer():
    secret = os.getenv("CONTENT_PLAN_EXPORT_TOKEN_SECRET") or current_app.config.get("SECRET_KEY") or os.getenv("EXTERNAL_AUTH_SECRET_KEY")
    if not secret:
        raise RuntimeError("Content plan export signing secret is not configured")
    return URLSafeTimedSerializer(secret, salt="content-plan-export-v1")


def _export_plan(user_id, plan_id, session_context=None):
    plan = get_content_plan(user_id, plan_id)
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        cursor.execute("SELECT is_superadmin, is_active FROM users WHERE id = %s", (user_id,))
        row = cursor.fetchone()
        if not row:
            raise PermissionError("Нет доступа")
        admin = row.get("is_superadmin") if hasattr(row, "get") else row[0]
        active = row.get("is_active") if hasattr(row, "get") else row[1]
        if not active:
            raise PermissionError("Нет доступа")
        for business_id in {plan["business_id"], *(item.get("business_id") for item in plan["items"] if item.get("business_id"))}:
            allowed, _ = verify_business_access(cursor, business_id, {**(session_context or {}), "user_id": user_id, "is_superadmin": bool(admin)})
            if not allowed:
                raise PermissionError("Нет доступа ко всем точкам плана")
        access = get_capability_access(plan["business_id"], "maps.news", bool(admin))
        if not access.get("allowed"):
            raise PermissionError("Экспорт недоступен на текущем тарифе")
        return plan
    finally:
        db.close()


@content_plans_bp.route("/<plan_id>/export", methods=["POST"])
def content_plan_export_prepare(plan_id):
    user, error = _require_auth()
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify(error="Некорректный запрос"), 400
    file_format = payload.get("format")
    if not isinstance(file_format, str) or file_format not in {"xlsx", "pdf"}:
        return jsonify(error="Выберите Excel или PDF"), 400
    try:
        plan = _export_plan(str(user["user_id"]), plan_id, user)
    except PermissionError:
        return jsonify(error="Нет доступа к плану"), 403
    except ValueError:
        return jsonify(error="План не найден"), 404
    token = _export_signer().dumps({"user_id": str(user["user_id"]), "session_kind": user.get("session_kind", "standard"), "scope_business_id": user.get("scope_business_id"), "plan_id": plan_id, "format": file_format, "fingerprint": fingerprint(plan)})
    return jsonify(success=True, download_url=f"/api/content-plans/download/{token}", filename=f"content-plan-{plan_id}.{file_format}", expires_in=300)


@content_plans_bp.route("/download/<token>", methods=["GET"])
def content_plan_export_download(token):
    try:
        data = _export_signer().loads(token, max_age=300)
        plan = _export_plan(data["user_id"], data["plan_id"], data)
        if fingerprint(plan) != data["fingerprint"]:
            return jsonify(error="План изменился. Подготовьте файл ещё раз."), 409
        output = render_export(plan, data["format"])
    except BadSignature:
        return jsonify(error="Ссылка недействительна или устарела"), 410
    except (PermissionError, ValueError):
        return jsonify(error="План недоступен"), 403
    response = send_file(output, mimetype="application/pdf" if data["format"] == "pdf" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", as_attachment=True, download_name=f"content-plan-{data['plan_id']}.{data['format']}")
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Access-Control-Allow-Origin"] = "https://web.telegram.org"
    current_app.logger.info("content_plan_download_success plan_id=%s format=%s", data['plan_id'], data['format'])
    return response


def _content_plan_business_id(cursor):
    payload = request.get_json(silent=True) if request.method in {"POST", "PUT", "PATCH"} else {}
    payload = payload if isinstance(payload, dict) else {}
    business_id = str(payload.get("business_id") or request.args.get("business_id") or "").strip()
    if business_id:
        return business_id
    route_values = request.view_args or {}
    plan_id = str(route_values.get("plan_id") or "").strip()
    if plan_id:
        cursor.execute("SELECT business_id FROM contentplans WHERE id = %s LIMIT 1", (plan_id,))
        row = cursor.fetchone()
        if row:
            return str(row.get("business_id") if hasattr(row, "get") else row[0])
    item_id = str(route_values.get("item_id") or "").strip()
    if item_id:
        cursor.execute("SELECT business_id FROM contentplanitems WHERE id = %s LIMIT 1", (item_id,))
        row = cursor.fetchone()
        if row:
            return str(row.get("business_id") if hasattr(row, "get") else row[0])
    return ""


@content_plans_bp.before_request
def require_maps_news_access():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    user_data = verify_session(auth_header.split(" ", 1)[1])
    if not user_data:
        return None
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        business_id = _content_plan_business_id(cursor)
        if not business_id:
            return None
        has_access, owner_id = verify_business_access(cursor, business_id, user_data)
        if not owner_id or not has_access:
            return None
        access = get_capability_access(business_id, "maps.news", bool(user_data.get("is_superadmin")))
        if access.get("allowed"):
            return None
        return jsonify({
            "success": False,
            "error": "payment_required",
            **access,
            "return_to": request.full_path.rstrip("?"),
        }), 402
    finally:
        db.close()


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
        from core.auth_context import AuthContext
        plan = update_content_plan_item(str(user_data.get("user_id") or ""), item_id, data,
            auth_context=AuthContext.from_session(user_data))
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
