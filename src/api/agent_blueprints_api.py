import json
import uuid

from flask import Blueprint, jsonify, request

from core.auth_helpers import require_auth_from_request, verify_business_access
from database_manager import DatabaseManager
from services.agent_blueprint_runner import (
    AgentBlueprintRunner,
    default_supervised_outreach_version_payload,
    parse_json_field,
    normalize_steps,
)
from services.agent_blueprint_orchestrator import build_agent_blueprint_orchestrator


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
        SELECT id
        FROM agent_blueprint_versions
        WHERE id = %s
          AND blueprint_id = %s
        """,
        (version_id, blueprint_id),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


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
                   v.goal AS latest_goal
            FROM agent_blueprints b
            LEFT JOIN LATERAL (
                SELECT id, version_number, goal
                FROM agent_blueprint_versions
                WHERE blueprint_id = b.id
                ORDER BY version_number DESC
                LIMIT 1
            ) v ON TRUE
            {where_sql}
            ORDER BY b.created_at DESC
            LIMIT 200
            """,
            tuple(params),
        )
        rows = [_normalize_json_row(dict(row)) for row in (cursor.fetchall() or [])]
        return jsonify({"success": True, "blueprints": rows})
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
        cursor.execute(
            """
            SELECT *
            FROM agent_runs
            WHERE blueprint_id = %s
            ORDER BY started_at DESC
            LIMIT 50
            """,
            (blueprint_id,),
        )
        runs = [_normalize_json_row(dict(row)) for row in (cursor.fetchall() or [])]
        return jsonify({"success": True, "blueprint": _normalize_json_row(blueprint), "versions": versions, "runs": runs})
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
        db.conn.commit()
        return jsonify({"success": True, "version": version}), 201
    except Exception:
        db.conn.rollback()
        raise
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
            cursor.execute(
                """
                SELECT id
                FROM agent_blueprint_versions
                WHERE blueprint_id = %s
                ORDER BY version_number DESC
                LIMIT 1
                """,
                (blueprint.get("id"),),
            )
            version_row = cursor.fetchone()
            version_id = str((version_row or {}).get("id") or "")
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
        return jsonify({"success": True, "run": runner.load_run(run_id)})
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
