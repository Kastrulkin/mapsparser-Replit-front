# Task Spec: operator-sprint6-operator-audit-20260520

## Metadata
- Task ID: operator-sprint6-operator-audit-20260520
- Created: 2026-05-20T19:26:53+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Sprint 6: add Operator audit/ledger events for attention brief, consent policy updates, and paid action preflight without executing paid actions, charging credits, calling Apify, generating content, or publishing externally.

## Acceptance criteria
- AC1: Operator records audit/ledger events for attention brief, consent policy updates, and paid action preflight.
- AC2: Audit events use the existing `agent_action_ledger` foundation with capability `localos.operator`; no new schema migration is introduced.
- AC3: Web/API exposes a read-only recent Operator event list scoped by authenticated business access.
- AC4: The `/dashboard/operator` surface shows a compact Operator journal.
- AC5: Sprint 6 does not execute paid actions, call Apify, reserve or charge credits, generate AI content, or publish externally.

## Constraints
- Keep changes scoped to Operator observability.
- Reuse existing auth and business access checks.
- Do not introduce provider write support or imply map publication support.
- Do not add credit ledger writes.

## Non-goals
- Paid action execution runtime.
- Parsequeue job creation.
- Apify calls or actual provider cost conversion.
- AI generation and draft persistence.
- External map/social publication.

## Verification plan
- Build: `npm run build`
- Unit tests: Operator audit, preflight, consent, paid actions, attention, Telegram copy.
- Integration tests: API compile and existing focused pytest coverage.
- Lint: `git diff --check`; scan touched implementation for forbidden `as` usage.
- Manual checks: proof-loop validation and code review of no paid/external execution paths.
