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
                "Smoke Document Agent User",
                "+10000000001",
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
                "Smoke Document Agent Business",
                "beauty_salon",
                "Smoke Street 3",
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


def assert_business_agent_config(ids):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        row = fetch_one(cursor, "SELECT ai_agents_config FROM businesses WHERE id = %s", (ids["business_id"],))
        config = row.get("ai_agents_config") if row else {}
        if isinstance(config, str):
            config = json.loads(config)
        booking = config.get("booking_agent") if isinstance(config, dict) else {}
        marketing = config.get("marketing_agent") if isinstance(config, dict) else {}
        if booking.get("enabled") is not True or booking.get("tone") != "friendly" or booking.get("language") != "ru":
            raise RuntimeError(f"booking agent config was not persisted: {config}")
        if marketing.get("enabled") is not False or marketing.get("tone") != "professional" or marketing.get("language") != "en":
            raise RuntimeError(f"marketing agent config was not persisted: {config}")
    finally:
        conn.close()


def main():
    suffix = uuid.uuid4().hex[:10]
    ids = {
        "user_id": f"smoke-doc-agent-user-{suffix}",
        "business_id": f"smoke-doc-agent-business-{suffix}",
        "blueprint_id": "",
        "run_id": "",
        "email": f"smoke-doc-agent-{suffix}@example.invalid",
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

        request_json("GET", "/api/auth/me", token=token, expected_status=200)
        agent_config = {
            "booking_agent": {
                "enabled": True,
                "agent_id": None,
                "tone": "friendly",
                "language": "ru",
                "variables": {"smoke": "document_agent"},
            },
            "marketing_agent": {
                "enabled": False,
                "agent_id": None,
                "tone": "professional",
                "language": "en",
                "variables": {},
            },
        }
        request_json(
            "PUT",
            "/api/business/profile",
            {"business_id": ids["business_id"], "ai_agents_config": json.dumps(agent_config, ensure_ascii=False)},
            token=token,
            expected_status=200,
        )
        assert_business_agent_config(ids)

        _, draft_payload = request_json(
            "POST",
            "/api/agent-blueprints/draft",
            {
                "business_id": ids["business_id"],
                "description": "Обработай договор, извлеки факты, риски и поля",
                "category": "documents",
            },
            token=token,
            expected_status=201,
        )
        ids["blueprint_id"] = draft_payload["blueprint"]["id"]
        initial_version = draft_payload["version"]
        request_json(
            "POST",
            f"/api/agent-blueprints/{ids['blueprint_id']}/setup",
            {
                "workflow_description": "Проверить договор перед отправкой клиенту",
                "data_sources": ["uploaded_documents", "manual_context"],
                "extraction_rules": "Найти оплату, сроки, ответственность, штрафы и открытые вопросы",
                "processing_rules": "Не придумывать факты, показывать только то, что есть в документе",
                "output_format": "summary, facts, fields, risks, next_questions",
                "approval_boundaries": ["final_output", "external_delivery"],
                "manual_control": "Итог проверяет человек перед использованием",
            },
            token=token,
            expected_status=200,
        )
        contract_text = (
            "Договор оказания услуг. Оплата 10000 рублей до 10 июня. "
            "Ответственность за просрочку: штраф 10% от суммы. "
            "Срок действия договора 30 дней."
        ).encode("utf-8")
        request_json(
            "POST",
            f"/api/agent-blueprints/{ids['blueprint_id']}/sources/upload",
            token=token,
            expected_status=201,
            data={"name": "Smoke contract"},
            files={"file": ("contract.txt", contract_text, "text/plain")},
        )
        _, run_payload = request_json(
            "POST",
            f"/api/agent-blueprints/{ids['blueprint_id']}/runs",
            {"input": {"source": "document_smoke"}},
            token=token,
            expected_status=201,
        )
        run = run_payload["run"]
        ids["run_id"] = run["id"]
        if run.get("status") != "waiting_approval":
            raise RuntimeError(f"document run did not stop for final approval: {run}")
        if any(item.get("step_type") == "capability" for item in run.get("steps", [])):
            raise RuntimeError(f"generic document run executed a capability: {run.get('steps')}")
        output_artifacts = [item for item in run.get("artifacts", []) if item.get("artifact_type") == "agent_output_draft"]
        if not output_artifacts:
            raise RuntimeError(f"document run did not create output draft: {run}")
        output_payload = output_artifacts[-1].get("payload_json") or {}
        result = output_payload.get("result") or {}
        if output_payload.get("external_dispatch_performed") is not False or output_payload.get("dispatch_state") != "not_dispatched":
            raise RuntimeError(f"document output side effect boundary failed: {output_payload}")
        if output_payload.get("analysis_source") not in {"gigachat", "deterministic_fallback"}:
            raise RuntimeError(f"document output missing analysis source: {output_payload}")
        if "llm_analysis_used" not in output_payload:
            raise RuntimeError(f"document output missing llm usage flag: {output_payload}")
        if not output_payload.get("provenance"):
            raise RuntimeError(f"document output missing provenance: {output_payload}")
        if result.get("external_dispatch_performed") is not False:
            raise RuntimeError(f"document result side effect boundary failed: {result}")
        if result.get("analysis_source") not in {"gigachat", "deterministic_fallback"}:
            raise RuntimeError(f"document result missing analysis source: {result}")
        for key in ("summary", "facts", "fields", "risks", "next_questions"):
            if key not in result:
                raise RuntimeError(f"document result missing {key}: {result}")
        if not result.get("risks") or not result.get("fields"):
            raise RuntimeError(f"document result is not useful enough: {result}")

        pending = [item for item in run.get("approvals", []) if item.get("status") == "pending"]
        if len(pending) != 1 or pending[0].get("approval_type") != "final_output":
            raise RuntimeError(f"final output approval missing: {run.get('approvals')}")
        _, approved_payload = request_json(
            "POST",
            f"/api/agent-runs/{ids['run_id']}/approvals/{pending[0]['id']}/approve",
            {"reason": "document smoke approved"},
            token=token,
            expected_status=200,
        )
        approved_run = approved_payload["run"]
        if approved_run.get("status") != "completed":
            raise RuntimeError(f"approved document run did not complete: {approved_run}")
        final_artifacts = [item for item in approved_run.get("artifacts", []) if item.get("artifact_type") == "agent_final_result"]
        if not final_artifacts:
            raise RuntimeError(f"approved document run missing final result: {approved_run}")

        _, feedback_payload = request_json(
            "POST",
            f"/api/agent-runs/{ids['run_id']}/feedback",
            {"feedback": "В следующей версии отдельно выделяй санкции и даты"},
            token=token,
            expected_status=201,
        )
        new_version = feedback_payload.get("version") or {}
        if int(new_version.get("version_number") or 0) <= int(initial_version.get("version_number") or 0):
            raise RuntimeError(f"feedback did not create a newer version: {feedback_payload}")
        if new_version.get("id") == approved_run.get("blueprint_version_id"):
            raise RuntimeError(f"feedback version reused old run version: {feedback_payload}")

        _, review_payload = request_json(
            "GET",
            f"/api/agent-blueprints/{ids['blueprint_id']}/review",
            token=token,
            expected_status=200,
        )
        sections = review_payload.get("review", {}).get("sections") or []
        if not sections:
            raise RuntimeError(f"review did not expose human-readable sections: {review_payload}")

        print(
            json.dumps(
                {
                    "success": True,
                    "base_url": BASE_URL,
                    "business_id": ids["business_id"],
                    "blueprint_id": ids["blueprint_id"],
                    "run_id": ids["run_id"],
                    "initial_version": initial_version.get("version_number"),
                    "feedback_version": new_version.get("version_number"),
                    "approval_type": pending[0].get("approval_type"),
                    "analysis_source": output_payload.get("analysis_source"),
                    "llm_analysis_used": output_payload.get("llm_analysis_used"),
                    "provenance": output_payload.get("provenance"),
                    "external_dispatch_performed": False,
                    "system_agents_config_persisted": True,
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
