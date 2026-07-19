import json
from datetime import datetime, timezone
from pathlib import Path

from tests.agent_blueprint_fakes import *  # noqa: F403


def test_agent_builder_session_understands_document_task_and_asks_questions():
    from services.agent_builder_session import build_agent_builder_state

    state = build_agent_builder_state(
        [{"role": "user", "content": "Нужен агент, который проверяет договоры и ищет риски"}],
    )

    assert state["category"] == "documents"
    assert state["preview"]["category"] == "documents"
    assert "Понял задачу" in state["messages"][-1]["content"]
    assert state["preview"]["external_dispatch_performed"] is False
    assert state["missing_questions"]
    assert any("документ" in item["question"].lower() for item in state["missing_questions"])


def test_agent_builder_session_reduces_questions_after_clarification():
    from services.agent_builder_session import append_user_message, build_agent_builder_state

    messages = [{"role": "user", "content": "Сделай агента"}]
    initial = build_agent_builder_state(messages)
    clarified_messages = append_user_message(
        initial["messages"],
        "Он проверяет договоры из DOCX, извлекает суммы, сроки и риски, результат нужен как краткий отчёт, человек проверяет итог.",
    )
    clarified = build_agent_builder_state(clarified_messages)

    assert clarified["category"] == "documents"
    assert len(clarified["missing_questions"]) < len(initial["missing_questions"])
    assert clarified["preview"]["output_format"]


def test_agent_builder_session_does_not_repeat_review_draft_question_after_answer():
    from services.agent_builder_session import append_user_message, build_agent_builder_state

    messages = [
        {
            "role": "user",
            "content": (
                "Агент должен парсить отзывы каждую среду в 9 утра. Все отображать в аккаунте ЛокалОС. "
                "Если появляются новые, то генерировать ответ и оповещать меня в телеграмме + присылать отзыв и ответ"
            ),
        }
    ]
    initial = build_agent_builder_state(messages)
    clarified_messages = append_user_message(
        initial["messages"],
        "Отдельные чероновики человек проверяет в телегираме - по оповещению",
    )
    clarified = build_agent_builder_state(clarified_messages)

    repeated_questions = [
        item["question"]
        for item in clarified["missing_questions"]
        if "отдельные черновики ответов или общий план реакции" in item["question"].lower()
    ]
    assert repeated_questions == []
    assert all(item["key"] != "output" for item in clarified["missing_questions"])


def test_agent_builder_session_preview_includes_feasibility_for_required_connectors():
    from services.agent_builder_session import build_agent_builder_state

    state = build_agent_builder_state(
        [
            {
                "role": "user",
                "content": (
                    "Мне нужен агент, который из Google таблицы со списком заказов берёт один заказ "
                    "за предыдущий день и создаёт пост в Telegram. Человек проверяет перед публикацией. "
                    "Формат: короткий текст в стиле довольных пассажиров. "
                    "Таблица https://docs.google.com/spreadsheets/d/1s79gWCm7A8X1drwN6yAscetf0adpRkamHCJyHCKyIqY/edit?gid=0#gid=0, "
                    "вкладка Sheet1. Telegram канал @riderra_updates."
                ),
            }
        ],
        connected_integrations=[
            {
                "id": "telegram-1",
                "provider": "telegram",
                "status": "active",
                "display_name": "Business bot",
                "config": {"bot_mode": "business_bot"},
            }
        ],
    )

    preview = state["preview"]
    feasibility = preview["feasibility"]

    assert preview["category"] == "custom"
    assert preview["capability_allowlist"] == ["google_sheets.read_rows", "communications.draft"]
    assert [item["provider"] for item in preview["required_connectors"]] == ["google_sheets", "telegram"]
    assert preview["required_connectors"][0]["action"]["kind"] == "connect_after_draft"
    assert preview["required_connectors"][0]["action"]["after_draft"] == "open_agent_connections"
    assert preview["required_connectors"][1]["action"]["kind"] == "connected"
    assert feasibility["status"] == "needs_connection"
    assert [item["provider"] for item in feasibility["missing_connections"]] == ["google_sheets"]
    assert feasibility["ready_bindings"][0]["provider"] == "telegram"
    assert preview["setup_flow"]["schema"] == "localos_agent_builder_setup_flow_v1"
    assert preview["setup_flow"]["status"] == "needs_connection"
    assert preview["setup_flow"]["primary_action"] == "choose_route"
    assert preview["setup_flow"]["next_step"] == "create_draft_then_choose_route"
    assert preview["setup_flow"]["post_create_status"] == "needs_provider_route"
    assert preview["setup_flow"]["post_create_next_step"] == "choose_provider_route"
    assert preview["setup_flow"]["can_create_draft"] is True
    assert preview["setup_flow"]["can_activate"] is False
    assert preview["setup_flow"]["steps"][1]["key"] == "clarify"
    assert preview["setup_flow"]["steps"][1]["status"] == "done"
    assert preview["setup_flow"]["steps"][-2]["key"] == "preview"
    assert preview["setup_flow"]["steps"][-1]["key"] == "activate"
    assert not any(item["type"] == "clarification" for item in preview["setup_flow"]["activation_blockers"])
    assert any(item["type"] == "connection" and item["provider"] == "google_sheets" for item in preview["setup_flow"]["activation_blockers"])
    assert preview["connection_plan"]["schema"] == "localos_agent_connection_plan_v1"
    assert preview["connection_plan"]["status"] == "needs_action"
    assert preview["connection_plan"]["items"][0]["action"] == "choose_route"
    assert preview["connection_plan"]["items"][0]["recommended_route"]["provider"] == "openclaw"
    assert "OpenClaw" in preview["connection_plan"]["items"][0]["recommended_route_reason"]
    assert preview["connection_plan"]["items"][1]["action"] == "choose_route"
    assert preview["connection_summary"]["schema"] == "localos_agent_connection_summary_v1"
    assert preview["connection_summary"]["status"] == "needs_connection"
    assert preview["connection_summary"]["missing_count"] == 0
    assert preview["connection_summary"]["route_count"] == 2
    assert preview["connection_summary"]["ready_count"] == 0
    assert preview["connection_summary"]["next_action"] == "choose_provider_routes"
    assert preview["connection_summary"]["items"][0]["action"] == "choose_route"
    assert preview["connection_summary"]["items"][0]["setup_cta"]["mode"] == "choose_route"
    assert "маршрут" in preview["connection_summary"]["items"][0]["setup_cta"]["label"].lower()
    assert preview["connection_summary"]["items"][1]["action"] == "choose_route"
    assert preview["connection_readiness"]["schema"] == "localos_agent_connection_readiness_v1"
    assert preview["connection_readiness"]["next_action"] == "choose_provider_routes"
    assert preview["connection_readiness"]["post_create_workspace"] == "connections"
    assert preview["connection_readiness"]["required_count"] == 2
    assert preview["connection_readiness"]["missing_count"] == 0
    assert preview["connection_readiness"]["route_count"] == 2
    assert preview["connection_readiness"]["ready_count"] == 0
    assert preview["connection_readiness"]["missing_services"] == []
    assert preview["connection_readiness"]["route_services"][0]["provider"] == "google_sheets"
    assert preview["connection_readiness"]["route_services"][0]["recommended_route"]["provider"] == "openclaw"
    assert preview["connection_readiness"]["ready_services"] == []
    assert preview["connection_readiness"]["services"][0]["provider_route_cta"]
    assert preview["connection_resolver"]["schema"] == "localos_agent_connection_resolver_v1"
    assert preview["connection_resolver"]["next_action"] == "resolve_connections"
    assert preview["connection_resolver"]["required_count"] == 2
    assert preview["connection_resolver"]["unresolved_count"] == 2
    assert preview["connection_resolver"]["items"][0]["role_label"] == "Источник данных"
    assert preview["connection_resolver"]["items"][0]["service_label"] == "Google Sheets"
    assert preview["connection_resolver"]["items"][0]["recommended_provider"] == "openclaw"
    assert "OpenClaw boundary" in preview["connection_resolver"]["items"][0]["explanation"]
    assert preview["connection_resolver"]["items"][1]["role_label"] == "Куда подготовить результат"
    assert preview["connection_resolver"]["items"][1]["state"] == "choose_route"
    assert preview["connector_intelligence"]["schema"] == "localos_agent_connector_intelligence_v1"
    assert preview["connector_intelligence"]["status"] == "needs_connection"
    assert preview["connector_intelligence"]["can_compile_draft"] is True
    assert preview["connector_intelligence"]["can_preview_after_connections"] is False
    assert preview["connector_intelligence"]["bindings"][0]["action"] == "choose_route"
    assert preview["connector_intelligence"]["bindings"][0]["route_state"] == "available"
    assert preview["connector_intelligence"]["bindings"][0]["recommended_route"]["provider"] == "openclaw"
    assert any(item["provider"] == "native_localos" for item in preview["connector_intelligence"]["bindings"][0]["provider_routes"])
    assert preview["connector_intelligence"]["bindings"][0]["setup_cta"]["mode"] == "choose_route"
    assert preview["connector_intelligence"]["bindings"][1]["action"] == "choose_route"
    assert preview["connector_intelligence"]["bindings"][1]["route_state"] == "connected"
    assert preview["connector_intelligence"]["capabilities"][0]["route_state"] == "available"
    assert any(item["label"] == "OpenClaw" for item in preview["connector_intelligence"]["provider_paths"])
    assert preview["service_intelligence"]["schema"] == "localos_agent_service_intelligence_v1"
    assert preview["service_intelligence"]["status"] == "needs_connection"
    assert preview["service_intelligence"]["can_create_draft"] is True
    assert preview["service_intelligence"]["can_activate"] is False
    assert preview["service_intelligence"]["state_counts"]["route_choice"] == 2
    assert preview["service_intelligence"]["state_counts"].get("already_connected", 0) == 0
    service_states = {
        item["provider"]: item["state"]
        for item in preview["service_intelligence"]["items"]
        if item.get("kind") == "binding"
    }
    assert service_states["google_sheets"] == "route_choice"
    assert service_states["telegram"] == "route_choice"
    assert any(
        item["provider"] == "google_sheets" and item["next_action"] == "choose_provider_route"
        for item in preview["service_intelligence"]["items"]
    )
    assert preview["openclaw_planner_loop"]["schema"] == "localos_openclaw_planner_loop_v1"
    assert preview["openclaw_planner_loop"]["may_execute_tools"] is False
    assert "openclaw.google_sheets.read_rows" in preview["openclaw_planner_loop"]["workflow_proposal"]["openclaw_action_refs"]
    assert any(item["key"] == "google_sheets_target" for item in state["missing_questions"])
    assert any(item["reason"] == "connection_resolver" and item["provider"] == "google_sheets" for item in state["preview"]["connection_resolver_questions"])
    assert state["preview"]["connection_resolver_questions"][0]["key"] == "google_sheets_target"
    assert any("таблиц" in item["question"].lower() for item in state["missing_questions"])
    assert "Google Sheets" in state["messages"][-1]["content"]


def test_agent_builder_session_extracts_connection_answers_into_bindings():
    from services.agent_builder_session import build_agent_builder_state

    state = build_agent_builder_state(
        [
            {
                "role": "user",
                "content": (
                    "Каждый день бери заказ из Google Sheets за вчера и готовь пост в Telegram. "
                    "Результат нужен как черновик поста. Перед публикацией человек проверяет результат. "
                    "Таблица https://docs.google.com/spreadsheets/d/1s79gWCm7A8X1drwN6yAscetf0adpRkamHCJyHCKyIqY/edit?gid=0#gid=0, "
                    "вкладка Sheet1. Telegram канал @riderra_updates"
                ),
            }
        ],
    )

    answer_bindings = state["preview"]["connection_answer_bindings"]

    assert answer_bindings["google_sheets_read"]["spreadsheet_id"] == "1s79gWCm7A8X1drwN6yAscetf0adpRkamHCJyHCKyIqY"
    assert answer_bindings["google_sheets_read"]["sheet_name"] == "Sheet1"
    assert answer_bindings["google_sheets_read"]["gid"] == "0"
    assert answer_bindings["telegram_delivery"]["telegram_target"] == "@riderra_updates"
    assert answer_bindings["telegram_delivery"]["target_type"] == "chat_or_channel"


def test_agent_builder_answer_resources_allow_draft_but_not_preview_without_provider_route():
    from api import agent_builder_api
    from services.agent_blueprint_draft_builder import compile_agent_blueprint
    from services.agent_builder_session import build_agent_builder_state
    from services.agent_integration_preflight import build_agent_integration_preflight

    prompt = (
        "Каждый день бери заказ из Google Sheets за вчера и готовь пост в Telegram. "
        "Результат нужен как черновик поста. Перед публикацией человек проверяет результат. "
        "Таблица https://docs.google.com/spreadsheets/d/1s79gWCm7A8X1drwN6yAscetf0adpRkamHCJyHCKyIqY/edit?gid=0#gid=0, "
        "вкладка Sheet1. Telegram канал @riderra_updates"
    )
    state = build_agent_builder_state([{"role": "user", "content": prompt}], business_id="biz1", user_id="user1")
    preview = state["preview"]
    draft = compile_agent_blueprint(
        preview["understood_task"],
        preview["category"],
        business_id="biz1",
        user_id="user1",
        planner_context=preview["openclaw_planner_context"],
    )
    answer_bindings = preview["connection_answer_bindings"]
    metadata = agent_builder_api._apply_answer_connection_bindings(dict(draft["metadata"]), answer_bindings)
    version_payload = agent_builder_api._apply_answer_bindings_to_version_payload(dict(draft["version_payload"]), answer_bindings)

    class Cursor:
        def __init__(self):
            self.rows = []

        def execute(self, query, params=None):
            self.rows = []

        def fetchall(self):
            return self.rows

    preflight = build_agent_integration_preflight(
        Cursor(),
        business_id="biz1",
        metadata=metadata,
        input_payload={},
    )
    preflight_by_key = {
        item["key"]: item
        for item in preflight["items"]
        if isinstance(item, dict)
    }
    version_bindings = {
        item["key"]: item
        for item in version_payload["required_integration_bindings"]
        if isinstance(item, dict)
    }

    assert preview["setup_flow"]["can_create_draft"] is True
    assert preview["setup_flow"]["post_create_status"] == "needs_provider_route"
    assert state["missing_questions"]
    assert metadata["builder_answer_connection_bindings"]["google_sheets_read"]["spreadsheet_id"] == "1s79gWCm7A8X1drwN6yAscetf0adpRkamHCJyHCKyIqY"
    assert metadata["builder_answer_connection_bindings"]["telegram_delivery"]["telegram_target"] == "@riderra_updates"
    assert version_bindings["google_sheets_read"]["default_config"]["spreadsheet_id"] == "1s79gWCm7A8X1drwN6yAscetf0adpRkamHCJyHCKyIqY"
    assert version_bindings["google_sheets_read"]["answer_configured"] is True
    assert version_bindings["telegram_delivery"]["default_config"]["telegram_target"] == "@riderra_updates"
    assert preflight["ready"] is False
    assert preflight_by_key["google_sheets_read"]["resolution"] == "builder_answer_needs_provider_route"
    assert preflight_by_key["google_sheets_read"]["missing_config"] == []
    assert preflight_by_key["telegram_delivery"]["resolution"] == "builder_answer_needs_provider_route"


def test_agent_builder_setup_flow_points_ready_connectors_to_preview_run():
    from services.agent_builder_session import build_agent_builder_state

    state = build_agent_builder_state(
        [
            {
                "role": "user",
                "content": (
                    "Каждый день бери заказ из Google Sheets за вчера и готовь пост в Telegram. "
                    "Результат нужен как черновик поста. Перед публикацией человек проверяет результат."
                ),
            }
        ],
        connected_integrations=[
            {
                "id": "sheets-1",
                "provider": "google_sheets",
                "status": "active",
                "display_name": "Orders sheet",
                "config": {"spreadsheet_id": "sheet-1", "sheet_name": "Orders"},
            },
            {
                "id": "telegram-1",
                "provider": "telegram",
                "status": "active",
                "display_name": "Business bot",
                "config": {"bot_mode": "business_bot"},
            },
        ],
    )

    setup_flow = state["preview"]["setup_flow"]

    assert setup_flow["status"] == "ready_for_draft"
    assert setup_flow["next_step"] == "create_draft_then_choose_route"
    assert setup_flow["post_create_status"] == "needs_provider_route"
    assert setup_flow["post_create_next_step"] == "choose_provider_route"
    assert setup_flow["can_create_draft"] is True
    assert setup_flow["can_run_preview"] is False
    assert setup_flow["can_activate"] is False
    assert setup_flow["steps"][-2]["status"] == "blocked"
    assert "маршрут" in setup_flow["post_create_description"].lower()
    assert state["preview"]["connection_readiness"]["next_action"] == "choose_provider_routes"
    assert state["preview"]["connection_readiness"]["post_create_workspace"] == "connections"
    assert state["preview"]["connection_readiness"]["can_run_preview_after_create"] is False
    assert state["preview"]["connection_readiness"]["ready_count"] == 0
    assert [item["action"] for item in state["preview"]["connection_summary"]["items"]] == ["choose_route", "choose_route"]
    assert state["preview"]["connection_resolver"]["next_action"] == "resolve_connections"
    assert state["preview"]["connection_resolver"]["resolved_count"] == 0
    assert state["preview"]["connection_resolver"]["unresolved_count"] == 2


def test_compiled_agent_creation_contract_google_sheets_to_telegram():
    from api import agent_blueprints_api, agent_builder_api
    from services.agent_blueprint_draft_builder import compile_agent_blueprint
    from services.agent_integration_preflight import build_agent_integration_preflight
    from services.agent_builder_session import build_agent_builder_state

    prompt = (
        "Каждый день бери заказ из Google Sheets за вчера и готовь пост в Telegram. "
        "Результат нужен как черновик поста. Перед публикацией человек проверяет результат. "
        "Таблица https://docs.google.com/spreadsheets/d/1s79gWCm7A8X1drwN6yAscetf0adpRkamHCJyHCKyIqY/edit?gid=0#gid=0, "
        "вкладка Sheet1. Telegram канал @riderra_updates"
    )
    connected_integrations = [
        {
            "id": "sheets-1",
            "provider": "google_sheets",
            "status": "active",
            "display_name": "Orders sheet",
            "config": {"spreadsheet_id": "spreadsheet-1", "sheet_name": "Orders"},
        },
        {
            "id": "telegram-1",
            "provider": "telegram",
            "status": "active",
            "display_name": "Business bot",
            "config": {"bot_mode": "business_bot"},
        },
    ]
    state = build_agent_builder_state(
        [{"role": "user", "content": prompt}],
        connected_integrations=connected_integrations,
        business_id="biz1",
        user_id="user1",
    )

    preview = state["preview"]
    setup_flow = preview["setup_flow"]

    assert [item["reason"] for item in state["missing_questions"]] == [
        "connection_resolver",
        "connection_resolver",
    ]
    assert [item["provider"] for item in state["missing_questions"]] == ["google_sheets", "telegram"]
    assert setup_flow["status"] == "ready_for_draft"
    assert setup_flow["next_step"] == "create_draft_then_choose_route"
    assert setup_flow["post_create_next_step"] == "choose_provider_route"
    assert preview["connector_intelligence"]["status"] == "ready"
    assert [item["action"] for item in preview["connection_summary"]["items"]] == ["choose_route", "choose_route"]
    assert preview["openclaw_planner_loop"]["may_execute_tools"] is False
    assert "openclaw.google_sheets.read_rows" in preview["openclaw_planner_loop"]["workflow_proposal"]["openclaw_action_refs"]

    selected_bindings = agent_builder_api._selected_connection_bindings(
        {"selected_connection_bindings": {}},
        preview,
        connected_integrations,
    )
    draft = compile_agent_blueprint(
        preview["understood_task"],
        preview["category"],
        business_id="biz1",
        user_id="user1",
        planner_context=preview["openclaw_planner_context"],
    )
    metadata = dict(draft["metadata"])
    metadata["execution_mode"] = "manual"
    metadata["agent_builder_preview"] = preview
    metadata["required_connectors"] = preview["required_connectors"]
    metadata["builder_setup_flow"] = setup_flow
    metadata = agent_builder_api._apply_selected_connection_bindings(metadata, selected_bindings)

    class Cursor:
        def __init__(self):
            self.rows = []

        def execute(self, query, params=None):
            normalized_query = " ".join(query.split()).lower()
            self.rows = []
            if "from agent_integrations" in normalized_query:
                return None
            if "from agent_runs" in normalized_query:
                self.rows = [
                    {
                        "id": "run-1",
                        "status": "completed",
                        "input_json": {
                            "schema": "localos_agent_preview_input_v1",
                            "preview_mode": True,
                            "external_side_effects_allowed": False,
                            "source": "agent_preview",
                        },
                        "output_json": {},
                        "error_text": "",
                        "started_at": datetime(2026, 6, 11, tzinfo=timezone.utc),
                        "completed_at": datetime(2026, 6, 11, tzinfo=timezone.utc),
                        "updated_at": datetime(2026, 6, 11, tzinfo=timezone.utc),
                    }
                ]
                return None
            raise AssertionError(f"Unhandled SQL: {query}")

        def fetchall(self):
            return self.rows

    preflight = build_agent_integration_preflight(
        Cursor(),
        business_id="biz1",
        metadata=metadata,
        input_payload={},
    )
    post_create_handoff = agent_builder_api._build_post_create_handoff(preflight)
    blueprint = {
        "id": "bp1",
        "business_id": "biz1",
        "category": "custom",
        "description": preview["understood_task"],
        "metadata_json": metadata,
    }
    version = {
        "id": "version-1",
        "version_number": 1,
        "goal": draft["version_payload"]["goal"],
        "inputs_schema_json": draft["version_payload"]["inputs_schema"],
        "steps_json": draft["version_payload"]["steps"],
        "capability_allowlist_json": draft["version_payload"]["capability_allowlist"],
        "approval_policy_json": draft["version_payload"]["approval_policy"],
        "output_schema_json": draft["version_payload"]["output_schema"],
    }
    preview_input = agent_blueprints_api._build_agent_preview_run_input(
        blueprint,
        version,
        {"input": {}},
    )
    activation_gate = agent_blueprints_api._build_activation_gate_summary(
        Cursor(),
        blueprint,
        version,
        metadata,
    )

    assert selected_bindings["google_sheets_read"]["selection_source"] == "auto_single_connection"
    assert selected_bindings["telegram_delivery"]["selection_source"] == "auto_single_connection"
    assert metadata["agent_binding_integrations"]["google_sheets_read"]["integration_id"] == "sheets-1"
    assert metadata["agent_binding_integrations"]["telegram_delivery"]["integration_id"] == "telegram-1"
    assert preflight["ready"] is False
    assert {item["provider"]: item["resolution"] for item in preflight["items"]} == {
        "google_sheets": "provider_route_required",
        "telegram": "provider_route_required",
    }
    assert post_create_handoff["status"] == "needs_provider_route"
    assert post_create_handoff["next_step"] == "choose_provider_route"
    assert preview_input["schema"] == "localos_agent_preview_input_v1"
    assert preview_input["preview_mode"] is True
    assert preview_input["external_side_effects_allowed"] is False
    assert preview_input["google_sheets"]["read_only"] is True
    assert preview_input["telegram"]["draft_only"] is True
    assert activation_gate["can_activate"] is False
    assert activation_gate["next_step"] == "choose_provider_route"

    selected_provider_routes = agent_builder_api._selected_provider_routes(
        {"selected_provider_routes": {"google_sheets_read": "openclaw", "telegram_delivery": "openclaw"}},
        preview,
    )
    route_metadata = agent_builder_api._apply_selected_provider_routes(dict(metadata), selected_provider_routes)
    route_preflight = build_agent_integration_preflight(
        Cursor(),
        business_id="biz1",
        metadata=route_metadata,
        input_payload={},
    )

    assert selected_provider_routes["google_sheets_read"]["provider"] == "openclaw"
    assert selected_provider_routes["telegram_delivery"]["provider"] == "openclaw"
    assert route_metadata["agent_binding_provider_routes"]["google_sheets_read"]["route_provider"] == "openclaw"
    assert route_metadata["agent_binding_provider_routes"]["telegram_delivery"]["route_provider"] == "openclaw"
    assert route_preflight["ready"] is True
    route_items = {
        item["key"]: item
        for item in route_preflight["items"]
        if isinstance(item, dict)
    }
    assert route_items["google_sheets_read"]["resolution"] == "provider_route_openclaw_boundary"
    assert route_items["telegram_delivery"]["resolution"] == "provider_route_openclaw_boundary"


def test_agent_builder_create_blueprint_endpoint_returns_ready_preview_handoff(monkeypatch):
    from flask import Flask

    from api import agent_builder_api
    from services.agent_builder_session import build_agent_builder_state

    prompt = (
        "Каждый день бери заказ из Google Sheets за вчера и готовь пост в Telegram. "
        "Результат нужен как черновик поста. Перед публикацией человек проверяет результат. "
        "Таблица https://docs.google.com/spreadsheets/d/1s79gWCm7A8X1drwN6yAscetf0adpRkamHCJyHCKyIqY/edit?gid=0#gid=0, "
        "вкладка Sheet1. Telegram канал @riderra_updates"
    )
    connected_integrations = [
        {
            "id": "sheets-1",
            "business_id": "biz1",
            "provider": "google_sheets",
            "status": "active",
            "display_name": "Orders sheet",
            "config_json": {"spreadsheet_id": "spreadsheet-1", "sheet_name": "Orders"},
        },
        {
            "id": "telegram-1",
            "business_id": "biz1",
            "provider": "telegram",
            "status": "active",
            "display_name": "Business bot",
            "config_json": {"bot_mode": "business_bot"},
        },
    ]
    state = build_agent_builder_state(
        [{"role": "user", "content": prompt}],
        connected_integrations=[
            {
                "id": "sheets-1",
                "provider": "google_sheets",
                "status": "active",
                "display_name": "Orders sheet",
                "config": {"spreadsheet_id": "spreadsheet-1", "sheet_name": "Orders"},
            },
            {
                "id": "telegram-1",
                "provider": "telegram",
                "status": "active",
                "display_name": "Business bot",
                "config": {"bot_mode": "business_bot"},
            },
        ],
        business_id="biz1",
        user_id="user1",
    )

    class FakeConnection:
        def __init__(self):
            self.cursor_instance = FakeCursor()
            self.committed = False
            self.rolled_back = False

        def cursor(self):
            return self.cursor_instance

        def commit(self):
            self.committed = True

        def rollback(self):
            self.rolled_back = True

    class FakeDatabase:
        def __init__(self):
            self.conn = fake_connection
            self.closed = False

        def close(self):
            self.closed = True

    class FakeCursor:
        def __init__(self):
            self.sessions = {
                "session-1": {
                    "id": "session-1",
                    "business_id": "biz1",
                    "created_by_user_id": "user1",
                    "status": "draft",
                    "initial_prompt": prompt,
                    "category": state["category"],
                    "messages_json": state["messages"],
                    "preview_json": state["preview"],
                    "missing_questions_json": state["missing_questions"],
                    "blueprint_id": None,
                }
            }
            self.integrations = connected_integrations
            self.blueprints = {}
            self.versions = {}
            self.last_result = None
            self.last_results = []

        def execute(self, query, params=None):
            normalized_query = " ".join(query.split()).lower()
            params = params or ()
            self.last_result = None
            self.last_results = []
            if normalized_query.startswith("select * from agent_builder_sessions"):
                self.last_result = self.sessions.get(params[0])
                return None
            if normalized_query.startswith("select id, provider, status, display_name, config_json"):
                business_id = params[0]
                self.last_results = [item for item in self.integrations if item["business_id"] == business_id]
                return None
            if normalized_query.startswith("select id, source, display_name"):
                self.last_results = []
                return None
            if normalized_query.startswith("select telegram_bot_token"):
                self.last_result = {"telegram_bot_token": ""}
                return None
            if normalized_query.startswith("insert into agent_blueprints"):
                metadata = json.loads(params[7])
                self.blueprints[params[0]] = {
                    "id": params[0],
                    "business_id": params[1],
                    "name": params[2],
                    "category": params[3],
                    "description": params[4],
                    "status": params[5],
                    "created_by_user_id": params[6],
                    "metadata_json": metadata,
                }
                return None
            if normalized_query.startswith("select coalesce(max(version_number)"):
                self.last_result = {"next_version": 1}
                return None
            if normalized_query.startswith("insert into agent_blueprint_versions"):
                self.versions[params[0]] = {
                    "id": params[0],
                    "blueprint_id": params[1],
                    "version_number": params[2],
                    "goal": params[3],
                    "inputs_schema_json": json.loads(params[4]),
                    "steps_json": json.loads(params[5]),
                    "persona_agent_id": params[6],
                    "capability_allowlist_json": json.loads(params[7]),
                    "approval_policy_json": json.loads(params[8]),
                    "output_schema_json": json.loads(params[9]),
                    "created_by_user_id": params[10],
                }
                return None
            if normalized_query.startswith("select * from agent_blueprint_versions where id"):
                self.last_result = self.versions.get(params[0])
                return None
            if normalized_query.startswith("update agent_builder_sessions"):
                session = self.sessions.get(params[6])
                session["status"] = params[0]
                session["category"] = params[1]
                session["messages_json"] = json.loads(params[2])
                session["preview_json"] = json.loads(params[3])
                session["missing_questions_json"] = json.loads(params[4])
                if params[5]:
                    session["blueprint_id"] = params[5]
                return None
            if normalized_query.startswith("select b.*"):
                blueprint = self.blueprints.get(params[0])
                latest_version = next(
                    (version for version in self.versions.values() if version["blueprint_id"] == params[0]),
                    None,
                )
                self.last_result = {
                    **blueprint,
                    "latest_version_id": latest_version["id"],
                    "latest_version_number": latest_version["version_number"],
                    "latest_goal": latest_version["goal"],
                }
                return None
            if "from agent_integrations" in normalized_query:
                business_id = params[0]
                self.last_results = [item for item in self.integrations if item["business_id"] == business_id]
                return None
            raise AssertionError(f"Unhandled SQL: {query}")

        def fetchone(self):
            return self.last_result

        def fetchall(self):
            return self.last_results

    fake_connection = FakeConnection()
    monkeypatch.setattr(agent_builder_api, "DatabaseManager", FakeDatabase)
    monkeypatch.setattr(agent_builder_api, "_require_auth", lambda: ({"user_id": "user1"}, None))
    monkeypatch.setattr(agent_builder_api, "_require_business_access", lambda cursor, business_id, user_data: (True, None))
    monkeypatch.setattr(
        agent_builder_api,
        "charge_agent_creation_credits",
        lambda cursor, business_id, user_id, source_id, description: {
            "status": "charged",
            "action_key": "agent_creation",
            "actual_credits": 3,
        },
    )

    app = Flask(__name__)
    request_context = app.test_request_context(
        "/api/agent-builder/sessions/session-1/create-blueprint",
        method="POST",
        json={
            "selected_provider_routes": {
                "google_sheets_read": "openclaw",
                "telegram_delivery": "openclaw",
            },
            "accepted_provider_routes": True,
        },
    )
    request_context.push()
    try:
        response, status_code = agent_builder_api.create_blueprint_from_agent_builder_session("session-1")
    finally:
        request_context.pop()

    payload = response.get_json()
    blueprint_id = payload["blueprint"]["id"]
    metadata = fake_connection.cursor_instance.blueprints[blueprint_id]["metadata_json"]

    assert status_code == 201
    assert fake_connection.committed is True
    assert fake_connection.rolled_back is False
    assert payload["success"] is True
    assert payload["next_step"] == "run_preview"
    assert payload["post_create_handoff"]["status"] == "ready_for_preview"
    assert payload["post_create_handoff"]["workspace_mode"] == "run"
    assert payload["connection_preflight"]["ready"] is True
    assert {item["provider"]: item["resolution"] for item in payload["connection_preflight"]["items"]} == {
        "google_sheets": "provider_route_openclaw_boundary",
        "telegram": "provider_route_openclaw_boundary",
    }
    assert payload["session"]["status"] == "blueprint_created"
    assert payload["session"]["blueprint_id"] == blueprint_id
    assert metadata["builder_selected_connection_bindings"]["google_sheets_read"]["selection_source"] == "auto_single_connection"
    assert metadata["builder_provider_routes_accepted"] is True
    assert metadata["agent_binding_provider_routes"]["telegram_delivery"]["integration_id"] == "openclaw_boundary"
    assert metadata["agent_binding_provider_routes"]["telegram_delivery"]["execution_boundary"] == "localos_policy_envelope"
    assert metadata["builder_answer_connection_bindings"]["google_sheets_read"]["spreadsheet_id"] == "1s79gWCm7A8X1drwN6yAscetf0adpRkamHCJyHCKyIqY"
    assert metadata["builder_answer_connection_bindings"]["telegram_delivery"]["telegram_target"] == "@riderra_updates"
    assert metadata["agent_binding_integrations"]["google_sheets_read"]["answer_config"]["sheet_name"] == "Sheet1"
    assert metadata["agent_binding_integrations"]["telegram_delivery"]["answer_config"]["telegram_target"] == "@riderra_updates"
    assert metadata["custom_process"]["google_sheets"]["spreadsheet_id"] == "1s79gWCm7A8X1drwN6yAscetf0adpRkamHCJyHCKyIqY"
    assert metadata["custom_process"]["telegram"]["telegram_target"] == "@riderra_updates"
    assert metadata["openclaw_planner_loop"]["may_execute_tools"] is False
    assert payload["version"]["capability_allowlist_json"] == ["google_sheets.read_rows", "communications.draft"]


def test_agent_preview_run_and_activation_endpoints_enforce_safe_gate(monkeypatch):
    from flask import Flask

    from api import agent_blueprints_api
    from api.agent_blueprints_api import _build_agent_preview_run_input
    from services.agent_blueprint_draft_builder import compile_agent_blueprint

    draft = compile_agent_blueprint(
        "Каждый день бери заказ из Google Sheets за вчера и готовь пост в Telegram. "
        "Результат нужен как черновик поста. Перед публикацией человек проверяет результат."
    )
    metadata = dict(draft["metadata"])
    metadata["execution_mode"] = "manual"
    metadata["custom_process"] = {
        "archetype": "google_sheets_to_telegram",
        "google_sheets_read": {
            "integration_id": "sheets-1",
            "spreadsheet_id": "spreadsheet-1",
            "sheet_name": "Orders",
        },
        "telegram_delivery": {
            "integration_id": "telegram-1",
            "bot_mode": "business_bot",
        },
        "google_sheets": {
            "integration_id": "sheets-1",
            "spreadsheet_id": "spreadsheet-1",
            "sheet_name": "Orders",
        },
        "telegram": {
            "integration_id": "telegram-1",
            "bot_mode": "business_bot",
        },
    }
    metadata["agent_binding_integrations"] = {
        "google_sheets_read": {
            "integration_id": "sheets-1",
            "provider": "google_sheets",
        },
        "telegram_delivery": {
            "integration_id": "telegram-1",
            "provider": "telegram",
        },
    }
    metadata["agent_binding_provider_routes"] = {
        "google_sheets_read": {
            "route_provider": "openclaw",
            "provider": "openclaw",
            "status": "active",
            "integration_id": "openclaw_boundary",
        },
        "telegram_delivery": {
            "route_provider": "openclaw",
            "provider": "openclaw",
            "status": "active",
            "integration_id": "openclaw_boundary",
        },
    }
    cursor = FakeCursor()
    cursor.tables["agent_blueprints"]["bp1"] = {
        "id": "bp1",
        "business_id": "biz1",
        "name": "Sheets to Telegram",
        "category": "custom",
        "description": "Google Sheets to Telegram",
        "status": "draft",
        "metadata_json": metadata,
    }
    cursor.tables["agent_blueprint_versions"]["ver1"] = {
        "id": "ver1",
        "blueprint_id": "bp1",
        "version_number": 1,
        "goal": draft["version_payload"]["goal"],
        "inputs_schema_json": draft["version_payload"]["inputs_schema"],
        "steps_json": draft["version_payload"]["steps"],
        "capability_allowlist_json": draft["version_payload"]["capability_allowlist"],
        "approval_policy_json": draft["version_payload"]["approval_policy"],
        "output_schema_json": draft["version_payload"]["output_schema"],
    }

    class FakeConnection:
        def __init__(self):
            self.cursor_instance = cursor
            self.commit_count = 0
            self.rollback_count = 0

        def cursor(self):
            return self.cursor_instance

        def commit(self):
            self.commit_count += 1

        def rollback(self):
            self.rollback_count += 1

    class FakeDatabase:
        def __init__(self):
            self.conn = fake_connection

        def close(self):
            return None

    fake_connection = FakeConnection()
    monkeypatch.setattr(agent_blueprints_api, "DatabaseManager", FakeDatabase)
    monkeypatch.setattr(agent_blueprints_api, "_require_auth", lambda: ({"user_id": "user1"}, None))
    monkeypatch.setattr(agent_blueprints_api, "_require_business_access", lambda cursor, business_id, user_data: (True, None))
    monkeypatch.setattr(agent_blueprints_api, "build_agent_blueprint_orchestrator", CountingOrchestrator)

    app = Flask(__name__)

    blocked_context = app.test_request_context(
        "/api/agent-blueprints/bp1/versions/ver1/activate",
        method="POST",
        json={},
    )
    blocked_context.push()
    try:
        blocked_response, blocked_status = agent_blueprints_api.activate_agent_blueprint_version("bp1", "ver1")
    finally:
        blocked_context.pop()
    blocked_payload = blocked_response.get_json()

    preflight_context = app.test_request_context(
        "/api/agent-blueprints/bp1/preflight",
        method="POST",
        json={"blueprint_version_id": "ver1", "input": {"preview_mode": True}},
    )
    preflight_context.push()
    try:
        preflight_response = agent_blueprints_api.preflight_agent_blueprint_run("bp1")
    finally:
        preflight_context.pop()
    preflight_payload = preflight_response.get_json()

    run_context = app.test_request_context(
        "/api/agent-blueprints/bp1/runs",
        method="POST",
        json={"blueprint_version_id": "ver1", "input": {"preview_mode": True}},
    )
    run_context.push()
    try:
        run_response, run_status = agent_blueprints_api.start_agent_blueprint_run("bp1")
    finally:
        run_context.pop()
    run_payload = run_response.get_json()
    run = run_payload["run"]

    activate_context = app.test_request_context(
        "/api/agent-blueprints/bp1/versions/ver1/activate",
        method="POST",
        json={"reason": "safe preview passed"},
    )
    activate_context.push()
    try:
        activate_response = agent_blueprints_api.activate_agent_blueprint_version("bp1", "ver1")
    finally:
        activate_context.pop()
    activate_payload = activate_response.get_json()

    preview_input = _build_agent_preview_run_input(
        cursor.tables["agent_blueprints"]["bp1"],
        cursor.tables["agent_blueprint_versions"]["ver1"],
        {"input": {"preview_mode": True}},
    )
    run_input = cursor.tables["agent_runs"][run["id"]]["input_json"]

    assert blocked_status == 400
    assert blocked_payload["code"] == "AGENT_ACTIVATION_GATE_BLOCKED"
    assert blocked_payload["activation_gate"]["next_step"] == "run_preview"
    assert preflight_payload["success"] is True
    assert preflight_payload["can_start"] is True
    assert preflight_payload["preview_run_gate"]["can_preview_run"] is True
    assert preflight_payload["preview_input"]["schema"] == "localos_agent_preview_input_v1"
    assert preflight_payload["preview_input"]["external_side_effects_allowed"] is False
    assert preflight_payload["preflight"]["ready"] is True
    assert run_status == 201
    assert run_payload["success"] is True
    assert run_input["schema"] == "localos_agent_preview_input_v1"
    assert run_input["preview_mode"] is True
    assert run_input["external_side_effects_allowed"] is False
    assert run["observability"]["preview_summary"]["safe_preview"] is True
    assert run["status"] in {"completed", "waiting_approval"}
    assert activate_payload["success"] is True
    assert activate_payload["active_version"]["id"] == "ver1"
    assert cursor.tables["agent_blueprints"]["bp1"]["status"] == "active"
    assert cursor.tables["agent_blueprints"]["bp1"]["metadata_json"]["active_version_id"] == "ver1"
    assert fake_connection.commit_count >= 2
    assert fake_connection.rollback_count == 0
    assert preview_input["external_side_effects_allowed"] is False


def test_browser_use_to_telegram_agent_preview_run_is_ready_after_connections(monkeypatch):
    from flask import Flask

    from api import agent_blueprints_api
    from services.agent_blueprint_draft_builder import compile_agent_blueprint

    draft = compile_agent_blueprint(
        "Через browser use открой сайт конкурента https://competitor.example, проверь изменения цен "
        "и подготовь короткое сообщение владельцу в Telegram.",
        use_ai=True,
    )
    metadata = dict(draft["metadata"])
    metadata["agent_integration_ids"] = ["browser-1", "telegram-1"]
    metadata["agent_binding_integrations"] = {
        "browser_use_read": {
            "integration_id": "browser-1",
            "provider": "browser_use",
        },
        "telegram_delivery": {
            "integration_id": "openclaw_boundary",
            "provider": "openclaw",
            "route_provider": "openclaw",
            "status": "active",
        },
    }
    metadata["agent_binding_provider_routes"] = {
        "telegram_delivery": {
            "route_provider": "openclaw",
            "provider": "openclaw",
            "status": "active",
            "integration_id": "openclaw_boundary",
            "execution_boundary": "localos_policy_envelope",
        },
    }
    metadata["custom_process"] = {
        "browser_use": {
            "integration_id": "browser-1",
            "target_urls": ["https://competitor.example"],
            "mode": "openclaw_browser_boundary",
        },
        "browser_use_read": {
            "integration_id": "browser-1",
            "target_urls": ["https://competitor.example"],
            "mode": "openclaw_browser_boundary",
        },
        "telegram": {
            "integration_id": "openclaw_boundary",
            "route_provider": "openclaw",
            "status": "active",
        },
    }
    cursor = FakeCursor()
    cursor.tables["agent_blueprints"]["bp-browser"] = {
        "id": "bp-browser",
        "business_id": "biz1",
        "name": "Мониторинг сайта конкурента",
        "category": "custom",
        "description": "Browser use проверяет сайт конкурента и готовит Telegram-отчёт.",
        "status": "draft",
        "metadata_json": metadata,
    }
    cursor.tables["agent_blueprint_versions"]["ver-browser"] = {
        "id": "ver-browser",
        "blueprint_id": "bp-browser",
        "version_number": 1,
        "goal": draft["version_payload"]["goal"],
        "inputs_schema_json": draft["version_payload"]["inputs_schema"],
        "steps_json": draft["version_payload"]["steps"],
        "capability_allowlist_json": draft["version_payload"]["capability_allowlist"],
        "approval_policy_json": draft["version_payload"]["approval_policy"],
        "output_schema_json": draft["version_payload"]["output_schema"],
    }
    cursor.tables["agent_integrations"]["browser-1"] = {
        "id": "browser-1",
        "business_id": "biz1",
        "provider": "browser_use",
        "status": "active",
        "display_name": "Browser use через OpenClaw",
        "auth_ref": None,
        "config_json": {
            "target_urls": ["https://competitor.example"],
            "mode": "openclaw_browser_boundary",
        },
        "limits_json": {"daily_page_check_cap": 12, "frequency_cap_minutes": 60},
        "connected_by_user_id": "user1",
        "created_at": "2026-06-21T10:00:00Z",
        "updated_at": "2026-06-21T10:00:00Z",
    }
    cursor.tables["agent_integrations"]["telegram-1"] = {
        "id": "telegram-1",
        "business_id": "biz1",
        "provider": "telegram",
        "status": "active",
        "display_name": "Бот владельца",
        "auth_ref": None,
        "config_json": {"bot_mode": "business_bot"},
        "limits_json": {"daily_message_cap": 30, "frequency_cap_minutes": 30},
        "connected_by_user_id": "user1",
        "created_at": "2026-06-21T10:00:00Z",
        "updated_at": "2026-06-21T10:00:00Z",
    }

    class FakeConnection:
        def __init__(self):
            self.cursor_instance = cursor
            self.commit_count = 0
            self.rollback_count = 0

        def cursor(self):
            return self.cursor_instance

        def commit(self):
            self.commit_count += 1

        def rollback(self):
            self.rollback_count += 1

    class FakeDatabase:
        def __init__(self):
            self.conn = fake_connection

        def close(self):
            return None

    fake_connection = FakeConnection()
    monkeypatch.setattr(agent_blueprints_api, "DatabaseManager", FakeDatabase)
    monkeypatch.setattr(agent_blueprints_api, "_require_auth", lambda: ({"user_id": "user1"}, None))
    monkeypatch.setattr(agent_blueprints_api, "_require_business_access", lambda cursor, business_id, user_data: (True, None))
    monkeypatch.setattr(agent_blueprints_api, "build_agent_blueprint_orchestrator", CountingOrchestrator)

    app = Flask(__name__)
    preflight_context = app.test_request_context(
        "/api/agent-blueprints/bp-browser/preflight",
        method="POST",
        json={"blueprint_version_id": "ver-browser", "input": {"preview_mode": True}},
    )
    preflight_context.push()
    try:
        preflight_response = agent_blueprints_api.preflight_agent_blueprint_run("bp-browser")
    finally:
        preflight_context.pop()
    preflight_payload = preflight_response.get_json()

    run_context = app.test_request_context(
        "/api/agent-blueprints/bp-browser/runs",
        method="POST",
        json={"blueprint_version_id": "ver-browser", "input": {"preview_mode": True}},
    )
    run_context.push()
    try:
        run_response, run_status = agent_blueprints_api.start_agent_blueprint_run("bp-browser")
    finally:
        run_context.pop()
    run_payload = run_response.get_json()
    run_input = cursor.tables["agent_runs"][run_payload["run"]["id"]]["input_json"]
    preflight_items = {
        item["key"]: item
        for item in preflight_payload["preflight"]["items"]
    }

    assert preflight_payload["success"] is True
    assert preflight_payload["can_start"] is True
    assert preflight_payload["preflight"]["ready"] is True
    assert preflight_items["browser_use_read"]["provider"] == "browser_use"
    assert preflight_items["browser_use_read"]["resolution"] == "blueprint_metadata"
    assert preflight_items["browser_use_read"]["execution_boundary"] == "connected_provider"
    assert preflight_items["telegram_delivery"]["resolution"] == "provider_route_openclaw_boundary"
    assert preflight_payload["preview_input"]["external_side_effects_allowed"] is False
    assert run_status == 201
    assert run_payload["success"] is True
    assert run_input["preview_mode"] is True
    assert run_input["external_side_effects_allowed"] is False
    assert run_payload["run"]["observability"]["preview_summary"]["safe_preview"] is True
    assert fake_connection.commit_count == 1
    assert fake_connection.rollback_count == 0


def test_agent_builder_setup_flow_blocks_draft_until_clarification_is_answered():
    from services.agent_builder_session import build_agent_builder_state

    state = build_agent_builder_state([{"role": "user", "content": "Сделай агента"}])
    setup_flow = state["preview"]["setup_flow"]

    assert setup_flow["status"] == "needs_clarification"
    assert setup_flow["primary_action"] == "answer_question"
    assert setup_flow["can_create_draft"] is False
    assert setup_flow["steps"][1]["key"] == "clarify"
    assert setup_flow["steps"][1]["status"] == "active"
    assert any(item["type"] == "clarification" for item in setup_flow["activation_blockers"])


def test_agent_builder_blocks_empty_google_sheets_to_telegram_workflow():
    from services.agent_builder_session import build_agent_builder_state

    state = build_agent_builder_state(
        [
            {
                "role": "user",
                "content": "Сделай агента: бери заказ из Google Sheets и делай пост в Telegram",
            }
        ]
    )
    setup_flow = state["preview"]["setup_flow"]
    questions = {item["key"]: item for item in state["missing_questions"]}

    assert setup_flow["status"] == "needs_clarification"
    assert setup_flow["primary_action"] == "answer_question"
    assert setup_flow["can_create_draft"] is False
    assert setup_flow["steps"][1]["status"] == "active"
    assert questions["google_sheets_target"]["reason"] == "openclaw_workflow_detail_missing"
    assert questions["telegram_target"]["reason"] == "openclaw_workflow_detail_missing"
    assert questions["schedule_frequency"]["reason"] == "openclaw_workflow_detail_missing"
    assert questions["post_format"]["reason"] == "openclaw_workflow_detail_missing"


def test_agent_builder_setup_flow_surfaces_compiler_clarifying_questions(monkeypatch):
    from services import agent_builder_session

    def fake_compile_agent_blueprint(description, category="", **kwargs):
        return {
            "name": "Google Sheets -> Telegram",
            "category": "custom",
            "description": description,
            "metadata": {
                "llm_intent": {
                    "status": "compiled_intent",
                    "source": "gigachat",
                    "intent": {
                        "clarifying_questions": [
                            "Какую вкладку Google Sheets читать?",
                            "В какой Telegram-канал готовить пост?",
                        ],
                    },
                },
                "required_integration_bindings": [
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
            },
            "version_payload": {
                "steps": [],
                "capability_allowlist": ["google_sheets.read_rows", "communications.draft"],
                "required_integration_bindings": [
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
            },
            "summary": {
                "sources": ["google_sheets", "telegram", "business_profile"],
                "capability_allowlist": ["google_sheets.read_rows", "communications.draft"],
            },
        }

    monkeypatch.setattr(agent_builder_session, "compile_agent_blueprint", fake_compile_agent_blueprint)

    state = agent_builder_session.build_agent_builder_state(
        [
            {
                "role": "user",
                "content": "Каждый день бери заказ из Google Sheets и готовь пост в Telegram.",
            }
        ],
        use_ai=True,
    )

    assert state["missing_questions"][0]["question"] == "Какую вкладку Google Sheets читать?"
    assert state["missing_questions"][0]["reason"] == "compiled_intent_clarification"
    assert state["preview"]["compiler_questions"][1]["question"] == "В какой Telegram-канал готовить пост?"
    assert state["preview"]["setup_flow"]["steps"][1]["questions"][0]["key"] == "compiler_question_1"
    assert state["preview"]["setup_flow"]["can_create_draft"] is False


def test_agent_builder_can_create_draft_when_sheet_id_is_deferred(monkeypatch):
    from services import agent_builder_session

    def fake_compile_agent_blueprint(description, category="", **kwargs):
        return {
            "name": "Orders status agent",
            "category": "custom",
            "description": description,
            "metadata": {
                "llm_intent": {
                    "status": "compiled_intent",
                    "source": "gigachat",
                    "intent": {
                        "workflow_draft": {
                            "trigger": "schedule.hourly",
                            "steps": [{"key": "read_orders", "capability": "google_sheets.read_rows"}],
                        },
                        "clarifying_questions": [
                            "Пожалуйста, уточните название Google Spreadsheet и Sheet, чтобы продолжить.",
                        ],
                        "approval_points": [{"key": "telegram_delivery", "reason": "external delivery requires approval"}],
                        "unsupported_requests": [],
                    },
                },
                "required_integration_bindings": [
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
            },
            "summary": {
                "sources": ["google_sheets", "telegram", "business_profile"],
                "capability_allowlist": ["google_sheets.read_rows", "communications.draft"],
            },
        }

    monkeypatch.setattr(agent_builder_session, "compile_agent_blueprint", fake_compile_agent_blueprint)

    state = agent_builder_session.build_agent_builder_state(
        [
            {
                "role": "user",
                "content": (
                    "Каждый час бери новые строки из Google Sheets с заказами и отправляй краткий статус "
                    "владельцу в Telegram после проверки. Таблица называется Заказы, лист Новый поток. "
                    "ID сейчас нет. Создай черновик агента без ID, а подключение конкретной таблицы "
                    "оставь следующим шагом в доступах."
                ),
            }
        ],
        use_ai=True,
    )

    assert [item["reason"] for item in state["missing_questions"]] == ["connection_resolver", "connection_resolver"]
    assert state["preview"]["setup_flow"]["can_create_draft"] is True
    assert state["preview"]["setup_flow"]["next_step"] == "create_draft_then_choose_route"
    assert state["preview"]["setup_flow"]["can_run_preview"] is False


def test_agent_builder_setup_flow_blocks_compiler_unsupported_request(monkeypatch):
    from services import agent_builder_session

    def fake_compile_agent_blueprint(description, category="", **kwargs):
        return {
            "name": "Unsafe external workflow",
            "category": "custom",
            "description": description,
            "metadata": {
                "llm_intent": {
                    "status": "compiled_intent",
                    "source": "gigachat",
                    "intent": {
                        "workflow_draft": {
                            "trigger": "schedule.daily",
                            "steps": [{"key": "read_source", "capability": "google_sheets.read_rows"}],
                        },
                        "approval_points": [{"key": "external_action", "reason": "external action requires approval"}],
                        "unsupported_requests": [
                            {
                                "request": "send without approval",
                                "reason": "Нельзя отправлять внешние сообщения без approval gate.",
                            }
                        ],
                        "clarifying_questions": [],
                    },
                },
            },
            "version_payload": {
                "steps": [],
                "capability_allowlist": [],
                "required_integration_bindings": [],
            },
            "summary": {
                "sources": ["manual_context", "business_profile"],
                "capability_allowlist": [],
            },
        }

    monkeypatch.setattr(agent_builder_session, "compile_agent_blueprint", fake_compile_agent_blueprint)

    state = agent_builder_session.build_agent_builder_state(
        [
            {
                "role": "user",
                "content": (
                    "Из Google Sheets извлеки заказы, подготовь отчёт, "
                    "человек проверяет результат перед действием."
                ),
            }
        ],
        use_ai=True,
    )

    setup_flow = state["preview"]["setup_flow"]
    review = state["preview"]["compiler_policy_review"]

    assert review["schema"] == "localos_agent_compiler_policy_review_v1"
    assert review["status"] == "blocked"
    assert review["workflow_draft"]["trigger"] == "schedule.daily"
    assert setup_flow["status"] == "blocked"
    assert setup_flow["next_step"] == "cannot_create"
    assert setup_flow["can_create_draft"] is False
    assert setup_flow["steps"][3]["status"] == "blocked"
    assert setup_flow["activation_blockers"][0]["type"] == "compiler_unsupported"


def test_agent_builder_service_intelligence_marks_multiple_existing_routes():
    from services.agent_builder_session import build_agent_builder_state

    state = build_agent_builder_state(
        [
            {
                "role": "user",
                "content": (
                    "Каждый день бери заказ из Google Sheets и готовь пост в Telegram. "
                    "Человек проверяет перед публикацией."
                ),
            }
        ],
        connected_integrations=[
            {
                "id": "telegram-1",
                "provider": "telegram",
                "status": "active",
                "display_name": "Business bot",
                "config": {"bot_mode": "business_bot"},
            },
            {
                "id": "telegram-2",
                "provider": "telegram",
                "status": "active",
                "display_name": "Marketing channel",
                "config": {"bot_mode": "business_bot"},
            },
        ],
    )

    telegram_item = next(
        item
        for item in state["preview"]["service_intelligence"]["items"]
        if item.get("kind") == "binding" and item.get("provider") == "telegram"
    )

    assert state["preview"]["feasibility"]["status"] == "needs_choice"
    assert telegram_item["state"] == "route_choice"
    assert telegram_item["state_label"] == "Нужно выбрать маршрут"
    assert telegram_item["next_action"] == "choose_provider_route"
    assert telegram_item["connection_count"] == 2


def test_agent_builder_service_intelligence_marks_forbidden_request_impossible():
    from services.agent_builder_session import build_agent_builder_state

    state = build_agent_builder_state(
        [
            {
                "role": "user",
                "content": "Сделай агента, который подключается к компьютерам Роскосмоса и скачивает файлы.",
            }
        ],
    )
    intelligence = state["preview"]["service_intelligence"]

    assert intelligence["status"] == "forbidden"
    assert intelligence["can_create_draft"] is False
    assert intelligence["state_counts"]["impossible"] >= 1
    assert any(
        item["kind"] == "policy" and item["state"] == "impossible" and item["next_action"] == "explain_policy_boundary"
        for item in intelligence["items"]
    )


def test_agent_builder_api_uses_ai_compiler_by_default():
    from api.agent_builder_api import _use_ai_compiler

    assert _use_ai_compiler({}) is True
    assert _use_ai_compiler({"use_ai_compiler": False}) is False
    assert _use_ai_compiler({"use_ai_compiler": True}) is True


def test_agent_builder_api_requires_compiler_plan_confirmation_only_for_reviewable_plan():
    from api.agent_builder_api import _compiler_plan_requires_confirmation

    assert _compiler_plan_requires_confirmation({}) is False
    assert _compiler_plan_requires_confirmation({"compiler_policy_review": {"status": "ok"}}) is False
    assert _compiler_plan_requires_confirmation(
        {
            "compiler_policy_review": {
                "workflow_draft": {
                    "trigger": "schedule.daily",
                    "steps": [{"key": "read_orders"}],
                }
            }
        }
    ) is True
    assert _compiler_plan_requires_confirmation(
        {
            "compiler_policy_review": {
                "approval_points": [{"key": "publish", "reason": "external publish"}],
            }
        }
    ) is True
    assert _compiler_plan_requires_confirmation(
        {
            "compiler_unsupported_requests": [{"reason": "No approved provider path"}],
        }
    ) is True


def test_agent_builder_api_requires_selected_provider_routes_for_required_bindings():
    from api.agent_builder_api import _missing_required_provider_routes, _required_provider_route_bindings

    preview = {
        "connection_readiness": {
            "services": [
                {
                    "key": "google_sheets_read",
                    "recommended_route": {
                        "provider": "openclaw",
                        "state": "available",
                        "provider_action": {"available": True},
                    },
                },
                {
                    "key": "telegram_delivery",
                    "recommended_route": {
                        "provider": "composio",
                        "state": "planned",
                    },
                },
            ]
        }
    }

    required = _required_provider_route_bindings(preview)

    assert required == [{"key": "google_sheets_read", "available_routes": ["openclaw"]}]
    assert _missing_required_provider_routes(preview, {}) == required
    assert _missing_required_provider_routes(preview, {"google_sheets_read": {"provider": "openclaw"}}) == []


def test_agent_builder_provider_routes_create_action_handler_contracts():
    from api import agent_builder_api

    metadata = {
        "execution_mode": "manual",
        "required_integration_bindings": [
            {"key": "google_sheets_read", "provider": "google_sheets"},
            {"key": "telegram_delivery", "provider": "telegram"},
        ],
        "custom_process": {},
    }
    selected = {
        "google_sheets_read": {
            "provider": "openclaw",
            "route_provider": "openclaw",
            "label": "OpenClaw",
            "connect_mode": "openclaw_policy_boundary",
        },
        "telegram_delivery": {
            "provider": "maton",
            "route_provider": "maton",
            "label": "Maton.ai",
            "connect_mode": "external_account_key",
            "external_account_id": "maton-account-1",
            "display_name": "Main Maton key",
        },
    }

    metadata = agent_builder_api._apply_selected_provider_routes(metadata, selected)

    assert metadata["agent_binding_provider_routes"]["google_sheets_read"]["route_provider"] == "openclaw"
    assert metadata["agent_binding_provider_routes"]["telegram_delivery"]["external_account_id"] == "maton-account-1"
    assert metadata["connector_action_handlers"]["google_sheets_read"]["handler"] == "openclaw_policy_boundary"
    assert metadata["connector_action_handlers"]["google_sheets_read"]["preflight_resolution"] == "provider_route_openclaw_boundary"
    assert metadata["connector_action_handlers"]["telegram_delivery"]["handler"] == "maton_external_account_bridge"
    assert metadata["connector_action_handlers"]["telegram_delivery"]["credential_source"] == "externalbusinessaccounts:maton"
    assert metadata["connector_action_handlers"]["telegram_delivery"]["external_side_effects_allowed_in_preview"] is False


def test_agent_builder_selected_maton_route_requires_or_auto_binds_external_account():
    from api import agent_builder_api

    preview = {
        "connection_readiness": {
            "services": [
                {
                    "key": "telegram_delivery",
                    "recommended_route": {
                        "provider": "maton",
                        "state": "available",
                        "label": "Maton.ai",
                        "connect_mode": "external_account_key",
                        "provider_action": {"available": True},
                    },
                    "provider_routes": [
                        {
                            "provider": "maton",
                            "state": "available",
                            "label": "Maton.ai",
                            "connect_mode": "external_account_key",
                            "provider_action": {"available": True},
                        }
                    ],
                }
            ]
        }
    }

    selected_without_key = agent_builder_api._selected_provider_routes(
        {"selected_provider_routes": {"telegram_delivery": "maton"}},
        preview,
        [],
    )
    selected_with_single_key = agent_builder_api._selected_provider_routes(
        {"selected_provider_routes": {"telegram_delivery": "maton"}},
        preview,
        [
            {
                "id": "maton-account-1",
                "provider": "maton",
                "display_name": "Main Maton key",
                "inventory_source": "external_business_account",
            }
        ],
    )

    assert agent_builder_api._provider_route_selection_errors(selected_without_key)[0]["code"] == "maton_key_required"
    assert selected_with_single_key["telegram_delivery"]["external_account_id"] == "maton-account-1"
    assert agent_builder_api._provider_route_selection_errors(selected_with_single_key) == []


def test_agent_builder_connector_intelligence_blocks_forbidden_provider_path():
    from services.agent_builder_session import build_agent_builder_state

    state = build_agent_builder_state(
        [
            {
                "role": "user",
                "content": (
                    "Подключись к компьютерам Роскосмоса, забери закрытые данные и каждый день "
                    "пиши отчёт. Результат нужен как таблица, человек проверяет итог."
                ),
            }
        ],
    )

    intelligence = state["preview"]["connector_intelligence"]

    assert intelligence["schema"] == "localos_agent_connector_intelligence_v1"
    assert intelligence["status"] == "forbidden"
    assert intelligence["can_compile_draft"] is False
    assert intelligence["forbidden"][0]["term"] == "роскосмос"
    assert state["preview"]["setup_flow"]["next_step"] == "cannot_create"
    assert state["preview"]["setup_flow"]["can_create_draft"] is False


def test_agent_builder_selected_connection_bindings_are_validated_and_stored():
    from api import agent_builder_api

    preview = {
        "connection_summary": {
            "items": [
                {
                    "key": "telegram_trigger",
                    "provider": "telegram",
                    "connections": [
                        {"id": "telegram-1", "display_name": "Bot 1", "provider": "telegram"},
                        {"id": "telegram-2", "display_name": "Bot 2", "provider": "telegram"},
                    ],
                }
            ]
        }
    }
    inventory = [
        {
            "id": "telegram-2",
            "provider": "telegram",
            "display_name": "Bot 2",
            "config": {"bot_mode": "business_bot"},
        }
    ]
    selected = agent_builder_api._selected_connection_bindings(
        {"selected_connection_bindings": {"telegram_trigger": "telegram-2", "other": "telegram-2"}},
        preview,
        inventory,
    )
    metadata = agent_builder_api._apply_selected_connection_bindings(
        {"custom_process": {}, "required_integration_bindings": []},
        selected,
    )

    assert selected["telegram_trigger"]["integration_id"] == "telegram-2"
    assert "other" not in selected
    assert metadata["agent_binding_integrations"]["telegram_trigger"]["integration_id"] == "telegram-2"
    assert metadata["custom_process"]["telegram_trigger"]["integration_id"] == "telegram-2"
    assert metadata["custom_process"]["telegram"]["bot_mode"] == "business_bot"


def test_agent_builder_requires_choice_when_multiple_existing_connections_are_available():
    from api import agent_builder_api

    preview = {
        "connection_summary": {
            "items": [
                {
                    "key": "telegram_trigger",
                    "provider": "telegram",
                    "title": "Telegram trigger",
                    "action": "choose_existing",
                    "connections": [
                        {"id": "telegram-1", "display_name": "Bot 1", "provider": "telegram"},
                        {"id": "telegram-2", "display_name": "Bot 2", "provider": "telegram"},
                    ],
                }
            ]
        }
    }

    missing = agent_builder_api._missing_required_connection_choices(preview, {})
    selected_missing = agent_builder_api._missing_required_connection_choices(
        preview,
        {"telegram_trigger": {"integration_id": "telegram-2", "provider": "telegram"}},
    )

    assert missing[0]["key"] == "telegram_trigger"
    assert missing[0]["connection_count"] == 2
    assert selected_missing == []


def test_agent_builder_auto_selects_single_existing_connection():
    from api import agent_builder_api

    preview = {
        "connection_summary": {
            "items": [
                {
                    "key": "telegram_trigger",
                    "provider": "telegram",
                    "action": "choose_existing",
                    "connections": [
                        {"id": "telegram-1", "display_name": "Bot 1", "provider": "telegram"},
                    ],
                },
                {
                    "key": "google_sheets_read",
                    "provider": "google_sheets",
                    "action": "choose_existing",
                    "connections": [
                        {"id": "sheet-1", "display_name": "Orders", "provider": "google_sheets"},
                        {"id": "sheet-2", "display_name": "Archive", "provider": "google_sheets"},
                    ],
                },
            ]
        }
    }
    inventory = [
        {
            "id": "telegram-1",
            "provider": "telegram",
            "display_name": "Bot 1",
            "config": {"bot_mode": "business_bot"},
        },
        {
            "id": "sheet-1",
            "provider": "google_sheets",
            "display_name": "Orders",
            "config": {"spreadsheet_id": "orders", "sheet_name": "Orders"},
        },
    ]

    selected = agent_builder_api._selected_connection_bindings(
        {"selected_connection_bindings": {}},
        preview,
        inventory,
    )

    assert selected["telegram_trigger"]["integration_id"] == "telegram-1"
    assert selected["telegram_trigger"]["selection_source"] == "auto_single_connection"
    assert "google_sheets_read" not in selected


def test_agent_builder_session_includes_openclaw_planner_context_envelope():
    from services.agent_builder_session import build_agent_builder_state

    state = build_agent_builder_state(
        [
            {
                "role": "user",
                "content": (
                    "Каждый день бери заказ из Google Sheets за вчера и готовь пост в Telegram. "
                    "Перед публикацией человек проверяет результат."
                ),
            }
        ],
        business_id="business-1",
        user_id="user-1",
    )

    context = state["preview"]["openclaw_planner_context"]

    assert context["schema"] == "localos_openclaw_planner_context_v1"
    assert context["business_scope"]["tenant_boundary"] == "single_business"
    assert context["business_scope"]["cross_business_access_allowed"] is False
    assert context["allowed_capabilities"] == ["google_sheets.read_rows", "communications.draft"]
    assert context["feasibility_status"] == "needs_connection"
    assert [item["provider"] for item in context["connection_state"]["missing_connections"]] == ["google_sheets", "telegram"]
    assert "credential_extraction" in context["forbidden_action_classes"]
    assert "external_publish" in context["approval_required_action_classes"]
    assert context["output_contract"]["must_not_execute_user_task"] is True
    assert context["output_contract"]["must_not_call_tools_directly"] is True
    assert state["compiler"]["openclaw_planner_context"]["schema"] == "localos_openclaw_planner_context_v1"


def test_agent_builder_session_passes_planner_context_to_ai_compiler(monkeypatch):
    from services import agent_blueprint_draft_builder
    from services.agent_builder_session import build_agent_builder_state

    captured = {}

    def fake_llm_intent(description, business_id="", user_id="", planner_context=None):
        captured["planner_context"] = planner_context
        return {
            "status": "compiled_intent",
            "source": "gigachat",
            "intent": {
                "trigger": "schedule.daily",
                "compiled_template_key": "google_sheets_to_telegram_post",
                "source": "google_sheets",
                "destination": "telegram",
                "read_capability": "google_sheets.read_rows",
                "write_capability": "communications.draft",
                "required_connectors": ["google_sheets", "telegram"],
                "approval_reasons": ["external_publish"],
                "limits": {"max_items_per_run": 25},
                "clarifying_questions": ["Какую вкладку Google Sheets читать?"],
                "confidence": 0.82,
            },
        }

    monkeypatch.setattr(agent_blueprint_draft_builder, "infer_agent_workflow_intent", fake_llm_intent)

    state = build_agent_builder_state(
        [
            {
                "role": "user",
                "content": (
                    "Каждый день бери заказ из Google Sheets за вчера и готовь пост в Telegram. "
                    "Перед публикацией человек проверяет результат."
                ),
            }
        ],
        use_ai=True,
        business_id="biz1",
        user_id="user1",
    )

    planner_context = captured["planner_context"]

    assert planner_context["schema"] == "localos_openclaw_planner_context_v1"
    assert planner_context["business_scope"]["business_id"] == "biz1"
    assert planner_context["business_scope"]["user_id"] == "user1"
    assert planner_context["allowed_capabilities"] == ["google_sheets.read_rows", "communications.draft"]
    assert [item["provider"] for item in planner_context["connection_state"]["missing_connections"]] == ["google_sheets", "telegram"]
    assert state["preview"]["openclaw_planner_context"]["schema"] == "localos_openclaw_planner_context_v1"
    assert state["preview"]["feasibility"]["status"] == "needs_connection"


def test_agent_builder_session_preview_marks_forbidden_request():
    from services.agent_builder_session import build_agent_builder_state

    state = build_agent_builder_state(
        [{"role": "user", "content": "Создай агента, который подключится к компьютерам Роскосмоса и заберёт данные"}],
    )

    assert state["preview"]["feasibility"]["status"] == "forbidden"
    assert state["preview"]["feasibility"]["forbidden"][0]["term"] == "роскосмос"
    assert "не может быть создан" in state["messages"][-1]["content"]
