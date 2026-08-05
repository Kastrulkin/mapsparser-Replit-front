#!/usr/bin/env python3
"""Backfill the public Telegram channels from the LocalOS B2B folder snapshot."""

from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any
from urllib import parse, request

from psycopg2.extras import Json

from database_manager import DatabaseManager
from services.knowledge_embeddings import enqueue_document_chunks
from services.knowledge_graph_service import upsert_document, upsert_source
from services.knowledge_public_telegram import parse_public_channel_html


CHANNELS = [
    ("andrew_shishkin", "Андрей Шишкин про B2B лидген"),
    ("startupoftheday", "Стартап дня. Александр Горный."),
    ("salesnotes", "Заметки продавца B2B"),
    ("sekamov", "Tim Sekamov @b2btalks"),
    ("ruminblog", "Упал, поднялся — блог Славы Рюмина"),
    ("floor_99", "Продажник +1 | B2B продажи"),
    ("leadgenvalley", "Про B2B аутрич из Долины"),
    ("marketing_bez_h2o", "Продажи здорового человека"),
    ("dindex", "Индекс дятла"),
    ("betternotworse", "Продакты не нужны"),
    ("disruptors_official", "Дизраптор"),
    ("oravb2b", "Orav Park | The 2 in B2B"),
    ("dimabeseda", "Dima Beseda"),
    ("solokumi", "Kumar & Solo"),
    ("temno", "Тёмная сторона / Темнографика"),
    ("out_of_scope", "OutOfScope | Федор Корягин"),
]
USES = ["market", "outreach", "localos_content", "client_content", "industry_recommendations"]
CORPUS_TAG = "telegram_b2b"


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--business-id", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--max-pages-per-source", default=0, type=int)
    parser.add_argument("--pause-seconds", default=0.25, type=float)
    return parser.parse_args()


def _opener() -> Any:
    proxy_url = str(os.getenv("TELEGRAM_HTTP_PROXY") or os.getenv("OUTBOUND_HTTP_PROXY") or "").strip()
    if proxy_url:
        return request.build_opener(request.ProxyHandler({"http": proxy_url, "https": proxy_url}))
    return request.build_opener()


def _page(opener: Any, username: str, before: int | None) -> list[dict[str, Any]]:
    url = f"https://t.me/s/{parse.quote(username)}"
    if before:
        url += "?" + parse.urlencode({"before": before})
    http_request = request.Request(
        url,
        headers={"User-Agent": "LocalOS-Knowledge-Collector/1.0 (+https://localos.pro)"},
    )
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            with opener.open(http_request, timeout=30) as response:
                html = response.read().decode("utf-8", errors="replace")
            return parse_public_channel_html(html)
        except Exception as error:
            last_error = error
            if attempt < 3:
                time.sleep(2 ** attempt)
    if last_error:
        raise last_error
    return []


def _source(database: DatabaseManager, business_id: str, username: str, title: str) -> dict[str, Any]:
    source = upsert_source(
        database.conn,
        source_type="telegram",
        external_key=f"telegram-public:{username}",
        title=title,
        canonical_url=f"https://t.me/{username}",
        source_role="community",
        visibility="public",
        sensitivity_class="public",
        allowed_uses=USES,
        status="active",
        metadata={
            "telegram_username": username,
            "telegram_source_type": "broadcast_channel",
            "telegram_folder": "b2b",
            "collector": "public_telegram_paginated_backfill",
            "corpus_tag": CORPUS_TAG,
            "segment": "b2b",
            "audience_type": "business",
            "submitted_by_business_id": business_id,
            "submitted_to_shared_catalog": True,
        },
        business_id=None,
        account_id=None,
        sync_mode="public_preview",
        sync_status="ready",
        backfill_days=365,
    )
    cursor = database.conn.cursor()
    cursor.execute(
        """
        INSERT INTO knowledge_source_subscriptions (
            business_id, source_id, purposes_json, topics_json, schedule_json, is_active
        ) VALUES (%s, %s, %s, %s, %s, TRUE)
        ON CONFLICT (business_id, source_id) DO UPDATE SET
            purposes_json = EXCLUDED.purposes_json,
            topics_json = EXCLUDED.topics_json,
            schedule_json = EXCLUDED.schedule_json,
            is_active = TRUE,
            updated_at = NOW()
        """,
        (
            business_id,
            source["id"],
            Json(["outreach_learning", "marketing_learning"]),
            Json(["b2b", CORPUS_TAG, "business_channels_and_chats"]),
            Json({"interval_hours": 24, "telegram_folder": "b2b"}),
        ),
    )
    cursor.close()
    database.conn.commit()
    return source


def _backfill_source(
    database: DatabaseManager,
    opener: Any,
    business_id: str,
    username: str,
    title: str,
    max_pages: int,
    pause_seconds: float,
) -> dict[str, Any]:
    source = _source(database, business_id, username, title)
    before: int | None = None
    pages = 0
    seen_ids: set[int] = set()
    stored = 0
    inserted = 0
    while True:
        messages = _page(opener, username, before)
        pages += 1
        page_ids = [int(item["external_id"]) for item in messages if str(item.get("external_id") or "").isdigit()]
        new_ids = [message_id for message_id in page_ids if message_id not in seen_ids]
        if not messages or not new_ids:
            break
        for message in messages:
            message_id = int(message["external_id"]) if str(message.get("external_id") or "").isdigit() else 0
            if not message_id or message_id in seen_ids:
                continue
            seen_ids.add(message_id)
            _, was_inserted = upsert_document(
                database.conn,
                source_id=str(source["id"]),
                business_id=None,
                external_id=str(message_id),
                document_type="telegram_message",
                title=title,
                content_text=str(message.get("content_text") or ""),
                permalink=message.get("permalink"),
                published_at=message.get("published_at"),
                sensitivity_class="public",
                allowed_uses=USES,
                metadata={
                    "collector": "public_telegram_paginated_backfill",
                    "telegram_folder": "b2b",
                    "corpus_tag": CORPUS_TAG,
                    "segment": "b2b",
                    "audience_type": "business",
                    "embedding_eligible": True,
                    "embedding_policy": "public_source",
                },
            )
            stored += 1
            if was_inserted:
                inserted += 1
        database.conn.commit()
        next_before = min(new_ids)
        if next_before <= 1 or next_before == before:
            break
        before = next_before
        if pages % 25 == 0:
            print(json.dumps({
                "event": "progress",
                "source": title,
                "pages": pages,
                "messages_stored": stored,
                "oldest_message_id": before,
            }, ensure_ascii=False), flush=True)
        if max_pages and pages >= max_pages:
            break
        time.sleep(max(0.0, min(pause_seconds, 5.0)))

    queued = 0
    while True:
        embedding = enqueue_document_chunks(database.conn, limit=10000, source_id=str(source["id"]))
        queued += embedding["queued"]
        database.conn.commit()
        if embedding["documents"] < 10000:
            break
    cursor = database.conn.cursor()
    cursor.execute(
        """
        UPDATE knowledge_sources
        SET last_collected_at = NOW(), sync_status = 'ready',
            backfill_completed_at = COALESCE(backfill_completed_at, NOW()),
            cursor_json = cursor_json || %s, updated_at = NOW()
        WHERE id = %s
        """,
        (Json({"public_backfill_oldest_message_id": before, "public_backfill_pages": pages}), source["id"]),
    )
    cursor.close()
    database.conn.commit()
    return {
        "source_id": str(source["id"]),
        "username": username,
        "title": title,
        "pages": pages,
        "messages_stored": stored,
        "messages_inserted": inserted,
        "embedding_jobs_queued": queued,
    }


def main() -> None:
    args = _arguments()
    opener = _opener()
    if not args.apply:
        preview = []
        for username, title in CHANNELS:
            messages = _page(opener, username, None)
            preview.append({"username": username, "title": title, "latest_page_messages": len(messages)})
        print(json.dumps({"mode": "dry_run", "sources": preview}, ensure_ascii=False, indent=2))
        return
    database = DatabaseManager()
    results: list[dict[str, Any]] = []
    try:
        for username, title in CHANNELS:
            result = _backfill_source(
                database,
                opener,
                args.business_id,
                username,
                title,
                args.max_pages_per_source,
                args.pause_seconds,
            )
            results.append(result)
            print(json.dumps({"event": "source_complete", **result}, ensure_ascii=False), flush=True)
    except Exception:
        database.conn.rollback()
        raise
    finally:
        database.close()
    print(json.dumps({"mode": "apply", "results": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
