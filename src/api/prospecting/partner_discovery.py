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
        _ensure_imported_partnership_workstream(
            cur,
            lead_id=existing_id,
            business_id=business_id,
            created_by=created_by,
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
    _ensure_imported_partnership_workstream(
        cur,
        lead_id=lead_id,
        business_id=business_id,
        created_by=created_by,
    )
    return lead_id, True


def _ensure_imported_partnership_workstream(
    cur,
    *,
    lead_id: str,
    business_id: str,
    created_by: str,
) -> str:
    """Ensure every imported partner lead enters the canonical workstream flow."""
    cur.execute(
        """
        SELECT id FROM lead_workstreams
        WHERE lead_id = %s
          AND workstream_type = 'client_partnership'
          AND client_business_id = %s
        LIMIT 1
        """,
        (lead_id, business_id),
    )
    existing = cur.fetchone()
    if existing:
        if hasattr(existing, "get"):
            return str(existing.get("id") or "")
        return str(existing[0])

    workstream_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO lead_workstreams (
            id, lead_id, workstream_type, client_business_id, status,
            created_by, created_at, updated_at
        ) VALUES (
            %s, %s, 'client_partnership', %s, 'unprocessed',
            NULLIF(%s, ''), NOW(), NOW()
        )
        RETURNING id
        """,
        (workstream_id, lead_id, business_id, created_by),
    )
    from services.contact_intelligence_service import enqueue_enrichment_job

    enqueue_enrichment_job(cur, workstream_id, allow_paid_enrichment=False)
    return workstream_id

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
                "Здравствуйте! Посмотрел вашу карточку на картах.",
                f"В открытых данных заметил один конкретный момент: {key_issue.lower()}.",
            ]
            if public_audit_url:
                message_lines.append(f"Сделал короткий разбор: {public_audit_url}")
            message_lines.append("Могу прислать короткий разбор с первым приоритетом.")
            message_lines.append("Посмотреть его будет полезно?")
        elif channel == "whatsapp":
            message_lines = [
                "Здравствуйте! Посмотрел вашу карточку на картах.",
                f"В открытых данных заметил один конкретный момент: {key_issue.lower()}.",
            ]
            if public_audit_url:
                message_lines.append(f"Короткий разбор здесь: {public_audit_url}")
            message_lines.append("Могу прислать короткий разбор с первым приоритетом.")
            message_lines.append("Посмотреть его будет полезно?")
        elif channel == "email":
            message_lines = [
                "Здравствуйте! Посмотрел вашу карточку на картах.",
                f"В открытых данных заметил один конкретный момент: {key_issue.lower()}.",
            ]
            if public_audit_url:
                message_lines.append(f"Сделал короткий разбор, как это исправить: {public_audit_url}")
            else:
                message_lines.append("Сделал короткий разбор, как это исправить.")
            message_lines.append("Могу прислать короткий разбор с первым приоритетом.")
            message_lines.append("Посмотреть его будет полезно?")
        else:
            message_lines = [
                "Здравствуйте! Посмотрел вашу карточку на картах.",
                f"В открытых данных заметил один конкретный момент: {key_issue.lower()}.",
            ]
            if public_audit_url:
                message_lines.append(f"Короткий разбор: {public_audit_url}")
            message_lines.append("Могу прислать короткий разбор с первым приоритетом.")
            message_lines.append("Посмотреть его будет полезно?")

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
