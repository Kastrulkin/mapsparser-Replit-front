import json
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from services.openclaw_website_reader import read_business_website


@pytest.fixture
def route(tmp_path, monkeypatch):
    config = tmp_path / 'read.json'
    config.write_text(json.dumps({'enabled': True, 'business_ids': ['branch']}))
    monkeypatch.setenv('LOCALOS_WEB_READ_CONFIG', str(config))
    monkeypatch.setenv('OPENCLAW_SANDBOX_BRIDGE_URL', 'http://bridge:8091/capabilities')
    monkeypatch.setenv('OPENCLAW_SANDBOX_BRIDGE_TOKEN', 'bridge-secret')
    monkeypatch.setitem(sys.modules, 'core.auth_helpers', SimpleNamespace(
        verify_business_access=lambda *a: (True, 'owner')))
    monkeypatch.setattr('core.outbound_network.validate_public_http_url', lambda value: value)
    cursor = Mock()
    cursor.fetchone.return_value = (False,)
    return cursor


def test_disabled_business_has_no_external_call(route, monkeypatch):
    post = Mock()
    monkeypatch.setattr('services.openclaw_website_reader.requests.post', post)
    assert read_business_website(route, 'user', 'other', 'https://example.com') is None
    post.assert_not_called()


def test_tuple_access_denied_prevents_network(route, monkeypatch):
    monkeypatch.setitem(sys.modules, 'core.auth_helpers', SimpleNamespace(
        verify_business_access=lambda *a: (False, None)))
    post = Mock()
    monkeypatch.setattr('services.openclaw_website_reader.requests.post', post)
    with pytest.raises(PermissionError):
        read_business_website(route, 'user', 'branch', 'https://example.com')
    post.assert_not_called()


def test_read_is_bounded_no_redirects_and_provenance_retained(route, monkeypatch):
    source = {'url': 'https://example.com', 'final_url': 'https://example.com/',
              'fetched_at': '2026-10-12T10:00:00Z', 'untrusted': True,
              'text': 'external text', 'provider': 'openclaw.web_fetch'}
    post = Mock(return_value=SimpleNamespace(status_code=200, json=lambda: {'ok': True, 'source': source}))
    monkeypatch.setattr('services.openclaw_website_reader.requests.post', post)
    result = read_business_website(route, 'user', 'branch', 'https://example.com')
    assert result['text'] == 'external text'
    assert post.call_args.kwargs['allow_redirects'] is False
    assert post.call_args.kwargs['json']['business_id'] == 'branch'


@pytest.mark.parametrize('status', [302, 401, 500, 504])
def test_failure_does_not_fallback(route, monkeypatch, status):
    post = Mock(return_value=SimpleNamespace(status_code=status))
    monkeypatch.setattr('services.openclaw_website_reader.requests.post', post)
    with pytest.raises(ValueError):
        read_business_website(route, 'user', 'branch', 'https://example.com')
    assert post.call_count == 1
