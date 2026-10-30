import json
from unittest.mock import patch
import pytest
from flask import Flask
import ai_agents_api
import chats_api
from services.client_agent_scope import validate_selection


class Cursor:
    def __init__(self):
        self.rows = []
        self.inserted = None
    def execute(self, sql, args=()):
        compact = ' '.join(sql.lower().split())
        self.rows = []
        if 'select owner_id' in compact:
            self.rows = [{'owner_id': 'owner'}]
        elif 'from aiagents' in compact:
            scoped = 'business_id = %s' in compact
            if compact.startswith('select created_by') or compact.startswith('select id from'):
                self.rows = [{'id':args[0],'created_by':'owner'}] if not scoped or args == ('own','biz') else []
            elif scoped:
                self.rows = [{'id':'own','name':'Own persona','type':'booking','created_by':'owner'}]
            else:
                self.rows = [{'id':'foreign','name':'Other business persona','type':'booking','created_by':'owner'}]
        elif 'insert into aiagents' in compact:
            self.inserted = (compact,args)
    def fetchone(self):
        return self.rows[0] if self.rows else None
    def fetchall(self):
        return self.rows


class DB:
    def __init__(self):
        self.cursor_value=Cursor()
        self.conn=self
    def cursor(self): return self.cursor_value
    def close(self): pass
    def commit(self): pass


@pytest.fixture
def client():
    app=Flask(__name__);app.register_blueprint(ai_agents_api.ai_agents_api_bp);app.register_blueprint(chats_api.chats_bp)
    db=DB();actor={'user_id':'owner','is_superadmin':True}
    with patch('ai_agents_api.DatabaseManager',return_value=db),patch('chats_api.DatabaseManager',return_value=db),patch('ai_agents_api.require_auth',return_value=actor),patch('chats_api.require_auth',return_value=actor),patch('ai_agents_api._ensure_ai_agents_schema'),patch('ai_agents_api._ensure_business_automation_access',return_value=None),patch('chats_api._client_chat_access',return_value=True):
        yield app.test_client(),db


@pytest.mark.parametrize('suffix',['/ai-agents/manage','/ai-agents'])
def test_lists_only_business_owned_personas(client,suffix):
    http,_=client;r=http.get('/api/business/biz'+suffix)
    assert r.status_code==200
    assert [a['id'] for a in r.json['agents']]==['own']


@pytest.mark.parametrize('method',['put','delete'])
def test_foreign_mutations_rejected_even_for_superadmin(client,method):
    http,_=client;r=getattr(http,method)('/api/business/biz/ai-agents/manage/foreign',json={'name':'wrong'})
    assert r.status_code==404


def test_foreign_sandbox_rejected_before_model_call(client):
    http,_=client;r=http.post('/api/business/biz/ai-agents/foreign/test',json={'message':'hello'})
    assert r.status_code==404


def test_create_stores_business_ownership(client):
    http,db=client;r=http.post('/api/business/biz/ai-agents/manage',json={'name':'Own','type':'booking'})
    assert r.status_code==201
    assert 'created_by, business_id' in db.cursor_value.inserted[0]
    assert db.cursor_value.inserted[1][-1]=='biz'


def test_foreign_saved_binding_rejected_including_disabled_role():
    with pytest.raises(ValueError):
        validate_selection(Cursor(),'biz',{'ai_agents_config':json.dumps({'booking_agent':{'enabled':False,'agent_id':'foreign'}})})
    validate_selection(Cursor(),'biz',{'ai_agents_config':{'booking_agent':{'enabled':False,'agent_id':'own'}}})
