from unittest.mock import Mock
from services.outreach_continuation import delivery_report, group_campaign_ids
from services.partnership_group_view import presentation


def test_reused_company_does_not_inherit_old_send_or_reply():
    cursor = Mock(); cursor.fetchall.return_value = []
    task = {'id': 'new-task', 'business_id': 'business', 'state': {'lead_ids': ['reused-lead']}}
    report = delivery_report(cursor, task)
    assert report['confirmed_sent'] == report['replies'] == report['queued'] == 0
    assert cursor.execute.call_count == 1
    assert cursor.execute.call_args.args[1] == ('business', 'new-task')
    task.update(config={'mode': 'prepare_only'}, status='completed', report=report)
    assert presentation(task)['phase'] == 'companies'


def test_receipts_require_group_campaign_and_business():
    cursor = Mock(); cursor.fetchall.side_effect = [[], []]
    cursor.fetchone.return_value = {'confirmed_sent': 1}
    task = {'id': 'task', 'business_id': 'business', 'state': {
        'lead_ids': ['shared-lead'], 'campaign_results': {'ws': {'campaign_id': 'approved-campaign'}}}}
    assert delivery_report(cursor, task)['confirmed_sent'] == 1
    calls = cursor.execute.call_args_list
    assert calls[1].args[1] == (['approved-campaign'], 'business')
    assert calls[2].args[1] == (['approved-campaign'], 'business')
    assert all('shared-lead' not in str(call) for call in calls)


def test_native_draft_batch_campaigns_remain_part_of_group():
    cursor=Mock(); cursor.fetchall.return_value=[{'campaign_id': 'batch-campaign'}]
    assert group_campaign_ids(cursor, {'id':'task','business_id':'b','state':{}})==['batch-campaign']


def test_campaign_contract_is_bound_to_current_task_not_first_historical_import(monkeypatch):
    import services.outreach_continuation as continuation
    monkeypatch.setattr(continuation, 'continuation_enabled', lambda business: True)
    cursor=Mock(); cursor.fetchone.return_value={'id':'current-task','status':'running','business_id':'b',
        'payload_json':{},'result_json':{'qualifications':{'ws':{'status':'qualified'}}}}
    contract=continuation.load_workstream_contract(cursor,'ws',task_id='current-task')
    assert contract['qualification']['status']=='qualified'
    assert contract['task_id']=='current-task'
    assert cursor.execute.call_args.args[1]==('ws',continuation.KIND,'current-task','current-task')


def test_preview_accepts_task_binding_before_any_generation(monkeypatch):
    import services.outreach_campaign_service as campaigns
    import services.outreach_continuation as continuation
    monkeypatch.setattr(campaigns,'_load_context',lambda *args:{'continuation_managed':True})
    monkeypatch.setattr(campaigns,'_apply_sender_mode',lambda context,mode:context)
    contract=Mock(return_value={'enabled':False})
    monkeypatch.setattr(continuation,'load_workstream_contract',contract)
    result=campaigns.build_preview(Mock(),'ws',continuation_task_id='reviewed-task',generate_ai=True)
    assert result['reason_code']=='continuation_audience_review_required'
    contract.assert_called_once()
    assert contract.call_args.kwargs['task_id']=='reviewed-task'
