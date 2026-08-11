from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from typing import Any, Callable
from zoneinfo import ZoneInfo

from psycopg2.extras import Json, RealDictCursor

from core.ai_learning import record_ai_learning_event
from database_manager import DatabaseManager
from services.knowledge_embeddings import GigaChatEmbeddingClient, _vector_literal
from services.llm import analyze_text_with_gigachat
from services.outreach_human_language import review_human_language


FOUNDER_CONTENT_TIMEZONE = ZoneInfo("Europe/Moscow")
FOUNDER_CONTENT_PROMPT_KEY = "founder_morning_post"
FOUNDER_CONTENT_PROMPT_VERSION = "v1"
FOUNDER_CONTENT_CAPABILITY = "founder_content.post"


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _row(cursor: Any, value: Any) -> dict[str, Any]:
    if not value:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "keys"):
        return {key: value[key] for key in value.keys()}
    description = getattr(cursor, "description", None) or []
    return {
        str(column[0]): value[index]
        for index, column in enumerate(description)
        if index < len(value)
    }


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    try:
        parsed = json.loads(value) if value else {}
    except Exception:
        return {}
    return dict(parsed) if isinstance(parsed, dict) else {}


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return list(value)
    try:
        parsed = json.loads(value) if value else []
    except Exception:
        return []
    return list(parsed) if isinstance(parsed, list) else []


def queue_founder_content_brief(
    cursor: Any,
    *,
    title: str,
    change_summary: str,
    rationale: str = "",
    created_by: str = "",
    proof: list[dict[str, Any]] | None = None,
    source_refs: list[str] | None = None,
    priority: int = 50,
    deployed_at: datetime | None = None,
) -> dict[str, Any]:
    clean_title = _clean(title)
    clean_summary = _clean(change_summary)
    if len(clean_title) < 5 or len(clean_summary) < 20:
        raise ValueError("FOUNDER_CONTENT_BRIEF_INCOMPLETE")
    brief_id = str(uuid.uuid4())
    content_key = stable_brief_key(clean_title, clean_summary)
    cursor.execute(
        """
        INSERT INTO founder_content_briefs (
            id, content_key, created_by, title, change_summary, rationale,
            proof_json, source_refs_json, priority, status, deployed_at,
            created_at, updated_at
        ) VALUES (
            %s, %s, NULLIF(%s, ''), %s, %s, %s,
            %s, %s, %s, 'queued', %s, NOW(), NOW()
        )
        RETURNING *
        """,
        (
            brief_id,
            content_key,
            created_by,
            clean_title,
            clean_summary,
            _clean(rationale),
            Json(proof or []),
            Json(source_refs or []),
            max(0, min(int(priority), 100)),
            deployed_at,
        ),
    )
    return _row(cursor, cursor.fetchone())


def _load_b2b_evidence(cursor: Any, query: str, *, limit: int = 6) -> list[dict[str, Any]]:
    clean_query = _clean(query)[:2000]
    if not clean_query:
        return []
    rows: list[dict[str, Any]] = []
    try:
        response = GigaChatEmbeddingClient().embed([clean_query])
        vectors = response.get("vectors") if isinstance(response, dict) else []
        vector = vectors[0] if isinstance(vectors, list) and vectors else []
        if vector:
            vector_value = _vector_literal(vector)
            cursor.execute(
                """
                SELECT chunk.content_text, document.id document_id,
                       document.permalink, document.published_at,
                       source.id source_id, source.title source_title,
                       1 - (chunk.embedding <=> %s::halfvec) similarity
                FROM knowledge_embedding_chunks chunk
                JOIN knowledge_document_chunk_links link ON link.chunk_id = chunk.id
                JOIN knowledge_documents document ON document.id = link.document_id
                JOIN knowledge_sources source ON source.id = document.source_id
                WHERE chunk.status = 'ready'
                  AND chunk.stale_at IS NULL
                  AND document.invalidated_at IS NULL
                  AND document.metadata_json->>'corpus_tag' = 'telegram_b2b'
                ORDER BY chunk.embedding <=> %s::halfvec
                LIMIT 80
                """,
                (vector_value, vector_value),
            )
            rows = [_row(cursor, item) for item in cursor.fetchall() or []]
    except Exception:
        try:
            cursor.connection.rollback()
        except Exception:
            pass
    if not rows:
        cursor.execute(
            """
            SELECT document.content_text, document.id document_id,
                   document.permalink, document.published_at,
                   source.id source_id, source.title source_title,
                   ts_rank_cd(
                       to_tsvector('russian', document.content_text),
                       plainto_tsquery('russian', %s)
                   ) similarity
            FROM knowledge_documents document
            JOIN knowledge_sources source ON source.id = document.source_id
            WHERE document.invalidated_at IS NULL
              AND document.metadata_json->>'corpus_tag' = 'telegram_b2b'
              AND to_tsvector('russian', document.content_text)
                  @@ plainto_tsquery('russian', %s)
            ORDER BY similarity DESC, document.published_at DESC NULLS LAST
            LIMIT 80
            """,
            (clean_query, clean_query),
        )
        rows = [_row(cursor, item) for item in cursor.fetchall() or []]
    selected: list[dict[str, Any]] = []
    seen_documents: set[str] = set()
    source_counts: dict[str, int] = {}
    for item in rows:
        document_id = str(item.get("document_id") or "")
        source_id = str(item.get("source_id") or "")
        if not document_id or document_id in seen_documents:
            continue
        if source_counts.get(source_id, 0) >= 2:
            continue
        seen_documents.add(document_id)
        source_counts[source_id] = source_counts.get(source_id, 0) + 1
        selected.append(
            {
                "document_id": document_id,
                "source_id": source_id,
                "source_title": _clean(item.get("source_title")),
                "published_at": item.get("published_at"),
                "permalink": _clean(item.get("permalink")),
                "excerpt": _clean(item.get("content_text"))[:1200],
                "similarity": float(item.get("similarity") or 0),
            }
        )
        if len(selected) >= max(3, min(int(limit), 8)):
            break
    return selected


def _evidence_is_sufficient(items: list[dict[str, Any]]) -> bool:
    documents = {str(item.get("document_id") or "") for item in items}
    sources = {str(item.get("source_id") or "") for item in items}
    return len(documents) >= 3 and len(sources) >= 2


def _feedback_pairs(cursor: Any, user_id: str, *, limit: int = 5) -> list[dict[str, str]]:
    cursor.execute(
        """
        SELECT draft_text, final_text
        FROM ailearningevents
        WHERE user_id = %s
          AND capability = %s
          AND event_type IN ('minor_edit', 'major_rewrite')
          AND NULLIF(BTRIM(COALESCE(draft_text, '')), '') IS NOT NULL
          AND NULLIF(BTRIM(COALESCE(final_text, '')), '') IS NOT NULL
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (user_id, FOUNDER_CONTENT_CAPABILITY, max(1, min(int(limit), 8))),
    )
    return [
        {
            "draft": str(item.get("draft_text") if isinstance(item, dict) else item[0] or "")[:2200],
            "final": str(item.get("final_text") if isinstance(item, dict) else item[1] or "")[:2200],
        }
        for item in cursor.fetchall() or []
    ]


def _build_prompt(
    brief: dict[str, Any],
    evidence: list[dict[str, Any]],
    feedback_pairs: list[dict[str, str]],
    *,
    retry_reasons: list[str] | None = None,
) -> str:
    evidence_blocks = []
    for index, item in enumerate(evidence, start=1):
        evidence_blocks.append(
            f"[{index}] Канал: {item.get('source_title')}\n"
            f"Дата: {item.get('published_at')}\n"
            f"Идея: {item.get('excerpt')}"
        )
    feedback_blocks = []
    for index, item in enumerate(feedback_pairs, start=1):
        feedback_blocks.append(
            f"Редакторская правка {index}.\n"
            f"Черновик:\n{item.get('draft')}\n"
            f"Версия автора:\n{item.get('final')}"
        )
    retry_block = ""
    if retry_reasons:
        retry_block = "\nПредыдущая версия не прошла проверку: " + ", ".join(retry_reasons) + ". Исправь эти проблемы."
    return "\n".join(
        [
            "Ты редактор авторского Telegram-канала основателя LocalOS.",
            "Напиши один пост на русском языке о реально внедрённом изменении продукта.",
            "Не имитируй конкретных авторов и не копируй формулировки из источников.",
            "Факты о LocalOS бери только из продуктового брифа и его подтверждений.",
            "Публикации B2B-каналов дают только теоретический принцип, но не факты о LocalOS.",
            "Одна главная мысль. Живой человеческий язык. Короткие абзацы.",
            "Длина 700-1600 знаков. Без хэштегов. Не больше одного эмодзи.",
            "Не добавляй продажный призыв. Можно завершить ясным выводом или честным вопросом.",
            "Не используй слова о полностью автономной публикации или отправке.",
            "Верни строго JSON: {\"post\": \"текст\"}.",
            retry_block,
            "",
            "Продуктовый бриф:",
            f"Название: {_clean(brief.get('title'))}",
            f"Что изменили: {_clean(brief.get('change_summary'))}",
            f"Зачем: {_clean(brief.get('rationale'))}",
            f"Подтверждения: {json.dumps(_json_list(brief.get('proof_json')), ensure_ascii=False)}",
            "",
            "Теоретические источники:",
            "\n\n".join(evidence_blocks),
            "",
            "Предыдущие правки автора. Учитывай направление изменений, но не переноси факты между постами:",
            "\n\n".join(feedback_blocks) if feedback_blocks else "Пока правок нет.",
        ]
    )


def _parse_generated_post(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    parsed: Any = None
    try:
        parsed = json.loads(raw)
    except Exception:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                parsed = json.loads(raw[start:end])
            except Exception:
                parsed = None
    if isinstance(parsed, dict):
        return str(parsed.get("post") or "").strip()
    return raw


def _default_generator(prompt: str, *, user_id: str, pipeline_id: str) -> str:
    return analyze_text_with_gigachat(
        prompt,
        task_type="social_post_generation",
        user_id=user_id,
        usage_reference=pipeline_id,
        pipeline_id=pipeline_id,
        pipeline_stage="founder_content_copy",
    )


def _long_source_overlap(text: str, evidence: list[dict[str, Any]], *, words: int = 10) -> bool:
    normalized_words = re.findall(r"[а-яёa-z0-9]+", text.lower())
    if len(normalized_words) < words:
        return False
    shingles = {
        " ".join(normalized_words[index:index + words])
        for index in range(0, len(normalized_words) - words + 1)
    }
    for item in evidence:
        source_words = re.findall(r"[а-яёa-z0-9]+", str(item.get("excerpt") or "").lower())
        source_text = " ".join(source_words)
        if any(shingle in source_text for shingle in shingles):
            return True
    return False


def review_founder_post(text: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
    language = review_human_language(text, require_signal_flow=False)
    reason_codes = list(language.get("reason_codes") or [])
    if len(text) < 500:
        reason_codes.append("POST_TOO_SHORT")
    if len(text) > 2200:
        reason_codes.append("POST_TOO_LONG")
    if _long_source_overlap(text, evidence):
        reason_codes.append("SOURCE_WORDING_OVERLAP")
    if re.search(r"#[\wа-яё]+", text, flags=re.IGNORECASE):
        reason_codes.append("HASHTAGS_NOT_ALLOWED")
    result = {
        "passed": not reason_codes,
        "verdict": "approve" if not reason_codes else "revise",
        "reason_codes": list(dict.fromkeys(reason_codes)),
        "human_language": language,
        "manual_publication_only": True,
    }
    return result


def _local_now(value: datetime | None = None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(FOUNDER_CONTENT_TIMEZONE)


def founder_content_window_is_due(value: datetime | None = None) -> bool:
    current = _local_now(value)
    hour = max(0, min(int(os.getenv("FOUNDER_CONTENT_MORNING_HOUR", "9")), 23))
    minute = max(0, min(int(os.getenv("FOUNDER_CONTENT_MORNING_MINUTE", "30")), 59))
    due_minute = hour * 60 + minute
    current_minute = current.hour * 60 + current.minute
    return due_minute <= current_minute <= due_minute + 90


def _eligible_superadmins(cursor: Any) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT id, BTRIM(CAST(telegram_id AS TEXT)) telegram_id
        FROM users
        WHERE is_superadmin IS TRUE
          AND COALESCE(is_active, TRUE) IS TRUE
          AND NULLIF(BTRIM(CAST(telegram_id AS TEXT)), '') IS NOT NULL
        ORDER BY created_at
        """
    )
    return [_row(cursor, item) for item in cursor.fetchall() or []]


def _cooldown_ready(cursor: Any, user_id: str, now_local: datetime) -> bool:
    cooldown_hours = max(12, min(int(os.getenv("FOUNDER_CONTENT_COOLDOWN_HOURS", "36")), 168))
    cursor.execute(
        """
        SELECT MAX(COALESCE(delivered_at, created_at)) last_at
        FROM founder_content_drafts
        WHERE user_id = %s
          AND status IN ('delivered', 'corrected', 'skipped')
        """,
        (user_id,),
    )
    value = _row(cursor, cursor.fetchone()).get("last_at")
    if not value:
        return True
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value <= now_local.astimezone(timezone.utc) - timedelta(hours=cooldown_hours)


def prepare_due_founder_content_drafts(
    conn: Any,
    *,
    now: datetime | None = None,
    generator: Callable[..., str] | None = None,
) -> list[dict[str, Any]]:
    if not founder_content_window_is_due(now):
        return []
    now_local = _local_now(now)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    created: list[dict[str, Any]] = []
    try:
        for user in _eligible_superadmins(cursor):
            user_id = str(user.get("id") or "")
            telegram_id = str(user.get("telegram_id") or "")
            if not user_id or not telegram_id or not _cooldown_ready(cursor, user_id, now_local):
                continue
            cursor.execute(
                """
                SELECT draft.*, brief.title brief_title
                FROM founder_content_drafts draft
                JOIN founder_content_briefs brief ON brief.id = draft.brief_id
                WHERE draft.user_id = %s AND draft.scheduled_for = %s
                LIMIT 1
                """,
                (user_id, now_local.date()),
            )
            existing_draft = _row(cursor, cursor.fetchone())
            if existing_draft:
                if str(existing_draft.get("status") or "") == "draft":
                    created.append(existing_draft)
                continue
            cursor.execute(
                """
                SELECT *
                FROM founder_content_briefs
                WHERE status = 'queued'
                  AND (deployed_at IS NULL OR deployed_at <= NOW())
                ORDER BY priority DESC, deployed_at DESC NULLS LAST, created_at
                LIMIT 1
                FOR UPDATE SKIP LOCKED
                """
            )
            brief = _row(cursor, cursor.fetchone())
            if not brief:
                continue
            query = " ".join(
                [
                    _clean(brief.get("title")),
                    _clean(brief.get("change_summary")),
                    _clean(brief.get("rationale")),
                ]
            )
            evidence = _load_b2b_evidence(cursor, query)
            if not _evidence_is_sufficient(evidence):
                continue
            feedback = _feedback_pairs(cursor, user_id)
            draft_id = str(uuid.uuid4())
            prompt = _build_prompt(brief, evidence, feedback)
            generate = generator or _default_generator
            generated = _parse_generated_post(generate(prompt, user_id=user_id, pipeline_id=draft_id))
            quality = review_founder_post(generated, evidence)
            if not quality.get("passed"):
                prompt = _build_prompt(
                    brief,
                    evidence,
                    feedback,
                    retry_reasons=list(quality.get("reason_codes") or []),
                )
                generated = _parse_generated_post(generate(prompt, user_id=user_id, pipeline_id=draft_id))
                quality = review_founder_post(generated, evidence)
            status = "draft" if quality.get("passed") else "needs_review"
            provenance = {
                "corpus_tag": "telegram_b2b",
                "knowledge_document_ids": [item["document_id"] for item in evidence],
                "knowledge_source_ids": list(dict.fromkeys(item["source_id"] for item in evidence)),
                "source_links": [item["permalink"] for item in evidence if item.get("permalink")],
                "feedback_examples_used": len(feedback),
                "prompt_key": FOUNDER_CONTENT_PROMPT_KEY,
                "prompt_version": FOUNDER_CONTENT_PROMPT_VERSION,
            }
            cursor.execute(
                """
                INSERT INTO founder_content_drafts (
                    id, brief_id, user_id, telegram_id, scheduled_for, status,
                    generated_text, quality_json, provenance_json, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                RETURNING *
                """,
                (
                    draft_id,
                    brief.get("id"),
                    user_id,
                    telegram_id,
                    now_local.date(),
                    status,
                    generated,
                    Json(quality),
                    Json(provenance),
                ),
            )
            draft = _row(cursor, cursor.fetchone())
            cursor.execute(
                "UPDATE founder_content_briefs SET status = 'used', updated_at = NOW() WHERE id = %s",
                (brief.get("id"),),
            )
            draft["brief_title"] = _clean(brief.get("title"))
            created.append(draft)
        return created
    finally:
        cursor.close()


def format_founder_content_telegram_message(draft: dict[str, Any]) -> str:
    title = _clean(draft.get("brief_title")) or "обновление LocalOS"
    text = str(draft.get("generated_text") or "").strip()
    review_note = ""
    if str(draft.get("status") or "") == "needs_review":
        review_note = (
            "⚠️ Этот вариант не прошёл внутреннюю проверку естественности. "
            "Отправляю его только как материал для вашей редакции.\n\n"
        )
    return (
        f"✍️ Черновик LocalOS на сегодня\n"
        f"Тема: {title}\n\n"
        f"{review_note}"
        f"{text}\n\n"
        "Ответьте на это сообщение своей исправленной версией. "
        "LocalOS сохранит разницу и учтёт её в следующих черновиках.\n"
        "Публикации автоматически не происходит."
    )


def mark_founder_content_delivered(
    conn: Any,
    *,
    draft_id: str,
    telegram_message_id: int,
) -> bool:
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE founder_content_drafts
            SET status = 'delivered', telegram_message_id = %s,
                delivered_at = NOW(), updated_at = NOW()
            WHERE id = %s AND status IN ('draft', 'needs_review')
            """,
            (telegram_message_id, draft_id),
        )
        return int(getattr(cursor, "rowcount", 0) or 0) > 0
    finally:
        cursor.close()


def build_editorial_diff(draft_text: str, final_text: str) -> dict[str, Any]:
    draft_tokens = re.findall(r"\S+", str(draft_text or ""))
    final_tokens = re.findall(r"\S+", str(final_text or ""))
    matcher = SequenceMatcher(None, draft_tokens, final_tokens, autojunk=False)
    changes: list[dict[str, Any]] = []
    removed: list[str] = []
    added: list[str] = []
    for operation, draft_start, draft_end, final_start, final_end in matcher.get_opcodes():
        if operation == "equal":
            continue
        before = " ".join(draft_tokens[draft_start:draft_end])
        after = " ".join(final_tokens[final_start:final_end])
        changes.append({"operation": operation, "before": before[:600], "after": after[:600]})
        if before:
            removed.append(before[:240])
        if after:
            added.append(after[:240])
    edit_ratio = max(0.0, min(1.0, 1.0 - matcher.ratio()))
    draft_value = str(draft_text or "")
    final_value = str(final_text or "")
    return {
        "edit_ratio": round(edit_ratio, 5),
        "changes": changes[:80],
        "removed_fragments": removed[:20],
        "added_fragments": added[:20],
        "draft_chars": len(draft_value),
        "final_chars": len(final_value),
        "length_ratio": round(len(final_value) / max(1, len(draft_value)), 3),
        "draft_paragraphs": len([item for item in draft_value.split("\n\n") if item.strip()]),
        "final_paragraphs": len([item for item in final_value.split("\n\n") if item.strip()]),
        "draft_questions": draft_value.count("?"),
        "final_questions": final_value.count("?"),
        "draft_exclamations": draft_value.count("!"),
        "final_exclamations": final_value.count("!"),
    }


def _feedback_summary(diff: dict[str, Any]) -> str:
    observations = []
    length_ratio = float(diff.get("length_ratio") or 1)
    if length_ratio <= 0.8:
        observations.append("вы сделали текст заметно короче")
    elif length_ratio >= 1.2:
        observations.append("вы расширили объяснение")
    if int(diff.get("final_paragraphs") or 0) > int(diff.get("draft_paragraphs") or 0):
        observations.append("добавили больше коротких абзацев")
    if int(diff.get("final_questions") or 0) < int(diff.get("draft_questions") or 0):
        observations.append("убрали часть вопросов")
    if int(diff.get("final_exclamations") or 0) < int(diff.get("draft_exclamations") or 0):
        observations.append("сделали тон спокойнее")
    return "; ".join(observations[:3]) or "зафиксировал формулировки и структуру"


def capture_founder_content_correction(
    conn: Any,
    *,
    telegram_id: str,
    reply_to_message_id: int,
    corrected_text: str,
) -> dict[str, Any]:
    final_text = str(corrected_text or "").strip()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            SELECT draft.*, brief.title brief_title
            FROM founder_content_drafts draft
            JOIN founder_content_briefs brief ON brief.id = draft.brief_id
            WHERE draft.telegram_id = %s
              AND draft.telegram_message_id = %s
              AND draft.status = 'delivered'
            LIMIT 1
            FOR UPDATE OF draft
            """,
            (str(telegram_id or "").strip(), int(reply_to_message_id)),
        )
        draft = _row(cursor, cursor.fetchone())
        if not draft:
            return {"captured": False, "matched": False, "reason_code": "FOUNDER_DRAFT_NOT_FOUND"}
        if len(final_text) < 100:
            return {"captured": False, "matched": True, "reason_code": "CORRECTION_TOO_SHORT"}
        original_text = str(draft.get("generated_text") or "")
        diff = build_editorial_diff(original_text, final_text)
        cursor.execute(
            """
            UPDATE founder_content_drafts
            SET status = 'corrected', corrected_text = %s,
                diff_json = %s, edit_ratio = %s,
                corrected_at = NOW(), updated_at = NOW()
            WHERE id = %s
            """,
            (final_text, Json(diff), diff["edit_ratio"], draft.get("id")),
        )
        cursor.execute(
            """
            SELECT 1
            FROM userexamples
            WHERE user_id = %s
              AND example_type = 'news'
              AND metadata_json->>'founder_content_draft_id' = %s
            LIMIT 1
            """,
            (draft.get("user_id"), str(draft.get("id"))),
        )
        if not cursor.fetchone():
            cursor.execute(
                """
                INSERT INTO userexamples (
                    id, user_id, business_id, example_type, example_text,
                    platform, origin, quality_status, metadata_json, created_at
                ) VALUES (%s, %s, NULL, 'news', %s, 'telegram', 'approved_edit',
                          'reference', %s, NOW())
                """,
                (
                    str(uuid.uuid4()),
                    draft.get("user_id"),
                    final_text,
                    Json(
                        {
                            "founder_content_draft_id": str(draft.get("id")),
                            "brief_id": str(draft.get("brief_id")),
                            "edit_ratio": diff["edit_ratio"],
                        }
                    ),
                ),
            )
        event_type = "major_rewrite" if float(diff["edit_ratio"]) >= 0.35 else "minor_edit"
        record_ai_learning_event(
            capability=FOUNDER_CONTENT_CAPABILITY,
            event_type=event_type,
            intent="founder_content",
            user_id=str(draft.get("user_id") or ""),
            accepted=True,
            rejected=False,
            edited_before_accept=True,
            outcome="editorial_correction",
            prompt_key=FOUNDER_CONTENT_PROMPT_KEY,
            prompt_version=FOUNDER_CONTENT_PROMPT_VERSION,
            draft_text=original_text,
            final_text=final_text,
            metadata={
                "founder_content_draft_id": str(draft.get("id")),
                "brief_id": str(draft.get("brief_id")),
                "telegram_message_id": int(reply_to_message_id),
                "diff": diff,
            },
            conn=conn,
        )
        return {
            "captured": True,
            "matched": True,
            "draft_id": str(draft.get("id")),
            "brief_title": _clean(draft.get("brief_title")),
            "edit_ratio": diff["edit_ratio"],
            "diff": diff,
            "feedback_summary": _feedback_summary(diff),
            "manual_publication_only": True,
        }
    finally:
        cursor.close()


def capture_founder_content_correction_from_telegram(
    *,
    telegram_id: str,
    reply_to_message_id: int,
    corrected_text: str,
) -> dict[str, Any]:
    database = DatabaseManager()
    try:
        result = capture_founder_content_correction(
            database.conn,
            telegram_id=telegram_id,
            reply_to_message_id=reply_to_message_id,
            corrected_text=corrected_text,
        )
        if result.get("captured"):
            database.conn.commit()
        else:
            database.conn.rollback()
        return result
    except Exception:
        database.conn.rollback()
        raise
    finally:
        database.close()


def stable_brief_key(title: str, change_summary: str) -> str:
    return hashlib.sha256(f"{_clean(title)}\n{_clean(change_summary)}".encode("utf-8")).hexdigest()
