from __future__ import annotations

import json
from typing import Any


LEGACY_BUSINESS_AI_SETTINGS = [
    "ai_agent_enabled",
    "ai_agent_tone",
    "ai_agent_restrictions",
    "ai_agents_config",
    "ai_agent_id",
]

LEGACY_WORKFLOW_STATUS = "deprecated_not_runtime_truth"


def build_legacy_ai_agent_migration_plan(cursor, business_id: str) -> dict[str, Any]:
    linked_persona_ids = _load_linked_persona_ids(cursor, business_id)
    legacy_agents = _load_legacy_ai_agents(cursor)
    business_settings = _load_business_ai_settings(cursor, business_id)

    agent_actions = []
    for agent in legacy_agents:
        agent_id = _clean_text(agent.get("id"))
        is_linked_to_blueprint = agent_id in linked_persona_ids
        is_business_selected_voice = agent_id and agent_id == _clean_text(business_settings.get("ai_agent_id"))
        is_active = _truthy(agent.get("is_active"))
        has_voice_content = _has_voice_content(agent)
        has_legacy_workflow = bool(_clean_text(agent.get("workflow")))

        if is_linked_to_blueprint:
            action = "use_as_persona"
            reason = "AIAgents row is already referenced by agent_blueprint_versions.persona_agent_id."
        elif is_business_selected_voice:
            action = "create_blueprint_candidate"
            reason = "Business ai_agent_id points to this legacy voice, but no blueprint version references it yet."
        elif is_active and has_voice_content:
            action = "create_blueprint_candidate"
            reason = "Active legacy persona has useful voice/chat configuration and needs a communications blueprint wrapper."
        else:
            action = "archive_candidate"
            reason = "Legacy row is inactive or lacks enough voice configuration for the product agent layer."

        agent_actions.append(
            {
                "agent_id": agent_id,
                "name": _clean_text(agent.get("name")),
                "type": _clean_text(agent.get("type")),
                "action": action,
                "reason": reason,
                "blueprint_category": "communications" if action == "create_blueprint_candidate" else None,
                "persona_role": "agent_voice",
                "is_active": is_active,
                "linked_to_blueprint": is_linked_to_blueprint,
                "business_selected_voice": bool(is_business_selected_voice),
                "legacy_workflow": {
                    "present": has_legacy_workflow,
                    "status": LEGACY_WORKFLOW_STATUS,
                    "migration_target": "agent_blueprint_versions.steps_json",
                },
                "run_preview_bridge": build_legacy_run_preview_bridge(agent, business_id),
            }
        )

    return {
        "business_id": business_id,
        "mode": "read_only_migration_plan",
        "destructive_changes_allowed": False,
        "legacy_agents": agent_actions,
        "business_settings": build_business_ai_settings_deprecation_plan(business_settings),
        "deletion_rule": {
            "allowed": False,
            "required_before_delete": [
                "Alembic migration script",
                "proof that UI no longer reads deprecated field or endpoint",
                "proof that API no longer reads deprecated field or endpoint",
                "production backup before schema/data change",
            ],
        },
        "runtime_truth": {
            "agent": "agent_blueprints",
            "compiled_workflow": "agent_blueprint_versions",
            "persona": "AIAgents via persona_agent_id",
            "legacy_workflow": LEGACY_WORKFLOW_STATUS,
            "execution_boundary": "ActionOrchestrator/OpenClaw",
        },
    }


def build_business_ai_settings_deprecation_plan(settings: dict[str, Any]) -> dict[str, Any]:
    mapped = {}
    for field_name in LEGACY_BUSINESS_AI_SETTINGS:
        value = settings.get(field_name)
        mapped[field_name] = {
            "present": value not in (None, "", {}, []),
            "status": "deprecated_migration_source",
            "current_value_preview": _value_preview(value),
            "target": _business_setting_target(field_name),
        }
    return {
        "fields": mapped,
        "rule": "Legacy business-level AI settings remain backward-compatible reads until persona/blueprint migration is proven complete.",
    }


def build_legacy_run_preview_bridge(agent: dict[str, Any], business_id: str) -> dict[str, Any]:
    return {
        "source": "AIAgents legacy sandbox",
        "status": "moved_to_shared_run_preview_contract",
        "business_id": business_id,
        "persona_agent_id": _clean_text(agent.get("id")),
        "preview_contract": {
            "target_runtime": "agent_blueprints",
            "run_endpoint": "/api/agent-blueprints/<blueprint_id>/runs",
            "run_detail_endpoint": "/api/agent-runs/<run_id>",
            "external_dispatch_performed": False,
            "side_effects": "none_without_blueprint_capability_and_approval",
        },
    }


def _load_linked_persona_ids(cursor, business_id: str) -> set[str]:
    if not _table_exists(cursor, "agent_blueprint_versions"):
        return set()
    cursor.execute(
        """
        SELECT DISTINCT v.persona_agent_id
        FROM agent_blueprint_versions v
        JOIN agent_blueprints b ON b.id = v.blueprint_id
        WHERE b.business_id = %s
          AND v.persona_agent_id IS NOT NULL
          AND v.persona_agent_id <> ''
        """,
        (business_id,),
    )
    return {_clean_text(row.get("persona_agent_id")) for row in cursor.fetchall() or [] if _clean_text(row.get("persona_agent_id"))}


def _load_legacy_ai_agents(cursor) -> list[dict[str, Any]]:
    if not _table_exists(cursor, "aiagents"):
        return []
    cursor.execute(
        """
        SELECT id, name, type, description, personality, workflow, task, identity,
               speech_style, restrictions_json, variables_json, is_active, created_by,
               created_at, updated_at
        FROM AIAgents
        ORDER BY type, name
        LIMIT 500
        """
    )
    return [dict(row) for row in cursor.fetchall() or []]


def _load_business_ai_settings(cursor, business_id: str) -> dict[str, Any]:
    if not _table_exists(cursor, "businesses"):
        return {}
    available_columns = _table_columns(cursor, "businesses")
    selected_columns = [field_name for field_name in LEGACY_BUSINESS_AI_SETTINGS if field_name in available_columns]
    if not selected_columns:
        return {}
    quoted_columns = ", ".join(selected_columns)
    cursor.execute(
        f"""
        SELECT {quoted_columns}
        FROM Businesses
        WHERE id = %s
        LIMIT 1
        """,
        (business_id,),
    )
    row = cursor.fetchone()
    return dict(row) if row else {}


def _business_setting_target(field_name: str) -> str:
    targets = {
        "ai_agent_enabled": "agent_blueprints.status",
        "ai_agent_tone": "AIAgents.speech_style or agent_blueprint_versions.persona",
        "ai_agent_restrictions": "AIAgents.restrictions_json or agent_blueprint_versions.approval_policy_json",
        "ai_agents_config": "agent_blueprints.metadata_json.agent_setup",
        "ai_agent_id": "agent_blueprint_versions.persona_agent_id",
    }
    return targets.get(field_name, "agent_blueprints.metadata_json")


def _table_exists(cursor, table_name: str) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = %s
        LIMIT 1
        """,
        (table_name,),
    )
    return cursor.fetchone() is not None


def _table_columns(cursor, table_name: str) -> set[str]:
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
        """,
        (table_name,),
    )
    return {_clean_text(row.get("column_name")) for row in cursor.fetchall() or []}


def _has_voice_content(agent: dict[str, Any]) -> bool:
    for field_name in ("personality", "task", "identity", "speech_style", "description"):
        if _clean_text(agent.get(field_name)):
            return True
    if _parse_json(agent.get("restrictions_json"), {}):
        return True
    if _parse_json(agent.get("variables_json"), {}):
        return True
    return False


def _parse_json(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return fallback
    return fallback


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    text = _clean_text(value).lower()
    if text in {"1", "true", "yes", "y", "on", "active"}:
        return True
    if text in {"0", "false", "no", "n", "off", "inactive"}:
        return False
    return bool(value)


def _value_preview(value: Any) -> Any:
    if isinstance(value, str) and len(value) > 160:
        return f"{value[:157]}..."
    return value


def _clean_text(value: Any) -> str:
    return str(value or "").strip()
