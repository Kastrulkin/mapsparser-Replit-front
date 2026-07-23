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
from services.lead_workstream_service import resolve_workstream, update_workstream
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

def _load_partnership_send_snapshot(*, business_id: str) -> dict[str, Any]:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            WITH draft_scope AS (
                SELECT
                    d.id, d.lead_id, d.workstream_id, d.channel, d.status,
                    d.generated_text, d.edited_text, d.approved_text,
                    d.created_at, d.updated_at,
                    l.name AS lead_name, l.category, l.city, l.email,
                    l.selected_channel, l.status AS lead_status,
                    l.pipeline_status AS lead_pipeline_status,
                    l.partnership_stage AS lead_partnership_stage
                FROM outreachmessagedrafts d
                JOIN prospectingleads l ON l.id = d.lead_id
                JOIN lead_workstreams ws ON ws.id = d.workstream_id
                WHERE d.status = %s
                  AND ws.client_business_id = %s
                  AND ws.workstream_type = 'client_partnership'
                  AND COALESCE(ws.status, '') NOT IN ('not_relevant', 'disqualified', 'closed_lost')
                  AND COALESCE(l.status, '') NOT IN ('not_relevant', 'disqualified', 'rejected', 'shortlist_rejected')
                  AND COALESCE(l.partnership_stage, '') NOT IN ('rejected', 'shortlist_rejected')
                  AND NOT EXISTS (
                        SELECT 1
                        FROM outreachsendqueue q
                        WHERE q.draft_id = d.id
                  )
            ),
            ranked_drafts AS (
                SELECT *,
                       ROW_NUMBER() OVER (
                           PARTITION BY lead_id
                           ORDER BY COALESCE(updated_at, created_at) DESC, created_at DESC, id DESC
                       ) AS draft_rank
                FROM draft_scope
            )
            SELECT
                id, lead_id, workstream_id, channel, status,
                generated_text, edited_text, approved_text,
                created_at, updated_at,
                lead_name, category, city, email,
                selected_channel, lead_status,
                lead_pipeline_status, lead_partnership_stage
            FROM ranked_drafts
            WHERE draft_rank = 1
            ORDER BY updated_at DESC, created_at DESC
            """,
            (DRAFT_APPROVED, business_id),
        )
        ready_drafts = [_serialize_draft(dict(row)) for row in cur.fetchall()]

        cur.execute(
            """
            SELECT DISTINCT b.id, b.batch_date, b.daily_limit, b.status, b.created_by, b.approved_by, b.created_at, b.updated_at
            FROM outreachsendbatches b
            JOIN outreachsendqueue q ON q.batch_id = b.id
            JOIN prospectingleads l ON l.id = q.lead_id
            WHERE l.business_id = %s
              AND COALESCE(l.intent, 'client_outreach') = 'partnership_outreach'
            ORDER BY b.batch_date DESC, b.created_at DESC
            LIMIT 20
            """,
            (business_id,),
        )
        batch_rows = [_serialize_batch_row(dict(row)) for row in cur.fetchall()]
        batches_by_id = {row["id"]: row for row in batch_rows}
        if batches_by_id:
            cur.execute(
                """
                SELECT
                    q.id, q.batch_id, q.lead_id, q.draft_id, q.channel,
                    q.delivery_status, q.provider_message_id, q.provider_name,
                    q.provider_account_id, q.recipient_kind, q.recipient_value, q.error_text,
                    q.sent_at, q.attempts, q.last_attempt_at, q.next_retry_at, q.dlq_at,
                    q.created_at, q.updated_at,
                    l.name AS lead_name,
                    l.email AS lead_email,
                    d.approved_text, d.generated_text,
                    r.classified_outcome AS latest_outcome,
                    r.human_confirmed_outcome AS latest_human_outcome,
                    r.raw_reply AS latest_raw_reply,
                    r.created_at AS latest_reaction_at
                FROM outreachsendqueue q
                JOIN prospectingleads l ON l.id = q.lead_id
                JOIN outreachmessagedrafts d ON d.id = q.draft_id
                LEFT JOIN LATERAL (
                    SELECT classified_outcome, human_confirmed_outcome, raw_reply, created_at
                    FROM outreachreactions rx
                    WHERE rx.queue_id = q.id
                    ORDER BY rx.created_at DESC
                    LIMIT 1
                ) r ON TRUE
                WHERE q.batch_id = ANY(%s)
                ORDER BY q.created_at ASC
                """,
                (list(batches_by_id.keys()),),
            )
            for row in cur.fetchall():
                payload = dict(row)
                batches_by_id[payload["batch_id"]]["items"].append(payload)

        cur.execute(
            """
            SELECT
                r.id, r.queue_id, r.lead_id, r.raw_reply,
                r.classified_outcome, r.confidence, r.human_confirmed_outcome,
                r.note, r.created_by, r.created_at, r.updated_at,
                l.name AS lead_name,
                q.batch_id, q.channel, q.delivery_status
            FROM outreachreactions r
            JOIN outreachsendqueue q ON q.id = r.queue_id
            JOIN prospectingleads l ON l.id = r.lead_id
            WHERE l.business_id = %s
              AND COALESCE(l.intent, 'client_outreach') = 'partnership_outreach'
            ORDER BY r.created_at DESC
            LIMIT 50
            """,
            (business_id,),
        )
        reactions = [_serialize_timestamp_fields(dict(row)) for row in cur.fetchall()]
        return {"ready_drafts": ready_drafts, "batches": batch_rows, "reactions": reactions}
    finally:
        conn.close()

@admin_prospecting_bp.route("/api/partnership/send-batches", methods=["GET"])
def partnership_send_batches():
    """User-level partnership send queue snapshot."""
    user_data, error = _require_auth()
    if error:
        return error
    try:
        requested_business_id = str(request.args.get("business_id") or "").strip() or None
        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
        finally:
            conn.close()
        snapshot = _load_partnership_send_snapshot(business_id=business_id)
        return jsonify({"success": True, "daily_cap": MAX_DAILY_OUTREACH_BATCH, **snapshot})
    except Exception as e:
        print(f"Error loading partnership send batches: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/partnership/send-batches", methods=["POST"])
def partnership_create_send_batch():
    """Create partnership send batch from approved drafts of one business."""
    user_data, error = _require_auth()
    if error:
        return error
    try:
        data = request.get_json(silent=True) or {}
        requested_business_id = str(data.get("business_id") or "").strip() or None
        draft_ids = data.get("draft_ids") or None
        if draft_ids is not None and not isinstance(draft_ids, list):
            return jsonify({"error": "draft_ids must be an array"}), 400

        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
        finally:
            conn.close()

        conn = get_db_connection()
        try:
            cur = conn.cursor()
            remaining_slots = _remaining_daily_outreach_slots(conn)
            if remaining_slots <= 0:
                return jsonify({"error": f"Daily outreach cap reached ({MAX_DAILY_OUTREACH_BATCH}/day)"}), 400

            query = """
                WITH draft_scope AS (
                    SELECT d.id, d.lead_id, d.workstream_id, d.channel, d.created_at, d.updated_at
                    FROM outreachmessagedrafts d
                    JOIN prospectingleads l ON l.id = d.lead_id
                    JOIN lead_workstreams ws ON ws.id = d.workstream_id
                    WHERE d.status = %s
                      AND ws.client_business_id = %s
                      AND ws.workstream_type = 'client_partnership'
                      AND COALESCE(ws.status, '') NOT IN ('not_relevant', 'disqualified', 'closed_lost')
                      AND COALESCE(l.status, '') NOT IN ('not_relevant', 'disqualified', 'rejected', 'shortlist_rejected')
                      AND COALESCE(l.partnership_stage, '') NOT IN ('rejected', 'shortlist_rejected')
                      AND NOT EXISTS (
                            SELECT 1
                            FROM outreachsendqueue q
                            WHERE q.draft_id = d.id
                      )
                ),
                ranked_drafts AS (
                    SELECT *,
                           ROW_NUMBER() OVER (
                               PARTITION BY lead_id
                               ORDER BY COALESCE(updated_at, created_at) DESC, created_at DESC, id DESC
                           ) AS draft_rank
                    FROM draft_scope
                )
                SELECT id, lead_id, workstream_id, channel
                FROM ranked_drafts
                WHERE draft_rank = 1
            """
            params: list[Any] = [DRAFT_APPROVED, business_id]
            if draft_ids:
                query += " AND id = ANY(%s)"
                params.append(draft_ids)
            query += " ORDER BY updated_at DESC, created_at DESC LIMIT %s"
            params.append(remaining_slots)
            cur.execute(query, tuple(params))
            rows = [dict(row) for row in cur.fetchall()]
            if not rows:
                return jsonify({"error": "No approved partnership drafts available for queue"}), 400

            batch_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO outreachsendbatches (
                    id, batch_date, daily_limit, status, created_by
                ) VALUES (%s, CURRENT_DATE, %s, %s, %s)
                """,
                (batch_id, MAX_DAILY_OUTREACH_BATCH, BATCH_DRAFT, user_data["user_id"]),
            )
            for row in rows:
                cur.execute(
                    """
                    INSERT INTO outreachsendqueue (
                        id, batch_id, lead_id, workstream_id, draft_id, channel, delivery_status
                    ) VALUES (%s, %s, %s, NULLIF(%s, '')::uuid, %s, %s, %s)
                    """,
                    (
                        str(uuid.uuid4()),
                        batch_id,
                        row["lead_id"],
                        str(row.get("workstream_id") or ""),
                        row["id"],
                        row["channel"],
                        QUEUE_STATUS_QUEUED,
                    ),
                )
                cur.execute(
                    """
                    UPDATE prospectingleads
                    SET status = %s,
                        partnership_stage = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (QUEUED_FOR_SEND, "queued_for_send", row["lead_id"]),
                )
            conn.commit()
        finally:
            conn.close()

        snapshot = _load_partnership_send_snapshot(business_id=business_id)
        batch = next((item for item in snapshot["batches"] if item["id"] == batch_id), None)
        return jsonify({"success": True, "daily_cap": MAX_DAILY_OUTREACH_BATCH, "batch": batch, **snapshot})
    except Exception as e:
        print(f"Error creating partnership send batch: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/partnership/send-batches/<string:batch_id>/approve", methods=["POST"])
def partnership_approve_send_batch(batch_id):
    """Approve partnership batch for dispatch."""
    user_data, error = _require_auth()
    if error:
        return error
    try:
        data = request.get_json(silent=True) or {}
        requested_business_id = str(data.get("business_id") or "").strip() or None
        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
            cur.execute(
                """
                SELECT 1
                FROM outreachsendqueue q
                JOIN prospectingleads l ON l.id = q.lead_id
                WHERE q.batch_id = %s
                  AND l.business_id = %s
                  AND COALESCE(l.intent, 'client_outreach') = 'partnership_outreach'
                LIMIT 1
                """,
                (batch_id, business_id),
            )
            if not cur.fetchone():
                return jsonify({"error": "Batch not found"}), 404
        finally:
            conn.close()

        batch, approve_error = _approve_send_batch(batch_id, user_data["user_id"])
        if approve_error:
            return jsonify({"error": approve_error}), 400
        snapshot = _load_partnership_send_snapshot(business_id=business_id)
        return jsonify({"success": True, "batch": batch, **snapshot})
    except Exception as e:
        print(f"Error approving partnership send batch: {e}")
        return jsonify({"error": str(e)}), 500

def _partnership_queue_access(cur, *, queue_id: str, business_id: str) -> dict[str, Any] | None:
    cur.execute(
        """
        SELECT q.id AS queue_id, q.lead_id, q.delivery_status
        FROM outreachsendqueue q
        JOIN prospectingleads l ON l.id = q.lead_id
        WHERE q.id = %s
          AND l.business_id = %s
          AND COALESCE(l.intent, 'client_outreach') = 'partnership_outreach'
        LIMIT 1
        """,
        (queue_id, business_id),
    )
    row = cur.fetchone()
    return dict(row) if row else None

@admin_prospecting_bp.route("/api/partnership/send-queue/<string:queue_id>/reaction", methods=["POST"])
def partnership_record_queue_reaction(queue_id):
    """Record reaction/outcome for partnership queue item (user-level)."""
    user_data, error = _require_auth()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        requested_business_id = str(data.get("business_id") or "").strip() or None
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
            if not _partnership_queue_access(cur, queue_id=queue_id, business_id=business_id):
                return jsonify({"error": "Queue item not found"}), 404
        finally:
            conn.close()

        reaction, reaction_error = _record_reaction(
            queue_id,
            data.get("raw_reply"),
            data.get("outcome"),
            (data.get("note") or "").strip() or None,
            user_data["user_id"],
        )
        if reaction_error:
            status_code = 404 if reaction_error == "Queue item not found" else 400
            return jsonify({"error": reaction_error}), status_code
        return jsonify({"success": True, "reaction": reaction})
    except Exception as e:
        print(f"Error recording partnership reaction: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/partnership/send-queue/<string:queue_id>/delivery", methods=["POST"])
def partnership_update_send_queue_delivery(queue_id):
    """User-level manual delivery status update for partnership queue item."""
    user_data, error = _require_auth()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        requested_business_id = str(data.get("business_id") or "").strip() or None
        delivery_status = (data.get("delivery_status") or "").strip().lower()
        if delivery_status not in {QUEUE_STATUS_SENT, QUEUE_STATUS_DELIVERED, QUEUE_STATUS_FAILED}:
            return jsonify({"error": "delivery_status must be sent, delivered or failed"}), 400

        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
            if not _partnership_queue_access(cur, queue_id=queue_id, business_id=business_id):
                return jsonify({"error": "Queue item not found"}), 404
        finally:
            conn.close()

        row = _update_send_queue_delivery(
            queue_id,
            delivery_status,
            (data.get("provider_message_id") or "").strip() or None,
            (data.get("error_text") or "").strip() or None,
        )
        if not row:
            return jsonify({"error": "Queue item not found"}), 404
        return jsonify({"success": True, "item": row})
    except Exception as e:
        print(f"Error updating partnership send queue delivery: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/partnership/send-queue/<string:queue_id>", methods=["DELETE"])
def partnership_delete_send_queue_item(queue_id):
    """User-level delete for partnership queue item."""
    user_data, error = _require_auth()
    if error:
        return error

    try:
        requested_business_id = str(request.args.get("business_id") or "").strip() or None
        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
            if not _partnership_queue_access(cur, queue_id=queue_id, business_id=business_id):
                return jsonify({"error": "Queue item not found"}), 404
        finally:
            conn.close()

        deleted = _delete_send_queue_item(queue_id)
        if not deleted:
            return jsonify({"success": True, "already_deleted": True, "queue_id": queue_id})
        return jsonify({"success": True, "item": deleted})
    except Exception as e:
        print(f"Error deleting partnership send queue item: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/partnership/reactions/<string:reaction_id>/confirm", methods=["POST"])
def partnership_confirm_reaction(reaction_id):
    """Confirm/override partnership reaction outcome (user-level)."""
    user_data, error = _require_auth()
    if error:
        return error
    try:
        data = request.get_json(silent=True) or {}
        requested_business_id = str(data.get("business_id") or "").strip() or None
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
            cur.execute(
                """
                SELECT 1
                FROM outreachreactions r
                JOIN outreachsendqueue q ON q.id = r.queue_id
                JOIN prospectingleads l ON l.id = q.lead_id
                WHERE r.id = %s
                  AND l.business_id = %s
                  AND COALESCE(l.intent, 'client_outreach') = 'partnership_outreach'
                LIMIT 1
                """,
                (reaction_id, business_id),
            )
            if not cur.fetchone():
                return jsonify({"error": "Reaction not found"}), 404
        finally:
            conn.close()

        reaction, reaction_error = _confirm_reaction(
            reaction_id,
            data.get("outcome"),
            (data.get("note") or "").strip() or None,
            user_data["user_id"],
        )
        if reaction_error:
            status_code = 404 if reaction_error == "Reaction not found" else 400
            return jsonify({"error": reaction_error}), status_code
        return jsonify({"success": True, "reaction": reaction})
    except Exception as e:
        print(f"Error confirming partnership reaction: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/admin/prospecting/groups", methods=["GET"])
def get_lead_groups():
    """List manual lead groups with readiness summary."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        status_filter = str(request.args.get("status") or "").strip().lower() or None
        conn = get_db_connection()
        try:
            _ensure_manual_crm_tables(conn)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            query = """
                SELECT
                    g.id,
                    g.name,
                    g.description,
                    g.status,
                    g.channel_hint,
                    g.city_hint,
                    g.created_by,
                    g.created_at,
                    g.updated_at,
                    COUNT(DISTINCT gi.lead_id)::INT AS leads_count,
                    COUNT(DISTINCT gi.lead_id) FILTER (WHERE COALESCE(l.selected_channel, '') = '')::INT AS without_channel_count,
                    COUNT(DISTINCT gi.lead_id) FILTER (WHERE COALESCE(l.phone, '') = '' AND COALESCE(l.email, '') = '' AND COALESCE(l.telegram_url, '') = '' AND COALESCE(l.whatsapp_url, '') = '')::INT AS without_contact_count,
                    COUNT(DISTINCT gi.lead_id) FILTER (WHERE po.lead_id IS NULL)::INT AS without_audit_count,
                    COUNT(DISTINCT gi.lead_id) FILTER (WHERE d.id IS NOT NULL)::INT AS drafts_count
                FROM lead_groups g
                LEFT JOIN lead_group_items gi ON gi.group_id = g.id
                LEFT JOIN prospectingleads l ON l.id = gi.lead_id
                LEFT JOIN adminprospectingleadpublicoffers po ON po.lead_id = gi.lead_id AND po.is_active = TRUE
                LEFT JOIN LATERAL (
                    SELECT id
                    FROM outreachmessagedrafts d
                    WHERE d.lead_id = gi.lead_id
                    ORDER BY d.updated_at DESC, d.created_at DESC
                    LIMIT 1
                ) d ON TRUE
            """
            params: list[Any] = []
            if status_filter in ALLOWED_GROUP_STATUSES:
                query += " WHERE g.status = %s"
                params.append(status_filter)
            query += """
                GROUP BY g.id, g.name, g.description, g.status, g.channel_hint, g.city_hint, g.created_by, g.created_at, g.updated_at
                ORDER BY g.updated_at DESC, g.created_at DESC
            """
            cur.execute(query, tuple(params))
            groups = [dict(row) for row in cur.fetchall() or []]
        finally:
            conn.close()
        return jsonify({"success": True, "groups": _to_json_compatible(groups), "count": len(groups)})
    except Exception as e:
        print(f"Error loading lead groups: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/admin/prospecting/groups", methods=["POST"])
def create_lead_group():
    """Create a reusable lead group from selected leads."""
    user_data, error = _require_superadmin()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        name = str(data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "name is required"}), 400
        description = str(data.get("description") or "").strip() or None
        status = str(data.get("status") or GROUP_STATUS_DRAFT).strip().lower() or GROUP_STATUS_DRAFT
        if status not in ALLOWED_GROUP_STATUSES:
            return jsonify({"error": "Unsupported group status"}), 400
        lead_ids = [str(item).strip() for item in (data.get("lead_ids") or []) if str(item).strip()]
        lead_ids = list(dict.fromkeys(lead_ids))
        channel_hint = str(data.get("channel_hint") or "").strip().lower() or None
        city_hint = str(data.get("city_hint") or "").strip() or None

        conn = get_db_connection()
        try:
            _ensure_manual_crm_tables(conn)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            group_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO lead_groups (
                    id, name, description, status, channel_hint, city_hint, created_by, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                """,
                (
                    group_id,
                    name,
                    description,
                    status,
                    channel_hint,
                    city_hint,
                    str(user_data.get("user_id") or "") or None,
                ),
            )
            for lead_id in lead_ids:
                cur.execute(
                    """
                    INSERT INTO lead_group_items (id, group_id, lead_id, added_by, added_at)
                    VALUES (%s, %s, %s, %s, NOW())
                    ON CONFLICT (group_id, lead_id) DO NOTHING
                    """,
                    (
                        str(uuid.uuid4()),
                        group_id,
                        lead_id,
                        str(user_data.get("user_id") or "") or None,
                    ),
                )
                _record_lead_timeline_event(
                    cur,
                    lead_id=lead_id,
                    event_type="added_to_group",
                    actor_id=str(user_data.get("user_id") or "") or None,
                    payload={"group_id": group_id, "group_name": name},
                )
            conn.commit()
        finally:
            conn.close()
        return jsonify({"success": True, "group_id": group_id})
    except Exception as e:
        print(f"Error creating lead group: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/admin/prospecting/groups/<string:group_id>", methods=["GET"])
def get_lead_group(group_id):
    """Load one group with member leads."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        conn = get_db_connection()
        try:
            _ensure_manual_crm_tables(conn)
            _ensure_admin_prospecting_public_offers_table(conn)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT * FROM lead_groups WHERE id = %s", (group_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Group not found"}), 404
            group = dict(row)
            cur.execute(
                """
                SELECT l.*
                FROM lead_group_items gi
                JOIN prospectingleads l ON l.id = gi.lead_id
                WHERE gi.group_id = %s
                ORDER BY gi.added_at DESC
                """,
                (group_id,),
            )
            leads = [_normalize_lead_for_display(dict(item)) for item in cur.fetchall() or []]
            leads = [item for item in leads if item]
            lead_ids = [str(item.get("id") or "").strip() for item in leads if str(item.get("id") or "").strip()]
            offer_by_lead_id: dict[str, dict[str, Any]] = {}
            if lead_ids:
                cur.execute(
                    """
                    SELECT lead_id, slug, is_active, updated_at, page_json
                    FROM adminprospectingleadpublicoffers
                    WHERE lead_id = ANY(%s)
                    """,
                    (lead_ids,),
                )
                for offer in cur.fetchall() or []:
                    payload = dict(offer)
                    lead_id = str(payload.get("lead_id") or "").strip()
                    if lead_id:
                        offer_by_lead_id[lead_id] = payload
            for lead in leads:
                lead_id = str(lead.get("id") or "").strip()
                offer = offer_by_lead_id.get(lead_id)
                slug = str((offer or {}).get("slug") or "").strip()
                if offer and bool(offer.get("is_active")) and slug:
                    page_json = offer.get("page_json") if isinstance(offer.get("page_json"), dict) else {}
                    primary_language, enabled_languages = _normalize_public_audit_languages(
                        page_json.get("preferred_language"),
                        page_json.get("enabled_languages"),
                    )
                    lead["public_audit_slug"] = slug
                    lead["public_audit_url"] = _make_public_offer_url(slug)
                    lead["has_public_audit"] = True
                    lead["public_audit_updated_at"] = offer.get("updated_at")
                    lead["preferred_language"] = primary_language
                    lead["enabled_languages"] = enabled_languages
            timeline_preview = _latest_timeline_preview(cur, lead_ids)
            groups_summary = _group_summary_for_lead_ids(cur, lead_ids)
            for lead in leads:
                lead_id = str(lead.get("id") or "").strip()
                lead["timeline_preview"] = timeline_preview.get(lead_id)
                lead["groups"] = groups_summary.get(lead_id, [])
                lead["group_count"] = len(lead["groups"])
        finally:
            conn.close()
        return jsonify({"success": True, "group": _to_json_compatible(group), "leads": _to_json_compatible(leads), "count": len(leads)})
    except Exception as e:
        print(f"Error loading lead group: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/admin/prospecting/groups/<string:group_id>/add-leads", methods=["POST"])
def add_leads_to_group(group_id):
    """Add leads to an existing group."""
    user_data, error = _require_superadmin()
    if error:
        return error

    try:
        lead_ids = [str(item).strip() for item in ((request.get_json(silent=True) or {}).get("lead_ids") or []) if str(item).strip()]
        lead_ids = list(dict.fromkeys(lead_ids))
        if not lead_ids:
            return jsonify({"error": "lead_ids is required"}), 400
        conn = get_db_connection()
        try:
            _ensure_manual_crm_tables(conn)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT name FROM lead_groups WHERE id = %s", (group_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Group not found"}), 404
            group_name = str(row.get("name") or "").strip()
            for lead_id in lead_ids:
                cur.execute(
                    """
                    INSERT INTO lead_group_items (id, group_id, lead_id, added_by, added_at)
                    VALUES (%s, %s, %s, %s, NOW())
                    ON CONFLICT (group_id, lead_id) DO NOTHING
                    """,
                    (str(uuid.uuid4()), group_id, lead_id, str(user_data.get("user_id") or "") or None),
                )
                _record_lead_timeline_event(
                    cur,
                    lead_id=lead_id,
                    event_type="added_to_group",
                    actor_id=str(user_data.get("user_id") or "") or None,
                    payload={"group_id": group_id, "group_name": group_name},
                )
            conn.commit()
        finally:
            conn.close()
        return jsonify({"success": True, "group_id": group_id, "added_count": len(lead_ids)})
    except Exception as e:
        print(f"Error adding leads to group: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/admin/prospecting/groups/<string:group_id>/remove-leads", methods=["POST"])
def remove_leads_from_group(group_id):
    """Remove leads from group without changing their pipeline status."""
    user_data, error = _require_superadmin()
    if error:
        return error

    try:
        lead_ids = [str(item).strip() for item in ((request.get_json(silent=True) or {}).get("lead_ids") or []) if str(item).strip()]
        lead_ids = list(dict.fromkeys(lead_ids))
        if not lead_ids:
            return jsonify({"error": "lead_ids is required"}), 400
        conn = get_db_connection()
        try:
            _ensure_manual_crm_tables(conn)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT name FROM lead_groups WHERE id = %s", (group_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Group not found"}), 404
            group_name = str(row.get("name") or "").strip()
            cur.execute(
                """
                DELETE FROM lead_group_items
                WHERE group_id = %s
                  AND lead_id = ANY(%s)
                """,
                (group_id, lead_ids),
            )
            for lead_id in lead_ids:
                _record_lead_timeline_event(
                    cur,
                    lead_id=lead_id,
                    event_type="removed_from_group",
                    actor_id=str(user_data.get("user_id") or "") or None,
                    payload={"group_id": group_id, "group_name": group_name},
                )
            conn.commit()
        finally:
            conn.close()
        return jsonify({"success": True, "group_id": group_id, "removed_count": len(lead_ids)})
    except Exception as e:
        print(f"Error removing leads from group: {e}")
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

@admin_prospecting_bp.route("/api/admin/prospecting/send-batches", methods=["GET"])
def get_outreach_send_batches():
    """List approved drafts ready for queue and recent batches."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        snapshot = _load_send_queue_snapshot()
        return jsonify(
            {
                "success": True,
                "ready_drafts": snapshot["ready_drafts"],
                "batches": snapshot["batches"],
                "reactions": _load_reactions(),
                "daily_cap": MAX_DAILY_OUTREACH_BATCH,
            }
        )
    except Exception as e:
        print(f"Error loading outreach send batches: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/admin/prospecting/send-batches", methods=["POST"])
def create_outreach_send_batch():
    """Create capped daily outreach batch from approved drafts."""
    user_data, error = _require_superadmin()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        draft_ids = data.get("draft_ids") or None
        if draft_ids is not None and not isinstance(draft_ids, list):
            return jsonify({"error": "draft_ids must be an array"}), 400

        batch_id, batch_error = _create_send_batch(user_data["user_id"], draft_ids)
        if batch_error:
            return jsonify({"error": batch_error}), 400
        snapshot = _load_send_queue_snapshot()
        batch = next((item for item in snapshot["batches"] if item["id"] == batch_id), None)
        return jsonify(
            {
                "success": True,
                "batch": batch,
                "daily_cap": MAX_DAILY_OUTREACH_BATCH,
            }
        )
    except Exception as e:
        print(f"Error creating outreach send batch: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/admin/prospecting/send-batches/<string:batch_id>/approve", methods=["POST"])
def approve_outreach_send_batch(batch_id):
    """Manual approval before actual sending."""
    user_data, error = _require_superadmin()
    if error:
        return error

    try:
        batch, batch_error = _approve_send_batch(batch_id, user_data["user_id"])
        if batch_error:
            return jsonify({"error": batch_error}), 400 if batch_error != "Batch not found" else 404
        return jsonify({"success": True, "batch": batch})
    except Exception as e:
        print(f"Error approving outreach send batch: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/admin/prospecting/send-batches/<string:batch_id>/dispatch", methods=["POST"])
def dispatch_outreach_send_batch(batch_id):
    """Start real delivery for one approved batch."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        batch, batch_error = _start_batch_dispatch(batch_id)
        if batch_error:
            return jsonify({"error": batch_error}), 400 if batch_error != "Batch not found" else 404
        return jsonify({"success": True, "batch": batch})
    except Exception as e:
        print(f"Error dispatching outreach batch: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/admin/prospecting/send-batches/<string:batch_id>", methods=["DELETE"])
def delete_outreach_send_batch(batch_id):
    """Delete full outreach batch (queue rows are removed by cascade)."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        deleted = _delete_send_batch(batch_id)
        if not deleted:
            # Idempotent delete: treat missing row as already deleted.
            return jsonify({"success": True, "already_deleted": True, "batch_id": batch_id})
        return jsonify({"success": True, "batch": deleted})
    except Exception as e:
        print(f"Error deleting outreach batch: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/admin/prospecting/send-batches/cleanup-test", methods=["POST"])
def cleanup_outreach_test_batches():
    """Delete draft/test batches to keep queue clean."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        summary = _cleanup_test_send_batches()
        return jsonify({"success": True, **summary})
    except Exception as e:
        print(f"Error cleaning outreach test batches: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/admin/prospecting/send-dispatch", methods=["POST"])
def dispatch_outreach_send_queue():
    """Run one manual dispatch cycle for due outreach queue items."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        batch_size = max(1, min(int(data.get("batch_size", 20) or 20), 200))
        summary = dispatch_due_outreach_queue(batch_size=batch_size)
        return jsonify(summary)
    except Exception as e:
        print(f"Error dispatching outreach queue: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@admin_prospecting_bp.route("/api/admin/prospecting/telegram-app/replies/sync", methods=["POST"])
def sync_telegram_app_replies():
    """Pull inbound Telegram app replies into outreachreactions."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        batch_id = str(data.get("batch_id") or "").strip() or None
        limit = max(1, min(int(data.get("limit", 25) or 25), 200))
        summary = _sync_telegram_app_replies(batch_id=batch_id, limit=limit)
        return jsonify(summary)
    except Exception as e:
        print(f"Error syncing telegram_app replies: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@admin_prospecting_bp.route("/api/admin/prospecting/send-queue/<string:queue_id>/delivery", methods=["POST"])
def update_send_queue_delivery(queue_id):
    """Manually mark delivery result for queued item."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        delivery_status = (data.get("delivery_status") or "").strip().lower()
        if delivery_status not in {QUEUE_STATUS_SENT, QUEUE_STATUS_DELIVERED, QUEUE_STATUS_FAILED}:
            return jsonify({"error": "delivery_status must be sent, delivered or failed"}), 400

        row = _update_send_queue_delivery(
            queue_id,
            delivery_status,
            (data.get("provider_message_id") or "").strip() or None,
            (data.get("error_text") or "").strip() or None,
        )
        if not row:
            return jsonify({"error": "Queue item not found"}), 404
        return jsonify({"success": True, "item": row})
    except Exception as e:
        print(f"Error updating send queue delivery: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/admin/prospecting/send-queue/<string:queue_id>", methods=["DELETE"])
def delete_outreach_send_queue_item(queue_id):
    """Delete queued/sent item from outreach queue."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        deleted = _delete_send_queue_item(queue_id)
        if not deleted:
            # Idempotent delete: treat missing row as already deleted.
            return jsonify({"success": True, "already_deleted": True, "queue_id": queue_id})
        return jsonify({"success": True, "item": deleted})
    except Exception as e:
        print(f"Error deleting outreach queue item: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/admin/prospecting/send-queue/<string:queue_id>/reaction", methods=["POST"])
def record_send_queue_reaction(queue_id):
    """Record inbound reaction and classify basic outcome."""
    user_data, error = _require_superadmin()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        reaction, reaction_error = _record_reaction(
            queue_id,
            data.get("raw_reply"),
            data.get("outcome"),
            (data.get("note") or "").strip() or None,
            user_data["user_id"],
        )
        if reaction_error:
            status_code = 404 if reaction_error == "Queue item not found" else 400
            return jsonify({"error": reaction_error}), status_code
        return jsonify({"success": True, "reaction": reaction})
    except Exception as e:
        print(f"Error recording outreach reaction: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/admin/prospecting/reactions/<string:reaction_id>/confirm", methods=["POST"])
def confirm_outreach_reaction(reaction_id):
    """Override the detected outcome for an existing reaction."""
    user_data, error = _require_superadmin()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        reaction, reaction_error = _confirm_reaction(
            reaction_id,
            data.get("outcome"),
            (data.get("note") or "").strip() or None,
            user_data["user_id"],
        )
        if reaction_error:
            status_code = 404 if reaction_error == "Reaction not found" else 400
            return jsonify({"error": reaction_error}), status_code
        return jsonify({"success": True, "reaction": reaction})
    except Exception as e:
        print(f"Error confirming outreach reaction: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/admin/prospecting/lead/<string:lead_id>/draft-generate", methods=["POST"])
def generate_outreach_draft(lead_id):
    """Generate initial first-contact draft for lead in channel_selected."""
    user_data, error = _require_superadmin()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        workstream_id = str(data.get("workstream_id") or "").strip() or None
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM prospectingleads WHERE id = %s", (lead_id,))
            lead = cur.fetchone()
            if not lead:
                return jsonify({"error": "Lead not found"}), 404
            lead_dict = dict(lead)
            workstream = resolve_workstream(
                conn,
                lead_id=lead_id,
                workstream_id=workstream_id,
            ) if workstream_id else None
            if workstream:
                from services.contact_intelligence_service import enqueue_enrichment_job

                job = enqueue_enrichment_job(cur, str(workstream.get("id")), force=bool(data.get("force")))
                conn.commit()
                return jsonify(
                    {
                        "success": True,
                        "accepted": True,
                        "job": {
                            "id": str(job.get("id")),
                            "workstream_id": str(job.get("workstream_id")),
                            "status": job.get("status"),
                            "phase": job.get("current_phase"),
                        },
                        "reused": bool(job.get("reused")),
                        "message": "Контакты и основания письма проверяются перед созданием черновика",
                    }
                ), 202
            selected_status = str((workstream or {}).get("status") or lead_dict.get("status") or "")
            if selected_status not in {CHANNEL_SELECTED, PIPELINE_IN_PROGRESS}:
                return jsonify({"error": "Choose a channel before preparing a message"}), 400

            channel = str((workstream or {}).get("selected_channel") or lead_dict.get("selected_channel") or "").strip().lower()
            if channel not in ALLOWED_OUTREACH_CHANNELS:
                return jsonify({"error": "Lead has no approved outreach channel"}), 400
            if not _lead_has_channel_contact(lead_dict, channel):
                return jsonify({"error": _outreach_channel_contact_error(channel)}), 400

            draft_payload = _generate_first_message_draft(lead_dict, channel)
            draft_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO outreachmessagedrafts (
                    id, lead_id, workstream_id, channel, angle_type, tone, status,
                    generated_text, learning_note_json, created_by
                ) VALUES (
                    %s, %s, NULLIF(%s, '')::uuid, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING id, lead_id, workstream_id, channel, angle_type, tone, status,
                          generated_text, edited_text, approved_text,
                          learning_note_json, created_at, updated_at
                """,
                (
                    draft_id,
                    lead_id,
                    str((workstream or {}).get("id") or ""),
                    channel,
                    draft_payload["angle_type"],
                    draft_payload["tone"],
                    DRAFT_GENERATED,
                    draft_payload["generated_text"],
                    Json(
                        {
                            "source": draft_payload.get("prompt_source") or "local_fallback",
                            "prompt_key": draft_payload.get("prompt_key"),
                            "prompt_version": draft_payload.get("prompt_version"),
                        }
                    ),
                    user_data["user_id"],
                ),
            )
            draft = dict(cur.fetchone())
            record_ai_learning_event(
                capability="outreach.draft_first_message",
                event_type="generated",
                intent="client_outreach",
                user_id=user_data.get("user_id"),
                prompt_key=str(draft_payload.get("prompt_key") or ""),
                prompt_version=str(draft_payload.get("prompt_version") or ""),
                final_text=str(draft_payload.get("generated_text") or "")[:3000],
                metadata={"lead_id": lead_id, "channel": channel, "source": draft_payload.get("prompt_source")},
                conn=conn,
            )
            conn.commit()
        finally:
            conn.close()

        return jsonify({"success": True, "draft": _serialize_draft(draft)})
    except Exception as e:
        print(f"Error generating outreach draft: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/admin/prospecting/lead/<string:lead_id>/draft-generate-from-audit", methods=["POST"])
def generate_outreach_draft_from_audit(lead_id):
    """Generate first-contact draft from lead card preview and move lead to outreach flow."""
    user_data, error = _require_superadmin()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        requested_channel = str(data.get("channel") or "").strip().lower()
        channel = requested_channel if requested_channel in ALLOWED_OUTREACH_CHANNELS else "telegram"
        workstream_id = str(data.get("workstream_id") or "").strip() or None

        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM prospectingleads WHERE id = %s", (lead_id,))
            lead = cur.fetchone()
            if not lead:
                return jsonify({"error": "Lead not found"}), 404
            lead_dict = dict(lead)
            workstream = resolve_workstream(
                conn,
                lead_id=lead_id,
                workstream_id=workstream_id,
            ) if workstream_id else None

            display_lead = _normalize_lead_for_display(dict(lead_dict))
            if not display_lead:
                return jsonify({"error": "Lead is not available for preview"}), 404
            display_lead = _attach_admin_prospecting_public_offer_metadata(conn, display_lead)
            preview = build_lead_card_preview_snapshot(display_lead)
            if not _lead_has_channel_contact(display_lead, channel):
                return jsonify({"error": _outreach_channel_contact_error(channel)}), 400

            if workstream:
                update_workstream(
                    conn,
                    workstream_id=str(workstream.get("id") or ""),
                    status=PIPELINE_IN_PROGRESS,
                    selected_channel=channel,
                )
                updated_lead = lead_dict
            else:
                cur.execute(
                    """
                    UPDATE prospectingleads
                    SET status = %s,
                        selected_channel = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING *
                    """,
                    (CHANNEL_SELECTED, channel, lead_id),
                )
                updated_lead = dict(cur.fetchone())
            updated_lead = _attach_admin_prospecting_public_offer_metadata(conn, updated_lead)

            draft_payload = _generate_audit_first_message_draft(updated_lead, preview, channel)
            draft_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO outreachmessagedrafts (
                    id, lead_id, workstream_id, channel, angle_type, tone, status,
                    generated_text, edited_text, learning_note_json, created_by
                ) VALUES (
                    %s, %s, NULLIF(%s, '')::uuid, %s, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING id, lead_id, workstream_id, channel, angle_type, tone, status,
                          generated_text, edited_text, approved_text,
                          learning_note_json, created_at, updated_at
                """,
                (
                    draft_id,
                    lead_id,
                    str((workstream or {}).get("id") or ""),
                    channel,
                    draft_payload["angle_type"],
                    draft_payload["tone"],
                    DRAFT_GENERATED,
                    draft_payload["generated_text"],
                    draft_payload["generated_text"],
                    Json(
                        {
                            "source": draft_payload.get("prompt_source") or "lead_preview_audit",
                            "prompt_key": draft_payload.get("prompt_key"),
                            "prompt_version": draft_payload.get("prompt_version"),
                        }
                    ),
                    user_data["user_id"],
                ),
            )
            draft = dict(cur.fetchone())
            record_ai_learning_event(
                capability="outreach.draft_first_message",
                event_type="generated",
                intent="client_outreach",
                user_id=user_data.get("user_id"),
                prompt_key=str(draft_payload.get("prompt_key") or ""),
                prompt_version=str(draft_payload.get("prompt_version") or ""),
                final_text=str(draft_payload.get("generated_text") or "")[:3000],
                metadata={"lead_id": lead_id, "channel": channel, "source": draft_payload.get("prompt_source")},
                conn=conn,
            )
            conn.commit()
        finally:
            conn.close()

        return jsonify(
            {
                "success": True,
                "lead": _normalize_lead_for_display(updated_lead),
                "draft": _serialize_draft(draft),
            }
        )
    except Exception as e:
        print(f"Error generating outreach draft from audit: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/admin/prospecting/lead/<string:lead_id>/prepare-room", methods=["POST"])
def prepare_client_sales_room(lead_id):
    user_data, error = _require_superadmin()
    if error:
        return error
    try:
        data = request.get_json(silent=True) or {}
        data_mode = _normalize_sales_room_data_mode(data.get("data_mode"))
        channel = str(data.get("channel") or "manual").strip().lower()
        if channel not in ALLOWED_OUTREACH_CHANNELS:
            channel = "manual"
        result = _prepare_client_sales_room(
            lead_id=lead_id,
            user_id=str(user_data.get("user_id") or ""),
            data_mode=data_mode,
            channel=channel,
            audit_offer=data.get("audit_offer") if isinstance(data.get("audit_offer"), dict) else None,
            workstream_id=str(data.get("workstream_id") or "").strip() or None,
        )
        if result.get("error"):
            return jsonify(result), int(result.get("status_code") or 400)
        return jsonify(_to_json_compatible(result))
    except Exception as e:
        print(f"Error preparing client sales room: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/admin/sales-rooms/<string:room_id>/audit-offer", methods=["PATCH"])
def admin_update_sales_room_audit_offer(room_id):
    user_data, error = _require_auth()
    if error:
        return error
    try:
        data = request.get_json(silent=True) or {}
        conn = get_db_connection()
        try:
            _ensure_sales_room_tables(conn)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                """
                SELECT id, slug, business_id, mode, lead_id, room_json, status, updated_at
                FROM sales_rooms
                WHERE id = %s
                LIMIT 1
                """,
                (room_id,),
            )
            room = _row_to_dict(cur.fetchone())
            if not room:
                return jsonify({"error": "Sales room not found"}), 404
            if not _can_edit_sales_room(cur, room, user_data):
                return jsonify({"error": "Forbidden"}), 403
            offer = _upsert_sales_room_audit_offer(cur, room=room, data=data)
            _record_sales_room_event_by_id(
                cur,
                room_id=str(room.get("id") or ""),
                event_type="audit_offer_admin_updated",
                metadata={
                    "offer_id": str(offer.get("id") or ""),
                    "enabled": bool(offer.get("enabled")),
                    "status": str(offer.get("status") or ""),
                    "updated_by": str(user_data.get("user_id") or ""),
                },
            )
            conn.commit()
            return jsonify({"success": True, "audit_offer": _to_json_compatible(offer)})
        finally:
            conn.close()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        print(f"Error updating sales room audit offer: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/admin/prospecting/lead/<string:lead_id>/parse", methods=["POST"])
def parse_lead_card(lead_id):
    """Link lead to LocalOS business if needed and enqueue Yandex card parse."""
    user_data, error = _require_superadmin()
    if error:
        return error

    try:
        lead = _load_prospecting_lead(lead_id)
        if not lead:
            return jsonify({"error": "Lead not found"}), 404

        display_lead = _normalize_lead_for_display(dict(lead))
        if not display_lead:
            return jsonify({"error": "Lead is not available for parsing"}), 400

        business, business_created = _ensure_parse_business_for_lead(display_lead, str(user_data["user_id"]))
        business_id = str(business.get("id") or "").strip()
        if not business_id:
            return jsonify({"error": "Failed to resolve business for lead"}), 500

        _update_lead_business_link(lead_id, business_id)
        source_url = str(
            business.get("yandex_url")
            or display_lead.get("source_url")
            or ""
        ).strip()
        if not source_url:
            return jsonify({"error": "У лида нет ссылки на Яндекс Карты для запуска парсинга"}), 400

        task = _enqueue_parse_task_for_business(business_id, user_data["user_id"], source_url)
        refreshed_lead = _load_prospecting_lead(lead_id) or display_lead
        return jsonify(
            {
                "success": True,
                "lead": _normalize_lead_for_display(refreshed_lead),
                "business": {
                    "id": business_id,
                    "name": business.get("name"),
                    "created": bool(business_created),
                    "shadow": str(business.get("moderation_status") or "").strip().lower() == LEAD_OUTREACH_MODERATION_STATUS,
                },
                "parse_task": {
                    "id": task.get("id"),
                    "status": task.get("status"),
                    "task_type": task.get("task_type"),
                    "source": task.get("source"),
                    "updated_at": task.get("updated_at"),
                    "retry_after": task.get("retry_after"),
                    "existing": bool(task.get("existing")),
                },
            }
        )
    except Exception as e:
        print(f"Error parsing lead card: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/admin/prospecting/shortlist/parse", methods=["POST"])
def parse_shortlist_cards():
    """Bulk enqueue parsing for shortlist leads."""
    user_data, error = _require_superadmin()
    if error:
        return error

    try:
        payload = request.get_json(silent=True) or {}
        lead_ids = payload.get("lead_ids")
        ids: list[str] = [str(item).strip() for item in (lead_ids or []) if str(item).strip()]

        conn = get_db_connection()
        try:
            cur = conn.cursor()
            if ids:
                cur.execute("SELECT * FROM prospectingleads WHERE id = ANY(%s)", (ids,))
            else:
                cur.execute("SELECT * FROM prospectingleads WHERE status = %s", (SHORTLIST_APPROVED,))
            leads = [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

        if not leads:
            return jsonify({"error": "No leads found for parsing"}), 404

        results = []
        enqueued = 0
        skipped = 0
        failed = 0
        for raw_lead in leads:
            lead = _normalize_lead_for_display(dict(raw_lead))
            if not lead:
                skipped += 1
                results.append({"lead_id": raw_lead.get("id"), "status": "skipped", "error": "invalid_lead_payload"})
                continue
            try:
                business, business_created = _ensure_parse_business_for_lead(lead, str(user_data["user_id"]))
                business_id = str(business.get("id") or "").strip()
                if not business_id:
                    failed += 1
                    results.append({"lead_id": lead.get("id"), "status": "failed", "error": "business_resolution_failed"})
                    continue
                _update_lead_business_link(str(lead.get("id")), business_id)
                source_url = str(business.get("yandex_url") or lead.get("source_url") or "").strip()
                if not source_url:
                    failed += 1
                    results.append({"lead_id": lead.get("id"), "status": "failed", "error": "missing_source_url"})
                    continue
                task = _enqueue_parse_task_for_business(business_id, user_data["user_id"], source_url)
                if task.get("existing"):
                    skipped += 1
                    state = "already_running"
                else:
                    enqueued += 1
                    state = "enqueued"
                results.append(
                    {
                        "lead_id": lead.get("id"),
                        "business_id": business_id,
                        "business_created": bool(business_created),
                        "business_shadow": str(business.get("moderation_status") or "").strip().lower() == LEAD_OUTREACH_MODERATION_STATUS,
                        "status": state,
                        "task_id": task.get("id"),
                        "task_status": task.get("status"),
                    }
                )
            except Exception as exc:
                failed += 1
                results.append({"lead_id": lead.get("id"), "status": "failed", "error": str(exc)})

        return jsonify(
            {
                "success": True,
                "total": len(leads),
                "enqueued": enqueued,
                "skipped": skipped,
                "failed": failed,
                "results": results,
            }
        )
    except Exception as e:
        print(f"Error bulk parsing shortlist: {e}")
        return jsonify({"error": str(e)}), 500
