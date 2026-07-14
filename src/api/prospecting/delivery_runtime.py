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
from services.lead_workstream_service import (
    CLIENT_PARTNERSHIP,
    LOCALOS_SALES,
    create_workstream,
    normalize_workstream_type,
    update_workstream,
)
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

def _update_send_queue_delivery(queue_id: str, delivery_status: str, provider_message_id: str | None, error_text: str | None):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        sent_at_sql = "NOW()" if delivery_status in {QUEUE_STATUS_SENT, QUEUE_STATUS_DELIVERED, QUEUE_STATUS_FAILED} else "NULL"
        cur.execute(
            f"""
            UPDATE outreachsendqueue
            SET delivery_status = %s,
                provider_message_id = %s,
                error_text = %s,
                sent_at = {sent_at_sql},
                updated_at = NOW()
            WHERE id = %s
            RETURNING id, batch_id, lead_id, workstream_id, draft_id, channel, delivery_status,
                      provider_message_id, error_text, sent_at, created_at, updated_at
            """,
            (delivery_status, provider_message_id, error_text, queue_id),
        )
        row = cur.fetchone()
        if not row:
            return None
        payload = dict(row)
        lead_status = "sent" if delivery_status in {QUEUE_STATUS_SENT, QUEUE_STATUS_DELIVERED} else CHANNEL_SELECTED
        pipeline_status = PIPELINE_CONTACTED if delivery_status in {QUEUE_STATUS_SENT, QUEUE_STATUS_DELIVERED} else PIPELINE_IN_PROGRESS
        next_action_value = _next_followup_at()
        if payload.get("workstream_id"):
            update_workstream(
                conn,
                workstream_id=str(payload.get("workstream_id") or ""),
                status=pipeline_status,
                selected_channel=str(payload.get("channel") or "") or None,
                next_action_at=next_action_value,
                last_contact=delivery_status in {QUEUE_STATUS_SENT, QUEUE_STATUS_DELIVERED},
            )
        else:
            cur.execute(
                """
                UPDATE prospectingleads
                SET status = %s,
                    pipeline_status = %s,
                    last_contact_at = CASE WHEN %s THEN NOW() ELSE last_contact_at END,
                    last_contact_channel = CASE WHEN %s THEN %s ELSE last_contact_channel END,
                    next_action_at = CASE WHEN %s THEN %s ELSE next_action_at END,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (
                    lead_status,
                    pipeline_status,
                    delivery_status in {QUEUE_STATUS_SENT, QUEUE_STATUS_DELIVERED},
                    delivery_status in {QUEUE_STATUS_SENT, QUEUE_STATUS_DELIVERED},
                    payload.get("channel"),
                    delivery_status in {QUEUE_STATUS_SENT, QUEUE_STATUS_DELIVERED},
                    next_action_value,
                    payload.get("lead_id"),
                ),
            )
        _record_lead_timeline_event(
            cur,
            lead_id=str(payload.get("lead_id") or ""),
            workstream_id=str(payload.get("workstream_id") or "") or None,
            event_type="delivery_sent" if delivery_status in {QUEUE_STATUS_SENT, QUEUE_STATUS_DELIVERED} else "delivery_failed",
            payload={"queue_id": queue_id, "delivery_status": delivery_status, "provider_message_id": provider_message_id},
        )
        conn.commit()
        return payload
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def _record_reaction(
    queue_id: str,
    raw_reply: str | None,
    outcome: str | None,
    note: str | None,
    user_id: str,
    *,
    provider_name: str | None = None,
    provider_account_id: str | None = None,
    provider_message_id: str | None = None,
    reply_created_at: Any = None,
    prefer_ai: bool = True,
):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT q.id, q.lead_id, q.workstream_id, q.delivery_status
            FROM outreachsendqueue q
            WHERE q.id = %s
            """,
            (queue_id,),
        )
        queue_row = cur.fetchone()
        if not queue_row:
            return None, "Queue item not found"

        queue_payload = dict(queue_row)
        if queue_payload.get("delivery_status") == QUEUE_STATUS_FAILED:
            return None, "Cannot attach reaction to failed delivery"

        normalized_outcome = (outcome or "").strip().lower() or None
        if normalized_outcome and normalized_outcome not in ALLOWED_REPLY_OUTCOMES:
            return None, "Outcome must be one of: positive, question, no_response, hard_no"

        normalized_provider_name = str(provider_name or "").strip()[:64] or None
        normalized_provider_account_id = str(provider_account_id or "").strip()[:255] or None
        normalized_provider_message_id = _normalize_provider_message_id(provider_message_id)
        if normalized_provider_name and normalized_provider_message_id:
            cur.execute(
                """
                SELECT id, queue_id, lead_id, raw_reply, classified_outcome,
                       confidence, human_confirmed_outcome, note, created_by, created_at, updated_at,
                       provider_name, provider_account_id, provider_message_id, reply_created_at
                FROM outreachreactions
                WHERE provider_name = %s
                  AND provider_account_id IS NOT DISTINCT FROM %s
                  AND provider_message_id = %s
                LIMIT 1
                """,
                (normalized_provider_name, normalized_provider_account_id, normalized_provider_message_id),
            )
            existing = cur.fetchone()
            if existing:
                return dict(existing), "Reaction already recorded"

        if prefer_ai:
            classified_outcome, confidence, classifier_source = _classify_reply_outcome_ai(raw_reply or "")
        else:
            classified_outcome, confidence = _classify_reply_outcome(raw_reply or "")
            classifier_source = "heuristic"
        final_outcome = normalized_outcome or classified_outcome
        note_prefix = f"classifier={classifier_source}"
        note_value = f"{note_prefix}; {note}" if note else note_prefix

        reaction_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO outreachreactions (
                id, queue_id, lead_id, raw_reply, classified_outcome,
                confidence, human_confirmed_outcome, note, created_by,
                provider_name, provider_account_id, provider_message_id, reply_created_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s
            )
            RETURNING id, queue_id, lead_id, raw_reply, classified_outcome,
                      confidence, human_confirmed_outcome, note, created_by, created_at, updated_at,
                      provider_name, provider_account_id, provider_message_id, reply_created_at
            """,
            (
                reaction_id,
                queue_id,
                queue_payload["lead_id"],
                (raw_reply or "").strip() or None,
                classified_outcome,
                confidence,
                final_outcome,
                note_value,
                user_id,
                normalized_provider_name,
                normalized_provider_account_id,
                normalized_provider_message_id,
                reply_created_at,
            ),
        )
        reaction = dict(cur.fetchone())

        next_lead_status = _lead_status_for_outcome(final_outcome)
        next_pipeline_status = (
            PIPELINE_CONVERTED
            if next_lead_status in {"qualified", "converted"}
            else PIPELINE_REPLIED
            if next_lead_status == "responded"
            else PIPELINE_CONTACTED
        )
        if queue_payload.get("workstream_id"):
            update_workstream(
                conn,
                workstream_id=str(queue_payload.get("workstream_id") or ""),
                status=next_pipeline_status,
            )
        else:
            cur.execute(
                """
                UPDATE prospectingleads
                SET status = %s,
                    pipeline_status = %s,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (next_lead_status, next_pipeline_status, queue_payload["lead_id"]),
            )
        _record_lead_timeline_event(
            cur,
            lead_id=str(queue_payload["lead_id"]),
            workstream_id=str(queue_payload.get("workstream_id") or "") or None,
            event_type="reaction_recorded",
            actor_id=user_id,
            comment=(raw_reply or "").strip() or None,
            payload={"queue_id": queue_id, "outcome": final_outcome},
        )
        conn.commit()
        return reaction, None
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def _delete_outreach_draft(draft_id: str) -> dict[str, Any] | None:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            DELETE FROM outreachmessagedrafts
            WHERE id = %s
            RETURNING id, lead_id, channel, angle_type, tone, status,
                      generated_text, edited_text, approved_text,
                      learning_note_json, created_at, updated_at
            """,
            (draft_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        conn.commit()
        return dict(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def _delete_send_queue_item(queue_id: str) -> dict[str, Any] | None:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            DELETE FROM outreachsendqueue
            WHERE id = %s
            RETURNING id, batch_id, lead_id, draft_id, channel, delivery_status,
                      provider_message_id, error_text, sent_at, created_at, updated_at
            """,
            (queue_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        payload = dict(row)
        cur.execute(
            """
            UPDATE prospectingleads
            SET status = %s,
                pipeline_status = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (CHANNEL_SELECTED, PIPELINE_IN_PROGRESS, payload.get("lead_id")),
        )
        conn.commit()
        return payload
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def _delete_send_batch(batch_id: str) -> dict[str, Any] | None:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            DELETE FROM outreachsendbatches
            WHERE id = %s
            RETURNING id, batch_date, daily_limit, status, created_by, approved_by, created_at, updated_at
            """,
            (batch_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        conn.commit()
        return dict(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def _cleanup_test_send_batches() -> dict[str, int]:
    """Remove batches in draft state and their queue rows (test/abandoned batches)."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id
            FROM outreachsendbatches
            WHERE status = %s
            """,
            (BATCH_DRAFT,),
        )
        batch_ids = [str((row.get("id") if hasattr(row, "get") else row[0])) for row in (cur.fetchall() or [])]
        if not batch_ids:
            return {"deleted_batches": 0, "deleted_queue_items": 0}

        cur.execute(
            """
            DELETE FROM outreachsendqueue
            WHERE batch_id = ANY(%s)
            RETURNING id
            """,
            (batch_ids,),
        )
        deleted_queue = len(cur.fetchall() or [])
        cur.execute(
            """
            DELETE FROM outreachsendbatches
            WHERE id = ANY(%s)
            RETURNING id
            """,
            (batch_ids,),
        )
        deleted_batches = len(cur.fetchall() or [])
        conn.commit()
        return {"deleted_batches": deleted_batches, "deleted_queue_items": deleted_queue}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def _lead_status_for_outcome(outcome: str | None) -> str:
    return {
        "positive": "responded",
        "question": "responded",
        "hard_no": "closed_negative",
        "no_response": "closed_no_response",
    }.get(outcome or "", "responded")

def _confirm_reaction(reaction_id: str, outcome: str, note: str | None, user_id: str):
    normalized_outcome = (outcome or "").strip().lower()
    if normalized_outcome not in ALLOWED_REPLY_OUTCOMES:
        return None, "Outcome must be one of: positive, question, no_response, hard_no"

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT r.id, r.lead_id, r.note
            FROM outreachreactions r
            WHERE r.id = %s
            """,
            (reaction_id,),
        )
        row = cur.fetchone()
        if not row:
            return None, "Reaction not found"

        payload = dict(row)
        note_parts = []
        if payload.get("note"):
            note_parts.append(str(payload["note"]).strip())
        note_parts.append(f"human_override={normalized_outcome}")
        note_parts.append(f"confirmed_by={user_id}")
        if note:
            note_parts.append(note)
        note_value = "; ".join(part for part in note_parts if part)

        cur.execute(
            """
            UPDATE outreachreactions
            SET human_confirmed_outcome = %s,
                note = %s,
                updated_at = NOW()
            WHERE id = %s
            RETURNING id, queue_id, lead_id, raw_reply, classified_outcome,
                      confidence, human_confirmed_outcome, note, created_by, created_at, updated_at,
                      provider_name, provider_account_id, provider_message_id, reply_created_at
            """,
            (normalized_outcome, note_value, reaction_id),
        )
        reaction = dict(cur.fetchone())
        next_lead_status = _lead_status_for_outcome(normalized_outcome)
        next_pipeline_status = (
            PIPELINE_CONVERTED
            if next_lead_status in {"qualified", "converted"}
            else PIPELINE_REPLIED
            if next_lead_status == "responded"
            else PIPELINE_CONTACTED
        )

        cur.execute(
            """
            UPDATE prospectingleads
            SET status = %s,
                pipeline_status = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (next_lead_status, next_pipeline_status, payload["lead_id"]),
        )
        conn.commit()
        return reaction, None
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

@admin_prospecting_bp.route("/api/admin/prospecting/search", methods=["POST"])
def search_businesses():
    """Queue prospecting search via Apify (Yandex / 2GIS / Google / Apple)."""
    user_data, error = _require_superadmin()
    if error:
        return error

    _expire_stale_search_jobs()
    data = request.get_json(silent=True) or {}
    query = (data.get("query") or "").strip()
    location = (data.get("location") or "").strip()
    source = str(data.get("source") or "apify_yandex").strip().lower()
    search_limit = int(data.get("limit", 50) or 50)

    if source not in {"apify_yandex", "apify_2gis", "apify_google", "apify_apple"}:
        return jsonify({"error": "Unsupported source"}), 400

    if not query or not location:
        return jsonify({"error": "Query and location are required"}), 400
    if search_limit < 1:
        return jsonify({"error": "Limit must be positive"}), 400

    service = ProspectingService(source=source)
    if not service.client:
        return jsonify({"error": "APIFY_TOKEN is not configured"}), 500

    try:
        job_id = _create_search_job(
            source=source,
            query=query,
            location=location,
            search_limit=search_limit,
            actor_id=service.actor_id,
            user_id=user_data["user_id"],
        )
        worker = threading.Thread(
            target=_run_search_job,
            args=(job_id, source, service.actor_id, query, location, search_limit),
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
                    "source": source,
                    "actor_id": service.actor_id,
                }
            ),
            202,
        )
    except Exception as e:
        print(f"Error queueing prospecting search: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/admin/prospecting/business-parse-apify", methods=["POST"])
def queue_business_parse_apify():
    """Queue single business card parsing through Apify actor (Yandex / 2GIS / Google / Apple)."""
    user_data, error = _require_auth()
    if error:
        return error

    data = request.get_json(silent=True) or {}
    source = str(data.get("source") or "apify_yandex").strip().lower()
    if source not in {"apify_yandex", "apify_2gis", "apify_google", "apify_apple"}:
        return jsonify({"error": "Unsupported source"}), 400

    service = ProspectingService(source=source)
    if not service.client:
        return jsonify({"error": "APIFY_TOKEN is not configured"}), 500

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        business_id = _resolve_business_for_user(cur, user_data, str(data.get("business_id") or "").strip())
        if not business_id:
            return jsonify({"error": "Business not found or access denied"}), 404

        if source == "apify_2gis":
            cur.execute(
                """
                SELECT url
                FROM businessmaplinks
                WHERE business_id = %s
                  AND (
                    map_type = '2gis'
                    OR LOWER(url) LIKE '%%2gis.ru/%%'
                    OR LOWER(url) LIKE '%%2gis.com/%%'
                  )
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (business_id,),
            )
        elif source == "apify_google":
            cur.execute(
                """
                SELECT url
                FROM businessmaplinks
                WHERE business_id = %s
                  AND (
                    map_type = 'google'
                    OR LOWER(url) LIKE '%%google.com/maps/%%'
                    OR LOWER(url) LIKE '%%google.com/search%%'
                    OR LOWER(url) LIKE '%%maps.app.goo.gl/%%'
                  )
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (business_id,),
            )
        elif source == "apify_apple":
            cur.execute(
                """
                SELECT url
                FROM businessmaplinks
                WHERE business_id = %s
                  AND (
                    map_type = 'apple'
                    OR LOWER(url) LIKE '%%maps.apple.com/%%'
                  )
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (business_id,),
            )
        else:
            cur.execute(
                """
                SELECT url
                FROM businessmaplinks
                WHERE business_id = %s
                  AND (
                    map_type = 'yandex'
                    OR LOWER(url) LIKE '%%yandex.ru/maps/%%'
                    OR LOWER(url) LIKE '%%yandex.com/maps/%%'
                  )
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (business_id,),
            )

        row = cur.fetchone()
        map_url = ""
        if row:
            map_url = str(row.get("url") if hasattr(row, "get") else row[0]).strip()
        if not map_url:
            return jsonify({"error": "Map link is not configured for this business"}), 400

        task_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO parsequeue (
                id, business_id, account_id, task_type, source,
                status, user_id, url, created_at, updated_at
            )
            VALUES (%s, %s, NULL, 'parse_card', %s, 'pending', %s, %s, NOW(), NOW())
            """,
            (task_id, business_id, source, str(user_data.get("user_id") or ""), map_url),
        )
        conn.commit()
        return jsonify(
            {
                "success": True,
                "task_id": task_id,
                "source": source,
                "message": "Apify-парсинг добавлен в очередь",
            }
        )
    except Exception as e:
        conn.rollback()
        print(f"Error queueing business Apify parse: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

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
        row = _mark_search_job_failed_if_stale(dict(row))
        raw_results = row.get("results_json")
        apify_status = None
        results_payload = []
        if isinstance(raw_results, list):
            results_payload = raw_results
        elif isinstance(raw_results, dict):
            apify_status = ((raw_results.get("_apify") or {}).get("status") if isinstance(raw_results.get("_apify"), dict) else None)
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
                    "apify_status": apify_status,
                    "error_text": row.get("error_text"),
                    "results": results_payload,
                    "created_at": row.get("created_at"),
                    "updated_at": row.get("updated_at"),
                    "completed_at": row.get("completed_at"),
                },
            }
        )
    except Exception as e:
        print(f"Error getting prospecting search job: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/admin/prospecting/search-job/latest", methods=["GET"])
def get_latest_search_job_status():
    """Get latest async search job for current superadmin."""
    user_data, error = _require_superadmin()
    if error:
        return error

    try:
        user_id = str(user_data.get("user_id") or "").strip() or None
        row = _get_latest_search_job(user_id)
        if not row:
            return jsonify({"success": True, "job": None})
        row = _mark_search_job_failed_if_stale(dict(row))
        raw_results = row.get("results_json")
        apify_status = None
        results_payload = []
        if isinstance(raw_results, list):
            results_payload = raw_results
        elif isinstance(raw_results, dict):
            apify_status = ((raw_results.get("_apify") or {}).get("status") if isinstance(raw_results.get("_apify"), dict) else None)
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
                    "apify_status": apify_status,
                    "error_text": row.get("error_text"),
                    "results": results_payload,
                    "created_at": row.get("created_at"),
                    "updated_at": row.get("updated_at"),
                    "completed_at": row.get("completed_at"),
                },
            }
        )
    except Exception as e:
        print(f"Error getting latest prospecting search job: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/admin/prospecting/leads", methods=["GET"])
def get_leads():
    """Get all saved leads."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            _ensure_manual_crm_tables(conn)
        finally:
            conn.close()
        filters = {
            "category": (request.args.get("category") or "").strip() or None,
            "city": (request.args.get("city") or "").strip() or None,
            "status": (request.args.get("status") or "").strip() or None,
            "group_id": (request.args.get("group_id") or "").strip() or None,
            "min_rating": float(request.args.get("min_rating")) if request.args.get("min_rating") not in {None, ""} else None,
            "max_rating": float(request.args.get("max_rating")) if request.args.get("max_rating") not in {None, ""} else None,
            "min_reviews": int(request.args.get("min_reviews")) if request.args.get("min_reviews") not in {None, ""} else None,
            "max_reviews": int(request.args.get("max_reviews")) if request.args.get("max_reviews") not in {None, ""} else None,
            "has_website": _to_bool_filter(request.args.get("has_website")),
            "has_phone": _to_bool_filter(request.args.get("has_phone")),
            "has_email": _to_bool_filter(request.args.get("has_email")),
            "has_messengers": _to_bool_filter(request.args.get("has_messengers")),
            "workstream_type": (request.args.get("workstream_type") or "").strip().lower() or None,
            "client_business_id": (request.args.get("client_business_id") or "").strip() or None,
            "action_state": (request.args.get("action_state") or "").strip().lower() or None,
        }
        compact_mode = _to_bool_query_flag(request.args.get("compact"), False)
        include_groups = _to_bool_query_flag(request.args.get("include_groups"), not compact_mode)
        include_timeline = _to_bool_query_flag(request.args.get("include_timeline"), not compact_mode)
        with DatabaseManager() as db:
            leads = db.get_all_leads_compact() if compact_mode else db.get_all_leads()
        offer_by_lead_id = {}
        sales_room_by_lead_id: dict[str, dict[str, Any]] = {}
        group_summary_by_lead_id: dict[str, list[dict[str, Any]]] = {}
        timeline_preview_by_lead_id: dict[str, dict[str, Any]] = {}
        conn = get_db_connection()
        try:
            _ensure_admin_prospecting_public_offers_table(conn)
            _ensure_manual_crm_tables(conn)
            _ensure_sales_room_tables(conn)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                """
                SELECT lead_id, slug, is_active, updated_at, page_json
                FROM adminprospectingleadpublicoffers
                """
            )
            for row in cur.fetchall() or []:
                lead_id = str(row.get("lead_id") or "").strip()
                if lead_id:
                    offer_by_lead_id[lead_id] = row
            lead_ids = [str((lead or {}).get("id") or "").strip() for lead in leads if str((lead or {}).get("id") or "").strip()]
            if lead_ids:
                cur.execute(
                    """
                    SELECT DISTINCT ON (lead_id::text)
                        lead_id::text AS lead_id,
                        status,
                        data_mode,
                        slug,
                        updated_at
                    FROM sales_rooms
                    WHERE lead_id::text = ANY(%s)
                      AND mode = %s
                    ORDER BY lead_id::text, updated_at DESC
                    """,
                    (lead_ids, SALES_ROOM_MODE_CLIENT),
                )
                for row in cur.fetchall() or []:
                    lead_id = str(row.get("lead_id") or "").strip()
                    if lead_id:
                        sales_room_by_lead_id[lead_id] = row
            if include_groups:
                group_summary_by_lead_id = _group_summary_for_lead_ids(cur, lead_ids)
            if include_timeline:
                timeline_preview_by_lead_id = _latest_timeline_preview(cur, lead_ids)
        finally:
            conn.close()
        normalized = []
        for lead in leads:
            display_lead = _normalize_lead_for_display(lead)
            if not display_lead:
                continue
            lead_id = str(display_lead.get("id") or "").strip()
            offer = offer_by_lead_id.get(str(display_lead.get("id") or "").strip())
            sales_room = sales_room_by_lead_id.get(lead_id)
            slug = str((offer or {}).get("slug") or "").strip()
            if offer and bool(offer.get("is_active")) and slug:
                page_json = offer.get("page_json") if isinstance(offer.get("page_json"), dict) else {}
                primary_language, enabled_languages = _normalize_public_audit_languages(
                    page_json.get("preferred_language"),
                    page_json.get("enabled_languages"),
                )
                display_lead["public_audit_slug"] = slug
                display_lead["public_audit_url"] = _make_public_offer_url(slug)
                display_lead["has_public_audit"] = True
                display_lead["public_audit_updated_at"] = offer.get("updated_at")
                display_lead["preferred_language"] = primary_language
                display_lead["enabled_languages"] = enabled_languages
            if sales_room:
                sales_room_slug = str(sales_room.get("slug") or "").strip()
                display_lead["sales_room_status"] = sales_room.get("status")
                display_lead["sales_room_data_mode"] = sales_room.get("data_mode")
                display_lead["sales_room_updated_at"] = sales_room.get("updated_at")
                if sales_room_slug:
                    display_lead["sales_room_url"] = _make_sales_room_url(sales_room_slug)
            if include_groups:
                display_lead["groups"] = group_summary_by_lead_id.get(lead_id, [])
                display_lead["group_count"] = len(display_lead["groups"])
            else:
                display_lead["groups"] = []
                display_lead["group_count"] = 0
            if include_timeline:
                display_lead["timeline_preview"] = timeline_preview_by_lead_id.get(lead_id)
            normalized.append(display_lead)
        from services.lead_workstream_service import attach_workstreams

        workstream_conn = get_db_connection()
        try:
            normalized = attach_workstreams(workstream_conn, normalized)
        finally:
            workstream_conn.close()
        client_options_by_id = {}
        for lead in normalized:
            for workstream in lead.get("workstreams") or []:
                if workstream.get("workstream_type") != "client_partnership":
                    continue
                option_id = str(workstream.get("client_business_id") or "").strip()
                option_name = str(workstream.get("client_business_name") or "").strip()
                if option_id and option_name:
                    client_options_by_id[option_id] = {"id": option_id, "name": option_name}
        client_options = sorted(
            client_options_by_id.values(),
            key=lambda item: str(item.get("name") or "").casefold(),
        )
        filtered = [lead for lead in normalized if _lead_matches_filters(lead, filters)]
        workstream_type = str(filters.get("workstream_type") or "").strip().lower()
        if workstream_type:
            filtered = [
                lead for lead in filtered
                if any(
                    str(item.get("workstream_type") or "").strip().lower() == workstream_type
                    for item in (lead.get("workstreams") or [])
                )
            ]
        client_business_id = str(filters.get("client_business_id") or "").strip()
        if client_business_id:
            filtered = [
                lead for lead in filtered
                if any(
                    str(item.get("client_business_id") or "").strip() == client_business_id
                    for item in (lead.get("workstreams") or [])
                )
            ]
        action_state = str(filters.get("action_state") or "").strip().lower()
        if action_state:
            filtered = [
                lead for lead in filtered
                if any(
                    str((item.get("next_action") or {}).get("code") or "").strip().lower() == action_state
                    for item in (lead.get("workstreams") or [])
                )
            ]
        group_id = str(filters.get("group_id") or "").strip()
        if group_id:
            filtered = [
                lead for lead in filtered
                if any(str(group.get("id") or "") == group_id for group in (lead.get("groups") or []))
            ]
        return jsonify(
            _to_json_compatible(
                {
                    "leads": filtered,
                    "count": len(filtered),
                    "client_options": client_options,
                }
            )
        )
    except Exception as e:
        print(f"Error getting leads: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/admin/prospecting/save", methods=["POST"])
def save_lead():
    """Save a lead to database."""
    user_data, error = _require_superadmin()
    if error:
        return error

    try:
        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            _ensure_manual_crm_tables(conn)
        finally:
            conn.close()
        data = request.get_json(silent=True) or {}
        lead_data = data.get("lead")
        workstream_type = normalize_workstream_type(data.get("workstream_type")) or LOCALOS_SALES
        client_business_id = str(data.get("client_business_id") or "").strip() or None

        if not lead_data:
            return jsonify({"error": "Lead data is required"}), 400
        if workstream_type == CLIENT_PARTNERSHIP and not client_business_id:
            return jsonify({"error": "client_business_id is required for partner leads"}), 400

        lead_data.setdefault("source", "apify_yandex")
        lead_data.setdefault("source_external_id", lead_data.get("google_id"))
        lead_data.setdefault("status", "new")
        lead_data.setdefault("pipeline_status", PIPELINE_UNPROCESSED)

        with DatabaseManager() as db:
            lead_id = db.save_lead(lead_data)

        conn = get_db_connection()
        try:
            _ensure_manual_crm_tables(conn)
            cur = conn.cursor()
            workstream = create_workstream(
                conn,
                lead_id=lead_id,
                workstream_type=workstream_type,
                client_business_id=client_business_id,
                actor_id=str(user_data.get("user_id") or "") or None,
            )
            _record_lead_timeline_event(
                cur,
                lead_id=lead_id,
                workstream_id=str(workstream.get("id") or ""),
                event_type="lead_created",
                comment="Lead added to intake",
                payload={
                    "source": lead_data.get("source"),
                    "pipeline_status": lead_data.get("pipeline_status") or PIPELINE_UNPROCESSED,
                    "workstream_type": workstream_type,
                    "client_business_id": client_business_id,
                },
            )
            conn.commit()
        finally:
            conn.close()

        return jsonify({
            "success": True,
            "lead_id": lead_id,
            "workstream": _to_json_compatible(workstream),
            "reused": bool(workstream.get("reused")),
        })
    except Exception as e:
        print(f"Error saving lead: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/admin/prospecting/import", methods=["POST"])
def import_leads():
    """Bulk import leads from external JSON payload (e.g. manual Apify export)."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        data = request.get_json(silent=True)
        if isinstance(data, list):
            raw_items = data
        else:
            payload = data or {}
            raw_items = (
                payload.get("items")
                or payload.get("results")
                or payload.get("leads")
                or []
            )

        if not isinstance(raw_items, list) or not raw_items:
            return jsonify({"error": "Items array is required"}), 400

        service = ProspectingService()
        normalized = service.normalize_results(raw_items)
        if not normalized:
            return jsonify({"error": "No valid lead items to import"}), 400

        imported_ids: list[str] = []
        with DatabaseManager() as db:
            for lead_data in normalized:
                lead_data.setdefault("source", "external_import")
                lead_data.setdefault("status", "new")
                lead_data.setdefault("source_external_id", lead_data.get("source_external_id") or lead_data.get("google_id"))
                imported_ids.append(db.save_lead(lead_data))

        return jsonify({
            "success": True,
            "imported_count": len(imported_ids),
            "skipped_count": max(0, len(raw_items) - len(normalized)),
            "lead_ids": imported_ids,
        })
    except Exception as e:
        print(f"Error importing leads: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/partnership/leads/import-links", methods=["POST"])
def partnership_import_links():
    """User-level import of partnership candidates via direct map links."""
    user_data, error = _require_auth()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        links = data.get("links") or []
        requested_business_id = str(data.get("business_id") or "").strip() or None
        default_city = str(data.get("city") or "").strip()
        default_category = str(data.get("category") or "").strip()
        if not isinstance(links, list) or not links:
            return jsonify({"error": "links array is required"}), 400

        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            _ensure_sales_room_tables(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
            schema_flags = _get_partnership_schema_flags(cur)

            imported_ids: list[str] = []
            skipped = 0
            for raw_link in links:
                source_url = str(raw_link or "").strip()
                if not source_url:
                    continue
                lead_id, created = _insert_partnership_lead_if_new(
                    cur,
                    business_id=business_id,
                    created_by=user_data["user_id"],
                    source_url=source_url,
                    name="Новый партнёр",
                    address=None,
                    city=default_city or None,
                    category=default_category or None,
                    source="manual_link",
                    source_kind="manual_link",
                    source_provider="localos_manual",
                    external_source_id=_extract_yandex_org_id_from_url(source_url) or None,
                )
                if not created:
                    skipped += 1
                    continue
                if lead_id:
                    imported_ids.append(lead_id)
            conn.commit()
        finally:
            conn.close()

        return jsonify(
            {
                "success": True,
                "imported_count": len(imported_ids),
                "skipped_count": skipped,
                "lead_ids": imported_ids,
            }
        )
    except Exception as e:
        print(f"Error importing partnership links: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/partnership/partners/import", methods=["POST"])
def partnership_import_partner_cards():
    """Import source-company partner cards before maps enrichment."""
    user_data, error = _require_auth()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        requested_business_id = str(data.get("business_id") or "").strip() or None
        source_company_id = str(data.get("source_company_id") or "").strip() or None
        source_company_name = str(data.get("source_company_name") or "").strip()
        items = data.get("items") or data.get("partners") or []
        if not source_company_name:
            return jsonify({"error": "source_company_name is required"}), 400
        if not isinstance(items, list) or not items:
            return jsonify({"error": "items must be a non-empty list"}), 400

        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            _ensure_manual_crm_tables(conn)
            _ensure_partnership_partner_cards_table(conn)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403

            imported: list[dict[str, Any]] = []
            updated_count = 0
            skipped_count = 0
            for raw_item in items:
                if not isinstance(raw_item, dict):
                    skipped_count += 1
                    continue
                partner_name = str(raw_item.get("partner_name") or raw_item.get("name") or "").strip()
                if not partner_name:
                    skipped_count += 1
                    continue
                partner_address = str(raw_item.get("partner_address") or raw_item.get("address") or "").strip() or None
                partner_city = str(raw_item.get("partner_city") or raw_item.get("city") or data.get("default_city") or "").strip() or None
                partner_category = str(raw_item.get("partner_category") or raw_item.get("category") or "").strip() or None
                partner_kind = _normalize_partner_kind(
                    raw_item.get("partner_kind") or raw_item.get("kind"),
                    partner_name,
                    partner_category,
                    raw_item,
                )
                yandex_maps_url = normalize_map_url(str(raw_item.get("yandex_maps_url") or raw_item.get("maps_url") or raw_item.get("source_url") or "").strip())
                match_status = PARTNER_MATCH_MANUAL_CONFIRMED if yandex_maps_url else PARTNER_MATCH_NOT_STARTED
                if partner_kind == PARTNER_KIND_RESIDENTIAL_COMPLEX:
                    match_status = PARTNER_MATCH_SKIPPED_RESIDENTIAL

                cur.execute(
                    """
                    SELECT *
                    FROM partnership_partner_cards
                    WHERE business_id = NULLIF(%s, '')::uuid
                      AND LOWER(source_company_name) = LOWER(%s)
                      AND LOWER(partner_name) = LOWER(%s)
                      AND COALESCE(LOWER(partner_address), '') = COALESCE(LOWER(%s), '')
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    (business_id, source_company_name, partner_name, partner_address or ""),
                )
                existing = _row_to_dict(cur.fetchone())
                if existing:
                    cur.execute(
                        """
                        UPDATE partnership_partner_cards
                        SET source_company_id = COALESCE(%s, source_company_id),
                            partner_city = COALESCE(%s, partner_city),
                            partner_category = COALESCE(%s, partner_category),
                            partner_kind = %s,
                            yandex_maps_url = COALESCE(NULLIF(%s, ''), yandex_maps_url),
                            yandex_maps_match_status = CASE
                                WHEN %s <> '' THEN %s
                                WHEN %s = %s THEN %s
                                ELSE yandex_maps_match_status
                            END,
                            lead_sync_status = CASE
                                WHEN %s = %s THEN %s
                                ELSE lead_sync_status
                            END,
                            raw_payload_json = %s,
                            updated_at = NOW()
                        WHERE id = %s
                        RETURNING *
                        """,
                        (
                            source_company_id,
                            partner_city,
                            partner_category,
                            partner_kind,
                            yandex_maps_url,
                            yandex_maps_url,
                            PARTNER_MATCH_MANUAL_CONFIRMED,
                            partner_kind,
                            PARTNER_KIND_RESIDENTIAL_COMPLEX,
                            PARTNER_MATCH_SKIPPED_RESIDENTIAL,
                            partner_kind,
                            PARTNER_KIND_RESIDENTIAL_COMPLEX,
                            PARTNER_LEAD_SKIPPED,
                            Json(_to_json_compatible(raw_item)),
                            existing.get("id"),
                        ),
                    )
                    updated = _row_to_dict(cur.fetchone())
                    imported.append(_normalize_partner_card_for_response(updated))
                    updated_count += 1
                    continue

                partner_id = str(uuid.uuid4())
                cur.execute(
                    """
                    INSERT INTO partnership_partner_cards (
                        id, business_id, source_company_id, source_company_name,
                        partner_name, partner_address, partner_city, partner_category, partner_kind,
                        yandex_maps_url, yandex_maps_match_status, yandex_maps_match_confidence,
                        lead_sync_status,
                        raw_payload_json, created_by, created_at, updated_at
                    ) VALUES (
                        %s, NULLIF(%s, '')::uuid, %s, %s,
                        %s, %s, %s, %s, %s,
                        NULLIF(%s, ''), %s, %s,
                        %s,
                        %s, NULLIF(%s, '')::uuid, NOW(), NOW()
                    )
                    RETURNING *
                    """,
                    (
                        partner_id,
                        business_id,
                        source_company_id,
                        source_company_name,
                        partner_name,
                        partner_address,
                        partner_city,
                        partner_category,
                        partner_kind,
                        yandex_maps_url,
                        match_status,
                        1.0 if yandex_maps_url else None,
                        PARTNER_LEAD_SKIPPED if partner_kind == PARTNER_KIND_RESIDENTIAL_COMPLEX else PARTNER_LEAD_NOT_SYNCED,
                        Json(_to_json_compatible(raw_item)),
                        str(user_data.get("user_id") or ""),
                    ),
                )
                imported.append(_normalize_partner_card_for_response(_row_to_dict(cur.fetchone())))
            conn.commit()
        finally:
            conn.close()
        return jsonify(
            {
                "success": True,
                "count": len(imported),
                "updated_count": updated_count,
                "skipped_count": skipped_count,
                "items": imported,
            }
        )
    except Exception:
        err = sys.exc_info()[1]
        print(f"Error importing partner cards: {err}")
        return jsonify({"error": str(err)}), 500

@admin_prospecting_bp.route("/api/partnership/partners", methods=["GET"])
def partnership_list_partner_cards():
    """List source-company partner cards with enrichment state."""
    user_data, error = _require_auth()
    if error:
        return error

    try:
        requested_business_id = str(request.args.get("business_id") or "").strip() or None
        source_company_name = str(request.args.get("source_company_name") or "").strip()
        match_status = str(request.args.get("match_status") or "").strip()
        limit = max(1, min(int(request.args.get("limit") or 200), 500))
        offset = max(0, int(request.args.get("offset") or 0))
        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            _ensure_partnership_partner_cards_table(conn)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
            where_sql = ["p.business_id = NULLIF(%s, '')::uuid"]
            params: list[Any] = [business_id]
            if source_company_name:
                where_sql.append("LOWER(p.source_company_name) = LOWER(%s)")
                params.append(source_company_name)
            if match_status:
                where_sql.append("p.yandex_maps_match_status = %s")
                params.append(match_status)
            cur.execute(
                f"""
                SELECT
                    p.*,
                    l.name AS lead_name,
                    l.status AS lead_status,
                    l.pipeline_status AS lead_pipeline_status,
                    l.partnership_stage AS lead_partnership_stage
                FROM partnership_partner_cards p
                LEFT JOIN prospectingleads l ON l.id = p.lead_id
                WHERE {' AND '.join(where_sql)}
                ORDER BY p.updated_at DESC, p.created_at DESC
                LIMIT %s OFFSET %s
                """,
                (*params, limit, offset),
            )
            rows = [_normalize_partner_card_for_response(_row_to_dict(row)) for row in cur.fetchall() or []]
        finally:
            conn.close()
        return jsonify({"success": True, "count": len(rows), "items": rows})
    except Exception:
        err = sys.exc_info()[1]
        print(f"Error listing partner cards: {err}")
        return jsonify({"error": str(err)}), 500

@admin_prospecting_bp.route("/api/partnership/partners/<string:partner_id>/find-yandex", methods=["POST"])
def partnership_find_partner_yandex(partner_id):
    """Find and optionally auto-select a Yandex Maps URL for a partner card."""
    user_data, error = _require_auth()
    if error:
        return error
    try:
        data = request.get_json(silent=True) or {}
        requested_business_id = str(data.get("business_id") or "").strip() or None
        force = bool(data.get("force"))
        conn = get_db_connection()
        try:
            _ensure_partnership_partner_cards_table(conn)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
            card = _load_partner_card(cur, partner_id=partner_id, business_id=business_id)
            if not card:
                return jsonify({"error": "Partner card not found"}), 404
            if _is_residential_partner_card(card):
                cur.execute(
                    """
                    UPDATE partnership_partner_cards
                    SET yandex_maps_match_status = %s,
                        lead_sync_status = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING *
                    """,
                    (PARTNER_MATCH_SKIPPED_RESIDENTIAL, PARTNER_LEAD_SKIPPED, card.get("id")),
                )
                updated = _normalize_partner_card_for_response(_row_to_dict(cur.fetchone()))
                conn.commit()
                return jsonify({"success": True, "status": PARTNER_MATCH_SKIPPED_RESIDENTIAL, "card": updated, "candidates": []})
            if str(card.get("yandex_maps_url") or "").strip() and str(card.get("yandex_maps_match_status") or "") == PARTNER_MATCH_MANUAL_CONFIRMED and not force:
                return jsonify({"success": True, "status": PARTNER_MATCH_MANUAL_CONFIRMED, "card": _normalize_partner_card_for_response(card), "candidates": []})

            candidates, search_error = _find_yandex_candidates_for_partner_card(card)
            status = PARTNER_MATCH_NOT_FOUND
            selected_url = None
            selected_confidence = None
            if candidates:
                top = candidates[0]
                top_confidence = float(top.get("confidence") or 0)
                second_confidence = float(candidates[1].get("confidence") or 0) if len(candidates) > 1 else 0.0
                if top_confidence >= 0.83 and (top_confidence - second_confidence) >= 0.08:
                    status = PARTNER_MATCH_FOUND
                    selected_url = str(top.get("yandex_maps_url") or "").strip() or None
                    selected_confidence = top_confidence
                else:
                    status = PARTNER_MATCH_AMBIGUOUS
                    selected_confidence = top_confidence
            elif search_error:
                status = PARTNER_MATCH_NOT_FOUND

            cur.execute(
                """
                UPDATE partnership_partner_cards
                SET yandex_maps_url = COALESCE(%s, yandex_maps_url),
                    yandex_maps_match_status = %s,
                    yandex_maps_match_confidence = %s,
                    yandex_maps_candidates_json = %s,
                    lead_sync_error = %s,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING *
                """,
                (
                    selected_url,
                    status,
                    selected_confidence,
                    Json(_to_json_compatible(candidates)),
                    search_error,
                    card.get("id"),
                ),
            )
            updated = _normalize_partner_card_for_response(_row_to_dict(cur.fetchone()))
            conn.commit()
        finally:
            conn.close()
        return jsonify({"success": True, "status": status, "card": updated, "candidates": candidates, "error": search_error})
    except Exception:
        err = sys.exc_info()[1]
        print(f"Error finding partner yandex link: {err}")
        return jsonify({"error": str(err)}), 500

@admin_prospecting_bp.route("/api/partnership/partners/<string:partner_id>/confirm-yandex-link", methods=["POST"])
def partnership_confirm_partner_yandex(partner_id):
    """Manually confirm or replace the Yandex Maps URL for a partner card."""
    user_data, error = _require_auth()
    if error:
        return error
    try:
        data = request.get_json(silent=True) or {}
        requested_business_id = str(data.get("business_id") or "").strip() or None
        yandex_maps_url = normalize_map_url(str(data.get("yandex_maps_url") or data.get("source_url") or "").strip())
        if not yandex_maps_url:
            return jsonify({"error": "yandex_maps_url is required"}), 400
        conn = get_db_connection()
        try:
            _ensure_partnership_partner_cards_table(conn)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
            card = _load_partner_card(cur, partner_id=partner_id, business_id=business_id)
            if not card:
                return jsonify({"error": "Partner card not found"}), 404
            cur.execute(
                """
                UPDATE partnership_partner_cards
                SET yandex_maps_url = %s,
                    yandex_maps_match_status = %s,
                    yandex_maps_match_confidence = %s,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING *
                """,
                (yandex_maps_url, PARTNER_MATCH_MANUAL_CONFIRMED, 1.0, card.get("id")),
            )
            updated = _normalize_partner_card_for_response(_row_to_dict(cur.fetchone()))
            conn.commit()
        finally:
            conn.close()
        return jsonify({"success": True, "card": updated})
    except Exception:
        err = sys.exc_info()[1]
        print(f"Error confirming partner yandex link: {err}")
        return jsonify({"error": str(err)}), 500

@admin_prospecting_bp.route("/api/partnership/partners/<string:partner_id>/sync-lead", methods=["POST"])
def partnership_sync_partner_lead(partner_id):
    """Sync a partner card into prospectingleads candidate stage."""
    user_data, error = _require_auth()
    if error:
        return error
    try:
        data = request.get_json(silent=True) or {}
        requested_business_id = str(data.get("business_id") or "").strip() or None
        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            _ensure_manual_crm_tables(conn)
            _ensure_partnership_partner_cards_table(conn)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
            card = _load_partner_card(cur, partner_id=partner_id, business_id=business_id)
            if not card:
                return jsonify({"error": "Partner card not found"}), 404
            lead_id, created, sync_error = _sync_partner_card_to_lead(cur, card=card, user_id=str(user_data.get("user_id") or ""))
            if sync_error and sync_error != "skipped_residential_complex":
                cur.execute(
                    """
                    UPDATE partnership_partner_cards
                    SET lead_sync_status = %s,
                        lead_sync_error = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING *
                    """,
                    (PARTNER_LEAD_FAILED, sync_error, card.get("id")),
                )
                updated = _normalize_partner_card_for_response(_row_to_dict(cur.fetchone()))
                conn.commit()
                return jsonify({"success": False, "error": sync_error, "card": updated}), 400
            cur.execute("SELECT * FROM partnership_partner_cards WHERE id = %s", (card.get("id"),))
            updated = _normalize_partner_card_for_response(_row_to_dict(cur.fetchone()))
            conn.commit()
        finally:
            conn.close()
        return jsonify({"success": True, "lead_id": lead_id, "created": created, "card": updated})
    except Exception:
        err = sys.exc_info()[1]
        print(f"Error syncing partner card to lead: {err}")
        return jsonify({"error": str(err)}), 500

@admin_prospecting_bp.route("/api/partnership/partners/<string:partner_id>/parse", methods=["POST"])
def partnership_parse_partner_card(partner_id):
    """Create or reuse a parse task for a partner card's map URL."""
    user_data, error = _require_auth()
    if error:
        return error
    try:
        data = request.get_json(silent=True) or {}
        requested_business_id = str(data.get("business_id") or "").strip() or None
        conn = get_db_connection()
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
        finally:
            conn.close()
        result = _process_partner_card_parse(
            partner_id=partner_id,
            business_id=business_id,
            user_id=str(user_data.get("user_id") or ""),
        )
        status_code = int(result.pop("status_code", 200) or 200)
        return jsonify(result), status_code
    except Exception:
        err = sys.exc_info()[1]
        print(f"Error parsing partner card: {err}")
        return jsonify({"error": str(err)}), 500

@admin_prospecting_bp.route("/api/partnership/partners/<string:partner_id>/audit", methods=["POST"])
def partnership_audit_partner_card(partner_id):
    """Create a public audit for a partner card and store the URL on the card."""
    user_data, error = _require_auth()
    if error:
        return error
    try:
        data = request.get_json(silent=True) or {}
        requested_business_id = str(data.get("business_id") or "").strip() or None
        requested_language = str(data.get("primary_language") or data.get("language") or "ru").strip().lower() or "ru"
        primary_language, _enabled_languages = _normalize_public_audit_languages(requested_language, [requested_language])
        conn = get_db_connection()
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
        finally:
            conn.close()
        result = _process_partner_card_audit(
            partner_id=partner_id,
            business_id=business_id,
            user_id=str(user_data.get("user_id") or ""),
            primary_language=primary_language,
        )
        status_code = int(result.pop("status_code", 200) or 200)
        return jsonify(result), status_code
    except Exception:
        err = sys.exc_info()[1]
        print(f"Error auditing partner card: {err}")
        return jsonify({"error": str(err)}), 500
