from api import outreach_campaign_api as campaign_api


class AuthorCampaignPayloadCursor:
    def __init__(self):
        self.rows = []
        self.queries = []

    def execute(self, query, params=None):
        normalized = " ".join(query.lower().split())
        self.queries.append((normalized, params))
        if "from outreach_campaigns" in normalized and "where" in normalized:
            self.rows = [{
                "id": "campaign-1",
                "workstream_id": "workstream-1",
                "room_id": None,
                "status": "draft",
                "workstream_type": "creator_collaboration",
                "sender_mode": "localos_for_partner",
                "policy_json": {"sender_mode": "localos_for_partner"},
            }]
        elif "from outreach_campaign_touches touch" in normalized:
            self.rows = [{
                "id": "touch-1",
                "campaign_id": "campaign-1",
                "sequence_index": 0,
                "channel": "email",
                "status": "draft",
                "message_brief_json": {
                    "source_fact_fingerprint": "facts:creator-bridge-current",
                },
                "quality_gate_json": {"passed": True},
            }]
        elif "from lead_workstream_research" in normalized:
            self.rows = [{"report_hash": "legacy-research-row"}]
        elif "from outreach_campaign_events" in normalized:
            self.rows = []
        elif "from outreach_inbound_events" in normalized:
            self.rows = []
        elif "from outreachsendqueue queue" in normalized:
            self.rows = []
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


def test_author_payload_uses_creator_bridge_fingerprint_used_by_approval(monkeypatch):
    cursor = AuthorCampaignPayloadCursor()
    calls = []
    monkeypatch.setattr(
        campaign_api,
        "current_outreach_source_fact_fingerprint",
        lambda _cursor, workstream_id, sender_mode: calls.append(
            (workstream_id, sender_mode)
        ) or "facts:creator-bridge-current",
        raising=False,
    )
    monkeypatch.setattr(
        campaign_api,
        "generation_contract_current",
        lambda *_args, **_kwargs: True,
    )

    payload = campaign_api._campaign_payload(cursor, "campaign-1")

    assert "select workstream_type from lead_workstreams" in cursor.queries[0][0]
    assert calls == [("workstream-1", "localos_for_partner")]
    assert not any(
        "from lead_workstream_research" in query
        for query, _params in cursor.queries
    )
    assert payload["generation_current"] is True
    assert payload["requires_regeneration"] is False


def test_author_payload_keeps_changed_creator_facts_stale(monkeypatch):
    cursor = AuthorCampaignPayloadCursor()
    monkeypatch.setattr(campaign_api, "current_outreach_source_fact_fingerprint", lambda *_args: "facts:changed")
    monkeypatch.setattr(campaign_api, "generation_contract_current", lambda *_args: True)
    payload = campaign_api._campaign_payload(cursor, "campaign-1")
    assert payload["generation_current"] is False
    assert payload["requires_regeneration"] is True


def test_author_payload_keeps_missing_creator_facts_stale(monkeypatch):
    cursor = AuthorCampaignPayloadCursor()
    monkeypatch.setattr(campaign_api, "current_outreach_source_fact_fingerprint", lambda *_args: "")
    monkeypatch.setattr(campaign_api, "generation_contract_current", lambda *_args: True)
    payload = campaign_api._campaign_payload(cursor, "campaign-1")
    assert payload["generation_current"] is False
    assert payload["requires_regeneration"] is True


def test_author_payload_keeps_invalid_generation_contract_stale(monkeypatch):
    cursor = AuthorCampaignPayloadCursor()
    monkeypatch.setattr(campaign_api, "current_outreach_source_fact_fingerprint", lambda *_args: "facts:creator-bridge-current")
    monkeypatch.setattr(campaign_api, "generation_contract_current", lambda *_args: False)
    payload = campaign_api._campaign_payload(cursor, "campaign-1")
    assert payload["generation_current"] is False
    assert payload["requires_regeneration"] is True


def test_non_author_payload_retains_research_fingerprint_path(monkeypatch):
    cursor = AuthorCampaignPayloadCursor()
    monkeypatch.setattr(campaign_api, "is_localos_author_lane", lambda _campaign: False)
    monkeypatch.setattr(campaign_api, "research_source_fact_fingerprint", lambda research: "facts:creator-bridge-current" if research["report_hash"] == "legacy-research-row" else "")
    monkeypatch.setattr(campaign_api, "generation_contract_current", lambda *_args: True)

    def unexpected_creator_call(*_args):
        raise AssertionError("Non-author campaign must use research fingerprint")

    monkeypatch.setattr(campaign_api, "current_outreach_source_fact_fingerprint", unexpected_creator_call)
    payload = campaign_api._campaign_payload(cursor, "campaign-1")
    assert any("from lead_workstream_research" in query for query, _params in cursor.queries)
    assert payload["generation_current"] is True
    assert payload["requires_regeneration"] is False
