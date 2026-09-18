import json

import pytest

from scripts import staging_fixture_cli


class FixtureCursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self.queries = []
        self.description = []

    def execute(self, query, params=None):
        self.queries.append((str(query), params))

    def fetchone(self):
        if self.rows:
            return self.rows.pop(0)
        return None


class FixtureConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self):
        return self.cursor_value

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def social_fixture_environment(monkeypatch):
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("DATABASE_URL", "postgresql://owner@127.0.0.1:35418/localos_staging_socialtest")
    monkeypatch.setenv("LOCALOS_STAGING_FIXTURE_MODE", "1")
    for key in ("PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE", "PGOPTIONS"):
        monkeypatch.delenv(key, raising=False)


def test_fixture_guard_rejects_non_staging_before_connection(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://owner@127.0.0.1/localos_staging_test")

    with pytest.raises(RuntimeError, match="isolated staging"):
        staging_fixture_cli.require_isolated_staging()


def test_social_fixture_guard_rejects_missing_enable_or_non_exact_target(monkeypatch):
    monkeypatch.setenv("LOCALOS_STAGING_FIXTURE_MODE", "")
    with pytest.raises(RuntimeError, match="explicit staging fixture mode"):
        staging_fixture_cli.require_social_publication_reconciliation_fixture()
    monkeypatch.setenv("LOCALOS_STAGING_FIXTURE_MODE", "1")
    monkeypatch.setenv("DATABASE_URL", "postgresql://owner@127.0.0.1:35418/localos_staging_socialtest?hostaddr=192.0.2.8")
    with pytest.raises(RuntimeError, match="exact isolated staging database URL"):
        staging_fixture_cli.require_social_publication_reconciliation_fixture()


def test_reset_rejects_disabled_fixture_mode_before_any_connection(monkeypatch):
    monkeypatch.setenv("LOCALOS_STAGING_FIXTURE_MODE", "")
    called = False

    def unexpected_connection():
        nonlocal called
        called = True
        raise AssertionError("fixture guard must run before a database connection")

    monkeypatch.setattr(staging_fixture_cli, "get_db_connection", unexpected_connection)

    with pytest.raises(RuntimeError, match="explicit staging fixture mode"):
        staging_fixture_cli.reset_social_publication_reconciliation()

    assert called is False


def test_reset_writes_only_fixed_owner_scoped_reconciliation_records(monkeypatch, capsys):
    cursor = FixtureCursor([None, None, None, None])
    connection = FixtureConnection(cursor)
    monkeypatch.setattr(staging_fixture_cli, "get_db_connection", lambda: connection)
    monkeypatch.setattr(staging_fixture_cli, "owner_business_id", lambda: "owner-business")
    monkeypatch.setattr(staging_fixture_cli, "owner_user_id", lambda: "owner-user")

    staging_fixture_cli.reset_social_publication_reconciliation()

    fixture = json.loads(capsys.readouterr().out)
    query_text = "\n".join(query for query, _params in cursor.queries)
    assert fixture["business_id"] == "owner-business"
    assert fixture["post_id"] == staging_fixture_cli.fixture_id(staging_fixture_cli.SOCIAL_RECONCILIATION_POST_LABEL)
    assert "SELECT business_id, content_plan_id, content_plan_item_id, metadata_json FROM social_posts WHERE id = %s" in query_text
    assert "SELECT id, business_id, content_plan_id, metadata_json FROM social_posts" in query_text
    assert "INSERT INTO contentplans" in query_text
    assert "'E2E publication reconciliation', 14, CURRENT_DATE" in query_text
    assert "CURRENT_DATE + 13" in query_text
    assert "created_at = NOW()" in query_text
    assert "INSERT INTO contentplanitems" in query_text
    assert "INSERT INTO social_posts" in query_text
    assert "'publishing'" in query_text
    assert "DELETE" not in query_text
    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert connection.closed is True


def test_reset_refuses_fixed_id_collision_outside_owner_without_mutation(monkeypatch):
    cursor = FixtureCursor([None, None, ("foreign-business",)])
    connection = FixtureConnection(cursor)
    monkeypatch.setattr(staging_fixture_cli, "get_db_connection", lambda: connection)
    monkeypatch.setattr(staging_fixture_cli, "owner_business_id", lambda: "owner-business")
    monkeypatch.setattr(staging_fixture_cli, "owner_user_id", lambda: "owner-user")

    with pytest.raises(RuntimeError, match="another business"):
        staging_fixture_cli.reset_social_publication_reconciliation()

    assert len(cursor.queries) == 3
    assert connection.commits == 0
    assert connection.rollbacks == 1
    assert connection.closed is True


def test_reset_refuses_item_platform_collision_without_mutation(monkeypatch):
    cursor = FixtureCursor([None, None, None, ("other-post", "owner-business")])
    connection = FixtureConnection(cursor)
    monkeypatch.setattr(staging_fixture_cli, "get_db_connection", lambda: connection)
    monkeypatch.setattr(staging_fixture_cli, "owner_business_id", lambda: "owner-business")
    monkeypatch.setattr(staging_fixture_cli, "owner_user_id", lambda: "owner-user")

    with pytest.raises(RuntimeError, match="another post"):
        staging_fixture_cli.reset_social_publication_reconciliation()

    assert len(cursor.queries) == 4
    assert connection.commits == 0
    assert connection.rollbacks == 1
    assert connection.closed is True


def test_reset_refuses_owner_owned_non_fixture_records_without_mutation(monkeypatch):
    cursor = FixtureCursor([("owner-business", "E2E publication reconciliation", {"fixture": "different-fixture"})])
    connection = FixtureConnection(cursor)
    monkeypatch.setattr(staging_fixture_cli, "get_db_connection", lambda: connection)
    monkeypatch.setattr(staging_fixture_cli, "owner_business_id", lambda: "owner-business")
    monkeypatch.setattr(staging_fixture_cli, "owner_user_id", lambda: "owner-user")

    with pytest.raises(RuntimeError, match="fixture identity"):
        staging_fixture_cli.reset_social_publication_reconciliation()

    assert len(cursor.queries) == 1
    assert connection.commits == 0
    assert connection.rollbacks == 1
    assert connection.closed is True


def test_reset_refuses_owner_owned_post_with_wrong_fixture_relationship(monkeypatch):
    cursor = FixtureCursor([
        None,
        None,
        ("owner-business", "other-plan", "other-item", {"fixture": "social-publication-reconciliation"}),
    ])
    connection = FixtureConnection(cursor)
    monkeypatch.setattr(staging_fixture_cli, "get_db_connection", lambda: connection)
    monkeypatch.setattr(staging_fixture_cli, "owner_business_id", lambda: "owner-business")
    monkeypatch.setattr(staging_fixture_cli, "owner_user_id", lambda: "owner-user")

    with pytest.raises(RuntimeError, match="fixture identity"):
        staging_fixture_cli.reset_social_publication_reconciliation()

    assert len(cursor.queries) == 3
    assert connection.commits == 0
    assert connection.rollbacks == 1


def test_reset_is_repeatable_and_inspect_returns_only_owner_record(monkeypatch, capsys):
    reset_cursor = FixtureCursor([None, None, None, None, None, None, None, None])
    reset_connection = FixtureConnection(reset_cursor)
    monkeypatch.setattr(staging_fixture_cli, "get_db_connection", lambda: reset_connection)
    monkeypatch.setattr(staging_fixture_cli, "owner_business_id", lambda: "owner-business")
    monkeypatch.setattr(staging_fixture_cli, "owner_user_id", lambda: "owner-user")

    staging_fixture_cli.reset_social_publication_reconciliation()
    first = json.loads(capsys.readouterr().out)
    staging_fixture_cli.reset_social_publication_reconciliation()
    second = json.loads(capsys.readouterr().out)

    assert first["post_id"] == second["post_id"]
    assert first["attempt_id"] == second["attempt_id"]
    assert reset_connection.commits == 2
    inspect_cursor = FixtureCursor([("post-id", "owner-business", "published", None, "https://example.invalid/receipt", {"publish_attempt": {"state": "manual_confirmed"}})])
    inspect_cursor.description = [
        ("id",), ("business_id",), ("status",), ("provider_post_id",), ("provider_post_url",), ("metadata_json",),
    ]
    inspect_connection = FixtureConnection(inspect_cursor)
    monkeypatch.setattr(staging_fixture_cli, "get_db_connection", lambda: inspect_connection)

    staging_fixture_cli.inspect_social_publication_reconciliation()

    inspected = json.loads(capsys.readouterr().out)
    assert inspected["business_id"] == "owner-business"
    assert inspected["status"] == "published"
    assert inspected["provider_post_url"] == "https://example.invalid/receipt"
    assert inspected["attempt_id"] == staging_fixture_cli.fixture_id(staging_fixture_cli.SOCIAL_RECONCILIATION_ATTEMPT_LABEL)
    assert inspect_connection.closed is True
