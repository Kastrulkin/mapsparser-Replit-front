"""Recipient projection only: no DB, provider, approval or send effects."""
import pytest

from api.outreach_campaign_api import _campaign_payload
from services import outreach_campaign_service
from tests.test_author_template_authorization import (
    Cursor,
    _preview_context_for_author_variant,
    _stub_author_preview_dependencies,
    grant,
)
from tests.test_outreach_campaign_history_payload import CampaignHistoryCursor


class RecipientProjectionCursor(CampaignHistoryCursor):
    def __init__(self, recipient):
        super().__init__()
        self.recipient = recipient
        self.touch_query = ""

    def execute(self, query, params=None):
        super().execute(query, params)
        if "FROM outreach_campaign_touches touch" in query:
            self.touch_query = " ".join(query.split())
            # Model SQL's projection: a joined column is absent until selected.
            if "contact.normalized_value AS recipient" in query:
                for row in self.rows:
                    row["recipient"] = self.recipient


def test_existing_history_identity_is_preserved_positive_control():
    payload = _campaign_payload(RecipientProjectionCursor("reviewed@example.invalid"), "campaign-1")
    assert payload["touches"][0]["id"] == "touch-1"
    assert payload["deliveries"][0]["touch_id"] == "touch-1"
    assert payload["inbound_events"][0]["touch_id"] == "touch-1"


@pytest.mark.parametrize("recipient", ["reviewed@example.invalid", "https://t.me/reviewed", None])
def test_saved_touch_projects_its_exact_contact_or_null_without_lead_fallback(recipient):
    cursor = RecipientProjectionCursor(recipient)
    payload = _campaign_payload(cursor, "campaign-1")
    assert payload["touches"][0]["recipient"] == recipient
    assert "LEFT JOIN lead_contact_points contact ON contact.id = touch.contact_point_id" in cursor.touch_query


def test_real_preview_carries_selected_recipient_on_the_touch(monkeypatch):
    context = _preview_context_for_author_variant("neutral_greeting_v1")
    context["creator_outreach_bridge"]["preferred_contact"] = "reviewed@example.invalid"
    _stub_author_preview_dependencies(monkeypatch, context)
    monkeypatch.setattr(outreach_campaign_service, "load_author_template_authorization", lambda cursor: grant())
    monkeypatch.setattr(outreach_campaign_service, "channel_availability", lambda *args: {
        "email": {"status": "ready", "contact_point_id": "contact", "sender_account_id": "sender",
                  "recipient": "reviewed@example.invalid"},
    })
    preview = outreach_campaign_service.build_preview(Cursor(), "workstream", generate_ai=False)
    assert preview["touches"]
    assert preview["touches"][0]["contact_point_id"] == "contact"
    assert preview["touches"][0]["recipient"] == "reviewed@example.invalid"


def test_review_display_prefers_normalized_provider_address_over_display_value():
    availability = outreach_campaign_service.channel_availability(Cursor(), {
        "sender_mode": "localos_for_partner", "client_business_id": "business-1",
        "selected_contact_point_id": "selected-contact",
        "contacts": [{"id": "selected-contact", "contact_type": "email",
                      "value": "ReviewED@example.invalid", "normalized_value": "reviewed@example.invalid",
                      "verification_status": "confirmed_source", "confidence": 0.9}],
    })
    assert availability["email"]["recipient"] == "reviewed@example.invalid"
