"""MAX transport ingress and authenticated linking. Disabled until configured."""
import hashlib
import hmac
import json
import os
import sys
import uuid

from flask import Blueprint, jsonify, request
from psycopg2.extras import Json

from core.auth_helpers import require_auth_from_request
from database_manager import DatabaseManager
from services.max_identity import MaxLinkError, consume_link_code, issue_link_code
from services.max_webapp_auth import max_enabled, validate_max_init_data

max_bp = Blueprint("max_api", __name__, url_prefix="/api/max")


@max_bp.after_request
def private_responses(response):
    response.headers['Cache-Control'] = 'no-store'
    return response


@max_bp.before_request
def require_max_enabled():
    if request.endpoint != 'max_api.max_diagnostics' and not max_enabled():
        return jsonify(success=False, error="MAX пока не включён"), 503


@max_bp.post("/webhook")
def webhook():
    request.max_content_length = 1_000_000
    secret = os.getenv("MAX_WEBHOOK_SECRET", "")
    if not secret or not hmac.compare_digest(request.headers.get("X-Max-Bot-Api-Secret", "").encode(), secret.encode()):
        return jsonify(success=False), 403
    if request.content_length and request.content_length > 1_000_000:
        return jsonify(success=False), 413
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or payload.get("update_type") not in {
        "message_created", "message_callback", "bot_started", "bot_stopped", "bot_added", "bot_removed"}:
        return jsonify(success=False, error="Некорректное событие"), 400
    for field in ('message', 'callback', 'user'):
        if field in payload and not isinstance(payload[field], dict):
            return jsonify(success=False, error='Некорректное событие'), 400
    message = payload.get('message') or {}
    for field in ('body', 'sender', 'recipient'):
        if field in message and message[field] is not None and not isinstance(message[field], dict):
            return jsonify(success=False, error='Некорректное сообщение'), 400
    payload.pop('_localos_link_hash', None)
    text = str((message.get('body') or {}).get('text') or '').strip()
    if payload['update_type'] == 'message_created' and text.startswith('/link '):
        # The durable inbox must not retain a usable account-linking credential.
        payload['_localos_link_hash'] = hashlib.sha256(text.split(maxsplit=1)[1].encode()).hexdigest()
        message['body']['text'] = '/link [redacted]'
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    kind = payload['update_type']
    message_id = ((payload.get('message') or {}).get('body') or {}).get('mid')
    callback_id = (payload.get('callback') or {}).get('callback_id')
    stable_id = message_id if kind == 'message_created' else callback_id if kind == 'message_callback' else None
    key = hashlib.sha256(f'{kind}:{stable_id}'.encode() if stable_id else serialized.encode()).hexdigest()
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        cursor.execute("""INSERT INTO max_webhook_events(event_key,payload_json) VALUES (%s,%s)
            ON CONFLICT(event_key) DO NOTHING""", (key, Json(payload)))
        db.conn.commit()
        return jsonify(success=True)
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.conn.rollback()
        db.close()


@max_bp.post("/link-code")
def link_code():
    actor = require_auth_from_request()
    if not actor or actor.get("session_kind") == "demo":
        return jsonify(success=False, error="Войдите в свой аккаунт LocalOS"), 401
    db = DatabaseManager()
    try:
        code = issue_link_code(db.conn.cursor(), str(actor.get("user_id") or actor.get("id")))
        db.conn.commit()
        response = jsonify(success=True, code=code, expires_in=600)
        response.headers["Cache-Control"] = "no-store"
        return response
    finally:
        db.conn.rollback()
        db.close()


@max_bp.post("/link")
def link():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(success=False), 400
    verified = validate_max_init_data(payload.get("init_data"))
    if not verified:
        return jsonify(success=False, error="Откройте приложение заново из MAX"), 401
    db = DatabaseManager()
    try:
        consume_link_code(db.conn.cursor(), payload.get("code"), verified["max_id"])
        db.conn.commit()
        return jsonify(success=True)
    except MaxLinkError:
        error = sys.exception()
        db.conn.rollback()
        return jsonify(success=False, error=str(error)), 409
    finally:
        db.conn.rollback()
        db.close()


@max_bp.route("/connection", methods=["GET", "DELETE", "PATCH"])
def connection():
    actor = require_auth_from_request()
    if not actor or actor.get("session_kind") == "demo":
        return jsonify(success=False), 401
    user_id = str(actor.get("user_id") or actor.get("id"))
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        if request.method == "DELETE":
            cursor.execute("UPDATE max_identities SET revoked_at=NOW(),notifications_enabled=FALSE WHERE user_id=%s", (user_id,))
            cursor.execute("UPDATE max_link_tokens SET consumed_at=NOW() WHERE user_id=%s AND consumed_at IS NULL", (user_id,))
            cursor.execute("DELETE FROM usersessions WHERE user_id=%s AND user_agent='localos-max-mini-app'", (user_id,))
            cursor.execute("DELETE FROM max_bot_states WHERE user_id=%s", (user_id,))
        elif request.method == "PATCH":
            payload = request.get_json(silent=True) or {}
            if type(payload.get("notifications_enabled")) is not bool:
                return jsonify(success=False), 400
            cursor.execute("UPDATE max_identities SET notifications_enabled=%s WHERE user_id=%s AND revoked_at IS NULL",
                           (payload["notifications_enabled"], user_id))
        cursor.execute("SELECT max_id,notifications_enabled FROM max_identities WHERE user_id=%s AND revoked_at IS NULL", (user_id,))
        row = cursor.fetchone()
        db.conn.commit()
        return jsonify(success=True, connection=dict(row) if row and hasattr(row, "keys") else None)
    finally:
        db.conn.rollback()
        db.close()


@max_bp.route('/channels/<business_id>', methods=['GET', 'POST', 'DELETE'])
def channel_connection(business_id):
    from auth_encryption import encrypt_auth_data, CRYPTOGRAPHY_AVAILABLE
    from services.business_permissions import require_permission
    from services.operator_conversations import _row
    from services.max_publication import probe_channel
    from services.max_transport import MaxTransport, MaxTransportError
    actor = require_auth_from_request()
    if not actor or actor.get('session_kind') == 'demo':
        return jsonify(success=False), 401
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        require_permission(cursor, business_id, actor, 'business.settings.write')
        cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ('max-channel:' + business_id,))
        cursor.execute("SELECT id,external_id,display_name FROM externalbusinessaccounts WHERE business_id=%s AND source='max_bot' AND COALESCE(is_active,TRUE) ORDER BY updated_at DESC LIMIT 1", (business_id,))
        current = _row(cursor, cursor.fetchone())
        if request.method == 'DELETE':
            cursor.execute("UPDATE externalbusinessaccounts SET is_active=FALSE,updated_at=NOW() WHERE business_id=%s AND source='max_bot'", (business_id,))
            current = {}
        elif request.method == 'POST':
            if not CRYPTOGRAPHY_AVAILABLE or not os.getenv('EXTERNAL_AUTH_SECRET_KEY', '').strip():
                raise ValueError('Для подключения канала настройте защищённое хранение ключей на сервере')
            payload = request.get_json(silent=True)
            if not isinstance(payload, dict):
                return jsonify(success=False), 400
            transport = MaxTransport(payload.get('bot_token'))
            target = probe_channel(transport, str(payload.get('chat_id') or '').strip())
            # Probe is read-only. Re-admit the owner before saving the verified destination.
            require_permission(cursor, business_id, actor, 'business.settings.write')
            account_id = current.get('id') or str(uuid.uuid4())
            encrypted = encrypt_auth_data(json.dumps({'bot_token': transport.token, 'bot_id': target['bot_id']}))
            cursor.execute("UPDATE externalbusinessaccounts SET is_active=FALSE,updated_at=NOW() WHERE business_id=%s AND source='max_bot' AND id<>%s", (business_id, account_id))
            cursor.execute("""INSERT INTO externalbusinessaccounts(id,business_id,source,external_id,display_name,auth_data_encrypted,is_active,created_at,updated_at)
                VALUES (%s,%s,'max_bot',%s,%s,%s,TRUE,NOW(),NOW()) ON CONFLICT(id) DO UPDATE SET
                external_id=EXCLUDED.external_id,display_name=EXCLUDED.display_name,auth_data_encrypted=EXCLUDED.auth_data_encrypted,
                is_active=TRUE,updated_at=NOW()""", (account_id, business_id, target['chat_id'], target['title'], encrypted))
            current = {'id': account_id, 'external_id': target['chat_id'], 'display_name': target['title']}
        db.conn.commit()
        return jsonify(success=True, connection=current or None)
    except PermissionError:
        return jsonify(success=False, error='Нет права настройки бизнеса или публикации в канале'), 403
    except (ValueError, MaxTransportError):
        return jsonify(success=False, error='Не удалось проверить MAX. Проверьте ID канала, токен и права бота.'), 400
    finally:
        db.conn.rollback()
        db.close()


@max_bp.get('/diagnostics')
def max_diagnostics():
    actor = require_auth_from_request()
    if not actor or not actor.get('is_superadmin') or actor.get('session_kind') == 'demo':
        return jsonify(success=False), 403
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        from services.operator_conversations import _row
        cursor.execute("SELECT to_regclass('max_webhook_events') AS events")
        installed = bool(_row(cursor, cursor.fetchone()).get('events'))
        metrics = []
        if installed:
            cursor.execute('''SELECT status,COUNT(*) AS count,
                COALESCE(MAX(EXTRACT(EPOCH FROM (NOW()-created_at))),0) AS oldest_age_seconds
                FROM max_webhook_events GROUP BY status''')
            metrics = [{**dict(row), 'oldest_age_seconds': float(row['oldest_age_seconds'])} for row in cursor.fetchall()]
        alerts = [row['status'] for row in metrics if row['count'] and (row['status'] in {'failed', 'needs_attention'}
            or row['status'] in {'pending','processing'} and row['oldest_age_seconds'] > 600)] if max_enabled() else []
        return jsonify(success=True, enabled=max_enabled(), schema_installed=installed,
            configured=bool(os.getenv('MAX_BOT_TOKEN') and os.getenv('MAX_WEBHOOK_SECRET') and os.getenv('MAX_BOT_USERNAME')),
            metrics=metrics, alerts=alerts)
    finally:
        db.conn.rollback()
        db.close()


@max_bp.post('/events/<event_key>/reconcile')
def max_reconcile_delivery(event_key):
    actor = require_auth_from_request()
    if not actor or not actor.get('is_superadmin') or actor.get('session_kind') == 'demo':
        return jsonify(success=False), 403
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict) or not isinstance(payload.get('message_ids', []), list) or len(payload.get('message_ids', [])) > 12:
        return jsonify(success=False), 400
    db = DatabaseManager()
    try:
        from services.operator_conversations import _row
        from services.max_reconciliation import inspect_delivery
        from services.max_transport import MaxTransport
        cursor = db.conn.cursor()
        cursor.execute("SELECT result_json,status FROM max_webhook_events WHERE event_key=%s AND status IN ('failed','needs_attention')", (event_key,))
        event = _row(cursor, cursor.fetchone())
        if not event:
            return jsonify(success=False, error='Запись не требует сверки'), 409
        reply = event.get('result_json') or {}
        evidence = inspect_delivery(reply, payload.get('message_ids') or reply.get('provider_message_ids') or [], MaxTransport())
        evidence['reviewed_by'] = str(actor.get('user_id') or actor.get('id'))
        cursor.execute('''UPDATE max_webhook_events SET result_json=COALESCE(result_json,'{}'::jsonb) || %s,
            status=CASE WHEN %s THEN 'completed' ELSE status END,
            completed_at=CASE WHEN %s THEN NOW() ELSE completed_at END
            WHERE event_key=%s AND status IN ('failed','needs_attention')''',
            (Json({'reconciliation': evidence}), evidence['verified'], evidence['verified'], event_key))
        db.conn.commit()
        return jsonify(success=True, evidence=evidence)
    finally:
        db.conn.rollback()
        db.close()
