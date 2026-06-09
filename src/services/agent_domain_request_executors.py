from __future__ import annotations

import json
from typing import Any, Dict, List

from core.agent_api_security import log_agent_action


APPROVED_EXECUTOR_REASON = "HUMAN_APPROVED_CONTROLLED_EXECUTOR"


def execute_approved_domain_requests(
    cursor: Any,
    *,
    run: Dict[str, Any],
    step: Dict[str, Any],
    orchestrator_result: Dict[str, Any],
    user_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Move capability-created domain requests into their post-approval execution state.

    Handlers create request records only. This layer runs after the blueprint human
    gate and records a controlled execution handoff without provider writes.
    """
    refs = _extract_refs(orchestrator_result)
    business_id = str(run.get("business_id") or "").strip()
    if not business_id:
        return _empty_result()
    user_id = str(user_data.get("user_id") or user_data.get("id") or "").strip()
    run_id = str(run.get("id") or "").strip()
    step_key = str(step.get("key") or "").strip()
    items: List[Dict[str, Any]] = []
    items.extend(_approve_sheet_requests(cursor, business_id, user_id, run_id, step_key, refs))
    items.extend(_approve_communication_requests(cursor, business_id, user_id, run_id, step_key, refs))
    items.extend(_approve_review_publish_requests(cursor, business_id, user_id, run_id, step_key, refs))
    items.extend(_approve_service_optimization_requests(cursor, business_id, user_id, run_id, step_key, refs))
    return {
        "executor": "agent_domain_request_executor_v1",
        "executed": len(items),
        "items": items,
        "external_dispatch_performed": False,
        "provider_writes_performed": False,
        "reason_code": APPROVED_EXECUTOR_REASON,
    }


def _empty_result() -> Dict[str, Any]:
    return {
        "executor": "agent_domain_request_executor_v1",
        "executed": 0,
        "items": [],
        "external_dispatch_performed": False,
        "provider_writes_performed": False,
        "reason_code": "NO_DOMAIN_REQUESTS",
    }


def _extract_refs(orchestrator_result: Dict[str, Any]) -> Dict[str, List[str]]:
    result = orchestrator_result.get("result") if isinstance(orchestrator_result.get("result"), dict) else {}
    refs = {
        "action_ids": [],
        "request_ids": [],
        "draft_ids": [],
        "review_ids": [],
    }
    candidates = {
        "action_ids": [orchestrator_result.get("action_id"), result.get("action_id")],
        "request_ids": [result.get("request_id")],
        "draft_ids": [result.get("draft_id")],
        "review_ids": [result.get("review_id")],
    }
    for key, values in candidates.items():
        for value in values:
            text = str(value or "").strip()
            if text and text not in refs[key]:
                refs[key].append(text)
    return refs


def _table_exists(cursor: Any, table_name: str) -> bool:
    try:
        cursor.execute("SELECT to_regclass(%s)", (table_name,))
        row = cursor.fetchone()
    except Exception:
        return False
    if not row:
        return False
    if isinstance(row, dict):
        return bool(row.get("to_regclass") or row.get("table_name"))
    if isinstance(row, (tuple, list)):
        return bool(row[0])
    return bool(row)


def _fetch_rows(cursor: Any, table_name: str, query: str, params: tuple[Any, ...], has_refs: bool) -> List[Dict[str, Any]]:
    if not has_refs or not _table_exists(cursor, table_name):
        return []
    cursor.execute(query, params)
    return [dict(row) for row in (cursor.fetchall() or [])]


def _approve_sheet_requests(cursor: Any, business_id: str, user_id: str, run_id: str, step_key: str, refs: Dict[str, List[str]]) -> List[Dict[str, Any]]:
    rows = _fetch_rows(
        cursor,
        "agent_sheet_operation_requests",
        """
        SELECT id, action_id, status, approval_state, apply_state, operation, sheet_name,
               provider_write_performed
        FROM agent_sheet_operation_requests
        WHERE business_id = %s AND (id = ANY(%s) OR action_id = ANY(%s))
        """,
        (business_id, refs.get("request_ids") or [], refs.get("action_ids") or []),
        bool(refs.get("request_ids") or refs.get("action_ids")),
    )
    items = []
    for row in rows:
        if bool(row.get("provider_write_performed")):
            continue
        cursor.execute(
            """
            UPDATE agent_sheet_operation_requests
            SET status = 'approved_for_execution',
                approval_state = 'approved',
                apply_state = 'approved_not_applied',
                updated_at = NOW()
            WHERE id = %s AND business_id = %s AND provider_write_performed = FALSE
            """,
            (row.get("id"), business_id),
        )
        ledger_id = _record_executor_ledger(
            cursor,
            business_id=business_id,
            user_id=user_id,
            run_id=run_id,
            step_key=step_key,
            request_id=str(row.get("id") or ""),
            action_id=str(row.get("action_id") or ""),
            capability="sheets.append_row_request",
            output_state="approved_not_applied",
            summary={"operation": row.get("operation"), "sheet_name": row.get("sheet_name")},
        )
        items.append(
            {
                "kind": "sheet_operation_request",
                "id": row.get("id"),
                "action_id": row.get("action_id"),
                "status": "approved_for_execution",
                "approval_state": "approved",
                "apply_state": "approved_not_applied",
                "ledger_id": ledger_id,
                "provider_write_performed": False,
            }
        )
    return items


def _approve_communication_requests(cursor: Any, business_id: str, user_id: str, run_id: str, step_key: str, refs: Dict[str, List[str]]) -> List[Dict[str, Any]]:
    rows = _fetch_rows(
        cursor,
        "agent_communication_requests",
        """
        SELECT id, action_id, capability, status, channel, recipient_count, delivery_state
        FROM agent_communication_requests
        WHERE business_id = %s AND (id = ANY(%s) OR action_id = ANY(%s))
        """,
        (business_id, refs.get("request_ids") or [], refs.get("action_ids") or []),
        bool(refs.get("request_ids") or refs.get("action_ids")),
    )
    items = []
    for row in rows:
        cursor.execute(
            """
            UPDATE agent_communication_requests
            SET status = 'approved_for_dispatch',
                delivery_state = 'queued_for_dispatch',
                updated_at = NOW()
            WHERE id = %s AND business_id = %s AND delivery_state <> 'dispatched'
            """,
            (row.get("id"), business_id),
        )
        capability = str(row.get("capability") or "communications.send_reminder")
        ledger_id = _record_executor_ledger(
            cursor,
            business_id=business_id,
            user_id=user_id,
            run_id=run_id,
            step_key=step_key,
            request_id=str(row.get("id") or ""),
            action_id=str(row.get("action_id") or ""),
            capability=capability,
            output_state="queued_for_dispatch",
            summary={"channel": row.get("channel"), "recipient_count": row.get("recipient_count")},
        )
        items.append(
            {
                "kind": "communication_request",
                "id": row.get("id"),
                "action_id": row.get("action_id"),
                "status": "approved_for_dispatch",
                "delivery_state": "queued_for_dispatch",
                "ledger_id": ledger_id,
                "provider_write_performed": False,
            }
        )
    return items


def _approve_review_publish_requests(cursor: Any, business_id: str, user_id: str, run_id: str, step_key: str, refs: Dict[str, List[str]]) -> List[Dict[str, Any]]:
    rows = _fetch_rows(
        cursor,
        "reviewreplydrafts",
        """
        SELECT id, review_id, status, source
        FROM reviewreplydrafts
        WHERE business_id = %s AND (id = ANY(%s) OR review_id = ANY(%s))
        """,
        (business_id, refs.get("draft_ids") or refs.get("request_ids") or [], refs.get("review_ids") or []),
        bool(refs.get("draft_ids") or refs.get("request_ids") or refs.get("review_ids")),
    )
    items = []
    for row in rows:
        cursor.execute(
            """
            UPDATE reviewreplydrafts
            SET status = 'approved_for_publish',
                updated_at = NOW()
            WHERE id = %s AND business_id = %s AND status IN ('publish_requested', 'generated', 'edited', 'pending_review')
            """,
            (row.get("id"), business_id),
        )
        ledger_id = _record_executor_ledger(
            cursor,
            business_id=business_id,
            user_id=user_id,
            run_id=run_id,
            step_key=step_key,
            request_id=str(row.get("id") or ""),
            action_id="",
            capability="reviews.reply.publish_request",
            output_state="approved_for_publish",
            summary={"review_id": row.get("review_id"), "source": row.get("source")},
        )
        items.append(
            {
                "kind": "review_publish_request",
                "id": row.get("id"),
                "review_id": row.get("review_id"),
                "status": "approved_for_publish",
                "ledger_id": ledger_id,
                "provider_write_performed": False,
            }
        )
    return items


def _approve_service_optimization_requests(cursor: Any, business_id: str, user_id: str, run_id: str, step_key: str, refs: Dict[str, List[str]]) -> List[Dict[str, Any]]:
    rows = _fetch_rows(
        cursor,
        "agent_service_optimization_requests",
        """
        SELECT id, action_id, status, service_count, apply_state
        FROM agent_service_optimization_requests
        WHERE business_id = %s AND (id = ANY(%s) OR action_id = ANY(%s))
        """,
        (business_id, refs.get("request_ids") or [], refs.get("action_ids") or []),
        bool(refs.get("request_ids") or refs.get("action_ids")),
    )
    items = []
    for row in rows:
        cursor.execute(
            """
            UPDATE agent_service_optimization_requests
            SET status = 'approved_for_apply',
                apply_state = 'apply_ready',
                updated_at = NOW()
            WHERE id = %s AND business_id = %s AND apply_state <> 'applied'
            """,
            (row.get("id"), business_id),
        )
        ledger_id = _record_executor_ledger(
            cursor,
            business_id=business_id,
            user_id=user_id,
            run_id=run_id,
            step_key=step_key,
            request_id=str(row.get("id") or ""),
            action_id=str(row.get("action_id") or ""),
            capability="services.optimize",
            output_state="apply_ready",
            summary={"service_count": row.get("service_count")},
        )
        items.append(
            {
                "kind": "service_optimization_request",
                "id": row.get("id"),
                "action_id": row.get("action_id"),
                "status": "approved_for_apply",
                "apply_state": "apply_ready",
                "ledger_id": ledger_id,
                "provider_write_performed": False,
            }
        )
    return items


def _record_executor_ledger(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    run_id: str,
    step_key: str,
    request_id: str,
    action_id: str,
    capability: str,
    output_state: str,
    summary: Dict[str, Any],
) -> str:
    return log_agent_action(
        cursor,
        agent_client_id=None,
        business_id=business_id,
        action_type="agent_domain_request_approved",
        capability=capability,
        required_scope=None,
        risk_level="high",
        input_summary=json.dumps({"request_id": request_id, "action_id": action_id}, ensure_ascii=False),
        output_summary=json.dumps({"state": output_state, **summary}, ensure_ascii=False),
        approval_id=None,
        status="approved_pending_provider_executor",
        reason_code=APPROVED_EXECUTOR_REASON,
        ip=None,
        user_agent=None,
        metadata={
            "run_id": run_id,
            "step_key": step_key,
            "request_id": request_id,
            "action_id": action_id,
            "approved_by_user_id": user_id,
            "external_dispatch_performed": False,
            "provider_write_performed": False,
            "executor": "agent_domain_request_executor_v1",
        },
    )
