"""AST-only causal contract for approval-time and replay-time media identity."""
import ast
import copy
import hashlib
import hmac
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote
import unittest


ROOT = Path(__file__).resolve().parents[1]


def functions(path, names):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    if {node.name for node in selected} != set(names):
        raise AssertionError("requested function missing")
    return selected


def load_contract(secret):
    media = ROOT / "src/services/social_posts/media_delivery.py"
    storage = ROOT / "src/services/media_file_storage.py"
    helpers = ROOT / "src/services/social_posts/metrics_policy.py"
    namespace = {"Any": object, "json": json, "os": SimpleNamespace(environ={"EXTERNAL_AUTH_SECRET_KEY": secret, "PUBLIC_BASE_URL": "https://local.test"}), "hmac": hmac, "hashlib": hashlib, "quote": quote}
    from services.media_library_scope import PHOTO_LIBRARY_SCOPE_SQL, PHOTO_USAGE_LIBRARY_SCOPE_SQL
    namespace["PHOTO_USAGE_LIBRARY_SCOPE_SQL"] = PHOTO_USAGE_LIBRARY_SCOPE_SQL
    namespace["PHOTO_LIBRARY_SCOPE_SQL"] = PHOTO_LIBRARY_SCOPE_SQL
    source = functions(media, {"_strict_selected_media_assets", "_approved_media_assets"})
    optional = [node for node in ast.parse(media.read_text()).body
                if isinstance(node, ast.FunctionDef) and node.name == "_media_public_url"]
    source = functions(helpers, {"_json_dict", "_json_value", "_row_to_dict"}) + optional + source
    delivery = functions(storage, {"build_media_delivery_url"})
    exec(compile(ast.Module(body=delivery + source, type_ignores=[]), "media-contract", "exec"), namespace)
    return namespace


class Cursor:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def execute(self, statement, params):
        self.calls.append((statement, params))

    def fetchall(self):
        return list(self.rows)


def asset(content_hash="a" * 64, storage_path="synthetic/photo", public_url="", version=1, mime_type="image/jpeg"):
    return {"id": "asset-1", "asset_version": version, "content_hash": content_hash, "original_url": public_url or "/synthetic/photo", "storage_key": storage_path, "versions_json": {"original": {"storage_path": storage_path, "public_url": public_url, "mime_type": mime_type}}}


def approved_from_selected(selected):
    value = selected[0]
    return {"media": [{"asset_id": value["id"], "asset_version": value["asset_version"], "content_hash": value["content_hash"], "storage_path": value["storage_path"], "public_url": value["public_url"], "mime_type": value["mime_type"]}]}


class ApprovalNormalizationContract(unittest.TestCase):
    def selected(self, secret, row):
        contract = load_contract(secret)
        cursor = Cursor([row])
        selected = contract["_strict_selected_media_assets"](cursor, {"id": "post-1", "content_plan_item_id": "item-1", "business_id": "business-1", "platform": "telegram"})
        self.assertEqual(cursor.calls[0][1], ("business-1", ["post-1", "item-1"], "telegram"))
        self.assertIn("usage.business_id = %s", cursor.calls[0][0])
        return contract, selected

    def assert_accepted(self, secret, row):
        original = copy.deepcopy(row)
        contract, selected = self.selected(secret, row)
        snapshot = approved_from_selected(selected)
        original_snapshot = copy.deepcopy(snapshot)
        cursor = Cursor([row])
        resolved = contract["_approved_media_assets"](cursor, {"business_id": "business-1"}, snapshot)
        self.assertEqual(cursor.calls[0][1], ("business-1", ["asset-1"]))
        self.assertIn("id = ANY(%s)", cursor.calls[0][0])
        self.assertIn("FROM businesses", cursor.calls[0][0])
        self.assertEqual(row, original)
        self.assertEqual(snapshot, original_snapshot)
        self.assertEqual(resolved, [{key: value for key, value in selected[0].items()
                                     if key != "original_url"}])
        return selected, resolved

    def test_same_local_media_without_secret_normalizes_empty_and_replays(self):
        selected, resolved = self.assert_accepted("", asset())
        self.assertEqual(selected[0]["public_url"], "")
        self.assertIsNotNone(resolved)

    def test_same_local_media_with_secret_normalizes_signed_url_and_replays(self):
        selected, resolved = self.assert_accepted("synthetic-signing-secret", asset())
        self.assertTrue(selected[0]["public_url"].startswith("https://local.test/api/media-intelligence/public/photos/"))
        expected = hmac.new(b"synthetic-signing-secret", ("asset-1:original:" + "a" * 64).encode(), hashlib.sha256).hexdigest()
        self.assertTrue(selected[0]["public_url"].endswith("&token=" + expected))
        self.assertIsNotNone(resolved)

    def test_public_http_identity_and_versions_public_url_are_preserved(self):
        for scheme in ("http", "https"):
            with self.subTest(scheme=scheme):
                url = scheme + "://cdn.example/photo.jpg"
                selected, _ = self.assert_accepted("synthetic-secret", asset(public_url=url))
                self.assertEqual(selected[0]["public_url"], url)

    def test_versions_url_precedes_different_original_url(self):
        row = asset(public_url="https://cdn.example/version.jpg")
        row["original_url"] = "https://cdn.example/original.jpg"
        selected, _ = self.assert_accepted("synthetic-secret", row)
        self.assertEqual(selected[0]["public_url"], "https://cdn.example/version.jpg")

    def test_storage_fallback_and_json_versions_keep_identity(self):
        row = asset()
        row["storage_key"] = ""
        row["versions_json"] = json.dumps(row["versions_json"])
        selected, _ = self.assert_accepted("", row)
        self.assertEqual(selected[0]["storage_path"], "synthetic/photo")

    def test_signed_configuration_drift_requires_fresh_approval(self):
        _, selected = self.selected("synthetic-old-secret", asset())
        for secret in ("", "synthetic-new-secret"):
            with self.subTest(secret=secret):
                contract = load_contract(secret)
                self.assertIsNone(contract["_approved_media_assets"](
                    Cursor([asset()]), {"business_id": "business-1"}, approved_from_selected(selected)))

    def test_identity_drift_or_missing_asset_is_denied(self):
        contract, selected = self.selected("synthetic-secret", asset(public_url="https://cdn.example/photo.jpg"))
        snapshot = approved_from_selected(selected)
        for changed in [
            {**asset(public_url="https://cdn.example/photo.jpg"), "content_hash": "b" * 64},
            {**asset(public_url="https://cdn.example/photo.jpg"), "storage_key": "other/photo"},
            {**asset(public_url="https://cdn.example/photo.jpg"), "asset_version": 2},
            asset(public_url="https://cdn.example/photo.jpg", mime_type="image/png"),
            asset(public_url="https://cdn.example/other.jpg"),
        ]:
            self.assertIsNone(contract["_approved_media_assets"](Cursor([changed]), {"business_id": "business-1"}, snapshot))
        self.assertIsNone(contract["_approved_media_assets"](Cursor([]), {"business_id": "business-1"}, snapshot))
        duplicate = copy.deepcopy(snapshot)
        duplicate["media"].append(copy.deepcopy(duplicate["media"][0]))
        self.assertIsNone(contract["_approved_media_assets"](Cursor([asset()]), {"business_id": "business-1"}, duplicate))

    def test_same_local_media_still_rejects_each_identity_drift(self):
        for secret in ("", "synthetic-secret"):
            contract, selected = self.selected(secret, asset())
            for field, value in (("content_hash", "b" * 64), ("storage_key", "other/photo"),
                                 ("asset_version", 2), ("id", "other-asset")):
                with self.subTest(secret=secret, field=field):
                    row = asset()
                    row[field] = value
                    self.assertIsNone(contract["_approved_media_assets"](
                        Cursor([row]), {"business_id": "business-1"}, approved_from_selected(selected)))

    def test_empty_or_invalid_snapshot_never_loads_other_media(self):
        contract = load_contract("")
        for snapshot, expected in (({"media": []}, []), ({}, None), ({"media": "invalid"}, None)):
            cursor = Cursor([asset()])
            self.assertEqual(contract["_approved_media_assets"](cursor, {"business_id": "business-1"}, snapshot), expected)
            self.assertEqual(cursor.calls, [])


if __name__ == "__main__":
    unittest.main()
