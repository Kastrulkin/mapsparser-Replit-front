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
from services.outreach_sender_profile_service import evaluate_sender_profile_completeness
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


_MATCH_TOKEN_SUFFIXES = (
    "иями", "ями", "ами", "ого", "ему", "ому", "ыми", "ими", "иях",
    "ах", "ях", "ий", "ый", "ая", "яя", "ое", "ее", "ые", "ие",
    "ой", "ей", "ам", "ям", "ом", "ем", "ов", "ев", "а", "я",
    "ы", "и", "у", "ю", "е", "о",
)
_AUDIENCE_MARKERS = {
    "families_with_children": ("дет", "ребен", "ребён", "родител", "семей", "подрост"),
    "health": ("медицин", "клиник", "врач", "здоров", "стомат", "реабилит", "анализ"),
    "beauty": ("красот", "космет", "волос", "парикмах", "маник", "педик", "бьюти", "спа"),
    "sport": ("спорт", "фитнес", "танц", "йога", "бассейн", "секци", "трениров"),
    "pets": ("ветеринар", "питом", "животн", "собак", "кошк"),
    "food": ("ресторан", "кафе", "еда", "питан", "пекар", "доставк"),
    "events": ("праздник", "свадеб", "фото", "мероприят", "развлеч"),
    "education": ("обучен", "образован", "школ", "курс", "репетитор", "язык"),
}


def _normalized_match_tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    for raw in _tokenize_match_text(text):
        token = raw.replace("ё", "е")
        for suffix in _MATCH_TOKEN_SUFFIXES:
            if token.endswith(suffix) and len(token) - len(suffix) >= 4:
                token = token[:-len(suffix)]
                break
        if len(token) >= 4 and not token.isdigit():
            tokens.add(token)
    return tokens


def _audience_tags(text: str) -> set[str]:
    normalized = str(text or "").lower().replace("ё", "е")
    return {
        tag
        for tag, markers in _AUDIENCE_MARKERS.items()
        if any(marker.replace("ё", "е") in normalized for marker in markers)
    }

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

    reason_codes = [
        str(item).strip()
        for item in data.get("reason_codes") or []
        if str(item or "").strip()
    ]
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

    sender_profile_incomplete = "SENDER_PROFILE_INCOMPLETE" in reason_codes
    source_url = str(data.get("source_url") or "").strip() or None
    recipient_observation = str(data.get("recipient_observation") or "").strip() or None
    if sender_profile_incomplete:
        readiness_code = "needs_sender_profile"
        next_action = "Заполните и подтвердите профиль отправителя"
    elif score < 40 or not recipient_observation or not str(source_url or "").lower().startswith(("http://", "https://")):
        readiness_code = "needs_evidence"
        next_action = "Соберите недостающие публичные факты и повторите проверку"
    else:
        readiness_code = "ready"
        next_action = "Проверьте предложение и подготовьте цепочку касаний"

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
        "recipient_observation": recipient_observation,
        "compatibility_hypothesis": str(data.get("compatibility_hypothesis") or "").strip() or None,
        "relevance_bridge": str(data.get("relevance_bridge") or "").strip() or None,
        "source_url": source_url,
        "score_breakdown": data.get("score_breakdown") if isinstance(data.get("score_breakdown"), dict) else {},
        "profile_completeness": data.get("profile_completeness") if isinstance(data.get("profile_completeness"), dict) else {},
        "direct_competitor": bool(data.get("direct_competitor")),
        "readiness_code": readiness_code,
        "next_action": next_action,
    }
    return normalized


def _partnership_match_needs_evidence(match: dict[str, Any] | None) -> bool:
    data = match if isinstance(match, dict) else {}
    try:
        score = int(data.get("match_score") or 0)
    except (TypeError, ValueError):
        score = 0
    source_url = str(data.get("source_url") or "").strip().lower()
    return (
        score < 40
        or not str(data.get("recipient_observation") or "").strip()
        or not source_url.startswith(("http://", "https://"))
    )


def _save_partnership_match_assessment(
    cur,
    *,
    lead_id: str,
    audit_json: dict[str, Any],
    match_result: dict[str, Any],
) -> None:
    """Persist a visible assessment without promoting the lead to matched."""

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

    if str(lead.get("parsed_identity_status") or "").strip().lower() == "mismatch":
        candidate_name = str(lead.get("parsed_candidate_name") or "другая компания").strip()
        return {
            "code": "repair_recipient_identity_mapping",
            "label": "Найти правильную карточку компании",
            "hint": f"Сейчас к лиду привязана карточка «{candidate_name}». LocalOS выполнит поиск заново перед парсингом.",
            "priority": "high",
        }

    if parse_status == "captcha":
        return {
            "code": "resolve_captcha",
            "label": "Пройти CAPTCHA",
            "hint": "Парсинг остановился и ждёт human-in-the-loop.",
            "priority": "high",
        }
    if parse_status == "error":
        parse_error = str(lead.get("parse_error") or "").strip().lower()
        if "business_closed" in parse_error or "permanent_closed" in parse_error:
            return {
                "code": "mark_closed_not_relevant",
                "label": "Компания закрыта — отметить неактуальной",
                "hint": "Повторный парсинг не поможет: публичная карточка сообщает о закрытии компании.",
                "priority": "high",
            }
        if "apify_empty_dataset" in parse_error or "empty dataset" in parse_error:
            return {
                "code": "find_alternate_public_source",
                "label": "Найти другой публичный источник",
                "hint": "Карточка не вернула данные после повторной проверки. Нужна другая ссылка на карты, официальный сайт или ручное подтверждение фактов.",
                "priority": "high",
            }
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
        if _partnership_source_requires_map_match(lead.get("source_url")):
            return {
                "code": "resolve_and_parse",
                "label": "Найти карточку и собрать данные",
                "hint": "LocalOS сначала подтвердит карточку компании на карте, затем соберёт услуги и контакты.",
                "priority": "high",
            }
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
    cur.execute(
        """
        SELECT * FROM outreach_sender_profiles
        WHERE workstream_type = 'client_partnership'
          AND client_business_id = %s AND is_active = TRUE
        LIMIT 1
        """,
        (business_id,),
    )
    sender_row = cur.fetchone()
    sender_profile = dict(sender_row) if sender_row else {}
    profile_completeness = evaluate_sender_profile_completeness(
        sender_profile,
        workstream_type="client_partnership",
        business_service_count=len(own_services),
    )
    if not sender_profile.get("confirmed_at") or not profile_completeness["ready"]:
        return _normalize_match_result(
            {
                "match_score": 0,
                "reason_codes": ["SENDER_PROFILE_INCOMPLETE"],
                "profile_completeness": profile_completeness,
                "risks": ["Сначала заполните профиль отправителя и желаемые типы партнёров."],
            },
            own_services_count=len(own_services),
            partner_services_count=len(partner_services),
        )

    cur.execute(
        """
        SELECT name, category, city, address, source_url, website, updated_at
        FROM prospectingleads WHERE id = %s LIMIT 1
        """,
        (lead_id,),
    )
    lead_row = cur.fetchone()
    lead = dict(lead_row) if lead_row else {}
    sender_context = (
        sender_profile.get("outreach_context_json")
        if isinstance(sender_profile.get("outreach_context_json"), dict)
        else {}
    )
    desired_partner_types = [
        str(item).strip()
        for item in sender_context.get("desired_partner_types") or []
        if str(item or "").strip()
    ]
    recipient_descriptor = " ".join([
        str(lead.get("category") or ""),
        " ".join(partner_services),
    ]).strip()
    recipient_tokens = _normalized_match_tokens(recipient_descriptor)
    matched_partner_types: list[str] = []
    for desired_type in desired_partner_types:
        desired_tokens = _normalized_match_tokens(desired_type)
        if desired_tokens and len(desired_tokens.intersection(recipient_tokens)) / len(desired_tokens) >= 0.5:
            matched_partner_types.append(desired_type)

    audience_text = " ".join([
        str(sender_context.get("audience") or ""),
        " ".join(str(item) for item in sender_context.get("segments") or []),
    ])
    common_audience_tags = sorted(_audience_tags(audience_text).intersection(_audience_tags(recipient_descriptor)))
    geography_tokens = _normalized_match_tokens(str(sender_context.get("geography") or ""))
    recipient_geography_tokens = _normalized_match_tokens(
        " ".join([str(lead.get("city") or ""), str(lead.get("address") or "")])
    )
    geography_match = bool(geography_tokens.intersection(recipient_geography_tokens))

    own_tokens = _normalized_match_tokens(" ".join(own_services))
    partner_tokens = _normalized_match_tokens(" ".join(partner_services))
    overlap_tokens = sorted(own_tokens.intersection(partner_tokens))
    overlap_ratio = len(overlap_tokens) / max(1, min(len(own_tokens), len(partner_tokens)))
    direct_competitor = overlap_ratio >= 0.35 and not matched_partner_types
    public_source_url = ""
    for source_candidate in (lead.get("source_url"), lead.get("website")):
        normalized_source = str(source_candidate or "").strip()
        if normalized_source.lower().startswith(("http://", "https://")):
            public_source_url = normalized_source
            break
    score_breakdown = {
        "desired_partner_type": 45 if matched_partner_types else 0,
        "audience_overlap_hypothesis": 20 if common_audience_tags else 0,
        "geography": 15 if geography_match else 0,
        "public_service_evidence": 10 if public_source_url and (partner_services or lead.get("category")) else 0,
        "service_complement": 10 if (matched_partner_types or common_audience_tags) and overlap_ratio < 0.2 else 0,
        "competition_penalty": -35 if direct_competitor else 0,
    }
    score = max(0, min(100, sum(score_breakdown.values())))
    recipient_observation_parts = []
    if public_source_url and lead.get("category"):
        recipient_observation_parts.append(
            f"В публичной карточке указана категория «{str(lead.get('category')).strip()}»"
        )
    if public_source_url and partner_services:
        recipient_observation_parts.append(
            "указаны услуги: " + ", ".join(partner_services[:3])
        )
    recipient_observation = "; ".join(recipient_observation_parts)
    if recipient_observation:
        recipient_observation += "."
    hypothesis_parts = []
    if matched_partner_types:
        hypothesis_parts.append(
            "компания соответствует указанному типу партнёров "
            + ", ".join(matched_partner_types[:2])
        )
    if common_audience_tags:
        hypothesis_parts.append("у компаний может пересекаться аудитория")
    compatibility_hypothesis = (
        "Гипотеза для проверки: " + "; ".join(hypothesis_parts) + "."
        if hypothesis_parts else ""
    )
    relevance_bridge = (
        "Это соответствует подтверждённому профилю партнёрского поиска и подходит для одного безопасного совместного теста."
        if score >= 40 else ""
    )
    match_result: dict[str, Any] | None = None
    deterministic_result = {
        "match_score": score,
        "overlap": overlap_tokens[:30],
        "complement": {
            "our_strength_tokens": sorted(list(own_tokens - partner_tokens))[:30],
            "partner_strength_tokens": sorted(list(partner_tokens - own_tokens))[:30],
        },
        "risks": [
            "Низкая точность, если у партнёра мало структурированных услуг."
            if not partner_services
            else "Проверьте каннибализацию по пересекающимся услугам."
        ],
        "offer_angles": ["Один безопасный совместный тест"],
        "recipient_observation": recipient_observation,
        "compatibility_hypothesis": compatibility_hypothesis,
        "relevance_bridge": relevance_bridge,
        "source_url": public_source_url,
        "score_breakdown": score_breakdown,
        "profile_completeness": profile_completeness,
        "direct_competitor": direct_competitor,
        "reason_codes": [
            "DESIRED_PARTNER_TYPE_MATCH" if matched_partner_types else "DESIRED_PARTNER_TYPE_MISSING",
            "AUDIENCE_OVERLAP_HYPOTHESIS" if common_audience_tags else "AUDIENCE_OVERLAP_MISSING",
        ],
    }

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
                match_result = dict(candidate_match)

    if not match_result:
        match_result = deterministic_result
    else:
        # AI may improve wording and angles, but it cannot replace the deterministic
        # score, sender-profile gate, or sourced recipient observation.
        ai_reason_codes = match_result.get("reason_codes")
        if not isinstance(ai_reason_codes, list):
            ai_reason_codes = []
        match_result.update({
            "match_score": deterministic_result["match_score"],
            "overlap": deterministic_result["overlap"],
            "recipient_observation": deterministic_result["recipient_observation"],
            "compatibility_hypothesis": deterministic_result["compatibility_hypothesis"],
            "relevance_bridge": deterministic_result["relevance_bridge"],
            "source_url": deterministic_result["source_url"],
            "score_breakdown": deterministic_result["score_breakdown"],
            "profile_completeness": deterministic_result["profile_completeness"],
            "direct_competitor": deterministic_result["direct_competitor"],
            "reason_codes": list(deterministic_result["reason_codes"]) + ai_reason_codes,
        })

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
            lead = _sync_partnership_lead_from_parsed_data(lead)
            if str(lead.get("parsed_identity_status") or "") == "mismatch":
                conn.rollback()
                return jsonify({
                    "error": "К лиду привязана карточка другой компании.",
                    "code": "PARTNER_RECIPIENT_IDENTITY_MISMATCH",
                    "candidate_name": lead.get("parsed_candidate_name"),
                    "next_action": "rerun_parse_to_rematch",
                }), 409
            snapshot = build_lead_card_preview_snapshot(lead)
            snapshot = _to_json_compatible(snapshot)
            quality = evaluate_audit_quality(
                snapshot,
                expected_name=str(lead.get("name") or ""),
                expected_address=str(lead.get("address") or ""),
            )
            if not quality.get("passed"):
                conn.rollback()
                return jsonify(
                    {
                        "error": "Аудит не прошёл проверку качества.",
                        "code": "AUDIT_QUALITY_BLOCKED",
                        "quality": quality,
                    }
                ), 422
            _ensure_admin_prospecting_public_offers_table(conn)
            audit_slug, audit_url, page_json = _create_admin_public_audit_for_lead(
                cur,
                lead=lead,
                user_id=str(user_data.get("user_id") or ""),
                source_type="partnership_partner",
            )
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
        return jsonify(
            {
                "success": True,
                "snapshot": snapshot,
                "audit_slug": audit_slug,
                "audit_url": audit_url,
                "audit_profile": snapshot.get("audit_profile"),
                "quality": quality,
                "page": page_json,
            }
        )
    except AuditQualityError as quality_error:
        return jsonify(
            {
                "error": "Аудит не прошёл проверку качества.",
                "code": "AUDIT_QUALITY_BLOCKED",
                "quality": quality_error.quality,
            }
        ), 422
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
            lead = _sync_partnership_lead_from_parsed_data(lead)
            if str(lead.get("parsed_identity_status") or "") == "mismatch":
                conn.rollback()
                return jsonify({
                    "error": "К лиду привязана карточка другой компании.",
                    "code": "PARTNER_RECIPIENT_IDENTITY_MISMATCH",
                    "candidate_name": lead.get("parsed_candidate_name"),
                    "next_action": "rerun_parse_to_rematch",
                }), 409

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
            if "SENDER_PROFILE_INCOMPLETE" in (match_result.get("reason_codes") or []):
                _save_partnership_match_assessment(
                    cur,
                    lead_id=lead_id,
                    audit_json=audit_json,
                    match_result=match_result,
                )
                conn.commit()
                return jsonify({
                    "success": True,
                    "status": "needs_sender_profile",
                    "code": "SENDER_PROFILE_INCOMPLETE",
                    "result": match_result,
                    "profile_completeness": match_result.get("profile_completeness") or {},
                    "next_action": match_result.get("next_action"),
                })
            if _partnership_match_needs_evidence(match_result):
                _save_partnership_match_assessment(
                    cur,
                    lead_id=lead_id,
                    audit_json=audit_json,
                    match_result=match_result,
                )
                conn.commit()
                return jsonify({
                    "success": True,
                    "status": "needs_evidence",
                    "code": "PARTNERSHIP_MATCH_NEEDS_EVIDENCE",
                    "result": match_result,
                    "next_action": match_result.get("next_action"),
                })

            _save_partnership_match_assessment(
                cur,
                lead_id=lead_id,
                audit_json=audit_json,
                match_result=match_result,
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
            assessment_count = 0
            skipped_count = 0
            results: list[dict[str, Any]] = []
            errors: list[dict[str, Any]] = []
            needs_attention: list[dict[str, Any]] = []

            for lead_id in normalized_ids:
                lead = _load_partnership_lead(cur, lead_id=lead_id, business_id=business_id)
                if not lead:
                    skipped_count += 1
                    errors.append({"lead_id": lead_id, "error": "Lead not found"})
                    continue
                lead = _sync_partnership_lead_from_parsed_data(lead)
                if str(lead.get("parsed_identity_status") or "") == "mismatch":
                    skipped_count += 1
                    errors.append({
                        "lead_id": lead_id,
                        "code": "PARTNER_RECIPIENT_IDENTITY_MISMATCH",
                        "error": "К лиду привязана карточка другой компании.",
                        "candidate_name": lead.get("parsed_candidate_name"),
                        "next_action": "rerun_parse_to_rematch",
                    })
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
                    if "SENDER_PROFILE_INCOMPLETE" in (match_result.get("reason_codes") or []):
                        _save_partnership_match_assessment(
                            cur,
                            lead_id=lead_id,
                            audit_json=audit_json,
                            match_result=match_result,
                        )
                        assessment_count += 1
                        skipped_count += 1
                        needs_attention.append({
                            "lead_id": lead_id,
                            "code": "SENDER_PROFILE_INCOMPLETE",
                            "next_action": match_result.get("next_action"),
                            "profile_completeness": match_result.get("profile_completeness") or {},
                        })
                        continue
                    if _partnership_match_needs_evidence(match_result):
                        _save_partnership_match_assessment(
                            cur,
                            lead_id=lead_id,
                            audit_json=audit_json,
                            match_result=match_result,
                        )
                        assessment_count += 1
                        skipped_count += 1
                        needs_attention.append({
                            "lead_id": lead_id,
                            "code": "PARTNERSHIP_MATCH_NEEDS_EVIDENCE",
                            "next_action": match_result.get("next_action"),
                            "result": match_result,
                        })
                        continue
                    _save_partnership_match_assessment(
                        cur,
                        lead_id=lead_id,
                        audit_json=audit_json,
                        match_result=match_result,
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
                    "assessment_count": assessment_count,
                    "skipped_count": skipped_count,
                    "results": results,
                    "needs_attention": needs_attention,
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
            if payload:
                payload = normalize_public_audit_page_json(payload, slug=normalized_slug)
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

            from services.contact_intelligence_service import enqueue_enrichment_job
            from services.lead_workstream_service import resolve_workstream

            workstream_id = str(data.get("workstream_id") or "").strip() or None
            workstream = resolve_workstream(
                conn,
                lead_id=lead_id,
                workstream_id=workstream_id,
                expected_type="client_partnership",
                client_business_id=business_id,
            )
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
                }
            ), 202

        finally:
            conn.close()
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

            from services.contact_intelligence_service import enqueue_enrichment_job

            cur.execute(
                """
                SELECT id, lead_id
                FROM lead_workstreams
                WHERE lead_id = ANY(%s)
                  AND workstream_type = 'client_partnership'
                  AND client_business_id = %s
                """,
                (normalized_ids, business_id),
            )
            workstreams = [dict(row) for row in cur.fetchall() or []]
            jobs = []
            for workstream in workstreams:
                job = enqueue_enrichment_job(
                    cur,
                    str(workstream.get("id")),
                    allow_paid_enrichment=bool(data.get("allow_paid_enrichment")),
                )
                jobs.append(
                    {
                        "id": str(job.get("id")),
                        "lead_id": str(workstream.get("lead_id")),
                        "status": job.get("status"),
                        "reused": bool(job.get("reused")),
                    }
                )
            conn.commit()
        finally:
            conn.close()

        return jsonify(
            {
                "success": True,
                "accepted": True,
                "queued_count": sum(1 for job in jobs if not job.get("reused")),
                "reused_count": sum(1 for job in jobs if job.get("reused")),
                "jobs": jobs,
            }
        ), 202
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
            if letter_type == "first_note":
                from services.contact_intelligence_service import enqueue_enrichment_job
                from services.lead_workstream_service import resolve_workstream

                workstream = resolve_workstream(
                    conn,
                    lead_id=lead_id,
                    workstream_id=str(data.get("workstream_id") or "").strip() or None,
                    expected_type="client_partnership",
                    client_business_id=business_id,
                )
                job = enqueue_enrichment_job(
                    cur,
                    str(workstream.get("id")),
                    allow_paid_enrichment=bool(data.get("allow_paid_enrichment")),
                )
                conn.commit()
                return jsonify(
                    {
                        "success": True,
                        "accepted": True,
                        "job": {
                            "id": str(job.get("id")),
                            "status": job.get("status"),
                            "phase": job.get("current_phase"),
                        },
                        "message": "Первое письмо будет создано после проверки контакта и оснований",
                    }
                ), 202

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
