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
