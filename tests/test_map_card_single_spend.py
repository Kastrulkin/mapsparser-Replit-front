import pytest
from services import ai_spend_budget
budget = ai_spend_budget


@pytest.mark.parametrize("visible", [True, False])
def test_map_run_is_single_call_across_router_scopes_and_restarts(monkeypatch, visible):
    rows=[]
    class Database:
        def __init__(self):self.conn=self;self.result=None;self.pending=None
        def cursor(self):return self
        def execute(self,sql,args=None):
            self.result=None
            if 'FROM agent_runs' in sql:self.result={'id':'run'} if visible else None
            if 'SELECT id FROM ai_spend_reservations' in sql:
                self.result={'id':'previous'} if any(row[6]==args[0] for row in rows) else None
            if 'INSERT INTO ai_spend_reservations' in sql:self.pending=args
        def fetchone(self):return self.result
        def commit(self):
            if self.pending:rows.append(self.pending)
        def rollback(self):pass
        def close(self):pass
    monkeypatch.setattr(budget,'_usage',lambda *_:{key:0 for key in budget.DEFAULT_LIMITS if key!='request_tokens'})
    context={'task_key':'agent_bounded_workflow_step','business_id':'meliora','operation_id':'durable-run'}
    body={'model':'GigaChat-2-Pro','max_tokens':3000,'parameters':{'max_tokens':4000},'messages':[{'role':'user','content':'Новый пакет оформления'}]}
    with budget.request_scope(operation_id='router-first', **({} if visible else {'map_card_run_id':'durable-run'})):
        budget.reserve(body,context,database_factory=Database)
    assert rows[0][6]=='map-card-run:durable-run'
    assert body['max_tokens']==body['parameters']['max_tokens']==3000
    for scope in ('schema-repair','network-retry','worker-restart'):
        with budget.request_scope(operation_id=scope, **({} if visible else {'map_card_run_id':'durable-run'})):
            with pytest.raises(budget.BudgetDenied,match='Автоматический повтор остановлен'):
                budget.reserve(body,context,database_factory=Database)
    assert len(rows)==1
    # A separately authorized new run is a distinct intent.
    with budget.request_scope(**({} if visible else {'map_card_run_id':'new-durable-run'})):
        budget.reserve(body,{**context,'operation_id':'new-durable-run'},database_factory=Database)
    assert len(rows)==2
    with budget.request_scope(map_card_run_id='oversized-new-run'):
        with pytest.raises(budget.BudgetDenied):
            budget.reserve({**body,'messages':[{'role':'user','content':'x'*16000}]},context,database_factory=Database)
    assert len(rows)==2


def test_trusted_scope_pins_uncommitted_map_run(monkeypatch):
    from services.map_card_ai_preparation import run_bounded_task
    from services.llm.contracts import LLMTaskRequest
    import services.llm.gateway
    seen=[]
    def fake(request):
        seen.append(budget._SCOPE.get().copy())
    monkeypatch.setattr(services.llm.gateway,'run_llm_task',fake)
    run_bounded_task(LLMTaskRequest(task_key='agent_bounded_workflow_step',prompt='test',usage_reference='not-committed-yet'),'maps_initial_setup')
    assert seen[0]['map_card_run_id']=='not-committed-yet'
    assert seen[0]['operation_id']=='map-card-run:not-committed-yet'
    assert not budget._SCOPE.get()


def test_map_sources_include_real_website_ahead_of_cached_context(monkeypatch):
    from services.map_card_ai_preparation import prepare_sources
    from services import map_card_agents
    reads=[]
    monkeypatch.setattr(map_card_agents,'collect',lambda *_,**kwargs:{'business':{'name':'Мелиора','website':'https://meliorabespoke.com/'},'services':[]})
    def read(*args):
        reads.append(args[-1]);return {'state':'observed','url':args[-1],'text':'Корпоративные подарки. Мерч и униформа. Фирменный стиль.'}
    monkeypatch.setattr(map_card_agents,'_read_page',read)
    run={'business_id':'business','created_by_user_id':'actor'}
    result=prepare_sources(None,run,'maps_initial_setup',{'sources':['old-profile']})
    assert reads==['https://meliorabespoke.com/']
    assert 'Корпоративные подарки' in result['map_card_evidence']['official_website']['text']
    assert 'sources' not in result
    reads.clear();prepare_sources(None,run,'maps_initial_setup',{},preview=True)
    assert reads==[]
