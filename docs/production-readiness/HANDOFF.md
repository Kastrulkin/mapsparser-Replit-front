# Readiness handoff

## Latest continuation — 17 September 23:22 UTC

The user's repeated server-maintenance request is already satisfied by the earlier runtime-snapshot release, reconciled live again in `docs/RUNTIME_RELEASE_20260917.md`: 9.6 GB free, eight services running, DB revision equals live head, no duplicate restart/build/migration. Telegram is currently healthy but restart count increased to six. This request does not require restarting shared local Docker Desktop; its incident/recovery boundary below remains unresolved.

Three packages are now committed and independently reviewed: `f1287d81` canonical network schema in journal fixtures; `0fdd3dce` pinned public contact GET; `b9a146aa` finance viewer/write and stored transaction-target authorization. Earlier mocked RBAC claims were replaced by actual native PostgreSQL/Flask red and green proof. Final clean `b9a146aa` archive: **826 passed, 5 third-party warnings, 54.58s** (55.518s captured), `raw/native-pg-security-final-b9a146aa.json`. This is a selected28-file aggregate on PG15, not the whole backend or productionPG16 suite. UX-SVC-01, UX-CONTENT-01 and UX-OP-01 route-switch candidates were reconciled as NO_BUG_PROVEN due to keyed Outlet. Working threat model `03-security-threat-model.md` distinguishes evidence from untested AI/tool boundaries.

Safe native fallback: a fresh owned cluster `/private/tmp/localos-readiness-native-pg.QAg5UY/data`, PostgreSQL15.15, literal127.0.0.1:35417, synthetic role `readiness_test_owner`. Databases `readiness_native_test` and `readiness_rbac_test`; no user/production data. Initially41MB, later215MB including WAL/catalog churn. It was stopped cleanly after all tests and zero other client connections; retained, not deleted. Shared Docker was not accessed/restarted. Reuse only after `pg_ctl status`/directory validation; do not rerun `start.sh` because it intentionally requires a fresh cluster. Safe restart command inside named tmux: `/usr/local/bin/pg_ctl -D /private/tmp/localos-readiness-native-pg.QAg5UY/data -l /private/tmp/localos-readiness-native-pg.QAg5UY/postgres.log -o '-h 127.0.0.1 -p 35417 -k /private/tmp/localos-readiness-native-pg.QAg5UY -c max_connections=20 -c shared_buffers=16MB -c max_wal_size=128MB -c min_wal_size=32MB' -w start`. Inspect exact directory and loopback bindings before tests. Native pgvector extension files are installed, but full native migration/app/browser fallback has not been run yet.

Final clean archive `/private/tmp/localos-readiness-security-final.YKHSLW` (b9a146aa); runner `/private/tmp/localos-readiness-native-pg.QAg5UY/security-final-tests.sh` is evidence, not blindly replayable because it extracts into that existing archive. The older `/tmp/localos-readiness-backend-final.F90et6` now contains3fadbabd plus the committed f128 journal fixture for causal713-pass replay; it is no longer an untouched3fadbabd archive. Next safe work: native full-schema/app/browser fallback, generic mutation role/object matrix, WhatsApp durable admission/reconciliation and uncertain sends; then performance, remaining scans/reports/demo. WhatsApp design review only, no implementation yet. Its processing has multi-commit/tool/provider effects, so admission-only suppression must not be called exactly-once or silently complete ambiguous outcomes.

Updated 2026-09-17 23:22 UTC / 2026-09-18 Moscow. Goal ACTIVE, incomplete. Continue current work; do not restart baseline inventory or reduce the original scope.

## STOP before further Docker work

Local Docker storage reports containerd/EXT4 I/O errors. Shared Docker restart approval was requested, not received; no reset/prune/user-volume changes. Read `LOCAL_DOCKER_INCIDENT_20260917.md` first. Host now2.4GiB free after lightweight native testing/archive; the server's9.6GB free is a different filesystem. Native isolated PostgreSQL enables actual SQL work without Docker recovery; no heavy image build/scan yet.

## Scope, source and authority

- Branch: `codex/production-readiness-20260917`.
- Baseline: `30262a5bf7b468e0a6f5a0e3d8262dbef119e075`, initially clean.
- Current code checkpoint: `b9a146aa` (27 commits since baseline, before later documentation). Always read fresh git status/log.
- Original full request preserved in `.agent/tasks/production-readiness-20260917/spec.md`; AC1–AC11 cover the entire goal.
- Local changes, synthetic isolated PostgreSQL/browser tests and local commits authorized. No new audit push, merge, deploy, production data/schema change, external send or credential rotation.
- Prior Docker snapshot/PG restart maintenance was separately completed and reconciled read-only; see `docs/RUNTIME_RELEASE_20260917.md`. No need to repeat it. The audit patches are NOT deployed.
- Historical privileged Supabase/Wordstat credential exposure confirmed offline. Revocation status asked, not received. Do not test keys, reveal values, rotate or rewrite history without authorization.
- All long operations named tmux. Python native wheels require `arch -arm64 venv/bin/python`. Never introduce casts or `as`. Use apply_patch for edits. Preserve other agents' work.

## Completed local packages

`b95aad11` inactive-session denial; `faefef25` real CI typecheck; `21c79e4c` authenticated WhatsApp/Telegram callbacks; `f7357c63` finance scope/native-file reset; `bd5c52e1` both frontend artifacts in Docker; `c4cbbdff` client-info/worker/Sheets fixtures; `f16aa159` guarded work-review rollback; `5e2412bb` Telegram replay admission + safe webhook logs; `04e8c5ca` guarded creator-portal rollback; `98bd5ecf` dashboard revoked/stale scope; `22589aed` stable journey registration/lifecycle; `adae95d6` mobile influencer targets; `0b571ed9` staging locale/registration/endpoint harness.

Each scoped package reviewed independently; exact evidence/limitations in `06-change-log.md`. No final whole-diff review or aggregate sign-off yet. Telegram webhook deployment requires provider rebind; it is not a drop-in rollout.

Further committed packages: `40f261b0` distribution guarded rollback; `bd300829` founder/Telegram fixtures; `f25f3455` fail-closed legacy quarantine and default-test safety; `ca8bdf0b` isolated Vite/Python browser harness with bounded startup and process-group cleanup.

New: `9aa140f0` nested guard assertion, `28019df1` service compression apply row lock, `3fadbabd` finance per-item savepoint. Root actual PostgreSQL combined11passed12.78s; reviewed.

`a04686de` fresh-local-only trusted restore helper; `a842d648` guarded compiled staging profile and run-scoped claim. Both independently reviewed, root purefake aggregate20passed2.14s (`/tmp/localos-readiness-pure-harness-final.log`). No actual execution of these helpers after Docker failed.

## Current independent work / ownership

- `migration_distribution_verify`: SSRF package complete/committed, idle.
- `inactive_session_fix`: finance role/target package complete/committed, idle.
- `readiness_patch_review`: all three latest packages approved; WhatsApp design review only; idle.
- Root: clean final826-test aggregate complete, native cluster stopped; no active audit test/build job. Unrelated finance_patch_review/localos-voice-final tmux sessions untouched.

## Environments and evidence — do not lose or prune

- Original clean frontend archive: `/private/tmp/localos-readiness-frontend.IBVnun/frontend`. Subsequently only locale config was patched; baseline artifacts predate change.
- Original full archive: `/tmp/localos-readiness-full.xWasXK`; only Sheets reconnect fixture subsequently patched. Do not call this entire directory pristine now.
- New frontend archive: `/tmp/localos-readiness-frontend-patched.XCFKVn/frontend`, application sources from commitadae95d6, harness files refreshed from0b571ed9, dependency symlink to original locked install, no .env.
- New build: `raw/frontend-patched-build.json`, exit0,32.856s. Built app/public with same staging flags, copied artifacts only into verified LOCAL staging app; no backend/container/DB restart.
- Docker project `localos-readiness-20260917`; app `localos-readiness-20260917-app-1`, HTTP `http://127.0.0.1:18017` via ingress proxy. App only on internal no-egress network; blank providers, SMTP localhost1, no bot/operator/worker processes.
- PostgreSQL loopback15417, separate `localos_staging` synthetic demo and `localos_test` pytest DBs. Credentials are synthetic in isolated scripts. Unrelated `seo-postgres`, `seo-redis`, `riderra-main-postgres` are user resources, never prune/restart.
- New archive `/tmp/localos-readiness-full-patched.o7ntNI` is tracked ca8bdf0b plus symlinked frontend dependencies/built artifacts, no .env. Failed aggregate used NEW `localos_readiness_final_20260917`: fixture guards require `test` in name. Keep it, create a different test-named DB for rerun; do not weaken fixture guards.
- Final archive `/tmp/localos-readiness-backend-final.F90et6` is tracked3fadbabd with dependency/artifact symlinks. `/tmp/localos-readiness-backend-final.sh` created `localos_readiness_test_full_20260917`; do NOT blindly rerun createdb. It completed with Docker/PG I/O failures, not green. Correct-name targeted run used `localos_readiness_test_targeted_20260917` and43tests passed before the incident. No running audit tmux jobs remain.
- Docker CLI `/Applications/Docker.app/Contents/Resources/bin/docker`; socket `unix:///Users/alexdemyanov/.docker/run/docker.sock`; Node22 `/usr/local/opt/node@22/bin`.
- Python network guard `/tmp/localos-readiness-guard.sHLsSu/sitecustomize.py` blocks providers/unrelated local app ports; sanitized env wrappers in /tmp. Beware subprocesses that override PYTHONPATH.
- Host free9.2GiB at22:30UTC,1.3GiB during incident,2.6GiB after exact duplicate-cache cleanup. No user data/volume cleanup.

## Baselines and live check to collect first

- Frontend baseline557unit /72mockedE2E, lint0err1warning, typecheck/build/npm audit pass.
- Backend baseline3542pass19fail691skip1error in257.034s. Patched aggregate ca8:3622pass691skip1fail21errors in297.468s, `raw/backend-patched-full-tests.json`. All21 errors are test-name DB guards; single failure stricter parent no-egress guard vs child message assertion. No product defect proved by these failures. Legacy now safely excluded in pytest.ini (not ad-hoc --ignore).
- First real API E2E interrupted after locale diagnosis:39pass19fail1interrupted55notrun. Artifacts intact at `/tmp/localos-readiness-real-e2e-baseline-results`.
- Corrected-locale full realAPI run:95passed19failed in330.392s, `raw/real-api-e2e-locale-green.json` exit1 despite misleading label. Artifacts remain in original frontend/test-results. Failures:15registration(runtime race + stale success-copy assertions),1mobile target,3compiled wrongport.
- Corrected causal journey red2fail7pass (4GET vs1; stale response rewrites login URL), green11pass. Additional late preparation/token tests included. Full typecheck39.149s and focused lint pass; reviewer combined13pass/typecheck.
- Patched real-API browser check completed: **33passed in94.759s**, child exit0. Script `/tmp/localos-readiness-patched-e2e.sh`, log/exit with same prefix. Tests ONLY journey-registration-continuity + authenticated-quality, all three viewports. Capture `raw/patched-registration-quality-e2e.json`. Registration and mobile target failures resolved in this local build; full114-test sign-off remains absent.
- Capture helper writes JSON and returns0 even on test failure. Inspect `exit_code`, `timed_out` and actual suite scope.
- Patched frontend aggregate complete:570unit/122files176.591s, TypeScript36.781s, lint14.728s (1existing warning),72mocked browser112.311s. Raw `frontend-patched-{lint,typecheck,unit,mocked-e2e}.json`.
- Migration aggregate23real-PG tests69.89s/70.415s captured; covers3guarded historical migrations and web-tracking chain. All committed.
- Local restore completed3.781s,288tables matched content/counts/logical columns/constraints/Alembic only. Evidence/archive private at `/private/tmp/localos-readiness-restore-72f33d10b62d43cb86c6900dbcfab506/`, target `localos_readiness_restore_72f33d10b62d43cb86c6900dbcfab506` retained. Independent review found no target/snapshot flaw, but **not full schema**: indexes/triggers/views/functions/sequences/grants unverified. Does not harden unsafe repository restore helper or prove production backup restore. Temp rehearsal source `/tmp/localos-readiness-restore-rehearsal.py` not suitable for commit unchanged.
- Subsequently the repository helper was independently hardened/committed, but its actual stream was not exercised. Final3fadbabd suite3565passed691skipped4failed79errors166.905s; all four test failures shown are PG I/O, setup/teardown errors include Docker filesystem I/O.691skip categories are in incident report;668are missing `OPERATOR_VOICE_TEST_DSN` and can potentially run on a validated isolated DB, not live providers.
- Browser-enabled image ca8 built296.953s and actual Chromium smoke passed3.811s; exact image ID/limits in incident report. `/tmp/localos-readiness-data-image.sh` then failed3fadbabd build2.979s on containerd I/O. `/tmp/localos-readiness-image-scan.sh` failed53.039s on image-layer EOF; subsequent new-commit secret scan never ran. Do not claim an image scan pass or restart those heavyweight jobs yet.

## Compiled runner prerequisite (not executed / not faked)

The basic seed does not produce the approved compiled-run fixture. App-integrated runner flags/profile remain absent. The standalone Docker sandbox script passed83.641s, actual inspected local image ID `sha256:59bcb20b99892291c8db3c5ff9105139e35773c7bf4dccdd74f99ef5b027ea98`, and removed only its temporary runner/network before the incident. This is not app UI proof.

`scripts/test_compiled_table_staging.py` is now guarded/run-scoped and requires explicit app/ingress/project/env/DB arguments. It validates this task's fixed proxy hash, internal network/alias and exact loopback mapping. Durable proxy/profile packaging and actual10previews/5runs remain. Local synthetic integration may pin inspected image ID per runner README; production deployment checker requires real manifest/RepoDigest. Verified synthetic owner business `db746101-5ebc-4c4c-9fc5-0e2ffae725a1`; no cohort flags were changed. Do not fake completed rows or skip assertions.

## Immediate next tasks

1. Resolve requested permission for shared local Docker recovery and sufficient host headroom. No reset/deletion of user volumes. Read incident; after approved recovery verify resource/DB integrity before restarting checks.
2. Final code image, isolated whole-backend aggregate and safe additional DSN-bound integration tests; preserve prior failed captures and choose a fresh test DB. Run heavy jobs serially; reuse scanner cache explicitly.
3. Durable compiled local profile + real fixture, then complete real-API browser aggregate. No synthetic pre-completed records.
4. Remaining whole-goal gaps: data/SSRF/RBAC/idempotency/scope; resolved Python/image/log/final-source scans; restore full schema verification; AMD64; five-flow p50/p95/p99 and bounded load; demo/all named reports; final whole-diff review. Source-only independent work may continue without Docker.
5. `evidence.json` overallFAIL and final `verdict.json` UNKNOWN intentionally. No production-ready claim; scaffold raw placeholders are not evidence.

Resume safely:

```sh
git status --short --branch
git log -6 --oneline
tmux list-sessions
tail -30 /tmp/localos-readiness-backend-final.log
git diff --check
```
