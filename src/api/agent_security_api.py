import json
import os

from flask import Blueprint, jsonify, request, send_from_directory

from auth_system import verify_session
from database_manager import DatabaseManager
from core.agent_api_security import (
    create_agent_client,
    decide_agent_client_promotion,
    ensure_agent_security_tables,
    evaluate_agent_access,
    find_agent_client_by_telegram_sender,
    build_agent_self_test_summary,
    load_agent_client_by_key,
    log_agent_action,
    mark_agent_seen,
    normalize_risk_level,
    public_agent_policy,
    request_agent_client_promotion,
    rotate_agent_client_key,
    update_agent_client,
    normalize_telegram_bot_username,
)
from core.agent_api_alerts import notify_superadmins_agent_alert
from services.prospecting_research_service import load_grants, replace_grants


agent_security_bp = Blueprint("agent_security_api", __name__)

AGENT_OPENAPI_FILENAME = "localos-agent-openapi.json"


def _agent_openapi_directories() -> list[str]:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    candidates = [
        os.getenv("FRONTEND_DIST_DIR", ""),
        os.path.join(repo_root, "frontend", "dist"),
        os.path.join(repo_root, "frontend", "public"),
    ]
    return [os.path.abspath(path) for path in candidates if path]


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


def _notify_agent_alert(cursor, title: str, details: dict | None = None) -> None:
    try:
        notify_superadmins_agent_alert(cursor, title, details)
    except Exception:
        pass


def _agent_client_metadata_from_payload(payload: dict) -> dict:
    metadata = {}
    if "telegram_bot_username" in payload:
        telegram_username = normalize_telegram_bot_username(payload.get("telegram_bot_username"))
        metadata["telegram_bot_username"] = telegram_username
    if "telegram_bot_id" in payload:
        telegram_id = str(payload.get("telegram_bot_id") or "").strip()
        metadata["telegram_bot_id"] = telegram_id
    note = str(payload.get("note") or "").strip()
    if note:
        metadata["note"] = note
    return metadata


def _parse_json_field(value, default):
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return default
    return default


@agent_security_bp.route("/api/agent-api/security/policy", methods=["GET"])
def agent_security_policy():
    return jsonify({"success": True, "policy": public_agent_policy()})


@agent_security_bp.route("/api/agent-api/openapi.json", methods=["GET"])
def agent_api_openapi_contract():
    for directory in _agent_openapi_directories():
        contract_path = os.path.join(directory, AGENT_OPENAPI_FILENAME)
        if os.path.isfile(contract_path):
            response = send_from_directory(directory, AGENT_OPENAPI_FILENAME, mimetype="application/json")
            response.headers["Cache-Control"] = "no-cache"
            return response
    return _json_error("Agent API OpenAPI contract is not built", 404, "CONTRACT_NOT_FOUND")


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
    prospecting_grants = payload.get("prospecting_grants")
    if prospecting_grants is not None and not isinstance(prospecting_grants, list):
        return _json_error("prospecting_grants must be an array", 400, "VALIDATION_ERROR")
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
            metadata={
                "created_by": "superadmin",
                **_agent_client_metadata_from_payload(payload),
            },
        )
        grants = replace_grants(cursor, result["client_id"], prospecting_grants or [])
        db.conn.commit()
        return jsonify(
            {
                "success": True,
                "client": {
                    "client_id": result["client_id"],
                    "status": result["status"],
                    "allowed_scopes": result["allowed_scopes"],
                    "prospecting_grants": grants,
                    "agent_key": result["agent_key"],
                    "agent_key_warning": "Store this key now. It is returned only once.",
                },
            }
        )
    except ValueError as error:
        db.conn.rollback()
        return _json_error(str(error), 400, "VALIDATION_ERROR")
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
                   allowed_scopes, rate_limits, metadata_json, created_at, updated_at, last_seen_at
            FROM agent_clients
            ORDER BY created_at DESC
            LIMIT 200
            """
        )
        rows = cursor.fetchall() or []
        clients = []
        for row in rows:
            item = dict(row)
            for key in ["allowed_scopes", "rate_limits", "metadata_json"]:
                value = item.get(key)
                if isinstance(value, str):
                    try:
                        item[key] = json.loads(value)
                    except Exception:
                        item[key] = [] if key == "allowed_scopes" else {}
            item["prospecting_grants"] = load_grants(cursor, str(item.get("id") or ""))
            clients.append(item)
        return jsonify({"success": True, "clients": clients})
    finally:
        db.close()


@agent_security_bp.route("/api/agent-api/clients/<client_id>", methods=["PATCH", "OPTIONS"])
def update_agent_client_endpoint(client_id: str):
    if request.method == "OPTIONS":
        return "", 200
    user_data, error_response = _require_superadmin()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    allowed_scopes = payload.get("allowed_scopes")
    if allowed_scopes is not None and not isinstance(allowed_scopes, list):
        return _json_error("allowed_scopes must be an array", 400, "VALIDATION_ERROR")
    rate_limits = payload.get("rate_limits")
    if rate_limits is not None and not isinstance(rate_limits, dict):
        return _json_error("rate_limits must be an object", 400, "VALIDATION_ERROR")
    prospecting_grants = payload.get("prospecting_grants")
    if prospecting_grants is not None and not isinstance(prospecting_grants, list):
        return _json_error("prospecting_grants must be an array", 400, "VALIDATION_ERROR")
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        metadata = {
            "updated_by": str(user_data.get("user_id") or user_data.get("id") or ""),
            "update_note": str(payload.get("note") or "").strip(),
            **_agent_client_metadata_from_payload(payload),
        }
        result = update_agent_client(
            cursor,
            client_id=client_id,
            status=payload.get("status"),
            allowed_scopes=allowed_scopes,
            rate_limits=rate_limits,
            metadata=metadata,
        )
        if not result:
            return _json_error("Agent client not found", 404, "NOT_FOUND")
        grants = replace_grants(cursor, client_id, prospecting_grants) if prospecting_grants is not None else load_grants(cursor, client_id)
        log_agent_action(
            cursor,
            agent_client_id=client_id,
            business_id=None,
            action_type="agent_client_update",
            capability="agent_api.security",
            required_scope="superadmin",
            risk_level="medium",
            input_summary={
                "status": payload.get("status"),
                "allowed_scopes": allowed_scopes,
                "rate_limits": rate_limits,
                "prospecting_grants": grants,
            },
            status="completed",
            reason_code="SUPERADMIN_UPDATE",
            ip=str(_request_meta().get("ip") or ""),
            user_agent=str(_request_meta().get("user_agent") or ""),
        )
        _notify_agent_alert(
            cursor,
            "Agent client settings changed",
            {
                "client_id": client_id,
                "status": result.get("status"),
                "reason_code": "SUPERADMIN_UPDATE",
            },
        )
        db.conn.commit()
        result["prospecting_grants"] = grants
        return jsonify({"success": True, "client": result})
    except ValueError as error:
        db.conn.rollback()
        return _json_error(str(error), 400, "VALIDATION_ERROR")
    finally:
        db.close()


@agent_security_bp.route("/api/agent-api/clients/telegram-binding/lookup", methods=["POST", "OPTIONS"])
def lookup_agent_client_by_telegram_binding_endpoint():
    if request.method == "OPTIONS":
        return "", 200
    user_data, error_response = _require_superadmin()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    sender = {
        "username": normalize_telegram_bot_username(payload.get("telegram_bot_username")),
        "telegram_id": str(payload.get("telegram_bot_id") or "").strip(),
    }
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        client = find_agent_client_by_telegram_sender(cursor, sender)
        if not client:
            return jsonify({"success": True, "client": None})
        return jsonify({"success": True, "client": client})
    finally:
        db.close()


@agent_security_bp.route("/api/agent-api/clients/<client_id>/rotate-key", methods=["POST", "OPTIONS"])
def rotate_agent_client_key_endpoint(client_id: str):
    if request.method == "OPTIONS":
        return "", 200
    _, error_response = _require_superadmin()
    if error_response:
        return error_response
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        result = rotate_agent_client_key(cursor, client_id)
        if not result:
            return _json_error("Agent client not found", 404, "NOT_FOUND")
        log_agent_action(
            cursor,
            agent_client_id=client_id,
            business_id=None,
            action_type="agent_client_key_rotate",
            capability="agent_api.security",
            required_scope="superadmin",
            risk_level="high",
            input_summary={"client_id": client_id},
            status="completed",
            reason_code="KEY_ROTATED",
            ip=str(_request_meta().get("ip") or ""),
            user_agent=str(_request_meta().get("user_agent") or ""),
        )
        _notify_agent_alert(
            cursor,
            "Agent key rotated",
            {
                "client_id": client_id,
                "status": result.get("status"),
                "reason_code": "KEY_ROTATED",
            },
        )
        db.conn.commit()
        return jsonify(
            {
                "success": True,
                "client": {
                    "client_id": result["client_id"],
                    "status": result["status"],
                    "agent_key": result["agent_key"],
                    "agent_key_warning": "Store this key now. It is returned only once.",
                },
            }
        )
    finally:
        db.close()


@agent_security_bp.route("/api/agent-api/clients/promotion/request", methods=["POST", "OPTIONS"])
def request_agent_client_promotion_endpoint():
    if request.method == "OPTIONS":
        return "", 200
    payload = request.get_json(silent=True) or {}
    requested_scopes = payload.get("requested_scopes")
    if requested_scopes is not None and not isinstance(requested_scopes, list):
        return _json_error("requested_scopes must be an array", 400, "VALIDATION_ERROR")
    db = DatabaseManager()
    cursor = db.conn.cursor()
    meta = _request_meta()
    try:
        client = _load_agent_client(cursor)
        access = evaluate_agent_access(
            client,
            required_scope="approvals:create",
            risk_level="low",
            action_type="agent_client_promotion_request",
        )
        if not access.get("ok"):
            log_agent_action(
                cursor,
                agent_client_id=str(client.get("id")) if client else None,
                business_id=None,
                action_type="agent_client_promotion_request",
                capability="agent_api.security",
                required_scope="approvals:create",
                risk_level="high",
                input_summary=payload,
                status="denied",
                reason_code=str(access.get("code") or "DENIED"),
                ip=str(meta.get("ip") or ""),
                user_agent=str(meta.get("user_agent") or ""),
            )
            _notify_agent_alert(
                cursor,
                "Promotion request denied",
                {
                    "client_id": str(client.get("id")) if client else "",
                    "action_type": "agent_client_promotion_request",
                    "risk_level": "high",
                    "status": "denied",
                    "reason_code": str(access.get("code") or "DENIED"),
                },
            )
            db.conn.commit()
            return _json_error(str(access.get("reason") or "agent access denied"), int(access.get("http_status") or 403), str(access.get("code") or "DENIED"))
        mark_agent_seen(cursor, str(client.get("id")))
        promotion_id = request_agent_client_promotion(
            cursor,
            client=client,
            requested_scopes=requested_scopes,
            use_case=str(payload.get("use_case") or ""),
            contact=str(payload.get("contact") or ""),
        )
        _notify_agent_alert(
            cursor,
            "Agent requested live promotion",
            {
                "client": str(client.get("organization_name") or ""),
                "client_id": str(client.get("id") or ""),
                "action_type": "agent_client_promotion_request",
                "risk_level": "high",
                "status": "pending_human",
                "approval_id": promotion_id,
            },
        )
        db.conn.commit()
        return jsonify({"success": True, "promotion_id": promotion_id, "status": "pending_human"})
    finally:
        db.close()


@agent_security_bp.route("/api/agent-api/self-test", methods=["POST", "OPTIONS"])
def agent_self_test_endpoint():
    if request.method == "OPTIONS":
        return "", 200
    payload = request.get_json(silent=True) or {}
    db = DatabaseManager()
    cursor = db.conn.cursor()
    meta = _request_meta()
    try:
        client = _load_agent_client(cursor)
        access = evaluate_agent_access(
            client,
            required_scope="",
            risk_level="low",
            action_type="agent_api_self_test",
        )
        if not access.get("ok"):
            log_agent_action(
                cursor,
                agent_client_id=str(client.get("id")) if client else None,
                business_id=None,
                action_type="agent_api_self_test",
                capability="agent_api.onboarding",
                required_scope=None,
                risk_level="low",
                input_summary={
                    "purpose": str(payload.get("purpose") or "sandbox_self_test")[:120],
                    "has_key": bool(_agent_key_from_request()),
                },
                status="denied",
                reason_code=str(access.get("code") or "DENIED"),
                ip=str(meta.get("ip") or ""),
                user_agent=str(meta.get("user_agent") or ""),
            )
            db.conn.commit()
            return _json_error(
                str(access.get("reason") or "agent access denied"),
                int(access.get("http_status") or 403),
                str(access.get("code") or "DENIED"),
            )
        mark_agent_seen(cursor, str(client.get("id")))
        summary = build_agent_self_test_summary(client, access)
        ledger_id = log_agent_action(
            cursor,
            agent_client_id=str(client.get("id")),
            business_id=None,
            action_type="agent_api_self_test",
            capability="agent_api.onboarding",
            required_scope=None,
            risk_level="low",
            input_summary={
                "purpose": str(payload.get("purpose") or "sandbox_self_test")[:120],
                "requested_checks": payload.get("checks") if isinstance(payload.get("checks"), list) else [],
            },
            output_summary={
                "status": summary.get("client", {}).get("status"),
                "scopes": summary.get("client", {}).get("allowed_scopes"),
                "can_create_approval_request": summary.get("available", {}).get("can_create_approval_request"),
            },
            status="completed",
            reason_code="SELF_TEST_OK",
            ip=str(meta.get("ip") or ""),
            user_agent=str(meta.get("user_agent") or ""),
            metadata={"onboarding_step": "self_test"},
        )
        db.conn.commit()
        return jsonify({"success": True, "self_test": summary, "ledger_id": ledger_id})
    finally:
        db.close()


@agent_security_bp.route("/api/agent-api/clients/<client_id>/promotion/decide", methods=["POST", "OPTIONS"])
def decide_agent_client_promotion_endpoint(client_id: str):
    if request.method == "OPTIONS":
        return "", 200
    user_data, error_response = _require_superadmin()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    allowed_scopes = payload.get("allowed_scopes")
    if allowed_scopes is not None and not isinstance(allowed_scopes, list):
        return _json_error("allowed_scopes must be an array", 400, "VALIDATION_ERROR")
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        result = decide_agent_client_promotion(
            cursor,
            client_id=client_id,
            decision=str(payload.get("decision") or ""),
            reviewer_user_id=str(user_data.get("user_id") or user_data.get("id") or ""),
            allowed_scopes=allowed_scopes,
            note=str(payload.get("note") or ""),
        )
        if not result:
            return _json_error("Agent client not found", 404, "NOT_FOUND")
        _notify_agent_alert(
            cursor,
            "Agent promotion decision",
            {
                "client_id": client_id,
                "decision": result.get("decision"),
                "status": result.get("status"),
                "reason_code": "PROMOTION_DECISION",
            },
        )
        db.conn.commit()
        return jsonify({"success": True, "promotion": result})
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
            _notify_agent_alert(
                cursor,
                "Agent action denied",
                {
                    "client_id": str(client.get("id")) if client else "",
                    "action_type": action_type or "approval_request",
                    "risk_level": risk_level,
                    "status": "denied",
                    "reason_code": str(access.get("code") or "DENIED"),
                    "business_id": business_id,
                },
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
        if risk_level in {"high", "critical"}:
            _notify_agent_alert(
                cursor,
                "High-risk agent approval request",
                {
                    "client": str(client.get("organization_name") or ""),
                    "client_id": str(client.get("id") or ""),
                    "action_type": action_type,
                    "risk_level": risk_level,
                    "status": "pending_human",
                    "approval_id": approval_id,
                    "business_id": business_id,
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
        items = []
        for row in rows:
            item = dict(row)
            item["input_summary"] = _parse_json_field(item.get("input_summary"), item.get("input_summary") or "")
            item["output_summary"] = _parse_json_field(item.get("output_summary"), item.get("output_summary") or "")
            item["metadata_json"] = _parse_json_field(item.get("metadata_json"), {})
            items.append(item)
        return jsonify({"success": True, "items": items})
    finally:
        db.close()


@agent_security_bp.route("/api/agent-api/discovery", methods=["GET"])
def agent_discovery_events_endpoint():
    user_data, error_response = _require_superadmin()
    if error_response:
        return error_response
    limit = max(1, min(int(request.args.get("limit", "100") or 100), 500))
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_agent_security_tables(cursor)
        cursor.execute(
            """
            SELECT id, event_type, path, method, status_code, agent_family,
                   ip_hash, user_agent, referrer, metadata_json, created_at
            FROM agent_discovery_events
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cursor.fetchall() or []
        cursor.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE event_type = 'docs_view')::INT docs_views,
                COUNT(*) FILTER (WHERE event_type = 'machine_readable_docs')::INT machine_docs,
                COUNT(*) FILTER (WHERE event_type = 'agent_api')::INT api_hits
            FROM agent_discovery_events
            WHERE created_at >= NOW() - INTERVAL '24 hours'
            """
        )
        summary_row = cursor.fetchone()
        summary = dict(summary_row) if summary_row else {}
        return jsonify({"success": True, "items": [dict(row) for row in rows], "summary_24h": summary})
    finally:
        db.close()
