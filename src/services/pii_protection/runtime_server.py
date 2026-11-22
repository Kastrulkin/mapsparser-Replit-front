"""Private TLS API: one model lane, bounded waiting, encrypted Redis mappings."""

import hmac
import os
import threading
import time
import uuid

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from services.pii_protection.gateway import MAX_CHARS, PIIProtectionError, ProtectionService, RedisStore, Scope, TOKEN
from services.pii_protection.public_context import PublicSpan
from services.pii_protection.runtime_config import SERVER_CONFIG, read_secret_json
from services.pii_protection.admission import AdmissionLimiter


def _scope(value):
    if not isinstance(value, dict) or set(value) != {'business_id', 'user_id', 'session_id'}:
        raise PIIProtectionError('PII_SCOPE_REQUIRED')
    scope = Scope(**value)
    scope.encoded()
    return scope


def create_app(config=None, service=None, terminate=os._exit):
    config = config if config is not None else read_secret_json(os.getenv('PII_SERVER_CONFIG_FILE', SERVER_CONFIG))
    token = config.get('bearer_token')
    deadline = config.get('recognition_timeout_seconds', 10)
    if (not isinstance(token, str) or not 40 <= len(token) <= 200
            or not isinstance(deadline, (int, float)) or not 1 <= deadline <= 15):
        raise PIIProtectionError('PII_RUNTIME_CONFIGURATION_REQUIRED')
    warmed = False
    if service is None:
        from services.pii_protection.engines import make_engine
        service = ProtectionService(make_engine('piighost_presidio'), RedisStore(config['redis_url']),
                                    config['mapping_key'].encode(), config.get('mapping_ttl_seconds', 900))
        if not service.store.client.ping():
            raise PIIProtectionError('PII_STORE_UNAVAILABLE')
        try:
            scope = Scope('synthetic-runtime-startup', 'synthetic-diagnostic', 'synthetic-' + uuid.uuid4().hex)
            for text in ('Full name: Mira Exampleton; email: synthetic-startup@example.invalid',
                         'Имя клиента: Ирина Синтетическая; email: synthetic-startup-ru@example.invalid'):
                exchange = service.protect(text, scope)
                if exchange.restore_text(exchange.text) != text:
                    raise ValueError()
        except Exception:
            raise PIIProtectionError('PII_RUNTIME_INITIALIZATION_FAILED') from None
        warmed = True
    app = Flask(__name__)
    app.config.update(MAX_CONTENT_LENGTH=512 * 1024, DEBUG=False, TESTING=False)
    lane = threading.BoundedSemaphore(1)
    admission = AdmissionLimiter(config)
    state_lock = threading.Lock()
    state = {'active_since': None, 'protect_ok': 0, 'resolve_ok': 0, 'busy': 0}
    stopped = threading.Event()
    app.extensions['pii_watchdog_stop'] = stopped

    def authorize_scope(value):
        scope = _scope(value)
        if config.get('synthetic_only', True) is not False and any(
                not item.startswith('synthetic-') for item in
                (scope.business_id, scope.user_id, scope.session_id)):
            raise PIIProtectionError('PII_RUNTIME_COHORT_DENIED')
        return scope

    def watchdog():
        while not stopped.wait(0.25):
            with state_lock:
                started = state['active_since']
            if started is not None and time.monotonic() - started > deadline:
                # Master restarts the worker. The original model process exits first.
                terminate(70)
                return

    threading.Thread(target=watchdog, daemon=True, name='pii-deadline').start()

    @app.before_request
    def authorize():
        if request.path == '/health' and request.method == 'GET':
            return None
        supplied = request.headers.get('Authorization', '')
        if not hmac.compare_digest(supplied.encode(), ('Bearer ' + token).encode()):
            return jsonify(error='PII_RUNTIME_AUTH_REQUIRED'), 401
        if request.method == 'POST' and request.mimetype != 'application/json':
            return jsonify(error='PII_INPUT_INVALID'), 400
        return None

    @app.errorhandler(Exception)
    def failed(error):
        if isinstance(error, PIIProtectionError):
            code = str(error)
            status = 429 if code == 'PII_RUNTIME_RATE_LIMITED' else 503 if code in {'PII_RUNTIME_BUSY', 'PII_STORE_UNAVAILABLE'} else 400
        elif isinstance(error, HTTPException):
            code = 'PII_INPUT_TOO_LARGE' if error.code == 413 else 'PII_INPUT_INVALID'
            status = error.code if error.code in {400, 404, 405, 413} else 400
        else:
            code, status = 'PII_RUNTIME_FAILED', 503
        response = jsonify(error=code)
        if status in {429, 503}:
            response.headers['Retry-After'] = '1'
        return response, status

    def body(fields):
        value = request.get_json()
        if not isinstance(value, dict) or set(value) != set(fields):
            raise PIIProtectionError('PII_INPUT_INVALID')
        return value

    @app.get('/health')
    def health():
        try:
            if hasattr(service.store, 'client') and not service.store.client.ping():
                raise ValueError()
        except Exception:
            return jsonify(error='PII_STORE_UNAVAILABLE'), 503
        return jsonify(status='ok')

    @app.post('/v1/protect')
    def protect():
        value = body(('scope', 'text', 'policy', 'allowed_tokens', 'public_context'))
        scope = authorize_scope(value['scope'])
        text, policy = value['text'], value['policy']
        if not isinstance(text, str) or len(text) > MAX_CHARS:
            raise PIIProtectionError('PII_INPUT_TOO_LARGE')
        if not isinstance(policy, str) or policy not in {'private', 'content', 'public_geo'}:
            raise PIIProtectionError('PII_POLICY_UNKNOWN')
        allowed = value['allowed_tokens']
        if (not isinstance(allowed, list) or len(allowed) > 2000
                or any(not isinstance(item, str) or not TOKEN.fullmatch(item) for item in allowed)):
            raise PIIProtectionError('PII_UNTRUSTED_PLACEHOLDER')
        context = value['public_context']
        fields = {'business_id', 'source_id', 'kind', 'start', 'end', 'value'}
        if (not isinstance(context, list) or len(context) > 100
                or any(not isinstance(item, dict) or set(item) != fields for item in context)):
            raise PIIProtectionError('PII_PUBLIC_CONTEXT_INVALID')
        public = tuple(PublicSpan(**item) for item in context)
        if not admission.admit(scope.business_id):
            raise PIIProtectionError('PII_RUNTIME_RATE_LIMITED')
        if not lane.acquire(timeout=0.25):
            with state_lock:
                state['busy'] += 1
            raise PIIProtectionError('PII_RUNTIME_BUSY')
        try:
            with state_lock:
                state['active_since'] = time.monotonic()
            for item in allowed:
                service.resolve(scope, item)
            result = service.protect(text, scope, policy, allowed, public_context=public)
            with state_lock:
                state['protect_ok'] += 1
            return jsonify(text=result.text, issued=sorted(result.issued), entity_count=result.entity_count)
        finally:
            with state_lock:
                state['active_since'] = None
            lane.release()

    @app.post('/v1/resolve')
    def resolve():
        value = body(('scope', 'token'))
        scope = authorize_scope(value['scope'])
        if not isinstance(value['token'], str) or not TOKEN.fullmatch(value['token']):
            raise PIIProtectionError('PII_UNTRUSTED_PLACEHOLDER')
        original = service.resolve(scope, value['token'])
        with state_lock:
            state['resolve_ok'] += 1
        return jsonify(value=original)

    @app.post('/v1/status')
    def status():
        body(())
        with state_lock:
            counts = {key: state[key] for key in ('protect_ok', 'resolve_ok', 'busy')}
        return jsonify(status='ok', model_lanes=1, model_pid=os.getpid(), warmup_completed=warmed,
                       synthetic_only=config.get('synthetic_only', True) is not False, **admission.status(), **counts)

    return app
