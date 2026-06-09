from __future__ import annotations

from typing import Any, Callable, Dict

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


def _result(status: str, **kwargs: Any) -> Dict[str, Any]:
    data = {
        "status": status,
        "external_dispatch_performed": False,
    }
    data.update(kwargs)
    return {"result": data, "billing": {"total_tokens": 0, "cost": 0.0}}


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
    return _result(
        "publish_request_created",
        review_id=str(payload.get("review_id") or ""),
        reply=str(payload.get("reply") or payload.get("draft") or ""),
        dispatch_state="pending_human",
    )


def _handle_services_optimize(envelope: Dict[str, Any], user_data: Dict[str, Any]) -> Dict[str, Any]:
    payload = _payload(envelope)
    name = str(payload.get("name") or payload.get("service_name") or "").strip()
    description = str(payload.get("description") or "").strip()
    return _result(
        "optimized_draft",
        service={
            "name": name,
            "description": description,
        },
        suggestions=[
            "clarify service outcome",
            "add duration or package details when available",
            "keep claims reviewable before publication",
        ],
        apply_performed=False,
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
    return _result(
        "read_plan_ready",
        appointments=[],
        filters={
            "from": str(payload.get("from") or ""),
            "to": str(payload.get("to") or ""),
            "client_id": str(payload.get("client_id") or ""),
        },
        source="appointments",
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
    payload = _payload(envelope)
    return _result(
        "send_request_created",
        message_type="appointment_reminder",
        dispatch_state="pending_human",
        recipient_count=_count_recipients(payload),
    )


def _handle_communications_send_offer(envelope: Dict[str, Any], user_data: Dict[str, Any]) -> Dict[str, Any]:
    payload = _payload(envelope)
    return _result(
        "send_request_created",
        message_type="package_offer",
        dispatch_state="pending_human",
        recipient_count=_count_recipients(payload),
    )


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


def _handle_billing_reserve(envelope: Dict[str, Any], user_data: Dict[str, Any]) -> Dict[str, Any]:
    billing = envelope.get("billing") if isinstance(envelope.get("billing"), dict) else {}
    return _result(
        "reserved_by_orchestrator",
        reserve_tokens=int(billing.get("reserve_tokens") or 0),
    )


def _handle_billing_settle(envelope: Dict[str, Any], user_data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "result": {
            "status": "settled_by_orchestrator",
            "external_dispatch_performed": False,
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
