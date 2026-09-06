from __future__ import annotations

import json
import sys
import os
import uuid
from typing import Any

from services.agent_canary_budget import evaluate_agent_canary_budget
from services.agent_blueprint_runner import AgentBlueprintRunner, parse_json_field
from services.agent_integration_preflight import build_agent_integration_preflight
from services.agent_run_billing import AGENT_RUN_ESTIMATED_CREDITS, finalize_agent_run_credits, reserve_agent_run_credits
from services.compiled_script_artifact import validate_artifact as validate_compiled_script_artifact
from services.compiled_script_runtime import CompiledRuntimeUnavailable, execute_in_attested_sandbox


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
    input_snapshot: dict[str, Any] | None = None,
    require_execution_mode_confirmation: bool = False,
) -> dict[str, Any]:
    blueprint_id = str(blueprint.get("id") or "")
    business_id = str(blueprint.get("business_id") or "")
    user_id = str(user_data.get("user_id") or user_data.get("id") or "")
    clean_key = str(idempotency_key or "").strip()
    snapshot = input_snapshot if isinstance(input_snapshot, dict) else {}
    if not clean_key:
        return {"success": False, "code": "IDEMPOTENCY_KEY_REQUIRED", "error": "idempotency_key is required"}

    # Replay is intentionally before the current version's preflight.  A
    # retry must return the original pinned run even when the active blueprint
    # configuration has changed since the first request.
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

    state_error = _validate_admission_state(
        blueprint,
        version,
        input_payload,
        require_execution_mode_confirmation=require_execution_mode_confirmation,
    )
    if state_error:
        return state_error
    version_error = _validate_pinned_version(blueprint, version)
    if version_error:
        return {"success": False, "code": "AGENT_VERSION_NOT_EXECUTABLE", "error": version_error}
    if str(version.get("compiled_state") or "legacy").strip() != "legacy" and (
        not str(snapshot.get("snapshot_id") or "") or not str(snapshot.get("content_hash") or "")
    ):
        return {"success": False, "code": "COMPILED_INPUT_SNAPSHOT_REQUIRED", "error": "compiled runs require an immutable input snapshot"}

    metadata = parse_json_field(blueprint.get("metadata_json"), {})
    required_bindings = parse_json_field(version.get("required_integration_bindings_json"), None)
    preflight = build_agent_integration_preflight(
        cursor,
        business_id=business_id,
        metadata=metadata if isinstance(metadata, dict) else {},
        required_bindings=required_bindings if isinstance(required_bindings, list) else None,
        input_payload=input_payload,
    )
    if not preflight.get("ready"):
        return {
            "success": False,
            "code": "AGENT_INTEGRATIONS_REQUIRED",
            "error": "agent_integration_preflight_blocked",
            "preflight": preflight,
        }

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

    preview = input_payload.get("preview_mode") is True
    canary = evaluate_agent_canary_budget(
        cursor,
        blueprint=blueprint,
        requested_credits=AGENT_RUN_ESTIMATED_CREDITS,
    )
    if not preview and canary.get("enabled") and not canary.get("allowed"):
        return {
            "success": False,
            "code": "AGENT_CANARY_BUDGET_BLOCKED",
            "error": "agent canary window or credit budget blocked this run",
            "canary": canary,
        }

    runner = AgentBlueprintRunner(cursor)
    runner._supersede_pending_runs(blueprint_id)
    run_id = str(uuid.uuid4())
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
            queued_at, started_at, attempt_count, max_attempts, billing_reservation_id,
            input_snapshot_id, input_snapshot_hash
        )
        VALUES (%s, %s, %s, %s, 'queued', %s::jsonb, '{}'::jsonb, %s, %s,
                NOW(), NULL, 0, 3, %s, %s, %s)
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
            str(snapshot.get("snapshot_id") or "") or None,
            str(snapshot.get("content_hash") or "") or None,
        ),
    )
    cursor.execute(
        """INSERT INTO agent_artifacts(id,run_id,step_id,artifact_type,title,payload_json)
           VALUES(%s,%s,NULL,'run_admission_audit','Запуск принят',%s::jsonb)""",
        (
            str(uuid.uuid4()),
            run_id,
            json.dumps(
                {
                    "run_id": run_id,
                    "blueprint_version_id": str(version.get("id") or ""),
                    "compiled_artifact_hash": str(version.get("compiled_artifact_hash") or ""),
                    "input_snapshot_id": str(snapshot.get("snapshot_id") or ""),
                    "input_snapshot_hash": str(snapshot.get("content_hash") or ""),
                    "actor": {
                        "user_id": user_id,
                        "session_kind": str(user_data.get("session_kind") or "standard"),
                        "scope_business_id": str(user_data.get("scope_business_id") or ""),
                        "is_superadmin": bool(user_data.get("is_superadmin")),
                        "impersonating": bool(user_data.get("impersonating")),
                    },
                },
                ensure_ascii=False,
            ),
        ),
    )
    run = runner.load_run(run_id, user_data)
    if isinstance(run, dict):
        run["billing"] = billing
    return {"success": True, "run": run, "reused": False}


def _validate_admission_state(
    blueprint: dict[str, Any],
    version: dict[str, Any],
    input_payload: dict[str, Any],
    *,
    require_execution_mode_confirmation: bool = False,
) -> dict[str, Any] | None:
    """Reject a new intent when the current executable state has changed.

    This intentionally runs after the idempotency lookup.  A network retry is
    not a second intent and must retain the original version and admission
    audit, while a fresh key must not queue a paused blueprint or an old
    manually/scheduled executable version.
    """
    if not str(version.get("id") or "").strip():
        return {
            "success": False,
            "code": "AGENT_RUN_VERSION_STALE",
            "error": "blueprint or pinned version changed",
        }
    metadata = parse_json_field(blueprint.get("metadata_json"), {})
    metadata = metadata if isinstance(metadata, dict) else {}
    # Compiled scripts have their own explicit lifecycle: successful preview
    # followed by human approval. The immutable blueprint-column pointer pins
    # exactly one executable version without a generic activation click, but
    # it never revives a paused blueprint or an older approved version.
    if str(version.get("compiled_state") or "legacy").strip() in {"approved", "active"}:
        if str(blueprint.get("status") or "") not in {"draft", "active"}:
            return {
                "success": False,
                "code": "AGENT_RUN_BLUEPRINT_NOT_ACTIVE",
                "error": "blueprint is no longer active",
            }
        if str(blueprint.get("compiled_approved_version_id") or "") != str(version.get("id") or ""):
            return {
                "success": False,
                "code": "AGENT_RUN_VERSION_STALE",
                "error": "compiled approved version is no longer current",
            }
        return None
    if not require_execution_mode_confirmation:
        return None
    if not input_payload.get("preview_mode") and str(metadata.get("execution_mode") or "").strip().lower() not in {
        "one_off",
        "manual",
        "scheduled",
    }:
        return {
            "success": False,
            "code": "AGENT_EXECUTION_MODE_REQUIRED",
            "error": "agent execution mode must be confirmed before a new run",
        }
    execution_mode = str(
        version.get("execution_mode") or metadata.get("execution_mode") or "manual"
    ).strip().lower()
    if input_payload.get("preview_mode") is True or execution_mode not in {"manual", "scheduled"}:
        return None
    if str(blueprint.get("status") or "") != "active":
        return {
            "success": False,
            "code": "AGENT_RUN_BLUEPRINT_NOT_ACTIVE",
            "error": "blueprint is no longer active",
        }
    if str(metadata.get("active_version_id") or "") != str(version.get("id") or ""):
        return {
            "success": False,
            "code": "AGENT_RUN_VERSION_STALE",
            "error": "pinned version is no longer active",
        }
    return None


def _validate_pinned_version(blueprint: dict[str, Any], version: dict[str, Any]) -> str:
    version_id = str(version.get("id") or "").strip()
    if not version_id:
        return "blueprint version id is required"
    if str(version.get("blueprint_id") or "").strip() not in {"", str(blueprint.get("id") or "").strip()}:
        return "blueprint version does not belong to this blueprint"
    compiled_state = str(version.get("compiled_state") or "legacy").strip()
    if compiled_state == "legacy":
        # Legacy versions are executable even when their historical DSL is
        # empty.  Candidate validation belongs to the compiled path and must
        # not turn valid legacy runs into uncontrolled rejections.
        return ""
    if str(os.getenv("COMPILED_SCRIPT_EXECUTE_ENABLED", "false")).lower() not in {"1", "true", "yes", "on"}:
        return "compiled script execution is disabled"
    if compiled_state not in {"approved", "active"}:
        return "compiled script version is not approved"
    from services.compiled_pilot_access import compiled_pilot_allowed
    if not compiled_pilot_allowed(str(blueprint.get("business_id") or ""), execute=True):
        return "compiled script execution is unavailable for this business"
    validation = validate_compiled_script_artifact(
        parse_json_field(version.get("compiled_artifact_json"), {})
    )
    if not validation.get("valid"):
        return "compiled script artifact hash or policy validation failed"
    return ""


def claim_next_agent_run(cursor: Any) -> dict[str, Any] | None:
    # Do not issue one broad UPDATE over every stale run. A live runner can hold
    # its row lock while invoking a provider; SKIP LOCKED lets this worker claim
    # another runnable item instead of waiting behind it.
    lease_token = str(uuid.uuid4())
    cursor.execute(
        """
        WITH stale_runs AS (
            SELECT id
            FROM agent_runs
            WHERE status = 'running'
              AND heartbeat_at < NOW() - INTERVAL '5 minutes'
            ORDER BY heartbeat_at ASC
            FOR UPDATE SKIP LOCKED
            LIMIT 50
        )
        UPDATE agent_runs run
        SET status = CASE WHEN run.attempt_count < run.max_attempts THEN 'retry_wait' ELSE 'failed' END,
            next_attempt_at = CASE WHEN run.attempt_count < run.max_attempts THEN NOW() ELSE NULL END,
            error_text = CASE
                WHEN run.attempt_count < run.max_attempts THEN 'worker heartbeat expired; retry scheduled'
                ELSE 'worker heartbeat expired; retry limit reached'
            END,
            completed_at = CASE WHEN run.attempt_count < run.max_attempts THEN NULL ELSE NOW() END,
            lease_token = NULL,
            updated_at = NOW()
        FROM stale_runs
        WHERE run.id = stale_runs.id
        RETURNING run.*
        """
    )
    expired = cursor.fetchall() if hasattr(cursor, "fetchall") else []
    for expired_run in expired:
        current = dict(expired_run)
        if str(current.get("status") or "") != "failed" or not current.get("billing_reservation_id"):
            continue
        cursor.execute(
            "SELECT reserved_credits FROM operatorcreditreservations WHERE id = %s",
            (current["billing_reservation_id"],),
        )
        reservation = cursor.fetchone() or {}
        current["reserved_credits"] = int(reservation.get("reserved_credits") or AGENT_RUN_ESTIMATED_CREDITS)
        finalize_agent_run_credits(cursor, run=current, actual_tokens=0)
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
            lease_token = %s,
            updated_at = NOW()
        FROM next_run
        WHERE r.id = next_run.id
        RETURNING r.*
        """,
        (lease_token,),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def heartbeat_agent_run(cursor: Any, *, run_id: str, lease_token: str) -> bool:
    """Extend a claim only when this worker still owns its fence."""
    cursor.execute(
        """
        UPDATE agent_runs
        SET heartbeat_at = NOW(), updated_at = NOW()
        WHERE id = %s AND status = 'running' AND lease_token = %s
        """,
        (run_id, lease_token),
    )
    return bool(getattr(cursor, "rowcount", 0))


def finish_agent_run_claim(cursor: Any, *, run_id: str, lease_token: str, status: str) -> bool:
    """Fence terminal status writes made by the queue worker itself.

    The legacy runner still owns its checkpoint writes.  This helper is used
    by the queue boundary so a recovered worker cannot overwrite a later
    claim's terminal state.
    """
    if status not in {"completed", "failed", "superseded", "rejected"}:
        return False
    cursor.execute(
        """
        UPDATE agent_runs
        SET heartbeat_at = NOW(), completed_at = COALESCE(completed_at, NOW()),
            lease_token = NULL, updated_at = NOW()
        WHERE id = %s AND status = %s AND lease_token = %s
        """,
        (run_id, status, lease_token),
    )
    return bool(getattr(cursor, "rowcount", 0))


def compiled_run_claim(run: dict[str, Any]) -> dict[str, Any] | None:
    """Read a compiled claim's immutable inputs in a short transaction only."""
    from database_manager import DatabaseManager

    database = DatabaseManager()
    try:
        cursor = database.conn.cursor()
        cursor.execute(
            """SELECT r.*, b.status AS blueprint_status, b.compiled_approved_version_id,
                      v.compiled_state, v.compiled_artifact_json, v.compiled_artifact_hash, v.compiled_preview_json,
                      v.compiled_approved_at, v.compiled_approved_by_user_id
               FROM agent_runs r
               JOIN agent_blueprint_versions v ON v.id=r.blueprint_version_id
               JOIN agent_blueprints b ON b.id=r.blueprint_id
               WHERE r.id=%s AND r.status='running' AND r.lease_token=%s
               FOR SHARE""",
            (str(run.get("id") or ""), str(run.get("lease_token") or "")),
        )
        row = cursor.fetchone()
        if not row:
            return {"error": "agent_run_lease_lost"}
        if str(row.get("compiled_state") or "legacy") == "legacy":
            return None
        if str(row.get("blueprint_status") or "") not in {"draft", "active"}:
            return {"error": "compiled_blueprint_not_active"}
        if str(row.get("compiled_approved_version_id") or "") != str(row.get("blueprint_version_id") or ""):
            return {"error": "compiled_version_not_current"}
        cursor.execute(
            """SELECT COALESCE(is_superadmin,FALSE) AS is_superadmin,
                      COALESCE(is_active,FALSE) AS is_active,
                      COALESCE(is_verified,FALSE) AS is_verified
               FROM users WHERE id=%s""",
            (row.get("created_by_user_id"),),
        )
        actor = cursor.fetchone() or {}
        if not bool(actor.get("is_active")) or not bool(actor.get("is_verified")):
            return {"error": "compiled_actor_account_not_active"}
        cursor.execute(
            """SELECT payload_json FROM agent_artifacts
               WHERE run_id=%s AND artifact_type='run_admission_audit'
               ORDER BY created_at DESC LIMIT 1""",
            (row.get("id"),),
        )
        admission_audit = cursor.fetchone() or {}
        admission_payload = parse_json_field(admission_audit.get("payload_json"), {})
        admission_actor = admission_payload.get("actor") if isinstance(admission_payload, dict) else {}
        if (
            not isinstance(admission_actor, dict)
            or str(admission_actor.get("user_id") or "") != str(row.get("created_by_user_id") or "")
            or str(admission_actor.get("session_kind") or "") != "standard"
            or bool(admission_actor.get("impersonating"))
        ):
            return {"error": "compiled_admission_context_invalid"}
        from core.auth_helpers import verify_business_access
        allowed, owner_id = verify_business_access(
            cursor,
            str(row.get("business_id") or ""),
            {"user_id": str(row.get("created_by_user_id") or ""), "is_superadmin": bool(actor.get("is_superadmin"))},
        )
        if not owner_id or not allowed:
            return {"error": "compiled_actor_access_revoked"}
        artifact = parse_json_field(row.get("compiled_artifact_json"), {})
        if str(row.get("compiled_state") or "") not in {"approved", "active"} or not row.get("compiled_approved_at") or not str(row.get("compiled_approved_by_user_id") or ""):
            return {"error": "compiled_version_not_approved"}
        validation = validate_compiled_script_artifact(artifact)
        if not validation.get("valid"):
            return {"error": "compiled_artifact_invalid"}
        preview = parse_json_field(row.get("compiled_preview_json"), {})
        artifact_hash = str(artifact.get("artifact_hash") or "")
        if (
            artifact_hash != str(row.get("compiled_artifact_hash") or "")
            or str((preview.get("result") or {}).get("artifact_hash") or "") != artifact_hash
            or preview.get("status") != "passed"
            or not str(preview.get("fixture_digest") or "")
            or not isinstance(preview.get("fixture_results"), list)
            or not preview.get("fixture_results")
            or not all(bool(item.get("passed")) for item in preview["fixture_results"] if isinstance(item, dict))
            or not any(item.get("source") == "user" for item in preview["fixture_results"] if isinstance(item, dict))
        ):
            return {"error": "compiled_preview_evidence_invalid"}
        from services.compiled_pilot_access import compiled_pilot_allowed
        if not compiled_pilot_allowed(str(row.get("business_id") or ""), execute=True):
            return {"error": "compiled_execution_not_allowed"}
        manifest = validation.get("manifest") or {}
        snapshot_id = str(row.get("input_snapshot_id") or "")
        snapshot_hash = str(row.get("input_snapshot_hash") or "")
        if "table_contract" in manifest and (not snapshot_id or not snapshot_hash):
            return {"error": "compiled_input_snapshot_required"}
        if "table_contract" in manifest:
            from services.compiled_input_snapshots import content_hash
            if content_hash(parse_json_field(row.get("input_json"), {})) != snapshot_hash:
                return {"error": "compiled_input_snapshot_hash_mismatch"}
        return {"run": dict(row), "artifact": artifact, "input": parse_json_field(row.get("input_json"), {})}
    finally:
        database.rollback_and_close()


def execute_claimed_compiled_agent_run(run: dict[str, Any]) -> dict[str, Any] | None:
    """Run pure compiled code outside PostgreSQL, then fence finalization.

    ``None`` means this is a legacy run and the caller must use the historical
    runner. The compiled sandbox receives only an immutable artifact and input.
    """
    prepared = compiled_run_claim(run)
    if prepared is None:
        return None
    run_id = str(run.get("id") or "")
    lease_token = str(run.get("lease_token") or "")
    if prepared.get("error"):
        return _finish_compiled_claim(run_id, lease_token, error=str(prepared["error"]))
    try:
        result = execute_in_attested_sandbox(prepared["artifact"], prepared["input"])
    except CompiledRuntimeUnavailable:
        error = sys.exception()
        return _finish_compiled_claim(run_id, lease_token, error=str(error), retryable=str(error) in {"compiled_script_runner_busy", "compiled_script_runner_timeout", "compiled_script_runner_unreachable"})
    except ValueError:
        error = sys.exception()
        return _finish_compiled_claim(run_id, lease_token, error=str(error))
    return _finish_compiled_claim(run_id, lease_token, result=result)


def _finish_compiled_claim(run_id: str, lease_token: str, *, result: dict[str, Any] | None = None, error: str = "", retryable: bool = False) -> dict[str, Any]:
    from database_manager import DatabaseManager

    database = DatabaseManager()
    try:
        cursor = database.conn.cursor()
        retry = retryable and result is None
        cursor.execute(
            """UPDATE agent_runs SET status=CASE WHEN %s AND attempt_count < max_attempts THEN 'retry_wait' ELSE %s END,
                    output_json=CASE WHEN %s::jsonb IS NULL THEN output_json ELSE %s::jsonb END,
                    error_text=%s, completed_at=CASE WHEN %s AND attempt_count < max_attempts THEN NULL ELSE NOW() END,
                    next_attempt_at=CASE WHEN %s THEN NOW() + INTERVAL '1 minute' ELSE NULL END,
                    heartbeat_at=NOW(), lease_token=NULL, updated_at=NOW()
               WHERE id=%s AND status='running' AND lease_token=%s RETURNING *""",
            (retry, "completed" if result is not None else "failed", json.dumps(result, ensure_ascii=False) if result is not None else None,
             json.dumps(result, ensure_ascii=False) if result is not None else None, error or None, retry, retry, run_id, lease_token),
        )
        current = cursor.fetchone()
        if not current:
            database.conn.rollback()
            return {"success": False, "code": "AGENT_RUN_LEASE_LOST", "run_id": run_id}
        current = dict(current)
        if str(current.get("status") or "") == "retry_wait":
            database.conn.commit()
            return {"success": False, "retry_scheduled": True, "run": current}
        if current.get("billing_reservation_id"):
            cursor.execute("SELECT reserved_credits FROM operatorcreditreservations WHERE id=%s", (current["billing_reservation_id"],))
            reservation = cursor.fetchone() or {}
            current["reserved_credits"] = int(reservation.get("reserved_credits") or AGENT_RUN_ESTIMATED_CREDITS)
        billing = finalize_agent_run_credits(cursor, run=current, actual_tokens=0)
        cursor.execute("UPDATE agent_runs SET output_json=COALESCE(output_json,'{}'::jsonb)||jsonb_build_object('run_billing',%s::jsonb) WHERE id=%s", (json.dumps(billing, ensure_ascii=False), run_id))
        database.conn.commit()
        current["run_billing"] = billing
        return {"success": result is not None, "run": current}
    except Exception:
        database.conn.rollback()
        raise
    finally:
        database.close()


def execute_claimed_agent_run(cursor: Any, run: dict[str, Any]) -> dict[str, Any]:
    run_id = str(run.get("id") or "")
    lease_token = str(run.get("lease_token") or "")
    if lease_token and not heartbeat_agent_run(cursor, run_id=run_id, lease_token=lease_token):
        return {
            "success": False,
            "code": "AGENT_RUN_LEASE_LOST",
            "error": "agent run lease is no longer owned by this worker",
            "run_id": run_id,
        }
    actor_id = str(run.get("created_by_user_id") or "")
    cursor.execute(
        "SELECT COALESCE(is_superadmin, FALSE) AS is_superadmin FROM users WHERE id = %s LIMIT 1",
        (actor_id,),
    )
    actor_row = cursor.fetchone() or {}
    user_data = {
        "user_id": actor_id,
        "id": actor_id,
        "is_superadmin": bool(actor_row.get("is_superadmin")),
    }
    runner = AgentBlueprintRunner(cursor)
    savepoint = "agent_run_execution"
    cursor.execute(f"SAVEPOINT {savepoint}")
    try:
        result = runner.execute_queued_run(run_id, user_data)
        current = result.get("run") if isinstance(result.get("run"), dict) else runner.load_run(run_id, user_data) or {}
    except Exception as exc:
        cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
        cursor.execute(f"RELEASE SAVEPOINT {savepoint}")
        _schedule_agent_run_retry(cursor, run, str(exc))
        return {"success": False, "error": str(exc), "run_id": run_id, "retry_scheduled": True}
    cursor.execute(f"RELEASE SAVEPOINT {savepoint}")

    if str(current.get("status") or "") == "failed" and _is_transient_error(str(current.get("error_text") or "")):
        _schedule_agent_run_retry(cursor, {**run, **current}, str(current.get("error_text") or "temporary agent run failure"))
        current = runner.load_run(run_id, user_data) or current

    if str(current.get("status") or "") in {"completed", "failed", "superseded", "rejected"}:
        if lease_token and not finish_agent_run_claim(
            cursor,
            run_id=run_id,
            lease_token=lease_token,
            status=str(current.get("status") or ""),
        ):
            return {
                "success": False,
                "code": "AGENT_RUN_LEASE_LOST",
                "error": "agent run completed after its worker lease was replaced",
                "run_id": run_id,
            }
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
