#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from psycopg2.extras import RealDictCursor

from database_manager import DatabaseManager
from services.creator_taxonomy_service import classify_creator_catalog


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify creator topics, style, geography, audience, formats, and client fit")
    parser.add_argument("--source", default="spb_catalog_20260823")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--keep-legacy-geography", action="store_true")
    arguments = parser.parse_args()

    database = DatabaseManager()
    cursor = database.conn.cursor(cursor_factory=RealDictCursor)
    try:
        result = classify_creator_catalog(
            cursor,
            import_source=arguments.source,
            limit=arguments.limit,
            normalize_profile_geography=not arguments.keep_legacy_geography,
        )
        if arguments.apply:
            database.conn.commit()
        else:
            database.conn.rollback()
        result["applied"] = arguments.apply
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception:
        database.conn.rollback()
        raise
    finally:
        database.close()


if __name__ == "__main__":
    raise SystemExit(main())
