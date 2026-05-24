# Evidence Bundle: agent-blueprint-outreach-real-pipeline-20260524

## Summary
- Overall status: PASS
- Last updated: 2026-05-24T20:25:00+03:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `AgentBlueprintRunner` now builds `lead_shortlist` from the prior `lead_source_plan` artifact when `lead_ids` are not manually provided.
  - `record_outcomes` now rehydrates draft ids from the `message_drafts` artifact, so the final timeline can show queued LocalOS handoff records for drafts generated inside the same run.
  - `scripts/smoke_agent_blueprint_outreach_api.py` now starts from a real transitional `prospectingleads` row in `new` / `unprocessed`, then runs sourcing filters instead of pre-seeding a shortlist-approved lead id.
- Gaps:
  - Live authenticated smoke was not executed in this local proof loop to avoid production fixture writes before deploy verification.

## Commands run
- `python3 -m py_compile src/services/agent_blueprint_runner.py src/services/outreach_send_capability.py src/api/agent_blueprints_api.py`
- `PYTHONPATH=src:. python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- `scripts/lint_backend_baseline.sh`
- `git diff --check`

## Raw artifacts
- .agent/tasks/agent-blueprint-outreach-real-pipeline-20260524/raw/build.txt
- .agent/tasks/agent-blueprint-outreach-real-pipeline-20260524/raw/test-unit.txt
- .agent/tasks/agent-blueprint-outreach-real-pipeline-20260524/raw/test-integration.txt
- .agent/tasks/agent-blueprint-outreach-real-pipeline-20260524/raw/lint.txt
- .agent/tasks/agent-blueprint-outreach-real-pipeline-20260524/raw/screenshot-1.png

## Known gaps
- Full live API smoke should be run only in the controlled deploy cycle because it creates and then cleans test fixture rows.
