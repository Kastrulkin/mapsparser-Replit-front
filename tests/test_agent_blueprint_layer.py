import json
from pathlib import Path


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
        "/api/agent-blueprints/<blueprint_id>": {
            "GET": "agent_blueprints_api.get_agent_blueprint",
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
        "/api/agent-blueprints/<blueprint_id>/runs": {
            "POST": "agent_blueprints_api.start_agent_blueprint_run",
        },
        "/api/agent-runs/<run_id>": {
            "GET": "agent_blueprints_api.get_agent_run",
        },
        "/api/agent-runs/<run_id>/support-export": {
            "GET": "agent_blueprints_api.get_agent_run_support_export",
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
        "billing.reserve",
        "billing.settle",
    }

    for capability in expected:
        assert capability in orchestrator.handlers

    assert "reviews.reply" in orchestrator.handlers
    assert "appointments.create" in orchestrator.handlers
    assert "communications.send" in orchestrator.handlers
    catalog = build_capability_catalog()
    assert expected.issubset(set(catalog["capabilities"]))
    assert catalog["capabilities"]["reviews.reply"]["alias_for"] == "reviews.reply.draft"


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


def test_communication_agent_showcase_has_five_safe_mvp_blueprints():
    from services.agent_blueprint_draft_builder import build_communication_agent_showcase_blueprints

    drafts = build_communication_agent_showcase_blueprints()
    expected = {
        "appointment_reminder": ("appointment.reminder.before", "communications.send_reminder", "approved_batch_only"),
        "post_visit_followup": ("visit.completed.after", "communications.send_reminder", "approved_batch_only"),
        "inactive_client_winback": ("client.inactive.since", "communications.send_offer", "approved_batch_only"),
        "package_offer_after_service": ("service.completed.relevant", "communications.send_offer", "approved_batch_only"),
        "inbound_request_reply_draft": ("inbound.message.received", "communications.draft", "draft_only"),
    }

    assert len(drafts) == 5
    by_key = {draft["metadata"]["communication_template_key"]: draft for draft in drafts}
    assert set(by_key) == set(expected)

    for key, values in expected.items():
        trigger, capability, mode = values
        draft = by_key[key]
        payload = draft["version_payload"]
        steps = payload["steps"]

        assert draft["category"] == "communications"
        assert payload["trigger"] == trigger
        assert payload["send_capability"] == capability
        assert payload["mode"] == mode
        assert payload["audience_rules"]
        assert payload["consent_rules"]
        assert payload["message_template"]
        assert payload["persona"]
        assert payload["delivery_outcome_journal"]["external_dispatch_performed"] is False
        assert payload["limits"]["external_send_requires_approval"] is True
        assert payload["limits"]["autonomous_send_allowed"] is False
        assert payload["external_dispatch_performed"] is False
        assert "communications.draft" in payload["capability_allowlist"]
        if capability != "communications.draft":
            assert capability in payload["capability_allowlist"]
            send_step = [step for step in steps if step["key"] == "send_message"][0]
            assert send_step["type"] == "capability"
            assert send_step["requires_approval"] is True
            assert send_step["payload"]["external_dispatch_performed"] is False
        else:
            assert payload["capability_allowlist"] == ["appointments.read", "communications.draft"]
            send_step = [step for step in steps if step["key"] == "send_message"][0]
            assert send_step["type"] == "artifact"
            assert send_step["payload"]["delivery_state"] == "not_dispatched"


def test_communication_agent_compiler_selects_mvp_templates_from_text():
    from services.agent_blueprint_draft_builder import compile_agent_blueprint

    examples = [
        ("Сделай сообщение после визита", "post_visit_followup"),
        ("Вернуть клиента, который давно не был", "inactive_client_winback"),
        ("Пакетное предложение после релевантной услуги", "package_offer_after_service"),
        ("Черновик ответа на входящий запрос", "inbound_request_reply_draft"),
    ]

    for prompt, expected_key in examples:
        draft = compile_agent_blueprint(prompt)
        assert draft["category"] == "communications"
        assert draft["metadata"]["communication_template_key"] == expected_key


def test_agent_product_view_uses_aiagent_as_voice_persona():
    from services.agent_product_layer import (
        attach_persona_to_version,
        attach_product_agent_to_blueprint,
        parse_persona_row,
    )

    persona = parse_persona_row(
        {
            "id": "voice-1",
            "name": "Администратор Анна",
            "type": "communication",
            "description": "Голос администратора",
            "personality": "спокойная и внимательная",
            "identity": "администратор салона",
            "speech_style": "коротко и дружелюбно",
            "restrictions_json": "{\"no_promises\": true}",
            "variables_json": "{\"signature\": \"Анна\"}",
            "is_active": 1,
        }
    )
    personas = {"voice-1": persona}
    version = attach_persona_to_version(
        {
            "id": "version-1",
            "version_number": 2,
            "persona_agent_id": "voice-1",
        },
        personas,
    )
    blueprint = attach_product_agent_to_blueprint(
        {
            "id": "blueprint-1",
            "name": "Напоминания о записи",
            "category": "communications",
            "status": "draft",
            "metadata_json": "{\"compiler\": \"agent_compiler_v1\"}",
        },
        version,
        personas,
    )

    assert version["persona"]["source"] == "AIAgents"
    assert version["persona"]["role"] == "agent_voice"
    assert blueprint["product_agent"]["kind"] == "agent"
    assert blueprint["product_agent"]["source"] == "agent_blueprints"
    assert blueprint["product_agent"]["persona_agent_id"] == "voice-1"
    assert blueprint["product_agent"]["voice"]["name"] == "Администратор Анна"
    assert blueprint["product_agent"]["components"]["persona"]["role"] == "agent_voice"
    assert blueprint["product_agent"]["legacy"]["communication_agent_is_blueprint_category"] is True


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


def test_agent_datahub_catalog_includes_connected_text_and_file_sources():
    from services.agent_datahub import build_agent_datahub_catalog

    class EmptyCursor:
        def execute(self, query, params=None):
            return None

        def fetchall(self):
            return []

    catalog = build_agent_datahub_catalog(
        EmptyCursor(),
        "biz-1",
        [
            {
                "id": "source-text",
                "source_type": "text",
                "name": "Контекст договора",
                "content_text": "Оплата 15000 до 10 июня. Штраф 12%.",
                "extraction_state": "ready",
            },
            {
                "id": "source-file",
                "source_type": "file",
                "name": "contract.docx",
                "file_name": "contract.docx",
                "content_text": "DOCX text",
                "extraction_state": "ready",
                "extraction_method": "docx_xml",
            },
        ],
    )

    connected = [item for item in catalog if item.get("connected") is True and str(item.get("key", "")).startswith("agent_source:")]
    assert [item["title"] for item in connected[:2]] == ["Контекст договора", "contract.docx"]
    assert connected[0]["state"] == "ready"
    assert connected[1]["source_type"] == "file"
    assert "DOCX text" in connected[1]["preview"][0]


def test_agent_blueprint_api_guards_version_blueprint_mismatch():
    api_source = Path("src/api/agent_blueprints_api.py").read_text(encoding="utf-8")
    workspace_source = Path("src/services/agent_blueprint_workspace.py").read_text(encoding="utf-8")
    document_llm_source = Path("src/services/agent_document_llm.py").read_text(encoding="utf-8")
    email_llm_source = Path("src/services/agent_email_llm.py").read_text(encoding="utf-8")
    review_analysis_source = Path("src/services/agent_review_reply_analysis.py").read_text(encoding="utf-8")
    table_analysis_source = Path("src/services/agent_table_analysis.py").read_text(encoding="utf-8")
    builder_api_source = Path("src/api/agent_builder_api.py").read_text(encoding="utf-8")
    agents_page_source = Path("frontend/src/pages/dashboard/AgentBlueprintsPage.tsx").read_text(encoding="utf-8")

    assert "VERSION_BLUEPRINT_MISMATCH" in api_source
    assert "_load_blueprint_version_for_blueprint" in api_source
    assert "build_agent_blueprint_orchestrator" in api_source
    assert "run_status" in api_source
    assert "approval_queue" in api_source
    assert "last_run_status" in api_source
    assert "pending_approvals_count" in api_source
    assert "sources_count" in api_source
    assert "versions_count" in api_source
    assert "/api/agent-blueprints/draft" in api_source
    assert "build_agent_blueprint_draft" in api_source
    assert "_insert_version(cursor, blueprint_id, version_payload, user_data)" in api_source
    assert "/api/agent-blueprints/<blueprint_id>/setup" in api_source
    assert "/api/agent-blueprints/<blueprint_id>/sources" in api_source
    assert "/api/agent-blueprints/<blueprint_id>/sources/catalog" in api_source
    assert "/api/agent-blueprints/<blueprint_id>/sources/upload" in api_source
    assert "build_agent_datahub_catalog" in api_source
    assert "build_agent_source_from_upload" in api_source
    assert "/api/agent-runs/<run_id>/feedback" in api_source
    assert "/api/agent-runs/<run_id>/support-export" in api_source
    assert "build_run_support_export" in api_source
    assert "/api/agent-blueprints/<blueprint_id>/versions/<version_id>/diff" in api_source
    assert "/api/agent-blueprints/<blueprint_id>/versions/<version_id>/activate" in api_source
    assert "/api/agent-blueprints/<blueprint_id>/versions/<version_id>/rollback" in api_source
    assert "_resolve_active_version" in api_source
    assert "_remember_active_version" in api_source
    assert "build_agent_version_diff" in workspace_source
    assert "_review_journal" in workspace_source
    assert "journal" in workspace_source
    assert "analyze_document_sources_with_llm" in workspace_source
    assert "draft_email_with_llm" in workspace_source
    assert "draft_review_replies_with_llm" in workspace_source
    assert "analyze_table_with_llm" in workspace_source
    assert "analyze_text_with_gigachat" in document_llm_source
    assert "agent_email_draft" in email_llm_source
    assert "agent_review_replies" in review_analysis_source
    assert "agent_table_analysis" in table_analysis_source
    assert "external_dispatch_performed" in document_llm_source
    assert "external_dispatch_performed" in email_llm_source
    assert "external_dispatch_performed" in review_analysis_source
    assert "publish_state" in review_analysis_source
    assert "external_dispatch_performed" in table_analysis_source
    assert "provenance" in document_llm_source
    assert "provenance" in email_llm_source
    assert "provenance" in review_analysis_source
    assert "provenance" in table_analysis_source
    assert "/api/agent-builder/sessions" in builder_api_source
    assert "build_agent_builder_state" in builder_api_source
    assert "create_blueprint_from_agent_builder_session" in builder_api_source
    assert "GenericRunProgress" in agents_page_source
    assert "Мои агенты" in agents_page_source
    assert "getAgentListStatus" in agents_page_source
    assert "AgentSummaryPill" in agents_page_source
    assert "Последний запуск" in agents_page_source
    assert "Ожидающие approvals" in agents_page_source
    assert "Источники данных" in agents_page_source
    assert "Изменить логику" in agents_page_source
    assert "Голос и стиль" in agents_page_source
    assert "AgentVoiceStylePanel" in agents_page_source
    assert "AIAgents legacy wrapper" in agents_page_source
    assert "Путь {humanizeCategory(category).toLowerCase()}-агента" in agents_page_source
    assert "Технический журнал" in agents_page_source
    assert "AgentRunObservabilityPanel" in agents_page_source
    assert "Action ledger" in agents_page_source
    assert "Support export" in agents_page_source
    assert "agent_run_observability_v1" in Path("src/services/agent_blueprint_runner.py").read_text(encoding="utf-8")
    assert "Использовано в последнем запуске" in agents_page_source
    assert "used_sources" in workspace_source
    assert "resultFieldLabels" in agents_page_source


def test_generic_document_runner_uses_sources_and_stops_for_final_approval():
    from services.agent_blueprint_draft_builder import build_agent_blueprint_draft
    from services.agent_blueprint_runner import AgentBlueprintRunner

    cursor = FakeCursor()
    draft = build_agent_blueprint_draft("Обработай договор и найди риски")
    cursor.tables["agent_blueprints"]["bp1"] = {
        "id": "bp1",
        "business_id": "biz1",
        "name": "Document agent",
        "category": "documents",
        "metadata_json": {
            **draft["metadata"],
            "agent_setup": {
                "workflow_description": "Проверить договор",
                "extraction_rules": "Найти сроки, оплату и ответственность",
                "processing_rules": "Не придумывать факты",
                "output_format": "Список рисков",
                "approval_boundaries": ["final_output", "external_delivery"],
            },
            "agent_sources": [
                {
                    "id": "src1",
                    "source_type": "text",
                    "name": "Договор",
                    "content_text": "Оплата 10000 рублей. Ответственность за просрочку: штраф 10%.",
                    "content_length": 68,
                    "extraction_state": "ready",
                }
            ],
        },
    }
    cursor.tables["agent_blueprint_versions"]["ver1"] = {
        "id": "ver1",
        "blueprint_id": "bp1",
        "steps_json": draft["version_payload"]["steps"],
        "capability_allowlist_json": [],
    }

    result = AgentBlueprintRunner(cursor).start_run("ver1", {}, {"user_id": "user1"})

    assert result["success"] is True
    run = result["run"]
    assert run["status"] == "waiting_approval"
    assert [step["step_key"] for step in run["steps"]] == [
        "collect_inputs",
        "extract_context",
        "prepare_output",
        "approve_output",
    ]
    output = [item for item in run["artifacts"] if item["artifact_type"] == "agent_output_draft"][0]
    assert output["payload_json"]["external_dispatch_performed"] is False
    assert output["payload_json"]["result"]["title"] == "Разбор документа"
    assert output["payload_json"]["result"]["facts"]
    assert output["payload_json"]["result"]["fields"]["Оплата"]
    assert output["payload_json"]["result"]["fields"]["Ответственность"]
    assert output["payload_json"]["dispatch_state"] == "not_dispatched"
    assert run["approvals"][0]["approval_type"] == "final_output"


def test_generic_email_runner_prepares_draft_and_never_dispatches():
    from services.agent_blueprint_draft_builder import build_agent_blueprint_draft
    from services.agent_blueprint_runner import AgentBlueprintRunner

    cursor = FakeCursor()
    draft = build_agent_blueprint_draft("Подготовь письмо клиенту по контексту", "email")
    cursor.tables["agent_blueprints"]["bp1"] = {
        "id": "bp1",
        "business_id": "biz1",
        "name": "Email agent",
        "category": "email",
        "metadata_json": {
            **draft["metadata"],
            "agent_setup": {
                "workflow_description": "Подготовить письмо клиенту о новой услуге",
                "extraction_rules": "Взять услугу, выгоду и ограничение по тону",
                "processing_rules": "Писать дружелюбно, не обещать скидку без подтверждения",
                "output_format": "subject, body, checklist, missing_info",
                "approval_boundaries": ["final_output", "external_delivery"],
            },
            "agent_sources": [
                {
                    "id": "src1",
                    "source_type": "text",
                    "name": "Контекст письма",
                    "content_text": "Адресат: Анна. Услуга: уход для волос. Цель: пригласить на консультацию.",
                    "content_length": 77,
                    "extraction_state": "ready",
                }
            ],
        },
    }
    cursor.tables["agent_blueprint_versions"]["ver1"] = {
        "id": "ver1",
        "blueprint_id": "bp1",
        "steps_json": draft["version_payload"]["steps"],
        "capability_allowlist_json": [],
    }

    result = AgentBlueprintRunner(cursor).start_run("ver1", {}, {"user_id": "user1"})

    assert result["success"] is True
    run = result["run"]
    assert run["status"] == "waiting_approval"
    assert not [step for step in run["steps"] if step["step_type"] == "capability"]
    output = [item for item in run["artifacts"] if item["artifact_type"] == "agent_output_draft"][0]
    payload = output["payload_json"]
    email_result = payload["result"]
    assert payload["category"] == "email"
    assert payload["external_dispatch_performed"] is False
    assert payload["dispatch_state"] == "not_dispatched"
    assert email_result["external_dispatch_performed"] is False
    assert email_result["delivery_state"] == "not_dispatched"
    assert email_result["subject"]
    assert email_result["body"]
    assert email_result["checklist"]
    assert email_result["provenance"] == ["Контекст письма"]
    assert run["approvals"][0]["approval_type"] == "final_output"


def test_generic_table_runner_prepares_report_and_never_dispatches():
    from services.agent_blueprint_draft_builder import build_agent_blueprint_draft
    from services.agent_blueprint_runner import AgentBlueprintRunner

    cursor = FakeCursor()
    draft = build_agent_blueprint_draft("Проверь CSV и найди ошибки", "tables")
    cursor.tables["agent_blueprints"]["bp1"] = {
        "id": "bp1",
        "business_id": "biz1",
        "name": "Table agent",
        "category": "tables",
        "metadata_json": {
            **draft["metadata"],
            "agent_setup": {
                "workflow_description": "Проверить таблицу клиентов",
                "extraction_rules": "Найти пустые email, дубли и строки к проверке",
                "processing_rules": "Не изменять таблицу, только показать проблемы",
                "output_format": "summary, exceptions, rows_to_review, recommendations",
                "approval_boundaries": ["final_output", "external_delivery"],
            },
            "agent_sources": [
                {
                    "id": "src1",
                    "source_type": "text",
                    "name": "clients.csv",
                    "content_text": "name,email,phone\nАнна,anna@example.com,+1\nАнна,anna@example.com,+1\nБорис,,+2\n",
                    "content_length": 83,
                    "extraction_state": "ready",
                }
            ],
        },
    }
    cursor.tables["agent_blueprint_versions"]["ver1"] = {
        "id": "ver1",
        "blueprint_id": "bp1",
        "steps_json": draft["version_payload"]["steps"],
        "capability_allowlist_json": [],
    }

    result = AgentBlueprintRunner(cursor).start_run("ver1", {}, {"user_id": "user1"})

    assert result["success"] is True
    run = result["run"]
    assert run["status"] == "waiting_approval"
    assert not [step for step in run["steps"] if step["step_type"] == "capability"]
    output = [item for item in run["artifacts"] if item["artifact_type"] == "agent_output_draft"][0]
    payload = output["payload_json"]
    table_result = payload["result"]
    assert payload["category"] == "tables"
    assert payload["external_dispatch_performed"] is False
    assert payload["dispatch_state"] == "not_dispatched"
    assert table_result["external_dispatch_performed"] is False
    assert table_result["delivery_state"] == "not_dispatched"
    assert table_result["summary"]
    assert table_result["exceptions"]
    assert table_result["rows_to_review"]
    assert table_result["recommendations"]
    assert table_result["provenance"] == ["clients.csv"]
    assert run["approvals"][0]["approval_type"] == "final_output"


def test_generic_reviews_runner_prepares_reply_drafts_and_never_publishes():
    from services.agent_blueprint_draft_builder import build_agent_blueprint_draft
    from services.agent_blueprint_runner import AgentBlueprintRunner

    cursor = FakeCursor()
    draft = build_agent_blueprint_draft("Подготовь ответы на отзывы", "reviews")
    reviews_text = (
        "author_name,rating,text\n"
        "Анна,5,Очень понравился сервис\n"
        "Иван,2,Долго ждал и администратор был груб\n"
    )
    cursor.tables["agent_blueprints"]["bp1"] = {
        "id": "bp1",
        "business_id": "biz1",
        "name": "Reviews agent",
        "category": "reviews",
        "metadata_json": {
            **draft["metadata"],
            "agent_setup": {
                "workflow_description": "Подготовить ответы на отзывы",
                "extraction_rules": "Определить тон, проблему клиента и безопасный ответ",
                "processing_rules": "Не обещать скидку, компенсацию или публикацию без подтверждения",
                "output_format": "reply_drafts, manual_review_reasons, checklist",
                "approval_boundaries": ["final_output", "external_delivery"],
            },
            "agent_sources": [
                {
                    "id": "src1",
                    "source_type": "text",
                    "name": "Отзывы",
                    "content_text": reviews_text,
                    "content_length": len(reviews_text),
                    "extraction_state": "ready",
                }
            ],
        },
    }
    cursor.tables["agent_blueprint_versions"]["ver1"] = {
        "id": "ver1",
        "blueprint_id": "bp1",
        "steps_json": draft["version_payload"]["steps"],
        "capability_allowlist_json": [],
    }

    result = AgentBlueprintRunner(cursor).start_run("ver1", {}, {"user_id": "user1"})

    assert result["success"] is True
    run = result["run"]
    assert run["status"] == "waiting_approval"
    assert not [step for step in run["steps"] if step["step_type"] == "capability"]
    output = [item for item in run["artifacts"] if item["artifact_type"] == "agent_output_draft"][0]
    payload = output["payload_json"]
    review_result = payload["result"]
    assert payload["category"] == "reviews"
    assert payload["external_dispatch_performed"] is False
    assert payload["dispatch_state"] == "not_dispatched"
    assert review_result["external_dispatch_performed"] is False
    assert review_result["publish_state"] == "not_published"
    assert review_result["delivery_state"] == "not_dispatched"
    assert review_result["reply_drafts"]
    assert review_result["manual_review_reasons"]
    assert review_result["checklist"]
    assert review_result["provenance"] == ["Отзывы"]
    assert run["approvals"][0]["approval_type"] == "final_output"


def test_agent_source_ingestion_extracts_text_pdf_docx_xlsx_and_rejects_unsafe_files():
    import io
    import zipfile

    from openpyxl import Workbook

    from services.agent_source_ingestion import build_agent_source_from_upload

    def build_test_pdf_bytes(text):
        stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("utf-8")
        objects = [
            b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
            b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
            (
                b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n"
            ),
            b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
            b"5 0 obj << /Length "
            + str(len(stream)).encode("ascii")
            + b" >> stream\n"
            + stream
            + b"\nendstream endobj\n",
        ]
        output = bytearray(b"%PDF-1.4\n")
        offsets = [0]
        for item in objects:
            offsets.append(len(output))
            output.extend(item)
        xref_offset = len(output)
        output.extend(b"xref\n0 6\n0000000000 65535 f \n")
        for offset in offsets[1:]:
            output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
        output.extend(b"trailer << /Root 1 0 R /Size 6 >>\n")
        output.extend(f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii"))
        return bytes(output)

    text_source, text_error = build_agent_source_from_upload(
        FakeUpload("contract.txt", "text/plain", "Оплата 10000. Ответственность: штраф.".encode("utf-8")),
        "Договор",
    )
    assert text_error == {}
    assert text_source["content_text"].startswith("Оплата 10000")
    assert text_source["extraction_state"] == "ready"

    pdf_bytes = build_test_pdf_bytes("Payment 15000. Penalty 12 percent.")
    pdf_source, pdf_error = build_agent_source_from_upload(
        FakeUpload("contract.pdf", "application/pdf", pdf_bytes),
    )
    assert pdf_error == {}
    assert "Payment 15000" in pdf_source["content_text"]
    assert pdf_source["extraction_method"] == "pypdf"

    docx_buffer = io.BytesIO()
    archive = zipfile.ZipFile(docx_buffer, "w")
    try:
        archive.writestr(
            "word/document.xml",
            (
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                "<w:body><w:p><w:r><w:t>Документ содержит срок и оплату.</w:t></w:r></w:p></w:body>"
                "</w:document>"
            ),
        )
    finally:
        archive.close()
    docx_source, docx_error = build_agent_source_from_upload(
        FakeUpload(
            "contract.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            docx_buffer.getvalue(),
        )
    )
    assert docx_error == {}
    assert "срок и оплату" in docx_source["content_text"]
    assert docx_source["extraction_method"] == "docx_xml"

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Риски"
    sheet.append(["Поле", "Значение"])
    sheet.append(["Штраф", "10%"])
    xlsx_buffer = io.BytesIO()
    workbook.save(xlsx_buffer)
    xlsx_source, xlsx_error = build_agent_source_from_upload(
        FakeUpload(
            "risks.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            xlsx_buffer.getvalue(),
        )
    )
    assert xlsx_error == {}
    assert "Штраф" in xlsx_source["content_text"]
    assert xlsx_source["extraction_method"] == "openpyxl"

    unsafe_source, unsafe_error = build_agent_source_from_upload(
        FakeUpload("payload.exe", "application/octet-stream", b"bad"),
    )
    assert unsafe_source == {}
    assert unsafe_error["code"] == "UNSUPPORTED_FILE_TYPE"
    assert "поддерживается" in unsafe_error["message"].lower()

    empty_source, empty_error = build_agent_source_from_upload(
        FakeUpload("empty.txt", "text/plain", b""),
    )
    assert empty_source == {}
    assert empty_error["code"] == "EMPTY_FILE"
    assert "пустой" in empty_error["message"].lower()


def test_agent_datahub_catalog_returns_available_internal_sources():
    from services.agent_datahub import build_agent_datahub_catalog

    cursor = FakeDatahubCursor()
    catalog = build_agent_datahub_catalog(
        cursor,
        "biz1",
        [{"source_type": "internal", "internal_source": "services"}],
    )

    by_key = {item["key"]: item for item in catalog}
    assert by_key["business_profile"]["available_count"] == 1
    assert by_key["services"]["available_count"] == 2
    assert by_key["services"]["connected"] is True
    assert by_key["reviews"]["preview"]
    assert by_key["prospectingleads"]["state"] == "empty"


def test_agent_document_llm_analysis_uses_generator_rules_and_provenance():
    from services.agent_document_llm import analyze_document_sources_with_llm

    captured = {}

    def fake_generator(prompt, *, business_id="", user_id=""):
        captured["prompt"] = prompt
        captured["business_id"] = business_id
        captured["user_id"] = user_id
        return json.dumps(
            {
                "title": "LLM contract analysis",
                "summary": ["Оплата 10000 рублей"],
                "risks": ["Штраф 10% за просрочку"],
                "facts": ["Срок 30 дней", "Оплата 10000 рублей"],
                "fields": {"Оплата": "10000 рублей", "Срок": "30 дней"},
                "next_questions": ["Кто подписывает договор?"],
                "rules_applied": ["Не придумывать факты"],
            },
            ensure_ascii=False,
        )

    result = analyze_document_sources_with_llm(
        {
            "workflow_description": "Проверить договор",
            "extraction_rules": "Суммы, сроки, штрафы",
            "processing_rules": "Не придумывать факты",
            "output_format": "Краткий отчёт",
        },
        [
            {
                "source_name": "contract.txt",
                "summary": "Оплата 10000 рублей. Срок 30 дней. Штраф 10%.",
                "raw": {"text": "Оплата 10000 рублей. Срок 30 дней. Штраф 10%."},
            }
        ],
        business_id="biz1",
        user_id="user1",
        generator=fake_generator,
    )

    assert result["llm_analysis_used"] is True
    assert result["analysis_source"] == "gigachat"
    assert result["external_dispatch_performed"] is False
    assert result["fields"]["Оплата"] == "10000 рублей"
    assert result["provenance"] == ["contract.txt"]
    assert captured["business_id"] == "biz1"
    assert captured["user_id"] == "user1"
    assert "Не придумывать факты" in captured["prompt"]
    assert "contract.txt" in captured["prompt"]


def test_agent_document_llm_analysis_falls_back_without_external_dispatch():
    from services.agent_document_llm import analyze_document_sources_with_llm

    def failing_generator(prompt, *, business_id="", user_id=""):
        raise RuntimeError("provider unavailable")

    result = analyze_document_sources_with_llm(
        {"processing_rules": "Показывать риски", "output_format": "Отчёт"},
        [{"source_name": "contract.txt", "summary": "Оплата 10000. Ответственность: штраф.", "raw": {}}],
        generator=failing_generator,
    )

    assert result["llm_analysis_used"] is False
    assert result["analysis_source"] == "deterministic_fallback"
    assert result["external_dispatch_performed"] is False
    assert result["provenance"] == ["contract.txt"]
    assert result["risks"]


def test_agent_email_llm_draft_uses_generator_rules_and_provenance():
    from services.agent_email_llm import draft_email_with_llm

    captured = {}

    def fake_generator(prompt, *, business_id="", user_id=""):
        captured["prompt"] = prompt
        captured["business_id"] = business_id
        captured["user_id"] = user_id
        return json.dumps(
            {
                "title": "Email draft",
                "subject": "Анна, приглашаем на консультацию",
                "body": "Здравствуйте, Анна! Приглашаем на консультацию по уходу для волос.",
                "checklist": ["Проверить имя", "Проверить оффер"],
                "assumptions": ["Контекст взят из источника"],
                "missing_info": ["Дата консультации"],
                "rules_applied": ["Не обещать скидку"],
            },
            ensure_ascii=False,
        )

    result = draft_email_with_llm(
        {
            "workflow_description": "Подготовить письмо клиенту",
            "extraction_rules": "Адресат, услуга, цель",
            "processing_rules": "Не обещать скидку",
            "output_format": "subject/body/checklist",
        },
        [
            {
                "source_name": "Контекст",
                "summary": "Адресат: Анна. Услуга: уход для волос.",
                "raw": {"text": "Адресат: Анна. Услуга: уход для волос. Цель: консультация."},
            }
        ],
        business_id="biz1",
        user_id="user1",
        generator=fake_generator,
    )

    assert result["llm_analysis_used"] is True
    assert result["analysis_source"] == "gigachat"
    assert result["external_dispatch_performed"] is False
    assert result["delivery_state"] == "not_dispatched"
    assert result["subject"] == "Анна, приглашаем на консультацию"
    assert result["checklist"]
    assert result["provenance"] == ["Контекст"]
    assert captured["business_id"] == "biz1"
    assert captured["user_id"] == "user1"
    assert "Не обещать скидку" in captured["prompt"]


def test_agent_email_llm_falls_back_without_external_dispatch():
    from services.agent_email_llm import draft_email_with_llm

    def failing_generator(prompt, *, business_id="", user_id=""):
        raise RuntimeError("provider unavailable")

    result = draft_email_with_llm(
        {"workflow_description": "Подготовить письмо", "processing_rules": "Дружелюбно"},
        [{"source_name": "Контекст", "summary": "Адресат: Анна. Услуга: консультация.", "raw": {}}],
        generator=failing_generator,
    )

    assert result["llm_analysis_used"] is False
    assert result["analysis_source"] == "deterministic_fallback"
    assert result["external_dispatch_performed"] is False
    assert result["delivery_state"] == "not_dispatched"
    assert result["subject"]
    assert result["body"]


def test_agent_table_analysis_uses_generator_rules_and_provenance():
    from services.agent_table_analysis import analyze_table_with_llm

    captured = {}

    def fake_generator(prompt, *, business_id="", user_id=""):
        captured["prompt"] = prompt
        captured["business_id"] = business_id
        captured["user_id"] = user_id
        return json.dumps(
            {
                "title": "Table report",
                "summary": ["Проверено 3 строки"],
                "exceptions": ["Строка 3: пустой email"],
                "rows_to_review": [
                    {"row": 3, "reason": "пустой email", "source_name": "clients.csv", "values": {"name": "Борис"}}
                ],
                "recommendations": ["Заполнить email"],
                "rules_applied": ["Не изменять таблицу"],
            },
            ensure_ascii=False,
        )

    result = analyze_table_with_llm(
        {
            "workflow_description": "Проверить клиентов",
            "extraction_rules": "Пустые email и дубли",
            "processing_rules": "Не изменять таблицу",
            "output_format": "exceptions report",
        },
        [
            {"source_name": "clients.csv", "summary": "name: Борис; email: ; phone: +2", "raw": {"name": "Борис", "email": "", "phone": "+2"}}
        ],
        business_id="biz1",
        user_id="user1",
        generator=fake_generator,
    )

    assert result["llm_analysis_used"] is True
    assert result["analysis_source"] == "gigachat"
    assert result["external_dispatch_performed"] is False
    assert result["delivery_state"] == "not_dispatched"
    assert result["exceptions"] == ["Строка 3: пустой email"]
    assert result["rows_to_review"][0]["row"] == 3
    assert result["provenance"] == ["clients.csv"]
    assert captured["business_id"] == "biz1"
    assert captured["user_id"] == "user1"
    assert "Не изменять таблицу" in captured["prompt"]


def test_agent_table_analysis_falls_back_without_external_dispatch():
    from services.agent_table_analysis import analyze_table_with_llm

    def failing_generator(prompt, *, business_id="", user_id=""):
        raise RuntimeError("provider unavailable")

    result = analyze_table_with_llm(
        {"workflow_description": "Проверить таблицу", "processing_rules": "Только отчёт"},
        [
            {"source_name": "clients.csv", "summary": "name: Анна; email: anna@example.com", "raw": {"name": "Анна", "email": "anna@example.com"}},
            {"source_name": "clients.csv", "summary": "name: Борис; email: ", "raw": {"name": "Борис", "email": ""}},
        ],
        generator=failing_generator,
    )

    assert result["llm_analysis_used"] is False
    assert result["analysis_source"] == "deterministic_fallback"
    assert result["external_dispatch_performed"] is False
    assert result["delivery_state"] == "not_dispatched"
    assert result["exceptions"]
    assert result["rows_to_review"]


def test_agent_review_reply_analysis_uses_generator_rules_and_provenance():
    from services.agent_review_reply_analysis import draft_review_replies_with_llm

    captured = {}

    def fake_generator(prompt, *, business_id="", user_id=""):
        captured["prompt"] = prompt
        captured["business_id"] = business_id
        captured["user_id"] = user_id
        return json.dumps(
            {
                "title": "Review replies",
                "summary": ["Подготовлено 2 черновика"],
                "reply_drafts": [
                    {
                        "review_id": "rev1",
                        "author_name": "Иван",
                        "rating": "2",
                        "sentiment": "negative",
                        "reply": "Иван, спасибо за обратную связь. Мы разберём ситуацию с ожиданием.",
                        "manual_review_reason": "Негативный отзыв требует проверки менеджером.",
                    }
                ],
                "manual_review_reasons": ["Негативный отзыв требует проверки менеджером."],
                "checklist": ["Проверить тон", "Не обещать компенсацию"],
                "rules_applied": ["Не обещать скидку"],
            },
            ensure_ascii=False,
        )

    result = draft_review_replies_with_llm(
        {
            "workflow_description": "Подготовить ответы на отзывы",
            "extraction_rules": "Тональность и причина недовольства",
            "processing_rules": "Не обещать скидку",
            "output_format": "reply_drafts/checklist",
        },
        [
            {
                "source_name": "Отзывы",
                "summary": "Иван поставил 2: долго ждал",
                "raw": {"id": "rev1", "author_name": "Иван", "rating": 2, "text": "Долго ждал"},
            }
        ],
        business_id="biz1",
        user_id="user1",
        generator=fake_generator,
    )

    assert result["llm_analysis_used"] is True
    assert result["analysis_source"] == "gigachat"
    assert result["external_dispatch_performed"] is False
    assert result["publish_state"] == "not_published"
    assert result["delivery_state"] == "not_dispatched"
    assert result["reply_drafts"][0]["reply"]
    assert result["manual_review_reasons"]
    assert result["provenance"] == ["Отзывы"]
    assert captured["business_id"] == "biz1"
    assert captured["user_id"] == "user1"
    assert "Не обещать скидку" in captured["prompt"]


def test_agent_review_reply_analysis_falls_back_without_publish():
    from services.agent_review_reply_analysis import draft_review_replies_with_llm

    def failing_generator(prompt, *, business_id="", user_id=""):
        raise RuntimeError("provider unavailable")

    result = draft_review_replies_with_llm(
        {"workflow_description": "Ответить на отзывы", "processing_rules": "Проверить негатив вручную"},
        [
            {
                "source_name": "Отзывы",
                "summary": "Ольга поставила 2: плохо и долго",
                "raw": {"id": "rev2", "author_name": "Ольга", "rating": 2, "text": "Плохо и долго"},
            }
        ],
        generator=failing_generator,
    )

    assert result["llm_analysis_used"] is False
    assert result["analysis_source"] == "deterministic_fallback"
    assert result["external_dispatch_performed"] is False
    assert result["publish_state"] == "not_published"
    assert result["delivery_state"] == "not_dispatched"
    assert result["reply_drafts"]
    assert result["manual_review_reasons"]
    assert result["provenance"] == ["Отзывы"]


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
    cursor.tables["agent_run_steps"]["step1"] = {
        "id": "step1",
        "run_id": "run1",
        "step_index": 0,
        "step_key": "send",
        "step_type": "capability",
        "status": "completed",
        "input_json": {},
        "output_json": {"orchestrator": {"action_id": "action-1"}},
    }

    run = AgentBlueprintRunner(cursor, FakeObservabilityOrchestrator()).load_run("run1", {"user_id": "user1"})
    observability = run["observability"]

    assert observability["schema"] == "agent_run_observability_v1"
    assert observability["action_ids"] == ["action-1"]
    assert observability["action_ledger"]["items"][0]["billing_summary"]["settled_tokens"] == 42
    assert observability["delivery_status"]["state"] == "delivered"
    assert observability["cost_tokens"]["total_cost"] == 0.012
    assert observability["support_export"]["endpoint"] == "/api/agent-runs/run1/support-export"


class FakeCursor:
    def __init__(self):
        self.tables = {
            "agent_blueprints": {},
            "agent_blueprint_versions": {},
            "agent_runs": {},
            "agent_run_steps": {},
            "agent_artifacts": {},
            "agent_approvals": {},
            "prospectingleads": {},
            "outreachmessagedrafts": {},
        }
        self.last_result = None
        self.last_results = []

    def execute(self, query, params=None):
        normalized_query = " ".join(query.split()).lower()
        params = params or ()
        if normalized_query.startswith("select * from agent_blueprint_versions where id"):
            self.last_result = self.tables["agent_blueprint_versions"].get(params[0])
            return None
        if normalized_query.startswith("select * from agent_blueprints where id"):
            self.last_result = self.tables["agent_blueprints"].get(params[0])
            return None
        if normalized_query.startswith("insert into agent_runs"):
            self.tables["agent_runs"][params[0]] = {
                "id": params[0],
                "blueprint_id": params[1],
                "blueprint_version_id": params[2],
                "business_id": params[3],
                "status": params[4],
                "input_json": json.loads(params[5]),
                "output_json": json.loads(params[6]),
                "created_by_user_id": params[7],
            }
            return None
        if normalized_query.startswith("select * from agent_runs where id"):
            self.last_result = self.tables["agent_runs"].get(params[0])
            return None
        if normalized_query.startswith("select step_index from agent_run_steps"):
            run_id = params[0]
            self.last_results = [
                {"step_index": step["step_index"]}
                for step in self.tables["agent_run_steps"].values()
                if step["run_id"] == run_id and step["status"] in {"completed", "rejected"}
            ]
            return None
        if normalized_query.startswith("insert into agent_run_steps"):
            self.tables["agent_run_steps"][params[0]] = {
                "id": params[0],
                "run_id": params[1],
                "step_index": params[2],
                "step_key": params[3],
                "step_type": params[4],
                "status": params[5],
                "input_json": json.loads(params[6]),
                "output_json": json.loads(params[7]),
            }
            return None
        if normalized_query.startswith("insert into agent_artifacts"):
            self.tables["agent_artifacts"][params[0]] = {
                "id": params[0],
                "run_id": params[1],
                "step_id": params[2],
                "artifact_type": params[3],
                "title": params[4],
                "payload_json": json.loads(params[5]),
            }
            return None
        if normalized_query.startswith("insert into agent_approvals"):
            self.tables["agent_approvals"][params[0]] = {
                "id": params[0],
                "run_id": params[1],
                "step_id": params[2],
                "status": "pending",
                "approval_type": params[3],
                "title": params[4],
                "payload_json": json.loads(params[5]),
                "requested_by_user_id": params[6],
            }
            return None
        if normalized_query.startswith("update agent_runs set status = 'waiting_approval'"):
            self.tables["agent_runs"][params[0]]["status"] = "waiting_approval"
            return None
        if normalized_query.startswith("update agent_runs set status = 'failed'"):
            self.tables["agent_runs"][params[1]]["status"] = "failed"
            self.tables["agent_runs"][params[1]]["error_text"] = params[0]
            return None
        if normalized_query.startswith("update agent_run_steps set status = 'failed'"):
            self.tables["agent_run_steps"][params[2]]["status"] = "failed"
            self.tables["agent_run_steps"][params[2]]["output_json"] = json.loads(params[0])
            self.tables["agent_run_steps"][params[2]]["error_text"] = params[1]
            return None
        if normalized_query.startswith("update agent_run_steps set status = 'blocked'"):
            self.tables["agent_run_steps"][params[2]]["status"] = "blocked"
            self.tables["agent_run_steps"][params[2]]["output_json"] = json.loads(params[0])
            self.tables["agent_run_steps"][params[2]]["error_text"] = params[1]
            return None
        if normalized_query.startswith("select * from agent_run_steps"):
            run_id = params[0]
            self.last_results = sorted(
                [step for step in self.tables["agent_run_steps"].values() if step["run_id"] == run_id],
                key=lambda item: item["step_index"],
            )
            return None
        if normalized_query.startswith("select * from agent_artifacts"):
            run_id = params[0]
            self.last_results = [item for item in self.tables["agent_artifacts"].values() if item["run_id"] == run_id]
            return None
        if normalized_query.startswith("select * from agent_approvals where id"):
            approval_id = params[0]
            run_id = params[1]
            approval = self.tables["agent_approvals"].get(approval_id)
            self.last_result = approval if approval and approval["run_id"] == run_id else None
            return None
        if normalized_query.startswith("select * from agent_approvals"):
            run_id = params[0]
            self.last_results = [item for item in self.tables["agent_approvals"].values() if item["run_id"] == run_id]
            return None
        if normalized_query.startswith("select payload_json from agent_artifacts"):
            run_id = params[0]
            artifact_type = params[1]
            matches = [
                item
                for item in self.tables["agent_artifacts"].values()
                if item["run_id"] == run_id and item["artifact_type"] == artifact_type
            ]
            self.last_result = {"payload_json": matches[-1]["payload_json"]} if matches else None
            return None
        if normalized_query.startswith("select 1 from agent_approvals"):
            run_id = params[0]
            approval_type = params[1] if len(params) > 1 else None
            matches = [
                item
                for item in self.tables["agent_approvals"].values()
                if item["run_id"] == run_id
                and item["status"] == "approved"
                and (approval_type is None or item["approval_type"] == approval_type)
            ]
            self.last_result = {"?column?": 1} if matches else None
            return None
        if normalized_query.startswith("select id, name, city, category, source"):
            business_id = params[0]
            lead_ids = params[1] if len(params) > 2 and isinstance(params[1], list) else []
            rows = []
            for lead in self.tables["prospectingleads"].values():
                if lead.get("business_id") != business_id:
                    continue
                if lead_ids and lead.get("id") not in lead_ids:
                    continue
                rows.append(lead)
            self.last_results = rows
            return None
        if normalized_query.startswith("select id, name, city, email"):
            business_id = params[0]
            lead_ids = params[1] if len(params) > 2 else []
            rows = []
            for lead in self.tables["prospectingleads"].values():
                if lead.get("business_id") != business_id:
                    continue
                if lead_ids and lead.get("id") not in lead_ids:
                    continue
                rows.append(lead)
            self.last_results = rows
            return None
        if normalized_query.startswith("update prospectingleads set status = case"):
            business_id = params[3]
            lead_ids = params[4]
            for lead_id in lead_ids:
                lead = self.tables["prospectingleads"].get(lead_id)
                if lead and lead.get("business_id") == business_id and lead.get("status") not in {
                    "channel_selected",
                    "draft_ready",
                    "queued_for_send",
                    "sent",
                    "delivered",
                }:
                    lead["status"] = params[0]
                    lead["pipeline_status"] = params[1]
                    lead["last_manual_action_by"] = params[2]
            return None
        if normalized_query.startswith("select d.id"):
            business_id = params[0]
            draft_ids = params[1] if len(params) > 2 else []
            rows = []
            for draft in self.tables["outreachmessagedrafts"].values():
                lead = self.tables["prospectingleads"].get(draft.get("lead_id"))
                if not lead or lead.get("business_id") != business_id:
                    continue
                if draft_ids and draft.get("id") not in draft_ids:
                    continue
                rows.append(
                    {
                        **draft,
                        "lead_name": lead.get("name"),
                    }
                )
            self.last_results = rows
            return None
        if normalized_query.startswith("select id, name, category"):
            business_id = params[0]
            lead_ids = set(params[1])
            limit = params[2]
            rows = []
            for lead in self.tables["prospectingleads"].values():
                if lead.get("business_id") != business_id or lead.get("id") not in lead_ids:
                    continue
                has_draft = any(
                    draft.get("lead_id") == lead.get("id") and draft.get("status") in {"generated", "edited", "approved"}
                    for draft in self.tables["outreachmessagedrafts"].values()
                )
                if not has_draft:
                    rows.append(lead)
            self.last_results = rows[:limit]
            return None
        if normalized_query.startswith("insert into outreachmessagedrafts"):
            self.tables["outreachmessagedrafts"][params[0]] = {
                "id": params[0],
                "lead_id": params[1],
                "channel": params[2],
                "angle_type": params[3],
                "tone": params[4],
                "status": params[5],
                "generated_text": params[6],
                "edited_text": params[7],
                "learning_note_json": json.loads(params[8]),
                "created_by": params[9],
                "approved_text": None,
            }
            return None
        if normalized_query.startswith("update prospectingleads set status = %s, selected_channel"):
            lead = self.tables["prospectingleads"].get(params[3])
            if lead and lead.get("business_id") == params[4]:
                lead["status"] = params[0]
                lead["selected_channel"] = params[1]
                lead["pipeline_status"] = params[2]
            return None
        if normalized_query.startswith("update outreachmessagedrafts set status = %s"):
            draft_ids = params[2]
            business_id = params[3]
            for draft_id in draft_ids:
                draft = self.tables["outreachmessagedrafts"].get(draft_id)
                lead = self.tables["prospectingleads"].get((draft or {}).get("lead_id"))
                if draft and lead and lead.get("business_id") == business_id:
                    draft["status"] = params[0]
                    draft["approved_by"] = params[1]
                    draft["approved_text"] = draft.get("edited_text") or draft.get("generated_text")
                    draft["edited_text"] = draft.get("edited_text") or draft.get("generated_text")
            return None
        if normalized_query.startswith("update prospectingleads set status = %s, pipeline_status"):
            business_id = params[2]
            draft_ids = set(params[3])
            lead_ids = {
                draft.get("lead_id")
                for draft in self.tables["outreachmessagedrafts"].values()
                if draft.get("id") in draft_ids
            }
            for lead_id in lead_ids:
                lead = self.tables["prospectingleads"].get(lead_id)
                if lead and lead.get("business_id") == business_id:
                    lead["status"] = params[0]
                    lead["pipeline_status"] = params[1]
            return None
        if normalized_query.startswith("update agent_approvals set status = 'approved'"):
            approval = self.tables["agent_approvals"].get(params[2])
            if approval and approval["run_id"] == params[3]:
                approval["status"] = "approved"
                approval["decided_by_user_id"] = params[0]
                approval["decision_reason"] = params[1]
            return None
        if normalized_query.startswith("update agent_run_steps set status = 'completed'"):
            step = self.tables["agent_run_steps"].get(params[1])
            if step:
                step["status"] = "completed"
                step["output_json"] = json.loads(params[0])
            return None
        if normalized_query.startswith("update agent_runs set status = 'running'"):
            self.tables["agent_runs"][params[0]]["status"] = "running"
            return None
        if normalized_query.startswith("update agent_runs set status = 'completed'"):
            self.tables["agent_runs"][params[1]]["status"] = "completed"
            self.tables["agent_runs"][params[1]]["output_json"] = json.loads(params[0])
            return None
        if normalized_query.startswith("select count(*) as count from agent_artifacts"):
            run_id = params[0]
            self.last_result = {"count": len([item for item in self.tables["agent_artifacts"].values() if item["run_id"] == run_id])}
            return None
        if normalized_query.startswith("select count(*) as count from agent_approvals"):
            run_id = params[0]
            self.last_result = {"count": len([item for item in self.tables["agent_approvals"].values() if item["run_id"] == run_id])}
            return None
        raise AssertionError(f"Unhandled SQL in fake cursor: {query}")

    def fetchone(self):
        return self.last_result

    def fetchall(self):
        return self.last_results


class FakeDatahubCursor:
    def __init__(self):
        self.last_results = []

    def execute(self, query, params=None):
        normalized_query = " ".join(query.split()).lower()
        if "from businesses" in normalized_query:
            self.last_results = [{"id": "biz1", "name": "Local Test", "business_type": "beauty", "city": "Moscow", "address": "Street"}]
            return None
        if "from userservices" in normalized_query:
            self.last_results = [
                {"id": "svc1", "name": "Haircut", "price": 1000, "description": "Cut"},
                {"id": "svc2", "name": "Color", "price": 3000, "description": "Color"},
            ]
            return None
        if "from externalbusinessreviews" in normalized_query:
            self.last_results = [{"id": "rev1", "author_name": "Anna", "rating": 5, "text": "Great"}]
            return None
        if "from prospectingleads" in normalized_query:
            self.last_results = []
            return None
        if "from outreachmessagedrafts" in normalized_query:
            self.last_results = [{"id": "draft1", "channel": "email", "status": "generated", "generated_text": "Hello"}]
            return None
        raise AssertionError(f"Unhandled Datahub SQL: {query}")

    def fetchall(self):
        return self.last_results


class CountingOrchestrator:
    def __init__(self):
        self.calls = 0
        self.last_envelope = None

    def execute(self, envelope, user_data, *, allow_execute_when_approved=False):
        self.calls += 1
        self.last_envelope = envelope
        return {
            "success": True,
            "status": "completed",
            "result": {
                "status": "queued_for_dispatch",
                "dispatch_state": "queued_not_dispatched",
                "external_dispatch_performed": False,
            },
        }


class FakeUpload:
    def __init__(self, filename, mimetype, data):
        self.filename = filename
        self.mimetype = mimetype
        self._data = data

    def read(self):
        return self._data


class FakeOutreachConnection:
    def __init__(self, draft_rows):
        self.cursor_instance = FakeOutreachCursor(draft_rows)
        self.inserted = self.cursor_instance.inserted
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class FakeOutreachCursor:
    def __init__(self, draft_rows):
        self.draft_rows = draft_rows
        self.last_result = None
        self.last_results = []
        self.inserted = []

    def execute(self, query, params=None):
        normalized_query = " ".join(query.split()).lower()
        params = params or ()
        if normalized_query.startswith("select count(*) as cnt"):
            self.last_result = {"cnt": 0}
            return None
        if normalized_query.startswith("select d.id"):
            self.last_results = self.draft_rows
            return None
        if normalized_query.startswith("insert into outreachsendbatches"):
            self.inserted.append(
                {
                    "kind": "batch",
                    "id": params[0],
                    "daily_limit": params[1],
                    "status": params[2],
                    "created_by": params[3],
                    "approved_by": params[4],
                }
            )
            return None
        if normalized_query.startswith("insert into outreachsendqueue"):
            self.inserted.append(
                {
                    "kind": "queue",
                    "id": params[0],
                    "batch_id": params[1],
                    "lead_id": params[2],
                    "draft_id": params[3],
                    "channel": params[4],
                    "delivery_status": params[5],
                }
            )
            return None
        if normalized_query.startswith("update prospectingleads"):
            self.inserted.append(
                {
                    "kind": "lead_update",
                    "status": params[0],
                    "pipeline_status": params[1],
                    "lead_id": params[2],
                    "business_id": params[3],
                }
            )
            return None
        raise AssertionError(f"Unhandled SQL in fake outreach cursor: {query}")

    def fetchone(self):
        return self.last_result

    def fetchall(self):
        return self.last_results
