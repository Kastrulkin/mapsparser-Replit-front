from datetime import datetime, timedelta, timezone

import pytest

from services.journey_action_notifications import _tasks_enabled
from services.lead_journey_service import (
    JourneyError,
    _clean_public_opportunity,
    _next_action_spec,
    build_growth_paths,
    claim_reserved_journey,
    claim_journey,
    create_lead_journey,
    execute_command,
    build_lead_preview,
    build_lead_preview_from_sources,
    load_public_journey,
    reconcile_map_actions,
    serialize_journey,
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


def test_public_journey_drops_sensitive_nested_metrics():
    result = serialize_journey(
        object(),
        {
            "id": "journey-1",
            "preview_json": {
                "opportunities": [{
                    "flow_type": "influencer",
                    "entity_type": "creator_profile",
                    "entity_id": "creator-1",
                    "title": "Анна",
                    "metrics": {
                        "followers": 12000,
                        "phone": "+79990000000",
                        "email": "hidden@example.test",
                        "token": "private-token",
                        "password": "private-password",
                    },
                }],
            },
        },
        public=True,
    )

    assert result["opportunities"][0]["metrics"] == {"followers": 12000}


def test_sent_message_waits_four_days_for_reply():
    next_type, status, due_at, payload = _next_action_spec(action("send_message"), "mark_sent", {"manual": True})

    assert next_type == "check_reply"
    assert status == "completed"
    assert due_at is not None
    assert 3.9 <= (due_at - datetime.now(timezone.utc)).total_seconds() / 86400 <= 4.1
    assert payload["manual"] is True


def test_influencer_journey_browses_before_paid_messages():
    next_type, status, due_at, payload = _next_action_spec(
        action("browse_creators", payload={"offer": {"service": "Стрижка", "version": 1}}),
        "complete",
        {},
    )

    assert (next_type, status, due_at) == ("send_message", "completed", None)
    assert payload["offer"] == {"service": "Стрижка", "version": 1}


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


def test_content_cycle_requires_draft_and_schedule_then_records_result():
    next_type, status, _due_at, payload = _next_action_spec(
        action("prepare_content", "content", {"content_topic": "Уход после процедуры"}),
        "prepare",
        {},
    )
    assert (next_type, status) == ("review_content", "completed")

    with pytest.raises(JourneyError) as draft_error:
        _next_action_spec(action("review_content", "content", payload), "save_draft", {"draft_text": ""})
    assert draft_error.value.code == "content_draft_required"

    next_type, status, _due_at, payload = _next_action_spec(
        action("review_content", "content", payload),
        "save_draft",
        {"draft_text": "Полезный материал"},
    )
    assert (next_type, status) == ("save_to_calendar", "completed")

    with pytest.raises(JourneyError) as schedule_error:
        _next_action_spec(action("save_to_calendar", "content", payload), "schedule", {})
    assert schedule_error.value.code == "content_schedule_required"

    next_type, status, _due_at, payload = _next_action_spec(
        action("save_to_calendar", "content", payload),
        "schedule",
        {"scheduled_for": "2026-09-01"},
    )
    assert (next_type, status) == ("waiting_for_publication", "completed")

    next_type, status, _due_at, payload = _next_action_spec(
        action("waiting_for_publication", "content", payload),
        "mark_published",
        {"publication_url": "https://example.test/post"},
    )
    assert (next_type, status) == ("add_content_result", "completed")

    next_type, status, _due_at, payload = _next_action_spec(
        action("add_content_result", "content", payload),
        "add_result",
        {"views": 40},
    )
    assert (next_type, status) == ("start_next_content_cycle", "completed")
    assert payload["cycle_completed"] is True


def test_automation_cycle_requires_configuration_confirmation_and_real_run():
    with pytest.raises(JourneyError) as missing_use_case:
        _next_action_spec(action("configure_automation", "automation"), "save_configuration", {"expected_result": "Черновики ответов"})
    assert missing_use_case.value.code == "automation_use_case_required"

    next_type, status, _due_at, payload = _next_action_spec(
        action("configure_automation", "automation"),
        "save_configuration",
        {"use_case": "reviews_without_reply", "expected_result": "Черновики ответов"},
    )
    assert (next_type, status) == ("review_automation_preflight", "completed")

    with pytest.raises(JourneyError) as missing_confirmation:
        _next_action_spec(action("review_automation_preflight", "automation", payload), "approve", {})
    assert missing_confirmation.value.code == "automation_preflight_confirmation_required"

    next_type, status, _due_at, payload = _next_action_spec(
        action("review_automation_preflight", "automation", payload),
        "approve",
        {"confirmed": True},
    )
    assert (next_type, status) == ("run_automation", "completed")

    next_type, status, _due_at, payload = _next_action_spec(
        action("run_automation", "automation", payload),
        "link_run",
        {},
    )
    assert (next_type, status) == ("review_automation_result", "completed")

    next_type, status, _due_at, payload = _next_action_spec(
        action("review_automation_result", "automation", payload),
        "add_result",
        {"result_summary": "Подготовлено 3 черновика, ничего не опубликовано"},
    )
    assert (next_type, status) == ("start_next_automation_cycle", "completed")
    assert payload["cycle_completed"] is True


def test_failed_map_comparison_can_return_to_refresh():
    next_type, status, _due_at, payload = _next_action_spec(
        action("compare_snapshot", "maps", {"refresh_error": "quota"}),
        "retry_refresh",
        {},
    )

    assert (next_type, status) == ("refresh_data", "completed")
    assert payload["verification_status"] == "refresh_retry_requested"
    assert payload["refresh_source_override"] == "yandex_maps"
    assert "refresh_error" not in payload


def test_invalid_transition_is_rejected():
    with pytest.raises(JourneyError) as error:
        _next_action_spec(action("send_message"), "add_result", {})
    assert error.value.code == "transition_not_allowed"


def test_token_hash_is_stable_without_storing_raw_token():
    assert token_hash("secret") == token_hash("secret")
    assert token_hash("secret") != "secret"
    assert token_hash("secret") != token_hash("other")


@pytest.mark.parametrize(
    "row,code",
    [
        ({"id": "journey-1", "status": "revoked", "revoked_at": datetime.now(timezone.utc), "expires_at": datetime.now(timezone.utc) + timedelta(days=1)}, "journey_revoked"),
        ({"id": "journey-1", "status": "preview", "revoked_at": None, "expires_at": datetime.now(timezone.utc) - timedelta(minutes=1)}, "journey_expired"),
    ],
)
def test_public_journey_rejects_revoked_and_expired_links(row, code):
    class Cursor:
        def execute(self, _query, _params):
            return None

        def fetchone(self):
            return row

    with pytest.raises(JourneyError) as error:
        load_public_journey(Cursor(), "secret")

    assert error.value.code == code


def test_claim_rejects_a_journey_reserved_for_another_tenant():
    class Cursor:
        def execute(self, _query, _params):
            return None

        def fetchone(self):
            return {
                "id": "journey-1", "status": "registration_pending", "revoked_at": None,
                "expires_at": datetime.now(timezone.utc) + timedelta(days=1),
                "claimed_user_id": "other-user", "claimed_business_id": "other-business",
                "selected_flow": "maps",
            }

    with pytest.raises(JourneyError) as error:
        claim_journey(Cursor(), token="secret", user_id="user-1", business_id="business-1")

    assert error.value.code == "journey_already_claimed"


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


def test_failed_map_refresh_blocks_comparison_with_provider_error():
    class Cursor:
        queries = []

        def execute(self, query, _params):
            self.queries.append(query)

    cursor = Cursor()

    reconcile_map_actions(cursor, business_ids=["business-1"])

    assert len(cursor.queries) == 2
    assert "SET status = 'blocked'" in cursor.queries[1]
    assert "queue.error_message" in cursor.queries[1]
    assert "queue.status IN ('error', 'failed', 'cancelled')" in cursor.queries[1]


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

    assert len(preview["opportunities"]) == 5
    assert preview["opportunities"][2]["metrics"] == {"rating": 4.8, "reviews_count": 42}
    assert preview["opportunities"][3]["flow_type"] == "content"
    assert "Салон красоты" in preview["opportunities"][3]["reason"]
    assert preview["opportunities"][4]["flow_type"] == "automation"
    assert "prompt" not in preview["opportunities"][4]
    assert "phone" not in preview


def test_lead_preview_uses_real_public_examples_without_contact_fields():
    class Cursor:
        def __init__(self):
            self.rows = [
                {"id": "creator-1", "display_name": "Анна", "description": "Пишет о городе", "primary_city": "Казань", "canonical_url": "https://example.test/anna", "public_metrics_json": {"followers": 1200}, "private_email": "hidden@example.test"},
                {"id": "partner-1", "name": "Кофейня", "category": "Кофе", "city": "Казань", "rating": 4.8, "source_url": "https://example.test/cafe", "phone": "+79990000000"},
                {"id": "item-1", "theme": "Уход после процедуры", "goal": "Ответить на частый вопрос", "draft_text": "Короткий безопасный фрагмент", "scheduled_for": "2026-09-01"},
            ]

        def execute(self, _query, _params):
            return None

        def fetchone(self):
            return self.rows.pop(0)

    preview = build_lead_preview_from_sources(Cursor(), {"id": "lead-1", "name": "Студия", "city": "Казань"})

    assert preview["opportunities"][0]["title"] == "Анна"
    assert preview["opportunities"][0]["public_url"] == "https://example.test/anna"
    assert preview["opportunities"][1]["title"] == "Кофейня"
    assert preview["opportunities"][3]["entity_id"] == "item-1"
    assert "private_email" not in preview["opportunities"][0]
    assert "phone" not in preview["opportunities"][1]


def test_journey_notifications_follow_existing_tasks_preference():
    assert _tasks_enabled({"business:b-1": {"tasks": True}}, "b-1") is True
    assert _tasks_enabled({"business:b-1": {"tasks": False}}, "b-1") is False
    assert _tasks_enabled({"business:b-2": {"tasks": True}}, "b-1") is False


def test_growth_paths_put_focus_action_on_matching_path_and_lock_paid_content():
    actions = [{
        "id": "action-1", "flow_type": "influencer", "status": "ready",
        "reason": "Автор уже выбран", "cta_label": "Открыть автора", "payload": {},
    }]

    paths = build_growth_paths(actions=actions, automation_allowed=False)

    assert [item["flow_type"] for item in paths] == ["maps", "content", "influencer", "partnership", "automation"]
    content = next(item for item in paths if item["flow_type"] == "content")
    influencer = next(item for item in paths if item["flow_type"] == "influencer")
    assert content["access"]["status"] == "payment_required"
    assert content["access"]["cta_target"]["screen"] == "settings"
    assert influencer["action"]["id"] == "action-1"
    assert influencer["access"]["status"] == "available"
    automation = next(item for item in paths if item["flow_type"] == "automation")
    assert automation["access"]["cta_target"]["screen"] == "agents"


def test_reserved_journey_is_resumed_by_bound_user_without_public_token(monkeypatch):
    class Cursor:
        def execute(self, _query, params):
            self.params = params

        def fetchone(self):
            return {"id": "journey-1", "claimed_user_id": "user-1", "claimed_business_id": "business-1", "status": "registration_pending"}

    cursor = Cursor()
    captured = {}

    def claim_loaded(_cursor, **kwargs):
        captured.update(kwargs)
        return {"id": "journey-1"}, {"id": "action-1"}

    monkeypatch.setattr("services.lead_journey_service._claim_loaded_journey", claim_loaded)

    result = claim_reserved_journey(cursor, user_id="user-1")

    assert cursor.params == ("user-1",)
    assert result[1]["id"] == "action-1"
    assert captured["business_id"] == "business-1"


def test_journey_creation_rejects_entity_type_outside_safe_preview():
    with pytest.raises(JourneyError) as error:
        create_lead_journey(
            object(), prospect_lead_id="lead-1", source="admin", selected_flow="content",
            selected_entity_type="creator_collaboration", selected_entity_id="item-1",
            preview={"opportunities": [{
                "flow_type": "content", "entity_type": "contentplanitem", "entity_id": "item-1",
                "title": "Тема", "summary": "Пример", "reason": "Подходит",
            }]},
        )

    assert error.value.code == "selected_entity_mismatch"


def test_stale_action_is_rejected_before_domain_update():
    class Cursor:
        def __init__(self):
            self.rows = [{
                "id": "action-1", "business_id": "business-1", "flow_type": "content",
                "entity_type": "contentplanitem", "entity_id": "item-1", "action_type": "review_content",
                "status": "ready", "version": 3, "payload_json": {},
            }, None]

        def execute(self, _query, _params):
            return None

        def fetchone(self):
            return self.rows.pop(0)

    with pytest.raises(JourneyError) as error:
        execute_command(
            Cursor(), action_id="action-1", business_id="business-1", user_id="user-1",
            command="save_draft", expected_version=2, idempotency_key="request-1",
            surface="web", payload={"draft_text": "Текст"},
        )

    assert error.value.code == "stale_action"


def test_same_idempotency_key_returns_current_action_without_second_transition():
    action_row = {
        "id": "action-1", "business_id": "business-1", "flow_type": "maps",
        "entity_type": "card_audit", "action_type": "complete_map_task",
        "status": "completed", "version": 2, "payload_json": {}, "cta_target_json": {},
    }

    class Cursor:
        def __init__(self):
            self.rows = [action_row, {"id": "event-1"}, action_row, None]

        def execute(self, _query, _params):
            return None

        def fetchone(self):
            return self.rows.pop(0)

    result = execute_command(
        Cursor(), action_id="action-1", business_id="business-1", user_id="user-1",
        command="complete", expected_version=1, idempotency_key="same-request",
        surface="telegram_mini_app", payload={},
    )

    assert result["idempotent_replay"] is True
    assert result["action"]["version"] == 2
