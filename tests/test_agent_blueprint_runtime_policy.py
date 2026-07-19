import json
from datetime import datetime, timezone
from pathlib import Path

from tests.agent_blueprint_fakes import *  # noqa: F403


def test_runner_blocks_custom_agent_start_when_required_external_binding_missing():
    from services.agent_blueprint_draft_builder import compile_agent_blueprint
    from services.agent_blueprint_runner import AgentBlueprintRunner

    draft = compile_agent_blueprint(
        "Каждый вечер проверяй Google Sheets, бери новые оплаты и создавай транзакции в финансах LocalOS"
    )
    cursor = FakeCursor()
    cursor.tables["agent_blueprints"]["bp1"] = {
        "id": "bp1",
        "business_id": "biz1",
        "name": "Finance import",
        "category": "custom",
        "metadata_json": draft["metadata"],
    }
    cursor.tables["agent_blueprint_versions"]["ver1"] = {
        "id": "ver1",
        "blueprint_id": "bp1",
        "steps_json": draft["version_payload"]["steps"],
        "capability_allowlist_json": draft["version_payload"]["capability_allowlist"],
    }

    result = AgentBlueprintRunner(cursor, orchestrator=CountingOrchestrator()).start_run("ver1", {}, {"user_id": "user1"})

    assert result["success"] is False
    assert result["code"] == "AGENT_INTEGRATIONS_REQUIRED"
    assert result["preflight"]["status"] == "blocked"
    assert result["preflight"]["missing_count"] == 1
    assert result["preflight"]["missing"][0]["provider"] == "google_sheets"
    assert result["preflight"]["missing"][0]["missing_config"] == ["spreadsheet_id", "sheet_name"]
    assert cursor.tables["agent_runs"] == {}


def test_runner_creates_openclaw_preview_observations_from_route_contract():
    from services.agent_blueprint_runner import AgentBlueprintRunner

    cursor = FakeCursor()
    cursor.tables["agent_blueprints"]["bp1"] = {
        "id": "bp1",
        "business_id": "biz1",
        "name": "Sheets preview",
        "category": "custom",
        "metadata_json": {
            "required_integration_bindings": [
                {
                    "key": "google_sheets_read",
                    "provider": "google_sheets",
                    "capability": "google_sheets.read_rows",
                    "required_config": ["spreadsheet_id", "sheet_name"],
                }
            ],
            "agent_binding_provider_routes": {
                "google_sheets_read": {
                    "route_provider": "openclaw",
                    "status": "active",
                    "integration_id": "openclaw_boundary",
                }
            },
            "agent_binding_integrations": {
                "google_sheets_read": {
                    "route_provider": "openclaw",
                    "status": "active",
                    "integration_id": "openclaw_boundary",
                }
            },
        },
    }
    cursor.tables["agent_blueprint_versions"]["ver1"] = {
        "id": "ver1",
        "blueprint_id": "bp1",
        "steps_json": [],
        "capability_allowlist_json": ["google_sheets.read_rows"],
    }
    orchestrator = CountingOrchestrator()
    result = AgentBlueprintRunner(cursor, orchestrator=orchestrator).start_run(
        "ver1",
        {
            "schema": "localos_agent_preview_input_v1",
            "preview_mode": True,
            "external_side_effects_allowed": False,
            "connector_action_handlers": [
                {
                    "binding_key": "google_sheets_read",
                    "route_provider": "openclaw",
                    "handler": "openclaw_policy_boundary",
                    "credential_source": "openclaw_m2m",
                    "preflight_resolution": "provider_route_openclaw_boundary",
                    "execution_boundary": "localos_policy_envelope",
                    "approval_required": True,
                    "audit_required": True,
                    "external_side_effects_allowed_in_preview": False,
                }
            ],
            "openclaw_preview_routes": [
                {
                    "binding_key": "google_sheets_read",
                    "capability": "google_sheets.read_rows",
                    "provider": "openclaw",
                    "provider_action_ref": "openclaw.google_sheets.read_rows",
                    "external_side_effects_allowed_in_preview": False,
                }
            ],
            "openclaw_action_plan": [
                {
                    "step_key": "google_sheets_read",
                    "capability": "google_sheets.read_rows",
                    "provider": "openclaw",
                    "provider_action_ref": "openclaw.google_sheets.read_rows",
                }
            ],
        },
        {"user_id": "user1"},
    )

    artifact = next(
        item
        for item in cursor.tables["agent_artifacts"].values()
        if item["artifact_type"] == "openclaw_preview_observations"
    )

    assert result["success"] is True
    assert result["run"]["status"] == "completed"
    assert orchestrator.calls == 0
    assert artifact["payload_json"]["schema"] == "localos_openclaw_preview_observations_v1"
    assert artifact["payload_json"]["external_actions_executed"] is False
    assert artifact["payload_json"]["handler_contracts"][0]["handler"] == "openclaw_policy_boundary"
    assert artifact["payload_json"]["observations"][0]["external_action_executed"] is False
    assert result["run"]["observability"]["preview_summary"]["openclaw_action_count"] == 1


def test_blocking_business_result_stops_before_downstream_write(monkeypatch):
    from services import agent_blueprint_runner
    from services.agent_blueprint_runner import AgentBlueprintRunner

    cursor = FakeCursor()
    cursor.tables["agent_blueprints"]["bp1"] = {
        "id": "bp1",
        "business_id": "biz1",
        "name": "Blocked sheets agent",
        "category": "custom",
        "metadata_json": {},
    }
    cursor.tables["agent_blueprint_versions"]["ver1"] = {
        "id": "ver1",
        "blueprint_id": "bp1",
        "steps_json": [
            {
                "key": "prepare_output",
                "type": "artifact",
                "title": "Подготовить результат",
                "artifact_type": "agent_output_draft",
            },
            {
                "key": "save_content_plan_draft",
                "type": "capability",
                "title": "Сохранить черновик",
                "capability": "content_plan.item.create_draft",
            },
        ],
        "capability_allowlist_json": ["content_plan.item.create_draft"],
    }
    monkeypatch.setattr(
        agent_blueprint_runner,
        "build_generic_artifact_payload",
        lambda *_args, **_kwargs: {
            "status": "generated",
            "result": {
                "status": "needs_google_access",
                "title": "Нужно переподключить Google-доступ",
                "summary": ["Таблица выбрана, но сохранённый доступ больше не работает."],
            },
        },
    )
    orchestrator = CountingOrchestrator()

    result = AgentBlueprintRunner(cursor, orchestrator=orchestrator).start_run(
        "ver1",
        {},
        {"user_id": "user1"},
    )

    run = result["run"]
    assert run["status"] == "failed"
    assert run["error_text"] == "Нужно переподключить Google-доступ"
    assert [step["step_key"] for step in run["steps"]] == ["prepare_output"]
    assert run["business_result"]["status"] == "needs_google_access"
    assert run["result_state"] == "blocked"
    assert orchestrator.calls == 0


def test_successful_retry_clears_previous_transient_error():
    from services.agent_blueprint_runner import AgentBlueprintRunner

    cursor = FakeCursor()
    cursor.tables["agent_blueprints"]["bp1"] = {
        "id": "bp1",
        "business_id": "biz1",
        "name": "Recovery canary",
        "category": "custom",
        "metadata_json": {},
    }
    cursor.tables["agent_blueprint_versions"]["ver1"] = {
        "id": "ver1",
        "blueprint_id": "bp1",
        "steps_json": [],
        "capability_allowlist_json": [],
    }
    cursor.tables["agent_runs"]["run1"] = {
        "id": "run1",
        "blueprint_id": "bp1",
        "blueprint_version_id": "ver1",
        "business_id": "biz1",
        "status": "retry_wait",
        "input_json": {"preview_mode": True},
        "output_json": {},
        "created_by_user_id": "user1",
        "error_text": "worker heartbeat expired; retry scheduled",
        "next_attempt_at": "2026-07-19T14:00:00Z",
    }

    result = AgentBlueprintRunner(cursor).execute_queued_run(
        "run1",
        {"user_id": "user1"},
    )

    assert result["run"]["status"] == "completed"
    assert result["run"]["error_text"] is None
    assert result["run"]["next_attempt_at"] is None


def test_agent_integration_preflight_allows_inline_rows_and_native_finance():
    from services.agent_blueprint_draft_builder import compile_agent_blueprint
    from services.agent_integration_preflight import build_agent_integration_preflight

    draft = compile_agent_blueprint(
        "Каждый вечер проверяй Google Sheets, бери новые оплаты и создавай транзакции в финансах LocalOS"
    )
    cursor = FakeCursor()

    preflight = build_agent_integration_preflight(
        cursor,
        business_id="biz1",
        metadata=draft["metadata"],
        input_payload={"rows": [{"amount": "12000", "type": "revenue"}]},
    )

    assert preflight["status"] == "ready"
    assert preflight["missing_count"] == 0
    by_provider = {item["provider"]: item for item in preflight["items"]}
    assert by_provider["google_sheets"]["resolution"] == "input_payload"
    assert by_provider["localos_finance"]["resolution"] == "native_localos"


def test_runner_builds_shortlist_from_sourced_unprocessed_leads():
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
        "name": "Fresh Lead",
        "category": "beauty",
        "city": "Moscow",
        "email": "fresh@example.com",
        "source": "yandex_maps",
        "status": "new",
        "selected_channel": "",
        "pipeline_status": "unprocessed",
    }
    runner = AgentBlueprintRunner(cursor, orchestrator=CountingOrchestrator())

    result = runner.start_run(
        "ver1",
        {"source": "yandex_maps", "city": "Moscow", "intent": "client_outreach", "limit": 5},
        {"user_id": "user1"},
    )
    run = result["run"]
    shortlist_artifact = [item for item in run["artifacts"] if item["artifact_type"] == "lead_shortlist"][-1]
    shortlist_payload = shortlist_artifact["payload_json"]

    assert shortlist_payload["source"] == "prospectingleads"
    assert shortlist_payload["source_artifact"] == "lead_source_plan"
    assert shortlist_payload["count"] == 1
    assert shortlist_payload["items"][0]["id"] == "lead1"

    shortlist_approval = run["approvals"][0]
    after_shortlist = runner.approve(run["id"], shortlist_approval["id"], {"user_id": "user1"})

    assert cursor.tables["prospectingleads"]["lead1"]["status"] == "channel_selected"
    assert after_shortlist["run"]["approvals"][-1]["approval_type"] == "drafts"


def test_risk_policy_requires_human_for_dangerous_capabilities():
    from core.action_policy import evaluate_risk_policy

    for capability in ("outreach.send_batch", "content.publish", "billing.payment", "records.delete"):
        risk = evaluate_risk_policy(capability, {}, {})
        assert risk["requires_human"] is True
        assert risk["reason"] == "dangerous capability requires review"


def test_runner_load_run_includes_observability_envelope_for_openclaw_actions():
    from services.agent_blueprint_runner import AgentBlueprintRunner

    class FakeObservabilityOrchestrator:
        def execute(self, envelope, user_data, *, allow_execute_when_approved=False):
            return {"success": True, "status": "completed", "action_id": "action-1", "result": {}, "billing": {}}

        def get_action_support_package(self, action_id, user_data, **kwargs):
            return {
                "success": True,
                "action_id": action_id,
                "tenant_id": "biz1",
                "capability": "communications.send_reminder",
                "trace_id": "agent-run:run1:send",
                "status": "completed",
                "delivery_stats": {
                    "attempts_total": 1,
                    "attempts_success": 1,
                    "attempts_failed": 0,
                },
                "billing": {
                    "summary": {
                        "reserved_tokens": 2000,
                        "settled_tokens": 42,
                        "released_tokens": 1958,
                        "total_cost": 0.012,
                    },
                    "entries": [{"entry_type": "settle", "tokens_out": 42, "cost": 0.012}],
                },
                "timeline": {
                    "events": [
                        {"source": "action_transition", "event_type": "completed", "status": "completed", "details": {}},
                    ],
                },
            }

    cursor = FakeCursor()
    preview_openclaw_action_plan = [
        {
            "step_key": "read_sheet",
            "title": "Read Google Sheets rows",
            "capability": "sheets.read_rows",
            "provider": "openclaw",
            "provider_action_ref": "openclaw.google_sheets.read_rows",
            "provider_policy": "localos_envelope",
            "risk_class": "read",
            "approval_class": "none",
            "requires_approval": False,
        },
        {
            "step_key": "append_sheet",
            "title": "Prepare approved append request",
            "capability": "sheets.append_row_request",
            "provider": "openclaw",
            "provider_action_ref": "openclaw.google_sheets.append_row",
            "provider_policy": "localos_envelope",
            "risk_class": "external_write",
            "approval_class": "human_before_write",
            "requires_approval": True,
        },
    ]
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
            "openclaw_action_plan": preview_openclaw_action_plan,
            "policy_envelope": {
                "execution_boundary": "openclaw_action_orchestrator",
                "external_side_effects_allowed_in_preview": False,
                "approval_owner": "LocalOS",
                "billing_owner": "LocalOS",
                "audit_owner": "LocalOS",
            },
            "preview_context": {
                "understood_task": "Проверить Google Sheets и показать append request",
                "data_sources": ["Google Sheets", "Telegram"],
                "manual_control": "Подтвердить перед записью в таблицу.",
            },
        },
        "output_json": {},
        "created_by_user_id": "user1",
    }
    cursor.tables["agent_run_steps"]["step1"] = {
        "id": "step1",
        "run_id": "run1",
        "step_index": 0,
        "step_key": "send",
        "step_type": "capability",
        "status": "completed",
        "input_json": {},
        "output_json": {
            "capability": "sheets.append_row_request",
            "orchestrator": {
                "action_id": "action-1",
                "result": {"request_id": "sheet-request-1"},
            },
        },
    }
    cursor.tables["agent_sheet_operation_requests"]["sheet-request-1"] = {
        "id": "sheet-request-1",
        "business_id": "biz1",
        "action_id": "action-1",
        "integration_id": "integration-1",
        "spreadsheet_id": "spreadsheet-1",
        "sheet_name": "Leads",
        "operation": "append_row",
        "status": "request_created",
        "approval_state": "pending_human",
        "apply_state": "not_applied",
        "row_values_json": ["Anna", "Telegram"],
        "mapping_json": {"name": "telegram_username"},
        "limits_json": {"daily_cap": 10},
        "provider_write_performed": False,
        "created_at": "2026-06-09T10:00:00Z",
    }

    run = AgentBlueprintRunner(cursor, FakeObservabilityOrchestrator()).load_run("run1", {"user_id": "user1"})
    observability = run["observability"]

    assert observability["schema"] == "agent_run_observability_v1"
    assert observability["preview_summary"]["schema"] == "localos_agent_preview_summary_v1"
    assert observability["preview_summary"]["is_preview"] is True
    assert observability["preview_summary"]["safe_preview"] is True
    assert observability["preview_summary"]["understood_task"] == "Проверить Google Sheets и показать append request"
    assert observability["preview_summary"]["external_actions_performed"] is False
    assert observability["preview_summary"]["openclaw_action_count"] == 2
    assert observability["preview_summary"]["openclaw_action_plan"][0]["provider_action_ref"] == "openclaw.google_sheets.read_rows"
    assert observability["preview_summary"]["openclaw_action_plan"][1]["requires_approval"] is True
    assert observability["preview_summary"]["policy_envelope"]["execution_boundary"] == "openclaw_action_orchestrator"
    assert observability["preview_summary"]["policy_envelope"]["approval_owner"] == "LocalOS"
    assert observability["preview_summary"]["approval_gate"]["waiting_actions_count"] == 1
    assert observability["preview_summary"]["approval_gate"]["external_actions_performed"] is False
    assert "approval" in observability["preview_summary"]["activation_hint"].lower()
    assert observability["preview_summary"]["next_step"] == "review_approvals"
    assert observability["preview_summary"]["next_step_label"] == "Проверить approval"
    assert observability["action_ids"] == ["action-1"]
    assert observability["action_ledger"]["items"][0]["billing_summary"]["settled_tokens"] == 42
    assert observability["billing_ledger"]["summary"]["reserved_tokens"] == 2000
    assert observability["billing_ledger"]["summary"]["settled_tokens"] == 42
    assert observability["billing_ledger"]["summary"]["released_tokens"] == 1958
    assert observability["billing_ledger"]["actions"][0]["action_id"] == "action-1"
    assert observability["billing_ledger"]["actions"][0]["capability"] == "communications.send_reminder"
    assert observability["billing_ledger"]["actions"][0]["entry_count"] == 1
    assert observability["billing_ledger"]["entries"][0]["entry_type"] == "settle"
    assert observability["billing_ledger"]["entries"][0]["tokens_out"] == 42
    assert observability["unified_billing_ledger"]["schema"] == "localos_agent_run_unified_billing_ledger_v1"
    assert observability["unified_billing_ledger"]["summary"]["actual_tokens"] == 42
    assert observability["unified_billing_ledger"]["summary"]["external_action_count"] == 1
    assert observability["unified_billing_ledger"]["items"][0]["key"] == "preview_run"
    assert observability["unified_billing_ledger"]["items"][0]["actual_tokens"] == 0
    assert observability["unified_billing_ledger"]["items"][1]["key"] == "external_action"
    assert observability["unified_billing_ledger"]["items"][1]["actual_tokens"] == 42
    assert observability["delivery_status"]["state"] == "delivered"
    assert observability["cost_tokens"]["total_cost"] == 0.012
    assert observability["domain_requests"]["count"] == 1
    assert observability["domain_requests"]["pending"] == 1
    domain_request = observability["domain_requests"]["items"][0]
    assert domain_request["kind"] == "sheet_operation_request"
    assert domain_request["approval_state"] == "pending_human"
    assert domain_request["apply_state"] == "not_applied"
    assert domain_request["provider_handoff"]["provider_executor"] == "manual_controlled_google_sheets_append"
    assert domain_request["provider_handoff"]["spreadsheet_id"] == "spreadsheet-1"
    assert domain_request["provider_write_performed"] is False
    assert "External spreadsheet write requires human approval" in domain_request["why_waiting"]
    assert observability["support_export"]["endpoint"] == "/api/agent-runs/run1/support-export"


def test_runner_observability_exposes_source_to_result_chain():
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
    cursor.tables["agent_runs"]["run1"] = {
        "id": "run1",
        "blueprint_id": "bp1",
        "blueprint_version_id": "ver1",
        "business_id": "biz1",
        "status": "completed",
        "input_json": {},
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
                    "provider_read_performed": True,
                    "rows": [{"date": "2026-04-20", "route": "Airport -> Center"}],
                },
            },
        },
    }
    cursor.tables["agent_artifacts"]["artifact1"] = {
        "id": "artifact1",
        "run_id": "run1",
        "step_id": "output-step",
        "artifact_type": "telegram_post_draft",
        "title": "Черновик поста",
        "payload_json": {
            "items_used": 1,
            "result": {
                "title": "Черновик сообщения",
                "draft_text": "Поездка на 20 апреля\n\nПодготовлен черновик сообщения:\nмаршрут: Airport -> Center.",
            },
        },
        "created_at": "2026-06-28 12:00:00",
    }
    cursor.tables["agent_integrations"]["integration-1"] = {
        "id": "integration-1",
        "business_id": "biz1",
        "provider": "google_sheets",
        "status": "active",
        "auth_ref": "ext-1",
        "config_json": {"spreadsheet_id": "spreadsheet-1", "sheet_name": "Trips"},
    }

    observability = AgentBlueprintRunner(cursor).load_run("run1", {"user_id": "user1"})["observability"]["source_result_chain"]

    assert observability["source_step_present"] is True
    assert observability["provider_connected"] is True
    assert observability["provider_read_attempted"] is True
    assert observability["rows_returned_count"] == 1
    assert observability["rows_used_for_output_count"] == 1
    assert observability["result_generated"] is True
    assert observability["blocker_code"] == ""
