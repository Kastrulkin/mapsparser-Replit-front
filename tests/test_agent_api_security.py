from core.agent_api_security import (
    BLOCKED_DIRECT_ACTIONS,
    action_requires_approval,
    build_agent_self_test_summary,
    classify_discovery_path,
    evaluate_agent_access,
    generate_agent_key,
    hash_agent_key,
    identify_agent_family,
    normalize_risk_level,
    public_agent_policy,
    should_track_discovery_path,
)
from core.telegram_agent_transport import (
    classify_telegram_sender,
    parse_trusted_telegram_agent_bots,
    should_accept_telegram_agent_message,
    telegram_bot_to_bot_policy_decision,
)
from flask import Flask
import api.agent_security_api as agent_security_api


class FakeAgentCursor:
    def execute(self, _sql, _params=None):
        return None


class FakeAgentDb:
    def __init__(self):
        self.conn = self
        self.committed = False
        self.closed = False
        self.cursor_instance = FakeAgentCursor()

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


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
    assert should_track_discovery_path("/localos-agent-tools.json") is True
    assert should_track_discovery_path("/localos-agent-openapi.json") is True
    assert should_track_discovery_path("/api/agent-api/security/policy") is True
    assert should_track_discovery_path("/dashboard/finance") is False
    assert classify_discovery_path("/docs") == "docs_view"
    assert classify_discovery_path("/llms.txt") == "machine_readable_docs"
    assert classify_discovery_path("/localos-agent-openapi.json") == "machine_readable_docs"
    assert classify_discovery_path("/api/agent-api/ledger") == "agent_api"


def test_agent_self_test_summary_is_safe_and_scope_aware():
    client = {
        "id": "client-1",
        "organization_name": "Sandbox Agent",
        "status": "sandbox",
        "allowed_scopes": ["audit:read", "reviews:draft", "approvals:create"],
    }
    access = {"ok": True, "code": "OK", "reason": ""}

    summary = build_agent_self_test_summary(client, access)

    assert summary["client"]["client_id"] == "client-1"
    assert summary["client"]["status"] == "sandbox"
    assert summary["available"]["read_scopes"] == ["audit:read"]
    assert summary["available"]["draft_scopes"] == ["reviews:draft", "approvals:create"]
    assert summary["available"]["can_create_approval_request"] is True
    assert summary["available"]["live_external_execution"] is False
    assert "send_customer_messages" in summary["blocked_direct_actions"]


def test_agent_self_test_endpoint_records_safe_ledger(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(agent_security_api.agent_security_bp)
    fake_db = FakeAgentDb()
    monkeypatch.setattr(agent_security_api, "DatabaseManager", lambda: fake_db)
    monkeypatch.setattr(
        agent_security_api,
        "_load_agent_client",
        lambda _cursor: {
            "id": "client-1",
            "organization_name": "Sandbox Agent",
            "status": "sandbox",
            "allowed_scopes": ["audit:read", "approvals:create"],
        },
    )
    monkeypatch.setattr(agent_security_api, "log_agent_action", lambda _cursor, **_kwargs: "ledger-1")

    response = app.test_client().post(
        "/api/agent-api/self-test",
        headers={"X-LocalOS-Agent-Key": "localos_agent_sandbox_test"},
        json={"purpose": "test"},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["ledger_id"] == "ledger-1"
    assert payload["self_test"]["client"]["status"] == "sandbox"
    assert fake_db.committed is True
    assert fake_db.closed is True


def test_agent_self_test_endpoint_rejects_missing_key(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(agent_security_api.agent_security_bp)
    fake_db = FakeAgentDb()
    monkeypatch.setattr(agent_security_api, "DatabaseManager", lambda: fake_db)
    monkeypatch.setattr(agent_security_api, "_load_agent_client", lambda _cursor: None)
    monkeypatch.setattr(agent_security_api, "log_agent_action", lambda _cursor, **_kwargs: "ledger-denied")

    response = app.test_client().post("/api/agent-api/self-test", json={"purpose": "test"})
    payload = response.get_json()

    assert response.status_code == 401
    assert payload["success"] is False
    assert payload["code"] == "AGENT_AUTH_REQUIRED"
    assert fake_db.committed is True
    assert fake_db.closed is True


def test_agent_family_detection_for_known_crawlers():
    assert identify_agent_family("GPTBot/1.0") == "openai"
    assert identify_agent_family("ClaudeBot") == "anthropic"
    assert identify_agent_family("PerplexityBot") == "perplexity"
    assert identify_agent_family("Mozilla/5.0") == "browser_or_unknown"


def test_telegram_bot_to_bot_sender_classification_and_guardrails():
    update = {
        "message": {
            "message_id": 10,
            "from": {"id": 777, "is_bot": True, "username": "PartnerAgentBot"},
            "chat": {"id": 555},
        }
    }
    sender = classify_telegram_sender(update, local_bot_username="LocalOSBot")
    assert sender["sender_type"] == "telegram_bot"
    assert sender["username"] == "PartnerAgentBot"

    denied = should_accept_telegram_agent_message(sender, trusted_bot_usernames=set(), hop_count=0)
    assert denied["ok"] is False
    assert denied["code"] == "UNKNOWN_TELEGRAM_BOT"

    allowed = should_accept_telegram_agent_message(sender, trusted_bot_usernames={"partneragentbot"}, hop_count=1)
    assert allowed["ok"] is True

    loop_block = should_accept_telegram_agent_message(sender, trusted_bot_usernames={"partneragentbot"}, hop_count=4)
    assert loop_block["ok"] is False
    assert loop_block["code"] == "BOT_TO_BOT_HOP_LIMIT"


def test_telegram_bot_to_bot_policy_blocks_normal_routing_for_bots():
    human_update = {
        "message": {
            "message_id": 11,
            "from": {"id": 778, "is_bot": False, "username": "owner"},
            "chat": {"id": 556},
        }
    }
    human_decision = telegram_bot_to_bot_policy_decision(human_update)
    assert human_decision["allow_normal_routing"] is True

    self_update = {
        "message": {
            "message_id": 13,
            "from": {"id": 780, "is_bot": True, "username": "LocalOSBot"},
            "chat": {"id": 558},
        }
    }
    self_decision = telegram_bot_to_bot_policy_decision(self_update, local_bot_username="LocalOSBot")
    assert self_decision["allow_normal_routing"] is False
    assert self_decision["should_alert"] is False
    assert self_decision["code"] == "LOCALOS_SELF_MESSAGE"

    trusted = parse_trusted_telegram_agent_bots("@PartnerAgentBot, other_bot")
    bot_update = {
        "message": {
            "message_id": 12,
            "from": {"id": 779, "is_bot": True, "username": "PartnerAgentBot"},
            "chat": {"id": 557},
        }
    }
    bot_decision = telegram_bot_to_bot_policy_decision(bot_update, trusted_bot_usernames=trusted)
    assert bot_decision["allow_normal_routing"] is False
    assert bot_decision["should_alert"] is True
    assert bot_decision["code"] == "TELEGRAM_AGENT_CLIENT_BINDING_REQUIRED"

    sandbox_decision = telegram_bot_to_bot_policy_decision(
        bot_update,
        bound_agent_client={"id": "client-1", "status": "sandbox"},
    )
    assert sandbox_decision["allow_normal_routing"] is False
    assert sandbox_decision["should_alert"] is True
    assert sandbox_decision["code"] == "TELEGRAM_AGENT_TRANSPORT_SANDBOX"
    assert sandbox_decision["agent_client_id"] == "client-1"

    live_decision = telegram_bot_to_bot_policy_decision(
        bot_update,
        bound_agent_client={"id": "client-1", "status": "live"},
    )
    assert live_decision["allow_normal_routing"] is False
    assert live_decision["should_alert"] is False
    assert live_decision["code"] == "TELEGRAM_AGENT_API_REQUIRED"
