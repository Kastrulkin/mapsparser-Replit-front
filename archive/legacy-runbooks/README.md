# Legacy Runtime Archive

This folder stores root-level scripts, dumps, and systemd unit files that no longer represent the canonical LocalOS runtime.

Canonical runtime today:

- Docker + Docker Compose
- PostgreSQL
- server working directory: `/opt/seo-app`
- source of truth for deploy commands: `README.md`, `AGENTS.md`, `docs/DOCKER_DEPLOY.md`, and `scripts/deploy_backend_src.sh` / `scripts/deploy_frontend_dist.sh`

Use these archived files only for historical debugging. Do not copy systemd units or SQLite-era helpers from this folder into production unless a current runbook explicitly says so.

Archived groups:

- `root-scripts/`: old one-off debug, repro, reset, cleanup, and fix helpers from the repository root.
- `root-docs/`: old one-off task/fix instructions that are not canonical runbooks.
- `src-debug/`: old one-off debug, repro, reset, and local repair helpers that used to live in `src/`.
- `systemd-services/`: legacy service unit files superseded by the current Docker/Postgres and OpenClaw-hosted runtime.
- `local-dumps/`: local schema/result/debug dumps that are not runtime source of truth.
