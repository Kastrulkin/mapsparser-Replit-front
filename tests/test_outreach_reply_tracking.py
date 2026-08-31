from datetime import datetime, timezone

from services.outreach_reply_tracking_service import (
    _next_action_at,
    business_tracking_enabled,
    normalize_external_peer,
    record_bound_inbound_event,
)
from services.outreach_yougile_sync_service import (
    _deadline,
    _find_existing_task,
    _target_column_id,
    _task_description,
)


def test_external_peer_normalization_is_channel_specific():
    assert normalize_external_peer("email", " Lead@Example.COM ") == "lead@example.com"
    assert normalize_external_peer("telegram", "https://t.me/Partner_Name") == "partner_name"
    assert normalize_external_peer("telegram", "@Partner_Name") == "partner_name"
    assert normalize_external_peer("telegram", "https://t.me/m/private-message") == ""


def test_thread_sync_requires_flag_and_business_allowlist(monkeypatch):
    monkeypatch.setenv("OUTREACH_EMAIL_THREAD_SYNC_ENABLED", "true")
    monkeypatch.setenv("OUTREACH_THREAD_SYNC_BUSINESS_IDS", "business-a,business-b")

    assert business_tracking_enabled("business-a", "email") is True
    assert business_tracking_enabled("business-c", "email") is False
    assert business_tracking_enabled("business-a", "telegram") is False


def test_next_action_defaults_to_next_calendar_day_and_honours_agreed_date():
    occurred_at = datetime(2026, 8, 25, 18, 30, tzinfo=timezone.utc)

    assert _next_action_at("Спасибо, ответим позже", occurred_at) == datetime(
        2026, 8, 26, 10, 0, tzinfo=timezone.utc,
    )
    assert _next_action_at("Давайте встретимся 28.08", occurred_at) == datetime(
        2026, 8, 28, 10, 0, tzinfo=timezone.utc,
    )


def test_bound_inbound_event_accepts_iso_timestamp_from_telegram_subprocess(monkeypatch):
    class Cursor:
        rowcount = 1

        def execute(self, _query, _params=None):
            return None

        def fetchone(self):
            return {"id": "event-1"}

    monkeypatch.setattr(
        "services.outreach_reply_tracking_service.update_binding_cursor",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "services.outreach_reply_tracking_service.upsert_relationship_from_reply",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "services.outreach_reply_tracking_service._room_for_workstream",
        lambda *_args, **_kwargs: None,
    )

    status = record_bound_inbound_event(
        Cursor(),
        binding={
            "id": "binding-1",
            "lead_id": "lead-1",
            "workstream_id": "workstream-1",
            "business_id": "business-1",
        },
        sender_account_id="sender-1",
        channel="telegram",
        provider_event_id="telegram:1:2",
        raw_reply="Давайте завтра",
        classification={
            "classification": "question",
            "is_human": True,
            "stops_campaign": True,
            "confidence": 1.0,
        },
        occurred_at="2026-08-28T10:15:00+00:00",
    )

    assert status == "recorded"


def test_yougile_deadline_is_calendar_day_payload():
    value = _deadline("2026-08-26T10:00:00+00:00")

    assert value == {"deadline": 1787738400000, "withTime": False}


def test_yougile_finds_one_existing_lead_task_without_renaming_it():
    tasks = [
        {"id": "other", "title": "Оценить предложение УК «Старт»"},
        {"id": "match", "title": "Проверить ответ ЖК START после email-касания"},
    ]

    assert _find_existing_task(tasks, "ЖК START") == tasks[1]


def test_yougile_rejects_ambiguous_partial_task_matches():
    tasks = [
        {"id": "one", "title": "Ответ ЖК START"},
        {"id": "two", "title": "Фоллоу-ап ЖК START"},
    ]

    try:
        _find_existing_task(tasks, "ЖК START")
    except RuntimeError as exc:
        assert str(exc) == "yougile_task_ambiguous"
    else:
        raise AssertionError("Ambiguous task matches must stop automatic synchronization")


def test_yougile_projects_touch_number_without_creating_another_deal():
    config = {
        "touch_column_ids": {"1": "column-first", "2": "column-second"},
        "conversation_column_id": "column-conversation",
    }

    assert _target_column_id(
        config,
        {"event_kind": "touch_sent", "touch_number": 2},
    ) == "column-second"
    assert _target_column_id(
        {"conversation_column_id": "column-conversation"},
        {"event_kind": "touch_sent", "touch_number": 2},
    ) is None
    assert "2-е касание" in _task_description(
        {"event_kind": "touch_sent", "touch_number": 2, "channel": "vk"}
    )


def test_yougile_reply_keeps_response_touch_number_in_description():
    description = _task_description(
        {
            "event_kind": "inbound_reply",
            "touch_number": 3,
            "channel": "email",
            "reply_excerpt": "Интересно",
        }
    )

    assert "Ответили после 3-го касания" in description
    assert "Ответ: Интересно" in description
