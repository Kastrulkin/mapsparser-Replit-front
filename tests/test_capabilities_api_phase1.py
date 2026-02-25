from __future__ import annotations

import os
import uuid

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
