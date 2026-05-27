# Evidence Bundle: agents-rima-like-ux-product-polish-20260527

## Summary
- Overall status: PASS
- Last updated: 2026-05-27T19:20:00+00:00
- Code commit: `bb9adae Polish Rima-like agents UX`
- Production deploy: frontend dist deployed to `/opt/seo-app/frontend/dist` and `/app/frontend/dist`.

## Acceptance Criteria Evidence

### AC1: Creation UX
- Status: PASS
- Proof:
  - `raw/prod-agents-ux-ui-smoke.txt` verifies one `Создать агента` CTA, dialog builder preview, created-agent banner, and first-screen technical-word absence.
  - `raw/prod-agents-ux-ui-smoke.png` captures the production UI after creating the agent.
  - `frontend/src/pages/dashboard/AgentBlueprintsPage.tsx` now shows connected data summary in wizard step 2 and preview rows in step 4.
- Gaps:
  - None for this cycle.

### AC2: Run Detail / Journal
- Status: PASS
- Proof:
  - `frontend/src/pages/dashboard/AgentBlueprintsPage.tsx` renders `AgentRunReviewPanel` before the collapsed `Технический журнал`.
  - `raw/test-unit.txt` includes `test_agent_run_review_journal_is_human_readable`.
- Gaps:
  - Production UI smoke focused on creation/settings. Runtime journal remains covered by unit/API proof from this and previous proof bundles.

### AC3: Datahub-Lite Polish
- Status: PASS
- Proof:
  - `raw/prod-agents-ux-ui-smoke.txt` verifies `datahub connected/available split`.
  - UI now separates `Подключено к агенту` and `Доступно в LocalOS`.
  - UI displays readable source type, state, file size/text length, and extraction errors.
- Gaps:
  - Real PDF/DOCX/XLSX quality testing remains a continuing product polish item.

### AC4: Version UX
- Status: PASS
- Proof:
  - `raw/prod-agents-ux-ui-smoke.txt` verifies `version summary`.
  - `VersionSummary` shows active version, changed fields, created date, and run/activate/rollback controls.
  - `raw/test-unit.txt` includes `test_agent_version_diff_shows_readable_changes`.
- Gaps:
  - None for current UI controls.

### AC5: Email Agent End-To-End
- Status: PASS
- Proof:
  - `raw/prod-email-agent-smoke.txt` shows an email agent run using LLM, producing subject `Приглашение на консультацию по уходу за волосами`.
  - The same smoke confirms `approval_type=final_output` and `external_dispatch_performed=false`.
  - Fixture was cleaned by the smoke.
- Gaps:
  - None.

### AC6: Deploy, Cleanup, Health
- Status: PASS
- Proof:
  - `raw/build.txt`: frontend build passed.
  - `raw/test-unit.txt`: targeted pytest passed.
  - `raw/lint.txt`: backend lint baseline passed.
  - `raw/deploy-frontend.txt`: production frontend deploy passed with `HTTP/1.1 200 OK`.
  - `raw/deploy-frontend-content-check.txt`: live bundle contains new UX markers.
  - `raw/prod-ui-fixture-cleanup-verify.txt`: production UI smoke fixture counts are all zero.
  - `raw/prod-health-after-ux-polish.txt`: app/worker/postgres running and `HTTP/1.1 200 OK`.
- Gaps:
  - None.

## Commands Run
- `python3 -m pytest -q tests/test_agent_blueprint_layer.py -k 'agent_blueprint_api_guards_version_blueprint_mismatch or agent_version_diff_shows_readable_changes or agent_run_review_journal_is_human_readable'`
- `npm --prefix frontend run build`
- `scripts/lint_backend_baseline.sh`
- `scripts/deploy_frontend_dist.sh`
- `python3 .agent/tasks/agents-rima-like-ux-product-polish-20260527/raw/prod_agents_ux_ui_smoke.py`
- `ssh ... 'cd /opt/seo-app && docker compose exec -T app ...' < scripts/smoke_agent_blueprint_email_api.py`
- `ssh ... 'cd /opt/seo-app && docker compose exec -T postgres psql ... cleanup/verify ...'`

## Raw Artifacts
- `raw/build.txt`
- `raw/test-unit.txt`
- `raw/lint.txt`
- `raw/deploy-frontend.txt`
- `raw/deploy-frontend-content-check.txt`
- `raw/prod-agents-ux-ui-smoke.txt`
- `raw/prod-agents-ux-ui-smoke.png`
- `raw/prod-email-agent-smoke.txt`
- `raw/prod-ui-fixture-cleanup-verify.txt`
- `raw/prod-health-after-ux-polish.txt`

## Known Gaps
- Browser plugin input failed because the in-app virtual clipboard was unavailable; production UI smoke was completed with local Playwright instead and saved as proof.
- Rich document parsing quality for real-world PDF/DOCX/XLSX files remains a later product-polish track.
