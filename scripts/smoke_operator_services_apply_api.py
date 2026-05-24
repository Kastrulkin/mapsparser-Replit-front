#!/usr/bin/env python3
import json
import os
import sys
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
from services.operator_services_optimization import optimize_services_from_operator


BASE_URL = os.getenv("SMOKE_BASE_URL", "http://localhost:8000").rstrip("/")
KEEP_FIXTURE = os.getenv("SMOKE_KEEP_FIXTURE", "").strip().lower() in {"1", "true", "yes"}
PASSWORD = os.getenv("SMOKE_PASSWORD", f"SmokePass-{uuid.uuid4().hex[:12]}-Aa1")


def row_to_dict(row):
    if not row:
        return None
    if isinstance(row, dict):
        return dict(row)
    if hasattr(row, "keys"):
        return dict(row)
    return None


def request_json(method, path, payload=None, token=None, expected_status=None, allow_error=False):
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
    if status >= 400 and not allow_error:
        raise RuntimeError(f"{method} {path}: HTTP {status}: {data}")
    return status, data


def fetch_one(cursor, query, params):
    cursor.execute(query, params)
    return row_to_dict(cursor.fetchone())


def fetch_all(cursor, query, params):
    cursor.execute(query, params)
    return [row_to_dict(row) or {} for row in (cursor.fetchall() or [])]


def table_exists(cursor, table_name):
    cursor.execute("SELECT to_regclass(%s) AS table_ref", (f"public.{table_name}",))
    row = row_to_dict(cursor.fetchone()) or {}
    return bool(row.get("table_ref"))


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
                "Smoke Operator Services User",
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
                "Smoke Operator Services Business",
                "beauty_salon",
                "Smoke Street 3",
                "Smoke City",
                "US",
                "trial",
                "active",
            ),
        )
        for index, service_id in enumerate(ids["service_ids"], start=1):
            cursor.execute(
                """
                INSERT INTO userservices (
                    id, business_id, user_id, name, description, optimized_name,
                    optimized_description, category, price, is_active, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, '', '', %s, %s, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (
                    service_id,
                    ids["business_id"],
                    ids["user_id"],
                    f"Smoke Service {index}",
                    f"Original smoke description {index}",
                    "beauty",
                    str(1000 + index),
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
        if table_exists(cursor, "agent_action_ledger"):
            cursor.execute("DELETE FROM agent_action_ledger WHERE business_id = %s", (ids["business_id"],))
        if table_exists(cursor, "serviceregenerationjobitems"):
            cursor.execute(
                """
                DELETE FROM serviceregenerationjobitems
                WHERE job_id IN (
                    SELECT id FROM serviceregenerationjobs WHERE business_id = %s
                )
                """,
                (ids["business_id"],),
            )
        if table_exists(cursor, "serviceregenerationjobs"):
            cursor.execute("DELETE FROM serviceregenerationjobs WHERE business_id = %s", (ids["business_id"],))
        if table_exists(cursor, "operatorcreditreservations"):
            cursor.execute("DELETE FROM operatorcreditreservations WHERE business_id = %s", (ids["business_id"],))
        if table_exists(cursor, "credit_ledger"):
            cursor.execute("DELETE FROM credit_ledger WHERE user_id = %s", (ids["user_id"],))
        cursor.execute("DELETE FROM userservices WHERE business_id = %s", (ids["business_id"],))
        cursor.execute("DELETE FROM usersessions WHERE user_id = %s", (ids["user_id"],))
        cursor.execute("DELETE FROM businesses WHERE id = %s", (ids["business_id"],))
        cursor.execute("DELETE FROM users WHERE id = %s", (ids["user_id"],))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fake_services_generator(prompt, *, business_id, user_id):
    return json.dumps(
        {
            "services": [
                {
                    "service_id": "SERVICE_ID_1",
                    "optimized_name": "Smoke Optimized Service 1",
                    "seo_description": "Smoke SEO description one.",
                },
                {
                    "service_id": "SERVICE_ID_2",
                    "optimized_name": "Smoke Optimized Service 2",
                    "seo_description": "Smoke SEO description two.",
                },
            ]
        },
        ensure_ascii=False,
    )


def generate_suggestions(ids):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        def generator(prompt, *, business_id, user_id):
            return fake_services_generator(prompt, business_id=business_id, user_id=user_id).replace(
                "SERVICE_ID_1", ids["service_ids"][0]
            ).replace("SERVICE_ID_2", ids["service_ids"][1])

        result = optimize_services_from_operator(
            cursor,
            business_id=ids["business_id"],
            user_id=ids["user_id"],
            limit=2,
            channel="smoke",
            services_generator=generator,
        )
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def service_rows(ids):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        return fetch_all(
            cursor,
            """
            SELECT id, name, optimized_name, optimized_description
            FROM userservices
            WHERE business_id = %s
            ORDER BY id ASC
            """,
            (ids["business_id"],),
        )
    finally:
        conn.close()


def ledger_count(ids):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        row = fetch_one(
            cursor,
            "SELECT COUNT(*) AS count FROM credit_ledger WHERE user_id = %s",
            (ids["user_id"],),
        ) or {}
        return int(row.get("count") or 0)
    finally:
        conn.close()


def latest_apply_event(ids, expected_status):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        rows = fetch_all(
            cursor,
            """
            SELECT status, metadata_json, output_summary
            FROM agent_action_ledger
            WHERE business_id = %s
              AND capability = 'localos.operator'
              AND action_type = 'operator_tool_executed'
            ORDER BY created_at DESC
            LIMIT 5
            """,
            (ids["business_id"],),
        )
        for row in rows:
            metadata = row.get("metadata_json") or {}
            if isinstance(metadata, str):
                metadata = json.loads(metadata)
            if metadata.get("action_key") == "services_optimize_apply" and row.get("status") == expected_status:
                return {**row, "metadata_json": metadata}
        return None
    finally:
        conn.close()


def assert_condition(condition, message, failures):
    if not condition:
        failures.append(message)


def main():
    suffix = uuid.uuid4().hex[:10]
    ids = {
        "user_id": f"smoke-operator-user-{suffix}",
        "business_id": f"smoke-operator-business-{suffix}",
        "service_ids": [
            f"smoke-operator-service-a-{suffix}",
            f"smoke-operator-service-b-{suffix}",
        ],
        "email": f"smoke-operator-{suffix}@example.invalid",
    }
    fixture_cleaned = False
    try:
        setup_fixture(ids)
        generate_result = generate_suggestions(ids)
        ids["job_id"] = str((generate_result.get("optimization_job") or {}).get("id") or "")
        ledger_after_generate = ledger_count(ids)
        before_block_rows = service_rows(ids)

        _, login_payload = request_json(
            "POST",
            "/api/auth/login",
            {"email": ids["email"], "password": PASSWORD},
            expected_status=200,
        )
        token = str(login_payload.get("token") or "")
        if not token:
            raise RuntimeError("login did not return token")

        _, blocked_payload = request_json(
            "POST",
            "/api/operator/services/optimize/apply",
            {"business_id": ids["business_id"], "job_id": ids["job_id"], "limit": 2},
            token=token,
            expected_status=200,
        )
        after_block_rows = service_rows(ids)
        blocked_event = latest_apply_event(ids, "blocked")

        _, apply_payload = request_json(
            "POST",
            "/api/operator/services/optimize/apply",
            {"business_id": ids["business_id"], "job_id": ids["job_id"], "limit": 2, "confirm_apply": True},
            token=token,
            expected_status=200,
        )
        after_apply_rows = service_rows(ids)
        ledger_after_apply = ledger_count(ids)
        completed_event = latest_apply_event(ids, "completed")

        failures = []
        blocked_result = blocked_payload.get("operator_result") or {}
        apply_result = apply_payload.get("operator_result") or {}
        completed_metadata = (completed_event or {}).get("metadata_json") or {}
        blocked_metadata = (blocked_event or {}).get("metadata_json") or {}

        assert_condition(generate_result.get("status") == "completed", "generate_status_not_completed", failures)
        assert_condition(bool(ids["job_id"]), "missing_job_id", failures)
        assert_condition(ledger_after_generate >= 1, f"missing_generation_ledger={ledger_after_generate}", failures)
        assert_condition(blocked_payload.get("success") is False, "apply_without_confirm_success", failures)
        assert_condition("explicit_confirmation_required" in (blocked_result.get("blocked_reasons") or []), "missing_explicit_confirmation_block", failures)
        assert_condition(before_block_rows == after_block_rows, "services_changed_without_confirm", failures)
        assert_condition(bool(blocked_event), "missing_blocked_audit_event", failures)
        assert_condition(blocked_metadata.get("explicit_confirmation") is False, "blocked_event_confirmation_not_false", failures)
        assert_condition(apply_payload.get("success") is True, "confirmed_apply_not_success", failures)
        assert_condition(apply_result.get("status") == "completed", "confirmed_apply_status_not_completed", failures)
        assert_condition(apply_result.get("applied_count") == 2, f"applied_count={apply_result.get('applied_count')}", failures)
        assert_condition(apply_result.get("external_writes_performed") is False, "external_writes_performed_true", failures)
        assert_condition(apply_result.get("external_calls_performed") is False, "external_calls_performed_true", failures)
        assert_condition(apply_result.get("credit_charged") is False, "credit_charged_true", failures)
        assert_condition(int(apply_result.get("charged_credits") or 0) == 0, f"charged_credits={apply_result.get('charged_credits')}", failures)
        assert_condition(ledger_after_apply == ledger_after_generate, "ledger_changed_on_apply", failures)
        assert_condition(bool(completed_event), "missing_completed_audit_event", failures)
        assert_condition(completed_metadata.get("external_writes_performed") is False, "completed_event_external_writes", failures)
        assert_condition(completed_metadata.get("credit_charged") is False, "completed_event_credit_charged", failures)
        assert_condition(completed_metadata.get("explicit_confirmation") is True, "completed_event_confirmation_not_true", failures)
        assert_condition(all(str(row.get("optimized_name") or "").startswith("Smoke Optimized Service") for row in after_apply_rows), "services_not_optimized", failures)

        if not KEEP_FIXTURE:
            cleanup_fixture(ids)
            fixture_cleaned = True

        output = {
            "success": not failures,
            "base_url": BASE_URL,
            "scenario": "operator_services_apply_authenticated_boundary",
            "user_id": ids["user_id"],
            "business_id": ids["business_id"],
            "job_id": ids["job_id"],
            "generated_suggestions": len(generate_result.get("service_suggestions") or []),
            "ledger_after_generate": ledger_after_generate,
            "ledger_after_apply": ledger_after_apply,
            "blocked_without_confirm": blocked_result.get("status") == "blocked",
            "confirmed_apply_status": apply_result.get("status"),
            "applied_count": apply_result.get("applied_count"),
            "external_writes_performed": apply_result.get("external_writes_performed"),
            "credit_charged": apply_result.get("credit_charged"),
            "blocked_audit_event": bool(blocked_event),
            "completed_audit_event": bool(completed_event),
            "fixture_cleaned": fixture_cleaned,
            "failures": failures,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        if failures:
            raise SystemExit(1)
    finally:
        if not KEEP_FIXTURE and not fixture_cleaned:
            cleanup_fixture(ids)


if __name__ == "__main__":
    main()
