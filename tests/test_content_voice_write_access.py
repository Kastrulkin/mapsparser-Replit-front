import json
from dataclasses import dataclass, field

import pytest
from flask import Flask

from api import content_voice_api
from core import auth_helpers
from services import content_voice_service


@dataclass
class VoiceState:
    actor_id: str
    superadmin: bool = False
    session_kind: str = "standard"
    scope_business_id: str = ""
    downgrade_after_initial_read: bool = False
    business_state: str = "active"
    business_access_queries: int = 0
    write_role_queries: int = 0
    advisory_locks: int = 0
    profile_upserts: int = 0
    explicit_write_commits: int = 0
    rollbacks: int = 0
    example_reads: list[str] = field(default_factory=list)
    profiles: dict = field(default_factory=lambda: {
        "business-1": {
            "summary": "Existing voice",
            "preferences_json": {"content_rules": ["Сохранять фактический тон"]},
            "forbidden_phrases_json": [],
            "typical_ctas_json": [],
            "reference_example_ids_json": [],
            "status": "confirmed",
            "version": 3,
        },
    })


class StrictVoiceCursor:
    def __init__(self, state):
        self.state = state
        self.last_operation = ""

    def execute(self, query, params=None):
        normalized = " ".join(str(query).lower().split())
        bound_params = tuple(params or ())
        actor_id = self.state.actor_id
        if "from businesses b" in normalized:
            assert bound_params == (actor_id, actor_id, actor_id, "business-1")
            self.state.business_access_queries += 1
            self.last_operation = "business_access"
            return
        if "select bm.role" in normalized:
            assert bound_params == (
                "business-1",
                actor_id,
                "business-1",
                actor_id,
                "business-1",
                actor_id,
            )
            self.state.write_role_queries += 1
            self.last_operation = "write_roles"
            return
        if "from userexamples" in normalized and "example_type = 'news'" in normalized:
            assert "where user_id = %s and example_type = 'news' and (business_id = %s or business_id is null)" in normalized
            assert bound_params == (actor_id, "business-1", "business-1", content_voice_service.CONTENT_EXAMPLE_LIMIT)
            self.state.example_reads.append(actor_id)
            self.last_operation = "examples"
            return
        if normalized == "select * from content_voice_profiles where business_id = %s":
            assert bound_params == ("business-1",)
            self.last_operation = "profile"
            return
        if normalized == "select to_regclass('public.ailearningevents')":
            assert bound_params == ()
            self.last_operation = "learning_table"
            return
        if normalized == "select pg_advisory_xact_lock(hashtextextended(%s,0))":
            assert bound_params == ("editorial-profile:business-1",)
            self.state.advisory_locks += 1
            self.last_operation = "advisory"
            return
        if normalized == "select preferences_json from content_voice_profiles where business_id=%s":
            assert bound_params == ("business-1",)
            self.last_operation = "preferences"
            return
        if "insert into content_voice_profiles" in normalized:
            assert bound_params[0] == "business-1"
            assert bound_params[7] == actor_id
            assert bound_params[8] == actor_id
            self.state.profile_upserts += 1
            previous = self.state.profiles.get("business-1", {})
            self.state.profiles["business-1"] = {
                "summary": bound_params[1],
                "preferences_json": json.loads(bound_params[2]),
                "forbidden_phrases_json": json.loads(bound_params[3]),
                "typical_ctas_json": json.loads(bound_params[4]),
                "reference_example_ids_json": json.loads(bound_params[5]),
                "status": bound_params[6],
                "version": int(previous.get("version") or 0) + 1,
            }
            self.last_operation = "upsert"
            return
        raise AssertionError(f"unexpected SQL in content voice admission test: {normalized}")

    def fetchone(self):
        if self.last_operation == "business_access":
            if self.state.business_state != "active":
                return None
            actor_id = self.state.actor_id
            return {
                "owner_id": None if actor_id == "manager-1" else "owner-1",
                "has_business_membership": actor_id in {"viewer-1", "member-1", "manager-1", "mixed-role-1", "mixed-role-2", "downgraded-member-1"},
                "has_network_membership": actor_id in {"network-viewer-1", "network-member-1", "mixed-role-1", "mixed-role-2"},
                "owns_network": actor_id == "network-owner-1",
            }
        if self.last_operation in {"profile", "preferences"}:
            return dict(self.state.profiles.get("business-1", {}))
        if self.last_operation == "learning_table":
            return {"to_regclass": None}
        raise AssertionError(f"unexpected fetchone after {self.last_operation}")

    def fetchall(self):
        if self.last_operation == "examples":
            return []
        if self.last_operation == "write_roles":
            roles = {
                "viewer-1": ["viewer"],
                "member-1": ["member"],
                "manager-1": ["manager"],
                "network-viewer-1": ["viewer"],
                "network-member-1": ["member"],
                "mixed-role-1": ["viewer", "member"],
                "mixed-role-2": ["member", "viewer"],
                "network-owner-1": ["network_owner"],
                "downgraded-member-1": (
                    ["viewer"]
                    if self.state.downgrade_after_initial_read and self.state.business_access_queries >= 2
                    else ["member"]
                ),
            }
            return [{"role": role} for role in roles.get(self.state.actor_id, [])]
        raise AssertionError(f"unexpected fetchall after {self.last_operation}")


class StrictVoiceConnection:
    def __init__(self, state):
        self.cursor_instance = StrictVoiceCursor(state)

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        # This tracks the route's explicit write commit only. The real
        # DatabaseManager.close() may commit cleanup when closing a connection.
        self.cursor_instance.state.explicit_write_commits += 1

    def rollback(self):
        self.cursor_instance.state.rollbacks += 1


class StrictVoiceDatabaseManager:
    def __init__(self, state):
        self.conn = StrictVoiceConnection(state)
        self.closed = False

    def close(self):
        self.closed = True


def _client(monkeypatch, state):
    app = Flask(__name__)
    app.register_blueprint(content_voice_api.content_voice_bp)
    monkeypatch.setattr(content_voice_api, "verify_session", lambda _token: {
        "user_id": state.actor_id,
        "is_superadmin": state.superadmin,
        "session_kind": state.session_kind,
        "scope_business_id": state.scope_business_id,
    })
    monkeypatch.setattr(content_voice_service, "DatabaseManager", lambda: StrictVoiceDatabaseManager(state))
    return app.test_client()


@pytest.mark.parametrize(
    ("actor_id", "superadmin", "session_kind", "scope_business_id", "expected_write_queries"),
    [
        ("owner-1", False, "standard", "", 0),
        ("member-1", False, "standard", "", 1),
        ("manager-1", False, "standard", "", 1),
        ("network-member-1", False, "standard", "", 1),
        ("network-owner-1", False, "standard", "", 1),
        ("mixed-role-1", False, "standard", "", 1),
        ("mixed-role-2", False, "standard", "", 1),
        ("superadmin-1", True, "standard", "", 0),
        ("member-1", False, "demo", "business-1", 1),
    ],
)
def test_content_voice_patch_allows_canonical_writers_and_scopes_profile_upsert(
    monkeypatch,
    actor_id,
    superadmin,
    session_kind,
    scope_business_id,
    expected_write_queries,
):
    state = VoiceState(
        actor_id=actor_id,
        superadmin=superadmin,
        session_kind=session_kind,
        scope_business_id=scope_business_id,
    )
    client = _client(monkeypatch, state)

    response = client.patch(
        "/api/content-voice",
        headers={"Authorization": "Bearer session-token"},
        json={
            "business_id": "business-1",
            "summary": "Scoped voice update",
            "preferences": {"content_rules": ["Attempted overwrite"], "tone": "concise"},
            "confirm": True,
        },
    )

    assert content_voice_service.verify_business_access is auth_helpers.verify_business_access
    assert response.status_code == 200
    assert response.get_json()["profile"]["business_id"] == "business-1"
    assert response.get_json()["profile"]["version"] == 4
    assert state.example_reads == [actor_id, actor_id]
    assert state.business_access_queries == 3
    assert state.write_role_queries == expected_write_queries
    assert state.advisory_locks == 1
    assert state.profile_upserts == 1
    assert state.explicit_write_commits == 1
    assert state.profiles["business-1"]["summary"] == "Scoped voice update"
    assert state.profiles["business-1"]["preferences_json"]["content_rules"] == ["Сохранять фактический тон"]


@pytest.mark.parametrize(
    "state",
    [
        VoiceState(actor_id="viewer-1"),
        VoiceState(actor_id="network-viewer-1"),
        VoiceState(actor_id="viewer-1", session_kind="demo", scope_business_id="business-1"),
    ],
)
def test_content_voice_patch_denies_viewers_before_write_connection_effects(monkeypatch, state):
    client = _client(monkeypatch, state)

    response = client.patch(
        "/api/content-voice",
        headers={"Authorization": "Bearer session-token"},
        json={"business_id": "business-1", "summary": "Viewer must not save"},
    )

    assert (response.status_code, state.profile_upserts, state.explicit_write_commits) == (403, 0, 0)
    assert state.example_reads == [state.actor_id]
    assert state.business_access_queries == 2
    assert state.write_role_queries == 1
    assert state.advisory_locks == 0
    assert state.profile_upserts == 0
    assert state.explicit_write_commits == 0


@pytest.mark.parametrize(
    ("state", "expected_access_queries"),
    [
        (VoiceState(actor_id="stranger-1"), 1),
        (VoiceState(actor_id="owner-1", session_kind="demo", scope_business_id="business-2"), 0),
    ],
)
def test_content_voice_patch_denies_foreign_or_demo_scope_before_profile_write(monkeypatch, state, expected_access_queries):
    client = _client(monkeypatch, state)

    response = client.patch(
        "/api/content-voice",
        headers={"Authorization": "Bearer session-token"},
        json={"business_id": "business-1", "summary": "Foreign target"},
    )

    assert (response.status_code, state.profile_upserts, state.explicit_write_commits) == (403, 0, 0)
    assert state.business_access_queries == expected_access_queries
    assert state.write_role_queries == 0
    assert state.advisory_locks == 0
    assert state.profile_upserts == 0
    assert state.explicit_write_commits == 0


@pytest.mark.parametrize("business_state", ["missing", "inactive"])
def test_content_voice_patch_denies_missing_or_inactive_business_before_profile_write(monkeypatch, business_state):
    state = VoiceState(actor_id="owner-1", business_state=business_state)
    client = _client(monkeypatch, state)

    response = client.patch(
        "/api/content-voice",
        headers={"Authorization": "Bearer session-token"},
        json={"business_id": "business-1", "summary": "Unavailable target"},
    )

    assert (response.status_code, state.profile_upserts, state.explicit_write_commits) == (403, 0, 0)
    assert state.business_access_queries == 1
    assert state.write_role_queries == 0
    assert state.advisory_locks == 0
    assert state.profile_upserts == 0
    assert state.explicit_write_commits == 0


def test_content_voice_patch_rechecks_write_membership_after_initial_profile_read(monkeypatch):
    state = VoiceState(actor_id="downgraded-member-1", downgrade_after_initial_read=True)
    client = _client(monkeypatch, state)

    response = client.patch(
        "/api/content-voice",
        headers={"Authorization": "Bearer session-token"},
        json={"business_id": "business-1", "summary": "Downgraded writer"},
    )

    assert (response.status_code, state.profile_upserts, state.explicit_write_commits) == (403, 0, 0)
    assert state.business_access_queries == 2
    assert state.write_role_queries == 1
    assert state.advisory_locks == 0
    assert state.profile_upserts == 0
    assert state.explicit_write_commits == 0


@pytest.mark.parametrize(
    "state",
    [
        VoiceState(actor_id="viewer-1"),
        VoiceState(actor_id="viewer-1", session_kind="demo", scope_business_id="business-1"),
    ],
)
def test_content_voice_get_preserves_viewer_read_access_and_personal_example_scope(monkeypatch, state):
    client = _client(monkeypatch, state)

    response = client.get(
        "/api/content-voice?business_id=business-1",
        headers={"Authorization": "Bearer session-token"},
    )

    assert response.status_code == 200
    assert response.get_json()["profile"]["business_id"] == "business-1"
    assert state.example_reads == ["viewer-1"]
    assert state.business_access_queries == 1
    assert state.write_role_queries == 0
    assert state.advisory_locks == 0
    assert state.profile_upserts == 0
    assert state.explicit_write_commits == 0
