from datetime import datetime, timezone

import pytest

from services.journey_action_notifications import _tasks_enabled
from services.lead_journey_service import (
    JourneyError,
    _clean_public_opportunity,
    _next_action_spec,
    build_lead_preview,
    load_public_journey,
    token_hash,
)


def action(action_type, flow_type="influencer", payload=None):
    return {"action_type": action_type, "flow_type": flow_type, "payload_json": payload or {}}


def test_public_opportunity_drops_private_fields_and_truncates_message():
    result = _clean_public_opportunity({
        "flow_type": "influencer",
        "entity_type": "creator_profile",
        "entity_id": "creator-1",
        "title": "Анна",
        "summary": "Локальный автор",
        "reason": "Подходит по географии",
        "mechanic": "Бартер",
        "message_excerpt": "x" * 400,
        "contact": "+79990000000",
        "full_message": "private",
        "metrics": {"followers": 12000},
    })

    assert result["entity_id"] == "creator-1"
    assert len(result["message_excerpt"]) == 180
    assert "contact" not in result
    assert "full_message" not in result
    assert result["metrics"]["followers"] == 12000


def test_sent_message_waits_four_days_for_reply():
    next_type, status, due_at, payload = _next_action_spec(action("send_message"), "mark_sent", {"manual": True})

    assert next_type == "check_reply"
    assert status == "completed"
    assert due_at is not None
    assert 3.9 <= (due_at - datetime.now(timezone.utc)).total_seconds() / 86400 <= 4.1
    assert payload["manual"] is True


@pytest.mark.parametrize("flow,expected", [("influencer", "select_next_influencer"), ("partnership", "select_next_partner")])
def test_refusal_closes_reply_step_and_selects_next_candidate(flow, expected):
    next_type, status, _due_at, payload = _next_action_spec(action("check_reply", flow), "record_reply", {"outcome": "refused"})

    assert next_type == expected
    assert status == "completed"
    assert payload["reply_outcome"] == "refused"


def test_maps_cycle_moves_through_refresh_and_comparison():
    next_type, status, _due_at, payload = _next_action_spec(
        action("complete_map_task", "maps", {"task_index": 0, "tasks_total": 1}),
        "complete",
        {"reported": True},
    )
    assert (next_type, status) == ("refresh_data", "completed")

    next_type, status, _due_at, payload = _next_action_spec(action("refresh_data", "maps", payload), "complete", {"score_after": 68})
    assert (next_type, status) == ("compare_snapshot", "completed")

    next_type, status, _due_at, payload = _next_action_spec(action("compare_snapshot", "maps", payload), "complete", {})
    assert (next_type, status) == ("start_next_map_plan", "completed")
    assert payload["cycle_completed"] is True


def test_invalid_transition_is_rejected():
    with pytest.raises(JourneyError) as error:
        _next_action_spec(action("send_message"), "add_result", {})
    assert error.value.code == "transition_not_allowed"


def test_token_hash_is_stable_without_storing_raw_token():
    assert token_hash("secret") == token_hash("secret")
    assert token_hash("secret") != "secret"
    assert token_hash("secret") != token_hash("other")


def test_public_journey_lock_targets_only_journey_row():
    class Cursor:
        query = ""

        def execute(self, query, _params):
            self.query = query

        def fetchone(self):
            return {"id": "journey-1", "status": "preview", "expires_at": None}

    cursor = Cursor()

    journey = load_public_journey(cursor, "secret", lock=True)

    assert journey["id"] == "journey-1"
    assert "FOR UPDATE OF journey" in cursor.query


def test_lead_preview_uses_only_safe_business_context():
    preview = build_lead_preview({
        "name": "Студия",
        "city": "Казань",
        "address": "ул. Баумана, 1",
        "category": "Салон красоты",
        "rating": 4.8,
        "reviews_count": 42,
        "phone": "+79990000000",
    })

    assert len(preview["opportunities"]) == 3
    assert preview["opportunities"][2]["metrics"] == {"rating": 4.8, "reviews_count": 42}
    assert "phone" not in preview


def test_journey_notifications_follow_existing_tasks_preference():
    assert _tasks_enabled({"business:b-1": {"tasks": True}}, "b-1") is True
    assert _tasks_enabled({"business:b-1": {"tasks": False}}, "b-1") is False
    assert _tasks_enabled({"business:b-2": {"tasks": True}}, "b-1") is False
