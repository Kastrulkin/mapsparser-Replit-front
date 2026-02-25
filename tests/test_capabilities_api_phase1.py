from __future__ import annotations

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
