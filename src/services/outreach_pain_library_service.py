"""Versioned owner-language library learned from monitored public sources.

The library is segment guidance, never evidence about a particular recipient.
New source material creates a draft. Only an explicitly approved version is
eligible for outreach generation.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from psycopg2.extras import Json

from services.outreach_playbook import BEAUTY_OWNER_PAINS, beauty_outreach_guidance


PAIN_LIBRARY_PATTERN_KEY = "beauty_owner_pain_library"
PAIN_LIBRARY_TITLE = "Язык болей владельцев салонов и специалистов красоты"
MIN_DOCUMENTS = 3
MIN_SOURCES = 2
MAX_SOURCE_PHRASES_PER_PAIN = 8
COMPILER_VERSION = "owner_language_v5"

PAIN_PATTERNS: dict[str, tuple[str, ...]] = {
    "marketing_and_clients": (
        r"клиент\w*\s+(?:нет|мало|не хватает)\b", r"\b(?:нет|мало)\s+клиент",
        r"реклам\w*.*(?:не работает|не помогает|впустую|коту под хвост)",
        r"(?:нет|мало)\s+(?:запис|обращени)", r"(?:запис|обращени)\w*\s+(?:нет|мало)\b",
        r"не знаю,?\s+что публиков",
    ),
    "staff_and_processes": (
        r"мастер\w*\s+(?:уход|увод|сабот|не хотят)", r"не могу.*(?:найти|удержать).*(?:мастер|сотрудник|администратор)",
        r"(?:нет|мало)\s+отклик", r"отклик\w*\s+(?:нет|мало)\b", r"сотрудник\w*.*(?:уход|не работают)",
    ),
    "reviews_and_service": (
        r"плох\w*\s+отзыв", r"как реагировать.*жалоб", r"не потерять репутац",
        r"клиент\w*.*недовол", r"разбираться.*владельц",
    ),
    "pricing_and_average_ticket": (
        r"боюсь.*(?:поднять|повысить).*цен", r"подня\w*\s+цен(?:у|ы|ам|ах)?\b", r"средний чек.*(?:мал|низк)",
        r"отменить скид", r"неудобно.*(?:цен|стоимост)",
    ),
    "operations_and_burnout": (
        r"если не я,?\s+то никто", r"работаю за .*?(?:администратор|управляющ|бухгалтер)",
        r"(?:устал|устала|выгорел|выгорела).*бизнес", r"жить некогда", r"не могу уехать",
        r"(?:тону|(?<!не )тонуть) в операцион", r"тащить всё сам", r"тащить всё сама",
    ),
    "retention": (
        r"клиент\w*.*не возвращ", r"возвратност\w*.*низк", r"ув[её]л\w*\s+клиент",
        r"уводят клиент", r"забрал\w*\s+(?:с собой\s+)?баз",
    ),
    "revenue_without_profit": (
        r"выручка есть,?\s+а прибыли нет", r"(?:бизнес|салон) работает,?\s+а денег нет",
        r"остаются копейки", r"оборот.*(?:а|но)\s+прибыл\w*\s+(?:нет|мало|низк)",
        r"владельц\w*\s+ничего не оста[её]тся",
    ),
}


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _sentences(value: Any) -> list[str]:
    raw = str(value or "").replace("\r", "\n")
    parts = re.split(r"(?:\n+|(?<=[.!?])\s+)", raw)
    return [_text(part).strip(" -–—•") for part in parts if 12 <= len(_text(part)) <= 180]


def classify_owner_language(documents: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Extract short source-backed phrases and keep their provenance."""

    result: dict[str, list[dict[str, Any]]] = {key: [] for key in PAIN_PATTERNS}
    seen: dict[str, set[str]] = {key: set() for key in PAIN_PATTERNS}
    for document in documents:
        for phrase in _sentences(document.get("content") or document.get("content_text")):
            normalized = phrase.lower()
            for pain_key, patterns in PAIN_PATTERNS.items():
                if not any(re.search(pattern, normalized) for pattern in patterns):
                    continue
                fingerprint = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
                if fingerprint in seen[pain_key] or len(result[pain_key]) >= MAX_SOURCE_PHRASES_PER_PAIN:
                    continue
                seen[pain_key].add(fingerprint)
                result[pain_key].append({
                    "text": phrase,
                    "document_id": str(document.get("id") or ""),
                    "source_id": str(document.get("source_id") or ""),
                    "source_title": _text(document.get("source_title") or document.get("channel")),
                    "permalink": document.get("permalink") or document.get("source_url"),
                    "published_at": str(document.get("published_at") or ""),
                    "status": "segment_hypothesis_only",
                })
    return result


def pain_library_source_hash(documents: list[dict[str, Any]]) -> str:
    identities = sorted(
        f"{document.get('id') or ''}:{document.get('published_at') or ''}"
        for document in documents
    )
    return hashlib.sha256("|".join(identities).encode("utf-8")).hexdigest()


def fetch_monitored_pain_documents(cursor: Any, *, limit: int = 500) -> list[dict[str, Any]]:
    """Read only public sources explicitly subscribed for learning."""

    cursor.execute(
        """
        SELECT DISTINCT document.id, document.content_text AS content,
               document.permalink, document.published_at,
               source.id AS source_id, source.title AS source_title
        FROM knowledge_documents document
        JOIN knowledge_sources source ON source.id = document.source_id
        JOIN knowledge_source_subscriptions subscription ON subscription.source_id = source.id
        WHERE document.invalidated_at IS NULL
          AND subscription.is_active = TRUE
          AND source.visibility = 'public'
          AND (
              subscription.purposes_json ? 'outreach_learning'
              OR subscription.purposes_json ? 'marketing_learning'
          )
          AND (
              document.metadata_json->>'audience_type' = 'business'
              OR document.metadata_json->>'corpus_tag' = 'telegram_b2b'
              OR source.metadata_json->>'audience_type' = 'business'
          )
        ORDER BY document.published_at DESC NULLS LAST
        LIMIT %s
        """,
        (max(1, min(int(limit), 2000)),),
    )
    return [dict(row) for row in cursor.fetchall()]


def compile_pain_library_draft(cursor: Any, documents: list[dict[str, Any]], *, user_id: str) -> dict[str, Any]:
    sources = {str(document.get("source_id") or "") for document in documents if document.get("source_id")}
    if len(documents) < MIN_DOCUMENTS or len(sources) < MIN_SOURCES:
        raise ValueError("pain_library_support_insufficient")
    source_hash = pain_library_source_hash(documents)
    cursor.execute(
        """
        SELECT id, version, status, compiler_result_json
        FROM outreach_knowledge_patterns
        WHERE pattern_key = %s
        ORDER BY version DESC
        LIMIT 1
        """,
        (PAIN_LIBRARY_PATTERN_KEY,),
    )
    latest_row = cursor.fetchone()
    latest = dict(latest_row) if latest_row else {}
    latest_result = latest.get("compiler_result_json") if isinstance(latest.get("compiler_result_json"), dict) else {}
    if latest_result.get("source_hash") == source_hash and latest_result.get("compiler_version") == COMPILER_VERSION:
        return {"id": str(latest.get("id")), "version": latest.get("version"), "status": latest.get("status"), "unchanged": True}

    extracted = classify_owner_language(documents)
    canonical = {item["key"]: item for item in BEAUTY_OWNER_PAINS}
    pains = []
    for pain_key, item in canonical.items():
        pains.append({
            "key": pain_key,
            "approved_seed_phrases": list(item["phrases"]),
            "candidate_source_phrases": extracted.get(pain_key) or [],
            "localos_bridge": item["localos_bridge"],
            "support": item["support"],
        })
    version = int(latest.get("version") or 0) + 1
    pattern_id = str(uuid.uuid4())
    source_refs = [
        {
            "document_id": str(document.get("id") or ""),
            "source_id": str(document.get("source_id") or ""),
            "permalink": document.get("permalink") or document.get("source_url"),
            "published_at": str(document.get("published_at") or ""),
        }
        for document in documents
    ]
    rules = {
        "library_version": f"pain-library-v{version}",
        "pain_language_status": "segment_hypothesis_only",
        "pains": pains,
        "usage_policy": {
            "recipient_fact_requires_separate_evidence": True,
            "one_pain_per_touch": True,
            "one_cta_per_touch": True,
            "source_phrase_requires_approval": True,
        },
    }
    cursor.execute(
        """
        INSERT INTO outreach_knowledge_patterns (
            id, pattern_key, version, title, pattern_type, status, segment,
            trigger_contract_json, message_rule_json, contraindications_json,
            source_refs_json, support_document_count, support_source_count,
            compiled_by, compiler_result_json, created_at, updated_at
        ) VALUES (%s, %s, %s, %s, 'pain', 'draft', 'beauty', %s, %s, %s, %s, %s, %s,
                  'monitored_public_sources_v1', %s, NOW(), NOW())
        """,
        (
            pattern_id,
            PAIN_LIBRARY_PATTERN_KEY,
            version,
            PAIN_LIBRARY_TITLE,
            Json({"source_purposes": ["outreach_learning", "marketing_learning"]}),
            Json(rules),
            Json(["Не утверждать боль как факт о получателе без evidence"]),
            Json(source_refs),
            len(documents),
            len(sources),
            Json({
                "source_hash": source_hash,
                "compiler_version": COMPILER_VERSION,
                "compiled_at": datetime.now(timezone.utc).isoformat(),
                "compiled_by_user": user_id,
            }),
        ),
    )
    return {"id": pattern_id, "version": version, "status": "draft", "unchanged": False}


def refresh_pain_library_draft(cursor: Any, *, user_id: str, limit: int = 500) -> dict[str, Any]:
    documents = fetch_monitored_pain_documents(cursor, limit=limit)
    return compile_pain_library_draft(cursor, documents, user_id=user_id)


def load_approved_pain_library(cursor: Any) -> dict[str, Any]:
    """Return the active approved version, falling back to curated v1."""

    cursor.execute(
        """
        SELECT id, version, message_rule_json, source_refs_json
        FROM outreach_knowledge_patterns
        WHERE pattern_key = %s AND pattern_type = 'pain' AND status = 'approved'
        ORDER BY version DESC
        LIMIT 1
        """,
        (PAIN_LIBRARY_PATTERN_KEY,),
    )
    row = cursor.fetchone()
    if not row:
        return beauty_outreach_guidance()
    pattern = dict(row)
    rules = pattern.get("message_rule_json") if isinstance(pattern.get("message_rule_json"), dict) else {}
    guidance = beauty_outreach_guidance()
    guidance["version"] = str(rules.get("library_version") or f"pain-library-v{pattern.get('version')}")
    guidance["pattern_id"] = str(pattern.get("id") or "")
    guidance["pattern_version"] = int(pattern.get("version") or 0)
    guidance["pain_library"] = list(rules.get("pains") or guidance["pain_library"])
    guidance["source_refs"] = list(pattern.get("source_refs_json") or [])
    guidance["pain_language_status"] = "segment_hypothesis_only"
    return guidance
