import json
import uuid
from datetime import datetime, timezone

from flask import Blueprint, Response, jsonify, request

from core.auth_helpers import require_auth_from_request, verify_business_access
from database_manager import DatabaseManager
from services.agent_blueprint_runner import (
    AgentBlueprintRunner,
    default_supervised_outreach_version_payload,
    parse_json_field,
    normalize_steps,
)
from services.agent_blueprint_orchestrator import build_agent_blueprint_orchestrator
from services.agent_blueprint_draft_builder import build_agent_blueprint_draft
from services.agent_blueprint_workspace import (
    build_agent_version_diff,
    build_blueprint_review,
    build_feedback_version_payload,
    build_learning_loop_summary,
    build_version_payload_from_row,
    normalize_agent_setup,
    normalize_agent_source,
    workspace_parse_json_field,
)
from services.agent_product_layer import (
    attach_persona_to_version,
    attach_product_agent_to_blueprint,
    collect_persona_agent_ids,
    parse_persona_row,
)
from services.agent_legacy_migration import apply_legacy_ai_agent_migration, build_legacy_ai_agent_migration_plan
from services.agent_source_ingestion import build_agent_source_from_upload
from services.agent_datahub import build_agent_datahub_catalog


agent_blueprints_bp = Blueprint("agent_blueprints_api", __name__)


def _json_error(message: str, status: int, code: str):
    return jsonify({"success": False, "error": message, "code": code}), status


def _require_auth():
    user_data = require_auth_from_request()
    if not user_data:
        return None, _json_error("Authorization required", 401, "AUTH_REQUIRED")
    return user_data, None


def _user_id(user_data: dict) -> str:
    return str(user_data.get("user_id") or user_data.get("id") or "")


def _normalize_json_row(row: dict) -> dict:
    result = dict(row)
    for key in list(result.keys()):
        if key.endswith("_json"):
            fallback = [] if key in {"steps_json", "capability_allowlist_json"} else {}
            result[key] = parse_json_field(result.get(key), fallback)
    return result


def _load_personas_by_id(cursor, persona_ids: list[str]) -> dict:
    clean_ids = [item for item in persona_ids if item]
    if not clean_ids:
        return {}
    cursor.execute(
        """
        SELECT id, name, type, description, personality, identity, speech_style,
               restrictions_json, variables_json, is_active
        FROM AIAgents
        WHERE id = ANY(%s)
        """,
        (clean_ids,),
    )
    personas = {}
    for row in cursor.fetchall() or []:
        persona = parse_persona_row(dict(row))
        if persona:
            personas[persona["id"]] = persona
    return personas


def _require_business_access(cursor, business_id: str, user_data: dict):
    has_access, owner_id = verify_business_access(cursor, business_id, user_data)
    if not owner_id:
        return False, _json_error("Business not found", 404, "BUSINESS_NOT_FOUND")
    if not has_access:
        return False, _json_error("Forbidden", 403, "FORBIDDEN")
    return True, None


def _load_blueprint(cursor, blueprint_id: str):
    cursor.execute("SELECT * FROM agent_blueprints WHERE id = %s", (blueprint_id,))
    row = cursor.fetchone()
    return dict(row) if row else None


def _load_blueprint_version_for_blueprint(cursor, blueprint_id: str, version_id: str):
    cursor.execute(
        """
        SELECT *
        FROM agent_blueprint_versions
        WHERE id = %s
          AND blueprint_id = %s
        """,
        (version_id, blueprint_id),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def _load_blueprint_version(cursor, version_id: str):
    cursor.execute("SELECT * FROM agent_blueprint_versions WHERE id = %s", (version_id,))
    row = cursor.fetchone()
    return dict(row) if row else None


def _load_latest_blueprint_version(cursor, blueprint_id: str):
    cursor.execute(
        """
        SELECT *
        FROM agent_blueprint_versions
        WHERE blueprint_id = %s
        ORDER BY version_number DESC
        LIMIT 1
        """,
        (blueprint_id,),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def _blueprint_metadata(blueprint: dict) -> dict:
    metadata = workspace_parse_json_field(blueprint.get("metadata_json"), {})
    return metadata if isinstance(metadata, dict) else {}


def _save_blueprint_metadata(cursor, blueprint_id: str, metadata: dict) -> None:
    cursor.execute(
        """
        UPDATE agent_blueprints
        SET metadata_json = %s::jsonb,
            updated_at = NOW()
        WHERE id = %s
        """,
        (json.dumps(metadata, ensure_ascii=False), blueprint_id),
    )


def _normalize_agent_integration(row: dict, *, attached: bool = True) -> dict:
    config = workspace_parse_json_field(row.get("config_json"), {})
    limits = workspace_parse_json_field(row.get("limits_json"), {})
    if not isinstance(config, dict):
        config = {}
    if not isinstance(limits, dict):
        limits = {}
    provider = str(row.get("provider") or "").strip()
    return {
        "id": str(row.get("id") or ""),
        "business_id": str(row.get("business_id") or ""),
        "provider": provider,
        "provider_label": _agent_integration_provider_label(provider),
        "status": str(row.get("status") or "draft"),
        "display_name": str(row.get("display_name") or ""),
        "auth_ref": str(row.get("auth_ref") or ""),
        "has_auth_ref": bool(str(row.get("auth_ref") or "").strip()),
        "config": config,
        "limits": limits,
        "attached": attached,
        "connected_by_user_id": str(row.get("connected_by_user_id") or ""),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "execution_boundary": _agent_integration_execution_boundary(provider),
    }


def _agent_integration_provider_label(provider: str) -> str:
    labels = {
        "google_sheets": "Google Sheets",
        "telegram": "Telegram",
    }
    return labels.get(provider, provider or "integration")


def _agent_integration_execution_boundary(provider: str) -> dict:
    if provider == "google_sheets":
        return {
            "capabilities": ["sheets.append_row_request", "google_sheets.append_row"],
            "approval_required": True,
            "executor": "agent_sheet_provider_executor_v1",
            "external_write": "approved_append_row",
        }
    if provider == "telegram":
        return {
            "triggers": ["telegram.message.received"],
            "capabilities": ["communications.draft", "communications.send_reminder", "communications.send_offer"],
            "approval_required": True,
            "executor": "channel_router",
            "external_write": "approved_delivery_only",
        }
    return {
        "capabilities": [],
        "approval_required": True,
        "executor": "action_orchestrator",
        "external_write": "approval_required",
    }


def _agent_integration_provider_catalog() -> list[dict]:
    return [
        {
            "provider": "google_sheets",
            "title": "Google Sheets",
            "description": "Controlled append/write boundary для compiled workflows: approval -> provider executor -> ledger.",
            "required_config": ["spreadsheet_id", "sheet_name"],
            "default_limits": {"daily_append_cap": 50, "frequency_cap_minutes": 0},
            "status": "available",
        },
        {
            "provider": "telegram",
            "title": "Telegram",
            "description": "Trigger boundary для сообщений в бота и supervised delivery через router.",
            "required_config": ["bot_mode"],
            "default_limits": {"daily_message_cap": 50, "frequency_cap_minutes": 30},
            "status": "available",
        },
    ]


def _agent_integration_ids(metadata: dict) -> list[str]:
    raw_ids = metadata.get("agent_integration_ids") if isinstance(metadata.get("agent_integration_ids"), list) else []
    result = []
    for item in raw_ids:
        item_id = str(item or "").strip()
        if item_id and item_id not in result:
            result.append(item_id)
    return result


def _agent_integration_binding_status(metadata: dict, integrations: list[dict]) -> list[dict]:
    required = metadata.get("required_integration_bindings") if isinstance(metadata.get("required_integration_bindings"), list) else []
    by_provider = {}
    for integration in integrations:
        provider = str(integration.get("provider") or "").strip()
        if provider and provider not in by_provider:
            by_provider[provider] = integration
    result = []
    for item in required:
        if not isinstance(item, dict):
            continue
        provider = str(item.get("provider") or "").strip()
        integration = by_provider.get(provider)
        config = workspace_parse_json_field((integration or {}).get("config_json"), {})
        if not isinstance(config, dict):
            config = {}
        required_config = item.get("required_config") if isinstance(item.get("required_config"), list) else []
        missing_config = [
            str(config_key)
            for config_key in required_config
            if not str(config.get(str(config_key)) or "").strip()
        ]
        status = "connected" if integration and str(integration.get("status") or "") == "active" and not missing_config else "needs_connection"
        result.append(
            {
                "key": str(item.get("key") or ""),
                "provider": provider,
                "direction": str(item.get("direction") or ""),
                "required": bool(item.get("required", True)),
                "approval_required": bool(item.get("approval_required", True)),
                "capability": str(item.get("capability") or ""),
                "trigger": str(item.get("trigger") or ""),
                "status": status,
                "integration_id": str((integration or {}).get("id") or ""),
                "missing_config": missing_config,
            }
        )
    return result


def _load_agent_integrations(cursor, business_id: str, integration_ids: list[str] | None = None) -> list[dict]:
    if integration_ids:
        cursor.execute(
            """
            SELECT id, business_id, provider, status, display_name, auth_ref,
                   config_json, limits_json, connected_by_user_id, created_at, updated_at
            FROM agent_integrations
            WHERE business_id = %s
              AND id = ANY(%s)
            ORDER BY updated_at DESC, created_at DESC
            """,
            (business_id, integration_ids),
        )
    else:
        cursor.execute(
            """
            SELECT id, business_id, provider, status, display_name, auth_ref,
                   config_json, limits_json, connected_by_user_id, created_at, updated_at
            FROM agent_integrations
            WHERE business_id = %s
            ORDER BY updated_at DESC, created_at DESC
            LIMIT 100
            """,
            (business_id,),
        )
    return [dict(row) for row in cursor.fetchall() or []]


def _load_agent_external_auth_options(cursor, business_id: str) -> list[dict]:
    try:
        cursor.execute(
            """
            SELECT id, source, external_id, display_name, is_active, updated_at
            FROM externalbusinessaccounts
            WHERE business_id = %s
              AND is_active = TRUE
              AND source IN ('google_business', 'telegram_app')
            ORDER BY updated_at DESC
            LIMIT 50
            """,
            (business_id,),
        )
    except Exception:
        return []
    return [
        {
            "id": str(row.get("id") or ""),
            "source": str(row.get("source") or ""),
            "display_name": str(row.get("display_name") or row.get("external_id") or row.get("source") or ""),
            "updated_at": row.get("updated_at"),
        }
        for row in cursor.fetchall() or []
    ]


def _sanitize_agent_integration_config(provider: str, payload: dict) -> dict:
    source = payload.get("config") if isinstance(payload.get("config"), dict) else payload
    if provider == "google_sheets":
        return {
            "spreadsheet_id": str(source.get("spreadsheet_id") or source.get("google_spreadsheet_id") or "").strip(),
            "sheet_name": str(source.get("sheet_name") or source.get("tab") or "Sheet1").strip() or "Sheet1",
            "operation": "append_row",
            "mode": "approved_executor",
        }
    if provider == "telegram":
        return {
            "bot_mode": str(source.get("bot_mode") or "business_bot").strip() or "business_bot",
            "trigger": "telegram.message.received",
            "mode": "trigger_boundary",
        }
    return {}


def _sanitize_agent_integration_limits(provider: str, payload: dict) -> dict:
    source = payload.get("limits") if isinstance(payload.get("limits"), dict) else payload
    if provider == "google_sheets":
        return {
            "daily_append_cap": _safe_int(source.get("daily_append_cap"), 50, 1, 500),
            "frequency_cap_minutes": _safe_int(source.get("frequency_cap_minutes"), 0, 0, 1440),
        }
    if provider == "telegram":
        return {
            "daily_message_cap": _safe_int(source.get("daily_message_cap"), 50, 1, 500),
            "frequency_cap_minutes": _safe_int(source.get("frequency_cap_minutes"), 30, 0, 1440),
        }
    return {}


def _safe_int(value, fallback: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = fallback
    return max(minimum, min(parsed, maximum))


def _sync_blueprint_integration_metadata(cursor, blueprint: dict, integration: dict) -> dict:
    blueprint_id = str(blueprint.get("id") or "")
    metadata = _blueprint_metadata(_load_blueprint(cursor, blueprint_id) or blueprint)
    integration_ids = _agent_integration_ids(metadata)
    integration_id = str(integration.get("id") or "").strip()
    if integration_id and integration_id not in integration_ids:
        integration_ids.append(integration_id)
    metadata["agent_integration_ids"] = integration_ids[-25:]
    capability_integrations = metadata.get("capability_integrations") if isinstance(metadata.get("capability_integrations"), dict) else {}
    provider = str(integration.get("provider") or "").strip()
    if provider:
        capability_integrations[provider] = integration_id
    metadata["capability_integrations"] = capability_integrations
    if provider == "google_sheets":
        custom_process = metadata.get("custom_process") if isinstance(metadata.get("custom_process"), dict) else {}
        custom_process["trigger"] = str(custom_process.get("trigger") or "telegram.message.received")
        config = workspace_parse_json_field(integration.get("config_json"), {})
        if not isinstance(config, dict):
            config = {}
        custom_process["google_sheets"] = {
            "integration_id": integration_id,
            "spreadsheet_id": str(config.get("spreadsheet_id") or "").strip(),
            "sheet_name": str(config.get("sheet_name") or "Sheet1").strip() or "Sheet1",
            "operation": "append_row",
        }
        custom_process["binding_status"] = "connected"
        metadata["custom_process"] = custom_process
    if provider == "telegram":
        triggers = metadata.get("triggers") if isinstance(metadata.get("triggers"), list) else []
        if "telegram.message.received" not in triggers:
            triggers.append("telegram.message.received")
        metadata["triggers"] = triggers[-10:]
    _save_blueprint_metadata(cursor, blueprint_id, metadata)
    return metadata


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _version_number(version: dict | None) -> int:
    try:
        return int((version or {}).get("version_number") or 0)
    except Exception:
        return 0


def _resolve_active_version(cursor, blueprint: dict):
    metadata = _blueprint_metadata(blueprint)
    active_version_id = str(metadata.get("active_version_id") or "").strip()
    if active_version_id:
        version = _load_blueprint_version_for_blueprint(cursor, str(blueprint.get("id") or ""), active_version_id)
        if version:
            return version
    return _load_latest_blueprint_version(cursor, str(blueprint.get("id") or ""))


def _remember_active_version(cursor, blueprint: dict, version: dict, user_data: dict, action: str, reason: str = "") -> dict:
    blueprint_id = str(blueprint.get("id") or "")
    refreshed_blueprint = _load_blueprint(cursor, blueprint_id) if blueprint_id else None
    metadata = _blueprint_metadata(refreshed_blueprint or blueprint)
    previous_active_id = str(metadata.get("active_version_id") or "").strip()
    event = {
        "action": action,
        "previous_active_version_id": previous_active_id,
        "active_version_id": str(version.get("id") or ""),
        "active_version_number": _version_number(version),
        "reason": reason,
        "created_by_user_id": _user_id(user_data),
        "created_at": _utc_now_text(),
    }
    events = metadata.get("version_events") if isinstance(metadata.get("version_events"), list) else []
    events.append(event)
    metadata["active_version_id"] = event["active_version_id"]
    metadata["active_version_number"] = event["active_version_number"]
    metadata["active_version_updated_at"] = event["created_at"]
    metadata["version_events"] = events[-50:]
    _save_blueprint_metadata(cursor, blueprint_id, metadata)
    cursor.execute(
        """
        UPDATE agent_blueprints
        SET status = 'active',
            updated_at = NOW()
        WHERE id = %s
          AND status <> 'archived'
        """,
        (blueprint_id,),
    )
    return event


def _decorate_versions(cursor, blueprint: dict, versions: list[dict]) -> tuple[list[dict], dict | None]:
    active_version = _resolve_active_version(cursor, blueprint)
    active_version_id = str((active_version or {}).get("id") or "")
    by_number = {_version_number(version): version for version in versions}
    decorated = []
    for version in versions:
        previous = by_number.get(_version_number(version) - 1)
        decorated_version = dict(version)
        decorated_version["is_active"] = str(version.get("id") or "") == active_version_id
        decorated_version["active_state"] = "active" if decorated_version["is_active"] else "inactive"
        decorated_version["diff_from_previous"] = build_agent_version_diff(previous, version)
        decorated.append(decorated_version)
    return decorated, active_version


def _require_blueprint_access(cursor, blueprint_id: str, user_data: dict):
    blueprint = _load_blueprint(cursor, blueprint_id)
    if not blueprint:
        return None, _json_error("Blueprint not found", 404, "NOT_FOUND")
    allowed, error_response = _require_business_access(cursor, str(blueprint.get("business_id") or ""), user_data)
    if not allowed:
        return None, error_response
    return blueprint, None


def _insert_version(cursor, blueprint_id: str, payload: dict, user_data: dict):
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
            output_schema_json, created_by_user_id
        )
        VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s)
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
            _user_id(user_data),
        ),
    )
    cursor.execute("SELECT * FROM agent_blueprint_versions WHERE id = %s", (version_id,))
    return _normalize_json_row(dict(cursor.fetchone()))


@agent_blueprints_bp.route("/api/agent-blueprints", methods=["GET"])
def list_agent_blueprints():
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        business_id = str(request.args.get("business_id") or "").strip()
        params = []
        where_sql = ""
        if business_id:
            allowed, access_error = _require_business_access(cursor, business_id, user_data)
            if not allowed:
                return access_error
            where_sql = "WHERE b.business_id = %s"
            params.append(business_id)
        elif not user_data.get("is_superadmin"):
            where_sql = """
            WHERE b.business_id IN (
                SELECT id FROM businesses WHERE owner_id = %s
            )
            """
            params.append(_user_id(user_data))
        cursor.execute(
            f"""
            SELECT b.*,
                   v.id AS latest_version_id,
                   v.version_number AS latest_version_number,
                   v.goal AS latest_goal,
                   v.persona_agent_id latest_persona_agent_id,
                   av.id AS active_version_id,
                   av.version_number AS active_version_number,
                   av.goal AS active_goal,
                   av.persona_agent_id active_persona_agent_id,
                   lr.id last_run_id,
                   lr.status last_run_status,
                   lr.started_at last_run_started_at,
                   lr.completed_at last_run_completed_at,
                   COALESCE(pq.pending_approvals_count, 0) pending_approvals_count,
                   COALESCE(vs.versions_count, 0) versions_count,
                   COALESCE(jsonb_array_length(CASE WHEN jsonb_typeof(b.metadata_json->'agent_sources') = 'array' THEN b.metadata_json->'agent_sources' ELSE '[]'::jsonb END), 0) sources_count,
                   COALESCE(jsonb_array_length(CASE WHEN jsonb_typeof(b.metadata_json->'agent_journal') = 'array' THEN b.metadata_json->'agent_journal' ELSE '[]'::jsonb END), 0) journal_entries_count
            FROM agent_blueprints b
            LEFT JOIN LATERAL (
                SELECT id, version_number, goal, persona_agent_id
                FROM agent_blueprint_versions
                WHERE blueprint_id = b.id
                ORDER BY version_number DESC
                LIMIT 1
            ) v ON TRUE
            LEFT JOIN LATERAL (
                SELECT id, version_number, goal, persona_agent_id
                FROM agent_blueprint_versions
                WHERE blueprint_id = b.id
                  AND id = COALESCE(NULLIF(b.metadata_json->>'active_version_id', ''), v.id)
                LIMIT 1
            ) av ON TRUE
            LEFT JOIN LATERAL (
                SELECT id, status, started_at, completed_at
                FROM agent_runs
                WHERE blueprint_id = b.id
                ORDER BY started_at DESC
                LIMIT 1
            ) lr ON TRUE
            LEFT JOIN LATERAL (
                SELECT COUNT(*) pending_approvals_count
                FROM agent_approvals a
                JOIN agent_runs r ON r.id = a.run_id
                WHERE r.blueprint_id = b.id
                  AND a.status = 'pending'
            ) pq ON TRUE
            LEFT JOIN LATERAL (
                SELECT COUNT(*) versions_count
                FROM agent_blueprint_versions
                WHERE blueprint_id = b.id
            ) vs ON TRUE
            {where_sql}
            ORDER BY b.created_at DESC
            LIMIT 200
            """,
            tuple(params),
        )
        rows = [_normalize_json_row(dict(row)) for row in (cursor.fetchall() or [])]
        personas = _load_personas_by_id(cursor, collect_persona_agent_ids(rows))
        decorated_rows = []
        for row in rows:
            active_version = {
                "id": row.get("active_version_id") or row.get("latest_version_id"),
                "version_number": row.get("active_version_number") or row.get("latest_version_number"),
                "persona_agent_id": row.get("active_persona_agent_id") or row.get("latest_persona_agent_id"),
            }
            decorated_rows.append(attach_product_agent_to_blueprint(row, active_version, personas))
        return jsonify({"success": True, "blueprints": decorated_rows})
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-blueprints", methods=["POST"])
def create_agent_blueprint():
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    business_id = str(payload.get("business_id") or "").strip()
    name = str(payload.get("name") or "").strip()
    category = str(payload.get("category") or "custom").strip().lower()
    if not business_id or not name:
        return _json_error("business_id and name are required", 400, "VALIDATION_ERROR")

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        allowed, access_error = _require_business_access(cursor, business_id, user_data)
        if not allowed:
            return access_error
        blueprint_id = str(uuid.uuid4())
        template = str(payload.get("template") or "").strip().lower()
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        cursor.execute(
            """
            INSERT INTO agent_blueprints (
                id, business_id, name, category, description, status, created_by_user_id, metadata_json
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (
                blueprint_id,
                business_id,
                name,
                category,
                str(payload.get("description") or "").strip() or None,
                str(payload.get("status") or "draft").strip().lower(),
                _user_id(user_data),
                json.dumps(metadata, ensure_ascii=False),
            ),
        )
        version = None
        if template == "supervised_outreach" or payload.get("create_default_version"):
            version_payload = default_supervised_outreach_version_payload()
            version_payload["persona_agent_id"] = payload.get("persona_agent_id")
            version = _insert_version(cursor, blueprint_id, version_payload, user_data)
            _remember_active_version(cursor, {"id": blueprint_id, "metadata_json": metadata}, version, user_data, "created")
        db.conn.commit()
        blueprint = _load_blueprint(cursor, blueprint_id)
        return jsonify(
            {
                "success": True,
                "blueprint": _normalize_json_row(blueprint),
                "version": version,
            }
        ), 201
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-blueprints/draft", methods=["POST"])
def create_agent_blueprint_draft():
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    business_id = str(payload.get("business_id") or "").strip()
    description = str(payload.get("description") or "").strip()
    if not business_id or not description:
        return _json_error("business_id and description are required", 400, "VALIDATION_ERROR")

    draft = build_agent_blueprint_draft(description, str(payload.get("category") or ""))
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        allowed, access_error = _require_business_access(cursor, business_id, user_data)
        if not allowed:
            return access_error
        blueprint_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO agent_blueprints (
                id, business_id, name, category, description, status, created_by_user_id, metadata_json
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (
                blueprint_id,
                business_id,
                str(draft.get("name") or "").strip() or "Кастомный агент",
                str(draft.get("category") or "custom").strip().lower(),
                str(draft.get("description") or "").strip() or None,
                "draft",
                _user_id(user_data),
                json.dumps(draft.get("metadata") if isinstance(draft.get("metadata"), dict) else {}, ensure_ascii=False),
            ),
        )
        version_payload = draft.get("version_payload") if isinstance(draft.get("version_payload"), dict) else {}
        version = _insert_version(cursor, blueprint_id, version_payload, user_data)
        _remember_active_version(cursor, {"id": blueprint_id, "metadata_json": draft.get("metadata") if isinstance(draft.get("metadata"), dict) else {}}, version, user_data, "created")
        db.conn.commit()
        blueprint = _load_blueprint(cursor, blueprint_id)
        return jsonify(
            {
                "success": True,
                "blueprint": _normalize_json_row(blueprint),
                "version": version,
                "draft": {
                    "category": draft.get("category"),
                    "summary": draft.get("summary") if isinstance(draft.get("summary"), dict) else {},
                },
            }
        ), 201
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-blueprints/legacy-migration-plan", methods=["GET"])
def get_agent_blueprint_legacy_migration_plan():
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    business_id = str(request.args.get("business_id") or "").strip()
    if not business_id:
        return _json_error("business_id is required", 400, "VALIDATION_ERROR")
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        allowed, access_error = _require_business_access(cursor, business_id, user_data)
        if not allowed:
            return access_error
        plan = build_legacy_ai_agent_migration_plan(cursor, business_id)
        return jsonify({"success": True, "migration_plan": plan})
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-blueprints/legacy-migration/apply", methods=["POST"])
def apply_agent_blueprint_legacy_migration():
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    business_id = str(payload.get("business_id") or "").strip()
    if not business_id:
        return _json_error("business_id is required", 400, "VALIDATION_ERROR")
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        allowed, access_error = _require_business_access(cursor, business_id, user_data)
        if not allowed:
            return access_error
        result = apply_legacy_ai_agent_migration(cursor, business_id, _user_id(user_data))
        db.conn.commit()
        return jsonify({"success": True, "migration": result})
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-blueprints/<blueprint_id>", methods=["GET"])
def get_agent_blueprint(blueprint_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        blueprint, access_error = _require_blueprint_access(cursor, blueprint_id, user_data)
        if access_error:
            return access_error
        cursor.execute(
            """
            SELECT *
            FROM agent_blueprint_versions
            WHERE blueprint_id = %s
            ORDER BY version_number DESC
            """,
            (blueprint_id,),
        )
        versions = [_normalize_json_row(dict(row)) for row in (cursor.fetchall() or [])]
        versions, active_version = _decorate_versions(cursor, blueprint, versions)
        personas = _load_personas_by_id(cursor, collect_persona_agent_ids(versions, [active_version] if active_version else []))
        versions = [attach_persona_to_version(version, personas) for version in versions]
        if active_version:
            active_version = attach_persona_to_version(_normalize_json_row(active_version), personas)
        decorated_blueprint = attach_product_agent_to_blueprint(_normalize_json_row(blueprint), active_version, personas)
        run_status = str(request.args.get("run_status") or "").strip().lower()
        run_params = [blueprint_id]
        run_where = "WHERE blueprint_id = %s"
        if run_status:
            run_where = f"{run_where} AND status = %s"
            run_params.append(run_status)
        cursor.execute(
            f"""
            SELECT *
            FROM agent_runs
            {run_where}
            ORDER BY started_at DESC
            LIMIT 50
            """,
            tuple(run_params),
        )
        runs = [_normalize_json_row(dict(row)) for row in (cursor.fetchall() or [])]
        cursor.execute(
            """
            SELECT a.*,
                   r.status run_status,
                   r.started_at run_started_at
            FROM agent_approvals a
            JOIN agent_runs r ON r.id = a.run_id
            WHERE r.blueprint_id = %s
              AND a.status = 'pending'
            ORDER BY a.requested_at ASC
            LIMIT 50
            """,
            (blueprint_id,),
        )
        approval_queue = [_normalize_json_row(dict(row)) for row in (cursor.fetchall() or [])]
        metadata = _blueprint_metadata(blueprint)
        learning_events = metadata.get("learning_events") if isinstance(metadata.get("learning_events"), list) else []
        version_events = metadata.get("version_events") if isinstance(metadata.get("version_events"), list) else []
        feedback_history = metadata.get("feedback_history") if isinstance(metadata.get("feedback_history"), list) else []
        legacy_migration = metadata.get("legacy_migration") if isinstance(metadata.get("legacy_migration"), dict) else {}
        return jsonify(
            {
                "success": True,
                "blueprint": decorated_blueprint,
                "active_version": active_version if active_version else None,
                "active_version_id": str((active_version or {}).get("id") or ""),
                "active_version_number": _version_number(active_version),
                "versions": versions,
                "runs": runs,
                "approval_queue": approval_queue,
                "learning_events": learning_events[-50:],
                "version_events": version_events[-50:],
                "feedback_history": feedback_history[-20:],
                "legacy_migration": legacy_migration,
            }
        )
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-blueprints/<blueprint_id>/versions", methods=["POST"])
def create_agent_blueprint_version(blueprint_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    if not str(payload.get("goal") or "").strip():
        return _json_error("goal is required", 400, "VALIDATION_ERROR")
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        blueprint, access_error = _require_blueprint_access(cursor, blueprint_id, user_data)
        if access_error:
            return access_error
        version = _insert_version(cursor, str(blueprint.get("id")), payload, user_data)
        event = _remember_active_version(cursor, blueprint, version, user_data, "created")
        db.conn.commit()
        return jsonify({"success": True, "version": version, "active_version": version, "version_event": event}), 201
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-blueprints/<blueprint_id>/versions/<version_id>/diff", methods=["GET"])
def get_agent_blueprint_version_diff(blueprint_id: str, version_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        blueprint, access_error = _require_blueprint_access(cursor, blueprint_id, user_data)
        if access_error:
            return access_error
        version = _load_blueprint_version_for_blueprint(cursor, str(blueprint.get("id") or ""), version_id)
        if not version:
            return _json_error("Blueprint version not found", 404, "VERSION_NOT_FOUND")
        compare_to_id = str(request.args.get("compare_to_version_id") or "").strip()
        compare_to = None
        if compare_to_id:
            compare_to = _load_blueprint_version_for_blueprint(cursor, str(blueprint.get("id") or ""), compare_to_id)
            if not compare_to:
                return _json_error("Compare version not found", 404, "COMPARE_VERSION_NOT_FOUND")
        else:
            cursor.execute(
                """
                SELECT *
                FROM agent_blueprint_versions
                WHERE blueprint_id = %s
                  AND version_number < %s
                ORDER BY version_number DESC
                LIMIT 1
                """,
                (blueprint.get("id"), _version_number(version)),
            )
            row = cursor.fetchone()
            compare_to = dict(row) if row else None
        diff = build_agent_version_diff(compare_to, version)
        return jsonify({"success": True, "version": _normalize_json_row(version), "compare_to": _normalize_json_row(compare_to) if compare_to else None, "diff": diff})
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-blueprints/<blueprint_id>/versions/<version_id>/activate", methods=["POST"])
def activate_agent_blueprint_version(blueprint_id: str, version_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        blueprint, access_error = _require_blueprint_access(cursor, blueprint_id, user_data)
        if access_error:
            return access_error
        version = _load_blueprint_version_for_blueprint(cursor, str(blueprint.get("id") or ""), version_id)
        if not version:
            return _json_error("Blueprint version not found", 404, "VERSION_NOT_FOUND")
        active_before = _resolve_active_version(cursor, blueprint)
        event = _remember_active_version(cursor, blueprint, version, user_data, "activated", str(payload.get("reason") or ""))
        db.conn.commit()
        return jsonify(
            {
                "success": True,
                "active_version": _normalize_json_row(version),
                "previous_active_version": _normalize_json_row(active_before) if active_before else None,
                "diff": build_agent_version_diff(active_before, version),
                "version_event": event,
            }
        )
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-blueprints/<blueprint_id>/versions/<version_id>/rollback", methods=["POST"])
def rollback_agent_blueprint_version(blueprint_id: str, version_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        blueprint, access_error = _require_blueprint_access(cursor, blueprint_id, user_data)
        if access_error:
            return access_error
        version = _load_blueprint_version_for_blueprint(cursor, str(blueprint.get("id") or ""), version_id)
        if not version:
            return _json_error("Blueprint version not found", 404, "VERSION_NOT_FOUND")
        active_before = _resolve_active_version(cursor, blueprint)
        if active_before and str(active_before.get("id") or "") == str(version.get("id") or ""):
            return _json_error("Version is already active", 400, "VERSION_ALREADY_ACTIVE")
        reason = str(payload.get("reason") or "rollback").strip()
        event = _remember_active_version(cursor, blueprint, version, user_data, "rollback", reason)
        db.conn.commit()
        return jsonify(
            {
                "success": True,
                "active_version": _normalize_json_row(version),
                "previous_active_version": _normalize_json_row(active_before) if active_before else None,
                "diff": build_agent_version_diff(active_before, version),
                "version_event": event,
            }
        )
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-blueprints/<blueprint_id>/setup", methods=["POST"])
def setup_agent_blueprint(blueprint_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        blueprint, access_error = _require_blueprint_access(cursor, blueprint_id, user_data)
        if access_error:
            return access_error
        metadata = _blueprint_metadata(blueprint)
        setup = normalize_agent_setup(payload)
        metadata["agent_setup"] = setup
        metadata["setup_completed"] = True
        _save_blueprint_metadata(cursor, blueprint_id, metadata)
        version = None
        latest_version = _load_latest_blueprint_version(cursor, blueprint_id)
        if latest_version:
            version_payload = build_version_payload_from_row(latest_version)
            input_schema = version_payload.get("inputs_schema") if isinstance(version_payload.get("inputs_schema"), dict) else {}
            input_schema["agent_setup"] = setup
            version_payload["inputs_schema"] = input_schema
            output_schema = version_payload.get("output_schema") if isinstance(version_payload.get("output_schema"), dict) else {}
            output_schema["human_review"] = True
            version_payload["output_schema"] = output_schema
            version = _insert_version(cursor, blueprint_id, version_payload, user_data)
            _remember_active_version(cursor, blueprint, version, user_data, "setup_updated")
        db.conn.commit()
        refreshed = _load_blueprint(cursor, blueprint_id)
        return jsonify({"success": True, "blueprint": _normalize_json_row(refreshed), "setup": setup, "version": version})
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-blueprints/<blueprint_id>/integrations", methods=["GET"])
def list_agent_blueprint_integrations(blueprint_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        blueprint, access_error = _require_blueprint_access(cursor, blueprint_id, user_data)
        if access_error:
            return access_error
        business_id = str(blueprint.get("business_id") or "")
        metadata = _blueprint_metadata(blueprint)
        attached_ids = _agent_integration_ids(metadata)
        attached_rows = _load_agent_integrations(cursor, business_id, attached_ids) if attached_ids else []
        all_rows = _load_agent_integrations(cursor, business_id)
        attached_lookup = {str(row.get("id") or "") for row in attached_rows}
        integrations = [_normalize_agent_integration(row, attached=True) for row in attached_rows]
        binding_status = _agent_integration_binding_status(metadata, attached_rows)
        available = [
            _normalize_agent_integration(row, attached=False)
            for row in all_rows
            if str(row.get("id") or "") not in attached_lookup
        ]
        return jsonify(
            {
                "success": True,
                "integrations": integrations,
                "available_integrations": available,
                "provider_catalog": _agent_integration_provider_catalog(),
                "external_auth_options": _load_agent_external_auth_options(cursor, business_id),
                "capability_integrations": metadata.get("capability_integrations") if isinstance(metadata.get("capability_integrations"), dict) else {},
                "custom_process": metadata.get("custom_process") if isinstance(metadata.get("custom_process"), dict) else {},
                "required_integration_bindings": metadata.get("required_integration_bindings") if isinstance(metadata.get("required_integration_bindings"), list) else [],
                "binding_status": binding_status,
            }
        )
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-blueprints/<blueprint_id>/integrations", methods=["POST"])
def save_agent_blueprint_integration(blueprint_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    provider = str(payload.get("provider") or "").strip().lower()
    if provider not in {"google_sheets", "telegram"}:
        return _json_error("Unsupported integration provider", 400, "UNSUPPORTED_PROVIDER")
    status = str(payload.get("status") or "active").strip().lower()
    if status not in {"draft", "active", "paused"}:
        return _json_error("Unsupported integration status", 400, "UNSUPPORTED_STATUS")
    config = _sanitize_agent_integration_config(provider, payload)
    if provider == "google_sheets" and not str(config.get("spreadsheet_id") or "").strip():
        return _json_error("spreadsheet_id is required for Google Sheets integration", 400, "SPREADSHEET_REQUIRED")
    limits = _sanitize_agent_integration_limits(provider, payload)
    integration_id = str(payload.get("integration_id") or payload.get("id") or "").strip()
    if not integration_id:
        integration_id = str(uuid.uuid4())
    display_name = str(payload.get("display_name") or _agent_integration_provider_label(provider)).strip()
    auth_ref = str(payload.get("auth_ref") or "").strip() or None

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        blueprint, access_error = _require_blueprint_access(cursor, blueprint_id, user_data)
        if access_error:
            return access_error
        business_id = str(blueprint.get("business_id") or "")
        cursor.execute(
            """
            SELECT id
            FROM agent_integrations
            WHERE id = %s
              AND business_id = %s
            """,
            (integration_id, business_id),
        )
        existing = cursor.fetchone()
        if existing:
            cursor.execute(
                """
                UPDATE agent_integrations
                SET provider = %s,
                    status = %s,
                    display_name = %s,
                    auth_ref = %s,
                    config_json = %s::jsonb,
                    limits_json = %s::jsonb,
                    connected_by_user_id = %s,
                    updated_at = NOW()
                WHERE id = %s
                  AND business_id = %s
                """,
                (
                    provider,
                    status,
                    display_name,
                    auth_ref,
                    json.dumps(config, ensure_ascii=False),
                    json.dumps(limits, ensure_ascii=False),
                    _user_id(user_data),
                    integration_id,
                    business_id,
                ),
            )
        else:
            cursor.execute(
                """
                INSERT INTO agent_integrations (
                    id, business_id, provider, status, display_name, auth_ref,
                    config_json, limits_json, connected_by_user_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)
                """,
                (
                    integration_id,
                    business_id,
                    provider,
                    status,
                    display_name,
                    auth_ref,
                    json.dumps(config, ensure_ascii=False),
                    json.dumps(limits, ensure_ascii=False),
                    _user_id(user_data),
                ),
            )
        cursor.execute(
            """
            SELECT id, business_id, provider, status, display_name, auth_ref,
                   config_json, limits_json, connected_by_user_id, created_at, updated_at
            FROM agent_integrations
            WHERE id = %s
              AND business_id = %s
            """,
            (integration_id, business_id),
        )
        integration = dict(cursor.fetchone())
        metadata = _sync_blueprint_integration_metadata(cursor, blueprint, integration)
        db.conn.commit()
        return jsonify(
            {
                "success": True,
                "integration": _normalize_agent_integration(integration, attached=True),
                "capability_integrations": metadata.get("capability_integrations") if isinstance(metadata.get("capability_integrations"), dict) else {},
                "custom_process": metadata.get("custom_process") if isinstance(metadata.get("custom_process"), dict) else {},
                "binding_status": _agent_integration_binding_status(metadata, [integration]),
            }
        ), 201
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-blueprints/<blueprint_id>/sources", methods=["POST"])
def add_agent_blueprint_source(blueprint_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        blueprint, access_error = _require_blueprint_access(cursor, blueprint_id, user_data)
        if access_error:
            return access_error
        metadata = _blueprint_metadata(blueprint)
        sources = metadata.get("agent_sources") if isinstance(metadata.get("agent_sources"), list) else []
        source = normalize_agent_source(payload)
        sources.append(source)
        metadata["agent_sources"] = sources[-50:]
        _save_blueprint_metadata(cursor, blueprint_id, metadata)
        db.conn.commit()
        return jsonify({"success": True, "source": source, "sources": metadata["agent_sources"]}), 201
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-blueprints/<blueprint_id>/sources/catalog", methods=["GET"])
def list_agent_blueprint_source_catalog(blueprint_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        blueprint, access_error = _require_blueprint_access(cursor, blueprint_id, user_data)
        if access_error:
            return access_error
        metadata = _blueprint_metadata(blueprint)
        sources = metadata.get("agent_sources") if isinstance(metadata.get("agent_sources"), list) else []
        catalog = build_agent_datahub_catalog(cursor, str(blueprint.get("business_id") or ""), sources)
        return jsonify({"success": True, "catalog": catalog})
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-blueprints/<blueprint_id>/sources/upload", methods=["POST"])
def upload_agent_blueprint_source(blueprint_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    uploaded_file = request.files.get("file")
    preferred_name = str(request.form.get("name") or "").strip()
    source_payload, upload_error = build_agent_source_from_upload(uploaded_file, preferred_name)
    if upload_error:
        return _json_error(str(upload_error.get("message") or "file upload failed"), 400, str(upload_error.get("code") or "UPLOAD_FAILED"))
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        blueprint, access_error = _require_blueprint_access(cursor, blueprint_id, user_data)
        if access_error:
            return access_error
        metadata = _blueprint_metadata(blueprint)
        sources = metadata.get("agent_sources") if isinstance(metadata.get("agent_sources"), list) else []
        source = normalize_agent_source(source_payload)
        sources.append(source)
        metadata["agent_sources"] = sources[-50:]
        _save_blueprint_metadata(cursor, blueprint_id, metadata)
        db.conn.commit()
        return jsonify({"success": True, "source": source, "sources": metadata["agent_sources"]}), 201
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-blueprints/<blueprint_id>/review", methods=["GET"])
def review_agent_blueprint(blueprint_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        blueprint, access_error = _require_blueprint_access(cursor, blueprint_id, user_data)
        if access_error:
            return access_error
        return jsonify({"success": True, "review": build_blueprint_review(cursor, str(blueprint.get("id") or ""))})
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-blueprints/<blueprint_id>/runs", methods=["POST"])
def start_agent_blueprint_run(blueprint_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        blueprint, access_error = _require_blueprint_access(cursor, blueprint_id, user_data)
        if access_error:
            return access_error
        version_id = str(payload.get("blueprint_version_id") or "").strip()
        if not version_id:
            active_version = _resolve_active_version(cursor, blueprint)
            version_id = str((active_version or {}).get("id") or "")
        elif not _load_blueprint_version_for_blueprint(cursor, str(blueprint.get("id") or ""), version_id):
            return _json_error("Blueprint version does not belong to this blueprint", 400, "VERSION_BLUEPRINT_MISMATCH")
        if not version_id:
            return _json_error("Blueprint has no version", 400, "NO_VERSION")
        runner = AgentBlueprintRunner(cursor, build_agent_blueprint_orchestrator())
        result = runner.start_run(version_id, payload.get("input") if isinstance(payload.get("input"), dict) else {}, user_data)
        db.conn.commit()
        if not result.get("success"):
            return _json_error(str(result.get("error") or "run failed"), 400, "RUN_FAILED")
        return jsonify(result), 201
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-runs/<run_id>", methods=["GET"])
def get_agent_run(run_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        cursor.execute("SELECT blueprint_id FROM agent_runs WHERE id = %s", (run_id,))
        row = cursor.fetchone()
        if not row:
            return _json_error("Run not found", 404, "NOT_FOUND")
        blueprint, access_error = _require_blueprint_access(cursor, str(row.get("blueprint_id") or ""), user_data)
        if access_error:
            return access_error
        runner = AgentBlueprintRunner(cursor, build_agent_blueprint_orchestrator())
        return jsonify({"success": True, "run": runner.load_run(run_id, user_data)})
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-runs/<run_id>/support-export", methods=["GET"])
def get_agent_run_support_export(run_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        cursor.execute("SELECT blueprint_id FROM agent_runs WHERE id = %s", (run_id,))
        row = cursor.fetchone()
        if not row:
            return _json_error("Run not found", 404, "NOT_FOUND")
        blueprint, access_error = _require_blueprint_access(cursor, str(row.get("blueprint_id") or ""), user_data)
        if access_error:
            return access_error
        runner = AgentBlueprintRunner(cursor, build_agent_blueprint_orchestrator())
        if str(request.args.get("format") or "").strip().lower() == "markdown":
            return Response(runner.render_run_support_export_markdown(run_id, user_data), mimetype="text/markdown")
        result = runner.build_run_support_export(run_id, user_data)
        if not result.get("success"):
            return _json_error(str(result.get("error") or "support export failed"), 400, "SUPPORT_EXPORT_FAILED")
        return jsonify(result)
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-runs/<run_id>/feedback", methods=["POST"])
def create_agent_run_feedback(run_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    feedback_text = str(payload.get("feedback") or "").strip()
    if not feedback_text:
        return _json_error("feedback is required", 400, "VALIDATION_ERROR")
    trigger_type = str(payload.get("trigger_type") or payload.get("feedback_type") or "manual_feedback").strip().lower()
    if trigger_type not in {"manual_edit", "approval_rejected", "bad_outcome", "runtime_error", "manual_feedback", "run_review"}:
        trigger_type = "manual_feedback"
    auto_activate = bool(payload.get("auto_activate") is True)
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        cursor.execute("SELECT * FROM agent_runs WHERE id = %s", (run_id,))
        run = cursor.fetchone()
        if not run:
            return _json_error("Run not found", 404, "NOT_FOUND")
        run = dict(run)
        blueprint, access_error = _require_blueprint_access(cursor, str(run.get("blueprint_id") or ""), user_data)
        if access_error:
            return access_error
        version = _load_blueprint_version_for_blueprint(cursor, str(blueprint.get("id") or ""), str(run.get("blueprint_version_id") or ""))
        if not version:
            return _json_error("Blueprint version not found", 404, "VERSION_NOT_FOUND")
        feedback = {
            "run_id": run_id,
            "feedback": feedback_text,
            "trigger_type": trigger_type,
            "manual_edit": payload.get("manual_edit") if isinstance(payload.get("manual_edit"), dict) else {},
            "outcome": payload.get("outcome") if isinstance(payload.get("outcome"), dict) else {},
            "error": payload.get("error") if isinstance(payload.get("error"), dict) else {},
            "created_by_user_id": _user_id(user_data),
            "source": "learning_loop",
            "created_at": _utc_now_text(),
        }
        metadata = _blueprint_metadata(blueprint)
        history = metadata.get("feedback_history") if isinstance(metadata.get("feedback_history"), list) else []
        history.append(feedback)
        metadata["feedback_history"] = history[-20:]
        learning_events = metadata.get("learning_events") if isinstance(metadata.get("learning_events"), list) else []
        _save_blueprint_metadata(cursor, str(blueprint.get("id") or ""), metadata)
        version_payload = build_feedback_version_payload(version, feedback)
        new_version = _insert_version(cursor, str(blueprint.get("id") or ""), version_payload, user_data)
        diff = build_agent_version_diff(version, new_version)
        event = None
        if auto_activate:
            event = _remember_active_version(cursor, blueprint, new_version, user_data, "feedback_applied", feedback_text)
        refreshed_blueprint = _load_blueprint(cursor, str(blueprint.get("id") or ""))
        refreshed_metadata = _blueprint_metadata(refreshed_blueprint or blueprint)
        learning_summary = build_learning_loop_summary(feedback, version, new_version, diff, auto_activate)
        learning_events = refreshed_metadata.get("learning_events") if isinstance(refreshed_metadata.get("learning_events"), list) else learning_events
        learning_events.append(
            {
                "run_id": run_id,
                "trigger_type": trigger_type,
                "feedback": feedback_text,
                "previous_version_id": str(version.get("id") or ""),
                "candidate_version_id": str(new_version.get("id") or ""),
                "candidate_version_number": _version_number(new_version),
                "activation_state": learning_summary["activation_state"],
                "created_by_user_id": _user_id(user_data),
                "created_at": feedback["created_at"],
            }
        )
        refreshed_metadata["learning_events"] = learning_events[-50:]
        _save_blueprint_metadata(cursor, str(blueprint.get("id") or ""), refreshed_metadata)
        db.conn.commit()
        return jsonify(
            {
                "success": True,
                "feedback": feedback,
                "version": new_version,
                "candidate_version": new_version,
                "diff": diff,
                "learning": learning_summary,
                "version_event": event,
            }
        ), 201
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-runs/<run_id>/approvals/<approval_id>/approve", methods=["POST"])
def approve_agent_run(run_id: str, approval_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    return _decide_agent_run_approval(run_id, approval_id, user_data, "approve", str(payload.get("reason") or ""))


@agent_blueprints_bp.route("/api/agent-runs/<run_id>/approvals/<approval_id>/reject", methods=["POST"])
def reject_agent_run(run_id: str, approval_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    return _decide_agent_run_approval(run_id, approval_id, user_data, "reject", str(payload.get("reason") or ""))


def _decide_agent_run_approval(run_id: str, approval_id: str, user_data: dict, decision: str, reason: str):
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        cursor.execute("SELECT blueprint_id FROM agent_runs WHERE id = %s", (run_id,))
        row = cursor.fetchone()
        if not row:
            return _json_error("Run not found", 404, "NOT_FOUND")
        blueprint, access_error = _require_blueprint_access(cursor, str(row.get("blueprint_id") or ""), user_data)
        if access_error:
            return access_error
        runner = AgentBlueprintRunner(cursor, build_agent_blueprint_orchestrator())
        if decision == "approve":
            result = runner.approve(run_id, approval_id, user_data, reason)
        else:
            result = runner.reject(run_id, approval_id, user_data, reason)
        db.conn.commit()
        if not result.get("success"):
            return _json_error(str(result.get("error") or "approval decision failed"), 400, "APPROVAL_DECISION_FAILED")
        return jsonify(result)
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()
