import json
from datetime import datetime, timezone
from pathlib import Path

from tests.agent_blueprint_fakes import *  # noqa: F403


def test_agent_blueprint_draft_builder_creates_safe_document_agent():
    from services.agent_blueprint_draft_builder import build_agent_blueprint_draft

    draft = build_agent_blueprint_draft("Обработай договор, найди риски и подготовь письмо клиенту")
    version_payload = draft["version_payload"]
    steps = version_payload["steps"]

    assert draft["category"] == "documents"
    assert draft["metadata"]["builder"] == "description_builder_v1"
    assert "uploaded_documents" in draft["summary"]["sources"]
    assert version_payload["capability_allowlist"] == []
    assert any(step["type"] == "approval" for step in steps)
    assert "external_delivery" in draft["summary"]["approval_boundaries"]


def test_agent_blueprint_draft_builder_respects_explicit_category():
    from services.agent_blueprint_draft_builder import build_agent_blueprint_draft

    draft = build_agent_blueprint_draft("Подготовь результат по этому контексту", "documents")

    assert draft["category"] == "documents"
    assert draft["name"] == "Подготовь результат по этому контексту"
    assert draft["version_payload"]["capability_allowlist"] == []
    assert draft["summary"]["external_dispatch_performed"] is False


def test_agent_compiler_creates_communications_reminder_blueprint():
    from services.agent_blueprint_draft_builder import compile_agent_blueprint

    draft = compile_agent_blueprint(
        "Сделай агента, который напоминает клиентам о записи и сообщает про пакетное предложение"
    )
    payload = draft["version_payload"]

    assert draft["category"] == "communications"
    assert draft["metadata"]["compiler"] == "agent_compiler_v1"
    assert payload["trigger"] == "appointment.reminder.before"
    assert payload["audience"] == "clients_with_upcoming_appointments"
    assert payload["audience_rules"]
    assert payload["consent_rules"]
    assert payload["message_template"]
    assert payload["persona"]
    assert payload["send_capability"] == "communications.send_reminder"
    assert payload["delivery_outcome_journal"]["journal_type"] == "communications_delivery_outcome"
    assert payload["mode"] == "approved_batch_only"
    assert payload["external_dispatch_performed"] is False
    assert payload["data_sources"] == ["appointments", "services", "packages", "business_profile"]
    assert [step["key"] for step in payload["steps"]] == [
        "collect_audience",
        "prepare_message",
        "validate_consent",
        "approve_message",
        "send_message",
        "record_outcome",
    ]
    assert payload["capability_allowlist"] == [
        "appointments.read",
        "communications.draft",
        "communications.send_reminder",
    ]
    assert payload["approval_policy"]["first_run"] == "manual_approval_required"
    assert payload["approval_policy"]["mass_send"] == "manual_approval_required"
    assert payload["approval_policy"]["mode"] == "approved_batch_only"
    assert payload["limits"]["daily_cap"] == 10
    assert payload["limits"]["autonomous_send_allowed"] is False
    assert "drafts" in payload["output_schema"]["properties"]
    assert "delivery_report" in payload["output_schema"]["properties"]
    assert "outcomes" in payload["output_schema"]["properties"]
    assert "delivery_outcome_journal" in payload["output_schema"]["properties"]


def test_agent_compiler_creates_custom_telegram_to_sheets_blueprint():
    from services.agent_blueprint_draft_builder import compile_agent_blueprint

    draft = compile_agent_blueprint("Когда пользователь пишет в Telegram бота, добавь строку в Google таблицу")
    payload = draft["version_payload"]

    assert draft["category"] == "custom"
    assert draft["metadata"]["custom_process"]["kind"] == "source_destination_workflow"
    assert draft["metadata"]["custom_process"]["trigger"] == "telegram.message.received"
    assert draft["metadata"]["custom_process"]["target"] == "sheets.append_row_request"
    assert payload["trigger"] == "telegram.message.received"
    assert payload["mode"] == "approved_capability_request"
    assert payload["capability_allowlist"] == ["sheets.append_row_request"]
    assert payload["approval_policy"]["sheet_update"] == "manual_approval_required"
    assert draft["metadata"]["compiled_process"]["schema"] == "compiled_source_destination_workflow_v1"
    assert draft["metadata"]["required_integration_bindings"][0]["key"] == "telegram_trigger"
    assert draft["metadata"]["required_integration_bindings"][1]["key"] == "google_sheets_append"
    assert draft["metadata"]["required_integration_bindings"][1]["required_config"] == ["spreadsheet_id", "sheet_name"]
    assert payload["required_integration_bindings"][1]["capability"] == "sheets.append_row_request"
    assert payload["limits"]["autonomous_external_write_allowed"] is False
    assert [step["key"] for step in payload["steps"]] == [
        "capture_telegram_trigger",
        "prepare_sheet_row",
        "approve_sheet_update",
        "request_google_sheets",
        "record_google_sheets_outcome",
    ]
    assert payload["steps"][3]["requires_approval"] is True
    assert payload["steps"][3]["required_approval_type"] == "sheet_update"
    assert payload["side_effects_performed"] is False


def test_agent_compiler_creates_direct_confirmed_sheets_append_without_ai_classification(monkeypatch):
    from services import agent_blueprint_draft_builder

    def fail_ai_classifier(*args, **kwargs):
        raise AssertionError("Direct Google Sheets writes must compile deterministically")

    monkeypatch.setattr(agent_blueprint_draft_builder, "infer_agent_workflow_intent", fail_ai_classifier)
    draft = agent_blueprint_draft_builder.compile_agent_blueprint(
        "В Google Таблице 1s79gWCm7A8X1drwN6yAscetf0adpRkamHCJyHCkyIqY на листе «Тех лист» "
        "добавь после моего подтверждения одну строку: LOCALOS_SHEETS_CANARY, 2026-07-23, preview-approved. "
        "Ничего не удаляй и не меняй структуру таблицы.",
        use_ai=True,
    )
    payload = draft["version_payload"]

    assert draft["category"] == "custom"
    assert draft["metadata"]["compiler_source"] == "deterministic_google_sheets_write"
    assert payload["trigger"] == "manual.run"
    assert payload["capability_allowlist"] == ["sheets.append_row_request"]
    assert [item["provider"] for item in payload["required_integration_bindings"]] == ["google_sheets"]
    assert payload["required_integration_bindings"][0]["direction"] == "external_write"
    assert payload["inputs_schema"]["required"] == ["row_values"]
    assert payload["inputs_schema"]["properties"]["row_values"]["default"] == [
        "LOCALOS_SHEETS_CANARY",
        "2026-07-23",
        "preview-approved",
    ]
    draft_step = next(step for step in payload["steps"] if step.get("artifact_type") == "sheet_row_draft")
    request_step = next(step for step in payload["steps"] if step.get("capability") == "sheets.append_row_request")
    assert draft_step["payload"]["sheet_name"] == "Тех лист"
    assert request_step["payload"]["sheet_name"] == "Тех лист"
    assert request_step["required_approval_type"] == "sheet_update"


def test_agent_compiler_creates_source_destination_blueprint_for_sheets_to_finance():
    from services.agent_blueprint_draft_builder import compile_agent_blueprint

    draft = compile_agent_blueprint(
        "Каждый вечер проверяй Google Sheets, бери новые оплаты и создавай транзакции в финансах LocalOS"
    )
    payload = draft["version_payload"]

    assert draft["category"] == "custom"
    assert draft["metadata"]["custom_process"]["kind"] == "source_destination_workflow"
    assert draft["metadata"]["custom_process"]["archetype"] == "google_sheets_to_localos_finance"
    assert draft["metadata"]["custom_process"]["source"] == "google_sheets.read_rows"
    assert draft["metadata"]["custom_process"]["target"] == "finance.transaction.create"
    assert draft["metadata"]["custom_process"]["schedule"]["time"] == "19:00"
    assert payload["trigger"] == "schedule.daily"
    assert payload["capability_allowlist"] == ["google_sheets.read_rows", "finance.transaction.create"]
    assert payload["approval_policy"]["finance_transaction_import"] == "manual_approval_required"
    assert draft["metadata"]["compiled_process"]["schema"] == "compiled_source_destination_workflow_v1"
    assert payload["required_integration_bindings"][0]["key"] == "google_sheets_read"
    assert payload["required_integration_bindings"][1]["key"] == "localos_finance"
    assert [step["key"] for step in payload["steps"]] == [
        "read_google_sheets",
        "normalize_finance_rows",
        "approve_finance_transaction_import",
        "request_localos_finance",
        "record_localos_finance_outcome",
    ]
    assert payload["steps"][3]["capability"] == "finance.transaction.create"
    assert payload["steps"][3]["payload"]["rows_from_step"] == "read_google_sheets"
    assert payload["steps"][0]["provider"] == "openclaw"
    assert payload["steps"][0]["provider_action_ref"] == "openclaw.google_sheets.read_rows"
    assert payload["steps"][0]["provider_policy"] == "localos_envelope"
    assert payload["steps"][3]["payload"]["input_mappings"] == [
        {
            "target": "rows",
            "from_step": "read_google_sheets",
            "path": "orchestrator.result.rows",
            "required": True,
        }
    ]
    assert payload["limits"]["autonomous_localos_write_allowed"] is False
    assert draft["metadata"]["compiled_artifact_candidate"]["schema"] == "localos_compiled_artifact_candidate_v1"
    assert draft["metadata"]["compiled_artifact_candidate"]["status"] == "validation_passed"
    assert draft["metadata"]["compiled_validation"]["valid"] is True
    assert draft["metadata"]["compiled_artifact_candidate"]["dsl"]["schema"] == "localos_agent_workflow_dsl_v1"
    assert draft["metadata"]["compiled_artifact_candidate"]["activation_gate"]["requires_validation_passed"] is True


def test_agent_compiler_creates_source_destination_blueprint_for_sheets_to_telegram_post():
    from services.agent_blueprint_draft_builder import compile_agent_blueprint

    draft = compile_agent_blueprint(
        "Мне нужен агент, который из онлайн таблицы гугл со списком заказов берёт один из заказов "
        "на предыдущий день и создаёт пост в телеграм. В стиле - наши пассажиры насладились поездкой "
        "из аэропорта лос анджелеса в санта барбару."
    )
    payload = draft["version_payload"]

    assert draft["category"] == "custom"
    assert draft["metadata"]["custom_process"]["kind"] == "source_destination_workflow"
    assert draft["metadata"]["custom_process"]["archetype"] == "google_sheets_to_telegram"
    assert draft["metadata"]["custom_process"]["source"] == "google_sheets.read_rows"
    assert draft["metadata"]["custom_process"]["target"] == "communications.draft"
    assert draft["metadata"]["custom_process"]["schedule"]["time"] == "10:00"
    assert payload["trigger"] == "schedule.daily"
    assert payload["capability_allowlist"] == ["google_sheets.read_rows", "communications.draft"]
    assert payload["approval_policy"]["telegram_post_approval"] == "manual_approval_required"
    assert draft["metadata"]["compiled_process"]["schema"] == "compiled_source_destination_workflow_v1"
    assert payload["required_integration_bindings"][0]["key"] == "google_sheets_read"
    assert payload["required_integration_bindings"][1]["key"] == "telegram_delivery"
    assert payload["required_integration_bindings"][1]["provider"] == "telegram"
    assert payload["required_integration_bindings"][1]["required_config"] == ["bot_mode"]
    assert [step["key"] for step in payload["steps"]] == [
        "read_google_sheets",
        "prepare_telegram_post",
        "approve_telegram_post_approval",
        "request_telegram",
        "record_telegram_outcome",
    ]
    assert payload["steps"][1]["artifact_type"] == "telegram_post_draft"
    assert payload["steps"][3]["capability"] == "communications.draft"
    assert payload["steps"][0]["provider_action_ref"] == "openclaw.google_sheets.read_rows"
    assert payload["steps"][3]["provider_action_ref"] == "openclaw.telegram.create_draft"
    assert payload["steps"][3]["provider_policy"] == "localos_envelope"
    assert payload["steps"][3]["payload"]["message_type"] == "telegram_post_draft"
    assert payload["steps"][3]["payload"]["rows_from_step"] == "read_google_sheets"
    assert payload["steps"][3]["payload"]["input_mappings"] == [
        {
            "target": "rows",
            "from_step": "read_google_sheets",
            "path": "orchestrator.result.rows",
            "required": True,
        }
    ]
    assert payload["limits"]["autonomous_external_write_allowed"] is False
    assert draft["metadata"]["compiled_artifact_candidate"]["status"] == "validation_passed"
    assert draft["metadata"]["compiled_validation"]["valid"] is True


def test_agent_compiler_creates_source_only_blueprint_for_google_sheet_result_url():
    from services.agent_blueprint_draft_builder import compile_agent_blueprint

    draft = compile_agent_blueprint(
        "Агент открывает таблицу со списком поездок, выбирает одну из поездок 20 апреля 2022 года. "
        "https://docs.google.com/spreadsheets/d/1s79gWCm7A8X1drwN6yAscetf0adpRkamHCJyHCkyIqY/edit?gid=0#gid=0 "
        "пишет пост и сохраняет его в контент план на 27 июня 2026 года"
    )
    payload = draft["version_payload"]

    assert draft["category"] == "custom"
    assert draft["metadata"]["custom_process"]["kind"] == "source_to_result_workflow"
    assert draft["metadata"]["custom_process"]["source"] == "google_sheets.read_rows"
    assert draft["metadata"]["custom_process"]["target"] == "content_plan.item.create_draft"
    assert draft["metadata"]["compiled_process"]["schema"] == "compiled_source_to_result_workflow_v1"
    assert payload["mode"] == "source_to_reviewed_result"
    assert payload["capability_allowlist"] == ["google_sheets.read_rows", "content_plan.item.create_draft"]
    assert payload["required_integration_bindings"][0]["key"] == "google_sheets_read"
    assert [step["key"] for step in payload["steps"]] == [
        "read_google_sheets",
        "prepare_output",
        "save_content_plan_draft",
        "save_result",
    ]
    assert "content_plan.item.create_draft" in payload["capability_allowlist"]
    assert payload["approval_policy"]["required_for"] == []
    assert payload["steps"][0]["capability"] == "google_sheets.read_rows"
    assert payload["steps"][0]["provider_action_ref"] == "openclaw.google_sheets.read_rows"
    assert payload["steps"][1]["artifact_type"] == "agent_output_draft"
    assert payload["steps"][1]["payload"]["rows_from_step"] == "read_google_sheets"
    assert payload["approval_policy"]["mode"] == "external_actions_only"
    assert payload["limits"]["autonomous_external_write_allowed"] is False
    assert draft["metadata"]["compiled_artifact_candidate"]["status"] == "validation_passed"
    assert draft["metadata"]["compiled_validation"]["valid"] is True


def test_agent_compiler_keeps_content_plan_step_with_common_typo():
    from services.agent_blueprint_draft_builder import compile_agent_blueprint

    draft = compile_agent_blueprint(
        "Агент открывает Google-таблицу со списком поездок, пишет пост и сохраняет его "
        "в конент план на 27 июня 2026 года"
    )
    payload = draft["version_payload"]

    assert [step["key"] for step in payload["steps"]] == [
        "read_google_sheets",
        "prepare_output",
        "save_content_plan_draft",
        "save_result",
    ]
    assert "content_plan.item.create_draft" in payload["capability_allowlist"]


def test_compiled_workflow_validation_rejects_write_without_approval():
    from services.agent_compiled_artifact import validate_compiled_artifact_candidate

    version_payload = {
        "goal": "Записать строку в таблицу",
        "trigger": "manual.run",
        "mode": "approved_capability_request",
        "inputs_schema": {"type": "object"},
        "steps": [
            {
                "key": "write_sheet",
                "type": "capability",
                "capability": "sheets.append_row_request",
                "requires_approval": False,
            }
        ],
        "capability_allowlist": ["sheets.append_row_request"],
        "approval_policy": {},
        "required_integration_bindings": [
            {
                "key": "google_sheets_append",
                "provider": "google_sheets",
                "capability": "sheets.append_row_request",
            }
        ],
        "limits": {"autonomous_external_write_allowed": False},
        "output_schema": {"type": "object"},
    }

    result = validate_compiled_artifact_candidate(version_payload, {"compiled_process": {"schema": "compiled_source_destination_workflow_v1"}})

    assert result["ready"] is False
    assert result["validation"]["status"] == "invalid"
    fields = [item["field"] for item in result["validation"]["errors"]]
    assert "steps[0].requires_approval" in fields
    assert "steps[0].required_approval_type" in fields


def test_agent_compiler_builds_internal_summary_instead_of_review_replies():
    from services.agent_blueprint_draft_builder import compile_agent_blueprint

    draft = compile_agent_blueprint(
        "Каждый день прочитать профиль бизнеса, услуги и последние отзывы, "
        "затем сохранить короткую внутреннюю сводку. Ничего не публиковать и не отправлять."
    )
    payload = draft["version_payload"]
    output_step = next(step for step in payload["steps"] if step["key"] == "prepare_output")

    assert draft["category"] == "custom"
    assert draft["metadata"]["draft_category"] == "business_summary"
    assert draft["metadata"]["data_sources"] == ["business_profile", "services", "external_reviews"]
    assert output_step["payload"]["category"] == "business_summary"
    assert output_step["payload"]["format"] == "internal_business_summary"
    assert payload["trigger"] == "schedule.daily"
    assert payload["approval_policy"]["required_for"] == []
    assert payload["approval_policy"]["mode"] == "external_actions_only"
    assert not any(step["type"] == "approval" for step in payload["steps"])
    assert payload["steps"][-1]["payload"]["status"] == "saved"
    assert payload["steps"][-1]["payload"]["delivery_state"] == "internal_only"
    assert draft["summary"]["category"] == "business_summary"
    assert draft["summary"]["outputs"] == ["internal_business_summary"]
    assert draft["summary"]["approval_required"] is False
    assert draft["metadata"]["compiled_process"]["approval_boundary"] == "external_actions_only"
    assert draft["metadata"]["compiled_validation"]["valid"] is True


def test_agent_compiler_keeps_internal_review_draft_without_result_approval():
    from services.agent_blueprint_draft_builder import compile_agent_blueprint

    draft = compile_agent_blueprint(
        "По кнопке прочитай отзывы, выбери один отзыв без ответа и подготовь внутренний черновик ответа. "
        "Ничего не публикуй и не отправляй."
    )
    payload = draft["version_payload"]

    assert draft["category"] == "reviews"
    assert payload["approval_policy"]["required_for"] == []
    assert payload["approval_policy"]["mode"] == "external_actions_only"
    assert not any(step["type"] == "approval" for step in payload["steps"])
    assert payload["steps"][-1]["payload"]["status"] == "saved"
    assert payload["steps"][-1]["payload"]["delivery_state"] == "internal_only"
    assert draft["summary"]["category"] == "reviews"
    assert draft["summary"]["approval_required"] is False


def test_agent_compiler_treats_prepared_news_as_internal_content_draft():
    from services.agent_blueprint_draft_builder import compile_agent_blueprint

    draft = compile_agent_blueprint(
        "По кнопке подготовь 3 новости для карточек на основе услуг, отзывов, сезонности и текущих задач."
    )
    payload = draft["version_payload"]
    output_step = next(step for step in payload["steps"] if step["key"] == "prepare_output")

    assert draft["category"] == "custom"
    assert draft["metadata"]["draft_category"] == "custom"
    assert draft["metadata"]["data_sources"] == ["external_reviews", "services", "business_profile", "manual_context"]
    assert output_step["payload"]["category"] == "custom"
    assert payload["approval_policy"]["required_for"] == []
    assert payload["approval_policy"]["mode"] == "external_actions_only"
    assert not any(step["type"] == "approval" for step in payload["steps"])
    assert payload["steps"][-1]["payload"]["delivery_state"] == "internal_only"
    assert draft["metadata"]["compiled_validation"]["valid"] is True


def test_compiled_workflow_validation_rejects_review_renderer_for_content_draft():
    from services.agent_compiled_artifact import validate_compiled_artifact_candidate

    version_payload = {
        "goal": "Подготовь 3 новости для карточек на основе услуг и отзывов.",
        "trigger": "manual.run",
        "mode": "draft",
        "inputs_schema": {"type": "object"},
        "steps": [
            {
                "key": "prepare_output",
                "type": "artifact",
                "artifact_type": "agent_output_draft",
                "payload": {"category": "reviews", "format": "reply_drafts"},
            }
        ],
        "capability_allowlist": [],
        "approval_policy": {"required_for": []},
        "required_integration_bindings": [],
        "limits": {},
        "output_schema": {"type": "object"},
    }

    result = validate_compiled_artifact_candidate(version_payload, {})

    assert result["ready"] is False
    assert any("review-reply" in item["message"] for item in result["validation"]["errors"])


def test_compiled_workflow_validation_rejects_review_renderer_for_internal_summary():
    from services.agent_compiled_artifact import validate_compiled_artifact_candidate

    version_payload = {
        "goal": "Прочитать профиль и отзывы, затем сохранить короткую внутреннюю сводку.",
        "trigger": "schedule.daily",
        "mode": "draft",
        "inputs_schema": {"type": "object"},
        "steps": [
            {
                "key": "prepare_output",
                "type": "artifact",
                "artifact_type": "agent_output_draft",
                "payload": {"category": "reviews", "format": "reply_drafts"},
            }
        ],
        "capability_allowlist": [],
        "approval_policy": {},
        "required_integration_bindings": [],
        "limits": {},
        "output_schema": {"type": "object"},
    }

    result = validate_compiled_artifact_candidate(
        version_payload,
        {"compiled_process": {"schema": "compiled_custom_workflow_v1"}},
    )

    assert result["ready"] is False
    assert result["validation"]["status"] == "invalid"
    assert result["validation"]["errors"][0]["field"] == "steps[0].payload.format"


def test_compiled_workflow_validation_rejects_manual_approval_contract_for_daily_internal_summary():
    from services.agent_compiled_artifact import validate_compiled_artifact_candidate

    version_payload = {
        "goal": "Каждый день сохранять короткую внутреннюю сводку.",
        "trigger": "manual.run",
        "mode": "draft",
        "inputs_schema": {"type": "object"},
        "steps": [
            {
                "key": "prepare_output",
                "type": "artifact",
                "artifact_type": "agent_output_draft",
                "payload": {"category": "business_summary", "format": "internal_business_summary"},
            },
            {
                "key": "approve_output",
                "type": "approval",
                "approval_type": "final_output",
            },
        ],
        "capability_allowlist": [],
        "approval_policy": {"required_for": ["final_output"]},
        "required_integration_bindings": [],
        "limits": {},
        "output_schema": {"type": "object"},
    }

    result = validate_compiled_artifact_candidate(
        version_payload,
        {"compiled_process": {"schema": "compiled_custom_workflow_v1"}},
    )

    assert result["ready"] is False
    assert result["validation"]["status"] == "invalid"
    fields = {item["field"] for item in result["validation"]["errors"]}
    assert fields == {"approval_policy.required_for", "steps", "trigger"}


def test_compiled_workflow_validation_rejects_openclaw_action_capability_mismatch():
    from services.agent_compiled_artifact import validate_compiled_artifact_candidate

    version_payload = {
        "goal": "Прочитать таблицу",
        "trigger": "manual.run",
        "mode": "approved_capability_request",
        "inputs_schema": {"type": "object"},
        "steps": [
            {
                "key": "read_sheet",
                "type": "capability",
                "capability": "google_sheets.read_rows",
                "provider": "openclaw",
                "provider_action_ref": "openclaw.telegram.publish_message",
                "requires_approval": False,
            }
        ],
        "capability_allowlist": ["google_sheets.read_rows"],
        "approval_policy": {},
        "required_integration_bindings": [
            {
                "key": "google_sheets_read",
                "provider": "google_sheets",
                "capability": "google_sheets.read_rows",
            }
        ],
        "limits": {"autonomous_external_write_allowed": False},
        "output_schema": {"type": "object"},
    }

    result = validate_compiled_artifact_candidate(version_payload, {"compiled_process": {"schema": "compiled_source_destination_workflow_v1"}})

    assert result["ready"] is False
    assert result["validation"]["status"] == "invalid"
    assert "steps[0].provider_action_ref" in [item["field"] for item in result["validation"]["errors"]]


def test_compiled_workflow_validation_uses_metadata_snapshot_for_version_rows():
    from services.agent_blueprint_draft_builder import compile_agent_blueprint
    from services.agent_blueprint_workspace import build_version_payload_from_row
    from services.agent_compiled_artifact import validate_compiled_artifact_candidate

    draft = compile_agent_blueprint(
        "Каждый вечер проверяй Google Sheets, бери новые оплаты и создавай транзакции в финансах LocalOS"
    )
    version_row = {
        "goal": draft["version_payload"]["goal"],
        "inputs_schema_json": draft["version_payload"]["inputs_schema"],
        "steps_json": draft["version_payload"]["steps"],
        "capability_allowlist_json": draft["version_payload"]["capability_allowlist"],
        "approval_policy_json": draft["version_payload"]["approval_policy"],
        "output_schema_json": draft["version_payload"]["output_schema"],
    }

    result = validate_compiled_artifact_candidate(build_version_payload_from_row(version_row), draft["metadata"])

    assert result["ready"] is True
    assert result["candidate"]["dsl"]["trigger"] == "schedule.daily"
    assert result["candidate"]["dsl"]["limits"]["autonomous_localos_write_allowed"] is False
    assert result["candidate"]["dsl"]["required_integration_bindings"][0]["key"] == "google_sheets_read"


def test_agent_metrics_summary_reports_compiled_runtime_health():
    from services.agent_blueprint_draft_builder import compile_agent_blueprint
    from services.agent_metrics import build_agent_metrics_summary

    draft = compile_agent_blueprint(
        "Каждый вечер проверяй Google Sheets, бери новые оплаты и создавай транзакции в финансах LocalOS"
    )
    metadata = dict(draft["metadata"])
    metadata["billing"] = {
        "estimated_credits": 3,
        "actual_credits": 3,
        "idempotency_key": "charge1",
    }
    metrics = build_agent_metrics_summary(
        {"id": "bp1", "status": "draft"},
        [{"id": "ver1", "version_number": 1}],
        {"id": "ver1", "version_number": 1},
        [
            {
                "id": "run1",
                "status": "completed",
                "input_json": {"preview_mode": True},
                "output_json": {
                    "observability": {
                        "cost_tokens": {
                            "reserved_tokens": 10,
                            "settled_tokens": 7,
                            "released_tokens": 3,
                            "inflight_reserved_tokens": 0,
                            "total_cost": 0.14,
                        },
                        "billing_ledger": {
                            "actions": [
                                {
                                    "action_id": "action1",
                                    "capability": "localos.finance.write",
                                    "settled_tokens": 42,
                                    "total_cost": 0.012,
                                }
                            ],
                            "entries": [],
                        },
                    }
                },
            },
            {"id": "run2", "status": "failed", "output_json": {}},
        ],
        [{"id": "approval1", "approval_type": "finance_transaction_import"}],
        metadata,
    )

    assert metrics["schema"] == "agent_metrics_summary_v1"
    assert metrics["compiled"]["validation_valid"] is True
    assert metrics["compiled"]["runtime_llm_required"] is False
    assert metrics["versions"]["active_version_number"] == 1
    assert metrics["runs"]["by_status"] == {"completed": 1, "failed": 1}
    assert metrics["approvals"]["pending"] == 1
    assert metrics["cost_tokens"]["reserved_tokens"] == 10
    assert metrics["cost_tokens"]["total_cost"] == 0.14
    assert metrics["billing_breakdown"]["schema"] == "localos_agent_billing_breakdown_v1"
    assert metrics["billing_breakdown"]["items"][0]["key"] == "agent_creation"
    assert any(item["key"] == "external_action" for item in metrics["cost_tokens"]["breakdown"])
    assert metrics["unified_billing_ledger"]["schema"] == "localos_agent_unified_billing_ledger_v1"
    assert metrics["unified_billing_ledger"]["summary"]["estimated_credits"] == 4
    assert metrics["unified_billing_ledger"]["summary"]["actual_credits"] == 3
    assert metrics["unified_billing_ledger"]["summary"]["actual_tokens"] == 49
    assert metrics["unified_billing_ledger"]["items"][0]["key"] == "agent_creation"
    assert any(item["key"] == "preview_run" and item["actual_tokens"] == 7 for item in metrics["unified_billing_ledger"]["items"])
    assert any(item["key"] == "external_action" and item["actual_tokens"] == 42 for item in metrics["unified_billing_ledger"]["items"])


def test_agent_creation_cost_preview_exposes_unified_ledger_estimate_items():
    from services.agent_builder_billing import build_agent_creation_cost_preview

    preview = build_agent_creation_cost_preview()

    assert preview["schema"] == "localos_agent_billing_estimate_v1"
    assert preview["total_estimated_credits"] == 4
    assert preview["total_estimated_tokens"] == 8500
    assert [item["key"] for item in preview["items"]] == [
        "agent_creation",
        "preview_run",
        "production_run",
        "external_action",
        "operator_chat",
    ]
    assert preview["items"][0]["billing_mode"] == "reserve_then_charge"
    assert preview["items"][3]["billing_mode"] == "action_orchestrator_reserve_settle"


def test_existing_agent_templates_publish_compiled_artifact_candidate():
    from services.agent_blueprint_draft_builder import compile_agent_blueprint

    examples = [
        ("Найди клиентов для outreach", "outreach", "compiled_outreach_workflow_v1"),
        ("Проверяй договоры и ищи риски", "documents", "compiled_documents_workflow_v1"),
        ("Готовь ответы на отзывы", "reviews", "compiled_reviews_workflow_v1"),
        ("Сделай таблицу исключений", "tables", "compiled_tables_workflow_v1"),
    ]

    for prompt, category, schema in examples:
        draft = compile_agent_blueprint(prompt)

        assert draft["category"] == category
        assert draft["metadata"]["compiled_process"]["schema"] == schema
        assert draft["metadata"]["compiled_artifact_candidate"]["status"] == "validation_passed"
        assert draft["metadata"]["compiled_validation"]["valid"] is True
        assert draft["metadata"]["compiler_contract"]["runtime_llm_required"] is False


def test_agent_compiler_uses_gigachat_only_at_design_time(monkeypatch):
    from services import agent_blueprint_draft_builder

    def fake_llm_intent(description, *, business_id="", user_id="", planner_context=None):
        return {
            "status": "compiled_intent",
            "source": "gigachat",
            "intent": {
                "trigger": "schedule.daily",
                "source": "google_sheets",
                "destination": "localos_finance",
                "read_capability": "google_sheets.read_rows",
                "write_capability": "finance.transaction.create",
                "required_connectors": ["google_sheets", "localos_finance"],
                "approval_reasons": ["localos_finance_write", "ambiguous_data"],
                "limits": {"max_items_per_run": 100},
                "clarifying_questions": [],
                "confidence": 0.92,
            },
        }

    monkeypatch.setattr(agent_blueprint_draft_builder, "infer_agent_workflow_intent", fake_llm_intent)

    draft = agent_blueprint_draft_builder.compile_agent_blueprint(
        "Раз в день переноси оплаты из таблицы в финансы",
        use_ai=True,
        business_id="biz1",
        user_id="user1",
    )
    metadata = draft["metadata"]
    steps = draft["version_payload"]["steps"]

    assert metadata["compiler_source"] == "gigachat_intent_extractor"
    assert metadata["llm_intent"]["status"] == "compiled_intent"
    assert metadata["compiler_contract"]["llm_usage"] == "design_time_only"
    assert metadata["compiler_contract"]["runtime_llm_required"] is False
    assert metadata["compiled_process"]["runtime_truth"] == "agent_blueprint_versions.steps_json"
    assert [step["type"] for step in steps] == ["capability", "artifact", "approval", "capability", "artifact"]
    assert "gigachat" not in str(draft["version_payload"]).lower()


def test_agent_compiler_llm_intent_is_sanitized_to_allowed_capabilities():
    from services.agent_compiler_llm import infer_agent_workflow_intent

    def fake_generator(prompt, business_id, user_id):
        assert "LocalOS/OpenClaw policy envelope" in prompt
        return """
        {
          "trigger": "schedule.daily",
          "source": "google_sheets",
          "destination": "localos_finance",
          "read_capability": "google_sheets.read_rows",
          "write_capability": "dangerous.delete_everything",
          "required_connectors": ["google_sheets"],
          "approval_reasons": ["localos_finance_write"],
          "limits": {"max_items_per_run": 9999},
          "clarifying_questions": ["Какую вкладку читать?"],
          "confidence": 2
        }
        """

    result = infer_agent_workflow_intent(
        "Каждый вечер читай оплаты из Google Sheets и готовь финансы",
        business_id="biz1",
        user_id="user1",
        intent_generator=fake_generator,
    )

    assert result["status"] == "compiled_intent"
    assert result["intent"]["source"] == "google_sheets"
    assert result["intent"]["destination"] == "localos_finance"
    assert result["intent"]["read_capability"] == "google_sheets.read_rows"
    assert result["intent"]["write_capability"] == ""
    assert result["intent"]["limits"]["max_items_per_run"] == 500
    assert result["intent"]["confidence"] == 1.0


def test_agent_compiler_llm_prompt_includes_localos_openclaw_planner_context():
    from services.agent_compiler_llm import infer_agent_workflow_intent

    def fake_generator(prompt, business_id, user_id):
        assert business_id == "biz1"
        assert user_id == "user1"
        assert "localos_openclaw_planner_context_v1" in prompt
        assert '"tenant_boundary": "single_business"' in prompt
        assert '"missing_connections"' in prompt
        assert '"provider": "telegram"' in prompt
        assert "credential_extraction" in prompt
        assert "must_not_call_tools_directly" in prompt
        return """
        {
          "compiled_template_key": "google_sheets_to_telegram_post",
          "source": "google_sheets",
          "destination": "telegram",
          "read_capability": "google_sheets.read_rows",
          "write_capability": "communications.draft",
          "required_connectors": ["google_sheets", "telegram", "forbidden_provider"],
          "approval_reasons": ["external_publish"],
          "limits": {"max_items_per_run": 25},
          "clarifying_questions": ["Какую вкладку Google Sheets читать?"],
          "confidence": 0.7
        }
        """

    result = infer_agent_workflow_intent(
        "Подготовь пост в Telegram из заказа в Google Sheets",
        business_id="biz1",
        user_id="user1",
        planner_context={
            "schema": "localos_openclaw_planner_context_v1",
            "business_scope": {
                "business_id": "biz1",
                "user_id": "user1",
                "tenant_boundary": "single_business",
                "cross_business_access_allowed": False,
            },
            "allowed_capabilities": ["google_sheets.read_rows", "communications.draft"],
            "connection_state": {
                "missing_connections": [
                    {
                        "key": "telegram_delivery",
                        "provider": "telegram",
                        "provider_title": "Telegram",
                        "status": "missing",
                    }
                ]
            },
            "forbidden_action_classes": ["credential_extraction"],
            "output_contract": {"must_not_call_tools_directly": True},
        },
        intent_generator=fake_generator,
    )

    assert result["status"] == "compiled_intent"
    assert result["intent"]["compiled_template_key"] == "google_sheets_to_telegram_post"
    assert result["intent"]["required_connectors"] == ["google_sheets", "telegram"]
    assert result["intent"]["clarifying_questions"] == ["Какую вкладку Google Sheets читать?"]


def test_agent_compiler_llm_returns_planner_artifact_inside_policy_envelope():
    from services.agent_compiler_llm import infer_agent_workflow_intent

    def fake_generator(prompt, business_id, user_id):
        assert "workflow_draft" in prompt
        assert "approval_points" in prompt
        assert "unsupported_requests" in prompt
        return """
        {
          "compiled_template_key": "google_sheets_to_telegram_post",
          "source": "google_sheets",
          "destination": "telegram",
          "read_capability": "google_sheets.read_rows",
          "write_capability": "communications.draft",
          "required_connectors": ["google_sheets", "telegram", "unknown_provider"],
          "workflow_draft": {
            "trigger": "schedule.daily",
            "steps": [
              {"key": "read_orders", "capability": "google_sheets.read_rows", "secret": "drop"},
              {"key": "prepare_post", "type": "artifact"}
            ],
            "outputs": [{"key": "telegram_post_draft"}]
          },
          "approval_points": [
            {"key": "publish", "reason": "external publish", "raw_token": "drop"}
          ],
          "unsupported_requests": [
            {"request": "bypass approval", "reason": "LocalOS policy requires approval"}
          ],
          "approval_reasons": ["external_publish"],
          "limits": {"max_items_per_run": 15},
          "clarifying_questions": [],
          "confidence": 0.8
        }
        """

    result = infer_agent_workflow_intent(
        "Каждый день бери заказ из Google Sheets и готовь пост в Telegram",
        business_id="biz1",
        user_id="user1",
        intent_generator=fake_generator,
    )

    intent = result["intent"]
    assert result["status"] == "compiled_intent"
    assert intent["required_connectors"] == ["google_sheets", "telegram"]
    assert intent["workflow_draft"]["trigger"] == "schedule.daily"
    assert intent["workflow_draft"]["steps"][0]["key"] == "read_orders"
    assert "secret" not in intent["workflow_draft"]["steps"][0]
    assert intent["approval_points"][0]["reason"] == "external publish"
    assert "raw_token" not in intent["approval_points"][0]
    assert intent["unsupported_requests"][0]["reason"] == "LocalOS policy requires approval"


def test_agent_compiler_registry_drives_llm_template_selection():
    from services.agent_compiler_llm import infer_agent_workflow_intent
    from services.agent_compiler_registry import compiled_template_prompt_lines, get_compiled_agent_template

    def fake_generator(prompt, business_id, user_id):
        assert "google_sheets_to_localos_finance" in prompt
        assert "telegram_to_google_sheets" in prompt
        assert "google_sheets_to_telegram_post" in prompt
        return """
        {
          "compiled_template_key": "google_sheets_to_localos_finance",
          "source": "manual",
          "destination": "manual",
          "read_capability": "dangerous.read",
          "write_capability": "dangerous.write",
          "required_connectors": [],
          "approval_reasons": [],
          "limits": {"max_items_per_run": 100},
          "confidence": 0.8
        }
        """

    assert get_compiled_agent_template("google_sheets_to_localos_finance")["write_capability"] == "finance.transaction.create"
    assert any("communication:appointment_reminder" in line for line in compiled_template_prompt_lines())

    result = infer_agent_workflow_intent(
        "Импортируй оплаты из Google Sheets в финансы",
        business_id="biz1",
        user_id="user1",
        intent_generator=fake_generator,
    )

    assert result["status"] == "compiled_intent"
    assert result["intent"]["compiled_template_key"] == "google_sheets_to_localos_finance"
    assert result["intent"]["trigger"] == "schedule.daily"
    assert result["intent"]["source"] == "google_sheets"
    assert result["intent"]["destination"] == "localos_finance"
    assert result["intent"]["read_capability"] == "google_sheets.read_rows"
    assert result["intent"]["write_capability"] == "finance.transaction.create"
    assert result["intent"]["required_connectors"] == ["google_sheets", "localos_finance"]
    assert result["intent"]["approval_reasons"] == ["localos_finance_write", "ambiguous_data"]


def test_openclaw_capability_catalog_normalizes_actions_and_falls_back():
    from services.openclaw_capability_catalog import get_openclaw_capability_catalog

    fallback = get_openclaw_capability_catalog(fetcher=lambda: (_ for _ in ()).throw(RuntimeError("offline")))
    assert fallback["status"] == "fallback"
    assert any(
        action["localos_capability"] == "google_sheets.read_rows"
        and action["openclaw_action_ref"] == "openclaw.google_sheets.read_rows"
        for action in fallback["actions"]
    )

    catalog = get_openclaw_capability_catalog(
        fetcher=lambda: {
            "actions": [
                {
                    "name": "openclaw.custom.tool",
                    "capability": "custom.safe_action",
                    "provider": "custom",
                    "risk": "read",
                    "required_auth": ["custom_auth"],
                }
            ]
        }
    )
    assert catalog["source"] == "openclaw"
    assert catalog["actions"][0]["localos_capability"] == "custom.safe_action"
    assert catalog["actions"][0]["required_auth"] == ["custom_auth"]


def test_openclaw_capability_catalog_normalizes_current_capabilities_catalog_shape():
    from services.openclaw_capability_catalog import get_openclaw_capability_catalog

    catalog = get_openclaw_capability_catalog(
        fetcher=lambda: {
            "success": True,
            "capabilities": {
                "google_sheets.read_rows": {
                    "name": "google_sheets.read_rows",
                    "risk": "external_read",
                    "side_effects": "none; provider reads are resolved by the selected connector",
                    "approval_required": False,
                },
                "google_sheets.read": {
                    "name": "google_sheets.read",
                    "alias_for": "google_sheets.read_rows",
                    "risk": "external_read",
                    "side_effects": "none",
                    "approval_required": False,
                },
                "communications.send_offer": {
                    "name": "communications.send_offer",
                    "risk": "external_send_request",
                    "side_effects": "creates an offer send request only",
                    "approval_required": True,
                },
            },
        }
    )

    by_capability = {action["localos_capability"]: action for action in catalog["actions"]}
    assert catalog["source"] == "openclaw"
    assert catalog["discovery"]["provider_paths_preserved"] is True
    assert by_capability["google_sheets.read_rows"]["openclaw_action_ref"] == "openclaw.google_sheets.read_rows"
    assert by_capability["google_sheets.read_rows"]["required_auth"] == ["google_sheets"]
    assert "provider_candidates" in by_capability["google_sheets.read_rows"]
    assert any(item["provider"] == "native_localos" for item in by_capability["google_sheets.read_rows"]["provider_candidates"])
    assert by_capability["communications.send_offer"]["openclaw_action_ref"] == "openclaw.telegram.publish_message"
    assert by_capability["communications.send_offer"]["approval_class"] == "external_send_request"
    assert any(item["provider"] == "openclaw" for item in by_capability["communications.send_offer"]["provider_candidates"])


def test_openclaw_capability_catalog_can_use_sandbox_bridge_env(monkeypatch):
    from services import openclaw_capability_catalog

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "actions": [
                    {
                        "openclaw_action_ref": "openclaw.browser.supervised_publish",
                        "localos_capability": "social.post.publish_supervised_browser",
                        "service": "browser",
                        "status": "available",
                    }
                ]
            }

    def fake_get(url, headers=None, timeout=0):
        captured["url"] = url
        captured["headers"] = headers or {}
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.delenv("OPENCLAW_CAPABILITY_CATALOG_URL", raising=False)
    monkeypatch.delenv("OPENCLAW_BASE_URL", raising=False)
    monkeypatch.delenv("OPENCLAW_LOCALOS_TOKEN", raising=False)
    monkeypatch.delenv("OPENCLAW_TOKEN", raising=False)
    monkeypatch.setenv("OPENCLAW_SANDBOX_BRIDGE_URL", "http://openclaw.local/capabilities")
    monkeypatch.setenv("OPENCLAW_SANDBOX_BRIDGE_TOKEN", "bridge-token")
    monkeypatch.setattr(openclaw_capability_catalog.requests, "get", fake_get)

    catalog = openclaw_capability_catalog.get_openclaw_capability_catalog()

    assert captured["url"] == "http://openclaw.local/capabilities"
    assert captured["headers"]["Authorization"] == "Bearer bridge-token"
    assert catalog["source"] == "openclaw"
    assert catalog["actions"][0]["localos_capability"] == "social.post.publish_supervised_browser"


def test_openclaw_planner_loop_uses_catalog_without_tool_execution():
    from services.agent_openclaw_planner_loop import build_openclaw_planner_loop

    result = build_openclaw_planner_loop(
        {
            "schema": "localos_openclaw_planner_context_v1",
            "allowed_capabilities": ["google_sheets.read_rows", "communications.draft"],
            "required_bindings": [
                {
                    "key": "google_sheets_read",
                    "provider": "google_sheets",
                    "capability": "google_sheets.read_rows",
                    "required_config": ["spreadsheet_id", "sheet_name"],
                },
                {
                    "key": "telegram_delivery",
                    "provider": "telegram",
                    "capability": "communications.draft",
                    "required_config": ["bot_mode"],
                },
            ],
            "connection_state": {
                "missing_connections": [
                    {
                        "key": "google_sheets_read",
                        "provider": "google_sheets",
                        "provider_title": "Google Sheets",
                        "status": "missing",
                        "missing_config": ["spreadsheet_id", "sheet_name"],
                    }
                ],
            },
            "output_contract": {
                "format": "json_only",
                "compiled_workflow_owner": "localos",
            },
            "approval_required_action_classes": ["external_send"],
            "forbidden_action_classes": ["unauthorized_external_system_access"],
        },
        openclaw_catalog={
            "source": "openclaw",
            "actions": [
                {
                    "openclaw_action_ref": "openclaw.google_sheets.read_rows",
                    "localos_capability": "google_sheets.read_rows",
                    "service": "google_sheets",
                    "risk_class": "read",
                    "required_auth": ["google_sheets"],
                    "provider_candidates": [{"provider": "openclaw", "state": "available", "role": "planner_or_connector"}],
                },
                {
                    "openclaw_action_ref": "openclaw.telegram.create_draft",
                    "localos_capability": "communications.draft",
                    "service": "telegram",
                    "risk_class": "draft",
                    "required_auth": ["telegram"],
                    "provider_candidates": [{"provider": "openclaw", "state": "available", "role": "planner_or_connector"}],
                },
            ],
        },
    )

    assert result["schema"] == "localos_openclaw_planner_loop_v1"
    assert result["mode"] == "design_time_only"
    assert result["may_execute_tools"] is False
    assert result["must_compile_in_localos"] is True
    assert result["planner_contract"]["schema"] == "localos_openclaw_planner_contract_v1"
    assert result["planner_contract"]["tool_execution_allowed"] is False
    assert result["planner_contract"]["external_side_effects_allowed"] is False
    assert result["planner_contract"]["compiled_workflow_owner"] == "localos"
    assert result["planner_contract"]["required_response_schema"]["workflow_draft"] == "object"
    assert "execute_tools" in result["planner_contract"]["must_not"]
    assert result["status"] == "needs_clarification"
    assert result["clarifying_questions"][0]["key"] == "connect_google_sheets"
    assert any(item["key"] == "google_sheets_target" for item in result["clarifying_questions"])
    assert result["workflow_proposal"]["policy"] == "localos_envelope"
    assert {"capability": "google_sheets.read_rows", "provider_path": "openclaw:available"} in result["workflow_proposal"]["provider_paths"]
    assert result["workflow_proposal"]["openclaw_action_refs"] == [
        "openclaw.google_sheets.read_rows",
        "openclaw.telegram.create_draft",
    ]


def test_openclaw_planner_loop_requires_workflow_details_before_draft():
    from services.agent_openclaw_planner_loop import build_openclaw_planner_loop

    result = build_openclaw_planner_loop(
        {
            "schema": "localos_openclaw_planner_context_v1",
            "task": "Сделай агента: бери заказ из Google Sheets и делай пост в Telegram",
            "allowed_capabilities": ["google_sheets.read_rows", "communications.draft"],
            "required_bindings": [
                {
                    "key": "google_sheets_read",
                    "provider": "google_sheets",
                    "capability": "google_sheets.read_rows",
                    "required_config": ["spreadsheet_id", "sheet_name"],
                },
                {
                    "key": "telegram_delivery",
                    "provider": "telegram",
                    "capability": "communications.draft",
                    "required_config": ["bot_mode"],
                },
            ],
            "connection_state": {},
            "connection_answer_bindings": {},
            "output_contract": {
                "format": "json_only",
                "compiled_workflow_owner": "localos",
            },
        }
    )

    questions = {item["key"]: item for item in result["clarifying_questions"]}

    assert result["status"] == "needs_clarification"
    assert result["may_execute_tools"] is False
    assert questions["google_sheets_target"]["reason"] == "openclaw_workflow_detail_missing"
    assert questions["telegram_target"]["reason"] == "openclaw_workflow_detail_missing"
    assert questions["schedule_frequency"]["reason"] == "openclaw_workflow_detail_missing"
    assert questions["post_format"]["reason"] == "openclaw_workflow_detail_missing"
    assert "blocking_workflow_details_before_draft" in result["planner_contract"]["must_return"]
