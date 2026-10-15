import pytest
from flask import Flask
from services.max_reconciliation import inspect_delivery
from services.max_transport import MaxTransportError
from api import max_api


class Transport:
    def __init__(self, *, recipient='123', text='Result', attachments=None):
        self.result = {'body': {'mid': 'mid.1', 'text': text, 'attachments': attachments or []}, 'recipient': {'user_id': recipient}}
        self.calls = []
    def call(self, method, path):
        self.calls.append((method, path))
        return self.result


def test_reconciliation_only_reads_provider_and_requires_exact_content():
    transport = Transport()
    result = inspect_delivery({'user_id': '123', 'text': 'Result', 'attachments': []}, ['mid.1'], transport)
    assert result['verified'] is True
    assert transport.calls == [('GET', '/messages/mid.1')]


@pytest.mark.parametrize('transport', [Transport(recipient='456'), Transport(text='Changed'), Transport(attachments=[{'type': 'image'}])])
def test_recipient_text_or_media_mismatch_cannot_confirm_delivery(transport):
    result = inspect_delivery({'user_id': '123', 'text': 'Result', 'attachments': []}, ['mid.1'], transport)
    assert result['verified'] is False


def test_missing_receipt_or_incomplete_chunk_list_never_confirms_execution():
    assert not inspect_delivery({'text': 'Unknown recovery'}, [], Transport())['verified']
    assert not inspect_delivery({'user_id': '123', 'text': 'x' * 5000}, ['mid.1'], Transport())['verified']
    assert not inspect_delivery({'user_id': '123', 'text': 'Result'}, ['../subscriptions'], Transport())['verified']


def test_diagnostics_is_private_even_when_max_disabled(monkeypatch):
    monkeypatch.setenv('MAX_ENABLED', 'false')
    monkeypatch.setattr(max_api, 'require_auth_from_request', lambda: None)
    monkeypatch.setattr(max_api, 'DatabaseManager', lambda: pytest.fail('unauthorized diagnostics must not query DB'))
    app = Flask(__name__); app.register_blueprint(max_api.max_bp)
    assert app.test_client().get('/api/max/diagnostics').status_code == 403
