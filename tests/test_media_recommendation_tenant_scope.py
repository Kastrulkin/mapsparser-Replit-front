"""Bounded tenant contract for media recommendations.

The test extracts the complete production service function and supplies only
in-memory cursor rows and ranking collaborators.  It does not import the
application, open a database, or call a provider.
"""

import ast
import copy
import hashlib
import json
import os
from pathlib import Path
from types import ModuleType
import unittest


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "src" / "services" / "media_intelligence.py"
SOURCE_ENV = "MEDIA_RECOMMENDATION_TENANT_SCOPE_SOURCE"
FUNCTION_NAME = "recommend_media_for_post"


def _source_path():
    candidate = Path(os.environ.get(SOURCE_ENV, DEFAULT_SOURCE)).resolve()
    default_source = DEFAULT_SOURCE.resolve()
    temp_root = Path("/private/tmp").resolve()
    valid_override = (
        candidate.is_relative_to(temp_root)
        and candidate.name == "media_intelligence.py"
        and candidate.parent.name == "src"
        and candidate.parent.parent.name.startswith("localos-media-tenant-")
        and candidate.parent.parent.parent == temp_root
    )
    if candidate != default_source and not valid_override:
        raise AssertionError(
            f"{SOURCE_ENV} must point to src/services/media_intelligence.py or "
            "/private/tmp/localos-media-tenant-.../src/media_intelligence.py"
        )
    valid_default_layout = (
        candidate.name == "media_intelligence.py"
        and candidate.parent.name == "services"
        and candidate.parent.parent.name == "src"
    )
    if not (valid_default_layout or valid_override) or not candidate.is_file():
        raise AssertionError(f"invalid media intelligence source: {candidate}")
    return candidate


SOURCE = _source_path()


def _helper_node():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    matches = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == FUNCTION_NAME
    ]
    if len(matches) != 1:
        raise AssertionError(f"expected one {FUNCTION_NAME}, found {len(matches)}")
    return copy.deepcopy(matches[0])


def _helper_nodes(*names):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    found = {
        node.name: copy.deepcopy(node)
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    }
    if set(found) != set(names):
        raise AssertionError(f"expected helpers {names}, found {tuple(found)}")
    return [found[name] for name in names]


class _Cursor:
    def __init__(self, *, manual_asset_id=""):
        self.queries = []
        self._one = None
        self._many = []
        self._manual_asset_id = manual_asset_id
        self._social_posts = [
            {"content_plan_item_id": "owned-item", "business_id": "business-owner", "platform": "telegram"},
            {"content_plan_item_id": "owned-item", "business_id": "business-foreign", "platform": "foreign-platform"},
        ]

    def execute(self, query, parameters):
        self.queries.append((query, parameters))
        normalized = " ".join(query.lower().split())
        if "from contentplanitems" in normalized:
            item_id = parameters[0]
            business_id = parameters[1] if len(parameters) > 1 else None
            is_scoped = "business_id = %s" in normalized
            if item_id == "foreign-item" and (not is_scoped or business_id == "business-foreign"):
                self._one = {
                    "id": "foreign-item",
                    "theme": "Private tenant topic",
                    "goal": "Private tenant goal",
                    "draft_text": "Private tenant text",
                    "content_type": "news",
                }
            elif item_id == "owned-item" and (not is_scoped or business_id == "business-owner"):
                self._one = {
                    "id": "owned-item",
                    "theme": "Owned topic",
                    "goal": "Owned goal",
                    "draft_text": "Owned text",
                    "content_type": "news",
                }
            else:
                self._one = None
            self._many = []
        elif "from social_posts" in normalized:
            self._one = None
            rows = [row for row in self._social_posts if row["content_plan_item_id"] == parameters[0]]
            if "business_id = %s" in normalized:
                rows = [row for row in rows if row["business_id"] == parameters[1]]
            self._many = [{"platform": row["platform"]} for row in rows]
        elif "from photo_asset_usage_events" in normalized:
            self._one = {"photo_asset_id": self._manual_asset_id} if self._manual_asset_id else None
            self._many = []
        else:
            raise AssertionError(f"unexpected query: {query}")

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._many


def _load_function(candidate_calls, *, assets=None):
    asset_rows = [dict(asset) for asset in (assets or [])]
    namespace = {
        "Any": object,
        "_row_to_dict": lambda _cursor, row: dict(row) if isinstance(row, dict) else None,
        "_clean_text": lambda value: str(value or "").strip(),
        "list_photo_assets": lambda _cursor, business_id: candidate_calls.append(("list", business_id)) or [dict(asset) for asset in asset_rows],
        "build_photo_coverage": lambda _cursor, business_id: candidate_calls.append(("coverage", business_id)) or {"missing": []},
        "PLATFORM_HINTS": {"telegram": "Owned platform hint", "foreign-platform": "Foreign platform hint"},
    }
    module = ModuleType("media_recommendation_tenant_scope_contract")
    module.__dict__.update(namespace)
    unit = ast.Module(
        body=_helper_nodes("_goal_categories", "_photo_why", "rank_photo_assets", "prioritize_selected_photo") + [_helper_node()],
        type_ignores=[],
    )
    exec(compile(ast.fix_missing_locations(unit), str(SOURCE), "exec"), module.__dict__)
    return module.recommend_media_for_post


def _load_ranking_helpers():
    module = ModuleType("media_recommendation_ranking_contract")
    module.__dict__.update({"Any": object, "_clean_text": lambda value: str(value or "").strip()})
    unit = ast.Module(
        body=_helper_nodes("_goal_categories", "_photo_why", "rank_photo_assets", "prioritize_selected_photo"),
        type_ignores=[],
    )
    exec(compile(ast.fix_missing_locations(unit), str(SOURCE), "exec"), module.__dict__)
    return module


class MediaRecommendationTenantScopeTests(unittest.TestCase):
    def test_extracts_complete_real_service_function(self):
        self.assertTrue(callable(_load_function([])))

    def test_foreign_content_item_is_indistinguishable_from_missing_before_candidate_access(self):
        candidate_calls = []
        cursor = _Cursor()
        recommend = _load_function(candidate_calls)

        with self.assertRaisesRegex(ValueError, "Публикация не найдена"):
            recommend(cursor, business_id="business-owner", content_plan_item_id="foreign-item")

        self.assertEqual(candidate_calls, [])
        self.assertEqual(len(cursor.queries), 1)
        query, parameters = cursor.queries[0]
        self.assertIn("FROM contentplanitems", query)
        self.assertEqual(parameters, ("foreign-item", "business-owner"))

    def test_missing_content_item_has_the_existing_not_found_behavior_before_candidate_access(self):
        candidate_calls = []
        cursor = _Cursor()
        recommend = _load_function(candidate_calls)

        with self.assertRaisesRegex(ValueError, "Публикация не найдена"):
            recommend(cursor, business_id="business-owner", content_plan_item_id="missing-item")

        self.assertEqual(candidate_calls, [])
        self.assertEqual(len(cursor.queries), 1)

    def test_unusual_item_id_remains_a_bound_value_and_is_not_found_before_candidate_access(self):
        candidate_calls = []
        cursor = _Cursor()
        recommend = _load_function(candidate_calls)
        unusual_item_id = "foreign-item' OR '1'='1"

        with self.assertRaisesRegex(ValueError, "Публикация не найдена"):
            recommend(cursor, business_id="business-owner", content_plan_item_id=unusual_item_id)

        self.assertEqual(candidate_calls, [])
        self.assertEqual(len(cursor.queries), 1)
        query, parameters = cursor.queries[0]
        self.assertIn("id = %s", query)
        self.assertEqual(parameters, (unusual_item_id, "business-owner"))

    def test_owned_content_item_keeps_the_recommendation_flow(self):
        candidate_calls = []
        cursor = _Cursor()
        recommend = _load_function(candidate_calls)

        result = recommend(cursor, business_id="business-owner", content_plan_item_id="owned-item")

        self.assertEqual(result["status"], "missing")
        self.assertEqual(result["selection_source"], "recommendation")
        self.assertEqual(result["platform_hints"], ["Owned platform hint"])
        self.assertEqual(candidate_calls, [("list", "business-owner"), ("coverage", "business-owner")])

    def test_owned_ready_item_keeps_manual_photo_choice_in_the_real_service_function(self):
        candidate_calls = []
        cursor = _Cursor(manual_asset_id="manual")
        recommend = _load_function(
            candidate_calls,
            assets=[
                {"id": "automatic", "category": "entrance", "quality_score": 80, "freshness_score": 70, "suitable_platforms": []},
                {"id": "manual", "category": "result", "quality_score": 65, "freshness_score": 70, "suitable_platforms": ["telegram"]},
            ],
        )

        result = recommend(cursor, business_id="business-owner", content_plan_item_id="owned-item")

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["selection_source"], "manual")
        self.assertEqual(result["selected_asset"]["id"], "manual")
        self.assertEqual([asset["id"] for asset in result["alternatives"]], ["automatic"])
        self.assertEqual(result["platform_hints"], ["Owned platform hint"])
        self.assertEqual(candidate_calls, [("list", "business-owner"), ("coverage", "business-owner")])

    def test_real_ranking_and_manual_choice_helpers_keep_the_existing_selection_contract(self):
        helpers = _load_ranking_helpers()
        ranked = helpers.rank_photo_assets(
            [
                {"id": "automatic", "category": "entrance", "quality_score": 80, "freshness_score": 70, "suitable_platforms": []},
                {"id": "manual", "category": "result", "quality_score": 65, "freshness_score": 70, "suitable_platforms": ["instagram"]},
            ],
            goal="Продающий пост про результат",
            platforms=["instagram"],
        )

        selected, alternatives, manually_selected = helpers.prioritize_selected_photo(ranked, "automatic")

        self.assertEqual(ranked[0]["id"], "manual")
        self.assertEqual(selected["id"], "automatic")
        self.assertEqual([item["id"] for item in alternatives], ["manual"])
        self.assertTrue(manually_selected)


if __name__ == "__main__":
    print(
        json.dumps(
            {
                "source_path": str(SOURCE),
                "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                "test_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    unittest.main()
