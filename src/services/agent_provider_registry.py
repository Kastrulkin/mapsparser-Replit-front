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
        {"provider": "openclaw", "state": "available", "role": "planner_or_connector"},
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
        {"provider": "openclaw", "state": "available", "role": "planner_or_connector"},
        {"provider": "native_localos", "state": "available", "role": "approved_google_sheets_executor"},
        {"provider": "composio", "state": "planned", "role": "future_google_sheets_connector"},
        {"provider": "manual", "state": "available", "role": "fallback"},
    ],
    "google_sheets.read_rows": [
        {"provider": "openclaw", "state": "available", "role": "planner_or_connector"},
        {"provider": "composio", "state": "planned", "role": "future_google_sheets_reader"},
        {"provider": "native_localos", "state": "available", "role": "native_google_sheets_reader"},
        {"provider": "manual", "state": "available", "role": "uploaded_file_or_paste"},
    ],
    "browser_use.read_page": [
        {"provider": "openclaw", "state": "available", "role": "browser_use_boundary"},
        {"provider": "manual", "state": "available", "role": "human_browser_fallback"},
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
    "browser_use": {
        "title": "Browser use",
        "description": "Supervised website reading and change monitoring through the OpenClaw browser boundary.",
        "required_config": ["target_urls"],
        "default_limits": {"daily_page_check_cap": 50, "frequency_cap_minutes": 60},
        "status": "available",
        "provider_candidates": ["openclaw", "manual"],
        "capabilities": ["browser_use.read_page"],
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


def connector_provider_routes(provider: str = "", capability: str = "") -> List[Dict[str, Any]]:
    provider_key = str(provider or "").strip()
    capability_key = str(capability or "").strip()
    routes: List[Dict[str, Any]] = []
    if provider_key:
        catalog_item = INTEGRATION_PROVIDER_CATALOG.get(provider_key, {})
        for candidate in catalog_item.get("provider_candidates", []) if isinstance(catalog_item.get("provider_candidates"), list) else []:
            route = _provider_route(str(candidate or "").strip(), "connector")
            if route:
                routes.append(route)
    if capability_key:
        for candidate in capability_provider_candidates(capability_key):
            route = _provider_route(str(candidate.get("provider") or "").strip(), str(candidate.get("role") or "capability"))
            if route:
                routes.append(route)
    return _dedupe_provider_routes(routes)


def best_provider_route_state(routes: List[Dict[str, Any]]) -> str:
    rank = {
        "connected": 0,
        "available": 1,
        "manual": 2,
        "planned": 3,
        "unavailable": 4,
    }
    best = "unavailable"
    best_rank = rank[best]
    for route in routes:
        state = str(route.get("state") or "unavailable")
        current_rank = rank.get(state, 4)
        if current_rank < best_rank:
            best = state
            best_rank = current_rank
    return best


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


def _provider_route(provider: str, role: str) -> Dict[str, Any]:
    if not provider:
        return {}
    meta = PROVIDER_REGISTRY.get(provider, {})
    status = str(meta.get("status") or "unknown")
    state = "available"
    if provider == "manual":
        state = "manual"
    elif status == "planned":
        state = "planned"
    elif status not in {"available", "ready"}:
        state = "unavailable"
    return {
        "provider": provider,
        "label": str(meta.get("label") or provider),
        "kind": str(meta.get("kind") or ""),
        "state": state,
        "status": status,
        "role": role,
        "connect_mode": _provider_connect_mode(provider),
        "primary_cta": _provider_primary_cta(provider, state),
        "provider_action": _provider_action(provider, state, role),
        "credentials_source": str(meta.get("credentials_source") or ""),
        "description": str(meta.get("description") or ""),
    }


def _provider_connect_mode(provider: str) -> str:
    if provider == "native_localos":
        return "localos_native_config"
    if provider == "maton":
        return "external_account_key"
    if provider == "openclaw":
        return "openclaw_policy_boundary"
    if provider == "composio":
        return "planned_oauth_connector"
    if provider == "manual":
        return "manual_fallback"
    return "provider_config"


def _provider_primary_cta(provider: str, state: str) -> str:
    if state == "planned":
        return "Будет доступно позже"
    if provider == "native_localos":
        return "Настроить в LocalOS"
    if provider == "maton":
        return "Выбрать Maton key"
    if provider == "openclaw":
        return "Использовать OpenClaw boundary"
    if provider == "manual":
        return "Использовать ручной режим"
    return "Настроить provider"


def _provider_action(provider: str, state: str, role: str) -> Dict[str, Any]:
    if state == "planned":
        return {
            "kind": "planned_oauth_connector" if provider == "composio" else "planned_provider",
            "available": False,
            "ui_target": "provider_roadmap",
            "label": "Будет доступно позже",
            "description": "Provider route есть в registry, но пока не может активировать агента.",
            "role": role,
        }
    if provider == "native_localos":
        return {
            "kind": "open_localos_config",
            "available": True,
            "ui_target": "agent_connections",
            "label": "Настроить в LocalOS",
            "description": "Откройте форму LocalOS для выбранного binding; preflight проверит поля перед preview.",
            "role": role,
        }
    if provider == "maton":
        return {
            "kind": "select_external_account_key",
            "available": True,
            "ui_target": "external_business_accounts",
            "label": "Выбрать Maton key",
            "description": "Используйте сохранённый Maton.ai API key как provider bridge за approval/audit boundary.",
            "role": role,
        }
    if provider == "openclaw":
        return {
            "kind": "use_openclaw_boundary",
            "available": True,
            "ui_target": "openclaw_policy_boundary",
            "label": "Использовать OpenClaw boundary",
            "description": "OpenClaw может планировать или исполнять capability только внутри LocalOS policy envelope.",
            "role": role,
        }
    if provider == "manual":
        return {
            "kind": "manual_fallback",
            "available": True,
            "ui_target": "draft_only_or_manual",
            "label": "Использовать ручной режим",
            "description": "LocalOS подготовит draft/artifacts, а внешний шаг выполнит человек.",
            "role": role,
        }
    return {
        "kind": "provider_config",
        "available": state in {"available", "connected"},
        "ui_target": "agent_connections",
        "label": "Настроить provider",
        "description": "Настройте provider route перед preflight и preview.",
        "role": role,
    }


def _dedupe_provider_routes(routes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    seen = set()
    for route in routes:
        provider = str(route.get("provider") or "")
        role = str(route.get("role") or "")
        key = (provider, role)
        if not provider or key in seen:
            continue
        seen.add(key)
        result.append(route)
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
