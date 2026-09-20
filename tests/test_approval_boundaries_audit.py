from scripts import audit_approval_boundaries


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
