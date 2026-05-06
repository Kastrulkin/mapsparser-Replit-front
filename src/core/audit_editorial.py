from __future__ import annotations

import copy
import re
from typing import Any


SUMMARY_PUBLIC_MAX = 320
SUMMARY_WHATSAPP_MAX = 240


AUDIT_FORBIDDEN_MARKERS = (
    "за чем сюда идти",
    "слабый визуальный слой режет доверие",
    "зоны роста",
    "реальные запросы клиентов",
    "без допрекламы",
    "конверсионный блок",
    "конверсионные фото",
    "social proof",
    "для medical вертикали",
    "для beauty вертикали",
    "алгоритмы и пользователи",
    "ai ",
    "q&a",
)


TECHNICAL_PUBLIC_KEYS = {
    "audit_full",
    "ai_enrichment",
    "debug",
    "debug_json",
    "raw_response",
    "prompt",
    "prompt_text",
    "prompt_key",
    "prompt_version",
    "prompt_source",
    "model",
    "model_name",
    "reasoning",
}


PROFILE_ACTOR = {
    "medical": "пациент",
    "hospitality": "гость",
}

PROFILE_ACTOR_DATIVE = {
    "medical": "пациенту",
    "hospitality": "гостю",
}


def normalize_audit_text(value: Any, *, audit_profile: str = "") -> str:
    text = str(value or "").strip()
    if not text:
        return text

    replacements = (
        ("за чем сюда идти", "с каким запросом обращаться"),
        ("Зачем сюда идти", "С каким запросом обращаться"),
        (
            "Описание карточки не объясняет, с каким запросом сюда обращаться",
            "Описание не показывает основные услуги и поводы обратиться",
        ),
        (
            "описание карточки не объясняет, с каким запросом сюда обращаться",
            "описание не показывает основные услуги и поводы обратиться",
        ),
        (
            "Описание карточки не объясняет центр под поисковое намерение",
            "Описание не показывает ключевые процедуры и формат центра",
        ),
        (
            "описание карточки не объясняет центр под поисковое намерение",
            "описание не показывает ключевые процедуры и формат центра",
        ),
        (
            "Описание карточки не объясняет центр под запросы клиентов",
            "Описание не показывает ключевые процедуры, формат центра и кому он подходит",
        ),
        (
            "описание карточки не объясняет центр под запросы клиентов",
            "описание не показывает ключевые процедуры, формат центра и кому он подходит",
        ),
        (
            "Описание карточки не объясняет ценность бизнеса",
            "Описание не показывает, чем занимается бизнес и почему его выбрать",
        ),
        (
            "описание карточки не объясняет ценность бизнеса",
            "описание не показывает, чем занимается бизнес и почему его выбрать",
        ),
        ("слабый визуальный слой режет доверие", "не хватает визуальных доказательств выбора"),
        ("Слабый визуальный слой режет доверие", "Не хватает визуальных доказательств выбора"),
        ("зоны роста", "что мешает получать больше обращений"),
        ("Зоны роста", "Что мешает получать больше обращений"),
        ("под реальный спрос", "под поисковые сценарии клиентов"),
        ("Под реальный спрос", "Под поисковые сценарии клиентов"),
        ("под поисковое намерение", "под запросы клиентов"),
        ("Под поисковое намерение", "Под запросы клиентов"),
        ("реальные запросы клиентов", "поисковые сценарии клиентов"),
        ("Реальные запросы клиентов", "Поисковые сценарии клиентов"),
        ("без допрекламы", "без увеличения рекламного бюджета"),
        ("Без допрекламы", "Без увеличения рекламного бюджета"),
        ("конверсионные фото", "фото, которые помогают выбрать"),
        ("конверсионный блок", "понятный блок выбора"),
        ("conversion layer", "слой выбора"),
        ("social proof", "доверие через отзывы"),
        ("Q&A", "вопросы и ответы"),
        ("q&a", "вопросы и ответы"),
        ("freshness", "свежести обновлений"),
        ("УТП", "отличие"),
        ("утп", "отличие"),
        ("Добавить описание 500–1000 символов:", "Добавить короткое описание:"),
        ("Добавить описание 500-1000 символов:", "Добавить короткое описание:"),
        ("Для medical вертикали", "Для медицинской карточки"),
        ("Для beauty вертикали", "Для карточки услуг"),
        ("алгоритмы и пользователи ждут", "пользователям важно видеть"),
        ("Пациенты и алгоритмы ждут", "Пациентам важно видеть"),
        ("описание не превращает их в понятные причины записаться", "описание не выделяет их как основные причины выбрать карточку"),
        ("не превращает отзывы в SEO", "не использует отзывы для доверия и выбора"),
        ("не продаёт", "не объясняет"),
        ("режет доверие", "снижает доверие"),
        ("целевой зоны", "нужного уровня"),
    )
    result = text
    for source, target in replacements:
        result = result.replace(source, target)

    if audit_profile not in {"medical", "hospitality"}:
        result = result.replace("Пациент", "Клиент").replace("пациент", "клиент")
    if audit_profile not in {"beauty", "wellness", "medical"}:
        result = re.sub(r"\bсалона\b", "бизнеса", result, flags=re.IGNORECASE)
        result = re.sub(r"\bсалон\b", "бизнес", result, flags=re.IGNORECASE)

    result = re.sub(r"\s+", " ", result).strip()
    return result


def truncate_sentence(text: Any, limit: int) -> str:
    value = re.sub(r"\s+", " ", str(text or "").strip())
    if len(value) <= limit:
        return value
    cut = value[: max(0, limit - 1)].rstrip()
    sentence_end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if sentence_end >= 120:
        return cut[: sentence_end + 1].strip()
    return cut.rstrip(" .,;:") + "…"


def actor_for_profile(audit_profile: Any) -> str:
    return PROFILE_ACTOR.get(str(audit_profile or "").strip().lower(), "клиент")


def actor_dative_for_profile(audit_profile: Any) -> str:
    return PROFILE_ACTOR_DATIVE.get(str(audit_profile or "").strip().lower(), "клиенту")


def _first_issue(audit: dict[str, Any]) -> dict[str, Any]:
    for key in ("top_3_issues", "issue_blocks", "findings"):
        items = audit.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict):
                return item
    return {}


def _issue_title(issue: dict[str, Any]) -> str:
    return str(issue.get("title") or issue.get("problem") or issue.get("description") or "").strip().rstrip(".")


def _issue_fix(issue: dict[str, Any]) -> str:
    return str(issue.get("fix") or issue.get("description") or issue.get("title") or "").strip().rstrip(".")


def _first_action_fix(audit: dict[str, Any], fallback: str) -> str:
    actions = audit.get("recommended_actions")
    if isinstance(actions, list):
        for item in actions:
            if not isinstance(item, dict):
                continue
            candidate = str(item.get("description") or item.get("fix") or item.get("title") or "").strip().rstrip(".")
            if candidate and candidate.lower() != fallback.lower():
                return candidate
    return fallback


def _state_fact(audit: dict[str, Any]) -> str:
    state = audit.get("current_state") if isinstance(audit.get("current_state"), dict) else {}
    facts: list[str] = []
    services_count = int(state.get("services_count") or 0)
    priced_count = int(state.get("services_with_price_count") or state.get("priced_services_count") or 0)
    photos_count = int(state.get("photos_count") or 0)
    reviews_count = int(state.get("reviews_count") or 0)
    unanswered = int(state.get("unanswered_reviews_count") or 0)
    rating = state.get("rating")
    has_website = state.get("has_website")
    has_activity = state.get("has_recent_activity")
    description_present = bool(state.get("description_present"))

    if services_count > 0 and priced_count <= 0:
        facts.append(f"услуг {services_count}, но цены не показаны")
    elif services_count <= 0:
        facts.append("услуги не раскрыты в карточке")
    if photos_count <= 0:
        facts.append("фотографий нет")
    elif photos_count == 1:
        facts.append("всего 1 фото")
    elif photos_count < 8:
        facts.append(f"фото пока {photos_count}")
    if reviews_count > 0 and unanswered > 0:
        facts.append(f"без ответа {unanswered} отзывов")
    elif reviews_count <= 0:
        facts.append("отзывов пока нет")
    if rating is not None:
        try:
            rating_value = float(rating)
        except (TypeError, ValueError):
            rating_value = None
        if rating_value is not None and 0 < rating_value < 4.5:
            facts.append(f"рейтинг {rating_value:.1f}")
    if has_website is False:
        facts.append("сайт не указан")
    if has_activity is False:
        facts.append("новости не обновлялись")
    if not description_present:
        facts.append("описание не объясняет основные услуги")

    return ", ".join(facts[:2])


def _pattern_hint(audit: dict[str, Any]) -> str:
    patterns = audit.get("industry_patterns") if isinstance(audit.get("industry_patterns"), dict) else {}
    examples = patterns.get("examples") if isinstance(patterns.get("examples"), list) else []
    service_patterns = patterns.get("service_patterns") if isinstance(patterns.get("service_patterns"), list) else []
    if examples:
        return f"Ориентир для услуг: {', '.join(str(item) for item in examples[:2])}."
    if service_patterns:
        return str(service_patterns[0]).strip().rstrip(".") + "."
    return ""


def build_editorial_summary(audit: dict[str, Any], *, max_length: int = SUMMARY_PUBLIC_MAX) -> str:
    if not isinstance(audit, dict):
        return ""
    audit_profile = str(audit.get("audit_profile") or "").strip().lower()
    actor = actor_for_profile(audit_profile)
    actor_dative = actor_dative_for_profile(audit_profile)
    business_name = str(audit.get("business_name") or audit.get("name") or "").strip()
    issue = _first_issue(audit)
    issue_title = normalize_audit_text(_issue_title(issue), audit_profile=audit_profile)
    issue_fix = normalize_audit_text(_first_action_fix(audit, _issue_fix(issue)), audit_profile=audit_profile)
    state_fact = _state_fact(audit)
    pattern_hint = _pattern_hint(audit)

    if issue_title:
        if business_name:
            first = f"У «{business_name}»: {issue_title[:1].lower() + issue_title[1:]}."
        else:
            first = issue_title + "."
    elif state_fact:
        first = f"В карточке видно: {state_fact}."
    else:
        first = "Карточка нуждается в более понятной упаковке предложения."

    if state_fact:
        second = f"Сейчас {state_fact}, поэтому {actor_dative} сложнее быстро выбрать и обратиться."
    elif pattern_hint:
        second = pattern_hint
    else:
        second = f"{actor_dative[:1].upper() + actor_dative[1:]} нужно быстрее понять основные услуги, доказательства выбора и следующий шаг."

    if issue_fix and issue_fix.lower() != issue_title.lower():
        third = f"Первое действие: {issue_fix}."
    else:
        third = "Первое действие: выделить основные услуги, добавить доказательства выбора и обновить карточку."

    return truncate_sentence(
        normalize_audit_text(" ".join([first, second, third]), audit_profile=audit_profile),
        max_length,
    )


def build_summary_variants(audit: dict[str, Any]) -> dict[str, str]:
    public_summary = build_editorial_summary(audit, max_length=SUMMARY_PUBLIC_MAX)
    whatsapp_summary = build_editorial_summary(audit, max_length=SUMMARY_WHATSAPP_MAX)
    return {
        "summary_public": public_summary,
        "summary_whatsapp": whatsapp_summary,
    }


def _contains_forbidden_marker(text: Any) -> bool:
    lowered = str(text or "").strip().lower().replace("ё", "е")
    return any(marker.replace("ё", "е") in lowered for marker in AUDIT_FORBIDDEN_MARKERS)


def audit_quality_gate(audit: dict[str, Any]) -> dict[str, Any]:
    summary = str(audit.get("summary_text") or "").strip()
    issues: list[str] = []
    if len(summary) > SUMMARY_PUBLIC_MAX:
        issues.append("summary_too_long")
    if _contains_forbidden_marker(summary):
        issues.append("summary_forbidden_marker")
    for key in ("issue_blocks", "top_3_issues", "recommended_actions"):
        items = audit.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            joined = " ".join(str(value or "") for value in item.values())
            if _contains_forbidden_marker(joined):
                issues.append(f"{key}_forbidden_marker")
                break
    return {
        "status": "pass" if not issues else "rewritten",
        "issues": sorted(set(issues)),
    }


def apply_audit_editorial_pass(audit: dict[str, Any]) -> dict[str, Any]:
    output = copy.deepcopy(audit if isinstance(audit, dict) else {})
    audit_profile = str(output.get("audit_profile") or "").strip().lower()

    for key in ("summary_text", "why_now"):
        if key in output:
            output[key] = normalize_audit_text(output.get(key), audit_profile=audit_profile)

    for list_key in ("issue_blocks", "top_3_issues", "recommended_actions", "findings"):
        items = output.get(list_key)
        if not isinstance(items, list):
            continue
        next_items: list[Any] = []
        for item in items:
            if not isinstance(item, dict):
                next_items.append(item)
                continue
            next_item = copy.deepcopy(item)
            for text_key in ("title", "problem", "description", "evidence", "impact", "fix"):
                if text_key in next_item:
                    next_item[text_key] = normalize_audit_text(next_item.get(text_key), audit_profile=audit_profile)
            next_items.append(next_item)
        output[list_key] = next_items

    for list_key in (
        "best_fit_customer_profile",
        "weak_fit_customer_profile",
        "best_fit_guest_profile",
        "weak_fit_guest_profile",
        "search_intents_to_target",
        "photo_shots_missing",
        "positioning_focus",
    ):
        items = output.get(list_key)
        if isinstance(items, list):
            output[list_key] = [normalize_audit_text(item, audit_profile=audit_profile) for item in items]

    gate_before = audit_quality_gate(output)
    if gate_before["issues"] or output.get("business_name") or not str(output.get("summary_text") or "").strip():
        output["summary_text"] = build_editorial_summary(output, max_length=SUMMARY_PUBLIC_MAX)

    variants = build_summary_variants(output)
    output.update(variants)
    output["editorial_quality_gate"] = audit_quality_gate(output)
    return output


def clean_public_payload(value: Any) -> Any:
    if isinstance(value, list):
        return [clean_public_payload(item) for item in value]
    if not isinstance(value, dict):
        return value
    result: dict[str, Any] = {}
    for key, item in value.items():
        if key in TECHNICAL_PUBLIC_KEYS:
            continue
        result[key] = clean_public_payload(item)
    return result
