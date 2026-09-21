from scripts import audit_approval_boundaries
import pytest


def test_approval_boundaries_audit_has_no_findings() -> None:
    findings = []

    audit_approval_boundaries.audit_blueprint_boundaries(findings)
    audit_approval_boundaries.audit_operator_boundaries(findings)
    audit_approval_boundaries.audit_dispatcher_opt_in(findings)

    assert findings == []


def test_audit_rejects_unconditional_orchestrator_approval_override(monkeypatch):
    original_read = audit_approval_boundaries.read_text

    def unsafe_runner(path):
        source = original_read(path)
        if path == "src/services/agent_blueprint_runner.py":
            return source.replace("allow_execute_when_approved=approval_verified", "allow_execute_when_approved=True")
        return source

    monkeypatch.setattr(audit_approval_boundaries, "read_text", unsafe_runner)
    findings = []

    audit_approval_boundaries.audit_blueprint_boundaries(findings)

    assert any("unconditional approval override" in finding for finding in findings)


@pytest.mark.parametrize(
    "override",
    [
        "allow_execute_when_approved=approval_verified or (1 == 1)",
        "allow_execute_when_approved=approval_verified or 'yes'",
        "allow_execute_when_approved=not approval_verified",
        "allow_execute_when_approved=(approval_verified if approval_verified else True)",
        "allow_execute_when_approved=other_flag",
        "**{'allow_execute_when_approved': True}",
    ],
)
def test_audit_rejects_unverified_approval_expressions(monkeypatch, override):
    original_read = audit_approval_boundaries.read_text

    def mutated_runner(path):
        source = original_read(path)
        if path == "src/services/agent_blueprint_runner.py":
            marker = "allow_execute_when_approved=approval_verified"
            assert source.count(marker) >= 2
            return source.replace(marker, override, 1)
        return source

    monkeypatch.setattr(audit_approval_boundaries, "read_text", mutated_runner)
    findings = []
    audit_approval_boundaries.audit_blueprint_boundaries(findings)
    assert any("unverified approval override" in finding for finding in findings)


@pytest.mark.parametrize("override", ["allow_execute_when_approved=False", ""])
def test_audit_allows_safe_override_forms_without_weakening_other_checks(monkeypatch, override):
    original_read = audit_approval_boundaries.read_text

    def denied_runner(path):
        source = original_read(path)
        if path == "src/services/agent_blueprint_runner.py":
            marker = "allow_execute_when_approved=approval_verified"
            assert source.count(marker) >= 2
            return source.replace(marker, override, 1)
        return source

    monkeypatch.setattr(audit_approval_boundaries, "read_text", denied_runner)
    findings = []
    audit_approval_boundaries.audit_blueprint_boundaries(findings)
    assert findings == []
