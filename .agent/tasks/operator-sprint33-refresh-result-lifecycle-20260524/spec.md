# Task Spec: operator-sprint33-refresh-result-lifecycle-20260524

## Metadata
- Task ID: operator-sprint33-refresh-result-lifecycle-20260524
- Created: 2026-05-24T08:20:06+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Sprint 33: connect map refresh queue result to Operator: parsequeue completion -> identify newly saved reviews -> show found N new reviews in API/UI; no external writes

## Acceptance criteria
- AC1: Operator exposes a guarded API to check a queued map refresh result by `parsequeue` id.
- AC2: Completed refresh jobs count reviews saved after the job started and report how many are still unanswered.
- AC3: Pending/failed/missing jobs return structured statuses instead of pretending fresh data is available.
- AC4: Web Operator UI shows the refresh job, lets the user check completion, displays new review snippets, and offers bulk reply generation for unanswered reviews.
- AC5: No Apify call, credit charge, external write, or map publication is introduced in this sprint.

## Constraints
- No database schema migration.
- Use existing `parsequeue` and `externalbusinessreviews` data.
- Keep review reply publication manual.
- Preserve existing paid compute/credit paths without changing pricing.

## Non-goals
- Running Apify from Operator.
- Actual-cost settlement in the worker.
- Charging for map refresh.
- Applying service optimization suggestions.
- Telegram follow-up after refresh completion.

## Verification plan
- Build: Python compile for changed backend modules; Vite production build for frontend.
- Unit tests: targeted Operator refresh, fresh review, and map refresh tests.
- Integration tests: route-level behavior covered by service and existing API import checks; no live DB mutation.
- Lint: `git diff --check`.
- Manual checks: inspect Operator UI diff for queue/result card and no external publication path.
