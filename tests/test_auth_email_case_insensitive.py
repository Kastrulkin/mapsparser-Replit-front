import auth_system


class FakeCursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self.queries = []

    def execute(self, query, params=None):
        self.queries.append((query, params))

    def fetchone(self):
        if not self.rows:
            return None
        return self.rows.pop(0)


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor
        self.closed = False

    def cursor(self):
        return self.cursor_value

    def close(self):
        self.closed = True


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
