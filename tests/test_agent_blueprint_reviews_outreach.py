import json
from datetime import datetime, timezone
from pathlib import Path

from tests.agent_blueprint_fakes import *  # noqa: F403


def test_agent_version_diff_shows_readable_changes():
    from services.agent_blueprint_workspace import build_agent_version_diff

    first_version = {
        "id": "ver1",
        "version_number": 1,
        "goal": "Проверить договор",
        "inputs_schema_json": {"agent_setup": {"processing_rules": "Показывать риски"}},
        "steps_json": [{"key": "prepare_output", "type": "artifact"}],
        "capability_allowlist_json": [],
        "approval_policy_json": {"required_for": ["final_output"]},
        "output_schema_json": {"format": "summary"},
    }
    second_version = {
        "id": "ver2",
        "version_number": 2,
        "goal": "Проверить договор и выделить санкции",
        "inputs_schema_json": {"agent_setup": {"processing_rules": "Показывать риски и санкции отдельно"}},
        "steps_json": [{"key": "prepare_output", "type": "artifact"}],
        "capability_allowlist_json": [],
        "approval_policy_json": {"required_for": ["final_output"]},
        "output_schema_json": {"format": "summary", "feedback_history": [{"feedback": "Выделяй санкции"}]},
    }

    diff = build_agent_version_diff(first_version, second_version)

    assert diff["change_type"] == "changed"
    assert "goal" in diff["changed_fields"]
    assert "inputs_schema" in diff["changed_fields"]
    assert "output_schema" in diff["changed_fields"]
    assert diff["summary"].startswith("Изменено:")


def test_agent_learning_loop_summary_requires_human_activation():
    from services.agent_blueprint_workspace import build_agent_version_diff, build_learning_loop_summary

    previous_version = {
        "id": "ver1",
        "version_number": 1,
        "goal": "Напоминать клиентам о записи",
        "inputs_schema_json": {},
        "steps_json": [{"key": "draft", "type": "artifact"}],
        "capability_allowlist_json": ["communications.draft"],
        "approval_policy_json": {"required_for": ["final_output"]},
        "output_schema_json": {"format": "drafts"},
    }
    candidate_version = {
        "id": "ver2",
        "version_number": 2,
        "goal": "Напоминать клиентам о записи",
        "inputs_schema_json": {},
        "steps_json": [{"key": "draft", "type": "artifact"}],
        "capability_allowlist_json": ["communications.draft"],
        "approval_policy_json": {"required_for": ["final_output"], "last_feedback_requires_review": True},
        "output_schema_json": {
            "format": "drafts",
            "feedback_history": [{"feedback": "Не обещать скидку без пакета"}],
        },
    }
    feedback = {
        "run_id": "run1",
        "trigger_type": "manual_edit",
        "feedback": "Не обещать скидку без пакета",
    }

    diff = build_agent_version_diff(previous_version, candidate_version)
    learning = build_learning_loop_summary(feedback, previous_version, candidate_version, diff)

    assert learning["schema"] == "agent_learning_loop_v1"
    assert learning["mode"] == "versioned_review"
    assert learning["trigger_label"] == "Ручная правка текста"
    assert learning["activation_state"] == "candidate"
    assert learning["human_gate_required"] is True
    assert learning["candidate_version_id"] == "ver2"
    assert "activate" in learning["available_actions"]
    assert "rollback" in learning["available_actions"]
    assert learning["diff"]["change_type"] == "changed"


def test_agent_run_review_journal_is_human_readable():
    from services.agent_blueprint_workspace import _review_journal

    journal = _review_journal(
        {"id": "run1", "input_json": {"source": "smoke"}},
        [
            {
                "artifact_type": "agent_output_draft",
                "payload_json": {
                    "status": "generated",
                    "analysis_source": "gigachat",
                    "llm_analysis_used": True,
                    "provenance": ["contract.txt"],
                    "external_dispatch_performed": False,
                    "result": {
                        "title": "Разбор документа",
                        "facts": ["Оплата 10000"],
                        "risks": ["Штраф 10%"],
                        "next_questions": ["Кто подписывает?"],
                    },
                },
            }
        ],
        [{"id": "approval1", "status": "pending", "title": "Подтвердить результат", "approval_type": "final_output", "payload_json": {}}],
        {
            "agent_setup": {
                "workflow_description": "Проверить договор",
                "processing_rules": "Не придумывать факты",
                "output_format": "summary/risks",
            },
            "agent_sources": [{"name": "contract.txt", "source_type": "file"}],
        },
    )

    kinds = [item["kind"] for item in journal]
    assert "input" in kinds
    assert "output" in kinds
    assert "approval" in kinds
    output_entry = [item for item in journal if item["kind"] == "output"][0]
    detail_labels = [item["label"] for item in output_entry["details"]]
    assert "Источник анализа" in detail_labels
    assert "Использованные источники" in detail_labels
    assert "Внешняя отправка" in detail_labels
    assert output_entry["payload"]["external_dispatch_performed"] is False


def test_agent_review_tracks_sources_used_by_latest_run():
    from services.agent_blueprint_workspace import _used_source_summaries

    used_sources = _used_source_summaries(
        {
            "agent_sources": [
                {
                    "id": "source-contract",
                    "name": "contract.txt",
                    "source_type": "file",
                    "file_name": "contract.txt",
                    "extraction_state": "ready",
                    "content_length": 120,
                },
                {
                    "id": "source-unused",
                    "name": "unused.txt",
                    "source_type": "file",
                    "extraction_state": "ready",
                },
            ],
        },
        [
            {
                "artifact_type": "agent_extracted_context",
                "payload_json": {
                    "items": [{"source_name": "contract.txt", "summary": "Оплата 10000"}],
                },
            },
            {
                "artifact_type": "agent_output_draft",
                "payload_json": {
                    "provenance": ["contract.txt"],
                    "result": {"summary": ["Оплата 10000"]},
                },
            },
        ],
    )

    assert len(used_sources) == 1
    assert used_sources[0]["name"] == "contract.txt"
    assert used_sources[0]["source_type"] == "file"
    assert used_sources[0]["content_length"] == 120


def test_outreach_run_review_journal_explains_pipeline_and_queue_boundary():
    from services.agent_blueprint_workspace import _review_journal

    journal = _review_journal(
        {"id": "run1", "input_json": {"source": "yandex_maps", "city": "Moscow", "limit": 5}},
        [
            {
                "artifact_type": "lead_source_plan",
                "payload_json": {
                    "status": "hydrated",
                    "source": "prospectingleads",
                    "count": 1,
                    "filters": {"source": "yandex_maps", "city": "Moscow", "intent": "client_outreach", "limit": 5},
                    "status_counts": {"new": 1},
                    "items": [{"id": "lead1", "name": "Fresh Lead", "status": "new"}],
                },
            },
            {
                "artifact_type": "lead_shortlist",
                "payload_json": {
                    "status": "hydrated",
                    "source": "prospectingleads",
                    "source_artifact": "lead_source_plan",
                    "count": 1,
                    "items": [{"id": "lead1", "name": "Fresh Lead", "selected_channel": "email"}],
                },
            },
            {
                "artifact_type": "message_drafts",
                "payload_json": {
                    "status": "hydrated",
                    "source": "outreachmessagedrafts",
                    "count": 1,
                    "items": [{"id": "draft1", "lead_name": "Fresh Lead", "channel": "email", "status": "generated"}],
                },
            },
            {
                "artifact_type": "outreach_outcomes",
                "payload_json": {
                    "status": "hydrated",
                    "source": "outreachsendqueue",
                    "count": 1,
                    "queued_count": 1,
                    "dispatch_state": "queued_not_dispatched",
                    "external_dispatch_performed": False,
                    "operator_note": "Queue rows are LocalOS handoff records. External dispatcher is a separate contour.",
                    "items": [{"id": "queue1", "delivery_status": "queued"}],
                },
            },
        ],
        [],
        {
            "agent_setup": {
                "workflow_description": "Найти клиентов и подготовить сообщения",
                "manual_control": "Подтверждать shortlist и черновики",
            },
        },
    )

    kinds = [item["kind"] for item in journal]
    assert "sourcing" in kinds
    assert "shortlist" in kinds
    assert "drafts" in kinds
    assert "queue" in kinds
    sourcing_labels = [item["label"] for item in [entry for entry in journal if entry["kind"] == "sourcing"][0]["details"]]
    shortlist_labels = [item["label"] for item in [entry for entry in journal if entry["kind"] == "shortlist"][0]["details"]]
    draft_labels = [item["label"] for item in [entry for entry in journal if entry["kind"] == "drafts"][0]["details"]]
    queue_labels = [item["label"] for item in [entry for entry in journal if entry["kind"] == "queue"][0]["details"]]
    assert "Источник данных" in sourcing_labels
    assert "Найдено лидов" in sourcing_labels
    assert "Лидов в shortlist" in shortlist_labels
    assert "Черновиков" in draft_labels
    assert "В очереди" in queue_labels
    assert "Dispatch" in queue_labels
    assert "Внешняя отправка" in queue_labels


def test_outreach_send_batch_handler_queues_approved_drafts_without_external_dispatch(monkeypatch):
    from services import outreach_send_capability

    connection = FakeOutreachConnection(
        [
            {
                "id": "draft1",
                "lead_id": "lead1",
                "channel": "email",
                "email": "owner@example.com",
            }
        ]
    )
    monkeypatch.setattr(outreach_send_capability, "get_db_connection", lambda: connection)

    result = outreach_send_capability.handle_outreach_send_batch(
        {
            "tenant_id": "biz1",
            "actor": {"user_id": "user1"},
            "payload": {"draft_ids": ["draft1"], "daily_limit": 99},
        },
        {"user_id": "user1"},
    )

    output = result["result"]
    assert output["status"] == "queued_for_dispatch"
    assert output["queue_count"] == 1
    assert output["draft_ids"] == ["draft1"]
    assert output["daily_limit"] == 10
    assert output["dispatch_state"] == "queued_not_dispatched"
    assert output["dispatcher_required"] is True
    assert output["external_dispatch_performed"] is False
    assert "External dispatcher did not run" in output["operator_note"]
    assert connection.committed is True
    assert any(item["kind"] == "batch" and item["status"] == "approved" for item in connection.inserted)
    assert any(item["kind"] == "queue" and item["draft_id"] == "draft1" for item in connection.inserted)


def test_runner_stops_on_first_approval_step():
    from services.agent_blueprint_runner import AgentBlueprintRunner, default_supervised_outreach_version_payload

    cursor = FakeCursor()
    cursor.tables["agent_blueprints"]["bp1"] = {
        "id": "bp1",
        "business_id": "biz1",
        "name": "Outreach",
        "category": "outreach",
    }
    cursor.tables["agent_blueprint_versions"]["ver1"] = {
        "id": "ver1",
        "blueprint_id": "bp1",
        "steps_json": default_supervised_outreach_version_payload()["steps"],
        "capability_allowlist_json": ["outreach.send_batch"],
    }

    result = AgentBlueprintRunner(cursor).start_run("ver1", {"limit": 30}, {"user_id": "user1"})

    assert result["success"] is True
    run = result["run"]
    assert run["status"] == "waiting_approval"
    assert [step["step_key"] for step in run["steps"]] == ["source_leads", "shortlist", "approve_shortlist"]
    assert run["approvals"][0]["approval_type"] == "shortlist"
    assert run["approvals"][0]["status"] == "pending"


def test_runner_blocks_send_capability_without_required_drafts_approval():
    from services.agent_blueprint_runner import AgentBlueprintRunner

    cursor = FakeCursor()
    cursor.tables["agent_runs"]["run1"] = {
        "id": "run1",
        "blueprint_id": "bp1",
        "blueprint_version_id": "ver1",
        "business_id": "biz1",
        "status": "running",
        "input_json": {"draft_ids": ["draft1"]},
        "output_json": {},
        "created_by_user_id": "user1",
    }
    cursor.tables["agent_blueprint_versions"]["ver1"] = {
        "id": "ver1",
        "blueprint_id": "bp1",
        "steps_json": [],
        "capability_allowlist_json": ["outreach.send_batch"],
    }
    cursor.tables["agent_approvals"]["approval1"] = {
        "id": "approval1",
        "run_id": "run1",
        "step_id": "step1",
        "status": "approved",
        "approval_type": "shortlist",
        "title": "Shortlist approved",
        "payload_json": {},
        "requested_by_user_id": "user1",
    }
    orchestrator = CountingOrchestrator()
    step = {
        "key": "send_limited_batch",
        "type": "capability",
        "capability": "outreach.send_batch",
        "requires_approval": True,
        "required_approval_type": "drafts",
        "payload": {"daily_limit": 10},
    }

    completed = AgentBlueprintRunner(cursor, orchestrator=orchestrator)._execute_capability_step(
        cursor.tables["agent_runs"]["run1"],
        cursor.tables["agent_blueprint_versions"]["ver1"],
        step,
        5,
        {"user_id": "user1"},
    )

    assert completed is False
    assert orchestrator.calls == 0
    assert cursor.tables["agent_runs"]["run1"]["status"] == "failed"
    blocked_steps = [item for item in cursor.tables["agent_run_steps"].values() if item["status"] == "blocked"]
    assert blocked_steps
    assert blocked_steps[0]["output_json"]["required_approval_type"] == "drafts"


def test_runner_creates_drafts_after_shortlist_approval_and_queues_after_drafts_approval():
    from services.agent_blueprint_runner import AgentBlueprintRunner, default_supervised_outreach_version_payload

    cursor = FakeCursor()
    cursor.tables["agent_blueprints"]["bp1"] = {
        "id": "bp1",
        "business_id": "biz1",
        "name": "Outreach",
        "category": "outreach",
    }
    cursor.tables["agent_blueprint_versions"]["ver1"] = {
        "id": "ver1",
        "blueprint_id": "bp1",
        "steps_json": default_supervised_outreach_version_payload()["steps"],
        "capability_allowlist_json": ["outreach.send_batch"],
    }
    cursor.tables["prospectingleads"]["lead1"] = {
        "id": "lead1",
        "business_id": "biz1",
        "name": "Lead One",
        "category": "beauty",
        "city": "Moscow",
        "email": "owner@example.com",
        "status": "shortlist_approved",
        "selected_channel": "",
        "pipeline_status": "in_progress",
    }
    orchestrator = CountingOrchestrator()
    runner = AgentBlueprintRunner(cursor, orchestrator=orchestrator)

    result = runner.start_run("ver1", {"lead_ids": ["lead1"], "limit": 5}, {"user_id": "user1"})
    run = result["run"]
    source_artifact = [item for item in run["artifacts"] if item["artifact_type"] == "lead_source_plan"][-1]
    assert source_artifact["payload_json"]["source"] == "prospectingleads"
    assert source_artifact["payload_json"]["status"] == "hydrated"
    assert source_artifact["payload_json"]["count"] == 1
    assert source_artifact["payload_json"]["filters"]["lead_ids"] == ["lead1"]
    shortlist_approval = run["approvals"][0]
    assert shortlist_approval["payload_json"]["artifact_type"] == "lead_shortlist"
    assert shortlist_approval["payload_json"]["count"] == 1

    after_shortlist = runner.approve(run["id"], shortlist_approval["id"], {"user_id": "user1"})
    draft_approval = after_shortlist["run"]["approvals"][-1]
    assert draft_approval["approval_type"] == "drafts"
    assert draft_approval["payload_json"]["artifact_type"] == "message_drafts"
    assert draft_approval["payload_json"]["count"] == 1
    draft_id = draft_approval["payload_json"]["items"][0]["id"]
    assert cursor.tables["outreachmessagedrafts"][draft_id]["status"] == "generated"
    assert cursor.tables["prospectingleads"]["lead1"]["status"] == "channel_selected"

    after_drafts = runner.approve(after_shortlist["run"]["id"], draft_approval["id"], {"user_id": "user1"})

    assert after_drafts["run"]["status"] == "completed"
    assert cursor.tables["outreachmessagedrafts"][draft_id]["status"] == "approved"
    assert cursor.tables["prospectingleads"]["lead1"]["status"] == "draft_ready"
    assert orchestrator.calls == 1
    assert orchestrator.last_envelope["capability"] == "outreach.send_batch"
    assert orchestrator.last_envelope["payload"]["draft_ids"] == [draft_id]
    assert orchestrator.last_envelope["payload"]["daily_limit"] == 10


def test_runner_creates_maton_delivery_preview_draft_without_dispatch(monkeypatch):
    from services import agent_blueprint_runner
    from services.agent_blueprint_runner import AgentBlueprintRunner

    def _fail_dispatch(*args, **kwargs):
        raise AssertionError("Maton dispatch must not run during safe preview")

    monkeypatch.setattr(agent_blueprint_runner, "dispatch_with_routing", _fail_dispatch)

    cursor = FakeCursor()
    cursor.tables["agent_blueprints"]["bp1"] = {
        "id": "bp1",
        "business_id": "biz1",
        "name": "Maton delivery",
        "category": "communications",
        "metadata_json": {
            "connector_action_handlers": {
                "telegram_delivery": {
                    "handler": "maton_external_account_bridge",
                    "external_account_id": "maton-account-1",
                },
            },
            "agent_binding_provider_routes": {
                "telegram_delivery": {
                    "provider": "maton",
                    "external_account_id": "maton-account-1",
                },
            },
        },
    }
    cursor.tables["agent_blueprint_versions"]["ver1"] = {
        "id": "ver1",
        "blueprint_id": "bp1",
        "steps_json": [],
        "capability_allowlist_json": ["communications.send_offer"],
    }
    cursor.tables["agent_runs"]["run1"] = {
        "id": "run1",
        "blueprint_id": "bp1",
        "blueprint_version_id": "ver1",
        "business_id": "biz1",
        "status": "running",
        "input_json": {"preview_mode": True, "external_side_effects_allowed": False},
        "output_json": {},
        "created_by_user_id": "user1",
    }
    cursor.tables["agent_approvals"]["approval1"] = {
        "id": "approval1",
        "run_id": "run1",
        "step_id": "approval-step",
        "status": "approved",
        "approval_type": "communications_send",
        "title": "Approve send",
        "payload_json": {},
        "requested_by_user_id": "user1",
    }
    orchestrator = CountingOrchestrator()
    step = {
        "key": "send_offer",
        "type": "capability",
        "capability": "communications.send_offer",
        "requires_approval": True,
        "required_approval_type": "communications_send",
        "payload": {
            "message": "Пакетное предложение для клиента",
            "channel": "telegram",
            "telegram_target": "@client",
        },
    }

    completed = AgentBlueprintRunner(cursor, orchestrator=orchestrator)._execute_capability_step(
        cursor.tables["agent_runs"]["run1"],
        cursor.tables["agent_blueprint_versions"]["ver1"],
        step,
        1,
        {"user_id": "user1"},
    )

    assert completed is True
    assert orchestrator.calls == 0
    artifact = next(item for item in cursor.tables["agent_artifacts"].values() if item["artifact_type"] == "maton_delivery_request")
    payload = artifact["payload_json"]
    assert payload["schema"] == "localos_maton_delivery_request_v1"
    assert payload["status"] == "preview_draft_created"
    assert payload["delivery_state"] == "preview_draft_only"
    assert payload["external_dispatch_performed"] is False
    assert payload["external_account_id"] == "maton-account-1"
    delivery_step = next(
        step
        for step in cursor.tables["agent_run_steps"].values()
        if step["step_key"] == "send_offer"
    )
    runtime_contract = delivery_step["output_json"]["production_action_contract"]
    assert runtime_contract["schema"] == "localos_production_action_contract_v1"
    assert runtime_contract["capability"] == "communications.send_offer"
    assert runtime_contract["preflight"]["status"] == "passed"
    assert runtime_contract["approval_policy"]["required"] is True
    assert runtime_contract["approval_policy"]["approval_type"] == "communications_send"
    assert runtime_contract["ledger"]["required"] is True
    assert runtime_contract["recovery"]["state"] == "ready"
    assert runtime_contract["side_effects"]["external_dispatch_performed"] is False


def test_runner_sends_maton_delivery_only_after_approval_and_explicit_dispatch(monkeypatch):
    from services import agent_blueprint_runner
    from services.agent_blueprint_runner import AgentBlueprintRunner

    captured = {}

    def _fake_load_context(cursor, business_id):
        captured["business_id"] = business_id
        return {"id": business_id, "name": "Riderra", "maton_api_key": "key", "maton_bridge_enabled": True}

    def _fake_dispatch(ctx, text, *, preferred_provider="telegram", force_channel_id=None):
        captured["text"] = text
        captured["preferred_provider"] = preferred_provider
        captured["force_channel_id"] = force_channel_id
        return {
            "success": True,
            "selected_channel_id": "maton_bridge",
            "selected_provider": "maton",
            "attempts": [{"channel_id": "maton_bridge", "provider": "maton", "success": True}],
        }

    monkeypatch.setattr(agent_blueprint_runner, "load_business_channel_context", _fake_load_context)
    monkeypatch.setattr(agent_blueprint_runner, "dispatch_with_routing", _fake_dispatch)

    cursor = FakeCursor()
    cursor.tables["agent_blueprints"]["bp1"] = {
        "id": "bp1",
        "business_id": "biz1",
        "name": "Maton delivery",
        "category": "communications",
        "metadata_json": {
            "connector_action_handlers": {
                "telegram_delivery": {
                    "handler": "maton_external_account_bridge",
                    "external_account_id": "maton-account-1",
                },
            },
            "agent_binding_provider_routes": {
                "telegram_delivery": {
                    "provider": "maton",
                    "external_account_id": "maton-account-1",
                },
            },
        },
    }
    cursor.tables["agent_blueprint_versions"]["ver1"] = {
        "id": "ver1",
        "blueprint_id": "bp1",
        "steps_json": [],
        "capability_allowlist_json": ["communications.send_offer"],
    }
    cursor.tables["agent_runs"]["run1"] = {
        "id": "run1",
        "blueprint_id": "bp1",
        "blueprint_version_id": "ver1",
        "business_id": "biz1",
        "status": "running",
        "input_json": {},
        "output_json": {},
        "created_by_user_id": "user1",
    }
    cursor.tables["agent_approvals"]["approval1"] = {
        "id": "approval1",
        "run_id": "run1",
        "step_id": "approval-step",
        "status": "approved",
        "approval_type": "communications_send",
        "title": "Approve send",
        "payload_json": {},
        "requested_by_user_id": "user1",
    }
    step = {
        "key": "send_offer",
        "type": "capability",
        "capability": "communications.send_offer",
        "requires_approval": True,
        "required_approval_type": "communications_send",
        "payload": {
            "message": "Пакетное предложение для клиента",
            "dispatch_mode": "send_after_approval",
            "external_side_effects_allowed": True,
            "telegram_target": "@client",
        },
    }

    completed = AgentBlueprintRunner(cursor, orchestrator=CountingOrchestrator())._execute_capability_step(
        cursor.tables["agent_runs"]["run1"],
        cursor.tables["agent_blueprint_versions"]["ver1"],
        step,
        1,
        {"user_id": "user1"},
    )

    assert completed is True
    assert captured["business_id"] == "biz1"
    assert captured["text"] == "Пакетное предложение для клиента"
    assert captured["preferred_provider"] == "maton"
    assert captured["force_channel_id"] == "maton_bridge"
    artifact = next(item for item in cursor.tables["agent_artifacts"].values() if item["artifact_type"] == "maton_delivery_request")
    payload = artifact["payload_json"]
    assert payload["status"] == "sent"
    assert payload["delivery_state"] == "sent"
    assert payload["external_dispatch_performed"] is True
    assert payload["router_result"]["selected_channel_id"] == "maton_bridge"


def test_default_runner_is_wired_to_real_google_sheets_and_finance_handlers():
    from services.agent_blueprint_runner import AgentBlueprintRunner

    runner = AgentBlueprintRunner(FakeCursor())

    assert "google_sheets.read_rows" in runner.orchestrator.handlers
    assert "finance.transaction.create" in runner.orchestrator.handlers


def test_runner_build_capability_payload_hydrates_google_sheets_binding_from_metadata():
    from services.agent_blueprint_runner import AgentBlueprintRunner

    cursor = FakeCursor()
    cursor.tables["agent_blueprints"]["bp1"] = {
        "id": "bp1",
        "business_id": "biz1",
        "metadata_json": {
            "required_integration_bindings": [
                {
                    "key": "google_sheets_read",
                    "provider": "google_sheets",
                    "capability": "google_sheets.read_rows",
                    "required_config": ["spreadsheet_id", "sheet_name"],
                }
            ],
            "custom_process": {
                "google_sheets_read": {
                    "integration_id": "integration-1",
                    "spreadsheet_id": "spreadsheet-1",
                    "sheet_name": "Trips",
                }
            },
        },
    }
    run = {
        "id": "run1",
        "blueprint_id": "bp1",
        "input_json": {},
    }
    step = {
        "key": "read_google_sheets",
        "type": "capability",
        "capability": "google_sheets.read_rows",
        "payload": {
            "integration_binding": "google_sheets_read",
            "limit": 100,
        },
    }

    payload = AgentBlueprintRunner(cursor)._build_capability_payload(run, step)

    assert payload["integration_id"] == "integration-1"
    assert payload["spreadsheet_id"] == "spreadsheet-1"
    assert payload["sheet_name"] == "Trips"


def test_runner_passes_compiled_step_rows_to_next_capability_without_runtime_ai():
    from services.agent_blueprint_runner import AgentBlueprintRunner

    class FinanceCaptureOrchestrator:
        def __init__(self):
            self.calls = []

        def execute(self, envelope, user_data, *, allow_execute_when_approved=False):
            self.calls.append(envelope)
            return {
                "success": True,
                "status": "completed",
                "result": {
                    "status": "finance_transaction_request_created",
                    "proposal_count": len(envelope["payload"].get("rows") or []),
                    "rows": envelope["payload"].get("rows") or [],
                    "localos_write_performed": False,
                },
            }

    cursor = FakeCursor()
    cursor.tables["agent_runs"]["run1"] = {
        "id": "run1",
        "blueprint_id": "bp1",
        "blueprint_version_id": "ver1",
        "business_id": "biz1",
        "status": "running",
        "input_json": {
            "preview_mode": True,
            "external_side_effects_allowed": False,
            "goal": "Проверить таблицу и подготовить действие",
            "preview_context": {
                "understood_task": "Проверить Google Sheets и показать append request",
                "data_sources": ["Google Sheets", "Telegram"],
                "manual_control": "Подтвердить перед записью в таблицу.",
            },
        },
        "output_json": {},
        "created_by_user_id": "user1",
    }
    cursor.tables["agent_blueprint_versions"]["ver1"] = {
        "id": "ver1",
        "blueprint_id": "bp1",
        "steps_json": [],
        "capability_allowlist_json": ["google_sheets.read_rows", "finance.transaction.create"],
    }
    cursor.tables["agent_run_steps"]["read-step"] = {
        "id": "read-step",
        "run_id": "run1",
        "step_index": 0,
        "step_key": "read_google_sheets",
        "step_type": "capability",
        "status": "completed",
        "input_json": {},
        "output_json": {
            "capability": "google_sheets.read_rows",
            "orchestrator": {
                "success": True,
                "result": {
                    "status": "read_completed",
                    "rows": [{"row_number": 2, "date": "2026-06-09", "type": "revenue", "amount": "12000"}],
                },
            },
        },
    }
    cursor.tables["agent_approvals"]["approval1"] = {
        "id": "approval1",
        "run_id": "run1",
        "step_id": "approval-step",
        "status": "approved",
        "approval_type": "finance_transaction_import",
        "title": "Approved",
        "payload_json": {},
        "requested_by_user_id": "user1",
    }
    orchestrator = FinanceCaptureOrchestrator()
    step = {
        "key": "request_localos_finance",
        "type": "capability",
        "capability": "finance.transaction.create",
        "requires_approval": True,
        "required_approval_type": "finance_transaction_import",
        "payload": {
            "input_mappings": [
                {
                    "target": "rows",
                    "from_step": "read_google_sheets",
                    "path": "orchestrator.result.rows",
                    "required": True,
                }
            ],
            "rows_from_step": "read_google_sheets",
            "localos_write_performed": False,
        },
    }

    completed = AgentBlueprintRunner(cursor, orchestrator=orchestrator)._execute_capability_step(
        cursor.tables["agent_runs"]["run1"],
        cursor.tables["agent_blueprint_versions"]["ver1"],
        step,
        3,
        {"user_id": "user1"},
    )

    assert completed is True
    assert len(orchestrator.calls) == 1
    assert orchestrator.calls[0]["capability"] == "finance.transaction.create"
    assert orchestrator.calls[0]["payload"]["rows"][0]["amount"] == "12000"
    assert "input_mappings" not in orchestrator.calls[0]["payload"]
    assert "rows_from_step" not in orchestrator.calls[0]["payload"]
    assert "gigachat" not in json.dumps(orchestrator.calls[0], ensure_ascii=False).lower()
    finance_step = next(
        step
        for step in cursor.tables["agent_run_steps"].values()
        if step["step_key"] == "request_localos_finance"
    )
    assert finance_step["output_json"]["approved_executor"]["localos_writes_performed"] is False
    runtime_contract = finance_step["output_json"]["production_action_contract"]
    assert runtime_contract["schema"] == "localos_production_action_contract_v1"
    assert runtime_contract["capability"] == "finance.transaction.create"
    assert runtime_contract["preflight"]["status"] == "passed"
    assert runtime_contract["approval_policy"]["required"] is True
    assert runtime_contract["approval_policy"]["approval_type"] == "finance_transaction_import"
    assert runtime_contract["ledger"]["required"] is True
    assert runtime_contract["limits"]["subscription_checked"] is True
    assert runtime_contract["recovery"]["idempotency_key"] == "agent-run:run1:request_localos_finance"
    assert runtime_contract["side_effects"]["localos_write_performed"] is False
    assert cursor.tables["finance_entries"] == {}


def test_runner_applies_finance_requests_only_after_explicit_apply():
    from services.agent_blueprint_runner import AgentBlueprintRunner

    class FinanceProposalOrchestrator:
        def execute(self, envelope, user_data, *, allow_execute_when_approved=False):
            return {
                "success": True,
                "status": "completed",
                "action_id": "action-finance-1",
                "result": {
                    "status": "finance_transaction_request_created",
                    "request_id": "finance-request-1",
                    "source": "google_sheets",
                    "normalized_mapping": {"amount": "amount"},
                    "proposal_count": 1,
                    "finance_entry_proposals": [
                        {
                            "record_type": "entry",
                            "date": "2026-06-09",
                            "type": "revenue",
                            "category": "sales",
                            "amount": 12000,
                            "comment": "Оплата по таблице",
                            "row_number": 1,
                            "duplicate_key": "finance-dup-apply-1",
                        }
                    ],
                    "rows_requiring_review": [],
                    "errors": [],
                    "approval_state": "pending_human",
                    "apply_state": "not_applied",
                    "localos_write_performed": False,
                },
            }

        def get_action_support_package(self, action_id, user_data, limit=100, full=False):
            return {
                "action_id": action_id,
                "action": {"status": "completed", "capability": "finance.transaction.create"},
                "timeline": {"count": 0, "events": []},
                "billing_summary": {},
                "delivery_stats": {},
            }

    cursor = FakeCursor()
    cursor.tables["agent_runs"]["run1"] = {
        "id": "run1",
        "blueprint_id": "bp1",
        "blueprint_version_id": "ver1",
        "business_id": "biz1",
        "status": "running",
        "input_json": {"preview_mode": False},
        "output_json": {},
        "created_by_user_id": "user1",
    }
    cursor.tables["agent_blueprint_versions"]["ver1"] = {
        "id": "ver1",
        "blueprint_id": "bp1",
        "steps_json": [],
        "capability_allowlist_json": ["finance.transaction.create"],
    }
    cursor.tables["agent_approvals"]["approval1"] = {
        "id": "approval1",
        "run_id": "run1",
        "step_id": "approval-step",
        "status": "approved",
        "approval_type": "finance_transaction_import",
        "title": "Approved",
        "payload_json": {},
        "requested_by_user_id": "user1",
    }
    step = {
        "key": "request_localos_finance",
        "type": "capability",
        "capability": "finance.transaction.create",
        "requires_approval": True,
        "required_approval_type": "finance_transaction_import",
        "payload": {"rows": [{"amount": 12000}]},
    }
    runner = AgentBlueprintRunner(cursor, orchestrator=FinanceProposalOrchestrator())

    completed = runner._execute_capability_step(
        cursor.tables["agent_runs"]["run1"],
        cursor.tables["agent_blueprint_versions"]["ver1"],
        step,
        1,
        {"user_id": "user1"},
    )
    run_before_apply = runner.load_run("run1", {"user_id": "user1"})
    finance_request = run_before_apply["observability"]["domain_requests"]["items"][0]

    assert completed is True
    assert cursor.tables["finance_entries"] == {}
    assert finance_request["kind"] == "finance_transaction_request"
    assert finance_request["approval_state"] == "approved"
    assert finance_request["apply_state"] == "apply_ready"
    assert finance_request["can_apply"] is True

    result = runner.apply_finance_requests("run1", {"user_id": "user1"})

    assert result["success"] is True
    assert result["items"][0]["apply_state"] == "applied"
    assert len(cursor.tables["finance_entries"]) == 1
    assert next(iter(cursor.tables["finance_entries"].values()))["duplicate_key"] == "finance-dup-apply-1"
    assert cursor.ledger_entries[0]["capability"] == "finance.transaction.create"
    finance_step = next(
        step
        for step in cursor.tables["agent_run_steps"].values()
        if step["step_key"] == "request_localos_finance"
    )
    assert finance_step["output_json"]["approved_executor"]["localos_writes_performed"] is True


def test_runner_builds_finance_outcome_artifact_from_compiled_step_outputs():
    from services.agent_blueprint_runner import AgentBlueprintRunner

    cursor = FakeCursor()
    cursor.tables["agent_runs"]["run1"] = {
        "id": "run1",
        "blueprint_id": "bp1",
        "blueprint_version_id": "ver1",
        "business_id": "biz1",
        "status": "completed",
        "input_json": {
            "preview_mode": True,
            "external_side_effects_allowed": False,
            "goal": "Проверить таблицу и подготовить действие",
            "preview_context": {
                "understood_task": "Проверить Google Sheets и показать append request",
                "data_sources": ["Google Sheets", "Telegram"],
                "manual_control": "Подтвердить перед записью в таблицу.",
            },
        },
        "output_json": {},
        "created_by_user_id": "user1",
    }
    cursor.tables["agent_run_steps"]["read-step"] = {
        "id": "read-step",
        "run_id": "run1",
        "step_index": 0,
        "step_key": "read_google_sheets",
        "step_type": "capability",
        "status": "completed",
        "input_json": {},
        "output_json": {
            "capability": "google_sheets.read_rows",
            "orchestrator": {
                "success": True,
                "result": {
                    "status": "read_completed",
                    "count": 2,
                    "rows": [
                        {"row_number": 2, "date": "2026-06-09", "type": "revenue", "amount": "12000"},
                        {"row_number": 3, "date": "2026-06-10", "type": "expense", "amount": "2500"},
                    ],
                },
            },
        },
    }
    cursor.tables["agent_run_steps"]["finance-step"] = {
        "id": "finance-step",
        "run_id": "run1",
        "step_index": 3,
        "step_key": "request_localos_finance",
        "step_type": "capability",
        "status": "completed",
        "input_json": {},
        "output_json": {
            "capability": "finance.transaction.create",
            "orchestrator": {
                "success": True,
                "action_id": "action-finance-1",
                "result": {
                    "status": "finance_transaction_request_created",
                    "request_id": "finance-request-1",
                    "proposal_count": 2,
                    "review_count": 1,
                    "error_count": 0,
                    "finance_entry_proposals": [{"row_number": 2}, {"row_number": 3}],
                    "rows_requiring_review": [{"row_number": 3, "review_reasons": ["category_missing_or_default"]}],
                    "errors": [],
                    "approval_state": "pending_human",
                    "apply_state": "not_applied",
                    "localos_write_performed": False,
                },
            },
            "approved_executor": {
                "localos_writes_performed": 2,
                "items": [
                    {
                        "kind": "finance_transaction_request",
                        "batch_id": "batch-1",
                        "rows_imported": 2,
                        "rows_failed": 0,
                        "rows_skipped": 0,
                    }
                ],
            },
        },
    }
    runner = AgentBlueprintRunner(cursor, orchestrator=CountingOrchestrator())

    payload = runner._build_artifact_payload(
        cursor.tables["agent_runs"]["run1"],
        {
            "key": "record_localos_finance_outcome",
            "artifact_type": "localos_finance_outcome",
            "payload": {
                "source_step": "read_google_sheets",
                "request_step": "request_localos_finance",
                "journal": ["rows_read", "proposals", "rows_requiring_review", "errors"],
            },
        },
    )

    assert payload["rows_read"] == 2
    assert payload["proposal_count"] == 2
    assert payload["review_count"] == 1
    assert payload["error_count"] == 0
    assert payload["rows_imported"] == 2
    assert payload["apply_state"] == "applied"
    assert payload["localos_write_performed"] is True
    assert payload["recovery"]["idempotency"] == "rerun uses finance duplicate_key checks before inserting rows"
    assert "gigachat" not in json.dumps(payload, ensure_ascii=False).lower()


def test_finance_outcome_journal_is_human_readable():
    from services.agent_blueprint_workspace import _artifact_journal_entry

    entry = _artifact_journal_entry(
        "localos_finance_outcome",
        {
            "status": "applied",
            "rows_read": 2,
            "proposal_count": 2,
            "review_count": 1,
            "error_count": 0,
            "rows_imported": 2,
            "apply_state": "applied",
            "localos_write_performed": True,
        },
    )

    assert entry["kind"] == "finance_outcome"
    assert entry["title"] == "Итог записи в финансы"
    assert "Записано 2 финансовых строк" in entry["summary"]
    labels = [item["label"] for item in entry["details"]]
    assert "Прочитано строк" in labels
    assert "Требует проверки" in labels
    assert "Запись в LocalOS" in labels
