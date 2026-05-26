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


def test_agent_blueprint_api_guards_version_blueprint_mismatch():
    api_source = Path("src/api/agent_blueprints_api.py").read_text(encoding="utf-8")
    workspace_source = Path("src/services/agent_blueprint_workspace.py").read_text(encoding="utf-8")
    document_llm_source = Path("src/services/agent_document_llm.py").read_text(encoding="utf-8")
    builder_api_source = Path("src/api/agent_builder_api.py").read_text(encoding="utf-8")

    assert "VERSION_BLUEPRINT_MISMATCH" in api_source
    assert "_load_blueprint_version_for_blueprint" in api_source
    assert "build_agent_blueprint_orchestrator" in api_source
    assert "run_status" in api_source
    assert "approval_queue" in api_source
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
    assert "/api/agent-blueprints/<blueprint_id>/versions/<version_id>/diff" in api_source
    assert "/api/agent-blueprints/<blueprint_id>/versions/<version_id>/activate" in api_source
    assert "/api/agent-blueprints/<blueprint_id>/versions/<version_id>/rollback" in api_source
    assert "_resolve_active_version" in api_source
    assert "_remember_active_version" in api_source
    assert "build_agent_version_diff" in workspace_source
    assert "analyze_document_sources_with_llm" in workspace_source
    assert "analyze_text_with_gigachat" in document_llm_source
    assert "external_dispatch_performed" in document_llm_source
    assert "provenance" in document_llm_source
    assert "/api/agent-builder/sessions" in builder_api_source
    assert "build_agent_builder_state" in builder_api_source
    assert "create_blueprint_from_agent_builder_session" in builder_api_source


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


def test_agent_source_ingestion_extracts_text_docx_xlsx_and_rejects_unsafe_files():
    import io
    import zipfile

    from openpyxl import Workbook

    from services.agent_source_ingestion import build_agent_source_from_upload

    text_source, text_error = build_agent_source_from_upload(
        FakeUpload("contract.txt", "text/plain", "Оплата 10000. Ответственность: штраф.".encode("utf-8")),
        "Договор",
    )
    assert text_error == {}
    assert text_source["content_text"].startswith("Оплата 10000")
    assert text_source["extraction_state"] == "ready"

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
