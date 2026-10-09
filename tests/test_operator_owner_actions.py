from datetime import datetime, timezone
import pytest
from tests.test_operator_workday import workday
from tests.test_work_journal_pg import journal
from tests.test_finance_daily_pg import daily
from tests.test_operator_voice_pg import pg
from services import operator_owner_actions

actions=operator_owner_actions


@pytest.fixture
def owner_day(workday,monkeypatch):
    conn,c=workday
    c.execute('ALTER TABLE businesses ADD COLUMN is_active BOOLEAN DEFAULT TRUE, ADD COLUMN working_hours TEXT')
    c.execute("UPDATE businesses SET working_hours='09:00–19:00'")
    c.execute('''ALTER TABLE journey_actions ADD COLUMN status TEXT DEFAULT 'ready', ADD COLUMN version INT DEFAULT 1,
        ADD COLUMN created_at TIMESTAMPTZ DEFAULT NOW(), ADD COLUMN updated_at TIMESTAMPTZ DEFAULT NOW()''')
    c.execute('CREATE TABLE telegramcontrolpreferences(user_id TEXT PRIMARY KEY,telegram_id TEXT,notification_preferences_json JSONB)')
    c.execute("INSERT INTO telegramcontrolpreferences VALUES ('u','123','{}')")
    monkeypatch.setattr(actions,'now',lambda:datetime(2026,10,9,12,tzinfo=timezone.utc))
    return conn,c


def arguments(kind='reminder',**extra):
    return dict(kind=kind,date='2026-10-10',time='10:00',timezone='Europe/Tallinn',title='Проверить шампунь',
        quote='Напомни завтра в 10:00 проверить шампунь',text='Проверить шампунь',**extra)


def test_reminder_preview_persist_read_replay_cancel(owner_day):
    _,c=owner_day
    args=arguments()
    prepared=actions.prepare(c,'b','u',args,args['quote'])
    assert prepared['status']=='approval_required'
    assert 'Сегодня' in prepared['chat_response']
    assert not actions.read(c,'b','u',{})['owner_actions']
    saved=actions.apply(c,'b','u',prepared['approval']['envelope'],'approved')
    assert saved['owner_action_id']
    assert actions.apply(c,'b','u',prepared['approval']['envelope'],'again')['idempotent']
    rows=actions.read(c,'b','u',{})['owner_actions']
    assert len(rows)==1 and rows[0]['payload_json']['timezone']=='Europe/Tallinn'
    assert rows[0]['due_at'].astimezone(timezone.utc).hour==7
    cancel=actions.prepare(c,'b','u',{'operation':'cancel','id':str(rows[0]['id']),'version':rows[0]['version']},'Отмени задачу')
    actions.apply(c,'b','u',cancel['approval']['envelope'],'cancel')
    assert not actions.read(c,'b','u',{})['owner_actions']


def test_task_deadline_does_not_create_sale_or_booking(owner_day):
    _,c=owner_day
    args=arguments('task')
    preview=actions.prepare(c,'b','u',args,args['quote'])
    actions.apply(c,'b','u',preview['approval']['envelope'],'task')
    assert actions.read(c,'b','u',{})['owner_actions'][0]['payload_json']['kind']=='task'
    c.execute('SELECT COUNT(*) n FROM financialtransactions');assert c.fetchone()['n']==0
    c.execute('SELECT COUNT(*) n FROM bookings');assert c.fetchone()['n']==2


def test_hours_date_only_and_stale_permanent_hours(owner_day):
    _,c=owner_day
    quote='Завтра работаем с 11:00 до 16:00'
    args={'kind':'hours','date':'2026-10-10','time':'11:00','end':'16:00','quote':quote}
    preview=actions.prepare(c,'b','u',args,quote)
    actions.apply(c,'b','u',preview['approval']['envelope'],'hours')
    assert actions.effective_hours(c,'b','2026-10-10')['end']=='16:00'
    assert actions.effective_hours(c,'b','2026-10-11') is None
    assert actions.permanent_hours(c,'b')=='09:00–19:00'
    quote='11 октября 2026 работаем с 11:00 до 16:00'
    next_preview=actions.prepare(c,'b','u',{**args,'date':'2026-10-11','quote':quote},quote)
    c.execute("UPDATE businesses SET working_hours='10:00–20:00'")
    with pytest.raises(ValueError,match='Постоянный график изменился'):
        actions.apply(c,'b','u',next_preview['approval']['envelope'],'stale')


def test_delivery_requires_explicit_channel_and_current_recipient(owner_day):
    _,c=owner_day
    args=arguments(delivery='telegram')
    with pytest.raises(ValueError,match='явно'):actions.prepare(c,'b','u',args,args['quote'])
    args['quote']+=' в Telegram'
    prepared=actions.prepare(c,'b','u',args,args['quote'])
    c.execute("UPDATE telegramcontrolpreferences SET telegram_id='456'")
    with pytest.raises(ValueError,match='Telegram изменился'):actions.apply(c,'b','u',prepared['approval']['envelope'],'stale')


def test_permissions_and_lost_access_fail_closed(owner_day):
    _,c=owner_day
    args=arguments()
    with pytest.raises(PermissionError):actions.prepare(c,'b','viewer',args,args['quote'])
    with pytest.raises(PermissionError):actions.prepare(c,'other','u',args,args['quote'])
    prepared=actions.prepare(c,'b','admin',args,args['quote'])
    c.execute("UPDATE business_members SET status='revoked' WHERE user_id='admin'")
    with pytest.raises(PermissionError):actions.apply(c,'b','admin',prepared['approval']['envelope'],'lost')


def test_invalid_past_and_invented_fields_do_not_create_actions(owner_day):
    _,c=owner_day
    args=arguments()
    with pytest.raises(ValueError):actions.prepare(c,'b','u',{**args,'date':'2026-10-11'},args['quote'])
    with pytest.raises(ValueError):actions.prepare(c,'b','u',{**args,'time':'13:00'},args['quote'])
    with pytest.raises(ValueError):actions.prepare(c,'b','u',{**args,'date':'2026-10-09'},'Напомни сегодня в 10:00')
    assert not actions.read(c,'b','u',{})['owner_actions']


def test_notification_guard_stops_cancelled_target_or_in_app(owner_day):
    from services.journey_action_notifications import owner_delivery_allowed
    _,c=owner_day
    row={'business_id':'b','user_id':'u','telegram_id':'123','payload_json':{'delivery':'telegram','telegram_id':'123'}}
    assert owner_delivery_allowed(c,row)
    assert not owner_delivery_allowed(c,{**row,'payload_json':{'delivery':'in_app'}})
    c.execute("UPDATE telegramcontrolpreferences SET telegram_id='456'")
    assert not owner_delivery_allowed(c,row)


def test_compiled_summary_uses_real_read_capability():
    from services.agent_blueprint_creation import _finance_summary_draft
    draft=_finance_summary_draft('Каждый день сводка выручки и числа чеков',
        {'execution_mode':'scheduled','trigger':'schedule.daily','schedule':{'time':'18:00','timezone':'Europe/Moscow'}})
    version=draft['version_payload']
    assert version['steps'][0]['capability']=='finance.summary.read'
    assert version['schedule']['time']=='18:00'
    assert version['capability_allowlist']==['finance.summary.read']
    assert not version['required_integration_bindings']


def test_transient_editorial_notes_do_not_leak_into_promotions():
    from services.operator_editorial import durable_note
    from services.operator_social_post_generation import validate_operational_claims
    assert not durable_note({'text':'Сегодня свободны два кресла с 15:00 до 17:00'})
    assert durable_note({'text':'У нас четыре кресла и бережный уход'})
    with pytest.raises(ValueError):validate_operational_claims('Сегодня свободны два кресла','Акция 10% на SPA-маску')


def test_clarification_stops_after_first_tool_and_refusal_is_not_completed():
    from services.operator_tool_loop import run_operator_tool_loop
    calls=[]
    def plan(state):
        calls.append(state)
        return {'action':'tool_call','tool':'content.plan','arguments':{}}
    outcome=run_operator_tool_loop(business_id='b',user_id='u',message='Подготовь план',tools=[
        {'name':'content.plan','risk_class':'write_internal','execute':lambda a:{'status':'clarification_required','chat_response':'Сколько постов в неделю?'}}],planner=plan)
    assert outcome['status']=='clarification_required' and len(calls)==1
    outcome=run_operator_tool_loop(business_id='b',user_id='u',message='Можешь сделать напоминание?',tools=[],
        planner=lambda s:{'action':'final','message':'Не могу создать напоминание: нет инструмента.'})
    assert outcome['status']=='unsupported'


def test_demo_session_cannot_prepare_or_confirm(owner_day):
    _,c=owner_day
    args=arguments()
    for session in ({'session_kind':'demo'},{'impersonating':True},{'impersonated_by':'staff'}):
        tool=actions.tools(c,'b','u',args['quote'],session)[0]
        assert tool['prepare_approval'](args)['status']=='blocked'
        envelope=actions.prepare(c,'b','u',args,args['quote'])['approval']['envelope']
        with pytest.raises(PermissionError):actions.apply(c,'b','u',envelope,'approval',session)
    assert not actions.read(c,'b','u',{})['owner_actions']


def test_content_plan_followup_preserves_entire_request(monkeypatch):
    from services import operator_core, operator_workday
    monkeypatch.setattr(operator_workday,'enabled',lambda business:False)
    captured=[]
    def create(**arguments):
        captured.append(arguments['message'])
        return {'status':'clarification_required' if len(captured)==1 else 'completed','chat_response':'Частота?' if len(captured)==1 else 'Создано'}
    monkeypatch.setattr(operator_core,'_create_content_plan',create)
    source='Подготовь контент-план на 7 дней с 10 октября 2026: акция только 10–12 октября'
    result,pending=operator_core.route_operator_message(None,business_id='b',user_id='u',message=source,channel='web')
    assert result['status']=='clarification_required'
    result,pending=operator_core.route_operator_message(None,business_id='b',user_id='u',message='Один пост в день',channel='web',pending_context=pending)
    assert result['status']=='completed'
    assert source in captured[1] and 'Один пост в день' in captured[1]


def test_finance_summary_negative_delivery_is_not_external_send():
    from services.agent_blueprint_creation import _finance_summary_requested
    assert _finance_summary_requested('Ежедневно готовить сводку выручки и чеков. Только черновик, без включения и отправки.')
    assert _finance_summary_requested('Готовить финансовую сводку, не отправляй.')
    assert not _finance_summary_requested('Отправляй финансовую сводку в Telegram ежедневно')


def test_daily_content_schedule_keeps_exact_start():
    from services.operator_plan_schedule import extract
    from services.operator_plan_continuation import PlanClarification
    message='Контент-план на 7 дней с 10 октября 2026. Один пост в день'
    schedule=extract(message)
    assert schedule['dates']==[f'2026-10-{day}' for day in range(10,17)]
    assert extract('Контент-план на 7 дней с 10 октября 2026. Ежедневно')['dates']==schedule['dates']
    with pytest.raises(PlanClarification):extract(message.replace('Один','Два'))


def test_workday_followup_keeps_source_and_session(monkeypatch):
    from services import operator_workday_router, operator_workday, operator_day_facts, operator_core, finance_daily
    from services import operator_story, disk_import_media, operator_colleagues, operator_audio
    monkeypatch.setattr(operator_workday,'enabled',lambda business:True)
    monkeypatch.setattr(operator_workday,'authorize',lambda *args:None)
    monkeypatch.setattr(operator_day_facts,'read_request',lambda *args:None)
    monkeypatch.setattr(finance_daily,'enabled',lambda business:False)
    monkeypatch.setattr(finance_daily,'settings',lambda *args:{'timezone':'Europe/Moscow'})
    monkeypatch.setattr(operator_audio,'authorize_actor',lambda *args:(None,{}))
    monkeypatch.setattr(operator_core,'operator_subscription_block',lambda *args:None)
    for module in (operator_workday,operator_day_facts,operator_story,disk_import_media,operator_colleagues):
        monkeypatch.setattr(module,'tools',lambda *args,**kwargs:[])
    seen=[]
    def catalog(cursor,**kwargs):
        seen.append(kwargs)
        return [{'name':'content.create_plan','capability':'content.create_plan','risk_class':'write_internal_draft','deterministic_response':True,
            'execute':lambda arguments:{'status':'clarification_required' if len(seen)==1 else 'completed','chat_response':'Частота?' if len(seen)==1 else 'Создано'}}]
    monkeypatch.setattr(operator_core,'_operator_tool_catalog',catalog)
    params=dict(cursor=None,business_id='b',user_id='u',channel='web',payload={},conversation_id='c',conversation_history=[],
        actor_context={'session_kind':'standard','user_id':'u'},pending_approvals=[],planner=lambda state:{'action':'tool_call','tool':'content.create_plan','arguments':{}})
    source='Контент-план с 10 октября 2026 на 7 дней. Не используй свободные кресла'
    result,pending=operator_workday_router.route(message=source,pending={},**params)
    assert pending.get('source_message')==source, result
    result,pending=operator_workday_router.route(message='Один пост в день',pending=pending,**params)
    assert result['status']=='completed'
    assert source in seen[1]['message'] and 'Один пост в день' in seen[1]['message']
    assert seen[1]['actor_context']==params['actor_context']


def test_today_items_visible_without_workspace_toggle_and_scope_safe(owner_day):
    _,c=owner_day
    c.execute('ALTER TABLE businesses ADD COLUMN IF NOT EXISTS network_id TEXT, ADD COLUMN IF NOT EXISTS name TEXT')
    c.execute("INSERT INTO networks(id,name,owner_id) VALUES ('network','Test network','u')")
    c.execute("UPDATE businesses SET network_id='network',name=id")
    args=arguments()
    envelope=actions.prepare(c,'b','u',args,args['quote'])['approval']['envelope']
    actions.apply(c,'b','u',envelope,'saved')
    items=actions.today_items(c,{'kind':'business','id':'b','business_ids':['b']},'u')
    assert len(items)==1 and items[0]['kind']=='owner_action'
    assert items[0]['stage']=='2026-10-10 10:00 (Europe/Tallinn)'
    assert not actions.today_items(c,{'kind':'business','id':'other','business_ids':['other']},'u')
    assert not actions.today_items(c,{'kind':'business','id':'b','business_ids':['b']},'viewer')
    assert len(actions.today_items(c,{'kind':'network','id':'network','business_ids':[]},'u'))==1

def test_transfer_same_record_complete_batch_and_atomic_stale(owner_day):
    _,c=owner_day
    args=arguments()
    first=actions.apply(c,'b','u',actions.prepare(c,'b','u',args,args['quote'])['approval']['envelope'],'first')
    row=actions.read(c,'b','u',{})['owner_actions'][0]
    message='Перенеси напоминание на 12 октября 2026 в 11:00'
    transfer=actions.prepare(c,'b','u',{'operation':'reschedule','id':row['id'],'version':1,'date':'2026-10-12','time':'11:00','quote':message},message)['approval']['envelope']
    actions.apply(c,'b','u',transfer,'move')
    assert actions.apply(c,'b','u',transfer,'move')['idempotent']
    rows=actions.read(c,'b','u',{})['owner_actions']
    assert len(rows)==1 and rows[0]['id']==first['owner_action_id']
    assert rows[0]['version']==2 and rows[0]['payload_json']['date']=='2026-10-12'
    task_args=arguments('task')
    task=actions.apply(c,'b','u',actions.prepare(c,'b','u',task_args,task_args['quote'])['approval']['envelope'],'task')
    batch=actions.prepare(c,'b','u',{'items':[{'operation':'complete','id':task['owner_action_id'],'version':1},{'operation':'cancel','id':row['id'],'version':2}]},'Заверши задачу и отмени напоминание')['approval']['envelope']
    c.execute('UPDATE journey_actions SET version=version+1 WHERE id=%s',(row['id'],))
    with pytest.raises(ValueError):actions.apply(c,'b','u',batch,'stale')
    c.execute('SELECT status FROM journey_actions WHERE id=%s',(task['owner_action_id'],))
    assert c.fetchone()['status']=='ready'
    batch=actions.prepare(c,'b','u',{'items':[{'operation':'complete','id':task['owner_action_id'],'version':1},{'operation':'cancel','id':row['id'],'version':3}]},'Заверши задачу и отмени напоминание')['approval']['envelope']
    actions.apply(c,'b','u',batch,'batch')
    c.execute('SELECT status FROM journey_actions ORDER BY status')
    assert [item['status'] for item in c.fetchall()]==['cancelled','completed']


def test_day_closed_is_not_permanent_hours(owner_day):
    _,c=owner_day
    message='Завтра 10 октября 2026 закрыто весь день'
    preview=actions.prepare(c,'b','u',{'kind':'hours','date':'2026-10-10','closed':True,'quote':message},message)
    actions.apply(c,'b','u',preview['approval']['envelope'],'closed')
    assert actions.effective_hours(c,'b','2026-10-10')['closed'] is True
    assert actions.effective_hours(c,'b','2026-10-11') is None
    assert actions.permanent_hours(c,'b')=='09:00–19:00'
