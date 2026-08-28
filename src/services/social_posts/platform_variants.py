from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

from services.llm import analyze_text_with_gigachat


PLATFORM_VARIANT_RULES_VERSION = "v1"

PLATFORM_VARIANT_RULES = {
    "telegram": (
        "Полезный самостоятельный пост: 2-5 коротких абзацев, живое конкретное начало, "
        "спокойный следующий шаг. Не добавляй хештеги."
    ),
    "vk": (
        "Понятный пост для сообщества: 2-4 коротких абзаца, немного больше объяснения, "
        "чем на картах, и один естественный следующий шаг."
    ),
    "max": (
        "Компактный пост для канала MAX: главная мысль в первой строке, 2-4 коротких "
        "абзаца и один понятный следующий шаг. Текст должен сочетаться с одним живым "
        "фото; без россыпи эмодзи и хештегов."
    ),
    "google_business": (
        "Короткая фактическая новость для карточки компании: что произошло или чем полезно, "
        "кому это важно и что сделать дальше. До 1500 символов, без хештегов."
    ),
    "yandex_maps": (
        "Короткая новость для карточки на картах: конкретная услуга, ситуация или событие. "
        "Без просьб подписаться или комментировать, до 1200 символов."
    ),
    "two_gis": (
        "Короткая самостоятельная новость для карточки 2ГИС: факты, польза и спокойный "
        "следующий шаг. Не копируй дословно версию Яндекс Карт, до 1200 символов."
    ),
    "instagram": (
        "Подпись к визуальной публикации: сильная первая строка, 2-4 коротких абзаца, "
        "связь с фотографией и один мягкий следующий шаг. Без хештегов в первой версии."
    ),
    "facebook": (
        "Пост с локальным контекстом: 2-4 коротких абзаца, достаточно объяснения для "
        "самостоятельного чтения и один понятный следующий шаг."
    ),
}

PLATFORM_TEXT_LIMITS = {
    "telegram": 4096,
    "max": 4000,
    "google_business": 1500,
    "yandex_maps": 1200,
    "two_gis": 1200,
}

CHANNEL_LANGUAGE_NAMES = {
    "en": "English",
    "ru": "Russian",
}


def platform_variant_base_hash(base_text: str) -> str:
    normalized = re.sub(r"\s+", " ", str(base_text or "")).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def build_platform_variants(
    base_text: str,
    platforms: list[str],
    item: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    normalized_platforms = [
        platform
        for platform in platforms
        if platform in PLATFORM_VARIANT_RULES
    ]
    if not str(base_text or "").strip() or not normalized_platforms:
        return {}

    item_payload = item or {}
    channel_languages = _channel_languages(item_payload, normalized_platforms)
    ai_variants: dict[str, str] = {}
    generation_error = ""
    try:
        raw_result = analyze_text_with_gigachat(
            _platform_variant_prompt(base_text, normalized_platforms, item_payload),
            task_type="news_generation",
            business_id=str(item_payload.get("business_id") or item_payload.get("plan_business_id") or ""),
        )
        ai_variants = _parse_platform_variants(raw_result, normalized_platforms)
        if not ai_variants:
            generation_error = "empty_or_invalid_ai_response"
    except Exception as error:
        generation_error = str(error)[:240] or "ai_exception"

    base_hash = platform_variant_base_hash(base_text)
    adapted_at = datetime.now(timezone.utc).isoformat()
    result: dict[str, dict[str, Any]] = {}
    for platform in normalized_platforms:
        requested_language = channel_languages.get(platform)
        raw_ai_text = ai_variants.get(platform, "")
        ai_text = _normalize_platform_variant_text(platform, raw_ai_text)
        language_matches = _matches_channel_language(ai_text, requested_language)
        if not language_matches:
            ai_text = ""
        if ai_text:
            source = "ai"
            text = ai_text
        elif requested_language:
            source = "unavailable"
            text = ""
        else:
            source = "deterministic"
            text = deterministic_platform_variant(platform, base_text)
        adaptation_error = ""
        if source != "ai":
            adaptation_error = "language_mismatch" if raw_ai_text and not language_matches else generation_error
        result[platform] = {
            "text": text,
            "metadata": {
                "variant_source": source,
                "variant_status": "current" if text else "needs_regeneration",
                "base_text_hash": base_hash,
                "platform_rules_version": PLATFORM_VARIANT_RULES_VERSION,
                "channel_language": requested_language or "",
                "manually_edited": False,
                "adapted_at": adapted_at,
                "adaptation_error": adaptation_error,
            },
        }
    return result


def deterministic_platform_variant(platform: str, base_text: str) -> str:
    text = _normalize_paragraphs(base_text)
    if not text:
        return ""
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text)) if part.strip()]
    if platform in {"google_business", "yandex_maps", "two_gis"}:
        limit = PLATFORM_TEXT_LIMITS.get(platform, 1200)
        compact = " ".join(sentences[:4])
        return _truncate_at_sentence(compact, limit)
    if platform == "instagram":
        return _paragraphize_sentences(sentences, first_paragraph_size=1, paragraph_size=2, max_paragraphs=4)
    if platform in {"telegram", "max"}:
        return _paragraphize_sentences(sentences, first_paragraph_size=1, paragraph_size=2, max_paragraphs=5)
    if platform in {"vk", "facebook"}:
        return _paragraphize_sentences(sentences, first_paragraph_size=1, paragraph_size=2, max_paragraphs=4)
    return text


def merge_platform_variant_metadata(
    current_metadata: dict[str, Any] | None,
    variant_metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(current_metadata or {})
    merged.update(dict(variant_metadata or {}))
    return merged


def _platform_variant_prompt(base_text: str, platforms: list[str], item: dict[str, Any]) -> str:
    channel_languages = _channel_languages(item, platforms)
    rules = "\n".join(
        _platform_prompt_rule(platform, channel_languages.get(platform))
        for platform in platforms
    )
    return (
        "Ты редактор публикаций локального бизнеса. Создай отдельную версию одного сообщения "
        "для каждой указанной площадки.\n\n"
        "Неприкосновенные правила:\n"
        "- сохрани факты, даты, числа, условия, название компании и главный смысл исходного текста;\n"
        "- не добавляй новые услуги, цены, обещания, адреса, причины, преимущества или события;\n"
        "- одна версия раскрывает одну мысль;\n"
        "- пиши человеческим языком и короткими абзацами;\n"
        "- не используй внутренние слова: цель публикации, бизнес-задача, контент-план;\n"
        "- не копируй одну и ту же формулировку во все каналы;\n"
        "- не используй markdown и списки с техническими пояснениями;\n"
        "- верни только JSON-объект без code fence в формате "
        '{"variants":{"telegram":"текст","vk":"текст"}}.\n\n'
        f"Тема: {str(item.get('theme') or '').strip()}\n"
        f"Задача: {str(item.get('goal') or '').strip()}\n\n"
        f"Исходный подтверждённый текст:\n{str(base_text or '').strip()}\n\n"
        f"Правила площадок:\n{rules}"
    )


def _channel_languages(item: dict[str, Any], platforms: list[str]) -> dict[str, str]:
    metadata = item.get("metadata_json")
    raw_languages = metadata.get("channel_languages") if isinstance(metadata, dict) else None
    if not isinstance(raw_languages, dict):
        return {}
    allowed_platforms = set(platforms)
    return {
        str(platform).strip(): str(language).strip().lower()
        for platform, language in raw_languages.items()
        if str(platform).strip() in allowed_platforms
        and str(language).strip().lower() in CHANNEL_LANGUAGE_NAMES
    }


def _platform_prompt_rule(platform: str, language: str | None) -> str:
    language_rule = ""
    if language:
        language_rule = f" write in {CHANNEL_LANGUAGE_NAMES[language]};"
    return f"- {platform}:{language_rule} {PLATFORM_VARIANT_RULES[platform]}"


def _matches_channel_language(text: str, language: str | None) -> bool:
    if not text or not language:
        return bool(text)
    cyrillic_count = len(re.findall(r"[А-Яа-яЁё]", text))
    if language == "en":
        return cyrillic_count < 4
    if language == "ru":
        return cyrillic_count >= 4
    return True


def _parse_platform_variants(raw_result: Any, platforms: list[str]) -> dict[str, str]:
    text = str(raw_result or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    candidates = [text]
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace >= 0 and last_brace > first_brace:
        candidates.append(text[first_brace:last_brace + 1])
    parsed: dict[str, Any] = {}
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except Exception:
            continue
        if isinstance(value, dict):
            parsed = value
            break
    variants = parsed.get("variants") if isinstance(parsed.get("variants"), dict) else parsed
    return {
        platform: str(variants.get(platform) or "").strip()
        for platform in platforms
        if str(variants.get(platform) or "").strip()
    }


def _normalize_platform_variant_text(platform: str, raw_text: str) -> str:
    text = _normalize_paragraphs(raw_text)
    if not text:
        return ""
    if any(marker in text.lower() for marker in ("цель публикации", "бизнес-задача", "контент-план")):
        return ""
    if text.count("#") > 0:
        return ""
    limit = PLATFORM_TEXT_LIMITS.get(platform)
    if limit and len(text) > limit:
        return _truncate_at_sentence(text, limit)
    return text


def _normalize_paragraphs(value: str) -> str:
    paragraphs = [
        re.sub(r"\s+", " ", paragraph).strip()
        for paragraph in re.split(r"\n\s*\n", str(value or "").strip())
    ]
    return "\n\n".join(paragraph for paragraph in paragraphs if paragraph)


def _paragraphize_sentences(
    sentences: list[str],
    first_paragraph_size: int,
    paragraph_size: int,
    max_paragraphs: int,
) -> str:
    if not sentences:
        return ""
    paragraphs = [" ".join(sentences[:first_paragraph_size])]
    remaining = sentences[first_paragraph_size:]
    while remaining and len(paragraphs) < max_paragraphs:
        paragraphs.append(" ".join(remaining[:paragraph_size]))
        remaining = remaining[paragraph_size:]
    if remaining:
        paragraphs[-1] = f"{paragraphs[-1]} {' '.join(remaining)}".strip()
    return "\n\n".join(paragraph for paragraph in paragraphs if paragraph)


def _truncate_at_sentence(text: str, limit: int) -> str:
    normalized = str(text or "").strip()
    if len(normalized) <= limit:
        return normalized
    shortened = normalized[:limit].rstrip()
    boundary = max(shortened.rfind("."), shortened.rfind("!"), shortened.rfind("?"))
    if boundary >= max(80, limit // 2):
        return shortened[:boundary + 1].strip()
    word_boundary = shortened.rfind(" ")
    return shortened[:word_boundary].rstrip(" ,;:-") if word_boundary > 0 else shortened
