"""DML-only proof for retired prospecting schema helpers."""
import importlib.util
import os
from pathlib import Path
import uuid

import psycopg2
from psycopg2.extras import RealDictCursor
import pytest

from api.prospecting.access_schema import _ensure_manual_crm_tables, _ensure_sales_room_tables
from api.prospecting.audit_routes import _ensure_partnership_artifacts_table_from_cursor


ROOT = Path(__file__).parents[1]


def _apply_prospecting_reconciliation(cursor) -> None:
    path = ROOT / "alembic_migrations/versions/20260906_move_prospecting_runtime_ddl.py"
    spec = importlib.util.spec_from_file_location("prospecting_reconciliation", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    previous_execute = migration.op.execute
    try:
        migration.op.execute = cursor.execute
        migration.upgrade()
    finally:
        migration.op.execute = previous_execute


@pytest.fixture
def connection():
    dsn = os.getenv("LOCALOS_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("LOCALOS_TEST_DATABASE_URL is required")
    conn = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    schema = "test_prospecting_" + uuid.uuid4().hex
    cur = conn.cursor()
    cur.execute(f'CREATE SCHEMA "{schema}"')
    cur.execute(f'SET search_path TO "{schema}"')
    cur.execute("CREATE TABLE prospectingleads(id TEXT PRIMARY KEY, status TEXT, pipeline_status TEXT, disqualification_reason TEXT, postponed_comment TEXT, next_action_at TIMESTAMPTZ, last_contact_at TIMESTAMPTZ, qualified_at TIMESTAMPTZ, last_manual_action_at TIMESTAMPTZ)")
    cur.execute("CREATE TABLE lead_groups(id TEXT PRIMARY KEY, name TEXT, status TEXT, created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ)")
    cur.execute("CREATE TABLE lead_group_items(id TEXT PRIMARY KEY, group_id TEXT, lead_id TEXT, added_at TIMESTAMPTZ)")
    cur.execute("CREATE TABLE lead_timeline_events(id TEXT PRIMARY KEY, lead_id TEXT, event_type TEXT, created_at TIMESTAMPTZ)")
    for table, columns in {
        'partnership_partner_cards':'id UUID,business_id UUID,source_company_name TEXT,partner_name TEXT,yandex_maps_match_status TEXT,lead_id TEXT,updated_at TIMESTAMPTZ',
        'sales_rooms':'id UUID,slug TEXT,business_id UUID,mode TEXT,lead_id TEXT,partner_card_id UUID,room_json JSONB,status TEXT,updated_at TIMESTAMPTZ',
        'sales_room_events':'id UUID,room_id UUID,event_type TEXT,created_at TIMESTAMPTZ',
        'sales_room_messages':'id UUID,room_id UUID,author_type TEXT,body_text TEXT,created_at TIMESTAMPTZ',
        'sales_room_files':'id UUID,room_id UUID,storage_path TEXT,public_url TEXT,created_at TIMESTAMPTZ',
        'sales_room_proposal_versions':'id UUID,room_id UUID,version_no INTEGER,body_text TEXT,created_at TIMESTAMPTZ',
        'sales_room_proposal_suggestions':'id UUID,room_id UUID,selection_text TEXT,status TEXT,created_at TIMESTAMPTZ',
        'sales_room_participants':'id UUID,room_id UUID,email TEXT,is_verified BOOLEAN,access_token TEXT,created_at TIMESTAMPTZ',
        'sales_room_audit_offers':'id UUID,room_id UUID,company_name TEXT,company_map_url TEXT,status TEXT,metadata_json JSONB,created_at TIMESTAMPTZ',
        'partnershipleadartifacts':'lead_id TEXT,audit_json JSONB,match_json JSONB,offer_draft_json JSONB,updated_at TIMESTAMPTZ',
    }.items():
        cur.execute(f'CREATE TABLE {table} ({columns})')
    conn.commit()
    yield conn, schema
    conn.rollback(); cur.execute(f'DROP SCHEMA "{schema}" CASCADE'); conn.commit(); conn.close()


def test_prospecting_helpers_require_no_ddl_privilege(connection):
    conn, schema = connection
    cur = conn.cursor(); role = 'test_prospecting_dml_' + uuid.uuid4().hex
    cur.execute(f'CREATE ROLE "{role}" NOLOGIN'); cur.execute(f'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"'); cur.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA "{schema}" TO "{role}"'); conn.commit()
    try:
        cur.execute(f'SET ROLE "{role}"'); cur.execute('SAVEPOINT denied')
        with pytest.raises(psycopg2.errors.InsufficientPrivilege): cur.execute('CREATE TABLE forbidden_prospecting_ddl(id INTEGER)')
        cur.execute('ROLLBACK TO SAVEPOINT denied')
        _ensure_manual_crm_tables(conn); _ensure_sales_room_tables(conn); _ensure_partnership_artifacts_table_from_cursor(cur)
    finally:
        conn.rollback(); cur.execute('RESET ROLE'); cur.execute(f'DROP OWNED BY "{role}"'); cur.execute(f'DROP ROLE "{role}"'); conn.commit()


def test_prospecting_reconciliation_preserves_manual_status_and_maps_delivery_state(connection):
    conn, _schema = connection
    cur = conn.cursor()
    cur.executemany(
        "INSERT INTO prospectingleads(id, status, pipeline_status) VALUES (%s, %s, %s)",
        [
            ("sent", "sent", "unprocessed"),
            ("delivered", "delivered", "unprocessed"),
            ("second", "second_message_sent", ""),
            ("manual", "sent", "postponed"),
            ("converted", "qualified", "unprocessed"),
        ],
    )
    _apply_prospecting_reconciliation(cur)
    cur.execute("SELECT id, pipeline_status FROM prospectingleads ORDER BY id")
    assert {row["id"]: row["pipeline_status"] for row in cur.fetchall()} == {
        "converted": "converted",
        "delivered": "waiting_reply",
        "manual": "postponed",
        "second": "second_message_sent",
        "sent": "contacted",
    }
