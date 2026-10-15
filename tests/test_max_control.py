import hashlib
import hmac
import json
from urllib.parse import urlencode

import pytest
import requests
from flask import Flask

from services.max_webapp_auth import validate_max_init_data
from services.max_transport import MaxTransport, MaxTransportError
from services.max_publication import probe_channel
from api import max_api


def signed_launch(**overrides):
    values = {'auth_date': '1700000000', 'user': json.dumps({'id': 123, 'first_name': 'Test'})}
    values.update(overrides)
    check = '\n'.join(f'{key}={values[key]}' for key in sorted(values))
    secret = hmac.new(b'WebAppData', b'synthetic-max-token', hashlib.sha256).digest()
    values['hash'] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(values)


def test_signed_max_identity_and_expiry():
    raw = signed_launch()
    assert validate_max_init_data(raw, bot_token='synthetic-max-token', now=1700000100)['max_id'] == '123'
    assert validate_max_init_data(raw, bot_token='other-token', now=1700000100) is None
    assert validate_max_init_data(raw, bot_token='synthetic-max-token', now=1700004000) is None
    assert validate_max_init_data(raw, bot_token='synthetic-max-token', now=1699999999) is None
    assert validate_max_init_data(raw + '&auth_date=1700000001', bot_token='synthetic-max-token', now=1700000100) is None
    assert validate_max_init_data(raw + '&hash=other', bot_token='synthetic-max-token', now=1700000100) is None


@pytest.mark.parametrize('user', ['[]', '{}', '{"id":true}', '{"id":"123"}', '{"id":-1}', 'null', 'broken'])
def test_invalid_signed_user_is_rejected(user):
    assert validate_max_init_data(signed_launch(user=user), bot_token='synthetic-max-token', now=1700000100) is None


class Cursor:
    def __init__(self):
        self.rows = []
        self.keys = set()
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if 'INSERT INTO max_webhook_events' in sql:
            self.keys.add(params[0])

    def fetchone(self):
        return self.rows[0] if self.rows else None


class DB:
    def __init__(self):
        self.conn = self
        self.cursor_value = Cursor()
        self.commits = 0
        self.rollbacks = 0

    def cursor(self): return self.cursor_value
    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1
    def close(self): pass


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('MAX_ENABLED', 'true')
    monkeypatch.setenv('MAX_WEBHOOK_SECRET', 'synthetic-webhook-secret')
    app = Flask(__name__)
    app.register_blueprint(max_api.max_bp)
    return app.test_client()


def test_webhook_auth_and_disabled_gate_do_not_open_database(client, monkeypatch):
    monkeypatch.setattr(max_api, 'DatabaseManager', lambda: pytest.fail('DB must not be opened'))
    assert client.post('/api/max/webhook', json={}).status_code == 403
    monkeypatch.setenv('MAX_ENABLED', 'false')
    assert client.post('/api/max/webhook', json={}).status_code == 503


def test_webhook_commits_before_ack_and_deduplicates_provider_mid(client, monkeypatch):
    db = DB()
    monkeypatch.setattr(max_api, 'DatabaseManager', lambda: db)
    headers = {'X-Max-Bot-Api-Secret': 'synthetic-webhook-secret'}
    event = {'update_type': 'message_created', 'timestamp': 100, 'message': {'body': {'mid': 'mid-1', 'text': 'hello'}}}
    assert client.post('/api/max/webhook', headers=headers, json=event).status_code == 200
    event['timestamp'] = 200
    assert client.post('/api/max/webhook', headers=headers, json=event).status_code == 200
    assert db.commits == 2 and len(db.cursor_value.keys) == 1


def test_webhook_never_accepts_internal_notification_events(client, monkeypatch):
    monkeypatch.setattr(max_api, 'DatabaseManager', lambda: pytest.fail('DB must not be opened'))
    assert client.post('/api/max/webhook', headers={'X-Max-Bot-Api-Secret': 'synthetic-webhook-secret'},
                       json={'update_type': 'localos_notification', 'max_id': '123'}).status_code == 400


def test_webhook_failure_rolls_back_and_does_not_ack(client, monkeypatch):
    db = DB()
    def fail(): raise RuntimeError('synthetic storage failure')
    db.commit = fail
    monkeypatch.setattr(max_api, 'DatabaseManager', lambda: db)
    response = client.post('/api/max/webhook', headers={'X-Max-Bot-Api-Secret': 'synthetic-webhook-secret'}, json={'update_type': 'bot_started'})
    assert response.status_code == 500 and db.rollbacks >= 1


def test_transport_timeout_is_uncertain_and_not_retried():
    class Session:
        calls = 0
        def request(self, *args, **kwargs):
            self.calls += 1
            assert kwargs['allow_redirects'] is False
            assert kwargs['headers'] == {'Authorization': 'synthetic-secret'}
            raise requests.Timeout('sensitive request details')
    session = Session()
    caught = pytest.raises(MaxTransportError, MaxTransport('synthetic-secret', session=session).send, '123', 'hello')
    assert caught.value.uncertain and session.calls == 1
    assert 'synthetic-secret' not in str(caught.value) and 'sensitive' not in str(caught.value)


def test_probe_requires_actual_bot_write_permission():
    class Transport:
        def call(self, method, path):
            if path == '/me': return {'user_id': 1, 'is_bot': True}
            if path.endswith('/members/me'): return {'user_id': 1, 'is_admin': True, 'permissions': self.permissions}
            return {'chat_id': -123, 'type': 'channel', 'title': 'Test channel'}
    transport = Transport()
    transport.permissions = ['read_all_messages']
    with pytest.raises(PermissionError): probe_channel(transport, '-123')
    transport.permissions = ['write']
    assert probe_channel(transport, '-123')['bot_id'] == '1'


def test_max_preferences_never_write_telegram_storage():
    from services.telegram_control_scope import save_control_scope
    class PreferencesCursor(Cursor):
        def execute(self, sql, params=()):
            super().execute(sql, params)
            self.rows = [{'table_ref': None}] if 'to_regclass' in sql else []
    cursor = PreferencesCursor()
    save_control_scope(cursor, user_id='u', telegram_id='123', platform='max', scope={'kind': 'business', 'id': 'b', 'name': 'Test'})
    assert any('INSERT INTO maxcontrolpreferences' in sql for sql, _ in cursor.calls)
    assert all('telegramcontrolpreferences' not in sql for sql, _ in cursor.calls)
    with pytest.raises(ValueError):
        save_control_scope(cursor, user_id='u', telegram_id='123', platform='max; DROP TABLE users', scope={'kind': 'business'})


@pytest.mark.parametrize('body', [{'success': False}, {'code': 'bad.request', 'message': 'Sensitive provider text'}])
def test_transport_rejects_error_envelope_without_leaking_provider_text(body):
    class Response:
        status_code = 200
        def json(self): return body
    class Session:
        def request(self, *args, **kwargs): return Response()
    caught = pytest.raises(MaxTransportError, MaxTransport('synthetic', session=Session()).call, 'POST', '/answers')
    assert str(caught.value) == 'max_api_rejected' and not caught.value.uncertain


def test_max_menu_covers_every_registered_telegram_command():
    import ast
    from pathlib import Path
    from services.mobile_bot_menu import MAX_COMMANDS
    tree = ast.parse((Path(__file__).parents[1] / 'src/telegram_bot.py').read_text())
    telegram_commands = {node.args[0].value for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'CommandHandler'
        and node.args and isinstance(node.args[0], ast.Constant)}
    assert telegram_commands == {name for name, _ in MAX_COMMANDS}


def test_durable_inbox_redacts_link_code_and_ignores_supplied_internal_hash(client, monkeypatch):
    db = DB()
    monkeypatch.setattr(max_api, 'DatabaseManager', lambda: db)
    code = 'synthetic-once-code-' + 'x' * 32
    event = {'update_type': 'message_created', '_localos_link_hash': 'forged', 'message': {
        'body': {'mid': 'link-1', 'text': '/link ' + code}}}
    result = client.post('/api/max/webhook', headers={'X-Max-Bot-Api-Secret': 'synthetic-webhook-secret'}, json=event)
    assert result.status_code == 200
    saved = db.cursor_value.calls[-1][1][1].adapted
    assert code not in json.dumps(saved)
    assert saved['_localos_link_hash'] == hashlib.sha256(code.encode()).hexdigest()
    assert saved['message']['body']['text'] == '/link [redacted]'
