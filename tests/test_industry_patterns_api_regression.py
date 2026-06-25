from flask import Flask

import api.admin_industry_patterns_api as industry_patterns_api


class FakeCursor:
    def __init__(self):
        self.calls = 0

    def execute(self, _sql, _params=None):
        self.calls += 1

    def fetchall(self):
        if self.calls == 1:
            return [{"status": "pending_review", "count": 2}]
        if self.calls == 2:
            return [{"status": "active", "count": 1}]
        return []

    def fetchone(self):
        return None


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()
        self.closed = False
        self.committed = False

    def cursor(self):
        return self.cursor_instance

    def close(self):
        self.closed = True

    def commit(self):
        self.committed = True


class FakeMatrixCursor:
    def __init__(self):
        self.queries = []
        self.params = []
        self.last_query = ""

    def execute(self, sql, params=None):
        self.last_query = str(sql).lower()
        self.queries.append(str(sql))
        self.params.append(params)

    def fetchall(self):
        if "from aiprompts" in self.last_query:
            return [
                {
                    "prompt_type": "content_matrix.culture.announcement",
                    "prompt_text": "Override culture announcement",
                    "description": "Content matrix",
                    "updated_at": "2026-06-25",
                    "updated_by": "admin",
                }
            ]
        if "from industry_pattern_versions" in self.last_query:
            return [
                {
                    "industry_key": "culture",
                    "pattern_type": "news",
                    "pattern_text": "Сохранять название, дату и время события.",
                    "version": "2026.06.1",
                    "activated_at": "2026-06-25",
                }
            ]
        return []

    def fetchone(self):
        return None


class FakeMatrixConnection:
    def __init__(self):
        self.cursor_instance = FakeMatrixCursor()
        self.closed = False
        self.committed = False

    def cursor(self):
        return self.cursor_instance

    def close(self):
        self.closed = True

    def commit(self):
        self.committed = True


def build_client(monkeypatch, user_data=None):
    app = Flask(__name__)
    app.register_blueprint(industry_patterns_api.admin_industry_patterns_bp)

    def fake_verify_session(_token):
        return user_data

    monkeypatch.setattr(industry_patterns_api, "verify_session", fake_verify_session)
    return app.test_client()


def test_admin_patterns_summary_rejects_missing_auth(monkeypatch):
    client = build_client(monkeypatch, {"user_id": "admin", "is_superadmin": True})

    response = client.get("/api/admin/industry-patterns/summary")

    assert response.status_code == 403
    assert response.get_json()["success"] is False


def test_admin_patterns_summary_rejects_regular_user(monkeypatch):
    client = build_client(monkeypatch, {"user_id": "user", "is_superadmin": False})

    response = client.get("/api/admin/industry-patterns/summary", headers={"Authorization": "Bearer regular"})

    assert response.status_code == 403
    assert response.get_json()["error"] == "Forbidden"


def test_admin_patterns_summary_allows_superadmin(monkeypatch):
    conn = FakeConnection()
    client = build_client(monkeypatch, {"user_id": "admin", "is_superadmin": True})
    monkeypatch.setattr(industry_patterns_api, "get_db_connection", lambda: conn)
    monkeypatch.setattr(industry_patterns_api, "ensure_industry_pattern_tables", lambda _conn: None)
    monkeypatch.setattr(
        industry_patterns_api,
        "build_monthly_industry_pattern_impact_report",
        lambda _conn, days, limit: {"totals": {"needs_review": 0}, "period_days": days, "limit": limit},
    )
    monkeypatch.setattr(
        industry_patterns_api,
        "summarize_industry_pattern_admin_safety",
        lambda _conn: {"superadmin_only": True, "rollback_requires_preview": True},
    )

    response = client.get("/api/admin/industry-patterns/summary", headers={"Authorization": "Bearer admin"})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["proposal_counts"]["pending_review"] == 2
    assert payload["version_counts"]["active"] == 1
    assert payload["safety"]["superadmin_only"] is True


def test_disable_requires_explicit_confirmation(monkeypatch):
    client = build_client(monkeypatch, {"user_id": "admin", "is_superadmin": True})
    monkeypatch.setattr(
        industry_patterns_api,
        "get_db_connection",
        lambda: (_ for _ in ()).throw(AssertionError("DB should not be opened before confirm")),
    )

    response = client.post(
        "/api/admin/industry-patterns/versions/v1/disable",
        headers={"Authorization": "Bearer admin"},
        json={"reason": "test"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Disable confirmation required"


def test_recalibrate_requires_explicit_confirmation(monkeypatch):
    client = build_client(monkeypatch, {"user_id": "admin", "is_superadmin": True})
    monkeypatch.setattr(
        industry_patterns_api,
        "get_db_connection",
        lambda: (_ for _ in ()).throw(AssertionError("DB should not be opened before confirm")),
    )

    response = client.post(
        "/api/admin/industry-patterns/recalibrate",
        headers={"Authorization": "Bearer admin"},
        json={},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Recalibration confirmation required"


def test_rollback_requires_preview_confirmation_token(monkeypatch):
    conn = FakeConnection()
    client = build_client(monkeypatch, {"user_id": "admin", "is_superadmin": True})
    monkeypatch.setattr(industry_patterns_api, "get_db_connection", lambda: conn)
    monkeypatch.setattr(
        industry_patterns_api,
        "get_industry_pattern_rollback_preview",
        lambda _conn, current_version_id, target_version_id, days: {
            "can_confirm": True,
            "confirmation_token": f"rollback:{current_version_id}:{target_version_id}",
        },
    )
    monkeypatch.setattr(
        industry_patterns_api,
        "rollback_industry_pattern_version",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("Rollback should not run without token")),
    )

    response = client.post(
        "/api/admin/industry-patterns/versions/current/rollback",
        headers={"Authorization": "Bearer admin"},
        json={"target_version_id": "target", "reason": "test"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Rollback preview confirmation required"


def test_rollback_with_preview_token_runs_and_logs(monkeypatch):
    conn = FakeConnection()
    events = []
    client = build_client(monkeypatch, {"user_id": "admin", "is_superadmin": True})
    monkeypatch.setattr(industry_patterns_api, "get_db_connection", lambda: conn)
    monkeypatch.setattr(
        industry_patterns_api,
        "get_industry_pattern_rollback_preview",
        lambda _conn, current_version_id, target_version_id, days: {
            "can_confirm": True,
            "confirmation_token": f"rollback:{current_version_id}:{target_version_id}",
        },
    )
    monkeypatch.setattr(
        industry_patterns_api,
        "rollback_industry_pattern_version",
        lambda _conn, **_kwargs: {
            "status": "active",
            "reason": "test",
            "disabled_versions": ["current"],
        },
    )

    def fake_record_event(_conn, **kwargs):
        events.append(kwargs)
        return {"recorded": 1}

    monkeypatch.setattr(industry_patterns_api, "record_industry_pattern_admin_event", fake_record_event)

    response = client.post(
        "/api/admin/industry-patterns/versions/current/rollback",
        headers={"Authorization": "Bearer admin"},
        json={
            "target_version_id": "target",
            "reason": "test",
            "confirmation_token": "rollback:current:target",
        },
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["result"]["status"] == "active"
    assert events[0]["action"] == "rollback_confirmed"
    assert events[0]["target_id"] == "current"


def test_publication_matrix_lists_base_rules_and_learned_patterns(monkeypatch):
    conn = FakeMatrixConnection()
    client = build_client(monkeypatch, {"user_id": "admin", "is_superadmin": True})
    monkeypatch.setattr(industry_patterns_api, "get_db_connection", lambda: conn)
    monkeypatch.setattr(industry_patterns_api, "ensure_industry_pattern_tables", lambda _conn: None)

    response = client.get(
        "/api/admin/industry-patterns/publication-matrix?industry_key=culture&objective_key=announcement",
        headers={"Authorization": "Bearer admin"},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["rows"][0]["prompt_type"] == "content_matrix.culture.announcement"
    assert payload["rows"][0]["effective_prompt"] == "Override culture announcement"
    assert payload["rows"][0]["learned_techniques"][0]["pattern_text"] == "Сохранять название, дату и время события."


def test_publication_matrix_update_writes_aiprompt_override(monkeypatch):
    conn = FakeMatrixConnection()
    events = []
    client = build_client(monkeypatch, {"user_id": "admin", "is_superadmin": True})
    monkeypatch.setattr(industry_patterns_api, "get_db_connection", lambda: conn)
    monkeypatch.setattr(industry_patterns_api, "record_industry_pattern_admin_event", lambda _conn, **kwargs: events.append(kwargs))

    response = client.put(
        "/api/admin/industry-patterns/publication-matrix",
        headers={"Authorization": "Bearer admin"},
        json={
            "industry_key": "culture",
            "objective_key": "announcement",
            "prompt_text": "New rules",
        },
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["prompt_type"] == "content_matrix.culture.announcement"
    assert conn.committed is True
    assert events[0]["action"] == "content_matrix_updated"
