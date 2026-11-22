"""Real web/bot entrypoints, synthetic PostgreSQL journals and loopback LLM HTTP."""

import asyncio
import importlib.util
import json
import os
import re
import socket
import time
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from cryptography.fernet import Fernet

from tests.test_pii_protection import mock_provider, integrated
from services.pii_protection.engines import EngineResult, Finding
from services.pii_protection.gateway import MemoryStore, ProtectionService, Scope, TOKEN
from services.llm.contracts import LLMTaskDefinition


BID, UID = 'synthetic-business', 'synthetic-user'
PRIVATE = ('Mira Exampleton', 'mira@example.invalid')
PUBLIC = 'Louis Vuitton'


@pytest.fixture
def scope():
    return Scope(BID, UID, 'synthetic-session')


@pytest.fixture
def service():
    if os.getenv('PII_SYNTHETIC_RUNTIME_TEST') == '1':
        from services.pii_protection.remote import RemoteProtectionService
        from services.pii_protection.runtime_config import CLIENT_CONFIG
        client = RemoteProtectionService.from_file(CLIENT_CONFIG)
        original = client.protect
        last = [0.0]
        def paced(*args, **kwargs):
            time.sleep(max(0, 0.28 - (time.monotonic() - last[0])))
            last[0] = time.monotonic()
            return original(*args, **kwargs)
        client.protect = paced
        return client
    class Engine:
        def scan(self, text):
            findings = [Finding(match.start(), match.end(), kind)
                        for value, kind in [(PRIVATE[0], 'PERSON'), (PRIVATE[1], 'EMAIL'), (PUBLIC, 'PERSON')]
                        for match in re.finditer(re.escape(value), text)]
            return EngineResult(text, findings)
    return ProtectionService(Engine(), MemoryStore(), Fernet.generate_key())


@pytest.fixture(autouse=True)
def isolated_network(monkeypatch):
    monkeypatch.setenv('PYTHON_DOTENV_DISABLED', '1')
    connect, lookup = socket.socket.connect, socket.getaddrinfo
    allowed = {'127.0.0.1'}
    for host in ['localos-pii-runtime', 'pii-acceptance-postgres']:
        try:
            allowed.update(item[4][0] for item in lookup(host, None, type=socket.SOCK_STREAM))
        except socket.gaierror:
            pass
    def checked(connection, address):
        if isinstance(address, tuple) and address[0] not in allowed:
            raise AssertionError('External network is forbidden in synthetic acceptance')
        return connect(connection, address)
    monkeypatch.setattr(socket.socket, 'connect', checked)


@pytest.fixture(autouse=True)
def scoped_activation(tmp_path, monkeypatch):
    if os.getenv('PII_ACCEPTANCE_ACTIVATION_PROFILE') != 'operator_text':
        return
    path = tmp_path/'activation.json'
    path.write_text(json.dumps({'version': 1, 'enabled': True, 'scope': 'operator_text', 'mode': 'enforce'}))
    path.chmod(0o600)
    monkeypatch.setenv('PII_ACTIVATION_CONFIG_FILE', str(path))
    monkeypatch.setenv('PII_ACTIVATION_REQUIRED', 'true')


@pytest.fixture
def database(monkeypatch):
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from urllib.parse import urlsplit
    dsn = os.getenv('PII_ACCEPTANCE_TEST_DSN')
    if not dsn:
        pytest.skip('PII_ACCEPTANCE_TEST_DSN must select the disposable synthetic database')
    url = urlsplit(dsn)
    if (url.hostname not in {'127.0.0.1', 'pii-acceptance-postgres'} or url.path != '/pii_synthetic'
            or url.username != 'synthetic' or url.port not in {15439, 5432}):
        raise RuntimeError('Only the disposable synthetic database is permitted')
    conn = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    schema = 'pii_synthetic_' + uuid.uuid4().hex
    c = conn.cursor()
    c.execute('CREATE SCHEMA ' + schema)
    c.execute('SET search_path TO ' + schema)
    c.execute('CREATE TABLE users(id TEXT PRIMARY KEY,is_active BOOLEAN,is_superadmin BOOLEAN)')
    c.execute('''CREATE TABLE businesses(id TEXT PRIMARY KEY,owner_id TEXT,network_id TEXT,is_active BOOLEAN,
                 subscription_tier TEXT,subscription_status TEXT,subscription_ends_at TIMESTAMPTZ)''')
    c.execute('CREATE TABLE networks(id TEXT PRIMARY KEY,owner_id TEXT)')
    c.execute('CREATE TABLE business_members(business_id TEXT,user_id TEXT,status TEXT,role TEXT)')
    c.execute('CREATE TABLE network_members(network_id TEXT,user_id TEXT,status TEXT,role TEXT)')
    c.execute('CREATE TABLE cards(id TEXT,business_id TEXT,url TEXT,title TEXT,address TEXT,created_at TIMESTAMPTZ DEFAULT NOW())')
    c.execute('CREATE TABLE businessmaplinks(business_id TEXT,url TEXT)')
    c.execute('INSERT INTO users VALUES (%s,TRUE,FALSE),(%s,TRUE,FALSE)', (UID, 'synthetic-other'))
    c.execute("INSERT INTO businesses VALUES (%s,%s,NULL,TRUE,'elite','active',NOW()+INTERVAL '1 year')", (BID, UID))
    c.execute('INSERT INTO cards(id,business_id,url,title,address) VALUES (%s,%s,%s,%s,%s)',
              ('synthetic-card', BID, 'https://yandex.ru/maps/org/123/', PUBLIC, 'Пушкинская улица, 1'))
    c.execute('INSERT INTO businessmaplinks VALUES (%s,%s)', (BID, 'https://yandex.ru/maps/org/123/'))
    c.execute('INSERT INTO cards(id,business_id,url,title) VALUES (%s,%s,%s,%s)',
              ('synthetic-foreign', 'synthetic-foreign-business', 'https://yandex.ru/maps/org/321/', 'Foreign Unapproved Brand'))
    from alembic import op
    monkeypatch.setattr(op, 'execute', c.execute)
    path = Path(__file__).parents[1] / 'alembic_migrations/versions/20260711_add_operator_conversations.py'
    spec = importlib.util.spec_from_file_location('pii_synthetic_conversations', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.upgrade()
    c.execute('ALTER TABLE operatoractions ADD COLUMN expires_at TIMESTAMPTZ')
    c.execute('''CREATE TABLE operator_chat_requests(user_id TEXT,business_id TEXT,channel TEXT,request_id TEXT,
                 input_hash TEXT,result_json JSONB,PRIMARY KEY(user_id,business_id,channel,request_id))''')
    for channel in ['web', 'telegram']:
        c.execute('INSERT INTO operatorconversations(id,business_id,user_id,channel) VALUES (%s,%s,%s,%s)',
                  ('synthetic-' + channel + '-' + uuid.uuid4().hex, BID, UID, channel))
    conn.commit()
    from services import operator_request_history
    monkeypatch.setattr(operator_request_history, 'enabled', lambda *_: False)
    monkeypatch.setenv('OPERATOR_WORKDAY_ENABLED', 'false')
    monkeypatch.setenv('OPERATOR_REQUEST_HISTORY_ENABLED', 'false')
    class Connection:
        def cursor(self):
            return conn.cursor()
        def commit(self):
            conn.commit()
        def rollback(self):
            conn.rollback()
        def close(self):
            pass
    yield conn, c, Connection()
    conn.rollback()
    c.execute('DROP SCHEMA ' + schema + ' CASCADE')
    conn.commit()
    conn.close()


@pytest.fixture
def routes(database, integrated, monkeypatch):
    from flask import Flask
    from api import operator_api
    from services import operator_core, operator_tool_loop, telegram_dashboard
    conn, c, proxy = database
    gateway, request, captured, behavior = integrated
    monkeypatch.setattr(gateway, 'get_task_definition', lambda _: LLMTaskDefinition(
        'operator_tool_plan', 'deepseek', 'deepseek_reasoning', 'business_internal', response_kind='json'))
    calls = []
    tools = [
        {'name': 'communications.draft', 'risk_class': 'draft_only', 'approval_required': False,
         'explicit_intent_markers': ('подготов',), 'input_schema': {'type': 'object', 'properties': {'message': {'type': 'string'}}, 'required': ['message']},
         'execute': lambda args: calls.append(('draft', args)) or {'status': 'completed', 'draft': {'id': 'synthetic-draft'}, 'external_writes_performed': False}},
        {'name': 'communications.prepare_send', 'risk_class': 'external_send_request', 'approval_required': True,
         'explicit_intent_markers': ('отправ',), 'input_schema': {'type': 'object', 'properties': {'message': {'type': 'string'}, 'audience': {'type': 'string'}}},
         'prepare_approval': lambda args: calls.append(('preview', args)) or {'status': 'approval_required', 'chat_response': 'Проверьте черновик',
             'approval': {'envelope': args}, 'external_writes_performed': False}},
    ]
    selected = [operator_core._normalize_tool_contract(tool, business_id=BID) for tool in tools]
    monkeypatch.setattr(operator_core, '_operator_tool_catalog', lambda *args, **kwargs: selected)
    from services import finance_daily
    monkeypatch.setattr(finance_daily, 'settings', lambda *args: {'timezone': 'Europe/Moscow'})
    def router(cursor, **args):
        # Real routing and planner; the model/provider and domain side effects
        # terminate at synthetic boundaries. No production billing or sends.
        return operator_core.route_operator_message(cursor, tool_planner=operator_tool_loop.plan_operator_step, **args)
    monkeypatch.setattr(operator_api, 'route_operator_message', router)
    monkeypatch.setattr(telegram_dashboard, 'route_operator_message', router)
    class DB:
        def __init__(self):
            self.conn = proxy
        def close(self):
            pass
    monkeypatch.setattr(operator_api, 'DatabaseManager', DB)
    monkeypatch.setattr(operator_api, 'require_auth_from_request', lambda: {'user_id': UID, 'id': UID})
    from subscription_manager import build_subscription_capabilities, capability_access_payload
    access = build_subscription_capabilities(business_id=BID, tier='elite', status='active')
    monkeypatch.setattr(operator_api, '_scope_capability_access', lambda *args: capability_access_payload(access, 'operator'))
    monkeypatch.setattr(operator_api, '_scope_subscription_access', lambda *args: access)
    monkeypatch.setattr(operator_api, 'record_operator_event', lambda *args, **kwargs: None)
    monkeypatch.setattr(telegram_dashboard, 'get_db_connection', lambda: proxy)
    monkeypatch.setattr(telegram_dashboard, 'record_operator_event', lambda *args, **kwargs: None)
    app = Flask('pii-synthetic-acceptance')
    app.register_blueprint(operator_api.operator_bp)
    return app.test_client(), telegram_dashboard, captured, behavior, calls


def send(routes, channel, text, request_id='synthetic-request', extra=None):
    client, dashboard, captured, behavior, calls = routes
    if channel == 'web':
        response = client.post('/api/operator/chat', json={'business_id': BID, 'message': text, 'request_id': request_id, **(extra or {})})
        assert response.status_code == 200
        return response.get_json()['operator_result']
    return dashboard.build_operator_chat_payload({'business_id': BID, 'user_id': UID,
        'operator_payload': {'request_id': request_id, **(extra or {})}}, text)['result']


@pytest.mark.parametrize('channel', ['web', 'telegram'])
@pytest.mark.parametrize('scenario', ['display', 'draft', 'approval', 'forbidden_field'])
def test_complete_text_journal_privacy_and_replay(routes, database, channel, scenario):
    client, dashboard, captured, behavior, calls = routes
    step = [0]
    def reply(prompt):
        assert all(value not in prompt for value in PRIVATE)
        assert PUBLIC in prompt and 'Foreign Unapproved Brand' not in prompt
        tokens = TOKEN.findall(prompt)
        assert tokens
        if step[0] == 0 and scenario != 'display':
            step[0] += 1
            args = {'message': ' '.join(tokens)}
            if scenario == 'forbidden_field':
                args['audience'] = tokens[0]
            return json.dumps({'action': 'tool_call', 'tool': 'communications.draft' if scenario == 'draft' else 'communications.prepare_send',
                               'arguments': args, 'remaining_actions': []})
        return json.dumps({'action': 'final', 'message': 'Ответ: ' + ' '.join(tokens), 'remaining_actions': []})
    behavior['reply'] = reply
    message = 'Подготовь отправку контактного черновика: Full name: Mira Exampleton; email: mira@example.invalid'
    result = send(routes, channel, message, extra={'pii_public_context': [{'value': PRIVATE[0]}]})
    size = len(captured)
    repeated = send(routes, channel, message, extra={'pii_public_context': [{'value': PRIVATE[0]}]})
    assert len(captured) == size and repeated['message_id'] == result['message_id']
    assert result['external_writes_performed'] is False
    if scenario == 'approval':
        assert result['status'] == 'approval_required' and calls[0][0] == 'preview'
        assert all(value in calls[0][1]['message'] for value in PRIVATE)
        database[1].execute('SELECT envelope_json FROM operatoractions')
        envelope = database[1].fetchone()['envelope_json']
        assert all(value in json.dumps(envelope) for value in PRIVATE)
    elif scenario == 'forbidden_field':
        assert calls == []
        assert any(b'pii_tool_restore_denied' in item for item in captured)
    else:
        assert result['status'] == 'completed'
        assert all(value in result['chat_response'] for value in PRIVATE)
        if scenario == 'draft':
            assert all(value in calls[0][1]['message'] for value in PRIVATE)
    from services.pii_protection.operator_context import PUBLIC_CARDS
    assert PUBLIC_CARDS.get() is None


def test_web_denies_foreign_actor_before_journal_or_model(routes, database, monkeypatch):
    from api import operator_api
    monkeypatch.setattr(operator_api, 'require_auth_from_request', lambda: {'user_id': 'synthetic-other'})
    response = routes[0].post('/api/operator/chat', json={'business_id': BID, 'message': 'Full name: Mira Exampleton'})
    assert response.status_code == 403 and routes[2] == []
    database[1].execute('SELECT COUNT(*) n FROM operatormessages')
    assert database[1].fetchone()['n'] == 0


def test_overload_blocks_before_provider_and_shows_retry_message(routes, service, monkeypatch):
    from services.pii_protection.gateway import PIIProtectionError
    def limited(*args, **kwargs):
        raise PIIProtectionError('PII_RUNTIME_RATE_LIMITED')
    monkeypatch.setattr(service, 'protect', limited)
    result = send(routes, 'web', 'Full name: Mira Exampleton; email: mira@example.invalid')
    assert routes[2] == [] and result['planner_failed']
    assert 'позже' in result['chat_response'] and result['external_writes_performed'] is False


def test_disabled_shared_chat_does_not_load_public_records(database, monkeypatch):
    from services import operator_chat_service
    from services.pii_protection import operator_context
    monkeypatch.setenv('PII_PROTECTION_ENABLED', 'false')
    path = os.getenv('PII_ACTIVATION_CONFIG_FILE')
    if path and Path(path).is_file():
        value = json.loads(Path(path).read_text());value['enabled'] = False;Path(path).write_text(json.dumps(value))
    def forbidden(*args, **kwargs):
        pytest.fail('The disabled integration must not read public records')
    monkeypatch.setattr(operator_context, 'load_public_cards', forbidden)
    result = operator_chat_service.process_chat(database[1], business_id=BID, user_id=UID, channel='web',
        message='synthetic legacy', router=lambda *args, **kwargs: ({'status': 'completed', 'chat_response': 'legacy'}, {}))
    assert result['chat_response'] == 'legacy'


def test_actual_bot_text_handler_returns_restored_reply_without_telegram_io(routes, monkeypatch):
    import telegram_bot
    from services import operator_telegram_voice, operator_request_history
    async def skip(*args, **kwargs):
        return False
    monkeypatch.setattr(operator_telegram_voice, 'correction', skip)
    monkeypatch.setattr(operator_request_history, 'mark_delivery', lambda *args: None)
    monkeypatch.setattr(telegram_bot, '_telegram_agent_message_decision', lambda _: {'allow_normal_routing': True})
    monkeypatch.setattr(telegram_bot, '_is_bound_user', lambda _: True)
    monkeypatch.setattr(telegram_bot, '_resolve_telegram_control_scope', lambda _: {'kind': 'business', 'id': BID})
    monkeypatch.setattr(telegram_bot, '_control_scope_business_context', lambda *args: {'business_id': BID, 'user_id': UID})
    telegram_bot.user_states['900001'] = {'state': 'idle'}
    routes[3]['reply'] = lambda prompt: json.dumps({'action': 'final', 'message': 'Ответ: ' + ' '.join(TOKEN.findall(prompt)), 'remaining_actions': []})
    message = SimpleNamespace(text='Full name: Mira Exampleton; email: mira@example.invalid',
                              message_id=101, reply_to_message=None, reply_text=AsyncMock())
    update = SimpleNamespace(effective_user=SimpleNamespace(id=900001, full_name='Synthetic User'),
                             effective_chat=SimpleNamespace(id=900001), message=message, effective_message=message)
    asyncio.run(telegram_bot.handle_text(update, SimpleNamespace()))
    assert message.reply_text.await_count == 1
    reply = message.reply_text.await_args.args[0]
    assert all(value in reply for value in PRIVATE)
    assert routes[2] and all(all(value.encode() not in body for value in PRIVATE) for body in routes[2])
