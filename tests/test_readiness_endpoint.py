import main
from core import readiness
from legacy_routes import core_public
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit, urlunsplit
import uuid

import psycopg2
from psycopg2 import sql
import pytest


ROOT = Path(__file__).parents[1]
NATIVE_DSN_ENV = "LOCALOS_READINESS_ENDPOINT_TEST_DATABASE_URL"
NATIVE_GUARD_ENV = "LOCALOS_READINESS_ENDPOINT_GUARD_SHA256"
OWNED_DATABASE_PREFIX = "localos_readiness_endpoint_"


class _Cursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self.queries = []
        self.closed = False

    def execute(self, query, parameters=None):
        self.queries.append((str(query), parameters))

    def fetchone(self):
        return self.rows.pop(0)

    def fetchall(self):
        return self.rows.pop(0)

    def close(self):
        self.closed = True


class _Connection:
    def __init__(self, cursor):
        self.cursor_value = cursor
        self.closed = False

    def cursor(self):
        return self.cursor_value

    def close(self):
        self.closed = True


def _healthy_rows():
    columns = []
    for table_name, names in readiness.REQUIRED_COLUMNS.items():
        columns.extend((table_name, name) for name in names)
    return [
        (1,),
        ("alembic_version",),
        [("head",)],
        columns,
        [(name,) for name in readiness.REQUIRED_INDEXES],
    ]


def test_database_ready_uses_only_bounded_read_only_queries(monkeypatch):
    cursor = _Cursor(_healthy_rows())
    connection = _Connection(cursor)
    captured = {}
    monkeypatch.setenv("DATABASE_URL", "postgresql://readiness")
    monkeypatch.setattr(readiness, "expected_heads", lambda: frozenset({"head"}))

    def connect(database_url, connect_timeout):
        captured["database_url"] = database_url
        captured["connect_timeout"] = connect_timeout
        return connection

    assert readiness.database_ready(connect) is True
    assert captured == {"database_url": "postgresql://readiness", "connect_timeout": 2}
    assert connection.closed is True
    assert cursor.closed is True
    assert cursor.queries[:4] == [
        ("BEGIN READ ONLY", None),
        ("SET LOCAL statement_timeout = %s", ("1500ms",)),
        ("SET LOCAL lock_timeout = %s", ("250ms",)),
        ("SELECT 1", None),
    ]
    assert all(
        query.lstrip().upper().startswith(("BEGIN READ ONLY", "SET LOCAL", "SELECT"))
        for query, _parameters in cursor.queries
    )
    assert all("create " not in query.lower() for query, _parameters in cursor.queries)
    assert all("drop " not in query.lower() for query, _parameters in cursor.queries)
    assert all("truncate " not in query.lower() for query, _parameters in cursor.queries)
    assert all("grant " not in query.lower() for query, _parameters in cursor.queries)


def test_database_ready_closes_resources_after_schema_failure(monkeypatch):
    rows = _healthy_rows()
    rows[-1] = []
    cursor = _Cursor(rows)
    connection = _Connection(cursor)
    monkeypatch.setenv("DATABASE_URL", "postgresql://readiness")
    monkeypatch.setattr(readiness, "expected_heads", lambda: frozenset({"head"}))

    assert readiness.database_ready(lambda dsn, connect_timeout: connection) is False
    assert connection.closed is True
    assert cursor.closed is True


def test_database_ready_rejects_missing_revision(monkeypatch):
    rows = _healthy_rows()
    rows[1] = (None,)
    cursor = _Cursor(rows)
    connection = _Connection(cursor)
    monkeypatch.setenv("DATABASE_URL", "postgresql://readiness")
    monkeypatch.setattr(readiness, "expected_heads", lambda: frozenset({"head"}))

    assert readiness.database_ready(lambda dsn, connect_timeout: connection) is False
    assert connection.closed is True
    assert cursor.closed is True


def test_database_ready_rejects_missing_required_column(monkeypatch):
    rows = _healthy_rows()
    rows[-2] = rows[-2][1:]
    cursor = _Cursor(rows)
    connection = _Connection(cursor)
    monkeypatch.setenv("DATABASE_URL", "postgresql://readiness")
    monkeypatch.setattr(readiness, "expected_heads", lambda: frozenset({"head"}))

    assert readiness.database_ready(lambda dsn, connect_timeout: connection) is False
    assert connection.closed is True
    assert cursor.closed is True


def test_database_ready_accepts_only_the_configured_compatible_revision(monkeypatch):
    rows = _healthy_rows()
    rows[2] = [("legacy-head",)]
    cursor = _Cursor(rows)
    connection = _Connection(cursor)
    monkeypatch.setenv("DATABASE_URL", "postgresql://readiness")
    monkeypatch.setenv("LOCALOS_COMPATIBLE_SCHEMA_REVISIONS", "legacy-head")
    monkeypatch.setattr(readiness, "expected_heads", lambda: frozenset({"current-head"}))

    assert readiness.database_ready(lambda dsn, connect_timeout: connection) is True
    assert connection.closed is True
    assert cursor.closed is True


def test_database_ready_closes_cursor_when_query_raises(monkeypatch):
    class _BrokenCursor(_Cursor):
        def execute(self, query, parameters=None):
            super().execute(query, parameters)
            if query == "SELECT 1":
                raise RuntimeError("database unavailable")

    cursor = _BrokenCursor([])
    connection = _Connection(cursor)
    monkeypatch.setenv("DATABASE_URL", "postgresql://readiness")

    assert readiness.database_ready(lambda dsn, connect_timeout: connection) is False
    assert connection.closed is True
    assert cursor.closed is True


def test_database_ready_does_not_raise_when_resource_close_fails(monkeypatch):
    class _BrokenCloseCursor(_Cursor):
        def close(self):
            self.closed = True
            raise RuntimeError("cursor close failed")

    class _BrokenCloseConnection(_Connection):
        def close(self):
            self.closed = True
            raise RuntimeError("connection close failed")

    cursor = _BrokenCloseCursor(_healthy_rows())
    connection = _BrokenCloseConnection(cursor)
    monkeypatch.setenv("DATABASE_URL", "postgresql://readiness")
    monkeypatch.setattr(readiness, "expected_heads", lambda: frozenset({"head"}))

    assert readiness.database_ready(lambda dsn, connect_timeout: connection) is False
    assert connection.closed is True
    assert cursor.closed is True


def test_database_ready_requires_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    assert readiness.database_ready(lambda dsn, connect_timeout: (_ for _ in ()).throw(AssertionError("must not connect"))) is False


def test_ready_response_is_generic_and_health_remains_db_free(monkeypatch):
    monkeypatch.setattr(core_public, "database_ready", lambda: False)
    monkeypatch.setattr(core_public, "should_track_discovery_path", lambda path: False)

    client = main.app.test_client()
    assert client.get("/health").get_json() == {"status": "ok", "message": "SEO анализатор работает"}
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.get_json() == {"status": "not_ready"}
    assert "database" not in response.get_data().decode("utf-8").lower()


def test_ready_route_returns_ready_only_when_probe_succeeds(monkeypatch):
    monkeypatch.setattr(core_public, "database_ready", lambda: True)
    monkeypatch.setattr(core_public, "should_track_discovery_path", lambda path: False)

    response = main.app.test_client().get("/ready")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ready"}


def test_schema_checker_imports_with_its_runtime_pythonpath():
    environment = {
        "PATH": os.getenv("PATH", ""),
        "PYTHONPATH": os.pathsep.join((str(ROOT), str(ROOT / "src"))),
    }
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import runpy; runpy.run_path('scripts/check_content_learning_schema.py', run_name='schema_import_probe')",
        ],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_schema_checker_standalone_cli_does_not_require_pythonpath():
    environment = {
        "PATH": os.getenv("PATH", ""),
        "DATABASE_URL": "postgresql://readiness_test_owner@127.0.0.1:1/readiness_unavailable",
    }
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_content_learning_schema.py")],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )

    assert result.returncode != 0
    assert "ModuleNotFoundError" not in (result.stdout + result.stderr)


def _native_base_dsn() -> str:
    database_url = os.getenv(NATIVE_DSN_ENV, "")
    if not database_url:
        pytest.skip(f"{NATIVE_DSN_ENV} is required for native readiness proof")
    if any(os.getenv(key) for key in ("PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE", "PGOPTIONS")):
        raise RuntimeError("native readiness proof refuses inherited libpq overrides")
    parsed = urlsplit(database_url)
    if (
        parsed.scheme != "postgresql"
        or parsed.hostname not in {"127.0.0.1", "::1"}
        or parsed.port != 35418
        or not re.fullmatch(r"/readiness_full_test_[a-z0-9_]+", parsed.path)
        or parsed.query
        or parsed.fragment
    ):
        raise RuntimeError("native readiness proof requires a migrated owned loopback readiness database")
    guard_directory = os.getenv("PYTHONPATH", "").split(os.pathsep)[0]
    guard_path = Path(guard_directory) / "sitecustomize.py"
    loaded_guard = sys.modules.get("sitecustomize")
    expected_hash = os.getenv(NATIVE_GUARD_ENV, "")
    if (
        not guard_path.is_file()
        or loaded_guard is None
        or Path(str(getattr(loaded_guard, "__file__", ""))).resolve() != guard_path.resolve()
        or not re.fullmatch(r"[0-9a-f]{64}", expected_hash)
        or hashlib.sha256(guard_path.read_bytes()).hexdigest() != expected_hash
    ):
        raise RuntimeError("native readiness proof requires pinned guard-first sitecustomize")
    return database_url


def _database_url_for(database_url: str, database_name: str) -> str:
    parts = urlsplit(database_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database_name}", "", ""))


def _run_migrations(database_url: str) -> None:
    guard_directory = os.getenv("PYTHONPATH", "").split(os.pathsep)[0]
    environment = {
        "PATH": os.getenv("PATH", ""),
        "HOME": os.getenv("HOME", ""),
        "DATABASE_URL": database_url,
        "FLASK_APP": "src.main:app",
        "PYTHONPATH": os.pathsep.join((guard_directory, str(ROOT / "src"), str(ROOT))),
        "PYTHON_DOTENV_DISABLED": "1",
        "BROWSER_COOKIE_AUTH_ENABLED": "false",
    }
    result = subprocess.run(
        [sys.executable, "-m", "flask", "db", "upgrade"],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        timeout=180,
        check=False,
    )
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout)[-2000:])


@pytest.fixture
def native_readiness_databases(monkeypatch):
    base_dsn = _native_base_dsn()
    database_name = OWNED_DATABASE_PREFIX + uuid.uuid4().hex
    empty_database_name = OWNED_DATABASE_PREFIX + uuid.uuid4().hex
    admin_dsn = _database_url_for(base_dsn, "postgres")
    expected_owner = str(urlsplit(base_dsn).username or "")
    if not expected_owner:
        raise RuntimeError("native readiness proof requires an explicit database owner")
    created_databases = {}
    try:
        admin = psycopg2.connect(admin_dsn, connect_timeout=5)
        cursor = admin.cursor()
        try:
            admin.autocommit = True
            for name in (database_name, empty_database_name):
                cursor.execute("SELECT 1 FROM pg_database WHERE datname=%s", (name,))
                if cursor.fetchone() is not None:
                    raise RuntimeError("native readiness proof refuses a pre-existing owned database")
                cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
                cursor.execute(
                    "SELECT d.oid, pg_get_userbyid(d.datdba) FROM pg_database d WHERE d.datname=%s",
                    (name,),
                )
                identity = cursor.fetchone()
                if identity is None or str(identity[1]) != expected_owner:
                    raise RuntimeError("native readiness proof refuses an unexpected database identity")
                created_databases[name] = (int(identity[0]), str(identity[1]))
        finally:
            cursor.close()
            admin.close()
        database_url = _database_url_for(base_dsn, database_name)
        empty_database_url = _database_url_for(base_dsn, empty_database_name)
        _run_migrations(database_url)
        monkeypatch.setenv("DATABASE_URL", database_url)
        monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
        monkeypatch.setenv("BROWSER_COOKIE_AUTH_ENABLED", "false")
        yield {
            "database_url": database_url,
            "empty_database_url": empty_database_url,
            "admin_dsn": admin_dsn,
        }
    finally:
        admin = None
        cursor = None
        try:
            admin = psycopg2.connect(admin_dsn, connect_timeout=5)
            cursor = admin.cursor()
            admin.autocommit = True
            for name, expected_identity in created_databases.items():
                cursor.execute(
                    "SELECT d.oid, pg_get_userbyid(d.datdba) FROM pg_database d WHERE d.datname=%s",
                    (name,),
                )
                identity = cursor.fetchone()
                if identity is None or (int(identity[0]), str(identity[1])) != expected_identity:
                    raise RuntimeError("native readiness cleanup refuses an unexpected target identity")
                cursor.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        finally:
            if cursor is not None:
                cursor.close()
            if admin is not None:
                admin.close()


def _response_is_generic_not_ready(response):
    assert response.status_code == 503
    assert response.get_json() == {"status": "not_ready"}
    response_text = response.get_data().decode("utf-8").lower()
    assert "database" not in response_text
    assert "alembic" not in response_text
    assert "postgres" not in response_text


def _schema_snapshot(database_url: str) -> tuple:
    connection = psycopg2.connect(database_url, connect_timeout=5)
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT version_num FROM alembic_version ORDER BY version_num")
        revisions = tuple(row[0] for row in cursor.fetchall())
        cursor.execute("SELECT COUNT(*) FROM contentplans")
        plan_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM contentplanitems")
        item_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM usernews")
        news_count = cursor.fetchone()[0]
        return revisions, plan_count, item_count, news_count
    finally:
        cursor.close()
        connection.close()


def _assert_database_absent(admin_dsn: str, database_name: str) -> None:
    connection = psycopg2.connect(admin_dsn, connect_timeout=5)
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT 1 FROM pg_database WHERE datname=%s", (database_name,))
        assert cursor.fetchone() is None
    finally:
        cursor.close()
        connection.close()


def _assert_readonly_transaction(database_url: str) -> None:
    connection = psycopg2.connect(database_url, connect_timeout=2)
    cursor = connection.cursor()
    try:
        cursor.execute("BEGIN READ ONLY")
        cursor.execute("SHOW transaction_read_only")
        assert cursor.fetchone()[0] == "on"
    finally:
        connection.rollback()
        cursor.close()
        connection.close()


def test_registered_readiness_routes_use_an_owned_migrated_database(native_readiness_databases, monkeypatch):
    database_url = native_readiness_databases["database_url"]
    _assert_readonly_transaction(database_url)
    before = _schema_snapshot(database_url)
    monkeypatch.setattr(core_public, "should_track_discovery_path", lambda path: False)
    client = main.app.test_client()

    assert client.get("/health").get_json() == {"status": "ok", "message": "SEO анализатор работает"}
    assert client.get("/ready").status_code == 200
    assert client.get("/ready").get_json() == {"status": "ready"}
    assert _schema_snapshot(database_url) == before

    monkeypatch.setenv("LOCALOS_SCHEMA_NAME", "readiness_missing_" + uuid.uuid4().hex)
    _response_is_generic_not_ready(client.get("/ready"))
    monkeypatch.delenv("LOCALOS_SCHEMA_NAME", raising=False)

    connection = psycopg2.connect(database_url, connect_timeout=5)
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT version_num FROM alembic_version ORDER BY version_num")
        actual_revisions = tuple(row[0] for row in cursor.fetchall())
        cursor.execute("DELETE FROM alembic_version")
        cursor.execute("INSERT INTO alembic_version(version_num) VALUES ('readiness-mismatch')")
        connection.commit()
        _response_is_generic_not_ready(client.get("/ready"))
        cursor.execute("DELETE FROM alembic_version")
        for revision in actual_revisions:
            cursor.execute("INSERT INTO alembic_version(version_num) VALUES (%s)", (revision,))
        connection.commit()
    finally:
        cursor.close()
        connection.close()
    assert client.get("/ready").get_json() == {"status": "ready"}
    assert _schema_snapshot(database_url) == before

    monkeypatch.setenv("DATABASE_URL", native_readiness_databases["empty_database_url"])
    _response_is_generic_not_ready(client.get("/ready"))

    unavailable_name = OWNED_DATABASE_PREFIX + uuid.uuid4().hex
    unavailable_url = _database_url_for(database_url, unavailable_name)
    _assert_database_absent(native_readiness_databases["admin_dsn"], unavailable_name)
    monkeypatch.setenv("DATABASE_URL", unavailable_url)
    _response_is_generic_not_ready(client.get("/ready"))
    _assert_database_absent(native_readiness_databases["admin_dsn"], unavailable_name)

    environment = {
        "PATH": os.getenv("PATH", ""),
        "HOME": os.getenv("HOME", ""),
        "DATABASE_URL": database_url,
        "PYTHONPATH": os.getenv("PYTHONPATH", ""),
        "PYTHON_DOTENV_DISABLED": "1",
        "BROWSER_COOKIE_AUTH_ENABLED": "false",
    }
    for command in (
        [sys.executable, str(ROOT / "scripts" / "localos_migrator.py"), "check"],
        [sys.executable, str(ROOT / "scripts" / "check_content_learning_schema.py")],
    ):
        result = subprocess.run(
            command,
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stderr or result.stdout
