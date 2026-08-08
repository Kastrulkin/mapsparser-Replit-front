# Outreach generic-touch quality gate — red/green report

Date: 2026-08-07

## Scope

- Added one approved regression test for a founder-led `audit_step` that omits the selected observation and offer bridge.
- Changed only the founder-led fallback checks inside `src/services/outreach_campaign_service.py::_quality_gate`.
- No database, campaign, deployment, commit, push, or send operations were performed.

## Red proof

The generated message contained neither `свежий отзыв`, `без ответа`, nor the selected bridge. Before the fix the gate returned:

- `passed=true`
- `removal=true`
- `bridge=true`
- `specificity=true`
- observation accuracy, offer bridge, and recipient specificity: `2/2`
- no reason codes

The focused test failed as predicted.

## Minimal fix

The generic `LocalOS` / `разбор` and candidate-length shortcuts were replaced with a deterministic selected-candidate link derived from existing typed checks: grounded observation, explicit bridge, approved case, operator-approved idea, or residential relevance. Explicit founder story/proof and respectful-close paths remain available.

## Green proof

- Focused regression node: `1 passed in 0.32s`.
- Broader outreach suites: `217 passed in 1.34s`.
- `python3 -m py_compile` passed for the production and test files.
- `git diff --check` passed.

## Residual risk

Regenerated previews whose only reachable messages are generic founder/audit/phone touches may now become `needs_evidence`. This is the intended safety behavior, but should be reviewed before any campaign persistence or send.
