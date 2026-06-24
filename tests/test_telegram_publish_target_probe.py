from messengers_api import _telegram_publish_target_probe_payload


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
    assert "bot token" in payload["message_ru"]
    assert payload["checks"][0]["key"] == "telegram_bot_token"
    assert payload["checks"][1]["key"] == "telegram_chat_id"


def test_telegram_publish_target_probe_payload_ready_guides_to_content_plan_proof():
    payload = _telegram_publish_target_probe_payload(
        "ready",
        True,
        [],
        {"ok": True},
        {"ok": True},
        {"ok": True},
    )

    assert payload["ready"] is True
    assert payload["status"] == "ready"
    assert payload["proof_kind"] == "telegram_publish_target_probe"
    assert "preview" in payload["message_ru"]
    assert "контент-плана" in payload["next_action_ru"]
    assert payload["checks"][2]["ok"] is True
