"""Client boundaries plus durable writes, using only disposable local PostgreSQL."""
import importlib.util
import json
import os
import uuid

import psycopg2
import pytest
import requests
from flask import Flask, request
from psycopg2.extras import RealDictCursor
from api import yougile_api
from auth_encryption import decrypt_auth_data
from services import yougile_client, yougile_tasks

DSN = 'postgresql://yougile_test@127.0.0.1:55531/postgres'
PROJECT, BOARD, COLUMN, USER, TASK, FOREIGN = [str(uuid.UUID(int=n)) for n in range(1, 7)]
SECRET = 'client-secret-not-to-be-returned'


@pytest.fixture
def pilot(monkeypatch):
    if not os.getenv('YOUGILE_TEST_DSN'):
        pytest.skip('YOUGILE_TEST_DSN required for disposable local PostgreSQL')
    assert os.environ['YOUGILE_TEST_DSN'] == DSN
    schema = 'yougile_test_' + uuid.uuid4().hex
    admin = psycopg2.connect(DSN, cursor_factory=RealDictCursor)
    q = admin.cursor()
    q.execute('CREATE SCHEMA ' + schema)
    q.execute('SET search_path TO ' + schema)
    q.execute('CREATE TABLE users(id text PRIMARY KEY,is_active boolean,is_superadmin boolean)')
    q.execute('CREATE TABLE businesses(id text PRIMARY KEY,owner_id text,network_id text,is_active boolean)')
    q.execute('CREATE TABLE business_members(business_id text,user_id text,role text,status text)')
    q.execute('CREATE TABLE network_members(network_id text,user_id text,role text,status text)')
    q.execute('CREATE TABLE networks(id text,owner_id text)')
    q.execute('''CREATE TABLE externalbusinessaccounts(id text PRIMARY KEY,business_id text REFERENCES businesses(id),
        source text,auth_data_encrypted text,is_active boolean,last_error text,created_at timestamp,updated_at timestamp)''')
    q.execute("INSERT INTO users VALUES('owner',TRUE,FALSE),('other',TRUE,FALSE),('manager',TRUE,FALSE),('viewer',TRUE,FALSE)")
    q.execute("INSERT INTO businesses VALUES('mine','owner',NULL,TRUE),('theirs','other',NULL,TRUE)")
    q.execute("INSERT INTO business_members VALUES('mine','manager','manager','active'),('mine','viewer','viewer','active')")
    spec = importlib.util.spec_from_file_location('yougile_migration', 'alembic_migrations/versions/20261031_yougile_tasks.py')
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    monkeypatch.setattr(migration.op, 'execute', q.execute)
    migration.upgrade(); migration.upgrade()
    admin.commit()
    def connect():
        return psycopg2.connect(DSN, cursor_factory=RealDictCursor, options='-csearch_path=' + schema)
    monkeypatch.setattr(yougile_api, 'get_db_connection', connect)
    monkeypatch.setattr(yougile_tasks, 'get_db_connection', connect)
    monkeypatch.setattr(yougile_api, 'require_auth_from_request', lambda: None if request.headers.get('Test-User') == 'anonymous' else {
        'user_id': request.headers.get('Test-User', 'owner'), 'session_kind': request.headers.get('Test-Kind', 'standard'),
        'impersonating': request.headers.get('Test-Impersonating') == 'true'})
    monkeypatch.setenv('YOUGILE_CLIENT_ENABLED', 'true')
    monkeypatch.setenv('EXTERNAL_AUTH_SECRET_KEY', 'isolated-test-key')
    calls, tasks = [], {}
    state = {'fail_after_write': False, 'foreign_board': False, 'readback_failed': False}
    def provider(token, method, path, payload=None, params=None):
        assert token == SECRET
        calls.append((method, path, payload))
        if path == '/users/me': return {'id': USER}
        if path == '/projects/' + PROJECT: return {'id': PROJECT, 'title': 'Команда', 'users': {USER: 'worker'}}
        if path == '/boards/' + BOARD: return {'id': BOARD, 'title': 'Поручения', 'projectId': FOREIGN if state['foreign_board'] else PROJECT}
        if path == '/columns/' + COLUMN: return {'id': COLUMN, 'title': 'Новые', 'boardId': BOARD}
        if path == '/columns/' + FOREIGN: return {'id': FOREIGN, 'title': 'Чужая колонка', 'boardId': FOREIGN}
        if path == '/tasks/' + FOREIGN: return {'id': FOREIGN, 'title': 'Чужая задача', 'columnId': FOREIGN}
        if method == 'POST' and path == '/tasks':
            tasks[TASK] = {'id': TASK, 'completed': False, 'archived': False, **payload}
            if state['fail_after_write']:
                raise yougile_client.YouGileError('unknown_result', 'Результат неизвестен.', 502)
            return {'id': TASK}
        if path == '/tasks/' + TASK:
            if method == 'PUT': tasks[TASK].update(payload); return {'id': TASK}
            if state['readback_failed']:
                raise yougile_client.YouGileError('provider_unavailable', 'Временно недоступно.', 502)
            return tasks[TASK]
        if path == '/projects': rows = [{'id': PROJECT, 'title': 'Команда'}]
        elif path == '/boards': rows = [{'id': BOARD, 'title': 'Поручения', 'projectId': PROJECT}]
        elif path == '/columns': rows = [{'id': COLUMN, 'title': 'Новые', 'boardId': BOARD}]
        elif path == '/users': rows = [{'id': USER, 'realName': 'Анна'}, {'id': FOREIGN, 'realName': 'Чужой сотрудник'}]
        elif path == '/tasks': rows = list(tasks.values())
        else: raise AssertionError((method, path))
        return {'content': rows, 'paging': {'next': False}}
    monkeypatch.setattr(yougile_client, 'request', provider)
    app = Flask(__name__); app.register_blueprint(yougile_api.yougile_bp)
    yield {'client': app.test_client(), 'connect': connect, 'calls': calls, 'tasks': tasks, 'state': state}
    admin.rollback(); q.execute('SET search_path TO public'); q.execute('DROP SCHEMA ' + schema + ' CASCADE'); admin.commit(); admin.close()


def configured(pilot):
    client = pilot['client']
    result = client.post('/api/business/mine/yougile/connection', json={'api_key': SECRET})
    assert result.status_code == 200, result.json
    result = client.put('/api/business/mine/yougile/selection', json={'project_id': PROJECT, 'board_id': BOARD, 'column_id': COLUMN})
    assert result.status_code == 200, result.json


def draft(pilot, user='owner', **args):
    c = pilot['connect']()
    try:
        result = yougile_tasks.prepare(c.cursor(), 'mine', user, {'operation': 'create', 'title': 'Собрать фото', 'assigned': [USER], **args})
        c.commit(); return result
    finally: c.close()


def apply(payload, user='owner'):
    return yougile_tasks.apply({'tenant_id': 'mine', 'payload': payload}, {'user_id': user})


def test_connection_encrypts_key_and_selection_does_not_write_provider(pilot):
    configured(pilot)
    status = pilot['client'].get('/api/business/mine/yougile/status').json
    assert status['configured'] and status['can_configure']
    assert SECRET not in json.dumps(status)
    c = pilot['connect']();q = c.cursor();q.execute("SELECT auth_data_encrypted FROM externalbusinessaccounts WHERE business_id='mine'")
    ciphertext = q.fetchone()['auth_data_encrypted'];c.close()
    assert SECRET not in ciphertext and json.loads(decrypt_auth_data(ciphertext))['api_key'] == SECRET
    assert all(method == 'GET' for method, _, _ in pilot['calls'])


@pytest.mark.parametrize('user,kind,impersonating,code', [('anonymous','standard','false',401), ('other','standard','false',403), ('owner','demo','false',403), ('owner','standard','true',403)])
def test_tenant_and_identity_boundaries(pilot, user, kind, impersonating, code):
    response = pilot['client'].get('/api/business/mine/yougile/status', headers={'Test-User': user,'Test-Kind': kind,'Test-Impersonating': impersonating})
    assert response.status_code == code
    assert not pilot['calls']


def test_staff_can_read_but_cannot_change_connection(pilot):
    configured(pilot)
    for user in ['manager', 'viewer']:
        headers = {'Test-User': user}
        assert pilot['client'].get('/api/business/mine/yougile/tasks', headers=headers).status_code == 200
        assert pilot['client'].post('/api/business/mine/yougile/connection', headers=headers, json={'api_key': SECRET}).status_code == 403
    with pytest.raises(yougile_client.YouGileError): draft(pilot, user='viewer')


def test_encryption_is_required(pilot, monkeypatch):
    monkeypatch.delenv('EXTERNAL_AUTH_SECRET_KEY')
    result = pilot['client'].post('/api/business/mine/yougile/connection', json={'api_key': SECRET})
    assert result.status_code == 503 and not pilot['calls']


def test_foreign_board_and_assignee_rejected(pilot):
    configured(pilot)
    with pytest.raises(yougile_client.YouGileError): draft(pilot, assigned=[FOREIGN])
    with pytest.raises(yougile_client.YouGileError): draft(pilot, operation='complete', task_id=FOREIGN)
    pilot['state']['foreign_board'] = True
    assert pilot['client'].get('/api/business/mine/yougile/tasks').status_code == 409
    assert not any(method != 'GET' for method, _, _ in pilot['calls'])


def test_create_deadline_idempotency_and_complete(pilot):
    configured(pilot)
    payload = draft(pilot, user='manager', deadline='2026-11-03T18:00:00+03:00')
    assert not any(method != 'GET' for method, _, _ in pilot['calls'])
    first = apply(payload, 'manager'); assert first['status'] == 'completed', first
    assert apply(payload, 'manager') == first
    assert len([call for call in pilot['calls'] if call[0] == 'POST']) == 1
    assert pilot['tasks'][TASK]['deadline']['withTime'] is True
    completed = draft(pilot, operation='complete', task_id=TASK)
    result = apply(completed); assert result['status'] == 'completed', result
    assert pilot['tasks'][TASK]['completed'] is True


def test_stale_connection_and_task_block_writes(pilot):
    configured(pilot)
    payload = draft(pilot)
    configured(pilot)
    result = apply(payload)
    assert result['status'] == 'blocked' and result['blocked_reasons'] == ['stale_preview']
    result = apply(draft(pilot)); assert result['status'] == 'completed', result
    completed = draft(pilot, operation='complete', task_id=TASK)
    pilot['tasks'][TASK]['title'] = 'Изменено другим сотрудником'
    assert apply(completed)['blocked_reasons'] == ['stale_task']
    assert not any(method == 'PUT' for method, _, _ in pilot['calls'])


def test_unknown_write_is_never_retried(pilot):
    configured(pilot); payload = draft(pilot);pilot['state']['fail_after_write'] = True
    assert apply(payload)['blocked_reasons'] == ['unknown_result']
    assert apply(payload)['blocked_reasons'] == ['unknown_result']
    assert len([call for call in pilot['calls'] if call[0] == 'POST']) == 1


def test_readback_retry_does_not_repeat_creation(pilot):
    configured(pilot); payload = draft(pilot); pilot['state']['readback_failed'] = True
    assert apply(payload)['status'] == 'blocked'
    pilot['state']['readback_failed'] = False
    assert apply(payload)['status'] == 'completed'
    assert len([call for call in pilot['calls'] if call[0] == 'POST']) == 1


def test_readback_accepts_additional_deadline_metadata(pilot, monkeypatch):
    configured(pilot); payload = draft(pilot, deadline='2026-11-03T18:00:00+03:00')
    original = yougile_client.request
    def provider(*args, **kwargs):
        result = original(*args, **kwargs)
        if args[1:3] == ('GET', '/tasks/' + TASK):
            return {**result, 'deadline': {**result['deadline'], 'history': ['provider metadata']}}
        return result
    monkeypatch.setattr(yougile_client, 'request', provider)
    assert apply(payload)['status'] == 'completed'


def test_disconnect_clears_secret_and_invalidates_approval(pilot):
    configured(pilot); payload = draft(pilot)
    assert pilot['client'].delete('/api/business/mine/yougile/connection').status_code == 200
    assert apply(payload)['status'] == 'blocked'
    c=pilot['connect']();q=c.cursor();q.execute("SELECT auth_data_encrypted,is_active FROM externalbusinessaccounts WHERE business_id='mine'")
    row=q.fetchone();c.close();assert row['auth_data_encrypted'] is None and not row['is_active']


def test_orchestrator_policy_requires_approval_and_operational_role(pilot):
    from core.action_policy import check_tenant_access, evaluate_risk_policy
    assert evaluate_risk_policy('yougile.task.apply', {}, {'mode': 'auto'})['requires_human']
    c=pilot['connect']();q=c.cursor()
    assert check_tenant_access(q,'mine','manager',False,'yougile.task.apply')['ok']
    assert not check_tenant_access(q,'mine','viewer',False,'yougile.task.apply')['ok']
    assert not check_tenant_access(q,'theirs','owner',False,'yougile.task.apply')['ok']
    c.close()


def test_transport_redacts_provider_errors_and_does_not_follow_redirects(monkeypatch):
    calls=[]
    class Response:
        status_code=401
        def json(self): return {'error': SECRET}
    def send(method,url,**kwargs): calls.append((method,url,kwargs));return Response()
    monkeypatch.setattr(requests,'request',send)
    error = pytest.raises(yougile_client.YouGileError, yougile_client.request, SECRET, 'GET', '/users/me')
    assert SECRET not in str(error.value)
    assert calls[0][2]['allow_redirects'] is False
    assert calls[0][1].startswith('https://ru.yougile.com/api-v2/')
    with pytest.raises(yougile_client.YouGileError):yougile_client.request(SECRET,'DELETE','/tasks/'+TASK)
    with pytest.raises(yougile_client.YouGileError):yougile_client.request(SECRET,'GET','https://evil.test')
    assert len(calls)==1


def test_pagination_rejects_incomplete_duplicate_and_oversized_pages(monkeypatch):
    monkeypatch.setattr(yougile_client,'request',lambda *a,**kw:{'content':[],'paging':{'next':True}})
    with pytest.raises(yougile_client.YouGileError):yougile_client.collection(SECRET,'projects')
    monkeypatch.setattr(yougile_client,'request',lambda *a,**kw:{'content':[{'id':PROJECT}]*2,'paging':{'next':False}})
    with pytest.raises(yougile_client.YouGileError):yougile_client.collection(SECRET,'projects')
    monkeypatch.setattr(yougile_client,'request',lambda *a,**kw:{'content':[{'id':PROJECT}]*101,'paging':{'next':False}})
    with pytest.raises(yougile_client.YouGileError):yougile_client.collection(SECRET,'projects')


def test_task_board_snapshot_avoids_reordering_between_small_pages(monkeypatch):
    rows = [{'id': str(uuid.UUID(int=n))} for n in range(1, 111)]
    calls = []
    def provider(*args, **kwargs):
        params = kwargs['params'];calls.append(params)
        if params['limit'] >= len(rows):return {'content': rows, 'paging': {'next': False}}
        if params['offset'] == 0:return {'content': rows[:100], 'paging': {'next': True}}
        return {'content': [rows[0], *rows[101:]], 'paging': {'next': False}}
    monkeypatch.setattr(yougile_client, 'request', provider)
    assert yougile_client.collection(SECRET, 'tasks', {'columnId': COLUMN}) == rows
    assert len(calls) == 1


@pytest.mark.parametrize('channel', ['web', 'telegram', 'max_bot'])
def test_chat_reads_tasks_and_prepares_existing_orchestrator_approval(pilot, monkeypatch, channel):
    import sys
    from types import SimpleNamespace
    from services import operator_yougile_tasks
    from services.operator_tool_loop import run_operator_tool_loop
    configured(pilot)
    prepared = []
    def registered(**kwargs):
        prepared.append(kwargs)
        return {'status': 'approval_required', 'approval': {'envelope': {'orchestrator_action_id': 'reviewed-action'}}}
    # Isolate the adapter boundary; the existing broad operator module depends
    # on an outreach continuation module absent from this repository baseline.
    monkeypatch.setitem(sys.modules, 'services.operator_core', SimpleNamespace(_prepare_registered_capability_approval=registered))
    connection = pilot['connect']()
    decisions = iter([
        {'action': 'tool_call', 'tool': 'tasks.yougile.list', 'arguments': {}},
        {'action': 'tool_call', 'tool': 'tasks.yougile.prepare', 'arguments': {'operation': 'create', 'title': 'Собрать фото', 'assigned': [USER]}},
    ])
    result = run_operator_tool_loop(business_id='mine', user_id='owner', message='Создай задачу собрать фото',
        tools=operator_yougile_tasks.tools(connection.cursor(), 'mine', 'owner', channel), planner=lambda _state: next(decisions))
    connection.close()
    assert result['status'] == 'approval_required', result
    assert prepared[0]['backend_capability'] == 'yougile.task.apply'
    assert prepared[0]['channel'] == channel
    assert prepared[0]['payload']['business_id'] == 'mine'
    assert 'Анна' in result['chat_response']
    assert all(method == 'GET' for method, _, _ in pilot['calls'])
