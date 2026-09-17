"""The exact pre-approval snapshot, including an empty range, gates a write."""
import pytest

from services import agent_google_sheets_adapter
from services.agent_blueprint_runner import AgentBlueprintRunner


@pytest.fixture
def sheet_adapter(monkeypatch):
    calls = []
    current = {"values": []}

    class Response:
        status_code = 200
        content = b"{}"

        def json(self):
            return dict(current)

    def get(_url, **_kwargs):
        calls.append("read")
        return Response()

    def put(_url, **_kwargs):
        calls.append("write")
        return Response()

    monkeypatch.setattr(agent_google_sheets_adapter.requests, "get", get)
    monkeypatch.setattr(agent_google_sheets_adapter.requests, "put", put)
    adapter = agent_google_sheets_adapter.GoogleSheetsAppendAdapter({"token": "synthetic"})
    return adapter, current, calls


def test_approved_empty_range_cannot_overwrite_new_content(sheet_adapter):
    adapter, current, calls = sheet_adapter
    current["values"] = [["entered after approval"]]
    with pytest.raises(agent_google_sheets_adapter.GoogleSheetsAdapterError, match="VALUES_CHANGED"):
        adapter.update_cells({
            "spreadsheet_id": "synthetic-sheet", "range": "Data!A1",
            "expected_values": [], "values": [["proposed value"]],
        })
    assert calls == ["read"]


def test_approved_empty_range_can_fill_still_empty_cells(sheet_adapter):
    adapter, _current, calls = sheet_adapter
    result = adapter.update_cells({
        "spreadsheet_id": "synthetic-sheet", "range": "Data!A1",
        "expected_values": [], "values": [["proposed value"]],
    })
    assert result["success"]
    assert result["before"] == []
    assert calls == ["read", "write"]


def test_missing_snapshot_cannot_be_interpreted_as_empty(sheet_adapter):
    adapter, _current, calls = sheet_adapter
    with pytest.raises(agent_google_sheets_adapter.GoogleSheetsAdapterError, match="expected_values"):
        adapter.update_cells({
            "spreadsheet_id": "synthetic-sheet", "range": "Data!A1",
            "values": [["proposed value"]],
        })
    assert calls == []


@pytest.mark.parametrize("run_input", [{"preview_mode": True}, {"external_side_effects_allowed": False}])
def test_sheet_preview_cannot_create_a_provider_handoff(monkeypatch, run_input):
    writes = []

    class Cursor:
        def execute(self, query, params):
            writes.append((query, params))

    class Orchestrator:
        def execute(self, *_args, **_kwargs):
            pytest.fail("a preview cannot create a provider handoff")

    runner = AgentBlueprintRunner(Cursor(), Orchestrator())
    monkeypatch.setattr(runner, "_insert_step", lambda *_args: "step")
    monkeypatch.setattr(runner, "_build_capability_payload", lambda *_args: {"values": [["test"]]})
    monkeypatch.setattr(runner, "_has_required_approval", lambda *_args: True)
    result = runner._execute_capability_step(
        {"id": "run", "business_id": "business", "input_json": run_input},
        {"capability_allowlist_json": ["google_sheets.update_cells"]},
        {"key": "write", "capability": "google_sheets.update_cells"}, 1, {"user_id": "user"},
    )
    assert result is True
    assert len(writes) == 1
    assert "preview_only" in writes[0][1][0]
    assert "provider_write_performed" in writes[0][1][0]


def test_unknown_provider_result_is_not_described_as_completed():
    runner = AgentBlueprintRunner(None)
    headline = runner._preview_summary_headline(
        {"status": "waiting_provider"}, False, {"ready": True}, [],
        [{"state": "provider_reconciliation_required"}],
    )
    assert "Результат записи неизвестен" in headline
