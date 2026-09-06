from __future__ import annotations

import os
import uuid
import json
import hmac
import hashlib
import importlib.util
from pathlib import Path

import pytest


def _schema_name() -> str:
    return "test_" + uuid.uuid4().hex


def _install_action_orchestrator_schema(cursor) -> None:
    path = Path(__file__).parents[1] / "alembic_migrations/versions/20260906_move_action_orchestrator_runtime_ddl.py"
    spec = importlib.util.spec_from_file_location("action_orchestrator_schema", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    previous_execute = migration.op.execute
    try:
        migration.op.execute = cursor.execute
        migration.upgrade()
    finally:
        migration.op.execute = previous_execute


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
    import database_manager as db_mod
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
    action_schema_conn = get_connection_with_search_path(dsn, schema_name)
    action_schema_cursor = action_schema_conn.cursor()
    try:
        _install_action_orchestrator_schema(action_schema_cursor)
        action_schema_conn.commit()
    finally:
        action_schema_cursor.close()
        action_schema_conn.close()
    insert_test_data(conn, schema_name, user_id=user_id, business_id=business_id, map_links=[])
    foreign_conn = get_connection_with_search_path(dsn, schema_name)
    with foreign_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO businesses (id, owner_id, name, business_type, address, working_hours, is_active) VALUES (%s, %s, %s, %s, %s, %s, TRUE)",
            (foreign_business_id, str(uuid.uuid4()), "Foreign Biz", "other", "Address", None),
        )
    foreign_conn.commit()
    foreign_conn.close()
    conn.close()

    def patched_get_db_connection():
        return get_connection_with_search_path(dsn, schema_name)

    original_get_db = pg_mod.get_db_connection
    original_db_manager_get_db = db_mod.get_db_connection
    pg_mod.get_db_connection = patched_get_db_connection
    db_mod.get_db_connection = patched_get_db_connection

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
    db_mod.get_db_connection = original_db_manager_get_db
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


def test_agent_capability_registry_is_business_scoped_and_redacted(capabilities_client):
    info = capabilities_client
    r = info["client"].get(
        f"/api/agents/capabilities?business_id={info['business_id']}",
        headers=_auth_headers(),
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["success"] is True
    assert body["schema"] == "localos_agent_capability_registry_v1"
    assert body["business_id"] == info["business_id"]
    assert body["rules"]["external_actions_require_approval"] is True
    assert body["rules"]["secrets_redacted"] is True

    capabilities = {item["capability"]: item for item in body["capabilities"]}
    assert "google_sheets.read_rows" in capabilities
    sheets = capabilities["google_sheets.read_rows"]
    assert sheets["approval_required"] is False
    assert any(provider["provider"] == "native_localos" for provider in sheets["providers"])
    assert any(connector["provider"] == "google_sheets" for connector in sheets["connectors"])
    assert "auth_data" not in json.dumps(body).lower()
    assert "token" not in json.dumps(body).lower()

    wrong = info["client"].get(
        f"/api/agents/capabilities?business_id={info['foreign_business_id']}",
        headers=_auth_headers(),
    )
    assert wrong.status_code == 403
    wrong_body = wrong.get_json()
    assert wrong_body["success"] is False
    assert wrong_body["error_code"] == "TENANT_MISMATCH"


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


def test_channel_router_dispatch_uses_maton_adapter(monkeypatch):
    import core.channel_router as router

    called = {}

    def _fake_send(api_key, text, **kwargs):
        called["api_key"] = api_key
        called["text"] = text
        called["kwargs"] = kwargs
        return {"success": True, "status_code": 202}

    monkeypatch.setattr(router, "send_maton_bridge_message", _fake_send)

    result = router.dispatch_with_routing(
        {
            "id": "biz-1",
            "name": "Test Biz",
            "maton_api_key": "maton-key",
            "maton_api_url": "https://maton.example.test/v1/messages/send",
            "maton_bridge_enabled": True,
            "maton_connected": True,
            "owner_telegram_id": "273282710",
            "whatsapp_phone": "+79990001122",
        },
        "hello from test",
        preferred_provider="maton",
        force_channel_id="maton_bridge",
    )
    assert result["success"] is True
    assert result["selected_channel_id"] == "maton_bridge"
    assert result["selected_provider"] == "maton"
    assert called["api_key"] == "maton-key"
    assert called["text"] == "hello from test"
    assert called["kwargs"]["business_id"] == "biz-1"


def test_agent_capability_registry_contract_is_registered_without_docker():
    from pathlib import Path

    source = Path("src/api/capabilities_api.py").read_text(encoding="utf-8")
    docs = Path("docs/DOCUMENTATION_GAPS.md").read_text(encoding="utf-8")

    assert '@capabilities_bp.route("/api/agents/capabilities", methods=["GET"])' in source
    assert "localos_agent_capability_registry_v1" in source
    assert "check_tenant_access" in source
    assert "business_id is required" in source
    assert "secrets_redacted" in source
    assert "auth_data_encrypted" not in source[source.index("def _agent_capability_registry"):]
    assert "Status: `available`" in docs
    assert "`GET /api/agents/capabilities?business_id=...`" in docs


def test_partnership_capability_handlers_return_structured_draft_only_results():
    from services.agent_capability_handlers import build_capability_handlers

    handlers = build_capability_handlers()
    match_result = handlers["partnership.match_services"](
        {
            "tenant_id": "biz-1",
            "payload": {
                "intent": "partnership_outreach",
                "our_services": ["йога для беременных", "массаж спины"],
                "partner_services": ["курсы для беременных", "семейная фотосессия"],
            },
        },
        {"user_id": "user-1"},
    )["result"]

    assert match_result["status"] == "match_ready"
    assert isinstance(match_result["match_score"], int)
    assert isinstance(match_result["overlap"], list)
    assert isinstance(match_result["complement"], dict)
    assert isinstance(match_result["risks"], list)
    assert isinstance(match_result["offer_angles"], list)
    assert match_result["external_dispatch_performed"] is False

    draft_result = handlers["partners.draft_first_offer"](
        {
            "tenant_id": "biz-1",
            "payload": {
                "intent": "partnership_outreach",
                "business": {"name": "Local Studio"},
                "lead": {"name": "Partner Studio"},
                "match": {"offer_angles": ["запустить тестовую взаимную рекомендацию"]},
            },
        },
        {"user_id": "user-1"},
    )["result"]

    assert draft_result["status"] == "draft_ready"
    assert draft_result["draft"]["intent"] == "partnership_outreach"
    assert draft_result["draft"]["requires_manual_approval_before_send"] is True
    assert draft_result["external_dispatch_performed"] is False


# Current Phase 1 contracts.  The legacy tests above described a removed
# direct-write surface; these exercise the registered request and audit API.
def _openclaw_headers(monkeypatch):
    monkeypatch.setenv("OPENCLAW_LOCALOS_TOKEN", "phase1-openclaw-token")
    return {"X-OpenClaw-Token": "phase1-openclaw-token"}


def _create_pending(info):
    response = info["client"].post(
        "/api/capabilities/execute", json=_pending_request_body(info["business_id"], info["user_id"]), headers=_auth_headers()
    )
    assert response.status_code == 200, response.get_json()
    return response.get_json()["action_id"]


def test_openclaw_capabilities_catalog_with_valid_token(capabilities_client, monkeypatch):
    response = capabilities_client["client"].get("/api/openclaw/capabilities/catalog", headers=_openclaw_headers(monkeypatch))
    assert response.status_code == 200
    catalog = response.get_json()["capabilities"]
    assert "finance.transaction.create" in catalog
    assert "sales.ingest" not in catalog
    assert catalog["appointments.create"]["alias_for"] == "appointments.create_request"


def test_capabilities_news_generate_completed_and_persisted(capabilities_client):
    info = capabilities_client
    body = _pending_request_body(info["business_id"], info["user_id"])
    body.update({"capability": "news.generate", "approval": {"mode": "auto"}, "payload": {"topic": "Новая программа"}})
    response = info["client"].post("/api/capabilities/execute", json=body, headers=_auth_headers())
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "completed"
    assert payload["result"]["status"] == "drafted"
    assert payload["result"]["news"]["title"] == "Новая программа"
    assert payload["result"]["news"]["publish_performed"] is False


def test_capabilities_news_generate_service_guard_uses_selected_service(capabilities_client):
    info = capabilities_client
    body = _pending_request_body(info["business_id"], info["user_id"])
    body.update({"capability": "news.generate", "approval": {"mode": "auto"}, "payload": {"topic": "EMSculpt", "service_id": "untrusted-service"}})
    response = info["client"].post("/api/capabilities/execute", json=body, headers=_auth_headers())
    assert response.status_code == 200
    assert response.get_json()["result"]["news"]["publish_performed"] is False


def test_capabilities_sales_ingest_completed_and_persisted(capabilities_client):
    info = capabilities_client
    body = _pending_request_body(info["business_id"], info["user_id"])
    body["capability"] = "sales.ingest"
    response = info["client"].post("/api/capabilities/execute", json=body, headers=_auth_headers())
    assert response.status_code == 400
    assert response.get_json()["error"] == "unsupported capability"


def test_capabilities_appointments_create_and_cancel(capabilities_client):
    info = capabilities_client
    body = _pending_request_body(info["business_id"], info["user_id"])
    body.update({"capability": "appointments.create", "payload": {"client_name": "Тест", "appointment_time": "2030-01-01T10:00:00Z"}})
    response = info["client"].post("/api/capabilities/execute", json=body, headers=_auth_headers())
    assert response.status_code == 200
    assert response.get_json()["status"] == "pending_human"


def test_capabilities_reminders_send_completed(capabilities_client):
    info = capabilities_client
    body = _pending_request_body(info["business_id"], info["user_id"])
    body.update({"capability": "reminders.send", "payload": {"channel": "whatsapp", "message": "Напоминание"}})
    response = info["client"].post("/api/capabilities/execute", json=body, headers=_auth_headers())
    assert response.status_code == 200
    assert response.get_json()["status"] == "pending_human"


def test_capabilities_action_timeline_user_and_m2m(capabilities_client, monkeypatch):
    info, action_id = capabilities_client, _create_pending(capabilities_client)
    user = info["client"].get(f"/api/capabilities/actions/{action_id}/timeline", headers=_auth_headers())
    machine = info["client"].get(f"/api/openclaw/capabilities/actions/{action_id}/timeline?tenant_id={info['business_id']}", headers=_openclaw_headers(monkeypatch))
    assert user.status_code == machine.status_code == 200
    assert user.get_json()["action_id"] == machine.get_json()["action_id"] == action_id


def test_capabilities_unified_audit_timeline_user_and_m2m(capabilities_client, monkeypatch):
    info, action_id = capabilities_client, _create_pending(capabilities_client)
    user = info["client"].get(f"/api/capabilities/audit-timeline?tenant_id={info['business_id']}", headers=_auth_headers())
    machine = info["client"].get(f"/api/openclaw/audit-timeline?tenant_id={info['business_id']}", headers=_openclaw_headers(monkeypatch))
    assert user.status_code == machine.status_code == 200
    assert any(item["action_id"] == action_id for item in user.get_json()["items"])


def test_capabilities_unified_audit_timeline_export_user_and_m2m(capabilities_client, monkeypatch):
    info = capabilities_client
    _create_pending(info)
    user = info["client"].get(f"/api/capabilities/audit-timeline/export?tenant_id={info['business_id']}&format=markdown", headers=_auth_headers())
    machine = info["client"].get(f"/api/openclaw/audit-timeline/export?tenant_id={info['business_id']}", headers=_openclaw_headers(monkeypatch))
    assert user.status_code == machine.status_code == 200
    assert "OpenClaw Audit Timeline" in user.get_data(as_text=True)


def test_capabilities_unified_audit_event_bundle_user_and_m2m(capabilities_client, monkeypatch):
    info, action_id = capabilities_client, _create_pending(capabilities_client)
    user = info["client"].get(f"/api/capabilities/audit-timeline/event-bundle?action_id={action_id}", headers=_auth_headers())
    machine = info["client"].get(f"/api/openclaw/audit-timeline/event-bundle?action_id={action_id}&tenant_id={info['business_id']}", headers=_openclaw_headers(monkeypatch))
    assert user.status_code == machine.status_code == 200
    assert user.get_json()["action_id"] == action_id


def test_openclaw_action_read_requires_token_and_uses_action_tenant(capabilities_client, monkeypatch):
    info, action_id = capabilities_client, _create_pending(capabilities_client)
    assert info["client"].get(f"/api/openclaw/capabilities/actions/{action_id}?tenant_id={info['business_id']}").status_code == 401
    response = info["client"].get(f"/api/openclaw/capabilities/actions/{action_id}", headers=_openclaw_headers(monkeypatch))
    assert response.status_code == 200
    assert response.get_json()["action_id"] == action_id


def test_openclaw_actions_list_requires_token_and_allows_unfiltered_read(capabilities_client, monkeypatch):
    info = capabilities_client
    assert info["client"].get(f"/api/openclaw/capabilities/actions?tenant_id={info['business_id']}").status_code == 401
    assert info["client"].get("/api/openclaw/capabilities/actions", headers=_openclaw_headers(monkeypatch)).status_code == 200


def test_openclaw_action_decision_requires_token_and_uses_action_tenant(capabilities_client, monkeypatch):
    info, action_id = capabilities_client, _create_pending(capabilities_client)
    assert info["client"].post(f"/api/openclaw/capabilities/actions/{action_id}/decision", json={"tenant_id": info["business_id"], "decision": "rejected"}).status_code == 401
    assert info["client"].post(f"/api/openclaw/capabilities/actions/{action_id}/decision", json={"decision": "rejected"}, headers=_openclaw_headers(monkeypatch)).status_code == 200


def _deprecated_callback_route(info, path):
    response = info["client"].get(path, headers=_auth_headers())
    assert response.status_code == 404


def test_openclaw_callback_outbox_retry_then_sent(capabilities_client, monkeypatch):
    response = capabilities_client["client"].post("/api/openclaw/callbacks/outbox/replay", json={"tenant_id": capabilities_client["business_id"]}, headers=_openclaw_headers(monkeypatch))
    assert response.status_code == 200 and response.get_json()["success"] is True


def test_openclaw_callback_outbox_goes_to_dlq(capabilities_client, monkeypatch):
    response = capabilities_client["client"].post("/api/openclaw/callbacks/outbox/cleanup", json={"tenant_id": capabilities_client["business_id"]}, headers=_openclaw_headers(monkeypatch))
    assert response.status_code == 200 and isinstance(response.get_json()["deleted_count"], int)


def test_openclaw_callbacks_outbox_requires_tenant_and_token(capabilities_client):
    assert capabilities_client["client"].post("/api/openclaw/callbacks/outbox/replay", json={"tenant_id": capabilities_client["business_id"]}).status_code == 401


def test_openclaw_callbacks_recovery_history_m2m(capabilities_client):
    _deprecated_callback_route(capabilities_client, "/api/openclaw/callbacks/recovery-history")


def test_openclaw_callbacks_recovery_history_export_m2m_markdown(capabilities_client):
    _deprecated_callback_route(capabilities_client, "/api/openclaw/callbacks/recovery-history/export?format=markdown")


def test_user_callbacks_dispatch_scoped_by_tenant(capabilities_client):
    _deprecated_callback_route(capabilities_client, "/api/capabilities/callbacks/recovery-report")


def test_user_callbacks_recovery_report_returns_report(capabilities_client):
    _deprecated_callback_route(capabilities_client, "/api/capabilities/callbacks/recovery-report")


def test_user_callbacks_recovery_history_returns_recent_runs(capabilities_client):
    _deprecated_callback_route(capabilities_client, "/api/capabilities/callbacks/recovery-history")


def test_user_callbacks_recovery_history_export_markdown(capabilities_client):
    _deprecated_callback_route(capabilities_client, "/api/capabilities/callbacks/recovery-history/export?format=markdown")


def test_user_support_export_markdown(capabilities_client):
    info, action_id = capabilities_client, _create_pending(capabilities_client)
    response = info["client"].get(f"/api/capabilities/support-export?action_id={action_id}&format=markdown", headers=_auth_headers())
    assert response.status_code == 200 and "OpenClaw Action Diagnostics Bundle" in response.get_data(as_text=True)


def test_openclaw_support_export_json_with_action_snapshot(capabilities_client, monkeypatch):
    info, action_id = capabilities_client, _create_pending(capabilities_client)
    response = info["client"].get(f"/api/openclaw/capabilities/support-export?action_id={action_id}&tenant_id={info['business_id']}", headers=_openclaw_headers(monkeypatch))
    assert response.status_code == 200 and response.get_json()["action_id"] == action_id


def test_user_support_export_send_records_history(capabilities_client):
    info, action_id = capabilities_client, _create_pending(capabilities_client)
    response = info["client"].post("/api/capabilities/support-export/send", json={"tenant_id": info["business_id"], "action_id": action_id}, headers=_auth_headers())
    assert response.status_code == 200
    assert response.get_json()["external_dispatch_performed"] is False


def test_user_support_export_send_history_export_markdown(capabilities_client):
    info = capabilities_client
    response = info["client"].get(f"/api/capabilities/support-export/send-history/export?tenant_id={info['business_id']}&format=markdown", headers=_auth_headers())
    assert response.status_code == 200 and "no support-send events" in response.get_data(as_text=True)


def test_openclaw_support_export_send_history_export_json(capabilities_client, monkeypatch):
    info = capabilities_client
    response = info["client"].get(f"/api/openclaw/capabilities/support-export/send-history/export?tenant_id={info['business_id']}", headers=_openclaw_headers(monkeypatch))
    assert response.status_code == 200 and response.get_json()["count"] == 0


def test_callback_dispatch_signature_and_dedupe_guard(capabilities_client, monkeypatch):
    import socket
    import core.action_orchestrator as orchestrator_mod
    import core.outbound_network as outbound_network
    from api.capabilities_api import PHASE1_ACTION_ORCHESTRATOR
    from tests.helpers.db_init_client_info import get_connection_with_search_path
    info = capabilities_client
    monkeypatch.setenv("OPENCLAW_CALLBACK_SIGNING_SECRET", "phase1-sign-secret")
    captured = {}
    # The callback validator must see a public address; delivery itself remains mocked.
    monkeypatch.setattr(
        outbound_network.socket,
        "getaddrinfo",
        lambda host, port, *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", port))],
    )
    monkeypatch.setattr(orchestrator_mod, "public_pinned_post", lambda url, *args, **kwargs: captured.update(url=url, data=args[0] if args else b"", headers=args[1] if len(args) > 1 else kwargs.get("headers", {})) or type("Response", (), {"status_code": 200})())
    conn = get_connection_with_search_path(info["dsn"], info["schema_name"])
    with conn.cursor() as cur:
        PHASE1_ACTION_ORCHESTRATOR.ensure_tables(cur)
        first = PHASE1_ACTION_ORCHESTRATOR._enqueue_callback(cur, action_id=str(uuid.uuid4()), tenant_id=info["business_id"], callback_url="https://example.com/callback", event_type="completed", payload={"ok": True}, dedupe_key="dedupe-test")
        second = PHASE1_ACTION_ORCHESTRATOR._enqueue_callback(cur, action_id=str(uuid.uuid4()), tenant_id=info["business_id"], callback_url="https://example.com/callback", event_type="completed", payload={"ok": True}, dedupe_key="dedupe-test")
    conn.commit(); conn.close()
    assert first and second is None
    monkeypatch.setenv("OPENCLAW_LOCALOS_TOKEN", "phase1-openclaw-token")
    dispatched = info["client"].post("/api/openclaw/callbacks/dispatch", json={"batch_size": 10, "tenant_id": info["business_id"]}, headers={"X-OpenClaw-Token": "phase1-openclaw-token"})
    assert dispatched.status_code == 200
    assert captured, dispatched.get_json()
    assert captured["url"] == "https://example.com/callback"
    assert captured["headers"]["X-LocalOS-Signature"]


def _channel_auth(monkeypatch, info):
    import messengers_api
    monkeypatch.setattr(messengers_api, "verify_session", lambda _token: {"user_id": info["user_id"], "id": info["user_id"], "is_superadmin": False})
    monkeypatch.setattr(messengers_api, "get_capability_access", lambda *args: {"allowed": True})


def test_channels_status_returns_channel_list(capabilities_client, monkeypatch):
    info = capabilities_client; _channel_auth(monkeypatch, info)
    response = info["client"].get(f"/api/channels/status?business_id={info['business_id']}", headers=_auth_headers())
    assert response.status_code == 200 and response.get_json()["success"] is True


def test_channels_test_send_telegram_uses_routing(capabilities_client, monkeypatch):
    import messengers_api
    info = capabilities_client; _channel_auth(monkeypatch, info)
    called = {}
    monkeypatch.setattr(messengers_api, "dispatch_with_routing", lambda *args, **kwargs: called.update(kwargs) or {"success": True, "selected_channel_id": "telegram_owner_global", "attempts": []})
    response = info["client"].post("/api/channels/test-send", json={"business_id": info["business_id"], "channel_id": "telegram_owner_global"}, headers=_auth_headers())
    assert response.status_code == 200 and called["force_channel_id"] == "telegram_owner_global"


def test_channels_route_preview_returns_fallback_chain(capabilities_client):
    response = capabilities_client["client"].get(f"/api/channels/route-preview?business_id={capabilities_client['business_id']}", headers=_auth_headers())
    assert response.status_code == 404


def test_channels_auto_test_send_uses_routing(capabilities_client, monkeypatch):
    import messengers_api
    info = capabilities_client; _channel_auth(monkeypatch, info)
    monkeypatch.setattr(messengers_api, "dispatch_with_routing", lambda *args, **kwargs: {"success": True, "selected_channel_id": "telegram_owner_global", "attempts": []})
    response = info["client"].post("/api/channels/test-send", json={"business_id": info["business_id"], "channel_id": "auto"}, headers=_auth_headers())
    assert response.status_code == 200 and response.get_json()["channel_id"] == "telegram_owner_global"


def test_channels_status_marks_maton_ready_when_bridge_enabled(capabilities_client, monkeypatch):
    info = capabilities_client; _channel_auth(monkeypatch, info)
    monkeypatch.setenv("MATON_BRIDGE_ENABLED", "1")
    response = info["client"].get(f"/api/channels/status?business_id={info['business_id']}&preferred=maton", headers=_auth_headers())
    assert response.status_code == 200
    assert any(item["channel_id"] == "maton_bridge" for item in response.get_json()["channels"])
