from __future__ import annotations

import json
import uuid
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


def apply_legacy_ai_agent_migration(cursor, business_id: str, user_id: str) -> dict[str, Any]:
    plan = build_legacy_ai_agent_migration_plan(cursor, business_id)
    legacy_agents_by_id = {_clean_text(agent.get("id")): agent for agent in _load_legacy_ai_agents(cursor)}
    applied = []
    skipped = []
    for item in plan.get("legacy_agents") or []:
        agent_id = _clean_text(item.get("agent_id"))
        action = _clean_text(item.get("action"))
        if action == "use_as_persona":
            skipped.append({"agent_id": agent_id, "reason": "already_linked_to_blueprint"})
            continue
        if action != "create_blueprint_candidate":
            skipped.append({"agent_id": agent_id, "reason": action or "not_migratable"})
            continue
        agent = legacy_agents_by_id.get(agent_id)
        if not agent:
            skipped.append({"agent_id": agent_id, "reason": "legacy_agent_not_found"})
            continue
        existing = _find_existing_legacy_blueprint(cursor, business_id, agent_id)
        if existing:
            skipped.append({"agent_id": agent_id, "blueprint_id": existing.get("id"), "reason": "migration_already_applied"})
            continue
        migrated = _create_legacy_persona_blueprint(cursor, business_id, agent, user_id)
        applied.append(migrated)
    refreshed_plan = build_legacy_ai_agent_migration_plan(cursor, business_id)
    return {
        "business_id": business_id,
        "mode": "applied_non_destructive",
        "applied_count": len(applied),
        "skipped_count": len(skipped),
        "applied": applied,
        "skipped": skipped,
        "migration_plan": refreshed_plan,
        "deletion_ready": False,
        "deletion_note": "Legacy tables/fields are not deleted by apply. Remove only after schema migration, backup, and proof that UI/API no longer read them.",
    }


def business_has_product_agent_runtime(cursor, business_id: str) -> bool:
    if not _table_exists(cursor, "agent_blueprints"):
        return False
    cursor.execute(
        """
        SELECT 1
        FROM agent_blueprints
        WHERE business_id = %s
          AND status IN ('active', 'needs_approval')
        LIMIT 1
        """,
        (business_id,),
    )
    return cursor.fetchone() is not None


def business_agent_enabled_for_channel(cursor, business_id: str) -> dict[str, Any]:
    if business_has_product_agent_runtime(cursor, business_id):
        return {
            "enabled": True,
            "source": "agent_blueprints",
            "legacy_field_status": "deprecated_not_runtime_truth",
        }
    settings = _load_business_ai_settings(cursor, business_id)
    legacy_enabled = _truthy(settings.get("ai_agent_enabled"))
    return {
        "enabled": legacy_enabled,
        "source": "businesses.ai_agent_enabled_legacy_fallback" if legacy_enabled else "none",
        "legacy_field_status": "deprecated_migration_source",
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
        "rule": "Legacy business-level AI settings are migration sources only. Runtime should prefer agent_blueprints; channel webhooks may use deprecated fallback until migration is applied.",
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


def _find_existing_legacy_blueprint(cursor, business_id: str, agent_id: str) -> dict[str, Any] | None:
    cursor.execute(
        """
        SELECT *
        FROM agent_blueprints
        WHERE business_id = %s
          AND metadata_json->'legacy_migration'->>'source_agent_id' = %s
        LIMIT 1
        """,
        (business_id, agent_id),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def _create_legacy_persona_blueprint(cursor, business_id: str, agent: dict[str, Any], user_id: str) -> dict[str, Any]:
    agent_id = _clean_text(agent.get("id"))
    blueprint_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())
    agent_name = _clean_text(agent.get("name")) or "Legacy voice"
    workflow_text = _clean_text(agent.get("workflow"))
    metadata = {
        "builder": "legacy_ai_agent_migration_v1",
        "compiler": "legacy_persona_wrapper_v1",
        "compiled_workflow_status": "migrated_candidate",
        "draft_category": "communications",
        "legacy_migration": {
            "source": "AIAgents",
            "source_agent_id": agent_id,
            "source_agent_name": agent_name,
            "applied_at": _utc_now_text(),
            "legacy_workflow_status": LEGACY_WORKFLOW_STATUS,
            "legacy_business_fields_status": "deprecated_migration_source",
            "runtime_truth": "agent_blueprint_versions.steps_json",
        },
        "agent_setup": {
            "workflow_description": _clean_text(agent.get("task"))
            or _clean_text(agent.get("description"))
            or f"Коммуникационный агент с голосом {agent_name}",
            "data_sources": ["business_profile", "manual_context"],
            "extraction_rules": "Определить намерение клиента, нужный канал и факты, которые можно безопасно использовать.",
            "processing_rules": "Использовать persona как голос и стиль. Не исполнять legacy AIAgents.workflow как runtime.",
            "output_format": "Черновик ответа или коммуникационного действия для ручной проверки.",
            "approval_boundaries": ["final_output", "external_delivery"],
            "manual_control": "Любая внешняя отправка, запись, публикация или изменение данных требует approval.",
            "legacy_workflow_preview": workflow_text[:1000],
        },
        "agent_sources": [
            {
                "id": f"legacy-persona-{agent_id}",
                "source_type": "internal",
                "name": "Legacy persona voice",
                "internal_source": "legacy_ai_agent_persona",
                "content_text": _legacy_persona_summary(agent),
                "content_length": len(_legacy_persona_summary(agent)),
                "extraction_state": "ready",
                "extraction_method": "legacy_migration_v1",
            }
        ],
    }
    cursor.execute(
        """
        INSERT INTO agent_blueprints (
            id, business_id, name, category, description, status, created_by_user_id, metadata_json
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        """,
        (
            blueprint_id,
            business_id,
            f"{agent_name} · коммуникационный агент",
            "communications",
            "Migrated non-destructive wrapper for legacy AIAgents persona.",
            "draft",
            user_id,
            json.dumps(metadata, ensure_ascii=False),
        ),
    )
    version_payload = _legacy_persona_version_payload(agent, metadata)
    cursor.execute(
        """
        INSERT INTO agent_blueprint_versions (
            id, blueprint_id, version_number, goal, inputs_schema_json, steps_json,
            persona_agent_id, capability_allowlist_json, approval_policy_json,
            output_schema_json, created_by_user_id
        )
        VALUES (%s, %s, 1, %s, %s::jsonb, %s::jsonb, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s)
        """,
        (
            version_id,
            blueprint_id,
            version_payload["goal"],
            json.dumps(version_payload["inputs_schema"], ensure_ascii=False),
            json.dumps(version_payload["steps"], ensure_ascii=False),
            agent_id or None,
            json.dumps(version_payload["capability_allowlist"], ensure_ascii=False),
            json.dumps(version_payload["approval_policy"], ensure_ascii=False),
            json.dumps(version_payload["output_schema"], ensure_ascii=False),
            user_id,
        ),
    )
    metadata["active_version_id"] = version_id
    metadata["active_version_number"] = 1
    metadata["version_events"] = [
        {
            "action": "legacy_migration_created",
            "previous_active_version_id": "",
            "active_version_id": version_id,
            "active_version_number": 1,
            "reason": "Created from legacy AIAgents persona as blueprint runtime wrapper.",
            "created_by_user_id": user_id,
            "created_at": _utc_now_text(),
        }
    ]
    cursor.execute(
        """
        UPDATE agent_blueprints
        SET metadata_json = %s::jsonb,
            updated_at = NOW()
        WHERE id = %s
        """,
        (json.dumps(metadata, ensure_ascii=False), blueprint_id),
    )
    return {
        "agent_id": agent_id,
        "blueprint_id": blueprint_id,
        "version_id": version_id,
        "status": "created_draft_blueprint",
    }


def _legacy_persona_version_payload(agent: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    setup = metadata.get("agent_setup") if isinstance(metadata.get("agent_setup"), dict) else {}
    return {
        "goal": _clean_text(setup.get("workflow_description")) or "Коммуникационный агент из legacy persona",
        "inputs_schema": {
            "agent_setup": setup,
            "legacy_migration": metadata.get("legacy_migration"),
        },
        "steps": [
            {
                "key": "collect_inputs",
                "type": "artifact",
                "title": "Собрать входные данные",
                "artifact_type": "agent_input_plan",
                "payload": {"status": "migrated", "category": "communications"},
            },
            {
                "key": "prepare_draft",
                "type": "artifact",
                "title": "Подготовить черновик",
                "artifact_type": "agent_output_draft",
                "payload": {
                    "status": "draft",
                    "category": "communications",
                    "external_dispatch_performed": False,
                    "legacy_workflow_status": LEGACY_WORKFLOW_STATUS,
                },
            },
            {
                "key": "approve_output",
                "type": "approval",
                "title": "Подтвердить результат",
                "approval_type": "final_output",
            },
            {
                "key": "save_result",
                "type": "artifact",
                "title": "Сохранить итог",
                "artifact_type": "agent_final_result",
                "payload": {
                    "status": "pending_approval",
                    "external_dispatch_performed": False,
                    "delivery_state": "not_dispatched",
                },
            },
        ],
        "persona_agent_id": _clean_text(agent.get("id")) or None,
        "capability_allowlist": ["communications.draft"],
        "approval_policy": {
            "required_for": ["final_output", "external_delivery"],
            "legacy_workflow_runtime_truth": LEGACY_WORKFLOW_STATUS,
        },
        "output_schema": {
            "format": "communications_draft",
            "external_dispatch_performed": False,
            "legacy_workflow_runtime_truth": LEGACY_WORKFLOW_STATUS,
        },
    }


def _legacy_persona_summary(agent: dict[str, Any]) -> str:
    parts = [
        f"name: {_clean_text(agent.get('name'))}",
        f"type: {_clean_text(agent.get('type'))}",
        f"description: {_clean_text(agent.get('description'))}",
        f"personality: {_clean_text(agent.get('personality'))}",
        f"task: {_clean_text(agent.get('task'))}",
        f"identity: {_clean_text(agent.get('identity'))}",
        f"speech_style: {_clean_text(agent.get('speech_style'))}",
        f"restrictions: {_value_preview(agent.get('restrictions_json'))}",
    ]
    return "\n".join(item for item in parts if not item.endswith(": "))


def _utc_now_text() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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
