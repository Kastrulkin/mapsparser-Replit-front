from api.outreach_campaign_api import _campaign_payload


class CampaignHistoryCursor:
    def __init__(self):
        self.rows = []

    def execute(self, query, params=None):
        normalized = " ".join(query.lower().split())
        if "from outreach_campaigns where id" in normalized:
            self.rows = [{
                "id": "campaign-1",
                "workstream_id": "workstream-1",
                "room_id": None,
                "status": "stopped",
                "last_reply_at": "2026-07-23T10:30:00+00:00",
            }]
        elif "from outreach_campaign_touches where campaign_id" in normalized:
            self.rows = [{
                "id": "touch-1",
                "campaign_id": "campaign-1",
                "sequence_index": 0,
                "channel": "email",
                "status": "sent",
                "generated_text": "Первое сообщение",
                "message_brief_json": {},
                "quality_gate_json": {},
            }]
        elif "from outreach_campaign_events" in normalized:
            self.rows = []
        elif "from outreach_inbound_events" in normalized:
            self.rows = [{
                "id": "reply-1",
                "campaign_id": "campaign-1",
                "touch_id": "touch-1",
                "channel": "email",
                "event_type": "reply",
                "classification": "interested",
                "is_human": True,
                "stops_campaign": True,
                "raw_payload_json": {"raw_reply": "Да, пришлите детали"},
            }]
        elif "from outreachsendqueue queue" in normalized:
            self.rows = [{
                "id": "delivery-1",
                "touch_id": "touch-1",
                "channel": "email",
                "delivery_status": "delivered",
                "provider_message_id": "provider-message-1",
            }]
        elif "from sales_rooms" in normalized:
            self.rows = []
        elif "from lead_relationship_states" in normalized:
            self.rows = []
        else:
            raise AssertionError(f"Unexpected query: {normalized}")

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return list(self.rows)


def test_campaign_payload_links_delivery_and_human_reply_to_exact_touch():
    payload = _campaign_payload(CampaignHistoryCursor(), "campaign-1")

    assert payload is not None
    assert payload["touches"][0]["id"] == "touch-1"
    assert payload["deliveries"][0]["touch_id"] == "touch-1"
    assert payload["inbound_events"][0]["touch_id"] == "touch-1"
    assert payload["inbound_events"][0]["raw_payload_json"]["raw_reply"] == "Да, пришлите детали"
    assert payload["inbound_events"][0]["stops_campaign"] is True
