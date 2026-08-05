#!/usr/bin/env python3
"""Compile a reviewable LocalOS outreach pattern from the Telegram B2B corpus.

Dry-run is the default. ``--execute`` writes a draft only; a superadmin must
approve it separately through the canonical outreach API.
"""

from __future__ import annotations

import argparse
import json

from psycopg2.extras import RealDictCursor

from pg_db_utils import get_db_connection
from services.outreach_experiment_service import (
    ACTIVE_SOCIAL_MAP_GAP,
    compile_pattern_draft,
    dedupe_corpus_documents,
    extract_and_review_corpus_pattern,
    pattern_support_ready,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="store a draft pattern")
    parser.add_argument("--user-id", default="", help="operator user id for provenance")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--ai", action="store_true", help="extract with DeepSeek and review with GigaChat Max")
    args = parser.parse_args()
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT document.id, document.content_text AS content,
                   document.permalink AS source_url, source.id AS source_id,
                   source.title AS channel, document.published_at
            FROM knowledge_documents document
            JOIN knowledge_sources source ON source.id = document.source_id
            WHERE document.metadata_json->>'corpus_tag' = 'telegram_b2b'
              AND document.invalidated_at IS NULL
              AND document.content_text ~* '(карт|отзыв|соцсет|telegram|контент|персонализ)'
            ORDER BY document.published_at DESC
            LIMIT %s
            """,
            (max(3, min(args.limit, 1000)),),
        )
        documents = dedupe_corpus_documents([dict(row) for row in cursor.fetchall()])
        summary = {
            "pattern_key": ACTIVE_SOCIAL_MAP_GAP,
            "document_count": len(documents),
            "source_count": len({str(item.get("source_id")) for item in documents}),
            "support_ready": pattern_support_ready(documents),
            "dry_run": not args.execute,
            "external_dispatch_performed": False,
        }
        if not args.execute:
            print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
            conn.rollback()
            return 0
        compiler_result = extract_and_review_corpus_pattern(documents, user_id=args.user_id) if args.ai else None
        pattern = compile_pattern_draft(
            cursor,
            documents,
            user_id=args.user_id,
            compiler_result=compiler_result,
        )
        conn.commit()
        print(json.dumps({**summary, "pattern": pattern}, ensure_ascii=False, indent=2, default=str))
        return 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
