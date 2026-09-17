import pytest
from services import content_rules


def test_requires_timezone():
    with pytest.raises(ValueError,match='часовой пояс'):
        content_rules.parse_time('2026-09-17T12:00:00')


def test_rule_validation_allows_confirmed_entertainment(monkeypatch):
    monkeypatch.setattr(content_rules,'active_rules',lambda *args:[{'text':'Не обещать любые мультфильмы'}])
    assert content_rules.validate(None,'b','u','Игровая обстановка',lambda *args,**kwargs:'{"valid":true,"violations":[]}')=='Игровая обстановка'


@pytest.mark.parametrize('response',['','{}','{"valid":false,"violations":["любые мультфильмы"]}','{"valid":true,"violations":["неподтверждено"]}'])
def test_fail_closed_on_invalid_validation(monkeypatch,response):
    monkeypatch.setattr(content_rules,'active_rules',lambda *args:[{'text':'Не обещать любые мультфильмы'}])
    with pytest.raises(ValueError):
        content_rules.validate(None,'b','u','Любые мультфильмы',lambda *args,**kwargs:response)


def test_no_extra_model_call_without_rules(monkeypatch):
    monkeypatch.setattr(content_rules,'active_rules',lambda *args:[])
    assert content_rules.validate(None,'b','u','Черновик',None)=='Черновик'


def test_one_repair_and_recheck(monkeypatch):
    monkeypatch.setattr(content_rules,'active_rules',lambda *args:[{'text':'Не обещать любые мультфильмы'}])
    replies=iter(['{"valid":false,"violations":["обещание"]}','{"post":"Игровая обстановка и внимательные мастера для вашего ребёнка."}','{"valid":true,"violations":[]}'])
    assert 'Игровая' in content_rules.enforce(None,'b','u','Любые мультфильмы',lambda *args,**kwargs:next(replies))
    with pytest.raises(StopIteration): next(replies)


def test_failed_repair_never_released(monkeypatch):
    monkeypatch.setattr(content_rules,'active_rules',lambda *args:[{'text':'Запрет'}])
    replies=iter(['{"valid":false,"violations":["нарушение"]}','{"post":"Неправильный текст, который всё ещё нарушает правило бизнеса."}','{"valid":false,"violations":["нарушение"]}'])
    with pytest.raises(ValueError):content_rules.enforce(None,'b','u','Текст',lambda *args,**kwargs:next(replies))


@pytest.mark.parametrize('text,amount',[('Стоимость 1 200 ₽','1200'),('Цена 350,50 евро','350.50'),('Услуга 500 руб.','500')])
def test_money_normalization(text,amount):
    from decimal import Decimal
    assert content_rules.money_values(text)==[Decimal(amount)]


def test_unverified_price_rejected_before_model(monkeypatch):
    monkeypatch.setattr(content_rules,'active_rules',lambda *args:[])
    with pytest.raises(ValueError,match='Неподтверждённая цена'):
        content_rules.validate(None,'b','u','Цена 500 ₽',lambda *a,**kw:pytest.fail('unverified price reached model'))


def test_explicit_owner_price_is_evidence(monkeypatch):
    monkeypatch.setattr(content_rules,'active_rules',lambda *args:[])
    assert content_rules.validate(None,'b','u','Цена 500 ₽',lambda *a,**kw:'{"valid":true,"violations":[]}',source_facts='Цена 500 ₽')=='Цена 500 ₽'
