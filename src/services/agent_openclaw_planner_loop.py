from __future__ import annotations

from typing import Any, Dict, List

from services.openclaw_capability_catalog import get_openclaw_capability_catalog, openclaw_actions_for_capability


def build_openclaw_planner_loop(
    planner_context: Dict[str, Any],
    *,
    openclaw_catalog: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    context = planner_context if isinstance(planner_context, dict) else {}
    catalog = openclaw_catalog or get_openclaw_capability_catalog()
    allowed_capabilities = _clean_list(context.get("allowed_capabilities"))
    connection_state = context.get("connection_state") if isinstance(context.get("connection_state"), dict) else {}
    required_bindings = context.get("required_bindings") if isinstance(context.get("required_bindings"), list) else []

    questions = []
    questions.extend(_questions_for_connection_state(connection_state))
    questions.extend(_questions_for_required_bindings(required_bindings, connection_state))
    questions = _dedupe_questions(questions)[:5]

    capability_plan = [_capability_plan_item(capability, catalog) for capability in allowed_capabilities]
    forbidden = connection_state.get("forbidden") if isinstance(connection_state.get("forbidden"), list) else []
    unsupported = connection_state.get("unsupported") if isinstance(connection_state.get("unsupported"), list) else []
    blocked = bool(forbidden or unsupported)

    return {
        "schema": "localos_openclaw_planner_loop_v1",
        "mode": "design_time_only",
        "catalog_source": str(catalog.get("source") or ""),
        "status": "blocked" if blocked else ("needs_clarification" if questions else "proposal_ready"),
        "may_execute_tools": False,
        "must_compile_in_localos": True,
        "planner_contract": _planner_contract(context),
        "clarifying_questions": questions,
        "capability_plan": capability_plan,
        "workflow_proposal": {
            "allowed_capabilities": allowed_capabilities,
            "required_bindings": _binding_summaries(required_bindings),
            "provider_paths": _provider_paths_from_capability_plan(capability_plan),
            "openclaw_action_refs": [
                str(action.get("openclaw_action_ref") or "")
                for item in capability_plan
                for action in (item.get("openclaw_actions") if isinstance(item.get("openclaw_actions"), list) else [])
                if str(action.get("openclaw_action_ref") or "").strip()
            ],
            "policy": "localos_envelope",
        },
    }


def _planner_contract(context: Dict[str, Any]) -> Dict[str, Any]:
    output_contract = context.get("output_contract") if isinstance(context.get("output_contract"), dict) else {}
    approval_classes = _clean_list(context.get("approval_required_action_classes"))
    forbidden_classes = _clean_list(context.get("forbidden_action_classes"))
    return {
        "schema": "localos_openclaw_planner_contract_v1",
        "role": "clarify_and_propose_workflow",
        "execution_mode": "design_time_only",
        "tool_execution_allowed": False,
        "external_side_effects_allowed": False,
        "compiled_workflow_owner": str(output_contract.get("compiled_workflow_owner") or "localos"),
        "response_format": str(output_contract.get("format") or "json_only"),
        "required_response_schema": {
            "clarifying_questions": "array",
            "workflow_draft": "object",
            "required_connectors": "array",
            "capability_plan": "array",
            "approval_points": "array",
            "unsupported_requests": "array",
        },
        "must_return": [
            "missing_details_or_empty_array",
            "provider_requirements",
            "openclaw_action_refs_only_as_references",
            "localos_policy_risks",
        ],
        "must_not": [
            "execute_tools",
            "send_messages",
            "publish_content",
            "write_external_systems",
            "request_or_store_raw_credentials",
            "bypass_localos_subscription_or_approval",
        ],
        "approval_required_action_classes": approval_classes,
        "forbidden_action_classes": forbidden_classes,
    }


def _questions_for_connection_state(connection_state: Dict[str, Any]) -> List[Dict[str, str]]:
    questions = []
    for item in connection_state.get("missing_connections") or []:
        if not isinstance(item, dict):
            continue
        provider = str(item.get("provider") or "").strip()
        title = str(item.get("provider_title") or provider or "подключение").strip()
        missing_config = _clean_list(item.get("missing_config"))
        if missing_config:
            questions.append(
                {
                    "key": f"connect_{provider}",
                    "question": f"Подключите {title} и заполните: {', '.join(missing_config)}.",
                    "reason": "required_connection_missing_config",
                }
            )
        else:
            questions.append(
                {
                    "key": f"connect_{provider}",
                    "question": f"Подключите {title}, чтобы агент можно было активировать.",
                    "reason": "required_connection_missing",
                }
            )
    for item in connection_state.get("connection_choices") or []:
        if not isinstance(item, dict):
            continue
        provider = str(item.get("provider") or "").strip()
        title = str(item.get("provider_title") or provider or "подключение").strip()
        count = item.get("connection_count") if isinstance(item.get("connection_count"), int) else 0
        questions.append(
            {
                "key": f"choose_{provider}",
                "question": f"Выберите, какой {title} использовать для агента. Найдено подключений: {count}.",
                "reason": "multiple_connections_available",
            }
        )
    for item in connection_state.get("unsupported") or []:
        if isinstance(item, dict):
            questions.append(
                {
                    "key": "unsupported_capability",
                    "question": str(item.get("reason") or "Нет разрешённого provider path для нужного действия."),
                    "reason": "unsupported",
                }
            )
    for item in connection_state.get("forbidden") or []:
        if isinstance(item, dict):
            questions.append(
                {
                    "key": "forbidden_request",
                    "question": str(item.get("reason") or "Запрос запрещён политикой LocalOS."),
                    "reason": "forbidden",
                }
            )
    return questions


def _questions_for_required_bindings(required_bindings: List[Any], connection_state: Dict[str, Any]) -> List[Dict[str, str]]:
    ready_providers = set()
    ready_bindings = connection_state.get("ready_bindings") if isinstance(connection_state.get("ready_bindings"), list) else []
    for ready_binding in ready_bindings:
        if not isinstance(ready_binding, dict):
            continue
        provider = str(ready_binding.get("provider") or "").strip()
        if provider:
            ready_providers.add(provider)
    questions = []
    for item in required_bindings:
        if not isinstance(item, dict):
            continue
        provider = str(item.get("provider") or "").strip()
        if provider in ready_providers:
            continue
        required_config = _clean_list(item.get("required_config"))
        if provider == "google_sheets" and {"spreadsheet_id", "sheet_name"}.issubset(set(required_config)):
            questions.append(
                {
                    "key": "google_sheets_target",
                    "question": "Укажите Google Sheets таблицу и лист, которые агент должен читать или обновлять.",
                    "reason": "binding_config_needed",
                }
            )
        elif provider == "telegram" and "bot_mode" in required_config:
            questions.append(
                {
                    "key": "telegram_target",
                    "question": "Выберите Telegram-бота или режим доставки для агента.",
                    "reason": "binding_config_needed",
                }
            )
    return questions


def _capability_plan_item(capability: str, catalog: Dict[str, Any]) -> Dict[str, Any]:
    actions = openclaw_actions_for_capability(catalog, capability)
    provider_candidates = _provider_candidates_from_actions(actions)
    return {
        "capability": capability,
        "openclaw_supported": bool(actions),
        "openclaw_actions": actions,
        "provider_candidates": provider_candidates,
        "provider_paths": _provider_path_labels(provider_candidates),
        "required_auth": _required_auth_from_actions(actions),
        "execution_boundary": "localos_envelope",
    }


def _provider_candidates_from_actions(actions: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    result: List[Dict[str, str]] = []
    seen = set()
    for action in actions:
        candidates = action.get("provider_candidates") if isinstance(action.get("provider_candidates"), list) else []
        for item in candidates:
            if not isinstance(item, dict):
                continue
            provider = str(item.get("provider") or "").strip()
            state = str(item.get("state") or "").strip() or "available"
            role = str(item.get("role") or "").strip()
            key = (provider, state, role)
            if not provider or key in seen:
                continue
            seen.add(key)
            result.append({"provider": provider, "state": state, "role": role})
    return result


def _provider_path_labels(provider_candidates: List[Dict[str, str]]) -> List[str]:
    result = []
    for item in provider_candidates:
        provider = str(item.get("provider") or "").strip()
        state = str(item.get("state") or "").strip()
        if provider and state:
            result.append(f"{provider}:{state}")
        elif provider:
            result.append(provider)
    return result


def _provider_paths_from_capability_plan(capability_plan: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    result = []
    seen = set()
    for item in capability_plan:
        capability = str(item.get("capability") or "").strip()
        for path in item.get("provider_paths") if isinstance(item.get("provider_paths"), list) else []:
            clean = str(path or "").strip()
            key = (capability, clean)
            if capability and clean and key not in seen:
                seen.add(key)
                result.append({"capability": capability, "provider_path": clean})
    return result


def _required_auth_from_actions(actions: List[Dict[str, Any]]) -> List[str]:
    result = []
    for action in actions:
        required_auth = action.get("required_auth") if isinstance(action.get("required_auth"), list) else []
        for value in required_auth:
            clean = str(value or "").strip()
            if clean and clean not in result:
                result.append(clean)
    return result


def _binding_summaries(values: List[Any]) -> List[Dict[str, Any]]:
    result = []
    for item in values:
        if not isinstance(item, dict):
            continue
        result.append(
            {
                "key": str(item.get("key") or ""),
                "provider": str(item.get("provider") or ""),
                "capability": str(item.get("capability") or ""),
                "direction": str(item.get("direction") or ""),
                "required_config": _clean_list(item.get("required_config")),
            }
        )
    return result


def _dedupe_questions(values: List[Dict[str, str]]) -> List[Dict[str, str]]:
    result = []
    seen = set()
    for item in values:
        key = str(item.get("key") or item.get("question") or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _clean_list(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []
    result = []
    for value in values:
        clean = str(value or "").strip()
        if clean and clean not in result:
            result.append(clean)
    return result
