from __future__ import annotations

import hashlib
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from psycopg2.extras import Json, RealDictCursor

from core.knowledge_policy import redact_text
from services.knowledge_embeddings import GigaChatEmbeddingClient, _business_allowed, _enabled, _vector_literal


@dataclass(frozen=True)
class KnowledgeSearchRequest:
    business_id: str
    query: str
    purpose: str
    source_types: tuple[str, ...] = ()
    published_after: datetime | None = None
    limit: int = 12
    pipeline_id: str = ""
    consumer: str = "knowledge"


@dataclass
class KnowledgeHit:
    document_id: str
    chunk_id: str
    source_id: str
    excerpt: str
    permalink: str = ""
    published_at: Any = None
    similarity: float = 0.0
    source_type: str = ""
    sensitivity_class: str = ""
    evidence_ids: list[str] = field(default_factory=list)
    assertion_ids: list[str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)


def _table_exists(cursor: Any, table_name: str) -> bool:
    cursor.execute("SELECT to_regclass(%s) AS table_name", (f"public.{table_name}",))
    row = cursor.fetchone()
    value = row.get("table_name") if isinstance(row, dict) else (row[0] if row else None)
    return bool(value)


def _query_instruction(request: KnowledgeSearchRequest) -> str:
    purpose_labels = {
        "client_content": "Найди факты и сигналы для создания полезного материала клиентам бизнеса.",
        "industry_recommendations": "Найди факты, паттерны и сигналы для практической рекомендации бизнесу.",
        "localos_content": "Найди подтверждённые знания для внутреннего ответа LocalOS.",
        "market": "Найди актуальные рыночные сигналы и подтверждающие источники.",
        "outreach": "Найди разрешённые публичные факты для персонализации обращения.",
    }
    instruction = purpose_labels.get(request.purpose, "Найди наиболее релевантные подтверждённые факты.")
    return f"{instruction}\nЗапрос: {request.query.strip()}"


def _filters(request: KnowledgeSearchRequest, *, include_chunk: bool = True) -> tuple[str, list[Any]]:
    filters = [
        "document.invalidated_at IS NULL",
        "source.status = 'active'",
        "document.allowed_uses @> jsonb_build_array(%s::text)",
        "(document.business_id = %s OR (document.sensitivity_class = 'public' "
        "AND source.visibility NOT IN ('private', 'invite')) OR "
        "(document.business_id IS NULL AND document.sensitivity_class = 'shared_deidentified'))",
    ]
    if include_chunk:
        filters[0:0] = ["chunk.status = 'ready'", "chunk.stale_at IS NULL"]
    params: list[Any] = [request.purpose, request.business_id]
    if request.source_types:
        filters.append("document.document_type = ANY(%s)")
        params.append(list(request.source_types))
    if request.published_after:
        filters.append("COALESCE(document.published_at, document.created_at) >= %s")
        params.append(request.published_after)
    return " AND ".join(filters), params


def _base_select(extra_columns: str = "") -> str:
    extra = f", {extra_columns}" if extra_columns else ""
    return f"""
        SELECT DISTINCT ON (chunk.id)
               chunk.id AS chunk_id, chunk.content_text,
               document.id AS document_id, document.permalink, document.published_at,
               document.sensitivity_class, document.document_type,
               source.id AS source_id, source.source_type, source.title AS source_title,
               COALESCE(
                   (source.metadata_json->>'retrieval_quality_weight')::numeric,
                   (source.metadata_json->>'confidence')::numeric,
                   0.7
               ) AS source_confidence,
               (document.business_id IS NOT NULL) AS tenant_specific,
               GREATEST(0.0, 1.0 - EXTRACT(EPOCH FROM (
                   NOW() - COALESCE(document.published_at, document.updated_at)
               )) / 31557600.0) AS freshness_score,
               COALESCE((
                   SELECT COUNT(DISTINCT evidence.source_id)
                   FROM knowledge_evidence evidence
                   WHERE evidence.document_id = document.id AND evidence.invalidated_at IS NULL
               ), 0) AS confirmation_count,
               COALESCE((
                   SELECT COUNT(*)
                   FROM knowledge_retrieval_events event
                   WHERE event.result_chunk_ids @> jsonb_build_array(chunk.id::text)
                     AND event.outcome IN ('accepted', 'published', 'applied')
               ), 0) AS successful_uses,
               COALESCE((
                   SELECT jsonb_agg(DISTINCT evidence.id::text)
                   FROM knowledge_evidence evidence
                   WHERE evidence.document_id = document.id AND evidence.invalidated_at IS NULL
               ), '[]'::jsonb) AS evidence_ids,
               COALESCE((
                   SELECT jsonb_agg(DISTINCT evidence.assertion_id::text)
                   FROM knowledge_evidence evidence
                   WHERE evidence.document_id = document.id AND evidence.invalidated_at IS NULL
                     AND evidence.assertion_id IS NOT NULL
               ), '[]'::jsonb) AS assertion_ids
               {extra}
        FROM knowledge_embedding_chunks chunk
        JOIN knowledge_document_chunk_links link ON link.chunk_id = chunk.id
        JOIN knowledge_documents document ON document.id = link.document_id
        JOIN knowledge_sources source ON source.id = document.source_id
    """


def _vector_rows(cursor: Any, request: KnowledgeSearchRequest, vector: list[Any]) -> list[dict[str, Any]]:
    where_sql, params = _filters(request, include_chunk=False)
    vector_value = _vector_literal(vector)
    cursor.execute(
        f"""
        WITH nearest AS MATERIALIZED (
            SELECT chunk.id AS chunk_id, chunk.content_text,
                   chunk.embedding <=> %s::halfvec AS distance
            FROM knowledge_embedding_chunks chunk
            WHERE chunk.status = 'ready' AND chunk.stale_at IS NULL
            ORDER BY distance
            LIMIT 2000
        ), eligible AS (
            SELECT nearest.chunk_id, nearest.content_text, nearest.distance,
                   document.id AS document_id, document.permalink, document.published_at,
                   document.updated_at AS document_updated_at,
                   document.sensitivity_class, document.document_type,
                   source.id AS source_id, source.source_type, source.title AS source_title,
                   source.metadata_json AS source_metadata_json,
                   (document.business_id IS NOT NULL) AS tenant_specific,
                   ROW_NUMBER() OVER (
                       PARTITION BY nearest.chunk_id
                       ORDER BY (document.business_id = %s) DESC,
                                COALESCE(document.published_at, document.updated_at) DESC
                   ) AS tenant_rank
            FROM nearest
            JOIN knowledge_document_chunk_links link ON link.chunk_id = nearest.chunk_id
            JOIN knowledge_documents document ON document.id = link.document_id
            JOIN knowledge_sources source ON source.id = document.source_id
            WHERE {where_sql}
        ), top_candidates AS (
            SELECT * FROM eligible
            WHERE tenant_rank = 1
            ORDER BY distance
            LIMIT 50
        )
        SELECT candidate.*,
               1 - candidate.distance AS similarity,
               COALESCE(
                   (candidate.source_metadata_json->>'retrieval_quality_weight')::numeric,
                   (candidate.source_metadata_json->>'confidence')::numeric,
                   0.7
               ) AS source_confidence,
               GREATEST(0.0, 1.0 - EXTRACT(EPOCH FROM (
                   NOW() - COALESCE(candidate.published_at, candidate.document_updated_at)
               )) / 31557600.0) AS freshness_score,
               COALESCE((
                   SELECT COUNT(DISTINCT evidence.source_id)
                   FROM knowledge_evidence evidence
                   WHERE evidence.document_id = candidate.document_id
                     AND evidence.invalidated_at IS NULL
               ), 0) AS confirmation_count,
               COALESCE((
                   SELECT COUNT(*)
                   FROM knowledge_retrieval_events event
                   WHERE event.result_chunk_ids @> jsonb_build_array(candidate.chunk_id::text)
                     AND event.outcome IN ('accepted', 'published', 'applied')
               ), 0) AS successful_uses,
               COALESCE((
                   SELECT jsonb_agg(DISTINCT evidence.id::text)
                   FROM knowledge_evidence evidence
                   WHERE evidence.document_id = candidate.document_id
                     AND evidence.invalidated_at IS NULL
               ), '[]'::jsonb) AS evidence_ids,
               COALESCE((
                   SELECT jsonb_agg(DISTINCT evidence.assertion_id::text)
                   FROM knowledge_evidence evidence
                   WHERE evidence.document_id = candidate.document_id
                     AND evidence.invalidated_at IS NULL
                     AND evidence.assertion_id IS NOT NULL
               ), '[]'::jsonb) AS assertion_ids
        FROM top_candidates candidate
        ORDER BY candidate.distance
        """,
        [vector_value, request.business_id, *params],
    )
    return [dict(row) for row in cursor.fetchall()]


def _lexical_rows(cursor: Any, request: KnowledgeSearchRequest) -> list[dict[str, Any]]:
    where_sql, params = _filters(request)
    lexical_rank = """
        ts_rank_cd(
            to_tsvector('russian', chunk.content_text),
            plainto_tsquery('russian', %s)
        ) AS lexical_rank
    """
    cursor.execute(
        f"""
        SELECT candidate.*, candidate.lexical_rank AS similarity
        FROM (
            {_base_select(lexical_rank)}
            WHERE {where_sql}
              AND to_tsvector('russian', chunk.content_text) @@ plainto_tsquery('russian', %s)
            ORDER BY chunk.id, lexical_rank DESC
        ) candidate
        ORDER BY candidate.lexical_rank DESC
        LIMIT 50
        """,
        [request.query, *params, request.query],
    )
    return [dict(row) for row in cursor.fetchall()]


def _rrf(vector_rows: list[dict[str, Any]], lexical_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    combined: dict[str, dict[str, Any]] = {}
    for mode, rows in (("vector", vector_rows), ("lexical", lexical_rows)):
        for index, row in enumerate(rows, start=1):
            chunk_id = str(row.get("chunk_id") or "")
            item = combined.setdefault(chunk_id, {**row, "rrf_score": 0.0, "modes": []})
            item["rrf_score"] += 1.0 / (60 + index)
            item["modes"].append(mode)
            if mode == "vector":
                item["vector_similarity"] = float(row.get("similarity") or 0)
    for item in combined.values():
        item["quality_score"] = (
            float(item.get("rrf_score") or 0)
            + 0.0015 * min(float(item.get("source_confidence") or 0), 1.0)
            + 0.0010 * min(float(item.get("freshness_score") or 0), 1.0)
            + 0.0005 * min(int(item.get("confirmation_count") or 0), 5)
            + 0.0005 * min(int(item.get("successful_uses") or 0), 5)
            + (0.0010 if bool(item.get("tenant_specific")) else 0.0)
        )
    return sorted(
        combined.values(),
        key=lambda item: (
            float(item.get("quality_score") or 0),
            float(item.get("rrf_score") or 0),
        ),
        reverse=True,
    )


def retrieve_knowledge(conn, request: KnowledgeSearchRequest) -> dict[str, Any]:
    started = time.monotonic()
    safe_limit = max(1, min(int(request.limit or 12), 15))
    if not request.business_id or not request.query.strip() or not request.purpose:
        return {"hits": [], "mode": "none", "event_id": "", "reason": "INVALID_REQUEST"}
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    if not _table_exists(cursor, "knowledge_embedding_chunks"):
        cursor.close()
        return {"hits": [], "mode": "none", "event_id": "", "reason": "SCHEMA_UNAVAILABLE"}
    lexical_rows = _lexical_rows(cursor, request)
    vector_rows: list[dict[str, Any]] = []
    vector_error = ""
    if _enabled() and _business_allowed(request.business_id):
        try:
            response = GigaChatEmbeddingClient().embed([_query_instruction(request)])
            vectors = response.get("vectors") or []
            if vectors:
                vector_rows = _vector_rows(cursor, request, vectors[0])
        except Exception as error:
            vector_error = type(error).__name__
    ranked = _rrf(vector_rows, lexical_rows)
    selected: list[dict[str, Any]] = []
    source_counts: dict[str, int] = {}
    for row in ranked:
        source_id = str(row.get("source_id") or "")
        if source_counts.get(source_id, 0) >= 3:
            continue
        source_counts[source_id] = source_counts.get(source_id, 0) + 1
        selected.append(row)
        if len(selected) >= safe_limit:
            break
    mode = "hybrid" if vector_rows and lexical_rows else "vector" if vector_rows else "lexical" if lexical_rows else "none"
    event_id = str(uuid.uuid4())
    latency_ms = int((time.monotonic() - started) * 1000)
    cursor.execute(
        """
        INSERT INTO knowledge_retrieval_events (
            id, pipeline_id, business_id, consumer, purpose, query_hash,
            retrieval_mode, result_chunk_ids, selected_evidence_ids, latency_ms,
            metadata_json
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            event_id,
            request.pipeline_id or None,
            request.business_id,
            request.consumer,
            request.purpose,
            hashlib.sha256(request.query.encode("utf-8")).hexdigest(),
            mode,
            Json([str(row.get("chunk_id") or "") for row in selected]),
            Json(list(dict.fromkeys(
                evidence_id
                for row in selected
                for evidence_id in list(row.get("evidence_ids") or [])
            ))),
            latency_ms,
            Json({"vector_error": vector_error, "shadow": _shadow_enabled()}),
        ),
    )
    cursor.close()
    hits = [
        KnowledgeHit(
            document_id=str(row.get("document_id") or ""),
            chunk_id=str(row.get("chunk_id") or ""),
            source_id=str(row.get("source_id") or ""),
            excerpt=str(row.get("content_text") or "")[:3000],
            permalink=str(row.get("permalink") or ""),
            published_at=row.get("published_at"),
            similarity=float(row.get("vector_similarity") or row.get("similarity") or 0),
            source_type=str(row.get("source_type") or row.get("document_type") or ""),
            sensitivity_class=str(row.get("sensitivity_class") or ""),
            evidence_ids=list(row.get("evidence_ids") or []),
            assertion_ids=list(row.get("assertion_ids") or []),
            provenance={
                "source_title": str(row.get("source_title") or ""),
                "modes": list(row.get("modes") or []),
                "rrf_score": float(row.get("rrf_score") or 0),
            },
        )
        for row in selected
    ]
    return {"hits": hits, "mode": mode, "event_id": event_id, "latency_ms": latency_ms}


def _shadow_enabled() -> bool:
    return str(os.getenv("KNOWLEDGE_EMBEDDINGS_SHADOW") or "true").lower() in {"1", "true", "yes", "on"}


def retrieval_context(result: dict[str, Any], *, max_chars: int = 12000) -> tuple[str, dict[str, Any]]:
    hits = result.get("hits") if isinstance(result.get("hits"), list) else []
    blocks: list[str] = []
    used = 0
    for index, hit in enumerate(hits, start=1):
        if not isinstance(hit, KnowledgeHit):
            continue
        block = f"[{index}] {hit.excerpt}\nИсточник: {hit.permalink or hit.source_id}"
        remaining = max_chars - used
        if remaining <= 0:
            break
        blocks.append(block[:remaining])
        used += len(blocks[-1])
    metadata = {
        "retrieval_event_id": str(result.get("event_id") or ""),
        "retrieval_mode": str(result.get("mode") or "none"),
        "knowledge_document_ids": [hit.document_id for hit in hits if isinstance(hit, KnowledgeHit)],
        "knowledge_chunk_ids": [hit.chunk_id for hit in hits if isinstance(hit, KnowledgeHit)],
        "knowledge_evidence_ids": list(dict.fromkeys(
            evidence_id for hit in hits if isinstance(hit, KnowledgeHit) for evidence_id in hit.evidence_ids
        )),
    }
    return "\n\n".join(blocks), metadata


def semantic_context_for_connection(
    conn,
    *,
    business_id: str,
    query: str,
    purpose: str,
    consumer: str,
    pipeline_id: str = "",
    source_types: tuple[str, ...] = (),
) -> tuple[str, dict[str, Any]]:
    if not _enabled() or not _business_allowed(business_id):
        return "", {"retrieval_reason": "disabled_or_outside_cohort"}
    safe_query, _ = redact_text(query)
    if not safe_query.strip():
        return "", {"retrieval_reason": "empty_after_redaction"}
    try:
        result = retrieve_knowledge(
            conn,
            KnowledgeSearchRequest(
                business_id=business_id,
                query=safe_query[:4000],
                purpose=purpose,
                source_types=source_types,
                pipeline_id=pipeline_id,
                consumer=consumer,
            ),
        )
        context, metadata = retrieval_context(result)
        if _shadow_enabled():
            return "", {**metadata, "retrieval_shadow": True}
        return context, {**metadata, "retrieval_shadow": False}
    except Exception as error:
        return "", {"retrieval_reason": "retrieval_failed", "retrieval_error": type(error).__name__}


def semantic_context_for_cursor(cursor: Any, **kwargs: Any) -> tuple[str, dict[str, Any]]:
    conn = getattr(cursor, "connection", None)
    if conn is None:
        return "", {"retrieval_reason": "connection_unavailable"}
    return semantic_context_for_connection(conn, **kwargs)


def semantic_context_for_business(**kwargs: Any) -> tuple[str, dict[str, Any]]:
    if not _enabled():
        return "", {"retrieval_reason": "disabled"}
    from database_manager import DatabaseManager

    db = DatabaseManager()
    try:
        result = semantic_context_for_connection(db.conn, **kwargs)
        db.conn.commit()
        return result
    except Exception:
        db.conn.rollback()
        return "", {"retrieval_reason": "retrieval_failed"}
    finally:
        db.close()


def record_retrieval_outcome(
    conn,
    *,
    event_id: str,
    outcome: str,
    edit_ratio: float | None = None,
    selected_evidence_ids: list[str] | None = None,
) -> bool:
    allowed = {"shown", "accepted", "edited", "rejected", "published", "applied", "reverted", "stale"}
    if outcome not in allowed:
        raise ValueError("UNKNOWN_RETRIEVAL_OUTCOME")
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE knowledge_retrieval_events
        SET outcome = %s, edit_ratio = %s,
            selected_evidence_ids = CASE WHEN %s IS NULL THEN selected_evidence_ids ELSE %s END,
            updated_at = NOW()
        WHERE id = %s
        """,
        (
            outcome,
            None if edit_ratio is None else max(0.0, min(float(edit_ratio), 1.0)),
            None if selected_evidence_ids is None else "provided",
            Json(selected_evidence_ids or []),
            event_id,
        ),
    )
    updated = int(getattr(cursor, "rowcount", 0) or 0) > 0
    cursor.close()
    return updated
