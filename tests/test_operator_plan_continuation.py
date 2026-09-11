from datetime import date
import pytest
from services.operator_plan_continuation import resolve_continuation, PlanClarification
from services import operator_core
from core.content_plan_generator import build_content_plan_skeleton

COMMAND = '12 го заканчивается подготовленный контент план — нужен следующий, сделай, старый не удаляй'

class Cursor:
    def __init__(self, plan=None):
        self.plan=plan
        self.calls=[]
    def execute(self, sql, params): self.calls.append((sql,params))
    def fetchone(self): return self.plan
    def fetchall(self): return [{'theme':'Старая тема'}]


def test_continuation_uses_actual_shifted_last_item_and_preserves_source():
    cursor=Cursor({'id':'old','period_end':date(2026,9,5),'last_date':date(2026,9,12),'generated_plan_json':{'selected_channels':['google_business']}})
    request=resolve_continuation(cursor,'b',COMMAND)
    assert request['period_start']==date(2026,9,13)
    assert request['previous_plan_id']=='old'
    assert request['excluded_themes']==['Старая тема']
    assert request['channels']==['google_business']
    assert all(sql.startswith('SELECT') for sql,_ in cursor.calls)
    assert all('b' in params for _,params in cursor.calls)


@pytest.mark.parametrize('plan', [None, {'id':'old','last_date':date(2026,9,18)}])
def test_missing_or_conflicting_plan_asks_before_generation(plan):
    with pytest.raises(PlanClarification): resolve_continuation(Cursor(plan),'b',COMMAND)


@pytest.mark.parametrize('channel', ['telegram','web','telegram_mini_app'])
def test_real_voice_phrase_passes_continuation_and_request_key(monkeypatch,channel):
    from services import content_plan_service
    calls=[]
    monkeypatch.setattr(content_plan_service,'create_generated_content_plan',lambda *a,**kw: calls.append(kw) or {'id':'new','period_start':'2026-09-13','period_end':'2026-10-12'})
    result,_=operator_core.route_operator_message(None,business_id='b',user_id='u',message=COMMAND,channel=channel,action_payload={'request_id':'voice:a'})
    assert result['status']=='completed'
    assert calls[0]['continuation_message']==COMMAND
    assert calls[0]['operator_request_id']=='voice:a'
    assert 'Старые планы сохранены' in result['chat_response']


def test_generator_excludes_old_titles_and_does_not_repeat_to_fill():
    context={'business':{'name':'Riderra'},'excluded_plan_themes':['Подсветить услугу: Трансфер'], 'services':[{'id':'s','name':'Трансфер'}]}
    plan=build_content_plan_skeleton(context,period_days=30,density='standard',period_start=date(2026,9,13))
    themes=[item['theme'] for item in plan['items']]
    assert 'Подсветить услугу: Трансфер' not in themes
    assert len(themes)==len(set(themes))
    assert all('2026-09-13'<=item['scheduled_for']<='2026-10-12' for item in plan['items'])


def test_continuation_intent_requires_a_request():
    assert operator_core._is_content_plan_intent('Продолжи контент-план')
    assert operator_core._is_content_plan_intent(COMMAND)
    assert not operator_core._is_content_plan_intent('Подготовленный контент план заканчивается')
    assert not operator_core._is_content_plan_intent('Не создавай контент план')


@pytest.mark.parametrize('message', ['12-го сентября 2026 заканчивается контент план', 'Контент план заканчивается 12 сентября'])
def test_spoken_end_date_in_both_orders(message):
    result=resolve_continuation(Cursor({'id':'old','last_date':date(2026,9,12)}),'b',message)
    assert result['period_start']==date(2026,9,13)


def test_wrong_month_is_not_silently_ignored():
    with pytest.raises(PlanClarification):
        resolve_continuation(Cursor({'id':'old','last_date':date(2026,9,12)}),'b','12 октября заканчивается план')
