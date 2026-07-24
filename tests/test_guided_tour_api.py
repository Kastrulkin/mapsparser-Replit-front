import sys

from flask import Flask, jsonify


if "src" not in sys.path:
    sys.path.insert(0, "src")

from api import guided_tour_api


class FakeCursor:
    def __init__(self, *, rows=None, all_rows=None):
        self.rows = list(rows or [])
        self.all_rows = list(all_rows or [])
        self.queries = []

    def execute(self, query, params=None):
        self.queries.append((query, params))

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def fetchall(self):
        return list(self.all_rows)


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self.cursor_value

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def build_app():
    app = Flask(__name__)

    @app.route("/api/business/demo", methods=["GET", "POST"])
    def demo_business_route():
        return jsonify({"success": True})

    @app.route("/api/business/<business_id>/details", methods=["GET"])
    def scoped_business_route(business_id):
        return jsonify({"success": True, "business_id": business_id})

    @app.route("/api/services", methods=["GET"])
    def scoped_services_route():
        return jsonify({"success": True})

    app.register_blueprint(guided_tour_api.guided_tour_bp)
    return app


def demo_session(token="demo_token"):
    return {
        "user_id": "demo-user",
        "session_id": f"session-{token}",
        "session_kind": "demo",
        "scope_business_id": "demo-business",
        "is_superadmin": False,
    }


def clear_rate_limit():
    with guided_tour_api._rate_lock:
        guided_tour_api._rate_hits.clear()


def test_public_demo_session_is_hidden_when_disabled(monkeypatch):
    clear_rate_limit()
    monkeypatch.setenv("PUBLIC_DEMO_ENABLED", "false")
    response = build_app().test_client().post("/api/public-demo/session")

    assert response.status_code == 404
    assert response.get_json()["error"] == "public_demo_disabled"


def test_public_demo_session_uses_isolated_token_and_configured_scope(monkeypatch):
    clear_rate_limit()
    monkeypatch.setenv("PUBLIC_DEMO_ENABLED", "true")
    monkeypatch.setenv("PUBLIC_DEMO_USER_ID", "demo-user")
    monkeypatch.setenv("PUBLIC_DEMO_BUSINESS_ID", "demo-business")
    monkeypatch.setenv("DEMO_SESSION_TTL_DAYS", "30")
    cursor = FakeCursor(rows=[{"id": "demo-business", "owner_id": "demo-user", "business_is_active": True, "user_is_active": True}])
    connection = FakeConnection(cursor)
    captured = {}

    monkeypatch.setattr(guided_tour_api, "get_db_connection", lambda: connection)

    def create_session(user_id, **kwargs):
        captured.update({"user_id": user_id, **kwargs})
        return "personal-demo-token"

    monkeypatch.setattr(guided_tour_api, "create_session", create_session)
    response = build_app().test_client().post("/api/public-demo/session", environ_base={"REMOTE_ADDR": "192.0.2.10"})

    assert response.status_code == 200
    assert response.get_json()["token"] == "personal-demo-token"
    assert captured["session_kind"] == "demo"
    assert captured["scope_business_id"] == "demo-business"
    assert captured["expires_days"] == 30
    assert connection.closed is True


def test_public_demo_session_rate_limit_is_twenty_per_hour(monkeypatch):
    clear_rate_limit()
    monkeypatch.setenv("PUBLIC_DEMO_ENABLED", "true")
    monkeypatch.setenv("PUBLIC_DEMO_USER_ID", "demo-user")
    monkeypatch.setenv("PUBLIC_DEMO_BUSINESS_ID", "demo-business")

    def connection_factory():
        return FakeConnection(FakeCursor(rows=[{"business_is_active": True, "user_is_active": True}]))

    monkeypatch.setattr(guided_tour_api, "get_db_connection", connection_factory)
    monkeypatch.setattr(guided_tour_api, "create_session", lambda *args, **kwargs: "token")
    client = build_app().test_client()

    for _ in range(20):
        assert client.post("/api/public-demo/session", environ_base={"REMOTE_ADDR": "192.0.2.20"}).status_code == 200

    response = client.post("/api/public-demo/session", environ_base={"REMOTE_ADDR": "192.0.2.20"})
    assert response.status_code == 429
    assert response.get_json()["error"] == "rate_limited"


def test_demo_policy_blocks_mutations_and_sensitive_reads(monkeypatch):
    monkeypatch.setattr(guided_tour_api, "verify_session", lambda token: demo_session(token))
    client = build_app().test_client()
    headers = {"Authorization": "Bearer demo_token"}

    mutation = client.post("/api/business/demo", headers=headers)
    secrets = client.get("/api/business/demo/external-accounts", headers=headers)
    allowed_read = client.get("/api/business/demo", headers=headers)

    assert mutation.status_code == 403
    assert mutation.get_json()["error"] == "demo_read_only"
    assert secrets.status_code == 403
    assert secrets.get_json()["error"] == "demo_route_not_allowed"
    assert allowed_read.status_code == 200


def test_demo_policy_rejects_business_ids_outside_session_scope(monkeypatch):
    monkeypatch.setattr(guided_tour_api, "verify_session", lambda token: demo_session(token))
    client = build_app().test_client()
    headers = {"Authorization": "Bearer demo_token"}

    path_scope = client.get("/api/business/another-business/details", headers=headers)
    query_scope = client.get("/api/services?business_id=another-business", headers=headers)
    allowed_scope = client.get("/api/business/demo-business/details", headers=headers)

    assert path_scope.status_code == 403
    assert path_scope.get_json()["error"] == "demo_business_scope_violation"
    assert query_scope.status_code == 403
    assert query_scope.get_json()["error"] == "demo_business_scope_violation"
    assert allowed_scope.status_code == 200


def test_standard_session_keeps_existing_mutation_behavior(monkeypatch):
    monkeypatch.setattr(
        guided_tour_api,
        "verify_session",
        lambda token: {**demo_session(token), "session_kind": "standard"},
    )
    response = build_app().test_client().post(
        "/api/business/demo",
        headers={"Authorization": "Bearer standard-token"},
    )

    assert response.status_code == 200


def test_progress_is_scoped_to_each_demo_session(monkeypatch):
    monkeypatch.setattr(guided_tour_api, "verify_session", lambda token: demo_session(token))
    cursors = []

    def connection_factory():
        cursor = FakeCursor()
        cursors.append(cursor)
        return FakeConnection(cursor)

    monkeypatch.setattr(guided_tour_api, "get_db_connection", connection_factory)
    client = build_app().test_client()

    first = client.get(
        "/api/guided-tours/roga-i-kopyta-v1/progress",
        headers={"Authorization": "Bearer visitor-a"},
    )
    second = client.get(
        "/api/guided-tours/roga-i-kopyta-v1/progress",
        headers={"Authorization": "Bearer visitor-b"},
    )

    assert first.get_json()["progress"]["status"] == "not_started"
    assert second.get_json()["progress"]["status"] == "not_started"
    assert cursors[0].queries[0][1][0] == "session-visitor-a"
    assert cursors[1].queries[0][1][0] == "session-visitor-b"


def test_progress_pause_round_trip_preserves_completed_steps(monkeypatch):
    monkeypatch.setattr(guided_tour_api, "verify_session", lambda token: demo_session(token))
    row = {
        "id": "progress-id",
        "tour_key": "roga-i-kopyta-v1",
        "tour_version": 1,
        "status": "paused",
        "chapter_key": "network-pulse",
        "step_key": "network-switcher",
        "completed_steps_json": ["welcome", "operator-nav"],
        "started_at": "2026-07-16T20:00:00+00:00",
        "paused_at": "2026-07-16T20:05:00+00:00",
        "completed_at": None,
        "updated_at": "2026-07-16T20:05:00+00:00",
    }
    connection = FakeConnection(FakeCursor(rows=[row]))
    monkeypatch.setattr(guided_tour_api, "get_db_connection", lambda: connection)

    response = build_app().test_client().put(
        "/api/guided-tours/roga-i-kopyta-v1/progress",
        headers={"Authorization": "Bearer visitor-a"},
        json={
            "tour_version": 1,
            "status": "paused",
            "chapter_key": "network-pulse",
            "step_key": "network-switcher",
            "completed_steps": ["welcome", "operator-nav"],
        },
    )

    assert response.status_code == 200
    assert response.get_json()["progress"]["completed_steps"] == ["welcome", "operator-nav"]
    assert response.get_json()["progress"]["status"] == "paused"
    assert connection.committed is True


def test_progress_rejects_old_or_invalid_tour_versions(monkeypatch):
    monkeypatch.setattr(guided_tour_api, "verify_session", lambda token: demo_session(token))
    client = build_app().test_client()
    headers = {"Authorization": "Bearer visitor-a"}

    old = client.put(
        "/api/guided-tours/roga-i-kopyta-v1/progress",
        headers=headers,
        json={"tour_version": 0, "status": "active"},
    )
    invalid = client.put(
        "/api/guided-tours/roga-i-kopyta-v1/progress",
        headers=headers,
        json={"tour_version": "latest", "status": "active"},
    )

    assert old.status_code == 409
    assert invalid.status_code == 400
    assert invalid.get_json()["error"] == "invalid_tour_version"


def test_events_accept_only_the_documented_funnel(monkeypatch):
    monkeypatch.setattr(guided_tour_api, "verify_session", lambda token: demo_session(token))
    connection = FakeConnection(FakeCursor())
    monkeypatch.setattr(guided_tour_api, "get_db_connection", lambda: connection)
    client = build_app().test_client()
    headers = {"Authorization": "Bearer visitor-a"}

    accepted = client.post(
        "/api/guided-tours/roga-i-kopyta-v1/events",
        headers=headers,
        json={"event_type": "target_missing", "step_key": "card-services"},
    )
    rejected = client.post(
        "/api/guided-tours/roga-i-kopyta-v1/events",
        headers=headers,
        json={"event_type": "arbitrary_event"},
    )

    assert accepted.status_code == 201
    assert rejected.status_code == 400
    assert rejected.get_json()["error"] == "unsupported_event_type"


def test_guided_tour_routes_are_registered_in_main_app():
    import main

    routes = {
        (str(rule), frozenset(rule.methods - {"HEAD", "OPTIONS"}))
        for rule in main.app.url_map.iter_rules()
    }
    expected = {
        ("/api/public-demo/session", frozenset({"POST"})),
        ("/api/guided-tours/<tour_key>/progress", frozenset({"GET"})),
        ("/api/guided-tours/<tour_key>/progress", frozenset({"PUT"})),
        ("/api/guided-tours/<tour_key>/events", frozenset({"POST"})),
        ("/api/admin/guided-tours/summary", frozenset({"GET"})),
    }

    assert expected.issubset(routes)
