from src.services import checkout_session_service


class _FakeCursor:
    def __init__(self) -> None:
        self.description = [("id",), ("email",), ("password_hash",), ("telegram_id",)]
        self._rows = []
        self.connection = self
        self.closed = False
        self.last_execute = ("", None)

    def execute(self, query, params=None):
        text = str(query)
        self.last_execute = (text, params)
        if "FROM users WHERE email = %s" in text:
            self._rows = [{"id": "user-1", "email": "demo@example.com", "telegram_id": ""}]
            self.description = [("id",), ("email",), ("telegram_id",)]
            return
        if "UPDATE users" in text and "telegram_id = %s" in text:
            self._rows = [{"id": "user-1", "email": "demo@example.com", "telegram_id": "tg-1"}]
            self.description = [("id",), ("email",), ("telegram_id",)]
            return
        if "SELECT id, email, password_hash, telegram_id FROM users" in text:
            self._rows = [{"id": "user-2", "email": "new@example.com", "password_hash": "", "telegram_id": ""}]
            self.description = [("id",), ("email",), ("password_hash",), ("telegram_id",)]
            return
        if "SELECT id, name, yandex_url FROM businesses" in text:
            self._rows = [{"id": "biz-1", "name": "Capri", "yandex_url": "https://maps.example/capri"}]
            self.description = [("id",), ("name",), ("yandex_url",)]
            return
        self._rows = []

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)

    def close(self):
        self.closed = True


def test_find_or_create_user_for_checkout_backfills_telegram_id() -> None:
    cursor = _FakeCursor()
    session = {
        "email": "demo@example.com",
        "telegram_id": "tg-1",
        "telegram_name": "Demo",
        "phone": "",
    }

    user = checkout_session_service.find_or_create_user_for_checkout(session, cursor)

    assert user["id"] == "user-1"
    assert user["telegram_id"] == "tg-1"


def test_build_checkout_status_payload_requires_password_setup_for_passwordless_email_user() -> None:
    cursor = _FakeCursor()
    session = {
        "id": "session-1",
        "provider": "yookassa",
        "entry_point": "pricing_page",
        "status": "completed",
        "tariff_id": "starter_monthly",
        "user_id": "user-2",
        "business_id": "biz-1",
        "email": "new@example.com",
        "audit_public_url": "https://localos.pro/capri",
        "normalized_maps_url": "https://maps.example/capri",
    }

    payload = checkout_session_service.build_checkout_status_payload(session, cursor)

    assert payload["account_created"] is True
    assert payload["business_created"] is True
    assert payload["requires_password_setup"] is True
    assert payload["business_name"] == "Capri"
