import base64
import types
import pytest
from services import outreach_web_search as web, outreach_continuation as continuation

@pytest.fixture
def yandex(monkeypatch):
    monkeypatch.setenv('OUTREACH_WEB_SEARCH_ENABLED','true')
    monkeypatch.setenv('YANDEX_SEARCH_API_KEY','test-secret')
    monkeypatch.setenv('YANDEX_SEARCH_FOLDER_ID','folder')
    monkeypatch.setenv('YANDEX_SEARCH_PAID_REQUESTS_ENABLED','true')
    for provider in ('TAVILY','EXA'):
        monkeypatch.delenv(provider+'_API_KEY',raising=False)

def response(xml,code=200):
    return types.SimpleNamespace(status_code=code,json=lambda:{'rawData':base64.b64encode(xml.encode()).decode()})

def test_key_and_explicit_consent_required(monkeypatch,yandex):
    monkeypatch.setattr(web.requests,'post',lambda *a,**k:pytest.fail('No request allowed'))
    with pytest.raises(RuntimeError,match='paid_approval_required'):web.search('suppliers','Kazan',3,provider='yandex')
    monkeypatch.setenv('YANDEX_SEARCH_PAID_REQUESTS_ENABLED','false')
    with pytest.raises(RuntimeError,match='paid_approval_required'):web.search('suppliers','Kazan',3,provider='yandex',paid_search_approved=True)
    assert not web.configured('yandex')

def test_yandex_never_enters_free_fallback(monkeypatch,yandex):
    monkeypatch.setattr(web.requests,'post',lambda *a,**k:pytest.fail('No request allowed'))
    assert web._providers()==[]
    with pytest.raises(RuntimeError,match='not_configured'):web.search('suppliers','Kazan',3)

def test_real_api_contract_and_xml_result_normalization(monkeypatch,yandex):
    calls=[]
    def post(url,**kwargs):
        calls.append((url,kwargs))
        return response('<yandexsearch><response><results><group><doc><url>https://supplier.example/contact</url><title>A <hlword>Supplier</hlword></title><passages><passage>Public email</passage></passages></doc><doc><url>https://supplier.example/</url><title>Duplicate</title></doc></group></results></response></yandexsearch>')
    monkeypatch.setattr(web.requests,'post',post)
    result=web.search('suppliers','Kazan',3,provider='yandex',paid_search_approved=True)
    assert len(calls)==1 and len(result)==1
    assert calls[0][0]=='https://searchapi.api.cloud.yandex.net/v2/web/search'
    assert calls[0][1]['json']['folderId']=='folder'
    assert calls[0][1]['json']['query']['searchType']=='SEARCH_TYPE_COM'
    assert calls[0][1]['json']['responseFormat']=='FORMAT_XML'
    assert result[0]['name']=='A Supplier'
    assert result[0]['source_provider']=='yandex_web' and result[0]['qualification_required']

@pytest.mark.parametrize('xml',['bad XML','<!DOCTYPE foo [<!ENTITY x "secret">]><yandexsearch>&x;</yandexsearch>'])
def test_malformed_or_entity_xml_rejected(monkeypatch,yandex,xml):
    monkeypatch.setattr(web.requests,'post',lambda *a,**k:response(xml))
    with pytest.raises(RuntimeError,match='invalid_response'):web.search('x','y',3,provider='yandex',paid_search_approved=True)

def test_rate_limit_is_not_retried_or_fallback(monkeypatch,yandex):
    calls=[]
    monkeypatch.setattr(web.requests,'post',lambda *a,**k:(calls.append(a),response('',429))[1])
    with pytest.raises(RuntimeError,match='rate_limited'):web.search('x','y',3,provider='yandex',paid_search_approved=True)
    assert len(calls)==1

def test_provider_changes_approval_version():
    raw={'audience':'Suppliers','search_geography':['Kazan'],'mode':'find_only','target_count':3}
    original=continuation.normalize_config(raw)
    yandex_config=continuation.normalize_config({**raw,'web_search_provider':'yandex'})
    assert continuation.config_hash(original)!=continuation.config_hash(yandex_config)
    assert continuation.normalize_config(yandex_config)['web_search_provider']=='yandex'

