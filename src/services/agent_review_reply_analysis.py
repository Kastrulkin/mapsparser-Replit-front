from __future__ import annotations

import json
import re
import sys
from typing import Any, Callable, Dict, List

from services.gigachat_client import analyze_text_with_gigachat


MAX_REVIEW_LLM_CONTEXT_CHARS = 12000
REVIEW_LLM_PROMPT_VERSION = "agent_review_replies_v6"
REVIEW_SOURCE_NAMES = {"reviews", "external_reviews", "отзывы", "отзывы компании", "последние отзывы"}
ANONYMOUS_AUTHOR_NAMES = {"", "клиент", "аноним", "анонимный пользователь", "пользователь"}
UNVERIFIED_PROMISE_MARKERS = (
    "компенсац",
    "компенсир",
    "возмест",
    "вернем деньги",
    "вернуть деньги",
    "возврат средств",
    "скидк",
    "бесплатн",
    "подар",
    "предпримем меры",
    "примем меры",
    "соответствующие меры",
    "проведем внутреннее расследование",
    "немедленно проведем",
    "refund",
    "reimburse",
    "discount",
    "free service",
    "gift",
)
UNVERIFIED_INTERNAL_ACTION_PATTERNS = (
    r"\b(?:учтем|учтём)\b.{0,120}\bобучени\w*\s+сотрудник",
    r"\b(?:проведем|проведём)\b.{0,80}\bобучени\w*",
    r"\b(?:обязательно\s+исправим|гарантируем|решим\s+(?:эту\s+)?проблему)\b",
    (
        r"\bмы\s+(?:немедленно\s+|обязательно\s+)?"
        r"(?:разберем|разберём|проверим|предотвратим|учтем|учтём|примем|исправим|проведем|проведём|"
        r"свяжемся|компенсируем|вернем|вернём|обучим|улучшим|сделаем|гарантируем|позаботимся|"
        r"выясним|решим|передадим|предпримем)\b"
    ),
)
UNVERIFIED_PROMISE_REVIEW_REASON = (
    "Неподтверждённое обещание генератора удалено. Проверьте безопасный черновик перед публикацией."
)
INCOMPLETE_REPLY_REVIEW_REASON = (
    "Незавершённый черновик генератора заменён полным безопасным ответом. Проверьте его перед публикацией."
)
UNVERIFIED_NAME_REVIEW_REASON = (
    "Неподтверждённое имя получателя удалено. Проверьте безопасный черновик перед публикацией."
)


def draft_review_replies_with_llm(
    setup: Dict[str, Any],
    extracted_items: List[Dict[str, Any]],
    feedback_history: List[Dict[str, Any]] | None = None,
    business_id: str = "",
    user_id: str = "",
    run_id: str = "",
    generator: Callable[..., str] | None = None,
) -> Dict[str, Any]:
    selected_reviews = _selected_reviews(setup, extracted_items)
    reply_limit = _requested_reply_limit(setup)
    fallback = build_review_replies_fallback(setup, extracted_items, feedback_history or [])
    if not selected_reviews:
        fallback.update(
            {
                "analysis_source": "deterministic_no_matching_reviews",
                "analysis_prompt_key": "agent_review_replies",
                "analysis_prompt_version": REVIEW_LLM_PROMPT_VERSION,
                "llm_analysis_used": False,
                "llm_error": "",
                "provenance": [],
                "external_dispatch_performed": False,
                "publish_state": "not_published",
                "delivery_state": "not_dispatched",
            }
        )
        return fallback
    prompt = _build_review_prompt(setup, selected_reviews, feedback_history or [], reply_limit)
    try:
        raw_response = (
            generator(prompt, business_id=business_id, user_id=user_id)
            if generator
            else _default_review_generator(prompt, business_id=business_id, user_id=user_id, run_id=run_id)
        )
        parsed = _parse_llm_json(raw_response)
        normalized = _normalize_llm_review_replies(parsed, fallback, selected_reviews, reply_limit)
        normalized.update(
            {
                "analysis_source": "gigachat",
                "analysis_prompt_key": "agent_review_replies",
                "analysis_prompt_version": REVIEW_LLM_PROMPT_VERSION,
                "llm_analysis_used": True,
                "llm_error": "",
                "provenance": _provenance(selected_reviews),
                "external_dispatch_performed": False,
                "publish_state": "not_published",
                "delivery_state": "not_dispatched",
            }
        )
        return normalized
    except Exception:
        exc = sys.exc_info()[1]
        fallback.update(
            {
                "analysis_source": "deterministic_fallback",
                "analysis_prompt_key": "agent_review_replies",
                "analysis_prompt_version": REVIEW_LLM_PROMPT_VERSION,
                "llm_analysis_used": False,
                "llm_error": str(exc)[:240],
                "provenance": _provenance(selected_reviews),
                "external_dispatch_performed": False,
                "publish_state": "not_published",
                "delivery_state": "not_dispatched",
            }
        )
        return fallback


def build_review_replies_fallback(
    setup: Dict[str, Any],
    extracted_items: List[Dict[str, Any]],
    feedback_history: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    reviews = _selected_reviews(setup, extracted_items)
    rules = _clean_text(setup.get("processing_rules"))
    feedback_notes = [
        _clean_text(item.get("feedback"))
        for item in (feedback_history or [])
        if isinstance(item, dict) and _clean_text(item.get("feedback"))
    ][-3:]
    replies = [_fallback_reply(review, rules) for review in reviews[:_requested_reply_limit(setup)]]
    if not replies:
        missing_text = "Отзывы без ответа не найдены." if _requests_unanswered(setup) else "Отзывы для подготовки ответа не найдены."
        return {
            "title": "Нет отзывов для ответа",
            "summary": [missing_text, "Публикация не выполнялась."],
            "reply_drafts": [],
            "manual_review_reasons": ["Обновите источник отзывов или измените параметры запуска."],
            "checklist": [],
            "rules_applied": [rules] if rules else [],
            "feedback_notes": feedback_notes,
            "format": _clean_text(setup.get("output_format")) or "Черновики ответов на отзывы",
        }
    return {
        "title": "Черновики ответов на отзывы",
        "summary": [
            f"Подготовлено черновиков: {len(replies)}",
            "Публикация не выполнялась.",
        ],
        "reply_drafts": replies,
        "manual_review_reasons": _manual_review_reasons(replies, rules),
        "checklist": _review_checklist(replies, rules),
        "rules_applied": [rules] if rules else [],
        "feedback_notes": feedback_notes,
        "format": _clean_text(setup.get("output_format")) or "Черновики ответов на отзывы",
    }


def _default_review_generator(prompt: str, *, business_id: str = "", user_id: str = "", run_id: str = "") -> str:
    return analyze_text_with_gigachat(
        prompt,
        task_type="agent_review_replies",
        business_id=business_id or None,
        user_id=user_id or None,
        usage_reference=f"agent-run:{run_id}" if run_id else None,
    )


def _build_review_prompt(
    setup: Dict[str, Any],
    selected_reviews: List[Dict[str, Any]],
    feedback_history: List[Dict[str, Any]],
    reply_limit: int,
) -> str:
    feedback_notes = [
        _clean_text(item.get("feedback"))
        for item in feedback_history
        if isinstance(item, dict) and _clean_text(item.get("feedback"))
    ][-3:]
    payload = {
        "task": _clean_text(setup.get("workflow_description")),
        "extraction_rules": _clean_text(setup.get("extraction_rules")),
        "processing_rules": _clean_text(setup.get("processing_rules")),
        "output_format": _clean_text(setup.get("output_format")),
        "manual_control": _clean_text(setup.get("manual_control")),
        "feedback_notes": feedback_notes,
        "reply_limit": reply_limit,
        "reviews": _review_context(selected_reviews),
    }
    return (
        "Ты готовишь безопасные черновики ответов на отзывы для LocalOS agent blueprint. "
        "Используй только предоставленные отзывы, не обещай компенсации/скидки без данных, не публикуй ответ. "
        "Не обещай внутреннее расследование, обучение сотрудников или изменения процессов, если таких фактов нет во входных данных. "
        "Каждый ответ должен состоять из полных предложений и не заканчиваться многоточием. "
        "Не обращайся по имени, если author_name пустой, анонимный или обозначен как пользователь. "
        "Верни только JSON без markdown с полями: "
        "title, summary(list), reply_drafts(list), manual_review_reasons(list), checklist(list), rules_applied(list). "
        f"Подготовь не больше {reply_limit} ответов и сохрани review_id исходного отзыва. "
        "reply_drafts должны быть объектами: review_id, author_name, rating, sentiment, reply, manual_review_reason.\n\n"
        f"INPUT_JSON:\n{json.dumps(payload, ensure_ascii=False)}"
    )


def _review_context(selected_reviews: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    context = []
    used = 0
    for review in selected_reviews[:30]:
        text = json.dumps(review, ensure_ascii=False)
        remaining = MAX_REVIEW_LLM_CONTEXT_CHARS - used
        if remaining <= 0:
            break
        snippet = text[:remaining]
        used += len(snippet)
        context.append({"source_name": review["source_name"], "values": snippet})
    return context


def _parse_llm_json(raw_response: str) -> Dict[str, Any]:
    text = _clean_text(raw_response)
    if not text:
        raise ValueError("empty LLM response")
    try:
        parsed = json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("LLM response does not contain JSON")
        parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("LLM response JSON is not an object")
    return parsed


def _normalize_llm_review_replies(
    parsed: Dict[str, Any],
    fallback: Dict[str, Any],
    selected_reviews: List[Dict[str, Any]],
    reply_limit: int,
) -> Dict[str, Any]:
    reply_drafts = _anchor_reply_drafts(_clean_reply_drafts(parsed.get("reply_drafts")), selected_reviews)[:reply_limit]
    if not reply_drafts:
        reply_drafts = fallback["reply_drafts"][:reply_limit]
    reply_drafts, safety_reasons = _guard_unverified_promises(reply_drafts, selected_reviews)
    summary = _clean_string_list(parsed.get("summary")) or fallback["summary"]
    if safety_reasons:
        summary = fallback["summary"]
    summary = [item for item in summary if not item.lower().startswith("подготовлено")]
    manual_review_reasons = _clean_string_list(parsed.get("manual_review_reasons")) or fallback["manual_review_reasons"]
    checklist = _clean_string_list(parsed.get("checklist")) or fallback["checklist"]
    rules_applied = _clean_string_list(parsed.get("rules_applied")) or fallback["rules_applied"]
    if safety_reasons:
        manual_review_reasons = fallback["manual_review_reasons"]
        checklist = fallback["checklist"]
        rules_applied = fallback["rules_applied"]
    return {
        "title": _clean_text(parsed.get("title")) or fallback["title"],
        "summary": [f"Подготовлено черновиков: {len(reply_drafts)}", *summary],
        "reply_drafts": reply_drafts,
        "manual_review_reasons": list(dict.fromkeys([*manual_review_reasons, *safety_reasons]))[:12],
        "checklist": checklist,
        "rules_applied": rules_applied,
        "feedback_notes": fallback.get("feedback_notes") or [],
        "format": fallback.get("format") or "Черновики ответов на отзывы",
    }


def _guard_unverified_promises(
    reply_drafts: List[Dict[str, str]],
    selected_reviews: List[Dict[str, Any]],
) -> tuple[List[Dict[str, str]], List[str]]:
    reviews_by_id = {
        _clean_text(review.get("review_id")): review
        for review in selected_reviews
        if _clean_text(review.get("review_id"))
    }
    guarded = []
    safety_reasons = []
    for draft in reply_drafts:
        source = reviews_by_id.get(_clean_text(draft.get("review_id")))
        if source is None:
            source = next(
                (
                    review
                    for review in selected_reviews
                    if _clean_text(review.get("author_name")) == _clean_text(draft.get("author_name"))
                ),
                {},
            )
        quality_reasons = _reply_quality_reasons(draft, source or draft)
        if not quality_reasons:
            guarded.append(draft)
            continue
        safe_draft = _fallback_reply(source or draft, "")
        safe_draft["manual_review_reason"] = " ".join(quality_reasons)
        guarded.append(safe_draft)
        safety_reasons.extend(quality_reasons)
    return guarded, list(dict.fromkeys(safety_reasons))


def _reply_quality_reasons(draft: Dict[str, str], source: Dict[str, Any]) -> List[str]:
    reply = _clean_text(draft.get("reply"))
    normalized_reply = reply.lower().replace("ё", "е")
    reasons = []
    if any(marker in normalized_reply for marker in UNVERIFIED_PROMISE_MARKERS):
        reasons.append(UNVERIFIED_PROMISE_REVIEW_REASON)
    if any(re.search(pattern, normalized_reply) for pattern in UNVERIFIED_INTERNAL_ACTION_PATTERNS):
        reasons.append(UNVERIFIED_PROMISE_REVIEW_REASON)
    if reply.endswith(("...", "…")):
        reasons.append(INCOMPLETE_REPLY_REVIEW_REASON)
    author_name = _clean_text(source.get("author_name"))
    if _is_anonymous_author(author_name) and re.match(
        r"^(?:добрый\s+(?:день|вечер)|здравствуйте|доброго\s+времени\s+суток)[,!]?\s+[А-ЯЁ][а-яё]{1,30}(?:[,.!]|$)",
        reply,
        flags=re.IGNORECASE,
    ):
        reasons.append(UNVERIFIED_NAME_REVIEW_REASON)
    return reasons


def _review_items(extracted_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    reviews = []
    for item in extracted_items:
        if _clean_text(item.get("source_name")).lower() not in REVIEW_SOURCE_NAMES:
            continue
        review = _review_from_item(item)
        if review["text"]:
            reviews.append(review)
    return reviews


def _review_from_item(item: Dict[str, Any]) -> Dict[str, Any]:
    raw = item.get("raw") if isinstance(item.get("raw"), dict) else {}
    text = _clean_text(raw.get("text")) or _clean_text(item.get("summary"))
    return {
        "source_name": _clean_text(item.get("source_name")) or "reviews",
        "review_id": _clean_text(raw.get("id")),
        "author_name": _clean_text(raw.get("author_name")),
        "rating": _clean_text(raw.get("rating")),
        "text": text,
        "response_text": _clean_text(raw.get("response_text")),
    }


def _selected_reviews(setup: Dict[str, Any], extracted_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    reviews = _review_items(extracted_items)
    if _requests_unanswered(setup):
        reviews = [review for review in reviews if not review.get("response_text")]
    return reviews[:_requested_reply_limit(setup)]


def _requests_unanswered(setup: Dict[str, Any]) -> bool:
    task = _clean_text(setup.get("run_request") or setup.get("workflow_description")).lower()
    return any(marker in task for marker in ("без ответа", "неотвеч", "нет ответа"))


def _requested_reply_limit(setup: Dict[str, Any]) -> int:
    task = _clean_text(setup.get("run_request") or setup.get("workflow_description")).lower()
    match = re.search(r"(?:выбер\w*|подготов\w*|ответ\w*)[^\d]{0,24}(\d{1,2})\s+отзыв", task)
    if match:
        return max(1, min(int(match.group(1)), 12))
    if re.search(r"\b(?:один|одну|одно)\s+отзыв", task) or "последний отзыв" in task:
        return 1
    return 12


def _anchor_reply_drafts(reply_drafts: List[Dict[str, str]], selected_reviews: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    by_id = {_clean_text(review.get("review_id")): review for review in selected_reviews if _clean_text(review.get("review_id"))}
    result = []
    for draft in reply_drafts:
        review_id = _clean_text(draft.get("review_id"))
        source = by_id.get(review_id)
        if source is None and len(selected_reviews) == 1 and not result:
            source = selected_reviews[0]
        if source is None:
            continue
        result.append(
            {
                **draft,
                "source_name": _clean_text(source.get("source_name")),
                "review_id": _clean_text(source.get("review_id")),
                "rating": _clean_text(source.get("rating")),
                "author_name": _clean_text(source.get("author_name")),
            }
        )
    return result


def _fallback_reply(review: Dict[str, Any], rules: str) -> Dict[str, str]:
    sentiment = _sentiment(review)
    author = _clean_text(review.get("author_name"))
    salutation = f"{author}, " if not _is_anonymous_author(author) else ""
    if sentiment == "negative":
        reply = (
            f"{salutation}Спасибо за обратную связь. Нам жаль, что опыт оказался не таким, как ожидалось. "
            "Если удобно, напишите нам напрямую дату визита и детали, чтобы мы могли проверить ситуацию."
        )
        reason = "Негативный отзыв требует ручной проверки перед публикацией."
    elif sentiment == "positive":
        reply = f"{salutation}Спасибо за тёплый отзыв. Нам очень приятно, что вы остались довольны."
        reason = "Проверить, что ответ соответствует стилю бренда."
    else:
        reply = f"{salutation}Спасибо за отзыв. Мы учтём вашу обратную связь в работе."
        reason = "Нейтральный отзыв: проверить контекст перед публикацией."
    if rules:
        reason = f"{reason} Правило: {rules[:120]}"
    return {
        "source_name": review.get("source_name") or "",
        "review_id": review.get("review_id") or "",
        "rating": review.get("rating") or "",
        "author_name": author,
        "sentiment": sentiment,
        "reply": reply,
        "manual_review_reason": reason,
    }


def _is_anonymous_author(author_name: str) -> bool:
    return _clean_text(author_name).lower() in ANONYMOUS_AUTHOR_NAMES


def _sentiment(review: Dict[str, Any]) -> str:
    rating_text = _clean_text(review.get("rating"))
    try:
        rating = float(rating_text.replace(",", "."))
    except Exception:
        rating = 0
    text = _clean_text(review.get("text")).lower()
    negative_markers = ("плохо", "ужас", "не понрав", "ждал", "проблем", "груб", "долго", "bad", "terrible")
    if rating and rating <= 3:
        return "negative"
    if any(marker in text for marker in negative_markers):
        return "negative"
    if rating >= 4:
        return "positive"
    return "neutral"


def _manual_review_reasons(replies: List[Dict[str, str]], rules: str) -> List[str]:
    reasons = [_clean_text(reply.get("manual_review_reason")) for reply in replies if _clean_text(reply.get("manual_review_reason"))]
    if rules:
        reasons.append(f"Проверить соблюдение правила: {rules[:160]}")
    return list(dict.fromkeys(reasons))[:12]


def _review_checklist(replies: List[Dict[str, str]], rules: str) -> List[str]:
    checklist = ["Проверить тон ответа", "Не публиковать без ручного подтверждения"]
    if any(reply.get("sentiment") == "negative" for reply in replies):
        checklist.append("Негативные отзывы проверить особенно внимательно")
    if rules:
        checklist.append("Проверить соблюдение ограничений агента")
    return checklist


def _clean_reply_drafts(value: Any) -> List[Dict[str, str]]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        if not isinstance(item, dict):
            continue
        reply = _clean_text(item.get("reply"))
        if not reply:
            continue
        result.append(
            {
                "source_name": _clean_text(item.get("source_name")),
                "review_id": _clean_text(item.get("review_id")),
                "rating": _clean_text(item.get("rating")),
                "author_name": _clean_text(item.get("author_name")),
                "sentiment": _clean_text(item.get("sentiment")) or "unknown",
                "reply": reply,
                "manual_review_reason": _clean_text(item.get("manual_review_reason")),
            }
        )
    return result[:12]


def _provenance(extracted_items: List[Dict[str, Any]]) -> List[str]:
    result = []
    for item in extracted_items:
        source_name = _clean_text(item.get("source_name"))
        if source_name:
            result.append(source_name)
    return list(dict.fromkeys(result))


def _clean_string_list(value: Any) -> List[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [_clean_text(item) for item in value if _clean_text(item)][:12]


def _clean_text(value: Any) -> str:
    return str(value or "").strip()
