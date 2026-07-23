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
from services.llm import analyze_text_with_gigachat
from services.operator_credit_reservation import finalize_reserved_action_credits, reserve_paid_action_credits
from services.prospecting_service import ProspectingService
from services.lead_workstream_service import update_workstream
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
            cur.execute(
                """
                UPDATE prospectingleads
                SET status = %s,
                    updated_at = NOW()
                WHERE id = %s
                """,
                ("draft_ready", draft_dict["lead_id"]),
            )

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
            lead_intent = _resolve_lead_intent(cur, str(draft_dict["lead_id"]))
            record_ai_learning_event(
                conn=conn,
                capability="outreach.draft_first_message",
                event_type="accepted",
                intent=lead_intent,
                user_id=user_data.get("user_id"),
                accepted=True,
                edited_before_accept=(
                    str(draft_dict.get("generated_text") or "").strip() != approved_text
                ),
                draft_text=str(draft_dict.get("generated_text") or "")[:3000],
                final_text=approved_text[:3000],
                metadata={
                    "draft_id": draft_id,
                    "lead_id": str(draft_dict.get("lead_id") or ""),
                    "channel": draft_dict.get("channel"),
                    "angle_type": draft_dict.get("angle_type"),
                    "tone": draft_dict.get("tone"),
                },
            )
            conn.commit()
        finally:
            conn.close()

        return jsonify({"success": True, "draft": _serialize_draft(updated)})
    except Exception as e:
        print(f"Error approving outreach draft: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/admin/prospecting/drafts/<string:draft_id>/manual-sent", methods=["POST"])
def mark_outreach_draft_sent_manually(draft_id):
    """Mark approved draft as sent manually and create a history item in outreach queue."""
    user_data, error = _require_superadmin()
    if error:
        return error

    try:
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT
                    d.*,
                    l.name AS lead_name,
                    l.status AS lead_status,
                    l.selected_channel,
                    l.telegram_url,
                    l.whatsapp_url,
                    l.phone,
                    l.email
                FROM outreachmessagedrafts d
                JOIN prospectingleads l ON l.id = d.lead_id
                WHERE d.id = %s
                LIMIT 1
                """,
                (draft_id,),
            )
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Draft not found"}), 404
            draft = dict(row)
            channel = str(draft.get("channel") or draft.get("selected_channel") or "").strip().lower()
            if not channel:
                return jsonify({"error": "Draft has no channel"}), 400
            if channel != "manual" and not _lead_has_channel_contact(draft, channel):
                return jsonify({"error": _outreach_channel_contact_error(channel)}), 400

            cur.execute(
                """
                SELECT id
                FROM outreachsendqueue
                WHERE draft_id = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (draft_id,),
            )
            existing = cur.fetchone()
            recipient_kind, recipient_value = _resolve_manual_outreach_recipient(draft, channel)

            if existing:
                queue_id = str(existing["id"] if hasattr(existing, "__getitem__") else existing[0])
                cur.execute(
                    """
                    UPDATE outreachsendqueue
                    SET delivery_status = %s,
                        provider_name = %s,
                        provider_message_id = %s,
                        recipient_kind = %s,
                        recipient_value = %s,
                        error_text = NULL,
                        sent_at = NOW(),
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (QUEUE_STATUS_SENT, "manual", f"manual:{draft_id}", recipient_kind, recipient_value, queue_id),
                )
            else:
                batch_id = str(uuid.uuid4())
                queue_id = str(uuid.uuid4())
                cur.execute(
                    """
                    INSERT INTO outreachsendbatches (
                        id, batch_date, daily_limit, status, created_by, approved_by
                    ) VALUES (
                        %s, CURRENT_DATE, %s, %s, %s, %s
                    )
                    """,
                    (batch_id, MAX_DAILY_OUTREACH_BATCH, BATCH_APPROVED, user_data["user_id"], user_data["user_id"]),
                )
                cur.execute(
                    """
                    INSERT INTO outreachsendqueue (
                        id, batch_id, lead_id, workstream_id, draft_id, channel, delivery_status,
                        provider_message_id, provider_name, recipient_kind, recipient_value, sent_at
                    ) VALUES (
                        %s, %s, %s, NULLIF(%s, '')::uuid, %s, %s, %s,
                        %s, %s, %s, %s, NOW()
                    )
                    """,
                    (
                        queue_id,
                        batch_id,
                        draft["lead_id"],
                        str(draft.get("workstream_id") or ""),
                        draft_id,
                        channel,
                        QUEUE_STATUS_SENT,
                        f"manual:{draft_id}",
                        "manual",
                        recipient_kind,
                        recipient_value,
                    ),
                )

            if draft.get("workstream_id"):
                update_workstream(
                    conn,
                    workstream_id=str(draft.get("workstream_id") or ""),
                    status=PIPELINE_CONTACTED,
                    selected_channel=channel,
                    next_action_at=_next_followup_at(),
                    last_contact=True,
                    last_contact_comment="Marked sent manually from approved draft",
                )
            else:
                cur.execute(
                    """
                    UPDATE prospectingleads
                    SET status = %s,
                        pipeline_status = %s,
                        last_contact_at = NOW(),
                        last_contact_channel = %s,
                        last_contact_comment = %s,
                        next_action_at = %s,
                        last_manual_action_at = NOW(),
                        last_manual_action_by = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (
                        "sent",
                        PIPELINE_CONTACTED,
                        channel,
                        "Marked sent manually from approved draft",
                        _next_followup_at(),
                        str(user_data.get("user_id") or "") or None,
                        draft["lead_id"],
                    ),
                )
            _record_lead_timeline_event(
                cur,
                lead_id=str(draft["lead_id"]),
                workstream_id=str(draft.get("workstream_id") or "") or None,
                event_type="manual_contact_marked",
                actor_id=str(user_data.get("user_id") or "") or None,
                comment="Marked sent manually from approved draft",
                payload={"channel": channel, "draft_id": draft_id, "queue_id": queue_id},
            )
            conn.commit()
        finally:
            conn.close()

        return jsonify({"success": True, "draft_id": draft_id, "lead_id": draft["lead_id"]})
    except Exception as e:
        print(f"Error marking outreach draft as sent manually: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/admin/prospecting/drafts/<string:draft_id>/save", methods=["POST"])
def save_outreach_draft(draft_id):
    """Save edited outreach draft without approving it."""
    user_data, error = _require_superadmin()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        edited_text = (data.get("edited_text") or "").strip()
        if not edited_text:
            return jsonify({"error": "edited_text is required"}), 400

        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT status FROM outreachmessagedrafts WHERE id = %s", (draft_id,))
            draft = cur.fetchone()
            if not draft:
                return jsonify({"error": "Draft not found"}), 404

            current_status = draft["status"] if hasattr(draft, "__getitem__") else draft[0]
            next_status = DRAFT_GENERATED if current_status == DRAFT_REJECTED else current_status

            cur.execute(
                """
                UPDATE outreachmessagedrafts
                SET edited_text = %s,
                    status = %s,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING id, lead_id, channel, angle_type, tone, status,
                          generated_text, edited_text, approved_text,
                          learning_note_json, created_at, updated_at
                """,
                (
                    edited_text,
                    next_status,
                    draft_id,
                ),
            )
            updated = dict(cur.fetchone())
            lead_intent = _resolve_lead_intent(cur, str(updated.get("lead_id") or ""))
            record_ai_learning_event(
                conn=conn,
                capability="outreach.draft_first_message",
                event_type="edited",
                intent=lead_intent,
                user_id=user_data.get("user_id"),
                draft_text=str(updated.get("generated_text") or "")[:3000],
                final_text=str(edited_text or "")[:3000],
                metadata={
                    "draft_id": draft_id,
                    "lead_id": str(updated.get("lead_id") or ""),
                    "channel": updated.get("channel"),
                },
            )
            conn.commit()
        finally:
            conn.close()

        return jsonify({"success": True, "draft": _serialize_draft(updated)})
    except Exception as e:
        print(f"Error saving outreach draft: {e}")
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
            updated = dict(row)
            lead_intent = _resolve_lead_intent(cur, str(updated.get("lead_id") or ""))
            record_ai_learning_event(
                conn=conn,
                capability="outreach.draft_first_message",
                event_type="rejected",
                intent=lead_intent,
                user_id=user_data.get("user_id"),
                rejected=True,
                draft_text=str(updated.get("edited_text") or updated.get("generated_text") or "")[:3000],
                final_text="",
                metadata={
                    "draft_id": draft_id,
                    "lead_id": str(updated.get("lead_id") or ""),
                    "channel": updated.get("channel"),
                },
            )
            conn.commit()
        finally:
            conn.close()

        return jsonify({"success": True, "draft": _serialize_draft(updated)})
    except Exception as e:
        print(f"Error rejecting outreach draft: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/admin/ai/learning-metrics", methods=["GET"])
def ai_learning_metrics():
    """Basic acceptance/edit metrics for P0 learning visibility."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        intent = _normalize_learning_intent(request.args.get("intent") or "operations")
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            ensure_ai_learning_events_table(conn)
            cur.execute(
                """
                WITH latest_prompts AS (
                    SELECT DISTINCT ON (capability)
                        capability,
                        prompt_key,
                        prompt_version
                    FROM ailearningevents
                    WHERE intent = %s
                    ORDER BY capability, created_at DESC
                )
                SELECT
                    e.capability,
                    COUNT(*) FILTER (WHERE event_type = 'accepted') AS accepted_total,
                    COUNT(*) FILTER (WHERE event_type = 'accepted' AND COALESCE(edited_before_accept, FALSE) = FALSE) AS accepted_raw_total,
                    COUNT(*) FILTER (WHERE event_type = 'accepted' AND COALESCE(edited_before_accept, FALSE) = TRUE) AS accepted_edited_total,
                    COALESCE(lp.prompt_key, '') AS prompt_key,
                    COALESCE(lp.prompt_version, '') AS prompt_version
                FROM ailearningevents e
                LEFT JOIN latest_prompts lp ON lp.capability = e.capability
                WHERE e.intent = %s
                  AND e.created_at >= NOW() - INTERVAL '30 days'
                GROUP BY e.capability, lp.prompt_key, lp.prompt_version
                ORDER BY e.capability
                """,
                (intent, intent),
            )
            rows = cur.fetchall()
        finally:
            conn.close()

        items = []
        for row in rows:
            capability = row["capability"] if hasattr(row, "get") else row[0]
            accepted_total = int((row["accepted_total"] if hasattr(row, "get") else row[1]) or 0)
            accepted_raw_total = int((row["accepted_raw_total"] if hasattr(row, "get") else row[2]) or 0)
            accepted_edited_total = int((row["accepted_edited_total"] if hasattr(row, "get") else row[3]) or 0)
            prompt_key = (row["prompt_key"] if hasattr(row, "get") else row[4]) or ""
            prompt_version = (row["prompt_version"] if hasattr(row, "get") else row[5]) or ""
            accepted_raw_pct = (accepted_raw_total / accepted_total * 100.0) if accepted_total else 0.0
            edited_before_accept_pct = (accepted_edited_total / accepted_total * 100.0) if accepted_total else 0.0
            items.append(
                {
                    "capability": capability,
                    "accepted_total": accepted_total,
                    "accepted_raw_total": accepted_raw_total,
                    "accepted_edited_total": accepted_edited_total,
                    "accepted_raw_pct": round(accepted_raw_pct, 2),
                    "edited_before_accept_pct": round(edited_before_accept_pct, 2),
                    "prompt_key": prompt_key,
                    "prompt_version": prompt_version,
                }
            )

        return jsonify({"success": True, "intent": intent, "window_days": 30, "items": items})
    except Exception as e:
        print(f"Error loading ai learning metrics: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/admin/prospecting/drafts/<string:draft_id>", methods=["DELETE"])
def delete_outreach_draft(draft_id):
    """Delete outreach draft."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        deleted = _delete_outreach_draft(draft_id)
        if not deleted:
            # Idempotent delete: treat missing row as already deleted.
            return jsonify({"success": True, "already_deleted": True, "draft_id": draft_id})
        return jsonify({"success": True, "draft": _serialize_draft(deleted)})
    except Exception as e:
        print(f"Error deleting outreach draft: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/admin/prospecting/lead/<string:lead_id>/preview", methods=["GET"])
def preview_lead_card(lead_id):
    """Return deterministic preview snapshot for an outreach lead."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        lead = _load_prospecting_lead(lead_id)

        if not lead:
            return jsonify({"error": "Lead not found"}), 404

        lead = _drop_mismatched_explicit_business_link(dict(lead))
        lead = _sync_lead_business_link_from_parse_history(dict(lead))
        lead = _sync_lead_contacts_from_parsed_data(dict(lead))
        display_lead = _normalize_lead_for_display(dict(lead))
        if not display_lead:
            return jsonify({"error": "Lead is not available for preview"}), 404
        conn = get_db_connection()
        try:
            display_lead = _attach_admin_prospecting_public_offer_metadata(conn, display_lead)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            group_summary = _group_summary_for_lead_ids(cur, [lead_id])
            display_lead["groups"] = group_summary.get(lead_id, [])
            display_lead["group_count"] = len(display_lead["groups"])
            display_lead["timeline_preview"] = _latest_timeline_preview(cur, [lead_id]).get(lead_id)
        finally:
            conn.close()

        preview = build_lead_card_preview_snapshot(display_lead)
        return jsonify(_to_json_compatible({"success": True, "lead": display_lead, "preview": preview}))
    except Exception as e:
        print(f"Error building outreach lead preview: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/admin/prospecting/lead/<string:lead_id>/offer-page", methods=["POST"])
def generate_admin_prospecting_offer_page(lead_id):
    """Create/update public audit page for an outreach lead. Superadmin only."""
    user_data, error = _require_superadmin()
    if error:
        return error
    try:
        data = request.get_json(silent=True) or {}
        requested_language = str(data.get("primary_language") or data.get("language") or "en").strip().lower() or "en"
        requested_languages = data.get("enabled_languages")
        primary_language, enabled_languages = _normalize_public_audit_languages(requested_language, requested_languages)

        lead = _load_prospecting_lead(lead_id)
        if not lead:
            return jsonify({"error": "Lead not found"}), 404

        lead = _drop_mismatched_explicit_business_link(dict(lead))
        lead = _sync_lead_business_link_from_parse_history(dict(lead))
        lead = _sync_lead_contacts_from_parsed_data(dict(lead))
        display_lead = _normalize_lead_for_display(dict(lead))
        if not display_lead:
            return jsonify({"error": "Lead is not available for public page"}), 404

        preview = build_lead_card_preview_snapshot(display_lead)
        page_json = _to_json_compatible(
            _build_admin_lead_offer_payload(
                lead=display_lead,
                preview=preview,
                preferred_language=primary_language,
                enabled_languages=enabled_languages,
            )
        )
        ai_enrichment = _generate_lead_audit_enrichment(display_lead, preview, primary_language)
        audit_payload = page_json.get("audit") if isinstance(page_json.get("audit"), dict) else {}
        if audit_payload:
            enriched_summary = str(ai_enrichment.get("summary_text") or "").strip()
            enriched_actions = _normalize_recommended_actions(ai_enrichment.get("recommended_actions"))
            if enriched_summary:
                audit_payload["summary_text"] = enriched_summary
            if enriched_actions:
                audit_payload["recommended_actions"] = enriched_actions
            why_now = str(ai_enrichment.get("why_now") or "").strip()
            if why_now:
                audit_payload["why_now"] = why_now
            audit_payload["ai_enrichment"] = ai_enrichment.get("meta") if isinstance(ai_enrichment.get("meta"), dict) else {}
            page_json["audit"] = audit_payload
        page_json["ai_enrichment"] = ai_enrichment.get("meta") if isinstance(ai_enrichment.get("meta"), dict) else {}
        page_json = normalize_public_audit_page_json(page_json)

        conn = get_db_connection()
        try:
            _ensure_admin_prospecting_public_offers_table(conn)
            cur = conn.cursor()
            existing_row = _fetch_admin_public_offer_row(cur, lead_id)
            base_slug = _build_offer_slug(
                str(display_lead.get("name") or "lead"),
                str(display_lead.get("city") or ""),
                str(display_lead.get("address") or ""),
            )
            slug = base_slug
            suffix = 1
            while True:
                cur.execute(
                    """
                    SELECT lead_id
                    FROM adminprospectingleadpublicoffers
                    WHERE slug = %s
                    LIMIT 1
                    """,
                    (slug,),
                )
                row = cur.fetchone()
                if not row:
                    break
                existing_lead_id = row.get("lead_id") if hasattr(row, "get") else (row[0] if row else None)
                if str(existing_lead_id or "") == str(lead_id):
                    break
                suffix += 1
                slug = f"{base_slug}-{suffix}"

            generated_json = copy.deepcopy(page_json)
            existing_edited_json = existing_row.get("edited_json") if isinstance((existing_row or {}).get("edited_json"), dict) else None
            existing_status = str((existing_row or {}).get("edit_status") or "").strip() or "generated"
            next_published_json = copy.deepcopy(generated_json)
            next_page_json = copy.deepcopy(generated_json)
            next_edit_status = "generated"
            if existing_edited_json:
                editor_blocks = normalize_editor_blocks(existing_edited_json.get("blocks"))
                if existing_status == "published":
                    next_published_json = apply_editor_blocks_to_page_json(generated_json, editor_blocks)
                    next_page_json = copy.deepcopy(next_published_json)
                    next_edit_status = "published"
                else:
                    existing_published_json = existing_row.get("published_json") if isinstance((existing_row or {}).get("published_json"), dict) else None
                    if existing_published_json:
                        next_published_json = existing_published_json
                        next_page_json = copy.deepcopy(existing_published_json)
                    next_edit_status = "draft_edited"

            cur.execute(
                """
                INSERT INTO adminprospectingleadpublicoffers (
                    lead_id, business_id, business_profile, source_type,
                    slug, page_json, generated_json, edited_json, published_json,
                    edit_status, is_active, created_by, published_by, published_at, created_at, updated_at
                ) VALUES (%s, NULLIF(%s, '')::uuid, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, NULLIF(%s, '')::uuid, NULLIF(%s, '')::uuid, %s, NOW(), NOW())
                ON CONFLICT (lead_id) DO UPDATE
                SET slug = EXCLUDED.slug,
                    page_json = EXCLUDED.page_json,
                    business_id = EXCLUDED.business_id,
                    business_profile = EXCLUDED.business_profile,
                    source_type = EXCLUDED.source_type,
                    generated_json = EXCLUDED.generated_json,
                    edited_json = COALESCE(adminprospectingleadpublicoffers.edited_json, EXCLUDED.edited_json),
                    published_json = CASE
                        WHEN COALESCE(adminprospectingleadpublicoffers.edit_status, 'generated') = 'published' THEN EXCLUDED.published_json
                        ELSE COALESCE(adminprospectingleadpublicoffers.published_json, EXCLUDED.published_json)
                    END,
                    edit_status = CASE
                        WHEN COALESCE(adminprospectingleadpublicoffers.edit_status, 'generated') = 'published' THEN 'published'
                        WHEN adminprospectingleadpublicoffers.edited_json IS NOT NULL THEN 'draft_edited'
                        ELSE EXCLUDED.edit_status
                    END,
                    is_active = TRUE,
                    published_by = CASE
                        WHEN COALESCE(adminprospectingleadpublicoffers.edit_status, 'generated') = 'published' THEN EXCLUDED.published_by
                        ELSE adminprospectingleadpublicoffers.published_by
                    END,
                    published_at = CASE
                        WHEN COALESCE(adminprospectingleadpublicoffers.edit_status, 'generated') = 'published' THEN EXCLUDED.published_at
                        ELSE adminprospectingleadpublicoffers.published_at
                    END,
                    updated_at = NOW()
                """,
                (
                    lead_id,
                    str(display_lead.get("business_id") or ""),
                    str(page_json.get("audit", {}).get("audit_profile") or "").strip() or None,
                    "admin_prospecting_public_audit",
                    slug,
                    Json(next_page_json),
                    Json(generated_json),
                    Json(existing_edited_json) if existing_edited_json else None,
                    Json(next_published_json),
                    next_edit_status,
                    user_data.get("user_id"),
                    user_data.get("user_id") if next_edit_status == "published" else None,
                    datetime.now(timezone.utc) if next_edit_status == "published" else None,
                ),
            )
            conn.commit()
            display_lead = _attach_admin_prospecting_public_offer_metadata(conn, display_lead)
            record_ai_learning_event(
                capability="lead.audit_enrichment",
                event_type="generated",
                intent="client_outreach",
                user_id=user_data.get("user_id"),
                prompt_key=str((ai_enrichment.get("meta") or {}).get("prompt_key") or ""),
                prompt_version=str((ai_enrichment.get("meta") or {}).get("prompt_version") or ""),
                final_text=str(audit_payload.get("summary_text") or "")[:3000] if isinstance(audit_payload, dict) else None,
                metadata={
                    "lead_id": lead_id,
                    "source": str((ai_enrichment.get("meta") or {}).get("source") or ""),
                },
                conn=conn,
            )
            conn.commit()
        finally:
            conn.close()

        return jsonify(
            _to_json_compatible({
                "success": True,
                "slug": slug,
                "public_url": _append_public_offer_language(_make_public_offer_url(slug), primary_language),
                "page": page_json,
                "lead": display_lead,
            })
        )
    except Exception as e:
        print(f"Error generating admin prospecting offer page: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/admin/prospecting/lead/<string:lead_id>/audit-editor", methods=["GET"])
def get_admin_public_audit_editor(lead_id):
    user_data, error = _require_superadmin()
    if error:
        return error
    try:
        lead = _load_prospecting_lead(lead_id)
        if not lead:
            return jsonify({"error": "Lead not found"}), 404
        conn = get_db_connection()
        try:
            _ensure_admin_prospecting_public_offers_table(conn)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            row = _fetch_admin_public_offer_row(cur, lead_id)
            if not row:
                return jsonify({"error": "Public audit page is not generated yet"}), 404
            response_payload = _build_admin_public_offer_editor_response(row=row, lead=lead)
            response_payload["viewer"] = {"user_id": user_data.get("user_id")}
            return jsonify(response_payload)
        finally:
            conn.close()
    except Exception as e:
        print(f"Error loading admin public audit editor: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/admin/prospecting/lead/<string:lead_id>/audit-editor", methods=["PUT"])
def save_admin_public_audit_editor(lead_id):
    user_data, error = _require_superadmin()
    if error:
        return error
    try:
        data = request.get_json(silent=True) or {}
        blocks = data.get("blocks")
        if not isinstance(blocks, dict):
            return jsonify({"error": "blocks object is required"}), 400
        lead = _load_prospecting_lead(lead_id)
        if not lead:
            return jsonify({"error": "Lead not found"}), 404
        conn = get_db_connection()
        try:
            _ensure_admin_prospecting_public_offers_table(conn)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            row = _fetch_admin_public_offer_row(cur, lead_id)
            if not row:
                return jsonify({"error": "Public audit page is not generated yet"}), 404
            generated_blocks, edited_json, edit_status = _apply_admin_public_offer_edited_snapshot(
                row=row,
                edited_blocks=blocks,
            )
            cur.execute(
                """
                UPDATE adminprospectingleadpublicoffers
                SET edited_json = %s,
                    edit_status = %s,
                    edited_by = NULLIF(%s, '')::uuid,
                    edited_at = CASE WHEN %s = 'generated' THEN NULL ELSE NOW() END,
                    updated_at = NOW()
                WHERE lead_id = %s
                RETURNING
                    lead_id, slug, page_json, generated_json, edited_json, published_json,
                    business_id, business_profile, source_type, edit_status,
                    created_by, created_at, updated_at, edited_by, edited_at, published_by, published_at
                """,
                (
                    Json(edited_json) if edited_json else None,
                    edit_status,
                    user_data.get("user_id"),
                    edit_status,
                    lead_id,
                ),
            )
            updated_row = cur.fetchone()
            conn.commit()
            if not updated_row:
                return jsonify({"error": "Failed to save audit editor draft"}), 500
            response_payload = _build_admin_public_offer_editor_response(row=dict(updated_row), lead=lead)
            response_payload["saved"] = True
            response_payload["generated_blocks"] = generated_blocks
            return jsonify(response_payload)
        finally:
            conn.close()
    except Exception as e:
        print(f"Error saving admin public audit editor: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/admin/prospecting/lead/<string:lead_id>/audit-editor/diff", methods=["GET"])
def get_admin_public_audit_editor_diff(lead_id):
    _, error = _require_superadmin()
    if error:
        return error
    try:
        conn = get_db_connection()
        try:
            _ensure_admin_prospecting_public_offers_table(conn)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            row = _fetch_admin_public_offer_row(cur, lead_id)
            if not row:
                return jsonify({"error": "Public audit page is not generated yet"}), 404
            normalized_row = _normalize_admin_public_offer_row(row)
            state = normalize_editor_state(
                generated_page_json=normalized_row.get("generated_json") if isinstance(normalized_row.get("generated_json"), dict) else {},
                edited_json=normalized_row.get("edited_json") if isinstance(normalized_row.get("edited_json"), dict) else None,
                published_page_json=normalized_row.get("published_json") if isinstance(normalized_row.get("published_json"), dict) else {},
            )
            return jsonify({"success": True, "diff": compute_editor_diff(state["generated"], state["edited"], state["published"])})
        finally:
            conn.close()
    except Exception as e:
        print(f"Error loading admin public audit editor diff: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/admin/prospecting/lead/<string:lead_id>/audit-editor/reset-block", methods=["POST"])
def reset_admin_public_audit_editor_block(lead_id):
    user_data, error = _require_superadmin()
    if error:
        return error
    try:
        data = request.get_json(silent=True) or {}
        block_key = str(data.get("block") or "").strip()
        if block_key not in EDITOR_BLOCK_KEYS:
            return jsonify({"error": "Unknown block"}), 400
        lead = _load_prospecting_lead(lead_id)
        if not lead:
            return jsonify({"error": "Lead not found"}), 404
        conn = get_db_connection()
        try:
            _ensure_admin_prospecting_public_offers_table(conn)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            row = _fetch_admin_public_offer_row(cur, lead_id)
            if not row:
                return jsonify({"error": "Public audit page is not generated yet"}), 404
            normalized_row = _normalize_admin_public_offer_row(row)
            generated_blocks = build_generated_editor_blocks(
                normalized_row.get("generated_json") if isinstance(normalized_row.get("generated_json"), dict) else {}
            )
            current_edited_blocks = normalize_editor_blocks(
                (normalized_row.get("edited_json") or {}).get("blocks")
                if isinstance(normalized_row.get("edited_json"), dict)
                else None
            )
            current_edited_blocks[block_key] = copy.deepcopy(generated_blocks[block_key])
            _, next_edited_json, next_status = _apply_admin_public_offer_edited_snapshot(
                row=normalized_row,
                edited_blocks=current_edited_blocks,
            )
            cur.execute(
                """
                UPDATE adminprospectingleadpublicoffers
                SET edited_json = %s,
                    edit_status = %s,
                    edited_by = NULLIF(%s, '')::uuid,
                    edited_at = CASE WHEN %s = 'generated' THEN NULL ELSE NOW() END,
                    updated_at = NOW()
                WHERE lead_id = %s
                RETURNING
                    lead_id, slug, page_json, generated_json, edited_json, published_json,
                    business_id, business_profile, source_type, edit_status,
                    created_by, created_at, updated_at, edited_by, edited_at, published_by, published_at
                """,
                (
                    Json(next_edited_json) if next_edited_json else None,
                    next_status,
                    user_data.get("user_id"),
                    next_status,
                    lead_id,
                ),
            )
            updated_row = cur.fetchone()
            conn.commit()
            if not updated_row:
                return jsonify({"error": "Failed to reset block"}), 500
            response_payload = _build_admin_public_offer_editor_response(row=dict(updated_row), lead=lead)
            response_payload["reset_block"] = block_key
            return jsonify(response_payload)
        finally:
            conn.close()
    except Exception as e:
        print(f"Error resetting admin public audit block: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/admin/prospecting/lead/<string:lead_id>/audit-editor/publish", methods=["POST"])
def publish_admin_public_audit_editor(lead_id):
    user_data, error = _require_superadmin()
    if error:
        return error
    try:
        lead = _load_prospecting_lead(lead_id)
        if not lead:
            return jsonify({"error": "Lead not found"}), 404
        conn = get_db_connection()
        try:
            _ensure_admin_prospecting_public_offers_table(conn)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            row = _fetch_admin_public_offer_row(cur, lead_id)
            if not row:
                return jsonify({"error": "Public audit page is not generated yet"}), 404
            normalized_row = _normalize_admin_public_offer_row(row)
            generated_json = normalized_row.get("generated_json") if isinstance(normalized_row.get("generated_json"), dict) else {}
            generated_blocks = build_generated_editor_blocks(generated_json)
            edited_json = normalized_row.get("edited_json") if isinstance(normalized_row.get("edited_json"), dict) else None
            edited_blocks = normalize_editor_blocks(edited_json.get("blocks") if edited_json else generated_blocks)
            next_published_json = apply_editor_blocks_to_page_json(generated_json, edited_blocks)
            audit_id = f"admin_public_offer:{lead_id}"
            cur.execute(
                """
                UPDATE adminprospectingleadpublicoffers
                SET published_json = %s,
                    page_json = %s,
                    edit_status = 'published',
                    published_by = NULLIF(%s, '')::uuid,
                    published_at = NOW(),
                    updated_at = NOW()
                WHERE lead_id = %s
                RETURNING
                    lead_id, slug, page_json, generated_json, edited_json, published_json,
                    business_id, business_profile, source_type, edit_status,
                    created_by, created_at, updated_at, edited_by, edited_at, published_by, published_at
                """,
                (
                    Json(next_published_json),
                    Json(next_published_json),
                    user_data.get("user_id"),
                    lead_id,
                ),
            )
            updated_row = cur.fetchone()
            if not updated_row:
                conn.rollback()
                return jsonify({"error": "Failed to publish audit"}), 500
            _record_admin_public_audit_learning_events(
                conn=conn,
                user_id=str(user_data.get("user_id") or ""),
                lead_id=lead_id,
                audit_id=audit_id,
                business_id=str(updated_row.get("business_id") or ""),
                generated_page_json=generated_json,
                generated_blocks=generated_blocks,
                published_blocks=edited_blocks,
            )
            conn.commit()
            response_payload = _build_admin_public_offer_editor_response(row=dict(updated_row), lead=lead)
            response_payload["publish_success"] = True
            return jsonify(response_payload)
        finally:
            conn.close()
    except Exception as e:
        print(f"Error publishing admin public audit editor: {e}")
        return jsonify({"error": str(e)}), 500
