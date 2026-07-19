from __future__ import annotations

import os
import re
import uuid
from typing import Any

from flask import Blueprint, jsonify, request
from psycopg2.extras import Json, RealDictCursor

from api.prospecting.access_schema import _require_auth, _resolve_business_for_user
from pg_db_utils import get_db_connection
from services.outreach_campaign_service import (
    DEFAULT_SEQUENCE,
    SUPPORTED_CHANNELS,
    approve_campaign,
    build_pilot_readiness,
    build_preview,
    change_campaign_status,
    persist_preview,
    record_campaign_business_outcome,
    record_campaign_event,
    record_manual_touch,
)
from services.outreach_safety_service import (
    learning_stat_metrics,
    normalized_contact_hash,
    recipient_key,
    run_dispatch_preflight,
)
from services.contact_intelligence_service import enqueue_enrichment_job
from services.outreach_personalization_ai import generation_contract_current
from services.outreach_email_adapter import (
    EmailAdapterError,
    normalize_mailbox_config,
    preflight_mailbox,
)
from services.outreach_sender_service import (
    change_sender_permission,
    connect_email_sender,
    disconnect_sender,
    list_sender_accounts,
    load_sender_account,
    preflight_email_sender,
)


outreach_campaign_bp = Blueprint("outreach_campaigns", __name__)


def _learning_tokens(value: Any) -> set[str]:
    return {
        token[:6] if len(token) > 6 else token
        for token in re.findall(r"[a-zа-яё0-9]+", str(value or "").lower())
        if len(token) >= 4
    }


def _sender_scope(
    cursor: Any,
    user_data: dict[str, Any],
    *,
    scope_type: str,
    requested_business_id: str | None,
) -> tuple[str, str | None] | None:
    normalized_scope = str(scope_type or "business").strip().lower()
    if normalized_scope == "platform":
        return ("platform", None) if user_data.get("is_superadmin") else None
    if normalized_scope != "business":
        return None
    business_id = _resolve_business_for_user(cursor, user_data, requested_business_id)
    return ("business", business_id) if business_id else None


def _authorized_sender_account(
    cursor: Any,
    sender_account_id: str,
    user_data: dict[str, Any],
) -> dict[str, Any] | None:
    sender = load_sender_account(cursor, sender_account_id)
    if not sender:
        return None
    if sender.get("scope_type") == "platform":
        return sender if user_data.get("is_superadmin") else None
    business_id = str(sender.get("business_id") or "")
    allowed_business = _resolve_business_for_user(cursor, user_data, business_id)
    return sender if allowed_business == business_id else None


def _record_suppression_event(
    cursor: Any,
    *,
    suppression_id: str | None,
    action: str,
    scope_type: str,
    business_id: str | None,
    actor_id: str | None,
    payload: dict[str, Any] | None = None,
) -> None:
    cursor.execute(
        """
        INSERT INTO outreach_suppression_events (
            id, suppression_id, action, scope_type, business_id,
            actor_id, payload_json, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        """,
        (
            str(uuid.uuid4()), suppression_id, action, scope_type,
            business_id, actor_id, Json(payload or {}),
        ),
    )


def _authorized_workstream(cursor: Any, workstream_id: str, user_data: dict[str, Any]) -> dict[str, Any] | None:
    cursor.execute(
        "SELECT id, lead_id, workstream_type, client_business_id FROM lead_workstreams WHERE id = %s",
        (workstream_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    workstream = dict(row)
    if workstream.get("workstream_type") == "localos_sales":
        return workstream if user_data.get("is_superadmin") else None
    business_id = str(workstream.get("client_business_id") or "")
    allowed_business = _resolve_business_for_user(cursor, user_data, business_id)
    return workstream if allowed_business == business_id else None


def _authorized_campaign(cursor: Any, campaign_id: str, user_data: dict[str, Any]) -> dict[str, Any] | None:
    cursor.execute(
        "SELECT id, workstream_id FROM outreach_campaigns WHERE id = %s",
        (campaign_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    campaign = dict(row)
    return campaign if _authorized_workstream(cursor, str(campaign["workstream_id"]), user_data) else None


def _campaign_payload(cursor: Any, campaign_id: str) -> dict[str, Any] | None:
    cursor.execute("SELECT * FROM outreach_campaigns WHERE id = %s", (campaign_id,))
    row = cursor.fetchone()
    if not row:
        return None
    campaign = dict(row)
    cursor.execute(
        "SELECT * FROM outreach_campaign_touches WHERE campaign_id = %s ORDER BY sequence_index",
        (campaign_id,),
    )
    campaign["touches"] = [dict(item) for item in cursor.fetchall()]
    campaign["generation_current"] = bool(campaign["touches"]) and all(
        generation_contract_current(
            touch.get("message_brief_json"),
            touch.get("quality_gate_json"),
        )
        for touch in campaign["touches"]
    )
    campaign["requires_regeneration"] = not campaign["generation_current"]
    cursor.execute(
        "SELECT * FROM outreach_campaign_events WHERE campaign_id = %s ORDER BY created_at DESC LIMIT 200",
        (campaign_id,),
    )
    campaign["events"] = [dict(item) for item in cursor.fetchall()]
    return campaign


@outreach_campaign_bp.get("/api/outreach/sender-accounts")
def get_sender_accounts():
    user_data, error = _require_auth()
    if error:
        return error
    scope_type = str(request.args.get("scope_type") or "business").strip()
    requested_business_id = str(request.args.get("business_id") or "").strip() or None
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        scope = _sender_scope(
            cursor,
            user_data,
            scope_type=scope_type,
            requested_business_id=requested_business_id,
        )
        if not scope:
            return jsonify({"success": False, "error": "Sender scope access denied"}), 403
        resolved_scope, business_id = scope
        return jsonify({
            "success": True,
            "scope_type": resolved_scope,
            "business_id": business_id,
            "sender_accounts": list_sender_accounts(
                cursor, scope_type=resolved_scope, business_id=business_id,
            ),
        })
    finally:
        conn.close()


@outreach_campaign_bp.post("/api/outreach/sender-accounts/email/preflight")
def preflight_email_sender_connection():
    user_data, error = _require_auth()
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    mailbox_payload = payload.get("mailbox") if isinstance(payload.get("mailbox"), dict) else payload
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        scope = _sender_scope(
            cursor,
            user_data,
            scope_type=str(payload.get("scope_type") or "business"),
            requested_business_id=str(payload.get("business_id") or "").strip() or None,
        )
        if not scope:
            return jsonify({"success": False, "error": "Sender scope access denied"}), 403
        result = preflight_mailbox(normalize_mailbox_config(mailbox_payload))
        return jsonify({
            "success": True,
            "preflight": result,
            "scope_type": scope[0],
            "business_id": scope[1],
            "messages_sent": 0,
        })
    except (ValueError, EmailAdapterError) as exc:
        return jsonify({
            "success": False,
            "error": str(exc),
            "reason_code": getattr(exc, "code", str(exc)),
            "messages_sent": 0,
        }), 422
    finally:
        conn.close()


@outreach_campaign_bp.post("/api/outreach/sender-accounts/email")
def connect_email_sender_account():
    user_data, error = _require_auth()
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    mailbox_payload = payload.get("mailbox") if isinstance(payload.get("mailbox"), dict) else payload
    if "outreach_enabled" in payload and not isinstance(payload.get("outreach_enabled"), bool):
        return jsonify({"success": False, "error": "outreach_enabled must be boolean"}), 400
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        scope = _sender_scope(
            cursor,
            user_data,
            scope_type=str(payload.get("scope_type") or "business"),
            requested_business_id=str(payload.get("business_id") or "").strip() or None,
        )
        if not scope:
            return jsonify({"success": False, "error": "Sender scope access denied"}), 403
        sender = connect_email_sender(
            cursor,
            scope_type=scope[0],
            business_id=scope[1],
            owner_user_id=str(user_data.get("user_id") or "") or None,
            mailbox_payload=mailbox_payload,
            outreach_enabled=bool(payload.get("outreach_enabled", False)),
        )
        conn.commit()
        return jsonify({"success": True, "sender_account": sender}), 201
    except (ValueError, EmailAdapterError) as exc:
        conn.rollback()
        return jsonify({
            "success": False,
            "error": str(exc),
            "reason_code": getattr(exc, "code", str(exc)),
        }), 422
    finally:
        conn.close()


@outreach_campaign_bp.post("/api/outreach/sender-accounts/<sender_account_id>/preflight")
def preflight_existing_sender_account(sender_account_id: str):
    user_data, error = _require_auth()
    if error:
        return error
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        sender = _authorized_sender_account(cursor, sender_account_id, user_data)
        if not sender:
            return jsonify({"success": False, "error": "Sender account not found or access denied"}), 404
        if sender.get("channel") != "email":
            return jsonify({"success": False, "error": "Channel preflight is not available here"}), 409
        result = preflight_email_sender(
            cursor,
            sender_account_id,
            actor_id=str(user_data.get("user_id") or "") or None,
        )
        conn.commit()
        return jsonify({"success": True, "preflight": result, "messages_sent": 0})
    except (LookupError, ValueError, EmailAdapterError) as exc:
        conn.commit()
        return jsonify({
            "success": False,
            "error": str(exc),
            "reason_code": getattr(exc, "code", "sender_preflight_failed"),
            "messages_sent": 0,
        }), 422
    finally:
        conn.close()


@outreach_campaign_bp.patch("/api/outreach/sender-accounts/<sender_account_id>/permission")
def update_sender_account_permission(sender_account_id: str):
    user_data, error = _require_auth()
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload.get("outreach_enabled"), bool):
        return jsonify({"success": False, "error": "outreach_enabled must be boolean"}), 400
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        if not _authorized_sender_account(cursor, sender_account_id, user_data):
            return jsonify({"success": False, "error": "Sender account not found or access denied"}), 404
        sender = change_sender_permission(
            cursor,
            sender_account_id,
            outreach_enabled=payload["outreach_enabled"],
            actor_id=str(user_data.get("user_id") or "") or None,
        )
        conn.commit()
        return jsonify({"success": True, "sender_account": sender})
    except (LookupError, ValueError) as exc:
        conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 409
    finally:
        conn.close()


@outreach_campaign_bp.delete("/api/outreach/sender-accounts/<sender_account_id>")
def disconnect_sender_account(sender_account_id: str):
    user_data, error = _require_auth()
    if error:
        return error
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        if not _authorized_sender_account(cursor, sender_account_id, user_data):
            return jsonify({"success": False, "error": "Sender account not found or access denied"}), 404
        sender = disconnect_sender(
            cursor,
            sender_account_id,
            actor_id=str(user_data.get("user_id") or "") or None,
        )
        conn.commit()
        return jsonify({"success": True, "sender_account": sender})
    except LookupError as exc:
        conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    finally:
        conn.close()


@outreach_campaign_bp.post("/api/outreach/workstreams/<workstream_id>/preview")
def preview_campaign(workstream_id: str):
    user_data, error = _require_auth()
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    sequence = payload.get("sequence") if isinstance(payload.get("sequence"), list) else None
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        if not _authorized_workstream(cursor, workstream_id, user_data):
            return jsonify({"success": False, "error": "Workstream not found or access denied"}), 404
        preview = build_preview(cursor, workstream_id, sequence=sequence)
        campaign = None
        if bool(payload.get("save")) and preview.get("status") == "ready":
            campaign = persist_preview(
                cursor,
                preview,
                user_id=str(user_data.get("user_id") or ""),
            )
            conn.commit()
        else:
            conn.rollback()
        return jsonify({"success": True, "preview": preview, "campaign": campaign})
    except LookupError as exc:
        conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    except ValueError as exc:
        conn.rollback()
        return jsonify({"success": False, "error": str(exc), "reason_code": "preview_blocked"}), 422
    finally:
        conn.close()


@outreach_campaign_bp.get("/api/outreach/workstreams/<workstream_id>/campaigns")
def list_campaigns(workstream_id: str):
    user_data, error = _require_auth()
    if error:
        return error
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        if not _authorized_workstream(cursor, workstream_id, user_data):
            return jsonify({"success": False, "error": "Workstream not found or access denied"}), 404
        cursor.execute(
            "SELECT * FROM outreach_campaigns WHERE workstream_id = %s ORDER BY version DESC",
            (workstream_id,),
        )
        campaigns = []
        for row in cursor.fetchall():
            campaign = _campaign_payload(cursor, str(row["id"]))
            if campaign:
                campaigns.append(campaign)
        return jsonify({"success": True, "campaigns": campaigns})
    finally:
        conn.close()


@outreach_campaign_bp.get("/api/outreach/campaigns/<campaign_id>")
def get_campaign(campaign_id: str):
    user_data, error = _require_auth()
    if error:
        return error
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        if not _authorized_campaign(cursor, campaign_id, user_data):
            return jsonify({"success": False, "error": "Campaign not found or access denied"}), 404
        return jsonify({"success": True, "campaign": _campaign_payload(cursor, campaign_id)})
    finally:
        conn.close()


@outreach_campaign_bp.post("/api/outreach/campaigns/<campaign_id>/approve")
def approve_campaign_route(campaign_id: str):
    user_data, error = _require_auth()
    if error:
        return error
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        if not _authorized_campaign(cursor, campaign_id, user_data):
            return jsonify({"success": False, "error": "Campaign not found or access denied"}), 404
        result = approve_campaign(cursor, campaign_id, user_id=str(user_data.get("user_id") or ""))
        conn.commit()
        return jsonify({"success": True, "campaign": result})
    except ValueError as exc:
        conn.rollback()
        return jsonify({"success": False, "error": str(exc), "reason_code": "campaign_preflight_failed"}), 409
    finally:
        conn.close()


@outreach_campaign_bp.post("/api/outreach/campaigns/<campaign_id>/<action>")
def change_campaign_route(campaign_id: str, action: str):
    if action not in {"pause", "resume", "cancel"}:
        return jsonify({"success": False, "error": "Unknown campaign action"}), 404
    user_data, error = _require_auth()
    if error:
        return error
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        if not _authorized_campaign(cursor, campaign_id, user_data):
            return jsonify({"success": False, "error": "Campaign not found or access denied"}), 404
        result = change_campaign_status(
            cursor, campaign_id, action, user_id=str(user_data.get("user_id") or ""),
        )
        conn.commit()
        return jsonify({"success": True, "campaign": result})
    except ValueError as exc:
        conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 409
    finally:
        conn.close()


@outreach_campaign_bp.post("/api/outreach/campaigns/<campaign_id>/touches/<touch_id>/manual-event")
def manual_touch_event(campaign_id: str, touch_id: str):
    user_data, error = _require_auth()
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    event_type = str(payload.get("event_type") or "").strip()
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        if not _authorized_campaign(cursor, campaign_id, user_data):
            return jsonify({"success": False, "error": "Campaign not found or access denied"}), 404
        result = record_manual_touch(
            cursor,
            campaign_id,
            touch_id,
            event_type,
            user_id=str(user_data.get("user_id") or ""),
            note=str(payload.get("note") or "").strip()[:1000],
        )
        conn.commit()
        return jsonify({"success": True, "event": result})
    except (LookupError, ValueError) as exc:
        conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 409
    finally:
        conn.close()


@outreach_campaign_bp.post("/api/outreach/campaigns/<campaign_id>/outcome")
def campaign_business_outcome(campaign_id: str):
    user_data, error = _require_auth()
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    outcome_type = str(payload.get("outcome_type") or "").strip()
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        if not _authorized_campaign(cursor, campaign_id, user_data):
            return jsonify({"success": False, "error": "Campaign not found or access denied"}), 404
        result = record_campaign_business_outcome(
            cursor,
            campaign_id,
            outcome_type,
            user_id=str(user_data.get("user_id") or ""),
            note=str(payload.get("note") or "").strip()[:1000],
        )
        conn.commit()
        return jsonify({"success": True, "outcome": result})
    except (LookupError, ValueError) as exc:
        conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 409
    finally:
        conn.close()


@outreach_campaign_bp.post("/api/outreach/campaigns/<campaign_id>/pilot-preflight")
def pilot_campaign_preflight(campaign_id: str):
    """Explain pilot readiness without sending or changing canonical state."""
    user_data, error = _require_auth()
    if error:
        return error
    global_dispatcher_enabled = str(
        os.getenv("OUTREACH_DISPATCH_ENABLED") or ""
    ).strip().lower() in {"1", "true", "yes", "on"}
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        if not _authorized_campaign(cursor, campaign_id, user_data):
            return jsonify({"success": False, "error": "Campaign not found or access denied"}), 404
        campaign = _campaign_payload(cursor, campaign_id) or {}
        touches = campaign.get("touches") if isinstance(campaign.get("touches"), list) else []
        first_touch = next(
            (
                touch for touch in touches
                if int(touch.get("sequence_index") or 0) == 0
            ),
            {},
        )
        queue = {}
        if first_touch.get("id"):
            cursor.execute(
                """
                SELECT id, batch_id, delivery_status, sender_account_id,
                       scheduled_at, sent_at, preflight_reason
                FROM outreachsendqueue
                WHERE campaign_touch_id = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (first_touch.get("id"),),
            )
            queue = dict(cursor.fetchone() or {})
        state = {
            "campaign_status": campaign.get("status"),
            "stop_reason": campaign.get("stop_reason"),
            "last_reply_at": campaign.get("last_reply_at"),
            "generation_current": campaign.get("generation_current"),
            "quality_passed": bool(touches) and all(
                bool((touch.get("quality_gate_json") or {}).get("passed"))
                for touch in touches
            ),
            "touch_id": first_touch.get("id"),
            "touch_status": first_touch.get("status"),
            "channel": first_touch.get("channel"),
            "sender_account_id": first_touch.get("sender_account_id") or queue.get("sender_account_id"),
            "queue_id": queue.get("id"),
            "delivery_status": queue.get("delivery_status"),
        }
        dispatch_preflight = None
        if (
            queue.get("id")
            and queue.get("delivery_status") == "queued"
            and campaign.get("status") in {"approved", "active"}
            and first_touch.get("channel") in {"telegram", "email"}
            and not global_dispatcher_enabled
        ):
            dispatch_preflight = run_dispatch_preflight(cursor, str(queue["id"]))
        readiness = build_pilot_readiness(
            state,
            dispatch_preflight=dispatch_preflight,
            global_dispatcher_enabled=global_dispatcher_enabled,
        )
        return jsonify({"success": True, "pilot_readiness": readiness})
    finally:
        conn.rollback()
        conn.close()


@outreach_campaign_bp.post("/api/outreach/campaigns/<campaign_id>/pilot-dispatch-first-touch")
def pilot_dispatch_first_touch(campaign_id: str):
    user_data, error = _require_auth()
    if error:
        return error
    if str(os.getenv("OUTREACH_DISPATCH_ENABLED") or "").strip().lower() in {"1", "true", "yes", "on"}:
        return jsonify({
            "success": False,
            "error": "Pilot dispatch is available only while the global dispatcher is disabled",
            "reason_code": "pilot_requires_global_dispatcher_disabled",
        }), 409
    payload = request.get_json(silent=True) or {}
    if str(payload.get("confirm_campaign_id") or "").strip() != campaign_id:
        return jsonify({
            "success": False,
            "error": "Explicit campaign confirmation is required",
            "reason_code": "pilot_campaign_confirmation_required",
        }), 400

    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        if not _authorized_campaign(cursor, campaign_id, user_data):
            return jsonify({"success": False, "error": "Campaign not found or access denied"}), 404
        cursor.execute(
            """
            SELECT campaign.status AS campaign_status,
                   touch.id AS touch_id, touch.sequence_index, touch.channel,
                   touch.status AS touch_status, touch.sender_account_id,
                   queue.id AS queue_id, queue.batch_id,
                   queue.delivery_status, queue.scheduled_at
            FROM outreach_campaigns campaign
            JOIN outreach_campaign_touches touch ON touch.campaign_id = campaign.id
            LEFT JOIN outreachsendqueue queue ON queue.campaign_touch_id = touch.id
            WHERE campaign.id = %s
            ORDER BY touch.sequence_index
            LIMIT 1
            """,
            (campaign_id,),
        )
        first_touch = dict(cursor.fetchone() or {})
        if not first_touch:
            return jsonify({"success": False, "error": "Campaign has no touches"}), 409
        if first_touch.get("campaign_status") not in {"approved", "active"}:
            return jsonify({
                "success": False,
                "error": "Approve the whole campaign before pilot dispatch",
                "reason_code": "pilot_campaign_not_approved",
            }), 409
        if int(first_touch.get("sequence_index") or 0) != 0:
            return jsonify({"success": False, "error": "First touch sequence is invalid"}), 409
        if first_touch.get("channel") not in {"telegram", "email"}:
            return jsonify({
                "success": False,
                "error": "The first pilot touch is manual and must be marked by the user",
                "reason_code": "pilot_first_touch_manual",
            }), 409
        if not first_touch.get("sender_account_id"):
            return jsonify({
                "success": False,
                "error": "First touch has no sender account",
                "reason_code": "sender_account_required",
            }), 409
        if not first_touch.get("queue_id") or first_touch.get("delivery_status") != "queued":
            return jsonify({
                "success": False,
                "error": "First touch is not queued for its initial send",
                "reason_code": "pilot_first_touch_not_queued",
            }), 409
        cursor.execute(
            """
            SELECT COUNT(*) AS count
            FROM outreach_campaign_touches
            WHERE campaign_id = %s
              AND status IN ('manual_sent', 'sent', 'delivered')
            """,
            (campaign_id,),
        )
        if int(dict(cursor.fetchone() or {}).get("count") or 0) > 0:
            return jsonify({
                "success": False,
                "error": "Pilot first touch has already been sent",
                "reason_code": "pilot_first_touch_already_sent",
            }), 409
        queue_id = str(first_touch["queue_id"])
        batch_id = str(first_touch["batch_id"])
        touch_id = str(first_touch["touch_id"])
        sender_account_id = str(first_touch["sender_account_id"])
    finally:
        conn.rollback()
        conn.close()

    from api.admin_prospecting import _sync_telegram_app_replies
    from services.outreach_dispatch_service import dispatch_due_outreach_queue
    from services.outreach_email_reply_service import sync_email_replies

    if first_touch.get("channel") == "telegram":
        reply_sync = _sync_telegram_app_replies(
            limit=50,
            sender_account_id=sender_account_id,
        )
    else:
        reply_sync = sync_email_replies(
            sender_limit=1,
            per_sender_limit=100,
            sender_account_id=sender_account_id,
        )
    reply_sync_failed = int(reply_sync.get("failed") or 0)
    if reply_sync_failed > 0:
        return jsonify({
            "success": False,
            "error": "Reply sync failed; pilot send is blocked",
            "reason_code": "reply_sync_failed",
            "messages_sent": 0,
        }), 409

    dispatch = dispatch_due_outreach_queue(
        batch_size=1,
        batch_id=batch_id,
        queue_id=queue_id,
    )
    messages_sent = int(dispatch.get("sent") or 0) + int(dispatch.get("delivered") or 0)
    audit_conn = get_db_connection()
    try:
        audit_cursor = audit_conn.cursor(cursor_factory=RealDictCursor)
        record_campaign_event(
            audit_cursor,
            campaign_id,
            "pilot_first_touch_dispatch",
            actor_id=str(user_data.get("user_id") or "") or None,
            touch_id=touch_id,
            reason_code="sent" if messages_sent == 1 else "not_sent",
            payload={
                "queue_id": queue_id,
                "picked": int(dispatch.get("picked") or 0),
                "sent": int(dispatch.get("sent") or 0),
                "delivered": int(dispatch.get("delivered") or 0),
                "blocked": int(dispatch.get("blocked") or 0),
                "future_touches_dispatched": 0,
            },
        )
        audit_conn.commit()
    except Exception:
        audit_conn.rollback()
        raise
    finally:
        audit_conn.close()
    return jsonify({
        "success": messages_sent == 1,
        "campaign_id": campaign_id,
        "touch_id": touch_id,
        "queue_id": queue_id,
        "messages_sent": messages_sent,
        "future_touches_dispatched": 0,
        "global_dispatcher_enabled": False,
        "dispatch": dispatch,
    }), 200


@outreach_campaign_bp.post("/api/outreach/campaigns/<campaign_id>/pilot-reply-sync")
def pilot_reply_sync(campaign_id: str):
    user_data, error = _require_auth()
    if error:
        return error
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        if not _authorized_campaign(cursor, campaign_id, user_data):
            return jsonify({"success": False, "error": "Campaign not found or access denied"}), 404
        cursor.execute(
            """
            SELECT queue.batch_id, queue.sender_account_id, queue.channel,
                   queue.delivery_status, queue.sent_at,
                   touch.id AS touch_id, touch.sequence_index
            FROM outreachsendqueue queue
            JOIN outreach_campaign_touches touch ON touch.id = queue.campaign_touch_id
            WHERE touch.campaign_id = %s
              AND queue.delivery_status IN ('sent', 'delivered')
              AND queue.sent_at IS NOT NULL
            ORDER BY touch.sequence_index DESC
            LIMIT 1
            """,
            (campaign_id,),
        )
        sent_touch = dict(cursor.fetchone() or {})
        if not sent_touch:
            return jsonify({
                "success": False,
                "error": "Campaign has no sent automatic touch",
                "reason_code": "pilot_reply_sync_before_send",
            }), 409
        channel = str(sent_touch.get("channel") or "")
        if channel not in {"telegram", "email"}:
            return jsonify({
                "success": False,
                "error": "Reply sync is unavailable for this channel",
                "reason_code": "pilot_reply_sync_manual_channel",
            }), 409
        sender_account_id = str(sent_touch.get("sender_account_id") or "")
        batch_id = str(sent_touch.get("batch_id") or "")
        touch_id = str(sent_touch.get("touch_id") or "")
        if not sender_account_id or not batch_id or not touch_id:
            return jsonify({
                "success": False,
                "error": "Pilot reply sync context is incomplete",
                "reason_code": "pilot_reply_sync_context_missing",
            }), 409
    finally:
        conn.rollback()
        conn.close()

    if channel == "telegram":
        from api.admin_prospecting import _sync_telegram_app_replies

        sync_result = _sync_telegram_app_replies(
            batch_id=batch_id,
            limit=25,
            sender_account_id=sender_account_id,
        )
    else:
        from services.outreach_email_reply_service import sync_email_replies

        sync_result = sync_email_replies(
            sender_limit=1,
            per_sender_limit=100,
            sender_account_id=sender_account_id,
            campaign_id=campaign_id,
        )
    if int(sync_result.get("failed") or 0) > 0:
        return jsonify({
            "success": False,
            "error": "Reply sync failed",
            "reason_code": "pilot_reply_sync_failed",
            "channel": channel,
            "reply_sync": sync_result,
        }), 409

    result_conn = get_db_connection()
    try:
        result_cursor = result_conn.cursor(cursor_factory=RealDictCursor)
        result_cursor.execute(
            """
            SELECT campaign.status, campaign.stop_reason, campaign.last_reply_at,
                   inbound.classification, inbound.occurred_at AS reply_occurred_at
            FROM outreach_campaigns campaign
            LEFT JOIN LATERAL (
                SELECT classification, occurred_at
                FROM outreach_inbound_events
                WHERE campaign_id = campaign.id AND is_human = TRUE
                ORDER BY occurred_at DESC, created_at DESC
                LIMIT 1
            ) inbound ON TRUE
            WHERE campaign.id = %s
            """,
            (campaign_id,),
        )
        campaign_state = dict(result_cursor.fetchone() or {})
        reply_received = bool(campaign_state.get("last_reply_at") or campaign_state.get("classification"))
        record_campaign_event(
            result_cursor,
            campaign_id,
            "pilot_reply_sync",
            actor_id=str(user_data.get("user_id") or "") or None,
            touch_id=touch_id,
            reason_code="reply_received" if reply_received else "no_reply_yet",
            payload={
                "channel": channel,
                "sender_account_id": sender_account_id,
                "picked": int(sync_result.get("picked") or 0),
                "imported": int(sync_result.get("imported") or 0),
                "duplicates": int(sync_result.get("duplicates") or 0),
                "reply_received": reply_received,
            },
        )
        result_conn.commit()
    except Exception:
        result_conn.rollback()
        raise
    finally:
        result_conn.close()
    return jsonify({
        "success": True,
        "campaign_id": campaign_id,
        "channel": channel,
        "reply_received": reply_received,
        "classification": campaign_state.get("classification"),
        "campaign_status": campaign_state.get("status"),
        "stop_reason": campaign_state.get("stop_reason"),
        "future_touches_stopped": reply_received and campaign_state.get("stop_reason") == "recipient_replied",
        "reply_sync": sync_result,
    })


@outreach_campaign_bp.post("/api/outreach/suppressions")
def create_suppression():
    user_data, error = _require_auth()
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    workstream_id = str(payload.get("workstream_id") or "").strip()
    if not workstream_id:
        return jsonify({"success": False, "error": "workstream_id is required"}), 400
    reason_code = str(payload.get("reason_code") or "manual_dnc").strip()[:64]
    contact_type = str(payload.get("contact_type") or "").strip().lower()
    contact_value = str(payload.get("contact_value") or "").strip()
    requested_scope = str(payload.get("scope_type") or "").strip()
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        workstream = _authorized_workstream(cursor, workstream_id, user_data)
        if not workstream:
            return jsonify({"success": False, "error": "Workstream not found or access denied"}), 404
        default_scope = "platform" if workstream.get("workstream_type") == "localos_sales" else "business"
        scope_type = requested_scope or default_scope
        if scope_type == "platform_safety" and not user_data.get("is_superadmin"):
            return jsonify({"success": False, "error": "Platform safety scope requires superadmin"}), 403
        if scope_type not in {default_scope, "platform_safety"}:
            return jsonify({"success": False, "error": "Invalid suppression scope"}), 400
        contact_hash = normalized_contact_hash(contact_type, contact_value) if contact_type and contact_value else ""
        lead_recipient_key = recipient_key(str(workstream.get("lead_id") or ""))
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtext(%s))",
            (f"suppression:{scope_type}:{workstream.get('client_business_id') or ''}:{contact_hash or lead_recipient_key}",),
        )
        cursor.execute(
            """
            SELECT * FROM outreach_suppressions
            WHERE scope_type = %s
              AND COALESCE(business_id, '') = COALESCE(%s, '')
              AND (expires_at IS NULL OR expires_at > NOW())
              AND (
                  (NULLIF(%s, '') IS NOT NULL AND normalized_contact_hash = %s)
                  OR (NULLIF(%s, '') IS NULL AND recipient_key = %s)
              )
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (
                scope_type,
                workstream.get("client_business_id") if scope_type == "business" else None,
                contact_hash,
                contact_hash,
                contact_hash,
                lead_recipient_key,
            ),
        )
        existing = cursor.fetchone()
        if existing:
            conn.rollback()
            return jsonify({"success": True, "suppression": dict(existing), "reused": True}), 200
        suppression_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO outreach_suppressions (
                id, lead_id, workstream_id, scope_type, business_id,
                normalized_contact_hash, recipient_key, reason_code, source,
                note, expires_at, created_by, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, NULLIF(%s, ''), %s, %s, 'manual', %s, %s, %s, NOW(), NOW())
            RETURNING *
            """,
            (
                suppression_id, workstream.get("lead_id"), workstream_id, scope_type,
                workstream.get("client_business_id") if scope_type == "business" else None,
                contact_hash,
                lead_recipient_key, reason_code,
                str(payload.get("note") or "").strip()[:1000] or None,
                payload.get("expires_at"), str(user_data.get("user_id") or "") or None,
            ),
        )
        result = dict(cursor.fetchone())
        _record_suppression_event(
            cursor,
            suppression_id=suppression_id,
            action="created",
            scope_type=scope_type,
            business_id=workstream.get("client_business_id") if scope_type == "business" else None,
            actor_id=str(user_data.get("user_id") or "") or None,
            payload={
                "reason_code": reason_code,
                "contact_type": contact_type or None,
                "has_contact_hash": bool(contact_type and contact_value),
                "workstream_id": workstream_id,
            },
        )
        conn.commit()
        return jsonify({"success": True, "suppression": result}), 201
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@outreach_campaign_bp.get("/api/outreach/workstreams/<workstream_id>/suppressions")
def list_suppressions(workstream_id: str):
    user_data, error = _require_auth()
    if error:
        return error
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        workstream = _authorized_workstream(cursor, workstream_id, user_data)
        if not workstream:
            return jsonify({"success": False, "error": "Workstream not found or access denied"}), 404
        cursor.execute(
            """
            SELECT * FROM outreach_suppressions
            WHERE lead_id = %s OR workstream_id = %s
            ORDER BY created_at DESC
            """,
            (workstream.get("lead_id"), workstream_id),
        )
        return jsonify({"success": True, "suppressions": [dict(row) for row in cursor.fetchall()]})
    finally:
        conn.close()


@outreach_campaign_bp.delete("/api/outreach/suppressions/<suppression_id>")
def delete_suppression(suppression_id: str):
    user_data, error = _require_auth()
    if error:
        return error
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM outreach_suppressions WHERE id = %s", (suppression_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"success": False, "error": "Suppression not found"}), 404
        suppression = dict(row)
        authorized = bool(user_data.get("is_superadmin")) if suppression.get("scope_type") != "business" else (
            _resolve_business_for_user(cursor, user_data, str(suppression.get("business_id") or ""))
            == str(suppression.get("business_id") or "")
        )
        if not authorized:
            return jsonify({"success": False, "error": "Access denied"}), 403
        _record_suppression_event(
            cursor,
            suppression_id=suppression_id,
            action="deleted",
            scope_type=str(suppression.get("scope_type") or "business"),
            business_id=suppression.get("business_id"),
            actor_id=str(user_data.get("user_id") or "") or None,
            payload={"reason_code": suppression.get("reason_code")},
        )
        cursor.execute("DELETE FROM outreach_suppressions WHERE id = %s", (suppression_id,))
        conn.commit()
        return jsonify({"success": True, "deleted_id": suppression_id})
    finally:
        conn.close()


@outreach_campaign_bp.post("/api/outreach/suppressions/import")
def import_suppressions():
    user_data, error = _require_auth()
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    if not items or len(items) > 1000:
        return jsonify({"success": False, "error": "Provide 1 to 1000 suppression items"}), 400
    scope_type = str(payload.get("scope_type") or "business").strip()
    requested_business_id = str(payload.get("business_id") or "").strip() or None
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        if scope_type == "platform":
            if not user_data.get("is_superadmin"):
                return jsonify({"success": False, "error": "Access denied"}), 403
            business_id = None
        elif scope_type == "business":
            business_id = _resolve_business_for_user(cursor, user_data, requested_business_id)
            if not business_id:
                return jsonify({"success": False, "error": "Business access required"}), 403
        else:
            return jsonify({"success": False, "error": "Invalid scope_type"}), 400
        imported = []
        reused = 0
        actor_id = str(user_data.get("user_id") or "") or None
        for item in items:
            if not isinstance(item, dict):
                continue
            contact_type = str(item.get("contact_type") or "").strip().lower()
            contact_value = str(item.get("contact_value") or item.get("value") or "").strip()
            if not contact_type or not contact_value:
                continue
            contact_hash = normalized_contact_hash(contact_type, contact_value)
            cursor.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))",
                (f"suppression:{scope_type}:{business_id or ''}:{contact_hash}",),
            )
            cursor.execute(
                """
                SELECT id FROM outreach_suppressions
                WHERE scope_type = %s
                  AND COALESCE(business_id, '') = COALESCE(%s, '')
                  AND normalized_contact_hash = %s
                  AND (expires_at IS NULL OR expires_at > NOW())
                LIMIT 1
                """,
                (scope_type, business_id, contact_hash),
            )
            if cursor.fetchone():
                reused += 1
                continue
            suppression_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO outreach_suppressions (
                    id, scope_type, business_id, normalized_contact_hash,
                    reason_code, source, note, expires_at, created_by,
                    created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, 'import', %s, %s, %s, NOW(), NOW())
                RETURNING id
                """,
                (
                    suppression_id, scope_type, business_id, contact_hash,
                    str(item.get("reason_code") or "imported_dnc")[:64],
                    str(item.get("note") or "")[:1000] or None,
                    item.get("expires_at"), actor_id,
                ),
            )
            imported.append(suppression_id)
            _record_suppression_event(
                cursor,
                suppression_id=suppression_id,
                action="imported",
                scope_type=scope_type,
                business_id=business_id,
                actor_id=actor_id,
                payload={"contact_type": contact_type, "contact_hash": contact_hash},
            )
        if not imported and not reused:
            conn.rollback()
            return jsonify({"success": False, "error": "No valid suppression items"}), 400
        conn.commit()
        return jsonify({"success": True, "imported": len(imported), "reused": reused, "ids": imported}), 201
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@outreach_campaign_bp.get("/api/outreach/learning/strategy-stats")
def learning_strategy_stats():
    user_data, error = _require_auth()
    if error:
        return error
    workstream_type = str(request.args.get("workstream_type") or "client_partnership").strip()
    requested_business_id = str(request.args.get("business_id") or "").strip() or None
    if workstream_type not in {"localos_sales", "client_partnership"}:
        return jsonify({"success": False, "error": "Invalid workstream_type"}), 400
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        if workstream_type == "localos_sales":
            if not user_data.get("is_superadmin"):
                return jsonify({"success": False, "error": "Access denied"}), 403
            scope_type = "platform"
            business_id = None
        else:
            business_id = _resolve_business_for_user(cursor, user_data, requested_business_id)
            if not business_id:
                return jsonify({"success": False, "error": "Business access required"}), 403
            scope_type = "business"
        cursor.execute(
            """
            SELECT stats.*, COALESCE(outcome_counts.no_reply_count, 0) AS no_reply_count,
                   sender_health.sender_health_score,
                   sender_health.sender_health_status,
                   CASE
                       WHEN sample_status = 'insufficient_data' THEN 'insufficient_data'
                       WHEN complaint_count > 0 OR unsubscribe_count > 0 THEN 'review_safety'
                       WHEN positive_reply_count > 0 THEN 'candidate_for_reuse'
                       ELSE 'no_positive_signal'
                   END AS recommendation_status
            FROM outreach_strategy_stats stats
            LEFT JOIN LATERAL (
                SELECT COUNT(*) FILTER (WHERE event.outcome_type = 'no_reply') AS no_reply_count
                FROM outreach_learning_events event
                WHERE event.scope_type = stats.scope_type
                  AND COALESCE(event.business_id, '') = COALESCE(stats.business_id, '')
                  AND event.workstream_type = stats.workstream_type
                  AND event.strategy_fingerprint = stats.strategy_fingerprint
            ) outcome_counts ON TRUE
            LEFT JOIN LATERAL (
                SELECT
                    MIN(sender.health_score) AS sender_health_score,
                    CASE
                        WHEN BOOL_OR(sender.health_status = 'blocked') THEN 'blocked'
                        WHEN BOOL_OR(sender.health_status = 'paused') THEN 'paused'
                        WHEN BOOL_OR(sender.health_status = 'degraded') THEN 'degraded'
                        WHEN BOOL_OR(sender.health_status = 'warning') THEN 'warning'
                        ELSE 'healthy'
                    END AS sender_health_status
                FROM outreach_campaign_touches touch
                JOIN outreach_campaigns campaign ON campaign.id = touch.campaign_id
                JOIN outreach_sender_accounts sender ON sender.id = touch.sender_account_id
                WHERE touch.strategy_fingerprint = stats.strategy_fingerprint
                  AND campaign.scope_type = stats.scope_type
                  AND COALESCE(campaign.business_id, '') = COALESCE(stats.business_id, '')
            ) sender_health ON TRUE
            WHERE scope_type = %s
              AND COALESCE(business_id, '') = COALESCE(%s, '')
              AND workstream_type = %s
            ORDER BY
                CASE sample_status WHEN 'reliable' THEN 0 WHEN 'preliminary' THEN 1 ELSE 2 END,
                confidence DESC, delivered_count DESC
            LIMIT 200
            """,
            (scope_type, business_id, workstream_type),
        )
        stats_rows = []
        for raw_row in cursor.fetchall():
            row = dict(raw_row)
            row.update(learning_stat_metrics(row))
            stats_rows.append(row)
        return jsonify({
            "success": True,
            "scope_type": scope_type,
            "business_id": business_id,
            "workstream_type": workstream_type,
            "stats": stats_rows,
            "note": "Recommendations transfer strategy dimensions, never recipient facts.",
        })
    finally:
        conn.close()


@outreach_campaign_bp.post("/api/outreach/workstreams/<workstream_id>/apply-learning-recommendation")
def apply_learning_recommendation(workstream_id: str):
    user_data, error = _require_auth()
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    fingerprint = str(payload.get("strategy_fingerprint") or "").strip()
    if not fingerprint:
        return jsonify({"success": False, "error": "strategy_fingerprint is required"}), 400
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        workstream = _authorized_workstream(cursor, workstream_id, user_data)
        if not workstream:
            return jsonify({"success": False, "error": "Workstream not found or access denied"}), 404
        scope_type = "platform" if workstream.get("workstream_type") == "localos_sales" else "business"
        business_id = workstream.get("client_business_id") if scope_type == "business" else None
        cursor.execute(
            """
            SELECT *
            FROM outreach_strategy_stats
            WHERE scope_type = %s
              AND COALESCE(business_id, '') = COALESCE(%s, '')
              AND workstream_type = %s
              AND strategy_fingerprint = %s
            """,
            (scope_type, business_id, workstream.get("workstream_type"), fingerprint),
        )
        stat = dict(cursor.fetchone() or {})
        if not stat:
            return jsonify({"success": False, "error": "Learning recommendation not found"}), 404
        if (
            stat.get("sample_status") == "insufficient_data"
            or int(stat.get("positive_reply_count") or 0) <= 0
            or int(stat.get("unsubscribe_count") or 0) > 0
            or int(stat.get("complaint_count") or 0) > 0
        ):
            return jsonify({
                "success": False,
                "error": "Recommendation is not safe or does not have enough evidence",
                "reason_code": "learning_recommendation_not_eligible",
            }), 409
        cursor.execute(
            """
            SELECT lead.category,
                   latest_research.message_brief_json->>'segment' AS research_segment
            FROM lead_workstreams ws
            JOIN prospectingleads lead ON lead.id = ws.lead_id
            LEFT JOIN LATERAL (
                SELECT message_brief_json
                FROM lead_workstream_research research
                WHERE research.workstream_id = ws.id
                ORDER BY researched_at DESC, created_at DESC
                LIMIT 1
            ) latest_research ON TRUE
            WHERE ws.id = %s
            """,
            (workstream_id,),
        )
        lead_context = dict(cursor.fetchone() or {})
        current_segment_tokens = _learning_tokens(
            lead_context.get("research_segment") or lead_context.get("category")
        )
        learned_segment_tokens = _learning_tokens(
            (stat.get("dimensions_json") or {}).get("segment")
            if isinstance(stat.get("dimensions_json"), dict)
            else ""
        )
        if (
            current_segment_tokens
            and learned_segment_tokens
            and not current_segment_tokens.intersection(learned_segment_tokens)
        ):
            return jsonify({
                "success": False,
                "error": "Recommendation belongs to a different segment",
                "reason_code": "learning_segment_mismatch",
            }), 409
        cursor.execute(
            """
            SELECT BOOL_OR(sender.health_status IN ('degraded', 'paused', 'blocked')) AS unsafe_sender
            FROM outreach_campaign_touches touch
            JOIN outreach_campaigns campaign ON campaign.id = touch.campaign_id
            JOIN outreach_sender_accounts sender ON sender.id = touch.sender_account_id
            WHERE touch.strategy_fingerprint = %s
              AND campaign.scope_type = %s
              AND COALESCE(campaign.business_id, '') = COALESCE(%s, '')
            """,
            (fingerprint, scope_type, business_id),
        )
        sender_health = dict(cursor.fetchone() or {})
        if sender_health.get("unsafe_sender"):
            return jsonify({
                "success": False,
                "error": "Restore sender health before reusing this strategy",
                "reason_code": "sender_health_blocks_learning",
            }), 409
        dimensions = stat.get("dimensions_json") if isinstance(stat.get("dimensions_json"), dict) else {}
        sequence = [
            {"channel": channel, "day_offset": day, "angle": angle}
            for channel, day, angle in DEFAULT_SEQUENCE
        ]
        sequence_index = max(0, min(int(dimensions.get("sequence_index") or 0), len(sequence) - 1))
        recommended_channel = str(dimensions.get("channel") or "").strip().lower()
        recommended_angle = str(dimensions.get("angle") or "").strip().lower()
        recommended_day = dimensions.get("day_offset")
        if recommended_channel in SUPPORTED_CHANNELS:
            sequence[sequence_index]["channel"] = recommended_channel
        if recommended_angle:
            other_index = next(
                (index for index, item in enumerate(sequence) if item["angle"] == recommended_angle),
                None,
            )
            if other_index is not None and other_index != sequence_index:
                sequence[other_index]["angle"] = sequence[sequence_index]["angle"]
            sequence[sequence_index]["angle"] = recommended_angle
        if isinstance(recommended_day, int):
            previous_day = int(sequence[sequence_index - 1]["day_offset"]) if sequence_index > 0 else -1
            next_day = int(sequence[sequence_index + 1]["day_offset"]) if sequence_index + 1 < len(sequence) else recommended_day + 2
            if previous_day < recommended_day < next_day:
                sequence[sequence_index]["day_offset"] = recommended_day
        preview = build_preview(cursor, workstream_id, sequence=sequence)
        if preview.get("status") != "ready":
            conn.rollback()
            return jsonify({
                "success": False,
                "error": "Recommendation does not pass current lead preflight",
                "reason_code": "learning_recommendation_preview_blocked",
                "preview": preview,
            }), 422
        campaign = persist_preview(
            cursor,
            preview,
            user_id=str(user_data.get("user_id") or ""),
        )
        cursor.execute(
            """
            UPDATE outreach_campaigns
            SET policy_json = policy_json || %s, updated_at = NOW()
            WHERE id = %s
            """,
            (
                Json({
                    "learning_recommendation": {
                        "strategy_fingerprint": fingerprint,
                        "source_sample_status": stat.get("sample_status"),
                        "source_delivered_count": int(stat.get("delivered_count") or 0),
                        "source_positive_reply_count": int(stat.get("positive_reply_count") or 0),
                        "approval_required": True,
                    },
                }),
                campaign["id"],
            ),
        )
        record_campaign_event(
            cursor,
            campaign["id"],
            "learning_recommendation_applied",
            actor_id=str(user_data.get("user_id") or "") or None,
            payload={
                "strategy_fingerprint": fingerprint,
                "source_sample_status": stat.get("sample_status"),
                "facts_transferred": False,
                "approval_required": True,
            },
        )
        conn.commit()
        return jsonify({
            "success": True,
            "campaign": campaign,
            "preview": preview,
            "approval_required": True,
            "facts_transferred": False,
        }), 201
    except (TypeError, ValueError) as exc:
        conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 422
    finally:
        conn.close()


def _telegram_signal_for_workstream(
    cursor: Any,
    *,
    opportunity_id: str,
    workstream: dict[str, Any],
) -> dict[str, Any] | None:
    cursor.execute(
        """
        SELECT opportunity.*
        FROM telegram_opportunities opportunity
        JOIN telegram_opportunity_sources radar_source ON radar_source.id = opportunity.source_id
        JOIN knowledge_sources knowledge_source ON knowledge_source.id = radar_source.knowledge_source_id
        JOIN telegram_account_permissions permission ON permission.account_id = opportunity.account_id
        WHERE opportunity.id = %s
          AND opportunity.business_id = %s
          AND knowledge_source.visibility = 'public'
          AND knowledge_source.status = 'active'
          AND permission.radar_enabled = TRUE
          AND opportunity.message_link IS NOT NULL
        """,
        (opportunity_id, workstream.get("client_business_id")),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


@outreach_campaign_bp.get("/api/outreach/workstreams/<workstream_id>/telegram-signals")
def list_linked_telegram_signals(workstream_id: str):
    user_data, error = _require_auth()
    if error:
        return error
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        workstream = _authorized_workstream(cursor, workstream_id, user_data)
        if not workstream:
            return jsonify({"success": False, "error": "Workstream not found or access denied"}), 404
        cursor.execute(
            """
            SELECT link.id AS link_id, link.status AS link_status,
                   opportunity.id, opportunity.chat_title, opportunity.message_text,
                   opportunity.message_link, opportunity.message_date,
                   opportunity.relevance_score, opportunity.reason
            FROM lead_signal_links link
            JOIN telegram_opportunities opportunity ON opportunity.id = link.source_id
            WHERE link.workstream_id = %s
              AND link.source_type = 'telegram_opportunity'
            ORDER BY link.updated_at DESC
            """,
            (workstream_id,),
        )
        return jsonify({"success": True, "signals": [dict(row) for row in cursor.fetchall()]})
    finally:
        conn.close()


@outreach_campaign_bp.post("/api/outreach/workstreams/<workstream_id>/telegram-signals/<opportunity_id>")
def link_telegram_signal(workstream_id: str, opportunity_id: str):
    user_data, error = _require_auth()
    if error:
        return error
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        workstream = _authorized_workstream(cursor, workstream_id, user_data)
        if not workstream:
            return jsonify({"success": False, "error": "Workstream not found or access denied"}), 404
        if workstream.get("workstream_type") != "client_partnership":
            return jsonify({"success": False, "error": "Telegram signal linking currently requires business scope"}), 409
        signal = _telegram_signal_for_workstream(
            cursor, opportunity_id=opportunity_id, workstream=workstream,
        )
        if not signal:
            return jsonify({
                "success": False,
                "error": "Signal is not public, radar permission is disabled, or tenant does not match",
            }), 409
        link_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO lead_signal_links (
                id, workstream_id, source_type, source_id, status,
                linked_by, created_at, updated_at
            ) VALUES (%s, %s, 'telegram_opportunity', %s, 'selected', %s, NOW(), NOW())
            ON CONFLICT (workstream_id, source_type, source_id)
            DO UPDATE SET status = 'selected', linked_by = EXCLUDED.linked_by, updated_at = NOW()
            RETURNING *
            """,
            (link_id, workstream_id, opportunity_id, str(user_data.get("user_id") or "") or None),
        )
        link = dict(cursor.fetchone())
        job = enqueue_enrichment_job(cursor, workstream_id, force=True)
        conn.commit()
        return jsonify({"success": True, "link": link, "enrichment_job_id": str(job.get("id"))})
    finally:
        conn.close()


@outreach_campaign_bp.delete("/api/outreach/workstreams/<workstream_id>/telegram-signals/<opportunity_id>")
def unlink_telegram_signal(workstream_id: str, opportunity_id: str):
    user_data, error = _require_auth()
    if error:
        return error
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        if not _authorized_workstream(cursor, workstream_id, user_data):
            return jsonify({"success": False, "error": "Workstream not found or access denied"}), 404
        cursor.execute(
            """
            UPDATE lead_signal_links
            SET status = 'rejected', linked_by = %s, updated_at = NOW()
            WHERE workstream_id = %s
              AND source_type = 'telegram_opportunity'
              AND source_id = %s
            RETURNING id
            """,
            (str(user_data.get("user_id") or "") or None, workstream_id, opportunity_id),
        )
        row = cursor.fetchone()
        if not row:
            return jsonify({"success": False, "error": "Signal link not found"}), 404
        job = enqueue_enrichment_job(cursor, workstream_id, force=True)
        conn.commit()
        return jsonify({"success": True, "status": "rejected", "enrichment_job_id": str(job.get("id"))})
    finally:
        conn.close()


@outreach_campaign_bp.post("/api/outreach/enrichment/backfill")
def enrichment_backfill():
    user_data, error = _require_auth()
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    workstream_type = str(payload.get("workstream_type") or "client_partnership").strip()
    requested_business_id = str(payload.get("business_id") or "").strip() or None
    should_queue = bool(payload.get("queue"))
    force = bool(payload.get("force", True))
    limit = max(1, min(int(payload.get("limit") or 500), 2000))
    if workstream_type not in {"localos_sales", "client_partnership"}:
        return jsonify({"success": False, "error": "Invalid workstream_type"}), 400
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        if workstream_type == "localos_sales":
            if not user_data.get("is_superadmin"):
                return jsonify({"success": False, "error": "Access denied"}), 403
            business_id = None
        else:
            business_id = _resolve_business_for_user(cursor, user_data, requested_business_id)
            if not business_id:
                return jsonify({"success": False, "error": "Business access required"}), 403
        cursor.execute(
            """
            SELECT ws.id, ws.lead_id, ws.lifecycle_status,
                   latest.status AS enrichment_status,
                   EXISTS (
                       SELECT 1 FROM lead_workstream_research research
                       WHERE research.workstream_id = ws.id
                   ) AS has_research,
                   (SELECT COUNT(*) FROM lead_contact_points contact WHERE contact.lead_id = ws.lead_id) AS contact_count
            FROM lead_workstreams ws
            LEFT JOIN LATERAL (
                SELECT status FROM lead_enrichment_jobs job
                WHERE job.workstream_id = ws.id
                ORDER BY created_at DESC LIMIT 1
            ) latest ON TRUE
            WHERE ws.workstream_type = %s
              AND (%s IS NULL OR ws.client_business_id = %s)
            ORDER BY ws.updated_at ASC
            LIMIT %s
            """,
            (workstream_type, business_id, business_id, limit),
        )
        workstreams = [dict(row) for row in cursor.fetchall()]
        coverage = {
            "total": len(workstreams),
            "with_research": sum(1 for item in workstreams if item.get("has_research")),
            "with_contacts": sum(1 for item in workstreams if int(item.get("contact_count") or 0) > 0),
            "ready": sum(1 for item in workstreams if item.get("enrichment_status") == "ready"),
            "needs_contact": sum(1 for item in workstreams if item.get("enrichment_status") == "needs_contact"),
            "needs_evidence": sum(1 for item in workstreams if item.get("enrichment_status") == "needs_evidence"),
            "suppressed": sum(1 for item in workstreams if item.get("enrichment_status") == "suppressed"),
            "failed": sum(1 for item in workstreams if item.get("enrichment_status") == "failed"),
            "not_processed": sum(1 for item in workstreams if not item.get("enrichment_status")),
        }
        queued = 0
        reused = 0
        job_ids = []
        if should_queue:
            for workstream in workstreams:
                job = enqueue_enrichment_job(cursor, str(workstream["id"]), force=force)
                job_ids.append(str(job.get("id")))
                if job.get("reused"):
                    reused += 1
                else:
                    queued += 1
            conn.commit()
        else:
            conn.rollback()
        return jsonify({
            "success": True,
            "mode": "queued" if should_queue else "preview",
            "workstream_type": workstream_type,
            "business_id": business_id,
            "coverage": coverage,
            "queued": queued,
            "reused": reused,
            "job_ids": job_ids,
            "campaigns_created": 0,
            "campaigns_approved": 0,
            "messages_sent": 0,
        })
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
