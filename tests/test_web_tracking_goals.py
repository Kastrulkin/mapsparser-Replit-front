from datetime import datetime, timezone

import pytest

from services.web_tracking_goals_service import (
    WebTrackingConfigurationError,
    ingest_confirmed_conversion,
    page_matches,
    preview_page_group,
    validate_goal_payload,
    validate_page_group_payload,
)


class Cursor:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.current = None
        self.queries = []

    def execute(self, query, params=None):
        self.queries.append((query, params))
        self.current = self.rows.pop(0) if self.rows else None

    def fetchone(self):
        return self.current

    def fetchall(self):
        return self.current or []


def test_page_group_rules_support_exact_prefix_contains_list_and_exclusions():
    assert page_matches("/services/hair", "prefix", ["/services"], []) is True
    assert page_matches("/prices", "exact", ["/prices"], []) is True
    assert page_matches("/ru/price-list", "contains", ["/price"], []) is True
    assert page_matches("/contact", "list", ["/contact", "/about"], []) is True
    assert page_matches("/services/archive", "prefix", ["/services"], ["/archive"]) is False


def test_page_group_preview_returns_real_matching_paths_before_save():
    cursor = Cursor([[
        {"path": "/services/hair", "title": "Стрижки", "views": 8, "sessions": 5},
        {"path": "/contact", "title": "Контакты", "views": 2, "sessions": 2},
    ]])

    result = preview_page_group(cursor, "business-1", {
        "name": "Услуги",
        "group_type": "service",
        "match_type": "prefix",
        "include_patterns": ["/services"],
        "exclude_patterns": [],
    })

    assert result["matched_paths"] == 1
    assert result["matched_sessions"] == 5
    assert result["sample"][0]["title"] == "Стрижки"


def test_configuration_rejects_ambiguous_active_rules_and_missing_goal_matchers():
    with pytest.raises(WebTrackingConfigurationError, match="page_group_patterns_required"):
        validate_page_group_payload({"name": "Услуги", "group_type": "service", "match_type": "prefix"})
    with pytest.raises(WebTrackingConfigurationError, match="goal_cta_required"):
        validate_goal_payload({"name": "Запись", "goal_type": "cta_click", "matcher": {}})


@pytest.mark.parametrize("goal_type", ["message_started", "message_lead", "call_answered", "call_qualified"])
def test_confirmed_phone_and_messenger_states_can_be_goals(goal_type):
    result = validate_goal_payload({"name": "Подтверждённый результат", "goal_type": goal_type})
    assert result["goal_type"] == goal_type


def test_confirmed_conversion_is_privacy_bounded_and_idempotent():
    cursor = Cursor([{"id": "conversion-1"}])
    result = ingest_confirmed_conversion(cursor, {"id": "tracker-1", "business_id": "business-1"}, {
        "source": "yclients",
        "external_id": "booking-1",
        "event_type": "booking_confirmed",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "attribution_session_id": "s_0123456789abcdef01234567",
        "amount": "3500",
        "currency": "rub",
        "provider": "yclients",
        "client_phone": "+79990000000",
    })

    assert result["accepted"] is True
    query, params = cursor.queries[0]
    assert "ON CONFLICT" in query
    serialized = str(params)
    assert "+79990000000" not in serialized
    assert "yclients" in serialized
