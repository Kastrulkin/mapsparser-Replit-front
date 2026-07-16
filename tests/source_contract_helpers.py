from pathlib import Path


def read_agent_blueprints_frontend_source() -> str:
    paths = [Path("frontend/src/pages/dashboard/AgentBlueprintsPage.tsx")]
    paths.extend(sorted(Path("frontend/src/pages/dashboard/agents").glob("*.ts")))
    paths.extend(sorted(Path("frontend/src/pages/dashboard/agents").glob("*.tsx")))
    return "\n".join(path.read_text(encoding="utf-8") for path in paths)
