# Task Spec: operator-sprint43-refresh-retry-request-20260524

## Metadata
- Task ID: operator-sprint43-refresh-retry-request-20260524
- Created: 2026-05-24T17:05:18+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Sprint 43: controlled retry request for failed/captcha refresh jobs. User can request a paid read-only retry from Operator; LocalOS creates a new paid refresh job through existing preflight/reserve/enqueue boundary without mutating the failed job or writing to map providers.

## Acceptance criteria
- AC1: Operator exposes an authenticated retry endpoint and web Operator action for a specific refresh job.
- AC2: Retry is allowed only for failed/captcha/paused/warning reliability states and blocked for processing/non-retryable jobs.
- AC3: Paid retry requires explicit `confirm_retry=true` before reserving credits or creating a new parsequeue job.
- AC4: Confirmed retry uses the existing paid map refresh enqueue boundary and creates a new read-only job without mutating the old job.
- AC5: Boundary evidence shows no provider writes, no direct Apify call, no customer messages, and no credit charge at request time.
- AC6: Targeted tests, backend lint, frontend build, and diff check pass.

## Constraints
- Use existing `parsequeue`, `operatorcreditreservations`, paid preflight/reservation, and map refresh enqueue code.
- Do not add a migration or table.
- Do not mutate the failed source job.
- Do not call Apify directly from retry service.
- Do not write to external map providers.

## Non-goals
- Automatic retry scheduler.
- Automatic UI polling after the retried job completes.
- Provider incident dashboard.
- Customer-facing notification.

## Verification plan
- Build: py_compile retry service and Operator API.
- Unit tests: retry plan, processing block, confirmation gate, confirmed enqueue boundary, refresh result, map refresh, Telegram follow-up, worker settlement.
- Integration tests: route ownership/boundary lint and diff whitespace check.
- Lint: backend baseline guardrail for controlled retry.
- Frontend: production Vite build.
- Manual checks: inspect endpoint, service, and UI for no old-job mutation and no provider writes.
