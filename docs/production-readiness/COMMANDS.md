# Verified commands and evidence

All local commands below assume repository root unless a working directory is specified. Long runs use named tmux sessions. Production commands are not authorized by this audit; any later server block must begin `cd /opt/seo-app`. **At22:38UTC local Docker storage failed; do not replay Docker commands before the approved recovery/preflight in LOCAL_DOCKER_INCIDENT_20260917.md.**

## Baseline, 2026-09-17

Baseline archive: `git archive 30262a5bf7b468e0a6f5a0e3d8262dbef119e075 frontend` extracted into a new `mktemp -d` directory, not the live checkout. Directory recorded in task `raw/frontend-baseline-directory.txt`.

From its `frontend/` directory, all passed:

```sh
npm ci --no-audit --fund=false
npm run lint
npm run typecheck
npm run test -- --maxWorkers=2
npm run build:all
npx playwright test e2e/*.spec.ts --workers=2
npm audit --json
```

Durations/counts/warnings in `PROGRESS.md`; exact command/cwd/exit/stdout/stderr in task `raw/baseline-frontend-*.json`. Capture helper returns success after writing a report even if the child failed: inspect report `exit_code` and `timed_out`, not only the wrapper exit.

```sh
arch -arm64 venv/bin/python -m pip check
git diff --check
```

Pip reported no broken requirements. This does not replace lockfile installation or a vulnerability scan.

## Reproductions / focused checks

```sh
# Incorrect baseline CI command: exits 0 but reports zero files.
cd frontend
npm exec tsc -- --noEmit --listFilesOnly
```

Auth builder red: `venv/bin/pytest -q tests/test_auth_email_case_insensitive.py` → 2 failed / 12 passed before patch. Final reviewed check:

```sh
venv/bin/pytest -q tests/test_auth_email_case_insensitive.py tests/test_auth_user_routes.py tests/test_browser_session_security.py tests/test_network_member_access.py
```

42 passed after the independent legacy-zero correction. Webhook red (all provider/DB effects mocked):

```sh
PYTHONPATH=src arch -arm64 /usr/local/bin/python3 -m pytest -q tests/test_legacy_webhook_auth_security.py
```

Three expected failures before fixes: unsigned WhatsApp POST, default verify token, unsigned Telegram POST.

## Still required

Final patched clean-image build and browser-worker variant; repaired full backend green; hardened restore helper/full schema comparison; complete real-API browser journeys; image/log/final-source secret scans and resolved Python audit; five-flow performance/load measurements. Never invoke staging scripts casually against developer `.env`.

## Running isolated baselines

- Full baseline archive: `/tmp/localos-readiness-full.xWasXK` (89 MiB, originally tracked baseline only; subsequently only the Sheets test fixture reconnect was patched for its focused rerun). Recorded baseline captures predate that patch.
- Docker project: `localos-readiness-20260917`; local override `/tmp/localos-readiness-loopback.yml` binds app `127.0.0.1:18017`, PostgreSQL `127.0.0.1:15417`, internal runtime network. No workers/bot start, no inherited production env. Build uses canonical Dockerfile with staging browser download disabled.
- Named tmux: `readiness-docker-baseline`, script `/tmp/localos-readiness-docker-baseline.sh`; `build --no-cache app` captured as `raw/baseline-docker-build.json`.
- Initial wrapper attempt failed before build because sanitized PATH omitted Docker. Corrected PATH includes `/Applications/Docker.app/Contents/Resources/bin` and `/usr/local/opt/node@22/bin`. This was a harness error, not a product defect.
- Named tmux: `readiness-security-scans` completed; script `/tmp/localos-readiness-scans.sh`. Redacted Gitleaks history/current-source and Trivy vulnerability/config/license output stays in private `/tmp/localos-readiness-scans.nqz3lr`. Current94 candidates triaged as noncredentials; historical service-role/Wordstat exposure confirmed, revocation unknown.

## Completed isolated runtime checks

- `/tmp/localos-readiness-public-build.sh` builds baseline plus Docker-public packaging fix; `raw/docker-public-build-green.json` exit0, 39.493s. Both entrypoints/UID/permissions: `raw/docker-public-runtime-green.json` exit0.
- `/tmp/localos-readiness-staging-smoke.sh`: exit0, public-audit HTTP200; synthetic seed and `scripts/smoke_journey_staging.py` five-flow smoke pass. This creates synthetic local data only.
- `/tmp/localos-readiness-backend-baseline.sh`: F821 pass, empty DB migration head `20260907_001`, baseline pytest 3542pass19fail691skip1error. Legacy manual provider tests explicitly excluded.
- `/tmp/localos-readiness-sheet-fixture.sh`: isolated test DSN + Python network guard, focused recovery/queue16pass (2.68s tests; 3.238s wall), no external provider.

## Real API browser harness

From `/private/tmp/localos-readiness-frontend.IBVnun/frontend` using Node22 and Docker CLI on sanitized PATH:

```sh
JOURNEY_STAGING_BASE_URL=http://127.0.0.1:18017 \
JOURNEY_STAGING_CONTAINER=localos-readiness-20260917-app-1 \
node node_modules/@playwright/test/cli.js test --config playwright.journey-staging.config.ts --workers=1
```

Initial default-English run intentionally interrupted (exit130) after locale mismatches were confirmed. Raw JSON `baseline-real-api-e2e.json`; original screenshots/traces moved intact to `/tmp/localos-readiness-real-e2e-baseline-results`. Corrected locale run is `/tmp/localos-readiness-real-e2e-ru.sh` / tmux `readiness-real-e2e-ru`, label `real-api-e2e-locale-green` (label is not a verdict: inspect its child exit). At that baseline the compiled spec had hardcoded18006; commit0b571ed9 corrected its target. Actual compiled fixture remains required.

## Patched phase, 17 September 22:05 UTC

The prior corrected-locale full run finished95pass19fail; its artifacts remain in the original archive. Committed frontend harness centralizes baseURL, including legacy LOCALOS_STAGING_BASE_URL alias. Later a842d648 also removed the standalone script's historical defaults and generic queue claim; explicit verified local profile arguments are now required.

- `/tmp/localos-readiness-frontend-patched-build.sh`: fresh committed frontend archive (no .env), locked installed dependencies reused, same staging flags, both assets build in32.856s. Identity guards precede artifact copy into LOCAL staging app only. No production command.
- `/tmp/localos-readiness-patched-e2e.sh`: targeted registration-continuity + authenticated-quality, all three projects, **33passed94.759s**, child exit0. JSON `raw/patched-registration-quality-e2e.json`.
- `/tmp/localos-readiness-migration-chain-final.sh`: sanitized env, outbound guard, actual PostgreSQL testcontainers. `tests/test_work_review_migration_rollback.py tests/test_creator_portal_migration_rollback.py tests/test_creator_offer_distribution_migration_rollback.py tests/test_web_tracking_postgres.py` → **23passed69.89s**,70.415s captured wall. All cleanup targets disposable UUID databases.
- `/tmp/localos-readiness-frontend-aggregate.sh`: completed lint/typecheck/unit, all child exits0. Lint0errors/1existing warning14.728s, TypeScript36.781s, unit570passed/122files176.591s captured.
- `/tmp/localos-readiness-mocked-e2e-patched.sh`:72passed112.311s; own strict48173 Vite, no reuse, mocked API only.
- `/tmp/localos-readiness-backend-patched.sh`: clean ca8bdf0b archive; F821/migrations pass, full pytest3622passed691skipped1failed21errors. New synthetic DB name omitted mandatory `test` substring; preserve that fixture guard and create a new correct target. The one failed network-safety assertion saw inherited guard denial first. Raw JSON retains exact failure; do not overwrite it or blindly rerun createdb.
- `/tmp/localos-readiness-restore-rehearsal.py`: guarded local consistent-snapshot dump to private archive and restore to new UUID DB. Final tmux `readinessrestore4` log `/tmp/localos-readiness-restore-tmux-4.log`, exit0; source/target288tables' data/columns/constraints/Alembic match3.781s. Private evidence path in HANDOFF. No production backup or exhaustive schema/grant validation; target retained, no cleanup. Temp helper is evidence of this run, not the repository production restore runbook.

Never infer a green compiled UI from the basic seed. Follow HANDOFF's required verified sandbox profile and run-scoped fixture preparation before invoking its real runner script.

## Later checkpoint and interruption

- `/tmp/localos-readiness-backend-name-recheck.sh`: correct NEW test-named DB,43passed5.04s. Do not repeat its createdb verbatim.
- `/tmp/localos-readiness-data-regressions.sh`: real portable PostgreSQL data regressions+finance unit11passed12.78s,13.285s capture. Commits28019df1/3fadbabd.
- `/tmp/localos-readiness-browser-image.sh`: clean committed ca8 archive, ARM64 browser-enabled build296.953s and actual nonroot/read-only/network-none Chromium smoke3.811s, both pass.
- `/tmp/localos-readiness-runner-isolation.sh`: actual Docker sandbox script83.641s, pass; own temporary network/container removed by script, image retained. Not app-integrated fixture.
- `/tmp/localos-readiness-backend-final.sh`: archive3fadbabd `/tmp/localos-readiness-backend-final.F90et6`, NEW `localos_readiness_test_full_20260917`, F821+upgrade pass. Full3565passed691skipped4failed79errors166.905s amid Docker filesystem I/O. Prior output retained, no rerun yet.
- `/tmp/localos-readiness-data-image.sh`: image buildfailed2.979s containerdI/O; `/tmp/localos-readiness-image-scan.sh`: image scanfailed53.039s layerEOF; later secret scan in that script did not run. Neither is green.
- Root no-network pure check: `arch -arm64 venv/bin/python -m pytest -q tests/test_compiled_table_staging_harness.py tests/test_postgres_restore_helper_safety.py` in tmux with inherited Python no-egress hook →20passed2.14s, `/tmp/localos-readiness-pure-harness-final.log`.
- Future Trivy runs should explicitly reuse `/Users/alexdemyanov/Library/Caches/trivy`; sanitized env without HOME caused a second1.3GiB public database cache in `/private/tmp/trivy/db`. Only that verified-identical duplicate was deleted; original cache/reports retained. No broader cleanup or Docker restart performed.
