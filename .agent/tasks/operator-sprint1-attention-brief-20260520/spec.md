# Task Spec: operator-sprint1-attention-brief-20260520

## Metadata
- Task ID: operator-sprint1-attention-brief-20260520
- Created: 2026-05-20T10:46:09+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Sprint 1: implement the first LocalOS Operator MVP intent 'Что требует моего внимания сегодня?' as a cached-data attention brief. Add a minimal governed Operator backend surface that returns structured attention items from existing LocalOS data only, with no paid external refresh, no AI generation billing changes, no schema migrations, no provider writes, and no deployment. Reuse existing auth/business scoping patterns and document verification evidence.

## Acceptance criteria
- AC1: Backend exposes an authenticated, business-scoped Operator attention brief endpoint for `Что требует моего внимания сегодня?`.
- AC2: Attention brief uses cached LocalOS data only and returns structured JSON with summary, metrics, freshness, action items, action classes, and explicit execution limits.
- AC3: The implementation does not run paid external refreshes, AI generation, external writes, provider publication, schema migrations, or production data changes.
- AC4: Dashboard includes a first Operator web surface at `/dashboard/operator` that calls the endpoint and displays the cached brief, signals, freshness, and paid-refresh limitation.
- AC5: Documentation marks the Sprint 1 cached MVP as available/beta without implying unsupported provider write support or public MCP availability.
- AC6: Proof-loop evidence records changed files and validation checks.

## Constraints
- Reuse existing auth and business access patterns.
- Keep changes narrowly scoped to Operator Sprint 1.
- Preserve existing dirty worktree changes from previous article/docs work.
- Do not modify production data or deploy.
- Follow Sprint 0 action taxonomy and consent boundaries.

## Non-goals
- Implement freeform LLM chat.
- Implement paid Apify refresh execution.
- Implement paid AI generation consent/ledger changes.
- Implement Telegram command routing to Operator core.
- Implement provider write/publish actions.
- Add schema migrations.
- Commit, push, or deploy.

## Verification plan
- Build: `npm --prefix frontend run build`.
- Unit tests: `python3 -m pytest -q tests/test_operator_attention.py`.
- Integration tests: not run; endpoint requires a live app/database session and Sprint 1 was verified by service unit tests plus build.
- Lint/compile: `python3 -m py_compile src/services/operator_attention.py src/api/operator_api.py src/main.py`.
- Manual checks: inspect docs and grep for unsupported claims.
