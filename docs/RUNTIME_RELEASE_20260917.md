# Runtime maintenance — 17 September 2026

## Result and scope

The user authorized Docker builds, a PostgreSQL restart and necessary migrations after expanding the server disk. Maintenance completed between **20:37:17 and 20:38:30 UTC** (23:37–23:38 Moscow). This is the maintenance interval, not a continuously measured HTTP outage.

- Built and deployed two **runtime-snapshot images**, preserving the existing Debian/Python packages, runtime user and working production backend files. This was **not** a clean rebuild from updated upstream base images or a rollout of the repository Dockerfile's non-root hardening.
- `app`, `worker`, `operator-worker`: `seo-app-app:runtime-20260917`, image ID `sha256:9c80f46a92f4cf5066b2e5f9fb55a21207416dba9d1197ac370f52096599129b`.
- `telegram-bot`: `seo-app-telegram-bot:runtime-20260917`, image ID `sha256:ba649754daa9448a4ec24e6597bc618db8c07daa6bd57e31ca3bcbb1e59ba5d9`.
- The compliance worker was stopped/started around the database maintenance but retained its original container/image. Redis and ClamAV were not restarted.
- PostgreSQL was restarted without replacing its image, container or data volume. The identical container/volume identifiers were checked before and after. The new postmaster start time was `2026-09-17 20:38:18.07045+00`.
- No schema upgrade was necessary or executed: database revision and the migration graph's head were both `20260907_001`. The revision identifier's date is not a freshness test: this merged head depends on the later September migrations.
- Startup remained `schema-check-only`. No direct production data edits, migration stamping, resets or volume deletion were performed.

Production was not reset to the old server Git HEAD or overwritten with the local checkout. Its live backend contains hotfixes; snapshots and bind mounts preserve them. The frontend is the already verified `290d1d56` release described in [the frontend release record](FRONTEND_TECH_DEBT_20260917.md).

## Backup and rollback

Server directory: `/opt/seo-app/release-backups/runtime-20260917.J1dT4n/` (restricted access).

- `database.dump`: approximately 1.7 GB, custom-format `pg_dump`; checksum recorded separately.
- Validated the archive table of contents and read/decompressed the entire archive with `pg_restore --file=/dev/null`. This proves archive readability, **not** a rehearsal restoring into another database.
- Previous Compose configuration, resolved configuration, image IDs, source/build context checksums, exact snapshot Dockerfile, execution scripts and build/deployment logs are retained there. The resolved configuration contains secrets; do not publish or commit this directory.
- Previous runtime images retain rollback tags `seo-app-app:rollback-20260917` and `seo-app-telegram-bot:rollback-20260917`. Original app image ID: `sha256:d761ed9b46508afc3d1b3b2e778711372fb947322ae44f3d0aa32eafe4a3c60e`; bot: `sha256:fe7adc39dcb13067bb0e9d1511464e246e4d1480735619e1a5c338c85ccea232`.
- Application rollback restores the saved Compose references and recreates only app/worker/operator-worker/telegram-bot with `--no-deps --no-build`. It does not require a database restore because the schema was unchanged. Review intervening configuration changes before replacing Compose.

The initial preparation check used the wrong public HTML path; it was corrected to `frontend/public-dist/public-audit/index.html`. BuildKit also rejected a bare local image ID in `FROM`; verified local rollback tags were used instead. Neither attempt changed running production containers.

## Verification

- Both Docker builds passed `pip check` and Python compilation. Isolated, network-disabled image probes imported app dependencies and Telegram 20.8 successfully.
- Compose comparison proved that the only effective configuration differences were four service image references. Database settings, feature flags, mounts and migration mode stayed unchanged.
- Before stopping services, non-terminal work counts were zero for parsequeue, agent_runs and operator_async_jobs.
- The candidate image passed the read-only schema gate before deployment; live app passed it again after deployment.
- All eight production services were running afterwards. PostgreSQL, Redis, ClamAV and Telegram reported healthy; the four replaced containers had restart count zero.
- Verification order: Compose status → recent app logs → local HTTP HEAD → targeted public/API/asset checks. `/health` returned `status=ok` locally and through `https://localos.pro`; unauthenticated `/api/auth/me` returned the expected 401. Both current entry JS assets returned 200.
- Main and public HTML hashes match the previous frontend release, including `/app/dist/index.html` fallback. No frontend bundle was rebuilt from stale server frontend source.
- Control row counts before/after matched: users 33; businesses 2038; userservices 146797. Queue state counts also matched. These are sanity checks, not proof that every row was compared.
- Targeted local regression/adjacent tests: **10 passed** across `test_docker_build_context_contract.py`, `test_backend_deploy_dependency_gate.py`, `test_migration_startup_contract.py`, `test_compiled_deployment_contract.py`. The earlier complete frontend suites were not rerun for this infrastructure-only maintenance.
- Root filesystem after backup/build: 50 GB total, approximately **9.6 GB free (80% used)**. Existing backups and rollback images were retained.

## Docker build-context defect — FIX_PROVEN

The existing `.dockerignore` omitted production release/backup/staging directories. A normal root-context `COPY . .` could include database dumps or resolved configurations stored there.

Following the `bug-reproducer` workflow, a minimal Docker build used synthetic sentinels only, without any real production data. The original exclusion check failed; after excluding release/backup/staging directories, the same build passed and still included required `src`, `scripts` and `alembic_migrations` fixtures. A checked-in configuration regression test also failed before the fix and passed afterwards. The narrow exclusion patch was applied locally and on the server, preserving their unrelated differences.

## Residual scope

- A clean rebuild from the canonical Dockerfile, dependency/base-image updates and non-root runtime rollout remain a separate compatibility/hardening release. This snapshot build intentionally preserves the working dependency/runtime baseline; it does not claim to complete those changes.
- Startup emits a non-fatal warning about the optional popular-query file. `src/service_categorizer.py` uses a CWD-relative `../prompts/popular_queries_with_clicks.txt` lookup with an empty-dictionary fallback. This path was not changed by this maintenance.
- Telegram experienced intermittent `ConnectError`/`ReadError` after startup. A host request through the same proxy also timed out, then returned HTTP 302. Polling recovered without a container restart: the successful-poll heartbeat advanced from `1789677586.179186` to `1789677767.1276252` (20:42:47 UTC), with an observed age of 1.3 seconds. No messages were sent or updates consumed by a diagnostic client. The proxy/network instability is a residual integration risk, not a proven application-code regression or a fixed network incident.
- No external publication, message delivery, payment, or authenticated business-write smoke was initiated for verification.
