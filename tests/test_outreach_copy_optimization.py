import copy
import json
from datetime import datetime, timedelta, timezone

import pytest
from services import outreach_personalization_ai as ai
from services import outreach_review_cache as cache
from services.outreach_copy_optimization import language_review_prompt, approved_template_touches


class MemoryRedis:
    def __init__(self): self.values = {}; self.ttls = []
    def get(self, key): return self.values.get(key)
    def setex(self, key, ttl, value): self.values[key] = value; self.ttls.append(ttl)


def payload():
    return dict(motion='localos_sales', identity={'company_name': 'Пример'},
                candidate={'source_url': 'https://example.com/fact', 'observed_fact': 'В официальном канале есть новые услуги.',
                           'evidence_id': 'fact', 'recipient_segment': 'beauty_team', 'freshness': 'current', 'evidence_status': 'observed'},
                founder_story={'story': 'Одобренный опыт.', 'proof': 'Точное доказательство.', 'offer': 'Короткий разбор.'},
                sequence=[{'sequence_index': 0, 'channel': 'email', 'angle': 'founder_story', 'day_offset': 0}],
                business_id='business', user_id='owner')


def review_response(prompt, **kwargs):
    record = json.loads(prompt.split('INPUT_JSON:\n', 1)[1])
    return json.dumps({'reviews': [{'sequence_index': touch['sequence_index'], 'scores': {key: 2 for key in ai.QUALITY_CRITERIA}, 'verdict': 'approve', 'reason_codes': []} for touch in record['touches']]})


@pytest.fixture
def cached_ai(monkeypatch):
    backend = MemoryRedis(); calls = []
    monkeypatch.setattr(cache, '_backend', lambda: backend)
    monkeypatch.setattr(ai, 'model_configuration', lambda routed: {'model': 'test-model'})
    monkeypatch.setattr('services.outreach_language_routing.enabled', lambda business_id: False)
    def review(prompt, **kwargs): calls.append(prompt); return review_response(prompt, **kwargs)
    monkeypatch.setattr(ai, '_default_generator', review)
    return backend, calls


def test_identical_review_reused_and_current_inputs_invalidate(cached_ai):
    backend, calls = cached_ai; data = payload(); before = copy.deepcopy(data)
    first = ai.generate_personalized_sequence(**data)
    assert first['status'] == 'ready'
    assert first['review_cache']['semantic_hit'] is False
    second = ai.generate_personalized_sequence(**data)
    assert second['review_cache']['semantic_hit'] is True
    assert first['touches'] == second['touches']
    assert len(calls) == 1 and data == before
    assert all(ttl == 3600 for ttl in backend.ttls)
    data['candidate']['source_url'] = 'https://example.com/new-fact'
    assert ai.generate_personalized_sequence(**data)['review_cache']['semantic_hit'] is False
    data['founder_story']['proof'] += ' Дополнение.'
    assert ai.generate_personalized_sequence(**data)['review_cache']['semantic_hit'] is False
    assert len(calls) == 3


def test_failed_or_malformed_cached_result_never_approves(cached_ai, monkeypatch):
    backend, calls = cached_ai; data = payload()
    ai.generate_personalized_sequence(**data)
    key = next(iter(backend.values))
    backend.values[key] = json.dumps({'reviews': [{'sequence_index': 0, 'scores': {}, 'verdict': 'approve'}]})
    assert ai.generate_personalized_sequence(**data)['review_cache']['semantic_hit'] is False
    backend.values.clear()
    def reject(prompt, **kwargs):
        value = json.loads(review_response(prompt)); value['reviews'][0]['verdict'] = 'reject'; return json.dumps(value)
    monkeypatch.setattr(ai, '_default_generator', reject)
    assert not ai.generate_personalized_sequence(**data)['semantic_reviews'][0]['passed']
    assert backend.values == {}


def test_cache_outage_runs_normal_check_and_never_sends(cached_ai, monkeypatch):
    _, calls = cached_ai
    def unavailable(): raise RuntimeError('Cache unavailable')
    monkeypatch.setattr(cache, '_backend', unavailable)
    result = ai.generate_personalized_sequence(**payload())
    assert result['status'] == 'ready' and not result['review_cache']['semantic_hit']
    assert len(calls) == 1


def test_keys_isolate_actor_company_model_rules_and_day():
    data = dict(stage='semantic', prompt='Exact message and rules', provenance={'source': 'https://example.com'}, business_id='company', user_id='owner', model_config={'model': 'model-v1'}, code_digest='code-v1', now=datetime(2026, 10, 16, tzinfo=timezone.utc))
    first = cache.review_cache_key(**data)
    assert 'company' not in first and 'owner' not in first
    for key, value in [('prompt', 'Changed message/rules'), ('provenance', {'source': 'changed'}), ('business_id', 'other'), ('user_id', 'other'), ('model_config', {'model': 'model-v2'}), ('code_digest', 'code-v2'), ('now', data['now'] + timedelta(days=1))]:
        assert cache.review_cache_key(**{**data, key: value}) != first


def test_grammar_only_sees_editable_text():
    touch = {'sequence_index': 0, 'text': 'Точный текст.', 'subject': 'Тема', 'evidence_ids': ['secret-id'], 'source_url': 'https://example.com/hidden', 'observation': 'ORIGINAL_SOURCE_METADATA', 'relevance_bridge': 'DUPLICATE_BRIDGE', 'localized_fields': {'private': 'HIDDEN'}}
    before = copy.deepcopy(touch); prompt = language_review_prompt([touch], 'ru')
    assert json.loads(prompt.split('INPUT_JSON:\n')[1]) == [{'sequence_index': 0, 'text': touch['text'], 'subject': touch['subject']}]
    assert touch == before
    for forbidden in ('secret-id', 'hidden', 'ORIGINAL_SOURCE_METADATA', 'DUPLICATE_BRIDGE', 'HIDDEN'): assert forbidden not in prompt


def template_payload():
    data = payload(); data.pop('business_id'); data.pop('user_id'); data['language'] = 'ru'
    data['candidate'].update(evidence_kind='active_social_activity', outreach_template_key='active_social_multichannel_content_v1', outreach_template_version=2, sender_mode='localos')
    data['sequence'][0]['angle'] = 'signal'
    return data


def test_only_current_canonical_templates_render_without_generation(cached_ai):
    data = template_payload(); before = copy.deepcopy(data)
    touches = approved_template_touches(**data)
    assert touches and touches[0]['template_version'] == 2
    assert data['candidate']['observed_fact'] in touches[0]['text']
    assert data == before
    data.pop('language')
    result = ai.generate_personalized_sequence(**data, business_id='business', user_id='owner')
    assert result['generation_mode'] == 'approved_template'
    assert result['touches'][0]['text'] == touches[0]['text']
    assert len(cached_ai[1]) == 1  # semantic review, zero copy-generation calls
    assert 'независимый редактор' in cached_ai[1][0]
    assert ai.generate_personalized_sequence(**data, business_id='business', user_id='owner')['review_cache']['semantic_hit']
    assert len(cached_ai[1]) == 1


@pytest.mark.parametrize('change', [dict(outreach_template_version=999), dict(outreach_template_key='user_supplied_body'), dict(freshness='stale'), dict(evidence_status='revoked'), dict(outreach_template_disabled=True), dict(sender_mode='localos_for_partner'), dict(evidence_id=None)])
def test_unapproved_changed_or_ineligible_templates_fall_back(change):
    data = template_payload(); data['candidate'].update(change)
    assert approved_template_touches(**data) is None


def test_templates_require_matching_touch_evidence_and_honor_forbidden_claims():
    data = template_payload(); data['sequence'][0]['source_url'] = 'https://example.com/another'
    assert approved_template_touches(**data) is None
    data['sequence'][0].pop('source_url'); data['founder_story']['forbidden_claims'] = ['LocalOS']
    assert approved_template_touches(**data) is None
    data['founder_story']['forbidden_claims'] = []; data['language'] = 'en'
    assert approved_template_touches(**data) is None


def test_routed_semantic_and_language_reviews_are_reused_with_private_scope(cached_ai, monkeypatch):
    calls = []
    monkeypatch.setattr('services.outreach_language_routing.enabled', lambda business_id: True)
    def run(prompt, **kwargs):
        calls.append((prompt, kwargs))
        assert 'Пример' not in prompt
        return json.dumps({'passed': True, 'issues': []}) if kwargs.get('review') else review_response(prompt, **kwargs)
    monkeypatch.setattr('services.outreach_language_routing.run_copy', run)
    data = template_payload(); data.pop('language')
    first = ai.generate_personalized_sequence(**data, business_id='business', user_id='owner')
    assert first['status'] == 'ready' and first['generation_mode'] == 'approved_template'
    assert first['touches'][0]['subject'].startswith('Пример')
    assert len(calls) == 2
    assert calls[1][1]['review'] is True and 'evidence_ids' not in calls[1][0]
    second = ai.generate_personalized_sequence(**data, business_id='business', user_id='owner')
    assert second['review_cache'] == {'semantic_hit': True, 'language_hit': True}
    assert second['touches'] == first['touches']
    assert len(calls) == 2
    # A different identity must not reuse sanitized-placeholder results.
    data['identity']['company_name'] = 'Другой пример'
    third = ai.generate_personalized_sequence(**data, business_id='business', user_id='owner')
    assert third['status'] == 'ready' and not third['review_cache']['semantic_hit']
    assert len(calls) == 4


def test_selected_editorial_contract_uses_existing_contract_renderer():
    data = template_payload(); data['candidate']['approved_copy_contract'] = 'fgf_average_ticket_owner_v1'
    assert approved_template_touches(**data) is None


def test_cached_result_expires_or_model_changes_before_next_manual_check(cached_ai, monkeypatch):
    backend, calls = cached_ai; data = payload()
    ai.generate_personalized_sequence(**data)
    backend.values.clear()  # Redis TTL eviction
    assert not ai.generate_personalized_sequence(**data)['review_cache']['semantic_hit']
    monkeypatch.setattr(ai, 'model_configuration', lambda routed: {'model': 'new-model'})
    assert not ai.generate_personalized_sequence(**data)['review_cache']['semantic_hit']
    assert len(calls) == 3


def test_cache_never_overrides_current_suppression(cached_ai):
    from services.outreach_campaign_service import _quality_gate
    data = payload()
    ai.generate_personalized_sequence(**data)
    reused = ai.generate_personalized_sequence(**data)
    assert reused['review_cache']['semantic_hit']
    gate = _quality_gate(reused['touches'][0]['text'], data['candidate'], data['founder_story'], channel='email', channel_status='ready', suppressed=True, angle='founder_story')
    assert not gate['passed']
