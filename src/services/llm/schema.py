from __future__ import annotations

import json
from typing import Any


def parse_json_value(content: str) -> dict[str, Any] | list[Any] | None:
    text = str(content or "").strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except Exception:
        start = min([index for index in (text.find("{"), text.find("[")) if index >= 0], default=-1)
        object_end = text.rfind("}")
        array_end = text.rfind("]")
        end = max(object_end, array_end)
        if start < 0 or end <= start:
            return None
        try:
            parsed = json.loads(text[start : end + 1])
        except Exception:
            return None
    if isinstance(parsed, (dict, list)):
        return parsed
    return None


def validate_json_schema(value: Any, schema: dict[str, Any] | None, path: str = "$") -> list[str]:
    if not schema:
        return []
    errors: list[str] = []
    expected = schema.get("type")
    matches = {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
    }
    if expected and not matches.get(str(expected), True):
        return [f"{path}: expected {expected}"]
    if isinstance(value, dict):
        required = schema.get("required") if isinstance(schema.get("required"), list) else []
        for key in required:
            if key not in value:
                errors.append(f"{path}.{key}: required")
        properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        for key, child_schema in properties.items():
            if key in value and isinstance(child_schema, dict):
                errors.extend(validate_json_schema(value[key], child_schema, f"{path}.{key}"))
    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        for index, item in enumerate(value):
            errors.extend(validate_json_schema(item, schema["items"], f"{path}[{index}]"))
    enum_values = schema.get("enum")
    if isinstance(enum_values, list) and value not in enum_values:
        errors.append(f"{path}: value outside enum")
    return errors
