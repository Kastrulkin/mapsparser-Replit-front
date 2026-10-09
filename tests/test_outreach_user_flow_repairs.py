from flask import Flask
import pytest
from api import outreach_campaign_api as messages
from api import partnership_leads_api as continuations
from api.prospecting import access_schema
from services import outreach_continuation, partnership_leads_service, operator_conversations
from services import outreach_web_search, operator_search_demand
from services.agent_blueprint_draft_builder import requires_native_outreach
from services.agent_blueprint_workspace import _render_output

class Cursor:
    def __init__(self, group=True, leads=None):
        self.group = group
        self.leads = ['lead1','lead2'] if leads is None else leads
        self.calls = []
    def execute(self, sql, params=None):
        self.calls.append((sql, params))
    def fetchone(self):
        return {'id':'task', 'result_json':{'lead_ids':self.leads}, 'payload_json':{}} if self.group else None
    def fetchall(self):
        return [{'touch_id':'touch','delivery_status':'sent','provider_message_id':'proof'}]

class Connection:
    def __init__(self, cursor): self.cur=cursor
    def cursor(self, **kwargs): return self.cur
    def commit(self): pass
    def rollback(self): pass
    def close(self): pass

@pytest.fixture
def app():
    app=Flask(__name__)
    app.register_blueprint(messages.outreach_campaign_bp)
    app.register_blueprint(continuations.partnership_leads_bp)
    return app

@pytest.fixture
def auth(monkeypatch):
    user={'user_id':'user','is_superadmin':True}
    monkeypatch.setattr(messages,'_require_auth',lambda:(user,None))
    monkeypatch.setattr(access_schema,'_require_auth',lambda:(user,None))
    monkeypatch.setattr(messages,'_resolve_business_for_user',lambda *args:'biz')
    monkeypatch.setattr(access_schema,'_resolve_business_for_user',lambda *args:'biz')

@pytest.mark.parametrize('leads', [['lead1','lead2'], []])
def test_group_filter_applied_before_pagination_and_summary(app,auth,monkeypatch,leads):
    cur=Cursor(leads=leads)
    monkeypatch.setattr(messages,'get_db_connection',lambda:Connection(cur))
    result=app.test_client().get('/api/outreach/messages?business_id=biz&search_task_id=task&limit=1')
    assert result.status_code==200
    query,params=cur.calls[-1]
    assert 'ranked.lead_id::text = ANY(%s::text[])' in query
    assert params[-1]==leads
    assert 'WHERE' in query and query.index('ranked.lead_id::text = ANY') < query.index('LIMIT 5000')
    assert cur.calls[0][1]==('task','biz')
    assert result.json['summary']['sent']==1


def test_missing_or_other_business_group_never_falls_back_to_all_messages(app,auth,monkeypatch):
    cur=Cursor(group=False)
    monkeypatch.setattr(messages,'get_db_connection',lambda:Connection(cur))
    result=app.test_client().get('/api/outreach/messages?business_id=biz&search_task_id=foreign')
    assert result.status_code==404
    assert len(cur.calls)==1


def test_blocked_preview_returns_reason_without_creating_approval(app,auth,monkeypatch):
    import pg_db_utils
    cur=Cursor()
    monkeypatch.setattr(pg_db_utils,'get_db_connection',lambda:Connection(cur))
    monkeypatch.setattr(outreach_continuation,'continuation_enabled',lambda *a:True)
    monkeypatch.setattr(outreach_continuation,'actor_can_write',lambda *a:True)
    monkeypatch.setattr(partnership_leads_service,'_partnership_write_access',lambda *a:None)
    blocked={'status':'blocked','approval':None,'reason_code':'web_search_not_configured','chat_response':'Веб-поиск не подключён'}
    monkeypatch.setattr(outreach_continuation,'prepare_new_task_approval',lambda *a,**k:blocked)
    monkeypatch.setattr(operator_conversations,'create_pending_operator_action',lambda **k:pytest.fail('Must not create approval'))
    monkeypatch.setattr(operator_conversations,'find_latest_operator_conversation',lambda *a,**k:pytest.fail('Must not create conversation'))
    result=app.test_client().post('/api/partnership/continuations',json={'business_id':'biz','operation':'preview','config':{}})
    assert result.status_code==200
    assert result.json==blocked
    assert cur.calls==[]


def test_search_connection_check_is_not_wordstat(monkeypatch):
    command='Проверь готовность веб-поиска для аутрича: какие поисковые API подключены. Без поисковых запросов.'
    assert not operator_search_demand.matches(command)
    assert outreach_web_search.readiness_request(command)
    assert operator_search_demand.matches('Покажи поисковые запросы Wordstat')
    assert operator_search_demand.matches('Покажи поисковые запросы для SEO услуг')
    monkeypatch.setattr(outreach_web_search,'_providers',lambda:[])
    monkeypatch.setattr(outreach_web_search.requests,'get',lambda *a,**k:pytest.fail('No external call'))
    result=outreach_web_search.readiness()
    assert result['reason_code']=='web_search_not_configured'
    assert result['quota_status']=='unknown'
    assert result['external_calls_performed'] is False


def test_generic_profile_result_cannot_claim_to_perform_outreach():
    goal='Проверить сведения и контакты с источниками, подготовить три индивидуальных английских письма для компаний.'
    assert requires_native_outreach(goal,'partnerships')
    with pytest.raises(ValueError,match='согласованные условия'):
        _render_output('partnerships',{'workflow_description':goal},[{'summary':'profile only'}],[])
    assert not requires_native_outreach('Прочитай профиль и подготовь внутреннюю сводку','custom')
