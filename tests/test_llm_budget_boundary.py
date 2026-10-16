import pytest
from services.llm import gateway, LLMTaskRequest, LLMTaskResult


@pytest.mark.parametrize('task', ['news_generation', 'service_catalog_analysis'])
def test_exhausted_budget_never_falls_back_or_runs_paid_shadow(monkeypatch, task):
    monkeypatch.setenv('LLM_ROUTER_ENABLED', 'true')
    monkeypatch.setenv('LLM_SHADOW_MODE', 'true')
    monkeypatch.setenv('LLM_DEEPSEEK_BUSINESS_IDS', 'business')
    monkeypatch.setattr(gateway, '_provider_for_request', lambda *_: 'gigachat')
    calls = []
    def generate(*_, **kwargs):
        calls.append(kwargs['provider'])
        return LLMTaskResult(status='provider_terminal_error', provider='gigachat', fallback_reason='gigachat_budget_exceeded')
    monkeypatch.setattr(gateway, '_generate_once', generate)
    monkeypatch.setattr(gateway, '_record_result', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(gateway, 'run_llm_shadow_task', lambda *_: pytest.fail('Budget refusal must not start paid shadow'))
    result = gateway.run_llm_task(LLMTaskRequest(task_key=task, prompt='test', business_id='business'))
    assert result.fallback_reason == 'gigachat_budget_exceeded'
    assert calls == ['gigachat']
