# Task Spec: industry-patterns-rollback-safety-stage11-20260506

## Metadata
- Task ID: industry-patterns-rollback-safety-stage11-20260506
- Created: 2026-05-06T14:57:38+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Этап 11: rollback safety + сравнение версий перед применением

## Acceptance criteria
- AC1: Rollback from an active pattern card no longer executes on the first click.
- AC2: Telegram shows a rollback preview comparing current active version and target version before applying.
- AC3: Preview includes current/target text, impact counters, bad rate, text length delta, added/removed terms, warnings, and selected reason.
- AC4: Superadmin must choose/confirm a rollback reason and press a separate confirm button before DB state changes.
- AC5: Confirmation re-validates same industry/type and current active context before rollback.
- AC6: Rollback writes a decision record and an impact timeline event.
- AC7: Existing version management remains backward-compatible with old `ip_rb` callbacks.
- AC8: Relevant local tests and production smoke checks pass.

## Constraints
- Do not add a migration.
- Do not auto-rollback or auto-disable patterns.
- Keep callback data under Telegram limits.
- Rollback remains superadmin-only.
- Preserve stage 10 behavior for creating new pending versions.

## Non-goals
- Web/admin UI version diff.
- Automated A/B attribution.
- Applying rollback without explicit Telegram HITL.

## Verification plan
- Build: Python syntax checks for touched modules.
- Unit tests: industry pattern helpers and related regressions.
- Integration tests: production AST/import smoke, service restart, HTTP smoke, logs.
- Lint: no dedicated lint for this stage.
- Manual checks: inspect Telegram callback flow and callback data lengths.
