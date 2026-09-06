"""One explicit ownership registry for durable worker loops.

The registry does not start containers or perform a cutover.  It makes the
runtime role selected by a container inspectable and prevents a typo from
silently creating a worker that owns no queue.
"""
from __future__ import annotations

import os


ROLE_ALIASES = {
    "parser": frozenset({"parser", "parsers"}),
    "agent": frozenset({"agent", "agents", "script"}),
    "operator": frozenset({"operator", "operators"}),
    "dispatcher": frozenset({"dispatcher", "dispatch"}),
    "maintenance": frozenset({"maintenance", "maint"}),
    "general": frozenset({"general", "legacy"}),
}
WORKER_ROLES = frozenset(ROLE_ALIASES)


def configured_worker_role(value: str | None = None) -> str:
    configured = str(value if value is not None else os.getenv("WORKER_ROLE", "all")).strip().lower()
    if configured in {"", "all"}:
        return "all"
    for role, aliases in ROLE_ALIASES.items():
        if configured in aliases:
            return role
    raise ValueError(f"unknown WORKER_ROLE: {configured}")


def worker_role_enabled(role: str, configured: str | None = None) -> bool:
    normalized = configured_worker_role(configured)
    if role not in WORKER_ROLES:
        raise ValueError(f"unknown worker ownership role: {role}")
    return normalized == "all" or normalized == role
