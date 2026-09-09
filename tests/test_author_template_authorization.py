from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
from pathlib import Path

import pytest
from flask import Flask

from services import author_template_authorization_service as auth
from services import outreach_campaign_service as campaign
from services import outreach_safety_service as safety
from services.outreach_template_service import render_creator_invitation_template


class Cursor:
    def __init__(self, *, rows=(), lists=()):
        self.rows, self.lists, self.calls = list(rows), list(lists), []

    def execute(self, query, params=()):
        self.calls.append((query, params))

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def fetchall(self):
        return self.lists.pop(0) if self.lists else []


def bridge():
    return {
        "status": "ready", "creator_display_name": "Катерина Давыдова",
        "constraints": {"invitation_only": True, "invitation_template": "verified_name_v2"},
        "terms_version": 2, "approved_at": "2026-09-08T14:00:00Z",
        "channel_id": "channel", "evidence_id": "evidence",
        "selected_contact_point_id": "contact",
    }


def grant():
    return {"id": "grant", "approved_by": "admin", "sender_account_id": "sender",
            "manifest": auth.template_manifest()}


def sender():
    return {"id": "sender", "status": "connected", "outreach_enabled": True,
            "health_status": "healthy", "capabilities_json": {"direct_send": True, "reply_sync": True}}


def event():
    return {"id": "grant", "actor_id": "admin", "actor_authorized": True,
            "created_at": datetime.now(timezone.utc),
            "payload_json": {"state": "active", "grant_id": "grant", "manifest": auth.template_manifest()}}


def test_grant_load_uses_only_canonical_sender_and_latest_permission_event():
    cursor = Cursor(rows=[event()], lists=[[sender()]])
    result = auth.load_author_template_authorization(cursor)
    assert result["id"] == "grant"
    assert "scope_type = 'platform' AND business_id IS NULL" in cursor.calls[0][0]
    assert "localosgo@gmail.com" in cursor.calls[0][1]
    assert "permission_changed" in cursor.calls[1][0]
    assert "ORDER BY event.created_at DESC, event.id DESC LIMIT 1" in cursor.calls[1][0]
    assert auth.PERMISSION_KIND in cursor.calls[1][1]
    assert "constraints" not in " ".join(sql for sql, _ in cursor.calls)


@pytest.mark.parametrize("case", ["revoked", "actor", "time", "manifest", "forged_id", "duplicate_sender", "disabled_sender", "no_reply_sync"])
def test_grant_load_fails_closed(case):
    saved, account = event(), sender()
    accounts = [account]
    if case == "revoked": saved["payload_json"]["state"] = "revoked"
    if case == "actor": saved["actor_authorized"] = False
    if case == "time": saved["created_at"] = None
    if case == "manifest": saved["payload_json"]["manifest"]["daily_limit"] = 200
    if case == "forged_id": saved["payload_json"]["grant_id"] = "other"
    if case == "duplicate_sender": accounts.append(deepcopy(account))
    if case == "disabled_sender": account["outreach_enabled"] = False
    if case == "no_reply_sync": account["capabilities_json"]["reply_sync"] = False
    assert auth.load_author_template_authorization(Cursor(rows=[saved], lists=[accounts])) == {}


@pytest.mark.parametrize("enabled", [True, False])
def test_permission_decision_appends_real_actor_and_can_revoke(enabled):
    cursor = Cursor(rows=[{"id": "admin"}, None], lists=[[sender()]])
    result = auth.set_author_template_authorization(cursor, sender_account_id="sender", actor_id="admin",
        enabled=enabled, authorization_reference="direct-user-decision")
    assert result["state"] == ("active" if enabled else "revoked")
    sql, params = cursor.calls[-1]
    assert "INSERT INTO outreach_sender_account_events" in sql
    assert "clock_timestamp()" in sql and params[2] == "admin"
    assert params[3].adapted["authorization_reference"] == "direct-user-decision"
    assert not any("UPDATE" in sql or "DELETE" in sql for sql, _ in cursor.calls)


def test_permission_change_requires_real_current_superadmin():
    with pytest.raises(PermissionError):
        auth.set_author_template_authorization(Cursor(), sender_account_id="sender", actor_id="business-user",
            enabled=True, authorization_reference="caller-said-yes")


def test_same_permission_is_idempotent():
    cursor = Cursor(rows=[{"id": "admin"}, event()], lists=[[sender()]])
    result = auth.set_author_template_authorization(cursor, sender_account_id="sender", actor_id="admin",
        enabled=True, authorization_reference="second-click")
    assert result["unchanged"] and result["id"] == "grant"
    assert not any("INSERT" in sql for sql, _ in cursor.calls)


@pytest.mark.parametrize("matched_history", ["same_profile_old_email", "different_profile_same_email", "manual", "uncertain"])
def test_first_invitation_history_has_no_day_or_cooldown_cutoff(matched_history):
    cursor = Cursor(rows=[{"match": matched_history}])
    assert auth.previously_contacted_author(cursor, creator_profile_id="creator", recipient=" Same@Example.Test ", queue_id="new-queue")
    sql, params = cursor.calls[0]
    assert "creator_id=%s OR (%s <> '' AND recipient=%s)" in sql
    assert params == ("new-queue", "creator", "same@example.test", "same@example.test")
    assert "NOW()" not in sql and "CURRENT_DATE" not in sql and "INTERVAL" not in sql
    assert "('sent', 'delivered')" in sql and "send_uncertain" in sql
    assert "('manual_sent', 'manual_reply')" in sql
    assert "NULLIF(queue.recipient_value, '')" in sql


@pytest.mark.parametrize("case", ["exact", "body", "subject", "name", "channel", "sender", "followup", "manifest"])
def test_only_exact_first_invitation_is_authorized(case):
    evidence, permission = bridge(), grant()
    rendered = render_creator_invitation_template(evidence)
    args = {"bridge": evidence, "authorization": permission, "sender_account_id": "sender",
            "channel": "email", "sequence_index": 0, "subject": rendered["subject"], "body": rendered["body"]}
    if case == "body": args["body"] += " Дополнительное предложение"
    if case == "subject": args["subject"] += "!"
    if case == "name": evidence["creator_display_name"] = "@kdvmua"
    if case == "channel": args["channel"] = "telegram"
    if case == "sender": args["sender_account_id"] = "riderra"
    if case == "followup": args["sequence_index"] = 1
    if case == "manifest": permission["manifest"]["template_version"] = 99
    assert auth.exact_author_invitation(**args) is (case == "exact")


def test_neutral_variant_is_exact_and_requires_the_new_manifest():
    evidence, permission = bridge(), grant()
    evidence["creator_display_name"] = "@channel_without_name"
    evidence["constraints"]["author_invitation_variant"] = "neutral_greeting_v1"
    rendered = render_creator_invitation_template(evidence)
    assert rendered["subject"] == "LocalOS | сотрудничество"
    assert rendered["body"].startswith("Здравствуйте!\n\n")
    args = dict(bridge=evidence, authorization=permission, sender_account_id="sender",
                channel="email", sequence_index=0, subject=rendered["subject"], body=rendered["body"])
    assert auth.exact_author_invitation(**args)
    assert not auth.exact_author_invitation(**{**args, "body": rendered["body"] + "!"})
    assert not auth.exact_author_invitation(**{**args, "subject": "Unknown | LocalOS | сотрудничество"})
    legacy = deepcopy(permission)
    legacy["manifest"]["authorization_version"] = 1
    assert not auth.exact_author_invitation(**{**args, "authorization": legacy})

def test_neutral_variant_passes_the_runtime_template_contract():
    evidence, permission = bridge(), grant()
    evidence["creator_display_name"] = "@channel_without_name"
    evidence["constraints"]["author_invitation_variant"] = "neutral_greeting_v1"
    rendered = render_creator_invitation_template(evidence)
    result = campaign._apply_creator_invitation_template_contract(
        {"passed": False, "diagnostic_codes": ["removal"], "reason_codes": ["WEAK_OFFER_BRIDGE"], "blocking_reasons": []},
        subject=rendered["subject"], body=rendered["body"], bridge=evidence,
        manual_review_context="", manual_reviewer_role="", template_authorization=permission,
    )
    assert result["passed"] and result["creator_invitation_copy_contract"]["authorized_template"]


def _preview_context_for_author_variant(variant):
    constraints = {"invitation_only": True}
    if variant is not None:
        constraints["author_invitation_variant"] = variant
    return {
        "workstream_type": "creator_collaboration",
        "sender_mode": "localos_for_partner",
        "lead_id": "lead",
        "lead_name": "Author channel",
        "city": "Moscow",
        "category": "creator",
        "source_url": "https://example.test/channel",
        "client_business_id": "business",
        "sender_profile": {"id": "profile"},
        "platform_sender_profile": {"confirmed_at": "2026-09-09T10:00:00Z"},
        "creator_outreach_bridge": {
            **bridge(),
            "creator_display_name": "@channel_without_name",
            "constraints": constraints,
        },
        "research": {"selected_personalization_id": "candidate"},
    }


def _stub_author_preview_dependencies(monkeypatch, context):
    monkeypatch.setattr(campaign, "_load_context", lambda *args: context)
    monkeypatch.setattr(campaign, "_apply_sender_mode", lambda value, mode: value)
    monkeypatch.setattr(campaign, "build_evidence_ledger", lambda value: [{"id": "evidence"}])
    monkeypatch.setattr(campaign, "evaluate_sender_profile_completeness", lambda *args, **kwargs: {"ready": True})
    monkeypatch.setattr(campaign, "channel_availability", lambda *args: {
        "email": {"status": "ready", "contact_point_id": "contact", "sender_account_id": "sender"}
    })
    monkeypatch.setattr(campaign, "_suppression_status", lambda *args: {"suppressed": False})
    monkeypatch.setattr(campaign, "build_outreach_decision", lambda *args, **kwargs: {"action": "write_now"})
    monkeypatch.setattr(campaign, "offer_candidates", lambda *args: [{"id": "offer", "text": "Offer", "cta": "Offer"}])
    monkeypatch.setattr(campaign, "trust_candidates", lambda *args: [{"id": "trust", "statement": "Trust"}])
    monkeypatch.setattr(campaign, "select_offer", lambda offers, value: offers[0])
    monkeypatch.setattr(campaign, "select_trust", lambda trusts, value: trusts[0])
    monkeypatch.setattr(campaign, "build_personalization_candidates", lambda *args, **kwargs: [{
        "id": "candidate", "evidence_id": "evidence", "evidence_kind": "creator_identity",
        "source_url": "https://example.test/channel", "observed_fact": "Public channel",
        "relevance_to_offer": "Offer", "bridge": "Offer", "recipient": "Author",
    }])
    monkeypatch.setattr(campaign, "_quality_gate", lambda *args, **kwargs: {
        "passed": False, "checks": {"bridge": False}, "diagnostic_codes": ["bridge"],
        "reason_codes": ["WEAK_OFFER_BRIDGE"], "blocking_reasons": [], "verdict": "revise",
    })
    monkeypatch.setattr(campaign, "_strategy_dimensions", lambda *args, **kwargs: {})
    monkeypatch.setattr(campaign, "_review_record", lambda *args, **kwargs: {})


def test_preview_loads_live_grant_and_applies_exact_neutral_contract(monkeypatch):
    context = _preview_context_for_author_variant("neutral_greeting_v1")
    _stub_author_preview_dependencies(monkeypatch, context)
    loaded = []
    monkeypatch.setattr(campaign, "load_author_template_authorization", lambda cursor: loaded.append(cursor) or grant())

    preview = campaign.build_preview(Cursor(), "workstream", generate_ai=False)

    assert len(loaded) == 1
    contract = preview["touches"][0]["quality_gate"]["creator_invitation_copy_contract"]
    assert contract["authorized_template"] and preview["touches"][0]["quality_gate"]["passed"]


def test_preview_does_not_load_grant_or_admit_unknown_author_variant(monkeypatch):
    context = _preview_context_for_author_variant("unknown_variant")
    _stub_author_preview_dependencies(monkeypatch, context)
    loaded = []
    monkeypatch.setattr(campaign, "load_author_template_authorization", lambda cursor: loaded.append(cursor) or grant())

    preview = campaign.build_preview(Cursor(), "workstream", generate_ai=False)

    assert not loaded
    contract = preview["touches"][0]["quality_gate"]["creator_invitation_copy_contract"]
    assert not contract["authorized_template"] and not preview["touches"][0]["quality_gate"]["passed"]


def test_template_permission_replaces_only_individual_copy_approval():
    evidence = bridge()
    rendered = render_creator_invitation_template(evidence)
    gate = {"checks": {"removal": False}, "diagnostic_codes": ["removal"],
            "reason_codes": ["WEAK_OFFER_BRIDGE"], "blocking_reasons": [], "passed": False}
    args = dict(subject=rendered["subject"], body=rendered["body"], bridge=evidence,
                manual_review_context="", manual_reviewer_role="", template_authorization=grant())
    result = campaign._apply_creator_invitation_template_contract(gate, **args)
    assert result["passed"]
    assert result["creator_invitation_copy_contract"]["authorized_template"]
    assert not result["creator_invitation_copy_contract"]["authorized_saved_review"]
    gate["reason_codes"].append("UNSUPPORTED_CLAIM")
    assert not campaign._apply_creator_invitation_template_contract(gate, **args)["passed"]
    args["template_authorization"] = None
    assert not campaign._apply_creator_invitation_template_contract(gate, **args)["passed"]


def test_exact_authorized_v2_copy_accepts_its_approved_em_dash():
    evidence = bridge()
    rendered = render_creator_invitation_template(evidence)
    assert "—" in rendered["body"]
    gate = {
        "checks": {
            "removal": False,
            "bridge": False,
            "specificity": False,
            "style_contract": False,
        },
        "diagnostic_codes": ["removal", "bridge", "specificity", "style_contract"],
        "reason_codes": [
            "DECORATIVE_PERSONALIZATION",
            "WEAK_OFFER_BRIDGE",
            "STYLE_VIOLATION",
        ],
        "blocking_reasons": ["decorative_personalization", "style_contract_violation"],
        "passed": False,
    }

    result = campaign._apply_creator_invitation_template_contract(
        gate,
        subject=rendered["subject"],
        body=rendered["body"],
        bridge=evidence,
        manual_review_context="",
        manual_reviewer_role="",
        template_authorization=grant(),
    )

    assert result["passed"]
    assert result["checks"]["style_contract"] is True


@pytest.mark.parametrize("case", ["ok", "revoked", "copy", "contact", "b2b"])
def test_authorize_wrapper_rechecks_live_permission_and_exact_copy(monkeypatch, case):
    evidence = bridge()
    rendered = render_creator_invitation_template(evidence)
    saved = {"id": "campaign", "workstream_id": "workstream", "status": "draft",
             "sender_mode": "localos_for_partner", "workstream_type": "creator_collaboration", "policy_json": {}}
    touch = {**rendered, "generated_text": rendered["body"], "sender_account_id": "sender",
             "channel": "email", "sequence_index": 0, "contact_point_id": "contact"}
    if case == "copy": touch["generated_text"] += "!"
    if case == "contact": touch["contact_point_id"] = "different"
    if case == "b2b": saved["workstream_type"] = "localos_sales"
    monkeypatch.setattr(campaign, "load_author_template_authorization", lambda *a, **k: {} if case == "revoked" else grant())
    monkeypatch.setattr(campaign, "_load_context", lambda *a: {"creator_outreach_bridge": evidence})
    monkeypatch.setattr(campaign, "_apply_sender_mode", lambda context, mode: context)
    approvals = []
    monkeypatch.setattr(campaign, "approve_campaign", lambda *a, **k: approvals.append(k) or {"status": "approved"})
    cursor = Cursor(rows=[saved], lists=[[touch]])
    if case != "ok":
        with pytest.raises(ValueError): campaign.approve_campaign_by_author_template(cursor, "campaign")
        assert not approvals
    else:
        assert campaign.approve_campaign_by_author_template(cursor, "campaign")["status"] == "approved"
        assert approvals[0]["user_id"] is None
        assert approvals[0]["template_authorization"]["id"] == "grant"


@pytest.mark.parametrize("case", ["revoked", "copy", "contact", "b2b", "draft_copy", "draft_id", "draft_contact", "valid_but_stale_facts"])
def test_dispatch_rechecks_permission_without_bypassing_existing_facts_gate(monkeypatch, case):
    evidence, permission = bridge(), grant()
    rendered = render_creator_invitation_template(evidence)
    item = {"id": "queue", "lead_id": "lead", "campaign_touch_id": "touch", "campaign_status": "approved", "touch_status": "scheduled",
            "approved_at": datetime.now(timezone.utc), "approved_snapshot_hash": "snapshot",
            "campaign_id": "campaign", "campaign_workstream_id": "workstream", "sender_account_id": "sender",
            "sender_mode": "localos_for_partner", "workstream_type": "creator_collaboration",
            "policy_json": {"approval_mode": "author_template", "author_template_authorization_id": "grant"},
            "queue_draft_id": "draft", "queued_draft_id": "draft", "queued_draft_status": "approved",
            "queued_draft_body": rendered["body"], "queued_draft_channel": "email",
            "queued_draft_contact_id": "contact", "queued_draft_lead_id": "lead", "queued_draft_workstream_id": "workstream"}
    touch = {"draft_id": "draft", "contact_point_id": "contact", "channel": "email", "sequence_index": 0,
             "subject": rendered["subject"], "generated_text": rendered["body"], "approved_text": rendered["body"]}
    if case == "revoked": permission = {}
    if case == "copy": touch["approved_text"] += "!"
    if case == "contact": touch["contact_point_id"] = "changed"
    if case == "b2b": item["workstream_type"] = "localos_sales"
    if case == "draft_copy": item["queued_draft_body"] += " altered after approval"
    if case == "draft_id": item["queue_draft_id"] = "other-draft"
    if case == "draft_contact": item["queued_draft_contact_id"] = "different-contact"
    monkeypatch.setattr(safety, "load_partnership_repeat_contact_guard", lambda *a, **k: {})
    generation_calls = []
    monkeypatch.setattr(
        safety,
        "generation_contract_current",
        lambda *a, **k: generation_calls.append(k) or True,
    )
    monkeypatch.setattr(auth, "load_author_template_authorization", lambda *a, **k: permission)
    monkeypatch.setattr(campaign, "_load_context", lambda *a: {"creator_outreach_bridge": evidence})
    monkeypatch.setattr(campaign, "current_outreach_source_fact_fingerprint", lambda *a: "")
    result = safety.run_dispatch_preflight(Cursor(rows=[item], lists=[[touch]]), "queue")
    expected = ("author_template_authorization_revoked_or_changed" if case in {"revoked", "b2b"}
                else "author_template_queued_draft_changed" if case.startswith("draft_")
                else "source_facts_changed" if case == "valid_but_stale_facts"
                else "author_template_copy_or_contact_changed")
    assert not result["allowed"] and result["reason_code"] == expected
    if case == "valid_but_stale_facts":
        assert generation_calls == [{"require_ai": False}]
    else:
        assert not generation_calls


@pytest.mark.parametrize(
    ("enabled", "expected_reason"),
    [("true", "generation_contract_outdated"), ("false", "source_facts_changed")],
)
def test_non_author_template_dispatch_preserves_ai_generation_default(monkeypatch, enabled, expected_reason):
    item = {
        "id": "queue", "lead_id": "lead", "campaign_touch_id": "touch",
        "campaign_status": "approved", "touch_status": "scheduled",
        "approved_at": datetime.now(timezone.utc), "approved_snapshot_hash": "snapshot",
        "campaign_id": "campaign", "campaign_workstream_id": "workstream",
        "workstream_type": "localos_sales", "policy_json": {"approval_mode": "manual"},
    }
    touch = {"message_brief_json": {}, "quality_gate_json": {"passed": True}}
    generation_calls = []
    original_generation_contract = safety.generation_contract_current
    monkeypatch.setenv("OUTREACH_AI_PERSONALIZATION_ENABLED", enabled)
    monkeypatch.setattr(safety, "load_partnership_repeat_contact_guard", lambda *a, **k: {})
    monkeypatch.setattr(
        safety,
        "generation_contract_current",
        lambda *a, **k: generation_calls.append(k) or original_generation_contract(*a, **k),
    )

    result = safety.run_dispatch_preflight(Cursor(rows=[item, None], lists=[[touch]]), "queue")

    assert not result["allowed"]
    assert result["reason_code"] == expected_reason
    assert generation_calls == [{"require_ai": None}]


def test_exact_author_template_preflight_skips_ai_provenance_only_after_full_validation(monkeypatch):
    evidence, permission = bridge(), grant()
    rendered = render_creator_invitation_template(evidence)
    item = {
        "id": "queue", "lead_id": "lead", "campaign_touch_id": "touch",
        "campaign_status": "approved", "touch_status": "scheduled",
        "approved_at": datetime.now(timezone.utc), "approved_snapshot_hash": "snapshot",
        "campaign_id": "campaign", "campaign_workstream_id": "workstream",
        "sender_account_id": "sender", "sender_mode": "localos_for_partner",
        "workstream_type": "creator_collaboration",
        "policy_json": {"approval_mode": "author_template", "author_template_authorization_id": "grant"},
        "queue_draft_id": "draft", "queued_draft_id": "draft", "queued_draft_status": "approved",
        "queued_draft_body": rendered["body"], "queued_draft_channel": "email",
        "queued_draft_contact_id": "contact", "queued_draft_lead_id": "lead",
        "queued_draft_workstream_id": "workstream",
    }
    touch = {
        "draft_id": "draft", "contact_point_id": "contact", "channel": "email", "sequence_index": 0,
        "subject": rendered["subject"], "generated_text": rendered["body"], "approved_text": rendered["body"],
        # The deterministic template intentionally has no AI metadata.
        "message_brief_json": {}, "quality_gate_json": {"passed": True},
    }
    monkeypatch.setenv("OUTREACH_AI_PERSONALIZATION_ENABLED", "true")
    monkeypatch.setattr(safety, "load_partnership_repeat_contact_guard", lambda *a, **k: {})
    monkeypatch.setattr(auth, "load_author_template_authorization", lambda *a, **k: permission)
    monkeypatch.setattr(campaign, "_load_context", lambda *a: {"creator_outreach_bridge": evidence})
    monkeypatch.setattr(campaign, "current_outreach_source_fact_fingerprint", lambda *a: "")

    result = safety.run_dispatch_preflight(Cursor(rows=[item], lists=[[touch]]), "queue")

    assert not result["allowed"]
    assert result["reason_code"] == "source_facts_changed"


def test_exact_author_template_approval_does_not_require_ai_provenance(monkeypatch):
    """The deterministic author lane remains approvable while AI is globally on."""
    policy = {
        "approval_mode": "author_template", "author_template_authorization_id": "grant",
        "author_policy_version": campaign.AUTHOR_POLICY_VERSION,
        "daily_limit": campaign.AUTHOR_DAILY_LIMIT,
        "channel_daily_limits": campaign.AUTHOR_CHANNEL_DAILY_LIMITS,
    }
    saved = {
        "id": "campaign", "status": "draft", "workstream_id": "workstream",
        "workstream_type": "creator_collaboration", "sender_mode": "localos_for_partner", "touch_count": 1,
        "quality_passed": True, "senders_ready": True, "policy_json": policy,
    }
    touch = {
        "id": "touch", "lead_id": "lead", "workstream_id": "workstream",
        "channel": "email", "sender_account_id": "sender", "contact_point_id": "contact",
        "sender_status": "connected", "sender_health_status": "healthy",
        "sender_outreach_enabled": True,
        "sender_capabilities_json": {"direct_send": True, "reply_sync": True},
        "message_brief_json": {"source_fact_fingerprint": "current"},
        # Exact-template previews intentionally have no AI generation metadata.
        "quality_gate_json": {"passed": True}, "angle_type": "invitation",
        "generated_text": "exact template body", "scheduled_at": None,
    }
    monkeypatch.setenv("OUTREACH_AI_PERSONALIZATION_ENABLED", "true")
    monkeypatch.setattr(campaign, "load_author_template_authorization", lambda *a, **k: grant())
    monkeypatch.setattr(campaign, "current_outreach_source_fact_fingerprint", lambda *a: "current")
    monkeypatch.setattr(campaign, "sender_scope_preflight_reason", lambda *a: None)
    cursor = Cursor(rows=[saved, {"count": 0}, {"id": "campaign", "version": 1, "status": "approved"}], lists=[[touch], []])

    result = campaign.approve_campaign(
        cursor, "campaign", user_id=None, template_authorization=grant(),
    )

    assert result["status"] == "approved"
    assert result["approval_mode"] == "author_template"


def test_dispatch_uses_validated_bytes_not_earlier_mutable_draft_snapshot():
    from services.outreach_dispatch_service import bind_preflight_dispatch_item
    old_item = {"id": "queue", "approved_text": "unapproved old bytes", "email": "wrong@test", "subject": "wrong"}
    proof = {"item": {"policy_json": {"approval_mode": "author_template"}},
             "validated_dispatch_payload": {"id": "queue", "approved_text": "approved exact bytes",
                 "generated_text": "approved exact bytes", "email": "verified@test", "subject": "exact",
                 "sender_account_id": "localos-sender"}}
    bound = bind_preflight_dispatch_item(old_item, proof)
    old_item["approved_text"] = "concurrent mutation"
    assert bound["approved_text"] == "approved exact bytes"
    assert bound["email"] == "verified@test" and bound["subject"] == "exact"
    assert bound["sender_account_id"] == "localos-sender"
    del proof["validated_dispatch_payload"]
    with pytest.raises(ValueError): bind_preflight_dispatch_item(old_item, proof)


@pytest.fixture
def api(monkeypatch):
    path = Path(__file__).resolve().parents[1] / "src/api/outreach_campaign_api.py"
    spec = importlib.util.spec_from_file_location("author_permission_api_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    class Connection:
        def cursor(self, **kw): return object()
        def close(self): pass
        def commit(self): pass
        def rollback(self): pass
    monkeypatch.setattr(module, "get_db_connection", Connection)
    monkeypatch.setattr(module, "_authorized_sender_account", lambda *a: sender())
    app = Flask(__name__)
    app.register_blueprint(module.outreach_campaign_bp)
    return module, app.test_client()


def test_api_rejects_business_actor_before_reading_payload(api, monkeypatch):
    module, client = api
    monkeypatch.setattr(module, "_require_auth", lambda: ({"user_id": "business", "is_superadmin": False}, None))
    response = client.patch("/api/outreach/sender-accounts/sender/author-template-authorization",
                            json={"enabled": True, "actor_id": "admin"})
    assert response.status_code == 403


def test_api_requires_exact_template_hash_and_uses_authenticated_actor(api, monkeypatch):
    module, client = api
    monkeypatch.setattr(module, "_require_auth", lambda: ({"user_id": "actual-admin", "is_superadmin": True}, None))
    calls = []
    monkeypatch.setattr(module, "set_author_template_authorization", lambda *a, **k: calls.append(k) or {"state": "active"})
    url = "/api/outreach/sender-accounts/sender/author-template-authorization"
    assert client.patch(url, json={"enabled": True}).status_code == 409
    assert not calls
    response = client.patch(url, json={"enabled": True, "actor_id": "fake",
        "approved_template_sha256": auth.template_manifest()["template_definition_sha256"]})
    assert response.status_code == 200
    assert calls[0]["actor_id"] == "actual-admin"
    assert response.get_json()["external_dispatch_performed"] is False
