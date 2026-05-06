from __future__ import annotations

from typing import Any


SERVICE_REGENERATION_BATCH_LIMIT = 10
MAX_SERVICE_REGENERATION_ATTEMPTS = 1
SERVICE_REGENERATION_RATE_LIMIT_COOLDOWN_MINUTES = 15
SERVICE_REGENERATION_ITEM_DELAY_SECONDS = 3


def build_problem_regeneration_instructions(quality: dict[str, Any]) -> str:
    issue_codes = quality.get("issue_codes")
    if not isinstance(issue_codes, list):
        issue_codes = []

    keyword_score = quality.get("keyword_score")
    if not isinstance(keyword_score, dict):
        keyword_score = {}

    instructions = [
        "Сохрани смысл исходной услуги и исправь только проблему качества SEO-предложения.",
    ]

    missing = keyword_score.get("missing")
    if isinstance(missing, list) and missing:
        instructions.append(
            "Сохрани SEO-ключи: " + ", ".join([str(item) for item in missing[:5]]) + "."
        )
    if "weak_matches_only" in issue_codes:
        instructions.append(
            "Замени слабое близкое совпадение на более точное вхождение ключа без потери смысла."
        )
    if "fallback_used" in issue_codes or "fallback_description" in issue_codes:
        instructions.append(
            "Не возвращай шаблонное описание; сделай короткое точное описание в одно предложение."
        )
    if "guardrail_reasons" in issue_codes:
        instructions.append(
            "Не добавляй неподтвержденные обещания, зоны, препараты, объемы или аудиторию."
        )
    if "name_unchanged" in issue_codes:
        instructions.append(
            "Улучшить название можно только за счет релевантного ключа и сохраненных атрибутов."
        )
    if "no_keywords" in issue_codes:
        instructions.append(
            "SEO-ключи не найдены: сохрани исходный смысл и добавь только очевидный ключ из названия услуги."
        )

    return " ".join(instructions)


def select_problem_services_for_regeneration(
    services: list[dict[str, Any]],
    audit_items: list[dict[str, Any]],
    attempts_by_service_id: dict[str, int],
    *,
    limit: int = SERVICE_REGENERATION_BATCH_LIMIT,
    max_attempts: int = MAX_SERVICE_REGENERATION_ATTEMPTS,
) -> dict[str, Any]:
    services_by_id = {
        str(service.get("id") or ""): service
        for service in services
        if str(service.get("id") or "").strip()
    }
    selected: list[dict[str, Any]] = []
    manual_review: list[dict[str, Any]] = []

    for item in audit_items:
        if not item.get("needs_review"):
            continue
        service_id = str(item.get("service_id") or "").strip()
        if not service_id or service_id not in services_by_id:
            continue
        attempts = int(attempts_by_service_id.get(service_id, 0) or 0)
        entry = {
            "service": services_by_id[service_id],
            "quality": item,
            "attempts": attempts,
            "instructions": build_problem_regeneration_instructions(item),
        }
        if attempts >= max_attempts:
            manual_review.append(entry)
            continue
        if len(selected) < limit:
            selected.append(entry)

    remaining_after_batch = max(
        0,
        len([
            item for item in audit_items
            if item.get("needs_review") and str(item.get("service_id") or "").strip() in services_by_id
        ]) - len(selected) - len(manual_review),
    )

    return {
        "selected": selected,
        "manual_review": manual_review,
        "remaining_after_batch": remaining_after_batch,
    }


def is_manual_review_regeneration_status(value: Any) -> bool:
    return str(value or "").strip().lower() in {
        "manual_review",
        "needs_manual_review",
        "manual",
    }
