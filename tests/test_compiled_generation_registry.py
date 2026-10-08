from services import compiled_script_artifact
from services.llm.contracts import LLMTaskResult
from services.llm.registry import get_task_definition


def test_compiler_is_registered_for_json_and_compile_time_only():
    definition = get_task_definition('compiled_script_generation')
    assert definition.primary_provider == 'deepseek'
    assert definition.response_kind == 'json'
    assert definition.response_schema['required'] == ['source', 'manifest', 'fixtures']
    assert not definition.shadow_allowed


def test_compiler_preserves_gateway_failure_without_parse_error(monkeypatch):
    monkeypatch.setattr(compiled_script_artifact, 'run_llm_task', lambda request:
        LLMTaskResult(status='task_blocked', fallback_reason='LLM_TASK_NOT_REGISTERED'))
    result = compiled_script_artifact.generate_candidate_from_description('Compile', business_id='b', user_id='u')
    assert result == {'status': 'generation_failed', 'error': 'LLM_TASK_NOT_REGISTERED'}


def test_compiler_uses_gateway_validated_json_instead_of_markdown(monkeypatch):
    candidate = {'source': 'def process(input_payload):\n    return {}', 'manifest': {}, 'fixtures': []}
    monkeypatch.setattr(compiled_script_artifact, 'run_llm_task', lambda request:
        LLMTaskResult(status='completed', content='```json\nnot directly parseable\n```', parsed_data=candidate))
    monkeypatch.setattr(compiled_script_artifact, 'validate_candidate', lambda *args: {'valid': True, 'source': args[0]})
    result = compiled_script_artifact.generate_candidate_from_description('Compile', business_id='b', user_id='u')
    assert result['status'] == 'ready'
    assert result['candidate']['source'] == candidate['source']
