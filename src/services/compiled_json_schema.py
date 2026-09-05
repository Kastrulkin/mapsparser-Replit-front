"""Small, deterministic JSON-schema subset for sandbox contracts."""
from typing import Any

ALLOWED = {"type", "properties", "required", "additionalProperties", "items", "enum", "minItems", "maxItems", "minLength", "maxLength", "minimum", "maximum"}
TYPES = {"object", "array", "string", "integer", "number", "boolean", "null"}


def validate_schema(schema: Any) -> list[str]:
    if not isinstance(schema, dict): return ["schema_not_object"]
    unknown = set(schema) - ALLOWED
    if unknown or schema.get("type") not in TYPES: return ["schema_unsupported"]
    if schema["type"] == "object":
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if not isinstance(properties, dict) or not isinstance(required, list) or any(key not in properties for key in required): return ["schema_object_invalid"]
        return sum((validate_schema(value) for value in properties.values()), [])
    if schema["type"] == "array":
        return validate_schema(schema.get("items")) if "items" in schema else ["schema_items_required"]
    return []


def validate_value(schema: dict, value: Any, path: str = "$") -> list[str]:
    errors = validate_schema(schema)
    if errors: return errors
    kind = schema["type"]
    types = {"object": dict, "array": list, "string": str, "integer": int, "number": (int, float), "boolean": bool}
    if kind == "null": valid = value is None
    elif kind in {"integer", "number"}: valid = isinstance(value, types[kind]) and not isinstance(value, bool)
    else: valid = isinstance(value, types[kind])
    if not valid: return [path + ":type"]
    if "enum" in schema and (not isinstance(schema["enum"], list) or value not in schema["enum"]): return [path + ":enum"]
    if kind == "object":
        properties = schema.get("properties", {})
        unknown = set(value) - set(properties)
        if schema.get("additionalProperties", False) is not True and unknown: errors.append(path + ":unknown")
        for key in schema.get("required", []):
            if key not in value: errors.append(path + "." + key + ":required")
        for key, child in properties.items():
            if key in value: errors.extend(validate_value(child, value[key], path + "." + key))
    if kind == "array":
        if "minItems" in schema and len(value) < schema["minItems"]: errors.append(path + ":minItems")
        if "maxItems" in schema and len(value) > schema["maxItems"]: errors.append(path + ":maxItems")
        for index, item in enumerate(value): errors.extend(validate_value(schema["items"], item, path + "[" + str(index) + "]"))
    if kind == "string":
        if "minLength" in schema and len(value) < schema["minLength"]: errors.append(path + ":minLength")
        if "maxLength" in schema and len(value) > schema["maxLength"]: errors.append(path + ":maxLength")
    if kind in {"integer", "number"}:
        if "minimum" in schema and value < schema["minimum"]: errors.append(path + ":minimum")
        if "maximum" in schema and value > schema["maximum"]: errors.append(path + ":maximum")
    return errors
