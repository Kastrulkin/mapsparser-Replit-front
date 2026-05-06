from flask import Blueprint, jsonify, request

from auth_system import verify_session
from database_manager import get_db_connection
from core.industry_pattern_recalibration import (
    build_monthly_industry_pattern_impact_report,
    create_industry_pattern_version_proposal,
    decide_industry_pattern_proposal,
    disable_industry_pattern_version,
    ensure_industry_pattern_tables,
    get_industry_pattern_detail_card,
    get_industry_pattern_rollback_preview,
    list_industry_pattern_admin_events,
    mark_industry_pattern_version_for_revision,
    record_industry_pattern_admin_event,
    regenerate_industry_pattern_revision,
    rollback_industry_pattern_version,
    run_monthly_industry_pattern_recalibration,
    summarize_industry_pattern_admin_safety,
    summarize_industry_pattern_health,
)


admin_industry_patterns_bp = Blueprint("admin_industry_patterns", __name__)


def _row_value(row, key, index, default=None):
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    if hasattr(row, "get"):
        try:
            return row.get(key, default)
        except Exception:
            pass
    try:
        return row[index]
    except Exception:
        return default


def _json_response(payload, status=200):
    return jsonify(payload), status


def _current_superadmin():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ", 1)[1].strip()
    user_data = verify_session(token)
    if not user_data or not user_data.get("is_superadmin"):
        return None
    return user_data


def _require_superadmin():
    user_data = _current_superadmin()
    if not user_data:
        return None, _json_response({"success": False, "error": "Forbidden"}, 403)
    return user_data, None


def _request_json():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _user_id(user_data):
    return str(user_data.get("user_id") or user_data.get("id") or "")


def _clean_filter(value, default="all"):
    clean = str(value or default).strip()
    return clean or default


def _proposal_from_row(row):
    return {
        "id": str(_row_value(row, "id", 0, "") or ""),
        "industry_key": str(_row_value(row, "industry_key", 1, "") or ""),
        "pattern_type": str(_row_value(row, "pattern_type", 2, "") or ""),
        "proposed_pattern": str(_row_value(row, "proposed_pattern", 3, "") or ""),
        "confidence": float(_row_value(row, "confidence", 4, 0) or 0),
        "risk_level": str(_row_value(row, "risk_level", 5, "") or ""),
        "status": str(_row_value(row, "status", 6, "") or ""),
        "decision_comment": str(_row_value(row, "decision_comment", 7, "") or ""),
        "activated_version_id": str(_row_value(row, "activated_version_id", 8, "") or ""),
        "created_at": str(_row_value(row, "created_at", 9, "") or ""),
        "updated_at": str(_row_value(row, "updated_at", 10, "") or ""),
        "examples": _row_value(row, "examples_json", 11, []) or [],
        "source_counts": _row_value(row, "source_counts_json", 12, {}) or {},
    }


def _version_from_row(row):
    return {
        "version_id": str(_row_value(row, "id", 0, "") or ""),
        "industry_key": str(_row_value(row, "industry_key", 1, "") or ""),
        "pattern_type": str(_row_value(row, "pattern_type", 2, "") or ""),
        "pattern_text": str(_row_value(row, "pattern_text", 3, "") or ""),
        "version": str(_row_value(row, "version", 4, "") or ""),
        "status": str(_row_value(row, "status", 5, "") or ""),
        "activated_by": str(_row_value(row, "activated_by", 6, "") or ""),
        "activated_at": str(_row_value(row, "activated_at", 7, "") or ""),
        "disabled_at": str(_row_value(row, "disabled_at", 8, "") or ""),
        "created_at": str(_row_value(row, "created_at", 9, "") or ""),
        "source_proposal_id": str(_row_value(row, "source_proposal_id", 10, "") or ""),
    }


@admin_industry_patterns_bp.route("/api/admin/industry-patterns/summary", methods=["GET"])
def industry_patterns_summary():
    _, error = _require_superadmin()
    if error:
        return error
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        ensure_industry_pattern_tables(conn)
        cursor.execute(
            """
            SELECT status, COUNT(*) AS count
            FROM industry_pattern_proposals
            GROUP BY status
            """
        )
        proposal_counts = {
            str(_row_value(row, "status", 0, "") or ""): int(_row_value(row, "count", 1, 0) or 0)
            for row in cursor.fetchall() or []
        }
        cursor.execute(
            """
            SELECT status, COUNT(*) AS count
            FROM industry_pattern_versions
            GROUP BY status
            """
        )
        version_counts = {
            str(_row_value(row, "status", 0, "") or ""): int(_row_value(row, "count", 1, 0) or 0)
            for row in cursor.fetchall() or []
        }
        impact = build_monthly_industry_pattern_impact_report(conn, days=30, limit=50)
        safety = summarize_industry_pattern_admin_safety(conn)
        return jsonify(
            {
                "success": True,
                "proposal_counts": proposal_counts,
                "version_counts": version_counts,
                "impact": impact,
                "safety": safety,
            }
        )
    finally:
        conn.close()


@admin_industry_patterns_bp.route("/api/admin/industry-patterns/admin-events", methods=["GET"])
def industry_patterns_admin_events():
    _, error = _require_superadmin()
    if error:
        return error
    limit = max(1, min(int(request.args.get("limit") or 20), 100))
    conn = get_db_connection()
    try:
        events = list_industry_pattern_admin_events(conn, limit=limit)
        return jsonify({"success": True, "events": events})
    finally:
        conn.close()


@admin_industry_patterns_bp.route("/api/admin/industry-patterns/proposals", methods=["GET"])
def industry_patterns_proposals():
    _, error = _require_superadmin()
    if error:
        return error
    status = _clean_filter(request.args.get("status"), "pending_review")
    industry_key = _clean_filter(request.args.get("industry_key"), "all")
    pattern_type = _clean_filter(request.args.get("pattern_type"), "all")
    limit = max(1, min(int(request.args.get("limit") or 50), 100))
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        ensure_industry_pattern_tables(conn)
        where_parts = []
        params = []
        if status != "all":
            where_parts.append("status = %s")
            params.append(status)
        if industry_key != "all":
            where_parts.append("industry_key = %s")
            params.append(industry_key)
        if pattern_type != "all":
            where_parts.append("pattern_type = %s")
            params.append(pattern_type)
        where_clause = "WHERE " + " AND ".join(where_parts) if where_parts else ""
        cursor.execute(
            f"""
            SELECT id, industry_key, pattern_type, proposed_pattern, confidence, risk_level,
                   status, decision_comment, activated_version_id, created_at, updated_at,
                   examples_json, source_counts_json
            FROM industry_pattern_proposals
            {where_clause}
            ORDER BY updated_at DESC, created_at DESC
            LIMIT %s
            """,
            params + [limit],
        )
        return jsonify({"success": True, "proposals": [_proposal_from_row(row) for row in cursor.fetchall() or []]})
    finally:
        conn.close()


@admin_industry_patterns_bp.route("/api/admin/industry-patterns/versions", methods=["GET"])
def industry_patterns_versions():
    _, error = _require_superadmin()
    if error:
        return error
    status = _clean_filter(request.args.get("status"), "active")
    industry_key = _clean_filter(request.args.get("industry_key"), "all")
    pattern_type = _clean_filter(request.args.get("pattern_type"), "all")
    limit = max(1, min(int(request.args.get("limit") or 50), 100))
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        ensure_industry_pattern_tables(conn)
        where_parts = []
        params = []
        if status != "all":
            where_parts.append("status = %s")
            params.append(status)
        if industry_key != "all":
            where_parts.append("industry_key = %s")
            params.append(industry_key)
        if pattern_type != "all":
            where_parts.append("pattern_type = %s")
            params.append(pattern_type)
        where_clause = "WHERE " + " AND ".join(where_parts) if where_parts else ""
        cursor.execute(
            f"""
            SELECT id, industry_key, pattern_type, pattern_text, version, status,
                   activated_by, activated_at, disabled_at, created_at, source_proposal_id
            FROM industry_pattern_versions
            {where_clause}
            ORDER BY COALESCE(activated_at, created_at) DESC, created_at DESC
            LIMIT %s
            """,
            params + [limit],
        )
        versions = [_version_from_row(row) for row in cursor.fetchall() or []]
        health = summarize_industry_pattern_health(conn, industry_key=industry_key, pattern_type=pattern_type, days=30, limit=20)
        return jsonify({"success": True, "versions": versions, "health": health})
    finally:
        conn.close()


@admin_industry_patterns_bp.route("/api/admin/industry-patterns/versions/<string:version_id>", methods=["GET"])
def industry_pattern_version_detail(version_id):
    user_data, error = _require_superadmin()
    if error:
        return error
    conn = get_db_connection()
    try:
        detail = get_industry_pattern_detail_card(conn, version_id=version_id, days=30, event_limit=30)
        record_industry_pattern_admin_event(
            conn,
            actor_id=_user_id(user_data),
            action="view_detail",
            target_type="version",
            target_id=version_id,
            metadata={"source": "web_admin"},
        )
        return jsonify({"success": True, "detail": detail})
    finally:
        conn.close()


@admin_industry_patterns_bp.route("/api/admin/industry-patterns/proposals/<string:proposal_id>/decision", methods=["POST"])
def industry_pattern_decide_proposal(proposal_id):
    user_data, error = _require_superadmin()
    if error:
        return error
    data = _request_json()
    conn = get_db_connection()
    try:
        result = decide_industry_pattern_proposal(
            conn,
            proposal_id=proposal_id,
            decision=str(data.get("decision") or ""),
            decided_by=_user_id(user_data),
            decision_comment=str(data.get("comment") or "web admin"),
        )
        record_industry_pattern_admin_event(
            conn,
            actor_id=_user_id(user_data),
            action=f"proposal_{result.get('decision') or 'decision'}",
            target_type="proposal",
            target_id=proposal_id,
            metadata={"status": result.get("status"), "activated_version_id": result.get("activated_version_id")},
        )
        return jsonify({"success": True, "result": result})
    except ValueError:
        return _json_response({"success": False, "error": "Invalid proposal decision"}, 400)
    finally:
        conn.close()


@admin_industry_patterns_bp.route("/api/admin/industry-patterns/proposals/<string:proposal_id>/regenerate", methods=["POST"])
def industry_pattern_regenerate_proposal(proposal_id):
    user_data, error = _require_superadmin()
    if error:
        return error
    conn = get_db_connection()
    try:
        result = regenerate_industry_pattern_revision(
            conn,
            proposal_id=proposal_id,
            decided_by=_user_id(user_data),
        )
        record_industry_pattern_admin_event(
            conn,
            actor_id=_user_id(user_data),
            action="proposal_regenerated",
            target_type="proposal",
            target_id=proposal_id,
            metadata={"created_proposal_id": result.get("created_proposal_id"), "status": result.get("status")},
        )
        return jsonify({"success": True, "result": result})
    except ValueError:
        return _json_response({"success": False, "error": "Invalid proposal regeneration"}, 400)
    finally:
        conn.close()


@admin_industry_patterns_bp.route("/api/admin/industry-patterns/versions/<string:version_id>/disable", methods=["POST"])
def industry_pattern_disable_version(version_id):
    user_data, error = _require_superadmin()
    if error:
        return error
    data = _request_json()
    if data.get("confirm") is not True:
        return _json_response({"success": False, "error": "Disable confirmation required"}, 400)
    conn = get_db_connection()
    try:
        result = disable_industry_pattern_version(
            conn,
            version_id=version_id,
            decided_by=_user_id(user_data),
            reason=str(data.get("reason") or "web admin disable"),
        )
        record_industry_pattern_admin_event(
            conn,
            actor_id=_user_id(user_data),
            action="disable_confirmed",
            target_type="version",
            target_id=version_id,
            metadata={"reason": result.get("reason"), "status": result.get("status")},
        )
        return jsonify({"success": True, "result": result})
    except ValueError:
        return _json_response({"success": False, "error": "Invalid active version"}, 400)
    finally:
        conn.close()


@admin_industry_patterns_bp.route("/api/admin/industry-patterns/versions/<string:version_id>/revision", methods=["POST"])
def industry_pattern_mark_version_revision(version_id):
    user_data, error = _require_superadmin()
    if error:
        return error
    data = _request_json()
    conn = get_db_connection()
    try:
        result = mark_industry_pattern_version_for_revision(
            conn,
            version_id=version_id,
            decided_by=_user_id(user_data),
            reason=str(data.get("reason") or "web admin revision"),
        )
        record_industry_pattern_admin_event(
            conn,
            actor_id=_user_id(user_data),
            action="version_marked_revision",
            target_type="version",
            target_id=version_id,
            metadata={"proposal_id": result.get("proposal_id"), "reason": result.get("reason")},
        )
        return jsonify({"success": True, "result": result})
    except ValueError:
        return _json_response({"success": False, "error": "Invalid active version"}, 400)
    finally:
        conn.close()


@admin_industry_patterns_bp.route("/api/admin/industry-patterns/versions/<string:version_id>/new-proposal", methods=["POST"])
def industry_pattern_create_version_proposal(version_id):
    user_data, error = _require_superadmin()
    if error:
        return error
    data = _request_json()
    conn = get_db_connection()
    try:
        result = create_industry_pattern_version_proposal(
            conn,
            version_id=version_id,
            decided_by=_user_id(user_data),
            reason=str(data.get("reason") or "web admin new version"),
        )
        record_industry_pattern_admin_event(
            conn,
            actor_id=_user_id(user_data),
            action="new_version_proposal",
            target_type="version",
            target_id=version_id,
            metadata={"proposal_id": result.get("proposal_id"), "reason": result.get("reason")},
        )
        return jsonify({"success": True, "result": result})
    except ValueError:
        return _json_response({"success": False, "error": "Invalid active version"}, 400)
    finally:
        conn.close()


@admin_industry_patterns_bp.route(
    "/api/admin/industry-patterns/versions/<string:current_version_id>/rollback-preview/<string:target_version_id>",
    methods=["GET"],
)
def industry_pattern_rollback_preview(current_version_id, target_version_id):
    user_data, error = _require_superadmin()
    if error:
        return error
    conn = get_db_connection()
    try:
        preview = get_industry_pattern_rollback_preview(
            conn,
            current_version_id=current_version_id,
            target_version_id=target_version_id,
            days=30,
        )
        record_industry_pattern_admin_event(
            conn,
            actor_id=_user_id(user_data),
            action="rollback_preview",
            target_type="version",
            target_id=current_version_id,
            metadata={
                "target_version_id": target_version_id,
                "can_confirm": preview.get("can_confirm"),
                "warnings": preview.get("warnings") or [],
            },
        )
        return jsonify({"success": True, "preview": preview})
    except ValueError:
        return _json_response({"success": False, "error": "Invalid rollback preview"}, 400)
    finally:
        conn.close()


@admin_industry_patterns_bp.route("/api/admin/industry-patterns/versions/<string:current_version_id>/rollback", methods=["POST"])
def industry_pattern_rollback(current_version_id):
    user_data, error = _require_superadmin()
    if error:
        return error
    data = _request_json()
    target_version_id = str(data.get("target_version_id") or "").strip()
    reason = str(data.get("reason") or "web admin rollback")
    confirmation_token = str(data.get("confirmation_token") or "").strip()
    conn = get_db_connection()
    try:
        preview = get_industry_pattern_rollback_preview(
            conn,
            current_version_id=current_version_id,
            target_version_id=target_version_id,
            days=30,
        )
        if not preview.get("can_confirm"):
            return _json_response({"success": False, "error": "Rollback confirmation blocked", "preview": preview}, 400)
        if confirmation_token != str(preview.get("confirmation_token") or ""):
            return _json_response({"success": False, "error": "Rollback preview confirmation required", "preview": preview}, 400)
        result = rollback_industry_pattern_version(
            conn,
            current_version_id=current_version_id,
            target_version_id=target_version_id,
            decided_by=_user_id(user_data),
            reason=reason,
        )
        record_industry_pattern_admin_event(
            conn,
            actor_id=_user_id(user_data),
            action="rollback_confirmed",
            target_type="version",
            target_id=current_version_id,
            metadata={
                "target_version_id": target_version_id,
                "reason": result.get("reason"),
                "disabled_versions": result.get("disabled_versions") or [],
            },
        )
        return jsonify({"success": True, "result": result})
    except ValueError:
        return _json_response({"success": False, "error": "Invalid rollback request"}, 400)
    finally:
        conn.close()


@admin_industry_patterns_bp.route("/api/admin/industry-patterns/recalibrate", methods=["POST"])
def industry_patterns_recalibrate():
    user_data, error = _require_superadmin()
    if error:
        return error
    data = _request_json()
    if data.get("confirm") is not True:
        return _json_response({"success": False, "error": "Recalibration confirmation required"}, 400)
    conn = get_db_connection()
    try:
        result = run_monthly_industry_pattern_recalibration(conn, create_proposals=True)
        record_industry_pattern_admin_event(
            conn,
            actor_id=_user_id(user_data),
            action="manual_recalibration",
            target_type="system",
            target_id="industry_patterns",
            metadata={
                "period_start": result.get("period_start"),
                "period_end": result.get("period_end"),
                "created_count": len(result.get("created_proposal_ids") or []),
            },
        )
        return jsonify({"success": True, "result": result})
    finally:
        conn.close()
