#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from typing import Any


def _json(value: dict[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def _row_to_dict(row: Any) -> dict[str, Any]:
    if not row:
        return {}
    if isinstance(row, dict):
        return dict(row)
    if hasattr(row, "keys"):
        return dict(row)
    return {}


def main() -> int:
    try:
        from database_manager import get_db_connection
        from services.agent_capability_handlers import build_capability_handlers
    except Exception as exc:
        _json({"success": False, "status": "blocked", "reason": f"imports_failed: {exc}"})
        return 2

    business_id = str(os.getenv("BUSINESS_ID") or "").strip()
    integration_id = str(os.getenv("GOOGLE_SHEETS_INTEGRATION_ID") or "").strip()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        query = """
            SELECT id, business_id, provider, status, display_name, auth_ref, config_json
            FROM agent_integrations
            WHERE provider = 'google_sheets'
              AND status = 'active'
        """
        params: list[Any] = []
        if business_id:
            query += " AND business_id = %s"
            params.append(business_id)
        if integration_id:
            query += " AND id = %s"
            params.append(integration_id)
        query += " ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST LIMIT 1"
        cur.execute(query, tuple(params))
        integration = _row_to_dict(cur.fetchone())
    finally:
        conn.close()

    if not integration:
        _json(
            {
                "success": False,
                "status": "blocked",
                "stage": "integration",
                "reason": "active_google_sheets_integration_not_found",
                "required": "Create or connect a Google Sheets integration for the business.",
            }
        )
        return 1

    config = integration.get("config_json") if isinstance(integration.get("config_json"), dict) else {}
    auth_ref = str(integration.get("auth_ref") or "").strip()
    if not auth_ref:
        _json(
            {
                "success": False,
                "status": "blocked",
                "stage": "oauth_binding",
                "business_id": integration.get("business_id"),
                "integration_id": integration.get("id"),
                "reason": "google_sheets_integration_has_no_auth_ref",
                "required": "Reconnect Google with Sheets scope or save the integration after OAuth so auth_ref is bound.",
            }
        )
        return 1

    spreadsheet_id = str(os.getenv("SPREADSHEET_ID") or config.get("spreadsheet_id") or "").strip()
    sheet_name = str(os.getenv("SHEET_NAME") or config.get("sheet_name") or "Sheet1").strip() or "Sheet1"
    if not spreadsheet_id:
        _json(
            {
                "success": False,
                "status": "blocked",
                "stage": "integration_config",
                "business_id": integration.get("business_id"),
                "integration_id": integration.get("id"),
                "has_auth_ref": True,
                "reason": "spreadsheet_id_missing",
            }
        )
        return 1

    result = build_capability_handlers()["google_sheets.read_rows"](
        {
            "tenant_id": str(integration.get("business_id") or ""),
            "payload": {
                "integration_id": str(integration.get("id") or ""),
                "spreadsheet_id": spreadsheet_id,
                "sheet_name": sheet_name,
                "limit": int(os.getenv("LIMIT") or "5"),
            },
        },
        {"user_id": os.getenv("USER_ID") or "smoke-google-sheets-reference-agent"},
    )["result"]

    provider_read = bool(result.get("provider_read_performed"))
    status = str(result.get("status") or "")
    _json(
        {
            "success": provider_read and status == "read_completed",
            "status": "pass" if provider_read and status == "read_completed" else "blocked",
            "scenario": "google_sheets_reference_agent_read_rows",
            "stages": {
                "google_sheets": True,
                "oauth_binding": bool(auth_ref),
                "integration": True,
                "capability_read": provider_read,
                "artifact_ready_input": provider_read,
                "approval_stop_required": True,
            },
            "business_id": integration.get("business_id"),
            "integration_id": integration.get("id"),
            "sheet_name": sheet_name,
            "result_status": status,
            "provider_error": result.get("provider_error"),
            "provider_error_message": result.get("provider_error_message"),
            "next_action": result.get("next_action"),
            "row_count": result.get("count"),
        }
    )
    return 0 if provider_read and status == "read_completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
