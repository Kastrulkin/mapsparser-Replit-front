from __future__ import annotations

import hashlib
import json
import sys
import uuid
from typing import Any, Dict, Protocol

from core.agent_api_security import log_agent_action
from services.agent_google_sheets_adapter import GoogleSheetsAdapterError, load_google_sheets_append_adapter


class SheetAppendAdapter(Protocol):
    def append_row(self, request: Dict[str, Any]) -> Dict[str, Any]: ...
    def update_cells(self, request: Dict[str, Any]) -> Dict[str, Any]: ...


def sheet_request_hash(row: Dict[str, Any]) -> str:
    value = {
        "id": row.get("id"), "action_id": row.get("action_id"), "business_id": row.get("business_id"),
        "integration_id": row.get("integration_id"), "spreadsheet_id": row.get("spreadsheet_id"),
        "sheet_name": row.get("sheet_name"), "operation": row.get("operation"),
        "row_values_json": _decode_json(row.get("row_values_json"), []),
        "mapping_json": _decode_json(row.get("mapping_json"), {}),
        "source_event_json": _decode_json(row.get("source_event_json"), {}),
        "limits_json": _decode_json(row.get("limits_json"), {}),
        "bound_run_id": row.get("bound_run_id"), "bound_step_id": row.get("bound_step_id"),
        "bound_approval_id": row.get("bound_approval_id"),
    }
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def sheet_snapshot_hash(value: Dict[str, Any]) -> str:
    canonical = {
        "business_id": value.get("business_id"), "integration_id": value.get("integration_id"),
        "spreadsheet_id": value.get("spreadsheet_id"), "sheet_name": value.get("sheet_name"),
        "operation": value.get("operation"), "row_values": _decode_json(value.get("row_values_json", value.get("row_values")), []),
        "mapping": _decode_json(value.get("mapping_json", value.get("mapping")), {}),
        "source_event": _decode_json(value.get("source_event_json", value.get("source_event")), {}),
        "limits": _decode_json(value.get("limits_json", value.get("limits")), {}),
    }
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")).hexdigest()


def recover_expired_sheet_provider_attempts(cursor: Any) -> int:
    """Never resend an expired external write: retain it for reconciliation."""
    cursor.execute("""
        UPDATE agent_sheet_operation_requests
        SET apply_state='provider_reconciliation_required', provider_state='reconciliation_required',
            provider_lease_token=NULL, provider_lease_expires_at=NULL,
            error_text='provider lease expired; external write outcome is unknown',
            provider_result_json=jsonb_build_object('certainty','unknown','reason','provider_lease_expired'), updated_at=NOW()
        WHERE apply_state='provider_executing' AND provider_lease_expires_at < NOW()
    """)
    return int(cursor.rowcount or 0)


def hold_invalid_sheet_provider_requests(cursor: Any) -> int:
    """Hold legacy, revoked, or unbound records before any provider call."""
    cursor.execute("""
        UPDATE agent_sheet_operation_requests request
        SET apply_state='approval_invalid', provider_state='approval_invalid',
            error_text='provider request is not bound to a current approved run and exact request snapshot',
            provider_result_json=jsonb_build_object('certainty','not_sent','reason','approval_or_binding_invalid'), updated_at=NOW()
        WHERE request.apply_state='provider_request_queued' AND (
            request.bound_run_id IS NULL OR request.bound_step_id IS NULL OR request.bound_approval_id IS NULL OR request.request_hash IS NULL
            OR NOT EXISTS (SELECT 1 FROM agent_approvals approval WHERE approval.id=request.bound_approval_id AND approval.run_id=request.bound_run_id AND approval.status='approved' AND approval.approval_type='sheet_update' AND approval.payload_json ? 'sheet_write_snapshot')
            OR EXISTS (SELECT 1 FROM agent_runs run WHERE run.id=request.bound_run_id AND (LOWER(COALESCE(run.input_json->>'preview_mode','false')) IN ('true','1') OR LOWER(COALESCE(run.input_json->>'external_side_effects_allowed','true')) IN ('false','0')))
        )
    """)
    return int(cursor.rowcount or 0)


def claim_next_sheet_provider_request(cursor: Any, *, business_id: str = "", lease_seconds: int = 300) -> Dict[str, Any] | None:
    """Short committed claim protected by SKIP LOCKED and an approval fence."""
    hold_invalid_sheet_provider_requests(cursor)
    recover_expired_sheet_provider_attempts(cursor)
    lease_token = str(uuid.uuid4())
    cursor.execute("""
        WITH candidate AS (
            SELECT request.id, approval.payload_json->'sheet_write_snapshot'->>'hash' AS approval_snapshot_hash
            FROM agent_sheet_operation_requests request
            JOIN agent_approvals approval ON approval.id=request.bound_approval_id AND approval.run_id=request.bound_run_id
                AND approval.status='approved' AND approval.approval_type='sheet_update'
                AND approval.payload_json ? 'sheet_write_snapshot'
            JOIN agent_runs run ON run.id=request.bound_run_id AND run.status='waiting_provider' AND run.business_id=request.business_id
                AND LOWER(COALESCE(run.input_json->>'preview_mode','false')) NOT IN ('true','1')
                AND LOWER(COALESCE(run.input_json->>'external_side_effects_allowed','true')) NOT IN ('false','0')
            JOIN agent_blueprints blueprint ON blueprint.id=run.blueprint_id AND blueprint.status='active'
            JOIN agent_run_steps step ON step.id=request.bound_step_id AND step.run_id=run.id AND step.status='waiting_provider'
            WHERE request.status='provider_pending' AND request.approval_state='approved'
              AND request.apply_state='provider_request_queued' AND request.provider_write_performed=FALSE
              AND request.bound_run_id IS NOT NULL AND request.bound_step_id IS NOT NULL AND request.bound_approval_id IS NOT NULL AND request.request_hash IS NOT NULL
              AND (%s='' OR request.business_id=%s)
            ORDER BY request.updated_at ASC, request.created_at ASC FOR UPDATE SKIP LOCKED LIMIT 1
        )
        UPDATE agent_sheet_operation_requests request
        SET apply_state='provider_executing', provider_state='executing', provider_lease_token=%s,
            provider_lease_expires_at=NOW()+(%s*INTERVAL '1 second'), provider_attempt_count=provider_attempt_count+1, updated_at=NOW()
        FROM candidate WHERE request.id=candidate.id RETURNING request.*, candidate.approval_snapshot_hash
    """, (business_id, business_id, lease_token, max(30, min(int(lease_seconds), 1800))))
    row = cursor.fetchone()
    if not row:
        return None
    claimed = dict(row)
    if sheet_request_hash(claimed) != str(claimed.get("request_hash") or ""):
        _mark_reconciliation(cursor, claimed, "request payload changed after approval", certainty="not_sent")
        return None
    if sheet_snapshot_hash(claimed) != str(claimed.get("approval_snapshot_hash") or ""):
        _mark_reconciliation(cursor, claimed, "approved sheet snapshot no longer matches request", certainty="not_sent")
        return None
    return claimed


def process_next_sheet_provider_request(*, business_id: str = "", user_id: str = "", adapter: SheetAppendAdapter | None = None) -> Dict[str, Any] | None:
    """Call Google only after the claim connection is committed and closed."""
    from database_manager import DatabaseManager
    database = DatabaseManager()
    try:
        cursor = database.conn.cursor()
        claimed = claim_next_sheet_provider_request(cursor, business_id=business_id)
        database.conn.commit()
    except Exception:
        database.conn.rollback()
        raise
    finally:
        database.close()
    if not claimed:
        return None
    request = _request_payload(claimed)
    active_adapter = adapter
    adapter_error = ""
    if active_adapter is None:
        database = DatabaseManager()
        try:
            cursor = database.conn.cursor()
            active_adapter = load_google_sheets_append_adapter(cursor, business_id=str(claimed.get("business_id") or ""), integration_id=str(claimed.get("integration_id") or ""))
        except GoogleSheetsAdapterError:
            error = sys.exception()
            adapter_error = str(error or "provider adapter unavailable")
        finally:
            database.close()
        if adapter_error:
            return _finish_with_attention(claimed, request, user_id, adapter_error, state="provider_unavailable", certainty="not_sent")
    try:
        result = active_adapter.update_cells(request) if str(request.get("operation") or "append_row") == "update_cells" else active_adapter.append_row(request)
    except Exception:
        error = sys.exception()
        return _finish_with_attention(claimed, request, user_id, str(error or "provider request failed"))
    if not bool(result.get("success")):
        return _finish_with_attention(claimed, request, user_id, str(result.get("error") or "provider rejected request"), result)
    return _finish_applied(claimed, request, user_id, result)


def _finish_applied(claimed: Dict[str, Any], request: Dict[str, Any], user_id: str, provider_result: Dict[str, Any]) -> Dict[str, Any]:
    from database_manager import DatabaseManager
    database = DatabaseManager()
    try:
        cursor = database.conn.cursor()
        cursor.execute("""
            UPDATE agent_sheet_operation_requests SET status='applied', apply_state='applied', provider_state='applied', provider_write_performed=TRUE,
                provider_lease_token=NULL, provider_lease_expires_at=NULL, provider_result_json=%s::jsonb, error_text=NULL, updated_at=NOW()
            WHERE id=%s AND provider_lease_token=%s AND apply_state='provider_executing'
              AND provider_lease_expires_at >= NOW()
        """, (json.dumps(_safe_provider_result(provider_result), ensure_ascii=False), claimed.get("id"), claimed.get("provider_lease_token")))
        if not cursor.rowcount:
            database.conn.rollback()
            return {"success": False, "code": "SHEET_PROVIDER_LEASE_LOST", "request_id": claimed.get("id")}
        cursor.execute("""
            UPDATE agent_run_steps SET status='completed', completed_at=NOW(), output_json=COALESCE(output_json,'{}'::jsonb)||%s::jsonb
            WHERE id=%s AND run_id=%s AND status='waiting_provider'
        """, (json.dumps({"provider_result": _safe_provider_result(provider_result), "provider_write_performed": True}, ensure_ascii=False), claimed.get("bound_step_id"), claimed.get("bound_run_id")))
        cursor.execute("""
            UPDATE agent_runs run SET status='queued', lease_token=NULL, heartbeat_at=NOW(), next_attempt_at=NOW(), updated_at=NOW()
            WHERE run.id=%s AND run.status='waiting_provider'
              AND EXISTS (SELECT 1 FROM agent_run_steps step WHERE step.id=%s AND step.run_id=run.id AND step.status='completed')
        """, (claimed.get("bound_run_id"), claimed.get("bound_step_id")))
        _record_finish_ledger(cursor, claimed, request, user_id, "provider_applied", "applied", True, provider_result)
        database.conn.commit()
        return {"success": True, "request_id": claimed.get("id"), "apply_state": "applied", "provider_write_performed": True}
    except Exception:
        database.conn.rollback()
        raise
    finally:
        database.close()


def _finish_with_attention(claimed: Dict[str, Any], request: Dict[str, Any], user_id: str, error_text: str, provider_result: Dict[str, Any] | None = None, *, state: str = "provider_reconciliation_required", certainty: str = "unknown") -> Dict[str, Any]:
    from database_manager import DatabaseManager
    database = DatabaseManager()
    try:
        cursor = database.conn.cursor()
        if not _mark_reconciliation(cursor, claimed, error_text, provider_result=provider_result, state=state, certainty=certainty):
            database.conn.rollback()
            return {"success": False, "code": "SHEET_PROVIDER_LEASE_LOST", "request_id": claimed.get("id")}
        _record_finish_ledger(cursor, claimed, request, user_id, "provider_attention", "provider_reconciliation_required", False, provider_result or {"error": error_text, "certainty": "unknown"})
        database.conn.commit()
        return {"success": False, "request_id": claimed.get("id"), "apply_state": state, "provider_write_performed": False}
    except Exception:
        database.conn.rollback()
        raise
    finally:
        database.close()


def _mark_reconciliation(cursor: Any, row: Dict[str, Any], error_text: str, *, provider_result: Dict[str, Any] | None = None, certainty: str = "unknown", state: str = "provider_reconciliation_required") -> bool:
    result = _safe_provider_result(provider_result or {})
    result["certainty"] = result.get("certainty") or certainty
    token = str(row.get("provider_lease_token") or "")
    cursor.execute("""
        UPDATE agent_sheet_operation_requests SET apply_state=%s, provider_state=%s,
            provider_lease_token=NULL, provider_lease_expires_at=NULL, error_text=%s, provider_result_json=%s::jsonb, updated_at=NOW()
        WHERE id=%s AND (%s='' OR provider_lease_token=%s)
    """, (state, "unavailable" if state == "provider_unavailable" else "reconciliation_required", error_text[:2000], json.dumps(result, ensure_ascii=False), row.get("id"), token, token))
    return bool(cursor.rowcount)


def _record_finish_ledger(cursor: Any, row: Dict[str, Any], request: Dict[str, Any], user_id: str, status: str, state: str, write_performed: bool, result: Dict[str, Any]) -> None:
    log_agent_action(cursor, agent_client_id=None, business_id=str(row.get("business_id") or ""), action_type="agent_sheet_provider_executor", capability="sheets.append_row_request", required_scope=None, risk_level="high", input_summary=json.dumps({"request_id": row.get("id"), "action_id": row.get("action_id")}, ensure_ascii=False), output_summary=json.dumps({"state": state, "provider_write_performed": write_performed, "provider_result": _safe_provider_result(result)}, ensure_ascii=False), approval_id=str(row.get("bound_approval_id") or "") or None, status=status, reason_code="CONTROLLED_GOOGLE_SHEETS_PROVIDER_EXECUTOR", ip=None, user_agent=None, metadata={"approved_request_id": row.get("id"), "action_id": row.get("action_id"), "bound_run_id": row.get("bound_run_id"), "bound_step_id": row.get("bound_step_id"), "executed_by_user_id": user_id, "provider_write_performed": write_performed, "executor": "agent_sheet_provider_executor_v2"})


def _request_payload(row: Dict[str, Any]) -> Dict[str, Any]:
    mapping = _decode_json(row.get("mapping_json"), {})
    mapping = mapping if isinstance(mapping, dict) else {}
    return {"request_id": row.get("id"), "action_id": row.get("action_id"), "business_id": row.get("business_id"), "user_id": row.get("user_id"), "integration_id": row.get("integration_id"), "spreadsheet_id": row.get("spreadsheet_id"), "sheet_name": row.get("sheet_name") or "Sheet1", "operation": row.get("operation") or "append_row", "row_values": _decode_json(row.get("row_values_json"), []), "mapping": mapping, "range": mapping.get("range"), "values": mapping.get("values"), "expected_values": mapping.get("expected_values") if "expected_values" in mapping else None, "source_event": _decode_json(row.get("source_event_json"), {}), "limits": _decode_json(row.get("limits_json"), {})}


def _safe_provider_result(value: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(value or {})
    for key in ("access_token", "refresh_token", "token", "authorization", "credentials"):
        if key in result:
            result[key] = "[redacted]"
    return result


def _decode_json(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return fallback
    return fallback
