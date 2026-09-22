"""AST-isolated regression tests for legacy Yandex parser console diagnostics."""

from __future__ import annotations

import ast
import copy
from contextlib import ExitStack, redirect_stdout
import io
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import unittest
from unittest.mock import patch


SOURCE_PATH = Path(__file__).parents[1] / "src" / "yandex_maps_scraper.py"
SYNTHETIC_MARKER = "synthetic-private-legacy-parser-marker"


def _source_text():
    if "--source-stdin" in sys.argv:
        sys.argv.remove("--source-stdin")
        return sys.stdin.read()
    return SOURCE_PATH.read_text(encoding="utf-8")


SOURCE_TEXT = _source_text()


def _tree():
    return ast.parse(SOURCE_TEXT, filename=str(SOURCE_PATH))


def _function(tree, name):
    return next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)


def _is_print(statement):
    return (
        isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Call)
        and isinstance(statement.value.func, ast.Name)
        and statement.value.func.id == "print"
    )


def _completion_print(function):
    for node in ast.walk(function):
        body = getattr(node, "body", [])
        for index, statement in enumerate(body[:-2]):
            if (
                isinstance(statement, ast.Expr)
                and isinstance(statement.value, ast.Call)
                and isinstance(statement.value.func, ast.Attribute)
                and isinstance(statement.value.func.value, ast.Name)
                and statement.value.func.value.id == "browser"
                and statement.value.func.attr == "close"
                and _is_print(body[index + 1])
                and isinstance(body[index + 2], ast.Return)
                and isinstance(body[index + 2].value, ast.Name)
                and body[index + 2].value.id == "data"
            ):
                return body[index + 1]
    raise AssertionError("legacy completion diagnostic not found")


def _overview_handler(function):
    for candidate in ast.walk(function):
        if isinstance(candidate, ast.Try) and any(
            isinstance(statement, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "overview_tab" for target in statement.targets)
            for statement in candidate.body
        ):
            return candidate.handlers[0]
    raise AssertionError("legacy overview fallback handler not found")


def _compile_module(body, namespace):
    module = ast.fix_missing_locations(ast.Module(body=body, type_ignores=[]))
    exec(compile(module, str(SOURCE_PATH), "exec"), namespace)
    return namespace


def _capture(callback):
    output = io.StringIO()
    with redirect_stdout(output):
        result = callback()
    return result, output.getvalue()


def _capture_exception(callback):
    output = io.StringIO()
    with redirect_stdout(output):
        try:
            callback()
        except Exception as error:
            return output.getvalue(), error
    raise AssertionError("expected legacy parser branch to raise")


def _deny_external_side_effects(*_args, **_kwargs):
    raise AssertionError("unexpected external side effect")


def _guard_external_side_effects(stack):
    targets = [
        "socket.socket.connect",
        "socket.socket.connect_ex",
        "subprocess.Popen",
        "os.system",
        "os.posix_spawn",
        "os.posix_spawnp",
        "sqlite3.connect",
    ]
    targets.extend(
        f"os.{name}"
        for name in ("spawnv", "spawnve", "spawnvp", "spawnvpe")
        if hasattr(os, name)
    )
    for target in targets:
        stack.enter_context(patch(target, side_effect=_deny_external_side_effects))


class LegacyParserDiagnosticLogsTests(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        _guard_external_side_effects(stack)

    def test_browser_launch_fallback_omits_exception_text_and_preserves_failure(self):
        launch_browser = copy.deepcopy(_function(_tree(), "_launch_browser"))
        probe = _compile_module([launch_browser], {})["_launch_browser"]
        attempts = []

        class UnavailableBrowser:
            def __init__(self, name):
                self.name = name

            def launch(self, **_kwargs):
                attempts.append(self.name)
                raise RuntimeError(SYNTHETIC_MARKER)

        playwright = type(
            "Playwright",
            (),
            {
                "chromium": UnavailableBrowser("Chromium"),
                "firefox": UnavailableBrowser("Firefox"),
                "webkit": UnavailableBrowser("WebKit"),
            },
        )()

        stdout, error = _capture_exception(lambda: probe(playwright))

        self.assertEqual(str(error), "Не удалось запустить ни один браузер")
        self.assertEqual(attempts, ["Chromium", "Firefox", "WebKit"])
        self.assertEqual(
            stdout.splitlines(),
            [
                "Chromium недоступен: launch_failed",
                "Firefox недоступен: launch_failed",
                "WebKit недоступен: launch_failed",
            ],
        )
        self.assertNotIn(SYNTHETIC_MARKER, stdout)

    def test_entry_diagnostic_omits_url_and_leaves_url_value_unchanged(self):
        function = _function(_tree(), "parse_yandex_card")
        entry_print = copy.deepcopy(next(statement for statement in function.body if _is_print(statement)))
        scaffold = ast.parse(
            """
def exercise(url):
    pass
"""
        )
        probe = scaffold.body[0]
        assert isinstance(probe, ast.FunctionDef)
        probe.body = [entry_print, ast.Return(value=ast.Name(id="url", ctx=ast.Load()))]
        exercise = _compile_module([probe], {})["exercise"]

        result, stdout = _capture(lambda: exercise(SYNTHETIC_MARKER))

        self.assertEqual(result, SYNTHETIC_MARKER)
        self.assertEqual(stdout, "Начинаем legacy-парсинг Яндекс.Карт\n")
        self.assertNotIn(SYNTHETIC_MARKER, stdout)

    def test_overview_fallback_omits_exception_text_and_continues(self):
        function = _function(_tree(), "parse_yandex_card")
        handler = _overview_handler(function)
        scaffold = ast.parse(
            """
def exercise(marker):
    try:
        raise RuntimeError(marker)
    except Exception:
        pass
    return "continued"
"""
        )
        probe = scaffold.body[0]
        assert isinstance(probe, ast.FunctionDef)
        try_node = next(node for node in probe.body if isinstance(node, ast.Try))
        try_node.handlers = [copy.deepcopy(handler)]
        exercise = _compile_module([probe], {})["exercise"]

        result, stdout = _capture(lambda: exercise(SYNTHETIC_MARKER))

        self.assertEqual(result, "continued")
        self.assertEqual(stdout, "Вкладка 'Обзор' недоступна; продолжаем с fallback\n")
        self.assertNotIn(SYNTHETIC_MARKER, stdout)

    def test_completion_diagnostic_omits_title_and_address_and_returns_same_data(self):
        function = _function(_tree(), "parse_yandex_card")
        completion_print = copy.deepcopy(_completion_print(function))
        scaffold = ast.parse(
            """
def exercise(data, browser_name):
    pass
"""
        )
        probe = scaffold.body[0]
        assert isinstance(probe, ast.FunctionDef)
        probe.body = [completion_print, ast.Return(value=ast.Name(id="data", ctx=ast.Load()))]
        exercise = _compile_module([probe], {})["exercise"]
        data = {"title": SYNTHETIC_MARKER, "address": SYNTHETIC_MARKER}

        result, stdout = _capture(lambda: exercise(data, "synthetic-browser"))

        self.assertIs(result, data)
        self.assertEqual(data["title"], SYNTHETIC_MARKER)
        self.assertEqual(data["address"], SYNTHETIC_MARKER)
        self.assertEqual(stdout, "Legacy-парсинг завершен\n")
        self.assertNotIn(SYNTHETIC_MARKER, stdout)


class LegacyParserDiagnosticGuardTests(unittest.TestCase):
    def test_guard_denies_complete_entry_point_set_and_restores_socket_methods(self):
        originals = [
            (socket.socket, "connect", socket.socket.connect),
            (socket.socket, "connect_ex", socket.socket.connect_ex),
            (subprocess, "Popen", subprocess.Popen),
            (os, "system", os.system),
            (os, "posix_spawn", os.posix_spawn),
            (os, "posix_spawnp", os.posix_spawnp),
            (sqlite3, "connect", sqlite3.connect),
        ]
        originals.extend(
            (os, name, getattr(os, name))
            for name in ("spawnv", "spawnve", "spawnvp", "spawnvpe")
            if hasattr(os, name)
        )
        stack = ExitStack()
        probe = socket.socket()
        try:
            _guard_external_side_effects(stack)
            for callback in (
                lambda: probe.connect(("127.0.0.1", 1)),
                lambda: probe.connect_ex(("127.0.0.1", 1)),
                lambda: sqlite3.connect(":memory:"),
                lambda: subprocess.Popen(["not-run"]),
                lambda: os.system("not-run"),
                lambda: os.posix_spawn("not-run", ["not-run"], {}),
                lambda: os.posix_spawnp("not-run", ["not-run"], {}),
            ):
                with self.assertRaisesRegex(AssertionError, "unexpected external side effect"):
                    callback()
            for name in ("spawnv", "spawnve", "spawnvp", "spawnvpe"):
                if not hasattr(os, name):
                    continue
                arguments = (os.P_WAIT, "not-run", ["not-run"])
                if name in {"spawnve", "spawnvpe"}:
                    arguments = (*arguments, {})
                with self.assertRaisesRegex(AssertionError, "unexpected external side effect"):
                    getattr(os, name)(*arguments)
        finally:
            stack.close()
            probe.close()

        for owner, name, original in originals:
            self.assertIs(getattr(owner, name), original)

    def test_unittest_cleanup_restores_guard_when_setup_raises(self):
        original_connect_ex = socket.socket.connect_ex
        original_popen = subprocess.Popen

        class SetupFailureCase(unittest.TestCase):
            def setUp(self):
                stack = ExitStack()
                self.addCleanup(stack.close)
                _guard_external_side_effects(stack)
                raise RuntimeError("synthetic setup failure")

            def test_never_runs(self):
                self.fail("setup failure must prevent this test")

        result = unittest.TestResult()
        SetupFailureCase("test_never_runs").run(result)

        self.assertEqual(len(result.errors), 1)
        self.assertEqual(result.failures, [])
        self.assertIn("RuntimeError: synthetic setup failure", result.errors[0][1])
        self.assertIs(socket.socket.connect_ex, original_connect_ex)
        self.assertIs(subprocess.Popen, original_popen)


if __name__ == "__main__":
    unittest.main()
