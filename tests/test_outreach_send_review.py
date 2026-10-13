from unittest.mock import Mock
import ast
from pathlib import Path
import pytest
from services import outreach_send_review as service


def review():
    return {'business_id':'b','user_id':'u','task_ids':['task'],'letters':[
        {'campaign_id':'one','recipient':'one@example.org','sender':'sender@example.org','subject':'Exact subject','generated_text':'Exact text'},
        {'campaign_id':'two','recipient':'two@example.org'}]}


@pytest.mark.parametrize('field,value',[('recipient','changed@example.org'),('sender','changed@example.org'),('subject','Changed'),('generated_text','Changed')])
def test_snapshot_binds_visible_email_fields(field,value):
    original=review();digest=service.review_digest(original);original['letters'][0][field]=value
    assert service.review_digest(original)!=digest


def test_stale_confirmation_cannot_create_queue(monkeypatch):
    monkeypatch.setattr(service,'load_review',lambda *a,**kw:review());cursor=Mock()
    with pytest.raises(ValueError,match='send_review_stale'):
        service.confirm(cursor,business_id='b',user_id='u',envelope={'business_id':'b','review_hash':'old','task_ids':['task']})
    cursor.execute.assert_not_called()


def test_changed_business_rejected_before_loading(monkeypatch):
    load=Mock();monkeypatch.setattr(service,'load_review',load)
    with pytest.raises(ValueError,match='business_mismatch'):
        service.confirm(Mock(),business_id='other',user_id='u',envelope={'business_id':'b'})
    load.assert_not_called()


def test_native_failure_rolls_back_entire_batch(monkeypatch):
    import services.outreach_campaign_service as native
    monkeypatch.setattr(service,'load_review',lambda *a,**kw:review())
    approve=Mock(side_effect=[{},ValueError('native_sender_not_ready')]);monkeypatch.setattr(native,'approve_campaign',approve)
    cursor=Mock()
    with pytest.raises(ValueError,match='native_sender_not_ready'):
        service.confirm(cursor,business_id='b',user_id='u',envelope={'business_id':'b','task_ids':['task'],'review_hash':service.review_digest(review())})
    statements=[call.args[0] for call in cursor.execute.call_args_list]
    assert 'ROLLBACK TO SAVEPOINT reviewed_group_send' in statements
    assert not any("SET status='approved'" in sql for sql in statements)
    assert approve.call_args_list[0].kwargs['reviewed_batch_id']==approve.call_args_list[1].kwargs['reviewed_batch_id']
    assert all(call.kwargs['user_id']=='u' for call in approve.call_args_list)


def test_preview_never_approves_or_dispatches(monkeypatch):
    import services.outreach_campaign_service as native
    r=review();r['letters']=r['letters'][:1];r['letters'][0]['source_url']='https://public.example.org/tour';monkeypatch.setattr(service,'load_review',lambda *a,**kw:r)
    approve=Mock();monkeypatch.setattr(native,'approve_campaign',approve)
    result=service.preview(Mock(),business_id='b',user_id='u',task_ids=['task'])
    assert result['approval']['capability']=='partnerships.send_review'
    assert result['approval']['envelope']['operation']=='confirm_send'
    assert 'Exact text' in result['chat_response'] and 'one@example.org' in result['chat_response']
    assert 'https://public.example.org/tour' in result['chat_response']
    assert 'drafts' not in result
    approve.assert_not_called()


@pytest.mark.parametrize('change,reason',[('foreign','search_task_not_found'),('running','pause_before_send_review'),('unqualified','letters_need_review'),('followup','first_email_only_required'),('quality','letter_not_send_ready')])
def test_reject_unsafe_group(monkeypatch,change,reason):
    import services.operator_audio as auth
    import services.outreach_continuation as continuation
    monkeypatch.setattr(auth,'authorize_actor',lambda *a:({'is_superadmin':True},{}))
    monkeypatch.setattr(continuation,'actor_can_write',lambda *a:True)
    task={'status':'completed','payload_json':{},'result_json':{'verified_contact_workstream_ids':['ws'],
        'qualifications':{'ws':{'status':'qualified'}},'campaign_results':{'ws':{'campaign_id':'c','status':'ready'}}}}
    touch={'id':'t','sequence_index':0,'channel':'email','recipient':'public@example.org','sender':'sender@example.org',
        'subject':'Subject','generated_text':'Grounded letter','quality_gate_json':{'passed':True}}
    if change=='running':task['status']='running'
    if change=='unqualified':task['result_json']['qualifications']['ws']['status']='needs_evidence'
    if change=='followup':touch['sequence_index']=1
    if change=='quality':touch['quality_gate_json']['passed']=False
    cursor=Mock();cursor.fetchone.side_effect=[None if change=='foreign' else task,{'id':'c','lead_id':'lead','status':'draft'}];cursor.fetchall.return_value=[touch]
    with pytest.raises(ValueError,match=reason):service.load_review(cursor,business_id='b',user_id='u',task_ids=['task'])


def test_send_approval_is_not_legacy_search_confirmation():
    path=Path(__file__).resolve().parents[1]/'src/services/operator_core.py'
    function=next(node for node in ast.parse(path.read_text()).body if isinstance(node,ast.FunctionDef) and node.name=='standardize_operator_result')
    ns={'Any':object,'CAPABILITY_BY_NAME':{},'_result_ref':lambda *a,**kw:{'href':None,**kw}}
    exec(compile(ast.Module(body=[function],type_ignores=[]),str(path),'exec'),ns)
    result=ns['standardize_operator_result']({'approval':{'capability':'partnerships.send_review'},'chat_response':'Review exact email'},'partnerships.continue_outreach')
    assert result['capability']=='partnerships.send_review'


def test_explicit_send_review_can_cover_two_groups_without_a_search():
    from services.operator_outreach_read_request import send_review_request
    one='e361ce95-586a-441f-a167-455805fdb5ed';two='d4b43860-d176-41f9-8085-462f962f39f3'
    assert send_review_request(f'Подготовь единый просмотр отправки для групп {one} и {two}')['task_ids']==sorted([one,two])
    assert send_review_request('Отправь письма') is None


@pytest.mark.parametrize('contacted',[True,False])
def test_first_contact_uses_same_business_native_queue_evidence(contacted):
    cursor=Mock();cursor.fetchone.return_value={'contacted':contacted}
    assert service.prior_first_contact(cursor,'business','lead') is contacted
    assert cursor.execute.call_args.args[1]==('business','lead')
    sql=cursor.execute.call_args.args[0]
    assert 'provider_message_id' in sql and 'delivery_unknown' in sql


def test_explicit_review_replaces_unfinished_other_task_before_any_ai_router(monkeypatch):
    import services.outreach_continuation as continuation
    action=Mock(return_value={'status':'blocked','blocked_reasons':['search_task_not_found']})
    monkeypatch.setattr(continuation,'operator_task',action)
    path=Path(__file__).resolve().parents[1]/'src/services/operator_core.py'
    function=next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='route_operator_message')
    # Postponed annotations let this test execute the real dispatch without importing unrelated app services.
    module=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),function],type_ignores=[])
    ns={'standardize_operator_result':lambda result,cap:dict(result,capability=cap)}
    exec(compile(ast.fix_missing_locations(module),str(path),'exec'),ns)
    result,pending=ns['route_operator_message'](Mock(),business_id='other-business',user_id='u',
        message='Для Riderra подготовь просмотр отправки задачи d4b43860-d176-41f9-8085-462f962f39f3.',channel='telegram',
        pending_context={'capability':'settings.profile.clarification'},actor_context={'user_id':'u'})
    assert result['blocked_reasons']==['search_task_not_found'] and pending=={}
    assert 'Сменить бизнес' in result['chat_response'] and 'Ничего не отправлено' in result['chat_response']
    assert action.call_args.kwargs['business_id']=='other-business'
    assert action.call_args.kwargs['arguments']['task_ids']==['d4b43860-d176-41f9-8085-462f962f39f3']
