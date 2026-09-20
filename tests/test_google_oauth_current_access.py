"""Callback authorization using signed state and synthetic DB/provider boundaries."""

import pytest
from flask import Flask

from api import google_business_api


class OAuthDatabase:
    def __init__(self, actor, business, existing=False, tuple_rows=False):
        self.actor = actor
        self.business = business
        self.existing = existing
        self.tuple_rows = tuple_rows
        self.conn = self
        self.result = None
        self.queries = []
        self.pending = []
        self.persisted = []
        self.rollbacks = 0
        self.closed = False
        self.rowcount = 1
        self.fail_write = False

    def cursor(self):
        return self

    def execute(self, query, params=None):
        sql = " ".join(query.split()).lower()
        self.queries.append((sql, params))
        if "from businesses business" in sql and "join users actor" in sql:
            assert params == ("actor-1", "business-1")
            self.result = None
            if self.actor is not None and self.business is not None:
                row = {
                    "owner_id": self.business["owner_id"],
                    "is_active": self.actor["is_active"],
                    "is_superadmin": self.actor["is_superadmin"],
                }
                self.result = tuple(row.values()) if self.tuple_rows else row
        elif sql.startswith("select id from externalbusinessaccounts"):
            assert params == ("business-1",)
            self.result = {"id": "account-1"} if self.existing else None
        elif sql.startswith(("insert into externalbusinessaccounts", "update externalbusinessaccounts", "update agent_integrations")):
            self.pending.append((sql, params))
            if self.fail_write:
                raise RuntimeError("Synthetic persistence failure")
        else:
            raise AssertionError(f"Unexpected SQL: {sql}")

    def fetchone(self):
        return self.result

    def commit(self):
        self.persisted.extend(self.pending)
        self.pending.clear()

    def rollback(self):
        self.rollbacks += 1
        self.pending.clear()

    def close(self):
        # Production DatabaseManager.close commits before closing too.
        self.commit()
        self.closed = True


@pytest.fixture(params=["google_business", "google_sheets"])
def callback(request, monkeypatch):
    purpose = request.param
    monkeypatch.setenv("GOOGLE_OAUTH_STATE_SECRET", "synthetic-callback-state-only")
    monkeypatch.setenv("FRONTEND_URL", "https://frontend.invalid")
    app = Flask(__name__)
    app.register_blueprint(google_business_api.google_business_bp)
    calls = []
    db = OAuthDatabase(
        {"is_active": True, "is_superadmin": False},
        {"owner_id": "actor-1"},
    )
    on_exchange = []

    class Provider:
        def get_credentials_from_code(self, code):
            assert code == "synthetic-code"
            calls.append("exchange")
            for change in on_exchange:
                change()
            return object()

        def credentials_to_dict(self, credentials):
            return {"synthetic": True}

        def get_account_identity(self, credentials):
            calls.append("identity")
            return {"email": "synthetic@example.invalid"}

        def list_accounts(self):
            calls.append("discovery")
            return []

    monkeypatch.setattr(google_business_api, "DatabaseManager", lambda: db)
    monkeypatch.setattr(google_business_api, "GoogleBusinessAuth", Provider)
    monkeypatch.setattr(google_business_api, "GoogleSheetsAuth", Provider)
    monkeypatch.setattr(google_business_api, "GoogleBusinessAPI", lambda credentials: Provider())
    monkeypatch.setattr(google_business_api, "encrypt_auth_data", lambda payload: "synthetic-encrypted")
    monkeypatch.setattr(google_business_api, "_auth_data_column", lambda cursor: "auth_data_encrypted")
    state = google_business_api._encode_google_oauth_state(
        "actor-1", "business-1", "/dashboard/settings/integrations", purpose,
    )
    route = "/api/google/oauth/callback" if purpose == "google_business" else "/api/google/sheets/oauth/callback"

    def invoke(signed_state=state):
        return app.test_client().get(route, query_string={"code": "synthetic-code", "state": signed_state})

    return db, calls, on_exchange, invoke


@pytest.mark.parametrize("revocation", ["owner", "admin", "inactive_owner", "inactive_admin", "missing_user", "missing_business"])
def test_callback_rechecks_current_access_before_provider_exchange(callback, revocation):
    db, calls, _, invoke = callback
    if revocation in ("owner", "admin"):
        db.business["owner_id"] = "new-owner"
    elif revocation in ("inactive_owner", "inactive_admin"):
        db.actor["is_active"] = False
        if revocation == "inactive_admin":
            db.actor["is_superadmin"] = True
            db.business["owner_id"] = "new-owner"
    elif revocation == "missing_user":
        db.actor = None
    else:
        db.business = None

    response = invoke()

    assert calls == [], "Revoked access must prevent OAuth provider exchange"
    assert db.persisted == []
    assert response.status_code == 302
    assert "google_auth=error" in response.location
    assert db.closed


@pytest.mark.parametrize("revocation", ["owner", "admin", "inactive"])
def test_callback_rechecks_access_after_provider_exchange_before_writes(callback, revocation):
    db, calls, on_exchange, invoke = callback
    if revocation == "admin":
        db.actor["is_superadmin"] = True
        db.business["owner_id"] = "someone-else"
        on_exchange.append(lambda: db.actor.update(is_superadmin=False))
    elif revocation == "owner":
        on_exchange.append(lambda: db.business.update(owner_id="new-owner"))
    else:
        on_exchange.append(lambda: db.actor.update(is_active=False))

    response = invoke()

    assert calls[0] == "exchange"
    assert db.persisted == [], "Revoked access must prevent credential/rebind writes"
    assert response.status_code == 302
    assert "google_auth=error" in response.location
    assert db.closed


@pytest.mark.parametrize("admin", [False, True])
@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("tuple_rows", [False, True])
def test_callback_preserves_current_owner_and_admin_reconnect(callback, admin, existing, tuple_rows):
    db, calls, _, invoke = callback
    db.actor["is_superadmin"] = admin
    if admin:
        db.business["owner_id"] = "someone-else"
    db.existing = existing
    db.tuple_rows = tuple_rows

    response = invoke()

    assert response.status_code == 302
    assert "google_auth=success" in response.location
    assert calls[0] == "exchange"
    assert db.persisted
    assert db.closed
    auth_queries = [sql for sql, _ in db.queries if "join users actor" in sql]
    assert len(auth_queries) == 2
    assert "for share" not in auth_queries[0]
    assert "for share of business, actor" in auth_queries[1]


def test_callback_does_not_hold_authorization_transaction_during_exchange(callback):
    db, _, on_exchange, invoke = callback

    def verify_admission_finished():
        assert db.rollbacks == 1
        assert len(db.queries) == 1
        assert "for share" not in db.queries[0][0]

    on_exchange.append(verify_admission_finished)

    assert "google_auth=success" in invoke().location


@pytest.mark.parametrize("failure", ["exchange", "persistence"])
def test_callback_rolls_back_and_closes_on_failure(callback, failure):
    db, _, on_exchange, invoke = callback

    def fail_exchange():
        raise RuntimeError("Synthetic provider failure")

    if failure == "exchange":
        on_exchange.append(fail_exchange)
    else:
        db.fail_write = True

    response = invoke()

    assert response.status_code == 302
    assert "google_auth=error" in response.location
    assert db.persisted == []
    assert db.pending == []
    assert db.rollbacks == 2
    assert db.closed


def test_callback_rejects_unsigned_state_without_any_effects(callback):
    db, calls, _, invoke = callback

    response = invoke("actor-1_business-1")

    assert response.status_code == 302
    assert "google_auth=error" in response.location
    assert calls == []
    assert db.queries == []
    assert db.persisted == []
