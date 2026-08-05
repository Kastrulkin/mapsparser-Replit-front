from __future__ import annotations

import os
import re
import uuid
import hmac
from datetime import datetime, timedelta, timezone
from typing import Any

from flask import Blueprint, jsonify, request
from psycopg2.extras import Json, RealDictCursor

from api.prospecting.access_schema import _require_auth, _resolve_business_for_user
from pg_db_utils import get_db_connection
from services.outreach_campaign_service import (
    DEFAULT_SEQUENCE,
    SENDER_MODE_LOCALOS_FOR_PARTNER,
    SUPPORTED_CHANNELS,
    apply_draft_campaign_review,
    approve_campaign,
    build_pilot_readiness,
    build_preview,
    change_campaign_status,
    persist_preview,
    record_campaign_business_outcome,
    record_campaign_event,
    record_manual_touch,
    resolve_sender_mode,
    runtime_touch_channel_status,
    update_draft_campaign_touch,
)
from services.outreach_safety_service import (
    classify_inbound_event,
    learning_stat_metrics,
    normalized_contact_hash,
    recipient_key,
    run_dispatch_preflight,
    strategy_fingerprint,
)
from services.outreach_relationship_service import (
    approve_room_invitation,
    build_relationship_delta,
    build_room_preview,
)
from services.contact_intelligence_service import enqueue_enrichment_job
from services.outreach_personalization_ai import generation_contract_current
from services.outreach_email_adapter import (
    EmailAdapterError,
    normalize_mailbox_config,
    preflight_mailbox,
)
from services.outreach_experiment_service import (
    ACTIVE_SOCIAL_MAP_GAP,
    assign_experiment_member,
    compile_pattern_draft,
    corpus_patterns_enabled,
    create_beauty_experiment,
    experiments_enabled,
    extract_and_review_corpus_pattern,
    list_experiments,
    next_stage,
    select_stage_candidates,
)
from services.outreach_sender_service import (
    change_sender_permission,
    connect_email_sender,
    connect_manual_max_sender,
    connect_vk_community_sender,
    connect_vk_sender,
    disconnect_sender,
    list_sender_accounts,
    load_sender_account,
    preflight_email_sender,
    preflight_vk_sender_account,
)
from services.outreach_vk_adapter import (
    VK_OUTREACH_SCOPES,
    VkOutreachAdapterError,
    verify_vk_outreach_access,
)
from services.vk_oauth_service import (
    VkOAuthError,
    build_vk_authorization_url,
    decode_vk_oauth_state,
    encode_vk_oauth_state,
    exchange_vk_authorization_code,
    validate_vk_pkce_value,
    vk_pkce_challenge,
)


outreach_campaign_bp = Blueprint("outreach_campaigns", __name__)


def _parse_campaign_start_at(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    normalized = f"{raw[:-1]}+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("start_at must be a valid ISO-8601 date-time") from exc
    if parsed.tzinfo is None:
        raise ValueError("start_at must include a timezone")
    utc_value = parsed.astimezone(timezone.utc)
    if utc_value < datetime.now(timezone.utc) - timedelta(minutes=5):
        raise ValueError("start_at must not be in the past")
    return utc_value


def _outreach_sandbox_enabled() -> bool:
    return str(os.getenv("OUTREACH_SANDBOX_ENABLED") or "true").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _room_preview_for_outreach(preview: dict[str, Any]) -> dict[str, Any]:
    lead = preview.get("lead") if isinstance(preview.get("lead"), dict) else {}
    return build_room_preview(
        preview,
        {
            "lead_name": lead.get("name"),
            "city": lead.get("city"),
            "category": lead.get("category"),
            "source_url": lead.get("source_url"),
        },
    )


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


def _authorized_sender_mode(
    workstream: dict[str, Any],
    requested_mode: Any,
    user_data: dict[str, Any],
) -> str:
    mode = resolve_sender_mode(str(workstream.get("workstream_type") or ""), requested_mode)
    if mode == SENDER_MODE_LOCALOS_FOR_PARTNER and not user_data.get("is_superadmin"):
        raise PermissionError("Only a superadmin can send a partner campaign as LocalOS")
    return mode


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
        """
        SELECT touch.*,
               sender.status AS sender_status,
               sender.outreach_enabled AS sender_outreach_enabled,
               sender.health_status AS sender_health_status,
               sender.capabilities_json AS sender_capabilities_json,
               permissions.outreach_enabled AS telegram_outreach_enabled
        FROM outreach_campaign_touches touch
        LEFT JOIN outreach_sender_accounts sender ON sender.id = touch.sender_account_id
        LEFT JOIN telegram_account_permissions permissions ON permissions.account_id = sender.external_account_id
        WHERE touch.campaign_id = %s
        ORDER BY touch.sequence_index
        """,
        (campaign_id,),
    )
    campaign["touches"] = []
    for item in cursor.fetchall():
        touch = dict(item)
        touch["channel_status"] = runtime_touch_channel_status(touch)
        campaign["touches"].append(touch)
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
    cursor.execute(
        """
        SELECT id, campaign_id, touch_id, sender_account_id, channel,
               provider_event_id, event_type, classification, is_human,
               stops_campaign, confidence, raw_payload_json, classified_by,
               occurred_at, created_at
        FROM outreach_inbound_events
        WHERE campaign_id = %s
        ORDER BY occurred_at, created_at
        """,
        (campaign_id,),
    )
    campaign["inbound_events"] = [dict(item) for item in cursor.fetchall()]
    cursor.execute(
        """
        SELECT queue.id, queue.campaign_touch_id AS touch_id, queue.channel,
               queue.delivery_status, queue.provider_message_id, queue.error_text,
               queue.scheduled_at, queue.sent_at, queue.created_at, queue.updated_at
        FROM outreachsendqueue queue
        JOIN outreach_campaign_touches touch ON touch.id = queue.campaign_touch_id
        WHERE touch.campaign_id = %s
        ORDER BY queue.created_at
        """,
        (campaign_id,),
    )
    campaign["deliveries"] = [dict(item) for item in cursor.fetchall()]
    cursor.execute(
        """
        SELECT id, slug, status, visibility, room_json, updated_at
        FROM sales_rooms
        WHERE id = %s
        """,
        (campaign.get("room_id"),),
    )
    room = cursor.fetchone()
    campaign["room"] = dict(room) if room else None
    cursor.execute(
        "SELECT * FROM lead_relationship_states WHERE workstream_id = %s",
        (campaign.get("workstream_id"),),
    )
    relationship = cursor.fetchone()
    campaign["relationship"] = dict(relationship) if relationship else None
    return campaign


MESSAGE_QUEUE_READ_EVENTS = {"read", "read_receipt", "opened", "message_read"}
MESSAGE_QUEUE_FAILED_STATUSES = {"failed", "delivery_failed", "retry", "dlq", "blocked"}


def _message_queue_status(row: dict[str, Any], *, now: datetime | None = None) -> str:
    """Resolve one honest, user-facing state for an outreach touch.

    Read/delivered states are never inferred from a successful send. They only
    appear when the provider persisted the corresponding receipt.
    """
    if bool(row.get("reply_is_human")):
        return "replied"
    receipt_type = str(row.get("receipt_event_type") or "").strip().lower()
    if receipt_type in MESSAGE_QUEUE_READ_EVENTS:
        return "read"

    delivery_status = str(row.get("delivery_status") or "").strip().lower()
    if delivery_status in MESSAGE_QUEUE_FAILED_STATUSES:
        return "failed"
    if delivery_status in {"read", "opened"}:
        return "read"
    if delivery_status in {"delivered", "sent", "sending", "queued"}:
        return delivery_status

    touch_status = str(row.get("touch_status") or "draft").strip().lower()
    campaign_status = str(row.get("campaign_status") or "draft").strip().lower()
    if touch_status in MESSAGE_QUEUE_FAILED_STATUSES:
        return "failed"
    if touch_status in {"sent", "delivered", "manual_sent"}:
        return "sent" if touch_status == "manual_sent" else touch_status
    if touch_status in {"paused", "cancelled", "skipped", "reply_cancelled"}:
        return touch_status
    if campaign_status == "draft" or touch_status == "draft":
        return "draft"

    scheduled_at = row.get("scheduled_at")
    current_time = now or datetime.now(timezone.utc)
    if isinstance(scheduled_at, datetime):
        comparable_scheduled_at = scheduled_at
        if comparable_scheduled_at.tzinfo is None:
            comparable_scheduled_at = comparable_scheduled_at.replace(tzinfo=timezone.utc)
        if comparable_scheduled_at > current_time:
            return "scheduled"

    channel = str(row.get("channel") or "").strip().lower()
    if channel in {"max", "whatsapp", "manual"} or touch_status in {"manual", "awaiting_manual_send"}:
        return "awaiting_manual_send"
    if campaign_status in {"approved", "active"} or touch_status in {"approved", "scheduled"}:
        return "scheduled"
    return touch_status or "draft"


@outreach_campaign_bp.get("/api/outreach/messages")
def get_outreach_message_queue():
    """Return current-version outreach touches as an operational message queue."""
    user_data, error = _require_auth()
    if error:
        return error

    requested_workstream_type = str(request.args.get("workstream_type") or "").strip().lower()
    if requested_workstream_type not in {"", "localos_sales", "client_partnership"}:
        return jsonify({"success": False, "error": "Unsupported workstream_type"}), 400
    requested_business_id = str(request.args.get("business_id") or "").strip() or None
    requested_channel = str(request.args.get("channel") or "").strip().lower()
    requested_status = str(request.args.get("status") or "").strip().lower()
    search_query = str(request.args.get("q") or "").strip()
    try:
        limit = max(1, min(int(request.args.get("limit") or 100), 500))
        offset = max(0, int(request.args.get("offset") or 0))
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "limit and offset must be integers"}), 400

    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        is_superadmin = bool(user_data.get("is_superadmin"))
        resolved_business_id = None
        if requested_business_id or not is_superadmin:
            resolved_business_id = _resolve_business_for_user(cursor, user_data, requested_business_id)
            if not resolved_business_id:
                return jsonify({"success": False, "error": "Business access denied"}), 403
        if not is_superadmin and requested_workstream_type == "localos_sales":
            return jsonify({"success": False, "error": "Platform outreach access denied"}), 403

        where_clauses = ["ranked.campaign_rank = 1"]
        params: list[Any] = []
        if requested_workstream_type:
            where_clauses.append("ranked.workstream_type = %s")
            params.append(requested_workstream_type)
        elif not is_superadmin:
            where_clauses.append("ranked.workstream_type = 'client_partnership'")
        if resolved_business_id:
            where_clauses.append("ranked.client_business_id = %s")
            params.append(resolved_business_id)
        if requested_channel:
            where_clauses.append("touch.channel = %s")
            params.append(requested_channel)
        if search_query:
            where_clauses.append(
                "(lead.name ILIKE %s OR COALESCE(contact.value, '') ILIKE %s OR COALESCE(touch.subject, '') ILIKE %s OR COALESCE(touch.approved_text, touch.generated_text, '') ILIKE %s)"
            )
            search_pattern = f"%{search_query}%"
            params.extend([search_pattern, search_pattern, search_pattern, search_pattern])

        cursor.execute(
            f"""
            WITH ranked_campaigns AS (
                SELECT campaign.*,
                       workstream.workstream_type,
                       workstream.client_business_id,
                       ROW_NUMBER() OVER (
                           PARTITION BY campaign.workstream_id
                           ORDER BY campaign.version DESC, campaign.created_at DESC
                       ) AS campaign_rank
                FROM outreach_campaigns campaign
                JOIN lead_workstreams workstream ON workstream.id = campaign.workstream_id
            )
            SELECT
                touch.id AS touch_id,
                touch.sequence_index,
                touch.channel,
                touch.status AS touch_status,
                touch.scheduled_at,
                touch.subject,
                COALESCE(touch.approved_text, touch.generated_text, '') AS message_text,
                ranked.id AS campaign_id,
                ranked.version AS campaign_version,
                ranked.status AS campaign_status,
                ranked.workstream_id,
                ranked.workstream_type,
                ranked.client_business_id,
                lead.id AS lead_id,
                lead.name AS lead_name,
                lead.category AS lead_category,
                business.name AS client_business_name,
                contact.value AS recipient,
                contact.contact_type AS recipient_type,
                sender.sender_identity,
                sender.display_name AS sender_display_name,
                delivery.id AS delivery_id,
                delivery.delivery_status,
                delivery.provider_message_id,
                delivery.error_text,
                delivery.sent_at,
                delivery.updated_at AS delivery_updated_at,
                reply.id AS reply_event_id,
                reply.is_human AS reply_is_human,
                reply.classification AS reply_classification,
                reply.raw_payload_json AS reply_payload_json,
                reply.occurred_at AS replied_at,
                receipt.event_type AS receipt_event_type,
                receipt.occurred_at AS receipt_at
            FROM ranked_campaigns ranked
            JOIN outreach_campaign_touches touch ON touch.campaign_id = ranked.id
            JOIN prospectingleads lead ON lead.id = ranked.lead_id
            LEFT JOIN businesses business ON business.id = ranked.client_business_id
            LEFT JOIN lead_contact_points contact ON contact.id = touch.contact_point_id
            LEFT JOIN outreach_sender_accounts sender ON sender.id = touch.sender_account_id
            LEFT JOIN LATERAL (
                SELECT queue.id, queue.delivery_status, queue.provider_message_id,
                       queue.error_text, queue.sent_at, queue.updated_at
                FROM outreachsendqueue queue
                WHERE queue.campaign_touch_id = touch.id
                ORDER BY queue.created_at DESC
                LIMIT 1
            ) delivery ON TRUE
            LEFT JOIN LATERAL (
                SELECT inbound.id, inbound.is_human, inbound.classification,
                       inbound.raw_payload_json, inbound.occurred_at
                FROM outreach_inbound_events inbound
                WHERE inbound.touch_id = touch.id
                  AND inbound.is_human = TRUE
                ORDER BY inbound.occurred_at DESC, inbound.created_at DESC
                LIMIT 1
            ) reply ON TRUE
            LEFT JOIN LATERAL (
                SELECT inbound.event_type, inbound.occurred_at
                FROM outreach_inbound_events inbound
                WHERE inbound.touch_id = touch.id
                  AND LOWER(inbound.event_type) IN ('read', 'read_receipt', 'opened', 'message_read')
                ORDER BY inbound.occurred_at DESC, inbound.created_at DESC
                LIMIT 1
            ) receipt ON TRUE
            WHERE {' AND '.join(where_clauses)}
            ORDER BY COALESCE(delivery.sent_at, touch.scheduled_at, touch.updated_at) DESC
            LIMIT 5000
            """,
            tuple(params),
        )
        raw_items = [dict(row) for row in cursor.fetchall()]
        items = []
        summary: dict[str, int] = {"all": 0}
        for item in raw_items:
            item["status"] = _message_queue_status(item)
            summary["all"] += 1
            summary[item["status"]] = summary.get(item["status"], 0) + 1
            if requested_status and item["status"] != requested_status:
                continue
            items.append(item)
        total = len(items)
        return jsonify({
            "success": True,
            "items": items[offset:offset + limit],
            "total": total,
            "offset": offset,
            "limit": limit,
            "summary": summary,
        })
    finally:
        conn.close()


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


@outreach_campaign_bp.post("/api/outreach/sender-accounts/max/manual")
def connect_manual_max_sender_account():
    user_data, error = _require_auth()
    if error:
        return error
    payload = request.get_json(silent=True) or {}
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
        sender = connect_manual_max_sender(
            cursor,
            scope_type=scope[0],
            business_id=scope[1],
            owner_user_id=str(user_data.get("user_id") or "") or None,
            phone=payload.get("phone"),
            display_name=str(payload.get("display_name") or "").strip() or None,
        )
        conn.commit()
        return jsonify({
            "success": True,
            "sender_account": sender,
            "message": (
                "MAX добавлен в ручном режиме. LocalOS подготовит текст, "
                "а отправку и ответ нужно отметить вручную."
            ),
            "messages_sent": 0,
        }), 201
    except ValueError as exc:
        conn.rollback()
        return jsonify({
            "success": False,
            "error": str(exc),
            "reason_code": "max_manual_connect_failed",
            "messages_sent": 0,
        }), 422
    finally:
        conn.close()


@outreach_campaign_bp.post("/api/outreach/sender-accounts/vk/oauth/start")
def start_vk_outreach_oauth():
    user_data, error = _require_auth()
    if error:
        return error
    payload = request.get_json(silent=True) or {}
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
        code_challenge = validate_vk_pkce_value(payload.get("code_challenge"), "code_challenge")
        client_state = str(payload.get("client_state") or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{20,160}", client_state):
            return jsonify({"success": False, "error": "Не удалось начать безопасное подключение VK."}), 400
        return_to = "/dashboard/settings/integrations?focus=outreach_vk"
        if scope[0] == "platform":
            return_to += "&sender_scope=platform"
        state = encode_vk_oauth_state({
            "purpose": "outreach_sender",
            "user_id": str(user_data.get("user_id") or ""),
            "scope_type": scope[0],
            "business_id": scope[1],
            "code_challenge": code_challenge,
            "client_state": client_state,
            "return_to": return_to,
        })
        return jsonify({
            "success": True,
            "auth_url": build_vk_authorization_url(
                state=state,
                code_challenge=code_challenge,
                scopes=VK_OUTREACH_SCOPES,
            ),
            "messages_sent": 0,
        })
    except (VkOAuthError, ValueError) as exc:
        return jsonify({
            "success": False,
            "error": str(exc),
            "reason_code": getattr(exc, "code", "vk_oauth_start_failed"),
            "messages_sent": 0,
        }), 422
    finally:
        conn.close()


@outreach_campaign_bp.post("/api/outreach/sender-accounts/vk/community/connect")
def connect_vk_outreach_community():
    user_data, error = _require_auth()
    if error:
        return error
    payload = request.get_json(silent=True) or {}
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
        sender = connect_vk_community_sender(
            cursor,
            scope_type=scope[0],
            business_id=scope[1],
            owner_user_id=str(user_data.get("user_id") or "") or None,
            community_reference=str(payload.get("community_url") or payload.get("community_id") or ""),
            access_token=str(payload.get("access_token") or ""),
        )
        conn.commit()
        return jsonify({
            "success": True,
            "sender_account": sender,
            "message": "Сообщество VK подключено без права отправки. Получатель увидит фактическое имя сообщества.",
            "messages_sent": 0,
        }), 201
    except (VkOutreachAdapterError, ValueError) as exc:
        conn.rollback()
        return jsonify({
            "success": False,
            "error": str(exc),
            "reason_code": getattr(exc, "code", "vk_community_connect_failed"),
            "messages_sent": 0,
        }), 422
    finally:
        conn.close()


@outreach_campaign_bp.post("/api/outreach/sender-accounts/vk/oauth/complete")
def complete_vk_outreach_oauth():
    user_data, error = _require_auth()
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        state_payload = decode_vk_oauth_state(payload.get("state"))
        if str(state_payload.get("purpose") or "") != "outreach_sender":
            return jsonify({"success": False, "error": "Это подключение VK предназначено для другой функции."}), 409
        if str(state_payload.get("user_id") or "") != str(user_data.get("user_id") or ""):
            return jsonify({"success": False, "error": "Это подключение VK относится к другому пользователю."}), 403
        scope = _sender_scope(
            cursor,
            user_data,
            scope_type=str(state_payload.get("scope_type") or "business"),
            requested_business_id=str(state_payload.get("business_id") or "").strip() or None,
        )
        if not scope or scope[0] != state_payload.get("scope_type") or scope[1] != state_payload.get("business_id"):
            return jsonify({"success": False, "error": "Контур VK-подключения изменился. Начните ещё раз."}), 403
        code_verifier = validate_vk_pkce_value(payload.get("code_verifier"), "code_verifier")
        if not hmac.compare_digest(
            vk_pkce_challenge(code_verifier),
            str(state_payload.get("code_challenge") or ""),
        ):
            return jsonify({"success": False, "error": "Не удалось проверить подключение VK. Начните ещё раз."}), 400
        token_payload = exchange_vk_authorization_code(
            code=str(payload.get("code") or ""),
            device_id=str(payload.get("device_id") or ""),
            code_verifier=code_verifier,
        )
        verification = verify_vk_outreach_access(str(token_payload.get("access_token") or ""))
        sender = connect_vk_sender(
            cursor,
            scope_type=scope[0],
            business_id=scope[1],
            owner_user_id=str(user_data.get("user_id") or "") or None,
            token_payload=token_payload,
            device_id=str(payload.get("device_id") or ""),
            verification=verification,
        )
        conn.commit()
        return jsonify({
            "success": True,
            "sender_account": sender,
            "message": "VK подключён без права отправки. Разрешение включается отдельно.",
            "messages_sent": 0,
        }), 201
    except (VkOAuthError, VkOutreachAdapterError, ValueError) as exc:
        conn.rollback()
        return jsonify({
            "success": False,
            "error": str(exc),
            "reason_code": getattr(exc, "code", "vk_oauth_complete_failed"),
            "messages_sent": 0,
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
        if sender.get("channel") not in {"email", "vk"}:
            return jsonify({"success": False, "error": "Channel preflight is not available here"}), 409
        if sender.get("channel") == "vk":
            result = preflight_vk_sender_account(
                cursor,
                sender_account_id,
                actor_id=str(user_data.get("user_id") or "") or None,
            )
        else:
            result = preflight_email_sender(
                cursor,
                sender_account_id,
                actor_id=str(user_data.get("user_id") or "") or None,
            )
        conn.commit()
        return jsonify({"success": True, "preflight": result, "messages_sent": 0})
    except (LookupError, ValueError, EmailAdapterError, VkOutreachAdapterError) as exc:
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
    if "touch_overrides" in payload and not isinstance(payload.get("touch_overrides"), list):
        return jsonify({"error": "touch_overrides must be a list"}), 400
    touch_overrides = (
        payload.get("touch_overrides")
        if isinstance(payload.get("touch_overrides"), list)
        else None
    )
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        workstream = _authorized_workstream(cursor, workstream_id, user_data)
        if not workstream:
            return jsonify({"success": False, "error": "Workstream not found or access denied"}), 404
        sender_mode = _authorized_sender_mode(workstream, payload.get("sender_mode"), user_data)
        preview = build_preview(
            cursor,
            workstream_id,
            sequence=sequence,
            touch_overrides=touch_overrides,
            start_at=_parse_campaign_start_at(payload.get("start_at")),
            sender_mode=sender_mode,
            offer_id=str(payload.get("offer_id") or "").strip() or None,
            trust_strategy=str(payload.get("trust_strategy") or "").strip() or None,
            manual_reviewer_role=(
                "superadmin" if user_data.get("is_superadmin") else "business_user"
            ),
        )
        campaign = None
        if bool(payload.get("save")) and preview.get("status") in {"ready", "needs_channel_setup", "needs_evidence", "needs_revision"}:
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
    except PermissionError as exc:
        conn.rollback()
        return jsonify({"success": False, "error": str(exc), "reason_code": "sender_mode_forbidden"}), 403
    finally:
        conn.close()


@outreach_campaign_bp.get("/api/outreach/sandbox/workstreams")
def list_outreach_sandbox_workstreams():
    user_data, error = _require_auth()
    if error:
        return error
    if not _outreach_sandbox_enabled():
        return jsonify({"success": False, "error": "Outreach sandbox is disabled"}), 404
    requested_business_id = str(request.args.get("business_id") or "").strip()
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        if user_data.get("is_superadmin"):
            if requested_business_id:
                cursor.execute(
                    """
                    SELECT ws.id, ws.lead_id, ws.workstream_type, ws.client_business_id,
                           ws.lifecycle_status, lead.name AS lead_name,
                           business.name AS business_name
                    FROM lead_workstreams ws
                    JOIN prospectingleads lead ON lead.id = ws.lead_id
                    LEFT JOIN businesses business ON business.id = ws.client_business_id
                    WHERE ws.client_business_id = %s
                    ORDER BY ws.updated_at DESC
                    LIMIT 250
                    """,
                    (requested_business_id,),
                )
            else:
                cursor.execute(
                    """
                    SELECT ws.id, ws.lead_id, ws.workstream_type, ws.client_business_id,
                           ws.lifecycle_status, lead.name AS lead_name,
                           business.name AS business_name
                    FROM lead_workstreams ws
                    JOIN prospectingleads lead ON lead.id = ws.lead_id
                    LEFT JOIN businesses business ON business.id = ws.client_business_id
                    ORDER BY ws.updated_at DESC
                    LIMIT 250
                    """
                )
        else:
            business_id = _resolve_business_for_user(cursor, user_data, requested_business_id or None)
            if not business_id:
                return jsonify({"success": False, "error": "Business access denied"}), 403
            cursor.execute(
                """
                SELECT ws.id, ws.lead_id, ws.workstream_type, ws.client_business_id,
                       ws.lifecycle_status, lead.name AS lead_name,
                       business.name AS business_name
                FROM lead_workstreams ws
                JOIN prospectingleads lead ON lead.id = ws.lead_id
                LEFT JOIN businesses business ON business.id = ws.client_business_id
                WHERE ws.workstream_type = 'client_partnership'
                  AND ws.client_business_id = %s
                ORDER BY ws.updated_at DESC
                LIMIT 250
                """,
                (business_id,),
            )
        workstreams = []
        for row in cursor.fetchall():
            item = dict(row)
            if item.get("workstream_type") == "localos_sales":
                item["allowed_sender_modes"] = ["localos"]
            elif user_data.get("is_superadmin"):
                item["allowed_sender_modes"] = ["partner_business", "localos_for_partner"]
            else:
                item["allowed_sender_modes"] = ["partner_business"]
            workstreams.append(item)
        return jsonify({"success": True, "workstreams": workstreams})
    finally:
        conn.rollback()
        conn.close()


@outreach_campaign_bp.post("/api/outreach/sandbox/preview")
def outreach_sandbox_preview():
    user_data, error = _require_auth()
    if error:
        return error
    if not _outreach_sandbox_enabled():
        return jsonify({"success": False, "error": "Outreach sandbox is disabled"}), 404
    payload = request.get_json(silent=True) or {}
    workstream_id = str(payload.get("workstream_id") or "").strip()
    if not workstream_id:
        return jsonify({"success": False, "error": "workstream_id is required"}), 400
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        workstream = _authorized_workstream(cursor, workstream_id, user_data)
        if not workstream:
            return jsonify({"success": False, "error": "Workstream not found or access denied"}), 404
        sender_mode = _authorized_sender_mode(workstream, payload.get("sender_mode"), user_data)
        preview = build_preview(
            cursor,
            workstream_id,
            sequence=payload.get("sequence") if isinstance(payload.get("sequence"), list) else None,
            sender_mode=sender_mode,
            offer_id=str(payload.get("offer_id") or "").strip() or None,
            trust_strategy=str(payload.get("trust_strategy") or "").strip() or None,
            generate_ai=False,
        )
        return jsonify({
            "success": True,
            "dry_run": True,
            "external_dispatch_performed": False,
            "preview": preview,
            "room_preview": _room_preview_for_outreach(preview),
        })
    except (LookupError, ValueError) as exc:
        return jsonify({"success": False, "error": str(exc), "reason_code": "sandbox_preview_blocked"}), 422
    except PermissionError as exc:
        return jsonify({"success": False, "error": str(exc), "reason_code": "sender_mode_forbidden"}), 403
    finally:
        conn.rollback()
        conn.close()


@outreach_campaign_bp.post("/api/outreach/sandbox/simulate-reply")
def outreach_sandbox_simulate_reply():
    user_data, error = _require_auth()
    if error:
        return error
    if not _outreach_sandbox_enabled():
        return jsonify({"success": False, "error": "Outreach sandbox is disabled"}), 404
    payload = request.get_json(silent=True) or {}
    workstream_id = str(payload.get("workstream_id") or "").strip()
    raw_reply = str(payload.get("reply") or payload.get("raw_reply") or "").strip()
    if not workstream_id or not raw_reply:
        return jsonify({"success": False, "error": "workstream_id and reply are required"}), 400
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        workstream = _authorized_workstream(cursor, workstream_id, user_data)
        if not workstream:
            return jsonify({"success": False, "error": "Workstream not found or access denied"}), 404
        sender_mode = _authorized_sender_mode(workstream, payload.get("sender_mode"), user_data)
        preview = build_preview(
            cursor,
            workstream_id,
            sender_mode=sender_mode,
            offer_id=str(payload.get("offer_id") or "").strip() or None,
            trust_strategy=str(payload.get("trust_strategy") or "").strip() or None,
            generate_ai=False,
        )
        classification = classify_inbound_event({"raw_reply": raw_reply})
        relationship_delta = build_relationship_delta(raw_reply, classification["classification"])
        room_preview = _room_preview_for_outreach(preview)
        if classification.get("classification") in {"interested", "question"}:
            room_preview["status"] = "engaged"
            room_preview["visibility"] = "ready_to_share"
            room_preview["next_step"] = "Проверить приглашение в комнату"
            room_preview["invitation_draft"] = {
                "status": "draft",
                "approval_required": True,
                "text": "Спасибо за ответ. Подготовил приватную комнату с идеей, основаниями matching и следующим шагом.",
            }
        return jsonify({
            "success": True,
            "dry_run": True,
            "external_dispatch_performed": False,
            "production_records_created": 0,
            "classification": classification,
            "future_touches_stopped": bool(classification.get("stops_campaign")),
            "relationship_memory_preview": relationship_delta,
            "decision": preview.get("decision") or {},
            "room_preview": room_preview,
        })
    except (LookupError, ValueError) as exc:
        return jsonify({"success": False, "error": str(exc), "reason_code": "sandbox_reply_blocked"}), 422
    except PermissionError as exc:
        return jsonify({"success": False, "error": str(exc), "reason_code": "sender_mode_forbidden"}), 403
    finally:
        conn.rollback()
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


@outreach_campaign_bp.patch("/api/outreach/campaigns/<campaign_id>/touches/<touch_id>")
def update_campaign_touch(campaign_id: str, touch_id: str):
    user_data, error = _require_auth()
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        if not _authorized_campaign(cursor, campaign_id, user_data):
            return jsonify({"success": False, "error": "Campaign not found or access denied"}), 404
        touch = update_draft_campaign_touch(
            cursor,
            campaign_id=campaign_id,
            touch_id=touch_id,
            subject=payload.get("subject"),
            generated_text=str(payload.get("text") or ""),
            user_id=str(user_data.get("user_id") or ""),
        )
        conn.commit()
        return jsonify({
            "success": True,
            "touch": touch,
            "campaign": _campaign_payload(cursor, campaign_id),
            "campaign_version_unchanged": True,
            "quality_review_required": True,
            "external_dispatch_performed": False,
        })
    except LookupError as exc:
        conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    except ValueError as exc:
        conn.rollback()
        return jsonify({"success": False, "error": str(exc), "reason_code": "touch_edit_blocked"}), 409
    finally:
        conn.close()


@outreach_campaign_bp.post("/api/outreach/campaigns/<campaign_id>/review-edits")
def review_campaign_touch_edits(campaign_id: str):
    user_data, error = _require_auth()
    if error:
        return error
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        authorized = _authorized_campaign(cursor, campaign_id, user_data)
        if not authorized:
            return jsonify({"success": False, "error": "Campaign not found or access denied"}), 404
        campaign = _campaign_payload(cursor, campaign_id)
        if not campaign:
            return jsonify({"success": False, "error": "Campaign not found"}), 404
        if campaign.get("status") not in {"draft", "paused"}:
            return jsonify({"success": False, "error": "Only a draft or paused campaign can be reviewed"}), 409

        touches = list(campaign.get("touches") or [])
        if not touches:
            return jsonify({"success": False, "error": "Campaign has no messages to review"}), 409
        scheduled_values = [
            touch.get("scheduled_at")
            for touch in touches
            if isinstance(touch.get("scheduled_at"), datetime)
        ]
        start_at = min(scheduled_values) if scheduled_values else datetime.now(timezone.utc)
        sequence = []
        overrides = []
        for touch in touches:
            scheduled_at = touch.get("scheduled_at")
            day_offset = (
                max(0, round((scheduled_at - start_at).total_seconds() / 86_400))
                if isinstance(scheduled_at, datetime)
                else int(touch.get("sequence_index") or 0) * 3
            )
            brief = touch.get("message_brief_json") if isinstance(touch.get("message_brief_json"), dict) else {}
            sequence.append({
                "channel": str(touch.get("channel") or "manual"),
                "day_offset": day_offset,
                "angle": str(touch.get("angle_type") or "proof"),
                "sender_account_id": str(touch.get("sender_account_id") or "") or None,
            })
            overrides.append({
                "sequence_index": int(touch.get("sequence_index") or 0),
                "subject": str(touch.get("subject") or ""),
                "text": str(touch.get("generated_text") or ""),
                "original_subject": str(brief.get("original_generated_subject") or ""),
                "original_text": str(brief.get("original_generated_text") or ""),
                "human_edited": bool(brief.get("human_edited")),
            })

        preview = build_preview(
            cursor,
            str(campaign.get("workstream_id") or authorized.get("workstream_id") or ""),
            sequence=sequence,
            touch_overrides=overrides,
            start_at=start_at,
            sender_mode=str(campaign.get("sender_mode") or "") or None,
            generate_ai=False,
            manual_reviewer_role=(
                "superadmin" if user_data.get("is_superadmin") else "business_user"
            ),
        )
        reviewed_touches = [
            {
                "sequence_index": int(touch.get("sequence_index") or 0),
                "subject": touch.get("subject"),
                "text": touch.get("text"),
                "quality_gate": touch.get("quality_gate") or {},
            }
            for touch in preview.get("touches") or []
        ]
        review = apply_draft_campaign_review(
            cursor,
            campaign_id=campaign_id,
            reviewed_touches=reviewed_touches,
            user_id=str(user_data.get("user_id") or ""),
        )
        conn.commit()
        return jsonify({
            "success": True,
            "review": review,
            "preview": preview,
            "campaign": _campaign_payload(cursor, campaign_id),
            "campaign_version_unchanged": True,
            "external_dispatch_performed": False,
        })
    except LookupError as exc:
        conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    except ValueError as exc:
        conn.rollback()
        return jsonify({"success": False, "error": str(exc), "reason_code": "touch_review_blocked"}), 409
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


@outreach_campaign_bp.post("/api/outreach/campaigns/<campaign_id>/room-invitation/approve")
def approve_campaign_room_invitation(campaign_id: str):
    """Explicitly publish an already prepared room invitation; it does not send it."""
    user_data, error = _require_auth()
    if error:
        return error
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        if not _authorized_campaign(cursor, campaign_id, user_data):
            return jsonify({"success": False, "error": "Campaign not found or access denied"}), 404
        room = approve_room_invitation(
            cursor,
            campaign_id=campaign_id,
            actor_id=str(user_data.get("user_id") or ""),
        )
        conn.commit()
        return jsonify({
            "success": True,
            "room": room,
            "invitation_sent": False,
            "external_dispatch_performed": False,
        })
    except (LookupError, ValueError) as exc:
        conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 409
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
            and first_touch.get("channel") in {"telegram", "email", "vk"}
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
        if first_touch.get("channel") not in {"telegram", "email", "vk"}:
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
    from services.outreach_vk_reply_service import sync_vk_replies

    if first_touch.get("channel") == "telegram":
        reply_sync = _sync_telegram_app_replies(
            limit=50,
            sender_account_id=sender_account_id,
        )
    elif first_touch.get("channel") == "email":
        reply_sync = sync_email_replies(
            sender_limit=1,
            per_sender_limit=100,
            sender_account_id=sender_account_id,
        )
    else:
        reply_sync = sync_vk_replies(
            sender_limit=1,
            per_conversation_limit=50,
            sender_account_id=sender_account_id,
            campaign_id=campaign_id,
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
        if channel not in {"telegram", "email", "vk"}:
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
    elif channel == "email":
        from services.outreach_email_reply_service import sync_email_replies

        sync_result = sync_email_replies(
            sender_limit=1,
            per_sender_limit=100,
            sender_account_id=sender_account_id,
            campaign_id=campaign_id,
        )
    else:
        from services.outreach_vk_reply_service import sync_vk_replies

        sync_result = sync_vk_replies(
            sender_limit=1,
            per_conversation_limit=50,
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


@outreach_campaign_bp.get("/api/outreach/experiments")
def get_outreach_experiments():
    """Return staged tests inside the existing outreach results workflow."""
    user_data, error = _require_auth()
    if error:
        return error
    if not user_data.get("is_superadmin"):
        return jsonify({"success": False, "error": "Access denied"}), 403
    if not experiments_enabled():
        return jsonify({"success": True, "enabled": False, "experiments": []})
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        return jsonify({"success": True, "enabled": True, "experiments": list_experiments(cursor)})
    finally:
        conn.close()


@outreach_campaign_bp.post("/api/outreach/experiments")
def create_outreach_experiment():
    user_data, error = _require_auth()
    if error:
        return error
    if not user_data.get("is_superadmin"):
        return jsonify({"success": False, "error": "Access denied"}), 403
    if not experiments_enabled():
        return jsonify({"success": False, "error": "Outreach experiments are disabled"}), 409
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        experiment = create_beauty_experiment(cursor, user_id=str(user_data.get("user_id") or "") or None)
        conn.commit()
        return jsonify({"success": True, "experiment": experiment}), 201
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@outreach_campaign_bp.post("/api/outreach/experiments/<experiment_id>/dry-run")
def dry_run_outreach_experiment(experiment_id: str):
    user_data, error = _require_auth()
    if error:
        return error
    if not user_data.get("is_superadmin"):
        return jsonify({"success": False, "error": "Access denied"}), 403
    if not experiments_enabled():
        return jsonify({"success": False, "error": "Outreach experiments are disabled"}), 409
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        result = select_stage_candidates(cursor, experiment_id)
        return jsonify({"success": True, "dry_run": True, "external_dispatch_performed": False, **result})
    except LookupError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    finally:
        conn.close()


@outreach_campaign_bp.post("/api/outreach/experiments/<experiment_id>/prepare-drafts")
def prepare_outreach_experiment_drafts(experiment_id: str):
    """Persist only draft campaigns for the current explicit stage."""
    user_data, error = _require_auth()
    if error:
        return error
    if not user_data.get("is_superadmin"):
        return jsonify({"success": False, "error": "Access denied"}), 403
    if not experiments_enabled():
        return jsonify({"success": False, "error": "Outreach experiments are disabled"}), 409
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        selection = select_stage_candidates(cursor, experiment_id)
        cursor.execute(
            """
            SELECT * FROM outreach_knowledge_patterns
            WHERE pattern_key = %s AND status = 'approved'
            ORDER BY version DESC LIMIT 1
            """,
            (ACTIVE_SOCIAL_MAP_GAP,),
        )
        pattern = dict(cursor.fetchone() or {})
        if selection["stage"]["variant"] == "treatment" and not pattern:
            return jsonify({"success": False, "error": "Approved corpus pattern is required"}), 409
        prepared = []
        skipped = []
        sequence = [
            {"channel": "email", "day_offset": 0, "angle": "signal"},
            {"channel": "email", "day_offset": 3, "angle": "founder_story"},
            {"channel": "email", "day_offset": 7, "angle": "proof"},
            {"channel": "email", "day_offset": 12, "angle": "respectful_close"},
        ]
        for candidate in selection["candidates"]:
            preview = build_preview(cursor, candidate["workstream_id"], sequence=sequence, sender_mode="localos")
            if preview.get("status") not in {"ready", "needs_channel_setup", "needs_revision", "needs_evidence"} or not preview.get("touches"):
                skipped.append({"workstream_id": candidate["workstream_id"], "reason": preview.get("status")})
                continue
            for touch in preview["touches"]:
                strategy = dict(touch.get("strategy") or {})
                strategy.update({
                    "experiment_id": experiment_id,
                    "cohort": candidate["cohort"],
                    "variant": candidate["variant"],
                    "pattern_id": str(pattern.get("id") or "") or None,
                    "pattern_version": pattern.get("version"),
                    "signal_combo": ACTIVE_SOCIAL_MAP_GAP if candidate["variant"] == "treatment" else "map_gap_control",
                })
                touch["strategy"] = strategy
                touch["strategy_fingerprint"] = strategy_fingerprint(strategy)
            campaign = persist_preview(cursor, preview, user_id=str(user_data.get("user_id") or ""))
            assign_experiment_member(
                cursor,
                experiment_id=experiment_id,
                workstream_id=candidate["workstream_id"],
                campaign_id=campaign["id"],
                cohort=candidate["cohort"],
                variant=candidate["variant"],
                pattern=pattern or None,
            )
            cursor.execute(
                """
                UPDATE outreach_campaigns
                SET policy_json = policy_json || %s::jsonb, updated_at = NOW()
                WHERE id = %s
                """,
                (Json({
                    "experiment_id": experiment_id,
                    "cohort": candidate["cohort"],
                    "variant": candidate["variant"],
                    "automatic_stage_advancement": False,
                    "automatic_dispatch": False,
                }), campaign["id"]),
            )
            prepared.append(campaign)
        conn.commit()
        return jsonify({
            "success": True,
            "status": "drafts_prepared",
            "prepared": prepared,
            "skipped": skipped,
            "approval_required": True,
            "external_dispatch_performed": False,
        })
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@outreach_campaign_bp.post("/api/outreach/experiments/<experiment_id>/advance")
def advance_outreach_experiment(experiment_id: str):
    """Advance only after every current-stage draft has been human reviewed."""
    user_data, error = _require_auth()
    if error:
        return error
    if not user_data.get("is_superadmin"):
        return jsonify({"success": False, "error": "Access denied"}), 403
    if not experiments_enabled():
        return jsonify({"success": False, "error": "Outreach experiments are disabled"}), 409
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM outreach_experiments WHERE id = %s FOR UPDATE", (experiment_id,))
        experiment = dict(cursor.fetchone() or {})
        if not experiment:
            return jsonify({"success": False, "error": "Experiment not found"}), 404
        cursor.execute(
            """
            SELECT COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE campaign.status IN ('approved', 'active', 'completed')) AS reviewed
            FROM outreach_experiment_members member
            JOIN outreach_campaigns campaign ON campaign.id = member.campaign_id
            WHERE member.experiment_id = %s AND member.cohort = %s
            """,
            (experiment_id, experiment["current_stage"]),
        )
        counts = dict(cursor.fetchone() or {})
        if not counts.get("total") or int(counts.get("reviewed") or 0) != int(counts.get("total") or 0):
            return jsonify({"success": False, "error": "Current stage still requires human review"}), 409
        following = next_stage(str(experiment["current_stage"]))
        if not following:
            cursor.execute("UPDATE outreach_experiments SET status = 'completed', updated_at = NOW() WHERE id = %s", (experiment_id,))
        else:
            cursor.execute("UPDATE outreach_experiments SET current_stage = %s, status = 'active', updated_at = NOW() WHERE id = %s", (following, experiment_id))
        conn.commit()
        return jsonify({"success": True, "current_stage": following, "external_dispatch_performed": False})
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@outreach_campaign_bp.get("/api/outreach/knowledge-patterns")
def get_outreach_knowledge_patterns():
    user_data, error = _require_auth()
    if error:
        return error
    if not user_data.get("is_superadmin"):
        return jsonify({"success": False, "error": "Access denied"}), 403
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM outreach_knowledge_patterns ORDER BY pattern_key, version DESC")
        return jsonify({"success": True, "enabled": corpus_patterns_enabled(), "patterns": [dict(row) for row in cursor.fetchall()]})
    finally:
        conn.close()


@outreach_campaign_bp.post("/api/outreach/knowledge-patterns/compile")
def compile_outreach_knowledge_pattern():
    user_data, error = _require_auth()
    if error:
        return error
    if not user_data.get("is_superadmin"):
        return jsonify({"success": False, "error": "Access denied"}), 403
    if not corpus_patterns_enabled():
        return jsonify({"success": False, "error": "Corpus patterns are disabled"}), 409
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT document.id, document.content_text AS content,
                   document.permalink AS source_url, source.id AS source_id,
                   source.title AS channel, document.published_at
            FROM knowledge_documents document
            JOIN knowledge_sources source ON source.id = document.source_id
            WHERE document.metadata_json->>'corpus_tag' = 'telegram_b2b'
              AND document.invalidated_at IS NULL
              AND document.content_text ~* '(карт|отзыв|соцсет|telegram|контент|персонализ)'
            ORDER BY document.published_at DESC
            LIMIT 200
            """
        )
        documents = [dict(row) for row in cursor.fetchall()]
        compiler_result = extract_and_review_corpus_pattern(
            documents,
            user_id=str(user_data.get("user_id") or ""),
        )
        pattern = compile_pattern_draft(
            cursor,
            documents,
            user_id=str(user_data.get("user_id") or ""),
            compiler_result=compiler_result,
        )
        conn.commit()
        return jsonify({"success": True, "pattern": pattern, "approval_required": True}), 201
    except ValueError as exc:
        conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 409
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@outreach_campaign_bp.post("/api/outreach/knowledge-patterns/<pattern_id>/approve")
def approve_outreach_knowledge_pattern(pattern_id: str):
    user_data, error = _require_auth()
    if error:
        return error
    if not user_data.get("is_superadmin"):
        return jsonify({"success": False, "error": "Access denied"}), 403
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            UPDATE outreach_knowledge_patterns
            SET status = 'approved', reviewed_by = %s, approved_at = NOW(), updated_at = NOW()
            WHERE id = %s AND status = 'draft'
              AND support_document_count >= 3 AND support_source_count >= 2
            RETURNING id, pattern_key, version, status
            """,
            (str(user_data.get("user_id") or "") or None, pattern_id),
        )
        pattern = cursor.fetchone()
        if not pattern:
            conn.rollback()
            return jsonify({"success": False, "error": "Pattern is not ready for approval"}), 409
        conn.commit()
        return jsonify({"success": True, "pattern": dict(pattern)})
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
        sender_mode = _authorized_sender_mode(
            workstream,
            dimensions.get("sender_mode"),
            user_data,
        )
        preview = build_preview(
            cursor,
            workstream_id,
            sequence=sequence,
            sender_mode=sender_mode,
        )
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
    except PermissionError as exc:
        conn.rollback()
        return jsonify({"success": False, "error": str(exc), "reason_code": "sender_mode_forbidden"}), 403
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
