from __future__ import annotations

import uuid
from typing import Any

from flask import jsonify, request
from psycopg2.extras import Json, RealDictCursor

from api.prospecting.access_schema import _require_auth, _require_superadmin, _resolve_business_for_user
from api.prospecting.shared import admin_prospecting_bp
from pg_db_utils import get_db_connection
from services.contact_intelligence_service import (
    enqueue_enrichment_job,
    serialize_contact_point,
)
from services.outreach_sender_profile_service import evaluate_sender_profile_completeness
from services.outreach_personalization_ai import generation_contract_current


def _serialize_job(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    return {
        "id": str(row.get("id")),
        "workstream_id": str(row.get("workstream_id")),
        "status": row.get("status"),
        "phase": row.get("current_phase"),
        "attempt_count": int(row.get("attempt_count") or 0),
        "message_brief": row.get("message_brief_json") or {},
        "message_readiness": row.get("readiness_json") or {},
        "result": row.get("result_json") or {},
        "error": row.get("error_message"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "completed_at": row.get("completed_at"),
    }


def _load_workstream(cursor, *, lead_id: str, workstream_id: str, client_business_id: str | None = None) -> dict[str, Any] | None:
    params: list[Any] = [lead_id, workstream_id]
    client_filter = ""
    if client_business_id:
        client_filter = "AND ws.workstream_type = 'client_partnership' AND ws.client_business_id = %s"
        params.append(client_business_id)
    cursor.execute(
        f"""
        SELECT ws.*, lead.name AS lead_name, lead.business_id AS lead_business_id,
               client.name AS client_business_name
        FROM lead_workstreams ws
        JOIN prospectingleads lead ON lead.id = ws.lead_id
        LEFT JOIN businesses client ON client.id = ws.client_business_id
        WHERE ws.lead_id = %s AND ws.id = %s {client_filter}
        LIMIT 1
        """,
        tuple(params),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def _load_intelligence(cursor, workstream: dict[str, Any]) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT * FROM lead_contact_points
        WHERE lead_id = %s
        ORDER BY
          CASE verification_status WHEN 'verified' THEN 0 WHEN 'confirmed_source' THEN 1 ELSE 2 END,
          confidence DESC, updated_at DESC
        """,
        (workstream.get("lead_id"),),
    )
    contacts = [serialize_contact_point(dict(row)) for row in cursor.fetchall() or []]
    cursor.execute(
        """
        SELECT * FROM lead_enrichment_jobs
        WHERE workstream_id = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (workstream.get("id"),),
    )
    job_row = cursor.fetchone()
    cursor.execute(
        """
        SELECT id, channel, status, generated_text, edited_text, approved_text,
               message_brief_json, quality_gate_json, include_room_link,
               contact_point_id, sender_profile_id, created_at, updated_at
        FROM outreachmessagedrafts
        WHERE workstream_id = %s
          AND enrichment_job_id IS NOT NULL
        ORDER BY updated_at DESC, created_at DESC
        LIMIT 1
        """,
        (workstream.get("id"),),
    )
    draft_row = cursor.fetchone()
    cursor.execute(
        """
        SELECT id, display_name, role_title, company_name, competence_story,
               proof_points_json, verified_cases_json, signature_text, confirmed_at,
               outreach_context_json, allowed_offers_json, forbidden_claims_json,
               voice_examples_json
        FROM outreach_sender_profiles
        WHERE workstream_type = %s
          AND COALESCE(client_business_id, '') = COALESCE(%s, '')
          AND is_active = TRUE
        LIMIT 1
        """,
        (workstream.get("workstream_type"), workstream.get("client_business_id")),
    )
    sender_row = cursor.fetchone()
    sender_profile = dict(sender_row) if sender_row else None
    business_service_count = None
    if workstream.get("workstream_type") == "client_partnership":
        cursor.execute(
            """
            SELECT COUNT(*) AS service_count
            FROM userservices
            WHERE business_id = %s AND COALESCE(is_active, TRUE) = TRUE
            """,
            (workstream.get("client_business_id"),),
        )
        service_row = cursor.fetchone()
        business_service_count = int(
            (service_row.get("service_count") if service_row else 0) or 0
        )
    profile_completeness = evaluate_sender_profile_completeness(
        sender_profile,
        workstream_type=str(workstream.get("workstream_type") or ""),
        business_service_count=business_service_count,
    )
    draft_payload = dict(draft_row) if draft_row else None
    if draft_payload is not None:
        draft_payload["generation_current"] = generation_contract_current(
            draft_payload.get("message_brief_json"),
            draft_payload.get("quality_gate_json"),
        )
        draft_payload["requires_regeneration"] = not draft_payload["generation_current"]
    first_message = (
        draft_payload
        if draft_row
        and profile_completeness["ready"]
        and sender_profile
        and sender_profile.get("confirmed_at")
        else None
    )
    selected = next(
        (item for item in contacts if item.get("id") == str(workstream.get("selected_contact_point_id"))),
        None,
    )
    return {
        "workstream_id": str(workstream.get("id")),
        "lead_id": str(workstream.get("lead_id")),
        "contacts": contacts,
        "contact_summary": {
            "found": sum(1 for item in contacts if item.get("type") != "website"),
            "verified": sum(
                1 for item in contacts
                if item.get("type") != "website"
                and item.get("verification_status") in {"verified", "confirmed_source"}
            ),
        },
        "selected_recipient": selected,
        "job": _serialize_job(dict(job_row) if job_row else None),
        "sender_profile": sender_profile,
        "sender_profile_completeness": profile_completeness,
        "first_message": first_message,
    }


def _save_sender_profile(
    cursor,
    *,
    workstream_type: str,
    client_business_id: str | None,
    user_id: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    display_name = str(data.get("display_name") or "").strip()
    role_title = str(data.get("role_title") or "").strip()
    company_name = str(data.get("company_name") or "").strip()
    if not display_name or not role_title or not company_name:
        raise ValueError("Укажите имя, роль и компанию отправителя")
    confirmation_requested = bool(data.get("confirmed"))

    def normalize_facts(value: Any) -> list[dict[str, Any]]:
        items = value if isinstance(value, list) else []
        normalized: list[dict[str, Any]] = []
        for item in items:
            if isinstance(item, dict):
                fact = str(
                    item.get("fact") or item.get("text") or item.get("result") or item.get("title") or ""
                ).strip()
                status = str(item.get("status") or ("approved" if confirmation_requested else "missing")).strip().lower()
                source = str(item.get("source") or "sender_confirmation").strip()
            else:
                fact = str(item or "").strip()
                status = "approved" if confirmation_requested else "missing"
                source = "sender_confirmation"
            if fact and status in {"approved", "observed", "hypothesis", "missing"}:
                normalized.append({"fact": fact, "status": status, "source": source})
        return normalized

    competence_story = str(data.get("competence_story") or "").strip()
    competence_status = str(
        data.get("competence_story_status") or ("approved" if confirmation_requested and competence_story else "missing")
    ).strip().lower()
    if competence_status not in {"approved", "observed", "hypothesis", "missing"}:
        raise ValueError("Неверный статус founder story")
    outreach_context = data.get("outreach_context") if isinstance(data.get("outreach_context"), dict) else {}
    proof_points = normalize_facts(data.get("proof_points"))
    verified_cases = normalize_facts(data.get("verified_cases"))
    allowed_offers = normalize_facts(data.get("allowed_offers"))
    forbidden_claims = normalize_facts(data.get("forbidden_claims"))
    voice_examples = normalize_facts(data.get("voice_examples"))
    business_service_count = None
    if workstream_type == "client_partnership":
        cursor.execute(
            """
            SELECT COUNT(*) AS service_count
            FROM userservices
            WHERE business_id = %s AND COALESCE(is_active, TRUE) = TRUE
            """,
            (client_business_id,),
        )
        service_row = cursor.fetchone()
        business_service_count = int(
            (service_row.get("service_count") if service_row else 0) or 0
        )
    candidate_profile = {
        "display_name": display_name,
        "role_title": role_title,
        "company_name": company_name,
        "competence_story": competence_story,
        "proof_points_json": proof_points,
        "verified_cases_json": verified_cases,
        "allowed_offers_json": allowed_offers,
        "forbidden_claims_json": forbidden_claims,
        "voice_examples_json": voice_examples,
        "outreach_context_json": {
            **outreach_context,
            "competence_story_status": competence_status,
        },
    }
    completeness = evaluate_sender_profile_completeness(
        candidate_profile,
        workstream_type=workstream_type,
        business_service_count=business_service_count,
    )
    confirmed = confirmation_requested and bool(completeness["ready"])
    outreach_context = {
        **outreach_context,
        "competence_story_status": competence_status,
        "fact_status_contract": ["approved", "observed", "hypothesis", "missing"],
        "profile_completeness": completeness,
    }
    cursor.execute(
        "SELECT pg_advisory_xact_lock(hashtext(%s))",
        (f"sender-profile:{workstream_type}:{client_business_id or 'localos'}",),
    )
    cursor.execute(
        """
        UPDATE outreach_sender_profiles
        SET is_active = FALSE, updated_at = NOW()
        WHERE workstream_type = %s
          AND COALESCE(client_business_id, '') = COALESCE(%s, '')
          AND is_active = TRUE
        """,
        (workstream_type, client_business_id),
    )
    profile_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO outreach_sender_profiles (
            id, workstream_type, client_business_id, display_name, role_title,
            company_name, competence_story, proof_points_json, verified_cases_json,
            signature_text, outreach_context_json, allowed_offers_json,
            forbidden_claims_json, voice_examples_json,
            is_active, confirmed_at, created_by, created_at, updated_at
        ) VALUES (
            %s, %s, NULLIF(%s, ''), %s, %s, %s, NULLIF(%s, ''), %s, %s,
            NULLIF(%s, ''), %s, %s, %s, %s,
            TRUE, CASE WHEN %s THEN NOW() ELSE NULL END,
            NULLIF(%s, ''), NOW(), NOW()
        )
        RETURNING *
        """,
        (
            profile_id, workstream_type, client_business_id or "", display_name, role_title,
            company_name, competence_story,
            Json(proof_points),
            Json(verified_cases),
            str(data.get("signature_text") or ""),
            Json(outreach_context),
            Json(allowed_offers),
            Json(forbidden_claims),
            Json(voice_examples),
            confirmed, user_id,
        ),
    )
    profile = dict(cursor.fetchone())
    profile["profile_completeness"] = completeness
    return profile


@admin_prospecting_bp.route("/api/admin/prospecting/leads/<string:lead_id>/contact-intelligence", methods=["POST"])
def admin_start_contact_intelligence(lead_id: str):
    _, error = _require_superadmin()
    if error:
        return error
    data = request.get_json(silent=True) or {}
    workstream_id = str(data.get("workstream_id") or "").strip()
    if not workstream_id:
        return jsonify({"error": "workstream_id is required"}), 400
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        workstream = _load_workstream(cursor, lead_id=lead_id, workstream_id=workstream_id)
        if not workstream:
            return jsonify({"error": "Lead workstream not found"}), 404
        job = enqueue_enrichment_job(
            cursor,
            workstream_id,
            force=bool(data.get("force")),
            allow_paid_enrichment=bool(data.get("allow_paid_enrichment")),
        )
        conn.commit()
        return jsonify({"success": True, "job": _serialize_job(job), "reused": bool(job.get("reused"))}), 202
    finally:
        conn.close()


@admin_prospecting_bp.route("/api/admin/prospecting/leads/<string:lead_id>/contact-intelligence", methods=["GET"])
def admin_get_contact_intelligence(lead_id: str):
    _, error = _require_superadmin()
    if error:
        return error
    workstream_id = str(request.args.get("workstream_id") or "").strip()
    if not workstream_id:
        return jsonify({"error": "workstream_id is required"}), 400
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        workstream = _load_workstream(cursor, lead_id=lead_id, workstream_id=workstream_id)
        if not workstream:
            return jsonify({"error": "Lead workstream not found"}), 404
        return jsonify({"success": True, **_load_intelligence(cursor, workstream)})
    finally:
        conn.close()


@admin_prospecting_bp.route("/api/admin/prospecting/leads/<string:lead_id>/recipient", methods=["POST"])
def admin_select_contact_recipient(lead_id: str):
    _, error = _require_superadmin()
    if error:
        return error
    data = request.get_json(silent=True) or {}
    workstream_id = str(data.get("workstream_id") or "").strip()
    contact_point_id = str(data.get("contact_point_id") or "").strip()
    if not workstream_id or not contact_point_id:
        return jsonify({"error": "workstream_id and contact_point_id are required"}), 400
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        workstream = _load_workstream(cursor, lead_id=lead_id, workstream_id=workstream_id)
        if not workstream:
            return jsonify({"error": "Lead workstream not found"}), 404
        cursor.execute(
            "SELECT id FROM lead_contact_points WHERE id = %s AND lead_id = %s AND verification_status <> 'invalid'",
            (contact_point_id, lead_id),
        )
        if not cursor.fetchone():
            return jsonify({"error": "Contact point not found"}), 404
        cursor.execute(
            "UPDATE lead_workstreams SET selected_contact_point_id = %s, updated_at = NOW() WHERE id = %s",
            (contact_point_id, workstream_id),
        )
        job = enqueue_enrichment_job(cursor, workstream_id, force=True)
        conn.commit()
        return jsonify({"success": True, "contact_point_id": contact_point_id, "job": _serialize_job(job)}), 202
    finally:
        conn.close()


@admin_prospecting_bp.route("/api/admin/prospecting/sender-profiles", methods=["GET", "POST"])
def admin_sender_profiles():
    user_data, error = _require_superadmin()
    if error:
        return error
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        if request.method == "GET":
            cursor.execute(
                """
                SELECT p.*, b.name AS client_business_name
                FROM outreach_sender_profiles p
                LEFT JOIN businesses b ON b.id = p.client_business_id
                WHERE p.is_active = TRUE
                ORDER BY p.workstream_type, b.name NULLS FIRST
                """
            )
            return jsonify({"success": True, "profiles": [dict(row) for row in cursor.fetchall() or []]})
        data = request.get_json(silent=True) or {}
        workstream_type = str(data.get("workstream_type") or "localos_sales").strip()
        client_business_id = str(data.get("client_business_id") or "").strip() or None
        if workstream_type not in {"localos_sales", "client_partnership"}:
            return jsonify({"error": "Unsupported workstream_type"}), 400
        if workstream_type == "client_partnership" and not client_business_id:
            return jsonify({"error": "client_business_id is required"}), 400
        profile = _save_sender_profile(
            cursor,
            workstream_type=workstream_type,
            client_business_id=client_business_id,
            user_id=str(user_data.get("user_id") or ""),
            data=data,
        )
        conn.commit()
        return jsonify({
            "success": True,
            "profile": profile,
            "profile_completeness": profile.get("profile_completeness") or {},
        }), 201
    except ValueError as validation_error:
        conn.rollback()
        return jsonify({"error": str(validation_error)}), 400
    finally:
        conn.close()


def _partnership_context(data: dict[str, Any] | None = None):
    user_data, error = _require_auth()
    if error:
        return None, None, error
    requested = str((data or {}).get("business_id") or request.args.get("business_id") or "").strip() or None
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    business_id = _resolve_business_for_user(cursor, user_data, requested)
    if not business_id:
        conn.close()
        return None, None, (jsonify({"error": "Business not found or access denied"}), 403)
    return conn, {"user": user_data, "business_id": business_id}, None


@admin_prospecting_bp.route("/api/partnership/leads/<string:lead_id>/contact-intelligence", methods=["GET", "POST"])
def partnership_contact_intelligence(lead_id: str):
    data = request.get_json(silent=True) or {} if request.method == "POST" else {}
    conn, context, error = _partnership_context(data)
    if error:
        return error
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        workstream_id = str(data.get("workstream_id") or request.args.get("workstream_id") or "").strip()
        if not workstream_id:
            return jsonify({"error": "workstream_id is required"}), 400
        workstream = _load_workstream(
            cursor,
            lead_id=lead_id,
            workstream_id=workstream_id,
            client_business_id=str(context.get("business_id")),
        )
        if not workstream:
            return jsonify({"error": "Lead workstream not found"}), 404
        if request.method == "POST":
            job = enqueue_enrichment_job(
                cursor,
                workstream_id,
                force=bool(data.get("force")),
                allow_paid_enrichment=bool(data.get("allow_paid_enrichment")),
            )
            conn.commit()
            return jsonify({"success": True, "job": _serialize_job(job), "reused": bool(job.get("reused"))}), 202
        return jsonify({"success": True, **_load_intelligence(cursor, workstream)})
    finally:
        conn.close()


@admin_prospecting_bp.route("/api/partnership/leads/<string:lead_id>/recipient", methods=["POST"])
def partnership_select_contact_recipient(lead_id: str):
    data = request.get_json(silent=True) or {}
    conn, context, error = _partnership_context(data)
    if error:
        return error
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        workstream_id = str(data.get("workstream_id") or "").strip()
        contact_point_id = str(data.get("contact_point_id") or "").strip()
        workstream = _load_workstream(
            cursor,
            lead_id=lead_id,
            workstream_id=workstream_id,
            client_business_id=str(context.get("business_id")),
        )
        if not workstream:
            return jsonify({"error": "Lead workstream not found"}), 404
        cursor.execute(
            "SELECT id FROM lead_contact_points WHERE id = %s AND lead_id = %s AND verification_status <> 'invalid'",
            (contact_point_id, lead_id),
        )
        if not cursor.fetchone():
            return jsonify({"error": "Contact point not found"}), 404
        cursor.execute(
            "UPDATE lead_workstreams SET selected_contact_point_id = %s, updated_at = NOW() WHERE id = %s",
            (contact_point_id, workstream_id),
        )
        job = enqueue_enrichment_job(cursor, workstream_id, force=True)
        conn.commit()
        return jsonify({"success": True, "job": _serialize_job(job)}), 202
    finally:
        conn.close()


@admin_prospecting_bp.route("/api/partnership/sender-profile", methods=["GET", "POST"])
def partnership_sender_profile():
    data = request.get_json(silent=True) or {} if request.method == "POST" else {}
    conn, context, error = _partnership_context(data)
    if error:
        return error
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        business_id = str(context.get("business_id"))
        if request.method == "GET":
            cursor.execute(
                """
                SELECT business.name AS company_name,
                       business.city AS geography,
                       owner.name AS sender_name
                FROM businesses business
                LEFT JOIN users owner ON owner.id = business.owner_id
                WHERE business.id::text = %s
                LIMIT 1
                """,
                (business_id,),
            )
            business_row = cursor.fetchone() or {}
            suggested_sender_name = str(business_row.get("sender_name") or "").strip()
            if suggested_sender_name.lower() in {"superadmin", "admin", "administrator"}:
                suggested_sender_name = ""
            cursor.execute(
                """
                SELECT name
                FROM userservices
                WHERE business_id = %s
                  AND COALESCE(is_active, TRUE) = TRUE
                  AND NULLIF(BTRIM(name), '') IS NOT NULL
                ORDER BY name
                LIMIT 100
                """,
                (business_id,),
            )
            business_services = [
                str(item.get("name") or "").strip()
                for item in cursor.fetchall() or []
                if str(item.get("name") or "").strip()
            ]
            cursor.execute(
                """
                SELECT * FROM outreach_sender_profiles
                WHERE workstream_type = 'client_partnership'
                  AND client_business_id = %s AND is_active = TRUE
                LIMIT 1
                """,
                (business_id,),
            )
            row = cursor.fetchone()
            profile = dict(row) if row else None
            completeness = evaluate_sender_profile_completeness(
                profile,
                workstream_type="client_partnership",
                business_service_count=len(business_services),
            )
            return jsonify({
                "success": True,
                "profile": profile,
                "profile_completeness": completeness,
                "suggested_context": {
                    "services": business_services,
                    "services_source": "business_services",
                    "company_name": str(business_row.get("company_name") or "").strip(),
                    "display_name": suggested_sender_name,
                    "geography": str(business_row.get("geography") or "").strip(),
                    "requires_confirmation": True,
                },
            })
        profile = _save_sender_profile(
            cursor,
            workstream_type="client_partnership",
            client_business_id=business_id,
            user_id=str(context.get("user", {}).get("user_id") or ""),
            data=data,
        )
        conn.commit()
        return jsonify({
            "success": True,
            "profile": profile,
            "profile_completeness": profile.get("profile_completeness") or {},
        }), 201
    except ValueError as validation_error:
        conn.rollback()
        return jsonify({"error": str(validation_error)}), 400
    finally:
        conn.close()
