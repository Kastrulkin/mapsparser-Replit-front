"""Synthetic regressions for Apify diagnostics and their local status reader."""

from __future__ import annotations

import ast
import copy
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import re

import pytest

from src.services.prospecting_service import ProspectingService


ROOT = Path(__file__).parents[1]
MARKER = "synthetic-private-apify-diagnostic-marker"
MISMATCH = "Ссылка ведёт на другую карточку. Проверьте ссылку и повторите сбор данных."


def _humanize():
    path = ROOT / "src" / "legacy_routes" / "parsing_networks.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                 and node.name == "_humanize_parse_error_message"]
    assert len(functions) == 1
    module = ast.fix_missing_locations(ast.Module(body=[ast.ImportFrom(
        module="__future__", names=[ast.alias(name="annotations")], level=0),
        copy.deepcopy(functions[0])], type_ignores=[]))
    namespace = {"os": os, "json": json, "re": re}
    exec(compile(module, str(path), "exec"), namespace)
    return namespace["_humanize_parse_error_message"]


def test_new_trace_omits_arbitrary_values_and_keys_but_keeps_stage(tmp_path):
    payload = {"name": MARKER, "phone": MARKER, "headers": {MARKER: MARKER},
               "run_input": {MARKER: MARKER}, "items": [{"title": MARKER}],
               "cost": 0.25}
    before = copy.deepcopy(payload)
    ProspectingService._append_debug_trace(str(tmp_path), "run_started", payload)
    path = tmp_path / "apify_trace.json"
    assert path.exists()
    assert MARKER not in path.read_text()
    events = json.loads(path.read_text())
    assert len(events) == 1
    assert events[0]["event"] == "run_started"
    assert events[0]["diagnostics_version"] == 2
    assert events[0]["payload"]["type"] == "object"
    assert events[0]["payload"]["field_count"] == len(payload)
    assert payload == before


def test_append_does_not_repersist_legacy_raw_event_values(tmp_path):
    path = tmp_path / "apify_trace.json"
    path.write_text(json.dumps([{"event": "input_prepared", "ts": MARKER,
        "payload": {"phone": MARKER}, MARKER: MARKER},
        {"event": "run_started", "ts": "2026-09-21T06:00:00Z",
         "payload": {"title": MARKER}}]))
    ProspectingService._append_debug_trace(str(tmp_path), "run_succeeded", {"name": MARKER})
    text = path.read_text()
    events = json.loads(text)
    assert MARKER not in text
    assert [item["event"] for item in events] == ["input_prepared", "run_started", "run_succeeded"]
    assert events[1]["ts"] == "2026-09-21T06:00:00Z"
    assert all(item["diagnostics_version"] == 2 for item in events)


def test_unknown_event_is_a_fixed_category_not_arbitrary_input(tmp_path):
    ProspectingService._append_debug_trace(str(tmp_path), MARKER, {"error": MARKER})
    text = (tmp_path / "apify_trace.json").read_text()
    assert MARKER not in text
    assert json.loads(text)[0]["event"] == "other"


def test_disabled_trace_does_not_open_files(monkeypatch):
    monkeypatch.setattr("builtins.open", lambda *_a, **_k: pytest.fail("disabled trace opened a file"))
    assert ProspectingService._append_debug_trace(None, "run_started", {"name": MARKER}) is None


def test_trace_write_failure_is_nonfatal_and_value_free(tmp_path, monkeypatch, capsys):
    def fail(*_args, **_kwargs):
        raise OSError(MARKER)
    monkeypatch.setattr("builtins.open", fail)
    assert ProspectingService._append_debug_trace(str(tmp_path), "run_started", {"name": MARKER}) is None
    captured = capsys.readouterr()
    assert MARKER not in captured.out + captured.err


def test_all_supported_trace_calls_retain_recognized_event_categories(tmp_path):
    tree = ast.parse((ROOT / "src" / "services" / "prospecting_service.py").read_text())
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Attribute) and node.func.attr == "_append_debug_trace"]
    assert calls
    event_names = []
    for call in calls:
        assert len(call.args) >= 2 and isinstance(call.args[1], ast.Constant)
        name = call.args[1].value
        assert isinstance(name, str)
        event_names.append(name)
        ProspectingService._append_debug_trace(str(tmp_path), name)
    events = json.loads((tmp_path / "apify_trace.json").read_text())
    assert [item["event"] for item in events] == event_names


def test_actor_failure_log_omits_values_and_reraises_original_error():
    service = ProspectingService.__new__(ProspectingService)
    service.api_token = "synthetic-unused-value"
    error = RuntimeError(MARKER)
    calls = []
    def fail(query, location, **kwargs):
        calls.append((query, location, kwargs))
        raise error
    service.run_search = fail
    output = io.StringIO()
    with redirect_stdout(output), pytest.raises(RuntimeError) as caught:
        service.search_businesses("synthetic query", "synthetic city", limit=1)
    assert caught.value is error
    assert len(calls) == 1
    assert calls[0][2]["limit"] == 1
    assert MARKER not in output.getvalue()
    assert "Error running Apify actor" in output.getvalue()


def test_v2_identity_diagnostic_has_actionable_status_without_private_details(tmp_path):
    ProspectingService._append_debug_trace(str(tmp_path), "identity_filtered",
        {"rejected_candidates": [{"name": MARKER, "city": MARKER, "address": MARKER}]})
    result = _humanize()(f"Parsed entity mismatch for source URL | {MARKER} bundle={tmp_path}")
    assert result == MISMATCH
    assert MARKER not in result
    assert str(tmp_path) not in result


def test_reader_accepts_explicit_v2_trace_shape(tmp_path):
    (tmp_path / "apify_trace.json").write_text(json.dumps([
        {"diagnostics_version": 2, "event": "identity_filtered",
         "payload": {"type": "object", "field_count": 3}},
    ]))
    assert _humanize()(f"Parsed entity mismatch for source URL bundle={tmp_path}") == MISMATCH


def test_existing_legacy_trace_reader_contract_is_preserved(tmp_path):
    (tmp_path / "apify_trace.json").write_text(json.dumps([
        {"event": "identity_filtered", "payload": {"rejected_candidates": [
            {"name": "Synthetic place", "city": "Synthetic city", "address": "Synthetic address"}]}}
    ]))
    assert _humanize()(f"Parsed entity mismatch for source URL bundle={tmp_path}") == (
        "Ссылка ведёт на другую карточку: название: Synthetic place; город: Synthetic city; адрес: Synthetic address")


@pytest.mark.parametrize("message", [None, "", "synthetic unrelated failure", "Parsed entity mismatch for source URL"])
def test_reader_empty_unrelated_and_absent_bundle_behavior_is_preserved(message):
    assert _humanize()(message) == (message or None)
