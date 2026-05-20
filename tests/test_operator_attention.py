from services.operator_attention import build_attention_brief


class FakeCursor:
    def __init__(self, tables=None, columns=None):
        self.tables = set(tables or [])
        self.columns = columns or {}
        self.last_query = ""
        self.last_params = ()

    def execute(self, query, params=None):
        self.last_query = " ".join(str(query or "").lower().split())
        self.last_params = params or ()

    def fetchone(self):
        query = self.last_query
        if "to_regclass" in query:
            table_ref = str((self.last_params or ("",))[0] or "").split(".")[-1]
            return {"table_ref": table_ref if table_ref in self.tables else None}
        if "information_schema.columns" in query:
            table_name = self.last_params[0]
            column_name = self.last_params[1]
            return {"found": 1} if column_name in self.columns.get(table_name, set()) else None
        if "from businesses" in query:
            return {"id": "biz-1", "name": "Салон LocalOS", "business_name": None, "description": ""}
        if "from cards" in query:
            return {
                "id": "card-1",
                "created_at": "2026-05-18T10:00:00+00:00",
                "rating": 4.9,
                "reviews_count": 12,
                "overview": {"photos_count": 4, "news_count": 1},
                "photos": [],
                "news": [],
                "reviews": [],
            }
        if "from externalbusinessreviews" in query:
            return {
                "total": 12,
                "with_response": 9,
                "without_response": 3,
                "latest_seen_at": "2026-05-19T08:00:00+00:00",
            }
        if "from usernews" in query:
            return {"cnt": 2}
        if "from reviewreplydrafts" in query:
            return {"cnt": 1}
        if "from action_requests" in query:
            return {"cnt": 1}
        if "from prospectingleads" in query:
            return {"total": 5, "ready": 2}
        return None


def test_attention_brief_uses_cached_data_and_reports_no_execution():
    cursor = FakeCursor(
        tables={
            "businesses",
            "cards",
            "externalbusinessreviews",
            "usernews",
            "reviewreplydrafts",
            "action_requests",
            "prospectingleads",
        },
        columns={
            "cards": {"business_id", "id", "created_at", "rating", "reviews_count", "overview", "photos", "news", "reviews"},
            "externalbusinessreviews": {"response_text"},
            "usernews": {"business_id"},
            "prospectingleads": {"intent", "partnership_stage", "status"},
        },
    )

    brief = build_attention_brief(cursor, "biz-1", "user-1")

    assert brief["action_class"] == "free_cached"
    assert brief["data_mode"] == "cached"
    assert brief["limits"]["paid_actions_performed"] is False
    assert brief["paid_action_offers"][0]["action_key"] == "map_reviews_refresh"
    assert brief["paid_action_offers"][0]["status"] == "proposal_only"
    assert brief["paid_action_offers"][0]["credit_multiplier"] == 10
    assert brief["limits"]["external_writes_performed"] is False
    assert brief["metrics"]["reviews_without_response"] == 3
    assert brief["metrics"]["pending_approvals"] == 1
    item_ids = {item["id"] for item in brief["items"]}
    assert "reviews_without_response" in item_ids
    assert "pending_approvals" in item_ids
    assert "partnership_leads_ready" in item_ids


def test_attention_brief_handles_missing_optional_tables():
    cursor = FakeCursor(
        tables={"businesses"},
        columns={},
    )

    brief = build_attention_brief(cursor, "biz-1", "user-1")

    assert brief["metrics"]["reviews_without_response"] == 0
    assert brief["metrics"]["pending_news"] == 0
    assert brief["freshness"]["paid_refresh_required_for_fresh_data"] is True
    assert brief["paid_action_offers"][0]["estimate_available"] is False
    assert brief["limits"]["manual_publication_only"] is True
    assert brief["items"]
