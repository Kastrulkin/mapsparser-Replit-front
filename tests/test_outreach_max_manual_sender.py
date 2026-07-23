from __future__ import annotations

from pathlib import Path

import pytest

from services.outreach_sender_service import (
    change_sender_permission,
    connect_manual_max_sender,
    normalize_manual_max_phone,
)


class SenderCursor:
    def __init__(self) -> None:
        self.row = None
        self.sender = None

    def execute(self, query, params=()):
        normalized = " ".join(str(query).split())
        self.row = None
        if normalized.startswith("SELECT * FROM outreach_sender_accounts"):
            self.row = self.sender
            return
        if normalized.startswith("INSERT INTO outreach_sender_accounts"):
            capabilities = params[6].adapted
            self.sender = {
                "id": params[0],
                "scope_type": params[1],
                "business_id": params[2],
                "owner_user_id": params[3],
                "channel": "max",
                "sender_identity": params[4],
                "display_name": params[5],
                "status": "connected",
                "outreach_enabled": False,
                "capabilities_json": capabilities,
                "health_status": "healthy",
                "health_score": 100,
            }
            self.row = self.sender
            return
        if normalized.startswith("UPDATE outreach_sender_accounts SET health_status") and self.sender:
            self.sender["health_status"] = "healthy"
            self.sender["health_score"] = 100

    def fetchone(self):
        return self.row


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+7 921 422-48-43", "+79214224843"),
        ("8 (921) 422-48-43", "+79214224843"),
    ],
)
def test_normalize_manual_max_phone(raw, expected):
    assert normalize_manual_max_phone(raw) == expected


def test_manual_max_sender_is_saved_without_automation_permission():
    cursor = SenderCursor()

    sender = connect_manual_max_sender(
        cursor,
        scope_type="platform",
        business_id=None,
        owner_user_id="superadmin-1",
        phone="+7 921 422-48-43",
        display_name="LocalOS · MAX",
    )

    assert sender["channel"] == "max"
    assert sender["sender_identity"] == "+79214224843"
    assert sender["status"] == "connected"
    assert sender["outreach_enabled"] is False
    assert sender["reply_sync_enabled"] is False
    assert sender["capabilities"] == {
        "provider": "manual_max",
        "account_kind": "personal_account_manual",
        "direct_send": False,
        "reply_sync": False,
        "manual_handoff": True,
        "recipient_requires_max_url_or_manual_contact": True,
    }

    with pytest.raises(ValueError, match="Direct send and reply sync are required"):
        change_sender_permission(
            cursor,
            sender["id"],
            outreach_enabled=True,
            actor_id="superadmin-1",
        )


def test_manual_max_endpoint_never_claims_an_automatic_connection():
    source = Path("src/api/outreach_campaign_api.py").read_text(encoding="utf-8")

    assert 'post("/api/outreach/sender-accounts/max/manual")' in source
    assert '"messages_sent": 0' in source
    assert "MAX добавлен в ручном режиме" in source


def test_sender_pause_still_covers_campaign_and_queue():
    source = Path("src/services/outreach_sender_service.py").read_text(encoding="utf-8")
    pause_start = source.index("def _pause_sender_work")
    max_start = source.index("def normalize_manual_max_phone")
    pause_source = source[pause_start:max_start]

    assert "UPDATE outreach_campaign_touches" in pause_source
    assert "UPDATE outreach_campaigns campaign" in pause_source
    assert "UPDATE outreachsendqueue" in pause_source
