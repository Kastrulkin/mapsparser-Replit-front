# Evidence Bundle: approval-boundaries-audit-20260524

## Summary
- Overall status: PASS
- Last updated: 2026-05-24T12:08:00+03:00

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
  - `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py tests/test_operator_paid_action_adapter.py tests/test_operator_review_reply_bulk.py` passed with `17 passed`.
  - `python3 -m py_compile src/services/agent_blueprint_runner.py src/core/action_policy.py src/worker.py` passed locally.
  - `scripts/lint_backend_baseline.sh` passed.
- Gaps:
  - Full test suite not run for this narrow boundary hardening task.

### AC6
- Status: PASS
- Proof:
  - Production deploy/recreate completed for `app` and `worker`.
  - `docker compose ps` showed app, worker, and postgres up.
  - `curl -I http://localhost:8000` returned `HTTP/1.1 200 OK`.
  - Live import check in app container returned `imports ok`.
- Gaps:
  - Live `py_compile` attempted in read-only container failed only because Python tried to create `__pycache__`; import check was used instead with `PYTHONDONTWRITEBYTECODE=1`.

## Commands run
- `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py tests/test_operator_paid_action_adapter.py tests/test_operator_review_reply_bulk.py`
- `python3 -m py_compile src/services/agent_blueprint_runner.py src/core/action_policy.py src/worker.py`
- `scripts/lint_backend_baseline.sh`
- `git push origin main`
- `git push gitverse main`
- `scp -i ~/.ssh/localos_prod -o ConnectTimeout=15 docker-compose.yml root@80.78.242.105:/tmp/docker-compose.yml`
- `ssh -i ~/.ssh/localos_prod -o ConnectTimeout=15 root@80.78.242.105 'cd /opt/seo-app && install -m 644 /tmp/docker-compose.yml docker-compose.yml && docker compose up -d --force-recreate app worker ...'`
- `ssh -i ~/.ssh/localos_prod -o ConnectTimeout=15 root@80.78.242.105 'cd /opt/seo-app && docker compose ps && docker compose logs --since 5m app ...'`
- `ssh -i ~/.ssh/localos_prod -o ConnectTimeout=15 root@80.78.242.105 'cd /opt/seo-app && docker compose exec -T app sh -lc "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app/src python3 -c ..."'`

## Raw artifacts
- .agent/tasks/approval-boundaries-audit-20260524/raw/build.txt
- .agent/tasks/approval-boundaries-audit-20260524/raw/test-unit.txt
- .agent/tasks/approval-boundaries-audit-20260524/raw/test-integration.txt
- .agent/tasks/approval-boundaries-audit-20260524/raw/lint.txt
- .agent/tasks/approval-boundaries-audit-20260524/raw/screenshot-1.png

## Known gaps
- Unrelated Operator Sprint 35 tracked/untracked changes remain in the working tree and were intentionally left out of this proof.
- Full supervised outreach sourcing -> shortlist -> drafts -> approvals -> queue integration is still a separate P1/P2 product task.
