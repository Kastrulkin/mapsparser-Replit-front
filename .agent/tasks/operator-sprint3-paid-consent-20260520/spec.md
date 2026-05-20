# Task Spec: operator-sprint3-paid-consent-20260520

## Metadata
- Task ID: operator-sprint3-paid-consent-20260520
- Created: 2026-05-20T12:57:35+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Sprint 3: add Operator paid-action proposal and consent contract skeleton for paid refresh/generation actions without executing charges or external tools

## Acceptance criteria
- AC1: Operator has a shared code-level paid action taxonomy for map refresh, review reply generation, news generation, social post generation, and service optimization.
- AC2: The attention brief can return paid action offers with consent modes, cost source, Apify x10 multiplier metadata, and proposal-only execution status.
- AC3: Web Operator and Telegram Operator show the paid refresh offer without charging credits, calling Apify, generating content, or publishing externally.
- AC4: The implementation does not invent live prices, public write support, or fully autonomous publication. Map publishing remains manual copy/paste.
- AC5: Focused tests cover offer metadata, attention brief integration, and Telegram copy.

## Constraints
- Do not change production data or add migrations in Sprint 3.
- Do not execute paid refresh, AI generation, external writes, or credit ledger updates.
- Preserve existing cached-data attention brief behavior.
- Follow existing Docker/Postgres runtime assumptions.

## Non-goals
- Real Apify execution.
- Actual cost estimation from provider run results.
- User-facing consent persistence.
- Automatic publishing to Yandex/Google/2GIS.

## Verification plan
- Build: py_compile for changed backend modules.
- Unit tests: operator attention, operator paid action offers, Telegram dashboard copy.
- Integration tests: not required; Sprint 3 is proposal-only and does not add routes or DB schema.
- Lint: targeted TypeScript build if frontend changes require it.
- Manual checks: inspect API response shape and UI copy in changed files.
