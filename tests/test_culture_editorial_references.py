import pytest
from services.culture_editorial_references import is_culture_editorial_reference, culture_editorial_guidance
from core.industry_patterns import detect_industry_key, format_industry_pattern_prompt


@pytest.mark.parametrize('text', ['Выставка: одна работа и рассказ художника',
    'Квартет играет концерт. Зрители выбирают следующий номер.',
    'Cultural gallery exhibition with a curator',
    'Культурное пространство: знакомство с командой'])
def test_cultural_reference_kept(text):
    assert is_culture_editorial_reference(text)


@pytest.mark.parametrize('text', ['Севкабель: кабельная продукция на промышленной выставке',
    '#стартапдня: инвестиции в культурный центр',
    'Казино: депозит и выигрыш', 'Каток: заточка коньков и аренда льда'])
def test_false_reference_rejected(text):
    assert not is_culture_editorial_reference(text)


def test_new_cultural_business_gets_shared_rules():
    kind = detect_industry_key(business_type='culture', business_name='Новое культурное пространство')
    assert kind == 'culture'
    text = format_industry_pattern_prompt(kind, mode='news')
    assert 'архив' in text.lower() and 'коллекц' in text.lower()
    refs = culture_editorial_guidance()
    assert len(refs) == 3 and all(r['source_url'] for r in refs)
    assert all('Каток' not in str(r) and 'business_id' not in r for r in refs)
