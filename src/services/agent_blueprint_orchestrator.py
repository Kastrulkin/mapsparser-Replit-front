from core.action_orchestrator import ActionOrchestrator
from services.outreach_send_capability import (
    OUTREACH_SEND_BATCH_CAPABILITY,
    handle_outreach_send_batch,
)


def build_agent_blueprint_orchestrator() -> ActionOrchestrator:
    return ActionOrchestrator(
        {
            OUTREACH_SEND_BATCH_CAPABILITY: handle_outreach_send_batch,
        }
    )
