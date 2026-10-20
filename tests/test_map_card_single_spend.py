import pytest
from services import ai_spend_budget as budget


def test_map_run_is_single_call_across_router_scopes_and_restarts(monkeypatch):
    rows=[]
    class Database:
        def __init__(self):self.conn=self;self.result=None;self.pending=None
        def cursor(self):return self
        def execute(self,sql,args=None):
            self.result=None
            if 'FROM agent_runs' in sql:self.result={'id':'run'}
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
    with budget.request_scope(operation_id='router-first'):
        budget.reserve(body,context,database_factory=Database)
    assert rows[0][6]=='map-card-run:durable-run'
    assert body['max_tokens']==body['parameters']['max_tokens']==3000
    for scope in ('schema-repair','network-retry','worker-restart'):
        with budget.request_scope(operation_id=scope):
            with pytest.raises(budget.BudgetDenied,match='Автоматический повтор остановлен'):
                budget.reserve(body,context,database_factory=Database)
    assert len(rows)==1
    # A separately authorized new run is a distinct intent.
    budget.reserve(body,{**context,'operation_id':'new-durable-run'},database_factory=Database)
    assert len(rows)==2
