from __future__ import annotations

import json
import os
import re
from typing import Any, Callable

from core.telegram_userbot import fetch_recent_messages, load_userbot_account
from services.telegram_account_permissions_service import assert_account_access
from services.telegram_opportunity_radar import (
    _row_to_dict,
    ingest_opportunity,
    normalize_keywords,
    notify_owner_for_opportunity,
    score_message,
)


FetchMessagesFunc = Callable[..., dict[str, Any]]


def _env_int(name: str, default: int, *, minimum: int = 1, maximum: int = 1000) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except Exception:
        value = default
    return max(minimum, min(value, maximum))


def _load_active_sources(cursor: Any, *, business_id: str | None = None, limit: int = 25) -> list[dict[str, Any]]:
    params: list[Any] = []
    where = ["is_active = TRUE"]
    if business_id:
        where.append("business_id = %s")
        params.append(business_id)
    params.append(max(1, min(int(limit or 25), 200)))
    cursor.execute(
        f"""
        SELECT id, business_id, user_id, account_id, source_type, title,
               telegram_chat_id, telegram_username, monitor_config_json,
               last_message_id, last_checked_at
        FROM telegram_opportunity_sources
        WHERE {" AND ".join(where)}
        ORDER BY
            CASE WHEN last_checked_at IS NULL THEN 0 ELSE 1 END,
            last_checked_at ASC NULLS FIRST,
            updated_at ASC NULLS FIRST
        LIMIT %s
        """,
        tuple(params),
    )
    return [_row_to_dict(cursor, row) or {} for row in cursor.fetchall() or []]


def _source_keywords(source: dict[str, Any]) -> list[str]:
    config = source.get("monitor_config_json")
    if isinstance(config, str):
        try:
            config = json.loads(config)
        except Exception:
            config = {}
    if not isinstance(config, dict):
        return []
    return normalize_keywords(config.get("keywords"))


def _match_keywords(text: str, keywords: list[str]) -> list[str]:
    normalized_text = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    if not normalized_text:
        return []
    hits: list[str] = []
    for keyword in keywords:
        normalized_keyword = re.sub(r"\s+", " ", keyword.lower()).strip()
        if not normalized_keyword:
            continue
        keyword_variants = {normalized_keyword}
        if re.search(r"[а-яё]", normalized_keyword):
            stem = re.sub(
                r"(ностями|ностью|ности|ность|ение|ении|ения|ями|ами|ого|ему|ыми|ими|ой|ая|ое|ые|ий|ый|ия|ие|ии|а|я|ы|и|е|у|ю|ь)$",
                "",
                normalized_keyword,
            ).strip()
            if len(stem) >= 5:
                keyword_variants.add(stem)
        if any(variant and variant in normalized_text for variant in keyword_variants):
            hits.append(keyword)
    return hits


def _message_to_payload(
    source: dict[str, Any],
    message: dict[str, Any],
    *,
    account_id: str | None,
    keyword_hits: list[str],
) -> dict[str, Any]:
    text = str(message.get("text") or "").strip()
    local_score = score_message(text) or {}
    keyword_score = min(100, 55 + max(0, len(keyword_hits) - 1) * 5)
    score = max(int(local_score.get("score") or 0), keyword_score)
    signal_type = str(local_score.get("signal_type") or "keyword_match")
    reason_parts: list[str] = []
    if keyword_hits:
        reason_parts.append("Слова поиска: " + ", ".join(keyword_hits[:6]))
    if local_score.get("reason"):
        reason_parts.append(str(local_score["reason"]))

    return {
        "business_id": str(source.get("business_id") or ""),
        "user_id": str(source.get("user_id") or "").strip() or None,
        "account_id": account_id,
        "source": {
            "title": str(source.get("title") or source.get("telegram_chat_id") or ""),
            "telegram_chat_id": str(source.get("telegram_chat_id") or ""),
            "telegram_username": str(source.get("telegram_username") or "").strip(),
            "source_type": str(source.get("source_type") or "chat"),
            "monitor_config": source.get("monitor_config_json") if isinstance(source.get("monitor_config_json"), dict) else {},
        },
        "message": {
            "id": str(message.get("id") or ""),
            "text": text,
            "date": message.get("date"),
            "sender_id": message.get("sender_id"),
        },
        "signal_type": signal_type,
        "score": score,
        "reason": " · ".join(reason_parts) or None,
        "raw_payload": {
            "source": "telegram_opportunity_monitor",
            "keyword_hits": keyword_hits,
            "telegram_message": message,
        },
    }


def _mark_source_checked(
    cursor: Any,
    source_id: str,
    *,
    last_message_id: str | None = None,
    needs_attention_reason: str | None = None,
) -> None:
    cursor.execute(
        """
        UPDATE telegram_opportunity_sources
        SET last_message_id = COALESCE(%s, last_message_id),
            last_checked_at = NOW(),
            needs_attention_reason = %s,
            updated_at = NOW()
        WHERE id = %s
        """,
        (last_message_id, needs_attention_reason, source_id),
    )


def _resolve_account(cursor: Any, source: dict[str, Any]) -> dict[str, Any] | None:
    configured_account_id = str(os.getenv("TELEGRAM_OPPORTUNITY_MONITOR_ACCOUNT_ID") or "").strip()
    source_account_id = str(source.get("account_id") or "").strip()
    business_id = str(source.get("business_id") or "").strip()

    account_id = configured_account_id or source_account_id
    account = (
        load_userbot_account(cursor, account_id=account_id, business_id=business_id)
        if account_id
        else load_userbot_account(cursor, business_id=business_id)
    )
    if not account:
        return None
    allowed, _reason, _context = assert_account_access(
        cursor,
        str(account.get("account_id") or ""),
        business_id=business_id,
        scope_type="business",
        capability="radar",
    )
    return account if allowed else None


def run_telegram_opportunity_monitor(
    cursor: Any,
    *,
    business_id: str | None = None,
    source_limit: int | None = None,
    messages_limit: int | None = None,
    fetch_messages_func: FetchMessagesFunc = fetch_recent_messages,
) -> dict[str, Any]:
    safe_source_limit = source_limit or _env_int("TELEGRAM_OPPORTUNITY_MONITOR_SOURCE_LIMIT", 25, minimum=1, maximum=200)
    safe_messages_limit = messages_limit or _env_int("TELEGRAM_OPPORTUNITY_MONITOR_MESSAGES_LIMIT", 20, minimum=1, maximum=100)
    sources = _load_active_sources(cursor, business_id=business_id, limit=safe_source_limit)
    result = {
        "sources_checked": 0,
        "sources_with_errors": 0,
        "messages_seen": 0,
        "matches": 0,
        "created": 0,
        "duplicates": 0,
        "alerts_sent": 0,
        "skipped_no_keywords": 0,
        "skipped_no_account": 0,
    }

    for source in sources:
        source_id = str(source.get("id") or "")
        keywords = _source_keywords(source)
        if not keywords:
            result["skipped_no_keywords"] += 1
            _mark_source_checked(cursor, source_id, needs_attention_reason="keywords_empty")
            continue

        account = _resolve_account(cursor, source)
        if not account:
            result["skipped_no_account"] += 1
            _mark_source_checked(cursor, source_id, needs_attention_reason="telegram_userbot_account_missing")
            continue

        peer = str(source.get("telegram_username") or "").strip()
        if peer:
            peer = "@" + peer.lstrip("@")
        else:
            peer = str(source.get("telegram_chat_id") or "").strip()
        if not peer:
            result["sources_with_errors"] += 1
            _mark_source_checked(cursor, source_id, needs_attention_reason="telegram_peer_missing")
            continue

        try:
            fetched = fetch_messages_func(
                account,
                peer,
                after_message_id=source.get("last_message_id"),
                limit=safe_messages_limit,
            )
        except Exception as exc:
            result["sources_with_errors"] += 1
            _mark_source_checked(cursor, source_id, needs_attention_reason=f"fetch_error:{type(exc).__name__}:{str(exc)[:180]}")
            continue

        if fetched.get("status") != "ok":
            result["sources_with_errors"] += 1
            _mark_source_checked(cursor, source_id, needs_attention_reason=str(fetched.get("status") or "fetch_failed"))
            continue

        result["sources_checked"] += 1
        messages = [item for item in (fetched.get("messages") or []) if isinstance(item, dict)]
        result["messages_seen"] += len(messages)
        max_message_id: int | None = None
        account_id = str(account.get("account_id") or source.get("account_id") or "").strip() or None

        for message in messages:
            try:
                message_id = int(message.get("id") or 0)
                if max_message_id is None or message_id > max_message_id:
                    max_message_id = message_id
            except Exception:
                pass

            text = str(message.get("text") or "").strip()
            hits = _match_keywords(text, keywords)
            if not hits:
                continue
            result["matches"] += 1
            payload = _message_to_payload(source, message, account_id=account_id, keyword_hits=hits)
            ingest_result = ingest_opportunity(cursor, payload)
            if ingest_result.get("created"):
                result["created"] += 1
                alert_result = notify_owner_for_opportunity(cursor, ingest_result.get("opportunity") or {})
                if alert_result.get("sent"):
                    result["alerts_sent"] += 1
            elif ingest_result.get("duplicate"):
                result["duplicates"] += 1

        _mark_source_checked(
            cursor,
            source_id,
            last_message_id=str(max_message_id) if max_message_id is not None else None,
            needs_attention_reason=None,
        )

    return result
