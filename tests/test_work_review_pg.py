import importlib.util
from pathlib import Path
import pytest
from tests.test_work_journal_pg import journal, note
from tests.test_finance_daily_pg import daily
from tests.test_operator_voice_pg import pg
from services import work_review, work_journal


@pytest.fixture
def review(journal,monkeypatch):
    conn,c=journal
    c.execute("CREATE TABLE journey_actions(id UUID PRIMARY KEY,business_id TEXT,user_id TEXT,flow_type TEXT CHECK(flow_type IS NOT NULL),entity_type TEXT,entity_id TEXT,action_type TEXT,status TEXT DEFAULT 'ready',title TEXT,description TEXT,cta_label TEXT,cta_target_json JSONB,payload_json JSONB,dedupe_key TEXT,due_at TIMESTAMPTZ,created_at TIMESTAMPTZ DEFAULT NOW(),completed_at TIMESTAMPTZ,version INTEGER DEFAULT 1,updated_at TIMESTAMPTZ DEFAULT NOW(),CONSTRAINT ck_journey_actions_flow CHECK(flow_type IN ('content','automation')))")
    from alembic import op
    monkeypatch.setattr(op,'execute',c.execute)
    spec=importlib.util.spec_from_file_location('review_migration',Path(__file__).parents[1]/'alembic_migrations/versions/20260914_work_review.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.upgrade();module.upgrade()
    monkeypatch.setenv('OPERATOR_WORK_REVIEW_BUSINESS_IDS','b')
    return conn,c


def test_grant_revoke_privacy_and_replay(review):
    _,c=review
    row=note(c)
    assert work_journal.list_entries(c,'b','admin')==[]
    with pytest.raises(PermissionError):work_review.list_inbox(c,'b','admin')
    grant=work_review.prepare_grant(c,'b','u',{'user_id':'admin'})
    work_review.apply_grant(c,'b','u',grant,'grant')
    assert len(work_review.list_inbox(c,'b','admin'))==1
    args={'request_id':'decision','version':row['version'],'status':'in_progress','decision':'Внутренний комментарий'}
    changed=work_review.decision(c,'b','admin',row['id'],args)
    assert work_review.decision(c,'b','admin',row['id'],args)['version']==changed['version']
    assert 'decision' not in work_journal.list_entries(c,'b','master')[0]
    assert all('decision' not in h['after_json'] for h in work_journal.history(c,'b','master',row['id']))
    revoke=work_review.prepare_grant(c,'b','u',{'user_id':'admin','enabled':False})
    work_review.apply_grant(c,'b','u',revoke,'revoke')
    with pytest.raises(PermissionError):work_review.decision(c,'b','admin',row['id'],args)


def test_stale_decision_and_atomic_task(review):
    _,c=review
    row=note(c)
    changed=work_review.decision(c,'b','u',row['id'],{'request_id':'accept','version':1,'status':'in_progress'})
    with pytest.raises(ValueError,match='изменилась'):work_review.decision(c,'b','u',row['id'],{'request_id':'stale','version':1,'status':'observing'})
    args={'request_id':'task','version':changed['version'],'title':'Уточнить встречу клиента','kind':'task','assigned_to':'admin'}
    task=work_review.create_action(c,'b','u',row['id'],args)
    assert work_review.create_action(c,'b','u',row['id'],args)['id']==task['id']
    assert len(work_review.links(c,'b','u',row['id']))==1
    assert 'description' not in work_review.links(c,'b','master',row['id'])[0]
    c.execute('SELECT COUNT(*) n FROM financialtransactions');assert c.fetchone()['n']==0


def test_staff_correction_does_not_expose_internal_decision(review):
    _,c=review
    row=note(c)
    changed=work_review.decision(c,'b','u',row['id'],{'request_id':'secret','version':1,'status':'observing','decision':'Внутреннее расследование'})
    args={'id':row['id'],'version':changed['version'],'quote':'Клиент отказался от ухода, дорого'}
    corrected=work_journal.save_note(c,'b','master','web',None,'correction',args['quote'],args)
    assert 'decision' not in corrected
    assert 'decision' not in work_journal.save_note(c,'b','master','web',None,'correction',args['quote'],args)


def test_explicit_urgency_only(review):
    _,c=review
    assert note(c,key='urgent',quote='Срочно: клиентка недовольна',outcome='note',reason=None,booking_id=None)['urgent']
    assert not note(c,key='normal',quote='Не срочно: клиентка недовольна',outcome='note',reason=None,booking_id=None)['urgent']


def test_digest_uses_business_zone_and_no_duplicate(review,monkeypatch):
    from services import work_review_notifications, business_input_settings
    from datetime import datetime,timezone
    _,c=review
    c.execute("ALTER TABLE businesses ADD COLUMN IF NOT EXISTS owner_id TEXT")
    c.execute("UPDATE businesses SET owner_id='u' WHERE id='b'")
    row=note(c,booking_id=None)
    c.execute("UPDATE business_work_journal SET created_at='2026-09-14T09:00:00Z' WHERE id=%s",(row['id'],))
    monkeypatch.setattr(business_input_settings,'resolve',lambda *args:{'timezone':'Europe/Tallinn'})
    work_review_notifications.collect(c,datetime(2026,9,14,14,59,tzinfo=timezone.utc))
    c.execute('SELECT COUNT(*) n FROM journey_actions');assert c.fetchone()['n']==0
    work_review_notifications.collect(c,datetime(2026,9,14,15,tzinfo=timezone.utc))
    work_review_notifications.collect(c,datetime(2026,9,14,15,1,tzinfo=timezone.utc))
    c.execute('SELECT COUNT(*) n FROM journey_actions');assert c.fetchone()['n']==1
    work_review_notifications.collect(c,datetime(2026,9,15,15,tzinfo=timezone.utc))
    c.execute('SELECT COUNT(*) n FROM journey_actions');assert c.fetchone()['n']==1


def test_shared_task_link_and_manual_result_is_not_external_success(review):
    _,c=review
    row=note(c)
    row=work_review.decision(c,'b','u',row['id'],{'request_id':'accept','version':1,'status':'in_progress'})
    action=work_review.create_action(c,'b','u',row['id'],{'request_id':'action','version':row['version'],'title':'Уточнить жалобу'})
    args={'action_id':str(action['id']),'request_id':'finished','version':action['version'],'result':'Администратор уточнил обстоятельства'}
    finished=work_review.complete_action(c,'b','u',row['id'],args)
    assert finished['payload_json']['result_source']=='manual_report'
    assert work_review.complete_action(c,'b','u',row['id'],args)['version']==finished['version']
    assert work_journal.read_entry(c,'b',work_journal.scope(c,'b','u'),row['id'])['review_status']=='in_progress'


def test_rollback_flag_does_not_relax_employee_privacy(review,monkeypatch):
    _,c=review
    note(c)
    monkeypatch.setenv('OPERATOR_WORK_REVIEW_BUSINESS_IDS','')
    assert work_journal.list_entries(c,'b','admin')==[]
    assert len(work_journal.list_entries(c,'b','u'))==1


def test_review_delivery_does_not_enable_unrelated_notifications(review,monkeypatch):
    from services import journey_action_notifications, business_input_settings
    _,c=review
    c.execute('ALTER TABLE businesses ADD COLUMN IF NOT EXISTS owner_id TEXT')
    c.execute("UPDATE businesses SET owner_id='u' WHERE id='b'")
    c.execute('ALTER TABLE journey_actions ADD COLUMN priority INTEGER DEFAULT 50')
    c.execute('CREATE TABLE telegramcontrolpreferences(user_id TEXT,telegram_id TEXT,notification_preferences_json JSONB)')
    c.execute("INSERT INTO telegramcontrolpreferences VALUES ('u','123','{}'),('admin','456','{}')")
    c.execute('''CREATE TABLE journey_action_notification_deliveries(dedupe_key TEXT PRIMARY KEY,action_id UUID,action_version INTEGER,user_id TEXT,telegram_id TEXT,message_text TEXT,reply_markup_json JSONB,sent_at TIMESTAMPTZ,created_at TIMESTAMPTZ DEFAULT NOW())''')
    monkeypatch.setenv('JOURNEY_NOTIFICATIONS_ENABLED','false')
    monkeypatch.setattr(business_input_settings,'resolve',lambda *args:{})
    grant=work_review.prepare_grant(c,'b','u',{'user_id':'admin'})
    work_review.apply_grant(c,'b','u',grant,'grant')
    note(c,key='urgent',quote='Срочно: клиентка недовольна',outcome='note',reason=None,booking_id=None)
    delivered=journey_action_notifications.collect_due_journey_action_notifications(review[0])
    assert {item['telegram_id'] for item in delivered}=={'123','456'}
    revoke=work_review.prepare_grant(c,'b','u',{'user_id':'admin','enabled':False})
    work_review.apply_grant(c,'b','u',revoke,'revoke')
    remaining=journey_action_notifications.collect_due_journey_action_notifications(review[0])
    assert {item['telegram_id'] for item in remaining}=={'123'}


def test_manager_grant_is_applied_only_after_existing_confirmation(review):
    from services import operator_chat_service,operator_core,work_recommendations
    conn,c=review
    class Orchestrator:
        prepared=None
        def execute(self,envelope,user):
            self.prepared=envelope
            return {'success':True,'status':'pending_human','action_id':'grant-manager','approval':{'status':'pending_human'}}
        def resolve_human_decision(self,*args,**kwargs):
            saved=work_recommendations.apply_policy(c,'b','u',self.prepared['payload'],'grant-manager')
            return {'success':True,'status':'completed','result':saved}
    orchestrator=Orchestrator()
    def router(cursor,**kwargs):return operator_core.route_operator_message(cursor,tool_planner=lambda state:{'action':'tool_call','tool':'work.prepare_policy','arguments':{'kind':'reviewer','user_id':'admin','enabled':True}},action_orchestrator=orchestrator,**kwargs)
    result=operator_chat_service.process_chat(c,business_id='b',user_id='u',channel='web',message='Дай управляющему право разбора журнала',payload={'request_id':'grant'},router=router)
    conn.commit()
    assert result['status']=='approval_required'
    assert not work_review.can_review(c,'b','admin')
    applied,_=operator_core.confirm_pending_operator_action(c,action_id=result['approval']['action_id'],business_id='b',user_id='u',action_orchestrator=orchestrator)
    assert applied['status']=='completed'
    assert work_review.can_review(c,'b','admin')


def test_one_task_can_address_multiple_observations(review):
    _,c=review
    first=note(c,key='first');second=note(c,key='second')
    first=work_review.decision(c,'b','u',first['id'],{'request_id':'first-accept','version':1,'status':'in_progress'})
    second=work_review.decision(c,'b','u',second['id'],{'request_id':'second-accept','version':1,'status':'in_progress'})
    action=work_review.create_action(c,'b','u',first['id'],{'request_id':'create','version':first['version'],'title':'Разобрать похожие жалобы'})
    args={'request_id':'link','version':second['version'],'existing_action_id':str(action['id']),'action_version':action['version']}
    work_review.create_action(c,'b','u',second['id'],args)
    work_review.create_action(c,'b','u',second['id'],args)
    c.execute('SELECT COUNT(*) n FROM journey_actions');assert c.fetchone()['n']==1
    c.execute('SELECT COUNT(*) n FROM business_work_links');assert c.fetchone()['n']==2


def test_unknown_event_time_is_not_an_invented_date(review):
    _,c=review
    row=note(c,key='uncertain-time',quote='Клиентка была недовольна встречей в прошлый раз',outcome='note',reason=None,booking_id=None,occurred_at='2020-01-01T00:00:00Z')
    assert row['occurred_at'].year!=2020
    assert not row['facts_json']['event_time_known']
