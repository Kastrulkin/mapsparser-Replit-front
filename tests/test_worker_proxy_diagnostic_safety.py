"""AST-isolated proxy diagnostic privacy checks; never import worker runtime."""

from __future__ import annotations

import ast
import copy
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import random
import re
import runpy
import sys
import time
import types
import unittest
from urllib.parse import quote


WORKER_SOURCE = Path(__file__).parents[1] / "src" / "worker.py"
MARKER = "synthetic-private-proxy-diagnostic-marker"


def _source_text() -> str:
    if "--source-stdin" in sys.argv:
        sys.argv.remove("--source-stdin")
        return sys.stdin.read()
    return WORKER_SOURCE.read_text(encoding="utf-8")


SOURCE_TEXT = _source_text()


def _tree():
    return ast.parse(SOURCE_TEXT, filename=str(WORKER_SOURCE))


def _function(name: str):
    matches = [node for node in _tree().body if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(matches) != 1:
        raise AssertionError(f"expected one worker function: {name}")
    return copy.deepcopy(matches[0])


def _compile_function(name: str, namespace):
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    module = ast.Module(body=[future, _function(name)], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(WORKER_SOURCE), "exec"), namespace)


def _compile_optional_projection_helper(namespace):
    if any(
        isinstance(node, ast.FunctionDef) and node.name == "_proxy_preflight_diagnostic_reason"
        for node in _tree().body
    ):
        _compile_function("_proxy_preflight_diagnostic_reason", namespace)


def _selected_proxy_preflight_branch():
    task = _function("_execute_map_card_task")
    matches = []
    for node in ast.walk(task):
        if not isinstance(node, ast.If):
            continue
        if ast.unparse(node.test) != "parsed_source == 'yandex_maps' and active_proxy":
            continue
        if any(
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Name)
            and child.func.id == "_preflight_yandex_proxy"
            for child in ast.walk(node)
        ):
            matches.append(copy.deepcopy(node))
    if len(matches) != 1:
        raise AssertionError("expected one selected-proxy preflight branch")
    return matches[0]


def _compile_preflight_chain(namespace):
    _compile_function("_preflight_yandex_proxy", namespace)
    _compile_optional_projection_helper(namespace)
    scaffold = ast.parse(
        "def exercise_preflight():\n"
        "    parsed_source = 'yandex_maps'\n"
        "    active_proxy = {'id': 'proxy-fixed', 'proxy': {'server': 'http://proxy.invalid:33335'}}\n"
        "    proxy_id = 'proxy-fixed'\n"
        "    native_failure_reason = ''\n"
        "    url = 'https://example.invalid/maps/org/123/'\n"
        "    pass\n"
        "    return active_proxy, proxy_id, native_failure_reason\n",
    ).body[0]
    scaffold.body[-2:-1] = [_selected_proxy_preflight_branch()]
    module = ast.Module(body=[scaffold], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(WORKER_SOURCE), "exec"), namespace)


def _compile_reviews_delta_task(namespace):
    _compile_optional_projection_helper(namespace)
    _compile_function("_process_yandex_reviews_delta_task", namespace)


class _Cursor:
    def __init__(self, *, fail=False):
        self.calls = []
        self.fail = fail
        self.closed = False

    def execute(self, query, params):
        self.calls.append((query, params))
        if self.fail:
            raise RuntimeError(MARKER)

    def close(self):
        self.closed = True


class _Connection:
    def __init__(self, cursor):
        self.cursor_obj = cursor
        self.committed = False
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def _capture(callback):
    output = io.StringIO()
    with redirect_stdout(output):
        value = callback()
    return value, output.getvalue()


def _namespace(*, request_get, mark_result):
    sensitive = runpy.run_path(str(WORKER_SOURCE.parent / "core" / "sensitive_text.py"))

    class RequestException(Exception):
        pass

    return {
        "Any": object,
        "Dict": dict,
        "Optional": object,
        "os": os,
        "quote": quote,
        "random": random,
        "re": re,
        "time": time,
        "requests": types.SimpleNamespace(RequestException=RequestException, get=request_get),
        "_HUMAN_USER_AGENTS": ["synthetic-agent"],
        "redact_sensitive_text": sensitive["redact_sensitive_text"],
        "_mark_proxy_result": mark_result,
    }


class WorkerProxyDiagnosticSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def deny_external_effects(event, _args):
            if event in {
                "socket.connect",
                "subprocess.Popen",
                "os.system",
                "os.posix_spawn",
                "os.spawn",
                "sqlite3.connect",
            }:
                raise AssertionError(f"unexpected external effect: {event}")

        sys.addaudithook(deny_external_effects)

    def test_request_exception_reason_stays_internal_but_selected_proxy_console_is_value_free(self):
        marks = []
        namespace = _namespace(
            request_get=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                namespace["requests"].RequestException(MARKER),
            ),
            mark_result=lambda *args, **kwargs: marks.append((args, kwargs)),
        )
        _compile_preflight_chain(namespace)
        (active_proxy, proxy_id, native_failure_reason), output = _capture(namespace["exercise_preflight"])
        self.assertIsNone(active_proxy)
        self.assertEqual(proxy_id, "")
        self.assertEqual(len(marks), 1)
        self.assertIn(MARKER, marks[0][1]["reason"])
        self.assertNotIn(MARKER, native_failure_reason)
        self.assertNotIn(MARKER, output)
        self.assertIn("Proxy preflight", output)

    def test_successful_preflight_keeps_ok_status_and_elapsed_contract(self):
        class Response:
            status_code = 200
            url = "https://example.invalid/maps/org/123/"
            text = "x" * 1200 + "123"

        namespace = _namespace(
            request_get=lambda *_args, **_kwargs: Response(),
            mark_result=lambda *_args, **_kwargs: None,
        )
        _compile_function("_preflight_yandex_proxy", namespace)
        result = namespace["_preflight_yandex_proxy"](
            "https://example.invalid/maps/org/123/",
            {"proxy": {"server": "http://proxy.invalid:33335"}},
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["reason"], "ok")
        self.assertEqual(result["status"], 200)
        self.assertIsInstance(result["elapsed_ms"], int)

    def test_proxy_stats_exception_console_omits_raw_reason_and_db_error(self):
        cursor = _Cursor(fail=True)
        connection = _Connection(cursor)
        namespace = {"Optional": object, "os": os, "get_db_connection": lambda: connection}
        _compile_function("_mark_proxy_result", namespace)
        _value, output = _capture(
            lambda: namespace["_mark_proxy_result"]("proxy-fixed", success=False, reason=MARKER),
        )
        self.assertEqual(len(cursor.calls), 1)
        self.assertNotIn(MARKER, output)
        self.assertTrue(cursor.closed)
        self.assertTrue(connection.closed)

    def test_proxy_failure_decision_and_cleanup_keep_fatal_and_transient_controls(self):
        for reason, expected_fatal in (("navigation timeout", True), ("unclassified failure", False)):
            cursor = _Cursor()
            connection = _Connection(cursor)
            namespace = {"Optional": object, "os": os, "get_db_connection": lambda: connection}
            _compile_function("_mark_proxy_result", namespace)
            _value, output = _capture(
                lambda: namespace["_mark_proxy_result"]("proxy-fixed", success=False, reason=reason),
            )
            self.assertEqual(output, "")
            self.assertEqual(cursor.calls[0][1][0], expected_fatal)
            self.assertTrue(connection.committed)
            self.assertTrue(cursor.closed)
            self.assertTrue(connection.closed)

    def test_reviews_delta_preflight_failure_keeps_raw_mark_input_but_not_stdout_or_worker_error(self):
        result = self._run_reviews_delta_preflight_failure(use_apify_fallback=False)
        self.assertEqual(len(result["marks"]), 1)
        self.assertIn(MARKER, result["marks"][0][1]["reason"])
        self.assertEqual(result["worker_errors"][0][0], "queue-fixed")
        self.assertNotIn(MARKER, result["worker_errors"][0][1] + result["output"])
        self.assertTrue(result["initial_cursor"].closed)
        self.assertTrue(result["initial_connection"].closed)

    def test_reviews_delta_apify_fallback_warning_and_metrics_omit_preflight_value(self):
        result = self._run_reviews_delta_preflight_failure(use_apify_fallback=True)
        self.assertEqual(len(result["marks"]), 1)
        self.assertIn(MARKER, result["marks"][0][1]["reason"])
        self.assertEqual(result["worker_errors"], [])
        self.assertNotIn(MARKER, result["output"] + repr(result["fallback_cursor"].calls))
        self.assertTrue(result["fallback_connection"].committed)
        self.assertTrue(result["fallback_cursor"].closed)
        self.assertTrue(result["fallback_connection"].closed)

    def test_reviews_full_apify_fallback_preserves_full_route_and_zero_delta_limit(self):
        result = self._run_reviews_delta_preflight_failure(
            use_apify_fallback=True,
            task_type="reviews_full",
        )
        self.assertEqual(result["fetch_calls"][0][1]["max_reviews"], 0)
        self.assertEqual(result["full_snapshot_calls"][0][1]["business_id"], "business-fixed")
        self.assertEqual(result["fallback_cursor"].calls[0][1][0], "completed")
        self.assertEqual(result["fallback_cursor"].calls[0][1][-1], "queue-fixed")
        self.assertNotIn(MARKER, result["output"] + repr(result["fallback_cursor"].calls))

    def _run_reviews_delta_preflight_failure(self, *, use_apify_fallback, task_type="reviews_delta"):
        cursor = _Cursor()
        connection = _Connection(cursor)
        fallback_cursor = _Cursor()
        fallback_connection = _Connection(fallback_cursor)
        marks = []
        worker_errors = []
        fetch_calls = []
        full_snapshot_calls = []
        connections = [connection]
        if use_apify_fallback:
            connections.append(fallback_connection)
        namespace = {
            "Any": object,
            "Dict": dict,
            "os": os,
            "json": json,
            "re": re,
            "time": time,
            "STATUS_COMPLETED": "completed",
            "get_db_connection": lambda: connections.pop(0),
            "load_known_yandex_review_ids": lambda *_args, **_kwargs: [],
            "load_expected_yandex_reviews_total": lambda *_args, **_kwargs: 0,
            "get_use_apify_map_parsing": lambda _connection: use_apify_fallback,
            "_get_next_proxy_for_playwright": lambda: {"id": "proxy-fixed", "proxy": {}},
            "_preflight_yandex_proxy": lambda *_args, **_kwargs: {
                "ok": False,
                "reason": "RequestException:" + MARKER,
                "elapsed_ms": 7,
            },
            "_mark_proxy_result": lambda *args, **kwargs: marks.append((args, kwargs)),
            "redact_sensitive_text": runpy.run_path(
                str(WORKER_SOURCE.parent / "core" / "sensitive_text.py"),
            )["redact_sensitive_text"],
            "_handle_worker_error": lambda queue_id, reason: worker_errors.append((queue_id, reason)),
            "fetch_complete_yandex_reviews": lambda *args, **kwargs: (fetch_calls.append((args, kwargs)) or []),
            "apply_yandex_review_delta": lambda *_args, **_kwargs: {"normalized": 0},
            "apply_complete_review_snapshot": lambda *args, **kwargs: (full_snapshot_calls.append((args, kwargs)) or {"total": 0}),
            "handle_review_sync_completion": lambda *_args, **_kwargs: None,
        }
        _compile_reviews_delta_task(namespace)
        _value, output = _capture(
            lambda: namespace["_process_yandex_reviews_delta_task"](
                {
                    "id": "queue-fixed",
                    "business_id": "business-fixed",
                    "url": "https://example.invalid/map",
                    "task_type": task_type,
                },
            ),
        )
        return {
            "initial_cursor": cursor,
            "initial_connection": connection,
            "fallback_cursor": fallback_cursor,
            "fallback_connection": fallback_connection,
            "fetch_calls": fetch_calls,
            "full_snapshot_calls": full_snapshot_calls,
            "marks": marks,
            "output": output,
            "worker_errors": worker_errors,
        }


if __name__ == "__main__":
    unittest.main()
