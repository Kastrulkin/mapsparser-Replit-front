#!/usr/bin/env python3
"""Read-only canary for the native Yandex Maps review parser."""

import argparse
import json
import os
import random
import sys
import time
import uuid


DEFAULT_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = str(os.getenv("LOCALOS_PROJECT_ROOT") or ("/app" if os.path.isdir("/app/src") else DEFAULT_PROJECT_ROOT))
SRC_PATH = os.path.join(PROJECT_ROOT, "src")
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

from database_manager import DatabaseManager
from parser_config import parse_yandex_card
from parser_config_cookies import get_yandex_cookies


def _proxy_for_playwright() -> dict | None:
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        cursor.execute(
            """
            SELECT proxy_type, host, port, username, password
            FROM proxyservers
            WHERE is_active = TRUE
            ORDER BY
                CASE WHEN is_working = TRUE THEN 0 ELSE 1 END,
                ((COALESCE(success_count, 0) + 1.0)
                    / (COALESCE(success_count, 0) + COALESCE(failure_count, 0) + 2.0)) DESC,
                COALESCE(last_checked_at, TIMESTAMP '1970-01-01') DESC
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        if not row:
            return None
        payload = dict(row)
    finally:
        db.close()

    host = str(payload.get("host") or "").strip()
    port = payload.get("port")
    if not host or not port:
        return None
    proxy_type = str(payload.get("proxy_type") or "http").strip().lower()
    result = {"server": f"{proxy_type}://{host}:{port}"}
    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "").strip()
    if username and password:
        if "brd-customer-" in username and "-session-" not in username:
            username = f"{username}-session-{int(time.time())}{random.randint(100000, 999999)}"
            rotation = [
                item.strip().lower()
                for item in str(os.getenv("PROXY_COUNTRY_ROTATION") or "").split(",")
                if item.strip()
            ]
            countries = [item for item in rotation if len(item) == 2 and item.isalpha()]
            if countries:
                username = f"{username}-country-{random.choice(countries)}"
        result["username"] = username
        result["password"] = password
    return result


def _run_once(url: str, attempt: int, use_proxy: bool = True) -> dict:
    started = time.monotonic()
    debug_bundle_id = f"native_canary_{attempt}_{uuid.uuid4().hex[:10]}"
    try:
        result = parse_yandex_card(
            url,
            keep_open_on_captcha=False,
            cookies=get_yandex_cookies(),
            proxy=_proxy_for_playwright() if use_proxy else None,
            headless=True,
            locale="ru-RU",
            timezone_id="Europe/Moscow",
            debug_bundle_id=debug_bundle_id,
        )
    except Exception as exc:
        return {
            "attempt": attempt,
            "duration_sec": round(time.monotonic() - started, 2),
            "error": exc.__class__.__name__,
            "message": str(exc)[:300],
            "debug_bundle_id": debug_bundle_id,
        }

    reviews = result.get("reviews") if isinstance(result, dict) else []
    if isinstance(reviews, dict):
        reviews = reviews.get("items") or []
    if not isinstance(reviews, list):
        reviews = []
    distinct_ids = {
        str(item.get("id") or f"{item.get('author')}|{item.get('text')}")
        for item in reviews
        if isinstance(item, dict) and str(item.get("text") or "").strip()
    }
    return {
        "attempt": attempt,
        "duration_sec": round(time.monotonic() - started, 2),
        "error": str(result.get("error") or ""),
        "title": str(result.get("title") or result.get("name") or ""),
        "reported_reviews_count": result.get("reviews_count"),
        "parsed_reviews_count": len(distinct_ids),
        "captcha": str(result.get("error") or "") == "captcha_detected",
        "debug_bundle_id": debug_bundle_id,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--expected-min", required=True, type=int)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument(
        "--no-proxy",
        action="store_true",
        help="Run directly, bypassing the configured proxy pool.",
    )
    args = parser.parse_args()

    results = [
        _run_once(args.url, attempt, use_proxy=not args.no_proxy)
        for attempt in range(1, args.attempts + 1)
    ]
    print(json.dumps({"expected_min": args.expected_min, "attempts": results}, ensure_ascii=False, indent=2))
    complete = [
        item
        for item in results
        if not item.get("error") and int(item.get("parsed_reviews_count") or 0) >= args.expected_min
    ]
    return 0 if len(complete) == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
