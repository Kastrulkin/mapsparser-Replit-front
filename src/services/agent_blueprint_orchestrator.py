from core.action_orchestrator import ActionOrchestrator
from services.agent_capability_handlers import build_capability_handlers


def build_agent_blueprint_orchestrator() -> ActionOrchestrator:
    return ActionOrchestrator(build_capability_handlers())
