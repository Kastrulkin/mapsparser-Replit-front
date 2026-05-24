# Evidence Bundle: supervised-outreach-integration-20260524

## Summary
- Overall status: PASS
- Last updated: 2026-05-24T12:23:00+03:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `AgentBlueprintRunner._build_lead_shortlist_payload` hydrates `lead_shortlist` from `prospectingleads`.
  - Live smoke started run with `lead_ids`, not prepared `draft_ids`.
  - Unit test validates shortlist approval payload contains the hydrated shortlist artifact.
- Gaps:
  - None for existing transitional `prospectingleads` flow.

### AC2
- Status: PASS
- Proof:
  - `_build_approval_payload` attaches `lead_shortlist` artifact data to `approval_type=shortlist`.
  - `_apply_shortlist_approval` moves approved leads into the existing outreach path unless they are already further along.
  - Targeted test asserts shortlist approval payload has `artifact_type=lead_shortlist` and `count=1`.
- Gaps:
  - Current approval accepts the artifact as a whole; per-lead partial approval remains future product polish.

### AC3
- Status: PASS
- Proof:
  - `_create_message_drafts_for_approved_shortlist` creates `outreachmessagedrafts` after shortlist approval using existing lead/contact data.
  - Drafts are local LocalOS rows with `source=agent_blueprint_local`; no external provider write occurs.
  - Targeted test asserts draft is created as `generated` and lead moves to `channel_selected`.
- Gaps:
  - Draft generation is deterministic local v1, not AI/prompt-backed yet.

### AC4
- Status: PASS
- Proof:
  - `_apply_drafts_approval` approves generated drafts in `outreachmessagedrafts`.
  - `_execute_capability_step` derives `draft_ids` from the latest `message_drafts` artifact when run input did not provide them.
  - Targeted test asserts `ActionOrchestrator` receives `outreach.send_batch` with exactly the generated draft id.
  - Transaction visibility bug found by live smoke was fixed by committing approval side effects before capability execution.
- Gaps:
  - None for the current sequential runner.

### AC5
- Status: PASS
- Proof:
  - Live smoke completed with `queue_status=queued` and `dispatcher_started=false`.
  - Production worker env check returned `OUTREACH_DISPATCH_ENABLED=false`.
  - Production worker logs had no `OUTREACH_DISPATCH` entries.
- Gaps:
  - Real dispatcher/provider delivery remains intentionally outside this task.

### AC6
- Status: PASS
- Proof:
  - `26 passed` for targeted tests.
  - `scripts/lint_backend_baseline.sh` passed.
  - Production deploy via `git archive HEAD` succeeded and root health returned `HTTP/1.1 200 OK`.
  - Live authenticated smoke passed: create blueprint -> run -> approve shortlist -> approve drafts -> queue batch -> fixture cleanup.
- Gaps:
  - Full test suite was not run; scope was targeted backend/runtime checks.

### AC7
- Status: PASS
- Proof:
  - `_build_lead_source_payload` hydrates the first `source_leads` artifact from `prospectingleads`.
  - Source artifact records filters, count, status counts, and selected lead rows.
  - Smoke now fails unless `lead_source_plan` has `source=prospectingleads`, `status=hydrated`, and `count=1`.
  - Backend lint guardrail requires `_build_lead_source_payload`, `source=prospectingleads`, and `status_counts`.
- Gaps:
  - Default smoke still creates a disposable fixture lead for safe production verification; using existing production leads would mutate real outreach state and needs explicit operator choice.

## Commands run
- `python3 -m py_compile src/services/agent_blueprint_runner.py scripts/smoke_agent_blueprint_outreach_api.py`
- `PYTHONPATH=src:. python3 -m pytest -q tests/test_agent_blueprint_layer.py tests/test_operator_paid_action_adapter.py tests/test_operator_review_reply_bulk.py tests/test_operator_refresh_result.py`
- `scripts/lint_backend_baseline.sh`
- `git push origin main`
- `git push gitverse main`
- `git archive --format=tar HEAD src scripts/smoke_agent_blueprint_outreach_api.py scripts/lint_backend_baseline.sh docker-compose.yml | ssh ... 'cd /opt/seo-app && tar -xf - && docker compose restart app worker ...'`
- `cat scripts/smoke_agent_blueprint_outreach_api.py | ssh ... 'cd /opt/seo-app && docker compose exec -T app ... python3 /tmp/smoke_agent_blueprint_outreach_api.py'`
- `ssh ... 'cd /opt/seo-app && docker compose ps && docker compose logs --since 10m app ...'`

## Raw artifacts
- .agent/tasks/supervised-outreach-integration-20260524/raw/build.txt
- .agent/tasks/supervised-outreach-integration-20260524/raw/test-unit.txt
- .agent/tasks/supervised-outreach-integration-20260524/raw/test-integration.txt
- .agent/tasks/supervised-outreach-integration-20260524/raw/lint.txt
- .agent/tasks/supervised-outreach-integration-20260524/raw/screenshot-1.png

## Known gaps
- Per-lead partial approval is not implemented yet.
- AI/prompt-backed blueprint drafting is still future work; current integration uses deterministic local draft text.
- Default production smoke still uses a disposable fixture lead to avoid mutating real prospecting leads.
