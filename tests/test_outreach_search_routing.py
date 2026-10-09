import sys,types
from decimal import Decimal
import pytest
from services import outreach_continuation as c
from services import outreach_web_search as web

@pytest.fixture
def billing(monkeypatch):
    monkeypatch.setitem(sys.modules,'services.operator_paid_actions',types.SimpleNamespace(APIFY_CREDIT_MULTIPLIER=Decimal('10')))
    from services import outreach_credit_billing
    return outreach_credit_billing

def config(source=None):
    raw={'audience':'Travel agencies','requirements':['Sells Phuket tours','Confirmed email'],'search_geography':['India'],'offer':'Transfers','mode':'prepare_only','target_count':3}
    if source: raw['search_source']=source
    return c.normalize_config(raw)

def test_new_and_legacy_search_default_to_web():
    assert config()['search_source']=='web'
    assert config('maps')['search_source']=='maps'
    with pytest.raises(ValueError): config('apify')

def test_unconfigured_web_never_calls_apify(monkeypatch):
    monkeypatch.delenv('BRAVE_SEARCH_API_KEY',raising=False)
    monkeypatch.setenv('OUTREACH_WEB_SEARCH_ENABLED','true')
    monkeypatch.setitem(sys.modules,'services.prospecting_service',None)
    with pytest.raises(RuntimeError,match='web_search_not_configured'): c._start_search(config(),0)

def test_api_key_alone_does_not_enable_paid_search(monkeypatch):
    monkeypatch.setenv('BRAVE_SEARCH_API_KEY','test')
    monkeypatch.delenv('OUTREACH_WEB_SEARCH_ENABLED',raising=False)
    assert web.configured() is False

def test_map_preview_has_separate_warning_and_new_approval(billing):
    result=c.prepare_new_task_approval(config('maps'),business_id='biz')
    assert 'Поиск на картах оплачивается отдельно' in result['chat_response']
    assert result['search_warning']
    assert result['approval']['envelope']['credit_terms_version']==3
    assert result['approval']['envelope']['search_policy_version']==1
    assert result['config']['search_source']=='maps'

def test_unconfigured_web_preview_has_no_launch_confirmation(monkeypatch,billing):
    monkeypatch.delenv('BRAVE_SEARCH_API_KEY',raising=False)
    result=c.prepare_new_task_approval(config(),business_id='biz')
    assert result['status']=='blocked'
    assert result['approval'] is None
    assert result['reason_code']=='web_search_not_configured'

def test_source_is_part_of_approved_version():
    assert c.config_hash(config()) != c.config_hash(config('maps'))

def test_web_run_polls_saved_results_without_another_request(monkeypatch):
    monkeypatch.setattr(web,'search',lambda *args:[{'name':'Agency','url':'https://agency.example'}])
    run=c._start_search(config(),0)
    monkeypatch.setattr(web,'search',lambda *args:pytest.fail('Second external request'))
    monkeypatch.setitem(sys.modules,'services.prospecting_service',None)
    assert c._poll_search(run,15)[0]['name']=='Agency'

def test_web_search_has_separate_credit_quote(billing):
    assert billing.credit_quote(config())['search_each']==1
    assert billing.credit_quote(config('maps'))['search_each']>1

@pytest.fixture
def providers(monkeypatch):
    monkeypatch.setenv('OUTREACH_WEB_SEARCH_ENABLED','true')
    for name in ('TAVILY','EXA'):
        monkeypatch.setenv(name+'_API_KEY','test')
        monkeypatch.setenv(name+'_FREE_ONLY_VERIFIED','true')

def response(code=200, data=None):
    return types.SimpleNamespace(status_code=code,json=lambda:data or {})

def usage(used=0, paygo=0, plan='Researcher'):
    return response(data={'key':{'limit':1000,'usage':used},'account':{'current_plan':plan,'plan_limit':1000,'plan_usage':used,'paygo_limit':paygo}})

def test_web_results_are_unqualified_and_deduplicated(monkeypatch,providers):
    monkeypatch.setattr(web.requests,'get',lambda *a,**k:usage())
    calls=[]
    def post(url,**kw):
        calls.append((url,kw))
        return response(data={'results':[{'title':'Agency','url':'https://agency.example/phuket'},{'title':'Contact','url':'https://agency.example/contact'},{'title':'Invalid','url':'javascript:alert(1)'}]})
    monkeypatch.setattr(web.requests,'post',post)
    items=web.search('agency','India',15)
    assert len(items)==1 and items[0]['qualification_required']
    assert items[0]['source_provider']=='tavily_web'
    assert 'phone' not in items[0]
    assert len(calls)==1 and calls[0][1]['json']['search_depth']=='basic'
    assert calls[0][1]['json']['auto_parameters'] is False

def test_exhausted_tavily_switches_to_exa(monkeypatch,providers):
    monkeypatch.setattr(web.requests,'get',lambda *a,**k:usage(1000))
    calls=[]
    def post(url,**kw):
        calls.append(url)
        assert 'contents' not in kw['json']
        return response(data={'results':[{'title':'Supplier','url':'https://supplier.example'}]})
    monkeypatch.setattr(web.requests,'post',post)
    assert web.search('supplier','Kazan',15)[0]['source_provider']=='exa_web'
    assert calls==['https://api.exa.ai/search']

def test_both_quotas_exhausted_stops(monkeypatch,providers):
    monkeypatch.setattr(web.requests,'get',lambda *a,**k:usage(1000))
    monkeypatch.setattr(web.requests,'post',lambda *a,**k:response(402))
    with pytest.raises(RuntimeError,match='web_search_free_quota_exhausted'):
        web.search('agency','India',3)

@pytest.mark.parametrize('code,error',[(401,'access_denied'),(429,'rate_limited'),(500,'failed')])
def test_no_fallback_for_ambiguous_or_access_errors(monkeypatch,providers,code,error):
    monkeypatch.setattr(web.requests,'get',lambda *a,**k:usage())
    calls=[]
    def post(url,**kw):
        calls.append(url)
        return response(code)
    monkeypatch.setattr(web.requests,'post',post)
    with pytest.raises(RuntimeError,match='web_search_'+error):web.search('agency','India',3)
    assert calls==['https://api.tavily.com/search']

@pytest.mark.parametrize('paygo,plan',[(10,'Researcher'),(0,'Bootstrap')])
def test_paid_account_is_not_used(monkeypatch,providers,paygo,plan):
    monkeypatch.setattr(web.requests,'get',lambda *a,**k:usage(paygo=paygo,plan=plan))
    monkeypatch.setattr(web.requests,'post',lambda *a,**k:pytest.fail('Paid call'))
    with pytest.raises(RuntimeError,match='free_plan_unverified'):web.search('agency','India',3)

def test_keys_without_free_account_verification_are_disabled(monkeypatch,providers):
    monkeypatch.delenv('TAVILY_FREE_ONLY_VERIFIED')
    monkeypatch.delenv('EXA_FREE_ONLY_VERIFIED')
    assert not web.configured()

def test_provider_quota_response_switches_only_once(monkeypatch,providers):
    monkeypatch.setattr(web.requests,'get',lambda *a,**k:usage())
    calls=[]
    def post(url,**kw):
        calls.append(url)
        return response(432 if 'tavily' in url else 200,{'results':[]})
    monkeypatch.setattr(web.requests,'post',post)
    assert web.search('agency','India',3)==[]
    assert len(calls)==2

def test_empty_results_do_not_switch(monkeypatch,providers):
    monkeypatch.setattr(web.requests,'get',lambda *a,**k:usage())
    calls=[]
    def post(url,**kw):
        calls.append(url)
        return response(data={'results':[]})
    monkeypatch.setattr(web.requests,'post',post)
    assert web.search('agency','India',3)==[]
    assert len(calls)==1
