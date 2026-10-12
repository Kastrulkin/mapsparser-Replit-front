import pytest
from datetime import datetime, timezone

from services.openclaw_capability_catalog import get_openclaw_capability_catalog


def action(**fields):
    return {
        "openclaw_action_ref": "openclaw.browser.read_page",
        "localos_capability": "browser_use.read_page",
        "status": "available",
        **fields,
    }


def test_empty_live_catalog_is_not_available():
    result = get_openclaw_capability_catalog(lambda: {"actions": []})
    assert result["status"] == "empty"
    assert result["execution_ready"] is False


def test_sandbox_names_are_discovered_but_not_executable():
    result = get_openclaw_capability_catalog(
        lambda: {"capabilities": ["leads.score", "partners.enrich_contacts"]}
    )
    assert len(result["actions"]) == 2
    assert result["status"] == "discovered"
    assert all(item["status"] == "unverified" for item in result["actions"])
    assert all(not item["execution_ready"] for item in result["actions"])


@pytest.mark.parametrize("payload", [{"ok": True}, None, "html", {"actions": ["broken"]}])
def test_invalid_live_contract_is_visible(payload):
    result = get_openclaw_capability_catalog(lambda: payload)
    assert result["status"] == "invalid"
    assert result["execution_ready"] is False
    assert result["actions"] == []


@pytest.mark.parametrize("payload", [
    {"actions": [action()]},
    {"capabilities": {"browser_use.read_page": {"status": "available"}}},
])
def test_legacy_available_is_description_not_execution_proof(payload):
    result = get_openclaw_capability_catalog(lambda: payload)
    assert len(result["actions"]) == 1
    assert result["actions"][0]["described"] is True
    assert result["actions"][0]["execution_ready"] is False


def test_static_fallback_is_never_execution_authority(monkeypatch):
    for name in ("OPENCLAW_CAPABILITY_CATALOG_URL", "OPENCLAW_BASE_URL", "OPENCLAW_SANDBOX_BRIDGE_URL"):
        monkeypatch.delenv(name, raising=False)
    result = get_openclaw_capability_catalog()
    assert result["source"] == "static_fallback"
    assert result["actions"]
    assert all(not item["execution_ready"] for item in result["actions"])


def test_arbitrary_sandbox_endpoint_is_not_used(monkeypatch):
    from services import openclaw_capability_catalog
    monkeypatch.delenv("OPENCLAW_CAPABILITY_CATALOG_URL", raising=False)
    monkeypatch.delenv("OPENCLAW_BASE_URL", raising=False)
    monkeypatch.setenv("OPENCLAW_SANDBOX_BRIDGE_URL", "https://bridge.example/execute")
    monkeypatch.setattr(openclaw_capability_catalog.requests, "get", lambda *a, **k: pytest.fail("unexpected request"))
    result = get_openclaw_capability_catalog()
    assert result["source"] == "static_fallback"


def test_http_error_is_sanitized_and_non_executable():
    def fail():
        raise RuntimeError("secret-token-in-upstream-error")
    result = get_openclaw_capability_catalog(fail)
    assert "secret-token" not in str(result)
    assert result["execution_ready"] is False


def test_only_fresh_explicit_verification_is_ready():
    result = get_openclaw_capability_catalog(lambda: {"actions": [action(
        configured=True, verified=True, verified_at=datetime.now(timezone.utc).isoformat()
    )]})
    assert result["execution_ready"] is True
    assert result["actions"][0]["status"] == "available"


@pytest.mark.parametrize("stamp", ["not-a-date", "2020-01-01T00:00:00+00:00", "2999-01-01T00:00:00+00:00", "2026-10-12T00:00:00"])
def test_stale_invalid_or_future_verification_is_not_ready(stamp):
    result = get_openclaw_capability_catalog(lambda: {"actions": [action(
        configured=True, verified=True, verified_at=stamp
    )]})
    assert result["execution_ready"] is False


def test_compiler_does_not_choose_unverified_external_provider():
    from services.agent_openclaw_workflow_refs import annotate_steps_with_openclaw_action_refs
    step = {"type": "capability", "capability": "browser_use.read_page"}
    catalog = get_openclaw_capability_catalog(lambda: {"actions": [action()]})
    assert annotate_steps_with_openclaw_action_refs([step], catalog) == [step]


def test_compiler_can_bind_fresh_verified_provider():
    from services.agent_openclaw_workflow_refs import annotate_steps_with_openclaw_action_refs
    step = {"type": "capability", "capability": "browser_use.read_page"}
    catalog = get_openclaw_capability_catalog(lambda: {"actions": [action(
        configured=True, verified=True, verified_at=datetime.now(timezone.utc).isoformat()
    )]})
    result = annotate_steps_with_openclaw_action_refs([step], catalog)[0]
    assert result["provider_action_ref"] == "openclaw.browser.read_page"
    assert result["provider_policy"] == "localos_envelope"


def test_catalog_credentials_are_not_forwarded_on_redirect(monkeypatch):
    from services import openclaw_capability_catalog
    monkeypatch.setenv("OPENCLAW_CAPABILITY_CATALOG_URL", "https://openclaw.example/catalog")
    class Redirect:
        status_code = 302
        def raise_for_status(self):
            pass
        def json(self):
            pytest.fail("redirect body must not be interpreted as catalog")
    def get(url, **kwargs):
        assert kwargs["allow_redirects"] is False
        return Redirect()
    monkeypatch.setattr(openclaw_capability_catalog.requests, "get", get)
    result = get_openclaw_capability_catalog()
    assert result["execution_ready"] is False
