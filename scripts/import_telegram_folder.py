#!/usr/bin/env python3
"""Import every text message from a named Telegram folder into LocalOS knowledge.

Dry-run is the default. Public channels and groups are eligible for governed
embeddings. Private sources are retained in tenant scope and never queued for
the external embedding provider.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from psycopg2.extras import Json, RealDictCursor
from telethon.tl.functions.messages import GetDialogFiltersRequest

from core.knowledge_policy import redact_text
from core.telegram_userbot import _connect_client, classify_telegram_entity, load_userbot_account
from database_manager import DatabaseManager
from services.knowledge_embeddings import enqueue_document_chunks
from services.knowledge_graph_service import upsert_document, upsert_source


PUBLIC_USES = [
    "market",
    "outreach",
    "localos_content",
    "client_content",
    "industry_recommendations",
]
PRIVATE_USES = ["localos_content"]
CORPUS_TAG = "telegram_b2b"
SEGMENT = "b2b"


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", default="B2B")
    parser.add_argument("--account-id", default="")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--commit-every", default=250, type=int)
    parser.add_argument("--max-messages-per-source", default=0, type=int)
    return parser.parse_args()


def _folder_title(value: Any) -> str:
    title = getattr(value, "title", "")
    return str(getattr(title, "text", title) or "").strip()


def _account_rows(database: DatabaseManager, account_id: str) -> list[dict[str, Any]]:
    cursor = database.conn.cursor(cursor_factory=RealDictCursor)
    query = """
        SELECT account.id, account.business_id, business.name AS business_name
        FROM externalbusinessaccounts account
        JOIN telegram_account_permissions permission ON permission.account_id = account.id
        LEFT JOIN businesses business ON business.id = account.business_id
        WHERE account.source = 'telegram_app'
          AND account.is_active = TRUE
          AND permission.radar_enabled = TRUE
    """
    params: list[Any] = []
    if account_id:
        query += " AND account.id = %s"
        params.append(account_id)
    query += " ORDER BY account.updated_at DESC NULLS LAST"
    cursor.execute(query, params)
    rows = [dict(row) for row in cursor.fetchall()]
    cursor.close()
    return rows


async def _folder_dialogs(auth_data: dict[str, Any], folder_name: str) -> tuple[dict[str, Any], list[Any]]:
    client = await _connect_client(auth_data)
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("telegram_account_not_authorized")
        response = await client(GetDialogFiltersRequest())
        filters = list(getattr(response, "filters", response) or [])
        matches = [item for item in filters if _folder_title(item).casefold() == folder_name.casefold()]
        if not matches:
            return {}, []
        folder = matches[0]
        peers = list(getattr(folder, "pinned_peers", None) or []) + list(getattr(folder, "include_peers", None) or [])
        entities: list[Any] = []
        seen: set[tuple[str, str]] = set()
        for peer in peers:
            entity = await client.get_entity(peer)
            key = (type(entity).__name__, str(getattr(entity, "id", "")))
            if key in seen:
                continue
            seen.add(key)
            entities.append(entity)
        return {
            "id": getattr(folder, "id", None),
            "title": _folder_title(folder),
            "explicit_peers": len(peers),
        }, entities
    finally:
        await client.disconnect()


def _dialog_summary(entity: Any) -> dict[str, Any]:
    classification = classify_telegram_entity(entity)
    username = str(classification.get("username") or "").strip().lstrip("@").lower()
    public = bool(username and classification.get("signal_source_eligible"))
    return {
        "entity": entity,
        "entity_id": str(classification.get("entity_id") or getattr(entity, "id", "")),
        "entity_type": str(classification.get("entity_type") or "unknown"),
        "title": str(classification.get("title") or getattr(entity, "name", "Telegram") or "Telegram"),
        "username": username,
        "public": public,
    }


def _source_metadata(item: dict[str, Any], folder_name: str, account_id: str) -> dict[str, Any]:
    return {
        "telegram_chat_id": item["entity_id"],
        "telegram_username": item["username"],
        "telegram_source_type": item["entity_type"],
        "telegram_folder": folder_name,
        "collector": "telegram_userbot_folder_import",
        "corpus_tag": CORPUS_TAG,
        "segment": SEGMENT,
        "audience_type": "business",
        "account_id_used_for_collection": account_id,
    }


def _upsert_subscription(cursor: Any, business_id: str, source_id: str, public: bool) -> None:
    purposes = ["outreach_learning", "marketing_learning"] if public else ["private_research"]
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
            source_id,
            Json(purposes),
            Json([SEGMENT, CORPUS_TAG, "business_channels_and_chats"]),
            Json({"interval_hours": 24, "telegram_folder": "B2B"}),
        ),
    )


def _permalink(item: dict[str, Any], message_id: Any) -> str | None:
    if not item["public"] or not item["username"] or not message_id:
        return None
    return f"https://t.me/{item['username']}/{message_id}"


async def _import_dialog(
    database: DatabaseManager,
    auth_data: dict[str, Any],
    client: Any,
    item: dict[str, Any],
    folder_name: str,
    commit_every: int,
    max_messages: int,
) -> dict[str, Any]:
    account_id = str(auth_data["account_id"])
    business_id = str(auth_data["business_id"])
    if item["public"]:
        external_key = f"telegram-public:{item['username']}"
        visibility = "public"
        sensitivity = "public"
        allowed_uses = PUBLIC_USES
        source_business_id = None
        source_account_id = None
        sync_mode = "public_preview"
        canonical_url = f"https://t.me/{item['username']}"
    else:
        external_key = f"telegram-private:{business_id}:{account_id}:{item['entity_id']}"
        visibility = "private"
        sensitivity = "tenant_confidential"
        allowed_uses = PRIVATE_USES
        source_business_id = business_id
        source_account_id = account_id
        sync_mode = "archive"
        canonical_url = None
    source = upsert_source(
        database.conn,
        source_type="telegram",
        external_key=external_key,
        title=item["title"],
        canonical_url=canonical_url,
        source_role="community",
        visibility=visibility,
        sensitivity_class=sensitivity,
        allowed_uses=allowed_uses,
        status="active",
        metadata=_source_metadata(item, folder_name, account_id),
        business_id=source_business_id,
        account_id=source_account_id,
        sync_mode=sync_mode,
        sync_status="ready",
        backfill_days=365,
    )
    cursor = database.conn.cursor()
    _upsert_subscription(cursor, business_id, str(source["id"]), item["public"])
    cursor.close()
    database.conn.commit()

    seen = 0
    stored = 0
    inserted = 0
    queued = 0
    skipped_non_text = 0
    iterator = client.iter_messages(item["entity"], reverse=True)
    async for message in iterator:
        seen += 1
        if max_messages and seen > max_messages:
            break
        raw_text = str(getattr(message, "message", None) or "").strip()
        if not raw_text:
            skipped_non_text += 1
            continue
        content_text = redact_text(raw_text)[0] if item["public"] else raw_text
        document, was_inserted = upsert_document(
            database.conn,
            source_id=str(source["id"]),
            business_id=None if item["public"] else business_id,
            external_id=str(getattr(message, "id", "")),
            document_type="telegram_message",
            title=item["title"],
            content_text=content_text,
            permalink=_permalink(item, getattr(message, "id", None)),
            published_at=getattr(message, "date", None),
            sensitivity_class=sensitivity,
            allowed_uses=allowed_uses,
            metadata={
                "collector": "telegram_userbot_folder_import",
                "telegram_folder": folder_name,
                "corpus_tag": CORPUS_TAG,
                "segment": SEGMENT,
                "audience_type": "business",
                "embedding_eligible": item["public"],
                "embedding_policy": "public_source" if item["public"] else "blocked_private_source",
                "views": getattr(message, "views", None),
                "forwards": getattr(message, "forwards", None),
            },
        )
        stored += 1
        if was_inserted:
            inserted += 1
        if stored % max(1, commit_every) == 0:
            database.conn.commit()
            print(json.dumps({
                "event": "progress",
                "source": item["title"],
                "stored": stored,
                "inserted": inserted,
                "embedding_jobs_queued": queued,
            }, ensure_ascii=False), flush=True)
    database.conn.commit()
    if item["public"]:
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
        (Json({"folder_import_completed_at": datetime.now(timezone.utc).isoformat()}), source["id"]),
    )
    cursor.close()
    database.conn.commit()
    return {
        "source_id": str(source["id"]),
        "title": item["title"],
        "visibility": visibility,
        "messages_seen": seen,
        "messages_stored": stored,
        "messages_inserted": inserted,
        "non_text_skipped": skipped_non_text,
        "embedding_jobs_queued": queued,
        "embedding_eligible": item["public"],
    }


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    database = DatabaseManager()
    try:
        account_rows = _account_rows(database, args.account_id)
        matches: list[dict[str, Any]] = []
        for row in account_rows:
            cursor = database.conn.cursor()
            auth_data = load_userbot_account(cursor, account_id=str(row["id"]))
            cursor.close()
            if not auth_data:
                continue
            folder, dialogs = await _folder_dialogs(auth_data, args.folder)
            if folder:
                matches.append({"row": row, "auth_data": auth_data, "folder": folder, "dialogs": dialogs})
        if not matches:
            raise RuntimeError(f"telegram_folder_not_found:{args.folder}")
        if len(matches) != 1:
            raise RuntimeError("telegram_folder_is_ambiguous; pass --account-id")
        match = matches[0]
        items = [_dialog_summary(entity) for entity in match["dialogs"]]
        public_count = len([item for item in items if item["public"]])
        preview = {
            "mode": "apply" if args.apply else "dry_run",
            "account_id": str(match["row"]["id"]),
            "business_id": str(match["row"]["business_id"]),
            "business_name": match["row"].get("business_name"),
            "folder": match["folder"],
            "dialogs_count": len(items),
            "public_embedding_eligible": public_count,
            "private_embedding_blocked": len(items) - public_count,
            "dialogs": [
                {
                    "entity_id": item["entity_id"],
                    "entity_type": item["entity_type"],
                    "title": item["title"],
                    "username": item["username"],
                    "visibility": "public" if item["public"] else "private",
                    "corpus_tag": CORPUS_TAG,
                }
                for item in items
            ],
        }
        if not args.apply:
            return preview
        client = await _connect_client(match["auth_data"])
        results: list[dict[str, Any]] = []
        try:
            for item in items:
                result = await _import_dialog(
                    database,
                    match["auth_data"],
                    client,
                    item,
                    args.folder,
                    args.commit_every,
                    args.max_messages_per_source,
                )
                results.append(result)
                print(json.dumps({"event": "source_complete", **result}, ensure_ascii=False), flush=True)
        finally:
            await client.disconnect()
        preview["results"] = results
        return preview
    except Exception:
        database.conn.rollback()
        raise
    finally:
        database.close()


def main() -> None:
    args = _arguments()
    result = asyncio.run(_run(args))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
