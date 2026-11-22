"""Scoped, fail-closed protection for LocalOS. No provider calls live here."""

import contextlib
import contextvars
import hashlib
import hmac
import json
import os
import re
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from functools import lru_cache

from services.pii_protection.rules import protected_findings
from services.pii_protection.public_context import validated_public_spans


TOKEN = re.compile(r"<<PII_[A-Z_]+:[0-9a-f]{32}>>")
MAX_CHARS = 100_000


class PIIProtectionError(RuntimeError):
    """Only fixed reason codes may escape this boundary."""

    def __init__(self, code="PII_PROTECTION_FAILED"):
        super().__init__(code if re.fullmatch(r"PII_[A-Z_]+", code) else "PII_PROTECTION_FAILED")


def enabled():
    from services.pii_protection.activation import active
    return active()


@dataclass(frozen=True, repr=False)
class Scope:
    business_id: str
    user_id: str
    session_id: str

    def encoded(self):
        values = (self.business_id, self.user_id, self.session_id)
        if any(not isinstance(value, str) or not value or len(value) > 200 for value in values):
            raise PIIProtectionError("PII_SCOPE_REQUIRED")
        return json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode()


class MemoryStore:
    """Explicit test-only store. Runtime enforcement requires shared Redis."""

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.values = {}
        self.lock = threading.RLock()

    def put(self, key, value, ttl):
        with self.lock:
            now = self.clock()
            self.values = {item: entry for item, entry in self.values.items() if entry[0] > now}
            if len(self.values) >= 10_000:
                raise PIIProtectionError("PII_STORE_FULL")
            self.values[key] = (now + ttl, value)

    def get(self, key):
        with self.lock:
            entry = self.values.get(key)
            if not entry or entry[0] <= self.clock():
                self.values.pop(key, None)
                return None
            return entry[1]


class RedisStore:
    def __init__(self, url):
        import redis
        self.client = redis.Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2,
                                           decode_responses=False)

    def put(self, key, value, ttl):
        if not self.client.set(key, value, ex=ttl):
            raise PIIProtectionError("PII_STORE_UNAVAILABLE")

    def get(self, key):
        return self.client.get(key)


class ProtectionService:
    def __init__(self, engine, store, encryption_key, ttl=900):
        from cryptography.fernet import Fernet
        if not 60 <= ttl <= 86_400:
            raise PIIProtectionError("PII_TTL_INVALID")
        self.engine = engine
        self.store = store
        self.cipher = Fernet(encryption_key)
        self.secret = hmac.digest(encryption_key, b"localos-pii-token-v1", "sha256")
        self.ttl = ttl
        self.scan_lock = threading.Lock()

    def digest(self, value):
        return hmac.new(self.secret, value, hashlib.sha256).hexdigest()

    def scope_key(self, scope):
        return self.digest(scope.encoded())

    def mapping_key(self, scope, token):
        return "localos:pii:v1:" + self.scope_key(scope) + ":" + self.digest(token.encode())

    def issue(self, scope, kind, original):
        message = scope.encoded() + b"\x00" + kind.encode() + b"\x00" + original.encode()
        token = "<<PII_" + kind + ":" + self.digest(message)[:32] + ">>"
        payload = json.dumps({"scope": self.scope_key(scope), "token": token,
                              "kind": kind, "value": original}, ensure_ascii=False).encode()
        self.store.put(self.mapping_key(scope, token), self.cipher.encrypt(payload), self.ttl)
        return token

    def resolve(self, scope, token):
        blob = self.store.get(self.mapping_key(scope, token))
        if not blob:
            raise PIIProtectionError("PII_MAPPING_EXPIRED")
        try:
            payload = json.loads(self.cipher.decrypt(blob, ttl=self.ttl))
        except Exception:
            raise PIIProtectionError("PII_MAPPING_INVALID") from None
        if payload.get("scope") != self.scope_key(scope) or payload.get("token") != token:
            raise PIIProtectionError("PII_SCOPE_MISMATCH")
        return payload["value"]

    def protect(self, text, scope, policy="private", allowed_tokens=(), *, public_context=()):
        scope.encoded()
        if not isinstance(text, str) or len(text) > MAX_CHARS:
            raise PIIProtectionError("PII_INPUT_TOO_LARGE")
        try:
            public_spans = validated_public_spans(text, scope.business_id, policy, public_context)
        except ValueError:
            raise PIIProtectionError("PII_PUBLIC_CONTEXT_INVALID") from None
        allowed = set(allowed_tokens)
        incoming = set(TOKEN.findall(text))
        if incoming - allowed or "<<PII_" in TOKEN.sub("", text):
            raise PIIProtectionError("PII_UNTRUSTED_PLACEHOLDER")
        # Keep offsets intact while excluding already-issued placeholders from NLP.
        scan_text = TOKEN.sub(lambda match: " " * len(match.group()), text)
        with self.scan_lock:
            native = self.engine.scan(scan_text)
        findings = protected_findings(scan_text, native.findings, policy, public_spans)
        if len(findings) > 2000:
            raise PIIProtectionError("PII_TOO_MANY_ENTITIES")
        result = text
        issued = set(incoming)
        for finding in reversed(findings):
            original = text[finding.start:finding.end]
            # Secrets never enter the reversible mapping store.
            token = "[SECRET_REDACTED]" if finding.kind == "SECRET" else self.issue(scope, finding.kind, original)
            if finding.kind != "SECRET":
                issued.add(token)
            result = result[:finding.start] + token + result[finding.end:]
        return Exchange(self, scope, result, frozenset(issued), len(findings))


@dataclass(repr=False)
class Exchange:
    service: ProtectionService
    scope: Scope
    text: str
    issued: frozenset[str]
    entity_count: int

    def restore_text(self, text):
        if not isinstance(text, str):
            raise PIIProtectionError("PII_OUTPUT_INVALID")
        if "<<PII_" in TOKEN.sub("", text):
            raise PIIProtectionError("PII_UNTRUSTED_PLACEHOLDER")

        def replace(match):
            token = match.group()
            if token not in self.issued:
                raise PIIProtectionError("PII_UNTRUSTED_PLACEHOLDER")
            return self.service.resolve(self.scope, token)

        return TOKEN.sub(replace, text)

    def restore_value(self, value):
        if isinstance(value, str):
            return self.restore_text(value)
        if isinstance(value, list):
            return [self.restore_value(item) for item in value]
        if isinstance(value, dict):
            if any("<<PII_" in str(key) for key in value):
                raise PIIProtectionError("PII_OUTPUT_INVALID")
            return {key: self.restore_value(item) for key, item in value.items()}
        return value

    def restore_tool(self, tool_name, arguments, *, scope, allowed_fields, authorized, operation="read", approved=False):
        """Server-owned allowlist and authorization, never values supplied by a model."""
        if scope != self.scope or not authorized:
            raise PIIProtectionError("PII_TOOL_SCOPE_DENIED")
        if not tool_name or operation not in {"read", "preview", "write"}:
            raise PIIProtectionError("PII_TOOL_DENIED")
        if operation == "write" and not approved:
            raise PIIProtectionError("PII_TOOL_APPROVAL_REQUIRED")
        if not isinstance(arguments, dict):
            raise PIIProtectionError("PII_TOOL_ARGUMENT_DENIED")
        result = {}
        for key, value in arguments.items():
            contains_token = "<<PII_" in json.dumps(value, ensure_ascii=False)
            if contains_token and (not isinstance(value, str) or key not in allowed_fields or key in {"business_id", "user_id", "organization_id", "session_id", "url", "endpoint", "tool"}):
                raise PIIProtectionError("PII_TOOL_ARGUMENT_DENIED")
            result[key] = self.restore_value(value) if contains_token else value
        return result

    def restore_stream(self, chunks):
        """Buffer split tokens. Only authorized display text uses this path."""
        buffer = ""
        for chunk in chunks:
            buffer += chunk
            while buffer:
                opening = buffer.find("<<PII_")
                if opening >= 0:
                    if opening:
                        yield buffer[:opening]
                        buffer = buffer[opening:]
                    closing = buffer.find(">>")
                    if closing < 0:
                        if len(buffer) > 128:
                            raise PIIProtectionError("PII_UNTRUSTED_PLACEHOLDER")
                        break
                    yield self.restore_text(buffer[:closing + 2])
                    buffer = buffer[closing + 2:]
                else:
                    keep = next((size for size in range(min(len(buffer), 6), 0, -1)
                                 if buffer.endswith("<<PII_"[:size])), 0)
                    if len(buffer) > keep:
                        yield buffer[:-keep] if keep else buffer
                        buffer = buffer[-keep:] if keep else ""
                    break
        if buffer:
            if "<<" in buffer:
                raise PIIProtectionError("PII_UNTRUSTED_PLACEHOLDER")
            yield buffer


@lru_cache(maxsize=1)
def runtime_service():
    from services.pii_protection.runtime_config import CLIENT_CONFIG
    config_file = os.getenv("PII_RUNTIME_CONFIG_FILE", CLIENT_CONFIG)
    transport = os.getenv("PII_RUNTIME_TRANSPORT", "auto")
    if transport not in {"auto", "shared", "local"}:
        raise PIIProtectionError("PII_RUNTIME_CONFIGURATION_REQUIRED")
    if transport == "shared" or (transport == "auto" and os.path.lexists(config_file)):
        from services.pii_protection.remote import RemoteProtectionService
        return RemoteProtectionService.from_file(config_file)
    from services.pii_protection.engines import make_engine
    key = os.getenv("PII_MAPPING_KEY", "").encode()
    url = os.getenv("PII_REDIS_URL", "")
    if not key or not url:
        raise PIIProtectionError("PII_CONFIGURATION_REQUIRED")
    return ProtectionService(make_engine(os.getenv("PII_PROTECTION_ENGINE", "piighost_presidio")),
                             RedisStore(url), key, int(os.getenv("PII_MAPPING_TTL_SECONDS", "900")))


@dataclass(repr=False)
class Job:
    service: ProtectionService
    scope: Scope
    policy: str
    public_context: tuple = ()
    issued: set[str] = field(default_factory=set)
    last_exchange: Exchange | None = None


_job = contextvars.ContextVar("localos_pii_job", default=None)
_outbound = contextvars.ContextVar("localos_pii_outbound", default=None)


@contextlib.contextmanager
def outbound(exchange):
    marker = _outbound.set(exchange)
    try:
        yield
    finally:
        _outbound.reset(marker)


def assert_protected_transport(body=None):
    """Deny legacy direct calls, embeddings and multimodal payloads in this pilot."""
    if not enabled():
        return
    exchange = _outbound.get()
    if not exchange or not isinstance(body, dict) or any(key in body for key in ("input", "files", "functions", "tools")):
        raise PIIProtectionError("PII_UNPROTECTED_ROUTE")
    allowed_keys = {"model", "messages", "temperature", "max_tokens", "parameters", "thinking", "response_format"}
    if set(body) - allowed_keys:
        raise PIIProtectionError("PII_UNPROTECTED_ROUTE")
    messages = body.get("messages")
    if (not isinstance(messages, list) or len(messages) != 1
            or not isinstance(messages[0], dict) or messages[0].get("role") != "user"
            or set(messages[0]) - {"role", "content"}):
        raise PIIProtectionError("PII_UNPROTECTED_ROUTE")
    allowed = {exchange.text, exchange.text + "\n\nReturn only a valid JSON object without markdown."}
    if not isinstance(messages[0].get("content"), str) or messages[0]["content"] not in allowed:
        raise PIIProtectionError("PII_UNPROTECTED_ROUTE")


def prepare_attempt(prompt):
    job = _job.get()
    if job is None:
        raise PIIProtectionError("PII_SCOPE_REQUIRED")
    exchange = job.service.protect(prompt, job.scope, job.policy, job.issued, public_context=job.public_context)
    job.issued.update(exchange.issued)
    job.last_exchange = exchange
    return exchange


def _is_tool_output(value):
    if isinstance(value, dict):
        if ({"function_call", "tool_calls"} & value.keys()
                or value.get("action") == "tool_call"
                or {"tool", "arguments"} <= value.keys()):
            return True
        return any(_is_tool_output(item) for item in value.values())
    if isinstance(value, list):
        return any(_is_tool_output(item) for item in value)
    return False


def run_with_privacy(request, execute):
    if not enabled():
        return execute()
    from services.llm.contracts import LLMTaskResult
    marker = None
    try:
        from services.pii_protection.activation import configuration
        if configuration()['mode'] == 'blocked':
            raise PIIProtectionError('PII_ACTIVATION_BLOCKED')
        scope = Scope(request.business_id, request.user_id, request.pii_session_id or uuid.uuid4().hex)
        scope.encoded()
        # Model- or user-supplied placeholder strings are never accepted on ingress.
        if "<<PII_" in request.prompt:
            raise PIIProtectionError("PII_UNTRUSTED_PLACEHOLDER")
        job = Job(runtime_service(), scope, request.pii_policy, request.pii_public_context)
        marker = _job.set(job)
        mode = os.getenv("PII_PROTECTION_MODE", "enforce")
        if mode == "diagnostic":
            prepare_attempt(request.prompt)
            return LLMTaskResult(status="policy_blocked", fallback_reason="PII_DIAGNOSTIC_NO_PROVIDER")
        if mode != "enforce":
            raise PIIProtectionError("PII_CONFIGURATION_REQUIRED")
        result = execute()
        if result.status == "completed" and job.last_exchange:
            exchange = job.last_exchange
            if request.task_key == "operator_tool_plan":
                result.pii_context = exchange
                return result
            # Legacy agent callers must not receive restored tool arguments by
            # masquerading as an ordinary text/JSON generation task.
            if (_is_tool_output(result.parsed_data)
                    or re.search(r'"(?:function_call|tool_calls)"\s*:|"action"\s*:\s*"tool_call"', result.content)):
                raise PIIProtectionError("PII_TOOL_DENIED")
            if result.parsed_data is not None:
                result.parsed_data = exchange.restore_value(result.parsed_data)
                result.content = json.dumps(result.parsed_data, ensure_ascii=False)
            else:
                try:
                    value = json.loads(result.content)
                except (ValueError, TypeError):
                    value = None
                if _is_tool_output(value):
                    raise PIIProtectionError("PII_TOOL_DENIED")
                result.content = (json.dumps(exchange.restore_value(value), ensure_ascii=False)
                                  if isinstance(value, (dict, list)) else exchange.restore_text(result.content))
        return result
    except Exception:
        failure = sys.exception()
        code = str(failure) if isinstance(failure, PIIProtectionError) else "PII_PROTECTION_FAILED"
        return LLMTaskResult(status="policy_blocked", fallback_reason=code)
    finally:
        if marker is not None:
            _job.reset(marker)
