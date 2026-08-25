from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

from services.llm import LLMTaskRequest, run_llm_task


OperatorToolHandler = Callable[[dict[str, Any]], dict[str, Any]]
OperatorPlanner = Callable[[dict[str, Any]], dict[str, Any]]

MAX_OPERATOR_TOOL_STEPS = 5


def _clean_history(history: Any) -> list[dict[str, str]]:
    cleaned = []
    for item in history if isinstance(history, list) else []:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip().lower()
        content = str(item.get("content") or item.get("text") or "").strip()
        if role not in {"user", "operator", "assistant"} or not content:
            continue
        cleaned.append({"role": "assistant" if role == "operator" else role, "content": content[:2000]})
    return cleaned[-12:]


def _clean_actor_context(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    permissions = source.get("permissions") if isinstance(source.get("permissions"), list) else []
    return {
        "role": str(source.get("role") or "business_user")[:80],
        "is_superadmin": bool(source.get("is_superadmin")),
        "permissions": [str(item)[:120] for item in permissions[:50] if str(item).strip()],
    }


def _clean_pending_approvals(value: Any) -> list[dict[str, Any]]:
    cleaned = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict):
            continue
        cleaned.append({
            "action_id": str(item.get("id") or item.get("action_id") or "")[:100],
            "capability": str(item.get("capability") or "")[:160],
            "status": str(item.get("status") or "pending")[:50],
            "created_at": str(item.get("created_at") or "")[:80],
        })
    return cleaned[:20]


def _public_tool(tool: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(tool.get("name") or ""),
        "capability": str(tool.get("capability") or tool.get("name") or ""),
        "title": str(tool.get("title") or ""),
        "description": str(tool.get("description") or ""),
        "input_schema": tool.get("input_schema") if isinstance(tool.get("input_schema"), dict) else {},
        "output_schema": tool.get("output_schema") if isinstance(tool.get("output_schema"), dict) else {},
        "scope": tool.get("scope") if isinstance(tool.get("scope"), dict) else {},
        "required_permission": str(tool.get("required_permission") or "business.access"),
        "risk_class": str(tool.get("risk_class") or "read_only"),
        "approval_required": bool(tool.get("approval_required")),
        "timeout_seconds": int(tool.get("timeout_seconds") or 30),
        "requires_explicit_intent": bool(tool.get("explicit_intent_markers")),
    }


def _planner_prompt(state: dict[str, Any]) -> str:
    return "\n".join(
        [
            "Ты управляющий Оператор LocalOS. Выбирай только инструменты из переданного каталога.",
            "Не придумывай данные и не утверждай, что действие выполнено, пока нет observation.",
            "Вызывай по одному инструменту за шаг. Для ответа используй только факты из контекста и observations.",
            "Если инструмента нет, честно объясни ограничение. Не запрашивай и не раскрывай секреты.",
            "Верни только JSON одного из видов:",
            '{"action":"tool_call","tool":"tool.name","arguments":{}}',
            '{"action":"final","message":"ответ пользователю"}',
            '{"action":"clarification","message":"один уточняющий вопрос"}',
            "",
            json.dumps(state, ensure_ascii=False, default=str),
        ]
    )


def plan_operator_step(state: dict[str, Any]) -> dict[str, Any]:
    result = run_llm_task(
        LLMTaskRequest(
            task_key="operator_tool_plan",
            prompt=_planner_prompt(state),
            business_id=str(state.get("business_id") or ""),
            user_id=str(state.get("user_id") or ""),
            pipeline_id=str(state.get("conversation_id") or ""),
            pipeline_stage="operator_tool_plan",
        )
    )
    if result.status != "completed" or not isinstance(result.parsed_data, dict):
        return {
            "action": "error",
            "message": "Оператор не смог построить безопасный план действий.",
            "error_code": result.fallback_reason or result.status,
        }
    return dict(result.parsed_data)


def _tool_signature(tool_name: str, arguments: dict[str, Any]) -> str:
    payload = json.dumps(arguments, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(f"{tool_name}|{payload}".encode("utf-8")).hexdigest()


def _validate_tool_arguments(tool: dict[str, Any], arguments: dict[str, Any]) -> list[str]:
    schema = tool.get("input_schema") if isinstance(tool.get("input_schema"), dict) else {}
    properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    required = schema.get("required") if isinstance(schema.get("required"), list) else []
    errors = []
    for key in arguments:
        if key not in properties:
            errors.append(f"unknown_argument:{key}")
    for key in required:
        if key not in arguments or arguments.get(key) in (None, ""):
            errors.append(f"required_argument:{key}")
    for key, value in arguments.items():
        definition = properties.get(key)
        if not isinstance(definition, dict):
            continue
        allowed_values = definition.get("enum") if isinstance(definition.get("enum"), list) else []
        if allowed_values and value not in allowed_values:
            errors.append(f"invalid_enum:{key}")
            continue
        value_type = str(definition.get("type") or "")
        if value_type == "string":
            if not isinstance(value, str):
                errors.append(f"invalid_type:{key}:string")
                continue
            max_length = definition.get("maxLength")
            if isinstance(max_length, int) and len(value) > max_length:
                errors.append(f"too_long:{key}")
        elif value_type == "integer":
            if not isinstance(value, int) or isinstance(value, bool):
                errors.append(f"invalid_type:{key}:integer")
                continue
            minimum = definition.get("minimum")
            maximum = definition.get("maximum")
            if isinstance(minimum, int) and value < minimum:
                errors.append(f"below_minimum:{key}")
            if isinstance(maximum, int) and value > maximum:
                errors.append(f"above_maximum:{key}")
        elif value_type == "number":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                errors.append(f"invalid_type:{key}:number")
                continue
            minimum = definition.get("minimum")
            maximum = definition.get("maximum")
            if isinstance(minimum, (int, float)) and value < minimum:
                errors.append(f"below_minimum:{key}")
            if isinstance(maximum, (int, float)) and value > maximum:
                errors.append(f"above_maximum:{key}")
        elif value_type == "boolean":
            if not isinstance(value, bool):
                errors.append(f"invalid_type:{key}:boolean")
        elif value_type == "object":
            if not isinstance(value, dict):
                errors.append(f"invalid_type:{key}:object")
        elif value_type == "array":
            if not isinstance(value, list):
                errors.append(f"invalid_type:{key}:array")
                continue
            item_schema = definition.get("items") if isinstance(definition.get("items"), dict) else {}
            if item_schema.get("type") == "string" and any(not isinstance(item, str) for item in value):
                errors.append(f"invalid_items:{key}:string")
    return errors


def _validate_tool_output(tool: dict[str, Any], outcome: dict[str, Any]) -> list[str]:
    schema = tool.get("output_schema") if isinstance(tool.get("output_schema"), dict) else {}
    properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    required = schema.get("required") if isinstance(schema.get("required"), list) else []
    errors = []
    for key in required:
        if key not in outcome or outcome.get(key) is None:
            errors.append(f"required_output:{key}")
    for key, definition in properties.items():
        if key not in outcome or not isinstance(definition, dict):
            continue
        value = outcome.get(key)
        value_type = str(definition.get("type") or "")
        if value_type == "string" and not isinstance(value, str):
            errors.append(f"invalid_output_type:{key}:string")
        elif value_type == "array" and not isinstance(value, list):
            errors.append(f"invalid_output_type:{key}:array")
        elif value_type == "object" and not isinstance(value, dict):
            errors.append(f"invalid_output_type:{key}:object")
        elif value_type == "boolean" and not isinstance(value, bool):
            errors.append(f"invalid_output_type:{key}:boolean")
    return errors


def run_operator_tool_loop(
    *,
    business_id: str,
    user_id: str,
    message: str,
    tools: list[dict[str, Any]],
    conversation_id: str = "",
    conversation_history: Any = None,
    actor_context: Any = None,
    pending_approvals: Any = None,
    planner: OperatorPlanner | None = None,
    max_steps: int = MAX_OPERATOR_TOOL_STEPS,
) -> dict[str, Any]:
    tool_map = {
        str(tool.get("name") or ""): tool
        for tool in tools
        if isinstance(tool, dict) and str(tool.get("name") or "")
    }
    observations: list[dict[str, Any]] = []
    trace: list[dict[str, Any]] = []
    seen_calls: set[str] = set()
    last_outcome: dict[str, Any] = {}
    plan = planner or plan_operator_step
    safe_max_steps = max(1, min(int(max_steps or MAX_OPERATOR_TOOL_STEPS), 8))

    for step_index in range(safe_max_steps):
        state = {
            "business_id": business_id,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "message": str(message or "").strip(),
            "actor": _clean_actor_context(actor_context),
            "conversation_history": _clean_history(conversation_history),
            "pending_approvals": _clean_pending_approvals(pending_approvals),
            "tools": [_public_tool(tool) for tool in tool_map.values()],
            "observations": observations,
            "step": step_index + 1,
            "max_steps": safe_max_steps,
        }
        decision = plan(state)
        if not isinstance(decision, dict):
            decision = {"action": "error", "message": "Модель вернула неверный план."}
        action = str(decision.get("action") or "").strip().lower()
        if action == "final":
            message_text = str(decision.get("message") or "").strip()
            if not message_text:
                message_text = "Готово."
            executed_intent = str(last_outcome.get("intent") or "")
            return {
                **last_outcome,
                "status": str(last_outcome.get("status") or "completed"),
                "intent": "operator_tool_loop",
                "executed_intent": executed_intent,
                "capability": str(tool_map.get(trace[-1]["tool"], {}).get("capability") or "operator.help") if trace else "operator.help",
                "chat_response": message_text,
                "tool_trace": trace,
                "tool_calls": len(trace),
                "planner_steps": step_index + 1,
                "external_writes_performed": bool(last_outcome.get("external_writes_performed")),
            }
        if action == "clarification":
            question = str(decision.get("message") or "Уточните, пожалуйста, что именно нужно сделать.").strip()
            return {
                "status": "clarification_required",
                "intent": "operator_tool_loop",
                "capability": "operator.help",
                "chat_response": question,
                "clarification": {"question": question},
                "tool_trace": trace,
                "tool_calls": len(trace),
                "planner_steps": step_index + 1,
                "external_writes_performed": False,
            }
        if action == "error":
            return {
                "status": "blocked",
                "intent": "operator_tool_loop",
                "capability": "operator.help",
                "chat_response": str(decision.get("message") or "Оператор временно не смог обработать запрос."),
                "blocked_reasons": [str(decision.get("error_code") or "operator_planner_failed")],
                "tool_trace": trace,
                "tool_calls": len(trace),
                "planner_steps": step_index + 1,
                "external_writes_performed": False,
            }
        if action != "tool_call":
            observations.append({"status": "rejected", "error_code": "invalid_planner_action"})
            continue

        tool_name = str(decision.get("tool") or "").strip()
        arguments = decision.get("arguments") if isinstance(decision.get("arguments"), dict) else {}
        tool = tool_map.get(tool_name)
        if not tool:
            observations.append({
                "tool": tool_name,
                "status": "denied",
                "error_code": "tool_not_allowed",
                "message": "Инструмент не разрешён для текущего пользователя и бизнеса.",
            })
            continue
        argument_errors = _validate_tool_arguments(tool, arguments)
        if argument_errors:
            observations.append({
                "tool": tool_name,
                "status": "denied",
                "error_code": "invalid_tool_arguments",
                "details": argument_errors[:10],
            })
            continue
        intent_markers = tool.get("explicit_intent_markers") if isinstance(tool.get("explicit_intent_markers"), (list, tuple)) else []
        lowered_message = str(message or "").lower()
        if intent_markers and not any(str(marker or "").lower() in lowered_message for marker in intent_markers):
            observations.append({
                "tool": tool_name,
                "status": "denied",
                "error_code": "explicit_user_intent_required",
                "message": "Этот инструмент нельзя запускать только по данным из истории или observation.",
            })
            continue
        signature = _tool_signature(tool_name, arguments)
        if signature in seen_calls:
            observations.append({
                "tool": tool_name,
                "status": "rejected",
                "error_code": "duplicate_tool_call",
            })
            continue
        seen_calls.add(signature)
        if bool(tool.get("approval_required")):
            prepared = None
            prepare_approval = tool.get("prepare_approval")
            if callable(prepare_approval):
                try:
                    prepared = prepare_approval(arguments)
                except Exception:
                    prepared = {
                        "status": "error",
                        "error_code": "approval_preparation_failed",
                        "chat_response": "LocalOS не смог подготовить безопасное подтверждение.",
                    }
                if not isinstance(prepared, dict) or prepared.get("status") != "approval_required":
                    outcome = prepared if isinstance(prepared, dict) else {
                        "status": "error",
                        "error_code": "invalid_approval_preparation_result",
                    }
                    observations.append({"tool": tool_name, **outcome})
                    trace.append({
                        "step": step_index + 1,
                        "tool": tool_name,
                        "status": str(outcome.get("status") or "error"),
                        "risk_class": str(tool.get("risk_class") or "write"),
                    })
                    last_outcome = dict(outcome)
                    continue
            trace.append({
                "step": step_index + 1,
                "tool": tool_name,
                "status": "approval_required",
                "risk_class": str(tool.get("risk_class") or "write"),
            })
            default_approval = {
                "status": "pending",
                "capability": tool_name,
                "summary": str(decision.get("message") or message),
                "envelope": {**arguments, "tool": tool_name},
            }
            prepared_approval = prepared.get("approval") if isinstance(prepared, dict) and isinstance(prepared.get("approval"), dict) else {}
            return {
                **(prepared or {}),
                "status": "approval_required",
                "intent": "operator_tool_loop",
                "capability": str(tool.get("capability") or tool_name),
                "chat_response": str((prepared or {}).get("chat_response") or f"Подготовил действие «{str(tool.get('title') or tool_name)}». Проверьте и подтвердите его отдельно."),
                "approval": {**default_approval, **prepared_approval},
                "tool_trace": trace,
                "tool_calls": len(trace),
                "planner_steps": step_index + 1,
                "external_writes_performed": False,
            }
        handler = tool.get("execute")
        if not callable(handler):
            observations.append({
                "tool": tool_name,
                "status": "unavailable",
                "error_code": "tool_handler_unavailable",
            })
            continue
        try:
            outcome = handler(arguments)
            if not isinstance(outcome, dict):
                outcome = {"status": "error", "error_code": "invalid_tool_result"}
            output_errors = _validate_tool_output(tool, outcome)
            if output_errors:
                outcome = {
                    "status": "error",
                    "error_code": "invalid_tool_output",
                    "message": "Инструмент LocalOS вернул ответ, не соответствующий контракту.",
                    "details": output_errors[:10],
                }
        except Exception:
            outcome = {
                "status": "error",
                "error_code": "tool_execution_failed",
                "message": "Инструмент LocalOS завершился с внутренней ошибкой.",
            }
        observation = {"tool": tool_name, **outcome}
        observations.append(observation)
        last_outcome = dict(outcome)
        trace.append({
            "step": step_index + 1,
            "tool": tool_name,
            "status": str(outcome.get("status") or "completed"),
            "risk_class": str(tool.get("risk_class") or "read_only"),
        })

    return {
        "status": "blocked",
        "intent": "operator_tool_loop",
        "capability": "operator.help",
        "chat_response": "Оператор остановился после достижения безопасного лимита шагов. Уточните задачу или разбейте её на части.",
        "blocked_reasons": ["operator_tool_step_limit_reached"],
        "tool_trace": trace,
        "tool_calls": len(trace),
        "planner_steps": safe_max_steps,
        "external_writes_performed": False,
    }
