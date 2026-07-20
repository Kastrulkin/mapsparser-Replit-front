import json
from datetime import datetime, timezone
from pathlib import Path

from tests.agent_blueprint_fakes import *  # noqa: F403


def test_run_business_result_prefers_final_artifact():
    from services.agent_blueprint_runner import AgentBlueprintRunner

    cursor = FakeCursor()
    cursor.tables["agent_runs"]["run1"] = {
        "id": "run1",
        "blueprint_id": "bp1",
        "blueprint_version_id": "ver1",
        "business_id": "biz1",
        "status": "completed",
        "input_json": {},
        "output_json": {},
    }
    cursor.tables["agent_artifacts"]["draft"] = {
        "id": "draft",
        "run_id": "run1",
        "step_id": "step1",
        "artifact_type": "agent_output_draft",
        "title": "Draft",
        "payload_json": {"result": {"draft_text": "old draft"}},
    }
    cursor.tables["agent_artifacts"]["final"] = {
        "id": "final",
        "run_id": "run1",
        "step_id": "step2",
        "artifact_type": "agent_final_result",
        "title": "Final",
        "payload_json": {
            "result": {"draft_text": "saved final"},
            "saved_destination": {
                "status": "draft_saved",
                "plan_id": "plan-1",
                "item_id": "item-1",
                "content_plan_url": "/dashboard/content?plan_id=plan-1",
                "localos_write_performed": True,
            },
        },
    }

    run = AgentBlueprintRunner(cursor).load_run("run1")

    assert run["business_result"]["draft_text"] == "saved final"
    assert run["business_result"]["saved_destination"]["status"] == "draft_saved"
    assert run["business_result"]["saved_destination"]["content_plan_url"] == "/dashboard/content?plan_id=plan-1"
    assert run["result_state"] == "saved"


def test_new_run_supersedes_old_pending_approval():
    from services.agent_blueprint_runner import AgentBlueprintRunner

    cursor = FakeCursor()
    cursor.tables["agent_blueprints"]["bp1"] = {
        "id": "bp1",
        "business_id": "biz1",
        "status": "draft",
        "metadata_json": {"required_integration_bindings": []},
    }
    cursor.tables["agent_blueprint_versions"]["ver1"] = {
        "id": "ver1",
        "blueprint_id": "bp1",
        "version_number": 1,
        "steps_json": [],
    }
    cursor.tables["agent_runs"]["old"] = {
        "id": "old",
        "blueprint_id": "bp1",
        "blueprint_version_id": "ver1",
        "business_id": "biz1",
        "status": "waiting_approval",
        "input_json": {},
        "output_json": {},
    }
    cursor.tables["agent_approvals"]["approval-old"] = {
        "id": "approval-old",
        "run_id": "old",
        "step_id": "approval-step",
        "status": "pending",
        "approval_type": "final_output",
        "title": "Old approval",
        "payload_json": {},
    }

    result = AgentBlueprintRunner(cursor).start_run("ver1", {"preview_mode": True}, {"user_id": "user1"})

    assert result["success"] is True
    assert cursor.tables["agent_approvals"]["approval-old"]["status"] == "superseded"
    assert cursor.tables["agent_runs"]["old"]["status"] == "superseded"


def test_content_plan_draft_capability_preview_and_past_date_do_not_write():
    from services.agent_capability_handlers import _handle_content_plan_item_create_draft

    preview = _handle_content_plan_item_create_draft(
        {
            "tenant_id": "biz1",
            "trace_id": "run1",
            "payload": {
                "preview_mode": True,
                "scheduled_for": "2099-07-27",
                "draft_text": "Prepared post",
                "theme": "Trip",
            },
        },
        {"user_id": "user1"},
    )["result"]
    past = _handle_content_plan_item_create_draft(
        {
            "tenant_id": "biz1",
            "trace_id": "run2",
            "payload": {
                "scheduled_for": "2020-01-01",
                "draft_text": "Prepared post",
                "theme": "Trip",
            },
        },
        {"user_id": "user1"},
    )["result"]

    assert preview["status"] == "preview_ready"
    assert preview["localos_write_performed"] is False
    assert past["status"] == "needs_future_date"
    assert past["reason_code"] == "CONTENT_PLAN_DATE_IN_PAST"
    assert past["localos_write_performed"] is False


def test_legacy_final_output_approval_is_skipped_for_internal_result():
    from services.agent_blueprint_runner import AgentBlueprintRunner

    cursor = FakeCursor()
    cursor.tables["agent_blueprints"]["bp1"] = {
        "id": "bp1",
        "business_id": "biz1",
        "status": "draft",
        "metadata_json": {"required_integration_bindings": []},
    }
    cursor.tables["agent_blueprint_versions"]["ver1"] = {
        "id": "ver1",
        "blueprint_id": "bp1",
        "version_number": 1,
        "steps_json": [
            {"key": "draft", "type": "artifact", "artifact_type": "agent_output_draft"},
            {"key": "approve", "type": "approval", "approval_type": "final_output"},
            {"key": "final", "type": "artifact", "artifact_type": "agent_final_result"},
        ],
    }

    result = AgentBlueprintRunner(cursor).start_run("ver1", {"preview_mode": True}, {"user_id": "user1"})

    assert result["success"] is True
    assert result["run"]["status"] == "completed"
    assert cursor.tables["agent_approvals"] == {}


def test_content_plan_draft_capability_is_idempotent(monkeypatch):
    from services import agent_capability_handlers

    class ContentPlanCursor:
        def __init__(self):
            self.plan_id = ""
            self.items = {}
            self.fetchone_value = None

        def execute(self, query, params=None):
            normalized = " ".join(query.split()).lower()
            params = params or ()
            if normalized.startswith("select id from contentplans"):
                self.fetchone_value = {"id": self.plan_id} if self.plan_id else None
            elif normalized.startswith("insert into contentplans"):
                self.plan_id = str(params[0])
                self.fetchone_value = None
            elif normalized.startswith("insert into contentplanitems"):
                self.items[str(params[0])] = {"plan_id": params[1], "draft_text": params[8]}
                self.fetchone_value = None
            else:
                raise AssertionError(f"Unhandled content-plan SQL: {query}")

        def fetchone(self):
            return self.fetchone_value

    class ContentPlanConnection:
        def __init__(self):
            self.cursor_value = ContentPlanCursor()

        def cursor(self):
            return self.cursor_value

        def commit(self):
            return None

        def rollback(self):
            return None

    connection = ContentPlanConnection()

    class ContentPlanDatabase:
        def __init__(self):
            self.conn = connection

        def close(self):
            return None

    monkeypatch.setattr(agent_capability_handlers, "DatabaseManager", ContentPlanDatabase)
    monkeypatch.setattr(agent_capability_handlers, "ensure_content_plan_tables", lambda _cursor: None)
    envelope = {
        "tenant_id": "biz1",
        "trace_id": "run1",
        "payload": {
            "scheduled_for": "2099-07-27",
            "draft_text": "Prepared post",
            "theme": "Trip",
            "source_run_id": "run1",
        },
    }

    first = agent_capability_handlers._handle_content_plan_item_create_draft(envelope, {"user_id": "user1"})["result"]
    second = agent_capability_handlers._handle_content_plan_item_create_draft(envelope, {"user_id": "user1"})["result"]

    assert first["status"] == "draft_saved"
    assert second["item_id"] == first["item_id"]
    assert len(connection.cursor_value.items) == 1


def test_execution_modes_and_scheduled_next_run_are_explicit():
    from api.agent_blueprints_api import _agent_execution_mode, _agent_schedule_status

    one_off = {"metadata_json": {"execution_mode": "one_off"}}
    manual = {"metadata_json": {"execution_mode": "manual", "custom_process": {"trigger": "manual.run"}}}
    scheduled = {
        "metadata_json": {
            "execution_mode": "scheduled",
            "custom_process": {
                "trigger": "schedule.daily",
                "schedule": {"time": "09:30", "timezone": "Europe/Tallinn"},
            },
        }
    }

    assert _agent_execution_mode(one_off) == "one_off"
    assert _agent_execution_mode(manual) == "manual"
    assert _agent_execution_mode(scheduled) == "scheduled"
    schedule_status = _agent_schedule_status(scheduled)
    assert schedule_status["ready"] is True
    assert schedule_status["timezone"] == "Europe/Tallinn"
    assert schedule_status["next_run_at"]


def test_activate_version_marks_blueprint_active_for_trigger_runtime(monkeypatch):
    from api import agent_blueprints_api

    class ActivationCursor:
        def __init__(self):
            self.metadata = {}
            self.status = "draft"

        def execute(self, query, params=None):
            normalized_query = " ".join(query.split()).lower()
            params = params or ()
            if normalized_query.startswith("update agent_blueprints") and "set metadata_json" in normalized_query:
                self.metadata = json.loads(params[0])
                return None
            if normalized_query.startswith("update agent_blueprints") and "set status = 'active'" in normalized_query:
                self.status = "active"
                return None
            raise AssertionError(f"Unhandled activation SQL: {query}")

    cursor = ActivationCursor()
    blueprint = {"id": "bp1", "metadata_json": {"version_events": []}, "status": "draft"}
    version = {"id": "ver1", "version_number": 1}
    monkeypatch.setattr(agent_blueprints_api, "_load_blueprint", lambda _cursor, _blueprint_id: blueprint)

    event = agent_blueprints_api._remember_active_version(
        cursor,
        blueprint,
        version,
        {"user_id": "user1"},
        "activated",
        "ready for telegram trigger",
    )

    assert event["active_version_id"] == "ver1"
    assert cursor.metadata["active_version_id"] == "ver1"
    assert cursor.status == "active"


def test_agent_integration_binding_status_tracks_required_compiled_bindings():
    from api import agent_blueprints_api

    metadata = {
        "execution_mode": "manual",
        "required_integration_bindings": [
            {"key": "telegram_trigger", "provider": "telegram", "direction": "trigger", "trigger": "telegram.message.received"},
            {
                "key": "google_sheets_append",
                "provider": "google_sheets",
                "direction": "external_write",
                "capability": "sheets.append_row_request",
                "required_config": ["spreadsheet_id", "sheet_name"],
            },
        ],
        "agent_binding_integrations": {
            "google_sheets_append": {
                "answer_config": {"spreadsheet_id": "spreadsheet-1", "sheet_name": "Leads"},
            }
        },
    }
    rows = [
        {
            "id": "telegram-1",
            "provider": "telegram",
            "status": "active",
            "config_json": {"bot_mode": "business_bot"},
        },
        {
            "id": "sheets-1",
            "provider": "google_sheets",
            "status": "active",
            "config_json": {"spreadsheet_id": "spreadsheet-1", "sheet_name": "Leads"},
        },
    ]

    status = agent_blueprints_api._agent_integration_binding_status(metadata, rows)

    assert [item["status"] for item in status] == ["connected", "connected"]
    assert status[1]["integration_id"] == "sheets-1"
    assert status[1]["missing_config"] == []
    assert status[1]["answer_config"]["sheet_name"] == "Leads"


def test_agent_integration_binding_status_treats_localos_finance_as_native_ready():
    from api import agent_blueprints_api

    metadata = {
        "required_integration_bindings": [
            {
                "key": "localos_finance",
                "provider": "localos_finance",
                "direction": "localos_write_request",
                "capability": "finance.transaction.create",
                "required_config": ["transaction_type"],
            },
        ]
    }

    status = agent_blueprints_api._agent_integration_binding_status(metadata, [])

    assert status[0]["status"] == "connected"
    assert status[0]["integration_id"] == "native_localos"
    assert status[0]["resolution"] == "native_localos"
    assert status[0]["missing_config"] == []


def test_agent_integration_binding_status_treats_business_profile_as_native_ready():
    from api import agent_blueprints_api

    metadata = {
        "required_integration_bindings": [
            {
                "key": "business_reviews_context",
                "provider": "business_profile",
                "direction": "local_context",
                "required_config": [],
            },
        ]
    }

    status = agent_blueprints_api._agent_integration_binding_status(metadata, [])

    assert status[0]["status"] == "connected"
    assert status[0]["integration_id"] == "native_localos"
    assert status[0]["resolution"] == "native_localos"
    assert status[0]["missing_config"] == []


def test_agent_preflight_treats_business_profile_as_native_ready():
    from services.agent_integration_preflight import build_agent_integration_preflight

    class Cursor:
        def execute(self, query, params=None):
            assert "from agent_integrations" in " ".join(query.split()).lower()

        def fetchall(self):
            return []

    metadata = {
        "required_integration_bindings": [
            {
                "key": "business_reviews_context",
                "provider": "business_profile",
                "direction": "local_context",
                "required": True,
                "required_config": [],
            },
        ]
    }

    preflight = build_agent_integration_preflight(Cursor(), business_id="biz1", metadata=metadata, input_payload={})

    assert preflight["ready"] is True
    assert preflight["missing_count"] == 0
    assert preflight["items"][0]["status"] == "ready"
    assert preflight["items"][0]["resolution"] == "native_localos"


def test_direct_agent_draft_auto_selects_single_connection_and_requires_ambiguous_choice():
    from api import agent_blueprints_api

    preview = {
        "connection_summary": {
            "items": [
                {
                    "key": "telegram_delivery",
                    "provider": "telegram",
                    "title": "Telegram",
                    "action": "choose_existing",
                    "connections": [{"id": "tg1", "display_name": "Бот бизнеса"}],
                },
                {
                    "key": "google_sheets_read",
                    "provider": "google_sheets",
                    "title": "Google Sheets",
                    "action": "choose_existing",
                    "connections": [
                        {"id": "sheet1", "display_name": "Orders"},
                        {"id": "sheet2", "display_name": "Archive"},
                    ],
                },
            ]
        }
    }
    inventory = [
        {"id": "tg1", "provider": "telegram", "display_name": "Бот бизнеса", "config": {"bot_mode": "business_bot"}},
        {"id": "sheet1", "provider": "google_sheets", "display_name": "Orders", "config": {"sheet_name": "Sheet1"}},
        {"id": "sheet2", "provider": "google_sheets", "display_name": "Archive", "config": {"sheet_name": "Archive"}},
    ]

    selected = agent_blueprints_api._direct_selected_connection_bindings({}, preview, inventory)
    missing = agent_blueprints_api._direct_missing_required_connection_choices(preview, selected)

    assert selected["telegram_delivery"]["integration_id"] == "tg1"
    assert selected["telegram_delivery"]["selection_source"] == "auto_single_connection"
    assert "google_sheets_read" not in selected
    assert missing == [
        {
            "key": "google_sheets_read",
            "provider": "google_sheets",
            "title": "Google Sheets",
            "connection_count": 2,
        }
    ]

    selected = agent_blueprints_api._direct_selected_connection_bindings(
        {"selected_connection_bindings": {"google_sheets_read": "sheet2"}},
        preview,
        inventory,
    )
    metadata = agent_blueprints_api._apply_direct_selected_connection_bindings({}, selected)

    assert selected["google_sheets_read"]["integration_id"] == "sheet2"
    assert agent_blueprints_api._direct_missing_required_connection_choices(preview, selected) == []
    assert metadata["agent_binding_integrations"]["google_sheets_read"]["provider"] == "google_sheets"
    assert metadata["custom_process"]["google_sheets"]["sheet_name"] == "Archive"


def test_sync_blueprint_integration_metadata_records_selected_binding(monkeypatch):
    from api import agent_blueprints_api
    from services.agent_integration_preflight import build_agent_integration_preflight

    class Cursor:
        def __init__(self):
            self.saved_metadata = {}

        def execute(self, query, params=None):
            normalized_query = " ".join(query.split()).lower()
            if normalized_query.startswith("update agent_blueprints"):
                self.saved_metadata = json.loads(params[0])
                return None
            if "from agent_integrations" in normalized_query:
                return None
            raise AssertionError(f"Unhandled SQL: {query}")

        def fetchall(self):
            return []

    blueprint = {
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
            "custom_process": {},
        },
    }
    integration = {
        "id": "sheets-1",
        "provider": "google_sheets",
        "status": "active",
        "config_json": {"spreadsheet_id": "spreadsheet-1", "sheet_name": "Orders", "operation": "read_rows"},
    }
    monkeypatch.setattr(agent_blueprints_api, "_load_blueprint", lambda _cursor, _blueprint_id: blueprint)
    cursor = Cursor()

    metadata = agent_blueprints_api._sync_blueprint_integration_metadata(
        cursor,
        blueprint,
        integration,
        "google_sheets_read",
    )
    preflight = build_agent_integration_preflight(cursor, business_id="biz1", metadata=metadata, input_payload={})

    assert metadata["agent_binding_integrations"]["google_sheets_read"]["integration_id"] == "sheets-1"
    assert metadata["custom_process"]["google_sheets_read"]["spreadsheet_id"] == "spreadsheet-1"
    assert preflight["ready"] is False
    assert preflight["items"][0]["resolution"] == "provider_route_required"
    assert preflight["items"][0]["integration_id"] == "sheets-1"


def test_agent_preflight_reports_selected_binding_missing_config():
    from services.agent_integration_preflight import build_agent_integration_preflight

    class Cursor:
        def execute(self, query, params=None):
            return None

        def fetchall(self):
            return []

    metadata = {
        "required_integration_bindings": [
            {
                "key": "google_sheets_read",
                "provider": "google_sheets",
                "capability": "google_sheets.read_rows",
                "required_config": ["spreadsheet_id", "sheet_name"],
            }
        ],
        "agent_binding_integrations": {
            "google_sheets_read": {
                "integration_id": "sheets-1",
                "provider": "google_sheets",
            }
        },
    }

    preflight = build_agent_integration_preflight(Cursor(), business_id="biz1", metadata=metadata, input_payload={})

    assert preflight["ready"] is False
    assert preflight["status"] == "blocked"
    assert preflight["missing_count"] == 1
    assert preflight["items"][0]["status"] == "needs_config"
    assert preflight["items"][0]["resolution"] == "blueprint_metadata_missing_config"
    assert preflight["items"][0]["integration_id"] == "sheets-1"
    assert preflight["items"][0]["missing_config"] == ["spreadsheet_id", "sheet_name"]
    assert "spreadsheet_id" in preflight["items"][0]["summary"]


def test_agent_preflight_does_not_treat_answer_config_as_external_connection():
    from services.agent_integration_preflight import build_agent_integration_preflight

    class Cursor:
        def execute(self, query, params=None):
            return None

        def fetchall(self):
            return []

    metadata = {
        "required_integration_bindings": [
            {
                "key": "google_sheets_read",
                "provider": "google_sheets",
                "capability": "google_sheets.read_rows",
                "required_config": ["spreadsheet_id", "sheet_name"],
            }
        ],
        "agent_binding_integrations": {
            "google_sheets_read": {
                "answer_config": {
                    "spreadsheet_id": "spreadsheet-from-dialog",
                    "sheet_name": "Orders",
                }
            }
        },
        "custom_process": {
            "google_sheets_read": {
                "spreadsheet_id": "spreadsheet-from-dialog",
                "sheet_name": "Orders",
            },
            "google_sheets": {
                "spreadsheet_id": "spreadsheet-from-dialog",
                "sheet_name": "Orders",
            },
        },
    }

    preflight = build_agent_integration_preflight(Cursor(), business_id="biz1", metadata=metadata, input_payload={})

    assert preflight["ready"] is False
    assert preflight["status"] == "blocked"
    assert preflight["items"][0]["status"] == "needs_connection"
    assert preflight["items"][0]["resolution"] == "builder_answer_needs_provider_route"
    assert preflight["items"][0]["missing_config"] == []
    assert preflight["items"][0]["provider"] == "google_sheets"


def test_agent_preflight_merges_answer_config_into_selected_connection():
    from services.agent_integration_preflight import build_agent_integration_preflight

    class Cursor:
        def execute(self, query, params=None):
            return None

        def fetchall(self):
            return []

    metadata = {
        "required_integration_bindings": [
            {
                "key": "google_sheets_read",
                "provider": "google_sheets",
                "capability": "google_sheets.read_rows",
                "required_config": ["spreadsheet_id", "sheet_name"],
            }
        ],
        "agent_binding_integrations": {
            "google_sheets_read": {
                "integration_id": "sheets-1",
                "provider": "google_sheets",
                "answer_config": {
                    "spreadsheet_id": "spreadsheet-from-dialog",
                    "sheet_name": "Orders",
                },
            }
        },
    }

    preflight = build_agent_integration_preflight(Cursor(), business_id="biz1", metadata=metadata, input_payload={})

    assert preflight["ready"] is False
    assert preflight["items"][0]["status"] == "needs_connection"
    assert preflight["items"][0]["resolution"] == "provider_route_required"


def test_agent_preflight_rejects_revoked_google_auth_without_saved_binding_metadata():
    from services.agent_integration_preflight import build_agent_integration_preflight

    class Cursor:
        def __init__(self):
            self.results = []

        def execute(self, query, params=None):
            normalized_query = " ".join(query.split()).lower()
            if "from agent_integrations integration" in normalized_query:
                self.results = [
                    {
                        "id": "sheets-1",
                        "business_id": "biz1",
                        "provider": "google_sheets",
                        "status": "active",
                        "display_name": "Trips",
                        "auth_ref": "google-account-1",
                        "auth_account_id": "google-account-1",
                        "auth_is_active": False,
                        "auth_last_error": "invalid_grant",
                        "config_json": {
                            "spreadsheet_id": "spreadsheet-1",
                            "sheet_name": "Trips",
                        },
                    }
                ]
                return None
            if "from externalbusinessaccounts" in normalized_query:
                self.results = []
                return None
            raise AssertionError(f"Unhandled SQL: {query}")

        def fetchall(self):
            return self.results

    metadata = {
        "required_integration_bindings": [
            {
                "key": "google_sheets_read",
                "provider": "google_sheets",
                "capability": "google_sheets.read_rows",
                "required_config": ["spreadsheet_id", "sheet_name"],
            }
        ],
    }

    preflight = build_agent_integration_preflight(Cursor(), business_id="biz1", metadata=metadata, input_payload={})

    assert preflight["ready"] is False
    assert preflight["missing_count"] == 1
    assert preflight["items"][0]["resolution"] == "google_sheets_auth_reconnect_required"
    assert preflight["items"][0]["next_action_label"] == "Переподключить Google-доступ"
    assert preflight["items"][0]["integration_id"] == "sheets-1"


def test_agent_preflight_allows_google_sheets_native_read_when_auth_ref_bound():
    from services.agent_integration_preflight import build_agent_integration_preflight

    class Cursor:
        def execute(self, query, params=None):
            return None

        def fetchall(self):
            return [
                {
                    "id": "sheets-1",
                    "provider": "google_sheets",
                    "status": "active",
                    "auth_ref": "google-account-1",
                    "config_json": {"spreadsheet_id": "spreadsheet-1", "sheet_name": "Orders"},
                }
            ]

    metadata = {
        "required_integration_bindings": [
            {
                "key": "google_sheets_read",
                "provider": "google_sheets",
                "capability": "google_sheets.read_rows",
                "required_config": ["spreadsheet_id", "sheet_name"],
            }
        ],
        "agent_binding_integrations": {
            "google_sheets_read": {
                "integration_id": "sheets-1",
                "provider": "google_sheets",
            }
        },
        "custom_process": {
            "google_sheets_read": {
                "integration_id": "sheets-1",
                "spreadsheet_id": "spreadsheet-1",
                "sheet_name": "Orders",
            },
            "google_sheets": {
                "integration_id": "sheets-1",
                "spreadsheet_id": "spreadsheet-1",
                "sheet_name": "Orders",
            },
        },
    }

    preflight = build_agent_integration_preflight(Cursor(), business_id="biz1", metadata=metadata, input_payload={})

    assert preflight["ready"] is True
    assert preflight["items"][0]["status"] == "ready"
    assert preflight["items"][0]["resolution"] == "agent_integration_native_provider"
    assert preflight["items"][0]["integration_id"] == "sheets-1"


def test_agent_preflight_uses_config_from_selected_google_sheets_integration():
    from services.agent_integration_preflight import build_agent_integration_preflight

    class Cursor:
        def __init__(self):
            self.results = []

        def execute(self, query, params=None):
            normalized_query = " ".join(query.split()).lower()
            if "from agent_integrations" in normalized_query:
                self.results = [
                    {
                        "id": "sheets-1",
                        "business_id": "biz1",
                        "provider": "google_sheets",
                        "status": "active",
                        "display_name": "Trips",
                        "auth_ref": "google-account-1",
                        "config_json": {
                            "spreadsheet_id": "spreadsheet-1",
                            "sheet_name": "Trips",
                        },
                    }
                ]
                return None
            if "from externalbusinessaccounts" in normalized_query:
                self.results = []
                return None
            raise AssertionError(f"Unhandled SQL: {query}")

        def fetchall(self):
            return self.results

    metadata = {
        "required_integration_bindings": [
            {
                "key": "google_sheets_read",
                "provider": "google_sheets",
                "capability": "google_sheets.read_rows",
                "required_config": ["spreadsheet_id", "sheet_name"],
                "default_config": {"sheet_name": "Sheet1"},
            }
        ],
        "agent_integration_ids": ["sheets-1"],
        "agent_binding_integrations": {
            "google_sheets_read": {
                "integration_id": "sheets-1",
                "provider": "google_sheets",
            }
        },
    }

    preflight = build_agent_integration_preflight(Cursor(), business_id="biz1", metadata=metadata, input_payload={})

    assert preflight["ready"] is True
    assert preflight["missing_count"] == 0
    assert preflight["items"][0]["resolution"] == "agent_integration_native_provider"
    assert preflight["items"][0]["integration_id"] == "sheets-1"


def test_agent_preflight_rejects_revoked_google_auth_bound_to_integration():
    from services.agent_integration_preflight import build_agent_integration_preflight

    class Cursor:
        def __init__(self):
            self.results = []

        def execute(self, query, params=None):
            normalized_query = " ".join(query.split()).lower()
            if "from agent_integrations integration" in normalized_query:
                self.results = [
                    {
                        "id": "sheets-1",
                        "business_id": "biz1",
                        "provider": "google_sheets",
                        "status": "active",
                        "display_name": "Trips",
                        "auth_ref": "google-account-1",
                        "auth_account_id": "google-account-1",
                        "auth_is_active": False,
                        "auth_last_error": "invalid_grant",
                        "config_json": {
                            "spreadsheet_id": "spreadsheet-1",
                            "sheet_name": "Trips",
                        },
                    }
                ]
                return None
            if "from externalbusinessaccounts" in normalized_query:
                self.results = []
                return None
            raise AssertionError(f"Unhandled SQL: {query}")

        def fetchall(self):
            return self.results

    metadata = {
        "required_integration_bindings": [
            {
                "key": "google_sheets_read",
                "provider": "google_sheets",
                "capability": "google_sheets.read_rows",
                "required_config": ["spreadsheet_id", "sheet_name"],
            }
        ],
        "agent_binding_integrations": {
            "google_sheets_read": {
                "integration_id": "sheets-1",
                "provider": "google_sheets",
            }
        },
    }

    preflight = build_agent_integration_preflight(Cursor(), business_id="biz1", metadata=metadata, input_payload={})

    assert preflight["ready"] is False
    assert preflight["items"][0]["status"] == "needs_connection"
    assert preflight["items"][0]["resolution"] == "google_sheets_auth_reconnect_required"
    assert preflight["items"][0]["credential_state"] == "reconnect_required"
    assert preflight["items"][0]["next_action_label"] == "Переподключить Google-доступ"


def test_activation_connection_blocker_keeps_binding_route_context():
    from api import agent_blueprints_api

    preflight = {
        "items": [
            {
                "key": "google_sheets_read",
                "provider": "google_sheets",
                "capability": "google_sheets.read_rows",
                "status": "needs_connection",
                "resolution": "missing_integration",
                "required": True,
                "missing_config": ["spreadsheet_id", "sheet_name"],
            }
        ],
    }

    connection_plan = agent_blueprints_api._activation_connection_plan_from_preflight(
        preflight,
        available_integrations=[
            {
                "id": "sheet-existing",
                "provider": "google_sheets",
                "status": "active",
                "display_name": "Orders sheet",
            }
        ],
        provider_catalog=agent_blueprints_api._agent_integration_provider_catalog(),
    )
    plan_item = connection_plan["items"][0]
    blocker = agent_blueprints_api._activation_connection_blocker(preflight["items"][0], plan_item)
    human_blockers = agent_blueprints_api._activation_gate_human_blockers([blocker], preflight, {})

    assert blocker["binding_key"] == "google_sheets_read"
    assert blocker["missing_config"] == ["spreadsheet_id", "sheet_name"]
    assert blocker["route_state"] == "available"
    assert blocker["preferred_route"]["provider"] == "openclaw"
    assert plan_item["action"] == "choose_existing"
    assert plan_item["setup_cta"]["action"] == "choose_existing"
    assert "Orders sheet" == plan_item["existing_integrations"][0]["display_name"]
    assert "сохранённый доступ" in plan_item["why_blocked"]
    assert any(item["provider"] == "openclaw" for item in blocker["provider_routes"])
    assert human_blockers[0]["binding_key"] == "google_sheets_read"
    assert human_blockers[0]["preferred_route"]["provider"] == "openclaw"
    assert "Google Sheets" in human_blockers[0]["message"]


def test_agent_preflight_does_not_treat_compiled_defaults_as_external_connection():
    from services.agent_integration_preflight import build_agent_integration_preflight

    class Cursor:
        def execute(self, query, params=None):
            return None

        def fetchall(self):
            return []

    metadata = {
        "required_integration_bindings": [
            {
                "key": "telegram_delivery",
                "provider": "telegram",
                "capability": "communications.draft",
                "direction": "external_publish_request",
                "required_config": ["bot_mode"],
                "default_config": {"bot_mode": "business_bot"},
            }
        ]
    }

    preflight = build_agent_integration_preflight(Cursor(), business_id="biz1", metadata=metadata, input_payload={})

    assert preflight["ready"] is False
    assert preflight["status"] == "blocked"
    assert preflight["items"][0]["status"] == "needs_connection"
    assert preflight["items"][0]["resolution"] == "missing_integration"
    assert preflight["items"][0]["provider"] == "telegram"


def test_agent_preflight_accepts_openclaw_provider_route_for_binding(monkeypatch):
    from api import agent_blueprints_api
    from services.agent_integration_preflight import build_agent_integration_preflight

    class Cursor:
        def __init__(self):
            self.saved_metadata = {}

        def execute(self, query, params=None):
            normalized_query = " ".join(query.split()).lower()
            if normalized_query.startswith("update agent_blueprints"):
                self.saved_metadata = json.loads(params[0])
                return None
            if "from agent_integrations" in normalized_query:
                return None
            raise AssertionError(f"Unhandled SQL: {query}")

        def fetchall(self):
            return []

    blueprint = {
        "id": "bp1",
        "business_id": "biz1",
        "metadata_json": {
            "required_integration_bindings": [
                {
                    "key": "telegram_delivery",
                    "provider": "telegram",
                    "capability": "communications.send_offer",
                    "required_config": ["bot_mode"],
                }
            ],
        },
    }
    monkeypatch.setattr(agent_blueprints_api, "_load_blueprint", lambda _cursor, _blueprint_id: blueprint)
    cursor = Cursor()

    metadata = agent_blueprints_api._apply_agent_provider_route_metadata(
        cursor,
        blueprint,
        binding_key="telegram_delivery",
        route_provider="openclaw",
    )
    preflight = build_agent_integration_preflight(cursor, business_id="biz1", metadata=metadata, input_payload={})
    status = agent_blueprints_api._agent_integration_binding_status(metadata, [])

    assert preflight["ready"] is True
    assert preflight["items"][0]["resolution"] == "provider_route_openclaw_boundary"
    assert preflight["items"][0]["integration_id"] == "openclaw_boundary"
    assert preflight["items"][0]["execution_boundary"] == "openclaw_inside_localos_policy"
    assert preflight["items"][0]["autonomy_level"] == "supervised"
    assert preflight["items"][0]["approval_state"] == "approval_required"
    assert "OpenClaw" in preflight["items"][0]["policy_summary"]
    assert status[0]["status"] == "connected"
    assert status[0]["resolution"] == "provider_route_openclaw"


def test_agent_preflight_accepts_maton_provider_route_with_external_account(monkeypatch):
    from api import agent_blueprints_api
    from services.agent_integration_preflight import build_agent_integration_preflight

    class Cursor:
        def __init__(self):
            self.saved_metadata = {}

        def execute(self, query, params=None):
            normalized_query = " ".join(query.split()).lower()
            if normalized_query.startswith("update agent_blueprints"):
                self.saved_metadata = json.loads(params[0])
                return None
            if "from agent_integrations" in normalized_query:
                return None
            raise AssertionError(f"Unhandled SQL: {query}")

        def fetchall(self):
            return []

    blueprint = {
        "id": "bp1",
        "business_id": "biz1",
        "metadata_json": {
            "required_integration_bindings": [
                {
                    "key": "telegram_delivery",
                    "provider": "telegram",
                    "capability": "communications.send_offer",
                    "required_config": ["bot_mode"],
                }
            ],
        },
    }
    monkeypatch.setattr(agent_blueprints_api, "_load_blueprint", lambda _cursor, _blueprint_id: blueprint)
    cursor = Cursor()

    metadata = agent_blueprints_api._apply_agent_provider_route_metadata(
        cursor,
        blueprint,
        binding_key="telegram_delivery",
        route_provider="maton",
        external_account={"id": "maton-account-1", "display_name": "Main Maton key"},
    )
    preflight = build_agent_integration_preflight(cursor, business_id="biz1", metadata=metadata, input_payload={})
    status = agent_blueprints_api._agent_integration_binding_status(metadata, [])

    assert preflight["ready"] is True
    assert preflight["items"][0]["resolution"] == "provider_route_maton_external_account"
    assert preflight["items"][0]["integration_id"] == "maton-account-1"
    assert preflight["items"][0]["execution_boundary"] == "maton_bridge_inside_localos_policy"
    assert preflight["items"][0]["credential_state"] == "external_account_bound"
    assert "Maton" in preflight["items"][0]["policy_summary"]
    assert status[0]["status"] == "connected"
    assert status[0]["route_provider"] == "maton"


def test_agent_preflight_accepts_manual_provider_route_as_human_fallback(monkeypatch):
    from api import agent_blueprints_api
    from services.agent_integration_preflight import build_agent_integration_preflight

    class Cursor:
        def __init__(self):
            self.saved_metadata = {}

        def execute(self, query, params=None):
            normalized_query = " ".join(query.split()).lower()
            if normalized_query.startswith("update agent_blueprints"):
                self.saved_metadata = json.loads(params[0])
                return None
            if "from agent_integrations" in normalized_query:
                return None
            raise AssertionError(f"Unhandled SQL: {query}")

        def fetchall(self):
            return []

    blueprint = {
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
        },
    }
    monkeypatch.setattr(agent_blueprints_api, "_load_blueprint", lambda _cursor, _blueprint_id: blueprint)
    cursor = Cursor()

    metadata = agent_blueprints_api._apply_agent_provider_route_metadata(
        cursor,
        blueprint,
        binding_key="google_sheets_read",
        route_provider="manual",
    )
    preflight = build_agent_integration_preflight(cursor, business_id="biz1", metadata=metadata, input_payload={})
    status = agent_blueprints_api._agent_integration_binding_status(metadata, [])

    assert preflight["ready"] is True
    assert preflight["items"][0]["resolution"] == "provider_route_manual_fallback"
    assert preflight["items"][0]["execution_boundary"] == "human_operated_fallback"
    assert preflight["items"][0]["autonomy_level"] == "draft_only"
    assert preflight["items"][0]["approval_state"] == "human_action_required"
    assert "человек" in preflight["items"][0]["policy_summary"]
    assert status[0]["status"] == "connected"
    assert status[0]["route_provider"] == "manual"
    assert metadata["agent_binding_provider_routes"]["google_sheets_read"]["draft_only_until_human_action"] is True


def test_agent_preflight_reports_active_integration_missing_config():
    from services.agent_integration_preflight import build_agent_integration_preflight

    class Cursor:
        def __init__(self):
            self.results = []

        def execute(self, query, params=None):
            normalized_query = " ".join(query.split()).lower()
            if "from agent_integrations" in normalized_query:
                self.results = [
                    {
                        "id": "sheets-1",
                        "business_id": "biz1",
                        "provider": "google_sheets",
                        "status": "active",
                        "display_name": "Orders sheet",
                        "config_json": {"spreadsheet_id": "spreadsheet-1"},
                    }
                ]
                return None
            raise AssertionError(f"Unhandled SQL: {query}")

        def fetchall(self):
            return self.results

    metadata = {
        "required_integration_bindings": [
            {
                "key": "google_sheets_read",
                "provider": "google_sheets",
                "capability": "google_sheets.read_rows",
                "required_config": ["spreadsheet_id", "sheet_name"],
            }
        ],
    }

    preflight = build_agent_integration_preflight(Cursor(), business_id="biz1", metadata=metadata, input_payload={})

    assert preflight["ready"] is False
    assert preflight["items"][0]["status"] == "needs_config"
    assert preflight["items"][0]["resolution"] == "agent_integration_missing_config"
    assert preflight["items"][0]["integration_id"] == "sheets-1"
    assert preflight["items"][0]["missing_config"] == ["sheet_name"]


def test_agent_connection_plan_turns_bindings_into_user_next_actions():
    from api import agent_blueprints_api

    binding_status = [
        {
            "key": "google_sheets_read",
            "provider": "google_sheets",
            "capability": "google_sheets.read_rows",
            "status": "missing",
            "missing_config": ["spreadsheet_id", "sheet_name"],
        },
        {
            "key": "telegram_delivery",
            "provider": "telegram",
            "capability": "communications.draft",
            "status": "connected",
            "integration_id": "telegram-1",
            "resolution": "agent_integration",
        },
        {
            "key": "localos_finance",
            "provider": "localos_finance",
            "capability": "finance.transaction.create",
            "status": "connected",
            "integration_id": "native_localos",
            "resolution": "native_localos",
        },
    ]
    available = [
        {
            "id": "sheet-existing",
            "provider": "google_sheets",
            "status": "active",
            "display_name": "Orders sheet",
        }
    ]

    plan = agent_blueprints_api._agent_connection_plan(
        binding_status,
        [],
        available,
        agent_blueprints_api._agent_integration_provider_catalog(),
    )

    assert plan["schema"] == "localos_agent_connection_plan_v1"
    assert plan["status"] == "needs_action"
    assert plan["missing_count"] == 1
    assert plan["items"][0]["action"] == "choose_existing"
    assert plan["items"][0]["route_state"] == "available"
    assert "выберите" in plan["items"][0]["route_summary"].lower()
    assert plan["items"][0]["setup_cta"]["action"] == "choose_existing"
    assert "сохранённый доступ" in plan["items"][0]["why_blocked"]
    assert plan["items"][0]["existing_integrations"][0]["display_name"] == "Orders sheet"
    assert any(item["provider"] == "openclaw" for item in plan["items"][0]["provider_routes"])
    assert any(item["provider"] == "native_localos" for item in plan["items"][0]["provider_paths"])
    assert plan["items"][1]["action"] == "ready"
    assert plan["items"][1]["route_state"] == "connected"
    assert plan["items"][2]["action"] == "native_ready"


def test_agent_post_connect_handoff_routes_ready_connections_to_preview():
    from api import agent_blueprints_api

    ready = agent_blueprints_api._build_agent_post_connect_handoff(
        {
            "schema": "localos_agent_connection_plan_v1",
            "status": "ready",
            "missing_count": 0,
            "items": [],
        }
    )
    blocked = agent_blueprints_api._build_agent_post_connect_handoff(
        {
            "schema": "localos_agent_connection_plan_v1",
            "status": "needs_action",
            "missing_count": 2,
            "items": [
                {
                    "key": "google_sheets_read",
                    "provider": "google_sheets",
                    "action": "ready",
                },
                {
                    "key": "telegram_delivery",
                    "provider": "telegram",
                    "action": "connect_required",
                },
            ],
        }
    )

    assert ready["status"] == "ready_for_preview"
    assert ready["workspace_mode"] == "run"
    assert ready["next_step"] == "run_preview"
    assert "безопасный тест" in ready["description"]
    assert "workflow" not in ready["description"]
    assert "preflight" not in ready["description"]
    assert "approval gate" not in ready["description"]
    assert blocked["status"] == "needs_connections"
    assert blocked["workspace_mode"] == "connections"
    assert blocked["next_step"] == "connect_required_integrations"
    assert blocked["next_binding_key"] == "telegram_delivery"


def test_agent_builder_post_create_handoff_contains_connection_plan():
    from api import agent_builder_api

    handoff = agent_builder_api._build_post_create_handoff(
        {
            "ready": False,
            "items": [
                {
                    "key": "google_sheets_read",
                    "provider": "google_sheets",
                    "capability": "google_sheets.read_rows",
                    "status": "needs_connection",
                    "required": True,
                    "missing_config": ["spreadsheet_id", "sheet_name"],
                },
                {
                    "key": "telegram_delivery",
                    "provider": "telegram",
                    "capability": "communications.draft",
                    "status": "ready",
                    "resolution": "agent_integration",
                    "required": True,
                },
            ],
            "missing": [
                {
                    "key": "google_sheets_read",
                    "provider": "google_sheets",
                    "capability": "google_sheets.read_rows",
                    "status": "needs_connection",
                    "required": True,
                    "missing_config": ["spreadsheet_id", "sheet_name"],
                }
            ],
        }
    )

    assert handoff["schema"] == "localos_agent_post_create_handoff_v1"
    assert handoff["status"] == "needs_connections"
    assert handoff["next_binding_key"] == "google_sheets_read"
    assert handoff["next_binding"]["key"] == "google_sheets_read"
    assert handoff["next_binding"]["title"] == "Google Sheets"
    assert handoff["next_binding"]["route_state"] == "available"
    assert handoff["next_binding"]["route_summary"]
    assert handoff["next_binding"]["recommended_route"]["provider"] == "openclaw"
    assert "OpenClaw" in handoff["next_binding"]["recommended_route_reason"]
    assert handoff["next_route"]["provider"] == "openclaw"
    assert handoff["next_route"]["primary_cta"]
    assert handoff["connection_plan"]["schema"] == "localos_agent_connection_plan_v1"
    assert handoff["connection_plan"]["missing_count"] == 1
    assert handoff["connection_plan"]["items"][0]["action"] == "connect_required"
    assert handoff["connection_plan"]["items"][0]["provider_routes"]
    assert handoff["connection_plan"]["items"][1]["action"] == "ready"


def test_agent_builder_post_create_handoff_routes_ready_agent_to_preview_run():
    from api import agent_builder_api

    handoff = agent_builder_api._build_post_create_handoff(
        {
            "ready": True,
            "items": [
                {
                    "key": "google_sheets_read",
                    "provider": "google_sheets",
                    "capability": "google_sheets.read_rows",
                    "status": "ready",
                    "resolution": "agent_integration",
                    "required": True,
                },
                {
                    "key": "telegram_delivery",
                    "provider": "telegram",
                    "capability": "communications.draft",
                    "status": "ready",
                    "resolution": "agent_integration",
                    "required": True,
                },
            ],
            "missing": [],
        }
    )

    assert handoff["status"] == "ready_for_preview"
    assert handoff["next_step"] == "run_preview"
    assert handoff["workspace_mode"] == "run"
    assert handoff["next_binding"] == {}
    assert handoff["next_route"] == {}
    assert "preview run" in handoff["description"]


def test_activation_gate_summary_explains_missing_connector(monkeypatch):
    from api import agent_blueprints_api

    class Cursor:
        def execute(self, *args, **kwargs):
            return None

        def fetchall(self):
            return []

    monkeypatch.setattr(
        agent_blueprints_api,
        "validate_compiled_artifact_candidate",
        lambda payload, metadata: {"ready": True, "validation": {"status": "passed", "errors": []}},
    )
    monkeypatch.setattr(
        agent_blueprints_api,
        "build_version_payload_from_row",
        lambda row: {"steps": []},
    )

    metadata = {
        "execution_mode": "manual",
        "required_integration_bindings": [
            {
                "key": "google_sheets_read",
                "provider": "google_sheets",
                "capability": "google_sheets.read_rows",
                "required_config": ["spreadsheet_id"],
            }
        ]
    }
    gate = agent_blueprints_api._build_activation_gate_summary(
        Cursor(),
        {"business_id": "biz1"},
        {"id": "version-1", "version_number": 1},
        metadata,
    )

    assert gate["schema"] == "localos_agent_activation_gate_v1"
    assert gate["can_activate"] is False
    assert gate["next_step"] == "connect_required_integrations"
    assert gate["primary_action_label"] == "Открыть подключения"
    assert gate["human_blockers"][0]["provider"] == "google_sheets"
    assert "Google Sheets" in gate["summary"]
    assert "spreadsheet_id" in gate["summary"]
    assert gate["connection_plan"]["schema"] == "localos_agent_connection_plan_v1"
    assert gate["connection_plan"]["items"][0]["action"] == "connect_required"
    assert gate["connection_plan"]["items"][0]["recommended_route"]["provider"] == "openclaw"
    assert gate["next_binding_key"] == "google_sheets_read"


def test_legacy_agent_requires_execution_mode_confirmation():
    from api import agent_blueprints_api

    blueprint = {
        "status": "active",
        "metadata_json": {
            "custom_process": {
                "trigger": "schedule.daily",
                "schedule": {"time": "09:00", "timezone": "Europe/Tallinn"},
            }
        },
    }

    assert agent_blueprints_api._agent_execution_mode(blueprint) == "scheduled"
    assert agent_blueprints_api._agent_execution_mode_source(blueprint) == "legacy_trigger"
    assert agent_blueprints_api._agent_execution_mode_confirmation_required(blueprint) is True
    assert agent_blueprints_api._agent_lifecycle_state(blueprint) == "needs_setup"


def test_completed_one_off_has_completed_lifecycle():
    from api import agent_blueprints_api

    blueprint = {
        "status": "active",
        "last_run_status": "completed",
        "last_run_input_json": {"preview_mode": False},
        "metadata_json": {"execution_mode": "one_off"},
    }

    assert agent_blueprints_api._agent_execution_mode_source(blueprint) == "explicit"
    assert agent_blueprints_api._agent_execution_mode_confirmation_required(blueprint) is False
    assert agent_blueprints_api._agent_lifecycle_state(blueprint) == "completed"


def test_activation_gate_requires_safe_preview_run(monkeypatch):
    from api import agent_blueprints_api

    class Cursor:
        def __init__(self):
            self.rows = []

        def execute(self, query, params=None):
            normalized_query = " ".join(query.split()).lower()
            self.rows = []
            if "from agent_runs" in normalized_query:
                self.rows = []

        def fetchall(self):
            return self.rows

    monkeypatch.setattr(
        agent_blueprints_api,
        "validate_compiled_artifact_candidate",
        lambda payload, metadata: {"ready": True, "validation": {"status": "passed", "errors": []}},
    )
    monkeypatch.setattr(
        agent_blueprints_api,
        "build_version_payload_from_row",
        lambda row: {"steps": []},
    )

    gate = agent_blueprints_api._build_activation_gate_summary(
        Cursor(),
        {"id": "bp1", "business_id": "biz1"},
        {"id": "version-1", "version_number": 1},
        {"execution_mode": "manual", "required_integration_bindings": []},
    )

    assert gate["can_activate"] is False
    assert gate["requires_preview_run"] is True
    assert gate["preview_run_status"]["ready"] is False
    assert gate["next_step"] == "run_preview"
    assert gate["primary_action_label"] == "Запустить preview"
    assert gate["human_blockers"][0]["type"] == "preview_run"


def test_activation_gate_accepts_completed_safe_preview_run(monkeypatch):
    from api import agent_blueprints_api

    class Cursor:
        def __init__(self):
            self.rows = []

        def execute(self, query, params=None):
            normalized_query = " ".join(query.split()).lower()
            self.rows = []
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

        def fetchall(self):
            return self.rows

    monkeypatch.setattr(
        agent_blueprints_api,
        "validate_compiled_artifact_candidate",
        lambda payload, metadata: {"ready": True, "validation": {"status": "passed", "errors": []}},
    )
    monkeypatch.setattr(
        agent_blueprints_api,
        "build_version_payload_from_row",
        lambda row: {"steps": []},
    )

    gate = agent_blueprints_api._build_activation_gate_summary(
        Cursor(),
        {"id": "bp1", "business_id": "biz1"},
        {"id": "version-1", "version_number": 1},
        {"execution_mode": "manual", "required_integration_bindings": []},
    )

    assert gate["can_activate"] is True
    assert gate["preview_run_status"]["ready"] is True
    assert gate["preview_run_status"]["passed_run"]["id"] == "run-1"
    assert gate["next_step"] == "activate_version"


def test_activation_gate_blocks_autonomous_write_limits_even_after_preview(monkeypatch):
    from api import agent_blueprints_api

    class Cursor:
        def __init__(self):
            self.rows = []

        def execute(self, query, params=None):
            normalized_query = " ".join(query.split()).lower()
            self.rows = []
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

        def fetchall(self):
            return self.rows

    monkeypatch.setattr(
        agent_blueprints_api,
        "validate_compiled_artifact_candidate",
        lambda payload, metadata: {
            "ready": True,
            "validation": {"status": "passed", "errors": []},
            "candidate": {
                "dsl": {
                    "limits": {
                        "autonomous_external_write_allowed": True,
                    }
                }
            },
        },
    )

    gate = agent_blueprints_api._build_activation_gate_summary(
        Cursor(),
        {"id": "bp1", "business_id": "biz1"},
        {
            "id": "version-1",
            "version_number": 1,
            "steps_json": [
                {
                    "key": "write_sheet",
                    "type": "capability",
                    "capability": "sheets.append_row_request",
                    "requires_approval": True,
                    "required_approval_type": "sheet_update",
                },
                {
                    "key": "approve_sheet_update",
                    "type": "approval",
                    "approval_type": "sheet_update",
                },
            ],
            "approval_policy_json": {"sheet_update": "manual_approval_required"},
            "capability_allowlist_json": ["sheets.append_row_request"],
        },
        {"execution_mode": "manual", "required_integration_bindings": []},
    )

    assert gate["can_activate"] is False
    assert gate["next_step"] == "fix_compiled_workflow"
    assert gate["approval_policy_status"]["ready"] is False
    assert gate["approval_policy_status"]["autonomous_writes_allowed"] is True
    assert gate["human_blockers"][0]["type"] == "approval_policy"


def test_google_sheets_integration_config_preserves_read_write_operation():
    from api import agent_blueprints_api

    read_config = agent_blueprints_api._sanitize_agent_integration_config(
        "google_sheets",
        {
            "config": {
                "spreadsheet_id": "spreadsheet-1",
                "sheet_name": "Payments",
                "operation": "read_rows",
            }
        },
    )
    invalid_config = agent_blueprints_api._sanitize_agent_integration_config(
        "google_sheets",
        {
            "config": {
                "spreadsheet_id": "spreadsheet-1",
                "sheet_name": "Payments",
                "operation": "delete_sheet",
            }
        },
    )

    assert read_config["operation"] == "read_rows"
    assert invalid_config["operation"] == "read_write"


def test_google_oauth_requests_sheets_scope_for_agent_runtime():
    from pathlib import Path

    from services.agent_google_sheets_adapter import SHEETS_SCOPE

    source = Path("src/google_business_auth.py").read_text(encoding="utf-8")
    assert SHEETS_SCOPE in source
    assert "autogenerate_code_verifier=False" in source


def test_google_sheets_integration_auto_binds_google_business_auth_ref():
    from api import agent_blueprints_api

    class Cursor:
        def __init__(self):
            self.last_result = None

        def execute(self, query, params=None):
            normalized_query = " ".join(query.split()).lower()
            params = params or ()
            if "from externalbusinessaccounts" in normalized_query:
                assert params[0] == "biz1"
                self.last_result = {"id": "google-account-1"}
                return None
            raise AssertionError(f"Unhandled SQL: {query}")

        def fetchone(self):
            return self.last_result

    assert (
        agent_blueprints_api._resolve_agent_integration_auth_ref(
            Cursor(),
            "biz1",
            "google_sheets",
            "",
        )
        == "google-account-1"
    )


def test_google_oauth_callback_syncs_google_sheets_runtime_auth_ref():
    from pathlib import Path

    source = Path("src/api/google_business_api.py").read_text(encoding="utf-8")
    assert "def _sync_google_sheets_agent_auth_refs" in source
    assert "UPDATE agent_integrations" in source
    assert "provider = 'google_sheets'" in source
    assert "COALESCE(auth_ref, '') = ''" in source
    assert "_sync_google_sheets_agent_auth_refs(cursor, business_id, account_id)" in source


def test_maton_integration_config_is_delivery_bridge_with_caps():
    from api import agent_blueprints_api

    config = agent_blueprints_api._sanitize_agent_integration_config(
        "maton",
        {"config": {"channel": "whatsapp_business"}},
    )
    limits = agent_blueprints_api._sanitize_agent_integration_limits(
        "maton",
        {"limits": {"daily_message_cap": 25, "frequency_cap_minutes": 15}},
    )

    assert config["channel"] == "whatsapp_business"
    assert config["mode"] == "approved_delivery_bridge"
    assert limits["daily_message_cap"] == 25
    assert limits["frequency_cap_minutes"] == 15


def test_whatsapp_integration_config_is_supported_channel_boundary():
    from api import agent_blueprints_api
    from services.agent_provider_registry import integration_provider_catalog

    config = agent_blueprints_api._sanitize_agent_integration_config(
        "whatsapp",
        {"config": {"channel_mode": "manual_whatsapp"}},
    )
    limits = agent_blueprints_api._sanitize_agent_integration_limits(
        "whatsapp",
        {"limits": {"daily_message_cap": 35, "frequency_cap_minutes": 20}},
    )
    catalog = {item["provider"]: item for item in integration_provider_catalog()}
    boundary = agent_blueprints_api._agent_integration_execution_boundary("whatsapp")

    assert config["channel_mode"] == "manual_whatsapp"
    assert config["trigger"] == "whatsapp.message.received"
    assert config["mode"] == "trigger_boundary"
    assert limits["daily_message_cap"] == 35
    assert limits["frequency_cap_minutes"] == 20
    assert catalog["whatsapp"]["status"] == "available"
    assert boundary["executor"] == "channel_router"
    assert boundary["external_write"] == "approved_delivery_only"


def test_browser_use_integration_config_and_generic_binding_use_openclaw_boundary():
    from api import agent_blueprints_api
    from services.agent_blueprint_draft_builder import compile_agent_blueprint
    from services.agent_provider_registry import integration_provider_catalog

    config = agent_blueprints_api._sanitize_agent_integration_config(
        "browser_use",
        {"config": {"target_urls": "https://example.com\nhttps://competitor.example"}},
    )
    limits = agent_blueprints_api._sanitize_agent_integration_limits(
        "browser_use",
        {"limits": {"daily_page_check_cap": 12, "frequency_cap_minutes": 45}},
    )
    catalog = {item["provider"]: item for item in integration_provider_catalog()}
    boundary = agent_blueprints_api._agent_integration_execution_boundary("browser_use")
    draft = compile_agent_blueprint(
        "Через browser use открой сайт конкурента https://example.com, проверь изменения цен и подготовь сообщение владельцу в Telegram.",
        use_ai=True,
    )
    metadata = draft["metadata"]
    required = metadata["required_integration_bindings"]
    browser_binding = next(item for item in required if item["provider"] == "browser_use")

    assert config["target_urls"] == ["https://example.com", "https://competitor.example"]
    assert config["mode"] == "openclaw_browser_boundary"
    assert limits["daily_page_check_cap"] == 12
    assert limits["frequency_cap_minutes"] == 45
    assert catalog["browser_use"]["status"] == "available"
    assert boundary["executor"] == "openclaw_browser_boundary"
    assert boundary["capabilities"] == ["browser_use.read_page"]
    assert browser_binding["key"] == "browser_use_read"
    assert browser_binding["capability"] == "browser_use.read_page"
    assert browser_binding["required_config"] == ["target_urls"]
    assert browser_binding["execution_boundary"] == "openclaw_browser_boundary"


def test_custom_process_mapping_updates_compiled_version_steps():
    from api import agent_blueprints_api
    from services.agent_blueprint_draft_builder import compile_agent_blueprint

    draft = compile_agent_blueprint("Когда пользователь пишет в Telegram бота, добавь строку в Google таблицу")
    version_payload = agent_blueprints_api._apply_custom_process_to_version_payload(
        draft["version_payload"],
        {
            "row_values": ["{{received_at}}", "{{message_text}}", "{{telegram_user_id}}"],
            "columns": ["received_at", "message_text", "telegram_user_id"],
            "daily_append_cap": 12,
            "google_sheets": {"sheet_name": "Requests"},
        },
    )

    request_step = [step for step in version_payload["steps"] if step.get("capability") == "sheets.append_row_request"][0]
    draft_step = [step for step in version_payload["steps"] if step["key"] == "prepare_sheet_row"][0]
    assert request_step["payload"]["sheet_name"] == "Requests"
    assert request_step["payload"]["daily_append_cap"] == 12
    assert request_step["payload"]["row_values"] == ["{{received_at}}", "{{message_text}}", "{{telegram_user_id}}"]
    assert draft_step["payload"]["columns"] == ["received_at", "message_text", "telegram_user_id"]
    assert version_payload["output_schema"]["sheet_name"] == "Requests"
    assert version_payload["limits"]["daily_append_cap"] == 12
