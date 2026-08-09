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
})
ALLOWED_SURFACES = frozenset({"web", "telegram_mini_app"})


def validate_product_event(event_name: object, surface: object) -> tuple[str | None, str | None, str | None]:
    clean_event = str(event_name or "").strip()
    clean_surface = str(surface or "").strip()
    if clean_event not in ALLOWED_PRODUCT_EVENTS:
        return None, None, "Событие не поддерживается"
    if clean_surface not in ALLOWED_SURFACES:
        return None, None, "Поверхность не поддерживается"
    return clean_event, clean_surface, None


def record_product_event(cursor: Any, *, event_name: str, surface: str, business_id: str | None,
                         user_id: str | None, scope_type: str | None = None,
                         scope_id: str | None = None, screen: str = "", target: str = "",
                         properties: dict[str, Any] | None = None) -> str:
    event_id = str(uuid.uuid4())
    cursor.execute(
        """INSERT INTO product_analytics_events
           (id, event_name, channel, business_id, user_id, scope_type, scope_id, screen, target, properties_json)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)""",
        (event_id, event_name, surface, business_id, user_id, scope_type, scope_id,
         screen[:160], target[:500], json.dumps(properties or {}, ensure_ascii=False)),
    )
    return event_id
