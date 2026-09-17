"""Isolated schemas in a local disposable PostgreSQL test database only."""
import importlib.util
import os
import uuid
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
import pytest
from services import content_rules


@pytest.fixture
def pg(monkeypatch):
    dsn=os.getenv('OPERATOR_VOICE_TEST_DSN')
    if not dsn: pytest.skip('Disposable PostgreSQL required')
    conn=psycopg2.connect(dsn,cursor_factory=RealDictCursor);cursor=conn.cursor();schema='rules_'+uuid.uuid4().hex
    cursor.execute('CREATE SCHEMA '+schema);cursor.execute('SET search_path TO '+schema)
    cursor.execute('CREATE TABLE users(id TEXT PRIMARY KEY)');cursor.execute("INSERT INTO users VALUES ('owner'),('manager'),('employee')")
    cursor.execute('CREATE TABLE businesses(id TEXT PRIMARY KEY,network_id TEXT)');cursor.execute("INSERT INTO businesses VALUES ('b','n'),('other','other')")
    cursor.execute('CREATE TABLE networks(id TEXT,owner_id TEXT)')
    cursor.execute('CREATE TABLE business_members(business_id TEXT,user_id TEXT,status TEXT,role TEXT)')
    cursor.execute("INSERT INTO business_members VALUES ('b','manager','active','manager'),('b','employee','active','employee')")
    cursor.execute('CREATE TABLE network_members(network_id TEXT,user_id TEXT,status TEXT,role TEXT)')
    cursor.execute('''CREATE TABLE content_voice_profiles(business_id TEXT PRIMARY KEY,preferences_json JSONB,status TEXT,created_by TEXT,version INT DEFAULT 1,updated_at TIMESTAMPTZ DEFAULT NOW())''')
    from alembic import op
    monkeypatch.setattr(op,'execute',cursor.execute)
    spec=importlib.util.spec_from_file_location('rules_migration',Path(__file__).parents[1]/'alembic_migrations/versions/20260917_content_rules.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.upgrade();module.upgrade()
    monkeypatch.setattr(content_rules,'authorize_actor',lambda cursor,user,business,**kw:({'role':'business_owner' if user=='owner' else 'business_user'},{}))
    yield cursor
    conn.rollback();conn.close()


def save(cursor,**kwargs):
    return content_rules.change(cursor,business_id='b',user_id='owner',request_id='r',text='Не обещать любые мультфильмы',**kwargs)


def test_idempotency_and_history(pg):
    first=save(pg);assert save(pg)==first
    pg.execute('SELECT count(*) n FROM content_rule_history');assert pg.fetchone()['n']==1
    assert len(content_rules.active_rules(pg,'b'))==1


def test_duplicate_id_with_different_text_rejected(pg):
    save(pg)
    with pytest.raises(content_rules.RuleConflict):
        content_rules.change(pg,business_id='b',user_id='owner',request_id='r',text='Другое')


def test_stale_change_preserves_current(pg):
    rule=save(pg)
    updated=content_rules.change(pg,business_id='b',user_id='owner',request_id='r2',text='Новое',rule_id=rule['id'],expected_version=1)
    with pytest.raises(content_rules.RuleConflict):
        content_rules.change(pg,business_id='b',user_id='owner',request_id='r3',text='Затереть',rule_id=rule['id'],expected_version=1)
    assert content_rules.active_rules(pg,'b')[0]==updated


def test_cancel_preserves_history(pg):
    rule=save(pg)
    content_rules.change(pg,business_id='b',user_id='owner',request_id='r2',rule_id=rule['id'],expected_version=1,status='cancelled')
    assert not content_rules.active_rules(pg,'b')
    pg.execute('SELECT count(*) n FROM content_rule_history');assert pg.fetchone()['n']==2


def test_manager_and_employee_permissions(pg):
    assert content_rules.can_manage(pg,'manager','b')
    assert not content_rules.can_manage(pg,'employee','b')
    assert not content_rules.can_manage(pg,'manager','other')
    with pytest.raises(PermissionError):
        content_rules.change(pg,business_id='b',user_id='employee',request_id='r',text='Запрет')
    pg.execute("UPDATE business_members SET status='revoked' WHERE user_id='manager'")
    assert not content_rules.can_manage(pg,'manager','b')


def test_network_manager_permissions(pg):
    pg.execute("DELETE FROM business_members WHERE user_id='manager'")
    pg.execute("INSERT INTO network_members VALUES ('n','manager','active','manager')")
    assert content_rules.can_manage(pg,'manager','b')
    assert not content_rules.can_manage(pg,'manager','other')


@pytest.mark.parametrize('dates',[{'starts_at':'2099-01-01T00:00:00+00:00'},{'ends_at':'2000-01-01T00:00:00+00:00'}])
def test_inactive_periods(pg,dates):
    save(pg,**dates);assert not content_rules.active_rules(pg,'b')


def test_other_profile_preferences_preserved(pg):
    pg.execute("INSERT INTO content_voice_profiles(business_id,preferences_json) VALUES ('b','{\"tone_instruction\":\"Тепло\"}')")
    save(pg);assert content_rules.load(pg,'b')['tone_instruction']=='Тепло'


def test_foreign_rule_cannot_be_modified(pg):
    rule=save(pg)
    with pytest.raises(content_rules.RuleConflict):
        content_rules.change(pg,business_id='other',user_id='owner',request_id='foreign',text='Перезаписать чужое',rule_id=rule['id'],expected_version=1)
    assert content_rules.active_rules(pg,'b')[0]==rule
