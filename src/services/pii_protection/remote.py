"""Authenticated, certificate-verified client for the single-host PII runtime."""

import http.client
import json
import re
import ssl
import threading
import time
from urllib.parse import urlsplit

from services.pii_protection.gateway import Exchange, MAX_CHARS, PIIProtectionError, TOKEN
from services.pii_protection.public_context import validated_public_spans
from services.pii_protection.runtime_config import read_secret_json

MAX_WIRE_BYTES = 512 * 1024


class RemoteProtectionService:
    def __init__(self, endpoint, bearer_token, ca_pem):
        try:
            parsed = urlsplit(endpoint)
            if (parsed.scheme != 'https' or parsed.hostname not in {'localos-pii-runtime', 'localhost', '127.0.0.1'}
                    or parsed.username or parsed.password or parsed.query or parsed.fragment
                    or parsed.path not in {'', '/'} or not 1 <= parsed.port <= 65535
                    or not isinstance(bearer_token, str) or not 40 <= len(bearer_token) <= 200
                    or not bearer_token.isascii()
                    or any(not (char.isalnum() or char in '-_') for char in bearer_token)):
                raise ValueError()
            context = ssl.create_default_context(cadata=ca_pem)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
        except Exception:
            raise PIIProtectionError('PII_RUNTIME_CONFIGURATION_REQUIRED') from None
        self.host, self.port = parsed.hostname, parsed.port
        self._token = bearer_token
        self._tls = context
        self._connections = threading.local()

    @classmethod
    def from_file(cls, path):
        config = read_secret_json(path)
        if set(config) != {'version', 'endpoint', 'bearer_token', 'ca_pem'}:
            raise PIIProtectionError('PII_RUNTIME_CONFIGURATION_REQUIRED')
        return cls(config['endpoint'], config['bearer_token'], config['ca_pem'])

    def _connection(self):
        connection = getattr(self._connections, 'value', None)
        if connection is not None and time.monotonic() - self._connections.used_at > 3:
            self._close()
            connection = None
        if connection is None:
            connection = http.client.HTTPSConnection(self.host, self.port, timeout=2, context=self._tls)
            connection.connect()
            connection.sock.settimeout(15)
            self._connections.value = connection
            self._connections.used_at = time.monotonic()
        return connection

    def _close(self):
        connection = getattr(self._connections, 'value', None)
        if connection is not None:
            connection.close()
            self._connections.value = None

    def _call(self, path, payload):
        try:
            data = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode()
            if len(data) > MAX_WIRE_BYTES:
                raise PIIProtectionError('PII_INPUT_TOO_LARGE')
            connection = self._connection()
            connection.request('POST', path, body=data, headers={
                'Content-Type': 'application/json', 'Authorization': 'Bearer ' + self._token,
            })
            response = connection.getresponse()
            body = response.read(MAX_WIRE_BYTES + 1)
            self._connections.used_at = time.monotonic()
            if len(body) > MAX_WIRE_BYTES:
                raise PIIProtectionError('PII_RUNTIME_RESPONSE_INVALID')
            value = json.loads(body)
            if not isinstance(value, dict):
                raise PIIProtectionError('PII_RUNTIME_RESPONSE_INVALID')
            if response.status != 200:
                code = value.get('error')
                if (set(value) == {'error'} and isinstance(code, str) and len(code) <= 64
                        and re.fullmatch(r'PII_[A-Z_]+', code)):
                    raise PIIProtectionError(code)
                raise PIIProtectionError('PII_RUNTIME_UNAVAILABLE')
            return value
        except PIIProtectionError:
            self._close()
            raise
        except Exception:
            self._close()
            # No retries or fallback to a local model/plaintext route.
            raise PIIProtectionError('PII_RUNTIME_UNAVAILABLE') from None

    def protect(self, text, scope, policy='private', allowed_tokens=(), *, public_context=()):
        scope.encoded()
        if not isinstance(text, str) or len(text) > MAX_CHARS:
            raise PIIProtectionError('PII_INPUT_TOO_LARGE')
        try:
            validated_public_spans(text, scope.business_id, policy, public_context)
        except ValueError:
            raise PIIProtectionError('PII_PUBLIC_CONTEXT_INVALID') from None
        if (not isinstance(allowed_tokens, (tuple, list, set, frozenset)) or len(allowed_tokens) > 2000
                or any(not isinstance(token, str) or not TOKEN.fullmatch(token) for token in allowed_tokens)):
            raise PIIProtectionError('PII_UNTRUSTED_PLACEHOLDER')
        context = [{name: getattr(span, name) for name in
                    ('business_id', 'source_id', 'kind', 'start', 'end', 'value')} for span in public_context]
        value = self._call('/v1/protect', {
            'scope': {'business_id': scope.business_id, 'user_id': scope.user_id, 'session_id': scope.session_id},
            'text': text, 'policy': policy, 'allowed_tokens': sorted(allowed_tokens), 'public_context': context,
        })
        issued = value.get('issued')
        if (set(value) != {'text', 'issued', 'entity_count'} or not isinstance(value.get('text'), str)
                or len(value['text']) > MAX_WIRE_BYTES or not isinstance(issued, list) or len(issued) > 2000
                or any(not isinstance(token, str) or not TOKEN.fullmatch(token) for token in issued)
                or not isinstance(value.get('entity_count'), int) or isinstance(value['entity_count'], bool)
                or not 0 <= value['entity_count'] <= 2000
                or set(TOKEN.findall(value['text'])) - set(issued)
                or '<<PII_' in TOKEN.sub('', value['text'])):
            raise PIIProtectionError('PII_RUNTIME_RESPONSE_INVALID')
        return Exchange(self, scope, value['text'], frozenset(issued), value['entity_count'])

    def resolve(self, scope, token):
        scope.encoded()
        if not isinstance(token, str) or not TOKEN.fullmatch(token):
            raise PIIProtectionError('PII_UNTRUSTED_PLACEHOLDER')
        value = self._call('/v1/resolve', {
            'scope': {'business_id': scope.business_id, 'user_id': scope.user_id, 'session_id': scope.session_id},
            'token': token,
        })
        if set(value) != {'value'} or not isinstance(value['value'], str) or len(value['value']) > MAX_CHARS:
            raise PIIProtectionError('PII_RUNTIME_RESPONSE_INVALID')
        return value['value']
