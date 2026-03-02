from __future__ import annotations

import threading
import uuid
from typing import Any

from flask import Blueprint, jsonify, request
from psycopg2.extras import Json

from auth_system import verify_session
from database_manager import DatabaseManager
from pg_db_utils import get_db_connection
from services.prospecting_service import ProspectingService


admin_prospecting_bp = Blueprint("admin_prospecting", __name__)


def _auth_error(message: str, status_code: int):
    return jsonify({"error": message}), status_code


def _require_superadmin():
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None, _auth_error("Authorization required", 401)

    token = auth_header.split(" ", 1)[1]
    user_data = verify_session(token)
    if not user_data:
        return None, _auth_error("Invalid token", 401)
    if not user_data.get("is_superadmin"):
        return None, _auth_error("Superadmin access required", 403)
    return user_data, None


def _create_search_job(
    *,
    query: str,
    location: str,
    search_limit: int,
    actor_id: str,
    user_id: str,
) -> str:
    job_id = str(uuid.uuid4())
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO outreachsearchjobs (
                id, source, actor_id, query, location, search_limit, status, created_by
            ) VALUES (
                %s, %s, %s, %s, %s, %s, 'queued', %s
            )
            """,
            (job_id, "apify_yandex", actor_id, query, location, search_limit, user_id),
        )
        conn.commit()
        return job_id
    finally:
        conn.close()


def _update_search_job(job_id: str, **updates: Any) -> None:
    if not updates:
        return

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        assignments = []
        values = []
        for key, value in updates.items():
            assignments.append(f"{key} = %s")
            values.append(Json(value) if key == "results_json" else value)
        assignments.append("updated_at = NOW()")
        if "status" in updates and updates["status"] in {"completed", "failed"}:
            assignments.append("completed_at = NOW()")
        values.append(job_id)
        cur.execute(
            f"UPDATE outreachsearchjobs SET {', '.join(assignments)} WHERE id = %s",
            values,
        )
        conn.commit()
    finally:
        conn.close()


def _get_search_job(job_id: str):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                id, source, actor_id, query, location, search_limit, status,
                result_count, created_by, error_text, results_json,
                created_at, updated_at, completed_at
            FROM outreachsearchjobs
            WHERE id = %s
            """,
            (job_id,),
        )
        return cur.fetchone()
    finally:
        conn.close()


def _run_search_job(job_id: str, query: str, location: str, search_limit: int) -> None:
    _update_search_job(job_id, status="running", error_text=None)
    try:
        service = ProspectingService()
        results = service.search_businesses(query, location, search_limit)
        _update_search_job(
            job_id,
            status="completed",
            result_count=len(results),
            results_json=results,
            error_text=None,
        )
    except Exception as exc:
        print(f"Error in async prospecting search job {job_id}: {exc}")
        _update_search_job(job_id, status="failed", error_text=str(exc))


@admin_prospecting_bp.route("/api/admin/prospecting/search", methods=["POST"])
def search_businesses():
    """Queue Yandex prospecting search via Apify."""
    user_data, error = _require_superadmin()
    if error:
        return error

    data = request.get_json(silent=True) or {}
    query = (data.get("query") or "").strip()
    location = (data.get("location") or "").strip()
    search_limit = int(data.get("limit", 50) or 50)

    if not query or not location:
        return jsonify({"error": "Query and location are required"}), 400
    if search_limit < 1:
        return jsonify({"error": "Limit must be positive"}), 400
    search_limit = min(search_limit, 200)

    service = ProspectingService()
    if not service.client:
        return jsonify({"error": "APIFY_TOKEN is not configured"}), 500

    try:
        job_id = _create_search_job(
            query=query,
            location=location,
            search_limit=search_limit,
            actor_id=service.actor_id,
            user_id=user_data["user_id"],
        )
        worker = threading.Thread(
            target=_run_search_job,
            args=(job_id, query, location, search_limit),
            daemon=True,
            name=f"outreach-search-{job_id}",
        )
        worker.start()
        return (
            jsonify(
                {
                    "success": True,
                    "job_id": job_id,
                    "status": "queued",
                    "source": "apify_yandex",
                    "actor_id": service.actor_id,
                }
            ),
            202,
        )
    except Exception as e:
        print(f"Error queueing prospecting search: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/search-job/<string:job_id>", methods=["GET"])
def get_search_job_status(job_id):
    """Get async search job status and results."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        row = _get_search_job(job_id)
        if not row:
            return jsonify({"error": "Search job not found"}), 404
        return jsonify(
            {
                "success": True,
                "job": {
                    "id": row.get("id"),
                    "source": row.get("source"),
                    "actor_id": row.get("actor_id"),
                    "query": row.get("query"),
                    "location": row.get("location"),
                    "limit": row.get("search_limit"),
                    "status": row.get("status"),
                    "result_count": row.get("result_count") or 0,
                    "error_text": row.get("error_text"),
                    "results": row.get("results_json") or [],
                    "created_at": row.get("created_at"),
                    "updated_at": row.get("updated_at"),
                    "completed_at": row.get("completed_at"),
                },
            }
        )
    except Exception as e:
        print(f"Error getting prospecting search job: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/leads", methods=["GET"])
def get_leads():
    """Get all saved leads."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        with DatabaseManager() as db:
            leads = db.get_all_leads()
        return jsonify({"leads": leads})
    except Exception as e:
        print(f"Error getting leads: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/save", methods=["POST"])
def save_lead():
    """Save a lead to database."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        lead_data = data.get("lead")

        if not lead_data:
            return jsonify({"error": "Lead data is required"}), 400

        lead_data.setdefault("source", "apify_yandex")
        lead_data.setdefault("source_external_id", lead_data.get("google_id"))
        lead_data.setdefault("status", "new")

        with DatabaseManager() as db:
            lead_id = db.save_lead(lead_data)

        return jsonify({"success": True, "lead_id": lead_id})
    except Exception as e:
        print(f"Error saving lead: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/lead/<string:lead_id>/status", methods=["POST"])
def update_lead_status(lead_id):
    """Update lead status."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        status = data.get("status")

        if not status:
            return jsonify({"error": "Status is required"}), 400

        with DatabaseManager() as db:
            success = db.update_lead_status(lead_id, status)

        if success:
            return jsonify({"success": True})
        return jsonify({"error": "Lead not found"}), 404
    except Exception as e:
        print(f"Error updating lead status: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/lead/<string:lead_id>", methods=["DELETE"])
def delete_lead(lead_id):
    """Delete a lead."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        with DatabaseManager() as db:
            success = db.delete_lead(lead_id)

        if success:
            return jsonify({"success": True})
        return jsonify({"error": "Lead not found"}), 404
    except Exception as e:
        print(f"Error deleting lead: {e}")
        return jsonify({"error": str(e)}), 500
