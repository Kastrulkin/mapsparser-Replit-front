from __future__ import annotations

import os
from typing import Any, Callable, Dict, List

import requests

from services.agent_provider_registry import capability_provider_candidates


OpenClawCatalogFetcher = Callable[[], Any]


STATIC_OPENCLAW_CAPABILITY_FALLBACK: List[Dict[str, Any]] = [
    {
        "openclaw_action_ref": "openclaw.google_sheets.read_rows",
        "title": "Read Google Sheets rows",
        "service": "google_sheets",
        "localos_capability": "google_sheets.read_rows",
        "risk_class": "read",
        "required_auth": ["google_sheets"],
        "approval_class": "none",
        "side_effect": "none",
        "status": "available",
    },
    {
        "openclaw_action_ref": "openclaw.google_sheets.append_row",
        "title": "Append Google Sheets row",
        "service": "google_sheets",
        "localos_capability": "sheets.append_row_request",
        "risk_class": "external_write",
        "required_auth": ["google_sheets"],
        "approval_class": "external_write",
        "side_effect": "external_write",
        "status": "available",
    },
    {
        "openclaw_action_ref": "openclaw.telegram.publish_message",
        "title": "Publish Telegram message",
        "service": "telegram",
        "localos_capability": "communications.send_offer",
        "risk_class": "external_publish",
        "required_auth": ["telegram"],
        "approval_class": "external_publish",
        "side_effect": "external_send",
        "status": "available",
    },
    {
        "openclaw_action_ref": "openclaw.telegram.create_draft",
        "title": "Create Telegram draft",
        "service": "telegram",
        "localos_capability": "communications.draft",
        "risk_class": "draft",
        "required_auth": ["telegram"],
        "approval_class": "none",
        "side_effect": "none",
        "status": "available",
    },
    {
        "openclaw_action_ref": "openclaw.browser.read_page",
        "title": "Read website page",
        "service": "browser",
        "localos_capability": "browser_use.read_page",
        "risk_class": "read",
        "required_auth": [],
        "approval_class": "none",
        "side_effect": "none",
        "status": "available",
    },
    {
        "openclaw_action_ref": "openclaw.maton.send_message",
        "title": "Send message through Maton bridge",
        "service": "maton",
        "localos_capability": "communications.send_offer",
        "risk_class": "external_send",
        "required_auth": ["maton"],
        "approval_class": "external_send",
        "side_effect": "external_send",
        "status": "available",
    },
]


def get_openclaw_capability_catalog(fetcher: OpenClawCatalogFetcher | None = None) -> Dict[str, Any]:
    source = "static_fallback"
    raw_catalog: Any = None
    catalog_fetcher = fetcher or _configured_openclaw_catalog_fetcher()
    if catalog_fetcher:
        try:
            raw_catalog = catalog_fetcher()
            source = "openclaw"
        except Exception:
            return {
                "schema": "localos_openclaw_capability_catalog_v1",
                "source": "static_fallback",
                "status": "fallback",
                "error": "OpenClaw catalog request failed",
                "discovery": {
                    "mode": "static_fallback",
                    "provider_paths_preserved": True,
                },
                "actions": _normalize_catalog(STATIC_OPENCLAW_CAPABILITY_FALLBACK),
            }
    actions = _normalize_catalog(raw_catalog if raw_catalog is not None else STATIC_OPENCLAW_CAPABILITY_FALLBACK)
    return {
        "schema": "localos_openclaw_capability_catalog_v1",
        "source": source,
        "status": "available" if source == "openclaw" else "fallback",
        "discovery": {
            "mode": "live_http" if source == "openclaw" else "static_fallback",
            "provider_paths_preserved": True,
        },
        "actions": actions,
    }


def _normalize_catalog(raw_catalog: Any) -> List[Dict[str, Any]]:
    if isinstance(raw_catalog, dict):
        if isinstance(raw_catalog.get("actions"), list):
            raw_actions = raw_catalog.get("actions") or []
        elif isinstance(raw_catalog.get("capabilities"), dict):
            raw_actions = _actions_from_capabilities(raw_catalog.get("capabilities") or {})
        else:
            raw_actions = []
    elif isinstance(raw_catalog, list):
        raw_actions = raw_catalog
    else:
        raw_actions = []
    result: List[Dict[str, Any]] = []
    for item in raw_actions:
        if not isinstance(item, dict):
            continue
        normalized = _normalize_action(item)
        if normalized:
            result.append(normalized)
    return result


def _configured_openclaw_catalog_fetcher() -> OpenClawCatalogFetcher | None:
    url = str(os.getenv("OPENCLAW_CAPABILITY_CATALOG_URL") or "").strip()
    if not url:
        base_url = str(os.getenv("OPENCLAW_BASE_URL") or "").strip().rstrip("/")
        if base_url:
            url = f"{base_url}/api/openclaw/capabilities/catalog"
    token = str(os.getenv("OPENCLAW_LOCALOS_TOKEN") or os.getenv("OPENCLAW_TOKEN") or "").strip()
    if not url:
        return None

    def _fetch() -> Any:
        headers = {"Accept": "application/json"}
        if token:
            headers["X-OpenClaw-Token"] = token
            headers["X-OpenClaw-Internal-Token"] = token
            headers["Authorization"] = f"Bearer {token}"
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and payload.get("success") is False:
            raise RuntimeError(str(payload.get("error") or "OpenClaw catalog request failed"))
        return payload

    return _fetch


def _actions_from_capabilities(capabilities: Dict[str, Any]) -> List[Dict[str, Any]]:
    actions = []
    for capability, meta in capabilities.items():
        if not isinstance(meta, dict):
            continue
        canonical = str(meta.get("alias_for") or capability or "").strip()
        if not canonical:
            continue
        actions.append(
            {
                "openclaw_action_ref": str(meta.get("openclaw_action_ref") or _default_action_ref(canonical)),
                "title": str(meta.get("title") or meta.get("name") or canonical),
                "service": _service_from_capability(canonical),
                "localos_capability": canonical,
                "risk_class": str(meta.get("risk") or meta.get("risk_class") or "unknown"),
                "required_auth": _required_auth_from_capability(canonical, meta),
                "approval_class": _approval_class(canonical, meta),
                "side_effect": _side_effect_from_meta(meta),
                "status": _status_from_provider_candidates(canonical, meta),
                "provider_candidates": _provider_candidates_from_meta(canonical, meta),
            }
        )
    return actions


def _normalize_action(item: Dict[str, Any]) -> Dict[str, Any]:
    action_ref = str(
        item.get("openclaw_action_ref")
        or item.get("action_ref")
        or item.get("name")
        or item.get("id")
        or ""
    ).strip()
    capability = str(item.get("localos_capability") or item.get("capability") or "").strip()
    if not action_ref or not capability:
        return {}
    required_auth = item.get("required_auth") if isinstance(item.get("required_auth"), list) else []
    provider_candidates = _provider_candidates_from_meta(capability, item)
    return {
        "openclaw_action_ref": action_ref,
        "title": str(item.get("title") or item.get("label") or action_ref),
        "service": str(item.get("service") or item.get("provider") or ""),
        "localos_capability": capability,
        "risk_class": str(item.get("risk_class") or item.get("risk") or "unknown"),
        "required_auth": [str(value) for value in required_auth if str(value or "").strip()],
        "approval_class": str(item.get("approval_class") or item.get("approval") or "none"),
        "side_effect": str(item.get("side_effect") or "unknown"),
        "status": str(item.get("status") or "available"),
        "provider": "openclaw",
        "provider_candidates": provider_candidates,
        "provider_paths": _provider_paths(provider_candidates),
    }


def _provider_candidates_from_meta(capability: str, meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw_candidates = meta.get("provider_candidates")
    if not isinstance(raw_candidates, list):
        raw_candidates = meta.get("providers") if isinstance(meta.get("providers"), list) else []
    candidates: List[Dict[str, Any]] = []
    for item in raw_candidates:
        if not isinstance(item, dict):
            continue
        provider = str(item.get("provider") or item.get("name") or "").strip()
        if not provider:
            continue
        candidates.append(
            {
                "provider": provider,
                "state": str(item.get("state") or item.get("status") or "available"),
                "role": str(item.get("role") or item.get("kind") or ""),
            }
        )
    if not candidates:
        candidates = capability_provider_candidates(capability)
    return _dedupe_provider_candidates(candidates)


def _provider_paths(provider_candidates: List[Dict[str, Any]]) -> List[str]:
    result = []
    for item in provider_candidates:
        provider = str(item.get("provider") or "").strip()
        state = str(item.get("state") or "").strip()
        if provider and state:
            result.append(f"{provider}:{state}")
        elif provider:
            result.append(provider)
    return result


def _status_from_provider_candidates(capability: str, meta: Dict[str, Any]) -> str:
    explicit = str(meta.get("status") or "").strip()
    if explicit:
        return explicit
    states = {str(item.get("state") or "").strip() for item in _provider_candidates_from_meta(capability, meta)}
    if "available" in states:
        return "available"
    if "planned" in states:
        return "planned"
    return "available"


def _dedupe_provider_candidates(values: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result = []
    seen = set()
    for item in values:
        provider = str(item.get("provider") or "").strip()
        state = str(item.get("state") or item.get("provider_status") or "").strip() or "available"
        role = str(item.get("role") or "").strip()
        key = (provider, state, role)
        if not provider or key in seen:
            continue
        seen.add(key)
        result.append({"provider": provider, "state": state, "role": role})
    return result


def _default_action_ref(capability: str) -> str:
    explicit = {
        "google_sheets.read_rows": "openclaw.google_sheets.read_rows",
        "sheets.append_row_request": "openclaw.google_sheets.append_row",
        "communications.draft": "openclaw.telegram.create_draft",
        "communications.send_offer": "openclaw.telegram.publish_message",
        "communications.send_reminder": "openclaw.telegram.publish_message",
    }
    capability_key = str(capability or "").strip()
    return explicit.get(capability_key, f"openclaw.{capability_key}")


def _service_from_capability(capability: str) -> str:
    capability_key = str(capability or "").strip()
    if capability_key.startswith("google_sheets") or capability_key.startswith("sheets."):
        return "google_sheets"
    if capability_key.startswith("communications."):
        return "telegram"
    if capability_key.startswith("finance."):
        return "localos_finance"
    return capability_key.split(".", 1)[0] if "." in capability_key else capability_key


def _required_auth_from_capability(capability: str, meta: Dict[str, Any]) -> List[str]:
    auth = meta.get("required_auth")
    if isinstance(auth, list):
        return [str(value) for value in auth if str(value or "").strip()]
    service = _service_from_capability(capability)
    if service in {"google_sheets", "telegram", "maton"}:
        return [service]
    return []


def _approval_class(capability: str, meta: Dict[str, Any]) -> str:
    if meta.get("approval_class"):
        return str(meta.get("approval_class") or "")
    if bool(meta.get("approval_required")):
        return str(meta.get("risk") or "approval_required")
    return "none"


def _side_effect_from_meta(meta: Dict[str, Any]) -> str:
    text = str(meta.get("side_effects") or meta.get("side_effect") or "").strip()
    if not text or text == "none":
        return "none"
    if "none" in text and "unless" not in text:
        return "none"
    return text


def openclaw_actions_for_capability(catalog: Dict[str, Any], capability: str) -> List[Dict[str, Any]]:
    capability_key = str(capability or "").strip()
    actions = catalog.get("actions") if isinstance(catalog.get("actions"), list) else []
    return [
        dict(action)
        for action in actions
        if isinstance(action, dict) and str(action.get("localos_capability") or "").strip() == capability_key
    ]
