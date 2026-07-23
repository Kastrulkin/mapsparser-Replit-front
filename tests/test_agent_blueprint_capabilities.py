import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tests.agent_blueprint_fakes import *  # noqa: F403
from tests.source_contract_helpers import read_agent_blueprints_frontend_source


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


def test_domain_capability_handlers_read_and_create_internal_requests(monkeypatch):
    from services import agent_capability_handlers

    db = FakeCapabilityDatabase()
    monkeypatch.setattr(agent_capability_handlers, "DatabaseManager", lambda: db)
    handlers = agent_capability_handlers.build_capability_handlers()
    user_data = {"user_id": "user-1"}

    appointments = handlers["appointments.read"](
        {
            "tenant_id": "biz1",
            "actor": {"id": "user-1"},
            "capability": "appointments.read",
            "payload": {"limit": 5, "status": "confirmed"},
        },
        user_data,
    )
    assert appointments["result"]["status"] == "read_completed"
    assert appointments["result"]["source"] == "Bookings"
    assert appointments["result"]["count"] == 1
    assert appointments["result"]["appointments"][0]["client_phone"] == "+79990000000"

    reminder = handlers["communications.send_reminder"](
        {
            "tenant_id": "biz1",
            "action_id": "act-reminder",
            "actor": {"id": "user-1"},
            "capability": "communications.send_reminder",
            "payload": {"limit": 10, "message": "Ждём вас завтра", "channel": "whatsapp"},
        },
        user_data,
    )
    assert reminder["result"]["status"] == "send_request_created"
    assert reminder["result"]["dispatch_state"] == "pending_human"
    assert reminder["result"]["delivery_state"] == "not_dispatched"
    assert reminder["result"]["provider_write_performed"] is False
    assert reminder["result"]["external_dispatch_performed"] is False
    assert reminder["result"]["recipient_count"] == 1
    assert db.cursor_instance.inserted["agent_communication_requests"]["capability"] == "communications.send_reminder"


def test_review_publish_and_service_optimize_capabilities_create_safe_local_records(monkeypatch):
    from services import agent_capability_handlers

    db = FakeCapabilityDatabase()
    monkeypatch.setattr(agent_capability_handlers, "DatabaseManager", lambda: db)
    handlers = agent_capability_handlers.build_capability_handlers()
    user_data = {"user_id": "user-1"}

    publish_request = handlers["reviews.reply.publish_request"](
        {
            "tenant_id": "biz1",
            "action_id": "act-review",
            "actor": {"id": "user-1"},
            "capability": "reviews.reply.publish_request",
            "payload": {"review_id": "rev1", "reply": "Спасибо за отзыв!"},
        },
        user_data,
    )
    assert publish_request["result"]["status"] == "publish_request_created"
    assert publish_request["result"]["dispatch_state"] == "pending_human"
    assert publish_request["result"]["manual_publish_required"] is True
    assert publish_request["result"]["localos_write_performed"] is True
    assert publish_request["result"]["localos_url"] == "/dashboard/card?tab=reviews&review_filter=needs_reply"
    assert publish_request["result"]["provider_write_performed"] is False
    assert db.cursor_instance.inserted["reviewreplydrafts"]["status"] == "publish_requested"

    optimize = handlers["services.optimize"](
        {
            "tenant_id": "biz1",
            "action_id": "act-services",
            "actor": {"id": "user-1"},
            "capability": "services.optimize",
            "payload": {"limit": 5},
        },
        user_data,
    )
    assert optimize["result"]["status"] == "optimized_draft"
    assert optimize["result"]["apply_performed"] is False
    assert optimize["result"]["manual_apply_required"] is True
    assert optimize["result"]["provider_write_performed"] is False
    assert optimize["result"]["suggestions"][0]["requires_manual_approval"] is True
    assert optimize["result"]["visual_diff"][0]["changed_fields"]
    assert optimize["result"]["visual_diff"][0]["before"]["name"] == "Стрижка"
    assert optimize["result"]["visual_diff"][0]["after"]["name"]
    assert db.cursor_instance.inserted["agent_service_optimization_requests"]["apply_state"] == "not_applied"
    assert db.cursor_instance.inserted["agent_service_optimization_requests"]["diff_json"][0]["changed_fields"]


def test_billing_capabilities_delegate_to_credit_reservation_layer(monkeypatch):
    from services import agent_capability_handlers

    db = FakeCapabilityDatabase()
    calls = {"reserve": None, "settle": None}

    def fake_reserve(cursor, **kwargs):
        calls["reserve"] = kwargs
        return {
            "reservation_id": "res-1",
            "status": "reserved",
            "credit_reserved": True,
            "side_effects": {"credit_reserved": True},
        }

    def fake_settle(cursor, **kwargs):
        calls["settle"] = kwargs
        return {
            "reservation_id": "res-1",
            "status": "settled",
            "side_effects": {"credit_charged": True, "credit_released": False},
        }

    monkeypatch.setattr(agent_capability_handlers, "DatabaseManager", lambda: db)
    monkeypatch.setattr(agent_capability_handlers, "reserve_paid_action_credits", fake_reserve)
    monkeypatch.setattr(agent_capability_handlers, "finalize_reserved_action_credits", fake_settle)
    handlers = agent_capability_handlers.build_capability_handlers()

    reserve = handlers["billing.reserve"](
        {
            "tenant_id": "biz1",
            "actor": {"id": "user-1"},
            "idempotency_key": "idem-reserve",
            "capability": "billing.reserve",
            "payload": {"estimated_credits": 3, "action_key": "agent.test"},
        },
        {"user_id": "user-1"},
    )
    assert reserve["result"]["status"] == "reserved"
    assert reserve["result"]["credit_reserved"] is True
    assert calls["reserve"]["business_id"] == "biz1"
    assert calls["reserve"]["estimated_credits"] == 3
    assert calls["reserve"]["idempotency_key"] == "idem-reserve"

    settle = handlers["billing.settle"](
        {
            "tenant_id": "biz1",
            "action_id": "action-settle",
            "actor": {"id": "user-1"},
            "capability": "billing.settle",
            "payload": {"reservation_id": "res-1"},
        },
        {"user_id": "user-1"},
    )
    assert settle["result"]["status"] == "settled"
    assert settle["result"]["credit_charged"] is True
    assert settle["result"]["credit_released"] is False
    assert calls["settle"]["reservation_id"] == "res-1"
    assert calls["settle"]["external_id"] == "action-settle"


def test_sheets_append_row_capability_creates_local_request_without_provider_write(monkeypatch):
    from services import agent_capability_handlers

    db = FakeCapabilityDatabase()
    monkeypatch.setattr(agent_capability_handlers, "DatabaseManager", lambda: db)
    handlers = agent_capability_handlers.build_capability_handlers()

    result = handlers["sheets.append_row_request"](
        {
            "tenant_id": "biz1",
            "action_id": "act-sheet",
            "actor": {"id": "user-1"},
            "capability": "sheets.append_row_request",
            "payload": {
                "spreadsheet_id": "spreadsheet-1",
                "sheet_name": "Leads",
                "row_values": ["{{received_at}}", "{{telegram_username}}", "{{message_text}}"],
                "telegram": {
                    "message_text": "Новая заявка",
                    "telegram_username": "anna",
                    "received_at": "2026-06-09T10:00:00Z",
                },
            },
        },
        {"user_id": "user-1"},
    )

    assert result["result"]["status"] == "sheet_append_request_created"
    assert result["result"]["approval_state"] == "pending_human"
    assert result["result"]["apply_state"] == "not_applied"
    assert result["result"]["provider_write_performed"] is False
    assert result["result"]["row_values"] == ["2026-06-09T10:00:00Z", "anna", "Новая заявка"]
    assert db.cursor_instance.inserted["agent_sheet_operation_requests"]["provider_write_performed"] is False
    assert db.cursor_instance.inserted["agent_sheet_operation_requests"]["row_values_json"] == [
        "2026-06-09T10:00:00Z",
        "anna",
        "Новая заявка",
    ]


def test_sheets_append_row_capability_requires_sheet_connection(monkeypatch):
    from services import agent_capability_handlers

    db = FakeCapabilityDatabase()
    monkeypatch.setattr(agent_capability_handlers, "DatabaseManager", lambda: db)
    result = agent_capability_handlers.build_capability_handlers()["sheets.append_row_request"](
        {
            "tenant_id": "biz1",
            "actor": {"id": "user-1"},
            "capability": "sheets.append_row_request",
            "payload": {"row_values": ["value"]},
        },
        {"user_id": "user-1"},
    )

    assert result["result"]["status"] == "validation_error"
    assert result["result"]["error_code"] == "SHEET_CONNECTION_REQUIRED"
    assert result["result"]["provider_write_performed"] is False


def test_sheets_append_row_capability_requires_orchestrator_human_gate():
    from core.action_policy import evaluate_risk_policy

    decision = evaluate_risk_policy("sheets.append_row_request", {"spreadsheet_id": "sheet-1"}, {})

    assert decision["ok"] is True
    assert decision["requires_human"] is True
    assert "spreadsheet" in decision["reason"]


def test_finance_transaction_create_capability_normalizes_rows_without_localos_write():
    from services import agent_capability_handlers

    handlers = agent_capability_handlers.build_capability_handlers()
    result = handlers["finance.transaction.create"](
        {
            "tenant_id": "biz1",
            "action_id": "act-finance",
            "actor": {"id": "user-1"},
            "capability": "finance.transaction.create",
            "payload": {
                "source": "google_sheets",
                "rows": [
                    {
                        "date": "2026-06-09",
                        "type": "income",
                        "category": "sales",
                        "amount": "12000",
                        "comment": "Оплата по таблице",
                    },
                    {
                        "date": "2026-06-09",
                        "type": "expense",
                        "amount": "2500",
                        "comment": "Материалы без категории",
                    },
                ],
            },
        },
        {"user_id": "user-1"},
    )

    payload = result["result"]
    assert payload["status"] == "finance_transaction_request_created"
    assert payload["proposal_count"] == 2
    assert payload["approval_state"] == "pending_human"
    assert payload["apply_state"] == "not_applied"
    assert payload["manual_apply_required"] is True
    assert payload["localos_write_performed"] is False
    assert payload["provider_write_performed"] is False
    assert payload["finance_entry_proposals"][0]["type"] == "revenue"
    assert payload["finance_entry_proposals"][0]["duplicate_key"]
    assert payload["rows_requiring_review"][0]["review_reasons"] == ["category_missing_or_default"]


def test_finance_transaction_create_requires_orchestrator_human_gate():
    from core.action_policy import evaluate_risk_policy

    decision = evaluate_risk_policy("finance.transaction.create", {"amount": 12000}, {})

    assert decision["ok"] is True
    assert decision["requires_human"] is True
    assert "finance" in decision["reason"]


def test_approved_domain_executor_moves_sheet_request_after_human_gate():
    from services.agent_domain_request_executors import execute_approved_domain_requests

    cursor = FakeApprovedDomainExecutorCursor()
    cursor.tables["agent_sheet_operation_requests"]["sheet-request-1"] = {
        "id": "sheet-request-1",
        "business_id": "biz1",
        "action_id": "action-1",
        "status": "request_created",
        "approval_state": "pending_human",
        "apply_state": "not_applied",
        "operation": "append_row",
        "integration_id": "integration-1",
        "spreadsheet_id": "spreadsheet-1",
        "sheet_name": "Leads",
        "provider_write_performed": False,
    }

    result = execute_approved_domain_requests(
        cursor,
        run={"id": "run1", "business_id": "biz1"},
        step={"key": "request_sheet_append"},
        orchestrator_result={
            "action_id": "action-1",
            "result": {"request_id": "sheet-request-1"},
        },
        user_data={"user_id": "user1"},
    )

    request = cursor.tables["agent_sheet_operation_requests"]["sheet-request-1"]
    assert result["executed"] == 1
    assert result["provider_writes_performed"] is False
    assert result["items"][0]["kind"] == "sheet_operation_request"
    assert request["status"] == "approved_for_execution"
    assert request["approval_state"] == "approved"
    assert request["apply_state"] == "provider_request_queued"
    assert request["provider_write_performed"] is False
    assert result["items"][0]["apply_state"] == "provider_request_queued"
    assert result["items"][0]["provider_handoff"]["provider_executor"] == "manual_controlled_google_sheets_append"
    assert result["items"][0]["provider_handoff"]["spreadsheet_id"] == "spreadsheet-1"
    assert cursor.ledger_entries[0]["action_type"] == "agent_domain_request_approved"
    assert cursor.ledger_entries[0]["status"] == "approved_pending_provider_executor"
    assert cursor.ledger_entries[0]["metadata"]["run_id"] == "run1"
    assert cursor.ledger_entries[0]["output_summary"]["state"] == "provider_request_queued"


def test_approved_domain_executor_applies_finance_transactions_after_human_gate():
    from services.agent_domain_request_executors import execute_approved_domain_requests

    cursor = FakeApprovedDomainExecutorCursor()
    proposal = {
        "record_type": "entry",
        "date": "2026-06-09",
        "type": "revenue",
        "category": "sales",
        "amount": 12000,
        "comment": "Оплата по таблице",
        "row_number": 1,
        "duplicate_key": "finance-dup-1",
    }

    result = execute_approved_domain_requests(
        cursor,
        run={"id": "run1", "business_id": "biz1"},
        step={"key": "request_localos_finance"},
        orchestrator_result={
            "action_id": "action-finance",
            "result": {
                "request_id": "finance-request-1",
                "status": "finance_transaction_request_created",
                "source": "google_sheets",
                "normalized_mapping": {"amount": "amount"},
                "finance_entry_proposals": [proposal],
                "errors": [],
            },
        },
        user_data={"user_id": "user1"},
    )

    batches = list(cursor.tables["finance_import_batches"].values())
    entries = list(cursor.tables["finance_entries"].values())
    assert result["executed"] == 1
    assert result["localos_writes_performed"] is True
    assert result["provider_writes_performed"] is False
    assert result["items"][0]["kind"] == "finance_transaction_request"
    assert result["items"][0]["apply_state"] == "applied"
    assert batches[0]["source_type"] == "agent"
    assert batches[0]["status"] == "completed"
    assert batches[0]["rows_imported"] == 1
    assert entries[0]["source"] == "agent"
    assert entries[0]["duplicate_key"] == "finance-dup-1"
    assert entries[0]["amount"] == 12000
    assert cursor.ledger_entries[0]["capability"] == "finance.transaction.create"
    assert cursor.ledger_entries[0]["output_summary"]["localos_write_performed"] is True
    assert cursor.ledger_entries[0]["metadata"]["provider_write_performed"] is False


def test_sheet_provider_executor_marks_unavailable_without_adapter():
    from services.agent_sheet_provider_executor import execute_queued_sheet_provider_requests

    cursor = FakeSheetProviderExecutorCursor()
    cursor.tables["agent_sheet_operation_requests"]["sheet-request-1"] = {
        "id": "sheet-request-1",
        "business_id": "biz1",
        "user_id": "user1",
        "action_id": "action-1",
        "status": "approved_for_execution",
        "approval_state": "approved",
        "apply_state": "provider_request_queued",
        "operation": "append_row",
        "integration_id": "integration-1",
        "spreadsheet_id": "spreadsheet-1",
        "sheet_name": "Leads",
        "row_values_json": ["2026-06-09T10:00:00Z", "anna", "Новая заявка"],
        "mapping_json": {},
        "source_event_json": {"trigger_event_id": "trigger-1"},
        "limits_json": {"daily_append_cap": 50},
        "provider_write_performed": False,
    }

    result = execute_queued_sheet_provider_requests(cursor, business_id="biz1", user_id="operator1")

    request = cursor.tables["agent_sheet_operation_requests"]["sheet-request-1"]
    assert result["processed"] == 1
    assert result["provider_writes_performed"] is False
    assert result["items"][0]["apply_state"] == "provider_unavailable"
    assert request["status"] == "provider_unavailable"
    assert request["apply_state"] == "provider_unavailable"
    assert request["provider_write_performed"] is False
    assert "integration" in request["error_text"] or "not found" in request["error_text"]
    assert cursor.ledger_entries[0]["action_type"] == "agent_sheet_provider_executor"
    assert cursor.ledger_entries[0]["status"] == "provider_attention"
    assert cursor.ledger_entries[0]["metadata"]["provider_write_performed"] is False


def test_google_sheets_adapter_loads_active_agent_integration_credentials(monkeypatch):
    from services import agent_google_sheets_adapter

    cursor = FakeGoogleSheetsIntegrationCursor()
    cursor.agent_integrations["integration-1"] = {
        "id": "integration-1",
        "business_id": "biz1",
        "provider": "google_sheets",
        "status": "active",
        "auth_ref": "external-1",
        "config_json": {},
    }
    cursor.external_accounts["external-1"] = {
        "id": "external-1",
        "business_id": "biz1",
        "source": "google_sheets",
        "auth_data_encrypted": "encrypted-auth",
        "is_active": True,
    }
    monkeypatch.setattr(
        agent_google_sheets_adapter,
        "decrypt_auth_data",
        lambda encrypted: json.dumps(
            {
                "token": "access-token",
                "scopes": [agent_google_sheets_adapter.SHEETS_SCOPE],
            }
        ),
    )

    adapter = agent_google_sheets_adapter.load_google_sheets_append_adapter(
        cursor,
        business_id="biz1",
        integration_id="integration-1",
    )

    assert adapter.credentials["token"] == "access-token"


def test_google_sheets_adapter_can_use_google_business_oauth_credentials(monkeypatch):
    from services import agent_google_sheets_adapter

    cursor = FakeGoogleSheetsIntegrationCursor()
    cursor.external_accounts["google-1"] = {
        "id": "google-1",
        "business_id": "biz1",
        "source": "google_business",
        "display_name": "Google-доступ",
        "auth_data_encrypted": "encrypted-auth",
        "is_active": True,
    }
    monkeypatch.setattr(
        agent_google_sheets_adapter,
        "decrypt_auth_data",
        lambda encrypted: json.dumps(
            {
                "token": "access-token",
                "scopes": [agent_google_sheets_adapter.SHEETS_SCOPE],
            }
        ),
    )

    adapter = agent_google_sheets_adapter.load_google_sheets_append_adapter(
        cursor,
        business_id="biz1",
        integration_id="stale-integration-id",
    )

    assert adapter.credentials["token"] == "access-token"


def test_preflight_treats_google_business_oauth_as_sheets_credential():
    from services.agent_integration_preflight import build_agent_integration_preflight

    class Cursor:
        def __init__(self):
            self.rows = []

        def execute(self, query, params=None):
            normalized_query = " ".join(query.split()).lower()
            self.rows = []
            if "from agent_integrations" in normalized_query:
                return None
            if "from externalbusinessaccounts" in normalized_query:
                self.rows = [
                    {
                        "id": "google-1",
                        "business_id": "biz1",
                        "source": "google_business",
                        "display_name": "Google-доступ",
                    }
                ]
                return None
            raise AssertionError(f"Unhandled SQL: {query}")

        def fetchall(self):
            return self.rows

    metadata = {
        "required_integration_bindings": [
            {
                "key": "google_sheets_read",
                "provider": "google_sheets",
                "capability": "google_sheets.read_rows",
                "required": True,
                "required_config": ["spreadsheet_id", "sheet_name"],
            }
        ],
        "agent_binding_integrations": {
            "google_sheets_read": {
                "integration_id": "stale-integration-id",
                "spreadsheet_id": "spreadsheet-1",
                "sheet_name": "Trips",
            }
        },
    }

    preflight = build_agent_integration_preflight(
        Cursor(),
        business_id="biz1",
        metadata=metadata,
        input_payload={},
    )

    assert preflight["ready"] is True
    assert preflight["items"][0]["resolution"] == "agent_integration_native_provider"


def test_google_oauth_returns_to_agent_flow_from_reconnect_cta():
    agent_page = read_agent_blueprints_frontend_source()
    integrations_page = Path("frontend/src/pages/dashboard/settings/IntegrationsPageV3.tsx").read_text()
    google_api = Path("src/api/google_business_api.py").read_text()

    assert "return_to: '/dashboard/agents'" in agent_page
    assert "oauthParams.set('return_to'" in integrations_page
    assert "request.args.get(\"return_to\")" in google_api
    assert "dashboard/profile?google_auth" not in google_api


def test_google_sheets_adapter_append_row_uses_google_sheets_api(monkeypatch):
    from services import agent_google_sheets_adapter

    calls = []

    class FakeResponse:
        status_code = 200
        content = b"{}"
        text = "{}"

        def json(self):
            return {"updates": {"updatedRange": "Leads!A2:C2", "updatedRows": 1, "updatedCells": 3}}

    def fake_post(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return FakeResponse()

    monkeypatch.setattr(agent_google_sheets_adapter.requests, "post", fake_post)
    adapter = agent_google_sheets_adapter.GoogleSheetsAppendAdapter(
        {"token": "access-token", "scopes": [agent_google_sheets_adapter.SHEETS_SCOPE]}
    )

    result = adapter.append_row(
        {
            "spreadsheet_id": "spreadsheet-1",
            "sheet_name": "Leads",
            "row_values": ["2026-06-09T10:00:00Z", "anna", "Новая заявка"],
        }
    )

    assert result["success"] is True
    assert result["updated_rows"] == 1
    assert calls[0]["url"].startswith("https://sheets.googleapis.com/v4/spreadsheets/spreadsheet-1/values/Leads%21A1:append")
    assert calls[0]["params"]["valueInputOption"] == "USER_ENTERED"
    assert calls[0]["headers"]["Authorization"] == "Bearer access-token"
    assert calls[0]["json"]["values"][0] == ["2026-06-09T10:00:00Z", "anna", "Новая заявка"]


def test_google_sheets_adapter_update_cells_rechecks_before_write(monkeypatch):
    from services import agent_google_sheets_adapter

    calls = []

    class FakeResponse:
        status_code = 200
        content = b"{}"
        text = "{}"

        def __init__(self, payload):
            self.payload = payload

        def json(self):
            return self.payload

    def fake_get(url, **kwargs):
        calls.append({"method": "get", "url": url, **kwargs})
        return FakeResponse({"range": "Trips!B2:C2", "values": [["old", "10"]]})

    def fake_put(url, **kwargs):
        calls.append({"method": "put", "url": url, **kwargs})
        return FakeResponse({"updatedRange": "Trips!B2:C2", "updatedCells": 2})

    monkeypatch.setattr(agent_google_sheets_adapter.requests, "get", fake_get)
    monkeypatch.setattr(agent_google_sheets_adapter.requests, "put", fake_put)
    adapter = agent_google_sheets_adapter.GoogleSheetsAppendAdapter(
        {"token": "access-token", "scopes": [agent_google_sheets_adapter.SHEETS_SCOPE]}
    )

    result = adapter.update_cells({
        "operation": "update_cells",
        "spreadsheet_id": "spreadsheet-1",
        "range": "Trips!B2:C2",
        "expected_values": [["old", "10"]],
        "values": [["new", "20"]],
    })

    assert result["before"] == [["old", "10"]]
    assert result["after"] == [["new", "20"]]
    assert result["updated_cells"] == 2
    assert [call["method"] for call in calls] == ["get", "put"]
    assert calls[0]["params"]["valueRenderOption"] == "FORMULA"


def test_google_sheets_adapter_blocks_conflict_formula_and_cell_overflow(monkeypatch):
    from services import agent_google_sheets_adapter

    class FakeResponse:
        status_code = 200
        content = b"{}"
        text = "{}"

        def json(self):
            return {"values": [["changed"]]}

    monkeypatch.setattr(agent_google_sheets_adapter.requests, "get", lambda url, **kwargs: FakeResponse())
    adapter = agent_google_sheets_adapter.GoogleSheetsAppendAdapter(
        {"token": "access-token", "scopes": [agent_google_sheets_adapter.SHEETS_SCOPE]}
    )

    with pytest.raises(agent_google_sheets_adapter.GoogleSheetsAdapterError, match="VALUES_CHANGED"):
        adapter.update_cells({
            "spreadsheet_id": "sheet-1",
            "range": "Data!A1",
            "expected_values": [["old"]],
            "values": [["new"]],
        })
    with pytest.raises(agent_google_sheets_adapter.GoogleSheetsAdapterError, match="formulas"):
        adapter.append_row({"spreadsheet_id": "sheet-1", "row_values": ["=SUM(A1:A2)"]})
    with pytest.raises(agent_google_sheets_adapter.GoogleSheetsAdapterError, match="100 cells"):
        adapter.append_row({"spreadsheet_id": "sheet-1", "row_values": list(range(101))})


def test_google_sheets_adapter_read_rows_uses_google_sheets_values_api(monkeypatch):
    from services import agent_google_sheets_adapter

    calls = []

    class FakeResponse:
        status_code = 200
        content = b"{}"
        text = "{}"

        def json(self):
            return {
                "range": "Payments!A1:C3",
                "values": [
                    ["date", "type", "amount"],
                    ["2026-06-09", "revenue", "12000"],
                    ["2026-06-10", "expense", "2500"],
                ],
            }

    def fake_get(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return FakeResponse()

    monkeypatch.setattr(agent_google_sheets_adapter.requests, "get", fake_get)
    adapter = agent_google_sheets_adapter.GoogleSheetsAppendAdapter(
        {"token": "access-token", "scopes": [agent_google_sheets_adapter.SHEETS_SCOPE]}
    )

    result = adapter.read_rows(
        {
            "spreadsheet_id": "spreadsheet-1",
            "sheet_name": "Payments",
            "range": "Payments!A1:C",
            "limit": 10,
        }
    )

    assert result["success"] is True
    assert result["headers"] == ["date", "type", "amount"]
    assert result["row_count"] == 2
    assert result["rows"][0]["date"] == "2026-06-09"
    assert result["rows"][0]["amount"] == "12000"
    assert "spreadsheets/spreadsheet-1/values/Payments%21A1%3AC" in calls[0]["url"]
    assert calls[0]["headers"]["Authorization"] == "Bearer access-token"


def test_google_sheets_adapter_read_rows_falls_back_from_default_sheet1_to_first_tab(monkeypatch):
    from services import agent_google_sheets_adapter

    calls = []

    class InvalidRangeResponse:
        status_code = 400
        content = b'{"error":{"message":"Unable to parse range: Sheet1!A1:Z"}}'
        text = '{"error":{"message":"Unable to parse range: Sheet1!A1:Z"}}'

        def json(self):
            return {"error": {"message": "Unable to parse range: Sheet1!A1:Z"}}

    class MetadataResponse:
        status_code = 200
        content = b"{}"
        text = "{}"

        def json(self):
            return {"sheets": [{"properties": {"title": "Trips"}}]}

    class ReadResponse:
        status_code = 200
        content = b"{}"
        text = "{}"

        def json(self):
            return {
                "range": "Trips!A1:C2",
                "values": [
                    ["date", "from", "to"],
                    ["2026-04-20", "Tallinn", "Airport"],
                ],
            }

    def fake_get(url, **kwargs):
        calls.append({"url": url, **kwargs})
        if "/values/Sheet1%21A1%3AZ" in url:
            return InvalidRangeResponse()
        if url.endswith("/spreadsheets/spreadsheet-1"):
            return MetadataResponse()
        return ReadResponse()

    monkeypatch.setattr(agent_google_sheets_adapter.requests, "get", fake_get)
    adapter = agent_google_sheets_adapter.GoogleSheetsAppendAdapter(
        {"token": "access-token", "scopes": [agent_google_sheets_adapter.SHEETS_SCOPE]}
    )

    result = adapter.read_rows(
        {
            "spreadsheet_id": "spreadsheet-1",
            "sheet_name": "Sheet1",
            "limit": 10,
        }
    )

    assert result["success"] is True
    assert result["sheet_name"] == "Trips"
    assert result["row_count"] == 1
    assert result["rows"][0]["from"] == "Tallinn"
    assert "/values/Trips%21A1%3AZ" in calls[-1]["url"]


def test_google_sheets_adapter_read_rows_refreshes_expired_access_token(monkeypatch):
    from services import agent_google_sheets_adapter

    calls = []

    class UnauthorizedResponse:
        status_code = 401
        content = b'{"error":"expired"}'
        text = '{"error":"expired"}'

        def json(self):
            return {"error": "expired"}

    class ReadResponse:
        status_code = 200
        content = b"{}"
        text = "{}"

        def json(self):
            return {
                "range": "Trips!A1:C2",
                "values": [
                    ["date", "from", "to"],
                    ["2022-04-20", "Tallinn", "Airport"],
                ],
            }

    class RefreshResponse:
        status_code = 200
        content = b"{}"
        text = "{}"

        def json(self):
            return {"access_token": "fresh-token"}

    def fake_get(url, **kwargs):
        calls.append({"method": "get", "url": url, **kwargs})
        if len([call for call in calls if call["method"] == "get"]) == 1:
            return UnauthorizedResponse()
        return ReadResponse()

    def fake_post(url, **kwargs):
        calls.append({"method": "post", "url": url, **kwargs})
        return RefreshResponse()

    monkeypatch.setattr(agent_google_sheets_adapter.requests, "get", fake_get)
    monkeypatch.setattr(agent_google_sheets_adapter.requests, "post", fake_post)
    adapter = agent_google_sheets_adapter.GoogleSheetsAppendAdapter(
        {
            "token": "expired-token",
            "refresh_token": "refresh-token",
            "client_id": "client-id",
            "client_secret": "client-secret",
            "token_uri": "https://oauth2.googleapis.com/token",
            "scopes": [agent_google_sheets_adapter.SHEETS_SCOPE],
        }
    )

    result = adapter.read_rows(
        {
            "spreadsheet_id": "spreadsheet-1",
            "sheet_name": "Trips",
            "limit": 10,
        }
    )

    get_calls = [call for call in calls if call["method"] == "get"]
    refresh_calls = [call for call in calls if call["method"] == "post"]
    assert result["success"] is True
    assert result["row_count"] == 1
    assert result["rows"][0]["from"] == "Tallinn"
    assert len(get_calls) == 2
    assert len(refresh_calls) == 1
    assert get_calls[0]["headers"]["Authorization"] == "Bearer expired-token"
    assert get_calls[1]["headers"]["Authorization"] == "Bearer fresh-token"
    assert refresh_calls[0]["data"]["refresh_token"] == "refresh-token"


def test_google_sheets_read_rows_capability_uses_native_provider(monkeypatch):
    from services import agent_capability_handlers

    class FakeReadAdapter:
        def read_rows(self, request):
            return {
                "success": True,
                "range": "Payments!A1:C3",
                "sheet_name": "Actual tab",
                "headers": ["date", "type", "amount"],
                "rows": [{"row_number": 2, "date": "2026-06-09", "type": "revenue", "amount": "12000"}],
                "row_count": 1,
            }

    db = FakeCapabilityDatabase()
    monkeypatch.setattr(agent_capability_handlers, "DatabaseManager", lambda: db)
    monkeypatch.setattr(
        agent_capability_handlers,
        "load_google_sheets_read_adapter",
        lambda cursor, business_id, integration_id="": FakeReadAdapter(),
    )

    result = agent_capability_handlers.build_capability_handlers()["google_sheets.read_rows"](
        {
            "tenant_id": "biz1",
            "actor": {"id": "user-1"},
            "capability": "google_sheets.read_rows",
            "payload": {
                "integration_id": "integration-1",
                "spreadsheet_id": "spreadsheet-1",
                "sheet_name": "Payments",
                "limit": 10,
            },
        },
        {"user_id": "user-1"},
    )

    payload = result["result"]
    assert payload["status"] == "read_completed"
    assert payload["provider_read_performed"] is True
    assert payload["source"] == "google_sheets"
    assert payload["sheet_name"] == "Actual tab"
    assert payload["count"] == 1
    assert payload["rows"][0]["amount"] == "12000"


def test_google_sheets_invalid_grant_marks_saved_account_for_reconnect(monkeypatch):
    from services import agent_capability_handlers
    from services.agent_google_sheets_adapter import GoogleSheetsAdapterError

    class Cursor:
        def __init__(self):
            self.calls = []

        def execute(self, query, params=None):
            self.calls.append((" ".join(query.split()).lower(), params))

    class Connection:
        def __init__(self):
            self.cursor_instance = Cursor()
            self.committed = False

        def cursor(self):
            return self.cursor_instance

        def commit(self):
            self.committed = True

    class Database:
        def __init__(self):
            self.conn = Connection()

        def close(self):
            return None

    class RevokedAdapter:
        def read_rows(self, _request):
            raise GoogleSheetsAdapterError(
                'Google token refresh failed with HTTP 400: {"error":"invalid_grant","error_description":"Token has been expired or revoked."}'
            )

    database = Database()
    monkeypatch.setattr(agent_capability_handlers, "DatabaseManager", lambda: database)
    monkeypatch.setattr(
        agent_capability_handlers,
        "load_google_sheets_read_adapter",
        lambda *_args, **_kwargs: RevokedAdapter(),
    )

    response = agent_capability_handlers.build_capability_handlers()["google_sheets.read_rows"](
        {
            "tenant_id": "biz1",
            "capability": "google_sheets.read_rows",
            "payload": {
                "integration_id": "integration-1",
                "spreadsheet_id": "spreadsheet-1",
                "sheet_name": "Trips",
            },
        },
        {"user_id": "user-1"},
    )

    payload = response["result"]
    update_call = next(call for call in database.conn.cursor_instance.calls if call[0].startswith("update externalbusinessaccounts"))
    assert payload["status"] == "provider_read_required"
    assert payload["next_action"] == "connect_or_repair_google_sheets_provider"
    assert "invalid_grant" in payload["provider_error_message"]
    assert update_call[1][1:] == ("biz1", "integration-1", "biz1", "integration-1")
    assert database.conn.committed is True


def test_google_sheets_missing_tab_is_not_reported_as_oauth_failure(monkeypatch):
    from services import agent_capability_handlers
    from services.agent_blueprint_workspace import _render_output
    from services.agent_google_sheets_adapter import GoogleSheetsAdapterError

    class MissingTabAdapter:
        def read_rows(self, _request):
            raise GoogleSheetsAdapterError(
                "Google Sheets read failed with HTTP 400: Unable to parse range: Missing tab!A1:Z"
            )

    db = FakeCapabilityDatabase()
    monkeypatch.setattr(agent_capability_handlers, "DatabaseManager", lambda: db)
    monkeypatch.setattr(
        agent_capability_handlers,
        "load_google_sheets_read_adapter",
        lambda *_args, **_kwargs: MissingTabAdapter(),
    )

    capability_result = agent_capability_handlers.build_capability_handlers()["google_sheets.read_rows"](
        {
            "tenant_id": "biz1",
            "capability": "google_sheets.read_rows",
            "payload": {
                "integration_id": "integration-1",
                "spreadsheet_id": "spreadsheet-1",
                "sheet_name": "Missing tab",
            },
        },
        {"user_id": "user-1"},
    )["result"]
    business_result = _render_output(
        "custom",
        {
            "workflow_description": "Открой таблицу поездок и подготовь сообщение владельцу",
            "processing_rules": "Не придумывать факты",
            "output_format": "Готовое сообщение для проверки",
        },
        [
            {
                "source_name": "google_sheets_error",
                "summary": capability_result["provider_error_message"],
                "raw": capability_result,
            }
        ],
        [],
        {},
    )

    assert capability_result["status"] == "provider_read_required"
    assert business_result["status"] == "needs_sheet_tab"
    assert business_result["title"] == "Нужно выбрать лист таблицы"
    assert "Переподключ" not in json.dumps(business_result, ensure_ascii=False)


def test_google_sheets_temporary_provider_error_is_raised_for_worker_retry(monkeypatch):
    from services import agent_capability_handlers
    from services.agent_google_sheets_adapter import GoogleSheetsAdapterError

    class Cursor:
        pass

    class Connection:
        def cursor(self):
            return Cursor()

    class Database:
        def __init__(self):
            self.conn = Connection()

        def close(self):
            return None

    class TemporaryFailureAdapter:
        def read_rows(self, _request):
            raise GoogleSheetsAdapterError("Google Sheets read failed with HTTP 503: backend unavailable")

    monkeypatch.setattr(agent_capability_handlers, "DatabaseManager", Database)
    monkeypatch.setattr(
        agent_capability_handlers,
        "load_google_sheets_read_adapter",
        lambda *_args, **_kwargs: TemporaryFailureAdapter(),
    )

    with pytest.raises(RuntimeError, match="temporary Google Sheets provider error"):
        agent_capability_handlers.build_capability_handlers()["google_sheets.read_rows"](
            {
                "tenant_id": "biz1",
                "capability": "google_sheets.read_rows",
                "payload": {
                    "integration_id": "integration-1",
                    "spreadsheet_id": "spreadsheet-1",
                    "sheet_name": "Trips",
                },
            },
            {"user_id": "user-1"},
        )


def test_agent_queue_treats_temporary_google_provider_error_as_retryable():
    from services.agent_run_queue import _is_transient_error

    assert _is_transient_error("temporary Google Sheets provider error: HTTP 503") is True


def test_source_result_chain_requires_real_google_sheets_provider_read():
    from services.agent_blueprint_runner import AgentBlueprintRunner

    runner = AgentBlueprintRunner(cursor=None)
    source_step = {
        "step_key": "read_google_sheets",
        "status": "completed",
        "output_json": {
            "capability": "google_sheets.read_rows",
            "orchestrator": {
                "result": {
                    "status": "read_completed",
                    "source": "inline_rows",
                    "provider_read_performed": False,
                    "rows": [{"row_number": 2, "title": "Preview order"}],
                }
            },
        },
    }
    artifacts = [
        {
            "artifact_type": "telegram_post_draft",
            "payload_json": {
                "result": {"draft_text": "Черновик из строки"},
                "items_used": 1,
            },
        }
    ]

    chain = runner._build_source_result_chain(
        [source_step],
        artifacts,
        {"items": [{"provider": "google_sheets", "status": "ready"}]},
    )

    assert chain["provider_read_attempted"] is True
    assert chain["provider_read_performed"] is False
    assert chain["external_source_verified"] is False
    assert chain["result_generated"] is True
    assert chain["chain_verified"] is False
    assert chain["blocker_code"] == "SOURCE_NOT_VERIFIED"


def test_source_result_chain_verifies_result_after_real_google_sheets_read():
    from services.agent_blueprint_runner import AgentBlueprintRunner

    runner = AgentBlueprintRunner(cursor=None)
    source_step = {
        "step_key": "read_google_sheets",
        "status": "completed",
        "output_json": {
            "capability": "google_sheets.read_rows",
            "orchestrator": {
                "result": {
                    "status": "read_completed",
                    "source": "google_sheets",
                    "provider_read_performed": True,
                    "rows": [{"row_number": 2, "title": "Real order"}],
                }
            },
        },
    }
    artifacts = [
        {
            "artifact_type": "telegram_post_draft",
            "payload_json": {
                "result": {"draft_text": "Черновик из строки таблицы"},
                "items_used": 1,
            },
        }
    ]

    chain = runner._build_source_result_chain(
        [source_step],
        artifacts,
        {"items": [{"provider": "google_sheets", "status": "ready"}]},
    )

    assert chain["provider_read_performed"] is True
    assert chain["external_source_verified"] is True
    assert chain["chain_verified"] is True
    assert chain["blocker_code"] == ""


def test_sheet_provider_executor_loads_adapter_from_agent_integration_and_applies(monkeypatch):
    from services import agent_sheet_provider_executor

    class FakeSheetsAdapter:
        def __init__(self):
            self.requests = []

        def append_row(self, request):
            self.requests.append(request)
            return {
                "success": True,
                "updated_range": "Leads!A2:C2",
                "updated_rows": 1,
            }

    adapter = FakeSheetsAdapter()
    requested = []

    def fake_load_adapter(cursor, *, business_id, integration_id=""):
        requested.append({"business_id": business_id, "integration_id": integration_id})
        return adapter

    monkeypatch.setattr(agent_sheet_provider_executor, "load_google_sheets_append_adapter", fake_load_adapter)
    cursor = FakeSheetProviderExecutorCursor()
    cursor.tables["agent_sheet_operation_requests"]["sheet-request-1"] = {
        "id": "sheet-request-1",
        "business_id": "biz1",
        "user_id": "user1",
        "action_id": "action-1",
        "status": "approved_for_execution",
        "approval_state": "approved",
        "apply_state": "provider_request_queued",
        "operation": "append_row",
        "integration_id": "integration-1",
        "spreadsheet_id": "spreadsheet-1",
        "sheet_name": "Leads",
        "row_values_json": ["2026-06-09T10:00:00Z", "anna", "Новая заявка"],
        "mapping_json": {},
        "source_event_json": {"trigger_event_id": "trigger-1"},
        "limits_json": {"daily_append_cap": 50},
        "provider_write_performed": False,
    }

    result = agent_sheet_provider_executor.execute_queued_sheet_provider_requests(
        cursor,
        business_id="biz1",
        user_id="operator1",
    )

    request = cursor.tables["agent_sheet_operation_requests"]["sheet-request-1"]
    assert requested == [{"business_id": "biz1", "integration_id": "integration-1"}]
    assert adapter.requests[0]["spreadsheet_id"] == "spreadsheet-1"
    assert result["provider_writes_performed"] is True
    assert request["status"] == "applied"
    assert request["apply_state"] == "applied"
    assert request["provider_write_performed"] is True


def test_sheet_provider_executor_applies_with_adapter_and_audit():
    from services.agent_sheet_provider_executor import execute_queued_sheet_provider_requests

    class FakeSheetsAdapter:
        def __init__(self):
            self.requests = []

        def append_row(self, request):
            self.requests.append(request)
            return {
                "success": True,
                "updated_range": "Leads!A2:C2",
                "updated_rows": 1,
                "access_token": "secret-token",
            }

    cursor = FakeSheetProviderExecutorCursor()
    cursor.tables["agent_sheet_operation_requests"]["sheet-request-1"] = {
        "id": "sheet-request-1",
        "business_id": "biz1",
        "user_id": "user1",
        "action_id": "action-1",
        "status": "approved_for_execution",
        "approval_state": "approved",
        "apply_state": "provider_request_queued",
        "operation": "append_row",
        "integration_id": "integration-1",
        "spreadsheet_id": "spreadsheet-1",
        "sheet_name": "Leads",
        "row_values_json": ["2026-06-09T10:00:00Z", "anna", "Новая заявка"],
        "mapping_json": {},
        "source_event_json": {"trigger_event_id": "trigger-1"},
        "limits_json": {"daily_append_cap": 50},
        "provider_write_performed": False,
    }
    adapter = FakeSheetsAdapter()

    result = execute_queued_sheet_provider_requests(cursor, business_id="biz1", user_id="operator1", adapter=adapter)

    request = cursor.tables["agent_sheet_operation_requests"]["sheet-request-1"]
    assert result["processed"] == 1
    assert result["provider_writes_performed"] is True
    assert adapter.requests[0]["row_values"] == ["2026-06-09T10:00:00Z", "anna", "Новая заявка"]
    assert request["status"] == "applied"
    assert request["apply_state"] == "applied"
    assert request["provider_write_performed"] is True
    assert cursor.ledger_entries[0]["status"] == "provider_applied"
    assert cursor.ledger_entries[0]["output_summary"]["provider_result"]["access_token"] == "[redacted]"


def test_approved_domain_executor_applies_service_optimization_to_localos_data():
    from services.agent_domain_request_executors import execute_approved_domain_requests

    cursor = FakeApprovedDomainExecutorCursor()
    cursor.tables["agent_service_optimization_requests"]["service-request-1"] = {
        "id": "service-request-1",
        "business_id": "biz1",
        "action_id": "action-services",
        "status": "approved_for_apply",
        "service_count": 1,
        "suggestions_json": [
            {
                "service_id": "svc1",
                "current_name": "Стрижка",
                "current_description": "Классическая стрижка",
                "proposed_name": "Стрижка · Парикмахерские услуги",
                "proposed_description": "Стрижка: кратко опишите результат услуги, длительность и кому она подходит.",
            }
        ],
        "diff_json": [],
        "apply_state": "apply_ready",
    }
    cursor.tables["userservices"]["svc1"] = {
        "id": "svc1",
        "business_id": "biz1",
        "name": "Стрижка",
        "description": "Классическая стрижка",
        "optimized_name": "",
        "optimized_description": "",
    }

    result = execute_approved_domain_requests(
        cursor,
        run={"id": "run1", "business_id": "biz1"},
        step={"key": "apply_services"},
        orchestrator_result={
            "action_id": "action-services",
            "result": {"request_id": "service-request-1"},
        },
        user_data={"user_id": "user1"},
    )

    request = cursor.tables["agent_service_optimization_requests"]["service-request-1"]
    service = cursor.tables["userservices"]["svc1"]
    assert result["executed"] == 1
    assert result["items"][0]["kind"] == "service_optimization_request"
    assert result["items"][0]["apply_state"] == "applied"
    assert result["items"][0]["applied_count"] == 1
    assert request["status"] == "applied"
    assert request["apply_state"] == "applied"
    assert service["optimized_name"] == "Стрижка · Парикмахерские услуги"
    assert service["optimized_description"].startswith("Стрижка:")
    assert cursor.ledger_entries[0]["capability"] == "services.optimize"
    assert cursor.ledger_entries[0]["metadata"]["provider_write_performed"] is False


def test_approved_domain_executor_creates_communication_delivery_journal_with_consent_gate():
    from services.agent_domain_request_executors import execute_approved_domain_requests

    cursor = FakeApprovedDomainExecutorCursor()
    cursor.tables["agent_communication_requests"]["comm-request-1"] = {
        "id": "comm-request-1",
        "business_id": "biz1",
        "action_id": "action-comm",
        "capability": "communications.send_offer",
        "message_type": "package_offer",
        "status": "approved_request",
        "channel": "telegram",
        "recipient_count": 2,
        "recipients_json": [
            {"client_id": "client-1", "client_name": "Anna", "consent": {"marketing": True}},
            {"client_id": "client-2", "client_name": "Boris", "consent": {"marketing": False}},
        ],
        "message_template": "Пакетное предложение",
        "limits_json": {"daily_cap": 10, "frequency_cap": "one_per_trigger"},
        "consent_json": {"required": True},
        "delivery_state": "not_dispatched",
    }

    result = execute_approved_domain_requests(
        cursor,
        run={"id": "run1", "business_id": "biz1"},
        step={"key": "send_offer"},
        orchestrator_result={
            "action_id": "action-comm",
            "result": {"request_id": "comm-request-1"},
        },
        user_data={"user_id": "user1"},
    )

    request = cursor.tables["agent_communication_requests"]["comm-request-1"]
    journal_rows = list(cursor.tables["agent_communication_delivery_journal"].values())
    assert result["executed"] == 1
    assert result["items"][0]["kind"] == "communication_request"
    assert result["items"][0]["queued_count"] == 1
    assert result["items"][0]["blocked_count"] == 1
    assert request["status"] == "approved_for_dispatch"
    assert request["delivery_state"] == "queued_for_dispatch"
    assert len(journal_rows) == 2
    assert {row["delivery_state"] for row in journal_rows} == {"queued_for_dispatch", "blocked_by_consent"}
    assert all(row["provider_write_performed"] is False for row in journal_rows)
    assert cursor.ledger_entries[0]["capability"] == "communications.send_offer"
    assert cursor.ledger_entries[0]["metadata"]["provider_write_performed"] is False


def test_approved_domain_executor_creates_review_provider_publish_request():
    from services.agent_domain_request_executors import execute_approved_domain_requests

    cursor = FakeApprovedDomainExecutorCursor()
    cursor.tables["reviewreplydrafts"]["draft-1"] = {
        "id": "draft-1",
        "review_id": "review-1",
        "business_id": "biz1",
        "status": "publish_requested",
        "source": "yandex",
        "generated_text": "Спасибо за отзыв!",
        "edited_text": "Спасибо за отзыв, будем рады видеть вас снова!",
        "tone": "friendly",
    }

    result = execute_approved_domain_requests(
        cursor,
        run={"id": "run1", "business_id": "biz1"},
        step={"key": "publish_review_reply"},
        orchestrator_result={
            "result": {"draft_id": "draft-1", "review_id": "review-1"},
        },
        user_data={"user_id": "user1"},
    )

    draft = cursor.tables["reviewreplydrafts"]["draft-1"]
    publish_requests = list(cursor.tables["agent_review_publish_requests"].values())
    assert result["executed"] == 1
    assert result["items"][0]["kind"] == "review_publish_request"
    assert result["items"][0]["publish_state"] == "provider_request_queued"
    assert draft["status"] == "approved_for_publish"
    assert len(publish_requests) == 1
    assert publish_requests[0]["draft_id"] == "draft-1"
    assert publish_requests[0]["review_id"] == "review-1"
    assert publish_requests[0]["status"] == "provider_publish_requested"
    assert publish_requests[0]["publish_state"] == "provider_request_queued"
    assert publish_requests[0]["provider_request_json"]["publish_mode"] == "controlled_request_only"
    assert publish_requests[0]["provider_write_performed"] is False
    assert cursor.ledger_entries[0]["capability"] == "reviews.reply.publish_request"
    assert cursor.ledger_entries[0]["status"] == "approved_pending_provider_executor"
    assert cursor.ledger_entries[0]["metadata"]["provider_write_performed"] is False


def test_telegram_trigger_runtime_records_ignored_event_when_no_custom_blueprint():
    from services.agent_trigger_runtime import dispatch_telegram_message_to_agent_blueprints

    cursor = FakeTelegramTriggerCursor()
    result = dispatch_telegram_message_to_agent_blueprints(
        cursor,
        "biz1",
        {
            "message_text": "Добавь заявку в таблицу",
            "telegram_user_id": "123",
            "telegram_username": "anna",
            "chat_id": "456",
            "message_id": "789",
            "received_at": "2026-06-09T10:00:00Z",
        },
    )

    assert result["success"] is True
    assert result["matched_count"] == 0
    assert result["legacy_reply_should_continue"] is True
    assert cursor.trigger_events[0]["status"] == "ignored"
    assert cursor.trigger_events[0]["reason_code"] == "NO_MATCHING_ACTIVE_BLUEPRINT"


def test_telegram_trigger_runtime_starts_active_custom_agent_and_waits_for_sheet_approval():
    from services.agent_blueprint_draft_builder import compile_agent_blueprint
    from services.agent_trigger_runtime import dispatch_telegram_message_to_agent_blueprints

    draft = compile_agent_blueprint("Когда пользователь пишет в Telegram бота, добавь строку в Google таблицу")
    payload = draft["version_payload"]
    cursor = FakeActiveTelegramTriggerCursor()
    cursor.tables["agent_blueprints"]["bp1"] = {
        "id": "bp1",
        "business_id": "biz1",
        "name": draft["name"],
        "category": "custom",
        "status": "active",
        "created_by_user_id": "user1",
        "metadata_json": {
            **draft["metadata"],
            "execution_mode": "scheduled",
            "active_version_id": "ver1",
            "custom_process": {
                **draft["metadata"]["custom_process"],
                "google_sheets": {
                    "integration_id": "integration-1",
                    "spreadsheet_id": "spreadsheet-1",
                    "sheet_name": "Leads",
                },
            },
        },
    }
    cursor.tables["agent_blueprint_versions"]["ver1"] = {
        "id": "ver1",
        "blueprint_id": "bp1",
        "version_number": 1,
        "goal": payload["goal"],
        "inputs_schema_json": payload["inputs_schema"],
        "steps_json": payload["steps"],
        "capability_allowlist_json": payload["capability_allowlist"],
        "approval_policy_json": payload["approval_policy"],
        "output_schema_json": payload["output_schema"],
        "created_by_user_id": "user1",
    }

    result = dispatch_telegram_message_to_agent_blueprints(
        cursor,
        "biz1",
        {
            "message_text": "Новая заявка: Анна",
            "telegram_user_id": "123",
            "telegram_username": "anna",
            "chat_id": "456",
            "message_id": "789",
            "received_at": "2026-06-09T10:00:00Z",
        },
    )

    run = next(iter(cursor.tables["agent_runs"].values()))
    approval = next(iter(cursor.tables["agent_approvals"].values()))
    assert result["success"] is True
    assert result["matched_count"] == 1
    assert result["legacy_reply_should_continue"] is False
    assert cursor.trigger_events[0]["status"] == "run_started"
    assert cursor.trigger_events[0]["run_id"] == run["id"]
    assert run["status"] == "waiting_approval"
    assert run["input_json"]["integration_id"] == "integration-1"
    assert run["input_json"]["spreadsheet_id"] == "spreadsheet-1"
    assert run["input_json"]["sheet_name"] == "Leads"
    assert approval["approval_type"] == "sheet_update"
    assert approval["status"] == "pending"


def test_scheduled_trigger_runtime_blocks_when_required_sheet_connection_missing(monkeypatch):
    from services.agent_blueprint_draft_builder import compile_agent_blueprint
    from services.agent_trigger_runtime import dispatch_scheduled_agent_blueprints

    monkeypatch.setenv("AGENT_ASYNC_RUNS_ENABLED", "true")
    monkeypatch.setenv("AGENT_BETA_BUSINESS_IDS", "biz1")

    draft = compile_agent_blueprint(
        "Каждый вечер прочитай новые строки Google Sheets и подготовь результат"
    )
    payload = draft["version_payload"]
    cursor = FakeActiveTelegramTriggerCursor()
    cursor.tables["agent_blueprints"]["bp1"] = {
        "id": "bp1",
        "business_id": "biz1",
        "name": draft["name"],
        "category": "custom",
        "status": "active",
        "created_by_user_id": "user1",
        "metadata_json": {
            **draft["metadata"],
            "execution_mode": "scheduled",
            "active_version_id": "ver1",
        },
    }
    cursor.tables["agent_blueprint_versions"]["ver1"] = {
        "id": "ver1",
        "blueprint_id": "bp1",
        "version_number": 1,
        "goal": payload["goal"],
        "inputs_schema_json": payload["inputs_schema"],
        "steps_json": payload["steps"],
        "capability_allowlist_json": payload["capability_allowlist"],
        "approval_policy_json": payload["approval_policy"],
        "output_schema_json": payload["output_schema"],
        "created_by_user_id": "user1",
    }

    result = dispatch_scheduled_agent_blueprints(cursor, "biz1")

    assert result["success"] is True
    assert result["matched_count"] == 0
    assert result["legacy_reply_should_continue"] is False
    assert result["skipped"][0]["reason"] == "AGENT_INTEGRATIONS_REQUIRED"
    assert result["skipped"][0]["preflight"]["missing"][0]["provider"] == "google_sheets"
    assert cursor.tables["agent_runs"] == {}
    assert cursor.trigger_events[0]["source"] == "scheduler"
    assert cursor.trigger_events[0]["event_type"] == "schedule.daily"
    assert cursor.trigger_events[0]["status"] == "ignored"


def test_scheduled_trigger_runtime_starts_active_safe_agent_outside_legacy_categories(monkeypatch):
    from services import agent_trigger_runtime

    monkeypatch.setenv("AGENT_ASYNC_RUNS_ENABLED", "true")
    monkeypatch.setenv("AGENT_BETA_BUSINESS_IDS", "biz1")
    monkeypatch.setattr(agent_trigger_runtime, "enqueue_agent_run", _fake_scheduled_enqueue)

    cursor = FakeActiveTelegramTriggerCursor()
    cursor.tables["agent_blueprints"]["bp1"] = {
        "id": "bp1",
        "business_id": "biz1",
        "name": "Ежедневная сверка",
        "category": "reviews",
        "status": "active",
        "created_by_user_id": "user1",
        "metadata_json": {
            "execution_mode": "scheduled",
            "active_version_id": "ver1",
            "required_integration_bindings": [],
            "custom_process": {
                "kind": "source_destination_workflow",
                "trigger": "schedule.daily",
                    "schedule": {"frequency": "daily", "time": "19:00", "timezone": "Europe/Moscow"},
            },
        },
    }
    cursor.tables["agent_blueprint_versions"]["ver1"] = {
        "id": "ver1",
        "blueprint_id": "bp1",
        "version_number": 1,
        "goal": "Проверить ежедневный запуск",
        "inputs_schema_json": {"trigger": "schedule.daily"},
        "steps_json": [],
        "capability_allowlist_json": [],
        "approval_policy_json": {},
        "output_schema_json": {"trigger": "schedule.daily"},
        "created_by_user_id": "user1",
    }

    result = agent_trigger_runtime.dispatch_scheduled_agent_blueprints(cursor, "biz1")

    run = next(iter(cursor.tables["agent_runs"].values()))
    assert result["success"] is True
    assert result["matched_count"] == 1
    assert result["started_runs"][0]["run_status"] == "queued"
    assert cursor.trigger_events[0]["status"] == "run_started"
    assert cursor.trigger_events[0]["run_id"] == run["id"]
    assert run["status"] == "queued"
    assert run["input_json"]["preview_mode"] is False
    assert run["input_json"]["trigger"] == "schedule.daily"
    assert run["input_json"]["source_event"]["source"] == "scheduler"


def test_due_scheduler_skips_capability_that_is_not_beta_enabled():
    from services.agent_trigger_runtime import dispatch_due_scheduled_agent_blueprints

    cursor = FakeActiveTelegramTriggerCursor()
    cursor.tables["agent_blueprints"]["bp1"] = {
        "id": "bp1",
        "business_id": "biz1",
        "name": "Небезопасное напоминание",
        "category": "communications",
        "status": "active",
        "created_by_user_id": "user1",
        "metadata_json": {
            "execution_mode": "scheduled",
            "active_version_id": "ver1",
            "custom_process": {"trigger": "schedule.daily", "schedule": {"time": "09:00", "timezone": "UTC"}},
        },
    }
    cursor.tables["agent_blueprint_versions"]["ver1"] = {
        "id": "ver1",
        "blueprint_id": "bp1",
        "version_number": 1,
        "steps_json": [{"key": "send", "type": "capability", "capability": "communications.send_reminder"}],
        "capability_allowlist_json": ["communications.send_reminder"],
        "output_schema_json": {"trigger": "schedule.daily"},
    }

    result = dispatch_due_scheduled_agent_blueprints(
        cursor,
        now=datetime(2026, 6, 10, 9, 5, tzinfo=timezone.utc),
    )

    assert result["dispatched_count"] == 0
    assert result["skipped"][0]["reason"] == "capability_not_beta_enabled"
    assert cursor.tables["agent_runs"] == {}


def test_due_scheduled_trigger_dispatcher_runs_each_business_once_per_day(monkeypatch):
    from services import agent_trigger_runtime

    monkeypatch.setenv("AGENT_ASYNC_RUNS_ENABLED", "true")
    monkeypatch.setenv("AGENT_BETA_BUSINESS_IDS", "biz1")
    monkeypatch.setattr(agent_trigger_runtime, "enqueue_agent_run", _fake_scheduled_enqueue)

    cursor = FakeActiveTelegramTriggerCursor()
    cursor.tables["agent_blueprints"]["bp1"] = {
        "id": "bp1",
        "business_id": "biz1",
        "name": "Ежедневная сверка",
        "category": "custom",
        "status": "active",
        "created_by_user_id": "user1",
        "metadata_json": {
            "execution_mode": "scheduled",
            "active_version_id": "ver1",
            "required_integration_bindings": [],
            "custom_process": {
                "kind": "source_destination_workflow",
                "trigger": "schedule.daily",
                "schedule": {"frequency": "daily", "time": "19:00", "timezone": "Europe/Moscow"},
            },
        },
    }
    cursor.tables["agent_blueprint_versions"]["ver1"] = {
        "id": "ver1",
        "blueprint_id": "bp1",
        "version_number": 1,
        "goal": "Проверить ежедневный запуск",
        "inputs_schema_json": {"trigger": "schedule.daily"},
        "steps_json": [],
        "capability_allowlist_json": [],
        "approval_policy_json": {},
        "output_schema_json": {"trigger": "schedule.daily"},
        "created_by_user_id": "user1",
    }

    first = agent_trigger_runtime.dispatch_due_scheduled_agent_blueprints(
        cursor,
        now=datetime(2026, 6, 10, 19, 5, tzinfo=timezone.utc),
    )
    second = agent_trigger_runtime.dispatch_due_scheduled_agent_blueprints(
        cursor,
        now=datetime(2026, 6, 10, 19, 10, tzinfo=timezone.utc),
    )

    assert first["dispatched_count"] == 1
    assert first["dispatched"][0]["blueprint_id"] == "bp1"
    assert first["dispatched"][0]["run_id"]
    assert next(iter(cursor.tables["agent_runs"].values()))["input_json"]["preview_mode"] is False
    assert second["dispatched_count"] == 0
    assert second["skipped"][0]["reason"] == "already_recorded_for_schedule"
    assert len(cursor.tables["agent_runs"]) == 1


def test_due_scheduler_retries_slot_deferred_by_parallel_run(monkeypatch):
    from services import agent_trigger_runtime

    monkeypatch.setenv("AGENT_ASYNC_RUNS_ENABLED", "true")
    monkeypatch.setenv("AGENT_BETA_BUSINESS_IDS", "biz1")
    attempts = []

    def enqueue_with_temporary_conflict(cursor, *, blueprint, version, input_payload, user_data, idempotency_key):
        attempts.append(idempotency_key)
        if len(attempts) == 1:
            return {
                "success": False,
                "code": "AGENT_RUN_ALREADY_IN_PROGRESS",
                "error": "agent run already in progress",
            }
        return _fake_scheduled_enqueue(
            cursor,
            blueprint=blueprint,
            version=version,
            input_payload=input_payload,
            user_data=user_data,
            idempotency_key=idempotency_key,
        )

    monkeypatch.setattr(agent_trigger_runtime, "enqueue_agent_run", enqueue_with_temporary_conflict)
    cursor = FakeActiveTelegramTriggerCursor()
    cursor.tables["agent_blueprints"]["bp1"] = {
        "id": "bp1",
        "business_id": "biz1",
        "name": "Ежедневная сверка",
        "category": "custom",
        "status": "active",
        "created_by_user_id": "user1",
        "metadata_json": {
            "execution_mode": "scheduled",
            "active_version_id": "ver1",
            "custom_process": {
                "trigger": "schedule.daily",
                "schedule": {"time": "19:00", "timezone": "Europe/Moscow"},
            },
        },
    }
    cursor.tables["agent_blueprint_versions"]["ver1"] = {
        "id": "ver1",
        "blueprint_id": "bp1",
        "version_number": 1,
        "steps_json": [],
        "output_schema_json": {"trigger": "schedule.daily"},
    }

    first = agent_trigger_runtime.dispatch_due_scheduled_agent_blueprints(
        cursor,
        now=datetime(2026, 6, 10, 19, 5, tzinfo=timezone.utc),
    )
    second = agent_trigger_runtime.dispatch_due_scheduled_agent_blueprints(
        cursor,
        now=datetime(2026, 6, 10, 19, 10, tzinfo=timezone.utc),
    )

    assert first["dispatched_count"] == 0
    assert first["skipped"][0]["reason"] == "AGENT_RUN_ALREADY_IN_PROGRESS"
    assert cursor.trigger_events[0]["status"] == "deferred"
    assert second["dispatched_count"] == 1
    assert cursor.trigger_events[1]["status"] == "run_started"
    assert len(cursor.tables["agent_runs"]) == 1
    assert attempts[0] == attempts[1]


def test_due_scheduled_trigger_dispatcher_waits_until_schedule_time():
    from services.agent_trigger_runtime import dispatch_due_scheduled_agent_blueprints

    cursor = FakeActiveTelegramTriggerCursor()
    cursor.tables["agent_blueprints"]["bp1"] = {
        "id": "bp1",
        "business_id": "biz1",
        "name": "Ежедневная сверка",
        "category": "custom",
        "status": "active",
        "created_by_user_id": "user1",
        "metadata_json": {
            "execution_mode": "scheduled",
            "active_version_id": "ver1",
            "required_integration_bindings": [],
            "custom_process": {
                "trigger": "schedule.daily",
                "schedule": {"frequency": "daily", "time": "19:00", "timezone": "UTC"},
            },
        },
    }
    cursor.tables["agent_blueprint_versions"]["ver1"] = {
        "id": "ver1",
        "blueprint_id": "bp1",
        "version_number": 1,
        "steps_json": [],
        "output_schema_json": {"trigger": "schedule.daily"},
    }

    result = dispatch_due_scheduled_agent_blueprints(
        cursor,
        now=datetime(2026, 6, 10, 18, 59, tzinfo=timezone.utc),
    )

    assert result["checked_businesses"] == 1
    assert result["dispatched_count"] == 0
    assert cursor.tables["agent_runs"] == {}


def test_scheduler_uses_iana_timezone_for_due_time():
    from services.agent_trigger_runtime import _schedule_context, _schedule_is_due

    blueprint = {
        "metadata_json": {
            "custom_process": {
                "schedule": {"time": "17:50", "timezone": "Europe/Tallinn"},
            },
        },
    }
    version = {"output_schema_json": {}}
    before = datetime(2026, 7, 20, 14, 49, tzinfo=timezone.utc)
    due = datetime(2026, 7, 20, 14, 50, tzinfo=timezone.utc)

    assert _schedule_context(blueprint, version, before)["due"] is False
    context = _schedule_context(blueprint, version, due)
    assert context["due"] is True
    assert context["schedule_date"] == "2026-07-20"
    assert context["local_now"].startswith("2026-07-20T17:50:00")
    assert _schedule_is_due({"time": "17:50", "timezone": "Europe/Tallinn"}, before) is False
    assert _schedule_is_due({"time": "17:50", "timezone": "Europe/Tallinn"}, due) is True


def test_scheduler_starts_next_day_when_activated_after_local_slot():
    from services.agent_trigger_runtime import _schedule_context

    blueprint = {
        "metadata_json": {
            "active_version_updated_at": "2026-07-20T15:05:00Z",
            "execution_mode_confirmed_at": "2026-07-20T15:00:00Z",
            "custom_process": {
                "schedule": {"time": "17:50", "timezone": "Europe/Tallinn"},
            },
        },
    }

    context = _schedule_context(
        blueprint,
        {"output_schema_json": {}},
        datetime(2026, 7, 20, 15, 10, tzinfo=timezone.utc),
    )

    assert context["ready"] is True
    assert context["due"] is False
    assert context["reason"] == "schedule_starts_next_day"


def test_scheduler_catches_up_after_restart_when_enabled_before_slot():
    from services.agent_trigger_runtime import _schedule_context

    blueprint = {
        "metadata_json": {
            "active_version_updated_at": "2026-07-20T12:00:00Z",
            "execution_mode_confirmed_at": "2026-07-20T12:05:00Z",
            "custom_process": {
                "schedule": {"time": "17:50", "timezone": "Europe/Tallinn"},
            },
        },
    }

    context = _schedule_context(
        blueprint,
        {"output_schema_json": {}},
        datetime(2026, 7, 20, 15, 10, tzinfo=timezone.utc),
    )

    assert context["ready"] is True
    assert context["due"] is True


def test_scheduler_rejects_invalid_timezones_and_times():
    from services.agent_trigger_runtime import _schedule_context, _schedule_is_due

    invalid_timezone = {
        "metadata_json": {
            "custom_process": {"schedule": {"time": "17:50", "timezone": "Mars/Olympus"}},
        },
    }
    invalid_time = {
        "metadata_json": {
            "custom_process": {"schedule": {"time": "29:90", "timezone": "Europe/Tallinn"}},
        },
    }
    now = datetime(2026, 7, 20, 15, 10, tzinfo=timezone.utc)

    assert _schedule_context(invalid_timezone, {"output_schema_json": {}}, now)["reason"] == "schedule_timezone_invalid"
    assert _schedule_context(invalid_time, {"output_schema_json": {}}, now)["reason"] == "schedule_time_invalid"
    assert _schedule_is_due({"time": "17:50", "timezone": "Mars/Olympus"}, now) is False
    assert _schedule_is_due({"time": "29:90", "timezone": "Europe/Tallinn"}, now) is False


def test_due_scheduler_runs_two_blueprints_for_same_business(monkeypatch):
    from services import agent_trigger_runtime

    monkeypatch.setenv("AGENT_ASYNC_RUNS_ENABLED", "true")
    monkeypatch.setenv("AGENT_BETA_BUSINESS_IDS", "biz1")
    monkeypatch.setattr(agent_trigger_runtime, "enqueue_agent_run", _fake_scheduled_enqueue)

    cursor = FakeActiveTelegramTriggerCursor()
    for index, schedule_time in enumerate(["09:00", "10:00"], start=1):
        blueprint_id = f"bp{index}"
        version_id = f"ver{index}"
        cursor.tables["agent_blueprints"][blueprint_id] = {
            "id": blueprint_id,
            "business_id": "biz1",
            "name": f"Scheduled {index}",
            "category": "custom",
            "status": "active",
            "created_by_user_id": "user1",
            "metadata_json": {
                "execution_mode": "scheduled",
                "active_version_id": version_id,
                "required_integration_bindings": [],
                "custom_process": {
                    "trigger": "schedule.daily",
                    "schedule": {"time": schedule_time, "timezone": "Europe/Tallinn"},
                },
            },
        }
        cursor.tables["agent_blueprint_versions"][version_id] = {
            "id": version_id,
            "blueprint_id": blueprint_id,
            "version_number": 1,
            "steps_json": [],
            "output_schema_json": {"trigger": "schedule.daily"},
        }

    result = agent_trigger_runtime.dispatch_due_scheduled_agent_blueprints(
        cursor,
        now=datetime(2026, 7, 10, 8, 5, tzinfo=timezone.utc),
    )

    assert result["checked_businesses"] == 1
    assert result["checked_blueprints"] == 2
    assert result["dispatched_count"] == 2
    assert {item["blueprint_id"] for item in result["dispatched"]} == {"bp1", "bp2"}
    assert len(cursor.tables["agent_runs"]) == 2


def test_due_scheduler_skips_business_outside_async_beta(monkeypatch):
    from services import agent_trigger_runtime

    monkeypatch.setenv("AGENT_ASYNC_RUNS_ENABLED", "true")
    monkeypatch.setenv("AGENT_BETA_BUSINESS_IDS", "other-business")
    cursor = FakeActiveTelegramTriggerCursor()
    cursor.tables["agent_blueprints"]["bp1"] = {
        "id": "bp1",
        "business_id": "biz1",
        "name": "Ежедневная сверка",
        "category": "custom",
        "status": "active",
        "created_by_user_id": "user1",
        "metadata_json": {
            "execution_mode": "scheduled",
            "active_version_id": "ver1",
            "custom_process": {
                "trigger": "schedule.daily",
                "schedule": {"time": "09:00", "timezone": "UTC"},
            },
        },
    }
    cursor.tables["agent_blueprint_versions"]["ver1"] = {
        "id": "ver1",
        "blueprint_id": "bp1",
        "steps_json": [],
        "output_schema_json": {"trigger": "schedule.daily"},
    }

    result = agent_trigger_runtime.dispatch_due_scheduled_agent_blueprints(
        cursor,
        now=datetime(2026, 6, 10, 9, 5, tzinfo=timezone.utc),
    )

    assert result["dispatched_count"] == 0
    assert result["skipped"][0]["reason"] == "async_runtime_not_enabled_for_business"
    assert cursor.tables["agent_runs"] == {}


def _fake_scheduled_enqueue(cursor, *, blueprint, version, input_payload, user_data, idempotency_key):
    run_id = f"queued-{blueprint['id']}"
    run = {
        "id": run_id,
        "blueprint_id": blueprint["id"],
        "blueprint_version_id": version["id"],
        "business_id": blueprint["business_id"],
        "status": "queued",
        "input_json": input_payload,
        "created_by_user_id": user_data["user_id"],
        "idempotency_key": idempotency_key,
    }
    cursor.tables["agent_runs"][run_id] = run
    return {"success": True, "run": run, "reused": False}
