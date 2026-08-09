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

from services.knowledge_embeddings import GigaChatEmbeddingClient, _enabled, _vector_literal

from services.outreach_playbook import (
    BEAUTY_OWNER_PAINS,
    BEAUTY_PAIN_SIGNAL_HYPOTHESES,
    PAIN_SIGNAL_LIBRARY_VERSION,
    beauty_outreach_guidance,
)


PAIN_LIBRARY_PATTERN_KEY = "beauty_owner_pain_library"
PAIN_LIBRARY_TITLE = "Язык болей владельцев салонов и специалистов красоты"
MIN_DOCUMENTS = 3
MIN_SOURCES = 2
MAX_SOURCE_PHRASES_PER_PAIN = 8
COMPILER_VERSION = "owner_language_v7_review_editorial_examples"
LANGUAGE_SUPPORT_MIN_DOCUMENTS = 3
LANGUAGE_SUPPORT_MIN_SOURCES = 3
LANGUAGE_SUPPORT_MIN_PROFESSIONAL_SOURCES = 2
LANGUAGE_SUPPORT_MAX_VENDOR_SOURCES = 1

LANGUAGE_THEME_BY_SIGNAL = {
    "recent_price_update_announcement": "price_surface_sync",
    "active_social_with_service_price_gap": "price_surface_sync",
    "active_social_with_unanswered_negative_review": "review_workflow",
    "unanswered_reviews_with_active_presence": "review_workflow",
    "recent_new_service_announcement": "content_reuse",
    "recent_event_announcement": "event_distribution",
    "repeated_open_slots": "manual_time",
}
LANGUAGE_LEXICAL_QUERY_BY_THEME = {
    "price_surface_sync": "прайс OR цены OR карты OR площадки",
    "review_workflow": "отзыв OR ответ OR репутация OR карты",
    "content_reuse": "контент OR пост OR текст OR публикация",
    "event_distribution": "клиентский день OR мероприятие OR регистрация OR анонс",
    "manual_time": "вручную OR время OR проверка OR операционка",
}

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
               policy.eligibility->>'speaker_role' AS speaker_role,
               policy.eligibility->>'audience' AS audience,
               policy.eligibility->>'content_role' AS content_role,
               source.id AS source_id, source.title AS source_title
        FROM knowledge_documents document
        JOIN knowledge_sources source ON source.id = document.source_id
        JOIN knowledge_source_subscriptions subscription ON subscription.source_id = source.id
        CROSS JOIN LATERAL (
            SELECT COALESCE(
                document.metadata_json->'pain_voice_eligibility',
                source.metadata_json->'pain_voice_eligibility',
                '{}'::jsonb
            ) AS eligibility
        ) policy
        WHERE document.invalidated_at IS NULL
          AND subscription.is_active = TRUE
          AND source.status = 'active'
          AND source.source_type = 'telegram'
          AND source.visibility = 'public'
          AND source.sensitivity_class = 'public'
          AND document.sensitivity_class = 'public'
          AND source.allowed_uses ? 'outreach'
          AND document.allowed_uses ? 'outreach'
          AND document.permalink LIKE 'https://t.me/%%'
          AND (
              subscription.purposes_json ? 'outreach_learning'
              OR subscription.purposes_json ? 'marketing_learning'
          )
          AND policy.eligibility->>'industry' = 'beauty_salon'
          AND policy.eligibility->>'audience' IN (
              'business_owner', 'beauty_professional'
          )
          AND policy.eligibility->>'speaker_role' IN (
              'owner', 'manager', 'master', 'expert', 'vendor'
          )
          AND policy.eligibility->>'content_role' IN (
              'first_person_experience', 'professional_discussion', 'advice'
          )
          AND policy.eligibility->>'pain_support_eligible' = 'true'
          AND policy.eligibility->>'voice_style_eligible' = 'true'
          AND policy.eligibility->>'eligibility_confidence' IN ('high', 'medium')
          AND COALESCE(document.published_at, document.created_at) >= NOW() - INTERVAL '1095 days'
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
        "pain_signal_library_version": PAIN_SIGNAL_LIBRARY_VERSION,
        "pain_signal_hypotheses": [
            {
                "key": item["key"],
                "pain_key": item["pain_key"],
                "required_signals": list(item["required_signals"]),
                "hypothesis": item["hypothesis"],
                "hypothesis_status": item.get(
                    "hypothesis_status", "segment_hypothesis_only"
                ),
                "safe_formulation": item["safe_formulation"],
                "localos_action": item.get("localos_action"),
                "contraindications": list(item["contraindications"]),
                "status": item["status"],
            }
            for item in BEAUTY_PAIN_SIGNAL_HYPOTHESES
        ],
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
    """Return approved owner language with canonical executable signal rules.

    Approved monitored language may evolve independently, but an older database
    snapshot must not remove newer safety contracts shipped in code.
    """

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
    canonical_signal_rules = list(guidance["pain_signal_hypotheses"])
    canonical_keys = {
        str(item.get("key") or "")
        for item in canonical_signal_rules
        if isinstance(item, dict)
    }
    approved_signal_rules = [
        item
        for item in rules.get("pain_signal_hypotheses") or []
        if isinstance(item, dict)
        and str(item.get("key") or "") not in canonical_keys
    ]
    guidance["pain_signal_hypotheses"] = canonical_signal_rules + approved_signal_rules
    guidance["source_refs"] = list(pattern.get("source_refs_json") or [])
    guidance["pain_language_status"] = "segment_hypothesis_only"
    return guidance


def _approved_pain_document_ids(playbook: dict[str, Any], pain_key: str) -> list[str]:
    identifiers = []
    for pain in playbook.get("pain_library") or []:
        if not isinstance(pain, dict) or _text(pain.get("key")) != _text(pain_key):
            continue
        for phrase in pain.get("candidate_source_phrases") or []:
            if not isinstance(phrase, dict):
                continue
            identifier = _text(phrase.get("document_id"))
            if identifier and identifier not in identifiers:
                identifiers.append(identifier)
    return identifiers


def _query_vector(query: str) -> list[Any] | None:
    if not _enabled() or not _text(query):
        return None
    try:
        response = GigaChatEmbeddingClient().embed([query])
        vectors = response.get("vectors") or []
        return vectors[0] if vectors else None
    except Exception:
        return None


def retrieve_language_support(
    cursor: Any,
    *,
    query: str,
    segment: str,
    theme: str,
    approved_document_ids: list[str] | None = None,
    query_vector: list[Any] | None = None,
    limit: int = 6,
) -> dict[str, Any]:
    """Retrieve public professional language; never return raw quotes to preview."""

    curated_ids = [str(item) for item in approved_document_ids or [] if str(item)]
    lexical_query = LANGUAGE_LEXICAL_QUERY_BY_THEME.get(theme, query)
    vector = query_vector if query_vector is not None else _query_vector(query)
    vector_select = (
        ", 1 - (chunk.embedding <=> %s::halfvec) AS vector_similarity"
        if vector
        else ", 0.0::numeric AS vector_similarity"
    )
    vector_order = "chunk.embedding <=> %s::halfvec," if vector else ""
    vector_value = _vector_literal(vector) if vector else None
    params: list[Any] = [lexical_query]
    if vector:
        params.append(vector_value)
    params.extend([
        curated_ids,
        segment, segment, segment, segment,
        theme, theme, theme, theme,
        lexical_query,
        bool(vector),
    ])
    if vector:
        params.append(vector_value)
    fetch_limit = max(24, min(max(1, int(limit)) * 12, 72))
    params.append(fetch_limit)
    cursor.execute(
        f"""
        SELECT document.id AS document_id, chunk.id AS chunk_id,
               source.id AS source_id, source.title AS source_title,
               document.permalink, document.published_at,
               policy.eligibility->>'speaker_role' AS speaker_role,
               policy.eligibility->>'audience' AS audience,
               policy.eligibility->>'content_role' AS content_role,
               ts_rank_cd(
                   to_tsvector('russian', chunk.content_text),
                   websearch_to_tsquery('russian', %s)
               ) AS lexical_rank
               {vector_select}
        FROM knowledge_embedding_chunks chunk
        JOIN knowledge_document_chunk_links link ON link.chunk_id = chunk.id
        JOIN knowledge_documents document ON document.id = link.document_id
        JOIN knowledge_sources source ON source.id = document.source_id
        JOIN knowledge_source_subscriptions subscription ON subscription.source_id = source.id
        CROSS JOIN LATERAL (
            SELECT COALESCE(
                document.metadata_json->'pain_voice_eligibility',
                source.metadata_json->'pain_voice_eligibility',
                '{{}}'::jsonb
            ) AS eligibility
        ) policy
        WHERE chunk.status = 'ready'
          AND chunk.stale_at IS NULL
          AND document.invalidated_at IS NULL
          AND source.status = 'active'
          AND source.source_type = 'telegram'
          AND source.visibility = 'public'
          AND source.sensitivity_class = 'public'
          AND document.sensitivity_class = 'public'
          AND source.allowed_uses ? 'outreach'
          AND document.allowed_uses ? 'outreach'
          AND document.permalink LIKE 'https://t.me/%%'
          AND subscription.is_active = TRUE
          AND (
              subscription.purposes_json ? 'outreach_learning'
              OR subscription.purposes_json ? 'marketing_learning'
          )
          AND policy.eligibility->>'industry' = 'beauty_salon'
          AND policy.eligibility->>'audience' IN ('business_owner', 'beauty_professional')
          AND policy.eligibility->>'speaker_role' IN (
              'owner', 'manager', 'master', 'expert', 'vendor'
          )
          AND policy.eligibility->>'content_role' IN (
              'first_person_experience', 'professional_discussion', 'advice'
          )
          AND policy.eligibility->>'pain_support_eligible' = 'true'
          AND policy.eligibility->>'voice_style_eligible' = 'true'
          AND policy.eligibility->>'eligibility_confidence' IN ('high', 'medium')
          AND COALESCE(document.published_at, document.created_at) >= NOW() - INTERVAL '1095 days'
          AND (
              document.id = ANY(%s::uuid[])
              OR (
                  (
                      document.metadata_json->'segments' ? %s
                      OR document.metadata_json->>'segment' = %s
                      OR source.metadata_json->'segments' ? %s
                      OR source.metadata_json->>'segment' = %s
                  )
                  AND (
                      document.metadata_json->'themes' ? %s
                      OR document.metadata_json->>'theme' = %s
                      OR source.metadata_json->'themes' ? %s
                      OR source.metadata_json->>'theme' = %s
                  )
              )
          )
          AND (
              to_tsvector('russian', chunk.content_text) @@ websearch_to_tsquery('russian', %s)
              OR %s::boolean
          )
        ORDER BY {vector_order} lexical_rank DESC,
                 document.published_at DESC NULLS LAST
        LIMIT %s
        """,
        tuple(params),
    )
    rows = [dict(row) for row in cursor.fetchall()]
    rows.sort(
        key=lambda row: (
            float(row.get("vector_similarity") or 0),
            float(row.get("lexical_rank") or 0),
        ),
        reverse=True,
    )
    selected = []
    selected_document_ids: set[str] = set()
    selected_source_ids: set[str] = set()
    vendor_source_ids: set[str] = set()
    for row in rows:
        document_id = _text(row.get("document_id"))
        source_id = _text(row.get("source_id"))
        speaker_role = _text(row.get("speaker_role"))
        if not document_id or not source_id or document_id in selected_document_ids:
            continue
        if source_id in selected_source_ids:
            continue
        if speaker_role == "vendor" and len(vendor_source_ids) >= LANGUAGE_SUPPORT_MAX_VENDOR_SOURCES:
            continue
        selected.append(row)
        selected_document_ids.add(document_id)
        selected_source_ids.add(source_id)
        if speaker_role == "vendor":
            vendor_source_ids.add(source_id)
        if len(selected) >= min(max(3, int(limit)), 6):
            break
    document_ids = list(dict.fromkeys(_text(row.get("document_id")) for row in selected if row.get("document_id")))
    source_ids = list(dict.fromkeys(_text(row.get("source_id")) for row in selected if row.get("source_id")))
    professional_source_ids = list(dict.fromkeys(
        _text(row.get("source_id"))
        for row in selected
        if row.get("source_id") and _text(row.get("speaker_role")) != "vendor"
    ))
    recent_document_count = sum(
        1
        for row in selected
        if row.get("published_at")
        and (datetime.now(timezone.utc) - row["published_at"]).days <= 730
    )
    supported = (
        len(document_ids) >= LANGUAGE_SUPPORT_MIN_DOCUMENTS
        and len(source_ids) >= LANGUAGE_SUPPORT_MIN_SOURCES
        and len(professional_source_ids) >= LANGUAGE_SUPPORT_MIN_PROFESSIONAL_SOURCES
        and len(vendor_source_ids) <= LANGUAGE_SUPPORT_MAX_VENDOR_SOURCES
        and recent_document_count >= 2
    )
    support_level = "supported" if supported else "weak" if len(source_ids) >= 2 else "unsupported"
    return {
        "status": support_level,
        "support_level": support_level,
        "segment": segment,
        "theme": theme,
        "retrieval_mode": "hybrid" if vector else "lexical",
        "document_count": len(document_ids),
        "source_count": len(source_ids),
        "professional_source_count": len(professional_source_ids),
        "vendor_source_count": len(vendor_source_ids),
        "recent_document_count": recent_document_count,
        "pain_reference_ids": document_ids,
        "language_reference_ids": [
            _text(row.get("chunk_id")) for row in selected if row.get("chunk_id")
        ],
        "sources": [
            {
                "document_id": _text(row.get("document_id")),
                "source_id": _text(row.get("source_id")),
                "source_title": _text(row.get("source_title")),
                "permalink": row.get("permalink"),
                "published_at": str(row.get("published_at") or ""),
            }
            for row in selected
        ],
        "paraphrase_only": True,
        "raw_quotes_exposed": False,
        "similarity_is_sole_approval_criterion": False,
    }


def language_support_for_candidate(
    cursor: Any,
    candidate: dict[str, Any],
    playbook: dict[str, Any],
) -> dict[str, Any]:
    pain_key = _text(candidate.get("signal_pain_key") or candidate.get("pain_key"))
    recipient_segment = _text(candidate.get("recipient_segment"))
    segment = (
        "beauty"
        if recipient_segment in {
            "private_beauty_specialist", "beauty_team", "beauty_network"
        }
        else recipient_segment
    )
    if not segment or not pain_key:
        return {
            "status": "not_checked",
            "segment": segment,
            "theme": pain_key,
            "pain_reference_ids": [],
            "language_reference_ids": [],
            "sources": [],
            "paraphrase_only": True,
            "raw_quotes_exposed": False,
            "similarity_is_sole_approval_criterion": False,
        }
    theme = LANGUAGE_THEME_BY_SIGNAL.get(
        _text(candidate.get("signal_combo")),
        pain_key,
    )
    query = " ".join(
        item
        for item in (
            pain_key,
            _text(candidate.get("problem_hypothesis")),
            _text(candidate.get("localos_action")),
        )
        if item
    )
    try:
        pain_support = retrieve_language_support(
            cursor,
            query=query,
            segment=segment,
            theme=theme,
            approved_document_ids=_approved_pain_document_ids(playbook, pain_key),
        )
        if _text(candidate.get("signal_combo")) != "recent_price_update_announcement":
            return pain_support
        if _text(pain_support.get("status")) == "supported":
            return pain_support
        voice_support = retrieve_language_support(
            cursor,
            query="ручная проверка и перенос обновлений между площадками",
            segment=segment,
            theme="manual_time",
            approved_document_ids=[],
        )
        return {
            "status": "conditional_operator_approved",
            "support_level": "unsupported",
            "segment": segment,
            "theme": "price_surface_sync",
            "pain_support_status": pain_support.get("status") or "unsupported",
            "language_support_status": voice_support.get("status") or "unsupported",
            "document_count": voice_support.get("document_count") or 0,
            "source_count": voice_support.get("source_count") or 0,
            "professional_source_count": voice_support.get("professional_source_count") or 0,
            "pain_reference_ids": [],
            "language_reference_ids": list(
                voice_support.get("language_reference_ids") or []
            ),
            "sources": list(voice_support.get("sources") or []),
            "pain_support": {
                "status": pain_support.get("status") or "unsupported",
                "theme": "price_surface_sync",
                "document_count": pain_support.get("document_count") or 0,
                "source_count": pain_support.get("source_count") or 0,
                "pain_reference_ids": [],
                "frequency_claim_allowed": False,
            },
            "voice_support": {
                "status": voice_support.get("status") or "unsupported",
                "theme": "manual_time",
                "document_count": voice_support.get("document_count") or 0,
                "source_count": voice_support.get("source_count") or 0,
                "language_reference_ids": list(
                    voice_support.get("language_reference_ids") or []
                ),
            },
            "operator_approval_id": "salon_price_300plus_clicks_v1",
            "wording_policy": "conditional_only",
            "frequency_claim_allowed": False,
            "paraphrase_only": True,
            "raw_quotes_exposed": False,
            "similarity_is_sole_approval_criterion": False,
        }
    except Exception:
        return {
            "status": "unavailable",
            "segment": segment,
            "theme": pain_key,
            "pain_reference_ids": [],
            "language_reference_ids": [],
            "sources": [],
            "paraphrase_only": True,
            "raw_quotes_exposed": False,
            "similarity_is_sole_approval_criterion": False,
        }
