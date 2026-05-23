#!/usr/bin/env python3
import json
import os
import sys
import time
import uuid
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path


repo_root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
for candidate in (os.getenv("APP_SRC_DIR"), "/app/src", str(repo_root / "src")):
    if candidate and candidate not in sys.path:
        sys.path.insert(0, candidate)

from auth_system import hash_password
from database_manager import get_db_connection


BASE_URL = os.getenv("SMOKE_BASE_URL", "http://localhost:8000").rstrip("/")
KEEP_FIXTURE = os.getenv("SMOKE_KEEP_FIXTURE", "").strip().lower() in {"1", "true", "yes"}
PASSWORD = os.getenv("SMOKE_PASSWORD", f"SmokePass-{uuid.uuid4().hex[:12]}-Aa1")


def request_json(method, path, payload=None, token=None, expected_status=None):
    body = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(f"{BASE_URL}{path}", data=body, headers=headers, method=method)
    try:
        response = urllib.request.urlopen(request, timeout=20)
        status = response.status
        raw = response.read().decode("utf-8")
    except urllib.error.HTTPError:
        error = sys.exc_info()[1]
        status = error.code
        raw = error.read().decode("utf-8")
    data = json.loads(raw) if raw.strip() else {}
    if expected_status and status != expected_status:
        raise RuntimeError(f"{method} {path}: expected {expected_status}, got {status}: {data}")
    if status >= 400:
        raise RuntimeError(f"{method} {path}: HTTP {status}: {data}")
    return status, data


def fetch_one(cursor, query, params):
    cursor.execute(query, params)
    row = cursor.fetchone()
    return dict(row) if row else None


def setup_fixture(ids):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        now = datetime.utcnow().isoformat()
        cursor.execute(
            """
            INSERT INTO users (
                id, email, name, phone, password_hash, is_active, is_verified,
                email_verified_at, personal_data_consent_at,
                personal_data_consent_version, credits_balance, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, TRUE, TRUE, NOW(), NOW(), %s, %s, %s, %s)
            """,
            (
                ids["user_id"],
                ids["email"],
                "Smoke Agent Blueprint User",
                "+10000000000",
                hash_password(PASSWORD),
                "localos-personal-data-v1-2026-05-11",
                100000,
                now,
                now,
            ),
        )
        cursor.execute(
            """
            INSERT INTO businesses (
                id, owner_id, name, business_type, address, city, country,
                is_active, subscription_tier, subscription_status, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                ids["business_id"],
                ids["user_id"],
                "Smoke Agent Blueprint Business",
                "beauty_salon",
                "Smoke Street 1",
                "Smoke City",
                "US",
                "trial",
                "active",
            ),
        )
        cursor.execute(
            """
            INSERT INTO prospectingleads (
                id, name, address, city, email, source, status, selected_channel,
                business_id, intent, pipeline_status, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            """,
            (
                ids["lead_id"],
                "Smoke Outreach Lead",
                "Lead Street 2",
                "Smoke City",
                "lead-smoke@example.invalid",
                "smoke_agent_blueprint",
                "channel_selected",
                "email",
                ids["business_id"],
                "client_outreach",
                "in_progress",
            ),
        )
        cursor.execute(
            """
            INSERT INTO outreachmessagedrafts (
                id, lead_id, channel, angle_type, tone, status,
                generated_text, approved_text, created_by, approved_by,
                created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            """,
            (
                ids["draft_id"],
                ids["lead_id"],
                "email",
                "partnership",
                "short",
                "approved",
                "Smoke generated text",
                "Smoke approved text",
                ids["user_id"],
                ids["user_id"],
            ),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def cleanup_fixture(ids):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT action_id FROM action_requests WHERE tenant_id = %s", (ids["business_id"],))
        action_ids = [str(row.get("action_id") or "") for row in cursor.fetchall()]
        if action_ids:
            cursor.execute("DELETE FROM action_callback_attempts WHERE action_id = ANY(%s)", (action_ids,))
            cursor.execute("DELETE FROM action_callback_outbox WHERE action_id = ANY(%s)", (action_ids,))
            cursor.execute("DELETE FROM action_approvals WHERE action_id = ANY(%s)", (action_ids,))
            cursor.execute("DELETE FROM action_transitions WHERE action_id = ANY(%s)", (action_ids,))
            cursor.execute("DELETE FROM billing_ledger WHERE action_id = ANY(%s)", (action_ids,))
            cursor.execute("DELETE FROM action_requests WHERE action_id = ANY(%s)", (action_ids,))
        cursor.execute(
            """
            DELETE FROM agent_approvals
            WHERE run_id IN (SELECT id FROM agent_runs WHERE blueprint_id = %s)
            """,
            (ids["blueprint_id"],),
        )
        cursor.execute(
            """
            DELETE FROM agent_artifacts
            WHERE run_id IN (SELECT id FROM agent_runs WHERE blueprint_id = %s)
            """,
            (ids["blueprint_id"],),
        )
        cursor.execute(
            """
            DELETE FROM agent_run_steps
            WHERE run_id IN (SELECT id FROM agent_runs WHERE blueprint_id = %s)
            """,
            (ids["blueprint_id"],),
        )
        cursor.execute("DELETE FROM agent_runs WHERE blueprint_id = %s", (ids["blueprint_id"],))
        cursor.execute("DELETE FROM agent_blueprint_versions WHERE blueprint_id = %s", (ids["blueprint_id"],))
        cursor.execute("DELETE FROM agent_blueprints WHERE id = %s", (ids["blueprint_id"],))
        cursor.execute("DELETE FROM outreachsendqueue WHERE draft_id = %s", (ids["draft_id"],))
        cursor.execute("DELETE FROM outreachsendbatches WHERE id = %s", (ids["batch_id"],))
        cursor.execute("DELETE FROM outreachmessagedrafts WHERE id = %s", (ids["draft_id"],))
        cursor.execute("DELETE FROM prospectingleads WHERE id = %s", (ids["lead_id"],))
        cursor.execute("DELETE FROM usersessions WHERE user_id = %s", (ids["user_id"],))
        cursor.execute("DELETE FROM businesses WHERE id = %s", (ids["business_id"],))
        cursor.execute("DELETE FROM users WHERE id = %s", (ids["user_id"],))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def assert_no_dispatch(ids):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        row = fetch_one(
            cursor,
            """
            SELECT
                q.id AS queue_id,
                q.delivery_status,
                q.sent_at,
                q.provider_message_id,
                b.id AS batch_id,
                b.status AS batch_status
            FROM outreachsendqueue q
            JOIN outreachsendbatches b ON b.id = q.batch_id
            WHERE q.draft_id = %s
            """,
            (ids["draft_id"],),
        )
        if not row:
            raise RuntimeError("send queue row was not created")
        ids["batch_id"] = str(row.get("batch_id") or "")
        if row.get("delivery_status") != "queued":
            raise RuntimeError(f"dispatcher changed delivery_status: {row}")
        if row.get("sent_at") is not None or row.get("provider_message_id"):
            raise RuntimeError(f"dispatcher side effect detected: {row}")
        if row.get("batch_status") != "approved":
            raise RuntimeError(f"batch was not approved: {row}")
        return row
    finally:
        conn.close()


def main():
    suffix = uuid.uuid4().hex[:10]
    ids = {
        "user_id": f"smoke-agent-user-{suffix}",
        "business_id": f"smoke-agent-business-{suffix}",
        "lead_id": f"smoke-agent-lead-{suffix}",
        "draft_id": f"smoke-agent-draft-{suffix}",
        "blueprint_id": "",
        "run_id": "",
        "batch_id": "",
        "email": f"smoke-agent-{suffix}@example.invalid",
    }
    try:
        setup_fixture(ids)
        _, login_payload = request_json(
            "POST",
            "/api/auth/login",
            {"email": ids["email"], "password": PASSWORD},
            expected_status=200,
        )
        token = login_payload.get("token")
        if not token:
            raise RuntimeError("login did not return token")

        request_json("GET", "/api/auth/me", token=token, expected_status=200)
        _, blueprint_payload = request_json(
            "POST",
            "/api/agent-blueprints",
            {
                "business_id": ids["business_id"],
                "name": "Smoke Supervised Outreach Agent",
                "category": "outreach",
                "template": "supervised_outreach",
            },
            token=token,
            expected_status=201,
        )
        ids["blueprint_id"] = blueprint_payload["blueprint"]["id"]
        _, run_payload = request_json(
            "POST",
            f"/api/agent-blueprints/{ids['blueprint_id']}/runs",
            {"input": {"draft_ids": [ids["draft_id"]], "daily_limit": 10}},
            token=token,
            expected_status=201,
        )
        run = run_payload["run"]
        ids["run_id"] = run["id"]

        approval_count = 0
        while run.get("status") == "waiting_approval":
            pending = [item for item in run.get("approvals", []) if item.get("status") == "pending"]
            if not pending:
                raise RuntimeError(f"run is waiting approval but no pending approval exists: {run}")
            approval_id = pending[0]["id"]
            _, decision_payload = request_json(
                "POST",
                f"/api/agent-runs/{ids['run_id']}/approvals/{approval_id}/approve",
                {"reason": "smoke approved"},
                token=token,
                expected_status=200,
            )
            run = decision_payload["run"]
            approval_count += 1
            if approval_count > 4:
                raise RuntimeError("approval loop did not converge")

        if run.get("status") != "completed":
            raise RuntimeError(f"run did not complete: {run.get('status')} {run.get('error_text')}")
        queue_row = assert_no_dispatch(ids)
        time.sleep(2)
        assert_no_dispatch(ids)

        print(
            json.dumps(
                {
                    "success": True,
                    "base_url": BASE_URL,
                    "user_id": ids["user_id"],
                    "business_id": ids["business_id"],
                    "blueprint_id": ids["blueprint_id"],
                    "run_id": ids["run_id"],
                    "batch_id": ids["batch_id"],
                    "approval_count": approval_count,
                    "queue_status": queue_row.get("delivery_status"),
                    "dispatcher_started": False,
                    "fixture_cleaned": not KEEP_FIXTURE,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        if KEEP_FIXTURE:
            print("SMOKE_KEEP_FIXTURE enabled; fixture was not removed.", file=sys.stderr)
        else:
            cleanup_fixture(ids)


if __name__ == "__main__":
    main()
