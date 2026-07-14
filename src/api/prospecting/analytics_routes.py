from __future__ import annotations

import copy
import json
import os
import csv
import io
import threading
import subprocess
import sys
import uuid
import re
import time
import random
from difflib import SequenceMatcher
from urllib.parse import unquote
from datetime import date, datetime, timedelta, timezone
from typing import Any

import requests
from flask import Blueprint, jsonify, request, send_file
from psycopg2.extras import Json, RealDictCursor

from auth_system import CONSENT_VERSION, normalize_email, verify_session
from core.channel_delivery import normalize_phone, send_maton_bridge_message
from core.card_audit import build_lead_card_preview_snapshot
from core.audit_quality import evaluate_audit_quality
from core.telegram_userbot import load_userbot_account, send_message as userbot_send_message
from core.ai_learning import ensure_ai_learning_events_table, record_ai_learning_event
from core.audit_editorial import (
    apply_audit_editorial_pass,
    build_editorial_summary,
    normalize_audit_text,
    truncate_sentence,
)
from core.public_audit_editor import (
    ACTION_PLAN_BLOCK_KEY,
    EDITOR_BLOCK_KEYS,
    SUMMARY_BLOCK_KEY,
    TOP_ISSUES_BLOCK_KEY,
    apply_editor_blocks_to_page_json,
    blocks_equal,
    build_generated_editor_blocks,
    build_learning_metadata,
    classify_edit_kind,
    compute_editor_diff,
    normalize_public_audit_page_json,
    normalize_editor_blocks,
    normalize_editor_state,
    render_block_text,
)
from core.helpers import get_business_id_from_user
from core.map_url_normalizer import is_google_map_url, normalize_map_url
from core.parsing_runtime_config import get_use_apify_map_parsing, resolve_map_source_for_queue
try:
    from src.database_manager import DatabaseManager
except ImportError:
    from database_manager import DatabaseManager
from pg_db_utils import get_db_connection
from services.gigachat_client import analyze_text_with_gigachat
from services.operator_credit_reservation import finalize_reserved_action_credits, reserve_paid_action_credits
from services.prospecting_service import ProspectingService
from services.sales_room_helpers import (
    append_sales_room_link_to_outreach_text as _append_sales_room_link_to_outreach_text,
    make_sales_room_url as _make_sales_room_url,
    normalize_sales_room_data_mode as _normalize_sales_room_data_mode,
)
from services.sales_room_review_service import (
    can_edit_sales_room as _can_edit_sales_room,
    create_sales_room_proposal_version as _create_sales_room_proposal_version,
    ensure_sales_room_proposal_version as _ensure_sales_room_proposal_version,
    load_sales_room_by_slug as _load_sales_room_by_slug,
    load_sales_room_latest_version as _load_sales_room_latest_version,
    load_sales_room_messages as _load_sales_room_messages,
    load_sales_room_review as _load_sales_room_review,
    replace_text_for_sales_room_suggestion as _replace_text_for_sales_room_suggestion,
    serialize_sales_room_message as _serialize_sales_room_message,
    serialize_sales_room_suggestion as _serialize_sales_room_suggestion,
    serialize_sales_room_version as _serialize_sales_room_version,
    update_sales_room_proposal_body as _update_sales_room_proposal_body,
)
from services.sales_room_audit_offer_service import (
    AUDIT_OFFER_DEFAULT_BUTTON,
    AUDIT_OFFER_DEFAULT_TEXT,
    AUDIT_OFFER_DEFAULT_TITLE,
    AUDIT_OFFER_PLATFORMS,
    AUDIT_OFFER_REQUESTABLE_STATUSES,
    AUDIT_OFFER_TERMINAL_STATUSES,
    AUDIT_OFFER_VISIBLE_STATUSES,
    audit_offer_processing_delay_seconds as _audit_offer_processing_delay_seconds,
    build_sales_room_participant_access_token as _build_sales_room_participant_access_token,
    ensure_audit_offer_user as _ensure_audit_offer_user,
    load_sales_room_participant_by_token as _load_sales_room_participant_by_token,
    participant_token_from_request as _participant_token_from_request,
    public_audit_offer_allowed_for_participant as _public_audit_offer_allowed_for_participant,
    record_sales_room_event_by_id as _record_sales_room_event_by_id,
    send_sales_room_audit_ready_email as _send_sales_room_audit_ready_email,
    send_sales_room_participant_verification_email as _send_sales_room_participant_verification_email,
    serialize_public_audit_offer as _serialize_public_audit_offer,
    serialize_sales_room_participant as _serialize_sales_room_participant,
)

from api.prospecting.shared import admin_prospecting_bp

class AuditQualityError(ValueError):
    def __init__(self, quality: dict[str, Any]):
        super().__init__("Audit quality gate failed")
        self.quality = quality

SHORTLIST_APPROVED = "shortlist_approved"
SHORTLIST_REJECTED = "shortlist_rejected"
SELECTED_FOR_OUTREACH = "selected_for_outreach"
CHANNEL_SELECTED = "channel_selected"
ALLOWED_OUTREACH_CHANNELS = {"telegram", "whatsapp", "max", "email", "manual"}
DRAFT_GENERATED = "generated"
DRAFT_APPROVED = "approved"
DRAFT_REJECTED = "rejected"
QUEUED_FOR_SEND = "queued_for_send"
BATCH_DRAFT = "draft"
BATCH_APPROVED = "approved"
QUEUE_STATUS_QUEUED = "queued"
QUEUE_STATUS_SENDING = "sending"
QUEUE_STATUS_SENT = "sent"
QUEUE_STATUS_DELIVERED = "delivered"
QUEUE_STATUS_RETRY = "retry"
QUEUE_STATUS_DLQ = "dlq"
QUEUE_STATUS_FAILED = "failed"
MAX_DAILY_OUTREACH_BATCH = 10
ALLOWED_REPLY_OUTCOMES = {"positive", "question", "no_response", "hard_no"}
SEARCH_JOB_TIMEOUT_SEC = int(os.environ.get("APIFY_SEARCH_TIMEOUT_SEC", "180"))
OUTREACH_SEND_MAX_ATTEMPTS = int(os.environ.get("OUTREACH_SEND_MAX_ATTEMPTS", "3"))
OUTREACH_RETRY_DELAY_DAYS = (1, 2)  # D1, D3 относительно D0
OUTREACH_SEND_DELAY_MIN_SEC = max(0.0, float(os.environ.get("OUTREACH_SEND_DELAY_MIN_SEC", "12")))
OUTREACH_SEND_DELAY_MAX_SEC = max(OUTREACH_SEND_DELAY_MIN_SEC, float(os.environ.get("OUTREACH_SEND_DELAY_MAX_SEC", "28")))
SALES_ROOM_UPLOAD_MAX_BYTES = int(os.environ.get("SALES_ROOM_UPLOAD_MAX_BYTES", str(10 * 1024 * 1024)))
SALES_ROOM_UPLOAD_DIR = os.environ.get(
    "SALES_ROOM_UPLOAD_DIR",
    os.path.join(os.environ.get("DEBUG_DIR", "debug_data"), "sales_room_uploads"),
)
SALES_ROOM_ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "xls", "xlsx", "csv", "txt", "png", "jpg", "jpeg", "webp"}
PUBLIC_SALES_ROOM_MESSAGE_LIMIT = int(os.environ.get("PUBLIC_SALES_ROOM_MESSAGE_LIMIT", "20"))
PUBLIC_SALES_ROOM_FILE_LIMIT = int(os.environ.get("PUBLIC_SALES_ROOM_FILE_LIMIT", "10"))
PUBLIC_SALES_ROOM_SUGGESTION_LIMIT = int(os.environ.get("PUBLIC_SALES_ROOM_SUGGESTION_LIMIT", "20"))
PUBLIC_SALES_ROOM_EVENT_LIMIT = int(os.environ.get("PUBLIC_SALES_ROOM_EVENT_LIMIT", "120"))
PUBLIC_SALES_ROOM_WRITE_WINDOW_SEC = int(os.environ.get("PUBLIC_SALES_ROOM_WRITE_WINDOW_SEC", "3600"))
PUBLIC_SALES_ROOM_EVENT_WINDOW_SEC = int(os.environ.get("PUBLIC_SALES_ROOM_EVENT_WINDOW_SEC", "60"))
_public_sales_room_rate_lock = threading.Lock()
_public_sales_room_rate_buckets: dict[str, list[float]] = {}
TELEGRAM_REPLY_SYNC_LOOKBACK_DAYS = max(1, int(os.environ.get("TELEGRAM_REPLY_SYNC_LOOKBACK_DAYS", "14")))
TELEGRAM_REPLY_SYNC_PER_CHAT_LIMIT = max(1, min(int(os.environ.get("TELEGRAM_REPLY_SYNC_PER_CHAT_LIMIT", "12")), 50))
TELEGRAM_REPLY_SYNC_TIMEOUT_SEC = max(5, int(os.environ.get("TELEGRAM_REPLY_SYNC_TIMEOUT_SEC", "12")))
LEAD_OUTREACH_MODERATION_STATUS = "lead_outreach"
PUBLIC_AUDIT_LANGUAGES = ("ru", "en", "fr", "es", "el", "de", "th", "ar", "ha", "tr")
PIPELINE_UNPROCESSED = "unprocessed"
PIPELINE_IN_PROGRESS = "in_progress"
PIPELINE_POSTPONED = "postponed"
PIPELINE_NOT_RELEVANT = "not_relevant"
PIPELINE_CONTACTED = "contacted"
PIPELINE_WAITING_REPLY = "waiting_reply"
PIPELINE_SECOND_MESSAGE_SENT = "second_message_sent"
PIPELINE_REPLIED = "replied"
PIPELINE_CONVERTED = "converted"
PIPELINE_CLOSED_LOST = "closed_lost"
PARTNER_KIND_BUSINESS = "business"
PARTNER_KIND_RESIDENTIAL_COMPLEX = "residential_complex"
PARTNER_KIND_OTHER = "other"
PARTNER_MATCH_NOT_STARTED = "not_started"
PARTNER_MATCH_FOUND = "found"
PARTNER_MATCH_AMBIGUOUS = "ambiguous"
PARTNER_MATCH_NOT_FOUND = "not_found"
PARTNER_MATCH_MANUAL_CONFIRMED = "manual_confirmed"
PARTNER_MATCH_SKIPPED_RESIDENTIAL = "skipped_residential_complex"
PARTNER_AUDIT_NOT_STARTED = "not_started"
PARTNER_AUDIT_GENERATED = "generated"
PARTNER_AUDIT_FAILED = "failed"
PARTNER_LEAD_NOT_SYNCED = "not_synced"
PARTNER_LEAD_SYNCED = "synced"
PARTNER_LEAD_SKIPPED = "skipped_residential_complex"
PARTNER_LEAD_FAILED = "failed"
SALES_ROOM_MODE_PARTNER = "partner_search"
SALES_ROOM_MODE_CLIENT = "client_search"
SALES_ROOM_DATA_AUDITED = "audited"
SALES_ROOM_DATA_TEMPLATE = "template"
SALES_ROOM_AUDITED_CREDITS = 1
ACTIVE_PARTNERSHIP_LEAD_SQL = """
  AND COALESCE(l.pipeline_status, '') NOT IN ('not_relevant', 'disqualified', 'closed_lost')
  AND COALESCE(l.status, '') NOT IN ('not_relevant', 'disqualified', 'rejected', 'shortlist_rejected')
  AND COALESCE(l.partnership_stage, '') NOT IN ('rejected', 'shortlist_rejected')
"""
ALLOWED_PIPELINE_STATUSES = {
    PIPELINE_UNPROCESSED,
    PIPELINE_IN_PROGRESS,
    PIPELINE_POSTPONED,
    PIPELINE_NOT_RELEVANT,
    PIPELINE_CONTACTED,
    PIPELINE_WAITING_REPLY,
    PIPELINE_SECOND_MESSAGE_SENT,
    PIPELINE_REPLIED,
    PIPELINE_CONVERTED,
    PIPELINE_CLOSED_LOST,
}
NOT_RELEVANT_REASONS = {
    "not_icp",
    "duplicate",
    "closed_business",
    "no_contacts",
    "weak_potential",
    "wrong_geo",
    "other",
}
GROUP_STATUS_DRAFT = "draft"
GROUP_STATUS_ACTIVE = "active"
GROUP_STATUS_ARCHIVED = "archived"
ALLOWED_GROUP_STATUSES = {GROUP_STATUS_DRAFT, GROUP_STATUS_ACTIVE, GROUP_STATUS_ARCHIVED}

PARTNER_MAP_MATCH_MIN_CONFIDENCE = 0.83
PARTNER_MAP_MATCH_MIN_MARGIN = 0.08
PARTNERSHIP_SYNTHETIC_MARKERS = (
    "детский этаж",
    "медицинские арендаторы",
    "кинотеатр / развлечения",
    "развлекательный автомат",
    "группа арендаторов",
)

_RU_LAT_MAP = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}

_SLUG_PART_ALIASES = {
    "санкт-петербург": "saint-petersburg",
    "санкт петербург": "saint-petersburg",
    "saint petersburg": "saint-petersburg",
    "st petersburg": "saint-petersburg",
    "подковырова": "podkovirova",
}

_STREET_PREFIX_PATTERN = re.compile(
    r"^(ulitsa|ulitsa\.|ul\.|street|st\.|st|prospekt|pr\.|pr|pereulok|per\.|per|naberezhnaya|nab\.|nab|bulvar|boulevard|bulevard|shosse|sh\.)\s+",
    re.IGNORECASE,
)

@admin_prospecting_bp.route("/api/partnership/leads/bulk-parse", methods=["POST"])
def partnership_bulk_parse_leads():
    """Bulk parse enqueue for selected partnership leads."""
    user_data, error = _require_auth()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        requested_business_id = str(data.get("business_id") or "").strip() or None
        lead_ids = data.get("lead_ids") or []
        if not isinstance(lead_ids, list) or len(lead_ids) == 0:
            return jsonify({"error": "lead_ids must be a non-empty list"}), 400
        normalized_ids = [str(lead_id or "").strip() for lead_id in lead_ids]
        normalized_ids = [lead_id for lead_id in normalized_ids if lead_id]
        if not normalized_ids:
            return jsonify({"error": "lead_ids must contain valid ids"}), 400

        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
        finally:
            conn.close()

        queued_count = 0
        existing_count = 0
        skipped_count = 0
        tasks: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        for lead_id in normalized_ids:
            try:
                conn = get_db_connection()
                try:
                    cur = conn.cursor()
                    lead = _load_partnership_lead(cur, lead_id=lead_id, business_id=business_id)
                finally:
                    conn.close()
                if not lead:
                    skipped_count += 1
                    errors.append({"lead_id": lead_id, "error": "Lead not found"})
                    continue

                display_lead = _normalize_lead_for_display(dict(lead))
                if not display_lead:
                    skipped_count += 1
                    errors.append({"lead_id": lead_id, "error": "Lead is not available for parsing"})
                    continue
                if _is_internal_partnership_source_url(display_lead.get("source_url")):
                    skipped_count += 1
                    errors.append({"lead_id": lead_id, "error": "Google Docs import source is not a map card"})
                    continue

                business, _business_created = _ensure_parse_business_for_partnership_lead(display_lead, str(user_data["user_id"]))
                parse_business_id = str(business.get("id") or "").strip()
                if not parse_business_id:
                    skipped_count += 1
                    errors.append({"lead_id": lead_id, "error": "Failed to resolve business for lead"})
                    continue

                conn = get_db_connection()
                try:
                    cur = conn.cursor()
                    cur.execute(
                        """
                        UPDATE prospectingleads
                        SET parse_business_id = %s,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (parse_business_id, lead_id),
                    )
                    conn.commit()
                finally:
                    conn.close()
                source_url = str(business.get("yandex_url") or display_lead.get("source_url") or "").strip()
                if not source_url:
                    skipped_count += 1
                    errors.append({"lead_id": lead_id, "error": "Missing map url"})
                    continue

                task = _enqueue_parse_task_for_business(parse_business_id, user_data["user_id"], source_url)
                if bool(task.get("existing")):
                    existing_count += 1
                else:
                    queued_count += 1
                tasks.append(
                    {
                        "lead_id": lead_id,
                        "task_id": task.get("id"),
                        "status": task.get("status"),
                        "source": task.get("source"),
                        "existing": bool(task.get("existing")),
                    }
                )
            except Exception as lead_exc:
                skipped_count += 1
                errors.append({"lead_id": lead_id, "error": str(lead_exc)})

        return jsonify(
            {
                "success": True,
                "queued_count": queued_count,
                "existing_count": existing_count,
                "skipped_count": skipped_count,
                "tasks": tasks,
                "errors": errors,
            }
        )
    except Exception as e:
        print(f"Error partnership bulk parse leads: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/partnership/ralph-loop-summary", methods=["GET"])
def partnership_ralph_loop_summary():
    """Weekly operator summary for pilot cohort: throughput, outcomes and learning signals."""
    user_data, error = _require_auth()
    if error:
        return error

    try:
        requested_business_id = str(request.args.get("business_id") or "").strip() or None
        window_days = max(1, min(int(request.args.get("window_days") or 7), 90))
        pilot_cohort = str(request.args.get("pilot_cohort") or "").strip().lower() or None

        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
            schema_flags = _get_partnership_schema_flags(cur)

            lead_filter_sql = [
                "l.business_id = %s",
                "COALESCE(l.intent, 'client_outreach') = 'partnership_outreach'",
            ]
            lead_filter_params: list[Any] = [business_id]
            if pilot_cohort and pilot_cohort != "all":
                lead_filter_sql.append("COALESCE(l.pilot_cohort, 'backlog') = %s")
                lead_filter_params.append(pilot_cohort)
            lead_filter = " AND ".join(lead_filter_sql)
            parse_status_sql = "''::text"
            if schema_flags["has_parse_lookup"]:
                parse_status_sql = _partnership_parse_status_select_sql("l")
            parsed_completed_sql = "(SELECT COUNT(*) FROM leads_scope WHERE COALESCE(parse_status, '') = 'completed')"
            if not schema_flags["has_parse_lookup"]:
                parsed_completed_sql = "0"

            if schema_flags["has_reaction_outcomes"]:
                cur.execute(
                    f"""
                    WITH leads_scope AS (
                        SELECT
                            l.id,
                            l.partnership_stage,
                            l.selected_channel,
                            l.created_at,
                            l.updated_at,
                            {parse_status_sql} AS parse_status
                        FROM prospectingleads l
                        WHERE {lead_filter}
                    ),
                    sent_scope AS (
                        SELECT q.id, q.channel, q.delivery_status, q.created_at, q.lead_id
                        FROM outreachsendqueue q
                        JOIN leads_scope ls ON ls.id = q.lead_id
                        WHERE q.created_at >= NOW() - (%s || ' days')::INTERVAL
                    ),
                    reaction_scope AS (
                        SELECT r.id,
                               COALESCE(r.human_confirmed_outcome, r.classified_outcome, '') AS final_outcome,
                               q.channel
                        FROM outreachmessagereactions r
                        JOIN outreachsendqueue q ON q.id = r.queue_id
                        JOIN leads_scope ls ON ls.id = q.lead_id
                        WHERE r.created_at >= NOW() - (%s || ' days')::INTERVAL
                    ),
                    draft_scope AS (
                        SELECT d.id, d.status
                        FROM outreachmessagedrafts d
                        JOIN leads_scope ls ON ls.id = d.lead_id
                        WHERE COALESCE(d.updated_at, d.created_at) >= NOW() - (%s || ' days')::INTERVAL
                    )
                    SELECT
                        (SELECT COUNT(*) FROM leads_scope) AS leads_total,
                        {parsed_completed_sql} AS parsed_completed_count,
                        (SELECT COUNT(*) FROM leads_scope WHERE COALESCE(partnership_stage, 'imported') IN ('audited','matched','proposal_draft_ready','selected_for_outreach','channel_selected','approved_for_send','sent')) AS audited_count,
                        (SELECT COUNT(*) FROM leads_scope WHERE COALESCE(partnership_stage, 'imported') IN ('matched','proposal_draft_ready','selected_for_outreach','channel_selected','approved_for_send','sent')) AS matched_count,
                        (SELECT COUNT(*) FROM draft_scope) AS drafts_total,
                        (SELECT COUNT(*) FROM draft_scope WHERE COALESCE(status, '') = 'approved') AS drafts_approved_count,
                        (SELECT COUNT(*) FROM sent_scope) AS sent_total,
                        (SELECT COUNT(*) FROM reaction_scope WHERE final_outcome = 'positive') AS positive_count,
                        (SELECT COUNT(*) FROM reaction_scope WHERE final_outcome = 'question') AS question_count,
                        (SELECT COUNT(*) FROM reaction_scope WHERE final_outcome = 'no_response') AS no_response_count,
                        (SELECT COUNT(*) FROM reaction_scope WHERE final_outcome = 'hard_no') AS hard_no_count
                    """,
                    (*lead_filter_params, window_days, window_days, window_days),
                )
            else:
                cur.execute(
                    f"""
                    WITH leads_scope AS (
                        SELECT
                            l.id,
                            l.partnership_stage,
                            l.selected_channel,
                            l.created_at,
                            l.updated_at,
                            {parse_status_sql} AS parse_status
                        FROM prospectingleads l
                        WHERE {lead_filter}
                    ),
                    sent_scope AS (
                        SELECT q.id, q.channel, q.delivery_status, q.created_at, q.lead_id
                        FROM outreachsendqueue q
                        JOIN leads_scope ls ON ls.id = q.lead_id
                        WHERE q.created_at >= NOW() - (%s || ' days')::INTERVAL
                    ),
                    draft_scope AS (
                        SELECT d.id, d.status
                        FROM outreachmessagedrafts d
                        JOIN leads_scope ls ON ls.id = d.lead_id
                        WHERE COALESCE(d.updated_at, d.created_at) >= NOW() - (%s || ' days')::INTERVAL
                    )
                    SELECT
                        (SELECT COUNT(*) FROM leads_scope) AS leads_total,
                        {parsed_completed_sql} AS parsed_completed_count,
                        (SELECT COUNT(*) FROM leads_scope WHERE COALESCE(partnership_stage, 'imported') IN ('audited','matched','proposal_draft_ready','selected_for_outreach','channel_selected','approved_for_send','sent')) AS audited_count,
                        (SELECT COUNT(*) FROM leads_scope WHERE COALESCE(partnership_stage, 'imported') IN ('matched','proposal_draft_ready','selected_for_outreach','channel_selected','approved_for_send','sent')) AS matched_count,
                        (SELECT COUNT(*) FROM draft_scope) AS drafts_total,
                        (SELECT COUNT(*) FROM draft_scope WHERE COALESCE(status, '') = 'approved') AS drafts_approved_count,
                        (SELECT COUNT(*) FROM sent_scope) AS sent_total,
                        0 AS positive_count,
                        0 AS question_count,
                        0 AS no_response_count,
                        0 AS hard_no_count
                    """,
                    (*lead_filter_params, window_days, window_days),
                )
            row = cur.fetchone()

            if schema_flags["has_reaction_outcomes"]:
                cur.execute(
                    f"""
                    WITH leads_scope AS (
                        SELECT
                            l.id,
                            l.partnership_stage,
                            {parse_status_sql} AS parse_status
                        FROM prospectingleads l
                        WHERE {lead_filter}
                    ),
                    sent_scope AS (
                        SELECT q.id, q.channel, q.delivery_status, q.created_at, q.lead_id
                        FROM outreachsendqueue q
                        JOIN leads_scope ls ON ls.id = q.lead_id
                        WHERE q.created_at >= NOW() - (%s || ' days')::INTERVAL
                          AND q.created_at < NOW() - (%s || ' days')::INTERVAL
                    ),
                    reaction_scope AS (
                        SELECT r.id,
                               COALESCE(r.human_confirmed_outcome, r.classified_outcome, '') AS final_outcome
                        FROM outreachmessagereactions r
                        JOIN outreachsendqueue q ON q.id = r.queue_id
                        JOIN leads_scope ls ON ls.id = q.lead_id
                        WHERE r.created_at >= NOW() - (%s || ' days')::INTERVAL
                          AND r.created_at < NOW() - (%s || ' days')::INTERVAL
                    ),
                    draft_scope AS (
                        SELECT d.id, d.status
                        FROM outreachmessagedrafts d
                        JOIN leads_scope ls ON ls.id = d.lead_id
                        WHERE COALESCE(d.updated_at, d.created_at) >= NOW() - (%s || ' days')::INTERVAL
                          AND COALESCE(d.updated_at, d.created_at) < NOW() - (%s || ' days')::INTERVAL
                    )
                    SELECT
                        (SELECT COUNT(*) FROM leads_scope) AS leads_total,
                        {parsed_completed_sql} AS parsed_completed_count,
                        (SELECT COUNT(*) FROM leads_scope WHERE COALESCE(partnership_stage, 'imported') IN ('audited','matched','proposal_draft_ready','selected_for_outreach','channel_selected','approved_for_send','sent')) AS audited_count,
                        (SELECT COUNT(*) FROM leads_scope WHERE COALESCE(partnership_stage, 'imported') IN ('matched','proposal_draft_ready','selected_for_outreach','channel_selected','approved_for_send','sent')) AS matched_count,
                        (SELECT COUNT(*) FROM draft_scope) AS drafts_total,
                        (SELECT COUNT(*) FROM draft_scope WHERE COALESCE(status, '') = 'approved') AS drafts_approved_count,
                        (SELECT COUNT(*) FROM sent_scope) AS sent_total,
                        (SELECT COUNT(*) FROM reaction_scope WHERE final_outcome = 'positive') AS positive_count,
                        (SELECT COUNT(*) FROM reaction_scope WHERE final_outcome = 'question') AS question_count,
                        (SELECT COUNT(*) FROM reaction_scope WHERE final_outcome = 'no_response') AS no_response_count,
                        (SELECT COUNT(*) FROM reaction_scope WHERE final_outcome = 'hard_no') AS hard_no_count
                    """,
                    (
                        *lead_filter_params,
                        window_days * 2,
                        window_days,
                        window_days * 2,
                        window_days,
                        window_days * 2,
                        window_days,
                    ),
                )
            else:
                cur.execute(
                    f"""
                    WITH leads_scope AS (
                        SELECT
                            l.id,
                            l.partnership_stage,
                            {parse_status_sql} AS parse_status
                        FROM prospectingleads l
                        WHERE {lead_filter}
                    ),
                    sent_scope AS (
                        SELECT q.id, q.channel, q.delivery_status, q.created_at, q.lead_id
                        FROM outreachsendqueue q
                        JOIN leads_scope ls ON ls.id = q.lead_id
                        WHERE q.created_at >= NOW() - (%s || ' days')::INTERVAL
                          AND q.created_at < NOW() - (%s || ' days')::INTERVAL
                    ),
                    draft_scope AS (
                        SELECT d.id, d.status
                        FROM outreachmessagedrafts d
                        JOIN leads_scope ls ON ls.id = d.lead_id
                        WHERE COALESCE(d.updated_at, d.created_at) >= NOW() - (%s || ' days')::INTERVAL
                          AND COALESCE(d.updated_at, d.created_at) < NOW() - (%s || ' days')::INTERVAL
                    )
                    SELECT
                        (SELECT COUNT(*) FROM leads_scope) AS leads_total,
                        {parsed_completed_sql} AS parsed_completed_count,
                        (SELECT COUNT(*) FROM leads_scope WHERE COALESCE(partnership_stage, 'imported') IN ('audited','matched','proposal_draft_ready','selected_for_outreach','channel_selected','approved_for_send','sent')) AS audited_count,
                        (SELECT COUNT(*) FROM leads_scope WHERE COALESCE(partnership_stage, 'imported') IN ('matched','proposal_draft_ready','selected_for_outreach','channel_selected','approved_for_send','sent')) AS matched_count,
                        (SELECT COUNT(*) FROM draft_scope) AS drafts_total,
                        (SELECT COUNT(*) FROM draft_scope WHERE COALESCE(status, '') = 'approved') AS drafts_approved_count,
                        (SELECT COUNT(*) FROM sent_scope) AS sent_total,
                        0 AS positive_count,
                        0 AS question_count,
                        0 AS no_response_count,
                        0 AS hard_no_count
                    """,
                    (
                        *lead_filter_params,
                        window_days * 2,
                        window_days,
                        window_days * 2,
                        window_days,
                    ),
                )
            baseline_row = cur.fetchone()

            by_channel_rows = []
            if schema_flags["has_reaction_outcomes"]:
                cur.execute(
                    f"""
                    WITH leads_scope AS (
                        SELECT l.id
                        FROM prospectingleads l
                        WHERE {lead_filter}
                    )
                    SELECT
                        q.channel,
                        COUNT(*) AS total,
                        COUNT(*) FILTER (WHERE COALESCE(r.human_confirmed_outcome, r.classified_outcome, '') = 'positive') AS positive_count,
                        COUNT(*) FILTER (WHERE COALESCE(r.human_confirmed_outcome, r.classified_outcome, '') = 'question') AS question_count,
                        COUNT(*) FILTER (WHERE COALESCE(r.human_confirmed_outcome, r.classified_outcome, '') = 'no_response') AS no_response_count,
                        COUNT(*) FILTER (WHERE COALESCE(r.human_confirmed_outcome, r.classified_outcome, '') = 'hard_no') AS hard_no_count
                    FROM outreachsendqueue q
                    LEFT JOIN outreachmessagereactions r ON r.queue_id = q.id
                    JOIN leads_scope ls ON ls.id = q.lead_id
                    WHERE q.created_at >= NOW() - (%s || ' days')::INTERVAL
                    GROUP BY q.channel
                    ORDER BY total DESC, q.channel
                    """,
                    (*lead_filter_params, window_days),
                )
                by_channel_rows = cur.fetchall() or []

            ensure_ai_learning_events_table(conn)
            cur.execute(
                """
                WITH latest_prompts AS (
                    SELECT DISTINCT ON (capability)
                        capability, prompt_key, prompt_version
                    FROM ailearningevents
                    WHERE intent = 'partnership_outreach'
                    ORDER BY capability, created_at DESC
                )
                SELECT
                    e.capability,
                    COUNT(*) FILTER (WHERE event_type = 'accepted') AS accepted_total,
                    COUNT(*) FILTER (WHERE event_type = 'accepted' AND COALESCE(edited_before_accept, FALSE) = TRUE) AS accepted_edited_total,
                    COALESCE(lp.prompt_key, '') AS prompt_key,
                    COALESCE(lp.prompt_version, '') AS prompt_version
                FROM ailearningevents e
                LEFT JOIN latest_prompts lp ON lp.capability = e.capability
                WHERE e.intent = 'partnership_outreach'
                  AND e.created_at >= NOW() - (%s || ' days')::INTERVAL
                GROUP BY e.capability, lp.prompt_key, lp.prompt_version
                ORDER BY accepted_total DESC, e.capability
                """,
                (window_days,),
            )
            learning_rows = cur.fetchall() or []

            cur.execute(
                """
                SELECT
                    COUNT(*)::INT AS edited_accepts_total,
                    COALESCE(AVG(CHAR_LENGTH(COALESCE(draft_text, ''))), 0)::FLOAT AS avg_generated_len,
                    COALESCE(AVG(CHAR_LENGTH(COALESCE(final_text, ''))), 0)::FLOAT AS avg_final_len,
                    COUNT(*) FILTER (
                        WHERE CHAR_LENGTH(COALESCE(final_text, '')) > CHAR_LENGTH(COALESCE(draft_text, ''))
                    )::INT AS expanded_count,
                    COUNT(*) FILTER (
                        WHERE CHAR_LENGTH(COALESCE(final_text, '')) < CHAR_LENGTH(COALESCE(draft_text, ''))
                    )::INT AS shortened_count,
                    COUNT(*) FILTER (
                        WHERE CHAR_LENGTH(COALESCE(final_text, '')) = CHAR_LENGTH(COALESCE(draft_text, ''))
                    )::INT AS unchanged_count
                FROM ailearningevents
                WHERE intent = 'partnership_outreach'
                  AND capability = 'partnership.draft_offer'
                  AND event_type = 'accepted'
                  AND COALESCE(edited_before_accept, FALSE) = TRUE
                  AND business_id = NULLIF(%s, '')::uuid
                  AND created_at >= NOW() - (%s || ' days')::INTERVAL
                """,
                (business_id, window_days),
            )
            edit_row = cur.fetchone()

            if schema_flags["has_reaction_outcomes"]:
                cur.execute(
                    f"""
                    WITH leads_scope AS (
                        SELECT l.id
                        FROM prospectingleads l
                        WHERE {lead_filter}
                    ),
                    latest_reaction AS (
                        SELECT DISTINCT ON (r.queue_id)
                            r.queue_id,
                            COALESCE(r.human_confirmed_outcome, r.classified_outcome, '') AS final_outcome
                        FROM outreachmessagereactions r
                        ORDER BY r.queue_id, COALESCE(r.created_at, NOW()) DESC
                    )
                    SELECT
                        COALESCE(d.learning_note_json->>'prompt_key', '') AS prompt_key,
                        COALESCE(d.learning_note_json->>'prompt_version', '') AS prompt_version,
                        COUNT(*)::INT AS drafts_total,
                        COUNT(*) FILTER (WHERE COALESCE(d.status, '') = 'approved')::INT AS approved_total,
                        COUNT(*) FILTER (
                            WHERE COALESCE(d.status, '') = 'approved'
                              AND COALESCE(d.approved_text, '') <> COALESCE(d.generated_text, '')
                        )::INT AS edited_approved_total,
                        COUNT(DISTINCT q.id)::INT AS sent_total,
                        COUNT(DISTINCT q.id) FILTER (WHERE lr.final_outcome = 'positive')::INT AS positive_count
                    FROM outreachmessagedrafts d
                    JOIN leads_scope ls ON ls.id = d.lead_id
                    LEFT JOIN outreachsendqueue q ON q.draft_id = d.id
                        AND q.created_at >= NOW() - (%s || ' days')::INTERVAL
                    LEFT JOIN latest_reaction lr ON lr.queue_id = q.id
                    WHERE COALESCE(d.updated_at, d.created_at) >= NOW() - (%s || ' days')::INTERVAL
                    GROUP BY COALESCE(d.learning_note_json->>'prompt_key', ''), COALESCE(d.learning_note_json->>'prompt_version', '')
                    ORDER BY approved_total DESC, sent_total DESC, prompt_key, prompt_version
                    """,
                    (*lead_filter_params, window_days, window_days),
                )
            else:
                cur.execute(
                    f"""
                    WITH leads_scope AS (
                        SELECT l.id
                        FROM prospectingleads l
                        WHERE {lead_filter}
                    )
                    SELECT
                        COALESCE(d.learning_note_json->>'prompt_key', '') AS prompt_key,
                        COALESCE(d.learning_note_json->>'prompt_version', '') AS prompt_version,
                        COUNT(*)::INT AS drafts_total,
                        COUNT(*) FILTER (WHERE COALESCE(d.status, '') = 'approved')::INT AS approved_total,
                        COUNT(*) FILTER (
                            WHERE COALESCE(d.status, '') = 'approved'
                              AND COALESCE(d.approved_text, '') <> COALESCE(d.generated_text, '')
                        )::INT AS edited_approved_total,
                        COUNT(DISTINCT q.id)::INT AS sent_total,
                        0::INT AS positive_count
                    FROM outreachmessagedrafts d
                    JOIN leads_scope ls ON ls.id = d.lead_id
                    LEFT JOIN outreachsendqueue q ON q.draft_id = d.id
                        AND q.created_at >= NOW() - (%s || ' days')::INTERVAL
                    WHERE COALESCE(d.updated_at, d.created_at) >= NOW() - (%s || ' days')::INTERVAL
                    GROUP BY COALESCE(d.learning_note_json->>'prompt_key', ''), COALESCE(d.learning_note_json->>'prompt_version', '')
                    ORDER BY approved_total DESC, sent_total DESC, prompt_key, prompt_version
                    """,
                    (*lead_filter_params, window_days, window_days),
                )
            prompt_rows = cur.fetchall() or []
        finally:
            conn.close()

        row_dict = dict(row) if hasattr(row, "keys") else {}
        baseline_dict = dict(baseline_row) if hasattr(baseline_row, "keys") else {}
        edit_dict = dict(edit_row) if hasattr(edit_row, "keys") else {}
        sent_total = int(row_dict.get("sent_total") or 0)
        positive_count = int(row_dict.get("positive_count") or 0)
        question_count = int(row_dict.get("question_count") or 0)
        no_response_count = int(row_dict.get("no_response_count") or 0)
        hard_no_count = int(row_dict.get("hard_no_count") or 0)
        positive_rate_pct = round((positive_count / sent_total * 100.0), 2) if sent_total else 0.0
        baseline_sent_total = int(baseline_dict.get("sent_total") or 0)
        baseline_positive_count = int(baseline_dict.get("positive_count") or 0)
        baseline_positive_rate_pct = round((baseline_positive_count / baseline_sent_total * 100.0), 2) if baseline_sent_total else 0.0
        edited_accepts_total = int(edit_dict.get("edited_accepts_total") or 0)
        avg_generated_len = round(float(edit_dict.get("avg_generated_len") or 0.0), 1)
        avg_final_len = round(float(edit_dict.get("avg_final_len") or 0.0), 1)
        expanded_count = int(edit_dict.get("expanded_count") or 0)
        shortened_count = int(edit_dict.get("shortened_count") or 0)
        unchanged_count = int(edit_dict.get("unchanged_count") or 0)

        top_channels = []
        for ch in by_channel_rows:
            chd = dict(ch) if hasattr(ch, "keys") else {}
            total = int(chd.get("total") or 0)
            pos = int(chd.get("positive_count") or 0)
            top_channels.append(
                {
                    "channel": chd.get("channel") or "unknown",
                    "total": total,
                    "positive_count": pos,
                    "positive_rate_pct": round((pos / total * 100.0), 2) if total else 0.0,
                }
            )

        source_performance: list[dict[str, Any]] = []
        try:
            conn = get_db_connection()
            try:
                _ensure_partnership_columns(conn)
                cur = conn.cursor()
                source_filter_sql = [
                    "l.business_id = %s",
                    "COALESCE(l.intent, 'client_outreach') = 'partnership_outreach'",
                    "COALESCE(l.created_at, NOW()) >= NOW() - (%s || ' days')::INTERVAL",
                ]
                source_filter_params: list[Any] = [business_id, window_days]
                if pilot_cohort and pilot_cohort != "all":
                    source_filter_sql.append("COALESCE(l.pilot_cohort, 'backlog') = %s")
                    source_filter_params.append(pilot_cohort)
                source_filter = " AND ".join(source_filter_sql)
                if schema_flags["has_reaction_outcomes"]:
                    cur.execute(
                        f"""
                        WITH lead_scope AS (
                            SELECT
                                l.id,
                                COALESCE(NULLIF(l.source_kind, ''), 'unknown') AS source_kind,
                                COALESCE(NULLIF(l.source_provider, ''), 'unknown') AS source_provider
                            FROM prospectingleads l
                            WHERE {source_filter}
                        ),
                        sent_scope AS (
                            SELECT DISTINCT q.id, q.lead_id
                            FROM outreachsendqueue q
                            WHERE q.created_at >= NOW() - (%s || ' days')::INTERVAL
                        ),
                        latest_reaction AS (
                            SELECT DISTINCT ON (r.queue_id)
                                r.queue_id,
                                COALESCE(r.human_confirmed_outcome, r.classified_outcome, '') AS final_outcome
                            FROM outreachmessagereactions r
                            ORDER BY r.queue_id, COALESCE(r.created_at, NOW()) DESC
                        )
                        SELECT
                            ls.source_kind,
                            ls.source_provider,
                            COUNT(DISTINCT ls.id)::INT AS leads_total,
                            COUNT(DISTINCT ls.id) FILTER (WHERE COALESCE(pl.partnership_stage, '') IN ('audited', 'matched', 'proposal_draft_ready', 'selected_for_outreach', 'channel_selected', 'approved_for_send', 'sent'))::INT AS audited_count,
                            COUNT(DISTINCT ls.id) FILTER (WHERE COALESCE(pl.partnership_stage, '') IN ('matched', 'proposal_draft_ready', 'selected_for_outreach', 'channel_selected', 'approved_for_send', 'sent'))::INT AS matched_count,
                            COUNT(DISTINCT d.id)::INT AS draft_count,
                            COUNT(DISTINCT q.id)::INT AS sent_count,
                            COUNT(DISTINCT q.id) FILTER (WHERE lr.final_outcome = 'positive')::INT AS positive_count
                        FROM lead_scope ls
                        JOIN prospectingleads pl ON pl.id = ls.id
                        LEFT JOIN outreachmessagedrafts d ON d.lead_id = ls.id
                        LEFT JOIN sent_scope q ON q.lead_id = ls.id
                        LEFT JOIN latest_reaction lr ON lr.queue_id = q.id
                        GROUP BY ls.source_kind, ls.source_provider
                        ORDER BY positive_count DESC, sent_count DESC, leads_total DESC, ls.source_kind, ls.source_provider
                        """,
                        (*source_filter_params, window_days),
                    )
                else:
                    cur.execute(
                        f"""
                        WITH lead_scope AS (
                            SELECT
                                l.id,
                                COALESCE(NULLIF(l.source_kind, ''), 'unknown') AS source_kind,
                                COALESCE(NULLIF(l.source_provider, ''), 'unknown') AS source_provider
                            FROM prospectingleads l
                            WHERE {source_filter}
                        ),
                        sent_scope AS (
                            SELECT DISTINCT q.id, q.lead_id
                            FROM outreachsendqueue q
                            WHERE q.created_at >= NOW() - (%s || ' days')::INTERVAL
                        )
                        SELECT
                            ls.source_kind,
                            ls.source_provider,
                            COUNT(DISTINCT ls.id)::INT AS leads_total,
                            COUNT(DISTINCT ls.id) FILTER (WHERE COALESCE(pl.partnership_stage, '') IN ('audited', 'matched', 'proposal_draft_ready', 'selected_for_outreach', 'channel_selected', 'approved_for_send', 'sent'))::INT AS audited_count,
                            COUNT(DISTINCT ls.id) FILTER (WHERE COALESCE(pl.partnership_stage, '') IN ('matched', 'proposal_draft_ready', 'selected_for_outreach', 'channel_selected', 'approved_for_send', 'sent'))::INT AS matched_count,
                            COUNT(DISTINCT d.id)::INT AS draft_count,
                            COUNT(DISTINCT q.id)::INT AS sent_count,
                            0::INT AS positive_count
                        FROM lead_scope ls
                        JOIN prospectingleads pl ON pl.id = ls.id
                        LEFT JOIN outreachmessagedrafts d ON d.lead_id = ls.id
                        LEFT JOIN sent_scope q ON q.lead_id = ls.id
                        GROUP BY ls.source_kind, ls.source_provider
                        ORDER BY sent_count DESC, leads_total DESC, ls.source_kind, ls.source_provider
                        """,
                        (*source_filter_params, window_days),
                    )
                source_rows = cur.fetchall() or []
            finally:
                conn.close()
        except Exception as source_error:
            print(f"Error partnership Ralph loop source performance: {source_error}")
            source_rows = []

        for sr in source_rows:
            srd = dict(sr) if hasattr(sr, "keys") else {}
            leads_total = int(srd.get("leads_total") or 0)
            audited_count = int(srd.get("audited_count") or 0)
            matched_count = int(srd.get("matched_count") or 0)
            draft_count = int(srd.get("draft_count") or 0)
            sent_for_source = int(srd.get("sent_count") or 0)
            positive_for_source = int(srd.get("positive_count") or 0)
            source_performance.append(
                {
                    "source_kind": srd.get("source_kind") or "unknown",
                    "source_provider": srd.get("source_provider") or "unknown",
                    "leads_total": leads_total,
                    "audited_count": audited_count,
                    "matched_count": matched_count,
                    "draft_count": draft_count,
                    "sent_count": sent_for_source,
                    "positive_count": positive_for_source,
                    "audit_rate_pct": round((audited_count / leads_total * 100.0), 2) if leads_total else 0.0,
                    "match_rate_pct": round((matched_count / leads_total * 100.0), 2) if leads_total else 0.0,
                    "draft_rate_pct": round((draft_count / leads_total * 100.0), 2) if leads_total else 0.0,
                    "sent_rate_pct": round((sent_for_source / leads_total * 100.0), 2) if leads_total else 0.0,
                    "positive_rate_pct": round((positive_for_source / sent_for_source * 100.0), 2) if sent_for_source else 0.0,
                    "lead_to_positive_pct": round((positive_for_source / leads_total * 100.0), 2) if leads_total else 0.0,
                }
            )

        learning = []
        for lr in learning_rows:
            lrd = dict(lr) if hasattr(lr, "keys") else {}
            accepted_total = int(lrd.get("accepted_total") or 0)
            accepted_edited_total = int(lrd.get("accepted_edited_total") or 0)
            learning.append(
                {
                    "capability": lrd.get("capability") or "",
                    "accepted_total": accepted_total,
                    "accepted_edited_total": accepted_edited_total,
                    "edited_before_accept_pct": round((accepted_edited_total / accepted_total * 100.0), 2) if accepted_total else 0.0,
                    "prompt_key": lrd.get("prompt_key") or "",
                    "prompt_version": lrd.get("prompt_version") or "",
                }
            )

        blockers = []
        if int(row_dict.get("leads_total") or 0) and int(row_dict.get("parsed_completed_count") or 0) < int(row_dict.get("leads_total") or 0):
            blockers.append("Не все лиды допарсены")
        if int(row_dict.get("drafts_total") or 0) > int(row_dict.get("drafts_approved_count") or 0):
            blockers.append("Есть черновики без утверждения")
        if sent_total and (positive_count + question_count + no_response_count + hard_no_count) < sent_total:
            blockers.append("Есть отправки без зафиксированного outcome")

        recommendations = []
        if positive_rate_pct < baseline_positive_rate_pct:
            recommendations.append("Позитивная конверсия ниже предыдущей недели: проверьте оффер и первый абзац письма.")
        if int(row_dict.get("drafts_total") or 0) > int(row_dict.get("drafts_approved_count") or 0):
            recommendations.append("Сократите очередь утверждения: разберите черновики, чтобы не терять темп отправок.")
        if sent_total == 0 and int(row_dict.get("drafts_approved_count") or 0) > 0:
            recommendations.append("Есть утверждённые сообщения без отправки: соберите и утвердите batch.")
        if top_channels:
            best_channel = max(top_channels, key=lambda item: float(item.get("positive_rate_pct") or 0.0))
            if float(best_channel.get("positive_rate_pct") or 0.0) > 0:
                recommendations.append(
                    f"Лучший канал недели: {best_channel.get('channel') or 'unknown'} ({best_channel.get('positive_rate_pct') or 0}% positive)."
                )
        if learning:
            most_edited = max(learning, key=lambda item: float(item.get("edited_before_accept_pct") or 0.0))
            if float(most_edited.get("edited_before_accept_pct") or 0.0) >= 40.0:
                recommendations.append(
                    f"Промпт {most_edited.get('capability') or 'unknown'} часто правят вручную — стоит обновить формулировки в админке."
                )
        if edited_accepts_total > 0:
            if shortened_count > expanded_count:
                recommendations.append(
                    "Операторы чаще сокращают первое письмо перед отправкой — стоит сделать дефолтный оффер короче и плотнее."
                )
            elif expanded_count > shortened_count:
                recommendations.append(
                    "Операторы чаще дописывают первое письмо перед отправкой — базовому офферу не хватает конкретики."
                )
        if source_performance:
            scalable_sources = [
                item for item in source_performance if int(item.get("leads_total") or 0) >= 3 and float(item.get("lead_to_positive_pct") or 0.0) > 0.0
            ]
            if scalable_sources:
                best_source = sorted(
                    scalable_sources,
                    key=lambda item: (
                        -float(item.get("lead_to_positive_pct") or 0.0),
                        -float(item.get("sent_rate_pct") or 0.0),
                        -int(item.get("leads_total") or 0),
                    ),
                )[0]
                recommendations.append(
                    f"Источник для масштабирования: {best_source.get('source_kind') or 'unknown'} / {best_source.get('source_provider') or 'unknown'} ({best_source.get('lead_to_positive_pct') or 0}% lead→positive)."
                )
            noisy_sources = [
                item for item in source_performance
                if int(item.get("leads_total") or 0) >= 5
                and float(item.get("lead_to_positive_pct") or 0.0) == 0.0
                and float(item.get("draft_rate_pct") or 0.0) < 35.0
            ]
            if noisy_sources:
                noisiest = sorted(
                    noisy_sources,
                    key=lambda item: (
                        int(item.get("leads_total") or 0),
                        -float(item.get("draft_rate_pct") or 0.0),
                    ),
                    reverse=True,
                )[0]
                recommendations.append(
                    f"Источник даёт много шума: {noisiest.get('source_kind') or 'unknown'} / {noisiest.get('source_provider') or 'unknown'} — стоит ужесточить фильтры или снизить приоритет."
                )

        prompt_performance = []
        for pr in prompt_rows:
            prd = dict(pr) if hasattr(pr, "keys") else {}
            approved_total = int(prd.get("approved_total") or 0)
            edited_approved_total = int(prd.get("edited_approved_total") or 0)
            sent_for_prompt = int(prd.get("sent_total") or 0)
            positive_for_prompt = int(prd.get("positive_count") or 0)
            prompt_performance.append(
                {
                    "prompt_key": prd.get("prompt_key") or "unknown",
                    "prompt_version": prd.get("prompt_version") or "unknown",
                    "drafts_total": int(prd.get("drafts_total") or 0),
                    "approved_total": approved_total,
                    "edited_approved_total": edited_approved_total,
                    "edited_before_accept_pct": round((edited_approved_total / approved_total * 100.0), 2) if approved_total else 0.0,
                    "sent_total": sent_for_prompt,
                    "positive_count": positive_for_prompt,
                    "positive_rate_pct": round((positive_for_prompt / sent_for_prompt * 100.0), 2) if sent_for_prompt else 0.0,
                }
            )

        recommended_prompt_version = None
        if prompt_performance:
            viable_prompt_versions = [item for item in prompt_performance if int(item.get("approved_total") or 0) >= 2]
            if viable_prompt_versions:
                best_prompt = sorted(
                    viable_prompt_versions,
                    key=lambda item: (
                        -float(item.get("positive_rate_pct") or 0.0),
                        float(item.get("edited_before_accept_pct") or 0.0),
                        -int(item.get("approved_total") or 0),
                    ),
                )[0]
                recommended_prompt_version = best_prompt
                recommendations.append(
                    f"Наиболее стабильный prompt недели: {best_prompt.get('prompt_key')} / v{best_prompt.get('prompt_version')}."
                )

        return jsonify(
            {
                "success": True,
                "business_id": business_id,
                "window_days": window_days,
                "pilot_cohort": pilot_cohort or "all",
                "summary": {
                    "leads_total": int(row_dict.get("leads_total") or 0),
                    "parsed_completed_count": int(row_dict.get("parsed_completed_count") or 0),
                    "audited_count": int(row_dict.get("audited_count") or 0),
                    "matched_count": int(row_dict.get("matched_count") or 0),
                    "drafts_total": int(row_dict.get("drafts_total") or 0),
                    "drafts_approved_count": int(row_dict.get("drafts_approved_count") or 0),
                    "sent_total": sent_total,
                    "positive_count": positive_count,
                    "question_count": question_count,
                    "no_response_count": no_response_count,
                    "hard_no_count": hard_no_count,
                    "positive_rate_pct": positive_rate_pct,
                },
                "baseline": {
                    "window_days": window_days,
                    "sent_total": baseline_sent_total,
                    "positive_count": baseline_positive_count,
                    "positive_rate_pct": baseline_positive_rate_pct,
                    "deltas": {
                        "sent_total": sent_total - baseline_sent_total,
                        "positive_count": positive_count - baseline_positive_count,
                        "positive_rate_pct": round(positive_rate_pct - baseline_positive_rate_pct, 2),
                    },
                },
                "top_channels": top_channels,
                "source_performance": source_performance,
                "learning": learning,
                "prompt_performance": prompt_performance,
                "recommended_prompt_version": recommended_prompt_version,
                "blockers": blockers,
                "recommendations": recommendations,
                "edit_insights": {
                    "edited_accepts_total": edited_accepts_total,
                    "avg_generated_len": avg_generated_len,
                    "avg_final_len": avg_final_len,
                    "expanded_count": expanded_count,
                    "shortened_count": shortened_count,
                    "unchanged_count": unchanged_count,
                },
            }
        )
    except Exception as e:
        print(f"Error partnership Ralph loop summary: {e}")
        return jsonify({"error": str(e)}), 500

def _ensure_partnership_artifacts_table(conn) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS partnershipleadartifacts (
            lead_id TEXT PRIMARY KEY REFERENCES prospectingleads(id) ON DELETE CASCADE,
            audit_json JSONB,
            match_json JSONB,
            offer_draft_json JSONB,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

def _slugify_text(value: str) -> str:
    source = str(value or "").strip().lower()
    if not source:
        return ""
    aliased = _SLUG_PART_ALIASES.get(source)
    if aliased:
        return aliased
    converted = []
    for ch in source:
        if "a" <= ch <= "z" or "0" <= ch <= "9":
            converted.append(ch)
            continue
        if ch in _RU_LAT_MAP:
            converted.append(_RU_LAT_MAP[ch])
            continue
        if ch in {" ", "-", "_", ".", ",", "/", "|", ":"}:
            converted.append("-")
            continue
    slug = re.sub(r"-{2,}", "-", "".join(converted)).strip("-")
    return _SLUG_PART_ALIASES.get(slug, slug)

def _extract_address_street_name(address: str | None) -> str:
    text = str(address or "").strip()
    if not text:
        return ""
    parts = [part.strip() for part in text.split(",") if str(part or "").strip()]
    if not parts:
        return ""
    street_candidate = ""
    for part in parts:
        lower = part.lower()
        if any(token in lower for token in ("улиц", "ул.", "street", "st ", "st.", "просп", "наб", "шоссе", "бульвар", "переул", "коса", "sok", "cad", "mah")):
            street_candidate = part
            break
    if not street_candidate:
        street_candidate = parts[1] if len(parts) > 1 else parts[0]
    street_candidate = re.sub(r"\b\d+[a-zа-я\-\/]*\b", "", street_candidate, flags=re.IGNORECASE).strip(" ,.-")
    lower_candidate = street_candidate.lower()
    for prefix in (
        "улица ",
        "ул. ",
        "ул ",
        "проспект ",
        "пр. ",
        "переулок ",
        "пер. ",
        "набережная ",
        "наб. ",
        "шоссе ",
        "бульвар ",
    ):
        if lower_candidate.startswith(prefix):
            street_candidate = street_candidate[len(prefix):].strip()
            break
    street_candidate = _STREET_PREFIX_PATTERN.sub("", street_candidate).strip()
    return street_candidate

def _build_offer_slug(name: str | None, city: str | None = None, address: str | None = None) -> str:
    parts: list[str] = []
    for value in (
        _slugify_text(str(name or "").strip()),
        _slugify_text(str(city or "").strip()),
        _slugify_text(_extract_address_street_name(address)),
    ):
        if value and value not in parts:
            parts.append(value)
    if not parts:
        return f"lead-{uuid.uuid4().hex[:8]}"
    return "-".join(parts)

def _slugify_company_name(name: str) -> str:
    slug = _slugify_text(name)
    return slug or f"lead-{uuid.uuid4().hex[:8]}"

def _ensure_partnership_public_offers_table(conn) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS partnershippublicoffers (
            lead_id TEXT PRIMARY KEY REFERENCES prospectingleads(id) ON DELETE CASCADE,
            business_id UUID NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            page_json JSONB NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_by UUID,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_partnershippublicoffers_business_id
        ON partnershippublicoffers (business_id)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_partnershippublicoffers_is_active
        ON partnershippublicoffers (is_active)
        """
    )

def _ensure_admin_prospecting_public_offers_table(conn) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS adminprospectingleadpublicoffers (
            lead_id TEXT PRIMARY KEY REFERENCES prospectingleads(id) ON DELETE CASCADE,
            slug TEXT NOT NULL UNIQUE,
            page_json JSONB NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_by UUID,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_adminprospectingleadpublicoffers_is_active
        ON adminprospectingleadpublicoffers (is_active)
        """
    )
    cur.execute("ALTER TABLE adminprospectingleadpublicoffers ADD COLUMN IF NOT EXISTS business_id UUID")
    cur.execute("ALTER TABLE adminprospectingleadpublicoffers ADD COLUMN IF NOT EXISTS business_profile TEXT")
    cur.execute("ALTER TABLE adminprospectingleadpublicoffers ADD COLUMN IF NOT EXISTS source_type TEXT NOT NULL DEFAULT 'admin_prospecting_public_audit'")
    cur.execute("ALTER TABLE adminprospectingleadpublicoffers ADD COLUMN IF NOT EXISTS generated_json JSONB")
    cur.execute("ALTER TABLE adminprospectingleadpublicoffers ADD COLUMN IF NOT EXISTS edited_json JSONB")
    cur.execute("ALTER TABLE adminprospectingleadpublicoffers ADD COLUMN IF NOT EXISTS published_json JSONB")
    cur.execute("ALTER TABLE adminprospectingleadpublicoffers ADD COLUMN IF NOT EXISTS edit_status TEXT NOT NULL DEFAULT 'generated'")
    cur.execute("ALTER TABLE adminprospectingleadpublicoffers ADD COLUMN IF NOT EXISTS edited_by UUID")
    cur.execute("ALTER TABLE adminprospectingleadpublicoffers ADD COLUMN IF NOT EXISTS edited_at TIMESTAMPTZ")
    cur.execute("ALTER TABLE adminprospectingleadpublicoffers ADD COLUMN IF NOT EXISTS published_by UUID")
    cur.execute("ALTER TABLE adminprospectingleadpublicoffers ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ")
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_adminprospectingleadpublicoffers_edit_status
        ON adminprospectingleadpublicoffers (edit_status, updated_at DESC)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_adminprospectingleadpublicoffers_business_id
        ON adminprospectingleadpublicoffers (business_id)
        """
    )

def _build_admin_lead_offer_payload(
    *,
    lead: dict[str, Any],
    preview: dict[str, Any],
    preferred_language: str | None = None,
    enabled_languages: list[str] | None = None,
) -> dict[str, Any]:
    lead_name = str(lead.get("name") or "Компания").strip() or "Компания"
    preview_meta = preview.get("preview_meta") if isinstance(preview, dict) else {}
    if not isinstance(preview_meta, dict):
        preview_meta = {}
    current_state = preview.get("current_state") if isinstance(preview, dict) else {}
    if not isinstance(current_state, dict):
        current_state = {}
    business_preview = preview.get("business") if isinstance(preview, dict) else {}
    if not isinstance(business_preview, dict):
        business_preview = {}
    lead_city = str(lead.get("city") or "").strip()
    lead_address = str(lead.get("address") or "").strip()
    resolved_city = (
        lead_city
        or str(business_preview.get("city") or "").strip()
        or str(lead_address.split(",", 1)[0] if lead_address else "").strip()
    )
    primary_language, selected_languages = _normalize_public_audit_languages(preferred_language, enabled_languages)
    return {
        "lead_id": str(lead.get("id") or ""),
        "name": lead_name,
        "preferred_language": primary_language,
        "primary_language": primary_language,
        "enabled_languages": selected_languages,
        "available_languages": selected_languages,
        "category": lead.get("category"),
        "city": resolved_city or None,
        "address": lead.get("address"),
        "source_url": lead.get("source_url"),
        "logo_url": preview_meta.get("logo_url"),
        "photo_urls": preview_meta.get("photo_urls") if isinstance(preview_meta.get("photo_urls"), list) else [],
        "rating": current_state.get("rating"),
        "reviews_count": current_state.get("reviews_count"),
        "services_count": current_state.get("services_count"),
        "photos_state": current_state.get("photos_state"),
        "has_website": current_state.get("has_website"),
        "has_recent_activity": current_state.get("has_recent_activity"),
        "audit": {
            "summary_score": preview.get("summary_score"),
            "health_level": preview.get("health_level"),
            "health_label": preview.get("health_label"),
            "summary_text": preview.get("summary_text"),
            "findings": preview.get("findings") if isinstance(preview.get("findings"), list) else [],
            "recommended_actions": preview.get("recommended_actions") if isinstance(preview.get("recommended_actions"), list) else [],
            "issue_blocks": preview.get("issue_blocks") if isinstance(preview.get("issue_blocks"), list) else [],
            "top_3_issues": preview.get("top_3_issues") if isinstance(preview.get("top_3_issues"), list) else [],
            "action_plan": preview.get("action_plan") if isinstance(preview.get("action_plan"), dict) else {},
            "audit_profile": preview.get("audit_profile"),
            "audit_profile_label": preview.get("audit_profile_label"),
            "best_fit_customer_profile": preview.get("best_fit_customer_profile") if isinstance(preview.get("best_fit_customer_profile"), list) else [],
            "weak_fit_customer_profile": preview.get("weak_fit_customer_profile") if isinstance(preview.get("weak_fit_customer_profile"), list) else [],
            "best_fit_guest_profile": preview.get("best_fit_guest_profile") if isinstance(preview.get("best_fit_guest_profile"), list) else [],
            "weak_fit_guest_profile": preview.get("weak_fit_guest_profile") if isinstance(preview.get("weak_fit_guest_profile"), list) else [],
            "search_intents_to_target": preview.get("search_intents_to_target") if isinstance(preview.get("search_intents_to_target"), list) else [],
            "photo_shots_missing": preview.get("photo_shots_missing") if isinstance(preview.get("photo_shots_missing"), list) else [],
            "positioning_focus": preview.get("positioning_focus") if isinstance(preview.get("positioning_focus"), list) else [],
            "cadence": preview.get("cadence") if isinstance(preview.get("cadence"), dict) else {},
            "services_preview": preview.get("services_preview") if isinstance(preview.get("services_preview"), list) else [],
            "rating": current_state.get("rating"),
            "reviews_count": current_state.get("reviews_count"),
            "subscores": preview.get("subscores") if isinstance(preview.get("subscores"), dict) else {},
            "current_state": current_state,
            "parse_context": preview.get("parse_context") if isinstance(preview.get("parse_context"), dict) else {},
            "revenue_potential": preview.get("revenue_potential") if isinstance(preview.get("revenue_potential"), dict) else {},
            "reviews_preview": preview.get("reviews_preview") if isinstance(preview.get("reviews_preview"), list) else [],
            "news_preview": preview.get("news_preview") if isinstance(preview.get("news_preview"), list) else [],
        },
        "audit_full": preview if isinstance(preview, dict) else {},
        "cta": {
            "telegram_url": lead.get("telegram_url"),
            "whatsapp_url": lead.get("whatsapp_url"),
            "email": lead.get("email"),
            "website": lead.get("website"),
        },
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

def _build_partnership_offer_payload(
    *,
    lead: dict[str, Any],
    audit_json: dict[str, Any] | None,
    match_json: dict[str, Any] | None,
    offer_draft_json: dict[str, Any] | None,
    preferred_language: str | None = None,
    enabled_languages: list[str] | None = None,
) -> dict[str, Any]:
    lead_name = str(lead.get("name") or "Партнёр").strip() or "Партнёр"
    source_url = str(lead.get("source_url") or "").strip()
    source_payload = lead.get("search_payload_json")
    if not isinstance(source_payload, dict):
        source_payload = {}
    logo_url = _normalize_media_url(source_payload.get("logo_url"))
    photos = source_payload.get("photos")
    photo_urls: list[str] = []
    if isinstance(photos, list):
        for item in photos:
            value = _normalize_media_url(item) or ""
            if value:
                photo_urls.append(value)
    cta = {
        "telegram_url": str(lead.get("telegram_url") or "").strip() or None,
        "whatsapp_url": str(lead.get("whatsapp_url") or "").strip() or None,
        "email": str(lead.get("email") or "").strip() or None,
        "website": str(lead.get("website") or "").strip() or None,
    }
    audit = audit_json if isinstance(audit_json, dict) else {}
    match = match_json if isinstance(match_json, dict) else {}
    draft = offer_draft_json if isinstance(offer_draft_json, dict) else {}
    message = (
        str(draft.get("approved_text") or "").strip()
        or str(draft.get("edited_text") or "").strip()
        or str(draft.get("generated_text") or "").strip()
    )

    primary_language, selected_languages = _normalize_public_audit_languages(preferred_language, enabled_languages)
    return {
        "lead_id": str(lead.get("id") or ""),
        "name": lead_name,
        "preferred_language": primary_language,
        "primary_language": primary_language,
        "enabled_languages": selected_languages,
        "available_languages": selected_languages,
        "category": lead.get("category"),
        "city": lead.get("city"),
        "address": lead.get("address"),
        "source_url": source_url,
        "logo_url": logo_url,
        "photo_urls": photo_urls[:8],
        "audit": {
            "summary_score": audit.get("summary_score"),
            "health_level": audit.get("health_level"),
            "health_label": audit.get("health_label"),
            "summary_text": audit.get("summary_text"),
            "findings": audit.get("findings") if isinstance(audit.get("findings"), list) else [],
            "recommended_actions": audit.get("recommended_actions") if isinstance(audit.get("recommended_actions"), list) else [],
            "issue_blocks": audit.get("issue_blocks") if isinstance(audit.get("issue_blocks"), list) else [],
            "top_3_issues": audit.get("top_3_issues") if isinstance(audit.get("top_3_issues"), list) else [],
            "action_plan": audit.get("action_plan") if isinstance(audit.get("action_plan"), dict) else {},
            "audit_profile": audit.get("audit_profile"),
            "audit_profile_label": audit.get("audit_profile_label"),
            "best_fit_customer_profile": audit.get("best_fit_customer_profile") if isinstance(audit.get("best_fit_customer_profile"), list) else [],
            "weak_fit_customer_profile": audit.get("weak_fit_customer_profile") if isinstance(audit.get("weak_fit_customer_profile"), list) else [],
            "best_fit_guest_profile": audit.get("best_fit_guest_profile") if isinstance(audit.get("best_fit_guest_profile"), list) else [],
            "weak_fit_guest_profile": audit.get("weak_fit_guest_profile") if isinstance(audit.get("weak_fit_guest_profile"), list) else [],
            "search_intents_to_target": audit.get("search_intents_to_target") if isinstance(audit.get("search_intents_to_target"), list) else [],
            "photo_shots_missing": audit.get("photo_shots_missing") if isinstance(audit.get("photo_shots_missing"), list) else [],
            "positioning_focus": audit.get("positioning_focus") if isinstance(audit.get("positioning_focus"), list) else [],
            "cadence": audit.get("cadence") if isinstance(audit.get("cadence"), dict) else {},
            "services_preview": audit.get("services_preview") if isinstance(audit.get("services_preview"), list) else [],
            "subscores": audit.get("subscores") if isinstance(audit.get("subscores"), dict) else {},
            "current_state": audit.get("current_state") if isinstance(audit.get("current_state"), dict) else {},
            "parse_context": audit.get("parse_context") if isinstance(audit.get("parse_context"), dict) else {},
            "revenue_potential": audit.get("revenue_potential") if isinstance(audit.get("revenue_potential"), dict) else {},
            "reviews_preview": audit.get("reviews_preview") if isinstance(audit.get("reviews_preview"), list) else [],
            "news_preview": audit.get("news_preview") if isinstance(audit.get("news_preview"), list) else [],
        },
        "audit_full": audit if isinstance(audit, dict) else {},
        "match": {
            "match_score": match.get("match_score"),
            "score_explanation": match.get("score_explanation"),
            "offer_angles": match.get("offer_angles") if isinstance(match.get("offer_angles"), list) else [],
        },
        "message": message or None,
        "cta": cta,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

def _make_public_offer_url(slug: str) -> str:
    frontend_base = str(os.environ.get("FRONTEND_BASE_URL") or "").strip().rstrip("/")
    if not frontend_base:
        frontend_base = "https://localos.pro"
    return f"{frontend_base}/{slug}"

def _is_internal_partnership_source_url(url: Any) -> bool:
    return str(url or "").strip().lower().startswith("localos-doc://")

def _load_latest_sales_room_url_for_lead(cur, lead_id: str) -> str:
    _ensure_sales_room_tables(cur.connection)
    cur.execute(
        """
        SELECT slug
        FROM sales_rooms
        WHERE lead_id = %s
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (lead_id,),
    )
    row = cur.fetchone()
    slug = str(row.get("slug") if row and hasattr(row, "get") else (row[0] if row else "")).strip()
    return _make_sales_room_url(slug) if slug else ""

def _sales_room_slug_base(*parts: Any) -> str:
    base = _build_offer_slug(
        str(parts[0] if len(parts) > 0 else "room"),
        str(parts[1] if len(parts) > 1 else ""),
        str(parts[2] if len(parts) > 2 else ""),
    )
    return f"room-{base}" if not base.startswith("room-") else base

def _unique_sales_room_slug(cur, base_slug: str, room_id: str | None = None) -> str:
    slug = _slugify_company_name(base_slug)
    suffix = 1
    while True:
        cur.execute("SELECT id FROM sales_rooms WHERE slug = %s LIMIT 1", (slug,))
        row = cur.fetchone()
        existing_id = ""
        if row and hasattr(row, "get"):
            existing_id = str(row.get("id") or "")
        if not row or (room_id and existing_id == room_id):
            return slug
        suffix += 1
        slug = f"{base_slug}-{suffix}"

def _short_list(items: Any, limit: int = 3) -> list[str]:
    if not isinstance(items, list):
        return []
    result: list[str] = []
    for item in items:
        text = ""
        if isinstance(item, dict):
            text = str(item.get("title") or item.get("description") or item.get("body") or "").strip()
        else:
            text = str(item or "").strip()
        if text:
            result.append(text)
        if len(result) >= limit:
            break
    return result

def _clean_sales_room_offer_text(text: str) -> str:
    lines = [line.rstrip() for line in str(text or "").replace("\r\n", "\n").split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    if lines:
        first_line_raw = lines[0].strip()
        first_line = first_line_raw.lower()
        greeting_prefixes = (
            "здравствуйте",
            "добрый день",
            "добрый вечер",
            "привет",
        )
        if first_line.rstrip("!. ,") in greeting_prefixes or any(first_line.startswith(f"{prefix},") for prefix in greeting_prefixes):
            lines.pop(0)
        else:
            for prefix in greeting_prefixes:
                pattern = re.compile(rf"^{re.escape(prefix)}[.!?,\s]+", re.IGNORECASE)
                if pattern.match(first_line_raw):
                    lines[0] = pattern.sub("", first_line_raw, count=1).strip()
                    break
    cleaned_lines: list[str] = []
    for line in lines:
        normalized = line.strip()
        if "/room/" in normalized or "localos.pro/room/" in normalized:
            continue
        cleaned_lines.append(line)
    while cleaned_lines and not cleaned_lines[-1].strip():
        cleaned_lines.pop()
    signature_starts = {"с уважением", "с уважением,", "спасибо", "спасибо,"}
    for index, line in enumerate(cleaned_lines):
        if line.strip().lower() in signature_starts:
            cleaned_lines = cleaned_lines[:index]
            break
    cleaned = "\n".join(cleaned_lines).strip()
    return re.sub(r"\n{3,}", "\n\n", cleaned)

def _extract_sales_room_offer_text(offer_draft_json: dict[str, Any] | None) -> str:
    if not isinstance(offer_draft_json, dict):
        return ""
    candidates: list[Any] = [
        offer_draft_json.get("approved_text"),
        offer_draft_json.get("edited_text"),
        offer_draft_json.get("generated_text"),
        offer_draft_json.get("text"),
        offer_draft_json.get("draft_text"),
        offer_draft_json.get("body_text"),
        offer_draft_json.get("message"),
    ]
    for key in ("draft", "offer", "payload"):
        nested = offer_draft_json.get(key)
        if isinstance(nested, dict):
            candidates.extend(
                [
                    nested.get("approved_text"),
                    nested.get("edited_text"),
                    nested.get("generated_text"),
                    nested.get("text"),
                    nested.get("draft_text"),
                    nested.get("body_text"),
                    nested.get("message"),
                ]
            )
    for candidate in candidates:
        cleaned = _clean_sales_room_offer_text(str(candidate or ""))
        if cleaned:
            return cleaned
    return ""

def _fallback_sales_room_offer_text(*, mode: str, business_name: str, lead_name: str) -> str:
    if mode == SALES_ROOM_MODE_PARTNER:
        return (
            f"Предлагаем обсудить партнёрство между {business_name} и {lead_name}.\n\n"
            "Возможный формат:\n"
            "— кросс-рекомендации клиентам, которым актуальны смежные услуги;\n"
            "— простой тест на 1–2 недели без сложной интеграции;\n"
            "— понятный следующий шаг после обсуждения деталей."
        )
    return (
        f"Предлагаем обсудить, как {lead_name} может получать больше обращений из локального спроса.\n\n"
        "Возможный формат:\n"
        "— посмотреть, где теряются обращения;\n"
        "— выбрать первые точки роста;\n"
        "— согласовать следующий шаг без лишней подготовки."
    )

def _build_organika_partner_offer_text(
    *,
    business_name: str,
    lead_name: str,
    audit_json: dict[str, Any],
) -> str:
    profile = str(audit_json.get("audit_profile") or "default_local_business").strip().lower()
    profile_angles = {
        "shopping_center": (
            "посетители центра, которым важно совместить несколько дел за один визит",
            "одну совместную памятку или локальную публикацию с полезным сценарием визита",
        ),
        "commercial_center": (
            "сотрудники и посетители комплекса, которые пользуются сервисами рядом с работой",
            "один полезный материал для арендаторов или посетителей с понятными локальными сценариями",
        ),
        "medical": (
            "жители района, которые заботятся о здоровье и внешнем виде, но принимают решения раздельно",
            "один совместный просветительский материал без медицинских рекомендаций и передачи данных клиентов",
        ),
        "fitness": (
            "люди, которые совмещают тренировки и уход за собой",
            "один совместный материал о комфортном сценарии до или после тренировки",
        ),
        "beauty": (
            "локальная аудитория, которая регулярно выбирает услуги ухода",
            "одну небольшую совместную публикацию о разных сценариях ухода без обещания скидок",
        ),
        "fashion": (
            "семьи района, которым удобно совместить выбор детской одежды и другие дела рядом",
            "одну полезную подборку по сезонному детскому гардеробу без обещания скидок или наличия конкретных товаров",
        ),
        "retail": (
            "жители района, которые выбирают товары и локальные услуги в одной поездке",
            "одну полезную локальную подборку без обещания скидок или наличия конкретных товаров",
        ),
        "education_children": (
            "родители, которые планируют занятия ребёнка и свои дела в одном районе",
            "одну полезную локальную памятку для родителей без обещания скидок или передачи контактов",
        ),
        "family_entertainment": (
            "семьи, которые планируют досуг и другие дела в одном районе",
            "один совместный гид по комфортному семейному сценарию на выходной",
        ),
        "travel": (
            "жители района, которые готовятся к поездке и заранее планируют время",
            "один чек-лист подготовки к поездке без выдуманных цен и гарантий",
        ),
        "financial_services": (
            "жители района, которые ценят понятные локальные сервисы",
            "один совместный информационный материал без обещаний одобрения или финансовой выгоды",
        ),
        "repair_service": (
            "жители района, которым нужны регулярные бытовые услуги рядом",
            "один полезный материал о том, как подготовить вещь к ремонту и дальнейшему уходу",
        ),
    }
    audience, test_format = profile_angles.get(
        profile,
        (
            "жители и посетители района, которым важны понятные локальные сервисы",
            "один небольшой совместный материал для локальной аудитории",
        ),
    )
    return (
        f"У {business_name} и {lead_name} есть пересечение по локальной аудитории: {audience}.\n\n"
        "Предлагаем начать без интеграции и автоматической рассылки: "
        f"подготовить {test_format}.\n\n"
        "Следующий шаг — 20-минутный разговор: сверить интерес и выбрать один безопасный тест. "
        "Скидки, передача клиентов и любые рекомендации обсуждаются отдельно и заранее не обещаются."
    )

def _build_sales_room_proposal(
    *,
    mode: str,
    data_mode: str,
    lead: dict[str, Any],
    business_name: str,
    audit_json: dict[str, Any] | None = None,
    match_json: dict[str, Any] | None = None,
    offer_draft_json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    lead_name = str(lead.get("name") or "компания").strip() or "компания"
    body_text = _extract_sales_room_offer_text(offer_draft_json)
    if not body_text:
        body_text = _fallback_sales_room_offer_text(mode=mode, business_name=business_name, lead_name=lead_name)
    if mode == SALES_ROOM_MODE_PARTNER:
        return {
            "title": "Предложение",
            "summary": "",
            "body_text": body_text,
            "bullets": [],
            "next_step": "Обсудить детали и согласовать первый тест.",
            "data_mode": data_mode,
        }

    return {
        "title": "Предложение",
        "summary": "",
        "body_text": body_text,
        "bullets": [],
        "next_step": "Обсудить детали и выбрать первый шаг.",
        "data_mode": data_mode,
    }

def _build_sales_room_payload(
    *,
    mode: str,
    data_mode: str,
    lead: dict[str, Any],
    business_profile: dict[str, Any],
    audit_public_url: str,
    audit_json: dict[str, Any] | None,
    match_json: dict[str, Any] | None,
    proposal_json: dict[str, Any],
    slug: str,
) -> dict[str, Any]:
    business_name = _pick_business_display_name(business_profile)
    lead_name = str(lead.get("name") or "Компания").strip() or "Компания"
    safe_audit = audit_json if data_mode == SALES_ROOM_DATA_AUDITED and isinstance(audit_json, dict) else {}
    safe_match = match_json if data_mode == SALES_ROOM_DATA_AUDITED and isinstance(match_json, dict) else {}
    safe_audit_public_url = audit_public_url if data_mode == SALES_ROOM_DATA_AUDITED else ""
    return _to_json_compatible(
        {
            "type": "sales_room",
            "slug": slug,
            "public_url": _make_sales_room_url(slug),
            "mode": mode,
            "data_mode": data_mode,
            "business": {
                "name": business_name,
            },
            "recipient": {
                "name": lead_name,
                "category": lead.get("category"),
                "city": lead.get("city"),
                "address": lead.get("address"),
                "source_url": lead.get("source_url"),
            },
            "proposal": proposal_json,
            "audit": {
                "available": bool(safe_audit),
                "public_url": safe_audit_public_url or None,
                "summary_score": safe_audit.get("summary_score"),
                "health_label": safe_audit.get("health_label"),
                "summary_text": safe_audit.get("summary_text"),
                "findings": safe_audit.get("findings") if isinstance(safe_audit.get("findings"), list) else [],
                "recommended_actions": safe_audit.get("recommended_actions") if isinstance(safe_audit.get("recommended_actions"), list) else [],
            },
            "match": {
                "available": bool(safe_match),
                "match_score": safe_match.get("match_score"),
                "score_explanation": safe_match.get("score_explanation"),
                "offer_angles": safe_match.get("offer_angles") if isinstance(safe_match.get("offer_angles"), list) else [],
                "reason_codes": safe_match.get("reason_codes") if isinstance(safe_match.get("reason_codes"), list) else [],
            },
            "cta": {
                "primary_label": "Обсудить предложение" if mode == SALES_ROOM_MODE_PARTNER else "Обсудить рост",
                "secondary_label": "Посмотреть аудит" if safe_audit_public_url else "Проверить свою компанию в LocalOS",
                "secondary_url": safe_audit_public_url or "https://localos.pro",
            },
            "localos": {
                "badge": "Сделано в LocalOS",
                "description": "LocalOS помогает локальному бизнесу превращать спрос в клиентов и выручку.",
            },
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    )
