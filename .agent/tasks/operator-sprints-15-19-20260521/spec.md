# Task Spec: operator-sprints-15-19-20260521

## Metadata
- Task ID: operator-sprints-15-19-20260521
- Created: 2026-05-21T10:32:51+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Implement Operator sprints 15-19: manual review intake, UI/Telegram surface, real paid_compute credit charging, and gated Apify refresh adapter

## Acceptance criteria
- AC1: Operator chat accepts a pasted manual review, stores it in LocalOS, generates a reply draft, and returns the draft in the chat response.
- AC2: The manual review reply flow is billed as paid compute through credit preflight, reservation, charge finalization, and insufficient-balance blocking.
- AC3: The dashboard exposes the chat-command flow and the reviews UI can display stored LocalOS reply drafts for manual copy/publish.
- AC4: Telegram owner chat routes the same manual review intent through the same backend service without bypassing credit or manual-publication policy.
- AC5: Map refresh execution remains gated: no direct Apify call by default; only a disabled internal enqueue boundary exists for future controlled rollout.
- AC6: Documentation reflects the implemented Sprint 15-19 capabilities and remaining gaps.

## Constraints
- Do not publish review replies to external map providers.
- Do not enable Apify execution by default.
- Do not mutate production data during local implementation.
- Preserve Docker/Postgres runtime assumptions.
- Follow repository code style, including no new Python `as` or typecast usage in touched backend files.

## Non-goals
- No production deploy in this task.
- No provider write support.
- No real Apify provider-cost settlement.
- No autonomous external publication.

## Verification plan
- Build: `npm run build` in `frontend`.
- Unit tests: focused Operator pytest suite for manual review, paid actions, reservations, audit, and Telegram copy.
- Integration tests: map-refresh enqueue boundary and chat service tests using local sqlite-backed fixtures.
- Lint/static checks: `python3 -m py_compile`, `git diff --check`, and no-new-`as` scan for touched backend/test files.
- Manual checks: inspect git diff and docs for unsupported provider-write claims.
