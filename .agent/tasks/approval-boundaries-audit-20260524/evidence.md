# Evidence Bundle: approval-boundaries-audit-20260524

## Summary
- Overall status: PASS
- Last updated: 2026-05-24T18:00:00+03:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `src/services/agent_blueprint_runner.py` now marks default supervised outreach send with `required_approval_type: "drafts"`.
  - `_execute_capability_step` calls `_has_required_approval(run_id, step)`, so an unrelated earlier approval no longer unlocks a send capability.
  - `tests/test_agent_blueprint_layer.py::test_runner_blocks_send_capability_without_required_drafts_approval` proves a shortlist approval does not call the orchestrator for `outreach.send_batch`.
- Gaps:
  - None for the current sequential v1 runner.

### AC2
- Status: PASS
- Proof:
  - `src/core/action_policy.py` adds default human-review policy for dangerous capability names.
  - `tests/test_agent_blueprint_layer.py::test_risk_policy_requires_human_for_dangerous_capabilities` covers `outreach.send_batch`, `content.publish`, `billing.payment`, and `records.delete`.
  - Live container policy check returned `{'ok': True, 'requires_human': True, 'reason': 'dangerous capability requires review'}` for `outreach.send_batch`.
- Gaps:
  - Capability taxonomy is name-based for this generic fallback; explicit per-capability policies can still be added later.

### AC3
- Status: PASS
- Proof:
  - `src/worker.py` default changed to `_env_bool("OUTREACH_DISPATCH_ENABLED", False)`.
  - `docker-compose.yml` exposes `OUTREACH_DISPATCH_ENABLED: ${OUTREACH_DISPATCH_ENABLED:-false}` for both `app` and `worker`.
  - `scripts/lint_backend_baseline.sh` checks that worker default is false and compose has explicit opt-in markers for app and worker.
  - Production worker env check returned `false`.
- Gaps:
  - None.

### AC4
- Status: PASS
- Proof:
  - Blueprint send step still goes through `ActionOrchestrator`, which invokes `outreach.send_batch` as queueing behavior.
  - Worker dispatcher remains disabled unless the separate `OUTREACH_DISPATCH_ENABLED=true` contour is explicitly configured.
  - Production logs after restart had no `OUTREACH_DISPATCH` entries.
- Gaps:
  - Full sourcing-to-send product integration remains a later supervised outreach task.

### AC5
- Status: PASS
- Proof:
  - `PYTHONPATH=src:. python3 -m pytest -q tests/test_approval_boundaries_audit.py tests/test_agent_blueprint_layer.py tests/test_operator_paid_action_adapter.py tests/test_operator_review_reply_bulk.py tests/test_operator_paid_executor.py tests/test_operator_manual_publish.py` passed with `27 passed`.
  - `python3 -m py_compile scripts/audit_approval_boundaries.py` passed locally.
  - `scripts/lint_backend_baseline.sh` passed.
- Gaps:
  - Full test suite not run for this narrow boundary hardening task.

### AC6
- Status: PASS
- Proof:
  - Production scripts/tests sync completed from commit `6cd7947` without runtime restart because app code did not change.
  - `docker compose ps` showed app, worker, and postgres up.
  - `curl -I http://localhost:8000` returned `HTTP/1.1 200 OK`.
  - Server-side `python3 scripts/audit_approval_boundaries.py` returned PASS.
  - Worker env returned `OUTREACH_DISPATCH_ENABLED=false`.
- Gaps:
  - No runtime restart was needed for script/test-only changes.

### AC7
- Status: PASS
- Proof:
  - `scripts/audit_approval_boundaries.py` rejects direct Blueprint calls to `dispatch_due_outreach_queue`, channel sends, `requests.post`, `requests.get`, and `urllib.request.urlopen`.
  - The same audit rejects direct Operator external send/dispatch calls.
  - The audit requires Blueprint markers for `ActionOrchestrator`, approval source, billing source, dangerous capability approval, and explicit queue-not-dispatched result markers.
  - The audit requires Operator paid-generation markers for preflight, reserve, finalize, and `external_writes_performed=false`.
  - `tests/test_approval_boundaries_audit.py` imports the audit and asserts no findings.
- Gaps:
  - Static marker checks are intentionally conservative; deeper semantic proof remains in targeted behavior tests.

## Commands run
- `python3 scripts/audit_approval_boundaries.py`
- `python3 -m py_compile scripts/audit_approval_boundaries.py`
- `PYTHONPATH=src:. python3 -m pytest -q tests/test_approval_boundaries_audit.py tests/test_agent_blueprint_layer.py tests/test_operator_paid_action_adapter.py tests/test_operator_review_reply_bulk.py tests/test_operator_paid_executor.py tests/test_operator_manual_publish.py`
- `scripts/lint_backend_baseline.sh`
- `git push origin main`
- `git push gitverse main`
- `git archive --format=tar HEAD scripts/audit_approval_boundaries.py scripts/lint_backend_baseline.sh tests/test_approval_boundaries_audit.py | ssh ... 'cd /opt/seo-app && tar -xf - && python3 scripts/audit_approval_boundaries.py && docker compose ps && curl -I http://localhost:8000 && docker compose exec -T worker sh -lc "printenv OUTREACH_DISPATCH_ENABLED || true"'`

## Raw artifacts
- .agent/tasks/approval-boundaries-audit-20260524/raw/build.txt
- .agent/tasks/approval-boundaries-audit-20260524/raw/test-unit.txt
- .agent/tasks/approval-boundaries-audit-20260524/raw/test-integration.txt
- .agent/tasks/approval-boundaries-audit-20260524/raw/lint.txt
- .agent/tasks/approval-boundaries-audit-20260524/raw/screenshot-1.png

## Known gaps
- Unrelated `.agent/tasks/operator-sprint38-services-apply-20260524/` remains in the working tree and was intentionally left out of this proof.
- Full supervised outreach sourcing -> shortlist -> drafts -> approvals -> queue integration is still a separate P1/P2 product task.
