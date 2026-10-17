import pytest
from services.education_editorial_references import is_education_editorial_reference, education_editorial_guidance
from core.industry_patterns import detect_industry_key, format_industry_pattern_prompt


@pytest.mark.parametrize('text', ['Школа беременных: подготовка к родам',
    'Как я чуть не открыл домашнюю школу', 'Автошкола: запись на вождение',
    'Франшиза: открыть школу программирования для детей', 'Школа инвесторов: венчур'])
def test_unrelated_school_rejected(text):
    assert not is_education_editorial_reference(text)


@pytest.mark.parametrize('text', ['Робототехника: дети собрали конструкцию',
    'Должен ли ребёнок читать до школы?', 'Ученик показывает свой проект в Roblox',
    'Children create their own Scratch stories'])
def test_child_education_kept(text):
    assert is_education_editorial_reference(text)


def test_guidance_is_shared_not_tenant_specific():
    refs = education_editorial_guidance()
    assert len(refs) == 3
    assert len({r['id'] for r in refs}) == 3
    assert all(r['source_url'].startswith('https://') for r in refs)
    assert all(r['source_type'] == 'editorial_guidance' for r in refs)
    assert all('business_id' not in r and 'Intellectum' not in str(r) for r in refs)


def test_new_school_uses_same_type_and_rules():
    key = detect_industry_key(business_name='New Horizons Coding School')
    assert key == 'education_children'
    assert 'проект' in format_industry_pattern_prompt(key, mode='news')


def test_loader_searches_education_before_global_limit_and_keeps_guidance():
    from services.content_plan_service import _load_editorial_pattern_library
    class Cursor:
        def __init__(self):
            self.selects = []
            self.rows = []
        def execute(self, sql, params=None):
            if 'SELECT' in sql:
                self.selects.append((sql, params))
                self.rows = ([{'id': 'valid', 'content_text': 'Дети собрали проект по робототехнике: сначала выбрали детали, потом проверили программу.\n\nЗа 40 минут ученик научился находить ошибку и объяснять своё решение.', 'metadata_json': {}, 'source_role': 'expert'},
                              {'id': 'invalid', 'content_text': 'Школа беременных: ребёнок и роды', 'metadata_json': {}, 'source_role': 'expert'}]
                             if 'knowledge_documents' in sql else [])
        def fetchall(self):
            return self.rows
    cursor = Cursor()
    result = _load_editorial_pattern_library(cursor, {}, industry_key='education_children')
    assert result[0]['source_type'] == 'editorial_guidance'
    assert any(r['id'] == 'telegram_valid' for r in result)
    assert not any(r['id'] == 'telegram_invalid' for r in result)
    assert len(cursor.selects) == 2
    for sql, params in cursor.selects:
        assert '~* %s' in sql and 'LIMIT 400' in sql
        assert params[0] is True
