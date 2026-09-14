import json
import pytest
from services import content_plan_direction
from services.operator_plan_continuation import PlanClarification


def skeleton():
    return {'items': [{'scheduled_for': f'2026-10-{i+1:02d}'} for i in range(10)], 'meta': {}}


def response(mode, value, count):
    groups = [{'label': 'Азия осенью и зимой', 'mode': mode, 'value': value}]
    if count < 10: groups.append({'label': 'Другие темы трансферов', 'mode': 'remainder', 'value': None})
    return {'groups': groups, 'items': [{'group': 0 if i < count else 1, 'theme': f'Тема {i}', 'goal': 'Совет клиенту'} for i in range(10)]}


@pytest.mark.parametrize('mode,value,count', [('all',None,10),('count',3,3),('percent',40,4),('part',None,5)])
def test_allocations_preserve_dates_and_original_brief(monkeypatch,mode,value,count):
    prompts=[]
    def generate(prompt,*args):
        prompts.append(prompt);return json.dumps(response(mode,value,count))
    monkeypatch.setattr(content_plan_direction,'_generate',generate)
    plan=skeleton();dates=[item['scheduled_for'] for item in plan['items']]
    result=content_plan_direction.apply_direction(plan,{'business':{'name':'Riderra'}},'Таиланд Китай Япония Корея, осень зима','b','u')
    assert result['meta']['editorial_counts'][0] == count
    assert result['meta']['editorial_brief'] in prompts[0]
    assert [item['scheduled_for'] for item in result['items']] == dates
    assert all(item['source_kind']=='editorial_brief' for item in result['items'])
    assert sum(len(items) for items in result['weekly_groups'].values())==10


@pytest.mark.parametrize('failure', ['bad_json','allocation','audit','duplicate','provider'])
def test_invalid_generation_never_becomes_success(monkeypatch,failure):
    data=response('count',3,3)
    if failure=='allocation': data['groups'][0]['value']=4
    if failure=='audit': data['items'][0]['theme']='Не заполнены контакты карточки'
    if failure=='duplicate': data['items'][1]['theme']=data['items'][0]['theme']
    def generate(*args):
        if failure=='provider': raise RuntimeError('unavailable')
        return 'bad' if failure=='bad_json' else json.dumps(data)
    monkeypatch.setattr(content_plan_direction,'_generate',generate)
    plan=skeleton()
    with pytest.raises(PlanClarification):content_plan_direction.apply_direction(plan,{},'3 поста про Азию','b','u')
    assert all('theme' not in item for item in plan['items'])
