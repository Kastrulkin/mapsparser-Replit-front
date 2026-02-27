from __future__ import annotations

import os
import uuid
import json
import hmac
import hashlib

import pytest


def _schema_name() -> str:
    return "test_" + uuid.uuid4().hex


def _auth_headers() -> dict:
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def capabilities_client(postgres_container, run_migrations):
    from tests.helpers.db_init_client_info import (
        create_schema,
        create_client_info_tables,
        get_connection_with_search_path,
        insert_test_data,
    )
    import pg_db_utils as pg_mod
    import psycopg2
    from psycopg2.extras import RealDictCursor
    import main as main_mod

    raw_url = postgres_container.get_connection_url()
    dsn = raw_url.replace("postgresql+psycopg2://", "postgresql://", 1) if "postgresql+psycopg2" in raw_url else raw_url
    schema_name = _schema_name()
    user_id = str(uuid.uuid4())
    business_id = str(uuid.uuid4())
    foreign_business_id = str(uuid.uuid4())

    conn = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    create_schema(conn, schema_name)
    create_client_info_tables(conn, schema_name)
    insert_test_data(conn, schema_name, user_id=user_id, business_id=business_id, map_links=[])
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO businesses (id, owner_id, name, business_type, address, working_hours, is_active) VALUES (%s, %s, %s, %s, %s, %s, TRUE)",
            (foreign_business_id, str(uuid.uuid4()), "Foreign Biz", "other", "Address", None),
        )
    conn.commit()
    conn.close()

    def patched_get_db_connection():
        return get_connection_with_search_path(dsn, schema_name)

    original_get_db = pg_mod.get_db_connection
    pg_mod.get_db_connection = patched_get_db_connection

    original_verify = main_mod.verify_session
    main_mod.verify_session = lambda _token: {"user_id": user_id, "id": user_id, "is_superadmin": False}

    yield {
        "client": main_mod.app.test_client(),
        "dsn": dsn,
        "schema_name": schema_name,
        "user_id": user_id,
        "business_id": business_id,
        "foreign_business_id": foreign_business_id,
    }

    pg_mod.get_db_connection = original_get_db
    main_mod.verify_session = original_verify


def _pending_request_body(business_id: str, actor_id: str, idempotency_key: str | None = None) -> dict:
    return {
        "tenant_id": business_id,
        "actor": {
            "id": actor_id,
            "type": "user",
            "role": "owner",
            "channel": "api",
        },
        "trace_id": str(uuid.uuid4()),
        "idempotency_key": idempotency_key or str(uuid.uuid4()),
        "capability": "services.optimize",
        "approval": {"mode": "required", "ttl_sec": 1200},
        "billing": {"tariff_id": "phase1-test", "reserve_tokens": 1200},
        "payload": {
            "name": "Робототехника",
            "description": "Курс для детей",
            "bulk": True,
            "source": "file",
        },
    }


def test_capabilities_execute_returns_pending_human(capabilities_client):
    info = capabilities_client
    r = info["client"].post(
        "/api/capabilities/execute",
        json=_pending_request_body(info["business_id"], info["user_id"]),
        headers=_auth_headers(),
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["success"] is True
    assert body["status"] == "pending_human"
    assert body.get("action_id")
    assert body.get("approval", {}).get("status") == "pending_human"


def test_capabilities_execute_is_idempotent_for_same_key(capabilities_client):
    info = capabilities_client
    idem = str(uuid.uuid4())
    body = _pending_request_body(info["business_id"], info["user_id"], idempotency_key=idem)
    r1 = info["client"].post("/api/capabilities/execute", json=body, headers=_auth_headers())
    r2 = info["client"].post("/api/capabilities/execute", json=body, headers=_auth_headers())
    assert r1.status_code == 200
    assert r2.status_code == 200
    j1 = r1.get_json()
    j2 = r2.get_json()
    assert j1["action_id"] == j2["action_id"]
    assert j2.get("idempotent_replay") is True


def test_capabilities_decision_rejected_and_status_endpoint(capabilities_client):
    info = capabilities_client
    r1 = info["client"].post(
        "/api/capabilities/execute",
        json=_pending_request_body(info["business_id"], info["user_id"]),
        headers=_auth_headers(),
    )
    assert r1.status_code == 200
    action_id = r1.get_json()["action_id"]

    r2 = info["client"].post(
        f"/api/capabilities/actions/{action_id}/decision",
        json={"decision": "rejected", "reason": "manual reject in test"},
        headers=_auth_headers(),
    )
    assert r2.status_code == 200
    body2 = r2.get_json()
    assert body2["success"] is True
    assert body2["status"] == "rejected"
    assert body2["action_id"] == action_id

    r3 = info["client"].get(f"/api/capabilities/actions/{action_id}", headers=_auth_headers())
    assert r3.status_code == 200
    body3 = r3.get_json()
    assert body3["success"] is True
    assert body3["status"] == "rejected"
    assert body3["capability"] == "services.optimize"
    assert body3["tenant_id"] == info["business_id"]


def test_capabilities_execute_rejects_tenant_mismatch(capabilities_client):
    info = capabilities_client
    body = _pending_request_body(info["foreign_business_id"], info["user_id"])
    r = info["client"].post("/api/capabilities/execute", json=body, headers=_auth_headers())
    assert r.status_code == 400
    resp = r.get_json()
    assert resp["success"] is False
    assert resp["status"] == "failed"
    assert resp["error_code"] in {"TENANT_MISMATCH", "TENANT_NOT_FOUND"}


def test_capabilities_action_auto_expires_by_ttl(capabilities_client):
    info = capabilities_client
    r1 = info["client"].post(
        "/api/capabilities/execute",
        json=_pending_request_body(info["business_id"], info["user_id"]),
        headers=_auth_headers(),
    )
    assert r1.status_code == 200
    action_id = r1.get_json()["action_id"]

    from tests.helpers.db_init_client_info import get_connection_with_search_path

    conn = get_connection_with_search_path(info["dsn"], info["schema_name"])
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE action_approvals SET expires_at = CURRENT_TIMESTAMP - INTERVAL '2 minutes' WHERE action_id = %s",
            (action_id,),
        )
    conn.commit()
    conn.close()

    r2 = info["client"].get(f"/api/capabilities/actions/{action_id}", headers=_auth_headers())
    assert r2.status_code == 200
    body = r2.get_json()
    assert body["success"] is True
    assert body["status"] == "expired"


def test_capabilities_actions_list_returns_items(capabilities_client):
    info = capabilities_client
    r_create = info["client"].post(
        "/api/capabilities/execute",
        json=_pending_request_body(info["business_id"], info["user_id"]),
        headers=_auth_headers(),
    )
    assert r_create.status_code == 200
    created_action_id = r_create.get_json()["action_id"]

    r_list = info["client"].get(
        f"/api/capabilities/actions?tenant_id={info['business_id']}&limit=20&offset=0",
        headers=_auth_headers(),
    )
    assert r_list.status_code == 200
    body = r_list.get_json()
    assert body["success"] is True
    assert body["count"] >= 1
    assert isinstance(body["items"], list)
    assert any(item.get("action_id") == created_action_id for item in body["items"])


def test_capabilities_action_billing_completed_rejected_expired(capabilities_client):
    info = capabilities_client
    import main as main_mod

    original_review_handler = main_mod.PHASE1_ACTION_ORCHESTRATOR.handlers.get("reviews.reply")
    main_mod.PHASE1_ACTION_ORCHESTRATOR.handlers["reviews.reply"] = (
        lambda env, user: {
            "result": {"reply": "ok"},
            "billing": {
                "total_tokens": 300,
                "cost": 0.12,
                "tool_calls": 1,
                "tariff_id": "phase1-test",
            },
        }
    )

    try:
        completed_body = {
            "tenant_id": info["business_id"],
            "actor": {"id": info["user_id"], "type": "user", "role": "owner", "channel": "api"},
            "trace_id": str(uuid.uuid4()),
            "idempotency_key": str(uuid.uuid4()),
            "capability": "reviews.reply",
            "approval": {"mode": "auto", "ttl_sec": 1200},
            "billing": {"tariff_id": "phase1-test", "reserve_tokens": 1000},
            "payload": {"review": "great", "publish": False},
        }
        r_completed = info["client"].post("/api/capabilities/execute", json=completed_body, headers=_auth_headers())
        assert r_completed.status_code == 200, r_completed.get_json()
        completed_action_id = r_completed.get_json()["action_id"]
        assert completed_action_id, r_completed.get_json()

        rs_completed = info["client"].get(f"/api/capabilities/actions/{completed_action_id}", headers=_auth_headers())
        assert rs_completed.status_code == 200, rs_completed.get_json()

        rb_completed = info["client"].get(f"/api/capabilities/actions/{completed_action_id}/billing", headers=_auth_headers())
        assert rb_completed.status_code == 200, rb_completed.get_json()
        b_completed = rb_completed.get_json()
        assert b_completed["success"] is True
        assert b_completed["summary"]["reserved_tokens"] == 1000
        assert b_completed["summary"]["settled_tokens"] == 300
        assert b_completed["summary"]["released_tokens"] == 700
        assert b_completed["summary"]["inflight_reserved_tokens"] == 0
        assert any(e["entry_type"] == "reserve" for e in b_completed["entries"])
        assert any(e["entry_type"] == "settle" for e in b_completed["entries"])
        assert any(e["entry_type"] == "release" for e in b_completed["entries"])

        r_rej_create = info["client"].post(
            "/api/capabilities/execute",
            json=_pending_request_body(info["business_id"], info["user_id"]),
            headers=_auth_headers(),
        )
        assert r_rej_create.status_code == 200
        rej_action_id = r_rej_create.get_json()["action_id"]
        r_rej_decision = info["client"].post(
            f"/api/capabilities/actions/{rej_action_id}/decision",
            json={"decision": "rejected", "reason": "manual reject"},
            headers=_auth_headers(),
        )
        assert r_rej_decision.status_code == 200

        rb_rejected = info["client"].get(f"/api/capabilities/actions/{rej_action_id}/billing", headers=_auth_headers())
        assert rb_rejected.status_code == 200
        b_rejected = rb_rejected.get_json()
        assert b_rejected["success"] is True
        assert b_rejected["status"] == "rejected"
        assert b_rejected["summary"]["reserved_tokens"] == 0
        assert b_rejected["summary"]["settled_tokens"] == 0
        assert b_rejected["summary"]["released_tokens"] == 0

        r_exp_create = info["client"].post(
            "/api/capabilities/execute",
            json=_pending_request_body(info["business_id"], info["user_id"]),
            headers=_auth_headers(),
        )
        assert r_exp_create.status_code == 200
        exp_action_id = r_exp_create.get_json()["action_id"]

        from tests.helpers.db_init_client_info import get_connection_with_search_path

        conn = get_connection_with_search_path(info["dsn"], info["schema_name"])
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE action_approvals SET expires_at = CURRENT_TIMESTAMP - INTERVAL '2 minutes' WHERE action_id = %s",
                (exp_action_id,),
            )
        conn.commit()
        conn.close()

        rb_expired = info["client"].get(f"/api/capabilities/actions/{exp_action_id}/billing", headers=_auth_headers())
        assert rb_expired.status_code == 200
        b_expired = rb_expired.get_json()
        assert b_expired["success"] is True
        assert b_expired["status"] == "expired"
        assert b_expired["summary"]["reserved_tokens"] == 0
        assert b_expired["summary"]["settled_tokens"] == 0
        assert b_expired["summary"]["released_tokens"] == 0
    finally:
        if original_review_handler is not None:
            main_mod.PHASE1_ACTION_ORCHESTRATOR.handlers["reviews.reply"] = original_review_handler


def test_openclaw_execute_requires_token(capabilities_client):
    info = capabilities_client
    body = _pending_request_body(info["business_id"], info["user_id"])
    r = info["client"].post("/api/openclaw/capabilities/execute", json=body)
    assert r.status_code == 401
    resp = r.get_json()
    assert resp["success"] is False


def test_openclaw_execute_pending_human_with_valid_token(capabilities_client):
    info = capabilities_client
    token_name = "OPENCLAW_LOCALOS_TOKEN"
    previous = os.getenv(token_name)
    os.environ[token_name] = "phase1-openclaw-token"
    try:
        body = _pending_request_body(info["business_id"], info["user_id"])
        # Для OpenClaw actor может не содержать id local user — backend проставит owner_id tenant.
        body["actor"] = {"type": "system", "role": "openclaw", "channel": "openclaw"}
        r = info["client"].post(
            "/api/openclaw/capabilities/execute",
            json=body,
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r.status_code == 200, r.get_json()
        resp = r.get_json()
        assert resp["success"] is True
        assert resp["status"] == "pending_human"
        assert resp.get("action_id")
    finally:
        if previous is None:
            os.environ.pop(token_name, None)
        else:
            os.environ[token_name] = previous


def test_openclaw_capabilities_catalog_requires_token(capabilities_client):
    info = capabilities_client
    r = info["client"].get("/api/openclaw/capabilities/catalog")
    assert r.status_code == 401
    body = r.get_json()
    assert body["success"] is False


def test_openclaw_capabilities_catalog_with_valid_token(capabilities_client):
    info = capabilities_client
    token_name = "OPENCLAW_LOCALOS_TOKEN"
    previous = os.getenv(token_name)
    os.environ[token_name] = "phase1-openclaw-token"
    try:
        r = info["client"].get(
            "/api/openclaw/capabilities/catalog",
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r.status_code == 200, r.get_json()
        body = r.get_json()
        assert body["success"] is True
        assert "required_envelope_fields" in body
        assert "capabilities" in body
        capabilities = body["capabilities"]
        assert "reviews.reply" in capabilities
        assert "services.optimize" in capabilities
        assert "news.generate" in capabilities
        assert "sales.ingest" in capabilities
        assert "appointments.create" in capabilities
        assert "appointments.update" in capabilities
        assert "appointments.cancel" in capabilities
        assert "reminders.send" in capabilities
    finally:
        if previous is None:
            os.environ.pop(token_name, None)
        else:
            os.environ[token_name] = previous


def test_openclaw_capabilities_health_requires_token(capabilities_client):
    info = capabilities_client
    r = info["client"].get(
        f"/api/openclaw/capabilities/health?tenant_id={info['business_id']}"
    )
    assert r.status_code == 401
    body = r.get_json()
    assert body["success"] is False


def test_openclaw_capabilities_health_with_valid_token(capabilities_client):
    info = capabilities_client
    token_name = "OPENCLAW_LOCALOS_TOKEN"
    previous = os.getenv(token_name)
    os.environ[token_name] = "phase1-openclaw-token"
    try:
        r = info["client"].get(
            f"/api/openclaw/capabilities/health?tenant_id={info['business_id']}&window_minutes=120",
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r.status_code == 200, r.get_json()
        body = r.get_json()
        assert body["success"] is True
        assert body["tenant_id"] == info["business_id"]
        assert body["status"] in {"ready", "degraded"}
        assert "checks" in body
        assert "metrics" in body
        assert isinstance(body["checks"].get("token_configured"), bool)
        assert isinstance(body["checks"].get("callbacks_enabled"), bool)
        assert isinstance(body["checks"].get("dlq_count"), int)
        assert isinstance(body["checks"].get("retry_backlog"), int)
        assert isinstance(body["checks"].get("stuck_retry"), int)
    finally:
        if previous is None:
            os.environ.pop(token_name, None)
        else:
            os.environ[token_name] = previous


def test_openclaw_callbacks_outbox_replay_requires_token(capabilities_client):
    info = capabilities_client
    r = info["client"].post("/api/openclaw/callbacks/outbox/replay", json={"tenant_id": info["business_id"]})
    assert r.status_code == 401
    body = r.get_json()
    assert body["success"] is False


def test_openclaw_callbacks_outbox_replay_and_cleanup_with_valid_token(capabilities_client):
    info = capabilities_client
    token_name = "OPENCLAW_LOCALOS_TOKEN"
    previous = os.getenv(token_name)
    os.environ[token_name] = "phase1-openclaw-token"
    try:
        r_replay = info["client"].post(
            "/api/openclaw/callbacks/outbox/replay",
            json={"tenant_id": info["business_id"], "include_retry": True, "limit": 10},
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_replay.status_code == 200, r_replay.get_json()
        p_replay = r_replay.get_json()
        assert p_replay["success"] is True
        assert p_replay["tenant_id"] == info["business_id"]
        assert isinstance(p_replay.get("replayed_count"), int)

        r_cleanup = info["client"].post(
            "/api/openclaw/callbacks/outbox/cleanup",
            json={"tenant_id": info["business_id"], "older_than_minutes": 1, "limit": 10},
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_cleanup.status_code == 200, r_cleanup.get_json()
        p_cleanup = r_cleanup.get_json()
        assert p_cleanup["success"] is True
        assert p_cleanup["tenant_id"] == info["business_id"]
        assert isinstance(p_cleanup.get("deleted_count"), int)
    finally:
        if previous is None:
            os.environ.pop(token_name, None)
        else:
            os.environ[token_name] = previous


def test_openclaw_capabilities_health_trend_with_valid_token(capabilities_client):
    info = capabilities_client
    token_name = "OPENCLAW_LOCALOS_TOKEN"
    previous = os.getenv(token_name)
    os.environ[token_name] = "phase1-openclaw-token"
    try:
        r_health = info["client"].get(
            f"/api/openclaw/capabilities/health?tenant_id={info['business_id']}&window_minutes=30",
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_health.status_code == 200, r_health.get_json()

        r_trend = info["client"].get(
            f"/api/openclaw/capabilities/health/trend?tenant_id={info['business_id']}&window_minutes=120&limit=50",
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_trend.status_code == 200, r_trend.get_json()
        trend_body = r_trend.get_json()
        assert trend_body["success"] is True
        assert trend_body["tenant_id"] == info["business_id"]
        assert isinstance(trend_body.get("items"), list)
        assert trend_body.get("count", 0) >= 1
    finally:
        if previous is None:
            os.environ.pop(token_name, None)
        else:
            os.environ[token_name] = previous


def test_openclaw_billing_reconcile_requires_token(capabilities_client):
    info = capabilities_client
    r = info["client"].get(
        f"/api/openclaw/capabilities/billing/reconcile?tenant_id={info['business_id']}"
    )
    assert r.status_code == 401
    body = r.get_json()
    assert body["success"] is False


def test_openclaw_billing_reconcile_with_valid_token(capabilities_client):
    info = capabilities_client
    token_name = "OPENCLAW_LOCALOS_TOKEN"
    previous = os.getenv(token_name)
    os.environ[token_name] = "phase1-openclaw-token"
    try:
        body = _pending_request_body(info["business_id"], info["user_id"])
        body["actor"] = {"type": "system", "role": "openclaw", "channel": "openclaw"}
        r_exec = info["client"].post(
            "/api/openclaw/capabilities/execute",
            json=body,
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_exec.status_code == 200, r_exec.get_json()

        r = info["client"].get(
            f"/api/openclaw/capabilities/billing/reconcile?tenant_id={info['business_id']}&window_minutes=120&limit=50",
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r.status_code == 200, r.get_json()
        payload = r.get_json()
        assert payload["success"] is True
        assert payload["tenant_id"] == info["business_id"]
        assert isinstance(payload.get("items"), list)
        assert isinstance(payload.get("summary"), dict)
        assert "actions_checked" in payload["summary"]
        assert "tokenusage_minus_settled" in payload["summary"]
    finally:
        if previous is None:
            os.environ.pop(token_name, None)
        else:
            os.environ[token_name] = previous


def test_user_capabilities_health_trend_authorized(capabilities_client):
    info = capabilities_client
    r_health = info["client"].get(
        f"/api/capabilities/health?tenant_id={info['business_id']}&window_minutes=30",
        headers=_auth_headers(),
    )
    assert r_health.status_code == 200, r_health.get_json()
    health_body = r_health.get_json()
    assert health_body["success"] is True

    r_trend = info["client"].get(
        f"/api/capabilities/health/trend?tenant_id={info['business_id']}&window_minutes=180&limit=50",
        headers=_auth_headers(),
    )
    assert r_trend.status_code == 200, r_trend.get_json()
    trend_body = r_trend.get_json()
    assert trend_body["success"] is True
    assert trend_body["tenant_id"] == info["business_id"]
    assert isinstance(trend_body.get("items"), list)
    assert trend_body.get("count", 0) >= 1


def test_capabilities_news_generate_completed_and_persisted(capabilities_client, monkeypatch):
    info = capabilities_client
    import main as main_mod
    from tests.helpers.db_init_client_info import get_connection_with_search_path

    monkeypatch.setattr(main_mod, "get_prompt_from_db", lambda key, _uid=None: "Generate news JSON with key news from: {raw_info}")
    monkeypatch.setattr(main_mod, "analyze_text_with_gigachat", lambda *args, **kwargs: '{"news":"Новая программа школы открыта"}')

    body = {
        "tenant_id": info["business_id"],
        "actor": {"id": info["user_id"], "type": "user", "role": "owner", "channel": "api"},
        "trace_id": str(uuid.uuid4()),
        "idempotency_key": str(uuid.uuid4()),
        "capability": "news.generate",
        "approval": {"mode": "auto", "ttl_sec": 1200},
        "billing": {"tariff_id": "phase1-test", "reserve_tokens": 500},
        "payload": {
            "language": "ru",
            "raw_info": "Открыли новый курс робототехники для детей",
            "use_service": False,
            "use_transaction": False,
            "use_seo_keywords": False,
        },
    }
    r = info["client"].post("/api/capabilities/execute", json=body, headers=_auth_headers())
    assert r.status_code == 200, r.get_json()
    resp = r.get_json()
    assert resp["success"] is True
    assert resp["status"] == "completed"
    news_id = str(resp["result"]["news_id"])
    assert news_id

    conn = get_connection_with_search_path(info["dsn"], info["schema_name"])
    with conn.cursor() as cur:
        cur.execute("SELECT generated_text FROM UserNews WHERE id = %s AND user_id = %s", (news_id, info["user_id"]))
        row = cur.fetchone()
    conn.close()
    assert row is not None
    text = row["generated_text"] if hasattr(row, "get") else row[0]
    assert "Новая программа школы" in str(text)


def test_capabilities_news_generate_service_guard_uses_selected_service(capabilities_client, monkeypatch):
    info = capabilities_client
    import main as main_mod
    from tests.helpers.db_init_client_info import get_connection_with_search_path

    service_id = str(uuid.uuid4())
    conn = get_connection_with_search_path(info["dsn"], info["schema_name"])
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND lower(table_name) = 'userservices'
            """
        )
        cols = {str((r[0] if isinstance(r, tuple) else r.get("column_name")) or "").lower() for r in (cur.fetchall() or [])}
        insert_cols = ["id", "business_id", "name", "description"]
        insert_vals = [service_id, info["business_id"], "EMSculpt", "Неинвазивная аппаратная коррекция фигуры"]
        if "is_active" in cols:
            insert_cols.append("is_active")
            insert_vals.append(True)
        cur.execute(
            f"INSERT INTO UserServices ({', '.join(insert_cols)}) VALUES ({', '.join(['%s'] * len(insert_cols))})",
            tuple(insert_vals),
        )
    conn.commit()
    conn.close()

    monkeypatch.setattr(main_mod, "get_prompt_from_db", lambda key, _uid=None: "Generate news JSON with key news from: {service_context}")
    monkeypatch.setattr(
        main_mod,
        "analyze_text_with_gigachat",
        lambda *args, **kwargs: '{"news":"Приглашаем на массаж и косметологию в нашем салоне"}',
    )

    body = {
        "tenant_id": info["business_id"],
        "actor": {"id": info["user_id"], "type": "user", "role": "owner", "channel": "api"},
        "trace_id": str(uuid.uuid4()),
        "idempotency_key": str(uuid.uuid4()),
        "capability": "news.generate",
        "approval": {"mode": "auto", "ttl_sec": 1200},
        "billing": {"tariff_id": "phase1-test", "reserve_tokens": 500},
        "payload": {
            "language": "ru",
            "use_service": True,
            "service_id": service_id,
            "use_transaction": False,
            "use_seo_keywords": False,
            "raw_info": "",
        },
    }
    r = info["client"].post("/api/capabilities/execute", json=body, headers=_auth_headers())
    assert r.status_code == 200, r.get_json()
    resp = r.get_json()
    assert resp["success"] is True
    assert resp["status"] == "completed"
    news_id = str(resp["result"]["news_id"])

    conn2 = get_connection_with_search_path(info["dsn"], info["schema_name"])
    with conn2.cursor() as cur2:
        cur2.execute("SELECT generated_text FROM UserNews WHERE id = %s", (news_id,))
        row = cur2.fetchone()
    conn2.close()
    assert row is not None
    text = row["generated_text"] if hasattr(row, "get") else row[0]
    assert "EMSculpt" in str(text)


def test_capabilities_sales_ingest_completed_and_persisted(capabilities_client):
    info = capabilities_client
    from tests.helpers.db_init_client_info import get_connection_with_search_path

    body = {
        "tenant_id": info["business_id"],
        "actor": {"id": info["user_id"], "type": "user", "role": "owner", "channel": "api"},
        "trace_id": str(uuid.uuid4()),
        "idempotency_key": str(uuid.uuid4()),
        "capability": "sales.ingest",
        "approval": {"mode": "auto", "ttl_sec": 1200},
        "billing": {"tariff_id": "phase1-test", "reserve_tokens": 600},
        "payload": {
            "source": "manual",
            "transactions": [
                {
                    "transaction_date": "2026-02-26",
                    "amount": 3500,
                    "client_type": "new",
                    "services": ["Робототехника"],
                    "notes": "Тестовая запись",
                }
            ],
        },
    }
    r = info["client"].post("/api/capabilities/execute", json=body, headers=_auth_headers())
    assert r.status_code == 200, r.get_json()
    resp = r.get_json()
    assert resp["success"] is True
    assert resp["status"] == "completed"
    assert resp["result"]["inserted_count"] == 1

    tx_id = str(resp["result"]["transactions"][0]["transaction_id"])
    conn = get_connection_with_search_path(info["dsn"], info["schema_name"])
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, business_id, user_id, amount FROM FinancialTransactions WHERE id = %s LIMIT 1",
            (tx_id,),
        )
        row = cur.fetchone()
    conn.close()
    assert row is not None
    row_id = row["id"] if hasattr(row, "get") else row[0]
    row_business = row["business_id"] if hasattr(row, "get") else row[1]
    row_user = row["user_id"] if hasattr(row, "get") else row[2]
    assert str(row_id) == tx_id
    assert str(row_business) == str(info["business_id"])
    assert str(row_user) == str(info["user_id"])


def test_capabilities_appointments_create_and_cancel(capabilities_client):
    info = capabilities_client
    from tests.helpers.db_init_client_info import get_connection_with_search_path

    create_body = {
        "tenant_id": info["business_id"],
        "actor": {"id": info["user_id"], "type": "user", "role": "owner", "channel": "api"},
        "trace_id": str(uuid.uuid4()),
        "idempotency_key": str(uuid.uuid4()),
        "capability": "appointments.create",
        "approval": {"mode": "auto", "ttl_sec": 1200},
        "billing": {"tariff_id": "phase1-test", "reserve_tokens": 300},
        "payload": {
            "client_name": "Тест Клиент",
            "client_phone": "+79990001122",
            "service_name": "Робототехника",
            "appointment_time": "2026-03-01T10:30:00+03:00",
            "notes": "Тестовая запись",
        },
    }
    r_create = info["client"].post("/api/capabilities/execute", json=create_body, headers=_auth_headers())
    assert r_create.status_code == 200, r_create.get_json()
    create_resp = r_create.get_json()
    assert create_resp["success"] is True
    assert create_resp["status"] == "completed"
    appointment_id = str(create_resp["result"]["appointment_id"])
    assert appointment_id

    conn = get_connection_with_search_path(info["dsn"], info["schema_name"])
    with conn.cursor() as cur:
        cur.execute("SELECT id, business_id, status, service_name FROM Bookings WHERE id = %s", (appointment_id,))
        row = cur.fetchone()
    conn.close()
    assert row is not None
    row_status = row["status"] if hasattr(row, "get") else row[2]
    assert str(row_status) == "pending"

    cancel_body = {
        "tenant_id": info["business_id"],
        "actor": {"id": info["user_id"], "type": "user", "role": "owner", "channel": "api"},
        "trace_id": str(uuid.uuid4()),
        "idempotency_key": str(uuid.uuid4()),
        "capability": "appointments.cancel",
        "approval": {"mode": "auto", "ttl_sec": 1200},
        "billing": {"tariff_id": "phase1-test", "reserve_tokens": 100},
        "payload": {
            "appointment_id": appointment_id,
            "reason": "Клиент попросил перенести",
        },
    }
    r_cancel = info["client"].post("/api/capabilities/execute", json=cancel_body, headers=_auth_headers())
    assert r_cancel.status_code == 200, r_cancel.get_json()
    cancel_resp = r_cancel.get_json()
    assert cancel_resp["success"] is True
    assert cancel_resp["status"] == "completed"
    assert cancel_resp["result"]["status"] == "cancelled"

    conn2 = get_connection_with_search_path(info["dsn"], info["schema_name"])
    with conn2.cursor() as cur:
        cur.execute("SELECT status, notes FROM Bookings WHERE id = %s", (appointment_id,))
        row2 = cur.fetchone()
    conn2.close()
    assert row2 is not None
    status2 = row2["status"] if hasattr(row2, "get") else row2[0]
    notes2 = row2["notes"] if hasattr(row2, "get") else row2[1]
    assert str(status2) == "cancelled"
    assert "Причина отмены" in str(notes2 or "")


def test_capabilities_reminders_send_completed(capabilities_client, monkeypatch):
    info = capabilities_client
    import ai_agent_tools as tools_mod

    monkeypatch.setattr(
        tools_mod,
        "send_message_to_client",
        lambda business_id, client_phone, message, channel='whatsapp': {
            "success": True,
            "message": "sent",
            "business_id": business_id,
            "client_phone": client_phone,
            "channel": channel,
        },
    )

    body = {
        "tenant_id": info["business_id"],
        "actor": {"id": info["user_id"], "type": "user", "role": "owner", "channel": "api"},
        "trace_id": str(uuid.uuid4()),
        "idempotency_key": str(uuid.uuid4()),
        "capability": "reminders.send",
        "approval": {"mode": "auto", "ttl_sec": 1200},
        "billing": {"tariff_id": "phase1-test", "reserve_tokens": 120},
        "payload": {
            "client_name": "Тест Клиент",
            "client_phone": "+79990001122",
            "channel": "whatsapp",
            "message": "Напоминаем о вашей записи завтра в 10:30",
        },
    }
    r = info["client"].post("/api/capabilities/execute", json=body, headers=_auth_headers())
    assert r.status_code == 200, r.get_json()
    resp = r.get_json()
    assert resp["success"] is True
    assert resp["status"] == "completed"
    assert resp["result"]["sent"] is True
    assert resp["result"]["channel"] == "whatsapp"


def test_openclaw_action_status_and_billing_with_valid_token(capabilities_client):
    info = capabilities_client
    token_name = "OPENCLAW_LOCALOS_TOKEN"
    previous = os.getenv(token_name)
    os.environ[token_name] = "phase1-openclaw-token"
    try:
        body = _pending_request_body(info["business_id"], info["user_id"])
        body["actor"] = {"type": "system", "role": "openclaw", "channel": "openclaw"}
        r_exec = info["client"].post(
            "/api/openclaw/capabilities/execute",
            json=body,
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_exec.status_code == 200, r_exec.get_json()
        action_id = r_exec.get_json()["action_id"]

        r_status = info["client"].get(
            f"/api/openclaw/capabilities/actions/{action_id}?tenant_id={info['business_id']}",
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_status.status_code == 200, r_status.get_json()
        status_body = r_status.get_json()
        assert status_body["success"] is True
        assert status_body["action_id"] == action_id
        assert status_body["tenant_id"] == info["business_id"]

        r_billing = info["client"].get(
            f"/api/openclaw/capabilities/actions/{action_id}/billing?tenant_id={info['business_id']}",
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_billing.status_code == 200, r_billing.get_json()
        billing_body = r_billing.get_json()
        assert billing_body["success"] is True
        assert billing_body["action_id"] == action_id
        assert billing_body["tenant_id"] == info["business_id"]
        assert "summary" in billing_body
        assert "entries" in billing_body
    finally:
        if previous is None:
            os.environ.pop(token_name, None)
        else:
            os.environ[token_name] = previous


def test_capabilities_action_timeline_user_and_m2m(capabilities_client):
    info = capabilities_client
    token_name = "OPENCLAW_LOCALOS_TOKEN"
    previous = os.getenv(token_name)
    os.environ[token_name] = "phase1-openclaw-token"
    import main as main_mod

    original_reviews_handler = main_mod.PHASE1_ACTION_ORCHESTRATOR.handlers.get("reviews.reply")
    main_mod.PHASE1_ACTION_ORCHESTRATOR.handlers["reviews.reply"] = (
        lambda env, user: {
            "result": {"reply": "ok"},
            "billing": {
                "total_tokens": 111,
                "cost": 0.01,
                "tool_calls": 1,
                "tariff_id": "phase1-test",
            },
        }
    )

    try:
        body = {
            "tenant_id": info["business_id"],
            "actor": {"id": info["user_id"], "type": "user", "role": "owner", "channel": "api"},
            "trace_id": str(uuid.uuid4()),
            "idempotency_key": str(uuid.uuid4()),
            "capability": "reviews.reply",
            "approval": {"mode": "auto", "ttl_sec": 1200},
            "billing": {"tariff_id": "phase1-test", "reserve_tokens": 1000},
            "payload": {"review": "good", "publish": False},
        }
        r_exec = info["client"].post("/api/capabilities/execute", json=body, headers=_auth_headers())
        assert r_exec.status_code == 200, r_exec.get_json()
        action_id = r_exec.get_json()["action_id"]

        r_user_timeline = info["client"].get(
            f"/api/capabilities/actions/{action_id}/timeline?limit=200",
            headers=_auth_headers(),
        )
        assert r_user_timeline.status_code == 200, r_user_timeline.get_json()
        user_timeline = r_user_timeline.get_json()
        assert user_timeline["success"] is True
        assert user_timeline["action_id"] == action_id
        assert user_timeline["count"] >= 3
        assert int(user_timeline.get("total_count", 0)) >= user_timeline["count"]
        assert any(e.get("source") == "action_transition" for e in user_timeline.get("events", []))
        assert any(e.get("source") == "billing_ledger" for e in user_timeline.get("events", []))

        r_user_timeline_source = info["client"].get(
            f"/api/capabilities/actions/{action_id}/timeline?limit=200&source=action_transition",
            headers=_auth_headers(),
        )
        assert r_user_timeline_source.status_code == 200, r_user_timeline_source.get_json()
        user_timeline_source = r_user_timeline_source.get_json()
        assert user_timeline_source["success"] is True
        assert user_timeline_source["count"] >= 1
        assert all(e.get("source") == "action_transition" for e in user_timeline_source.get("events", []))

        r_user_timeline_search = info["client"].get(
            f"/api/capabilities/actions/{action_id}/timeline?limit=200&search=status_changed",
            headers=_auth_headers(),
        )
        assert r_user_timeline_search.status_code == 200, r_user_timeline_search.get_json()
        user_timeline_search = r_user_timeline_search.get_json()
        assert user_timeline_search["success"] is True
        assert user_timeline_search["count"] >= 1

        r_m2m_timeline = info["client"].get(
            f"/api/openclaw/capabilities/actions/{action_id}/timeline?tenant_id={info['business_id']}&limit=200",
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_m2m_timeline.status_code == 200, r_m2m_timeline.get_json()
        m2m_timeline = r_m2m_timeline.get_json()
        assert m2m_timeline["success"] is True
        assert m2m_timeline["action_id"] == action_id
        assert m2m_timeline["count"] >= 3

        r_m2m_timeline_filtered = info["client"].get(
            f"/api/openclaw/capabilities/actions/{action_id}/timeline?tenant_id={info['business_id']}&limit=1&offset=0&source=billing_ledger",
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_m2m_timeline_filtered.status_code == 200, r_m2m_timeline_filtered.get_json()
        m2m_timeline_filtered = r_m2m_timeline_filtered.get_json()
        assert m2m_timeline_filtered["success"] is True
        assert int(m2m_timeline_filtered.get("limit", 0)) == 1
        assert int(m2m_timeline_filtered.get("offset", 0)) == 0
        assert int(m2m_timeline_filtered.get("total_count", 0)) >= m2m_timeline_filtered["count"]
        assert all(e.get("source") == "billing_ledger" for e in m2m_timeline_filtered.get("events", []))

        r_user_support = info["client"].get(
            f"/api/capabilities/actions/{action_id}/support-package?limit=200",
            headers=_auth_headers(),
        )
        assert r_user_support.status_code == 200, r_user_support.get_json()
        user_support = r_user_support.get_json()
        assert user_support["success"] is True
        assert user_support["action_id"] == action_id
        assert user_support["action"]["success"] is True
        assert user_support["billing"]["success"] is True
        assert user_support["timeline"]["success"] is True
        assert user_support["timeline"]["count"] >= 3
        assert "delivery_stats" in user_support
        assert int(user_support["delivery_stats"].get("attempts_total", 0)) >= 0

        r_user_support_filtered = info["client"].get(
            f"/api/capabilities/actions/{action_id}/support-package?limit=200&source=billing_ledger",
            headers=_auth_headers(),
        )
        assert r_user_support_filtered.status_code == 200, r_user_support_filtered.get_json()
        user_support_filtered = r_user_support_filtered.get_json()
        assert user_support_filtered["success"] is True
        assert all(
            e.get("source") == "billing_ledger"
            for e in (user_support_filtered.get("timeline", {}) or {}).get("events", [])
        )
        r_user_support_full = info["client"].get(
            f"/api/capabilities/actions/{action_id}/support-package?limit=2&offset=0&full=true",
            headers=_auth_headers(),
        )
        assert r_user_support_full.status_code == 200, r_user_support_full.get_json()
        user_support_full = r_user_support_full.get_json()
        assert user_support_full["success"] is True
        timeline_full = (user_support_full.get("timeline", {}) or {})
        assert int(timeline_full.get("count", 0)) >= 3
        assert int(timeline_full.get("total_count", 0)) == int(timeline_full.get("count", 0))
        r_user_bundle = info["client"].get(
            f"/api/capabilities/actions/{action_id}/diagnostics-bundle?limit=2&offset=0&full=true&attempts_full=true",
            headers=_auth_headers(),
        )
        assert r_user_bundle.status_code == 200, r_user_bundle.get_json()
        user_bundle = r_user_bundle.get_json()
        assert user_bundle["success"] is True
        assert user_bundle.get("support_package", {}).get("success") is True
        assert user_bundle.get("callback_attempts", {}).get("success") is True
        assert user_bundle.get("filters", {}).get("timeline", {}).get("full") is True
        assert user_bundle.get("filters", {}).get("callback_attempts", {}).get("full") is True
        r_user_bundle_md = info["client"].get(
            f"/api/capabilities/actions/{action_id}/diagnostics-bundle?limit=2&offset=0&full=true&attempts_full=true&format=markdown",
            headers=_auth_headers(),
        )
        assert r_user_bundle_md.status_code == 200, r_user_bundle_md.get_json()
        user_bundle_md = r_user_bundle_md.get_json()
        assert user_bundle_md["success"] is True
        assert isinstance(user_bundle_md.get("markdown_report"), str)
        assert "# OpenClaw Action Diagnostics Bundle" in user_bundle_md.get("markdown_report", "")
        r_user_lifecycle = info["client"].get(
            f"/api/capabilities/actions/{action_id}/lifecycle-summary?full=true",
            headers=_auth_headers(),
        )
        assert r_user_lifecycle.status_code == 200, r_user_lifecycle.get_json()
        user_lifecycle = r_user_lifecycle.get_json()
        assert user_lifecycle["success"] is True
        assert user_lifecycle["action_id"] == action_id
        lifecycle_user = user_lifecycle.get("lifecycle", {})
        assert "pending_human" in lifecycle_user
        assert "completed" in lifecycle_user
        r_user_incident = info["client"].get(
            f"/api/capabilities/actions/{action_id}/incident-report",
            headers=_auth_headers(),
        )
        assert r_user_incident.status_code == 200, r_user_incident.get_json()
        user_incident = r_user_incident.get_json()
        assert user_incident["success"] is True
        assert isinstance(user_incident.get("markdown_report"), str)
        assert "# OpenClaw Incident Report" in user_incident.get("markdown_report", "")
        assert user_incident.get("incident_snapshot", {}).get("success") is True
        r_user_incident_snapshot = info["client"].get(
            f"/api/capabilities/actions/{action_id}/incident-snapshot",
            headers=_auth_headers(),
        )
        assert r_user_incident_snapshot.status_code == 200, r_user_incident_snapshot.get_json()
        user_incident_snapshot = r_user_incident_snapshot.get_json()
        assert user_incident_snapshot["success"] is True
        assert user_incident_snapshot["action_id"] == action_id
        assert user_incident_snapshot.get("overview", {}).get("timeline_events", 0) >= 0
        assert isinstance(user_incident_snapshot.get("recent_timeline"), list)

        r_m2m_support = info["client"].get(
            f"/api/openclaw/capabilities/actions/{action_id}/support-package?tenant_id={info['business_id']}&limit=200",
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_m2m_support.status_code == 200, r_m2m_support.get_json()
        m2m_support = r_m2m_support.get_json()
        assert m2m_support["success"] is True
        assert m2m_support["action_id"] == action_id
        assert m2m_support["tenant_id"] == info["business_id"]
        assert m2m_support["timeline"]["count"] >= 3
        assert "delivery_stats" in m2m_support

        r_m2m_support_filtered = info["client"].get(
            f"/api/openclaw/capabilities/actions/{action_id}/support-package?tenant_id={info['business_id']}&limit=200&source=action_transition",
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_m2m_support_filtered.status_code == 200, r_m2m_support_filtered.get_json()
        m2m_support_filtered = r_m2m_support_filtered.get_json()
        assert m2m_support_filtered["success"] is True
        assert all(
            e.get("source") == "action_transition"
            for e in (m2m_support_filtered.get("timeline", {}) or {}).get("events", [])
        )
        r_m2m_support_full = info["client"].get(
            f"/api/openclaw/capabilities/actions/{action_id}/support-package?tenant_id={info['business_id']}&limit=2&offset=0&full=true",
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_m2m_support_full.status_code == 200, r_m2m_support_full.get_json()
        m2m_support_full = r_m2m_support_full.get_json()
        assert m2m_support_full["success"] is True
        timeline_full_m2m = (m2m_support_full.get("timeline", {}) or {})
        assert int(timeline_full_m2m.get("count", 0)) >= 3
        assert int(timeline_full_m2m.get("total_count", 0)) == int(timeline_full_m2m.get("count", 0))
        r_m2m_bundle = info["client"].get(
            f"/api/openclaw/capabilities/actions/{action_id}/diagnostics-bundle?tenant_id={info['business_id']}&limit=2&offset=0&full=true&attempts_full=true",
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_m2m_bundle.status_code == 200, r_m2m_bundle.get_json()
        m2m_bundle = r_m2m_bundle.get_json()
        assert m2m_bundle["success"] is True
        assert m2m_bundle.get("support_package", {}).get("success") is True
        assert m2m_bundle.get("callback_attempts", {}).get("success") is True
        assert m2m_bundle.get("filters", {}).get("timeline", {}).get("full") is True
        assert m2m_bundle.get("filters", {}).get("callback_attempts", {}).get("full") is True
        r_m2m_bundle_md = info["client"].get(
            f"/api/openclaw/capabilities/actions/{action_id}/diagnostics-bundle?tenant_id={info['business_id']}&limit=2&offset=0&full=true&attempts_full=true&format=markdown",
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_m2m_bundle_md.status_code == 200, r_m2m_bundle_md.get_json()
        m2m_bundle_md = r_m2m_bundle_md.get_json()
        assert m2m_bundle_md["success"] is True
        assert isinstance(m2m_bundle_md.get("markdown_report"), str)
        assert "# OpenClaw Action Diagnostics Bundle" in m2m_bundle_md.get("markdown_report", "")
        r_m2m_lifecycle = info["client"].get(
            f"/api/openclaw/capabilities/actions/{action_id}/lifecycle-summary?tenant_id={info['business_id']}&full=true",
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_m2m_lifecycle.status_code == 200, r_m2m_lifecycle.get_json()
        m2m_lifecycle = r_m2m_lifecycle.get_json()
        assert m2m_lifecycle["success"] is True
        assert m2m_lifecycle["action_id"] == action_id
        assert "pending_human" in (m2m_lifecycle.get("lifecycle") or {})
        r_m2m_incident = info["client"].get(
            f"/api/openclaw/capabilities/actions/{action_id}/incident-report?tenant_id={info['business_id']}",
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_m2m_incident.status_code == 200, r_m2m_incident.get_json()
        m2m_incident = r_m2m_incident.get_json()
        assert m2m_incident["success"] is True
        assert isinstance(m2m_incident.get("markdown_report"), str)
        assert "# OpenClaw Incident Report" in m2m_incident.get("markdown_report", "")
        r_m2m_incident_snapshot = info["client"].get(
            f"/api/openclaw/capabilities/actions/{action_id}/incident-snapshot?tenant_id={info['business_id']}",
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_m2m_incident_snapshot.status_code == 200, r_m2m_incident_snapshot.get_json()
        m2m_incident_snapshot = r_m2m_incident_snapshot.get_json()
        assert m2m_incident_snapshot["success"] is True
        assert m2m_incident_snapshot["tenant_id"] == info["business_id"]
        assert isinstance(m2m_incident_snapshot.get("recent_timeline"), list)

        r_user_attempts = info["client"].get(
            f"/api/capabilities/actions/{action_id}/callback-attempts?limit=50&offset=0",
            headers=_auth_headers(),
        )
        assert r_user_attempts.status_code == 200, r_user_attempts.get_json()
        user_attempts = r_user_attempts.get_json()
        assert user_attempts["success"] is True
        assert user_attempts["action_id"] == action_id
        assert "items" in user_attempts
        assert "summary" in user_attempts
        assert "event_type_breakdown" in user_attempts

        r_m2m_attempts = info["client"].get(
            f"/api/openclaw/capabilities/actions/{action_id}/callback-attempts?tenant_id={info['business_id']}&limit=50&offset=0",
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_m2m_attempts.status_code == 200, r_m2m_attempts.get_json()
        m2m_attempts = r_m2m_attempts.get_json()
        assert m2m_attempts["success"] is True
        assert m2m_attempts["action_id"] == action_id
        assert "event_type_breakdown" in m2m_attempts

        r_m2m_wrong_tenant = info["client"].get(
            f"/api/openclaw/capabilities/actions/{action_id}/timeline?tenant_id={info['foreign_business_id']}&limit=200",
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_m2m_wrong_tenant.status_code in {400, 403, 404}
        wrong = r_m2m_wrong_tenant.get_json()
        assert wrong["success"] is False

        r_m2m_wrong_tenant_support = info["client"].get(
            f"/api/openclaw/capabilities/actions/{action_id}/support-package?tenant_id={info['foreign_business_id']}&limit=200",
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_m2m_wrong_tenant_support.status_code in {400, 403, 404}
        wrong_support = r_m2m_wrong_tenant_support.get_json()
        assert wrong_support["success"] is False
        r_m2m_wrong_tenant_bundle = info["client"].get(
            f"/api/openclaw/capabilities/actions/{action_id}/diagnostics-bundle?tenant_id={info['foreign_business_id']}&limit=200",
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_m2m_wrong_tenant_bundle.status_code in {400, 403, 404}
        wrong_bundle = r_m2m_wrong_tenant_bundle.get_json()
        assert wrong_bundle["success"] is False
        r_m2m_wrong_tenant_lifecycle = info["client"].get(
            f"/api/openclaw/capabilities/actions/{action_id}/lifecycle-summary?tenant_id={info['foreign_business_id']}&full=true",
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_m2m_wrong_tenant_lifecycle.status_code in {400, 403, 404}
        wrong_lifecycle = r_m2m_wrong_tenant_lifecycle.get_json()
        assert wrong_lifecycle["success"] is False
        r_m2m_wrong_tenant_incident = info["client"].get(
            f"/api/openclaw/capabilities/actions/{action_id}/incident-report?tenant_id={info['foreign_business_id']}",
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_m2m_wrong_tenant_incident.status_code in {400, 403, 404}
        wrong_incident = r_m2m_wrong_tenant_incident.get_json()
        assert wrong_incident["success"] is False
        r_m2m_wrong_tenant_incident_snapshot = info["client"].get(
            f"/api/openclaw/capabilities/actions/{action_id}/incident-snapshot?tenant_id={info['foreign_business_id']}",
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_m2m_wrong_tenant_incident_snapshot.status_code in {400, 403, 404}
        wrong_incident_snapshot = r_m2m_wrong_tenant_incident_snapshot.get_json()
        assert wrong_incident_snapshot["success"] is False

        r_m2m_wrong_tenant_attempts = info["client"].get(
            f"/api/openclaw/capabilities/actions/{action_id}/callback-attempts?tenant_id={info['foreign_business_id']}&limit=50&offset=0",
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_m2m_wrong_tenant_attempts.status_code in {400, 403, 404}
        wrong_attempts = r_m2m_wrong_tenant_attempts.get_json()
        assert wrong_attempts["success"] is False
    finally:
        if original_reviews_handler is not None:
            main_mod.PHASE1_ACTION_ORCHESTRATOR.handlers["reviews.reply"] = original_reviews_handler
        else:
            main_mod.PHASE1_ACTION_ORCHESTRATOR.handlers.pop("reviews.reply", None)
        if previous is None:
            os.environ.pop(token_name, None)
        else:
            os.environ[token_name] = previous


def test_openclaw_action_read_requires_tenant_and_token(capabilities_client):
    info = capabilities_client
    token_name = "OPENCLAW_LOCALOS_TOKEN"
    previous = os.getenv(token_name)
    os.environ[token_name] = "phase1-openclaw-token"
    try:
        body = _pending_request_body(info["business_id"], info["user_id"])
        body["actor"] = {"type": "system", "role": "openclaw", "channel": "openclaw"}
        r_exec = info["client"].post(
            "/api/openclaw/capabilities/execute",
            json=body,
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_exec.status_code == 200, r_exec.get_json()
        action_id = r_exec.get_json()["action_id"]

        r_no_token = info["client"].get(
            f"/api/openclaw/capabilities/actions/{action_id}?tenant_id={info['business_id']}"
        )
        assert r_no_token.status_code == 401
        assert r_no_token.get_json()["success"] is False

        r_no_tenant = info["client"].get(
            f"/api/openclaw/capabilities/actions/{action_id}",
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_no_tenant.status_code == 400
        assert r_no_tenant.get_json()["success"] is False

        r_wrong_tenant = info["client"].get(
            f"/api/openclaw/capabilities/actions/{action_id}?tenant_id={info['foreign_business_id']}",
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_wrong_tenant.status_code in {400, 403, 404}
        wrong_body = r_wrong_tenant.get_json()
        assert wrong_body["success"] is False
        if wrong_body.get("error_code") is not None:
            assert wrong_body.get("error_code") in {"TENANT_MISMATCH", "TENANT_NOT_FOUND", "ACTION_NOT_FOUND"}
    finally:
        if previous is None:
            os.environ.pop(token_name, None)
        else:
            os.environ[token_name] = previous


def test_openclaw_actions_list_with_valid_token(capabilities_client):
    info = capabilities_client
    token_name = "OPENCLAW_LOCALOS_TOKEN"
    previous = os.getenv(token_name)
    os.environ[token_name] = "phase1-openclaw-token"
    try:
        body = _pending_request_body(info["business_id"], info["user_id"])
        body["actor"] = {"type": "system", "role": "openclaw", "channel": "openclaw"}
        r_exec = info["client"].post(
            "/api/openclaw/capabilities/execute",
            json=body,
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_exec.status_code == 200, r_exec.get_json()
        action_id = r_exec.get_json()["action_id"]

        r_list = info["client"].get(
            f"/api/openclaw/capabilities/actions?tenant_id={info['business_id']}&limit=20&offset=0",
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_list.status_code == 200, r_list.get_json()
        body_list = r_list.get_json()
        assert body_list["success"] is True
        assert body_list["count"] >= 1
        assert any(item.get("action_id") == action_id for item in body_list.get("items", []))
    finally:
        if previous is None:
            os.environ.pop(token_name, None)
        else:
            os.environ[token_name] = previous


def test_openclaw_actions_list_requires_token_and_tenant(capabilities_client):
    info = capabilities_client
    token_name = "OPENCLAW_LOCALOS_TOKEN"
    previous = os.getenv(token_name)
    os.environ[token_name] = "phase1-openclaw-token"
    try:
        r_no_token = info["client"].get(
            f"/api/openclaw/capabilities/actions?tenant_id={info['business_id']}"
        )
        assert r_no_token.status_code == 401
        assert r_no_token.get_json()["success"] is False

        r_no_tenant = info["client"].get(
            "/api/openclaw/capabilities/actions",
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_no_tenant.status_code == 400
        assert r_no_tenant.get_json()["success"] is False
    finally:
        if previous is None:
            os.environ.pop(token_name, None)
        else:
            os.environ[token_name] = previous


def test_openclaw_action_decision_rejected_with_valid_token(capabilities_client):
    info = capabilities_client
    token_name = "OPENCLAW_LOCALOS_TOKEN"
    previous = os.getenv(token_name)
    os.environ[token_name] = "phase1-openclaw-token"
    try:
        body = _pending_request_body(info["business_id"], info["user_id"])
        body["actor"] = {"type": "system", "role": "openclaw", "channel": "openclaw"}
        r_exec = info["client"].post(
            "/api/openclaw/capabilities/execute",
            json=body,
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_exec.status_code == 200, r_exec.get_json()
        action_id = r_exec.get_json()["action_id"]

        r_decision = info["client"].post(
            f"/api/openclaw/capabilities/actions/{action_id}/decision",
            json={"tenant_id": info["business_id"], "decision": "rejected", "reason": "manual reject by control plane"},
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_decision.status_code == 200, r_decision.get_json()
        body_decision = r_decision.get_json()
        assert body_decision["success"] is True
        assert body_decision["status"] == "rejected"
        assert body_decision["action_id"] == action_id
    finally:
        if previous is None:
            os.environ.pop(token_name, None)
        else:
            os.environ[token_name] = previous


def test_openclaw_action_decision_requires_token_and_tenant(capabilities_client):
    info = capabilities_client
    token_name = "OPENCLAW_LOCALOS_TOKEN"
    previous = os.getenv(token_name)
    os.environ[token_name] = "phase1-openclaw-token"
    try:
        body = _pending_request_body(info["business_id"], info["user_id"])
        body["actor"] = {"type": "system", "role": "openclaw", "channel": "openclaw"}
        r_exec = info["client"].post(
            "/api/openclaw/capabilities/execute",
            json=body,
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_exec.status_code == 200, r_exec.get_json()
        action_id = r_exec.get_json()["action_id"]

        r_no_token = info["client"].post(
            f"/api/openclaw/capabilities/actions/{action_id}/decision",
            json={"tenant_id": info["business_id"], "decision": "rejected"},
        )
        assert r_no_token.status_code == 401
        assert r_no_token.get_json()["success"] is False

        r_no_tenant = info["client"].post(
            f"/api/openclaw/capabilities/actions/{action_id}/decision",
            json={"decision": "rejected"},
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_no_tenant.status_code == 400
        assert r_no_tenant.get_json()["success"] is False
    finally:
        if previous is None:
            os.environ.pop(token_name, None)
        else:
            os.environ[token_name] = previous


def test_openclaw_callback_outbox_retry_then_sent(capabilities_client, monkeypatch):
    info = capabilities_client
    token_name = "OPENCLAW_LOCALOS_TOKEN"
    previous = os.getenv(token_name)
    os.environ[token_name] = "phase1-openclaw-token"
    import core.action_orchestrator as orchestrator_mod
    from tests.helpers.db_init_client_info import get_connection_with_search_path

    class _FailingResponse:
        status_code = 500

    def _always_fail_post(*_args, **_kwargs):
        return _FailingResponse()

    class _OkResponse:
        status_code = 200

    def _always_ok_post(*_args, **_kwargs):
        return _OkResponse()

    try:
        monkeypatch.setattr(orchestrator_mod.requests, "post", _always_fail_post)
        body = _pending_request_body(info["business_id"], info["user_id"])
        body["actor"] = {"type": "system", "role": "openclaw", "channel": "openclaw"}
        body["approval"] = {
            "mode": "required",
            "ttl_sec": 1200,
            "callback_url": "https://openclaw.local/callback",
        }
        r_exec = info["client"].post(
            "/api/openclaw/capabilities/execute",
            json=body,
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_exec.status_code == 200, r_exec.get_json()
        action_id = r_exec.get_json()["action_id"]

        conn = get_connection_with_search_path(info["dsn"], info["schema_name"])
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT status, attempts
                FROM action_callback_outbox
                WHERE action_id = %s AND event_type = 'pending_human'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (action_id,),
            )
            row = cur.fetchone()
        conn.close()
        assert row is not None
        status_val = row["status"] if hasattr(row, "get") else row[0]
        attempts_val = int((row["attempts"] if hasattr(row, "get") else row[1]) or 0)
        assert status_val in {"retry", "dlq"}
        assert attempts_val >= 1

        conn_force = get_connection_with_search_path(info["dsn"], info["schema_name"])
        with conn_force.cursor() as cur_force:
            cur_force.execute(
                """
                UPDATE action_callback_outbox
                SET next_attempt_at = CURRENT_TIMESTAMP - INTERVAL '1 second'
                WHERE action_id = %s AND event_type = 'pending_human' AND status = 'retry'
                """,
                (action_id,),
            )
        conn_force.commit()
        conn_force.close()

        monkeypatch.setattr(orchestrator_mod.requests, "post", _always_ok_post)
        r_dispatch = info["client"].post(
            "/api/openclaw/callbacks/dispatch",
            json={"batch_size": 20},
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_dispatch.status_code == 200

        conn2 = get_connection_with_search_path(info["dsn"], info["schema_name"])
        with conn2.cursor() as cur2:
            cur2.execute(
                """
                SELECT status
                FROM action_callback_outbox
                WHERE action_id = %s AND event_type = 'pending_human'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (action_id,),
            )
            row2 = cur2.fetchone()
            cur2.execute(
                """
                SELECT COUNT(*) AS c,
                       SUM(CASE WHEN success THEN 1 ELSE 0 END) AS ok_count,
                       SUM(CASE WHEN success THEN 0 ELSE 1 END) AS fail_count
                FROM action_callback_attempts
                WHERE action_id = %s
                """,
                (action_id,),
            )
            attempt_row = cur2.fetchone()
        conn2.close()
        assert row2 is not None
        status_after = row2["status"] if hasattr(row2, "get") else row2[0]
        assert status_after == "sent"
        assert attempt_row is not None
        total_attempts = int((attempt_row["c"] if hasattr(attempt_row, "get") else attempt_row[0]) or 0)
        ok_count = int((attempt_row["ok_count"] if hasattr(attempt_row, "get") else attempt_row[1]) or 0)
        fail_count = int((attempt_row["fail_count"] if hasattr(attempt_row, "get") else attempt_row[2]) or 0)
        assert total_attempts >= 2
        assert ok_count >= 1
        assert fail_count >= 1

        r_attempts_failed = info["client"].get(
            f"/api/openclaw/capabilities/actions/{action_id}/callback-attempts?tenant_id={info['business_id']}&limit=50&offset=0&success=false",
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_attempts_failed.status_code == 200, r_attempts_failed.get_json()
        failed_body = r_attempts_failed.get_json()
        assert failed_body["success"] is True
        assert failed_body["total"] >= 1
        assert int((failed_body.get("summary") or {}).get("failed_attempts", 0)) >= 1
        assert all(not bool(item.get("success")) for item in failed_body.get("items", []))

        r_attempts_sent = info["client"].get(
            f"/api/openclaw/capabilities/actions/{action_id}/callback-attempts?tenant_id={info['business_id']}&limit=50&offset=0&success=true",
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_attempts_sent.status_code == 200, r_attempts_sent.get_json()
        sent_body = r_attempts_sent.get_json()
        assert sent_body["success"] is True
        assert sent_body["total"] >= 1
        assert int((sent_body.get("summary") or {}).get("success_attempts", 0)) >= 1
        assert all(bool(item.get("success")) for item in sent_body.get("items", []))
    finally:
        if previous is None:
            os.environ.pop(token_name, None)
        else:
            os.environ[token_name] = previous


def test_openclaw_callback_outbox_goes_to_dlq(capabilities_client, monkeypatch):
    info = capabilities_client
    token_name = "OPENCLAW_LOCALOS_TOKEN"
    previous = os.getenv(token_name)
    os.environ[token_name] = "phase1-openclaw-token"
    import core.action_orchestrator as orchestrator_mod
    from tests.helpers.db_init_client_info import get_connection_with_search_path

    class _FailingResponse:
        status_code = 500

    def _always_fail_post(*_args, **_kwargs):
        return _FailingResponse()

    try:
        monkeypatch.setattr(orchestrator_mod.requests, "post", _always_fail_post)
        body = _pending_request_body(info["business_id"], info["user_id"])
        body["actor"] = {"type": "system", "role": "openclaw", "channel": "openclaw"}
        body["approval"] = {
            "mode": "required",
            "ttl_sec": 1200,
            "callback_url": "https://openclaw.local/callback",
        }
        r_exec = info["client"].post(
            "/api/openclaw/capabilities/execute",
            json=body,
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_exec.status_code == 200, r_exec.get_json()
        action_id = r_exec.get_json()["action_id"]

        conn = get_connection_with_search_path(info["dsn"], info["schema_name"])
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE action_callback_outbox
                SET status = 'retry',
                    attempts = max_attempts - 1,
                    next_attempt_at = CURRENT_TIMESTAMP - INTERVAL '1 second'
                WHERE action_id = %s AND event_type = 'pending_human'
                """,
                (action_id,),
            )
        conn.commit()
        conn.close()

        r_dispatch = info["client"].post(
            "/api/openclaw/callbacks/dispatch",
            json={"batch_size": 20},
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_dispatch.status_code == 200
        dispatch_body = r_dispatch.get_json()
        assert dispatch_body["dlq"] >= 1

        conn2 = get_connection_with_search_path(info["dsn"], info["schema_name"])
        with conn2.cursor() as cur2:
            cur2.execute(
                """
                SELECT status
                FROM action_callback_outbox
                WHERE action_id = %s AND event_type = 'pending_human'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (action_id,),
            )
            row2 = cur2.fetchone()
        conn2.close()
        assert row2 is not None
        status_after = row2["status"] if hasattr(row2, "get") else row2[0]
        assert status_after == "dlq"
    finally:
        if previous is None:
            os.environ.pop(token_name, None)
        else:
            os.environ[token_name] = previous


def test_openclaw_callbacks_outbox_requires_tenant_and_token(capabilities_client):
    info = capabilities_client
    token_name = "OPENCLAW_LOCALOS_TOKEN"
    previous = os.getenv(token_name)
    os.environ[token_name] = "phase1-openclaw-token"
    try:
        r_no_token = info["client"].get(
            f"/api/openclaw/callbacks/outbox?tenant_id={info['business_id']}"
        )
        assert r_no_token.status_code == 401
        assert r_no_token.get_json()["success"] is False

        r_no_tenant = info["client"].get(
            "/api/openclaw/callbacks/outbox",
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_no_tenant.status_code == 400
        assert r_no_tenant.get_json()["success"] is False
    finally:
        if previous is None:
            os.environ.pop(token_name, None)
        else:
            os.environ[token_name] = previous


def test_openclaw_callbacks_dispatch_requires_token(capabilities_client):
    info = capabilities_client
    r_no_token = info["client"].post("/api/openclaw/callbacks/dispatch", json={"batch_size": 10})
    assert r_no_token.status_code == 401
    body = r_no_token.get_json()
    assert body["success"] is False


def test_openclaw_callbacks_metrics_m2m_and_user(capabilities_client):
    info = capabilities_client
    token_name = "OPENCLAW_LOCALOS_TOKEN"
    previous = os.getenv(token_name)
    os.environ[token_name] = "phase1-openclaw-token"
    import main as main_mod
    from tests.helpers.db_init_client_info import get_connection_with_search_path

    try:
        conn = get_connection_with_search_path(info["dsn"], info["schema_name"])
        with conn.cursor() as cur:
            main_mod.PHASE1_ACTION_ORCHESTRATOR.ensure_tables(cur)
            cur.execute(
                """
                INSERT INTO action_callback_outbox (id, action_id, tenant_id, callback_url, event_type, payload_json, status, attempts, max_attempts, next_attempt_at, dedupe_key)
                VALUES
                (%s, %s, %s, 'https://cb.local/sent', 'completed', %s, 'sent', 1, 5, CURRENT_TIMESTAMP, %s),
                (%s, %s, %s, 'https://cb.local/retry', 'pending_human', %s, 'retry', 2, 5, CURRENT_TIMESTAMP - INTERVAL '20 minutes', %s),
                (%s, %s, %s, 'https://cb.local/dlq', 'rejected', %s, 'dlq', 5, 5, CURRENT_TIMESTAMP, %s)
                """,
                (
                    str(uuid.uuid4()),
                    str(uuid.uuid4()),
                    info["business_id"],
                    json.dumps({"ok": True}, ensure_ascii=False),
                    f"{uuid.uuid4().hex}:sent",
                    str(uuid.uuid4()),
                    str(uuid.uuid4()),
                    info["business_id"],
                    json.dumps({"ok": False}, ensure_ascii=False),
                    f"{uuid.uuid4().hex}:retry",
                    str(uuid.uuid4()),
                    str(uuid.uuid4()),
                    info["business_id"],
                    json.dumps({"ok": False}, ensure_ascii=False),
                    f"{uuid.uuid4().hex}:dlq",
                ),
            )
        conn.commit()
        conn.close()

        r_m2m = info["client"].get(
            f"/api/openclaw/callbacks/metrics?tenant_id={info['business_id']}&window_minutes=120",
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_m2m.status_code == 200, r_m2m.get_json()
        body_m2m = r_m2m.get_json()
        assert body_m2m["success"] is True
        assert body_m2m["tenant_id"] == info["business_id"]
        assert body_m2m["metrics"]["sent"] >= 1
        assert body_m2m["metrics"]["retry"] >= 1
        assert body_m2m["metrics"]["dlq"] >= 1
        assert any(a.get("code") == "DLQ_THRESHOLD" for a in body_m2m.get("alerts", []))

        r_user = info["client"].get(
            f"/api/capabilities/callbacks/metrics?tenant_id={info['business_id']}&window_minutes=120",
            headers=_auth_headers(),
        )
        assert r_user.status_code == 200, r_user.get_json()
        body_user = r_user.get_json()
        assert body_user["success"] is True
        assert body_user["tenant_id"] == info["business_id"]
        assert "metrics" in body_user
    finally:
        if previous is None:
            os.environ.pop(token_name, None)
        else:
            os.environ[token_name] = previous


def test_user_callbacks_dispatch_scoped_by_tenant(capabilities_client, monkeypatch):
    info = capabilities_client
    import main as main_mod
    import core.action_orchestrator as orchestrator_mod
    from tests.helpers.db_init_client_info import get_connection_with_search_path

    captured = {"urls": []}

    class _OkResponse:
        status_code = 200

    def _capture_post(url, data=None, timeout=None, headers=None):
        captured["urls"].append(url)
        return _OkResponse()

    monkeypatch.setattr(orchestrator_mod.requests, "post", _capture_post)

    conn = get_connection_with_search_path(info["dsn"], info["schema_name"])
    with conn.cursor() as cur:
        orch = main_mod.PHASE1_ACTION_ORCHESTRATOR
        orch.ensure_tables(cur)
        own_action = str(uuid.uuid4())
        foreign_action = str(uuid.uuid4())
        orch._enqueue_callback(
            cur,
            action_id=own_action,
            tenant_id=info["business_id"],
            callback_url="https://cb.local/own",
            event_type="completed",
            payload={"own": True},
            dedupe_key=f"{own_action}:completed",
        )
        orch._enqueue_callback(
            cur,
            action_id=foreign_action,
            tenant_id=info["foreign_business_id"],
            callback_url="https://cb.local/foreign",
            event_type="completed",
            payload={"foreign": True},
            dedupe_key=f"{foreign_action}:completed",
        )
    conn.commit()
    conn.close()

    r_ok = info["client"].post(
        "/api/capabilities/callbacks/dispatch",
        json={"tenant_id": info["business_id"], "batch_size": 10},
        headers=_auth_headers(),
    )
    assert r_ok.status_code == 200, r_ok.get_json()
    ok_body = r_ok.get_json()
    assert ok_body["success"] is True
    assert ok_body["tenant_id"] == info["business_id"]
    assert ok_body["sent"] >= 1
    assert "https://cb.local/own" in captured["urls"]
    assert "https://cb.local/foreign" not in captured["urls"]

    r_forbidden = info["client"].post(
        "/api/capabilities/callbacks/dispatch",
        json={"tenant_id": info["foreign_business_id"], "batch_size": 10},
        headers=_auth_headers(),
    )
    assert r_forbidden.status_code in {400, 403, 404}
    forbidden_body = r_forbidden.get_json()
    assert forbidden_body["success"] is False
    assert forbidden_body.get("error") in {"forbidden", "tenant_id is required", "tenant_id not found"}


def test_callback_dispatch_signature_and_dedupe_guard(capabilities_client, monkeypatch):
    info = capabilities_client
    token_name = "OPENCLAW_LOCALOS_TOKEN"
    prev_token = os.getenv(token_name)
    os.environ[token_name] = "phase1-openclaw-token"
    secret_name = "OPENCLAW_CALLBACK_SIGNING_SECRET"
    prev_secret = os.getenv(secret_name)
    os.environ[secret_name] = "phase1-sign-secret"

    import main as main_mod
    from tests.helpers.db_init_client_info import get_connection_with_search_path

    captured = {}

    class _OkResponse:
        status_code = 200

    def _capture_post(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        captured["headers"] = kwargs.get("headers") or {}
        return _OkResponse()

    try:
        orch = main_mod.PHASE1_ACTION_ORCHESTRATOR
        conn = get_connection_with_search_path(info["dsn"], info["schema_name"])
        with conn.cursor() as cur:
            orch.ensure_tables(cur)
            action_id = str(uuid.uuid4())
            first_id = orch._enqueue_callback(
                cur,
                action_id=action_id,
                tenant_id=info["business_id"],
                callback_url="https://openclaw.local/callback",
                event_type="completed",
                payload={"hello": "world"},
                dedupe_key=f"{action_id}:completed",
            )
            second_id = orch._enqueue_callback(
                cur,
                action_id=action_id,
                tenant_id=info["business_id"],
                callback_url="https://openclaw.local/callback",
                event_type="completed",
                payload={"hello": "world"},
                dedupe_key=f"{action_id}:completed",
            )
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM action_callback_outbox WHERE dedupe_key = %s",
                (f"{action_id}:completed",),
            )
            count_row = cur.fetchone()
        conn.commit()
        conn.close()

        assert first_id is not None
        assert second_id is None
        assert int((count_row["cnt"] if hasattr(count_row, "get") else count_row[0]) or 0) == 1

        import core.action_orchestrator as orchestrator_mod

        monkeypatch.setattr(orchestrator_mod.requests, "post", _capture_post)
        r_dispatch = info["client"].post(
            "/api/openclaw/callbacks/dispatch",
            json={"batch_size": 10},
            headers={"X-OpenClaw-Token": "phase1-openclaw-token"},
        )
        assert r_dispatch.status_code == 200, r_dispatch.get_json()
        assert captured.get("url") == "https://openclaw.local/callback"

        headers = captured.get("headers") or {}
        event_id = headers.get("X-LocalOS-Event-Id")
        event_ts = headers.get("X-LocalOS-Event-Timestamp")
        dedupe_key = headers.get("X-LocalOS-Dedupe-Key")
        signature = headers.get("X-LocalOS-Signature")
        assert event_id
        assert event_ts
        assert dedupe_key == f"{action_id}:completed"
        assert signature

        raw_data = captured.get("kwargs", {}).get("data", b"")
        if isinstance(raw_data, bytes):
            raw_data = raw_data.decode("utf-8")
        payload = json.loads(raw_data or "{}")
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        expected = hmac.new(
            b"phase1-sign-secret",
            f"{event_id}.{event_ts}.{canonical}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        assert signature == expected
    finally:
        if prev_token is None:
            os.environ.pop(token_name, None)
        else:
            os.environ[token_name] = prev_token
        if prev_secret is None:
            os.environ.pop(secret_name, None)
        else:
            os.environ[secret_name] = prev_secret
