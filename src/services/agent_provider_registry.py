from __future__ import annotations

from typing import Any, Dict, List


PROVIDER_REGISTRY: Dict[str, Dict[str, Any]] = {
    "native_localos": {
        "label": "LocalOS",
        "kind": "native",
        "status": "available",
        "credentials_source": "localos_domain_data",
        "description": "Reads and writes LocalOS domain records behind policy, approval, audit and billing.",
    },
    "maton": {
        "label": "Maton.ai",
        "kind": "connector_provider",
        "status": "available",
        "credentials_source": "externalbusinessaccounts:maton",
        "description": "User-provided Maton.ai API key for outbound channel and connector bridge actions.",
    },
    "openclaw": {
        "label": "OpenClaw",
        "kind": "execution_boundary_or_connector",
        "status": "available",
        "credentials_source": "openclaw_m2m",
        "description": "ActionOrchestrator/OpenClaw capability boundary with callbacks, ledger, limits and support export.",
    },
    "composio": {
        "label": "Composio",
        "kind": "connector_provider",
        "status": "planned",
        "credentials_source": "composio_connected_accounts",
        "description": "Future OAuth/tool provider for broad SaaS connectors such as Gmail, Sheets, Notion, Slack and HubSpot.",
    },
    "manual": {
        "label": "Manual handoff",
        "kind": "manual",
        "status": "available",
        "credentials_source": "none",
        "description": "Draft-only or human-operated fallback when no provider is ready for external execution.",
    },
}


CAPABILITY_PROVIDER_MAP: Dict[str, List[Dict[str, Any]]] = {
    "outreach.send_batch": [
        {"provider": "openclaw", "state": "available", "role": "preferred_boundary"},
        {"provider": "maton", "state": "available", "role": "delivery_bridge"},
        {"provider": "manual", "state": "available", "role": "fallback"},
    ],
    "reviews.reply.draft": [
        {"provider": "native_localos", "state": "available", "role": "draft_store"},
    ],
    "reviews.reply.publish_request": [
        {"provider": "native_localos", "state": "available", "role": "publish_request_store"},
        {"provider": "openclaw", "state": "available", "role": "approval_boundary"},
        {"provider": "composio", "state": "planned", "role": "future_provider_write"},
        {"provider": "manual", "state": "available", "role": "fallback"},
    ],
    "services.optimize": [
        {"provider": "native_localos", "state": "available", "role": "suggestion_store"},
    ],
    "news.generate": [
        {"provider": "native_localos", "state": "available", "role": "draft_store"},
    ],
    "appointments.read": [
        {"provider": "native_localos", "state": "available", "role": "domain_read"},
        {"provider": "composio", "state": "planned", "role": "external_calendar_or_crm_read"},
    ],
    "appointments.create_request": [
        {"provider": "native_localos", "state": "available", "role": "request_store"},
        {"provider": "composio", "state": "planned", "role": "external_calendar_or_crm_write"},
        {"provider": "manual", "state": "available", "role": "fallback"},
    ],
    "communications.draft": [
        {"provider": "native_localos", "state": "available", "role": "draft_store"},
    ],
    "communications.send_reminder": [
        {"provider": "openclaw", "state": "available", "role": "approval_boundary"},
        {"provider": "maton", "state": "available", "role": "delivery_bridge"},
        {"provider": "native_localos", "state": "available", "role": "telegram_or_waba_channel"},
        {"provider": "composio", "state": "planned", "role": "future_channel_connector"},
        {"provider": "manual", "state": "available", "role": "fallback"},
    ],
    "communications.send_offer": [
        {"provider": "openclaw", "state": "available", "role": "approval_boundary"},
        {"provider": "maton", "state": "available", "role": "delivery_bridge"},
        {"provider": "native_localos", "state": "available", "role": "telegram_or_waba_channel"},
        {"provider": "composio", "state": "planned", "role": "future_channel_connector"},
        {"provider": "manual", "state": "available", "role": "fallback"},
    ],
    "support.export": [
        {"provider": "openclaw", "state": "available", "role": "support_bundle"},
        {"provider": "native_localos", "state": "available", "role": "agent_run_export"},
    ],
    "sheets.append_row_request": [
        {"provider": "native_localos", "state": "available", "role": "approved_google_sheets_executor"},
        {"provider": "composio", "state": "planned", "role": "future_google_sheets_connector"},
        {"provider": "manual", "state": "available", "role": "fallback"},
    ],
    "google_sheets.read_rows": [
        {"provider": "composio", "state": "planned", "role": "future_google_sheets_reader"},
        {"provider": "native_localos", "state": "available", "role": "native_google_sheets_reader"},
        {"provider": "manual", "state": "available", "role": "uploaded_file_or_paste"},
    ],
    "finance.transaction.create": [
        {"provider": "native_localos", "state": "available", "role": "domain_write_request"},
        {"provider": "manual", "state": "available", "role": "approval_queue"},
    ],
    "billing.reserve": [
        {"provider": "native_localos", "state": "available", "role": "credit_reservation"},
        {"provider": "openclaw", "state": "available", "role": "ledger_boundary"},
    ],
    "billing.settle": [
        {"provider": "native_localos", "state": "available", "role": "credit_settlement"},
        {"provider": "openclaw", "state": "available", "role": "ledger_boundary"},
    ],
}


INTEGRATION_PROVIDER_CATALOG: Dict[str, Dict[str, Any]] = {
    "google_sheets": {
        "title": "Google Sheets",
        "description": "Controlled read/write boundary for spreadsheet workflows.",
        "required_config": ["spreadsheet_id", "sheet_name"],
        "default_limits": {"daily_append_cap": 50, "frequency_cap_minutes": 0},
        "status": "available",
        "provider_candidates": ["native_localos", "composio", "manual"],
        "capabilities": ["sheets.append_row_request", "google_sheets.read_rows"],
    },
    "telegram": {
        "title": "Telegram",
        "description": "Inbound trigger and supervised delivery through LocalOS channel router.",
        "required_config": ["bot_mode"],
        "default_limits": {"daily_message_cap": 50, "frequency_cap_minutes": 30},
        "status": "available",
        "provider_candidates": ["native_localos", "maton", "openclaw"],
        "capabilities": ["communications.draft", "communications.send_reminder", "communications.send_offer"],
    },
    "maton": {
        "title": "Maton.ai",
        "description": "Connector bridge using the Maton.ai API key saved in LocalOS integrations.",
        "required_config": ["channel"],
        "default_limits": {"daily_message_cap": 50, "frequency_cap_minutes": 30},
        "status": "available",
        "provider_candidates": ["maton"],
        "capabilities": ["communications.send_reminder", "communications.send_offer", "outreach.send_batch"],
    },
    "localos_finance": {
        "title": "Финансы LocalOS",
        "description": "LocalOS finance destination for approved transaction creation workflows.",
        "required_config": ["transaction_type"],
        "default_limits": {"daily_transaction_cap": 100},
        "status": "available",
        "provider_candidates": ["native_localos", "manual"],
        "capabilities": ["finance.transaction.create"],
    },
    "composio": {
        "title": "Composio",
        "description": "Future OAuth connector marketplace for broad SaaS tools.",
        "required_config": ["toolkit"],
        "default_limits": {"daily_action_cap": 50, "frequency_cap_minutes": 0},
        "status": "planned",
        "provider_candidates": ["composio"],
        "capabilities": ["google_sheets.read_rows", "sheets.append_row_request"],
    },
}


def get_provider_registry() -> Dict[str, Dict[str, Any]]:
    return {key: dict(value) for key, value in PROVIDER_REGISTRY.items()}


def provider_label(provider: str) -> str:
    item = PROVIDER_REGISTRY.get(str(provider or "").strip())
    if not item:
        return str(provider or "").strip() or "integration"
    return str(item.get("label") or provider)


def capability_provider_candidates(capability: str) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for item in CAPABILITY_PROVIDER_MAP.get(str(capability or "").strip(), []):
        provider = str(item.get("provider") or "").strip()
        provider_meta = PROVIDER_REGISTRY.get(provider, {})
        enriched = dict(item)
        enriched["provider_label"] = str(provider_meta.get("label") or provider)
        enriched["provider_kind"] = str(provider_meta.get("kind") or "")
        enriched["provider_status"] = str(provider_meta.get("status") or "")
        result.append(enriched)
    return result


def integration_provider_catalog() -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for provider, meta in INTEGRATION_PROVIDER_CATALOG.items():
        item = dict(meta)
        item["provider"] = provider
        item["providers"] = [
            {
                "provider": candidate,
                "label": provider_label(candidate),
                "status": str(PROVIDER_REGISTRY.get(candidate, {}).get("status") or "unknown"),
            }
            for candidate in item.get("provider_candidates", [])
        ]
        result.append(item)
    return result


def integration_execution_boundary(provider: str) -> Dict[str, Any]:
    provider_key = str(provider or "").strip()
    item = INTEGRATION_PROVIDER_CATALOG.get(provider_key, {})
    capabilities = item.get("capabilities") if isinstance(item.get("capabilities"), list) else []
    executor = "provider_resolver"
    external_write = "approval_required"
    if provider_key == "google_sheets":
        executor = "agent_sheet_provider_executor_v1"
        external_write = "approved_append_row"
    elif provider_key == "telegram":
        executor = "channel_router"
        external_write = "approved_delivery_only"
    elif provider_key == "maton":
        executor = "channel_router"
        external_write = "approved_delivery_bridge"
    elif provider_key == "localos_finance":
        executor = "localos_finance_request_executor"
        external_write = "approved_localos_write"
    elif provider_key == "composio":
        executor = "composio_connector_provider"
        external_write = "planned_provider_write"
    return {
        "capabilities": [str(value) for value in capabilities],
        "approval_required": True,
        "executor": executor,
        "external_write": external_write,
        "provider_candidates": item.get("provider_candidates", []),
    }
