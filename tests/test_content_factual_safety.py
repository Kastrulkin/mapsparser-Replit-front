import json
import pytest
from services.content_plan_service import _parse_content_candidates, _score_content_candidate, _sanitize_generated_news_text, _repair_generated_brand_name

BRIEF = {'sources':[{'id':'service','fact':'Прокол ушей Система 75'}], 'confirmed_details':['Прокол ушей Система 75']}
PLAN_TEXT = 'Перед проколом ушей объясните ребёнку, что будет короткий щелчок и лёгкое пощипывание.\n\nПрокол выполняют системой 75 — инструмент делает прокол быстро и стерильно.'
NEWS_TEXT = 'Прокол ушей Система 75\n\nПроцедура выполняется с соблюдением всех необходимых требований.'

@pytest.mark.parametrize('text',[PLAN_TEXT, NEWS_TEXT])
def test_recorded_unconfirmed_claims_fail_factual_gate(text):
    candidate={'text':text,'used_fact_ids':['service'],'unsupported_facts':[]}
    scored=_score_content_candidate(candidate,BRIEF,{})
    assert not scored['factual_gate_passed']
    assert not scored['quality_passed']

@pytest.mark.parametrize('url',[
    'https://max.ru/id027504009270_bot?start=yanmap',
    'https://example.org/a_b?q=one_two&x=%23value#part_one',
    'https://example.org/стерильно_быстро#раздел',
])
def test_cleanup_preserves_exact_url(url):
    clean=_sanitize_generated_news_text('**Запись**: '+url+'\n\n#ненужныйхэштег')
    assert url in clean
    assert '**' not in clean and '#ненужныйхэштег' not in clean
    parsed=_parse_content_candidates(json.dumps({'candidates':[{'text':clean,'used_fact_ids':['service']}]}))
    assert url in parsed[0]['text']

def test_brand_typo_repair_leaves_url_unchanged():
    url='https://example.org/расчоска?name=Веселая'
    assert url in _repair_generated_brand_name('Веселая расчоска '+url,'Веселая расческа')

from services.content_factual_safety import unsupported_procedure_claims, validate_procedure_claims, UnsupportedContentClaims, PROCEDURE_FACT_CONTRACT

@pytest.mark.parametrize('claim',['стерильно','безопасно','безболезненно','лёгкое пощипывание','короткий щелчок','с соблюдением всех необходимых требований','Прокол выполняется быстро'])
def test_each_property_requires_its_own_evidence(claim):
    assert unsupported_procedure_claims(claim,['Прокол ушей Система 75'])
    assert not unsupported_procedure_claims(claim,[claim])

@pytest.mark.parametrize('source',[
    'Не обещайте стерильность: стерильно не подтверждено.',
    'Неизвестно, стерильно ли выполняется процедура.',
    'Проводится стерильно?',
    'https://example.org/стерильно',
])
def test_negative_or_question_or_url_is_not_evidence(source):
    assert unsupported_procedure_claims('Процедура выполняется стерильно.',[source])

def test_one_confirmed_property_does_not_license_another():
    issues=unsupported_procedure_claims('Прокол выполняется быстро и стерильно.',['Прокол выполняется быстро.'])
    assert len(issues)==1 and 'стерильность' in issues[0]

def test_simple_service_draft_and_links_pass_without_enrichment():
    text='В «Весёлой расчёске» доступен прокол ушей Система 75.\n\nПодробности: https://max.ru/id027504009270_bot?start=yanmap'
    assert validate_procedure_claims(text,['Прокол ушей Система 75'])==text

def test_procedural_text_in_link_is_not_a_claim():
    assert not unsupported_procedure_claims('Запись: https://example.org/стерильно_быстро',[])

def test_new_prompt_explicitly_forbids_inventing_procedure_properties():
    from services.operator_news_generation import _build_news_prompt
    assert PROCEDURE_FACT_CONTRACT in _build_news_prompt(source_text='Прокол ушей Система 75',business={})
