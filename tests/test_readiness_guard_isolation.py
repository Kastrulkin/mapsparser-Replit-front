"""Mutation checks for the health test, without importing the application or DB."""

import ast
from pathlib import Path
import types
import unittest

import flask
import pytest


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_SOURCE = ROOT / "src/legacy_routes/core_public.py"
TEST_SOURCE = ROOT / "tests/test_readiness_endpoint.py"


def _health_contract_detects_probe_call(insert_probe):
    app = flask.Flask("readiness_guard_isolation")
    core_public = types.ModuleType("isolated_health_routes")
    core_public.__dict__.update({
        "app": app,
        "jsonify": flask.jsonify,
        "database_ready": lambda: False,
        "should_track_discovery_path": lambda _path: False,
    })
    tree = ast.parse(PUBLIC_SOURCE.read_text())
    routes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in {"health", "ready"}]
    assert len(routes) == 2
    if insert_probe:
        health = next(node for node in routes if node.name == "health")
        health.body.insert(0, ast.Expr(value=ast.Call(func=ast.Name(id="database_ready", ctx=ast.Load()), args=[], keywords=[])))
    exec(compile(ast.fix_missing_locations(ast.Module(body=routes, type_ignores=[])), str(PUBLIC_SOURCE), "exec"), core_public.__dict__)

    tests = ast.parse(TEST_SOURCE.read_text())
    selected = [node for node in tests.body if isinstance(node, ast.FunctionDef) and node.name == "test_ready_response_is_generic_and_health_remains_db_free"]
    assert len(selected) == 1
    namespace = {"main": types.SimpleNamespace(app=app), "core_public": core_public}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(TEST_SOURCE), "exec"), namespace)
    monkeypatch = pytest.MonkeyPatch()
    try:
        namespace[selected[0].name](monkeypatch)
    except AssertionError:
        return True
    finally:
        monkeypatch.undo()
    return False


class ReadinessGuardIsolationTests(unittest.TestCase):
    def test_current_health_contract_passes_without_database_probe(self):
        self.assertFalse(_health_contract_detects_probe_call(False))

    def test_health_contract_detects_database_probe_regression(self):
        self.assertTrue(_health_contract_detects_probe_call(True))
