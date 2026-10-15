"""Real PostgreSQL in a disposable testcontainer; never uses application DSNs."""
import importlib.util
import threading
import uuid
from pathlib import Path

import psycopg2
import pytest
from psycopg2.extras import RealDictCursor

from services.max_identity import consume_link_code, issue_link_code, MaxLinkError


@pytest.fixture
def max_pg(postgres_container, monkeypatch):
    dsn = postgres_container.get_connection_url().replace('postgresql+psycopg2://', 'postgresql://')
    schema = 'max_' + uuid.uuid4().hex
    def connect():
        return psycopg2.connect(dsn, cursor_factory=RealDictCursor, options='-csearch_path=' + schema)
    connection = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    cursor = connection.cursor()
    cursor.execute('CREATE SCHEMA ' + schema)
    cursor.execute('SET search_path TO ' + schema)
    cursor.execute('CREATE TABLE users(id TEXT PRIMARY KEY, is_active BOOLEAN DEFAULT TRUE, email TEXT, name TEXT, phone TEXT, is_superadmin BOOLEAN DEFAULT FALSE)')
    cursor.execute("INSERT INTO users(id) VALUES ('u1'),('u2')")
    cursor.execute('CREATE TABLE product_analytics_events(channel TEXT)')
    cursor.execute('''CREATE TABLE usersessions(id TEXT PRIMARY KEY,user_id TEXT,token TEXT UNIQUE,
        expires_at TIMESTAMPTZ,ip_address TEXT,user_agent TEXT,created_at TIMESTAMPTZ,
        session_kind TEXT,scope_business_id TEXT)''')
    migration_path = Path(__file__).parents[1] / 'alembic_migrations/versions/20261015_max_control.py'
    spec = importlib.util.spec_from_file_location('max_migration', migration_path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    from alembic import op
    monkeypatch.setattr(op, 'execute', cursor.execute)
    migration.upgrade()
    migration.upgrade()
    connection.commit()
    yield connection, connect
    connection.rollback()
    cursor.execute('DROP SCHEMA ' + schema + ' CASCADE')
    connection.commit()
    connection.close()


def test_code_is_one_use_and_cannot_take_over_another_identity(max_pg):
    connection, _ = max_pg
    cursor = connection.cursor()
    code = issue_link_code(cursor, 'u1')
    assert consume_link_code(cursor, code, '123') == 'u1'
    connection.commit()
    with pytest.raises(MaxLinkError): consume_link_code(cursor, code, '456')
    connection.rollback()
    code2 = issue_link_code(cursor, 'u2')
    connection.commit()
    with pytest.raises(MaxLinkError): consume_link_code(cursor, code2, '123')
    connection.rollback()
    cursor.execute("SELECT user_id FROM max_identities WHERE max_id='123'")
    assert cursor.fetchone()['user_id'] == 'u1'


def test_reissue_and_expiry_invalidate_old_codes(max_pg):
    connection, _ = max_pg
    cursor = connection.cursor()
    old = issue_link_code(cursor, 'u1')
    current = issue_link_code(cursor, 'u1')
    connection.commit()
    with pytest.raises(MaxLinkError): consume_link_code(cursor, old, '123')
    connection.rollback()
    cursor.execute("UPDATE max_link_tokens SET expires_at=NOW()-INTERVAL '1 second'")
    connection.commit()
    with pytest.raises(MaxLinkError): consume_link_code(cursor, current, '123')
    connection.rollback()


def test_concurrent_consumers_link_only_one_identity(max_pg):
    connection, connect = max_pg
    code = issue_link_code(connection.cursor(), 'u1')
    connection.commit()
    barrier = threading.Barrier(2)
    outcomes = []
    def consume(identity):
        attempt = connect()
        try:
            barrier.wait(timeout=10)
            consume_link_code(attempt.cursor(), code, identity)
            attempt.commit()
            outcomes.append('linked')
        except MaxLinkError:
            attempt.rollback()
            outcomes.append('rejected')
        finally:
            attempt.close()
    threads = [threading.Thread(target=consume, args=(identity,)) for identity in ['123', '456']]
    for thread in threads: thread.start()
    for thread in threads: thread.join(timeout=15)
    assert sorted(outcomes) == ['linked', 'rejected']
    cursor = connection.cursor()
    cursor.execute('SELECT COUNT(*) AS n FROM max_identities')
    assert cursor.fetchone()['n'] == 1


def test_same_webhook_receipt_can_only_be_inserted_once(max_pg):
    connection, _ = max_pg
    cursor = connection.cursor()
    for _ in range(2):
        cursor.execute("INSERT INTO max_webhook_events(event_key,payload_json) VALUES ('same','{}') ON CONFLICT(event_key) DO NOTHING")
    cursor.execute("SELECT COUNT(*) AS n FROM max_webhook_events")
    assert cursor.fetchone()['n'] == 1


def test_revocation_and_relink_never_revive_an_old_session(max_pg, monkeypatch):
    connection, connect = max_pg
    import auth_system
    monkeypatch.setenv('MAX_ENABLED', 'true')
    monkeypatch.setattr(auth_system, 'get_db_connection', connect)
    code = issue_link_code(connection.cursor(), 'u1')
    consume_link_code(connection.cursor(), code, '123')
    connection.commit()
    token = auth_system.create_session('u1', user_agent='localos-max-mini-app', expires_days=1)
    assert token
    assert auth_system.verify_session(token)['messenger_platform'] == 'max'
    cursor = connection.cursor()
    cursor.execute("UPDATE max_identities SET revoked_at=NOW() WHERE user_id='u1'")
    connection.commit()
    assert auth_system.verify_session(token) is None
    cursor.execute("UPDATE max_identities SET revoked_at=NULL,linked_at=NOW() WHERE user_id='u1'")
    connection.commit()
    assert auth_system.verify_session(token) is None
    new_token = auth_system.create_session('u1', user_agent='localos-max-mini-app', expires_days=1)
    assert auth_system.verify_session(new_token)
    monkeypatch.setenv('MAX_ENABLED', 'false')
    assert auth_system.verify_session(new_token) is None


@pytest.mark.parametrize('uncertain', [False, True])
def test_worker_never_resends_an_acknowledged_or_uncertain_reply(max_pg, monkeypatch, uncertain):
    connection, connect = max_pg
    from services import max_bot, max_transport
    from services.max_transport import MaxTransportError
    import database_manager
    monkeypatch.setenv('MAX_ENABLED', 'true')
    class Database:
        def __init__(self): self.conn = connect()
        def close(self): self.conn.close()
    monkeypatch.setattr(database_manager, 'DatabaseManager', Database)
    monkeypatch.setattr(max_bot, 'prepare_bot_response', lambda *args: {'user_id': '123', 'text': 'x' * 5000, 'attachments': [{'approved': True}]})
    calls = []
    class Transport:
        def send(self, user_id, text, attachments):
            calls.append((text, attachments))
            if uncertain: raise MaxTransportError('max_connection_failed', uncertain=True)
            return {'message': {'body': {'mid': 'mid-' + str(len(calls))}}}
    monkeypatch.setattr(max_transport, 'MaxTransport', Transport)
    cursor = connection.cursor()
    cursor.execute("INSERT INTO max_webhook_events(event_key,payload_json) VALUES ('e1','{}')")
    connection.commit()
    max_bot.process_next_max_event()
    max_bot.process_next_max_event()
    cursor.execute("SELECT status,result_json FROM max_webhook_events WHERE event_key='e1'")
    row = cursor.fetchone()
    assert row['status'] == ('needs_attention' if uncertain else 'completed')
    assert len(calls) == (1 if uncertain else 2)
    if not uncertain:
        assert calls[0][1] == [] and calls[1][1] == [{'approved': True}]
        assert ''.join(text for text, _ in calls) == 'x' * 5000
        assert row['result_json']['provider_message_ids'] == ['mid-1', 'mid-2']


def test_disconnected_identity_can_be_replaced_without_reviving_sessions(max_pg):
    connection, _ = max_pg
    cursor = connection.cursor()
    consume_link_code(cursor, issue_link_code(cursor, 'u1'), '123')
    cursor.execute("UPDATE max_identities SET revoked_at=NOW() WHERE user_id='u1'")
    consume_link_code(cursor, issue_link_code(cursor, 'u1'), '456')
    cursor.execute("SELECT max_id FROM max_identities WHERE user_id='u1'")
    assert cursor.fetchone()['max_id'] == '456'


def test_command_stage_survives_new_connection_and_rejects_changed_business(max_pg, monkeypatch):
    from services.max_commands import handle_command
    import subscription_manager
    monkeypatch.setattr(subscription_manager, 'capability_access_payload', lambda *args: {'allowed': True})
    from services import max_commands
    commands = max_commands
    monkeypatch.setattr(commands, 'capability_access_payload', lambda *args: {'allowed': True})
    connection, connect = max_pg
    arguments = {'actor': {'id': 'u1', 'max_id': '123'}, 'business_id': 'b1', 'subscription': {}, 'event_key': 'test'}
    first = handle_command(connection.cursor(), text='/reply_review', callback='', **arguments)
    assert 'Пришлите' in first['text']
    connection.commit()
    resumed = connect()
    try:
        second = handle_command(resumed.cursor(), text='Спасибо!', callback='', **arguments)
        assert second['operator_message'] == 'Подготовь ответ на отзыв: Спасибо!'
        resumed.rollback()
        changed = handle_command(resumed.cursor(), text='Спасибо!', callback='', **{**arguments, 'business_id': 'b2'})
        assert 'изменился' in changed['text']
        resumed.commit()
    finally:
        resumed.close()
    cursor = connection.cursor()
    cursor.execute('SELECT 1 FROM max_bot_states')
    assert cursor.fetchone() is None


def test_stopped_bot_suppresses_already_queued_guest_audit(max_pg):
    from services.max_bot import prepare_bot_response
    from services.max_guest_audits import prepare_guest_audit_result
    connection, _ = max_pg
    cursor = connection.cursor()
    cursor.execute('CREATE TABLE publicreportrequests(slug TEXT,status TEXT)')
    cursor.execute("INSERT INTO publicreportrequests VALUES ('s','completed')")
    cursor.execute("INSERT INTO max_guest_audits(event_key,max_id,slug,public_url) VALUES ('a','123','s','https://localos.pro/s')")
    prepare_bot_response(cursor, {'update_type': 'bot_stopped', 'user': {'user_id': 123}}, 'stop')
    assert prepare_guest_audit_result(cursor, {'audit_event_key': 'a', 'max_id': '123'}) is None


def test_recovery_intent_blocks_repeat_after_uncertain_execution(max_pg, monkeypatch):
    connection, connect = max_pg
    import database_manager
    from services.mobile_diagnostics import run_reviewed_operation_once
    class Database:
        def __init__(self): self.conn = connect()
        def close(self): self.conn.close()
    monkeypatch.setattr(database_manager, 'DatabaseManager', Database)
    calls = []
    def uncertain():
        calls.append(1)
        raise RuntimeError('sensitive details')
    first = run_reviewed_operation_once('diagnostics:nonce', uncertain)
    second = run_reviewed_operation_once('diagnostics:nonce', uncertain)
    assert first == second and len(calls) == 1 and 'sensitive' not in first
    cursor = connection.cursor()
    cursor.execute("SELECT status FROM max_webhook_events WHERE event_key='diagnostics:nonce'")
    assert cursor.fetchone()['status'] == 'needs_attention'


def test_feature_category_stage_and_industry_preview_are_durable(max_pg, monkeypatch):
    from services.max_commands import handle_command
    from core import industry_pattern_recalibration
    industry = industry_pattern_recalibration
    monkeypatch.setattr(industry, 'run_monthly_industry_pattern_recalibration', lambda *args: pytest.fail('preview must not mutate rules'))
    connection, _ = max_pg
    cursor = connection.cursor()
    arguments = {'actor': {'id': 'u1', 'max_id': '123'}, 'business_id': 'b1', 'subscription': {}, 'event_key': 'test'}
    preview = handle_command(cursor, text='/feature_request', callback='', **arguments)
    assert len(preview['buttons'][0]['payload']['buttons']) == 6
    selected = handle_command(cursor, text='', callback='feature_category:reviews', **arguments)
    assert 'Опишите' in selected['text']
    cursor.execute("SELECT state_json FROM max_bot_states WHERE user_id='u1'")
    assert cursor.fetchone()['state_json']['category'] == 'reviews'
    preview = handle_command(cursor, text='/industry_patterns_recalibrate', callback='',
        **{**arguments, 'business_id': 'platform', 'actor': {**arguments['actor'], 'is_superadmin': True}})
    assert preview['buttons'][0]['payload']['buttons'][0][0]['payload'].startswith('industry_recalibrate:')
    connection.commit()


def test_waiting_voice_result_does_not_starve_other_events(max_pg, monkeypatch):
    connection, connect = max_pg
    from services import max_bot
    import database_manager
    monkeypatch.setenv('MAX_ENABLED', 'true')
    class Database:
        def __init__(self): self.conn = connect()
        def close(self): self.conn.close()
    monkeypatch.setattr(database_manager, 'DatabaseManager', Database)
    def prepare(cursor, payload, key):
        if key == 'waiting': raise max_bot.MaxEventDeferred()
        return None
    monkeypatch.setattr(max_bot, 'prepare_bot_response', prepare)
    cursor = connection.cursor()
    cursor.execute("INSERT INTO max_webhook_events(event_key,payload_json,created_at) VALUES ('waiting','{}',NOW()-INTERVAL '1 second'),('ready','{}',NOW())")
    connection.commit()
    assert max_bot.process_next_max_event() == 'waiting'
    assert max_bot.process_next_max_event() == 'ready'
    cursor.execute("SELECT status,available_at>NOW() AS delayed FROM max_webhook_events WHERE event_key='waiting'")
    assert dict(cursor.fetchone()) == {'status': 'pending', 'delayed': True}


def test_revocation_after_preparation_prevents_private_reply_delivery(max_pg, monkeypatch):
    connection, connect = max_pg
    from services import max_bot, max_transport
    import database_manager
    monkeypatch.setenv('MAX_ENABLED', 'true')
    class Database:
        def __init__(self): self.conn = connect()
        def close(self): self.conn.close()
    monkeypatch.setattr(database_manager, 'DatabaseManager', Database)
    monkeypatch.setattr(max_bot, 'resolve_control_scope', lambda *args, **kwargs: None)
    cursor = connection.cursor()
    consume_link_code(cursor, issue_link_code(cursor, 'u1'), '123')
    cursor.execute("INSERT INTO max_webhook_events(event_key,payload_json) VALUES ('private',%s)",
        (json_payload({'update_type': 'bot_started', 'user': {'user_id': 123}}),))
    connection.commit()
    def prepare(cursor, payload, key):
        cursor.execute("UPDATE max_identities SET revoked_at=NOW() WHERE max_id='123'")
        return max_bot.response('123', 'Private business result')
    monkeypatch.setattr(max_bot, 'prepare_bot_response', prepare)
    monkeypatch.setattr(max_transport.MaxTransport, 'send', lambda *args, **kwargs: pytest.fail('revoked recipient must not get private data'))
    max_bot.process_next_max_event()
    cursor.execute("SELECT status,error_code FROM max_webhook_events WHERE event_key='private'")
    assert dict(cursor.fetchone()) == {'status': 'failed', 'error_code': 'delivery_access_revoked'}


def json_payload(value):
    from psycopg2.extras import Json
    return Json(value)


def test_max_session_binding_survives_clock_skew_but_not_a_changed_identity(max_pg, monkeypatch):
    connection, connect = max_pg
    import auth_system
    monkeypatch.setenv('MAX_ENABLED', 'true')
    monkeypatch.setattr(auth_system, 'get_db_connection', connect)
    cursor = connection.cursor()
    consume_link_code(cursor, issue_link_code(cursor, 'u1'), '123')
    connection.commit()
    token = auth_system.create_session('u1', user_agent='localos-max-mini-app')
    assert auth_system.verify_session(token)
    cursor.execute("UPDATE usersessions SET created_at=NOW()+INTERVAL '1 day' WHERE token=%s", (token,))
    connection.commit()
    assert auth_system.verify_session(token)  # Timestamp drift cannot change the binding.
    cursor.execute("UPDATE max_identities SET linked_at=linked_at-INTERVAL '1 second' WHERE max_id='123'")
    connection.commit()
    assert auth_system.verify_session(token) is None  # Even a backwards clock cannot revive it.
    cursor.execute("UPDATE usersessions SET user_agent='localos-max-mini-app' WHERE token=%s", (token,))
    connection.commit()
    assert auth_system.verify_session(token) is None  # Legacy unversioned MAX sessions fail closed.
