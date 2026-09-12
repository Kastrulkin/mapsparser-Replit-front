import importlib.util
import json
from pathlib import Path
from datetime import datetime, timezone
import pytest
from tests.test_finance_daily_pg import daily
from tests.test_operator_voice_pg import pg
from services import work_journal, work_recommendations, operator_core, operator_chat_service, operator_audio


@pytest.fixture
def journal(daily,monkeypatch):
    conn,c=daily
    c.execute('ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT TRUE')
    c.execute('ALTER TABLE users ADD COLUMN is_superadmin BOOLEAN DEFAULT FALSE')
    c.execute('ALTER TABLE userservices ADD COLUMN price TEXT')
    c.execute('ALTER TABLE userservices ADD COLUMN duration_minutes INTEGER')
    c.execute("INSERT INTO userservices(id,business_id,name,is_active,price,duration_minutes) VALUES ('main','b','Окрашивание',TRUE,'100',60),('care','b','Уход',TRUE,'20',15),('kit','b','Набор',TRUE,'30',5)")
    c.execute('CREATE TABLE masters(id TEXT PRIMARY KEY,business_id TEXT,name TEXT)')
    c.execute("INSERT INTO masters VALUES ('m1','b','Первый'),('m2','b','Второй')")
    c.execute('CREATE TABLE bookings(id TEXT PRIMARY KEY,business_id TEXT,master_id TEXT,service_id TEXT,booking_date DATE,booking_time TEXT,status TEXT)')
    c.execute("INSERT INTO bookings VALUES ('v1','b','m1','main','2026-09-12','2026-09-12T10:00:00+03:00','confirmed'),('v2','b','m2','main','2026-09-12','2026-09-12T11:00:00+03:00','confirmed')")
    c.execute('CREATE TABLE business_members(business_id TEXT,user_id TEXT,role TEXT,status TEXT)')
    for user,role in [('master','member'),('admin','manager'),('viewer','viewer')]:
        c.execute("INSERT INTO users(id,is_active,is_superadmin) VALUES (%s,TRUE,FALSE)",(user,))
        c.execute("INSERT INTO business_members VALUES ('b',%s,%s,'active')",(user,role))
    c.execute('CREATE TABLE averageticketmatrices(id TEXT PRIMARY KEY,business_id TEXT,matrix_json JSONB,generated_at TIMESTAMPTZ DEFAULT NOW(),updated_at TIMESTAMPTZ DEFAULT NOW())')
    c.execute('CREATE TABLE averageticketevents(id TEXT PRIMARY KEY,business_id TEXT,booking_id TEXT,main_service_id TEXT,addon_service_id TEXT,event_type TEXT,event_date DATE,master_id TEXT,notes TEXT,created_by TEXT,created_at TIMESTAMPTZ DEFAULT NOW())')
    matrix={'upsell_matrix':[{'main_service_id':'main','recommended_addons':[{'id':'l1','service_id':'care','status':'active','priority':'high','reason':'Согласованная связка'},{'id':'l2','service_id':'kit','status':'active','priority':'medium'}]}]}
    c.execute("INSERT INTO averageticketmatrices(id,business_id,matrix_json) VALUES ('matrix','b',%s::jsonb)",(json.dumps(matrix),))
    from alembic import op
    monkeypatch.setattr(op,'execute',c.execute)
    path=Path(__file__).parents[1]/'alembic_migrations/versions/20260912_work_journal.py'
    spec=importlib.util.spec_from_file_location('work_migration',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.upgrade();module.upgrade()
    c.execute("INSERT INTO business_master_bindings(business_id,user_id,master_id) VALUES ('b','master','m1')")
    def auth(cursor,user,business):
        if business!='b':raise PermissionError('Нет доступа')
        cursor.execute('SELECT is_active FROM users WHERE id=%s',(user,));row=cursor.fetchone()
        if not row or not row['is_active']:raise PermissionError('Нет доступа')
        return {'role':'business_owner' if user=='u' else 'business_user'},{}
    monkeypatch.setattr(operator_audio,'authorize_actor',auth)
    monkeypatch.setenv('OPERATOR_WORK_JOURNAL_BUSINESS_IDS','b')
    conn.commit();return conn,c


def note(c,user='master',key='one',**extra):
    args={'quote':'Клиент отказался от ухода, дорого','outcome':'declined','reason':'дорого','booking_id':'v1','addon_service_id':'care',**extra}
    return work_journal.save_note(c,'b',user,'web','message',key,args['quote'],args)


def test_atomic_note_event_and_no_revenue(journal):
    conn,c=journal
    row=note(c);conn.commit();replay=note(c)
    assert row['id']==replay['id']
    c.execute('SELECT COUNT(*) n FROM averageticketevents');assert c.fetchone()['n']==1
    c.execute('SELECT COUNT(*) n FROM financialtransactions');assert c.fetchone()['n']==0
    assert work_recommendations.recommend(c,'b','master',{'booking_id':'v1'})['items'][0]['recommendations'][0]['previous_results'][0]['event_type']=='declined'


def test_role_isolation(journal):
    _,c=journal
    note(c)
    note(c,user='admin',key='second',booking_id='v2')
    assert len(work_journal.list_entries(c,'b','master'))==1
    assert len(work_journal.list_entries(c,'b','admin'))==2
    assert len(work_journal.list_entries(c,'b','viewer'))==0
    with pytest.raises(PermissionError):note(c,user='viewer')
    with pytest.raises(PermissionError):note(c,key='foreign',booking_id='v2')
    with pytest.raises(PermissionError):work_recommendations.recommend(c,'other','master',{'booking_id':'v1'})
    c.execute("UPDATE business_members SET status='revoked' WHERE user_id='master'")
    with pytest.raises(PermissionError):note(c,key='revoked')


def test_unlinked_note_and_correction_void_history(journal):
    _,c=journal
    row=note(c,booking_id=None)
    c.execute('SELECT COUNT(*) n FROM averageticketevents');assert c.fetchone()['n']==0
    args={'id':row['id'],'version':1,'quote':'Клиент отказался от ухода, дорого','booking_id':'v1'}
    updated=work_journal.save_note(c,'b','master','telegram','next','link',args['quote'],args)
    assert updated['version']==2
    with pytest.raises(ValueError,match='изменена'):work_journal.save_note(c,'b','master','web','next','stale',args['quote'],args)
    cancelled=work_journal.save_note(c,'b','master','web','next','void','',{'id':row['id'],'version':2,'void':True})
    assert cancelled['is_voided']
    c.execute('SELECT COUNT(*) n FROM averageticketevents WHERE NOT is_voided');assert c.fetchone()['n']==0
    assert len(work_journal.history(c,'b','master',row['id']))==3


@pytest.mark.parametrize('quote',['Если клиент откажется от ухода','Например, клиент отказался','Что предложить клиенту?'])
def test_questions_not_facts(journal,quote):
    _,c=journal
    with pytest.raises(ValueError):note(c,quote=quote)
    c.execute('SELECT COUNT(*) n FROM business_work_journal');assert c.fetchone()['n']==0


def rule(**extra):return {'action':'ban','addon_service_id':'care','permanent':True,'instruction':'Не предлагайте уход',**extra}


def test_owner_policy_preview_apply_replay_and_stale(journal):
    _,c=journal
    payload=work_recommendations.prepare_policy(c,'b','u',{'changes':[rule()]})
    assert len(work_recommendations.recommend(c,'b','master',{'booking_id':'v1'})['items'][0]['recommendations'])==2
    with pytest.raises(PermissionError):work_recommendations.prepare_policy(c,'b','admin',{'changes':[rule()]})
    work_recommendations.apply_policy(c,'b','u',payload,'approved')
    work_recommendations.apply_policy(c,'b','u',payload,'approved')
    assert [r['service_id'] for r in work_recommendations.recommend(c,'b','master',{'booking_id':'v1'})['items'][0]['recommendations']]==['kit']
    with pytest.raises(ValueError,match='изменились'):work_recommendations.apply_policy(c,'b','u',payload,'stale')
    c.execute("SELECT COUNT(*) n FROM business_work_history WHERE kind='rules'");assert c.fetchone()['n']==1


def test_rule_time_gap_unknown_and_fail_closed(journal,monkeypatch):
    _,c=journal
    services=work_recommendations.catalog(c,'b');matrix=work_recommendations.matrix(c,'b')['matrix_json']
    timed=rule(id='timed',permanent=False,starts_at='2026-09-12T10:00:00+03:00',ends_at='2026-09-12T11:00:00+03:00')
    assert len(work_recommendations.select(services,matrix,[timed],'main',now=datetime.fromisoformat('2026-09-12T10:00:00+03:00')))==1
    assert len(work_recommendations.select(services,matrix,[timed],'main',now=datetime.fromisoformat('2026-09-12T11:00:00+03:00')))==2
    gap=rule(id='gap',action='minimum_gap',minutes=15)
    assert len(work_recommendations.select(services,matrix,[gap],'main'))==1
    payload=work_recommendations.prepare_policy(c,'b','u',{'changes':[rule()]});work_recommendations.apply_policy(c,'b','u',payload,'approved')
    monkeypatch.setenv('OPERATOR_WORK_JOURNAL_BUSINESS_IDS','')
    assert work_recommendations.recommend(c,'b','master',{'booking_id':'v1'})['status']=='blocked'


def test_matrix_change_invalidates_preview_and_archived_service_is_excluded(journal):
    _,c=journal
    payload=work_recommendations.prepare_policy(c,'b','u',{'changes':[rule()]})
    c.execute("UPDATE averageticketmatrices SET updated_at=NOW()+INTERVAL '1 second'")
    with pytest.raises(ValueError):work_recommendations.apply_policy(c,'b','u',payload,'changed')
    c.execute("UPDATE userservices SET is_active=FALSE WHERE id='care'")
    assert [r['service_id'] for r in work_recommendations.recommend(c,'b','master',{'booking_id':'v1'})['items'][0]['recommendations']]==['kit']

@pytest.mark.parametrize('channel',['web','telegram','telegram_mini_app'])
@pytest.mark.parametrize('voice',[False,True])
@pytest.mark.parametrize('user',['u','admin','master'])
def test_six_inputs_three_roles_observation_replay(journal,channel,voice,user):
    conn,c=journal;message='Клиент отказался от ухода, дорого';payload={'request_id':'input'}
    if voice:
        asset=operator_audio.create_transcription(c,content=b'fixture',user_id=user,business_id='b',channel=channel,conversation_id=None,request_id='audio')
        c.execute("UPDATE operator_audio_assets SET transcript=%s,status='ready' WHERE id=%s",(message,asset['asset_id']))
        c.execute("UPDATE operator_async_jobs SET status='completed' WHERE id=%s",(asset['job_id'],))
        payload.update(transcription_id=asset['asset_id'],conversation_id=asset['conversation_id'])
    def planner(state):
        if state.get('observations'):return {'action':'final','message':'Наблюдение сохранено.'}
        return {'action':'tool_call','tool':'work.save_observation','arguments':{'quote':message,'outcome':'declined','reason':'дорого','booking_id':'v1','addon_service_id':'care'}}
    def router(cursor,**args):return operator_core.route_operator_message(cursor,tool_planner=planner,**args)
    args=dict(business_id='b',user_id=user,channel=channel,message=message,payload=payload,router=router)
    first=operator_chat_service.process_chat(c,**args);conn.commit()
    second=operator_chat_service.process_chat(c,**args)
    assert first['status']=='completed',first
    assert first['message_id']==second['message_id']
    c.execute('SELECT COUNT(*) n FROM business_work_journal');assert c.fetchone()['n']==1
    c.execute('SELECT COUNT(*) n FROM averageticketevents');assert c.fetchone()['n']==1
    c.execute('SELECT COUNT(*) n FROM financialtransactions');assert c.fetchone()['n']==0


def test_revoked_member_cannot_read(journal):
    _,c=journal;note(c)
    c.execute("UPDATE business_members SET status='revoked' WHERE user_id='master'")
    with pytest.raises(PermissionError):work_journal.list_entries(c,'b','master')
    with pytest.raises(PermissionError):work_recommendations.recommend(c,'b','master',{'booking_id':'v1'})


def test_changed_request_and_policy_replay_rejected(journal):
    _,c=journal;note(c)
    with pytest.raises(ValueError):note(c,outcome='interested')
    envelope=work_recommendations.prepare_policy(c,'b','u',{'changes':[rule()]})
    work_recommendations.apply_policy(c,'b','u',envelope,'action')
    changed={**envelope,'data':{'rules':[]}}
    with pytest.raises(ValueError):work_recommendations.apply_policy(c,'b','u',changed,'action')


def test_event_day_uses_business_zone_and_missing_zone_is_atomic(journal):
    _,c=journal
    row=note(c,occurred_at='2026-09-11T22:30:00+00:00')
    c.execute('SELECT event_date FROM averageticketevents');assert str(c.fetchone()['event_date'])=='2026-09-12'
    c.execute('DELETE FROM business_finance_settings')
    with pytest.raises(ValueError):note(c,key='missing-zone')
    c.execute('SELECT COUNT(*) n FROM business_work_journal');assert c.fetchone()['n']==1


def test_matrix_apply_rechecks_active_service_and_preserves_before(journal):
    _,c=journal
    old=work_recommendations.matrix(c,'b')['matrix_json']
    proposed=json.loads(json.dumps(old));proposed['upsell_matrix'][0]['recommended_addons'][0]['status']='disabled'
    envelope=work_recommendations.prepare_policy(c,'b','u',{'kind':'matrix','matrix_id':'matrix','matrix_json':proposed})
    c.execute("UPDATE userservices SET is_active=FALSE WHERE id='care'")
    with pytest.raises(ValueError):work_recommendations.apply_policy(c,'b','u',envelope,'matrix-apply')
    c.execute("UPDATE userservices SET is_active=TRUE WHERE id='care'")
    work_recommendations.apply_policy(c,'b','u',envelope,'matrix-apply')
    c.execute("SELECT before_json FROM business_work_history WHERE kind='matrix'");assert c.fetchone()['before_json']['matrix_json']==old


def test_followup_cannot_duplicate_saved_observation(journal):
    _,c=journal
    from services.operator_work_journal import tools
    original=note(c,booking_id=None);saved=[]
    entries=tools(c,'b','master','telegram','Клиент отказался от ухода, дорого\nУточнение: в десять','message-2','next',saved,previous_saved=[original])
    output=next(t for t in entries if t['name']=='work.save_observation')['execute']({'quote':'Клиент отказался от ухода, дорого','outcome':'declined'})
    assert output['status']=='clarification_required'
    c.execute('SELECT COUNT(*) n FROM business_work_journal');assert c.fetchone()['n']==1

@pytest.mark.parametrize('channel',['web','telegram','telegram_mini_app'])
@pytest.mark.parametrize('voice',[False,True])
def test_owner_rules_through_existing_confirmation(journal,channel,voice):
    conn,c=journal;message='Постоянно не предлагайте уход';payload={'request_id':'rule'}
    if voice:
        asset=operator_audio.create_transcription(c,content=b'fixture',user_id='u',business_id='b',channel=channel,conversation_id=None,request_id='recording')
        c.execute("UPDATE operator_audio_assets SET transcript=%s,status='ready' WHERE id=%s",(message,asset['asset_id']))
        c.execute("UPDATE operator_async_jobs SET status='completed' WHERE id=%s",(asset['job_id'],))
        payload.update(transcription_id=asset['asset_id'],conversation_id=asset['conversation_id'])
    class Orchestrator:
        prepared=None
        def execute(self,envelope,user):
            self.prepared=envelope
            return {'success':True,'status':'pending_human','action_id':'owner-rule','approval':{'status':'pending_human'}}
        def resolve_human_decision(self,*args,**kwargs):
            saved=work_recommendations.apply_policy(c,'b','u',self.prepared['payload'],'owner-rule')
            return {'success':True,'status':'completed','result':{'status':'completed','saved':saved,'chat_response':'Правила сохранены'}}
    orchestrator=Orchestrator()
    def router(cursor,**args):return operator_core.route_operator_message(cursor,tool_planner=lambda state:{'action':'tool_call','tool':'work.prepare_policy','arguments':{'changes':[rule()]}},action_orchestrator=orchestrator,**args)
    preview=operator_chat_service.process_chat(c,business_id='b',user_id='u',channel=channel,message=message,payload=payload,router=router);conn.commit()
    assert preview['status']=='approval_required',preview
    assert work_recommendations.policy(c,'b')['version']==0
    kwargs=dict(action_id=preview['approval']['action_id'],business_id='b',user_id='u',action_orchestrator=orchestrator)
    result,_=operator_core.confirm_pending_operator_action(c,**kwargs)
    assert result['status']=='completed',result
    _,replay=operator_core.confirm_pending_operator_action(c,**kwargs);assert replay
    assert work_recommendations.policy(c,'b')['version']==1


def test_binding_creation_and_assignment_require_confirmation(journal):
    _,c=journal
    envelope=work_recommendations.prepare_policy(c,'b','u',{'kind':'binding','user_id':'admin','master_name':'Новый мастер'})
    c.execute("SELECT COUNT(*) n FROM masters");assert c.fetchone()['n']==2
    saved=work_recommendations.apply_policy(c,'b','u',envelope,'binding')
    master_id=saved['applied_change']['master_id']
    c.execute("SELECT master_id FROM business_master_bindings WHERE user_id='admin'");assert c.fetchone()['master_id']==master_id
    appointment=work_recommendations.prepare_policy(c,'b','u',{'kind':'assignment','master_id':master_id,'booking_id':'v1'})
    work_recommendations.apply_policy(c,'b','u',appointment,'assign')
    with pytest.raises(PermissionError):work_recommendations.recommend(c,'b','master',{'booking_id':'v1'})


def test_permanent_instruction_is_not_misrouted_to_content():
    from services.operator_work_journal import matches
    assert matches('Постоянно не предлагайте уход')
    assert not matches('Подготовь пост про уход')


def test_correction_does_not_keep_old_derived_outcome(journal):
    _,c=journal;row=note(c)
    changed=work_journal.save_note(c,'b','master','web','message2','fix','Клиент спросил про парковку',{'id':row['id'],'version':1,'quote':'Клиент спросил про парковку'})
    assert changed['facts_json']['outcome']=='note'
    c.execute('SELECT COUNT(*) n FROM averageticketevents WHERE NOT is_voided');assert c.fetchone()['n']==0


def test_unapproved_generated_matrix_does_not_replace_confirmed_recommendations(journal):
    _,c=journal
    envelope=work_recommendations.prepare_policy(c,'b','u',{'changes':[rule(addon_service_id='kit')]})
    work_recommendations.apply_policy(c,'b','u',envelope,'ban-kit')
    c.execute("INSERT INTO averageticketmatrices(id,business_id,matrix_json,generated_at) VALUES ('new','b','{}',NOW()+INTERVAL '1 minute')")
    result=work_recommendations.recommend(c,'b','master',{'booking_id':'v1'})
    assert [r['service_id'] for r in result['items'][0]['recommendations']]==['care']


def test_http_access_edit_history_and_cross_business(journal,monkeypatch):
    conn,c=journal
    from flask import Flask
    from api import work_journal_api
    class DB:
        def __init__(self):self.conn=conn
        def close(self):pass
    monkeypatch.setattr(work_journal_api,'DatabaseManager',DB)
    monkeypatch.setattr(work_journal_api,'verify_session',lambda token:{'user_id':token} if token in {'master','viewer','u','admin'} else None)
    app=Flask(__name__);app.register_blueprint(work_journal_api.work_journal_bp)
    client=app.test_client()
    assert client.get('/api/work-journal?business_id=b').status_code==403
    headers={'Authorization':'Bearer master'}
    response=client.post('/api/work-journal',headers=headers,json={'business_id':'b','text':'Клиент отказался от ухода, дорого','booking_id':'v1','outcome':'declined','request_id':'api'})
    assert response.status_code==200,response.json
    entry=response.json['entry'];conn.commit()
    assert client.get('/api/work-journal?business_id=b',headers=headers).json['items'][0]['can_edit']
    assert client.get('/api/work-journal?business_id=other',headers=headers).status_code==403
    assert client.patch('/api/work-journal/'+entry['id'],headers={'Authorization':'Bearer viewer'},json={'business_id':'b','version':1,'void':True,'request_id':'forbidden'}).status_code==403
    assert client.get('/api/work-journal/'+entry['id']+'/history?business_id=b',headers=headers).json['items'][0]['after_json']['change_source']['text']=='Клиент отказался от ухода, дорого'


def test_supported_rule_predicates_only(journal):
    _,c=journal
    with pytest.raises(ValueError,match='не поддерживается'):
        work_recommendations.prepare_policy(c,'b','u',{'changes':[rule(skin_condition='sensitive')]})
    with pytest.raises(ValueError,match='срок'):
        work_recommendations.prepare_policy(c,'b','u',{'changes':[rule(permanent=False)]})
