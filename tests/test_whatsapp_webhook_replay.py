import hashlib
import hmac
import json
import os
import sys
import threading
import uuid

import pytest
from flask import Flask


if "src" not in sys.path:
    sys.path.insert(0, "src")


import ai_agent_webhooks
from services import whatsapp_webhook_admission


class _EventsCursor:
    def __init__(self) -> None:
        self.executed: list[tuple[str, object]] = []

    def execute(self, query, params=()) -> None:
        self.executed.append((query, params))

    def fetchall(self):
        return [
            {
                "id": "event-1",
                "business_id": "business-1",
                "status": "needs_reconciliation",
                "reason_code": "WHATSAPP_SEND_UNCONFIRMED",
                "created_at": "2026-09-18T10:00:00+00:00",
                "updated_at": "2026-09-18T10:01:00+00:00",
                "payload_json": {"message": "private"},
                "source_event_key": "whatsapp:79990001122:wamid.private",
            }
        ]


class _EventsDatabase:
    def __init__(self) -> None:
        self.cursor_instance = _EventsCursor()
        self.conn = self
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def close(self) -> None:
        self.closed = True


class _DatabaseWrapper:
    def __init__(self, connection) -> None:
        self.conn = connection

    def close(self) -> None:
        self.conn.close()


def _signed_payload() -> bytes:
    payload = {
        "entry": [
            {
                "id": "waba-account-1",
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "phone-id-1"},
                            "messages": [
                                {
                                    "from": "79990001122",
                                    "id": "wamid.replay-1",
                                    "text": {"body": "Нужна запись"},
                                }
                            ],
                        }
                    }
                ],
            }
        ]
    }
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _signature(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _client():
    app = Flask(__name__)
    app.register_blueprint(ai_agent_webhooks.ai_webhooks_bp)
    return app.test_client()


def test_identical_signed_whatsapp_delivery_runs_legacy_side_effects_once(monkeypatch) -> None:
    secret = "test-app-secret"
    body = _signed_payload()
    calls: list[str] = []
    monkeypatch.setenv("WHATSAPP_APP_SECRET", secret)
    monkeypatch.setattr(
        ai_agent_webhooks,
        "find_business_by_waba_phone_id",
        lambda phone_id: {
            "id": "business-1",
            "waba_phone_id": phone_id,
            "waba_access_token": "synthetic-token",
            "ai_agent_enabled": True,
        },
    )
    monkeypatch.setattr(
        ai_agent_webhooks,
        "process_message",
        lambda **_kwargs: calls.append("process") or {"success": True, "response": "Ответ"},
    )
    monkeypatch.setattr(
        ai_agent_webhooks,
        "send_whatsapp_message",
        lambda **_kwargs: calls.append("send") or True,
    )
    states: dict[tuple[str, str, str], str] = {}

    def admit(business_id, sender_phone, provider_message_id):
        key = (business_id, sender_phone, provider_message_id)
        if key in states:
            return {"state": "duplicate_completed", "event_id": "event-1"}
        states[key] = "processing"
        return {"state": "admitted", "event_id": "event-1"}

    monkeypatch.setattr(ai_agent_webhooks, "admit_whatsapp_message", admit)
    monkeypatch.setattr(ai_agent_webhooks, "mark_whatsapp_message_completed", lambda *_args: True)

    headers = {"X-Hub-Signature-256": _signature(secret, body)}
    first = _client().post("/api/webhooks/whatsapp", data=body, content_type="application/json", headers=headers)
    second = _client().post("/api/webhooks/whatsapp", data=body, content_type="application/json", headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert calls == ["process", "send"]


def test_signed_message_without_a_provider_id_has_no_side_effects(monkeypatch) -> None:
    secret = "test-app-secret"
    body = _signed_payload()
    payload = json.loads(body)
    payload["entry"][0]["changes"][0]["value"]["messages"][0]["id"] = ""
    malformed = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    calls: list[str] = []
    monkeypatch.setenv("WHATSAPP_APP_SECRET", secret)
    monkeypatch.setattr(ai_agent_webhooks, "find_business_by_waba_phone_id", lambda *_args: calls.append("lookup"))
    monkeypatch.setattr(ai_agent_webhooks, "process_message", lambda **_kwargs: calls.append("process"))

    response = _client().post(
        "/api/webhooks/whatsapp",
        data=malformed,
        content_type="application/json",
        headers={"X-Hub-Signature-256": _signature(secret, malformed)},
    )

    assert response.status_code == 400
    assert calls == []


def test_signed_opaque_provider_id_with_base64_padding_is_admitted(monkeypatch) -> None:
    secret = "test-app-secret"
    payload = json.loads(_signed_payload())
    payload["entry"][0]["changes"][0]["value"]["messages"][0]["id"] = "wamid.opaque_value=="
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    calls: list[str] = []
    monkeypatch.setenv("WHATSAPP_APP_SECRET", secret)
    monkeypatch.setattr(
        ai_agent_webhooks,
        "find_business_by_waba_phone_id",
        lambda phone_id: {
            "id": "business-1",
            "waba_phone_id": phone_id,
            "waba_access_token": "synthetic-token",
            "ai_agent_enabled": True,
        },
    )
    monkeypatch.setattr(
        ai_agent_webhooks,
        "admit_whatsapp_message",
        lambda **_kwargs: {"state": "admitted", "event_id": "event-1"},
    )
    monkeypatch.setattr(
        ai_agent_webhooks,
        "process_message",
        lambda **_kwargs: calls.append("process") or {"success": True, "response": "Ответ"},
    )
    monkeypatch.setattr(ai_agent_webhooks, "send_whatsapp_message", lambda **_kwargs: calls.append("send") or True)
    monkeypatch.setattr(ai_agent_webhooks, "mark_whatsapp_message_completed", lambda *_args: True)

    response = _client().post(
        "/api/webhooks/whatsapp",
        data=body,
        content_type="application/json",
        headers={"X-Hub-Signature-256": _signature(secret, body)},
    )

    assert response.status_code == 200
    assert calls == ["process", "send"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("from", ["79990001122"]),
        ("from", 79990001122),
        ("id", {"message": "wamid.bad"}),
        ("id", 1),
        ("text", {"body": {"unexpected": "object"}}),
    ],
)
def test_signed_non_string_message_identifiers_have_no_side_effects(monkeypatch, field, value) -> None:
    secret = "test-app-secret"
    payload = json.loads(_signed_payload())
    payload["entry"][0]["changes"][0]["value"]["messages"][0][field] = value
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    calls: list[str] = []
    monkeypatch.setenv("WHATSAPP_APP_SECRET", secret)
    monkeypatch.setattr(ai_agent_webhooks, "find_business_by_waba_phone_id", lambda *_args: calls.append("lookup"))
    monkeypatch.setattr(ai_agent_webhooks, "process_message", lambda **_kwargs: calls.append("process"))

    response = _client().post(
        "/api/webhooks/whatsapp",
        data=body,
        content_type="application/json",
        headers={"X-Hub-Signature-256": _signature(secret, body)},
    )

    assert response.status_code == 400
    assert calls == []


def test_processing_duplicate_does_not_starve_later_fresh_message(monkeypatch) -> None:
    secret = "test-app-secret"
    payload = json.loads(_signed_payload())
    messages = payload["entry"][0]["changes"][0]["value"]["messages"]
    messages.append(
        {
            "from": "79990001122",
            "id": "wamid.fresh-2",
            "text": {"body": "Свежий запрос"},
        }
    )
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    calls: list[str] = []
    monkeypatch.setenv("WHATSAPP_APP_SECRET", secret)
    monkeypatch.setattr(
        ai_agent_webhooks,
        "find_business_by_waba_phone_id",
        lambda phone_id: {
            "id": "business-1",
            "waba_phone_id": phone_id,
            "waba_access_token": "synthetic-token",
            "ai_agent_enabled": True,
        },
    )
    monkeypatch.setattr(
        ai_agent_webhooks,
        "admit_whatsapp_message",
        lambda **kwargs: (
            {"state": "duplicate_processing", "event_id": "event-old"}
            if kwargs["provider_message_id"] == "wamid.replay-1"
            else {"state": "admitted", "event_id": "event-fresh"}
        ),
    )
    monkeypatch.setattr(
        ai_agent_webhooks,
        "process_message",
        lambda **kwargs: calls.append(kwargs["message"]) or {"success": True, "response": "Ответ"},
    )
    monkeypatch.setattr(ai_agent_webhooks, "send_whatsapp_message", lambda **_kwargs: calls.append("send") or True)
    monkeypatch.setattr(ai_agent_webhooks, "mark_whatsapp_message_completed", lambda *_args: True)

    response = _client().post(
        "/api/webhooks/whatsapp",
        data=body,
        content_type="application/json",
        headers={"X-Hub-Signature-256": _signature(secret, body)},
    )

    assert response.status_code == 409
    assert calls == ["Свежий запрос", "send"]


def test_processing_failure_requires_reconciliation_without_provider_send(monkeypatch) -> None:
    secret = "test-app-secret"
    body = _signed_payload()
    calls: list[str] = []
    reasons: list[str] = []
    monkeypatch.setenv("WHATSAPP_APP_SECRET", secret)
    monkeypatch.setattr(
        ai_agent_webhooks,
        "find_business_by_waba_phone_id",
        lambda phone_id: {
            "id": "business-1",
            "waba_phone_id": phone_id,
            "waba_access_token": "synthetic-token",
            "ai_agent_enabled": True,
        },
    )
    monkeypatch.setattr(
        ai_agent_webhooks,
        "admit_whatsapp_message",
        lambda **_kwargs: {"state": "admitted", "event_id": "event-1"},
    )
    monkeypatch.setattr(
        ai_agent_webhooks,
        "process_message",
        lambda **_kwargs: calls.append("process") or {"success": False},
    )
    monkeypatch.setattr(
        ai_agent_webhooks,
        "send_whatsapp_message",
        lambda **_kwargs: calls.append("send") or True,
    )
    monkeypatch.setattr(
        ai_agent_webhooks,
        "mark_whatsapp_message_reconciliation",
        lambda _event_id, reason: reasons.append(reason),
    )

    response = _client().post(
        "/api/webhooks/whatsapp",
        data=body,
        content_type="application/json",
        headers={"X-Hub-Signature-256": _signature(secret, body)},
    )

    assert response.status_code == 409
    assert calls == ["process"]
    assert reasons == ["WHATSAPP_PROCESSING_UNCONFIRMED"]


@pytest.mark.parametrize(
    "result",
    [[], "unexpected"],
)
def test_non_dict_processing_result_requires_reconciliation(monkeypatch, result) -> None:
    secret = "test-app-secret"
    body = _signed_payload()
    reasons: list[str] = []
    monkeypatch.setenv("WHATSAPP_APP_SECRET", secret)
    monkeypatch.setattr(
        ai_agent_webhooks,
        "find_business_by_waba_phone_id",
        lambda phone_id: {
            "id": "business-1",
            "waba_phone_id": phone_id,
            "waba_access_token": "synthetic-token",
            "ai_agent_enabled": True,
        },
    )
    monkeypatch.setattr(
        ai_agent_webhooks,
        "admit_whatsapp_message",
        lambda **_kwargs: {"state": "admitted", "event_id": "event-1"},
    )
    monkeypatch.setattr(ai_agent_webhooks, "process_message", lambda **_kwargs: result)
    monkeypatch.setattr(
        ai_agent_webhooks,
        "send_whatsapp_message",
        lambda **_kwargs: (_ for _item in ()).throw(AssertionError("send must not run")),
    )
    monkeypatch.setattr(
        ai_agent_webhooks,
        "mark_whatsapp_message_reconciliation",
        lambda _event_id, reason: reasons.append(reason),
    )

    response = _client().post(
        "/api/webhooks/whatsapp",
        data=body,
        content_type="application/json",
        headers={"X-Hub-Signature-256": _signature(secret, body)},
    )

    assert response.status_code == 409
    assert reasons == ["WHATSAPP_PROCESSING_UNCONFIRMED"]


def test_send_exception_requires_reconciliation(monkeypatch) -> None:
    secret = "test-app-secret"
    body = _signed_payload()
    reasons: list[str] = []
    monkeypatch.setenv("WHATSAPP_APP_SECRET", secret)
    monkeypatch.setattr(
        ai_agent_webhooks,
        "find_business_by_waba_phone_id",
        lambda phone_id: {
            "id": "business-1",
            "waba_phone_id": phone_id,
            "waba_access_token": "synthetic-token",
            "ai_agent_enabled": True,
        },
    )
    monkeypatch.setattr(
        ai_agent_webhooks,
        "admit_whatsapp_message",
        lambda **_kwargs: {"state": "admitted", "event_id": "event-1"},
    )
    monkeypatch.setattr(
        ai_agent_webhooks,
        "process_message",
        lambda **_kwargs: {"success": True, "response": "Ответ"},
    )
    monkeypatch.setattr(
        ai_agent_webhooks,
        "send_whatsapp_message",
        lambda **_kwargs: (_ for _item in ()).throw(RuntimeError("transport uncertain")),
    )
    monkeypatch.setattr(
        ai_agent_webhooks,
        "mark_whatsapp_message_reconciliation",
        lambda _event_id, reason: reasons.append(reason),
    )

    response = _client().post(
        "/api/webhooks/whatsapp",
        data=body,
        content_type="application/json",
        headers={"X-Hub-Signature-256": _signature(secret, body)},
    )

    assert response.status_code == 409
    assert reasons == ["WHATSAPP_SEND_UNCONFIRMED"]


def test_whatsapp_event_ledger_requires_superadmin(monkeypatch) -> None:
    monkeypatch.setattr(ai_agent_webhooks, "require_auth_from_request", lambda: None)
    assert _client().get("/api/webhooks/whatsapp/events").status_code == 401

    monkeypatch.setattr(ai_agent_webhooks, "require_auth_from_request", lambda: {"is_superadmin": False})
    assert _client().get("/api/webhooks/whatsapp/events").status_code == 403


def test_whatsapp_event_ledger_returns_only_redacted_fields(monkeypatch) -> None:
    database = _EventsDatabase()
    monkeypatch.setattr(ai_agent_webhooks, "require_auth_from_request", lambda: {"is_superadmin": True})
    monkeypatch.setattr(ai_agent_webhooks, "DatabaseManager", lambda: database)

    response = _client().get("/api/webhooks/whatsapp/events?status=needs_reconciliation")

    assert response.status_code == 200
    event = response.get_json()["events"][0]
    assert event == {
        "id": "event-1",
        "business_id": "business-1",
        "status": "needs_reconciliation",
        "reason_code": "WHATSAPP_SEND_UNCONFIRMED",
        "created_at": "2026-09-18T10:00:00+00:00",
        "updated_at": "2026-09-18T10:01:00+00:00",
    }
    assert "payload_json" not in event
    assert "source_event_key" not in event
    assert database.closed
    query = database.cursor_instance.executed[0][0]
    assert "source = 'whatsapp'" in query
    assert "LIMIT 100" in query


def _native_admission_database_factory():
    psycopg2 = pytest.importorskip("psycopg2")
    dsn = str(os.getenv("WHATSAPP_ADMISSION_TEST_DSN") or "").strip()
    if not dsn:
        pytest.skip("WHATSAPP_ADMISSION_TEST_DSN is required for native PostgreSQL proof")
    if os.getenv("PGHOSTADDR") or os.getenv("PGSERVICE"):
        pytest.fail("native admission proof rejects inherited libpq host overrides")
    options = psycopg2.extensions.parse_dsn(dsn)
    host = str(options.get("host") or "").strip()
    database_name = str(options.get("dbname") or "").strip()
    port = str(options.get("port") or "").strip()
    if (
        host not in {"127.0.0.1", "::1"}
        or not port.isdigit()
        or "test" not in database_name.casefold()
        or options.get("hostaddr")
        or options.get("service")
    ):
        pytest.fail("native admission proof requires an explicit isolated loopback test DSN")
    schema = f"whatsapp_admission_{uuid.uuid4().hex}"
    control = psycopg2.connect(dsn)
    cursor = control.cursor()
    cursor.execute(f'CREATE SCHEMA "{schema}"')
    cursor.execute(
        f"""
        CREATE TABLE "{schema}".agent_trigger_events (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            source TEXT NOT NULL,
            event_type TEXT NOT NULL,
            status TEXT NOT NULL,
            payload_json JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            reason_code TEXT,
            source_event_key TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cursor.execute(
        f"""
        CREATE UNIQUE INDEX "uq_{schema}_source_key"
        ON "{schema}".agent_trigger_events(business_id, source, source_event_key)
        WHERE source_event_key IS NOT NULL
        """
    )
    control.commit()

    def open_database() -> _DatabaseWrapper:
        connection = psycopg2.connect(dsn)
        cursor = connection.cursor()
        cursor.execute(f'SET search_path TO "{schema}"')
        connection.commit()
        return _DatabaseWrapper(connection)

    def cleanup() -> None:
        cursor = control.cursor()
        cursor.execute(f'DROP TABLE IF EXISTS "{schema}".agent_trigger_events')
        cursor.execute(f'DROP SCHEMA IF EXISTS "{schema}"')
        control.commit()
        control.close()

    return open_database, cleanup


def test_native_admission_rejects_inherited_libpq_override_before_connect(monkeypatch) -> None:
    psycopg2 = pytest.importorskip("psycopg2")
    monkeypatch.setenv("WHATSAPP_ADMISSION_TEST_DSN", "postgresql://owner@127.0.0.1:55432/test_webhook")
    monkeypatch.setenv("PGHOSTADDR", "127.0.0.2")
    monkeypatch.setattr(
        psycopg2,
        "connect",
        lambda *_args, **_kwargs: (_ for _item in ()).throw(AssertionError("connection must not start")),
    )

    with pytest.raises(pytest.fail.Exception):
        _native_admission_database_factory()


def test_native_postgres_admission_is_tenant_scoped_and_concurrent() -> None:
    open_database, cleanup = _native_admission_database_factory()
    try:
        first = open_database()
        second = open_database()
        sender_phone = "79990001122"
        provider_message_id = f"wamid.concurrent-{uuid.uuid4().hex}"
        barrier = threading.Barrier(2)
        results: list[dict[str, str]] = []
        errors: list[BaseException] = []

        def admit(database) -> None:
            try:
                barrier.wait(timeout=5)
                result = whatsapp_webhook_admission.admit_whatsapp_message(
                    "business-native-a",
                    sender_phone,
                    provider_message_id,
                    database,
                )
                results.append(result)
            except BaseException:
                errors.append(sys.exception())

        first_thread = threading.Thread(target=admit, args=(first,))
        second_thread = threading.Thread(target=admit, args=(second,))
        first_thread.start()
        second_thread.start()
        first_thread.join(timeout=10)
        second_thread.join(timeout=10)
        first.close()
        second.close()

        assert not errors
        assert sorted(item["state"] for item in results) == ["admitted", "duplicate_processing"]

        admitted_event_id = next(item["event_id"] for item in results if item["state"] == "admitted")
        inspection = open_database()
        cursor = inspection.conn.cursor()
        cursor.execute(
            """
            SELECT status, reason_code, created_at = updated_at
            FROM agent_trigger_events
            WHERE id = %s
            """,
            (admitted_event_id,),
        )
        assert cursor.fetchone() == ("processing", None, True)
        inspection.close()

        completion = open_database()
        assert whatsapp_webhook_admission.mark_whatsapp_message_completed(admitted_event_id, completion)
        cursor = completion.conn.cursor()
        cursor.execute("SELECT status, reason_code, updated_at FROM agent_trigger_events WHERE id = %s", (admitted_event_id,))
        assert cursor.fetchone()[0] == "completed"
        completion.close()

        tenant_b = open_database()
        tenant_b_result = whatsapp_webhook_admission.admit_whatsapp_message(
            "business-native-b",
            sender_phone,
            provider_message_id,
            tenant_b,
        )
        tenant_b.close()
        assert tenant_b_result["state"] == "admitted"
    finally:
        cleanup()
