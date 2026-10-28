"""Use only the disposable PostgreSQL started for this test on port 55449."""
import importlib.util
import json
import os
import time
import urllib.parse
import uuid
from concurrent.futures import ThreadPoolExecutor

import psycopg2
import pytest
from flask import Flask, request
from psycopg2.extras import RealDictCursor

from api import trello_api
from auth_encryption import decrypt_auth_data, encrypt_auth_data
from services import trello_client


DSN = 'postgresql://trello_test@127.0.0.1:55449/postgres'
BOARD = 'a' * 24
OTHER = 'b' * 24


@pytest.fixture
def pilot(monkeypatch):
    # No environment DSN: never connect to the application's configured database.
    if not os.getenv('TRELLO_TEST_DSN'):
        pytest.skip('TRELLO_TEST_DSN required for disposable PostgreSQL')
    assert os.getenv('TRELLO_TEST_DSN') == DSN
    conn = psycopg2.connect(DSN, cursor_factory=RealDictCursor)
    schema = 'trello_test_' + uuid.uuid4().hex
    cursor = conn.cursor()
    cursor.execute('CREATE SCHEMA ' + schema)
    cursor.execute('SET search_path TO ' + schema)
    cursor.execute('CREATE TABLE users(id text PRIMARY KEY,is_active boolean,is_superadmin boolean)')
    cursor.execute('CREATE TABLE businesses(id text PRIMARY KEY,owner_id text,is_active boolean)')
    cursor.execute('''CREATE TABLE usersessions(id text PRIMARY KEY,user_id text,session_kind text,
        scope_business_id text,expires_at timestamptz)''')
    cursor.execute('''CREATE TABLE externalbusinessaccounts(id text PRIMARY KEY,business_id text REFERENCES businesses(id),
        source text,display_name text,auth_data_encrypted text,is_active boolean,last_error text,
        last_sync_at timestamp,created_at timestamp,updated_at timestamp)''')
    cursor.execute("INSERT INTO users VALUES('owner',TRUE,FALSE),('foreign',TRUE,FALSE)")
    cursor.execute("INSERT INTO businesses VALUES('mine','owner',TRUE),('theirs','foreign',TRUE)")
    cursor.execute("INSERT INTO usersessions VALUES('session','owner','standard','',NOW()+INTERVAL '1 hour')")
    spec = importlib.util.spec_from_file_location('trello_migration', 'alembic_migrations/versions/20261028_trello_read_only.py')
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    monkeypatch.setattr(migration.op, 'execute', cursor.execute)
    migration.upgrade()
    migration.upgrade()
    conn.commit()
    def connect():
        return psycopg2.connect(DSN, cursor_factory=RealDictCursor, options='-csearch_path=' + schema)
    monkeypatch.setattr(trello_api, 'get_db_connection', connect)
    monkeypatch.setattr(trello_api, 'require_auth_from_request', lambda: {
        'user_id': request.headers.get('Test-User', 'owner'), 'session_id': 'session',
        'session_kind': request.headers.get('Test-Kind', 'standard'),
        'impersonating': request.headers.get('Test-Impersonating') == 'true'})
    monkeypatch.setenv('TRELLO_READ_ENABLED', 'true')
    monkeypatch.setenv('TRELLO_OAUTH_CLIENT_ID', 'test-client')
    monkeypatch.setenv('TRELLO_OAUTH_CLIENT_SECRET', 'test-secret')
    monkeypatch.setenv('TRELLO_OAUTH_REDIRECT_URI', 'http://localhost/api/trello/oauth/callback')
    monkeypatch.setenv('EXTERNAL_AUTH_SECRET_KEY', 'test-crypto')
    monkeypatch.setattr(trello_client, 'boards', lambda token: [{'id': BOARD, 'name': 'My Board'}])
    app = Flask(__name__)
    app.register_blueprint(trello_api.trello_bp)
    yield app, app.test_client(), conn, cursor
    conn.rollback()
    cursor.execute('SET search_path TO public')
    cursor.execute('DROP SCHEMA ' + schema + ' CASCADE')
    conn.commit()
    conn.close()


def credentials(expiry=None):
    return {'access_token': 'SECRET-ACCESS', 'refresh_token': 'SECRET-REFRESH',
            'expires_at': expiry if expiry is not None else time.time()+3600,
            'scope': 'read:board:trello offline_access'}


def connect_account(conn, cursor, expiry=None):
    cursor.execute("INSERT INTO externalbusinessaccounts(id,business_id,source,auth_data_encrypted,is_active) VALUES('account','mine','trello',%s,TRUE)",
                   (encrypt_auth_data(json.dumps(credentials(expiry))),))
    conn.commit()


def start(client):
    response = client.post('/api/business/mine/trello/authorize')
    assert response.status_code == 200
    return urllib.parse.parse_qs(urllib.parse.urlsplit(response.json['authorization_url']).query)['state'][0]


def test_oauth_is_browser_bound_single_use_and_does_not_expose_credentials(pilot, monkeypatch):
    app, client, conn, cursor = pilot
    exchanges = []
    def exchange(grant):
        exchanges.append(grant)
        return credentials()
    monkeypatch.setattr(trello_client, 'exchange_token', exchange)
    state = start(client)
    # A different browser cannot complete or consume this attempt.
    outsider = app.test_client()
    assert 'failed' in outsider.get('/api/trello/oauth/callback?code=code&state='+state).location
    assert exchanges == []
    result = client.get('/api/trello/oauth/callback?code=code&state='+state)
    assert 'trello_result=connected' in result.location
    assert exchanges[0]['code_verifier'] and len(exchanges) == 1
    assert 'failed' in client.get('/api/trello/oauth/callback?code=code&state='+state).location
    assert len(exchanges) == 1
    status = client.get('/api/business/mine/trello/status')
    assert status.json['connected'] is True
    assert 'SECRET' not in status.text
    cursor.execute('SELECT auth_data_encrypted FROM externalbusinessaccounts')
    assert 'SECRET' not in cursor.fetchone()['auth_data_encrypted']


@pytest.mark.parametrize('headers,business', [({'Test-User': 'foreign'}, 'mine'),
    ({}, 'theirs'), ({'Test-Kind': 'demo'}, 'mine'), ({'Test-Impersonating': 'true'}, 'mine')])
def test_business_and_session_boundary(pilot, headers, business):
    app, client, conn, cursor = pilot
    for path, method in [('status', 'GET'), ('authorize', 'POST'), ('boards', 'GET'), ('selection', 'PUT'), ('connection', 'DELETE')]:
        response = client.open('/api/business/'+business+'/trello/'+path, method=method, headers=headers)
        assert response.status_code == 403


def test_session_expiry_and_denial_do_not_save_connection(pilot, monkeypatch):
    app, client, conn, cursor = pilot
    state = start(client)
    cursor.execute("UPDATE usersessions SET expires_at=NOW()-INTERVAL '1 second'")
    conn.commit()
    assert 'failed' in client.get('/api/trello/oauth/callback?code=code&state='+state).location
    cursor.execute("UPDATE usersessions SET expires_at=NOW()+INTERVAL '1 hour'")
    conn.commit()
    state = start(client)
    assert 'denied' in client.get('/api/trello/oauth/callback?error=access_denied&state='+state).location
    cursor.execute('SELECT count(*) n FROM externalbusinessaccounts')
    assert cursor.fetchone()['n'] == 0


def test_disconnect_during_exchange_cannot_reconnect(pilot, monkeypatch):
    app, client, conn, cursor = pilot
    state = start(client)
    def exchange(grant):
        assert app.test_client().delete('/api/business/mine/trello/connection').status_code == 200
        return credentials()
    monkeypatch.setattr(trello_client, 'exchange_token', exchange)
    assert 'failed' in client.get('/api/trello/oauth/callback?code=code&state='+state).location
    cursor.execute('SELECT count(*) n FROM externalbusinessaccounts')
    assert cursor.fetchone()['n'] == 0


def test_refresh_rotation_commits_even_when_later_read_fails(pilot, monkeypatch):
    app, client, conn, cursor = pilot
    connect_account(conn, cursor, 0)
    fresh = {**credentials(), 'refresh_token': 'ROTATED'}
    monkeypatch.setattr(trello_client, 'exchange_token', lambda grant: fresh)
    def fail(token):
        raise trello_client.TrelloError('provider_unavailable', 'Try later', 502)
    monkeypatch.setattr(trello_client, 'boards', fail)
    assert client.get('/api/business/mine/trello/boards').status_code == 502
    cursor.execute("SELECT auth_data_encrypted FROM externalbusinessaccounts WHERE id='account'")
    saved = json.loads(decrypt_auth_data(cursor.fetchone()['auth_data_encrypted']))
    assert saved['refresh_token'] == 'ROTATED'


def test_concurrent_reads_only_refresh_once(pilot, monkeypatch):
    app, client, conn, cursor = pilot
    connect_account(conn, cursor, 0)
    calls = []
    def exchange(grant):
        calls.append(grant)
        time.sleep(.05)
        return credentials()
    monkeypatch.setattr(trello_client, 'exchange_token', exchange)
    def read(_):
        return app.test_client().get('/api/business/mine/trello/boards').status_code
    pool = ThreadPoolExecutor(max_workers=2)
    try:
        assert list(pool.map(read, [1, 2])) == [200, 200]
    finally:
        pool.shutdown()
    assert len(calls) == 1


def test_selection_sync_and_disconnect_are_local_only(pilot, monkeypatch):
    app, client, conn, cursor = pilot
    connect_account(conn, cursor)
    assert client.put('/api/business/mine/trello/selection', json={'board_ids': [OTHER]}).status_code == 403
    assert client.post('/api/business/mine/trello/boards/'+BOARD+'/sync').status_code == 403
    assert client.put('/api/business/mine/trello/selection', json={'board_ids': [BOARD]}).status_code == 200
    complete = {'board': {'id': BOARD, 'name': 'Saved'}, 'lists': [], 'cards': [], 'complete': True}
    monkeypatch.setattr(trello_client, 'board_snapshot', lambda token, board_id: complete)
    assert client.post('/api/business/mine/trello/boards/'+BOARD+'/sync').status_code == 200
    assert client.get('/api/business/mine/trello/boards/'+BOARD+'/snapshot').json['snapshot'] == complete
    def fail(*args):
        raise trello_client.TrelloError('incomplete_snapshot', 'incomplete', 502)
    monkeypatch.setattr(trello_client, 'board_snapshot', fail)
    assert client.post('/api/business/mine/trello/boards/'+BOARD+'/sync').status_code == 502
    assert client.get('/api/business/mine/trello/boards/'+BOARD+'/snapshot').json['snapshot'] == complete
    assert client.delete('/api/business/mine/trello/connection').status_code == 200
    assert client.get('/api/business/mine/trello/status').json['connected'] is False
    cursor.execute('SELECT count(*) n FROM trello_board_snapshots')
    assert cursor.fetchone()['n'] == 0
    cursor.execute('SELECT auth_data_encrypted FROM externalbusinessaccounts')
    assert cursor.fetchone()['auth_data_encrypted'] is None


def test_revoked_access_hides_cached_snapshot(pilot, monkeypatch):
    app, client, conn, cursor = pilot
    connect_account(conn, cursor)
    cursor.execute("INSERT INTO trello_board_snapshots VALUES('account',%s,'Private',%s,NOW())", (BOARD, json.dumps({'private': True})))
    conn.commit()
    def denied(token):
        raise trello_client.TrelloError('reauthorization_required', 'Reconnect', 401)
    monkeypatch.setattr(trello_client, 'boards', denied)
    assert client.get('/api/business/mine/trello/boards').status_code == 401
    response = client.get('/api/business/mine/trello/boards/'+BOARD+'/snapshot')
    assert response.status_code == 409 and 'private' not in response.text


def test_missing_board_membership_removes_private_cache(pilot, monkeypatch):
    app, client, conn, cursor = pilot
    connect_account(conn, cursor)
    cursor.execute("INSERT INTO trello_board_snapshots VALUES('account',%s,'Private',%s,NOW())", (BOARD, json.dumps({'private': True})))
    conn.commit()
    monkeypatch.setattr(trello_client, 'boards', lambda token: [])
    response = client.get('/api/business/mine/trello/boards/'+BOARD+'/snapshot')
    assert response.status_code == 403 and 'private' not in response.text
    cursor.execute('SELECT count(*) n FROM trello_board_snapshots')
    assert cursor.fetchone()['n'] == 0


def test_disabled_flag_does_not_offer_oauth(pilot, monkeypatch):
    app, client, conn, cursor = pilot
    monkeypatch.setenv('TRELLO_READ_ENABLED', 'false')
    assert client.get('/api/business/mine/trello/status').json['enabled'] is False
    assert client.post('/api/business/mine/trello/authorize').status_code == 503


def test_corrupt_credentials_offer_reconnection_instead_of_retry_loop(pilot):
    app, client, conn, cursor = pilot
    connect_account(conn, cursor)
    cursor.execute('UPDATE externalbusinessaccounts SET auth_data_encrypted=%s', (encrypt_auth_data('[]'),))
    conn.commit()
    assert client.get('/api/business/mine/trello/boards').status_code == 409
    assert client.get('/api/business/mine/trello/status').json['needs_reauthorization'] is True
