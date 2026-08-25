from flask import Flask

from api import network_health_api


class _Cursor:
    def __init__(self):
        self.query = ""

    def execute(self, query, params=None):
        self.query = " ".join(str(query).split())

    def fetchone(self):
        if "SELECT owner_id FROM Businesses" in self.query:
            return {"owner_id": "owner-1"}
        if "SELECT to_regclass" in self.query:
            return {"exists_flag": True}
        if "source = 'yandex_business'" in self.query:
            return {"count": 5}
        raise AssertionError(f"Unexpected fetchone query: {self.query}")

    def fetchall(self):
        if "FROM businesses b" not in self.query:
            raise AssertionError(f"Unexpected fetchall query: {self.query}")
        return [
            {
                "business_id": "business-1",
                "business_name": "Organica",
                "address": "Saint Petersburg",
                "business_type": "beauty",
                "yandex_url": "https://yandex.example/organica",
                "rating": 4.9,
                "reviews_count": 345,
                "news_count": 1,
                "unanswered_reviews_count": 2,
            }
        ]


class _Database:
    def __init__(self):
        self.conn = self
        self.cursor_instance = _Cursor()

    def cursor(self):
        return self.cursor_instance

    def close(self):
        return None


def test_single_business_health_uses_current_review_snapshot(monkeypatch):
    monkeypatch.setattr(
        network_health_api,
        "verify_session",
        lambda _token: {"user_id": "owner-1", "is_superadmin": False},
    )
    monkeypatch.setattr(network_health_api, "DatabaseManager", _Database)
    monkeypatch.setattr(network_health_api, "ensure_growth_schema", lambda _db: None)
    monkeypatch.setattr(
        network_health_api,
        "_get_map_metrics",
        lambda _cursor, _business_id: {"rating": 4.9, "reviews_count": 345},
    )

    app = Flask(__name__)
    app.register_blueprint(network_health_api.network_health_bp)
    client = app.test_client()

    response = client.get(
        "/api/network/health?business_id=business-1",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.get_json()["data"]["unanswered_reviews_count"] == 2
