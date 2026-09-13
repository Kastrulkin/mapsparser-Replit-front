"""Regression checks for session and transaction boundaries using disposable PostgreSQL."""
import os
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
import pytest
from flask import Flask
from database_manager import DatabaseManager
from tests.test_operator_voice_pg import pg
from tests.test_finance_daily_pg import daily
from tests.test_work_journal_pg import journal, note


def database_factory(connection):
    cursor = connection.cursor()
    cursor.execute('SELECT current_schema() name')
    schema = cursor.fetchone()['name']
    connection.commit()
    created = []
    def factory():
        instance = DatabaseManager.__new__(DatabaseManager)
        instance.conn = psycopg2.connect(os.environ['OPERATOR_VOICE_TEST_DSN'], cursor_factory=RealDictCursor,
                                        options='-c search_path='+schema)
        instance._closed = False
        created.append(instance)
        return instance
    return factory, created


def journal_app(connection, monkeypatch, session):
    from api import work_journal_api
    factory, created = database_factory(connection)
    monkeypatch.setattr(work_journal_api, 'DatabaseManager', factory)
    monkeypatch.setattr(work_journal_api, 'verify_session', lambda token: session)
    app = Flask(__name__)
    app.register_blueprint(work_journal_api.work_journal_bp)
    return app, created


@pytest.mark.parametrize("method", ["get", "post"])
def test_work_journal_preserves_restricted_session_scope(journal, monkeypatch, method):
    connection, cursor = journal
    app, created = journal_app(connection, monkeypatch,
        {'user_id':'u','session_kind':'demo','scope_business_id':'different-business'})
    response = getattr(app.test_client(), method)('/api/work-journal?business_id=b', headers={'Authorization':'Bearer scoped'}, json={'text':'Наблюдение'})
    assert response.status_code == 403
    assert all(instance._closed for instance in created)


def test_work_journal_rolls_back_unexpected_failure(journal, monkeypatch):
    connection, cursor = journal
    app, created = journal_app(connection, monkeypatch, {'user_id':'u'})
    from api import work_journal_api
    def broken(cursor, business, user, data):
        note(cursor, user='u', key='unexpected-failure')
        raise RuntimeError('failure after writing note and event')
    app.add_url_rule('/failure', view_func=lambda: work_journal_api.dispatch(broken), methods=['POST'])
    response = app.test_client().post('/failure', headers={'Authorization':'Bearer owner'}, json={'business_id':'b'})
    assert response.status_code == 500
    cursor.execute('SELECT COUNT(*) n FROM business_work_journal')
    assert cursor.fetchone()['n'] == 0
    cursor.execute('SELECT COUNT(*) n FROM averageticketevents')
    assert cursor.fetchone()['n'] == 0
    assert all(instance._closed for instance in created)


def test_finance_response_failure_does_not_commit_manual_entry(pg, monkeypatch):
    from api import finance_api
    connection, cursor = pg
    cursor.execute('CREATE TABLE finance_entries(id TEXT,business_id TEXT,date DATE,type TEXT,category TEXT,amount NUMERIC,source TEXT,comment TEXT)')
    factory, created = database_factory(connection)
    monkeypatch.setattr(finance_api, 'DatabaseManager', factory)
    monkeypatch.setattr(finance_api, '_require_finance_user_and_business', lambda: ({'user_id':'u'},'b',None))
    def broken(*args):
        raise RuntimeError('snapshot calculation failed')
    monkeypatch.setattr(finance_api, '_finance_snapshot_for_period', broken)
    app = Flask(__name__); app.register_blueprint(finance_api.finance_bp)
    response = app.test_client().post('/api/finance/manual-entry', json={'entries':[{'amount':350}]})
    assert response.status_code == 500
    cursor.execute('SELECT COUNT(*) n FROM finance_entries')
    assert cursor.fetchone()['n'] == 0
    assert all(instance._closed for instance in created)


def test_audio_failure_keeps_input_and_rolls_back_ready_state(pg, monkeypatch):
    import database_manager
    from services import operator_audio, operator_async_jobs, operator_speechkit
    connection, cursor = pg
    upload = operator_audio.create_transcription(cursor, content=b'original audio', user_id='u',business_id='b',
        channel='web',conversation_id=None,request_id='rollback-audio')
    cursor.execute("UPDATE operator_audio_assets SET provider_operation_id='existing-operation' WHERE id=%s", (upload['asset_id'],))
    claimed = operator_async_jobs.claim_next_operator_async_job(cursor)
    cursor.execute('SELECT path FROM operator_audio_assets WHERE id=%s',(upload['asset_id'],))
    source = Path(cursor.fetchone()['path'])
    factory, created = database_factory(connection)
    monkeypatch.setattr(database_manager, 'DatabaseManager', factory)
    class Provider:
        def result(self, operation): return 'Покажи услуги'
    monkeypatch.setattr(operator_speechkit, 'SpeechKit', Provider)
    def broken(*args): raise RuntimeError('classification failed')
    monkeypatch.setattr(operator_audio, 'finance_transcription_result', broken)
    with pytest.raises(RuntimeError, match='classification failed'):
        operator_audio.process_audio_job(claimed)
    cursor.execute('SELECT status,path FROM operator_audio_assets WHERE id=%s',(upload['asset_id'],))
    row=cursor.fetchone()
    assert row['status'] != 'ready'
    assert row['path'] == str(source)
    assert source.read_bytes() == b'original audio'
    assert all(instance._closed for instance in created)


def test_recovered_ready_speech_returns_speech_result(pg, monkeypatch):
    import database_manager
    from services import operator_audio, operator_async_jobs, operator_chat_service
    connection, cursor = pg
    reply = operator_chat_service.process_chat(cursor,business_id='b',user_id='u',channel='telegram',message='Что ты умеешь?',
        router=lambda *a,**k: ({'status':'completed','chat_response':'Сохранённый ответ'},{}))
    speech=operator_audio.create_speech(cursor,user_id='u',message_id=reply['message_id'])
    path=operator_audio.audio_root()/(speech['asset_id']+'.ogg');path.write_bytes(b'cached audio')
    cursor.execute("UPDATE operator_audio_assets SET status='ready',path=%s WHERE id=%s",(str(path),speech['asset_id']))
    claimed=operator_async_jobs.claim_next_operator_async_job(cursor)
    factory,_=database_factory(connection);monkeypatch.setattr(database_manager,'DatabaseManager',factory)
    result=operator_audio.process_audio_job(claimed)
    assert result['audio_url']=='/api/operator/audio/'+speech['asset_id']
    assert result['message_id']==reply['message_id']
    assert 'transcript' not in result


def test_finance_success_commits_before_closing(pg, monkeypatch):
    from api import finance_api
    connection, cursor = pg
    cursor.execute('CREATE TABLE finance_entries(id TEXT,business_id TEXT,date DATE,type TEXT,category TEXT,amount NUMERIC,source TEXT,comment TEXT)')
    factory, created = database_factory(connection)
    monkeypatch.setattr(finance_api, 'DatabaseManager', factory)
    monkeypatch.setattr(finance_api, '_require_finance_user_and_business', lambda: ({'user_id':'u'},'b',None))
    def snapshot(c, business, start, end):
        c.execute('SELECT SUM(amount) total FROM finance_entries')
        return {}, {}, {'revenue':str(c.fetchone()['total'])}
    monkeypatch.setattr(finance_api, '_finance_snapshot_for_period', snapshot)
    app=Flask(__name__);app.register_blueprint(finance_api.finance_bp)
    result=app.test_client().post('/api/finance/manual-entry',json={'entries':[{'amount':350}]})
    assert result.status_code==200
    assert result.json['dashboard']['revenue']=='350.0'
    cursor.execute('SELECT COUNT(*) n FROM finance_entries')
    assert cursor.fetchone()['n']==1
    assert all(instance._closed for instance in created)


def test_deferred_commit_failure_is_visible_to_context_caller(pg):
    connection, cursor=pg
    cursor.execute('CREATE TABLE deferred_entries(id INTEGER UNIQUE DEFERRABLE INITIALLY DEFERRED)')
    factory,_=database_factory(connection)
    manager=factory()
    manager.conn.cursor().execute('INSERT INTO deferred_entries VALUES (1),(1)')
    with pytest.raises(psycopg2.errors.UniqueViolation):
        manager.__exit__(None,None,None)
    assert manager._closed
    cursor.execute('SELECT COUNT(*) n FROM deferred_entries')
    assert cursor.fetchone()['n']==0


def test_stale_audio_worker_cannot_delete_recoverable_input(pg, monkeypatch):
    import database_manager
    from services import operator_audio,operator_async_jobs,operator_speechkit
    connection,cursor=pg
    upload=operator_audio.create_transcription(cursor,content=b'keep source',user_id='u',business_id='b',channel='web',conversation_id=None,request_id='lease')
    cursor.execute("UPDATE operator_audio_assets SET provider_operation_id='existing' WHERE id=%s",(upload['asset_id'],))
    claimed=operator_async_jobs.claim_next_operator_async_job(cursor)
    cursor.execute('SELECT path FROM operator_audio_assets WHERE id=%s',(upload['asset_id'],));source=Path(cursor.fetchone()['path'])
    factory,_=database_factory(connection);monkeypatch.setattr(database_manager,'DatabaseManager',factory)
    class Provider:
        def result(self, operation):
            other=factory()
            other.conn.cursor().execute("UPDATE operator_async_jobs SET lease_token='replacement' WHERE id=%s",(claimed['id'],))
            other.conn.commit();other.close()
            return 'Покажи услуги'
    monkeypatch.setattr(operator_speechkit,'SpeechKit',Provider)
    with pytest.raises(ValueError,match='другому исполнителю'):
        operator_audio.process_audio_job(claimed)
    cursor.execute('SELECT status,path FROM operator_audio_assets WHERE id=%s',(upload['asset_id'],));row=cursor.fetchone()
    assert row['status']!='ready'
    assert row['path']==str(source)
    assert source.read_bytes()==b'keep source'
