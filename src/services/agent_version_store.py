"""Canonical immutable version persistence shared by API and Operator."""
import json
import uuid
from services.agent_blueprint_runner import normalize_steps, parse_json_field


def _normalize_json_row(row: dict) -> dict:
    result = dict(row)
    for key in list(result.keys()):
        if key.endswith("_json"):
            fallback = [] if key in {"steps_json", "capability_allowlist_json"} else {}
            result[key] = parse_json_field(result.get(key), fallback)
    return result


def insert_version(cursor, blueprint_id: str, payload: dict, user_data: dict, *, trusted_compiled: bool = False):
    cursor.execute("SELECT id FROM agent_blueprints WHERE id=%s FOR UPDATE", (blueprint_id,))
    if not cursor.fetchone():
        raise ValueError("agent_not_found")
    if not trusted_compiled:
        payload = {key: value for key, value in payload.items() if not str(key).startswith("compiled_")}
    cursor.execute(
        "SELECT COALESCE(MAX(version_number), 0) + 1 AS next_version FROM agent_blueprint_versions WHERE blueprint_id = %s",
        (blueprint_id,),
    )
    version_row = cursor.fetchone() or {}
    version_number = int(version_row.get("next_version") or 1)
    version_id = str(uuid.uuid4())
    steps = normalize_steps(payload.get("steps"))
    cursor.execute(
        """
        INSERT INTO agent_blueprint_versions (
            id, blueprint_id, version_number, goal, inputs_schema_json, steps_json,
            persona_agent_id, capability_allowlist_json, approval_policy_json,
            output_schema_json, execution_mode, trigger, schedule_json, runtime_config_json, limits_json,
            required_integration_bindings_json, compiled_artifact_json, compiled_artifact_hash, compiled_state, created_by_user_id
        )
        VALUES (
            %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s::jsonb, %s::jsonb,
            %s::jsonb, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s, %s
        )
        """,
        (
            version_id,
            blueprint_id,
            version_number,
            str(payload.get("goal") or "").strip(),
            json.dumps(payload.get("inputs_schema") if isinstance(payload.get("inputs_schema"), dict) else {}, ensure_ascii=False),
            json.dumps(steps, ensure_ascii=False),
            str(payload.get("persona_agent_id") or "").strip() or None,
            json.dumps(payload.get("capability_allowlist") if isinstance(payload.get("capability_allowlist"), list) else [], ensure_ascii=False),
            json.dumps(payload.get("approval_policy") if isinstance(payload.get("approval_policy"), dict) else {}, ensure_ascii=False),
            json.dumps(payload.get("output_schema") if isinstance(payload.get("output_schema"), dict) else {}, ensure_ascii=False),
            str(payload.get("execution_mode") or ("scheduled" if str(payload.get("trigger") or "").startswith("schedule.") else "manual")).strip(),
            str(payload.get("trigger") or "manual.run").strip(),
            json.dumps(payload.get("schedule") if isinstance(payload.get("schedule"), dict) else {}, ensure_ascii=False),
            json.dumps(payload.get("runtime_config") if isinstance(payload.get("runtime_config"), dict) else {}, ensure_ascii=False),
            json.dumps(payload.get("limits") if isinstance(payload.get("limits"), dict) else {}, ensure_ascii=False),
            json.dumps(
                payload.get("required_integration_bindings")
                if isinstance(payload.get("required_integration_bindings"), list)
                else [],
                ensure_ascii=False,
            ),
            json.dumps(payload.get("compiled_artifact") if trusted_compiled and isinstance(payload.get("compiled_artifact"), dict) else {}, ensure_ascii=False),
            str(payload.get("compiled_artifact_hash") or "").strip() if trusted_compiled else None,
            str(payload.get("compiled_state") or "legacy").strip() if trusted_compiled else "legacy",
            str(user_data.get('user_id') or user_data.get('id') or ''),
        ),
    )
    cursor.execute("SELECT * FROM agent_blueprint_versions WHERE id = %s", (version_id,))
    return _normalize_json_row(dict(cursor.fetchone()))

