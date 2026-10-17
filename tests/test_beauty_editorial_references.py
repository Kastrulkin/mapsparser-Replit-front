import pytest
from services.beauty_editorial_references import is_beauty_editorial_reference,beauty_editorial_guidance
from core.industry_patterns import detect_industry_key

@pytest.mark.parametrize('text',['Стрижка: слои у лица и длина','Маникюр в молочном оттенке','Тонирование: работа с оттенком'])
def test_salon_reference(text):
    assert is_beauty_editorial_reference(text)

@pytest.mark.parametrize('text',['Вакансия: мастер маникюра','Франшиза салона красоты','Обучение мастеров окрашиванию','Оптовые поставки для укладки','Школа: красивая осень','Маникюр: гарантированный результат'])
def test_not_customer_reference(text):
    assert not is_beauty_editorial_reference(text)

def test_shared_guidance_for_new_salon():
    assert detect_industry_key(business_type='beauty_salon')=='beauty'
    refs=beauty_editorial_guidance()
    assert len(refs)==3 and len({r['id'] for r in refs})==3
    assert all(r['source_url'].startswith('https://') for r in refs)
    assert 'Органика' not in str(refs) and 'business_id' not in str(refs)
