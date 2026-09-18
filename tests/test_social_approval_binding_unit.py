"""Pure approval descriptor coverage for every API publishing platform."""

import pathlib
import sys

import pytest


ROOT = pathlib.Path(__file__).parents[1]


class _Cursor:
    description = [("id",), ("business_id",), ("source",), ("external_id",), ("auth_data_encrypted",)]

    def __init__(self, platform):
        self.platform = platform
        self.query = ""

    def execute(self, query, params):
        self.query = query

    def fetchone(self):
        if "FROM businesses" in self.query:
            return ("@approved_channel", "123:synthetic-bot-token")
        source = "google_business" if self.platform == "google_business" else "meta" if self.platform in {"facebook", "instagram"} else "vk"
        external_id = "locations/approved" if self.platform == "google_business" else "page-approved"
        return ("account-1", "business-1", source, external_id, "encrypted")


@pytest.mark.parametrize(
    ("platform", "auth_data", "recipient"),
    (
        ("telegram", {}, {"chat_id": "@approved_channel"}),
        ("vk", {"access_token": "synthetic", "owner_id": "-42"}, {"id": "-42"}),
        ("google_business", {}, {"id": "locations/approved"}),
        ("facebook", {"access_token": "synthetic", "page_id": "page-approved"}, {"id": "page-approved"}),
        ("instagram", {"access_token": "synthetic", "ig_user_id": "ig-approved"}, {"id": "ig-approved"}),
    ),
)
def test_api_approval_snapshot_binds_nonsecret_destination(platform, auth_data, recipient, monkeypatch):
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    from services.social_posts import approval_binding

    monkeypatch.setattr(approval_binding, "_media_descriptor", lambda cursor, post: [])
    monkeypatch.setattr(approval_binding, "decrypt_auth_data", lambda encrypted: auth_data)
    monkeypatch.setattr(approval_binding, "decode_telegram_bot_token", lambda encrypted: "123:synthetic-bot-token")
    snapshot = approval_binding.build_approval_snapshot(
        _Cursor(platform),
        {
            "business_id": "business-1",
            "platform": platform,
            "publish_mode": "api",
            "platform_text": "Approved text",
        },
        "approval-1",
    )

    assert snapshot["binding"]["provider"] == platform
    assert snapshot["binding"]["recipient"] == recipient
    assert approval_binding._contains_sensitive_key(snapshot) is False
    assert "synthetic-bot-token" not in str(snapshot)


def test_usage_history_overflow_fails_closed_before_media_deduplication(monkeypatch):
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    from services.social_posts import media_delivery

    class Cursor:
        def execute(self, query, params):
            return None

        def fetchall(self):
            return [{"id": "old-asset"}] * 101

    monkeypatch.setattr(media_delivery, "_row_to_dict", lambda cursor, row: row)

    with pytest.raises(ValueError, match="неоднозначен"):
        media_delivery._strict_selected_media_assets(
            Cursor(),
            {"id": "post-1", "business_id": "business-1", "platform": "telegram", "media_json": []},
        )
