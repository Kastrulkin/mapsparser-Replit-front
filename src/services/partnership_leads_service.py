"""Partnership lead lifecycle handlers.

This module is the first scenario-level extraction from ``api.admin_prospecting``.
The public API module owns Flask routing; these handlers intentionally preserve
legacy response shapes while the shared helpers are moved out in later blocks.
"""
from __future__ import annotations

import json
from typing import Any

from flask import jsonify, request
from psycopg2.extras import RealDictCursor

from database_manager import DatabaseManager
from pg_db_utils import get_db_connection
from core.ai_learning import ensure_ai_learning_events_table, record_ai_learning_event
from services.lead_workstream_service import (
    CLIENT_PARTNERSHIP,
    LOCALOS_SALES,
    attach_workstreams,
    create_workstream,
    normalize_workstream_type,
    resolve_workstream,
    update_workstream,
)
from api import admin_prospecting as _legacy

ALLOWED_OUTREACH_CHANNELS = _legacy.ALLOWED_OUTREACH_CHANNELS
ALLOWED_PIPELINE_STATUSES = _legacy.ALLOWED_PIPELINE_STATUSES
CHANNEL_SELECTED = _legacy.CHANNEL_SELECTED
NOT_RELEVANT_REASONS = _legacy.NOT_RELEVANT_REASONS
PIPELINE_CLOSED_LOST = _legacy.PIPELINE_CLOSED_LOST
PIPELINE_CONTACTED = _legacy.PIPELINE_CONTACTED
PIPELINE_CONVERTED = _legacy.PIPELINE_CONVERTED
PIPELINE_IN_PROGRESS = _legacy.PIPELINE_IN_PROGRESS
PIPELINE_NOT_RELEVANT = _legacy.PIPELINE_NOT_RELEVANT
PIPELINE_POSTPONED = _legacy.PIPELINE_POSTPONED
PIPELINE_REPLIED = _legacy.PIPELINE_REPLIED
PIPELINE_SECOND_MESSAGE_SENT = _legacy.PIPELINE_SECOND_MESSAGE_SENT
PIPELINE_UNPROCESSED = _legacy.PIPELINE_UNPROCESSED
QUEUED_FOR_SEND = _legacy.QUEUED_FOR_SEND
SELECTED_FOR_OUTREACH = _legacy.SELECTED_FOR_OUTREACH
SHORTLIST_APPROVED = _legacy.SHORTLIST_APPROVED
SHORTLIST_REJECTED = _legacy.SHORTLIST_REJECTED
_apply_pipeline_transition = _legacy._apply_pipeline_transition
_ensure_manual_crm_tables = _legacy._ensure_manual_crm_tables
_ensure_partnership_artifacts_table = _legacy._ensure_partnership_artifacts_table
_ensure_partnership_columns = _legacy._ensure_partnership_columns
_ensure_sales_room_tables = _legacy._ensure_sales_room_tables
_lead_has_channel_contact = _legacy._lead_has_channel_contact
_make_sales_room_url = _legacy._make_sales_room_url
_normalize_lead_for_display = _legacy._normalize_lead_for_display
_normalize_prompt_meta = _legacy._normalize_prompt_meta
_normalize_public_audit_languages = _legacy._normalize_public_audit_languages
_normalize_sales_room_data_mode = _legacy._normalize_sales_room_data_mode
_outreach_channel_contact_error = _legacy._outreach_channel_contact_error
_partnership_next_best_action = _legacy._partnership_next_best_action
_prepare_partnership_sales_room = _legacy._prepare_partnership_sales_room
_record_lead_timeline_event = _legacy._record_lead_timeline_event
_require_auth = _legacy._require_auth
_require_superadmin = _legacy._require_superadmin
_resolve_business_for_user = _legacy._resolve_business_for_user
_sync_partnership_lead_from_parsed_data = _legacy._sync_partnership_lead_from_parsed_data
_to_json_compatible = _legacy._to_json_compatible

__all__ = [
    "partnership_list_leads",
    "partnership_update_lead",
    "partnership_mark_lead_manual_contact",
    "partnership_bulk_update_leads",
    "partnership_delete_lead",
    "partnership_bulk_delete_leads",
    "partnership_prepare_sales_room",
    "update_lead_status",
    "mark_lead_manual_contact",
    "add_lead_comment",
    "get_lead_timeline",
    "review_lead_shortlist",
    "select_lead_for_outreach",
    "select_outreach_channel",
    "update_lead_contacts",
    "update_lead_language",
    "delete_lead",
    "create_lead_workstream",
]

def partnership_list_leads():
    """User-level list of partnership leads for one business."""
    user_data, error = _require_auth()
    if error:
        return error

    try:
        requested_business_id = str(request.args.get("business_id") or "").strip() or None
        stage_filter = str(request.args.get("stage") or "").strip().lower() or None
        pipeline_status_filter = str(request.args.get("pipeline_status") or "").strip().lower() or None
        pilot_cohort = str(request.args.get("pilot_cohort") or "").strip().lower() or None
        q = str(request.args.get("q") or "").strip().lower()
        limit = max(1, min(int(request.args.get("limit") or 100), 500))
        offset = max(0, int(request.args.get("offset") or 0))

        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            _ensure_partnership_artifacts_table(conn)
            _ensure_sales_room_tables(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403

            where_sql = [
                "active_ws.client_business_id = %s",
                "active_ws.workstream_type = 'client_partnership'",
            ]
            params: list[Any] = [business_id]
            if stage_filter:
                where_sql.append("COALESCE(partnership_stage, 'imported') = %s")
                params.append(stage_filter)
            if pipeline_status_filter:
                if pipeline_status_filter == "in_progress":
                    where_sql.append(
                        """(
                            COALESCE(active_ws.status, 'unprocessed') IN ('in_progress', 'qualified')
                            OR (
                                COALESCE(active_ws.status, '') = ''
                                AND COALESCE(partnership_stage, 'imported') IN (
                                    'audited', 'matched', 'proposal_draft_ready', 'selected_for_outreach',
                                    'channel_selected', 'proposal_approved', 'queued_for_send'
                                )
                            )
                        )"""
                    )
                elif pipeline_status_filter == "postponed":
                    where_sql.append(
                        "(COALESCE(active_ws.status, 'unprocessed') IN ('postponed', 'deferred') OR COALESCE(partnership_stage, 'imported') = 'deferred')"
                    )
                elif pipeline_status_filter == "not_relevant":
                    where_sql.append(
                        "(COALESCE(active_ws.status, 'unprocessed') IN ('not_relevant', 'disqualified') OR COALESCE(partnership_stage, 'imported') IN ('rejected', 'shortlist_rejected'))"
                    )
                elif pipeline_status_filter == "contacted":
                    where_sql.append(
                        """(
                            COALESCE(active_ws.status, 'unprocessed') IN ('contacted', 'waiting_reply', 'sent', 'delivered')
                            OR COALESCE(partnership_stage, 'imported') IN ('approved_for_send', 'sent')
                        )"""
                    )
                elif pipeline_status_filter == "replied":
                    where_sql.append("COALESCE(active_ws.status, 'unprocessed') IN ('replied', 'responded')")
                else:
                    where_sql.append("COALESCE(active_ws.status, 'unprocessed') = %s")
                    params.append(pipeline_status_filter)
            if pilot_cohort:
                where_sql.append("COALESCE(pilot_cohort, 'backlog') = %s")
                params.append(pilot_cohort)
            if q:
                where_sql.append("(LOWER(COALESCE(name, '')) LIKE %s OR LOWER(COALESCE(source_url, '')) LIKE %s)")
                q_like = f"%{q}%"
                params.extend([q_like, q_like])

            cur.execute(
                f"""
                SELECT prospectingleads.id, prospectingleads.name, prospectingleads.address, prospectingleads.city,
                       prospectingleads.category, prospectingleads.source_url, prospectingleads.source,
                       prospectingleads.source_kind, prospectingleads.source_provider,
                       prospectingleads.external_place_id, prospectingleads.external_source_id,
                       prospectingleads.dedupe_key, prospectingleads.lat, prospectingleads.lon,
                       prospectingleads.search_payload_json, prospectingleads.enrich_payload_json,
                       prospectingleads.deferred_reason, prospectingleads.deferred_until,
                       prospectingleads.phone, prospectingleads.email, prospectingleads.telegram_url,
                       prospectingleads.whatsapp_url, prospectingleads.website, prospectingleads.rating,
                       prospectingleads.reviews_count, prospectingleads.status,
                       COALESCE(active_ws.selected_channel, prospectingleads.selected_channel) AS selected_channel,
                       prospectingleads.intent, prospectingleads.partnership_stage, prospectingleads.pilot_cohort,
                       COALESCE(active_ws.status, prospectingleads.pipeline_status, 'unprocessed') AS pipeline_status,
                       prospectingleads.disqualification_reason,
                       prospectingleads.disqualification_comment, prospectingleads.postponed_comment,
                       COALESCE(active_ws.next_action_at, prospectingleads.next_action_at) AS next_action_at,
                       COALESCE(active_ws.last_contact_at, prospectingleads.last_contact_at) AS last_contact_at,
                       COALESCE(active_ws.last_contact_channel, prospectingleads.last_contact_channel) AS last_contact_channel,
                       COALESCE(active_ws.last_contact_comment, prospectingleads.last_contact_comment) AS last_contact_comment,
                       prospectingleads.parse_business_id, prospectingleads.updated_at,
                       prospectingleads.created_at,
                       active_ws.id AS active_workstream_id,
                       (
                           SELECT client_business.name
                           FROM businesses client_business
                           WHERE client_business.id = prospectingleads.business_id
                           LIMIT 1
                       ) AS client_business_name,
                       pq_last.id AS parse_task_id,
                       pq_last.status AS parse_status,
                       COALESCE(pq_last.updated_at, pq_last.created_at) AS parse_updated_at,
                       pq_last.retry_after AS parse_retry_after,
                       pq_last.error_message AS parse_error,
                       sr_last.status AS sales_room_status,
                       sr_last.data_mode AS sales_room_data_mode,
                       sr_last.slug AS sales_room_slug,
                       sr_last.updated_at AS sales_room_updated_at,
                       COALESCE(artifact_last.audit_ready, FALSE) AS audit_ready,
                       artifact_last.match_json AS match_summary_json,
                       artifact_last.updated_at AS artifact_updated_at
                FROM prospectingleads
                JOIN lead_workstreams active_ws ON active_ws.lead_id = prospectingleads.id
                LEFT JOIN LATERAL (
                    SELECT
                        pq.id, pq.status, pq.updated_at, pq.created_at, pq.retry_after, pq.error_message
                    FROM parsequeue pq
                    WHERE (
                            (prospectingleads.parse_business_id IS NOT NULL AND pq.business_id = prospectingleads.parse_business_id)
                            OR (
                                prospectingleads.parse_business_id IS NULL
                                AND prospectingleads.source_url IS NOT NULL
                                AND prospectingleads.source_url <> ''
                                AND pq.url = prospectingleads.source_url
                            )
                          )
                      AND pq.task_type IN ('parse_card', 'sync_yandex_business')
                    ORDER BY COALESCE(pq.updated_at, pq.created_at) DESC
                    LIMIT 1
                ) pq_last ON TRUE
                LEFT JOIN LATERAL (
                    SELECT status, data_mode, slug, updated_at
                    FROM sales_rooms sr
                    WHERE sr.lead_id = prospectingleads.id
                      AND (sr.workstream_id = active_ws.id OR sr.workstream_id IS NULL)
                    ORDER BY sr.updated_at DESC
                    LIMIT 1
                ) sr_last ON TRUE
                LEFT JOIN LATERAL (
                    SELECT
                        COALESCE(audit_json, '{{}}'::jsonb) <> '{{}}'::jsonb AS audit_ready,
                        match_json,
                        updated_at
                    FROM partnershipleadartifacts artifact
                    WHERE artifact.lead_id = prospectingleads.id
                    LIMIT 1
                ) artifact_last ON TRUE
                WHERE {' AND '.join(where_sql)}
                ORDER BY active_ws.updated_at DESC NULLS LAST, prospectingleads.created_at DESC
                LIMIT %s OFFSET %s
                """,
                (*params, limit, offset),
            )
            rows = cur.fetchall()
        finally:
            conn.close()

        items = []
        for row in rows:
            payload = dict(row) if hasattr(row, "keys") else {}
            parse_status = str(payload.get("parse_status") or "").strip().lower()
            if parse_status in {"completed", "done"}:
                payload = _sync_partnership_lead_from_parsed_data(payload)
            sales_room_slug = str(payload.get("sales_room_slug") or "").strip()
            if sales_room_slug:
                payload["sales_room_url"] = _make_sales_room_url(sales_room_slug)
            payload["next_best_action"] = _partnership_next_best_action(payload)
            items.append(payload)
        attach_conn = get_db_connection()
        try:
            items = attach_workstreams(attach_conn, items)
        finally:
            attach_conn.close()
        return jsonify({"success": True, "count": len(items), "items": items})
    except Exception as e:
        print(f"Error listing partnership leads: {e}")
        return jsonify({"error": str(e)}), 500


def create_lead_workstream(lead_id):
    """Attach an independent LocalOS sales or client partnership context."""
    user_data, error = _require_superadmin()
    if error:
        return error

    data = request.get_json(silent=True) or {}
    workstream_type = normalize_workstream_type(data.get("workstream_type"))
    if workstream_type not in {LOCALOS_SALES, CLIENT_PARTNERSHIP}:
        return jsonify({"error": "Unsupported workstream_type"}), 400
    client_business_id = str(data.get("client_business_id") or "").strip() or None
    try:
        conn = get_db_connection()
        try:
            workstream = create_workstream(
                conn,
                lead_id=lead_id,
                workstream_type=workstream_type,
                client_business_id=client_business_id,
                actor_id=str(user_data.get("user_id") or "") or None,
            )
            conn.commit()
        finally:
            conn.close()
        return jsonify({"success": True, "workstream": _to_json_compatible(workstream)})
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        print(f"Error creating lead workstream: {exc}")
        return jsonify({"error": str(exc)}), 500


def partnership_update_lead(lead_id):
    """User-level stage update for partnership lead."""
    user_data, error = _require_auth()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        requested_business_id = str(data.get("business_id") or "").strip() or None
        stage = str(data.get("partnership_stage") or "").strip().lower()
        status = str(data.get("status") or "").strip().lower()
        pipeline_status = str(data.get("pipeline_status") or "").strip().lower()
        selected_channel = str(data.get("selected_channel") or "").strip().lower() or None
        pilot_cohort = str(data.get("pilot_cohort") or "").strip().lower() or None
        deferred_reason_present = "deferred_reason" in data
        deferred_reason = str(data.get("deferred_reason") or "").strip() if deferred_reason_present else None
        deferred_until_present = "deferred_until" in data
        deferred_until_raw = str(data.get("deferred_until") or "").strip() if deferred_until_present else None
        deferred_until = deferred_until_raw or None
        name = str(data.get("name") or "").strip() or None
        city = str(data.get("city") or "").strip() or None
        category = str(data.get("category") or "").strip() or None
        address = str(data.get("address") or "").strip() or None
        phone = str(data.get("phone") or "").strip() or None
        email = str(data.get("email") or "").strip() or None
        website = str(data.get("website") or "").strip() or None
        telegram_url = str(data.get("telegram_url") or "").strip() or None
        whatsapp_url = str(data.get("whatsapp_url") or "").strip() or None
        if (
            not stage
            and not status
            and not pipeline_status
            and selected_channel is None
            and pilot_cohort is None
            and not deferred_reason_present
            and not deferred_until_present
            and name is None
            and city is None
            and category is None
            and address is None
            and phone is None
            and email is None
            and website is None
            and telegram_url is None
            and whatsapp_url is None
        ):
            return jsonify({"error": "Nothing to update"}), 400

        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
            cur.execute(
                """
                SELECT l.id, l.name, l.telegram_url, l.whatsapp_url, l.email, ws.id AS workstream_id
                FROM prospectingleads l
                JOIN lead_workstreams ws ON ws.lead_id = l.id
                WHERE l.id = %s
                  AND ws.client_business_id = %s
                  AND ws.workstream_type = 'client_partnership'
                """,
                (lead_id, business_id),
            )
            existing_row = cur.fetchone()
            if not existing_row:
                return jsonify({"error": "Lead not found"}), 404
            existing_lead = dict(existing_row)
            candidate_lead = {
                **existing_lead,
                "telegram_url": telegram_url if telegram_url is not None else existing_lead.get("telegram_url"),
                "whatsapp_url": whatsapp_url if whatsapp_url is not None else existing_lead.get("whatsapp_url"),
                "email": email if email is not None else existing_lead.get("email"),
            }
            if selected_channel is not None and not _lead_has_channel_contact(candidate_lead, selected_channel):
                return jsonify({"error": _outreach_channel_contact_error(selected_channel)}), 400
            if pipeline_status and pipeline_status not in ALLOWED_PIPELINE_STATUSES:
                return jsonify({"error": f"pipeline_status must be one of: {', '.join(sorted(ALLOWED_PIPELINE_STATUSES))}"}), 400

            assignments = ["updated_at = NOW()"]
            params: list[Any] = []
            if stage:
                assignments.append("partnership_stage = %s")
                params.append(stage)
                if not pipeline_status:
                    if stage == "deferred":
                        pipeline_status = PIPELINE_POSTPONED
                    elif stage in {"rejected", "shortlist_rejected"}:
                        pipeline_status = PIPELINE_NOT_RELEVANT
                    elif stage in {"approved_for_send", "sent"}:
                        pipeline_status = PIPELINE_CONTACTED
                    elif stage not in {"imported"}:
                        pipeline_status = PIPELINE_IN_PROGRESS
            if pilot_cohort is not None:
                assignments.append("pilot_cohort = %s")
                params.append(pilot_cohort)
            if deferred_reason_present:
                assignments.append("deferred_reason = %s")
                params.append(deferred_reason)
            if deferred_until_present:
                assignments.append("deferred_until = %s")
                params.append(deferred_until)
            if name is not None:
                assignments.append("name = %s")
                params.append(name)
            if city is not None:
                assignments.append("city = %s")
                params.append(city)
            if category is not None:
                assignments.append("category = %s")
                params.append(category)
            if address is not None:
                assignments.append("address = %s")
                params.append(address)
            if phone is not None:
                assignments.append("phone = %s")
                params.append(phone)
            if email is not None:
                assignments.append("email = %s")
                params.append(email)
            if website is not None:
                assignments.append("website = %s")
                params.append(website)
            if telegram_url is not None:
                assignments.append("telegram_url = %s")
                params.append(telegram_url)
            if whatsapp_url is not None:
                assignments.append("whatsapp_url = %s")
                params.append(whatsapp_url)

            params.append(lead_id)
            cur.execute(
                f"""
                UPDATE prospectingleads
                SET {', '.join(assignments)}
                WHERE id = %s
                RETURNING id, name, source_url, status, selected_channel, partnership_stage, pipeline_status, pilot_cohort,
                          deferred_reason, deferred_until, phone, email, website, telegram_url, whatsapp_url, city, category, address, updated_at
                """,
                tuple(params),
            )
            updated = cur.fetchone()
            if not updated:
                return jsonify({"error": "Lead not found"}), 404
            workstream_status = pipeline_status or status or str(existing_lead.get("status") or PIPELINE_UNPROCESSED)
            updated_workstream = update_workstream(
                conn,
                workstream_id=str(existing_lead.get("workstream_id") or ""),
                status=workstream_status,
                selected_channel=selected_channel,
                next_action_at=deferred_until if deferred_until_present else None,
            )
            if pipeline_status == PIPELINE_CONVERTED:
                ensure_ai_learning_events_table(conn)
                cur.execute(
                    """
                    SELECT id, learning_note_json, generated_text, approved_text, edited_text
                    FROM outreachmessagedrafts
                    WHERE lead_id = %s
                      AND (workstream_id = %s OR workstream_id IS NULL)
                    ORDER BY updated_at DESC, created_at DESC
                    LIMIT 1
                    """,
                    (lead_id, str(existing_lead.get("workstream_id") or "")),
                )
                draft_row = cur.fetchone()
                draft_context = dict(draft_row) if draft_row and hasattr(draft_row, "keys") else {}
                learning_note = draft_context.get("learning_note_json")
                if not isinstance(learning_note, dict):
                    learning_note = {}
                prompt_meta = _normalize_prompt_meta(
                    learning_note,
                    fallback_key="partners.draft_first_note",
                    fallback_version="unknown",
                    fallback_source="unknown",
                )
                final_text = str(
                    draft_context.get("approved_text")
                    or draft_context.get("edited_text")
                    or draft_context.get("generated_text")
                    or ""
                ).strip()
                record_ai_learning_event(
                    capability="partnership.draft_offer",
                    event_type="outcome",
                    intent="partnership_outreach",
                    user_id=user_data.get("user_id"),
                    business_id=business_id,
                    outcome="partner",
                    prompt_key=prompt_meta.get("prompt_key"),
                    prompt_version=prompt_meta.get("prompt_version"),
                    final_text=final_text[:3000] if final_text else None,
                    metadata={
                        "lead_id": lead_id,
                        "draft_id": str(draft_context.get("id") or ""),
                        "pipeline_status": pipeline_status,
                        "partnership_outcome": "partner",
                        **learning_note,
                        **prompt_meta,
                    },
                    conn=conn,
                )
            conn.commit()
        finally:
            conn.close()

        item = dict(updated) if hasattr(updated, "keys") else updated
        if isinstance(item, dict):
            item["active_workstream_id"] = updated_workstream.get("id")
            item["pipeline_status"] = updated_workstream.get("status")
            item["selected_channel"] = updated_workstream.get("selected_channel")
        return jsonify({"success": True, "item": item, "workstream": _to_json_compatible(updated_workstream)})
    except Exception as e:
        print(f"Error updating partnership lead: {e}")
        return jsonify({"error": str(e)}), 500


def partnership_mark_lead_manual_contact(lead_id):
    """User-level manual contact marker for room-first partnership outreach."""
    user_data, error = _require_auth()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        requested_business_id = str(data.get("business_id") or "").strip() or None
        channel = str(data.get("channel") or "manual").strip().lower() or "manual"
        comment = str(data.get("comment") or "").strip() or "Отправлено вручную из цифровой комнаты"
        if channel not in ALLOWED_OUTREACH_CHANNELS:
            return jsonify({"error": "Unsupported channel"}), 400

        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            _ensure_manual_crm_tables(conn)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
            cur.execute(
                """
                SELECT l.*, ws.id AS workstream_id
                FROM prospectingleads l
                JOIN lead_workstreams ws ON ws.lead_id = l.id
                WHERE l.id = %s
                  AND ws.client_business_id = %s
                  AND ws.workstream_type = 'client_partnership'
                LIMIT 1
                """,
                (lead_id, business_id),
            )
            lead = cur.fetchone()
            if not lead:
                return jsonify({"error": "Lead not found"}), 404
            lead_payload = dict(lead)
            if channel != "manual" and not _lead_has_channel_contact(lead_payload, channel):
                return jsonify({"error": _outreach_channel_contact_error(channel)}), 400

            updated_workstream = update_workstream(
                conn,
                workstream_id=str(lead_payload.get("workstream_id") or ""),
                status=PIPELINE_CONTACTED,
                selected_channel=channel,
                last_contact=True,
                last_contact_comment=comment,
            )
            _record_lead_timeline_event(
                cur,
                lead_id=lead_id,
                workstream_id=str(lead_payload.get("workstream_id") or ""),
                event_type="manual_contact_marked",
                actor_id=str(user_data.get("user_id") or "") or None,
                comment=comment,
                payload={"channel": channel, "source": "partnership_room"},
            )
            conn.commit()
            updated = _normalize_lead_for_display(lead_payload) or lead_payload
            updated["pipeline_status"] = updated_workstream.get("status")
            updated["selected_channel"] = updated_workstream.get("selected_channel")
        finally:
            conn.close()

        return jsonify({
            "success": True,
            "lead": _to_json_compatible(updated),
            "workstream": _to_json_compatible(updated_workstream),
        })
    except Exception as e:
        print(f"Error marking partnership manual contact: {e}")
        return jsonify({"error": str(e)}), 500


def partnership_bulk_update_leads():
    """Bulk update stage/channel/status for partnership leads."""
    user_data, error = _require_auth()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        requested_business_id = str(data.get("business_id") or "").strip() or None
        lead_ids_raw = data.get("lead_ids") or []
        lead_ids = [str(item).strip() for item in lead_ids_raw if str(item).strip()]
        lead_ids = list(dict.fromkeys(lead_ids))
        stage = str(data.get("partnership_stage") or "").strip().lower()
        status = str(data.get("status") or "").strip().lower()
        pipeline_status = str(data.get("pipeline_status") or "").strip().lower()
        selected_channel = str(data.get("selected_channel") or "").strip().lower() or None
        pilot_cohort = str(data.get("pilot_cohort") or "").strip().lower() or None
        deferred_reason_present = "deferred_reason" in data
        deferred_reason = str(data.get("deferred_reason") or "").strip() if deferred_reason_present else None
        deferred_until_present = "deferred_until" in data
        deferred_until_raw = str(data.get("deferred_until") or "").strip() if deferred_until_present else None
        deferred_until = deferred_until_raw or None

        if not lead_ids:
            return jsonify({"error": "lead_ids is required"}), 400
        if not stage and not status and not pipeline_status and selected_channel is None and pilot_cohort is None and not deferred_reason_present and not deferred_until_present:
            return jsonify({"error": "Nothing to update"}), 400
        if selected_channel is not None and selected_channel not in ALLOWED_OUTREACH_CHANNELS:
            return jsonify({"error": "Unsupported channel"}), 400
        if pipeline_status and pipeline_status not in ALLOWED_PIPELINE_STATUSES:
            return jsonify({"error": f"pipeline_status must be one of: {', '.join(sorted(ALLOWED_PIPELINE_STATUSES))}"}), 400

        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
            if selected_channel is not None and selected_channel != "manual":
                cur.execute(
                    """
                    SELECT l.id, l.name, l.telegram_url, l.whatsapp_url, l.email
                    FROM prospectingleads l
                    JOIN lead_workstreams ws ON ws.lead_id = l.id
                    WHERE l.id = ANY(%s)
                      AND ws.client_business_id = %s
                      AND ws.workstream_type = 'client_partnership'
                    """,
                    (lead_ids, business_id),
                )
                rows = [dict(row) for row in cur.fetchall() or []]
                invalid = [row for row in rows if not _lead_has_channel_contact(row, selected_channel)]
                if invalid:
                    example = str(invalid[0].get("name") or invalid[0].get("id") or "lead")
                    return jsonify({
                        "error": f"{_outreach_channel_contact_error(selected_channel)}: {example}",
                        "invalid_ids": [str(row.get("id") or "") for row in invalid if str(row.get("id") or "").strip()],
                    }), 400

            assignments = ["updated_at = NOW()"]
            params: list[Any] = []
            if stage:
                assignments.append("partnership_stage = %s")
                params.append(stage)
                if not pipeline_status:
                    if stage == "deferred":
                        pipeline_status = PIPELINE_POSTPONED
                    elif stage in {"rejected", "shortlist_rejected"}:
                        pipeline_status = PIPELINE_NOT_RELEVANT
                    elif stage in {"approved_for_send", "sent"}:
                        pipeline_status = PIPELINE_CONTACTED
                    elif stage not in {"imported"}:
                        pipeline_status = PIPELINE_IN_PROGRESS
            if pilot_cohort is not None:
                assignments.append("pilot_cohort = %s")
                params.append(pilot_cohort)
            if deferred_reason_present:
                assignments.append("deferred_reason = %s")
                params.append(deferred_reason)
            if deferred_until_present:
                assignments.append("deferred_until = %s")
                params.append(deferred_until)

            params.extend([lead_ids, business_id])
            cur.execute(
                f"""
                UPDATE prospectingleads
                SET {', '.join(assignments)}
                WHERE id = ANY(%s)
                  AND EXISTS (
                      SELECT 1
                      FROM lead_workstreams ws
                      WHERE ws.lead_id = prospectingleads.id
                        AND ws.client_business_id = %s
                        AND ws.workstream_type = 'client_partnership'
                  )
                RETURNING id
                """,
                tuple(params),
            )
            rows = cur.fetchall() or []
            updated_ids = [row["id"] if hasattr(row, "get") else row[0] for row in rows]
            workstream_status = pipeline_status or status
            if updated_ids and (workstream_status or selected_channel is not None or deferred_until_present):
                cur.execute(
                    """
                    UPDATE lead_workstreams
                    SET status = COALESCE(%s, status),
                        selected_channel = CASE WHEN %s THEN %s ELSE selected_channel END,
                        next_action_at = CASE WHEN %s THEN %s ELSE next_action_at END,
                        updated_at = NOW()
                    WHERE lead_id = ANY(%s)
                      AND client_business_id = %s
                      AND workstream_type = 'client_partnership'
                    """,
                    (
                        workstream_status,
                        selected_channel is not None,
                        selected_channel,
                        deferred_until_present,
                        deferred_until,
                        updated_ids,
                        business_id,
                    ),
                )
            if pipeline_status == PIPELINE_CONVERTED and updated_ids:
                ensure_ai_learning_events_table(conn)
                cur.execute(
                    """
                    SELECT DISTINCT ON (lead_id)
                        id, lead_id, learning_note_json, generated_text, approved_text, edited_text
                    FROM outreachmessagedrafts
                    WHERE lead_id = ANY(%s)
                    ORDER BY lead_id, updated_at DESC, created_at DESC
                    """,
                    (updated_ids,),
                )
                draft_rows = [dict(row) for row in cur.fetchall() or []]
                drafts_by_lead = {str(row.get("lead_id") or ""): row for row in draft_rows}
                for current_lead_id in updated_ids:
                    draft_context = drafts_by_lead.get(str(current_lead_id)) or {}
                    learning_note = draft_context.get("learning_note_json")
                    if not isinstance(learning_note, dict):
                        learning_note = {}
                    prompt_meta = _normalize_prompt_meta(
                        learning_note,
                        fallback_key="partners.draft_first_note",
                        fallback_version="unknown",
                        fallback_source="unknown",
                    )
                    final_text = str(
                        draft_context.get("approved_text")
                        or draft_context.get("edited_text")
                        or draft_context.get("generated_text")
                        or ""
                    ).strip()
                    record_ai_learning_event(
                        capability="partnership.draft_offer",
                        event_type="outcome",
                        intent="partnership_outreach",
                        user_id=user_data.get("user_id"),
                        business_id=business_id,
                        outcome="partner",
                        prompt_key=prompt_meta.get("prompt_key"),
                        prompt_version=prompt_meta.get("prompt_version"),
                        final_text=final_text[:3000] if final_text else None,
                        metadata={
                            "lead_id": str(current_lead_id),
                            "draft_id": str(draft_context.get("id") or ""),
                            "pipeline_status": pipeline_status,
                            "partnership_outcome": "partner",
                            **learning_note,
                            **prompt_meta,
                        },
                        conn=conn,
                    )
            conn.commit()
        finally:
            conn.close()

        return jsonify({"success": True, "updated_count": len(updated_ids), "updated_ids": updated_ids})
    except Exception as e:
        print(f"Error bulk updating partnership leads: {e}")
        return jsonify({"error": str(e)}), 500


def partnership_delete_lead(lead_id):
    """Delete one partnership lead (with linked artifacts via FK cascade)."""
    user_data, error = _require_auth()
    if error:
        return error
    try:
        requested_business_id = str(request.args.get("business_id") or "").strip() or None
        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            _ensure_partnership_artifacts_table(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
            cur.execute(
                """
                DELETE FROM lead_workstreams
                WHERE lead_id = %s
                  AND client_business_id = %s
                  AND workstream_type = 'client_partnership'
                RETURNING lead_id
                """,
                (lead_id, business_id),
            )
            deleted = cur.fetchone()
            if not deleted:
                return jsonify({"error": "Lead not found"}), 404
            cur.execute("SELECT 1 FROM lead_workstreams WHERE lead_id = %s LIMIT 1", (lead_id,))
            if not cur.fetchone():
                cur.execute("DELETE FROM prospectingleads WHERE id = %s", (lead_id,))
            conn.commit()
        finally:
            conn.close()
        return jsonify({"success": True, "deleted_id": lead_id})
    except Exception as e:
        print(f"Error deleting partnership lead: {e}")
        return jsonify({"error": str(e)}), 500


def partnership_bulk_delete_leads():
    """Bulk delete partnership leads and linked artifacts."""
    user_data, error = _require_auth()
    if error:
        return error
    try:
        data = request.get_json(silent=True) or {}
        requested_business_id = str(data.get("business_id") or "").strip() or None
        lead_ids_raw = data.get("lead_ids") or []
        lead_ids = [str(item).strip() for item in lead_ids_raw if str(item).strip()]
        lead_ids = list(dict.fromkeys(lead_ids))
        if not lead_ids:
            return jsonify({"error": "lead_ids is required"}), 400

        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            _ensure_partnership_artifacts_table(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
            cur.execute(
                """
                DELETE FROM lead_workstreams
                WHERE lead_id = ANY(%s)
                  AND client_business_id = %s
                  AND workstream_type = 'client_partnership'
                RETURNING lead_id
                """,
                (lead_ids, business_id),
            )
            rows = cur.fetchall() or []
            deleted_lead_ids = [row["lead_id"] if hasattr(row, "get") else row[0] for row in rows]
            if deleted_lead_ids:
                cur.execute(
                    """
                    DELETE FROM prospectingleads l
                    WHERE l.id = ANY(%s)
                      AND NOT EXISTS (
                          SELECT 1 FROM lead_workstreams ws WHERE ws.lead_id = l.id
                      )
                    """,
                    (deleted_lead_ids,),
                )
            conn.commit()
        finally:
            conn.close()

        deleted_ids = [row["lead_id"] if hasattr(row, "get") else row[0] for row in rows]
        return jsonify({"success": True, "deleted_count": len(deleted_ids), "deleted_ids": deleted_ids})
    except Exception as e:
        print(f"Error bulk deleting partnership leads: {e}")
        return jsonify({"error": str(e)}), 500


def partnership_prepare_sales_room(lead_id):
    user_data, error = _require_auth()
    if error:
        return error
    try:
        data = request.get_json(silent=True) or {}
        requested_business_id = str(data.get("business_id") or "").strip() or None
        data_mode = _normalize_sales_room_data_mode(data.get("data_mode"))
        channel = str(data.get("channel") or "manual").strip().lower()
        if channel not in ALLOWED_OUTREACH_CHANNELS:
            channel = "manual"
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
        finally:
            conn.close()
        if not business_id:
            return jsonify({"error": "Business not found or access denied"}), 403
        result = _prepare_partnership_sales_room(
            lead_id=lead_id,
            business_id=business_id,
            user_id=str(user_data.get("user_id") or ""),
            data_mode=data_mode,
            channel=channel,
            audit_offer=data.get("audit_offer") if isinstance(data.get("audit_offer"), dict) else None,
            reuse_existing=bool(data.get("reuse_existing")),
            workstream_id=str(data.get("workstream_id") or "").strip() or None,
        )
        if result.get("error"):
            return jsonify(result), int(result.get("status_code") or 400)
        return jsonify(_to_json_compatible(result))
    except Exception as e:
        print(f"Error partnership prepare sales room: {e}")
        return jsonify({"error": str(e)}), 500


def update_lead_status(lead_id):
    """Update lead pipeline status or legacy status with manual-first validation."""
    user_data, error = _require_superadmin()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        requested_status = str(data.get("pipeline_status") or data.get("status") or "").strip().lower()
        legacy_to_pipeline = {
            "new": PIPELINE_UNPROCESSED,
            SHORTLIST_APPROVED: PIPELINE_IN_PROGRESS,
            SELECTED_FOR_OUTREACH: PIPELINE_IN_PROGRESS,
            CHANNEL_SELECTED: PIPELINE_IN_PROGRESS,
            "draft_ready": PIPELINE_IN_PROGRESS,
            QUEUED_FOR_SEND: PIPELINE_IN_PROGRESS,
            "sent": PIPELINE_CONTACTED,
            "delivered": PIPELINE_CONTACTED,
            "second_message_sent": PIPELINE_SECOND_MESSAGE_SENT,
            "responded": PIPELINE_REPLIED,
            "qualified": PIPELINE_CONVERTED,
            "converted": PIPELINE_CONVERTED,
            "deferred": PIPELINE_POSTPONED,
            SHORTLIST_REJECTED: PIPELINE_NOT_RELEVANT,
            "rejected": PIPELINE_NOT_RELEVANT,
            "closed": PIPELINE_CLOSED_LOST,
        }
        pipeline_status = legacy_to_pipeline.get(requested_status, requested_status)
        comment = str(data.get("comment") or "").strip() or None
        disqualification_reason = str(data.get("disqualification_reason") or "").strip().lower() or None
        disqualification_comment = str(data.get("disqualification_comment") or "").strip() or None
        postponed_comment = str(data.get("postponed_comment") or data.get("comment") or "").strip() or None
        next_action_at = str(data.get("next_action_at") or "").strip() or None
        workstream_id = str(data.get("workstream_id") or "").strip() or None

        if pipeline_status not in ALLOWED_PIPELINE_STATUSES:
            return jsonify({"error": f"pipeline_status must be one of: {', '.join(sorted(ALLOWED_PIPELINE_STATUSES))}"}), 400
        if pipeline_status == PIPELINE_NOT_RELEVANT:
            if disqualification_reason not in NOT_RELEVANT_REASONS:
                return jsonify({"error": "disqualification_reason is required"}), 400
            if disqualification_reason == "other" and not disqualification_comment:
                return jsonify({"error": "disqualification_comment is required for reason=other"}), 400
        if pipeline_status == PIPELINE_POSTPONED and not postponed_comment:
            return jsonify({"error": "postponed_comment is required"}), 400

        conn = get_db_connection()
        try:
            _ensure_manual_crm_tables(conn)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            if workstream_id:
                workstream = resolve_workstream(
                    conn,
                    lead_id=lead_id,
                    workstream_id=workstream_id,
                )
                updated_workstream = update_workstream(
                    conn,
                    workstream_id=str(workstream.get("id") or ""),
                    status=pipeline_status,
                    next_action_at=next_action_at if pipeline_status == PIPELINE_POSTPONED else None,
                )
                _record_lead_timeline_event(
                    cur,
                    lead_id=lead_id,
                    workstream_id=workstream_id,
                    event_type="workstream_status_changed",
                    actor_id=str(user_data.get("user_id") or "") or None,
                    comment=comment,
                    payload={"pipeline_status": pipeline_status},
                )
                cur.execute("SELECT * FROM prospectingleads WHERE id = %s", (lead_id,))
                lead_row = cur.fetchone()
                conn.commit()
                lead_payload = dict(lead_row) if lead_row else {"id": lead_id}
                return jsonify({
                    "success": True,
                    "lead": _to_json_compatible(lead_payload),
                    "workstream": _to_json_compatible(updated_workstream),
                })
            updated = _apply_pipeline_transition(
                cur,
                lead_id=lead_id,
                pipeline_status=pipeline_status,
                actor_id=str(user_data.get("user_id") or "") or None,
                comment=comment,
                disqualification_reason=disqualification_reason if pipeline_status == PIPELINE_NOT_RELEVANT else None,
                disqualification_comment=disqualification_comment if pipeline_status == PIPELINE_NOT_RELEVANT else None,
                postponed_comment=postponed_comment if pipeline_status == PIPELINE_POSTPONED else None,
                next_action_at=next_action_at if pipeline_status == PIPELINE_POSTPONED else None,
            )
            if not updated:
                return jsonify({"error": "Lead not found"}), 404
            conn.commit()
            updated = _normalize_lead_for_display(updated) or updated
        finally:
            conn.close()

        return jsonify({"success": True, "lead": _to_json_compatible(updated)})
    except Exception as e:
        print(f"Error updating lead status: {e}")
        return jsonify({"error": str(e)}), 500


def mark_lead_manual_contact(lead_id):
    """Mark lead as contacted manually without requiring queue dispatch."""
    user_data, error = _require_superadmin()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        channel = str(data.get("channel") or "manual").strip().lower() or "manual"
        comment = str(data.get("comment") or "").strip() or None
        workstream_id = str(data.get("workstream_id") or "").strip() or None
        if channel not in ALLOWED_OUTREACH_CHANNELS:
            return jsonify({"error": "Unsupported channel"}), 400

        conn = get_db_connection()
        try:
            _ensure_manual_crm_tables(conn)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT * FROM prospectingleads WHERE id = %s", (lead_id,))
            lead = cur.fetchone()
            if not lead:
                return jsonify({"error": "Lead not found"}), 404
            lead_payload = dict(lead)
            if channel != "manual" and not _lead_has_channel_contact(lead_payload, channel):
                return jsonify({"error": _outreach_channel_contact_error(channel)}), 400
            if workstream_id:
                workstream = resolve_workstream(
                    conn,
                    lead_id=lead_id,
                    workstream_id=workstream_id,
                )
                updated_workstream = update_workstream(
                    conn,
                    workstream_id=str(workstream.get("id") or ""),
                    status=PIPELINE_CONTACTED,
                    selected_channel=channel,
                    last_contact=True,
                    last_contact_comment=comment,
                )
                _record_lead_timeline_event(
                    cur,
                    lead_id=lead_id,
                    workstream_id=workstream_id,
                    event_type="manual_contact_marked",
                    actor_id=str(user_data.get("user_id") or "") or None,
                    comment=comment,
                    payload={"channel": channel},
                )
                conn.commit()
                return jsonify({
                    "success": True,
                    "lead": _to_json_compatible(lead_payload),
                    "workstream": _to_json_compatible(updated_workstream),
                })
            updated = _apply_pipeline_transition(
                cur,
                lead_id=lead_id,
                pipeline_status=PIPELINE_CONTACTED,
                actor_id=str(user_data.get("user_id") or "") or None,
                comment=comment or "Manual contact marked",
                last_contact_channel=channel,
                last_contact_comment=comment,
                set_last_contact_at=True,
            )
            _record_lead_timeline_event(
                cur,
                lead_id=lead_id,
                event_type="manual_contact_marked",
                actor_id=str(user_data.get("user_id") or "") or None,
                comment=comment,
                payload={"channel": channel},
            )
            conn.commit()
            updated = _normalize_lead_for_display(updated or lead_payload) or updated or lead_payload
        finally:
            conn.close()

        return jsonify({"success": True, "lead": _to_json_compatible(updated)})
    except Exception as e:
        print(f"Error marking manual lead contact: {e}")
        return jsonify({"error": str(e)}), 500


def add_lead_comment(lead_id):
    """Add free-form operator note to lead timeline."""
    user_data, error = _require_superadmin()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        comment = str(data.get("comment") or "").strip()
        workstream_id = str(data.get("workstream_id") or "").strip() or None
        if not comment:
            return jsonify({"error": "comment is required"}), 400

        conn = get_db_connection()
        try:
            _ensure_manual_crm_tables(conn)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                """
                UPDATE prospectingleads
                SET last_manual_action_at = NOW(),
                    last_manual_action_by = %s,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING *
                """,
                (str(user_data.get("user_id") or "") or None, lead_id),
            )
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Lead not found"}), 404
            if workstream_id:
                resolve_workstream(conn, lead_id=lead_id, workstream_id=workstream_id)
            _record_lead_timeline_event(
                cur,
                lead_id=lead_id,
                workstream_id=workstream_id,
                event_type="comment_added",
                actor_id=str(user_data.get("user_id") or "") or None,
                comment=comment,
            )
            conn.commit()
            lead = _normalize_lead_for_display(dict(row)) or dict(row)
        finally:
            conn.close()
        return jsonify({"success": True, "lead": _to_json_compatible(lead)})
    except Exception as e:
        print(f"Error adding lead comment: {e}")
        return jsonify({"error": str(e)}), 500


def get_lead_timeline(lead_id):
    """Return manual/automation timeline for one lead."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        conn = get_db_connection()
        try:
            _ensure_manual_crm_tables(conn)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT 1 FROM prospectingleads WHERE id = %s", (lead_id,))
            if not cur.fetchone():
                return jsonify({"error": "Lead not found"}), 404
            workstream_id = str(request.args.get("workstream_id") or "").strip() or None
            cur.execute(
                """
                SELECT id, lead_id, workstream_id, event_type, actor_id, comment, payload_json, created_at
                FROM lead_timeline_events
                WHERE lead_id = %s
                  AND (%s IS NULL OR workstream_id = %s)
                ORDER BY created_at DESC
                LIMIT 200
                """,
                (lead_id, workstream_id, workstream_id),
            )
            events = [dict(row) for row in cur.fetchall() or []]
        finally:
            conn.close()
        return jsonify({"success": True, "events": _to_json_compatible(events), "count": len(events)})
    except Exception as e:
        print(f"Error loading lead timeline: {e}")
        return jsonify({"error": str(e)}), 500


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


def select_outreach_channel(lead_id):
    """Select outreach channel for lead and advance to channel_selected."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        channel = (data.get("channel") or "").strip().lower()
        workstream_id = str(data.get("workstream_id") or "").strip() or None
        if channel not in ALLOWED_OUTREACH_CHANNELS:
            return jsonify({"error": "Channel must be one of: telegram, whatsapp, max, email, manual"}), 400

        if workstream_id:
            conn = get_db_connection()
            try:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute("SELECT * FROM prospectingleads WHERE id = %s", (lead_id,))
                lead = cur.fetchone()
                if not lead:
                    return jsonify({"error": "Lead not found"}), 404
                lead_payload = dict(lead)
                if not _lead_has_channel_contact(lead_payload, channel):
                    return jsonify({"error": _outreach_channel_contact_error(channel)}), 400
                workstream = resolve_workstream(
                    conn,
                    lead_id=lead_id,
                    workstream_id=workstream_id,
                )
                updated_workstream = update_workstream(
                    conn,
                    workstream_id=str(workstream.get("id") or ""),
                    status=PIPELINE_IN_PROGRESS,
                    selected_channel=channel,
                )
                _record_lead_timeline_event(
                    cur,
                    lead_id=lead_id,
                    workstream_id=workstream_id,
                    event_type="workstream_channel_selected",
                    payload={"channel": channel},
                )
                conn.commit()
            finally:
                conn.close()
            return jsonify({
                "success": True,
                "lead": _to_json_compatible(lead_payload),
                "workstream": _to_json_compatible(updated_workstream),
                "selected_channel": channel,
            })

        with DatabaseManager() as db:
            lead = db.get_lead_by_id(lead_id)
            if not lead:
                return jsonify({"error": "Lead not found"}), 404
            if lead.get("status") not in {SELECTED_FOR_OUTREACH, CHANNEL_SELECTED}:
                return jsonify({"error": "Lead must be selected for outreach before channel selection"}), 400
            if not _lead_has_channel_contact(lead, channel):
                return jsonify({"error": _outreach_channel_contact_error(channel)}), 400
            success = db.update_lead_outreach(lead_id, CHANNEL_SELECTED, channel)
            if not success:
                return jsonify({"error": "Lead not found"}), 404
            lead = db.get_lead_by_id(lead_id)

        return jsonify({"success": True, "lead": lead, "status": CHANNEL_SELECTED, "selected_channel": channel})
    except Exception as e:
        print(f"Error selecting outreach channel: {e}")
        return jsonify({"error": str(e)}), 500


def update_lead_contacts(lead_id):
    """Manually update lead contact fields (telegram/whatsapp/email/phone/website)."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        allowed_fields = ("telegram_url", "whatsapp_url", "email", "phone", "website")
        updates: dict[str, Any] = {}
        for field in allowed_fields:
            if field in data:
                raw_value = data.get(field)
                if raw_value is None:
                    updates[field] = None
                else:
                    text_value = str(raw_value).strip()
                    updates[field] = text_value or None

        if not updates:
            return jsonify({"error": "No contact fields provided"}), 400

        conn = get_db_connection()
        try:
            cur = conn.cursor()
            assignments = []
            values: list[Any] = []
            for field, value in updates.items():
                assignments.append(f"{field} = %s")
                values.append(value)
            assignments.append("updated_at = NOW()")
            values.append(lead_id)
            cur.execute(
                f"""
                UPDATE prospectingleads
                SET {', '.join(assignments)}
                WHERE id = %s
                RETURNING *
                """,
                values,
            )
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Lead not found"}), 404
            conn.commit()
            lead = dict(row)
        finally:
            conn.close()

        return jsonify({"success": True, "lead": _normalize_lead_for_display(lead)})
    except Exception as e:
        print(f"Error updating lead contacts: {e}")
        return jsonify({"error": str(e)}), 500


def update_lead_language(lead_id):
    """Update lead preferred language and enabled languages."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        requested_language = str(data.get("preferred_language") or data.get("language") or "").strip().lower()
        primary_language, enabled_languages = _normalize_public_audit_languages(requested_language, data.get("enabled_languages"))

        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE prospectingleads
                SET preferred_language = %s,
                    enabled_languages = %s,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING *
                """,
                (primary_language, json.dumps(enabled_languages, ensure_ascii=False), lead_id),
            )
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Lead not found"}), 404
            conn.commit()
            lead = dict(row)
        finally:
            conn.close()

        return jsonify({"success": True, "lead": _normalize_lead_for_display(lead)})
    except Exception as e:
        print(f"Error updating lead language: {e}")
        return jsonify({"error": str(e)}), 500


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
