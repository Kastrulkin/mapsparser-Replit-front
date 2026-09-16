import json
from services.llm import gateway, LLMTaskRequest, LLMTaskResult
from services.llm.registry import get_task_definition


def test_repair_contains_original_response_and_task_schema():
    request = LLMTaskRequest(task_key='operator_tool_plan', prompt='Измени этот пост: комиссия в три раза меньше')
    result = LLMTaskResult(status='schema_invalid', content='{"tool":"content.edit_item","arguments":{"brief":"меньше посредников"}}', validation_errors=['$.action: required'])
    prompt = gateway._recovery_prompt(request, get_task_definition(request.task_key), result)
    payload = json.loads(prompt.splitlines()[-1])
    assert payload['previous_response'] == result.content
    assert payload['response_schema']['required'] == ['action']
    assert request.prompt in prompt


def test_empty_result_retries_task_instead_of_asking_to_repair_missing_answer():
    request = LLMTaskRequest(task_key='operator_tool_plan', prompt='Измени пост')
    prompt = gateway._recovery_prompt(request, get_task_definition(request.task_key), LLMTaskResult(status='empty_response'))
    assert 'Выполни исходное задание заново' in prompt
    assert 'Исправь только формат' not in prompt


def test_internal_repair_response_is_failure_after_single_retry(monkeypatch):
    calls = []
    def generate(*args, **kwargs):
        calls.append(kwargs['prompt'])
        return LLMTaskResult(status='completed', provider='deepseek', content=json.dumps({'action':'final','message':'Не вижу исходного ответа, который нужно исправить: отсутствует поле $.action'}, ensure_ascii=False))
    monkeypatch.setenv('OPERATOR_DEEPSEEK_ROUTER_ENABLED', 'true')
    monkeypatch.setenv('LLM_SHADOW_MODE', 'false')
    monkeypatch.setattr(gateway, '_generate_once', generate)
    monkeypatch.setattr(gateway, '_record_llm_usage', lambda *a, **kw: None)
    result = gateway.run_llm_task(LLMTaskRequest(task_key='operator_tool_plan', prompt='Измени этот пост'))
    assert len(calls) == 2
    assert result.status == 'fallback_required'
    assert result.fallback_reason == 'LLM_SCHEMA_RETRY_EXHAUSTED'


def test_recovery_error_releases_credit_without_executing_tools(monkeypatch):
    from services import operator_tool_billing
    monkeypatch.setenv('OPERATOR_DEEPSEEK_ROUTER_ENABLED', 'true')
    monkeypatch.setenv('LLM_SHADOW_MODE', 'false')
    monkeypatch.setattr(gateway, '_generate_once', lambda *a, **kw: LLMTaskResult(status='completed', provider='deepseek', content='{"action":"final","message":"Пришлите ответ с ошибкой схемы $.action"}'))
    monkeypatch.setattr(gateway, '_record_llm_usage', lambda *a, **kw: None)
    monkeypatch.setattr(operator_tool_billing, 'build_paid_action_preflight', lambda *a, **kw: {'status':'ready'})
    monkeypatch.setattr(operator_tool_billing, 'reserve_paid_action_credits', lambda *a, **kw: {'status':'reserved','reservation_id':'test'})
    finalizations = []
    def finalize(*a, **kw):
        finalizations.append(kw)
        return {'status':'released','charge_credits':0}
    monkeypatch.setattr(operator_tool_billing, 'finalize_reserved_action_credits', finalize)
    result = operator_tool_billing.run_paid_operator_tool_loop(object(), business_id='test', user_id='test', message='Измени этот пост', tools=[])
    assert result['status'] == 'blocked'
    assert result['planner_failed'] is True
    assert result['credit_charged'] is False
    assert result['tool_calls'] == 0
    assert finalizations[0]['finalization_mode'] == 'release'
    assert '$.action' not in result['chat_response']
