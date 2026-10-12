"""Pure prompt regression checks: no database, provider calls or generation."""
import ast
import re
import os
from pathlib import Path


def build_prompt():
    source = Path(os.environ.get('CONTENT_FACT_SOURCE', str(Path(__file__).resolve().parents[1] / 'deploy/content_fact_contract/release_functions.py')))
    tree = ast.parse(source.read_text())
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == '_content_generation_v2_prompt')
    namespace = {
        'Any': object, 'NATURAL_CONTENT_CONTRACT': '',
        '_content_plan_language_instruction': lambda language: 'Русский',
        '_build_content_plan_business_fact_block': lambda facts: facts['name'],
        '_content_brief_prompt_block': lambda brief: 'review-1: ребёнок сидел в кресле',
    }
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
    return namespace['_content_generation_v2_prompt'](
        business_facts={'name': 'Весёлая расчёска'},
        brief={'sources': [{'id': 'review-1', 'type': 'public_review'}]},
        voice={'examples': [{'text': 'У другого бизнеса дети возвращаются каждую неделю'}]},
        language='ru')


def test_review_and_examples_do_not_authorize_fiction():
    prompt = build_prompt()
    assert 'НЕ источник фактов текущего поста' in prompt
    assert 'Не превращай отзыв в рассказ от первого лица' in prompt
    assert 'повторный визит' in prompt
    assert 'Источника story_facts нет' in prompt
    assert 'Человеческая история допустима только' in prompt


def test_strict_json_and_missing_facts_contract():
    prompt = build_prompt()
    assert 'только двойные кавычки' in prompt
    assert 'Никаких Markdown-ограждений' in prompt
    assert '{"candidates":[]}' in prompt
    assert 'Каждый used_fact_ids должен быть ID из брифа' in prompt


def claim_checker():
    source = Path(os.environ.get('CONTENT_FACT_SOURCE', str(Path(__file__).resolve().parents[1] / 'deploy/content_fact_contract/release_functions.py')))
    tree = ast.parse(source.read_text())
    nodes = [node for node in tree.body if
             (isinstance(node, ast.FunctionDef) and node.name in {
                 '_unsupported_candidate_claims', '_content_creative_warnings',
                 '_content_brief_fact_sources',
                 '_strip_content_json_markdown', '_parse_content_candidates'})
             or (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                 and node.target.id == 'UNSUPPORTED_CLAIM_PATTERNS')]
    namespace = {'Any': object, 're': re, 'json': __import__('json'),
                 '_format_long_generated_paragraphs': lambda text: text,
                 '_sanitize_generated_news_text': lambda text: text}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), namespace)
    return namespace['_unsupported_candidate_claims']


def test_generalizations_are_not_factual_blockers_but_new_story_is():
    brief = {'sources': [{'id': 'review-1', 'type': 'public_review',
                         'fact': 'Двухлетний сын спокойно сидел в кресле-машинке.'}]}
    text = ('Мастера умеют найти подход даже к самым активным непоседам. '
            'Дети выходят довольные, а родители спокойны за результат. '
            'Теперь он готовится к детскому саду.')
    assert len(claim_checker()(text, brief)) == 1
    assert claim_checker()('Атмосфера праздника. Дети выходят довольные, а родители спокойны за результат.', brief) == []
    assert claim_checker()('В отзыве родитель рассказал, что сын спокойно сидел в кресле-машинке.', brief) == []


def test_review_cannot_become_author_first_person_story():
    brief = {'sources': [{'id': 'review-1', 'type': 'public_review', 'fact': 'Сын сидел спокойно.'}]}
    assert claim_checker()('Боялась, что будет сложно усадить малыша.', brief)


def fact_snapshot_namespace():
    source = Path(os.environ.get('CONTENT_FACT_SOURCE', str(Path(__file__).resolve().parents[1] / 'deploy/content_fact_contract/release_functions.py')))
    names = {'_with_content_fact_sources', '_content_brief_fact_sources',
             '_content_brief_prompt_block', '_score_content_candidate'}
    tree = ast.parse(source.read_text())
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    namespace = {'Any': object, 're': re, 'SLOP_PATTERNS': [],
                 '_unsupported_candidate_claims': claim_checker(),
                 '_editorial_quality_issues': lambda text, voice: ([], [], [], []),
                 '_confirmed_story_coverage_issues': lambda text, brief: [],
                 '_content_creative_warnings': lambda text: [],
                 'review_content_text': lambda text, brief: {'quality_passed': True}}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), namespace)
    return namespace


def test_service_description_and_address_reach_writer_and_validator():
    n = fact_snapshot_namespace()
    service = {'id': 'service:123', 'fact': 'Первая стрижка: подарим диплом.',
               'business_id': 'eng', 'table': 'userservices', 'record_id': '123',
               'origin': 'manual_user_verified'}
    original = {'sources': [{'id': 'services', 'fact': 'Первая стрижка'}]}
    brief = n['_with_content_fact_sources'](original,
        {'address': 'Энгельса, 154', 'service_sources': [service]}, 'eng')
    assert 'fact_sources' not in original
    prompt_block = n['_content_brief_prompt_block'](brief)
    assert 'service:123' in prompt_block and 'подарим диплом' in prompt_block
    assert 'business_profile:address' in prompt_block and '154' in prompt_block
    assert service in brief['fact_sources']
    assert claim_checker()('Энгельса, 154. После первой стрижки подарим диплом.', brief) == []
    assert claim_checker()('Стрижка стоит 99999 рублей.', brief)
    candidate = {'text': 'После первой стрижки подарим диплом.', 'used_fact_ids': ['service:123']}
    assert n['_score_content_candidate'](candidate, brief, {})['factual_gate_passed']
    candidate['used_fact_ids'] = ['nonexistent']
    assert not n['_score_content_candidate'](candidate, brief, {})['factual_gate_passed']


def test_snapshot_does_not_import_another_branch_and_legacy_still_works():
    n = fact_snapshot_namespace()
    legacy = {'sources': [{'id': 'old', 'fact': 'Первая стрижка'}]}
    brief = n['_with_content_fact_sources'](legacy, {'service_sources': [
        {'id': 'service:other', 'fact': 'Другая услуга', 'business_id': 'dol'}]}, 'eng')
    assert 'service:other' not in {x['id'] for x in brief['fact_sources']}
    assert n['_content_brief_fact_sources'](legacy) == legacy['sources']


def test_markdown_wrapper_is_removed_without_repairing_bad_json():
    source = Path(os.environ.get('CONTENT_FACT_SOURCE', str(Path(__file__).resolve().parents[1] / 'deploy/content_fact_contract/release_functions.py')))
    tree = ast.parse(source.read_text())
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef)
             and node.name in {'_strip_content_json_markdown', '_parse_content_candidates'}]
    namespace = {'Any': object, 're': re, 'json': __import__('json'),
                 '_format_long_generated_paragraphs': lambda text: text,
                 '_sanitize_generated_news_text': lambda text: text}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), namespace)
    parser = namespace['_parse_content_candidates']
    payload = '{"candidates":[{"text":"Первая стрижка","used_fact_ids":["services"]}]}'
    assert parser('```json\n' + payload + '\n```') == parser(payload)
    assert parser("```json\n{'candidates': []}\n```") == []
