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
PASSWORD = os.getenv("SMOKE_PASSWORD", f"SmokePass-{uuid.uuid4().hex[:12]}-Aa1")
KEEP_FIXTURE = os.getenv("SMOKE_KEEP_FIXTURE", "").strip().lower() in {"1", "true", "yes"}

GENERIC_AGENT_CASES = [
    {
        "category": "documents",
        "description": "Проверь документ и покажи риски",
        "source_name": "Договор",
        "source_text": "Оплата 10000 до 10 июня. Штраф 10% за просрочку. Срок 30 дней.",
        "expected_result_keys": {"summary", "facts", "fields", "risks", "next_questions"},
    },
    {
        "category": "email",
        "description": "Подготовь письмо клиенту по контексту",
        "source_name": "Контекст письма",
        "source_text": "Клиент просил условия сотрудничества и сроки запуска в июне.",
        "expected_result_keys": {"subject", "body"},
    },
    {
        "category": "tables",
        "description": "Разбери таблицу и найди исключения",
        "source_name": "CSV с платежами",
        "source_text": "client,amount,status\nA,10000,paid\nB,,missing_amount\nC,5000,late",
        "expected_result_keys": {"summary", "exceptions"},
    },
    {
        "category": "reviews",
        "description": "Подготовь ответы на отзывы без публикации",
        "source_name": "Отзывы",
        "source_text": "Анна: отлично, 5 звезд. Иван: долго ждал, 3 звезды.",
        "expected_result_keys": {"replies"},
    },
]


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
                "Smoke Generic Agent User",
                "+10000000002",
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
                "Smoke Generic Agent Business",
                "beauty_salon",
                "Smoke Street 4",
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
        cursor.execute(
            "DELETE FROM agent_runs WHERE blueprint_id IN (SELECT id FROM agent_blueprints WHERE business_id = %s)",
            (ids["business_id"],),
        )
        cursor.execute(
            "DELETE FROM agent_blueprint_versions WHERE blueprint_id IN (SELECT id FROM agent_blueprints WHERE business_id = %s)",
            (ids["business_id"],),
        )
        cursor.execute("DELETE FROM agent_blueprints WHERE business_id = %s", (ids["business_id"],))
        cursor.execute("DELETE FROM usersessions WHERE user_id = %s", (ids["user_id"],))
        cursor.execute("DELETE FROM businesses WHERE id = %s", (ids["business_id"],))
        cursor.execute("DELETE FROM users WHERE id = %s", (ids["user_id"],))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def assert_generic_run_boundaries(case, run):
    if run.get("status") != "waiting_approval":
        raise RuntimeError(f"{case['category']} bypassed approval: {run}")
    capability_steps = [item for item in run.get("steps", []) if item.get("step_type") == "capability"]
    if capability_steps:
        raise RuntimeError(f"{case['category']} executed capability steps: {capability_steps}")
    pending = [item for item in run.get("approvals", []) if item.get("status") == "pending"]
    if len(pending) != 1 or pending[0].get("approval_type") != "final_output":
        raise RuntimeError(f"{case['category']} missing final output approval: {run.get('approvals')}")
    output_artifacts = [item for item in run.get("artifacts", []) if item.get("artifact_type") == "agent_output_draft"]
    if not output_artifacts:
        raise RuntimeError(f"{case['category']} did not create a draft artifact: {run}")
    output_payload = output_artifacts[-1].get("payload_json") or {}
    if output_payload.get("external_dispatch_performed") is not False:
        raise RuntimeError(f"{case['category']} performed external dispatch: {output_payload}")
    if output_payload.get("dispatch_state") != "not_dispatched":
        raise RuntimeError(f"{case['category']} dispatch state is not safe: {output_payload}")
    result = output_payload.get("result") or {}
    missing_keys = sorted(case["expected_result_keys"] - set(result.keys()))
    if missing_keys:
        raise RuntimeError(f"{case['category']} result missing {missing_keys}: {result}")


def main():
    suffix = uuid.uuid4().hex[:10]
    ids = {
        "user_id": f"smoke-generic-agent-user-{suffix}",
        "business_id": f"smoke-generic-agent-business-{suffix}",
        "email": f"smoke-generic-agent-{suffix}@example.invalid",
    }
    created = []
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

        for case in GENERIC_AGENT_CASES:
            _, draft_payload = request_json(
                "POST",
                "/api/agent-blueprints/draft",
                {
                    "business_id": ids["business_id"],
                    "description": case["description"],
                    "category": case["category"],
                },
                token=token,
                expected_status=201,
            )
            blueprint_id = draft_payload["blueprint"]["id"]
            created.append({"category": case["category"], "blueprint_id": blueprint_id})
            request_json(
                "POST",
                f"/api/agent-blueprints/{blueprint_id}/setup",
                {
                    "workflow_description": case["description"],
                    "data_sources": ["manual_context"],
                    "extraction_rules": "Извлечь факты и важные поля",
                    "processing_rules": "Не отправлять наружу, не публиковать, не запускать dispatcher",
                    "output_format": "human review result",
                    "approval_boundaries": ["final_output", "external_delivery"],
                    "manual_control": "Итог всегда проверяет человек",
                },
                token=token,
                expected_status=200,
            )
            request_json(
                "POST",
                f"/api/agent-blueprints/{blueprint_id}/sources",
                {
                    "source_type": "text",
                    "name": case["source_name"],
                    "content_text": case["source_text"],
                },
                token=token,
                expected_status=201,
            )
            _, run_payload = request_json(
                "POST",
                f"/api/agent-blueprints/{blueprint_id}/runs",
                {"input": {"source": "generic_boundary_smoke"}},
                token=token,
                expected_status=201,
            )
            assert_generic_run_boundaries(case, run_payload["run"])

        print(
            json.dumps(
                {
                    "success": True,
                    "base_url": BASE_URL,
                    "business_id": ids["business_id"],
                    "checked_categories": [item["category"] for item in GENERIC_AGENT_CASES],
                    "blueprints": created,
                    "external_dispatch_performed": False,
                    "dispatcher_started": False,
                    "approvals_required": True,
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
