"""Synthetic, AST-isolated worker diagnostics; never import the worker runtime."""

from __future__ import annotations

import ast
import copy
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import runpy
import sys
import types
import unittest


WORKER_SOURCE = Path(__file__).parents[1] / "src" / "worker.py"
MARKER = "synthetic-private-worker-artifact-marker"


def _worker_tree():
    return ast.parse(WORKER_SOURCE.read_text(encoding="utf-8"))


def _task():
    return next(node for node in _worker_tree().body
                if isinstance(node, ast.FunctionDef) and node.name == "_execute_map_card_task")


def _if_with_expression(expression, required_call=None):
    expected = ast.dump(ast.parse(expression, mode="eval").body)
    candidates = [node for node in ast.walk(_task())
                  if isinstance(node, ast.If) and ast.dump(node.test) == expected
                  and (required_call is None or any(
                      isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
                      and child.func.id == required_call for child in ast.walk(node)))]
    assert len(candidates) == 1, "must exercise exactly one current runtime branch"
    return candidates[0]


def _run_nodes(nodes, namespace):
    scaffold = ast.parse("def exercise(card_data=None):\n    pass\n").body[0]
    scaffold.body = copy.deepcopy(nodes)
    module = ast.fix_missing_locations(ast.Module(body=[scaffold], type_ignores=[]))
    exec(compile(module, str(WORKER_SOURCE), "exec"), namespace)
    namespace["exercise"](namespace.get("card_data"))


class _MemoryFile(io.StringIO):
    def __exit__(self, *_args):
        # Keep the generated artifact available for assertions after with/open.
        return False


def _namespace(*, fail_open=False):
    artifacts = {}

    def open_memory(path, mode="w", **_kwargs):
        if fail_open:
            raise OSError(MARKER)
        if mode == "r":
            existing = artifacts[os.path.basename(path)]
            existing.seek(0)
            return existing
        output = _MemoryFile()
        artifacts[os.path.basename(path)] = output
        return output

    helpers = runpy.run_path(str(WORKER_SOURCE.parent / "core" / "parser_debug_artifacts.py"))
    return {
        "open": open_memory,
        "os": types.SimpleNamespace(path=os.path, makedirs=lambda *_a, **_k: None),
        "json": json,
        "debug_value_shape": helpers["debug_value_shape"],
        "debug_url_summary": helpers["debug_url_summary"],
        "bundle_dir": "/synthetic-bundle",
    }, artifacts


def _stdout(callback):
    stream = io.StringIO()
    with redirect_stdout(stream):
        callback()
    return stream.getvalue()


class WorkerParserArtifactSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def deny_external_effects(event, _args):
            if event in {"socket.connect", "subprocess.Popen", "os.system",
                         "os.posix_spawn", "os.spawn", "sqlite3.connect"}:
                raise AssertionError(f"unexpected external effect: {event}")
        sys.addaudithook(deny_external_effects)

    def _exercise_payload_artifacts(self, fail_open=False):
        namespace, artifacts = _namespace(fail_open=fail_open)
        apify = {"run_id": MARKER, "usage_total_usd": 0.25,
                 "run_data": {"usageTotalUsd": 0.25}, "run_input": {MARKER: MARKER},
                 "item_preview": {"phone": MARKER}}
        validation = {"warnings": [MARKER], "quality_score": 0.5,
                      "hard_missing": [MARKER], "missing_fields": [MARKER],
                      "found_fields": [MARKER]}
        card = {"warnings": [MARKER], "title": MARKER}
        namespace.update(apify_debug_payload=apify, validation_result=validation,
                         card_data=card, reason=MARKER, is_successful=False)
        before = copy.deepcopy((apify, validation, card))
        output = _stdout(lambda: _run_nodes([
            _if_with_expression("bundle_dir and apify_debug_payload"),
            _if_with_expression("bundle_dir and validation_result"),
        ], namespace))
        self.assertEqual((apify, validation, card), before)
        # Billing must receive the original payload, including exact cost/run ID.
        self.assertIs(namespace["apify_debug_payload"], apify)
        self.assertEqual(apify["usage_total_usd"], 0.25)
        return artifacts, output

    def test_apify_and_validation_artifacts_omit_values_without_mutating_results(self):
        artifacts, output = self._exercise_payload_artifacts()
        self.assertEqual(set(artifacts), {"apify_debug.json", "validation.json"})
        for filename, artifact in artifacts.items():
            with self.subTest(filename=filename):
                payload = json.loads(artifact.getvalue())
                self.assertNotIn(MARKER, artifact.getvalue())
                self.assertEqual(payload["diagnostics_version"], 2)
        self.assertNotIn(MARKER, output)

    def test_artifact_write_failures_omit_exception_text(self):
        artifacts, output = self._exercise_payload_artifacts(fail_open=True)
        self.assertEqual(artifacts, {})
        self.assertIn("apify_debug.json", output)
        self.assertIn("validation.json", output)
        self.assertNotIn(MARKER, output)

    def _exercise_async_failure(self, fail_open=False, fail_handler=False):
        namespace, artifacts = _namespace(fail_open=fail_open)
        errors = []

        def handle(queue_id, message):
            errors.append((queue_id, message))
            if fail_handler:
                raise RuntimeError(MARKER)

        namespace.update(msg="Playwright Sync API inside asyncio loop " + MARKER,
                         e=RuntimeError(MARKER), queue_dict={"id": "synthetic-queue"},
                         _handle_worker_error=handle,
                         traceback=types.SimpleNamespace(format_exc=lambda: MARKER))
        branch = _if_with_expression("_is_playwright_sync_in_async_error(msg)")
        output = _stdout(lambda: _run_nodes(branch.body, namespace))
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0][0], "synthetic-queue")
        self.assertIn("playwright_sync_in_async_loop", errors[0][1])
        self.assertNotIn(MARKER, errors[0][1])
        return artifacts, output

    def test_sync_in_async_crash_artifact_omits_exception_and_traceback(self):
        artifacts, output = self._exercise_async_failure()
        self.assertEqual(set(artifacts), {"exception.txt"})
        persisted = artifacts["exception.txt"].getvalue()
        self.assertIn("Playwright Sync-in-async crash", persisted)
        self.assertNotIn(MARKER, persisted + output)

    def test_sync_in_async_write_and_status_failures_omit_exception_text(self):
        artifacts, output = self._exercise_async_failure(fail_open=True, fail_handler=True)
        self.assertEqual(artifacts, {})
        self.assertIn("exception.txt", output)
        self.assertIn("parsequeue", output)
        self.assertNotIn(MARKER, output)

    def _exercise_normalization(self, fallback):
        namespace, _ = _namespace()
        card = {} if fallback else {"title_or_name": MARKER}
        calls = []

        def promote(payload):
            payload[MARKER] = MARKER
            return payload

        def load_identity(business_id):
            calls.append(business_id)
            return {"name": MARKER, "address": MARKER}

        def apply_identity(payload, **identity):
            payload["title_or_name"] = identity["business_name"]
            return True

        namespace.update(card_data=card, business_id="synthetic-business",
                         _promote_nested_card_payload=promote,
                         _load_business_identity_for_fallback=load_identity,
                         _apply_business_identity_fallback=apply_identity)
        branch = _if_with_expression("isinstance(card_data, dict) and not card_data.get('error')",
                                     "_promote_nested_card_payload")
        output = _stdout(lambda: _run_nodes([branch], namespace))
        self.assertEqual(card["title_or_name"], MARKER)
        self.assertEqual(card[MARKER], MARKER)
        self.assertEqual(calls, ["synthetic-business"] if fallback else [])
        self.assertIn("WORKER_NORMALIZE", output)
        self.assertNotIn(MARKER, output)

    def test_promoted_keys_and_title_are_not_logged(self):
        self._exercise_normalization(fallback=False)

    def test_identity_fallback_keeps_title_without_logging_it(self):
        self._exercise_normalization(fallback=True)

    def _exercise_timeout_wrapper(self, *, alive=False, empty=False, fail_open=False):
        namespace, artifacts = _namespace(fail_open=fail_open)
        calls = []
        result = {"title": MARKER, "_apify_debug": {"run_id": MARKER, "usage_total_usd": 0.25}}
        process = types.SimpleNamespace(start=lambda: calls.append("start"),
            join=lambda *_a, **_k: calls.append("join"), is_alive=lambda: alive,
            terminate=lambda: calls.append("terminate"))
        queue = types.SimpleNamespace(empty=lambda: empty, get=lambda: result)
        context = types.SimpleNamespace(Queue=lambda **_k: queue, Process=lambda **_k: process)
        namespace.update(multiprocessing=types.SimpleNamespace(get_context=lambda _method: context),
                         _parse_card_via_apify_subprocess_entry=lambda *_a: None)
        function = next(node for node in _worker_tree().body if isinstance(node, ast.FunctionDef)
                        and node.name == "_parse_card_via_apify_with_timeout")
        module = ast.fix_missing_locations(ast.Module(body=[ast.ImportFrom(
            module="__future__", names=[ast.alias(name="annotations")], level=0),
            copy.deepcopy(function)], type_ignores=[]))
        exec(compile(module, str(WORKER_SOURCE), "exec"), namespace)
        returned = []
        output = _stdout(lambda: returned.append(namespace[function.name](
            MARKER, debug_bundle_dir="/synthetic-bundle", debug_context={MARKER: MARKER}, city=MARKER)))
        self.assertEqual(calls.count("start"), 1)
        self.assertEqual(calls.count("terminate"), int(alive))
        if alive or empty:
            self.assertEqual(returned[0]["url"], MARKER)
            expected_error = "apify_parser_subprocess_timeout" if alive else "apify_parser_subprocess_no_result"
            self.assertEqual(returned[0]["error"], expected_error)
        else:
            self.assertIs(returned[0], result)
        return artifacts, output

    def test_timeout_diagnostic_omits_values_but_keeps_error_result(self):
        artifacts, output = self._exercise_timeout_wrapper(alive=True)
        self.assertEqual(set(artifacts), {"timeout.json"})
        self.assertNotIn(MARKER, artifacts["timeout.json"].getvalue() + output)

    def test_no_result_diagnostic_omits_values_but_keeps_error_result(self):
        artifacts, output = self._exercise_timeout_wrapper(empty=True)
        self.assertEqual(set(artifacts), {"subprocess_no_result.json"})
        self.assertNotIn(MARKER, artifacts["subprocess_no_result.json"].getvalue() + output)

    def test_timeout_and_no_result_write_failures_omit_exception_text(self):
        for arguments in ({"alive": True}, {"empty": True}):
            with self.subTest(arguments=arguments):
                artifacts, output = self._exercise_timeout_wrapper(fail_open=True, **arguments)
                self.assertEqual(artifacts, {})
                self.assertIn("Failed to write", output)
                self.assertNotIn(MARKER, output)

    def test_successful_queue_result_preserves_provider_data(self):
        artifacts, output = self._exercise_timeout_wrapper()
        self.assertEqual(artifacts, {})
        self.assertEqual(output, "")

    def test_functional_ipc_file_round_trip_keeps_card_and_billing_payload(self):
        namespace, artifacts = _namespace()
        result = {"title": MARKER, "raw_payload_json": {MARKER: MARKER},
                  "_apify_debug": {"run_id": MARKER, "usage_total_usd": 0.25}}
        messages = []
        queue = types.SimpleNamespace(put=messages.append, empty=lambda: not messages,
                                      get=lambda: messages.pop(0))

        def create_process(*, target, args, daemon):
            self.assertTrue(daemon)
            return types.SimpleNamespace(start=lambda: target(*args),
                join=lambda *_a, **_k: None, is_alive=lambda: False)

        context = types.SimpleNamespace(Queue=lambda **_k: queue, Process=create_process)
        namespace.update(multiprocessing=types.SimpleNamespace(get_context=lambda _method: context),
                         _parse_card_via_apify=lambda *_a, **_k: result)
        names = {"_parse_card_via_apify_subprocess_entry", "_parse_card_via_apify_with_timeout"}
        functions = [copy.deepcopy(node) for node in _worker_tree().body
                     if isinstance(node, ast.FunctionDef) and node.name in names]
        self.assertEqual(len(functions), 2)
        module = ast.fix_missing_locations(ast.Module(body=[ast.ImportFrom(
            module="__future__", names=[ast.alias(name="annotations")], level=0),
            *functions], type_ignores=[]))
        exec(compile(module, str(WORKER_SOURCE), "exec"), namespace)
        returned = namespace["_parse_card_via_apify_with_timeout"](
            MARKER, debug_bundle_dir="/synthetic-bundle")
        self.assertEqual(returned, result)
        self.assertEqual(set(artifacts), {"apify_result.json"})
        self.assertEqual(json.loads(artifacts["apify_result.json"].getvalue()), result)
