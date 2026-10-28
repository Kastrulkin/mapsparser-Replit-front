"""Owner-only read pilot. Local writes never mutate Trello boards or webhooks."""
import functools
import hmac
import json
import os
import secrets
import sys
import time
import uuid

from flask import Blueprint, current_app, jsonify, redirect, request
from psycopg2.extras import Json

from auth_encryption import decrypt_auth_data, encrypt_auth_data
from core.auth_context import AuthContext
from core.auth_helpers import require_auth_from_request
from pg_db_utils import get_db_connection
from services import trello_client


trello_bp = Blueprint('trello_api', __name__)
COOKIE = 'localos_trello_oauth'
CALLBACK = '/api/trello/oauth/callback'
RETURN_PATH = '/dashboard/settings/integrations?focus=trello'


def enabled():
    return os.getenv('TRELLO_READ_ENABLED', 'false').lower() == 'true'


def require_owner(cursor, business_id, actor):
    auth = AuthContext.from_session(actor)
    if auth.session_kind != 'standard' or auth.impersonating or not auth.permits_business(business_id):
        raise trello_client.TrelloError('access_denied', 'Подключение Trello доступно владельцу бизнеса.', 403)
    cursor.execute('''SELECT b.owner_id,u.is_active,u.is_superadmin FROM businesses b
        JOIN users u ON u.id=%s WHERE b.id=%s AND (b.is_active=TRUE OR b.is_active IS NULL)
        FOR SHARE OF b,u''', (auth.user_id, business_id))
    row = cursor.fetchone()
    if not row or not row['is_active'] or (row['owner_id'] != auth.user_id and not row['is_superadmin']):
        raise trello_client.TrelloError('access_denied', 'Нет доступа к подключению этого бизнеса.', 403)


def business_endpoint(function):
    @functools.wraps(function)
    def handle(business_id, **kwargs):
        actor = require_auth_from_request()
        if not actor:
            return jsonify(error='authentication_required', message='Войдите в LocalOS.'), 401
        conn = None
        try:
            conn = get_db_connection()
            require_owner(conn.cursor(), business_id, actor)
            if not enabled():
                if function.__name__ == 'status':
                    return jsonify(success=True, enabled=False, configured=False, connected=False, boards=[])
                raise trello_client.TrelloError('disabled', 'Пилот Trello пока выключен.', 503)
            result = function(conn, business_id, actor, **kwargs)
            conn.commit()
            return result
        except trello_client.TrelloError:
            error = sys.exception()
            if conn:
                conn.rollback()
            return jsonify(success=False, error=error.code, message=str(error)), error.status
        except Exception:
            error = sys.exception()
            if conn:
                conn.rollback()
            # Provider exceptions can carry credentials; never log their message or traceback.
            current_app.logger.error('Trello request failed type=%s', type(error).__name__)
            return jsonify(success=False, error='internal_error', message='Не удалось обработать подключение Trello.'), 500
        finally:
            if conn:
                conn.close()
    return handle


def _account(cursor, business_id):
    cursor.execute("SELECT * FROM externalbusinessaccounts WHERE business_id=%s AND source='trello' AND is_active=TRUE FOR UPDATE",
                   (business_id,))
    account = cursor.fetchone()
    if not account or not account.get('auth_data_encrypted'):
        raise trello_client.TrelloError('not_connected', 'Сначала подключите Trello.', 409)
    return dict(account)


def _access(conn, business_id, actor):
    trello_client.configuration()
    cursor = conn.cursor()
    account = _account(cursor, business_id)
    try:
        credentials = json.loads(decrypt_auth_data(account['auth_data_encrypted']) or '{}')
    except (TypeError, ValueError):
        credentials = {}
    if (not isinstance(credentials, dict) or not credentials.get('access_token') or not credentials.get('refresh_token')
            or not isinstance(credentials.get('expires_at'), (int, float))):
        cursor.execute("UPDATE externalbusinessaccounts SET last_error='reauthorization_required' WHERE id=%s", (account['id'],))
        conn.commit()
        raise trello_client.TrelloError('reauthorization_required', 'Подключите Trello заново.', 409)
    if credentials.get('expires_at', 0) <= time.time() + 60:
        try:
            credentials = trello_client.exchange_token({'grant_type': 'refresh_token', 'refresh_token': credentials['refresh_token']})
        except trello_client.TrelloError:
            error = sys.exception()
            if error.code != 'rate_limited':
                cursor.execute("UPDATE externalbusinessaccounts SET last_error='reauthorization_required' WHERE id=%s", (account['id'],))
                conn.commit()
            raise
        encrypted = encrypt_auth_data(json.dumps(credentials))
        cursor.execute('UPDATE externalbusinessaccounts SET auth_data_encrypted=%s,last_error=NULL,updated_at=NOW() WHERE id=%s',
                       (encrypted, account['id']))
        # Rotation must survive a later provider read failure.
        conn.commit()
        require_owner(conn.cursor(), business_id, actor)
        current = _account(conn.cursor(), business_id)
        if current['id'] != account['id'] or current['auth_data_encrypted'] != encrypted:
            raise trello_client.TrelloError('connection_changed', 'Подключение изменилось. Повторите загрузку.', 409)
        account = current
    return account, credentials['access_token']


def _provider_call(conn, account, function, *args):
    try:
        return function(*args)
    except trello_client.TrelloError:
        error = sys.exception()
        if error.code in ('reauthorization_required', 'provider_access_denied'):
            conn.cursor().execute('UPDATE externalbusinessaccounts SET last_error=%s,updated_at=NOW() WHERE id=%s',
                                  (error.code, account['id']))
            conn.commit()
        raise


@trello_bp.get('/api/business/<business_id>/trello/status')
@business_endpoint
def status(conn, business_id, actor):
    configured = True
    try:
        trello_client.configuration()
    except trello_client.TrelloError:
        configured = False
    cursor = conn.cursor()
    cursor.execute("SELECT id,last_error,auth_data_encrypted IS NOT NULL AND auth_data_encrypted<>'' has_credentials FROM externalbusinessaccounts WHERE business_id=%s AND source='trello' AND is_active=TRUE", (business_id,))
    account = cursor.fetchone()
    selected = []
    if account:
        cursor.execute('SELECT board_id,board_name,last_sync_at FROM trello_board_snapshots WHERE account_id=%s ORDER BY board_name,board_id', (account['id'],))
        selected = [dict(row) for row in cursor.fetchall()]
    return jsonify(success=True, enabled=True, configured=configured, connected=bool(account and account['has_credentials']),
                   needs_reauthorization=bool(account and account.get('last_error')), boards=selected, read_only=True)


@trello_bp.post('/api/business/<business_id>/trello/authorize')
@business_endpoint
def authorize(conn, business_id, actor):
    trello_client.configuration()
    if not actor.get('session_id'):
        raise trello_client.TrelloError('session_required', 'Войдите в LocalOS заново.', 401)
    state = secrets.token_urlsafe(32)
    browser = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    url = trello_client.authorization_url(state, verifier)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM trello_oauth_attempts WHERE business_id=%s AND expires_at < NOW()', (business_id,))
    cursor.execute('UPDATE trello_oauth_attempts SET cancelled=TRUE WHERE business_id=%s', (business_id,))
    cursor.execute('''INSERT INTO trello_oauth_attempts
        (state_hash,browser_hash,business_id,user_id,session_id,verifier_encrypted,expires_at)
        VALUES(%s,%s,%s,%s,%s,%s,NOW()+INTERVAL '10 minutes')''',
        (trello_client.digest(state), trello_client.digest(browser), business_id, actor['user_id'],
         actor['session_id'], encrypt_auth_data(verifier)))
    response = jsonify(success=True, authorization_url=url)
    response.set_cookie(COOKIE, browser, max_age=600, httponly=True, samesite='Lax', path=CALLBACK,
                        secure=trello_client.configuration()[2].startswith('https://'))
    return response


@trello_bp.get(CALLBACK)
def callback():
    conn = None
    result = 'failed'
    try:
        if not enabled():
            raise trello_client.TrelloError('disabled', 'Trello выключен.')
        trello_client.configuration()
        state = request.args.get('state', '')
        browser = request.cookies.get(COOKIE, '')
        if not state or len(state) > 200 or not browser:
            raise trello_client.TrelloError('invalid_state', 'Начните подключение заново.')
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''SELECT * FROM trello_oauth_attempts WHERE state_hash=%s
            AND expires_at>NOW() AND consumed_at IS NULL AND cancelled=FALSE FOR UPDATE''', (trello_client.digest(state),))
        attempt = cursor.fetchone()
        if not attempt or not hmac.compare_digest(attempt['browser_hash'], trello_client.digest(browser)):
            raise trello_client.TrelloError('invalid_state', 'Начните подключение заново.')
        cursor.execute('''SELECT user_id,session_kind,scope_business_id FROM usersessions
            WHERE id=%s AND user_id=%s AND expires_at>NOW()''', (attempt['session_id'], attempt['user_id']))
        actor = cursor.fetchone()
        if not actor:
            raise trello_client.TrelloError('session_expired', 'Войдите в LocalOS заново.')
        require_owner(cursor, attempt['business_id'], dict(actor))
        verifier = decrypt_auth_data(attempt['verifier_encrypted'])
        cursor.execute("UPDATE trello_oauth_attempts SET consumed_at=NOW(),verifier_encrypted='' WHERE state_hash=%s", (attempt['state_hash'],))
        conn.commit()  # A callback cannot exchange the same code twice.
        if request.args.get('error'):
            result = 'denied'
        else:
            code = request.args.get('code', '')
            if not code or len(code) > 4096 or not verifier:
                raise trello_client.TrelloError('invalid_code', 'Начните подключение заново.')
            credentials = trello_client.exchange_token({'grant_type': 'authorization_code', 'code': code, 'code_verifier': verifier})
            trello_client.boards(credentials['access_token'])  # Verify actual read access before saving.
            require_owner(cursor, attempt['business_id'], dict(actor))
            cursor.execute('SELECT id FROM usersessions WHERE id=%s AND expires_at>NOW()', (attempt['session_id'],))
            if not cursor.fetchone():
                raise trello_client.TrelloError('session_expired', 'Войдите в LocalOS заново.')
            cursor.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', ('trello:' + attempt['business_id'],))
            cursor.execute('SELECT cancelled FROM trello_oauth_attempts WHERE state_hash=%s FOR UPDATE', (attempt['state_hash'],))
            if cursor.fetchone()['cancelled']:
                raise trello_client.TrelloError('connection_changed', 'Начните подключение заново.')
            cursor.execute("SELECT id FROM externalbusinessaccounts WHERE business_id=%s AND source='trello' FOR UPDATE", (attempt['business_id'],))
            previous = cursor.fetchone()
            if previous:
                account_id = previous['id']
                cursor.execute('DELETE FROM trello_board_snapshots WHERE account_id=%s', (account_id,))
                cursor.execute('''UPDATE externalbusinessaccounts SET auth_data_encrypted=%s,is_active=TRUE,
                    last_error=NULL,last_sync_at=NULL,updated_at=NOW() WHERE id=%s''',
                    (encrypt_auth_data(json.dumps(credentials)), account_id))
            else:
                cursor.execute('''INSERT INTO externalbusinessaccounts
                    (id,business_id,source,display_name,auth_data_encrypted,is_active,created_at,updated_at)
                    VALUES(%s,%s,'trello','Trello',%s,TRUE,NOW(),NOW())''',
                    (str(uuid.uuid4()), attempt['business_id'], encrypt_auth_data(json.dumps(credentials))))
            conn.commit()
            result = 'connected'
    except trello_client.TrelloError:
        if conn:
            conn.rollback()
    except Exception:
        error = sys.exception()
        if conn:
            conn.rollback()
        current_app.logger.error('Trello callback failed type=%s', type(error).__name__)
    finally:
        if conn:
            conn.close()
    response = redirect(RETURN_PATH + '&trello_result=' + result)
    response.delete_cookie(COOKIE, path=CALLBACK)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Referrer-Policy'] = 'no-referrer'
    return response


@trello_bp.get('/api/business/<business_id>/trello/boards')
@business_endpoint
def boards(conn, business_id, actor):
    account, token = _access(conn, business_id, actor)
    result = _provider_call(conn, account, trello_client.boards, token)
    conn.cursor().execute('DELETE FROM trello_board_snapshots WHERE account_id=%s AND NOT (board_id=ANY(%s::text[]))',
                          (account['id'], [board['id'] for board in result]))
    conn.cursor().execute('UPDATE externalbusinessaccounts SET last_error=NULL WHERE id=%s', (account['id'],))
    return jsonify(success=True, boards=result)


@trello_bp.put('/api/business/<business_id>/trello/selection')
@business_endpoint
def selection(conn, business_id, actor):
    payload = request.get_json(silent=True) or {}
    selected = payload.get('board_ids') if isinstance(payload, dict) else None
    if not isinstance(selected, list) or len(selected) > 10 or len(set(str(item) for item in selected)) != len(selected):
        raise trello_client.TrelloError('invalid_selection', 'Выберите до 10 разных досок.')
    for board_id in selected:
        trello_client.validate_id(board_id)
    account, token = _access(conn, business_id, actor)
    available = {item['id']: item for item in _provider_call(conn, account, trello_client.boards, token)}
    if any(board_id not in available for board_id in selected):
        raise trello_client.TrelloError('invalid_selection', 'Обновите список доступных досок.', 403)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM trello_board_snapshots WHERE account_id=%s AND NOT (board_id=ANY(%s::text[]))', (account['id'], selected))
    for board_id in selected:
        cursor.execute('''INSERT INTO trello_board_snapshots(account_id,board_id,board_name) VALUES(%s,%s,%s)
            ON CONFLICT(account_id,board_id) DO UPDATE SET board_name=EXCLUDED.board_name''',
            (account['id'], board_id, available[board_id]['name']))
    return jsonify(success=True, selected_board_ids=selected)


@trello_bp.post('/api/business/<business_id>/trello/boards/<board_id>/sync')
@business_endpoint
def sync(conn, business_id, actor, board_id):
    trello_client.validate_id(board_id)
    account, token = _access(conn, business_id, actor)
    cursor = conn.cursor()
    cursor.execute('SELECT board_id FROM trello_board_snapshots WHERE account_id=%s AND board_id=%s', (account['id'], board_id))
    if not cursor.fetchone():
        raise trello_client.TrelloError('board_not_selected', 'Сначала выберите эту доску.', 403)
    snapshot = _provider_call(conn, account, trello_client.board_snapshot, token, board_id)
    cursor.execute('''UPDATE trello_board_snapshots SET snapshot_json=%s,board_name=%s,last_sync_at=NOW()
        WHERE account_id=%s AND board_id=%s''', (Json(snapshot), snapshot['board']['name'], account['id'], board_id))
    cursor.execute('UPDATE externalbusinessaccounts SET last_sync_at=NOW(),last_error=NULL WHERE id=%s', (account['id'],))
    return jsonify(success=True, card_count=len(snapshot['cards']), snapshot=snapshot, read_only=True)


@trello_bp.delete('/api/business/<business_id>/trello/connection')
@business_endpoint
def disconnect(conn, business_id, actor):
    cursor = conn.cursor()
    cursor.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', ('trello:' + business_id,))
    cursor.execute("SELECT id FROM externalbusinessaccounts WHERE business_id=%s AND source='trello' FOR UPDATE", (business_id,))
    account = cursor.fetchone()
    if account:
        cursor.execute('DELETE FROM trello_board_snapshots WHERE account_id=%s', (account['id'],))
        cursor.execute("UPDATE externalbusinessaccounts SET is_active=FALSE,auth_data_encrypted=NULL,last_error=NULL,last_sync_at=NULL,updated_at=NOW() WHERE id=%s", (account['id'],))
    cursor.execute("UPDATE trello_oauth_attempts SET cancelled=TRUE,verifier_encrypted='' WHERE business_id=%s", (business_id,))
    return jsonify(success=True)


@trello_bp.get('/api/business/<business_id>/trello/boards/<board_id>/snapshot')
@business_endpoint
def snapshot(conn, business_id, actor, board_id):
    trello_client.validate_id(board_id)
    cursor = conn.cursor()
    account, token = _access(conn, business_id, actor)
    if account.get('last_error'):
        raise trello_client.TrelloError('reauthorization_required', 'Подтвердите доступ Trello перед просмотром данных.', 409)
    available = _provider_call(conn, account, trello_client.boards, token)
    if not any(board['id'] == board_id for board in available):
        cursor.execute('DELETE FROM trello_board_snapshots WHERE account_id=%s AND board_id=%s', (account['id'], board_id))
        conn.commit()
        raise trello_client.TrelloError('board_access_revoked', 'Доступ к этой доске больше не подтверждён.', 403)
    cursor.execute('SELECT snapshot_json,last_sync_at FROM trello_board_snapshots WHERE account_id=%s AND board_id=%s', (account['id'], board_id))
    row = cursor.fetchone()
    if not row:
        raise trello_client.TrelloError('board_not_selected', 'Доска не выбрана.', 404)
    return jsonify(success=True, snapshot=row['snapshot_json'], last_sync_at=row['last_sync_at'], read_only=True)


@trello_bp.after_request
def private_response(response):
    response.headers['Cache-Control'] = 'no-store'
    return response
