#!/usr/bin/env python3

from __future__ import annotations

import json
import re
from typing import Any

from psycopg2.extras import RealDictCursor

from database_manager import DatabaseManager
from services.knowledge_embeddings import GigaChatEmbeddingClient, _vector_literal


THEMES = {
    "icp_segmentation": r"\m(icp|ицп)\M|идеальн.{0,24}клиент|целев.{0,24}аудитор|сегмент",
    "personalization_signals": r"персонализац|персонализ|кастомизац|релевантн.{0,30}(сообщ|письм)|триггер",
    "offer_value": r"оффер|ценностн.{0,24}предлож|\mутп\M|value proposition",
    "followup_sequence": r"follow.?up|фол+оу|повторн.{0,24}(касан|письм|сообщ)|цепочк|дожим",
    "deliverability": r"доставляемост|прогрев.{0,24}(домен|почт)|\mspf\M|\mdkim\M|спам",
    "social_proof": r"кейс|социальн.{0,24}доказ|отзыв|результат.{0,24}клиент",
    "discovery_pain": r"кастдев|discovery|диагностик|боль клиент|проблем.{0,30}клиент",
    "multichannel": r"мультикан|омникан|linkedin|email.{0,40}telegram|телеграм.{0,40}email",
    "automation_ai": r"автоматизац|нейросет|искусственн.{0,24}интеллект|\mai\M|ии-",
    "metrics_roi": r"конверси|reply rate|\mroi\M|окупаем|\mcac\M|\mltv\M",
}

SEMANTIC_QUERIES = {
    "reply_drivers": "Какие свойства первого холодного B2B сообщения повышают вероятность содержательного ответа?",
    "failure_modes": "Почему B2B аутрич не получает ответы и какие ошибки повторяются чаще всего?",
    "personalization": "Как персонализировать B2B аутрич по реальным сигналам компании без декоративных комплиментов?",
    "sequence": "Как строить последовательность касаний и follow-up в B2B продажах?",
    "automation": "Что в B2B аутриче можно автоматизировать, а что должно оставаться ручным и человеческим?",
    "content_bridge": "Как использовать экспертный контент и личный бренд для начала B2B диалога?",
}


def _compact(value: Any, size: int = 700) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:size]


def _overview(cursor: Any) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT COUNT(*) AS documents,
               COUNT(DISTINCT source.id) AS sources,
               MIN(document.published_at) AS first_published_at,
               MAX(document.published_at) AS last_published_at
        FROM knowledge_documents document
        JOIN knowledge_sources source ON source.id = document.source_id
        WHERE document.metadata_json->>'corpus_tag' = 'telegram_b2b'
          AND document.invalidated_at IS NULL
        """
    )
    return dict(cursor.fetchone())


def _theme_counts(cursor: Any) -> list[dict[str, Any]]:
    result = []
    for key, pattern in THEMES.items():
        cursor.execute(
            """
            SELECT COUNT(*) AS messages, COUNT(DISTINCT source_id) AS sources
            FROM knowledge_documents
            WHERE metadata_json->>'corpus_tag' = 'telegram_b2b'
              AND invalidated_at IS NULL
              AND content_text ~* %s
            """,
            (pattern,),
        )
        result.append({"theme": key, **dict(cursor.fetchone())})
    return result


def _semantic_hits(cursor: Any, query: str) -> list[dict[str, Any]]:
    response = GigaChatEmbeddingClient().embed([query])
    vector = (response.get("vectors") or [])[0]
    cursor.execute(
        """
        SELECT chunk.id AS chunk_id, chunk.content_text,
               document.permalink, document.published_at,
               source.title AS source_title,
               1 - (chunk.embedding <=> %s::halfvec) AS similarity
        FROM knowledge_embedding_chunks chunk
        JOIN knowledge_document_chunk_links link ON link.chunk_id = chunk.id
        JOIN knowledge_documents document ON document.id = link.document_id
        JOIN knowledge_sources source ON source.id = document.source_id
        WHERE chunk.status = 'ready' AND chunk.stale_at IS NULL
          AND document.invalidated_at IS NULL
          AND document.metadata_json->>'corpus_tag' = 'telegram_b2b'
        ORDER BY chunk.embedding <=> %s::halfvec
        LIMIT 60
        """,
        (_vector_literal(vector), _vector_literal(vector)),
    )
    selected = []
    source_counts: dict[str, int] = {}
    for row in cursor.fetchall():
        source = str(row["source_title"])
        if source_counts.get(source, 0) >= 1:
            continue
        source_counts[source] = source_counts.get(source, 0) + 1
        selected.append({
            "source": source,
            "published_at": row.get("published_at"),
            "permalink": row.get("permalink"),
            "similarity": round(float(row.get("similarity") or 0), 4),
            "excerpt": _compact(row.get("content_text")),
        })
        if len(selected) >= 5:
            break
    return selected


def main() -> None:
    database = DatabaseManager()
    cursor = database.conn.cursor(cursor_factory=RealDictCursor)
    try:
        semantic = {
            key: _semantic_hits(cursor, query)
            for key, query in SEMANTIC_QUERIES.items()
        }
        print(json.dumps({
            "overview": _overview(cursor),
            "theme_counts": _theme_counts(cursor),
            "semantic": semantic,
        }, ensure_ascii=False, default=str, indent=2))
    finally:
        cursor.close()
        database.close()


if __name__ == "__main__":
    main()
