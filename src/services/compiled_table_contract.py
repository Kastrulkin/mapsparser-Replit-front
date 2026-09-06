"""Frozen, string-only CSV contract. This is validation, never the executor."""
import json

TABLE_SCHEMA = "localos_table_input_v1"
MAX_ROWS = 200
MAX_COLUMNS = 20
MAX_CELL_LENGTH = 1000
MAX_INPUT_BYTES = 20 * 1024


def normalize_table_input(value, columns=None):
    if not isinstance(value, dict) or set(value) != {"rows"} or not isinstance(value["rows"], list):
        raise ValueError("table_rows_required")
    rows = value["rows"]
    if len(rows) > MAX_ROWS:
        raise ValueError("table_row_limit")
    normalized = []
    for row in rows:
        if not isinstance(row, dict) or len(row) > MAX_COLUMNS:
            raise ValueError("table_row_invalid")
        if any(not isinstance(key, str) or not key.strip() or key != key.strip() or len(key) > 80 for key in row):
            raise ValueError("table_columns_invalid")
        if columns is not None and set(row) - set(columns):
            raise ValueError("table_unmapped_column")
        if any(not isinstance(cell, str) or len(cell) > MAX_CELL_LENGTH for cell in row.values()):
            raise ValueError("table_cells_must_be_text")
        if any("\x1f" in cell for cell in row.values()):
            raise ValueError("table_reserved_separator")
        normalized.append(dict(row))
    result = {"rows": normalized}
    if len(json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode()) > MAX_INPUT_BYTES:
        raise ValueError("table_input_size_limit")
    return result


def normalize_table_contract(value):
    if not isinstance(value, dict) or type(value.get("version")) is not int or value.get("version") not in {1, 2}:
        raise ValueError("table_contract_version_invalid")
    columns = value.get("columns")
    if not isinstance(columns, list) or not 1 <= len(columns) <= MAX_COLUMNS:
        raise ValueError("table_columns_required")
    if any(not isinstance(column, str) or not column.strip() or column != column.strip() or len(column) > 80 for column in columns) or len(set(columns)) != len(columns):
        raise ValueError("table_columns_invalid")
    result = {"version": value["version"], "columns": list(columns)}
    for name in ("required_columns", "dedupe_columns"):
        selected = value.get(name)
        if not isinstance(selected, list) or any(not isinstance(column, str) or column not in columns for column in selected) or len(set(selected)) != len(selected):
            raise ValueError("table_rule_columns_invalid")
        result[name] = list(selected)
    if not result["dedupe_columns"]:
        raise ValueError("table_dedupe_columns_required")
    name = str(value.get("version_name") or "Проверка таблицы").strip()
    if not name or len(name) > 80:
        raise ValueError("table_version_name_invalid")
    result["version_name"] = name
    return result


def table_manifest(contract, runner_image_digest):
    contract = normalize_table_contract(contract)
    row_schema = {"type": "object", "properties": {column: {"type": "string", "maxLength": MAX_CELL_LENGTH} for column in contract["columns"]}, "additionalProperties": False}
    error_schema = {"type": "object", "properties": {"row": {"type": "integer", "minimum": 1}, "code": {"type": "string", "enum": ["required", "row_not_object"]}, "columns": {"type": "array", "items": {"type": "string"}}}, "required": ["row", "code"], "additionalProperties": False}
    if contract["version"] == 2:
        error_schema["properties"]["code"]["enum"].append("duplicate")
    count = {"type": "integer", "minimum": 0, "maximum": MAX_ROWS}
    return {
        "kind": "localos.sheet_validate_dedupe_report.v1",
        "table_contract": contract,
        "input_schema": {"type": "object", "properties": {"rows": {"type": "array", "items": row_schema, "maxItems": MAX_ROWS}}, "required": ["rows"], "additionalProperties": False},
        "output_schema": {"type": "object", "properties": {
            "schema": {"type": "string", "enum": ["localos_compiled_script_result_v1"]},
            "rows": {"type": "array", "items": row_schema, "maxItems": MAX_ROWS},
            "report": {"type": "object", "properties": {"received": count, "accepted": count, "duplicates": count, "invalid": count, "errors": {"type": "array", "items": error_schema, "maxItems": MAX_ROWS}}, "required": ["received", "accepted", "duplicates", "invalid", "errors"], "additionalProperties": False},
        }, "required": ["schema", "rows", "report"], "additionalProperties": False},
        "required_columns": contract["required_columns"], "dedupe_columns": contract["dedupe_columns"],
        "runtime_version": "python-3.12-restricted-v1", "runner_image_digest": runner_image_digest,
        "dependencies": [], "uses_model": False, "external_effects": [],
    }


def generation_instructions(contract):
    """Fully specify existing v1 semantics without supplying an implementation."""
    version_rule = ""
    if contract.get("version") == 2:
        version_rule = "\nVersion 2: each skipped duplicate also adds {row:original 1-based DATA row number excluding header,code:'duplicate'} to report.errors in input row order. report.invalid counts only invalid/required rows, NOT duplicate entries; duplicates remain in report.duplicates."
    return "\nFrozen table contract: " + json.dumps(contract, ensure_ascii=False) + """
Input is {rows:[objects containing text cells]}. Preserve original values and row order. Reject a row
when any required column is missing or is empty after strip(); report {row:1-based input position,
code:'required',columns:[missing columns in configured order]}. Deduplicate valid rows by the ordered
dedupe_columns, using str(row.get(column) or '').strip().lower().join semantics with a U+001F separator;
retain the first valid row. Do not deduplicate invalid rows. Return exactly
{schema:'localos_compiled_script_result_v1',rows:acceptedRows,report:{received:inputCount,
accepted:acceptedCount,duplicates:duplicateCount,invalid:errorCount,errors:errors}}.
No extra report fields, hashes or runtime metadata: the server adds those. Empty input returns zero
counts. You must implement these rules in Python process(input_payload). Allowed attribute calls are
get,strip,lower,upper,items,append,split,join; use a list with membership checks for seen keys.
The platform supplies the manifest and independently evaluates the returned source. No extra rules
from informal description may override the frozen contract. No fallback or prewritten program is used.
""" + version_rule
