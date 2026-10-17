import copy
import importlib.util
import json
import pytest
from services import content_plan_service as service
from services.content_generation_options import candidate_instruction, merge_alternatives
from services.llm.registry import get_task_definition


class Database:
    def __init__(self):
        self.item = {'id':'item','plan_id':'plan','business_id':'business','root_business_id':'business','theme':'Новая услуга','goal':'Объяснить услугу','source_ref':'Услуга','draft_text':'Сохранённый основной текст.','status':'edited','metadata_json':{'generation_source':'manual','other_feature':{'keep':True}}}
        self.statements=[];self.commits=0
        self.conn=self
    def cursor(self):return self
    def execute(self,sql,args=None):
        self.statements.append((sql,args))
        if sql.startswith('UPDATE contentplanitems SET metadata_json = jsonb_set'):
            self.item['metadata_json']['content_generation_v2']=json.loads(args[0])
    def fetchone(self):
        sql=self.statements[-1][0]
        if 'SELECT i.id' in sql:return copy.deepcopy(self.item)
        if 'SELECT name, city' in sql:return {'name':'Пример','description':'Описание','site':'','website':''}
        if 'is_superadmin' in sql:return {'coalesce':False}
        return None
    def fetchall(self):return []
    def commit(self):self.commits+=1
    def rollback(self):pass
    def close(self):pass


@pytest.fixture
def generation(monkeypatch):
    db=Database();calls=[]
    monkeypatch.setattr(service,'DatabaseManager',lambda:db)
    monkeypatch.setattr(service,'ensure_content_plan_tables',lambda *_:None)
    monkeypatch.setattr(service,'get_business_owner_id',lambda *_:'owner')
    for name,value in [('_content_plan_business_facts',{'name':'Пример','description':'Описание'}),('_load_content_plan_service_sources',[]),('_load_content_plan_service_facts',''),('load_active_industry_patterns',[]),('_load_business_content_evidence',[]),('_load_editorial_pattern_library',[]),('load_content_voice_context',{}),('_resolve_scope_target_meta',{})]:
        if hasattr(service,name):
            monkeypatch.setattr(service,name,lambda *_, _value=value, **__:copy.deepcopy(_value))
    monkeypatch.setattr(service,'_content_plan_knowledge_context',lambda *_:('',{}))
    monkeypatch.setattr(service,'_content_generation_v2_enabled',lambda:True)
    monkeypatch.setattr(service,'_build_content_brief_v1',lambda *_:{'complete':True,'sources':[{'id':'fact','fact':'Подтверждённая услуга.'}],'confirmed_details':['Подтверждённая услуга.']})
    if importlib.util.find_spec('services.business_knowledge'):
        monkeypatch.setattr('services.business_knowledge.context',lambda *_:{'text':'','sources':[],'revision':1})
    if importlib.util.find_spec('services.operator_editorial'):
        monkeypatch.setattr('services.operator_editorial.editorial_prompt',lambda *_:'')
    if importlib.util.find_spec('services.operator_editorial'):
        monkeypatch.setattr('services.operator_editorial.editorial_evidence',lambda *_:[])
    if importlib.util.find_spec('services.content_rules'):
        monkeypatch.setattr('services.content_rules.enforce',lambda _cursor,_business,_user,text,*_:text)
    monkeypatch.setattr(service,'_score_content_candidate',lambda candidate,*_:{**candidate,'quality_passed':True,'score':80})
    monkeypatch.setattr(service,'_looks_like_ice_rink_hallucination',lambda *_:False)
    monkeypatch.setattr(service,'_content_plan_draft_needs_fallback',lambda *_:False)
    monkeypatch.setattr(service,'_record_content_plan_event',lambda **_:None)
    monkeypatch.setattr(service,'get_content_plan',lambda *_:{'id':'plan','items':[copy.deepcopy(db.item)]})
    def generate(prompt,**kwargs):
        calls.append((prompt,kwargs)); count=2 if 'ровно два новых' in prompt else 1
        return json.dumps({'candidates':[{'id':f'variant-{i}','angle':f'Подход {i}','text':f'Новый подтверждённый текст {i}.','used_fact_ids':['fact'],'unsupported_facts':[]} for i in range(count)]})
    monkeypatch.setattr(service,'analyze_text_with_gigachat',generate)
    return db,calls


def test_one_candidate_default_and_two_only_on_explicit_request():
    assert 'ровно один' in candidate_instruction()
    assert 'ровно два новых' in candidate_instruction(2,'Старый текст')
    for count in (0,3,10):
        with pytest.raises(ValueError):candidate_instruction(count)


def test_default_generator_requests_only_one(generation):
    db,calls=generation
    result=service.generate_draft_for_plan_item('owner','item')
    assert len(calls)==1 and 'ровно один вариант' in calls[0][0]
    assert result['generation']['success']
    assert len(result['generation']['alternatives'])==1


def test_additional_variants_preserve_text_status_metadata_and_reuse_request(generation):
    db,calls=generation; original=copy.deepcopy(db.item)
    kwargs={'additional_variants':True,'expected_draft_text':original['draft_text'],'request_id':'request-1'}
    first=service.generate_draft_for_plan_item('owner','item',**kwargs)
    assert first['generation']['preserved_current_draft'] and len(first['generation']['alternatives'])==2
    assert db.item['draft_text']==original['draft_text'] and db.item['status']==original['status']
    assert db.item['metadata_json']['other_feature']==original['metadata_json']['other_feature']
    assert len(calls)==1 and 'ровно два новых' in calls[0][0]
    updates=[sql for sql,args in db.statements if sql.lstrip().startswith('UPDATE')]
    assert len(updates)==1 and 'SET metadata_json' in updates[0] and 'draft_text =' not in updates[0]
    again=service.generate_draft_for_plan_item('owner','item',**kwargs)
    assert again['generation']['success'] and len(calls)==1


def test_stale_or_unauthorized_request_never_calls_model(generation):
    db,calls=generation
    with pytest.raises(service.ContentPlanItemConflict):
        service.generate_draft_for_plan_item('owner','item',additional_variants=True,expected_draft_text='Устаревший текст',request_id='r1')
    with pytest.raises(PermissionError):
        service.generate_draft_for_plan_item('other','item',additional_variants=True,expected_draft_text=db.item['draft_text'],request_id='r2')
    assert calls==[]


def test_failed_additional_generation_preserves_everything(generation,monkeypatch):
    db,calls=generation;original=copy.deepcopy(db.item)
    monkeypatch.setattr(service,'analyze_text_with_gigachat',lambda *_a,**_k:'not json')
    result=service.generate_draft_for_plan_item('owner','item',additional_variants=True,expected_draft_text=db.item['draft_text'],request_id='r')
    assert result['generation']['success'] is False and db.item==original
    assert not any(sql.lstrip().startswith('UPDATE') for sql,args in db.statements)


def test_merge_keeps_selected_id_bounds_history_and_does_not_fabricate_review():
    item={'draft_text':'Ручной текст','metadata_json':{'content_generation_v2':{'selected_variant_id':'old','variants':[{'id':'old','text':'Прежний вариант','quality_passed':True}]}}}
    before=copy.deepcopy(item)
    meta,added=merge_alternatives(item,[{'id':'variant-1','text':'Новый','quality_passed':True}],'request')
    assert item==before and meta['selected_variant_id']=='old'
    assert meta['variants'][0]['id']=='old' and added[0]['id']!='variant-1'
    assert not any(v['text']=='Ручной текст' for v in meta['variants'])


@pytest.mark.parametrize('task',['news_generation','content_plan_generation_v2'])
def test_copy_route_explicitly_disables_reasoning_without_changing_provider(task):
    definition=get_task_definition(task)
    assert definition.thinking_enabled is False and definition.primary_provider=='gigachat'
    if task=='content_plan_generation_v2':
        schema=definition.response_schema['properties']['candidates']
        assert schema['minItems']==1 and schema['maxItems']==2


@pytest.mark.parametrize('task',['news_generation','content_plan_generation_v2'])
def test_actual_deepseek_payload_disables_thinking(task,monkeypatch):
    from services.llm import adapters
    from services.llm.contracts import LLMTaskRequest
    calls=[]
    class Response:
        status_code=200
        def raise_for_status(self):pass
        def json(self):return {'choices':[{'message':{'content':'{"candidates":[]}'},'finish_reason':'stop'}],'usage':{'prompt_tokens':10,'completion_tokens':10,'total_tokens':20}}
    def post(*args,**kwargs):calls.append(kwargs['json']);return Response()
    monkeypatch.setenv('DEEPSEEK_API_KEY','synthetic-key')
    monkeypatch.setattr(adapters.requests,'post',post)
    result=adapters.DeepSeekAdapter().generate(LLMTaskRequest(task_key=task,prompt='Return JSON'),get_task_definition(task),prompt='Return JSON')
    assert result.status=='completed'
    assert len(calls)==1 and calls[0]['thinking']=={'type':'disabled'}


def test_generate_route_requires_explicit_boolean_and_stale_conflict(monkeypatch):
    from flask import Flask
    from api import content_plans_api
    app=Flask(__name__);app.register_blueprint(content_plans_api.content_plans_bp)
    monkeypatch.setattr(content_plans_api,'_require_auth',lambda:({'user_id':'owner'},None))
    calls=[]
    def generate(*args,**kwargs):calls.append(kwargs);return {'plan':{},'generation':{'success':True}}
    monkeypatch.setattr(content_plans_api,'generate_draft_for_plan_item',generate)
    client=app.test_client()
    assert client.post('/api/content-plans/items/item/generate-draft',json={'additional_variants':'false'}).status_code==400
    assert client.post('/api/content-plans/items/item/generate-draft',json={'additional_variants':True}).status_code==400
    assert calls==[]
    assert client.post('/api/content-plans/items/item/generate-draft',json={'language':'ru'}).status_code==200
    assert 'additional_variants' not in calls[0]
    assert client.post('/api/content-plans/items/item/generate-draft',json={'additional_variants':True,'expected_draft_text':'Текст','request_id':'r'}).status_code==200
    assert calls[-1]['additional_variants'] is True
    def stale(*_a,**_k):raise service.ContentPlanItemConflict('Изменилось')
    monkeypatch.setattr(content_plans_api,'generate_draft_for_plan_item',stale)
    assert client.post('/api/content-plans/items/item/generate-draft',json={'additional_variants':True,'expected_draft_text':'Текст','request_id':'r'}).status_code==409
