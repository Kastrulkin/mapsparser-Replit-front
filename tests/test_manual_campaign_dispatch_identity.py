"""Real campaign hash/preflight/binding with fake SQL and unrelated gate stubs."""
import pytest
from services import outreach_safety_service


class GenericCampaignPreflightCursor:
    """Faithful result routing for the SQL used by generic campaign preflight."""

    def __init__(self, item, touches):
        self.item = item
        self.touches = touches
        self.query = ""

    def execute(self, query, params=()):
        self.query = query

    def fetchall(self):
        if "SELECT * FROM outreach_campaign_touches" in self.query:
            return self.touches
        return []

    def fetchone(self):
        if "SELECT q.id, q.lead_id" in self.query:
            return self.item
        if "SELECT evidence_json, signals_json, report_hash" in self.query:
            return {"current": "source-fingerprint-A"}
        if "SELECT COUNT(*) AS sent_count" in self.query:
            return {"sent_count": 0}
        return None


def _generic_campaign_fixture(*, draft_body="Approved A", touch_approved="Approved A", recipient="owner@example.invalid"):
    from services.outreach_safety_service import approval_snapshot_hash

    campaign = {
        "id": "campaign-1",
        "version": 1,
        "workstream_id": "workstream-1",
        "lead_id": "lead-1",
        "scope_type": "business",
        "business_id": "business-1",
        "sender_profile_id": "profile-1",
        "policy_json": {"daily_limit": 10},
    }
    touch = {
        "id": "touch-1",
        "draft_id": "draft-1",
        "contact_point_id": "contact-1",
        "sender_account_id": "sender-1",
        "channel": "email",
        "sequence_index": 0,
        "angle_type": "introduction",
        "scheduled_at": None,
        "subject": "Approved subject",
        "generated_text": "Approved A",
        "approved_text": touch_approved,
        "message_brief_json": {"source_fact_fingerprint": "source-fingerprint-A"},
        "quality_gate_json": {"passed": True},
    }
    approved_snapshot_hash = approval_snapshot_hash(campaign, [touch])
    item = {
        "id": "queue-1",
        "lead_id": "lead-1",
        "lead_name": "Lead A",
        "workstream_id": "workstream-1",
        "campaign_workstream_id": "workstream-1",
        "campaign_touch_id": "touch-1",
        "touch_id": "touch-1",
        "queue_draft_id": "draft-1",
        "queued_draft_id": "draft-1",
        "queued_draft_status": "approved",
        "queued_draft_body": draft_body,
        "queued_draft_channel": "email",
        "queue_channel": "email",
        "queued_draft_contact_id": "contact-1",
        "queued_draft_lead_id": "lead-1",
        "queued_draft_workstream_id": "workstream-1",
        "sender_account_id": "sender-1",
        "delivery_status": "sending",
        "queue_recipient_key": "lead:lead-1",
        "touch_status": "queued",
        "channel": "email",
        "contact_point_id": "contact-1",
        "sequence_index": 0,
        "campaign_id": "campaign-1",
        "campaign_status": "approved",
        "scope_type": "business",
        "business_id": "business-1",
        "campaign_recipient_key": "lead:lead-1",
        "version": 1,
        "sender_profile_id": "profile-1",
        "approved_at": "2026-09-20T10:00:00+00:00",
        "approved_snapshot_hash": approved_snapshot_hash,
        "policy_json": {"daily_limit": 10},
        "sender_mode": "partner_business",
        "workstream_type": "client_partnership",
        "sender_scope_type": "business",
        "sender_channel": "email",
        "sender_identity": "business@example.invalid",
        "sender_business_id": "business-1",
        "sender_status": "connected",
        "health_status": "healthy",
        "sender_outreach_enabled": True,
        "sender_capabilities_json": {"direct_send": True, "reply_sync": True},
        "contact_type": "email",
        "normalized_value": recipient,
        "contact_verification_status": "verified",
    }
    return campaign, item, touch


def _allow_unrelated_generic_preflight_gates(monkeypatch):
    monkeypatch.setattr(outreach_safety_service, "load_partnership_repeat_contact_guard", lambda *_args, **_kwargs: {"blocked": False})
    monkeypatch.setattr(outreach_safety_service, "generation_contract_current", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(outreach_safety_service, "research_source_fact_fingerprint", lambda *_args, **_kwargs: "source-fingerprint-A")


def test_generic_campaign_unchanged_approval_is_admitted(monkeypatch):
    _allow_unrelated_generic_preflight_gates(monkeypatch)
    _campaign, current, touch = _generic_campaign_fixture()
    result = outreach_safety_service.run_dispatch_preflight(GenericCampaignPreflightCursor(current, [touch]), "queue-1")
    assert result["allowed"] is True


def test_generic_campaign_dispatch_binds_the_current_approved_bytes_and_recipient(monkeypatch):
    from services.outreach_dispatch_service import bind_preflight_dispatch_item

    _allow_unrelated_generic_preflight_gates(monkeypatch)
    _campaign, current, touch = _generic_campaign_fixture()
    preflight = outreach_safety_service.run_dispatch_preflight(GenericCampaignPreflightCursor(current, [touch]), "queue-1")
    earlier_provider_item = {
        "id": "queue-1",
        "approved_text": "Earlier provider bytes",
        "generated_text": "Earlier provider bytes",
        "email": "earlier@example.invalid",
    }

    assert preflight["allowed"] is True
    bound = bind_preflight_dispatch_item(earlier_provider_item, preflight)

    assert bound["approved_text"] == "Approved A"
    assert bound["email"] == "owner@example.invalid"


@pytest.mark.parametrize(
    ("draft_body", "touch_approved"),
    [
        ("Changed B after approval", "Approved A"),
        ("Approved A", "Changed B after approval"),
        ("Changed B after approval", "Changed B after approval"),
    ],
)
def test_generic_campaign_preflight_rejects_mutation_not_covered_by_the_campaign_hash(
    monkeypatch, draft_body, touch_approved
):
    _allow_unrelated_generic_preflight_gates(monkeypatch)
    campaign, current, touch = _generic_campaign_fixture(
        draft_body=draft_body,
        touch_approved=touch_approved,
    )
    original_touch = {**touch, "approved_text": "Approved A"}

    assert outreach_safety_service.approval_snapshot_hash(campaign, [touch]) == outreach_safety_service.approval_snapshot_hash(campaign, [original_touch])

    result = outreach_safety_service.run_dispatch_preflight(GenericCampaignPreflightCursor(current, [touch]), "queue-1")

    assert result["allowed"] is False


def test_generic_dispatch_refuses_to_use_a_preflight_result_without_a_fresh_payload():
    from services.outreach_dispatch_service import bind_preflight_dispatch_item

    with pytest.raises(ValueError):
        bind_preflight_dispatch_item(
            {"id": "queue-1", "approved_text": "Earlier provider bytes", "email": "earlier@example.invalid"},
            {"allowed": True, "item": {"id": "queue-1", "policy_json": {}}},
        )


@pytest.mark.parametrize(("field", "value"), [
    ("queue_draft_id", "different-draft"),
    ("queued_draft_id", "different-draft"),
    ("queued_draft_status", "edited"),
    ("queued_draft_channel", "telegram"),
    ("queue_channel", "telegram"),
    ("sender_channel", "telegram"),
    ("queued_draft_contact_id", "different-contact"),
    ("contact_point_id", "different-contact"),
    ("queued_draft_lead_id", "different-lead"),
    ("queued_draft_workstream_id", "different-workstream"),
    ("workstream_id", "different-workstream"),
    ("sender_account_id", "different-sender"),
    ("campaign_touch_id", "different-touch"),
])
def test_generic_preflight_blocks_unbound_queue_or_draft(monkeypatch, field, value):
    _allow_unrelated_generic_preflight_gates(monkeypatch)
    _campaign, current, touch = _generic_campaign_fixture()
    current[field] = value
    result = outreach_safety_service.run_dispatch_preflight(GenericCampaignPreflightCursor(current, [touch]), "queue-1")
    assert result["allowed"] is False
    assert result["reason_code"] == "campaign_queued_draft_changed"


@pytest.mark.parametrize(("channel", "recipient", "provider_field"), [
    ("email", "owner@example.invalid", "email"),
    ("telegram", "https://t.me/reviewed_contact", "telegram_url"),
    ("vk", "https://vk.com/reviewed_contact", "contact_value"),
])
def test_automatic_channels_use_fresh_preflight_fields_without_lead_fallback(
    monkeypatch, channel, recipient, provider_field
):
    from services.outreach_dispatch_service import bind_preflight_dispatch_item

    _allow_unrelated_generic_preflight_gates(monkeypatch)
    campaign, current, touch = _generic_campaign_fixture(recipient=recipient)
    touch["channel"] = channel
    for field in ("channel", "queue_channel", "queued_draft_channel", "sender_channel", "contact_type"):
        current[field] = channel
    current["telegram_outreach_enabled"] = True
    current["approved_snapshot_hash"] = outreach_safety_service.approval_snapshot_hash(campaign, [touch])
    result = outreach_safety_service.run_dispatch_preflight(GenericCampaignPreflightCursor(current, [touch]), "queue-1")
    assert result["allowed"] is True
    original = {"id": "queue-1", "approved_text": "stale", "phone": "old-phone",
                "whatsapp_url": "old-whatsapp", "telegram_url": "old-telegram", "email": "old-email"}
    bound = bind_preflight_dispatch_item(original, result)
    assert bound[provider_field] == recipient
    assert bound["approved_text"] == bound["generated_text"] == "Approved A"
    assert bound["subject"] == "Approved subject"
    assert bound["channel"] == channel
    assert bound["sender_account_id"] == "sender-1"
    assert bound["phone"] is None
    assert bound["whatsapp_url"] is None
    assert original["approved_text"] == "stale"
    current["normalized_value"] = "changed-after-preflight"
    touch["generated_text"] = "changed-after-preflight"
    assert bound[provider_field] == recipient
    assert bound["approved_text"] == "Approved A"


@pytest.mark.parametrize("channel", ["whatsapp", "max", "sms", "phone", "manual", "vk_manual"])
def test_generic_dispatch_does_not_promote_manual_channels(monkeypatch, channel):
    _allow_unrelated_generic_preflight_gates(monkeypatch)
    campaign, current, touch = _generic_campaign_fixture()
    touch["channel"] = channel
    for field in ("channel", "queue_channel", "queued_draft_channel", "sender_channel", "contact_type"):
        current[field] = channel
    current["approved_snapshot_hash"] = outreach_safety_service.approval_snapshot_hash(campaign, [touch])
    result = outreach_safety_service.run_dispatch_preflight(GenericCampaignPreflightCursor(current, [touch]), "queue-1")
    assert result["allowed"] is False
    assert result["reason_code"] == "campaign_dispatch_contact_invalid"


@pytest.mark.parametrize(("field", "value", "reason"), [
    ("contact_type", "telegram", "campaign_dispatch_contact_invalid"),
    ("normalized_value", "  ", "campaign_dispatch_contact_invalid"),
    ("sender_status", "disconnected", "sender_not_connected"),
    ("sender_outreach_enabled", False, "sender_permission_revoked"),
    ("contact_verification_status", "stale", "recipient_contact_invalid"),
])
def test_other_preflight_gates_still_reject(monkeypatch, field, value, reason):
    _allow_unrelated_generic_preflight_gates(monkeypatch)
    _campaign, current, touch = _generic_campaign_fixture()
    current[field] = value
    result = outreach_safety_service.run_dispatch_preflight(GenericCampaignPreflightCursor(current, [touch]), "queue-1")
    assert result["allowed"] is False
    assert result["reason_code"] == reason


def test_generic_generation_gate_keeps_default_ai_requirement(monkeypatch):
    _allow_unrelated_generic_preflight_gates(monkeypatch)
    calls = []
    monkeypatch.setattr(outreach_safety_service, "generation_contract_current",
                        lambda *args, **kwargs: calls.append(kwargs) or False)
    _campaign, current, touch = _generic_campaign_fixture()
    result = outreach_safety_service.run_dispatch_preflight(GenericCampaignPreflightCursor(current, [touch]), "queue-1")
    assert result["allowed"] is False
    assert result["reason_code"] == "generation_contract_outdated"
    assert calls == [{"require_ai": None}]


def test_changed_hashed_body_requires_new_campaign_approval(monkeypatch):
    _allow_unrelated_generic_preflight_gates(monkeypatch)
    _campaign, current, touch = _generic_campaign_fixture()
    current["queued_draft_body"] = touch["generated_text"] = touch["approved_text"] = "New unapproved body"
    result = outreach_safety_service.run_dispatch_preflight(GenericCampaignPreflightCursor(current, [touch]), "queue-1")
    assert result["allowed"] is False
    assert result["reason_code"] == "approval_version_changed"
