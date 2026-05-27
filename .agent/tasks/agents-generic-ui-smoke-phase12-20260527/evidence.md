# Evidence Bundle: agents-generic-ui-smoke-phase12-20260527

## Summary
- Overall status: PASS
- Last updated: 2026-05-27T16:32:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `raw/prod-email-fixture.txt`: email agent created run `88641347-03d6-4d76-8c83-76a0e5b4e581`, `analysis_source=gigachat`, `llm_analysis_used=true`, `external_dispatch_performed=false`.
  - `raw/prod-table-fixture.txt`: table agent created run `3ecbcb2a-3453-4fc9-99a1-4e3a80c4fa2c`, found exceptions/rows to review, `external_dispatch_performed=false`.
  - `raw/prod-reviews-fixture.txt`: reviews agent created run `99077fe9-ed66-4256-8094-f1df8ce5b8ef`, created reply drafts, `publish_state=not_published`, `external_dispatch_performed=false`.
- Gaps:
  - None.

### AC2
- Status: PASS
- Proof:
  - `raw/browser-generic-ui-smoke.txt`: authenticated browser flow passed for email, tables, and reviews.
  - Screenshots: `raw/browser-email-results.png`, `raw/browser-tables-results.png`, `raw/browser-reviews-results.png`.
- Gaps:
  - In-app browser typing was blocked by a missing virtual clipboard in the tool runtime, so this proof used local headless Playwright instead.

### AC3
- Status: PASS
- Proof:
  - `raw/browser-generic-ui-smoke.txt`: each scenario reports `visible_pre_count_before_technical_journal=0`.
- Gaps:
  - DOM still contains closed `<details>` payloads as expected; the smoke checks only visible/open technical journal blocks.

### AC4
- Status: PASS
- Proof:
  - `raw/prod-fixtures-cleanup.txt`: exact smoke fixtures deleted.
  - `raw/prod-fixtures-cleanup-verify.txt`: `users=0`, `businesses=0`, `blueprints=0`, `runs=0`.
- Gaps:
  - None.

## Commands run
- `ssh ... 'cd /opt/seo-app && docker compose exec -T app ... smoke_agent_blueprint_email_api.py'`
- `ssh ... 'cd /opt/seo-app && docker compose exec -T app ... smoke_agent_blueprint_table_api.py'`
- `ssh ... 'cd /opt/seo-app && docker compose exec -T app ... smoke_agent_blueprint_reviews_api.py'`
- `SMOKE_UI_PASSWORD=... python3 .agent/tasks/agents-generic-ui-smoke-phase12-20260527/raw/generic_ui_smoke.py`
- `ssh ... 'cd /opt/seo-app && docker compose exec -T app python -'` cleanup and verification

## Raw artifacts
- .agent/tasks/agents-generic-ui-smoke-phase12-20260527/raw/build.txt
- .agent/tasks/agents-generic-ui-smoke-phase12-20260527/raw/test-unit.txt
- .agent/tasks/agents-generic-ui-smoke-phase12-20260527/raw/test-integration.txt
- .agent/tasks/agents-generic-ui-smoke-phase12-20260527/raw/lint.txt
- .agent/tasks/agents-generic-ui-smoke-phase12-20260527/raw/screenshot-1.png
- .agent/tasks/agents-generic-ui-smoke-phase12-20260527/raw/prod-email-fixture.txt
- .agent/tasks/agents-generic-ui-smoke-phase12-20260527/raw/prod-table-fixture.txt
- .agent/tasks/agents-generic-ui-smoke-phase12-20260527/raw/prod-reviews-fixture.txt
- .agent/tasks/agents-generic-ui-smoke-phase12-20260527/raw/browser-generic-ui-smoke.txt
- .agent/tasks/agents-generic-ui-smoke-phase12-20260527/raw/browser-email-results.png
- .agent/tasks/agents-generic-ui-smoke-phase12-20260527/raw/browser-tables-results.png
- .agent/tasks/agents-generic-ui-smoke-phase12-20260527/raw/browser-reviews-results.png
- .agent/tasks/agents-generic-ui-smoke-phase12-20260527/raw/prod-fixtures-cleanup.txt
- .agent/tasks/agents-generic-ui-smoke-phase12-20260527/raw/prod-fixtures-cleanup-verify.txt
- .agent/tasks/agents-generic-ui-smoke-phase12-20260527/raw/prod-health-after-smoke.txt

## Known gaps
- No product code changed in this cycle, so there was no deploy step beyond verifying the already deployed production bundle.
