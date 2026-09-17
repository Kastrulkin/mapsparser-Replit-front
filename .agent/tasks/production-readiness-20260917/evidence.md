# Evidence Bundle: production-readiness-20260917

Status: **FAIL / incomplete whole-goal evidence**, updated 2026-09-17 UTC. This is a progress checkpoint, not final independent sign-off.

Latest interruption: full3fadbabd rerun3565passed691skipped4failed79errors and next image build/scan failed on local Docker/EXT4/PG I/O. See `docs/production-readiness/LOCAL_DOCKER_INCIDENT_20260917.md`; host2.6GiB after exact duplicate-cache cleanup, shared local Docker recovery permission requested. No heavy job is still running. Later pure harness packets a04686de/a842d648 independently reviewed and combined20passed2.14s, without Docker.

## Source and acceptance

The original complete request and AC1–AC11 remain in spec.md. evidence.json maps all11criteria to captured evidence and explicit gaps. verdict.json remains UNKNOWN because the final whole-diff verifier has not run; per-package independent reviews are recorded in the change log.

## Verified evidence groups

- Latest nativeSQL/security phase: fresh loopback PostgreSQL15.15, exact owned data_directory; journal704pass4fixture failures→713pass, then cleanb9a146aa selected28-file826pass5warnings54.58s. `raw/native-pg-security-final-b9a146aa.json` exit0/no timeout55.518s. Commitsf1287d81/0fdd3dce/b9a146aa independently reviewed. Own cluster stopped afterwards; no shared Docker restart. This does not prove full backend/PG16 parity. Original false RBAC fake-label/ImportError claims were superseded by real stored-membership/HTTP-effect proof.

- Clean frontend baseline:557unit,72mockedE2E, app+Node typecheck, both builds, lint0errors/1warning, npm audit0. Exact cwd/commands/duration/warnings in raw/baseline-frontend-*.json.
- Clean backend baseline:3542passed,19failed,691skipped,1error; raw/baseline-backend-tests.json. Do not replace this baseline with later targeted results.
- Reviewed local fixes: inactive sessions, authenticated ingress, Telegram replay admission/log redaction, finance/dashboard scope, journey navigation, mobile targets, CI typecheck, Docker public packaging and test fixtures. See docs/production-readiness/06-change-log.md for exact red/green captures, reviewer evidence and commit scope.
- Clean ARM64 Docker public packaging image: both entrypoints, UID10001/read-only source, public HTTP200, isolated synthetic five-flow API smoke. raw/docker-public-{build,runtime}-green.json. Image does not include subsequent backend security fixes and disables browser download.
- PostgreSQL rollback:23passed69.89s across work-review, creator portal, offer distribution and existing web-tracking upgrade→downgrade→upgrade contract; raw/migration-rollback-chain-final.json. Includes lossiness refusal/data retention and three concurrent-writer cases. No production downgrade.
- Real API browser baseline:95passed19failed330.392s after locale correction, raw/real-api-e2e-locale-green.json (actual exit1). Naming is not verdict.
- Patched frontend build32.856s plus targeted real API33passed94.759s across desktop/laptop/mobile, raw/frontend-patched-build.json and raw/patched-registration-quality-e2e.json. Registration/email/selected-action continuity and authenticated quality are proven for this local build; compiled scenario not included.
- Patched frontend aggregate:570unit/122files,72mockedE2E, lint0errors/1existingwarning and explicit app+Node TypeScript pass. `raw/frontend-patched-{lint,typecheck,unit,mocked-e2e}.json`.
- Patched backend ca8:3622passed691skipped1failed21setup errors297.468s. DB-name guard errors corrected by using NEW valid test target; focused43pass. Nested outbound-guard assertion repaired and independently reviewed9aa140f0, normal+guarded5pass. Full3fadbabd rerun completed3565pass691skip4fail79errors166.905s during Docker/PG I/O failure; not green.
- DATA-SVC and DATA-FIN real PostgreSQL races reproduced and reviewed fixes committed28019df1/3fadbabd. Portable disposable fixtures and stronger service lock wait proof required by review before acceptance. Root combined11pass12.78s; `raw/data-concurrency-root-green.json`.
- ARM64 browser-enabled image ca8 build296.953s, Chromium153.0.8010.12 smoke3.811s with UID10001, read-only root/source, no network and both frontend artifacts. `raw/docker-browser-ca8-{build,smoke}.json`; excludes later two data patches. Actual standalone compiled Docker sandbox passes83.641s, `raw/compiled-runner-docker-isolation.json`; actual app-level compiled fixture still absent.
- Actual local backup→restore: one exported consistent snapshot, verified local cluster, fresh UUID DB;288publictables data/counts/logical columns/constraints and Alembic revision equal,3.781s. Independent review confirmed limits: not indexes/triggers/views/functions/sequences/grants, not production backup. Private archive and target retained; metadata path in HANDOFF.
- Current-source baseline secret scan94candidates triaged as noncredentials; historical704candidates include confirmed privileged exposure, revocation unknown. Private scan evidence stays outside tracked artifacts; no credential values copied here.

## Commands and replay

Exact sanitized command captures include cwd, child exit_code, timed_out, duration_ms and bounded stdout/stderr. The capture wrapper's own successful exit only proves JSON was written. Command recipes and isolated environments are in docs/production-readiness/COMMANDS.md and HANDOFF.md.

Use named tmux and credential-free archives. Docker app18017/PG15417/testcontainers are currently unavailable pending storage recovery; do not replay them blindly. The retained native PostgreSQL cluster can be restarted using the exact owned-path command in HANDOFF. Do not load local .env, hit arbitrary development apps, send providers or mutate production.

## Unproven requirements

All residual whole-goal gaps are explicit in evidence.json and problems.md: full backend and114realAPI aggregate, actual compiled app fixture/profile, complete tenant/role/security/data concurrency audit, dependency/image/log scans, real guarded-helper execution/full schema comparison, AMD64 image, five-flow latency/load measurements, operational runbook, demo rehearsal, eight remaining reports and final independent whole-diff review.

The scaffold raw/build.txt, test-unit.txt, test-integration.txt, lint.txt and screenshot-1.png are placeholders, NOT evidence. Structural proof-loop validation does not mean readiness or passing acceptance.
