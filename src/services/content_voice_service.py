from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from database_manager import DatabaseManager
from core.helpers import get_business_owner_id


CONTENT_EXAMPLE_LIMIT = 50
CONTENT_EXAMPLE_PLATFORMS = {"", "yandex_maps", "two_gis", "google_business", "telegram", "vk", "instagram", "facebook"}
CONTENT_EXAMPLE_ORIGINS = {"manual", "published", "approved_edit", "import"}
CONTENT_EXAMPLE_QUALITY = {"reference", "regular", "avoid"}


def _row_to_dict(cursor: Any, row: Any) -> dict[str, Any]:
    if not row:
        return {}
    if isinstance(row, dict):
        return dict(row)
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    description = getattr(cursor, "description", None) or []
    return {
        str(column[0]): row[index]
        for index, column in enumerate(description)
        if index < len(row)
    }


def _json_value(value: Any, fallback: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value) if value else fallback
    except Exception:
        return fallback


def _verify_access(cursor: Any, user_id: str, business_id: str) -> None:
    owner_id = get_business_owner_id(cursor, business_id)
    if str(owner_id or "") == str(user_id or ""):
        return
    cursor.execute("SELECT COALESCE(is_superadmin, FALSE) FROM users WHERE id = %s", (user_id,))
    row = cursor.fetchone()
    if row and bool(row[0] if isinstance(row, (tuple, list)) else row.get("coalesce")):
        return
    cursor.execute(
        "SELECT 1 FROM business_members WHERE business_id = %s AND user_id = %s AND status = 'active' AND role IN ('manager', 'member') LIMIT 1",
        (business_id, user_id),
    )
    if cursor.fetchone():
        return
    raise PermissionError("Нет доступа к стилю публикаций этого бизнеса")


def _serialize_example(cursor: Any, row: Any) -> dict[str, Any]:
    item = _row_to_dict(cursor, row)
    created_at = item.get("created_at")
    return {
        "id": str(item.get("id") or ""),
        "business_id": str(item.get("business_id") or ""),
        "text": str(item.get("example_text") or ""),
        "platform": str(item.get("platform") or ""),
        "origin": str(item.get("origin") or "manual"),
        "quality_status": str(item.get("quality_status") or "reference"),
        "metadata": _json_value(item.get("metadata_json"), {}),
        "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at or ""),
    }


def _derive_profile(examples: list[dict[str, Any]]) -> dict[str, Any]:
    texts = [str(item.get("text") or "").strip() for item in examples if str(item.get("text") or "").strip()]
    if not texts:
        return {"summary": "", "preferences": {}, "forbidden_phrases": [], "typical_ctas": []}
    average_length = round(sum(len(text) for text in texts) / len(texts))
    question_share = sum("?" in text for text in texts) / len(texts)
    exclamation_share = sum("!" in text for text in texts) / len(texts)
    paragraph_share = sum("\n" in text for text in texts) / len(texts)
    length_label = "короткие" if average_length < 350 else "развёрнутые" if average_length > 750 else "средние по длине"
    tone_parts = [length_label, "конкретные публикации"]
    if paragraph_share >= 0.5:
        tone_parts.append("с короткими абзацами")
    if question_share < 0.25:
        tone_parts.append("без частых вопросов в начале")
    if exclamation_share < 0.35:
        tone_parts.append("со спокойной эмоциональностью")
    ctas: list[str] = []
    for text in texts:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        for sentence in sentences[-2:]:
            lower = sentence.lower()
            if any(marker in lower for marker in ("подробност", "запис", "смотрите", "приход", "афиш")):
                clean = sentence.strip()[:180]
                if clean and clean not in ctas:
                    ctas.append(clean)
    return {
        "summary": ", ".join(tone_parts).capitalize() + ".",
        "preferences": {
            "average_length": average_length,
            "uses_paragraphs": paragraph_share >= 0.5,
            "uses_opening_questions": question_share >= 0.5,
            "emotionality": "expressive" if exclamation_share >= 0.5 else "calm",
        },
        "forbidden_phrases": [],
        "typical_ctas": ctas[:5],
    }


def _learning_suggestion(cursor: Any, business_id: str) -> dict[str, Any] | None:
    cursor.execute("SELECT to_regclass('public.ailearningevents')")
    table_row = cursor.fetchone()
    table_ref = table_row[0] if isinstance(table_row, (tuple, list)) else _row_to_dict(cursor, table_row).get("to_regclass")
    if not table_ref:
        return None
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM ailearningevents
        WHERE business_id = NULLIF(%s, '')::uuid
          AND capability IN ('content_plan.item', 'content_plan.publish')
          AND event_type IN ('major_rewrite', 'minor_edit')
          AND created_at >= NOW() - INTERVAL '90 days'
        """,
        (business_id,),
    )
    row = cursor.fetchone()
    count = int((row[0] if isinstance(row, (tuple, list)) else _row_to_dict(cursor, row).get("count")) or 0) if row else 0
    if count < 3:
        return None
    cursor.execute(
        """
        SELECT draft_text, final_text
        FROM ailearningevents
        WHERE business_id = NULLIF(%s, '')::uuid
          AND capability IN ('content_plan.item', 'content_plan.publish')
          AND event_type IN ('major_rewrite', 'minor_edit')
          AND NULLIF(BTRIM(COALESCE(draft_text, '')), '') IS NOT NULL
          AND NULLIF(BTRIM(COALESCE(final_text, '')), '') IS NOT NULL
        ORDER BY created_at DESC
        LIMIT 5
        """,
        (business_id,),
    )
    edits = [_row_to_dict(cursor, item) for item in cursor.fetchall() or []]
    shorter_count = sum(len(str(item.get("final_text") or "")) < len(str(item.get("draft_text") or "")) * 0.8 for item in edits)
    removed_question_count = sum(
        "?" in str(item.get("draft_text") or "")[:160] and "?" not in str(item.get("final_text") or "")[:160]
        for item in edits
    )
    proposed_rule = "Писать конкретнее и ближе к подтверждённому инфоповоду."
    if shorter_count >= 3:
        proposed_rule = "Делать публикации короче и быстрее переходить к главной мысли."
    elif removed_question_count >= 3:
        proposed_rule = "Начинать публикацию сразу с факта, без рекламного вопроса."
    return {
        "key": "review_recent_edits",
        "text": f"Вы несколько раз редактировали публикации. Предлагаем правило: «{proposed_rule}» LocalOS ничего не изменит без подтверждения.",
        "proposed_rule": proposed_rule,
        "edits_count": count,
    }


def get_content_voice(user_id: str, business_id: str) -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        _verify_access(cursor, user_id, business_id)
        cursor.execute(
            """
            SELECT id, business_id, example_text, platform, origin, quality_status, metadata_json, created_at
            FROM userexamples
            WHERE user_id = %s AND example_type = 'news' AND (business_id = %s OR business_id IS NULL)
            ORDER BY (business_id = %s) DESC, (quality_status = 'reference') DESC, created_at DESC
            LIMIT %s
            """,
            (user_id, business_id, business_id, CONTENT_EXAMPLE_LIMIT),
        )
        examples = [_serialize_example(cursor, row) for row in cursor.fetchall() or []]
        cursor.execute("SELECT * FROM content_voice_profiles WHERE business_id = %s", (business_id,))
        profile = _row_to_dict(cursor, cursor.fetchone())
        derived = _derive_profile([item for item in examples if item.get("quality_status") != "avoid"])
        payload = {
            "business_id": business_id,
            "summary": str(profile.get("summary") or derived["summary"]),
            "preferences": _json_value(profile.get("preferences_json"), derived["preferences"]),
            "forbidden_phrases": _json_value(profile.get("forbidden_phrases_json"), derived["forbidden_phrases"]),
            "typical_ctas": _json_value(profile.get("typical_ctas_json"), derived["typical_ctas"]),
            "reference_example_ids": _json_value(profile.get("reference_example_ids_json"), []),
            "status": str(profile.get("status") or "draft"),
            "version": int(profile.get("version") or 1),
            "examples": examples,
            "learning_suggestion": _learning_suggestion(cursor, business_id),
        }
        return payload
    finally:
        db.close()


def add_content_voice_example(
    user_id: str,
    business_id: str,
    text: str,
    *,
    platform: str = "",
    origin: str = "manual",
    quality_status: str = "reference",
) -> dict[str, Any]:
    clean_text = str(text or "").strip()
    clean_platform = str(platform or "").strip()
    clean_origin = str(origin or "manual").strip()
    clean_quality = str(quality_status or "reference").strip()
    if len(clean_text) < 20:
        raise ValueError("Добавьте полный пример публикации")
    if len(clean_text) > 12000:
        raise ValueError("Пример слишком длинный")
    if clean_platform not in CONTENT_EXAMPLE_PLATFORMS:
        raise ValueError("Неизвестная площадка")
    if clean_origin not in CONTENT_EXAMPLE_ORIGINS:
        raise ValueError("Неизвестное происхождение примера")
    if clean_quality not in CONTENT_EXAMPLE_QUALITY:
        raise ValueError("Неизвестная оценка примера")
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        _verify_access(cursor, user_id, business_id)
        cursor.execute(
            "SELECT COUNT(*) FROM userexamples WHERE user_id = %s AND example_type = 'news' AND business_id = %s",
            (user_id, business_id),
        )
        row = cursor.fetchone()
        count = int(row[0] if isinstance(row, (tuple, list)) else _row_to_dict(cursor, row).get("count") or 0)
        if count >= CONTENT_EXAMPLE_LIMIT:
            raise ValueError("Для одного бизнеса можно сохранить до 50 примеров")
        example_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO userexamples (id, user_id, business_id, example_type, example_text, platform, origin, quality_status, metadata_json, created_at)
            VALUES (%s, %s, %s, 'news', %s, NULLIF(%s, ''), %s, %s, '{}'::jsonb, NOW())
            RETURNING id, business_id, example_text, platform, origin, quality_status, metadata_json, created_at
            """,
            (example_id, user_id, business_id, clean_text, clean_platform, clean_origin, clean_quality),
        )
        created = _serialize_example(cursor, cursor.fetchone())
        db.conn.commit()
        return created
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


def delete_content_voice_example(user_id: str, example_id: str) -> None:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        cursor.execute("SELECT business_id FROM userexamples WHERE id = %s AND user_id = %s AND example_type = 'news'", (example_id, user_id))
        row = cursor.fetchone()
        if not row:
            raise ValueError("Пример не найден")
        business_id = str(row[0] if isinstance(row, (tuple, list)) else _row_to_dict(cursor, row).get("business_id") or "")
        if business_id:
            _verify_access(cursor, user_id, business_id)
        cursor.execute("DELETE FROM userexamples WHERE id = %s AND user_id = %s AND example_type = 'news'", (example_id, user_id))
        db.conn.commit()
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


def update_content_voice(user_id: str, business_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    current = get_content_voice(user_id, business_id)
    summary = str(payload.get("summary") if "summary" in payload else current.get("summary") or "").strip()[:600]
    preferences = payload.get("preferences") if isinstance(payload.get("preferences"), dict) else current.get("preferences") or {}
    forbidden = payload.get("forbidden_phrases") if isinstance(payload.get("forbidden_phrases"), list) else current.get("forbidden_phrases") or []
    ctas = payload.get("typical_ctas") if isinstance(payload.get("typical_ctas"), list) else current.get("typical_ctas") or []
    reference_ids = payload.get("reference_example_ids") if isinstance(payload.get("reference_example_ids"), list) else current.get("reference_example_ids") or []
    status = "confirmed" if payload.get("confirm") is True or current.get("status") == "confirmed" else "draft"
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        _verify_access(cursor, user_id, business_id)
        cursor.execute(
            """
            INSERT INTO content_voice_profiles (
                business_id, summary, preferences_json, forbidden_phrases_json, typical_ctas_json,
                reference_example_ids_json, status, version, created_by, confirmed_by, confirmed_at, created_at, updated_at
            ) VALUES (%s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s, 1, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (business_id) DO UPDATE SET
                summary = EXCLUDED.summary,
                preferences_json = EXCLUDED.preferences_json,
                forbidden_phrases_json = EXCLUDED.forbidden_phrases_json,
                typical_ctas_json = EXCLUDED.typical_ctas_json,
                reference_example_ids_json = EXCLUDED.reference_example_ids_json,
                status = EXCLUDED.status,
                version = content_voice_profiles.version + 1,
                confirmed_by = EXCLUDED.confirmed_by,
                confirmed_at = EXCLUDED.confirmed_at,
                updated_at = NOW()
            """,
            (
                business_id,
                summary,
                json.dumps(preferences, ensure_ascii=False),
                json.dumps([str(item)[:160] for item in forbidden[:30]], ensure_ascii=False),
                json.dumps([str(item)[:240] for item in ctas[:10]], ensure_ascii=False),
                json.dumps([str(item) for item in reference_ids[:20]], ensure_ascii=False),
                status,
                user_id,
                user_id if status == "confirmed" else None,
                datetime.now(timezone.utc) if status == "confirmed" else None,
            ),
        )
        db.conn.commit()
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()
    return get_content_voice(user_id, business_id)


def load_content_voice_context(cursor: Any, *, user_id: str, business_id: str, limit: int = 5) -> dict[str, Any]:
    cursor.execute("SELECT * FROM content_voice_profiles WHERE business_id = %s", (business_id,))
    profile = _row_to_dict(cursor, cursor.fetchone())
    cursor.execute(
        """
        SELECT id, business_id, example_text, platform, origin, quality_status, metadata_json, created_at
        FROM userexamples
        WHERE user_id = %s AND example_type = 'news' AND quality_status != 'avoid'
          AND (business_id = %s OR business_id IS NULL)
        ORDER BY (business_id = %s) DESC, (quality_status = 'reference') DESC, created_at DESC
        LIMIT %s
        """,
        (user_id, business_id, business_id, max(1, min(limit, 5))),
    )
    examples = [_serialize_example(cursor, row) for row in cursor.fetchall() or []]
    remaining = max(0, min(limit, 5) - len(examples))
    if remaining:
        cursor.execute(
            """
            SELECT id, business_id, generated_text AS example_text, NULL AS platform,
                   'approved_edit' AS origin, 'reference' AS quality_status,
                   '{}'::jsonb AS metadata_json, created_at
            FROM usernews
            WHERE user_id = %s AND business_id = %s AND approved = 1
              AND NULLIF(BTRIM(COALESCE(generated_text, '')), '') IS NOT NULL
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (user_id, business_id, remaining),
        )
        examples.extend(_serialize_example(cursor, row) for row in cursor.fetchall() or [])
    remaining = max(0, min(limit, 5) - len(examples))
    if remaining:
        cursor.execute(
            """
            SELECT id, business_id, COALESCE(NULLIF(platform_text, ''), base_text) AS example_text,
                   platform, 'published' AS origin, 'reference' AS quality_status,
                   metadata_json, created_at
            FROM social_posts
            WHERE business_id = %s AND status = 'published'
              AND NULLIF(BTRIM(COALESCE(platform_text, base_text, '')), '') IS NOT NULL
            ORDER BY published_at DESC NULLS LAST, updated_at DESC
            LIMIT %s
            """,
            (business_id, remaining),
        )
        examples.extend(_serialize_example(cursor, row) for row in cursor.fetchall() or [])
    deduplicated_examples: list[dict[str, Any]] = []
    seen_texts: set[str] = set()
    for example in examples:
        normalized = " ".join(str(example.get("text") or "").lower().split())
        if not normalized or normalized in seen_texts:
            continue
        seen_texts.add(normalized)
        deduplicated_examples.append(example)
    examples = deduplicated_examples[: max(1, min(limit, 5))]
    derived = _derive_profile(examples)
    return {
        "summary": str(profile.get("summary") or derived.get("summary") or ""),
        "preferences": _json_value(profile.get("preferences_json"), derived.get("preferences") or {}),
        "forbidden_phrases": _json_value(profile.get("forbidden_phrases_json"), []),
        "typical_ctas": _json_value(profile.get("typical_ctas_json"), derived.get("typical_ctas") or []),
        "version": int(profile.get("version") or 1),
        "status": str(profile.get("status") or "draft"),
        "examples": examples,
    }
