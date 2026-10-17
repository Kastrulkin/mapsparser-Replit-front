import pytest
from core.industry_patterns import detect_industry_key,format_industry_pattern_prompt
from services.apparel_editorial_references import is_apparel_editorial_reference,apparel_editorial_guidance

@pytest.mark.parametrize('text',['Пошив брендированной одежды: худи и посадка','Футболка: размещение логотипа','Garment manufacturing: sample and fit'])
def test_garment_reference_kept(text):
    assert is_apparel_editorial_reference(text)

@pytest.mark.parametrize('text',['Корпоративные подарки: конфеты и ежедневники','Подарочный сертификат на пошив','Ремонт швейных машин','Стартап #стартапдня: швейное производство','Упаковка и подарочный набор с футболкой','Лекция о предпринимателях, которые привлекали внимание','Парикмахер отвлекался от процесса'])
def test_wrong_reference_rejected(text):
    assert not is_apparel_editorial_reference(text)

def test_new_manufacturer_gets_shared_type():
    key=detect_industry_key(business_name='Новая фабрика',business_type='пошив брендированной одежды')
    assert key=='apparel_manufacturing'
    text=format_industry_pattern_prompt(key,mode='news')
    assert 'подарк' in text.lower() and 'состав' in text.lower()
    assert detect_industry_key(business_type='manufacturer',industry='apparel_manufacturing')==key
    assert detect_industry_key(business_name='Магазин одежды',business_type='retail')=='retail'
    assert all('business_id' not in r and 'Мелиора' not in str(r) for r in apparel_editorial_guidance())

def test_curated_catalogue_has_fifteen_distinct_sourced_references():
    references = apparel_editorial_guidance()
    assert len(references) == 15
    assert len({r['id'] for r in references}) == 15
    assert len({r['source_url'] for r in references}) == 15
    assert all(r['source_url'].startswith('https://') for r in references)
    assert all(r['source_type'] == 'editorial_guidance' and r['techniques'] for r in references)

def test_apparel_loader_preserves_catalogue_with_default_limit():
    from services.content_plan_service import _load_editorial_pattern_library, _format_editorial_pattern_context

    class EmptyLibrary:
        def execute(self, *args):
            pass

        def fetchall(self):
            return []

    references = _load_editorial_pattern_library(EmptyLibrary(), {}, industry_key='apparel_manufacturing')
    assert len(references) == 15
    prompt = _format_editorial_pattern_context(references)
    assert all(r['source_url'] in prompt for r in apparel_editorial_guidance())
    assert 'не факты компании' in prompt
