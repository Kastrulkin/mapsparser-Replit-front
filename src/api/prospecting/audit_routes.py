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
from services.lead_workstream_service import (
    CLIENT_PARTNERSHIP,
    LOCALOS_SALES,
    resolve_workstream,
    update_workstream,
)
from services.prospecting_research_service import load_latest_research
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
    workstream_id: str | None = None,
) -> dict[str, Any]:
    draft_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO outreachmessagedrafts (
            id, lead_id, workstream_id, channel, angle_type, tone, status,
            generated_text, edited_text, learning_note_json, created_by, created_at, updated_at
        ) VALUES (
            %s, %s, NULLIF(%s, '')::uuid, %s, %s, %s, %s,
            %s, %s, %s, %s, NOW(), NOW()
        )
        RETURNING id, lead_id, workstream_id, channel, angle_type, tone, status,
                  generated_text, edited_text, approved_text,
                  learning_note_json, created_at, updated_at
        """,
        (
            draft_id,
            lead_id,
            workstream_id or "",
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

def _normalize_audit_offer_platform(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in AUDIT_OFFER_PLATFORMS else "yandex"

def _normalize_audit_offer_status(value: Any, *, enabled: bool, prepared_audit_url: str) -> str:
    normalized = str(value or "").strip().lower()
    allowed = AUDIT_OFFER_VISIBLE_STATUSES | {"draft", "disabled"}
    if normalized in allowed:
        if not enabled:
            return "disabled"
        return normalized
    if not enabled:
        return "disabled"
    return "prepared" if prepared_audit_url else "draft"

def _normalize_sales_room_audit_offer_payload(data: dict[str, Any], room: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = data if isinstance(data, dict) else {}
    enabled = bool(payload.get("enabled") or payload.get("show_offer"))
    prepared_slug = str(payload.get("prepared_audit_slug") or payload.get("preparedAuditSlug") or "").strip()
    prepared_url = str(payload.get("prepared_audit_url") or payload.get("preparedAuditUrl") or "").strip()
    if not prepared_url and prepared_slug:
        prepared_url = _make_public_offer_url(prepared_slug)
    lead_email = normalize_email(str(payload.get("lead_email") or payload.get("leadEmail") or ""))
    lead_id = str(payload.get("lead_id") or payload.get("leadId") or (room or {}).get("lead_id") or "").strip()
    company_name = str(payload.get("company_name") or payload.get("companyName") or "").strip()
    if not company_name:
        room_json = (room or {}).get("room_json") if isinstance((room or {}).get("room_json"), dict) else {}
        recipient = room_json.get("recipient") if isinstance(room_json.get("recipient"), dict) else {}
        company_name = str(recipient.get("name") or "Компания").strip() or "Компания"
    company_map_url = str(payload.get("company_map_url") or payload.get("companyMapUrl") or "").strip()
    if not company_map_url:
        room_json = (room or {}).get("room_json") if isinstance((room or {}).get("room_json"), dict) else {}
        recipient = room_json.get("recipient") if isinstance(room_json.get("recipient"), dict) else {}
        company_map_url = str(recipient.get("source_url") or "").strip()
    status = _normalize_audit_offer_status(payload.get("status"), enabled=enabled, prepared_audit_url=prepared_url)
    return {
        "lead_id": lead_id or None,
        "lead_email": lead_email or None,
        "company_name": company_name,
        "company_map_url": company_map_url,
        "company_address": str(payload.get("company_address") or payload.get("companyAddress") or "").strip() or None,
        "platform": _normalize_audit_offer_platform(payload.get("platform")),
        "enabled": enabled,
        "admin_comment": str(payload.get("admin_comment") or payload.get("adminComment") or "").strip() or None,
        "offer_title": str(payload.get("offer_title") or payload.get("offerTitle") or AUDIT_OFFER_DEFAULT_TITLE).strip(),
        "offer_text": str(payload.get("offer_text") or payload.get("offerText") or AUDIT_OFFER_DEFAULT_TEXT).strip(),
        "button_text": str(payload.get("button_text") or payload.get("buttonText") or AUDIT_OFFER_DEFAULT_BUTTON).strip(),
        "prepared_audit_slug": prepared_slug or None,
        "prepared_audit_url": prepared_url or None,
        "status": status,
    }

def _upsert_sales_room_audit_offer(cur, *, room: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    payload = _normalize_sales_room_audit_offer_payload(data, room)
    if not payload["company_map_url"]:
        raise ValueError("company_map_url is required")
    room_id = str(room.get("id") or "").strip()
    offer_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO sales_room_audit_offers (
            id, room_id, lead_id, lead_email, company_name, company_map_url, company_address,
            platform, enabled, admin_comment, offer_title, offer_text, button_text,
            prepared_audit_slug, prepared_audit_url, status, created_at, updated_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, NOW(), NOW()
        )
        ON CONFLICT (room_id) DO UPDATE
        SET lead_id = EXCLUDED.lead_id,
            lead_email = EXCLUDED.lead_email,
            company_name = EXCLUDED.company_name,
            company_map_url = EXCLUDED.company_map_url,
            company_address = EXCLUDED.company_address,
            platform = EXCLUDED.platform,
            enabled = EXCLUDED.enabled,
            admin_comment = EXCLUDED.admin_comment,
            offer_title = EXCLUDED.offer_title,
            offer_text = EXCLUDED.offer_text,
            button_text = EXCLUDED.button_text,
            prepared_audit_slug = EXCLUDED.prepared_audit_slug,
            prepared_audit_url = EXCLUDED.prepared_audit_url,
            status = CASE
                WHEN sales_room_audit_offers.status IN ('requested', 'processing', 'ready', 'opened')
                    THEN sales_room_audit_offers.status
                ELSE EXCLUDED.status
            END,
            updated_at = NOW()
        RETURNING *
        """,
        (
            offer_id,
            room_id,
            payload["lead_id"],
            payload["lead_email"],
            payload["company_name"],
            payload["company_map_url"],
            payload["company_address"],
            payload["platform"],
            payload["enabled"],
            payload["admin_comment"],
            payload["offer_title"],
            payload["offer_text"],
            payload["button_text"],
            payload["prepared_audit_slug"],
            payload["prepared_audit_url"],
            payload["status"],
        ),
    )
    return _row_to_dict(cur.fetchone())

def _load_sales_room_audit_offer(cur, room_id: str, *, for_update: bool = False) -> dict[str, Any]:
    suffix = " FOR UPDATE" if for_update else ""
    cur.execute(
        f"""
        SELECT *
        FROM sales_room_audit_offers
        WHERE room_id = %s
        LIMIT 1
        {suffix}
        """,
        (room_id,),
    )
    return _row_to_dict(cur.fetchone())

def _public_audit_offer_visible_for_user(
    cur,
    room: dict[str, Any],
    offer: dict[str, Any],
    user_data: dict[str, Any] | None,
    *,
    current_business_id: str = "",
) -> bool:
    if not offer or not bool(offer.get("enabled")):
        return False
    if str(offer.get("status") or "").strip().lower() not in AUDIT_OFFER_VISIBLE_STATUSES:
        return False
    if not user_data:
        return True
    user_id = str(user_data.get("user_id") or user_data.get("id") or "").strip()
    company_name = str(offer.get("company_name") or "").strip()
    if not user_id or not company_name:
        return False
    target_slug = _slugify_company_name(company_name)
    if current_business_id:
        cur.execute(
            """
            SELECT name, owner_id
            FROM businesses
            WHERE id = %s
            LIMIT 1
            """,
            (current_business_id,),
        )
        row = cur.fetchone()
        if not row:
            return False
        name = str(row.get("name") if hasattr(row, "get") else row[0]).strip()
        owner_id = str(row.get("owner_id") if hasattr(row, "get") else row[1]).strip()
        if owner_id != user_id and not bool(user_data.get("is_superadmin")):
            return False
        return bool(name and _slugify_company_name(name) == target_slug)
    if bool(user_data.get("is_superadmin")):
        return True
    cur.execute(
        """
        SELECT name
        FROM businesses
        WHERE owner_id = %s
        ORDER BY created_at DESC
        LIMIT 50
        """,
        (user_id,),
    )
    rows = cur.fetchall() or []
    for row in rows:
        name = str(row.get("name") if hasattr(row, "get") else row[0]).strip()
        if name and _slugify_company_name(name) == target_slug:
            return True
    return False

def release_ready_audit_offers(now: datetime | None = None) -> int:
    _now = now or datetime.now(timezone.utc)
    delay_seconds = _audit_offer_processing_delay_seconds()
    conn = get_db_connection()
    released = 0
    try:
        _ensure_sales_room_tables(conn)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT o.*, r.slug
            FROM sales_room_audit_offers o
            JOIN sales_rooms r ON r.id = o.room_id
            WHERE o.status = 'processing'
              AND o.processing_started_at IS NOT NULL
              AND o.processing_started_at <= %s - (%s * INTERVAL '1 second')
            FOR UPDATE
            """,
            (_now, delay_seconds),
        )
        rows = [dict(row) for row in (cur.fetchall() or [])]
        for offer in rows:
            audit_url = str(offer.get("prepared_audit_url") or "").strip()
            if not audit_url:
                continue
            room_id = str(offer.get("room_id") or "")
            cur.execute(
                """
                UPDATE sales_room_audit_offers
                SET status = 'ready',
                    ready_at = COALESCE(ready_at, %s),
                    updated_at = NOW()
                WHERE id = %s
                  AND status = 'processing'
                RETURNING *
                """,
                (_now, offer.get("id")),
            )
            updated = _row_to_dict(cur.fetchone())
            if not updated:
                continue
            email = normalize_email(str(updated.get("lead_email") or ""))
            if not email and updated.get("requested_by_participant_id"):
                cur.execute(
                    "SELECT email FROM sales_room_participants WHERE id = %s LIMIT 1",
                    (updated.get("requested_by_participant_id"),),
                )
                participant_row = cur.fetchone()
                email = normalize_email(str(participant_row.get("email") if participant_row and hasattr(participant_row, "get") else ""))
            _record_sales_room_event_by_id(cur, room_id=room_id, event_type="audit_offer_ready", metadata={"offer_id": str(updated.get("id") or "")})
            if email and not updated.get("email_sent_at"):
                email_sent = _send_sales_room_audit_ready_email(
                    email=email,
                    company_name=str(updated.get("company_name") or "компания"),
                    audit_url=audit_url,
                    user_id=str(updated.get("requested_user_id") or ""),
                )
                if email_sent:
                    cur.execute(
                        """
                        UPDATE sales_room_audit_offers
                        SET email_sent_at = %s,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (_now, updated.get("id")),
                    )
                    _record_sales_room_event_by_id(
                        cur,
                        room_id=room_id,
                        event_type="audit_offer_email_sent",
                        metadata={"offer_id": str(updated.get("id") or ""), "email": email},
                    )
            released += 1
        conn.commit()
        return released
    finally:
        conn.close()

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
        "title": str(
            proposal.get("title")
            or ("Идея сотрудничества" if mode == SALES_ROOM_MODE_PARTNER else "Предложение")
        ).strip(),
        "summary": str(proposal.get("summary") or "").strip(),
        "body_text": body_text,
        "bullets": proposal.get("bullets") if isinstance(proposal.get("bullets"), list) else [],
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
        SELECT l.*, ws.id AS active_workstream_id
        FROM prospectingleads l
        JOIN lead_workstreams ws ON ws.lead_id = l.id
        WHERE l.id = %s
          AND ws.client_business_id = %s
          AND ws.workstream_type = 'client_partnership'
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

def _refresh_existing_partnership_sales_room(
    cur,
    *,
    business_id: str,
    user_id: str,
    lead: dict[str, Any],
    business_profile: dict[str, Any],
    audit_json: dict[str, Any],
    match_json: dict[str, Any],
    workstream_id: str,
    channel: str,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    lead_id = str(lead.get("id") or "").strip()
    cur.execute(
        """
        SELECT *
        FROM sales_rooms
        WHERE business_id = NULLIF(%s, '')::uuid
          AND lead_id = %s
          AND mode = %s
          AND (workstream_id = NULLIF(%s, '')::uuid OR workstream_id IS NULL)
        ORDER BY created_at ASC
        LIMIT 1
        FOR UPDATE
        """,
        (business_id, lead_id, SALES_ROOM_MODE_PARTNER, workstream_id),
    )
    room = _row_to_dict(cur.fetchone())
    if not room:
        return None

    business_name = _pick_business_display_name(business_profile)
    lead_name = str(lead.get("name") or "компания").strip() or "компания"
    body_text = _build_organika_partner_offer_text(
        business_name=business_name,
        lead_name=lead_name,
        audit_json=audit_json,
        lead=lead,
        business_profile=business_profile,
    )
    research = lead.get("research") if isinstance(lead.get("research"), dict) else {}
    opener = str(research.get("suggested_opener") or "").strip()
    if opener and opener not in body_text:
        body_text = f"{opener}\n\n{body_text}"
    proposal_json = {
        "title": f"Предложение от {business_name}",
        "summary": "Один безопасный тест сотрудничества без автоматических рассылок.",
        "body_text": body_text,
        "bullets": [],
        "next_step": "Сверить интерес на 20-минутном разговоре и выбрать один тест.",
        "data_mode": SALES_ROOM_DATA_TEMPLATE,
    }
    generated_room_json = _build_sales_room_payload(
        mode=SALES_ROOM_MODE_PARTNER,
        data_mode=SALES_ROOM_DATA_TEMPLATE,
        lead=lead,
        business_profile=business_profile,
        audit_public_url="",
        audit_json={},
        match_json={},
        proposal_json=proposal_json,
        slug=str(room.get("slug") or ""),
    )
    existing_room_json = room.get("room_json") if isinstance(room.get("room_json"), dict) else {}
    room_json = dict(existing_room_json)
    room_json.update(generated_room_json)
    latest_version = _load_sales_room_latest_version(cur, str(room.get("id") or ""))
    if not latest_version:
        latest_version = _ensure_sales_room_proposal_version(
            cur,
            room_id=str(room.get("id") or ""),
            body_text=str((existing_room_json.get("proposal") or {}).get("body_text") or ""),
            author_name=business_name,
            metadata={"source": "existing_room_proposal"},
        )
    if str(latest_version.get("body_text") or "").strip() != body_text:
        latest_version = _create_sales_room_proposal_version(
            cur,
            room_id=str(room.get("id") or ""),
            body_text=body_text,
            author_name=business_name,
            author_contact="",
            metadata={
                "source": "partner_audit_rollout",
                "lead_id": lead_id,
                "audit_profile": audit_json.get("audit_profile"),
            },
        )
    cur.execute(
        """
        UPDATE sales_rooms
        SET data_mode = %s,
            audit_public_url = NULL,
            workstream_id = NULLIF(%s, '')::uuid,
            proposal_json = %s,
            room_json = %s,
            updated_at = NOW()
        WHERE id = %s
        RETURNING *
        """,
        (
            SALES_ROOM_DATA_TEMPLATE,
            workstream_id,
            Json(proposal_json),
            Json(room_json),
            str(room.get("id") or ""),
        ),
    )
    room = _row_to_dict(cur.fetchone())
    room["public_url"] = _make_sales_room_url(str(room.get("slug") or ""))
    room["room_json"] = room_json
    invitation_text = _build_sales_room_invitation_text(
        mode=SALES_ROOM_MODE_PARTNER,
        data_mode=SALES_ROOM_DATA_TEMPLATE,
        business_name=business_name,
        lead_name=lead_name,
        room_url=room["public_url"],
    )
    if opener and opener not in invitation_text:
        invitation_text = f"{opener}\n\n{invitation_text}"
    draft = _create_sales_room_invitation_draft(
        cur,
        lead_id=lead_id,
        room_id=str(room.get("id") or ""),
        mode=SALES_ROOM_MODE_PARTNER,
        data_mode=SALES_ROOM_DATA_TEMPLATE,
        channel=channel,
        text=invitation_text,
        user_id=user_id,
        workstream_id=workstream_id,
    )
    _record_sales_room_event_by_id(
        cur,
        room_id=str(room.get("id") or ""),
        event_type="partner_audit_room_updated",
        metadata={
            "lead_id": lead_id,
            "proposal_version": latest_version.get("version_no"),
            "audit_profile": audit_json.get("audit_profile"),
        },
    )
    return room, draft

def _refresh_existing_client_sales_room(
    cur,
    *,
    user_id: str,
    lead: dict[str, Any],
    business_profile: dict[str, Any],
    channel: str,
    workstream_id: str,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    lead_id = str(lead.get("id") or "").strip()
    cur.execute(
        """
        SELECT *
        FROM sales_rooms
        WHERE lead_id = %s
          AND mode = %s
          AND (workstream_id = NULLIF(%s, '')::uuid OR workstream_id IS NULL)
        ORDER BY created_at ASC
        LIMIT 1
        FOR UPDATE
        """,
        (lead_id, SALES_ROOM_MODE_CLIENT, workstream_id),
    )
    room = _row_to_dict(cur.fetchone())
    if not room:
        return None

    business_name = _pick_business_display_name(business_profile)
    lead_name = str(lead.get("name") or "компания").strip() or "компания"
    proposal_json = _build_sales_room_proposal(
        mode=SALES_ROOM_MODE_CLIENT,
        data_mode=SALES_ROOM_DATA_TEMPLATE,
        lead=lead,
        business_name=business_name,
        business_profile=business_profile,
    )
    body_text = str(proposal_json.get("body_text") or "").strip()
    generated_room_json = _build_sales_room_payload(
        mode=SALES_ROOM_MODE_CLIENT,
        data_mode=SALES_ROOM_DATA_TEMPLATE,
        lead=lead,
        business_profile=business_profile,
        audit_public_url=str(room.get("audit_public_url") or ""),
        audit_json={},
        match_json={},
        proposal_json=proposal_json,
        slug=str(room.get("slug") or ""),
    )
    room_json = room.get("room_json") if isinstance(room.get("room_json"), dict) else {}
    room_json = {**room_json, **generated_room_json}
    latest_version = _ensure_sales_room_proposal_version(
        cur,
        room_id=str(room.get("id") or ""),
        body_text=str((room.get("proposal_json") or {}).get("body_text") or ""),
        author_name=business_name,
        metadata={"source": "existing_room_proposal"},
    )
    if str(latest_version.get("body_text") or "").strip() != body_text:
        latest_version = _create_sales_room_proposal_version(
            cur,
            room_id=str(room.get("id") or ""),
            body_text=body_text,
            author_name=business_name,
            author_contact="",
            metadata={"source": "codex_public_research", "lead_id": lead_id},
        )
    cur.execute(
        """
        UPDATE sales_rooms
        SET workstream_id = NULLIF(%s, '')::uuid,
            proposal_json = %s,
            room_json = %s,
            updated_at = NOW()
        WHERE id = %s
        RETURNING *
        """,
        (workstream_id, Json(proposal_json), Json(room_json), str(room.get("id") or "")),
    )
    room = _row_to_dict(cur.fetchone())
    room["public_url"] = _make_sales_room_url(str(room.get("slug") or ""))
    room["room_json"] = room_json
    invitation_text = _build_sales_room_invitation_text(
        mode=SALES_ROOM_MODE_CLIENT,
        data_mode=SALES_ROOM_DATA_TEMPLATE,
        business_name=business_name,
        lead_name=lead_name,
        room_url=room["public_url"],
    )
    research = lead.get("research") if isinstance(lead.get("research"), dict) else {}
    opener = str(research.get("suggested_opener") or "").strip()
    if opener and opener not in invitation_text:
        invitation_text = f"{opener}\n\n{invitation_text}"
    draft = _create_sales_room_invitation_draft(
        cur,
        lead_id=lead_id,
        room_id=str(room.get("id") or ""),
        mode=SALES_ROOM_MODE_CLIENT,
        data_mode=SALES_ROOM_DATA_TEMPLATE,
        channel=channel,
        text=invitation_text,
        user_id=user_id,
        workstream_id=workstream_id,
    )
    _record_sales_room_event_by_id(
        cur,
        room_id=str(room.get("id") or ""),
        event_type="lead_research_room_updated",
        metadata={"lead_id": lead_id, "proposal_version": latest_version.get("version_no")},
    )
    return room, draft

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
    workstream_id: str | None = None,
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
        business_profile=business_profile,
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
            id, slug, business_id, mode, lead_id, workstream_id, partner_card_id,
            data_mode, audit_public_url, match_json, proposal_json, room_json,
            status, visibility, created_by, created_at, updated_at
        ) VALUES (
            %s, %s, %s, %s, %s, NULLIF(%s, '')::uuid, NULLIF(%s, '')::uuid,
            %s, %s, %s, %s, %s,
            'ready', 'shared', NULLIF(%s, '')::uuid, NOW(), NOW()
        )
        RETURNING *
        """,
        (
            room_id,
            slug,
            business_id,
            mode,
            lead_id or None,
            workstream_id or "",
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
    research = lead.get("research") if isinstance(lead.get("research"), dict) else {}
    opener = str(research.get("suggested_opener") or "").strip()
    if opener and opener not in invitation_text:
        invitation_text = f"{opener}\n\n{invitation_text}"
    draft = _create_sales_room_invitation_draft(
        cur,
        lead_id=lead_id,
        room_id=room_id,
        mode=mode,
        data_mode=data_mode,
        channel=channel,
        text=invitation_text,
        user_id=user_id,
        workstream_id=workstream_id,
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
    audit_offer: dict[str, Any] | None = None,
    reuse_existing: bool = False,
    workstream_id: str | None = None,
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
        workstream = resolve_workstream(
            conn,
            lead_id=lead_id,
            workstream_id=workstream_id or str(lead.get("active_workstream_id") or ""),
            expected_type=CLIENT_PARTNERSHIP,
            client_business_id=business_id,
        )
        resolved_workstream_id = str(workstream.get("id") or "")
        research = load_latest_research(conn, resolved_workstream_id)
        if research:
            lead["research"] = research
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
        if (data_mode == SALES_ROOM_DATA_AUDITED or reuse_existing) and not audit_json:
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
            reason_codes = match_json.get("reason_codes") if isinstance(match_json, dict) else []
            if "SENDER_PROFILE_INCOMPLETE" in (reason_codes or []):
                conn.rollback()
                return {
                    "error": "Сначала заполните профиль отправителя для партнёрского аутрича.",
                    "code": "SENDER_PROFILE_INCOMPLETE",
                    "profile_completeness": match_json.get("profile_completeness") or {},
                    "status_code": 422,
                }
            if _partnership_match_needs_evidence(match_json):
                conn.rollback()
                return {
                    "error": "Совместимость пока не подтверждена фактами.",
                    "code": "PARTNERSHIP_MATCH_NEEDS_EVIDENCE",
                    "result": match_json,
                    "status_code": 422,
                }
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
        existing_room_result = None
        if reuse_existing:
            existing_room_result = _refresh_existing_partnership_sales_room(
                cur,
                business_id=business_id,
                user_id=user_id,
                lead=lead,
                business_profile=business_profile,
                audit_json=audit_json,
                match_json=match_json,
                workstream_id=resolved_workstream_id,
                channel=channel,
            )
        if existing_room_result:
            room, draft = existing_room_result
        else:
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
                workstream_id=resolved_workstream_id,
            )
        if isinstance(audit_offer, dict) and audit_offer:
            _upsert_sales_room_audit_offer(cur, room=room, data=audit_offer)
        billing = {"status": "not_required", "credit_charged": False, "charged_credits": 0}
        if data_mode == SALES_ROOM_DATA_AUDITED:
            billing = _finalize_sales_room_credit(
                cur,
                reservation=reservation,
                business_id=business_id,
                user_id=user_id,
                room_id=str(room.get("id") or ""),
            )
        if not existing_room_result:
            cur.execute(
                """
                UPDATE prospectingleads
                SET partnership_stage = %s,
                    updated_at = NOW()
                WHERE id = %s
                """,
                ("proposal_draft_ready", lead_id),
            )
        update_workstream(
            conn,
            workstream_id=resolved_workstream_id,
            status=PIPELINE_IN_PROGRESS,
            selected_channel=channel,
        )
        conn.commit()
        return {
            "success": True,
            "room": room,
            "draft": _serialize_draft(draft) if draft else None,
            "billing": billing,
            "reused": bool(existing_room_result),
        }
    finally:
        conn.close()

def _prepare_client_sales_room(
    *,
    lead_id: str,
    user_id: str,
    data_mode: str,
    channel: str,
    audit_offer: dict[str, Any] | None = None,
    workstream_id: str | None = None,
    reuse_existing: bool = False,
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
        workstream = resolve_workstream(
            conn,
            lead_id=lead_id,
            workstream_id=workstream_id,
            expected_type=LOCALOS_SALES,
        )
        resolved_workstream_id = str(workstream.get("id") or "")
        display_lead = _normalize_lead_for_display(dict(lead))
        if not display_lead:
            return {"error": "Lead is not available for room", "status_code": 400}
        research = load_latest_research(conn, resolved_workstream_id)
        if research:
            display_lead["research"] = research
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
        existing_room_result = None
        if reuse_existing:
            existing_room_result = _refresh_existing_client_sales_room(
                cur,
                user_id=user_id,
                lead=display_lead,
                business_profile=business_profile,
                channel=channel,
                workstream_id=resolved_workstream_id,
            )
        if existing_room_result:
            room, draft = existing_room_result
        else:
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
                workstream_id=resolved_workstream_id,
            )
        if isinstance(audit_offer, dict) and audit_offer:
            _upsert_sales_room_audit_offer(cur, room=room, data=audit_offer)
        billing = {"status": "not_required", "credit_charged": False, "charged_credits": 0}
        if data_mode == SALES_ROOM_DATA_AUDITED:
            billing = _finalize_sales_room_credit(
                cur,
                reservation=reservation,
                business_id=business_id,
                user_id=user_id,
                room_id=str(room.get("id") or ""),
            )
        update_workstream(
            conn,
            workstream_id=resolved_workstream_id,
            status=PIPELINE_IN_PROGRESS,
            selected_channel=channel,
        )
        conn.commit()
        return {
            "success": True,
            "room": room,
            "draft": _serialize_draft(draft),
            "billing": billing,
            "reused": bool(existing_room_result),
        }
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
