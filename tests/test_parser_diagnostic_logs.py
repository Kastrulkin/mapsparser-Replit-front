"""Regression contract: parser diagnostics are value-free; stdlib/AST isolation only."""

from __future__ import annotations

import ast
import copy
from contextlib import redirect_stdout
from datetime import datetime
import io
import json
import os
from pathlib import Path
import random
import runpy
import sys
import time
import types
from typing import Any, Dict, List, Optional
import unittest


PARSER_SOURCE = Path(__file__).parents[1] / "src" / "parser_interception.py"
DEBUG_ARTIFACTS_SOURCE = Path(__file__).parents[1] / "src" / "core" / "parser_debug_artifacts.py"
SYNTHETIC_MARKER = "synthetic-private-parser-diagnostic-marker"


class _FakeRequest:
    headers = {"X-Test": "synthetic"}
    method = "GET"


class _FakeResponse:
    url = (
        "https://synthetic-private-parser-diagnostic-marker:"
        "synthetic-private-parser-diagnostic-marker@maps.yandex.ru/org/"
        "synthetic-private-parser-diagnostic-marker.json?token="
        "synthetic-private-parser-diagnostic-marker"
    )
    headers = {"content-type": "application/json"}
    status = 200
    request = _FakeRequest()

    def __init__(self):
        self.payload = {"organization": {"title": SYNTHETIC_MARKER}}

    def json(self):
        return self.payload


class _NoWriteOs:
    path = types.SimpleNamespace(join=lambda directory, filename: f"{directory}/{filename}")

    @staticmethod
    def makedirs(_directory, exist_ok=False):
        return None


class _FakePage:
    def __init__(self, url):
        self.url = url
        self.response_callback = None

    def on(self, event, callback):
        if event == "response":
            self.response_callback = callback

    def goto(self, _url, wait_until, timeout):
        return types.SimpleNamespace(status=429)

    def wait_for_timeout(self, _milliseconds):
        return None

    def title(self):
        return ""

    def get_by_text(self, _text, exact=False):
        return types.SimpleNamespace(is_visible=lambda: False)

    def locator(self, _selector):
        return types.SimpleNamespace(count=lambda: 0)


class _FakeCaptchaPage(_FakePage):
    def goto(self, _url, wait_until, timeout):
        return types.SimpleNamespace(status=200)

    def title(self):
        return f"captcha {SYNTHETIC_MARKER}"


def _parser_tree():
    return ast.parse(PARSER_SOURCE.read_text(encoding="utf-8"), filename=str(PARSER_SOURCE))


def _parser_class(tree):
    return next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "YandexMapsInterceptionParser"
    )


def _parser_method(tree, method_name):
    return next(
        node for node in _parser_class(tree).body
        if isinstance(node, ast.FunctionDef) and node.name == method_name
    )


def _compiled_method(method_name, namespace):
    method = copy.deepcopy(_parser_method(_parser_tree(), method_name))
    module = ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[]))
    exec(compile(module, str(PARSER_SOURCE), "exec"), namespace)
    return namespace[method_name]


def _compiled_module_function(function_name, namespace):
    function = next(
        node for node in _parser_tree().body
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    )
    module = ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(function)], type_ignores=[]))
    exec(compile(module, str(PARSER_SOURCE), "exec"), namespace)
    return namespace[function_name]


def _extracted_response_handler(debug_bundle_dir, open_function=None):
    tree = _parser_tree()
    parse_method = _parser_method(tree, "parse_yandex_card")
    handler = next(
        node for node in ast.walk(parse_method) if isinstance(node, ast.FunctionDef) and node.name == "handle_response"
    )
    helpers = runpy.run_path(str(DEBUG_ARTIFACTS_SOURCE))
    state = types.SimpleNamespace(
        debug_bundle_dir=debug_bundle_dir,
        api_responses={},
        review_api_response_count=0,
        review_ids_seen=set(),
        _review_ids_from_payload=lambda _payload: set(),
    )
    namespace = {
        "json": json,
        "os": _NoWriteOs if debug_bundle_dir else os,
        "time": time,
        "debug_value_shape": helpers["debug_value_shape"],
        "debug_url_summary": helpers["debug_url_summary"],
        "self": state,
    }
    if open_function is not None:
        namespace["open"] = open_function
    module = ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(handler)], type_ignores=[]))
    exec(compile(module, str(PARSER_SOURCE), "exec"), namespace)
    return namespace["handle_response"], state


def _captured_output(callback):
    output = io.StringIO()
    redirector = redirect_stdout(output)
    redirector.__enter__()
    try:
        result = callback()
    finally:
        redirector.__exit__(None, None, None)
    return result, output.getvalue()


def _parser_getenv(name, default=None):
    if name == "PARSER_DEBUG_BUNDLES_ENABLED":
        return "false"
    return default


def _parse_method_namespace():
    helpers = runpy.run_path(str(DEBUG_ARTIFACTS_SOURCE))
    return {
        "Any": Any,
        "BrowserSession": object,
        "datetime": datetime,
        "debug_html_placeholder": helpers["debug_html_placeholder"],
        "debug_url_summary": helpers["debug_url_summary"],
        "debug_value_shape": helpers["debug_value_shape"],
        "Dict": Dict,
        "Optional": Optional,
        "os": types.SimpleNamespace(getenv=_parser_getenv),
        "PlaywrightTimeoutError": TimeoutError,
        "random": random,
    }


def _review_method():
    return _compiled_method(
        "_extract_reviews_from_api",
        {"Any": Any, "Dict": Dict, "List": List, "Optional": Optional},
    )


def _post_method():
    return _compiled_method(
        "_extract_posts",
        {"Any": Any, "Dict": Dict, "List": List, "datetime": datetime},
    )


class ParserDiagnosticLogsTests(unittest.TestCase):
    def test_intercept_log_omits_raw_response_url_and_preserves_payload_identity(self):
        handler, state = _extracted_response_handler(None)
        response = _FakeResponse()

        _result, stdout = _captured_output(lambda: handler(response))

        self.assertIs(state.api_responses[response.url]["data"], response.payload)
        self.assertIn("Перехвачен важный API запрос", stdout)
        self.assertNotIn(SYNTHETIC_MARKER, stdout)

    def test_intercept_writer_error_omits_exception_detail_and_keeps_response(self):
        def failing_open(*_args, **_kwargs):
            raise RuntimeError(SYNTHETIC_MARKER)

        handler, state = _extracted_response_handler("synthetic-debug-dir", failing_open)
        response = _FakeResponse()

        _result, stdout = _captured_output(lambda: handler(response))

        self.assertIs(state.api_responses[response.url]["data"], response.payload)
        self.assertIn("Failed to save debug json", stdout)
        self.assertNotIn(SYNTHETIC_MARKER, stdout)

    def test_review_diagnostics_omit_review_values_while_returning_them_unchanged(self):
        method = _review_method()
        payload = {
            "reviews": [{
                "author": {"name": SYNTHETIC_MARKER},
                "rating": 5,
                "text": SYNTHETIC_MARKER,
                "date": SYNTHETIC_MARKER,
                "ownerComment": {"text": SYNTHETIC_MARKER, "date": SYNTHETIC_MARKER},
                "metdata": SYNTHETIC_MARKER,
                SYNTHETIC_MARKER: SYNTHETIC_MARKER,
            }]
        }

        reviews, stdout = _captured_output(lambda: method(types.SimpleNamespace(), payload, "synthetic"))

        self.assertEqual(reviews[0]["author"], SYNTHETIC_MARKER)
        self.assertEqual(reviews[0]["rating"], "5")
        self.assertEqual(reviews[0]["text"], SYNTHETIC_MARKER)
        self.assertEqual(reviews[0]["date"], SYNTHETIC_MARKER)
        self.assertEqual(reviews[0]["response_text"], SYNTHETIC_MARKER)
        self.assertNotIn(SYNTHETIC_MARKER, stdout)

    def test_post_diagnostics_omit_post_values_and_arbitrary_keys_while_returning_them(self):
        method = _post_method()
        payload = {
            "posts": [{
                "title": SYNTHETIC_MARKER,
                "text": SYNTHETIC_MARKER,
                "date": SYNTHETIC_MARKER,
                "url": SYNTHETIC_MARKER,
                "metdata": SYNTHETIC_MARKER,
                SYNTHETIC_MARKER: SYNTHETIC_MARKER,
            }]
        }

        posts, stdout = _captured_output(lambda: method(types.SimpleNamespace(), payload))

        self.assertEqual(posts[0]["title"], SYNTHETIC_MARKER)
        self.assertEqual(posts[0]["text"], SYNTHETIC_MARKER)
        self.assertEqual(posts[0]["date"], SYNTHETIC_MARKER)
        self.assertEqual(posts[0]["url"], SYNTHETIC_MARKER)
        self.assertNotIn(SYNTHETIC_MARKER, stdout)

    def test_initial_parse_diagnostic_omits_input_url_but_error_result_remains_explicit(self):
        parse_method = _compiled_method(
            "parse_yandex_card",
            _parse_method_namespace(),
        )
        parser = types.SimpleNamespace(
            debug_bundle_dir=None,
            debug_bundle_id=None,
            org_id=None,
            api_responses={},
            extract_org_id=lambda _url: "123",
        )
        input_url = f"https://maps.yandex.ru/org/{SYNTHETIC_MARKER}?token={SYNTHETIC_MARKER}"
        page = _FakePage(input_url)
        session = types.SimpleNamespace(context=object(), page=page)

        result, stdout = _captured_output(lambda: parse_method(parser, input_url, session))

        self.assertEqual(result["error"], "yandex_rate_limited")
        self.assertEqual(result["url"], input_url)
        self.assertNotIn(SYNTHETIC_MARKER, stdout)

    def test_invalid_input_diagnostic_omits_raw_url_from_value_error_and_stdout(self):
        parse_method = _compiled_method(
            "parse_yandex_card",
            _parse_method_namespace(),
        )
        parser = types.SimpleNamespace(
            debug_bundle_dir=None,
            debug_bundle_id=None,
            org_id=None,
            api_responses={},
            extract_org_id=lambda _url: None,
        )
        invalid_url = f"invalid://{SYNTHETIC_MARKER}"

        def invalid_parse_message():
            try:
                parse_method(parser, invalid_url, types.SimpleNamespace(context=object(), page=_FakePage(invalid_url)))
            except ValueError:
                return str(sys.exc_info()[1])
            self.fail("invalid URL must raise ValueError")

        error_message, stdout = _captured_output(invalid_parse_message)

        self.assertNotIn(SYNTHETIC_MARKER, error_message)
        self.assertNotIn(SYNTHETIC_MARKER, stdout)

    def test_missing_review_date_reports_only_field_count_and_preserves_arbitrary_key_data(self):
        payload = {
            "reviews": [{
                "author": SYNTHETIC_MARKER,
                "text": SYNTHETIC_MARKER,
                "metdata": SYNTHETIC_MARKER,
                SYNTHETIC_MARKER: SYNTHETIC_MARKER,
            }]
        }

        reviews, stdout = _captured_output(lambda: _review_method()(types.SimpleNamespace(), payload, "synthetic"))

        self.assertEqual(reviews[0]["author"], SYNTHETIC_MARKER)
        self.assertEqual(reviews[0]["text"], SYNTHETIC_MARKER)
        self.assertEqual(reviews[0]["date"], "")
        self.assertIn("field_count=", stdout)
        self.assertNotIn(SYNTHETIC_MARKER, stdout)

    def test_string_owner_reply_is_returned_without_echoing_its_content(self):
        payload = {
            "reviews": [{
                "author": SYNTHETIC_MARKER,
                "text": SYNTHETIC_MARKER,
                "ownerComment": SYNTHETIC_MARKER,
            }]
        }

        reviews, stdout = _captured_output(lambda: _review_method()(types.SimpleNamespace(), payload, "synthetic"))

        self.assertEqual(reviews[0]["response_text"], SYNTHETIC_MARKER)
        self.assertTrue(reviews[0]["has_response"])
        self.assertIn("Извлечен ответ организации", stdout)
        self.assertNotIn(SYNTHETIC_MARKER, stdout)

    def test_invalid_post_timestamp_logs_category_without_title_or_exception_detail(self):
        payload = {
            "posts": [{
                "title": SYNTHETIC_MARKER,
                "text": SYNTHETIC_MARKER,
                "url": SYNTHETIC_MARKER,
                "timestamp": 10 ** 400,
                "metdata": SYNTHETIC_MARKER,
            }]
        }

        posts, stdout = _captured_output(lambda: _post_method()(types.SimpleNamespace(), payload))

        self.assertEqual(posts[0]["title"], SYNTHETIC_MARKER)
        self.assertEqual(posts[0]["text"], SYNTHETIC_MARKER)
        self.assertEqual(posts[0]["url"], SYNTHETIC_MARKER)
        self.assertEqual(posts[0]["date"], "")
        self.assertIn("Error parsing post timestamp", stdout)
        self.assertNotIn(SYNTHETIC_MARKER, stdout)

    def test_valid_http_url_without_org_id_has_value_free_validation_diagnostics(self):
        parse_method = _compiled_method("parse_yandex_card", _parse_method_namespace())
        parser = types.SimpleNamespace(
            debug_bundle_dir=None,
            debug_bundle_id=None,
            org_id=None,
            api_responses={},
            extract_org_id=lambda _url: None,
        )
        input_url = f"https://maps.yandex.ru/maps/{SYNTHETIC_MARKER}?token={SYNTHETIC_MARKER}"

        def missing_org_message():
            try:
                parse_method(parser, input_url, types.SimpleNamespace(context=object(), page=_FakePage(input_url)))
            except ValueError:
                return str(sys.exc_info()[1])
            self.fail("valid HTTP URL without org ID must raise ValueError")

        error_message, stdout = _captured_output(missing_org_message)

        self.assertIn("org_id", error_message)
        self.assertNotIn(SYNTHETIC_MARKER, error_message)
        self.assertNotIn(SYNTHETIC_MARKER, stdout)

    def test_captcha_title_stays_private_while_captcha_url_return_is_explicit(self):
        parse_method = _compiled_method("parse_yandex_card", _parse_method_namespace())
        parser = types.SimpleNamespace(
            debug_bundle_dir=None,
            debug_bundle_id=None,
            org_id=None,
            api_responses={},
            extract_org_id=lambda _url: "123",
        )
        input_url = f"https://maps.yandex.ru/org/{SYNTHETIC_MARKER}?token={SYNTHETIC_MARKER}"
        page = _FakeCaptchaPage(input_url)
        session = types.SimpleNamespace(context=object(), page=page)

        result, stdout = _captured_output(lambda: parse_method(parser, input_url, session))

        self.assertEqual(result["error"], "captcha_detected")
        self.assertEqual(result["captcha_url"], input_url)
        self.assertIn("Капча не была решена", stdout)
        self.assertNotIn(SYNTHETIC_MARKER, stdout)

    def test_unknown_session_kwarg_is_count_only_in_debug_validation_error(self):
        class _Manager:
            pass

        parse_function = _compiled_module_function(
            "parse_yandex_card",
            {
                "ALLOWED_SESSION_KWARGS": set(),
                "Any": Any,
                "BrowserSession": object,
                "BrowserSessionManager": _Manager,
                "Dict": Dict,
                "List": List,
                "Optional": Optional,
                "os": types.SimpleNamespace(getenv=lambda _name, _default=None: "test"),
                "PARSER_MODE_FULL": "full",
            },
        )

        def unknown_kwarg_message():
            try:
                parse_function("https://maps.yandex.ru/org/123", **{SYNTHETIC_MARKER: SYNTHETIC_MARKER})
            except ValueError:
                return str(sys.exc_info()[1])
            self.fail("unknown session kwarg must raise in a debug environment")

        error_message, stdout = _captured_output(unknown_kwarg_message)

        self.assertIn("count=1", error_message)
        self.assertNotIn(SYNTHETIC_MARKER, error_message)
        self.assertEqual(stdout, "")


if __name__ == "__main__":
    unittest.main()
