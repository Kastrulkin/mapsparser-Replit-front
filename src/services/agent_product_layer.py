from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List


def parse_persona_row(row: Dict[str, Any] | None) -> Dict[str, Any] | None:
    if not row:
        return None
    persona_id = _clean_text(row.get("id"))
    if not persona_id:
        return None
    return {
        "id": persona_id,
        "kind": "persona",
        "source": "AIAgents",
        "role": "agent_voice",
        "name": _clean_text(row.get("name")) or "Голос агента",
        "type": _clean_text(row.get("type")),
        "description": _clean_text(row.get("description")),
        "personality": _clean_text(row.get("personality")),
        "identity": _clean_text(row.get("identity")),
        "speech_style": _clean_text(row.get("speech_style")),
        "restrictions": _parse_json(row.get("restrictions_json"), {}),
        "variables": _parse_json(row.get("variables_json"), {}),
        "is_active": _truthy(row.get("is_active")),
    }


def collect_persona_agent_ids(*collections: Iterable[Dict[str, Any]]) -> List[str]:
    result = []
    seen = set()
    for collection in collections:
        for item in collection or []:
            for key in ("persona_agent_id", "latest_persona_agent_id", "active_persona_agent_id"):
                persona_id = _clean_text(item.get(key))
                if persona_id and persona_id not in seen:
                    seen.add(persona_id)
                    result.append(persona_id)
    return result


def build_product_agent_view(
    blueprint: Dict[str, Any],
    active_version: Dict[str, Any] | None = None,
    persona: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    metadata = _parse_json(blueprint.get("metadata_json"), {})
    category = _clean_text(blueprint.get("category")) or "custom"
    active_version_id = _clean_text((active_version or {}).get("id"))
    active_version_number = _safe_int((active_version or {}).get("version_number"))
    persona_id = _clean_text((active_version or {}).get("persona_agent_id"))
    return {
        "id": _clean_text(blueprint.get("id")),
        "kind": "agent",
        "source": "agent_blueprints",
        "name": _clean_text(blueprint.get("name")) or "LocalOS агент",
        "category": category,
        "description": _clean_text(blueprint.get("description")),
        "status": _clean_text(blueprint.get("status")) or "draft",
        "blueprint_id": _clean_text(blueprint.get("id")),
        "active_version_id": active_version_id,
        "active_version_number": active_version_number,
        "persona_agent_id": persona_id or None,
        "persona": persona,
        "voice": persona,
        "components": {
            "blueprint": {
                "id": _clean_text(blueprint.get("id")),
                "category": category,
            },
            "persona": {
                "id": persona_id,
                "source": "AIAgents",
                "role": "agent_voice",
                "optional": True,
                "attached": bool(persona),
            },
            "compiled_workflow": {
                "version_id": active_version_id,
                "version_number": active_version_number,
            },
        },
        "legacy": {
            "ai_agents_role": "voice_persona",
            "communication_agent_is_blueprint_category": True,
        },
        "metadata": {
            "agent_setup": metadata.get("agent_setup") if isinstance(metadata.get("agent_setup"), dict) else {},
            "builder": _clean_text(metadata.get("builder")),
            "compiler": _clean_text(metadata.get("compiler")),
        },
    }


def attach_product_agent_to_blueprint(
    blueprint: Dict[str, Any],
    active_version: Dict[str, Any] | None = None,
    personas_by_id: Dict[str, Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    result = dict(blueprint)
    personas = personas_by_id or {}
    persona_id = _clean_text((active_version or {}).get("persona_agent_id"))
    persona = personas.get(persona_id) if persona_id else None
    result["product_agent"] = build_product_agent_view(result, active_version, persona)
    result["persona"] = persona
    result["voice"] = persona
    return result


def attach_persona_to_version(
    version: Dict[str, Any],
    personas_by_id: Dict[str, Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    result = dict(version)
    persona_id = _clean_text(result.get("persona_agent_id"))
    persona = (personas_by_id or {}).get(persona_id) if persona_id else None
    result["persona"] = persona
    result["voice"] = persona
    return result


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


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _clean_text(value: Any) -> str:
    return str(value or "").strip()
