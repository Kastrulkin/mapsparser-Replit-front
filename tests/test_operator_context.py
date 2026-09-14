from services.operator_context import PlannerContext


def test_domain_words_and_lossless_request_local_references():
    tools=[{'name':'content.read'},{'name':'finance.read'},{'name':'work.context'}]
    assert PlannerContext('Сопоставь данные').tools(tools)==tools
    assert PlannerContext('Измени пост').tools(tools)==tools[:1]
    context=PlannerContext('Измени план')
    raw={'id':'abbd961a-273f-4f15-836e-33aacc0aa0e3','versions':['a'*64]}
    encoded=context.encode(raw)
    assert encoded['id']=='@ref1'
    assert context.decode(encoded)==raw
    assert PlannerContext('Другая команда').decode('@ref1')=='@ref1'


def test_original_requirement_not_cut_mid_block():
    from services.operator_tool_loop import _clean_history
    requirement='Сохрани прежние публикации. '+('Тема длинного задания. '*200)
    assert _clean_history([{'role':'user','content':requirement}])[0]['content']==requirement.strip()


def test_followup_keeps_short_answers_and_questions_in_current_topic():
    history=[{'role':'user','content':'Измени контент-план'},
             {'role':'assistant','content':'На сколько недель?'},
             {'role':'user','content':'На четыре'},
             {'role':'assistant','content':'С какой даты начать?'}]
    assert PlannerContext('Посты начиная с понедельника').history(history)==history


def test_topic_switch_excludes_old_clarification_but_keeps_current_exchange():
    history=[{'role':'user','content':'Запиши выручку'},
             {'role':'assistant','content':'Укажите валюту'},
             {'role':'user','content':'Лучше измени контент-план'},
             {'role':'assistant','content':'Сколько публикаций?'},
             {'role':'user','content':'Четыре'}]
    assert PlannerContext('Посты про путешествия').history(history)==history[2:]


def test_negated_revision_is_not_a_deterministic_mutation():
    from services.operator_plan_revision import explicit_schedule
    assert explicit_schedule('Не меняй план: один пост в неделю, два про Таиланд') is None
    assert explicit_schedule('Не изменяй план: один пост в неделю, два про Таиланд') is None
    assert explicit_schedule('Расскажи, как изменить план: один пост в неделю, два про Таиланд') is None


def test_question_and_negation_variants_use_normal_interpretation():
    from services.operator_plan_revision import explicit_schedule
    for prefix in ['Если изменить','Как изменить','Можно ли изменить','Не перерабатывай','Расскажи, как изменить']:
        assert explicit_schedule(prefix+' план: один пост в неделю, два про Таиланд') is None
    assert explicit_schedule('Пожалуйста, измени план: один пост в неделю, два про Таиланд')['post_count']==2


def test_finance_switch_does_not_retain_old_content_answers():
    history=[{'role':'user','content':'Измени посты'}, {'role':'assistant','content':'Сколько?'},
             {'role':'user','content':'Четыре'}, {'role':'user','content':'Запиши выручку'},
             {'role':'assistant','content':'В какой валюте?'}]
    assert PlannerContext('Расходы тоже запиши').history(history)==history[-2:]
