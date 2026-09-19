from dataclasses import dataclass, field

import pytest
from flask import Flask

from api import operator_api
from core import auth_helpers


@dataclass
class EffectCounters:
    generator: int = 0
    events: int = 0
    commits: int = 0
    rollbacks: int = 0


@dataclass
class RoleCursor:
    actor_id: str
    last_query: str = ""
    last_operation: str = ""
    read_queries: int = 0
    write_role_queries: int = 0
    effects: EffectCounters = field(default_factory=EffectCounters)

    def execute(self, query, params=None):
        self.last_query = " ".join(str(query).lower().split())
        bound_params = tuple(params or ())
        if "from businesses b" in self.last_query:
            assert bound_params == (self.actor_id, self.actor_id, self.actor_id, "business-1")
            self.read_queries += 1
            self.last_operation = "business_access"
            return
        if "select bm.role" in self.last_query:
            assert bound_params == (
                "business-1",
                self.actor_id,
                "business-1",
                self.actor_id,
                "business-1",
                self.actor_id,
            )
            self.write_role_queries += 1
            self.last_operation = "write_roles"
            return
        raise AssertionError(f"unexpected SQL in route admission test: {self.last_query}")

    def fetchone(self):
        assert self.last_operation == "business_access"
        if self.actor_id == "missing-business":
            return None
        return {
            "owner_id": "owner-1",
            "has_business_membership": self.actor_id in {"viewer-1", "member-1", "mixed-role-1"},
            "has_network_membership": self.actor_id in {"network-viewer-1", "network-member-1", "mixed-role-1"},
            "owns_network": self.actor_id == "network-owner-1",
        }

    def fetchall(self):
        assert self.last_operation == "write_roles"
        roles = {
            "viewer-1": ["viewer"],
            "member-1": ["member"],
            "network-viewer-1": ["viewer"],
            "network-member-1": ["member"],
            "mixed-role-1": ["viewer", "member"],
            "network-owner-1": ["network_owner"],
        }
        return [{"role": role} for role in roles.get(self.actor_id, [])]


class RoleConnection:
    def __init__(self, cursor):
        self.cursor_instance = cursor
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.cursor_instance.effects.commits += 1

    def rollback(self):
        self.cursor_instance.effects.rollbacks += 1


class RoleDatabaseManager:
    def __init__(self, cursor):
        self.conn = RoleConnection(cursor)
        self.closed = False

    def close(self):
        self.closed = True


def _client(monkeypatch, actor):
    cursor = RoleCursor(actor_id=str(actor["user_id"]))
    database = RoleDatabaseManager(cursor)
    app = Flask(__name__)
    app.register_blueprint(operator_api.operator_bp)

    monkeypatch.setattr(operator_api, "DatabaseManager", lambda: database)
    monkeypatch.setattr(operator_api, "require_auth_from_request", lambda: actor)
    monkeypatch.setattr(
        operator_api,
        "generate_news_draft_from_operator",
        lambda *_args, **_kwargs: _generated_news(cursor.effects),
    )
    monkeypatch.setattr(operator_api, "record_operator_event", lambda *_args, **_kwargs: _record_event(cursor.effects))

    return app.test_client(), cursor, database


def _generated_news(effects):
    effects.generator += 1
    return {
        "status": "completed",
        "news_draft": {"id": "news-1"},
        "external_writes_performed": False,
    }


def _record_event(effects):
    effects.events += 1


def _actor(user_id, superadmin=False):
    return {"user_id": user_id, "id": user_id, "is_superadmin": superadmin}


@pytest.mark.parametrize(
    ("actor", "expected_status", "expected_write_queries", "expected_effects", "expected_route_commits"),
    [
        (_actor("viewer-1"), 403, 1, (0, 0), None),
        (_actor("network-viewer-1"), 403, 1, (0, 0), None),
        (_actor("member-1"), 200, 1, (1, 1), 1),
        (_actor("network-member-1"), 200, 1, (1, 1), 1),
        (_actor("mixed-role-1"), 200, 1, (1, 1), 1),
        (_actor("owner-1"), 200, 0, (1, 1), 1),
        (_actor("network-owner-1"), 200, 1, (1, 1), 1),
        (_actor("superadmin-1", superadmin=True), 200, 0, (1, 1), 1),
        (_actor("stranger-1"), 403, 0, (0, 0), None),
        (_actor("missing-business"), 404, 0, (0, 0), None),
        ({**_actor("owner-1"), "session_kind": "demo", "scope_business_id": "business-2"}, 404, 0, (0, 0), None),
    ],
)
def test_operator_news_generate_requires_canonical_write_admission_before_effects(
    monkeypatch,
    actor,
    expected_status,
    expected_write_queries,
    expected_effects,
    expected_route_commits,
):
    client, cursor, database = _client(monkeypatch, actor)

    response = client.post(
        "/api/operator/news/generate",
        json={"business_id": "business-1", "message": "Новая услуга доступна"},
    )

    assert operator_api.verify_business_access is auth_helpers.verify_business_access
    assert operator_api.verify_business_write_access is auth_helpers.verify_business_write_access
    assert response.status_code == expected_status
    assert cursor.read_queries == (0 if actor.get("session_kind") == "demo" else 1)
    assert cursor.write_role_queries == expected_write_queries
    assert (cursor.effects.generator, cursor.effects.events) == expected_effects
    if expected_route_commits is not None:
        assert cursor.effects.commits == expected_route_commits
    assert cursor.effects.rollbacks == 0
    assert database.closed is True


@pytest.mark.parametrize(
    ("actor", "payload", "expected_status"),
    [
        (None, {"business_id": "business-1", "message": "Новая услуга доступна"}, 401),
        (_actor("owner-1"), {"message": "Новая услуга доступна"}, 400),
        (_actor("owner-1"), {"business_id": "business-1"}, 400),
    ],
)
def test_operator_news_generate_rejects_unauthenticated_or_incomplete_payload_before_database(
    monkeypatch,
    actor,
    payload,
    expected_status,
):
    app = Flask(__name__)
    app.register_blueprint(operator_api.operator_bp)
    created = []

    def database_manager():
        created.append(True)
        raise AssertionError("invalid requests must not open the database")

    monkeypatch.setattr(operator_api, "DatabaseManager", database_manager)
    monkeypatch.setattr(operator_api, "require_auth_from_request", lambda: actor)

    response = app.test_client().post("/api/operator/news/generate", json=payload)

    assert response.status_code == expected_status
    assert created == []
