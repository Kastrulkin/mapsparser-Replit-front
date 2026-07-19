from __future__ import annotations

import json
import sys
from typing import Any, Callable, Dict, List

from services.gigachat_client import analyze_text_with_gigachat


MAX_TABLE_LLM_CONTEXT_CHARS = 12000
TABLE_LLM_PROMPT_VERSION = "agent_table_analysis_v1"


def analyze_table_with_llm(
    setup: Dict[str, Any],
    extracted_items: List[Dict[str, Any]],
    feedback_history: List[Dict[str, Any]] | None = None,
    business_id: str = "",
    user_id: str = "",
    run_id: str = "",
    generator: Callable[..., str] | None = None,
) -> Dict[str, Any]:
    fallback = build_table_analysis_fallback(setup, extracted_items, feedback_history or [])
    prompt = _build_table_prompt(setup, extracted_items, feedback_history or [])
    try:
        raw_response = (
            generator(prompt, business_id=business_id, user_id=user_id)
            if generator
            else _default_table_generator(prompt, business_id=business_id, user_id=user_id, run_id=run_id)
        )
        parsed = _parse_llm_json(raw_response)
        normalized = _normalize_llm_table(parsed, fallback)
        normalized.update(
            {
                "analysis_source": "gigachat",
                "analysis_prompt_key": "agent_table_analysis",
                "analysis_prompt_version": TABLE_LLM_PROMPT_VERSION,
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
                "analysis_prompt_key": "agent_table_analysis",
                "analysis_prompt_version": TABLE_LLM_PROMPT_VERSION,
                "llm_analysis_used": False,
                "llm_error": str(exc)[:240],
                "provenance": _provenance(extracted_items),
                "external_dispatch_performed": False,
                "delivery_state": "not_dispatched",
            }
        )
        return fallback


def build_table_analysis_fallback(
    setup: Dict[str, Any],
    extracted_items: List[Dict[str, Any]],
    feedback_history: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    rows = _table_rows(extracted_items)
    exceptions = _fallback_exceptions(rows)
    rows_to_review = _rows_to_review(rows, exceptions)
    rules = _clean_text(setup.get("processing_rules"))
    feedback_notes = [
        _clean_text(item.get("feedback"))
        for item in (feedback_history or [])
        if isinstance(item, dict) and _clean_text(item.get("feedback"))
    ][-3:]
    return {
        "title": "Отчёт по таблице",
        "summary": _fallback_summary(rows, exceptions),
        "exceptions": exceptions,
        "rows_to_review": rows_to_review,
        "recommendations": _recommendations(exceptions, rules),
        "rules_applied": [rules] if rules else [],
        "feedback_notes": feedback_notes,
        "format": _clean_text(setup.get("output_format")) or "Отчёт по исключениям",
    }


def _default_table_generator(prompt: str, *, business_id: str = "", user_id: str = "", run_id: str = "") -> str:
    return analyze_text_with_gigachat(
        prompt,
        task_type="agent_table_analysis",
        business_id=business_id or None,
        user_id=user_id or None,
        usage_reference=f"agent-run:{run_id}" if run_id else None,
    )


def _build_table_prompt(
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
        "sources": _table_context(extracted_items),
    }
    return (
        "Ты анализируешь таблицу для LocalOS agent blueprint. "
        "Используй только предоставленные строки, не придумывай факты и не выполняй внешних действий. "
        "Верни только JSON без markdown с полями: "
        "title, summary(list), exceptions(list), rows_to_review(list), recommendations(list), rules_applied(list). "
        "rows_to_review должны быть объектами с row, reason, source_name, values.\n\n"
        f"INPUT_JSON:\n{json.dumps(payload, ensure_ascii=False)}"
    )


def _table_context(extracted_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    context = []
    used = 0
    for index, item in enumerate(extracted_items[:50], start=1):
        source_name = _clean_text(item.get("source_name")) or "Источник"
        raw = item.get("raw") if isinstance(item.get("raw"), dict) else {}
        if raw:
            text = json.dumps(raw, ensure_ascii=False)
        else:
            text = _clean_text(item.get("summary"))
        if not text:
            continue
        remaining = MAX_TABLE_LLM_CONTEXT_CHARS - used
        if remaining <= 0:
            break
        snippet = text[:remaining]
        used += len(snippet)
        context.append({"row": index, "source_name": source_name, "values": snippet})
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


def _normalize_llm_table(parsed: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": _clean_text(parsed.get("title")) or fallback["title"],
        "summary": _clean_string_list(parsed.get("summary")) or fallback["summary"],
        "exceptions": _clean_string_list(parsed.get("exceptions")) or fallback["exceptions"],
        "rows_to_review": _clean_rows_to_review(parsed.get("rows_to_review")) or fallback["rows_to_review"],
        "recommendations": _clean_string_list(parsed.get("recommendations")) or fallback["recommendations"],
        "rules_applied": _clean_string_list(parsed.get("rules_applied")) or fallback["rules_applied"],
        "feedback_notes": fallback.get("feedback_notes") or [],
        "format": fallback.get("format") or "Отчёт по исключениям",
    }


def _table_rows(extracted_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for index, item in enumerate(extracted_items, start=1):
        raw = item.get("raw") if isinstance(item.get("raw"), dict) else {}
        rows.append(
            {
                "row": index,
                "source_name": _clean_text(item.get("source_name")) or "Источник",
                "summary": _clean_text(item.get("summary")),
                "values": {str(key): _clean_text(value) for key, value in raw.items()},
            }
        )
    return rows


def _fallback_summary(rows: List[Dict[str, Any]], exceptions: List[str]) -> List[str]:
    return [
        f"Проверено строк: {len(rows)}",
        f"Найдено исключений: {len(exceptions)}",
    ]


def _fallback_exceptions(rows: List[Dict[str, Any]]) -> List[str]:
    exceptions = []
    seen_rows: Dict[str, int] = {}
    for row in rows:
        values = row.get("values") if isinstance(row.get("values"), dict) else {}
        empty_keys = [key for key, value in values.items() if not _clean_text(value)]
        if empty_keys:
            exceptions.append(f"Строка {row.get('row')}: пустые поля {', '.join(empty_keys[:4])}")
        duplicate_key = _duplicate_key(values)
        if duplicate_key:
            if duplicate_key in seen_rows:
                exceptions.append(f"Строка {row.get('row')}: возможный дубль строки {seen_rows[duplicate_key]}")
            else:
                seen_rows[duplicate_key] = int(row.get("row") or 0)
    if not exceptions and rows:
        exceptions.append("Критичных исключений по базовым правилам не найдено.")
    if not rows:
        exceptions.append("Нет строк для анализа.")
    return exceptions[:12]


def _rows_to_review(rows: List[Dict[str, Any]], exceptions: List[str]) -> List[Dict[str, Any]]:
    result = []
    for exception in exceptions:
        row_number = _extract_row_number(exception)
        if not row_number:
            continue
        row = next((item for item in rows if item.get("row") == row_number), {})
        result.append(
            {
                "row": row_number,
                "reason": exception,
                "source_name": row.get("source_name") or "",
                "values": row.get("values") if isinstance(row.get("values"), dict) else {},
            }
        )
    return result[:12]


def _recommendations(exceptions: List[str], rules: str) -> List[str]:
    result = []
    if any("пустые поля" in item for item in exceptions):
        result.append("Заполнить пустые обязательные поля перед использованием таблицы.")
    if any("дубль" in item for item in exceptions):
        result.append("Проверить возможные дубликаты и оставить одну актуальную строку.")
    if rules:
        result.append(f"Проверить результат по правилу: {rules[:180]}")
    if not result:
        result.append("Проверить выборочно 2-3 строки перед финальным использованием.")
    return result[:8]


def _duplicate_key(values: Dict[str, str]) -> str:
    for key in ("email", "phone", "телефон", "почта", "id", "name", "название"):
        value = _clean_text(values.get(key))
        if value:
            return f"{key}:{value.lower()}"
    return ""


def _extract_row_number(text: str) -> int:
    parts = text.replace(":", " ").split()
    for index, part in enumerate(parts):
        if part.lower() == "строка" and index + 1 < len(parts):
            try:
                return int(parts[index + 1])
            except Exception:
                return 0
    return 0


def _clean_rows_to_review(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        if not isinstance(item, dict):
            continue
        row_number = 0
        try:
            row_number = int(item.get("row") or 0)
        except Exception:
            row_number = 0
        result.append(
            {
                "row": row_number,
                "reason": _clean_text(item.get("reason")),
                "source_name": _clean_text(item.get("source_name")),
                "values": item.get("values") if isinstance(item.get("values"), dict) else {},
            }
        )
    return [item for item in result if item["row"] or item["reason"]][:12]


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
