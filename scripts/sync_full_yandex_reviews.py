#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from database_manager import DatabaseManager
from services.yandex_full_reviews_sync import sync_complete_yandex_reviews


def main() -> int:
    parser = argparse.ArgumentParser(description="Store one complete Yandex review snapshot")
    parser.add_argument("--business-id", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--expected-total", type=int, default=0)
    args = parser.parse_args()

    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        result = sync_complete_yandex_reviews(
            cursor,
            business_id=args.business_id,
            map_url=args.url,
            expected_total=args.expected_total or None,
        )
        db.conn.commit()
        print(json.dumps(result, ensure_ascii=False, default=str))
        return 0
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
