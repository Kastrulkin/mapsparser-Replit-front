from flask import Flask

from api import crm_integration_requests_api


class _Cursor:
    def __init__(self):
        self.queries = []
        self.fetchone_results = [None, {
            "id": "request-1",
            "business_id": "business-1",
            "requested_by": "user-1",
            "crm_name": "MoySklad",
            "note": "Нужна выручка и средний чек",
            "status": "open",
            "created_at": None,
            "updated_at": None,
        }]

    def execute(self, query, params=None):
        self.queries.append((query, params))

    def fetchone(self):
        return self.fetchone_results.pop(0)


class _Connection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.committed = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        return None


class _Database:
    cursor = _Cursor()
    connection = _Connection(cursor)

    def __init__(self):
        self.conn = self.connection

    def close(self):
        return None


def _app():
    app = Flask(__name__)
    app.register_blueprint(crm_integration_requests_api.crm_integration_requests_bp)
    return app


def test_crm_request_is_scope_checked_and_persisted(monkeypatch):
    _Database.cursor = _Cursor()
    _Database.connection = _Connection(_Database.cursor)
    monkeypatch.setattr(crm_integration_requests_api, "require_auth_from_request", lambda: {"user_id": "user-1"})
    monkeypatch.setattr(crm_integration_requests_api, "verify_business_access", lambda *_args: (True, "user-1"))
    monkeypatch.setattr(crm_integration_requests_api, "DatabaseManager", _Database)

    response = _app().test_client().post(
        "/api/business/business-1/crm-integration-requests",
        json={"crm_name": "  MoySklad  ", "note": "Нужна выручка и средний чек"},
    )

    assert response.status_code == 201
    assert response.get_json()["request"]["crm_name"] == "MoySklad"
    assert _Database.connection.committed is True
    insert_params = next(params for query, params in _Database.cursor.queries if "INSERT INTO crm_integration_requests" in query)
    assert insert_params[3:] == (
        "MoySklad",
        "moysklad",
        "",
        "",
        "business",
        "business-1",
        "Нужна выручка и средний чек",
    )


def test_crm_request_rejects_foreign_business(monkeypatch):
    monkeypatch.setattr(crm_integration_requests_api, "require_auth_from_request", lambda: {"user_id": "user-1"})
    monkeypatch.setattr(crm_integration_requests_api, "verify_business_access", lambda *_args: (False, "other-user"))
    monkeypatch.setattr(crm_integration_requests_api, "DatabaseManager", _Database)

    response = _app().test_client().post(
        "/api/business/foreign-business/crm-integration-requests",
        json={"crm_name": "MoySklad"},
    )

    assert response.status_code == 403
    assert response.get_json()["error"] == "Нет доступа к бизнесу"


def test_crm_request_rejects_network_scope_tampering(monkeypatch):
    cursor = _Cursor()
    cursor.fetchone_results = [{"network_id": "network-1"}]
    _Database.cursor = cursor
    _Database.connection = _Connection(cursor)
    monkeypatch.setattr(crm_integration_requests_api, "require_auth_from_request", lambda: {"user_id": "user-1"})
    monkeypatch.setattr(crm_integration_requests_api, "verify_business_access", lambda *_args: (True, "user-1"))
    monkeypatch.setattr(crm_integration_requests_api, "DatabaseManager", _Database)

    response = _app().test_client().post(
        "/api/business/business-1/crm-integration-requests",
        json={"crm_name": "MoySklad", "scope_type": "network", "scope_id": "foreign-network"},
    )

    assert response.status_code == 403
    assert response.get_json()["error"] == "Точка не относится к выбранной сети"
    assert _Database.connection.committed is False


def test_business_member_cannot_submit_a_network_wide_crm_request(monkeypatch):
    cursor = _Cursor()
    cursor.fetchone_results = [{"network_id": "network-1"}, {"allowed": False}]
    _Database.cursor = cursor
    _Database.connection = _Connection(cursor)
    monkeypatch.setattr(crm_integration_requests_api, "require_auth_from_request", lambda: {"user_id": "business-member"})
    monkeypatch.setattr(crm_integration_requests_api, "verify_business_access", lambda *_args: (True, "owner-1"))
    monkeypatch.setattr(crm_integration_requests_api, "DatabaseManager", _Database)

    response = _app().test_client().post(
        "/api/business/business-1/crm-integration-requests",
        json={"crm_name": "MoySklad", "scope_type": "network", "scope_id": "network-1"},
    )

    assert response.status_code == 403
    assert response.get_json()["error"] == "Нет доступа к управлению сетью"
    assert _Database.connection.committed is False


def test_network_owner_or_member_can_manage_network_request_scope():
    cursor = _Cursor()
    cursor.fetchone_results = [{"allowed": True}]

    assert crm_integration_requests_api._can_manage_network(cursor, "network-1", {"user_id": "network-member"}) is True
    assert cursor.queries[-1][1] == ("network-member", "network-1", "network-member")


def test_superadmin_can_manage_network_request_scope_without_membership_query():
    cursor = _Cursor()

    assert crm_integration_requests_api._can_manage_network(cursor, "network-1", {"user_id": "admin", "is_superadmin": True}) is True
    assert cursor.queries == []
