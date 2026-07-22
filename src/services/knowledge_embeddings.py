from __future__ import annotations

import hashlib
import json
import os
import socket
import time
import uuid
from dataclasses import dataclass
from typing import Any

import requests
from psycopg2.extras import Json, RealDictCursor

from core.knowledge_policy import detect_pii_flags, redact_text
from services.gigachat_client import get_gigachat_client


EMBEDDING_VERSION = "semantic_memory_v1"
TARGET_CHARS = 2400
OVERLAP_CHARS = 240
ALLOWED_EXTERNAL_CLASSES = {"public", "shared_deidentified"}
BLOCKED_VISIBILITY = {"private", "invite"}
SAFE_TENANT_DOCUMENT_TYPES = {
    "service_observation",
    "localos_recommendation",
    "private_chat_aggregate",
}


def _enabled() -> bool:
    return str(os.getenv("KNOWLEDGE_EMBEDDINGS_ENABLED") or "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _model() -> str:
    return str(os.getenv("KNOWLEDGE_EMBEDDINGS_MODEL") or "EmbeddingsGigaR").strip()


def _business_allowed(business_id: str) -> bool:
    configured = {
        item.strip()
        for item in str(os.getenv("KNOWLEDGE_EMBEDDINGS_BUSINESS_IDS") or "").split(",")
        if item.strip()
    }
    return not configured or not business_id or business_id in configured


def _estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 2) // 3)


def _chunk_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _row_dict(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        return dict(row)
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    return {}


@dataclass(frozen=True)
class TextChunk:
    text: str
    ordinal: int
    char_start: int
    char_end: int
    chunk_hash: str
    token_count: int


def split_text(text: Any, *, target_chars: int = TARGET_CHARS, overlap_chars: int = OVERLAP_CHARS) -> list[TextChunk]:
    value = str(text or "").strip()
    if not value:
        return []
    safe_target = max(600, min(int(target_chars), 6000))
    safe_overlap = max(0, min(int(overlap_chars), safe_target // 3))
    chunks: list[TextChunk] = []
    start = 0
    ordinal = 0
    while start < len(value):
        desired_end = min(len(value), start + safe_target)
        end = desired_end
        if desired_end < len(value):
            search_start = max(start + safe_target // 2, desired_end - 500)
            candidates = [
                value.rfind("\n\n", search_start, desired_end),
                value.rfind(". ", search_start, desired_end),
                value.rfind("\n", search_start, desired_end),
            ]
            boundary = max(candidates)
            if boundary > start:
                end = boundary + (2 if value[boundary:boundary + 2] in {"\n\n", ". "} else 1)
        chunk_text = value[start:end].strip()
        if chunk_text:
            chunks.append(
                TextChunk(
                    text=chunk_text,
                    ordinal=ordinal,
                    char_start=start,
                    char_end=end,
                    chunk_hash=_chunk_hash(chunk_text),
                    token_count=_estimate_tokens(chunk_text),
                )
            )
            ordinal += 1
        if end >= len(value):
            break
        next_start = max(start + 1, end - safe_overlap)
        start = next_start
    return chunks


class GigaChatEmbeddingClient:
    def __init__(self) -> None:
        self.base_url = str(
            os.getenv("KNOWLEDGE_EMBEDDINGS_BASE_URL") or "https://api.giga.chat/v1"
        ).rstrip("/")
        self.model = _model()

    def _headers(self) -> dict[str, str]:
        token = get_gigachat_client().get_access_token()
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def embed(self, texts: list[str]) -> dict[str, Any]:
        if not texts:
            return {"vectors": [], "usage": 0, "request_id": ""}
        started = time.monotonic()
        response = requests.post(
            f"{self.base_url}/embeddings",
            headers=self._headers(),
            json={"model": self.model, "input": texts},
            timeout=90,
            verify=get_gigachat_client().verify_tls,
        )
        response.raise_for_status()
        payload = response.json()
        items = payload.get("data") if isinstance(payload.get("data"), list) else []
        ordered = sorted(items, key=lambda item: int(item.get("index") or 0))
        vectors = [item.get("embedding") for item in ordered if isinstance(item.get("embedding"), list)]
        if len(vectors) != len(texts):
            raise RuntimeError("GIGACHAT_EMBEDDING_COUNT_MISMATCH")
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        prompt_tokens = int(usage.get("prompt_tokens") or sum(_estimate_tokens(text) for text in texts))
        return {
            "vectors": vectors,
            "usage": prompt_tokens,
            "request_id": str(payload.get("id") or response.headers.get("x-request-id") or ""),
            "latency_ms": int((time.monotonic() - started) * 1000),
        }

    def embedding_balance(self) -> int | None:
        try:
            response = requests.get(
                f"{self.base_url}/balance",
                headers=self._headers(),
                timeout=20,
                verify=get_gigachat_client().verify_tls,
            )
            if response.status_code == 403:
                return None
            response.raise_for_status()
            return _find_embedding_balance(response.json())
        except Exception:
            return None


def _find_embedding_balance(value: Any) -> int | None:
    balances: list[int] = []
    if isinstance(value, dict):
        label = str(
            value.get("model") or value.get("name") or value.get("type") or value.get("usage") or ""
        ).lower()
        for key in ("balance", "tokens", "available_tokens", "remaining_tokens", "value"):
            raw = value.get(key)
            if "embedding" in label and isinstance(raw, (int, float)):
                balances.append(int(raw))
        for nested in value.values():
            found = _find_embedding_balance(nested)
            if found is not None:
                balances.append(found)
    elif isinstance(value, list):
        for nested in value:
            found = _find_embedding_balance(nested)
            if found is not None:
                balances.append(found)
    return sum(balances) if balances else None


def _vector_literal(vector: list[Any]) -> str:
    if len(vector) != 2560:
        raise ValueError("EMBEDDING_DIMENSION_MISMATCH")
    return "[" + ",".join(str(float(item)) for item in vector) + "]"


def enqueue_document_chunks(conn, *, limit: int = 1000, document_id: str = "") -> dict[str, int]:
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    filters = [
        "d.invalidated_at IS NULL",
        "s.status = 'active'",
        "s.visibility NOT IN ('private', 'invite')",
        "(d.sensitivity_class IN ('public', 'shared_deidentified') "
        "OR (d.sensitivity_class = 'tenant_confidential' "
        "AND d.document_type = ANY(%s)))",
        "jsonb_array_length(d.allowed_uses) > 0",
    ]
    params: list[Any] = [sorted(SAFE_TENANT_DOCUMENT_TYPES)]
    if document_id:
        filters.append("d.id = %s")
        params.append(document_id)
    params.append(max(1, min(int(limit), 10000)))
    cursor.execute(
        f"""
        SELECT d.id, d.business_id, d.content_text, d.content_hash, d.sensitivity_class,
               d.pii_flags, s.visibility
        FROM knowledge_documents d
        JOIN knowledge_sources s ON s.id = d.source_id
        WHERE {' AND '.join(filters)}
          AND NOT EXISTS (
              SELECT 1 FROM knowledge_document_chunk_links link
              WHERE link.document_id = d.id AND link.document_content_hash = d.content_hash
          )
        ORDER BY d.created_at ASC
        LIMIT %s
        """,
        params,
    )
    documents = [dict(row) for row in cursor.fetchall()]
    linked = 0
    queued = 0
    blocked = 0
    for document in documents:
        safe_text, flags = redact_text(document.get("content_text"))
        declared = list(document.get("pii_flags") or [])
        all_flags = set(declared + flags + detect_pii_flags(safe_text))
        if "secret" in all_flags:
            blocked += 1
            continue
        cursor.execute(
            "DELETE FROM knowledge_document_chunk_links WHERE document_id = %s AND document_content_hash <> %s",
            (document["id"], document["content_hash"]),
        )
        chunks = split_text(safe_text)
        for chunk in chunks:
            chunk_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO knowledge_embedding_chunks (
                    id, chunk_hash, content_text, token_count, embedding_model,
                    embedding_version, status, metadata_json
                ) VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s)
                ON CONFLICT (chunk_hash, embedding_model, embedding_version)
                DO UPDATE SET updated_at = NOW()
                RETURNING id, status
                """,
                (
                    chunk_id,
                    chunk.chunk_hash,
                    chunk.text,
                    chunk.token_count,
                    _model(),
                    EMBEDDING_VERSION,
                    Json({"redacted": safe_text != str(document.get("content_text") or "")}),
                ),
            )
            stored = _row_dict(cursor.fetchone())
            stored_id = str(stored.get("id") or chunk_id)
            cursor.execute(
                """
                INSERT INTO knowledge_document_chunk_links (
                    document_id, chunk_id, document_content_hash, chunk_ordinal, char_start, char_end
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (document_id, chunk_id, chunk_ordinal) DO UPDATE SET
                    document_content_hash = EXCLUDED.document_content_hash,
                    char_start = EXCLUDED.char_start,
                    char_end = EXCLUDED.char_end
                """,
                (
                    document["id"], stored_id, document["content_hash"], chunk.ordinal,
                    chunk.char_start, chunk.char_end,
                ),
            )
            linked += 1
            if str(stored.get("status") or "") != "ready":
                cursor.execute(
                    """
                    INSERT INTO knowledge_embedding_jobs (id, chunk_id, status)
                    VALUES (%s, %s, 'queued')
                    ON CONFLICT DO NOTHING
                    """,
                    (str(uuid.uuid4()), stored_id),
                )
                queued += max(int(getattr(cursor, "rowcount", 0) or 0), 0)
    cursor.execute(
        """
        UPDATE knowledge_embedding_chunks chunk
        SET status = 'stale', stale_at = NOW(), updated_at = NOW()
        WHERE chunk.stale_at IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM knowledge_document_chunk_links link WHERE link.chunk_id = chunk.id
          )
        """
    )
    cursor.close()
    return {"documents": len(documents), "linked": linked, "queued": queued, "blocked": blocked}


def _claim_jobs(conn, batch_size: int) -> list[dict[str, Any]]:
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        """
        WITH due AS (
            SELECT job.id
            FROM knowledge_embedding_jobs job
            JOIN knowledge_embedding_chunks chunk ON chunk.id = job.chunk_id
            WHERE job.status IN ('queued', 'retry')
              AND job.next_attempt_at <= NOW()
              AND chunk.status IN ('pending', 'retry')
            ORDER BY job.created_at
            FOR UPDATE OF job SKIP LOCKED
            LIMIT %s
        )
        UPDATE knowledge_embedding_jobs job
        SET status = 'running', locked_at = NOW(), locked_by = %s,
            attempt_count = attempt_count + 1, updated_at = NOW()
        FROM due
        WHERE job.id = due.id
        RETURNING job.id, job.chunk_id, job.attempt_count, job.max_attempts
        """,
        (batch_size, socket.gethostname()),
    )
    jobs = [dict(row) for row in cursor.fetchall()]
    if jobs:
        cursor.execute(
            """
            SELECT id, content_text, token_count FROM knowledge_embedding_chunks
            WHERE id = ANY(%s::uuid[])
            """,
            ([str(job["chunk_id"]) for job in jobs],),
        )
        chunks = {str(row["id"]): dict(row) for row in cursor.fetchall()}
        for job in jobs:
            job["chunk"] = chunks.get(str(job["chunk_id"])) or {}
    cursor.close()
    return jobs


def process_embedding_jobs(conn, *, batch_size: int | None = None) -> dict[str, Any]:
    if not _enabled():
        return {"status": "disabled", "processed": 0}
    safe_batch = max(1, min(int(batch_size or os.getenv("KNOWLEDGE_EMBEDDINGS_BATCH_SIZE") or 16), 32))
    client = GigaChatEmbeddingClient()
    balance = client.embedding_balance()
    minimum = max(0, int(os.getenv("KNOWLEDGE_EMBEDDINGS_MIN_BALANCE") or 10000000))
    if balance is not None and balance < minimum:
        return {"status": "balance_guard", "processed": 0, "balance": balance}
    jobs = _claim_jobs(conn, safe_batch)
    if not jobs:
        return {"status": "idle", "processed": 0, "balance": balance}
    texts = [str(job.get("chunk", {}).get("content_text") or "") for job in jobs]
    started = time.monotonic()
    try:
        response = client.embed(texts)
        cursor = conn.cursor()
        for job, vector in zip(jobs, response["vectors"]):
            vector_literal = _vector_literal(vector)
            cursor.execute(
                """
                UPDATE knowledge_embedding_chunks
                SET embedding = %s::halfvec, status = 'ready', provider_request_id = %s,
                    error_code = NULL, embedded_at = NOW(), stale_at = NULL, updated_at = NOW()
                WHERE id = %s
                """,
                (vector_literal, response.get("request_id"), job["chunk_id"]),
            )
            cursor.execute(
                """
                SELECT other.id, 1 - (other.embedding <=> %s::halfvec) AS similarity
                FROM knowledge_embedding_chunks other
                WHERE other.id <> %s AND other.status = 'ready' AND other.stale_at IS NULL
                  AND 1 - (other.embedding <=> %s::halfvec) >= 0.92
                ORDER BY other.embedding <=> %s::halfvec
                LIMIT 1
                """,
                (vector_literal, job["chunk_id"], vector_literal, vector_literal),
            )
            nearest = cursor.fetchone()
            if nearest:
                cursor.execute(
                    """
                    UPDATE knowledge_embedding_chunks
                    SET metadata_json = metadata_json || jsonb_build_object(
                        'near_duplicate_of', %s::text,
                        'near_duplicate_similarity', %s::numeric
                    )
                    WHERE id = %s
                    """,
                    (nearest[0], nearest[1], job["chunk_id"]),
                )
            cursor.execute(
                """
                UPDATE knowledge_embedding_jobs
                SET status = 'completed', error_code = NULL, updated_at = NOW()
                WHERE id = %s
                """,
                (job["id"],),
            )
        _record_usage(
            cursor,
            total_tokens=int(response.get("usage") or 0),
            latency_ms=int(response.get("latency_ms") or 0),
            request_id=str(response.get("request_id") or ""),
            chunks=len(jobs),
        )
        cursor.close()
        return {
            "status": "completed",
            "processed": len(jobs),
            "tokens": int(response.get("usage") or 0),
            "balance": balance,
        }
    except Exception as error:
        cursor = conn.cursor()
        code = "EMBEDDING_PROVIDER_ERROR"
        for job in jobs:
            exhausted = int(job.get("attempt_count") or 0) >= int(job.get("max_attempts") or 4)
            cursor.execute(
                """
                UPDATE knowledge_embedding_jobs
                SET status = %s, error_code = %s,
                    next_attempt_at = NOW() + (LEAST(attempt_count, 6) * INTERVAL '5 minutes'),
                    updated_at = NOW()
                WHERE id = %s
                """,
                ("dead_letter" if exhausted else "retry", code, job["id"]),
            )
            cursor.execute(
                "UPDATE knowledge_embedding_chunks SET status = %s, error_code = %s, updated_at = NOW() WHERE id = %s",
                ("failed" if exhausted else "retry", code, job["chunk_id"]),
            )
        cursor.close()
        return {
            "status": "failed",
            "processed": 0,
            "attempted": len(jobs),
            "error_code": code,
            "latency_ms": int((time.monotonic() - started) * 1000),
            "error_type": type(error).__name__,
        }


def _record_usage(cursor: Any, *, total_tokens: int, latency_ms: int, request_id: str, chunks: int) -> None:
    cursor.execute("SELECT to_regclass('public.tokenusage') AS table_name")
    row = cursor.fetchone()
    table_name = row.get("table_name") if isinstance(row, dict) else (row[0] if row else None)
    if not table_name:
        return
    cursor.execute(
        """
        INSERT INTO tokenusage (
            id, task_type, model, prompt_tokens, completion_tokens, total_tokens,
            endpoint, provider, provider_request_id, latency_ms, request_status,
            prompt_version, shadow, metadata_json
        ) VALUES (%s, 'knowledge_embedding', %s, %s, 0, %s, 'embeddings',
                  'gigachat', %s, %s, 'completed', %s, FALSE, %s)
        """,
        (
            str(uuid.uuid4()), _model(), total_tokens, total_tokens, request_id or None,
            latency_ms, EMBEDDING_VERSION, Json({"chunks": chunks, "client_billing": False}),
        ),
    )


def embedding_status(conn) -> dict[str, Any]:
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        """
        SELECT COUNT(*) AS chunks_total,
               COUNT(*) FILTER (WHERE status = 'ready' AND stale_at IS NULL) AS chunks_ready,
               COUNT(*) FILTER (WHERE status IN ('pending', 'retry')) AS chunks_pending,
               COUNT(*) FILTER (WHERE status IN ('failed', 'blocked')) AS chunks_failed,
               COALESCE(SUM(token_count) FILTER (WHERE status = 'ready'), 0) AS indexed_tokens
        FROM knowledge_embedding_chunks
        """
    )
    summary = _row_dict(cursor.fetchone())
    cursor.execute(
        """
        SELECT status, COUNT(*) AS count FROM knowledge_embedding_jobs
        GROUP BY status ORDER BY status
        """
    )
    summary["jobs"] = {str(row["status"]): int(row["count"]) for row in cursor.fetchall()}
    cursor.close()
    return summary


def run_embedding_maintenance(conn) -> dict[str, int]:
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE knowledge_embedding_jobs
        SET status = 'retry', locked_at = NULL, locked_by = NULL,
            next_attempt_at = NOW(), error_code = 'STALE_LOCK_RECOVERED', updated_at = NOW()
        WHERE status = 'running' AND locked_at < NOW() - INTERVAL '20 minutes'
        """
    )
    recovered_jobs = max(int(getattr(cursor, "rowcount", 0) or 0), 0)
    cursor.execute(
        """
        UPDATE knowledge_embedding_chunks chunk
        SET status = 'stale', stale_at = COALESCE(stale_at, NOW()), updated_at = NOW()
        WHERE NOT EXISTS (
            SELECT 1 FROM knowledge_document_chunk_links link WHERE link.chunk_id = chunk.id
        ) AND chunk.status <> 'stale'
        """
    )
    stale_chunks = max(int(getattr(cursor, "rowcount", 0) or 0), 0)
    cursor.execute(
        """
        DELETE FROM knowledge_embedding_chunks chunk
        WHERE chunk.status = 'stale' AND chunk.stale_at < NOW() - INTERVAL '30 days'
          AND NOT EXISTS (
              SELECT 1 FROM knowledge_document_chunk_links link WHERE link.chunk_id = chunk.id
          )
        """
    )
    deleted_chunks = max(int(getattr(cursor, "rowcount", 0) or 0), 0)
    cursor.execute(
        """
        WITH source_quality AS (
            SELECT source.id,
                   COUNT(DISTINCT event.id) AS uses,
                   COUNT(DISTINCT event.id) FILTER (
                       WHERE event.outcome IN ('accepted', 'published', 'applied')
                   ) AS successes
            FROM knowledge_sources source
            JOIN knowledge_documents document ON document.source_id = source.id
            JOIN knowledge_document_chunk_links link ON link.document_id = document.id
            JOIN knowledge_retrieval_events event
              ON event.result_chunk_ids @> jsonb_build_array(link.chunk_id::text)
            WHERE event.created_at >= NOW() - INTERVAL '90 days'
            GROUP BY source.id
            HAVING COUNT(DISTINCT event.id) >= 5
        )
        UPDATE knowledge_sources source
        SET metadata_json = source.metadata_json || jsonb_build_object(
                'retrieval_quality_weight',
                LEAST(1.0, GREATEST(0.2, quality.successes::numeric / quality.uses::numeric))
            ),
            updated_at = NOW()
        FROM source_quality quality
        WHERE source.id = quality.id
        """
    )
    recalibrated_sources = max(int(getattr(cursor, "rowcount", 0) or 0), 0)
    cursor.close()
    return {
        "recovered_jobs": recovered_jobs,
        "stale_chunks": stale_chunks,
        "deleted_chunks": deleted_chunks,
        "recalibrated_sources": recalibrated_sources,
    }
