from services.lead_workstream_service import (
    CLIENT_PARTNERSHIP,
    LOCALOS_SALES,
    build_channel_state,
    build_next_action,
    build_readiness_gate,
    build_relationship_stage,
    build_room_state,
    lead_kind,
    legacy_workstream,
    normalize_workstream_type,
)


def test_normalize_workstream_type_preserves_legacy_intents():
    assert normalize_workstream_type("client_outreach") == LOCALOS_SALES
    assert normalize_workstream_type("partnership_outreach") == CLIENT_PARTNERSHIP
    assert normalize_workstream_type("partnership") == CLIENT_PARTNERSHIP
    assert normalize_workstream_type("partner") == CLIENT_PARTNERSHIP
    assert normalize_workstream_type("unknown") is None


def test_legacy_partner_workstream_keeps_client_name():
    workstream = legacy_workstream(
        {
            "id": "lead-1",
            "intent": "partnership_outreach",
            "business_id": "business-1",
            "client_business_name": "Органика",
            "pipeline_status": "in_progress",
        }
    )

    assert workstream["workstream_type"] == CLIENT_PARTNERSHIP
    assert workstream["client_business_id"] == "business-1"
    assert workstream["client_business_name"] == "Органика"


def test_one_company_can_have_localos_and_partner_contexts():
    workstreams = [
        {"workstream_type": LOCALOS_SALES},
        {"workstream_type": CLIENT_PARTNERSHIP, "client_business_name": "Новамед"},
    ]

    assert lead_kind(workstreams) == "both"


def test_channel_state_distinguishes_missing_recipient_and_manual_ready():
    lead = {"email": "owner@example.com"}

    missing = build_channel_state(lead, {"selected_channel": "telegram"})
    ready = build_channel_state(lead, {"selected_channel": "email"})

    assert missing["code"] == "missing_recipient"
    assert missing["label"] == "Нет контакта получателя"
    assert ready["code"] == "manual_ready"
    assert ready["label"] == "Готово к ручной отправке"


def test_room_and_next_action_follow_operator_sequence():
    lead = {"email": "owner@example.com"}
    workstream = {"status": "in_progress", "selected_channel": "email", "room": None}

    assert build_room_state(workstream)["code"] == "missing"
    assert build_next_action(lead, workstream) == {
        "code": "prepare_room",
        "label": "Подготовить комнату",
    }

    workstream["room"] = {
        "status": "invitation_ready",
        "public_url": "https://localos.pro/room/example",
    }
    assert build_room_state(workstream)["label"] == "Готова"
    assert build_next_action(lead, workstream) == {
        "code": "review_message",
        "label": "Проверить сообщение",
    }


def test_contacted_context_does_not_change_other_context_action():
    lead = {"phone": "+79990000000"}
    localos = {"status": "contacted", "selected_channel": "manual", "room": None}
    partner = {"status": "in_progress", "selected_channel": "manual", "room": None}

    assert build_next_action(lead, localos)["code"] == "wait_or_follow_up"
    assert build_next_action(lead, partner)["code"] == "prepare_room"


def test_saved_campaign_becomes_an_explicit_operator_action():
    lead = {"email": "owner@example.com"}
    draft = {
        "status": "in_progress",
        "selected_channel": "email",
        "campaign_state": {"status": "draft", "version": 3},
    }
    active = {
        "status": "in_progress",
        "selected_channel": "email",
        "campaign_state": {"status": "approved", "version": 4},
    }

    assert build_next_action(lead, draft) == {
        "code": "review_draft",
        "label": "Проверить черновик",
    }
    assert build_next_action(lead, active) == {
        "code": "check_campaign",
        "label": "Проверить кампанию",
    }


def test_relationship_stage_preserves_touch_number_and_first_response_touch():
    sent = build_relationship_stage(
        {"campaign_state": {"last_confirmed_touch": {"touch_number": 2, "channel": "vk"}}}
    )
    replied = build_relationship_stage(
        {
            "campaign_state": {
                "last_confirmed_touch": {"touch_number": 3, "channel": "email"},
                "first_human_response": {"touch_number": 2, "channel": "vk"},
            }
        }
    )

    assert sent["label"] == "2-е касание отправлено"
    assert replied["label"] == "Ответили после 2-го касания"
    assert replied["touch_number"] == 2


def test_readiness_gate_exposes_every_blocker_before_send():
    lead = {"email": "owner@example.com"}
    workstream = {
        "selected_channel": "email",
        "selected_recipient": {
            "value": "owner@example.com",
            "verification_status": "verified",
        },
        "research": {"sources": [{"url": "https://example.com"}], "stale": False},
        "campaign_state": {
            "status": "approved",
            "touches_count": 2,
            "sequence_has_gap": False,
            "first_human_response": None,
        },
        "active_suppression": None,
    }

    ready = build_readiness_gate(lead, workstream)
    assert ready["code"] == "ready"
    assert ready["blockers"] == []

    workstream["campaign_state"]["sequence_has_gap"] = True
    workstream["active_suppression"] = {"reason": "unsubscribe"}
    workstream["duplicate_recipient"] = {"other_workstream_id": "workstream-2"}
    blocked = build_readiness_gate(lead, workstream)
    assert blocked["code"] == "needs_attention"
    assert "history" in blocked["blockers"]
    assert "unique_recipient" in blocked["blockers"]
    assert "sequence" in blocked["blockers"]
