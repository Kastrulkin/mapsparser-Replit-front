from datetime import datetime, timedelta, timezone

import pytest

from services.creator_portal_service import (
    _creator_channel_url,
    connect_creator_telegram,
    create_telegram_connect_link,
)


class TelegramCursor:
    def __init__(self, invite=None, conflicting_account=None):
        self.invite = invite
        self.conflicting_account = conflicting_account
        self.last_query = ""
        self.executed = []

    def execute(self, query, params=None):
        self.last_query = query
        self.executed.append((query, params))

    def fetchone(self):
        if "FROM creator_invites i" in self.last_query:
            return self.invite
        if "WHERE telegram_id" in self.last_query:
            return self.conflicting_account
        return None


@pytest.mark.parametrize(
    ("platform", "value", "expected"),
    [
        ("telegram", "@anna_spb", "https://t.me/anna_spb"),
        ("instagram", "anna_places", "https://instagram.com/anna_places"),
        ("threads", "threads.net/@anna", "https://threads.net/@anna"),
        ("youtube", "https://www.youtube.com/@anna/?view=1", "https://youtube.com/@anna"),
    ],
)
def test_creator_channel_url_accepts_username_and_public_link(platform, value, expected):
    assert _creator_channel_url(platform, value) == expected


def test_creator_channel_url_rejects_unknown_platform():
    with pytest.raises(ValueError, match="поддерживаемую площадку"):
        _creator_channel_url("unknown", "anna")


def test_creator_channel_url_rejects_link_from_another_platform():
    with pytest.raises(ValueError, match="не соответствует"):
        _creator_channel_url("telegram", "instagram.com/anna")


def test_creator_creates_short_lived_telegram_connection_link(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_USERNAME", "LocalOspro_bot")
    cursor = TelegramCursor()

    result = create_telegram_connect_link(cursor, account={"id": "account-1", "creator_profile_id": "profile-1"})

    assert result["telegram_url"].startswith("https://t.me/LocalOspro_bot?start=creator_connect_")
    assert result["expires_in_minutes"] == 60
    assert any("purpose, email, expires_at" in query and params[3] == "telegram_login" for query, params in cursor.executed)


def test_creator_connects_telegram_without_changing_email_login():
    cursor = TelegramCursor(invite={
        "id": "invite-1",
        "creator_profile_id": "profile-1",
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=30),
        "claimed_at": None,
        "account_id": "account-1",
        "display_name": "Анна",
    })

    result = connect_creator_telegram(
        cursor,
        token="connect-token",
        telegram_id="12345",
        telegram_username="anna_spb",
    )

    account_update = next((query, params) for query, params in cursor.executed if "UPDATE creator_accounts" in query)
    assert "preferred_auth" not in account_update[0]
    assert account_update[1] == ("12345", "anna_spb", "account-1")
    assert result["display_name"] == "Анна"
    assert result["portal_url"].startswith("https://localos.pro/creator/login/telegram?token=")


def test_creator_cannot_reuse_or_steal_telegram_connection():
    expired = TelegramCursor(invite={
        "id": "invite-1",
        "creator_profile_id": "profile-1",
        "expires_at": datetime.now(timezone.utc) - timedelta(seconds=1),
        "claimed_at": None,
        "account_id": "account-1",
        "display_name": "Анна",
    })
    with pytest.raises(LookupError, match="истекла"):
        connect_creator_telegram(expired, token="expired", telegram_id="12345", telegram_username="anna")

    conflict = TelegramCursor(invite={
        "id": "invite-2",
        "creator_profile_id": "profile-1",
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=30),
        "claimed_at": None,
        "account_id": "account-1",
        "display_name": "Анна",
    }, conflicting_account={"id": "account-2"})
    with pytest.raises(ValueError, match="другому кабинету"):
        connect_creator_telegram(conflict, token="conflict", telegram_id="12345", telegram_username="anna")
