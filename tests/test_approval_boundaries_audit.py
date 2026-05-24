from scripts import audit_approval_boundaries


def test_approval_boundaries_audit_has_no_findings() -> None:
    findings = []

    audit_approval_boundaries.audit_blueprint_boundaries(findings)
    audit_approval_boundaries.audit_operator_boundaries(findings)
    audit_approval_boundaries.audit_dispatcher_opt_in(findings)

    assert findings == []
