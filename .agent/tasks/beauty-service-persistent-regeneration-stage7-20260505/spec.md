# Task Spec: beauty-service-persistent-regeneration-stage7-20260505

## Metadata
- Task ID: beauty-service-persistent-regeneration-stage7-20260505
- Created: 2026-05-05T19:05:00+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md
- README.md

## Original task statement
Этап 7: сделать перегенерацию проблемных услуг устойчивой и наблюдаемой: job в БД вместо in-memory, manual review status в UI, история качества по услуге, ручное подтверждение массовой перегенерации, rate limit cooldown, подготовка к stage 8.

## Acceptance criteria
- AC1: Regeneration jobs and item attempts persist in PostgreSQL through Alembic-managed schema.
- AC2: `POST /api/services/regenerate-problematic` supports manual confirmation before starting a batch.
- AC3: UI separates “нужна ручная проверка” from ordinary `needs_review` and does not send manual-review services into bulk regeneration.
- AC4: UI shows per-service quality history from the latest regeneration item.
- AC5: Telegram flow asks for confirmation before starting a batch and then starts the same backend job.
- AC6: Rate limit handling stores cooldown and exposes it to UI/status.
- AC7: Tests/build/deploy verification pass.

## Constraints
- Create DB schema only through Alembic.
- Backup production DB before applying schema changes.
- Avoid full unrelated refactors.
- Keep existing service optimizer endpoint as generation engine.

## Non-goals
- Stage 8 automatic policy for only fixable issue classes.
- Full admin analytics page for regeneration history.
- Worker-process queue consumer; this stage persists jobs and uses app-triggered background execution.

## Verification plan
- `python3 -m py_compile` for changed Python files and migration.
- Targeted pytest for beauty/service scoring/regeneration.
- `npm run build:all`.
- Production DB backup, deploy, migration current check, route auth checks, app logs, Telegram service status.
