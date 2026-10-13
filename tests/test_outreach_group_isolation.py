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


def test_group_message_scope_uses_exact_task_campaigns_not_shared_leads():
    from services.partnership_group_view import message_campaign_scope
    cursor = Mock()
    cursor.fetchone.return_value = {'id': 'current-task', 'result_json': {
        'lead_ids': ['shared-company'], 'campaign_results': {
            'ws': {'campaign_id': 'current-campaign'}}}, 'payload_json': {}}
    cursor.fetchall.return_value = [{'campaign_id': 'projected-campaign'}]
    assert message_campaign_scope(cursor, 'business', 'current-task') == [
        'current-campaign', 'projected-campaign']
    assert cursor.execute.call_args_list[0].args[1] == ('current-task', 'business')


def test_empty_group_message_scope_does_not_fall_back_to_all_campaigns():
    from services.partnership_group_view import message_campaign_scope
    cursor = Mock()
    cursor.fetchone.return_value = {'id': 'task', 'result_json': {
        'lead_ids': ['historical-company']}, 'payload_json': {}}
    cursor.fetchall.return_value = []
    assert message_campaign_scope(cursor, 'business', 'task') == []


def test_message_scope_rejects_task_from_other_business():
    import pytest
    from services.partnership_group_view import message_campaign_scope, GroupNotFound
    cursor = Mock(); cursor.fetchone.return_value = None
    with pytest.raises(GroupNotFound):
        message_campaign_scope(cursor, 'other-business', 'task')
    cursor.fetchall.assert_not_called()


def test_status_response_contains_real_result_reason_and_exact_group_link(monkeypatch):
    import services.outreach_chat_results as results
    monkeypatch.setattr(results, 'letters', lambda *args: (_ for _ in ()).throw(AssertionError('Status must not load all letters')))
    task = {'id': 'task', 'business_id': 'business', 'display_name': 'India', 'state': {},
            'report': {'found': 3, 'eligible': 2, 'target': 3, 'prepared': 0, 'credits_charged': 3},
            'presentation': {'label': 'Требуется действие', 'reason': 'Не удалось создать письма',
                             'next_action': {'label': 'Посмотреть компании'}}}
    output = results.result(Mock(), {'stage': 'Проверка завершена'}, include_letters=False, task=task)
    assert 'Подходят: 2 / 3' in output['chat_response']
    assert '3 кр.' in output['chat_response']
    assert 'Не удалось создать письма' in output['chat_response']
    assert 'search_task_id=task' in output['result_ref']['href']
    assert output['external_dispatch_performed'] is False


def test_personalization_prefers_offer_fact_over_generic_company_description():
    from services.outreach_personalization_ai import qualified_requirement_for_offer, attributed_observation
    def criterion(quote, source_type='official_website'):
        return {'status': 'verified', 'quote': quote, 'evidence': {'fact': quote, 'source_url': 'https://example.org', 'source_type': source_type}}
    qualification = {'criteria': {'requirement_0': criterion('We are a luxury travel company in India'),
        'requirement_1': criterion('2 nights in Krabi and 2 nights in Phuket'),
        'requirement_2': criterion('Email Phuket@example.org', 'public_contact_source')}}
    assert qualified_requirement_for_offer(qualification, 'Riderra transfers in Phuket')['quote'] == '2 nights in Krabi and 2 nights in Phuket'
    assert attributed_observation('We create luxury holidays').startswith('Your website states: “We')
    assert attributed_observation('Two nights in Phuket') == 'Two nights in Phuket'


def test_old_native_draft_is_not_reused_after_generation_contract_fix():
    from services.outreach_continuation import campaign_requires_refresh
    cursor=Mock(); cursor.fetchall.return_value=[{'message_brief_json': {'generation_source':'deepseek',
        'generation_prompt_version':'outreach_personalization_v15','semantic_review_prompt_version':'outreach_semantic_review_v6'},
        'quality_gate_json': {'passed':True,'semantic_review':{'passed':True}}}]
    assert campaign_requires_refresh(cursor, 'campaign', 'business')
    assert cursor.execute.call_args.args[1] == ('campaign','business')


def test_offer_evidence_selection_is_not_specific_to_tourism():
    from services.outreach_personalization_ai import qualified_requirement_for_offer
    criteria = {'requirement_0': {'status':'verified','quote':'Licensed supplier in Kazan','evidence':{'source_url':'https://supplier.example/about'}},
                'requirement_1': {'status':'verified','quote':'Wholesale organic cosmetics','evidence':{'source_url':'https://supplier.example/catalog'}},
                'requirement_2': {'status':'not_verified','quote':'Organic cosmetics certification','evidence':{'source_url':'https://supplier.example'}}}
    chosen=qualified_requirement_for_offer({'criteria':criteria},'Organic cosmetics partnership')
    assert chosen['quote']=='Wholesale organic cosmetics'


def test_recipient_first_person_is_attributed_in_actual_template_rendering():
    from services.outreach_personalization_ai import _normalize_touches, _request_record
    record=_request_record(motion='client_partnership',identity={'company_name':'Example agency'},
        candidate={'observed_fact':'We arrange holiday tours','source_url':'https://example.org','evidence_id':'public-fact','relevance_to_offer':'Riderra transfers'},
        founder_story={'story':'Alex from Riderra','offer':'Riderra transfers'},
        sequence=[{'sequence_index':0,'channel':'email','angle':'business_reputation','day_offset':0}],voice_examples=[])
    record['copy_language']='en'
    output=_normalize_touches([{'sequence_index':0,'channel':'email','angle':'business_reputation',
        'text_template':'Hello {{RECIPIENT}},\n\n{{OBSERVATION}}\n\n{{BRIDGE}}\n\nWould you like details?',
        'evidence_ids':['public-fact']}], record)
    assert 'Your website states: “We arrange holiday tours”.' in output[0]['text']


def test_offer_bridge_names_verified_context_without_inventing_need():
    from services.outreach_personalization_ai import qualified_offer_bridge
    value = qualified_offer_bridge('Riderra transfers in Phuket', '#### Day 1: Arrival in Phuket')
    assert 'Day 1: Arrival in Phuket' in value and 'Riderra transfers in Phuket' in value
    assert '####' not in value
    assert 'need' not in value and 'нужна' not in value
