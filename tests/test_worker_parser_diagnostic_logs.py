"""AST-isolated regression tests for value-free worker parser diagnostics."""

from __future__ import annotations

import ast
import copy
from contextlib import redirect_stdout
import io
from pathlib import Path
import sys
import unittest


WORKER_SOURCE = Path(__file__).parents[1] / "src" / "worker.py"
SYNTHETIC_MARKER = "synthetic-private-worker-parser-marker"


def _worker_tree():
    return ast.parse(WORKER_SOURCE.read_text(encoding="utf-8"), filename=str(WORKER_SOURCE))


def _execute_task_node(tree):
    return next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_execute_map_card_task")


def _direct_parser_exception_handler(tree):
    function = _execute_task_node(tree)
    return next(
        node
        for node in ast.walk(function)
        if isinstance(node, ast.ExceptHandler)
        and node.name == "e"
        and any(
            isinstance(statement, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "msg" for target in statement.targets)
            for statement in node.body
        )
    )


def _subprocess_exception_body(tree):
    function = _execute_task_node(tree)
    return next(
        node.body
        for node in ast.walk(function)
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == "card_error"
        and len(node.test.ops) == 1
        and isinstance(node.test.ops[0], ast.Eq)
        and len(node.test.comparators) == 1
        and isinstance(node.test.comparators[0], ast.Constant)
        and node.test.comparators[0].value == "parser_subprocess_exception"
    )


def _compile_direct_exception_probe(namespace):
    handler = copy.deepcopy(_direct_parser_exception_handler(_worker_tree()))
    scaffold = ast.parse(
        """
def exercise(marker):
    active_proxy = {"id": "synthetic-proxy"}
    parsed_source = "yandex_maps"
    proxy_id = "synthetic-proxy"
    url = marker
    cookies = {}
    debug_bundle_id = "synthetic-bundle"
    geolocation_kwarg = {}
    bundle_dir = None
    try:
        raise RuntimeError(marker)
    except Exception:
        pass
    return card_data
"""
    )
    function = scaffold.body[0]
    assert isinstance(function, ast.FunctionDef)
    try_node = next(node for node in function.body if isinstance(node, ast.Try))
    try_node.handlers = [handler]
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    exec(compile(module, str(WORKER_SOURCE), "exec"), namespace)
    return namespace["exercise"]


def _compile_subprocess_probe(namespace):
    body = copy.deepcopy(_subprocess_exception_body(_worker_tree()))
    scaffold = ast.parse(
        """
def exercise(card_data):
    active_proxy = {"id": "synthetic-proxy"}
    parsed_source = "yandex_maps"
    proxy_id = "synthetic-proxy"
    url = "synthetic-url"
    cookies = {}
    debug_bundle_id = "synthetic-bundle"
    geolocation_kwarg = {}
    card_error = str(card_data.get("error") or "").strip()
    if card_error == "parser_subprocess_exception":
        pass
    return card_data
"""
    )
    function = scaffold.body[0]
    assert isinstance(function, ast.FunctionDef)
    target_if = next(
        node for node in function.body if isinstance(node, ast.If) and isinstance(node.test, ast.Compare)
    )
    target_if.body = body
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    exec(compile(module, str(WORKER_SOURCE), "exec"), namespace)
    return namespace["exercise"]


def _profile():
    return {
        "user_agent": "synthetic-agent",
        "viewport": {"width": 1, "height": 1},
        "launch_args": [],
        "init_scripts": [],
    }


def _capture(callback):
    output = io.StringIO()
    with redirect_stdout(output):
        callback()
    return output.getvalue()


def _capture_exception(callback):
    output = io.StringIO()
    with redirect_stdout(output):
        try:
            callback()
        except Exception as error:
            return output.getvalue(), error
    raise AssertionError("expected parser retry to raise")


class WorkerParserDiagnosticLogsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def deny_external_side_effects(event, _args):
            if event in {
                "socket.connect",
                "subprocess.Popen",
                "os.system",
                "os.posix_spawn",
                "os.spawn",
                "sqlite3.connect",
            }:
                raise AssertionError(f"unexpected external side effect: {event}")

        sys.addaudithook(deny_external_side_effects)

    def test_direct_proxy_exception_omits_synthetic_exception_text_and_keeps_retry(self):
        attempts = []
        proxy_results = []
        retry_result = {"title": "synthetic"}

        def parser(*_args, **_kwargs):
            attempts.append(True)
            return retry_result

        probe = _compile_direct_exception_probe(
            {
                "ACTIVE_CAPTCHA_SESSIONS": {},
                "_build_human_browser_profile": _profile,
                "_is_playwright_sync_in_async_error": lambda _message: False,
                "_mark_proxy_result": lambda *args, **kwargs: proxy_results.append((args, kwargs)),
                "_parse_yandex_card_with_playwright_fallback": parser,
            }
        )

        results = []
        stdout = _capture(lambda: results.append(probe(SYNTHETIC_MARKER)))

        self.assertEqual(len(attempts), 1)
        self.assertIs(results[0], retry_result)
        self.assertEqual(len(proxy_results), 1)
        self.assertEqual(proxy_results[0][1]["reason"], SYNTHETIC_MARKER)
        self.assertNotIn(SYNTHETIC_MARKER, stdout)
        self.assertIn("parser_exception | retry without proxy", stdout)

    def test_subprocess_successful_retry_replaces_result_without_logging_input_values(self):
        calls = []
        retry_result = {"title": "synthetic"}

        def parser(*args, **kwargs):
            calls.append((args, kwargs))
            return retry_result

        probe = _compile_subprocess_probe(
            {
                "ACTIVE_CAPTCHA_SESSIONS": {},
                "_build_human_browser_profile": _profile,
                "_parse_yandex_card_with_playwright_fallback": parser,
            }
        )
        initial_card_data = {
            "error": "parser_subprocess_exception",
            "message": SYNTHETIC_MARKER,
            "traceback": SYNTHETIC_MARKER,
        }

        results = []
        stdout = _capture(lambda: results.append(probe(initial_card_data)))

        self.assertIs(results[0], retry_result)
        self.assertEqual(initial_card_data["message"], SYNTHETIC_MARKER)
        self.assertEqual(initial_card_data["traceback"], SYNTHETIC_MARKER)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], ("synthetic-url",))
        self.assertIsNone(calls[0][1]["proxy"])
        self.assertTrue(calls[0][1]["keep_open_on_captcha"])
        self.assertNotIn(SYNTHETIC_MARKER, stdout)
        self.assertIn("Retry without proxy succeeded after parser_subprocess_exception", stdout)

    def test_direct_proxy_retry_exception_omits_synthetic_exception_text_and_reraises(self):
        calls = []

        def parser(*args, **kwargs):
            calls.append((args, kwargs))
            raise RuntimeError(SYNTHETIC_MARKER)

        probe = _compile_direct_exception_probe(
            {
                "ACTIVE_CAPTCHA_SESSIONS": {},
                "_build_human_browser_profile": _profile,
                "_is_playwright_sync_in_async_error": lambda _message: False,
                "_mark_proxy_result": lambda *_args, **_kwargs: None,
                "_parse_yandex_card_with_playwright_fallback": parser,
            }
        )

        stdout, error = _capture_exception(lambda: probe(SYNTHETIC_MARKER))

        self.assertIsInstance(error, RuntimeError)
        self.assertEqual(str(error), SYNTHETIC_MARKER)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], (SYNTHETIC_MARKER,))
        self.assertIsNone(calls[0][1]["proxy"])
        self.assertTrue(calls[0][1]["keep_open_on_captcha"])
        self.assertNotIn(SYNTHETIC_MARKER, stdout)

    def test_subprocess_message_traceback_and_retry_result_omit_synthetic_values(self):
        calls = []

        def parser(*_args, **_kwargs):
            calls.append((_args, _kwargs))
            return {"error": SYNTHETIC_MARKER}

        probe = _compile_subprocess_probe(
            {
                "ACTIVE_CAPTCHA_SESSIONS": {},
                "_build_human_browser_profile": _profile,
                "_parse_yandex_card_with_playwright_fallback": parser,
            }
        )
        card_data = {
            "error": "parser_subprocess_exception",
            "message": SYNTHETIC_MARKER,
            "traceback": SYNTHETIC_MARKER,
        }

        results = []
        stdout = _capture(lambda: results.append(probe(card_data)))
        result = results[0]

        self.assertIs(result, card_data)
        self.assertEqual(card_data["message"], SYNTHETIC_MARKER)
        self.assertEqual(card_data["traceback"], SYNTHETIC_MARKER)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], ("synthetic-url",))
        self.assertIsNone(calls[0][1]["proxy"])
        self.assertTrue(calls[0][1]["keep_open_on_captcha"])
        self.assertNotIn(SYNTHETIC_MARKER, stdout)

    def test_subprocess_retry_exception_omits_synthetic_exception_text(self):
        calls = []

        def parser(*_args, **_kwargs):
            calls.append((_args, _kwargs))
            raise RuntimeError(SYNTHETIC_MARKER)

        probe = _compile_subprocess_probe(
            {
                "ACTIVE_CAPTCHA_SESSIONS": {},
                "_build_human_browser_profile": _profile,
                "_parse_yandex_card_with_playwright_fallback": parser,
            }
        )
        card_data = {"error": "parser_subprocess_exception"}

        stdout = _capture(lambda: probe(card_data))

        self.assertEqual(len(calls), 1)
        self.assertIsNone(calls[0][1]["proxy"])
        self.assertIn("Retry without proxy failed: parser_exception", stdout)
        self.assertNotIn(SYNTHETIC_MARKER, stdout)


if __name__ == "__main__":
    unittest.main()
