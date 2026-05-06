from __future__ import annotations

import json
import re
from typing import Any

from core.industry_patterns import evaluate_pattern_fit
from core.service_problem_regeneration import is_manual_review_regeneration_status


KeywordLevel = str


BEAUTY_CLOSE_GROUPS: list[list[str]] = [
    ["ваксинг", "восковая депиляция", "депиляция воском"],
    ["афро", "афрокудри", "афро кудри"],
    ["брови", "бровей", "бровная коррекция", "коррекция бровей"],
    ["ресницы", "ресниц", "наращивание ресниц"],
    ["биозавивка", "завивка"],
    ["косметология", "косметологическая процедура"],
    ["инъекции", "инъекционная косметология"],
    ["детская", "для детей", "ребенок", "ребёнок", "дети"],
    ["макияж", "визаж"],
    ["эпиляция", "лазерная эпиляция"],
    ["перманент", "татуаж", "пудровое напыление", "перманентный макияж"],
    ["маникюр", "ногти", "покрытие ногтей", "покрытие"],
    ["педикюр", "стопы", "ногти на ногах"],
    ["ботокс", "ботулинотерапия", "ботулинический токсин"],
    ["чистка лица", "уход за лицом", "пилинг", "уход"],
    ["ламинирование", "долговременная укладка"],
]


def normalize_service_text(value: Any) -> str:
    text = str(value or "").lower().replace("ё", "е")
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_keyword_token(value: Any) -> str:
    token = normalize_service_text(value)
    if len(token) <= 4:
        return token
    token = re.sub(
        r"(иями|ями|ами|его|ому|ыми|ими|ая|яя|ое|ее|ый|ий|ой|ых|их|ую|юю|ого|ему|ам|ям|ах|ях|ов|ев|ей|ом|ем|ою|ею|ы|и|а|я|о|е|у|ю)$",
        "",
        token,
    )
    token = re.sub(r"(ическ|ичес|ическа)$", "", token)
    return token


def tokenize_keyword_text(value: Any) -> list[str]:
    tokens: list[str] = []
    for item in normalize_service_text(value).split(" "):
        token = normalize_keyword_token(item)
        if len(token) >= 3 and token not in tokens:
            tokens.append(token)
    return tokens


def normalize_keyword_list(raw_keywords: Any) -> list[str]:
    flattened: list[str] = []

    def append_keyword(value: Any) -> None:
        keyword = str(value or "").strip()
        if keyword:
            flattened.append(keyword)

    if isinstance(raw_keywords, list):
        for item in raw_keywords:
            if isinstance(item, list):
                for nested in item:
                    append_keyword(nested)
                continue
            if isinstance(item, str):
                trimmed = item.strip()
                if not trimmed:
                    continue
                if trimmed.startswith("[") and trimmed.endswith("]"):
                    try:
                        parsed = json.loads(trimmed)
                    except Exception:
                        parsed = None
                    if isinstance(parsed, list):
                        for parsed_item in parsed:
                            append_keyword(parsed_item)
                        continue
                append_keyword(trimmed)
                continue
            append_keyword(item)
    elif isinstance(raw_keywords, str):
        trimmed = raw_keywords.strip()
        if trimmed.startswith("[") and trimmed.endswith("]"):
            try:
                parsed = json.loads(trimmed)
            except Exception:
                parsed = None
            if isinstance(parsed, list):
                for parsed_item in parsed:
                    append_keyword(parsed_item)
            elif trimmed:
                append_keyword(trimmed)
        elif trimmed:
            append_keyword(trimmed)

    unique: list[str] = []
    for keyword in flattened:
        clean_keyword = keyword.strip()
        if clean_keyword and clean_keyword not in unique:
            unique.append(clean_keyword)
    return unique


def _close_group_tokens(keyword: str) -> list[str]:
    normalized_keyword = normalize_service_text(keyword)
    keyword_tokens = tokenize_keyword_text(keyword)
    tokens: list[str] = []
    for group in BEAUTY_CLOSE_GROUPS:
        group_matches = False
        for item in group:
            normalized_item = normalize_service_text(item)
            item_tokens = tokenize_keyword_text(item)
            if (
                normalized_keyword in normalized_item
                or normalized_item in normalized_keyword
                or any(token in keyword_tokens for token in item_tokens)
            ):
                group_matches = True
        if group_matches:
            for item in group:
                for token in tokenize_keyword_text(item):
                    if token not in tokens:
                        tokens.append(token)
    return tokens


def match_keyword_level(draft: Any, keyword: Any) -> KeywordLevel | None:
    normalized_draft = normalize_service_text(draft)
    normalized_keyword = normalize_service_text(keyword)
    if not normalized_draft or len(normalized_keyword) < 3:
        return None
    if normalized_keyword in normalized_draft:
        return "exact"

    draft_tokens = tokenize_keyword_text(draft)
    keyword_tokens = tokenize_keyword_text(keyword)
    if keyword_tokens and all(token in draft_tokens for token in keyword_tokens):
        return "normalized"

    close_tokens = _close_group_tokens(str(keyword or ""))
    if close_tokens and any(token in draft_tokens for token in close_tokens):
        normalized_draft = normalize_service_text(draft)
        normalized_keyword = normalize_service_text(keyword)
        if normalized_keyword == "педикюр" and "маникюр" in normalized_draft:
            return None
        return "close"

    return None


def evaluate_service_keyword_score(
    draft: Any,
    keywords: Any,
    source_text: Any = "",
) -> dict[str, Any]:
    keyword_items = normalize_keyword_list(keywords)
    matches: list[dict[str, str]] = []
    missing: list[str] = []
    weak: list[str] = []
    added: list[str] = []

    for keyword in keyword_items:
        level = match_keyword_level(draft, keyword)
        if level:
            matches.append({"keyword": keyword, "level": level})
            if level == "close":
                weak.append(keyword)
            source_level = match_keyword_level(source_text, keyword) if source_text else None
            if source_text and source_level not in {"exact", "normalized"}:
                added.append(keyword)
        else:
            missing.append(keyword)

    total = len(keyword_items)
    found = len(matches)
    exact = len([item for item in matches if item.get("level") == "exact"])
    normalized = len([item for item in matches if item.get("level") == "normalized"])
    close = len([item for item in matches if item.get("level") == "close"])
    coverage = round(found / total, 2) if total else 0

    if total == 0:
        status = "no_keywords"
    elif missing:
        status = "partial"
    else:
        status = "ok"

    return {
        "status": status,
        "total": total,
        "found": found,
        "missing_count": len(missing),
        "coverage": coverage,
        "exact_count": exact,
        "normalized_count": normalized,
        "close_count": close,
        "matches": matches,
        "missing": missing,
        "added": added,
        "weak": weak,
    }


def _normalize_guardrail_reasons(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item or "").strip() for item in value if str(item or "").strip()]
    if isinstance(value, str):
        trimmed = value.strip()
        if not trimmed:
            return []
        if trimmed.startswith("[") and trimmed.endswith("]"):
            try:
                parsed = json.loads(trimmed)
            except Exception:
                parsed = None
            if isinstance(parsed, list):
                return [str(item or "").strip() for item in parsed if str(item or "").strip()]
        return [trimmed]
    return []


def evaluate_service_quality(service: dict[str, Any]) -> dict[str, Any]:
    name = str(service.get("name") or "").strip()
    description = str(service.get("description") or "").strip()
    optimized_name = str(service.get("optimized_name") or "").strip()
    optimized_description = str(service.get("optimized_description") or "").strip()
    keywords = service.get("keywords")
    draft_text = f"{optimized_name} {optimized_description}".strip()
    source_text = f"{name} {description}".strip()
    score = evaluate_service_keyword_score(draft_text, keywords, source_text)
    pattern_fit = service.get("pattern_fit")
    if not isinstance(pattern_fit, dict):
        pattern_fit = evaluate_pattern_fit(
            draft_text,
            service.get("industry_key") or service.get("vertical_key") or "local_business",
            mode="service",
        )
    guardrail_reasons = _normalize_guardrail_reasons(service.get("guardrail_reasons"))
    manual_review = is_manual_review_regeneration_status(service.get("regeneration_status"))

    issue_codes: list[str] = []
    issue_labels: list[str] = []

    if score["total"] == 0:
        issue_codes.append("no_keywords")
        issue_labels.append("нет SEO-запросов для проверки")
    if score["missing"]:
        issue_codes.append("missing_keywords")
        issue_labels.append("не хватает запроса: " + ", ".join(score["missing"][:3]))
    if score["found"] > 0 and score["found"] == score["close_count"]:
        issue_codes.append("weak_matches_only")
        issue_labels.append("запрос использован слишком неточно")
    if optimized_description and "услуга по исходному формату записи" in normalize_service_text(optimized_description):
        issue_codes.append("fallback_description")
        issue_labels.append("описание выглядит шаблонно")
    if bool(service.get("fallback_used")):
        issue_codes.append("fallback_used")
        issue_labels.append("описание нужно переписать точнее")
    if guardrail_reasons:
        issue_codes.append("guardrail_reasons")
        issue_labels.append("нужна проверка смысла и обещаний")
    if pattern_fit.get("status") == "needs_review":
        issue_codes.append("pattern_fit")
        issue_labels.append("формулировка слабо совпадает с рабочими паттернами индустрии")
    if optimized_name and name and normalize_service_text(optimized_name) == normalize_service_text(name):
        issue_codes.append("name_unchanged")
        issue_labels.append("название почти не изменилось")
    if optimized_description and description and normalize_service_text(optimized_description) == normalize_service_text(description):
        issue_codes.append("description_unchanged")
        issue_labels.append("описание почти не изменилось")
    if not optimized_name and not optimized_description:
        issue_codes.append("no_suggestion")
        issue_labels.append("нет SEO-предложения")
    if manual_review:
        issue_codes.append("manual_review")
        issue_labels.append("нужна ручная проверка")

    seen_codes: list[str] = []
    seen_labels: list[str] = []
    for code in issue_codes:
        if code not in seen_codes:
            seen_codes.append(code)
    for label in issue_labels:
        if label not in seen_labels:
            seen_labels.append(label)

    status = "manual_review" if manual_review else "needs_review" if seen_codes else "good"
    return {
        "service_id": str(service.get("id") or ""),
        "name": name,
        "status": status,
        "needs_review": status == "needs_review",
        "manual_review": status == "manual_review",
        "issue_codes": seen_codes,
        "issue_labels": seen_labels,
        "keyword_score": score,
        "pattern_fit": pattern_fit,
        "guardrail_reasons": guardrail_reasons,
    }


def build_services_quality_audit(services: list[dict[str, Any]]) -> dict[str, Any]:
    items = [evaluate_service_quality(service) for service in services]
    summary = {
        "total": len(items),
        "good": len([item for item in items if item.get("status") == "good"]),
        "needs_review": len([item for item in items if item.get("needs_review")]),
        "manual_review": len([item for item in items if item.get("manual_review")]),
        "fallback": len([
            item for item in items
            if "fallback_used" in item.get("issue_codes", []) or "fallback_description" in item.get("issue_codes", [])
        ]),
        "missing_keywords": len([item for item in items if "missing_keywords" in item.get("issue_codes", [])]),
        "weak_matches_only": len([item for item in items if "weak_matches_only" in item.get("issue_codes", [])]),
        "guardrail_failed": len([item for item in items if "guardrail_reasons" in item.get("issue_codes", [])]),
        "no_keywords": len([item for item in items if "no_keywords" in item.get("issue_codes", [])]),
        "pattern_fit": len([item for item in items if "pattern_fit" in item.get("issue_codes", [])]),
    }
    return {
        "summary": summary,
        "items": items,
        "telegram_summary": (
            f"Проверено {summary['total']} услуг\n"
            f"ОК: {summary['good']}\n"
            f"Требуют доработки: {summary['needs_review']}\n"
            f"Не хватает важных запросов: {summary['missing_keywords']}\n"
            f"Шаблонные описания: {summary['fallback']}"
        ),
    }
