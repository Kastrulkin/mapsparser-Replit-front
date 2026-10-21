"""Real subscription and tenant authorization; isolated PostgreSQL, no provider calls."""
from datetime import datetime, timedelta
import uuid
import pytest
from tests.test_operator_day_brief_pg import team, save
from tests.test_operator_workday import workday
from tests.test_work_journal_pg import journal
from tests.test_finance_daily_pg import daily
from tests.test_operator_voice_pg import pg
from services import operator_audio, operator_day_brief, work_journal, work_review, operator_core
from subscription_manager import build_subscription_capabilities

REAL_AUTHORIZE = operator_audio.authorize_actor

@pytest.fixture
def ordinary(team, monkeypatch):
    conn, c = team
    c.execute("ALTER TABLE journey_actions ADD CONSTRAINT ck_journey_actions_flow CHECK (flow_type IS NOT NULL)")
    import importlib.util
    from pathlib import Path
    from alembic import op
    monkeypatch.setattr(op, 'execute', c.execute)
    spec=importlib.util.spec_from_file_location('team_review_migration',Path(__file__).parents[1]/'alembic_migrations/versions/20260914_work_review.py')
    migration=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    migration.upgrade()
    c.execute("ALTER TABLE businesses ADD COLUMN is_active BOOLEAN DEFAULT TRUE, ADD COLUMN subscription_tier TEXT DEFAULT 'starter', ADD COLUMN subscription_status TEXT DEFAULT 'active', ADD COLUMN subscription_ends_at TIMESTAMP")
    monkeypatch.setattr(operator_audio, 'authorize_actor', REAL_AUTHORIZE)
    monkeypatch.setenv('OPERATOR_TEAM_WORK_ENABLED', 'true')
    for name in ['OPERATOR_WORKDAY_BUSINESS_IDS','OPERATOR_WORK_JOURNAL_BUSINESS_IDS','OPERATOR_WORK_REVIEW_BUSINESS_IDS','OPERATOR_VOICE_BUSINESS_IDS']:
        monkeypatch.delenv(name, raising=False)
    from database_manager import DBCursorWrapper
    return conn, DBCursorWrapper(c)

@pytest.mark.parametrize('tier', ['starter','professional','concierge','elite','promo'])
def test_brief_and_journal_available_on_every_active_plan(ordinary, tier):
    _, c = ordinary
    c.execute('UPDATE businesses SET subscription_tier=%s', (tier,))
    owner = operator_day_brief.overview(c, business='b', user='u')
    employee = operator_day_brief.overview(c, business='b', user='master')
    assert owner['can_manage'] and not employee['can_manage']
    assert employee['can_complete']
    entry = work_journal.save_note(c,'b','master','max_bot',None,'note-'+tier,'Грязные окна',{'quote':'Грязные окна','outcome':'note'})
    assert entry['user_id'] == 'master'
    assert work_journal.list_entries(c,'b','u')[0]['id'] == entry['id']
    assert work_review.enabled('b')
    assert operator_audio.enabled('transcription', 'b')
    assert operator_audio.enabled('speech', 'b')

@pytest.mark.parametrize('capability', ['work.journal','work.policy','work.schedule','work.day_brief','work.owner_action','work.colleague'])
def test_team_tools_are_not_management_only(capability):
    access = build_subscription_capabilities(tier='starter', status='active')
    assert operator_core.operator_subscription_block(access, capability) is None
    for paid in ['partnerships.search', 'finance.read', 'agents.run', 'average_ticket.manage']:
        assert operator_core.operator_subscription_block(access, paid)['status'] == 'blocked'

@pytest.mark.parametrize('status', ['cancelled','expired'])
def test_inactive_subscription_cannot_write_journal_or_brief(ordinary, status):
    _, c = ordinary
    c.execute('UPDATE businesses SET subscription_status=%s', (status,))
    with pytest.raises(PermissionError): operator_day_brief.overview(c,business='b',user='u')
    with pytest.raises(PermissionError): work_journal.scope(c,'b','master',write=True)


def test_expired_date_does_not_use_active_status(ordinary):
    _, c = ordinary
    c.execute('UPDATE businesses SET subscription_ends_at=%s', (datetime.now()-timedelta(days=1),))
    with pytest.raises(PermissionError): operator_day_brief.overview(c,business='b',user='u')


def test_staff_scope_and_owner_review_are_real_not_admin_emulation(ordinary):
    _, c = ordinary
    actor, access = REAL_AUTHORIZE(c,'master','b')
    assert not actor['is_superadmin'] and actor['role']=='business_user'
    assert 'management' not in access['capabilities']
    current=save(c)
    operator_day_brief.apply(c,business='b',user='u',envelope=operator_day_brief.preview(c,business='b',user='u',identifier=current['id'],version=1))
    assert len(operator_day_brief.assignments(c,'b','master'))==1
    assert operator_day_brief.assignments(c,'b','viewer')==[]
    with pytest.raises(PermissionError): save(c,recipients=[{'user_id':'outsider','tasks':[]}])
    with pytest.raises(PermissionError): operator_day_brief.save(c,business='b',user='master',payload={})
    with pytest.raises(PermissionError): work_journal.scope(c,'b','viewer',write=True)
    with pytest.raises(PermissionError): work_review.require_review(c,'b','master')
    with pytest.raises(PermissionError): work_journal.scope(c,'other','master')
    c.execute("UPDATE business_members SET status='revoked' WHERE user_id='master'")
    with pytest.raises(PermissionError): operator_day_brief.overview(c,business='b',user='master')


def test_rollout_respects_voice_kill_switch(ordinary, monkeypatch):
    monkeypatch.setenv('OPERATOR_VOICE_INPUT_ENABLED','false')
    assert not operator_audio.enabled('transcription','b')
    assert operator_audio.enabled('speech','b')

@pytest.mark.parametrize('channel',['web','telegram','telegram_mini_app','max_bot','max_mini_app'])
def test_employee_plain_journal_needs_no_generation_or_admin(ordinary, channel, monkeypatch):
    _,c=ordinary
    from services import operator_chat_service
    def forbidden(*args, **kwargs):
        raise AssertionError('Plain observation must not invoke a paid planner')
    monkeypatch.setattr(operator_core,'run_paid_operator_tool_loop',forbidden)
    message='У входа грязные окна. Нужен мойщик окон.'
    result=operator_chat_service.process_chat(c,business_id='b',user_id='master',channel=channel,message=message,
        payload={'request_id':'plain-'+channel,'input_context':'work_journal'},router=operator_core.route_operator_message)
    assert result['status']=='completed'
    row=work_journal.list_entries(c,'b','u')[0]
    assert row['facts_json']['quote']==message and row['user_id']=='master'
    replay=operator_chat_service.process_chat(c,business_id='b',user_id='master',channel=channel,message=message,
        payload={'request_id':'plain-'+channel,'input_context':'work_journal'},router=operator_core.route_operator_message)
    assert result['message_id']==replay['message_id']
    assert len(work_journal.list_entries(c,'b','u'))==1


def test_global_rollout_does_not_subscribe_clients_to_notifications(ordinary, monkeypatch):
    _,c=ordinary
    from services import work_review_notifications, business_input_settings
    from datetime import timezone
    monkeypatch.setattr(business_input_settings,'resolve',lambda *args:{'timezone':'Europe/Moscow'})
    entry=work_journal.save_note(c,'b','master','telegram',None,'urgent-note','Срочно: грязные окна',{'quote':'Срочно: грязные окна','outcome':'note'})
    assert work_review.digest_settings(c,'b','u')['enabled'] is False
    work_review_notifications.collect(c,datetime.now(timezone.utc))
    c.execute('SELECT COUNT(*) n FROM journey_actions');assert c.fetchone()['n']==0
    work_review.digest_settings(c,'b','u',{'enabled':True,'local_time':'23:59'})
    assert work_review.digest_settings(c,'b','u')['enabled'] is True
    work_review_notifications.collect(c,datetime.now(timezone.utc))
    c.execute('SELECT COUNT(*) n FROM journey_actions');assert c.fetchone()['n']==1
    work_review_notifications.collect(c,datetime.now(timezone.utc))
    c.execute('SELECT COUNT(*) n FROM journey_actions');assert c.fetchone()['n']==1

@pytest.mark.parametrize('change',[None,'opt_out','access_revoked','binding_revoked','stale_version','closed','text_changed','category_disabled','subscription_expired'])
def test_max_journal_outbox_rechecks_current_scope_and_opt_in(ordinary, change):
    _,c=ordinary
    from services import work_review_notifications, max_notifications
    c.execute('ALTER TABLE users ADD COLUMN email TEXT')
    c.execute('CREATE TABLE max_webhook_events(event_key TEXT PRIMARY KEY,payload_json JSONB)')
    work_journal.save_note(c,'b','master','max_bot',None,'urgent-max','Срочно: грязные окна',{'quote':'Срочно: грязные окна','outcome':'note'})
    work_review.digest_settings(c,'b','u',{'enabled':True,'local_time':'23:59'})
    work_review_notifications.collect(c)
    actor={'id':'u','max_id':'owner-max'}
    scope={'id':'b'}
    max_notifications.collect_work_journal_notifications(c,actor=actor,scope=scope,preference_scope='business:b')
    max_notifications.collect_work_journal_notifications(c,actor=actor,scope=scope,preference_scope='business:b')
    c.execute('SELECT payload_json FROM max_webhook_events');rows=c.fetchall()
    assert len(rows)==1
    payload=rows[0]['payload_json']
    assert payload['screen']=='work_journal' and payload['category']=='tasks'
    if change=='opt_out':work_review.digest_settings(c,'b','u',{'enabled':False,'local_time':'23:59'})
    if change=='access_revoked':c.execute("UPDATE businesses SET owner_id='admin'")
    if change=='binding_revoked':c.execute("UPDATE max_identities SET revoked_at=NOW() WHERE user_id='u'")
    if change=='stale_version':c.execute('UPDATE journey_actions SET version=version+1')
    if change=='closed':c.execute("UPDATE journey_actions SET status='completed'")
    if change=='text_changed':c.execute("UPDATE journey_actions SET title='Изменено'")
    if change=='category_disabled':
        c.execute('CREATE TABLE maxcontrolpreferences(user_id TEXT,notification_preferences_json JSONB)')
        c.execute('INSERT INTO maxcontrolpreferences VALUES (%s,%s::jsonb)',('u','{"business:b":{"tasks":false}}'))
    if change=='subscription_expired':c.execute("UPDATE businesses SET subscription_status='cancelled'")
    ready=max_notifications.prepare_notification(c,payload)
    assert bool(ready) is (change is None)


def test_disabling_journal_delivery_suppresses_pending_telegram_notification(ordinary):
    _,c=ordinary
    from services import work_review_notifications
    work_review.digest_settings(c,'b','u',{'enabled':True,'local_time':'23:59'})
    assert work_review_notifications.recipient_allowed(c,'b','u')
    work_review.digest_settings(c,'b','u',{'enabled':False,'local_time':'23:59'})
    assert not work_review_notifications.recipient_allowed(c,'b','u')


def test_daily_journal_digest_works_through_production_cursor_adapter(ordinary,monkeypatch):
    _,raw=ordinary
    from services import work_review_notifications,business_input_settings
    from datetime import timezone
    c=raw
    monkeypatch.setattr(business_input_settings,'resolve',lambda *args:{'timezone':'Europe/Moscow'})
    work_journal.save_note(c,'b','master','telegram',None,'daily-real-cursor','Грязные окна',{'quote':'Грязные окна','outcome':'note'})
    work_review.digest_settings(c,'b','u',{'enabled':True,'local_time':'00:00'})
    moment=datetime.now(timezone.utc)+timedelta(days=1)
    work_review_notifications.collect(c,moment)
    work_review_notifications.collect(c,moment)
    c.execute("SELECT COUNT(*) n FROM journey_actions WHERE entity_type='work_digest'")
    assert c.fetchone()['n']==1


def test_expired_client_can_read_history_but_cannot_mutate_or_enable_delivery(ordinary):
    _,c=ordinary
    entry=work_journal.save_note(c,'b','master','telegram',None,'before-expiry','Грязные окна',{'quote':'Грязные окна','outcome':'note'})
    c.execute("UPDATE businesses SET subscription_status='expired'")
    assert work_journal.list_entries(c,'b','master')[0]['id']==entry['id']
    assert work_review.list_inbox(c,'b','u')[0]['id']==entry['id']
    with pytest.raises(PermissionError):work_review.decision(c,'b','u',entry['id'],{'request_id':'after-expiry','version':1,'status':'in_progress'})
    from services.work_review_notifications import recipient_allowed
    assert not recipient_allowed(c,'b','u')


@pytest.mark.parametrize('user',['u','viewer'])
def test_global_team_rollout_keeps_read_only_chat_access(ordinary,user):
    _,c=ordinary
    from services import operator_chat_service
    if user=='u':c.execute("UPDATE businesses SET subscription_status='expired'")
    def read(*args,**kwargs):return {'status':'completed','capability':'operator.help','chat_response':'Справка'},{}
    result=operator_chat_service.process_chat(c,business_id='b',user_id=user,channel='web',message='Что ты умеешь?',payload={'request_id':'read-only'},router=read)
    assert result['status']=='completed'
    with pytest.raises(PermissionError):work_journal.scope(c,'b',user,write=True)


@pytest.mark.parametrize('channel',['telegram','max_bot'])
def test_explicit_journal_note_overrides_old_partner_context_without_interpreting_the_quote(ordinary,channel,monkeypatch):
    _,c=ordinary
    from services import operator_chat_service,operator_work_journal,operator_partner_work
    from services.operator_conversations import get_or_create_operator_conversation,set_operator_pending_context
    conversation=get_or_create_operator_conversation(c,business_id='b',user_id='master',channel=channel)
    set_operator_pending_context(c,str(conversation['id']),{'capability':'partnerships.selected','selected_partner':{'item_id':'not-a-visible-partner'}})
    def forbidden(*args,**kwargs):raise AssertionError('A journal quote is data, never a command')
    monkeypatch.setattr(operator_work_journal,'ban_request',forbidden)
    monkeypatch.setattr(operator_partner_work,'route',forbidden)
    monkeypatch.setattr(operator_core,'run_paid_operator_tool_loop',forbidden)
    quote='Клиент сказал: не предлагайте уход. У входа грязные окна.'
    result=operator_chat_service.process_chat(c,business_id='b',user_id='master',channel=channel,message='В журнал: '+quote,payload={'request_id':'explicit-note'},router=operator_core.route_operator_message)
    assert result['status']=='completed' and 'selected_partner' not in result
    assert result['journal_entries'][0]['facts_json']['quote']==quote
    c.execute('SELECT COUNT(*) n FROM operatoractions');assert c.fetchone()['n']==0
