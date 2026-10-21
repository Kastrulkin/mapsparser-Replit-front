"""Regression: enabling team work must not block a selected partner."""
import json
import pytest
from services import operator_workday_router, work_journal

class Cursor:
    def __init__(self):
        self.context={'selected_object':{'type':'schedule','date':'2026-10-21'}}
    def execute(self, sql, args):
        if sql.startswith('UPDATE operatorconversations'):
            self.context=json.loads(args[0])
    def fetchone(self):
        return {'input_context_json':dict(self.context)}

@pytest.mark.parametrize('channel',['web','telegram','telegram_mini_app','max_bot','max_mini_app'])
def test_partner_is_delegated_without_stale_schedule(monkeypatch,channel):
    monkeypatch.setattr(work_journal,'scope',lambda *args:None)
    cursor=Cursor()
    payload={'selected_object':{'type':'partner','id':'chosen'},'channel':channel}
    result=operator_workday_router.input_context(cursor,'business','manager','conversation',payload)
    assert 'selected_object' not in result
    assert payload['selected_object']=={'type':'partner','id':'chosen'}
    assert 'selected_object' not in cursor.context

@pytest.mark.parametrize('selected',[{},'partner',{'type':'unknown'}])
def test_unknown_selection_still_rejected(monkeypatch,selected):
    monkeypatch.setattr(work_journal,'scope',lambda *args:None)
    with pytest.raises(ValueError,match='Неизвестный'):
        operator_workday_router.input_context(Cursor(),'business','manager','conversation',{'selected_object':selected})

def test_access_check_is_preserved(monkeypatch):
    def denied(*args):raise PermissionError('Denied')
    monkeypatch.setattr(work_journal,'scope',denied)
    with pytest.raises(PermissionError):
        operator_workday_router.input_context(Cursor(),'foreign','manager','conversation',{'selected_object':{'type':'partner','id':'chosen'}})

@pytest.mark.parametrize('previous,force',[(None,False),('ready',False),('queued',False),('drafting',False),('failed',True),('needs_evidence',True),('needs_contact',True)])
def test_explicit_retry_only_for_failed_preparation(monkeypatch,previous,force):
    from services import operator_partner_work, lead_workstream_service, contact_intelligence_service
    class QueueCursor:
        connection=object()
        def execute(self,*args):pass
        def fetchone(self):return {'status':previous} if previous else None
    monkeypatch.setattr(operator_partner_work,'partner_selection',lambda *args,**kw:{'version':'v','status':'new','workstream_id':'work'})
    monkeypatch.setattr(lead_workstream_service,'resolve_workstream',lambda *args,**kw:{'id':'work'})
    calls=[]
    def enqueue(cursor,workstream_id,force=False,allow_paid_enrichment=False,requested_by_user_id=''):
        calls.append((force,allow_paid_enrichment,requested_by_user_id))
        return {'id':'job','status':'queued','reused':False}
    monkeypatch.setattr(contact_intelligence_service,'enqueue_enrichment_job',enqueue)
    operator_partner_work.queue_first_note(QueueCursor(),user_id='manager',business_id='business',lead_id='partner',expected_version='v')
    assert calls==[(force,False,'manager')]

@pytest.mark.parametrize('job_status,result_status',[('queued','queued'),('ready','completed'),('needs_evidence','clarification_required')])
def test_preparation_result_does_not_claim_ready_when_queued(monkeypatch,job_status,result_status):
    from services import operator_partner_work
    monkeypatch.setattr(operator_partner_work,'queue_first_note',lambda *args,**kwargs:{'id':'job','status':job_status})
    result=operator_partner_work.apply(None,user_id='manager',business_id='business',envelope={'payload':{'version':'v','lead_id':'partner'}})
    assert result['status']==result_status
    assert 'Письмо не отправлено' in result['chat_response']
    assert job_status not in result['chat_response']

from tests.test_operator_voice_pg import pg
@pytest.mark.parametrize('channel',['web','telegram','telegram_mini_app','max_bot','max_mini_app'])
def test_full_chat_with_workday_enabled_delegates_partner(pg,monkeypatch,channel):
    from services import operator_chat_service,operator_workday,operator_partner_work
    conn,c=pg
    c.execute("ALTER TABLE operatorconversations ADD COLUMN input_context_json JSONB DEFAULT '{}'::jsonb")
    monkeypatch.setattr(operator_workday,'enabled',lambda business:True)
    monkeypatch.setattr(work_journal,'scope',lambda *args:None)
    def selection(cursor,**kwargs):
        if kwargs['item_id']!='allowed':raise PermissionError('Foreign partner')
        return {'item_id':'allowed','version':'v','name':'Studio','channel':'manual','status':'new'}
    monkeypatch.setattr(operator_partner_work,'partner_selection',selection)
    calls=[]
    def router(cursor,**kwargs):
        calls.append(kwargs['pending_context']['selected_partner']['item_id'])
        return {'status':'completed','chat_response':'Selected partner'},{}
    args=dict(business_id='b',user_id='u',channel=channel,message='Подготовь первое письмо',router=router)
    result=operator_chat_service.process_chat(c,**args,payload={'request_id':'first','selected_object':{'type':'partner','id':'allowed'}})
    assert result['status']=='completed' and calls==['allowed']
    conn.commit()
    with pytest.raises(PermissionError,match='Foreign partner'):
        operator_chat_service.process_chat(c,**args,payload={'request_id':'second','selected_object':{'type':'partner','id':'foreign'}})
    assert calls==['allowed']

@pytest.mark.parametrize('code',['gigachat_budget_exceeded','deepseek_budget_exceeded'])
def test_budget_failure_preserves_evidence_and_actionable_state(code):
    from services.contact_intelligence_service import PersonalizationGenerationError,_is_terminal_draft_provider_error,_draft_provider_unavailable_state
    error=PersonalizationGenerationError(code,'Budget unavailable',retryable=False)
    assert _is_terminal_draft_provider_error(error)
    quality,readiness=_draft_provider_unavailable_state({'contact_id':'verified'},error)
    assert not quality['passed'] and readiness['code']=='needs_evidence'
    assert readiness['contact_id']=='verified'
    assert readiness['missing_items'][0]['code']=='ai_budget_exhausted'
    assert 'лимит' in readiness['missing'][0]

from services.openclaw_website_research import publication_facts

def test_reader_metadata_never_becomes_a_fact():
    research={'facts':[{'fact':'Page title: Clinic'}],'pages':[{'final_url':'https://example.test','fetched_at':'2026-10-21T10:00:00Z',
        'content_text':'Public contact/company context from source HTML:\n[Написать нам](/contact)\nMain page content:\n## Клиника\nМы принимаем взрослых и детей по записи в нашем медицинском центре.'}]}
    facts=publication_facts(research)
    assert len(facts)==1 and 'На сайте компании сказано: «Мы принимаем' in facts[0]['fact']
    assert facts[0]['source_url']=='https://example.test' and facts[0]['observed_at']=='2026-10-21T10:00:00Z'

def test_empty_or_navigation_only_site_cannot_supply_evidence():
    assert publication_facts({'pages':[{'final_url':'https://example.test','content_text':'Page title: Clinic\nPublic contact/company context from source HTML:\n[Написать нам](/contact)'}]})==[]

def test_service_metadata_fails_final_copy_check():
    from services.contact_intelligence_service import evaluate_first_message
    result=evaluate_first_message('Здравствуйте! Page title: Клиника. Публичный фрагмент сайта для проверки. Обсудим?',{})
    assert not result['passed'] and 'В письмо попало служебное описание источника' in result['failures']

def test_first_partnership_touch_does_not_imply_previous_contact():
    from services.outreach_personalization_ai import _assemble_policy_bound_text
    record={'motion':'client_partnership','sender':{'name':'Мария','role':'управляющий','business':'Студия','founder_story':'Основатель создал студию для семей.'},
      'identity':{'company_name':'Клиника','recipient_type':'business'},'representation':{},
      'personalization':{'observation':'В клинике принимают взрослых и детей','relevance_to_offer':'Предлагаем обсудить взаимные рекомендации'}}
    text=_assemble_policy_bound_text(index=0,opening_style='direct',cta_intent='discuss_pilot',
      expected_item={'angle':'founder_story'},request_record=record)
    assert 'Пишем от «Студия»' in text and 'Коротко продолж' not in text


def test_unrequested_preparation_never_queues_work():
    from services.contact_intelligence_service import enqueue_enrichment_job
    class Cursor:
        def __init__(self): self.queries=[]
        def execute(self,sql,args=()): self.queries.append(sql)
        def fetchone(self): return None
    cursor=Cursor()
    result=enqueue_enrichment_job(cursor,'work',force=True)
    assert result['skipped'] and result['reason']=='manual_request_required'
    assert not any('INSERT' in sql for sql in cursor.queries)


def test_processing_requires_exact_authorized_workstream():
    from services.contact_intelligence_service import process_enrichment_job,PersonalizationGenerationError
    with pytest.raises(PersonalizationGenerationError,match='по вашей команде'):
        process_enrichment_job(None,{'id':'job','workstream_id':'work',
            'result_json':{'generation_request':{'source':'user_request','actor_user_id':'manager','workstream_id':'foreign'}}})
