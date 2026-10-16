import copy
import json

from services.outreach_personalization_ai import (
    PROMPT_VERSION, REVIEW_PROMPT_VERSION, _request_record,
    _generation_prompt, _review_prompt, generation_contract_current,
)
from services.outreach_prompt_context import sales_prompt_record


def request_record():
    return _request_record(
        motion='localos_sales', identity={'company_name': 'Пример'},
        candidate={
            'evidence_id': 'lead-fact', 'source_url': 'https://example.com/fact',
            'observed_fact': 'В официальном канале опубликован новый прайс.',
            'observed_at': '2026-10-15', 'freshness': 'fresh',
            'recipient_segment': 'beauty_team',
            'signal_combo': 'recent_price_update_announcement',
            'signal_hypothesis_key': 'recent_price_update_announcement',
            'approved_copy_contract': 'fgf_average_ticket_owner_v1',
            'publication_capabilities': {'approval_required': True, 'manual_or_supervised_channels': ['yandex_maps', 'two_gis']},
            'language_support': {'status': 'unsupported', 'sources': [{'permalink': 'https://example.com/language'}], 'frequency_claim_allowed': False},
        },
        founder_story={'story': 'Одобренный опыт.', 'proof': 'Точное доказательство.', 'offer': 'Только черновик.', 'forbidden_claims': ['гарантируем продажи']},
        sequence=[{'sequence_index': 0, 'channel': 'email', 'angle': 'average_ticket', 'text': 'Предварительный текст.', 'subject': 'Исходная тема', 'day_offset': 0}],
        voice_examples=['Индивидуальный пример отправителя.'],
    )


def test_projection_keeps_selected_contract_safety_sources_and_full_facts():
    request = request_record()
    request['personalization']['observation'] *= 100
    before = copy.deepcopy(request)
    projected = sales_prompt_record(request)
    playbook = projected['outreach_playbook']
    assert request == before
    for key in ('identity', 'personalization', 'evidence', 'sender', 'policy', 'representation', 'sequence'):
        assert projected[key] == request[key]
    for key in ('method_rules', 'constraints', 'approved_cases', 'approved_proofs'):
        assert playbook[key] == request['outreach_playbook'][key]
    selected = request['outreach_playbook']['approved_copy_contracts'][0]
    assert playbook['approved_copy_contracts'] == [selected]
    assert [x['key'] for x in playbook['pain_signal_hypotheses']] == ['recent_price_update_announcement']
    assert all('average_ticket' in x['angles'] for x in playbook['outreach_templates'])
    assert not {'source_refs', 'approved_message_examples'}.intersection(playbook)


def test_bulk_corpus_removed_but_retrieved_sources_and_support_denial_preserved():
    request = request_record()
    playbook = request['outreach_playbook']
    playbook['source_refs'] = [{'permalink': 'https://example.com/corpus/' + str(i)} for i in range(1000)]
    for pain in playbook['pain_library']:
        pain['candidate_source_phrases'] = [{'phrase': 'Исходная цитата корпуса.' * 50} for _ in range(50)]
    projected = sales_prompt_record(request)
    assert all('candidate_source_phrases' not in pain for pain in projected['outreach_playbook']['pain_library'])
    assert projected['personalization']['language_support'] == request['personalization']['language_support']
    assert len(json.dumps(projected, ensure_ascii=False)) < len(json.dumps(request, ensure_ascii=False)) * .1


def test_review_checks_final_message_and_preserves_conflicting_observations():
    request = request_record()
    p = request['personalization']
    touches = [dict(sequence_index=0, channel='email', angle='average_ticket', subject='Тема', text='Финальный текст', evidence_ids=['lead-fact'], observation=p['observation'], relevance_bridge=p['relevance_to_offer'], problem_hypothesis=p['problem_hypothesis']),
               dict(sequence_index=1, channel='email', angle='proof', text='Второй текст', observation='Неподтверждённое утверждение')]
    record = {'request': request, 'touches': touches, 'reviewed_at_utc': '2026-10-16T12:00:00Z'}
    before = copy.deepcopy(record)
    projected = sales_prompt_record(record, review=True)
    assert record == before
    assert projected['reviewed_at_utc'] == record['reviewed_at_utc']
    assert 'deterministic_draft' not in projected['request']['sequence'][0]
    assert 'deterministic_subject' not in projected['request']['sequence'][0]
    assert 'observation' not in projected['touches'][0]
    for key in ('text', 'subject', 'channel', 'angle', 'sequence_index', 'evidence_ids'):
        assert projected['touches'][0][key] == touches[0][key]
    assert projected['touches'][1]['observation'] == 'Неподтверждённое утверждение'


def test_non_sales_inputs_and_unknown_constraints_are_preserved():
    request = request_record()
    request['outreach_playbook']['custom_safety_rule'] = 'Запрещено обещать скидку.'
    assert sales_prompt_record(request)['outreach_playbook']['custom_safety_rule'] == 'Запрещено обещать скидку.'
    request['motion'] = 'client_partnership'
    assert sales_prompt_record(request) is request
    review = {'request': request, 'touches': []}
    assert sales_prompt_record(review, review=True) is review


def test_real_prompt_builders_use_projection_without_invalidating_saved_drafts():
    request = request_record()
    request['outreach_playbook']['source_refs'] = ['BULK_CORPUS_MUST_STAY_OUT']
    generation = _generation_prompt(request)
    review = _review_prompt({'request': request, 'touches': []})
    assert 'BULK_CORPUS_MUST_STAY_OUT' not in generation + review
    for prompt in (generation, review):
        data = json.loads(prompt.split('INPUT_JSON:\n', 1)[1])
        payload = data.get('request', data)
        assert payload['personalization']['language_support']['status'] == 'unsupported'
        assert 'Точное доказательство.' in prompt
        assert 'гарантируем продажи' in prompt
    assert generation_contract_current(
        {'generation_source': 'gigachat', 'generation_prompt_version': PROMPT_VERSION, 'semantic_review_prompt_version': REVIEW_PROMPT_VERSION},
        {'passed': True, 'semantic_review': {'passed': True}}, require_ai=True,
    )
