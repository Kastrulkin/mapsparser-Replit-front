import pytest
from services.operator_plan_schedule import extract
from services.operator_plan_continuation import PlanClarification
from services.operator_followups import directed_note


def test_exact_weekly_dates_and_distribution():
    value=extract('Подготовь новый контент-план с 1 ноября 2026 на четыре недели: один пост в неделю, два про Таиланд, один про Китай, один про Танзанию. Старый план не удаляй.')
    assert value['dates']==['2026-11-01','2026-11-08','2026-11-15','2026-11-22']
    assert value['period_days']==28
    assert [g['value'] for g in value['groups']]==[2,1,1]


@pytest.mark.parametrize('text',[
    'С 1 ноября 2026 на четыре недели один пост в неделю, три про Таиланд',
    'Один пост в неделю на четыре недели',
    'С 31 ноября 2026 на четыре недели один пост в неделю',
])
def test_inconsistent_schedule_requires_question(text):
    with pytest.raises(PlanClarification):extract(text)


@pytest.mark.parametrize('text,category',[
    ('Клиентка была недовольна, что её плохо встретили. Передай руководителю.', 'complaint'),
    ('Пожелание клиента: присылать номер машины заранее. Передай администратору.', 'wish'),
    ('Срочно: есть идея — проверять табличку. Передай руководителю и администратору.', 'idea'),
])
def test_addressed_note_is_exact_quote(text,category):
    assert directed_note(text)=={'quote':text,'category':category,'outcome':'note'}


@pytest.mark.parametrize('text',[
    'Если клиентка недовольна, передай руководителю?',
    'Не сохраняй пожелание клиента, передай руководителю',
    'Клиент недоволен. Передай руководителю и верни деньги',
])
def test_ambiguous_or_mixed_does_not_autosave(text):
    assert directed_note(text) is None


def test_greeting_cannot_complete_a_write_command():
    from services.operator_tool_loop import run_operator_tool_loop
    calls=[]
    def planner(state):
        calls.append(state)
        return {'action':'final','message':'Здравствуйте! Чем помочь?'}
    result=run_operator_tool_loop(business_id='b',user_id='u',message='Придумай вместо него пост',tools=[],planner=planner)
    assert result['status']=='blocked'
    assert result['planner_failed'] is True
    assert len(calls)==2


def test_real_speechkit_transcript_without_punctuation():
    value=extract('С 1 ноября 2026 года на 4 недели 1 пост в неделю 2 про таиланд 1 про китай 1 про танзанию')
    assert value['dates']==['2026-11-01','2026-11-08','2026-11-15','2026-11-22']
    assert [g['value'] for g in value['groups']]==[2,1,1]
    assert [g['label'] for g in value['groups']]==['таиланд','китай','танзанию']


def test_explicit_dates_without_frequency_are_not_silently_ignored():
    with pytest.raises(PlanClarification,match='часто'):
        extract('Создай 4 поста с 1 ноября 2026 на четыре недели')


def test_one_post_dative_form():
    value=extract('Контент-план с 1 ноября 2026 на четыре недели, по одному посту в неделю')
    assert len(value['dates'])==4
