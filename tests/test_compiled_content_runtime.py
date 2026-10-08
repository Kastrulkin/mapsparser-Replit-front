from tests.test_compiled_runner_load import runner
from tests.test_compiled_content_program import version
from services.compiled_content_program import contract_for, manifest_for, validation_fixtures, validate_requests
from services.compiled_script_artifact import build_artifact
from services import compiled_script_runtime, compiled_script_artifact


def test_saved_content_program_runs_without_model_and_returns_only_references(runner, monkeypatch):
    module, _server = runner
    def forbid_model(*args, **kwargs):
        raise AssertionError('A saved program must not call AI at execution time')
    monkeypatch.setattr(compiled_script_artifact, 'run_llm_task', forbid_model)
    manifest = manifest_for(contract_for(version(),'b'), module.IMAGE_DIGEST)
    source = "def process(input_payload):\n    return {'requests': [{'post_id': p['post_id'], 'revision': p['revision']} for p in input_payload['posts'] if p['eligible']]}"
    artifact = build_artifact(source, manifest, validation_fixtures())
    payload = {'posts':[{'post_id':'ready','revision':'r1','eligible':True}, {'post_id':'draft','revision':'r2','eligible':False}]}
    result = compiled_script_runtime.execute_in_attested_sandbox(artifact,payload)
    assert validate_requests(result,payload) == [{'post_id':'ready','revision':'r1'}]
    assert result['runtime_ai_calls'] == 0
