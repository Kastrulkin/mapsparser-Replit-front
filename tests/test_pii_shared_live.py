"""Explicit synthetic-only live profile; all LLM HTTP endpoints stay loopback mocks."""

import os
import socket
import sys
import time

import pytest

if os.getenv('PII_SYNTHETIC_RUNTIME_TEST') != '1':
    pytest.skip('Requires the isolated shared-runtime synthetic profile', allow_module_level=True)

from tests.test_pii_protection import integrated, mock_provider, scope
from tests.test_pii_protection import test_all_200_scenarios_http_with_live_redis as test_shared_200_scenarios_both_http_adapters
from tests.test_pii_protection import test_real_adapter_outgoing_payload_and_display_restoration as test_shared_http_display_restoration
from services.pii_protection.remote import RemoteProtectionService
from services.pii_protection.runtime_config import CLIENT_CONFIG


@pytest.fixture
def service():
    client = RemoteProtectionService.from_file(CLIENT_CONFIG)
    protect = client.protect
    last = [0.0]
    def paced(*args, **kwargs):
        # Pace the synthetic corpus explicitly; never retry failed real requests.
        time.sleep(max(0, 0.28 - (time.monotonic() - last[0])))
        last[0] = time.monotonic()
        return protect(*args, **kwargs)
    client.protect = paced
    return client


@pytest.fixture(autouse=True)
def private_network_only(monkeypatch):
    connect, lookup = socket.socket.connect, socket.getaddrinfo
    addresses = {v[4][0] for v in lookup('localos-pii-runtime', 8765, type=socket.SOCK_STREAM)}

    def checked_connect(connection, address):
        if not isinstance(address, tuple) or not (address[0] == '127.0.0.1' or
                                                 address[0] in addresses and address[1] == 8765):
            raise AssertionError('Only private runtime and loopback mocks are allowed')
        return connect(connection, address)

    def checked_lookup(host, *args, **kwargs):
        if host not in {'127.0.0.1', 'localos-pii-runtime'}:
            raise AssertionError('External DNS disabled')
        return lookup(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, 'connect', checked_connect)
    monkeypatch.setattr(socket, 'getaddrinfo', checked_lookup)


def test_client_process_never_loads_nlp(service, scope):
    protected = service.protect('Email: synthetic-client@example.invalid', scope)
    assert 'synthetic-client@example.invalid' not in protected.text
    assert not any(name in sys.modules for name in ['spacy', 'piighost', 'presidio_analyzer'])
    status = service._call('/v1/status', {})
    assert status['model_lanes'] == 1 and status['synthetic_only'] is True
