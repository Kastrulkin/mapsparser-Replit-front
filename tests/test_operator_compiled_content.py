import pytest
from flask import Flask, jsonify
from services import operator_compiled_content


@pytest.fixture
def actor(monkeypatch):
    value = {'user_id': 'owner', 'is_active': True, 'is_verified': True, 'session_kind': 'standard'}
    monkeypatch.setattr(operator_compiled_content, '_authorized_actor', lambda *args, **kwargs: value)
    monkeypatch.setattr(operator_compiled_content, '_load', lambda *args: (
        {'id': 'pilot', 'business_id': 'business'},
        {'id': 'v1', 'goal': 'Передавать готовые посты с фото', 'compiled_state': 'checking'}))
    return value


def test_compile_is_only_a_durable_proposal_until_human_confirmation(actor, monkeypatch):
    monkeypatch.setattr(operator_compiled_content, '_invoke', lambda *args: pytest.fail('Compile must wait for confirmation'))
    result = operator_compiled_content.prepare(None, business_id='business', user_id='owner',
        arguments={'operation': 'compile', 'blueprint_id': 'pilot'})
    assert result['status'] == 'approval_required'
    assert result['approval']['envelope']['payload']['expected_version_id'] == 'v1'
    assert not result['external_writes_performed']


def test_confirmed_compile_uses_same_common_operation_and_detects_changed_intent(actor, monkeypatch):
    calls = []
    monkeypatch.setattr(operator_compiled_content, '_invoke', lambda *args: calls.append(args) or (
        {'success': True, 'candidate_version': {'id': 'v2'}}, 201))
    result = operator_compiled_content.prepare(None, business_id='business', user_id='owner',
        arguments={'operation': 'compile', 'blueprint_id': 'pilot'})
    envelope = result['approval']['envelope']
    result = operator_compiled_content.execute(None, business_id='business', user_id='owner', envelope=envelope)
    assert result['version_id'] == 'v2'
    assert calls[0][0] == 'compile'
    envelope['payload']['description'] = 'Changed after preview'
    assert operator_compiled_content.execute(None, business_id='business', user_id='owner', envelope=envelope)['status'] == 'blocked'
    assert len(calls) == 1


def test_preview_uses_fresh_snapshot_and_never_approves_or_runs(actor, monkeypatch):
    calls = []
    def invoke(operation, *_args):
        calls.append(operation)
        if operation == 'snapshot':
            return {'snapshot': {'id': 'snapshot', 'input': {'posts': []}}}, 201
        return {'preview': {'status': 'passed'}}, 200
    monkeypatch.setattr(operator_compiled_content, '_invoke', invoke)
    result = operator_compiled_content.prepare(None, business_id='business', user_id='owner',
        arguments={'operation': 'preview', 'blueprint_id': 'pilot'})
    assert result['status'] == 'completed'
    assert calls == ['snapshot', 'preview']
    assert 'Подходящих постов' in result['chat_response']


def test_run_proposal_keeps_same_snapshot_and_idempotency_key(actor, monkeypatch):
    calls = []
    def invoke(operation, *_args):
        calls.append(operation)
        return {'snapshot': {'id': 'snapshot', 'input': {'posts': []}}}, 201
    monkeypatch.setattr(operator_compiled_content, '_invoke', invoke)
    result = operator_compiled_content.prepare(None, business_id='business', user_id='owner',
        arguments={'operation': 'run', 'blueprint_id': 'pilot'})
    assert calls == ['snapshot']
    assert result['status'] == 'approval_required'
    payload = result['approval']['envelope']['payload']
    assert payload['snapshot_id'] == 'snapshot'
    assert payload['idempotency_key'].endswith(':snapshot')


def test_stale_or_unauthorized_chat_never_calls_operations(actor, monkeypatch):
    monkeypatch.setattr(operator_compiled_content, '_invoke', lambda *args: pytest.fail('No operation allowed'))
    result = operator_compiled_content.prepare(None, business_id='business', user_id='owner',
        arguments={'operation': 'compile', 'blueprint_id': 'pilot', 'expected_version_id': 'old'})
    assert result['blocked_reasons'] == ['compiled_version_changed']
    monkeypatch.setattr(operator_compiled_content, '_authorized_actor', lambda *args, **kwargs: {})
    assert operator_compiled_content.prepare(None, business_id='business', user_id='owner',
        arguments={'operation': 'compile', 'blueprint_id': 'pilot'})['status'] == 'blocked'


def test_adapter_does_not_fake_an_http_authentication(monkeypatch):
    from api import agent_blueprints_api
    monkeypatch.setattr(agent_blueprints_api, '_require_auth', lambda: pytest.fail('No fake HTTP request'))
    calls = []
    monkeypatch.setattr(agent_blueprints_api, 'compiled_compile_for_actor', lambda *args: calls.append(args) or (jsonify({'success': True}), 201))
    assert operator_compiled_content._invoke('compile', 'pilot', {'user_id': 'owner'}, {}) == ({'success': True}, 201)
    assert calls[0][1]['user_id'] == 'owner'


@pytest.mark.parametrize('operation', ['snapshot', 'compile', 'preview', 'approve', 'run'])
def test_common_operations_reject_demo_before_database(monkeypatch, operation):
    from api import agent_blueprints_api
    monkeypatch.setattr(agent_blueprints_api, 'DatabaseManager', lambda: pytest.fail('Demo cannot touch DB'))
    with Flask(__name__).app_context():
        response, status = getattr(agent_blueprints_api, f'compiled_{operation}_for_actor')('pilot',
            {'user_id': 'owner', 'session_kind': 'demo'}, {})
    assert status == 403
    assert response.get_json()['code'] == 'COMPILED_SESSION_NOT_ALLOWED'
