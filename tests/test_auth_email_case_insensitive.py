import auth_system
from core.email_delivery import build_password_setup_link


class FakeCursor:
    def __init__(self, rows, fetchall_rows=None):
        self.rows = list(rows)
        self.fetchall_rows = list(fetchall_rows or [])
        self.queries = []

    def execute(self, query, params=None):
        self.queries.append((query, params))

    def fetchone(self):
        if not self.rows:
            return None
        return self.rows.pop(0)

    def fetchall(self):
        return list(self.fetchall_rows)


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor
        self.closed = False

    def cursor(self):
        return self.cursor_value

    def close(self):
        self.closed = True

    def commit(self):
        pass


def test_authenticate_user_looks_up_email_case_insensitively(monkeypatch):
    password_hash = auth_system.hash_password("secret-password")
    cursor = FakeCursor(
        [
            {
                "id": "user-1",
                "email": "Eliseygoodmaps@yandex.ru",
                "password_hash": password_hash,
                "name": "Elisey",
                "phone": None,
                "is_active": True,
                "is_verified": True,
            }
        ]
    )
    connection = FakeConnection(cursor)
    monkeypatch.setattr(auth_system, "get_db_connection", lambda: connection)

    result = auth_system.authenticate_user("  eliseygoodmaps@yandex.ru  ", "secret-password")

    assert result["id"] == "user-1"
    assert result["email"] == "Eliseygoodmaps@yandex.ru"
    assert "LOWER(email)" in cursor.queries[0][0]
    assert cursor.queries[0][1] == ("eliseygoodmaps@yandex.ru",)


def test_create_user_checks_duplicates_by_normalized_email(monkeypatch):
    cursor = FakeCursor([{"id": "existing-user"}])
    connection = FakeConnection(cursor)
    monkeypatch.setattr(auth_system, "get_db_connection", lambda: connection)

    result = auth_system.create_user("Eliseygoodmaps@yandex.ru", "secret-password")

    assert result["error"] == "Пользователь с таким email уже существует"
    assert "LOWER(email)" in cursor.queries[0][0]
    assert cursor.queries[0][1] == ("eliseygoodmaps@yandex.ru",)


def test_authenticate_user_blocks_unverified_email(monkeypatch):
    password_hash = auth_system.hash_password("secret-password")
    cursor = FakeCursor(
        [
            {
                "id": "user-1",
                "email": "new@example.com",
                "password_hash": password_hash,
                "name": "New",
                "phone": None,
                "is_active": True,
                "is_verified": False,
            }
        ]
    )
    connection = FakeConnection(cursor)
    monkeypatch.setattr(auth_system, "get_db_connection", lambda: connection)

    result = auth_system.authenticate_user("new@example.com", "secret-password")

    assert result["error"] == "EMAIL_NOT_VERIFIED"


def test_create_user_stores_consent_and_unverified_status(monkeypatch):
    columns = [
        {"column_name": "updated_at"},
        {"column_name": "verification_token"},
        {"column_name": "is_verified"},
        {"column_name": "personal_data_consent_at"},
        {"column_name": "personal_data_consent_version"},
        {"column_name": "privacy_accepted_at"},
        {"column_name": "terms_accepted_at"},
        {"column_name": "consent_ip"},
        {"column_name": "consent_user_agent"},
    ]
    cursor = FakeCursor([None], fetchall_rows=columns)
    connection = FakeConnection(cursor)
    monkeypatch.setattr(auth_system, "get_db_connection", lambda: connection)

    result = auth_system.create_user(
        "New@Example.com",
        "secret-password",
        personal_data_consent=True,
        consent_version="policy-v1",
        consent_ip="127.0.0.1",
        consent_user_agent="pytest",
        is_verified=False,
    )

    insert_query, insert_params = cursor.queries[2]
    assert result["email"] == "new@example.com"
    assert "personal_data_consent_at" in insert_query
    assert "is_verified" in insert_query
    assert False in insert_params
    assert "policy-v1" in insert_params


def test_create_password_setup_token_rotates_token_for_passwordless_user(monkeypatch):
    columns = [
        {"column_name": "verification_token"},
        {"column_name": "is_verified"},
        {"column_name": "updated_at"},
    ]
    cursor = FakeCursor(
        [
            {
                "id": "user-1",
                "email": "Manual@Example.com",
                "name": "Manual User",
                "phone": None,
                "password_hash": None,
                "is_active": True,
            }
        ],
        fetchall_rows=columns,
    )
    connection = FakeConnection(cursor)
    monkeypatch.setattr(auth_system, "get_db_connection", lambda: connection)
    monkeypatch.setattr(auth_system.secrets, "token_urlsafe", lambda length: "setup-token")

    result = auth_system.create_password_setup_token("user-1")

    update_query, update_params = cursor.queries[2]
    assert result["success"] is True
    assert result["verification_token"] == "setup-token"
    assert "verification_token = %s" in update_query
    assert "is_verified = %s" in update_query
    assert update_params[0] == "setup-token"
    assert False in update_params


def test_create_password_setup_token_does_not_rotate_existing_password_user(monkeypatch):
    columns = [{"column_name": "verification_token"}]
    cursor = FakeCursor(
        [
            {
                "id": "user-1",
                "email": "user@example.com",
                "name": "User",
                "phone": None,
                "password_hash": "hash",
                "is_active": True,
            }
        ],
        fetchall_rows=columns,
    )
    connection = FakeConnection(cursor)
    monkeypatch.setattr(auth_system, "get_db_connection", lambda: connection)

    result = auth_system.create_password_setup_token("user-1")

    assert result["error"] == "У пользователя уже установлен пароль"
    assert len(cursor.queries) == 2


def test_build_password_setup_link_encodes_email_and_token(monkeypatch):
    monkeypatch.setenv("PUBLIC_APP_URL", "https://localos.pro/")

    link = build_password_setup_link("User+test@example.com", "token/value")

    assert link == "https://localos.pro/set-password?email=User%2Btest%40example.com&token=token%2Fvalue"
