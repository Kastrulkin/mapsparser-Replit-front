"""Real PostgreSQL regression for the legacy business-data read route."""

import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit, urlunsplit
import uuid

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import parse_dsn
import pytest


ROOT = Path(__file__).resolve().parents[1]
OWNED_PREFIX = "localos_legacy_business_data_"


def isolated_base_dsn() -> str:
    database_url = os.getenv("LOCALOS_READINESS_JOURNEY_DATABASE_URL", "")
    if not database_url:
        pytest.skip("LOCALOS_READINESS_JOURNEY_DATABASE_URL is required for isolated PostgreSQL proof")
    if os.getenv("PGHOSTADDR") or os.getenv("PGSERVICE") or os.getenv("PGSERVICEFILE") or os.getenv("PGOPTIONS"):
        raise RuntimeError("real PostgreSQL proof refuses inherited libpq overrides")
    parsed_url = urlsplit(database_url)
    if parsed_url.scheme != "postgresql" or parsed_url.query or parsed_url.fragment:
        raise RuntimeError("real PostgreSQL proof requires a plain postgresql DSN without query or fragment")
    params = parse_dsn(database_url)
    port = str(params.get("port") or "")
    if (
        str(params.get("host") or "") not in {"127.0.0.1", "::1"}
        or not str(params.get("dbname") or "").lower().startswith("readiness_")
        or not port.isdigit()
        or int(port) < 32768
        or params.get("hostaddr")
        or params.get("service")
    ):
        raise RuntimeError("real PostgreSQL proof requires an explicit loopback readiness database")
    return database_url


@pytest.mark.parametrize("environment_key", ["PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE", "PGOPTIONS"])
def test_isolated_base_dsn_rejects_inherited_libpq_override(monkeypatch, environment_key):
    monkeypatch.setenv("LOCALOS_READINESS_JOURNEY_DATABASE_URL", "postgresql://owner@127.0.0.1:35418/readiness_operator_test")
    monkeypatch.setenv(environment_key, "unsafe")
    with pytest.raises(RuntimeError):
        isolated_base_dsn()


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql://owner@127.0.0.1:35418/readiness_operator_test?dbname=other",
        "postgresql://owner@127.0.0.1:35418/readiness_operator_test#other",
        "mysql://owner@127.0.0.1:35418/readiness_operator_test",
    ],
)
def test_isolated_base_dsn_rejects_identity_rewriting_url_parts(monkeypatch, database_url):
    monkeypatch.setenv("LOCALOS_READINESS_JOURNEY_DATABASE_URL", database_url)
    monkeypatch.delenv("PGHOSTADDR", raising=False)
    monkeypatch.delenv("PGSERVICE", raising=False)
    monkeypatch.delenv("PGSERVICEFILE", raising=False)
    monkeypatch.delenv("PGOPTIONS", raising=False)
    with pytest.raises(RuntimeError):
        isolated_base_dsn()


def database_url_for(database_url: str, database_name: str) -> str:
    parts = urlsplit(database_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database_name}", parts.query, parts.fragment))


def migrate(database_url: str) -> None:
    environment = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", "")}
    existing_pythonpath = os.environ.get("PYTHONPATH", "")
    paths = [entry for entry in existing_pythonpath.split(os.pathsep) if entry]
    paths.extend((str(ROOT / "src"), str(ROOT)))
    environment.update(
        {
            "DATABASE_URL": database_url,
            "FLASK_APP": "src.main:app",
            "PYTHONPATH": os.pathsep.join(dict.fromkeys(paths)),
            "PYTHON_DOTENV_DISABLED": "1",
        }
    )
    completed = subprocess.run(
        [sys.executable, "-m", "flask", "db", "upgrade"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError((completed.stderr or completed.stdout)[-2000:])


def seed_user_and_business(database_url: str) -> tuple[str, str]:
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    from auth_system import hash_password

    user_id, business_id = str(uuid.uuid4()), str(uuid.uuid4())
    connection = psycopg2.connect(database_url)
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO users (id, email, password_hash, is_active, is_verified, is_superadmin)
            VALUES (%s, %s, %s, TRUE, TRUE, FALSE)
            """,
            (user_id, f"{user_id}@benchmark.invalid", hash_password("benchmark-password")),
        )
        cursor.execute(
            """
            INSERT INTO businesses (id, owner_id, name, entity_group, subscription_tier, subscription_status)
            VALUES (%s, %s, 'Legacy data benchmark', 'client', 'concierge', 'active')
            """,
            (business_id, user_id),
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()
    return user_id, business_id


@pytest.fixture
def migrated_business_database(monkeypatch):
    base_dsn = isolated_base_dsn()
    database_name = OWNED_PREFIX + uuid.uuid4().hex
    admin = psycopg2.connect(database_url_for(base_dsn, "postgres"))
    cursor = admin.cursor()
    try:
        admin.autocommit = True
        cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
    finally:
        cursor.close()
        admin.close()
    database_url = database_url_for(base_dsn, database_name)
    try:
        migrate(database_url)
        monkeypatch.setenv("DATABASE_URL", database_url)
        monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
        monkeypatch.setenv("BROWSER_COOKIE_AUTH_ENABLED", "false")
        yield database_url
    finally:
        admin = psycopg2.connect(database_url_for(base_dsn, "postgres"))
        cursor = admin.cursor()
        try:
            admin.autocommit = True
            cursor.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(database_name)))
        finally:
            cursor.close()
            admin.close()


def test_legacy_business_data_reads_migrated_transaction_date_and_preserves_tenant_scope(migrated_business_database):
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    from main import app

    user_id, business_id = seed_user_and_business(migrated_business_database)
    _foreign_user, foreign_business = seed_user_and_business(migrated_business_database)
    connection = psycopg2.connect(migrated_business_database)
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO financialtransactions (id, user_id, business_id, amount, description, transaction_type, transaction_date)
            VALUES ('newest', %s, %s, 1200, 'Новая операция', 'income', '2026-09-18'),
                   ('older', %s, %s, 800, 'Старая операция', 'income', '2026-09-17')
            """,
            (user_id, business_id, user_id, business_id),
        )
        cursor.execute(
            """
            INSERT INTO userservices (id, user_id, business_id, category, name, description, keywords, price, is_active)
            VALUES ('service-1', %s, %s, 'hair', 'Стрижка', 'Услуга', '[]'::jsonb, '1200', TRUE)
            """,
            (user_id, business_id),
        )
        cursor.execute(
            """
            INSERT INTO financialmetrics (id, business_id, metric_name, metric_value, period)
            VALUES ('metric-1', %s, 'revenue', 2000, '2026-09')
            """,
            (business_id,),
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()

    client = app.test_client()
    login = client.post(
        "/api/auth/login",
        json={"email": f"{user_id}@benchmark.invalid", "password": "benchmark-password"},
    )
    assert login.status_code == 200
    token = login.get_json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get(f"/api/business/{business_id}/data", headers=headers)

    assert response.status_code == 200
    financial_data = response.get_json()["financial_data"]
    assert [transaction["id"] for transaction in financial_data["transactions"]] == ["newest", "older"]
    assert "2026" in str(financial_data["transactions"][0]["date"])
    assert response.get_json()["services"][0]["id"] == "service-1"
    assert financial_data["metrics"][0]["id"] == "metric-1"
    assert client.get(f"/api/business/{foreign_business}/data", headers=headers).status_code == 403
