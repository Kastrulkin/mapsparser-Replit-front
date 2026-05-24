# Task Spec: supervised-outreach-integration-20260524

## Metadata
- Task ID: supervised-outreach-integration-20260524
- Created: 2026-05-24T09:12:22+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md
- agents/autonomous_development_brief.md

## Original task statement
P1/P2 supervised outreach integration: sourcing leads -> shortlist -> drafts -> approvals -> batch queue, without starting dispatcher

## Acceptance criteria
- AC1: Blueprint run can start from `lead_ids` and hydrate a real shortlist artifact from `prospectingleads`.
- AC2: Shortlist approval contains the actual shortlist payload and advances selected leads in the existing outreach pipeline.
- AC3: After shortlist approval, blueprint creates LocalOS outreach message drafts from existing lead data without external provider writes.
- AC4: Draft approval approves those generated drafts and passes their `draft_ids` to `outreach.send_batch`.
- AC5: Send batch creates queue rows only; dispatcher remains disabled and no external dispatch side effect occurs.
- AC6: Targeted tests, backend lint, deploy, and live API smoke pass.

## Constraints
- Reuse existing transitional outreach tables: `prospectingleads`, `outreachmessagedrafts`, `outreachsendbatches`, `outreachsendqueue`.
- Do not introduce a second lead table or new production schema.
- Do not enable `OUTREACH_DISPATCH_ENABLED`.
- Do not perform real provider sends.
- Keep external side effects behind ActionOrchestrator.

## Non-goals
- Universal no-code agent builder.
- AI/provider-based draft generation inside blueprint runtime.
- Full UI redesign.
- Real dispatcher/provider delivery.
- Modifying unrelated Operator Sprint 36 changes.

## Verification plan
- Build: `python3 -m py_compile src/services/agent_blueprint_runner.py scripts/smoke_agent_blueprint_outreach_api.py`.
- Unit tests: targeted Agent Blueprint and adjacent Operator tests.
- Integration tests: live authenticated Agent Blueprint API smoke on production container.
- Lint: `scripts/lint_backend_baseline.sh`.
- Manual checks: production `docker compose ps`, app/worker logs, root health, worker dispatcher env/logs.
