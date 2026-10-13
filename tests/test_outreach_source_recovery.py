import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock

import pytest


@pytest.fixture
def bridge():
    path = Path(__file__).resolve().parents[1] / 'integrations/openclaw/outreach_mvp/web_read.py'
    spec = importlib.util.spec_from_file_location('source_bridge', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_canonical_alias_and_known_pages_keep_contact_evidence(bridge, monkeypatch):
    monkeypatch.setattr(bridge, 'public_url', lambda value: value)
    calls = []
    def read(method, path, headers, payload):
        url = payload['url']
        calls.append(url)
        text = '\n'.join('Generic service information for visitors.' for _ in range(25))
        if url.endswith('/contact'):
            text = 'A travel agency in India. Contact hello@example.org for Phuket tours.'
        return 200, {'source': {'url': url, 'final_url': url.replace('www.example.org', 'example.org'), 'text': text}}
    monkeypatch.setattr(bridge, 'handle_web_read', read)
    result = bridge.research_website({'url': 'https://www.example.org/', 'business_id': 'b', 'job_id': 'j', 'requirements': ['India', 'Phuket'], 'known_source_urls': ['https://example.org/contact']}, {})
    assert len(calls) == 2
    assert result['contacts'][0]['source_url'] == 'https://example.org/contact'
    assert any('Phuket' in fact['fact'] for fact in result['facts'])
    assert all(fact['untrusted'] for fact in result['facts'])
    assert len(result['facts']) <= 20


@pytest.mark.parametrize('url', ['https://other.org/contact', 'https://example.org.evil.test/', 'https://other.example.org/'])
def test_known_source_cannot_expand_domain_access(bridge, monkeypatch, url):
    monkeypatch.setattr(bridge, 'public_url', lambda value: value)
    read = Mock()
    monkeypatch.setattr(bridge, 'handle_web_read', read)
    with pytest.raises(ValueError, match='invalid_known_sources'):
        bridge.research_website({'url': 'https://example.org/', 'known_source_urls': [url]}, {})
    assert not read.called


def test_five_page_budget_with_many_links_and_known_sources(bridge, monkeypatch):
    monkeypatch.setattr(bridge, 'public_url', lambda value: value)
    calls = []
    def read(method, path, headers, payload):
        calls.append(payload['url'])
        text = '\n'.join(f'[About](https://example.org/about/{i})' for i in range(20)) + '\n[Contact](https://example.org/contact)'
        return 200, {'source': {'url': payload['url'], 'final_url': payload['url'], 'text': text}}
    monkeypatch.setattr(bridge, 'handle_web_read', read)
    bridge.research_website({'url': 'https://example.org/', 'business_id': 'b', 'job_id': 'j', 'known_source_urls': ['https://example.org/about/prior']}, {})
    assert len(calls) == 5
    assert calls[1] == 'https://example.org/contact'


def test_readiness_is_renewed_only_after_real_success(bridge, monkeypatch, tmp_path):
    path = tmp_path / 'config.json'
    config = {'enabled': True, 'business_ids': ['b'], 'verified_at': '2026-01-01T00:00:00Z'}
    path.write_text(json.dumps(config))
    monkeypatch.setattr(bridge, 'CONFIG_PATH', path)
    probe = Mock(return_value={'ok': True, 'result': {'details': {'status': 200, 'finalUrl': 'https://localos.pro/robots.txt', 'text': 'User-agent: Googlebot'}}})
    monkeypatch.setattr(bridge, 'invoke_fetch', probe)
    assert bridge.reverify_fetch(config)
    saved = json.loads(path.read_text())
    assert saved['business_ids'] == ['b'] and saved['enabled'] is True
    assert saved['verified_at'] != '2026-01-01T00:00:00Z'
    assert probe.call_args.args == ('https://localos.pro/robots.txt',)
    assert not bridge.reverify_fetch(config)
    assert probe.call_count == 1


def test_failed_readiness_probe_does_not_extend_verification(bridge, monkeypatch, tmp_path):
    config = {'verified_at': '2026-01-01T00:00:00Z'}
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(config))
    monkeypatch.setattr(bridge, 'CONFIG_PATH', path)
    monkeypatch.setattr(bridge, 'invoke_fetch', Mock(side_effect=RuntimeError('synthetic failure')))
    assert not bridge.reverify_fetch(config)
    assert json.loads(path.read_text()) == config


def test_foreign_business_cannot_trigger_read_or_reverification(bridge, monkeypatch, tmp_path):
    path = tmp_path / 'config.json'
    path.write_text(json.dumps({'enabled': True, 'verified_at': '2026-01-01T00:00:00Z', 'business_ids': ['b']}))
    monkeypatch.setattr(bridge, 'CONFIG_PATH', path)
    monkeypatch.setenv('OPENCLAW_INTERNAL_TOKEN', 'synthetic')
    verify = Mock()
    monkeypatch.setattr(bridge, 'reverify_fetch', verify)
    status, result = bridge.handle_web_read('POST', '/capabilities/partners.research_website', {'X-OpenClaw-Internal-Token': 'synthetic'}, {'business_id': 'foreign'})
    assert status == 403 and not verify.called


def test_contact_evidence_rejects_manual_and_unsourced_contacts():
    from services.outreach_continuation import verified_contact_evidence
    cursor = Mock()
    cursor.fetchall.return_value = [
        {'id': 'a', 'value': 'public@example.org', 'source_url': 'https://example.org/contact', 'verification_status': 'confirmed_source'},
        {'id': 'b', 'value': 'manual@example.org', 'source_url': 'https://example.org/', 'verification_status': 'manual'},
        {'id': 'c', 'value': 'unsourced@example.org', 'source_url': '', 'verification_status': 'verified'},
    ]
    facts = verified_contact_evidence(cursor, 'ws', 'business')
    assert len(facts) == 1 and facts[0]['id'] == 'contact:a'
    assert 'delivery has not been verified' in facts[0]['fact']
    assert cursor.execute.call_args.args[1] == ('ws', 'business')
    assert 'stale_after>NOW()' in cursor.execute.call_args.args[0]


def test_existing_map_company_is_reused_by_site(monkeypatch):
    import sys, types
    from services.outreach_continuation import import_source_urls, normalize_config
    module = types.ModuleType('api.prospecting.partner_discovery')
    module._insert_partnership_lead_if_new = Mock()
    module._ensure_imported_partnership_workstream = Mock(return_value='existing-ws')
    monkeypatch.setitem(sys.modules, 'api.prospecting.partner_discovery', module)
    cursor = Mock()
    cursor.fetchall.return_value = [{'id': 'existing-lead', 'website': 'https://www.example.org/'}]
    config = normalize_config({'source_urls': ['https://example.org/'], 'audience': 'Supplier', 'offer': 'A quote', 'language': 'en'})
    state = {}
    import_source_urls(cursor, {'business_id': 'b', 'user_id': 'u', 'id': 'task'}, config, state)
    assert not module._insert_partnership_lead_if_new.called
    assert state['lead_ids'] == ['existing-lead'] and state['reused_companies'] == 1



def test_unique_named_company_wins_over_historical_domain_stub():
    from services.outreach_continuation import select_source_company
    company={'id':'canonical','name':'EWS Holidays','website':'https://www.ewsholidays.com/'}
    stub={'id':'stub','name':'www.ewsholidays.com','website':'https://www.ewsholidays.com/'}
    assert select_source_company([stub,company],company['website']) is company
    assert select_source_company([company,stub],company['website']) is company


def test_two_named_companies_still_require_owner_decision():
    from services.outreach_continuation import select_source_company
    with pytest.raises(ValueError,match='ambiguous_existing_company'):
        select_source_company([{'id':'one','name':'First agency'}, {'id':'two','name':'Second agency'}], 'https://example.org/')
