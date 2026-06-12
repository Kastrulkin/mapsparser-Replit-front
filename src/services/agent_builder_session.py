from __future__ import annotations

from typing import Any, Dict, List

from services.agent_blueprint_draft_builder import compile_agent_blueprint, infer_blueprint_category
from services.agent_builder_billing import build_agent_creation_cost_preview
from services.agent_feasibility_resolver import resolve_agent_feasibility
from services.agent_openclaw_planner_context import build_openclaw_planner_context
from services.agent_openclaw_planner_loop import build_openclaw_planner_loop
from services.agent_provider_registry import capability_provider_candidates, integration_provider_catalog


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


def build_agent_builder_state(
    messages: List[Dict[str, Any]],
    preferred_category: str = "",
    *,
    use_ai: bool = False,
    business_id: str = "",
    user_id: str = "",
    connected_integrations: List[Dict[str, Any]] | None = None,
    subscription: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    normalized_messages = _normalize_messages(messages)
    description = _conversation_text(normalized_messages)
    category = _clean_text(preferred_category) or infer_blueprint_category(description)
    draft = compile_agent_blueprint(
        description,
        category,
        use_ai=False,
        business_id=business_id,
        user_id=user_id,
    )
    preview = _build_preview(
        description,
        category,
        draft,
        connected_integrations=connected_integrations or [],
        subscription=subscription or {},
    )
    planner_context = build_openclaw_planner_context(
        description=description,
        category=category,
        preview=preview,
        business_id=business_id,
        user_id=user_id,
    )
    if use_ai:
        draft = compile_agent_blueprint(
            description,
            category,
            use_ai=True,
            business_id=business_id,
            user_id=user_id,
            planner_context=planner_context,
        )
        preview = _build_preview(
            description,
            category,
            draft,
            connected_integrations=connected_integrations or [],
            subscription=subscription or {},
        )
        planner_context = build_openclaw_planner_context(
            description=description,
            category=category,
            preview=preview,
            business_id=business_id,
            user_id=user_id,
        )
    planner_loop = build_openclaw_planner_loop(planner_context)
    preview["openclaw_planner_context"] = planner_context
    preview["openclaw_planner_loop"] = planner_loop
    compiler_questions = _compiler_questions(draft)
    preview["compiler_questions"] = compiler_questions
    resolver_questions = _connection_resolver_questions(preview)
    preview["connection_resolver_questions"] = resolver_questions
    questions = _merge_questions(_missing_questions(description, category), compiler_questions, planner_loop, resolver_questions)
    preview["setup_flow"] = _build_setup_flow(preview, questions)
    assistant_message = _assistant_message(preview, questions)
    return {
        "messages": normalized_messages + [assistant_message],
        "category": category,
        "preview": preview,
        "missing_questions": questions,
        "compiler": {
            "name": "agent_compiler_v1",
            "status": "draft_compiled",
            "openclaw_planner_context": planner_context,
            "openclaw_planner_loop": planner_loop,
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
        "setup_flow": preview.get("setup_flow") if isinstance(preview.get("setup_flow"), dict) else {},
        "compiler_questions": preview.get("compiler_questions") if isinstance(preview.get("compiler_questions"), list) else [],
        "compiler_policy_review": preview.get("compiler_policy_review") if isinstance(preview.get("compiler_policy_review"), dict) else {},
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


def _build_preview(
    description: str,
    category: str,
    draft: Dict[str, Any],
    *,
    connected_integrations: List[Dict[str, Any]],
    subscription: Dict[str, Any],
) -> Dict[str, Any]:
    summary = draft.get("summary") if isinstance(draft.get("summary"), dict) else {}
    sources = summary.get("sources") if isinstance(summary.get("sources"), list) else []
    metadata = draft.get("metadata") if isinstance(draft.get("metadata"), dict) else {}
    version_payload = draft.get("version_payload") if isinstance(draft.get("version_payload"), dict) else {}
    capability_allowlist = summary.get("capability_allowlist") if isinstance(summary.get("capability_allowlist"), list) else []
    if not capability_allowlist:
        capability_allowlist = version_payload.get("capability_allowlist") if isinstance(version_payload.get("capability_allowlist"), list) else []
    required_bindings = metadata.get("required_integration_bindings") if isinstance(metadata.get("required_integration_bindings"), list) else []
    if not required_bindings:
        required_bindings = version_payload.get("required_integration_bindings") if isinstance(version_payload.get("required_integration_bindings"), list) else []
    compiler_review = _compiler_policy_review(metadata)
    feasibility = resolve_agent_feasibility(
        description=description,
        required_capabilities=[str(item) for item in capability_allowlist],
        required_bindings=[item for item in required_bindings if isinstance(item, dict)],
        connected_integrations=connected_integrations,
        subscription=subscription,
    )
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
        "capability_allowlist": capability_allowlist,
        "required_integration_bindings": required_bindings,
        "feasibility": feasibility,
        "compiler_workflow_draft": compiler_review["workflow_draft"],
        "compiler_approval_points": compiler_review["approval_points"],
        "compiler_unsupported_requests": compiler_review["unsupported_requests"],
        "compiler_policy_review": compiler_review,
        "connector_intelligence": _build_connector_intelligence(feasibility),
        "required_connectors": _connector_preview_items(feasibility),
        "connection_plan": _build_preview_connection_plan(feasibility),
        "connection_readiness": _build_connection_readiness(feasibility),
        "connection_resolver": _build_connection_resolver(feasibility),
        "connection_summary": _build_connection_summary(feasibility),
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


def _compiler_questions(draft: Dict[str, Any]) -> List[Dict[str, str]]:
    metadata = draft.get("metadata") if isinstance(draft.get("metadata"), dict) else {}
    llm_intent = metadata.get("llm_intent") if isinstance(metadata.get("llm_intent"), dict) else {}
    intent = llm_intent.get("intent") if isinstance(llm_intent.get("intent"), dict) else {}
    raw_questions = intent.get("clarifying_questions") if isinstance(intent.get("clarifying_questions"), list) else []
    result: List[Dict[str, str]] = []
    for index, question in enumerate(raw_questions):
        clean = _clean_text(question)
        if clean:
            result.append(
                {
                    "key": f"compiler_question_{index + 1}",
                    "question": clean,
                    "reason": "compiled_intent_clarification",
                }
            )
    return result[:3]


def _compiler_policy_review(metadata: Dict[str, Any]) -> Dict[str, Any]:
    llm_intent = metadata.get("llm_intent") if isinstance(metadata.get("llm_intent"), dict) else {}
    intent = llm_intent.get("intent") if isinstance(llm_intent.get("intent"), dict) else {}
    workflow_draft = intent.get("workflow_draft") if isinstance(intent.get("workflow_draft"), dict) else {}
    approval_points = intent.get("approval_points") if isinstance(intent.get("approval_points"), list) else []
    unsupported_requests = intent.get("unsupported_requests") if isinstance(intent.get("unsupported_requests"), list) else []
    clean_approval_points = [item for item in approval_points if isinstance(item, dict)][:8]
    clean_unsupported = [item for item in unsupported_requests if isinstance(item, dict)][:8]
    return {
        "schema": "localos_agent_compiler_policy_review_v1",
        "source": str(llm_intent.get("source") or ""),
        "status": "blocked" if clean_unsupported else ("needs_approval" if clean_approval_points else "ok"),
        "workflow_draft": workflow_draft,
        "approval_points": clean_approval_points,
        "unsupported_requests": clean_unsupported,
    }


def _connection_resolver_questions(preview: Dict[str, Any]) -> List[Dict[str, str]]:
    resolver = preview.get("connection_resolver") if isinstance(preview.get("connection_resolver"), dict) else {}
    items = resolver.get("items") if isinstance(resolver.get("items"), list) else []
    result: List[Dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        state = str(item.get("state") or "").strip()
        if state in {"ready", "native_ready"}:
            continue
        question = _connection_resolver_question_text(item)
        if not question:
            continue
        provider = str(item.get("provider") or "").strip()
        key = _connection_resolver_question_key(item)
        result.append(
            {
                "key": key,
                "question": question,
                "reason": "connection_resolver",
                "provider": provider,
                "role": str(item.get("role") or ""),
            }
        )
    return result[:3]


def _connection_resolver_question_key(item: Dict[str, Any]) -> str:
    provider = str(item.get("provider") or "").strip()
    role = str(item.get("role") or "").strip()
    if provider == "google_sheets":
        return "google_sheets_target"
    if provider == "telegram":
        return "telegram_destination"
    if provider == "localos_finance":
        return "localos_finance_target"
    if provider == "maton":
        return "maton_key"
    clean_provider = provider or str(item.get("key") or "service").strip()
    return f"connection_{clean_provider}_{role or 'service'}"


def _connection_resolver_question_text(item: Dict[str, Any]) -> str:
    provider = str(item.get("provider") or "").strip()
    service = str(item.get("service_label") or provider or "сервис").strip()
    role_label = str(item.get("role_label") or "шаг агента").strip()
    state = str(item.get("state") or "").strip()
    recommended = str(item.get("recommended_label") or item.get("recommended_provider") or "").strip()
    if state == "choose_existing":
        return f"Какой сохранённый доступ {service} использовать для роли «{role_label}»?"
    if provider == "google_sheets":
        return "Какую Google таблицу и вкладку использовать как источник данных?"
    if provider == "telegram":
        return "В какой Telegram-канал, чат или бот готовить результат?"
    if provider == "localos_finance":
        return "В какой раздел финансов LocalOS записывать результат и какие поля обязательны?"
    if recommended:
        return f"Используем {recommended} как способ подключения для {service} в роли «{role_label}»?"
    return f"Как подключить {service} для роли «{role_label}»?"


def _merge_questions(
    local_questions: List[Dict[str, str]],
    compiler_questions: List[Dict[str, str]],
    planner_loop: Dict[str, Any],
    resolver_questions: List[Dict[str, str]] | None = None,
) -> List[Dict[str, str]]:
    result: List[Dict[str, str]] = []
    seen = set()
    seen_questions = set()
    resolver_questions = resolver_questions if isinstance(resolver_questions, list) else []
    for item in compiler_questions + resolver_questions + local_questions:
        key = str(item.get("key") or item.get("question") or "").strip()
        question = str(item.get("question") or "").strip()
        question_key = question.lower()
        if not key or key in seen or (question_key and question_key in seen_questions):
            continue
        seen.add(key)
        if question_key:
            seen_questions.add(question_key)
        result.append(item)
    planner_questions = planner_loop.get("clarifying_questions") if isinstance(planner_loop.get("clarifying_questions"), list) else []
    for item in planner_questions:
        if not isinstance(item, dict):
            continue
        reason = str(item.get("reason") or "").strip()
        if reason in {"required_connection_missing", "required_connection_missing_config", "multiple_connections_available"}:
            continue
        key = str(item.get("key") or item.get("question") or "").strip()
        question = str(item.get("question") or "").strip()
        question_key = question.lower()
        if not key or not question or key in seen or question_key in seen_questions:
            continue
        seen.add(key)
        seen_questions.add(question_key)
        result.append(
            {
                "key": key,
                "question": question,
            }
        )
    return result[:5]


def _assistant_message(preview: Dict[str, Any], questions: List[Dict[str, str]]) -> Dict[str, Any]:
    feasibility = preview.get("feasibility") if isinstance(preview.get("feasibility"), dict) else {}
    feasibility_status = str(feasibility.get("status") or "")
    missing_connections = feasibility.get("missing_connections") if isinstance(feasibility.get("missing_connections"), list) else []
    connection_choices = feasibility.get("connection_choices") if isinstance(feasibility.get("connection_choices"), list) else []
    compiler_review = preview.get("compiler_policy_review") if isinstance(preview.get("compiler_policy_review"), dict) else {}
    compiler_unsupported = compiler_review.get("unsupported_requests") if isinstance(compiler_review.get("unsupported_requests"), list) else []
    if compiler_unsupported:
        reason = str(compiler_unsupported[0].get("reason") or compiler_unsupported[0].get("request") or "часть запроса выходит за policy envelope")
        content = f"Понял задачу как: {preview['understood_task']} Но такой агент нельзя создать без изменения логики: {reason}"
    elif feasibility_status == "forbidden":
        content = f"Понял задачу как: {preview['understood_task']} Но такой агент не может быть создан в рамках политики LocalOS."
    elif questions:
        question_text = " ".join([item["question"] for item in questions[:2]])
        content = f"Понял задачу как: {preview['understood_task']} Нужно уточнить: {question_text}"
        if missing_connections:
            names = ", ".join([str(item.get("provider_title") or item.get("provider") or "") for item in missing_connections[:3]])
            content = f"{content} Для запуска также нужно подключить: {names}."
        elif connection_choices:
            names = ", ".join([str(item.get("provider_title") or item.get("provider") or "") for item in connection_choices[:3]])
            content = f"{content} Ещё нужно выбрать, какой доступ использовать: {names}."
    elif missing_connections:
        names = ", ".join([str(item.get("provider_title") or item.get("provider") or "") for item in missing_connections[:3]])
        content = f"Понял задачу как: {preview['understood_task']} Для запуска нужно подключить: {names}."
    elif connection_choices:
        names = ", ".join([str(item.get("provider_title") or item.get("provider") or "") for item in connection_choices[:3]])
        content = f"Понял задачу как: {preview['understood_task']} Нужно выбрать, какой доступ использовать: {names}."
    else:
        content = f"Понял задачу как: {preview['understood_task']} Данных достаточно, можно создать агента."
    return {"role": "assistant", "content": content}


def _build_setup_flow(preview: Dict[str, Any], questions: List[Dict[str, str]]) -> Dict[str, Any]:
    feasibility = preview.get("feasibility") if isinstance(preview.get("feasibility"), dict) else {}
    status = str(feasibility.get("status") or "ready")
    missing_connections = feasibility.get("missing_connections") if isinstance(feasibility.get("missing_connections"), list) else []
    connection_choices = feasibility.get("connection_choices") if isinstance(feasibility.get("connection_choices"), list) else []
    unsupported = feasibility.get("unsupported") if isinstance(feasibility.get("unsupported"), list) else []
    forbidden = feasibility.get("forbidden") if isinstance(feasibility.get("forbidden"), list) else []
    compiler_review = preview.get("compiler_policy_review") if isinstance(preview.get("compiler_policy_review"), dict) else {}
    compiler_unsupported = compiler_review.get("unsupported_requests") if isinstance(compiler_review.get("unsupported_requests"), list) else []
    compiler_blocked = bool(compiler_unsupported)
    can_create_draft = not questions and status not in {"forbidden", "unsupported", "needs_payment"} and not compiler_blocked
    can_run_preview = can_create_draft and status == "ready"
    can_activate = False
    next_step = "cannot_create" if compiler_blocked else _setup_next_step(status, questions, missing_connections, connection_choices)
    post_create_status = _post_create_status(status, missing_connections, connection_choices)
    return {
        "schema": "localos_agent_builder_setup_flow_v1",
        "status": "blocked" if compiler_blocked else _setup_flow_status(status, questions),
        "primary_action": "cannot_create" if compiler_blocked else _setup_primary_action(status, questions, missing_connections, connection_choices),
        "next_step": next_step,
        "next_step_title": _setup_next_step_title(next_step),
        "next_step_description": _setup_next_step_description(next_step, missing_connections, connection_choices),
        "can_create_draft": can_create_draft,
        "can_run_preview": can_run_preview,
        "can_activate": can_activate,
        "post_create_status": post_create_status,
        "post_create_next_step": _post_create_next_step(post_create_status),
        "post_create_description": _post_create_description(post_create_status, missing_connections, connection_choices),
        "activation_blockers": _activation_blockers(status, questions, missing_connections, connection_choices, forbidden, unsupported, compiler_unsupported),
        "steps": [
            {
                "key": "understand",
                "label": "Понять задачу",
                "status": "done" if _clean_text(preview.get("understood_task")) else "active",
                "description": "LocalOS превращает описание в черновик workflow.",
            },
            {
                "key": "clarify",
                "label": "Уточнить детали",
                "status": "active" if questions else "done",
                "description": questions[0]["question"] if questions else "Деталей достаточно для первой версии.",
                "questions": questions,
            },
            {
                "key": "connect",
                "label": "Подключить сервисы",
                "status": _connector_step_status(questions, missing_connections, connection_choices),
                "description": _connector_step_description(missing_connections, connection_choices),
                "missing_connections": missing_connections,
                "connection_choices": connection_choices,
            },
            {
                "key": "policy",
                "label": "Проверить ограничения",
                "status": "blocked" if forbidden or unsupported or compiler_blocked else "done",
                "description": _policy_step_description(status),
                "forbidden": forbidden,
                "unsupported": unsupported,
                "compiler_unsupported": compiler_unsupported,
            },
            {
                "key": "create",
                "label": "Создать draft",
                "status": "ready" if can_create_draft else "blocked",
                "description": _create_step_description(can_create_draft, post_create_status),
            },
            {
                "key": "preview",
                "label": "Preview run",
                "status": "next" if can_create_draft and post_create_status == "ready_for_preview" else "blocked",
                "description": "Следующий шаг после draft: проверить агента без внешних действий." if can_create_draft else "Сначала создайте draft агента.",
            },
            {
                "key": "activate",
                "label": "Активировать",
                "status": "blocked",
                "description": "Активация станет доступна после preflight, preview run, limits и approval policy.",
            },
        ],
    }


def _setup_next_step(
    feasibility_status: str,
    questions: List[Dict[str, str]],
    missing_connections: List[Dict[str, Any]],
    connection_choices: List[Dict[str, Any]],
) -> str:
    if feasibility_status in {"forbidden", "unsupported"}:
        return "cannot_create"
    if questions:
        return "answer_clarification"
    if feasibility_status == "needs_payment":
        return "top_up_balance"
    if connection_choices:
        return "create_draft_then_choose_connection"
    if missing_connections:
        return "create_draft_then_connect"
    return "create_draft_then_preview"


def _setup_next_step_title(next_step: str) -> str:
    labels = {
        "answer_clarification": "Ответьте на уточнение",
        "create_draft_then_connect": "Создайте draft, затем подключите сервисы",
        "create_draft_then_choose_connection": "Создайте draft, затем выберите доступ",
        "create_draft_then_preview": "Создайте draft и проверьте preview run",
        "top_up_balance": "Пополните баланс",
        "cannot_create": "Такой агент недоступен",
    }
    return labels.get(next_step, "Проверьте настройку")


def _setup_next_step_description(
    next_step: str,
    missing_connections: List[Dict[str, Any]],
    connection_choices: List[Dict[str, Any]],
) -> str:
    if next_step == "answer_clarification":
        return "LocalOS ещё не знает достаточно деталей, чтобы собрать проверяемый workflow."
    if next_step == "create_draft_then_connect":
        names = ", ".join([str(item.get("provider_title") or item.get("provider") or "") for item in missing_connections[:3]])
        return f"Draft можно создать сейчас. После создания откроем подключения: {names or 'обязательные сервисы'}."
    if next_step == "create_draft_then_choose_connection":
        names = ", ".join([str(item.get("provider_title") or item.get("provider") or "") for item in connection_choices[:3]])
        return f"Draft можно создать сейчас. После создания выберите, какой доступ использовать: {names or 'подключение'}."
    if next_step == "create_draft_then_preview":
        return "Подключения выглядят готовыми. После создания откроем preview run: он проверит workflow без внешних действий."
    if next_step == "top_up_balance":
        return "Создание или первый запуск упирается в лимиты подписки или кредиты."
    if next_step == "cannot_create":
        return "Запрос выходит за LocalOS policy envelope или не имеет разрешённого provider path."
    return "Проверьте задачу, подключения и policy."


def _post_create_status(
    feasibility_status: str,
    missing_connections: List[Dict[str, Any]],
    connection_choices: List[Dict[str, Any]],
) -> str:
    if feasibility_status in {"forbidden", "unsupported", "needs_payment"}:
        return "blocked"
    if connection_choices:
        return "needs_connection_choice"
    if missing_connections:
        return "needs_connection"
    return "ready_for_preview"


def _post_create_next_step(post_create_status: str) -> str:
    values = {
        "needs_connection": "connect_required_integrations",
        "needs_connection_choice": "choose_existing_connection",
        "ready_for_preview": "run_preview",
        "blocked": "review_blockers",
    }
    return values.get(post_create_status, "review_blockers")


def _post_create_description(
    post_create_status: str,
    missing_connections: List[Dict[str, Any]],
    connection_choices: List[Dict[str, Any]],
) -> str:
    if post_create_status == "ready_for_preview":
        return "После создания откроем preview run. Он покажет входные данные, шаги, artifacts и approval gate без внешних действий."
    if post_create_status == "needs_connection_choice":
        names = ", ".join([str(item.get("provider_title") or item.get("provider") or "") for item in connection_choices[:3]])
        return f"После создания нужно выбрать существующий доступ: {names or 'подключение'}."
    if post_create_status == "needs_connection":
        names = ", ".join([str(item.get("provider_title") or item.get("provider") or "") for item in missing_connections[:3]])
        return f"После создания нужно подключить: {names or 'обязательные сервисы'}."
    return "Перед продолжением нужно разобраться с блокерами."


def _create_step_description(can_create_draft: bool, post_create_status: str) -> str:
    if not can_create_draft:
        return "Сначала завершите обязательные шаги выше."
    if post_create_status == "ready_for_preview":
        return "Создаст draft агента и откроет preview run перед активацией."
    if post_create_status in {"needs_connection", "needs_connection_choice"}:
        return "Создаст draft агента и откроет подключение обязательных сервисов."
    return "Создаст draft агента, но продолжение зависит от блокеров."


def _connector_step_status(
    questions: List[Dict[str, str]],
    missing_connections: List[Dict[str, Any]],
    connection_choices: List[Dict[str, Any]],
) -> str:
    if missing_connections or connection_choices:
        return "blocked" if questions else "active"
    return "done"


def _connector_step_description(missing_connections: List[Dict[str, Any]], connection_choices: List[Dict[str, Any]]) -> str:
    if missing_connections:
        names = ", ".join([str(item.get("provider_title") or item.get("provider") or "") for item in missing_connections[:3]])
        return f"Нужно подключить: {names}."
    if connection_choices:
        names = ", ".join([str(item.get("provider_title") or item.get("provider") or "") for item in connection_choices[:3]])
        return f"Нужно выбрать доступ: {names}."
    return "Обязательные подключения готовы или будут проверены на preflight."


def _policy_step_description(feasibility_status: str) -> str:
    if feasibility_status == "forbidden":
        return "Запрос запрещён политикой LocalOS."
    if feasibility_status == "unsupported":
        return "Нет разрешённого provider path для нужного действия."
    if feasibility_status == "needs_payment":
        return "Создание или запуск упирается в оплату/кредиты."
    return "Workflow остаётся внутри LocalOS policy envelope."


def _setup_flow_status(feasibility_status: str, questions: List[Dict[str, str]]) -> str:
    if feasibility_status in {"forbidden", "unsupported"}:
        return "blocked"
    if questions:
        return "needs_clarification"
    if feasibility_status in {"needs_connection", "needs_choice", "needs_payment"}:
        return feasibility_status
    return "ready_for_draft"


def _setup_primary_action(
    feasibility_status: str,
    questions: List[Dict[str, str]],
    missing_connections: List[Dict[str, Any]],
    connection_choices: List[Dict[str, Any]],
) -> str:
    if feasibility_status in {"forbidden", "unsupported"}:
        return "cannot_create"
    if questions:
        return "answer_question"
    if connection_choices:
        return "choose_connection"
    if missing_connections:
        return "connect_service"
    if feasibility_status == "needs_payment":
        return "top_up_balance"
    return "create_draft"


def _activation_blockers(
    feasibility_status: str,
    questions: List[Dict[str, str]],
    missing_connections: List[Dict[str, Any]],
    connection_choices: List[Dict[str, Any]],
    forbidden: List[Dict[str, Any]],
    unsupported: List[Dict[str, Any]],
    compiler_unsupported: List[Dict[str, Any]] | None = None,
) -> List[Dict[str, str]]:
    blockers: List[Dict[str, str]] = []
    if questions:
        blockers.append({"type": "clarification", "message": "Ответьте на уточняющие вопросы перед созданием draft."})
    for item in missing_connections:
        blockers.append(
            {
                "type": "connection",
                "provider": str(item.get("provider") or ""),
                "message": str(item.get("provider_title") or item.get("provider") or "Нужно подключение"),
            }
        )
    for item in connection_choices:
        blockers.append(
            {
                "type": "choice",
                "provider": str(item.get("provider") or ""),
                "message": str(item.get("provider_title") or item.get("provider") or "Нужно выбрать подключение"),
            }
        )
    for item in forbidden:
        blockers.append({"type": "forbidden", "message": str(item.get("reason") or "Запрещено политикой LocalOS.")})
    for item in unsupported:
        blockers.append({"type": "unsupported", "message": str(item.get("reason") or "Нет разрешённого provider path.")})
    for item in compiler_unsupported or []:
        if isinstance(item, dict):
            blockers.append(
                {
                    "type": "compiler_unsupported",
                    "message": str(item.get("reason") or item.get("message") or item.get("request") or "Compiler считает часть запроса неподдерживаемой."),
                }
            )
    if feasibility_status == "needs_payment":
        blockers.append({"type": "billing", "message": "Недостаточно доступного баланса или подписки."})
    return blockers


def _connector_preview_items(feasibility: Dict[str, Any]) -> List[Dict[str, Any]]:
    bindings = feasibility.get("bindings") if isinstance(feasibility.get("bindings"), list) else []
    result = []
    for item in bindings:
        if not isinstance(item, dict):
            continue
        result.append(
            {
                "key": str(item.get("key") or ""),
                "provider": str(item.get("provider") or ""),
                "title": str(item.get("provider_title") or item.get("provider") or ""),
                "status": str(item.get("status") or ""),
                "connection_count": item.get("connection_count") if isinstance(item.get("connection_count"), int) else 0,
                "missing_config": item.get("missing_config") if isinstance(item.get("missing_config"), list) else [],
                "connections": item.get("connections") if isinstance(item.get("connections"), list) else [],
                "action": _connector_action(item),
            }
        )
    return result


def _build_preview_connection_plan(feasibility: Dict[str, Any]) -> Dict[str, Any]:
    bindings = feasibility.get("bindings") if isinstance(feasibility.get("bindings"), list) else []
    catalog_by_provider = {
        str(item.get("provider") or "").strip(): item
        for item in integration_provider_catalog()
        if isinstance(item, dict) and str(item.get("provider") or "").strip()
    }
    items = []
    for binding in bindings:
        if not isinstance(binding, dict):
            continue
        provider = str(binding.get("provider") or "").strip()
        catalog_item = catalog_by_provider.get(provider, {})
        action = _preview_connection_action(binding, catalog_item)
        provider_routes = _provider_routes(binding.get("provider_routes"))
        recommended_route = _recommended_provider_route(provider_routes, action, provider)
        items.append(
            {
                "key": str(binding.get("key") or provider or ""),
                "provider": provider,
                "title": str(binding.get("provider_title") or catalog_item.get("title") or provider),
                "capability": str(binding.get("capability") or ""),
                "trigger": str(binding.get("trigger") or ""),
                "direction": str(binding.get("direction") or ""),
                "binding_status": str(binding.get("status") or ""),
                "action": action,
                "primary_label": _preview_connection_label(action),
                "explanation": _preview_connection_explanation(binding, action),
                "route_state": str(binding.get("route_state") or ""),
                "route_summary": str(binding.get("route_summary") or ""),
                "provider_routes": provider_routes,
                "recommended_route": recommended_route,
                "recommended_route_reason": _recommended_provider_route_reason(recommended_route, action, provider),
                "missing_config": binding.get("missing_config") if isinstance(binding.get("missing_config"), list) else [],
                "approval_required": bool(binding.get("approval_required", True)),
                "existing_integrations": binding.get("connections") if isinstance(binding.get("connections"), list) else [],
                "attached_integrations": binding.get("connections") if str(binding.get("status") or "") == "ready" and isinstance(binding.get("connections"), list) else [],
                "provider_paths": _preview_provider_paths(catalog_item),
            }
        )
    missing_count = len([item for item in items if item.get("action") not in {"ready", "native_ready"}])
    return {
        "schema": "localos_agent_connection_plan_v1",
        "status": "ready" if missing_count == 0 else "needs_action",
        "missing_count": missing_count,
        "items": items,
    }


def _build_connector_intelligence(feasibility: Dict[str, Any]) -> Dict[str, Any]:
    bindings = feasibility.get("bindings") if isinstance(feasibility.get("bindings"), list) else []
    capabilities = feasibility.get("capabilities") if isinstance(feasibility.get("capabilities"), list) else []
    forbidden = feasibility.get("forbidden") if isinstance(feasibility.get("forbidden"), list) else []
    unsupported = feasibility.get("unsupported") if isinstance(feasibility.get("unsupported"), list) else []
    status = str(feasibility.get("status") or "ready")
    binding_items = [_connector_intelligence_binding(item) for item in bindings if isinstance(item, dict)]
    capability_items = [_connector_intelligence_capability(item) for item in capabilities if isinstance(item, dict)]
    return {
        "schema": "localos_agent_connector_intelligence_v1",
        "status": status,
        "headline": _connector_intelligence_headline(status, binding_items, forbidden, unsupported),
        "can_compile_draft": status not in {"forbidden", "unsupported", "needs_payment"},
        "can_preview_after_connections": status == "ready",
        "next_action": str(feasibility.get("next_action") or ""),
        "bindings": binding_items,
        "capabilities": capability_items,
        "provider_paths": _connector_intelligence_provider_paths(binding_items, capability_items),
        "forbidden": forbidden,
        "unsupported": unsupported,
    }


def _build_connection_summary(feasibility: Dict[str, Any]) -> Dict[str, Any]:
    bindings = feasibility.get("bindings") if isinstance(feasibility.get("bindings"), list) else []
    forbidden = feasibility.get("forbidden") if isinstance(feasibility.get("forbidden"), list) else []
    unsupported = feasibility.get("unsupported") if isinstance(feasibility.get("unsupported"), list) else []
    status = str(feasibility.get("status") or "ready")
    items = [_connection_summary_item(item) for item in bindings if isinstance(item, dict)]
    missing_count = len([item for item in items if item.get("action") == "connect_required"])
    choice_count = len([item for item in items if item.get("action") == "choose_existing"])
    ready_count = len([item for item in items if item.get("action") in {"ready", "native_ready"}])
    blocked_count = len([item for item in items if item.get("action") == "planned_provider"]) + len(forbidden) + len(unsupported)
    next_action = _connection_summary_next_action(status, missing_count, choice_count, blocked_count)
    return {
        "schema": "localos_agent_connection_summary_v1",
        "status": status,
        "headline": _connection_summary_headline(status, missing_count, choice_count, ready_count, blocked_count),
        "next_action": next_action,
        "next_action_label": _connection_summary_next_action_label(next_action),
        "ready_count": ready_count,
        "missing_count": missing_count,
        "choice_count": choice_count,
        "blocked_count": blocked_count,
        "items": items,
        "forbidden": forbidden,
        "unsupported": unsupported,
    }


def _build_connection_readiness(feasibility: Dict[str, Any]) -> Dict[str, Any]:
    bindings = feasibility.get("bindings") if isinstance(feasibility.get("bindings"), list) else []
    forbidden = feasibility.get("forbidden") if isinstance(feasibility.get("forbidden"), list) else []
    unsupported = feasibility.get("unsupported") if isinstance(feasibility.get("unsupported"), list) else []
    status = str(feasibility.get("status") or "ready")
    services = [_connection_readiness_service(item) for item in bindings if isinstance(item, dict)]
    missing = [item for item in services if item.get("action") == "connect_required"]
    choices = [item for item in services if item.get("action") == "choose_existing"]
    ready = [item for item in services if item.get("action") in {"ready", "native_ready"}]
    blocked = [item for item in services if item.get("action") == "planned_provider"]
    next_action = _connection_readiness_next_action(status, missing, choices, blocked, forbidden, unsupported)
    return {
        "schema": "localos_agent_connection_readiness_v1",
        "status": status,
        "next_action": next_action,
        "title": _connection_readiness_title(next_action, missing, choices, ready, blocked, forbidden, unsupported),
        "description": _connection_readiness_description(next_action, missing, choices, ready, blocked, forbidden, unsupported),
        "required_count": len(services),
        "ready_count": len(ready),
        "missing_count": len(missing),
        "choice_count": len(choices),
        "blocked_count": len(blocked) + len(forbidden) + len(unsupported),
        "can_create_draft": status not in {"forbidden", "unsupported", "needs_payment"},
        "can_run_preview_after_create": status == "ready",
        "post_create_workspace": _connection_readiness_post_create_workspace(next_action),
        "services": services,
        "ready_services": ready,
        "missing_services": missing,
        "choice_services": choices,
        "blocked_services": blocked,
        "forbidden": forbidden,
        "unsupported": unsupported,
    }


def _build_connection_resolver(feasibility: Dict[str, Any]) -> Dict[str, Any]:
    bindings = feasibility.get("bindings") if isinstance(feasibility.get("bindings"), list) else []
    forbidden = feasibility.get("forbidden") if isinstance(feasibility.get("forbidden"), list) else []
    unsupported = feasibility.get("unsupported") if isinstance(feasibility.get("unsupported"), list) else []
    status = str(feasibility.get("status") or "ready")
    items = [_connection_resolver_item(item) for item in bindings if isinstance(item, dict)]
    unresolved = [
        item
        for item in items
        if str(item.get("state") or "") not in {"ready", "native_ready"}
    ]
    blocked = [
        item
        for item in items
        if str(item.get("state") or "") in {"planned_provider", "unsupported", "forbidden"}
    ]
    next_action = _connection_resolver_next_action(status, unresolved, blocked, forbidden, unsupported)
    return {
        "schema": "localos_agent_connection_resolver_v1",
        "status": status,
        "title": _connection_resolver_title(items, unresolved, blocked, forbidden, unsupported),
        "summary": _connection_resolver_summary(items, unresolved, blocked, forbidden, unsupported),
        "next_action": next_action,
        "next_action_label": _connection_resolver_next_action_label(next_action),
        "can_continue": status not in {"forbidden", "unsupported", "needs_payment"} and not blocked,
        "required_count": len(items),
        "resolved_count": len(items) - len(unresolved),
        "unresolved_count": len(unresolved),
        "blocked_count": len(blocked) + len(forbidden) + len(unsupported),
        "items": items,
        "forbidden": forbidden,
        "unsupported": unsupported,
    }


def _connection_resolver_item(binding: Dict[str, Any]) -> Dict[str, Any]:
    provider = str(binding.get("provider") or "").strip()
    catalog_item = _catalog_item_by_provider(provider)
    action = _preview_connection_action(binding, catalog_item)
    provider_routes = _provider_routes(binding.get("provider_routes"))
    route = _recommended_provider_route(provider_routes, action, provider)
    connections = binding.get("connections") if isinstance(binding.get("connections"), list) else []
    state = _connection_resolver_state(action, route)
    return {
        "key": str(binding.get("key") or provider or ""),
        "role": _connection_resolver_role(binding),
        "role_label": _connection_resolver_role_label(binding),
        "provider": provider,
        "service_label": str(binding.get("provider_title") or catalog_item.get("title") or provider),
        "capability": str(binding.get("capability") or ""),
        "direction": str(binding.get("direction") or ""),
        "state": state,
        "state_label": _connection_resolver_state_label(state),
        "recommended_provider": str(route.get("provider") or ""),
        "recommended_label": str(route.get("label") or route.get("provider") or ""),
        "recommended_cta": str(route.get("primary_cta") or ""),
        "connect_mode": str(route.get("connect_mode") or ""),
        "explanation": _connection_resolver_explanation(binding, action, route, connections),
        "resolution_hint": _connection_resolver_resolution_hint(binding, action, route, connections),
        "connection_count": len(connections),
        "connections": connections[:5],
        "missing_config": binding.get("missing_config") if isinstance(binding.get("missing_config"), list) else [],
        "provider_routes": provider_routes,
        "recommended_route": route,
    }


def _connection_resolver_role(binding: Dict[str, Any]) -> str:
    direction = str(binding.get("direction") or "").strip()
    capability = str(binding.get("capability") or "").strip()
    provider = str(binding.get("provider") or "").strip()
    if direction == "read" or capability.endswith(".read") or ".read_" in capability:
        return "source"
    if direction == "write" and provider.startswith("localos"):
        return "localos_record"
    if direction == "write" or "communications." in capability or "send" in capability or "draft" in capability:
        return "destination"
    if provider in {"business_profile", "localos_finance"}:
        return "localos_data"
    return "service"


def _connection_resolver_role_label(binding: Dict[str, Any]) -> str:
    role = _connection_resolver_role(binding)
    labels = {
        "source": "Источник данных",
        "destination": "Куда подготовить результат",
        "localos_record": "Запись в LocalOS",
        "localos_data": "Данные LocalOS",
        "service": "Сервис",
    }
    return labels.get(role, "Сервис")


def _connection_resolver_state(action: str, route: Dict[str, str]) -> str:
    if action in {"ready", "native_ready"}:
        return action
    route_state = str(route.get("state") or route.get("status") or "").strip()
    if action == "choose_existing":
        return "choose_existing"
    if action == "planned_provider" or route_state == "planned":
        return "planned_provider"
    if route_state in {"available", "manual", "connected"}:
        return "available"
    return "connect_required"


def _connection_resolver_state_label(state: str) -> str:
    labels = {
        "ready": "Уже подключено",
        "native_ready": "Уже есть в LocalOS",
        "choose_existing": "Нужно выбрать доступ",
        "available": "Можно подключить",
        "connect_required": "Нужно подключить",
        "planned_provider": "Пока недоступно",
        "unsupported": "Не поддерживается",
        "forbidden": "Запрещено policy",
    }
    return labels.get(state, "Проверить")


def _connection_resolver_explanation(
    binding: Dict[str, Any],
    action: str,
    route: Dict[str, str],
    connections: List[Dict[str, Any]],
) -> str:
    service = str(binding.get("provider_title") or binding.get("provider") or "сервис")
    route_provider = str(route.get("provider") or "").strip()
    if action in {"ready", "native_ready"}:
        if connections:
            return f"{service} уже подключён к бизнесу и может быть выбран для агента."
        return f"{service} доступен внутри LocalOS без внешнего ключа."
    if action == "choose_existing":
        return f"Найдено несколько доступов {service}. Выберите, какой использовать в плане агента."
    if route_provider == "openclaw":
        return f"{service} можно выполнить через OpenClaw boundary под правилами LocalOS."
    if route_provider == "maton":
        return f"{service} можно подключить через Maton.ai key, если у бизнеса сохранён такой доступ."
    if route_provider == "manual":
        return f"{service} можно оставить ручным шагом: LocalOS подготовит результат, человек выполнит внешнее действие."
    if route_provider == "native_localos":
        return f"{service} доступен как нативный домен LocalOS."
    if route_provider == "composio":
        return f"{service} есть как будущий OAuth route через Composio, но пока не активирует агента."
    return f"Для {service} нужен разрешённый способ подключения."


def _connection_resolver_resolution_hint(
    binding: Dict[str, Any],
    action: str,
    route: Dict[str, str],
    connections: List[Dict[str, Any]],
) -> str:
    if action in {"ready", "native_ready"}:
        return "Можно переходить к safe preview после создания агента."
    if action == "choose_existing":
        return "Выберите один из существующих доступов перед созданием агента."
    route_provider = str(route.get("provider") or "").strip()
    if route_provider == "openclaw":
        return "Выберите OpenClaw как способ выполнения и подтвердите подключения."
    if route_provider == "maton":
        return "Выберите сохранённый Maton.ai key или добавьте его в интеграциях."
    if route_provider == "manual":
        return "Агент останется draft-only до ручного внешнего действия."
    if route_provider == "native_localos":
        return "Дополнительный внешний доступ не нужен."
    if route_provider == "composio":
        return "Пока нельзя активировать через этот путь; можно вернуться позже."
    if connections:
        return "Проверьте настройки сохранённого доступа."
    return "Подключите сервис или выберите доступный provider route."


def _connection_resolver_next_action(
    status: str,
    unresolved: List[Dict[str, Any]],
    blocked: List[Dict[str, Any]],
    forbidden: List[Dict[str, Any]],
    unsupported: List[Dict[str, Any]],
) -> str:
    if status in {"forbidden", "unsupported"} or blocked or forbidden or unsupported:
        return "blocked"
    if status == "needs_payment":
        return "top_up_balance"
    if unresolved:
        return "resolve_connections"
    return "run_safe_preview"


def _connection_resolver_next_action_label(next_action: str) -> str:
    labels = {
        "blocked": "Нельзя активировать",
        "top_up_balance": "Пополнить баланс",
        "resolve_connections": "Выбрать подключения",
        "run_safe_preview": "Перейти к safe preview",
    }
    return labels.get(next_action, "Проверить подключения")


def _connection_resolver_title(
    items: List[Dict[str, Any]],
    unresolved: List[Dict[str, Any]],
    blocked: List[Dict[str, Any]],
    forbidden: List[Dict[str, Any]],
    unsupported: List[Dict[str, Any]],
) -> str:
    if blocked or forbidden or unsupported:
        return "Часть подключений недоступна"
    if unresolved:
        return "Нужно выбрать подключения"
    if items:
        return "Подключения понятны"
    return "Внешние подключения не нужны"


def _connection_resolver_summary(
    items: List[Dict[str, Any]],
    unresolved: List[Dict[str, Any]],
    blocked: List[Dict[str, Any]],
    forbidden: List[Dict[str, Any]],
    unsupported: List[Dict[str, Any]],
) -> str:
    if blocked or forbidden or unsupported:
        return "LocalOS покажет, какие части задачи нельзя выполнить через разрешённые provider paths."
    if unresolved:
        names = ", ".join([str(item.get("service_label") or item.get("provider") or "") for item in unresolved[:3]])
        return f"Перед созданием агента выберите способ подключения для: {names}."
    if items:
        return "Все нужные сервисы сопоставлены с безопасными способами выполнения."
    return "Агент использует только данные и действия внутри LocalOS."


def _connection_readiness_service(binding: Dict[str, Any]) -> Dict[str, Any]:
    provider = str(binding.get("provider") or "").strip()
    catalog_item = _catalog_item_by_provider(provider)
    action = _preview_connection_action(binding, catalog_item)
    connections = binding.get("connections") if isinstance(binding.get("connections"), list) else []
    provider_routes = _provider_routes(binding.get("provider_routes"))
    route = _recommended_provider_route(provider_routes, action, provider)
    return {
        "key": str(binding.get("key") or provider or ""),
        "provider": provider,
        "title": str(binding.get("provider_title") or catalog_item.get("title") or provider),
        "capability": str(binding.get("capability") or ""),
        "action": action,
        "action_label": _preview_connection_label(action),
        "status": str(binding.get("status") or ""),
        "route_state": str(binding.get("route_state") or ""),
        "route_summary": str(binding.get("route_summary") or ""),
        "explanation": _preview_connection_explanation(binding, action),
        "provider_route_label": str(route.get("label") or ""),
        "provider_route_cta": str(route.get("primary_cta") or ""),
        "recommended_route": route,
        "recommended_route_reason": _recommended_provider_route_reason(route, action, provider),
        "connect_mode": str(route.get("connect_mode") or ""),
        "connections": connections[:5],
        "connection_count": len(connections),
        "missing_config": binding.get("missing_config") if isinstance(binding.get("missing_config"), list) else [],
        "setup_cta": _preview_connection_setup_cta(binding, action),
    }


def _recommended_provider_route(routes: List[Dict[str, str]], action: str, provider: str) -> Dict[str, str]:
    if not routes:
        return {}
    provider_key = str(provider or "").strip()
    action_key = str(action or "").strip()
    if action_key in {"ready", "native_ready"}:
        for route in routes:
            if str(route.get("state") or route.get("status") or "") == "connected":
                return route
    preferred_providers = ["openclaw", "maton", "native_localos", "manual", "composio"]
    if provider_key in {"localos_finance", "business_profile"} or action_key == "native_ready":
        preferred_providers = ["native_localos", "openclaw", "manual", "maton", "composio"]
    for candidate in preferred_providers:
        for route in routes:
            state = str(route.get("state") or route.get("status") or "")
            if str(route.get("provider") or "") == candidate and state in {"available", "connected", "manual"}:
                return route
    for state in ["connected", "available", "manual", "planned"]:
        for route in routes:
            if str(route.get("state") or route.get("status") or "") == state:
                return route
    return routes[0] if routes else {}


def _recommended_provider_route_reason(route: Dict[str, str], action: str, provider: str) -> str:
    route_provider = str(route.get("provider") or "").strip()
    if not route_provider:
        return ""
    if route_provider == "openclaw":
        return "Рекомендуем OpenClaw: он даёт planner/execution boundary, а LocalOS держит policy, billing, audit и approvals."
    if route_provider == "maton":
        return "Рекомендуем Maton, если нужен сохранённый API key для connector bridge внутри LocalOS policy."
    if route_provider == "native_localos":
        return "Рекомендуем нативный маршрут LocalOS для доменных данных и действий, которые уже живут внутри продукта."
    if route_provider == "manual":
        return "Ручной fallback подходит для draft-only режима: LocalOS подготовит результат, внешний шаг выполнит человек."
    if route_provider == "composio":
        return "Composio пока planned route: можно показать будущий OAuth path, но не активировать агента через него."
    return f"Provider route {route_provider} будет проверен через LocalOS preflight."


def _connection_readiness_next_action(
    status: str,
    missing: List[Dict[str, Any]],
    choices: List[Dict[str, Any]],
    blocked: List[Dict[str, Any]],
    forbidden: List[Dict[str, Any]],
    unsupported: List[Dict[str, Any]],
) -> str:
    if status in {"forbidden", "unsupported"} or blocked or forbidden or unsupported:
        return "blocked_by_policy_or_provider"
    if status == "needs_payment":
        return "top_up_balance"
    if choices:
        return "choose_existing_connections"
    if missing:
        return "connect_missing_services"
    return "create_draft_then_preview"


def _connection_readiness_post_create_workspace(next_action: str) -> str:
    if next_action in {"choose_existing_connections", "connect_missing_services"}:
        return "connections"
    if next_action == "create_draft_then_preview":
        return "run"
    return "settings"


def _connection_readiness_title(
    next_action: str,
    missing: List[Dict[str, Any]],
    choices: List[Dict[str, Any]],
    ready: List[Dict[str, Any]],
    blocked: List[Dict[str, Any]],
    forbidden: List[Dict[str, Any]],
    unsupported: List[Dict[str, Any]],
) -> str:
    if next_action == "blocked_by_policy_or_provider":
        return "Этот workflow нельзя активировать через доступные provider paths"
    if next_action == "top_up_balance":
        return "Перед созданием нужен доступный баланс"
    if next_action == "choose_existing_connections":
        return f"Нужно выбрать подключение: {len(choices)}"
    if next_action == "connect_missing_services":
        return f"Нужно подключить сервисы: {len(missing)}"
    if ready:
        return f"Все подключения готовы: {len(ready)}"
    if not missing and not choices and not blocked and not forbidden and not unsupported:
        return "Внешние подключения не требуются"
    return "Проверьте подключения агента"


def _connection_readiness_description(
    next_action: str,
    missing: List[Dict[str, Any]],
    choices: List[Dict[str, Any]],
    ready: List[Dict[str, Any]],
    blocked: List[Dict[str, Any]],
    forbidden: List[Dict[str, Any]],
    unsupported: List[Dict[str, Any]],
) -> str:
    if next_action == "blocked_by_policy_or_provider":
        reasons = [str(item.get("reason") or item.get("capability") or item.get("term") or "") for item in forbidden + unsupported]
        if not reasons and blocked:
            reasons = [str(item.get("title") or item.get("provider") or "") for item in blocked]
        return ". ".join([item for item in reasons if item][:2]) or "Нет разрешённого provider route внутри LocalOS policy envelope."
    if next_action == "top_up_balance":
        return "LocalOS не начнёт compiled workflow, пока лимиты подписки или кредиты не позволяют создать агента."
    if next_action == "choose_existing_connections":
        names = ", ".join([str(item.get("title") or item.get("provider") or "") for item in choices[:3]])
        return f"Найдены несколько подходящих доступов. Выберите, какой использовать для: {names}."
    if next_action == "connect_missing_services":
        names = ", ".join([str(item.get("title") or item.get("provider") or "") for item in missing[:3]])
        return f"Draft можно создать, но preview и активация будут заблокированы, пока не подключены: {names}."
    if ready:
        names = ", ".join([str(item.get("title") or item.get("provider") or "") for item in ready[:3]])
        return f"После создания LocalOS откроет safe preview run. Готовые доступы: {names}."
    return "LocalOS проверит доступы ещё раз на preflight перед preview run и активацией."


def _connection_summary_item(binding: Dict[str, Any]) -> Dict[str, Any]:
    provider = str(binding.get("provider") or "").strip()
    catalog_item = _catalog_item_by_provider(provider)
    action = _preview_connection_action(binding, catalog_item)
    connections = binding.get("connections") if isinstance(binding.get("connections"), list) else []
    return {
        "key": str(binding.get("key") or provider or ""),
        "provider": provider,
        "title": str(binding.get("provider_title") or catalog_item.get("title") or provider),
        "capability": str(binding.get("capability") or ""),
        "status": str(binding.get("status") or ""),
        "action": action,
        "action_label": _preview_connection_label(action),
        "explanation": _preview_connection_explanation(binding, action),
        "setup_cta": _preview_connection_setup_cta(binding, action),
        "connection_count": len(connections),
        "connections": connections[:5],
        "missing_config": binding.get("missing_config") if isinstance(binding.get("missing_config"), list) else [],
        "provider_paths": _preview_provider_paths(catalog_item),
    }


def _connection_summary_next_action(status: str, missing_count: int, choice_count: int, blocked_count: int) -> str:
    if status in {"forbidden", "unsupported"} or blocked_count:
        return "review_blockers"
    if status == "needs_payment":
        return "top_up_balance"
    if choice_count:
        return "choose_existing_connection"
    if missing_count:
        return "connect_required_integrations"
    return "create_draft_then_preview"


def _connection_summary_next_action_label(next_action: str) -> str:
    labels = {
        "review_blockers": "Проверить ограничения",
        "top_up_balance": "Пополнить баланс",
        "choose_existing_connection": "Выбрать подключение",
        "connect_required_integrations": "Подключить сервисы",
        "create_draft_then_preview": "Создать draft и открыть preview",
    }
    return labels.get(next_action, "Проверить подключения")


def _connection_summary_headline(status: str, missing_count: int, choice_count: int, ready_count: int, blocked_count: int) -> str:
    if status == "forbidden":
        return "Запрос нельзя выполнить в LocalOS policy envelope."
    if status == "unsupported":
        return "Для части действий нет разрешённого provider path."
    if status == "needs_payment":
        return "Перед продолжением нужен доступный баланс или тариф."
    if blocked_count:
        return "Часть подключений заблокирована политикой или provider registry."
    if choice_count:
        return f"Нужно выбрать существующее подключение: {choice_count}."
    if missing_count:
        return f"Нужно подключить сервисы: {missing_count}. Уже готово: {ready_count}."
    return f"Все нужные подключения готовы: {ready_count}."


def _connector_intelligence_binding(binding: Dict[str, Any]) -> Dict[str, Any]:
    provider = str(binding.get("provider") or "").strip()
    status = str(binding.get("status") or "").strip()
    catalog_item = _catalog_item_by_provider(provider)
    action = _preview_connection_action(binding, catalog_item)
    provider_routes = _provider_routes(binding.get("provider_routes"))
    recommended_route = _recommended_provider_route(provider_routes, action, provider)
    return {
        "key": str(binding.get("key") or provider or ""),
        "provider": provider,
        "title": str(binding.get("provider_title") or catalog_item.get("title") or provider),
        "capability": str(binding.get("capability") or ""),
        "status": status,
        "resolution": str(binding.get("resolution") or ""),
        "route_state": str(binding.get("route_state") or ""),
        "route_summary": str(binding.get("route_summary") or ""),
        "action": action,
        "action_label": _preview_connection_label(action),
        "explanation": _preview_connection_explanation(binding, action),
        "setup_cta": _preview_connection_setup_cta(binding, action),
        "connection_count": binding.get("connection_count") if isinstance(binding.get("connection_count"), int) else 0,
        "missing_config": binding.get("missing_config") if isinstance(binding.get("missing_config"), list) else [],
        "connections": binding.get("connections") if isinstance(binding.get("connections"), list) else [],
        "provider_routes": provider_routes,
        "recommended_route": recommended_route,
        "recommended_route_reason": _recommended_provider_route_reason(recommended_route, action, provider),
        "provider_paths": _preview_provider_paths(catalog_item),
    }


def _connector_intelligence_capability(capability_item: Dict[str, Any]) -> Dict[str, Any]:
    capability = str(capability_item.get("capability") or "").strip()
    provider_candidates = capability_item.get("provider_candidates") if isinstance(capability_item.get("provider_candidates"), list) else []
    if not provider_candidates:
        provider_candidates = capability_provider_candidates(capability)
    openclaw_actions = capability_item.get("openclaw_actions") if isinstance(capability_item.get("openclaw_actions"), list) else []
    return {
        "capability": capability,
        "status": str(capability_item.get("status") or ""),
        "route_state": str(capability_item.get("route_state") or ""),
        "provider_routes": _provider_routes(capability_item.get("provider_routes")),
        "provider_candidates": [_provider_candidate_summary(item) for item in provider_candidates if isinstance(item, dict)],
        "openclaw_actions": [
            {
                "service": str(item.get("service") or ""),
                "action": str(item.get("action") or ""),
                "openclaw_action_ref": str(item.get("openclaw_action_ref") or ""),
            }
            for item in openclaw_actions
            if isinstance(item, dict)
        ],
    }


def _provider_routes(values: Any) -> List[Dict[str, str]]:
    if not isinstance(values, list):
        return []
    result: List[Dict[str, str]] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        provider = str(item.get("provider") or "").strip()
        if not provider:
            continue
        result.append(
            {
                "provider": provider,
                "label": str(item.get("label") or provider),
                "state": str(item.get("state") or ""),
                "status": str(item.get("status") or ""),
                "role": str(item.get("role") or ""),
                "kind": str(item.get("kind") or ""),
                "connect_mode": str(item.get("connect_mode") or ""),
                "primary_cta": str(item.get("primary_cta") or ""),
                "provider_action": item.get("provider_action") if isinstance(item.get("provider_action"), dict) else {},
            }
        )
    return result


def _provider_candidate_summary(item: Dict[str, Any]) -> Dict[str, str]:
    provider = str(item.get("provider") or "").strip()
    return {
        "provider": provider,
        "state": str(item.get("state") or item.get("provider_status") or ""),
        "role": str(item.get("role") or ""),
        "label": str(item.get("provider_label") or _provider_label_from_catalog(provider)),
    }


def _connector_intelligence_provider_paths(binding_items: List[Dict[str, Any]], capability_items: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    seen = set()
    result: List[Dict[str, str]] = []
    for binding in binding_items:
        for item in binding.get("provider_paths") if isinstance(binding.get("provider_paths"), list) else []:
            if not isinstance(item, dict):
                continue
            key = f"{item.get('provider')}:{item.get('status')}"
            if key in seen:
                continue
            seen.add(key)
            result.append(
                {
                    "provider": str(item.get("provider") or ""),
                    "label": str(item.get("label") or item.get("provider") or ""),
                    "status": str(item.get("status") or ""),
                    "source": "binding",
                }
            )
    for capability in capability_items:
        for item in capability.get("provider_candidates") if isinstance(capability.get("provider_candidates"), list) else []:
            if not isinstance(item, dict):
                continue
            key = f"{item.get('provider')}:{item.get('state')}"
            if key in seen:
                continue
            seen.add(key)
            result.append(
                {
                    "provider": str(item.get("provider") or ""),
                    "label": str(item.get("label") or item.get("provider") or ""),
                    "status": str(item.get("state") or ""),
                    "source": "capability",
                }
            )
    return result[:8]


def _connector_intelligence_headline(status: str, bindings: List[Dict[str, Any]], forbidden: List[Dict[str, Any]], unsupported: List[Dict[str, Any]]) -> str:
    if forbidden:
        return "Запрос выходит за policy envelope LocalOS."
    if unsupported:
        return "Для части действий нет разрешённого provider path."
    missing_count = len([item for item in bindings if item.get("action") in {"connect_required", "planned_provider"}])
    choice_count = len([item for item in bindings if item.get("action") == "choose_existing"])
    if status == "needs_payment":
        return "Перед созданием нужно решить вопрос с оплатой или лимитами."
    if choice_count:
        return f"Нужно выбрать существующее подключение: {choice_count}."
    if missing_count:
        return f"Нужно подключить сервисы: {missing_count}."
    return "Нужные сервисы выглядят доступными; следующий шаг — safe preview."


def _catalog_item_by_provider(provider: str) -> Dict[str, Any]:
    for item in integration_provider_catalog():
        if isinstance(item, dict) and str(item.get("provider") or "") == provider:
            return item
    return {}


def _provider_label_from_catalog(provider: str) -> str:
    if not provider:
        return ""
    for item in integration_provider_catalog():
        providers = item.get("providers") if isinstance(item.get("providers"), list) else []
        for candidate in providers:
            if isinstance(candidate, dict) and str(candidate.get("provider") or "") == provider:
                return str(candidate.get("label") or provider)
    return provider


def _preview_connection_action(binding: Dict[str, Any], catalog_item: Dict[str, Any]) -> str:
    status = str(binding.get("status") or "").strip()
    resolution = str(binding.get("resolution") or "").strip()
    if status == "ready":
        return "native_ready" if resolution == "native_localos" else "ready"
    if status == "needs_choice":
        return "choose_existing"
    if str(catalog_item.get("status") or "").strip() == "planned":
        return "planned_provider"
    return "connect_required"


def _preview_connection_label(action: str) -> str:
    labels = {
        "ready": "Готово",
        "native_ready": "Готово в LocalOS",
        "choose_existing": "Выберите существующее подключение",
        "connect_required": "Подключите сервис",
        "planned_provider": "Будет доступно позже",
    }
    return labels.get(action, "Проверьте подключение")


def _preview_connection_explanation(binding: Dict[str, Any], action: str) -> str:
    provider_title = str(binding.get("provider_title") or binding.get("provider") or "подключение")
    if action in {"ready", "native_ready"}:
        return f"{provider_title} уже можно использовать в агенте."
    if action == "choose_existing":
        count = binding.get("connection_count") if isinstance(binding.get("connection_count"), int) else 0
        return f"У бизнеса уже есть доступы {provider_title}. Выберите один после создания draft. Найдено: {count}."
    if action == "planned_provider":
        return "Этот provider есть в roadmap, но пока недоступен для активации агента."
    missing_config = binding.get("missing_config") if isinstance(binding.get("missing_config"), list) else []
    if missing_config:
        return f"После создания draft заполните: {', '.join([str(item) for item in missing_config])}."
    return f"После создания draft откроем подключение {provider_title}."


def _preview_connection_setup_cta(binding: Dict[str, Any], action: str) -> Dict[str, str]:
    provider = str(binding.get("provider") or "").strip()
    provider_title = str(binding.get("provider_title") or provider or "подключение")
    if action in {"ready", "native_ready"}:
        return {
            "mode": "none",
            "label": "Готово",
            "description": f"{provider_title} уже доступен для safe preview.",
        }
    if action == "choose_existing":
        return {
            "mode": "choose_existing",
            "label": "Выбрать доступ",
            "description": f"Выберите, какой доступ {provider_title} привязать к compiled workflow.",
        }
    if action == "planned_provider":
        return {
            "mode": "planned",
            "label": "Недоступно",
            "description": "Provider path есть в roadmap, но пока не может активировать агента.",
        }
    return {
        "mode": "post_create_connections",
        "label": f"Создать draft и подключить {provider_title}",
        "description": f"После создания draft LocalOS откроет вкладку подключений и привяжет {provider_title} к нужному шагу.",
    }


def _preview_provider_paths(catalog_item: Dict[str, Any]) -> List[Dict[str, str]]:
    providers = catalog_item.get("providers") if isinstance(catalog_item.get("providers"), list) else []
    result = []
    for item in providers:
        if not isinstance(item, dict):
            continue
        provider = str(item.get("provider") or "").strip()
        if provider:
            result.append(
                {
                    "provider": provider,
                    "label": str(item.get("label") or provider),
                    "status": str(item.get("status") or "unknown"),
                }
            )
    return result


def _connector_action(binding: Dict[str, Any]) -> Dict[str, Any]:
    provider = str(binding.get("provider") or "").strip()
    status = str(binding.get("status") or "").strip()
    provider_title = str(binding.get("provider_title") or provider or "подключение")
    if status == "ready":
        return {
            "kind": "connected",
            "label": "Уже готово",
            "description": f"{provider_title} уже можно использовать в агенте.",
            "after_draft": "review_and_activate",
        }
    if status == "needs_choice":
        return {
            "kind": "choose_existing",
            "label": "Выбрать доступ после создания",
            "description": f"После создания draft откроем вкладку подключений и предложим выбрать {provider_title}.",
            "after_draft": "open_agent_connections",
        }
    if provider in {"google_sheets", "telegram", "maton"}:
        return {
            "kind": "connect_after_draft",
            "label": "Подключить после создания",
            "description": f"Создайте draft агента, затем LocalOS откроет подключение {provider_title}.",
            "after_draft": "open_agent_connections",
        }
    if provider == "localos_finance":
        return {
            "kind": "native",
            "label": "Доступ внутри LocalOS",
            "description": "Финансы LocalOS проверяются через policy, approval и preflight.",
            "after_draft": "review_and_activate",
        }
    return {
        "kind": "manual",
        "label": "Настроить после создания",
        "description": f"{provider_title} будет проверен на preflight после создания draft.",
        "after_draft": "open_agent_connections",
    }


def _has_data_hint(text: str) -> bool:
    return any(
        marker in text
        for marker in [
            "файл",
            "pdf",
            "docx",
            "xlsx",
            "csv",
            "google",
            "sheet",
            "таблиц",
            "отзыв",
            "профиль",
            "услуг",
            "лид",
            "контекст",
            "шаблон",
            "источник",
            "загруз",
            "запис",
            "пакет",
        ]
    )


def _has_extraction_hint(text: str) -> bool:
    return any(marker in text for marker in ["извлеч", "найд", "бер", "возьми", "риск", "сумм", "срок", "пол", "исключ", "ответ", "подготов", "проверь", "напом", "клиент"])


def _has_output_hint(text: str) -> bool:
    return any(marker in text for marker in ["результ", "отчет", "отчёт", "письм", "таблиц", "summary", "список", "черновик", "shortlist", "сообщ", "пост", "публикац"])


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
