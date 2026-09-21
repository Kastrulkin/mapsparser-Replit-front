"""Regression safety contract for parser debug bundles; intentionally stdlib-only."""

from __future__ import annotations

import ast
import copy
import json
import os
from pathlib import Path
import runpy
import tempfile
import time
import types
import unittest


PARSER_SOURCE = Path(__file__).parents[1] / "src" / "parser_interception.py"
DEBUG_ARTIFACTS_SOURCE = Path(__file__).parents[1] / "src" / "core" / "parser_debug_artifacts.py"
SYNTHETIC_MARKER = "synthetic-provider-marker-must-not-persist"


class _FakeRequest:
    headers = {"X-Test": "synthetic"}
    method = "GET"


class _FakeResponse:
    # This is inert fixture data only.  The real callback's allow-list admits
    # yandex.ru, so use that host and make the userinfo/path/query all carry
    # the same synthetic value whose persistence is prohibited by this test.
    url = (
        "https://synthetic-provider-marker-must-not-persist@maps.yandex.ru/"
        "watch/synthetic-provider-marker-must-not-persist.json?"
        "token=synthetic-provider-marker-must-not-persist"
    )
    headers = {"content-type": "application/json"}
    status = 200
    request = _FakeRequest()

    def __init__(self):
        self.payload = {"provider_debug_value": SYNTHETIC_MARKER}

    def json(self):
        return self.payload


class _MarkerCarrier:
    def __repr__(self):
        return SYNTHETIC_MARKER


def _extracted_response_handler(debug_bundle_dir: str | None):
    """Compile only the current nested interception handler, never import the app."""
    helpers = runpy.run_path(str(DEBUG_ARTIFACTS_SOURCE))
    tree = ast.parse(PARSER_SOURCE.read_text(encoding="utf-8"), filename=str(PARSER_SOURCE))
    parser_class = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "YandexMapsInterceptionParser"
    )
    parse_method = next(
        node for node in parser_class.body if isinstance(node, ast.FunctionDef) and node.name == "parse_yandex_card"
    )
    handler = next(
        node for node in ast.walk(parse_method) if isinstance(node, ast.FunctionDef) and node.name == "handle_response"
    )
    module = ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(handler)], type_ignores=[]))
    state = types.SimpleNamespace(
        debug_bundle_dir=debug_bundle_dir,
        api_responses={},
        review_api_response_count=0,
        review_ids_seen=set(),
        _review_ids_from_payload=lambda _payload: set(),
    )
    namespace = {
        "json": json,
        "os": os,
        "time": time,
        "debug_value_shape": helpers["debug_value_shape"],
        "debug_url_summary": helpers["debug_url_summary"],
        "debug_html_placeholder": helpers["debug_html_placeholder"],
        "self": state,
    }
    exec(compile(module, str(PARSER_SOURCE), "exec"), namespace)
    return namespace["handle_response"], state


class ParserDebugBundleSafetyTests(unittest.TestCase):
    def test_enabled_bundle_never_persists_a_synthetic_provider_marker(self):
        temporary_directory = tempfile.TemporaryDirectory()
        try:
            handler, state = _extracted_response_handler(temporary_directory.name)
            response = _FakeResponse()

            handler(response)

            artifacts = list(Path(temporary_directory.name).glob("*.json"))
            self.assertTrue(artifacts, "opt-in debug bundle should exercise the current JSON artifact branch")
            self.assertIs(state.api_responses[response.url]["data"], response.payload)
            persisted = "\n".join(path.read_text(encoding="utf-8") for path in artifacts)
            self.assertNotIn(SYNTHETIC_MARKER, persisted)
            self.assertNotIn(SYNTHETIC_MARKER, "\n".join(path.name for path in artifacts))
        finally:
            temporary_directory.cleanup()

    def test_disabled_bundle_does_not_write_an_intercepted_response(self):
        temporary_directory = tempfile.TemporaryDirectory()
        try:
            handler, _state = _extracted_response_handler(None)

            handler(_FakeResponse())

            self.assertEqual(list(Path(temporary_directory.name).iterdir()), [])
        finally:
            temporary_directory.cleanup()

    def test_debug_value_shape_is_value_free_bounded_and_nonmutating(self):
        helpers = runpy.run_path(str(DEBUG_ARTIFACTS_SOURCE))
        payload = {
            "unknown_key": SYNTHETIC_MARKER,
            "hittoken": SYNTHETIC_MARKER,
            "headers": {"Authorization": SYNTHETIC_MARKER, "Cookie": SYNTHETIC_MARKER},
            "cookies": [SYNTHETIC_MARKER, b"synthetic-binary-value"],
            "items": [{"unknown_child": SYNTHETIC_MARKER}],
            "number": 42,
            "flag": True,
        }
        expected_payload = copy.deepcopy(payload)

        shape = helpers["debug_value_shape"](payload)
        serialized_shape = json.dumps(shape, ensure_ascii=False)

        self.assertEqual(payload, expected_payload)
        self.assertNotIn(SYNTHETIC_MARKER, serialized_shape)
        self.assertNotIn("unknown_key", serialized_shape)
        self.assertEqual(shape["type"], "object")
        self.assertEqual(shape["fields"]["hittoken"], {"type": "string", "length": len(SYNTHETIC_MARKER)})
        self.assertEqual(shape["fields"]["headers"]["type"], "object")
        self.assertEqual(shape["fields"]["cookies"]["sample_shapes"][1], {"type": "unsupported"})

        cycle = {}
        cycle["data"] = cycle
        deep_shape = helpers["debug_value_shape"](cycle)
        self.assertLess(len(json.dumps(deep_shape)), 3000)
        cursor = deep_shape
        for _ in range(5):
            cursor = cursor["fields"]["data"]
        self.assertTrue(cursor["truncated"])

        large_shape = helpers["debug_value_shape"]({"items": list(range(10000))})
        self.assertEqual(large_shape["fields"]["items"]["item_count"], 10000)
        self.assertEqual(len(large_shape["fields"]["items"]["sample_shapes"]), 3)

        wide_cycle = {}
        for field in helpers["_DIAGNOSTIC_FIELDS"]:
            wide_cycle[field] = {"data": wide_cycle}
        wide_shape = helpers["debug_value_shape"](wide_cycle)

        def count_type_nodes(node):
            if isinstance(node, dict):
                return (1 if "type" in node else 0) + sum(count_type_nodes(value) for value in node.values())
            if isinstance(node, list):
                return sum(count_type_nodes(value) for value in node)
            return 0

        self.assertLessEqual(count_type_nodes(wide_shape), 120)
        unsupported_shape = helpers["debug_value_shape"](_MarkerCarrier())
        self.assertEqual(unsupported_shape, {"type": "unsupported"})
        self.assertNotIn(SYNTHETIC_MARKER, json.dumps(unsupported_shape))

    def test_debug_url_and_html_summaries_never_retain_raw_fixture_content(self):
        helpers = runpy.run_path(str(DEBUG_ARTIFACTS_SOURCE))
        raw_url = (
            "https://synthetic-provider-marker-must-not-persist:"
            "synthetic-provider-marker-must-not-persist@maps.yandex.ru/org/"
            "synthetic-provider-marker-must-not-persist?token="
            "synthetic-provider-marker-must-not-persist#synthetic-provider-marker-must-not-persist"
        )
        raw_html = (
            "<form action='/synthetic-provider-marker-must-not-persist'><input value='"
            "synthetic-provider-marker-must-not-persist'></form><script>"
            "synthetic-provider-marker-must-not-persist</script>"
        )

        url_summary = helpers["debug_url_summary"](raw_url)
        html_placeholder = helpers["debug_html_placeholder"](raw_html)

        self.assertEqual(raw_url.count(SYNTHETIC_MARKER), 5)
        self.assertEqual(url_summary["provider"], "yandex")
        self.assertEqual(url_summary["route"], "organization")
        self.assertTrue(url_summary["https"])
        self.assertTrue(url_summary["has_userinfo"])
        self.assertTrue(url_summary["has_query"])
        self.assertTrue(url_summary["has_fragment"])
        self.assertNotIn(SYNTHETIC_MARKER, json.dumps(url_summary))
        self.assertNotIn(SYNTHETIC_MARKER, html_placeholder)
        self.assertNotIn("<form", html_placeholder)
        self.assertNotIn("<script", html_placeholder)
        self.assertIn(str(len(raw_html)), html_placeholder)
        self.assertEqual(helpers["debug_url_summary"](None), {"kind": "invalid"})
        self.assertEqual(helpers["debug_url_summary"]("https://[malformed"), {"kind": "invalid"})

    def test_parser_source_routes_canonical_sinks_through_value_free_helpers(self):
        source = PARSER_SOURCE.read_text(encoding="utf-8")

        self.assertIn("json.dump(debug_value_shape(json_data), f, ensure_ascii=False, indent=2)", source)
        self.assertIn("f.write(debug_html_placeholder(html_redirect))", source)
        self.assertIn("f.write(debug_html_placeholder(html_failed))", source)
        self.assertIn("f.write(debug_html_placeholder(html_content))", source)
        self.assertIn("f.write(debug_html_placeholder(page_html))", source)
        self.assertIn("json.dump(debug_url_summary(initial_url), f)", source)
        self.assertIn("json.dump(debug_url_summary(final_url), f)", source)
        self.assertIn("json.dump(debug_value_shape(data), f, ensure_ascii=False, indent=2)", source)
        self.assertNotIn("json.dump(json_data, f, ensure_ascii=False, indent=2)", source)
        self.assertNotIn("f.write(html_redirect)", source)
        self.assertNotIn("f.write(html_failed)", source)
        self.assertNotIn("f.write(html_content)", source)
        self.assertNotIn("f.write(page_html)", source)
        self.assertNotIn("json.dump(initial_url, f)", source)
        self.assertNotIn("json.dump(final_url, f)", source)
        self.assertNotIn("json.dump(data, f, ensure_ascii=False, indent=2)", source)

        tree = ast.parse(source, filename=str(PARSER_SOURCE))
        parser_class = next(
            node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "YandexMapsInterceptionParser"
        )
        parse_method = next(
            node for node in parser_class.body if isinstance(node, ast.FunctionDef) and node.name == "parse_yandex_card"
        )
        screenshot_calls = [
            node
            for node in ast.walk(parse_method)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "screenshot"
        ]
        self.assertEqual(screenshot_calls, [])


if __name__ == "__main__":
    unittest.main()
