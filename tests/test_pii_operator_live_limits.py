"""Explicit live limiter acceptance; only the disposable database and fake LLM."""

import os

import pytest

if os.getenv('PII_SYNTHETIC_RUNTIME_TEST') != '1':
    pytest.skip('Requires the explicit synthetic shared-runtime profile', allow_module_level=True)

from tests.test_pii_operator_acceptance import database, integrated, isolated_network, mock_provider, routes, scope, scoped_activation, send, service
from services.pii_protection.gateway import PIIProtectionError
from services.pii_protection.remote import RemoteProtectionService


def test_actual_http_quota_stops_web_before_llm(routes, service, monkeypatch):
    status = service._call('/v1/status', {})
    assert status['business_protect_rps'] == 4
    def exhausted(text, scope, *args, **kwargs):
        # Exhaust immediately before the outbound attempt: SQL/router setup can
        # otherwise take long enough for the real token bucket to refill.
        payload = {'scope': {'business_id': scope.business_id, 'user_id': scope.user_id,
                             'session_id': scope.session_id},
                   'text': 'Email: synthetic-limit@example.invalid', 'policy': 'private',
                   'allowed_tokens': [], 'public_context': []}
        for _ in range(30):
            try:
                service._call('/v1/protect', payload)
            except PIIProtectionError:
                import sys
                assert str(sys.exc_info()[1]) == 'PII_RUNTIME_RATE_LIMITED'
                break
        else:
            pytest.fail('The real shared runtime must enforce the business quota')
        return RemoteProtectionService.protect(service, text, scope, *args, **kwargs)
    monkeypatch.setattr(service, 'protect', exhausted)
    result = send(routes, 'web', 'Full name: Mira Exampleton; email: mira@example.invalid')
    assert routes[2] == [] and routes[4] == []
    assert result['planner_failed'] and 'позже' in result['chat_response']
    assert result['external_writes_performed'] is False
