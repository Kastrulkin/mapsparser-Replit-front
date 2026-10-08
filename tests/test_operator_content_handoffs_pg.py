from psycopg2.extras import Json
from tests.test_outreach_continuation_pg import db
from services import operator_content_handoffs as handoff, telegram_control_scope
import pytest


@pytest.fixture
def configured(db,monkeypatch):
    conn,cur=db
    cur.execute('ALTER TABLE users ADD COLUMN name TEXT')
    cur.execute("UPDATE users SET name='Ирина' WHERE id='u2'")
    cur.execute('CREATE TABLE telegramcontrolpreferences(user_id TEXT PRIMARY KEY,telegram_id TEXT,notification_preferences_json JSONB,updated_at TIMESTAMPTZ)')
    settings={'content_publications':True,'content_publications_lead_days':1,'content_publications_time':'10:30','reviews':True}
    cur.execute("INSERT INTO telegramcontrolpreferences VALUES('u2','bot-recipient',%s,NOW())",(Json({'business:b':settings,'business:b2':{'tasks':True}}),))
    monkeypatch.setattr(handoff,'_authorized_actor',lambda *args,**kwargs:{'is_superadmin':True})
    monkeypatch.setattr('services.operator_audio.authorize_actor',lambda *args,**kwargs:None)
    monkeypatch.setattr('services.business_input_settings.resolve',lambda *args:{'timezone':'Europe/Moscow'})
    def read(cursor,user):
        cursor.execute('SELECT * FROM telegramcontrolpreferences WHERE user_id=%s',(user,))
        return dict(cursor.fetchone() or {})
    monkeypatch.setattr(telegram_control_scope,'_load_preference',read)
    return conn,cur


def test_handoff_updates_same_saved_recipient_and_preserves_other_preferences(configured):
    _,cur=configured
    preview=handoff.legacy_operator_task(cur,business_id='b',user_id='u',arguments={'operation':'configure','settings':{'platforms':['vk','telegram','max']}})
    assert preview['status']=='approval_required'
    assert '10:30' in preview['chat_response'] and 'Ирина' in preview['chat_response']
    result=handoff.execute(cur,business_id='b',user_id='u',envelope=preview['approval']['envelope'])
    assert result['status']=='completed'
    cur.execute('SELECT * FROM telegramcontrolpreferences')
    records=cur.fetchall()
    assert len(records)==1 and records[0]['telegram_id']=='bot-recipient' and records[0]['user_id']=='u2'
    prefs=records[0]['notification_preferences_json']
    assert prefs['business:b']['reviews'] and prefs['business:b']['content_publications_time']=='10:30'
    assert prefs['business:b']['content_publications_platforms']==['max','telegram','vk']
    assert prefs['business:b2']=={'tasks':True}


def test_changed_binding_requires_new_confirmation(configured):
    _,cur=configured
    preview=handoff.legacy_operator_task(cur,business_id='b',user_id='u',arguments={'operation':'pause'})
    cur.execute("UPDATE telegramcontrolpreferences SET telegram_id='different'")
    result=handoff.execute(cur,business_id='b',user_id='u',envelope=preview['approval']['envelope'])
    assert result['status']=='blocked' and 'handoff_binding_changed' in result['blocked_reasons']


def test_multiple_recipients_clarify_without_selecting_business_owner(configured):
    _,cur=configured
    cur.execute("INSERT INTO telegramcontrolpreferences VALUES('u','owner-bot','{\"business:b\":{\"content_publications\":true}}',NOW())")
    result=handoff.legacy_operator_task(cur,business_id='b',user_id='u',arguments={'operation':'resume'})
    assert result['status']=='clarification_required' and len(result['recipients'])==2
    result=handoff.legacy_operator_task(cur,business_id='b',user_id='u',arguments={'operation':'resume','recipient_user_id':'u2'})
    assert result['approval']['envelope']['recipient_user_id']=='u2'


def test_non_admin_cannot_manage_other_persons_handoff(configured,monkeypatch):
    _,cur=configured
    monkeypatch.setattr(handoff,'_authorized_actor',lambda *args,**kwargs:{'is_superadmin':False})
    result=handoff.operator_task(cur,business_id='b',user_id='u',arguments={'operation':'pause'})
    assert result['status']=='blocked'


@pytest.mark.parametrize('changes',[None,{},'bad',{'reviews':False},{'content_publications':'false'},
    {'content_publications_platforms':[]},{'content_publications_lead_days':8},{'content_publications_time':None}])
def test_execution_strictly_rechecks_handoff_changes(configured,changes):
    _,cur=configured
    preview=handoff.legacy_operator_task(cur,business_id='b',user_id='u',arguments={'operation':'pause'})
    envelope={**preview['approval']['envelope'],'changes':changes}
    cur.execute('SELECT notification_preferences_json FROM telegramcontrolpreferences')
    before=cur.fetchone()['notification_preferences_json']
    result=handoff.execute(cur,business_id='b',user_id='u',envelope=envelope)
    assert result['status']=='blocked'
    cur.execute('SELECT notification_preferences_json FROM telegramcontrolpreferences')
    assert cur.fetchone()['notification_preferences_json']==before
