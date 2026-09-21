"""AST-isolated parsequeue failure-reason privacy regressions; never import worker."""

from __future__ import annotations

import ast
import copy
from contextlib import redirect_stdout
from datetime import datetime, timedelta
import io
import os
from pathlib import Path
import re
import runpy
import sys
import types
import unittest


WORKER_SOURCE = Path(__file__).parents[1] / "src" / "worker.py"
TAXONOMY_SOURCE = WORKER_SOURCE.parent / "parsing_failure_taxonomy.py"
OPERATOR_REFRESH_SOURCE = WORKER_SOURCE.parent / "services" / "operator_refresh_result.py"
OPERATOR_NEWS_SOURCE = WORKER_SOURCE.parent / "services" / "operator_news_generation.py"
MARKER = "synthetic-private-parsequeue-reason-marker"


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


def _compile_functions(names, namespace):
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    module = ast.Module(body=[future, *[_function(name) for name in names]], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(WORKER_SOURCE), "exec"), namespace)


def _compile_pure_service_function(path: Path, name: str, namespace):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    matches = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(matches) != 1:
        raise AssertionError(f"expected one pure service function: {name}")
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    module = ast.Module(body=[future, copy.deepcopy(matches[0])], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(path), "exec"), namespace)


def _terminal_failure_branch():
    task = _function("_execute_map_card_task")
    matches = []
    for node in ast.walk(task):
        if not isinstance(node, ast.If):
            continue
        if not isinstance(node.test, ast.BoolOp) or not isinstance(node.test.op, ast.And):
            continue
        expression = ast.unparse(node.test)
        if "not is_successful" in expression and "captcha_detected" in expression:
            matches.append(copy.deepcopy(node))
    if len(matches) != 1:
        raise AssertionError("expected one normal terminal parse failure branch")
    return matches[0]


def _compile_terminal_branch(namespace):
    exercise = ast.parse(
        "def exercise_terminal(queue_dict, card_data, reason, debug_bundle_id=None, is_successful=False):\n    pass\n",
    ).body[0]
    exercise.body = [_terminal_failure_branch()]
    module = ast.Module(body=[exercise], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(WORKER_SOURCE), "exec"), namespace)


class _Cursor:
    def __init__(self, *, fail_execute=False):
        self.calls = []
        self.closed = False
        self.fail_execute = fail_execute

    def execute(self, query, params):
        self.calls.append((query, params))
        if self.fail_execute:
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


def _stdout(callback):
    stream = io.StringIO()
    with redirect_stdout(stream):
        result = callback()
    return result, stream.getvalue()


def _taxonomy_namespace():
    return runpy.run_path(str(TAXONOMY_SOURCE))


def _validator_namespace():
    taxonomy = _taxonomy_namespace()
    namespace = {
        "SOURCE_YANDEX_BUSINESS": "yandex_business",
        "STATUS_ERROR": "error",
        "classify_failure_reason": taxonomy["classify_failure_reason"],
    }
    if "safe_parser_error_code" in taxonomy:
        namespace["safe_parser_error_code"] = taxonomy["safe_parser_error_code"]
    _compile_functions(["_validate_parsing_result"], namespace)
    return namespace


def _retry_namespace(connection):
    taxonomy = _taxonomy_namespace()
    sensitive_text = runpy.run_path(str(WORKER_SOURCE.parent / "core" / "sensitive_text.py"))
    namespace = {
        "datetime": datetime,
        "timedelta": timedelta,
        "os": os,
        "re": re,
        "STATUS_PENDING": "pending",
        "STATUS_ERROR": "error",
        "get_db_connection": lambda: connection,
        "redact_sensitive_text": sensitive_text["redact_sensitive_text"],
        "classify_failure_reason": taxonomy["classify_failure_reason"],
        "_is_mass_network_task": lambda _queue: False,
    }
    if "safe_parser_error_code" in taxonomy:
        namespace["safe_parser_error_code"] = taxonomy["safe_parser_error_code"]
    _compile_functions(
        [
            "_parse_transient_retry_attempt",
            "_transient_retry_delay_for_task",
            "_uses_apify_timeout_slow_lane",
            "_apify_business_timeout_profile",
            "_effective_apify_business_timeout_sec",
            "_queue_transient_parse_retry",
        ],
        namespace,
    )
    return namespace


class WorkerFailureReasonSafetyTests(unittest.TestCase):
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

    def _validate_error(self, error, message):
        namespace = _validator_namespace()
        card_data = {"error": error, "message": message, "raw": {"marker": MARKER}}
        before = copy.deepcopy(card_data)
        result = namespace["_validate_parsing_result"](card_data, source="apify_yandex")
        self.assertEqual(card_data, before)
        return result

    def test_arbitrary_error_and_message_do_not_enter_validator_reason(self):
        successful, reason, validation = self._validate_error("provider_" + MARKER, "message=" + MARKER)
        self.assertFalse(successful)
        self.assertIsNone(validation)
        self.assertNotIn(MARKER, reason)
        self.assertTrue(reason)

    def test_known_apify_timeout_keeps_safe_retry_identity_without_message(self):
        successful, reason, validation = self._validate_error(
            "apify_parser_subprocess_timeout",
            "Apify timeout " + MARKER,
        )
        self.assertFalse(successful)
        self.assertIsNone(validation)
        self.assertIn("apify_parser_subprocess_timeout", reason)
        self.assertNotIn(MARKER, reason)

    def test_captcha_and_plain_unknown_controls_remain_terminal(self):
        namespace = _validator_namespace()
        captcha = {"error": "captcha_detected", "message": MARKER}
        self.assertEqual(namespace["_validate_parsing_result"](captcha), (False, "captcha_detected", None))
        successful, reason, validation = self._validate_error("unclassified_" + MARKER, "opaque=" + MARKER)
        self.assertFalse(successful)
        self.assertIsNone(validation)
        self.assertNotIn(MARKER, reason)

    def test_controlled_low_quality_reason_is_preserved(self):
        validation_module = types.ModuleType("parsed_payload_validation")
        validation_module.validate_parsed_payload = runpy.run_path(
            str(WORKER_SOURCE.parent / "parsed_payload_validation.py"),
        )["validate_parsed_payload"]
        previous = sys.modules.get("parsed_payload_validation")
        sys.modules["parsed_payload_validation"] = validation_module
        self.addCleanup(self._restore_module, "parsed_payload_validation", previous)
        namespace = _validator_namespace()
        successful, reason, validation = namespace["_validate_parsing_result"](
            {"title": "controlled fixture"},
            source="yandex_business",
        )
        self.assertFalse(successful)
        self.assertIsInstance(validation, dict)
        self.assertTrue(reason.startswith("low_quality_payload:"))

    def test_terminal_parsequeue_write_and_console_omit_raw_reason_values(self):
        cursor = _Cursor()
        connection = _Connection(cursor)
        validator = _validator_namespace()
        card_data = {"error": "provider_" + MARKER, "message": "opaque=" + MARKER}
        successful, reason, _validation = validator["_validate_parsing_result"](card_data, source="apify_yandex")
        self.assertFalse(successful)
        namespace = {
            "STATUS_ERROR": "error",
            "STATUS_COMPLETED": "completed",
            "os": os,
            "get_db_connection": lambda: connection,
            "_queue_transient_parse_retry": lambda *_args: False,
            "_has_existing_card_snapshot": lambda _business_id: False,
        }
        _compile_terminal_branch(namespace)
        _result, output = _stdout(
            lambda: namespace["exercise_terminal"]({"id": "queue-fixed"}, card_data, reason),
        )
        self.assertEqual(len(cursor.calls), 1)
        _query, params = cursor.calls[0]
        self.assertEqual(params[0], "error")
        self.assertEqual(params[-1], "queue-fixed")
        self.assertNotIn(MARKER, repr(params) + output)
        self.assertTrue(connection.committed)
        self.assertTrue(connection.closed)
        self.assertTrue(cursor.closed)

    def test_unknown_error_with_apify_empty_dataset_retries_without_persisting_raw_values(self):
        cursor = _Cursor()
        connection = _Connection(cursor)
        namespace = _retry_namespace(connection)
        card_data = {"error": "unclassified_" + MARKER, "message": "Apify empty dataset " + MARKER}
        validator = _validator_namespace()
        _successful, reason, _validation = validator["_validate_parsing_result"](card_data, source="apify_yandex")
        retried, output = _stdout(
            lambda: namespace["_queue_transient_parse_retry"](
                {"id": "queue-fixed", "source": "apify_yandex", "error_message": ""},
                reason,
                card_data,
            ),
        )
        self.assertTrue(retried)
        self.assertTrue(connection.committed)
        self.assertEqual(cursor.calls[0][1][0], "pending")
        self.assertNotIn(MARKER, repr(cursor.calls[0][1]) + output)
        self.assertTrue(connection.closed)
        self.assertTrue(cursor.closed)

    def test_legacy_empty_dataset_error_phrase_retries_without_persisting_raw_alias(self):
        cursor = _Cursor()
        connection = _Connection(cursor)
        namespace = _retry_namespace(connection)
        card_data = {
            "error": "Apify returned empty dataset for business card parsing " + MARKER,
            "message": "",
        }
        validator = _validator_namespace()
        _successful, reason, _validation = validator["_validate_parsing_result"](card_data, source="apify_yandex")
        retried, output = _stdout(
            lambda: namespace["_queue_transient_parse_retry"](
                {"id": "queue-fixed", "source": "apify_yandex", "error_message": ""},
                reason,
                card_data,
            ),
        )
        self.assertTrue(retried)
        self.assertNotIn(MARKER, repr(cursor.calls[0][1]) + output)

    def test_closed_business_text_stays_terminal_even_when_payload_looks_retryable(self):
        cursor = _Cursor()
        connection = _Connection(cursor)
        namespace = _retry_namespace(connection)
        retried, _output = _stdout(
            lambda: namespace["_queue_transient_parse_retry"](
                {"id": "queue-fixed", "source": "apify_yandex", "error_message": ""},
                "business_closed: " + MARKER,
                {"error": "apify_empty_dataset", "message": "Apify empty dataset"},
            ),
        )
        self.assertFalse(retried)
        self.assertEqual(cursor.calls, [])

    def test_retry_database_exception_is_not_printed_and_resources_close(self):
        cursor = _Cursor(fail_execute=True)
        connection = _Connection(cursor)
        namespace = _retry_namespace(connection)
        retried, output = _stdout(
            lambda: namespace["_queue_transient_parse_retry"](
                {"id": "queue-fixed", "source": "apify_yandex", "error_message": ""},
                "error: apify_parser_subprocess_timeout",
                {"error": "apify_parser_subprocess_timeout", "message": "timeout"},
            ),
        )
        self.assertFalse(retried)
        self.assertNotIn(MARKER, output)
        self.assertTrue(connection.closed)
        self.assertTrue(cursor.closed)

    def test_timeout_keeps_retry_budget_and_slow_lane_profile(self):
        cursor = _Cursor()
        connection = _Connection(cursor)
        namespace = _retry_namespace(connection)
        old_default = os.environ.get("APIFY_BUSINESS_PARSE_TIMEOUT_SEC")
        old_slow = os.environ.get("APIFY_BUSINESS_PARSE_TIMEOUT_SEC_SLOW")
        self.addCleanup(self._restore_env, "APIFY_BUSINESS_PARSE_TIMEOUT_SEC", old_default)
        self.addCleanup(self._restore_env, "APIFY_BUSINESS_PARSE_TIMEOUT_SEC_SLOW", old_slow)
        os.environ["APIFY_BUSINESS_PARSE_TIMEOUT_SEC"] = "330"
        os.environ["APIFY_BUSINESS_PARSE_TIMEOUT_SEC_SLOW"] = "540"
        queue_dict = {
            "id": "queue-fixed",
            "source": "apify_yandex",
            "error_message": "transient_retry_attempt=1; transient_error=apify_parser_subprocess_timeout",
        }
        self.assertEqual(namespace["_apify_business_timeout_profile"](queue_dict), "slow_lane")
        self.assertEqual(namespace["_effective_apify_business_timeout_sec"](queue_dict), 540)
        self.assertTrue(
            namespace["_queue_transient_parse_retry"](
                queue_dict,
                "error: apify_parser_subprocess_timeout",
                {"error": "apify_parser_subprocess_timeout", "message": "timeout"},
            ),
        )
        comment = cursor.calls[0][1][2]
        self.assertIn("transient_retry_attempt=2", comment)
        self.assertIn("transient_error=apify_parser_subprocess_timeout", comment)

    def test_2gis_timeout_retries_and_google_empty_dataset_stays_terminal(self):
        cursor = _Cursor()
        connection = _Connection(cursor)
        namespace = _retry_namespace(connection)
        self.assertTrue(
            namespace["_queue_transient_parse_retry"](
                {"id": "queue-2gis", "source": "2gis", "error_message": ""},
                "error: 2gis_parse_failed",
                {"error": "2gis_parse_failed", "message": "ERR_TIMED_OUT"},
            ),
        )
        self.assertFalse(
            namespace["_queue_transient_parse_retry"](
                {"id": "queue-google", "source": "apify_google", "error_message": ""},
                "error: apify_empty_dataset",
                {"error": "apify_empty_dataset", "message": "Apify empty dataset"},
            ),
        )

    def test_native_fallback_reason_uses_safe_validator_projection(self):
        namespace = _validator_namespace()
        _compile_functions(["_parse_yandex_native_first_with_fallback"], namespace)
        result, used_apify, native_reason = namespace["_parse_yandex_native_first_with_fallback"](
            lambda: (_ for _ in ()).throw(RuntimeError(MARKER)),
            lambda: {"title": "fallback fixture"},
        )
        self.assertTrue(used_apify)
        self.assertEqual(result["_parser_route"], "apify_yandex_fallback")
        self.assertNotIn(MARKER, native_reason)

    def test_downstream_reason_extractor_keeps_finite_timeout_or_unknown_codes(self):
        taxonomy = _taxonomy_namespace()
        namespace = {"classify_failure_reason": taxonomy["classify_failure_reason"]}
        _compile_pure_service_function(OPERATOR_NEWS_SOURCE, "_clean_text", namespace)
        _compile_pure_service_function(OPERATOR_REFRESH_SOURCE, "_extract_reason_code", namespace)
        validator = _validator_namespace()
        _successful, timeout_reason, _validation = validator["_validate_parsing_result"](
            {"error": "2gis_parse_failed", "message": "navigation timeout"},
            source="2gis",
        )
        _successful, unknown_reason, _validation = validator["_validate_parsing_result"](
            {"error": "provider_" + MARKER, "message": "opaque=" + MARKER},
            source="apify_yandex",
        )
        self.assertEqual(
            namespace["_extract_reason_code"]("error", timeout_reason + " bundle=" + MARKER),
            "timeout",
        )
        self.assertEqual(
            namespace["_extract_reason_code"]("error", unknown_reason + " bundle=" + MARKER),
            "unknown",
        )

    @staticmethod
    def _restore_env(name, previous):
        if previous is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous

    @staticmethod
    def _restore_module(name, previous):
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous


if __name__ == "__main__":
    unittest.main()
