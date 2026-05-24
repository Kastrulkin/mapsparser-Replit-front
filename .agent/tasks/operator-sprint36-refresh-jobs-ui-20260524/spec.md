# Task Spec: operator-sprint36-refresh-jobs-ui-20260524

## Metadata
- Task ID: operator-sprint36-refresh-jobs-ui-20260524
- Created: 2026-05-24T09:12:51+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Sprint 36: Operator UI for refresh jobs: recent refresh history, processing/completed/failed statuses, check result button, new reviews, transition to reply generation

## Acceptance criteria
- AC1: Backend exposes scoped recent Operator refresh jobs for a business/user.
- AC2: Refresh jobs include statuses `processing`, `completed`, and `failed`, plus new review and unanswered counts.
- AC3: Operator dashboard shows refresh history with status, check-result action, new review snippets, and transition to reply generation.
- AC4: The feature reuses the existing refresh result and reply generation flows without adding external map writes or publication.
- AC5: Documentation and proof artifacts describe the Sprint 36 boundary.

## Constraints
- Keep map publication manual.
- Do not add schema changes.
- Do not add direct Apify calls from Operator UI.
- Do not touch unrelated worktree changes.

## Non-goals
- Publishing replies to Yandex, Google, 2GIS, or other providers.
- Changing paid refresh accounting or parser execution.
- Adding a new background worker or scheduler.

## Verification plan
- Build: `python3 -m py_compile src/services/operator_refresh_result.py src/api/operator_api.py`
- Unit tests: `python3 -m pytest -q tests/test_operator_refresh_result.py tests/test_operator_map_refresh.py tests/test_operator_fresh_reviews.py tests/test_operator_apify_settlement.py tests/test_worker_apify_settlement.py`
- Integration tests: `npm run build`
- Lint: `git diff --check`
- Manual checks: local dev server/browser smoke, limited by auth redirect on `/dashboard/operator`.
