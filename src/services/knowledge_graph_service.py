import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from psycopg2.extras import Json, RealDictCursor

from core.knowledge_policy import detect_pii_flags, normalize_allowed_uses, normalize_sensitivity_class


def knowledge_layer_enabled() -> bool:
    return str(os.getenv("KNOWLEDGE_LAYER_ENABLED") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def content_hash(value: Any) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def canonical_key(value: Any) -> str:
    normalized = re.sub(r"[^a-zа-яё0-9]+", "-", str(value or "").strip().lower(), flags=re.IGNORECASE)
    return normalized.strip("-")[:180] or "unknown"


def _row_dict(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        return dict(row)
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    return {}


def upsert_source(
    conn,
    *,
    source_type: str,
    external_key: str,
    title: str,
    canonical_url: str | None = None,
    source_role: str = "unknown",
    visibility: str = "public",
    sensitivity_class: str = "public",
    pii_flags: list[str] | None = None,
    allowed_uses: list[str] | None = None,
    status: str = "candidate",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source_id = str(uuid.uuid4())
    safe_class = normalize_sensitivity_class(sensitivity_class)
    safe_uses = normalize_allowed_uses(allowed_uses or [])
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            INSERT INTO knowledge_sources (
                id, source_type, external_key, title, canonical_url, source_role,
                visibility, sensitivity_class, pii_flags, allowed_uses, status, metadata_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (source_type, external_key) DO UPDATE SET
                title = EXCLUDED.title,
                canonical_url = COALESCE(EXCLUDED.canonical_url, knowledge_sources.canonical_url),
                metadata_json = knowledge_sources.metadata_json || EXCLUDED.metadata_json,
                updated_at = NOW()
            RETURNING *
            """,
            (
                source_id,
                source_type,
                external_key,
                title,
                canonical_url,
                source_role,
                visibility,
                safe_class,
                Json(pii_flags or []),
                Json(safe_uses),
                status,
                Json(metadata or {}),
            ),
        )
        return _row_dict(cursor.fetchone())
    finally:
        cursor.close()


def decide_source(
    conn,
    *,
    source_id: str,
    status: str,
    source_role: str | None = None,
    allowed_uses: list[str] | None = None,
) -> dict[str, Any] | None:
    if status not in {"active", "paused"}:
        raise ValueError("Source decision must be active or paused")
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("SELECT source_role FROM knowledge_sources WHERE id = %s", (source_id,))
        current = cursor.fetchone()
        if not current:
            return None
        effective_role = str(source_role or current.get("source_role") or "unknown").strip()
        if status == "active" and effective_role == "unknown":
            raise ValueError("Перед включением укажите роль источника")
        cursor.execute(
            """
            UPDATE knowledge_sources
            SET status = %s,
                source_role = COALESCE(%s, source_role),
                allowed_uses = CASE WHEN %s IS NULL THEN allowed_uses ELSE %s END,
                updated_at = NOW()
            WHERE id = %s
            RETURNING *
            """,
            (
                status,
                effective_role,
                None if allowed_uses is None else "provided",
                Json(normalize_allowed_uses(allowed_uses or [])),
                source_id,
            ),
        )
        row = cursor.fetchone()
        return _row_dict(row) if row else None
    finally:
        cursor.close()


def upsert_document(
    conn,
    *,
    source_id: str,
    external_id: str,
    document_type: str,
    content_text: str,
    title: str | None = None,
    business_id: str | None = None,
    permalink: str | None = None,
    published_at: datetime | None = None,
    sensitivity_class: str = "public",
    pii_flags: list[str] | None = None,
    allowed_uses: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], bool]:
    document_id = str(uuid.uuid4())
    safe_class = normalize_sensitivity_class(sensitivity_class)
    detected_flags = detect_pii_flags(content_text)
    all_flags = sorted(set((pii_flags or []) + detected_flags))
    document_hash = content_hash(content_text)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            INSERT INTO knowledge_documents (
                id, source_id, business_id, external_id, document_type, title,
                content_text, permalink, published_at, content_hash,
                sensitivity_class, pii_flags, allowed_uses, metadata_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (source_id, external_id) DO UPDATE SET
                title = EXCLUDED.title,
                content_text = EXCLUDED.content_text,
                permalink = EXCLUDED.permalink,
                published_at = EXCLUDED.published_at,
                content_hash = EXCLUDED.content_hash,
                pii_flags = EXCLUDED.pii_flags,
                allowed_uses = EXCLUDED.allowed_uses,
                metadata_json = knowledge_documents.metadata_json || EXCLUDED.metadata_json,
                invalidated_at = NULL,
                updated_at = NOW()
            RETURNING *, (xmax = 0) AS inserted
            """,
            (
                document_id,
                source_id,
                business_id,
                external_id,
                document_type,
                title,
                content_text,
                permalink,
                published_at,
                document_hash,
                safe_class,
                Json(all_flags),
                Json(normalize_allowed_uses(allowed_uses or [])),
                Json(metadata or {}),
            ),
        )
        row = _row_dict(cursor.fetchone())
        inserted = bool(row.pop("inserted", False))
        return row, inserted
    finally:
        cursor.close()


def upsert_concept(
    conn,
    *,
    concept_type: str,
    label: str,
    industry: str | None = None,
    business_id: str | None = None,
    sensitivity_class: str = "public",
    allowed_uses: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    concept_id = str(uuid.uuid4())
    key = canonical_key(label)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            INSERT INTO knowledge_concepts (
                id, concept_type, canonical_key, label, industry, business_id,
                sensitivity_class, allowed_uses, metadata_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (
                concept_type, canonical_key, COALESCE(industry, ''), COALESCE(business_id, '')
            ) DO UPDATE SET
                label = EXCLUDED.label,
                allowed_uses = EXCLUDED.allowed_uses,
                metadata_json = knowledge_concepts.metadata_json || EXCLUDED.metadata_json,
                updated_at = NOW()
            RETURNING *
            """,
            (
                concept_id,
                concept_type,
                key,
                label,
                industry,
                business_id,
                normalize_sensitivity_class(sensitivity_class),
                Json(normalize_allowed_uses(allowed_uses or [])),
                Json(metadata or {}),
            ),
        )
        return _row_dict(cursor.fetchone())
    finally:
        cursor.close()


def upsert_assertion(
    conn,
    *,
    assertion_type: str,
    subject_type: str,
    subject_id: str,
    predicate: str,
    object_type: str,
    object_id: str,
    confidence: float,
    business_id: str | None = None,
    industry: str | None = None,
    allowed_uses: list[str] | None = None,
    sensitivity_class: str = "public",
    analysis_version: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    assertion_id = str(uuid.uuid4())
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            INSERT INTO knowledge_assertions (
                id, assertion_type, subject_type, subject_id, predicate,
                object_type, object_id, business_id, industry, confidence,
                allowed_uses, sensitivity_class, analysis_version, metadata_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (
                assertion_type, subject_type, subject_id, predicate, object_type, object_id,
                COALESCE(business_id, ''), COALESCE(analysis_version, '')
            ) WHERE invalidated_at IS NULL DO UPDATE SET
                confidence = GREATEST(knowledge_assertions.confidence, EXCLUDED.confidence),
                allowed_uses = EXCLUDED.allowed_uses,
                metadata_json = knowledge_assertions.metadata_json || EXCLUDED.metadata_json,
                updated_at = NOW()
            RETURNING *
            """,
            (
                assertion_id,
                assertion_type,
                subject_type,
                subject_id,
                predicate,
                object_type,
                object_id,
                business_id,
                industry,
                max(0, min(1, confidence)),
                Json(normalize_allowed_uses(allowed_uses or [])),
                normalize_sensitivity_class(sensitivity_class),
                analysis_version,
                Json(metadata or {}),
            ),
        )
        return _row_dict(cursor.fetchone())
    finally:
        cursor.close()


def add_evidence(
    conn,
    *,
    assertion_id: str,
    document_id: str,
    source_id: str,
    excerpt: str,
    observed_at: datetime | None,
    confidence: float,
    analysis_version: str,
    allowed_uses: list[str],
    sensitivity_class: str,
    pii_flags: list[str] | None = None,
) -> dict[str, Any]:
    evidence_id = str(uuid.uuid4())
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            INSERT INTO knowledge_evidence (
                id, assertion_id, document_id, source_id, excerpt, observed_at,
                confidence, analysis_version, allowed_uses, sensitivity_class, pii_flags
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (
                assertion_id, document_id, source_id, COALESCE(analysis_version, '')
            ) WHERE invalidated_at IS NULL DO UPDATE SET
                excerpt = EXCLUDED.excerpt,
                observed_at = EXCLUDED.observed_at,
                confidence = GREATEST(knowledge_evidence.confidence, EXCLUDED.confidence),
                allowed_uses = EXCLUDED.allowed_uses,
                sensitivity_class = EXCLUDED.sensitivity_class,
                pii_flags = EXCLUDED.pii_flags
            RETURNING *
            """,
            (
                evidence_id,
                assertion_id,
                document_id,
                source_id,
                excerpt[:1000],
                observed_at,
                max(0, min(1, confidence)),
                analysis_version,
                Json(normalize_allowed_uses(allowed_uses)),
                normalize_sensitivity_class(sensitivity_class),
                Json(pii_flags or []),
            ),
        )
        return _row_dict(cursor.fetchone())
    finally:
        cursor.close()


def overview(conn) -> dict[str, Any]:
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM knowledge_sources) AS sources_total,
                (SELECT COUNT(*) FROM knowledge_sources WHERE status = 'active') AS sources_active,
                (SELECT COUNT(*) FROM knowledge_sources WHERE status = 'candidate') AS sources_candidate,
                (SELECT COUNT(*) FROM knowledge_documents WHERE invalidated_at IS NULL) AS documents_total,
                (SELECT COUNT(*) FROM knowledge_assertions WHERE invalidated_at IS NULL) AS assertions_total,
                (SELECT COUNT(*) FROM learning_claims WHERE status = 'active' AND invalidated_at IS NULL) AS claims_active,
                (SELECT COUNT(*) FROM privacy_release_reviews WHERE status = 'pending') AS privacy_pending,
                (SELECT MAX(updated_at) FROM knowledge_sources) AS updated_at
            """
        )
        summary = _row_dict(cursor.fetchone())
        cursor.execute(
            """
            SELECT c.concept_type, c.label, COUNT(*)::INT AS evidence_count,
                   ROUND(AVG(a.confidence)::numeric, 3) AS confidence
            FROM knowledge_assertions a
            JOIN knowledge_concepts c ON c.id::text = a.object_id AND a.object_type = 'concept'
            WHERE a.invalidated_at IS NULL
            GROUP BY c.concept_type, c.label
            ORDER BY evidence_count DESC, confidence DESC
            LIMIT 12
            """
        )
        return {"summary": summary, "top_concepts": [_row_dict(row) for row in cursor.fetchall()]}
    finally:
        cursor.close()


def list_signals(
    conn,
    *,
    concept_type: str | None = None,
    industry: str | None = None,
    allowed_use: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    filters = ["a.invalidated_at IS NULL", "d.invalidated_at IS NULL", "s.status = 'active'"]
    params: list[Any] = []
    if concept_type:
        filters.append("c.concept_type = %s")
        params.append(concept_type)
    if industry:
        filters.append("COALESCE(a.industry, c.industry) = %s")
        params.append(industry)
    if allowed_use:
        filters.append("a.allowed_uses ? %s")
        params.append(allowed_use)
    params.append(max(1, min(limit, 200)))
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            f"""
            SELECT a.id AS assertion_id, a.assertion_type, a.predicate, a.confidence,
                   a.industry, a.allowed_uses, a.sensitivity_class,
                   c.id AS concept_id, c.concept_type, c.label,
                   e.id AS evidence_id, e.excerpt, e.observed_at,
                   d.id AS document_id, d.permalink, d.published_at,
                   s.id AS source_id, s.title AS source_title, s.source_role,
                   s.visibility, s.allowed_uses AS source_allowed_uses
            FROM knowledge_assertions a
            JOIN knowledge_concepts c ON c.id::text = a.object_id AND a.object_type = 'concept'
            JOIN LATERAL (
                SELECT item.* FROM knowledge_evidence item
                WHERE item.assertion_id = a.id AND item.invalidated_at IS NULL
                ORDER BY item.confidence DESC, item.created_at DESC LIMIT 1
            ) e ON TRUE
            JOIN knowledge_documents d ON d.id = e.document_id
            JOIN knowledge_sources s ON s.id = e.source_id
            WHERE {' AND '.join(filters)}
            ORDER BY COALESCE(e.observed_at, d.published_at, d.created_at) DESC, a.confidence DESC
            LIMIT %s
            """,
            params,
        )
        return [_row_dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()


def list_sources(conn, *, status: str | None = None) -> list[dict[str, Any]]:
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if status:
            cursor.execute(
                """
                SELECT s.*, COUNT(d.id)::INT AS documents_count
                FROM knowledge_sources s
                LEFT JOIN knowledge_documents d ON d.source_id = s.id AND d.invalidated_at IS NULL
                WHERE s.status = %s
                GROUP BY s.id ORDER BY s.updated_at DESC
                """,
                (status,),
            )
        else:
            cursor.execute(
                """
                SELECT s.*, COUNT(d.id)::INT AS documents_count
                FROM knowledge_sources s
                LEFT JOIN knowledge_documents d ON d.source_id = s.id AND d.invalidated_at IS NULL
                GROUP BY s.id ORDER BY s.status, s.updated_at DESC
                """
            )
        return [_row_dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()


def list_content_foundations(conn, *, industry: str = "beauty", limit_per_type: int = 3) -> dict[str, Any]:
    safe_limit = max(1, min(limit_per_type, 10))
    signals = list_signals(conn, industry=industry, allowed_use="client_content", limit=100)
    market_signals = [item for item in signals if item.get("concept_type") in {"market_signal", "pain", "topic"}][:safe_limit]
    salon_references = [item for item in signals if item.get("source_role") == "salon"][:safe_limit]
    service_patterns = list_signals(
        conn,
        concept_type="service",
        industry=industry,
        allowed_use="industry_recommendations",
        limit=safe_limit,
    )
    return {
        "industry": industry,
        "foundations": [
            {
                "type": "market_signal",
                "label": "Рыночный сигнал",
                "description": "Актуальная боль, изменение или вопрос аудитории с публичным источником.",
                "items": market_signals,
            },
            {
                "type": "salon_reference",
                "label": "Ориентир салона",
                "description": "Тема или приём из публичного контента салона. Текст не копируется.",
                "items": salon_references,
            },
            {
                "type": "service_pattern",
                "label": "Паттерн услуг",
                "description": "Формулировка или сочетание услуг, встречающееся в публичных карточках.",
                "items": service_patterns,
            },
        ],
        "generated_at": datetime.now(timezone.utc),
    }


def validate_content_foundation(
    conn,
    *,
    business_id: str,
    assertion_ids: list[str],
) -> dict[str, Any]:
    clean_ids = list(dict.fromkeys(str(item or "").strip() for item in assertion_ids if str(item or "").strip()))
    if not clean_ids:
        return {"knowledge_assertion_ids": [], "evidence_ids": [], "analysis_version": None}
    if len(clean_ids) > 10:
        raise ValueError("Для одного материала можно выбрать не больше 10 оснований")
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            SELECT a.id, a.analysis_version, a.business_id, a.sensitivity_class,
                   e.id AS evidence_id, s.status AS source_status
            FROM knowledge_assertions a
            JOIN knowledge_evidence e ON e.assertion_id = a.id AND e.invalidated_at IS NULL
            JOIN knowledge_sources s ON s.id = e.source_id
            WHERE a.id::text = ANY(%s)
              AND a.invalidated_at IS NULL
              AND a.allowed_uses ? 'client_content'
              AND s.status = 'active'
              AND (
                  a.sensitivity_class IN ('public', 'shared_deidentified')
                  OR (a.sensitivity_class = 'tenant_confidential' AND a.business_id = %s)
              )
            ORDER BY a.id, e.confidence DESC
            """,
            (clean_ids, business_id),
        )
        rows = [_row_dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
    found_ids = {str(row["id"]) for row in rows}
    if found_ids != set(clean_ids):
        raise ValueError("Одно из оснований недоступно этому бизнесу или не разрешено для контента")
    versions = sorted(set(str(row.get("analysis_version") or "") for row in rows if row.get("analysis_version")))
    return {
        "knowledge_assertion_ids": clean_ids,
        "evidence_ids": list(dict.fromkeys(str(row["evidence_id"]) for row in rows)),
        "analysis_version": ",".join(versions) or None,
        "hypothesis_id": clean_ids[0],
    }


def list_runs(conn, *, limit: int = 50) -> list[dict[str, Any]]:
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            SELECT r.*, s.title AS source_title
            FROM knowledge_analysis_runs r
            LEFT JOIN knowledge_sources s ON s.id = r.source_id
            ORDER BY r.created_at DESC LIMIT %s
            """,
            (max(1, min(limit, 200)),),
        )
        return [_row_dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()


def list_privacy_candidates(conn) -> list[dict[str, Any]]:
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            SELECT r.id AS review_id, r.status AS review_status, r.redacted_payload_json,
                   r.created_at AS requested_at, c.*
            FROM privacy_release_reviews r
            JOIN learning_claims c ON c.id = r.claim_id
            WHERE r.status = 'pending' AND c.invalidated_at IS NULL
            ORDER BY r.created_at ASC
            """
        )
        return [_row_dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()


def decide_privacy_candidate(
    conn,
    *,
    review_id: str,
    decision: str,
    reviewer_id: str,
    reason: str | None = None,
) -> dict[str, Any] | None:
    if decision not in {"approved", "rejected"}:
        raise ValueError("Privacy decision must be approved or rejected")
    if decision == "approved" and not str(os.getenv("KNOWLEDGE_SHARED_CLAIMS_ENABLED") or "").lower() in {
        "1", "true", "yes", "on"
    }:
        raise ValueError("Shared claims are disabled")
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            UPDATE privacy_release_reviews
            SET status = %s, reviewer_id = %s, decision_reason = %s,
                reviewed_at = NOW(), updated_at = NOW()
            WHERE id = %s AND status = 'pending'
            RETURNING claim_id
            """,
            (decision, reviewer_id, reason, review_id),
        )
        row = cursor.fetchone()
        if not row:
            return None
        claim_id = str(row["claim_id"])
        cursor.execute(
            """
            UPDATE learning_claims
            SET privacy_status = %s,
                status = CASE WHEN %s = 'approved' THEN 'active' ELSE status END,
                sensitivity_class = CASE WHEN %s = 'approved' THEN 'shared_deidentified' ELSE sensitivity_class END,
                updated_at = NOW()
            WHERE id = %s
            RETURNING *
            """,
            (decision, decision, decision, claim_id),
        )
        return _row_dict(cursor.fetchone())
    finally:
        cursor.close()


def invalidate_source(conn, *, source_id: str) -> dict[str, int]:
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE knowledge_documents SET invalidated_at = NOW(), updated_at = NOW() WHERE source_id = %s AND invalidated_at IS NULL",
            (source_id,),
        )
        documents = cursor.rowcount
        cursor.execute(
            """
            UPDATE knowledge_evidence e SET invalidated_at = NOW()
            FROM knowledge_documents d
            WHERE e.document_id = d.id AND d.source_id = %s AND e.invalidated_at IS NULL
            """,
            (source_id,),
        )
        evidence = cursor.rowcount
        cursor.execute(
            """
            UPDATE knowledge_assertions a SET invalidated_at = NOW(), updated_at = NOW()
            WHERE a.invalidated_at IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM knowledge_evidence e
                  WHERE e.assertion_id = a.id AND e.invalidated_at IS NULL
              )
            """
        )
        assertions = cursor.rowcount
        cursor.execute(
            """
            UPDATE learning_claims c SET status = 'invalidated', invalidated_at = NOW(), updated_at = NOW()
            WHERE c.invalidated_at IS NULL
              AND EXISTS (
                  SELECT 1 FROM knowledge_evidence e
                  WHERE e.claim_id = c.id AND e.invalidated_at IS NOT NULL
              )
            """
        )
        claims = cursor.rowcount
        return {"documents": documents, "evidence": evidence, "assertions": assertions, "claims": claims}
    finally:
        cursor.close()


def record_action_event(
    conn,
    *,
    business_id: str,
    action_type: str,
    source_type: str,
    source_id: str,
    status: str = "confirmed",
    hypothesis_id: str | None = None,
    approval_id: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    limitations: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    occurred_at: datetime | None = None,
) -> dict[str, Any]:
    event_id = str(uuid.uuid4())
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            INSERT INTO business_action_events (
                id, business_id, action_type, source_type, source_id, status,
                hypothesis_id, approval_id, before_json, after_json,
                limitations_json, evaluation_window_json, metadata_json, occurred_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (business_id, action_type, source_type, source_id) DO UPDATE SET
                status = EXCLUDED.status,
                approval_id = COALESCE(EXCLUDED.approval_id, business_action_events.approval_id),
                after_json = EXCLUDED.after_json,
                limitations_json = EXCLUDED.limitations_json,
                metadata_json = business_action_events.metadata_json || EXCLUDED.metadata_json
            RETURNING *
            """,
            (
                event_id,
                business_id,
                action_type,
                source_type,
                source_id,
                status,
                hypothesis_id,
                approval_id,
                Json(before or {}),
                Json(after or {}),
                Json(limitations or []),
                Json({"before_days": 28, "after_days": 28, "minimum_days_each_side": 14}),
                Json(metadata or {}),
                occurred_at or datetime.now(timezone.utc),
            ),
        )
        return _row_dict(cursor.fetchone())
    finally:
        cursor.close()


_EXTERNAL_CARD_FIELDS = ("title", "address", "phone", "site", "hours", "hours_full")


def diff_external_card_snapshot(
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    """Return only explicit profile changes, never infer deletion from sparse parser data."""
    if not before or not after:
        return {"before": {}, "after": {}}

    before_changes: dict[str, Any] = {}
    after_changes: dict[str, Any] = {}
    for field in _EXTERNAL_CARD_FIELDS:
        new_value = after.get(field)
        if new_value in (None, "", [], {}):
            continue
        old_value = before.get(field)
        old_normalized = json.dumps(old_value, ensure_ascii=False, sort_keys=True, default=str)
        new_normalized = json.dumps(new_value, ensure_ascii=False, sort_keys=True, default=str)
        if old_normalized == new_normalized:
            continue
        before_changes[field] = old_value
        after_changes[field] = new_value
    return {"before": before_changes, "after": after_changes}


def record_external_card_change(
    conn,
    *,
    business_id: str,
    card_id: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> dict[str, Any] | None:
    changes = diff_external_card_snapshot(before, after)
    changed_fields = list(changes["after"].keys())
    if not changed_fields:
        return None
    return record_action_event(
        conn,
        business_id=business_id,
        action_type="external_change_detected",
        source_type="card_snapshot",
        source_id=card_id,
        status="external_change_detected",
        before=changes["before"],
        after=changes["after"],
        limitations=[
            "Изменение обнаружено сравнением публичных снимков карты.",
            "LocalOS не приписывает это изменение своим действиям.",
            "Удаление поля не определяется, если парсер вернул неполный снимок.",
        ],
        metadata={"changed_fields": changed_fields},
    )


def attach_lead_knowledge_signals(conn, leads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lead_ids = [str(lead.get("id") or "").strip() for lead in leads]
    lead_ids = [lead_id for lead_id in lead_ids if lead_id]
    if not lead_ids:
        return leads
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            SELECT * FROM (
                SELECT a.subject_id AS lead_id, a.id AS assertion_id, a.confidence,
                       c.concept_type, c.label, e.id AS evidence_id, e.excerpt,
                       e.observed_at, d.permalink, s.title AS source_title,
                       ROW_NUMBER() OVER (
                           PARTITION BY a.subject_id
                           ORDER BY a.confidence DESC, COALESCE(e.observed_at, d.published_at) DESC
                       ) AS rank
                FROM knowledge_assertions a
                JOIN knowledge_concepts c ON c.id::text = a.object_id AND a.object_type = 'concept'
                JOIN knowledge_evidence e ON e.assertion_id = a.id AND e.invalidated_at IS NULL
                JOIN knowledge_documents d ON d.id = e.document_id AND d.invalidated_at IS NULL
                JOIN knowledge_sources s ON s.id = e.source_id
                WHERE a.subject_type = 'prospectinglead'
                  AND a.subject_id = ANY(%s)
                  AND a.invalidated_at IS NULL
                  AND a.allowed_uses ? 'outreach'
            ) ranked
            WHERE rank <= 3
            ORDER BY lead_id, rank
            """,
            (lead_ids,),
        )
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in cursor.fetchall():
            item = _row_dict(row)
            item.pop("rank", None)
            grouped.setdefault(str(item.pop("lead_id")), []).append(item)
    finally:
        cursor.close()

    result: list[dict[str, Any]] = []
    for raw_lead in leads:
        lead = dict(raw_lead)
        signals = grouped.get(str(lead.get("id") or ""), [])
        lead["knowledge_signals"] = signals
        lead["evidence_ids"] = [str(item["evidence_id"]) for item in signals]
        lead["personalization_source"] = signals[0] if signals else None
        workstreams = []
        for raw_workstream in lead.get("workstreams") or []:
            workstream = dict(raw_workstream)
            workstream["knowledge_signals"] = signals
            workstream["evidence_ids"] = lead["evidence_ids"]
            workstream["personalization_source"] = lead["personalization_source"]
            workstreams.append(workstream)
        lead["workstreams"] = workstreams
        result.append(lead)
    return result


def serialize_for_json(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: serialize_for_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serialize_for_json(item) for item in value]
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)
