from __future__ import annotations

import json
import sys
from typing import Any, Callable, Dict, List

from services.gigachat_client import analyze_text_with_gigachat


MAX_DOCUMENT_LLM_CONTEXT_CHARS = 12000
DOCUMENT_LLM_PROMPT_VERSION = "agent_document_analysis_v1"


def analyze_document_sources_with_llm(
    setup: Dict[str, Any],
    extracted_items: List[Dict[str, Any]],
    feedback_history: List[Dict[str, Any]] | None = None,
    business_id: str = "",
    user_id: str = "",
    generator: Callable[..., str] | None = None,
) -> Dict[str, Any]:
    fallback = build_document_analysis_fallback(setup, extracted_items, feedback_history or [])
    prompt = _build_document_prompt(setup, extracted_items, feedback_history or [])
    generate = generator or _default_document_generator
    try:
        raw_response = generate(prompt, business_id=business_id, user_id=user_id)
        parsed = _parse_llm_json(raw_response)
        normalized = _normalize_llm_analysis(parsed, fallback)
        normalized.update(
            {
                "analysis_source": "gigachat",
                "analysis_prompt_key": "agent_document_analysis",
                "analysis_prompt_version": DOCUMENT_LLM_PROMPT_VERSION,
                "llm_analysis_used": True,
                "llm_error": "",
                "provenance": _provenance(extracted_items),
                "external_dispatch_performed": False,
            }
        )
        return normalized
    except Exception:
        exc = sys.exc_info()[1]
        fallback.update(
            {
                "analysis_source": "deterministic_fallback",
                "analysis_prompt_key": "agent_document_analysis",
                "analysis_prompt_version": DOCUMENT_LLM_PROMPT_VERSION,
                "llm_analysis_used": False,
                "llm_error": str(exc)[:240],
                "provenance": _provenance(extracted_items),
                "external_dispatch_performed": False,
            }
        )
        return fallback


def build_document_analysis_fallback(
    setup: Dict[str, Any],
    extracted_items: List[Dict[str, Any]],
    feedback_history: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    facts = [_clean_text(item.get("summary")) for item in extracted_items if _clean_text(item.get("summary"))]
    facts = facts[:8]
    rules = _clean_text(setup.get("processing_rules"))
    feedback_notes = [
        _clean_text(item.get("feedback"))
        for item in (feedback_history or [])
        if isinstance(item, dict) and _clean_text(item.get("feedback"))
    ][-3:]
    summary = facts[:4] or ["Недостаточно извлечённого текста для анализа."]
    return {
        "title": "Разбор документа",
        "summary": summary,
        "risks": _risk_hints(facts, rules),
        "facts": facts,
        "fields": _document_fields(facts),
        "next_questions": _document_next_questions(facts),
        "rules_applied": [rules] if rules else [],
        "feedback_notes": feedback_notes,
        "format": _clean_text(setup.get("output_format")) or "Краткий структурированный результат",
    }


def _default_document_generator(prompt: str, *, business_id: str = "", user_id: str = "") -> str:
    return analyze_text_with_gigachat(
        prompt,
        task_type="agent_document_analysis",
        business_id=business_id or None,
        user_id=user_id or None,
    )


def _build_document_prompt(
    setup: Dict[str, Any],
    extracted_items: List[Dict[str, Any]],
    feedback_history: List[Dict[str, Any]],
) -> str:
    context = _document_context(extracted_items)
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
        "sources": context,
    }
    return (
        "Ты анализируешь документы для LocalOS agent blueprint. "
        "Используй только предоставленные источники, не придумывай факты, не выполняй внешних действий. "
        "Верни только JSON без markdown с полями: "
        "title, summary(list), risks(list), facts(list), fields(object), next_questions(list), rules_applied(list). "
        "Если факт не найден, добавь вопрос в next_questions.\n\n"
        f"INPUT_JSON:\n{json.dumps(payload, ensure_ascii=False)}"
    )


def _document_context(extracted_items: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    context = []
    used = 0
    for item in extracted_items:
        source_name = _clean_text(item.get("source_name")) or "Источник"
        raw = item.get("raw") if isinstance(item.get("raw"), dict) else {}
        text = _clean_text(raw.get("text")) or _clean_text(item.get("summary"))
        if not text:
            continue
        remaining = MAX_DOCUMENT_LLM_CONTEXT_CHARS - used
        if remaining <= 0:
            break
        snippet = text[:remaining]
        used += len(snippet)
        context.append({"source_name": source_name, "text": snippet})
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


def _normalize_llm_analysis(parsed: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": _clean_text(parsed.get("title")) or fallback["title"],
        "summary": _clean_string_list(parsed.get("summary")) or fallback["summary"],
        "risks": _clean_string_list(parsed.get("risks")) or fallback["risks"],
        "facts": _clean_string_list(parsed.get("facts")) or fallback["facts"],
        "fields": _clean_string_dict(parsed.get("fields")) or fallback["fields"],
        "next_questions": _clean_string_list(parsed.get("next_questions")) or fallback["next_questions"],
        "rules_applied": _clean_string_list(parsed.get("rules_applied")) or fallback["rules_applied"],
        "feedback_notes": fallback.get("feedback_notes") or [],
        "format": fallback.get("format") or "Краткий структурированный результат",
    }


def _provenance(extracted_items: List[Dict[str, Any]]) -> List[str]:
    result = []
    for item in extracted_items:
        source_name = _clean_text(item.get("source_name"))
        if source_name:
            result.append(source_name)
    return list(dict.fromkeys(result))


def _risk_hints(facts: List[str], rules: str) -> List[str]:
    risks = []
    keywords = ("штраф", "срок", "ответствен", "неустой", "расторж", "персональн", "оплат", "penalty", "payment", "term")
    for fact in facts:
        lowered = fact.lower()
        for keyword in keywords:
            if keyword in lowered:
                risks.append(f"Проверьте условие: {fact[:180]}")
                break
    if rules:
        risks.append(f"Проверено по правилу: {rules[:180]}")
    return risks[:8]


def _document_fields(facts: List[str]) -> Dict[str, str]:
    fields: Dict[str, str] = {}
    labels = {
        "срок": "Сроки",
        "term": "Сроки",
        "оплат": "Оплата",
        "payment": "Оплата",
        "сумм": "Суммы",
        "штраф": "Штрафы",
        "penalty": "Штрафы",
        "ответствен": "Ответственность",
        "liability": "Ответственность",
        "расторж": "Расторжение",
        "персональн": "Персональные данные",
    }
    for fact in facts:
        lowered = fact.lower()
        for keyword, label in labels.items():
            if keyword in lowered and label not in fields:
                fields[label] = fact[:300]
    return fields


def _document_next_questions(facts: List[str]) -> List[str]:
    text = " ".join(facts).lower()
    questions = []
    if "подпис" not in text and "sign" not in text:
        questions.append("Кто подписывает документ и есть ли полномочия?")
    if "срок" not in text and "term" not in text:
        questions.append("Какие сроки исполнения или действия документа?")
    if "оплат" not in text and "сумм" not in text and "payment" not in text:
        questions.append("Какие суммы, порядок оплаты и условия возврата?")
    if "ответствен" not in text and "штраф" not in text and "liability" not in text and "penalty" not in text:
        questions.append("Какая ответственность сторон и что происходит при нарушении?")
    return questions[:4]


def _clean_string_list(value: Any) -> List[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [_clean_text(item) for item in value if _clean_text(item)][:12]


def _clean_string_dict(value: Any) -> Dict[str, str]:
    if not isinstance(value, dict):
        return {}
    result: Dict[str, str] = {}
    for key, item in value.items():
        clean_key = _clean_text(key)
        clean_value = _clean_text(item)
        if clean_key and clean_value:
            result[clean_key[:80]] = clean_value[:600]
    return result


def _clean_text(value: Any) -> str:
    return str(value or "").strip()
