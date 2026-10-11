from copy import deepcopy
from datetime import date, datetime, timezone
from types import SimpleNamespace
import pytest

from services.compiled_content_handoff import handoff_targets, scope_digest, has_active_consent
from services.compiled_content_program import contract_for, manifest_for, validate_requests, request_identity
from services.content_network_renewal import successor_dates, last_packet_complete, service_changes
from services.content_publish_notifications import handoff_revision


def version():
    return {'execution_mode': 'scheduled', 'trigger': 'schedule.daily',
            'schedule_json': {'time': '10:00', 'timezone': 'Europe/Moscow'},
            'steps_json': [{'capability': 'content.publish_handoff', 'payload': {
                'business_id': 'a', 'business_ids': ['a', 'b'], 'recipient_user_ids': ['alex', 'irina'],
                'plan_ids': {'a': ['plan-a'], 'b': ['plan-b']}, 'platforms': ['telegram', 'vk', 'max'],
                'time': '10:00', 'timezone': 'Europe/Moscow', 'lead_days': 1,
                'renewal': {'period_days': 30, 'reviewer_user_id': 'alex'}}}]}


def test_two_branches_two_recipients_static_and_no_runtime_model():
    contract = contract_for(version(), 'a')
    assert contract['version'] == 2
    targets = handoff_targets(contract['scope'])
    assert {(t['business_id'], t['recipient_user_id']) for t in targets} == {
        ('a', 'alex'), ('a', 'irina'), ('b', 'alex'), ('b', 'irina')}
    manifest = manifest_for(contract, 'sha256:'+'1'*64)
    assert manifest['uses_model'] is False and manifest['external_effects'] is False
    ids = [request_identity(t, 'post') for t in targets]
    assert len(set(ids)) == 4
    with pytest.raises(ValueError):
        validate_requests({'requests': [{'post_id': 'other:alex:post', 'revision': 'r'}]},
                          {'posts': [{'post_id': identity, 'revision': 'r', 'eligible': True} for identity in ids]})


@pytest.mark.parametrize('key,value', [('business_ids', ['a', 'a']), ('recipient_user_ids', []),
    ('plan_ids', {'a': ['plan-a']}), ('renewal', {'period_days': 60, 'reviewer_user_id': 'alex'})])
def test_ambiguous_or_unbounded_scope_is_rejected(key, value):
    v = version()
    v['steps_json'][0]['payload'][key] = value
    with pytest.raises(ValueError):
        contract_for(v, 'a')


def test_consent_changes_with_branch_recipient_plan_or_renewal():
    scope = contract_for(version(), 'a')['scope']
    consent = {'version_id': 'v', 'scope': scope, 'scope_digest': scope_digest(version_id='v', scope=scope)}
    assert has_active_consent({'compiled_content_handoff_consent': consent}, version_id='v', scope=scope)
    changed = deepcopy(scope)
    changed['recipient_user_ids'] = ['alex']
    assert not has_active_consent({'compiled_content_handoff_consent': consent}, version_id='v', scope=changed)


def test_cadence_uses_shifted_actual_dates_and_never_past():
    start, end, dates = successor_dates(['2026-10-11', '2026-10-14', '2026-10-17'], today=date(2026,10,18))
    assert start == date(2026,10,20) and end == date(2026,11,18)
    assert dates[1] == '2026-10-23' and len(dates) == 10
    start, _, _ = successor_dates(['2026-09-01', '2026-09-04'], today=date(2026,10,11))
    assert start > date(2026,10,11)


def test_service_changes_compare_prices_without_updated_at_noise():
    previous = [{'id':'same','name':'Стрижка','price':500,'updated_at':'old'}, {'id':'removed','name':'Old'}]
    current = [{'id':'same','name':'Стрижка','price':600,'updated_at':'new'}, {'id':'new','name':'New'}]
    changes = service_changes(current,previous)
    assert changes['changed'][0]['before']['price'] == 500
    assert changes['changed'][0]['after']['price'] == 600
    assert changes['added'][0]['id'] == 'new' and changes['removed'][0]['id'] == 'removed'
    assert not service_changes([{'id':'a','name':'A','updated_at':'new'}], [{'id':'a','name':'A','updated_at':'old'}])['changed']


def test_schedule_allowlist_does_not_even_evaluate_other_automations(monkeypatch):
    from services import agent_trigger_runtime
    monkeypatch.setenv('AGENT_SCHEDULE_BLUEPRINT_IDS','our-pilot')
    monkeypatch.setattr(agent_trigger_runtime,'_load_scheduled_blueprints',lambda *args,**kwargs: [{'id':'riderra-1'},{'id':'riderra-2'}])
    def forbidden(*args,**kwargs):
        raise AssertionError('Another automation must not be evaluated or changed')
    monkeypatch.setattr(agent_trigger_runtime,'evaluate_agent_canary_budget',forbidden)
    result = agent_trigger_runtime.dispatch_due_scheduled_agent_blueprints(object())
    assert result['dispatched_count'] == 0
    assert len(result['skipped']) == 2
    assert all(row['reason'] == 'outside_schedule_allowlist' for row in result['skipped'])


def test_creation_approval_keeps_network_scope_and_hashes_changes(monkeypatch):
    from services import agent_blueprint_creation, agent_builder_billing
    monkeypatch.setattr(agent_blueprint_creation, 'preview_creation', lambda *args, **kwargs: {'status': 'ready'})
    monkeypatch.setattr(agent_builder_billing, 'build_paid_action_preflight', lambda *args, **kwargs: {'status': 'ready'})
    payload = {'name': 'Content', 'description': 'Network content', 'content_handoff_scope': {'business_ids': ['a', 'b'], 'recipient_user_ids': ['owner', 'manager']}}
    first = agent_blueprint_creation.prepare_creation(None, business_id='a', user_id='owner', actor_context={}, payload=payload)['approval']['envelope']
    assert first['payload']['content_handoff_scope'] == payload['content_handoff_scope']
    payload['content_handoff_scope'] = {**payload['content_handoff_scope'], 'recipient_user_ids': ['owner']}
    second = agent_blueprint_creation.prepare_creation(None, business_id='a', user_id='owner', actor_context={}, payload=payload)['approval']['envelope']
    assert first['idempotency_key'] != second['idempotency_key']


@pytest.mark.parametrize('uncertain', [False, True])
def test_network_dispatch_preserves_success_and_continues_other_recipient(monkeypatch, uncertain):
    from services import compiled_content_program, agent_capability_handlers
    import database_manager
    contract = contract_for(version(), 'a')
    contract['scope'].pop('renewal')
    targets = handoff_targets(contract['scope'])
    connection = SimpleNamespace(cursor=lambda: object())
    monkeypatch.setattr(database_manager,'DatabaseManager',lambda: SimpleNamespace(conn=connection,rollback_and_close=lambda: None))
    monkeypatch.setattr(compiled_content_program,'program_allowed',lambda *args: True)
    monkeypatch.setattr(compiled_content_program,'authorize_contract',lambda *args: None)
    monkeypatch.setattr(compiled_content_program,'dispatch_fence',lambda *args: True)
    monkeypatch.setattr(compiled_content_program,'runtime_targets',lambda *args: targets)
    calls = []
    def send(envelope, actor):
        calls.append(envelope['payload']['recipient_user_id'])
        if uncertain and len(calls) == 1:
            raise TimeoutError('unknown transport outcome')
        return {'result': {'status':'completed','publication_status_unchanged':True}, 'billing':{}}
    monkeypatch.setattr(agent_capability_handlers,'_handle_content_publish_handoff',send)
    posts = [{'post_id':request_identity(target,'post'), 'revision':'r', 'eligible':True} for target in targets]
    prepared = {'run':{'business_id':'a','blueprint_id':'bp','blueprint_version_id':'v','created_by_user_id':'alex','id':'run','lease_token':'lease'},
                'artifact':{'manifest':{'content_handoff_contract':contract},'artifact_hash':'hash'},'input':{'posts':posts}}
    outcome = compiled_content_program.dispatch_result(prepared, {'requests':[{'post_id':post['post_id'],'revision':'r'} for post in posts]})
    assert len(calls) == 4
    assert outcome['handoff']['status'] == ('needs_attention' if uncertain else 'completed')
    assert outcome['publication_status_unchanged']
    assert outcome['handoff']['targets'][-1]['result']['result']['status'] == 'completed'


def test_last_packet_requires_both_recipients_current_revision_and_all_parts():
    posts = []
    for platform in ['telegram', 'vk', 'max']:
        post = {'id': platform, 'platform': platform, 'status': 'approved', 'platform_text': 'Text',
                'scheduled_for': datetime(2026,11,1,tzinfo=timezone.utc), 'selected_photos': [{'id': 'photo'}]}
        revision = handoff_revision(post)
        receipt = {'sent_at': '2026-10-31', 'revision': revision, 'parts': {'photo:0': {'status': 'sent'}, 'text:0': {'status': 'sent'}}}
        post['metadata_json'] = {'staff_handoff': {'telegram_deliveries': {'alex': deepcopy(receipt), 'irina': deepcopy(receipt)}}}
        posts.append(post)
    assert last_packet_complete(posts, ['alex','irina'], ['telegram','vk','max'])
    posts[0]['metadata_json']['staff_handoff']['telegram_deliveries']['irina']['parts']['text:0']['status'] = 'uncertain'
    assert not last_packet_complete(posts, ['alex','irina'], ['telegram','vk','max'])
    posts[0]['metadata_json']['staff_handoff']['telegram_deliveries']['irina']['parts']['text:0']['status'] = 'sent'
    posts[0]['platform_text'] = 'Updated'
    assert not last_packet_complete(posts, ['alex','irina'], ['telegram','vk','max'])
