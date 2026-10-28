"""Read-only Trello transport. OAuth is the only permitted external POST."""
import base64
import hashlib
import os
import re
import time
import urllib.parse

import requests

import auth_encryption


SCOPES = ('read:board:trello', 'offline_access')
BOARD_FIELDS = 'id,name,closed,url'
CARD_FIELDS = 'id,name,desc,idBoard,idList,due,dueComplete,closed,idMembers,labels,url,dateLastActivity'


class TrelloError(Exception):
    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code = code
        self.status = status


def configuration():
    client_id = os.getenv('TRELLO_OAUTH_CLIENT_ID', '').strip()
    client_secret = os.getenv('TRELLO_OAUTH_CLIENT_SECRET', '').strip()
    redirect_uri = os.getenv('TRELLO_OAUTH_REDIRECT_URI', '').strip()
    parsed = urllib.parse.urlsplit(redirect_uri)
    local = parsed.hostname in ('localhost', '127.0.0.1')
    valid = (parsed.scheme == 'https' or (local and parsed.scheme == 'http'))
    if (not client_id or not client_secret or not valid or parsed.query or parsed.fragment
            or parsed.username or parsed.password or parsed.path != '/api/trello/oauth/callback'):
        raise TrelloError('not_configured', 'Подключение Trello ещё не настроено администратором.', 503)
    if not auth_encryption.CRYPTOGRAPHY_AVAILABLE or not os.getenv('EXTERNAL_AUTH_SECRET_KEY', '').strip():
        raise TrelloError('encryption_unavailable', 'Защищённое хранение подключения Trello ещё не настроено.', 503)
    return client_id, client_secret, redirect_uri


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def authorization_url(state, verifier):
    client_id, _, redirect_uri = configuration()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    return 'https://auth.atlassian.com/authorize?' + urllib.parse.urlencode({
        'client_id': client_id, 'redirect_uri': redirect_uri, 'response_type': 'code',
        'prompt': 'consent', 'scope': ' '.join(SCOPES), 'state': state,
        'code_challenge': challenge, 'code_challenge_method': 'S256',
    })


def _json_response(response):
    if response.status_code == 429:
        raise TrelloError('rate_limited', 'Trello ограничил частоту запросов. Повторите позже.', 429)
    if response.status_code == 401:
        raise TrelloError('reauthorization_required', 'Подключите Trello заново.', 401)
    if response.status_code in (403, 404):
        raise TrelloError('provider_access_denied', 'Доступ к данным Trello больше не подтверждён.', 403)
    if not 200 <= response.status_code < 300:
        raise TrelloError('provider_unavailable', 'Trello временно недоступен. Повторите позже.', 502)
    try:
        return response.json()
    except ValueError:
        raise TrelloError('invalid_response', 'Trello вернул неполный ответ.', 502) from None


def exchange_token(grant):
    client_id, client_secret, redirect_uri = configuration()
    payload = {**grant, 'client_id': client_id, 'client_secret': client_secret}
    if grant.get('grant_type') == 'authorization_code':
        payload['redirect_uri'] = redirect_uri
    try:
        response = requests.post('https://auth.atlassian.com/oauth/token', json=payload,
                                 timeout=(5, 20), allow_redirects=False)
    except requests.RequestException:
        raise TrelloError('oauth_unavailable', 'Не удалось подтвердить доступ Trello. Начните подключение заново.', 502) from None
    if response.status_code in (400, 401):
        raise TrelloError('reauthorization_required', 'Подключите Trello заново.', 401)
    data = _json_response(response)
    if not isinstance(data, dict):
        raise TrelloError('invalid_response', 'Trello не подтвердил доступ.', 502)
    scopes = set(str(data.get('scope') or '').split())
    # Never accept a grant with write scopes, including silently widened grants.
    if 'read:board:trello' not in scopes or scopes - set(SCOPES):
        raise TrelloError('invalid_scopes', 'Trello должен предоставить только доступ для чтения.', 403)
    if any(not isinstance(data.get(key), str) or not data[key] for key in ('access_token', 'refresh_token')):
        raise TrelloError('invalid_response', 'Trello не вернул необходимые данные подключения.', 502)
    expiry = data.get('expires_in')
    if not isinstance(expiry, (int, float)) or expiry <= 0:
        raise TrelloError('invalid_response', 'Trello не подтвердил срок действия доступа.', 502)
    return {'access_token': data['access_token'], 'refresh_token': data['refresh_token'],
            'expires_at': time.time() + expiry, 'scope': ' '.join(sorted(scopes))}


def validate_id(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{24}', value):
        raise TrelloError('invalid_board', 'Выберите доску из списка Trello.')
    return value


def _get(token, path, params):
    # Fixed host, fixed GET method and allowlisted paths; no generic request escape hatch.
    if not re.fullmatch(r'/members/me/boards|/boards/[0-9a-f]{24}(/lists|/cards)?', path):
        raise TrelloError('unsupported_operation', 'Операция Trello недоступна.', 403)
    try:
        response = requests.get('https://api.trello.com/1' + path, params=params,
                                headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/json'},
                                timeout=(5, 20), allow_redirects=False)
    except requests.RequestException:
        raise TrelloError('provider_unavailable', 'Не удалось прочитать Trello. Повторите позже.', 502) from None
    return _json_response(response)


def boards(token):
    result = _get(token, '/members/me/boards', {'filter': 'all', 'fields': BOARD_FIELDS})
    if not isinstance(result, list) or any(not isinstance(item, dict) or not item.get('id') for item in result):
        raise TrelloError('invalid_response', 'Trello не подтвердил список досок.', 502)
    return [{key: item.get(key) for key in BOARD_FIELDS.split(',')} for item in result]


def board_snapshot(token, board_id):
    validate_id(board_id)
    board = _get(token, '/boards/' + board_id, {'fields': BOARD_FIELDS})
    lists = _get(token, '/boards/' + board_id + '/lists', {'filter': 'all', 'fields': 'id,name,closed,idBoard'})
    if (not isinstance(board, dict) or board.get('id') != board_id or not isinstance(lists, list)
            or any(not isinstance(item, dict) or item.get('idBoard') != board_id or not item.get('id') for item in lists)):
        raise TrelloError('invalid_response', 'Trello не подтвердил данные доски.', 502)
    cards = {}
    before = None
    # Bounded pilot: never label a capped or malformed snapshot complete.
    for _page in range(21):
        params = {'filter': 'all', 'fields': CARD_FIELDS, 'limit': 1000, 'sort': '-id'}
        if before:
            params['before'] = before
        page = _get(token, '/boards/' + board_id + '/cards', params)
        if not isinstance(page, list) or len(page) > 1000:
            raise TrelloError('invalid_response', 'Trello не подтвердил список карточек.', 502)
        for item in page:
            if not isinstance(item, dict) or item.get('idBoard') != board_id:
                raise TrelloError('invalid_response', 'Trello вернул карточку другой доски.', 502)
            card_id = validate_id(item.get('id'))
            if card_id in cards or (before and card_id >= before):
                raise TrelloError('incomplete_snapshot', 'Не удалось получить полный список карточек. Повторите загрузку.', 502)
            cards[card_id] = {key: item.get(key) for key in CARD_FIELDS.split(',')}
        if len(cards) > 20000:
            raise TrelloError('snapshot_too_large', 'Доска превышает лимит пилота: 20 000 карточек.', 409)
        if len(page) < 1000:
            return {'board': {key: board.get(key) for key in BOARD_FIELDS.split(',')},
                    'lists': [{key: item.get(key) for key in ('id', 'name', 'closed', 'idBoard')} for item in lists],
                    'cards': list(cards.values()), 'complete': True}
        before = min(item['id'] for item in page)
    raise TrelloError('snapshot_too_large', 'Доска превышает лимит пилота: 20 000 карточек.', 409)
