"""Run against an isolated PostgreSQL, never the application database."""
import os
from types import SimpleNamespace
from unittest.mock import Mock

import psycopg2
import pytest

from services.openclaw_website_reader import read_business_website


def test_real_postgres_rights_and_source_roundtrip(tmp_path, monkeypatch):
    dsn = os.getenv('OPENCLAW_TEST_POSTGRES_DSN')
    if not dsn:
        pytest.fail('An isolated PostgreSQL DSN is required, not a skipped integration check')
    conn = psycopg2.connect(dsn)
    try:
        cursor = conn.cursor()
        # Temporary relations shadow production names, transaction rolls back.
        cursor.execute('CREATE TEMP TABLE users (id TEXT, is_superadmin BOOLEAN)')
        cursor.execute('CREATE TEMP TABLE businesses (id TEXT, owner_id TEXT)')
        cursor.execute("INSERT INTO users VALUES ('owner', FALSE), ('outsider', FALSE)")
        cursor.execute("INSERT INTO businesses VALUES ('branch', 'owner')")
        config = tmp_path / 'reader.json'
        config.write_text('{"enabled":true,"business_ids":["branch"]}')
        monkeypatch.setenv('LOCALOS_WEB_READ_CONFIG', str(config))
        monkeypatch.setenv('OPENCLAW_SANDBOX_BRIDGE_URL', 'http://bridge:8091/capabilities')
        monkeypatch.setenv('OPENCLAW_SANDBOX_BRIDGE_TOKEN', 'test-only')
        monkeypatch.setattr('core.outbound_network.validate_public_http_url', lambda value: value)
        source = {'url': 'https://example.com', 'final_url': 'https://example.com',
                  'fetched_at': '2026-10-12T10:00:00Z', 'untrusted': True, 'text': 'facts'}
        transport = Mock(return_value=SimpleNamespace(status_code=200,
            json=lambda: {'ok': True, 'source': source}))
        monkeypatch.setattr('services.openclaw_website_reader.requests.post', transport)
        with pytest.raises(PermissionError):
            read_business_website(cursor, 'outsider', 'branch', source['url'])
        transport.assert_not_called()
        result = read_business_website(cursor, 'owner', 'branch', source['url'])
        from psycopg2.extras import Json
        cursor.execute('CREATE TEMP TABLE draft_metadata (id TEXT PRIMARY KEY, metadata JSONB)')
        cursor.execute('INSERT INTO draft_metadata VALUES (%s, %s)', ('item', Json(result)))
        cursor.execute("SELECT metadata->>'text', metadata->>'untrusted' FROM draft_metadata WHERE id='item'")
        assert cursor.fetchone() == ('facts', 'true')
    finally:
        conn.rollback()
        conn.close()
