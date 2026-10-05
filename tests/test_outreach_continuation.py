import pytest
from services.outreach_continuation import normalize_config, config_hash, preview_task_config
from services.outreach_language_routing import public_context, review_language, run_copy, CopyRoutingError
from services.llm.contracts import LLMTaskResult


def config():
    return {"audience": "travel agencies", "offer": "transfer offer", "queries": [{"query": "travel agency", "city": "Delhi"}]}


def test_config_is_bounded_and_never_grants_send():
    assert normalize_config(config())["mode"] == "prepare_only"
    for override in ({"mode": "auto_send"}, {"max_search_calls": 999}, {"batch_size": True}, {"queries": []}):
        with pytest.raises(ValueError):
            normalize_config({**config(), **override})
    assert config_hash(normalize_config(config())) == config_hash(normalize_config(config()))
    assert config_hash(normalize_config(config())) != config_hash(normalize_config({**config(), "offer": "different"}))


def test_find_only_preview_shows_bounds_without_creating_a_task():
    result = preview_task_config({
        "audience": "Indian travel agencies selling Phuket",
        "agency_country": "India", "sold_destination": "Phuket",
        "target_count": 10, "mode": "find_only",
    })
    assert result["status"] == "completed"
    assert result["config"]["target_count"] == 10
    assert result["config"]["mode"] == "find_only"
    assert result["config"]["interval_minutes"] == 5
    assert result["config"]["queries"][0]["city"] == "India"
    assert result["config"]["max_candidates"] >= 10
    assert "Ориентир по стоимости" in result["chat_response"]
    assert "65 кредитов" in result["chat_response"]
    assert "общего баланса" in result["chat_response"]
    assert "USD" not in result["chat_response"]
    assert result["credit_quote"]["total_max"] == 65
    assert result["config"]["billing_mode"] == "shared_balance_actual"
    assert "DeepSeek" not in result["chat_response"]
    assert result["search_started"] is False
    assert result["external_writes_performed"] is False
    assert result["result_ref"] == {"href": "/dashboard/operator", "label": "Условия показаны в чате"}
    russian = preview_task_config({"audience": "турагентства Индии, продающие Пхукет",
        "agency_country": "Индия", "sold_destination": "Пхукет", "target_count": 10, "mode": "find_only"})
    assert russian["config"]["queries"] == [{"query": "travel agencies selling Phuket tours", "city": "India"}]


def test_one_step_review_keeps_cost_estimate_and_versioned_terms():
    from services.outreach_continuation import prepare_new_task_approval
    result = prepare_new_task_approval({"audience": "Indian travel agencies selling Phuket",
        "agency_country": "India", "sold_destination": "Phuket", "target_count": 10, "mode": "find_only"},
        business_id="riderra", request_id="one-request")
    assert result["status"] == "approval_required"
    assert result["search_started"] is False
    assert result["approval"]["envelope"]["operation"] == "create_and_start"
    assert result["approval"]["envelope"]["revision"] == config_hash(result["config"])
    assert result["approval"]["envelope"]["request_id"] == "one-request"
    assert "65 кредитов" in result["chat_response"]


def test_search_start_uses_one_bounded_http_post(monkeypatch):
    from services import outreach_continuation, prospecting_service
    calls = []
    class Response:
        def raise_for_status(self): pass
        def json(self): return {'data': {'id': 'run-1', 'defaultDatasetId': 'dataset-1'}}
    class Prospecting:
        client = object()
        api_token = 'test-token'
        def __init__(self, source): assert source == 'apify_google'
        def _actor_path_id(self): return 'test~actor'
        def _build_run_input(self, query, city, limit): return {'query': query, 'city': city, 'limit': limit}
        def _strip_none_values(self, value): return value
        def _apify_request(self, method, url, **kwargs):
            calls.append((method, url, kwargs))
            return Response()
    monkeypatch.setattr(prospecting_service, 'ProspectingService', Prospecting)
    result = outreach_continuation._start_search(normalize_config({**config(), 'mode': 'find_only',
        'target_count': 10, 'batch_size': 50, 'max_search_calls': 3}), 0)
    assert result == {'id': 'run-1', 'dataset_id': 'dataset-1', 'requested_limit': 50, 'query_index': 0}
    assert len(calls) == 1 and calls[0][0] == 'POST'
    assert calls[0][1] == 'https://api.apify.com/v2/actors/test~actor/runs'
    assert calls[0][2]['params']['maxItems'] == 50
    assert calls[0][2]['params']['maxTotalChargeUsd'].startswith('0.3333')
    assert calls[0][2]['timeout'] == 45


def test_search_start_does_not_retry_rejected_http_post(monkeypatch):
    from services import outreach_continuation, prospecting_service
    calls = []
    class Response:
        def raise_for_status(self): raise RuntimeError('provider_rejected')
    class Prospecting:
        client = object()
        api_token = 'test-token'
        def __init__(self, source): pass
        def _actor_path_id(self): return 'test~actor'
        def _build_run_input(self, query, city, limit): return {}
        def _strip_none_values(self, value): return value
        def _apify_request(self, method, url, **kwargs):
            calls.append(method)
            return Response()
    monkeypatch.setattr(prospecting_service, 'ProspectingService', Prospecting)
    with pytest.raises(RuntimeError, match='provider_rejected'):
        outreach_continuation._start_search(normalize_config({**config(), 'mode': 'find_only', 'target_count': 10}), 0)
    assert calls == ['POST']


def test_provider_minimum_prevents_underfunded_search_before_post(monkeypatch):
    from services import outreach_continuation, prospecting_service
    calls = []
    class Response:
        def raise_for_status(self): pass
        def json(self): return {'data': {'pricingInfos': [{'minimalMaxTotalChargeUsd': 0.5}]}}
    class Prospecting:
        api_token = 'test-token'
        def __init__(self, source): assert source == 'apify_google'
        def _actor_path_id(self): return 'test~actor'
        def _apify_request(self, method, url, **kwargs):
            calls.append(method)
            return Response()
    monkeypatch.setattr(prospecting_service, 'ProspectingService', Prospecting)
    minimum = outreach_continuation._provider_search_minimum_usd()
    cfg = normalize_config({**config(), 'mode': 'find_only', 'target_count': 10,
        'search_budget_cents': 100, 'max_search_calls': 3})
    assert outreach_continuation.search_provider_minimum_gap(cfg, minimum)
    assert not outreach_continuation.search_provider_minimum_gap({**cfg, 'max_search_calls': 2}, minimum)
    assert calls == ['GET']


def test_reconciled_search_gets_a_new_credit_reservation_key():
    from services.outreach_continuation import next_search_reservation_key
    first_serial, first_key = next_search_reservation_key({}, 0)
    retry_serial, retry_key = next_search_reservation_key({'search_attempt_serial': first_serial}, 0)
    assert (first_serial, first_key) == (1, '1:1')
    assert (retry_serial, retry_key) == (2, '1:2')


def test_language_follows_text_and_does_not_assume_cis_support():
    assert review_language("ru-RU")
    for lang in ("en", "kk", "uz-Latn", "hy", "unknown"):
        assert not review_language(lang)


def test_context_removes_identifiers_and_restores_server_side():
    record = {"identity": {"contact_name": "Jane Doe", "company_name": "Private Company"},
              "sender": {"name": "Sender", "voice_examples": ["unrestricted transcript"]},
              "evidence": [{"source_type": "public", "source_url": "https://example.org/Jane", "observation": "A public offer"}],
              "draft": "Jane Doe, jane@example.org +91 98765 43210 Private Company"}
    result = public_context(record)
    assert "Jane Doe" not in str(result.record)
    assert "jane@example.org" not in str(result.record)
    assert "98765" not in str(result.record)
    assert "unrestricted transcript" not in str(result.record)
    assert result.restore(result.record["draft"]) == record["draft"]
    with pytest.raises(CopyRoutingError):
        public_context({"evidence": [{"source_type": "private_conversation"}]})


def test_route_has_no_silent_provider_fallback():
    calls = []
    def runner(request):
        calls.append(request)
        return LLMTaskResult(status="completed", content="ok", provider="gigachat")
    assert run_copy("review", business_id="b", user_id="u", language="ru", review=True, runner=runner) == "ok"
    assert calls[-1].task_key == "outreach_language_review"
    with pytest.raises(CopyRoutingError):
        run_copy("draft", business_id="b", user_id="u", language="en", runner=runner)
    assert calls[-1].task_key == "outreach_public_copy"


def test_qualification_requires_real_quote_and_does_not_invent_evidence():
    from services.outreach_continuation import qualify_audience
    evidence = [{"id":"e1", "fact":"The agency sells Phuket holidays", "source_url":"https://example.org/phuket", "source_type":"public"}]
    def model(request):
        return LLMTaskResult(status="completed", provider="deepseek", parsed_data={"matches":True,"evidence_id":"e1","quote":"sells Phuket holidays","reason":"destination listed"})
    assert qualify_audience(config(), evidence, business_id="b", user_id="u", runner=model)["status"] == "qualified"
    def hallucination(request):
        return LLMTaskResult(status="completed", provider="deepseek", parsed_data={"matches":True,"evidence_id":"e1","quote":"Sells Paris holidays","reason":"invented"})
    assert qualify_audience(config(), evidence, business_id="b", user_id="u", runner=hallucination)["status"] == "needs_evidence"
    assert qualify_audience(config(), [], business_id="b", user_id="u", runner=model)["status"] == "needs_evidence"


def test_india_phuket_requires_separate_public_evidence_for_both_conditions():
    from services.outreach_continuation import qualify_audience
    evidence = [
        {"id": "company", "fact": "Our travel agency has an office in Kathmandu, Nepal.", "source_url": "https://example.com/about"},
        {"id": "tour", "fact": "We sell Phuket holiday packages to customers.", "source_url": "https://example.com/phuket"},
    ]
    def model(_request):
        return LLMTaskResult(status="completed", provider="deepseek", content="", parsed_data={
            "matches": True,
            "country": {"matches": False, "evidence_id": "company", "quote": "Our travel agency has an office in Kathmandu, Nepal."},
            "destination": {"matches": True, "evidence_id": "tour", "quote": "We sell Phuket holiday packages to customers."},
        })
    result = qualify_audience({**config(), "agency_country": "India", "sold_destination": "Phuket"}, evidence,
                              business_id="b", user_id="u", runner=model)
    assert result["status"] == "needs_evidence"
    assert result["criteria"]["country"]["status"] == "not_verified"
    assert result["criteria"]["destination"]["status"] == "verified"


def test_qualification_schema_accepts_the_country_and_destination_contract():
    from services.llm.registry import get_task_definition
    from services.llm.schema import validate_json_schema
    definition = get_task_definition("outreach_audience_qualify")
    response = {"matches": True, "reason": "Both conditions documented",
                "country": {"matches": True, "evidence_id": "india", "quote": "Based in Delhi, India"},
                "destination": {"matches": True, "evidence_id": "phuket", "quote": "We sell Phuket holidays"}}
    assert validate_json_schema(response, definition.response_schema) == []
    assert definition.thinking_enabled is False and definition.max_tokens >= 1600


def test_technical_verification_failure_is_not_exclusion():
    from services.outreach_continuation import preparation_report
    report = preparation_report({"target_count": 2}, {"lead_ids": ["a", "b"],
        "qualifications": {"a": {"status": "failed"}, "b": {"status": "needs_evidence"}}})
    assert report["verification_failed"] == 1
    assert report["excluded"] == 1
    assert report["shortfall"] == 2


def test_feature_requires_global_and_specific_business_enablement(monkeypatch):
    from services.outreach_continuation import continuation_enabled
    monkeypatch.delenv('OUTREACH_CONTINUATION_ENABLED', raising=False)
    assert not continuation_enabled('b')
    monkeypatch.setenv('OUTREACH_CONTINUATION_ENABLED','true')
    monkeypatch.setenv('OUTREACH_CONTINUATION_BUSINESS_IDS','b')
    assert continuation_enabled('b')
    assert not continuation_enabled('foreign')


def test_disabled_deepseek_cannot_call_gigachat_for_drafting(monkeypatch):
    from services.llm import gateway
    from services.llm.contracts import LLMTaskRequest
    monkeypatch.delenv('LLM_ROUTER_ENABLED',raising=False)
    monkeypatch.setattr(gateway,'_generate_with_provider_fallback',lambda *a,**k:pytest.fail('Wrong provider must not be invoked'))
    for key in ('outreach_public_copy','outreach_audience_qualify'):
        assert gateway.run_llm_task(LLMTaskRequest(task_key=key,prompt='draft',business_id='b')).status=='task_blocked'


def test_public_evidence_only_follows_bounded_same_host_links(monkeypatch):
    from services import outreach_public_evidence
    from core.outbound_network import OutboundHttpFetchResponse
    calls=[]
    def fetch(url,**kwargs):
        calls.append(url)
        return OutboundHttpFetchResponse(200,{'content-type':'text/html'},b'<p>We sell Phuket holidays to families.</p><a href="/phuket">Phuket trips</a><a href="http://127.0.0.1/phuket">Phuket internal</a>')
    monkeypatch.setattr(outreach_public_evidence.outbound_network,'public_pinned_get',fetch)
    evidence=outreach_public_evidence.collect_candidate_evidence('https://example.org',['Phuket'])
    assert evidence and all(item['source_url'].startswith('https://example.org') for item in evidence)
    assert len(calls)<=3 and all('127.0.0.1' not in url for url in calls)


@pytest.mark.parametrize('language,expected_reviews',[('en',0),('ru',1),('kk',0),('uz-latn',0),('hy',0)])
def test_deepseek_drafts_full_sequence_and_gigachat_only_reviews_supported_language(monkeypatch,language,expected_reviews):
    import json
    from services import outreach_language_routing, outreach_personalization_ai
    monkeypatch.setenv('OUTREACH_DEEPSEEK_DRAFTING_ENABLED','true')
    monkeypatch.setenv('OUTREACH_DEEPSEEK_BUSINESS_IDS','b')
    calls=[]
    def model(prompt,**kwargs):
        calls.append(kwargs)
        if kwargs.get('review'):
            return json.dumps({'passed':True,'issues':[]})
        if len(calls)==1:
            return json.dumps({'touches':[{'sequence_index':0,'channel':'email','angle':'business_reputation','subject':'Airport transfers','text_template':'Hello {{RECIPIENT}}. {{OBSERVATION}}. {{BRIDGE}}. May I send details?'}]})
        return json.dumps({'reviews':[{'sequence_index':0,'scores':{criterion:2 for criterion in outreach_personalization_ai.QUALITY_CRITERIA},'verdict':'approve','reason_codes':[]}]})
    monkeypatch.setattr(outreach_language_routing,'run_copy',model)
    result=outreach_personalization_ai.generate_personalized_sequence(motion='client_partnership',identity={'company_name':'Agency'},candidate={'language':language,'evidence_id':'source','source_url':'https://agency.example/phuket','observed_fact':'You sell Phuket holidays','relevance_to_offer':'We provide airport transfers'},founder_story={'story':'We operate transfers','offer':'Airport transfers'},sequence=[{'sequence_index':0,'channel':'email','angle':'business_reputation','day_offset':0}],business_id='b',user_id='u')
    assert result['status']=='ready',result
    assert result['source']=='deepseek'
    assert result['touches'][0]['subject']=='Airport transfers'
    assert 'Agency' in result['touches'][0]['text']
    assert sum(bool(call.get('review')) for call in calls)==expected_reviews
    assert result['semantic_reviews'][0]['passed'] is True


def test_search_creation_uses_one_http_post_and_applies_charge_cap(monkeypatch):
    from types import SimpleNamespace
    from services import prospecting_service, outreach_continuation
    observed={}
    def post(method,url,**kwargs):
        assert method=='POST'
        observed.update(kwargs)
        return SimpleNamespace(raise_for_status=lambda:None,json=lambda:{'data':{'id':'run','defaultDatasetId':'dataset'}})
    monkeypatch.setattr(prospecting_service,'ProspectingService',lambda **kwargs:SimpleNamespace(client=True,api_token='test',
        _actor_path_id=lambda:'x~y',_apify_request=post,_strip_none_values=lambda v:v,_build_run_input=lambda *a:{}))
    cfg=normalize_config({**config(),'max_search_calls':2,'search_budget_cents':100})
    assert outreach_continuation._start_search(cfg,0)['id']=='run'
    assert observed['params']['maxTotalChargeUsd']=='0.5'
    assert observed['params']['maxItems']==5 and observed['params']['timeout']==180


def test_riderra_pool_gate_requires_recent_shortage():
    from services import outreach_continuation, riderra_template_authorization_service
    class Cursor:
        def __init__(self,status): self.status=status
        def execute(self,query): assert "90 minutes" in query
        def fetchone(self): return {'status':self.status} if self.status else None
    for status in ('ready','daily_limit_reached','blocked',None):
        assert not outreach_continuation.riderra_pool_allows_search(Cursor(status),riderra_template_authorization_service.BUSINESS_ID)
    assert outreach_continuation.riderra_pool_allows_search(Cursor('shortage'),riderra_template_authorization_service.BUSINESS_ID)
    assert not outreach_continuation.riderra_pool_allows_search(Cursor('shortage'),'different-business')


def test_qualified_goal_is_not_twenty_model_calls():
    from services.outreach_continuation import normalize_config, preparation_report
    config = normalize_config({'audience': 'Indian travel agencies', 'offer': 'Phuket transfers',
        'queries': [{'query': 'travel agency', 'city': 'Delhi'}], 'target_count': 100,
        'agency_country': 'India', 'sold_destination': 'Phuket'})
    assert config['max_qualification_calls'] >= 100
    assert config['max_candidates'] > 100
    assert config['agency_country'] != config['sold_destination']
    state = {'lead_ids': [str(i) for i in range(100)],
             'qualifications': {'good': {'status': 'qualified'}, 'no_contact': {'status': 'qualified'}, 'bad': {'status': 'rejected'}},
             'verified_contact_workstream_ids': ['good', 'bad']}
    report = preparation_report(config, state)
    assert report['found'] == 100 and report['eligible'] == 1 and report['shortfall'] == 99
    assert report['model_cost'] is None


def test_chat_preview_pins_same_revision_and_terms_used_by_menu():
    from services.outreach_continuation import prepare_task_start
    stored = normalize_config({**config(), 'target_count': 100})
    class Cursor:
        def execute(self, sql, params):
            assert params == ('job', 'business', 'outreach_continue')
        def fetchone(self):
            return {'id': 'job', 'business_id': 'business', 'status': 'waiting_for_review',
                    'stage': 'Проверить', 'payload_json': stored, 'result_json': {}}
    preview = prepare_task_start(Cursor(), business_id='business', user_id='user', task_id='job', operation='start')
    assert preview['status'] == 'approval_required'
    assert preview['approval']['envelope']['revision'] == config_hash(stored)
    assert preview['approval']['envelope']['config'] == stored
    assert '100' in preview['chat_response'] and 'кредитов' in preview['chat_response']
    assert preview['approval']['envelope']['credit_terms_version'] == 1


def test_find_only_review_uses_search_wording_even_for_existing_task():
    from services.outreach_continuation import prepare_task_start, view
    stored = normalize_config({"audience": "Indian agencies selling Phuket", "mode": "find_only",
        "target_count": 10, "agency_country": "India", "sold_destination": "Phuket",
        "queries": [{"query": "travel agencies selling Phuket tours", "city": "India"}]})
    row = {"id": "job", "business_id": "business", "status": "waiting_for_review",
        "stage": "Проверьте условия и запустите подготовку", "payload_json": stored, "result_json": {}}
    class Cursor:
        def execute(self, sql, params): pass
        def fetchone(self): return row
    assert view(row)["stage"] == "Проверьте условия и запустите поиск"
    result = prepare_task_start(Cursor(), business_id="business", user_id="user", task_id="job", operation="start")
    assert "попыток подготовки" not in result["chat_response"]
    assert "50 проверок" in result["chat_response"]
    assert "USD" not in result["chat_response"]


def test_chat_confirm_rechecks_access_and_uses_shared_control(monkeypatch):
    from services import outreach_continuation, partnership_leads_service
    class Cursor:
        def execute(self, *args): pass
        def fetchone(self): return {'id': 'user', 'is_active': True}
    monkeypatch.setattr(outreach_continuation, 'continuation_enabled', lambda business: True)
    monkeypatch.setattr(outreach_continuation, 'actor_can_write', lambda *args: True)
    monkeypatch.setattr(partnership_leads_service, 'get_capability_access', lambda *args: {'allowed': True})
    calls = []
    monkeypatch.setattr(outreach_continuation, 'control_task', lambda cursor, **kw: calls.append(kw) or {'id': 'job'})
    envelope = {'business_id': 'b', 'task_id': 'job', 'operation': 'start', 'revision': 'pinned', 'credit_terms_version': 1}
    result = outreach_continuation.confirm_task_start(Cursor(), business_id='b', user_id='user', envelope=envelope)
    assert result['status'] == 'completed' and calls[0]['revision'] == 'pinned'
    monkeypatch.setattr(outreach_continuation, 'actor_can_write', lambda *args: False)
    assert outreach_continuation.confirm_task_start(Cursor(), business_id='b', user_id='user', envelope=envelope)['status'] == 'blocked'
    assert len(calls) == 1


def test_old_usd_approval_cannot_start_paid_search(monkeypatch):
    from services import outreach_continuation, partnership_leads_service
    class Cursor:
        def execute(self, *args): pass
        def fetchone(self): return {'id': 'user', 'is_active': True}
    monkeypatch.setattr(outreach_continuation, 'continuation_enabled', lambda business: True)
    monkeypatch.setattr(outreach_continuation, 'actor_can_write', lambda *args: True)
    monkeypatch.setattr(partnership_leads_service, 'get_capability_access', lambda *args: {'allowed': True})
    result = outreach_continuation.confirm_task_start(Cursor(), business_id='b', user_id='user',
        envelope={'business_id': 'b', 'task_id': 'job', 'operation': 'start', 'revision': 'old'})
    assert result['status'] == 'blocked' and result['blocked_reasons'] == ['credit_terms_changed']


def test_search_credit_quote_rounds_up_each_call_and_counts_checks():
    from services.outreach_credit_billing import actual_search_credits, credit_quote
    quoted = credit_quote(normalize_config({**config(), 'mode': 'find_only', 'target_count': 10,
        'search_budget_cents': 100, 'max_search_calls': 3, 'max_qualification_calls': 50}))
    assert quoted == {'search_each': 4, 'search_max': 12,
        'check_each': 1, 'check_max': 50, 'total_max': 62}
    shared = credit_quote(normalize_config({**config(), 'mode': 'find_only', 'target_count': 10,
        'billing_mode': 'shared_balance_actual', 'search_call_cap_cents': 50,
        'max_search_calls': 3, 'max_qualification_calls': 50}))
    assert shared['total_max'] == 65 and shared['search_each'] == 5
    assert actual_search_credits(0.21, shared['search_each']) == 3
    assert actual_search_credits(0, shared['search_each']) == 0
    with pytest.raises(ValueError, match='exceeds_reservation'):
        actual_search_credits(0.6, shared['search_each'])


def test_shared_balance_settles_receipt_and_releases_unused_hold(monkeypatch):
    from services import outreach_continuation, outreach_credit_billing
    cfg = normalize_config({**config(), 'mode': 'find_only', 'target_count': 10,
        'billing_mode': 'shared_balance_actual', 'search_call_cap_cents': 50})
    calls = []
    def finalize(cursor, row, **kwargs):
        calls.append(kwargs)
        return {'status': 'charged', 'charge_credits': kwargs['credits'],
                'release_credits': 5 - kwargs['credits']}
    monkeypatch.setattr(outreach_credit_billing, 'charge_step', finalize)
    state = {'search_run': {'usage_total_usd': 0.21}, 'search_credit_reservation_id': 'hold-1',
             'search_reservation_key': '1:1', 'search_credits_charged': 0}
    outreach_continuation.settle_actual_search(None, {'id': 'task'}, cfg, state)
    assert calls[0]['credits'] == 3
    assert state['search_credits_charged'] == 3
    assert 'search_credit_reservation_id' not in state
    assert 'search_reservation_key' not in state
    with pytest.raises(ValueError, match='search_cost_receipt_missing'):
        outreach_continuation.settle_actual_search(None, {'id': 'task'}, cfg,
            {'search_run': {}, 'search_credit_reservation_id': 'hold-2', 'search_reservation_key': '2:2'})
    assert len(calls) == 1


def test_find_only_does_not_require_offer_or_drafting():
    result = normalize_config({'audience': 'travel agencies', 'mode': 'find_only', 'target_count': 50,
                               'queries': [{'query': 'travel agency', 'city': 'Delhi'}]})
    assert result['mode'] == 'find_only' and result['offer'] == ''


def test_v2_one_city_can_expand_past_first_technical_batch():
    from services.outreach_continuation import normalize_config,search_call_limit,search_window_size
    config=normalize_config({'audience':'Travel agencies','mode':'find_only','target_count':100,
        'queries':[{'query':'travel agency','city':'Delhi'}],'max_search_calls':10})
    assert search_call_limit(config)==10
    assert [search_window_size(config,i) for i in range(3)]==[50,100,150]
    assert search_window_size(config,19)==config['max_candidates']
    legacy=normalize_config({'audience':'Agencies','offer':'Transfers','queries':[{'query':'travel','city':'Delhi'}]})
    assert search_call_limit(legacy)==1


def test_partial_search_cost_is_not_reported_as_zero_total():
    from services.outreach_continuation import preparation_report
    report=preparation_report({'target_count':100},{'search_calls':2,'search_cost_receipts':{'r1':0.12,'r2':None}})
    assert report['search_cost_usd'] is None and report['search_cost_known_usd']==0.12
    assert report['model_cost'] is None
    report=preparation_report({}, {'search_calls':2,'search_cost_receipts':{'r1':0.12,'r2':0.08}})
    assert report['search_cost_usd']==0.2 and report['search_cost_status']=='confirmed'
