from services import operator_tool_billing


def test_paid_tool_loop_charges_once_for_completed_plan(monkeypatch):
    monkeypatch.setattr(operator_tool_billing, "build_paid_action_preflight", lambda *_args, **_kwargs: {"status": "ready"})
    monkeypatch.setattr(
        operator_tool_billing,
        "reserve_paid_action_credits",
        lambda *_args, **_kwargs: {"status": "reserved", "reservation_id": "reservation-1"},
    )
    finalized = []

    def finalize(*_args, **kwargs):
        finalized.append(kwargs)
        return {"status": "charged", "charge_credits": 1}

    monkeypatch.setattr(operator_tool_billing, "finalize_reserved_action_credits", finalize)
    monkeypatch.setattr(
        operator_tool_billing,
        "run_operator_tool_loop",
        lambda **_kwargs: {"status": "completed", "capability": "services.read", "chat_response": "Готово"},
    )

    result = operator_tool_billing.run_paid_operator_tool_loop(
        object(),
        business_id="business-1",
        user_id="user-1",
        message="Проверь каталог",
        conversation_id="conversation-1",
        tools=[],
    )

    assert result["status"] == "completed"
    assert result["charged_credits"] == 1
    assert result["tool_plan_finalization_result"]["status"] == "charged"
    assert finalized[0]["finalization_mode"] == "charge"
    assert finalized[0]["actual_credits"] == 1


def test_paid_tool_loop_releases_reservation_when_provider_fails(monkeypatch):
    monkeypatch.setattr(operator_tool_billing, "build_paid_action_preflight", lambda *_args, **_kwargs: {"status": "ready"})
    monkeypatch.setattr(
        operator_tool_billing,
        "reserve_paid_action_credits",
        lambda *_args, **_kwargs: {"status": "reserved", "reservation_id": "reservation-1"},
    )
    finalized = []

    def finalize(*_args, **kwargs):
        finalized.append(kwargs)
        return {"status": "released", "charge_credits": 0, "release_credits": 1}

    monkeypatch.setattr(operator_tool_billing, "finalize_reserved_action_credits", finalize)
    monkeypatch.setattr(
        operator_tool_billing,
        "run_operator_tool_loop",
        lambda **_kwargs: {
            "status": "blocked",
            "capability": "operator.help",
            "chat_response": "Недоступно",
            "blocked_reasons": ["provider_timeout"],
        },
    )

    result = operator_tool_billing.run_paid_operator_tool_loop(
        object(),
        business_id="business-1",
        user_id="user-1",
        message="Проверь каталог",
        tools=[],
    )

    assert result["credit_charged"] is False
    assert finalized[0]["finalization_mode"] == "release"
    assert finalized[0]["actual_credits"] is None


def test_paid_tool_loop_releases_reservation_on_unexpected_failure(monkeypatch):
    monkeypatch.setattr(operator_tool_billing, "build_paid_action_preflight", lambda *_args, **_kwargs: {"status": "ready"})
    monkeypatch.setattr(
        operator_tool_billing,
        "reserve_paid_action_credits",
        lambda *_args, **_kwargs: {"status": "reserved", "reservation_id": "reservation-1"},
    )
    finalized = []

    def finalize(*_args, **kwargs):
        finalized.append(kwargs)
        return {"status": "released", "release_credits": 1}

    monkeypatch.setattr(operator_tool_billing, "finalize_reserved_action_credits", finalize)
    monkeypatch.setattr(operator_tool_billing, "run_operator_tool_loop", lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    result = operator_tool_billing.run_paid_operator_tool_loop(
        object(),
        business_id="business-1",
        user_id="user-1",
        message="Проверь каталог",
        tools=[],
    )

    assert result["status"] == "blocked"
    assert result["blocked_reasons"] == ["operator_tool_loop_failed"]
    assert finalized[0]["finalization_mode"] == "release"
