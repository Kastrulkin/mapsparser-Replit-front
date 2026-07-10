from __future__ import annotations

import json
import os
import uuid
from typing import Any

from services.agent_blueprint_runner import AgentBlueprintRunner, parse_json_field
from services.agent_integration_preflight import build_agent_integration_preflight
from services.agent_run_billing import AGENT_RUN_ESTIMATED_CREDITS, finalize_agent_run_credits, reserve_agent_run_credits


ACTIVE_EXECUTION_STATUSES = ("queued", "running", "retry_wait")
TRANSIENT_ERROR_MARKERS = ("timeout", "timed out", "connection", "temporar", "429", "502", "503", "504")


def async_agent_runs_enabled(business_id: str) -> bool:
    enabled = str(os.getenv("AGENT_ASYNC_RUNS_ENABLED", "false")).strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return False
    allowed = {
        item.strip()
        for item in str(os.getenv("AGENT_BETA_BUSINESS_IDS", "")).split(",")
        if item.strip()
    }
    return not allowed or business_id in allowed


def enqueue_agent_run(
    cursor: Any,
    *,
    blueprint: dict[str, Any],
    version: dict[str, Any],
    input_payload: dict[str, Any],
    user_data: dict[str, Any],
    idempotency_key: str,
) -> dict[str, Any]:
    blueprint_id = str(blueprint.get("id") or "")
    business_id = str(blueprint.get("business_id") or "")
    user_id = str(user_data.get("user_id") or user_data.get("id") or "")
    clean_key = str(idempotency_key or "").strip()
    if not clean_key:
        return {"success": False, "code": "IDEMPOTENCY_KEY_REQUIRED", "error": "idempotency_key is required"}

    metadata = parse_json_field(blueprint.get("metadata_json"), {})
    preflight = build_agent_integration_preflight(
        cursor,
        business_id=business_id,
        metadata=metadata if isinstance(metadata, dict) else {},
        input_payload=input_payload,
    )
    if not preflight.get("ready"):
        return {
            "success": False,
            "code": "AGENT_INTEGRATIONS_REQUIRED",
            "error": "agent_integration_preflight_blocked",
            "preflight": preflight,
        }

    cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (blueprint_id,))
    cursor.execute(
        """
        SELECT * FROM agent_runs
        WHERE business_id = %s AND blueprint_id = %s AND idempotency_key = %s
        LIMIT 1
        """,
        (business_id, blueprint_id, clean_key),
    )
    existing = cursor.fetchone()
    if existing:
        run = AgentBlueprintRunner(cursor).load_run(str(existing.get("id") or ""), user_data)
        return {"success": True, "run": run, "reused": True}

    cursor.execute(
        """
        SELECT id FROM agent_runs
        WHERE blueprint_id = %s AND status IN ('queued', 'running', 'retry_wait')
        ORDER BY COALESCE(queued_at, started_at, updated_at) DESC
        LIMIT 1
        """,
        (blueprint_id,),
    )
    in_progress = cursor.fetchone()
    if in_progress:
        return {
            "success": False,
            "code": "AGENT_RUN_ALREADY_IN_PROGRESS",
            "error": "agent run already in progress",
            "run_id": str(in_progress.get("id") or ""),
        }

    runner = AgentBlueprintRunner(cursor)
    runner._supersede_pending_runs(blueprint_id)
    run_id = str(uuid.uuid4())
    preview = input_payload.get("preview_mode") is True
    billing = reserve_agent_run_credits(
        cursor,
        business_id=business_id,
        user_id=user_id,
        run_id=run_id,
        idempotency_key=f"agent-run:{business_id}:{blueprint_id}:{clean_key}",
        preview=preview,
        estimated_credits=AGENT_RUN_ESTIMATED_CREDITS,
    )
    if not preview and billing.get("status") != "reserved":
        return {
            "success": False,
            "code": "AGENT_RUN_BILLING_BLOCKED",
            "error": "Недостаточно кредитов для запуска агента.",
            "billing": billing,
            "billing_url": "/dashboard/profile?focus=subscription#subscription",
        }

    cursor.execute(
        """
        INSERT INTO agent_runs (
            id, blueprint_id, blueprint_version_id, business_id, status,
            input_json, output_json, created_by_user_id, idempotency_key,
            queued_at, started_at, attempt_count, max_attempts, billing_reservation_id
        )
        VALUES (%s, %s, %s, %s, 'queued', %s::jsonb, '{}'::jsonb, %s, %s,
                NOW(), NULL, 0, 3, %s)
        """,
        (
            run_id,
            blueprint_id,
            str(version.get("id") or ""),
            business_id,
            json.dumps(input_payload or {}, ensure_ascii=False),
            user_id,
            clean_key,
            billing.get("reservation_id"),
        ),
    )
    run = runner.load_run(run_id, user_data)
    if isinstance(run, dict):
        run["billing"] = billing
    return {"success": True, "run": run, "reused": False}


def claim_next_agent_run(cursor: Any) -> dict[str, Any] | None:
    cursor.execute(
        """
        UPDATE agent_runs
        SET status = CASE WHEN attempt_count < max_attempts THEN 'retry_wait' ELSE 'failed' END,
            next_attempt_at = CASE WHEN attempt_count < max_attempts THEN NOW() ELSE NULL END,
            error_text = CASE
                WHEN attempt_count < max_attempts THEN 'worker heartbeat expired; retry scheduled'
                ELSE 'worker heartbeat expired; retry limit reached'
            END,
            completed_at = CASE WHEN attempt_count < max_attempts THEN NULL ELSE NOW() END,
            updated_at = NOW()
        WHERE status = 'running'
          AND heartbeat_at < NOW() - INTERVAL '5 minutes'
        """
    )
    cursor.execute(
        """
        WITH next_run AS (
            SELECT id
            FROM agent_runs
            WHERE status = 'queued'
               OR (status = 'retry_wait' AND COALESCE(next_attempt_at, NOW()) <= NOW())
            ORDER BY COALESCE(next_attempt_at, queued_at, updated_at) ASC
            FOR UPDATE SKIP LOCKED
            LIMIT 1
        )
        UPDATE agent_runs r
        SET status = 'running',
            started_at = COALESCE(r.started_at, NOW()),
            heartbeat_at = NOW(),
            next_attempt_at = NULL,
            attempt_count = r.attempt_count + 1,
            updated_at = NOW()
        FROM next_run
        WHERE r.id = next_run.id
        RETURNING r.*
        """
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def execute_claimed_agent_run(cursor: Any, run: dict[str, Any]) -> dict[str, Any]:
    run_id = str(run.get("id") or "")
    user_data = {
        "user_id": str(run.get("created_by_user_id") or ""),
        "id": str(run.get("created_by_user_id") or ""),
        "is_superadmin": False,
    }
    runner = AgentBlueprintRunner(cursor)
    try:
        result = runner.execute_queued_run(run_id, user_data)
        current = result.get("run") if isinstance(result.get("run"), dict) else runner.load_run(run_id, user_data) or {}
    except Exception as exc:
        _schedule_agent_run_retry(cursor, run, str(exc))
        return {"success": False, "error": str(exc), "run_id": run_id, "retry_scheduled": True}

    if str(current.get("status") or "") == "failed" and _is_transient_error(str(current.get("error_text") or "")):
        _schedule_agent_run_retry(cursor, {**run, **current}, str(current.get("error_text") or "temporary agent run failure"))
        current = runner.load_run(run_id, user_data) or current

    if str(current.get("status") or "") in {"completed", "failed", "superseded", "rejected"}:
        billing_summary = (
            ((current.get("observability") or {}).get("unified_billing_ledger") or {}).get("summary")
            if isinstance(current.get("observability"), dict)
            else {}
        )
        actual_tokens = int((billing_summary or {}).get("actual_tokens") or 0)
        if current.get("billing_reservation_id"):
            cursor.execute(
                "SELECT reserved_credits FROM operatorcreditreservations WHERE id = %s",
                (current.get("billing_reservation_id"),),
            )
            reservation = cursor.fetchone() or {}
            current["reserved_credits"] = int(reservation.get("reserved_credits") or AGENT_RUN_ESTIMATED_CREDITS)
        billing = finalize_agent_run_credits(cursor, run=current, actual_tokens=actual_tokens)
        cursor.execute(
            """
            UPDATE agent_runs
            SET output_json = COALESCE(output_json, '{}'::jsonb) || jsonb_build_object('run_billing', %s::jsonb),
                heartbeat_at = NOW(),
                updated_at = NOW()
            WHERE id = %s
            """,
            (json.dumps(billing, ensure_ascii=False), run_id),
        )
        current["run_billing"] = billing
    return {"success": True, "run": current}


def _schedule_agent_run_retry(cursor: Any, run: dict[str, Any], error_text: str) -> None:
    run_id = str(run.get("id") or "")
    attempts = int(run.get("attempt_count") or 1)
    max_attempts = int(run.get("max_attempts") or 3)
    retry = attempts < max_attempts and _is_transient_error(error_text)
    cursor.execute(
        "DELETE FROM agent_run_steps WHERE run_id = %s AND status IN ('running', 'failed')",
        (run_id,),
    )
    cursor.execute(
        """
        UPDATE agent_runs
        SET status = %s,
            error_text = %s,
            next_attempt_at = CASE WHEN %s THEN NOW() + (%s * INTERVAL '1 minute') ELSE NULL END,
            completed_at = CASE WHEN %s THEN NULL ELSE NOW() END,
            heartbeat_at = NOW(),
            updated_at = NOW()
        WHERE id = %s
        """,
        (
            "retry_wait" if retry else "failed",
            error_text[:2000],
            retry,
            min(2 ** max(attempts - 1, 0), 15),
            retry,
            run_id,
        ),
    )


def _is_transient_error(error_text: str) -> bool:
    normalized = str(error_text or "").lower()
    return any(marker in normalized for marker in TRANSIENT_ERROR_MARKERS)
