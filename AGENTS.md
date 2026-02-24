# Project Agent Rules (Canonical)

This file is the canonical instruction set for AI agents in this repository.

## 1. Source of Truth
- Always read `README.md` first.
- Runtime stack is Docker + Docker Compose + PostgreSQL.
- SQLite is legacy-only for one-off migration/debug scripts; do not treat it as runtime DB.

## 2. Environments
- Local workspace path: `/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре`
- Server path: `/opt/seo-app`
- Primary domain used in checks: `localos.pro`

## 3. Deployment Policy
- Prefer partial updates; avoid full rebuild when not needed.
- Frontend-only changes: build locally and sync `frontend/dist` into `app` container.
- Backend-only changes: sync `src/` (and migrations when needed) into `app`/`worker`, then restart only affected services.
- Use `docker compose restart app worker` instead of restarting all containers.

## 4. Database Safety
- Never modify production data without explicit user approval.
- Before schema changes on server: create DB backup.
- Schema changes only through Alembic in `alembic_migrations/versions`.
- Migration scripts must be idempotent where possible (`IF EXISTS`/`IF NOT EXISTS`).

## 5. Verification Standard
- Validate in this order:
  1) `docker compose ps`
  2) `docker compose logs --since ... app`
  3) `curl -I http://localhost:8000`
  4) targeted endpoint checks for changed feature
- For frontend runtime errors, prioritize browser console stack + app logs.

## 6. Documentation Structure
- Workflow rules are in `.cursor/rules/*.mdc`.
- Working logs/templates are in `.cursor/docs/*.md`.
- If README and rule files conflict, follow README + current runtime reality.

## 7. Current Rule Set
- `.cursor/rules/beautybot.mdc`
- `.cursor/rules/code_implementation_workflow.mdc`
- `.cursor/rules/verification_workflow.mdc`
- `.cursor/rules/dba_workflow.mdc`
- `.cursor/rules/frontend-design.mdc`

## 8. Legacy Cleanup Note
Older SQLite/systemd-first instructions were superseded by Docker/Postgres workflow.
Legacy details remain in git history and must not be used as default runbook.
