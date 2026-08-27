from __future__ import annotations

import csv
import io
import os
from typing import Any

from flask import Blueprint, jsonify, request
from psycopg2.extras import RealDictCursor

from core.auth_helpers import require_auth_from_request, verify_business_access
from database_manager import DatabaseManager
from services.creator_promotion_service import (
    add_deliverable,
    add_metric_snapshot,
    approve_campaign_terms,
    confirm_candidate_contact,
    create_campaign,
    create_collaboration,
    create_creator_room,
    creator_automation_allowed,
    creator_feature_state,
    enqueue_creator_search,
    import_creator_candidates,
    influencer_workspace,
    list_campaigns,
    list_collaborations,
    list_search_jobs,
    load_campaign,
    load_creator_room,
    load_search_job,
    metrics_summary,
    prepare_candidate_outreach,
    preview_candidate_outreach,
    promotion_overview,
    run_creator_search,
    respond_in_creator_room,
    update_campaign_terms,
    update_collaboration,
    update_shortlist,
    upsert_manual_creator,
    verify_deliverable,
)


creator_promotion_bp = Blueprint("creator_promotion", __name__, url_prefix="/api/promotion/influencers")


@creator_promotion_bp.before_request
def require_promotion_pilot():
    if request.endpoint in {
        "creator_promotion.feature_state",
        "creator_promotion.creator_room_public_get",
        "creator_promotion.creator_room_public_update",
    }:
        return None
    payload = request.get_json(silent=True) if request.method in {"POST", "PUT", "PATCH"} else None
    business_id = _business_id(payload if isinstance(payload, dict) else {})
    if not business_id:
        return None
    return _require_capability(business_id, "promotion_hub")


def _user_id(user_data: dict[str, Any]) -> str:
    return str(user_data.get("user_id") or user_data.get("id") or "").strip()


def _business_id(payload: dict[str, Any] | None = None) -> str:
    body = payload or {}
    return str(body.get("business_id") or request.args.get("business_id") or "").strip()


def _authorized_cursor(payload: dict[str, Any] | None = None):
    user_data = require_auth_from_request()
    if not user_data:
        return None, None, None, (jsonify({"success": False, "error": "Требуется авторизация"}), 401)
    business_id = _business_id(payload)
    if not business_id:
        return None, None, None, (jsonify({"success": False, "error": "business_id обязателен"}), 400)
    db = DatabaseManager()
    cursor = db.conn.cursor(cursor_factory=RealDictCursor)
    has_access, _owner_id = verify_business_access(cursor, business_id, user_data)
    if not has_access:
        db.close()
        return None, None, None, (jsonify({"success": False, "error": "Нет доступа к бизнесу"}), 403)
    return db, cursor, user_data, None


def _require_capability(business_id: str, capability: str):
    state = creator_feature_state(business_id)
    if not state.get(capability):
        return jsonify(
            {
                "success": False,
                "error": "Функция пока не включена для этого бизнеса.",
                "feature_state": state,
            }
        ), 404
    return None


def _require_creator_automation(cursor: Any, business_id: str):
    if creator_automation_allowed(cursor, business_id):
        return None
    return jsonify(
        {
            "success": False,
            "error": "Подготовка персональных сообщений, подключение каналов и отправка доступны после оплаты.",
            "code": "payment_required",
            "access": {
                "status": "payment_required",
                "cta_label": "Выбрать тариф",
                "cta_target": {"screen": "settings", "focus": "subscription"},
            },
        }
    ), 402


@creator_promotion_bp.get("/feature-state")
def feature_state():
    payload: dict[str, Any] = {}
    db, _cursor, _user_data, error = _authorized_cursor(payload)
    if error:
        return error
    business_id = _business_id(payload)
    try:
        return jsonify({"success": True, "feature_state": creator_feature_state(business_id)})
    finally:
        db.close()


@creator_promotion_bp.get("/overview")
def overview():
    db, cursor, _user_data, error = _authorized_cursor()
    if error:
        return error
    business_id = _business_id()
    try:
        gate = _require_capability(business_id, "promotion_hub")
        if gate:
            return gate
        return jsonify({"success": True, "overview": promotion_overview(cursor, business_id)})
    finally:
        db.close()


@creator_promotion_bp.get("/workspace")
def workspace():
    db, cursor, _user_data, error = _authorized_cursor()
    if error:
        return error
    business_id = _business_id()
    try:
        gate = _require_capability(business_id, "promotion_hub")
        if gate:
            return gate
        try:
            limit = min(max(int(request.args.get("limit") or 30), 1), 100)
            offset = max(int(request.args.get("cursor") or 0), 0)
        except (TypeError, ValueError):
            return jsonify({"success": False, "error": "Некорректный cursor или limit"}), 400
        filters = {
            "platform": request.args.get("platform"),
            "city": request.args.get("city"),
            "topic": request.args.get("topic"),
            "format": request.args.get("format"),
            "audience_size_band": request.args.get("audience_size_band"),
            "shortlisted": request.args.get("shortlisted"),
            "barter": request.args.get("barter"),
            "contactable": request.args.get("contactable"),
        }
        return jsonify({"success": True, "workspace": influencer_workspace(cursor, business_id=business_id, filters=filters, limit=limit, offset=offset)})
    except LookupError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    finally:
        db.close()


@creator_promotion_bp.get("/catalog")
def catalog():
    return workspace()


@creator_promotion_bp.get("/searches")
def searches_list():
    db, cursor, _user_data, error = _authorized_cursor()
    if error:
        return error
    business_id = _business_id()
    try:
        gate = _require_capability(business_id, "discovery")
        if gate:
            return gate
        return jsonify({"success": True, "searches": list_search_jobs(cursor, business_id)})
    finally:
        db.close()


@creator_promotion_bp.post("/searches")
def search_create():
    payload = request.get_json(silent=True) or {}
    db, cursor, user_data, error = _authorized_cursor(payload)
    if error:
        return error
    business_id = _business_id(payload)
    try:
        gate = _require_capability(business_id, "discovery")
        if gate:
            return gate
        async_enabled = str(os.getenv("INFLUENCER_ASYNC_SEARCH_ENABLED") or "true").strip().lower() in {"1", "true", "yes", "on"}
        search_function = enqueue_creator_search if async_enabled else run_creator_search
        search = search_function(cursor, business_id=business_id, user_id=_user_id(user_data), brief=payload.get("brief") if isinstance(payload.get("brief"), dict) else payload)
        db.conn.commit()
        return jsonify({"success": True, "search": search}), 202 if async_enabled else 201
    except (LookupError, ValueError) as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@creator_promotion_bp.get("/searches/<job_id>")
def search_get(job_id: str):
    db, cursor, _user_data, error = _authorized_cursor()
    if error:
        return error
    business_id = _business_id()
    try:
        return jsonify({"success": True, "search": load_search_job(cursor, business_id=business_id, job_id=job_id)})
    except LookupError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    finally:
        db.close()


@creator_promotion_bp.patch("/search-results/<result_id>")
def search_result_update(result_id: str):
    payload = request.get_json(silent=True) or {}
    db, cursor, _user_data, error = _authorized_cursor(payload)
    if error:
        return error
    business_id = _business_id(payload)
    try:
        search = update_shortlist(
            cursor,
            business_id=business_id,
            result_id=result_id,
            status=str(payload.get("shortlist_status") or "suggested"),
        )
        db.conn.commit()
        return jsonify({"success": True, "search": search})
    except LookupError as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    except ValueError as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    finally:
        db.close()


@creator_promotion_bp.post("/creators/manual")
def creator_manual():
    payload = request.get_json(silent=True) or {}
    db, cursor, _user_data, error = _authorized_cursor(payload)
    if error:
        return error
    business_id = _business_id(payload)
    try:
        creator = upsert_manual_creator(cursor, business_id=business_id, payload=payload)
        db.conn.commit()
        response: dict[str, Any] = {"success": True, "creator": creator}
        if creator.get("search_job_id"):
            response["search"] = load_search_job(cursor, business_id=business_id, job_id=str(creator["search_job_id"]))
        return jsonify(response), 201
    except (LookupError, ValueError) as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    finally:
        db.close()


@creator_promotion_bp.post("/creators/import")
def creators_import():
    payload = request.get_json(silent=True) or {}
    db, cursor, _user_data, error = _authorized_cursor(payload)
    if error:
        return error
    business_id = _business_id(payload)
    try:
        candidates = payload.get("candidates") if isinstance(payload.get("candidates"), list) else []
        if not candidates and str(payload.get("format") or "").lower() == "csv":
            reader = csv.DictReader(io.StringIO(str(payload.get("content") or "")))
            candidates = [dict(row) for row in reader]
        normalized = [item for item in candidates if isinstance(item, dict)]
        result = import_creator_candidates(
            cursor,
            business_id=business_id,
            candidates=normalized,
            search_job_id=str(payload.get("search_job_id") or ""),
        )
        db.conn.commit()
        response: dict[str, Any] = {"success": True, "result": result}
        if payload.get("search_job_id"):
            response["search"] = load_search_job(cursor, business_id=business_id, job_id=str(payload["search_job_id"]))
        return jsonify(response), 201
    except (LookupError, ValueError) as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    finally:
        db.close()


@creator_promotion_bp.get("/campaigns")
def campaigns_list():
    db, cursor, _user_data, error = _authorized_cursor()
    if error:
        return error
    business_id = _business_id()
    try:
        return jsonify({"success": True, "campaigns": list_campaigns(cursor, business_id)})
    finally:
        db.close()


@creator_promotion_bp.post("/campaigns")
def campaign_create():
    payload = request.get_json(silent=True) or {}
    db, cursor, user_data, error = _authorized_cursor(payload)
    if error:
        return error
    business_id = _business_id(payload)
    try:
        campaign = create_campaign(cursor, business_id=business_id, user_id=_user_id(user_data), payload=payload)
        db.conn.commit()
        return jsonify({"success": True, "campaign": campaign}), 201
    except (LookupError, ValueError) as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    finally:
        db.close()


@creator_promotion_bp.get("/campaigns/<campaign_id>")
def campaign_get(campaign_id: str):
    db, cursor, _user_data, error = _authorized_cursor()
    if error:
        return error
    business_id = _business_id()
    try:
        return jsonify({"success": True, "campaign": load_campaign(cursor, business_id=business_id, campaign_id=campaign_id)})
    except LookupError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    finally:
        db.close()


@creator_promotion_bp.patch("/campaigns/<campaign_id>")
def campaign_update(campaign_id: str):
    payload = request.get_json(silent=True) or {}
    db, cursor, _user_data, error = _authorized_cursor(payload)
    if error:
        return error
    business_id = _business_id(payload)
    try:
        campaign = update_campaign_terms(cursor, business_id=business_id, campaign_id=campaign_id, payload=payload)
        db.conn.commit()
        return jsonify({"success": True, "campaign": campaign, "requires_approval": True})
    except LookupError as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    except ValueError as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    finally:
        db.close()


@creator_promotion_bp.post("/campaigns/<campaign_id>/approve")
def campaign_approve(campaign_id: str):
    payload = request.get_json(silent=True) or {}
    db, cursor, _user_data, error = _authorized_cursor(payload)
    if error:
        return error
    business_id = _business_id(payload)
    try:
        campaign = approve_campaign_terms(cursor, business_id=business_id, campaign_id=campaign_id)
        db.conn.commit()
        return jsonify({"success": True, "campaign": campaign, "external_messages_sent": 0})
    except ValueError as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 409
    finally:
        db.close()


@creator_promotion_bp.post("/campaigns/<campaign_id>/candidates/<candidate_id>/prepare-outreach")
def candidate_prepare_outreach(campaign_id: str, candidate_id: str):
    payload = request.get_json(silent=True) or {}
    db, cursor, user_data, error = _authorized_cursor(payload)
    if error:
        return error
    business_id = _business_id(payload)
    try:
        access_gate = _require_creator_automation(cursor, business_id)
        if access_gate:
            return access_gate
        gate = _require_capability(business_id, "outreach")
        if gate:
            return gate
        prepared = prepare_candidate_outreach(
            cursor,
            db.conn,
            business_id=business_id,
            campaign_id=campaign_id,
            candidate_id=candidate_id,
            user_id=_user_id(user_data),
        )
        db.conn.commit()
        return jsonify({"success": True, "prepared": prepared, "external_messages_sent": 0})
    except LookupError as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    except ValueError as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    finally:
        db.close()


@creator_promotion_bp.get("/campaigns/<campaign_id>/candidates/<candidate_id>/outreach-preview")
def candidate_outreach_preview(campaign_id: str, candidate_id: str):
    db, cursor, _user_data, error = _authorized_cursor()
    if error:
        return error
    business_id = _business_id()
    try:
        access_gate = _require_creator_automation(cursor, business_id)
        if access_gate:
            return access_gate
        preview = preview_candidate_outreach(
            cursor,
            business_id=business_id,
            campaign_id=campaign_id,
            candidate_id=candidate_id,
        )
        return jsonify({"success": True, "preview": preview})
    except LookupError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    finally:
        db.close()


@creator_promotion_bp.post("/campaigns/<campaign_id>/candidates/<candidate_id>/confirm-contact")
def candidate_contact_confirm(campaign_id: str, candidate_id: str):
    payload = request.get_json(silent=True) or {}
    db, cursor, user_data, error = _authorized_cursor(payload)
    if error:
        return error
    business_id = _business_id(payload)
    try:
        access_gate = _require_creator_automation(cursor, business_id)
        if access_gate:
            return access_gate
        gate = _require_capability(business_id, "outreach")
        if gate:
            return gate
        preview = confirm_candidate_contact(
            cursor,
            business_id=business_id,
            campaign_id=campaign_id,
            candidate_id=candidate_id,
            user_id=_user_id(user_data),
            payload=payload,
        )
        db.conn.commit()
        return jsonify({"success": True, "preview": preview, "external_messages_sent": 0})
    except LookupError as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    except ValueError as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    finally:
        db.close()


@creator_promotion_bp.get("/collaborations")
def collaborations_list():
    db, cursor, _user_data, error = _authorized_cursor()
    if error:
        return error
    business_id = _business_id()
    try:
        return jsonify({"success": True, "collaborations": list_collaborations(cursor, business_id)})
    finally:
        db.close()


@creator_promotion_bp.post("/campaigns/<campaign_id>/candidates/<candidate_id>/collaboration")
def collaboration_create(campaign_id: str, candidate_id: str):
    payload = request.get_json(silent=True) or {}
    db, cursor, user_data, error = _authorized_cursor(payload)
    if error:
        return error
    business_id = _business_id(payload)
    try:
        collaboration = create_collaboration(
            cursor,
            business_id=business_id,
            campaign_id=campaign_id,
            candidate_id=candidate_id,
            user_id=_user_id(user_data),
            payload=payload,
        )
        db.conn.commit()
        return jsonify({"success": True, "collaboration": collaboration}), 201
    except LookupError as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    except ValueError as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    finally:
        db.close()


@creator_promotion_bp.patch("/collaborations/<collaboration_id>")
def collaboration_update(collaboration_id: str):
    payload = request.get_json(silent=True) or {}
    db, cursor, _user_data, error = _authorized_cursor(payload)
    if error:
        return error
    business_id = _business_id(payload)
    try:
        collaboration = update_collaboration(
            cursor,
            business_id=business_id,
            collaboration_id=collaboration_id,
            payload=payload,
        )
        db.conn.commit()
        return jsonify({"success": True, "collaboration": collaboration})
    except LookupError as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    except ValueError as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    finally:
        db.close()


@creator_promotion_bp.post("/collaborations/<collaboration_id>/room")
def collaboration_room_create(collaboration_id: str):
    payload = request.get_json(silent=True) or {}
    db, cursor, _user_data, error = _authorized_cursor(payload)
    if error:
        return error
    business_id = _business_id(payload)
    try:
        room = create_creator_room(cursor, business_id=business_id, collaboration_id=collaboration_id)
        db.conn.commit()
        return jsonify({"success": True, "room": room}), 201
    except LookupError as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    finally:
        db.close()


@creator_promotion_bp.post("/collaborations/<collaboration_id>/deliverables")
def deliverable_create(collaboration_id: str):
    payload = request.get_json(silent=True) or {}
    db, cursor, _user_data, error = _authorized_cursor(payload)
    if error:
        return error
    business_id = _business_id(payload)
    try:
        collaboration = add_deliverable(cursor, business_id=business_id, collaboration_id=collaboration_id, payload=payload)
        db.conn.commit()
        return jsonify({"success": True, "collaboration": collaboration}), 201
    except LookupError as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    finally:
        db.close()


@creator_promotion_bp.post("/deliverables/<deliverable_id>/metrics")
def metric_create(deliverable_id: str):
    payload = request.get_json(silent=True) or {}
    db, cursor, _user_data, error = _authorized_cursor(payload)
    if error:
        return error
    business_id = _business_id(payload)
    try:
        gate = _require_capability(business_id, "metrics")
        if gate:
            return gate
        summary = add_metric_snapshot(cursor, business_id=business_id, deliverable_id=deliverable_id, payload=payload)
        db.conn.commit()
        return jsonify({"success": True, "metrics": summary}), 201
    except (LookupError, ValueError) as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    finally:
        db.close()


@creator_promotion_bp.patch("/deliverables/<deliverable_id>/verification")
def deliverable_verify(deliverable_id: str):
    payload = request.get_json(silent=True) or {}
    db, cursor, _user_data, error = _authorized_cursor(payload)
    if error:
        return error
    business_id = _business_id(payload)
    try:
        collaboration = verify_deliverable(
            cursor,
            business_id=business_id,
            deliverable_id=deliverable_id,
            status=str(payload.get("verification_status") or "submitted"),
            proof=payload.get("proof") if isinstance(payload.get("proof"), dict) else {},
        )
        db.conn.commit()
        return jsonify({"success": True, "collaboration": collaboration})
    except LookupError as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    except ValueError as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    finally:
        db.close()


@creator_promotion_bp.get("/metrics")
def metrics_get():
    db, cursor, _user_data, error = _authorized_cursor()
    if error:
        return error
    business_id = _business_id()
    try:
        return jsonify({"success": True, "metrics": metrics_summary(cursor, business_id)})
    finally:
        db.close()


@creator_promotion_bp.get("/public/<token>")
def creator_room_public_get(token: str):
    db = DatabaseManager()
    cursor = db.conn.cursor(cursor_factory=RealDictCursor)
    try:
        return jsonify({"success": True, "room": load_creator_room(cursor, token)})
    except LookupError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    finally:
        db.close()


@creator_promotion_bp.patch("/public/<token>")
def creator_room_public_update(token: str):
    payload = request.get_json(silent=True) or {}
    db = DatabaseManager()
    cursor = db.conn.cursor(cursor_factory=RealDictCursor)
    try:
        room = respond_in_creator_room(cursor, token=token, payload=payload)
        db.conn.commit()
        return jsonify({"success": True, "room": room, "external_messages_sent": 0})
    except LookupError as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    except ValueError as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    finally:
        db.close()
