# Task Spec: operator-sprint26-bulk-review-replies-20260523

## Metadata
- Task ID: operator-sprint26-bulk-review-replies-20260523
- Created: 2026-05-23T18:13:31+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Original task statement
Sprint 26: paid bulk generation of reply drafts for stored unanswered reviews through Operator, with credit charge and manual publication boundary.

## Acceptance criteria
- AC1: Operator can generate reply drafts for already stored unanswered reviews without refreshing maps or writing to external providers.
- AC2: The bulk generation path uses the existing paid compute credit flow: preflight, reserve, generate, finalize charge, release on total failure.
- AC3: Insufficient credits block the action and return `/dashboard/billing`.
- AC4: Web Operator exposes the `review_replies_generate` action from the Inbox and shows created drafts, charge status, copy actions, and manual publication state.
- AC5: Docs and tool registry describe Sprint 26 without claiming map publication, Apify execution, or autonomous provider writes.

## Constraints
- Do not call Apify.
- Do not create parsequeue jobs.
- Do not publish replies to Yandex, Google, 2GIS, or any external provider.
- Keep publication as manual copy/paste.
- Charge only for successfully created LocalOS drafts.

## Non-goals
- News generation.
- Social post generation.
- Service optimization execution.
- Provider actual-cost settlement.
- External map write support.

## Verification plan
- Build: Python compile for new and touched Operator backend files; Vite production build.
- Unit tests: bulk review generation, manual review, inbox, paid preflight, reservation, manual publish.
- Integration tests: existing Operator paid-action, map refresh, audit, Telegram copy/router compatibility.
- Lint: `git diff --check`.
- Manual checks: browser smoke of `/dashboard/operator` auth-guard render.
