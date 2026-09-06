"""Admission's snapshot share lock prevents a concurrent retention delete."""
import json
import os
import uuid

import psycopg2
from psycopg2.extras import RealDictCursor
import pytest

from services.compiled_input_snapshots import content_hash, resolve_snapshot
from services.compiled_table_contract import TABLE_SCHEMA


def test_snapshot_share_lock_blocks_purge_delete_until_admission_finishes():
    dsn = os.getenv("LOCALOS_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("requires isolated PostgreSQL")
    first = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    second = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    schema = "test_snapshot_lock_" + uuid.uuid4().hex
    cursor = first.cursor()
    cursor.execute(f'CREATE SCHEMA "{schema}"')
    cursor.execute(f'SET search_path TO "{schema}"')
    second.cursor().execute(f'SET search_path TO "{schema}"')
    second.commit()
    try:
        cursor.execute("""CREATE TABLE compiled_input_snapshots(
            id TEXT PRIMARY KEY,business_id TEXT,user_id TEXT,blueprint_id TEXT,
            schema_version TEXT,source_kind TEXT,content_hash TEXT,input_json JSONB,expires_at TIMESTAMPTZ
        )""")
        value = {"rows": [{"email": "a@example.test"}]}
        cursor.execute("""INSERT INTO compiled_input_snapshots VALUES(
            'snapshot','business','user','blueprint',%s,'user_table',%s,%s::jsonb,NOW()+INTERVAL '1 hour'
        )""", (TABLE_SCHEMA, content_hash(value), json.dumps(value)))
        first.commit()
        locked = resolve_snapshot(first.cursor(), "snapshot", "business", "user", "blueprint", lock=True)
        assert locked["content_hash"] == content_hash(value)
        second.cursor().execute("SET lock_timeout TO '1ms'")
        with pytest.raises(psycopg2.Error):
            second.cursor().execute("DELETE FROM compiled_input_snapshots WHERE id='snapshot'")
        second.rollback()
        first.commit()
        second.cursor().execute("DELETE FROM compiled_input_snapshots WHERE id='snapshot'")
        second.commit()
    finally:
        second.rollback()
        first.rollback()
        cursor = first.cursor()
        cursor.execute(f'DROP SCHEMA "{schema}" CASCADE')
        first.commit()
        second.close()
        first.close()
