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
                "new",
                "",
                ids["business_id"],
                "client_outreach",
                "unprocessed",
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
        cursor.execute("DELETE FROM outreachsendqueue WHERE lead_id = %s", (ids["lead_id"],))
        cursor.execute("DELETE FROM outreachsendbatches WHERE id = %s", (ids["batch_id"],))
        cursor.execute("DELETE FROM outreachmessagedrafts WHERE lead_id = %s", (ids["lead_id"],))
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
            WHERE q.lead_id = %s
            ORDER BY q.created_at DESC
            LIMIT 1
            """,
            (ids["lead_id"],),
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
        "draft_id": "",
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
            {
                "input": {
                    "source": "smoke_agent_blueprint",
                    "city": "Smoke City",
                    "category": "",
                    "intent": "client_outreach",
                    "daily_limit": 10,
                    "limit": 5,
                }
            },
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
        source_artifacts = [
            item
            for item in run.get("artifacts", [])
            if item.get("artifact_type") == "lead_source_plan"
        ]
        if not source_artifacts:
            raise RuntimeError(f"run completed without lead_source_plan artifact: {run}")
        source_payload = source_artifacts[-1].get("payload_json") or {}
        if source_payload.get("source") != "prospectingleads":
            raise RuntimeError(f"lead sourcing did not use prospectingleads: {source_payload}")
        if source_payload.get("status") != "hydrated" or source_payload.get("count") != 1:
            raise RuntimeError(f"lead sourcing artifact was not hydrated from real leads: {source_payload}")
        shortlist_artifacts = [
            item
            for item in run.get("artifacts", [])
            if item.get("artifact_type") == "lead_shortlist"
        ]
        if not shortlist_artifacts:
            raise RuntimeError(f"run completed without lead_shortlist artifact: {run}")
        shortlist_payload = shortlist_artifacts[-1].get("payload_json") or {}
        if shortlist_payload.get("source_artifact") != "lead_source_plan":
            raise RuntimeError(f"shortlist did not derive from lead_source_plan: {shortlist_payload}")
        if shortlist_payload.get("count") != 1:
            raise RuntimeError(f"shortlist did not include sourced lead: {shortlist_payload}")
        draft_artifacts = [
            item
            for item in run.get("artifacts", [])
            if item.get("artifact_type") == "message_drafts"
        ]
        draft_items = []
        if draft_artifacts:
            payload = draft_artifacts[-1].get("payload_json") or {}
            draft_items = payload.get("items") if isinstance(payload.get("items"), list) else []
        if not draft_items:
            raise RuntimeError(f"run completed without message draft artifacts: {run}")
        ids["draft_id"] = str(draft_items[0].get("id") or "")
        if not ids["draft_id"]:
            raise RuntimeError(f"message draft artifact has no draft id: {draft_items[0]}")
        send_steps = [
            item
            for item in run.get("steps", [])
            if item.get("step_key") == "send_limited_batch"
        ]
        if not send_steps:
            raise RuntimeError(f"run completed without send_limited_batch step: {run}")
        send_output = send_steps[-1].get("output_json") or {}
        send_result = ((send_output.get("orchestrator") or {}).get("result") or {})
        if send_result.get("dispatch_state") != "queued_not_dispatched":
            raise RuntimeError(f"send step did not expose queued_not_dispatched state: {send_result}")
        if send_result.get("external_dispatch_performed") is not False:
            raise RuntimeError(f"send step claims external dispatch happened: {send_result}")
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
                    "source_artifact_status": source_payload.get("status"),
                    "source_artifact_count": source_payload.get("count"),
                    "approval_count": approval_count,
                    "queue_status": queue_row.get("delivery_status"),
                    "dispatch_state": send_result.get("dispatch_state"),
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
