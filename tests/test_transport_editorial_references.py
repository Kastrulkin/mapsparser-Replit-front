import pytest
from services.transport_editorial_references import is_transport_editorial_reference
from core.industry_patterns import detect_industry_key


@pytest.mark.parametrize('text', [
    'HomeLight #стартапдня: риэлтор и такси-агрегаторы',
    'TransferWise переводы денег из Англии в Австралию',
    'CarTaxi #стартапдня: Uber для эвакуаторов, водители',
    '#новостинедели: аэропорт, транспорт, инвестиции',
    'We offer freight грузоперевозки transport',
    'The restaurant serves a breakfast buffet',
])
def test_unrelated_reference_rejected(text):
    assert not is_transport_editorial_reference(text)


@pytest.mark.parametrize('text', [
    'Private airport transfers for your family holiday',
    'Трансфер в аэропорт для туристов',
    'Taxi til dit hotel i Aarhus',
    'Sightseeing journeys with a chauffeur',
])
def test_passenger_service_reference_kept(text):
    assert is_transport_editorial_reference(text)


def test_taxi_detected():
    assert detect_industry_key(business_name='Alternativ Taxi', categories=['Taxi service']) == 'transport'
