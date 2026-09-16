import pytest
from services.operator_editorial import preserve_requested_links
from services.operator_finance_amounts import verify_revenue

@pytest.mark.parametrize('text',['Бронирование: [ссылка для бронирования].','Новый текст без адреса.','Бронирование: https://riderra.com/ru?lang=ru'])
def test_required_link_retains_query_and_replaces_placeholder(text):
    result=preserve_requested_links(text,'Старый пост https://riderra.com/ru?lang=ru','Сократи текст, оставь ссылку для бронирования.')
    assert result.count('https://riderra.com/ru?lang=ru')==1
    assert '[ссылка' not in result

def test_no_link_added_when_removal_requested():
    assert preserve_requested_links('Текст','https://riderra.com','Удали ссылку')=='Текст'

@pytest.mark.parametrize('message,expected',[
 ('Выручка 350 евро, возврат 20 евро','350'),
 ('Сегодня 10 чеков 2 с допродажей выручка 350 евро возврат 20 евро','350'),
 ('Выручка триста пятьдесят евро, возврат двадцать евро','350'),
 ('Выручка 350,50 евро, возврат 20 евро','350.50'),
 ('Выручка 1 350 евро, возврат 20 евро','1350'),
 ('Выручка тридцать пять тысяч евро, возврат двадцать евро','35000'),
 ('Выручка после возвратов 350 евро, возврат 20 евро','370'),
 ('Выручка 350 евро после возвратов, возврат 20 евро','370'),
 ('Нет, выручка 380 евро. Остальное верно.','380'),
])
def test_revenue_is_grounded_in_user_input(message,expected):
    result=verify_revenue(message,{'kind':'daily','values':{'revenue':'999','refunds':'20','checks':'10'}})
    assert result['values']['revenue']==expected
    assert result['values']['checks']=='10'

@pytest.mark.parametrize('message',['Выручка после возвратов 350 евро','Выручка 350 евро, нет, выручка 380 евро'])
def test_ambiguous_revenue_requires_clarification(message):
    with pytest.raises(ValueError):verify_revenue(message,{'kind':'daily','values':{'revenue':'350'}})

def test_unmentioned_revenue_and_increment_are_unchanged():
    args={'kind':'daily','mode':'add','values':{'revenue':'20'}}
    assert verify_revenue('Добавь к выручке ещё 20',args)==args
    assert verify_revenue('Остальное верно',args)==args

@pytest.mark.parametrize('message',['Выручка -350 евро','Выручка 350–400 евро','Выручка 350 тыс рублей','Выручка триста евро пятьдесят центов'])
def test_unsupported_amount_shape_is_not_silently_changed(message):
    with pytest.raises(ValueError):verify_revenue(message,{'kind':'daily','values':{'revenue':'350'}})
