from __future__ import annotations

import os
import sys
from typing import Any, Dict

from flask import Blueprint, Response, jsonify, request

from core.action_orchestrator import ActionOrchestrator
from database_manager import DatabaseManager
from services.agent_capability_handlers import build_capability_catalog, build_capability_handlers


capabilities_bp = Blueprint("capabilities_api", __name__)
PHASE1_ACTION_ORCHESTRATOR = ActionOrchestrator(build_capability_handlers())


def _json_error(message: str, status: int, code: str):
    return jsonify({"success": False, "error": message, "code": code}), status


def _verify_session_token(token: str) -> Dict[str, Any] | None:
    main_module = sys.modules.get("main")
    verifier = getattr(main_module, "verify_session", None)
    if callable(verifier):
        return verifier(token)
    from auth_system import verify_session

    return verify_session(token)


def _require_user():
    auth_header = str(request.headers.get("Authorization") or "")
    if not auth_header.startswith("Bearer "):
        return None, _json_error("Authorization required", 401, "AUTH_REQUIRED")
    user_data = _verify_session_token(auth_header.split(" ", 1)[1])
    if not user_data:
        return None, _json_error("Authorization required", 401, "AUTH_REQUIRED")
    return user_data, None


def _openclaw_token_from_request() -> str:
    token = str(request.headers.get("X-OpenClaw-Token") or "").strip()
    if token:
        return token
    auth_header = str(request.headers.get("Authorization") or "")
    if auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1].strip()
    return ""


def _require_openclaw():
    configured = str(os.getenv("OPENCLAW_LOCALOS_TOKEN") or os.getenv("OPENCLAW_TOKEN") or "").strip()
    provided = _openclaw_token_from_request()
    if not configured or not provided or provided != configured:
        return None, _json_error("OpenClaw token required", 401, "OPENCLAW_TOKEN_REQUIRED")
    tenant_id = str((request.get_json(silent=True) or {}).get("tenant_id") or request.args.get("tenant_id") or "").strip()
    user_data = _m2m_user_for_tenant(tenant_id)
    return user_data, None


def _m2m_user_for_tenant(tenant_id: str) -> Dict[str, Any]:
    if not tenant_id:
        return {"user_id": "", "id": "", "is_superadmin": True, "source": "openclaw"}
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        cursor.execute("SELECT owner_id FROM businesses WHERE id = %s LIMIT 1", (tenant_id,))
        row = cursor.fetchone()
        owner_id = ""
        if row:
            owner_id = str(row.get("owner_id") if hasattr(row, "get") else row[0])
        return {"user_id": owner_id, "id": owner_id, "is_superadmin": False, "source": "openclaw"}
    finally:
        db.close()


def _response(result: Dict[str, Any]):
    status = int(result.get("http_code") or (200 if result.get("success", True) else 400))
    body = dict(result)
    body.pop("http_code", None)
    return jsonify(body), status


def _int_arg(name: str, default: int) -> int:
    try:
        return int(request.args.get(name) or default)
    except Exception:
        return default


def _bool_arg(name: str) -> bool:
    return str(request.args.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def _optional_bool_arg(name: str):
    raw = str(request.args.get(name) or "").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return None


def _execute_with_user(user_data: Dict[str, Any]):
    payload = request.get_json(silent=True) or {}
    return _response(PHASE1_ACTION_ORCHESTRATOR.execute(payload, user_data))


def _decision_with_user(action_id: str, user_data: Dict[str, Any]):
    payload = request.get_json(silent=True) or {}
    decision = str(payload.get("decision") or "").strip().lower()
    reason = str(payload.get("reason") or payload.get("decision_reason") or "").strip()
    return _response(PHASE1_ACTION_ORCHESTRATOR.resolve_human_decision(action_id, decision, user_data, reason))


@capabilities_bp.route("/api/capabilities/catalog", methods=["GET"])
def user_capabilities_catalog():
    user_data, error_response = _require_user()
    if error_response:
        return error_response
    return jsonify({"success": True, **build_capability_catalog()})


@capabilities_bp.route("/api/capabilities/execute", methods=["POST"])
def user_capabilities_execute():
    user_data, error_response = _require_user()
    if error_response:
        return error_response
    return _execute_with_user(user_data)


@capabilities_bp.route("/api/capabilities/actions", methods=["GET"])
def user_capabilities_actions():
    user_data, error_response = _require_user()
    if error_response:
        return error_response
    return _response(
        PHASE1_ACTION_ORCHESTRATOR.list_actions(
            user_data,
            tenant_id=request.args.get("tenant_id"),
            status=request.args.get("status"),
            limit=_int_arg("limit", 50),
            offset=_int_arg("offset", 0),
        )
    )


@capabilities_bp.route("/api/capabilities/actions/<action_id>", methods=["GET"])
def user_capabilities_action(action_id: str):
    user_data, error_response = _require_user()
    if error_response:
        return error_response
    return _response(PHASE1_ACTION_ORCHESTRATOR.get_action(action_id, user_data))


@capabilities_bp.route("/api/capabilities/actions/<action_id>/decision", methods=["POST"])
def user_capabilities_action_decision(action_id: str):
    user_data, error_response = _require_user()
    if error_response:
        return error_response
    return _decision_with_user(action_id, user_data)


@capabilities_bp.route("/api/capabilities/actions/<action_id>/billing", methods=["GET"])
def user_capabilities_action_billing(action_id: str):
    user_data, error_response = _require_user()
    if error_response:
        return error_response
    return _response(PHASE1_ACTION_ORCHESTRATOR.get_action_billing(action_id, user_data))


@capabilities_bp.route("/api/capabilities/actions/<action_id>/timeline", methods=["GET"])
def user_capabilities_action_timeline(action_id: str):
    user_data, error_response = _require_user()
    if error_response:
        return error_response
    return _response(_timeline(action_id, user_data))


@capabilities_bp.route("/api/capabilities/actions/<action_id>/callback-attempts", methods=["GET"])
def user_capabilities_action_callback_attempts(action_id: str):
    user_data, error_response = _require_user()
    if error_response:
        return error_response
    return _response(_callback_attempts(action_id, user_data))


@capabilities_bp.route("/api/capabilities/actions/<action_id>/support-package", methods=["GET"])
def user_capabilities_action_support_package(action_id: str):
    user_data, error_response = _require_user()
    if error_response:
        return error_response
    return _response(_support_package(action_id, user_data))


@capabilities_bp.route("/api/capabilities/actions/<action_id>/diagnostics-bundle", methods=["GET"])
def user_capabilities_action_diagnostics_bundle(action_id: str):
    user_data, error_response = _require_user()
    if error_response:
        return error_response
    bundle = _diagnostics_bundle(action_id, user_data)
    if str(request.args.get("format") or "").lower() == "markdown" and bundle.get("success"):
        markdown = PHASE1_ACTION_ORCHESTRATOR.render_action_diagnostics_markdown(bundle)
        return Response(markdown, mimetype="text/markdown")
    return _response(bundle)


@capabilities_bp.route("/api/capabilities/actions/<action_id>/lifecycle-summary", methods=["GET"])
def user_capabilities_action_lifecycle(action_id: str):
    user_data, error_response = _require_user()
    if error_response:
        return error_response
    return _response(_lifecycle(action_id, user_data))


@capabilities_bp.route("/api/capabilities/actions/<action_id>/incident-report", methods=["GET"])
def user_capabilities_action_incident_report(action_id: str):
    user_data, error_response = _require_user()
    if error_response:
        return error_response
    result = PHASE1_ACTION_ORCHESTRATOR.render_action_incident_report_markdown(action_id, user_data)
    if not result.get("success"):
        return _response(result)
    return Response(str(result.get("markdown_report") or ""), mimetype="text/markdown")


@capabilities_bp.route("/api/capabilities/actions/<action_id>/incident-snapshot", methods=["GET"])
def user_capabilities_action_incident_snapshot(action_id: str):
    user_data, error_response = _require_user()
    if error_response:
        return error_response
    return _response(PHASE1_ACTION_ORCHESTRATOR.get_action_incident_snapshot(action_id, user_data))


@capabilities_bp.route("/api/capabilities/callbacks/dispatch", methods=["POST"])
def user_capabilities_callbacks_dispatch():
    user_data, error_response = _require_user()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    return _response(
        PHASE1_ACTION_ORCHESTRATOR.dispatch_callback_outbox_for_tenant(
            user_data,
            tenant_id=str(payload.get("tenant_id") or ""),
            batch_size=int(payload.get("batch_size") or 50),
        )
    )


@capabilities_bp.route("/api/capabilities/callbacks/metrics", methods=["GET"])
def user_capabilities_callbacks_metrics():
    user_data, error_response = _require_user()
    if error_response:
        return error_response
    return _response(
        PHASE1_ACTION_ORCHESTRATOR.get_callback_metrics(
            user_data,
            tenant_id=str(request.args.get("tenant_id") or ""),
            window_minutes=_int_arg("window_minutes", 60),
        )
    )


@capabilities_bp.route("/api/capabilities/health", methods=["GET"])
def user_capabilities_health():
    user_data, error_response = _require_user()
    if error_response:
        return error_response
    return _response(_health(user_data))


@capabilities_bp.route("/api/capabilities/health/trend", methods=["GET"])
def user_capabilities_health_trend():
    user_data, error_response = _require_user()
    if error_response:
        return error_response
    return _response(
        PHASE1_ACTION_ORCHESTRATOR.get_capability_health_trend(
            user_data,
            tenant_id=str(request.args.get("tenant_id") or ""),
            window_minutes=_int_arg("window_minutes", 60),
            limit=_int_arg("limit", 50),
        )
    )


@capabilities_bp.route("/api/capabilities/billing/reconcile", methods=["GET"])
def user_capabilities_billing_reconcile():
    user_data, error_response = _require_user()
    if error_response:
        return error_response
    return _response(
        PHASE1_ACTION_ORCHESTRATOR.reconcile_billing(
            user_data,
            tenant_id=str(request.args.get("tenant_id") or ""),
            window_minutes=_int_arg("window_minutes", 60),
            limit=_int_arg("limit", 50),
        )
    )


@capabilities_bp.route("/api/capabilities/support-export", methods=["GET"])
def user_capabilities_support_export():
    user_data, error_response = _require_user()
    if error_response:
        return error_response
    return _support_export_response(user_data)


@capabilities_bp.route("/api/capabilities/support-export/send", methods=["POST"])
def user_capabilities_support_export_send():
    user_data, error_response = _require_user()
    if error_response:
        return error_response
    return _response(_support_send_result(user_data))


@capabilities_bp.route("/api/capabilities/support-export/send-history", methods=["GET"])
def user_capabilities_support_export_send_history():
    user_data, error_response = _require_user()
    if error_response:
        return error_response
    return _response(_support_send_history(user_data))


@capabilities_bp.route("/api/capabilities/support-export/send-history/export", methods=["GET"])
def user_capabilities_support_export_send_history_export():
    user_data, error_response = _require_user()
    if error_response:
        return error_response
    result = _support_send_history(user_data)
    if str(request.args.get("format") or "").lower() == "markdown":
        return Response(_support_send_history_markdown(result), mimetype="text/markdown")
    return _response(result)


@capabilities_bp.route("/api/capabilities/audit-timeline", methods=["GET"])
def user_capabilities_audit_timeline():
    user_data, error_response = _require_user()
    if error_response:
        return error_response
    return _response(_tenant_audit_timeline(user_data))


@capabilities_bp.route("/api/capabilities/audit-timeline/export", methods=["GET"])
def user_capabilities_audit_timeline_export():
    user_data, error_response = _require_user()
    if error_response:
        return error_response
    result = _tenant_audit_timeline(user_data)
    if str(request.args.get("format") or "").lower() == "markdown" and result.get("success"):
        return Response(_timeline_markdown(result), mimetype="text/markdown")
    return _response(result)


@capabilities_bp.route("/api/capabilities/audit-timeline/event-bundle", methods=["GET"])
def user_capabilities_audit_event_bundle():
    user_data, error_response = _require_user()
    if error_response:
        return error_response
    action_id = str(request.args.get("action_id") or request.args.get("event_id") or "").strip()
    if not action_id:
        return _json_error("action_id or event_id is required", 400, "VALIDATION_ERROR")
    return _response(PHASE1_ACTION_ORCHESTRATOR.get_action_incident_snapshot(action_id, user_data))


@capabilities_bp.route("/api/capabilities/callbacks/outbox/replay", methods=["POST"])
def user_capabilities_callbacks_replay():
    user_data, error_response = _require_user()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    return _response(
        PHASE1_ACTION_ORCHESTRATOR.replay_callback_outbox(
            user_data,
            tenant_id=str(payload.get("tenant_id") or ""),
            include_retry=bool(payload.get("include_retry")),
            limit=int(payload.get("limit") or 50),
        )
    )


@capabilities_bp.route("/api/capabilities/callbacks/outbox/cleanup", methods=["POST"])
def user_capabilities_callbacks_cleanup():
    user_data, error_response = _require_user()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    return _response(
        PHASE1_ACTION_ORCHESTRATOR.cleanup_callback_outbox(
            user_data,
            tenant_id=str(payload.get("tenant_id") or ""),
            older_than_minutes=int(payload.get("older_than_minutes") or int(payload.get("older_than_days") or 7) * 24 * 60),
            limit=int(payload.get("limit") or 100),
        )
    )


@capabilities_bp.route("/api/openclaw/capabilities/catalog", methods=["GET"])
def openclaw_capabilities_catalog():
    user_data, error_response = _require_openclaw()
    if error_response:
        return error_response
    return jsonify({"success": True, **build_capability_catalog()})


@capabilities_bp.route("/api/openclaw/capabilities/execute", methods=["POST"])
def openclaw_capabilities_execute():
    user_data, error_response = _require_openclaw()
    if error_response:
        return error_response
    return _execute_with_user(user_data)


@capabilities_bp.route("/api/openclaw/capabilities/actions", methods=["GET"])
def openclaw_capabilities_actions():
    user_data, error_response = _require_openclaw()
    if error_response:
        return error_response
    return _response(
        PHASE1_ACTION_ORCHESTRATOR.list_actions(
            user_data,
            tenant_id=request.args.get("tenant_id"),
            status=request.args.get("status"),
            limit=_int_arg("limit", 50),
            offset=_int_arg("offset", 0),
        )
    )


@capabilities_bp.route("/api/openclaw/capabilities/actions/<action_id>", methods=["GET"])
def openclaw_capabilities_action(action_id: str):
    user_data, error_response = _require_openclaw()
    if error_response:
        return error_response
    return _response(PHASE1_ACTION_ORCHESTRATOR.get_action(action_id, user_data))


@capabilities_bp.route("/api/openclaw/capabilities/actions/<action_id>/decision", methods=["POST"])
def openclaw_capabilities_action_decision(action_id: str):
    user_data, error_response = _require_openclaw()
    if error_response:
        return error_response
    return _decision_with_user(action_id, user_data)


@capabilities_bp.route("/api/openclaw/capabilities/actions/<action_id>/billing", methods=["GET"])
def openclaw_capabilities_action_billing(action_id: str):
    user_data, error_response = _require_openclaw()
    if error_response:
        return error_response
    return _response(PHASE1_ACTION_ORCHESTRATOR.get_action_billing(action_id, user_data))


@capabilities_bp.route("/api/openclaw/capabilities/actions/<action_id>/timeline", methods=["GET"])
def openclaw_capabilities_action_timeline(action_id: str):
    user_data, error_response = _require_openclaw()
    if error_response:
        return error_response
    return _response(_timeline(action_id, user_data))


@capabilities_bp.route("/api/openclaw/capabilities/actions/<action_id>/callback-attempts", methods=["GET"])
def openclaw_capabilities_action_callback_attempts(action_id: str):
    user_data, error_response = _require_openclaw()
    if error_response:
        return error_response
    return _response(_callback_attempts(action_id, user_data))


@capabilities_bp.route("/api/openclaw/capabilities/actions/<action_id>/support-package", methods=["GET"])
def openclaw_capabilities_action_support_package(action_id: str):
    user_data, error_response = _require_openclaw()
    if error_response:
        return error_response
    return _response(_support_package(action_id, user_data))


@capabilities_bp.route("/api/openclaw/capabilities/actions/<action_id>/diagnostics-bundle", methods=["GET"])
def openclaw_capabilities_action_diagnostics_bundle(action_id: str):
    user_data, error_response = _require_openclaw()
    if error_response:
        return error_response
    return _response(_diagnostics_bundle(action_id, user_data))


@capabilities_bp.route("/api/openclaw/capabilities/actions/<action_id>/lifecycle-summary", methods=["GET"])
def openclaw_capabilities_action_lifecycle(action_id: str):
    user_data, error_response = _require_openclaw()
    if error_response:
        return error_response
    return _response(_lifecycle(action_id, user_data))


@capabilities_bp.route("/api/openclaw/capabilities/actions/<action_id>/incident-snapshot", methods=["GET"])
def openclaw_capabilities_action_incident_snapshot(action_id: str):
    user_data, error_response = _require_openclaw()
    if error_response:
        return error_response
    return _response(PHASE1_ACTION_ORCHESTRATOR.get_action_incident_snapshot(action_id, user_data))


@capabilities_bp.route("/api/openclaw/capabilities/health", methods=["GET"])
def openclaw_capabilities_health():
    user_data, error_response = _require_openclaw()
    if error_response:
        return error_response
    return _response(_health(user_data))


@capabilities_bp.route("/api/openclaw/capabilities/health/trend", methods=["GET"])
def openclaw_capabilities_health_trend():
    user_data, error_response = _require_openclaw()
    if error_response:
        return error_response
    return _response(
        PHASE1_ACTION_ORCHESTRATOR.get_capability_health_trend(
            user_data,
            tenant_id=str(request.args.get("tenant_id") or ""),
            window_minutes=_int_arg("window_minutes", 60),
            limit=_int_arg("limit", 50),
        )
    )


@capabilities_bp.route("/api/openclaw/capabilities/billing/reconcile", methods=["GET"])
def openclaw_capabilities_billing_reconcile():
    user_data, error_response = _require_openclaw()
    if error_response:
        return error_response
    return _response(
        PHASE1_ACTION_ORCHESTRATOR.reconcile_billing(
            user_data,
            tenant_id=str(request.args.get("tenant_id") or ""),
            window_minutes=_int_arg("window_minutes", 60),
            limit=_int_arg("limit", 50),
        )
    )


@capabilities_bp.route("/api/openclaw/capabilities/support-export", methods=["GET"])
def openclaw_capabilities_support_export():
    user_data, error_response = _require_openclaw()
    if error_response:
        return error_response
    return _support_export_response(user_data)


@capabilities_bp.route("/api/openclaw/capabilities/support-export/send-history", methods=["GET"])
def openclaw_capabilities_support_export_send_history():
    user_data, error_response = _require_openclaw()
    if error_response:
        return error_response
    return _response(_support_send_history(user_data))


@capabilities_bp.route("/api/openclaw/capabilities/support-export/send-history/export", methods=["GET"])
def openclaw_capabilities_support_export_send_history_export():
    user_data, error_response = _require_openclaw()
    if error_response:
        return error_response
    result = _support_send_history(user_data)
    if str(request.args.get("format") or "").lower() == "markdown":
        return Response(_support_send_history_markdown(result), mimetype="text/markdown")
    return _response(result)


@capabilities_bp.route("/api/openclaw/audit-timeline", methods=["GET"])
def openclaw_audit_timeline():
    user_data, error_response = _require_openclaw()
    if error_response:
        return error_response
    return _response(_tenant_audit_timeline(user_data))


@capabilities_bp.route("/api/openclaw/audit-timeline/export", methods=["GET"])
def openclaw_audit_timeline_export():
    user_data, error_response = _require_openclaw()
    if error_response:
        return error_response
    result = _tenant_audit_timeline(user_data)
    if str(request.args.get("format") or "").lower() == "markdown" and result.get("success"):
        return Response(_timeline_markdown(result), mimetype="text/markdown")
    return _response(result)


@capabilities_bp.route("/api/openclaw/audit-timeline/event-bundle", methods=["GET"])
def openclaw_audit_event_bundle():
    user_data, error_response = _require_openclaw()
    if error_response:
        return error_response
    action_id = str(request.args.get("action_id") or request.args.get("event_id") or "").strip()
    if not action_id:
        return _json_error("action_id or event_id is required", 400, "VALIDATION_ERROR")
    return _response(PHASE1_ACTION_ORCHESTRATOR.get_action_incident_snapshot(action_id, user_data))


@capabilities_bp.route("/api/openclaw/callbacks/dispatch", methods=["POST"])
def openclaw_callbacks_dispatch():
    user_data, error_response = _require_openclaw()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    return _response(PHASE1_ACTION_ORCHESTRATOR.dispatch_callback_outbox(batch_size=int(payload.get("batch_size") or 50), tenant_id=payload.get("tenant_id")))


@capabilities_bp.route("/api/openclaw/callbacks/outbox", methods=["GET"])
def openclaw_callbacks_outbox():
    user_data, error_response = _require_openclaw()
    if error_response:
        return error_response
    return _response(
        PHASE1_ACTION_ORCHESTRATOR.list_callback_outbox(
            user_data,
            tenant_id=str(request.args.get("tenant_id") or ""),
            status=request.args.get("status"),
            limit=_int_arg("limit", 50),
            offset=_int_arg("offset", 0),
        )
    )


@capabilities_bp.route("/api/openclaw/callbacks/metrics", methods=["GET"])
def openclaw_callbacks_metrics():
    user_data, error_response = _require_openclaw()
    if error_response:
        return error_response
    return _response(
        PHASE1_ACTION_ORCHESTRATOR.get_callback_metrics(
            user_data,
            tenant_id=str(request.args.get("tenant_id") or ""),
            window_minutes=_int_arg("window_minutes", 60),
        )
    )


@capabilities_bp.route("/api/openclaw/callbacks/outbox/replay", methods=["POST"])
def openclaw_callbacks_replay():
    user_data, error_response = _require_openclaw()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    return _response(
        PHASE1_ACTION_ORCHESTRATOR.replay_callback_outbox(
            user_data,
            tenant_id=str(payload.get("tenant_id") or ""),
            include_retry=bool(payload.get("include_retry")),
            limit=int(payload.get("limit") or 50),
        )
    )


@capabilities_bp.route("/api/openclaw/callbacks/outbox/cleanup", methods=["POST"])
def openclaw_callbacks_cleanup():
    user_data, error_response = _require_openclaw()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    return _response(
        PHASE1_ACTION_ORCHESTRATOR.cleanup_callback_outbox(
            user_data,
            tenant_id=str(payload.get("tenant_id") or ""),
            older_than_minutes=int(payload.get("older_than_minutes") or int(payload.get("older_than_days") or 7) * 24 * 60),
            limit=int(payload.get("limit") or 100),
        )
    )


def _timeline(action_id: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
    return PHASE1_ACTION_ORCHESTRATOR.get_action_timeline(
        action_id,
        user_data,
        limit=_int_arg("limit", 200),
        offset=_int_arg("offset", 0),
        source=request.args.get("source"),
        event_type=request.args.get("event_type"),
        status=request.args.get("status"),
        search=request.args.get("search"),
        only_problematic=_bool_arg("only_problematic"),
    )


def _callback_attempts(action_id: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
    return PHASE1_ACTION_ORCHESTRATOR.list_action_callback_attempts(
        action_id,
        user_data,
        limit=_int_arg("limit", 100),
        offset=_int_arg("offset", 0),
        success=_optional_bool_arg("success"),
        event_type=request.args.get("event_type"),
    )


def _support_package(action_id: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
    return PHASE1_ACTION_ORCHESTRATOR.get_action_support_package(
        action_id,
        user_data,
        limit=_int_arg("limit", 200),
        offset=_int_arg("offset", 0),
        source=request.args.get("source"),
        event_type=request.args.get("event_type"),
        status=request.args.get("status"),
        search=request.args.get("search"),
        only_problematic=_bool_arg("only_problematic"),
        full=_bool_arg("full"),
    )


def _diagnostics_bundle(action_id: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
    return PHASE1_ACTION_ORCHESTRATOR.get_action_diagnostics_bundle(
        action_id,
        user_data,
        limit=_int_arg("limit", 200),
        offset=_int_arg("offset", 0),
        source=request.args.get("source"),
        event_type=request.args.get("event_type"),
        status=request.args.get("status"),
        search=request.args.get("search"),
        only_problematic=_bool_arg("only_problematic"),
        full=_bool_arg("full"),
        attempts_limit=_int_arg("attempts_limit", 200),
        attempts_offset=_int_arg("attempts_offset", 0),
        attempts_success=_optional_bool_arg("attempts_success"),
        attempts_event_type=request.args.get("attempts_event_type"),
        attempts_full=_bool_arg("attempts_full"),
    )


def _lifecycle(action_id: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
    return PHASE1_ACTION_ORCHESTRATOR.get_action_lifecycle_summary(
        action_id,
        user_data,
        limit=_int_arg("limit", 200),
        offset=_int_arg("offset", 0),
        source=request.args.get("source"),
        event_type=request.args.get("event_type"),
        status=request.args.get("status"),
        search=request.args.get("search"),
        only_problematic=_bool_arg("only_problematic"),
        full=True,
    )


def _health(user_data: Dict[str, Any]) -> Dict[str, Any]:
    tenant_id = str(request.args.get("tenant_id") or "").strip()
    metrics = PHASE1_ACTION_ORCHESTRATOR.get_callback_metrics(
        user_data,
        tenant_id=tenant_id,
        window_minutes=_int_arg("window_minutes", 60),
    )
    if not metrics.get("success"):
        return metrics
    metric_values = metrics.get("metrics") if isinstance(metrics.get("metrics"), dict) else {}
    checks = {
        "token_configured": bool(str(os.getenv("OPENCLAW_LOCALOS_TOKEN") or os.getenv("OPENCLAW_TOKEN") or "").strip()),
        "callbacks_enabled": True,
        "dlq_count": int(metric_values.get("dlq") or 0),
        "retry_backlog": int(metric_values.get("retry") or 0),
        "stuck_retry": int(metric_values.get("stuck_retry") or 0),
    }
    status = "ready"
    if checks["dlq_count"] > 0 or checks["stuck_retry"] > 0:
        status = "degraded"
    result = {
        "success": True,
        "tenant_id": tenant_id,
        "status": status,
        "ready": status == "ready",
        "checks": checks,
        "metrics": metrics,
        "alerts": metrics.get("alerts") or [],
        "window_minutes": _int_arg("window_minutes", 60),
    }
    PHASE1_ACTION_ORCHESTRATOR.record_capability_health_snapshot(
        user_data,
        tenant_id=tenant_id,
        status=status,
        ready=status == "ready",
        checks=checks,
        metrics=metric_values,
        alerts=metrics.get("alerts") or [],
        window_minutes=_int_arg("window_minutes", 60),
    )
    return result


def _support_export_response(user_data: Dict[str, Any]):
    action_id = str(request.args.get("action_id") or "").strip()
    if action_id:
        result = PHASE1_ACTION_ORCHESTRATOR.get_action_diagnostics_bundle(
            action_id,
            user_data,
            full=True,
            attempts_full=True,
        )
        if str(request.args.get("format") or "").lower() == "markdown" and result.get("success"):
            return Response(PHASE1_ACTION_ORCHESTRATOR.render_action_diagnostics_markdown(result), mimetype="text/markdown")
        return _response(result)
    tenant_id = str(request.args.get("tenant_id") or "").strip()
    return _response(_tenant_audit_timeline(user_data, tenant_id=tenant_id))


def _tenant_audit_timeline(user_data: Dict[str, Any], tenant_id: str | None = None) -> Dict[str, Any]:
    return PHASE1_ACTION_ORCHESTRATOR.list_actions(
        user_data,
        tenant_id=tenant_id or request.args.get("tenant_id"),
        status=request.args.get("status"),
        limit=_int_arg("limit", 50),
        offset=_int_arg("offset", 0),
    )


def _timeline_markdown(result: Dict[str, Any]) -> str:
    lines = ["# OpenClaw Audit Timeline", ""]
    for item in result.get("items") or []:
        lines.append(
            f"- `{item.get('created_at')}` `{item.get('action_id')}` `{item.get('capability')}` `{item.get('status')}`"
        )
    if not result.get("items"):
        lines.append("- no actions")
    lines.append("")
    return "\n".join(lines)


def _support_send_result(user_data: Dict[str, Any]) -> Dict[str, Any]:
    payload = request.get_json(silent=True) or {}
    action_id = str(payload.get("action_id") or "").strip()
    tenant_id = str(payload.get("tenant_id") or request.args.get("tenant_id") or "").strip()
    return {
        "success": True,
        "tenant_id": tenant_id,
        "action_id": action_id,
        "status": "recorded",
        "external_dispatch_performed": False,
        "operator_note": "Support bundle send is a registered API boundary; Telegram delivery is handled by the separate owner-bot/support surface.",
    }


def _support_send_history(user_data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "success": True,
        "tenant_id": str(request.args.get("tenant_id") or ""),
        "items": [],
        "count": 0,
        "limit": _int_arg("limit", 50),
    }


def _support_send_history_markdown(result: Dict[str, Any]) -> str:
    return "# Support Export Send History\n\n- no support-send events recorded by this API wrapper\n"
