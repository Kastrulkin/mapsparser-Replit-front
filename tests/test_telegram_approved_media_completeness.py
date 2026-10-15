"""Actual decorated media adapter with fake file/provider seams; never sends."""

import ast
from functools import wraps
import json
import os
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load_functions(path, names, namespace):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    selected = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    if {node.name for node in selected} != names:
        raise AssertionError("requested actual adapter functions must exist")
    module = ast.Module(
        body=[
            ast.ImportFrom(
                module="__future__", names=[ast.alias(name="annotations")], level=0
            ),
            *selected,
        ],
        type_ignores=[],
    )
    exec(compile(ast.fix_missing_locations(module), str(path), "exec"), namespace)


class MediaFixture:
    def __init__(self, unavailable=(), responses=None):
        self.unavailable = set(unavailable)
        self.materialized = []
        self.calls = []
        self.responses = responses
        self.namespace = {
            "json": json,
            "wraps": wraps,
            "PUBLISH_OUTCOMES": {"accepted", "not_attempted", "rejected", "uncertain"},
            "_media_asset_file": self.file,
            "_telegram_api_call": self.provider,
        }
        load_functions(
            ROOT / "src/services/social_posts/recommendations_handoff.py",
            {
                "_publish_adapter",
                "_publish_outcome_result",
                "_valid_provider_receipt",
                "_json_dict",
                "_telegram_post_url",
            },
            self.namespace,
        )
        source = Path(
            os.environ.get(
                "TELEGRAM_MEDIA_SOURCE",
                ROOT / "src/services/social_posts/media_delivery.py",
            )
        )
        load_functions(source, {"_publish_telegram_media_post"}, self.namespace)

    def file(self, asset):
        identity = asset["id"]
        self.materialized.append(identity)
        if identity in self.unavailable:
            return {}
        return {
            "content": identity.encode(),
            "mime_type": "image/jpeg",
            "filename": identity + ".jpg",
        }

    def provider(self, _token, method, fields, files=None):
        self.calls.append({"method": method, "fields": fields, "files": files})
        if self.responses is not None:
            return self.responses.pop(0)
        result = {"message_id": 21}
        if method == "sendMediaGroup":
            result = [{"message_id": 21 + index} for index in range(len(files))]
        return {"ok": True, "result": result}

    def publish(self, identities, text="Synthetic approved caption"):
        return self.namespace["_publish_telegram_media_post"](
            bot_token="synthetic-only",
            chat_id="@synthetic",
            text=text,
            media_assets=[{"id": identity} for identity in identities],
            transport_source="test",
        )


class TelegramApprovedMediaCompletenessTests(unittest.TestCase):
    def test_any_unavailable_approved_asset_prevents_all_provider_calls(self):
        for missing in (("first",), ("last",), ("first", "last")):
            with self.subTest(missing=missing):
                fixture = MediaFixture(unavailable=missing)
                result = fixture.publish(["first", "last"])
                self.assertEqual(fixture.calls, [])
                self.assertEqual(result["status"], "needs_review")
                self.assertEqual(result["publish_outcome"], "not_attempted")
                self.assertEqual(
                    result["metadata_json"]["provider_status"],
                    "telegram_media_unavailable",
                )
                self.assertNotIn("provider_post_id", result)

    def test_complete_approved_album_keeps_all_files_order_and_caption(self):
        fixture = MediaFixture()
        result = fixture.publish(["first", "middle", "last"])
        self.assertEqual(result["status"], "published")
        self.assertEqual(result["publish_outcome"], "accepted")
        self.assertEqual(result["metadata_json"]["media_attachment_count"], 3)
        self.assertEqual(fixture.materialized, ["first", "middle", "last"])
        self.assertEqual(len(fixture.calls), 1)
        call = fixture.calls[0]
        self.assertEqual(call["method"], "sendMediaGroup")
        self.assertEqual(
            [item["content"] for item in call["files"]], [b"first", b"middle", b"last"]
        )
        media = json.loads(call["fields"]["media"])
        self.assertEqual(
            [item["media"] for item in media],
            ["attach://photo0", "attach://photo1", "attach://photo2"],
        )
        self.assertEqual(media[0]["caption"], "Synthetic approved caption")

    def test_single_photo_and_empty_selection_keep_existing_contract(self):
        fixture = MediaFixture()
        result = fixture.publish(["first"])
        self.assertEqual(result["publish_outcome"], "accepted")
        self.assertEqual(fixture.calls[0]["method"], "sendPhoto")
        self.assertEqual(fixture.calls[0]["files"][0]["field_name"], "photo")
        empty = MediaFixture()
        self.assertEqual(empty.publish([])["publish_outcome"], "not_attempted")
        self.assertEqual(empty.calls, [])

    def test_caption_followup_failure_retains_media_receipt_without_retry(self):
        fixture = MediaFixture(
            responses=[
                {"ok": True, "result": {"message_id": 21}},
                {
                    "ok": False,
                    "error": "synthetic caption failure",
                    "publish_outcome": "uncertain",
                },
            ]
        )
        result = fixture.publish(["first"], text="x" * 1025)
        self.assertEqual(result["provider_post_id"], "21")
        self.assertEqual(result["publish_outcome"], "accepted")
        self.assertEqual(result["last_error"], "synthetic caption failure")
        self.assertEqual(
            [call["method"] for call in fixture.calls], ["sendPhoto", "sendMessage"]
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
