from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


TERMINAL_STATUSES = {"completed", "failed", "cancelled", "superseded", "rejected"}


def _row(cursor: Any, value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "keys"):
        return dict(value)
    columns = [item[0] for item in (getattr(cursor, "description", None) or [])]
    return {columns[index]: value[index] for index in range(min(len(columns), len(value)))}


def _json(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return {}
    return {}


def _allowed(scope: dict[str, Any], business_id: str) -> bool:
    if scope.get("kind") == "platform":
        return True
    return business_id in {str(item) for item in scope.get("business_ids") or []}


def _normalize_status(status: str) -> str:
    value = str(status or "").strip().lower()
    if value in {"pending", "pending_approval", "preview", "queued", "retrying"}:
        return "queued"
    if value in {"processing", "running", "executing", "in_progress"}:
        return "running"
    if value in {"captcha_required", "waiting_for_approval", "approval_required", "needs_review"}:
        return "waiting_for_review"
    if value in {"done", "success", "succeeded", "published", "manual_published"}:
        return "completed"
    if value in {"error", "stuck", "dead_letter"}:
        return "failed"
    return value or "queued"


def _progress(status: str, completed_steps: int = 0, total_steps: int = 0) -> int | None:
    if status == "completed":
        return 100
    if status in {"failed", "cancelled"}:
        return 100
    if total_steps > 0:
        return max(5, min(95, round((completed_steps / total_steps) * 100)))
    if status == "queued":
        return 0
    return None


def _payload(
    *,
    job_id: str,
    kind: str,
    status: str,
    stage: str,
    business_id: str,
    result: Any = None,
    error: str = "",
    started_at: Any = None,
    updated_at: Any = None,
    completed_steps: int = 0,
    total_steps: int = 0,
) -> dict[str, Any]:
    normalized = _normalize_status(status)
    return {
        "id": job_id,
        "kind": kind,
        "business_id": business_id or None,
        "status": normalized,
        "progress": _progress(normalized, completed_steps, total_steps),
        "stage": stage,
        "result": result or {},
        "error": error or None,
        "started_at": started_at.isoformat() if hasattr(started_at, "isoformat") else started_at,
        "updated_at": updated_at.isoformat() if hasattr(updated_at, "isoformat") else updated_at,
        "terminal": normalized in TERMINAL_STATUSES,
    }


def load_mobile_job(
    cursor: Any,
    *,
    job_id: str,
    user_id: str,
    scope: dict[str, Any],
) -> dict[str, Any] | None:
    cursor.execute(
        """
        SELECT id, business_id, capability, status, result_json, created_at, updated_at,
               expires_at, user_id
        FROM operatoractions
        WHERE id = %s AND user_id = %s
        LIMIT 1
        """,
        (job_id, user_id),
    )
    action = _row(cursor, cursor.fetchone())
    if action:
        business_id = str(action.get("business_id") or "")
        if business_id and not _allowed(scope, business_id):
            return None
        status = str(action.get("status") or "")
        expires_at = action.get("expires_at")
        if status not in {"completed", "failed", "cancelled"} and expires_at and expires_at < datetime.now(timezone.utc):
            status = "cancelled"
        return _payload(
            job_id=job_id,
            kind="operator_action",
            status=status,
            stage="Результат готов" if _normalize_status(status) == "completed" else "Ждёт подтверждения",
            business_id=business_id,
            result=_json(action.get("result_json")),
            started_at=action.get("created_at"),
            updated_at=action.get("updated_at"),
        )

    cursor.execute(
        """
        SELECT id, business_id, status, task_type, source, error_message, captcha_required,
               created_at, updated_at
        FROM parsequeue
        WHERE id = %s
        LIMIT 1
        """,
        (job_id,),
    )
    parse_job = _row(cursor, cursor.fetchone())
    if parse_job:
        business_id = str(parse_job.get("business_id") or "")
        if not _allowed(scope, business_id):
            return None
        status = "waiting_for_review" if bool(parse_job.get("captcha_required")) else str(parse_job.get("status") or "")
        source = str(parse_job.get("source") or "карт")
        return _payload(
            job_id=job_id,
            kind="card_refresh",
            status=status,
            stage=f"Обновляем данные: {source}",
            business_id=business_id,
            error=str(parse_job.get("error_message") or ""),
            started_at=parse_job.get("created_at"),
            updated_at=parse_job.get("updated_at"),
        )

    cursor.execute(
        """
        SELECT run.id, run.business_id, run.status, run.output_json, run.error_text,
               run.started_at, run.updated_at,
               COUNT(step.id) AS total_steps,
               COUNT(step.id) FILTER (WHERE step.status IN ('completed', 'success', 'succeeded')) AS completed_steps
        FROM agent_runs run
        LEFT JOIN agent_run_steps step ON step.run_id = run.id
        WHERE run.id = %s
        GROUP BY run.id
        LIMIT 1
        """,
        (job_id,),
    )
    agent_run = _row(cursor, cursor.fetchone())
    if agent_run:
        business_id = str(agent_run.get("business_id") or "")
        if not _allowed(scope, business_id):
            return None
        return _payload(
            job_id=job_id,
            kind="agent_run",
            status=str(agent_run.get("status") or ""),
            stage="ИИ-сотрудник выполняет задачу",
            business_id=business_id,
            result=_json(agent_run.get("output_json")),
            error=str(agent_run.get("error_text") or ""),
            started_at=agent_run.get("started_at"),
            updated_at=agent_run.get("updated_at"),
            completed_steps=int(agent_run.get("completed_steps") or 0),
            total_steps=int(agent_run.get("total_steps") or 0),
        )
    return None
