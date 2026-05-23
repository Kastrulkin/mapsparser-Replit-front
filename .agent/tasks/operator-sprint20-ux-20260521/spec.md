# Task Spec: operator-sprint20-ux-20260521

## Metadata
- Task ID: operator-sprint20-ux-20260521
- Created: 2026-05-21T12:36:47+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Sprint 20: improve Operator manual review UX with clear copy/open actions, charge/status display, and safer error states without enabling external publication

## Acceptance criteria
- AC1: Completed Operator manual-review chat results expose structured UI actions for copying the reply and opening the reviews tab.
- AC2: Insufficient-credit results expose a structured billing action and keep the paid function blocked.
- AC3: The Operator web panel shows credit status, publication status, execution status, copy action, and reviews navigation without claiming external publication.
- AC4: The reviews UI makes LocalOS drafts clearly manual-publication-only and gives copy feedback.
- AC5: Documentation records Sprint 20 as a UX/safety improvement only, with no provider writes, no Apify execution, and no new autonomous publication.

## Constraints
- Preserve manual publication boundary for all map providers.
- Do not enable Apify or external writes.
- Do not add schema changes.
- Keep changes scoped to Operator manual-review UX and related docs/tests.

## Non-goals
- No commit, push, or deploy unless separately requested.
- No authenticated production data test.
- No direct Yandex/Google/2GIS reply publication.

## Verification plan
- Build: `npm run build` in `frontend`.
- Unit tests: focused Operator manual-review and paid-credit tests.
- Integration tests: existing Operator paid-action tests for reservation/preflight/audit compatibility.
- Lint: Python compile plus `git diff --check`.
- Manual checks: inspect UI copy for manual-publication boundary and unsupported provider-write claims.
