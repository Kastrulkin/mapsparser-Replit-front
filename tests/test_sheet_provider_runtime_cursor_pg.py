"""Exercise Sheets claims through the same cursor adapter used by the worker."""

import os

import pytest
from psycopg2 import sql

from database_manager import DBCursorWrapper, DatabaseManager
from services.agent_sheet_provider_executor import claim_next_sheet_provider_request
from tests import test_agent_sheet_provider_queue_pg


sheet_queue_db = test_agent_sheet_provider_queue_pg.sheet_queue_db
_insert_bound_request = test_agent_sheet_provider_queue_pg._insert_bound_request


@pytest.fixture
def runtime_sheet_database(sheet_queue_db, monkeypatch):
    first, _second = sheet_queue_db
    cursor = first.cursor()
    cursor.execute("SELECT current_schema() AS name")
    schema = cursor.fetchone()["name"]
    first.commit()
    monkeypatch.setenv("DATABASE_URL", os.environ["LOCALOS_TEST_DATABASE_URL"])
    database = DatabaseManager()
    try:
        runtime_cursor = database.conn.cursor()
        assert isinstance(runtime_cursor, DBCursorWrapper)
        runtime_cursor.execute(
            sql.SQL("SET search_path TO {}").format(sql.Identifier(schema))
        )
        database.conn.commit()
        yield database
    finally:
        database.rollback_and_close()


def test_runtime_cursor_claims_approved_request_once(
    sheet_queue_db, runtime_sheet_database
):
    first, second = sheet_queue_db
    _insert_bound_request(first.cursor())
    first.commit()
    cursor = runtime_sheet_database.conn.cursor()

    claimed = claim_next_sheet_provider_request(cursor, business_id="biz")
    assert claimed is not None
    assert claimed["id"] == "sheet-1"
    assert claimed["provider_lease_token"]
    assert claimed["provider_attempt_count"] == 1
    assert claimed["apply_state"] == "provider_executing"
    runtime_sheet_database.conn.commit()

    assert claim_next_sheet_provider_request(cursor, business_id="biz") is None
    runtime_sheet_database.conn.commit()
    verify = second.cursor()
    verify.execute(
        "SELECT provider_attempt_count, provider_write_performed "
        "FROM agent_sheet_operation_requests WHERE id='sheet-1'"
    )
    assert verify.fetchone() == {
        "provider_attempt_count": 1,
        "provider_write_performed": False,
    }


def test_runtime_cursor_holds_request_without_approval_snapshot(
    sheet_queue_db, runtime_sheet_database
):
    first, second = sheet_queue_db
    _insert_bound_request(first.cursor())
    first.cursor().execute(
        "UPDATE agent_approvals SET payload_json='{}'::jsonb WHERE id='approval'"
    )
    first.commit()

    assert claim_next_sheet_provider_request(
        runtime_sheet_database.conn.cursor(), business_id="biz"
    ) is None
    runtime_sheet_database.conn.commit()
    verify = second.cursor()
    verify.execute(
        "SELECT apply_state, provider_attempt_count, provider_write_performed "
        "FROM agent_sheet_operation_requests WHERE id='sheet-1'"
    )
    assert verify.fetchone() == {
        "apply_state": "approval_invalid",
        "provider_attempt_count": 0,
        "provider_write_performed": False,
    }


def test_runtime_cursor_accepts_empty_queue(runtime_sheet_database):
    assert claim_next_sheet_provider_request(
        runtime_sheet_database.conn.cursor()
    ) is None
    runtime_sheet_database.conn.commit()
