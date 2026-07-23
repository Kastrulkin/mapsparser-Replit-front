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
from services.telegram_account_permissions_service import assert_account_access
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
ALLOWED_OUTREACH_CHANNELS = {"telegram", "whatsapp", "max", "email", "vk", "manual"}
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
        result_text = analyze_text_with_gigachat(prompt, task_type="lead_audit_enrichment")
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
            result_text = analyze_text_with_gigachat(retry_prompt, task_type="lead_audit_enrichment")
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
                "source": "deepseek",
                "prompt_key": "lead_audit_enrichment",
                "prompt_version": "v2",
                "prompt_source": "deepseek",
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
        "Структура: представьтесь как человек; назовите один проверяемый факт; "
        "предложите один конкретный результат; завершите одним простым вопросом.\n"
        "Не утверждай, что компания теряет клиентов. Не обещай рост, проценты или внедрение, "
        "если этого нет в подтверждённых фактах. Не вставляй ссылку на аудит в первое касание.\n"
        "Максимум 90 слов.\n"
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
    from services.outreach_dispatch_service import dispatch_due_outreach_queue as _dispatch_due_outreach_queue

    return _dispatch_due_outreach_queue(batch_size=batch_size, batch_id=batch_id, force_ready=force_ready)

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

def _resolve_telegram_app_account(account_id: str) -> dict[str, Any] | None:
    if not str(account_id or "").strip():
        return None
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
    return {
        "configured": None,
        "authorized": None,
        "phone": None,
        "account_id": None,
        "status": "sender_account_required",
        "message": "Статус проверяется для конкретного sender_account_id кампании",
    }


def _resolve_telegram_sender(sender_account_id: str) -> tuple[dict[str, Any] | None, str]:
    if not sender_account_id:
        return None, "sender_account_required"
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, scope_type, business_id, external_account_id, status
            FROM outreach_sender_accounts
            WHERE id = %s AND channel = 'telegram'
            """,
            (sender_account_id,),
        )
        row = cur.fetchone()
        if not row:
            return None, "sender_account_missing"
        sender = dict(row)
        if str(sender.get("status") or "") != "connected":
            return None, "sender_account_disabled"
        external_account_id = str(sender.get("external_account_id") or "")
        allowed, reason, _context = assert_account_access(
            cur,
            external_account_id,
            business_id=str(sender.get("business_id") or "") or None,
            scope_type=str(sender.get("scope_type") or "business"),
            capability="outreach",
        )
        if not allowed:
            return None, reason
        account = load_userbot_account(
            cur,
            business_id=str(sender.get("business_id") or "") or None,
            account_id=external_account_id,
        )
        return account, "ready" if account else "sender_account_missing"
    finally:
        conn.close()


def _resolve_email_sender(sender_account_id: str) -> tuple[dict[str, Any] | None, str]:
    if not sender_account_id:
        return None, "sender_account_required"
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT * FROM outreach_sender_accounts
            WHERE id = %s AND channel = 'email'
            """,
            (sender_account_id,),
        )
        row = cur.fetchone()
        if not row:
            return None, "sender_account_missing"
        sender = dict(row)
        if str(sender.get("status") or "") != "connected":
            return None, "sender_account_disabled"
        if not bool(sender.get("outreach_enabled")):
            return None, "sender_permission_revoked"
        if sender.get("health_status") in {"paused", "blocked"}:
            return None, f"sender_{sender.get('health_status')}"
        capabilities = sender.get("capabilities_json") or {}
        if (
            not isinstance(capabilities, dict)
            or not capabilities.get("direct_send")
            or not capabilities.get("reply_sync")
        ):
            return None, "sender_adapter_incomplete"
        return sender, "ready"
    finally:
        conn.close()


def _resolve_vk_sender(sender_account_id: str) -> tuple[dict[str, Any] | None, str]:
    if not sender_account_id:
        return None, "sender_account_required"
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT * FROM outreach_sender_accounts
            WHERE id = %s AND channel = 'vk'
            """,
            (sender_account_id,),
        )
        row = cur.fetchone()
        if not row:
            return None, "sender_account_missing"
        sender = dict(row)
        if str(sender.get("status") or "") != "connected":
            return None, "sender_account_disabled"
        if not bool(sender.get("outreach_enabled")):
            return None, "sender_permission_revoked"
        if sender.get("health_status") in {"paused", "blocked"}:
            return None, f"sender_{sender.get('health_status')}"
        capabilities = sender.get("capabilities_json") or {}
        if (
            not isinstance(capabilities, dict)
            or not capabilities.get("direct_send")
            or not capabilities.get("reply_sync")
        ):
            return None, "sender_adapter_incomplete"
        from services.outreach_vk_adapter import ensure_vk_outreach_config

        _config, refreshed_encrypted = ensure_vk_outreach_config(sender)
        if refreshed_encrypted:
            cur.execute(
                """
                UPDATE outreach_sender_accounts
                SET auth_data_encrypted = %s, updated_at = NOW()
                WHERE id = %s
                """,
                (refreshed_encrypted, sender_account_id),
            )
            conn.commit()
            sender["auth_data_encrypted"] = refreshed_encrypted
        return sender, "ready"
    finally:
        conn.close()


def _dispatch_via_vk_sender(item: dict[str, Any], message: str) -> dict[str, Any]:
    from services.outreach_vk_adapter import VkOutreachAdapterError, send_vk_message

    sender_account_id = str(item.get("sender_account_id") or "").strip()
    sender, sender_reason = _resolve_vk_sender(sender_account_id)
    capabilities = sender.get("capabilities_json") if isinstance(sender, dict) else {}
    provider_name = (
        str(capabilities.get("provider") or "vk_user_api")
        if isinstance(capabilities, dict)
        else "vk_user_api"
    )
    if not sender:
        return {
            "success": False,
            "error_code": sender_reason,
            "error_text": "A concrete permitted VK sender account is required",
            "provider_name": provider_name,
            "retryable": False,
        }
    try:
        return send_vk_message(
            sender,
            recipient_value=str(item.get("contact_value") or ""),
            body=message,
            idempotency_key=str(item.get("idempotency_key") or f"outreach:{item.get('id')}"),
        )
    except VkOutreachAdapterError as exc:
        return {
            "success": False,
            "error_code": exc.code,
            "error_text": str(exc),
            "provider_name": provider_name,
            "provider_account_id": sender_account_id,
            "recipient_kind": "vk",
            "recipient_value": str(item.get("contact_value") or "").strip() or None,
            "retryable": exc.retryable,
        }


def _dispatch_via_email_sender(item: dict[str, Any], message: str) -> dict[str, Any]:
    from services.outreach_email_adapter import EmailAdapterError, send_email

    sender_account_id = str(item.get("sender_account_id") or "").strip()
    sender, sender_reason = _resolve_email_sender(sender_account_id)
    if not sender:
        return {
            "success": False,
            "error_code": sender_reason,
            "error_text": "A concrete permitted email sender account is required",
            "provider_name": "native_email",
            "retryable": False,
        }
    try:
        return send_email(
            sender,
            recipient=str(item.get("email") or ""),
            subject=str(item.get("subject") or "").strip(),
            body=message,
            idempotency_key=str(item.get("idempotency_key") or f"outreach:{item.get('id')}"),
        )
    except EmailAdapterError as exc:
        return {
            "success": False,
            "error_code": exc.code,
            "error_text": str(exc),
            "provider_name": "native_email",
            "provider_account_id": sender_account_id,
            "recipient_kind": "email",
            "recipient_value": str(item.get("email") or "").strip() or None,
            "retryable": exc.retryable,
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
    sender_account_id = str(item.get("sender_account_id") or "").strip()
    account, sender_reason = _resolve_telegram_sender(sender_account_id)
    if not account:
        return {
            "success": False,
            "error_code": sender_reason,
            "error_text": "A concrete permitted Telegram sender account is required",
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

def _load_telegram_reply_sync_candidates(
    limit: int = 25,
    batch_id: str | None = None,
    sender_account_id: str | None = None,
) -> list[dict[str, Any]]:
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
                l.name AS lead_name,
                TRUE AS outreach_permission_checked,
                permission.outreach_enabled,
                sender.scope_type AS sender_scope_type,
                sender.business_id AS sender_business_id
            FROM outreachsendqueue q
            JOIN prospectingleads l ON l.id = q.lead_id
            JOIN outreach_sender_accounts sender ON sender.id = q.sender_account_id
            JOIN externalbusinessaccounts account ON account.id = sender.external_account_id
            JOIN telegram_account_permissions permission ON permission.account_id = account.id
            WHERE q.provider_name = 'telegram_app'
              AND q.delivery_status IN (%s, %s)
              AND q.provider_account_id IS NOT NULL
              AND q.recipient_value IS NOT NULL
              AND q.sent_at >= NOW() - (%s || ' days')::interval
              AND sender.status = 'connected'
              AND account.is_active = TRUE
              AND permission.outreach_enabled = TRUE
        """
        params: list[Any] = [QUEUE_STATUS_SENT, QUEUE_STATUS_DELIVERED, TELEGRAM_REPLY_SYNC_LOOKBACK_DAYS]
        if batch_id:
            query += " AND q.batch_id = %s"
            params.append(batch_id)
        if sender_account_id:
            query += " AND q.sender_account_id = %s"
            params.append(sender_account_id)
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
    account = _resolve_telegram_app_account(provider_account_id)
    if not account:
        return {"status": "failed", "reason": "telegram_app_missing", "imported": 0, "duplicates": 0}

    if item.get("outreach_permission_checked") and not bool(item.get("outreach_enabled")):
        return {"status": "failed", "reason": "outreach_permission_required", "imported": 0, "duplicates": 0}
    if not item.get("outreach_permission_checked") and account.get("business_id") is not None:
        permission_conn = get_db_connection()
        try:
            permission_cursor = permission_conn.cursor()
            allowed, reason, _context = assert_account_access(
                permission_cursor,
                provider_account_id,
                business_id=str(account.get("business_id") or "") or None,
                scope_type=str(item.get("sender_scope_type") or "business"),
                capability="outreach",
            )
            if not allowed:
                return {"status": "failed", "reason": reason, "imported": 0, "duplicates": 0}
        finally:
            permission_conn.close()

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

def _sync_telegram_app_replies(
    batch_id: str | None = None,
    limit: int = 25,
    sender_account_id: str | None = None,
) -> dict[str, Any]:
    items = _load_telegram_reply_sync_candidates(
        limit=limit,
        batch_id=batch_id,
        sender_account_id=sender_account_id,
    )
    summary = {
        "success": True,
        "batch_id": batch_id,
        "sender_account_id": sender_account_id,
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
            "sender_account_id": item.get("sender_account_id"),
            "idempotency_key": item.get("idempotency_key") or f"outreach:{item.get('id')}",
        },
    }

    try:
        resp = requests.post(
            endpoint,
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Idempotency-Key": str(item.get("idempotency_key") or f"outreach:{item.get('id')}"),
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

    if channel == "email" and not str(item.get("sender_account_id") or "").strip():
        return {
            "delivery_status": QUEUE_STATUS_FAILED,
            "error_text": "sender_account_required: connect a sender mailbox before email outreach",
            "provider_name": "email",
            "retryable": False,
        }

    if channel == "vk" and not str(item.get("sender_account_id") or "").strip():
        return {
            "delivery_status": QUEUE_STATUS_FAILED,
            "error_text": "sender_account_required: connect a VK account before VK outreach",
            "provider_name": "vk_user_api",
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

    if channel == "email":
        email_result = _dispatch_via_email_sender(item, message)
        if email_result.get("success"):
            return {
                "delivery_status": QUEUE_STATUS_SENT,
                "provider_message_id": str(email_result.get("provider_message_id") or "")[:255] or None,
                "provider_name": str(email_result.get("provider_name") or "native_email"),
                "provider_account_id": str(email_result.get("provider_account_id") or "")[:255] or None,
                "recipient_kind": "email",
                "recipient_value": str(email_result.get("recipient_value") or "")[:255] or None,
                "error_text": None,
                "retryable": False,
            }
        return {
            "delivery_status": QUEUE_STATUS_FAILED,
            "provider_name": str(email_result.get("provider_name") or "native_email"),
            "provider_account_id": str(email_result.get("provider_account_id") or "")[:255] or None,
            "recipient_kind": "email",
            "recipient_value": str(email_result.get("recipient_value") or "")[:255] or None,
            "error_text": (
                f"{email_result.get('error_code')}: {email_result.get('error_text')}"
                if email_result.get("error_code") and email_result.get("error_text")
                else str(email_result.get("error_text") or "Email delivery failed")
            )[:500],
            "retryable": bool(email_result.get("retryable", False)),
        }

    if channel == "vk":
        vk_result = _dispatch_via_vk_sender(item, message)
        if vk_result.get("success"):
            return {
                "delivery_status": QUEUE_STATUS_SENT,
                "provider_message_id": str(vk_result.get("provider_message_id") or "")[:255] or None,
                "provider_name": "vk_user_api",
                "provider_account_id": str(vk_result.get("provider_account_id") or "")[:255] or None,
                "recipient_kind": str(vk_result.get("recipient_kind") or "peer_id")[:64],
                "recipient_value": str(vk_result.get("recipient_value") or "")[:255] or None,
                "error_text": None,
                "retryable": False,
            }
        return {
            "delivery_status": QUEUE_STATUS_FAILED,
            "provider_name": "vk_user_api",
            "provider_account_id": str(vk_result.get("provider_account_id") or "")[:255] or None,
            "recipient_kind": str(vk_result.get("recipient_kind") or "vk")[:64],
            "recipient_value": str(vk_result.get("recipient_value") or "")[:255] or None,
            "error_text": (
                f"{vk_result.get('error_code')}: {vk_result.get('error_text')}"
                if vk_result.get("error_code") and vk_result.get("error_text")
                else str(vk_result.get("error_text") or "VK delivery failed")
            )[:500],
            "retryable": bool(vk_result.get("retryable", False)),
        }

    # Runtime-first outbound via OpenClaw for supported machine channels.
    if channel == "whatsapp":
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
