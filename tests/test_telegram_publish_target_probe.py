from messengers_api import _resolve_telegram_publish_probe_token, _telegram_publish_target_probe_payload


def test_telegram_publish_target_probe_can_use_global_owner_bot(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "global-token")

    transport = _resolve_telegram_publish_probe_token(None)

    assert transport["bot_token"] == "global-token"
    assert transport["token_source"] == "global_owner_bot"
    assert "глобальный бот LocalOS" in transport["token_label_ru"]


def test_telegram_publish_target_probe_payload_keeps_no_publish_invariant():
    payload = _telegram_publish_target_probe_payload(
        "missing_settings",
        False,
        ["telegram_bot_token", "telegram_chat_id"],
        {},
        {},
        {},
    )

    assert payload["schema"] == "localos_telegram_publish_target_probe_v1"
    assert payload["ready"] is False
    assert payload["missing_fields"] == ["telegram_bot_token", "telegram_chat_id"]
    assert payload["external_post_published"] is False
    assert payload["social_post_published"] is False
    assert payload["send_message_performed"] is False
    assert "bot token" in payload["message_ru"]
    assert "номер телефона" in payload["target_summary_ru"]
    assert payload["target_evidence"]["schema"] == "localos_telegram_publish_target_evidence_v1"
    assert payload["target_evidence"]["not_a_phone_target"] is True
    assert payload["checks"][0]["key"] == "telegram_bot_token"
    assert payload["checks"][1]["key"] == "telegram_chat_id"


def test_telegram_publish_target_probe_payload_ready_guides_to_content_plan_proof():
    payload = _telegram_publish_target_probe_payload(
        "ready",
        True,
        [],
        {"ok": True, "result": {"id": 123, "username": "LocalOspro_bot", "first_name": "LocalOS"}},
        {"ok": True, "result": {"id": -100500, "type": "channel", "title": "LocalOS Proof"}},
        {"ok": True, "result": {"status": "administrator", "can_post_messages": True}},
    )

    assert payload["ready"] is True
    assert payload["status"] == "ready"
    assert payload["proof_kind"] == "telegram_publish_target_probe"
    assert payload["send_message_performed"] is False
    assert payload["target_evidence"]["bot"]["username"] == "LocalOspro_bot"
    assert payload["target_evidence"]["target"]["type"] == "channel"
    assert payload["target_evidence"]["target"]["display_name"] == "LocalOS Proof"
    assert payload["target_evidence"]["permission"]["publish_allowed"] is True
    assert "LocalOS Proof" in payload["target_summary_ru"]
    assert "preview" in payload["message_ru"]
    assert "контент-плана" in payload["next_action_ru"]
    assert payload["checks"][2]["ok"] is True
