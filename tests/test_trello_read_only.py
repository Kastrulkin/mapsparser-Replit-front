import urllib.parse
import sys

import pytest
import requests
from flask import Flask

from api import trello_api
from services import trello_client


BOARD = 'a' * 24


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv('TRELLO_READ_ENABLED', 'true')
    monkeypatch.setenv('TRELLO_OAUTH_CLIENT_ID', 'test-client')
    monkeypatch.setenv('TRELLO_OAUTH_CLIENT_SECRET', 'test-client-secret')
    monkeypatch.setenv('TRELLO_OAUTH_REDIRECT_URI', 'http://localhost/api/trello/oauth/callback')
    monkeypatch.setenv('EXTERNAL_AUTH_SECRET_KEY', 'test-only-encryption-key')


class Response:
    def __init__(self, data, status=200):
        self.data = data
        self.status_code = status

    def json(self):
        return self.data


def test_authorization_is_read_only_pkce(configured):
    url = trello_client.authorization_url('state', 'v' * 86)
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    assert set(query['scope'][0].split()) == {'read:board:trello', 'offline_access'}
    assert query['state'] == ['state']
    assert query['code_challenge_method'] == ['S256']
    assert 'v' * 86 not in url and 'test-client-secret' not in url


@pytest.mark.parametrize('setting,value', [
    ('EXTERNAL_AUTH_SECRET_KEY', ''),
    ('TRELLO_OAUTH_REDIRECT_URI', 'http://untrusted.example/api/trello/oauth/callback'),
    ('TRELLO_OAUTH_REDIRECT_URI', 'https://example.com/api/trello/oauth/callback?redirect=elsewhere'),
])
def test_configuration_fails_closed(configured, monkeypatch, setting, value):
    monkeypatch.setenv(setting, value)
    with pytest.raises(trello_client.TrelloError):
        trello_client.configuration()


def test_missing_crypto_has_no_base64_fallback(configured, monkeypatch):
    monkeypatch.setattr(trello_client.auth_encryption, 'CRYPTOGRAPHY_AVAILABLE', False)
    with pytest.raises(trello_client.TrelloError):
        trello_client.configuration()


def test_token_exchange_uses_documented_endpoint_and_keeps_secrets_out_of_errors(configured, monkeypatch):
    calls = []
    def post(url, **kwargs):
        calls.append((url, kwargs))
        return Response({'access_token': 'access', 'refresh_token': 'refresh', 'expires_in': 3600,
                         'scope': 'read:board:trello offline_access'})
    monkeypatch.setattr(requests, 'post', post)
    result = trello_client.exchange_token({'grant_type': 'authorization_code', 'code': 'code', 'code_verifier': 'verifier'})
    assert result['refresh_token'] == 'refresh'
    assert calls[0][0] == 'https://auth.atlassian.com/oauth/token'
    assert calls[0][1]['json']['code_verifier'] == 'verifier'
    assert calls[0][1]['allow_redirects'] is False


@pytest.mark.parametrize('scope', ['write:board:trello read:board:trello', '', 'read:board:trello read:member:trello'])
def test_widened_grant_is_rejected(configured, monkeypatch, scope):
    monkeypatch.setattr(requests, 'post', lambda *args, **kwargs: Response({
        'scope': scope, 'access_token': 'SECRET', 'refresh_token': 'SECRET', 'expires_in': 3600}))
    pytest.raises(trello_client.TrelloError, trello_client.exchange_token, {'grant_type': 'refresh_token', 'refresh_token': 'SECRET'})


def test_transport_only_reads_allowlisted_paths(monkeypatch):
    calls = []
    def get(url, **kwargs):
        calls.append((url, kwargs))
        return Response([{'id': BOARD, 'name': 'Board'}])
    monkeypatch.setattr(requests, 'get', get)
    assert trello_client.boards('secret')[0]['id'] == BOARD
    assert calls[0][1]['headers']['Authorization'] == 'Bearer secret'
    assert 'secret' not in calls[0][0]
    for path in ('https://evil.example', '/cards/' + BOARD, '/boards/' + BOARD + '/members'):
        pytest.raises(trello_client.TrelloError, trello_client._get, 'secret', path, {})


@pytest.mark.parametrize('status,code', [(401, 'reauthorization_required'), (403, 'provider_access_denied'),
                                        (429, 'rate_limited'), (500, 'provider_unavailable'), (302, 'provider_unavailable')])
def test_provider_errors_are_sanitized(monkeypatch, status, code):
    monkeypatch.setattr(requests, 'get', lambda *args, **kwargs: Response({'error': 'TOKEN-SECRET'}, status))
    try:
        trello_client.boards('TOKEN-SECRET')
        pytest.fail('provider error expected')
    except trello_client.TrelloError:
        error = sys.exception()
        assert error.code == code
        assert 'TOKEN-SECRET' not in str(error)


def test_network_errors_never_expose_token(monkeypatch):
    def get(*args, **kwargs):
        raise requests.ConnectionError('Bearer TOKEN-SECRET')
    monkeypatch.setattr(requests, 'get', get)
    try:
        trello_client.boards('TOKEN-SECRET')
        pytest.fail('network error expected')
    except trello_client.TrelloError:
        error = sys.exception()
        assert 'TOKEN-SECRET' not in str(error)


def test_snapshot_paginates_including_archived_and_rejects_repeated_page(monkeypatch):
    cards = [{'id': format(number, '024x'), 'idBoard': BOARD, 'closed': True} for number in range(1000, 0, -1)]
    calls = []
    def get(token, path, params):
        calls.append(params)
        if path.endswith('/lists'):
            return []
        if path.endswith('/cards'):
            return [] if params.get('before') else cards
        return {'id': BOARD, 'name': 'Archive'}
    monkeypatch.setattr(trello_client, '_get', get)
    result = trello_client.board_snapshot('token', BOARD)
    assert result['complete'] and len(result['cards']) == 1000
    assert result['cards'][0]['closed'] is True
    assert calls[-1]['before'] == format(1, '024x')
    assert calls[-1]['filter'] == 'all'
    def repeated(token, path, params):
        if path.endswith('/lists'):
            return []
        if path.endswith('/cards'):
            return cards
        return {'id': BOARD}
    monkeypatch.setattr(trello_client, '_get', repeated)
    pytest.raises(trello_client.TrelloError, trello_client.board_snapshot, 'token', BOARD)


def test_snapshot_rejects_cross_board_card(monkeypatch):
    monkeypatch.setattr(trello_client, '_get', lambda token, path, params: [] if path.endswith('/lists') else
                        [{'id': 'b' * 24, 'idBoard': 'b' * 24}] if path.endswith('/cards') else {'id': BOARD})
    pytest.raises(trello_client.TrelloError, trello_client.board_snapshot, 'token', BOARD)


def test_no_unauthenticated_or_mutating_trello_routes(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(trello_api.trello_bp)
    monkeypatch.setattr(trello_api, 'require_auth_from_request', lambda: None)
    client = app.test_client()
    assert client.get('/api/business/private/trello/status').status_code == 401
    assert client.post('/api/business/private/trello/cards').status_code == 404
    response = client.get('/api/trello/oauth/callback?state=untrusted&code=SECRET')
    assert response.status_code == 302 and 'SECRET' not in response.location
    assert response.headers['Cache-Control'] == 'no-store'
