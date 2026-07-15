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

def _add_business_days(start_at: datetime | date | None, business_days: int) -> datetime:
    base_date = start_at.date() if isinstance(start_at, datetime) else start_at
    if not isinstance(base_date, date):
        base_date = datetime.utcnow().date()
    current = base_date
    remaining = max(0, business_days)
    while remaining > 0:
        current = current + timedelta(days=1)
        if current.isoweekday() <= 5:
            remaining -= 1
    return datetime.combine(current, datetime.min.time()).replace(tzinfo=timezone.utc)

def _public_sales_room_client_key() -> str:
    forwarded_for = str(request.headers.get("X-Forwarded-For") or "").split(",", 1)[0].strip()
    real_ip = str(request.headers.get("X-Real-IP") or "").strip()
    remote_addr = str(request.remote_addr or "").strip()
    return (forwarded_for or real_ip or remote_addr or "unknown")[:80]

def _check_public_sales_room_rate_limit(action: str, slug: str, limit: int, window_sec: int):
    if limit <= 0 or window_sec <= 0:
        return None
    now = time.monotonic()
    window_start = now - window_sec
    key = f"sales-room:{action}:{slug}:{_public_sales_room_client_key()}"
    with _public_sales_room_rate_lock:
        entries = [ts for ts in _public_sales_room_rate_buckets.get(key, []) if ts >= window_start]
        if len(entries) >= limit:
            retry_after = max(1, int(window_sec - (now - min(entries))))
            response = jsonify(
                {
                    "error": "rate_limited",
                    "reason": "public_sales_room_write_limit",
                    "retry_after_seconds": retry_after,
                }
            )
            response.headers["Retry-After"] = str(retry_after)
            return response, 429
        entries.append(now)
        _public_sales_room_rate_buckets[key] = entries
    return None

def _next_followup_at(anchor_at: datetime | date | None = None) -> datetime:
    return _add_business_days(anchor_at or datetime.utcnow(), 3)

def _normalize_learning_intent(raw_intent: str | None) -> str:
    value = str(raw_intent or "client_outreach").strip().lower()
    allowed = {"client_outreach", "partnership_outreach", "operations"}
    return value if value in allowed else "client_outreach"

def _to_json_compatible(value: Any) -> Any:
    def convert(item: Any) -> Any:
        if isinstance(item, datetime):
            return item.isoformat()
        if isinstance(item, date):
            return item.isoformat()
        if isinstance(item, dict):
            return {str(key): convert(inner) for key, inner in item.items()}
        if isinstance(item, list):
            return [convert(inner) for inner in item]
        if isinstance(item, tuple):
            return [convert(inner) for inner in item]
        return item

    return convert(value)

def _normalize_public_audit_languages(primary_language: str | None, enabled_languages: Any) -> tuple[str, list[str]]:
    requested_primary = str(primary_language or "").strip().lower()
    primary = requested_primary if requested_primary in PUBLIC_AUDIT_LANGUAGES else "en"

    normalized_enabled: list[str] = []
    if isinstance(enabled_languages, (list, tuple)):
        for item in enabled_languages:
            value = str(item or "").strip().lower()
            if value in PUBLIC_AUDIT_LANGUAGES and value not in normalized_enabled:
                normalized_enabled.append(value)

    if primary not in normalized_enabled:
        normalized_enabled.insert(0, primary)

    if not normalized_enabled:
        normalized_enabled = [primary]

    return primary, normalized_enabled

def _resolve_lead_intent(cur, lead_id: str) -> str:
    try:
        cur.execute("SELECT intent FROM prospectingleads WHERE id = %s", (lead_id,))
        row = cur.fetchone()
        if not row:
            return "client_outreach"
        if hasattr(row, "get"):
            return _normalize_learning_intent(row.get("intent"))
        if isinstance(row, (tuple, list)):
            return _normalize_learning_intent(row[0] if row else None)
    except Exception:
        pass
    return "client_outreach"

def _remaining_daily_outreach_slots(conn) -> int:
    """Hard-cap daily outreach slots based on queued items for today's batches."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM outreachsendqueue q
        JOIN outreachsendbatches b ON b.id = q.batch_id
        WHERE b.batch_date = CURRENT_DATE
        """
    )
    row = cur.fetchone()
    if not row:
        used = 0
    elif hasattr(row, "get"):
        used = int((row.get("cnt") or 0))
    else:
        used = int((row[0] if row else 0) or 0)
    return max(0, MAX_DAILY_OUTREACH_BATCH - used)

def _normalize_scalar_text(value: Any) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None

def _extract_max_contact(lead: dict[str, Any] | None) -> str | None:
    if not lead:
        return None
    website = str(lead.get("website") or "").strip()
    if website and ("max.ru" in website.lower() or "web.max.ru" in website.lower()):
        return website
    raw_links = lead.get("messenger_links_json")
    parsed_links: list[Any]
    if isinstance(raw_links, list):
        parsed_links = raw_links
    elif isinstance(raw_links, str) and raw_links.strip():
        try:
            parsed = json.loads(raw_links)
            parsed_links = parsed if isinstance(parsed, list) else [raw_links]
        except Exception:
            parsed_links = [raw_links]
    else:
        parsed_links = []
    for item in parsed_links:
        candidate = str(item or "").strip()
        if candidate and ("max.ru" in candidate.lower() or "web.max.ru" in candidate.lower()):
            return candidate
    return None

def _lead_has_channel_contact(lead: dict[str, Any] | None, channel: str | None) -> bool:
    normalized_channel = str(channel or "").strip().lower()
    if not normalized_channel:
        return False
    if normalized_channel == "manual":
        return True
    if not lead:
        return False
    if normalized_channel == "telegram":
        return _normalize_scalar_text(lead.get("telegram_url")) is not None
    if normalized_channel == "whatsapp":
        return _normalize_scalar_text(lead.get("whatsapp_url")) is not None
    if normalized_channel == "max":
        return _extract_max_contact(lead) is not None
    if normalized_channel == "email":
        return _normalize_scalar_text(lead.get("email")) is not None
    return False

def _outreach_channel_contact_error(channel: str | None) -> str:
    normalized_channel = str(channel or "").strip().lower()
    if normalized_channel == "telegram":
        return "Telegram channel cannot be selected without telegram_url"
    if normalized_channel == "whatsapp":
        return "WhatsApp channel cannot be selected without whatsapp_url"
    if normalized_channel == "max":
        return "MAX channel cannot be selected without max.ru contact"
    if normalized_channel == "email":
        return "Email channel cannot be selected without email"
    return "Selected outreach channel has no matching contact"

def _resolve_manual_outreach_recipient(lead: dict[str, Any] | None, channel: str | None) -> tuple[str | None, str | None]:
    normalized_channel = str(channel or "").strip().lower()
    if normalized_channel == "telegram":
        recipient = _resolve_telegram_app_recipient(lead or {})
        if recipient:
            return recipient.get("recipient_kind"), recipient.get("recipient_value")
        return None, None
    if normalized_channel == "whatsapp":
        phone = normalize_phone((lead or {}).get("whatsapp_url") or (lead or {}).get("phone"))
        return ("phone", phone) if phone else (None, None)
    if normalized_channel == "email":
        email = _normalize_scalar_text((lead or {}).get("email"))
        return ("email", email) if email else (None, None)
    if normalized_channel == "max":
        if _lead_has_channel_contact(lead or {}, "max"):
            return "max", "manual"
        return None, None
    if normalized_channel == "manual":
        return "manual", None
    return None, None

def _outreach_retry_delay_for_attempt(attempt_no: int) -> timedelta | None:
    # attempt_no считается уже после инкремента:
    # 1 => первый fail после D0, retry через 1 день
    # 2 => второй fail, retry через 2 дня (D3 относительно D0)
    if attempt_no <= 0:
        return None
    idx = attempt_no - 1
    if idx < len(OUTREACH_RETRY_DELAY_DAYS):
        return timedelta(days=int(OUTREACH_RETRY_DELAY_DAYS[idx]))
    return None

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

def _require_auth():
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None, _auth_error("Authorization required", 401)

    token = auth_header.split(" ", 1)[1]
    user_data = verify_session(token)
    if not user_data:
        return None, _auth_error("Invalid token", 401)
    return user_data, None

def _optional_auth() -> dict[str, Any] | None:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ", 1)[1]
    user_data = verify_session(token)
    return user_data if isinstance(user_data, dict) else None

def _resolve_business_for_user(cur, user_data: dict, requested_business_id: str | None) -> str | None:
    is_superadmin = bool(user_data.get("is_superadmin"))
    user_id = str(user_data.get("user_id") or "")
    business_id = (requested_business_id or "").strip() or get_business_id_from_user(user_id, None)
    if not business_id:
        return None
    if is_superadmin:
        return business_id
    cur.execute(
        """
        SELECT id
        FROM businesses
        WHERE id = %s AND owner_id = %s
        LIMIT 1
        """,
        (business_id, user_id),
    )
    row = cur.fetchone()
    return (row["id"] if hasattr(row, "get") else row[0]) if row else None

def _ensure_partnership_columns(conn) -> None:
    cur = conn.cursor()
    cur.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS intent TEXT DEFAULT 'client_outreach'")
    cur.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS partnership_stage TEXT DEFAULT 'imported'")
    cur.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS pilot_cohort TEXT DEFAULT 'backlog'")
    cur.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS business_id UUID")
    cur.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS parse_business_id UUID")
    cur.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS created_by UUID")
    cur.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS source_kind TEXT")
    cur.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS source_provider TEXT")
    cur.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS external_place_id TEXT")
    cur.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS external_source_id TEXT")
    cur.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS dedupe_key TEXT")
    cur.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS lat DOUBLE PRECISION")
    cur.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS lon DOUBLE PRECISION")
    cur.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS search_payload_json JSONB")
    cur.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS enrich_payload_json JSONB")
    cur.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS matched_sources_json JSONB")
    cur.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS deferred_reason TEXT")
    cur.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS deferred_until DATE")
    cur.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS preferred_language TEXT")
    cur.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS enabled_languages JSONB")
    cur.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS partner_source_company_id TEXT")
    cur.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS partner_source_company_name TEXT")
    cur.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS partner_source_partner_id TEXT")
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_prospectingleads_intent_stage
        ON prospectingleads (intent, partnership_stage)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_prospectingleads_intent_external_source
        ON prospectingleads (business_id, intent, external_source_id)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_prospectingleads_intent_phone
        ON prospectingleads (business_id, intent, phone)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_prospectingleads_partner_source
        ON prospectingleads (business_id, intent, partner_source_company_name)
        """
    )
    # DDL в PostgreSQL транзакционный; без commit изменения могут откатиться при закрытии conn.
    conn.commit()

def _ensure_manual_crm_tables(conn) -> None:
    cur = conn.cursor()
    cur.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS pipeline_status TEXT NOT NULL DEFAULT 'unprocessed'")
    cur.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS disqualification_reason TEXT")
    cur.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS disqualification_comment TEXT")
    cur.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS postponed_comment TEXT")
    cur.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS next_action_at TIMESTAMPTZ")
    cur.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS last_contact_at TIMESTAMPTZ")
    cur.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS last_contact_channel TEXT")
    cur.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS last_contact_comment TEXT")
    cur.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS qualified_at TIMESTAMPTZ")
    cur.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS qualified_by TEXT")
    cur.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS last_manual_action_at TIMESTAMPTZ")
    cur.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS last_manual_action_by TEXT")
    cur.execute(
        """
        UPDATE prospectingleads
        SET pipeline_status = CASE
            WHEN COALESCE(status, 'new') = 'new' THEN %s
            WHEN COALESCE(status, '') = 'deferred' THEN %s
            WHEN COALESCE(status, '') IN ('shortlist_rejected', 'rejected') THEN %s
            WHEN COALESCE(status, '') = 'sent' THEN %s
            WHEN COALESCE(status, '') = 'delivered' THEN %s
            WHEN COALESCE(status, '') = 'responded' THEN %s
            WHEN COALESCE(status, '') = 'second_message_sent' THEN %s
            WHEN COALESCE(status, '') IN ('qualified', 'converted') THEN %s
            WHEN COALESCE(status, '') = 'closed' THEN %s
            ELSE %s
        END
        WHERE COALESCE(pipeline_status, '') = ''
           OR (COALESCE(pipeline_status, '') = 'unprocessed' AND COALESCE(status, 'new') <> 'new')
        """,
        (
            PIPELINE_UNPROCESSED,
            PIPELINE_POSTPONED,
            PIPELINE_NOT_RELEVANT,
            PIPELINE_CONTACTED,
            PIPELINE_CONTACTED,
            PIPELINE_REPLIED,
            PIPELINE_SECOND_MESSAGE_SENT,
            PIPELINE_CONVERTED,
            PIPELINE_CLOSED_LOST,
            PIPELINE_IN_PROGRESS,
        ),
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS lead_groups (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            channel_hint TEXT,
            city_hint TEXT,
            created_by TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS lead_group_items (
            id TEXT PRIMARY KEY,
            group_id TEXT NOT NULL REFERENCES lead_groups(id) ON DELETE CASCADE,
            lead_id TEXT NOT NULL REFERENCES prospectingleads(id) ON DELETE CASCADE,
            added_by TEXT,
            added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (group_id, lead_id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS lead_timeline_events (
            id TEXT PRIMARY KEY,
            lead_id TEXT NOT NULL REFERENCES prospectingleads(id) ON DELETE CASCADE,
            event_type TEXT NOT NULL,
            actor_id TEXT,
            comment TEXT,
            payload_json JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_prospectingleads_pipeline_status ON prospectingleads(pipeline_status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_prospectingleads_next_action_at ON prospectingleads(next_action_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_prospectingleads_last_contact_at ON prospectingleads(last_contact_at DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_lead_groups_status ON lead_groups(status, created_at DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_lead_group_items_group_id ON lead_group_items(group_id, added_at DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_lead_group_items_lead_id ON lead_group_items(lead_id, added_at DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_lead_timeline_events_lead_created ON lead_timeline_events(lead_id, created_at DESC)")
    conn.commit()

def _ensure_partnership_partner_cards_table(conn) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS partnership_partner_cards (
            id UUID PRIMARY KEY,
            business_id UUID NOT NULL,
            source_company_id TEXT,
            source_company_name TEXT NOT NULL,
            partner_name TEXT NOT NULL,
            partner_address TEXT,
            partner_city TEXT,
            partner_category TEXT,
            partner_kind TEXT NOT NULL DEFAULT 'business',
            yandex_maps_url TEXT,
            yandex_maps_match_status TEXT NOT NULL DEFAULT 'not_started',
            yandex_maps_match_confidence DOUBLE PRECISION,
            yandex_maps_candidates_json JSONB,
            parse_business_id UUID,
            audit_public_url TEXT,
            audit_slug TEXT,
            audit_status TEXT NOT NULL DEFAULT 'not_started',
            audit_generated_at TIMESTAMPTZ,
            audit_error TEXT,
            lead_id TEXT REFERENCES prospectingleads(id) ON DELETE SET NULL,
            lead_sync_status TEXT NOT NULL DEFAULT 'not_synced',
            lead_sync_error TEXT,
            raw_payload_json JSONB,
            created_by UUID,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_partnership_partner_cards_business_updated
        ON partnership_partner_cards (business_id, updated_at DESC)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_partnership_partner_cards_source_company
        ON partnership_partner_cards (business_id, source_company_name)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_partnership_partner_cards_match_status
        ON partnership_partner_cards (business_id, yandex_maps_match_status)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_partnership_partner_cards_lead_id
        ON partnership_partner_cards (lead_id)
        """
    )
    conn.commit()

def _ensure_sales_room_tables(conn) -> None:
    _ensure_partnership_partner_cards_table(conn)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sales_rooms (
            id UUID PRIMARY KEY,
            slug TEXT NOT NULL UNIQUE,
            business_id UUID NOT NULL,
            mode TEXT NOT NULL,
            lead_id TEXT REFERENCES prospectingleads(id) ON DELETE SET NULL,
            partner_card_id UUID REFERENCES partnership_partner_cards(id) ON DELETE SET NULL,
            data_mode TEXT NOT NULL DEFAULT 'template',
            audit_public_url TEXT,
            match_json JSONB,
            proposal_json JSONB,
            room_json JSONB NOT NULL,
            invitation_draft_id TEXT REFERENCES outreachmessagedrafts(id) ON DELETE SET NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            created_by UUID,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sales_rooms_business_updated
        ON sales_rooms (business_id, updated_at DESC)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sales_rooms_lead
        ON sales_rooms (lead_id)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sales_rooms_partner_card
        ON sales_rooms (partner_card_id)
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sales_room_events (
            id UUID PRIMARY KEY,
            room_id UUID NOT NULL REFERENCES sales_rooms(id) ON DELETE CASCADE,
            event_type TEXT NOT NULL,
            metadata_json JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sales_room_events_room_created
        ON sales_room_events (room_id, created_at DESC)
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sales_room_messages (
            id UUID PRIMARY KEY,
            room_id UUID NOT NULL REFERENCES sales_rooms(id) ON DELETE CASCADE,
            author_type TEXT NOT NULL DEFAULT 'visitor',
            author_name TEXT,
            author_contact TEXT,
            body_text TEXT,
            attachments_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sales_room_messages_room_created
        ON sales_room_messages (room_id, created_at ASC)
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sales_room_files (
            id UUID PRIMARY KEY,
            room_id UUID NOT NULL REFERENCES sales_rooms(id) ON DELETE CASCADE,
            message_id UUID REFERENCES sales_room_messages(id) ON DELETE SET NULL,
            original_name TEXT NOT NULL,
            mime_type TEXT,
            size_bytes INTEGER NOT NULL DEFAULT 0,
            storage_path TEXT NOT NULL,
            public_url TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sales_room_files_room_created
        ON sales_room_files (room_id, created_at DESC)
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sales_room_proposal_versions (
            id UUID PRIMARY KEY,
            room_id UUID NOT NULL REFERENCES sales_rooms(id) ON DELETE CASCADE,
            version_no INTEGER NOT NULL,
            body_text TEXT NOT NULL,
            created_by_name TEXT,
            created_by_contact TEXT,
            metadata_json JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (room_id, version_no)
        )
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sales_room_proposal_versions_room
        ON sales_room_proposal_versions (room_id, version_no DESC)
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sales_room_proposal_suggestions (
            id UUID PRIMARY KEY,
            room_id UUID NOT NULL REFERENCES sales_rooms(id) ON DELETE CASCADE,
            version_id UUID REFERENCES sales_room_proposal_versions(id) ON DELETE SET NULL,
            suggestion_type TEXT NOT NULL DEFAULT 'replace',
            selection_text TEXT NOT NULL,
            selection_start INTEGER,
            selection_end INTEGER,
            replacement_text TEXT,
            comment_text TEXT,
            author_name TEXT,
            author_contact TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            resolved_by_name TEXT,
            resolved_by_contact TEXT,
            resolved_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sales_room_proposal_suggestions_room_status
        ON sales_room_proposal_suggestions (room_id, status, created_at DESC)
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sales_room_participants (
            id UUID PRIMARY KEY,
            room_id UUID NOT NULL REFERENCES sales_rooms(id) ON DELETE CASCADE,
            email TEXT NOT NULL,
            name TEXT,
            company TEXT,
            is_verified BOOLEAN NOT NULL DEFAULT FALSE,
            personal_data_consent_at TIMESTAMPTZ,
            personal_data_consent_version TEXT,
            privacy_accepted_at TIMESTAMPTZ,
            consent_ip TEXT,
            consent_user_agent TEXT,
            verification_token TEXT,
            access_token TEXT NOT NULL,
            verified_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (room_id, email)
        )
        """
    )
    cur.execute(
        """
        ALTER TABLE sales_room_participants
        ADD COLUMN IF NOT EXISTS personal_data_consent_at TIMESTAMPTZ
        """
    )
    cur.execute(
        """
        ALTER TABLE sales_room_participants
        ADD COLUMN IF NOT EXISTS personal_data_consent_version TEXT
        """
    )
    cur.execute(
        """
        ALTER TABLE sales_room_participants
        ADD COLUMN IF NOT EXISTS privacy_accepted_at TIMESTAMPTZ
        """
    )
    cur.execute(
        """
        ALTER TABLE sales_room_participants
        ADD COLUMN IF NOT EXISTS consent_ip TEXT
        """
    )
    cur.execute(
        """
        ALTER TABLE sales_room_participants
        ADD COLUMN IF NOT EXISTS consent_user_agent TEXT
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sales_room_participants_verification_token
        ON sales_room_participants (verification_token)
        WHERE verification_token IS NOT NULL
        """
    )
    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_sales_room_participants_access_token
        ON sales_room_participants (access_token)
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sales_room_audit_offers (
            id UUID PRIMARY KEY,
            room_id UUID NOT NULL REFERENCES sales_rooms(id) ON DELETE CASCADE,
            lead_id TEXT REFERENCES prospectingleads(id) ON DELETE SET NULL,
            lead_email TEXT,
            company_name TEXT NOT NULL,
            company_map_url TEXT NOT NULL,
            company_address TEXT,
            platform TEXT NOT NULL DEFAULT 'yandex',
            enabled BOOLEAN NOT NULL DEFAULT FALSE,
            admin_comment TEXT,
            offer_title TEXT,
            offer_text TEXT,
            button_text TEXT,
            prepared_audit_slug TEXT,
            prepared_audit_url TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            requested_by_participant_id UUID REFERENCES sales_room_participants(id) ON DELETE SET NULL,
            requested_user_id UUID,
            requested_at TIMESTAMPTZ,
            processing_started_at TIMESTAMPTZ,
            ready_at TIMESTAMPTZ,
            opened_at TIMESTAMPTZ,
            email_sent_at TIMESTAMPTZ,
            metadata_json JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (room_id)
        )
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sales_room_audit_offers_processing
        ON sales_room_audit_offers (status, processing_started_at)
        WHERE status = 'processing'
        """
    )

def _row_to_dict(row: Any) -> dict[str, Any]:
    if not row:
        return {}
    if hasattr(row, "keys"):
        return dict(row)
    return {}

def _normalize_partner_kind(value: Any, *text_parts: Any) -> str:
    raw = str(value or "").strip().lower()
    text = " ".join(str(part or "") for part in text_parts).lower()
    combined = f"{raw} {text}".strip()
    residential_tokens = (
        "residential_complex",
        "residential",
        "жк",
        "жилой комплекс",
        "жилкомплекс",
        "новострой",
    )
    if raw in {PARTNER_KIND_BUSINESS, PARTNER_KIND_RESIDENTIAL_COMPLEX, PARTNER_KIND_OTHER}:
        return raw
    if any(token in combined for token in residential_tokens):
        return PARTNER_KIND_RESIDENTIAL_COMPLEX
    if raw in {"other", "другое"}:
        return PARTNER_KIND_OTHER
    return PARTNER_KIND_BUSINESS

def _is_residential_partner_card(card: dict[str, Any]) -> bool:
    return _normalize_partner_kind(
        card.get("partner_kind"),
        card.get("partner_name"),
        card.get("partner_category"),
        card.get("raw_payload_json"),
    ) == PARTNER_KIND_RESIDENTIAL_COMPLEX

def _build_partner_source_label(card: dict[str, Any]) -> str:
    source_company_name = str(card.get("source_company_name") or "").strip()
    if source_company_name:
        return f"Партнёр {source_company_name}"
    return "Партнёр компании"

def _build_partner_search_query(card: dict[str, Any]) -> str:
    parts = [
        str(card.get("partner_name") or "").strip(),
        str(card.get("partner_city") or "").strip(),
        str(card.get("partner_address") or "").strip(),
    ]
    return " ".join(part for part in parts if part).strip()

def _extract_candidate_source_url(candidate: dict[str, Any]) -> str:
    for key in ("source_url", "url", "maps_url", "yandex_maps_url"):
        value = str(candidate.get(key) or "").strip()
        if value:
            return normalize_map_url(value)
    return ""

def _score_partner_candidate(card: dict[str, Any], candidate: dict[str, Any]) -> tuple[float, str]:
    partner_name = str(card.get("partner_name") or "").strip().lower()
    partner_address = str(card.get("partner_address") or "").strip().lower()
    candidate_name = str(candidate.get("name") or candidate.get("title") or "").strip().lower()
    candidate_address = str(candidate.get("address") or candidate.get("location") or "").strip().lower()
    if not partner_name:
        return 0.0, "missing_partner_name"

    name_score = SequenceMatcher(None, partner_name, candidate_name).ratio() if candidate_name else 0.0
    address_score = 0.0
    if partner_address and candidate_address:
        address_score = SequenceMatcher(None, partner_address, candidate_address).ratio()
    elif partner_address:
        address_score = 0.15

    source_url = _extract_candidate_source_url(candidate)
    url_bonus = 0.1 if source_url and "yandex." in source_url else 0.0
    score = min(1.0, round((name_score * 0.72) + (address_score * 0.18) + url_bonus, 4))
    reason = f"name={round(name_score, 3)} address={round(address_score, 3)} yandex_url={bool(url_bonus)}"
    return score, reason

def _normalize_partner_candidate(card: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    confidence, reason = _score_partner_candidate(card, candidate)
    source_url = _extract_candidate_source_url(candidate)
    reviews_count = candidate.get("reviews_count")
    if reviews_count is None and isinstance(candidate.get("reviews"), list):
        reviews_count = len(candidate.get("reviews") or [])
    return {
        "name": str(candidate.get("name") or candidate.get("title") or "").strip() or None,
        "address": str(candidate.get("address") or candidate.get("location") or "").strip() or None,
        "category": str(candidate.get("category") or candidate.get("categoryName") or "").strip() or None,
        "rating": candidate.get("rating") or candidate.get("totalScore"),
        "reviews_count": reviews_count,
        "yandex_maps_url": source_url or None,
        "external_source_id": str(candidate.get("source_external_id") or candidate.get("businessId") or candidate.get("source_id") or "").strip() or None,
        "confidence": confidence,
        "reason": reason,
        "raw": candidate,
    }

def _find_yandex_candidates_for_partner_card(card: dict[str, Any], limit: int = 5) -> tuple[list[dict[str, Any]], str | None]:
    query = _build_partner_search_query(card)
    if not query:
        return [], "missing_search_query"
    service = ProspectingService(source="apify_yandex")
    if not service.client:
        return [], "yandex_provider_unavailable"
    try:
        result = service.run_search(
            query,
            str(card.get("partner_city") or "").strip(),
            limit=max(1, min(limit, 10)),
            timeout_sec=SEARCH_JOB_TIMEOUT_SEC,
        )
    except Exception:
        return [], str(sys.exc_info()[1])
    raw_items = result.get("items") if isinstance(result, dict) else []
    if not isinstance(raw_items, list):
        raw_items = []
    candidates = [_normalize_partner_candidate(card, item) for item in raw_items if isinstance(item, dict)]
    candidates = [item for item in candidates if str(item.get("yandex_maps_url") or "").strip()]
    candidates.sort(key=lambda item: float(item.get("confidence") or 0), reverse=True)
    return candidates[:limit], None

def _partnership_lead_as_partner_card(lead: dict[str, Any]) -> dict[str, Any]:
    return {
        "partner_name": str(lead.get("name") or "").strip(),
        "partner_city": str(lead.get("city") or "").strip(),
        "partner_address": str(lead.get("address") or "").strip(),
    }

def _is_synthetic_partnership_lead(lead: dict[str, Any]) -> bool:
    identity = " ".join(
        str(lead.get(key) or "").strip().lower()
        for key in ("name", "category", "address")
    )
    return any(marker in identity for marker in PARTNERSHIP_SYNTHETIC_MARKERS)

def _candidate_is_closed(candidate: dict[str, Any]) -> bool:
    raw = candidate.get("raw") if isinstance(candidate.get("raw"), dict) else {}
    status = str(
        raw.get("businessStatus")
        or raw.get("business_status")
        or raw.get("status")
        or ""
    ).strip().lower()
    closed_statuses = {"closed", "permanently_closed", "temporarily_closed", "inactive"}
    return bool(
        raw.get("permanentlyClosed")
        or raw.get("temporarilyClosed")
        or raw.get("isClosed")
        or status in closed_statuses
    )

def _find_yandex_candidates_for_partnership_lead(
    lead: dict[str, Any],
    limit: int = 5,
) -> tuple[list[dict[str, Any]], str | None]:
    partner_card = _partnership_lead_as_partner_card(lead)
    candidates: list[dict[str, Any]] = []
    provider_error: str | None = None
    for attempt in range(2):
        candidates, provider_error = _find_yandex_candidates_for_partner_card(partner_card, limit=limit)
        if not provider_error:
            return candidates, None
        normalized_error = provider_error.lower()
        transient = any(
            marker in normalized_error
            for marker in ("timeout", "timed out", "temporar", "connection", "429", "502", "503", "504")
        )
        if attempt > 0 or not transient:
            break
    return candidates, provider_error

def _select_partnership_map_candidate(candidates: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str]:
    active_candidates = [candidate for candidate in candidates if not _candidate_is_closed(candidate)]
    if not active_candidates:
        return None, "closed_or_not_found"
    best = active_candidates[0]
    best_confidence = float(best.get("confidence") or 0)
    runner_up_confidence = float(active_candidates[1].get("confidence") or 0) if len(active_candidates) > 1 else 0.0
    if best_confidence < PARTNER_MAP_MATCH_MIN_CONFIDENCE:
        return None, "low_confidence"
    if len(active_candidates) > 1 and best_confidence - runner_up_confidence < PARTNER_MAP_MATCH_MIN_MARGIN:
        return None, "ambiguous"
    return best, "confirmed"

def _store_partnership_map_match(
    cur,
    *,
    lead: dict[str, Any],
    candidate: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> None:
    original_source_url = str(lead.get("source_url") or "").strip()
    existing_sources = lead.get("matched_sources_json")
    if not isinstance(existing_sources, list):
        existing_sources = []
    source_history = list(existing_sources)
    if original_source_url and not any(
        str(item.get("url") or "").strip() == original_source_url
        for item in source_history
        if isinstance(item, dict)
    ):
        source_history.append({"type": "source_document", "url": original_source_url})
    source_history.append(
        {
            "type": "yandex_map_match",
            "url": candidate.get("yandex_maps_url"),
            "confidence": candidate.get("confidence"),
            "reason": candidate.get("reason"),
            "matched_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    cur.execute(
        """
        UPDATE prospectingleads
        SET source_url = %s,
            source = 'apify_yandex',
            source_kind = 'maps',
            source_provider = 'apify_yandex',
            external_place_id = COALESCE(NULLIF(%s, ''), external_place_id),
            external_source_id = COALESCE(NULLIF(%s, ''), external_source_id),
            address = COALESCE(NULLIF(%s, ''), address),
            category = COALESCE(NULLIF(%s, ''), category),
            rating = COALESCE(%s, rating),
            reviews_count = COALESCE(%s, reviews_count),
            search_payload_json = %s,
            matched_sources_json = %s,
            updated_at = NOW()
        WHERE id = %s
        """,
        (
            str(candidate.get("yandex_maps_url") or "").strip(),
            str(candidate.get("external_source_id") or "").strip(),
            str(candidate.get("external_source_id") or "").strip(),
            str(candidate.get("address") or "").strip(),
            str(candidate.get("category") or "").strip(),
            candidate.get("rating"),
            candidate.get("reviews_count"),
            Json({"map_match_candidates": candidates}),
            Json(source_history),
            str(lead.get("id") or ""),
        ),
    )

def _load_partner_card(cur, *, partner_id: str, business_id: str) -> dict[str, Any] | None:
    cur.execute(
        """
        SELECT *
        FROM partnership_partner_cards
        WHERE id = NULLIF(%s, '')::uuid
          AND business_id = NULLIF(%s, '')::uuid
        LIMIT 1
        """,
        (partner_id, business_id),
    )
    row = cur.fetchone()
    payload = _row_to_dict(row)
    return payload or None

def _normalize_partner_card_for_response(card: dict[str, Any]) -> dict[str, Any]:
    payload = dict(card or {})
    payload["source_label"] = _build_partner_source_label(payload)
    payload["is_residential_complex"] = _is_residential_partner_card(payload)
    if str(payload.get("audit_slug") or "").strip() and not str(payload.get("audit_public_url") or "").strip():
        payload["audit_public_url"] = _make_public_offer_url(str(payload.get("audit_slug") or "").strip())
    return _to_json_compatible(payload)

def _upsert_partner_card_lead_link(
    cur,
    *,
    card: dict[str, Any],
    lead_id: str,
    lead_sync_status: str,
    lead_sync_error: str | None = None,
) -> None:
    cur.execute(
        """
        UPDATE partnership_partner_cards
        SET lead_id = %s,
            lead_sync_status = %s,
            lead_sync_error = %s,
            updated_at = NOW()
        WHERE id = %s
        """,
        (lead_id or None, lead_sync_status, lead_sync_error, card.get("id")),
    )

def _sync_partner_card_to_lead(cur, *, card: dict[str, Any], user_id: str) -> tuple[str | None, bool, str | None]:
    if _is_residential_partner_card(card):
        cur.execute(
            """
            UPDATE partnership_partner_cards
            SET yandex_maps_match_status = %s,
                lead_sync_status = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (PARTNER_MATCH_SKIPPED_RESIDENTIAL, PARTNER_LEAD_SKIPPED, card.get("id")),
        )
        return None, False, "skipped_residential_complex"

    source_url = normalize_map_url(str(card.get("yandex_maps_url") or "").strip())
    if not source_url:
        return None, False, "missing_yandex_maps_url"

    source_label = _build_partner_source_label(card)
    search_payload = {
        "source": "partnership_partner_card",
        "partner_source_company_id": str(card.get("source_company_id") or "").strip() or None,
        "partner_source_company_name": str(card.get("source_company_name") or "").strip() or None,
        "partner_source_partner_id": str(card.get("id") or "").strip() or None,
        "partner_source_label": source_label,
        "partner_card": {
            "id": str(card.get("id") or ""),
            "name": str(card.get("partner_name") or "").strip(),
            "address": str(card.get("partner_address") or "").strip(),
            "city": str(card.get("partner_city") or "").strip(),
            "category": str(card.get("partner_category") or "").strip(),
        },
    }
    lead_id, created = _insert_partnership_lead_if_new(
        cur,
        business_id=str(card.get("business_id") or ""),
        created_by=user_id,
        source_url=source_url,
        name=str(card.get("partner_name") or "").strip() or "Новый партнёр",
        address=str(card.get("partner_address") or "").strip() or None,
        city=str(card.get("partner_city") or "").strip() or None,
        category=str(card.get("partner_category") or "").strip() or None,
        source="partnership_partner_card",
        source_kind="partner_card",
        source_provider="localos_partner_card",
        external_source_id=_extract_yandex_org_id_from_url(source_url) or None,
        search_payload=search_payload,
    )
    if not lead_id:
        return None, False, "lead_insert_failed"

    cur.execute(
        """
        UPDATE prospectingleads
        SET partner_source_company_id = %s,
            partner_source_company_name = %s,
            partner_source_partner_id = %s,
            source = COALESCE(NULLIF(source, ''), 'partnership_partner_card'),
            status = COALESCE(NULLIF(status, ''), 'new'),
            pipeline_status = COALESCE(NULLIF(pipeline_status, ''), %s),
            partnership_stage = COALESCE(NULLIF(partnership_stage, ''), 'imported'),
            updated_at = NOW()
        WHERE id = %s
        """,
        (
            str(card.get("source_company_id") or "").strip() or None,
            str(card.get("source_company_name") or "").strip() or None,
            str(card.get("id") or "").strip() or None,
            PIPELINE_UNPROCESSED,
            lead_id,
        ),
    )
    _upsert_partner_card_lead_link(
        cur,
        card=card,
        lead_id=lead_id,
        lead_sync_status=PARTNER_LEAD_SYNCED,
    )
    try:
        _record_lead_timeline_event(
            cur,
            lead_id=lead_id,
            event_type="partner_card_synced",
            actor_id=user_id,
            comment=source_label,
            payload={
                "partner_card_id": str(card.get("id") or ""),
                "source_company_name": str(card.get("source_company_name") or ""),
            },
        )
    except Exception:
        pass
    return lead_id, created, None

def _create_admin_public_audit_for_lead(
    cur,
    *,
    lead: dict[str, Any],
    user_id: str,
    source_type: str,
    primary_language: str = "ru",
) -> tuple[str, str, dict[str, Any]]:
    preview = build_lead_card_preview_snapshot(lead)
    quality = evaluate_audit_quality(
        preview,
        expected_name=str(lead.get("name") or ""),
        expected_address=str(lead.get("address") or ""),
    )
    if not quality.get("passed"):
        raise AuditQualityError(quality)
    page_json = _to_json_compatible(
        _build_admin_lead_offer_payload(
            lead=lead,
            preview=preview,
            preferred_language=primary_language,
            enabled_languages=[primary_language],
        )
    )
    page_json["source"] = source_type
    page_json["quality"] = quality
    page_json["signup_context"] = {
        "source": "partnership_partner",
        "lead_id": str(lead.get("id") or ""),
        "partner_id": str(lead.get("partner_source_partner_id") or ""),
        "source_company_name": str(lead.get("partner_source_company_name") or ""),
        "maps_url": str(lead.get("source_url") or ""),
    }
    page_json = normalize_public_audit_page_json(page_json)

    base_slug = _build_offer_slug(
        str(lead.get("name") or "partner"),
        str(lead.get("city") or ""),
        str(lead.get("address") or ""),
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
        if str(existing_lead_id or "") == str(lead.get("id") or ""):
            break
        suffix += 1
        slug = f"{base_slug}-{suffix}"

    cur.execute(
        """
        INSERT INTO adminprospectingleadpublicoffers (
            lead_id, business_id, business_profile, source_type,
            slug, page_json, generated_json, edited_json, published_json,
            edit_status, is_active, created_by, published_by, published_at, created_at, updated_at
        ) VALUES (%s, NULLIF(%s, '')::uuid, %s, %s, %s, %s, %s, NULL, %s, %s, TRUE, NULLIF(%s, '')::uuid, NULLIF(%s, '')::uuid, NOW(), NOW(), NOW())
        ON CONFLICT (lead_id) DO UPDATE
        SET slug = EXCLUDED.slug,
            page_json = EXCLUDED.page_json,
            business_id = EXCLUDED.business_id,
            business_profile = EXCLUDED.business_profile,
            source_type = EXCLUDED.source_type,
            generated_json = EXCLUDED.generated_json,
            published_json = EXCLUDED.published_json,
            edit_status = EXCLUDED.edit_status,
            is_active = TRUE,
            published_by = EXCLUDED.published_by,
            published_at = NOW(),
            updated_at = NOW()
        """,
        (
            str(lead.get("id") or ""),
            str(lead.get("business_id") or ""),
            str(page_json.get("audit", {}).get("audit_profile") or "").strip() or None,
            source_type,
            slug,
            Json(page_json),
            Json(page_json),
            Json(page_json),
            "published",
            user_id,
            user_id,
        ),
    )
    return slug, _make_public_offer_url(slug), page_json

def _process_partner_card_parse(*, partner_id: str, business_id: str, user_id: str) -> dict[str, Any]:
    conn = get_db_connection()
    try:
        _ensure_partnership_columns(conn)
        _ensure_manual_crm_tables(conn)
        _ensure_partnership_partner_cards_table(conn)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        card = _load_partner_card(cur, partner_id=partner_id, business_id=business_id)
        if not card:
            return {"success": False, "error": "Partner card not found", "status_code": 404}
        lead_id = str(card.get("lead_id") or "").strip()
        if not lead_id:
            lead_id, _, sync_error = _sync_partner_card_to_lead(cur, card=card, user_id=user_id)
            if sync_error:
                conn.commit()
                return {"success": False, "error": sync_error, "status_code": 400}
        conn.commit()
        cur.execute("SELECT * FROM prospectingleads WHERE id = %s", (lead_id,))
        lead = _row_to_dict(cur.fetchone())
    finally:
        conn.close()

    if not lead:
        return {"success": False, "error": "Lead not found after sync", "status_code": 404}
    display_lead = _sync_partnership_lead_from_parsed_data(lead)
    parse_business_id = str(display_lead.get("parse_business_id") or "").strip()
    if not parse_business_id:
        business, _business_created = _ensure_parse_business_for_partnership_lead(display_lead, user_id)
        parse_business_id = str(business.get("id") or "").strip()
    source_url = str(display_lead.get("source_url") or "").strip()
    if not source_url:
        return {"success": False, "error": "missing_source_url", "status_code": 400}
    task = _enqueue_parse_task_for_business(parse_business_id, user_id, source_url)

    conn = get_db_connection()
    try:
        _ensure_partnership_partner_cards_table(conn)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            UPDATE partnership_partner_cards
            SET parse_business_id = NULLIF(%s, '')::uuid,
                updated_at = NOW()
            WHERE id = NULLIF(%s, '')::uuid
            RETURNING *
            """,
            (parse_business_id, partner_id),
        )
        updated = _normalize_partner_card_for_response(_row_to_dict(cur.fetchone()))
        conn.commit()
    finally:
        conn.close()
    return {
        "success": True,
        "task": _to_json_compatible(task),
        "parse_business_id": parse_business_id,
        "card": updated,
        "status_code": 200,
    }

def _process_partner_card_audit(
    *,
    partner_id: str,
    business_id: str,
    user_id: str,
    primary_language: str = "ru",
) -> dict[str, Any]:
    conn = get_db_connection()
    try:
        _ensure_partnership_columns(conn)
        _ensure_manual_crm_tables(conn)
        _ensure_partnership_partner_cards_table(conn)
        _ensure_admin_prospecting_public_offers_table(conn)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        card = _load_partner_card(cur, partner_id=partner_id, business_id=business_id)
        if not card:
            return {"success": False, "error": "Partner card not found", "status_code": 404}
        lead_id = str(card.get("lead_id") or "").strip()
        if not lead_id:
            lead_id, _, sync_error = _sync_partner_card_to_lead(cur, card=card, user_id=user_id)
            if sync_error:
                cur.execute(
                    """
                    UPDATE partnership_partner_cards
                    SET audit_status = %s,
                        audit_error = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (PARTNER_AUDIT_FAILED, sync_error, card.get("id")),
                )
                conn.commit()
                return {"success": False, "error": sync_error, "status_code": 400}
        cur.execute("SELECT * FROM prospectingleads WHERE id = %s", (lead_id,))
        lead = _row_to_dict(cur.fetchone())
        if not lead:
            return {"success": False, "error": "Lead not found after sync", "status_code": 404}
        lead = _sync_partnership_lead_from_parsed_data(lead)
        slug, public_url, page_json = _create_admin_public_audit_for_lead(
            cur,
            lead=lead,
            user_id=user_id,
            source_type="partnership_partner_public_audit",
            primary_language=primary_language,
        )
        cur.execute(
            """
            UPDATE partnership_partner_cards
            SET audit_public_url = %s,
                audit_slug = %s,
                audit_status = %s,
                audit_generated_at = NOW(),
                audit_error = NULL,
                updated_at = NOW()
            WHERE id = %s
            RETURNING *
            """,
            (public_url, slug, PARTNER_AUDIT_GENERATED, card.get("id")),
        )
        updated = _normalize_partner_card_for_response(_row_to_dict(cur.fetchone()))
        conn.commit()
    finally:
        conn.close()
    return {
        "success": True,
        "slug": slug,
        "public_url": public_url,
        "page": page_json,
        "card": updated,
        "status_code": 200,
    }

def _derive_pipeline_status_from_lead(lead: dict[str, Any] | None) -> str:
    if not lead:
        return PIPELINE_UNPROCESSED
    explicit = str(lead.get("pipeline_status") or "").strip().lower()
    if explicit in ALLOWED_PIPELINE_STATUSES:
        return explicit
    legacy = str(lead.get("status") or "").strip().lower()
    if not legacy or legacy == "new":
        return PIPELINE_UNPROCESSED
    if legacy in {"deferred", "shortlist_rejected", "rejected", "closed"}:
        return PIPELINE_NOT_RELEVANT
    if legacy in {"shortlist_approved", "selected_for_outreach", "channel_selected", "draft_ready", "queued_for_send", "audited", "matched", "proposal_draft_ready", "proposal_approved", "approved_for_send"}:
        return PIPELINE_IN_PROGRESS
    if legacy == "sent":
        return PIPELINE_CONTACTED
    if legacy == "delivered":
        return PIPELINE_CONTACTED
    if legacy == "responded":
        return PIPELINE_REPLIED
    if legacy == "second_message_sent":
        return PIPELINE_SECOND_MESSAGE_SENT
    if legacy in {"qualified", "converted"}:
        return PIPELINE_CONVERTED
    return PIPELINE_IN_PROGRESS

def _record_lead_timeline_event(
    cur,
    *,
    lead_id: str,
    event_type: str,
    actor_id: str | None = None,
    comment: str | None = None,
    payload: dict[str, Any] | None = None,
    workstream_id: str | None = None,
) -> None:
    if workstream_id:
        cur.execute(
            """
            INSERT INTO lead_timeline_events (
                id, lead_id, workstream_id, event_type, actor_id, comment, payload_json, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """,
            (
                str(uuid.uuid4()),
                lead_id,
                workstream_id,
                event_type,
                actor_id,
                (comment or "").strip() or None,
                Json(_to_json_compatible(payload or {})),
            ),
        )
        return
    cur.execute(
        """
        INSERT INTO lead_timeline_events (
            id, lead_id, event_type, actor_id, comment, payload_json, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """,
        (
            str(uuid.uuid4()),
            lead_id,
            event_type,
            actor_id,
            (comment or "").strip() or None,
            Json(_to_json_compatible(payload or {})),
        ),
    )

def _apply_pipeline_transition(
    cur,
    *,
    lead_id: str,
    pipeline_status: str,
    actor_id: str | None = None,
    comment: str | None = None,
    disqualification_reason: str | None = None,
    disqualification_comment: str | None = None,
    postponed_comment: str | None = None,
    next_action_at: str | None = None,
    last_contact_channel: str | None = None,
    last_contact_comment: str | None = None,
    set_last_contact_at: bool = False,
) -> dict[str, Any] | None:
    assignments = [
        "pipeline_status = %s",
        "last_manual_action_at = NOW()",
        "last_manual_action_by = %s",
        "updated_at = NOW()",
    ]
    params: list[Any] = [pipeline_status, actor_id]

    legacy_status = None
    if pipeline_status == PIPELINE_UNPROCESSED:
        legacy_status = "new"
    elif pipeline_status == PIPELINE_IN_PROGRESS:
        legacy_status = SHORTLIST_APPROVED
    elif pipeline_status == PIPELINE_POSTPONED:
        legacy_status = "deferred"
    elif pipeline_status == PIPELINE_NOT_RELEVANT:
        legacy_status = SHORTLIST_REJECTED
    elif pipeline_status == PIPELINE_CONTACTED:
        legacy_status = "sent"
    elif pipeline_status == PIPELINE_WAITING_REPLY:
        legacy_status = "sent"
    elif pipeline_status == PIPELINE_SECOND_MESSAGE_SENT:
        legacy_status = "second_message_sent"
    elif pipeline_status == PIPELINE_REPLIED:
        legacy_status = "responded"
    elif pipeline_status == PIPELINE_CONVERTED:
        legacy_status = "converted"
    elif pipeline_status == PIPELINE_CLOSED_LOST:
        legacy_status = "closed"
    if legacy_status:
        assignments.append("status = %s")
        params.append(legacy_status)

    if disqualification_reason is not None:
        assignments.append("disqualification_reason = %s")
        params.append(disqualification_reason)
    if disqualification_comment is not None:
        assignments.append("disqualification_comment = %s")
        params.append(disqualification_comment)
    if postponed_comment is not None:
        assignments.append("postponed_comment = %s")
        params.append(postponed_comment)
    if next_action_at is not None:
        assignments.append("next_action_at = %s")
        params.append(next_action_at or None)
    elif pipeline_status == PIPELINE_CONTACTED:
        assignments.append("next_action_at = %s")
        params.append(_next_followup_at())
    elif pipeline_status == PIPELINE_SECOND_MESSAGE_SENT:
        assignments.append("next_action_at = NULL")
    if last_contact_channel is not None:
        assignments.append("last_contact_channel = %s")
        params.append(last_contact_channel or None)
    if last_contact_comment is not None:
        assignments.append("last_contact_comment = %s")
        params.append(last_contact_comment or None)
    if set_last_contact_at:
        assignments.append("last_contact_at = NOW()")

    params.append(lead_id)
    cur.execute(
        f"""
        UPDATE prospectingleads
        SET {', '.join(assignments)}
        WHERE id = %s
        RETURNING *
        """,
        tuple(params),
    )
    row = cur.fetchone()
    if row:
        _record_lead_timeline_event(
            cur,
            lead_id=lead_id,
            event_type="pipeline_status_changed",
            actor_id=actor_id,
            comment=comment,
            payload={
                "pipeline_status": pipeline_status,
                "legacy_status": legacy_status,
                "disqualification_reason": disqualification_reason,
                "postponed_comment": postponed_comment,
                "next_action_at": next_action_at,
                "last_contact_channel": last_contact_channel,
            },
        )
        return dict(row) if hasattr(row, "keys") else None
    return None

def _group_summary_for_lead_ids(cur, lead_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    normalized_ids = [str(item or "").strip() for item in lead_ids if str(item or "").strip()]
    if not normalized_ids:
        return {}
    cur.execute(
        """
        SELECT gi.lead_id, g.id AS group_id, g.name, g.status, g.channel_hint, g.city_hint
        FROM lead_group_items gi
        JOIN lead_groups g ON g.id = gi.group_id
        WHERE gi.lead_id = ANY(%s)
        ORDER BY g.created_at DESC, g.name ASC
        """,
        (normalized_ids,),
    )
    summary: dict[str, list[dict[str, Any]]] = {}
    for row in cur.fetchall() or []:
        payload = dict(row) if hasattr(row, "keys") else {}
        lead_id = str(payload.get("lead_id") or "").strip()
        if not lead_id:
            continue
        summary.setdefault(lead_id, []).append(
            {
                "id": payload.get("group_id"),
                "name": payload.get("name"),
                "status": payload.get("status"),
                "channel_hint": payload.get("channel_hint"),
                "city_hint": payload.get("city_hint"),
            }
        )
    return summary

def _latest_timeline_preview(cur, lead_ids: list[str]) -> dict[str, dict[str, Any]]:
    normalized_ids = [str(item or "").strip() for item in lead_ids if str(item or "").strip()]
    if not normalized_ids:
        return {}
    cur.execute(
        """
        SELECT DISTINCT ON (lead_id)
            lead_id, event_type, comment, payload_json, created_at
        FROM lead_timeline_events
        WHERE lead_id = ANY(%s)
        ORDER BY lead_id, created_at DESC
        """,
        (normalized_ids,),
    )
    preview: dict[str, dict[str, Any]] = {}
    for row in cur.fetchall() or []:
        payload = dict(row) if hasattr(row, "keys") else {}
        lead_id = str(payload.get("lead_id") or "").strip()
        if lead_id:
            preview[lead_id] = {
                "event_type": payload.get("event_type"),
                "comment": payload.get("comment"),
                "payload": payload.get("payload_json") if isinstance(payload.get("payload_json"), dict) else {},
                "created_at": payload.get("created_at"),
            }
    return preview
