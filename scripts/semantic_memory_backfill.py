#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import time
from typing import Any

from database_manager import get_db_connection
from services.knowledge_embedding_ingestion import ingest_semantic_sources
from services.knowledge_embeddings import (
    embedding_status,
    enqueue_document_chunks,
    process_embedding_jobs,
)


def _write(event: str, payload: dict[str, Any]) -> None:
    print(json.dumps({"event": event, **payload}, ensure_ascii=False, default=str), flush=True)


def _ingest_all(batch_size: int) -> None:
    while True:
        conn = get_db_connection()
        try:
            result = ingest_semantic_sources(conn, limit_per_source=batch_size)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        _write("ingest", result)
        if not any(int(value or 0) >= batch_size for value in result.values()):
            return


def _enqueue_all(batch_size: int) -> None:
    while True:
        conn = get_db_connection()
        try:
            result = enqueue_document_chunks(conn, limit=batch_size)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        _write("enqueue", result)
        if int(result.get("documents") or 0) < batch_size:
            return


def _process_once(batch_size: int) -> dict[str, Any]:
    conn = get_db_connection()
    try:
        result = process_embedding_jobs(conn, batch_size=batch_size)
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _drain_queue(workers: int, batch_size: int, pause_seconds: float) -> None:
    idle_rounds = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        while idle_rounds < 3:
            results = list(pool.map(lambda _: _process_once(batch_size), range(workers)))
            processed = sum(int(item.get("processed") or 0) for item in results)
            _write("embedding_batch", {"processed": processed, "workers": results})
            terminal = {str(item.get("status") or "") for item in results}
            if "balance_guard" in terminal:
                _write("stopped", {"reason": "balance_guard"})
                return
            idle_rounds = idle_rounds + 1 if processed == 0 else 0
            time.sleep(max(0.2, pause_seconds))


def main() -> None:
    parser = argparse.ArgumentParser(description="Bounded LocalOS semantic-memory backfill")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--embedding-batch", type=int, default=32)
    parser.add_argument("--source-batch", type=int, default=10000)
    parser.add_argument("--document-batch", type=int, default=10000)
    parser.add_argument("--pause", type=float, default=1.0)
    args = parser.parse_args()
    if str(os.getenv("KNOWLEDGE_EMBEDDINGS_ENABLED") or "").lower() not in {"1", "true", "yes", "on"}:
        raise SystemExit("KNOWLEDGE_EMBEDDINGS_ENABLED is not enabled")
    workers = max(1, min(args.workers, 4))
    embedding_batch = max(1, min(args.embedding_batch, 64))
    source_batch = max(1, min(args.source_batch, 10000))
    document_batch = max(1, min(args.document_batch, 10000))
    _ingest_all(source_batch)
    _enqueue_all(document_batch)
    _drain_queue(workers, embedding_batch, args.pause)
    conn = get_db_connection()
    try:
        _write("complete", embedding_status(conn))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
