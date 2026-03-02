# Project Agent Rules (Canonical)

## 0. Mandatory Working Directory
- On server, run **all commands** from `/opt/seo-app` unless explicitly stated otherwise.
- Never assume current directory on server.
- Always start every server command block with:
  - `cd /opt/seo-app`
- This rule applies to `docker compose`, `docker`, `curl`, `grep`, `psql`, `python`, and any other server command.

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
- Canonical backend source path on server is `/opt/seo-app/src`.
- Do not copy Python runtime files into `/opt/seo-app/*.py` unless the file actually lives in the repository root.
- When verifying a hotfix, check the live file in container (`/app/src/...`), not only the host copy.

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

## 8.1 Current Platform State
- OpenClaw ↔ LocalOS integration roadmap (Phase 1–9) is complete in the current codebase.
- Live platform includes:
  - Action Orchestrator + policy + ledger + human-in-the-loop
  - M2M callbacks with retry/DLQ/outbox
  - diagnostics / support export / recovery flows
  - unified audit timeline
  - Telegram control surface with approval flow
  - unified multi-channel router (Telegram / WhatsApp / Maton bridge)
- The next product track is supervised outreach (lead sourcing, shortlist approval, draft approval, controlled sending).

## 9. Terminal Sessions (tmux)
- Use `tmux` for all long-running operations on server and local machine.
- Run builds, dependency installs, log tailing, and deployment commands inside a named `tmux` session.
- Default flow:
  1) `tmux new -s deploy`
  2) run long commands inside the session
  3) detach with `Ctrl+b` then `d`
  4) reattach with `tmux attach -t deploy`
- Do not run long operations in a plain SSH shell if connection drops are possible.
