from __future__ import annotations

import hashlib
import json
import re
import sys
from typing import Any, Dict
from urllib.parse import quote

import requests

from auth_encryption import decrypt_auth_data


SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
GOOGLE_SHEETS_EXTERNAL_ACCOUNT_SOURCES = ("google_sheets", "google_business")


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
        if len(row_values) > 100:
            raise GoogleSheetsAdapterError("Google Sheets changes are limited to 100 cells per approval.")
        if _contains_formula(row_values):
            raise GoogleSheetsAdapterError("Writing formulas is not allowed.")
        range_name = quote(f"{sheet_name}!A1", safe="")
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{quote(spreadsheet_id, safe='')}/values/{range_name}:append"
        request_kwargs = {
            "params": {"valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"},
            "headers": {"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            "json": {"values": [row_values]},
            "timeout": self.timeout_seconds,
        }
        response = requests.post(url, **request_kwargs)
        response = self._retry_with_refreshed_token_on_unauthorized("post", url, request_kwargs, response, credentials)
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
            "operation_hash": _operation_hash(request),
        }

    def preview_update_cells(self, request: Dict[str, Any]) -> Dict[str, Any]:
        spreadsheet_id = _normalize_spreadsheet_id(str(request.get("spreadsheet_id") or "").strip())
        range_value = str(request.get("range") or request.get("range_name") or "").strip()
        values = request.get("values") if isinstance(request.get("values"), list) else []
        expected_values = request.get("expected_values") if isinstance(request.get("expected_values"), list) else []
        if not spreadsheet_id or not range_value:
            raise GoogleSheetsAdapterError("spreadsheet_id and range are required for Google Sheets update.")
        cell_count = _cell_count(values)
        if cell_count < 1 or cell_count > 100:
            raise GoogleSheetsAdapterError("Google Sheets changes must contain between 1 and 100 cells.")
        if _contains_formula(values):
            raise GoogleSheetsAdapterError("Writing formulas is not allowed.")
        current_values = self.read_range_values(spreadsheet_id, range_value)
        if _contains_formula(current_values):
            raise GoogleSheetsAdapterError("Existing formulas cannot be overwritten.")
        if expected_values and _normalized_matrix(current_values) != _normalized_matrix(expected_values):
            raise GoogleSheetsAdapterError("GOOGLE_SHEETS_VALUES_CHANGED")
        return {
            "success": True,
            "spreadsheet_id": spreadsheet_id,
            "range": range_value,
            "before": current_values,
            "after": values,
            "cell_count": cell_count,
            "operation_hash": _operation_hash(request),
        }

    def update_cells(self, request: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(request.get("expected_values"), list):
            raise GoogleSheetsAdapterError("expected_values are required for conflict-safe Google Sheets update.")
        preview = self.preview_update_cells(request)
        credentials = _refresh_credentials_if_needed(dict(self.credentials))
        token = str(credentials.get("token") or "").strip()
        if not token:
            raise GoogleSheetsAdapterError("Google Sheets credentials do not include access token.")
        spreadsheet_id = str(preview.get("spreadsheet_id") or "")
        range_value = str(preview.get("range") or "")
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{quote(spreadsheet_id, safe='')}/values/{quote(range_value, safe='')}"
        request_kwargs = {
            "params": {"valueInputOption": "USER_ENTERED"},
            "headers": {"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            "json": {"range": range_value, "majorDimension": "ROWS", "values": request.get("values")},
            "timeout": self.timeout_seconds,
        }
        response = requests.put(url, **request_kwargs)
        response = self._retry_with_refreshed_token_on_unauthorized("put", url, request_kwargs, response, credentials)
        if response.status_code >= 400:
            raise GoogleSheetsAdapterError(f"Google Sheets update failed with HTTP {response.status_code}: {_response_excerpt(response)}")
        payload = response.json() if response.content else {}
        return {
            **preview,
            "success": True,
            "updated_range": payload.get("updatedRange") or range_value,
            "updated_rows": payload.get("updatedRows"),
            "updated_cells": payload.get("updatedCells"),
        }

    def read_range_values(self, spreadsheet_id: str, range_value: str) -> list[list[Any]]:
        credentials = _refresh_credentials_if_needed(dict(self.credentials))
        token = str(credentials.get("token") or "").strip()
        if not token:
            raise GoogleSheetsAdapterError("Google Sheets credentials do not include access token.")
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{quote(spreadsheet_id, safe='')}/values/{quote(range_value, safe='')}"
        request_kwargs = {
            "params": {"majorDimension": "ROWS", "valueRenderOption": "FORMULA"},
            "headers": {"Authorization": f"Bearer {token}"},
            "timeout": self.timeout_seconds,
        }
        response = requests.get(url, **request_kwargs)
        response = self._retry_with_refreshed_token_on_unauthorized("get", url, request_kwargs, response, credentials)
        if response.status_code >= 400:
            raise GoogleSheetsAdapterError(f"Google Sheets read failed with HTTP {response.status_code}: {_response_excerpt(response)}")
        payload = response.json() if response.content else {}
        values = payload.get("values") if isinstance(payload.get("values"), list) else []
        return [row if isinstance(row, list) else [] for row in values]

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
        requested_range = bool(range_value)
        if not range_value:
            range_value = f"{sheet_name}!A1:Z"
        limit = max(1, min(int(request.get("limit") or 100), 500))
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{quote(spreadsheet_id, safe='')}/values/{quote(range_value, safe='')}"
        request_kwargs = {
            "params": {"majorDimension": "ROWS"},
            "headers": {"Authorization": f"Bearer {token}"},
            "timeout": self.timeout_seconds,
        }
        response = requests.get(url, **request_kwargs)
        response = self._retry_with_refreshed_token_on_unauthorized("get", url, request_kwargs, response, credentials)
        if response.status_code >= 400 and not requested_range and sheet_name == "Sheet1" and _is_unable_to_parse_range_response(response):
            fallback_sheet_name = self._load_first_sheet_name(spreadsheet_id, credentials, request_kwargs)
            if fallback_sheet_name and fallback_sheet_name != sheet_name:
                sheet_name = fallback_sheet_name
                range_value = f"{sheet_name}!A1:Z"
                url = f"https://sheets.googleapis.com/v4/spreadsheets/{quote(spreadsheet_id, safe='')}/values/{quote(range_value, safe='')}"
                response = requests.get(url, **request_kwargs)
                response = self._retry_with_refreshed_token_on_unauthorized("get", url, request_kwargs, response, credentials)
        if response.status_code >= 400:
            raise GoogleSheetsAdapterError(f"Google Sheets read failed with HTTP {response.status_code}: {_response_excerpt(response)}")
        payload = response.json() if response.content else {}
        values = payload.get("values") if isinstance(payload.get("values"), list) else []
        headers = _normalize_headers(values[0]) if values else []
        all_rows = []
        raw_rows = values[1:] if headers else values
        for index, values_row in enumerate(raw_rows, start=2 if headers else 1):
            if headers:
                all_rows.append(_values_to_row(headers, values_row, index))
            else:
                all_rows.append({"row_number": index, "values": values_row if isinstance(values_row, list) else []})
        search_terms = [
            str(item or "").strip().casefold()
            for item in request.get("search_terms", [])
            if str(item or "").strip()
        ] if isinstance(request.get("search_terms"), list) else []
        matched_rows = all_rows
        if search_terms:
            matched_rows = [
                row
                for row in all_rows
                if any(term in json.dumps(row, ensure_ascii=False).casefold() for term in search_terms)
            ]
        rows = matched_rows[:limit]
        return {
            "success": True,
            "spreadsheet_id": spreadsheet_id,
            "sheet_name": sheet_name,
            "range": payload.get("range") or range_value,
            "headers": headers,
            "rows": rows,
            "row_count": len(rows),
            "search_applied": bool(search_terms),
        }

    def _load_first_sheet_name(
        self,
        spreadsheet_id: str,
        credentials: Dict[str, Any],
        base_request_kwargs: Dict[str, Any],
    ) -> str:
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{quote(spreadsheet_id, safe='')}"
        request_kwargs = {
            "params": {"fields": "sheets.properties.title"},
            "headers": dict(base_request_kwargs.get("headers") or {}),
            "timeout": self.timeout_seconds,
        }
        response = requests.get(url, **request_kwargs)
        response = self._retry_with_refreshed_token_on_unauthorized("get", url, request_kwargs, response, credentials)
        if response.status_code >= 400:
            return ""
        payload = response.json() if response.content else {}
        sheets = payload.get("sheets") if isinstance(payload.get("sheets"), list) else []
        for sheet in sheets:
            if not isinstance(sheet, dict):
                continue
            properties = sheet.get("properties") if isinstance(sheet.get("properties"), dict) else {}
            title = str(properties.get("title") or "").strip()
            if title:
                return title
        return ""

    def _retry_with_refreshed_token_on_unauthorized(
        self,
        method: str,
        url: str,
        request_kwargs: Dict[str, Any],
        response: requests.Response,
        credentials: Dict[str, Any],
    ) -> requests.Response:
        if response.status_code != 401:
            return response
        refreshed_credentials = _refresh_credentials(dict(credentials), force=True)
        refreshed_token = str(refreshed_credentials.get("token") or "").strip()
        current_token = str(credentials.get("token") or "").strip()
        if not refreshed_token or refreshed_token == current_token:
            return response
        refreshed_kwargs = dict(request_kwargs)
        refreshed_headers = dict(refreshed_kwargs.get("headers") or {})
        refreshed_headers["Authorization"] = f"Bearer {refreshed_token}"
        refreshed_kwargs["headers"] = refreshed_headers
        if method == "post":
            return requests.post(url, **refreshed_kwargs)
        if method == "put":
            return requests.put(url, **refreshed_kwargs)
        return requests.get(url, **refreshed_kwargs)


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


def _cell_count(values: Any) -> int:
    if not isinstance(values, list):
        return 0
    return sum(len(row) if isinstance(row, list) else 0 for row in values)


def _contains_formula(values: Any) -> bool:
    if not isinstance(values, list):
        return False
    for item in values:
        if isinstance(item, list):
            if _contains_formula(item):
                return True
        elif isinstance(item, str) and item.lstrip().startswith("="):
            return True
    return False


def _normalized_matrix(values: Any) -> list[list[Any]]:
    if not isinstance(values, list):
        return []
    return [list(row) if isinstance(row, list) else [row] for row in values]


def _operation_hash(request: Dict[str, Any]) -> str:
    payload = {
        "spreadsheet_id": _normalize_spreadsheet_id(str(request.get("spreadsheet_id") or "")),
        "sheet_name": str(request.get("sheet_name") or ""),
        "range": str(request.get("range") or request.get("range_name") or ""),
        "operation": str(request.get("operation") or "append_row"),
        "row_values": request.get("row_values") if isinstance(request.get("row_values"), list) else [],
        "values": request.get("values") if isinstance(request.get("values"), list) else [],
        "expected_values": request.get("expected_values") if isinstance(request.get("expected_values"), list) else [],
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


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
        fallback = _load_google_sheets_external_account_integration(
            cursor,
            business_id=business_id,
            preferred_account_id=integration_id,
        )
        if fallback:
            return fallback
        raise GoogleSheetsAdapterError("Active Google Sheets agent integration was not found.")
    return _row_to_dict(row, ["id", "business_id", "provider", "status", "auth_ref", "config_json"])


def _load_google_sheets_external_account_integration(
    cursor: Any,
    *,
    business_id: str,
    preferred_account_id: str,
) -> Dict[str, Any] | None:
    query = """
        SELECT id, business_id, source, display_name
        FROM externalbusinessaccounts
        WHERE business_id = %s
          AND is_active = TRUE
          AND source IN ('google_sheets', 'google_business')
        ORDER BY CASE WHEN source = 'google_sheets' THEN 0 ELSE 1 END, updated_at DESC
        LIMIT 1
    """
    params: tuple[Any, ...] = (business_id,)
    if preferred_account_id:
        query = """
            SELECT id, business_id, source, display_name
            FROM externalbusinessaccounts
            WHERE id = %s
              AND business_id = %s
              AND is_active = TRUE
              AND source IN ('google_sheets', 'google_business')
            LIMIT 1
        """
        params = (preferred_account_id, business_id)
    try:
        cursor.execute(query, params)
        row = cursor.fetchone()
    except Exception:
        row = None
    if not row and preferred_account_id:
        try:
            cursor.execute(
                """
                SELECT id, business_id, source, display_name
                FROM externalbusinessaccounts
                WHERE business_id = %s
                  AND is_active = TRUE
                  AND source IN ('google_sheets', 'google_business')
                ORDER BY CASE WHEN source = 'google_sheets' THEN 0 ELSE 1 END, updated_at DESC
                LIMIT 1
                """,
                (business_id,),
            )
            row = cursor.fetchone()
        except Exception:
            row = None
    if not row:
        return None
    item = _row_to_dict(row, ["id", "business_id", "source", "display_name"])
    account_id = str(item.get("id") or "").strip()
    source = str(item.get("source") or "").strip()
    if not account_id or source not in GOOGLE_SHEETS_EXTERNAL_ACCOUNT_SOURCES:
        return None
    return {
        "id": account_id,
        "business_id": str(item.get("business_id") or business_id),
        "provider": "google_sheets",
        "status": "active",
        "auth_ref": account_id,
        "config_json": "{}",
        "display_name": str(item.get("display_name") or "Google-доступ"),
        "inventory_source": "external_business_account",
    }


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
    source = str(data.get("source") or "").strip()
    if source not in GOOGLE_SHEETS_EXTERNAL_ACCOUNT_SOURCES:
        raise GoogleSheetsAdapterError("Referenced credentials are not a Google Sheets connection.")
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
    return _refresh_credentials(credentials, force=False)


def _refresh_credentials(credentials: Dict[str, Any], *, force: bool = False) -> Dict[str, Any]:
    if str(credentials.get("token") or "").strip() and not force:
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


def _is_unable_to_parse_range_response(response: requests.Response) -> bool:
    text = _response_excerpt(response).lower()
    return response.status_code == 400 and "unable to parse range" in text
