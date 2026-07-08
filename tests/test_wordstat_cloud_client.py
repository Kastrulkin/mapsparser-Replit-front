import pytest

from wordstat_client import WordstatClient, WordstatTemporaryUnavailable
from update_wordstat_data import _extract_queries


class _FakeConnection:
    def __init__(self):
        self.row_factory = None
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return object()

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class _OkResponse:
    status_code = 200
    headers = {}

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "results": [{"phrase": "стрижка москва", "count": "123"}],
            "associations": [{"phrase": "парикмахерская", "count": "77"}],
        }


class _RateLimitedResponse:
    status_code = 429
    headers = {"Retry-After": "60"}

    def raise_for_status(self):
        return None

    def json(self):
        return {}


def test_cloud_wordstat_client_calls_search_api_v2(monkeypatch):
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return _OkResponse()

    monkeypatch.setattr("wordstat_client.requests.post", fake_post)

    client = WordstatClient(api_key="test-key", folder_id="test-folder")
    data = client.get_popular_queries(["стрижка", "маникюр"], 213)

    assert len(data) == 2
    assert calls[0]["url"] == "https://searchapi.api.cloud.yandex.net/v2/wordstat/topRequests"
    assert calls[0]["headers"]["Authorization"] == "Api-Key test-key"
    assert calls[0]["json"]["folderId"] == "test-folder"
    assert calls[0]["json"]["phrase"] == "стрижка"
    assert calls[0]["json"]["regions"] == ["213"]
    assert calls[0]["json"]["devices"] == ["DEVICE_ALL"]


def test_extract_queries_supports_cloud_results_section():
    rows = _extract_queries({
        "results": [{"phrase": "стрижка москва", "count": "123"}],
        "associations": [{"phrase": "парикмахерская", "count": "77"}],
    })

    assert {"key": "стрижка москва", "clicks": 123} in rows
    assert {"key": "парикмахерская", "clicks": 77} in rows


def test_cloud_wordstat_client_stops_on_rate_limit(monkeypatch):
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(json)
        return _RateLimitedResponse()

    monkeypatch.setattr("wordstat_client.requests.post", fake_post)

    client = WordstatClient(api_key="test-key", folder_id="test-folder")

    with pytest.raises(WordstatTemporaryUnavailable):
        client.get_popular_queries(["стрижка", "маникюр"], 213)

    assert len(calls) == 1


def test_wordstat_update_endpoint_refreshes_selected_business(monkeypatch):
    from flask import Flask
    from api import wordstat_api

    fake_conn = _FakeConnection()
    refresh_calls = []

    monkeypatch.setattr(wordstat_api, "verify_session", lambda token: {"user_id": "user-1"})
    monkeypatch.setattr(wordstat_api, "get_business_owner_id", lambda cursor, business_id, include_active_check=True: "user-1")
    monkeypatch.setattr(wordstat_api, "get_db_connection", lambda: fake_conn)
    monkeypatch.setattr(wordstat_api.config, "is_configured", lambda: True)

    def fake_refresh(cursor, business_id):
        refresh_calls.append(business_id)
        return {
            "scope": "business",
            "targets": 1,
            "created": 3,
            "updated": 2,
            "fetched": 8,
            "saved": 5,
            "skipped_targets": 0,
        }

    monkeypatch.setattr(wordstat_api, "_refresh_business_wordstat_keywords", fake_refresh)

    app = Flask(__name__)
    app.register_blueprint(wordstat_api.wordstat_bp)
    client = app.test_client()

    response = client.post(
        "/api/wordstat/update",
        json={"business_id": "business-1"},
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["summary"]["scope"] == "business"
    assert data["summary"]["created"] == 3
    assert refresh_calls == ["business-1"]
    assert fake_conn.committed is True


def test_wordstat_update_endpoint_uses_cached_keywords_on_rate_limit(monkeypatch):
    from flask import Flask
    from api import wordstat_api

    fake_conn = _FakeConnection()

    monkeypatch.setattr(wordstat_api, "verify_session", lambda token: {"user_id": "user-1"})
    monkeypatch.setattr(wordstat_api, "get_business_owner_id", lambda cursor, business_id, include_active_check=True: "user-1")
    monkeypatch.setattr(wordstat_api, "get_db_connection", lambda: fake_conn)
    monkeypatch.setattr(wordstat_api.config, "is_configured", lambda: True)
    monkeypatch.setattr(
        wordstat_api,
        "_refresh_business_wordstat_keywords",
        lambda cursor, business_id: (_ for _ in ()).throw(WordstatTemporaryUnavailable("quota")),
    )
    monkeypatch.setattr(
        wordstat_api,
        "_count_existing_business_wordstat_items",
        lambda cursor, business_id: {"scope": "business", "targets": 1, "existing": 12, "last_update": None},
    )

    app = Flask(__name__)
    app.register_blueprint(wordstat_api.wordstat_bp)
    client = app.test_client()

    response = client.post(
        "/api/wordstat/update",
        json={"business_id": "business-1"},
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["warning"] == "wordstat_rate_limited_using_cached_keywords"
    assert data["summary"]["existing"] == 12
    assert fake_conn.rolled_back is True
