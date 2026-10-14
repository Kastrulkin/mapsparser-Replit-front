from services.agent_blueprint_creation import outreach_creation_summary
from services.outreach_continuation import normalize_config


def test_preview_exposes_exact_query_geography_and_generic_requirements():
    config=normalize_config({'audience':'Поставщики косметики','search_geography':['Казань'],
        'requirements':['Оптовые поставки','Публичный email'],
        'queries':[{'query':'поставщик косметики оптом Казань','city':'Казань'}],
        'target_count':2,'mode':'prepare_only','offer':'Поставка в салон','language':'ru'})
    text=outreach_creation_summary(config)
    assert 'Поставщики косметики' in text and 'Где: Казань' in text
    assert 'Оптовые поставки' in text and 'Публичный email' in text
    assert 'поставщик косметики оптом Казань' in text
    assert 'направление:' not in text and 'центов' not in text
