"""Explicitly provisioned internal integration; disabled until tenant binding exists."""
import logging
import os
from flask import Blueprint, jsonify, request
from core.agent_api_security import evaluate_agent_access, load_agent_client_by_key, log_agent_action
from pg_db_utils import get_db_connection
from services.business_permissions import load_actor, require_permission
from services.inbound_case_contract import CaseError
from services.inbound_case_service import InboundCaseService

inbound_cases_bp = Blueprint("inbound_cases", __name__)
logger = logging.getLogger(__name__)


def membership(cursor, business_id, user):
    actor = load_actor(cursor, user["user_id"])
    actor["is_superadmin"] = False  # A mapping cannot grant global-administrator access.
    require_permission(cursor, business_id, actor, "operations.write")
    return True


def dispatch(operation, run_id=None):
    if os.getenv("LOCALOS_INBOUND_CASES_ENABLED", "false").lower() != "true":
        return jsonify(success=False, code="case_integration_disabled"), 503
    if request.content_length and request.content_length > 128000:
        return jsonify(success=False, code="case_input_too_large"), 413
    body = request.args.to_dict() if request.method == "GET" else request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify(success=False, code="invalid_case_input"), 400
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        client = load_agent_client_by_key(cursor, request.headers.get("X-LocalOS-Agent-Key", ""))
        conn.commit()  # Release existing security bootstrap DDL locks.
        scope = "cases:" + operation
        access = evaluate_agent_access(client, required_scope=scope, action_type="inbound_case_" + operation)
        if not access["ok"]:
            raise CaseError(access["code"], access["http_status"])
        service = InboundCaseService(cursor, client, membership)
        result = service.prepare(body) if operation == "prepare" else getattr(service, operation)(run_id, body)
        log_agent_action(cursor, agent_client_id=client["id"], business_id=result["business_id"],
            action_type="inbound_case_" + operation, capability="inbound_case.review", required_scope=scope,
            risk_level="low", input_summary={"run_id": result["run_id"]},
            output_summary={"status": result["status"], "preparation_only": True}, status="completed", reason_code="OK")
        conn.commit()
        response = jsonify(success=True, case=result)
        response.headers["Cache-Control"] = "no-store"
        return response
    except CaseError as error:
        conn.rollback()
        return jsonify(success=False, code=error.code), error.status
    except PermissionError:
        conn.rollback()
        return jsonify(success=False, code="case_business_access_denied"), 403
    except Exception:
        conn.rollback()
        logger.error("Inbound case request failed", exc_info=False)  # Never log source text or keys.
        return jsonify(success=False, code="case_internal_error"), 500
    finally:
        conn.close()


@inbound_cases_bp.post("/api/agent-api/inbound-cases")
def prepare_case():
    return dispatch("prepare")


@inbound_cases_bp.get("/api/agent-api/inbound-cases/<run_id>")
def read_case(run_id):
    return dispatch("read", run_id)


@inbound_cases_bp.post("/api/agent-api/inbound-cases/<run_id>/review")
def review_case(run_id):
    return dispatch("review", run_id)
