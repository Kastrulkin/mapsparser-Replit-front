from __future__ import annotations

import json
import math
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from psycopg2.extras import Json, RealDictCursor

from core.knowledge_policy import redact_text
from core.telegram_userbot import fetch_message_page, fetch_recent_messages, load_userbot_account
from services.knowledge_graph_service import add_evidence, upsert_assertion, upsert_concept, upsert_document


ANALYSIS_VERSION = "telegram-audience-v1"
DEFAULT_BACKFILL_DAYS = 90
SYNC_INTERVAL_MINUTES = 24 * 60
RETRY_INTERVAL_MINUTES = 60

TRAVEL_SIGNAL_RULES: tuple[tuple[str, str, int, tuple[str, ...]], ...] = (
    (
        "pain",
        "Трансфер не подтверждён вовремя",
        78,
        ("не подтверд", "нет подтверждения", "ждём подтверждение", "трансфер не"),
    ),
    (
        "pain",
        "Риск опоздания или неявки водителя",
        76,
        ("водитель опоздал", "водитель не приехал", "не встретили", "опоздал трансфер", "неявка"),
    ),
    (
        "objection",
        "Непонятно, кто отвечает за проблему в поездке",
        70,
        ("кто отвечает", "кому писать", "нет связи", "не отвечает", "поддержка молчит"),
    ),
    (
        "pain",
        "Изменение рейса ломает организацию трансфера",
        72,
        ("перенесли рейс", "задержка рейса", "изменился рейс", "рейс отменили", "номер рейса"),
    ),
    (
        "pain",
        "Турагент рискует отношениями с клиентом",
        74,
        ("клиент недоволен", "потерять клиента", "жалоба клиента", "репутац", "подвели клиента"),
    ),
    (
        "practice",
        "Нужен понятный порядок работы с групповыми поездками",
        64,
        ("группа туристов", "групповой трансфер", "несколько машин", "табличка встречи", "координатор"),
    ),
    (
        "question",
        "Турагент уточняет условия трансфера",
        58,
        ("сколько стоит", "какая комиссия", "как заказать", "можно ли", "подскажите трансфер", "нужен трансфер"),
    ),
    (
        "market_signal",
        "Рабочая ситуация турагента требует внимания",
        50,
        ("турагент", "турист", "трансфер", "аэропорт", "отель", "ваучер", "экскурсия", "бронирование"),
    ),
)

GENERIC_SIGNAL_RULES: tuple[tuple[str, str, int, tuple[str, ...]], ...] = (
    (
        "pain",
        "Клиенты описывают повторяющуюся проблему",
        64,
        ("не работает", "не получается", "проблема", "сложно", "неудобно", "дорого", "долго", "боюсь"),
    ),
    (
        "question",
        "Аудитория задаёт практический вопрос",
        58,
        ("подскажите", "кто знает", "как сделать", "как выбрать", "можно ли", "где найти", "сколько стоит"),
    ),
    (
        "objection",
        "Аудитория сомневается перед решением",
        60,
        ("сомневаюсь", "не уверен", "есть ли смысл", "стоит ли", "опасаюсь", "не доверяю"),
    ),
    (
        "practice",
        "Участники делятся рабочей практикой",
        54,
        ("мы делаем", "у нас работает", "проверено", "мой опыт", "помогло", "решили так"),
    ),
)


def _row_dict(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        return dict(row)
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    return {}


def _json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except Exception:
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    return {}


def mask_phone(value: Any) -> str:
    phone = re.sub(r"\D", "", str(value or ""))
    if len(phone) < 6:
        return ""
    return f"+{phone[:3]}***{phone[-4:]}"


def classify_travel_signal(text: str) -> dict[str, Any] | None:
    normalized = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    if len(normalized) < 18:
        return None
    best: dict[str, Any] | None = None
    for concept_type, label, base_score, markers in TRAVEL_SIGNAL_RULES:
        hits = [marker for marker in markers if marker in normalized]
        if not hits:
            continue
        score = min(100, base_score + max(0, len(hits) - 1) * 6)
        candidate = {
            "concept_type": concept_type,
            "label": label,
            "relevance_score": score,
            "markers": hits[:6],
        }
        if best is None or score > int(best.get("relevance_score") or 0):
            best = candidate
    return best


def classify_market_signal(text: str, industry_key: str) -> dict[str, Any] | None:
    if str(industry_key or "") == "travel":
        travel_signal = classify_travel_signal(text)
        if travel_signal:
            return travel_signal
    normalized = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    if len(normalized) < 18:
        return None
    best: dict[str, Any] | None = None
    for concept_type, label, base_score, markers in GENERIC_SIGNAL_RULES:
        hits = [marker for marker in markers if marker in normalized]
        if not hits:
            continue
        score = min(100, base_score + max(0, len(hits) - 1) * 5)
        candidate = {
            "concept_type": concept_type,
            "label": label,
            "relevance_score": score,
            "markers": hits[:6],
        }
        if best is None or score > int(best.get("relevance_score") or 0):
            best = candidate
    return best


def raw_engagement(message: dict[str, Any]) -> int:
    return (
        int(message.get("views") or 0)
        + int(message.get("forwards") or 0) * 5
        + int(message.get("replies_count") or 0) * 8
        + int(message.get("reactions_total") or 0) * 3
    )


def priority_score(relevance: int, engagement: int) -> int:
    if engagement <= 0:
        return max(0, min(100, relevance))
    return max(0, min(100, round(relevance * 0.65 + engagement * 0.35)))


def _public_permalink(source: dict[str, Any], message_id: Any) -> str | None:
    metadata = _json_dict(source.get("metadata_json"))
    username = str(metadata.get("telegram_username") or "").strip().lstrip("@")
    if not username or not message_id:
        return None
    return f"https://t.me/{username}/{message_id}"


def _source_peer(source: dict[str, Any]) -> str:
    metadata = _json_dict(source.get("metadata_json"))
    username = str(metadata.get("telegram_username") or "").strip()
    if username:
        return "@" + username.lstrip("@")
    return str(metadata.get("telegram_chat_id") or "").strip()


def _source_policy(source: dict[str, Any]) -> tuple[str, list[str]]:
    if str(source.get("visibility") or "").strip() == "public":
        return "public", ["market", "localos_content", "client_content", "industry_recommendations"]
    return "tenant_confidential", ["localos_content"]


def _ingest_message(conn, source: dict[str, Any], message: dict[str, Any]) -> dict[str, Any]:
    text = str(message.get("text") or "").strip()
    if not text:
        return {"stored": False, "signal": False}
    sensitivity, allowed_uses = _source_policy(source)
    stored_text = redact_text(text)[0] if sensitivity == "public" else text
    business_id = str(source.get("business_id") or "").strip() or None
    published_at = None
    if message.get("date"):
        try:
            published_at = datetime.fromisoformat(str(message["date"]).replace("Z", "+00:00"))
        except Exception:
            published_at = None
    source_metadata = _json_dict(source.get("metadata_json"))
    industry_key = str(source_metadata.get("industry_key") or "local_business").strip() or "local_business"
    audience = str(source_metadata.get("audience") or "customers").strip() or "customers"
    signal = classify_market_signal(text, industry_key)
    relevance = int(signal.get("relevance_score") or 0) if signal else 0
    raw_score = raw_engagement(message)
    document, inserted = upsert_document(
        conn,
        source_id=str(source["id"]),
        business_id=business_id,
        external_id=str(message.get("id") or ""),
        document_type="telegram_message",
        title=str(source.get("title") or "Telegram"),
        content_text=stored_text,
        permalink=_public_permalink(source, message.get("id")),
        published_at=published_at,
        sensitivity_class=sensitivity,
        allowed_uses=allowed_uses,
        metadata={
            "collector": "telegram_userbot",
            "views": int(message.get("views") or 0),
            "forwards": int(message.get("forwards") or 0),
            "replies_count": int(message.get("replies_count") or 0),
            "reactions_total": int(message.get("reactions_total") or 0),
            "reactions": message.get("reactions") if isinstance(message.get("reactions"), dict) else {},
            "media_type": message.get("media_type"),
            "raw_engagement": raw_score,
            "relevance_score": relevance,
            "engagement_score": 0,
            "priority_score": relevance,
            "analysis_version": ANALYSIS_VERSION,
        },
    )
    if not signal or relevance < 50:
        return {"stored": True, "inserted": inserted, "signal": False, "document": document}

    concept_business_id = None if sensitivity == "public" else business_id
    concept = upsert_concept(
        conn,
        concept_type=str(signal["concept_type"]),
        label=str(signal["label"]),
        industry=industry_key,
        business_id=concept_business_id,
        sensitivity_class=sensitivity,
        allowed_uses=allowed_uses,
        metadata={"audience": audience, "markers": signal.get("markers") or []},
    )
    assertion = upsert_assertion(
        conn,
        assertion_type="audience_signal",
        subject_type="document",
        subject_id=str(document["id"]),
        predicate="expresses",
        object_type="concept",
        object_id=str(concept["id"]),
        confidence=relevance / 100,
        business_id=concept_business_id,
        industry=industry_key,
        allowed_uses=allowed_uses,
        sensitivity_class=sensitivity,
        analysis_version=ANALYSIS_VERSION,
        metadata={"audience": audience, "relevance_score": relevance},
    )
    excerpt = redact_text(text)[0] if sensitivity == "public" else text
    evidence = add_evidence(
        conn,
        assertion_id=str(assertion["id"]),
        document_id=str(document["id"]),
        source_id=str(source["id"]),
        excerpt=excerpt,
        observed_at=published_at,
        confidence=relevance / 100,
        analysis_version=ANALYSIS_VERSION,
        allowed_uses=allowed_uses,
        sensitivity_class=sensitivity,
        pii_flags=list(document.get("pii_flags") or []),
    )
    if business_id:
        _upsert_opportunity(conn, source, message, document, signal, raw_score)
    return {
        "stored": True,
        "inserted": inserted,
        "signal": True,
        "document": document,
        "assertion": assertion,
        "evidence": evidence,
    }


def _upsert_opportunity(
    conn,
    source: dict[str, Any],
    message: dict[str, Any],
    document: dict[str, Any],
    signal: dict[str, Any],
    raw_score: int,
) -> None:
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT id FROM telegram_opportunity_sources
            WHERE knowledge_source_id = %s AND business_id = %s
            LIMIT 1
            """,
            (source["id"], source["business_id"]),
        )
        source_row = cursor.fetchone()
        radar_source_id = source_row[0] if source_row else None
        if not radar_source_id:
            return
        relevance = int(signal.get("relevance_score") or 0)
        cursor.execute(
            """
            INSERT INTO telegram_opportunities (
                id, business_id, source_id, account_id, telegram_chat_id,
                telegram_message_id, chat_title, sender_id, message_date,
                message_text, message_link, signal_type, score, reason,
                raw_payload_json, knowledge_document_id, relevance_score,
                engagement_score, priority_score
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, 0, %s
            )
            ON CONFLICT (business_id, account_id, telegram_chat_id, telegram_message_id)
            DO UPDATE SET
                message_text = EXCLUDED.message_text,
                message_link = EXCLUDED.message_link,
                score = EXCLUDED.score,
                reason = EXCLUDED.reason,
                raw_payload_json = telegram_opportunities.raw_payload_json || EXCLUDED.raw_payload_json,
                knowledge_document_id = EXCLUDED.knowledge_document_id,
                relevance_score = EXCLUDED.relevance_score,
                priority_score = EXCLUDED.priority_score,
                updated_at = NOW()
            """,
            (
                str(uuid.uuid4()),
                source["business_id"],
                radar_source_id,
                source.get("account_id"),
                _json_dict(source.get("metadata_json")).get("telegram_chat_id") or "",
                str(message.get("id") or ""),
                str(source.get("title") or "Telegram"),
                str(message.get("sender_id") or "") or None,
                message.get("date"),
                str(message.get("text") or ""),
                _public_permalink(source, message.get("id")),
                str(signal.get("concept_type") or "market_signal"),
                relevance,
                "Найдена тема: " + str(signal.get("label") or ""),
                Json({"raw_engagement": raw_score, "markers": signal.get("markers") or []}),
                document["id"],
                relevance,
                relevance,
            ),
        )
    finally:
        cursor.close()


def _recalculate_source_engagement(conn, source_id: str) -> None:
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            SELECT id, COALESCE((metadata_json->>'raw_engagement')::INTEGER, 0) AS raw_engagement,
                   COALESCE((metadata_json->>'relevance_score')::INTEGER, 0) AS relevance_score
            FROM knowledge_documents
            WHERE source_id = %s AND document_type = 'telegram_message' AND invalidated_at IS NULL
            ORDER BY published_at DESC NULLS LAST
            LIMIT 5000
            """,
            (source_id,),
        )
        rows = [dict(row) for row in cursor.fetchall()]
        ranked = sorted(int(row.get("raw_engagement") or 0) for row in rows)
        total = len(ranked)
        for row in rows:
            raw = int(row.get("raw_engagement") or 0)
            if raw <= 0 or total <= 1:
                engagement = 0
            else:
                position = sum(1 for value in ranked if value <= raw) - 1
                engagement = round(position / (total - 1) * 100)
            relevance = int(row.get("relevance_score") or 0)
            priority = priority_score(relevance, engagement)
            cursor.execute(
                """
                UPDATE knowledge_documents
                SET metadata_json = metadata_json || %s, updated_at = NOW()
                WHERE id = %s
                """,
                (Json({"engagement_score": engagement, "priority_score": priority}), row["id"]),
            )
        cursor.execute(
            """
            UPDATE telegram_opportunities o
            SET engagement_score = COALESCE((d.metadata_json->>'engagement_score')::INTEGER, 0),
                priority_score = COALESCE((d.metadata_json->>'priority_score')::INTEGER, o.relevance_score),
                updated_at = NOW()
            FROM knowledge_documents d
            WHERE o.knowledge_document_id = d.id AND d.source_id = %s
            """,
            (source_id,),
        )
    finally:
        cursor.close()


def _load_due_userbot_sources(conn, limit_sources: int) -> list[dict[str, Any]]:
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            SELECT * FROM knowledge_sources
            WHERE source_type = 'telegram'
              AND status = 'active'
              AND sync_mode = 'telegram_userbot'
              AND EXISTS (
                  SELECT 1
                  FROM telegram_account_permissions p
                  WHERE p.account_id = knowledge_sources.account_id
                    AND p.radar_enabled = TRUE
              )
              AND (next_sync_at IS NULL OR next_sync_at <= NOW())
            ORDER BY next_sync_at ASC NULLS FIRST, last_collected_at ASC NULLS FIRST
            LIMIT %s
            """,
            (max(1, min(int(limit_sources or 10), 50)),),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()


FetchPage = Callable[..., dict[str, Any]]
FetchRecent = Callable[..., dict[str, Any]]
SOURCE_SYNC_SAVEPOINT = "telegram_source_sync"


def _source_savepoint(conn, action: str) -> None:
    statements = {
        "begin": f"SAVEPOINT {SOURCE_SYNC_SAVEPOINT}",
        "rollback": f"ROLLBACK TO SAVEPOINT {SOURCE_SYNC_SAVEPOINT}",
        "release": f"RELEASE SAVEPOINT {SOURCE_SYNC_SAVEPOINT}",
    }
    cursor = conn.cursor()
    try:
        cursor.execute(statements[action])
    finally:
        cursor.close()


def run_userbot_market_sync(
    conn,
    *,
    limit_sources: int = 10,
    max_pages_per_source: int = 5,
    fetch_page_func: FetchPage = fetch_message_page,
    fetch_recent_func: FetchRecent = fetch_recent_messages,
) -> dict[str, Any]:
    sources = _load_due_userbot_sources(conn, limit_sources)
    run_id = str(uuid.uuid4())
    result = {
        "run_id": run_id,
        "sources_checked": 0,
        "documents_seen": 0,
        "documents_imported": 0,
        "signals": 0,
        "errors": [],
    }
    if not sources:
        return result
    run_cursor = conn.cursor()
    try:
        run_cursor.execute(
            """
            INSERT INTO knowledge_analysis_runs (
                id, run_type, analysis_version, status, document_count,
                metadata_json, transmitted_classes, started_at
            ) VALUES (%s, 'telegram_market_sync', %s, 'running', 0, %s, '[]'::jsonb, NOW())
            """,
            (run_id, ANALYSIS_VERSION, Json({"sources_selected": len(sources), "external_ai_used": False})),
        )
    finally:
        run_cursor.close()
    for source in sources:
        _source_savepoint(conn, "begin")
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE knowledge_sources SET sync_status = 'syncing', last_sync_error = NULL, updated_at = NOW() WHERE id = %s",
                (source["id"],),
            )
        finally:
            cursor.close()
        try:
            account_id = str(source.get("account_id") or "").strip()
            business_id = str(source.get("business_id") or "").strip()
            account_cursor = conn.cursor()
            try:
                account = load_userbot_account(account_cursor, account_id=account_id, business_id=business_id)
            finally:
                account_cursor.close()
            if not account:
                _finish_source(conn, source["id"], "needs_account", "Telegram-аккаунт не подключён", minutes=RETRY_INTERVAL_MINUTES)
                _source_savepoint(conn, "release")
                continue
            peer = _source_peer(source)
            if not peer:
                raise ValueError("У источника не указан Telegram-чат")
            cursor_state = _json_dict(source.get("cursor_json"))
            backfill_complete = bool(source.get("backfill_completed_at"))
            source_completed = backfill_complete
            max_seen_id = int(cursor_state.get("last_message_id") or 0)
            if backfill_complete:
                response = fetch_recent_func(account, peer, after_message_id=max_seen_id, limit=100)
                pages = [response]
            else:
                pages = []
                before_id = cursor_state.get("backfill_before_id")
                for _index in range(max(1, min(int(max_pages_per_source or 5), 20))):
                    page = fetch_page_func(account, peer, before_message_id=before_id, limit=100)
                    pages.append(page)
                    messages = page.get("messages") if isinstance(page.get("messages"), list) else []
                    ids = [int(item.get("id") or 0) for item in messages if int(item.get("id") or 0) > 0]
                    if not ids:
                        source_completed = True
                        break
                    before_id = min(ids)
                    cutoff = datetime.now(timezone.utc) - timedelta(days=int(source.get("backfill_days") or DEFAULT_BACKFILL_DAYS))
                    dates = [_message_datetime(item.get("date")) for item in messages]
                    if len(messages) < 100 or any(value and value < cutoff for value in dates):
                        source_completed = True
                        break
                cursor_state["backfill_before_id"] = before_id

            for page in pages:
                if page.get("status") != "ok":
                    raise RuntimeError(str(page.get("status") or "Telegram не вернул сообщения"))
                messages = page.get("messages") if isinstance(page.get("messages"), list) else []
                cutoff = datetime.now(timezone.utc) - timedelta(days=int(source.get("backfill_days") or DEFAULT_BACKFILL_DAYS))
                for message in messages:
                    published_at = _message_datetime(message.get("date"))
                    if not backfill_complete and published_at and published_at < cutoff:
                        continue
                    message_id = int(message.get("id") or 0)
                    max_seen_id = max(max_seen_id, message_id)
                    stored = _ingest_message(conn, source, message)
                    if stored.get("stored"):
                        result["documents_seen"] += 1
                    if stored.get("inserted"):
                        result["documents_imported"] += 1
                    if stored.get("signal"):
                        result["signals"] += 1
            cursor_state["last_message_id"] = max_seen_id
            _recalculate_source_engagement(conn, str(source["id"]))
            _finish_source(
                conn,
                source["id"],
                "ready" if source_completed else "partial",
                None,
                minutes=SYNC_INTERVAL_MINUTES if source_completed else 1,
                cursor_state=cursor_state,
                backfill_completed=source_completed,
            )
            result["sources_checked"] += 1
            _source_savepoint(conn, "release")
        except Exception as error:
            message = f"{type(error).__name__}: {str(error)[:240]}"
            result["errors"].append({"source_id": str(source.get("id") or ""), "message": message})
            _source_savepoint(conn, "rollback")
            _finish_source(conn, source["id"], "failed", message, minutes=RETRY_INTERVAL_MINUTES)
            _source_savepoint(conn, "release")
    run_cursor = conn.cursor()
    try:
        run_cursor.execute(
            """
            UPDATE knowledge_analysis_runs
            SET status = %s, document_count = %s, processed_count = %s,
                failed_count = %s, error_json = %s, completed_at = NOW()
            WHERE id = %s
            """,
            (
                "completed" if not result["errors"] else "partial",
                result["documents_seen"],
                result["documents_seen"],
                len(result["errors"]),
                Json({"items": result["errors"]}),
                run_id,
            ),
        )
    finally:
        run_cursor.close()
    return result


def purge_expired_private_telegram_content(conn, *, retention_days: int = 180) -> int:
    safe_days = max(30, min(int(retention_days or 180), 730))
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            WITH expired AS (
                SELECT d.id
                FROM knowledge_documents d
                JOIN knowledge_sources s ON s.id = d.source_id
                WHERE d.document_type = 'telegram_message'
                  AND s.visibility <> 'public'
                  AND COALESCE(d.published_at, d.created_at) < NOW() - (%s * INTERVAL '1 day')
                  AND d.content_text <> '[Содержимое удалено по сроку хранения]'
            )
            UPDATE knowledge_evidence e
            SET excerpt = '[Обезличенный вывод сохранён без исходного сообщения]'
            FROM expired x
            WHERE e.document_id = x.id
            """,
            (safe_days,),
        )
        cursor.execute(
            """
            WITH expired AS (
                SELECT d.id
                FROM knowledge_documents d
                JOIN knowledge_sources s ON s.id = d.source_id
                WHERE d.document_type = 'telegram_message'
                  AND s.visibility <> 'public'
                  AND COALESCE(d.published_at, d.created_at) < NOW() - (%s * INTERVAL '1 day')
                  AND d.content_text <> '[Содержимое удалено по сроку хранения]'
            )
            UPDATE telegram_opportunities o
            SET message_text = '[Содержимое удалено по сроку хранения]',
                sender_id = NULL, message_link = NULL, raw_payload_json = '{}'::jsonb,
                updated_at = NOW()
            FROM expired x
            WHERE o.knowledge_document_id = x.id
            """,
            (safe_days,),
        )
        cursor.execute(
            """
            UPDATE knowledge_documents d
            SET content_text = '[Содержимое удалено по сроку хранения]',
                permalink = NULL,
                metadata_json = d.metadata_json - 'reactions',
                updated_at = NOW()
            FROM knowledge_sources s
            WHERE s.id = d.source_id
              AND d.document_type = 'telegram_message'
              AND s.visibility <> 'public'
              AND COALESCE(d.published_at, d.created_at) < NOW() - (%s * INTERVAL '1 day')
              AND d.content_text <> '[Содержимое удалено по сроку хранения]'
            """,
            (safe_days,),
        )
        return max(int(getattr(cursor, "rowcount", 0) or 0), 0)
    finally:
        cursor.close()


def _message_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _finish_source(
    conn,
    source_id: Any,
    status: str,
    error: str | None,
    *,
    minutes: int,
    cursor_state: dict[str, Any] | None = None,
    backfill_completed: bool = False,
) -> None:
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE knowledge_sources
            SET sync_status = %s,
                last_sync_error = %s,
                cursor_json = CASE WHEN %s IS NULL THEN cursor_json ELSE %s END,
                last_collected_at = CASE WHEN %s IN ('ready', 'partial') THEN NOW() ELSE last_collected_at END,
                backfill_completed_at = CASE WHEN %s THEN COALESCE(backfill_completed_at, NOW()) ELSE backfill_completed_at END,
                next_sync_at = NOW() + (%s * INTERVAL '1 minute'),
                updated_at = NOW()
            WHERE id = %s
            """,
            (
                status,
                error,
                None if cursor_state is None else "provided",
                Json(cursor_state or {}),
                status,
                backfill_completed,
                max(1, minutes),
                source_id,
            ),
        )
    finally:
        cursor.close()


def list_audience_insights(conn, *, business_id: str, industry: str, limit: int = 50) -> list[dict[str, Any]]:
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            SELECT c.id, c.concept_type, c.label, c.industry,
                   COUNT(DISTINCT e.source_id)::INTEGER AS sources_count,
                   COUNT(DISTINCT e.document_id)::INTEGER AS messages_count,
                   ROUND(AVG(a.confidence) * 100)::INTEGER AS relevance_score,
                   ROUND(AVG(COALESCE((d.metadata_json->>'engagement_score')::INTEGER, 0)))::INTEGER AS engagement_score,
                   ROUND(AVG(COALESCE((d.metadata_json->>'priority_score')::INTEGER, a.confidence * 100)))::INTEGER AS priority_score,
                   MAX(e.observed_at) AS last_seen_at,
                   BOOL_OR(s.visibility <> 'public') AS has_private_sources,
                   COALESCE(bd.decision, '') AS decision
            FROM knowledge_concepts c
            JOIN knowledge_assertions a ON a.object_type = 'concept' AND a.object_id = c.id::text AND a.invalidated_at IS NULL
            JOIN knowledge_evidence e ON e.assertion_id = a.id AND e.invalidated_at IS NULL
            JOIN knowledge_sources s ON s.id = e.source_id
            JOIN knowledge_documents d ON d.id = e.document_id
            LEFT JOIN business_audience_insight_decisions bd
              ON bd.concept_id = c.id AND bd.business_id = %s
            WHERE c.industry = %s
              AND (c.business_id IS NULL OR c.business_id = %s)
              AND (s.business_id IS NULL OR s.business_id = %s OR s.visibility = 'public')
              AND c.concept_type IN ('pain', 'question', 'objection', 'practice', 'market_signal')
            GROUP BY c.id, bd.decision
            ORDER BY priority_score DESC, messages_count DESC, last_seen_at DESC NULLS LAST
            LIMIT %s
            """,
            (business_id, industry, business_id, business_id, max(1, min(int(limit or 50), 100))),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()


def decide_audience_insight(
    conn,
    *,
    business_id: str,
    insight_id: str,
    decision: str,
    user_id: str,
) -> dict[str, Any]:
    if decision not in {"use_in_plan", "save_as_rule", "ignored"}:
        raise ValueError("Неизвестное решение")
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            SELECT * FROM knowledge_concepts
            WHERE id = %s
              AND (business_id IS NULL OR business_id = %s)
            """,
            (insight_id, business_id),
        )
        concept = cursor.fetchone()
        if not concept:
            raise LookupError("Сигнал не найден")
        cursor.execute(
            """
            INSERT INTO business_audience_insight_decisions (
                business_id, concept_id, decision, decided_by, decided_at, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, NOW(), NOW(), NOW())
            ON CONFLICT (business_id, concept_id) DO UPDATE SET
                decision = EXCLUDED.decision,
                decided_by = EXCLUDED.decided_by,
                decided_at = NOW(),
                updated_at = NOW()
            RETURNING decision, decided_by, decided_at
            """,
            (business_id, insight_id, decision, user_id),
        )
        decision_row = dict(cursor.fetchone())
        updated = dict(concept)
        updated.update(decision_row)
        if decision == "use_in_plan":
            updated["content_plan_item"] = _add_insight_to_latest_plan(cursor, business_id, updated)
        elif decision == "save_as_rule":
            updated["rule_proposal"] = _create_rule_proposal(cursor, business_id, updated, user_id)
        return updated
    finally:
        cursor.close()


def _add_insight_to_latest_plan(cursor: Any, business_id: str, concept: dict[str, Any]) -> dict[str, Any]:
    metadata = _json_dict(concept.get("metadata_json"))
    industry_key = str(concept.get("industry") or "local_business")
    audience = str(metadata.get("audience") or "customers")
    audience_goal = "Ответить на реальный вопрос или проблему аудитории"
    if industry_key == "travel":
        audience_goal = "Ответить на реальную боль турагентов"
    cursor.execute(
        """
        SELECT id FROM contentplans
        WHERE business_id = %s
        ORDER BY period_start DESC NULLS LAST, created_at DESC
        LIMIT 1
        """,
        (business_id,),
    )
    plan = cursor.fetchone()
    if not plan:
        raise ValueError("Сначала создайте контент-план")
    plan_id = str(plan["id"] if hasattr(plan, "keys") else plan[0])
    cursor.execute(
        """
        SELECT COALESCE(MAX(scheduled_for), CURRENT_DATE) + INTERVAL '1 day' AS scheduled_for
        FROM contentplanitems WHERE plan_id = %s
        """,
        (plan_id,),
    )
    scheduled_row = cursor.fetchone()
    scheduled_for = scheduled_row["scheduled_for"] if hasattr(scheduled_row, "keys") else scheduled_row[0]
    item_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO contentplanitems (
            id, plan_id, business_id, scheduled_for, content_type, theme, goal,
            source_kind, source_ref, draft_text, status, metadata_json, created_at, updated_at
        ) VALUES (
            %s, %s, %s, %s, 'audience_insight', %s,
            %s, 'knowledge', %s,
            '', 'planned', %s, NOW(), NOW()
        )
        RETURNING id, plan_id, scheduled_for, theme, status
        """,
        (
            item_id,
            plan_id,
            business_id,
            scheduled_for,
            str(concept.get("label") or "Тема аудитории"),
            audience_goal,
            str(concept.get("id") or ""),
            Json({
                "knowledge_assertion_ids": [],
                "knowledge_concept_id": str(concept.get("id") or ""),
                "knowledge_scope": f"business_or_public_{industry_key}",
                "industry_key": industry_key,
                "audience": audience,
                "topic_reason": "Тема основана на повторяющихся вопросах и обсуждениях аудитории",
            }),
        ),
    )
    return dict(cursor.fetchone())


def _create_rule_proposal(cursor: Any, business_id: str, concept: dict[str, Any], user_id: str) -> dict[str, Any]:
    industry_key = str(concept.get("industry") or "local_business").strip() or "local_business"
    cursor.execute(
        """
        SELECT COUNT(DISTINCT e.source_id)::INTEGER AS sources_count,
               COUNT(DISTINCT e.document_id)::INTEGER AS messages_count
        FROM knowledge_assertions a
        JOIN knowledge_evidence e ON e.assertion_id = a.id AND e.invalidated_at IS NULL
        WHERE a.object_type = 'concept' AND a.object_id = %s AND a.invalidated_at IS NULL
        """,
        (str(concept.get("id") or ""),),
    )
    counts = _row_dict(cursor.fetchone())
    sources_count = int(counts.get("sources_count") or 0)
    messages_count = int(counts.get("messages_count") or 0)
    if sources_count < 3 or messages_count < 20:
        raise ValueError("Для отраслевого правила нужно минимум 20 сообщений из 3 источников")
    proposal_id = str(uuid.uuid4())
    today = datetime.now(timezone.utc).date()
    cursor.execute(
        """
        INSERT INTO industry_pattern_proposals (
            id, industry_key, pattern_type, proposed_pattern, examples_json,
            source_period_start, source_period_end, source_counts_json,
            confidence, risk_level, status, created_at, updated_at
        ) VALUES (
            %s, %s, 'news', %s, %s, %s, %s, %s,
            %s, 'medium', 'pending_review', NOW(), NOW()
        )
        RETURNING id, industry_key, pattern_type, proposed_pattern, status
        """,
        (
            proposal_id,
            industry_key,
            str(concept.get("label") or ""),
            Json({"knowledge_concept_id": str(concept.get("id") or ""), "requested_by": user_id, "business_id": business_id}),
            today - timedelta(days=90),
            today,
            Json({"sources": sources_count, "messages": messages_count}),
            min(100, 50 + sources_count * 5 + int(math.log2(max(messages_count, 1))) * 5),
        ),
    )
    return dict(cursor.fetchone())
