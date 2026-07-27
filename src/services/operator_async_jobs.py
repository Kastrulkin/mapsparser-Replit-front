from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any


JOB_STATUSES = {"queued", "running", "waiting_for_review", "completed", "failed", "cancelled"}
TERMINAL_JOB_STATUSES = {"completed", "failed", "cancelled"}
RETRYABLE_JOB_KINDS = {
    "content_plan_generate",
    "content_draft_generate",
    "finance_document_recognize",
    "finance_crm_sync",
    "diagnostics_retry",
}
CANCELLABLE_JOB_KINDS = {
    "content_plan_generate",
    "content_draft_generate",
    "finance_document_recognize",
    "finance_crm_sync",
}


def _row(cursor: Any, value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "keys"):
        return dict(value)
    columns = [item[0] for item in (getattr(cursor, "description", None) or [])]
    return {columns[index]: value[index] for index in range(min(len(columns), len(value)))}


def _json(value: Any, fallback: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return fallback
    return fallback


def _iso(value: Any) -> Any:
    return value.isoformat() if hasattr(value, "isoformat") else value


def _scope_allows(scope: dict[str, Any], business_id: str) -> bool:
    if scope.get("kind") == "platform":
        return True
    return business_id in {str(item) for item in scope.get("business_ids") or []}


def _public_job(row: dict[str, Any]) -> dict[str, Any]:
    status = str(row.get("status") or "queued")
    kind = str(row.get("kind") or "operator_job")
    return {
        "id": str(row.get("id") or ""),
        "action_id": str(row.get("action_id") or "") or None,
        "business_id": str(row.get("business_id") or "") or None,
        "kind": kind,
        "status": status,
        "progress": max(0, min(100, int(row.get("progress") or 0))),
        "stage": str(row.get("stage") or ""),
        "result": _json(row.get("result_json"), {}),
        "error": str(row.get("error_text") or "") or None,
        "attempt_count": int(row.get("attempt_count") or 0),
        "max_attempts": int(row.get("max_attempts") or 0),
        "started_at": _iso(row.get("created_at")),
        "updated_at": _iso(row.get("updated_at")),
        "completed_at": _iso(row.get("completed_at")),
        "terminal": status in TERMINAL_JOB_STATUSES,
        "available_actions": [
            *(["retry"] if status == "failed" and kind in RETRYABLE_JOB_KINDS else []),
            *(["cancel"] if status in {"queued", "running", "waiting_for_review"} and kind in CANCELLABLE_JOB_KINDS else []),
        ],
    }


def create_operator_async_job(
    cursor: Any,
    *,
    user_id: str,
    action_id: str | None,
    business_id: str,
    kind: str,
    payload: dict[str, Any],
    idempotency_key: str,
    stage: str,
    max_attempts: int = 3,
) -> dict[str, Any]:
    job_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO operator_async_jobs (
            id, action_id, user_id, business_id, kind, status, progress, stage,
            payload_json, idempotency_key, max_attempts, next_attempt_at
        )
        VALUES (%s, %s, %s, %s, %s, 'queued', 0, %s, %s::jsonb, %s, %s, NOW())
        ON CONFLICT (user_id, idempotency_key)
        DO UPDATE SET updated_at = operator_async_jobs.updated_at
        RETURNING *
        """,
        (
            job_id,
            action_id,
            user_id,
            business_id or None,
            kind,
            stage,
            json.dumps(payload, ensure_ascii=False, default=str),
            idempotency_key,
            max(1, min(10, int(max_attempts))),
        ),
    )
    return _public_job(_row(cursor, cursor.fetchone()))


def load_operator_async_job(
    cursor: Any,
    *,
    job_id: str,
    user_id: str,
    scope: dict[str, Any],
    is_superadmin: bool = False,
) -> dict[str, Any] | None:
    cursor.execute("SELECT * FROM operator_async_jobs WHERE id = %s", (job_id,))
    row = _row(cursor, cursor.fetchone())
    if not row:
        return None
    business_id = str(row.get("business_id") or "")
    owns_job = str(row.get("user_id") or "") == user_id
    if not owns_job and not (is_superadmin and scope.get("kind") == "platform"):
        return None
    if business_id and not _scope_allows(scope, business_id):
        return None
    return _public_job(row)


def list_operator_async_jobs(
    cursor: Any,
    *,
    user_id: str,
    scope: dict[str, Any],
    is_superadmin: bool = False,
    status: str = "",
    cursor_value: str = "",
    limit: int = 25,
) -> dict[str, Any]:
    clean_limit = max(1, min(100, int(limit)))
    clauses = ["1 = 1"]
    params: list[Any] = []
    if not (is_superadmin and scope.get("kind") == "platform"):
        clauses.append("job.user_id = %s")
        params.append(user_id)
    business_ids = [str(item) for item in scope.get("business_ids") or [] if str(item)]
    if scope.get("kind") != "platform":
        clauses.append("job.business_id = ANY(%s)")
        params.append(business_ids)
    if status in JOB_STATUSES:
        clauses.append("job.status = %s")
        params.append(status)
    if cursor_value:
        try:
            cursor_time = datetime.fromisoformat(cursor_value.replace("Z", "+00:00"))
        except ValueError:
            cursor_time = None
        if cursor_time:
            clauses.append("job.updated_at < %s")
            params.append(cursor_time)
    params.append(clean_limit + 1)
    cursor.execute(
        f"""
        SELECT job.*
        FROM operator_async_jobs job
        WHERE {' AND '.join(clauses)}
        ORDER BY job.updated_at DESC, job.id DESC
        LIMIT %s
        """,
        tuple(params),
    )
    rows = [_row(cursor, item) for item in (cursor.fetchall() or [])]
    has_more = len(rows) > clean_limit
    page = rows[:clean_limit]
    next_cursor = _iso(page[-1].get("updated_at")) if has_more and page else None
    counts = {key: 0 for key in JOB_STATUSES}
    for item in page:
        item_status = str(item.get("status") or "queued")
        counts[item_status] = counts.get(item_status, 0) + 1
    return {
        "scope": scope,
        "items": [_public_job(item) for item in page],
        "counts": counts,
        "cursor": next_cursor,
        "as_of": datetime.now(timezone.utc).isoformat(),
        "freshness": "live",
        "data_warnings": [],
        "available_actions": ["open", "retry", "cancel"],
        "filters": {"statuses": sorted(JOB_STATUSES)},
    }


def retry_operator_async_job(
    cursor: Any,
    *,
    job_id: str,
    user_id: str,
    scope: dict[str, Any],
    is_superadmin: bool = False,
) -> dict[str, Any] | None:
    cursor.execute(
        """
        SELECT job.*, action.external_effects, action.idempotency_key AS action_idempotency_key
        FROM operator_async_jobs job
        LEFT JOIN operatoractions action ON action.id = job.action_id
        WHERE job.id = %s
        FOR UPDATE OF job
        """,
        (job_id,),
    )
    row = _row(cursor, cursor.fetchone())
    if not row:
        return None
    business_id = str(row.get("business_id") or "")
    owns_job = str(row.get("user_id") or "") == user_id
    if not owns_job and not (is_superadmin and scope.get("kind") == "platform"):
        return None
    if business_id and not _scope_allows(scope, business_id):
        return None
    if str(row.get("status") or "") != "failed" or str(row.get("kind") or "") not in RETRYABLE_JOB_KINDS:
        return {**_public_job(row), "blocked_reason": "retry_not_available"}
    if bool(row.get("external_effects")) and not str(row.get("action_idempotency_key") or ""):
        return {**_public_job(row), "blocked_reason": "idempotency_key_required"}
    if int(row.get("attempt_count") or 0) >= int(row.get("max_attempts") or 0):
        return {**_public_job(row), "blocked_reason": "retry_limit_reached"}
    cursor.execute(
        """
        UPDATE operator_async_jobs
        SET status = 'queued', progress = 0, stage = 'Повтор поставлен в очередь',
            error_text = NULL, next_attempt_at = NOW(), completed_at = NULL, updated_at = NOW()
        WHERE id = %s
        RETURNING *
        """,
        (job_id,),
    )
    return _public_job(_row(cursor, cursor.fetchone()))


def cancel_operator_async_job(
    cursor: Any,
    *,
    job_id: str,
    user_id: str,
    scope: dict[str, Any],
    is_superadmin: bool = False,
) -> dict[str, Any] | None:
    cursor.execute("SELECT * FROM operator_async_jobs WHERE id = %s FOR UPDATE", (job_id,))
    row = _row(cursor, cursor.fetchone())
    if not row:
        return None
    business_id = str(row.get("business_id") or "")
    owns_job = str(row.get("user_id") or "") == user_id
    if not owns_job and not (is_superadmin and scope.get("kind") == "platform"):
        return None
    if business_id and not _scope_allows(scope, business_id):
        return None
    if str(row.get("status") or "") not in {"queued", "running", "waiting_for_review"} or str(row.get("kind") or "") not in CANCELLABLE_JOB_KINDS:
        return {**_public_job(row), "blocked_reason": "cancel_not_available"}
    cursor.execute(
        """
        UPDATE operator_async_jobs
        SET status = 'cancelled', progress = 100, stage = 'Остановлено',
            completed_at = NOW(), updated_at = NOW()
        WHERE id = %s
        RETURNING *
        """,
        (job_id,),
    )
    return _public_job(_row(cursor, cursor.fetchone()))


def claim_next_operator_async_job(cursor: Any) -> dict[str, Any] | None:
    cursor.execute(
        """
        SELECT *
        FROM operator_async_jobs
        WHERE status = 'queued'
          AND (next_attempt_at IS NULL OR next_attempt_at <= NOW())
        ORDER BY created_at
        FOR UPDATE SKIP LOCKED
        LIMIT 1
        """
    )
    row = _row(cursor, cursor.fetchone())
    if not row:
        return None
    cursor.execute(
        """
        UPDATE operator_async_jobs
        SET status = 'running', progress = GREATEST(progress, 5), stage = 'LocalOS начал работу',
            attempt_count = attempt_count + 1, heartbeat_at = NOW(), updated_at = NOW()
        WHERE id = %s
        RETURNING *
        """,
        (row.get("id"),),
    )
    claimed = _row(cursor, cursor.fetchone())
    claimed["payload_json"] = _json(claimed.get("payload_json"), {})
    return claimed


def update_operator_async_job(
    cursor: Any,
    *,
    job_id: str,
    status: str,
    progress: int,
    stage: str,
    result: dict[str, Any] | None = None,
    error: str = "",
) -> None:
    clean_status = status if status in JOB_STATUSES else "failed"
    terminal = clean_status in TERMINAL_JOB_STATUSES
    cursor.execute(
        """
        UPDATE operator_async_jobs
        SET status = %s, progress = %s, stage = %s, result_json = %s::jsonb,
            error_text = %s, heartbeat_at = NOW(), updated_at = NOW(),
            completed_at = CASE WHEN %s THEN NOW() ELSE completed_at END
        WHERE id = %s AND status = 'running'
        """,
        (
            clean_status,
            max(0, min(100, int(progress))),
            stage,
            json.dumps(result or {}, ensure_ascii=False, default=str),
            error or None,
            terminal,
            job_id,
        ),
    )


def process_next_operator_async_job() -> dict[str, Any] | None:
    """Claim and execute one LocalOS-owned durable job.

    Domain queues remain authoritative for parsing and agent runs. This worker only
    handles operations that previously ran synchronously inside the mobile request.
    """
    from database_manager import DatabaseManager

    claim_db = DatabaseManager()
    claimed: dict[str, Any] | None = None
    try:
        claimed = claim_next_operator_async_job(claim_db.conn.cursor())
        claim_db.conn.commit()
    except Exception:
        claim_db.conn.rollback()
        raise
    finally:
        claim_db.close()
    if not claimed:
        return None

    job_id = str(claimed.get("id") or "")
    kind = str(claimed.get("kind") or "")
    user_id = str(claimed.get("user_id") or "")
    business_id = str(claimed.get("business_id") or "")
    payload = claimed.get("payload_json") if isinstance(claimed.get("payload_json"), dict) else {}
    result: dict[str, Any]
    try:
        if kind == "content_plan_generate":
            from services.content_plan_service import create_generated_content_plan

            result = create_generated_content_plan(
                user_id,
                business_id,
                scope_type=str(payload.get("scope_type") or "business"),
                scope_target_id=str(payload.get("scope_target_id") or business_id),
                period_days=int(payload.get("period_days") or 30),
                density=str(payload.get("density") or "standard"),
                content_mix=payload.get("content_mix") if isinstance(payload.get("content_mix"), dict) else {},
            )
            status, stage, progress = "completed", "Контент-план готов", 100
        elif kind == "content_draft_generate":
            from services.content_plan_service import generate_draft_for_plan_item

            result = generate_draft_for_plan_item(
                user_id,
                str(payload.get("item_id") or ""),
                str(payload.get("language") or "ru"),
            )
            status, stage, progress = "completed", "Текст публикации готов", 100
        else:
            raise ValueError("Для этой операции ещё нет безопасного фонового исполнителя")
        finish_db = DatabaseManager()
        try:
            update_operator_async_job(
                finish_db.conn.cursor(),
                job_id=job_id,
                status=status,
                progress=progress,
                stage=stage,
                result=result,
            )
            finish_db.conn.commit()
        finally:
            finish_db.close()
        return {"id": job_id, "kind": kind, "status": status, "result": result}
    except Exception as exc:
        fail_db = DatabaseManager()
        try:
            update_operator_async_job(
                fail_db.conn.cursor(),
                job_id=job_id,
                status="failed",
                progress=100,
                stage="Нужно внимание",
                error=str(exc),
            )
            fail_db.conn.commit()
        finally:
            fail_db.close()
        return {"id": job_id, "kind": kind, "status": "failed", "error": str(exc)}
