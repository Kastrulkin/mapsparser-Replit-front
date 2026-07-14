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

if __name__.startswith("src."):
    sys.modules.setdefault("api.admin_prospecting", sys.modules[__name__])
else:
    sys.modules.setdefault("src.api.admin_prospecting", sys.modules[__name__])

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

from functools import wraps

from api.prospecting import access_schema as _chunk_access_schema
from api.prospecting import partner_discovery as _chunk_partner_discovery
from api.prospecting import lead_parsing as _chunk_lead_parsing
from api.prospecting import audit_generation as _chunk_audit_generation
from api.prospecting import delivery_runtime as _chunk_delivery_runtime
from api.prospecting import search_routes as _chunk_search_routes
from api.prospecting import analytics_routes as _chunk_analytics_routes
from api.prospecting import audit_routes as _chunk_audit_routes
from api.prospecting import outreach_routes as _chunk_outreach_routes
from api.prospecting import sales_room_routes as _chunk_sales_room_routes
from api.prospecting import admin_routes as _chunk_admin_routes

_CHUNK_MODULES = (
    _chunk_access_schema,
    _chunk_partner_discovery,
    _chunk_lead_parsing,
    _chunk_audit_generation,
    _chunk_delivery_runtime,
    _chunk_search_routes,
    _chunk_analytics_routes,
    _chunk_audit_routes,
    _chunk_outreach_routes,
    _chunk_sales_room_routes,
    _chunk_admin_routes,
)
_IMPLEMENTATIONS = {
    name: value
    for module in _CHUNK_MODULES
    for name, value in vars(module).items()
    if callable(value) and getattr(value, "__module__", "") == module.__name__
}


def _bind_runtime_namespace() -> None:
    namespace = {
        name: value
        for name, value in globals().items()
        if name not in {"_bind_runtime_namespace", "_compatibility_wrapper"}
    }
    for module in _CHUNK_MODULES:
        vars(module).update(namespace)


def _compatibility_wrapper(name: str, implementation: Any):
    @wraps(implementation)
    def wrapper(*args: Any, **kwargs: Any):
        _bind_runtime_namespace()
        return _IMPLEMENTATIONS[name](*args, **kwargs)

    return wrapper


for _name, _implementation in _IMPLEMENTATIONS.items():
    if _name in {"_bind_runtime_namespace", "_compatibility_wrapper"}:
        continue
    globals()[_name] = _compatibility_wrapper(_name, _implementation)


@admin_prospecting_bp.before_request
def _sync_compatibility_namespace_before_request() -> None:
    _bind_runtime_namespace()


_bind_runtime_namespace()
