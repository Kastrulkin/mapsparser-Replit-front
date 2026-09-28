import pytest
from services.outreach_continuation import normalize_config, config_hash
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


def test_search_creation_disables_sdk_post_retry_and_applies_charge_cap(monkeypatch):
    from types import SimpleNamespace
    from decimal import Decimal
    import apify_client
    from services import prospecting_service, outreach_continuation
    observed={}
    def start(**kwargs):
        observed.update(kwargs)
        return {'id':'run','defaultDatasetId':'dataset'}
    def client(token,**kwargs):
        assert kwargs['max_retries']==0
        return SimpleNamespace(actor=lambda name:SimpleNamespace(start=start))
    monkeypatch.setattr(apify_client,'ApifyClient',client)
    monkeypatch.setattr(prospecting_service,'ProspectingService',lambda **kwargs:SimpleNamespace(client=True,api_token='test',actor_id='x~y',_strip_none_values=lambda v:v,_build_run_input=lambda *a:{}))
    cfg=normalize_config({**config(),'max_search_calls':2,'search_budget_cents':100})
    assert outreach_continuation._start_search(cfg,0)['id']=='run'
    assert observed['max_total_charge_usd']==Decimal('0.5')
    assert observed['max_items']==5 and observed['timeout_secs']==180


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
