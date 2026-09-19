from dataclasses import dataclass

import pytest

from services import operator_audio, operator_chat_service, telegram_dashboard
from core import auth_helpers


@dataclass
class StrictRoleCursor:
    actor_id: str
    superadmin: bool = False
    active: bool = True
    last_operation: str = ""
    business_access_queries: int = 0
    write_role_queries: int = 0
    subscription_queries: int = 0

    def execute(self, query, params=None):
        normalized = " ".join(str(query).lower().split())
        bound_params = tuple(params or ())
        if normalized == "select id, is_active, is_superadmin from users where id=%s":
            assert bound_params == (self.actor_id,)
            self.last_operation = "user"
            return
        if "from businesses b" in normalized:
            assert bound_params == (self.actor_id, self.actor_id, self.actor_id, "business-1")
            self.business_access_queries += 1
            self.last_operation = "business_access"
            return
        if "select bm.role" in normalized:
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
        if normalized == "select subscription_tier, subscription_status, subscription_ends_at from businesses where id=%s":
            assert bound_params == ("business-1",)
            self.subscription_queries += 1
            self.last_operation = "subscription"
            return
        raise AssertionError(f"unexpected SQL in Telegram operator admission test: {normalized}")

    def fetchone(self):
        if self.last_operation == "user":
            return {"id": self.actor_id, "is_active": self.active, "is_superadmin": self.superadmin}
        if self.last_operation == "business_access":
            return {
                "owner_id": "owner-1",
                "has_business_membership": self.actor_id in {"viewer-1", "member-1", "mixed-role-1"},
                "has_network_membership": self.actor_id in {"network-viewer-1", "network-member-1", "mixed-role-1"},
                "owns_network": self.actor_id == "network-owner-1",
            }
        if self.last_operation == "subscription":
            return {"subscription_tier": "concierge", "subscription_status": "active", "subscription_ends_at": None}
        raise AssertionError(f"unexpected fetchone after {self.last_operation}")

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


@pytest.fixture(autouse=True)
def clear_voice_execution_context():
    token = operator_audio.VOICE_EXECUTION_CONTEXT.set(None)
    yield
    operator_audio.VOICE_EXECUTION_CONTEXT.reset(token)


def _route_with_process_spy(monkeypatch, cursor):
    calls = []

    def process_chat(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return {"status": "completed", "chat_response": "Готово"}

    monkeypatch.setattr(operator_chat_service, "process_chat", process_chat)
    result = telegram_dashboard.route_operator_chat_for_telegram(
        cursor,
        business_id="business-1",
        user_id=cursor.actor_id,
        message="Подготовь новость о новой услуге",
    )
    return result, calls


@pytest.mark.parametrize(
    ("actor_id", "superadmin", "expected_write_queries"),
    [
        ("member-1", False, 1),
        ("network-member-1", False, 1),
        ("owner-1", False, 0),
        ("network-owner-1", False, 1),
        ("mixed-role-1", False, 1),
        ("superadmin-1", True, 0),
    ],
)
def test_telegram_operator_chat_allows_canonical_writers(monkeypatch, actor_id, superadmin, expected_write_queries):
    cursor = StrictRoleCursor(actor_id=actor_id, superadmin=superadmin)

    result, calls = _route_with_process_spy(monkeypatch, cursor)

    assert operator_audio.verify_business_access is auth_helpers.verify_business_access
    assert result["status"] == "completed"
    assert len(calls) == 1
    assert calls[0]["kwargs"]["actor_context"]["is_superadmin"] is superadmin
    assert cursor.business_access_queries == 1
    assert cursor.write_role_queries == expected_write_queries
    assert cursor.subscription_queries == 1


@pytest.mark.parametrize("actor_id", ["viewer-1", "network-viewer-1"])
def test_telegram_operator_chat_denies_viewers_before_process_chat(monkeypatch, actor_id):
    cursor = StrictRoleCursor(actor_id=actor_id)
    calls = []

    monkeypatch.setattr(operator_chat_service, "process_chat", lambda *args, **kwargs: calls.append((args, kwargs)))

    with pytest.raises(PermissionError, match="Нет доступа к бизнесу"):
        telegram_dashboard.route_operator_chat_for_telegram(
            cursor,
            business_id="business-1",
            user_id=actor_id,
            message="Подготовь новость о новой услуге",
        )

    assert calls == []
    assert cursor.business_access_queries == 1
    assert cursor.write_role_queries == 1
    assert cursor.subscription_queries == 0


def test_telegram_operator_chat_denies_stranger_before_process_chat(monkeypatch):
    cursor = StrictRoleCursor(actor_id="stranger-1")
    calls = []

    monkeypatch.setattr(operator_chat_service, "process_chat", lambda *args, **kwargs: calls.append((args, kwargs)))

    with pytest.raises(PermissionError, match="Нет доступа к бизнесу"):
        telegram_dashboard.route_operator_chat_for_telegram(
            cursor,
            business_id="business-1",
            user_id="stranger-1",
            message="Подготовь новость о новой услуге",
        )

    assert calls == []
    assert cursor.business_access_queries == 1
    assert cursor.write_role_queries == 0
    assert cursor.subscription_queries == 0


@pytest.mark.parametrize("active", [False, True])
def test_telegram_operator_chat_denies_inactive_or_missing_users_before_business_access(monkeypatch, active):
    cursor = StrictRoleCursor(actor_id="inactive-1" if not active else "missing-1", active=active)
    calls = []

    if active:
        monkeypatch.setattr(cursor, "fetchone", lambda: None)
    monkeypatch.setattr(operator_chat_service, "process_chat", lambda *args, **kwargs: calls.append((args, kwargs)))

    with pytest.raises(PermissionError, match="Аккаунт недоступен"):
        telegram_dashboard.route_operator_chat_for_telegram(
            cursor,
            business_id="business-1",
            user_id=cursor.actor_id,
            message="Подготовь новость о новой услуге",
        )

    assert calls == []
    assert cursor.business_access_queries == 0
    assert cursor.write_role_queries == 0
    assert cursor.subscription_queries == 0


def test_authorize_actor_defaults_to_read_access_without_write_role_query():
    cursor = StrictRoleCursor(actor_id="viewer-1")

    actor, access = operator_audio.authorize_actor(cursor, "viewer-1", "business-1")

    assert actor["role"] == "business_user"
    assert actor["is_superadmin"] is False
    assert access
    assert cursor.business_access_queries == 1
    assert cursor.write_role_queries == 0
    assert cursor.subscription_queries == 1
