"""Regression coverage for authorization changes after a publish claim.

The claim and provider phases use separate database connections.  A user can
therefore lose editor access after the durable ``publishing`` claim and before
the provider adapter is called.  The provider phase must re-admit writes, but
must not finalize an already issued provider effect as a new write gate.
"""

from __future__ import annotations

import pytest

from services import social_post_service
from services.social_posts import publication_lifecycle


class _RoleCursor:
    def __init__(self, role: str):
        self.role = role
        self._row = None
        self._rows = []
        self.executed: list[str] = []

    def execute(self, query, _params=None):
        normalized = " ".join(str(query).split())
        self.executed.append(normalized)
        if "pg_try_advisory_lock" in normalized:
            self._row = (True,)
        elif "pg_advisory_unlock" in normalized:
            self._row = (True,)
        elif "COALESCE(is_superadmin, FALSE)" in normalized:
            self._row = (False,)
        elif "FROM businesses b" in normalized and "has_business_membership" in normalized:
            self._row = ("owner-1", True, False, False)
        elif "SELECT bm.role" in normalized:
            self._rows = [(self.role,)]
        else:
            raise AssertionError(f"unexpected SQL: {normalized}")

    def fetchone(self):
        return self._row

    def fetchall(self):
        return self._rows


class _RoleConnection:
    def __init__(self, cursor: _RoleCursor):
        self.cursor_value = cursor
        self.autocommit = False

    def cursor(self):
        return self.cursor_value

    def set_session(self, *, autocommit=False):
        self.autocommit = autocommit


class _RoleDatabaseManager:
    instances: list["_RoleDatabaseManager"] = []
    role = "viewer"

    def __init__(self):
        self.cursor_value = _RoleCursor(self.role)
        self.conn = _RoleConnection(self.cursor_value)
        self.closed = False
        self.instances.append(self)

    def close(self):
        self.closed = True


def _claimed_post(post_id: str) -> dict:
    snapshot = {"hash": "approval-snapshot"}
    return {
        "id": post_id,
        "business_id": "business-1",
        "platform": "telegram",
        "publish_mode": "api",
        "status": "publishing",
        "approval_id": "approval-1",
        "platform_text": "Approved text",
        "base_text": "Approved text",
        "metadata_json": {
            "publish_attempt": {
                "id": "attempt-1",
                "state": "intent_committed",
                "approval_id": "approval-1",
                "approval_snapshot": snapshot,
                "approval_snapshot_hash": "approval-snapshot",
                "content_business_fingerprint": social_post_service._publish_attempt_fingerprint(
                    {
                        "business_id": "business-1",
                        "platform_text": "Approved text",
                        "base_text": "Approved text",
                        "platform": "telegram",
                    }
                ),
            }
        },
        "_publish_attempt_claimed_now": True,
    }


def _configure_provider_phase(monkeypatch, role: str):
    _RoleDatabaseManager.instances = []
    _RoleDatabaseManager.role = role
    current = _claimed_post("post-1")
    adapter_calls: list[dict] = []
    finalizer_calls: list[tuple] = []
    monkeypatch.setattr(social_post_service, "DatabaseManager", _RoleDatabaseManager)
    monkeypatch.setattr(
        social_post_service,
        "_claim_social_post_publish",
        lambda _user_id, _post_id: _claimed_post("post-1"),
    )
    monkeypatch.setattr(
        social_post_service,
        "_load_post_for_user",
        lambda _cursor, _user_id, _post_id: current,
    )
    monkeypatch.setattr(publication_lifecycle, "snapshot_is_well_formed", lambda _snapshot, _post: True)
    monkeypatch.setattr(
        social_post_service,
        "_publish_api_post",
        lambda _cursor, post, _snapshot: adapter_calls.append(post) or {
            "publish_outcome": "accepted",
            "provider_post_id": "provider-1",
        },
    )
    monkeypatch.setattr(
        social_post_service,
        "_finalize_social_post_publish",
        lambda *args: finalizer_calls.append(args) or {"status": "published", "provider_post_id": "provider-1"},
    )
    return current, adapter_calls, finalizer_calls


def test_viewer_demotion_after_claim_never_reaches_provider_and_keeps_reconciliation_state(monkeypatch):
    current, adapter_calls, finalizer_calls = _configure_provider_phase(monkeypatch, "viewer")

    with pytest.raises(PermissionError, match="Нет прав на изменение бизнеса"):
        social_post_service.publish_social_post("user-1", "post-1")

    assert adapter_calls == []
    assert finalizer_calls == []
    assert current["status"] == "publishing"
    assert current["metadata_json"]["publish_attempt"]["state"] == "intent_committed"
    assert _RoleDatabaseManager.instances[0].conn.autocommit is True
    assert any("pg_advisory_unlock" in query for query in _RoleDatabaseManager.instances[0].cursor_value.executed)


def test_editor_access_is_readmitted_and_keeps_existing_provider_finalization_path(monkeypatch):
    _current, adapter_calls, finalizer_calls = _configure_provider_phase(monkeypatch, "editor")

    result = social_post_service.publish_social_post("user-1", "post-1")

    assert result == {"status": "published", "provider_post_id": "provider-1"}
    assert [post["id"] for post in adapter_calls] == ["post-1"]
    assert len(finalizer_calls) == 1
    assert finalizer_calls[0][0:3] == ("user-1", "post-1", "attempt-1")
