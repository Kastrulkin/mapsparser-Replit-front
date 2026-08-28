from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any


CONTENT_EDITORIAL_RULES_VERSION = "content-editorial-v3"

NATURAL_CONTENT_CONTRACT = (
    "- каждое предложение добавляет новый факт, действие, наблюдаемый результат или следующий шаг;\n"
    "- после конкретной сцены не добавляй обобщающую «мораль»;\n"
    "- не пиши о понятном процессе, комфортном темпе, особом подходе или простых вещах вместо конкретного эпизода;\n"
    "- не добавляй привычки бизнеса вроде «мы всегда» по одному эпизоду;\n"
    "- не добавляй детали, которых нет в источниках;\n"
    "- удали предложение, если его можно без изменений поставить в пост любого конкурента."
)

GENERIC_SUMMARY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "GENERIC_SUMMARY",
        re.compile(
            r"\b(?:такой|этот|подобный)\s+"
            r"(?:визит|подход|процесс|формат|опыт|результат)\s+"
            r"(?:складывается|строится|создаётся|становится)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "GENERIC_SUMMARY",
        re.compile(
            r"\b(?:спокойный|комфортный|хороший|удачный)\s+"
            r"(?:визит|процесс|опыт)\s+складывается\b",
            re.IGNORECASE,
        ),
    ),
)

ABSTRACT_COPY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ABSTRACT_BENEFIT", re.compile(r"\bпонятн\w*\s+процесс\w*\b", re.IGNORECASE)),
    ("ABSTRACT_BENEFIT", re.compile(r"\bкомфортн\w*\s+темп\w*\b", re.IGNORECASE)),
    ("ABSTRACT_BENEFIT", re.compile(r"\bособ\w*\s+подход\w*\b", re.IGNORECASE)),
    ("ABSTRACT_BENEFIT", re.compile(r"\bскладывается\s+из\s+прост\w*\s+вещ\w*\b", re.IGNORECASE)),
)

SOURCE_SENSITIVE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("UNSUPPORTED_CLAIM", re.compile(r"\bлюбим\w*\s+мультфильм\w*\b", re.IGNORECASE)),
    ("UNSUPPORTED_CLAIM", re.compile(r"\bобъясн\w*\s+кажд\w*\s+шаг\w*\b", re.IGNORECASE)),
    ("UNSUPPORTED_CLAIM", re.compile(r"\bпоговор\w*\s+(?:пару|несколько)\s+минут\w*\b", re.IGNORECASE)),
    ("UNSUPPORTED_CLAIM", re.compile(r"\bбез\s+слёз\b", re.IGNORECASE)),
    ("UNSUPPORTED_HABIT", re.compile(r"\bмы\s+всегда\b", re.IGNORECASE)),
    ("UNSUPPORTED_HABIT", re.compile(r"\bнаш\w*\s+мастер\w*\s+(?:всегда|умеют)\b", re.IGNORECASE)),
)

ISSUE_MESSAGES = {
    "GENERIC_SUMMARY": "Абстрактный вывод после конкретной сцены",
    "ABSTRACT_BENEFIT": "Абстрактная польза без конкретного примера",
    "UNSUPPORTED_CLAIM": "Деталь не подтверждена источником",
    "UNSUPPORTED_HABIT": "Один эпизод превращён в общее обещание бизнеса",
    "EMPTY_TEXT": "Текст пуст",
}


def content_text_hash(text: str) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def source_text_from_brief(brief: dict[str, Any] | None) -> str:
    payload = brief if isinstance(brief, dict) else {}
    source_facts = [
        str(item.get("fact") or "").strip()
        for item in payload.get("sources") or []
        if isinstance(item, dict) and str(item.get("fact") or "").strip()
    ]
    confirmed = [str(value or "").strip() for value in payload.get("confirmed_details") or [] if str(value or "").strip()]
    return "\n".join([*source_facts, *confirmed]).strip()


def review_content_text(
    text: str,
    *,
    brief: dict[str, Any] | None = None,
    source_text: str = "",
    platform: str = "",
) -> dict[str, Any]:
    normalized_text = str(text or "").strip()
    evidence_text = str(source_text or "").strip() or source_text_from_brief(brief)
    issue_codes: list[str] = []

    if not normalized_text:
        issue_codes.append("EMPTY_TEXT")
    for code, pattern in (*GENERIC_SUMMARY_PATTERNS, *ABSTRACT_COPY_PATTERNS):
        if pattern.search(normalized_text):
            issue_codes.append(code)
    for code, pattern in SOURCE_SENSITIVE_PATTERNS:
        if pattern.search(normalized_text) and not pattern.search(evidence_text):
            issue_codes.append(code)

    unique_codes = list(dict.fromkeys(issue_codes))
    return {
        "quality_passed": not unique_codes,
        "quality_issues": [ISSUE_MESSAGES[code] for code in unique_codes],
        "quality_issue_codes": unique_codes,
        "quality_rules_version": CONTENT_EDITORIAL_RULES_VERSION,
        "quality_text_hash": content_text_hash(normalized_text),
        "quality_source_hash": content_text_hash(evidence_text),
        "quality_platform": str(platform or "").strip(),
        "quality_reviewed_at": datetime.now(timezone.utc).isoformat(),
    }


def quality_review_is_current(text: str, metadata: dict[str, Any] | None) -> bool:
    payload = metadata if isinstance(metadata, dict) else {}
    return bool(
        payload.get("quality_passed") is True
        and str(payload.get("quality_rules_version") or "") == CONTENT_EDITORIAL_RULES_VERSION
        and str(payload.get("quality_text_hash") or "") == content_text_hash(text)
    )
