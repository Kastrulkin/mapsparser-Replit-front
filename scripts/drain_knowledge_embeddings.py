#!/usr/bin/env python3
"""Drain the governed GigaChat embedding queue with balance protection."""

from __future__ import annotations

import argparse
import json
import time

from database_manager import DatabaseManager
from services.knowledge_embeddings import process_embedding_jobs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--max-batches", type=int, default=2000)
    parser.add_argument("--pause-seconds", type=float, default=10.0)
    args = parser.parse_args()
    database = DatabaseManager()
    processed = 0
    try:
        for batch_number in range(max(1, args.max_batches)):
            result = process_embedding_jobs(database.conn, batch_size=args.batch_size)
            database.conn.commit()
            processed += int(result.get("processed") or 0)
            if batch_number % 10 == 0 or result.get("status") != "completed":
                print(
                    json.dumps(
                        {"batch": batch_number + 1, "processed_total": processed, **result},
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
            if result.get("status") in {"idle", "disabled", "balance_guard"}:
                break
            pause_seconds = max(0.0, min(args.pause_seconds, 30.0))
            if result.get("status") == "failed":
                pause_seconds = max(pause_seconds, 10.0)
            time.sleep(pause_seconds)
    except Exception:
        database.conn.rollback()
        raise
    finally:
        database.close()


if __name__ == "__main__":
    main()
