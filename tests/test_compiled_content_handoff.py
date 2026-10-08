from services.agent_workflow_dsl import build_workflow_dsl_document, validate_workflow_dsl_document
from services.compiled_content_handoff import handoff_scope, has_active_consent, scope_digest
from services.agent_blueprint_creation import _content_handoff_draft
from services.telegram_bot_sender import send_telegram_message_result


def _version():
    return {
        "goal": "Передавать подготовленные публикации получателю",
        "id": "version-1",
        "execution_mode": "scheduled",
        "trigger": "schedule.daily",
        "schedule": {"time": "10:00", "timezone": "Europe/Moscow"},
        "steps": [
            {
                "key": "handoff",
                "type": "capability",
                "capability": "content.publish_handoff",
                "requires_approval": True,
                "required_approval_type": "content_handoff_activation",
                "payload": {
                    "business_id": "business-1",
                    "recipient_user_id": "recipient-1",
                    "platforms": ["telegram", "vk", "max"],
                    "lead_days": 1,
                    "time": "10:00",
                    "timezone": "Europe/Moscow",
                },
            }
        ],
        "capability_allowlist": ["content.publish_handoff"],
        "approval_policy": {"content_handoff_activation": "one_time_exact_scope_consent"},
        "required_integration_bindings": [],
        "limits": {"publication_status_changes": False},
        "output_schema": {"type": "object"},
        "inputs_schema": {"type": "object"},
    }


def test_scope_is_fixed_to_daily_business_time_and_timezone():
    scope = handoff_scope(_version(), "business-1")
    assert scope == {
        "business_id": "business-1",
        "recipient_user_id": "recipient-1",
        "platforms": ["max", "telegram", "vk"],
        "lead_days": 1,
        "time": "10:00",
        "timezone": "Europe/Moscow",
    }
    version = _version()
    version["schedule"]["time"] = "11:00"
    assert handoff_scope(version, "business-1") is None


def test_activation_consent_is_bound_to_version_and_exact_scope():
    scope = handoff_scope(_version(), "business-1")
    digest = scope_digest(version_id="version-1", scope=scope)
    metadata = {"compiled_content_handoff_consent": {"version_id": "version-1", "scope": scope, "scope_digest": digest}}
    assert has_active_consent(metadata, version_id="version-1", scope=scope)
    changed = {**scope, "recipient_user_id": "other-recipient"}
    assert not has_active_consent(metadata, version_id="version-1", scope=changed)
    assert not has_active_consent(metadata, version_id="version-2", scope=scope)


def test_compiled_workflow_accepts_handoff_only_with_activation_gate_and_scope():
    version = _version()
    document = build_workflow_dsl_document(version, {})
    checked = validate_workflow_dsl_document(document)
    assert checked["valid"], checked["errors"]

    version["steps"][0]["required_approval_type"] = "per_run_send"
    version["approval_policy"] = {"per_run_send": "manual"}
    document = build_workflow_dsl_document(version, {})
    checked = validate_workflow_dsl_document(document)
    assert not checked["valid"]
    assert any("one-time activation approval" in item["message"] for item in checked["errors"])


def test_natural_language_pilot_compiles_to_one_fixed_creator_scoped_workflow():
    draft = _content_handoff_draft(
        "За день до публикации в 10:00 отправлять готовые варианты постов через Telegram-бот",
        business_id="business-1",
        recipient_user_id="current-user",
        conditions={"trigger": "schedule.daily", "schedule": {"time": "10:00", "timezone": "Europe/Moscow"}},
    )
    version = draft["version_payload"]
    scope = handoff_scope(version, "business-1")
    assert scope["recipient_user_id"] == "current-user"
    assert scope["platforms"] == ["max", "telegram", "vk"]
    assert draft["metadata"]["compiled_validation"]["valid"]


def test_shared_telegram_sender_preserves_receipt_and_uncertainty_contract(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "synthetic-token")

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"ok":true,"result":{"message_id":42}}'

    calls = []
    result = send_telegram_message_result(
        "test-chat",
        "test text",
        include_outcome=True,
        urlopen=lambda request, timeout: calls.append((request, timeout)) or Response(),
    )
    assert result == {"success": True, "message_id": 42, "reason_code": "", "publish_outcome": "confirmed"}
    assert len(calls) == 1 and calls[0][1] == 10

    unknown = send_telegram_message_result(
        "test-chat",
        "test text",
        include_outcome=True,
        urlopen=lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError()),
    )
    assert unknown["publish_outcome"] == "uncertain"
    assert unknown["success"] is False
