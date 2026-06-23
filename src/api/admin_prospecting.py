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
from urllib.parse import quote, unquote
from datetime import date, datetime, timedelta, timezone
from typing import Any

import requests
from flask import Blueprint, jsonify, request, send_file
from psycopg2.extras import Json, RealDictCursor

from auth_system import verify_session
from core.channel_delivery import normalize_phone, send_maton_bridge_message
from core.card_audit import build_lead_card_preview_snapshot
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
from services.sales_room_file_storage import load_sales_room_file, sales_room_upload_root, store_sales_room_file


admin_prospecting_bp = Blueprint("admin_prospecting", __name__)

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
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, inner in value.items():
            normalized[str(key)] = _to_json_compatible(inner)
        return normalized
    if isinstance(value, list):
        return [_to_json_compatible(item) for item in value]
    if isinstance(value, tuple):
        return [_to_json_compatible(item) for item in value]
    return value


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
    page_json = _to_json_compatible(
        _build_admin_lead_offer_payload(
            lead=lead,
            preview=preview,
            preferred_language=primary_language,
            enabled_languages=[primary_language],
        )
    )
    page_json["source"] = source_type
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
) -> None:
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


def _get_cursor_table_columns(cur, table_name: str) -> set[str]:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        """,
        (table_name,),
    )
    cols = set()
    for row in cur.fetchall():
        col = row.get("column_name") if hasattr(row, "get") else (row[0] if row else None)
        if col:
            cols.add(str(col))
    return cols


def _cursor_table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) AS table_ref", (f"public.{table_name}",))
    row = cur.fetchone()
    if hasattr(row, "get"):
        return bool(row.get("table_ref"))
    return bool(row[0] if row else None)


def _get_partnership_schema_flags(cur) -> dict[str, bool]:
    prospectingleads_columns = _get_cursor_table_columns(cur, "prospectingleads")
    parsequeue_exists = _cursor_table_exists(cur, "parsequeue")
    parsequeue_columns = _get_cursor_table_columns(cur, "parsequeue") if parsequeue_exists else set()
    reactions_exists = _cursor_table_exists(cur, "outreachmessagereactions")
    reactions_columns = _get_cursor_table_columns(cur, "outreachmessagereactions") if reactions_exists else set()

    has_parse_lookup = (
        parsequeue_exists
        and {"business_id", "url", "task_type", "status", "created_at"}.issubset(parsequeue_columns)
        and {"parse_business_id", "source_url"}.issubset(prospectingleads_columns)
    )
    has_reactions = reactions_exists and {"queue_id", "created_at"}.issubset(reactions_columns)
    has_reaction_outcomes = has_reactions and {
        "human_confirmed_outcome",
        "classified_outcome",
    }.issubset(reactions_columns)

    return {
        "has_parse_lookup": has_parse_lookup,
        "has_reactions": has_reactions,
        "has_reaction_outcomes": has_reaction_outcomes,
    }


def _partnership_parse_status_select_sql(lead_alias: str = "l") -> str:
    return f"""
        (
            SELECT pq.status
            FROM parsequeue pq
            WHERE (
                    ({lead_alias}.parse_business_id IS NOT NULL AND pq.business_id = {lead_alias}.parse_business_id)
                    OR (
                        {lead_alias}.parse_business_id IS NULL
                        AND {lead_alias}.source_url IS NOT NULL
                        AND {lead_alias}.source_url <> ''
                        AND pq.url = {lead_alias}.source_url
                    )
                  )
              AND pq.task_type IN ('parse_card', 'sync_yandex_business')
            ORDER BY COALESCE(pq.updated_at, pq.created_at) DESC
            LIMIT 1
        )
    """


def _normalize_partnership_source_url(url: Any) -> str:
    value = str(url or "").strip()
    if not value:
        return ""
    return normalize_map_url(value)


def _normalize_partnership_phone(phone: Any) -> str:
    normalized = normalize_phone(str(phone or "").strip())
    return normalized or ""


def _should_use_lead_name_for_match(name: Any) -> bool:
    text = str(name or "").strip()
    if not text:
        return False
    lowered = text.lower()
    return lowered not in {"новый партнёр", "партнёр", "компания"}


def _derive_name_from_source_url(source_url: Any) -> str | None:
    url = str(source_url or "").strip()
    if not url:
        return None
    match = re.search(r"/org/([^/]+)/", url)
    if not match:
        return None
    slug = unquote(str(match.group(1) or "").strip())
    if not slug:
        return None
    parts = [part for part in re.split(r"[_\\-]+", slug) if part]
    if not parts:
        return None
    name = " ".join(parts).strip()
    return name[:255] if name else None


def _merge_source_labels(existing_value: Any, *labels: str | None) -> list[str]:
    merged: list[str] = []
    seen = set()

    def _add(value: Any) -> None:
        if value is None:
            return
        if isinstance(value, list):
            for item in value:
                _add(item)
            return
        text = str(value).strip()
        if not text:
            return
        key = text.lower()
        if key in seen:
            return
        seen.add(key)
        merged.append(text)

    _add(existing_value)
    for label in labels:
        _add(label)
    return merged


def _create_search_job(
    *,
    source: str,
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
            (job_id, source, actor_id, query, location, search_limit, user_id),
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


def _compact_search_result_for_storage(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(item.get("name") or "").strip() or "Новый лид",
        "source": str(item.get("source") or "apify_yandex").strip() or "apify_yandex",
        "address": str(item.get("address") or "").strip() or None,
        "city": str(item.get("city") or "").strip() or None,
        "phone": str(item.get("phone") or "").strip() or None,
        "website": str(item.get("website") or "").strip() or None,
        "email": str(item.get("email") or "").strip() or None,
        "telegram_url": str(item.get("telegram_url") or "").strip() or None,
        "whatsapp_url": str(item.get("whatsapp_url") or "").strip() or None,
        "messenger_links_json": item.get("messenger_links") if isinstance(item.get("messenger_links"), list) else [],
        "rating": _safe_float(item.get("rating")),
        "reviews_count": _safe_int(item.get("reviews_count")),
        "source_url": str(item.get("source_url") or "").strip() or None,
        "source_external_id": str(
            item.get("source_external_id") or item.get("google_id") or item.get("business_id") or ""
        ).strip()
        or None,
        "google_id": str(item.get("google_id") or "").strip() or None,
        "category": str(item.get("category") or "").strip() or None,
        "status": "new",
    }


def _compact_search_results_for_storage(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compacted: list[dict[str, Any]] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        compacted.append(_compact_search_result_for_storage(item))
    return compacted


def _import_search_results_into_leads(
    *,
    job_row: dict[str, Any],
    results: list[dict[str, Any]],
) -> dict[str, int | str | None]:
    created_by = str(job_row.get("created_by") or "").strip()
    if not created_by:
        return {"imported_count": 0, "merged_count": 0, "business_id": None}

    conn = get_db_connection()
    try:
        _ensure_partnership_columns(conn)
        cur = conn.cursor()
        business_id = get_business_id_from_user(created_by, None)
        if not business_id:
            return {"imported_count": 0, "merged_count": 0, "business_id": None}

        imported_count = 0
        merged_count = 0
        for item in results:
            if not isinstance(item, dict):
                continue
            source_url = _normalize_partnership_source_url(str(item.get("source_url") or "").strip())
            if not source_url:
                continue

            phone = str(item.get("phone") or "").strip() or None
            source = str(item.get("source") or job_row.get("source") or "apify_yandex").strip() or "apify_yandex"
            external_source_id = str(
                item.get("source_external_id") or item.get("google_id") or _extract_yandex_org_id_from_url(source_url) or ""
            ).strip() or None
            lead_id, created = _insert_partnership_lead_if_new(
                cur,
                business_id=business_id,
                created_by=created_by,
                source_url=source_url,
                name=str(item.get("name") or "").strip() or "Новый лид",
                address=str(item.get("address") or "").strip() or None,
                city=str(item.get("city") or "").strip() or None,
                category=str(item.get("category") or "").strip() or None,
                source=source,
                phone=phone,
                email=str(item.get("email") or "").strip() or None,
                website=str(item.get("website") or "").strip() or None,
                telegram_url=str(item.get("telegram_url") or "").strip() or None,
                whatsapp_url=str(item.get("whatsapp_url") or "").strip() or None,
                rating=_safe_float(item.get("rating")),
                reviews_count=_safe_int(item.get("reviews_count")),
                source_kind="apify_search",
                source_provider=source,
                external_source_id=external_source_id,
                search_payload={
                    "job_id": str(job_row.get("id") or "").strip() or None,
                    "query": str(job_row.get("query") or "").strip() or None,
                    "location": str(job_row.get("location") or "").strip() or None,
                    "search_limit": _safe_int(job_row.get("search_limit")),
                    "source": source,
                },
            )
            if created and lead_id:
                imported_count += 1
            elif lead_id:
                merged_count += 1
        conn.commit()
        return {
            "imported_count": imported_count,
            "merged_count": merged_count,
            "business_id": business_id,
        }
    except Exception:
        conn.rollback()
        raise
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


def _get_latest_search_job(created_by: str | None = None):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        if created_by:
            cur.execute(
                """
                SELECT
                    id, source, actor_id, query, location, search_limit, status,
                    result_count, created_by, error_text, results_json,
                    created_at, updated_at, completed_at
                FROM outreachsearchjobs
                WHERE created_by = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (created_by,),
            )
        else:
            cur.execute(
                """
                SELECT
                    id, source, actor_id, query, location, search_limit, status,
                    result_count, created_by, error_text, results_json,
                    created_at, updated_at, completed_at
                FROM outreachsearchjobs
                ORDER BY created_at DESC
                LIMIT 1
                """
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


def _to_bool_query_flag(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes"}:
        return True
    if normalized in {"0", "false", "no"}:
        return False
    return default


def _is_placeholder_like(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {
        "",
        "name",
        "title",
        "category",
        "source",
        "address",
        "location",
        "phone",
        "email",
        "website",
        "rating",
        "reviews_count",
        "status",
    }


def _normalize_lead_for_display(lead: dict[str, Any]) -> dict[str, Any] | None:
    normalized = dict(lead)
    if _is_placeholder_like(normalized.get("name")):
        normalized["name"] = None

    if not normalized.get("name"):
        for fallback_field in ("title", "company_name", "company"):
            fallback_value = normalized.get(fallback_field)
            if fallback_value and not _is_placeholder_like(fallback_value):
                normalized["name"] = str(fallback_value).strip()
                break

    for field in (
        "category",
        "address",
        "location",
        "phone",
        "email",
        "website",
        "source",
        "status",
        "pipeline_status",
    ):
        if _is_placeholder_like(normalized.get(field)):
            normalized[field] = None

    for field in ("rating", "reviews_count"):
        if _is_placeholder_like(normalized.get(field)):
            normalized[field] = None

    enabled_languages = normalized.get("enabled_languages")
    if isinstance(enabled_languages, str) and enabled_languages:
        try:
            normalized["enabled_languages"] = json.loads(enabled_languages)
        except Exception:
            normalized["enabled_languages"] = None

    if not normalized.get("name"):
        return None

    has_identity = any(
        normalized.get(field)
        for field in ("name", "address", "website", "phone", "source_url")
    )
    if not has_identity:
        return None

    normalized["pipeline_status"] = _derive_pipeline_status_from_lead(normalized)
    return normalized


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
    if status and (lead.get("pipeline_status") or lead.get("status") or "") != status:
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


def _insert_partnership_lead_if_new(
    cur,
    *,
    business_id: str,
    created_by: str,
    source_url: str,
    name: str | None,
    address: str | None,
    city: str | None,
    category: str | None,
    source: str,
    phone: str | None = None,
    email: str | None = None,
    website: str | None = None,
    telegram_url: str | None = None,
    whatsapp_url: str | None = None,
    rating: float | None = None,
    reviews_count: int | None = None,
    source_kind: str | None = None,
    source_provider: str | None = None,
    external_place_id: str | None = None,
    external_source_id: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    search_payload: dict[str, Any] | None = None,
) -> tuple[str | None, bool]:
    normalized_url = _normalize_partnership_source_url(source_url)
    if not normalized_url:
        return None, False
    table_columns = _get_cursor_table_columns(cur, "prospectingleads")
    normalized_external_source_id = str(
        external_source_id or external_place_id or _extract_yandex_org_id_from_url(normalized_url) or ""
    ).strip()
    normalized_phone = _normalize_partnership_phone(phone)

    exact_sql = [
        "business_id = %s",
        "AND",
        "COALESCE(intent, 'client_outreach') = 'partnership_outreach'",
        "AND (",
        "source_url = %s",
    ]
    exact_params: list[Any] = [business_id, normalized_url]
    if normalized_external_source_id and "external_source_id" in table_columns:
        exact_sql.extend(["OR external_source_id = %s"])
        exact_params.append(normalized_external_source_id)
    if normalized_phone:
        exact_sql.extend(["OR phone = %s"])
        exact_params.append(normalized_phone)
    exact_sql.append(")")
    cur.execute(
        f"""
        SELECT *
        FROM prospectingleads
        WHERE {" ".join(exact_sql)}
        ORDER BY updated_at DESC NULLS LAST, created_at DESC
        LIMIT 1
        """,
        exact_params,
    )
    existing = cur.fetchone()
    if not existing and _should_use_lead_name_for_match(name):
        normalized_address = str(address or "").strip().lower()
        name_params: list[Any] = [business_id, str(name or "").strip().lower()]
        city_sql = "COALESCE(LOWER(city), '') = COALESCE(%s, '')"
        address_sql = "COALESCE(LOWER(address), '') = COALESCE(%s, '')"
        name_params.append(str(city or "").strip().lower() or "")
        name_params.append(normalized_address)
        cur.execute(
            f"""
            SELECT *
            FROM prospectingleads
            WHERE business_id = %s
              AND COALESCE(intent, 'client_outreach') = 'partnership_outreach'
              AND LOWER(COALESCE(name, '')) = %s
              AND ({city_sql} OR {address_sql})
            ORDER BY updated_at DESC NULLS LAST, created_at DESC
            LIMIT 1
            """,
            name_params,
        )
        existing = cur.fetchone()
    if existing:
        existing_payload = dict(existing) if hasattr(existing, "keys") else {}
        existing_id = str(existing_payload.get("id") or (existing[0] if existing else ""))
        updates: list[str] = []
        params: list[Any] = []

        def _fill_if_missing(column: str, value: Any) -> None:
            existing_value = existing_payload.get(column)
            is_missing = existing_value in (None, "", [])
            if value not in (None, "", []) and is_missing:
                updates.append(f"{column} = %s")
                params.append(value)

        _fill_if_missing("address", address)
        _fill_if_missing("name", name)
        _fill_if_missing("city", city)
        _fill_if_missing("category", category)
        _fill_if_missing("phone", normalized_phone or phone)
        _fill_if_missing("email", email)
        _fill_if_missing("website", website)
        _fill_if_missing("telegram_url", telegram_url)
        _fill_if_missing("whatsapp_url", whatsapp_url)
        _fill_if_missing("source_url", normalized_url)
        _fill_if_missing("source", source)
        if "source_kind" in table_columns:
            _fill_if_missing("source_kind", source_kind)
        if "source_provider" in table_columns:
            _fill_if_missing("source_provider", source_provider)
        if "external_place_id" in table_columns:
            _fill_if_missing("external_place_id", external_place_id)
        if "external_source_id" in table_columns:
            _fill_if_missing("external_source_id", normalized_external_source_id)
        if "lat" in table_columns:
            _fill_if_missing("lat", lat)
        if "lon" in table_columns:
            _fill_if_missing("lon", lon)
        if rating is not None:
            updates.append("rating = %s")
            params.append(rating)
        if reviews_count is not None:
            updates.append("reviews_count = %s")
            params.append(reviews_count)
        if "search_payload_json" in table_columns and search_payload:
            updates.append("search_payload_json = %s")
            params.append(Json(search_payload))
        if "dedupe_key" in table_columns:
            dedupe_key = normalized_external_source_id or normalized_phone or normalized_url
            if dedupe_key:
                updates.append("dedupe_key = %s")
                params.append(dedupe_key)
        if "matched_sources_json" in table_columns:
            merged_sources = _merge_source_labels(
                existing_payload.get("matched_sources_json"),
                existing_payload.get("source"),
                source,
                source_provider,
            )
            updates.append("matched_sources_json = %s")
            params.append(Json(merged_sources))
        if updates:
            updates.append("updated_at = NOW()")
            params.append(existing_id)
            cur.execute(
                f"""
                UPDATE prospectingleads
                SET {", ".join(updates)}
                WHERE id = %s
                """,
                params,
            )
        return existing_id, False

    lead_id = str(uuid.uuid4())
    dedupe_key = normalized_external_source_id or normalized_phone or normalized_url
    cur.execute(
        """
        INSERT INTO prospectingleads (
            id, name, address, city, source_url, source, category, status,
            phone, email, website, telegram_url, whatsapp_url, rating, reviews_count,
            intent, partnership_stage, business_id, created_by, created_at, updated_at,
            source_kind, source_provider, external_place_id, external_source_id, dedupe_key,
            lat, lon, search_payload_json, matched_sources_json
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, NOW(), NOW(),
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s
        )
        """,
        (
            lead_id,
            (name or "Новый партнёр"),
            address or "",
            city,
            normalized_url,
            source,
            category,
            "imported",
            phone,
            email,
            website,
            telegram_url,
            whatsapp_url,
            rating,
            reviews_count,
            "partnership_outreach",
            "imported",
            business_id,
            created_by,
            source_kind,
            source_provider,
            external_place_id,
            normalized_external_source_id or None,
            dedupe_key or None,
            lat,
            lon,
            Json(search_payload) if search_payload else None,
            Json(_merge_source_labels([], source, source_provider)),
        ),
    )
    return lead_id, True


def _pick_first_value(row: dict[str, Any], candidates: list[str]) -> str | None:
    for key in candidates:
        if key in row and row.get(key) not in (None, ""):
            value = str(row.get(key)).strip()
            if value:
                return value
    return None


def _safe_float(raw: Any) -> float | None:
    if raw is None:
        return None
    text = str(raw).strip().replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except Exception:
        return None


def _safe_int(raw: Any) -> int | None:
    if raw is None:
        return None
    text = str(raw).strip().replace(" ", "")
    if not text:
        return None
    try:
        return int(float(text))
    except Exception:
        return None


def _contains_paid_promotion_signal(value: Any, depth: int = 0) -> bool:
    if depth > 5:
        return False
    if isinstance(value, str):
        normalized = value.lower()
        return any(
            marker in normalized
            for marker in (
                "geoadv_maps",
                "yclid=",
                "utm_source=geoadv",
                "paid promotion",
                "реклама",
                "платное продвиж",
                "продвижение",
            )
        )
    if isinstance(value, dict):
        for key, next_value in value.items():
            normalized_key = str(key or "").lower()
            if normalized_key in {"promo", "promoted", "promotion", "advertising", "ad", "ads", "paid"}:
                if next_value not in (None, False, "", [], {}):
                    return True
            if _contains_paid_promotion_signal(next_value, depth + 1):
                return True
    if isinstance(value, list):
        for item in value:
            if _contains_paid_promotion_signal(item, depth + 1):
                return True
    return False


def _normalize_contact_url(raw: str | None) -> str | None:
    value = str(raw or "").strip()
    if not value:
        return None
    if value.startswith(("http://", "https://", "tg://")):
        return value
    if value.startswith("@"):
        return f"https://t.me/{value[1:]}"
    if "t.me/" in value:
        return f"https://{value}" if not value.startswith("http") else value
    if value.startswith("wa.me/"):
        return f"https://{value}"
    return value


def _normalize_media_url(raw: Any) -> str | None:
    value = str(raw or "").strip()
    if not value:
        return None
    if value.startswith("//"):
        value = f"https:{value}"
    if "{size}" in value:
        value = value.replace("{size}", "XXXL")
    if "/%s" in value:
        value = value.replace("/%s", "/XXXL")
    elif "%s" in value:
        value = value.replace("%s", "XXXL")
    return value


def _extract_first_phone_from_raw(raw_phone: Any) -> str | None:
    if raw_phone is None:
        return None
    if isinstance(raw_phone, str):
        value = raw_phone.strip()
        return value or None
    if isinstance(raw_phone, list):
        for item in raw_phone:
            if isinstance(item, str) and item.strip():
                return item.strip()
            if isinstance(item, dict):
                for key in ("phone", "number", "formatted", "value"):
                    candidate = str(item.get(key) or "").strip()
                    if candidate:
                        return candidate
    if isinstance(raw_phone, dict):
        for key in ("phone", "number", "formatted", "value"):
            candidate = str(raw_phone.get(key) or "").strip()
            if candidate:
                return candidate
    return None


def _extract_contact_from_social_links(raw_links: Any) -> tuple[str | None, str | None]:
    telegram_url = None
    whatsapp_url = None
    if not isinstance(raw_links, list):
        return telegram_url, whatsapp_url
    for item in raw_links:
        candidate = ""
        if isinstance(item, str):
            candidate = item.strip()
        elif isinstance(item, dict):
            candidate = str(item.get("url") or item.get("href") or item.get("link") or "").strip()
        if not candidate:
            continue
        low = candidate.lower()
        if not telegram_url and ("t.me/" in low or "telegram.me/" in low):
            telegram_url = _normalize_contact_url(candidate)
        if not whatsapp_url and ("wa.me/" in low or "whatsapp.com/" in low or "api.whatsapp.com/" in low):
            whatsapp_url = _normalize_contact_url(candidate)
    return telegram_url, whatsapp_url


def _extract_apify_menu_preview(raw_menu: Any, limit: int | None = 20) -> list[dict[str, Any]]:
    if not isinstance(raw_menu, dict):
        return []
    raw_items = raw_menu.get("items")
    if not isinstance(raw_items, list):
        return []
    result: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("name") or "").strip()
        if not title:
            continue
        result.append(
            {
                "title": title,
                "description": str(item.get("description") or "").strip() or None,
                "price": str(item.get("price") or "").strip() or None,
                "currency": str(item.get("currency") or "").strip() or None,
                "category": str(item.get("category") or "").strip() or None,
                "photo_url": str(item.get("photoUrl") or "").strip() or None,
            }
        )
        if limit is not None and len(result) >= max(1, limit):
            break
    return result


def _normalize_partnership_file_row(
    row: dict[str, Any],
    *,
    default_city: str | None,
    default_category: str | None,
) -> tuple[dict[str, Any] | None, str | None]:
    name = _pick_first_value(
        row,
        ["name", "title", "shortTitle", "company", "company_name", "название", "компания"],
    ) or "Новый партнёр"
    source_url = _pick_first_value(
        row,
        [
            "source_url",
            "url",
            "link",
            "map_url",
            "maps_url",
            "yandex_url",
            "source",
            "ссылка",
            "ссылка_на_карту",
            "карта",
        ],
    )
    if not source_url:
        return None, "missing source_url/link"

    address = _pick_first_value(row, ["address", "additionalAddress", "адрес", "location", "локация"])
    city = _pick_first_value(row, ["city", "город"]) or (default_city or None)
    category = _pick_first_value(row, ["category", "категория"]) or (
        row.get("categories")[0] if isinstance(row.get("categories"), list) and row.get("categories") else None
    ) or (default_category or None)
    phone = _pick_first_value(row, ["phone", "телефон"]) or _extract_first_phone_from_raw(row.get("phones"))
    email = _pick_first_value(row, ["email", "почта", "e-mail"])
    website = _pick_first_value(row, ["website", "websiteUrl", "site", "сайт"])
    telegram_url = _normalize_contact_url(
        _pick_first_value(row, ["telegram_url", "telegram", "tg", "tg_url", "телеграм"])
    )
    whatsapp_url = _normalize_contact_url(
        _pick_first_value(row, ["whatsapp_url", "whatsapp", "wa", "wa_url", "ватсап"])
    )
    social_telegram, social_whatsapp = _extract_contact_from_social_links(row.get("socialLinks"))
    if not telegram_url:
        telegram_url = social_telegram
    if not whatsapp_url:
        whatsapp_url = social_whatsapp

    rating = _safe_float(_pick_first_value(row, ["rating", "рейтинг"]))
    reviews_count = _safe_int(
        _pick_first_value(
            row,
            ["reviews_count", "reviewCount", "ratingsCount", "reviews", "отзывов", "количество_отзывов"],
        )
    )
    is_verified = row.get("isVerifiedOwner")
    if not isinstance(is_verified, bool):
        is_verified = row.get("is_verified")
    if not isinstance(is_verified, bool):
        is_verified = None

    logo_url = _normalize_media_url(_pick_first_value(row, ["logo_url", "logoUrl", "logo", "avatar"]))
    photos_raw = row.get("photos")
    photos: list[str] = []
    if isinstance(photos_raw, list):
        for item in photos_raw:
            if isinstance(item, str) and item.strip():
                normalized_photo = _normalize_media_url(item.strip())
                if normalized_photo:
                    photos.append(normalized_photo)
            elif isinstance(item, dict):
                photo_url = _normalize_media_url(item.get("url") or item.get("src") or item.get("photoUrl"))
                if photo_url:
                    photos.append(photo_url)
    if not photos:
        photo_template = _normalize_media_url(row.get("photoUrlTemplate"))
        if photo_template:
            photos.append(photo_template)

    menu_full = _extract_apify_menu_preview(row.get("menu"), limit=None)
    menu_preview = menu_full[:20]
    services_with_price_count = sum(1 for item in menu_full if str(item.get("price") or "").strip())
    reviews_raw = row.get("reviews")
    reviews_preview: list[dict[str, Any]] = []
    if isinstance(reviews_raw, list):
        for item in reviews_raw[:20]:
            if not isinstance(item, dict):
                continue
            review_text = str(item.get("text") or "").strip()
            if not review_text:
                continue
            reviews_preview.append(
                {
                    "review": review_text,
                    "rating": item.get("rating"),
                    "author": item.get("authorName"),
                    "business_comment": item.get("businessComment"),
                    "date": item.get("date"),
                }
            )

    normalized = {
        "name": name,
        "source_url": str(source_url).strip(),
        "address": address,
        "city": city,
        "category": category,
        "phone": phone,
        "email": email,
        "website": website,
        "telegram_url": telegram_url,
        "whatsapp_url": whatsapp_url,
        "rating": rating,
        "reviews_count": reviews_count,
        "search_payload": {
            "import_format": "apify_yandex_json" if ("logoUrl" in row or "menu" in row or "reviewCount" in row) else "file_row",
            "logo_url": logo_url,
            "photos": photos[:20],
            "menu_preview": menu_preview,
            "menu_full": menu_full,
            "services_total_count": len(menu_full),
            "services_with_price_count": services_with_price_count,
            "reviews_preview": reviews_preview,
            "social_links": row.get("socialLinks") if isinstance(row.get("socialLinks"), list) else [],
            "source_row_url": row.get("url"),
            "source_business_id": row.get("businessId"),
            "is_verified": is_verified,
            "paid_promotion_detected": _contains_paid_promotion_signal(row),
        },
    }
    return normalized, None


def _parse_partnership_file_content(file_format: str, content: str) -> list[dict[str, Any]]:
    fmt = (file_format or "").strip().lower()
    if fmt in {"json", "jsonl"}:
        if fmt == "jsonl":
            rows: list[dict[str, Any]] = []
            for ln in (content or "").splitlines():
                line = ln.strip()
                if not line:
                    continue
                obj = json.loads(line)
                if isinstance(obj, dict):
                    rows.append(obj)
            return rows
        payload = json.loads(content or "[]")
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in ("items", "leads", "data", "results"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        return []

    if fmt == "csv":
        raw = content or ""
        sample = raw[:2048]
        delimiter = ";"
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            delimiter = dialect.delimiter
        except Exception:
            delimiter = ";" if sample.count(";") >= sample.count(",") else ","
        reader = csv.DictReader(io.StringIO(raw), delimiter=delimiter)
        return [dict(row or {}) for row in reader]

    raise ValueError("unsupported format; use csv/json/jsonl")


def _run_search_job(job_id: str, source: str, actor_id: str, query: str, location: str, search_limit: int) -> None:
    _update_search_job(job_id, status="running", error_text=None)
    try:
        service = ProspectingService(source=source, actor_id_override=actor_id)
        run_meta = service.start_search_run(query, location, search_limit)
        _update_search_job(
            job_id,
            status="running",
            error_text=None,
            results_json={
                "_apify": {
                    "run_id": run_meta.get("run_id"),
                    "dataset_id": run_meta.get("dataset_id"),
                    "status": run_meta.get("status"),
                }
            },
        )
    except Exception as exc:
        if "timed out" in str(exc).lower():
            _update_search_job(
                job_id,
                status="running",
                error_text=None,
                results_json={"_apify": {"status": "START_PENDING"}},
            )
            return
        print(f"Error in async prospecting search job {job_id}: {exc}")
        _update_search_job(job_id, status="failed", error_text=str(exc))


def _refresh_search_job_from_apify(row: dict[str, Any]) -> dict[str, Any]:
    status = (row.get("status") or "").strip().lower()
    if status not in {"queued", "running"}:
        return row

    results_blob = row.get("results_json")
    apify_meta = None
    if isinstance(results_blob, dict):
        apify_meta = results_blob.get("_apify")
    if not isinstance(apify_meta, dict):
        return row

    run_id = apify_meta.get("run_id")
    dataset_id = apify_meta.get("dataset_id")
    if not run_id:
        try:
            source = str(row.get("source") or "apify_yandex").strip().lower()
            actor_id = str(row.get("actor_id") or "").strip() or None
            service = ProspectingService(source=source, actor_id_override=actor_id)
            run_meta = service.start_search_run(
                row.get("query") or "",
                row.get("location") or "",
                int(row.get("search_limit") or 50),
            )
            _update_search_job(
                row["id"],
                status="running",
                error_text=None,
                results_json={
                    "_apify": {
                        "run_id": run_meta.get("run_id"),
                        "dataset_id": run_meta.get("dataset_id"),
                        "status": run_meta.get("status"),
                    }
                },
            )
            refreshed = _get_search_job(row["id"])
            return dict(refreshed) if refreshed else row
        except Exception as exc:
            if "timed out" in str(exc).lower():
                _update_search_job(
                    row["id"],
                    status="running",
                    error_text=None,
                    results_json={"_apify": {"status": "START_PENDING"}},
                )
                refreshed = _get_search_job(row["id"])
                return dict(refreshed) if refreshed else {**row, "status": "running", "error_text": None}
            print(f"Error starting Apify search job {row.get('id')}: {exc}")
            _update_search_job(row["id"], status="failed", error_text=str(exc))
            refreshed = _get_search_job(row["id"])
            return dict(refreshed) if refreshed else {**row, "status": "failed", "error_text": str(exc)}

    try:
        source = str(row.get("source") or "apify_yandex").strip().lower()
        actor_id = str(row.get("actor_id") or "").strip() or None
        service = ProspectingService(source=source, actor_id_override=actor_id)
        run_info = service.get_run(run_id)
        run_status = (run_info.get("status") or "").strip().upper()
        dataset_id = run_info.get("defaultDatasetId") or dataset_id

        if run_status in {"SUCCEEDED"}:
            results = service.fetch_dataset_items(dataset_id, compact=True)
            compact_results = _compact_search_results_for_storage(results)
            import_meta = _import_search_results_into_leads(job_row=row, results=compact_results)
            _update_search_job(
                row["id"],
                status="completed",
                result_count=len(compact_results),
                results_json=compact_results,
                error_text=None,
            )
            refreshed = _get_search_job(row["id"])
            refreshed_row = dict(refreshed) if refreshed else row
            if isinstance(refreshed_row.get("results_json"), list):
                refreshed_row["results_json"] = refreshed_row["results_json"]
            refreshed_row["imported_count"] = int(import_meta.get("imported_count") or 0)
            refreshed_row["merged_count"] = int(import_meta.get("merged_count") or 0)
            refreshed_row["import_business_id"] = import_meta.get("business_id")
            return refreshed_row
        elif run_status in {"FAILED", "ABORTED", "TIMED-OUT"}:
            status_message = (
                run_info.get("statusMessage")
                or run_info.get("status_message")
                or f"Apify run {run_status.lower()}"
            )
            _update_search_job(
                row["id"],
                status="failed",
                error_text=str(status_message),
                results_json={"_apify": {"run_id": run_id, "dataset_id": dataset_id, "status": run_status}},
            )
        else:
            _update_search_job(
                row["id"],
                status="running",
                error_text=None,
                results_json={"_apify": {"run_id": run_id, "dataset_id": dataset_id, "status": run_status}},
            )
        refreshed = _get_search_job(row["id"])
        return dict(refreshed) if refreshed else row
    except Exception as exc:
        if "timed out" in str(exc).lower():
            _update_search_job(
                row["id"],
                status="running",
                error_text=None,
                results_json={"_apify": {"run_id": run_id, "dataset_id": dataset_id, "status": "RUNNING"}},
            )
            refreshed = _get_search_job(row["id"])
            return dict(refreshed) if refreshed else {**row, "status": "running", "error_text": None}
        print(f"Error polling Apify search job {row.get('id')}: {exc}")
        return row


def _mark_search_job_failed_if_stale(row: dict[str, Any]) -> dict[str, Any]:
    row = _refresh_search_job_from_apify(row)
    status = (row.get("status") or "").strip().lower()
    if status not in {"queued", "running"}:
        return row

    results_blob = row.get("results_json")
    apify_meta = None
    if isinstance(results_blob, dict):
        apify_meta = results_blob.get("_apify")
    apify_status = ""
    if isinstance(apify_meta, dict):
        apify_status = str(apify_meta.get("status") or "").strip().upper()

    deadline_anchor = row.get("created_at") if apify_status == "START_PENDING" else (row.get("updated_at") or row.get("created_at"))
    if not isinstance(deadline_anchor, datetime):
        return row

    if deadline_anchor.tzinfo is None:
        deadline_anchor = deadline_anchor.replace(tzinfo=timezone.utc)

    deadline = deadline_anchor + timedelta(seconds=SEARCH_JOB_TIMEOUT_SEC)
    if datetime.now(timezone.utc) <= deadline:
        return row

    if apify_status == "START_PENDING":
        stale_error = f"Apify actor did not acknowledge start within {SEARCH_JOB_TIMEOUT_SEC} seconds"
    else:
        stale_error = f"Search timed out after {SEARCH_JOB_TIMEOUT_SEC} seconds"
    _update_search_job(row["id"], status="failed", error_text=stale_error)
    refreshed = _get_search_job(row["id"])
    return dict(refreshed) if refreshed else {**row, "status": "failed", "error_text": stale_error}


def _expire_stale_search_jobs() -> None:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, status, error_text, created_at, updated_at
            FROM outreachsearchjobs
            WHERE status IN ('queued', 'running')
            """
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    for row in rows:
        _mark_search_job_failed_if_stale(dict(row))


def _generate_first_message_draft(lead: dict[str, Any], channel: str) -> dict[str, str]:
    language = _resolve_outreach_language(lead)
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
    if language == "en":
        angle = f"noticed that {company_name} has {', '.join(weak_points[:2])} in Google/Maps listings"
        money_hint = "In our model this can cost a business part of its inbound requests each month."
    elif language == "tr":
        angle = f"{company_name} için harita kartında {', '.join(weak_points[:2])} olduğunu fark ettik"
        money_hint = "Modelimize göre bu, aylık gelen taleplerin bir kısmına mal olabilir."
    elif language == "el":
        angle = f"παρατηρήσαμε ότι για {company_name} υπάρχουν {', '.join(weak_points[:2])} στην κάρτα χαρτών"
        money_hint = "Στο μοντέλο μας αυτό μπορεί να κοστίζει μέρος των εισερχόμενων αιτημάτων κάθε μήνα."

    if language == "en":
        if channel == "telegram":
            opening = f"Hi! We reviewed {company_name}'s listing"
            cta = "If you'd like, I can share a short audit with quick wins."
        elif channel == "whatsapp":
            opening = f"Hi! We reviewed {company_name}'s listing"
            cta = "I can send a short audit with concrete growth points if that's relevant."
        elif channel == "email":
            opening = f"Hello! We reviewed {company_name}'s listing."
            cta = "If useful, we can share a short audit with concrete fixes and expected impact."
        else:
            opening = f"Hello. We reviewed {company_name}'s listing."
            cta = "If helpful, I can share a short audit and explain the highest-impact fixes."
        location_line = f" We see you in \"{category}\"{f' in {city}' if city else ''}."
    elif language == "tr":
        if channel == "telegram":
            opening = f"Merhaba! {company_name} kartını inceledik"
            cta = "İsterseniz kısa bir denetim ve hızlı kazanımlar gönderebilirim."
        elif channel == "whatsapp":
            opening = f"Merhaba! {company_name} kartını inceledik"
            cta = "Uygunsa net öneriler içeren kısa bir analiz paylaşabilirim."
        elif channel == "email":
            opening = f"Merhaba! {company_name} kartını inceledik."
            cta = "İsterseniz kısa bir analiz ve etkisini paylaşabiliriz."
        else:
            opening = f"Merhaba. {company_name} kartını inceledik."
            cta = "Uygunsa kısa bir analiz ve yüksek etkili düzeltmeleri paylaşabilirim."
        location_line = f" \"{category}\"{f' ({city})' if city else ''} alanında görünüyor."
    elif language == "el":
        if channel == "telegram":
            opening = f"Γεια σας! Ελέγξαμε την καταχώριση του {company_name}"
            cta = "Αν θέλετε, μπορώ να στείλω μια σύντομη ανάλυση με άμεσες βελτιώσεις."
        elif channel == "whatsapp":
            opening = f"Γεια σας! Ελέγξαμε την καταχώριση του {company_name}"
            cta = "Αν είναι σχετικό, μπορώ να στείλω μια σύντομη ανάλυση με συγκεκριμένα σημεία."
        elif channel == "email":
            opening = f"Γεια σας! Ελέγξαμε την καταχώριση του {company_name}."
            cta = "Αν σας ενδιαφέρει, μπορώ να στείλω μια σύντομη ανάλυση με προτεραιότητες."
        else:
            opening = f"Γεια σας. Ελέγξαμε την καταχώριση του {company_name}."
            cta = "Αν σας βολεύει, μπορώ να στείλω μια σύντομη ανάλυση και τις πιο σημαντικές βελτιώσεις."
        location_line = f" Σας βλέπουμε στην κατηγορία «{category}»{f' στο {city}' if city else ''}."
    else:
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

    return _generate_outreach_message_ai(
        lead=lead,
        preview={
            "summary_text": angle,
            "findings": [{"title": item} for item in weak_points[:3]],
            "recommended_actions": [],
            "revenue_potential": {},
        },
        channel=channel,
        fallback_message=draft_text,
        fallback_angle_type="maps_growth",
        fallback_tone="professional",
    )


def _generate_audit_first_message_draft(
    lead: dict[str, Any],
    preview: dict[str, Any],
    channel: str,
) -> dict[str, str]:
    language = _resolve_outreach_language(lead)
    company_name = (lead.get("name") or "вашей компании").strip()
    category = (lead.get("category") or "локального бизнеса").strip()
    city = (lead.get("city") or "").strip()

    findings = preview.get("findings") or []
    recommended_actions = preview.get("recommended_actions") or []
    public_audit_url = str(lead.get("public_audit_url") or "").strip()

    top_findings = [str(item.get("title") or "").strip() for item in findings if isinstance(item, dict)]
    top_findings = [item for item in top_findings if item][:2]
    key_issue = ", ".join(top_findings) if top_findings else "есть резерв роста карточки"

    top_action = ""
    for item in recommended_actions:
        if isinstance(item, dict):
            top_action = str(item.get("title") or "").strip()
            if top_action:
                break
    if not top_action:
        top_action = "быстрое усиление карточки по услугам и контенту"

    if language == "en":
        if channel == "telegram":
            message_lines = [
                f"Hi! {company_name} is likely missing customers from maps.",
                f"We reviewed the listing and see {key_issue.lower()}.",
            ]
            if public_audit_url:
                message_lines.append(f"Short audit: {public_audit_url}")
            message_lines.append("If relevant, we can implement the fixes and help grow map traffic.")
            message_lines.append("Would you like me to send the key steps here?")
        elif channel == "whatsapp":
            message_lines = [
                f"Hi! {company_name} is likely missing customers from maps.",
                f"We reviewed the listing and see {key_issue.lower()}.",
            ]
            if public_audit_url:
                message_lines.append(f"Short audit: {public_audit_url}")
            message_lines.append("If relevant, we can implement the fixes and help grow map traffic.")
            message_lines.append("Would this be interesting?")
        elif channel == "email":
            message_lines = [
                f"Hello! {company_name} is likely missing customers from maps.",
                f"We reviewed the listing and see {key_issue.lower()}.",
            ]
            if public_audit_url:
                message_lines.append(f"I made a short audit with the main fixes: {public_audit_url}")
            else:
                message_lines.append("I made a short audit with the main fixes.")
            message_lines.append("We can implement this for you and help bring more customers from maps.")
            message_lines.append("Would that be relevant?")
        else:
            message_lines = [
                f"Hello! {company_name} is likely missing customers from maps.",
                f"We reviewed the listing and see {key_issue.lower()}.",
            ]
            if public_audit_url:
                message_lines.append(f"Short audit: {public_audit_url}")
            message_lines.append("We can implement the fixes and help grow map traffic.")
            message_lines.append("Would that be relevant?")
    elif language == "tr":
        if channel == "telegram":
            message_lines = [
                f"Merhaba! {company_name} haritalardan müşteri kaçırıyor olabilir.",
                f"Kartı inceledik ve {key_issue.lower()} gördük.",
            ]
            if public_audit_url:
                message_lines.append(f"Kısa denetim: {public_audit_url}")
            message_lines.append("İsterseniz bunu sizin için uygulayıp haritalardan daha fazla müşteri getirebiliriz.")
            message_lines.append("İlgilenir misiniz?")
        elif channel == "whatsapp":
            message_lines = [
                f"Merhaba! {company_name} haritalardan müşteri kaçırıyor olabilir.",
                f"Kartı inceledik ve {key_issue.lower()} gördük.",
            ]
            if public_audit_url:
                message_lines.append(f"Kısa denetim: {public_audit_url}")
            message_lines.append("İsterseniz bunu sizin için uygulayıp haritalardan daha fazla müşteri getirebiliriz.")
            message_lines.append("Uygun olur mu?")
        elif channel == "email":
            message_lines = [
                f"Merhaba! {company_name} haritalardan müşteri kaçırıyor olabilir.",
                f"Kartı inceledik ve {key_issue.lower()} gördük.",
            ]
            if public_audit_url:
                message_lines.append(f"Ana düzeltmeleri içeren kısa bir denetim hazırladım: {public_audit_url}")
            else:
                message_lines.append("Ana düzeltmeleri içeren kısa bir denetim hazırladım.")
            message_lines.append("İsterseniz bunu sizin için uygulayıp haritalardan daha fazla müşteri getirebiliriz.")
            message_lines.append("İlginizi çeker mi?")
        else:
            message_lines = [
                f"Merhaba! {company_name} haritalardan müşteri kaçırıyor olabilir.",
                f"Kartı inceledik ve {key_issue.lower()} gördük.",
            ]
            if public_audit_url:
                message_lines.append(f"Kısa denetim: {public_audit_url}")
            message_lines.append("İsterseniz bunu sizin için uygulayıp haritalardan daha fazla müşteri getirebiliriz.")
            message_lines.append("İlginizi çeker mi?")
    elif language == "el":
        if channel == "telegram":
            message_lines = [
                f"Γεια σας! Το {company_name} μάλλον χάνει πελάτες από τους χάρτες.",
                f"Ελέγξαμε την καταχώριση και βλέπουμε {key_issue.lower()}.",
            ]
            if public_audit_url:
                message_lines.append(f"Σύντομος έλεγχος: {public_audit_url}")
            message_lines.append("Αν θέλετε, μπορούμε να το υλοποιήσουμε για εσάς και να αυξήσουμε την κίνηση από τους χάρτες.")
            message_lines.append("Θα σας ενδιέφερε;")
        elif channel == "whatsapp":
            message_lines = [
                f"Γεια σας! Το {company_name} μάλλον χάνει πελάτες από τους χάρτες.",
                f"Ελέγξαμε την καταχώριση και βλέπουμε {key_issue.lower()}.",
            ]
            if public_audit_url:
                message_lines.append(f"Σύντομος έλεγχος: {public_audit_url}")
            message_lines.append("Αν θέλετε, μπορούμε να το υλοποιήσουμε για εσάς και να αυξήσουμε την κίνηση από τους χάρτες.")
            message_lines.append("Σας ενδιαφέρει;")
        elif channel == "email":
            message_lines = [
                f"Γεια σας! Το {company_name} μάλλον χάνει πελάτες από τους χάρτες.",
                f"Ελέγξαμε την καταχώριση και βλέπουμε {key_issue.lower()}.",
            ]
            if public_audit_url:
                message_lines.append(f"Έφτιαξα έναν σύντομο έλεγχο με τις βασικές διορθώσεις: {public_audit_url}")
            else:
                message_lines.append("Έφτιαξα έναν σύντομο έλεγχο με τις βασικές διορθώσεις.")
            message_lines.append("Μπορούμε να το εφαρμόσουμε για εσάς και να αυξήσουμε την κίνηση από τους χάρτες.")
            message_lines.append("Θα είχε ενδιαφέρον;")
        else:
            message_lines = [
                f"Γεια σας! Το {company_name} μάλλον χάνει πελάτες από τους χάρτες.",
                f"Ελέγξαμε την καταχώριση και βλέπουμε {key_issue.lower()}.",
            ]
            if public_audit_url:
                message_lines.append(f"Σύντομος έλεγχος: {public_audit_url}")
            message_lines.append("Μπορούμε να το εφαρμόσουμε για εσάς και να αυξήσουμε την κίνηση από τους χάρτες.")
            message_lines.append("Θα σας ενδιέφερε;")
    else:
        if channel == "telegram":
            message_lines = [
                "Здравствуйте! Вы сейчас недополучаете клиентов с карт.",
                f"Посмотрели карточку {company_name} и видим: {key_issue.lower()}.",
            ]
            if public_audit_url:
                message_lines.append(f"Сделал короткий разбор: {public_audit_url}")
            message_lines.append("Можем внедрить это под ключ и привести больше клиентов с карт.")
            message_lines.append("Вам может быть это интересно?")
        elif channel == "whatsapp":
            message_lines = [
                "Здравствуйте! Вы сейчас недополучаете клиентов с карт.",
                f"Посмотрели карточку {company_name} и видим: {key_issue.lower()}.",
            ]
            if public_audit_url:
                message_lines.append(f"Короткий разбор здесь: {public_audit_url}")
            message_lines.append("Можем внедрить это под ключ и привести больше клиентов с карт.")
            message_lines.append("Это может быть актуально?")
        elif channel == "email":
            message_lines = [
                "Здравствуйте! Вы сейчас недополучаете клиентов с карт.",
                f"Посмотрели карточку {company_name} и видим: {key_issue.lower()}.",
            ]
            if public_audit_url:
                message_lines.append(f"Сделал короткий разбор, как это исправить: {public_audit_url}")
            else:
                message_lines.append("Сделал короткий разбор, как это исправить.")
            message_lines.append("Можем внедрить это под ключ и привести больше клиентов с карт.")
            message_lines.append("Вам может быть это интересно?")
        else:
            message_lines = [
                "Здравствуйте! Вы сейчас недополучаете клиентов с карт.",
                f"Посмотрели карточку {company_name} и видим: {key_issue.lower()}.",
            ]
            if public_audit_url:
                message_lines.append(f"Короткий разбор: {public_audit_url}")
            message_lines.append("Можем внедрить это под ключ и привести больше клиентов с карт.")
            message_lines.append("Вам может быть это интересно?")

    return _generate_outreach_message_ai(
        lead=lead,
        preview=preview,
        channel=channel,
        fallback_message="\n".join(message_lines).strip(),
        fallback_angle_type="audit_preview",
        fallback_tone="professional",
    )


def _deterministic_issue_hint_from_preview(preview: dict[str, Any]) -> str:
    findings = preview.get("findings") if isinstance(preview.get("findings"), list) else []
    titles = [str(item.get("title") or "").strip() for item in findings if isinstance(item, dict)]
    titles = [item for item in titles if item]
    if titles:
        hint = re.sub(r"\s+", " ", titles[0]).strip(" .")
        if hint:
            return hint[:1].lower() + hint[1:] + "."
    current_state = preview.get("current_state") if isinstance(preview.get("current_state"), dict) else {}
    services_count = int(current_state.get("services_count") or 0)
    photos_count = int(current_state.get("photos_count") or 0)
    has_website = bool(current_state.get("has_website"))
    reviews_count = int(current_state.get("reviews_count") or 0)
    rating = current_state.get("rating")
    if services_count <= 0:
        return "в карточке нет понятной структуры услуг."
    if photos_count <= 1:
        return "в карточке слишком мало фото, чтобы продавать качество услуг."
    if not has_website:
        return "в карточке не хватает контактов и маршрута к записи."
    if rating is None or reviews_count <= 0:
        return "карточка слабо закрывает доверие через рейтинг и отзывы."
    return "карточка не полностью работает на поиск и запись."


def _generate_superadmin_deterministic_first_message(
    lead: dict[str, Any],
    preview: dict[str, Any],
) -> dict[str, str]:
    public_audit_url = str(lead.get("public_audit_url") or "").strip()
    company_name = str(lead.get("name") or "ваш бизнес").strip() or "ваш бизнес"
    issue_hint = _deterministic_issue_hint_from_preview(preview)
    message_lines = [
        "Здравствуйте!",
        "",
        f"Нашёл {company_name} на картах - вижу, что у вас часть клиентов теряется.",
        f"Например, {issue_hint}",
        "",
        "Разобрал вашу карточку и показал конкретные причины и шаги, как исправить самостоятельно:",
        public_audit_url or "https://localos.pro",
        "Это обычно даёт +30-80% к обращениям без рекламы.",
        "",
        "Или, хотите, настрою всё, до результата?",
    ]
    return {
        "angle_type": "audit_preview",
        "tone": "professional",
        "generated_text": "\n".join(message_lines).strip(),
        "prompt_key": "outreach_first_message",
        "prompt_version": "deterministic_v1",
        "prompt_source": "deterministic",
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


def _serialize_batch_row(row: dict[str, Any]) -> dict[str, Any]:
    payload = dict(row)
    payload["items"] = []
    return payload


def _load_prospecting_lead(lead_id: str) -> dict[str, Any] | None:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM prospectingleads WHERE id = %s", (lead_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _get_table_columns(table_name: str) -> set[str]:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            """,
            (table_name,),
        )
        cols = set()
        for row in cur.fetchall():
            if hasattr(row, "get"):
                col = row.get("column_name")
            else:
                col = row[0] if row else None
            if col:
                cols.add(str(col))
        return cols
    finally:
        conn.close()


def _extract_yandex_org_id_from_url(url: Any) -> str:
    import re

    text = str(url or "").strip()
    if not text:
        return ""
    match = re.search(r"/org/(?:[^/]+/)?(\d+)", text)
    return match.group(1) if match else ""


def _extract_google_place_id_from_url(url: Any) -> str:
    text = str(url or "").strip()
    if not text:
        return ""
    patterns = (
        r"cid=(\d+)",
        r"!1s(0x[0-9a-f]+:0x[0-9a-f]+)",
        r"query_place_id=([^&]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return str(match.group(1) or "").strip()
    return ""


def _normalize_identity_text(value: Any) -> str:
    text = str(value or "").strip().lower().replace("ё", "е")
    text = unquote(text)
    text = re.sub(r"https?://", "", text)
    text = re.sub(r"[^a-z0-9а-я]+", " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def _identity_similarity(left: Any, right: Any) -> float:
    left_text = _normalize_identity_text(left)
    right_text = _normalize_identity_text(right)
    if not left_text or not right_text:
        return 0.0
    if left_text == right_text:
        return 1.0
    return SequenceMatcher(None, left_text, right_text).ratio()


def _lead_expected_external_id(lead: dict[str, Any]) -> str:
    source_url = str(lead.get("source_url") or "").strip()
    source_url_lower = source_url.lower()
    return str(
        lead.get("external_source_id")
        or lead.get("source_external_id")
        or lead.get("external_place_id")
        or lead.get("google_id")
        or (_extract_google_place_id_from_url(source_url) if "google." in source_url_lower or "maps.app.goo.gl" in source_url_lower else "")
        or _extract_yandex_org_id_from_url(source_url)
        or ""
    ).strip()


def _lead_identity_matches_candidate(
    lead: dict[str, Any],
    *,
    candidate_name: Any,
    candidate_city: Any,
    candidate_source_url: Any = None,
    candidate_external_id: Any = None,
) -> bool:
    expected_external_id = _lead_expected_external_id(lead)
    strong_expected_id = len(expected_external_id) >= 6
    candidate_external = str(candidate_external_id or "").strip()
    if strong_expected_id and candidate_external and expected_external_id.lower() != candidate_external.lower():
        return False

    lead_city = _normalize_identity_text(lead.get("city") or lead.get("address"))
    candidate_city_text = _normalize_identity_text(candidate_city)
    if (
        lead_city
        and candidate_city_text
        and lead_city not in candidate_city_text
        and candidate_city_text not in lead_city
        and not (strong_expected_id and candidate_external)
    ):
        return False

    lead_name = str(lead.get("name") or "").strip()
    candidate_name_text = str(candidate_name or "").strip()
    if lead_name and candidate_name_text and _identity_similarity(lead_name, candidate_name_text) < 0.42:
        return False

    source_url = normalize_map_url(str(lead.get("source_url") or "").strip())
    candidate_url = normalize_map_url(str(candidate_source_url or "").strip())
    if source_url and candidate_url and "yandex." in source_url and "yandex." in candidate_url:
        expected_org_id = _extract_yandex_org_id_from_url(source_url)
        candidate_org_id = _extract_yandex_org_id_from_url(candidate_url)
        if expected_org_id and candidate_org_id and expected_org_id != candidate_org_id:
            return False

    return True


def _extract_links_recursive(value: Any) -> list[str]:
    links: list[str] = []

    def _walk(node: Any) -> None:
        if node is None:
            return
        if isinstance(node, str):
            raw = node.strip()
            if raw:
                links.append(raw)
            return
        if isinstance(node, dict):
            for item in node.values():
                _walk(item)
            return
        if isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(value)
    deduped: list[str] = []
    seen = set()
    for item in links:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _extract_parsed_contacts(card_overview: Any) -> dict[str, str | list[str] | None]:
    overview = card_overview if isinstance(card_overview, dict) else {}
    social_links = _extract_links_recursive(overview.get("social_links"))
    telegram_url = None
    whatsapp_url = None
    email = None
    for item in social_links:
        low = item.lower()
        if not telegram_url and ("t.me/" in low or "telegram.me/" in low):
            telegram_url = item
        if not whatsapp_url and ("wa.me/" in low or "whatsapp.com/" in low or "api.whatsapp.com/" in low):
            whatsapp_url = item
        if not email:
            if low.startswith("mailto:"):
                email = item.split(":", 1)[1].strip()
            elif "@" in item and " " not in item and "/" not in item:
                email = item
    return {
        "telegram_url": telegram_url,
        "whatsapp_url": whatsapp_url,
        "email": email,
        "social_links": social_links,
    }


def _update_lead_business_link(lead_id: str, business_id: str) -> None:
    columns = _get_table_columns("prospectingleads")
    if "business_id" not in columns:
        return
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE prospectingleads
            SET business_id = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (business_id, lead_id),
        )
        conn.commit()
    finally:
        conn.close()


def _sync_lead_business_link_from_parse_history(lead: dict[str, Any]) -> dict[str, Any]:
    """Ensure lead.business_id points to latest parsed business for this lead URL/org."""
    lead_id = str(lead.get("id") or "").strip()
    if not lead_id:
        return lead

    source_url = str(lead.get("source_url") or "").strip()
    source_external_id = str(
        lead.get("source_external_id")
        or lead.get("google_id")
        or _extract_yandex_org_id_from_url(source_url)
        or ""
    ).strip()
    current_business_id = str(lead.get("business_id") or "").strip()

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'parsequeue'
            """
        )
        parsequeue_columns = {
            str(row.get("column_name") if hasattr(row, "get") else row[0])
            for row in (cur.fetchall() or [])
            if (row.get("column_name") if hasattr(row, "get") else (row[0] if row else None))
        }
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'businesses'
            """
        )
        business_columns = {
            str(row.get("column_name") if hasattr(row, "get") else row[0])
            for row in (cur.fetchall() or [])
            if (row.get("column_name") if hasattr(row, "get") else (row[0] if row else None))
        }

        if current_business_id:
            cur.execute("SELECT 1 FROM businesses WHERE id = %s LIMIT 1", (current_business_id,))
            if cur.fetchone():
                return lead

        filters: list[str] = ["pq.business_id IS NOT NULL", "pq.status IN ('completed', 'done')"]
        params: list[Any] = []

        if source_url:
            filters.append("(pq.url = %s OR pq.url ILIKE %s)")
            params.extend([source_url, f"%{source_external_id}%"] if source_external_id else [source_url, source_url])

        if source_external_id and "url" in parsequeue_columns:
            filters.append("pq.url ILIKE %s")
            params.append(f"%{source_external_id}%")

        if not source_url and not source_external_id:
            return lead

        where_sql = " OR ".join(f"({flt})" for flt in filters[2:]) if len(filters) > 2 else ""
        if where_sql:
            where_sql = f"({where_sql}) AND " + " AND ".join(filters[:2])
        else:
            where_sql = " AND ".join(filters)

        cur.execute(
            f"""
            SELECT pq.business_id
            FROM parsequeue pq
            WHERE {where_sql}
            ORDER BY pq.updated_at DESC NULLS LAST, pq.created_at DESC
            LIMIT 1
            """,
            params,
        )
        row = cur.fetchone()
        matched_business_id = str((row.get("business_id") if hasattr(row, "get") else (row[0] if row else "")) or "").strip()
        if not matched_business_id:
            return lead

        if matched_business_id == current_business_id:
            return lead

        business_select_fields = ["id", "name", "city"]
        if "yandex_url" in business_columns:
            business_select_fields.append("yandex_url")
        if "yandex_org_id" in business_columns:
            business_select_fields.append("yandex_org_id")
        cur.execute(
            f"""
            SELECT {", ".join(business_select_fields)}
            FROM businesses
            WHERE id = %s
            LIMIT 1
            """,
            (matched_business_id,),
        )
        business_row = cur.fetchone()
        candidate_business = dict(business_row) if business_row else {}
        if candidate_business and not _lead_identity_matches_candidate(
            lead,
            candidate_name=candidate_business.get("name"),
            candidate_city=candidate_business.get("city"),
            candidate_source_url=candidate_business.get("yandex_url"),
            candidate_external_id=candidate_business.get("yandex_org_id"),
        ):
            return lead

        cur.execute(
            """
            UPDATE prospectingleads
            SET business_id = %s,
                updated_at = NOW()
            WHERE id = %s
            RETURNING *
            """,
            (matched_business_id, lead_id),
        )
        updated = cur.fetchone()
        if updated:
            conn.commit()
            return dict(updated)
        return lead
    finally:
        conn.close()


def _find_existing_business_for_lead(lead: dict[str, Any]) -> dict[str, Any] | None:
    source_url = str(lead.get("source_url") or "").strip()
    source_external_id = str(
        lead.get("source_external_id")
        or lead.get("google_id")
        or _extract_yandex_org_id_from_url(source_url)
        or ""
    ).strip()
    explicit_business_id = str(lead.get("business_id") or "").strip()
    lead_name = str(lead.get("name") or "").strip()
    lead_city = str(lead.get("city") or "").strip()

    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'businesses'
            """
        )
        business_columns = set()
        for row in cursor.fetchall():
            if hasattr(row, "get"):
                col = row.get("column_name")
            else:
                col = row[0] if row else None
            if col:
                business_columns.add(str(col))

        business = None
        if explicit_business_id:
            cursor.execute("SELECT * FROM businesses WHERE id = %s LIMIT 1", (explicit_business_id,))
            row = cursor.fetchone()
            business = dict(row) if row else None
            if business and not _lead_identity_matches_candidate(
                lead,
                candidate_name=business.get("name"),
                candidate_city=business.get("city") or business.get("address"),
                candidate_source_url=business.get("yandex_url"),
                candidate_external_id=None,
            ):
                business = None

        if not business and source_external_id and "yandex_org_id" in business_columns:
            cursor.execute("SELECT * FROM businesses WHERE yandex_org_id = %s LIMIT 1", (source_external_id,))
            row = cursor.fetchone()
            business = dict(row) if row else None
            if business and not _lead_identity_matches_candidate(
                lead,
                candidate_name=business.get("name"),
                candidate_city=business.get("city") or business.get("address"),
                candidate_source_url=business.get("yandex_url"),
                candidate_external_id=source_external_id,
            ):
                business = None

        if not business and source_url and "yandex_url" in business_columns:
            if source_external_id:
                cursor.execute(
                    """
                    SELECT *
                    FROM businesses
                    WHERE yandex_url = %s OR yandex_url ILIKE %s
                    ORDER BY updated_at DESC NULLS LAST, created_at DESC
                    LIMIT 1
                    """,
                    (source_url, f"%{source_external_id}%"),
                )
            else:
                cursor.execute(
                    """
                    SELECT *
                    FROM businesses
                    WHERE yandex_url = %s
                    ORDER BY updated_at DESC NULLS LAST, created_at DESC
                    LIMIT 1
                    """,
                    (source_url,),
                )
            row = cursor.fetchone()
            business = dict(row) if row else None
            if business and not _lead_identity_matches_candidate(
                lead,
                candidate_name=business.get("name"),
                candidate_city=business.get("city") or business.get("address"),
                candidate_source_url=business.get("yandex_url"),
                candidate_external_id=source_external_id,
            ):
                business = None

        if not business and lead_name and _should_use_lead_name_for_match(lead_name):
            cursor.execute(
                """
                SELECT *
                FROM businesses
                WHERE LOWER(name) = LOWER(%s)
                  AND (%s = '' OR LOWER(COALESCE(city, '')) = LOWER(%s))
                ORDER BY updated_at DESC NULLS LAST, created_at DESC
                LIMIT 1
                """,
                (lead_name, lead_city, lead_city),
            )
            row = cursor.fetchone()
            business = dict(row) if row else None
            if business and not _lead_identity_matches_candidate(
                lead,
                candidate_name=business.get("name"),
                candidate_city=business.get("city") or business.get("address"),
                candidate_source_url=business.get("yandex_url"),
                candidate_external_id=None,
            ):
                business = None

        if business:
            return business
        return None
    finally:
        db.close()


def _drop_mismatched_explicit_business_link(lead: dict[str, Any]) -> dict[str, Any]:
    lead_id = str(lead.get("id") or "").strip()
    explicit_business_id = str(lead.get("business_id") or "").strip()
    if not lead_id or not explicit_business_id:
        return lead

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM businesses WHERE id = %s LIMIT 1", (explicit_business_id,))
        row = cur.fetchone()
        business = dict(row) if row and hasattr(row, "keys") else None
        if not business:
            return lead
        if _lead_identity_matches_candidate(
            lead,
            candidate_name=business.get("name"),
            candidate_city=business.get("city") or business.get("address"),
            candidate_source_url=business.get("yandex_url"),
            candidate_external_id=None,
        ):
            return lead
        cur.execute(
            """
            UPDATE prospectingleads
            SET business_id = NULL,
                updated_at = NOW()
            WHERE id = %s
              AND business_id = %s
            """,
            (lead_id, explicit_business_id),
        )
        conn.commit()
    finally:
        conn.close()

    sanitized = dict(lead)
    sanitized["business_id"] = None
    return sanitized


def _create_shadow_business_for_lead(lead: dict[str, Any], user_id: str) -> dict[str, Any]:
    """Create isolated business entity for lead parsing without mixing it into active client list."""
    source_url = str(lead.get("source_url") or "").strip()
    source_external_id = str(
        lead.get("source_external_id")
        or lead.get("google_id")
        or _extract_yandex_org_id_from_url(source_url)
        or ""
    ).strip()
    lead_name = str(lead.get("name") or "Lead without name").strip()[:255]
    lead_city = str(lead.get("city") or "").strip()[:120] or None
    lead_address = str(lead.get("address") or "").strip()[:400] or None
    lead_category = str(lead.get("category") or "").strip()[:120] or None

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'businesses'
            """
        )
        columns = set()
        for row in cur.fetchall():
            if hasattr(row, "get"):
                col = row.get("column_name")
            else:
                col = row[0] if row else None
            if col:
                columns.add(str(col))

        values: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "name": lead_name,
            "owner_id": user_id,
            "description": f"Lead shadow business for outreach lead {lead.get('id')}",
            "industry": lead_category,
            "business_type": lead_category,
            "address": lead_address,
            "city": lead_city,
            "website": (str(lead.get("website") or "").strip() or None),
            "phone": (str(lead.get("phone") or "").strip() or None),
            "email": (str(lead.get("email") or "").strip() or None),
            "yandex_url": source_url or None,
            "moderation_status": LEAD_OUTREACH_MODERATION_STATUS,
            "is_active": True,
        }
        if source_external_id and "yandex_org_id" in columns:
            values["yandex_org_id"] = source_external_id

        fields: list[str] = []
        params: list[Any] = []
        for key, value in values.items():
            if key in columns:
                fields.append(key)
                params.append(value)

        placeholders = ", ".join(["%s"] * len(fields))
        cur.execute(
            f"""
            INSERT INTO businesses ({", ".join(fields)})
            VALUES ({placeholders})
            RETURNING *
            """,
            params,
        )
        row = cur.fetchone()
        conn.commit()
        return dict(row)
    finally:
        conn.close()


def _ensure_parse_business_for_lead(lead: dict[str, Any], user_id: str) -> tuple[dict[str, Any], bool]:
    existing = _find_existing_business_for_lead(lead)
    if existing:
        return existing, False
    created = _create_shadow_business_for_lead(lead, user_id)
    return created, True


def _ensure_parse_business_for_partnership_lead(lead: dict[str, Any], user_id: str) -> tuple[dict[str, Any], bool]:
    """Resolve shadow business for partnership parse without binding to tenant business_id."""
    detached = dict(lead)
    detached["business_id"] = None
    existing = _find_existing_business_for_lead(detached)
    if existing:
        return existing, False
    created = _create_shadow_business_for_lead(detached, user_id)
    return created, True


def _extract_card_profile_fields(card_row: dict[str, Any]) -> dict[str, Any]:
    overview = card_row.get("overview")
    if isinstance(overview, str):
        try:
            overview = json.loads(overview)
        except Exception:
            overview = {}
    if not isinstance(overview, dict):
        overview = {}

    def _pick_text(*keys: str) -> str | None:
        for key in keys:
            value = overview.get(key)
            text = str(value or "").strip()
            if text and not _is_placeholder_like(text):
                return text
        return None

    parsed_contacts = _extract_parsed_contacts(overview)
    website_value = str(card_row.get("site") or "").strip()

    return {
        "name": _pick_text("name", "title", "company_name", "organization_name", "org_name"),
        "address": _pick_text("address", "full_address", "short_address", "location"),
        "city": _pick_text("city", "locality", "settlement"),
        "category": _pick_text("category", "rubric", "type", "business_type"),
        "phone": str(card_row.get("phone") or "").strip() or None,
        "website": website_value or None,
        "email": parsed_contacts.get("email"),
        "telegram_url": parsed_contacts.get("telegram_url"),
        "whatsapp_url": parsed_contacts.get("whatsapp_url"),
        "social_links": parsed_contacts.get("social_links") if isinstance(parsed_contacts.get("social_links"), list) else [],
        "rating": card_row.get("rating"),
        "reviews_count": card_row.get("reviews_count"),
    }


def _sync_partnership_lead_from_parsed_data(lead: dict[str, Any]) -> dict[str, Any]:
    lead_id = str(lead.get("id") or "").strip()
    parse_business_id = str(lead.get("parse_business_id") or "").strip()
    source_url = str(lead.get("source_url") or "").strip()
    if not lead_id:
        return lead

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        if not parse_business_id and source_url:
            cur.execute(
                """
                SELECT business_id
                FROM parsequeue
                WHERE task_type IN ('parse_card', 'sync_yandex_business')
                  AND status IN ('completed', 'done')
                  AND url = %s
                ORDER BY COALESCE(updated_at, created_at) DESC
                LIMIT 1
                """,
                (source_url,),
            )
            pq_row = cur.fetchone()
            if pq_row:
                parse_business_id = str(
                    pq_row.get("business_id") if hasattr(pq_row, "get") else (pq_row[0] if pq_row else "")
                ).strip()
                if parse_business_id:
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

        if not parse_business_id:
            return lead

        source_org_id = _extract_yandex_org_id_from_url(source_url)
        cur.execute(
            """
            SELECT phone, site, overview, rating, reviews_count
            FROM cards
            WHERE business_id = %s
              AND (
                    (%s <> '' AND url = %s)
                    OR (%s <> '' AND url ILIKE %s)
                  )
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (
                parse_business_id,
                source_url,
                source_url,
                source_org_id or "",
                f"%{source_org_id}%" if source_org_id else "",
            ),
        )
        row = cur.fetchone()
        if not row:
            cur.execute(
                """
                SELECT phone, site, overview, rating, reviews_count
                FROM cards
                WHERE business_id = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (parse_business_id,),
            )
            row = cur.fetchone()
        if not row:
            return lead
        card = dict(row)
        parsed = _extract_card_profile_fields(card)
        if not _lead_identity_matches_candidate(
            lead,
            candidate_name=parsed.get("name"),
            candidate_city=parsed.get("city") or parsed.get("address"),
            candidate_source_url=source_url,
            candidate_external_id=source_org_id,
        ):
            return lead

        updates: dict[str, Any] = {}
        raw_name = str(lead.get("name") or "").strip()
        if not raw_name or raw_name.lower() in {"новый партнёр", "партнёр", "компания"}:
            parsed_name = str(parsed.get("name") or "").strip()
            fallback_name = _derive_name_from_source_url(source_url)
            if parsed_name and not _is_placeholder_like(parsed_name):
                updates["name"] = parsed_name
            elif fallback_name:
                updates["name"] = fallback_name
        if not str(lead.get("address") or "").strip() and parsed.get("address"):
            updates["address"] = parsed.get("address")
        if not str(lead.get("city") or "").strip() and parsed.get("city"):
            updates["city"] = parsed.get("city")
        if not str(lead.get("category") or "").strip() and parsed.get("category"):
            updates["category"] = parsed.get("category")
        if not str(lead.get("phone") or "").strip() and parsed.get("phone"):
            updates["phone"] = parsed.get("phone")
        if not str(lead.get("website") or "").strip() and parsed.get("website"):
            updates["website"] = parsed.get("website")
        if not str(lead.get("email") or "").strip() and parsed.get("email"):
            updates["email"] = parsed.get("email")
        if not str(lead.get("telegram_url") or "").strip() and parsed.get("telegram_url"):
            updates["telegram_url"] = parsed.get("telegram_url")
        if not str(lead.get("whatsapp_url") or "").strip() and parsed.get("whatsapp_url"):
            updates["whatsapp_url"] = parsed.get("whatsapp_url")
        if (lead.get("rating") is None or str(lead.get("rating") or "").strip() == "") and parsed.get("rating") is not None:
            updates["rating"] = parsed.get("rating")
        if (lead.get("reviews_count") is None or int(lead.get("reviews_count") or 0) == 0) and parsed.get("reviews_count") is not None:
            updates["reviews_count"] = int(parsed.get("reviews_count") or 0)
        if parsed.get("social_links"):
            updates["messenger_links_json"] = Json(parsed.get("social_links"))

        if not updates:
            return lead

        assignments: list[str] = []
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
        updated = cur.fetchone()
        if updated:
            conn.commit()
            return dict(updated)
        return lead
    finally:
        conn.close()


def _enqueue_parse_task_for_business(business_id: str, user_id: str, source_url: str) -> dict[str, Any]:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, status, task_type, source, updated_at, retry_after
            FROM parsequeue
            WHERE business_id = %s
              AND task_type IN ('parse_card', 'sync_yandex_business')
              AND status IN ('pending', 'processing', 'captcha')
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (business_id,),
        )
        active = cur.fetchone()
        if active:
            payload = dict(active)
            payload["existing"] = True
            return payload

        task_id = str(uuid.uuid4())
        normalized_url = str(source_url or "").strip().lower()
        source_hint = "yandex_maps"
        if "2gis.ru/" in normalized_url or "2gis.com/" in normalized_url:
            source_hint = "2gis"
        elif "maps.apple.com/" in normalized_url:
            source_hint = "apple_maps"
        elif is_google_map_url(normalized_url):
            source_hint = "google_maps"
        parse_source = resolve_map_source_for_queue(source_hint, bool(get_use_apify_map_parsing(conn)))
        cur.execute(
            """
            INSERT INTO parsequeue (
                id, business_id, task_type, source, status, user_id, url, created_at, updated_at
            )
            VALUES (%s, %s, 'parse_card', %s, 'pending', %s, %s, NOW(), NOW())
            RETURNING id, status, task_type, source, updated_at, retry_after
            """,
            (task_id, business_id, parse_source, user_id, source_url),
        )
        created = dict(cur.fetchone())
        created["existing"] = False
        conn.commit()
        return created
    finally:
        conn.close()


def _sync_lead_contacts_from_parsed_data(lead: dict[str, Any]) -> dict[str, Any]:
    business_id = str(lead.get("business_id") or "").strip()
    if not business_id:
        return lead

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT phone, site, overview, rating, reviews_count
            FROM cards
            WHERE business_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (business_id,),
        )
        row = cur.fetchone()
        if not row:
            return lead
        card = dict(row)

        overview = card.get("overview")
        if isinstance(overview, str):
            try:
                overview = json.loads(overview)
            except Exception:
                overview = {}
        if not isinstance(overview, dict):
            overview = {}
        parsed = _extract_parsed_contacts(overview)
        updates: dict[str, Any] = {}
        if not str(lead.get("phone") or "").strip() and str(card.get("phone") or "").strip():
            updates["phone"] = str(card.get("phone")).strip()
        if not str(lead.get("website") or "").strip() and str(card.get("site") or "").strip():
            updates["website"] = str(card.get("site")).strip()
        if not str(lead.get("telegram_url") or "").strip() and parsed.get("telegram_url"):
            updates["telegram_url"] = parsed.get("telegram_url")
        if not str(lead.get("whatsapp_url") or "").strip() and parsed.get("whatsapp_url"):
            updates["whatsapp_url"] = parsed.get("whatsapp_url")
        if not str(lead.get("email") or "").strip() and parsed.get("email"):
            updates["email"] = parsed.get("email")
        if (lead.get("rating") is None or str(lead.get("rating")).strip() == "") and card.get("rating") is not None:
            updates["rating"] = card.get("rating")
        if (lead.get("reviews_count") is None or int(lead.get("reviews_count") or 0) == 0) and card.get("reviews_count") is not None:
            updates["reviews_count"] = int(card.get("reviews_count") or 0)
        if parsed.get("social_links"):
            updates["messenger_links_json"] = Json(parsed.get("social_links"))

        if not updates:
            return lead

        assignments = []
        values: list[Any] = []
        for field, value in updates.items():
            assignments.append(f"{field} = %s")
            values.append(value)
        assignments.append("updated_at = NOW()")
        values.append(lead["id"])

        cur.execute(
            f"""
            UPDATE prospectingleads
            SET {', '.join(assignments)}
            WHERE id = %s
            RETURNING *
            """,
            values,
        )
        updated = cur.fetchone()
        if updated:
            conn.commit()
            return dict(updated)
        return lead
    finally:
        conn.close()


def _get_prompt_from_db(prompt_type: str, fallback: str = "") -> str:
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT prompt_text FROM AIPrompts WHERE prompt_type = %s", (prompt_type,))
        row = cur.fetchone()
        if not row:
            return fallback
        if hasattr(row, "get"):
            value = row.get("prompt_text")
        elif isinstance(row, dict):
            value = row.get("prompt_text")
        else:
            value = row[0] if len(row) > 0 else None
        text = str(value or "").strip()
        return text or fallback
    except Exception:
        return fallback
    finally:
        if conn is not None:
            conn.close()


def _normalize_prompt_meta(raw_meta: Any, *, fallback_key: str, fallback_version: str, fallback_source: str) -> dict[str, str]:
    meta = raw_meta if isinstance(raw_meta, dict) else {}
    prompt_key = str(
        meta.get("prompt_key")
        or meta.get("template_key")
        or meta.get("key")
        or fallback_key
    ).strip() or fallback_key
    prompt_version = str(
        meta.get("prompt_version")
        or meta.get("template_version")
        or meta.get("version")
        or fallback_version
    ).strip() or fallback_version
    prompt_source = str(
        meta.get("prompt_source")
        or meta.get("source")
        or fallback_source
    ).strip() or fallback_source
    return {
        "prompt_key": prompt_key,
        "prompt_version": prompt_version,
        "prompt_source": prompt_source,
    }


def _extract_json_candidate(raw_text: str) -> dict[str, Any] | None:
    if not isinstance(raw_text, str):
        return None
    text = raw_text.strip()
    if not text:
        return None
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fence_match:
        text = fence_match.group(1).strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        candidate = text[start:end]
        cleaned = (
            candidate
            .replace("“", "\"")
            .replace("”", "\"")
            .replace("’", "'")
            .replace("‘", "'")
        )
        cleaned = re.sub(r",(\s*[}\]])", r"\1", cleaned)
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return None
    return None


def _language_label(language: str) -> str:
    labels = {
        "ru": "Русский",
        "en": "English",
        "tr": "Türkçe",
        "el": "Ελληνικά",
        "fr": "Français",
        "es": "Español",
        "de": "Deutsch",
        "th": "ไทย",
        "ar": "العربية",
        "ha": "Hausa",
    }
    return labels.get(language, "English")


def _prompt_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except Exception:
        return str(value)


def _render_prompt_template(template: str, variables: dict[str, Any]) -> str:
    rendered = str(template or "")
    for key, value in variables.items():
        rendered = rendered.replace("{" + str(key) + "}", str(value))
    return rendered


def _normalize_recommended_actions(items: Any) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            description = str(item.get("description") or "").strip()
            if title:
                normalized.append({"title": title, "description": description})
    return normalized


def _lowercase_first(text: Any) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    return value[:1].lower() + value[1:]


def _truncate_text(value: Any, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _compact_findings_payload(items: Any, limit: int = 5) -> list[dict[str, str]]:
    compact: list[dict[str, str]] = []
    if not isinstance(items, list):
        return compact
    for item in items:
        if not isinstance(item, dict):
            continue
        title = _truncate_text(item.get("title"), 160)
        severity = str(item.get("severity") or "").strip()
        if title:
            compact.append(
                {
                    "title": title,
                    "severity": severity,
                }
            )
        if len(compact) >= limit:
            break
    return compact


def _compact_actions_payload(items: Any, limit: int = 3) -> list[dict[str, str]]:
    compact: list[dict[str, str]] = []
    if not isinstance(items, list):
        return compact
    for item in items:
        if not isinstance(item, dict):
            continue
        title = _truncate_text(item.get("title"), 140)
        description = _truncate_text(item.get("description"), 220)
        if title:
            compact.append(
                {
                    "title": title,
                    "description": description,
                }
            )
        if len(compact) >= limit:
            break
    return compact


def _contains_quality_red_flags(text: Any, language: str) -> bool:
    normalized = str(text or "").strip().lower()
    if not normalized:
        return False
    generic_markers = [
        "высокий потенциал",
        "стратегическ",
        "онлайн-присутств",
        "обладает высоким",
        "имеет хороший рейтинг",
        "имеет хорошие отзывы",
        "отзывы дают доверие",
        "слабее влияют на запись",
        "категории и профиль",
        "профиль клиники можно усилить",
        "не хватает регулярных экспертных обновлений",
        "already has a strong base",
        "solid base",
        "high level of customer satisfaction",
        "online presence",
        "high potential",
        "strategic improvement",
    ]
    if any(marker in normalized for marker in generic_markers):
        return True
    if language == "ru" and re.search(r"\b(on|the|and|despite|currently|solid|base)\b", normalized):
        return True
    return False


def _needs_dense_audit_retry(summary_text: str, why_now: str, language: str) -> bool:
    summary = str(summary_text or "").strip()
    why = str(why_now or "").strip()
    if not summary:
        return True
    if len(summary) > 420 or len(why) > 220:
        return True
    if _contains_quality_red_flags(summary, language) or _contains_quality_red_flags(why, language):
        return True
    lowered = summary.lower()
    if language == "ru":
        praise_openers = (
            "ваш салон",
            "салон ",
            "ваш бизнес",
            "бизнес ",
            "театр ",
            "у салона ",
        )
        if lowered.startswith(praise_openers) and (
            "имеет " in lowered[:80] or "обладает " in lowered[:80]
        ):
            return True
    return False


def _deterministic_actor_label(preview: dict[str, Any]) -> str:
    audit_profile = str(preview.get("audit_profile") or "").strip().lower()
    if audit_profile == "medical":
        return "пациент"
    if audit_profile == "hospitality":
        return "гость"
    return "клиент"


def _deterministic_actor_dative(actor: str) -> str:
    mapping = {
        "клиент": "клиенту",
        "пациент": "пациенту",
        "гость": "гостю",
    }
    return mapping.get(actor, "клиенту")


def _deterministic_priority_steps(
    findings: list[dict[str, Any]],
    current_state: dict[str, Any],
) -> list[str]:
    joined = " ".join(
        str(item.get("title") or "").strip().lower()
        for item in findings
        if isinstance(item, dict)
    )
    priorities: list[str] = []

    def _add(step: str) -> None:
        if step and step not in priorities:
            priorities.append(step)

    services_count = int(current_state.get("services_count") or 0)
    services_with_price_count = int(current_state.get("services_with_price_count") or 0)
    photos_count = int(current_state.get("photos_count") or 0)
    photos_state = str(current_state.get("photos_state") or "").strip().lower()
    photo_confidence = str(
        current_state.get("photo_signal_confidence") or current_state.get("photos_confidence") or ""
    ).strip().lower()
    reviews_count = int(current_state.get("reviews_count") or 0)
    rating = current_state.get("rating")
    has_website = bool(current_state.get("has_website"))
    description_present = bool(current_state.get("description_present"))

    if "опис" in joined or not description_present:
        _add("переписать описание под основные услуги и сценарии обращения")
    if "услуг" in joined or services_count <= 0:
        _add("собрать понятную структуру услуг")
    if "цен" in joined or (services_count > 0 and services_with_price_count <= 0):
        _add("добавить ценовые ориентиры")
    if "фото" in joined or photos_state == "weak" or (photos_count <= 1 and photo_confidence == "confirmed"):
        _add("добавить фото, которые помогают оценить качество и результат")
    if "отзыв" in joined or "рейтинг" in joined or reviews_count <= 0 or rating is None:
        _add("усилить доверие через отзывы и ответы")
    if "контакт" in joined or not has_website:
        _add("закрыть пробелы в контактах и переходе в запись")

    return priorities[:3]


def _build_deterministic_dense_audit_enrichment(
    lead: dict[str, Any],
    preview: dict[str, Any],
    preferred_language: str | None,
) -> dict[str, Any]:
    language = str(preferred_language or "").strip().lower()
    if language not in PUBLIC_AUDIT_LANGUAGES:
        language = _resolve_outreach_language(lead)
    if language != "ru":
        fallback_summary = str(preview.get("summary_text") or "").strip()
        fallback_actions = _normalize_recommended_actions(preview.get("recommended_actions"))[:3]
        return {
            "summary_text": fallback_summary,
            "recommended_actions": fallback_actions,
            "why_now": "",
            "meta": {
                "source": "deterministic",
                "prompt_key": "lead_audit_enrichment",
                "prompt_version": "deterministic_dense_v2",
                "prompt_source": "local_dense",
            },
        }

    findings = preview.get("findings") if isinstance(preview.get("findings"), list) else []
    normalized_findings = [item for item in findings if isinstance(item, dict)]
    current_state = preview.get("current_state") if isinstance(preview.get("current_state"), dict) else {}
    actions = _normalize_recommended_actions(preview.get("recommended_actions"))[:3]
    actor = _deterministic_actor_label(preview)
    actor_dative = _deterministic_actor_dative(actor)

    services_count = int(current_state.get("services_count") or 0)
    services_with_price_count = int(current_state.get("services_with_price_count") or 0)
    photos_count = int(current_state.get("photos_count") or 0)
    photos_state = str(current_state.get("photos_state") or "").strip().lower()
    photo_confidence = str(
        current_state.get("photo_signal_confidence") or current_state.get("photos_confidence") or ""
    ).strip().lower()
    reviews_count = int(current_state.get("reviews_count") or 0)
    rating = current_state.get("rating")
    has_website = bool(current_state.get("has_website"))
    description_present = bool(current_state.get("description_present"))

    metric_fragments: list[str] = []
    if photos_count <= 1 and photo_confidence == "confirmed":
        metric_fragments.append("в карточке всего 1 фото")
    elif photos_count > 1 and photos_state == "weak":
        metric_fragments.append(f"фото пока только {photos_count}")
    if not has_website:
        metric_fragments.append("нет сайта")
    if rating is None and reviews_count <= 0:
        metric_fragments.append("нет рейтинга и отзывов")
    elif rating is not None:
        try:
            rating_value = float(rating)
        except (TypeError, ValueError):
            rating_value = None
        if rating_value is not None and rating_value < 4.5:
            metric_fragments.append(f"рейтинг {rating_value:.1f} ниже целевой зоны")
    elif reviews_count > 0 and reviews_count <= 5:
        metric_fragments.append(f"отзывов пока только {reviews_count}")
    if services_count > 0 and services_with_price_count <= 0:
        metric_fragments.append("нет ценовых ориентиров")

    metrics_text = ", ".join(metric_fragments[:3]).strip()

    top_titles = [
        str(item.get("title") or "").strip().rstrip(".")
        for item in normalized_findings[:2]
        if str(item.get("title") or "").strip()
    ]
    if len(top_titles) >= 2:
        sentence1 = f"{top_titles[0]}. Также: {_lowercase_first(top_titles[1])}."
    elif top_titles:
        sentence1 = f"{top_titles[0]}."
    elif services_count <= 0:
        sentence1 = "В карточке нет понятной структуры услуг."
    elif not description_present:
        sentence1 = "Описание карточки не объясняет, почему сюда стоит записаться."
    elif photos_state == "weak" or photos_count <= 1:
        sentence1 = "Карточка не даёт достаточного визуального доверия перед записью."
    else:
        sentence1 = "Карточка пока недобирает обращения из локального поиска."

    if services_count <= 0:
        if metrics_text:
            sentence2 = f"Сейчас {metrics_text}, поэтому {actor} не видит ни точку входа в запись, ни достаточное доказательство качества."
        else:
            sentence2 = f"Без понятных услуг {actor} не видит, с чем сюда можно обратиться и по какому запросу выбрать именно эту карточку."
    elif not description_present and (photos_state == "weak" or photos_count <= 1):
        if metrics_text:
            sentence2 = f"Сейчас {metrics_text}, поэтому {actor} не понимает ключевые направления и не получает визуального подтверждения качества до записи."
        else:
            sentence2 = f"{actor[:1].upper() + actor[1:]} не понимает ключевые направления и не получает визуального подтверждения качества до записи."
    elif not description_present:
        if metrics_text:
            sentence2 = f"Сейчас {metrics_text}, и {actor_dative} сложнее понять, какие услуги здесь ключевые и чем бизнес отличается от соседних предложений."
        else:
            sentence2 = f"{actor_dative[:1].upper() + actor_dative[1:]} сложнее понять, какие услуги здесь ключевые и чем бизнес отличается от соседних предложений."
    elif photos_state == "weak" or photos_count <= 1:
        if metrics_text:
            sentence2 = f"Сейчас {metrics_text}, и не хватает визуальных доказательств выбора до первого контакта."
        else:
            sentence2 = "Не хватает визуальных доказательств выбора до первого контакта."
    elif reviews_count <= 0 or rating is None:
        if metrics_text:
            sentence2 = f"Сейчас {metrics_text}, поэтому карточка хуже закрывает доверие и проигрывает более понятным конкурентам рядом."
        else:
            sentence2 = "Без рейтинга и свежих отзывов карточка хуже закрывает доверие и проигрывает более понятным конкурентам рядом."
    elif not has_website:
        if metrics_text:
            sentence2 = f"Сейчас {metrics_text}, и часть пользователей теряется ещё на этапе перехода в запись."
        else:
            sentence2 = "Часть пользователей теряется на этапе перехода в запись, потому что карточка не даёт полного маршрута к контакту."
    elif services_count > 0 and services_with_price_count <= 0:
        if metrics_text:
            sentence2 = f"Сейчас {metrics_text}, поэтому {actor_dative} сложнее быстро принять решение о записи."
        else:
            sentence2 = f"Услуги есть, но без ценовых ориентиров {actor_dative} сложнее быстро принять решение о записи."
    else:
        if metrics_text:
            sentence2 = f"Сейчас {metrics_text}, и часть клиентов выбирает конкурентов, где предложение упаковано понятнее."
        else:
            sentence2 = "Сейчас карточка выглядит слабее, чем могла бы, и часть клиентов выбирает конкурентов, где предложение упаковано понятнее."

    priorities = _deterministic_priority_steps(normalized_findings, current_state)
    if priorities:
        if len(priorities) == 1:
            sentence3 = f"В первую очередь стоит {priorities[0]}."
        elif len(priorities) == 2:
            sentence3 = f"В первую очередь стоит {priorities[0]} и {priorities[1]}."
        else:
            sentence3 = f"В первую очередь стоит {priorities[0]}, {priorities[1]} и {priorities[2]}."
    else:
        sentence3 = "В первую очередь стоит сделать карточку понятнее по услугам, доверию и конверсии."

    draft_audit = {
        "audit_profile": preview.get("audit_profile"),
        "summary_text": " ".join(
            part.strip()
            for part in [sentence1, sentence2, sentence3]
            if str(part or "").strip()
        ).strip(),
        "findings": normalized_findings,
        "recommended_actions": actions,
        "current_state": current_state,
        "industry_patterns": preview.get("industry_patterns") if isinstance(preview.get("industry_patterns"), dict) else {},
    }
    summary_text = build_editorial_summary(draft_audit)

    if services_count <= 0:
        why_now = f"Пока в карточке нет понятных услуг{', ' + metrics_text if metrics_text else ''}, часть клиентов выбирает конкурентов с более понятной карточкой."
    elif not description_present and (photos_state == "weak" or photos_count <= 1):
        why_now = f"Сейчас карточка теряет обращения и на поиске, и на доверии{', ' + metrics_text if metrics_text else ''}."
    elif reviews_count <= 0 or rating is None:
        why_now = f"Пока карточка не закрывает доверие через рейтинг и отзывы{', ' + metrics_text if metrics_text else ''}, часть обращений не доходит до записи."
    elif not has_website:
        why_now = f"Пока карточка не даёт полного маршрута к контакту{', ' + metrics_text if metrics_text else ''}, часть пользователей теряется перед записью."
    elif services_count > 0 and services_with_price_count <= 0:
        why_now = f"Пока у ключевых услуг нет ценовых ориентиров{', ' + metrics_text if metrics_text else ''}, карточка недобирает быстрые обращения из горячего спроса."
    else:
        why_now = f"Понятная упаковка карточки{', ' + metrics_text if metrics_text else ''} может быстрее переводить просмотры в обращения."

    return {
        "summary_text": normalize_audit_text(summary_text, audit_profile=str(preview.get("audit_profile") or "")),
        "recommended_actions": actions,
        "why_now": truncate_sentence(normalize_audit_text(why_now, audit_profile=str(preview.get("audit_profile") or "")), 180),
        "meta": {
            "source": "deterministic",
            "prompt_key": "lead_audit_enrichment",
            "prompt_version": "deterministic_dense_v2",
            "prompt_source": "local_dense",
        },
    }


def _needs_outreach_retry(message: str) -> bool:
    text = str(message or "").strip()
    if not text:
        return True
    line_count = len([line for line in text.splitlines() if line.strip()])
    lowered = text.lower()
    old_style_markers = (
        "выявлены основные недостатки",
        "предварительное исследование",
        "по нашей модели",
        "по нашей оценке",
        "оценили карточку",
        "выявили ключевые проблемы",
        "выявили два",
        "основные проблемы:",
        "проблемы:",
        "подробный разбор ситуации",
        "подробности и исправления",
    )
    if any(marker in lowered for marker in old_style_markers):
        return True
    return line_count > 5 or len(text) > 420


def _build_compact_audit_enrichment_payload(
    lead: dict[str, Any],
    factual_audit: dict[str, Any],
) -> dict[str, Any]:
    scorecard = factual_audit.get("scorecard") if isinstance(factual_audit.get("scorecard"), dict) else {}
    current_state = factual_audit.get("current_state") if isinstance(factual_audit.get("current_state"), dict) else {}
    revenue = factual_audit.get("revenue_potential") if isinstance(factual_audit.get("revenue_potential"), dict) else {}
    profile_contacts = factual_audit.get("profile_contacts") if isinstance(factual_audit.get("profile_contacts"), dict) else {}
    return {
        "business": {
            "name": str(lead.get("name") or "").strip(),
            "category": str(lead.get("category") or "").strip(),
            "city": str(lead.get("city") or "").strip(),
            "address": str(lead.get("address") or "").strip(),
        },
        "current_state": {
            "rating": current_state.get("rating"),
            "reviews_count": current_state.get("reviews_count"),
            "services_count": current_state.get("services_count"),
            "priced_services_count": current_state.get("priced_services_count"),
            "photos_count": current_state.get("photos_count"),
            "has_recent_activity": current_state.get("has_recent_activity"),
            "has_website": current_state.get("has_website"),
            "has_phone": current_state.get("has_phone"),
        },
        "scorecard": {
            "profile_completeness": scorecard.get("profile_completeness"),
            "services_quality": scorecard.get("services_quality"),
            "reviews_reputation": scorecard.get("reviews_reputation"),
            "content_activity": scorecard.get("content_activity"),
            "visual_trust": scorecard.get("visual_trust"),
            "seo_relevance": scorecard.get("seo_relevance"),
        },
        "revenue_potential": {
            "total_min": revenue.get("total_min"),
            "total_max": revenue.get("total_max"),
            "baseline_value": revenue.get("baseline_value"),
            "baseline_source": revenue.get("baseline_source"),
        },
        "contacts": {
            "has_website": profile_contacts.get("has_website"),
            "has_phone": profile_contacts.get("has_phone"),
            "has_whatsapp": profile_contacts.get("has_whatsapp"),
            "has_telegram": profile_contacts.get("has_telegram"),
        },
        "top_findings": _compact_findings_payload(factual_audit.get("findings")),
        "top_actions": _compact_actions_payload(factual_audit.get("recommended_actions")),
    }


def _build_compact_outreach_payload(
    lead: dict[str, Any],
    preview: dict[str, Any] | None,
) -> dict[str, Any]:
    preview_payload = preview if isinstance(preview, dict) else {}
    revenue = preview_payload.get("revenue_potential") if isinstance(preview_payload.get("revenue_potential"), dict) else {}
    current_state = preview_payload.get("current_state") if isinstance(preview_payload.get("current_state"), dict) else {}
    return {
        "business": {
            "name": str(lead.get("name") or "").strip(),
            "category": str(lead.get("category") or "").strip(),
            "city": str(lead.get("city") or "").strip(),
        },
        "current_state": {
            "rating": current_state.get("rating", lead.get("rating")),
            "reviews_count": current_state.get("reviews_count", lead.get("reviews_count")),
            "services_count": current_state.get("services_count", lead.get("services_count")),
        },
        "summary_text": _truncate_text(preview_payload.get("summary_text"), 240),
        "top_findings": _compact_findings_payload(preview_payload.get("findings"), limit=2),
        "top_actions": _compact_actions_payload(preview_payload.get("recommended_actions"), limit=2),
        "revenue_potential": {
            "total_min": revenue.get("total_min"),
            "total_max": revenue.get("total_max"),
        },
    }


def _generate_lead_audit_enrichment(
    lead: dict[str, Any],
    preview: dict[str, Any],
    preferred_language: str | None,
) -> dict[str, Any]:
    language = str(preferred_language or "").strip().lower()
    if language not in PUBLIC_AUDIT_LANGUAGES:
        language = _resolve_outreach_language(lead)

    fallback_summary = str(preview.get("summary_text") or "").strip()
    fallback_actions = _normalize_recommended_actions(preview.get("recommended_actions"))
    fallback = {
        "summary_text": fallback_summary,
        "recommended_actions": fallback_actions,
        "why_now": "",
        "meta": {
            "source": "deterministic",
            "prompt_key": "lead_audit_enrichment",
            "prompt_version": "fallback_v1",
            "prompt_source": "local_fallback",
        },
    }

    factual_payload = _to_json_compatible(
        _build_admin_lead_offer_payload(
            lead=lead,
            preview=preview,
            preferred_language=language,
            enabled_languages=[language],
        )
    )
    factual_audit = factual_payload.get("audit") if isinstance(factual_payload, dict) else {}
    if not isinstance(factual_audit, dict):
        factual_audit = {}

    compact_payload = _build_compact_audit_enrichment_payload(lead, factual_audit)
    fallback_prompt = (
        "Ты усиливаешь factual-аудит карточки локального бизнеса.\n"
        "Не меняй факты, цифры, названия, город, адрес, рейтинг, количество отзывов, услуг и ссылки.\n"
        "Нельзя придумывать новые услуги, контакты, проблемы или выгоду.\n"
        "Верни только один JSON-объект без markdown, без пролога, без code fence.\n"
        "Язык ответа: {language_name}\n"
        "Название бизнеса: {company_name}\n"
        "Категория: {category}\n"
        "Город: {city}\n"
        "Compact factual JSON: {factual_json}\n"
        "summary_text должен опираться на конкретные проблемы из top_findings или current_state, а не на общие фразы.\n"
        "Начинай summary_text с конкретного недостатка карточки, а не с похвалы бизнесу.\n"
        "Не начинай с фраз вроде 'у вас хороший рейтинг', 'высокий потенциал', 'сильная база'.\n"
        "Не используй пустые формулировки вроде 'высокий потенциал', 'стратегическое улучшение', 'онлайн-присутствие' без привязки к фактам.\n"
        "Не называй точкой роста абстрактную область вроде 'категории и профиль можно усилить', 'отзывы дают доверие', 'не хватает экспертных обновлений'.\n"
        "Каждая точка роста должна быть действием + механизмом: что сделать, где именно и зачем это влияет на поиск, запись или выбор.\n"
        "Хороший формат: 'переписать услуги с SEO-ключами, чтобы попасть в поиск пользователей', 'начать вести новости для лучшей видимости', 'отвечать на отзывы с упоминанием смежных услуг'.\n"
        "recommended_actions максимум 3.\n"
        "summary_text 2-3 предложения, максимум 420 символов.\n"
        "why_now одно короткое предложение, максимум 180 символов.\n"
        "Каждый recommended_action должен быть привязан к одному из top_findings или current_state.\n"
        "Формат ответа:\n"
        "{\"summary_text\":\"...\",\"recommended_actions\":[{\"title\":\"...\",\"description\":\"...\"}],\"why_now\":\"...\"}"
    )
    prompt_template = _get_prompt_from_db("lead_audit_enrichment", fallback_prompt)
    prompt = _render_prompt_template(
        prompt_template,
        {
            "language_name": _language_label(language),
            "company_name": str(lead.get("name") or "").strip(),
            "category": str(lead.get("category") or "").strip(),
            "city": str(lead.get("city") or "").strip(),
            "factual_json": _prompt_json(compact_payload),
        },
    )
    try:
        result_text = analyze_text_with_gigachat(prompt, task_type="ai_agent_marketing")
        parsed = _extract_json_candidate(result_text)
        if not parsed:
            raise ValueError("AI audit enrichment did not return JSON")
        summary_text = str(parsed.get("summary_text") or "").strip()
        recommended_actions = _normalize_recommended_actions(parsed.get("recommended_actions"))
        why_now = str(parsed.get("why_now") or "").strip()
        if _needs_dense_audit_retry(summary_text, why_now, language):
            retry_prompt = (
                prompt
                + "\nОтвет отклонён как слишком общий или языково нечистый."
                + "\nПерепиши короче и плотнее по сути."
                + "\nНачни с конкретного недостатка карточки."
                + "\nЗапрещены фразы: высокий потенциал, strategic improvement, online presence, solid base."
                + "\nНужны 1-2 конкретные проблемы из top_findings/current_state и короткое business consequence."
            )
            result_text = analyze_text_with_gigachat(retry_prompt, task_type="ai_agent_marketing")
            parsed = _extract_json_candidate(result_text)
            if not parsed:
                raise ValueError("AI audit enrichment retry did not return JSON")
            summary_text = str(parsed.get("summary_text") or "").strip()
            recommended_actions = _normalize_recommended_actions(parsed.get("recommended_actions"))
            why_now = str(parsed.get("why_now") or "").strip()
        if not summary_text:
            raise ValueError("AI audit enrichment returned empty summary_text")
        if not recommended_actions:
            recommended_actions = fallback_actions
        editorial_payload = apply_audit_editorial_pass(
            {
                "audit_profile": preview.get("audit_profile"),
                "summary_text": summary_text,
                "recommended_actions": recommended_actions,
                "why_now": why_now,
                "current_state": preview.get("current_state") if isinstance(preview.get("current_state"), dict) else {},
                "industry_patterns": preview.get("industry_patterns") if isinstance(preview.get("industry_patterns"), dict) else {},
            }
        )
        return {
            "summary_text": str(editorial_payload.get("summary_text") or "").strip(),
            "recommended_actions": editorial_payload.get("recommended_actions") if isinstance(editorial_payload.get("recommended_actions"), list) else recommended_actions,
            "why_now": str(editorial_payload.get("why_now") or "").strip(),
            "meta": {
                "source": "gigachat",
                "prompt_key": "lead_audit_enrichment",
                "prompt_version": "v1",
                "prompt_source": "gigachat",
                "raw_response": str(result_text or "")[:4000],
            },
        }
    except Exception as exc:
        print(f"Lead audit AI enrichment fallback: {exc}")
        return fallback


def _generate_outreach_message_ai(
    *,
    lead: dict[str, Any],
    preview: dict[str, Any] | None,
    channel: str,
    fallback_message: str,
    fallback_angle_type: str,
    fallback_tone: str,
) -> dict[str, str]:
    language = _resolve_outreach_language(lead)
    factual_payload = _build_compact_outreach_payload(lead, preview)
    fallback_prompt = (
        "Ты пишешь первое короткое сообщение владельцу локального бизнеса после аудита карточки.\n"
        "Верни строго JSON без markdown.\n"
        "Язык: {language_name}\n"
        "Канал: {channel}\n"
        "Бизнес: {company_name}\n"
        "Категория: {category}\n"
        "Город: {city}\n"
        "URL аудита: {public_audit_url}\n"
        "Factual JSON: {factual_json}\n"
        "Deterministic fallback: {fallback_message}\n"
        "Возьми из Factual JSON только 1-2 самых конкретных проблемы и не повторяй длинный summary целиком.\n"
        "Не используй общие фразы вроде 'улучшить онлайн-присутствие' или 'раскрыть потенциал', если можно назвать конкретный недостаток.\n"
        "Не пиши как мини-аудит и не используй формулировки: 'выявлены основные недостатки', 'по нашей модели', 'по нашей оценке', 'основные проблемы'.\n"
        "Не упоминай денежный диапазон или месячную выгоду.\n"
        "Сообщение должно быть коротким, прямым и выглядеть как первое касание человека.\n"
        "Желаемая структура для email на русском:\n"
        "1) Вы сейчас недополучаете клиентов с карт.\n"
        "2) Один короткий факт о 1-2 проблемах карточки.\n"
        "3) Ссылка на короткий аудит.\n"
        "4) Можем внедрить это под ключ.\n"
        "5) Короткий CTA-вопрос.\n"
        "Максимум 5 коротких строк.\n"
        "Формат ответа:\n"
        "{\"message\":\"...\",\"angle_type\":\"audit_preview\",\"tone\":\"professional\"}"
    )
    prompt_template = _get_prompt_from_db("outreach_first_message", fallback_prompt)
    prompt = _render_prompt_template(
        prompt_template,
        {
            "language_name": _language_label(language),
            "channel": channel,
            "company_name": str(lead.get("name") or "").strip(),
            "category": str(lead.get("category") or "").strip(),
            "city": str(lead.get("city") or "").strip(),
            "public_audit_url": str(lead.get("public_audit_url") or "").strip(),
            "factual_json": _prompt_json(factual_payload),
            "fallback_message": fallback_message,
        },
    )
    try:
        result_text = analyze_text_with_gigachat(prompt, task_type="ai_agent_marketing")
        parsed = _extract_json_candidate(result_text)
        if not parsed:
            raise ValueError("AI outreach draft did not return JSON")
        message = str(parsed.get("message") or parsed.get("text") or "").strip()
        if _needs_outreach_retry(message):
            retry_prompt = (
                prompt
                + "\nОтвет отклонён как слишком длинный или звучит как мини-аудит."
                + "\nСократи до 5 коротких строк максимум."
                + "\nНе используй денежный диапазон."
                + "\nУбери фразы: 'выявлены основные недостатки', 'по нашей модели', 'основные проблемы'."
                + "\nНазови 1-2 конкретные проблемы и дай ссылку на аудит."
            )
            result_text = analyze_text_with_gigachat(retry_prompt, task_type="ai_agent_marketing")
            parsed = _extract_json_candidate(result_text)
            if not parsed:
                raise ValueError("AI outreach retry did not return JSON")
            message = str(parsed.get("message") or parsed.get("text") or "").strip()
        if not message:
            raise ValueError("AI outreach draft returned empty message")
        if language == "ru" and "Можем внедрить это под ключ" not in message:
            message = re.sub(
                r"Можем\s+быстро\s+внедрить[^\n.?!]*под\s+ключ",
                "Можем внедрить это под ключ",
                message,
                flags=re.IGNORECASE,
            )
            if "Можем внедрить это под ключ" not in message and re.search(r"\bМожем\b|под\s+ключ|внедр|устранить", message, flags=re.IGNORECASE):
                message = f"{message.rstrip()}\n\nМожем внедрить это под ключ."
        return {
            "angle_type": str(parsed.get("angle_type") or fallback_angle_type).strip() or fallback_angle_type,
            "tone": str(parsed.get("tone") or fallback_tone).strip() or fallback_tone,
            "generated_text": message,
            "prompt_key": "outreach_first_message",
            "prompt_version": "v1",
            "prompt_source": "gigachat",
        }
    except Exception as exc:
        print(f"AI outreach first-message fallback: {exc}")
        return {
            "angle_type": fallback_angle_type,
            "tone": fallback_tone,
            "generated_text": fallback_message,
            "prompt_key": "outreach_first_message",
            "prompt_version": "fallback_v1",
            "prompt_source": "local_fallback",
        }


def _classify_reply_outcome(raw_reply: str) -> tuple[str, float]:
    text = (raw_reply or "").strip().lower()
    if not text:
        return "no_response", 0.9

    hard_no_signals = [
        "не интересно",
        "неактуально",
        "не надо",
        "не пишите",
        "удалите",
        "отстаньте",
        "stop",
        "не беспокоить",
    ]
    if any(signal in text for signal in hard_no_signals):
        return "hard_no", 0.9

    question_signals = ["?", "сколько", "как", "что", "подробнее", "цена", "стоимость", "какая"]
    if any(signal in text for signal in question_signals):
        return "question", 0.75

    positive_signals = [
        "интересно",
        "давайте",
        "актуально",
        "хорошо",
        "ок",
        "окей",
        "пришлите",
        "отправьте",
        "можно",
        "свяжитесь",
    ]
    if any(signal in text for signal in positive_signals):
        return "positive", 0.8

    return "question", 0.55


def _classify_reply_outcome_ai(raw_reply: str) -> tuple[str, float, str]:
    raw_reply = str(raw_reply or "").strip()
    if not raw_reply:
        outcome, confidence = _classify_reply_outcome("")
        return outcome, confidence, "heuristic"

    fallback_prompt = (
        "Ты классифицируешь ответ лида на первое аутрич-сообщение.\n"
        "Верни ТОЛЬКО JSON без пояснений.\n"
        "Допустимые значения outcome: positive, question, no_response, hard_no.\n"
        "confidence: число от 0 до 1.\n"
        "Правила:\n"
        "- positive: согласие, интерес, запрос прислать детали, готовность обсудить\n"
        "- question: вопрос, запрос уточнений, цены, условий, деталей\n"
        "- no_response: пустой/неинформативный ответ без явного интереса или отказа\n"
        "- hard_no: отказ, просьба не писать, негатив, stop\n"
        "Формат ответа:\n"
        "{\"outcome\":\"question\",\"confidence\":0.74}\n"
        "Текст ответа лида:\n"
        "{raw_reply}"
    )
    prompt_template = _get_prompt_from_db("outreach_reply_classification", fallback_prompt)
    prompt = prompt_template.replace("{raw_reply}", raw_reply)

    try:
        result_text = analyze_text_with_gigachat(prompt, task_type="ai_agent_marketing")
        parsed = _extract_json_candidate(result_text)
        if not parsed:
            raise ValueError("AI classifier did not return JSON")
        outcome = str(parsed.get("outcome") or "").strip().lower()
        if outcome not in ALLOWED_REPLY_OUTCOMES:
            raise ValueError(f"Unsupported outcome: {outcome}")
        confidence_raw = parsed.get("confidence", 0.7)
        try:
            confidence = float(confidence_raw)
        except Exception:
            confidence = 0.7
        confidence = max(0.0, min(1.0, confidence))
        return outcome, confidence, "ai"
    except Exception as exc:
        print(f"Outreach reply AI classification fallback: {exc}")
        outcome, confidence = _classify_reply_outcome(raw_reply)
        return outcome, confidence, "heuristic"


def _load_send_queue_snapshot():
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                d.id, d.lead_id, d.channel, d.status,
                d.generated_text, d.edited_text, d.approved_text,
                d.created_at, d.updated_at,
                l.name AS lead_name, l.category, l.city, l.selected_channel, l.status AS lead_status
            FROM outreachmessagedrafts d
            JOIN prospectingleads l ON l.id = d.lead_id
            WHERE d.status = %s
              AND NOT EXISTS (
                    SELECT 1
                    FROM outreachsendqueue q
                    WHERE q.draft_id = d.id
              )
            ORDER BY d.updated_at DESC, d.created_at DESC
            """,
            (DRAFT_APPROVED,),
        )
        ready_drafts = [_serialize_draft(dict(row)) for row in cur.fetchall()]

        cur.execute(
            """
            SELECT
                b.id, b.batch_date, b.daily_limit, b.status,
                b.created_by, b.approved_by, b.created_at, b.updated_at
            FROM outreachsendbatches b
            ORDER BY b.batch_date DESC, b.created_at DESC
            LIMIT 20
            """
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

        for batch in batch_rows:
            _apply_batch_runtime_state(batch)

        return {"ready_drafts": ready_drafts, "batches": batch_rows}
    finally:
        conn.close()


def _load_reactions(limit: int = 5000):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                r.id, r.queue_id, r.lead_id, r.raw_reply,
                r.classified_outcome, r.confidence, r.human_confirmed_outcome,
                r.note, r.created_by, r.created_at, r.updated_at,
                r.provider_name, r.provider_account_id, r.provider_message_id, r.reply_created_at,
                l.name AS lead_name,
                q.batch_id, q.channel, q.delivery_status
            FROM outreachreactions r
            JOIN prospectingleads l ON l.id = r.lead_id
            JOIN outreachsendqueue q ON q.id = r.queue_id
            ORDER BY r.created_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def _create_send_batch(user_id: str, draft_ids: list[str] | None = None):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        remaining_slots = _remaining_daily_outreach_slots(conn)
        if remaining_slots <= 0:
            return None, f"Daily outreach cap reached ({MAX_DAILY_OUTREACH_BATCH}/day)"

        query = """
            SELECT
                d.id, d.lead_id, d.channel,
                l.status AS lead_status,
                l.telegram_url,
                l.whatsapp_url,
                l.email
            FROM outreachmessagedrafts d
            JOIN prospectingleads l ON l.id = d.lead_id
            WHERE d.status = %s
              AND NOT EXISTS (
                    SELECT 1
                    FROM outreachsendqueue q
                    WHERE q.draft_id = d.id
              )
        """
        params: list[Any] = [DRAFT_APPROVED]
        if draft_ids:
            query += " AND d.id = ANY(%s)"
            params.append(draft_ids)
        query += " ORDER BY d.updated_at DESC, d.created_at DESC LIMIT %s"
        params.append(remaining_slots)
        cur.execute(query, params)
        selected_rows = [dict(row) for row in cur.fetchall()]
        valid_rows = [row for row in selected_rows if _lead_has_channel_contact(row, row.get("channel"))]

        if not valid_rows:
            return None, "No approved drafts available for queue"

        batch_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO outreachsendbatches (
                id, batch_date, daily_limit, status, created_by
            ) VALUES (
                %s, CURRENT_DATE, %s, %s, %s
            )
            """,
            (batch_id, MAX_DAILY_OUTREACH_BATCH, BATCH_DRAFT, user_id),
        )

        for row in valid_rows:
            queue_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO outreachsendqueue (
                    id, batch_id, lead_id, draft_id, channel, delivery_status
                ) VALUES (
                    %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    queue_id,
                    batch_id,
                    row["lead_id"],
                    row["id"],
                    row["channel"],
                    QUEUE_STATUS_QUEUED,
                ),
            )
            cur.execute(
                """
                UPDATE prospectingleads
                SET status = %s,
                    pipeline_status = %s,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (QUEUED_FOR_SEND, PIPELINE_IN_PROGRESS, row["lead_id"]),
            )

        conn.commit()
        return batch_id, None
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _load_send_batch(batch_id: str) -> dict[str, Any] | None:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, batch_date, daily_limit, status, created_by, approved_by, created_at, updated_at
            FROM outreachsendbatches
            WHERE id = %s
            """,
            (batch_id,),
        )
        row = cur.fetchone()
        return _serialize_batch_row(dict(row)) if row else None
    finally:
        conn.close()


def _load_send_batch_with_items(batch_id: str) -> dict[str, Any] | None:
    batch = _load_send_batch(batch_id)
    if not batch:
        return None
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                q.id, q.batch_id, q.lead_id, q.draft_id, q.channel,
                q.delivery_status, q.provider_message_id, q.error_text,
                q.sent_at, q.attempts, q.last_attempt_at, q.next_retry_at, q.dlq_at,
                q.created_at, q.updated_at,
                l.name AS lead_name,
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
            WHERE q.batch_id = %s
            ORDER BY q.created_at ASC
            """,
            (batch_id,),
        )
        batch["items"] = [dict(row) for row in cur.fetchall()]
        return batch
    finally:
        conn.close()


def _summarize_batch_items(items: list[dict[str, Any]]) -> dict[str, int]:
    summary = {
        "total": len(items),
        "queued": 0,
        "sending": 0,
        "sent": 0,
        "delivered": 0,
        "retry": 0,
        "failed": 0,
        "dlq": 0,
        "with_reaction": 0,
    }
    for item in items:
        status = str(item.get("delivery_status") or "").strip().lower()
        if status in summary:
            summary[status] += 1
        if item.get("latest_outcome") or item.get("latest_human_outcome") or item.get("latest_raw_reply"):
            summary["with_reaction"] += 1
    return summary


def _batch_runtime_status_from_summary(batch_status: str, summary: dict[str, int]) -> str:
    if batch_status == BATCH_DRAFT:
        return BATCH_DRAFT
    if summary.get("sending", 0) > 0:
        return "sending"
    waiting = summary.get("queued", 0) + summary.get("retry", 0)
    finished = summary.get("sent", 0) + summary.get("delivered", 0) + summary.get("failed", 0) + summary.get("dlq", 0)
    total = summary.get("total", 0)
    if total > 0 and finished >= total and waiting == 0:
        return "completed"
    return BATCH_APPROVED


def _apply_batch_runtime_state(batch: dict[str, Any] | None) -> dict[str, Any] | None:
    if not batch:
        return None
    items = batch.get("items")
    if not isinstance(items, list):
        items = []
        batch["items"] = items
    summary = _summarize_batch_items(items)
    batch["queue_summary"] = summary
    batch["runtime_status"] = _batch_runtime_status_from_summary(str(batch.get("status") or ""), summary)
    return batch


def _approve_send_batch(batch_id: str, user_id: str):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE outreachsendbatches
            SET status = %s,
                approved_by = %s,
                updated_at = NOW()
            WHERE id = %s
              AND status = %s
            RETURNING id, batch_date, daily_limit, status, created_by, approved_by, created_at, updated_at
            """,
            (BATCH_APPROVED, user_id, batch_id, BATCH_DRAFT),
        )
        row = cur.fetchone()
        if not row:
            cur.execute(
                """
                SELECT id, batch_date, daily_limit, status, created_by, approved_by, created_at, updated_at
                FROM outreachsendbatches
                WHERE id = %s
                """,
                (batch_id,),
            )
            existing = cur.fetchone()
            if not existing:
                return None, "Batch not found"
            return None, "Batch is not in draft status"
        conn.commit()
        batch = _load_send_batch_with_items(batch_id)
        batch = _apply_batch_runtime_state(batch)
        if not batch:
            return None, "Batch not found"
        batch["dispatch_summary"] = {
            "queued": int(batch.get("queue_summary", {}).get("queued", 0)),
            "sent": int(batch.get("queue_summary", {}).get("sent", 0)),
            "failed": int(batch.get("queue_summary", {}).get("failed", 0)),
            "total": int(batch.get("queue_summary", {}).get("total", 0)),
        }
        return batch, None
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def dispatch_due_outreach_queue(batch_size: int = 20, batch_id: str | None = None, force_ready: bool = False) -> dict[str, Any]:
    """Фоновый диспетчер outbound-очереди outreach: queued/retry -> sent/retry/dlq."""
    safe_batch_size = max(1, min(int(batch_size or 20), 200))
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        query = """
            WITH due AS (
                SELECT
                    q.id
                FROM outreachsendqueue q
                JOIN outreachsendbatches b ON b.id = q.batch_id
                WHERE b.status = %s
        """
        params: list[Any] = [BATCH_APPROVED]
        if batch_id:
            query += " AND q.batch_id = %s"
            params.append(batch_id)
        query += """
                  AND (
                    q.delivery_status = %s
        """
        params.append(QUEUE_STATUS_QUEUED)
        if force_ready:
            query += """
                    OR q.delivery_status = %s
            """
            params.append(QUEUE_STATUS_RETRY)
        else:
            query += """
                    OR (
                        q.delivery_status = %s
                        AND q.next_retry_at IS NOT NULL
                        AND q.next_retry_at <= NOW()
                    )
            """
            params.append(QUEUE_STATUS_RETRY)
        query += """
                  )
                ORDER BY COALESCE(q.next_retry_at, q.created_at) ASC
                LIMIT %s
                FOR UPDATE SKIP LOCKED
            )
            UPDATE outreachsendqueue q
            SET delivery_status = %s,
                attempts = COALESCE(q.attempts, 0) + 1,
                last_attempt_at = NOW(),
                updated_at = NOW()
            FROM due
            WHERE q.id = due.id
            RETURNING q.id, q.batch_id, q.lead_id, q.draft_id, q.channel, q.delivery_status,
                      q.attempts, q.provider_message_id, q.error_text
        """
        params.extend(
            [
                safe_batch_size,
                QUEUE_STATUS_SENDING,
            ]
        )
        cur.execute(
            query,
            params,
        )
        claimed = [dict(row) for row in cur.fetchall()]
        if claimed:
            queue_ids = [str(row.get("id") or "") for row in claimed if str(row.get("id") or "")]
            if queue_ids:
                placeholders = ",".join(["%s"] * len(queue_ids))
                cur.execute(
                    f"""
                    SELECT
                        q.id,
                        l.name AS lead_name,
                        l.phone,
                        l.email,
                        l.telegram_url,
                        l.whatsapp_url,
                        l.selected_channel,
                        d.approved_text,
                        d.generated_text
                    FROM outreachsendqueue q
                    LEFT JOIN outreachmessagedrafts d ON d.id = q.draft_id
                    LEFT JOIN prospectingleads l ON l.id = q.lead_id
                    WHERE q.id IN ({placeholders})
                    """,
                    tuple(queue_ids),
                )
                detail_map = {str(row.get("id") or ""): dict(row) for row in cur.fetchall()}
                for row in claimed:
                    row_id = str(row.get("id") or "")
                    details = detail_map.get(row_id) or {}
                    row.update(
                        {
                            "lead_name": details.get("lead_name"),
                            "phone": details.get("phone"),
                            "email": details.get("email"),
                            "telegram_url": details.get("telegram_url"),
                            "whatsapp_url": details.get("whatsapp_url"),
                            "selected_channel": details.get("selected_channel"),
                            "approved_text": details.get("approved_text"),
                            "generated_text": details.get("generated_text"),
                        }
                    )
        conn.commit()

        summary = {
            "success": True,
            "batch_id": batch_id,
            "picked": len(claimed),
            "sent": 0,
            "delivered": 0,
            "retry": 0,
            "dlq": 0,
            "failed": 0,
            "results": [],
        }
        if not claimed:
            return summary

        for item in claimed:
            queue_id = str(item.get("id") or "")
            lead_id = str(item.get("lead_id") or "")
            attempt_no = int(item.get("attempts") or 1)
            dispatch_result = _dispatch_outreach_queue_item(item)
            delivery_status = str(dispatch_result.get("delivery_status") or QUEUE_STATUS_FAILED).strip().lower()
            provider_message_id = dispatch_result.get("provider_message_id")
            provider_name = dispatch_result.get("provider_name")
            provider_account_id = dispatch_result.get("provider_account_id")
            recipient_kind = dispatch_result.get("recipient_kind")
            recipient_value = dispatch_result.get("recipient_value")
            error_text = str(dispatch_result.get("error_text") or "").strip()[:500] or None
            retryable = bool(dispatch_result.get("retryable", True))

            update_conn = get_db_connection()
            try:
                update_cur = update_conn.cursor()
                if delivery_status in {QUEUE_STATUS_SENT, QUEUE_STATUS_DELIVERED}:
                    update_cur.execute(
                        """
                        UPDATE outreachsendqueue
                        SET delivery_status = %s,
                            provider_message_id = %s,
                            provider_name = %s,
                            provider_account_id = %s,
                            recipient_kind = %s,
                            recipient_value = %s,
                            error_text = NULL,
                            sent_at = COALESCE(sent_at, NOW()),
                            next_retry_at = NULL,
                            dlq_at = NULL,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (
                            delivery_status,
                            provider_message_id,
                            provider_name,
                            provider_account_id,
                            recipient_kind,
                            recipient_value,
                            queue_id,
                        ),
                    )
                    update_cur.execute(
                        """
                        UPDATE prospectingleads
                        SET status = %s,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        ("sent", lead_id),
                    )
                    if delivery_status == QUEUE_STATUS_DELIVERED:
                        summary["delivered"] += 1
                    else:
                        summary["sent"] += 1
                else:
                    retry_delay = _outreach_retry_delay_for_attempt(attempt_no) if retryable else None
                    exhausted = (attempt_no >= OUTREACH_SEND_MAX_ATTEMPTS or retry_delay is None) and retryable
                    if not retryable:
                        next_status = QUEUE_STATUS_FAILED
                        next_retry_at = None
                        dlq_at_sql = "NULL"
                    elif exhausted:
                        next_status = QUEUE_STATUS_DLQ
                        next_retry_at = None
                        dlq_at_sql = "NOW()"
                        summary["dlq"] += 1
                    else:
                        next_status = QUEUE_STATUS_RETRY
                        next_retry_at = datetime.now(timezone.utc) + retry_delay
                        dlq_at_sql = "NULL"
                        summary["retry"] += 1
                    update_cur.execute(
                        f"""
                        UPDATE outreachsendqueue
                        SET delivery_status = %s,
                            provider_message_id = %s,
                            provider_name = %s,
                            provider_account_id = %s,
                            recipient_kind = %s,
                            recipient_value = %s,
                            error_text = %s,
                            next_retry_at = %s,
                            dlq_at = {dlq_at_sql},
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (
                            next_status,
                            provider_message_id,
                            provider_name,
                            provider_account_id,
                            recipient_kind,
                            recipient_value,
                            error_text,
                            next_retry_at,
                            queue_id,
                        ),
                    )
                    update_cur.execute(
                        """
                        UPDATE prospectingleads
                        SET status = %s,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (CHANNEL_SELECTED, lead_id),
                    )
                    summary["failed"] += 1
                update_conn.commit()
            except Exception:
                update_conn.rollback()
                raise
            finally:
                update_conn.close()

            summary["results"].append(
                {
                    "queue_id": queue_id,
                    "lead_id": lead_id,
                    "channel": item.get("channel"),
                    "attempt_no": attempt_no,
                    "delivery_status": delivery_status,
                    "provider_message_id": provider_message_id,
                    "provider_name": provider_name,
                    "provider_account_id": provider_account_id,
                    "recipient_kind": recipient_kind,
                    "recipient_value": recipient_value,
                    "error_text": error_text,
                }
            )
            if len(claimed) > 1 and queue_id != str(claimed[-1].get("id") or ""):
                delay_seconds = random.uniform(OUTREACH_SEND_DELAY_MIN_SEC, OUTREACH_SEND_DELAY_MAX_SEC)
                if delay_seconds > 0:
                    time.sleep(delay_seconds)
        return summary
    finally:
        conn.close()


def _dispatch_send_batch_async(batch_id: str, batch_size: int | None = None) -> None:
    target_batch = _load_send_batch_with_items(batch_id)
    if not target_batch:
        return
    target_batch = _apply_batch_runtime_state(target_batch)
    queue_summary = target_batch.get("queue_summary", {}) if target_batch else {}
    waiting_count = int(queue_summary.get("queued", 0)) + int(queue_summary.get("retry", 0))
    if waiting_count <= 0:
        return
    dispatch_due_outreach_queue(batch_size=batch_size or waiting_count, batch_id=batch_id, force_ready=True)


def _start_batch_dispatch(batch_id: str) -> tuple[dict[str, Any] | None, str | None]:
    batch = _load_send_batch_with_items(batch_id)
    batch = _apply_batch_runtime_state(batch)
    if not batch:
        return None, "Batch not found"
    if str(batch.get("status") or "") == BATCH_DRAFT:
        return None, "Batch must be approved before dispatch"
    runtime_status = str(batch.get("runtime_status") or "")
    if runtime_status == "sending":
        return None, "Batch is already sending"
    queue_summary = batch.get("queue_summary", {}) if isinstance(batch.get("queue_summary"), dict) else {}
    waiting_count = int(queue_summary.get("queued", 0)) + int(queue_summary.get("retry", 0))
    if waiting_count <= 0:
        return None, "No queued items left for dispatch"

    thread = threading.Thread(target=_dispatch_send_batch_async, args=(batch_id, waiting_count), daemon=True)
    thread.start()
    batch["runtime_status"] = "sending"
    return batch, None


def _extract_telegram_handle(raw_value: str | None) -> str:
    raw = str(raw_value or "").strip()
    if not raw:
        return ""
    if raw.startswith("@"):
        return raw[1:].strip()
    for prefix in ("https://t.me/", "http://t.me/", "https://telegram.me/", "http://telegram.me/"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            break
    raw = raw.strip().strip("/")
    if "/" in raw:
        raw = raw.split("/", 1)[0]
    if "?" in raw:
        raw = raw.split("?", 1)[0]
    if raw.startswith("+"):
        return ""
    if raw.isdigit():
        return ""
    return raw.strip().lstrip("@")


def _extract_telegram_invite_link(raw_value: str | None) -> str:
    raw = str(raw_value or "").strip()
    if not raw:
        return ""
    for prefix in ("https://t.me/", "http://t.me/", "https://telegram.me/", "http://telegram.me/"):
        if raw.startswith(prefix):
            suffix = raw[len(prefix):].strip().strip("/")
            suffix = suffix.split("?", 1)[0].split("#", 1)[0].strip()
            if suffix.startswith("+"):
                return raw
            return ""
    return ""


def _resolve_telegram_app_account(account_id: str | None = None) -> dict[str, Any] | None:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        account = load_userbot_account(cur, business_id=None, account_id=account_id)
        if not account:
            return None
        return account
    finally:
        conn.close()


def _telegram_app_status_payload() -> dict[str, Any]:
    account = _resolve_telegram_app_account()
    if not account:
        return {
            "configured": False,
            "authorized": False,
            "phone": None,
            "account_id": None,
            "status": "missing",
        }
    session_string = str(account.get("session_string") or "").strip()
    return {
        "configured": True,
        "authorized": bool(session_string),
        "phone": str(account.get("phone") or "").strip() or None,
        "account_id": str(account.get("account_id") or "").strip() or None,
        "status": "ready" if session_string else "not_authorized",
    }


def _resolve_telegram_app_recipient(lead: dict[str, Any]) -> dict[str, str] | None:
    handle = _extract_telegram_handle(lead.get("telegram_url"))
    if handle:
        return {
            "recipient_kind": "username",
            "recipient_value": f"@{handle}",
        }
    invite_link = _extract_telegram_invite_link(lead.get("telegram_url"))
    if invite_link:
        return {
            "recipient_kind": "invite_link",
            "recipient_value": invite_link,
        }
    phone = normalize_phone(lead.get("phone"))
    if phone:
        return {
            "recipient_kind": "phone",
            "recipient_value": phone,
        }
    return None


def _classify_telegram_app_error(exc: Exception) -> tuple[str, bool, str]:
    text = str(exc or "").strip()
    lowered = text.lower()
    class_name = exc.__class__.__name__.lower()

    if "floodwait" in class_name or "flood wait" in lowered or "a wait of" in lowered:
        return "telegram_flood_wait", True, text or "Flood wait from Telegram"
    if "invitehashexpired" in class_name or "checkchatinvite" in lowered or "invite link" in lowered:
        return "telegram_invite_expired", False, text or "Telegram invite link is expired"
    if "usernameinvalid" in class_name or "usernamenotoccupied" in class_name or "peeridinvalid" in class_name:
        return "telegram_peer_not_found", False, text or "Telegram peer not found"
    if "privacy" in class_name or "you can't write in this chat" in lowered or "cannot send messages" in lowered:
        return "telegram_privacy_restricted", False, text or "Telegram privacy restriction"
    if "timeout" in lowered or "timed out" in lowered or "connection" in lowered or "network" in lowered:
        return "telegram_send_failed", True, text or "Temporary Telegram transport failure"
    return "telegram_send_failed", True, text or "Telegram send failed"


def _classify_telegram_sync_error(exc: Exception) -> tuple[str, bool, str]:
    text = str(exc or "").strip()
    lowered = text.lower()
    class_name = exc.__class__.__name__.lower()

    if "floodwait" in class_name or "flood wait" in lowered or "a wait of" in lowered:
        return "telegram_flood_wait", True, text or "Flood wait from Telegram"
    if "usernameinvalid" in class_name or "usernamenotoccupied" in class_name or "peeridinvalid" in class_name:
        return "telegram_peer_not_found", False, text or "Telegram peer not found"
    if "privacy" in class_name or "you can't write in this chat" in lowered or "cannot find any entity" in lowered:
        return "telegram_peer_not_found", False, text or "Telegram peer not found"
    if "timeout" in lowered or "timed out" in lowered or "connection" in lowered or "network" in lowered:
        return "telegram_sync_failed", True, text or "Temporary Telegram transport failure"
    return "telegram_sync_failed", True, text or "Telegram sync failed"


def _normalize_provider_message_id(value: Any) -> str | None:
    normalized = str(value or "").strip()
    return normalized[:255] if normalized else None


def _fetch_telegram_replies_subprocess(
    account: dict[str, Any],
    recipient_value: str,
    *,
    sent_after: Any = None,
    after_message_id: Any = None,
    limit: int = TELEGRAM_REPLY_SYNC_PER_CHAT_LIMIT,
) -> dict[str, Any]:
    payload = {
        "account": _to_json_compatible(account),
        "recipient": recipient_value,
        "sent_after": _to_json_compatible(sent_after),
        "after_message_id": _to_json_compatible(after_message_id),
        "limit": int(limit or TELEGRAM_REPLY_SYNC_PER_CHAT_LIMIT),
    }
    runner = """
import json
import sys
from src.core.telegram_userbot import fetch_recent_replies

payload = json.loads(sys.stdin.read() or "{}")
result = fetch_recent_replies(
    payload.get("account") or {},
    payload.get("recipient") or "",
    sent_after=payload.get("sent_after"),
    after_message_id=payload.get("after_message_id"),
    limit=payload.get("limit") or 20,
)
print(json.dumps(result, ensure_ascii=False))
"""
    def _clean_subprocess_error(raw: str) -> str:
        lines = [line.strip() for line in str(raw or "").splitlines() if line.strip()]
        if not lines:
            return ""
        for line in reversed(lines):
            if "Traceback" in line:
                continue
            return line[:500]
        return lines[-1][:500]

    try:
        completed = subprocess.run(
            [sys.executable, "-c", runner],
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True,
            text=True,
            timeout=TELEGRAM_REPLY_SYNC_TIMEOUT_SEC,
            cwd="/app",
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"Timed out after {TELEGRAM_REPLY_SYNC_TIMEOUT_SEC}s") from exc

    stdout = str(completed.stdout or "").strip()
    if completed.returncode != 0:
        stderr = _clean_subprocess_error(completed.stderr or completed.stdout)
        raise RuntimeError(stderr or f"telegram reply subprocess failed with code {completed.returncode}")
    if not stdout:
        return {"status": "ok", "replies": []}
    try:
        return json.loads(stdout.splitlines()[-1])
    except Exception as exc:
        raise RuntimeError(f"Invalid telegram reply subprocess output: {stdout[:400]}") from exc


def _dispatch_via_telegram_app(item: dict[str, Any], message: str) -> dict[str, Any]:
    account = _resolve_telegram_app_account()
    if not account:
        return {
            "success": False,
            "error_code": "telegram_app_missing",
            "error_text": "Telegram app is not configured",
            "retryable": False,
        }

    account_id = str(account.get("account_id") or "").strip() or None
    session_string = str(account.get("session_string") or "").strip()
    if not session_string:
        return {
            "success": False,
            "error_code": "telegram_app_not_authorized",
            "error_text": "Telegram app is not authorized",
            "retryable": False,
            "provider_name": "telegram_app",
            "provider_account_id": account_id,
        }

    recipient = _resolve_telegram_app_recipient(item)
    if not recipient:
        return {
            "success": False,
            "error_code": "telegram_recipient_missing",
            "error_text": "Lead has no Telegram username and no fallback phone",
            "retryable": False,
            "provider_name": "telegram_app",
            "provider_account_id": account_id,
        }

    try:
        send_result = userbot_send_message(account, recipient["recipient_value"], message)
    except Exception as exc:
        error_code, retryable, error_text = _classify_telegram_app_error(exc)
        return {
            "success": False,
            "error_code": error_code,
            "error_text": error_text[:500],
            "retryable": retryable,
            "provider_name": "telegram_app",
            "provider_account_id": account_id,
            "recipient_kind": recipient["recipient_kind"],
            "recipient_value": recipient["recipient_value"],
        }

    status = str(send_result.get("status") or "").strip().lower()
    if status == "not_authorized":
        return {
            "success": False,
            "error_code": "telegram_app_not_authorized",
            "error_text": "Telegram app is not authorized",
            "retryable": False,
            "provider_name": "telegram_app",
            "provider_account_id": account_id,
            "recipient_kind": recipient["recipient_kind"],
            "recipient_value": recipient["recipient_value"],
            "route_label": str(send_result.get("route_label") or "").strip() or None,
            "route_target": str(send_result.get("route_target") or "").strip() or None,
        }
    if status != "sent":
        return {
            "success": False,
            "error_code": "telegram_send_failed",
            "error_text": f"Unexpected Telegram app status: {status or 'unknown'}",
            "retryable": True,
            "provider_name": "telegram_app",
            "provider_account_id": account_id,
            "recipient_kind": recipient["recipient_kind"],
            "recipient_value": recipient["recipient_value"],
            "route_label": str(send_result.get("route_label") or "").strip() or None,
            "route_target": str(send_result.get("route_target") or "").strip() or None,
        }

    provider_message_id = str(send_result.get("message_id") or "").strip()
    return {
        "success": True,
        "provider_name": "telegram_app",
        "provider_account_id": account_id,
        "recipient_kind": recipient["recipient_kind"],
        "recipient_value": recipient["recipient_value"],
        "provider_message_id": provider_message_id or f"telegram_app:{item.get('id')}",
        "route_label": str(send_result.get("route_label") or "").strip() or None,
        "route_target": str(send_result.get("route_target") or "").strip() or None,
    }


def _load_telegram_reply_sync_candidates(limit: int = 25, batch_id: str | None = None) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit or 25), 200))
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        query = """
            SELECT
                q.id,
                q.batch_id,
                q.lead_id,
                q.channel,
                q.delivery_status,
                q.provider_name,
                q.provider_account_id,
                q.provider_message_id,
                q.recipient_kind,
                q.recipient_value,
                q.sent_at,
                l.name AS lead_name
            FROM outreachsendqueue q
            JOIN prospectingleads l ON l.id = q.lead_id
            WHERE q.provider_name = 'telegram_app'
              AND q.delivery_status IN (%s, %s)
              AND q.provider_account_id IS NOT NULL
              AND q.recipient_value IS NOT NULL
              AND q.sent_at >= NOW() - (%s || ' days')::interval
        """
        params: list[Any] = [QUEUE_STATUS_SENT, QUEUE_STATUS_DELIVERED, TELEGRAM_REPLY_SYNC_LOOKBACK_DAYS]
        if batch_id:
            query += " AND q.batch_id = %s"
            params.append(batch_id)
        query += """
            ORDER BY COALESCE(q.sent_at, q.updated_at, q.created_at) DESC
            LIMIT %s
        """
        params.append(safe_limit)
        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def _sync_telegram_app_replies_for_queue_item(
    item: dict[str, Any],
    *,
    per_chat_limit: int = TELEGRAM_REPLY_SYNC_PER_CHAT_LIMIT,
) -> dict[str, Any]:
    queue_id = str(item.get("id") or "").strip()
    if not queue_id:
        return {"status": "skipped", "reason": "missing_queue_id", "imported": 0, "duplicates": 0}

    provider_account_id = str(item.get("provider_account_id") or "").strip()
    account = _resolve_telegram_app_account(provider_account_id or None)
    if not account:
        return {"status": "failed", "reason": "telegram_app_missing", "imported": 0, "duplicates": 0}

    session_string = str(account.get("session_string") or "").strip()
    if not session_string:
        return {"status": "failed", "reason": "telegram_app_not_authorized", "imported": 0, "duplicates": 0}

    recipient_value = str(item.get("recipient_value") or "").strip()
    if not recipient_value:
        return {"status": "failed", "reason": "telegram_recipient_missing", "imported": 0, "duplicates": 0}

    try:
        replies_result = _fetch_telegram_replies_subprocess(
            account,
            recipient_value,
            sent_after=item.get("sent_at"),
            after_message_id=item.get("provider_message_id"),
            limit=per_chat_limit,
        )
    except Exception as exc:
        error_code, retryable, error_text = _classify_telegram_sync_error(exc)
        return {
            "status": "failed",
            "reason": error_code,
            "retryable": retryable,
            "error_text": error_text[:500],
            "imported": 0,
            "duplicates": 0,
        }

    fetch_status = str(replies_result.get("status") or "").strip().lower()
    if fetch_status == "not_authorized":
        return {"status": "failed", "reason": "telegram_app_not_authorized", "imported": 0, "duplicates": 0}
    if fetch_status != "ok":
        return {
            "status": "failed",
            "reason": "telegram_sync_failed",
            "error_text": str(replies_result.get("error") or f"Unexpected Telegram sync status: {fetch_status or 'unknown'}")[:500],
            "imported": 0,
            "duplicates": 0,
        }

    replies = replies_result.get("replies") if isinstance(replies_result.get("replies"), list) else []
    imported = 0
    duplicates = 0
    last_reaction = None
    for reply in replies:
        provider_message_id = _normalize_provider_message_id(reply.get("message_id"))
        reaction, reaction_error = _record_reaction(
            queue_id,
            reply.get("text"),
            None,
            f"sync=telegram_app; recipient={recipient_value}; provider_message_id={provider_message_id or '-'}",
            "system:telegram_app_sync",
            provider_name="telegram_app",
            provider_account_id=provider_account_id,
            provider_message_id=provider_message_id,
            reply_created_at=reply.get("created_at"),
            prefer_ai=False,
        )
        if reaction_error == "Reaction already recorded":
            duplicates += 1
            continue
        if reaction_error:
            return {
                "status": "failed",
                "reason": "reaction_record_failed",
                "error_text": reaction_error,
                "imported": imported,
                "duplicates": duplicates,
            }
        imported += 1
        last_reaction = reaction

    if imported > 0:
        return {
            "status": "imported",
            "imported": imported,
            "duplicates": duplicates,
            "last_reaction": last_reaction,
        }
    return {
        "status": "noop",
        "imported": 0,
        "duplicates": duplicates,
    }


def _sync_telegram_app_replies(batch_id: str | None = None, limit: int = 25) -> dict[str, Any]:
    items = _load_telegram_reply_sync_candidates(limit=limit, batch_id=batch_id)
    summary = {
        "success": True,
        "batch_id": batch_id,
        "picked": len(items),
        "imported": 0,
        "duplicates": 0,
        "noops": 0,
        "failed": 0,
        "results": [],
    }
    for item in items:
        result = _sync_telegram_app_replies_for_queue_item(item)
        summary["results"].append(
            {
                "queue_id": item.get("id"),
                "lead_id": item.get("lead_id"),
                "lead_name": item.get("lead_name"),
                **result,
            }
        )
        if result.get("status") == "imported":
            summary["imported"] += int(result.get("imported") or 0)
            summary["duplicates"] += int(result.get("duplicates") or 0)
        elif result.get("status") == "noop":
            summary["duplicates"] += int(result.get("duplicates") or 0)
            summary["noops"] += 1
        else:
            summary["failed"] += 1
    return summary


def _resolve_outreach_maton_key() -> str:
    return (
        str(os.getenv("MATON_OUTREACH_API_KEY", "") or "").strip()
        or str(os.getenv("MATON_API_KEY", "") or "").strip()
    )


def _resolve_outreach_openclaw_endpoint() -> str:
    return str(os.getenv("OPENCLAW_OUTREACH_SEND_URL", "") or "").strip()


def _resolve_outreach_openclaw_token() -> str:
    return (
        str(os.getenv("OPENCLAW_OUTREACH_TOKEN", "") or "").strip()
        or str(os.getenv("OPENCLAW_LOCALOS_TOKEN", "") or "").strip()
    )


def _is_outreach_openclaw_strict() -> bool:
    return str(os.getenv("OPENCLAW_OUTREACH_STRICT", "") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _resolve_outreach_openclaw_health_endpoint() -> str:
    explicit = str(os.getenv("OPENCLAW_OUTREACH_HEALTH_URL", "") or "").strip()
    if explicit:
        return explicit
    endpoint = _resolve_outreach_openclaw_endpoint()
    if not endpoint:
        return ""
    base = endpoint.split("?", 1)[0].rstrip("/")
    if "/" in base:
        base = base.rsplit("/", 1)[0]
    if base.endswith("/capabilities"):
        base = base.rsplit("/", 1)[0]
    return f"{base}/healthz"


def _resolve_partnership_openclaw_caps_endpoint() -> str:
    return (
        str(os.getenv("OPENCLAW_PARTNERS_CAPS_URL", "") or "").strip()
        or str(os.getenv("OPENCLAW_SANDBOX_BRIDGE_URL", "") or "").strip()
    )


def _resolve_partnership_openclaw_token() -> str:
    return (
        str(os.getenv("OPENCLAW_PARTNERS_TOKEN", "") or "").strip()
        or str(os.getenv("OPENCLAW_SANDBOX_BRIDGE_TOKEN", "") or "").strip()
        or str(os.getenv("OPENCLAW_LOCALOS_TOKEN", "") or "").strip()
    )


def _is_partnership_openclaw_enabled() -> bool:
    value = str(os.getenv("OPENCLAW_PARTNERS_ENABLED", "1") or "1").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _call_partnership_openclaw_capability(
    capability: str,
    *,
    tenant_id: str,
    payload: dict[str, Any],
    timeout_sec: int = 35,
) -> dict[str, Any]:
    endpoint = _resolve_partnership_openclaw_caps_endpoint()
    token = _resolve_partnership_openclaw_token()
    if not endpoint:
        return {"success": False, "error": "OPENCLAW_PARTNERS_CAPS_URL is not configured"}
    if not token:
        return {"success": False, "error": "OPENCLAW_PARTNERS_TOKEN is not configured"}

    base = endpoint.rstrip("/")
    if base.endswith("/capabilities"):
        url = f"{base}/{capability}"
    else:
        url = base

    body = dict(payload or {})
    body.setdefault("tenant_id", tenant_id)

    headers = {
        "Authorization": f"Bearer {token}",
        "X-OpenClaw-Internal-Token": token,
        "X-Tenant-Id": tenant_id,
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(url, json=body, headers=headers, timeout=timeout_sec)
    except Exception as exc:
        return {"success": False, "error": f"OpenClaw request failed: {exc}"}

    try:
        data = response.json() if response.content else {}
    except Exception:
        data = {}

    if response.status_code >= 400:
        return {"success": False, "error": f"OpenClaw HTTP {response.status_code}: {data or response.text}"}

    ok = bool(data.get("success", True) or data.get("ok"))
    return {"success": ok, "data": data, "error": str(data.get("error") or "").strip() or None}


def _dispatch_via_openclaw(item: dict[str, Any], channel: str, message: str) -> dict[str, Any]:
    endpoint = _resolve_outreach_openclaw_endpoint()
    token = _resolve_outreach_openclaw_token()
    if not endpoint:
        return {"success": False, "error": "OPENCLAW_OUTREACH_SEND_URL is not configured"}
    if not token:
        return {"success": False, "error": "OPENCLAW_OUTREACH_TOKEN is not configured"}

    payload = {
        "channel": channel,
        "message": message,
        "lead": {
            "id": item.get("lead_id"),
            "name": item.get("lead_name"),
            "phone": item.get("phone"),
            "email": item.get("email"),
            "telegram_url": item.get("telegram_url"),
            "whatsapp_url": item.get("whatsapp_url"),
        },
        "meta": {
            "queue_id": item.get("id"),
            "batch_id": item.get("batch_id"),
            "draft_id": item.get("draft_id"),
            "source": "localos_outreach",
        },
    }

    try:
        resp = requests.post(
            endpoint,
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )
    except Exception as exc:
        return {"success": False, "error": f"OpenClaw request failed: {exc}"}

    try:
        data = resp.json() if resp.content else {}
    except Exception:
        data = {}

    if resp.status_code >= 400:
        return {"success": False, "error": f"OpenClaw HTTP {resp.status_code}: {data or resp.text}"}

    ok = bool(data.get("success") or data.get("ok") or data.get("accepted"))
    if not ok:
        return {"success": False, "error": str(data.get('error') or data or 'OpenClaw delivery failed')}
    provider_id = (
        str(data.get("message_id") or data.get("delivery_id") or data.get("action_id") or "").strip()
        or f"openclaw:{channel}:{item.get('id')}"
    )
    return {
        "success": True,
        "provider_name": "openclaw",
        "recipient_kind": channel,
        "recipient_value": (
            _extract_telegram_handle(item.get("telegram_url")) if channel == "telegram"
            else normalize_phone(item.get("whatsapp_url") or item.get("phone")) if channel == "whatsapp"
            else str(item.get("email") or "").strip() if channel == "email"
            else ""
        ) or None,
        "provider_message_id": provider_id,
    }


def _dispatch_outreach_queue_item(item: dict[str, Any]) -> dict[str, Any]:
    channel = str(item.get("channel") or item.get("selected_channel") or "").strip().lower()
    message = str(item.get("approved_text") or item.get("generated_text") or "").strip()
    strict_openclaw = _is_outreach_openclaw_strict()
    if not channel:
        return {"delivery_status": QUEUE_STATUS_FAILED, "error_text": "No channel selected"}
    if not message:
        return {"delivery_status": QUEUE_STATUS_FAILED, "error_text": "Draft text is empty"}

    if channel == "manual":
        return {
            "delivery_status": QUEUE_STATUS_DELIVERED,
            "provider_message_id": f"manual:{item.get('id')}",
            "provider_name": "manual",
            "recipient_kind": "manual",
            "recipient_value": None,
            "error_text": None,
            "retryable": False,
        }

    if channel == "max":
        return {
            "delivery_status": QUEUE_STATUS_FAILED,
            "error_text": "MAX delivery is not configured for outreach yet",
            "provider_name": "max",
            "retryable": False,
        }

    if channel == "email":
        return {
            "delivery_status": QUEUE_STATUS_FAILED,
            "error_text": "Email provider is not configured for outreach yet",
            "provider_name": "email",
            "retryable": False,
        }

    if channel == "telegram":
        telegram_result = _dispatch_via_telegram_app(item, message)
        if telegram_result.get("success"):
            return {
                "delivery_status": QUEUE_STATUS_SENT,
                "provider_message_id": str(telegram_result.get("provider_message_id") or "")[:255] or None,
                "provider_name": str(telegram_result.get("provider_name") or "telegram_app"),
                "provider_account_id": str(telegram_result.get("provider_account_id") or "")[:255] or None,
                "recipient_kind": str(telegram_result.get("recipient_kind") or "")[:64] or None,
                "recipient_value": str(telegram_result.get("recipient_value") or "")[:255] or None,
                "error_text": None,
                "retryable": False,
            }
        return {
            "delivery_status": QUEUE_STATUS_FAILED,
            "provider_name": str(telegram_result.get("provider_name") or "telegram_app"),
            "provider_account_id": str(telegram_result.get("provider_account_id") or "")[:255] or None,
            "recipient_kind": str(telegram_result.get("recipient_kind") or "")[:64] or None,
            "recipient_value": str(telegram_result.get("recipient_value") or "")[:255] or None,
            "error_text": (
                f"{telegram_result.get('error_code')}: {telegram_result.get('error_text')}"
                if telegram_result.get("error_code") and telegram_result.get("error_text")
                else str(telegram_result.get("error_code") or telegram_result.get("error_text") or "Telegram app delivery failed")
            )[:500],
            "retryable": bool(telegram_result.get("retryable", False)),
        }

    # Runtime-first outbound via OpenClaw for supported machine channels.
    if channel in {"whatsapp", "email"}:
        openclaw_result = _dispatch_via_openclaw(item, channel, message)
        if openclaw_result.get("success"):
            return {
                "delivery_status": QUEUE_STATUS_SENT,
                "provider_message_id": str(openclaw_result.get("provider_message_id") or "")[:255] or None,
                "provider_name": str(openclaw_result.get("provider_name") or "openclaw"),
                "recipient_kind": str(openclaw_result.get("recipient_kind") or channel)[:64] or None,
                "recipient_value": str(openclaw_result.get("recipient_value") or "")[:255] or None,
                "error_text": None,
                "retryable": False,
            }
        if strict_openclaw:
            return {
                "delivery_status": QUEUE_STATUS_FAILED,
                "provider_name": "openclaw",
                "error_text": f"OpenClaw strict mode: {str(openclaw_result.get('error') or 'delivery failed')[:430]}",
                "retryable": True,
            }
        # fallback to legacy bridge path below if strict mode is disabled.

    maton_key = _resolve_outreach_maton_key()
    if not maton_key:
        return {
            "delivery_status": QUEUE_STATUS_FAILED,
            "error_text": "MATON_OUTREACH_API_KEY is not configured",
            "provider_name": "maton",
            "retryable": False,
        }

    whatsapp_phone = normalize_phone(item.get("whatsapp_url") or item.get("phone"))
    telegram_handle = _extract_telegram_handle(item.get("telegram_url"))
    if channel == "telegram" and not telegram_handle:
        return {
            "delivery_status": QUEUE_STATUS_FAILED,
            "error_text": "Lead has no telegram handle/url",
            "provider_name": "maton",
            "retryable": False,
        }
    if channel == "whatsapp" and not whatsapp_phone:
        return {
            "delivery_status": QUEUE_STATUS_FAILED,
            "error_text": "Lead has no WhatsApp phone",
            "provider_name": "maton",
            "retryable": False,
        }

    response = send_maton_bridge_message(
        maton_key,
        message,
        target_channel=channel,
        business_id="outreach",
        business_name="LocalOS Outreach",
        telegram_handle=telegram_handle or None,
        whatsapp_phone=whatsapp_phone or None,
        metadata={
            "lead_id": item.get("lead_id"),
            "queue_id": item.get("id"),
            "lead_name": item.get("lead_name"),
            "channel": channel,
        },
    )
    if response.get("success"):
        provider_marker = (
            response.get("response_excerpt")
            or f"maton:{channel}:{item.get('id')}"
        )
        return {
            "delivery_status": QUEUE_STATUS_SENT,
            "provider_message_id": str(provider_marker)[:255],
            "provider_name": "maton",
            "recipient_kind": "telegram_handle" if channel == "telegram" else "phone",
            "recipient_value": telegram_handle if channel == "telegram" else whatsapp_phone,
            "error_text": None,
            "retryable": False,
        }
    return {
        "delivery_status": QUEUE_STATUS_FAILED,
        "provider_name": "maton",
        "error_text": str(response.get("error") or "Maton bridge delivery failed")[:500],
        "provider_message_id": None,
        "recipient_kind": "telegram_handle" if channel == "telegram" else "phone",
        "recipient_value": telegram_handle if channel == "telegram" else whatsapp_phone,
        "retryable": True,
    }


@admin_prospecting_bp.route("/api/admin/prospecting/outbound/health", methods=["GET"])
def get_outbound_health():
    """Return outbound runtime bridge health for prospecting dispatch."""
    _, error = _require_superadmin()
    if error:
        return error

    endpoint = _resolve_outreach_openclaw_endpoint()
    health_url = _resolve_outreach_openclaw_health_endpoint()
    token = _resolve_outreach_openclaw_token()
    strict_mode = _is_outreach_openclaw_strict()

    payload: dict[str, Any] = {
        "success": True,
        "strict_openclaw": strict_mode,
        "telegram_app": _telegram_app_status_payload(),
        "openclaw": {
            "configured": bool(endpoint and token),
            "endpoint": endpoint or None,
            "health_url": health_url or None,
            "token_configured": bool(token),
            "status": "not_configured",
            "http_status": None,
            "error": None,
        },
        "fallback": {
            "maton_configured": bool(_resolve_outreach_maton_key()),
            "enabled_when_strict_off": not strict_mode,
        },
    }

    if not endpoint or not token:
        return jsonify(payload)

    if not health_url:
        payload["openclaw"]["status"] = "unknown"
        payload["openclaw"]["error"] = "Health URL is not resolvable"
        return jsonify(payload)

    try:
        resp = requests.get(
            health_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=8,
        )
        payload["openclaw"]["http_status"] = resp.status_code
        if resp.status_code < 400:
            payload["openclaw"]["status"] = "ready"
        else:
            payload["openclaw"]["status"] = "degraded"
            payload["openclaw"]["error"] = f"HTTP {resp.status_code}"
    except Exception as exc:
        payload["openclaw"]["status"] = "down"
        payload["openclaw"]["error"] = str(exc)

    return jsonify(payload)


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
            RETURNING id, batch_id, lead_id, draft_id, channel, delivery_status,
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
            SELECT q.id, q.lead_id, q.delivery_status
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
        filtered = [lead for lead in normalized if _lead_matches_filters(lead, filters)]
        group_id = str(filters.get("group_id") or "").strip()
        if group_id:
            filtered = [
                lead for lead in filtered
                if any(str(group.get("id") or "") == group_id for group in (lead.get("groups") or []))
            ]
        return jsonify(_to_json_compatible({"leads": filtered, "count": len(filtered)}))
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
        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            _ensure_manual_crm_tables(conn)
        finally:
            conn.close()
        data = request.get_json(silent=True) or {}
        lead_data = data.get("lead")

        if not lead_data:
            return jsonify({"error": "Lead data is required"}), 400

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
            _record_lead_timeline_event(
                cur,
                lead_id=lead_id,
                event_type="lead_created",
                comment="Lead added to intake",
                payload={
                    "source": lead_data.get("source"),
                    "pipeline_status": lead_data.get("pipeline_status") or PIPELINE_UNPROCESSED,
                },
            )
            conn.commit()
        finally:
            conn.close()

        return jsonify({"success": True, "lead_id": lead_id})
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


@admin_prospecting_bp.route("/api/partnership/partners/bulk-process", methods=["POST"])
def partnership_bulk_process_partner_cards():
    """Run selected enrichment steps for partner cards."""
    user_data, error = _require_auth()
    if error:
        return error
    try:
        data = request.get_json(silent=True) or {}
        requested_business_id = str(data.get("business_id") or "").strip() or None
        raw_steps = data.get("steps") or ["find_yandex", "sync_lead", "parse", "audit"]
        steps = [str(step or "").strip().lower() for step in raw_steps if str(step or "").strip()]
        allowed_steps = {"find_yandex", "sync_lead", "parse", "audit"}
        steps = [step for step in steps if step in allowed_steps]
        if not steps:
            return jsonify({"error": "steps must include at least one supported step"}), 400
        partner_ids = [str(item or "").strip() for item in (data.get("partner_ids") or []) if str(item or "").strip()]
        source_company_names = [str(item or "").strip() for item in (data.get("source_company_names") or []) if str(item or "").strip()]

        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            _ensure_manual_crm_tables(conn)
            _ensure_partnership_partner_cards_table(conn)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
            where_sql = ["business_id = NULLIF(%s, '')::uuid"]
            params: list[Any] = [business_id]
            if partner_ids:
                where_sql.append("id = ANY(%s::uuid[])")
                params.append(partner_ids)
            if source_company_names:
                where_sql.append("source_company_name = ANY(%s)")
                params.append(source_company_names)
            cur.execute(
                f"""
                SELECT *
                FROM partnership_partner_cards
                WHERE {' AND '.join(where_sql)}
                ORDER BY updated_at DESC
                LIMIT 500
                """,
                tuple(params),
            )
            cards = [_row_to_dict(row) for row in cur.fetchall() or []]
        finally:
            conn.close()

        results: list[dict[str, Any]] = []
        summary = {
            "total": len(cards),
            "skipped_residential_complex": 0,
            "found": 0,
            "ambiguous": 0,
            "not_found": 0,
            "leads_synced": 0,
            "parse_tasks": 0,
            "audits_created": 0,
            "failed": 0,
        }

        for card in cards:
            card_id = str(card.get("id") or "")
            item_result: dict[str, Any] = {"partner_id": card_id, "steps": {}}
            if _is_residential_partner_card(card):
                summary["skipped_residential_complex"] += 1
                conn = get_db_connection()
                try:
                    _ensure_partnership_partner_cards_table(conn)
                    cur = conn.cursor()
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
                    conn.commit()
                finally:
                    conn.close()
                item_result["steps"]["skip"] = "residential_complex"
                results.append(item_result)
                continue

            if "find_yandex" in steps:
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
                        card["yandex_maps_url"] = selected_url
                    else:
                        status = PARTNER_MATCH_AMBIGUOUS
                        selected_confidence = top_confidence
                conn = get_db_connection()
                try:
                    _ensure_partnership_partner_cards_table(conn)
                    cur = conn.cursor()
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
                        """,
                        (selected_url, status, selected_confidence, Json(_to_json_compatible(candidates)), search_error, card.get("id")),
                    )
                    conn.commit()
                finally:
                    conn.close()
                if status == PARTNER_MATCH_FOUND:
                    summary["found"] += 1
                elif status == PARTNER_MATCH_AMBIGUOUS:
                    summary["ambiguous"] += 1
                else:
                    summary["not_found"] += 1
                item_result["steps"]["find_yandex"] = {"status": status, "error": search_error}

            if "sync_lead" in steps:
                conn = get_db_connection()
                try:
                    _ensure_partnership_columns(conn)
                    _ensure_manual_crm_tables(conn)
                    _ensure_partnership_partner_cards_table(conn)
                    cur = conn.cursor(cursor_factory=RealDictCursor)
                    refreshed = _load_partner_card(cur, partner_id=card_id, business_id=str(card.get("business_id") or ""))
                    if refreshed:
                        card = refreshed
                    lead_id, created, sync_error = _sync_partner_card_to_lead(cur, card=card, user_id=str(user_data.get("user_id") or ""))
                    if sync_error:
                        summary["failed"] += 1
                        item_result["steps"]["sync_lead"] = {"error": sync_error}
                    else:
                        summary["leads_synced"] += 1
                        item_result["steps"]["sync_lead"] = {"lead_id": lead_id, "created": created}
                    conn.commit()
                finally:
                    conn.close()

            if "parse" in steps:
                parse_result = _process_partner_card_parse(
                    partner_id=card_id,
                    business_id=str(card.get("business_id") or ""),
                    user_id=str(user_data.get("user_id") or ""),
                )
                if parse_result.get("success"):
                    summary["parse_tasks"] += 1
                    item_result["steps"]["parse"] = {
                        "task": parse_result.get("task"),
                        "parse_business_id": parse_result.get("parse_business_id"),
                    }
                else:
                    summary["failed"] += 1
                    item_result["steps"]["parse"] = {"error": parse_result.get("error")}

            if "audit" in steps:
                audit_result = _process_partner_card_audit(
                    partner_id=card_id,
                    business_id=str(card.get("business_id") or ""),
                    user_id=str(user_data.get("user_id") or ""),
                    primary_language="ru",
                )
                if audit_result.get("success"):
                    summary["audits_created"] += 1
                    item_result["steps"]["audit"] = {"public_url": audit_result.get("public_url")}
                else:
                    summary["failed"] += 1
                    item_result["steps"]["audit"] = {"error": audit_result.get("error")}

            results.append(item_result)

        return jsonify({"success": True, "summary": summary, "results": results})
    except Exception:
        err = sys.exc_info()[1]
        print(f"Error bulk processing partner cards: {err}")
        return jsonify({"error": str(err)}), 500


@admin_prospecting_bp.route("/api/partnership/leads/import-file", methods=["POST"])
def partnership_import_file():
    """User-level import of partnership candidates from CSV/JSON/JSONL content."""
    user_data, error = _require_auth()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        requested_business_id = str(data.get("business_id") or "").strip() or None
        filename = str(data.get("filename") or "").strip()
        file_format = str(data.get("format") or "").strip().lower()
        content = str(data.get("content") or "")
        default_city = str(data.get("default_city") or "").strip()
        default_category = str(data.get("default_category") or "").strip()

        if not content.strip():
            return jsonify({"error": "file content is required"}), 400

        if file_format not in {"csv", "json", "jsonl"}:
            if filename.lower().endswith(".csv"):
                file_format = "csv"
            elif filename.lower().endswith(".jsonl"):
                file_format = "jsonl"
            elif filename.lower().endswith(".json"):
                file_format = "json"
            else:
                return jsonify({"error": "Unsupported file format. Use CSV, JSON or JSONL"}), 400

        rows = _parse_partnership_file_content(file_format, content)
        if not rows:
            return jsonify({"error": "No records found in file"}), 400

        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403

            imported_ids: list[str] = []
            skipped_count = 0
            errors: list[dict[str, Any]] = []

            for idx, raw_row in enumerate(rows, start=1):
                if not isinstance(raw_row, dict):
                    skipped_count += 1
                    if len(errors) < 100:
                        errors.append({"row": idx, "error": "row is not an object"})
                    continue

                normalized, row_error = _normalize_partnership_file_row(
                    raw_row,
                    default_city=default_city or None,
                    default_category=default_category or None,
                )
                if row_error or not normalized:
                    skipped_count += 1
                    if len(errors) < 100:
                        errors.append({"row": idx, "error": row_error or "invalid row"})
                    continue

                lead_id, created = _insert_partnership_lead_if_new(
                    cur,
                    business_id=business_id,
                    created_by=user_data["user_id"],
                    source_url=normalized["source_url"],
                    name=normalized.get("name"),
                    address=normalized.get("address"),
                    city=normalized.get("city"),
                    category=normalized.get("category"),
                    source="file_import",
                    phone=normalized.get("phone"),
                    email=normalized.get("email"),
                    website=normalized.get("website"),
                    telegram_url=normalized.get("telegram_url"),
                    whatsapp_url=normalized.get("whatsapp_url"),
                    rating=normalized.get("rating"),
                    reviews_count=normalized.get("reviews_count"),
                    source_kind="file_import",
                    source_provider="localos_file_import",
                    external_source_id=_extract_yandex_org_id_from_url(normalized["source_url"]) or None,
                    search_payload={
                        "import_format": file_format,
                        "filename": filename or None,
                        **(normalized.get("search_payload") if isinstance(normalized.get("search_payload"), dict) else {}),
                    },
                )
                if not created:
                    skipped_count += 1
                    continue
                if lead_id:
                    imported_ids.append(lead_id)

            conn.commit()
        finally:
            conn.close()

        return jsonify(
            {
                "success": True,
                "filename": filename,
                "format": file_format,
                "rows_total": len(rows),
                "imported_count": len(imported_ids),
                "skipped_count": skipped_count,
                "lead_ids": imported_ids,
                "errors": errors,
            }
        )
    except Exception as e:
        print(f"Error importing partnership file: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/partnership/geo-search", methods=["POST"])
def partnership_geo_search():
    """Unified LocalOS geo-search router for partnership leads."""
    user_data, error = _require_auth()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        requested_business_id = str(data.get("business_id") or "").strip() or None
        city = str(data.get("city") or "").strip()
        category = str(data.get("category") or "").strip()
        query = str(data.get("query") or "").strip()
        provider = str(data.get("provider") or "google").strip().lower()
        items_raw = data.get("items")
        has_seed_items = isinstance(items_raw, list) and len(items_raw) > 0
        radius_km = int(data.get("radius_km") or 5)
        limit = int(data.get("limit") or 25)
        radius_km = max(1, min(radius_km, 100))
        limit = max(1, limit)
        if not has_seed_items and not city and not query:
            return jsonify({"error": "city or query is required"}), 400
        if provider not in {"google", "yandex", "both"}:
            return jsonify({"error": "provider must be one of: google, yandex, both"}), 400

        yandex_query = " ".join(part for part in [category, query] if part).strip() or query or category

        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
            provider_status = {
                "requested": provider,
                "google": {"enabled": provider in {"google", "both"}, "executed": False, "items_count": 0},
                "yandex": {"enabled": provider in {"yandex", "both"}, "executed": False, "items_count": 0},
            }
            warnings: list[str] = []
            meta_blob = {}
            candidates: list[dict[str, Any]] = []
            openclaw_enabled = _is_partnership_openclaw_enabled()

            if provider in {"google", "both"}:
                if not openclaw_enabled:
                    warnings.append("Google geo-search сейчас недоступен: интеграция OpenClaw не настроена на стороне LocalOS.")
                else:
                    cap_payload = {
                        "query": query,
                        "city": city,
                        "category": category,
                        "radius_km": radius_km,
                        "limit": limit,
                        "intent": "partnership_outreach",
                        "business_id": business_id,
                    }
                    if not has_seed_items:
                        cap_payload["provider"] = "google"
                    else:
                        normalized_items = []
                        for item in items_raw:
                            if not isinstance(item, dict):
                                continue
                            normalized_items.append(
                                {
                                    "name": item.get("name"),
                                    "source_url": item.get("source_url") or item.get("url"),
                                    "city": item.get("city"),
                                    "category": item.get("category"),
                                    "address": item.get("address"),
                                    "phone": item.get("phone"),
                                    "email": item.get("email"),
                                    "website": item.get("website"),
                                    "telegram_url": item.get("telegram_url"),
                                    "whatsapp_url": item.get("whatsapp_url"),
                                    "rating": item.get("rating"),
                                    "reviews_count": item.get("reviews_count"),
                                    "source_kind": item.get("source_kind"),
                                    "source_provider": item.get("source_provider"),
                                    "lat": item.get("lat"),
                                    "lon": item.get("lon"),
                                }
                            )
                        cap_payload["items"] = normalized_items
                    openclaw_result = _call_partnership_openclaw_capability(
                        "partners.search_geo",
                        tenant_id=business_id,
                        payload=cap_payload,
                        timeout_sec=60,
                    )
                    if not openclaw_result.get("success"):
                        return jsonify({"error": str(openclaw_result.get("error") or "OpenClaw geo-search failed")}), 502

                    data_blob = openclaw_result.get("data") or {}
                    result_blob = data_blob.get("result") if isinstance(data_blob, dict) else {}
                    meta_blob = result_blob.get("meta") if isinstance(result_blob, dict) else {}
                    provider_candidates = (
                        (result_blob.get("items") if isinstance(result_blob, dict) else None)
                        or (data_blob.get("items") if isinstance(data_blob, dict) else None)
                        or []
                    )
                    if not isinstance(provider_candidates, list):
                        provider_candidates = []
                    candidates.extend([item for item in provider_candidates if isinstance(item, dict)])
                    provider_status["google"]["executed"] = True
                    provider_status["google"]["items_count"] = len(provider_candidates)
                    if has_seed_items:
                        provider_status["google"]["items_count"] = len(provider_candidates)
                    elif isinstance(meta_blob, dict) and str(meta_blob.get("provider") or "").strip().lower() == "none":
                        warnings.append("Google geo-provider в OpenClaw сейчас работает в режиме provider=none, поэтому результат может быть пустым.")

            if provider in {"yandex", "both"}:
                yandex_service = ProspectingService(source="apify_yandex")
                if not yandex_service.client:
                    if provider == "yandex":
                        return jsonify({"error": "APIFY_TOKEN is not configured"}), 500
                    warnings.append("Yandex geo-search недоступен: APIFY_TOKEN не настроен на стороне LocalOS.")
                elif not yandex_query:
                    warnings.append("Для поиска по Яндекс.Картам укажите категорию или поисковый запрос.")
                else:
                    yandex_results = yandex_service.run_search(yandex_query, city, limit=limit, timeout_sec=180)
                    yandex_candidates = yandex_results.get("items") or []
                    if not isinstance(yandex_candidates, list):
                        yandex_candidates = []
                    candidates.extend([item for item in yandex_candidates if isinstance(item, dict)])
                    provider_status["yandex"]["executed"] = True
                    provider_status["yandex"]["items_count"] = len(yandex_candidates)

            if not isinstance(candidates, list):
                candidates = []

            imported_ids: list[str] = []
            merged_count = 0
            skipped = 0
            for item in candidates:
                if not isinstance(item, dict):
                    continue
                source_url = str(item.get("source_url") or item.get("url") or item.get("maps_url") or "").strip()
                lead_name = str(item.get("name") or item.get("title") or "Новый партнёр").strip()
                lead_city = str(item.get("city") or city or "").strip() or None
                lead_category = str(item.get("category") or category or "").strip() or None
                lead_address = str(item.get("address") or item.get("location") or "").strip() or None
                phone = str(item.get("phone") or "").strip() or None
                email = str(item.get("email") or "").strip() or None
                website = str(item.get("website") or item.get("website_url") or "").strip() or None
                telegram_url = str(item.get("telegram_url") or "").strip() or None
                whatsapp_url = str(item.get("whatsapp_url") or "").strip() or None
                external_place_id = str(item.get("place_id") or item.get("external_place_id") or item.get("google_place_id") or "").strip() or None
                external_source_id = str(item.get("source_id") or item.get("external_source_id") or external_place_id or "").strip() or None
                try:
                    lat = float(item.get("lat")) if item.get("lat") is not None else None
                except Exception:
                    lat = None
                try:
                    lon = float(item.get("lon")) if item.get("lon") is not None else None
                except Exception:
                    lon = None
                try:
                    rating = float(item.get("rating")) if item.get("rating") is not None else None
                except Exception:
                    rating = None
                try:
                    reviews_count = int(item.get("reviews_count")) if item.get("reviews_count") is not None else None
                except Exception:
                    reviews_count = None
                lead_id, created = _insert_partnership_lead_if_new(
                    cur,
                    business_id=business_id,
                    created_by=user_data["user_id"],
                    source_url=source_url,
                    name=lead_name,
                    address=lead_address,
                    city=lead_city,
                    category=lead_category,
                    source="openclaw_seed_geo" if has_seed_items else ("openclaw_google_geo" if provider in {"google", "both"} else "manual_geo"),
                    phone=phone,
                    email=email,
                    website=website,
                    telegram_url=telegram_url,
                    whatsapp_url=whatsapp_url,
                    rating=rating,
                    reviews_count=reviews_count,
                    source_kind=str(item.get("source_kind") or ("geo_search_seed" if has_seed_items else "geo_search")).strip() or ("geo_search_seed" if has_seed_items else "geo_search"),
                    source_provider=str(item.get("source_provider") or item.get("provider") or ("openclaw_seed" if has_seed_items else "openclaw_google")).strip() or ("openclaw_seed" if has_seed_items else "openclaw_google"),
                    external_place_id=external_place_id,
                    external_source_id=external_source_id,
                    lat=lat,
                    lon=lon,
                    search_payload={
                        "provider": str(meta_blob.get("provider") if isinstance(meta_blob, dict) else "") or ("seed_items" if has_seed_items else provider),
                        "city": city,
                        "category": category,
                        "query": query,
                        "radius_km": radius_km,
                        "limit": limit,
                        "candidate_name": lead_name,
                        "candidate_address": lead_address,
                        "items_mode": has_seed_items,
                    },
                )
                if created:
                    if lead_id:
                        imported_ids.append(lead_id)
                else:
                    if lead_id:
                        merged_count += 1
                    else:
                        skipped += 1
            conn.commit()
        finally:
            conn.close()

        return jsonify(
            {
                "success": True,
                "imported_count": len(imported_ids),
                "merged_count": merged_count,
                "skipped_count": skipped,
                "lead_ids": imported_ids,
                "source_total": len(candidates),
                "openclaw_meta": meta_blob if isinstance(meta_blob, dict) else {},
                "provider_status": provider_status,
                "warnings": warnings,
                "warning": " ".join(warnings).strip() or None,
            }
        )
    except Exception as e:
        print(f"Error partnership geo search: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/partnership/leads", methods=["GET"])
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
            _ensure_sales_room_tables(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403

            where_sql = [
                "business_id = %s",
                "COALESCE(intent, 'client_outreach') = 'partnership_outreach'",
            ]
            params: list[Any] = [business_id]
            if stage_filter:
                where_sql.append("COALESCE(partnership_stage, 'imported') = %s")
                params.append(stage_filter)
            if pipeline_status_filter:
                if pipeline_status_filter == "in_progress":
                    where_sql.append(
                        """(
                            COALESCE(pipeline_status, 'unprocessed') IN ('in_progress', 'qualified')
                            OR (
                                COALESCE(pipeline_status, '') = ''
                                AND COALESCE(partnership_stage, 'imported') IN (
                                    'audited', 'matched', 'proposal_draft_ready', 'selected_for_outreach',
                                    'channel_selected', 'proposal_approved', 'queued_for_send'
                                )
                            )
                        )"""
                    )
                elif pipeline_status_filter == "postponed":
                    where_sql.append(
                        "(COALESCE(pipeline_status, 'unprocessed') IN ('postponed', 'deferred') OR COALESCE(partnership_stage, 'imported') = 'deferred')"
                    )
                elif pipeline_status_filter == "not_relevant":
                    where_sql.append(
                        "(COALESCE(pipeline_status, 'unprocessed') IN ('not_relevant', 'disqualified') OR COALESCE(partnership_stage, 'imported') IN ('rejected', 'shortlist_rejected'))"
                    )
                elif pipeline_status_filter == "contacted":
                    where_sql.append(
                        """(
                            COALESCE(pipeline_status, 'unprocessed') IN ('contacted', 'waiting_reply', 'sent', 'delivered')
                            OR COALESCE(partnership_stage, 'imported') IN ('approved_for_send', 'sent')
                        )"""
                    )
                elif pipeline_status_filter == "replied":
                    where_sql.append("COALESCE(pipeline_status, 'unprocessed') IN ('replied', 'responded')")
                else:
                    where_sql.append("COALESCE(pipeline_status, 'unprocessed') = %s")
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
                       prospectingleads.reviews_count, prospectingleads.status, prospectingleads.selected_channel,
                       prospectingleads.intent, prospectingleads.partnership_stage, prospectingleads.pilot_cohort,
                       prospectingleads.pipeline_status, prospectingleads.disqualification_reason,
                       prospectingleads.disqualification_comment, prospectingleads.postponed_comment,
                       prospectingleads.next_action_at, prospectingleads.last_contact_at,
                       prospectingleads.last_contact_channel, prospectingleads.last_contact_comment,
                       prospectingleads.parse_business_id, prospectingleads.updated_at,
                       prospectingleads.created_at,
                       pq_last.id AS parse_task_id,
                       pq_last.status AS parse_status,
                       COALESCE(pq_last.updated_at, pq_last.created_at) AS parse_updated_at,
                       pq_last.retry_after AS parse_retry_after,
                       pq_last.error_message AS parse_error,
                       sr_last.status AS sales_room_status,
                       sr_last.data_mode AS sales_room_data_mode,
                       sr_last.slug AS sales_room_slug,
                       sr_last.updated_at AS sales_room_updated_at
                FROM prospectingleads
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
                    ORDER BY sr.updated_at DESC
                    LIMIT 1
                ) sr_last ON TRUE
                WHERE {' AND '.join(where_sql)}
                ORDER BY prospectingleads.updated_at DESC NULLS LAST, prospectingleads.created_at DESC
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
        return jsonify({"success": True, "count": len(items), "items": items})
    except Exception as e:
        print(f"Error listing partnership leads: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/partnership/health", methods=["GET"])
def partnership_health():
    """Health snapshot for partnership flow by business."""
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

            cur.execute(
                """
                SELECT COUNT(*)::INT
                FROM prospectingleads
                WHERE business_id = %s
                  AND COALESCE(intent, 'client_outreach') = 'partnership_outreach'
                """,
                (business_id,),
            )
            leads_total = int((cur.fetchone() or [0])[0] or 0)

            cur.execute(
                """
                SELECT COUNT(*)::INT
                FROM outreachmessagedrafts d
                JOIN prospectingleads l ON l.id = d.lead_id
                WHERE l.business_id = %s
                  AND COALESCE(l.intent, 'client_outreach') = 'partnership_outreach'
                """,
                (business_id,),
            )
            drafts_total = int((cur.fetchone() or [0])[0] or 0)

            cur.execute(
                """
                SELECT COUNT(*)::INT
                FROM outreachsendbatches b
                WHERE b.business_id = %s
                """,
                (business_id,),
            )
            batches_total = int((cur.fetchone() or [0])[0] or 0)

            reactions_total = 0
            if schema_flags["has_reactions"]:
                cur.execute(
                    """
                    SELECT COUNT(*)::INT
                    FROM outreachmessagereactions r
                    JOIN outreachsendqueue q ON q.id = r.queue_id
                    JOIN prospectingleads l ON l.id = q.lead_id
                    WHERE l.business_id = %s
                      AND COALESCE(l.intent, 'client_outreach') = 'partnership_outreach'
                    """,
                    (business_id,),
                )
                reactions_total = int((cur.fetchone() or [0])[0] or 0)
        finally:
            conn.close()

        openclaw_enabled = _is_partnership_openclaw_enabled()
        caps_endpoint = _resolve_partnership_openclaw_caps_endpoint()
        token_present = bool(_resolve_partnership_openclaw_token())
        return jsonify(
            {
                "success": True,
                "business_id": business_id,
                "openclaw": {
                    "enabled": openclaw_enabled,
                    "caps_endpoint_configured": bool(caps_endpoint),
                    "token_configured": token_present,
                },
                "counts": {
                    "leads_total": leads_total,
                    "drafts_total": drafts_total,
                    "batches_total": batches_total,
                    "reactions_total": reactions_total,
                },
            }
        )
    except Exception as e:
        print(f"Error partnership health: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/partnership/export", methods=["GET"])
def partnership_export():
    """Export partnership flow snapshot for support/ops."""
    user_data, error = _require_auth()
    if error:
        return error
    try:
        requested_business_id = str(request.args.get("business_id") or "").strip() or None
        export_format = str(request.args.get("format") or "json").strip().lower()
        limit = max(1, min(int(request.args.get("limit") or 30), 200))

        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
            schema_flags = _get_partnership_schema_flags(cur)

            cur.execute(
                """
                SELECT id, name, city, category, source_url, status, selected_channel,
                       partnership_stage, updated_at
                FROM prospectingleads
                WHERE business_id = %s
                  AND COALESCE(intent, 'client_outreach') = 'partnership_outreach'
                ORDER BY updated_at DESC NULLS LAST, created_at DESC
                LIMIT %s
                """,
                (business_id, limit),
            )
            leads = [dict(r) if hasattr(r, "keys") else {} for r in cur.fetchall()]

            cur.execute(
                """
                SELECT d.id, d.lead_id, d.channel, d.status, d.updated_at, l.name AS lead_name
                FROM outreachmessagedrafts d
                JOIN prospectingleads l ON l.id = d.lead_id
                WHERE l.business_id = %s
                  AND COALESCE(l.intent, 'client_outreach') = 'partnership_outreach'
                ORDER BY d.updated_at DESC NULLS LAST, d.created_at DESC
                LIMIT %s
                """,
                (business_id, limit),
            )
            drafts = [dict(r) if hasattr(r, "keys") else {} for r in cur.fetchall()]

            cur.execute(
                """
                SELECT b.id, b.status, b.batch_date, b.created_at, b.updated_at
                FROM outreachsendbatches b
                WHERE b.business_id = %s
                ORDER BY b.updated_at DESC NULLS LAST, b.created_at DESC
                LIMIT %s
                """,
                (business_id, limit),
            )
            batches = [dict(r) if hasattr(r, "keys") else {} for r in cur.fetchall()]

            reactions: list[dict[str, Any]] = []
            if schema_flags["has_reactions"]:
                cur.execute(
                    """
                    SELECT r.id, r.queue_id, r.classified_outcome, r.human_confirmed_outcome,
                           r.created_at, l.name AS lead_name
                    FROM outreachmessagereactions r
                    JOIN outreachsendqueue q ON q.id = r.queue_id
                    JOIN prospectingleads l ON l.id = q.lead_id
                    WHERE l.business_id = %s
                      AND COALESCE(l.intent, 'client_outreach') = 'partnership_outreach'
                    ORDER BY r.created_at DESC NULLS LAST
                    LIMIT %s
                    """,
                    (business_id, limit),
                )
                reactions = [dict(r) if hasattr(r, "keys") else {} for r in cur.fetchall()]
        finally:
            conn.close()

        snapshot = {
            "business_id": business_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "limit": limit,
            "counts": {
                "leads": len(leads),
                "drafts": len(drafts),
                "batches": len(batches),
                "reactions": len(reactions),
            },
            "leads": leads,
            "drafts": drafts,
            "batches": batches,
            "reactions": reactions,
        }

        if export_format == "markdown":
            lines = [
                "# Partnership Export",
                "",
                f"- business_id: `{business_id}`",
                f"- generated_at: `{snapshot['generated_at']}`",
                f"- limit: `{limit}`",
                "",
                "## Counts",
                f"- leads: {snapshot['counts']['leads']}",
                f"- drafts: {snapshot['counts']['drafts']}",
                f"- batches: {snapshot['counts']['batches']}",
                f"- reactions: {snapshot['counts']['reactions']}",
                "",
                "## Recent Leads",
            ]
            for lead in leads[:10]:
                lines.append(
                    f"- `{lead.get('id')}` | {lead.get('name') or '-'} | stage={lead.get('partnership_stage') or '-'} | status={lead.get('status') or '-'}"
                )
            lines.extend(["", "## Recent Drafts"])
            for draft in drafts[:10]:
                lines.append(
                    f"- `{draft.get('id')}` | lead={draft.get('lead_name') or draft.get('lead_id') or '-'} | status={draft.get('status') or '-'} | channel={draft.get('channel') or '-'}"
                )
            lines.extend(["", "## Recent Batches"])
            for batch in batches[:10]:
                lines.append(
                    f"- `{batch.get('id')}` | status={batch.get('status') or '-'} | batch_date={batch.get('batch_date') or '-'}"
                )
            lines.extend(["", "## Recent Reactions"])
            for reaction in reactions[:10]:
                lines.append(
                    f"- `{reaction.get('id')}` | lead={reaction.get('lead_name') or '-'} | classified={reaction.get('classified_outcome') or '-'} | confirmed={reaction.get('human_confirmed_outcome') or '-'}"
                )
            return jsonify({"success": True, "format": "markdown", "markdown_report": "\n".join(lines), **snapshot})

        return jsonify({"success": True, "format": "json", **snapshot})
    except Exception as e:
        print(f"Error partnership export: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/partnership/funnel", methods=["GET"])
def partnership_funnel():
    """Partnership funnel metrics aligned with the client-search operator pipeline."""
    user_data, error = _require_auth()
    if error:
        return error
    try:
        requested_business_id = str(request.args.get("business_id") or "").strip() or None
        window_days = max(1, min(int(request.args.get("window_days") or 30), 365))

        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403

            cur.execute(
                """
                WITH leads_scope AS (
                    SELECT
                        l.id,
                        l.partnership_stage,
                        CASE
                            WHEN COALESCE(l.pipeline_status, '') = 'qualified' THEN 'in_progress'
                            WHEN COALESCE(l.pipeline_status, '') = 'disqualified' THEN 'not_relevant'
                            WHEN COALESCE(l.pipeline_status, '') = 'deferred' THEN 'postponed'
                            WHEN COALESCE(l.pipeline_status, '') IN ('sent', 'delivered') THEN 'contacted'
                            WHEN COALESCE(l.pipeline_status, '') = 'responded' THEN 'replied'
                            WHEN COALESCE(l.pipeline_status, '') <> '' THEN l.pipeline_status
                            WHEN COALESCE(l.partnership_stage, 'imported') = 'deferred' THEN 'postponed'
                            WHEN COALESCE(l.partnership_stage, 'imported') IN ('rejected', 'shortlist_rejected') THEN 'not_relevant'
                            WHEN COALESCE(l.partnership_stage, 'imported') IN ('approved_for_send', 'sent') THEN 'contacted'
                            WHEN COALESCE(l.partnership_stage, 'imported') IN (
                                'audited', 'matched', 'proposal_draft_ready', 'selected_for_outreach',
                                'channel_selected', 'proposal_approved', 'queued_for_send'
                            ) THEN 'in_progress'
                            ELSE 'unprocessed'
                        END AS normalized_pipeline_status,
                        l.updated_at,
                        l.created_at
                    FROM prospectingleads l
                    WHERE l.business_id = %s
                      AND COALESCE(l.intent, 'client_outreach') = 'partnership_outreach'
                      AND COALESCE(l.updated_at, l.created_at) >= NOW() - (%s || ' days')::INTERVAL
                )
                SELECT
                    COUNT(*)::INT AS total_count,
                    COUNT(*) FILTER (WHERE normalized_pipeline_status = 'unprocessed')::INT AS unprocessed_count,
                    COUNT(*) FILTER (WHERE normalized_pipeline_status = 'in_progress')::INT AS in_progress_count,
                    COUNT(*) FILTER (WHERE normalized_pipeline_status IN ('contacted', 'waiting_reply'))::INT AS contacted_count,
                    COUNT(*) FILTER (WHERE normalized_pipeline_status = 'second_message_sent')::INT AS second_message_sent_count,
                    COUNT(*) FILTER (WHERE normalized_pipeline_status = 'replied')::INT AS replied_count,
                    COUNT(*) FILTER (WHERE normalized_pipeline_status = 'converted')::INT AS converted_count,
                    COUNT(*) FILTER (WHERE normalized_pipeline_status = 'postponed')::INT AS postponed_count,
                    COUNT(*) FILTER (WHERE normalized_pipeline_status IN ('not_relevant', 'closed_lost'))::INT AS not_relevant_count
                FROM leads_scope
                """,
                (business_id, window_days),
            )
            row = cur.fetchone()
            if row and hasattr(row, "keys"):
                total_count = int(row.get("total_count") or 0)
                unprocessed_count = int(row.get("unprocessed_count") or 0)
                in_progress_count = int(row.get("in_progress_count") or 0)
                contacted_count = int(row.get("contacted_count") or 0)
                second_message_sent_count = int(row.get("second_message_sent_count") or 0)
                replied_count = int(row.get("replied_count") or 0)
                converted_count = int(row.get("converted_count") or 0)
                postponed_count = int(row.get("postponed_count") or 0)
                not_relevant_count = int(row.get("not_relevant_count") or 0)
            else:
                values = list(row or [0, 0, 0, 0, 0, 0, 0, 0, 0])
                total_count = int(values[0] or 0)
                unprocessed_count = int(values[1] or 0)
                in_progress_count = int(values[2] or 0)
                contacted_count = int(values[3] or 0)
                second_message_sent_count = int(values[4] or 0)
                replied_count = int(values[5] or 0)
                converted_count = int(values[6] or 0)
                postponed_count = int(values[7] or 0)
                not_relevant_count = int(values[8] or 0)
        finally:
            conn.close()

        def _pct(numerator: int, denominator: int) -> float:
            if denominator <= 0:
                return 0.0
            return round((numerator / denominator) * 100.0, 2)

        stages = [
            {"key": "unprocessed", "label": "Необработан", "count": unprocessed_count},
            {"key": "in_progress", "label": "В работе", "count": in_progress_count, "conversion_from_prev_pct": _pct(in_progress_count, total_count)},
            {"key": "contacted", "label": "Отправлено", "count": contacted_count, "conversion_from_prev_pct": _pct(contacted_count, in_progress_count)},
            {"key": "second_message_sent", "label": "Второе сообщение", "count": second_message_sent_count, "conversion_from_prev_pct": _pct(second_message_sent_count, contacted_count)},
            {"key": "replied", "label": "Ответил", "count": replied_count, "conversion_from_prev_pct": _pct(replied_count, contacted_count + second_message_sent_count)},
            {"key": "converted", "label": "Конвертирован", "count": converted_count, "conversion_from_prev_pct": _pct(converted_count, replied_count)},
            {"key": "postponed", "label": "Отложен", "count": postponed_count},
            {"key": "not_relevant", "label": "Неактуален", "count": not_relevant_count},
        ]

        return jsonify(
            {
                "success": True,
                "business_id": business_id,
                "window_days": window_days,
                "funnel": stages,
                "summary": {
                    "work_to_contact_pct": _pct(contacted_count, in_progress_count),
                    "reply_to_conversion_pct": _pct(converted_count, replied_count),
                    "total_count": total_count,
                    "contacted_count": contacted_count,
                    "converted_count": converted_count,
                },
            }
        )
    except Exception as e:
        print(f"Error partnership funnel: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/partnership/source-quality-summary", methods=["GET"])
def partnership_source_quality_summary():
    """Quality of partnership lead sources across the operator pipeline."""
    user_data, error = _require_auth()
    if error:
        return error
    try:
        requested_business_id = str(request.args.get("business_id") or "").strip() or None
        window_days = max(1, min(int(request.args.get("window_days") or 30), 365))

        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
            schema_flags = _get_partnership_schema_flags(cur)

            positive_leads_cte = """
                positive_leads AS (
                    SELECT NULL::text AS lead_id WHERE FALSE
                )
            """
            if schema_flags["has_reaction_outcomes"]:
                positive_leads_cte = """
                positive_leads AS (
                    SELECT DISTINCT q.lead_id::text AS lead_id
                    FROM outreachmessagereactions r
                    JOIN outreachsendqueue q ON q.id = r.queue_id
                    JOIN leads_scope ls ON ls.id = q.lead_id
                    WHERE COALESCE(r.human_confirmed_outcome, r.classified_outcome, '') = 'positive'
                )
                """

            cur.execute(
                f"""
                WITH leads_scope AS (
                    SELECT
                        l.id,
                        COALESCE(l.source_kind, 'unknown') AS source_kind,
                        COALESCE(l.source_provider, 'unknown') AS source_provider,
                        COALESCE(l.partnership_stage, 'imported') AS partnership_stage
                    FROM prospectingleads l
                    WHERE l.business_id = %s
                      AND COALESCE(l.intent, 'client_outreach') = 'partnership_outreach'
                      AND COALESCE(l.updated_at, l.created_at) >= NOW() - (%s || ' days')::INTERVAL
                ),
                draft_leads AS (
                    SELECT DISTINCT d.lead_id
                    FROM outreachmessagedrafts d
                    JOIN leads_scope ls ON ls.id = d.lead_id
                ),
                sent_leads AS (
                    SELECT DISTINCT q.lead_id
                    FROM outreachsendqueue q
                    JOIN leads_scope ls ON ls.id = q.lead_id
                    WHERE COALESCE(q.delivery_status, '') IN ('sent', 'delivered')
                ),
                {positive_leads_cte}
                SELECT
                    ls.source_kind,
                    ls.source_provider,
                    COUNT(*)::INT AS leads_total,
                    COUNT(*) FILTER (
                        WHERE ls.partnership_stage IN ('audited','matched','proposal_draft_ready','approved_for_send','sent')
                    )::INT AS audited_count,
                    COUNT(*) FILTER (
                        WHERE ls.partnership_stage IN ('matched','proposal_draft_ready','approved_for_send','sent')
                    )::INT AS matched_count,
                    COUNT(DISTINCT dl.lead_id)::INT AS draft_count,
                    COUNT(DISTINCT sl.lead_id)::INT AS sent_count,
                    COUNT(DISTINCT pl.lead_id)::INT AS positive_count
                FROM leads_scope ls
                LEFT JOIN draft_leads dl ON dl.lead_id = ls.id
                LEFT JOIN sent_leads sl ON sl.lead_id = ls.id
                LEFT JOIN positive_leads pl ON pl.lead_id = ls.id
                GROUP BY ls.source_kind, ls.source_provider
                ORDER BY COUNT(*) DESC, ls.source_kind ASC, ls.source_provider ASC
                """,
                (business_id, window_days),
            )
            rows = [dict(r) if hasattr(r, "keys") else {} for r in (cur.fetchall() or [])]
        finally:
            conn.close()

        def _pct(numerator: int, denominator: int) -> float:
            if denominator <= 0:
                return 0.0
            return round((numerator / denominator) * 100.0, 2)

        items: list[dict[str, Any]] = []
        for row in rows:
            leads_total = int(row.get("leads_total") or 0)
            audited_count = int(row.get("audited_count") or 0)
            matched_count = int(row.get("matched_count") or 0)
            draft_count = int(row.get("draft_count") or 0)
            sent_count = int(row.get("sent_count") or 0)
            positive_count = int(row.get("positive_count") or 0)
            items.append(
                {
                    "source_kind": row.get("source_kind") or "unknown",
                    "source_provider": row.get("source_provider") or "unknown",
                    "leads_total": leads_total,
                    "audited_count": audited_count,
                    "matched_count": matched_count,
                    "draft_count": draft_count,
                    "sent_count": sent_count,
                    "positive_count": positive_count,
                    "audit_rate_pct": _pct(audited_count, leads_total),
                    "match_rate_pct": _pct(matched_count, leads_total),
                    "draft_rate_pct": _pct(draft_count, leads_total),
                    "sent_rate_pct": _pct(sent_count, leads_total),
                    "positive_rate_pct": _pct(positive_count, sent_count),
                    "lead_to_positive_pct": _pct(positive_count, leads_total),
                }
            )

        return jsonify(
            {
                "success": True,
                "business_id": business_id,
                "window_days": window_days,
                "items": items,
            }
        )
    except Exception as e:
        print(f"Error partnership source quality summary: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/partnership/blockers-summary", methods=["GET"])
def partnership_blockers_summary():
    """Operational blockers that slow partnership conversion."""
    user_data, error = _require_auth()
    if error:
        return error
    try:
        requested_business_id = str(request.args.get("business_id") or "").strip() or None
        window_days = max(1, min(int(request.args.get("window_days") or 30), 365))

        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
            schema_flags = _get_partnership_schema_flags(cur)
            parse_leads_cte = "SELECT l.id, ''::text AS parse_status"
            if schema_flags["has_parse_lookup"]:
                parse_leads_cte = f"""
                    SELECT
                        l.id,
                        {_partnership_parse_status_select_sql("l")} AS parse_status
                """
            reaction_lookup_sql = "SELECT ''::text AS outcome"
            if schema_flags["has_reaction_outcomes"]:
                reaction_lookup_sql = """
                    SELECT COALESCE(NULLIF(r.human_confirmed_outcome, ''), NULLIF(r.classified_outcome, ''), '') AS outcome
                    FROM outreachmessagereactions r
                    WHERE r.queue_id = q.id
                    ORDER BY COALESCE(r.updated_at, r.created_at) DESC
                    LIMIT 1
                """

            cur.execute(
                f"""
                WITH leads_scope AS (
                    {parse_leads_cte}
                    FROM prospectingleads l
                    WHERE l.business_id = %s
                      AND COALESCE(l.intent, 'client_outreach') = 'partnership_outreach'
                      AND COALESCE(l.updated_at, l.created_at) >= NOW() - (%s || ' days')::INTERVAL
                )
                SELECT
                    (SELECT COUNT(*)::INT
                     FROM leads_scope ls
                     WHERE COALESCE(ls.parse_status, '') IN ('pending', 'processing')) AS parse_in_progress_count,
                    (SELECT COUNT(*)::INT
                     FROM leads_scope ls
                     WHERE COALESCE(ls.parse_status, '') = 'captcha') AS captcha_required_count,
                    (SELECT COUNT(*)::INT
                     FROM leads_scope ls
                     WHERE COALESCE(ls.parse_status, '') = 'error') AS parse_error_count,
                    (SELECT COUNT(*)::INT
                     FROM outreachmessagedrafts d
                     JOIN leads_scope ls ON ls.id = d.lead_id
                     WHERE COALESCE(d.status, '') = %s) AS drafts_waiting_approval_count,
                    (SELECT COUNT(*)::INT
                     FROM outreachsendqueue q
                     JOIN leads_scope ls ON ls.id = q.lead_id
                     WHERE COALESCE(q.delivery_status, '') IN ('queued', 'sending', 'retry')) AS queue_waiting_delivery_count,
                    (SELECT COUNT(*)::INT
                     FROM outreachsendqueue q
                     JOIN leads_scope ls ON ls.id = q.lead_id
                     LEFT JOIN LATERAL (
                         {reaction_lookup_sql}
                     ) rx ON TRUE
                     WHERE COALESCE(q.delivery_status, '') IN ('sent', 'delivered')
                       AND COALESCE(rx.outcome, '') = '') AS sent_without_outcome_count
                """,
                (business_id, window_days, DRAFT_GENERATED),
            )
            row = cur.fetchone()
        finally:
            conn.close()

        if row and hasattr(row, "keys"):
            payload = {
                "parse_in_progress_count": int(row.get("parse_in_progress_count") or 0),
                "captcha_required_count": int(row.get("captcha_required_count") or 0),
                "parse_error_count": int(row.get("parse_error_count") or 0),
                "drafts_waiting_approval_count": int(row.get("drafts_waiting_approval_count") or 0),
                "queue_waiting_delivery_count": int(row.get("queue_waiting_delivery_count") or 0),
                "sent_without_outcome_count": int(row.get("sent_without_outcome_count") or 0),
            }
        else:
            values = list(row or [0, 0, 0, 0, 0, 0])
            payload = {
                "parse_in_progress_count": int(values[0] or 0),
                "captcha_required_count": int(values[1] or 0),
                "parse_error_count": int(values[2] or 0),
                "drafts_waiting_approval_count": int(values[3] or 0),
                "queue_waiting_delivery_count": int(values[4] or 0),
                "sent_without_outcome_count": int(values[5] or 0),
            }

        blockers = [
            {
                "key": "parse_in_progress",
                "label": "Парсинг ещё идёт",
                "count": payload["parse_in_progress_count"],
                "severity": "info",
                "hint": "Лиды ещё не дошли до аудита и матчинга.",
            },
            {
                "key": "captcha_required",
                "label": "Нужна CAPTCHA",
                "count": payload["captcha_required_count"],
                "severity": "warning",
                "hint": "Парсинг остановился и ждёт human-in-the-loop.",
            },
            {
                "key": "parse_error",
                "label": "Ошибки парсинга",
                "count": payload["parse_error_count"],
                "severity": "danger",
                "hint": "Эти лиды не продвинутся дальше, пока ошибка не обработана.",
            },
            {
                "key": "drafts_waiting_approval",
                "label": "Черновики ждут утверждения",
                "count": payload["drafts_waiting_approval_count"],
                "severity": "warning",
                "hint": "Офферы уже готовы, но не переведены в очередь отправки.",
            },
            {
                "key": "queue_waiting_delivery",
                "label": "Очередь ждёт доставки",
                "count": payload["queue_waiting_delivery_count"],
                "severity": "warning",
                "hint": "Batch создан, но доставка ещё не закрыта по статусам.",
            },
            {
                "key": "sent_without_outcome",
                "label": "Нет outcome после отправки",
                "count": payload["sent_without_outcome_count"],
                "severity": "info",
                "hint": "Сообщения ушли, но реакция ещё не классифицирована.",
            },
        ]

        return jsonify(
            {
                "success": True,
                "business_id": business_id,
                "window_days": window_days,
                "summary": payload,
                "blockers": blockers,
            }
        )
    except Exception as e:
        print(f"Error partnership blockers summary: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/partnership/outcomes-summary", methods=["GET"])
def partnership_outcomes_summary():
    """Partnership outcomes summary by channel and class for selected window."""
    user_data, error = _require_auth()
    if error:
        return error
    try:
        requested_business_id = str(request.args.get("business_id") or "").strip() or None
        window_days = max(1, min(int(request.args.get("window_days") or 30), 365))

        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
            schema_flags = _get_partnership_schema_flags(cur)
            total_reactions = 0
            positive_count = 0
            question_count = 0
            no_response_count = 0
            hard_no_count = 0
            by_channel: list[dict[str, Any]] = []

            if schema_flags["has_reaction_outcomes"]:
                cur.execute(
                    """
                    WITH leads_scope AS (
                        SELECT l.id
                        FROM prospectingleads l
                        WHERE l.business_id = %s
                          AND COALESCE(l.intent, 'client_outreach') = 'partnership_outreach'
                    ),
                    reactions_scope AS (
                        SELECT
                            COALESCE(q.channel, 'unknown') AS channel,
                            COALESCE(NULLIF(r.human_confirmed_outcome, ''), NULLIF(r.classified_outcome, ''), 'no_response') AS outcome
                        FROM outreachmessagereactions r
                        JOIN outreachsendqueue q ON q.id = r.queue_id
                        JOIN leads_scope ls ON ls.id = q.lead_id
                        WHERE COALESCE(r.updated_at, r.created_at) >= NOW() - (%s || ' days')::INTERVAL
                    )
                    SELECT
                        COUNT(*)::INT AS total_reactions,
                        COUNT(*) FILTER (WHERE outcome = 'positive')::INT AS positive_count,
                        COUNT(*) FILTER (WHERE outcome = 'question')::INT AS question_count,
                        COUNT(*) FILTER (WHERE outcome = 'no_response')::INT AS no_response_count,
                        COUNT(*) FILTER (WHERE outcome = 'hard_no')::INT AS hard_no_count
                    FROM reactions_scope
                    """,
                    (business_id, window_days),
                )
                row = cur.fetchone()
                if row and hasattr(row, "keys"):
                    total_reactions = int(row.get("total_reactions") or 0)
                    positive_count = int(row.get("positive_count") or 0)
                    question_count = int(row.get("question_count") or 0)
                    no_response_count = int(row.get("no_response_count") or 0)
                    hard_no_count = int(row.get("hard_no_count") or 0)
                else:
                    values = list(row or [0, 0, 0, 0, 0])
                    total_reactions = int(values[0] or 0)
                    positive_count = int(values[1] or 0)
                    question_count = int(values[2] or 0)
                    no_response_count = int(values[3] or 0)
                    hard_no_count = int(values[4] or 0)

                cur.execute(
                    """
                    WITH leads_scope AS (
                        SELECT l.id
                        FROM prospectingleads l
                        WHERE l.business_id = %s
                          AND COALESCE(l.intent, 'client_outreach') = 'partnership_outreach'
                    ),
                    reactions_scope AS (
                        SELECT
                            COALESCE(q.channel, 'unknown') AS channel,
                            COALESCE(NULLIF(r.human_confirmed_outcome, ''), NULLIF(r.classified_outcome, ''), 'no_response') AS outcome
                        FROM outreachmessagereactions r
                        JOIN outreachsendqueue q ON q.id = r.queue_id
                        JOIN leads_scope ls ON ls.id = q.lead_id
                        WHERE COALESCE(r.updated_at, r.created_at) >= NOW() - (%s || ' days')::INTERVAL
                    )
                    SELECT
                        channel,
                        COUNT(*)::INT AS total,
                        COUNT(*) FILTER (WHERE outcome = 'positive')::INT AS positive_count,
                        COUNT(*) FILTER (WHERE outcome = 'question')::INT AS question_count,
                        COUNT(*) FILTER (WHERE outcome = 'no_response')::INT AS no_response_count,
                        COUNT(*) FILTER (WHERE outcome = 'hard_no')::INT AS hard_no_count
                    FROM reactions_scope
                    GROUP BY channel
                    ORDER BY total DESC, channel ASC
                    """,
                    (business_id, window_days),
                )
                by_channel_rows = cur.fetchall() or []
                by_channel = [dict(r) if hasattr(r, "keys") else {} for r in by_channel_rows]
        finally:
            conn.close()

        def _pct(part: int, total: int) -> float:
            if total <= 0:
                return 0.0
            return round((part / total) * 100.0, 2)

        summary = {
            "total_reactions": total_reactions,
            "positive_count": positive_count,
            "question_count": question_count,
            "no_response_count": no_response_count,
            "hard_no_count": hard_no_count,
            "positive_rate_pct": _pct(positive_count, total_reactions),
            "question_rate_pct": _pct(question_count, total_reactions),
            "no_response_rate_pct": _pct(no_response_count, total_reactions),
            "hard_no_rate_pct": _pct(hard_no_count, total_reactions),
        }

        return jsonify(
            {
                "success": True,
                "business_id": business_id,
                "window_days": window_days,
                "summary": summary,
                "by_channel": by_channel,
            }
        )
    except Exception as e:
        print(f"Error partnership outcomes summary: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/partnership/leads/<string:lead_id>/parse", methods=["POST"])
def partnership_parse_lead(lead_id):
    """User-level parse enqueue for partnership lead."""
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
            lead = _load_partnership_lead(cur, lead_id=lead_id, business_id=business_id)
            if not lead:
                return jsonify({"error": "Lead not found"}), 404
        finally:
            conn.close()

        display_lead = _normalize_lead_for_display(dict(lead))
        if not display_lead:
            return jsonify({"error": "Lead is not available for parsing"}), 400
        if _is_internal_partnership_source_url(display_lead.get("source_url")):
            return jsonify({
                "error": "Для импортированных из Google Docs партнёров парсинг карты недоступен: добавьте ссылку на Яндекс Карты в поле источника или откройте карточку вручную.",
            }), 400

        business, business_created = _ensure_parse_business_for_partnership_lead(display_lead, str(user_data["user_id"]))
        parse_business_id = str(business.get("id") or "").strip()
        if not parse_business_id:
            return jsonify({"error": "Failed to resolve business for lead"}), 500

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
            return jsonify({"error": "У лида нет ссылки на Яндекс Карты для запуска парсинга"}), 400

        task = _enqueue_parse_task_for_business(parse_business_id, user_data["user_id"], source_url)
        refreshed_lead = _load_prospecting_lead(lead_id) or display_lead
        return jsonify(
            {
                "success": True,
                "lead": _normalize_lead_for_display(refreshed_lead),
                "business": {
                    "id": parse_business_id,
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
        print(f"Error partnership parse lead: {e}")
        return jsonify({"error": str(e)}), 500


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


@admin_prospecting_bp.route("/api/partnership/leads/<string:lead_id>", methods=["PATCH"])
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
                SELECT id, name, telegram_url, whatsapp_url, email
                FROM prospectingleads
                WHERE id = %s
                  AND business_id = %s
                  AND COALESCE(intent, 'client_outreach') = 'partnership_outreach'
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
            if status:
                assignments.append("status = %s")
                params.append(status)
            if pipeline_status:
                assignments.append("pipeline_status = %s")
                params.append(pipeline_status)
            if selected_channel is not None:
                assignments.append("selected_channel = %s")
                params.append(selected_channel)
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

            params.extend([lead_id, business_id])
            cur.execute(
                f"""
                UPDATE prospectingleads
                SET {', '.join(assignments)}
                WHERE id = %s
                  AND business_id = %s
                  AND COALESCE(intent, 'client_outreach') = 'partnership_outreach'
                RETURNING id, name, source_url, status, selected_channel, partnership_stage, pipeline_status, pilot_cohort,
                          deferred_reason, deferred_until, phone, email, website, telegram_url, whatsapp_url, city, category, address, updated_at
                """,
                tuple(params),
            )
            updated = cur.fetchone()
            if not updated:
                return jsonify({"error": "Lead not found"}), 404
            if pipeline_status == PIPELINE_CONVERTED:
                ensure_ai_learning_events_table(conn)
                cur.execute(
                    """
                    SELECT id, learning_note_json, generated_text, approved_text, edited_text
                    FROM outreachmessagedrafts
                    WHERE lead_id = %s
                    ORDER BY updated_at DESC, created_at DESC
                    LIMIT 1
                    """,
                    (lead_id,),
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

        return jsonify({"success": True, "item": dict(updated) if hasattr(updated, "keys") else updated})
    except Exception as e:
        print(f"Error updating partnership lead: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/partnership/leads/<string:lead_id>/manual-contact", methods=["POST"])
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
                SELECT *
                FROM prospectingleads
                WHERE id = %s
                  AND business_id = %s
                  AND COALESCE(intent, 'client_outreach') = 'partnership_outreach'
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

            updated = _apply_pipeline_transition(
                cur,
                lead_id=lead_id,
                pipeline_status=PIPELINE_CONTACTED,
                actor_id=str(user_data.get("user_id") or "") or None,
                comment=comment,
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
                payload={"channel": channel, "source": "partnership_room"},
            )
            conn.commit()
            updated = _normalize_lead_for_display(updated or lead_payload) or updated or lead_payload
        finally:
            conn.close()

        return jsonify({"success": True, "lead": _to_json_compatible(updated)})
    except Exception as e:
        print(f"Error marking partnership manual contact: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/partnership/leads/bulk-update", methods=["POST"])
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
                    SELECT id, name, telegram_url, whatsapp_url, email
                    FROM prospectingleads
                    WHERE id = ANY(%s)
                      AND business_id = %s
                      AND COALESCE(intent, 'client_outreach') = 'partnership_outreach'
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
            if status:
                assignments.append("status = %s")
                params.append(status)
            if pipeline_status:
                assignments.append("pipeline_status = %s")
                params.append(pipeline_status)
            if selected_channel is not None:
                assignments.append("selected_channel = %s")
                params.append(selected_channel)
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
                  AND business_id = %s
                  AND COALESCE(intent, 'client_outreach') = 'partnership_outreach'
                RETURNING id
                """,
                tuple(params),
            )
            rows = cur.fetchall() or []
            updated_ids = [row["id"] if hasattr(row, "get") else row[0] for row in rows]
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


@admin_prospecting_bp.route("/api/partnership/leads/<string:lead_id>", methods=["DELETE"])
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
                DELETE FROM prospectingleads
                WHERE id = %s
                  AND business_id = %s
                  AND COALESCE(intent, 'client_outreach') = 'partnership_outreach'
                RETURNING id
                """,
                (lead_id, business_id),
            )
            deleted = cur.fetchone()
            if not deleted:
                return jsonify({"error": "Lead not found"}), 404
            conn.commit()
        finally:
            conn.close()
        return jsonify({"success": True, "deleted_id": lead_id})
    except Exception as e:
        print(f"Error deleting partnership lead: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/partnership/leads/bulk-delete", methods=["POST"])
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
                DELETE FROM prospectingleads
                WHERE id = ANY(%s)
                  AND business_id = %s
                  AND COALESCE(intent, 'client_outreach') = 'partnership_outreach'
                RETURNING id
                """,
                (lead_ids, business_id),
            )
            rows = cur.fetchall() or []
            conn.commit()
        finally:
            conn.close()

        deleted_ids = [row["id"] if hasattr(row, "get") else row[0] for row in rows]
        return jsonify({"success": True, "deleted_count": len(deleted_ids), "deleted_ids": deleted_ids})
    except Exception as e:
        print(f"Error bulk deleting partnership leads: {e}")
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


def _make_sales_room_url(slug: str) -> str:
    frontend_base = str(os.environ.get("FRONTEND_BASE_URL") or "").strip().rstrip("/")
    if not frontend_base:
        frontend_base = "https://localos.pro"
    return f"{frontend_base}/room/{slug}"


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


def _append_sales_room_link_to_outreach_text(text: str, room_url: str) -> str:
    cleaned = str(text or "").strip()
    url = str(room_url or "").strip()
    if not cleaned or not url or "/room/" in cleaned:
        return cleaned
    return (
        f"{cleaned}\n\n"
        "Для удобства подготовил общую цифровую комнату, где можно обсуждать идеи, "
        "приглашать коллег и обмениваться материалами:\n\n"
        f"{url}"
    )


def _normalize_sales_room_data_mode(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized == SALES_ROOM_DATA_AUDITED:
        return SALES_ROOM_DATA_AUDITED
    return SALES_ROOM_DATA_TEMPLATE


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


def _build_sales_room_invitation_text(
    *,
    mode: str,
    data_mode: str,
    business_name: str,
    lead_name: str,
    room_url: str,
) -> str:
    if mode == SALES_ROOM_MODE_PARTNER:
        if data_mode == SALES_ROOM_DATA_AUDITED:
            return (
                "Здравствуйте!\n\n"
                f"Мы — {business_name}. Подготовили предложение по возможному партнёрству с {lead_name}.\n\n"
                "Для удобства собрал всё в общей цифровой комнате: там можно посмотреть идею, "
                "пригласить коллег, внести правки и обмениваться материалами.\n\n"
                f"{room_url}\n\n"
                "Подскажите, пожалуйста, с кем можно обсудить возможные варианты сотрудничества?"
            )
        return (
            "Здравствуйте!\n\n"
            f"Мы — {business_name}. Подготовили короткую идею сотрудничества с {lead_name}.\n\n"
            "Для удобства сделал общую цифровую комнату, где можно обсуждать варианты, "
            "приглашать коллег и обмениваться материалами.\n\n"
            f"{room_url}\n\n"
            "Подскажите, пожалуйста, с кем можно обсудить возможное сотрудничество?"
        )
    if data_mode == SALES_ROOM_DATA_AUDITED:
        return (
            f"Здравствуйте. Подготовили короткий разбор, где у {lead_name} могут теряться обращения и что можно улучшить.\n\n"
            f"Собрали всё на одной странице:\n{room_url}"
        )
    return (
        f"Здравствуйте. Подготовили короткое предложение по росту для {lead_name}.\n\n"
        f"Собрали его на одной странице:\n{room_url}"
    )


def _create_sales_room_invitation_draft(
    cur,
    *,
    lead_id: str,
    room_id: str,
    mode: str,
    data_mode: str,
    channel: str,
    text: str,
    user_id: str,
) -> dict[str, Any]:
    draft_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO outreachmessagedrafts (
            id, lead_id, channel, angle_type, tone, status,
            generated_text, edited_text, learning_note_json, created_by, created_at, updated_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, NOW(), NOW()
        )
        RETURNING id, lead_id, channel, angle_type, tone, status,
                  generated_text, edited_text, approved_text,
                  learning_note_json, created_at, updated_at
        """,
        (
            draft_id,
            lead_id,
            channel,
            "sales_room_invitation",
            "professional",
            DRAFT_GENERATED,
            text,
            text,
            Json(
                {
                    "intent": "partnership_outreach" if mode == SALES_ROOM_MODE_PARTNER else "client_outreach",
                    "room_id": room_id,
                    "data_mode": data_mode,
                    "prompt_key": "sales_room.invitation",
                    "prompt_version": "v1",
                    "prompt_source": "local_template",
                }
            ),
            user_id,
        ),
    )
    draft = _row_to_dict(cur.fetchone())
    cur.execute(
        """
        UPDATE sales_rooms
        SET invitation_draft_id = %s,
            status = 'invitation_ready',
            updated_at = NOW()
        WHERE id = %s
        """,
        (draft_id, room_id),
    )
    return draft


def _record_sales_room_event(conn, *, slug: str, event_type: str, metadata: dict[str, Any] | None = None) -> None:
    _ensure_sales_room_tables(conn)
    cur = conn.cursor()
    cur.execute("SELECT id FROM sales_rooms WHERE slug = %s LIMIT 1", (slug,))
    row = cur.fetchone()
    if not row:
        return
    room_id = row.get("id") if hasattr(row, "get") else row[0]
    cur.execute(
        """
        INSERT INTO sales_room_events (id, room_id, event_type, metadata_json, created_at)
        VALUES (%s, %s, %s, %s, NOW())
        """,
        (str(uuid.uuid4()), room_id, event_type, Json(metadata or {})),
    )
    if event_type == "view":
        cur.execute(
            """
            UPDATE sales_rooms
            SET status = CASE WHEN status IN ('ready', 'invitation_ready', 'approved', 'sent') THEN 'viewed' ELSE status END,
                updated_at = NOW()
            WHERE id = %s
            """,
            (room_id,),
        )


def _sales_room_upload_root() -> str:
    return sales_room_upload_root()


def _clean_sales_room_filename(filename: str) -> str:
    raw = str(filename or "file").strip().replace("\\", "/").split("/")[-1]
    cleaned = re.sub(r"[^A-Za-z0-9А-Яа-яЁё._ -]+", "-", raw).strip(" .-")
    return cleaned or "file"


def _sales_room_file_extension(filename: str) -> str:
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].strip().lower()


def _is_uuid_string(value: str) -> bool:
    try:
        uuid.UUID(str(value or "").strip())
        return True
    except ValueError:
        return False


def _serialize_sales_room_message(row: dict[str, Any]) -> dict[str, Any]:
    attachments = row.get("attachments_json")
    if not isinstance(attachments, list):
        attachments = []
    return _to_json_compatible(
        {
            "id": row.get("id"),
            "author_type": row.get("author_type") or "visitor",
            "author_name": row.get("author_name") or "Гость",
            "author_contact": row.get("author_contact") or "",
            "body_text": row.get("body_text") or "",
            "attachments": attachments,
            "created_at": row.get("created_at"),
        }
    )


def _serialize_sales_room_version(row: dict[str, Any]) -> dict[str, Any]:
    return _to_json_compatible(
        {
            "id": row.get("id"),
            "version_no": int(row.get("version_no") or 0),
            "body_text": row.get("body_text") or "",
            "created_by_name": row.get("created_by_name") or "",
            "created_by_contact": row.get("created_by_contact") or "",
            "created_at": row.get("created_at"),
        }
    )


def _serialize_sales_room_suggestion(row: dict[str, Any]) -> dict[str, Any]:
    return _to_json_compatible(
        {
            "id": row.get("id"),
            "version_id": row.get("version_id"),
            "suggestion_type": row.get("suggestion_type") or "replace",
            "selection_text": row.get("selection_text") or "",
            "selection_start": row.get("selection_start"),
            "selection_end": row.get("selection_end"),
            "replacement_text": row.get("replacement_text") or "",
            "comment_text": row.get("comment_text") or "",
            "author_name": row.get("author_name") or "Гость",
            "author_contact": row.get("author_contact") or "",
            "status": row.get("status") or "pending",
            "resolved_by_name": row.get("resolved_by_name") or "",
            "resolved_by_contact": row.get("resolved_by_contact") or "",
            "resolved_at": row.get("resolved_at"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }
    )


def _load_sales_room_messages(cur, room_id: str, limit: int = 50) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT id, author_type, author_name, author_contact, body_text, attachments_json, created_at
        FROM sales_room_messages
        WHERE room_id = %s
        ORDER BY created_at ASC
        LIMIT %s
        """,
        (room_id, limit),
    )
    rows = cur.fetchall() or []
    return [_serialize_sales_room_message(dict(row)) for row in rows]


def _load_sales_room_latest_version(cur, room_id: str) -> dict[str, Any]:
    cur.execute(
        """
        SELECT id, version_no, body_text, created_by_name, created_by_contact, metadata_json, created_at
        FROM sales_room_proposal_versions
        WHERE room_id = %s
        ORDER BY version_no DESC
        LIMIT 1
        """,
        (room_id,),
    )
    row = cur.fetchone()
    return dict(row) if row and hasattr(row, "keys") else {}


def _load_sales_room_review(cur, room_id: str) -> dict[str, Any]:
    latest = _load_sales_room_latest_version(cur, room_id)
    cur.execute(
        """
        SELECT id, version_id, suggestion_type, selection_text, selection_start, selection_end,
               replacement_text, comment_text, author_name, author_contact, status,
               resolved_by_name, resolved_by_contact, resolved_at, created_at, updated_at
        FROM sales_room_proposal_suggestions
        WHERE room_id = %s
        ORDER BY
          CASE WHEN status = 'pending' THEN 0 ELSE 1 END,
          created_at DESC
        LIMIT 100
        """,
        (room_id,),
    )
    suggestions = [_serialize_sales_room_suggestion(dict(row)) for row in (cur.fetchall() or [])]
    return {
        "latest_version": _serialize_sales_room_version(latest) if latest else None,
        "suggestions": suggestions,
    }


def _ensure_sales_room_proposal_version(
    cur,
    *,
    room_id: str,
    body_text: str,
    author_name: str = "",
    author_contact: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    current = _load_sales_room_latest_version(cur, room_id)
    if current:
        return current
    version_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO sales_room_proposal_versions (
            id, room_id, version_no, body_text, created_by_name, created_by_contact, metadata_json, created_at
        ) VALUES (
            %s, %s, 1, %s, %s, %s, %s, NOW()
        )
        RETURNING id, version_no, body_text, created_by_name, created_by_contact, metadata_json, created_at
        """,
        (version_id, room_id, body_text, author_name, author_contact, Json(metadata or {"source": "initial_room_proposal"})),
    )
    return dict(cur.fetchone())


def _create_sales_room_proposal_version(
    cur,
    *,
    room_id: str,
    body_text: str,
    author_name: str,
    author_contact: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    latest = _load_sales_room_latest_version(cur, room_id)
    next_version_no = int(latest.get("version_no") or 0) + 1 if latest else 1
    version_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO sales_room_proposal_versions (
            id, room_id, version_no, body_text, created_by_name, created_by_contact, metadata_json, created_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, NOW()
        )
        RETURNING id, version_no, body_text, created_by_name, created_by_contact, metadata_json, created_at
        """,
        (version_id, room_id, next_version_no, body_text, author_name, author_contact, Json(metadata or {})),
    )
    return dict(cur.fetchone())


def _replace_text_for_sales_room_suggestion(current_text: str, suggestion: dict[str, Any]) -> tuple[str, bool, str]:
    selection_text = str(suggestion.get("selection_text") or "")
    replacement_text = str(suggestion.get("replacement_text") or "")
    start_value = suggestion.get("selection_start")
    end_value = suggestion.get("selection_end")
    try:
        start = int(start_value) if start_value is not None else -1
        end = int(end_value) if end_value is not None else -1
    except (TypeError, ValueError):
        start = -1
        end = -1
    if start >= 0 and end > start and current_text[start:end] == selection_text:
        return f"{current_text[:start]}{replacement_text}{current_text[end:]}", True, "range"
    if selection_text and selection_text in current_text:
        return current_text.replace(selection_text, replacement_text, 1), True, "text"
    return current_text, False, "selection_not_found"


def _update_sales_room_proposal_body(cur, *, room_id: str, body_text: str) -> None:
    cur.execute(
        """
        UPDATE sales_rooms
        SET room_json = jsonb_set(
                COALESCE(room_json, '{}'),
                '{proposal,body_text}',
                to_jsonb(%s::text),
                TRUE
            ),
            proposal_json = jsonb_set(
                COALESCE(proposal_json, '{}'),
                '{body_text}',
                to_jsonb(%s::text),
                TRUE
            ),
            updated_at = NOW()
        WHERE id = %s
        """,
        (body_text, body_text, room_id),
    )


def _load_sales_room_by_slug(cur, slug: str) -> dict[str, Any]:
    cur.execute(
        """
        SELECT id, slug, business_id, mode, lead_id, room_json, status, updated_at
        FROM sales_rooms
        WHERE slug = %s
        LIMIT 1
        """,
        (slug,),
    )
    row = cur.fetchone()
    return dict(row) if row and hasattr(row, "keys") else {}


def _can_edit_sales_room(cur, room: dict[str, Any], user_data: dict[str, Any] | None) -> bool:
    if not user_data:
        return False
    if bool(user_data.get("is_superadmin")):
        return True
    user_id = str(user_data.get("user_id") or user_data.get("id") or "").strip()
    business_id = str(room.get("business_id") or "").strip()
    if not user_id or not business_id:
        return False
    cur.execute(
        """
        SELECT id
        FROM businesses
        WHERE id = %s
          AND owner_id = %s
        LIMIT 1
        """,
        (business_id, user_id),
    )
    return bool(cur.fetchone())


def _load_sales_room_offer_text_from_drafts(cur, lead_id: str) -> str:
    clean_lead_id = str(lead_id or "").strip()
    if not clean_lead_id:
        return ""
    cur.execute(
        """
        SELECT approved_text, edited_text, generated_text
        FROM outreachmessagedrafts
        WHERE lead_id = %s
          AND angle_type IN ('partnership_offer', 'partnership_commercial_offer')
        ORDER BY
          CASE WHEN status = 'approved' THEN 0 ELSE 1 END,
          updated_at DESC NULLS LAST,
          created_at DESC NULLS LAST
        LIMIT 1
        """,
        (clean_lead_id,),
    )
    row = cur.fetchone()
    draft = dict(row) if row and hasattr(row, "keys") else {}
    return _clean_sales_room_offer_text(
        str(draft.get("approved_text") or draft.get("edited_text") or draft.get("generated_text") or "")
    )


def _normalize_public_sales_room_proposal(cur, row: dict[str, Any], room_json: dict[str, Any]) -> dict[str, Any]:
    proposal = room_json.get("proposal") if isinstance(room_json.get("proposal"), dict) else {}
    body_text = str(proposal.get("body_text") or "").strip()
    mode = str(row.get("mode") or room_json.get("mode") or "").strip()
    lead_id = str(row.get("lead_id") or "").strip()
    if not body_text and mode == SALES_ROOM_MODE_PARTNER and lead_id:
        try:
            artifact = _load_partnership_artifact(cur, lead_id)
            offer_draft_json = artifact.get("offer_draft_json") if isinstance(artifact.get("offer_draft_json"), dict) else {}
            body_text = _extract_sales_room_offer_text(offer_draft_json)
        except Exception:
            print("Sales room offer artifact fallback skipped")
    if not body_text and mode == SALES_ROOM_MODE_PARTNER and lead_id:
        try:
            body_text = _load_sales_room_offer_text_from_drafts(cur, lead_id)
        except Exception:
            print("Sales room outreach draft fallback skipped")
    business = room_json.get("business") if isinstance(room_json.get("business"), dict) else {}
    recipient = room_json.get("recipient") if isinstance(room_json.get("recipient"), dict) else {}
    if not body_text:
        body_text = _fallback_sales_room_offer_text(
            mode=mode,
            business_name=str(business.get("name") or "наша компания"),
            lead_name=str(recipient.get("name") or "компания"),
        )
    room_json["proposal"] = {
        "title": "Предложение",
        "summary": "",
        "body_text": body_text,
        "bullets": [],
        "next_step": str(proposal.get("next_step") or "Обсудить детали и выбрать первый шаг.").strip(),
        "data_mode": str(proposal.get("data_mode") or room_json.get("data_mode") or ""),
    }
    return room_json


def _resolve_outreach_language(lead: dict[str, Any]) -> str:
    language = str(lead.get("preferred_language") or "").strip().lower()
    text_candidates = [
        str(lead.get("name") or ""),
        str(lead.get("category") or ""),
        str(lead.get("city") or ""),
        str(lead.get("address") or ""),
    ]
    joined = " ".join(text_candidates)
    has_cyrillic = bool(re.search(r"[А-Яа-яЁё]", joined))
    if has_cyrillic:
        return "ru"
    if language in PUBLIC_AUDIT_LANGUAGES:
        return language
    return "en"


def _attach_admin_prospecting_public_offer_metadata(conn, lead: dict[str, Any]) -> dict[str, Any]:
    payload = dict(lead or {})
    lead_id = str(payload.get("id") or "").strip()
    if not lead_id:
        return payload

    _ensure_admin_prospecting_public_offers_table(conn)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """
        SELECT slug, is_active, updated_at, page_json, published_json, generated_json
        FROM adminprospectingleadpublicoffers
        WHERE lead_id = %s
        LIMIT 1
        """,
        (lead_id,),
    )
    offer = cur.fetchone()
    if offer and bool(offer.get("is_active")) and str(offer.get("slug") or "").strip():
        slug = str(offer.get("slug") or "").strip()
        page_json = _resolve_admin_public_offer_row_page_json(offer)
        primary_language, enabled_languages = _normalize_public_audit_languages(
            page_json.get("preferred_language"),
            page_json.get("enabled_languages"),
        )
        payload["public_audit_slug"] = slug
        payload["public_audit_url"] = _make_public_offer_url(slug)
        payload["has_public_audit"] = True
        payload["public_audit_updated_at"] = offer.get("updated_at")
        payload["preferred_language"] = primary_language
        payload["enabled_languages"] = enabled_languages
        return payload

    payload.pop("public_audit_slug", None)
    payload.pop("public_audit_url", None)
    payload.pop("has_public_audit", None)
    payload.pop("public_audit_updated_at", None)
    return payload


def _append_public_offer_language(url: str, language: str | None) -> str:
    normalized_language = str(language or "").strip().lower()
    if normalized_language not in set(PUBLIC_AUDIT_LANGUAGES):
        return url
    delimiter = "&" if "?" in url else "?"
    return f"{url}{delimiter}lang={normalized_language}"


def _resolve_admin_public_offer_row_page_json(row: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(row, dict):
        return {}
    published_json = row.get("published_json")
    if isinstance(published_json, dict) and published_json:
        return published_json
    page_json = row.get("page_json")
    if isinstance(page_json, dict) and page_json:
        return page_json
    generated_json = row.get("generated_json")
    if isinstance(generated_json, dict):
        return generated_json
    return {}


def _fetch_admin_public_offer_row(cur, lead_id: str) -> dict[str, Any] | None:
    cur.execute(
        """
        SELECT
            lead_id,
            slug,
            page_json,
            generated_json,
            edited_json,
            published_json,
            business_id,
            business_profile,
            source_type,
            edit_status,
            created_by,
            created_at,
            updated_at,
            edited_by,
            edited_at,
            published_by,
            published_at
        FROM adminprospectingleadpublicoffers
        WHERE lead_id = %s
        LIMIT 1
        """,
        (lead_id,),
    )
    row = cur.fetchone()
    return dict(row) if row and hasattr(row, "keys") else None


def _normalize_admin_public_offer_row(row: dict[str, Any]) -> dict[str, Any]:
    generated_json = row.get("generated_json") if isinstance(row.get("generated_json"), dict) else {}
    page_json = row.get("page_json") if isinstance(row.get("page_json"), dict) else {}
    published_json = row.get("published_json") if isinstance(row.get("published_json"), dict) else {}
    if not generated_json:
        generated_json = page_json or published_json
    if not published_json:
        published_json = page_json or generated_json
    edited_json = row.get("edited_json") if isinstance(row.get("edited_json"), dict) else None
    edit_status = str(row.get("edit_status") or "").strip() or "generated"
    if not row.get("business_profile") and isinstance(generated_json, dict):
        audit = generated_json.get("audit") if isinstance(generated_json.get("audit"), dict) else {}
        row["business_profile"] = str(audit.get("audit_profile") or "").strip() or None
    row["generated_json"] = generated_json
    row["published_json"] = published_json
    row["page_json"] = published_json
    row["edited_json"] = edited_json
    row["edit_status"] = edit_status
    return row


def _build_admin_public_offer_editor_response(
    *,
    row: dict[str, Any],
    lead: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_row = _normalize_admin_public_offer_row(dict(row))
    generated_json = normalized_row.get("generated_json") if isinstance(normalized_row.get("generated_json"), dict) else {}
    published_json = normalized_row.get("published_json") if isinstance(normalized_row.get("published_json"), dict) else {}
    edited_json = normalized_row.get("edited_json") if isinstance(normalized_row.get("edited_json"), dict) else None
    state = normalize_editor_state(
        generated_page_json=generated_json,
        edited_json=edited_json,
        published_page_json=published_json,
    )
    diff = compute_editor_diff(state["generated"], state["edited"], state["published"])
    return _to_json_compatible(
        {
            "success": True,
            "audit_id": f"admin_public_offer:{normalized_row.get('lead_id')}",
            "lead_id": normalized_row.get("lead_id"),
            "slug": normalized_row.get("slug"),
            "public_url": _append_public_offer_language(
                _make_public_offer_url(str(normalized_row.get("slug") or "")),
                (published_json.get("preferred_language") if isinstance(published_json, dict) else None),
            ) if normalized_row.get("slug") else None,
            "edit_status": normalized_row.get("edit_status"),
            "business_id": normalized_row.get("business_id"),
            "business_profile": normalized_row.get("business_profile"),
            "source_type": normalized_row.get("source_type") or "admin_prospecting_public_audit",
            "generated": state["generated"],
            "edited": state["edited"],
            "published": state["published"],
            "diff": diff,
            "meta": {
                "created_at": normalized_row.get("created_at"),
                "updated_at": normalized_row.get("updated_at"),
                "edited_at": normalized_row.get("edited_at"),
                "published_at": normalized_row.get("published_at"),
                "edited_by": normalized_row.get("edited_by"),
                "published_by": normalized_row.get("published_by"),
                "lead_name": str((lead or {}).get("name") or published_json.get("name") or "").strip() or None,
            },
        }
    )


def _apply_admin_public_offer_edited_snapshot(
    *,
    row: dict[str, Any],
    edited_blocks: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], str]:
    normalized_row = _normalize_admin_public_offer_row(dict(row))
    generated_json = normalized_row.get("generated_json") if isinstance(normalized_row.get("generated_json"), dict) else {}
    generated_blocks = build_generated_editor_blocks(generated_json)
    normalized_blocks = normalize_editor_blocks(edited_blocks)
    if blocks_equal(generated_blocks, normalized_blocks):
        return generated_blocks, {}, "generated"
    return generated_blocks, {"blocks": normalized_blocks}, "draft_edited"


def _record_admin_public_audit_learning_events(
    *,
    conn,
    user_id: str | None,
    lead_id: str,
    audit_id: str,
    business_id: str | None,
    generated_page_json: dict[str, Any],
    generated_blocks: dict[str, Any],
    published_blocks: dict[str, Any],
) -> None:
    for block_key in EDITOR_BLOCK_KEYS:
        generated_text = render_block_text(block_key, generated_blocks.get(block_key))
        final_text = render_block_text(block_key, published_blocks.get(block_key))
        if generated_text == final_text:
            continue
        edit_kind = classify_edit_kind(generated_text, final_text)
        record_ai_learning_event(
            capability="lead.audit_block_editor",
            event_type="accepted",
            intent="client_outreach",
            user_id=user_id,
            business_id=business_id,
            accepted=True,
            edited_before_accept=True,
            prompt_key=block_key,
            prompt_version="manual_editor_v1",
            draft_text=generated_text[:3000],
            final_text=final_text[:3000],
            metadata=build_learning_metadata(
                page_json=generated_page_json,
                lead_id=lead_id,
                audit_id=audit_id,
                block_key=block_key,
                edit_kind=edit_kind,
            ),
            conn=conn,
        )


def _load_partnership_lead(cur, *, lead_id: str, business_id: str):
    cur.execute(
        """
        SELECT *
        FROM prospectingleads
        WHERE id = %s
          AND business_id = %s
          AND COALESCE(intent, 'client_outreach') = 'partnership_outreach'
        LIMIT 1
        """,
        (lead_id, business_id),
    )
    row = cur.fetchone()
    return dict(row) if row and hasattr(row, "keys") else None


def _load_business_profile(cur, business_id: str) -> dict[str, Any]:
    cur.execute("SELECT * FROM businesses WHERE id = %s LIMIT 1", (business_id,))
    row = cur.fetchone()
    return dict(row) if row and hasattr(row, "keys") else {}


def _pick_business_display_name(profile: dict[str, Any]) -> str:
    for key in ("name", "title", "company_name", "organization_name", "org_name"):
        value = str(profile.get(key) or "").strip()
        if value:
            return value
    return "наша компания"


def _reserve_sales_room_credit(cur, *, business_id: str, user_id: str, lead_id: str, mode: str) -> dict[str, Any]:
    return reserve_paid_action_credits(
        cur,
        business_id=business_id,
        user_id=user_id,
        action_key="sales_room.prepare_audited",
        estimated_credits=SALES_ROOM_AUDITED_CREDITS,
        idempotency_key=f"{mode}:{business_id}:{lead_id}:audited",
        metadata={
            "mode": mode,
            "lead_id": lead_id,
            "estimated_credits": SALES_ROOM_AUDITED_CREDITS,
        },
    )


def _finalize_sales_room_credit(
    cur,
    *,
    reservation: dict[str, Any],
    business_id: str,
    user_id: str,
    room_id: str,
) -> dict[str, Any]:
    reservation_id = str(reservation.get("reservation_id") or "").strip()
    if not reservation_id:
        return {
            "status": "not_required",
            "credit_charged": False,
            "charged_credits": 0,
        }
    finalization = finalize_reserved_action_credits(
        cur,
        reservation_id=reservation_id,
        business_id=business_id,
        user_id=user_id,
        actual_credits=SALES_ROOM_AUDITED_CREDITS,
        finalization_mode="charge",
        external_id=f"sales_room:{room_id}",
    )
    return {
        "status": finalization.get("status"),
        "reservation_id": reservation_id,
        "credit_charged": bool((finalization.get("side_effects") or {}).get("credit_charged")),
        "charged_credits": int(finalization.get("charge_credits") or 0),
        "blocked_reasons": finalization.get("blocked_reasons") or [],
    }


def _load_partnership_artifact(cur, lead_id: str) -> dict[str, Any]:
    _ensure_partnership_artifacts_table_from_cursor(cur)
    cur.execute(
        """
        SELECT audit_json, match_json, offer_draft_json
        FROM partnershipleadartifacts
        WHERE lead_id = %s
        LIMIT 1
        """,
        (lead_id,),
    )
    row = cur.fetchone()
    return _row_to_dict(row)


def _ensure_partnership_artifacts_table_from_cursor(cur) -> None:
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


def _create_or_update_sales_room(
    cur,
    *,
    business_id: str,
    user_id: str,
    mode: str,
    data_mode: str,
    lead: dict[str, Any],
    business_profile: dict[str, Any],
    audit_public_url: str,
    audit_json: dict[str, Any] | None,
    match_json: dict[str, Any] | None,
    offer_draft_json: dict[str, Any] | None = None,
    partner_card_id: str | None = None,
    channel: str = "manual",
) -> tuple[dict[str, Any], dict[str, Any]]:
    lead_id = str(lead.get("id") or "").strip()
    lead_name = str(lead.get("name") or "company").strip() or "company"
    business_name = _pick_business_display_name(business_profile)
    room_id = str(uuid.uuid4())
    slug = _unique_sales_room_slug(
        cur,
        _sales_room_slug_base(lead_name, lead.get("city"), lead.get("address")),
    )
    proposal_json = _build_sales_room_proposal(
        mode=mode,
        data_mode=data_mode,
        lead=lead,
        business_name=business_name,
        audit_json=audit_json,
        match_json=match_json,
        offer_draft_json=offer_draft_json,
    )
    room_json = _build_sales_room_payload(
        mode=mode,
        data_mode=data_mode,
        lead=lead,
        business_profile=business_profile,
        audit_public_url=audit_public_url,
        audit_json=audit_json,
        match_json=match_json,
        proposal_json=proposal_json,
        slug=slug,
    )
    cur.execute(
        """
        INSERT INTO sales_rooms (
            id, slug, business_id, mode, lead_id, partner_card_id,
            data_mode, audit_public_url, match_json, proposal_json, room_json,
            status, created_by, created_at, updated_at
        ) VALUES (
            %s, %s, %s, %s, %s, NULLIF(%s, '')::uuid,
            %s, %s, %s, %s, %s,
            'ready', NULLIF(%s, '')::uuid, NOW(), NOW()
        )
        RETURNING *
        """,
        (
            room_id,
            slug,
            business_id,
            mode,
            lead_id or None,
            str(partner_card_id or ""),
            data_mode,
            audit_public_url or None,
            Json(match_json or {}),
            Json(proposal_json),
            Json(room_json),
            user_id,
        ),
    )
    room = _row_to_dict(cur.fetchone())
    invitation_text = _build_sales_room_invitation_text(
        mode=mode,
        data_mode=data_mode,
        business_name=business_name,
        lead_name=lead_name,
        room_url=_make_sales_room_url(slug),
    )
    draft = _create_sales_room_invitation_draft(
        cur,
        lead_id=lead_id,
        room_id=room_id,
        mode=mode,
        data_mode=data_mode,
        channel=channel,
        text=invitation_text,
        user_id=user_id,
    )
    room["invitation_draft_id"] = draft.get("id")
    room["public_url"] = _make_sales_room_url(slug)
    room["room_json"] = room_json
    return room, draft


def _prepare_partnership_sales_room(
    *,
    lead_id: str,
    business_id: str,
    user_id: str,
    data_mode: str,
    channel: str,
) -> dict[str, Any]:
    conn = get_db_connection()
    try:
        _ensure_partnership_columns(conn)
        _ensure_partnership_artifacts_table(conn)
        _ensure_sales_room_tables(conn)
        cur = conn.cursor()
        lead = _load_partnership_lead(cur, lead_id=lead_id, business_id=business_id)
        if not lead:
            return {"error": "Lead not found", "status_code": 404}
        business_profile = _load_business_profile(cur, business_id)
        reservation: dict[str, Any] = {}
        if data_mode == SALES_ROOM_DATA_AUDITED:
            reservation = _reserve_sales_room_credit(cur, business_id=business_id, user_id=user_id, lead_id=lead_id, mode=SALES_ROOM_MODE_PARTNER)
            if str(reservation.get("status") or "") != "reserved":
                conn.rollback()
                return {
                    "error": "insufficient_credits",
                    "status_code": 402,
                    "billing": reservation,
                }

        artifact = _load_partnership_artifact(cur, lead_id)
        audit_json = artifact.get("audit_json") if isinstance(artifact.get("audit_json"), dict) else {}
        offer_draft_json = artifact.get("offer_draft_json") if isinstance(artifact.get("offer_draft_json"), dict) else {}
        if not offer_draft_json:
            draft_text = _load_sales_room_offer_text_from_drafts(cur, lead_id)
            if draft_text:
                offer_draft_json = {"text": draft_text}
        if data_mode == SALES_ROOM_DATA_AUDITED and not audit_json:
            audit_json = _to_json_compatible(build_lead_card_preview_snapshot(lead))
        match_json = artifact.get("match_json") if isinstance(artifact.get("match_json"), dict) else {}
        if data_mode == SALES_ROOM_DATA_AUDITED and not match_json:
            match_json = _compute_partnership_match_result(
                cur,
                business_id=business_id,
                lead_id=lead_id,
                audit_json=audit_json,
            )
        if data_mode == SALES_ROOM_DATA_AUDITED:
            cur.execute(
                """
                INSERT INTO partnershipleadartifacts (lead_id, audit_json, match_json, updated_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (lead_id) DO UPDATE
                SET audit_json = EXCLUDED.audit_json,
                    match_json = EXCLUDED.match_json,
                    updated_at = NOW()
                """,
                (lead_id, Json(audit_json), Json(match_json)),
            )
        room, draft = _create_or_update_sales_room(
            cur,
            business_id=business_id,
            user_id=user_id,
            mode=SALES_ROOM_MODE_PARTNER,
            data_mode=data_mode,
            lead=lead,
            business_profile=business_profile,
            audit_public_url=str(lead.get("public_audit_url") or ""),
            audit_json=audit_json,
            match_json=match_json,
            offer_draft_json=offer_draft_json,
            channel=channel,
        )
        billing = {"status": "not_required", "credit_charged": False, "charged_credits": 0}
        if data_mode == SALES_ROOM_DATA_AUDITED:
            billing = _finalize_sales_room_credit(
                cur,
                reservation=reservation,
                business_id=business_id,
                user_id=user_id,
                room_id=str(room.get("id") or ""),
            )
        cur.execute(
            """
            UPDATE prospectingleads
            SET partnership_stage = %s,
                status = %s,
                selected_channel = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            ("proposal_draft_ready", "proposal_draft_ready", channel, lead_id),
        )
        conn.commit()
        return {"success": True, "room": room, "draft": _serialize_draft(draft), "billing": billing}
    finally:
        conn.close()


def _prepare_client_sales_room(
    *,
    lead_id: str,
    user_id: str,
    data_mode: str,
    channel: str,
) -> dict[str, Any]:
    conn = get_db_connection()
    try:
        _ensure_sales_room_tables(conn)
        _ensure_admin_prospecting_public_offers_table(conn)
        cur = conn.cursor()
        cur.execute("SELECT * FROM prospectingleads WHERE id = %s LIMIT 1", (lead_id,))
        lead = _row_to_dict(cur.fetchone())
        if not lead:
            return {"error": "Lead not found", "status_code": 404}
        display_lead = _normalize_lead_for_display(dict(lead))
        if not display_lead:
            return {"error": "Lead is not available for room", "status_code": 400}
        business_id = str(display_lead.get("business_id") or "").strip()
        if not business_id:
            business, _business_created = _ensure_parse_business_for_lead(display_lead, user_id)
            business_id = str(business.get("id") or "").strip()
            _update_lead_business_link(lead_id, business_id)
            display_lead["business_id"] = business_id
        if not business_id:
            return {"error": "Business not found for lead", "status_code": 400}
        business_profile = _load_business_profile(cur, business_id)
        reservation: dict[str, Any] = {}
        if data_mode == SALES_ROOM_DATA_AUDITED:
            reservation = _reserve_sales_room_credit(cur, business_id=business_id, user_id=user_id, lead_id=lead_id, mode=SALES_ROOM_MODE_CLIENT)
            if str(reservation.get("status") or "") != "reserved":
                conn.rollback()
                return {
                    "error": "insufficient_credits",
                    "status_code": 402,
                    "billing": reservation,
                }
        display_lead = _attach_admin_prospecting_public_offer_metadata(conn, display_lead)
        preview = build_lead_card_preview_snapshot(display_lead) if data_mode == SALES_ROOM_DATA_AUDITED else {}
        audit_public_url = str(display_lead.get("public_audit_url") or "")
        room, draft = _create_or_update_sales_room(
            cur,
            business_id=business_id,
            user_id=user_id,
            mode=SALES_ROOM_MODE_CLIENT,
            data_mode=data_mode,
            lead=display_lead,
            business_profile=business_profile,
            audit_public_url=audit_public_url,
            audit_json=preview,
            match_json={},
            channel=channel,
        )
        billing = {"status": "not_required", "credit_charged": False, "charged_credits": 0}
        if data_mode == SALES_ROOM_DATA_AUDITED:
            billing = _finalize_sales_room_credit(
                cur,
                reservation=reservation,
                business_id=business_id,
                user_id=user_id,
                room_id=str(room.get("id") or ""),
            )
        cur.execute(
            """
            UPDATE prospectingleads
            SET status = %s,
                selected_channel = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (CHANNEL_SELECTED, channel, lead_id),
        )
        conn.commit()
        return {"success": True, "room": room, "draft": _serialize_draft(draft), "billing": billing}
    finally:
        conn.close()


def _classify_partnership_business_type(*parts: Any) -> str:
    text = " ".join(str(part or "") for part in parts).lower()
    rules = [
        ("dentistry", ("стомат", "зуб", "улыб", "ортодонт", "имплант")),
        ("cosmetology", ("косметолог", "косметик", "инъекц", "ботокс", "пилинг", "лицо")),
        ("hair_salon", ("парикмах", "стриж", "уклад", "волос", "причес", "причёс")),
        ("nail_salon", ("маник", "педик", "ногт", "nail")),
        ("beauty_salon", ("салон красот", "красот", "бров", "ресниц")),
        ("dance_school", ("танц", "хореограф", "балет")),
        ("theatre_studio", ("театр", "актер", "актёр", "сцен")),
        ("swimming_pool", ("аква", "бассейн", "плаван")),
        ("kids_center", ("детск", "дети", "ребен", "ребён", "школа", "садик", "центр развития")),
        ("sports_section", ("секц", "спорт", "единобор", "карат", "футбол", "гимнаст")),
        ("fitness", ("фитнес", "тренаж", "спортзал", "йога", "пилатес")),
        ("cultural_center", ("культур", "дворец", "дом творч", "центр досуг")),
        ("rope_park", ("веревоч", "верёвоч", "канат", "rope")),
        ("activity_park", ("активити", "парк", "развлеч", "батут", "квест")),
        ("gas_station", ("азс", "заправ", "топлив")),
        ("car_wash", ("автомой", "мойка")),
        ("car_service", ("автосервис", "сто", "ремонт авто", "шиномонтаж", "детейлинг")),
        ("cafe", ("кафе", "кофе", "ресторан", "пекар", "кондитер", "еда")),
        ("photo_studio", ("фото", "фотостуд", "видеостуд")),
        ("flower_shop", ("цвет", "букет", "флорист")),
        ("medical_center", ("медицин", "клиник", "врач", "анализ", "лаборатор")),
        ("pet_clinic", ("ветерин", "зоомаг", "грум", "питом")),
    ]
    for business_type, tokens in rules:
        if any(token in text for token in tokens):
            return business_type
    return "unknown_local_business"


def _business_type_label(business_type: str) -> str:
    labels = {
        "dentistry": "стоматология",
        "cosmetology": "косметология",
        "hair_salon": "салон стрижек",
        "nail_salon": "маникюрный салон",
        "beauty_salon": "салон красоты",
        "dance_school": "школа танцев",
        "theatre_studio": "театральная студия",
        "swimming_pool": "бассейн",
        "kids_center": "детский центр",
        "sports_section": "спортивная секция",
        "fitness": "фитнес",
        "cultural_center": "культурный центр",
        "rope_park": "верёвочный городок",
        "activity_park": "активити-парк",
        "gas_station": "АЗС",
        "car_wash": "автомойка",
        "car_service": "автосервис",
        "cafe": "кафе",
        "photo_studio": "фотостудия",
        "flower_shop": "цветочный магазин",
        "medical_center": "медицинский центр",
        "pet_clinic": "зоонаправление",
    }
    return labels.get(str(business_type or "").strip(), "локальный бизнес")


def _build_pair_pattern_payload(
    *,
    our_business_type: str,
    partner_business_type: str,
    client_segment: str,
) -> dict[str, Any]:
    pair = (our_business_type, partner_business_type)
    adult_beauty_types = {"beauty_salon", "cosmetology", "hair_salon", "nail_salon"}
    shared_audience = client_segment
    partner_value = "ваши услуги"
    why = "оба бизнеса работают с клиентами, которым важны удобство и качественный локальный сервис"
    risks = "не обещать результат за партнёра и не звучать как медицинская или финансовая рекомендация"

    if our_business_type in adult_beauty_types and partner_business_type == "dentistry":
        shared_audience = "жители района"
        partner_value = "чистка зубов у партнёра и посещение косметолога у нас"
        why = "клиентам удобно закрыть две задачи по внешнему виду рядом с домом"
    elif our_business_type in adult_beauty_types and partner_business_type in adult_beauty_types:
        shared_audience = "люди, которые регулярно занимаются собой"
        if partner_business_type == "nail_salon":
            partner_value = "маникюр у партнёра и посещение косметолога у нас"
        elif partner_business_type == "hair_salon":
            partner_value = "услуга в салоне стрижек у партнёра и посещение косметолога у нас"
        else:
            partner_value = "взаимодополняющие beauty-услуги рядом"
        why = "уходовые и beauty-услуги часто покупают в связке перед отпуском, событием или началом сезона"
    elif partner_business_type in {"dance_school", "theatre_studio", "kids_center", "sports_section", "swimming_pool"}:
        if our_business_type in adult_beauty_types:
            shared_audience = "семьи из района"
            partner_value = "занятия для ребёнка у партнёра и посещение косметолога у нас для родителей"
            why = "родителям удобно совмещать детские занятия и свои регулярные услуги рядом"
        else:
            shared_audience = "семей с детьми, которым важен аккуратный внешний вид ребёнка перед занятиями и событиями"
            partner_value = "быстрая подготовка образа ребёнка перед выступлением, фотоднём или новым сезоном занятий"
            why = "детские занятия регулярно создают поводы, когда ребёнку нужно выглядеть аккуратно"
    elif partner_business_type in {"fitness", "sports_section"}:
        if our_business_type in adult_beauty_types:
            shared_audience = "люди, которые занимаются собой"
            partner_value = "тренировки у партнёра и посещение косметолога у нас"
            why = "клиенты фитнеса часто покупают уход как часть общего режима заботы о себе"
        else:
            shared_audience = "людей, которые следят за внешностью, здоровьем и регулярным уходом"
            partner_value = "уход, стрижка или восстановление после тренировок и активного графика"
            why = "после спорта клиенты часто думают о внешнем виде, восстановлении и регулярном уходе"
    elif partner_business_type in {"cafe", "cultural_center", "activity_park", "rope_park"}:
        shared_audience = "жителей района и семей, которые выбирают локальные места для отдыха и повседневных дел"
        partner_value = "удобный сервис рядом до или после визита к вам"
        why = "локальные маршруты помогают клиентам решать несколько задач рядом"
    elif partner_business_type in {"gas_station", "car_wash", "car_service"}:
        shared_audience = "жителей района и владельцев автомобилей"
        partner_value = "сервисы рядом, которые удобно совместить с регулярными поездками"
        why = "у таких клиентов есть повторяющиеся маршруты и привычка выбирать удобные точки поблизости"

    return {
        "our_business_type": our_business_type,
        "partner_business_type": partner_business_type,
        "shared_audience": shared_audience,
        "partner_value": partner_value,
        "why_it_makes_sense": why,
        "risk_notes": risks,
        "confidence": 0.72 if partner_business_type != "unknown_local_business" else 0.35,
    }


def _build_package_idea_payload(
    *,
    our_business_type: str,
    partner_business_type: str,
    business_name: str,
    lead: dict[str, Any],
) -> dict[str, Any]:
    partner_label = _business_type_label(partner_business_type)
    our_label = _business_type_label(our_business_type)
    adult_beauty_types = {"beauty_salon", "cosmetology", "hair_salon", "nail_salon"}
    idea = {
        "package_type": "joint_package",
        "name": "Удобный локальный пакет",
        "our_part": f"услуга от {business_name}",
        "partner_part": f"услуга партнёра из направления «{partner_label}»",
        "audience": "клиенты, которым удобно решить две связанные задачи рядом",
        "occasion": "регулярный визит или подготовка к важному дню",
        "launch_mechanic": "тест на небольшой группе клиентов в течение 2-3 недель",
    }
    if our_business_type in adult_beauty_types and partner_business_type == "dentistry":
        idea.update(
            {
                "name": "Улыбка и уход за лицом",
                "our_part": "посещение косметолога",
                "partner_part": "чистка зубов у партнёра",
                "audience": "жители района, которым удобно закрыть несколько задач по внешнему виду рядом с домом",
                "occasion": "праздник, фотосессия, отпуск, важная встреча или регулярный уход",
            }
        )
    elif our_business_type in adult_beauty_types and partner_business_type == "nail_salon":
        idea.update(
            {
                "name": "Комплексный уход рядом",
                "our_part": "посещение косметолога",
                "partner_part": "маникюр или педикюр у партнёра",
                "audience": "люди, которые регулярно занимаются собой",
                "occasion": "отпуск, праздник, фотосессия, свидание или начало сезона",
            }
        )
    elif our_business_type in adult_beauty_types and partner_business_type in {"beauty_salon", "cosmetology", "hair_salon"}:
        idea.update(
            {
                "name": "Комплексный beauty-маршрут",
                "our_part": "посещение косметолога",
                "partner_part": f"услуга партнёра из направления «{partner_label}»",
                "audience": "люди, которые регулярно занимаются собой",
                "occasion": "отпуск, праздник, фотосессия, важная встреча или регулярный уход",
            }
        )
    elif our_business_type in adult_beauty_types and partner_business_type in {"fitness", "sports_section"}:
        idea.update(
            {
                "name": "Форма и уход",
                "our_part": "посещение косметолога",
                "partner_part": "тренировка, абонемент или спортивное питание у партнёра",
                "audience": "люди, которые занимаются собой",
                "occasion": "начало сезона, подготовка к отпуску или регулярный уход после активного графика",
            }
        )
    elif partner_business_type == "dentistry":
        idea.update(
            {
                "name": "Образ к важному событию",
                "our_part": "стрижка, укладка или уход за внешним видом",
                "partner_part": "чистка зубов, профилактический уход или консультация по эстетике улыбки",
                "audience": "клиенты, которые готовятся к событию и хотят выглядеть ухоженно",
                "occasion": "свадьба, фотосессия, выпускной, отпуск или важная встреча",
            }
        )
    elif our_business_type in adult_beauty_types and partner_business_type in {"dance_school", "theatre_studio", "kids_center", "sports_section", "swimming_pool"}:
        idea.update(
            {
                "package_type": "family_local_package",
                "name": "Пока ребёнок на занятии",
                "our_part": "посещение косметолога для родителей",
                "partner_part": f"занятие или визит в {str(lead.get('name') or partner_label).strip()}",
                "audience": "семьи из района",
                "occasion": "регулярные занятия ребёнка, выходной или семейный визит рядом",
                "launch_mechanic": "тест на небольшой группе родителей с обменом сертификатами или специальным предложением",
            }
        )
    elif partner_business_type in {"dance_school", "theatre_studio", "kids_center", "sports_section", "swimming_pool"}:
        idea.update(
            {
                "package_type": "event_package",
                "name": "Готовимся к выступлению",
                "our_part": "детская стрижка, аккуратная причёска или быстрая укладка",
                "partner_part": "группа детей перед концертом, отчётным занятием, соревнованием или фотоднём",
                "audience": "родители, которым важно, чтобы ребёнок выглядел аккуратно без лишней организации",
                "occasion": "выступление, фотодень, праздник, начало сезона или серия занятий на 3-4 месяца",
                "launch_mechanic": "тест на одной группе или одном мероприятии с предварительным сбором заявок от родителей",
            }
        )
    elif partner_business_type in {"fitness", "sports_section"}:
        idea.update(
            {
                "name": "Уход после активного графика",
                "our_part": "стрижка, уход или экспресс-приведение внешнего вида в порядок",
                "partner_part": "тренировки, абонемент или занятие у партнёра",
                "audience": "клиенты, которые регулярно занимаются спортом и следят за внешним видом",
                "occasion": "начало сезона, подготовка к отпуску или регулярный уход после тренировок",
            }
        )
    elif partner_business_type in {"cafe", "cultural_center", "activity_park", "rope_park"}:
        idea.update(
            {
                "package_type": "local_route",
                "name": "Маршрут рядом",
                "our_part": f"услуга в {business_name}",
                "partner_part": f"визит в {str(lead.get('name') or partner_label).strip()}",
                "audience": "семьи и жители района, которым удобно совместить уход, отдых и повседневные дела",
                "occasion": "выходной, детское мероприятие, локальный праздник или обычный визит рядом",
            }
        )
    elif partner_business_type in {"gas_station", "car_wash", "car_service"}:
        idea.update(
            {
                "package_type": "partner_bonus",
                "name": "Сервис рядом по пути",
                "our_part": f"услуга в {business_name}",
                "partner_part": f"услуга партнёра из направления «{partner_label}»",
                "audience": "жители района и владельцы автомобилей, которые регулярно ездят по одному маршруту",
                "occasion": "плановый визит, поездка по делам или регулярное обслуживание",
            }
        )
    return idea


def _pick_partnership_client_segment(
    *,
    business_profile: dict[str, Any],
    own_services: list[str],
    partner_category: str,
) -> str:
    category = str(
        business_profile.get("category")
        or business_profile.get("business_category")
        or business_profile.get("industry")
        or ""
    ).strip().lower()
    services_text = " ".join(own_services[:12]).lower()
    partner_category_text = str(partner_category or "").strip().lower()
    combined = " ".join([category, services_text, partner_category_text])

    if any(token in combined for token in ("дет", "реб", "сем", "школ", "садик")):
        return "семей с детьми и жителей района"
    if any(token in combined for token in ("авто", "машин", "шиномонтаж", "мойк", "детейл")):
        return "владельцев автомобилей и жителей района"
    if any(token in combined for token in ("салон", "красот", "космет", "парик", "маник", "барбер", "spa", "спа")):
        return "людей, которые регулярно занимаются собой"
    if any(token in combined for token in ("спорт", "фитнес", "йог", "танц", "массаж", "здоров")):
        return "людей, которые следят за здоровьем, внешностью и удобством сервисов рядом"
    if any(token in combined for token in ("кафе", "ресторан", "кофе", "еда", "пекар")):
        return "жителей района, которые часто выбирают локальные места для повседневных покупок и отдыха"
    return "жителей района и клиентов, которые уже пользуются нашими услугами"


def _build_partnership_first_note(
    *,
    business_name: str,
    lead: dict[str, Any],
    client_segment: str,
    our_business_type: str = "unknown_local_business",
    partner_business_type: str = "unknown_local_business",
    pair_pattern: dict[str, Any] | None = None,
    package_idea: dict[str, Any] | None = None,
) -> str:
    partner_name = str(lead.get("name") or "").strip()
    partner_text = partner_name or "вашей компании"
    adult_beauty_types = {"beauty_salon", "cosmetology", "hair_salon", "nail_salon"}
    pattern = pair_pattern if isinstance(pair_pattern, dict) else {}
    package = package_idea if isinstance(package_idea, dict) else {}
    shared_audience = str(pattern.get("shared_audience") or client_segment or "жители района").strip()
    our_part = str(package.get("our_part") or "").strip()
    partner_part = str(package.get("partner_part") or "").strip()
    occasion = str(package.get("occasion") or "").strip()

    concrete_offer = ""
    if our_business_type in adult_beauty_types and partner_business_type == "dentistry":
        concrete_offer = "Например, можно протестировать совместное предложение: чистка зубов у вас и посещение косметолога у нас."
    elif our_business_type in adult_beauty_types and partner_business_type == "nail_salon":
        concrete_offer = "Например, можно протестировать совместное предложение: маникюр у вас и посещение косметолога у нас."
    elif our_business_type in adult_beauty_types and partner_business_type in {"beauty_salon", "cosmetology", "hair_salon"}:
        concrete_offer = f"Например, можно протестировать совместное предложение: услуга в {partner_text} и посещение косметолога у нас."
    elif our_business_type in adult_beauty_types and partner_business_type in {"fitness", "sports_section"}:
        concrete_offer = f"Например, можно протестировать совместное предложение: занятие или покупка у вас и посещение косметолога у нас."
    elif our_business_type in adult_beauty_types and partner_business_type in {"dance_school", "theatre_studio", "kids_center", "swimming_pool"}:
        concrete_offer = "Например, можно протестировать совместное предложение для семей: занятие для ребёнка у вас и посещение косметолога у нас для родителей."
    elif our_part and partner_part:
        concrete_offer = f"Например, можно протестировать совместное предложение: {partner_part} и {our_part}."
    else:
        concrete_offer = "Например, можно протестировать совместное предложение для клиентов обеих компаний."

    if not occasion:
        occasion = "отпуском, праздником, фотосессией, важной встречей или регулярным уходом"

    lines = [
        "Здравствуйте!",
        f"Мы ваши соседи — {business_name}.",
        f"У нас общая аудитория — {shared_audience}.",
        concrete_offer,
        f"Такой формат особенно актуален перед {occasion}.",
        "Также можем обсудить обмен сертификатами или специальные предложения для клиентов обеих компаний.",
        "Если идея кажется интересной, давайте созвонимся на 10 минут и обсудим детали.",
    ]
    return "\n\n".join(lines).strip()


def _build_partnership_commercial_offer(
    *,
    business_name: str,
    lead: dict[str, Any],
    package_idea: dict[str, Any],
) -> str:
    partner_name = str(lead.get("name") or "").strip()
    greeting = "Здравствуйте!"
    if partner_name:
        greeting = f"Здравствуйте! Подготовили один простой вариант для {partner_name}."

    lines = [
        greeting,
        "Идея — протестировать небольшой пакет, который можно запустить без сложной интеграции.",
        f"Пакет: «{package_idea.get('name') or 'совместный формат'}».",
        f"С нашей стороны — {package_idea.get('our_part') or f'услуга в {business_name}'}.",
        f"С вашей стороны — {package_idea.get('partner_part') or 'услуга или аудитория партнёра'}.",
        f"Такой формат может быть интересен для аудитории: {package_idea.get('audience') or 'общие клиенты'}. Он решает понятную задачу: {package_idea.get('occasion') or 'удобно совместить связанные услуги'}.",
        f"Запуск можно сделать как {package_idea.get('launch_mechanic') or 'тест на небольшой группе клиентов в течение 2-3 недель'}.",
        "Если формат откликается, можем прислать короткую схему запуска и обсудить детали.",
    ]
    return "\n\n".join(lines).strip()


def _collect_business_service_names(cur, business_id: str) -> list[str]:
    cur.execute(
        """
        SELECT name
        FROM userservices
        WHERE business_id = %s
          AND (is_active IS TRUE OR is_active IS NULL)
          AND COALESCE(TRIM(name), '') <> ''
        ORDER BY updated_at DESC NULLS LAST, created_at DESC
        LIMIT 200
        """,
        (business_id,),
    )
    rows = cur.fetchall()
    result: list[str] = []
    for row in rows:
        if hasattr(row, "get"):
            value = row.get("name")
        else:
            value = row[0] if row else None
        text = str(value or "").strip()
        if text:
            result.append(text)
    return result


def _tokenize_match_text(text: str) -> set[str]:
    import re
    return {t.lower() for t in re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9]{4,}", str(text or ""))}


def _extract_partner_service_names_from_snapshot(snapshot: dict[str, Any]) -> list[str]:
    services_preview = snapshot.get("services_preview") if isinstance(snapshot, dict) else []
    if not isinstance(services_preview, list):
        return []
    names: list[str] = []
    for item in services_preview:
        if not isinstance(item, dict):
            continue
        current_name = str(item.get("current_name") or "").strip()
        if current_name:
            names.append(current_name)
    return names


def _normalize_match_result(
    raw_match: dict[str, Any] | None,
    *,
    own_services_count: int,
    partner_services_count: int,
) -> dict[str, Any]:
    """Normalize match payload and enrich it with reason-codes + human-readable explanation."""
    data = raw_match if isinstance(raw_match, dict) else {}

    overlap = data.get("overlap")
    if not isinstance(overlap, list):
        overlap = []
    overlap = [str(x).strip() for x in overlap if str(x).strip()]

    complement_raw = data.get("complement")
    if not isinstance(complement_raw, dict):
        complement_raw = {}
    our_strength = complement_raw.get("our_strength_tokens")
    partner_strength = complement_raw.get("partner_strength_tokens")
    if not isinstance(our_strength, list):
        our_strength = []
    if not isinstance(partner_strength, list):
        partner_strength = []
    our_strength = [str(x).strip() for x in our_strength if str(x).strip()]
    partner_strength = [str(x).strip() for x in partner_strength if str(x).strip()]

    try:
        score = int(round(float(data.get("match_score") or 0)))
    except Exception:
        score = 0
    score = max(0, min(100, score))

    reason_codes: list[str] = []
    if own_services_count <= 0:
        reason_codes.append("NO_OUR_SERVICES")
    if partner_services_count <= 0:
        reason_codes.append("NO_PARTNER_SERVICES")
    if own_services_count < 3 or partner_services_count < 3:
        reason_codes.append("LOW_SIGNAL_DATA")
    if overlap:
        reason_codes.append("HAS_OVERLAP")
    else:
        reason_codes.append("NO_DIRECT_OVERLAP")
    if partner_strength:
        reason_codes.append("HAS_COMPLEMENT")

    if score >= 70:
        reason_codes.append("STRONG_MATCH")
    elif score >= 40:
        reason_codes.append("MEDIUM_MATCH")
    else:
        reason_codes.append("LOW_MATCH")

    explanation_parts = []
    explanation_parts.append(
        f"Сопоставлено услуг: ваши {own_services_count}, партнёра {partner_services_count}."
    )
    if overlap:
        explanation_parts.append(f"Прямые пересечения: {', '.join(overlap[:5])}.")
    else:
        explanation_parts.append("Прямых пересечений по названиям услуг почти нет.")
    if partner_strength:
        explanation_parts.append(
            f"Комплементарные направления у партнёра: {', '.join(partner_strength[:5])}."
        )
    explanation_parts.append(
        f"Итоговый score {score}% рассчитан по балансу пересечений и комплементарности."
    )

    risks = data.get("risks")
    if not isinstance(risks, list):
        risks = []
    risks = [str(x).strip() for x in risks if str(x).strip()]

    offer_angles = data.get("offer_angles")
    if not isinstance(offer_angles, list):
        offer_angles = []
    offer_angles = [str(x).strip() for x in offer_angles if str(x).strip()]

    normalized = {
        "match_score": score,
        "overlap": overlap[:30],
        "complement": {
            "our_strength_tokens": our_strength[:30],
            "partner_strength_tokens": partner_strength[:30],
        },
        "risks": risks[:10],
        "offer_angles": offer_angles[:10],
        "source_counts": {
            "our_services": own_services_count,
            "partner_services": partner_services_count,
        },
        "reason_codes": reason_codes,
        "score_explanation": " ".join(explanation_parts).strip(),
    }
    return normalized


def _extract_openclaw_result_blob(resp: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(resp, dict):
        return {}
    data = resp.get("data")
    if not isinstance(data, dict):
        return {}
    result = data.get("result")
    if isinstance(result, dict):
        return result
    return data


def _normalize_enriched_contact_fields(payload: dict[str, Any] | None) -> dict[str, Any]:
    data = payload if isinstance(payload, dict) else {}
    phone = str(data.get("phone") or data.get("phone_e164") or "").strip() or None
    email = str(data.get("email") or "").strip() or None
    website = str(data.get("website") or data.get("website_url") or "").strip() or None
    telegram_url = str(data.get("telegram_url") or data.get("telegram") or "").strip() or None
    whatsapp_url = str(data.get("whatsapp_url") or data.get("whatsapp") or "").strip() or None
    return {
        "phone": phone,
        "email": email,
        "website": website,
        "telegram_url": telegram_url,
        "whatsapp_url": whatsapp_url,
    }


def _normalize_enrich_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    data = payload if isinstance(payload, dict) else {}
    confidence_raw = data.get("confidence")
    confidence: dict[str, float] = {}
    if isinstance(confidence_raw, dict):
        for key, value in confidence_raw.items():
            try:
                confidence[str(key)] = max(0.0, min(1.0, float(value)))
            except Exception:
                continue
    found_fields_raw = data.get("found_fields")
    found_fields = []
    if isinstance(found_fields_raw, list):
        found_fields = [str(item).strip() for item in found_fields_raw if str(item or "").strip()]
    provider = str(data.get("provider") or data.get("source_provider") or "").strip() or None
    normalized_contacts = _normalize_enriched_contact_fields(data)
    return {
        "provider": provider,
        "found_fields": found_fields,
        "confidence": confidence,
        "contacts": normalized_contacts,
        "raw": data,
    }


def _partnership_next_best_action(lead: dict[str, Any]) -> dict[str, Any]:
    stage = str(lead.get("partnership_stage") or "imported").strip().lower()
    status = str(lead.get("status") or "").strip().lower()
    parse_status = str(lead.get("parse_status") or "").strip().lower()
    has_contacts = any(
        str(lead.get(key) or "").strip()
        for key in ("phone", "email", "telegram_url", "whatsapp_url", "website")
    )
    has_channel = bool(str(lead.get("selected_channel") or "").strip())

    if parse_status == "captcha":
        return {
            "code": "resolve_captcha",
            "label": "Пройти CAPTCHA",
            "hint": "Парсинг остановился и ждёт human-in-the-loop.",
            "priority": "high",
        }
    if parse_status == "error":
        return {
            "code": "inspect_parse_error",
            "label": "Разобрать ошибку парсинга",
            "hint": "Без исправления парсинга аудит и матчинг будут неполными.",
            "priority": "high",
        }
    if parse_status in {"pending", "processing"}:
        return {
            "code": "wait_parse",
            "label": "Дождаться завершения парсинга",
            "hint": "Пока парсинг не завершён, данные по карточке ещё не полные.",
            "priority": "medium",
        }
    if parse_status in {"completed", "done"} and stage == "imported":
        return {
            "code": "run_audit",
            "label": "Запустить аудит",
            "hint": "Парсинг завершён, можно переходить к аудиту карточки.",
            "priority": "high",
        }
    if stage == "imported":
        return {
            "code": "run_parse",
            "label": "Запустить парсинг карточки",
            "hint": "Сначала нужно подтянуть реальные услуги, отзывы и контакты.",
            "priority": "high",
        }
    if stage == "audited":
        return {
            "code": "run_match",
            "label": "Запустить матчинг услуг",
            "hint": "После аудита нужно проверить комплементарность и пересечения.",
            "priority": "high",
        }
    if stage == "matched":
        return {
            "code": "draft_offer",
            "label": "Сгенерировать первое письмо",
            "hint": "Матчинг уже готов, можно переходить к офферу.",
            "priority": "high",
        }
    if stage in {"proposal_draft_ready"} or status == DRAFT_GENERATED:
        return {
            "code": "approve_draft",
            "label": "Утвердить черновик",
            "hint": "Черновик уже готов и ждёт вашего решения.",
            "priority": "high",
        }
    if stage in {"selected_for_outreach"} and not has_channel:
        return {
            "code": "choose_channel",
            "label": "Выбрать канал отправки",
            "hint": "Перед очередью нужно закрепить канал для первого контакта.",
            "priority": "medium",
        }
    if stage in {"channel_selected"} and not has_contacts:
        return {
            "code": "fill_contacts",
            "label": "Заполнить контакты",
            "hint": "Канал выбран, но контактов для отправки пока недостаточно.",
            "priority": "high",
        }
    if stage in {"channel_selected", "proposal_approved", "approved_for_send"}:
        return {
            "code": "queue_for_send",
            "label": "Добавить в batch",
            "hint": "Лид готов к постановке в очередь отправки.",
            "priority": "medium",
        }
    if stage == "queued_for_send":
        return {
            "code": "approve_batch",
            "label": "Утвердить batch или дождаться отправки",
            "hint": "Лид уже в очереди, следующий шаг — подтверждение или dispatch.",
            "priority": "medium",
        }
    if stage == "sent":
        return {
            "code": "record_outcome",
            "label": "Зафиксировать outcome",
            "hint": "После отправки важно сохранить реакцию: positive/question/no_response/hard_no.",
            "priority": "medium",
        }
    return {
        "code": "review_lead",
        "label": "Проверить лид вручную",
        "hint": "Для этого лида нужен ручной операторский просмотр перед следующим шагом.",
        "priority": "low",
    }


def _compute_partnership_match_result(
    cur,
    *,
    business_id: str,
    lead_id: str,
    audit_json: dict[str, Any],
) -> dict[str, Any]:
    own_services = _collect_business_service_names(cur, business_id)
    partner_services = _extract_partner_service_names_from_snapshot(audit_json)
    match_result: dict[str, Any] | None = None

    if _is_partnership_openclaw_enabled():
        openclaw_result = _call_partnership_openclaw_capability(
            "partners.match_services",
            tenant_id=business_id,
            payload={
                "business_id": business_id,
                "lead_id": lead_id,
                "intent": "partnership_outreach",
                "our_services": own_services,
                "partner_services": partner_services,
                "audit_snapshot": audit_json,
            },
            timeout_sec=40,
        )
        if openclaw_result.get("success"):
            result_blob = _extract_openclaw_result_blob(openclaw_result)
            candidate_match = result_blob.get("match")
            if isinstance(candidate_match, dict) and candidate_match:
                match_result = candidate_match

    if not match_result:
        own_tokens = _tokenize_match_text(" ".join(own_services))
        partner_tokens = _tokenize_match_text(" ".join(partner_services))
        overlap_tokens = sorted(list(own_tokens & partner_tokens))
        own_unique = sorted(list(own_tokens - partner_tokens))
        partner_unique = sorted(list(partner_tokens - own_tokens))

        denominator = max(1, len(own_tokens | partner_tokens))
        score = int(round((len(overlap_tokens) / denominator) * 100))
        match_result = {
            "match_score": score,
            "overlap": overlap_tokens[:30],
            "complement": {
                "our_strength_tokens": own_unique[:30],
                "partner_strength_tokens": partner_unique[:30],
            },
            "risks": [
                "Низкая точность, если у партнёра мало структурированных услуг."
                if not partner_services
                else "Проверьте каннибализацию по пересекающимся услугам."
            ],
            "offer_angles": [
                "Кросс-рекомендации по непересекающимся услугам",
                "Пакетные предложения с взаимной скидкой",
                "Совместный контент/новости для карт и соцсетей",
            ],
            "source_counts": {
                "our_services": len(own_services),
                "partner_services": len(partner_services),
            },
        }

    return _normalize_match_result(
        match_result,
        own_services_count=len(own_services),
        partner_services_count=len(partner_services),
    )


@admin_prospecting_bp.route("/api/partnership/leads/<string:lead_id>/audit", methods=["POST"])
def partnership_audit_lead(lead_id):
    user_data, error = _require_auth()
    if error:
        return error
    try:
        data = request.get_json(silent=True) or {}
        requested_business_id = str(data.get("business_id") or "").strip() or None
        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            _ensure_partnership_artifacts_table(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
            lead = _load_partnership_lead(cur, lead_id=lead_id, business_id=business_id)
            if not lead:
                return jsonify({"error": "Lead not found"}), 404

            snapshot: dict[str, Any] | None = None
            if _is_partnership_openclaw_enabled():
                openclaw_result = _call_partnership_openclaw_capability(
                    "partners.audit_card",
                    tenant_id=business_id,
                    payload={
                        "business_id": business_id,
                        "lead_id": lead_id,
                        "lead": lead,
                        "intent": "partnership_outreach",
                    },
                    timeout_sec=40,
                )
                if openclaw_result.get("success"):
                    result_blob = _extract_openclaw_result_blob(openclaw_result)
                    candidate_snapshot = result_blob.get("snapshot")
                    if isinstance(candidate_snapshot, dict) and candidate_snapshot:
                        snapshot = candidate_snapshot
            if not snapshot:
                snapshot = build_lead_card_preview_snapshot(lead)
            snapshot = _to_json_compatible(snapshot)
            cur.execute(
                """
                INSERT INTO partnershipleadartifacts (lead_id, audit_json, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (lead_id) DO UPDATE
                SET audit_json = EXCLUDED.audit_json,
                    updated_at = NOW()
                """,
                (lead_id, Json(snapshot)),
            )
            cur.execute(
                """
                UPDATE prospectingleads
                SET partnership_stage = %s,
                    status = %s,
                    updated_at = NOW()
                WHERE id = %s
                """,
                ("audited", "audited", lead_id),
            )
            conn.commit()
        finally:
            conn.close()
        return jsonify({"success": True, "snapshot": snapshot})
    except Exception as e:
        print(f"Error partnership audit lead: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/partnership/leads/<string:lead_id>/match", methods=["POST"])
def partnership_match_lead(lead_id):
    user_data, error = _require_auth()
    if error:
        return error
    try:
        data = request.get_json(silent=True) or {}
        requested_business_id = str(data.get("business_id") or "").strip() or None
        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            _ensure_partnership_artifacts_table(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
            lead = _load_partnership_lead(cur, lead_id=lead_id, business_id=business_id)
            if not lead:
                return jsonify({"error": "Lead not found"}), 404

            cur.execute("SELECT audit_json FROM partnershipleadartifacts WHERE lead_id = %s", (lead_id,))
            artifact_row = cur.fetchone()
            audit_json = {}
            if artifact_row:
                audit_json = artifact_row["audit_json"] if hasattr(artifact_row, "get") else artifact_row[0]
            if not isinstance(audit_json, dict) or not audit_json:
                audit_json = build_lead_card_preview_snapshot(lead)
            audit_json = _to_json_compatible(audit_json)
            match_result = _compute_partnership_match_result(
                cur,
                business_id=business_id,
                lead_id=lead_id,
                audit_json=audit_json,
            )

            cur.execute(
                """
                INSERT INTO partnershipleadartifacts (lead_id, audit_json, match_json, updated_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (lead_id) DO UPDATE
                SET audit_json = EXCLUDED.audit_json,
                    match_json = EXCLUDED.match_json,
                    updated_at = NOW()
                """,
                (lead_id, Json(audit_json), Json(match_result)),
            )
            cur.execute(
                """
                UPDATE prospectingleads
                SET partnership_stage = %s,
                    status = %s,
                    updated_at = NOW()
                WHERE id = %s
                """,
                ("matched", "matched", lead_id),
            )
            conn.commit()
        finally:
            conn.close()
        return jsonify({"success": True, "result": match_result})
    except Exception as e:
        print(f"Error partnership match lead: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/partnership/leads/bulk-match", methods=["POST"])
def partnership_bulk_match_leads():
    """Bulk match for selected partnership leads."""
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
            _ensure_partnership_artifacts_table(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403

            matched_count = 0
            skipped_count = 0
            results: list[dict[str, Any]] = []
            errors: list[dict[str, Any]] = []

            for lead_id in normalized_ids:
                lead = _load_partnership_lead(cur, lead_id=lead_id, business_id=business_id)
                if not lead:
                    skipped_count += 1
                    errors.append({"lead_id": lead_id, "error": "Lead not found"})
                    continue

                cur.execute("SELECT audit_json FROM partnershipleadartifacts WHERE lead_id = %s", (lead_id,))
                artifact_row = cur.fetchone()
                audit_json = {}
                if artifact_row:
                    audit_json = artifact_row["audit_json"] if hasattr(artifact_row, "get") else artifact_row[0]
                if not isinstance(audit_json, dict) or not audit_json:
                    audit_json = build_lead_card_preview_snapshot(lead)
                audit_json = _to_json_compatible(audit_json)

                try:
                    match_result = _compute_partnership_match_result(
                        cur,
                        business_id=business_id,
                        lead_id=lead_id,
                        audit_json=audit_json,
                    )
                    cur.execute(
                        """
                        INSERT INTO partnershipleadartifacts (lead_id, audit_json, match_json, updated_at)
                        VALUES (%s, %s, %s, NOW())
                        ON CONFLICT (lead_id) DO UPDATE
                        SET audit_json = EXCLUDED.audit_json,
                            match_json = EXCLUDED.match_json,
                            updated_at = NOW()
                        """,
                        (lead_id, Json(audit_json), Json(match_result)),
                    )
                    cur.execute(
                        """
                        UPDATE prospectingleads
                        SET partnership_stage = %s,
                            status = %s,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        ("matched", "matched", lead_id),
                    )
                    matched_count += 1
                    results.append(
                        {
                            "lead_id": lead_id,
                            "match_score": match_result.get("match_score"),
                            "reason_codes": match_result.get("reason_codes"),
                        }
                    )
                except Exception as lead_exc:
                    skipped_count += 1
                    errors.append({"lead_id": lead_id, "error": str(lead_exc)})

            conn.commit()
            return jsonify(
                {
                    "success": True,
                    "matched_count": matched_count,
                    "skipped_count": skipped_count,
                    "results": results,
                    "errors": errors,
                }
            )
        finally:
            conn.close()
    except Exception as e:
        print(f"Error partnership bulk match leads: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/partnership/leads/<string:lead_id>/offer-page", methods=["POST"])
def partnership_generate_offer_page(lead_id):
    user_data, error = _require_auth()
    if error:
        return error
    try:
        data = request.get_json(silent=True) or {}
        requested_business_id = str(data.get("business_id") or "").strip() or None
        requested_language = str(data.get("primary_language") or data.get("language") or "en").strip().lower() or "en"
        primary_language, enabled_languages = _normalize_public_audit_languages(requested_language, data.get("enabled_languages"))
        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            _ensure_partnership_artifacts_table(conn)
            _ensure_partnership_public_offers_table(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
            lead = _load_partnership_lead(cur, lead_id=lead_id, business_id=business_id)
            if not lead:
                return jsonify({"error": "Lead not found"}), 404

            cur.execute(
                """
                SELECT audit_json, match_json, offer_draft_json
                FROM partnershipleadartifacts
                WHERE lead_id = %s
                """,
                (lead_id,),
            )
            artifact = cur.fetchone()
            artifact_dict = dict(artifact) if artifact and hasattr(artifact, "keys") else {}
            audit_json = artifact_dict.get("audit_json") if isinstance(artifact_dict.get("audit_json"), dict) else {}
            match_json = artifact_dict.get("match_json") if isinstance(artifact_dict.get("match_json"), dict) else {}
            offer_draft_json = artifact_dict.get("offer_draft_json") if isinstance(artifact_dict.get("offer_draft_json"), dict) else {}

            if not audit_json:
                audit_json = build_lead_card_preview_snapshot(lead)

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
                    FROM partnershippublicoffers
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

            page_json = _to_json_compatible(_build_partnership_offer_payload(
                lead=lead,
                audit_json=audit_json,
                match_json=match_json,
                offer_draft_json=offer_draft_json,
                preferred_language=primary_language,
                enabled_languages=enabled_languages,
            ))
            cur.execute(
                """
                INSERT INTO partnershippublicoffers (
                    lead_id, business_id, slug, page_json, is_active, created_by, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, TRUE, %s, NOW(), NOW())
                ON CONFLICT (lead_id) DO UPDATE
                SET slug = EXCLUDED.slug,
                    page_json = EXCLUDED.page_json,
                    is_active = TRUE,
                    updated_at = NOW()
                """,
                (lead_id, business_id, slug, Json(page_json), user_data.get("user_id")),
            )
            conn.commit()
        finally:
            conn.close()

        return jsonify(
            {
                "success": True,
                "slug": slug,
                "public_url": _append_public_offer_language(_make_public_offer_url(slug), primary_language),
                "page": page_json,
            }
        )
    except Exception as e:
        print(f"Error partnership generate offer page: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/partnership/public/offer/<string:slug>", methods=["GET"])
def partnership_public_offer_page(slug):
    try:
        normalized_slug = _slugify_company_name(slug)
        conn = get_db_connection()
        try:
            _ensure_partnership_public_offers_table(conn)
            _ensure_admin_prospecting_public_offers_table(conn)
            cur = conn.cursor()
            cur.execute(
                """
                SELECT slug, page_json, updated_at
                FROM partnershippublicoffers
                WHERE slug = %s
                  AND is_active = TRUE
                LIMIT 1
                """,
                (normalized_slug,),
            )
            row = cur.fetchone()
            if not row:
                cur.execute(
                    """
                    SELECT slug, page_json, generated_json, published_json, updated_at
                    FROM adminprospectingleadpublicoffers
                    WHERE slug = %s
                      AND is_active = TRUE
                    LIMIT 1
                    """,
                    (normalized_slug,),
                )
                row = cur.fetchone()
            if not row:
                return jsonify({"error": "Offer page not found"}), 404
            row_dict = dict(row) if row and hasattr(row, "keys") else {}
            page_json = _resolve_admin_public_offer_row_page_json(row_dict) if row_dict else (
                row.get("page_json") if hasattr(row, "get") else (row[1] if isinstance(row, (list, tuple)) and len(row) > 1 else {})
            )
            updated_at = row.get("updated_at") if hasattr(row, "get") else (row[2] if isinstance(row, (list, tuple)) and len(row) > 2 else None)
            payload = _to_json_compatible(page_json) if isinstance(page_json, dict) else {}
            payload["slug"] = normalized_slug
            payload["public_url"] = _make_public_offer_url(normalized_slug)
            payload["updated_at"] = updated_at.isoformat() if hasattr(updated_at, "isoformat") else payload.get("updated_at")
            return jsonify({"success": True, "page": payload})
        finally:
            conn.close()
    except Exception as e:
        print(f"Error loading partnership public offer page: {e}")
        return jsonify({"error": str(e)}), 500


















@admin_prospecting_bp.route("/api/partnership/leads/<string:lead_id>/enrich-contacts", methods=["POST"])
def partnership_enrich_lead_contacts(lead_id):
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
            lead = _load_partnership_lead(cur, lead_id=lead_id, business_id=business_id)
            if not lead:
                return jsonify({"error": "Lead not found"}), 404

            lead_payload = {
                "lead_id": lead_id,
                "name": lead.get("name"),
                "source_url": lead.get("source_url"),
                "phone": lead.get("phone"),
                "email": lead.get("email"),
                "website": lead.get("website"),
                "telegram_url": lead.get("telegram_url"),
                "whatsapp_url": lead.get("whatsapp_url"),
            }

            enriched_source: dict[str, Any] = {}
            if _is_partnership_openclaw_enabled():
                openclaw_result = _call_partnership_openclaw_capability(
                    "partners.enrich_contacts",
                    tenant_id=business_id,
                    payload={"lead": lead_payload, "intent": "partnership_outreach", "business_id": business_id},
                    timeout_sec=60,
                )
                if not openclaw_result.get("success"):
                    return jsonify({"error": str(openclaw_result.get("error") or "OpenClaw contact enrich failed")}), 502
                enriched_source = _extract_openclaw_result_blob(openclaw_result) or {}
            else:
                enriched_source = lead_payload

            normalized = _normalize_enriched_contact_fields(enriched_source)
            enrich_payload = _normalize_enrich_payload(enriched_source)
            cur.execute(
                """
                UPDATE prospectingleads
                SET
                    phone = COALESCE(%s, phone),
                    email = COALESCE(%s, email),
                    website = COALESCE(%s, website),
                    telegram_url = COALESCE(%s, telegram_url),
                    whatsapp_url = COALESCE(%s, whatsapp_url),
                    enrich_payload_json = %s,
                    updated_at = NOW()
                WHERE id = %s
                  AND business_id = %s
                  AND COALESCE(intent, 'client_outreach') = 'partnership_outreach'
                RETURNING id, name, phone, email, website, telegram_url, whatsapp_url, enrich_payload_json, updated_at
                """,
                (
                    normalized.get("phone"),
                    normalized.get("email"),
                    normalized.get("website"),
                    normalized.get("telegram_url"),
                    normalized.get("whatsapp_url"),
                    Json(enrich_payload),
                    lead_id,
                    business_id,
                ),
            )
            updated = cur.fetchone()
            conn.commit()
        finally:
            conn.close()

        return jsonify(
            {
                "success": True,
                "lead": dict(updated) if updated and hasattr(updated, "keys") else {},
                "enriched": normalized,
                "enrich_payload": enrich_payload,
            }
        )
    except Exception as e:
        print(f"Error partnership enrich contacts: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/partnership/leads/bulk-enrich-contacts", methods=["POST"])
def partnership_bulk_enrich_contacts():
    user_data, error = _require_auth()
    if error:
        return error
    try:
        data = request.get_json(silent=True) or {}
        requested_business_id = str(data.get("business_id") or "").strip() or None
        lead_ids = data.get("lead_ids") or []
        if not isinstance(lead_ids, list) or not lead_ids:
            return jsonify({"error": "lead_ids array is required"}), 400
        normalized_ids = [str(item).strip() for item in lead_ids if str(item or "").strip()]
        if not normalized_ids:
            return jsonify({"error": "lead_ids array is required"}), 400

        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403

            cur.execute(
                """
                SELECT *
                FROM prospectingleads
                WHERE business_id = %s
                  AND id = ANY(%s)
                  AND COALESCE(intent, 'client_outreach') = 'partnership_outreach'
                ORDER BY updated_at DESC NULLS LAST, created_at DESC
                """,
                (business_id, normalized_ids),
            )
            rows = [dict(row) for row in (cur.fetchall() or [])]
            if not rows:
                return jsonify({"error": "Leads not found"}), 404

            updated_ids: list[str] = []
            skipped_ids: list[str] = []
            errors: list[dict[str, Any]] = []

            for lead in rows:
                lead_id = str(lead.get("id") or "").strip()
                lead_payload = {
                    "lead_id": lead_id,
                    "name": lead.get("name"),
                    "source_url": lead.get("source_url"),
                    "phone": lead.get("phone"),
                    "email": lead.get("email"),
                    "website": lead.get("website"),
                    "telegram_url": lead.get("telegram_url"),
                    "whatsapp_url": lead.get("whatsapp_url"),
                }
                try:
                    if _is_partnership_openclaw_enabled():
                        openclaw_result = _call_partnership_openclaw_capability(
                            "partners.enrich_contacts",
                            tenant_id=business_id,
                            payload={"lead": lead_payload, "intent": "partnership_outreach", "business_id": business_id},
                            timeout_sec=60,
                        )
                        if not openclaw_result.get("success"):
                            raise RuntimeError(str(openclaw_result.get("error") or "OpenClaw contact enrich failed"))
                        enriched_source = _extract_openclaw_result_blob(openclaw_result) or {}
                    else:
                        enriched_source = lead_payload

                    normalized = _normalize_enriched_contact_fields(enriched_source)
                    enrich_payload = _normalize_enrich_payload(enriched_source)
                    if not any(normalized.values()):
                        skipped_ids.append(lead_id)
                        continue

                    cur.execute(
                        """
                        UPDATE prospectingleads
                        SET
                            phone = COALESCE(%s, phone),
                            email = COALESCE(%s, email),
                            website = COALESCE(%s, website),
                            telegram_url = COALESCE(%s, telegram_url),
                            whatsapp_url = COALESCE(%s, whatsapp_url),
                            enrich_payload_json = %s,
                            updated_at = NOW()
                        WHERE id = %s
                          AND business_id = %s
                          AND COALESCE(intent, 'client_outreach') = 'partnership_outreach'
                        """,
                        (
                            normalized.get("phone"),
                            normalized.get("email"),
                            normalized.get("website"),
                            normalized.get("telegram_url"),
                            normalized.get("whatsapp_url"),
                            Json(enrich_payload),
                            lead_id,
                            business_id,
                        ),
                    )
                    updated_ids.append(lead_id)
                except Exception as exc:
                    errors.append({"lead_id": lead_id, "error": str(exc)})

            conn.commit()
        finally:
            conn.close()

        return jsonify(
            {
                "success": True,
                "updated_count": len(updated_ids),
                "skipped_count": len(skipped_ids),
                "updated_ids": updated_ids,
                "skipped_ids": skipped_ids,
                "errors": errors[:50],
            }
        )
    except Exception as e:
        print(f"Error partnership bulk enrich contacts: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/partnership/leads/<string:lead_id>/draft-offer", methods=["POST"])
def partnership_draft_offer(lead_id):
    user_data, error = _require_auth()
    if error:
        return error
    try:
        data = request.get_json(silent=True) or {}
        requested_business_id = str(data.get("business_id") or "").strip() or None
        tone = str(data.get("tone") or "профессиональный").strip()
        channel = str(data.get("channel") or "telegram").strip().lower()
        letter_type = str(data.get("letter_type") or "first_note").strip().lower()
        if letter_type not in {"first_note", "commercial_offer"}:
            return jsonify({"error": "letter_type must be one of: first_note, commercial_offer"}), 400
        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            _ensure_partnership_artifacts_table(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
            lead = _load_partnership_lead(cur, lead_id=lead_id, business_id=business_id)
            if not lead:
                return jsonify({"error": "Lead not found"}), 404

            cur.execute("SELECT match_json FROM partnershipleadartifacts WHERE lead_id = %s", (lead_id,))
            row = cur.fetchone()
            match_json = row["match_json"] if row and hasattr(row, "get") else (row[0] if row else {})
            if not isinstance(match_json, dict):
                match_json = {}

            business_profile = _load_business_profile(cur, business_id)
            business_name = _pick_business_display_name(business_profile)
            own_services = _collect_business_service_names(cur, business_id)
            our_business_type = _classify_partnership_business_type(
                business_name,
                business_profile.get("category"),
                business_profile.get("business_category"),
                business_profile.get("industry"),
                " ".join(own_services[:20]),
            )
            partner_business_type = _classify_partnership_business_type(
                lead.get("name"),
                lead.get("category"),
                lead.get("source"),
                lead.get("search_payload_json"),
                lead.get("enrich_payload_json"),
            )
            client_segment = _pick_partnership_client_segment(
                business_profile=business_profile,
                own_services=own_services,
                partner_category=str(lead.get("category") or ""),
            )
            pair_pattern = _build_pair_pattern_payload(
                our_business_type=our_business_type,
                partner_business_type=partner_business_type,
                client_segment=client_segment,
            )
            package_idea = _build_package_idea_payload(
                our_business_type=our_business_type,
                partner_business_type=partner_business_type,
                business_name=business_name,
                lead=lead,
            )
            template_policy = {
                "goal": "get_reply_not_sell_partnership",
                "format": "short_note" if letter_type == "first_note" else "commercial_offer",
                "language": "ru",
                "max_sentences": 6 if letter_type == "first_note" else 9,
                "required_structure": [
                    "who_we_are",
                    "why_this_partner",
                    "which_our_clients_can_be_useful",
                    "simple_test",
                    "10_min_call_question",
                ],
                "avoid": [
                    "do not start with QR codes, certificates, promos, leaflets, mechanics",
                    "do not sell partnership as an abstract idea",
                    "do not write a long pitch",
                    "do not use universal empty wording without one personalized client segment",
                ],
                "preferred_wording": "У нас есть клиенты, которым потенциально могут быть полезны ваши услуги.",
                "business_name": business_name,
                "client_segment": client_segment,
                "letter_type": letter_type,
                "our_business_type": our_business_type,
                "partner_business_type": partner_business_type,
                "pair_pattern": pair_pattern,
                "package_idea": package_idea if letter_type == "commercial_offer" else None,
            }
            draft_text: str | None = None
            prompt_meta = {
                "prompt_key": "partners.draft_first_note" if letter_type == "first_note" else "partners.draft_commercial_offer",
                "prompt_version": "short_note_v2" if letter_type == "first_note" else "commercial_offer_v1",
                "prompt_source": "openclaw",
            }
            if _is_partnership_openclaw_enabled():
                openclaw_result = _call_partnership_openclaw_capability(
                    "partners.draft_first_offer" if letter_type == "first_note" else "partners.draft_commercial_offer",
                    tenant_id=business_id,
                    payload={
                        "business_id": business_id,
                        "lead_id": lead_id,
                        "intent": "partnership_outreach",
                        "lead": lead,
                        "match": match_json,
                        "tone": tone,
                        "channel": channel,
                        "business": {
                            "name": business_name,
                            "profile": business_profile,
                            "services": own_services[:30],
                        },
                        "letter_type": letter_type,
                        "pair_pattern": pair_pattern,
                        "package_idea": package_idea if letter_type == "commercial_offer" else None,
                        "template_policy": template_policy,
                    },
                    timeout_sec=40,
                )
                if openclaw_result.get("success"):
                    result_blob = _extract_openclaw_result_blob(openclaw_result)
                    candidate_text = str(result_blob.get("text") or result_blob.get("draft_text") or "").strip()
                    if candidate_text:
                        draft_text = candidate_text
                    prompt_meta = _normalize_prompt_meta(
                        result_blob,
                        fallback_key="partners.draft_first_note" if letter_type == "first_note" else "partners.draft_commercial_offer",
                        fallback_version="short_note_v2" if letter_type == "first_note" else "commercial_offer_v1",
                        fallback_source="openclaw",
                    )

            if not draft_text:
                if letter_type == "commercial_offer":
                    draft_text = _build_partnership_commercial_offer(
                        business_name=business_name,
                        lead=lead,
                        package_idea=package_idea,
                    )
                else:
                    draft_text = _build_partnership_first_note(
                        business_name=business_name,
                        lead=lead,
                        client_segment=client_segment,
                        our_business_type=our_business_type,
                        partner_business_type=partner_business_type,
                        pair_pattern=pair_pattern,
                        package_idea=package_idea,
                    )
                prompt_meta = {
                    "prompt_key": "partners.draft_first_note_fallback" if letter_type == "first_note" else "partners.draft_commercial_offer_fallback",
                    "prompt_version": "short_note_v2" if letter_type == "first_note" else "commercial_offer_v1",
                    "prompt_source": "local_fallback",
                }

            room_url = _load_latest_sales_room_url_for_lead(cur, lead_id)
            draft_text = _append_sales_room_link_to_outreach_text(draft_text, room_url)

            draft_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO outreachmessagedrafts (
                    id, lead_id, channel, angle_type, tone, status,
                    generated_text, edited_text, learning_note_json, created_by, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, NOW(), NOW()
                )
                """,
                (
                    draft_id,
                    lead_id,
                    channel,
                    "partnership_offer" if letter_type == "first_note" else "partnership_commercial_offer",
                    tone,
                    DRAFT_GENERATED,
                    draft_text,
                    draft_text,
                    Json(
                        {
                            "intent": "partnership_outreach",
                            "auto_generated": True,
                            "letter_type": letter_type,
                            "our_business_type": our_business_type,
                            "partner_business_type": partner_business_type,
                            "pair_pattern": pair_pattern,
                            "package_idea": package_idea if letter_type == "commercial_offer" else None,
                            "template_policy": template_policy,
                            **prompt_meta,
                        }
                    ),
                    user_data["user_id"],
                ),
            )
            cur.execute(
                """
                INSERT INTO partnershipleadartifacts (lead_id, offer_draft_json, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (lead_id) DO UPDATE
                SET offer_draft_json = EXCLUDED.offer_draft_json,
                    updated_at = NOW()
                """,
                (
                    lead_id,
                    Json(
                        {
                            "draft_id": draft_id,
                            "text": draft_text,
                            "channel": channel,
                            "tone": tone,
                            "letter_type": letter_type,
                            "our_business_type": our_business_type,
                            "partner_business_type": partner_business_type,
                            "pair_pattern": pair_pattern,
                            "package_idea": package_idea if letter_type == "commercial_offer" else None,
                            "template_policy": template_policy,
                            **prompt_meta,
                        }
                    ),
                ),
            )
            cur.execute(
                """
                UPDATE prospectingleads
                SET partnership_stage = %s,
                    status = %s,
                    selected_channel = %s,
                    updated_at = NOW()
                WHERE id = %s
                """,
                ("proposal_draft_ready", "proposal_draft_ready", channel, lead_id),
            )
            conn.commit()
        finally:
            conn.close()

        try:
            record_ai_learning_event(
                capability="partnership.draft_offer",
                event_type="generated",
                intent="partnership_outreach",
                user_id=user_data.get("user_id"),
                business_id=business_id,
                prompt_key=prompt_meta.get("prompt_key"),
                prompt_version=prompt_meta.get("prompt_version"),
                draft_text="",
                final_text=draft_text[:3000],
                metadata={
                    "lead_id": lead_id,
                    "draft_id": draft_id,
                    "channel": channel,
                    "letter_type": letter_type,
                    "our_business_type": our_business_type,
                    "partner_business_type": partner_business_type,
                    "pair_pattern": pair_pattern,
                    "package_idea": package_idea if letter_type == "commercial_offer" else None,
                    **prompt_meta,
                },
            )
        except Exception as learning_exc:
            print(f"⚠️ partnership.draft_offer learning skipped: {learning_exc}")

        return jsonify({"success": True, "draft_id": draft_id, "text": draft_text, "channel": channel})
    except Exception as e:
        print(f"Error partnership draft offer: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/partnership/leads/<string:lead_id>/prepare-room", methods=["POST"])
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
        )
        if result.get("error"):
            return jsonify(result), int(result.get("status_code") or 400)
        return jsonify(_to_json_compatible(result))
    except Exception as e:
        print(f"Error partnership prepare sales room: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/partnership/drafts", methods=["GET"])
def partnership_list_drafts():
    """User-level list of partnership outreach drafts."""
    user_data, error = _require_auth()
    if error:
        return error
    try:
        requested_business_id = str(request.args.get("business_id") or "").strip() or None
        status_filter = str(request.args.get("status") or "").strip().lower() or None
        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403

            query = """
                WITH draft_scope AS (
                    SELECT
                        d.id, d.lead_id, d.channel, d.angle_type, d.tone, d.status,
                        d.generated_text, d.edited_text, d.approved_text,
                        d.learning_note_json, d.created_at, d.updated_at,
                        l.name AS lead_name, l.category, l.city, l.email,
                        l.selected_channel, l.status AS lead_status,
                        l.pipeline_status AS lead_pipeline_status,
                        l.partnership_stage AS lead_partnership_stage
                    FROM outreachmessagedrafts d
                    JOIN prospectingleads l ON l.id = d.lead_id
                    WHERE l.business_id = %s
                      AND COALESCE(l.intent, 'client_outreach') = 'partnership_outreach'
            """
            query += ACTIVE_PARTNERSHIP_LEAD_SQL
            params: list[Any] = [business_id]
            if status_filter:
                query += " AND d.status = %s"
                params.append(status_filter)
            query += """
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
                    id, lead_id, channel, angle_type, tone, status,
                    generated_text, edited_text, approved_text,
                    learning_note_json, created_at, updated_at,
                    lead_name, category, city, email,
                    selected_channel, lead_status,
                    lead_pipeline_status, lead_partnership_stage
                FROM ranked_drafts
                WHERE draft_rank = 1
                ORDER BY updated_at DESC, created_at DESC
                LIMIT 200
            """
            cur.execute(query, tuple(params))
            rows = [_serialize_draft(dict(row)) for row in cur.fetchall()]
        finally:
            conn.close()
        return jsonify({"success": True, "drafts": rows, "count": len(rows)})
    except Exception as e:
        print(f"Error listing partnership drafts: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/partnership/drafts/<string:draft_id>/approve", methods=["POST"])
def partnership_approve_draft(draft_id):
    """User-level approval for partnership draft."""
    user_data, error = _require_auth()
    if error:
        return error
    try:
        data = request.get_json(silent=True) or {}
        requested_business_id = str(data.get("business_id") or "").strip() or None
        approved_text = str(data.get("approved_text") or "").strip()
        if not approved_text:
            return jsonify({"error": "approved_text is required"}), 400

        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            ensure_ai_learning_events_table(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
            cur.execute(
                """
                SELECT d.id, d.lead_id, d.generated_text, d.edited_text, d.status, d.learning_note_json
                FROM outreachmessagedrafts d
                JOIN prospectingleads l ON l.id = d.lead_id
                WHERE d.id = %s
                  AND l.business_id = %s
                  AND COALESCE(l.intent, 'client_outreach') = 'partnership_outreach'
                LIMIT 1
                """,
                (draft_id, business_id),
            )
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Draft not found"}), 404
            draft_row = dict(row) if hasattr(row, "keys") else {
                "id": row[0], "lead_id": row[1], "generated_text": row[2], "edited_text": row[3], "status": row[4], "learning_note_json": row[5]
            }

            edited_text = str(draft_row.get("edited_text") or "")
            generated_text = str(draft_row.get("generated_text") or "")
            edited_before_accept = approved_text != generated_text
            prompt_meta = _normalize_prompt_meta(
                draft_row.get("learning_note_json"),
                fallback_key="partners.draft_first_note",
                fallback_version="unknown",
                fallback_source="unknown",
            )
            learning_note = draft_row.get("learning_note_json")
            if not isinstance(learning_note, dict):
                learning_note = {}
            accepted_learning_note = {
                **learning_note,
                "intent": "partnership_outreach",
                "accepted": True,
                "edited_before_accept": edited_before_accept,
                **prompt_meta,
            }

            cur.execute(
                """
                UPDATE outreachmessagedrafts
                SET approved_text = %s,
                    status = %s,
                    learning_note_json = %s,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING id, lead_id, channel, angle_type, tone, status,
                          generated_text, edited_text, approved_text,
                          learning_note_json, created_at, updated_at
                """,
                (
                    approved_text,
                    DRAFT_APPROVED,
                    Json(accepted_learning_note),
                    draft_id,
                ),
            )
            updated = cur.fetchone()
            cur.execute(
                """
                UPDATE prospectingleads
                SET status = %s,
                    partnership_stage = %s,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (DRAFT_APPROVED, "proposal_approved", draft_row["lead_id"]),
            )
            record_ai_learning_event(
                capability="partnership.draft_offer",
                event_type="accepted",
                intent="partnership_outreach",
                user_id=user_data.get("user_id"),
                business_id=business_id,
                accepted=True,
                edited_before_accept=edited_before_accept,
                prompt_key=prompt_meta.get("prompt_key"),
                prompt_version=prompt_meta.get("prompt_version"),
                draft_text=generated_text[:3000] if generated_text else None,
                final_text=approved_text[:3000],
                metadata={"draft_id": draft_id, "lead_id": draft_row["lead_id"], **accepted_learning_note},
                conn=conn,
            )
            conn.commit()
        finally:
            conn.close()

        payload = dict(updated) if hasattr(updated, "keys") else updated
        return jsonify({"success": True, "draft": _serialize_draft(payload)})
    except Exception as e:
        print(f"Error approving partnership draft: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/partnership/drafts/<string:draft_id>", methods=["DELETE"])
def partnership_delete_draft(draft_id):
    """User-level delete for partnership draft."""
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
            cur.execute(
                """
                SELECT 1
                FROM outreachmessagedrafts d
                JOIN prospectingleads l ON l.id = d.lead_id
                WHERE d.id = %s
                  AND l.business_id = %s
                  AND COALESCE(l.intent, 'client_outreach') = 'partnership_outreach'
                LIMIT 1
                """,
                (draft_id, business_id),
            )
            if not cur.fetchone():
                return jsonify({"error": "Draft not found"}), 404
        finally:
            conn.close()

        deleted = _delete_outreach_draft(draft_id)
        if not deleted:
            return jsonify({"success": True, "already_deleted": True, "draft_id": draft_id})
        return jsonify({"success": True, "draft": _serialize_draft(deleted)})
    except Exception as e:
        print(f"Error deleting partnership draft: {e}")
        return jsonify({"error": str(e)}), 500


def _load_partnership_send_snapshot(*, business_id: str) -> dict[str, Any]:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            WITH draft_scope AS (
                SELECT
                    d.id, d.lead_id, d.channel, d.status,
                    d.generated_text, d.edited_text, d.approved_text,
                    d.created_at, d.updated_at,
                    l.name AS lead_name, l.category, l.city, l.email,
                    l.selected_channel, l.status AS lead_status,
                    l.pipeline_status AS lead_pipeline_status,
                    l.partnership_stage AS lead_partnership_stage
                FROM outreachmessagedrafts d
                JOIN prospectingleads l ON l.id = d.lead_id
                WHERE d.status = %s
                  AND l.business_id = %s
                  AND COALESCE(l.intent, 'client_outreach') = 'partnership_outreach'
                  AND COALESCE(l.pipeline_status, '') NOT IN ('not_relevant', 'disqualified', 'closed_lost')
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
                id, lead_id, channel, status,
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
                    SELECT d.id, d.lead_id, d.channel, d.created_at, d.updated_at
                    FROM outreachmessagedrafts d
                    JOIN prospectingleads l ON l.id = d.lead_id
                    WHERE d.status = %s
                      AND l.business_id = %s
                      AND COALESCE(l.intent, 'client_outreach') = 'partnership_outreach'
                      AND COALESCE(l.pipeline_status, '') NOT IN ('not_relevant', 'disqualified', 'closed_lost')
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
                SELECT id, lead_id, channel
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
                        id, batch_id, lead_id, draft_id, channel, delivery_status
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (str(uuid.uuid4()), batch_id, row["lead_id"], row["id"], row["channel"], QUEUE_STATUS_QUEUED),
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


@admin_prospecting_bp.route("/api/admin/prospecting/lead/<string:lead_id>/status", methods=["POST"])
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


@admin_prospecting_bp.route("/api/admin/prospecting/lead/<string:lead_id>/manual-contact", methods=["POST"])
def mark_lead_manual_contact(lead_id):
    """Mark lead as contacted manually without requiring queue dispatch."""
    user_data, error = _require_superadmin()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        channel = str(data.get("channel") or "manual").strip().lower() or "manual"
        comment = str(data.get("comment") or "").strip() or None
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


@admin_prospecting_bp.route("/api/admin/prospecting/lead/<string:lead_id>/comment", methods=["POST"])
def add_lead_comment(lead_id):
    """Add free-form operator note to lead timeline."""
    user_data, error = _require_superadmin()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        comment = str(data.get("comment") or "").strip()
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
            _record_lead_timeline_event(
                cur,
                lead_id=lead_id,
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


@admin_prospecting_bp.route("/api/admin/prospecting/lead/<string:lead_id>/timeline", methods=["GET"])
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
            cur.execute(
                """
                SELECT id, lead_id, event_type, actor_id, comment, payload_json, created_at
                FROM lead_timeline_events
                WHERE lead_id = %s
                ORDER BY created_at DESC
                LIMIT 200
                """,
                (lead_id,),
            )
            events = [dict(row) for row in cur.fetchall() or []]
        finally:
            conn.close()
        return jsonify({"success": True, "events": _to_json_compatible(events), "count": len(events)})
    except Exception as e:
        print(f"Error loading lead timeline: {e}")
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
            return jsonify({"error": "Channel must be one of: telegram, whatsapp, max, email, manual"}), 400

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


@admin_prospecting_bp.route("/api/admin/prospecting/lead/<string:lead_id>/contacts", methods=["POST"])
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


@admin_prospecting_bp.route("/api/admin/prospecting/lead/<string:lead_id>/language", methods=["POST"])
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
            if not _lead_has_channel_contact(lead_dict, channel):
                return jsonify({"error": _outreach_channel_contact_error(channel)}), 400

            draft_payload = _generate_first_message_draft(lead_dict, channel)
            draft_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO outreachmessagedrafts (
                    id, lead_id, channel, angle_type, tone, status,
                    generated_text, learning_note_json, created_by
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
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

        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM prospectingleads WHERE id = %s", (lead_id,))
            lead = cur.fetchone()
            if not lead:
                return jsonify({"error": "Lead not found"}), 404
            lead_dict = dict(lead)

            display_lead = _normalize_lead_for_display(dict(lead_dict))
            if not display_lead:
                return jsonify({"error": "Lead is not available for preview"}), 404
            display_lead = _attach_admin_prospecting_public_offer_metadata(conn, display_lead)
            preview = build_lead_card_preview_snapshot(display_lead)
            if not _lead_has_channel_contact(display_lead, channel):
                return jsonify({"error": _outreach_channel_contact_error(channel)}), 400

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
                    id, lead_id, channel, angle_type, tone, status,
                    generated_text, edited_text, learning_note_json, created_by
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
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
        )
        if result.get("error"):
            return jsonify(result), int(result.get("status_code") or 400)
        return jsonify(_to_json_compatible(result))
    except Exception as e:
        print(f"Error preparing client sales room: {e}")
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
                        id, batch_id, lead_id, draft_id, channel, delivery_status,
                        provider_message_id, provider_name, recipient_kind, recipient_value, sent_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, NOW()
                    )
                    """,
                    (
                        queue_id,
                        batch_id,
                        draft["lead_id"],
                        draft_id,
                        channel,
                        QUEUE_STATUS_SENT,
                        f"manual:{draft_id}",
                        "manual",
                        recipient_kind,
                        recipient_value,
                    ),
                )

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
