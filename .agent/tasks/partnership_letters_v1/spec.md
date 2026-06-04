# Task Spec: partnership_letters_v1

## Metadata
- Task ID: partnership_letters_v1
- Created: 2026-06-04T13:56:11+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Внедрить генерацию первого письма и КП для партнёрств, обучение/metadata, подготовить черновики для всех потенциальных партнёров; второй тип для лидов с пометкой отправить КП

## Acceptance criteria
- AC1: Backend supports two partnership letter types: `first_note` and `commercial_offer`.
- AC2: Draft metadata preserves letter type, business type pair, pair pattern, package idea, prompt version, and AI/cache flags.
- AC3: Approval keeps metadata and records learning events with edit signal.
- AC4: Moving a partnership lead to converted records an outcome learning event with `outcome=partner`.
- AC5: UI exposes a bulk action to prepare commercial offers.
- AC6: Production has prepared first-note drafts for all active partnership leads and commercial-offer drafts for leads with preserved "send/selected channel" marker.

## Constraints
- Use current transitional `prospectingleads` + `outreachmessagedrafts` flow.
- No new schema migration in this iteration.
- Keep external send manual/approved; do not send messages automatically.
- Back up production data before mass draft updates.

## Non-goals
- Full editable business-type dictionary tables.
- GigaChat pair-pattern generation.
- Automatic external delivery.

## Verification plan
- Build: `python3 -m py_compile src/api/admin_prospecting.py`; `vite build`.
- Lint/typecheck: `tsc -p frontend/tsconfig.app.json --noEmit` with known unrelated failures documented.
- Integration checks: deploy app, `docker compose ps`, app/worker logs, `curl -I http://localhost:8000`.
- Data checks: SQL counts for active partnership leads, first-note drafts, commercial-offer drafts.
