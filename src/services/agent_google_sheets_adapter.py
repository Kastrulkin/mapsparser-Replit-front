from __future__ import annotations

import json
import re
import sys
from typing import Any, Dict
from urllib.parse import quote

import requests

from auth_encryption import decrypt_auth_data


SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"


class GoogleSheetsAdapterError(Exception):
    pass


class GoogleSheetsAppendAdapter:
    def __init__(self, credentials: Dict[str, Any], *, timeout_seconds: int = 15):
        self.credentials = credentials
        self.timeout_seconds = max(3, min(int(timeout_seconds or 15), 60))

    def append_row(self, request: Dict[str, Any]) -> Dict[str, Any]:
        credentials = _refresh_credentials_if_needed(dict(self.credentials))
        token = str(credentials.get("token") or "").strip()
        if not token:
            raise GoogleSheetsAdapterError("Google Sheets credentials do not include access token.")
        spreadsheet_id = _normalize_spreadsheet_id(str(request.get("spreadsheet_id") or "").strip())
        if not spreadsheet_id:
            raise GoogleSheetsAdapterError("spreadsheet_id is required for Google Sheets append.")
        sheet_name = str(request.get("sheet_name") or "Sheet1").strip() or "Sheet1"
        row_values = request.get("row_values") if isinstance(request.get("row_values"), list) else []
        if not row_values:
            raise GoogleSheetsAdapterError("row_values are required for Google Sheets append.")
        range_name = quote(f"{sheet_name}!A1", safe="")
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{quote(spreadsheet_id, safe='')}/values/{range_name}:append"
        response = requests.post(
            url,
            params={"valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"},
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"values": [row_values]},
            timeout=self.timeout_seconds,
        )
        if response.status_code >= 400:
            raise GoogleSheetsAdapterError(f"Google Sheets append failed with HTTP {response.status_code}: {_response_excerpt(response)}")
        payload = response.json() if response.content else {}
        return {
            "success": True,
            "spreadsheet_id": spreadsheet_id,
            "sheet_name": sheet_name,
            "updated_range": payload.get("updates", {}).get("updatedRange"),
            "updated_rows": payload.get("updates", {}).get("updatedRows"),
            "updated_cells": payload.get("updates", {}).get("updatedCells"),
        }

    def read_rows(self, request: Dict[str, Any]) -> Dict[str, Any]:
        credentials = _refresh_credentials_if_needed(dict(self.credentials))
        token = str(credentials.get("token") or "").strip()
        if not token:
            raise GoogleSheetsAdapterError("Google Sheets credentials do not include access token.")
        spreadsheet_id = _normalize_spreadsheet_id(str(request.get("spreadsheet_id") or "").strip())
        if not spreadsheet_id:
            raise GoogleSheetsAdapterError("spreadsheet_id is required for Google Sheets read.")
        sheet_name = str(request.get("sheet_name") or "Sheet1").strip() or "Sheet1"
        range_value = str(request.get("range") or request.get("range_name") or "").strip()
        if not range_value:
            range_value = f"{sheet_name}!A1:Z"
        limit = max(1, min(int(request.get("limit") or 100), 500))
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{quote(spreadsheet_id, safe='')}/values/{quote(range_value, safe='')}"
        response = requests.get(
            url,
            params={"majorDimension": "ROWS"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=self.timeout_seconds,
        )
        if response.status_code >= 400:
            raise GoogleSheetsAdapterError(f"Google Sheets read failed with HTTP {response.status_code}: {_response_excerpt(response)}")
        payload = response.json() if response.content else {}
        values = payload.get("values") if isinstance(payload.get("values"), list) else []
        headers = _normalize_headers(values[0]) if values else []
        rows = []
        raw_rows = values[1:] if headers else values
        for index, values_row in enumerate(raw_rows[:limit], start=2 if headers else 1):
            if headers:
                rows.append(_values_to_row(headers, values_row, index))
            else:
                rows.append({"row_number": index, "values": values_row if isinstance(values_row, list) else []})
        return {
            "success": True,
            "spreadsheet_id": spreadsheet_id,
            "sheet_name": sheet_name,
            "range": payload.get("range") or range_value,
            "headers": headers,
            "rows": rows,
            "row_count": len(rows),
        }


def load_google_sheets_append_adapter(cursor: Any, *, business_id: str, integration_id: str = "") -> GoogleSheetsAppendAdapter:
    integration = _load_agent_integration(cursor, business_id=business_id, integration_id=integration_id)
    auth_ref = str(integration.get("auth_ref") or "").strip()
    if not auth_ref:
        raise GoogleSheetsAdapterError("Active Google Sheets integration must reference encrypted external account credentials.")
    credentials = _load_external_account_credentials(cursor, business_id=business_id, auth_ref=auth_ref)
    _validate_sheets_credentials(credentials)
    return GoogleSheetsAppendAdapter(credentials)


def load_google_sheets_read_adapter(cursor: Any, *, business_id: str, integration_id: str = "") -> GoogleSheetsAppendAdapter:
    return load_google_sheets_append_adapter(cursor, business_id=business_id, integration_id=integration_id)


def _normalize_spreadsheet_id(value: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        return ""
    match = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]+)", clean)
    if match:
        return match.group(1)
    return clean


def _normalize_headers(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    headers = []
    for index, item in enumerate(values, start=1):
        clean = str(item or "").strip()
        headers.append(clean or f"column_{index}")
    return headers


def _values_to_row(headers: list[str], values: Any, row_number: int) -> Dict[str, Any]:
    row_values = values if isinstance(values, list) else []
    row: Dict[str, Any] = {"row_number": row_number}
    for index, header in enumerate(headers):
        row[header] = row_values[index] if index < len(row_values) else ""
    return row


def _load_agent_integration(cursor: Any, *, business_id: str, integration_id: str) -> Dict[str, Any]:
    params: tuple[Any, ...]
    if integration_id:
        query = """
            SELECT id, business_id, provider, status, auth_ref, config_json
            FROM agent_integrations
            WHERE id = %s
              AND business_id = %s
              AND provider = 'google_sheets'
              AND status = 'active'
            LIMIT 1
        """
        params = (integration_id, business_id)
    else:
        query = """
            SELECT id, business_id, provider, status, auth_ref, config_json
            FROM agent_integrations
            WHERE business_id = %s
              AND provider = 'google_sheets'
              AND status = 'active'
            ORDER BY updated_at DESC, created_at DESC
            LIMIT 1
        """
        params = (business_id,)
    cursor.execute(query, params)
    row = cursor.fetchone()
    if not row:
        raise GoogleSheetsAdapterError("Active Google Sheets agent integration was not found.")
    return _row_to_dict(row, ["id", "business_id", "provider", "status", "auth_ref", "config_json"])


def _load_external_account_credentials(cursor: Any, *, business_id: str, auth_ref: str) -> Dict[str, Any]:
    columns = _table_columns(cursor, "externalbusinessaccounts")
    encrypted_column = ""
    if "auth_data_encrypted" in columns:
        encrypted_column = "auth_data_encrypted"
    elif "auth_data" in columns:
        encrypted_column = "auth_data"
    if not encrypted_column:
        raise GoogleSheetsAdapterError("externalbusinessaccounts does not expose encrypted auth data.")
    cursor.execute(
        f"""
        SELECT id, business_id, source, {encrypted_column}, is_active
        FROM externalbusinessaccounts
        WHERE id = %s
          AND business_id = %s
          AND is_active = TRUE
        LIMIT 1
        """,
        (auth_ref, business_id),
    )
    row = cursor.fetchone()
    if not row:
        raise GoogleSheetsAdapterError("Referenced external credentials were not found or are inactive.")
    data = _row_to_dict(row, ["id", "business_id", "source", encrypted_column, "is_active"])
    encrypted_auth = str(data.get(encrypted_column) or "").strip()
    if not encrypted_auth:
        raise GoogleSheetsAdapterError("Referenced external credentials are empty.")
    raw_auth = decrypt_auth_data(encrypted_auth) or ""
    if not raw_auth:
        raise GoogleSheetsAdapterError("Referenced external credentials could not be decrypted.")
    try:
        credentials = json.loads(raw_auth)
    except Exception:
        raise GoogleSheetsAdapterError("Referenced external credentials must be JSON.")
    if not isinstance(credentials, dict):
        raise GoogleSheetsAdapterError("Referenced external credentials must be a JSON object.")
    return credentials


def _validate_sheets_credentials(credentials: Dict[str, Any]) -> None:
    scopes = credentials.get("scopes") if isinstance(credentials.get("scopes"), list) else []
    scope_values = [str(scope) for scope in scopes]
    if SHEETS_SCOPE not in scope_values:
        raise GoogleSheetsAdapterError("Google credentials do not include Sheets append scope.")
    if not str(credentials.get("token") or credentials.get("refresh_token") or "").strip():
        raise GoogleSheetsAdapterError("Google credentials do not include token or refresh token.")


def _refresh_credentials_if_needed(credentials: Dict[str, Any]) -> Dict[str, Any]:
    if str(credentials.get("token") or "").strip():
        return credentials
    refresh_token = str(credentials.get("refresh_token") or "").strip()
    client_id = str(credentials.get("client_id") or "").strip()
    client_secret = str(credentials.get("client_secret") or "").strip()
    token_uri = str(credentials.get("token_uri") or "https://oauth2.googleapis.com/token").strip()
    if not (refresh_token and client_id and client_secret):
        return credentials
    response = requests.post(
        token_uri,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=15,
    )
    if response.status_code >= 400:
        raise GoogleSheetsAdapterError(f"Google token refresh failed with HTTP {response.status_code}: {_response_excerpt(response)}")
    payload = response.json()
    if payload.get("access_token"):
        credentials["token"] = payload.get("access_token")
    return credentials


def _table_columns(cursor: Any, table_name: str) -> set[str]:
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND lower(table_name) = %s
        """,
        (str(table_name).lower(),),
    )
    result: set[str] = set()
    for row in cursor.fetchall() or []:
        if hasattr(row, "get"):
            value = row.get("column_name")
        else:
            value = row[0] if row else ""
        if value:
            result.add(str(value).lower())
    return result


def _row_to_dict(row: Any, keys: list[str]) -> Dict[str, Any]:
    if hasattr(row, "get"):
        return {key: row.get(key) for key in keys}
    return {key: row[index] if index < len(row) else None for index, key in enumerate(keys)}


def _response_excerpt(response: requests.Response) -> str:
    try:
        return response.text[:500]
    except Exception:
        return str(sys.exc_info()[1])[:500]
