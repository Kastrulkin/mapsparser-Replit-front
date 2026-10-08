import pytest
from services.compiled_content_program import contract_for, manifest_for, validate_requests, program_allowed
from services.compiled_script_artifact import build_artifact, validate_artifact
from services.content_delivery_status import delivery_status


def version():
    return {'execution_mode': 'scheduled', 'trigger': 'schedule.daily',
        'schedule_json': {'time': '10:00', 'timezone': 'Europe/Moscow'},
        'steps_json': [{'capability': 'content.publish_handoff', 'payload': {
            'business_id': 'b', 'recipient_user_id': 'owner', 'platforms': ['telegram','vk','max'],
            'time': '10:00', 'timezone': 'Europe/Moscow', 'lead_days': 1}}]}


def test_pure_artifact_uses_no_network_or_runtime_model():
    manifest = manifest_for(contract_for(version(), 'b'), 'sha256:'+'1'*64)
    source = "def process(input_payload):\n    return {'requests': []}"
    artifact = build_artifact(source, manifest, [{'source':'user','input':{'posts':[]},'expected':{'requests':[]}}])
    assert validate_artifact(artifact)['valid']
    assert artifact['external_effects'] is False and artifact['runtime_ai'] is False
    artifact['manifest']['content_handoff_contract']['scope']['recipient_user_id']='other'
    assert not validate_artifact(artifact)['valid']


@pytest.mark.parametrize('requests', [None, ['id'], [{'post_id':'other','revision':'r1'}],
    [{'post_id':'draft','revision':'r2'}], [{'post_id':'p','revision':'old'}],
    [{'post_id':'p','revision':'r1','recipient':'other'}],
    [{'post_id':'p','revision':'r1'},{'post_id':'p','revision':'r1'}]])
def test_broker_rejects_out_of_scope_changed_incomplete_and_duplicate_requests(requests):
    with pytest.raises(ValueError):
        validate_requests({'requests': requests}, {'posts':[
            {'post_id':'p','revision':'r1','eligible':True},
            {'post_id':'draft','revision':'r2','eligible':False}]})


def test_broker_accepts_only_immutable_eligible_references():
    expected=[{'post_id':'p','revision':'r1'}]
    assert validate_requests({'requests':expected},{'posts':[{'post_id':'p','revision':'r1','eligible':True}]}) == expected


def test_pilot_requires_both_business_and_automation_allowlists(monkeypatch):
    monkeypatch.setenv('COMPILED_SCRIPT_EXECUTE_ENABLED','true')
    monkeypatch.setenv('COMPILED_SCRIPT_PILOT_BUSINESS_IDS','b')
    monkeypatch.setenv('COMPILED_CONTENT_HANDOFF_BLUEPRINT_IDS','pilot')
    assert program_allowed('b','pilot')
    assert not program_allowed('b','other')
    assert not program_allowed('other','pilot')


@pytest.mark.parametrize('receipt,expected', [
    ({},'not_sent'),
    ({'parts':{'photo':{'status':'sent'}}},'partially_delivered'),
    ({'parts':{'photo':{'status':'sent'},'text':{'status':'not_sent'}}},'partially_delivered'),
    ({'parts':{'photo':{'status':'uncertain'}}},'needs_reconciliation'),
    ({'parts':{'photo':{'status':'not_sent'}}},'failed'),
    ({'sent_at':'2026-10-08','parts':{'photo':{'status':'sent'}}},'delivered')])
def test_delivery_projection_does_not_confuse_partial_with_success(receipt,expected):
    assert delivery_status({'staff_handoff':{'telegram_deliveries':{'owner':receipt}}}) == expected


def test_chat_prepares_same_blueprint_not_legacy_preferences(monkeypatch):
    from services import operator_agent_management, operator_content_handoffs
    calls = []
    monkeypatch.setattr(operator_agent_management, 'configure', lambda *args, **kwargs: calls.append(kwargs) or {'status':'approval_required'})
    result = operator_content_handoffs.operator_task(object(), business_id='b', user_id='owner',
        arguments={'operation':'configure','settings':{'time':'10:00','lead_days':1,'platforms':['telegram','vk','max']}})
    assert result['status'] == 'approval_required'
    assert calls[0]['arguments']['operation'] == 'create'
    assert calls[0]['business_id'] == 'b'
    assert 'на паузе' in calls[0]['arguments']['description']


def test_chat_never_substitutes_irina_for_test_recipient():
    from services.operator_content_handoffs import operator_task
    result = operator_task(object(), business_id='b', user_id='owner',
        arguments={'operation':'configure','recipient_user_id':'irina'})
    assert result['status'] == 'clarification_required'
