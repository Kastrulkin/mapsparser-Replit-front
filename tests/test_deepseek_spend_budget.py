import pytest
from services import ai_spend_budget
from services.llm import adapters, gateway, LLMTaskRequest, LLMTaskResult
from services.llm.registry import get_task_definition


def test_deepseek_budget_denial_is_terminal_before_http(monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'synthetic')
    calls = []
    def denied(body, context):
        calls.append(context)
        raise ai_spend_budget.BudgetDenied('limit')
    monkeypatch.setattr(ai_spend_budget, 'reserve', denied)
    monkeypatch.setattr(adapters.requests, 'post', lambda *_args, **_kwargs: pytest.fail('No HTTP after spend refusal'))
    r = adapters.DeepSeekAdapter().generate(LLMTaskRequest(task_key='news_generation', prompt='x'), get_task_definition('news_generation'), prompt='x')
    assert r.status == 'budget_exceeded'
    assert r.fallback_reason == 'deepseek_budget_exceeded'
    assert len(calls) == 1 and calls[0]['provider'] == 'deepseek'


def test_each_physical_retry_reserves_separately(monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'synthetic')
    reserved = []; settled = []
    monkeypatch.setattr(ai_spend_budget, 'reserve', lambda *_: reserved.append('r') or 'r')
    monkeypatch.setattr(ai_spend_budget, 'settle', lambda *a: settled.append(a))
    monkeypatch.setattr(adapters.time, 'sleep', lambda *_: None)
    class Response:
        status_code = 503
    monkeypatch.setattr(adapters.requests, 'post', lambda *_args, **_kwargs: Response())
    adapters.DeepSeekAdapter().generate(LLMTaskRequest(task_key='news_generation', prompt='x'), get_task_definition('news_generation'), prompt='x')
    assert len(reserved) == 2
    assert all(item[1] == 'uncertain' for item in settled)


def test_provider_counters_are_separate_without_model_bypass():
    class Cursor:
        def execute(self, sql, params):
            self.params = params
            assert "WHERE provider=%s" in sql
        def fetchone(self): return {'usage': {'daily_tokens': 123}}
    cursor = Cursor()
    assert ai_spend_budget._usage(cursor, 'day', 'month', 'operation', 'deepseek')['daily_tokens'] == 123
    assert cursor.params[-2] == 'deepseek'
    assert ai_spend_budget.limits('deepseek')['daily_tokens'] == 300000
    assert ai_spend_budget.limits()['daily_tokens'] == 100000
    assert pytest.raises(ai_spend_budget.BudgetDenied, ai_spend_budget.limits, 'unbudgeted')


def test_nested_command_scopes_reuse_one_operation_but_new_command_is_independent():
    values = []
    @ai_spend_budget.spend_operation
    def inner(): values.append(ai_spend_budget._SCOPE.get()['operation_id'])
    @ai_spend_budget.spend_operation
    def command():
        inner(); inner()
    command(); command()
    assert values[0] == values[1]
    assert values[2] == values[3]
    assert values[0] != values[2]


def test_deepseek_refusal_never_triggers_fallback_or_shadow(monkeypatch):
    calls = []
    monkeypatch.setattr(gateway, '_provider_for_request', lambda *_: 'deepseek')
    def generate(*_, **kwargs):
        calls.append(kwargs['provider'])
        return LLMTaskResult(status='budget_exceeded', provider='deepseek', fallback_reason='deepseek_budget_exceeded')
    monkeypatch.setattr(gateway, '_generate_once', generate)
    monkeypatch.setattr(gateway, '_record_result', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(gateway, 'run_llm_shadow_task', lambda *_: pytest.fail('No shadow after refusal'))
    r = gateway.run_llm_task(LLMTaskRequest(task_key='operator_tool_plan', prompt='x'))
    assert calls == ['deepseek'] and r.fallback_reason == 'deepseek_budget_exceeded'
