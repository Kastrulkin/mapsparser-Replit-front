from core.agent_api_security import (
    BLOCKED_DIRECT_ACTIONS,
    action_requires_approval,
    classify_discovery_path,
    evaluate_agent_access,
    generate_agent_key,
    hash_agent_key,
    identify_agent_family,
    normalize_risk_level,
    public_agent_policy,
    should_track_discovery_path,
)


def test_agent_key_generation_and_hashing_are_stable():
    key = generate_agent_key("sandbox")
    assert key.startswith("localos_agent_sandbox_")
    assert hash_agent_key(key) == hash_agent_key(key)
    assert hash_agent_key(key) != hash_agent_key(key + "x")


def test_sandbox_agent_cannot_execute_high_or_critical_actions():
    client = {
        "id": "client-1",
        "status": "sandbox",
        "allowed_scopes": ["approvals:create", "finance:read"],
    }
    allowed = evaluate_agent_access(
        client,
        required_scope="finance:read",
        risk_level="low",
        action_type="read_finance",
        business_id="biz-1",
    )
    assert allowed["ok"] is True

    blocked = evaluate_agent_access(
        client,
        required_scope="approvals:create",
        risk_level="high",
        action_type="bulk_update_proposal",
        business_id="biz-1",
    )
    assert blocked["ok"] is False
    assert blocked["code"] == "SANDBOX_RISK_BLOCKED"


def test_scope_is_required_before_agent_access_is_allowed():
    client = {
        "id": "client-1",
        "status": "live",
        "allowed_scopes": ["audit:read"],
    }
    result = evaluate_agent_access(
        client,
        required_scope="finance:read",
        risk_level="low",
        action_type="read_finance",
        business_id="biz-1",
    )
    assert result["ok"] is False
    assert result["code"] == "SCOPE_REQUIRED"


def test_blocked_direct_actions_require_approval_path():
    assert "send_customer_messages" in BLOCKED_DIRECT_ACTIONS
    assert normalize_risk_level(None, "send_customer_messages") == "critical"
    assert action_requires_approval("send_customer_messages", "critical") is True

    client = {
        "id": "client-1",
        "status": "live",
        "allowed_scopes": ["publish:request"],
    }
    result = evaluate_agent_access(
        client,
        required_scope="publish:request",
        risk_level="critical",
        action_type="send_customer_messages",
        business_id="biz-1",
    )
    assert result["ok"] is False
    assert result["code"] == "DIRECT_ACTION_BLOCKED"


def test_public_agent_policy_exposes_core_contract():
    policy = public_agent_policy()
    assert policy["new_client_default_status"] == "sandbox"
    assert "approvals:create" in policy["scopes"]
    assert "publish:request" in policy["scopes"]
    assert "delete_records" in policy["blocked_direct_actions"]


def test_agent_discovery_classification_tracks_docs_and_policy_files():
    assert should_track_discovery_path("/docs/security-model") is True
    assert should_track_discovery_path("/llms.txt") is True
    assert should_track_discovery_path("/localos-agent-policy.json") is True
    assert should_track_discovery_path("/api/agent-api/security/policy") is True
    assert should_track_discovery_path("/dashboard/finance") is False
    assert classify_discovery_path("/docs") == "docs_view"
    assert classify_discovery_path("/llms.txt") == "machine_readable_docs"
    assert classify_discovery_path("/api/agent-api/ledger") == "agent_api"


def test_agent_family_detection_for_known_crawlers():
    assert identify_agent_family("GPTBot/1.0") == "openai"
    assert identify_agent_family("ClaudeBot") == "anthropic"
    assert identify_agent_family("PerplexityBot") == "perplexity"
    assert identify_agent_family("Mozilla/5.0") == "browser_or_unknown"
