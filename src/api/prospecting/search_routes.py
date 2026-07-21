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
import math
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

def _geo_distance_km(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    earth_radius_km = 6371.0088
    lat_a_rad = math.radians(lat_a)
    lat_b_rad = math.radians(lat_b)
    delta_lat = math.radians(lat_b - lat_a)
    delta_lon = math.radians(lon_b - lon_a)
    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat_a_rad) * math.cos(lat_b_rad) * math.sin(delta_lon / 2) ** 2
    )
    return earth_radius_km * 2 * math.asin(min(1.0, math.sqrt(haversine)))


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

        def _geo_match_text(value: Any) -> str:
            return re.sub(r"[^0-9a-zа-яё]+", " ", str(value or "").lower()).strip()

        def _looks_like_same_business(candidate_name: str, candidate_address: str | None, business_row: dict[str, Any]) -> bool:
            own_name = _geo_match_text(business_row.get("name"))
            lead_name = _geo_match_text(candidate_name)
            if not own_name or len(own_name) < 5 or not lead_name:
                return False
            same_brand = own_name in lead_name or lead_name in own_name
            if not same_brand:
                return False
            own_address = _geo_match_text(business_row.get("address"))
            lead_address = _geo_match_text(candidate_address)
            if own_address and lead_address and (own_address in lead_address or lead_address in own_address):
                return True
            return own_name in lead_name

        yandex_query = " ".join(part for part in [category, query] if part).strip() or query or category

        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
            cur.execute("SELECT * FROM businesses WHERE id = %s LIMIT 1", (business_id,))
            business_row = dict(cur.fetchone() or {})
            try:
                business_lat = float(business_row.get("geo_lat"))
                business_lon = float(business_row.get("geo_lon"))
            except (TypeError, ValueError):
                business_lat = None
                business_lon = None
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
                    for candidate in provider_candidates:
                        if not isinstance(candidate, dict):
                            continue
                        candidate.setdefault("source", "openclaw_seed_geo" if has_seed_items else "openclaw_google_geo")
                        candidate.setdefault("source_kind", "geo_search_seed" if has_seed_items else "geo_search")
                        candidate.setdefault("source_provider", "openclaw_seed" if has_seed_items else "openclaw_google")
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
                    for candidate in yandex_candidates:
                        if not isinstance(candidate, dict):
                            continue
                        candidate.setdefault("source", "yandex_geo")
                        candidate.setdefault("source_kind", "geo_search")
                        candidate.setdefault("source_provider", "yandex_maps")
                    candidates.extend([item for item in yandex_candidates if isinstance(item, dict)])
                    provider_status["yandex"]["executed"] = True
                    provider_status["yandex"]["items_count"] = len(yandex_candidates)

            if not isinstance(candidates, list):
                candidates = []

            imported_ids: list[str] = []
            merged_count = 0
            skipped = 0
            outside_radius_count = 0
            missing_coordinates_count = 0
            for item in candidates:
                if not isinstance(item, dict):
                    continue
                source_url = str(item.get("source_url") or item.get("url") or item.get("maps_url") or "").strip()
                lead_name = str(item.get("name") or item.get("title") or "Новый партнёр").strip()
                lead_city = str(item.get("city") or city or "").strip() or None
                lead_category = str(item.get("category") or category or "").strip() or None
                lead_address = str(item.get("address") or item.get("location") or "").strip() or None
                if _looks_like_same_business(lead_name, lead_address, business_row):
                    skipped += 1
                    continue
                phone = str(item.get("phone") or "").strip() or None
                email = str(item.get("email") or "").strip() or None
                website = str(item.get("website") or item.get("website_url") or "").strip() or None
                telegram_url = str(item.get("telegram_url") or "").strip() or None
                whatsapp_url = str(item.get("whatsapp_url") or "").strip() or None
                external_place_id = str(item.get("place_id") or item.get("external_place_id") or item.get("google_place_id") or "").strip() or None
                external_source_id = str(item.get("source_id") or item.get("external_source_id") or external_place_id or "").strip() or None
                candidate_lat = item.get("lat") if item.get("lat") is not None else item.get("geo_lat")
                candidate_lon = item.get("lon") if item.get("lon") is not None else item.get("geo_lon")
                try:
                    lat = float(candidate_lat) if candidate_lat is not None else None
                except Exception:
                    lat = None
                try:
                    lon = float(candidate_lon) if candidate_lon is not None else None
                except Exception:
                    lon = None
                if business_lat is not None and business_lon is not None and not has_seed_items:
                    if lat is None or lon is None:
                        missing_coordinates_count += 1
                        skipped += 1
                        continue
                    if _geo_distance_km(business_lat, business_lon, lat, lon) > radius_km:
                        outside_radius_count += 1
                        skipped += 1
                        continue
                try:
                    rating = float(item.get("rating")) if item.get("rating") is not None else None
                except Exception:
                    rating = None
                try:
                    reviews_count = int(item.get("reviews_count")) if item.get("reviews_count") is not None else None
                except Exception:
                    reviews_count = None
                fallback_source = (
                    "openclaw_seed_geo"
                    if has_seed_items
                    else ("openclaw_google_geo" if provider in {"google", "both"} else "yandex_geo")
                )
                fallback_source_provider = (
                    "openclaw_seed"
                    if has_seed_items
                    else ("openclaw_google" if provider in {"google", "both"} else "yandex_maps")
                )
                meta_provider = ""
                if isinstance(meta_blob, dict):
                    meta_provider = str(meta_blob.get("provider") or "").strip()
                lead_id, created = _insert_partnership_lead_if_new(
                    cur,
                    business_id=business_id,
                    created_by=user_data["user_id"],
                    source_url=source_url,
                    name=lead_name,
                    address=lead_address,
                    city=lead_city,
                    category=lead_category,
                    source=str(item.get("source") or fallback_source).strip() or fallback_source,
                    phone=phone,
                    email=email,
                    website=website,
                    telegram_url=telegram_url,
                    whatsapp_url=whatsapp_url,
                    rating=rating,
                    reviews_count=reviews_count,
                    source_kind=str(item.get("source_kind") or ("geo_search_seed" if has_seed_items else "geo_search")).strip() or ("geo_search_seed" if has_seed_items else "geo_search"),
                    source_provider=str(item.get("source_provider") or item.get("provider") or fallback_source_provider).strip() or fallback_source_provider,
                    external_place_id=external_place_id,
                    external_source_id=external_source_id,
                    lat=lat,
                    lon=lon,
                    search_payload={
                        "provider": meta_provider or ("seed_items" if has_seed_items else provider),
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
                "outside_radius_count": outside_radius_count,
                "missing_coordinates_count": missing_coordinates_count,
                "openclaw_meta": meta_blob if isinstance(meta_blob, dict) else {},
                "provider_status": provider_status,
                "warnings": warnings,
                "warning": " ".join(warnings).strip() or None,
            }
        )
    except Exception as e:
        print(f"Error partnership geo search: {e}")
        return jsonify({"error": str(e)}), 500

@admin_prospecting_bp.route("/api/partnership/health", methods=["GET"])
def partnership_health():
    """Health snapshot for partnership flow by business."""
    user_data, error = _require_auth()
    if error:
        return error
    try:
        requested_business_id = str(request.args.get("business_id") or "").strip() or None

        def _count_from_row(row: Any) -> int:
            if not row:
                return 0
            if isinstance(row, dict):
                for key in ("total", "count", "count(*)"):
                    if key in row:
                        return int(row.get(key) or 0)
                values = list(row.values())
                return int((values[0] if values else 0) or 0)
            return int((row[0] if len(row) else 0) or 0)

        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            cur = conn.cursor()
            schema_flags = _get_partnership_schema_flags(cur)
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403

            cur.execute(
                """
                SELECT COUNT(*)::INT AS total
                FROM prospectingleads
                WHERE business_id = %s
                  AND COALESCE(intent, 'client_outreach') = 'partnership_outreach'
                """,
                (business_id,),
            )
            leads_total = _count_from_row(cur.fetchone())

            cur.execute(
                """
                SELECT COUNT(*)::INT AS total
                FROM outreachmessagedrafts d
                JOIN prospectingleads l ON l.id = d.lead_id
                WHERE l.business_id = %s
                  AND COALESCE(l.intent, 'client_outreach') = 'partnership_outreach'
                """,
                (business_id,),
            )
            drafts_total = _count_from_row(cur.fetchone())

            cur.execute(
                """
                SELECT COUNT(DISTINCT b.id)::INT AS total
                FROM outreachsendbatches b
                JOIN outreachsendqueue q ON q.batch_id = b.id
                JOIN prospectingleads l ON l.id = q.lead_id
                WHERE l.business_id = %s
                  AND COALESCE(l.intent, 'client_outreach') = 'partnership_outreach'
                """,
                (business_id,),
            )
            batches_total = _count_from_row(cur.fetchone())

            reactions_total = 0
            if schema_flags["has_reactions"]:
                cur.execute(
                    """
                    SELECT COUNT(*)::INT AS total
                    FROM outreachmessagereactions r
                    JOIN outreachsendqueue q ON q.id = r.queue_id
                    JOIN prospectingleads l ON l.id = q.lead_id
                    WHERE l.business_id = %s
                      AND COALESCE(l.intent, 'client_outreach') = 'partnership_outreach'
                    """,
                    (business_id,),
                )
                reactions_total = _count_from_row(cur.fetchone())
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

        map_match: dict[str, Any] | None = None
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
            parse_state = _load_latest_partnership_parse_state(cur, lead)
            if _partnership_parse_is_terminal_closed(parse_state):
                return jsonify({
                    "error": "Публичная карточка сообщает, что компания закрыта.",
                    "code": "PARTNER_BUSINESS_CLOSED",
                    "next_action": "mark_not_relevant",
                }), 409
            lead = _sync_partnership_lead_from_parsed_data(dict(lead))
            identity_mismatch = str(lead.get("parsed_identity_status") or "") == "mismatch"
            if _partnership_source_requires_map_match(lead.get("source_url")) or identity_mismatch:
                if _is_synthetic_partnership_lead(lead):
                    return jsonify(
                        {
                            "error": "Запись обозначает группу или тип бизнеса, а не одну компанию.",
                            "code": "PARTNER_MAP_MATCH_SYNTHETIC",
                        }
                    ), 422
                candidates, provider_error = _find_yandex_candidates_for_partnership_lead(lead)
                if provider_error:
                    return jsonify(
                        {
                            "error": "Не удалось выполнить поиск на Яндекс Картах.",
                            "code": "PARTNER_MAP_MATCH_PROVIDER_ERROR",
                            "detail": provider_error,
                        }
                    ), 503
                candidate, match_status = _select_partnership_map_candidate(candidates)
                if not candidate:
                    status_code = 404 if match_status == "closed_or_not_found" else 409
                    return jsonify(
                        {
                            "error": "Нельзя однозначно подтвердить карточку компании.",
                            "code": "PARTNER_MAP_MATCH_AMBIGUOUS",
                            "reason": match_status,
                            "candidates": candidates,
                        }
                    ), status_code
                _store_partnership_map_match(cur, lead=lead, candidate=candidate, candidates=candidates)
                conn.commit()
                lead = _load_partnership_lead(cur, lead_id=lead_id, business_id=business_id)
                map_match = {
                    "status": "confirmed",
                    "candidate": candidate,
                    "confidence": candidate.get("confidence"),
                }
        finally:
            conn.close()

        display_lead = _normalize_lead_for_display(dict(lead))
        if not display_lead:
            return jsonify({"error": "Lead is not available for parsing"}), 400
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
                "map_match": map_match,
            }
        )
    except Exception as e:
        print(f"Error partnership parse lead: {e}")
        return jsonify({"error": str(e)}), 500
