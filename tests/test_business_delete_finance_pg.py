"""Exercise business deletion against real PostgreSQL foreign keys."""
import os
from contextlib import closing

import psycopg2
import pytest
from psycopg2.extensions import parse_dsn
from psycopg2.extras import RealDictCursor

from database_manager import DatabaseManager, DBConnectionWrapper


FINANCE_TABLES = ('business_finance_settings', 'finance_daily_summaries', 'finance_daily_events')


@pytest.fixture
def business_db():
    dsn = os.getenv('OPERATOR_VOICE_TEST_DSN')
    if not dsn:
        pytest.skip('OPERATOR_VOICE_TEST_DSN not configured')
    settings = parse_dsn(dsn)
    if (settings.get('host') not in ('127.0.0.1', '::1') or settings.get('dbname') != 'localos_ci_test'
            or not settings.get('port') or not settings.get('user')
            or set(settings) - {'host', 'port', 'dbname', 'user', 'password'}
            or any(key in os.environ for key in ('PGHOSTADDR', 'PGSERVICE', 'PGSERVICEFILE', 'PGOPTIONS'))):
        raise ValueError('An explicit loopback connection to localos_ci_test is required')
    conn = psycopg2.connect(dsn, options='-c search_path=pg_temp,pg_catalog', cursor_factory=RealDictCursor)
    try:
        with conn.cursor() as cursor:
            cursor.execute('CREATE TEMP TABLE businesses (id text PRIMARY KEY, name text NOT NULL)')
            cursor.execute("INSERT INTO businesses VALUES ('target', 'Test client'), ('keep', 'Other client'), ('empty', 'No finance')")
            for table in FINANCE_TABLES:
                cursor.execute(f'CREATE TEMP TABLE {table} (business_id text NOT NULL REFERENCES businesses(id))')
                cursor.execute(f"INSERT INTO {table} VALUES ('target'), ('keep')")
        conn.commit()
        db = DatabaseManager.__new__(DatabaseManager)
        db.conn = DBConnectionWrapper(conn)
        db._closed = False
        yield db
    finally:
        conn.close()


def test_delete_business_removes_its_finance_rows_without_touching_other_clients(business_db):
    assert business_db.delete_business('target')
    with closing(business_db.conn.cursor()) as cursor:
        cursor.execute('SELECT id FROM businesses ORDER BY id')
        assert [row['id'] for row in cursor.fetchall()] == ['empty', 'keep']
        for table in FINANCE_TABLES:
            cursor.execute(f'SELECT business_id FROM {table}')
            assert [row['business_id'] for row in cursor.fetchall()] == ['keep']
    assert not business_db.delete_business('target')
    assert business_db.delete_business('empty')


def test_delete_business_rolls_back_finance_cleanup_if_another_foreign_key_blocks_it(business_db):
    with closing(business_db.conn.cursor()) as cursor:
        cursor.execute('CREATE TEMP TABLE other_business_data (business_id text REFERENCES businesses(id))')
        cursor.execute("INSERT INTO other_business_data VALUES ('target')")
    business_db.conn.commit()

    with pytest.raises(psycopg2.errors.ForeignKeyViolation, match='other_business_data'):
        business_db.delete_business('target')

    with closing(business_db.conn.cursor()) as cursor:
        cursor.execute("SELECT id FROM businesses WHERE id = 'target'")
        assert cursor.fetchone()['id'] == 'target'
        for table in FINANCE_TABLES:
            cursor.execute(f"SELECT business_id FROM {table} WHERE business_id = 'target'")
            assert cursor.fetchone()['business_id'] == 'target'
