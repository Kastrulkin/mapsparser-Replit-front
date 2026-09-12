import importlib.util
from pathlib import Path
import pytest
from tests.test_operator_voice_pg import pg
from services import finance_daily, operator_core, operator_chat_service, operator_audio


@pytest.fixture
def daily(pg,monkeypatch):
    conn,c=pg
    c.execute('ALTER TABLE businesses ADD COLUMN name TEXT')
    c.execute("UPDATE businesses SET name='Test business'")
    c.execute('CREATE TABLE financialtransactions(id TEXT PRIMARY KEY,user_id TEXT,business_id TEXT,amount NUMERIC,transaction_date DATE,transaction_type TEXT,description TEXT)')
    c.execute('CREATE TABLE finance_entries(id TEXT PRIMARY KEY,business_id TEXT,date DATE,type TEXT,amount NUMERIC)')
    c.execute('CREATE TABLE finance_service_metrics(id TEXT, business_id TEXT,period_start DATE,period_end DATE,service_name TEXT,revenue NUMERIC)')
    c.execute('CREATE TABLE userservices(id TEXT,business_id TEXT,name TEXT,is_active BOOLEAN)')
    from alembic import op
    monkeypatch.setattr(op,'execute',c.execute)
    path=Path(__file__).parents[1]/'alembic_migrations/versions/20260912_operator_finance_daily.py'
    spec=importlib.util.spec_from_file_location('daily_migration',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.upgrade();module.upgrade()
    monkeypatch.setenv('OPERATOR_FINANCE_INPUT_BUSINESS_IDS','b')
    def authorize(cursor,business,user,write=False):
        if (business,user)!=('b','u'):raise PermissionError('Нет доступа')
        return {},{}
    monkeypatch.setattr(finance_daily,'authorize',authorize)
    c.execute("INSERT INTO business_finance_settings(business_id,currency,timezone) VALUES ('b','EUR','Europe/Tallinn')")
    conn.commit()
    return conn,c


def facts(**extra):
    return {'kind':'daily','date':'2026-09-12','currency':'EUR','values':{'revenue':'350','refunds':'20','checks':10,'upsell_checks':2},**extra}


def prepare(c,args=None):return finance_daily.prepare(c,'b','u',args or facts(),'web','message')


def test_control_example_versions_and_no_synthetic_transactions(daily):
    conn,c=daily
    envelope=prepare(c)
    c.execute('SELECT COUNT(*) n FROM finance_daily_summaries');assert c.fetchone()['n']==0
    saved=finance_daily.apply(c,'b','u',envelope,'action');conn.commit()
    finance_daily.apply(c,'b','u',envelope,'action')
    report=finance_daily.read_period(c,'b','2026-09-12','2026-09-12')
    totals=report['currencies']['EUR']
    assert totals['net_revenue']==330 and totals['average_check']==35 and totals['upsell_share']==20
    c.execute('SELECT COUNT(*) n FROM financialtransactions');assert c.fetchone()['n']==0
    c.execute('SELECT COUNT(*) n FROM finance_daily_events');assert c.fetchone()['n']==1
    assert saved['version']==1


def test_late_import_is_detail_not_extra_revenue(daily):
    _,c=daily
    finance_daily.apply(c,'b','u',prepare(c),'action')
    c.execute("INSERT INTO financialtransactions(id,business_id,amount,transaction_date,transaction_type,currency) VALUES ('sale','b',300,'2026-09-12','income','EUR')")
    report=finance_daily.read_period(c,'b','2026-09-12','2026-09-12')
    assert report['currencies']['EUR']['revenue']==350
    assert report['days'][0]['discrepancies']['revenue']=={'reported':'350','detail':'300'}
    c.execute("UPDATE financialtransactions SET amount=350")
    assert finance_daily.read_period(c,'b','2026-09-12','2026-09-12')['currencies']['EUR']['revenue']==350


def test_add_correction_and_cancel_keep_history(daily):
    _,c=daily
    finance_daily.apply(c,'b','u',prepare(c),'one')
    addition=prepare(c,facts(mode='add',values={'checks':2}))
    assert addition['data']['checks']=='12'
    finance_daily.apply(c,'b','u',addition,'two')
    correction=prepare(c,facts(values={'revenue':380}))
    finance_daily.apply(c,'b','u',correction,'three')
    cancellation=prepare(c,facts(mode='void',values={}))
    finance_daily.apply(c,'b','u',cancellation,'four')
    report=finance_daily.read_period(c,'b','2026-09-12','2026-09-12')
    assert not report['days'] and len(report['voided_summaries'])==1
    c.execute('SELECT COUNT(*) n FROM finance_daily_events');assert c.fetchone()['n']==4


def test_stale_preview_and_foreign_scope_denied(daily):
    _,c=daily
    original=prepare(c);other=prepare(c,facts(values={'revenue':400}))
    finance_daily.apply(c,'b','u',original,'one')
    with pytest.raises(ValueError,match='изменился'):finance_daily.apply(c,'b','u',other,'two')
    with pytest.raises(PermissionError):finance_daily.apply(c,'other','u',original,'three')


@pytest.mark.parametrize('values',[{'checks':-1},{'checks':1.5},{'revenue':'NaN'},{'revenue':'1.234'},{'checks':1,'upsell_checks':2}])
def test_invalid_facts_never_saved(daily,values):
    _,c=daily
    with pytest.raises(ValueError):prepare(c,facts(values=values))


def test_unknown_is_not_zero_and_add_needs_base(daily):
    _,c=daily
    with pytest.raises(ValueError,match='неизвестен'):prepare(c,facts(mode='add',values={'checks':2}))
    finance_daily.apply(c,'b','u',prepare(c,facts(values={'revenue':350})),'one')
    values=finance_daily.read_period(c,'b','2026-09-12','2026-09-12')['currencies']['EUR']
    assert values['checks'] is None and values['average_check'] is None and values['refunds'] is None


def test_expense_and_refund_are_not_sales(daily):
    _,c=daily
    for kind,amount in [('income',350),('expense',50),('refund',20)]:
        args={'kind':'transaction','date':'2026-09-12','transaction_type':kind,'amount':amount,'has_upsell':kind=='income'}
        finance_daily.apply(c,'b','u',prepare(c,args),kind)
    values=finance_daily.read_period(c,'b','2026-09-12','2026-09-12')['currencies']['EUR']
    assert values['checks']==1 and values['net_revenue']==330 and values['expenses']==50 and values['upsell_share']==100


def test_separate_currencies_and_period_aggregate(daily):
    _,c=daily
    finance_daily.apply(c,'b','u',prepare(c),'one')
    finance_daily.apply(c,'b','u',prepare(c,facts(currency='USD')),'two')
    c.execute("INSERT INTO finance_service_metrics VALUES ('period','b','2026-09-01','2026-09-30','Service',9000)")
    report=finance_daily.read_period(c,'b','2026-09-12','2026-09-12')
    assert set(report['currencies'])=={'EUR','USD'} and len(report['period_aggregates'])==1
    snapshot=finance_daily.overlay_snapshot({'kpis':{'revenue':999,'average_ticket':999}},report)
    assert snapshot['kpis']['revenue'] is None


@pytest.mark.parametrize('channel',['telegram','web','telegram_mini_app'])
@pytest.mark.parametrize('voice',[False,True])
def test_six_inputs_preview_confirm_replay(daily,channel,voice):
    conn,c=daily;message='Сегодня 10 продаж, 2 допа, выручка 350 евро, возврат 20 евро'
    payload={'request_id':'request'}
    if voice:
        asset=operator_audio.create_transcription(c,content=b'fixture',user_id='u',business_id='b',channel=channel,conversation_id=None,request_id='recording')
        c.execute("UPDATE operator_audio_assets SET transcript=%s,status='ready' WHERE id=%s",(message,asset['asset_id']))
        c.execute("UPDATE operator_async_jobs SET status='completed' WHERE id=%s",(asset['job_id'],))
        payload.update(transcription_id=asset['asset_id'],conversation_id=asset['conversation_id'])
    class Orchestrator:
        prepared=None
        def execute(self,envelope,user):
            self.prepared=envelope
            return {'success':True,'status':'pending_human','action_id':'approved-action','approval':{'status':'pending_human'}}
        def resolve_human_decision(self,*args,**kwargs):
            saved=finance_daily.apply(c,'b','u',self.prepared['payload'],'approved-action')
            return {'success':True,'status':'completed','result':{'status':'completed','saved':saved,'chat_response':'Сохранено'}}
    orchestrator=Orchestrator()
    def router(cursor,**args):
        return operator_core.route_operator_message(cursor,tool_planner=lambda state:{'action':'tool_call','tool':'finance.prepare_facts','arguments':facts()},action_orchestrator=orchestrator,**args)
    args=dict(business_id='b',user_id='u',channel=channel,message=message,payload=payload,router=router)
    preview=operator_chat_service.process_chat(c,**args);conn.commit()
    assert preview['status']=='approval_required' and preview['approval']['status']=='pending'
    c.execute('SELECT COUNT(*) n FROM finance_daily_summaries');assert c.fetchone()['n']==0
    duplicate=operator_chat_service.process_chat(c,**args)
    assert duplicate['message_id']==preview['message_id']
    kwargs=dict(action_id=preview['approval']['action_id'],business_id='b',user_id='u',action_orchestrator=orchestrator)
    outcome,_=operator_core.confirm_pending_operator_action(c,**kwargs)
    assert outcome['status']=='completed'
    _,replay=operator_core.confirm_pending_operator_action(c,**kwargs)
    assert replay
    c.execute('SELECT COUNT(*) n FROM finance_daily_events');assert c.fetchone()['n']==1


def test_financial_policy_always_requires_human():
    from core.action_policy import evaluate_risk_policy
    for kind in ('daily','transaction','settings'):
        assert evaluate_risk_policy('finance.daily.apply_operator',{'kind':kind},{})['requires_human'] is True


def test_individual_operation_keeps_canonical_report_after_flag_off(daily,monkeypatch):
    _,c=daily
    c.execute('DELETE FROM business_finance_settings')
    envelope=prepare(c,{'kind':'transaction','date':'2026-09-12','currency':'EUR','transaction_type':'income','amount':'0.10'})
    finance_daily.apply(c,'b','u',envelope,'operation')
    monkeypatch.setenv('OPERATOR_FINANCE_INPUT_BUSINESS_IDS','')
    assert finance_daily.canonical_report(c,'b','2026-09-12','2026-09-12')['currencies']['EUR']['revenue']==0.1


def test_relative_day_uses_business_timezone(daily,monkeypatch):
    from datetime import datetime
    _,c=daily
    class FixedDateTime(datetime):
        @classmethod
        def now(cls,tz=None):return datetime.fromisoformat('2026-09-12T00:30:00+00:00').astimezone(tz)
    monkeypatch.setattr(finance_daily,'datetime',FixedDateTime)
    c.execute("UPDATE business_finance_settings SET timezone='America/Los_Angeles'")
    assert prepare(c,facts(date='today'))['date']=='2026-09-11'
    assert prepare(c,facts(date='yesterday'))['date']=='2026-09-10'


def test_linked_upsell_is_one_check_and_stale_receipt_is_denied(daily):
    _,c=daily
    base={'kind':'transaction','date':'2026-09-12','transaction_type':'income','amount':'300'}
    first=finance_daily.apply(c,'b','u',prepare(c,base),'receipt')
    upsell=prepare(c,{**base,'amount':'50','sale_type':'upsell','receipt_id':first['id']})
    finance_daily.apply(c,'b','u',upsell,'upsell')
    totals=finance_daily.read_period(c,'b','2026-09-12','2026-09-12')['currencies']['EUR']
    assert totals['checks']==1 and totals['revenue']==350 and totals['upsell_checks']==1
    c.execute('UPDATE financialtransactions SET is_voided=TRUE WHERE id=%s',(first['id'],))
    with pytest.raises(ValueError,match='чек'):finance_daily.apply(c,'b','u',upsell,'new-action')


def test_daily_service_import_no_proration_or_fake_check(daily):
    _,c=daily
    c.execute("INSERT INTO finance_service_metrics(id,business_id,period_start,period_end,revenue,currency) VALUES ('d','b','2026-09-12','2026-09-12',350,'EUR')")
    report=finance_daily.read_period(c,'b','2026-09-12','2026-09-12')
    assert report['currencies']['EUR']['revenue']==350 and report['currencies']['EUR']['checks'] is None
    c.execute("INSERT INTO finance_entries(id,business_id,date,type,amount,currency) VALUES ('e','b','2026-09-12','income',350,'EUR')")
    report=finance_daily.read_period(c,'b','2026-09-12','2026-09-12')
    assert report['currencies']['EUR']['revenue']==350 and report['overlapping_daily_sources']


def test_api_and_chat_share_control_example(daily,monkeypatch):
    from flask import Flask
    from api import finance_api
    from services import operator_finance_daily
    conn,c=daily
    finance_daily.apply(c,'b','u',prepare(c),'api-action')
    class DB:
        def __init__(self):self.conn=conn
        def close(self):pass
    monkeypatch.setattr(finance_api,'DatabaseManager',DB)
    monkeypatch.setattr(finance_api,'_require_finance_user_and_business',lambda:({'user_id':'u'},'b',None))
    monkeypatch.setattr(finance_api,'verify_session',lambda token:{'user_id':'u'})
    monkeypatch.setattr(finance_api,'verify_business_access',lambda *args:(True,'u'))
    app=Flask(__name__);app.register_blueprint(finance_api.finance_bp)
    client=app.test_client()
    report=client.get('/api/finance/daily?business_id=b&start=2026-09-12&end=2026-09-12').get_json()
    response=client.get('/api/finance/metrics?business_id=b&start_date=2026-09-12&end_date=2026-09-12',headers={'Authorization':'Bearer test'})
    assert response.status_code==200,response.get_json()
    assert response.get_json()['metrics']['average_check']==35
    chat=operator_finance_daily.read(c,'b','u',{'start':'2026-09-12','end':'2026-09-12'})
    assert chat['financial_daily']['currencies']==report['currencies']
    history=client.get('/api/finance/daily/'+report['days'][0]['summary_id']+'/history?business_id=b').get_json()
    assert len(history['items'])==1
    c.execute('DELETE FROM business_finance_settings')
    initial=client.get('/api/finance/daily?business_id=b')
    assert initial.status_code==200,initial.get_json()
    assert initial.get_json()['days'][0]['date']=='2026-09-12'


def test_correction_uses_original_date_and_currency(daily):
    _,c=daily
    first=finance_daily.apply(c,'b','u',prepare(c,{'kind':'transaction','date':'2026-09-01','currency':'USD','transaction_type':'income','amount':'100','has_upsell':False}),'original')
    corrected=prepare(c,{'kind':'transaction','transaction_id':first['id'],'amount':'120'})
    assert corrected['data']['transaction_date']=='2026-09-01' and corrected['data']['currency']=='USD'
    totals=finance_daily.read_period(c,'b','2026-09-01','2026-09-01')['currencies']['USD']
    assert totals['upsell_checks']==0
