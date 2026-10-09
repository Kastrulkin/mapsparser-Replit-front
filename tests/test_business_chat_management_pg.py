"""Disposable PostgreSQL checks for profile changes and owner-managed staff."""
import importlib.util
from pathlib import Path
import pytest
from tests.test_operator_voice_pg import pg
from tests.test_finance_daily_pg import daily
from services import business_chat_changes, business_team_management, operator_business_management, operator_core
from services.business_permissions import load_actor, require_permission
from services.business_member_directory import list_business_members

SCREENSHOT = '''Весёлая расчёска: часовой пояс не задан или неверен, использован UTC. - часовой пояс +3UTC Москва
My journey Together: часовой пояс не задан или неверен, использован UTC. - Дубай
Alternativ Taxi: часовой пояс не задан или неверен, использован UTC. - Дания, Орхус

Проставь часовые пояса'''


@pytest.fixture
def managed(daily, monkeypatch):
    conn,c = daily
    c.execute("ALTER TABLE users ADD COLUMN name TEXT, ADD COLUMN email TEXT UNIQUE, ADD COLUMN password_hash TEXT, ADD COLUMN verification_token TEXT, ADD COLUMN is_active BOOLEAN DEFAULT TRUE, ADD COLUMN is_superadmin BOOLEAN DEFAULT FALSE, ADD COLUMN is_verified BOOLEAN DEFAULT FALSE, ADD COLUMN created_at TIMESTAMPTZ DEFAULT NOW(), ADD COLUMN updated_at TIMESTAMPTZ DEFAULT NOW()")
    c.execute("UPDATE users SET email='owner@example.ru'")
    c.execute('CREATE TABLE networks(id TEXT PRIMARY KEY,name TEXT,owner_id TEXT REFERENCES users(id))')
    c.execute('ALTER TABLE businesses ADD COLUMN owner_id TEXT, ADD COLUMN network_id TEXT REFERENCES networks(id), ADD COLUMN is_active BOOLEAN DEFAULT TRUE, ADD COLUMN business_type TEXT, ADD COLUMN address TEXT, ADD COLUMN city TEXT, ADD COLUMN working_hours TEXT, ADD COLUMN geo_lat NUMERIC, ADD COLUMN geo_lon NUMERIC, ADD COLUMN site TEXT, ADD COLUMN website TEXT, ADD COLUMN updated_at TIMESTAMPTZ DEFAULT NOW()')
    c.execute("UPDATE businesses SET name='Весёлая расчёска',owner_id='u'")
    c.execute("INSERT INTO businesses(id,name,owner_id) VALUES ('b2','My journey Together','u'),('b3','Alternativ Taxi','u')")
    c.execute('CREATE TABLE businessprofiles(business_id TEXT PRIMARY KEY,contact_name TEXT,contact_email TEXT,contact_phone TEXT,updated_at TIMESTAMPTZ DEFAULT NOW())')
    c.execute('ALTER TABLE business_finance_settings ADD COLUMN city TEXT')
    c.execute('DELETE FROM business_finance_settings')
    from alembic import op
    monkeypatch.setattr(op,'execute',c.execute)
    for filename in ['20260729_add_network_members.py','20260729_add_business_members.py','20261009_business_chat_management.py']:
        path=Path(__file__).parents[1]/'alembic_migrations/versions'/filename
        spec=importlib.util.spec_from_file_location('management_migration',path)
        migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
        migration.upgrade();migration.upgrade()
    conn.commit()
    return conn,c


@pytest.mark.parametrize('channel',['web','telegram'])
def test_original_screenshot_prepares_three_correct_zones(managed,monkeypatch,channel):
    _,c=managed
    captured=[]
    def approval(**kwargs):
        captured.append(kwargs)
        return {'status':'approval_required','capability':kwargs['capability'],'approval':{'envelope':{'orchestrator_action_id':'o'}}}
    monkeypatch.setattr(operator_core,'_prepare_registered_capability_approval',approval)
    result,_=operator_core.route_operator_message(c,business_id='b',user_id='u',channel=channel,message=SCREENSHOT)
    assert result['status']=='approval_required'
    assert [(change['business_id'],change['patch']) for change in captured[0]['payload']['changes']] == [
        ('b',{'timezone':'Europe/Moscow'}),('b2',{'timezone':'Asia/Dubai'}),('b3',{'timezone':'Europe/Copenhagen'})]
    c.execute('SELECT count(*) n FROM business_finance_settings')
    assert c.fetchone()['n']==0


def test_settings_atomic_apply_replay_and_website_aliases(managed):
    conn,c=managed
    payload=business_chat_changes.prepare(c,'b','u',{'changes':[
        {'patch':{'website':'example.ru','address':'Ленина, 10','city':'Дубай'}},
        {'business':'b3','patch':{'timezone':'Europe/Copenhagen'}}]})
    assert payload['changes'][0]['patch']['timezone']=='Asia/Dubai'
    result=business_chat_changes.apply(c,'b','u',payload,'settings-action');conn.commit()
    assert result['status']=='completed'
    assert business_chat_changes.apply(c,'b','u',payload,'settings-action')==result
    c.execute("SELECT site,website,city,address FROM businesses WHERE id='b'")
    assert c.fetchone()=={'site':'https://example.ru','website':'https://example.ru','city':'Дубай','address':'Ленина, 10'}
    c.execute("SELECT timezone FROM business_finance_settings WHERE business_id='b'")
    assert c.fetchone()['timezone']=='Asia/Dubai'
    c.execute('SELECT count(*) n FROM business_change_receipts')
    assert c.fetchone()['n']==1


def test_batch_conflict_prevents_every_write(managed):
    conn,c=managed
    payload=business_chat_changes.prepare(c,'b','u',{'changes':[{'patch':{'website':'one.ru'}},{'business':'b2','patch':{'address':'New address'}}]})
    c.execute("UPDATE businesses SET address='Changed elsewhere' WHERE id='b2'");conn.commit()
    with pytest.raises(ValueError,match='изменились'):
        business_chat_changes.apply(c,'b','u',payload,'stale')
    conn.rollback()
    c.execute("SELECT site FROM businesses WHERE id='b'")
    assert c.fetchone()['site'] is None


def test_lost_rights_and_ambiguous_names_are_rejected(managed):
    conn,c=managed
    payload=business_chat_changes.prepare(c,'b','u',{'changes':[{'business':'b2','patch':{'address':'New address'}}]})
    c.execute("INSERT INTO users(id,email) VALUES ('other','other@example.ru')")
    c.execute("UPDATE businesses SET owner_id='other' WHERE id='b2'");conn.commit()
    with pytest.raises(PermissionError):business_chat_changes.apply(c,'b','u',payload,'lost')
    conn.rollback()
    c.execute("UPDATE businesses SET name='Весёлая расчёска' WHERE id='b3'")
    with pytest.raises(ValueError,match='Уточните бизнес'):
        business_chat_changes.prepare(c,'b','u',{'changes':[{'business':'Весёлая расчёска','patch':{'address':'New address'}}]})


def test_team_add_is_idempotent_and_master_permissions_are_distinct(managed):
    conn,c=managed
    args={'email':'anna@example.ru','name':'Анна','role':'master','scope':'business','businesses':['b','b2'],'send_invitation':False}
    payload=business_team_management.prepare(c,'b','u',args)
    result=business_team_management.apply(c,'b','u',payload,'team-action');conn.commit()
    assert business_team_management.apply(c,'b','u',payload,'team-action')==result
    c.execute("SELECT count(*) n FROM users WHERE email='anna@example.ru'");assert c.fetchone()['n']==1
    c.execute('SELECT count(*) n FROM business_members');assert c.fetchone()['n']==2
    actor=load_actor(c,result['user_id'])
    require_permission(c,'b',actor,'work.facts.write')
    with pytest.raises(PermissionError):require_permission(c,'b',actor,'operations.write')
    with pytest.raises(PermissionError):require_permission(c,'b',actor,'business.settings.write')
    with pytest.raises(PermissionError):business_team_management.prepare(c,'b',result['user_id'],{**args,'email':'new@example.ru'})


def test_suspended_account_and_owner_role_cannot_be_changed(managed):
    _,c=managed
    c.execute("INSERT INTO users(id,email,is_active) VALUES ('disabled','disabled@example.ru',FALSE)")
    args={'role':'admin','scope':'business','send_invitation':False}
    with pytest.raises(PermissionError,match='отключён'):
        business_team_management.prepare(c,'b','u',{**args,'email':'disabled@example.ru'})
    with pytest.raises(ValueError,match='владельца'):
        business_team_management.prepare(c,'b','u',{**args,'email':'owner@example.ru'})


def test_team_change_detects_concurrent_membership(managed):
    conn,c=managed
    c.execute("INSERT INTO users(id,email) VALUES ('staff','staff@example.ru')");conn.commit()
    args={'email':'staff@example.ru','role':'admin','scope':'business','send_invitation':False}
    payload=business_team_management.prepare(c,'b','u',args)
    c.execute("INSERT INTO business_members(id,business_id,user_id,role) VALUES ('m','b','staff','viewer')");conn.commit()
    with pytest.raises(ValueError,match='изменились'):
        business_team_management.apply(c,'b','u',payload,'stale-member')


@pytest.mark.parametrize('sent,status',[(False,'failed'),(True,'sent')])
def test_invitation_delivery_is_separate_and_not_repeated(managed,monkeypatch,sent,status):
    conn,c=managed
    from core import email_delivery
    calls=[]
    monkeypatch.setattr(email_delivery,'send_email',lambda *args: calls.append(args) or sent)
    payload=business_team_management.prepare(c,'b','u',{'email':'anna@example.ru','role':'admin','scope':'business','send_invitation':True})
    result=business_team_management.apply(c,'b','u',payload,'invite');conn.commit()
    assert result['membership_saved'] and result['invitation_status']=='pending' and not calls
    class Database:
        pass
    db=Database();db.conn=conn
    result=business_team_management.deliver_invitation(db,'invite',result)
    assert result['invitation_status']==status
    replay=business_team_management.apply(c,'b','u',payload,'invite');conn.commit()
    business_team_management.deliver_invitation(db,'invite',replay)
    assert len(calls)==1


def test_network_members_are_visible_once(managed):
    conn,c=managed
    c.execute("INSERT INTO networks(id,name,owner_id) VALUES ('n','Network','u')")
    c.execute("UPDATE businesses SET network_id='n' WHERE id='b'")
    payload=business_team_management.prepare(c,'b','u',{'email':'anna@example.ru','role':'admin','scope':'network','send_invitation':False})
    result=business_team_management.apply(c,'b','u',payload,'network-invite');conn.commit()
    c.execute("INSERT INTO business_members(id,business_id,user_id,role) VALUES ('direct','b',%s,'viewer')",(result['user_id'],))
    members=list_business_members(c,'b')
    staff=[member for member in members if member['id']==result['user_id']]
    assert len(staff)==1 and len(staff[0]['access'])==2


def test_tool_planner_prepares_address_and_site_through_same_registry(managed,monkeypatch):
    _,c=managed
    def approval(**kwargs):
        return {'status':'approval_required','capability':kwargs['capability'],'approval':{'envelope':{'orchestrator_action_id':'o'}}}
    monkeypatch.setattr(operator_core,'_prepare_registered_capability_approval',approval)
    def planner(state):
        assert any(tool['name']=='settings.prepare_changes' for tool in state['tools'])
        return {'action':'tool_call','tool':'settings.prepare_changes','arguments':{'changes':[{'patch':{'website':'example.ru','address':'Ленина, 10'}}]}}
    result,_=operator_core.route_operator_message(c,business_id='b',user_id='u',channel='web',message='Измени адрес и сайт бизнеса',tool_planner=planner)
    assert result['status']=='approval_required'
    assert result['preview']['changes'][0]['patch']=={'website':'https://example.ru','address':'Ленина, 10'}


def test_master_cannot_write_through_legacy_access_boundary(managed):
    _,c=managed
    from flask import Flask
    from core.auth_helpers import verify_business_access, verify_business_write_access
    c.execute("INSERT INTO users(id,email) VALUES ('master','master@example.ru')")
    c.execute("INSERT INTO business_members(id,business_id,user_id,role) VALUES ('m','b','master','master')")
    user=load_actor(c,'master')
    app=Flask(__name__)
    with app.test_request_context('/api/services/update',method='POST'):
        assert verify_business_access(c,'b',user)[0] is False
    with app.test_request_context('/api/operator/chat',method='POST'):
        assert verify_business_access(c,'b',user)[0] is True
        assert verify_business_write_access(c,'b',user)[0] is False


def test_new_capabilities_always_require_human_review():
    from core.action_policy import evaluate_risk_policy
    for capability in ['business.settings.apply_operator','business.team.apply_operator']:
        assert evaluate_risk_policy(capability,{}, {'mode':'auto'})['requires_human'] is True


def test_team_preview_explains_retained_network_rights(managed):
    _,c=managed
    c.execute("INSERT INTO users(id,email,name) VALUES ('staff','staff@example.ru','Существующее имя')")
    c.execute("INSERT INTO networks(id,name,owner_id) VALUES ('n','Сеть','u')")
    c.execute("UPDATE businesses SET network_id='n' WHERE id='b'")
    c.execute("INSERT INTO network_members(id,network_id,user_id,role) VALUES ('network-admin','n','staff','admin')")
    payload=business_team_management.prepare(c,'b','u',{'email':'staff@example.ru','name':'Другое имя','role':'master','scope':'business','send_invitation':False})
    assert payload['name']=='Существующее имя'
    assert 'доступ через сеть сохранится' in business_team_management.preview_text(payload)


def test_cancelled_clarification_does_not_intercept_next_task(managed,monkeypatch):
    _,c=managed
    monkeypatch.setattr(operator_core,'_read_requested_content',lambda *args:{'status':'completed','chat_response':'Контент прочитан'})
    result,_=operator_core.route_operator_message(c,business_id='b',user_id='u',channel='web',message='Покажи контент',pending_context={'capability':'settings.profile.clarification'})
    assert result['capability']!='settings.profile'


def test_timezone_batch_with_missing_assignment_never_prepares_partial_changes(managed):
    _,c=managed
    literal=operator_business_management.timezone_lines(SCREENSHOT.replace('Дания, Орхус','неизвестный город'))
    assert len(literal['changes'])==3
    result=operator_business_management.preview(c,'b','u',literal,kind='settings',channel='web',message=SCREENSHOT)
    assert result['status']=='clarification_required'
    c.execute('SELECT count(*) n FROM business_change_receipts');assert c.fetchone()['n']==0


def test_profile_management_schema_exposes_only_owner_controls(managed,monkeypatch):
    conn,c=managed
    from flask import Flask,Blueprint
    from api import business_management_api
    class Database:
        def __init__(self):self.conn=conn
        def rollback_and_close(self):conn.rollback()
    monkeypatch.setattr(business_management_api,'DatabaseManager',Database)
    monkeypatch.setattr(business_management_api,'require_auth_from_request',lambda:{'user_id':'u'})
    app=Flask(__name__);bp=Blueprint('management',__name__)
    business_management_api.register_business_management_routes(bp);app.register_blueprint(bp)
    response=app.test_client().get('/business-management?business_id=b')
    assert response.status_code==200
    assert response.json['can_manage_team'] and response.json['can_edit']
    assert not response.json['can_manage_network']
    assert {'admin','master','viewer'} <= {role['key'] for role in response.json['roles']}


@pytest.mark.parametrize('channel',['web','telegram'])
def test_named_lookup_and_selected_network_work_beyond_catalog_limit(managed,channel):
    _,c=managed
    c.execute("INSERT INTO businesses(id,name,owner_id) SELECT 'bulk-'||n, 'Ааа', 'u' FROM generate_series(1,1100) n")
    c.execute("INSERT INTO networks(id,name,owner_id) VALUES ('roga','Рога и копыта','u')")
    c.execute("UPDATE businesses SET name='Рога и копыта',network_id='roga' WHERE id='b'")
    c.execute("UPDATE businesses SET name='Рога и копыта — Красивых партизан',network_id='roga' WHERE id='b2'")
    c.execute("UPDATE users SET is_superadmin=TRUE WHERE id='u'")
    actor=load_actor(c,'u')
    catalog=business_chat_changes.owned_businesses(c,actor)
    assert len(catalog)==1000
    assert not any('Рога' in business['name'] for business in catalog)
    assert business_chat_changes.resolve_target(c,actor,'Рога и копыта','b2')=='b2'
    assert business_chat_changes.resolve_target(c,actor,'b','b2')=='b'
    assert business_chat_changes.resolve_target(c,actor,'Рога и копыта — Красивых партизан','b3')=='b2'
    tools=operator_business_management.tools(c,'b2','u','Покажи настройки бизнеса Рога и копыта',channel)
    find=next(tool for tool in tools if tool['name']=='settings.list_businesses')
    result=find['execute']({'query':'Рога и копыта'})
    assert result['selected_business']['id']=='b2'
    assert {business['id'] for business in result['businesses']}=={'b','b2'}
    assert result['has_more'] is False
    assert find['execute']({'query':'Несуществующая организация'})['businesses']==[]
    read=next(tool for tool in tools if tool['name']=='settings.get_profile')
    assert read['execute']({'business':'Рога и копыта'})['profile']['business_id']=='b2'
    decisions=iter([
        {'action':'tool_call','tool':'settings.list_businesses','arguments':{'query':'Рога и копыта'}},
        {'action':'tool_call','tool':'settings.get_profile','arguments':{'business':'Рога и копыта'}},
        {'action':'final','message':'Настройки выбранного филиала прочитаны.'}])
    result,_=operator_core.route_operator_message(c,business_id='b2',user_id='u',channel=channel,
        message='Покажи настройки бизнеса Рога и копыта',tool_planner=lambda state:next(decisions))
    assert result['status']=='completed'


def test_name_search_respects_member_access_and_demo_scope(managed):
    _,c=managed
    c.execute("INSERT INTO users(id,email) VALUES ('reader','reader@example.ru')")
    c.execute("INSERT INTO business_members(id,business_id,user_id,role) VALUES ('read','b2','reader','viewer')")
    reader=load_actor(c,'reader')
    assert business_chat_changes.resolve_target(c,reader,'My journey Together','b2')=='b2'
    assert business_chat_changes.search_businesses(c,reader,'Весёлая')==[]
    owner=load_actor(c,'u')
    owner.update({'session_kind':'demo','scope_business_id':'b2'})
    assert business_chat_changes.search_businesses(c,owner,'Весёлая')==[]
    with pytest.raises(ValueError):business_chat_changes.resolve_target(c,owner,'b','b2')


def test_unselected_network_requires_location_selection(managed):
    _,c=managed
    c.execute("INSERT INTO networks(id,name,owner_id) VALUES ('n','Одинаковая сеть','u')")
    c.execute("UPDATE businesses SET network_id='n' WHERE id IN ('b2','b3')")
    with pytest.raises(ValueError,match='Уточните бизнес'):
        business_chat_changes.resolve_target(c,load_actor(c,'u'),'Одинаковая сеть','b')
