import json

from flask import Blueprint, jsonify, request

from auth_system import verify_session
from database_manager import DatabaseManager
from core.agent_api_security import (
    create_agent_client,
    ensure_agent_security_tables,
    evaluate_agent_access,
    load_agent_client_by_key,
    log_agent_action,
    mark_agent_seen,
    normalize_risk_level,
    public_agent_policy,
)


agent_security_bp = Blueprint("agent_security_api", __name__)


def _json_error(message: str, status: int, code: str):
    return jsonify({"success": False, "error": message, "code": code}), status


def _auth_user():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header.replace("Bearer ", "", 1).strip()
    if not token:
        return None
    return verify_session(token)


def _require_superadmin():
    user_data = _auth_user()
    if not user_data:
        return None, _json_error("Authorization required", 401, "AUTH_REQUIRED")
    if not user_data.get("is_superadmin"):
        return None, _json_error("Superadmin required", 403, "SUPERADMIN_REQUIRED")
    return user_data, None


def _agent_key_from_request() -> str:
    header_value = str(request.headers.get("X-LocalOS-Agent-Key") or "").strip()
    if header_value:
        return header_value
    auth_header = str(request.headers.get("Authorization") or "").strip()
    if auth_header.startswith("Bearer "):
        return auth_header.replace("Bearer ", "", 1).strip()
    return ""


def _request_meta() -> dict:
    return {
        "ip": request.headers.get("X-Forwarded-For", request.remote_addr or ""),
        "user_agent": request.headers.get("User-Agent", ""),
    }


def _load_agent_client(cursor):
    agent_key = _agent_key_from_request()
    if not agent_key:
        return None
    return load_agent_client_by_key(cursor, agent_key)


@agent_security_bp.route("/api/agent-api/security/policy", methods=["GET"])
def agent_security_policy():
    return jsonify({"success": True, "policy": public_agent_policy()})


@agent_security_bp.route("/api/agent-api/clients", methods=["POST", "OPTIONS"])
def create_agent_client_endpoint():
    if request.method == "OPTIONS":
        return "", 200
    user_data, error_response = _require_superadmin()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    organization_name = str(payload.get("organization_name") or "").strip()
    contact_email = str(payload.get("contact_email") or "").strip().lower()
    if not organization_name or not contact_email:
        return _json_error("organization_name and contact_email are required", 400, "VALIDATION_ERROR")
    status = str(payload.get("status") or "sandbox").strip().lower()
    if status == "live":
        status = "sandbox"
    allowed_scopes = payload.get("allowed_scopes")
    if not isinstance(allowed_scopes, list):
        allowed_scopes = None
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        result = create_agent_client(
            cursor,
            owner_user_id=str(user_data.get("user_id") or user_data.get("id") or ""),
            organization_name=organization_name,
            contact_email=contact_email,
            allowed_scopes=allowed_scopes,
            status=status,
            rate_limits=payload.get("rate_limits") if isinstance(payload.get("rate_limits"), dict) else None,
            metadata={"created_by": "superadmin", "note": str(payload.get("note") or "").strip()},
        )
        db.conn.commit()
        return jsonify(
            {
                "success": True,
                "client": {
                    "client_id": result["client_id"],
                    "status": result["status"],
                    "allowed_scopes": result["allowed_scopes"],
                    "agent_key": result["agent_key"],
                    "agent_key_warning": "Store this key now. It is returned only once.",
                },
            }
        )
    finally:
        db.close()


@agent_security_bp.route("/api/agent-api/clients", methods=["GET"])
def list_agent_clients_endpoint():
    user_data, error_response = _require_superadmin()
    if error_response:
        return error_response
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_agent_security_tables(cursor)
        cursor.execute(
            """
            SELECT id, owner_user_id, organization_name, contact_email, status,
                   allowed_scopes, rate_limits, created_at, updated_at, last_seen_at
            FROM agent_clients
            ORDER BY created_at DESC
            LIMIT 200
            """
        )
        rows = cursor.fetchall() or []
        clients = []
        for row in rows:
            item = dict(row)
            for key in ["allowed_scopes", "rate_limits"]:
                value = item.get(key)
                if isinstance(value, str):
                    try:
                        item[key] = json.loads(value)
                    except Exception:
                        item[key] = [] if key == "allowed_scopes" else {}
            clients.append(item)
        return jsonify({"success": True, "clients": clients})
    finally:
        db.close()


@agent_security_bp.route("/api/agent-api/approvals/request", methods=["POST", "OPTIONS"])
def agent_approval_request_endpoint():
    if request.method == "OPTIONS":
        return "", 200
    payload = request.get_json(silent=True) or {}
    action_type = str(payload.get("action_type") or "").strip()
    business_id = str(payload.get("business_id") or "").strip()
    capability = str(payload.get("capability") or "").strip() or None
    risk_level = normalize_risk_level(str(payload.get("risk_level") or ""), action_type)
    if not action_type:
        return _json_error("action_type is required", 400, "VALIDATION_ERROR")
    db = DatabaseManager()
    cursor = db.conn.cursor()
    meta = _request_meta()
    try:
        client = _load_agent_client(cursor)
        access = evaluate_agent_access(
            client,
            required_scope="approvals:create",
            risk_level="medium",
            action_type="approval_request",
            business_id=business_id,
        )
        if not access.get("ok"):
            log_agent_action(
                cursor,
                agent_client_id=str(client.get("id")) if client else None,
                business_id=business_id or None,
                action_type=action_type or "approval_request",
                capability=capability,
                required_scope="approvals:create",
                risk_level=risk_level,
                input_summary=payload.get("input_summary") or payload,
                status="denied",
                reason_code=str(access.get("code") or "DENIED"),
                ip=str(meta.get("ip") or ""),
                user_agent=str(meta.get("user_agent") or ""),
            )
            db.conn.commit()
            return _json_error(str(access.get("reason") or "agent access denied"), int(access.get("http_status") or 403), str(access.get("code") or "DENIED"))
        mark_agent_seen(cursor, str(client.get("id")))
        approval_id = log_agent_action(
            cursor,
            agent_client_id=str(client.get("id")),
            business_id=business_id or None,
            action_type=action_type,
            capability=capability,
            required_scope="approvals:create",
            risk_level=risk_level,
            input_summary=payload.get("input_summary") or payload,
            output_summary=payload.get("proposed_output") or "",
            approval_id=None,
            status="pending_human",
            reason_code="APPROVAL_REQUIRED",
            ip=str(meta.get("ip") or ""),
            user_agent=str(meta.get("user_agent") or ""),
            metadata={
                "requested_scope": payload.get("requested_scope"),
                "risk_level": risk_level,
                "proposed_output": payload.get("proposed_output"),
            },
        )
        db.conn.commit()
        return jsonify(
            {
                "success": True,
                "approval_id": approval_id,
                "status": "pending_human",
                "risk_level": risk_level,
                "message": "Approval request recorded. Human approval is required before execution.",
            }
        )
    finally:
        db.close()


@agent_security_bp.route("/api/agent-api/ledger", methods=["GET"])
def agent_action_ledger_endpoint():
    user_data, error_response = _require_superadmin()
    if error_response:
        return error_response
    limit = max(1, min(int(request.args.get("limit", "100") or 100), 500))
    business_id = str(request.args.get("business_id") or "").strip()
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_agent_security_tables(cursor)
        if business_id:
            cursor.execute(
                """
                SELECT id, agent_client_id, business_id, action_type, capability, required_scope,
                       risk_level, input_summary, output_summary, approval_id, status, reason_code,
                       ip, user_agent, metadata_json, created_at
                FROM agent_action_ledger
                WHERE business_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (business_id, limit),
            )
        else:
            cursor.execute(
                """
                SELECT id, agent_client_id, business_id, action_type, capability, required_scope,
                       risk_level, input_summary, output_summary, approval_id, status, reason_code,
                       ip, user_agent, metadata_json, created_at
                FROM agent_action_ledger
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
        rows = cursor.fetchall() or []
        return jsonify({"success": True, "items": [dict(row) for row in rows]})
    finally:
        db.close()
