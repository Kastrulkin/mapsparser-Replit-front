import pytest

from services.outreach_campaign_service import change_campaign_status


class ResumeCursor:
    def __init__(self, campaign, touches):
        self.campaign = campaign
        self.touches = touches
        self.rows = []
        self.queries = []

    def execute(self, query, params=()):
        self.queries.append((query, params))
        normalized = " ".join(query.lower().split())
        if "from outreach_campaigns where id" in normalized:
            self.rows = [self.campaign]
        elif "from outreach_campaign_touches where campaign_id" in normalized and "select count" in normalized:
            self.rows = [{"count": 0}]
        elif "from outreach_campaign_touches t left join outreach_sender_accounts" in normalized:
            self.rows = self.touches
        elif "update outreach_campaigns set status" in normalized:
            self.rows = [{"id": "campaign", "version": 1, "status": "approved", "stop_reason": None}]
        else:
            self.rows = []

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return list(self.rows)


def _campaign(*, sender_mode="localos_for_partner", policy=None):
    return {
        "id": "campaign", "status": "paused", "approved_snapshot_hash": "snapshot",
        "scope_type": "business", "business_id": "business-1", "sender_mode": sender_mode,
        "policy_json": policy or {
            "sender_mode": sender_mode,
            "represented_business_id": "business-1",
        },
    }


def _touch(**changes):
    touch = {
        "id": "touch", "channel": "email", "sender_account_id": "sender",
        "sender_scope_type": "platform", "sender_business_id": None,
        "sender_status": "connected", "sender_health_status": "healthy",
        "sender_outreach_enabled": True,
        "sender_capabilities_json": {"direct_send": True, "reply_sync": True},
        "telegram_outreach_enabled": True,
    }
    touch.update(changes)
    return touch


def test_resume_accepts_platform_localos_sender_for_author_partner_campaign():
    cursor = ResumeCursor(_campaign(), [_touch()])

    result = change_campaign_status(cursor, "campaign", "resume", user_id="admin")

    assert result["status"] == "approved"


@pytest.mark.parametrize(
    ("campaign", "touch"),
    [
        (_campaign(policy={"sender_mode": "localos_for_partner", "represented_business_id": "other-business"}), _touch()),
        (_campaign(), _touch(sender_scope_type="business", sender_business_id="business-1")),
        (_campaign(), _touch(sender_status="disconnected")),
        (_campaign(), _touch(sender_outreach_enabled=False)),
        (_campaign(), _touch(channel="telegram", telegram_outreach_enabled=False)),
        (_campaign(sender_mode="partner_business"), _touch()),
    ],
)
def test_resume_keeps_scope_and_sender_capability_preflight(campaign, touch):
    cursor = ResumeCursor(campaign, [touch])

    with pytest.raises(ValueError, match="Sender account preflight failed"):
        change_campaign_status(cursor, "campaign", "resume", user_id="admin")

    assert not any("update outreach_campaigns set status" in query.lower() for query, _ in cursor.queries)


@pytest.mark.parametrize(
    ("capability", "value"),
    [
        ("direct_send", False),
        ("direct_send", "false"),
        ("direct_send", None),
        ("reply_sync", False),
        ("reply_sync", "false"),
        ("reply_sync", None),
    ],
)
def test_resume_requires_strict_boolean_sender_capabilities(capability, value):
    capabilities = {"direct_send": True, "reply_sync": True}
    if value is None:
        del capabilities[capability]
    else:
        capabilities[capability] = value
    cursor = ResumeCursor(_campaign(), [_touch(sender_capabilities_json=capabilities)])

    with pytest.raises(ValueError, match="Sender account preflight failed"):
        change_campaign_status(cursor, "campaign", "resume", user_id="admin")
