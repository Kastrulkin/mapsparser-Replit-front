from __future__ import annotations

from typing import Any, Dict, List

from services.agent_blueprint_draft_builder import compile_agent_blueprint, infer_blueprint_category
from services.agent_builder_billing import build_agent_creation_cost_preview
from services.agent_feasibility_resolver import resolve_agent_feasibility
from services.agent_openclaw_planner_context import build_openclaw_planner_context
from services.agent_openclaw_planner_loop import build_openclaw_planner_loop
from services.agent_provider_registry import integration_provider_catalog


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
    questions = _merge_questions(_missing_questions(description, category), planner_loop)
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
        "required_connectors": _connector_preview_items(feasibility),
        "connection_plan": _build_preview_connection_plan(feasibility),
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


def _merge_questions(local_questions: List[Dict[str, str]], planner_loop: Dict[str, Any]) -> List[Dict[str, str]]:
    result: List[Dict[str, str]] = []
    seen = set()
    for item in local_questions:
        key = str(item.get("key") or item.get("question") or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
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
        if not key or not question or key in seen:
            continue
        seen.add(key)
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
    if feasibility_status == "forbidden":
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
    can_create_draft = not questions and status not in {"forbidden", "unsupported", "needs_payment"}
    can_activate = can_create_draft and status == "ready"
    return {
        "schema": "localos_agent_builder_setup_flow_v1",
        "status": _setup_flow_status(status, questions),
        "primary_action": _setup_primary_action(status, questions, missing_connections, connection_choices),
        "can_create_draft": can_create_draft,
        "can_activate": can_activate,
        "activation_blockers": _activation_blockers(status, questions, missing_connections, connection_choices, forbidden, unsupported),
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
                "status": "blocked" if forbidden or unsupported else "done",
                "description": _policy_step_description(status),
                "forbidden": forbidden,
                "unsupported": unsupported,
            },
            {
                "key": "create",
                "label": "Создать агента",
                "status": "ready" if can_create_draft else "blocked",
                "description": "Создаст draft агента. Активация возможна только после preflight." if can_create_draft else "Сначала завершите обязательные шаги выше.",
            },
        ],
    }


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
