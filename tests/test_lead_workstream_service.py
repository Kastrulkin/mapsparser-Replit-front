from services.lead_workstream_service import (
    CLIENT_PARTNERSHIP,
    LOCALOS_SALES,
    build_channel_state,
    build_next_action,
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
