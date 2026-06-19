# Project Hardening Plan

This document is the current implementation-aware hardening backlog after the June 2026 security and quality sweep.

## Immediate Gates

- Run `scripts/local_quality_gate.sh` before broad frontend/backend changes.
- Treat `npm --prefix frontend audit --omit=dev` as a release gate.
- Treat full `npm --prefix frontend audit` as a development-environment gate.
- Add `pip-audit` to local/CI environments; the quality gate already calls it when installed.

## Runtime Canon

- Runtime is Docker Compose + PostgreSQL.
- Server commands start from `/opt/seo-app`.
- Legacy root debug/repro/reset/fix scripts and systemd units live in `archive/legacy-runbooks/` and are historical only.
- Production data and schema changes still require explicit approval and backups.

## Monolith Split Order

1. Move finance routes from `src/main.py` into a finance blueprint backed by existing `core.finance_*` modules.
2. Move external account / YClients / Google/Yandex sync routes into provider-specific blueprints.
3. Move legacy screenshot/pricelist analyze routes into a legacy analysis blueprint, then decide whether to delete or modernize them.
4. Split `src/api/admin_prospecting.py` into:
   - partnership lead CRUD and imports;
   - public offers;
   - sales rooms;
   - outreach drafts/batches/queue;
   - analytics and summaries.
5. Keep transitional outreach on `prospectingleads`; do not create parallel lead tables unless the product schema migration is explicitly approved.

## Type Hardening Order

1. Add narrow DTO types for sales-room API payloads.
2. Add partnership API request/response types.
3. Add agent builder session/preview/run types.
4. Add auth/session user types around `frontend/src/lib/auth_new.ts`.
5. Only then consider turning on stricter TypeScript options module-by-module.

## Security Follow-Ups

- Rotate the Yandex Wordstat secret that had been committed in `src/wordstat_client.py`.
- Review the bundled 2GIS catalog fallback key and decide whether it should move to environment configuration.
- Replace in-process public sales-room rate limits with Redis-backed Flask-Limiter storage when Redis is available.
- Review legacy upload/analyze endpoints in `src/main.py` and either remove them or move all filename handling to safe normalized names.
