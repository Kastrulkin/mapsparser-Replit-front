import sys

from flask import Flask


if "src" not in sys.path:
    sys.path.insert(0, "src")

from api import finance_api


class _Cursor:
    def __init__(self):
        self.executions = []
        self.description = [
            ("investment_amount",),
            ("returns_amount",),
            ("roi_percentage",),
            ("period_start",),
            ("period_end",),
        ]

    def execute(self, query, params=()):
        self.executions.append((" ".join(str(query).split()).lower(), tuple(params or ())))

    def fetchone(self):
        return (1000, 1500, 50, "2026-08-01", "2026-08-07")


class _Connection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def commit(self):
        return None


class _Database:
    cursor = _Cursor()

    def __init__(self):
        self.conn = _Connection(self.cursor)

    def close(self):
        return None


def _client(monkeypatch):
    _Database.cursor = _Cursor()
    monkeypatch.setattr(finance_api, "DatabaseManager", _Database)
    monkeypatch.setattr(finance_api, "verify_session", lambda _token: {"user_id": "user-1"})
    monkeypatch.setattr(finance_api, "get_business_id_from_user", lambda _user_id, requested: requested)
    monkeypatch.setattr(finance_api, "verify_business_access", lambda _cursor, business_id, _user: (business_id == "business-2", "owner-1"))
    app = Flask(__name__)
    app.register_blueprint(finance_api.finance_bp)
    return app.test_client()


def test_roi_read_and_write_are_scoped_to_the_selected_business(monkeypatch):
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}

    read_response = client.get("/api/finance/roi?business_id=business-2", headers=headers)
    write_response = client.post(
        "/api/finance/roi",
        headers=headers,
        json={
            "business_id": "business-2",
            "investment_amount": 1000,
            "returns_amount": 1500,
            "period_start": "2026-08-01",
            "period_end": "2026-08-07",
        },
    )

    assert read_response.status_code == 200
    assert write_response.status_code == 200
    roi_queries = [item for item in _Database.cursor.executions if "roidata" in item[0]]
    assert roi_queries
    assert all("business_id" in query for query, _params in roi_queries)
    assert all("business-2" in params for _query, params in roi_queries)
