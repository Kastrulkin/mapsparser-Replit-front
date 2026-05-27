#!/usr/bin/env python3
import json
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

import requests


repo_root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
for candidate in (os.getenv("APP_SRC_DIR"), "/app/src", str(repo_root / "src")):
    if candidate and candidate not in sys.path:
        sys.path.insert(0, candidate)

from auth_system import hash_password
from database_manager import get_db_connection


BASE_URL = os.getenv("SMOKE_BASE_URL", "http://localhost:8000").rstrip("/")
KEEP_FIXTURE = os.getenv("SMOKE_KEEP_FIXTURE", "").strip().lower() in {"1", "true", "yes"}
PASSWORD = os.getenv("SMOKE_PASSWORD", f"SmokePass-{uuid.uuid4().hex[:12]}-Aa1")


def request_json(method, path, payload=None, token=None, expected_status=None, **kwargs):
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        headers["Content-Type"] = "application/json"
        kwargs["data"] = json.dumps(payload)
    response = requests.request(method, f"{BASE_URL}{path}", headers=headers, timeout=30, **kwargs)
    try:
        data = response.json() if response.text.strip() else {}
    except Exception:
        raise RuntimeError(f"{method} {path}: non-json response {response.status_code}: {response.text[:200]}")
    if expected_status and response.status_code != expected_status:
        raise RuntimeError(f"{method} {path}: expected {expected_status}, got {response.status_code}: {data}")
    if response.status_code >= 400:
        raise RuntimeError(f"{method} {path}: HTTP {response.status_code}: {data}")
    return response.status_code, data


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
                "Smoke Table Agent User",
                "+10000000003",
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
                "Smoke Table Agent Business",
                "beauty_salon",
                "Smoke Street 5",
                "Smoke City",
                "US",
                "starter",
                "active",
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
        cursor.execute("DELETE FROM usersessions WHERE user_id = %s", (ids["user_id"],))
        cursor.execute("DELETE FROM businesses WHERE id = %s", (ids["business_id"],))
        cursor.execute("DELETE FROM users WHERE id = %s", (ids["user_id"],))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main():
    suffix = uuid.uuid4().hex[:10]
    ids = {
        "user_id": f"smoke-table-agent-user-{suffix}",
        "business_id": f"smoke-table-agent-business-{suffix}",
        "blueprint_id": "",
        "run_id": "",
        "email": f"smoke-table-agent-{suffix}@example.invalid",
    }
    fixture_created = False
    try:
        setup_fixture(ids)
        fixture_created = True
        _, login_payload = request_json(
            "POST",
            "/api/auth/login",
            {"email": ids["email"], "password": PASSWORD},
            expected_status=200,
        )
        token = login_payload.get("token")
        if not token:
            raise RuntimeError("login did not return token")

        _, draft_payload = request_json(
            "POST",
            "/api/agent-blueprints/draft",
            {
                "business_id": ids["business_id"],
                "description": "Проверь таблицу клиентов, найди пустые поля и дубли",
                "category": "tables",
            },
            token=token,
            expected_status=201,
        )
        ids["blueprint_id"] = draft_payload["blueprint"]["id"]
        request_json(
            "POST",
            f"/api/agent-blueprints/{ids['blueprint_id']}/setup",
            {
                "workflow_description": "Проверить таблицу клиентов перед импортом",
                "data_sources": ["uploaded_tables", "manual_context"],
                "extraction_rules": "Найти пустые email, дубли и строки к проверке",
                "processing_rules": "Не изменять таблицу, только показать проблемы",
                "output_format": "summary, exceptions, rows_to_review, recommendations",
                "approval_boundaries": ["final_output", "external_delivery"],
                "manual_control": "Человек проверяет отчёт перед импортом или рассылкой",
            },
            token=token,
            expected_status=200,
        )
        table_text = (
            "name,email,phone\n"
            "Анна,anna@example.com,+1\n"
            "Анна,anna@example.com,+1\n"
            "Борис,,+2\n"
        )
        request_json(
            "POST",
            f"/api/agent-blueprints/{ids['blueprint_id']}/sources",
            {
                "source_type": "text",
                "name": "clients.csv",
                "content_text": table_text,
            },
            token=token,
            expected_status=201,
        )
        _, run_payload = request_json(
            "POST",
            f"/api/agent-blueprints/{ids['blueprint_id']}/runs",
            {"input": {"source": "table_smoke"}},
            token=token,
            expected_status=201,
        )
        run = run_payload["run"]
        ids["run_id"] = run["id"]
        if run.get("status") != "waiting_approval":
            raise RuntimeError(f"table run did not stop for final approval: {run}")
        if any(item.get("step_type") == "capability" for item in run.get("steps", [])):
            raise RuntimeError(f"table run executed a capability: {run.get('steps')}")
        output_artifacts = [item for item in run.get("artifacts", []) if item.get("artifact_type") == "agent_output_draft"]
        if not output_artifacts:
            raise RuntimeError(f"table run did not create output draft: {run}")
        output_payload = output_artifacts[-1].get("payload_json") or {}
        result = output_payload.get("result") or {}
        if output_payload.get("external_dispatch_performed") is not False or output_payload.get("dispatch_state") != "not_dispatched":
            raise RuntimeError(f"table output boundary failed: {output_payload}")
        if result.get("external_dispatch_performed") is not False or result.get("delivery_state") != "not_dispatched":
            raise RuntimeError(f"table result boundary failed: {result}")
        for key in ("summary", "exceptions", "rows_to_review", "recommendations"):
            if key not in result:
                raise RuntimeError(f"table result missing {key}: {result}")
        if not result.get("exceptions") or not result.get("rows_to_review"):
            raise RuntimeError(f"table result is not useful enough: {result}")

        pending = [item for item in run.get("approvals", []) if item.get("status") == "pending"]
        if len(pending) != 1 or pending[0].get("approval_type") != "final_output":
            raise RuntimeError(f"final output approval missing: {run.get('approvals')}")

        _, review_payload = request_json(
            "GET",
            f"/api/agent-blueprints/{ids['blueprint_id']}/review",
            token=token,
            expected_status=200,
        )
        journal = review_payload.get("review", {}).get("journal") or []
        output_entries = [item for item in journal if isinstance(item, dict) and item.get("kind") == "output"]
        if not output_entries:
            raise RuntimeError(f"review journal missing table output: {review_payload}")
        output_details = output_entries[-1].get("details") or []
        output_detail_labels = {str(item.get("label") or "") for item in output_details if isinstance(item, dict)}
        if "Исключений" not in output_detail_labels or "Строк к проверке" not in output_detail_labels:
            raise RuntimeError(f"table journal output is not useful enough: {review_payload}")

        print(
            json.dumps(
                {
                    "success": True,
                    "base_url": BASE_URL,
                    "business_id": ids["business_id"],
                    "blueprint_id": ids["blueprint_id"],
                    "run_id": ids["run_id"],
                    "approval_type": pending[0].get("approval_type"),
                    "analysis_source": output_payload.get("analysis_source"),
                    "llm_analysis_used": output_payload.get("llm_analysis_used"),
                    "exceptions_count": len(result.get("exceptions") or []),
                    "rows_to_review_count": len(result.get("rows_to_review") or []),
                    "journal_detail_labels": sorted(output_detail_labels),
                    "external_dispatch_performed": False,
                    "fixture_cleaned": not KEEP_FIXTURE,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        if KEEP_FIXTURE:
            print("SMOKE_KEEP_FIXTURE enabled; fixture was not removed.", file=sys.stderr)
        elif fixture_created:
            cleanup_fixture(ids)
        time.sleep(0.1)


if __name__ == "__main__":
    main()
