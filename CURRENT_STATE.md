# Current State (2026-02-24)

## Runtime
- Deployment model: Docker Compose
- DB runtime: PostgreSQL
- Server path: `/opt/seo-app`
- Main services: `app`, `worker`, `postgres`

## Canonical docs
1. `README.md` (primary source of truth)
2. `AGENTS.md` (agent behavior policy)
3. `.cursor/rules/*.mdc` (active workflows)
4. `.cursor/docs/*.md` (short logs/templates)

## What was cleaned
- Replaced outdated SQLite/systemd-first active rule files with Docker/Postgres workflows.
- Normalized implementation/verification/simplification docs to compact current templates.
- Added canonical `AGENTS.md` with explicit priority and deployment policy.

## Operational policy
- Prefer partial deploys.
- Use Alembic for schema changes.
- Always back up DB before server migrations.
- Treat legacy SQLite details as archival only.
