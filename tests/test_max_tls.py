import hashlib
import ssl
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests
from core import outbound_network
from services.max_tls import max_ca_file, max_ssl_context
from services.max_transport import MaxTransport


def test_default_max_ca_is_the_existing_verified_public_root(monkeypatch):
    monkeypatch.delenv('MAX_CA_BUNDLE', raising=False)
    certificate = Path(max_ca_file()).read_text()
    assert hashlib.sha256(ssl.PEM_cert_to_DER_cert(certificate)).hexdigest() == 'd26d2d0231b7c39f92cc738512ba54103519e4405d68b5bd703e9788ca8ecf31'
    context = max_ssl_context()
    assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
    assert context.cert_store_stats()['x509_ca'] > 1
    assert requests.Session().verify is True


def test_max_transport_uses_scoped_ca_and_honors_explicit_bundle(monkeypatch, tmp_path):
    ca = tmp_path / 'max-ca.pem'
    ca.write_bytes(Path(max_ca_file()).read_bytes())
    monkeypatch.setenv('MAX_CA_BUNDLE', str(ca))
    session = SimpleNamespace()
    MaxTransport('synthetic-token', session=session)
    assert session.verify == str(ca)
    assert requests.Session().verify is True
    monkeypatch.setenv('MAX_CA_BUNDLE', str(tmp_path / 'missing'))
    with pytest.raises(ValueError): max_ca_file()


@pytest.mark.parametrize('method', ['GET', 'POST'])
def test_scoped_tls_keeps_pinning_hostname_and_no_redirects(monkeypatch, method):
    context = max_ssl_context()
    captured = {}
    class Response:
        status = 200
        headers = {}
        def read(self, limit): return b'{}'
        def close(self): pass
        def release_conn(self): pass
    class Pool:
        def __init__(self, *args, **kwargs): captured['args'] = args; captured['tls'] = kwargs
        def urlopen(self, *args, **kwargs): captured['request'] = kwargs; return Response()
        def close(self): pass
        def clear(self): pass
    monkeypatch.setattr(outbound_network, '_public_addresses_for_url', lambda url: (url, ['93.184.216.34'], 443))
    monkeypatch.setattr(outbound_network, 'resolve_outbound_http_proxy', lambda: '')
    monkeypatch.setattr(outbound_network.urllib3, 'HTTPSConnectionPool', Pool)
    monkeypatch.setattr(outbound_network.urllib3, 'PoolManager', Pool)
    if method == 'GET': outbound_network.public_pinned_get('https://upload.max.ru/file', {}, ssl_context=context)
    else: outbound_network.public_pinned_https_post('https://upload.max.ru/file', b'media', {}, ssl_context=context)
    assert captured['tls']['ssl_context'] is context
    assert captured['tls']['cert_reqs'] == 'CERT_REQUIRED'
    assert captured['tls']['assert_hostname'] == captured['tls']['server_hostname'] == 'upload.max.ru'
    assert captured['request']['redirect'] is False
    assert 'Authorization' not in captured['request']['headers']


def test_max_download_passes_the_scoped_context(monkeypatch):
    from services import max_inputs
    def fetch(url, headers, **kwargs):
        assert kwargs['ssl_context'].verify_mode == ssl.CERT_REQUIRED
        assert headers == {}
        return SimpleNamespace(status_code=200, body=b'image', headers={'content-type': 'image/jpeg'})
    monkeypatch.setattr(max_inputs, 'public_pinned_get', fetch)
    assert max_inputs.download_input('https://upload.max.ru/photo') == (b'image', 'image/jpeg')


def test_max_scoped_context_never_allows_private_network_downloads():
    with pytest.raises(ValueError):
        outbound_network.public_pinned_get('https://127.0.0.1/private', {}, ssl_context=max_ssl_context())


def test_max_explicit_ca_survives_generic_requests_environment(monkeypatch):
    monkeypatch.setenv('REQUESTS_CA_BUNDLE', '/generic-unrelated-ca.pem')
    captured = {}
    class Adapter(requests.adapters.BaseAdapter):
        def send(self, request, **kwargs):
            captured.update(kwargs)
            response = requests.Response()
            response.status_code = 200
            response._content = b'{"user_id":123}'
            return response
        def close(self): pass
    session = requests.Session()
    session.mount('https://', Adapter())
    assert MaxTransport('synthetic-token', session=session).call('GET', '/me') == {'user_id':123}
    assert captured['verify'] == max_ca_file()
    assert captured['verify'] != '/generic-unrelated-ca.pem'
