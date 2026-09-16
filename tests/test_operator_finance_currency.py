import pytest
from services.operator_finance_amounts import verify_currency

@pytest.mark.parametrize('message',[
    'Сегодня 10 чеков, выручка 350 рублей.',
    'Сегодня 10 чеков выручка 350 р возврат 20 р',
    'Выручка неизвестна, валюта рубли', 'Выручка 350 ₽', 'Расход 15 руб.', 'Выручка 350 RUB',
])
def test_explicit_rubles_survive_missing_model_currency(message):
    assert verify_currency(message, {'kind':'daily'})['currency']=='RUB'

@pytest.mark.parametrize('message,expected',[
    ('Выручка 350 евро','EUR'), ('Расход 15 USD','USD'),
    ('Выручка 350 белорусских рублей','BYN'),
])
def test_explicit_currency_overrides_model_guess(message,expected):
    assert verify_currency(message,{'kind':'daily','currency':'RUB'})['currency']==expected

@pytest.mark.parametrize('message',['Сегодня 10 чеков','Доход пока неизвестен','Выручка 350'])
def test_missing_currency_stays_missing(message):
    assert 'currency' not in verify_currency(message,{'kind':'daily'})

@pytest.mark.parametrize('message',['Выручка 350 рублей и 20 евро','Выручка 20 USD, расход 10 рублей'])
def test_mixed_currency_needs_separate_record(message):
    with pytest.raises(ValueError,match='валют'):
        verify_currency(message,{'kind':'daily'})

def test_settings_are_not_modified_by_financial_normalization():
    args={'kind':'settings','currency':'EUR'}
    assert verify_currency('Рубли не сохраняй',args)==args
