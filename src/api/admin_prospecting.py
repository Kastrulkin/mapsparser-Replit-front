from __future__ import annotations

import json
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

SHORTLIST_APPROVED = "shortlist_approved"
SHORTLIST_REJECTED = "shortlist_rejected"
SELECTED_FOR_OUTREACH = "selected_for_outreach"
CHANNEL_SELECTED = "channel_selected"
ALLOWED_OUTREACH_CHANNELS = {"telegram", "whatsapp", "email", "manual"}
DRAFT_GENERATED = "generated"
DRAFT_APPROVED = "approved"
DRAFT_REJECTED = "rejected"


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


def _to_bool_filter(value: str | None):
    if value is None or value == "":
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes"}:
        return True
    if normalized in {"0", "false", "no"}:
        return False
    return None


def _lead_matches_filters(lead: dict[str, Any], filters: dict[str, Any]) -> bool:
    category = filters.get("category")
    if category and category.lower() not in (lead.get("category") or "").lower():
        return False

    city = filters.get("city")
    if city:
        haystack = " ".join(
            part for part in [lead.get("city"), lead.get("address"), lead.get("location")] if part
        ).lower()
        if city.lower() not in haystack:
            return False

    status = filters.get("status")
    if status and (lead.get("status") or "") != status:
        return False

    min_rating = filters.get("min_rating")
    if min_rating is not None and float(lead.get("rating") or 0) < min_rating:
        return False

    max_rating = filters.get("max_rating")
    if max_rating is not None and float(lead.get("rating") or 0) > max_rating:
        return False

    min_reviews = filters.get("min_reviews")
    if min_reviews is not None and int(lead.get("reviews_count") or 0) < min_reviews:
        return False

    max_reviews = filters.get("max_reviews")
    if max_reviews is not None and int(lead.get("reviews_count") or 0) > max_reviews:
        return False

    has_website = filters.get("has_website")
    if has_website is not None and bool(lead.get("website")) != has_website:
        return False

    has_phone = filters.get("has_phone")
    if has_phone is not None and bool(lead.get("phone")) != has_phone:
        return False

    has_email = filters.get("has_email")
    if has_email is not None and bool(lead.get("email")) != has_email:
        return False

    has_messengers = filters.get("has_messengers")
    if has_messengers is not None:
        messenger_links = lead.get("messenger_links_json") or []
        if isinstance(messenger_links, str):
            try:
                import json

                messenger_links = json.loads(messenger_links)
            except Exception:
                messenger_links = []
        has_any_messenger = bool(
            lead.get("telegram_url") or lead.get("whatsapp_url") or (messenger_links if isinstance(messenger_links, list) else [])
        )
        if has_any_messenger != has_messengers:
            return False

    return True


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


def _generate_first_message_draft(lead: dict[str, Any], channel: str) -> dict[str, str]:
    company_name = (lead.get("name") or "вашей компании").strip()
    category = (lead.get("category") or "локального бизнеса").strip()
    city = (lead.get("city") or "").strip()
    rating = lead.get("rating")
    reviews_count = lead.get("reviews_count") or 0

    weak_points = []
    if reviews_count < 20:
        weak_points.append("мало отзывов")
    if rating and float(rating) < 4.7:
        weak_points.append("есть запас роста по рейтингу")
    if not lead.get("website"):
        weak_points.append("не видно отдельного сайта")
    if not lead.get("phone"):
        weak_points.append("не указан удобный контакт")
    if not weak_points:
        weak_points.append("карточку можно усилить по конверсии")

    angle = f"обратили внимание, что у {company_name} в Яндекс.Картах {', '.join(weak_points[:2])}"
    money_hint = "По нашей модели это может стоить бизнесу части входящих обращений каждый месяц."

    if channel == "telegram":
        opening = f"Здравствуйте. Посмотрели карточку {company_name}"
        cta = "Если хотите, пришлю короткий разбор и покажу, что можно быстро улучшить."
    elif channel == "whatsapp":
        opening = f"Здравствуйте! Посмотрели карточку {company_name}"
        cta = "Могу отправить короткий разбор с конкретными точками роста, если это актуально."
    elif channel == "email":
        opening = f"Здравствуйте! Мы посмотрели карточку {company_name} в Яндекс.Картах."
        cta = "Если интересно, отправим короткий разбор с конкретными доработками и прогнозом эффекта."
    else:
        opening = f"Здравствуйте. Изучили карточку {company_name}."
        cta = "Если удобно, покажу короткий разбор и объясню, какие доработки дадут эффект."

    location_line = f" Видим вас по направлению «{category}»{f' в {city}' if city else ''}."
    draft_text = f"{opening}:{location_line} {angle}. {money_hint} {cta}".strip()

    return {
        "angle_type": "maps_growth",
        "tone": "professional",
        "generated_text": draft_text,
    }


def _serialize_draft(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    payload = dict(row)
    learning = payload.get("learning_note_json")
    if isinstance(learning, str) and learning:
        try:
            payload["learning_note_json"] = json.loads(learning)
        except Exception:
            payload["learning_note_json"] = None
    return payload


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
        filters = {
            "category": (request.args.get("category") or "").strip() or None,
            "city": (request.args.get("city") or "").strip() or None,
            "status": (request.args.get("status") or "").strip() or None,
            "min_rating": float(request.args.get("min_rating")) if request.args.get("min_rating") not in {None, ""} else None,
            "max_rating": float(request.args.get("max_rating")) if request.args.get("max_rating") not in {None, ""} else None,
            "min_reviews": int(request.args.get("min_reviews")) if request.args.get("min_reviews") not in {None, ""} else None,
            "max_reviews": int(request.args.get("max_reviews")) if request.args.get("max_reviews") not in {None, ""} else None,
            "has_website": _to_bool_filter(request.args.get("has_website")),
            "has_phone": _to_bool_filter(request.args.get("has_phone")),
            "has_email": _to_bool_filter(request.args.get("has_email")),
            "has_messengers": _to_bool_filter(request.args.get("has_messengers")),
        }
        with DatabaseManager() as db:
            leads = db.get_all_leads()
        filtered = [lead for lead in leads if _lead_matches_filters(lead, filters)]
        return jsonify({"leads": filtered, "count": len(filtered)})
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


@admin_prospecting_bp.route("/api/admin/prospecting/lead/<string:lead_id>/shortlist", methods=["POST"])
def review_lead_shortlist(lead_id):
    """Approve or reject lead for shortlist."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        decision = (data.get("decision") or "").strip().lower()
        if decision not in {"approved", "rejected"}:
            return jsonify({"error": "Decision must be approved or rejected"}), 400

        new_status = SHORTLIST_APPROVED if decision == "approved" else SHORTLIST_REJECTED
        with DatabaseManager() as db:
            success = db.update_lead_status(lead_id, new_status)
            if not success:
                return jsonify({"error": "Lead not found"}), 404
            lead = db.get_lead_by_id(lead_id)

        return jsonify({"success": True, "lead": lead, "status": new_status})
    except Exception as e:
        print(f"Error reviewing lead shortlist: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/lead/<string:lead_id>/select", methods=["POST"])
def select_lead_for_outreach(lead_id):
    """Move shortlisted lead into outreach selection stage."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        with DatabaseManager() as db:
            lead = db.get_lead_by_id(lead_id)
            if not lead:
                return jsonify({"error": "Lead not found"}), 404
            if lead.get("status") != SHORTLIST_APPROVED:
                return jsonify({"error": "Lead must be in shortlist before outreach selection"}), 400
            success = db.update_lead_outreach(lead_id, SELECTED_FOR_OUTREACH, lead.get("selected_channel"))
            if not success:
                return jsonify({"error": "Lead not found"}), 404
            lead = db.get_lead_by_id(lead_id)

        return jsonify({"success": True, "lead": lead, "status": SELECTED_FOR_OUTREACH})
    except Exception as e:
        print(f"Error selecting lead for outreach: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/lead/<string:lead_id>/channel", methods=["POST"])
def select_outreach_channel(lead_id):
    """Select outreach channel for lead and advance to channel_selected."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        channel = (data.get("channel") or "").strip().lower()
        if channel not in ALLOWED_OUTREACH_CHANNELS:
            return jsonify({"error": "Channel must be one of: telegram, whatsapp, email, manual"}), 400

        with DatabaseManager() as db:
            lead = db.get_lead_by_id(lead_id)
            if not lead:
                return jsonify({"error": "Lead not found"}), 404
            if lead.get("status") not in {SELECTED_FOR_OUTREACH, CHANNEL_SELECTED}:
                return jsonify({"error": "Lead must be selected for outreach before channel selection"}), 400
            success = db.update_lead_outreach(lead_id, CHANNEL_SELECTED, channel)
            if not success:
                return jsonify({"error": "Lead not found"}), 404
            lead = db.get_lead_by_id(lead_id)

        return jsonify({"success": True, "lead": lead, "status": CHANNEL_SELECTED, "selected_channel": channel})
    except Exception as e:
        print(f"Error selecting outreach channel: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/drafts", methods=["GET"])
def get_outreach_drafts():
    """List outreach message drafts."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        status_filter = (request.args.get("status") or "").strip().lower() or None
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            query = """
                SELECT
                    d.id, d.lead_id, d.channel, d.angle_type, d.tone, d.status,
                    d.generated_text, d.edited_text, d.approved_text,
                    d.learning_note_json, d.created_at, d.updated_at,
                    l.name AS lead_name, l.category, l.city, l.selected_channel, l.status AS lead_status
                FROM outreachmessagedrafts d
                JOIN prospectingleads l ON l.id = d.lead_id
            """
            params: list[Any] = []
            if status_filter:
                query += " WHERE d.status = %s"
                params.append(status_filter)
            query += " ORDER BY d.created_at DESC"
            cur.execute(query, params)
            rows = [_serialize_draft(dict(row)) for row in cur.fetchall()]
        finally:
            conn.close()

        return jsonify({"success": True, "drafts": rows, "count": len(rows)})
    except Exception as e:
        print(f"Error loading outreach drafts: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/lead/<string:lead_id>/draft-generate", methods=["POST"])
def generate_outreach_draft(lead_id):
    """Generate initial first-contact draft for lead in channel_selected."""
    user_data, error = _require_superadmin()
    if error:
        return error

    try:
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM prospectingleads WHERE id = %s", (lead_id,))
            lead = cur.fetchone()
            if not lead:
                return jsonify({"error": "Lead not found"}), 404
            lead_dict = dict(lead)
            if lead_dict.get("status") != CHANNEL_SELECTED:
                return jsonify({"error": "Lead must be channel_selected before draft generation"}), 400

            channel = (lead_dict.get("selected_channel") or "").strip().lower()
            if channel not in ALLOWED_OUTREACH_CHANNELS:
                return jsonify({"error": "Lead has no approved outreach channel"}), 400

            draft_payload = _generate_first_message_draft(lead_dict, channel)
            draft_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO outreachmessagedrafts (
                    id, lead_id, channel, angle_type, tone, status,
                    generated_text, created_by
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING id, lead_id, channel, angle_type, tone, status,
                          generated_text, edited_text, approved_text,
                          learning_note_json, created_at, updated_at
                """,
                (
                    draft_id,
                    lead_id,
                    channel,
                    draft_payload["angle_type"],
                    draft_payload["tone"],
                    DRAFT_GENERATED,
                    draft_payload["generated_text"],
                    user_data["user_id"],
                ),
            )
            draft = dict(cur.fetchone())
            conn.commit()
        finally:
            conn.close()

        return jsonify({"success": True, "draft": _serialize_draft(draft)})
    except Exception as e:
        print(f"Error generating outreach draft: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/drafts/<string:draft_id>/approve", methods=["POST"])
def approve_outreach_draft(draft_id):
    """Approve outreach draft and persist learning example."""
    user_data, error = _require_superadmin()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        approved_text = (data.get("approved_text") or "").strip()
        note = (data.get("note") or "").strip() or None
        if not approved_text:
            return jsonify({"error": "approved_text is required"}), 400

        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM outreachmessagedrafts WHERE id = %s", (draft_id,))
            draft = cur.fetchone()
            if not draft:
                return jsonify({"error": "Draft not found"}), 404
            draft_dict = dict(draft)

            cur.execute(
                """
                UPDATE outreachmessagedrafts
                SET approved_text = %s,
                    edited_text = %s,
                    status = %s,
                    approved_by = %s,
                    learning_note_json = %s,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING id, lead_id, channel, angle_type, tone, status,
                          generated_text, edited_text, approved_text,
                          learning_note_json, created_at, updated_at
                """,
                (
                    approved_text,
                    approved_text,
                    DRAFT_APPROVED,
                    user_data["user_id"],
                    Json({"note": note} if note else {}),
                    draft_id,
                ),
            )
            updated = dict(cur.fetchone())

            learning_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO outreachlearningexamples (
                    id, example_type, lead_id, input_text, output_text, metadata_json, created_by
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    learning_id,
                    "approved_opening",
                    draft_dict["lead_id"],
                    draft_dict.get("generated_text"),
                    approved_text,
                    Json({"draft_id": draft_id, "note": note}),
                    user_data["user_id"],
                ),
            )
            conn.commit()
        finally:
            conn.close()

        return jsonify({"success": True, "draft": _serialize_draft(updated)})
    except Exception as e:
        print(f"Error approving outreach draft: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/drafts/<string:draft_id>/reject", methods=["POST"])
def reject_outreach_draft(draft_id):
    """Reject outreach draft."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE outreachmessagedrafts
                SET status = %s,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING id, lead_id, channel, angle_type, tone, status,
                          generated_text, edited_text, approved_text,
                          learning_note_json, created_at, updated_at
                """,
                (DRAFT_REJECTED, draft_id),
            )
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Draft not found"}), 404
            conn.commit()
            updated = dict(row)
        finally:
            conn.close()

        return jsonify({"success": True, "draft": _serialize_draft(updated)})
    except Exception as e:
        print(f"Error rejecting outreach draft: {e}")
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
