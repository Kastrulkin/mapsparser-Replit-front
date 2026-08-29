from __future__ import annotations

import uuid
from typing import Any

from flask import Blueprint, jsonify, request
from psycopg2.extras import RealDictCursor

from core.auth_helpers import require_auth_from_request, verify_business_access
from database_manager import DatabaseManager
from services.lead_journey_service import (
    JourneyError,
    PUBLIC_EVENT_NAMES,
    build_growth_paths,
    build_lead_preview,
    build_lead_preview_from_sources,
    claim_journey,
    create_lead_journey,
    execute_command,
    journey_flow_enabled,
    journey_enabled,
    list_actions,
    load_action,
    load_public_journey,
    select_public_opportunity,
    serialize_action,
    serialize_journey,
)
from services.product_telemetry_service import record_product_event, sanitize_public_event_properties


lead_journey_bp = Blueprint("lead_journey_api", __name__)

COMMAND_EVENT_NAMES = {
    "prepare": "action_prepare_clicked",
    "copy": "message_copied",
    "mark_sent": "action_marked_sent",
    "prepare_followup": "followup_created",
    "record_reply": "reply_recorded",
    "save_terms": "deal_started",
    "mark_launched": "deal_started",
    "mark_published": "deal_started",
    "add_result": "result_added",
    "complete": "map_task_completed",
    "start_next_cycle": "next_action_opened",
    "open_upgrade": "paywall_viewed",
    "save_draft": "content_draft_saved",
    "schedule": "content_scheduled",
}


def _error(exc: JourneyError):
    return jsonify({"success": False, "error": str(exc), "code": exc.code}), exc.status_code


def _require_enabled(flag: str = "LEAD_JOURNEY_ENABLED"):
    if journey_enabled(flag):
        return None
    return jsonify({"success": False, "error": "Функция пока не включена", "code": "feature_disabled"}), 404


def _user_id(user_data: dict[str, Any]) -> str:
    return str(user_data.get("user_id") or user_data.get("id") or "").strip()


def _authorized_business_cursor(business_id: str):
    user_data = require_auth_from_request()
    if not user_data:
        return None, None, None, (jsonify({"success": False, "error": "Требуется авторизация"}), 401)
    if not business_id:
        return None, None, None, (jsonify({"success": False, "error": "business_id обязателен"}), 400)
    db = DatabaseManager()
    cursor = db.conn.cursor(cursor_factory=RealDictCursor)
    has_access, owner_id = verify_business_access(cursor, business_id, user_data)
    if not has_access:
        db.close()
        return None, None, None, (jsonify({"success": False, "error": "Нет доступа" if owner_id else "Бизнес не найден"}), 403 if owner_id else 404)
    return db, cursor, user_data, None


def _require_superadmin_user():
    user_data = require_auth_from_request()
    if not user_data:
        return None, (jsonify({"success": False, "error": "Требуется авторизация"}), 401)
    if not bool(user_data.get("is_superadmin")):
        return None, (jsonify({"success": False, "error": "Недостаточно прав"}), 403)
    return user_data, None


@lead_journey_bp.get("/api/journeys")
def admin_journey_list():
    disabled = _require_enabled()
    if disabled:
        return disabled
    disabled = _require_enabled("JOURNEY_ADMIN_BUILDER_ENABLED")
    if disabled:
        return disabled
    _user_data, error = _require_superadmin_user()
    if error:
        return error
    db = DatabaseManager()
    cursor = db.conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            SELECT journey.*, lead.name AS lead_name
            FROM lead_journeys journey
            LEFT JOIN prospectingleads lead ON lead.id = journey.prospect_lead_id
            ORDER BY journey.created_at DESC
            LIMIT 100
            """
        )
        journeys = []
        for row in cursor.fetchall() or []:
            item = serialize_journey(cursor, dict(row), public=False)
            cursor.execute(
                """
                SELECT * FROM journey_actions
                WHERE journey_id = %s
                ORDER BY created_at DESC LIMIT 1
                """,
                (row.get("id"),),
            )
            latest_action = cursor.fetchone()
            cursor.execute(
                """
                SELECT event_type, command, to_status, surface, occurred_at
                FROM journey_action_events
                WHERE action_id IN (SELECT id FROM journey_actions WHERE journey_id = %s)
                ORDER BY occurred_at DESC LIMIT 1
                """,
                (row.get("id"),),
            )
            latest_event = cursor.fetchone()
            item["lead_name"] = str(row.get("lead_name") or "")
            item["latest_action"] = serialize_action(dict(latest_action)) if latest_action else None
            item["latest_event"] = dict(latest_event) if latest_event else None
            journeys.append(item)
        return jsonify({"success": True, "journeys": journeys})
    finally:
        db.close()


@lead_journey_bp.get("/api/journeys/preview")
def admin_journey_preview():
    disabled = _require_enabled()
    if disabled:
        return disabled
    disabled = _require_enabled("JOURNEY_ADMIN_BUILDER_ENABLED")
    if disabled:
        return disabled
    _user_data, error = _require_superadmin_user()
    if error:
        return error
    lead_id = str(request.args.get("lead_id") or "").strip()
    if not lead_id:
        return jsonify({"success": False, "error": "lead_id обязателен"}), 400
    db = DatabaseManager()
    cursor = db.conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            "SELECT id, name, address, city, category, rating, reviews_count FROM prospectingleads WHERE id = %s",
            (lead_id,),
        )
        lead = cursor.fetchone()
        if not lead:
            return jsonify({"success": False, "error": "Лид не найден"}), 404
        return jsonify({"success": True, "preview": build_lead_preview_from_sources(cursor, dict(lead))})
    finally:
        db.close()


@lead_journey_bp.post("/api/journeys")
def create_journey():
    disabled = _require_enabled()
    if disabled:
        return disabled
    disabled = _require_enabled("JOURNEY_ADMIN_BUILDER_ENABLED")
    if disabled:
        return disabled
    _user_data, auth_error = _require_superadmin_user()
    if auth_error:
        return auth_error
    payload = request.get_json(silent=True) or {}
    selected_flow = str(payload.get("selected_flow") or "").strip()
    if not selected_flow:
        return jsonify({"success": False, "error": "Выберите маршрут клиента", "code": "selected_flow_required"}), 400
    if not journey_flow_enabled(selected_flow):
        return jsonify({"success": False, "error": "Это направление пока не включено", "code": "flow_disabled"}), 404
    db = DatabaseManager()
    cursor = db.conn.cursor(cursor_factory=RealDictCursor)
    try:
        lead_id = str(payload.get("lead_id") or "").strip() or None
        lead = None
        if lead_id:
            cursor.execute(
                "SELECT id, name, address, city, category, rating, reviews_count FROM prospectingleads WHERE id = %s",
                (lead_id,),
            )
            lead = cursor.fetchone()
            if not lead:
                return jsonify({"success": False, "error": "Лид не найден"}), 404
        preview = payload.get("preview") if isinstance(payload.get("preview"), dict) else {}
        if not preview and lead:
            preview = build_lead_preview_from_sources(cursor, dict(lead))
        journey, token = create_lead_journey(
            cursor,
            prospect_lead_id=lead_id,
            preview=preview,
            source=str(payload.get("source") or "outreach"),
            expires_in_days=int(payload.get("expires_in_days") or 30),
            source_offer_type=str(payload.get("source_offer_type") or "lead_offer"),
            source_offer_id=str(payload.get("source_offer_id") or "") or None,
            selected_flow=selected_flow,
            selected_entity_type=str(payload.get("selected_entity_type") or "") or None,
            selected_entity_id=str(payload.get("selected_entity_id") or "") or None,
        )
        db.conn.commit()
        public_path = f"/start/{token}"
        return jsonify({
            "success": True,
            "journey": journey,
            "public_token": token,
            "public_path": public_path,
            "public_url": request.url_root.rstrip("/") + public_path,
        }), 201
    except JourneyError as exc:
        db.conn.rollback()
        return _error(exc)
    finally:
        db.close()


@lead_journey_bp.get("/api/journeys/diagnostics")
def journey_diagnostics():
    disabled = _require_enabled()
    if disabled:
        return disabled
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    if not bool(user_data.get("is_superadmin")):
        return jsonify({"success": False, "error": "Недостаточно прав"}), 403
    db = DatabaseManager()
    cursor = db.conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            SELECT
              COUNT(*) FILTER (WHERE status IN ('ready', 'in_progress', 'waiting', 'blocked')) AS active_actions,
              COUNT(*) FILTER (WHERE status IN ('ready', 'in_progress', 'waiting', 'blocked') AND business_id IS NULL) AS orphan_actions,
              COUNT(*) FILTER (WHERE status IN ('ready', 'in_progress', 'waiting', 'blocked') AND updated_at < NOW() - INTERVAL '7 days') AS stale_actions,
              COUNT(*) FILTER (WHERE status = 'blocked') AS blocked_actions
            FROM journey_actions
            """
        )
        action_health = dict(cursor.fetchone() or {})
        cursor.execute(
            """
            SELECT
              COUNT(*) FILTER (
                WHERE journey.status = 'claimed' AND NOT EXISTS (
                  SELECT 1 FROM journey_actions action
                  WHERE action.journey_id = journey.id
                    AND action.status IN ('ready', 'in_progress', 'waiting', 'blocked')
                )
              ) AS claimed_without_active_action,
              COUNT(*) FILTER (
                WHERE action.flow_type = 'content' AND action.entity_id IS NOT NULL
                  AND NOT EXISTS (SELECT 1 FROM contentplanitems item WHERE item.id = action.entity_id)
              ) AS content_domain_mismatches
            FROM lead_journeys journey
            LEFT JOIN journey_actions action ON action.journey_id = journey.id
              AND action.status IN ('ready', 'in_progress', 'waiting', 'blocked')
            """
        )
        projection_health = dict(cursor.fetchone() or {})
        cursor.execute(
            """
            SELECT COALESCE(selected_flow, 'legacy') AS flow_type, status, COUNT(*) AS count
            FROM lead_journeys
            GROUP BY COALESCE(selected_flow, 'legacy'), status
            ORDER BY flow_type, status
            """
        )
        funnel_counts = [dict(row) for row in (cursor.fetchall() or [])]
        cursor.execute(
            """
            SELECT COUNT(*) AS notification_dedupe_failures
            FROM journey_action_notification_deliveries delivery
            JOIN journey_actions action ON action.id = delivery.action_id
            WHERE delivery.sent_at IS NULL
              AND delivery.created_at < NOW() - INTERVAL '1 hour'
              AND action.status IN ('ready', 'waiting', 'blocked')
              AND action.version = delivery.action_version
            """
        )
        notification_health = dict(cursor.fetchone() or {})
        return jsonify({
            "success": True,
            "flags": {
                "lead_journey": journey_enabled(),
                "influencer": journey_flow_enabled("influencer"),
                "partnership": journey_flow_enabled("partnership"),
                "maps": journey_flow_enabled("maps"),
                "content": journey_flow_enabled("content"),
                "admin_builder": journey_enabled("JOURNEY_ADMIN_BUILDER_ENABLED"),
                "post_auth_redirect": journey_enabled("JOURNEY_POST_AUTH_REDIRECT_ENABLED"),
                "growth_paths_navigation": journey_enabled("GROWTH_PATHS_NAVIGATION_ENABLED"),
                "block_access_v2": journey_enabled("BLOCK_ACCESS_V2_ENABLED"),
                "notifications": journey_enabled("JOURNEY_NOTIFICATIONS_ENABLED"),
                "upsell": journey_enabled("JOURNEY_UPSELL_ENABLED"),
            },
            "health": {**action_health, **projection_health, **notification_health},
            "journeys_by_flow_status": funnel_counts,
        })
    finally:
        db.close()


@lead_journey_bp.post("/api/journeys/<string:journey_id>/revoke")
def revoke_journey(journey_id: str):
    disabled = _require_enabled()
    if disabled:
        return disabled
    disabled = _require_enabled("JOURNEY_ADMIN_BUILDER_ENABLED")
    if disabled:
        return disabled
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    if not bool(user_data.get("is_superadmin")):
        return jsonify({"success": False, "error": "Недостаточно прав"}), 403
    db = DatabaseManager()
    cursor = db.conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            "UPDATE lead_journeys SET status = 'revoked', revoked_at = COALESCE(revoked_at, NOW()), updated_at = NOW() WHERE id = %s RETURNING id, status, revoked_at",
            (journey_id,),
        )
        journey = cursor.fetchone()
        if not journey:
            return jsonify({"success": False, "error": "Journey не найден"}), 404
        cursor.execute(
            "UPDATE journey_actions SET status = 'cancelled', version = version + 1, updated_at = NOW() WHERE journey_id = %s AND status IN ('ready', 'in_progress', 'waiting', 'blocked')",
            (journey_id,),
        )
        db.conn.commit()
        return jsonify({"success": True, "journey": dict(journey)})
    finally:
        db.close()


@lead_journey_bp.get("/api/journeys/public/<string:token>")
def public_journey(token: str):
    disabled = _require_enabled()
    if disabled:
        return disabled
    db = DatabaseManager()
    cursor = db.conn.cursor(cursor_factory=RealDictCursor)
    try:
        journey = load_public_journey(cursor, token)
        return jsonify({"success": True, "journey": serialize_journey(cursor, journey, public=True)})
    except JourneyError as exc:
        return _error(exc)
    finally:
        db.close()


@lead_journey_bp.post("/api/journeys/public/<string:token>/events")
def public_journey_event(token: str):
    disabled = _require_enabled()
    if disabled:
        return disabled
    payload = request.get_json(silent=True) or {}
    event_name = str(payload.get("event_name") or "").strip()
    surface = str(payload.get("surface") or "web").strip()
    if event_name not in PUBLIC_EVENT_NAMES:
        return jsonify({"success": False, "error": "Событие не поддерживается"}), 400
    if surface not in {"web", "telegram_mini_app"}:
        return jsonify({"success": False, "error": "Поверхность не поддерживается"}), 400
    db = DatabaseManager()
    cursor = db.conn.cursor(cursor_factory=RealDictCursor)
    try:
        journey = load_public_journey(cursor, token)
        event_id = record_product_event(
            cursor, event_name=event_name, surface=surface,
            business_id=str(journey.get("claimed_business_id") or "") or None,
            user_id=str(journey.get("claimed_user_id") or "") or None,
            lead_id=str(journey.get("prospect_lead_id") or "") or None,
            journey_id=str(journey.get("id") or "") or None,
            flow_type=str(payload.get("flow_type") or "") or None,
            entity_type=str(payload.get("entity_type") or "") or None,
            entity_id=str(payload.get("entity_id") or "") or None,
            target=str(payload.get("target") or ""),
            properties=sanitize_public_event_properties(payload.get("properties")),
        )
        db.conn.commit()
        return jsonify({"success": True, "event_id": event_id}), 201
    except JourneyError as exc:
        db.conn.rollback()
        return _error(exc)
    finally:
        db.close()


@lead_journey_bp.post("/api/journeys/public/<string:token>/opportunities/<string:flow_type>/<string:entity_id>/preview")
def public_opportunity_preview(token: str, flow_type: str, entity_id: str):
    disabled = _require_enabled()
    if disabled:
        return disabled
    db = DatabaseManager()
    cursor = db.conn.cursor(cursor_factory=RealDictCursor)
    try:
        _journey, preview = select_public_opportunity(
            cursor, token=token, flow_type=flow_type,
            entity_id="" if entity_id == "_" else entity_id,
        )
        db.conn.commit()
        return jsonify({"success": True, "preview": preview})
    except JourneyError as exc:
        db.conn.rollback()
        return _error(exc)
    finally:
        db.close()


@lead_journey_bp.post("/api/journeys/claim")
def claim():
    disabled = _require_enabled()
    if disabled:
        return disabled
    payload = request.get_json(silent=True) or {}
    surface = str(payload.get("surface") or "web").strip()
    if surface not in {"web", "telegram_mini_app"}:
        return jsonify({"success": False, "error": "Поверхность не поддерживается"}), 400
    business_id = str(payload.get("business_id") or "").strip()
    db, cursor, user_data, error = _authorized_business_cursor(business_id)
    if error:
        return error
    try:
        selected = load_public_journey(cursor, str(payload.get("token") or "").strip())
        if not journey_flow_enabled(str(selected.get("selected_flow") or "")):
            return jsonify({"success": False, "error": "Это направление пока не включено", "code": "flow_disabled"}), 404
        journey, action = claim_journey(
            cursor, token=str(payload.get("token") or "").strip(),
            user_id=_user_id(user_data), business_id=business_id,
        )
        record_product_event(
            cursor, event_name="registration_completed", surface=surface,
            business_id=business_id, user_id=_user_id(user_data),
            lead_id=journey.get("prospect_lead_id"), journey_id=journey.get("id"),
            action_id=action.get("id"), flow_type=action.get("flow_type"),
            entity_type=action.get("entity_type"), entity_id=action.get("entity_id"),
            target="journey_claim", properties={"source": journey.get("source")},
        )
        record_product_event(
            cursor, event_name="journey_claimed", surface=surface,
            business_id=business_id, user_id=_user_id(user_data),
            lead_id=journey.get("prospect_lead_id"), journey_id=journey.get("id"),
            action_id=action.get("id"), flow_type=action.get("flow_type"),
            entity_type=action.get("entity_type"), entity_id=action.get("entity_id"),
            target="journey_claim", properties={"source": journey.get("source")},
        )
        db.conn.commit()
        return jsonify({"success": True, "journey": journey, "action": action})
    except JourneyError as exc:
        db.conn.rollback()
        return _error(exc)
    finally:
        db.close()


@lead_journey_bp.get("/api/journey-actions")
def actions_list():
    disabled = _require_enabled()
    if disabled:
        return disabled
    business_id = str(request.args.get("business_id") or "").strip()
    db, cursor, _user_data, error = _authorized_business_cursor(business_id)
    if error:
        return error
    try:
        actions = list_actions(cursor, business_id=business_id)
        db.conn.commit()
        return jsonify({"success": True, "focus_action": actions[0] if actions else None, "actions": actions})
    finally:
        db.close()


@lead_journey_bp.get("/api/growth-paths")
def growth_paths():
    disabled = _require_enabled()
    if disabled:
        return disabled
    disabled = _require_enabled("GROWTH_PATHS_NAVIGATION_ENABLED")
    if disabled:
        return disabled
    business_id = str(request.args.get("business_id") or "").strip()
    db, cursor, user_data, error = _authorized_business_cursor(business_id)
    if error:
        return error
    try:
        cursor.execute(
            """
            SELECT LOWER(COALESCE(subscription_tier, '')) IN
                       ('starter', 'professional', 'concierge', 'elite', 'promo', 'basic', 'pro', 'enterprise')
                   AND LOWER(COALESCE(subscription_status, '')) IN ('active', 'trialing')
                   AND (subscription_ends_at IS NULL OR subscription_ends_at >= CURRENT_TIMESTAMP)
                   AS automation_allowed
            FROM businesses WHERE id = %s
            """,
            (business_id,),
        )
        business = cursor.fetchone() or {}
        automation_allowed = bool(business.get("automation_allowed")) or bool(user_data.get("is_superadmin"))
        actions = list_actions(cursor, business_id=business_id)
        paths = build_growth_paths(actions=actions, automation_allowed=automation_allowed)
        db.conn.commit()
        return jsonify({
            "success": True,
            "focus_action": actions[0] if actions else None,
            "paths": paths,
        })
    finally:
        db.close()


@lead_journey_bp.get("/api/journey-actions/history")
def action_history():
    disabled = _require_enabled()
    if disabled:
        return disabled
    business_id = str(request.args.get("business_id") or "").strip()
    db, cursor, _user_data, error = _authorized_business_cursor(business_id)
    if error:
        return error
    try:
        return jsonify({"success": True, "actions": list_actions(cursor, business_id=business_id, history=True)})
    finally:
        db.close()


@lead_journey_bp.get("/api/journey-actions/<string:action_id>")
def action_detail(action_id: str):
    disabled = _require_enabled()
    if disabled:
        return disabled
    business_id = str(request.args.get("business_id") or "").strip()
    db, cursor, _user_data, error = _authorized_business_cursor(business_id)
    if error:
        return error
    try:
        return jsonify({"success": True, "action": serialize_action(load_action(cursor, action_id=action_id, business_id=business_id))})
    except JourneyError as exc:
        return _error(exc)
    finally:
        db.close()


@lead_journey_bp.post("/api/journey-actions/<string:action_id>/commands")
def action_command(action_id: str):
    disabled = _require_enabled()
    if disabled:
        return disabled
    payload = request.get_json(silent=True) or {}
    business_id = str(payload.get("business_id") or "").strip()
    db, cursor, user_data, error = _authorized_business_cursor(business_id)
    if error:
        return error
    idempotency_key = str(request.headers.get("Idempotency-Key") or payload.get("idempotency_key") or "").strip()
    if not idempotency_key:
        idempotency_key = str(uuid.uuid4())
    surface = str(payload.get("surface") or "web")
    if surface not in {"web", "telegram_mini_app"}:
        return jsonify({"success": False, "error": "Поверхность не поддерживается"}), 400
    try:
        current_action = load_action(cursor, action_id=action_id, business_id=business_id)
        if current_action.get("flow_type") != "upgrade" and not journey_flow_enabled(str(current_action.get("flow_type") or "")):
            return jsonify({"success": False, "error": "Это направление пока не включено", "code": "flow_disabled"}), 404
        if current_action.get("flow_type") == "content" and str(payload.get("command") or "") != "open_upgrade" and not bool(user_data.get("is_superadmin")):
            cursor.execute(
                """
                SELECT LOWER(COALESCE(subscription_tier, '')) IN
                           ('starter', 'professional', 'concierge', 'elite', 'promo', 'basic', 'pro', 'enterprise')
                       AND LOWER(COALESCE(subscription_status, '')) IN ('active', 'trialing')
                       AND (subscription_ends_at IS NULL OR subscription_ends_at >= CURRENT_TIMESTAMP)
                       AS automation_allowed
                FROM businesses WHERE id = %s
                """,
                (business_id,),
            )
            access_row = cursor.fetchone() or {}
            if not bool(access_row.get("automation_allowed")):
                return jsonify({
                    "success": False,
                    "error": "Полный контент-сценарий доступен после оплаты тарифа.",
                    "code": "payment_required",
                    "payment_required": True,
                    "billing_url": "/dashboard/profile?focus=subscription#subscription",
                }), 403
        if current_action.get("flow_type") == "influencer" and current_action.get("action_type") in {
            "send_message", "check_reply", "send_followup", "define_terms", "mark_published", "add_result", "select_next_influencer",
        } and not bool(user_data.get("is_superadmin")):
            cursor.execute(
                """
                SELECT LOWER(COALESCE(subscription_tier, '')) IN
                           ('starter', 'professional', 'concierge', 'elite', 'promo', 'basic', 'pro', 'enterprise')
                       AND LOWER(COALESCE(subscription_status, '')) IN ('active', 'trialing')
                       AND (subscription_ends_at IS NULL OR subscription_ends_at >= CURRENT_TIMESTAMP)
                       AS automation_allowed
                FROM businesses WHERE id = %s
                """,
                (business_id,),
            )
            access_row = cursor.fetchone() or {}
            if not bool(access_row.get("automation_allowed")):
                return jsonify({
                    "success": False,
                    "error": "Персональные сообщения, подключение канала и отправка доступны после оплаты.",
                    "code": "payment_required",
                    "payment_required": True,
                    "billing_url": "/dashboard/profile?focus=subscription#subscription",
                }), 402
        result = execute_command(
            cursor, action_id=action_id, business_id=business_id, user_id=_user_id(user_data),
            command=str(payload.get("command") or "").strip(),
            expected_version=int(payload.get("version") or 0), idempotency_key=idempotency_key,
            surface=surface, payload=payload.get("payload") if isinstance(payload.get("payload"), dict) else {},
        )
        event_name = COMMAND_EVENT_NAMES.get(str(payload.get("command") or "").strip())
        if event_name and not result.get("idempotent_replay"):
            record_product_event(
                cursor, event_name=event_name, surface=surface,
                business_id=business_id, user_id=_user_id(user_data),
                lead_id=current_action.get("lead_id"), journey_id=current_action.get("journey_id"),
                action_id=current_action.get("id"), flow_type=current_action.get("flow_type"),
                entity_type=current_action.get("entity_type"), entity_id=current_action.get("entity_id"),
                target=str(payload.get("command") or ""),
                properties={"idempotent_replay": bool(result.get("idempotent_replay"))},
            )
        db.conn.commit()
        return jsonify({"success": True, **result})
    except JourneyError as exc:
        db.conn.rollback()
        return _error(exc)
    finally:
        db.close()
