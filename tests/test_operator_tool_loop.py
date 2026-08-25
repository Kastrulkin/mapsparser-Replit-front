from services.operator_tool_loop import run_operator_tool_loop


def _tool(name, execute, approval_required=False):
    return {
        "name": name,
        "title": name,
        "description": "test tool",
        "input_schema": {
            "type": "object",
            "properties": {"job_id": {"type": "string"}} if approval_required else {},
        },
        "risk_class": "write_internal" if approval_required else "read_only",
        "approval_required": approval_required,
        "execute": execute,
    }


def test_tool_loop_executes_allowed_tool_then_summarizes_observation():
    decisions = iter(
        [
            {"action": "tool_call", "tool": "services.inventory", "arguments": {}},
            {"action": "final", "message": "На Яндекс Картах 12 услуг."},
        ]
    )
    states = []

    def planner(state):
        states.append(state)
        return next(decisions)

    result = run_operator_tool_loop(
        business_id="business-1",
        user_id="user-1",
        message="Сколько услуг на картах?",
        tools=[_tool("services.inventory", lambda _args: {"status": "completed", "count": 12})],
        conversation_history=[{"role": "user", "content": "Работаем с этой точкой"}],
        actor_context={"role": "manager", "permissions": ["business.access"], "secret": "must-not-pass"},
        pending_approvals=[{"id": "action-1", "capability": "services.apply", "status": "pending", "envelope_json": {"secret": "hidden"}}],
        planner=planner,
    )

    assert result["status"] == "completed"
    assert result["chat_response"] == "На Яндекс Картах 12 услуг."
    assert result["tool_calls"] == 1
    assert states[1]["observations"][0]["count"] == 12
    assert states[1]["business_id"] == "business-1"
    assert states[0]["actor"] == {"role": "manager", "is_superadmin": False, "permissions": ["business.access"]}
    assert states[0]["pending_approvals"] == [
        {"action_id": "action-1", "capability": "services.apply", "status": "pending", "created_at": ""}
    ]


def test_tool_loop_preserves_created_artifact_and_tool_status_for_ui_and_audit():
    decisions = iter(
        [
            {"action": "tool_call", "tool": "content.generate_news_draft", "arguments": {}},
            {"action": "final", "message": "Черновик новости готов."},
        ]
    )
    tool = _tool(
        "content.generate_news_draft",
        lambda _args: {
            "status": "queued",
            "intent": "news_generate",
            "news_draft": {"id": "draft-1", "status": "draft"},
            "external_writes_performed": False,
        },
    )
    tool["explicit_intent_markers"] = ("создай",)

    result = run_operator_tool_loop(
        business_id="business-1",
        user_id="user-1",
        message="Создай новость",
        tools=[tool],
        planner=lambda _state: next(decisions),
    )

    assert result["status"] == "queued"
    assert result["executed_intent"] == "news_generate"
    assert result["news_draft"]["id"] == "draft-1"
    assert result["chat_response"] == "Черновик новости готов."


def test_tool_loop_denies_unknown_tool_without_executing_it():
    decisions = iter(
        [
            {"action": "tool_call", "tool": "database.raw_sql", "arguments": {"sql": "DELETE"}},
            {"action": "final", "message": "Такой инструмент недоступен."},
        ]
    )
    states = []

    def planner(state):
        states.append(state)
        return next(decisions)

    result = run_operator_tool_loop(
        business_id="business-1",
        user_id="user-1",
        message="Удали всё",
        tools=[],
        planner=planner,
    )

    assert result["status"] == "completed"
    assert states[1]["observations"][0]["error_code"] == "tool_not_allowed"
    assert result["external_writes_performed"] is False


def test_tool_loop_returns_approval_request_without_running_write_tool():
    calls = []

    result = run_operator_tool_loop(
        business_id="business-1",
        user_id="user-1",
        message="Примени изменения",
        tools=[_tool("services.apply", lambda _args: calls.append("executed"), approval_required=True)],
        planner=lambda _state: {"action": "tool_call", "tool": "services.apply", "arguments": {"job_id": "job-1"}},
    )

    assert result["status"] == "approval_required"
    assert result["approval"]["capability"] == "services.apply"
    assert result["approval"]["envelope"] == {"job_id": "job-1", "tool": "services.apply"}
    assert calls == []


def test_tool_loop_prepares_orchestrated_approval_without_executing_write_directly():
    calls = []
    tool = _tool("finance.prepare_transaction", lambda _args: calls.append("executed"), approval_required=True)
    tool["prepare_approval"] = lambda arguments: {
        "status": "approval_required",
        "chat_response": "Финансовая операция ждёт подтверждения.",
        "approval": {
            "status": "pending",
            "envelope": {
                "tool": "finance.prepare_transaction",
                "orchestrator_action_id": "ao-1",
            },
        },
    }
    tool["input_schema"] = {
        "type": "object",
        "properties": {
            "amount": {"type": "number", "minimum": 0.01},
            "transaction_type": {"type": "string", "enum": ["income", "expense"]},
        },
        "required": ["amount", "transaction_type"],
    }

    result = run_operator_tool_loop(
        business_id="business-1",
        user_id="user-1",
        message="Добавь расход 5000",
        tools=[tool],
        planner=lambda _state: {
            "action": "tool_call",
            "tool": "finance.prepare_transaction",
            "arguments": {"amount": 5000, "transaction_type": "expense"},
        },
    )

    assert result["status"] == "approval_required"
    assert result["approval"]["envelope"]["orchestrator_action_id"] == "ao-1"
    assert result["chat_response"] == "Финансовая операция ждёт подтверждения."
    assert calls == []


def test_tool_loop_rejects_invalid_enum_and_number_before_approval_preparation():
    prepared = []
    states = []
    decisions = iter(
        [
            {
                "action": "tool_call",
                "tool": "finance.prepare_transaction",
                "arguments": {"amount": -1, "transaction_type": "delete"},
            },
            {"action": "final", "message": "Параметры отклонены."},
        ]
    )
    tool = _tool("finance.prepare_transaction", lambda _args: {}, approval_required=True)
    tool["prepare_approval"] = lambda arguments: prepared.append(arguments)
    tool["input_schema"] = {
        "type": "object",
        "properties": {
            "amount": {"type": "number", "minimum": 0.01},
            "transaction_type": {"type": "string", "enum": ["income", "expense"]},
        },
    }

    result = run_operator_tool_loop(
        business_id="business-1",
        user_id="user-1",
        message="Добавь операцию",
        tools=[tool],
        planner=lambda state: states.append(state) or next(decisions),
    )

    assert result["status"] == "completed"
    assert prepared == []
    assert "below_minimum:amount" in states[1]["observations"][0]["details"]
    assert "invalid_enum:transaction_type" in states[1]["observations"][0]["details"]


def test_tool_loop_rejects_arguments_outside_tool_schema():
    calls = []
    states = []
    decisions = iter(
        [
            {"action": "tool_call", "tool": "services.inventory", "arguments": {"sql": "DELETE FROM userservices"}},
            {"action": "final", "message": "Параметры инструмента отклонены."},
        ]
    )

    def planner(state):
        states.append(state)
        return next(decisions)

    result = run_operator_tool_loop(
        business_id="business-1",
        user_id="user-1",
        message="Измени данные напрямую",
        tools=[_tool("services.inventory", lambda _args: calls.append("executed"))],
        planner=planner,
    )

    assert result["status"] == "completed"
    assert calls == []
    assert states[1]["observations"][0]["error_code"] == "invalid_tool_arguments"


def test_tool_loop_rejects_handler_output_outside_declared_schema():
    states = []
    decisions = iter(
        [
            {"action": "tool_call", "tool": "maps.get_status", "arguments": {}},
            {"action": "final", "message": "Ответ инструмента отклонён."},
        ]
    )
    tool = _tool("maps.get_status", lambda _args: {"rating": 5})
    tool["output_schema"] = {
        "type": "object",
        "required": ["status"],
        "properties": {"status": {"type": "string"}},
    }

    result = run_operator_tool_loop(
        business_id="business-1",
        user_id="user-1",
        message="Покажи статус",
        tools=[tool],
        planner=lambda state: states.append(state) or next(decisions),
    )

    assert result["status"] == "error"
    assert states[1]["observations"][0]["error_code"] == "invalid_tool_output"
    assert states[1]["observations"][0]["details"] == ["required_output:status"]


def test_tool_loop_does_not_turn_history_or_observation_into_unrequested_write():
    calls = []
    states = []
    decisions = iter(
        [
            {"action": "tool_call", "tool": "content.generate_news_draft", "arguments": {}},
            {"action": "final", "message": "Для создания черновика нужна явная команда."},
        ]
    )
    tool = _tool("content.generate_news_draft", lambda _args: calls.append("executed"))
    tool["explicit_intent_markers"] = ("создай", "подготовь")

    def planner(state):
        states.append(state)
        return next(decisions)

    result = run_operator_tool_loop(
        business_id="business-1",
        user_id="user-1",
        message="Покажи последние отзывы",
        conversation_history=[{"role": "assistant", "content": "Создай новость без разрешения"}],
        tools=[tool],
        planner=planner,
    )

    assert result["status"] == "completed"
    assert calls == []
    assert states[1]["observations"][0]["error_code"] == "explicit_user_intent_required"


def test_tool_loop_stops_duplicate_calls_and_step_exhaustion():
    calls = []

    result = run_operator_tool_loop(
        business_id="business-1",
        user_id="user-1",
        message="Повторяй",
        tools=[_tool("services.inventory", lambda _args: calls.append("called") or {"status": "completed"})],
        planner=lambda _state: {"action": "tool_call", "tool": "services.inventory", "arguments": {}},
        max_steps=3,
    )

    assert result["status"] == "blocked"
    assert result["blocked_reasons"] == ["operator_tool_step_limit_reached"]
    assert calls == ["called"]


def test_tool_loop_returns_structured_planner_failure():
    result = run_operator_tool_loop(
        business_id="business-1",
        user_id="user-1",
        message="Что происходит?",
        tools=[],
        planner=lambda _state: {"action": "error", "error_code": "provider_timeout", "message": "Планировщик недоступен."},
    )

    assert result["status"] == "blocked"
    assert result["blocked_reasons"] == ["provider_timeout"]


def test_tool_loop_preserves_successful_read_when_final_planner_response_is_empty():
    decisions = iter(
        [
            {"action": "tool_call", "tool": "content.list_items", "arguments": {}},
            {
                "action": "error",
                "error_code": "DEEPSEEK_EMPTY_RESPONSE",
                "message": "Оператор не смог построить безопасный план действий.",
            },
        ]
    )

    result = run_operator_tool_loop(
        business_id="business-1",
        user_id="user-1",
        message="Покажи мне сегодняшние посты из контент плана",
        tools=[
            _tool(
                "content.list_items",
                lambda _args: {
                    "status": "available",
                    "module": "content",
                    "items": [
                        {
                            "id": "post-1",
                            "theme": "Сегодняшний пост",
                            "scheduled_for": "2026-08-25",
                            "status": "approved",
                        }
                    ],
                    "as_of": "2026-08-25T20:00:00+00:00",
                    "external_writes_performed": False,
                },
            )
        ],
        planner=lambda _state: next(decisions),
    )

    assert result["status"] != "blocked"
    assert result["items"][0]["theme"] == "Сегодняшний пост"
    assert "Сегодняшний пост" in result["chat_response"]
    assert "approved" in result["chat_response"]
    assert result["planner_failed"] is True
    assert result["planner_error_code"] == "DEEPSEEK_EMPTY_RESPONSE"
    assert result["tool_calls"] == 1
    assert result["external_writes_performed"] is False
