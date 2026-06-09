from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, Callable, Dict

from database_manager import DatabaseManager
from services.operator_credit_reservation import finalize_reserved_action_credits, reserve_paid_action_credits
from services.outreach_send_capability import (
    OUTREACH_SEND_BATCH_CAPABILITY,
    handle_outreach_send_batch,
)


CapabilityHandler = Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]


CANONICAL_CAPABILITIES: Dict[str, Dict[str, Any]] = {
    "outreach.send_batch": {
        "risk": "external_send",
        "side_effects": "queues approved outreach records inside LocalOS",
        "approval_required": True,
    },
    "reviews.reply.draft": {
        "risk": "draft",
        "side_effects": "none",
        "approval_required": False,
    },
    "reviews.reply.publish_request": {
        "risk": "external_publish_request",
        "side_effects": "creates a publish request only",
        "approval_required": True,
    },
    "services.optimize": {
        "risk": "draft_or_apply_request",
        "side_effects": "none unless later approved by a dedicated apply flow",
        "approval_required": False,
    },
    "news.generate": {
        "risk": "draft",
        "side_effects": "none",
        "approval_required": False,
    },
    "appointments.read": {
        "risk": "read",
        "side_effects": "none",
        "approval_required": False,
    },
    "appointments.create_request": {
        "risk": "booking_request",
        "side_effects": "creates a LocalOS request only",
        "approval_required": True,
    },
    "communications.draft": {
        "risk": "draft",
        "side_effects": "none",
        "approval_required": False,
    },
    "communications.send_reminder": {
        "risk": "external_send_request",
        "side_effects": "creates a reminder send request only",
        "approval_required": True,
    },
    "communications.send_offer": {
        "risk": "external_send_request",
        "side_effects": "creates an offer send request only",
        "approval_required": True,
    },
    "support.export": {
        "risk": "support_read",
        "side_effects": "none",
        "approval_required": False,
    },
    "sheets.append_row_request": {
        "risk": "external_spreadsheet_write_request",
        "side_effects": "creates a Google Sheets append-row request only",
        "approval_required": True,
    },
    "billing.reserve": {
        "risk": "billing",
        "side_effects": "ledger reservation is controlled by ActionOrchestrator",
        "approval_required": False,
    },
    "billing.settle": {
        "risk": "billing",
        "side_effects": "ledger settlement is controlled by ActionOrchestrator",
        "approval_required": False,
    },
}


LEGACY_CAPABILITY_ALIASES = {
    "reviews.reply": "reviews.reply.draft",
    "appointments.create": "appointments.create_request",
    "appointments.update": "appointments.create_request",
    "appointments.cancel": "appointments.create_request",
    "reminders.send": "communications.send_reminder",
    "communications.send": "communications.send_reminder",
    "google_sheets.append_row": "sheets.append_row_request",
    "sheets.append_row": "sheets.append_row_request",
    "billing.reserve/settle": "billing.reserve",
}


def build_capability_catalog() -> Dict[str, Any]:
    capabilities = {}
    for name, meta in CANONICAL_CAPABILITIES.items():
        capabilities[name] = _catalog_item(name, meta)
    for alias, target in LEGACY_CAPABILITY_ALIASES.items():
        target_meta = CANONICAL_CAPABILITIES.get(target, {})
        item = _catalog_item(alias, target_meta)
        item["alias_for"] = target
        capabilities[alias] = item
    return {
        "required_envelope_fields": [
            "tenant_id",
            "actor",
            "trace_id",
            "idempotency_key",
            "capability",
            "approval",
            "billing",
            "payload",
        ],
        "capabilities": capabilities,
    }


def build_capability_handlers() -> Dict[str, CapabilityHandler]:
    handlers: Dict[str, CapabilityHandler] = {
        OUTREACH_SEND_BATCH_CAPABILITY: handle_outreach_send_batch,
        "reviews.reply.draft": _handle_reviews_reply_draft,
        "reviews.reply.publish_request": _handle_reviews_reply_publish_request,
        "services.optimize": _handle_services_optimize,
        "news.generate": _handle_news_generate,
        "appointments.read": _handle_appointments_read,
        "appointments.create_request": _handle_appointments_create_request,
        "communications.draft": _handle_communications_draft,
        "communications.send_reminder": _handle_communications_send_reminder,
        "communications.send_offer": _handle_communications_send_offer,
        "support.export": _handle_support_export,
        "sheets.append_row_request": _handle_sheets_append_row_request,
        "billing.reserve": _handle_billing_reserve,
        "billing.settle": _handle_billing_settle,
    }
    for alias, target in LEGACY_CAPABILITY_ALIASES.items():
        if target in handlers:
            handlers[alias] = handlers[target]
    return handlers


def normalize_capability_name(value: Any) -> str:
    name = str(value or "").strip()
    return LEGACY_CAPABILITY_ALIASES.get(name, name)


def _catalog_item(name: str, meta: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": name,
        "risk": str(meta.get("risk") or "unknown"),
        "side_effects": str(meta.get("side_effects") or "unknown"),
        "approval_required": bool(meta.get("approval_required")),
        "timeout_seconds": 30,
        "retry": {
            "mode": "orchestrator_callback_outbox",
            "max_attempts": 5,
        },
        "audit": {
            "ledger": True,
            "action_request": True,
            "callback_outbox": True,
        },
    }


def _payload(envelope: Dict[str, Any]) -> Dict[str, Any]:
    value = envelope.get("payload")
    return value if isinstance(value, dict) else {}


def _actor_user_id(envelope: Dict[str, Any], user_data: Dict[str, Any]) -> str:
    actor = envelope.get("actor") if isinstance(envelope.get("actor"), dict) else {}
    return str(actor.get("id") or user_data.get("user_id") or user_data.get("id") or "").strip()


def _result(status: str, **kwargs: Any) -> Dict[str, Any]:
    data = {
        "status": status,
        "external_dispatch_performed": False,
    }
    data.update(kwargs)
    return {"result": data, "billing": {"total_tokens": 0, "cost": 0.0}}


def _stable_id(*parts: Any) -> str:
    raw = "|".join(str(part or "").strip() for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _row_to_dict(cursor: Any, row: Any) -> Dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, dict):
        return dict(row)
    if hasattr(row, "keys"):
        try:
            return dict(row)
        except Exception:
            return {}
    description = getattr(cursor, "description", None) or []
    columns = [str(col[0]) for col in description if col]
    if isinstance(row, (tuple, list)) and columns:
        return {columns[idx]: row[idx] for idx in range(min(len(columns), len(row)))}
    return {}


def _rows_to_dicts(cursor: Any, rows: Any) -> list[Dict[str, Any]]:
    return [_row_to_dict(cursor, row) for row in (rows or [])]


def _table_exists(cursor: Any, table_name: str) -> bool:
    cursor.execute("SELECT to_regclass(%s)", (str(table_name).lower(),))
    row = cursor.fetchone()
    if not row:
        return False
    if isinstance(row, dict):
        return bool(row.get("to_regclass") or row.get("reg") or row.get("?column?"))
    if isinstance(row, (tuple, list)):
        return bool(row[0])
    return bool(row)


def _table_columns(cursor: Any, table_name: str) -> set[str]:
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND lower(table_name) = %s
        """,
        (str(table_name).lower(),),
    )
    columns = set()
    for row in cursor.fetchall() or []:
        value = row.get("column_name") if isinstance(row, dict) else row[0]
        if value:
            columns.add(str(value).lower())
    return columns


def _ensure_communication_request_table(cursor: Any) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_communication_requests (
            id TEXT PRIMARY KEY,
            action_id TEXT NOT NULL UNIQUE,
            business_id TEXT NOT NULL,
            user_id TEXT,
            capability TEXT NOT NULL,
            message_type TEXT NOT NULL,
            status TEXT NOT NULL,
            channel TEXT,
            recipient_count INTEGER NOT NULL DEFAULT 0,
            recipients_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            message_template TEXT,
            limits_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            consent_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            delivery_state TEXT NOT NULL DEFAULT 'not_dispatched',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_communication_requests_business_status ON agent_communication_requests(business_id, status, created_at DESC)"
    )


def _ensure_service_optimization_request_table(cursor: Any) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_service_optimization_requests (
            id TEXT PRIMARY KEY,
            action_id TEXT NOT NULL UNIQUE,
            business_id TEXT NOT NULL,
            user_id TEXT,
            status TEXT NOT NULL,
            service_count INTEGER NOT NULL DEFAULT 0,
            suggestions_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            diff_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            apply_state TEXT NOT NULL DEFAULT 'not_applied',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_service_optimization_requests_business_status ON agent_service_optimization_requests(business_id, status, created_at DESC)"
    )
    cursor.execute(
        """
        ALTER TABLE agent_service_optimization_requests
        ADD COLUMN IF NOT EXISTS diff_json JSONB NOT NULL DEFAULT '[]'::jsonb
        """
    )


def _ensure_review_reply_draft_table(cursor: Any) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS reviewreplydrafts (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            review_id TEXT NOT NULL,
            user_id TEXT,
            source TEXT,
            rating INTEGER,
            author_name TEXT,
            review_text TEXT,
            generated_text TEXT NOT NULL,
            edited_text TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            tone TEXT,
            prompt_key TEXT,
            prompt_version TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_reviewreplydrafts_review_unique ON reviewreplydrafts(review_id)")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_reviewreplydrafts_business_status ON reviewreplydrafts(business_id, status, created_at DESC)"
    )


def _ensure_sheet_operation_request_table(cursor: Any) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_sheet_operation_requests (
            id TEXT PRIMARY KEY,
            action_id TEXT NOT NULL UNIQUE,
            business_id TEXT NOT NULL,
            user_id TEXT,
            integration_id TEXT,
            spreadsheet_id TEXT,
            sheet_name TEXT,
            operation TEXT NOT NULL,
            status TEXT NOT NULL,
            approval_state TEXT NOT NULL DEFAULT 'pending_human',
            apply_state TEXT NOT NULL DEFAULT 'not_applied',
            row_values_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            mapping_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            source_event_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            limits_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            provider_write_performed BOOLEAN NOT NULL DEFAULT FALSE,
            error_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_sheet_operation_requests_business_status ON agent_sheet_operation_requests(business_id, status, created_at DESC)"
    )


def _template_value(value: Any, context: Dict[str, Any]) -> Any:
    if not isinstance(value, str):
        return value
    result = value
    replacements = {
        "{{message_text}}": context.get("message_text"),
        "{{telegram.message_text}}": context.get("message_text"),
        "{{telegram_user_id}}": context.get("telegram_user_id"),
        "{{telegram.user_id}}": context.get("telegram_user_id"),
        "{{telegram_username}}": context.get("telegram_username"),
        "{{telegram.username}}": context.get("telegram_username"),
        "{{chat_id}}": context.get("chat_id"),
        "{{telegram.chat_id}}": context.get("chat_id"),
        "{{received_at}}": context.get("received_at"),
        "{{trigger_event_id}}": context.get("trigger_event_id"),
    }
    for token, replacement in replacements.items():
        result = result.replace(token, str(replacement or ""))
    return result


def _resolve_sheet_row_values(payload: Dict[str, Any]) -> list[Any]:
    context = payload.get("telegram") if isinstance(payload.get("telegram"), dict) else {}
    context = {**payload, **context}
    raw_values = payload.get("row_values")
    if not isinstance(raw_values, list):
        raw_values = payload.get("values") if isinstance(payload.get("values"), list) else []
    if raw_values:
        return [_template_value(item, context) for item in raw_values]
    message_text = str(context.get("message_text") or "").strip()
    received_at = str(context.get("received_at") or "").strip()
    username = str(context.get("telegram_username") or context.get("username") or "").strip()
    return [received_at, username, message_text]


def _resolve_sheet_mapping(payload: Dict[str, Any]) -> Dict[str, Any]:
    mapping = payload.get("mapping") if isinstance(payload.get("mapping"), dict) else {}
    context = payload.get("telegram") if isinstance(payload.get("telegram"), dict) else {}
    context = {**payload, **context}
    return {str(key): _template_value(value, context) for key, value in mapping.items()}


def _load_appointments(cursor: Any, tenant_id: str, payload: Dict[str, Any]) -> list[Dict[str, Any]]:
    if not _table_exists(cursor, "bookings"):
        return []
    filters = ["business_id = %s"]
    params: list[Any] = [tenant_id]
    client_phone = str(payload.get("client_phone") or payload.get("phone") or "").strip()
    status = str(payload.get("status") or "").strip()
    date_from = str(payload.get("from") or payload.get("date_from") or "").strip()
    date_to = str(payload.get("to") or payload.get("date_to") or "").strip()
    if client_phone:
        filters.append("client_phone = %s")
        params.append(client_phone)
    if status:
        filters.append("status = %s")
        params.append(status)
    if date_from:
        filters.append("booking_date >= %s")
        params.append(date_from)
    if date_to:
        filters.append("booking_date <= %s")
        params.append(date_to)
    limit = max(1, min(int(payload.get("limit") or 50), 200))
    params.append(limit)
    cursor.execute(
        f"""
        SELECT id, business_id, client_phone, client_name, service_id, service_name,
               booking_date, booking_time, status, notes, created_at, updated_at
        FROM Bookings
        WHERE {' AND '.join(filters)}
        ORDER BY booking_date ASC NULLS LAST, booking_time ASC NULLS LAST, created_at DESC
        LIMIT %s
        """,
        tuple(params),
    )
    return _rows_to_dicts(cursor, cursor.fetchall())


def _normalize_recipients(payload: Dict[str, Any]) -> list[Dict[str, Any]]:
    raw = payload.get("recipients")
    if not isinstance(raw, list):
        raw = payload.get("audience") if isinstance(payload.get("audience"), list) else []
    recipients: list[Dict[str, Any]] = []
    for item in raw:
        if isinstance(item, dict):
            phone = str(item.get("phone") or item.get("client_phone") or "").strip()
            channel = str(item.get("channel") or payload.get("channel") or "manual").strip()
            consent = item.get("consent") if isinstance(item.get("consent"), dict) else {}
            recipients.append(
                {
                    "client_id": str(item.get("client_id") or item.get("id") or "").strip(),
                    "client_name": str(item.get("client_name") or item.get("name") or "").strip(),
                    "client_phone": phone,
                    "channel": channel,
                    "consent": consent,
                }
            )
        elif str(item or "").strip():
            recipients.append(
                {
                    "client_id": "",
                    "client_name": "",
                    "client_phone": str(item or "").strip(),
                    "channel": str(payload.get("channel") or "manual").strip(),
                    "consent": {},
                }
            )
    return recipients


def _load_recipients_from_appointments(cursor: Any, tenant_id: str, payload: Dict[str, Any]) -> list[Dict[str, Any]]:
    if _normalize_recipients(payload):
        return _normalize_recipients(payload)
    appointments = _load_appointments(cursor, tenant_id, {**payload, "limit": payload.get("limit") or 50})
    recipients = []
    seen = set()
    for item in appointments:
        phone = str(item.get("client_phone") or "").strip()
        if not phone or phone in seen:
            continue
        seen.add(phone)
        recipients.append(
            {
                "client_id": "",
                "client_name": str(item.get("client_name") or "").strip(),
                "client_phone": phone,
                "channel": str(payload.get("channel") or "manual").strip(),
                "appointment_id": str(item.get("id") or "").strip(),
                "service_name": str(item.get("service_name") or "").strip(),
                "consent": {"transactional": True, "marketing": False},
            }
        )
    return recipients


def _create_communication_request(
    envelope: Dict[str, Any],
    user_data: Dict[str, Any],
    *,
    message_type: str,
) -> Dict[str, Any]:
    payload = _payload(envelope)
    tenant_id = str(envelope.get("tenant_id") or "").strip()
    action_id = str(envelope.get("action_id") or _stable_id("communication", tenant_id, message_type, payload))
    user_id = _actor_user_id(envelope, user_data)
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        _ensure_communication_request_table(cursor)
        recipients = _load_recipients_from_appointments(cursor, tenant_id, payload)
        daily_cap = int(payload.get("daily_cap") or payload.get("limit") or 10)
        daily_cap = max(1, min(daily_cap, 50))
        if len(recipients) > daily_cap:
            recipients = recipients[:daily_cap]
        request_id = _stable_id("agent_communication_request", action_id)
        template = str(payload.get("message") or payload.get("template") or "").strip()
        channel = str(payload.get("channel") or "manual").strip()
        cursor.execute(
            """
            INSERT INTO agent_communication_requests (
                id, action_id, business_id, user_id, capability, message_type, status,
                channel, recipient_count, recipients_json, message_template,
                limits_json, consent_json, delivery_state
            )
            VALUES (%s, %s, %s, %s, %s, %s, 'approved_request', %s, %s, %s, %s, %s, %s, 'not_dispatched')
            ON CONFLICT (action_id) DO UPDATE SET
                recipient_count = EXCLUDED.recipient_count,
                recipients_json = EXCLUDED.recipients_json,
                message_template = EXCLUDED.message_template,
                limits_json = EXCLUDED.limits_json,
                consent_json = EXCLUDED.consent_json,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id
            """,
            (
                request_id,
                action_id,
                tenant_id,
                user_id,
                str(envelope.get("capability") or ""),
                message_type,
                channel,
                len(recipients),
                _json_dumps(recipients),
                template,
                _json_dumps({"daily_cap": daily_cap, "frequency_cap": payload.get("frequency_cap") or "one_per_trigger"}),
                _json_dumps({"required": message_type == "package_offer", "rule": "marketing consent required for offers"}),
            ),
        )
        row = cursor.fetchone()
        request_id = str((row.get("id") if isinstance(row, dict) else row[0]) or request_id)
        db.conn.commit()
        return _result(
            "send_request_created",
            request_id=request_id,
            message_type=message_type,
            dispatch_state="pending_human",
            delivery_state="not_dispatched",
            recipient_count=len(recipients),
            recipients=recipients,
            limits={"daily_cap": daily_cap, "frequency_cap": payload.get("frequency_cap") or "one_per_trigger"},
            provider_write_performed=False,
        )
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


def _load_review(cursor: Any, tenant_id: str, review_id: str) -> Dict[str, Any]:
    if not review_id or not _table_exists(cursor, "externalbusinessreviews"):
        return {}
    cursor.execute(
        """
        SELECT id, business_id, source, external_review_id, rating, author_name, text, response_text, response_at
        FROM externalbusinessreviews
        WHERE id = %s AND business_id = %s
        LIMIT 1
        """,
        (review_id, tenant_id),
    )
    return _row_to_dict(cursor, cursor.fetchone())


def _load_services(cursor: Any, tenant_id: str, payload: Dict[str, Any]) -> list[Dict[str, Any]]:
    if not _table_exists(cursor, "userservices"):
        return []
    service_ids = payload.get("service_ids")
    if not isinstance(service_ids, list):
        single = str(payload.get("service_id") or "").strip()
        service_ids = [single] if single else []
    service_ids = [str(item).strip() for item in service_ids if str(item or "").strip()]
    limit = max(1, min(int(payload.get("limit") or 20), 100))
    columns = _table_columns(cursor, "userservices")
    select_columns = [
        "id",
        "business_id",
        "name",
        "description",
        "category",
        "price",
    ]
    if "optimized_name" in columns:
        select_columns.append("optimized_name")
    if "optimized_description" in columns:
        select_columns.append("optimized_description")
    where = ["business_id = %s"]
    params: list[Any] = [tenant_id]
    if "is_active" in columns:
        where.append("(is_active IS TRUE OR is_active IS NULL)")
    if service_ids:
        where.append("id = ANY(%s)")
        params.append(service_ids)
    order_parts = []
    if "updated_at" in columns:
        order_parts.append("updated_at DESC NULLS LAST")
    if "created_at" in columns:
        order_parts.append("created_at DESC NULLS LAST")
    order_sql = f"ORDER BY {', '.join(order_parts)}" if order_parts else "ORDER BY name ASC"
    params.append(limit)
    cursor.execute(
        f"""
        SELECT {', '.join(select_columns)}
        FROM userservices
        WHERE {' AND '.join(where)}
        {order_sql}
        LIMIT %s
        """,
        tuple(params),
    )
    return _rows_to_dicts(cursor, cursor.fetchall())


def _service_suggestion(service: Dict[str, Any]) -> Dict[str, Any]:
    name = str(service.get("name") or "").strip()
    description = str(service.get("description") or "").strip()
    category = str(service.get("category") or "").strip()
    optimized_name = str(service.get("optimized_name") or "").strip()
    optimized_description = str(service.get("optimized_description") or "").strip()
    proposed_name = optimized_name or name
    if category and category.lower() not in proposed_name.lower():
        proposed_name = f"{proposed_name} · {category}"
    proposed_description = optimized_description or description
    if not proposed_description:
        proposed_description = f"{name}: кратко опишите результат услуги, длительность и кому она подходит."
    return {
        "service_id": str(service.get("id") or "").strip(),
        "current_name": name,
        "current_description": description,
        "proposed_name": proposed_name,
        "proposed_description": proposed_description,
        "apply_state": "not_applied",
        "requires_manual_approval": True,
        "provider_write_performed": False,
    }


def _service_visual_diff(suggestions: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    diff = []
    for suggestion in suggestions:
        changed_fields = []
        current_name = str(suggestion.get("current_name") or "").strip()
        proposed_name = str(suggestion.get("proposed_name") or "").strip()
        current_description = str(suggestion.get("current_description") or "").strip()
        proposed_description = str(suggestion.get("proposed_description") or "").strip()
        if current_name != proposed_name:
            changed_fields.append("name")
        if current_description != proposed_description:
            changed_fields.append("description")
        diff.append(
            {
                "service_id": str(suggestion.get("service_id") or "").strip(),
                "changed_fields": changed_fields,
                "before": {
                    "name": current_name,
                    "description": current_description,
                },
                "after": {
                    "name": proposed_name,
                    "description": proposed_description,
                },
                "apply_state": str(suggestion.get("apply_state") or "not_applied"),
                "requires_manual_approval": True,
            }
        )
    return diff


def _handle_reviews_reply_draft(envelope: Dict[str, Any], user_data: Dict[str, Any]) -> Dict[str, Any]:
    payload = _payload(envelope)
    review_text = str(payload.get("review") or payload.get("review_text") or "").strip()
    tone = str(payload.get("tone") or "professional").strip()
    return _result(
        "drafted",
        draft={
            "reply": f"Спасибо за отзыв! Мы рады, что вам понравилось." if review_text else "",
            "tone": tone,
            "requires_manual_review": True,
        },
        publish_ready=False,
    )


def _handle_reviews_reply_publish_request(envelope: Dict[str, Any], user_data: Dict[str, Any]) -> Dict[str, Any]:
    payload = _payload(envelope)
    tenant_id = str(envelope.get("tenant_id") or "").strip()
    review_id = str(payload.get("review_id") or "").strip()
    reply = str(payload.get("reply") or payload.get("draft") or payload.get("generated_text") or "").strip()
    if not review_id or not reply:
        return _result(
            "validation_error",
            error_code="REVIEW_ID_AND_REPLY_REQUIRED",
            review_id=review_id,
            dispatch_state="not_created",
            provider_write_performed=False,
        )
    user_id = _actor_user_id(envelope, user_data)
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        _ensure_review_reply_draft_table(cursor)
        review = _load_review(cursor, tenant_id, review_id)
        draft_id = _stable_id("reviewreplydrafts", tenant_id, review_id)
        cursor.execute(
            """
            INSERT INTO reviewreplydrafts (
                id, business_id, review_id, user_id, source, rating, author_name,
                review_text, generated_text, edited_text, status, tone, prompt_key,
                prompt_version, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'publish_requested', %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (review_id)
            DO UPDATE SET
                generated_text = EXCLUDED.generated_text,
                edited_text = EXCLUDED.edited_text,
                status = 'publish_requested',
                tone = EXCLUDED.tone,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id
            """,
            (
                draft_id,
                tenant_id,
                review_id,
                user_id,
                str(review.get("source") or payload.get("source") or "agent_capability"),
                review.get("rating"),
                str(review.get("author_name") or payload.get("author_name") or ""),
                str(review.get("text") or payload.get("review_text") or ""),
                reply,
                reply,
                str(payload.get("tone") or "professional"),
                "agent_capability_publish_request",
                "v1",
            ),
        )
        row = cursor.fetchone()
        draft_id = str((row.get("id") if isinstance(row, dict) else row[0]) or draft_id)
        db.conn.commit()
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()
    return _result(
        "publish_request_created",
        review_id=review_id,
        draft_id=draft_id,
        reply=reply,
        dispatch_state="pending_human",
        provider_write_performed=False,
        manual_publish_required=True,
    )


def _handle_services_optimize(envelope: Dict[str, Any], user_data: Dict[str, Any]) -> Dict[str, Any]:
    payload = _payload(envelope)
    tenant_id = str(envelope.get("tenant_id") or "").strip()
    user_id = _actor_user_id(envelope, user_data)
    action_id = str(envelope.get("action_id") or _stable_id("services.optimize", tenant_id, payload))
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        _ensure_service_optimization_request_table(cursor)
        services = _load_services(cursor, tenant_id, payload)
        if not services:
            inline_name = str(payload.get("name") or payload.get("service_name") or "").strip()
            inline_description = str(payload.get("description") or "").strip()
            if inline_name:
                services = [{"id": "", "name": inline_name, "description": inline_description, "category": "", "price": ""}]
        suggestions = [_service_suggestion(service) for service in services]
        visual_diff = _service_visual_diff(suggestions)
        request_id = _stable_id("agent_service_optimization_request", action_id)
        cursor.execute(
            """
            INSERT INTO agent_service_optimization_requests (
                id, action_id, business_id, user_id, status, service_count,
                suggestions_json, diff_json, apply_state
            )
            VALUES (%s, %s, %s, %s, 'draft_ready', %s, %s, %s, 'not_applied')
            ON CONFLICT (action_id) DO UPDATE SET
                service_count = EXCLUDED.service_count,
                suggestions_json = EXCLUDED.suggestions_json,
                diff_json = EXCLUDED.diff_json,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id
            """,
            (request_id, action_id, tenant_id, user_id, len(suggestions), _json_dumps(suggestions), _json_dumps(visual_diff)),
        )
        row = cursor.fetchone()
        request_id = str((row.get("id") if isinstance(row, dict) else row[0]) or request_id)
        db.conn.commit()
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()
    return _result(
        "optimized_draft",
        request_id=request_id,
        service_count=len(suggestions),
        suggestions=suggestions,
        visual_diff=visual_diff,
        apply_performed=False,
        provider_write_performed=False,
        manual_apply_required=True,
    )


def _handle_news_generate(envelope: Dict[str, Any], user_data: Dict[str, Any]) -> Dict[str, Any]:
    payload = _payload(envelope)
    topic = str(payload.get("topic") or payload.get("prompt") or payload.get("title") or "").strip()
    return _result(
        "drafted",
        news={
            "title": topic or "Новость бизнеса",
            "body": str(payload.get("body") or "").strip(),
            "publish_performed": False,
        },
    )


def _handle_appointments_read(envelope: Dict[str, Any], user_data: Dict[str, Any]) -> Dict[str, Any]:
    payload = _payload(envelope)
    tenant_id = str(envelope.get("tenant_id") or "").strip()
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        appointments = _load_appointments(cursor, tenant_id, payload)
    finally:
        db.close()
    return _result(
        "read_completed",
        appointments=appointments,
        count=len(appointments),
        filters={
            "from": str(payload.get("from") or ""),
            "to": str(payload.get("to") or ""),
            "client_id": str(payload.get("client_id") or ""),
            "client_phone": str(payload.get("client_phone") or payload.get("phone") or ""),
            "status": str(payload.get("status") or ""),
        },
        source="Bookings",
    )


def _handle_appointments_create_request(envelope: Dict[str, Any], user_data: Dict[str, Any]) -> Dict[str, Any]:
    payload = _payload(envelope)
    return _result(
        "appointment_request_created",
        request={
            "client_id": str(payload.get("client_id") or ""),
            "service_id": str(payload.get("service_id") or ""),
            "starts_at": str(payload.get("starts_at") or ""),
            "status": "pending_human",
        },
    )


def _handle_communications_draft(envelope: Dict[str, Any], user_data: Dict[str, Any]) -> Dict[str, Any]:
    payload = _payload(envelope)
    return _result(
        "drafted",
        drafts=[
            {
                "channel": str(payload.get("channel") or "manual"),
                "message": str(payload.get("message") or payload.get("template") or "").strip(),
                "audience": payload.get("audience") or "clients_with_upcoming_appointments",
            }
        ],
    )


def _handle_communications_send_reminder(envelope: Dict[str, Any], user_data: Dict[str, Any]) -> Dict[str, Any]:
    return _create_communication_request(envelope, user_data, message_type="appointment_reminder")


def _handle_communications_send_offer(envelope: Dict[str, Any], user_data: Dict[str, Any]) -> Dict[str, Any]:
    return _create_communication_request(envelope, user_data, message_type="package_offer")


def _handle_support_export(envelope: Dict[str, Any], user_data: Dict[str, Any]) -> Dict[str, Any]:
    payload = _payload(envelope)
    return _result(
        "support_export_ready",
        export={
            "tenant_id": str(envelope.get("tenant_id") or ""),
            "action_id": str(payload.get("action_id") or envelope.get("action_id") or ""),
            "format": str(payload.get("format") or "json"),
        },
    )


def _handle_sheets_append_row_request(envelope: Dict[str, Any], user_data: Dict[str, Any]) -> Dict[str, Any]:
    payload = _payload(envelope)
    tenant_id = str(envelope.get("tenant_id") or "").strip()
    integration_id = str(payload.get("integration_id") or payload.get("google_sheets_integration_id") or "").strip()
    spreadsheet_id = str(payload.get("spreadsheet_id") or payload.get("google_spreadsheet_id") or "").strip()
    sheet_name = str(payload.get("sheet_name") or payload.get("tab") or "Sheet1").strip()
    row_values = _resolve_sheet_row_values(payload)
    mapping = _resolve_sheet_mapping(payload)
    if not integration_id and not spreadsheet_id:
        return _result(
            "validation_error",
            error_code="SHEET_CONNECTION_REQUIRED",
            dispatch_state="not_created",
            apply_state="not_applied",
            provider_write_performed=False,
        )
    if not row_values and not mapping:
        return _result(
            "validation_error",
            error_code="ROW_VALUES_REQUIRED",
            dispatch_state="not_created",
            apply_state="not_applied",
            provider_write_performed=False,
        )
    action_id = str(envelope.get("action_id") or _stable_id("sheets.append_row_request", tenant_id, payload))
    request_id = _stable_id("agent_sheet_operation_request", action_id)
    user_id = _actor_user_id(envelope, user_data)
    source_event = payload.get("source_event") if isinstance(payload.get("source_event"), dict) else {}
    if not source_event and payload.get("trigger_event_id"):
        source_event = {"trigger_event_id": str(payload.get("trigger_event_id") or "")}
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        _ensure_sheet_operation_request_table(cursor)
        cursor.execute(
            """
            INSERT INTO agent_sheet_operation_requests (
                id, action_id, business_id, user_id, integration_id, spreadsheet_id,
                sheet_name, operation, status, approval_state, apply_state,
                row_values_json, mapping_json, source_event_json, limits_json,
                provider_write_performed
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'append_row', 'request_created',
                    'pending_human', 'not_applied', %s, %s, %s, %s, FALSE)
            ON CONFLICT (action_id) DO UPDATE SET
                row_values_json = EXCLUDED.row_values_json,
                mapping_json = EXCLUDED.mapping_json,
                source_event_json = EXCLUDED.source_event_json,
                limits_json = EXCLUDED.limits_json,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id
            """,
            (
                request_id,
                action_id,
                tenant_id,
                user_id,
                integration_id or None,
                spreadsheet_id or None,
                sheet_name,
                _json_dumps(row_values),
                _json_dumps(mapping),
                _json_dumps(source_event),
                _json_dumps(
                    {
                        "approval_required": True,
                        "daily_append_cap": max(1, min(int(payload.get("daily_append_cap") or 50), 500)),
                    }
                ),
            ),
        )
        row = cursor.fetchone()
        request_id = str((row.get("id") if isinstance(row, dict) else row[0]) or request_id)
        db.conn.commit()
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()
    return _result(
        "sheet_append_request_created",
        request_id=request_id,
        operation="append_row",
        integration_id=integration_id,
        spreadsheet_id=spreadsheet_id,
        sheet_name=sheet_name,
        row_values=row_values,
        mapping=mapping,
        approval_state="pending_human",
        apply_state="not_applied",
        provider_write_performed=False,
        manual_apply_required=True,
    )


def _handle_billing_reserve(envelope: Dict[str, Any], user_data: Dict[str, Any]) -> Dict[str, Any]:
    billing = envelope.get("billing") if isinstance(envelope.get("billing"), dict) else {}
    payload = _payload(envelope)
    estimated_credits = payload.get("estimated_credits")
    if estimated_credits is None:
        return _result(
            "reserved_by_orchestrator",
            reserve_tokens=int(billing.get("reserve_tokens") or 0),
            reservation=None,
            credit_reserved=False,
            ledger="billing_ledger",
        )
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        reservation = reserve_paid_action_credits(
            cursor,
            business_id=str(envelope.get("tenant_id") or ""),
            user_id=_actor_user_id(envelope, user_data),
            action_key=str(payload.get("action_key") or "agent_capability.billing.reserve"),
            estimated_credits=estimated_credits,
            idempotency_key=str(envelope.get("idempotency_key") or envelope.get("action_id") or ""),
            metadata={
                "source": "agent_capability",
                "action_id": str(envelope.get("action_id") or ""),
                "capability": str(envelope.get("capability") or ""),
            },
        )
        db.conn.commit()
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()
    return _result(
        "reserved",
        reserve_tokens=int(billing.get("reserve_tokens") or 0),
        reservation=reservation,
        credit_reserved=bool((reservation or {}).get("side_effects", {}).get("credit_reserved")),
    )


def _handle_billing_settle(envelope: Dict[str, Any], user_data: Dict[str, Any]) -> Dict[str, Any]:
    payload = _payload(envelope)
    reservation_id = str(payload.get("reservation_id") or "").strip()
    if reservation_id:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        try:
            finalization = finalize_reserved_action_credits(
                cursor,
                business_id=str(envelope.get("tenant_id") or ""),
                user_id=_actor_user_id(envelope, user_data),
                reservation_id=reservation_id,
                actual_credits=payload.get("actual_credits"),
                finalization_mode=str(payload.get("finalization_mode") or "charge"),
                external_id=str(envelope.get("action_id") or reservation_id),
            )
            db.conn.commit()
        except Exception:
            db.conn.rollback()
            raise
        finally:
            db.close()
        return _result(
            "settled",
            reservation=finalization,
            credit_charged=bool((finalization or {}).get("side_effects", {}).get("credit_charged")),
            credit_released=bool((finalization or {}).get("side_effects", {}).get("credit_released")),
        )
    return {
        "result": {
            "status": "settled_by_orchestrator",
            "external_dispatch_performed": False,
            "ledger": "billing_ledger",
        },
        "billing": {
            "total_tokens": 0,
            "cost": 0.0,
        },
    }


def _count_recipients(payload: Dict[str, Any]) -> int:
    recipients = payload.get("recipients")
    if isinstance(recipients, list):
        return len(recipients)
    audience = payload.get("audience")
    if isinstance(audience, list):
        return len(audience)
    return 0
