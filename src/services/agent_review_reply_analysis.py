from __future__ import annotations

import json
import sys
from typing import Any, Callable, Dict, List

from services.gigachat_client import analyze_text_with_gigachat


MAX_REVIEW_LLM_CONTEXT_CHARS = 12000
REVIEW_LLM_PROMPT_VERSION = "agent_review_replies_v1"


def draft_review_replies_with_llm(
    setup: Dict[str, Any],
    extracted_items: List[Dict[str, Any]],
    feedback_history: List[Dict[str, Any]] | None = None,
    business_id: str = "",
    user_id: str = "",
    run_id: str = "",
    generator: Callable[..., str] | None = None,
) -> Dict[str, Any]:
    fallback = build_review_replies_fallback(setup, extracted_items, feedback_history or [])
    prompt = _build_review_prompt(setup, extracted_items, feedback_history or [])
    try:
        raw_response = (
            generator(prompt, business_id=business_id, user_id=user_id)
            if generator
            else _default_review_generator(prompt, business_id=business_id, user_id=user_id, run_id=run_id)
        )
        parsed = _parse_llm_json(raw_response)
        normalized = _normalize_llm_review_replies(parsed, fallback)
        normalized.update(
            {
                "analysis_source": "gigachat",
                "analysis_prompt_key": "agent_review_replies",
                "analysis_prompt_version": REVIEW_LLM_PROMPT_VERSION,
                "llm_analysis_used": True,
                "llm_error": "",
                "provenance": _provenance(extracted_items),
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
                "provenance": _provenance(extracted_items),
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
    reviews = _review_items(extracted_items)
    rules = _clean_text(setup.get("processing_rules"))
    feedback_notes = [
        _clean_text(item.get("feedback"))
        for item in (feedback_history or [])
        if isinstance(item, dict) and _clean_text(item.get("feedback"))
    ][-3:]
    replies = [_fallback_reply(review, rules) for review in reviews[:12]]
    if not replies:
        replies = [
            {
                "source_name": "manual_context",
                "review_id": "",
                "rating": "",
                "author_name": "",
                "sentiment": "unknown",
                "reply": "Спасибо за отзыв. Мы учтём обратную связь и улучшим сервис.",
                "manual_review_reason": "Нет текста отзыва для точного ответа.",
            }
        ]
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
    extracted_items: List[Dict[str, Any]],
    feedback_history: List[Dict[str, Any]],
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
        "reviews": _review_context(extracted_items),
    }
    return (
        "Ты готовишь безопасные черновики ответов на отзывы для LocalOS agent blueprint. "
        "Используй только предоставленные отзывы, не обещай компенсации/скидки без данных, не публикуй ответ. "
        "Верни только JSON без markdown с полями: "
        "title, summary(list), reply_drafts(list), manual_review_reasons(list), checklist(list), rules_applied(list). "
        "reply_drafts должны быть объектами: review_id, author_name, rating, sentiment, reply, manual_review_reason.\n\n"
        f"INPUT_JSON:\n{json.dumps(payload, ensure_ascii=False)}"
    )


def _review_context(extracted_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    context = []
    used = 0
    for item in extracted_items[:30]:
        review = _review_from_item(item)
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


def _normalize_llm_review_replies(parsed: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": _clean_text(parsed.get("title")) or fallback["title"],
        "summary": _clean_string_list(parsed.get("summary")) or fallback["summary"],
        "reply_drafts": _clean_reply_drafts(parsed.get("reply_drafts")) or fallback["reply_drafts"],
        "manual_review_reasons": _clean_string_list(parsed.get("manual_review_reasons")) or fallback["manual_review_reasons"],
        "checklist": _clean_string_list(parsed.get("checklist")) or fallback["checklist"],
        "rules_applied": _clean_string_list(parsed.get("rules_applied")) or fallback["rules_applied"],
        "feedback_notes": fallback.get("feedback_notes") or [],
        "format": fallback.get("format") or "Черновики ответов на отзывы",
    }


def _review_items(extracted_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [_review_from_item(item) for item in extracted_items if _review_from_item(item)["text"]]


def _review_from_item(item: Dict[str, Any]) -> Dict[str, Any]:
    raw = item.get("raw") if isinstance(item.get("raw"), dict) else {}
    text = _clean_text(raw.get("text")) or _clean_text(item.get("summary"))
    return {
        "source_name": _clean_text(item.get("source_name")) or "reviews",
        "review_id": _clean_text(raw.get("id")),
        "author_name": _clean_text(raw.get("author_name")),
        "rating": _clean_text(raw.get("rating")),
        "text": text,
    }


def _fallback_reply(review: Dict[str, Any], rules: str) -> Dict[str, str]:
    sentiment = _sentiment(review)
    author = review.get("author_name") or "клиент"
    if sentiment == "negative":
        reply = (
            f"{author}, спасибо за обратную связь. Нам жаль, что опыт оказался не таким, как ожидалось. "
            "Мы внимательно разберём ситуацию и свяжемся с командой, чтобы улучшить сервис."
        )
        reason = "Негативный отзыв требует ручной проверки перед публикацией."
    elif sentiment == "positive":
        reply = f"{author}, спасибо за тёплый отзыв. Нам очень приятно, что вы остались довольны."
        reason = "Проверить, что ответ соответствует стилю бренда."
    else:
        reply = f"{author}, спасибо за отзыв. Мы учтём вашу обратную связь в работе."
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
