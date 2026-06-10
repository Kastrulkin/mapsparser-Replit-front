from services.agent_builder_billing import (
    AGENT_CREATION_ACTION_KEY,
    AGENT_CREATION_ESTIMATED_CREDITS,
    build_agent_creation_cost_preview,
)
from services.agent_builder_session import build_agent_builder_state
from services.operator_paid_actions import PAID_ACTIONS


def test_agent_creation_is_registered_paid_action():
    action = PAID_ACTIONS[AGENT_CREATION_ACTION_KEY]

    assert action["action_class"] == "paid_compute"
    assert action["cost_source"] == "model_tokens"
    assert action["external_write"] is False


def test_agent_builder_preview_exposes_creation_cost():
    state = build_agent_builder_state(
        [{"role": "user", "content": "Сделай агента, который проверяет таблицу заказов и готовит отчет."}],
        "tables",
    )

    cost_preview = state["preview"]["cost_preview"]
    assert cost_preview == build_agent_creation_cost_preview()
    assert cost_preview["action_key"] == AGENT_CREATION_ACTION_KEY
    assert cost_preview["estimated_credits"] == AGENT_CREATION_ESTIMATED_CREDITS
