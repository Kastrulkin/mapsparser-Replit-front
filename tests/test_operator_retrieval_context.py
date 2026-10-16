import json
import pytest
from services.operator_context import PlannerContext
from services.operator_tool_loop import run_operator_tool_loop
from services import knowledge_retrieval
from services.knowledge_retrieval import KnowledgeHit, KnowledgeSearchRequest


def test_catalog_keeps_all_actions_and_input_constraints_but_not_response_schemas():
    schema={'type':'object','required':['id'],'properties':{'id':{'type':'string'},'operation':{'enum':['preview','start']}}}
    tool={'name':'partnerships.continue_outreach','description':'Запуск отдельно подтверждается.','input_schema':schema,'output_schema':{'huge':['x']*500},'scope':{'business_id':'x'},'risk_class':'write','approval_required':True}
    compact=PlannerContext('Найди и создай автоматизацию').tools([tool])
    assert compact[0]['input_schema']==schema
    assert compact[0]['description']==tool['description']
    assert compact[0]['name']==tool['name'] and compact[0]['approval_required']
    assert 'output_schema' not in compact[0] and 'output_schema' in tool
    assert len(json.dumps(compact)) < len(json.dumps([tool]))/2


def test_public_search_cannot_read_private_documents_even_in_current_business():
    sql,params=knowledge_retrieval._filters(KnowledgeSearchRequest('business','query','localos_content',public_only=True))
    assert "document.sensitivity_class IN ('public','shared_deidentified')" in sql
    assert "source.visibility NOT IN ('private','invite')" in sql
    assert params[1]=='business'


def test_active_operator_search_supplies_real_text_even_when_global_mode_is_shadow(monkeypatch):
    monkeypatch.setattr(knowledge_retrieval,'_enabled',lambda:True)
    monkeypatch.setattr(knowledge_retrieval,'_business_allowed',lambda *_:True)
    monkeypatch.setattr(knowledge_retrieval,'_shadow_enabled',lambda:True)
    hit=KnowledgeHit('doc','chunk','source','Подтверждённый факт','https://example.com/evidence')
    requests=[]
    def retrieve(conn,request):
        requests.append(request)
        return {'hits':[hit],'mode':'lexical','event_id':''}
    monkeypatch.setattr(knowledge_retrieval,'retrieve_knowledge',retrieve)
    text,meta=knowledge_retrieval.semantic_context_for_connection(object(),business_id='business',query='факт',purpose='localos_content',consumer='operator_planner',use_in_prompt=True,public_only=True,max_chars=500,limit=4)
    assert 'Подтверждённый факт' in text and hit.permalink in text
    assert meta['retrieval_shadow'] is False
    assert requests[0].public_only and requests[0].limit==4
    shadow_text,_=knowledge_retrieval.semantic_context_for_connection(object(),business_id='business',query='факт',purpose='localos_content',consumer='other')
    assert shadow_text==''


def test_bounded_context_keeps_complete_source_link_and_correct_provenance():
    hit=KnowledgeHit('d1','c1','s','факт '*200,'https://example.com/'+'a'*80)
    second=KnowledgeHit('d2','c2','s','второй факт','https://example.com/second')
    text,meta=knowledge_retrieval.retrieval_context({'hits':[hit,second]},max_chars=500)
    assert len(text)<=500 and text.endswith(hit.permalink)
    assert meta['knowledge_document_ids']==['d1']


def test_knowledge_query_is_retrieved_once_before_planning_and_put_in_prompt():
    calls=[]
    def search(args):
        calls.append(args)
        return {'status':'completed','context':'Факт. Источник: https://example.com/evidence','retrieval':{'retrieval_shadow':False}}
    tool={'name':'knowledge.search','risk_class':'read_only','input_schema':{'type':'object','properties':{'query':{'type':'string'}}},'execute':search}
    def planner(state):
        assert 'https://example.com/evidence' in state['observations'][0]['context']
        return {'action':'final','message':'Факт: https://example.com/evidence'}
    result=run_operator_tool_loop(business_id='b',user_id='u',message='Найди в базе знаний рекомендации',tools=[tool],planner=planner)
    assert len(calls)==1 and result['retrieval']['retrieval_shadow'] is False
    assert result['external_writes_performed'] is False


def test_denied_retrieval_never_calls_model():
    def denied(*_):raise PermissionError()
    tool={'name':'knowledge.search','risk_class':'read_only','execute':denied}
    result=run_operator_tool_loop(business_id='b',user_id='u',message='Найди в базе знаний',tools=[tool],planner=lambda *_:pytest.fail('Must stop before model'))
    assert result['status']=='blocked'


def test_embedding_budget_counts_input_and_settles_prompt_only_usage(monkeypatch):
    from services import ai_spend_budget
    short=ai_spend_budget.reservation_tokens({'input':['a'],'max_tokens':1})
    long=ai_spend_budget.reservation_tokens({'input':['a'*3000],'max_tokens':1})
    assert long-short==2999
    assert ai_spend_budget.limits('gigachat_embeddings')['daily_tokens']==100000
    settled=[]
    monkeypatch.setattr(ai_spend_budget,'reserve',lambda *_:'r')
    monkeypatch.setattr(ai_spend_budget,'settle',lambda *a:settled.append(a))
    class Response:
        status_code=200
        def json(self):return {'usage':{'prompt_tokens':25}}
    ai_spend_budget.guarded_post(Response,{'input':['test'],'max_tokens':1})
    assert settled[-1][1:3]==('completed',25)


def test_active_retrieval_event_records_use_instead_of_global_shadow(monkeypatch):
    monkeypatch.setattr(knowledge_retrieval,'_enabled',lambda:True)
    monkeypatch.setattr(knowledge_retrieval,'_business_allowed',lambda *_:True)
    monkeypatch.setattr(knowledge_retrieval,'_shadow_enabled',lambda:True)
    hit=KnowledgeHit('doc','chunk','s','Факт из базы','https://example.com/fact')
    monkeypatch.setattr(knowledge_retrieval,'retrieve_knowledge',lambda *_:{'hits':[hit],'event_id':'event','mode':'lexical'})
    updates=[]
    class Connection:
        def cursor(self):return self
        def execute(self,sql,params):updates.append(params[0].adapted)
        def close(self):pass
    text,meta=knowledge_retrieval.semantic_context_for_connection(Connection(),business_id='b',query='q',purpose='localos_content',consumer='operator_planner',use_in_prompt=True,public_only=True)
    assert text and meta['retrieval_shadow'] is False
    assert updates==[{'shadow':False,'used_in_prompt':True,'context_chars':len(text),'public_only':True}]


def test_explicit_public_operator_search_works_outside_old_pilot_but_private_does_not(monkeypatch):
    monkeypatch.setattr(knowledge_retrieval,'_enabled',lambda:True)
    monkeypatch.setattr(knowledge_retrieval,'_business_allowed',lambda *_:False)
    monkeypatch.setattr(knowledge_retrieval,'_shadow_enabled',lambda:True)
    hit=KnowledgeHit('d','c','s','Публичный проверенный факт','https://example.com')
    monkeypatch.setattr(knowledge_retrieval,'retrieve_knowledge',lambda *_:{'hits':[hit],'mode':'lexical','event_id':''})
    text,meta=knowledge_retrieval.semantic_context_for_connection(object(),business_id='new-business',query='query',purpose='localos_content',consumer='operator_planner',use_in_prompt=True,public_only=True)
    assert text and meta['retrieval_shadow'] is False
    private,_=knowledge_retrieval.semantic_context_for_connection(object(),business_id='new-business',query='query',purpose='localos_content',consumer='other',use_in_prompt=True)
    assert private==''


def test_full_user_question_has_a_subject_only_lexical_fallback():
    query='Какие рекомендации по оформлению карточки компании есть в базе знаний? Приведи источник. Ничего не меняй.'
    assert knowledge_retrieval._public_query_terms(query)==['оформлению','карточки']


def test_search_rechecks_actor_and_business_permission_before_retrieval(monkeypatch):
    from services import operator_knowledge_search
    calls=[]
    monkeypatch.setattr(operator_knowledge_search,'load_actor',lambda *_:calls.append('actor') or {'id':'u'})
    def denied(*_):
        calls.append('permission')
        raise PermissionError()
    monkeypatch.setattr(operator_knowledge_search,'require_permission',denied)
    monkeypatch.setattr(knowledge_retrieval,'semantic_context_for_cursor',lambda *_args,**_kwargs:pytest.fail('No retrieval before permission'))
    tool=operator_knowledge_search.knowledge_search_tool(object(),'b','u')
    pytest.raises(PermissionError,tool['execute'],{'query':'fact'})
    assert calls==['actor','permission']


def test_search_budget_scope_is_attributed_to_authorized_actor(monkeypatch):
    from services import operator_knowledge_search, ai_spend_budget
    monkeypatch.setattr(operator_knowledge_search,'load_actor',lambda *_:{'id':'u'})
    monkeypatch.setattr(operator_knowledge_search,'require_permission',lambda *_:None)
    seen=[]
    def retrieve(*_args,**_kwargs):
        seen.append(dict(ai_spend_budget._SCOPE.get()))
        return 'Факт. Источник: https://example.com',{'retrieval_shadow':False}
    monkeypatch.setattr(knowledge_retrieval,'semantic_context_for_cursor',retrieve)
    result=operator_knowledge_search.knowledge_search_tool(object(),'b','u')['execute']({'query':'fact'})
    assert result['status']=='completed'
    assert seen[0]['user_id']=='u' and seen[0]['business_id']=='b'
    assert not ai_spend_budget._SCOPE.get()


def test_embedding_budget_pause_preserves_jobs_instead_of_exhausting_retries(monkeypatch):
    from services import knowledge_embeddings,ai_spend_budget
    monkeypatch.setattr(knowledge_embeddings,'_enabled',lambda:True)
    monkeypatch.setattr(knowledge_embeddings,'_claim_jobs',lambda *_:[{'id':'j','chunk_id':'c','attempt_count':4,'chunk':{'content_text':'text'}}])
    monkeypatch.setattr(knowledge_embeddings.GigaChatEmbeddingClient,'embedding_balance',lambda *_:None)
    def denied(*_):raise ai_spend_budget.BudgetDenied('cap')
    monkeypatch.setattr(knowledge_embeddings.GigaChatEmbeddingClient,'embed',denied)
    sql=[]
    class Connection:
        def cursor(self):return self
        def execute(self,query,params):sql.append(query)
        def close(self):pass
    result=knowledge_embeddings.process_embedding_jobs(Connection())
    assert result['status']=='budget_guard'
    assert "status='queued'" in sql[0] and 'attempt_count-1' in sql[0]
    assert "status='pending'" in sql[1]
    assert not any('dead_letter' in query for query in sql)
