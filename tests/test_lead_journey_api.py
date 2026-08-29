from flask import Flask

from api import lead_journey_api


class _Cursor:
    def execute(self, _query, _params=None):
        return None

    def fetchone(self):
        return {"automation_allowed": False}


class _Connection:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0
        self.cursor_value = _Cursor()

    def cursor(self, **_kwargs):
        return self.cursor_value

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class _Database:
    latest = None

    def __init__(self):
        self.conn = _Connection()
        self.closed = False
        _Database.latest = self

    def close(self):
        self.closed = True


def _app():
    app = Flask(__name__)
    app.register_blueprint(lead_journey_api.lead_journey_bp)
    return app


def _enable_and_authorize(monkeypatch):
    monkeypatch.setattr(lead_journey_api, "journey_enabled", lambda _flag="LEAD_JOURNEY_ENABLED": True)
    monkeypatch.setattr(lead_journey_api, "require_auth_from_request", lambda: {"user_id": "user-1"})
    monkeypatch.setattr(lead_journey_api, "verify_business_access", lambda *_args: (True, "user-1"))
    monkeypatch.setattr(lead_journey_api, "DatabaseManager", _Database)


def test_public_event_rejects_non_allowlisted_event_before_database(monkeypatch):
    monkeypatch.setattr(lead_journey_api, "journey_enabled", lambda _flag="LEAD_JOURNEY_ENABLED": True)
    monkeypatch.setattr(lead_journey_api, "DatabaseManager", lambda: (_ for _ in ()).throw(AssertionError("database must not open")))

    response = _app().test_client().post(
        "/api/journeys/public/token/events",
        json={"event_name": "contact_exported", "surface": "web"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Событие не поддерживается"


def test_public_event_strips_sensitive_properties_before_recording(monkeypatch):
    monkeypatch.setattr(lead_journey_api, "journey_enabled", lambda _flag="LEAD_JOURNEY_ENABLED": True)
    monkeypatch.setattr(lead_journey_api, "DatabaseManager", _Database)
    monkeypatch.setattr(
        lead_journey_api,
        "load_public_journey",
        lambda *_args, **_kwargs: {
            "id": "journey-1",
            "prospect_lead_id": "lead-1",
            "claimed_business_id": None,
            "claimed_user_id": None,
        },
    )
    captured = {}
    monkeypatch.setattr(
        lead_journey_api,
        "record_product_event",
        lambda _cursor, **kwargs: captured.update(kwargs) or "event-1",
    )

    response = _app().test_client().post(
        "/api/journeys/public/token/events",
        json={
            "event_name": "lead_link_opened",
            "surface": "web",
            "properties": {
                "cta_variant": "primary",
                "password": "do-not-store",
                "token": "private-token",
                "email": "person@example.com",
            },
        },
    )

    assert response.status_code == 201
    assert captured["properties"] == {"cta_variant": "primary"}


def test_create_journey_requires_selected_flow_before_database(monkeypatch):
    monkeypatch.setattr(lead_journey_api, "journey_enabled", lambda _flag="LEAD_JOURNEY_ENABLED": True)
    monkeypatch.setattr(lead_journey_api, "require_auth_from_request", lambda: {"user_id": "admin-1", "is_superadmin": True})
    monkeypatch.setattr(lead_journey_api, "DatabaseManager", lambda: (_ for _ in ()).throw(AssertionError("database must not open")))

    response = _app().test_client().post("/api/journeys", json={"source": "test"})

    assert response.status_code == 400
    assert response.get_json()["code"] == "selected_flow_required"


def test_claim_respects_vertical_kill_switch(monkeypatch):
    _enable_and_authorize(monkeypatch)
    monkeypatch.setattr(lead_journey_api, "load_public_journey", lambda *_args, **_kwargs: {"selected_flow": "influencer"})
    monkeypatch.setattr(lead_journey_api, "journey_flow_enabled", lambda _flow: False)
    monkeypatch.setattr(lead_journey_api, "claim_journey", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("claim must not run")))

    response = _app().test_client().post(
        "/api/journeys/claim",
        json={"token": "token", "business_id": "business-1"},
    )

    assert response.status_code == 404
    assert response.get_json()["code"] == "flow_disabled"
    assert _Database.latest.closed is True


def test_action_list_commits_map_reconciliation(monkeypatch):
    _enable_and_authorize(monkeypatch)
    monkeypatch.setattr(lead_journey_api, "list_actions", lambda *_args, **_kwargs: [])

    response = _app().test_client().get("/api/journey-actions?business_id=business-1")

    assert response.status_code == 200
    assert _Database.latest.conn.commits == 1


def test_action_command_forwards_version_idempotency_and_records_funnel_once(monkeypatch):
    _enable_and_authorize(monkeypatch)
    monkeypatch.setattr(lead_journey_api, "journey_flow_enabled", lambda _flow: True)
    action = {
        "id": "action-1", "journey_id": "journey-1", "lead_id": "lead-1",
        "flow_type": "partnership", "entity_type": "lead_workstream", "entity_id": "workstream-1",
    }
    monkeypatch.setattr(lead_journey_api, "load_action", lambda *_args, **_kwargs: action)
    captured = {}

    def execute(_cursor, **kwargs):
        captured.update(kwargs)
        return {"action": {**action, "version": 8}, "next_action": None, "idempotent_replay": False}

    events = []
    monkeypatch.setattr(lead_journey_api, "execute_command", execute)
    monkeypatch.setattr(lead_journey_api, "record_product_event", lambda _cursor, **kwargs: events.append(kwargs) or "event-1")

    response = _app().test_client().post(
        "/api/journey-actions/action-1/commands",
        headers={"Idempotency-Key": "request-1"},
        json={
            "business_id": "business-1", "command": "record_reply", "version": 7,
            "surface": "telegram_mini_app", "payload": {"outcome": "interested"},
        },
    )

    assert response.status_code == 200
    assert captured["expected_version"] == 7
    assert captured["idempotency_key"] == "request-1"
    assert captured["surface"] == "telegram_mini_app"
    assert events[0]["event_name"] == "reply_recorded"
    assert events[0]["journey_id"] == "journey-1"
    assert _Database.latest.conn.commits == 1


def test_influencer_message_command_is_blocked_without_payment(monkeypatch):
    _enable_and_authorize(monkeypatch)
    monkeypatch.setattr(lead_journey_api, "journey_flow_enabled", lambda _flow: True)
    action = {
        "id": "action-1", "flow_type": "influencer", "action_type": "send_message",
        "entity_type": "creator_campaign", "entity_id": "campaign-1",
    }
    monkeypatch.setattr(lead_journey_api, "load_action", lambda *_args, **_kwargs: action)
    monkeypatch.setattr(lead_journey_api, "execute_command", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("paid command must not run")))

    response = _app().test_client().post(
        "/api/journey-actions/action-1/commands",
        json={"business_id": "business-1", "command": "copy", "version": 1, "surface": "web"},
    )

    assert response.status_code == 402
    assert response.get_json()["code"] == "payment_required"


def test_idempotent_action_replay_does_not_duplicate_product_event(monkeypatch):
    _enable_and_authorize(monkeypatch)
    monkeypatch.setattr(lead_journey_api, "journey_flow_enabled", lambda _flow: True)
    action = {"id": "action-1", "flow_type": "influencer", "entity_type": "creator_collaboration"}
    monkeypatch.setattr(lead_journey_api, "load_action", lambda *_args, **_kwargs: action)
    monkeypatch.setattr(
        lead_journey_api,
        "execute_command",
        lambda *_args, **_kwargs: {"action": action, "next_action": None, "idempotent_replay": True},
    )
    events = []
    monkeypatch.setattr(lead_journey_api, "record_product_event", lambda _cursor, **kwargs: events.append(kwargs))

    response = _app().test_client().post(
        "/api/journey-actions/action-1/commands",
        headers={"Idempotency-Key": "same-request"},
        json={"business_id": "business-1", "command": "mark_sent", "version": 2, "surface": "web"},
    )

    assert response.status_code == 200
    assert response.get_json()["idempotent_replay"] is True
    assert events == []
