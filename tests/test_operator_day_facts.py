import pytest
from tests.test_operator_workday import workday, prepare
from tests.test_work_journal_pg import journal
from tests.test_finance_daily_pg import daily
from tests.test_operator_voice_pg import pg
from services import operator_day_facts, operator_workday, work_journal, finance_daily


def save(c,key='capacity',user='u',**extra):
    quote='Сегодня с 15:00 до 17:00 свободны два кресла'
    args={'quote':quote,'operational':{'kind':'capacity','date':'2026-09-14','count':2,'start':'15:00','end':'17:00'},**extra}
    handler=operator_day_facts.tools(c,'b',user,'web',args['quote'],key)[0]['execute']
    return handler(args)


def test_capacity_persistent_dedup_correct_void(workday):
    _,c=workday
    row=save(c)['day_facts'][0]
    assert operator_day_facts.facts_result(c,'b','u',{'date':'2026-09-14'})['day_facts'][0]['id']==row['id']
    assert save(c,key='repeat')['idempotent']
    corrected=save(c,key='change',id=row['id'],version=1,quote='Сегодня с 15:00 до 17:00 свободны три кресла',operational={'kind':'capacity','date':'2026-09-14','count':3,'start':'15:00','end':'17:00'})
    assert corrected['day_facts'][0]['version']==2
    with pytest.raises(ValueError,match='изменена'):save(c,key='stale',id=row['id'],version=1)
    save(c,key='void',id=row['id'],version=2,void=True)
    assert not operator_day_facts.read(c,'b','u','2026-09-14')


def test_plan_joins_finance_schedule_and_absence(workday):
    _,c=workday
    save(c)
    quote='Сегодня мастер Первый отсутствует'
    operator_day_facts.tools(c,'b','u','telegram',quote,'absence')[0]['execute']({'quote':quote,'operational':{'kind':'absence','date':'2026-09-14','master':'Первый'}})
    operator_workday.apply(c,'b','u',prepare(c),'schedule')
    envelope=finance_daily.prepare(c,'b','u',{'kind':'daily','date':'2026-09-14','currency':'RUB','values':{'revenue':'12000','checks':6}},'web','finance')
    finance_daily.apply(c,'b','u',envelope,'finance')
    c.execute("ALTER TABLE journey_actions ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'ready', ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()")
    plan=operator_day_facts.plan(c,'b','u',{'date':'2026-09-14'})
    assert len(plan['schedule_conflicts'])==2
    assert '15:00–17:00' in plan['chat_response']
    assert plan['financial_daily']['currencies']['RUB']['checks']==6
    assert plan['financial_daily']['currencies']['RUB']['average_check']==2000
    assert operator_workday.briefing(c,'b','u',{'date':'2026-09-14'})['items'][0]['master_unavailable']
    c.execute('SELECT COUNT(*) n FROM financialtransactions');assert c.fetchone()['n']==0


def test_validation_and_permission(workday):
    _,c=workday
    with pytest.raises(PermissionError):save(c,user='master')
    with pytest.raises(PermissionError):save(c,user='viewer')
    with pytest.raises(ValueError):save(c,operational={'kind':'capacity','date':'2026-09-14','count':99,'start':'15:00','end':'17:00'})
    with pytest.raises(ValueError):save(c,quote='Если сегодня с 15:00 до 17:00 свободны два кресла')
    save(c)
    with pytest.raises(ValueError,match='пересекается'):save(c,key='overlap',quote='Сегодня с 16:00 до 18:00 свободны три кресла',operational={'kind':'capacity','date':'2026-09-14','count':3,'start':'16:00','end':'18:00'})
    assert not operator_day_facts.read(c,'b','u','2026-09-15')
    c.execute("UPDATE business_members SET status='revoked' WHERE user_id='admin'")
    with pytest.raises(PermissionError):save(c,user='admin')


def test_global_release_keeps_permission_gate(monkeypatch):
    monkeypatch.setenv('OPERATOR_BUSINESS_INFORMATION_ENABLED','1')
    assert all(module.enabled('new-business') for module in (work_journal,operator_workday,finance_daily))
    monkeypatch.setenv('OPERATOR_BUSINESS_INFORMATION_ENABLED','0')
    for variable in ('OPERATOR_WORKDAY_BUSINESS_IDS','OPERATOR_WORK_JOURNAL_BUSINESS_IDS','OPERATOR_FINANCE_INPUT_BUSINESS_IDS'):monkeypatch.setenv(variable,'')
    assert not operator_workday.enabled('new-business')


def test_router_exposes_schedule_and_day_facts(workday,monkeypatch):
    from services import operator_audio, operator_workday_router
    from services.operator_conversations import get_or_create_operator_conversation
    _,c=workday
    original=operator_audio.authorize_actor
    monkeypatch.setattr(operator_audio,'authorize_actor',lambda *a:(original(*a)[0],{'capabilities':['management','operator','finance','social_content']}))
    conversation=get_or_create_operator_conversation(c,business_id='b',user_id='u',channel='web')
    def planner(state):
        assert 'work.prepare_schedule' in {tool['name'] for tool in state['tools']},state['tools']
        return {'action':'tool_call','tool':'work.prepare_schedule','arguments':{'date':'2026-09-14','version':0,'entries':[{'time':'10:00','service_name':'Окрашивание','master':'Первый','duration_minutes':60}]}}
    outcome,_=operator_workday_router.route(c,business_id='b',user_id='u',message='Сохрани расписание на сегодня',channel='web',payload={},pending={},conversation_id=conversation['id'],conversation_history=[],actor_context={},pending_approvals=[],planner=planner)
    assert outcome['status']=='approval_required',outcome


def test_daily_read_is_not_a_write():
    from services.operator_finance_amounts import daily_statement
    assert daily_statement('Покажи сохранённые продажи за сегодня: выручку и число чеков. Только чтение.') is None
    assert daily_statement('Сегодня выручка 12000 рублей, 6 чеков')['values']['checks']=='6'


def test_void_legacy_transaction_preserves_unknown_currency(workday):
    _,c=workday
    c.execute("INSERT INTO financialtransactions(id,business_id,amount,transaction_date,transaction_type,description) VALUES ('legacy','b',12000,'2026-09-14','income','daily mistakenly imported')")
    preview=finance_daily.prepare(c,'b','u',{'kind':'transaction','mode':'void','transaction_id':'legacy'},'web','cleanup')
    assert preview['data']['currency'] is None
    assert 'валюта не указана' in finance_daily.preview_text(preview)
    finance_daily.apply(c,'b','u',preview,'void-legacy')
    assert not finance_daily.read_period(c,'b','2026-09-14','2026-09-14')['days']


def test_question_reads_plan_without_saving_again(workday):
    _,c=workday
    save(c)
    c.execute("ALTER TABLE journey_actions ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'ready', ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()")
    result=operator_day_facts.read_request(c,'b','u','Что мне делать сегодня дальше? Учти два кресла с 15:00 до 17:00')
    assert 'Следующие действия' in result['chat_response']
    with pytest.raises(ValueError,match='Вопрос'):operator_day_facts.tools(c,'b','u','web','Что мне делать сегодня?','question')[0]['execute']({'quote':'два кресла','operational':{'kind':'capacity'}})
    assert len(operator_day_facts.read(c,'b','u','2026-09-14'))==1
