# Task Spec: agents-generic-ui-smoke-phase12-20260527

## Metadata
- Task ID: agents-generic-ui-smoke-phase12-20260527
- Created: 2026-05-27T16:20:07+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Rima-like generic agents authenticated UI smoke for email, tables, reviews run detail

## Acceptance criteria
- AC1: Production API fixtures can create email, table, and reviews generic agent runs with LLM analysis and no external dispatch.
- AC2: Authenticated browser UI smoke can log in as each test user, open `/dashboard/agents`, select the run result, and see a human-readable run path for each agent type.
- AC3: JSON/runtime payload stays hidden behind `Технический журнал` by default for email, table, and reviews result views.
- AC4: Temporary production smoke users, businesses, blueprints, runs, artifacts, and approvals are cleaned up and verified absent.

## Constraints
- Do not modify production data except exact temporary smoke fixtures created by this proof loop.
- Do not start dispatchers or perform external send/publish actions.
- Do not commit real tokens or passwords in proof artifacts.

## Non-goals
- No product code change unless UI smoke exposes a defect.
- No database migration.
- No external provider writes.

## Verification plan
- Production API fixtures: run existing email/table/reviews smoke scripts with `SMOKE_KEEP_FIXTURE=1`.
- Browser UI smoke: run `.agent/tasks/agents-generic-ui-smoke-phase12-20260527/raw/generic_ui_smoke.py` against `https://localos.pro`.
- Cleanup: delete exact smoke fixture IDs from production DB and verify zero counts.
