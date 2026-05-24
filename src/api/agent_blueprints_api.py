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
from services.agent_blueprint_draft_builder import build_agent_blueprint_draft
from services.agent_blueprint_workspace import (
    build_blueprint_review,
    build_feedback_version_payload,
    build_version_payload_from_row,
    normalize_agent_setup,
    normalize_agent_source,
    workspace_parse_json_field,
)


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

    draft = build_agent_blueprint_draft(description)
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
        return jsonify(
            {
                "success": True,
                "blueprint": _normalize_json_row(blueprint),
                "versions": versions,
                "runs": runs,
                "approval_queue": approval_queue,
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
        db.conn.commit()
        return jsonify({"success": True, "version": version}), 201
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
        db.conn.commit()
        refreshed = _load_blueprint(cursor, blueprint_id)
        return jsonify({"success": True, "blueprint": _normalize_json_row(refreshed), "setup": setup, "version": version})
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


@agent_blueprints_bp.route("/api/agent-runs/<run_id>/feedback", methods=["POST"])
def create_agent_run_feedback(run_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    feedback_text = str(payload.get("feedback") or "").strip()
    if not feedback_text:
        return _json_error("feedback is required", 400, "VALIDATION_ERROR")
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
            "created_by_user_id": _user_id(user_data),
            "source": "run_review",
        }
        metadata = _blueprint_metadata(blueprint)
        history = metadata.get("feedback_history") if isinstance(metadata.get("feedback_history"), list) else []
        history.append(feedback)
        metadata["feedback_history"] = history[-20:]
        _save_blueprint_metadata(cursor, str(blueprint.get("id") or ""), metadata)
        version_payload = build_feedback_version_payload(version, feedback)
        new_version = _insert_version(cursor, str(blueprint.get("id") or ""), version_payload, user_data)
        db.conn.commit()
        return jsonify({"success": True, "feedback": feedback, "version": new_version}), 201
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
