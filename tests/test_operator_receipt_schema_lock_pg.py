"""A receipt connection must not wait on lazy audit DDL in the command transaction."""
import os
import uuid
import psycopg2
import pytest
from tests.test_operator_voice_pg import pg
from tests.fixtures.agent_security_legacy_ddl import ensure_agent_security_tables
from core import agent_api_security


def test_existing_audit_schema_does_not_block_independent_receipt(pg):
    connection, cursor = pg
    cursor.execute('SELECT current_schema() name')
    schema = cursor.fetchone()['name']
    ensure_agent_security_tables(cursor)
    connection.commit()
    other = psycopg2.connect(os.environ['OPERATOR_VOICE_TEST_DSN'], options='-c search_path='+schema)
    second = other.cursor()
    insert = "INSERT INTO agent_action_ledger(id,action_type,risk_level,status) VALUES (%s,'operator_request_received','low','received')"
    try:
        ensure_agent_security_tables(cursor)
        second.execute("SET LOCAL lock_timeout='500ms'")
        with pytest.raises(psycopg2.errors.LockNotAvailable):
            second.execute(insert, (str(uuid.uuid4()),))
        other.rollback()
        connection.rollback()
        agent_api_security.ensure_agent_security_tables(cursor)
        second.execute("SET LOCAL lock_timeout='500ms'")
        second.execute(insert, (str(uuid.uuid4()),))
        other.commit()
    finally:
        connection.rollback()
        other.rollback()
        other.close()
