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

def _generate_superadmin_deterministic_first_message(
    lead: dict[str, Any],
    preview: dict[str, Any],
) -> dict[str, str]:
    company_name = str(lead.get("name") or "ваш бизнес").strip() or "ваш бизнес"
    issue_hint = _deterministic_issue_hint_from_preview(preview)
    message_lines = [
        "Здравствуйте!",
        "",
        f"Посмотрел карточку {company_name} на картах.",
        f"В открытых данных заметил конкретный момент: {issue_hint}",
        "",
        "Подготовил короткий разбор с фактами и первым приоритетом.",
        "Отправить его вам для проверки?",
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
            from services.contact_intelligence_service import sync_parsed_lead_contacts

            sync_parsed_lead_contacts(cur, dict(updated))
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


def _load_latest_partnership_parse_state(cur, lead: dict[str, Any]) -> dict[str, Any]:
    cur.execute(
        """
        SELECT status, error_message, retry_after, updated_at
        FROM parsequeue
        WHERE (
                (%s <> '' AND business_id::text = %s)
                OR (%s = '' AND %s <> '' AND url = %s)
              )
          AND task_type IN ('parse_card', 'sync_yandex_business')
        ORDER BY COALESCE(updated_at, created_at) DESC
        LIMIT 1
        """,
        (
            str(lead.get("parse_business_id") or ""),
            str(lead.get("parse_business_id") or ""),
            str(lead.get("parse_business_id") or ""),
            str(lead.get("source_url") or ""),
            str(lead.get("source_url") or ""),
        ),
    )
    row = cur.fetchone()
    return dict(row) if row and hasattr(row, "keys") else {}


def _partnership_parse_is_terminal_closed(parse_state: dict[str, Any] | None) -> bool:
    state = parse_state if isinstance(parse_state, dict) else {}
    if str(state.get("status") or "").strip().lower() != "error":
        return False
    error = str(state.get("error_message") or "").strip().lower()
    return "business_closed" in error or "permanent_closed" in error

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
        "name": _pick_text("name", "title", "company_name", "organization_name", "org_name")
        or str(card_row.get("title") or "").strip() or None,
        "address": _pick_text("address", "full_address", "short_address", "location")
        or str(card_row.get("address") or "").strip() or None,
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
            SELECT title, address, url, phone, site, overview, rating, reviews_count
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
                SELECT title, address, url, phone, site, overview, rating, reviews_count
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
            candidate_source_url=parsed.get("source_url") or card.get("url") or source_url,
            candidate_external_id=source_org_id,
        ):
            mismatch = dict(lead)
            mismatch["parsed_identity_status"] = "mismatch"
            mismatch["parsed_candidate_name"] = parsed.get("name")
            mismatch["parsed_candidate_source_url"] = card.get("url")
            return mismatch

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
            from services.discovered_telegram_source_service import sync_discovered_telegram_sources

            sync_discovered_telegram_sources(conn, lead, parsed.get("social_links"))
            conn.commit()
            confirmed = dict(lead)
            confirmed["parsed_identity_status"] = "confirmed"
            return confirmed

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
            from services.contact_intelligence_service import sync_parsed_lead_contacts
            from services.discovered_telegram_source_service import sync_discovered_telegram_sources

            sync_discovered_telegram_sources(conn, dict(updated), parsed.get("social_links"))
            sync_parsed_lead_contacts(cur, dict(updated))
            conn.commit()
            result = dict(updated)
            result["parsed_identity_status"] = "confirmed"
            return result
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
            from services.discovered_telegram_source_service import sync_discovered_telegram_sources

            sync_discovered_telegram_sources(conn, lead, parsed.get("social_links"))
            conn.commit()
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
            from services.contact_intelligence_service import sync_parsed_lead_contacts
            from services.discovered_telegram_source_service import sync_discovered_telegram_sources

            sync_discovered_telegram_sources(conn, dict(updated), parsed.get("social_links"))
            sync_parsed_lead_contacts(cur, dict(updated))
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
