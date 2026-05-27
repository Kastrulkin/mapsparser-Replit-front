from __future__ import annotations

import json
import sys
from typing import Any, Callable, Dict, List

from services.gigachat_client import analyze_text_with_gigachat


MAX_EMAIL_LLM_CONTEXT_CHARS = 10000
EMAIL_LLM_PROMPT_VERSION = "agent_email_draft_v1"


def draft_email_with_llm(
    setup: Dict[str, Any],
    extracted_items: List[Dict[str, Any]],
    feedback_history: List[Dict[str, Any]] | None = None,
    business_id: str = "",
    user_id: str = "",
    generator: Callable[..., str] | None = None,
) -> Dict[str, Any]:
    fallback = build_email_draft_fallback(setup, extracted_items, feedback_history or [])
    prompt = _build_email_prompt(setup, extracted_items, feedback_history or [])
    generate = generator or _default_email_generator
    try:
        raw_response = generate(prompt, business_id=business_id, user_id=user_id)
        parsed = _parse_llm_json(raw_response)
        normalized = _normalize_llm_email(parsed, fallback)
        normalized.update(
            {
                "analysis_source": "gigachat",
                "analysis_prompt_key": "agent_email_draft",
                "analysis_prompt_version": EMAIL_LLM_PROMPT_VERSION,
                "llm_analysis_used": True,
                "llm_error": "",
                "provenance": _provenance(extracted_items),
                "external_dispatch_performed": False,
                "delivery_state": "not_dispatched",
            }
        )
        return normalized
    except Exception:
        exc = sys.exc_info()[1]
        fallback.update(
            {
                "analysis_source": "deterministic_fallback",
                "analysis_prompt_key": "agent_email_draft",
                "analysis_prompt_version": EMAIL_LLM_PROMPT_VERSION,
                "llm_analysis_used": False,
                "llm_error": str(exc)[:240],
                "provenance": _provenance(extracted_items),
                "external_dispatch_performed": False,
                "delivery_state": "not_dispatched",
            }
        )
        return fallback


def build_email_draft_fallback(
    setup: Dict[str, Any],
    extracted_items: List[Dict[str, Any]],
    feedback_history: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    facts = [_clean_text(item.get("summary")) for item in extracted_items if _clean_text(item.get("summary"))]
    facts = facts[:8]
    rules = _clean_text(setup.get("processing_rules"))
    task = _clean_text(setup.get("workflow_description"))
    output_format = _clean_text(setup.get("output_format")) or "Черновик письма"
    feedback_notes = [
        _clean_text(item.get("feedback"))
        for item in (feedback_history or [])
        if isinstance(item, dict) and _clean_text(item.get("feedback"))
    ][-3:]
    return {
        "title": "Черновик письма",
        "subject": _fallback_subject(task, facts),
        "body": _fallback_body(task, facts, rules, feedback_notes),
        "checklist": _email_checklist(facts, rules),
        "assumptions": _email_assumptions(facts),
        "missing_info": _email_missing_info(task, facts),
        "rules_applied": [rules] if rules else [],
        "feedback_notes": feedback_notes,
        "format": output_format,
    }


def _default_email_generator(prompt: str, *, business_id: str = "", user_id: str = "") -> str:
    return analyze_text_with_gigachat(
        prompt,
        task_type="agent_email_draft",
        business_id=business_id or None,
        user_id=user_id or None,
    )


def _build_email_prompt(
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
        "sources": _email_context(extracted_items),
    }
    return (
        "Ты готовишь безопасный черновик письма для LocalOS agent blueprint. "
        "Используй только предоставленные источники, не придумывай факты и не выполняй отправку. "
        "Верни только JSON без markdown с полями: "
        "title, subject, body, checklist(list), assumptions(list), missing_info(list), rules_applied(list). "
        "Письмо должно быть готовым к ручной проверке человеком, но не должно обещать отправку.\n\n"
        f"INPUT_JSON:\n{json.dumps(payload, ensure_ascii=False)}"
    )


def _email_context(extracted_items: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    context = []
    used = 0
    for item in extracted_items:
        source_name = _clean_text(item.get("source_name")) or "Источник"
        raw = item.get("raw") if isinstance(item.get("raw"), dict) else {}
        text = _clean_text(raw.get("text")) or _clean_text(item.get("summary"))
        if not text:
            continue
        remaining = MAX_EMAIL_LLM_CONTEXT_CHARS - used
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


def _normalize_llm_email(parsed: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": _clean_text(parsed.get("title")) or fallback["title"],
        "subject": _clean_text(parsed.get("subject")) or fallback["subject"],
        "body": _clean_text(parsed.get("body")) or fallback["body"],
        "checklist": _clean_string_list(parsed.get("checklist")) or fallback["checklist"],
        "assumptions": _clean_string_list(parsed.get("assumptions")) or fallback["assumptions"],
        "missing_info": _clean_string_list(parsed.get("missing_info")) or fallback["missing_info"],
        "rules_applied": _clean_string_list(parsed.get("rules_applied")) or fallback["rules_applied"],
        "feedback_notes": fallback.get("feedback_notes") or [],
        "format": fallback.get("format") or "Черновик письма",
    }


def _fallback_subject(task: str, facts: List[str]) -> str:
    if "отзыв" in task.lower():
        return "Ответ по вашему обращению"
    if facts:
        first = facts[0].split(".")[0].strip()
        if first:
            return first[:90]
    return "Предложение по вашему запросу"


def _fallback_body(task: str, facts: List[str], rules: str, feedback_notes: List[str]) -> str:
    lines = ["Здравствуйте!", ""]
    if task:
        lines.append(f"Подготовили черновик по задаче: {task}.")
    else:
        lines.append("Подготовили черновик по вашему запросу.")
    if facts:
        lines.extend(["", "Ключевой контекст:"])
        lines.extend(f"- {item}" for item in facts[:4])
    if rules:
        lines.extend(["", f"Учтено правило: {rules}"])
    if feedback_notes:
        lines.extend(["", f"Учтена последняя правка: {feedback_notes[-1]}"])
    lines.extend(["", "Готовы уточнить детали и адаптировать текст перед отправкой."])
    return "\n".join(lines)


def _email_checklist(facts: List[str], rules: str) -> List[str]:
    checklist = ["Проверить адресата и канал отправки", "Проверить факты перед отправкой"]
    if facts:
        checklist.append("Сверить ключевой контекст с источниками")
    if rules:
        checklist.append("Проверить соблюдение заданных правил тона и ограничений")
    return checklist


def _email_assumptions(facts: List[str]) -> List[str]:
    if facts:
        return ["Черновик основан только на подключённых источниках."]
    return ["Контекста мало, текст требует ручного уточнения перед использованием."]


def _email_missing_info(task: str, facts: List[str]) -> List[str]:
    text = f"{task} {' '.join(facts)}".lower()
    missing = []
    if "кому" not in text and "адресат" not in text and "client" not in text:
        missing.append("Кто адресат письма?")
    if "цель" not in text and "предлож" not in text and "приглас" not in text:
        missing.append("Какое главное действие ожидается от получателя?")
    if "тон" not in text and "стиль" not in text:
        missing.append("Какой тон использовать?")
    return missing[:4]


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
