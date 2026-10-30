import pytest
from services.client_chat_sandbox import action_preview,guard_response,HANDOFF_PREVIEW,BOOKING_PREVIEW

@pytest.mark.parametrize('message',['Позовите сотрудника','Хочу поговорить с живым администратором','Вы действительно уже отправили запрос сотруднику?'])
def test_handoff_is_explicit_preview(message):
    assert action_preview(message)==HANDOFF_PREVIEW

@pytest.mark.parametrize('response',['Ваш запрос передан сотруднику.','Сообщение отправлено администратору.','Вы записаны на завтра.'])
def test_false_effect_claim_is_removed(response):
    assert guard_response(response) in (HANDOFF_PREVIEW,BOOKING_PREVIEW)

def test_prices_are_preserved():
    assert action_preview('Сколько стоит массаж?') is None
    assert guard_response('Цена массажа 2000 рублей.')=='Цена массажа 2000 рублей.'
