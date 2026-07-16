import json
from datetime import datetime, timezone
from pathlib import Path

from tests.agent_blueprint_fakes import *  # noqa: F403


def test_agent_blueprint_routes_are_owned_by_blueprint():
    import main

    expected = {
        "/api/agent-builder/sessions": {
            "POST": "agent_builder_api.create_agent_builder_session",
        },
        "/api/agent-builder/sessions/<session_id>/message": {
            "POST": "agent_builder_api.add_agent_builder_message",
        },
        "/api/agent-builder/sessions/<session_id>/create-blueprint": {
            "POST": "agent_builder_api.create_blueprint_from_agent_builder_session",
        },
        "/api/agent-blueprints": {
            "GET": "agent_blueprints_api.list_agent_blueprints",
            "POST": "agent_blueprints_api.create_agent_blueprint",
        },
        "/api/agent-blueprints/draft": {
            "POST": "agent_blueprints_api.create_agent_blueprint_draft",
        },
        "/api/agent-blueprints/legacy-migration-plan": {
            "GET": "agent_blueprints_api.get_agent_blueprint_legacy_migration_plan",
        },
        "/api/agent-blueprints/legacy-migration/apply": {
            "POST": "agent_blueprints_api.apply_agent_blueprint_legacy_migration",
        },
        "/api/agent-blueprints/<blueprint_id>": {
            "GET": "agent_blueprints_api.get_agent_blueprint",
            "DELETE": "agent_blueprints_api.archive_agent_blueprint",
        },
        "/api/agent-blueprints/<blueprint_id>/versions": {
            "POST": "agent_blueprints_api.create_agent_blueprint_version",
        },
        "/api/agent-blueprints/<blueprint_id>/versions/<version_id>/diff": {
            "GET": "agent_blueprints_api.get_agent_blueprint_version_diff",
        },
        "/api/agent-blueprints/<blueprint_id>/versions/<version_id>/activate": {
            "POST": "agent_blueprints_api.activate_agent_blueprint_version",
        },
        "/api/agent-blueprints/<blueprint_id>/versions/<version_id>/rollback": {
            "POST": "agent_blueprints_api.rollback_agent_blueprint_version",
        },
        "/api/agent-blueprints/<blueprint_id>/setup": {
            "POST": "agent_blueprints_api.setup_agent_blueprint",
        },
        "/api/agent-blueprints/<blueprint_id>/integrations": {
            "GET": "agent_blueprints_api.list_agent_blueprint_integrations",
            "POST": "agent_blueprints_api.save_agent_blueprint_integration",
        },
        "/api/agent-blueprints/<blueprint_id>/custom-process": {
            "POST": "agent_blueprints_api.save_agent_blueprint_custom_process",
        },
        "/api/agent-blueprints/<blueprint_id>/custom-process/preview": {
            "POST": "agent_blueprints_api.preview_agent_blueprint_custom_process",
        },
        "/api/agent-blueprints/<blueprint_id>/sources": {
            "POST": "agent_blueprints_api.add_agent_blueprint_source",
        },
        "/api/agent-blueprints/<blueprint_id>/sources/catalog": {
            "GET": "agent_blueprints_api.list_agent_blueprint_source_catalog",
        },
        "/api/agent-blueprints/<blueprint_id>/sources/upload": {
            "POST": "agent_blueprints_api.upload_agent_blueprint_source",
        },
        "/api/agent-blueprints/<blueprint_id>/review": {
            "GET": "agent_blueprints_api.review_agent_blueprint",
        },
        "/api/agent-blueprints/<blueprint_id>/preflight": {
            "POST": "agent_blueprints_api.preflight_agent_blueprint_run",
        },
        "/api/agent-blueprints/<blueprint_id>/runs": {
            "POST": "agent_blueprints_api.start_agent_blueprint_run",
        },
        "/api/agent-runs/<run_id>": {
            "GET": "agent_blueprints_api.get_agent_run",
        },
        "/api/agent-runs/<run_id>/support-export": {
            "GET": "agent_blueprints_api.get_agent_run_support_export",
        },
        "/api/agent-runs/<run_id>/finance-requests/apply": {
            "POST": "agent_blueprints_api.apply_agent_run_finance_requests",
        },
        "/api/agent-runs/<run_id>/feedback": {
            "POST": "agent_blueprints_api.create_agent_run_feedback",
        },
        "/api/agent-runs/<run_id>/approvals/<approval_id>/approve": {
            "POST": "agent_blueprints_api.approve_agent_run",
        },
        "/api/agent-runs/<run_id>/approvals/<approval_id>/reject": {
            "POST": "agent_blueprints_api.reject_agent_run",
        },
    }

    actual = {}
    for rule in main.app.url_map.iter_rules():
        methods = rule.methods - {"HEAD", "OPTIONS"}
        actual.setdefault(rule.rule, {})
        for method in methods:
            actual[rule.rule][method] = rule.endpoint

    for route, methods in expected.items():
        for method, endpoint in methods.items():
            assert actual.get(route, {}).get(method) == endpoint


def test_agent_blueprint_migration_creates_expected_tables():
    migration = Path("alembic_migrations/versions/20260523_add_agent_blueprint_layer.py").read_text(encoding="utf-8")
    for table_name in [
        "agent_blueprints",
        "agent_blueprint_versions",
        "agent_runs",
        "agent_run_steps",
        "agent_artifacts",
        "agent_approvals",
    ]:
        assert f"CREATE TABLE IF NOT EXISTS {table_name}" in migration
    assert "JSONB" in migration
    assert "20260523_001" in migration
    assert "20260521_001" in migration


def test_agent_builder_session_migration_creates_expected_table():
    migration = Path("alembic_migrations/versions/20260525_add_agent_builder_sessions.py").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS agent_builder_sessions" in migration
    assert "preview_json JSONB" in migration
    assert "missing_questions_json JSONB" in migration
    assert "20260525_001" in migration
    assert "20260523_001" in migration


def test_agent_domain_request_migration_creates_expected_tables():
    migration = Path("alembic_migrations/versions/20260609_add_agent_domain_request_tables.py").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS agent_communication_requests" in migration
    assert "CREATE TABLE IF NOT EXISTS agent_service_optimization_requests" in migration
    assert "recipients_json JSONB" in migration
    assert "suggestions_json JSONB" in migration
    assert "delivery_state TEXT NOT NULL DEFAULT 'not_dispatched'" in migration
    assert "apply_state TEXT NOT NULL DEFAULT 'not_applied'" in migration
    assert "20260609_001" in migration
    assert "20260525_001" in migration


def test_custom_agent_integration_migration_creates_expected_tables():
    migration = Path("alembic_migrations/versions/20260609_add_custom_agent_integration_tables.py").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS agent_integrations" in migration
    assert "CREATE TABLE IF NOT EXISTS agent_trigger_events" in migration
    assert "CREATE TABLE IF NOT EXISTS agent_sheet_operation_requests" in migration
    assert "provider_write_performed BOOLEAN NOT NULL DEFAULT FALSE" in migration
    assert "apply_state TEXT NOT NULL DEFAULT 'not_applied'" in migration
    assert "20260609_002" in migration
    assert "20260609_001" in migration


def test_agent_service_optimization_diff_migration_adds_visual_diff_column():
    migration = Path("alembic_migrations/versions/20260609_add_agent_service_optimization_diff.py").read_text(encoding="utf-8")

    assert "ADD COLUMN IF NOT EXISTS diff_json JSONB" in migration
    assert "20260609_003" in migration
    assert "20260609_002" in migration


def test_agent_communication_delivery_journal_migration_creates_handoff_table():
    migration = Path("alembic_migrations/versions/20260609_add_agent_communication_delivery_journal.py").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS agent_communication_delivery_journal" in migration
    assert "router_handoff_json JSONB" in migration
    assert "provider_write_performed BOOLEAN NOT NULL DEFAULT FALSE" in migration
    assert "20260609_004" in migration
    assert "20260609_003" in migration


def test_agent_review_publish_request_migration_creates_expected_table():
    migration = Path("alembic_migrations/versions/20260609_add_agent_review_publish_requests.py").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS agent_review_publish_requests" in migration
    assert "provider_request_json JSONB" in migration
    assert "audit_json JSONB" in migration
    assert "provider_write_performed BOOLEAN NOT NULL DEFAULT FALSE" in migration
    assert "publish_state TEXT NOT NULL" in migration
    assert "20260609_005" in migration
    assert "20260609_004" in migration


def test_default_supervised_outreach_template_has_approval_gates():
    from services.agent_blueprint_runner import default_supervised_outreach_version_payload

    payload = default_supervised_outreach_version_payload()
    steps = payload["steps"]

    assert payload["capability_allowlist"] == ["outreach.send_batch"]
    assert [step["key"] for step in steps] == [
        "source_leads",
        "shortlist",
        "approve_shortlist",
        "draft_messages",
        "approve_drafts",
        "send_limited_batch",
        "record_outcomes",
    ]
    assert steps[2]["type"] == "approval"
    assert steps[4]["type"] == "approval"
    assert steps[5]["type"] == "capability"
    assert steps[5]["requires_approval"] is True
    assert steps[5]["required_approval_type"] == "drafts"


def test_agent_blueprint_orchestrator_exposes_stage4_capability_map():
    from services.agent_blueprint_orchestrator import build_agent_blueprint_orchestrator
    from services.agent_capability_handlers import build_capability_catalog
    from services.agent_provider_registry import integration_execution_boundary

    orchestrator = build_agent_blueprint_orchestrator()
    expected = {
        "outreach.send_batch",
        "reviews.reply.draft",
        "reviews.reply.publish_request",
        "services.optimize",
        "news.generate",
        "appointments.read",
        "appointments.create_request",
        "communications.draft",
        "communications.send_reminder",
        "communications.send_offer",
        "support.export",
        "sheets.append_row_request",
        "google_sheets.read_rows",
        "finance.transaction.create",
        "partnership.audit_card",
        "partnership.match_services",
        "partnership.draft_offer",
        "billing.reserve",
        "billing.settle",
    }

    for capability in expected:
        assert capability in orchestrator.handlers

    assert "reviews.reply" in orchestrator.handlers
    assert "appointments.create" in orchestrator.handlers
    assert "communications.send" in orchestrator.handlers
    assert "google_sheets.append_row" in orchestrator.handlers
    assert "finance.manual_entry" in orchestrator.handlers
    assert "partners.match_services" in orchestrator.handlers
    assert "partners.draft_first_offer" in orchestrator.handlers
    catalog = build_capability_catalog()
    assert expected.issubset(set(catalog["capabilities"]))
    assert catalog["capabilities"]["reviews.reply"]["alias_for"] == "reviews.reply.draft"
    assert catalog["capabilities"]["google_sheets.append_row"]["alias_for"] == "sheets.append_row_request"
    assert catalog["capabilities"]["finance.manual_entry"]["alias_for"] == "finance.transaction.create"
    assert catalog["capabilities"]["partners.match_services"]["alias_for"] == "partnership.match_services"
    assert catalog["capabilities"]["partners.draft_first_offer"]["alias_for"] == "partnership.draft_offer"
    assert catalog["provider_registry"]["maton"]["status"] == "available"
    assert catalog["provider_registry"]["openclaw"]["status"] == "available"
    assert catalog["provider_registry"]["composio"]["status"] == "planned"
    reminder_providers = {
        item["provider"]
        for item in catalog["capabilities"]["communications.send_reminder"]["provider_candidates"]
    }
    assert {"maton", "openclaw", "native_localos", "composio", "manual"}.issubset(reminder_providers)
    sheet_read_providers = {
        item["provider"]
        for item in catalog["capabilities"]["sheets.append_row_request"]["provider_candidates"]
    }
    assert {"native_localos", "composio", "manual"}.issubset(sheet_read_providers)
    partnership_match_providers = {
        item["provider"]
        for item in catalog["capabilities"]["partnership.match_services"]["provider_candidates"]
    }
    assert {"native_localos", "openclaw", "manual"}.issubset(partnership_match_providers)
    assert integration_execution_boundary("google_sheets")["executor"] == "agent_sheet_provider_executor_v1"
    assert integration_execution_boundary("maton")["executor"] == "channel_router"
    assert integration_execution_boundary("localos_finance")["executor"] == "localos_finance_request_executor"
    assert integration_execution_boundary("composio")["external_write"] == "planned_provider_write"
    from services.agent_provider_registry import connector_provider_routes

    reminder_routes = connector_provider_routes("telegram", "communications.send_reminder")
    maton_route = next(item for item in reminder_routes if item["provider"] == "maton")
    openclaw_route = next(item for item in reminder_routes if item["provider"] == "openclaw")
    composio_route = next(item for item in reminder_routes if item["provider"] == "composio")
    assert maton_route["connect_mode"] == "external_account_key"
    assert maton_route["primary_cta"] == "Выбрать Maton key"
    assert maton_route["provider_action"]["kind"] == "select_external_account_key"
    assert maton_route["provider_action"]["ui_target"] == "external_business_accounts"
    assert openclaw_route["connect_mode"] == "openclaw_policy_boundary"
    assert openclaw_route["primary_cta"] == "Использовать OpenClaw boundary"
    assert openclaw_route["provider_action"]["kind"] == "use_openclaw_boundary"
    assert openclaw_route["provider_action"]["ui_target"] == "openclaw_policy_boundary"
    assert composio_route["connect_mode"] == "planned_oauth_connector"
    assert composio_route["primary_cta"] == "Будет доступно позже"
    assert composio_route["provider_action"]["kind"] == "planned_oauth_connector"
    assert composio_route["provider_action"]["available"] is False


def test_custom_process_preview_input_uses_bound_integrations_and_safe_telegram_payload():
    from api import agent_blueprints_api

    blueprint = {
        "metadata_json": {
            "custom_process": {
                "google_sheets": {
                    "integration_id": "sheet-integration-1",
                    "spreadsheet_id": "spreadsheet-1",
                    "sheet_name": "Leads",
                }
            }
        }
    }

    preview = agent_blueprints_api._build_custom_process_preview_input(
        blueprint,
        {
            "message_text": "Новая заявка: Анна",
            "telegram_username": "anna",
        },
    )

    assert preview["preview_mode"] is True
    assert preview["source_event"]["preview"] is True
    assert preview["source_event"]["source"] == "telegram_preview"
    assert preview["integration_id"] == "sheet-integration-1"
    assert preview["spreadsheet_id"] == "spreadsheet-1"
    assert preview["sheet_name"] == "Leads"
    assert preview["telegram"]["message_text"] == "Новая заявка: Анна"
    assert preview["telegram"]["username"] == "anna"


def test_agent_preview_run_input_is_safe_and_compiled_workflow_aware():
    from api import agent_blueprints_api
    from services.agent_blueprint_draft_builder import compile_agent_blueprint

    draft = compile_agent_blueprint(
        "Каждый день бери заказ из Google Sheets за вчера и готовь пост в Telegram. "
        "Результат нужен как черновик поста. Перед публикацией человек проверяет результат."
    )
    draft["metadata"]["custom_process"]["google_sheets"] = {
        "spreadsheet_id": "spreadsheet-1",
        "sheet_name": "Orders",
        "gid": "0",
    }
    draft["metadata"]["custom_process"]["telegram"] = {
        "telegram_target": "@riderra_updates",
        "target_type": "chat_or_channel",
    }
    draft["metadata"]["connector_action_handlers"] = {
        "google_sheets_read": {
            "schema": "localos_connector_action_handler_v1",
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
    }
    version_payload = draft["version_payload"]
    blueprint = {
        "id": "bp1",
        "business_id": "biz1",
        "category": draft["category"],
        "description": "Google Sheets to Telegram",
        "metadata_json": draft["metadata"],
    }
    version = {
        "id": "version-1",
        "goal": version_payload["goal"],
        "trigger": version_payload["trigger"],
        "inputs_schema_json": version_payload["inputs_schema"],
        "steps_json": version_payload["steps"],
        "capability_allowlist_json": version_payload["capability_allowlist"],
        "approval_policy_json": version_payload["approval_policy"],
        "output_schema_json": version_payload["output_schema"],
    }

    preview_input = agent_blueprints_api._build_agent_preview_run_input(
        blueprint,
        version,
        {"input": {"preview_mode": True}},
    )

    assert preview_input["schema"] == "localos_agent_preview_input_v1"
    assert preview_input["preview_mode"] is True
    assert preview_input["external_side_effects_allowed"] is False
    assert preview_input["approval_required_for_external_actions"] is True
    assert preview_input["source_event"]["preview"] is True
    assert preview_input["google_sheets"]["read_only"] is True
    assert preview_input["google_sheets"]["spreadsheet_id"] == "spreadsheet-1"
    assert preview_input["google_sheets"]["sheet_name"] == "Orders"
    assert preview_input["google_sheets"]["gid"] == "0"
    assert preview_input["google_sheets"]["sample_rows"][0]["route"] == "Los Angeles airport → Santa Barbara"
    assert preview_input["telegram"]["draft_only"] is True
    assert preview_input["telegram"]["external_publish_performed"] is False
    assert preview_input["telegram"]["telegram_target"] == "@riderra_updates"
    assert [item["provider"] for item in preview_input["provider_bindings"]] == ["google_sheets", "telegram"]
    assert preview_input["policy_envelope"]["execution_boundary"] == "openclaw_action_orchestrator"
    assert preview_input["policy_envelope"]["external_side_effects_allowed_in_preview"] is False
    assert preview_input["connector_action_handlers"][0]["handler"] == "openclaw_policy_boundary"
    assert preview_input["openclaw_preview_routes"][0]["binding_key"] == "google_sheets_read"
    assert preview_input["openclaw_preview_routes"][0]["external_side_effects_allowed_in_preview"] is False
    assert preview_input["openclaw_action_plan"][0]["provider_action_ref"] == "openclaw.google_sheets.read_rows"
    assert preview_input["openclaw_action_plan"][0]["provider_policy"] == "localos_envelope"


def test_openclaw_and_capability_routes_are_registered():
    import main

    actual = {}
    for rule in main.app.url_map.iter_rules():
        methods = rule.methods - {"HEAD", "OPTIONS"}
        actual.setdefault(rule.rule, set()).update(methods)

    expected = {
        "/api/capabilities/execute": "POST",
        "/api/capabilities/catalog": "GET",
        "/api/capabilities/actions/<action_id>": "GET",
        "/api/capabilities/actions/<action_id>/decision": "POST",
        "/api/capabilities/actions/<action_id>/billing": "GET",
        "/api/capabilities/health": "GET",
        "/api/capabilities/support-export": "GET",
        "/api/openclaw/capabilities/execute": "POST",
        "/api/openclaw/capabilities/catalog": "GET",
        "/api/openclaw/capabilities/actions/<action_id>": "GET",
        "/api/openclaw/capabilities/actions/<action_id>/decision": "POST",
        "/api/openclaw/capabilities/health": "GET",
        "/api/openclaw/callbacks/outbox": "GET",
        "/api/openclaw/audit-timeline": "GET",
    }

    for route, method in expected.items():
        assert method in actual.get(route, set())


def test_legacy_ai_agent_migration_plan_marks_runtime_truth_and_deprecations():
    from services.agent_legacy_migration import (
        LEGACY_WORKFLOW_STATUS,
        build_business_ai_settings_deprecation_plan,
        build_legacy_run_preview_bridge,
    )

    settings_plan = build_business_ai_settings_deprecation_plan(
        {
            "ai_agent_enabled": True,
            "ai_agent_tone": "friendly",
            "ai_agent_restrictions": "no discounts",
            "ai_agents_config": "{}",
            "ai_agent_id": "voice-1",
        }
    )
    bridge = build_legacy_run_preview_bridge({"id": "voice-1"}, "biz-1")

    assert LEGACY_WORKFLOW_STATUS == "deprecated_not_runtime_truth"
    assert settings_plan["fields"]["ai_agent_enabled"]["status"] == "deprecated_migration_source"
    assert settings_plan["fields"]["ai_agent_id"]["target"] == "agent_blueprint_versions.persona_agent_id"
    assert bridge["status"] == "moved_to_shared_run_preview_contract"
    assert bridge["preview_contract"]["target_runtime"] == "agent_blueprints"
    assert bridge["preview_contract"]["external_dispatch_performed"] is False
