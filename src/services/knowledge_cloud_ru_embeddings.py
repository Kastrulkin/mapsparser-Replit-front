"""Parallel Cloud.ru embedding space that leaves the current GigaChat index intact."""
from __future__ import annotations

import os
import socket
import time
import uuid
from dataclasses import dataclass
from typing import Any

from psycopg2.extras import RealDictCursor

from services.ai_spend_budget import BudgetDenied
from services.cloud_ru_foundation import (
    CloudRuConfig,
    CloudRuFoundationClient,
    DEFAULT_EMBEDDING_DIMENSIONS,
)


DEFAULT_VERSION = "cloudru_giga_embeddings_3b_v1"


def _enabled() -> bool:
    return str(os.getenv("CLOUD_RU_EMBEDDINGS_ENABLED") or "").strip().lower() in {
        "1", "true", "yes", "on",
    }


@dataclass(frozen=True)
class CloudRuEmbeddingSpace:
    provider: str
    model: str
    version: str
    dimensions: int


def embedding_space() -> CloudRuEmbeddingSpace:
    config = CloudRuConfig.from_env()
    config.validate_model(config.embedding_model)
    return CloudRuEmbeddingSpace(
        provider="cloudru",
        model=config.embedding_model,
        version=str(os.getenv("CLOUD_RU_EMBEDDING_VERSION") or DEFAULT_VERSION).strip(),
        dimensions=config.embedding_dimensions,
    )


def _vector_literal(vector: list[Any], *, dimensions: int = DEFAULT_EMBEDDING_DIMENSIONS) -> str:
    if len(vector) != dimensions:
        raise ValueError("CLOUD_RU_EMBEDDING_DIMENSION_MISMATCH")
    return "[" + ",".join(str(float(item)) for item in vector) + "]"


def enqueue_cloud_ru_vectors(conn, *, limit: int = 1000) -> dict[str, int]:
    space = embedding_space()
    cursor = conn.cursor()
    cursor.execute(
        """
        WITH candidates AS (
            SELECT DISTINCT ON (chunk.chunk_hash) chunk.id
            FROM knowledge_embedding_chunks chunk
            WHERE chunk.status <> 'stale'
              AND EXISTS (
                  SELECT 1 FROM knowledge_document_chunk_links link
                  WHERE link.chunk_id = chunk.id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM knowledge_embedding_vectors vector
                  WHERE vector.chunk_id = chunk.id
                    AND vector.provider = %s
                    AND vector.model = %s
                    AND vector.embedding_version = %s
              )
            ORDER BY chunk.chunk_hash, chunk.created_at ASC
            LIMIT %s
        )
        INSERT INTO knowledge_embedding_vectors (
            id, chunk_id, provider, model, embedding_version, dimensions, status
        )
        SELECT gen_random_uuid(), candidate.id, %s, %s, %s, %s, 'pending'
        FROM candidates candidate
        ON CONFLICT (chunk_id, provider, model, embedding_version) DO NOTHING
        """,
        (
            space.provider,
            space.model,
            space.version,
            max(1, min(int(limit), 10000)),
            space.provider,
            space.model,
            space.version,
            space.dimensions,
        ),
    )
    queued = max(int(getattr(cursor, "rowcount", 0) or 0), 0)
    cursor.close()
    return {"queued": queued}


def _claim_vectors(conn, *, batch_size: int) -> list[dict[str, Any]]:
    space = embedding_space()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        """
        WITH due AS (
            SELECT vector.id
            FROM knowledge_embedding_vectors vector
            WHERE vector.provider = %s
              AND vector.model = %s
              AND vector.embedding_version = %s
              AND vector.dimensions = %s
              AND vector.status IN ('pending', 'retry')
              AND vector.next_attempt_at <= NOW()
            ORDER BY vector.created_at
            FOR UPDATE SKIP LOCKED
            LIMIT %s
        )
        UPDATE knowledge_embedding_vectors vector
        SET status = 'running', locked_at = NOW(), locked_by = %s,
            attempt_count = attempt_count + 1, updated_at = NOW()
        FROM due
        WHERE vector.id = due.id
        RETURNING vector.id, vector.chunk_id, vector.attempt_count
        """,
        (
            space.provider,
            space.model,
            space.version,
            space.dimensions,
            batch_size,
            socket.gethostname(),
        ),
    )
    rows = [dict(row) for row in cursor.fetchall()]
    if rows:
        cursor.execute(
            """
            SELECT id, content_text
            FROM knowledge_embedding_chunks
            WHERE id = ANY(%s::uuid[])
            """,
            ([str(row["chunk_id"]) for row in rows],),
        )
        chunks = {str(row["id"]): str(row["content_text"] or "") for row in cursor.fetchall()}
        for row in rows:
            row["content_text"] = chunks.get(str(row["chunk_id"]), "")
    cursor.close()
    return rows


def process_cloud_ru_vectors(conn, *, batch_size: int | None = None) -> dict[str, Any]:
    if not _enabled():
        return {"status": "disabled", "processed": 0}
    safe_batch = max(
        1,
        min(int(batch_size or os.getenv("CLOUD_RU_EMBEDDING_BATCH_SIZE") or 16), 128),
    )
    rows = _claim_vectors(conn, batch_size=safe_batch)
    if not rows:
        return {"status": "idle", "processed": 0}
    started = time.monotonic()
    try:
        response = CloudRuFoundationClient().embeddings(
            [str(row.get("content_text") or "") for row in rows]
        )
        cursor = conn.cursor()
        for row, vector in zip(rows, response.get("vectors") or []):
            cursor.execute(
                """
                UPDATE knowledge_embedding_vectors
                SET embedding_2048 = %s::halfvec(2048), status = 'ready',
                    provider_request_id = %s, error_code = NULL,
                    embedded_at = NOW(), locked_at = NULL, locked_by = NULL,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (_vector_literal(vector), response.get("request_id"), row["id"]),
            )
        cursor.close()
        return {
            "status": "completed",
            "processed": len(rows),
            "tokens": int(response.get("usage") or 0),
        }
    except BudgetDenied:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE knowledge_embedding_vectors
            SET status = 'pending', attempt_count = GREATEST(0, attempt_count - 1),
                next_attempt_at = NOW() + INTERVAL '1 hour',
                locked_at = NULL, locked_by = NULL,
                error_code = 'embedding_budget_exceeded', updated_at = NOW()
            WHERE id = ANY(%s::uuid[])
            """,
            ([str(row["id"]) for row in rows],),
        )
        cursor.close()
        return {"status": "budget_guard", "processed": 0, "attempted": len(rows)}
    except Exception as error:
        cursor = conn.cursor()
        for row in rows:
            exhausted = int(row.get("attempt_count") or 0) >= 4
            cursor.execute(
                """
                UPDATE knowledge_embedding_vectors
                SET status = %s, next_attempt_at = NOW() + INTERVAL '15 minutes',
                    locked_at = NULL, locked_by = NULL,
                    error_code = 'CLOUD_RU_EMBEDDING_PROVIDER_ERROR', updated_at = NOW()
                WHERE id = %s
                """,
                ("failed" if exhausted else "retry", row["id"]),
            )
        cursor.close()
        return {
            "status": "failed",
            "processed": 0,
            "attempted": len(rows),
            "error_code": "CLOUD_RU_EMBEDDING_PROVIDER_ERROR",
            "error_type": type(error).__name__,
            "latency_ms": int((time.monotonic() - started) * 1000),
        }


def cloud_ru_embedding_status(conn) -> dict[str, Any]:
    space = embedding_space()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        """
        SELECT status, COUNT(*) AS count
        FROM knowledge_embedding_vectors
        WHERE provider = %s AND model = %s AND embedding_version = %s
        GROUP BY status ORDER BY status
        """,
        (space.provider, space.model, space.version),
    )
    statuses = {str(row["status"]): int(row["count"]) for row in cursor.fetchall()}
    cursor.close()
    return {
        "provider": space.provider,
        "model": space.model,
        "version": space.version,
        "dimensions": space.dimensions,
        "enabled": _enabled(),
        "statuses": statuses,
    }
