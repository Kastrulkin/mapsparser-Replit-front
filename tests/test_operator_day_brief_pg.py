"""Real LocalOS state on loopback PostgreSQL. Provider delivery is mocked."""
import json
import uuid
import pytest
from tests.test_operator_voice_pg import pg
from tests.test_finance_daily_pg import daily
from tests.test_work_journal_pg import journal
from tests.test_operator_workday import workday
from services import operator_day_brief, operator_core, operator_chat_service, operator_audio, operator_work_handoff


@pytest.fixture
def team(workday, monkeypatch):
    conn, c = workday
    local_day = operator_day_brief.work_journal.local_day
    # Business today is deterministic; timezone calculation has its own journal tests.
    monkeypatch.setattr(operator_day_brief.work_journal, 'local_day', lambda cursor, business, value=None: '2026-10-17' if value is None else local_day(cursor, business, value))
    c.execute("ALTER TABLE businesses ADD COLUMN IF NOT EXISTS name TEXT DEFAULT 'Тестовый салон'")
    c.execute("UPDATE businesses SET name='Тестовый салон' WHERE id='b'")
    authorize_actor = operator_audio.authorize_actor
    def entitled(cursor, user, business):
        actor, _ = authorize_actor(cursor, user, business)
        return actor, {'capabilities': ['management', 'operator', 'average_ticket']}
    monkeypatch.setattr(operator_audio, 'authorize_actor', entitled)
    c.execute("CREATE TABLE max_identities(user_id TEXT,max_id TEXT,revoked_at TIMESTAMPTZ,notifications_enabled BOOLEAN DEFAULT TRUE)")
    c.execute("INSERT INTO max_identities(user_id,max_id) VALUES('master','987'),('u','owner-max')")
    c.execute("UPDATE users SET name=id,telegram_id='tg-' || id")
    c.execute("ALTER TABLE journey_actions ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'ready', ADD COLUMN version INT DEFAULT 1, ADD COLUMN created_at TIMESTAMPTZ DEFAULT NOW(),ADD COLUMN updated_at TIMESTAMPTZ DEFAULT NOW(),ADD COLUMN completed_at TIMESTAMPTZ, ADD COLUMN priority INT DEFAULT 50")
    monkeypatch.setenv('OPERATOR_DAY_BRIEF_DELIVERY_ENABLED', 'false')
    monkeypatch.setenv('MAX_BOT_USERNAME', 'fixture_bot')
    conn.commit()
    return conn, c


def save(c, current=None, recipients=None, focus='Внимательно встречаем новых клиентов.'):
    current = current or {}
    targets = recipients if recipients is not None else [{'user_id': 'master', 'platforms': ['telegram', 'max'], 'tasks': [{'text': 'Проверить готовность рабочего места.'}]}]
    return operator_day_brief.save(c, business='b', user='u', payload={'date': '2026-10-17', 'version': current.get('version', 0),
        'focus': focus, 'recipients': targets, 'request_id': str(uuid.uuid4())})


def test_save_preview_no_assign_or_send_and_employee_cannot_read_owner_draft(team):
    conn, c = team
    assert operator_day_brief.overview(c, business='b', user='master', day='2026-10-17')['draft'] is None
    current = save(c)
    preview = operator_day_brief.prepare(c, business='b', user='u', identifier=current['id'], version=1)
    assert preview['status'] == 'approval_required'
    assert preview['day_brief_preview']['messages'][0]['platforms'] == ['telegram', 'max']
    assert preview['approval']['envelope']['business_name'] == 'Тестовый салон'
    assert 'Тестовый салон' in preview['chat_response']
    assert 'Фокус дня' in preview['chat_response'] and 'Проверить готовность' in preview['chat_response']
    assert 'bindings' not in preview['day_brief_preview']['messages'][0]
    assert not preview['approval']['envelope']['delivery_enabled']
    c.execute('SELECT COUNT(*) n FROM journey_actions'); assert c.fetchone()['n'] == 0
    c.execute('SELECT COUNT(*) n FROM operator_async_jobs'); assert c.fetchone()['n'] == 0
    assert not operator_day_brief.draft(c, 'b', 'master', identifier=current['id'])
    with pytest.raises(PermissionError): operator_day_brief.save(c, business='b', user='master', payload={})
    with pytest.raises(PermissionError): operator_day_brief.overview(c, business='other', user='u')


def test_confirmation_assigns_one_shared_task_and_separate_platform_jobs_once(team, monkeypatch):
    conn, c = team
    monkeypatch.setenv('OPERATOR_DAY_BRIEF_DELIVERY_ENABLED', 'true')
    current = save(c)
    envelope = operator_day_brief.prepare(c, business='b', user='u', identifier=current['id'], version=1)['approval']['envelope']
    result = operator_day_brief.apply(c, business='b', user='u', envelope=envelope)
    repeated = operator_day_brief.apply(c, business='b', user='u', envelope=envelope)
    assert result['action_ids'] == repeated['action_ids']
    c.execute('SELECT COUNT(*) n FROM journey_actions'); assert c.fetchone()['n'] == 1
    c.execute('SELECT COUNT(*) n FROM operator_async_jobs'); assert c.fetchone()['n'] == 2
    assert len(operator_day_brief.assignments(c, 'b', 'master')) == 1
    assert operator_day_brief.assignments(c, 'b', 'admin') == []
    row = operator_day_brief.assignments(c, 'b', 'master')[0]
    task = row['payload_json']['tasks'][0]
    args = dict(business='b', user='master', action_id=str(row['id']), task_id=task['id'], version=row['version'], done=True)
    operator_day_brief.complete_task(c, **args)
    assert operator_day_brief.complete_task(c, **args)['idempotent']
    assert operator_day_brief.assignments(c, 'b', 'master')[0]['payload_json']['tasks'][0]['done']
    with pytest.raises(PermissionError): operator_day_brief.complete_task(c, **{**args, 'user': 'admin'})


@pytest.mark.parametrize('change', ['focus', 'recipient', 'membership', 'policy', 'delivery'])
def test_stale_confirmation_does_not_create_assignments(team, change, monkeypatch):
    conn, c = team
    current = save(c)
    envelope = operator_day_brief.prepare(c, business='b', user='u', identifier=current['id'], version=1)['approval']['envelope']
    if change == 'focus': save(c, current, focus='Другой фокус.')
    if change == 'recipient': c.execute("UPDATE users SET telegram_id='changed' WHERE id='master'")
    if change == 'membership': c.execute("UPDATE business_members SET status='revoked' WHERE user_id='master'")
    if change == 'policy': c.execute("UPDATE averageticketmatrices SET matrix_json='{}'")
    if change == 'delivery': monkeypatch.setenv('OPERATOR_DAY_BRIEF_DELIVERY_ENABLED', 'true')
    with pytest.raises((ValueError, PermissionError)): operator_day_brief.apply(c, business='b', user='u', envelope=envelope)
    c.execute('SELECT COUNT(*) n FROM journey_actions'); assert c.fetchone()['n'] == 0


def test_revision_retires_removed_recipient_tasks(team):
    conn, c = team
    current = save(c)
    envelope = operator_day_brief.preview(c, business='b', user='u', identifier=current['id'], version=1)
    operator_day_brief.apply(c, business='b', user='u', envelope=envelope)
    current = save(c, current, recipients=[{'user_id': 'admin', 'platforms': ['telegram'], 'tasks': [{'text': 'Проверить материалы.'}]}])
    operator_day_brief.apply(c, business='b', user='u', envelope=operator_day_brief.preview(c, business='b', user='u', identifier=current['id'], version=2))
    assert operator_day_brief.assignments(c, 'b', 'master') == []
    assert len(operator_day_brief.assignments(c, 'b', 'admin')) == 1


@pytest.mark.parametrize('channel', ['web', 'telegram', 'telegram_mini_app', 'max_bot', 'max_mini_app'])
def test_owner_text_voice_and_persistent_employee_commands(team, channel):
    conn, c = team
    result = operator_chat_service.process_chat(c, business_id='b', user_id='u', channel=channel, message='Фокус дня: Подготовить рабочие места.',
        payload={'request_id': 'focus'}, router=operator_core.route_operator_message)
    assert 'Подготовить рабочие места' in result['chat_response']
    c.execute("SELECT id FROM operatorconversations WHERE user_id='u' AND transport_key LIKE 'day-brief:%%'")
    stored_id = c.fetchone()['id']
    read, _ = operator_day_brief.route(c, business='b', user='u', channel=channel, message='Планёрка дня')
    assert 'Подготовить рабочие места' in read['chat_response']
    c.execute('SELECT COUNT(*) n FROM journey_actions'); assert c.fetchone()['n'] == 0
    # Voice uses the shared verified transcription path; no STT network invocation.
    audio = operator_audio.create_transcription(c, content=b'fixture', user_id='u', business_id='b', channel=channel, conversation_id=None, request_id='recording')
    c.execute("UPDATE operator_audio_assets SET status='ready',transcript='Фокус дня: Проверить качество встречи.' WHERE id=%s", (audio['asset_id'],))
    c.execute("UPDATE operator_async_jobs SET status='completed' WHERE id=%s", (audio['job_id'],))
    voiced = operator_chat_service.process_chat(c, business_id='b', user_id='u', channel=channel, message='Фокус дня: Проверить качество встречи.',
        payload={'request_id': 'voice', 'transcription_id': audio['asset_id'], 'conversation_id': audio['conversation_id']}, router=operator_core.route_operator_message)
    assert 'Проверить качество встречи' in voiced['chat_response']
    current = operator_day_brief.draft(c, 'b', 'u', identifier=stored_id)
    current = save(c, current)
    operator_day_brief.apply(c, business='b', user='u', envelope=operator_day_brief.preview(c, business='b', user='u', identifier=current['id'], version=current['version']))
    employee = operator_chat_service.process_chat(c, business_id='b', user_id='master', channel=channel, message='Мои задачи дня',
        payload={'request_id': 'employee'}, router=operator_core.route_operator_message)
    assert 'Проверить готовность' in employee['chat_response']
    completed = operator_chat_service.process_chat(c, business_id='b', user_id='master', channel=channel, message='Выполнено: 1',
        payload={'request_id': 'done'}, router=operator_core.route_operator_message)
    assert '✓ ' in completed['chat_response']


def test_native_operator_confirmation_replay_and_stale_preview(team):
    conn, c = team
    from services.operator_conversations import create_pending_operator_action
    current = save(c)
    preview = operator_day_brief.prepare(c, business='b', user='u', identifier=current['id'], version=1)
    action = create_pending_operator_action(c, conversation_id=current['id'], business_id='b', user_id='u', capability='work.day_brief', envelope=preview['approval']['envelope'])
    args = dict(action_id=action['id'], business_id='b', user_id='u', subscription_access={'capabilities': ['management']})
    result, replay = operator_core.confirm_pending_operator_action(c, **args)
    assert result['status'] == 'completed' and not replay
    assert operator_core.confirm_pending_operator_action(c, **args)[1]
    c.execute('SELECT COUNT(*) n FROM journey_actions'); assert c.fetchone()['n'] == 1
    newer = save(c, current, focus='Новый фокус.')
    another = operator_day_brief.prepare(c, business='b', user='u', identifier=newer['id'], version=2)
    action = create_pending_operator_action(c, conversation_id=current['id'], business_id='b', user_id='u', capability='work.day_brief', envelope=another['approval']['envelope'])
    save(c, newer, focus='Ещё одна правка.')
    blocked, replay = operator_core.confirm_pending_operator_action(c, **{**args, 'action_id': action['id']})
    assert blocked['status'] == 'blocked'


@pytest.mark.parametrize('platform', ['telegram', 'max'])
@pytest.mark.parametrize('outcome', ['sent', 'timeout'])
def test_provider_delivery_fence_and_duplicate_job(team, monkeypatch, platform, outcome):
    conn, c = team
    from services import operator_colleagues, max_transport
    from database_manager import DatabaseManager
    monkeypatch.setenv('OPERATOR_DAY_BRIEF_DELIVERY_ENABLED', 'true')
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN', 'fixture-token')
    monkeypatch.setenv('MAX_BOT_TOKEN', 'fixture-token')
    current = save(c)
    operator_day_brief.apply(c, business='b', user='u', envelope=operator_day_brief.preview(c, business='b', user='u', identifier=current['id'], version=1))
    conn.commit()
    c.execute('SELECT * FROM operator_async_jobs WHERE payload_json->\'briefing_delivery\'->>\'platform\'=%s', (platform,))
    job = dict(c.fetchone())
    class DB:
        def __init__(self): self.conn = conn
        def close(self): pass
    monkeypatch.setattr('database_manager.DatabaseManager', DB)
    calls = []
    def deliver(*args, **kwargs):
        calls.append(kwargs)
        c.execute('SELECT payload_json FROM operator_async_jobs WHERE id=%s', (job['id'],))
        assert c.fetchone()['payload_json']['briefing_delivery']['state'] == 'unknown'
        if outcome == 'timeout':
            if platform == 'max': raise max_transport.MaxTransportError('timeout', uncertain=True)
            raise operator_colleagues.requests.Timeout('fixture timeout')
        return {'message': {'body': {'mid': 'max-sent'}}}
    if platform == 'max': monkeypatch.setattr(max_transport.MaxTransport, 'send', deliver)
    else:
        def telegram(*args, **kwargs):
            deliver(*args, **kwargs)
            return type('Response', (), {'status_code': 200, 'json': lambda self: {'ok': True, 'result': {'message_id': 7}}})()
        monkeypatch.setattr(operator_colleagues.requests, 'post', telegram)
    first = operator_colleagues.process_job(job)
    assert first['delivery_state'] == ('sent' if outcome == 'sent' else 'unknown')
    second = operator_colleagues.process_job(job)
    assert second['delivery_state'] == first['delivery_state']
    assert len(calls) == 1


def test_owner_handoff_and_voice_safe_navigation(team):
    conn, c = team
    current = save(c)
    for platform in ['telegram', 'max']:
        link = operator_work_handoff.prepare_handoff(c, user_id='u', business_id='b', platform=platform,
            item_id=current['id'], item_type='day_brief', request_id=str(uuid.uuid4()))
        resumed = operator_work_handoff.resume_handoff(c, user_id='u', platform=platform, token=link['url'].split('start=')[1])
        assert resumed['item_type'] == 'day_brief' and 'screen=work_journal' in resumed['return_url']
    c.execute('SELECT COUNT(*) n FROM journey_actions'); assert c.fetchone()['n'] == 0


def test_deep_link_uses_selected_day_and_blocks_other_employee(team):
    conn, c = team
    current = save(c)
    operator_day_brief.apply(c, business='b', user='u', envelope=operator_day_brief.preview(c, business='b', user='u', identifier=current['id'], version=1))
    action = operator_day_brief.assignments(c, 'b', 'master')[0]
    owner = operator_day_brief.overview(c, business='b', user='u', item_id=current['id'])
    assert owner['date'] == '2026-10-17'
    employee = operator_day_brief.overview(c, business='b', user='master', item_id=str(action['id']))
    assert employee['date'] == '2026-10-17' and employee['draft'] is None
    with pytest.raises(PermissionError): operator_day_brief.overview(c, business='b', user='admin', item_id=str(action['id']))
    with pytest.raises(PermissionError): operator_day_brief.overview(c, business='b', user='master', item_id=current['id'])


def test_voice_api_retry_reuses_draft_without_reusing_consumed_audio(team, monkeypatch):
    from flask import Flask, Blueprint
    from api import operator_day_brief_api
    conn, c = team
    class DB:
        def __init__(self): self.conn = conn
        def close(self): pass
    monkeypatch.setattr(operator_day_brief_api, 'DatabaseManager', DB)
    monkeypatch.setattr(operator_day_brief_api, 'require_auth_from_request', lambda: {'user_id': 'u'})
    audio = operator_audio.create_transcription(c, content=b'fixture', user_id='u', business_id='b', channel='max_mini_app', conversation_id=None, request_id='voice-api')
    c.execute("UPDATE operator_audio_assets SET status='ready',transcript='Фокус голосом.' WHERE id=%s", (audio['asset_id'],))
    c.execute("UPDATE operator_async_jobs SET status='completed' WHERE id=%s", (audio['job_id'],))
    conn.commit()
    app = Flask(__name__);bp = Blueprint('day', __name__);operator_day_brief_api.register_day_brief_routes(bp);app.register_blueprint(bp)
    body = {'business_id': 'b', 'focus': 'Фокус голосом.', 'date': '2026-10-17', 'request_id': str(uuid.uuid4()), 'version': 0, 'recipients': [], 'transcription_id': audio['asset_id'], 'conversation_id': audio['conversation_id']}
    first = app.test_client().post('/day-brief', json=body)
    assert first.status_code == 200
    repeated = app.test_client().post('/day-brief', json=body)
    assert repeated.status_code == 200 and repeated.json['draft']['id'] == first.json['draft']['id']
    assert repeated.json['draft']['idempotent']


def test_bootstrap_resolves_only_own_brief_and_correct_business(team):
    from services.operator_mobile_deep_links import resolve_mobile_deep_link
    conn, c = team
    current = save(c)
    args = dict(scope={'kind': 'business', 'id': 'b', 'business_ids': ['b']}, navigation=[{'key': 'work_journal', 'status': 'available'}], screen='work_journal', item_type='day_brief', item_id=current['id'])
    assert resolve_mobile_deep_link(c, **args, user_id='u')['item_id'] == current['id']
    assert resolve_mobile_deep_link(c, **args, user_id='master')['fallback_reason'] == 'object_forbidden'
    assert resolve_mobile_deep_link(c, **args)['fallback_reason'] == 'object_forbidden'
    assert resolve_mobile_deep_link(c, **{**args, 'scope': {'kind': 'business', 'business_ids': ['other']}}, user_id='u')['fallback_applied']


def test_long_bot_preview_requires_complete_review_in_miniapp():
    value = {'status': 'approval_required', 'capability': 'work.day_brief', 'chat_response': 'x' * 5000,
        'approval': {'envelope': {'private': 'not-executed'}}, 'work_return_url': 'https://localos.pro/telegram/control?screen=work_journal'}
    result = operator_day_brief.chat_result(value)
    assert result['status'] == 'completed' and 'approval' not in result
    assert 'полный текст' in result['chat_response'] and result['work_return_url'] == value['work_return_url']


def test_employee_can_end_discussion_without_changing_tasks(team):
    conn, c = team
    result, pending = operator_day_brief.route(c, business='b', user='master', channel='max_bot',
        message='Отмена', pending={'day_brief_employee': [{'action_id': 'not-used'}]})
    assert result['status'] == 'cancelled' and pending == {}


@pytest.mark.parametrize('channel', ['telegram', 'max_bot'])
def test_bot_owner_selects_tasks_and_native_confirmation_before_employee_receives_them(team, channel):
    conn, c = team
    def chat(message, key):
        return operator_chat_service.process_chat(c, business_id='b', user_id='u', channel=channel, message=message,
            payload={'request_id': key}, router=operator_core.route_operator_message)
    first = chat('Фокус дня: Внимательно встречаем клиентов.', 'focus-bot')
    people = operator_day_brief.members(c, 'b')
    index = next(i + 1 for i, row in enumerate(people) if row['id'] == 'master')
    selected = chat('Сотрудники: ' + str(index), 'choose-bot')
    assert 'Внимательно встречаем клиентов' in selected['chat_response']
    assert operator_day_brief.assignments(c, 'b', 'master') == []
    prepared = chat('Подготовь передачу задач', 'prepare-bot')
    assert prepared['status'] == 'approval_required' and prepared['approval']['action_id']
    assert operator_day_brief.assignments(c, 'b', 'master') == []
    completed, replay = operator_core.confirm_pending_operator_action(c, action_id=prepared['approval']['action_id'], business_id='b', user_id='u', subscription_access={'capabilities': ['management']})
    assert completed['status'] == 'completed' and not replay
    assert len(operator_day_brief.assignments(c, 'b', 'master')) == 1


def test_operator_only_entitlement_does_not_grant_team_brief(team, monkeypatch):
    conn, c = team
    actor = operator_audio.authorize_actor
    def content_only(cursor, user, business):
        who, _ = actor(cursor, user, business)
        return who, {'capabilities': ['operator', 'social_content']}
    monkeypatch.setattr(operator_audio, 'authorize_actor', content_only)
    with pytest.raises(PermissionError, match='тарифе'):
        operator_day_brief.overview(c, business='b', user='u', day='2026-10-17')


def test_cancel_in_bot_rejects_same_preview_created_in_miniapp(team):
    conn, c = team
    from services.operator_conversations import create_pending_operator_action
    current = save(c)
    preview = operator_day_brief.prepare(c, business='b', user='u', identifier=current['id'], version=1)
    action = create_pending_operator_action(c, conversation_id=current['id'], business_id='b', user_id='u', capability='work.day_brief', envelope=preview['approval']['envelope'])
    result, context = operator_day_brief.route(c, business='b', user='u', channel='max_bot', message='Отмена',
        conversation_id='different-bot-conversation', pending={'selected_day_brief': {'id': current['id'], 'version': 1}})
    assert result['status'] == 'cancelled' and context == {}
    blocked, replay = operator_core.confirm_pending_operator_action(c, action_id=action['id'], business_id='b', user_id='u', subscription_access={'capabilities': ['management']})
    assert blocked['status'] == 'blocked'
    c.execute('SELECT COUNT(*) n FROM journey_actions'); assert c.fetchone()['n'] == 0


def test_private_assignments_are_excluded_from_legacy_business_lists_and_commands(team, monkeypatch):
    from services import operator_mobile_today, lead_journey_service
    conn, c = team
    current = save(c)
    operator_day_brief.apply(c, business='b', user='u', envelope=operator_day_brief.preview(c, business='b', user='u', identifier=current['id'], version=1))
    private = operator_day_brief.assignments(c, 'b', 'master')[0]
    common = str(uuid.uuid4())
    c.execute("INSERT INTO journey_actions(id,business_id,user_id,flow_type,entity_type,action_type,title,description,cta_label,payload_json,cta_target_json,dedupe_key) VALUES(%s,'b','u','maps','service','inspect','Общая задача','Проверка карточки','Открыть','{}','{}',%s)", (common, 'common:' + common))
    monkeypatch.setattr(operator_mobile_today, 'journey_enabled', lambda: True)
    monkeypatch.setattr(operator_mobile_today, '_table_exists', lambda cursor, name: True)
    visible = operator_mobile_today._load_journey_actions(c, {'kind': 'business', 'id': 'b', 'business_ids': ['b']})
    assert [row['id'] for row in visible] == [common]
    with pytest.raises(lead_journey_service.JourneyError): lead_journey_service.load_action(c, action_id=str(private['id']), business_id='b')
    assert str(lead_journey_service.load_action(c, action_id=common, business_id='b')['id']) == common
    c.execute("UPDATE journey_actions SET status='completed'")
    history = lead_journey_service.list_actions(c, business_id='b', history=True)
    assert [row['id'] for row in history] == [common]


@pytest.mark.parametrize('utterance', ['Фокус дня внимательно встречаем клиентов.', 'Фокус дня. Внимательно встречаем клиентов.', 'Фокус на день — внимательно встречаем клиентов.'])
def test_spoken_focus_does_not_require_dictating_colon(team, utterance):
    conn, c = team
    assert operator_core.should_route_operator_message(utterance)
    result = operator_chat_service.process_chat(c, business_id='b', user_id='u', channel='max_bot', message=utterance,
        payload={'request_id': str(uuid.uuid4())}, router=operator_core.route_operator_message)
    assert 'внимательно встречаем клиентов' in result['chat_response'].casefold()
    current = operator_day_brief.draft(c, 'b', 'u', day=result.get('date') or operator_day_brief.work_journal.local_day(c, 'b'))
    assert current['focus'].casefold() == 'внимательно встречаем клиентов.'
    c.execute('SELECT COUNT(*) n FROM journey_actions'); assert c.fetchone()['n'] == 0


def test_replayed_brief_keeps_completed_task_with_production_partial_index(team):
    _,c=team
    current=save(c)
    envelope=operator_day_brief.preview(c,business='b',user='u',identifier=current['id'],version=1)
    result=operator_day_brief.apply(c,business='b',user='u',envelope=envelope)
    row=operator_day_brief.assignments(c,'b','master')[0]
    task=row['payload_json']['tasks'][0]
    operator_day_brief.complete_task(c,business='b',user='master',action_id=str(row['id']),task_id=task['id'],version=row['version'],done=True)
    assert operator_day_brief.apply(c,business='b',user='u',envelope=envelope)['action_ids']==result['action_ids']
    c.execute('SELECT id,status FROM journey_actions');rows=c.fetchall()
    assert len(rows)==1 and rows[0]['status']=='completed'
    assert operator_day_brief.assignments(c,'b','master')[0]['payload_json']['tasks'][0]['done']


def test_delivery_status_is_scoped_metadata_and_does_not_claim_sent_without_receipt(team,monkeypatch):
    _,c=team
    monkeypatch.setenv('OPERATOR_DAY_BRIEF_DELIVERY_ENABLED','true')
    current=save(c)
    operator_day_brief.apply(c,business='b',user='u',envelope=operator_day_brief.preview(c,business='b',user='u',identifier=current['id'],version=1))
    employee=operator_day_brief.overview(c,business='b',user='master')
    assert {item['state'] for item in employee['deliveries']}=={'queued'}
    assert all(set(item)=={'action_id','platform','state'} for item in employee['deliveries'])
    assert operator_day_brief.overview(c,business='b',user='admin')['deliveries']==[]
    c.execute("UPDATE operator_async_jobs SET payload_json=jsonb_set(payload_json,'{briefing_delivery,state}','\"sent\"'::jsonb)")
    assert {item['state'] for item in operator_day_brief.overview(c,business='b',user='master')['deliveries']}=={'unknown'}
    c.execute("UPDATE operator_async_jobs SET payload_json=jsonb_set(payload_json,'{briefing_delivery,provider_message_id}','\"receipt\"'::jsonb)")
    assert {item['state'] for item in operator_day_brief.overview(c,business='b',user='master')['deliveries']}=={'sent'}

@pytest.mark.parametrize('channel', ['telegram', 'max_bot'])
def test_tomorrow_focus_prepares_without_schedule_or_delivery(team, channel):
    conn, c = team
    result, pending = operator_day_brief.route(c, business='b', user='u', channel=channel,
        message='Планёрка на завтра: фокус — внимательная консультация. Подготовь предварительный вариант, сотрудникам ничего не отправляй.')
    current = operator_day_brief.draft(c, 'b', 'u', identifier=pending['selected_day_brief']['id'])
    assert current['date'] == '2026-10-18'
    assert current['focus'] == 'внимательная консультация'
    assert not current['recipients']
    assert 'внимательная консультация' in result['chat_response']
    c.execute('SELECT COUNT(*) n FROM journey_actions'); assert c.fetchone()['n'] == 0
    c.execute('SELECT COUNT(*) n FROM operator_async_jobs'); assert c.fetchone()['n'] == 0


def test_selected_brief_does_not_capture_crm_or_partner_request(team):
    conn, c = team
    current = save(c)
    pending = {'selected_day_brief': {'id': current['id']}}
    for message in ['Хочу подключить CRM DIKIDI', 'Покажи действующих партнёров', 'Выручка за неделю 120000 рублей']:
        assert operator_day_brief.route(c, business='b', user='u', channel='max_bot', pending=pending, message=message) is None
