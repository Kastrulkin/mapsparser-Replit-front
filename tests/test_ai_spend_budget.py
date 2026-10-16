import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import pytest
from services import ai_spend_budget
budget = ai_spend_budget


def body():
    return {'model': 'GigaChat-2-Pro', 'max_tokens': 100, 'messages': [{'role': 'user', 'content': 'Проверка'}]}


def used():
    return {key: 0 for key in ('daily_tokens','monthly_tokens','operation_tokens','daily_calls','monthly_calls','operation_calls')}


@pytest.mark.parametrize('key', ['daily_tokens','monthly_tokens','operation_tokens','daily_calls','monthly_calls','operation_calls'])
def test_limits_block_before_provider(key):
    values = used();values[key] = budget.DEFAULT_LIMITS[key]
    with pytest.raises(budget.BudgetDenied):
        budget._check(values, budget.DEFAULT_LIMITS, 100)


def test_moscow_window_and_safe_text_reservation():
    day, month = budget.windows(datetime(2026,10,15,22,30,tzinfo=timezone.utc))
    assert day.day == 16
    assert day.hour == 0
    assert month.day == 1
    assert budget.reservation_tokens(body()) > len('Проверка'.encode()) + 100
    with pytest.raises(budget.BudgetDenied):
        budget.reservation_tokens({**body(), 'messages': [{'attachments': ['file']}]})


def test_unavailable_ledger_fails_closed():
    def unavailable(): raise OSError('private database detail')
    error = pytest.raises(budget.BudgetDenied, budget.reserve, body(), database_factory=unavailable)
    assert 'private' not in str(error.value)


def test_transport_uncertainty_retains_reservation(monkeypatch):
    calls=[]
    monkeypatch.setattr(budget,'reserve',lambda *_:'reservation')
    monkeypatch.setattr(budget,'settle',lambda *a,**k:calls.append(a))
    def timeout(): raise TimeoutError()
    with pytest.raises(TimeoutError):budget.guarded_post(timeout,body())
    assert calls[0][1] == 'uncertain'


def test_actual_usage_settles_and_missing_usage_remains_held(monkeypatch):
    calls=[]
    monkeypatch.setattr(budget,'reserve',lambda *_:'reservation')
    monkeypatch.setattr(budget,'settle',lambda *a,**k:calls.append(a))
    class Response:
        status_code=200
        def json(self):return {'usage':{'total_tokens':45}}
    budget.guarded_post(Response,body())
    assert calls[-1][1:3] == ('completed',45)
    Response.json=lambda _:{}
    budget.guarded_post(Response,body())
    assert calls[-1][1] == 'uncertain'


def test_atomic_reservations_allow_only_one_concurrent_call(monkeypatch):
    mutex=threading.Lock();rows=[]
    class Database:
        def __init__(self):self.conn=self;self.locked=False;self.pending=None
        def cursor(self):return self
        def execute(self,sql,params=None):
            if 'pg_advisory_xact_lock' in sql:mutex.acquire();self.locked=True
            elif 'INSERT INTO ai_spend_reservations' in sql:self.pending=params
        def commit(self):
            if self.pending:rows.append(self.pending)
            if self.locked:self.locked=False;mutex.release()
        def rollback(self):
            if self.locked:self.locked=False;mutex.release()
        def close(self):self.rollback()
    def usage(*_):return {**used(),'daily_calls':len(rows)}
    monkeypatch.setattr(budget,'_usage',usage)
    monkeypatch.setattr(budget,'limits',lambda:{**budget.DEFAULT_LIMITS,'daily_calls':1})
    def request(_):
        try:return budget.reserve(body(),database_factory=Database)
        except budget.BudgetDenied:return None
    pool = ThreadPoolExecutor(max_workers=8)
    try:results=list(pool.map(request,range(8)))
    finally:pool.shutdown()
    assert len([x for x in results if x]) == len(rows) == 1


def test_client_does_not_retry_or_call_http_when_budget_denied(monkeypatch):
    from services.gigachat_client import GigaChatClient,GigaChatProviderError
    def denied(*_):raise budget.BudgetDenied('limit')
    monkeypatch.setattr(budget,'reserve',denied)
    def forbidden(*_,**__):pytest.fail('Provider must not be called')
    monkeypatch.setattr('services.gigachat_client.requests.post',forbidden)
    client=object.__new__(GigaChatClient);client.verify_tls=True
    error = pytest.raises(GigaChatProviderError, client._post_with_retry,
        'https://api.giga.chat/v1/chat/completions',{},body())
    assert error.value.code == 'gigachat_budget_exceeded'
    assert error.value.retryable is False
