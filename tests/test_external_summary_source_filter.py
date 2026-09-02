from datetime import datetime

import main
from api import external_accounts_api


class SourceFilteredSummaryCursor:
    def __init__(self):
        self.one = None
        self.many = []
        self.description = []

    def execute(self, query, params=None):
        normalized = " ".join(str(query).split()).lower()
        self.one = None
        self.many = []

        if "from information_schema.tables" in normalized:
            self.many = [
                {"table_name": "externalbusinessstats"},
                {"table_name": "externalbusinessreviews"},
            ]
        elif "select id, network_id, owner_id, name from businesses" in normalized:
            self.one = {
                "id": "business-1",
                "network_id": None,
                "owner_id": "owner-1",
                "name": "Business",
            }
        elif "from externalbusinessstats" in normalized:
            # Google has no collected statistics.
            self.many = []
        elif "from externalbusinessreviews" in normalized:
            # Google has no collected reviews.
            self.one = {"total": 0, "with_response": 0, "without_response": 0}
        elif "from cards" in normalized and "is_latest = true" in normalized:
            self.one = {
                "created_at": datetime(2026, 8, 12, 8, 52),
                "rating": 4.8,
                "reviews_count": 142,
                "overview": {"snapshot_type": "full", "source": "yandex_maps"},
            }
        elif "from cards" in normalized:
            self.many = [{
                "created_at": datetime(2026, 8, 12, 8, 52),
                "rating": 4.8,
                "reviews_count": 142,
                "competitors": None,
                "overview": {"snapshot_type": "full", "source": "yandex_maps"},
            }]

    def fetchone(self):
        return self.one

    def fetchall(self):
        return list(self.many)


class SourceFilteredSummaryDatabase:
    def __init__(self):
        self.conn = self
        self.cursor_value = SourceFilteredSummaryCursor()

    def cursor(self):
        return self.cursor_value

    def close(self):
        return None


def test_google_summary_does_not_fall_back_to_yandex_card_metrics(monkeypatch):
    monkeypatch.setattr(external_accounts_api, "get_capability_access", lambda *_args, **_kwargs: {"allowed": True})
    monkeypatch.setattr(
        external_accounts_api,
        "verify_session",
        lambda token: {"user_id": "owner-1", "is_superadmin": False},
    )
    monkeypatch.setattr(
        external_accounts_api,
        "verify_business_access",
        lambda cursor, business_id, user_data: (True, "owner-1"),
    )
    monkeypatch.setattr(
        external_accounts_api,
        "DatabaseManager",
        SourceFilteredSummaryDatabase,
    )

    response = main.app.test_client().get(
        "/api/business/business-1/external/summary?source=google",
        headers={"Authorization": "Bearer owner-token"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["source"] == "google"
    assert payload["reviews_total"] == 0
    assert payload["rating"] is None
