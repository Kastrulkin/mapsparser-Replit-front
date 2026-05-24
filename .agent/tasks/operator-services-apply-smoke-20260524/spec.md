# Task Spec: operator-services-apply-smoke-20260524

## Metadata
- Task ID: operator-services-apply-smoke-20260524
- Created: 2026-05-24T15:13:30+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
P1 authenticated Operator services apply smoke and approval boundary smoke: generate services suggestions, block apply without confirm_apply, confirm apply, verify userservices/internal-only audit event, no external writes, no extra credit charge.

## Acceptance criteria
- AC1: Add a self-contained authenticated API smoke for Operator services apply that does not import `tests/`.
- AC2: Smoke creates its own user/business/services fixture and cleans it up.
- AC3: Smoke generates saved service optimization suggestions without external AI/provider calls.
- AC4: Authenticated apply without `confirm_apply` is blocked and does not mutate `userservices`.
- AC5: Authenticated apply with `confirm_apply=true` mutates only LocalOS service fields and marks the job/items applied.
- AC6: Apply creates audit events with `external_writes_performed=false`, `credit_charged=false`, and confirmation metadata.
- AC7: Apply does not create an extra credit ledger charge after suggestion generation.
- AC8: Lint baseline includes a guardrail that the smoke is self-contained.

## Constraints
- Do not call external providers or GigaChat during smoke.
- Do not leave production fixture data behind.
- Do not enable external dispatch or provider writes.
- Do not depend on `tests/` modules or fixtures.

## Non-goals
- Authenticated browser click automation.
- Telegram apply parity.
- Real provider service publishing.
- Full supervised outreach continuation.

## Verification plan
- Build: py_compile the new smoke script.
- Unit tests: focused Operator/boundary pytest set.
- Integration tests: live smoke against the app container on production/local compose.
- Lint: `scripts/lint_backend_baseline.sh`.
- Manual checks: server compose status, app/worker logs, root health, live frontend index.
