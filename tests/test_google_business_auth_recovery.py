import json

import pytest

from api.google_business_api import (
    _google_auth_needs_reconnect,
    _refresh_matching_google_accounts,
)
from google_business_api import GoogleBusinessAPIError
from google_business_sync_worker import GoogleBusinessSyncWorker


class UpdateCursor:
    def __init__(self):
        self.query = ""
        self.params = ()
        self.rowcount = 0

    def execute(self, query, params=None):
        self.query = " ".join(query.split())
        self.params = params or ()
        self.rowcount = 2


def test_google_auth_status_requires_reconnect_after_revoked_refresh_token():
    assert _google_auth_needs_reconnect({"last_error": "invalid_grant: Token has been expired or revoked."})
    assert _google_auth_needs_reconnect({"last_error": "Доступ Google истёк. Подключите Google Business заново."})
    assert not _google_auth_needs_reconnect({"last_error": None})


def test_google_oauth_refresh_updates_only_accessible_google_accounts():
    cursor = UpdateCursor()

    updated = _refresh_matching_google_accounts(
        cursor,
        "auth_data_encrypted",
        "encrypted",
        ["accounts/2", "accounts/1", "accounts/2", ""],
        "user-1",
    )

    assert updated == 2
    assert "split_part(COALESCE(external_id, ''), '/locations/', 1) = ANY(%s)" in cursor.query
    assert "business.owner_id = %s OR actor.is_superadmin = TRUE" in cursor.query
    assert cursor.params == ("encrypted", ["accounts/1", "accounts/2"], "user-1", "user-1")


def test_google_worker_does_not_hide_invalid_grant(monkeypatch):
    worker = GoogleBusinessSyncWorker()

    class ExpiredCredentials:
        expired = True
        refresh_token = "refresh-token"

    monkeypatch.setattr(
        "google_business_sync_worker.decrypt_auth_data",
        lambda value: json.dumps({"refresh_token": "refresh-token"}),
    )
    monkeypatch.setattr(worker.auth, "dict_to_credentials", lambda value: ExpiredCredentials())

    def fail_refresh(credentials):
        raise RuntimeError("invalid_grant: Token has been expired or revoked.")

    monkeypatch.setattr(worker.auth, "refresh_credentials", fail_refresh)

    with pytest.raises(GoogleBusinessAPIError, match="Подключите Google Business заново"):
        worker._get_api_client({"id": "account-1", "auth_data_encrypted": "encrypted"})
