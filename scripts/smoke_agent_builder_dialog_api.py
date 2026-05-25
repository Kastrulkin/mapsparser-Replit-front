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
PASSWORD = os.getenv("SMOKE_PASSWORD", f"SmokePass-Builder-{uuid.uuid4().hex[:12]}-Aa1")
KEEP_FIXTURE = os.getenv("SMOKE_KEEP_FIXTURE", "").strip().lower() in {"1", "true", "yes"}


def request_json(method, path, payload=None, token=None, expected_status=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        headers["Content-Type"] = "application/json"
    response = requests.request(
        method,
        f"{BASE_URL}{path}",
        headers=headers,
        data=json.dumps(payload) if payload is not None else None,
        timeout=30,
    )
    try:
        data = response.json() if response.text.strip() else {}
    except Exception:
        raise RuntimeError(f"{method} {path}: non-json response {response.status_code}: {response.text[:200]}")
    if expected_status and response.status_code != expected_status:
        raise RuntimeError(f"{method} {path}: expected {expected_status}, got {response.status_code}: {data}")
    if response.status_code >= 400:
        raise RuntimeError(f"{method} {path}: HTTP {response.status_code}: {data}")
    return data


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
                "Smoke Dialog Builder User",
                "+10000000004",
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
                "Smoke Dialog Builder Business",
                "beauty_salon",
                "Smoke Street 6",
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
            WHERE run_id IN (
                SELECT r.id FROM agent_runs r
                JOIN agent_blueprints b ON b.id = r.blueprint_id
                WHERE b.business_id = %s
            )
            """,
            (ids["business_id"],),
        )
        cursor.execute(
            """
            DELETE FROM agent_artifacts
            WHERE run_id IN (
                SELECT r.id FROM agent_runs r
                JOIN agent_blueprints b ON b.id = r.blueprint_id
                WHERE b.business_id = %s
            )
            """,
            (ids["business_id"],),
        )
        cursor.execute(
            """
            DELETE FROM agent_run_steps
            WHERE run_id IN (
                SELECT r.id FROM agent_runs r
                JOIN agent_blueprints b ON b.id = r.blueprint_id
                WHERE b.business_id = %s
            )
            """,
            (ids["business_id"],),
        )
        cursor.execute("DELETE FROM agent_runs WHERE blueprint_id IN (SELECT id FROM agent_blueprints WHERE business_id = %s)", (ids["business_id"],))
        cursor.execute("DELETE FROM agent_blueprint_versions WHERE blueprint_id IN (SELECT id FROM agent_blueprints WHERE business_id = %s)", (ids["business_id"],))
        cursor.execute("DELETE FROM agent_blueprints WHERE business_id = %s", (ids["business_id"],))
        cursor.execute("DELETE FROM agent_builder_sessions WHERE business_id = %s", (ids["business_id"],))
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
        "user_id": f"smoke-dialog-builder-user-{suffix}",
        "business_id": f"smoke-dialog-builder-business-{suffix}",
        "email": f"smoke-dialog-builder-{suffix}@example.invalid",
    }
    try:
        setup_fixture(ids)
        login_payload = request_json(
            "POST",
            "/api/auth/login",
            {"email": ids["email"], "password": PASSWORD},
            expected_status=200,
        )
        token = login_payload.get("token")
        if not token:
            raise RuntimeError("login did not return token")

        session_payload = request_json(
            "POST",
            "/api/agent-builder/sessions",
            {
                "business_id": ids["business_id"],
                "message": "Нужен агент, который проверяет договоры и ищет риски",
            },
            token=token,
            expected_status=201,
        )
        session = session_payload.get("session") or {}
        if session.get("category") != "documents":
            raise RuntimeError(f"builder did not infer documents: {session}")
        if not session.get("missing_questions"):
            raise RuntimeError(f"builder did not ask clarifying questions: {session}")
        if not (session.get("preview") or {}).get("understood_task"):
            raise RuntimeError(f"builder did not return preview: {session}")

        reply_payload = request_json(
            "POST",
            f"/api/agent-builder/sessions/{session['id']}/message",
            {
                "message": "Использовать DOCX договоры. Извлекать суммы, сроки, штрафы. Результат нужен как краткий отчёт, перед использованием проверяет человек.",
            },
            token=token,
            expected_status=200,
        )
        clarified = reply_payload.get("session") or {}
        if len(clarified.get("missing_questions") or []) >= len(session.get("missing_questions") or []):
            raise RuntimeError(f"builder did not reduce questions after clarification: {clarified}")

        created_payload = request_json(
            "POST",
            f"/api/agent-builder/sessions/{session['id']}/create-blueprint",
            {},
            token=token,
            expected_status=201,
        )
        blueprint = created_payload.get("blueprint") or {}
        version = created_payload.get("version") or {}
        if blueprint.get("category") != "documents":
            raise RuntimeError(f"created blueprint has wrong category: {created_payload}")
        if not version.get("id"):
            raise RuntimeError(f"created blueprint is missing version: {created_payload}")
        created_session = created_payload.get("session") or {}
        if created_session.get("status") != "blueprint_created" or created_session.get("blueprint_id") != blueprint.get("id"):
            raise RuntimeError(f"session was not linked to blueprint: {created_payload}")

        print(
            json.dumps(
                {
                    "success": True,
                    "base_url": BASE_URL,
                    "business_id": ids["business_id"],
                    "session_id": session["id"],
                    "blueprint_id": blueprint.get("id"),
                    "category": blueprint.get("category"),
                    "questions_initial": len(session.get("missing_questions") or []),
                    "questions_after_reply": len(clarified.get("missing_questions") or []),
                    "preview_available": True,
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
        time.sleep(0.1)


if __name__ == "__main__":
    main()
