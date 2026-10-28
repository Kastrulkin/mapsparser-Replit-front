import pytest
from services import finance_period, finance_daily
from tests.test_finance_daily_pg import daily
from tests.test_operator_voice_pg import pg

@pytest.mark.parametrize('message,expected', [
 ('За сентябрь 2026', ('2026-09-01','2026-09-30')),
 ('За февраль 2024', ('2024-02-01','2024-02-29')),
 ('За май 2026', ('2026-05-01','2026-05-31')),
 ('За июнь 2026', ('2026-06-01','2026-06-30')),
 ('С 19 по 25 октября 2026', ('2026-10-19','2026-10-25')),
 ('С 2026-10-19 по 2026-10-25', ('2026-10-19','2026-10-25')),
 ('С 19.10.2026 по 25.10.2026', ('2026-10-19','2026-10-25')),
])
def test_explicit_period(message,expected): assert finance_period.dates(message)==expected

@pytest.mark.parametrize('message', ['За неделю','За октябрь','С 2026-10-19','С 2026-10-25 по 2026-10-19','За февраль 2026 с 30 по 31 февраля 2026','За максимум 2026','С 2024-01-01 по 2026-01-01'])
def test_ambiguous_or_invalid_period_is_not_guessed(message):
    with pytest.raises(ValueError):finance_period.dates(message)

@pytest.mark.parametrize('spoken,currency,revenue', [('500 000 рублей','RUB','500000'),('пятьдесят тысяч евро','EUR','50000'),('1000,50 USD','USD','1000.50')])
def test_spoken_values(spoken,currency,revenue):
    args=finance_period.spoken_values('За сентябрь 2026 выручка '+spoken+', 200 чеков, 40 чеков с допродажей, возвраты 1000')
    assert args['currency']==currency
    assert finance_daily.checked_values(args['values'])=={'revenue':revenue,'refunds':'1000','checks':'200','upsell_checks':'40'}

@pytest.mark.parametrize('message',['Выручка 500 рублей и 50 евро','Выручка -500 рублей','Выручка 500-600 рублей','Выручка 300 рублей, выручка 400 рублей','Выручка 500 рублей, 20 чеков, 30 чеков с допродажей'])
def test_unsafe_values_rejected(message):
    with pytest.raises(ValueError):finance_daily.checked_values(finance_period.spoken_values(message)['values'])


def period(c,**extra):
    return finance_period.prepare(c,'b','u',{'period_start':'2026-09-01','period_end':'2026-09-30','currency':'EUR','values':{'revenue':50000,'checks':200,'upsell_checks':40},**extra},'max_bot','qa')


def test_preview_then_apply_replay_and_read_never_creates_days(daily):
    conn,c=daily;envelope=period(c)
    assert not finance_period.read(c,'b','2026-09-01','2026-09-30')
    first=finance_daily.apply(c,'b','u',envelope,'period-action');conn.commit()
    assert finance_daily.apply(c,'b','u',envelope,'period-action')==first
    report=finance_daily.read_period(c,'b','2026-09-01','2026-09-30')
    assert report['currencies']=={} and report['days']==[]
    assert report['reported_period_totals'][0]['values_json']['revenue']=='50000'
    c.execute('SELECT COUNT(*) n FROM financialtransactions');assert c.fetchone()['n']==0
    c.execute('SELECT COUNT(*) n FROM finance_daily_summaries');assert c.fetchone()['n']==0
    c.execute('SELECT COUNT(*) n FROM finance_daily_events');assert c.fetchone()['n']==1


def test_correction_stale_preview_and_cross_business(daily):
    _,c=daily;first=period(c);stale=period(c,values={'revenue':60000})
    finance_daily.apply(c,'b','u',first,'a')
    with pytest.raises(ValueError,match='изменился'):finance_daily.apply(c,'b','u',stale,'b')
    with pytest.raises(PermissionError):finance_daily.apply(c,'foreign','u',first,'c')
    corrected=period(c,values={'revenue':60000})
    assert 'заменит' in finance_period.preview(corrected)
    finance_daily.apply(c,'b','u',corrected,'d')
    saved=finance_period.read(c,'b','2026-09-01','2026-09-30')
    assert len(saved)==1 and saved[0]['version']==2 and saved[0]['values_json']['revenue']=='60000'


def test_daily_period_and_currencies_never_added_together(daily):
    _,c=daily
    day=finance_daily.prepare(c,'b','u',{'kind':'daily','date':'2026-09-12','currency':'EUR','values':{'revenue':100}},'telegram','day')
    finance_daily.apply(c,'b','u',day,'day')
    finance_daily.apply(c,'b','u',period(c),'month-eur')
    finance_daily.apply(c,'b','u',period(c,currency='RUB'),'month-rub')
    report=finance_daily.read_period(c,'b','2026-09-01','2026-09-30')
    assert report['currencies']['EUR']['revenue']==100
    assert len(report['reported_period_totals'])==2
    assert {row['currency'] for row in report['reported_period_totals']}=={'EUR','RUB'}

@pytest.mark.parametrize('channel',['telegram','max_bot','telegram_mini_app','max_mini_app'])
def test_same_monthly_message_routes_to_identical_review_without_model(daily,monkeypatch,channel):
    from services import operator_core,operator_finance_daily,work_journal
    _,c=daily
    monkeypatch.setattr(work_journal,'enabled',lambda b:False)
    monkeypatch.setattr(operator_core,'operator_subscription_block',lambda *a:None)
    seen=[]
    def review(**kwargs):
        seen.append(kwargs['payload']);return {'status':'approval_required','approval':{'action_id':'qa'}}
    monkeypatch.setattr(operator_core,'_prepare_registered_capability_approval',review)
    out,_=operator_core.route_operator_message(c,business_id='b',user_id='u',message='За сентябрь 2026 выручка 50 000 евро, 200 чеков, 40 чеков с допродажей',channel=channel)
    assert out['status']=='approval_required' and len(seen)==1
    assert seen[0]['kind']=='period' and seen[0]['period_start']=='2026-09-01' and seen[0]['data']['revenue']=='50000'
    assert 'не прибавляется' in out['chat_response']


def test_monthly_read_shows_saved_period_without_daily_sum(daily):
    from services import operator_finance_daily
    _,c=daily
    finance_daily.apply(c,'b','u',period(c),'month')
    result=operator_finance_daily.read(c,'b','u',{'start':'2026-09-01','end':'2026-09-30'})
    assert '50000' in result['chat_response'] and 'не прибавляется' in result['chat_response']
    assert result['financial_daily']['currencies']=={}


def test_gross_qualifier_is_not_mistaken_for_refund_amount():
    values=finance_period.spoken_values('За сентябрь 2026 выручка до возвратов 50000 рублей, 20 чеков')['values']
    assert values['revenue']=='50000' and 'refunds' not in values


def test_net_revenue_requires_explicit_refunds_and_unknown_is_not_zero():
    with pytest.raises(ValueError):finance_period.spoken_values('За сентябрь 2026 выручка после возвратов 50000 рублей')
    values=finance_period.spoken_values('За сентябрь 2026 выручка 50000 рублей, расходы пока не знаю')['values']
    assert values['expenses'] is None and values['revenue']=='50000'


def test_dashboard_exact_month_uses_reported_total_once_and_never_prorates(daily):
    _,c=daily
    day=finance_daily.prepare(c,'b','u',{'kind':'daily','date':'2026-09-12','currency':'EUR','values':{'revenue':100}},'telegram','day')
    finance_daily.apply(c,'b','u',day,'day')
    finance_daily.apply(c,'b','u',period(c),'month')
    month=finance_daily.read_period(c,'b','2026-09-01','2026-09-30')
    assert finance_daily.overlay_snapshot({},month)['kpis']['revenue']==50000
    subset=finance_daily.read_period(c,'b','2026-09-01','2026-09-12')
    assert finance_daily.overlay_snapshot({},subset)['kpis']['revenue']==100


def test_api_initial_view_keeps_period_total_without_timezone_or_daily_rows(daily,monkeypatch):
    from flask import Flask
    from api import finance_api
    conn,c=daily
    finance_daily.apply(c,'b','u',period(c),'month')
    c.execute('DELETE FROM business_finance_settings')
    class DB:
        def __init__(self):self.conn=conn
        def close(self):pass
    monkeypatch.setattr(finance_api,'DatabaseManager',DB)
    monkeypatch.setattr(finance_api,'_require_finance_user_and_business',lambda:({'user_id':'u'},'b',None))
    app=Flask(__name__);app.register_blueprint(finance_api.finance_bp)
    response=app.test_client().get('/api/finance/daily?business_id=b')
    assert response.status_code==200
    result=response.get_json()
    assert result['days']==[] and result['reported_period_totals'][0]['values_json']['revenue']=='50000'


def test_edit_before_confirmation_keeps_month_and_other_values(daily,monkeypatch):
    from services import operator_core,work_journal
    _,c=daily;draft=period(c)
    monkeypatch.setattr(work_journal,'enabled',lambda b:False)
    monkeypatch.setattr(operator_core,'operator_subscription_block',lambda *a:None)
    monkeypatch.setattr(operator_core,'_prepare_registered_capability_approval',lambda **kw:{'status':'approval_required','approval':{'action_id':'qa'}})
    result,pending=operator_core.route_operator_message(c,business_id='b',user_id='u',message='Нет, выручка 60000 евро',channel='max_bot',pending_context={'capability':'finance.period.input','draft':draft})
    assert result['financial_draft']['period_start']=='2026-09-01'
    assert result['financial_draft']['data']['revenue']=='60000'
    assert result['financial_draft']['data']['checks']=='200'
    assert pending['capability']=='finance.period.input'
