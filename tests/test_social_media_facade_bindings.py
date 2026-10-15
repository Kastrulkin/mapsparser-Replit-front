"""Stdlib-only regression for social-post facade namespace binding.

This bounded test compiles selected AST nodes into two isolated ``ModuleType``
namespaces.  It must not import the application: the production facade is
responsible for binding private helpers into split chunk modules.
"""

import ast
import copy
import json
from functools import wraps
from pathlib import Path
from types import ModuleType
import unittest


ROOT = Path(__file__).resolve().parents[1]
SERVICE_SOURCE = ROOT / "src/services/social_post_service.py"
MEDIA_SOURCE = ROOT / "src/services/social_posts/media_delivery.py"
METRICS_SOURCE = ROOT / "src/services/social_posts/metrics_policy.py"

EXPECTED_RUNTIME_IMPORTS = {
    "_json_dict": "services.social_posts.metrics_policy",
    "_row_to_dict": "services.social_posts.metrics_policy",
    "telegram_urlopen": "core.telegram_network",
    "outbound_urlopen": "core.outbound_network",
    "_provider_json_object": "services.social_posts.recommendations_handoff",
    "_http_publish_outcome": "services.social_posts.recommendations_handoff",
    "_telegram_post_url": "services.social_posts.provider_adapters",
}


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _runtime_import_declarations(tree: ast.Module) -> dict[str, str]:
    declarations: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        for alias in node.names:
            local_name = alias.asname or alias.name
            if local_name in EXPECTED_RUNTIME_IMPORTS:
                if local_name in declarations:
                    raise AssertionError(f"duplicate runtime declaration: {local_name}")
                declarations[local_name] = node.module
    return declarations


def _top_level_function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return copy.deepcopy(node)
    raise AssertionError(f"missing function: {name}")


def _top_level_assignment(tree: ast.Module, name: str) -> ast.Assign:
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            return copy.deepcopy(node)
    raise AssertionError(f"missing assignment: {name}")


def _wrapper_registration_loop(tree: ast.Module) -> ast.For:
    for node in tree.body:
        if isinstance(node, ast.For) and isinstance(node.target, ast.Tuple):
            target_names = [element.id for element in node.target.elts if isinstance(element, ast.Name)]
            if target_names == ["_name", "_implementation"]:
                return copy.deepcopy(node)
    raise AssertionError("missing facade wrapper registration loop")


def _compile(module: ModuleType, nodes: list[ast.stmt]) -> None:
    unit = ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[]))
    exec(compile(unit, f"<{module.__name__}>", "exec"), module.__dict__)


def _load_chunk(module_name: str, source: Path, function_names: set[str], namespace: dict[str, object]) -> ModuleType:
    module = ModuleType(module_name)
    module.__dict__.update(namespace)
    tree = _tree(source)
    _compile(module, [_top_level_function(tree, name) for name in function_names])
    return module


def _load_chunks_with_declared_metric_defaults() -> tuple[ModuleType, ModuleType, object]:
    metrics = _load_chunk(
        "metrics_policy_contract",
        METRICS_SOURCE,
        {"_json_value", "_json_dict", "_row_to_dict"},
        {"Any": object, "json": json},
    )
    media = _load_chunk(
        "media_delivery_contract",
        MEDIA_SOURCE,
        {"_selected_media_assets"},
        {"Any": object},
    )
    metric_json_dict = metrics.__dict__["_json_dict"]
    media.__dict__.update(
        {
            "_json_dict": metric_json_dict,
            "_row_to_dict": metrics.__dict__["_row_to_dict"],
        }
    )
    return metrics, media, metric_json_dict


def _install_real_facade_binding(metrics: ModuleType, media: ModuleType) -> ModuleType:
    service_tree = _tree(SERVICE_SOURCE)
    facade = ModuleType("social_post_service_contract")
    facade.__dict__.update(
        {
            "Any": object,
            "wraps": wraps,
            "_CHUNK_MODULES": (metrics, media),
        }
    )
    _compile(
        facade,
        [
            _top_level_assignment(service_tree, "_IMPLEMENTATIONS"),
            _top_level_function(service_tree, "_bind_runtime_namespace"),
            _top_level_function(service_tree, "_compatibility_wrapper"),
            _wrapper_registration_loop(service_tree),
        ],
    )
    facade._bind_runtime_namespace()
    return facade


class SocialMediaFacadeBindingContract(unittest.TestCase):
    def test_seven_runtime_import_declarations_are_exact(self) -> None:
        tree = _tree(MEDIA_SOURCE)
        self.assertEqual(_runtime_import_declarations(tree), EXPECTED_RUNTIME_IMPORTS)
        recommendations = [
            node
            for node in tree.body
            if isinstance(node, ast.ImportFrom)
            and node.module == "services.social_posts.recommendations_handoff"
        ]
        self.assertEqual(len(recommendations), 1)
        self.assertIn("_publish_adapter", {alias.name for alias in recommendations[0].names})

    def test_inline_media_works_after_declared_default_and_facade_binding(self) -> None:
        metrics, media, metric_json_dict = _load_chunks_with_declared_metric_defaults()
        self.assertIs(media.__dict__["_json_dict"], metric_json_dict)

        facade = _install_real_facade_binding(metrics, media)
        self.assertIs(facade.__dict__["_IMPLEMENTATIONS"]["_json_dict"], metric_json_dict)
        result = facade._selected_media_assets(
            object(),
            {
                "media_json": {
                    "id": "asset-1",
                    "versions_json": '{"original": {"storage_path": "media/a.jpg"}}',
                    "metadata_json": '{"upload": {"original_name": "a.jpg"}}',
                }
            },
        )

        self.assertEqual(result, [{"id": "asset-1", "asset_version": 0, "content_hash": "", "original_url": "", "public_url": "", "storage_path": "media/a.jpg", "mime_type": "image/jpeg", "original_name": "a.jpg"}])
        self.assertIs(media.__dict__["_json_dict"], facade.__dict__["_json_dict"])

    def test_facade_rebinds_an_override_before_a_chunk_wrapper_call(self) -> None:
        metrics, media, _ = _load_chunks_with_declared_metric_defaults()
        facade = _install_real_facade_binding(metrics, media)
        observed: list[object] = []

        def override(value: object) -> dict[str, object]:
            observed.append(value)
            return {}

        facade.__dict__["_json_dict"] = override
        facade._selected_media_assets(object(), {"media_json": {"id": "asset-2"}})

        self.assertIs(media.__dict__["_json_dict"], override)
        self.assertEqual(observed, [None, None, None, None])


if __name__ == "__main__":
    unittest.main()
