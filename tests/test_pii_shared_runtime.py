"""Shared-runtime contract: no production credentials, models or data."""

import datetime
import json
import ssl
import threading
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from cryptography.fernet import Fernet
from werkzeug.serving import make_server

from services.pii_protection import gateway
from services.pii_protection.engines import EngineResult, Finding
from services.pii_protection.gateway import MemoryStore, PIIProtectionError, ProtectionService, Scope
from services.pii_protection.remote import RemoteProtectionService
from services.pii_protection.runtime_config import read_secret_json
from services.pii_protection.runtime_server import create_app


AUTH = 'synthetic-token-' + 'a' * 50
SCOPE = Scope('synthetic-business', 'synthetic-user', 'synthetic-session')


class Engine:
    def __init__(self):
        self.calls = 0
        self.entered = threading.Event()
        self.release = None

    def scan(self, text):
        self.calls += 1
        self.entered.set()
        if self.release is not None:
            self.release.wait(5)
        value = 'person@example.invalid'
        start = text.find(value)
        return EngineResult(text, [] if start < 0 else [Finding(start, start + len(value), 'EMAIL')])


@pytest.fixture
def service():
    return ProtectionService(Engine(), MemoryStore(), Fernet.generate_key())


@pytest.fixture
def app(service):
    application = create_app({'bearer_token': AUTH, 'recognition_timeout_seconds': 10, 'synthetic_only': True,
                              'protect_rps':100,'protect_burst':50,'business_protect_rps':100,'business_protect_burst':50}, service)
    yield application
    application.extensions['pii_watchdog_stop'].set()


def payload(**changes):
    return {'scope': {'business_id': SCOPE.business_id, 'user_id': SCOPE.user_id, 'session_id': SCOPE.session_id},
            'text': 'Email: person@example.invalid', 'policy': 'private',
            'allowed_tokens': [], 'public_context': [], **changes}


def post(app, path='/v1/protect', value=None, auth=AUTH):
    return app.test_client().post(path, json=payload() if value is None else value,
                                  headers={'Authorization': 'Bearer ' + auth})


def test_auth_denies_before_detection_or_storage(app, service):
    result = post(app, auth='wrong')
    assert result.status_code == 401
    assert service.engine.calls == 0 and not service.store.values
    assert b'person@example.invalid' not in result.data


def test_synthetic_cohort_denies_non_synthetic_scope_before_scan(app, service):
    result = post(app, value=payload(scope={'business_id': 'unapproved-example', 'user_id': 'not-real', 'session_id': 'not-real'}))
    assert result.json == {'error': 'PII_RUNTIME_COHORT_DENIED'}
    assert service.engine.calls == 0 and not service.store.values


@pytest.mark.parametrize('change', [
    {'scope': {}}, {'extra': 'value'}, {'policy': 'unknown'}, {'allowed_tokens': ['forged']},
    {'text': 'x' * 100001}, {'public_context': [{}]}, {'public_context': {'business_id': 'spoof'}},
])
def test_invalid_contract_fails_without_echo(app, service, change):
    result = post(app, value=payload(**change))
    assert result.status_code == 400
    assert set(result.json) == {'error'}
    assert 'person@example.invalid' not in result.get_data(as_text=True)
    assert not service.store.values


def test_request_size_bound(app, service):
    result = post(app, value=payload(text='x' * (513 * 1024)))
    assert result.status_code == 413 and service.engine.calls == 0


def test_default_admission_blocks_before_scan_and_mapping(service):
    app = create_app({'bearer_token': AUTH, 'synthetic_only': True}, service)
    try:
        for _ in range(4):
            accepted = post(app)
            assert accepted.status_code == 200
        calls = service.engine.calls
        result = post(app)
        assert result.status_code == 429 and result.json == {'error': 'PII_RUNTIME_RATE_LIMITED'}
        assert result.headers['Retry-After'] == '1' and service.engine.calls == calls
        restored = post(app, '/v1/resolve', {'scope': payload()['scope'], 'token': accepted.json['issued'][0]})
        assert restored.status_code == 200 and restored.json['value'] == 'person@example.invalid'
        status = post(app, '/v1/status', {}).json
        assert status['rate_limited'] >= 1 and status['protect_rps'] == 10 and status['business_protect_rps'] == 4
    finally:
        app.extensions['pii_watchdog_stop'].set()


def test_real_initialization_warms_both_languages_before_readiness(service, monkeypatch):
    from types import SimpleNamespace
    from services.pii_protection import runtime_server, engines
    service.store.client = SimpleNamespace(ping=lambda: True)
    monkeypatch.setattr(engines, 'make_engine', lambda _: service.engine)
    monkeypatch.setattr(runtime_server, 'RedisStore', lambda _: service.store)
    monkeypatch.setattr(runtime_server, 'ProtectionService', lambda *args: service)
    app = create_app({'bearer_token': AUTH, 'mapping_key': Fernet.generate_key().decode(), 'redis_url': 'synthetic-unused'})
    try:
        assert service.engine.calls == 2 and service.store.values
        assert app.test_client().get('/health').status_code == 200
        status = post(app, '/v1/status', {}).json
        assert status['warmup_completed'] and status['protect_ok'] == 0
    finally:
        app.extensions['pii_watchdog_stop'].set()


def test_failed_warmup_cannot_report_ready_or_echo_payload(service, monkeypatch):
    from types import SimpleNamespace
    from services.pii_protection import runtime_server, engines
    service.store.client = SimpleNamespace(ping=lambda: True)
    monkeypatch.setattr(engines, 'make_engine', lambda _: service.engine)
    monkeypatch.setattr(runtime_server, 'RedisStore', lambda _: service.store)
    monkeypatch.setattr(runtime_server, 'ProtectionService', lambda *args: service)
    def failed(*args, **kwargs):
        raise RuntimeError('DO_NOT_EXPOSE_SYNTHETIC_STARTUP_TEXT')
    monkeypatch.setattr(service, 'protect', failed)
    with pytest.raises(PIIProtectionError, match='^PII_RUNTIME_INITIALIZATION_FAILED$'):
        create_app({'bearer_token': AUTH, 'mapping_key': Fernet.generate_key().decode(), 'redis_url': 'synthetic-unused'})


def test_shared_scope_restore_tamper_and_allowed_tokens(app):
    result = post(app)
    assert result.status_code == 200
    token = result.json['issued'][0]
    assert 'person@example.invalid' not in result.json['text']
    restored = post(app, '/v1/resolve', {'scope': payload()['scope'], 'token': token})
    assert restored.json == {'value': 'person@example.invalid'}
    wrong = dict(payload()['scope'], session_id='synthetic-other')
    assert post(app, '/v1/resolve', {'scope': wrong, 'token': token}).json == {'error': 'PII_MAPPING_EXPIRED'}
    assert post(app, value=payload(text=token, allowed_tokens=[token])).status_code == 200
    assert post(app, value=payload(text=token)).json == {'error': 'PII_UNTRUSTED_PLACEHOLDER'}
    assert post(app, value=payload(scope=wrong, text=token, allowed_tokens=[token])).status_code == 400


def test_redis_failure_is_generic_and_has_no_plaintext(app, service, monkeypatch):
    def fail(*_args):
        raise RuntimeError('DO_NOT_EXPOSE_PAYLOAD_OR_SECRET')
    monkeypatch.setattr(service.store, 'put', fail)
    result = post(app)
    assert result.status_code == 503 and result.json == {'error': 'PII_RUNTIME_FAILED'}
    assert b'DO_NOT_EXPOSE' not in result.data


def test_one_lane_rejects_excess_waiting(app, service):
    service.engine.release = threading.Event()
    results = []
    thread = threading.Thread(target=lambda: results.append(post(app)))
    thread.start()
    try:
        assert service.engine.entered.wait(1)
        result = post(app)
        assert result.status_code == 503 and result.json == {'error': 'PII_RUNTIME_BUSY'}
        assert service.engine.calls == 1
    finally:
        service.engine.release.set()
        thread.join(2)
    assert results[0].status_code == 200


def test_watchdog_terminates_stalled_model_worker(service):
    terminated = threading.Event()
    app = create_app({'bearer_token': AUTH, 'recognition_timeout_seconds': 1}, service,
                     terminate=lambda code: terminated.set() if code == 70 else None)
    service.engine.release = threading.Event()
    thread = threading.Thread(target=lambda: post(app))
    thread.start()
    try:
        assert service.engine.entered.wait(1)
        assert terminated.wait(2)
    finally:
        service.engine.release.set()
        thread.join(2)


@pytest.fixture
def certificate(tmp_path):
    import ipaddress
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'synthetic-pii-test')])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(minutes=1))
            .not_valid_after(now + datetime.timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]), critical=False)
            .sign(key, hashes.SHA256()))
    pem = cert.public_bytes(serialization.Encoding.PEM).decode()
    crt, private = tmp_path/'cert.pem', tmp_path/'key.pem'
    crt.write_text(pem)
    private.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                         serialization.NoEncryption()))
    private.chmod(0o600)
    return crt, private, pem


@pytest.fixture
def tls_runtime(app, certificate):
    crt, key, pem = certificate
    server = make_server('127.0.0.1', 0, app, threaded=True, ssl_context=(str(crt), str(key)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = RemoteProtectionService(f'https://127.0.0.1:{server.server_port}', AUTH, pem)
    try:
        yield client, server, pem
    finally:
        client._close()
        server.shutdown()
        thread.join(2)
        server.server_close()


def test_tls_end_to_end_restore_and_cross_scope(tls_runtime):
    client, _, _ = tls_runtime
    result = client.protect('Email: person@example.invalid', SCOPE)
    assert 'person@example.invalid' not in result.text
    assert result.restore_text(result.text) == 'Email: person@example.invalid'
    with pytest.raises(PIIProtectionError, match='PII_MAPPING_EXPIRED'):
        client.resolve(Scope('synthetic-other', SCOPE.user_id, SCOPE.session_id), next(iter(result.issued)))


def test_tls_rejects_wrong_ca_and_wrong_auth(tls_runtime):
    client, server, pem = tls_runtime
    wrong_auth = RemoteProtectionService(f'https://127.0.0.1:{server.server_port}', 'b' * 64, pem)
    with pytest.raises(PIIProtectionError, match='PII_RUNTIME_AUTH_REQUIRED'):
        wrong_auth.protect('Email: person@example.invalid', SCOPE)
    client._tls = ssl.create_default_context()
    with pytest.raises(PIIProtectionError, match='PII_RUNTIME_UNAVAILABLE'):
        client.protect('Email: person@example.invalid', SCOPE)


@pytest.mark.parametrize('endpoint', ['http://localhost:8765', 'https://external.invalid:8765',
                                      'https://localhost:8765/path', 'https://user:pass@localhost:8765'])
def test_client_rejects_unsafe_endpoint(certificate, endpoint):
    with pytest.raises(PIIProtectionError, match='PII_RUNTIME_CONFIGURATION_REQUIRED'):
        RemoteProtectionService(endpoint, AUTH, certificate[2])


def test_secret_file_permissions_and_symlinks(tmp_path):
    path = tmp_path/'secret.json'
    path.write_text(json.dumps({'version': 1}))
    path.chmod(0o644)
    with pytest.raises(PIIProtectionError):
        read_secret_json(str(path))
    path.chmod(0o600)
    assert read_secret_json(str(path)) == {'version': 1}
    link = tmp_path/'link.json'
    link.symlink_to(path)
    with pytest.raises(PIIProtectionError):
        read_secret_json(str(link))


def test_runtime_selects_shared_without_loading_models(tmp_path, monkeypatch):
    path = tmp_path/'client.json'
    path.write_text('{}')
    monkeypatch.setenv('PII_RUNTIME_CONFIG_FILE', str(path))
    monkeypatch.setenv('PII_RUNTIME_TRANSPORT', 'auto')
    marker = object()
    monkeypatch.setattr(RemoteProtectionService, 'from_file', lambda _: marker)
    gateway.runtime_service.cache_clear()
    try:
        assert gateway.runtime_service() is marker
    finally:
        gateway.runtime_service.cache_clear()


def test_disabled_gateway_never_reads_shared_configuration(monkeypatch):
    monkeypatch.setenv('PII_PROTECTION_ENABLED', 'false')
    monkeypatch.setattr(gateway, 'runtime_service', lambda: pytest.fail('Disabled gateway must not access runtime'))
    marker = object()
    assert gateway.run_with_privacy(None, lambda: marker) is marker
