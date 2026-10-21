"""Journal-to-search approvals on real authorization/PG; the search worker is not run."""
import uuid
import pytest
from tests.test_team_work_access_pg import ordinary, team, workday, journal, daily, pg
from services import work_journal,work_review,work_journal_partnerships,operator_core,outreach_continuation
from services.operator_conversations import get_or_create_operator_conversation,create_pending_operator_action
from services.operator_async_jobs import create_operator_async_job
from subscription_manager import build_subscription_capabilities

@pytest.fixture
def search(ordinary,monkeypatch):
    conn,c=ordinary
    c.execute("UPDATE businesses SET subscription_tier='concierge'")
    monkeypatch.setenv('OUTREACH_CONTINUATION_ENABLED','true')
    monkeypatch.setenv('OUTREACH_CONTINUATION_BUSINESS_IDS','b')
    from services import outreach_web_search
    monkeypatch.setattr(outreach_web_search,'configured',lambda *args:True)
    entry=work_journal.save_note(c,'b','master','telegram',None,'source','Грязные окна, нужен мойщик',{'quote':'Грязные окна, нужен мойщик','outcome':'note'})
    entry=work_review.decision(c,'b','u',entry['id'],{'version':entry['version'],'status':'in_progress','request_id':'accepted'})
    return conn,c,entry


def args(entry,**extra):
    return {'version':entry['version'],'audience':'Мойщики окон с выездом','geography':'Москва, район салона','target_count':3,'requirements':['Выезд по адресу салона','Присылают стоимость до заказа'],'request_id':str(uuid.uuid4()),**extra}


def pending(c,entry,payload=None):
    preview=work_journal_partnerships.prepare(c,'b','u',entry['id'],payload or args(entry))
    conversation=get_or_create_operator_conversation(c,business_id='b',user_id='u',channel='web')
    action=create_pending_operator_action(c,conversation_id=str(conversation['id']),business_id='b',user_id='u',capability='partnerships.continue_outreach',envelope=preview['approval']['envelope'])
    return preview,action


def confirm(c,action):
    return operator_core.confirm_pending_operator_action(c,action_id=str(action['id']),business_id='b',user_id='u',subscription_access=build_subscription_capabilities(tier='concierge',status='active'))


def test_preview_has_source_costs_and_no_job_or_external_send(search):
    _,c,entry=search
    preview,_=pending(c,entry)
    envelope=preview['approval']['envelope']
    assert preview['status']=='approval_required'
    assert 'Грязные окна' in preview['chat_response'] and 'кредит' in preview['chat_response']
    assert envelope['config']['search_source']=='web' and envelope['config']['mode']=='find_only'
    assert envelope['source_work_journal']=={'entry_id':entry['id'],'version':entry['version']}
    assert envelope['config']['max_search_calls']==1
    c.execute('SELECT COUNT(*) n FROM operator_async_jobs');assert c.fetchone()['n']==0
    c.execute('SELECT COUNT(*) n FROM journey_actions');assert c.fetchone()['n']==0


@pytest.mark.parametrize('mode',['find_only','prepare_only'])
def test_valid_confirm_links_existing_search_once_and_never_enables_auto_send(search,monkeypatch,mode):
    _,c,entry=search
    _,action=pending(c,entry,args(entry,mode=mode,offer='Нужно вымыть окна. Уточните стоимость и условия выезда.'))
    calls=[]
    def native(cursor,**kwargs):
        config=kwargs['envelope']['config'];calls.append(config)
        job=create_operator_async_job(cursor,user_id='u',business_id='b',kind='outreach_continue',action_id=None,stage='queued',payload=config,idempotency_key='native-search')
        return {'status':'completed','task':{'id':str(job['id'])},'job_id':str(job['id'])}
    monkeypatch.setattr(outreach_continuation,'confirm_task_start',native)
    result,replayed=confirm(c,action)
    assert result['status']=='completed' and not replayed
    assert confirm(c,action)[1] and len(calls)==1
    assert calls[0]['mode']==mode
    linked=work_review.links(c,'b','u',entry['id']);assert len(linked)==1
    assert linked[0]['payload_json']['search_task_id']==result['job_id']
    assert not linked[0]['payload_json']['approved_external']
    assert 'search_task_id=' in linked[0]['cta_target_json']['href']


@pytest.mark.parametrize('change',['edited','closed','revoked','expired'])
def test_stale_source_cannot_start_search(search,monkeypatch,change):
    _,c,entry=search
    _,action=pending(c,entry)
    if change=='edited':work_journal.save_note(c,'b','master','telegram',None,'edit','Окна уже чистые',{'id':entry['id'],'version':entry['version'],'quote':'Окна уже чистые'})
    if change=='closed':work_review.decision(c,'b','u',entry['id'],{'request_id':'close','version':entry['version'],'status':'completed','decision':'Окна уже вымыты'})
    if change=='revoked':c.execute("UPDATE businesses SET owner_id='admin'")
    if change=='expired':c.execute("UPDATE businesses SET subscription_status='expired'")
    def forbidden(*args,**kwargs):raise AssertionError('Stale source must not reach search execution')
    monkeypatch.setattr(outreach_continuation,'confirm_task_start',forbidden)
    result,_=confirm(c,action)
    assert result['status']=='blocked'
    c.execute('SELECT COUNT(*) n FROM operator_async_jobs');assert c.fetchone()['n']==0


def test_link_failure_rolls_back_the_new_search_job(search,monkeypatch):
    _,c,entry=search
    _,action=pending(c,entry)
    def native(cursor,**kwargs):
        job=create_operator_async_job(cursor,user_id='u',business_id='b',kind='outreach_continue',action_id=None,stage='queued',payload={},idempotency_key='must-rollback')
        return {'status':'completed','job_id':str(job['id'])}
    def fail_link(*args,**kwargs):raise ValueError('Связь с записью не сохранена')
    monkeypatch.setattr(outreach_continuation,'confirm_task_start',native)
    monkeypatch.setattr(work_journal_partnerships,'link_search',fail_link)
    assert confirm(c,action)[0]['status']=='blocked'
    c.execute('SELECT COUNT(*) n FROM operator_async_jobs');assert c.fetchone()['n']==0
    c.execute('SELECT status FROM operatoractions WHERE id=%s',(action['id'],));assert c.fetchone()['status']=='pending_approval'


def test_new_conditions_reject_old_buttons_even_from_another_conversation(search):
    _,c,entry=search
    _,old=pending(c,entry)
    new,_=pending(c,entry,args(entry,target_count=5))
    c.execute('SELECT status FROM operatoractions WHERE id=%s',(old['id'],));assert c.fetchone()['status']=='rejected'
    assert new['approval']['envelope']['config']['target_count']==5


@pytest.mark.parametrize('change',[{'mode':'auto_send'},{'target_count':True},{'target_count':11},{'geography':''},{'requirements':['x'*301]}])
def test_invalid_search_requests_cannot_create_approvals(search,change):
    _,c,entry=search
    with pytest.raises(ValueError):work_journal_partnerships.prepare(c,'b','u',entry['id'],args(entry,**change))
    c.execute('SELECT COUNT(*) n FROM operatoractions');assert c.fetchone()['n']==0


def test_plain_employee_and_basic_plan_do_not_gain_search_rights(search):
    _,c,entry=search
    with pytest.raises(PermissionError):work_journal_partnerships.prepare(c,'b','master',entry['id'],args(entry))
    c.execute("UPDATE businesses SET subscription_tier='starter'")
    assert work_journal_partnerships.prepare(c,'b','u',entry['id'],args(entry))['blocked_reasons']==['payment_required']


def test_http_preview_exposes_actionable_pending_status_and_expiry(search,monkeypatch):
    conn,c,entry=search
    from flask import Flask
    from api import work_journal_api
    class DB:
        def __init__(self):self.conn=conn
        def close(self):pass
    monkeypatch.setattr(work_journal_api,'DatabaseManager',DB)
    monkeypatch.setattr(work_journal_api,'verify_session',lambda token:{'user_id':'u'})
    app=Flask(__name__);app.register_blueprint(work_journal_api.work_journal_bp)
    response=app.test_client().post('/api/work-journal/'+entry['id']+'/service-search/preview',headers={'Authorization':'Bearer owner'},json={**args(entry),'business_id':'b','channel':'max_mini_app'})
    assert response.status_code==200,response.json
    assert response.json['approval']['status']=='pending'
    c.execute('SELECT expires_at FROM operatoractions WHERE id=%s',(response.json['approval']['action_id'],))
    assert c.fetchone()['expires_at'] is not None
    c.execute('SELECT COUNT(*) n FROM operator_async_jobs');assert c.fetchone()['n']==0


@pytest.mark.parametrize('mode',['find_only','prepare_only'])
def test_real_native_confirmation_queues_once_with_journal_link(search,monkeypatch,mode):
    _,c,entry=search
    from services import partnership_leads_service
    from services.operator_audio import authorize_actor
    from subscription_manager import capability_access_payload
    def capabilities(business,capability,*args):
        _,access=authorize_actor(c,'u',business)
        return capability_access_payload(access,capability)
    monkeypatch.setattr(partnership_leads_service,'get_capability_access',capabilities)
    _,action=pending(c,entry,args(entry,mode=mode,offer='Просим стоимость и доступное время.'))
    result,replayed=confirm(c,action)
    assert result['status']=='completed' and not replayed,result
    c.execute("SELECT * FROM operator_async_jobs WHERE kind='outreach_continue'")
    jobs=c.fetchall();assert len(jobs)==1
    assert jobs[0]['status']=='queued' and jobs[0]['result_json']['started']
    assert jobs[0]['payload_json']['mode']==mode
    assert jobs[0]['payload_json']['search_source']=='web'
    assert jobs[0]['payload_json']['max_search_calls']==1
    assert confirm(c,action)[1]
    c.execute("SELECT COUNT(*) n FROM operator_async_jobs WHERE kind='outreach_continue'");assert c.fetchone()['n']==1
    assert work_review.links(c,'b','u',entry['id'])[0]['payload_json']['search_task_id']==str(jobs[0]['id'])
