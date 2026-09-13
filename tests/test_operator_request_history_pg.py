import os
import psycopg2
from psycopg2.extras import RealDictCursor
import pytest
from tests.test_operator_voice_pg import pg
from services import operator_request_history, operator_chat_service, operator_audio


@pytest.fixture
def receipts(pg, monkeypatch):
    conn, cursor = pg
    cursor.execute('SELECT current_schema() name')
    schema = cursor.fetchone()['name']
    cursor.execute('''CREATE TABLE agent_action_ledger(id TEXT PRIMARY KEY,business_id TEXT,action_type TEXT,
        capability TEXT,risk_level TEXT,input_summary TEXT,output_summary TEXT,status TEXT,reason_code TEXT,
        metadata_json JSONB DEFAULT '{}',created_at TIMESTAMPTZ DEFAULT NOW())''')
    cursor.execute('ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT TRUE, ADD COLUMN is_superadmin BOOLEAN DEFAULT FALSE')
    cursor.execute('ALTER TABLE businesses ADD COLUMN owner_id TEXT, ADD COLUMN is_active BOOLEAN DEFAULT TRUE, ADD COLUMN network_id TEXT')
    cursor.execute("UPDATE businesses SET owner_id='u'")
    cursor.execute("INSERT INTO users(id) VALUES ('v')")
    cursor.execute('CREATE TABLE business_members(business_id TEXT,user_id TEXT,status TEXT)')
    cursor.execute("INSERT INTO business_members VALUES ('b','v','active')")
    cursor.execute('CREATE TABLE network_members(network_id TEXT,user_id TEXT,status TEXT)')
    cursor.execute('CREATE TABLE networks(id TEXT,owner_id TEXT)')
    conn.commit()
    class IndependentDB:
        def __init__(self):
            self.conn = psycopg2.connect(os.environ['OPERATOR_VOICE_TEST_DSN'], cursor_factory=RealDictCursor,
                                         options='-c search_path=' + schema + ' -c statement_timeout=5000')
        def close(self):
            self.conn.close()
    monkeypatch.setattr(operator_request_history, 'DatabaseManager', IndependentDB)
    monkeypatch.setenv('OPERATOR_REQUEST_AUDIT_BUSINESS_IDS', 'b')
    def authorize(c, user, business):
        operator_request_history.scope(c, business, user)
        from subscription_manager import build_subscription_capabilities
        return {'role': 'business_owner' if user == 'u' else 'business_user'}, build_subscription_capabilities(tier='concierge', status='active')
    monkeypatch.setattr(operator_audio, 'authorize_actor', authorize)
    return conn, cursor


def run(cursor, router, **payload):
    return operator_chat_service.process_chat(cursor, business_id='b', user_id='u', channel='web',
        message='Покажи следующий пост', payload={'request_id': 'one', **payload}, router=router)


def test_receipt_survives_business_rollback(receipts):
    conn, cursor = receipts
    def broken(c, **kwargs):
        raise RuntimeError('provider failure containing private content')
    with pytest.raises(RuntimeError):
        run(cursor, broken)
    conn.rollback()
    entries = operator_request_history.list_requests(cursor, 'b', 'u', {})['items']
    assert len(entries) == 1
    assert entries[0]['status'] == 'failed'
    assert entries[0]['reason_code'] == 'execution'
    assert entries[0]['input_summary'] == 'Покажи следующий пост'
    cursor.execute('SELECT COUNT(*) n FROM operatormessages')
    assert cursor.fetchone()['n'] == 0
    assert 'private' not in str(entries)


def test_completed_result_and_duplicate_are_atomic(receipts):
    conn, cursor = receipts
    calls = []
    def router(c, **kwargs):
        calls.append(kwargs['message'])
        return {'status': 'completed', 'chat_response': 'Следующий пост', 'capability': 'operator.query'}, {}
    first = run(cursor, router)
    conn.commit()
    second = run(cursor, router)
    conn.commit()
    assert first['message_id'] == second['message_id']
    assert len(calls) == 1
    entry = operator_request_history.detail(cursor, 'b', 'u', first['request_audit_id'])
    assert entry['metadata_json']['duplicates'] == 1
    assert entry['response']['content'] == 'Следующий пост'
    assert entry['status'] == 'completed'
    with pytest.raises(ValueError):
        operator_request_history.receive('b', 'u', 'web', 'Другой текст', {'request_id': 'one'})


def test_employee_cannot_read_or_comment_on_owner_request(receipts):
    conn, cursor = receipts
    receipt = operator_request_history.receive('b', 'u', 'web', 'private', {})
    assert not operator_request_history.list_requests(cursor, 'b', 'v', {})['items']
    with pytest.raises(PermissionError):
        operator_request_history.detail(cursor, 'b', 'v', receipt)
    with pytest.raises(PermissionError):
        operator_request_history.feedback(cursor, 'b', 'v', receipt, 'bad')
    operator_request_history.feedback(cursor, 'b', 'u', receipt, 'Не тот пост')
    operator_request_history.feedback(cursor, 'b', 'u', receipt, 'Нужен ближайший пост')
    cursor.execute("SELECT COUNT(*) n FROM agent_action_ledger WHERE action_type='operator_request_feedback'")
    assert cursor.fetchone()['n'] == 1
    cursor.execute("UPDATE business_members SET status='revoked' WHERE user_id='v'")
    conn.commit()
    with pytest.raises(PermissionError):
        operator_request_history.list_requests(cursor, 'b', 'v', {})


def test_forbidden_input_has_no_body_in_ledger(receipts):
    conn, cursor = receipts
    cursor.execute("UPDATE users SET is_active=FALSE WHERE id='u'")
    conn.commit()
    with pytest.raises(PermissionError):
        operator_request_history.receive('b', 'u', 'web', 'secret', {})
    cursor.execute('SELECT COUNT(*) n FROM agent_action_ledger')
    assert cursor.fetchone()['n'] == 0


def test_crash_leaves_receipt_unfinished_not_completed(receipts):
    conn, cursor = receipts
    receipt = operator_request_history.receive('b', 'u', 'web', 'Команда', {})
    operator_request_history.complete(cursor, receipt, {'status': 'completed'})
    conn.rollback()
    assert operator_request_history.detail(cursor, 'b', 'u', receipt)['status'] == 'received'


def test_failed_stt_visible_without_dispatching_chat(receipts):
    conn, cursor = receipts
    audio = operator_audio.create_transcription(cursor, content=b'broken recording', user_id='u', business_id='b',
        channel='web', conversation_id=None, request_id='audio-failure')
    cursor.execute("UPDATE operator_async_jobs SET status='failed' WHERE id=%s", (audio['job_id'],))
    conn.commit()
    rows = operator_request_history.list_requests(cursor, 'b', 'u', {'input_type': 'voice'})['items']
    assert len(rows) == 1 and rows[0]['reason_code'] == 'stt'
    assert rows[0]['status'] == 'failed'
    assert operator_request_history.detail(cursor, 'b', 'u', rows[0]['id'])['audio']['status']


def test_confirmation_updates_request_status(receipts):
    conn, cursor = receipts
    from services.operator_conversations import finish_operator_action
    def router(c, **kwargs):
        return {'status': 'approval_required', 'capability': 'finance.daily.write', 'chat_response': 'Сохранить?',
                'approval': {'envelope': {'orchestrator_action_id': 'approved-test'}}}, {}
    result = run(cursor, router)
    conn.commit()
    finish_operator_action(cursor, action_id=result['approval']['action_id'], result={'status': 'completed', 'chat_response': 'Сохранено'})
    conn.commit()
    entry = operator_request_history.detail(cursor, 'b', 'u', result['request_audit_id'])
    assert entry['status'] == 'completed' and entry['output_summary'] == 'Сохранено'


def test_receipt_migration_is_idempotent(receipts, monkeypatch):
    _, cursor = receipts
    import importlib.util
    from pathlib import Path
    from alembic import op
    monkeypatch.setattr(op, 'execute', cursor.execute)
    spec = importlib.util.spec_from_file_location('receipt_migration', Path(__file__).parents[1] / 'alembic_migrations/versions/20260913_operator_request_audit.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.upgrade()
    module.upgrade()
    cursor.execute("SELECT COUNT(*) n FROM pg_indexes WHERE schemaname=current_schema() AND indexname LIKE 'idx_operator_request_%'")
    assert cursor.fetchone()['n'] == 3


def test_access_revoked_during_execution_does_not_return_or_commit_response(receipts):
    conn, cursor = receipts
    def router(c, **kwargs):
        other = operator_request_history.DatabaseManager()
        try:
            other.conn.cursor().execute("UPDATE users SET is_active=FALSE WHERE id='u'")
            other.conn.commit()
        finally:
            other.close()
        return {'status': 'completed', 'capability': 'operator.query', 'chat_response': 'private result'}, {}
    with pytest.raises(PermissionError):
        run(cursor, router)
    conn.commit()
    cursor.execute('SELECT COUNT(*) n FROM operatormessages')
    assert cursor.fetchone()['n'] == 0
    cursor.execute("SELECT status,reason_code,output_summary FROM agent_action_ledger WHERE action_type=%s", (operator_request_history.EVENT,))
    row = cursor.fetchone()
    assert row['status'] == 'failed' and row['reason_code'] == 'access'
    assert not row['output_summary']
