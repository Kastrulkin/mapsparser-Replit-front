from __future__ import annotations

from typing import Any, Callable

from flask import Blueprint, jsonify, request
from psycopg2.extras import RealDictCursor

from core.auth_helpers import require_auth_from_request, verify_business_access
from database_manager import DatabaseManager
from services.creator_portal_service import (
    add_offer_message,
    authenticate_creator,
    claim_email,
    create_invite,
    creator_portal_feature_state,
    creator_respond,
    list_relationships,
    login_email,
    offer_detail,
    portal_home,
    preview_invite,
    relationship_detail,
    request_password_reset,
    reset_password,
    review_offer,
    submit_creator_metrics,
    submit_creator_publication,
    update_creator_profile,
    update_notifications,
    verify_email,
)
from services.creator_offer_distribution_service import update_offer_preferences


creator_portal_bp = Blueprint("creator_portal", __name__, url_prefix="/api/creator-portal")


def _json_error(message: str, status: int):
    return jsonify({"success": False, "error": message}), status


def _feature(name: str):
    state = creator_portal_feature_state()
    if state.get(name):
        return None
    return _json_error("Функция пока не включена", 404)


def _creator_token() -> str:
    header = str(request.headers.get("Authorization") or "").strip()
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return ""


def _with_db(operation: Callable[[Any], Any]):
    db = DatabaseManager()
    cursor = db.conn.cursor(cursor_factory=RealDictCursor)
    try:
        result = operation(cursor)
        db.conn.commit()
        return jsonify({"success": True, **result})
    except PermissionError as exc:
        db.conn.rollback()
        return _json_error(str(exc), 401)
    except LookupError as exc:
        db.conn.rollback()
        return _json_error(str(exc), 404)
    except ValueError as exc:
        db.conn.rollback()
        return _json_error(str(exc), 400)
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


def _creator_operation(operation: Callable[[Any, dict[str, Any]], dict[str, Any]]):
    token = _creator_token()
    if not token:
        return _json_error("Требуется вход автора", 401)
    return _with_db(lambda cursor: operation(cursor, authenticate_creator(cursor, token)))


def _internal_context(payload: dict[str, Any] | None = None):
    user = require_auth_from_request()
    if not user:
        return None, None, None, None, _json_error("Требуется авторизация", 401)
    business_id = str((payload or {}).get("business_id") or request.args.get("business_id") or "").strip()
    if not business_id:
        return None, None, None, None, _json_error("business_id обязателен", 400)
    db = DatabaseManager()
    cursor = db.conn.cursor(cursor_factory=RealDictCursor)
    allowed, _owner = verify_business_access(cursor, business_id, user)
    if not allowed:
        db.close()
        return None, None, None, None, _json_error("Нет доступа к бизнесу", 403)
    return db, cursor, user, business_id, None


@creator_portal_bp.get("/feature-state")
def feature_state():
    return jsonify({"success": True, "feature_state": creator_portal_feature_state()})


@creator_portal_bp.get("/invites/<token>")
def invite_preview(token: str):
    gate = _feature("portal")
    if gate:
        return gate
    return _with_db(lambda cursor: {"invite": preview_invite(cursor, token)})


@creator_portal_bp.post("/invites/<token>/claim-email")
def invite_claim_email(token: str):
    gate = _feature("portal")
    if gate:
        return gate
    payload = request.get_json(silent=True) or {}
    return _with_db(lambda cursor: claim_email(cursor, invite_token=token,
                                                email=str(payload.get("email") or ""),
                                                password=str(payload.get("password") or "")))


@creator_portal_bp.post("/email/verify")
def email_verify():
    gate = _feature("portal")
    if gate:
        return gate
    payload = request.get_json(silent=True) or {}
    return _with_db(lambda cursor: verify_email(cursor, str(payload.get("token") or "")))


@creator_portal_bp.post("/login/email")
def email_login():
    gate = _feature("portal")
    if gate:
        return gate
    payload = request.get_json(silent=True) or {}
    return _with_db(lambda cursor: login_email(cursor, email=str(payload.get("email") or ""),
                                                password=str(payload.get("password") or "")))


@creator_portal_bp.post("/password/request")
def password_request():
    payload = request.get_json(silent=True) or {}
    return _with_db(lambda cursor: request_password_reset(cursor, str(payload.get("email") or "")))


@creator_portal_bp.post("/password/reset")
def password_reset():
    payload = request.get_json(silent=True) or {}
    return _with_db(lambda cursor: reset_password(cursor, token=str(payload.get("token") or ""),
                                                   password=str(payload.get("password") or "")))


@creator_portal_bp.get("/me")
def me():
    return _creator_operation(lambda cursor, account: {"workspace": portal_home(cursor, account)})


@creator_portal_bp.get("/offers/<collaboration_id>")
def offer_get(collaboration_id: str):
    return _creator_operation(lambda cursor, account: {
        "offer": offer_detail(cursor, profile_id=str(account["creator_profile_id"]), collaboration_id=collaboration_id)
    })


@creator_portal_bp.post("/offers/<collaboration_id>/respond")
def offer_respond(collaboration_id: str):
    payload = request.get_json(silent=True) or {}
    return _creator_operation(lambda cursor, account: {
        "offer": creator_respond(cursor, account=account, collaboration_id=collaboration_id,
                                  action=str(payload.get("action") or ""), message=payload.get("message"))
    })


@creator_portal_bp.post("/offers/<collaboration_id>/messages")
def offer_message(collaboration_id: str):
    payload = request.get_json(silent=True) or {}
    return _creator_operation(lambda cursor, account: {
        "message": add_offer_message(cursor, collaboration_id=collaboration_id, sender_type="creator",
                                      sender_id=str(account["id"]), body=str(payload.get("message") or ""),
                                      profile_id=str(account["creator_profile_id"]))
    })


@creator_portal_bp.post("/offers/<offer_id>/publication")
def offer_publication(offer_id: str):
    payload = request.get_json(silent=True) or {}
    return _creator_operation(lambda cursor, account: {
        "offer": submit_creator_publication(cursor, account=account, offer_id=offer_id, payload=payload)
    })


@creator_portal_bp.post("/offers/<offer_id>/metrics")
def offer_metrics(offer_id: str):
    payload = request.get_json(silent=True) or {}
    return _creator_operation(lambda cursor, account: {
        "offer": submit_creator_metrics(cursor, account=account, offer_id=offer_id, payload=payload)
    })


@creator_portal_bp.patch("/profile")
def profile_update():
    payload = request.get_json(silent=True) or {}
    return _creator_operation(lambda cursor, account: {"profile": update_creator_profile(cursor, account=account, payload=payload)})


@creator_portal_bp.patch("/notifications")
def notifications_update():
    payload = request.get_json(silent=True) or {}
    return _creator_operation(lambda cursor, account: {"notifications": update_notifications(cursor, account=account, payload=payload)})


@creator_portal_bp.patch("/availability")
def availability_update():
    payload = request.get_json(silent=True) or {}
    return _creator_operation(lambda cursor, account: {
        "availability": update_offer_preferences(
            cursor,
            profile_id=str(account["creator_profile_id"]),
            payload=payload,
        )
    })


@creator_portal_bp.get("/internal/relationships")
def relationships_list():
    gate = _feature("relationships")
    if gate:
        return gate
    db, cursor, user, business_id, error = _internal_context()
    if error:
        return error
    try:
        stage = str(request.args.get("stage") or "").strip() or None
        stages = [item.strip() for item in str(request.args.get("stages") or "").split(",") if item.strip()]
        limit = min(max(int(request.args.get("limit") or 100), 1), 500)
        offset = max(int(request.args.get("offset") or 0), 0)
        registry = list_relationships(cursor, business_id=business_id,
                                      is_superadmin=bool(user.get("is_superadmin")),
                                      stage=stage, stages=stages, limit=limit, offset=offset)
        return jsonify({"success": True, "registry": registry})
    except ValueError as exc:
        return _json_error(str(exc), 400)
    finally:
        db.close()


@creator_portal_bp.post("/internal/relationships/<profile_id>/invite")
def relationship_invite(profile_id: str):
    gate = _feature("portal")
    if gate:
        return gate
    payload = request.get_json(silent=True) or {}
    db, cursor, user, _business_id, error = _internal_context(payload)
    if error:
        return error
    try:
        if not user.get("is_superadmin"):
            return _json_error("Приглашения создаёт LocalOS", 403)
        invite = create_invite(cursor, profile_id=profile_id, created_by=str(user.get("user_id") or user.get("id") or ""))
        db.conn.commit()
        return jsonify({"success": True, "invite": invite})
    except (LookupError, ValueError) as exc:
        db.conn.rollback()
        return _json_error(str(exc), 404 if isinstance(exc, LookupError) else 400)
    finally:
        db.close()


@creator_portal_bp.get("/internal/relationships/<profile_id>")
def relationship_get(profile_id: str):
    gate = _feature("relationships")
    if gate:
        return gate
    db, cursor, user, business_id, error = _internal_context()
    if error:
        return error
    try:
        item = relationship_detail(cursor, profile_id=profile_id, business_id=business_id,
                                   is_superadmin=bool(user.get("is_superadmin")))
        return jsonify({"success": True, "relationship": item})
    except LookupError as exc:
        return _json_error(str(exc), 404)
    finally:
        db.close()


@creator_portal_bp.post("/internal/collaborations/<collaboration_id>/review")
def collaboration_review(collaboration_id: str):
    payload = request.get_json(silent=True) or {}
    db, cursor, user, business_id, error = _internal_context(payload)
    if error:
        return error
    try:
        if not user.get("is_superadmin"):
            return _json_error("Проверку выполняет LocalOS", 403)
        result = review_offer(cursor, business_id=business_id, collaboration_id=collaboration_id,
                              reviewer_id=str(user.get("user_id") or user.get("id") or ""),
                              decision=str(payload.get("decision") or ""))
        db.conn.commit()
        return jsonify({"success": True, **result})
    except (LookupError, ValueError) as exc:
        db.conn.rollback()
        return _json_error(str(exc), 404 if isinstance(exc, LookupError) else 400)
    finally:
        db.close()


@creator_portal_bp.post("/internal/collaborations/<collaboration_id>/messages")
def collaboration_message(collaboration_id: str):
    payload = request.get_json(silent=True) or {}
    db, cursor, user, business_id, error = _internal_context(payload)
    if error:
        return error
    try:
        if not user.get("is_superadmin"):
            return _json_error("Переписку ведёт LocalOS", 403)
        cursor.execute("SELECT id FROM creator_collaborations WHERE id = %s AND business_id = %s", (collaboration_id, business_id))
        if not cursor.fetchone():
            raise LookupError("Предложение не найдено")
        message = add_offer_message(cursor, collaboration_id=collaboration_id, sender_type="localos",
                                    sender_id=str(user.get("user_id") or user.get("id") or ""),
                                    body=str(payload.get("message") or ""),
                                    visible_to_business=bool(payload.get("visible_to_business")))
        db.conn.commit()
        return jsonify({"success": True, "message": message})
    except (LookupError, ValueError) as exc:
        db.conn.rollback()
        return _json_error(str(exc), 404 if isinstance(exc, LookupError) else 400)
    finally:
        db.close()
