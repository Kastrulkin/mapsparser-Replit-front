from __future__ import annotations

from typing import Any, Dict, List

from services.agent_blueprint_draft_builder import compile_agent_blueprint, infer_blueprint_category
from services.agent_builder_billing import build_agent_creation_cost_preview


QUESTION_LIBRARY = {
    "communications": {
        "data": "Какие записи, услуги, пакеты и профиль бизнеса использовать для сообщения?",
        "extract": "Кому писать и за сколько до записи напоминать?",
        "output": "Нужны черновики, отчёт доставки и статусы реакции клиентов?",
    },
    "documents": {
        "data": "Какие документы или примеры результата использовать: файл, вставленный текст или источник LocalOS?",
        "extract": "Что нужно извлечь из документа: суммы, сроки, риски, поля, обязательства?",
        "output": "Какой результат подготовить: краткий отчёт, таблицу полей, письмо или список рисков?",
    },
    "email": {
        "data": "Какие данные использовать для письма: профиль бизнеса, шаблон, контекст клиента?",
        "extract": "Что обязательно должно попасть в письмо?",
        "output": "Нужен только черновик письма или ещё тема, чеклист и варианты тона?",
    },
    "tables": {
        "data": "Какую таблицу использовать: CSV, XLSX или вставленный текст?",
        "extract": "Какие исключения искать: пустые поля, суммы, статусы, дубликаты?",
        "output": "Какой отчёт нужен: список ошибок, summary или готовая таблица?",
    },
    "reviews": {
        "data": "Какие отзывы использовать: последние отзывы LocalOS или вставленный список?",
        "extract": "Какой стиль ответа нужен и какие темы нельзя обещать?",
        "output": "Нужны отдельные черновики ответов или общий план реакции?",
    },
    "outreach": {
        "data": "Где искать клиентов: город, категория, текущие prospectingleads или импорт?",
        "extract": "Какие лиды считать подходящими?",
        "output": "Что подготовить: shortlist, черновики сообщений или очередь отправки после approval?",
    },
    "custom": {
        "data": "Какие данные агент должен использовать?",
        "extract": "Что агент должен понять или извлечь?",
        "output": "Какой результат агент должен подготовить?",
    },
}


def build_agent_builder_state(messages: List[Dict[str, Any]], preferred_category: str = "") -> Dict[str, Any]:
    normalized_messages = _normalize_messages(messages)
    description = _conversation_text(normalized_messages)
    category = _clean_text(preferred_category) or infer_blueprint_category(description)
    draft = compile_agent_blueprint(description, category)
    preview = _build_preview(description, category, draft)
    questions = _missing_questions(description, category)
    assistant_message = _assistant_message(preview, questions)
    return {
        "messages": normalized_messages + [assistant_message],
        "category": category,
        "preview": preview,
        "missing_questions": questions,
        "compiler": {
            "name": "agent_compiler_v1",
            "status": "draft_compiled",
        },
    }


def append_user_message(messages: List[Dict[str, Any]], message: str) -> List[Dict[str, Any]]:
    normalized_messages = _normalize_messages(messages)
    text = _clean_text(message)
    if text:
        normalized_messages.append({"role": "user", "content": text})
    return normalized_messages


def preview_to_setup(preview: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "workflow_description": _clean_text(preview.get("understood_task")),
        "data_sources": preview.get("data_sources") if isinstance(preview.get("data_sources"), list) else [],
        "extraction_rules": _clean_text(preview.get("extraction_rules")),
        "processing_rules": _clean_text(preview.get("processing_rules")),
        "output_format": _clean_text(preview.get("output_format")),
        "approval_boundaries": ["final_output", "external_delivery"],
        "manual_control": _clean_text(preview.get("manual_control")) or "Итог проверяет человек перед внешним действием.",
    }


def _normalize_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result = []
    for item in messages:
        if not isinstance(item, dict):
            continue
        role = _clean_text(item.get("role")) or "user"
        content = _clean_text(item.get("content"))
        if role not in {"user", "assistant"} or not content:
            continue
        result.append({"role": role, "content": content})
    return result[-20:]


def _conversation_text(messages: List[Dict[str, Any]]) -> str:
    parts = []
    for item in messages:
        if item.get("role") == "user":
            parts.append(_clean_text(item.get("content")))
    return "\n".join([item for item in parts if item]).strip()


def _build_preview(description: str, category: str, draft: Dict[str, Any]) -> Dict[str, Any]:
    summary = draft.get("summary") if isinstance(draft.get("summary"), dict) else {}
    sources = summary.get("sources") if isinstance(summary.get("sources"), list) else []
    return {
        "understood_task": description or "Новый агент LocalOS",
        "category": category,
        "category_label": _category_label(category),
        "agent_name": draft.get("name") or _category_label(category),
        "data_sources": sources,
        "trigger": summary.get("trigger") or "",
        "audience": summary.get("audience") or "",
        "extraction_rules": _default_extraction_rules(category, description),
        "processing_rules": _default_processing_rules(category),
        "output_format": _default_output_format(category),
        "manual_control": "Ручное подтверждение перед финальным использованием и любым внешним действием.",
        "capability_allowlist": summary.get("capability_allowlist") if isinstance(summary.get("capability_allowlist"), list) else [],
        "limits": summary.get("limits") if isinstance(summary.get("limits"), dict) else {},
        "output_schema": summary.get("output_schema") if isinstance(summary.get("output_schema"), dict) else {},
        "approval_boundaries": summary.get("approval_boundaries") if isinstance(summary.get("approval_boundaries"), list) else ["final_output", "external_delivery"],
        "external_dispatch_performed": False,
        "cost_preview": build_agent_creation_cost_preview(),
        "compiler": "agent_compiler_v1",
    }


def _missing_questions(description: str, category: str) -> List[Dict[str, str]]:
    text = description.lower()
    library = QUESTION_LIBRARY.get(category) or QUESTION_LIBRARY["custom"]
    questions = []
    if len(description.strip()) < 24:
        questions.append({"key": "task", "question": "Опишите задачу агента чуть подробнее: что он должен делать каждый раз?"})
    if not _has_data_hint(text):
        questions.append({"key": "data", "question": library["data"]})
    if not _has_extraction_hint(text):
        questions.append({"key": "extract", "question": library["extract"]})
    if not _has_output_hint(text):
        questions.append({"key": "output", "question": library["output"]})
    if not _has_control_hint(text):
        questions.append({"key": "control", "question": "Где человек должен проверить результат перед действием?"})
    return questions[:3]


def _assistant_message(preview: Dict[str, Any], questions: List[Dict[str, str]]) -> Dict[str, Any]:
    if questions:
        question_text = " ".join([item["question"] for item in questions[:2]])
        content = f"Понял задачу как: {preview['understood_task']} Нужно уточнить: {question_text}"
    else:
        content = f"Понял задачу как: {preview['understood_task']} Данных достаточно, можно создать агента."
    return {"role": "assistant", "content": content}


def _has_data_hint(text: str) -> bool:
    return any(marker in text for marker in ["файл", "pdf", "docx", "xlsx", "csv", "отзыв", "профиль", "услуг", "лид", "контекст", "шаблон", "источник", "загруз", "запис", "пакет"])


def _has_extraction_hint(text: str) -> bool:
    return any(marker in text for marker in ["извлеч", "найд", "риск", "сумм", "срок", "пол", "исключ", "ответ", "подготов", "проверь", "напом", "клиент"])


def _has_output_hint(text: str) -> bool:
    return any(marker in text for marker in ["результ", "отчет", "отчёт", "письм", "таблиц", "summary", "список", "черновик", "shortlist", "сообщ"])


def _has_control_hint(text: str) -> bool:
    return any(marker in text for marker in ["руч", "провер", "подтверж", "approval", "перед отправ", "не отправ"])


def _default_extraction_rules(category: str, description: str) -> str:
    if category == "communications":
        return "Выбрать клиентов с ближайшей записью, проверить услугу, пакетное предложение и допустимость контакта."
    if category == "documents":
        return "Извлечь факты, суммы, сроки, риски, обязательства и отсутствующие поля."
    if category == "email":
        return "Понять адресата, цель письма, ключевые факты и ограничения тона."
    if category == "tables":
        return "Найти пустые поля, исключения, суммы, статусы и строки, требующие проверки."
    if category == "reviews":
        return "Определить тон отзыва, проблему клиента и безопасный черновик ответа."
    if category == "outreach":
        return "Собрать подходящих лидов, shortlist и черновики сообщений."
    return "Извлечь важные факты и недостающую информацию из данных агента."


def _default_processing_rules(category: str) -> str:
    if category == "communications":
        return "Подготовить черновики, проверить согласие, лимиты частоты и дневной лимит; не отправлять без approval."
    if category == "outreach":
        return "Не отправлять сообщения без approval; готовить только shortlist и черновики."
    return "Не придумывать факты; показывать, где данных не хватает; внешние действия не выполнять."


def _default_output_format(category: str) -> str:
    formats = {
        "communications": "Черновики сообщений, отчёт доставки и outcomes.",
        "documents": "Краткий разбор: summary, facts, fields, risks, next_questions.",
        "email": "Черновик письма: subject, body, checklist.",
        "tables": "Отчёт по таблице: summary, exceptions, rows_to_review.",
        "reviews": "Черновики ответов и причины ручной проверки.",
        "outreach": "Shortlist, черновики сообщений и approval gates.",
    }
    return formats.get(category, "Структурированный результат для review.")


def _category_label(category: str) -> str:
    labels = {
        "communications": "Агент коммуникаций",
        "documents": "Документный агент",
        "email": "Агент писем",
        "tables": "Агент таблиц",
        "reviews": "Агент отзывов",
        "outreach": "Агент поиска клиентов",
        "partnerships": "Агент партнёрств",
        "booking": "Агент бронирования",
        "services": "Агент услуг",
    }
    return labels.get(category, "Кастомный агент")


def _clean_text(value: Any) -> str:
    return str(value or "").strip()
