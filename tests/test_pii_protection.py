"""Synthetic-only privacy contract and real-library regression tests."""

import concurrent.futures
import hashlib
import json
import socket
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import os
import multiprocessing
import time

import pytest

from services.llm.contracts import LLMTaskDefinition, LLMTaskRequest
from services.pii_protection.engines import make_engine
from services.pii_protection.gateway import (
    Exchange, MemoryStore, PIIProtectionError, ProtectionService, Scope, TOKEN,
)
from services.pii_protection.public_context import PublicSpan
from scripts.pii_pilot.public_inputs import public_context_for_case


CORPUS_PATH = Path(__file__).parent / "fixtures/pii/synthetic_200.jsonl"
CASES = [json.loads(line) for line in CORPUS_PATH.read_text().splitlines()]


@pytest.fixture(scope="module")
def real_engine():
    pytest.importorskip("piighost")
    pytest.importorskip("presidio_analyzer")
    return make_engine("piighost_presidio")


@pytest.fixture
def service(real_engine, request):
    from cryptography.fernet import Fernet
    if getattr(request, "param", "memory") == "redis":
        from services.pii_protection.gateway import RedisStore
        url = os.getenv("PII_TEST_REDIS_URL", "")
        if not url:
            pytest.skip("Dedicated loopback Linux Redis not requested")
        if url != "redis://127.0.0.1:16379/15":
            raise RuntimeError("Only the dedicated ephemeral pilot Redis is allowed")
        return ProtectionService(real_engine, RedisStore(url), Fernet.generate_key())
    return ProtectionService(real_engine, MemoryStore(), Fernet.generate_key())


@pytest.fixture
def scope():
    return Scope("synthetic-business", "synthetic-user", "synthetic-session")


@pytest.fixture(autouse=True)
def deny_external_network(monkeypatch):
    connect = socket.socket.connect
    lookup = socket.getaddrinfo

    def local_only(connection, address):
        if not isinstance(address, tuple) or address[0] != "127.0.0.1":
            raise AssertionError("Only the loopback mock provider is allowed")
        return connect(connection, address)

    monkeypatch.setattr(socket.socket, "connect", local_only)

    def local_lookup(host, *args, **kwargs):
        if host != "127.0.0.1":
            raise AssertionError("External DNS is disabled")
        return lookup(host, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", local_lookup)


def test_corpus_is_frozen_and_synthetic():
    assert len(CASES) == 200
    assert hashlib.sha256(CORPUS_PATH.read_bytes()).hexdigest() == "ab660f83cf8e139525282b93d1c814dffcf1f9d1d73b5c9945833e33eafdf862"
    assert {case["language"] for case in CASES} == {"ru", "en", "tr", "de", "ar", "mixed"}
    assert len({case["id"] for case in CASES}) == 200
    for case in CASES:
        assert case["id"].startswith("synthetic-")
        for item in case["entities"]:
            assert case["text"][item["start"]:item["end"]] == item["value"]


def test_detection_never_emits_payload_traces(real_engine):
    assert all(not pipeline._tracer.is_active() for pipeline in real_engine.pipelines.values())


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_200_synthetic_cases_critical_fields_and_roundtrip(service, scope, case):
    exchange = service.protect(case["text"], scope, case["policy"], public_context=public_context_for_case(case["id"]))
    for item in case["entities"]:
        if item["critical"]:
            assert item["value"] not in exchange.text
    if any(item["type"] == "SECRET" for item in case["entities"]):
        assert "SECRET_REDACTED" in exchange.text
        assert all(item["value"] not in repr(service.store.values) for item in case["entities"])
    else:
        assert exchange.restore_text(exchange.text) == case["text"]


def test_original_name_and_verified_geo_regressions_are_fixed(service, scope):
    misses = []
    public_failures = []
    for case in CASES:
        result = service.protect(case["text"], scope, case["policy"], public_context=public_context_for_case(case["id"]))
        if any(item["value"] in result.text for item in case["entities"]):
            misses.append(case["id"])
        if any(value not in result.text for value in case["allowed_public"]):
            public_failures.append(case["id"])
    assert misses == []
    assert public_failures == []


def test_scopes_stable_tokens_and_encrypted_storage(service, scope):
    text = "Email: synthetic@example.invalid"
    first = service.protect(text, scope)
    second = service.protect(text, scope)
    foreign = service.protect(text, replace(scope, business_id="another-business"))
    assert first.text == second.text
    assert first.text != foreign.text
    assert "synthetic@example.invalid" not in repr(service.store.values)
    assert scope.business_id not in repr(service.store.values)
    assert "synthetic@example.invalid" not in repr(first)
    assert "synthetic@example.invalid" not in repr(scope)
    assert second.restore_text(second.text) == text


@pytest.mark.parametrize("field", ("business_id", "user_id", "session_id"))
def test_foreign_scope_cannot_resolve(service, scope, field):
    result = service.protect("Email: private@example.invalid", scope)
    token = next(iter(result.issued))
    with pytest.raises(PIIProtectionError):
        service.resolve(replace(scope, **{field: "foreign"}), token)


def test_unknown_same_scope_token_and_forged_input_are_denied(service, scope):
    first = service.protect("Email: first@example.invalid", scope)
    second = service.protect("Email: second@example.invalid", scope)
    with pytest.raises(PIIProtectionError):
        first.restore_text(second.text)
    with pytest.raises(PIIProtectionError):
        service.protect(second.text, scope)
    with pytest.raises(PIIProtectionError):
        first.restore_text("<<PII_EMAIL:" + "0" * 32 + ">>")


def test_expired_missing_corrupt_mapping_and_invalid_config(service, scope):
    result = service.protect("Email: expiry@example.invalid", scope)
    token = next(iter(result.issued))
    key = service.mapping_key(scope, token)
    service.store.values[key] = (0, b"expired")
    with pytest.raises(PIIProtectionError):
        result.restore_text(result.text)
    service.store.put(key, b"corrupt", 900)
    with pytest.raises(PIIProtectionError):
        result.restore_text(result.text)
    with pytest.raises(PIIProtectionError):
        service.protect("hello", replace(scope, session_id=""))


def test_stream_restores_every_possible_split(service, scope):
    text = "Email: stream@example.invalid"
    result = service.protect(text, scope)
    for position in range(len(result.text) + 1):
        assert "".join(result.restore_stream([result.text[:position], result.text[position:]])) == text
    assert "".join(result.restore_stream(iter(result.text))) == text
    with pytest.raises(PIIProtectionError):
        list(result.restore_stream(["<<PII_EMAIL:"]))


def test_json_restoration_escapes_quotes_and_preserves_types(service, scope):
    original = 'Ирина "Синтетическая" \\ имя'
    token = service.issue(scope, "PERSON", original)
    result = Exchange(service, scope, token, frozenset({token}), 1)
    value = {"name": token, "count": 2, "active": True, "nested": [token]}
    restored = result.restore_value(value)
    assert json.loads(json.dumps(restored))["name"] == original
    assert restored["count"] == 2 and restored["active"] is True
    with pytest.raises(PIIProtectionError):
        result.restore_value({token: "forged key"})


def test_tool_restore_requires_scope_fields_and_approval(service, scope):
    result = service.protect("Email: client@example.invalid", scope)
    token = next(iter(result.issued))
    arguments = {"email": token, "service": "haircut"}
    assert result.restore_tool("crm.find", arguments, scope=scope, allowed_fields=("email",), authorized=True)["email"] == "client@example.invalid"
    for changed in ({"authorized": False}, {"scope": replace(scope, user_id="foreign")},
                    {"allowed_fields": ()}, {"operation": "write"}):
        options = {"scope": scope, "allowed_fields": ("email",), "authorized": True, **changed}
        with pytest.raises(PIIProtectionError):
            result.restore_tool("crm.find", arguments, **options)
    with pytest.raises(PIIProtectionError):
        result.restore_tool("http.fetch", {"url": token}, scope=scope, allowed_fields=("url",), authorized=True)
    assert result.restore_tool("crm.book", arguments, scope=scope, allowed_fields=("email",),
                               authorized=True, operation="write", approved=True)["email"] == "client@example.invalid"


@pytest.fixture
def mock_provider():
    captured = []
    behavior = {"reply": lambda prompt: "Received " + " ".join(TOKEN.findall(prompt))}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            raw = self.rfile.read(int(self.headers["Content-Length"]))
            captured.append(raw)
            body = json.loads(raw)
            reply = behavior["reply"](body["messages"][0]["content"])
            payload = json.dumps({"id": "synthetic-provider", "choices": [{"message": {"content": reply}, "finish_reason": "stop"}],
                                  "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}", captured, behavior
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


@pytest.fixture
def integrated(monkeypatch, service, scope, mock_provider):
    from services.llm import gateway
    from services.gigachat_client import GigaChatClient

    url, captured, behavior = mock_provider
    monkeypatch.setenv("PII_PROTECTION_ENABLED", "true")
    monkeypatch.setenv("PII_PROTECTION_MODE", "enforce")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "synthetic-not-a-credential")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", url)
    monkeypatch.setenv("GIGACHAT_KEYS", "synthetic:synthetic")
    monkeypatch.setenv("GIGACHAT_API_BASE_URL", url)
    monkeypatch.setenv("NO_PROXY", "*")
    monkeypatch.setenv("LLM_SHADOW_MODE", "false")
    monkeypatch.setattr("services.pii_protection.gateway.runtime_service", lambda: service)
    monkeypatch.setattr("services.ai_spend_budget.reserve", lambda *_, **__: "synthetic-budget")
    monkeypatch.setattr("services.ai_spend_budget.settle", lambda *_, **__: None)
    monkeypatch.setattr(gateway, "_record_result", lambda *_, **__: None)
    definition = LLMTaskDefinition("synthetic_task", "deepseek", "deepseek_reasoning", "business_internal")
    monkeypatch.setattr(gateway, "get_task_definition", lambda _: definition)
    monkeypatch.setattr(gateway, "_provider_for_request", lambda *_: "deepseek")
    client = GigaChatClient()
    monkeypatch.setattr(client, "get_access_token", lambda: "synthetic-token")
    monkeypatch.setattr("services.gigachat_client.get_gigachat_client", lambda: client)
    request = LLMTaskRequest("synthetic_task", "", business_id=scope.business_id, user_id=scope.user_id,
                             pii_session_id=scope.session_id)
    return gateway, request, captured, behavior


@pytest.mark.parametrize("provider", ("gigachat", "deepseek"))
def test_real_adapter_outgoing_payload_and_display_restoration(integrated, monkeypatch, provider):
    gateway, request, captured, _ = integrated
    monkeypatch.setattr(gateway, "_provider_for_request", lambda *_: provider)
    text = "Full name: Mira Exampleton; phone: +90 555 000 01 23; email: mira@example.invalid"
    result = gateway.run_llm_task(replace(request, prompt=text))
    assert result.status == "completed"
    assert len(captured) == 1
    raw = captured[0].decode()
    for value in ("Mira Exampleton", "+90 555 000 01 23", "mira@example.invalid"):
        assert value not in raw
        assert value in result.content
    assert "<<PII_" in raw and "<<PII_" not in result.content


@pytest.mark.parametrize("provider", ("gigachat", "deepseek"))
def test_all_200_scenarios_at_actual_http_boundary(integrated, monkeypatch, provider):
    gateway, request, captured, _ = integrated
    monkeypatch.setattr(gateway, "_provider_for_request", lambda *_: provider)
    sent = 0
    for case in CASES:
        before = len(captured)
        result = gateway.run_llm_task(replace(request, prompt=case["text"], pii_policy=case["policy"],
                                              pii_public_context=public_context_for_case(case["id"])))
        if len(captured) == before:
            assert result.status == "policy_blocked"
            continue
        sent += 1
        assert len(captured) == before + 1
        content = json.loads(captured[-1])["messages"][0]["content"]
        for item in case["entities"]:
            if item["critical"]:
                assert item["value"] not in content
        assert result.status == "completed"
    assert sent >= 150


@pytest.mark.parametrize("provider", ("gigachat", "deepseek"))
@pytest.mark.parametrize("service", ("redis",), indirect=True)
def test_all_200_scenarios_http_with_live_redis(integrated, monkeypatch, provider):
    test_all_200_scenarios_at_actual_http_boundary(integrated, monkeypatch, provider)


@pytest.mark.parametrize("name,text", (
    ("ليلى السالمية", "ليلى السالمية تريد إعادة جدولة الموعد."),
    ("يوسف التجريبي", "يوسف التجريبي يرغب في حجز موعد."),
    ("نور القمرية", "نور القمرية would like to book a consultation."),
    ("سارة النورية", "سارة النورية wants to change the appointment."),
    ("Алина Testbrook", "Алина Testbrook would like to reschedule."),
    ("Maria Примерская", "Maria Примерская needs to move the appointment."),
    ("Дениз Örnekova", "Дениз Örnekova wants to book tomorrow."),
    ("Жан van Testbrook", "Жан van Testbrook would like to book a haircut."),
    ("Ирине Примерской", "Позвоните Ирине Примерской после приёма."),
    ("Алина Синтетическая", "Алина Синтетическая просит перенести визит."),
    ("Mira Testbrook", "Please contact Mira Testbrook after lunch."),
    ("Deniz Örnekova", "Deniz Örnekova randevusunu değiştirmek istiyor."),
    ("Mira Beispielova", "Mira Beispielova möchte einen Termin verschieben."),
))
def test_contextual_names_with_unseen_spellings(service, scope, name, text):
    result = service.protect(text, scope)
    assert name not in result.text
    assert result.restore_text(result.text) == text


def test_verified_public_span_is_local_to_occurrence_and_tenant(service, scope):
    name = "Алина Testbrook"
    text = f"Company: {name}; {name} would like to reschedule."
    start = text.index(name)
    public = PublicSpan(scope.business_id, "synthetic-map-record", "ORGANIZATION", start, start + len(name), name)
    result = service.protect(text, scope, "public_geo", public_context=(public,))
    assert result.text.count(name) == 1
    assert "Company: " + name in result.text
    assert result.restore_text(result.text) == text
    with pytest.raises(PIIProtectionError):
        service.protect(text, replace(scope, business_id="foreign"), "public_geo", public_context=(public,))
    with pytest.raises(PIIProtectionError):
        service.protect(text, scope, "public_geo", public_context=(replace(public, start=start + 1),))
    with pytest.raises(PIIProtectionError):
        service.protect(text, scope, "public_geo", public_context=(replace(public, kind="PERSON"),))
    with pytest.raises(PIIProtectionError):
        service.protect(text, scope, "public_geo", public_context=({"value": name},))


@pytest.mark.parametrize("field,value", (("source_id", 10), ("kind", ["ORGANIZATION"]),
                                          ("start", False), ("end", True)))
def test_malformed_public_metadata_is_rejected(service, scope, field, value):
    text = "Company: Example Studio"
    start = text.index("Example")
    public = PublicSpan(scope.business_id, "synthetic-map-record", "ORGANIZATION", start, len(text), text[start:])
    with pytest.raises(PIIProtectionError, match="PII_PUBLIC_CONTEXT_INVALID"):
        service.protect(text, scope, "public_geo", public_context=(replace(public, **{field: value}),))


def test_unverified_company_label_does_not_exempt_a_person(service, scope):
    name = "Алина Testbrook"
    result = service.protect(f"Company: {name}; {name} would like to reschedule.", scope, "public_geo")
    assert name not in result.text
    assert name not in service.protect(f"{name}. Later {name} would like to reschedule.", scope).text


def test_public_exemption_never_clears_private_labels_or_critical_values(service, scope):
    text = "Company: Example Studio; customer_name: Mira Testbrook; email: public@example.invalid; phone: +90 555 000 01 23"
    public = PublicSpan(scope.business_id, "synthetic-map-record", "ORGANIZATION", 0, len(text), text)
    result = service.protect(text, scope, "public_geo", public_context=(public,))
    for value in ("Mira Testbrook", "public@example.invalid", "+90 555 000 01 23"):
        assert value not in result.text


def _redis_worker_resolve(key, scope, token, queue):
    from services.pii_protection.gateway import RedisStore
    service = ProtectionService(None, RedisStore("redis://127.0.0.1:16379/15"), key)
    queue.put(service.resolve(scope, token))


@pytest.mark.parametrize("service", ("redis",), indirect=True)
def test_real_redis_encryption_ttl_scope_and_corruption(service, scope):
    result = service.protect("Email: redis-only@example.invalid", scope)
    token = next(iter(result.issued))
    key = service.mapping_key(scope, token)
    client = service.store.client
    assert b"redis-only@example.invalid" not in client.get(key)
    assert 0 < client.ttl(key) <= 900
    with pytest.raises(PIIProtectionError):
        service.resolve(replace(scope, business_id="foreign"), token)
    client.expire(key, 1)
    deadline = time.monotonic() + 3
    while client.exists(key) and time.monotonic() < deadline:
        time.sleep(0.05)
    with pytest.raises(PIIProtectionError):
        result.restore_text(result.text)
    client.set(key, b"corrupt", ex=60)
    with pytest.raises(PIIProtectionError):
        result.restore_text(result.text)
    client.delete(key)


@pytest.mark.parametrize("service", ("redis",), indirect=True)
def test_real_redis_cross_process_resolution(service, scope):
    from cryptography.fernet import Fernet
    key = Fernet.generate_key()
    writer = ProtectionService(service.engine, service.store, key)
    result = writer.protect("Email: worker@example.invalid", scope)
    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    worker = context.Process(target=_redis_worker_resolve, args=(key, scope, next(iter(result.issued)), queue))
    worker.start()
    try:
        assert queue.get(timeout=15) == "worker@example.invalid"
        worker.join(timeout=5)
        assert worker.exitcode == 0
    finally:
        if worker.is_alive():
            worker.terminate()
            worker.join(timeout=5)
        queue.close()


@pytest.mark.parametrize("service", ("redis",), indirect=True)
def test_real_redis_parallel_tenant_isolation(service, scope):
    def protect(index):
        own_scope = replace(scope, business_id="business-" + str(index % 2), session_id="session-" + str(index))
        text = "Email: parallel" + str(index) + "@example.invalid"
        result = service.protect(text, own_scope)
        assert result.restore_text(result.text) == text
        return result.text

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)
    try:
        tokens = list(pool.map(protect, range(32)))
    finally:
        pool.shutdown(wait=True)
    assert len(set(tokens)) == 32


@pytest.mark.parametrize("service", ("redis",), indirect=True)
def test_real_redis_connection_failure_stops_provider(integrated, service):
    from services.pii_protection.gateway import RedisStore
    gateway, request, captured, _ = integrated
    service.store = RedisStore("redis://127.0.0.1:1/15")
    result = gateway.run_llm_task(replace(request, prompt="Email: unavailable@example.invalid"))
    assert result.status == "policy_blocked" and captured == []


def test_mail_json_reply_and_authorized_recipient(integrated, scope):
    gateway, request, captured, behavior = integrated
    behavior["reply"] = lambda prompt: json.dumps({"reply": "Hello " + TOKEN.findall(prompt)[0], "count": 1})
    schema = {"type": "object", "required": ["reply"], "properties": {"reply": {"type": "string"}}}
    result = gateway.run_llm_task(replace(request, prompt="Email: customer@example.invalid", response_schema=schema))
    assert result.status == "completed"
    assert result.parsed_data["reply"] == "Hello customer@example.invalid"
    assert json.loads(result.content)["count"] == 1
    assert b"customer@example.invalid" not in captured[0]


def test_booking_tool_receives_real_values_only_at_trusted_boundary(integrated, scope):
    gateway, request, captured, behavior = integrated

    def reply(prompt):
        phone = next(token for token in TOKEN.findall(prompt) if "PII_PHONE:" in token)
        return json.dumps({"action": "tool_call", "tool": "crm.book", "arguments": {"phone": phone}, "remaining_actions": []})

    behavior["reply"] = reply
    result = gateway.run_llm_task(replace(request, task_key="operator_tool_plan", prompt="Phone: +7 999 000 01 23"))
    assert result.status == "completed"
    decision = json.loads(result.content)
    assert "<<PII_" in decision["arguments"]["phone"]
    calls = []
    with pytest.raises(PIIProtectionError):
        result.pii_context.restore_tool("crm.book", decision["arguments"], scope=scope,
                                        allowed_fields=("phone",), authorized=True, operation="write")
    trusted = result.pii_context.restore_tool("crm.book", decision["arguments"], scope=scope,
                                              allowed_fields=("phone",), authorized=True, operation="write", approved=True)
    calls.append(trusted)  # fake CRM only; no external booking implementation
    assert calls == [{"phone": "+7 999 000 01 23"}]
    assert b"+7 999 000 01 23" not in captured[0]


def test_operator_boundary_restores_only_catalog_allowed_fields(service, scope):
    from services.operator_tool_loop import run_operator_tool_loop

    exchange = service.protect("Phone: +7 999 000 01 23", scope)
    token = next(iter(exchange.issued))
    prepared = []
    tool = {"name": "crm.prepare_booking", "risk_class": "write", "approval_required": True,
            "pii_restore_fields": ["phone"],
            "input_schema": {"type": "object", "properties": {"phone": {"type": "string", "maxLength": 30}}},
            "prepare_approval": lambda args: prepared.append(args) or {"status": "approval_required", "chat_response": "Preview"}}
    decision = {"action": "tool_call", "tool": tool["name"], "arguments": {"phone": token}, "_pii_exchange": exchange}
    result = run_operator_tool_loop(business_id=scope.business_id, user_id=scope.user_id,
                                    conversation_id=scope.session_id, message="Запиши клиента", tools=[tool],
                                    planner=lambda _: dict(decision), max_steps=1)
    assert result["status"] == "approval_required"
    assert prepared == [{"phone": "+7 999 000 01 23"}]
    assert result["external_writes_performed"] is False
    tool["pii_restore_fields"] = []
    prepared.clear()
    run_operator_tool_loop(business_id=scope.business_id, user_id=scope.user_id,
                           conversation_id=scope.session_id, message="Запиши клиента", tools=[tool],
                           planner=lambda _: dict(decision), max_steps=1)
    assert prepared == []


def test_parallel_tenants_and_sessions_do_not_mix(integrated):
    gateway, request, captured, _ = integrated

    def call(index):
        email = f"synthetic{index}@example.invalid"
        result = gateway.run_llm_task(replace(request, business_id=f"business-{index % 2}",
                                             pii_session_id=f"session-{index}", prompt="Email: " + email))
        assert result.status == "completed"
        assert result.content == "Received " + email

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)
    try:
        list(pool.map(call, range(16)))
    finally:
        pool.shutdown(wait=True)
    assert len(captured) == 16
    assert all(b"@example.invalid" not in raw for raw in captured)


def test_gateway_failure_has_no_provider_fallback_or_raw_logging(integrated, service, monkeypatch, capsys):
    gateway, request, captured, _ = integrated

    def broken(_):
        raise TimeoutError("Sensitive synthetic@example.invalid")

    monkeypatch.setattr(service.engine, "scan", broken)
    result = gateway.run_llm_task(replace(request, prompt="Email: synthetic@example.invalid"))
    assert result.status == "policy_blocked" and result.fallback_reason == "PII_PROTECTION_FAILED"
    assert captured == []
    assert "synthetic@example.invalid" not in str(capsys.readouterr())
    assert "synthetic@example.invalid" not in repr(result)


def test_missing_mapping_or_foreign_output_blocks_restoration(integrated, service):
    gateway, request, captured, behavior = integrated

    def lose_mapping(prompt):
        service.store.values.clear()
        return " ".join(TOKEN.findall(prompt))

    behavior["reply"] = lose_mapping
    result = gateway.run_llm_task(replace(request, prompt="Email: expired@example.invalid"))
    assert result.fallback_reason == "PII_MAPPING_EXPIRED"
    assert result.content == "" and len(captured) == 1
    behavior["reply"] = lambda _: "<<PII_EMAIL:" + "0" * 32 + ">>"
    result = gateway.run_llm_task(replace(request, prompt="Email: current@example.invalid"))
    assert result.fallback_reason == "PII_UNTRUSTED_PLACEHOLDER" and result.content == ""


def test_diagnostic_invalid_config_secret_and_placeholder_never_send(integrated, monkeypatch):
    gateway, request, captured, _ = integrated
    monkeypatch.setenv("PII_PROTECTION_MODE", "diagnostic")
    result = gateway.run_llm_task(replace(request, prompt="Phone: +90 555 000 01 23"))
    assert result.fallback_reason == "PII_DIAGNOSTIC_NO_PROVIDER" and captured == []
    monkeypatch.setenv("PII_PROTECTION_MODE", "invalid-mode")
    assert gateway.run_llm_task(request).status == "policy_blocked"
    monkeypatch.setenv("PII_PROTECTION_MODE", "enforce")
    assert gateway.run_llm_task(replace(request, prompt="password: synthetic-secret")).status == "policy_blocked"
    assert gateway.run_llm_task(replace(request, prompt="<<PII_EMAIL:forged>>")).status == "policy_blocked"
    assert gateway.run_llm_task(replace(request, user_id="")).status == "policy_blocked"
    assert captured == []


def test_unapproved_tool_calls_cannot_hide_in_generic_json(integrated):
    gateway, request, captured, behavior = integrated
    behavior["reply"] = lambda prompt: json.dumps({"function_call": {"name": "mail.send", "arguments": {"to": TOKEN.findall(prompt)[0]}}})
    result = gateway.run_llm_task(replace(request, prompt="Email: victim@example.invalid"))
    assert result.status == "policy_blocked" and result.fallback_reason == "PII_TOOL_DENIED"
    assert result.content == "" and b"victim@example.invalid" not in captured[0]


def test_format_retry_reprotects_context_and_preserves_tokens(integrated):
    gateway, request, captured, behavior = integrated
    responses = []

    def reply(prompt):
        token = next(token for token in TOKEN.findall(prompt) if "PII_EMAIL:" in token)
        responses.append(token)
        return "{" if len(responses) == 1 else json.dumps({"email": token})

    behavior["reply"] = reply
    schema = {"type": "object", "required": ["email"], "properties": {"email": {"type": "string"}}}
    result = gateway.run_llm_task(replace(request, prompt="Email: retry@example.invalid", response_schema=schema))
    assert result.status == "completed"
    assert result.parsed_data["email"] == "retry@example.invalid"
    assert len(captured) == 2 and responses[0] == responses[1]
    assert all(b"retry@example.invalid" not in raw for raw in captured)


def test_duplicate_names_do_not_merge_record_identifiers(service, scope):
    text = "customer_id: SYNTH-A; name: Mira Exampleton; customer_id: SYNTH-B; name: Mira Exampleton"
    result = service.protect(text, scope)
    ids = [token for token in result.issued if "PII_IDENTIFIER:" in token]
    assert len(ids) == 2
    assert {service.resolve(scope, token) for token in ids} == {"SYNTH-A", "SYNTH-B"}
    assert result.restore_text(result.text) == text


def test_secrets_with_spaces_and_generic_tokens_are_irreversible(service, scope):
    text = 'password: "synthetic secret with spaces"; token: synthetic-token-only'
    result = service.protect(text, scope)
    assert "synthetic secret with spaces" not in result.text
    assert "synthetic-token-only" not in result.text
    assert "SECRET_REDACTED" in result.text
    assert "synthetic secret" not in repr(service.store.values)


def test_default_flag_off_preserves_behavior_without_engine(monkeypatch):
    from services.pii_protection.gateway import run_with_privacy
    monkeypatch.delenv("PII_PROTECTION_ENABLED", raising=False)
    monkeypatch.setattr("services.pii_protection.gateway.runtime_service", lambda: pytest.fail("No engine should load"))
    value = object()
    assert run_with_privacy(LLMTaskRequest("synthetic_task", "original"), lambda: value) is value


def test_direct_legacy_embeddings_and_media_routes_fail_closed(monkeypatch):
    from services.ai_spend_budget import guarded_post
    from services.gigachat_client import GigaChatClient
    monkeypatch.setenv("PII_PROTECTION_ENABLED", "true")
    for body in ({"messages": [{"role": "user", "content": "raw"}]}, {"input": ["raw"]}):
        with pytest.raises(PIIProtectionError):
            guarded_post(lambda: pytest.fail("Network must not run"), body)
    with pytest.raises(PIIProtectionError):
        object.__new__(GigaChatClient).upload_file_simple(b"synthetic image", "test.png")


def test_transport_rejects_tampered_content_metadata_and_media(service, scope, monkeypatch):
    from services.pii_protection.gateway import assert_protected_transport, outbound
    monkeypatch.setenv("PII_PROTECTION_ENABLED", "true")
    exchange = service.protect("Email: private@example.invalid", scope)
    body = {"model": "synthetic-model", "messages": [{"role": "user", "content": exchange.text}]}
    marker = outbound(exchange)
    marker.__enter__()
    try:
        assert_protected_transport(body)
        for changed in ({**body, "metadata": {"email": "private@example.invalid"}},
                        {**body, "messages": [{"role": "user", "content": "private@example.invalid"}]},
                        {**body, "messages": [{"role": "user", "content": [{"image": "synthetic"}]}]}):
            with pytest.raises(PIIProtectionError):
                assert_protected_transport(changed)
    finally:
        marker.__exit__(None, None, None)


def test_unconfigured_runtime_has_no_plaintext_fallback(monkeypatch, scope):
    from services.pii_protection.gateway import run_with_privacy, runtime_service
    monkeypatch.setenv("PII_PROTECTION_ENABLED", "true")
    monkeypatch.delenv("PII_MAPPING_KEY", raising=False)
    monkeypatch.delenv("PII_REDIS_URL", raising=False)
    runtime_service.cache_clear()
    request = LLMTaskRequest("synthetic_task", "Email: private@example.invalid",
                             business_id=scope.business_id, user_id=scope.user_id)
    result = run_with_privacy(request, lambda: pytest.fail("Unconfigured runtime must not execute"))
    assert result.fallback_reason == "PII_CONFIGURATION_REQUIRED"


def test_store_failure_prevents_any_provider_request(integrated, service, monkeypatch):
    gateway, request, captured, _ = integrated

    def failed_store(*_):
        raise RuntimeError("sensitive private@example.invalid")

    monkeypatch.setattr(service.store, "put", failed_store)
    result = gateway.run_llm_task(replace(request, prompt="Email: private@example.invalid"))
    assert result.fallback_reason == "PII_PROTECTION_FAILED" and captured == []


def test_shadow_diagnostic_releases_capacity(integrated, monkeypatch):
    gateway, request, captured, _ = integrated
    monkeypatch.setenv("PII_PROTECTION_MODE", "diagnostic")
    for _ in range(6):
        assert gateway._SHADOW_SEMAPHORE.acquire(blocking=False)
        result = gateway._run_shadow_request(replace(request, prompt="Email: shadow@example.invalid"), None)
        assert result.fallback_reason == "PII_DIAGNOSTIC_NO_PROVIDER"
    assert captured == []


def test_redis_ttl_and_cross_worker_shared_mapping(real_engine, scope):
    fakeredis = pytest.importorskip("fakeredis")
    from cryptography.fernet import Fernet
    from services.pii_protection.gateway import RedisStore
    store = object.__new__(RedisStore)
    store.client = fakeredis.FakeRedis()
    key = Fernet.generate_key()
    writer = ProtectionService(real_engine, store, key)
    reader = ProtectionService(real_engine, store, key)
    first = writer.protect("Email: shared@example.invalid", scope)
    token = next(iter(first.issued))
    assert reader.resolve(scope, token) == "shared@example.invalid"
    assert 0 < store.client.ttl(writer.mapping_key(scope, token)) <= 900
    assert b"shared@example.invalid" not in store.client.get(writer.mapping_key(scope, token))
    store.client.delete(writer.mapping_key(scope, token))
    with pytest.raises(PIIProtectionError):
        reader.resolve(scope, token)
