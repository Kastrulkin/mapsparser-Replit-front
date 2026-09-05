"""Append-only, allowlisted product telemetry shared by web and Mini App."""
from __future__ import annotations

import json
import uuid
from typing import Any


ALLOWED_PRODUCT_EVENTS = frozenset({
    "onboarding_completed", "today_open", "today_focus_open", "today_delegate_open",
    "today_delegate_focus", "today_pulse_open", "today_progress_open",
    "progress_action_open", "growth_loop_open", "growth_mission_open",
    "crm_integration_request_created", "progress_open", "mission_open",
    "statistics_flow_opened", "statistics_preview_created", "statistics_preview_confirmed",
    "crm_request_created",
    "lead_link_opened", "opportunity_preview_clicked", "opportunity_list_opened",
    "action_prepare_clicked", "partial_result_viewed", "registration_started",
    "registration_completed", "generated_action_viewed", "message_copied",
    "action_marked_sent", "followup_created", "reply_recorded", "deal_started",
    "result_added", "map_task_completed", "next_action_opened",
    "recurring_monitoring_enabled", "paywall_viewed", "subscription_started",
    "email_verified", "journey_claimed", "journey_workspace_opened",
    "auth_redirect_failed", "stale_action_detected", "orphan_action_detected",
    "content_draft_saved", "content_scheduled",
    "automation_configured", "automation_preflight_approved", "automation_run_linked",
    "today_priority_set", "today_priority_accepted", "today_priority_declined",
    "today_priority_snoozed", "today_priority_disabled", "today_priority_enabled", "today_priority_undone",
})
ALLOWED_SURFACES = frozenset({"web", "telegram_mini_app"})
PUBLIC_EVENT_PROPERTY_KEYS = frozenset({"cta_variant"})


def validate_product_event(event_name: object, surface: object) -> tuple[str | None, str | None, str | None]:
    clean_event = str(event_name or "").strip()
    clean_surface = str(surface or "").strip()
    if clean_event not in ALLOWED_PRODUCT_EVENTS:
        return None, None, "Событие не поддерживается"
    if clean_surface not in ALLOWED_SURFACES:
        return None, None, "Поверхность не поддерживается"
    return clean_event, clean_surface, None


def sanitize_public_event_properties(properties: object) -> dict[str, str | int | float | bool]:
    """Keep guest telemetry anonymous and intentionally narrow."""
    if not isinstance(properties, dict):
        return {}
    sanitized: dict[str, str | int | float | bool] = {}
    for key in PUBLIC_EVENT_PROPERTY_KEYS:
        value = properties.get(key)
        if isinstance(value, bool):
            sanitized[key] = value
        elif isinstance(value, (int, float)):
            sanitized[key] = value
        elif isinstance(value, str) and len(value) <= 80:
            sanitized[key] = value
    return sanitized


def record_product_event(cursor: Any, *, event_name: str, surface: str, business_id: str | None,
                         user_id: str | None, scope_type: str | None = None,
                         scope_id: str | None = None, screen: str = "", target: str = "",
                         properties: dict[str, Any] | None = None,
                         lead_id: str | None = None, journey_id: str | None = None,
                         action_id: str | None = None, flow_type: str | None = None,
                         entity_type: str | None = None, entity_id: str | None = None,
                         signal_source: str | None = None, deduplication_key: str | None = None) -> str:
    event_id = str(uuid.uuid4())
    if signal_source is not None or deduplication_key is not None:
        cursor.execute(
            """INSERT INTO product_analytics_events
               (id,event_name,channel,business_id,user_id,scope_type,scope_id,screen,target,
                properties_json,lead_id,journey_id,action_id,flow_type,entity_type,entity_id,
                signal_source,deduplication_key)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (user_id,business_id,deduplication_key)
                   WHERE deduplication_key IS NOT NULL DO NOTHING RETURNING id""",
            (event_id,event_name,surface,business_id,user_id,scope_type,scope_id,
             screen[:160],target[:500],json.dumps(properties or {},ensure_ascii=False),
             lead_id,journey_id,action_id,flow_type,entity_type,entity_id,
             signal_source or "client_observation",deduplication_key),
        )
        inserted = cursor.fetchone()
        if inserted:
            return str(inserted.get("id") if hasattr(inserted,"keys") else inserted[0])
        cursor.execute("SELECT id FROM product_analytics_events WHERE user_id=%s AND business_id=%s AND deduplication_key=%s", (user_id,business_id,deduplication_key))
        existing = cursor.fetchone()
        return str(existing.get("id") if hasattr(existing,"keys") else existing[0])
    cursor.execute(
        """INSERT INTO product_analytics_events
           (id, event_name, channel, business_id, user_id, scope_type, scope_id, screen, target,
            properties_json, lead_id, journey_id, action_id, flow_type, entity_type, entity_id)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s)""",
        (event_id, event_name, surface, business_id, user_id, scope_type, scope_id,
         screen[:160], target[:500], json.dumps(properties or {}, ensure_ascii=False),
         lead_id, journey_id, action_id, flow_type, entity_type, entity_id),
    )
    return event_id


def record_confirmed_user_action(cursor, *, auth, event_name, business_id, flow,
                                 operation_key, surface="web", entity_id=None):
    """Only call after a successful interactive application command, in its transaction."""
    from services.today_preferences_service import CONFIRMED_EVENTS, enabled, normalize_flow
    if not enabled("LOCALOS_TODAY_ACTIVITY_ENABLED", False) or not auth.permits_personalization_signal:
        return None
    if event_name not in CONFIRMED_EVENTS or not operation_key or not auth.permits_business(business_id):
        return None
    record_id = record_product_event(
        cursor, event_name=event_name, surface=surface, business_id=business_id,
        user_id=auth.user_id, scope_type="business", scope_id=business_id,
        flow_type=normalize_flow(flow), entity_id=entity_id,
        signal_source="confirmed_user_action",
        deduplication_key=f"command:{event_name}:{operation_key}",
    )
    cursor.execute("""INSERT INTO today_preferences(user_id,scope_type,scope_id)
        VALUES (%s,'business',%s) ON CONFLICT DO NOTHING""", (auth.user_id,business_id))
    return record_id
