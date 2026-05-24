# Task Spec: operator-sprint41-telegram-refresh-followup-20260524

## Metadata
- Task ID: operator-sprint41-telegram-refresh-followup-20260524
- Created: 2026-05-24T16:07:54+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Sprint 41: Telegram refresh actual follow-up. After map refresh completion, send a concise owner-bot follow-up with result once, without external writes to maps and without spam.

## Acceptance criteria
- AC1: Worker dispatches a one-time Telegram follow-up after a completed paid map refresh.
- AC2: Follow-up content includes refresh result, new/unanswered review counts, billing summary, and manual next step.
- AC3: Idempotency is stored on the matching refresh reservation metadata, so repeated worker passes do not spam.
- AC4: Boundary is explicit: no map-provider writes, no customer messages, no credit/pricing changes.
- AC5: Missing owner Telegram id, missing reservation, or still-processing refresh returns structured skipped results without sending.

## Constraints
- Use the existing owner-bot Telegram sender only.
- Do not publish review replies or write to Yandex/Google/2GIS.
- Do not add a new table or schema migration.
- Do not change refresh pricing or credit reservation behavior.

## Non-goals
- Telegram UI menu redesign.
- Retry campaign for failed Telegram sends.
- Customer-facing messages.
- External map writes.

## Verification plan
- Build: py_compile the worker and follow-up service.
- Unit tests: follow-up send, duplicate skip, missing Telegram skip, manual-publication copy.
- Integration tests: diff whitespace check.
- Lint: backend baseline guardrail for bounded Telegram follow-up.
- Manual checks: review worker dispatch placement after completed parsequeue status commit.
