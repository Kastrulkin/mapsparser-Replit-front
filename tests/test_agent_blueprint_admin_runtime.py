from api.agent_blueprints_api import _admin_agent_connection_summary, _build_admin_agent_review


def test_admin_review_uses_compiled_actions_instead_of_negative_description_words():
    review = _build_admin_agent_review(
        {
            "name": "Ежедневная внутренняя сводка",
            "description": "Ничего не публиковать и не отправлять.",
            "steps_json": [
                {"key": "read", "type": "artifact", "artifact_type": "agent_extracted_context"},
                {"key": "save", "type": "artifact", "artifact_type": "agent_final_result"},
            ],
            "capability_allowlist_json": [],
            "approval_policy_json": {},
            "metadata_json": {"required_integration_bindings": []},
        }
    )

    assert review == {
        "risk_level": "low",
        "risk_reasons": ["явных внешних или опасных действий не найдено"],
    }


def test_admin_review_marks_compiled_external_write_as_high_risk():
    review = _build_admin_agent_review(
        {
            "steps_json": [
                {
                    "key": "request_telegram",
                    "type": "capability",
                    "capability": "communications.draft",
                    "requires_approval": True,
                }
            ],
            "capability_allowlist_json": ["communications.draft"],
            "metadata_json": {
                "required_integration_bindings": [
                    {"key": "telegram_delivery", "provider": "telegram", "direction": "external_write"}
                ]
            },
        }
    )

    assert review["risk_level"] == "high"
    assert "внешняя отправка" in review["risk_reasons"]


def test_admin_review_does_not_treat_internal_message_draft_as_external_send():
    review = _build_admin_agent_review(
        {
            "steps_json": [
                {"key": "draft", "type": "capability", "capability": "communications.draft"}
            ],
            "capability_allowlist_json": ["communications.draft"],
            "metadata_json": {"required_integration_bindings": []},
        }
    )

    assert review["risk_level"] == "low"
    assert review["risk_reasons"] == ["явных внешних или опасных действий не найдено"]


def test_admin_connection_summary_only_counts_bindings_of_current_agent():
    summary = _admin_agent_connection_summary(
        {
            "metadata_json": {
                "agent_integration_ids": ["sheet-1"],
                "agent_binding_integrations": {
                    "google_sheets_read": {
                        "integration_id": "sheet-1",
                        "provider": "google_sheets",
                        "status": "active",
                    }
                },
            }
        },
        {"sheet-1": "google_sheets", "unrelated-telegram": "telegram"},
    )

    assert summary == {"integration_count": 1, "integration_providers": "google_sheets"}


def test_admin_connection_summary_does_not_inherit_business_integrations():
    summary = _admin_agent_connection_summary(
        {"metadata_json": {}},
        {"unrelated-sheet": "google_sheets"},
    )

    assert summary == {"integration_count": 0, "integration_providers": ""}


def test_admin_connection_summary_ignores_stale_binding_metadata():
    summary = _admin_agent_connection_summary(
        {
            "metadata_json": {
                "agent_binding_integrations": {
                    "google_sheets_read": {
                        "integration_id": "deleted-sheet",
                        "provider": "google_sheets",
                        "status": "active",
                    }
                },
            }
        },
        {},
    )

    assert summary == {"integration_count": 0, "integration_providers": ""}
