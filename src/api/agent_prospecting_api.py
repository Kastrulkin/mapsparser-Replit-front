"""Scoped prospecting endpoints for the personal Codex skill."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from psycopg2.extras import Json, RealDictCursor

from core.agent_api_security import (
    evaluate_agent_access,
    load_agent_client_by_key,
    log_agent_action,
    mark_agent_seen,
)
from pg_db_utils import get_db_connection
from services.prospecting_research_service import (
    IMPORT_MODES,
    grant_allows,
    import_report,
    load_context,
    parse_report,
    prepare_workstream_artifacts,
    preview_report,
)


agent_prospecting_bp = Blueprint("agent_prospecting_api", __name__)


def _agent_key():
    header = str(request.headers.get("X-LocalOS-Agent-Key") or "").strip()
    if header:
        return header
    authorization = str(request.headers.get("Authorization") or "").strip()
    if authorization.startswith("Bearer "):
        return authorization.replace("Bearer ", "", 1).strip()
    return ""


def _request_meta():
    return {
        "ip": request.headers.get("X-Forwarded-For", request.remote_addr or ""),
        "user_agent": request.headers.get("User-Agent", ""),
    }


def _error(message, status, code):
    return jsonify({"success": False, "error": message, "code": code}), status


def _authorized_context(required_scope, risk_level, action_type, workstream_type, business_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    client = load_agent_client_by_key(cursor, _agent_key()) if _agent_key() else None
    access = evaluate_agent_access(
        client,
        required_scope=required_scope,
        risk_level=risk_level,
        action_type=action_type,
        business_id=business_id or "",
    )
    grant_ok = bool(client) and grant_allows(
        cursor,
        str(client.get("id") or ""),
        workstream_type,
        business_id,
    )
    if access.get("ok") and not grant_ok:
        access = {
            "ok": False,
            "http_status": 403,
            "code": "PROSPECTING_GRANT_REQUIRED",
            "reason": "This agent client has no grant for the requested prospecting context",
        }
    return conn, cursor, client, access


def _log(cursor, client, action_type, scope, status, code, business_id=None, input_summary=None, output_summary=None):
    meta = _request_meta()
    return log_agent_action(
        cursor,
        agent_client_id=str(client.get("id") or "") if client else None,
        business_id=business_id,
        action_type=action_type,
        capability="prospecting.research",
        required_scope=scope,
        risk_level="medium" if action_type != "prospecting_context_read" else "low",
        input_summary=input_summary or {},
        output_summary=output_summary or {},
        status=status,
        reason_code=code,
        ip=str(meta["ip"]),
        user_agent=str(meta["user_agent"]),
    )


@agent_prospecting_bp.route("/api/agent-api/prospecting/context", methods=["GET"])
def prospecting_context():
    mode = str(request.args.get("mode") or "").strip().lower()
    business_id = str(request.args.get("business_id") or "").strip() or None
    workstream_type = IMPORT_MODES.get(mode)
    if not workstream_type:
        return _error("Unsupported prospecting mode", 400, "VALIDATION_ERROR")
    if workstream_type == "localos_sales":
        business_id = None
    conn, cursor, client, access = _authorized_context(
        "prospecting:context:read",
        "low",
        "prospecting_context_read",
        workstream_type,
        business_id,
    )
    try:
        if not access.get("ok"):
            _log(cursor, client, "prospecting_context_read", "prospecting:context:read", "denied", str(access.get("code") or "DENIED"), business_id)
            conn.commit()
            return _error(str(access.get("reason") or "Access denied"), int(access.get("http_status") or 403), str(access.get("code") or "DENIED"))
        context = load_context(cursor, mode, business_id)
        mark_agent_seen(cursor, str(client["id"]))
        _log(cursor, client, "prospecting_context_read", "prospecting:context:read", "completed", "OK", business_id, output_summary={"mode": mode})
        conn.commit()
        return jsonify({"success": True, "context": context})
    except LookupError as error:
        conn.rollback()
        return _error(str(error), 404, "NOT_FOUND")
    finally:
        conn.close()


@agent_prospecting_bp.route("/api/agent-api/prospecting/import-preview", methods=["POST"])
def prospecting_import_preview():
    payload = request.get_json(silent=True) or {}
    try:
        parsed = parse_report(payload)
    except ValueError as error:
        return _error(str(error), 400, "VALIDATION_ERROR")
    conn, cursor, client, access = _authorized_context(
        "prospecting:import",
        "medium",
        "prospecting_import_preview",
        parsed["workstream_type"],
        parsed["client_business_id"],
    )
    try:
        if not access.get("ok"):
            _log(cursor, client, "prospecting_import_preview", "prospecting:import", "denied", str(access.get("code") or "DENIED"), parsed["client_business_id"])
            conn.commit()
            return _error(str(access.get("reason") or "Access denied"), int(access.get("http_status") or 403), str(access.get("code") or "DENIED"))
        items = preview_report(cursor, parsed)
        mark_agent_seen(cursor, str(client["id"]))
        _log(
            cursor,
            client,
            "prospecting_import_preview",
            "prospecting:import",
            "completed",
            "OK",
            parsed["client_business_id"],
            input_summary={"candidate_count": len(items)},
            output_summary={"ambiguous_count": sum(1 for item in items if item["action"] == "ambiguous")},
        )
        conn.commit()
        return jsonify({"success": True, "items": items, "report_hash": parsed["report_hash"]})
    finally:
        conn.close()


@agent_prospecting_bp.route("/api/agent-api/prospecting/import", methods=["POST"])
def prospecting_import():
    payload = request.get_json(silent=True) or {}
    try:
        parsed = parse_report(payload)
    except ValueError as error:
        return _error(str(error), 400, "VALIDATION_ERROR")
    candidate_ids = payload.get("candidate_ids") if isinstance(payload.get("candidate_ids"), list) else []
    candidate_ids = [str(item).strip() for item in candidate_ids if str(item).strip()]
    idempotency_key = str(payload.get("idempotency_key") or "").strip()
    if not candidate_ids or not idempotency_key:
        return _error("candidate_ids and idempotency_key are required", 400, "VALIDATION_ERROR")
    if len(idempotency_key) > 200:
        return _error("idempotency_key is too long", 400, "VALIDATION_ERROR")
    conn, cursor, client, access = _authorized_context(
        "prospecting:import",
        "medium",
        "prospecting_import",
        parsed["workstream_type"],
        parsed["client_business_id"],
    )
    try:
        if not access.get("ok"):
            _log(cursor, client, "prospecting_import", "prospecting:import", "denied", str(access.get("code") or "DENIED"), parsed["client_business_id"])
            conn.commit()
            return _error(str(access.get("reason") or "Access denied"), int(access.get("http_status") or 403), str(access.get("code") or "DENIED"))
        result = import_report(conn, parsed, candidate_ids, str(client["id"]), idempotency_key)
        prepared = []
        if result.get("reused"):
            prepared = result.get("prepared") if isinstance(result.get("prepared"), list) else []
        else:
            draft_access = evaluate_agent_access(
                client,
                required_scope="prospecting:outreach:draft",
                risk_level="medium",
                action_type="prospecting_prepare_draft",
                business_id=parsed["client_business_id"] or "",
            )
            if draft_access.get("ok"):
                for item in result.get("imported") or []:
                    try:
                        prepared.append(
                            {
                                "workstream_id": item["workstream_id"],
                                "result": prepare_workstream_artifacts(item["workstream_id"], str(client["id"])),
                            }
                        )
                    except Exception as error:
                        prepared.append({"workstream_id": item["workstream_id"], "error": str(error)})
            else:
                prepared.append({"status": "not_prepared", "reason": str(draft_access.get("code") or "SCOPE_REQUIRED")})
        result["prepared"] = prepared
        result["external_send_performed"] = False
        if not result.get("reused"):
            cursor.execute(
                """
                UPDATE agent_prospecting_imports
                SET result_json = %s
                WHERE agent_client_id = %s AND idempotency_key = %s
                """,
                (Json(result), str(client["id"]), idempotency_key),
            )
        _log(
            cursor,
            client,
            "prospecting_import",
            "prospecting:import",
            "completed",
            "OK",
            parsed["client_business_id"],
            input_summary={"selected_count": len(candidate_ids), "idempotency_key": idempotency_key},
            output_summary={"imported_count": len(result.get("imported") or []), "skipped_count": len(result.get("skipped") or [])},
        )
        conn.commit()
        return jsonify(result)
    except ValueError as error:
        conn.rollback()
        _log(
            cursor,
            client,
            "prospecting_import",
            "prospecting:import",
            "denied",
            "IDEMPOTENCY_CONFLICT",
            parsed["client_business_id"],
            input_summary={"idempotency_key": idempotency_key},
        )
        conn.commit()
        return _error(str(error), 409, "IDEMPOTENCY_CONFLICT")
    except Exception:
        conn.rollback()
        _log(
            cursor,
            client,
            "prospecting_import",
            "prospecting:import",
            "failed",
            "INTERNAL_ERROR",
            parsed["client_business_id"],
            input_summary={"selected_count": len(candidate_ids)},
        )
        conn.commit()
        return _error("Prospecting import failed", 500, "INTERNAL_ERROR")
    finally:
        conn.close()


@agent_prospecting_bp.route("/api/agent-api/prospecting/workstreams/<workstream_id>/prepare", methods=["POST"])
def prospecting_prepare(workstream_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    client = load_agent_client_by_key(cursor, _agent_key()) if _agent_key() else None
    access = evaluate_agent_access(
        client,
        required_scope="prospecting:outreach:draft",
        risk_level="medium",
        action_type="prospecting_prepare_draft",
        business_id="",
    )
    business_id = None
    try:
        if not access.get("ok"):
            _log(cursor, client, "prospecting_prepare_draft", "prospecting:outreach:draft", "denied", str(access.get("code") or "DENIED"))
            conn.commit()
            return _error(str(access.get("reason") or "Access denied"), int(access.get("http_status") or 403), str(access.get("code") or "DENIED"))
        cursor.execute(
            "SELECT workstream_type, client_business_id FROM lead_workstreams WHERE id = %s LIMIT 1",
            (workstream_id,),
        )
        workstream = cursor.fetchone()
        if not workstream:
            _log(
                cursor,
                client,
                "prospecting_prepare_draft",
                "prospecting:outreach:draft",
                "denied",
                "NOT_FOUND",
                input_summary={"workstream_id": workstream_id},
            )
            conn.commit()
            return _error("Lead workstream not found", 404, "NOT_FOUND")
        workstream_type = str(workstream["workstream_type"])
        business_id = str(workstream.get("client_business_id") or "").strip() or None
        if not grant_allows(cursor, str(client.get("id") or ""), workstream_type, business_id):
            _log(
                cursor,
                client,
                "prospecting_prepare_draft",
                "prospecting:outreach:draft",
                "denied",
                "PROSPECTING_GRANT_REQUIRED",
                business_id,
                input_summary={"workstream_id": workstream_id},
            )
            conn.commit()
            return _error(
                "This agent client has no grant for the requested prospecting context",
                403,
                "PROSPECTING_GRANT_REQUIRED",
            )
        result = prepare_workstream_artifacts(workstream_id, str(client["id"]))
        _log(
            cursor,
            client,
            "prospecting_prepare_draft",
            "prospecting:outreach:draft",
            "completed",
            "OK",
            business_id,
            input_summary={"workstream_id": workstream_id},
            output_summary={"room_id": str((result.get("room") or {}).get("id") or ""), "external_send_performed": False},
        )
        conn.commit()
        return jsonify(result)
    except Exception:
        conn.rollback()
        _log(
            cursor,
            client,
            "prospecting_prepare_draft",
            "prospecting:outreach:draft",
            "failed",
            "INTERNAL_ERROR",
            business_id,
            input_summary={"workstream_id": workstream_id},
        )
        conn.commit()
        return _error("Prospecting draft preparation failed", 500, "INTERNAL_ERROR")
    finally:
        conn.close()
