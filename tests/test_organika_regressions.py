import pytest
from services.operator_finance_amounts import daily_statement,verify_currency
from services.operator_context import PlannerContext


def test_review_query_survives_domain_selection():
    query={'name':'localos.query'}
    assert query in PlannerContext('Покажи последние отзывы').tools([query,{'name':'reviews.generate_reply_drafts'}])

@pytest.mark.parametrize('text,values',[
    ('Сегодня 10 чеков, 2 с допродажей, выручка 350 р возврат 20 р',{'revenue':'350','checks':'10','upsell_checks':'2','refunds':'20'}),
    ('Сегодня ноль чеков, ноль допродаж, выручка ноль рублей',{'revenue':'0','checks':'0','upsell_checks':'0'}),
    ('Сегодня 4 чека, выручка после возврата в 500 р, возврат 50 р',{'revenue':'550','checks':'4','refunds':'50'}),
    ('Сегодня семь чеков, два с допродажей. Выручку пока не знаю. Валюта рубли',{'checks':'7','upsell_checks':'2'}),
])
def test_literal_daily_facts(text,values):
    result=daily_statement(text)
    assert result['values']==values
    assert result['currency']=='RUB'


def test_correction_uses_new_revenue_and_keeps_other_fields():
    draft={'date':'2026-09-16','currency':'RUB','data':{'revenue':'350','checks':'10','upsell_checks':'2'}}
    result=daily_statement('Сегодня 10 чеков, 2 с допродажей, выручка 350 рублей.\nУточнение: Нет, выручка 380 рублей. Остальное верно.',draft)
    assert result['values']['revenue']=='380' and result['values']['checks']=='10'
    assert result['date']==draft['date']


def test_example_or_month_is_not_daily():
    assert daily_statement('Если сегодня десять чеков и выручка 350 р') is None
    assert daily_statement('За август 9000 рублей, 60 чеков') is None


def test_nested_currency_is_not_financial_metric():
    value=verify_currency('Сегодня семь чеков. Валюта рубли',{'kind':'daily','values':{'checks':7,'currency':'RUB'}})
    assert value=={'kind':'daily','currency':'RUB','values':{'checks':7}}


def test_action_actor_uses_verified_database_identity(monkeypatch):
    from services import operator_core,operator_audio
    def verified(cursor,user,business):
        assert (cursor,user,business)==('cursor','u','b')
        return {'is_superadmin':True},{}
    monkeypatch.setattr(operator_audio,'authorize_actor',verified)
    assert operator_core._operator_action_actor('u','b','cursor')=={'user_id':'u','is_superadmin':True}
    def denied(*args):raise PermissionError('revoked')
    monkeypatch.setattr(operator_audio,'authorize_actor',denied)
    with pytest.raises(PermissionError):operator_core._operator_action_actor('u','b','cursor')


def test_twice_weekly_schedule_is_calculated_without_model():
    from services.operator_plan_schedule import extract
    result=extract('Создай контент-план с 1 декабря 2026 на две недели, два поста в неделю, всего четыре поста.')
    assert result['dates']==['2026-12-01','2026-12-04','2026-12-08','2026-12-11']


def test_speechkit_split_word_upsells_keeps_explicit_zero():
    value=daily_statement('Сегодня 0 чеков 0 до продаж выручка 0 р')
    assert value['values']['upsell_checks']=='0'


@pytest.mark.parametrize('message',['Можно увидеть запланированные посты?','Отложим услугу. Покажи текущий контент-план','Хочу посмотреть контент-план'])
def test_content_read_variants(message):
    from services.operator_core import _content_read_request
    assert _content_read_request(message)


def test_action_identity_uses_request_and_payload():
    from services.operator_core import _registered_capability_envelope
    from services.operator_chat_service import current_request_key
    args=dict(capability='communications.draft',business_id='b',user_id='u',channel='web',message='Придумай извинение',payload={'message':'Извините'})
    token=current_request_key.set('request-one')
    try:
        first=_registered_capability_envelope(**args)
        assert _registered_capability_envelope(**args)['idempotency_key']==first['idempotency_key']
        current_request_key.set('request-two')
        assert _registered_capability_envelope(**args)['idempotency_key']!=first['idempotency_key']
        current_request_key.set('request-one')
        args['payload']={'message':'Другой текст'}
        assert _registered_capability_envelope(**args)['idempotency_key']!=first['idempotency_key']
    finally:current_request_key.reset(token)


def test_monthly_total_cannot_become_first_day_summary():
    from services.operator_finance_daily import aggregate_input,aggregate_result
    assert aggregate_input('За август 2026 выручка 9000 рублей, 60 чеков. Запиши итог месяца, по дням данных нет.')
    assert not aggregate_input('Покажи выручку за август')
    assert aggregate_result()['status']=='blocked'


@pytest.mark.parametrize('text',['За прошлый месяц выручка 9000 рублей. Запиши','За текущий месяц выручка 9000 рублей','Месячная выручка 9000 рублей, 60 чеков','Итоги августа: 9000 рублей','В августе выручка 9000 рублей. Сохрани'])
def test_month_aggregate_variants_never_become_daily(text):
    from services.operator_finance_daily import aggregate_input
    assert aggregate_input(text)

@pytest.mark.parametrize('text',['За 12 августа выручка 9000 рублей','Сегодня выручка 9000 рублей','Покажи месячную выручку'])
def test_daily_dates_and_month_reads_are_not_aggregate_write(text):
    from services.operator_finance_daily import aggregate_input
    assert not aggregate_input(text)


def test_singular_week_and_once_weekly():
    from services.operator_plan_schedule import extract
    assert len(extract('Создай план с 1 декабря 2026 на неделю, три поста в неделю')['dates'])==3
    assert len(extract('Создай план с 1 декабря 2026 на четыре недели, раз в неделю')['dates'])==4
