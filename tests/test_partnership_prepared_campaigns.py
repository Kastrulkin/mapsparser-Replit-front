import pytest
from services.partnership_prepared_campaigns import validate_item,copy_digest,cold_guard


def item():
    return {'lead_id':'lead','channel':'telegram','contact':'@example','source':'https://example.test/contact','observation':'Подтверждённая компания рядом.','observed_at':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),'touches':[{'day_offset':0,'text':'Здравствуйте! Предлагаем партнёрство.'}]}


@pytest.mark.parametrize('change',[
    {'channel':'vk'},{'source':'https://password:secret@example.test/'},{'source':'javascript:alert(1)'},{'observation':''},
    {'touches':[]},{'touches':[{'day_offset':1,'text':'Текст'}]}, {'touches':[{'day_offset':False,'text':'Текст'}]},
    {'touches':[{'day_offset':0,'text':'Текст'},{'day_offset':0,'text':'Другой текст'}]},
    {'touches':[{'day_offset':0,'text':'Текст'},{'day_offset':91,'text':'Другой текст'}]},
    {'channel':'email','touches':[{'day_offset':0,'text':'Текст','subject':'Подмена\nBcc: secret@example.test'}]},
    {'channel':'email','touches':[{'day_offset':0,'text':'Текст'}]},
])
def test_rejects_unsupported_or_ambiguous_copy(change):
    value=item();value.update(change)
    with pytest.raises(ValueError):validate_item(value)


def test_does_not_rewrite_owner_template():
    value=item();value['touches'][0]['text']='Здравствуйте!\n\nМы - «Весёлая расчёска».\n\nВам может быть это интересно?'
    assert validate_item(value)['touches'][0]['text']==value['touches'][0]['text']


@pytest.mark.parametrize('field',['generated_text','subject','contact_point_id','sender_account_id','recipient','contact_source','sender_identity','updated_at'])
def test_review_binds_exact_content_recipient_sender_and_version(field):
    t={'id':'touch','channel':'telegram','generated_text':'Текст','subject':'Тема','contact_point_id':'recipient','sender_account_id':'sender','updated_at':'now'}
    assert copy_digest([t])!=copy_digest([{**t,field:'changed'}])


def test_cold_guard_blocks_cross_context_contact_history(monkeypatch):
    from services import outreach_safety_service
    monkeypatch.setattr(outreach_safety_service,'load_partnership_repeat_contact_guard',lambda *a,**k:{'blocked':False})
    class Cursor:
        def execute(self,q,p):self.params=p
        def fetchone(self):return {'id':'same-recipient-old-business'}
    c=Cursor()
    with pytest.raises(ValueError,match='прежние касания'):
        cold_guard(c,{'id':'new','company_id':'company'},'workstream','https://t.me/Partner')
    assert c.params==('company','partner','partner')


def test_cold_guard_denies_known_relationship_before_other_queries(monkeypatch):
    from services import outreach_safety_service
    monkeypatch.setattr(outreach_safety_service,'load_partnership_repeat_contact_guard',lambda *a,**k:{'blocked':True})
    with pytest.raises(ValueError,match='прежнее общение'):
        cold_guard(None,{'id':'lead'},'workstream','@recipient')


@pytest.mark.parametrize('reason',['RECIPIENT_SUPPRESSED','UNSUPPORTED_CLAIM','SENDER_SCOPE_MISMATCH'])
def test_human_copy_review_never_waives_noncopy_errors(monkeypatch,reason):
    from services import partnership_prepared_campaigns as prepared,operator_audio
    import subscription_manager
    monkeypatch.setattr(operator_audio,'authorize_actor',lambda *a,**k:({},{}))
    monkeypatch.setattr(subscription_manager,'capability_access_payload',lambda *a,**k:{'allowed':True})
    touches=[{'id':'touch','recipient':'@company','sequence_index':0,'generated_text':'Текст','quality_gate_json':{'passed':False,'reason_codes':[reason]}}]
    monkeypatch.setattr(prepared,'load_touches',lambda *a:touches)
    monkeypatch.setattr(prepared,'cold_guard',lambda *a:None)
    monkeypatch.setattr(prepared,'check_source_freshness',lambda *a:None)
    class Cursor:
        def execute(self,*a):pass
        def fetchone(self):return {'lead_id':'lead','workstream_id':'work','company_id':'company'}
    with pytest.raises(ValueError,match='безопасности'):
        prepared.review_copy(Cursor(),business_id='business',user={'user_id':'manager'},campaign_id='campaign',digest=prepared.copy_digest(touches))


def test_review_rejects_stale_copy_before_applying_decision(monkeypatch):
    from services import partnership_prepared_campaigns as prepared,operator_audio
    import subscription_manager
    monkeypatch.setattr(operator_audio,'authorize_actor',lambda *a,**k:({},{}))
    monkeypatch.setattr(subscription_manager,'capability_access_payload',lambda *a,**k:{'allowed':True})
    monkeypatch.setattr(prepared,'load_touches',lambda *a:[{'id':'touch','generated_text':'Новое письмо'}])
    class Cursor:
        def execute(self,*a):pass
        def fetchone(self):return {'lead_id':'lead','workstream_id':'work'}
    with pytest.raises(ValueError,match='изменился'):
        prepared.review_copy(Cursor(),business_id='business',user={'user_id':'manager'},campaign_id='campaign',digest='old')


def test_background_executor_rechecks_role_and_rolls_back_on_revoked_access(monkeypatch):
    from services import partnership_prepared_campaigns as prepared,operator_audio
    import database_manager
    called=[]
    class Connection:
        def cursor(self):return object()
        def commit(self):called.append('commit')
        def rollback(self):called.append('rollback')
    class Database:
        conn=Connection()
        def close(self):called.append('closed')
    monkeypatch.setattr(database_manager,'DatabaseManager',Database)
    def deny(*a,**k):raise PermissionError('Доступ отозван')
    monkeypatch.setattr(operator_audio,'authorize_actor',deny)
    with pytest.raises(PermissionError,match='отозван'):
        prepared.process_preparation_job({'user_id':'user','business_id':'business','payload_json':{'item':item()}})
    assert called==['rollback','closed']


def test_telegram_preserves_exact_body_without_an_email_subject():
    from services.partnership_prepared_campaigns import bind_exact_copy
    touch={'text':'Здравствуйте!\n\nГотовое письмо владельца.','subject':'Внутренний заголовок генератора'}
    human={'text':touch['text'],'subject':''}
    bind_exact_copy(touch,human,'telegram')
    assert touch==human


def test_email_still_requires_the_exact_human_subject():
    from services.partnership_prepared_campaigns import bind_exact_copy
    with pytest.raises(ValueError,match='Тема'):
        bind_exact_copy({'text':'Текст','subject':'Другая тема'},{'text':'Текст','subject':'Утверждённая тема'},'email')


def test_telegram_never_accepts_rewritten_body():
    from services.partnership_prepared_campaigns import bind_exact_copy
    with pytest.raises(ValueError,match='Текст'):
        bind_exact_copy({'text':'Новое письмо','subject':''},{'text':'Готовое письмо'},'telegram')


def test_cold_guard_honors_scoped_manual_hold_before_copy_review(monkeypatch):
    from services import outreach_safety_service,outreach_campaign_service
    monkeypatch.setattr(outreach_safety_service,'load_partnership_repeat_contact_guard',lambda *a,**k:{'blocked':False})
    contexts=[]
    def suppression(cursor,context):
        contexts.append(context)
        return {'suppressed':True,'reason_code':'manual_dnc'}
    monkeypatch.setattr(outreach_campaign_service,'_suppression_status',suppression)
    class Cursor:
        def execute(self,*a):pass
        def fetchone(self):return None
    with pytest.raises(ValueError,match='исключена из отправки'):
        cold_guard(Cursor(),{'id':'lead','business_id':'this-business','company_id':'company'},'workstream','@recipient')
    assert contexts==[{'lead_id':'lead','workstream_type':'client_partnership','client_business_id':'this-business'}]


def test_cold_guard_fails_closed_without_business_scope(monkeypatch):
    from services import outreach_safety_service
    monkeypatch.setattr(outreach_safety_service,'load_partnership_repeat_contact_guard',lambda *a,**k:{'blocked':False})
    class Cursor:
        def execute(self,*a):pass
        def fetchone(self):return None
    with pytest.raises(ValueError,match='Не определён бизнес'):
        cold_guard(Cursor(),{'id':'lead'},'workstream','@recipient')


@pytest.mark.parametrize('saved,current', [('old','new'), ('','new'), ('old','')])
def test_updated_or_missing_source_requires_new_preview(monkeypatch,saved,current):
    from services import partnership_prepared_campaigns as prepared,outreach_campaign_service
    monkeypatch.setattr(outreach_campaign_service,'current_outreach_source_fact_fingerprint',lambda *args:current)
    class Cursor:
        def execute(self,*args):pass
        def fetchone(self):return {'report_hash':'latest'}
    with pytest.raises(ValueError,match='Сведения о компании обновились'):
        prepared.check_source_freshness(Cursor(),'work',[{'message_brief_json':{'source_fact_fingerprint':saved}}])


def test_current_source_allows_review(monkeypatch):
    from services import partnership_prepared_campaigns as prepared,outreach_campaign_service
    monkeypatch.setattr(outreach_campaign_service,'current_outreach_source_fact_fingerprint',lambda *args:'same')
    class Cursor:
        def execute(self,*args):pass
        def fetchone(self):return {'report_hash':'latest'}
    prepared.check_source_freshness(Cursor(),'work',[{'message_brief_json':{'source_fact_fingerprint':'same'}}])
