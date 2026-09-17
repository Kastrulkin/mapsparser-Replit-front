import uuid
from urllib.parse import urlsplit, urlunsplit

import psycopg2
import pytest

from api import finance_api



def _database_url(database_url: str, database_name: str) -> str:
    parts = urlsplit(database_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database_name}", parts.query, parts.fragment))


def _dsn(postgres_container) -> str:
    return postgres_container.get_connection_url().replace("postgresql+psycopg2://", "postgresql://", 1)


@pytest.fixture
def finance_import_database(postgres_container):
    database_name = f"localos_data_fin_01_{uuid.uuid4().hex}"
    admin_url = _database_url(_dsn(postgres_container), "postgres")
    database_url = _database_url(_dsn(postgres_container), database_name)
    created = False
    database = None
    try:
        admin = psycopg2.connect(admin_url)
        admin.autocommit = True
        admin_cursor = admin.cursor()
        try:
            admin_cursor.execute(f'CREATE DATABASE "{database_name}"')
            created = True
        finally:
            admin_cursor.close()
            admin.close()
        database = psycopg2.connect(database_url)
        cursor = database.cursor()
        try:
            cursor.execute(
                """
                CREATE TABLE finance_entries (
                    id TEXT PRIMARY KEY,
                    business_id TEXT NOT NULL,
                    date DATE NOT NULL,
                    type TEXT NOT NULL,
                    category TEXT,
                    amount NUMERIC(14, 2) NOT NULL DEFAULT 0,
                    source TEXT NOT NULL DEFAULT 'manual',
                    comment TEXT,
                    import_batch_id TEXT,
                    external_id TEXT,
                    duplicate_key TEXT
                )
                """
            )
            cursor.execute(
                """
                CREATE UNIQUE INDEX uq_finance_entries_duplicate_key
                ON finance_entries(business_id, duplicate_key)
                WHERE duplicate_key IS NOT NULL
                """
            )
            cursor.execute(
                """
                CREATE TABLE finance_import_batches (
                    id TEXT PRIMARY KEY,
                    business_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    rows_imported INTEGER NOT NULL DEFAULT 0,
                    rows_failed INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            database.commit()
        finally:
            cursor.close()
        yield database, database_url
    finally:
        if database is not None:
            database.close()
        if created:
            admin = psycopg2.connect(admin_url)
            admin.autocommit = True
            admin_cursor = admin.cursor()
            try:
                admin_cursor.execute(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)')
            finally:
                admin_cursor.close()
                admin.close()


def _entry(duplicate_key: str, amount: int):
    return {
        "record_type": "entry",
        "date": "2026-09-18",
        "type": "revenue",
        "category": "sales",
        "amount": amount,
        "duplicate_key": duplicate_key,
        "row_number": amount,
    }


def test_concurrent_duplicate_does_not_poison_following_finance_import_row(finance_import_database):
    database, database_url = finance_import_database
    business_id = "finance-import-business"
    batch_id = "finance-import-batch"
    first = _entry("concurrent-duplicate", 100)
    following = _entry("following-row", 200)
    first_cursor = database.cursor()
    first_cursor.execute(
        "INSERT INTO finance_import_batches (id, business_id, status) VALUES (%s, %s, 'processing')",
        (batch_id, business_id),
    )
    assert finance_api._finance_import_duplicate_exists(
        first_cursor,
        business_id,
        first["record_type"],
        first["duplicate_key"],
    ) is False

    concurrent = psycopg2.connect(database_url)
    concurrent_cursor = concurrent.cursor()
    try:
        finance_api._insert_finance_import_item(concurrent_cursor, business_id, "other-batch", first)
        concurrent.commit()

        try:
            finance_api._insert_finance_import_item(first_cursor, business_id, batch_id, first)
        except psycopg2.errors.UniqueViolation:
            pass
        else:
            pytest.fail("concurrent duplicate must reach PostgreSQL unique index")

        finance_api._insert_finance_import_item(first_cursor, business_id, batch_id, following)
        first_cursor.execute(
            """
            UPDATE finance_import_batches
            SET status = 'completed_with_errors', rows_imported = 1, rows_failed = 1
            WHERE id = %s
            """,
            (batch_id,),
        )
        database.commit()
    finally:
        concurrent_cursor.close()
        concurrent.close()

    verify = database.cursor()
    verify.execute(
        "SELECT duplicate_key, import_batch_id FROM finance_entries WHERE business_id = %s ORDER BY duplicate_key",
        (business_id,),
    )
    assert verify.fetchall() == [("concurrent-duplicate", "other-batch"), ("following-row", batch_id)]
    verify.execute("SELECT status, rows_imported, rows_failed FROM finance_import_batches WHERE id = %s", (batch_id,))
    assert verify.fetchone() == ("completed_with_errors", 1, 1)
    verify.close()
