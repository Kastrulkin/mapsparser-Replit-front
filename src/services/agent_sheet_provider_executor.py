from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Protocol

from core.agent_api_security import log_agent_action
from services.agent_google_sheets_adapter import GoogleSheetsAdapterError, load_google_sheets_append_adapter


class SheetAppendAdapter(Protocol):
    def append_row(self, request: Dict[str, Any]) -> Dict[str, Any]:
        ...


def execute_queued_sheet_provider_requests(
    cursor: Any,
    *,
    business_id: str,
    user_id: str = "",
    limit: int = 20,
    adapter: SheetAppendAdapter | None = None,
) -> Dict[str, Any]:
    """Execute approved Google Sheets handoffs through an explicit provider boundary.

    The default production behavior is conservative: without an adapter, requests
    move to a visible provider-unavailable state and no external write happens.
    """
    rows = _load_queued_sheet_requests(cursor, business_id, limit)
    items: List[Dict[str, Any]] = []
    for row in rows:
        request = _request_payload(row)
        active_adapter = adapter
        if active_adapter is None:
            try:
                active_adapter = load_google_sheets_append_adapter(
                    cursor,
                    business_id=business_id,
                    integration_id=str(row.get("integration_id") or ""),
                )
            except GoogleSheetsAdapterError:
                items.append(_mark_provider_unavailable(cursor, row, request, user_id, str(sys.exc_info()[1] or "")))
                continue
        try:
            result = active_adapter.append_row(request)
        except Exception:
            items.append(_mark_provider_failed(cursor, row, request, user_id, str(sys.exc_info()[1] or "")))
            continue
        if bool(result.get("success")):
            items.append(_mark_provider_applied(cursor, row, request, result, user_id))
        else:
            items.append(_mark_provider_failed(cursor, row, request, user_id, str(result.get("error") or "provider_append_failed")))
    return {
        "executor": "agent_sheet_provider_executor_v1",
        "business_id": business_id,
        "processed": len(items),
        "items": items,
        "provider_writes_performed": any(bool(item.get("provider_write_performed")) for item in items),
    }


def _load_queued_sheet_requests(cursor: Any, business_id: str, limit: int) -> List[Dict[str, Any]]:
    cursor.execute(
        """
        SELECT id, action_id, business_id, user_id, integration_id, spreadsheet_id,
               sheet_name, operation, status, approval_state, apply_state,
               row_values_json, mapping_json, source_event_json, limits_json,
               provider_write_performed
        FROM agent_sheet_operation_requests
        WHERE business_id = %s
          AND status = 'approved_for_execution'
          AND approval_state = 'approved'
          AND apply_state = 'provider_request_queued'
          AND provider_write_performed = FALSE
        ORDER BY updated_at ASC, created_at ASC
        LIMIT %s
        """,
        (business_id, max(1, min(int(limit or 20), 100))),
    )
    return [dict(row) for row in (cursor.fetchall() or [])]


def _request_payload(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "request_id": row.get("id"),
        "action_id": row.get("action_id"),
        "business_id": row.get("business_id"),
        "user_id": row.get("user_id"),
        "integration_id": row.get("integration_id"),
        "spreadsheet_id": row.get("spreadsheet_id"),
        "sheet_name": row.get("sheet_name") or "Sheet1",
        "operation": row.get("operation") or "append_row",
        "row_values": _decode_json(row.get("row_values_json"), []),
        "mapping": _decode_json(row.get("mapping_json"), {}),
        "source_event": _decode_json(row.get("source_event_json"), {}),
        "limits": _decode_json(row.get("limits_json"), {}),
    }


def _mark_provider_unavailable(
    cursor: Any,
    row: Dict[str, Any],
    request: Dict[str, Any],
    user_id: str,
    reason: str = "Google Sheets provider adapter is not configured.",
) -> Dict[str, Any]:
    return _finish_request(
        cursor,
        row,
        request,
        user_id,
        status="provider_unavailable",
        apply_state="provider_unavailable",
        provider_write_performed=False,
        error_text=reason or "Google Sheets provider adapter is not configured.",
        provider_result={"success": False, "error_code": "GOOGLE_SHEETS_PROVIDER_NOT_CONFIGURED", "error": reason},
    )


def _mark_provider_failed(cursor: Any, row: Dict[str, Any], request: Dict[str, Any], user_id: str, error_text: str) -> Dict[str, Any]:
    return _finish_request(
        cursor,
        row,
        request,
        user_id,
        status="provider_failed",
        apply_state="provider_failed",
        provider_write_performed=False,
        error_text=error_text,
        provider_result={"success": False, "error": error_text},
    )


def _mark_provider_applied(
    cursor: Any,
    row: Dict[str, Any],
    request: Dict[str, Any],
    provider_result: Dict[str, Any],
    user_id: str,
) -> Dict[str, Any]:
    return _finish_request(
        cursor,
        row,
        request,
        user_id,
        status="applied",
        apply_state="applied",
        provider_write_performed=True,
        error_text="",
        provider_result=provider_result,
    )


def _finish_request(
    cursor: Any,
    row: Dict[str, Any],
    request: Dict[str, Any],
    user_id: str,
    *,
    status: str,
    apply_state: str,
    provider_write_performed: bool,
    error_text: str,
    provider_result: Dict[str, Any],
) -> Dict[str, Any]:
    cursor.execute(
        """
        UPDATE agent_sheet_operation_requests
        SET status = %s,
            apply_state = %s,
            provider_write_performed = %s,
            error_text = NULLIF(%s, ''),
            updated_at = NOW()
        WHERE id = %s
          AND business_id = %s
          AND apply_state = 'provider_request_queued'
        """,
        (status, apply_state, provider_write_performed, error_text, row.get("id"), row.get("business_id")),
    )
    ledger_id = log_agent_action(
        cursor,
        agent_client_id=None,
        business_id=str(row.get("business_id") or ""),
        action_type="agent_sheet_provider_executor",
        capability="sheets.append_row_request",
        required_scope=None,
        risk_level="high",
        input_summary=json.dumps(
            {
                "request_id": row.get("id"),
                "action_id": row.get("action_id"),
                "spreadsheet_id": row.get("spreadsheet_id"),
                "sheet_name": row.get("sheet_name"),
            },
            ensure_ascii=False,
        ),
        output_summary=json.dumps(
            {
                "state": apply_state,
                "provider_write_performed": provider_write_performed,
                "provider_result": _safe_provider_result(provider_result),
            },
            ensure_ascii=False,
        ),
        approval_id=None,
        status="provider_applied" if provider_write_performed else "provider_attention",
        reason_code="CONTROLLED_GOOGLE_SHEETS_PROVIDER_EXECUTOR",
        ip=None,
        user_agent=None,
        metadata={
            "approved_request_id": row.get("id"),
            "action_id": row.get("action_id"),
            "requested_by_user_id": row.get("user_id"),
            "executed_by_user_id": user_id,
            "provider_write_performed": provider_write_performed,
            "executor": "agent_sheet_provider_executor_v1",
        },
    )
    return {
        "kind": "sheet_operation_request",
        "id": row.get("id"),
        "action_id": row.get("action_id"),
        "status": status,
        "apply_state": apply_state,
        "provider_write_performed": provider_write_performed,
        "ledger_id": ledger_id,
        "error": error_text or "",
        "provider_result": _safe_provider_result(provider_result),
        "request": request,
    }


def _safe_provider_result(value: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(value or {})
    for secret_key in ("access_token", "refresh_token", "token", "authorization", "credentials"):
        if secret_key in result:
            result[secret_key] = "[redacted]"
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
