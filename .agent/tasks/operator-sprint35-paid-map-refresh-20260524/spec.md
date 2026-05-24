# Task Spec: operator-sprint35-paid-map-refresh-20260524

## Metadata
- Task ID: operator-sprint35-paid-map-refresh-20260524
- Created: 2026-05-24T08:57:20+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Sprint 35: full paid map refresh chain: preflight -> reserve -> enqueue parsequeue with reservation metadata.parsequeue_id -> worker Apify -> actual-cost settlement -> Operator result; no external writes or publication

## Acceptance criteria
- AC1: `Проверь новые отзывы` uses the paid-action preflight before any refresh job is queued.
- AC2: Successful refresh start reserves estimated `map_reviews_refresh` credits and stores the generated `parsequeue_id` in reservation metadata.
- AC3: The refresh enqueue path creates exactly a read-only `parsequeue` job and rolls the reservation back if enqueue fails.
- AC4: Operator returns enough user-facing metadata for the dashboard/chat to show reserved credits, queued refresh id, billing blocks, and later refresh results.
- AC5: The implementation does not add external map writes, reply publication, or direct Apify calls from Operator.

## Constraints
- Keep publication to maps manual.
- Reuse the existing Sprint 31 actual-cost settlement and Sprint 33 refresh-result lifecycle.
- Avoid schema changes.
- Do not touch unrelated worktree changes.

## Non-goals
- Directly publishing review replies to Yandex, Google, 2GIS, or other providers.
- Calling Apify from the web/chat request handler.
- Adding a new billing model beyond the existing Operator reservation and Apify settlement services.

## Verification plan
- Build: `python3 -m py_compile src/services/operator_map_refresh.py src/services/operator_fresh_reviews.py src/api/operator_api.py`
- Unit tests: `python3 -m pytest -q tests/test_operator_map_refresh.py tests/test_operator_fresh_reviews.py tests/test_operator_refresh_result.py tests/test_operator_apify_settlement.py`
- Integration tests: same targeted service/runtime boundary suite above.
- Lint: `git diff --check`
- Manual checks: inspect changed services, docs, and proof bundle.
