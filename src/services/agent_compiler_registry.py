from __future__ import annotations

from typing import Any, Dict, List

from services.agent_provider_registry import CAPABILITY_PROVIDER_MAP, INTEGRATION_PROVIDER_CATALOG
from services.communication_agent_templates import list_communication_agent_templates


SOURCE_DESTINATION_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "google_sheets_to_localos_finance": {
        "label": "Google Sheets -> LocalOS Finance",
        "category": "custom",
        "trigger": "schedule.daily",
        "source": "google_sheets",
        "destination": "localos_finance",
        "read_capability": "google_sheets.read_rows",
        "write_capability": "finance.transaction.create",
        "required_connectors": ["google_sheets", "localos_finance"],
        "approval_reasons": ["localos_finance_write", "ambiguous_data"],
        "compiled_schema": "compiled_source_destination_workflow_v1",
    },
    "telegram_to_google_sheets": {
        "label": "Telegram -> Google Sheets",
        "category": "custom",
        "trigger": "telegram.message.received",
        "source": "telegram",
        "destination": "google_sheets",
        "read_capability": "",
        "write_capability": "sheets.append_row_request",
        "required_connectors": ["telegram", "google_sheets"],
        "approval_reasons": ["external_write"],
        "compiled_schema": "compiled_source_destination_workflow_v1",
    },
    "google_sheets_to_telegram_post": {
        "label": "Google Sheets -> Telegram post draft",
        "category": "custom",
        "trigger": "schedule.daily",
        "source": "google_sheets",
        "destination": "telegram",
        "read_capability": "google_sheets.read_rows",
        "write_capability": "communications.draft",
        "required_connectors": ["google_sheets", "telegram"],
        "approval_reasons": ["telegram_post_approval", "external_publish"],
        "compiled_schema": "compiled_source_destination_workflow_v1",
    },
}


def list_compiled_agent_templates() -> List[Dict[str, Any]]:
    templates = []
    for key, value in SOURCE_DESTINATION_TEMPLATES.items():
        item = dict(value)
        item["key"] = key
        templates.append(item)
    for template in list_communication_agent_templates():
        templates.append(
            {
                "key": f"communication:{template['key']}",
                "label": str(template.get("name") or template.get("key") or "Communication agent"),
                "category": "communications",
                "trigger": str(template.get("trigger") or ""),
                "source": "manual",
                "destination": "communications",
                "read_capability": "communications.draft",
                "write_capability": str(template.get("send_capability") or ""),
                "required_connectors": ["localos_communications"],
                "approval_reasons": [str(template.get("approval_type") or "external_delivery")],
                "compiled_schema": "compiled_communications_workflow_v1",
            }
        )
    return templates


def get_compiled_agent_template(template_key: str) -> Dict[str, Any]:
    key = str(template_key or "").strip()
    for template in list_compiled_agent_templates():
        if template.get("key") == key:
            return dict(template)
    return {}


def infer_compiled_template_key(source: str, destination: str, read_capability: str = "", write_capability: str = "") -> str:
    source_key = str(source or "").strip()
    destination_key = str(destination or "").strip()
    read_key = str(read_capability or "").strip()
    write_key = str(write_capability or "").strip()
    for template in list_compiled_agent_templates():
        if template.get("source") != source_key or template.get("destination") != destination_key:
            continue
        if read_key and template.get("read_capability") != read_key:
            continue
        if write_key and template.get("write_capability") != write_key:
            continue
        return str(template.get("key") or "")
    return ""


def allowed_compiler_sources() -> set[str]:
    return {str(template.get("source") or "") for template in list_compiled_agent_templates() if template.get("source")}


def allowed_compiler_destinations() -> set[str]:
    return {str(template.get("destination") or "") for template in list_compiled_agent_templates() if template.get("destination")}


def allowed_compiler_capabilities() -> set[str]:
    capabilities = set(CAPABILITY_PROVIDER_MAP.keys())
    for template in list_compiled_agent_templates():
        for key in ["read_capability", "write_capability"]:
            capability = str(template.get(key) or "").strip()
            if capability:
                capabilities.add(capability)
    return capabilities


def allowed_compiler_connectors() -> set[str]:
    connectors = set(INTEGRATION_PROVIDER_CATALOG.keys())
    connectors.update({"localos_finance", "localos_communications", "manual"})
    return connectors


def allowed_compiler_triggers() -> set[str]:
    triggers = {"manual.run", "schedule.daily", "telegram.message.received"}
    triggers.update(str(template.get("trigger") or "") for template in list_compiled_agent_templates() if template.get("trigger"))
    return triggers


def compiled_template_prompt_lines() -> List[str]:
    lines = []
    for template in list_compiled_agent_templates():
        read_capability = str(template.get("read_capability") or "")
        write_capability = str(template.get("write_capability") or "")
        capabilities = ", ".join([item for item in [read_capability, write_capability] if item]) or "none"
        lines.append(
            f"- {template.get('key')}: source={template.get('source')}, destination={template.get('destination')}, "
            f"trigger={template.get('trigger')}, capabilities={capabilities}"
        )
    return lines
