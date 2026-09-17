# Production-readiness progress

Updated: 2026-09-17 22:48 UTC / 18 September Moscow. **IN PROGRESS — not production-ready sign-off.**

## Current infrastructure interruption

Local Docker/EXT4 I/O errors interrupted the next image build, image scan and final backend run. Host space fell to1.3GiB; only the audit-created duplicate public scanner cache was removed (1.3GiB; identical original retained), leaving2.6GiB. No daemon restart, volume deletion or production action. Shared local Docker restart approval requested, not received. See [incident and recovery requirements](LOCAL_DOCKER_INCIDENT_20260917.md). Do not repeat heavy Docker work yet.

## Scope and authority

The whole original objective is preserved in `.agent/tasks/production-readiness-20260917/spec.md`, AC1–AC11. Local fixes, isolated synthetic tests and local commits are authorized; no new production mutation, push, merge, deployment or external sends are included. Prior runtime maintenance is a separately completed operation, not this audit's release.

Branch `codex/production-readiness-20260917`; baseline `30262a5bf7b468e0a6f5a0e3d8262dbef119e075`, initially clean. Latest code checkpoint `a842d648`; see fresh git log for later documentation checkpoints. No intentional mutation of unrelated Docker services/volumes.

## Phase checklist

- [x] Canonical rules/product model/original request and proof bundle; architecture/security/DevOps reconnaissance.
- [x] Clean baseline frontend install, lint, explicit TypeScript app+Node,557 unit, both builds,72 mocked browser tests and npm audit.
- [x] Credential-free backend baseline with PostgreSQL; actual failures recorded (not declared green).
- [x] Canonical ARM64 Docker build, empty PostgreSQL upgrade, nonroot/protected source runtime checks.
- [x] Public artifact packaging fixed and tested in clean isolated image, public HTTP200 and five-flow API smoke.
- [x] Twenty-two small local commits througha842d648, independently reviewed; no deployment.
- [x] Patched frontend aggregate: 570 unit tests, 72 mocked browser scenarios, lint and app+Node TypeScript pass.
- [x] Original registration/navigation and mobile geometry failures now pass in real-API33-test rerun across desktop/laptop/mobile.
- [ ] Complete remaining compiled runner fixture + all final real-API browser checks.
- [x] Guarded migration rollback aggregate: 23 real PostgreSQL tests pass; distribution fix committed.
- [x] Consistent-snapshot backup restored into a new isolated database; 288 tables match in data, columns and constraints. Not a full schema/production restore proof.
- [x] Hardened local-only restore helper and compiled fixture guards: independently reviewed; root20purefake tests passed.
- [ ] Actual guarded-helper execution and restore verification of remaining schema objects.
- [ ] Full backend green: ca8 harness causes corrected; subsequent3fadbabd run3565passed691skipped4failed79errors interrupted by local Docker/PG I/O. No product-regression verdict from this environment failure.
- [ ] Reproduce/resolve remaining data/concurrency/SSRF/RBAC/idempotency/scope candidates; confirm tenant/object/role boundaries.
- [ ] Full current-source/history/image/log/dependency threat and supply-chain closure.
- [ ] Five-flow before/after p50/p95/p99, bounded load and query plans.
- [x] ARM64 browser-enabled image and real nonroot/offline/read-only Chromium launch.
- [ ] Final patched/AMD64 image, operational readiness/recovery/CI/runbook checks.
- [ ] Rehearsed safe10–15min demo and all named reports.
- [ ] Fresh whole-diff independent review, final aggregate checks and original DoD reconciliation.

## Baseline evidence

Captured command/cwd/exit/time/output in task `raw/baseline-*.json`. Frontend exported from baseline into `/private/tmp/localos-readiness-frontend.IBVnun/frontend`; later locale-only harness edits do not change the preserved baseline evidence.

| Check | Result | Captured wall time |
| --- | --- | ---: |
| Locked npm install |470packages; exit0 |10.461s |
| Frontend lint |0errors,1existing any warning auth_new.ts115 |13.984s |
| App+Node TypeScript |pass |34.838s |
| Frontend unit |557passed /121files |149.304s |
| Both frontend builds |pass; third-party PURE annotation warnings |25.266s |
| Mocked browser |72passed /3viewports; not API/tenant proof |102.145s |
| npm audit |0reported vulnerabilities at capture |1.844s |
| Python F821 |pass with documented fragment exclusions |0.442s |
| Backend pytest excluding unsafe legacy |3542passed,19failed,691skipped,1error |257.034s |
| Empty DB Alembic upgrade |head20260907_001, pass |11.852s |
| Clean no-cache Docker ARM64, browser download off |pass; UID10001/source nonwritable |375.375s |

Python local pip check passes but is neither a lockfile install nor a vulnerability audit. Floating Python/base-image dependencies remain open.

## Closed local packages — see change log for limits

| Finding | Commit | Verification |
| --- | --- | --- |
| Inactive sessions |b95aad11 |root42pass; reviewer40pass; legacy string0 regression |
| Real CI TypeScript gate |faefef25 |6real compiler cases, actual package script |
| Authenticated webhook ingress |21c79e4c |root83pass; reviewer85pass; provider rebind required before rollout |
| Finance import scope/native input |f7357c63 |4race/reset cases, reviewed |
| Public Docker packaging |bd5c52e1 |static4pass; clean image/public200/five-flow API smoke |
| Client/worker/Sheets fixtures |c4cbbdff |11client/worker +16Sheets; reviewed |
| Work-review guarded rollback |f16aa159 |7real-PG cases incl concurrent writer |
| Webhook replay/logging |5e2412bb |89pass with caplog/PII sentinels; WhatsApp replay remains separate |
| Creator-portal guarded rollback |04e8c5ca |4PG tests, root19.35s; locks/data refusal |
| Revoked dashboard scope |98bd5ecf |5cases; private-state remount, transient retry and race guards |
| Journey registration/lifecycle |22589aed |red2/7 →11pass; live registration15/15 after rebuild |
| Influencer mobile targets |adae95d6 |unit2pass; actual mobile geometry now passes |
| Real E2E harness contracts |0b571ed9 |reviewed locale, success POST+UI, shared target; no skip |
| Distribution guarded rollback |40f261b0 |11 cases; combined migration chain23passed69.89s |
| Founder/Telegram eligibility fixtures |bd300829 |red2 → green2; both files198passed7.82s |
| Legacy test quarantine |f25f3455 |4 isolated safety checks; aggregate exposed nested-guard assertion issue |
| Isolated Python browser harness |ca8bdf0b |10passed34.24s; strict own-port, mock-only API, failed-start process cleanup |

Clean image public fix: `sha256:3dc995eb73758128a56c4c1e42e43f3ca61c9c6725c70b3f12329958b12276f7`, build39.493s with cached dependency layers. This backend image contains baseline plus packaging only, NOT subsequent auth/webhook patches.

## Current real-browser result

- First default-English run intentionally interrupted after identifying locale mismatch:39pass19fail1interrupted55notrun,449.607s, exit130. Evidence retained.
- Corrected-locale full run: **95passed /19failed**,330.392s. Fifteen registration failures split between a real async navigation race and stale success-copy expectations; one mobile target failure; three compiled wrong-port failures.
- Runtime fixes + strict corrected harness rebuilt from committed source with no .env. Build both assets exit0 in32.856s; copied artifacts only to verified local synthetic app, no backend/container/DB restart.
- **Patched targeted real-API run:33passed in94.759s**, `raw/patched-registration-quality-e2e.json`: registration→confirmation→selected action for5flows ×3viewports plus6authenticated-page quality checks ×3viewports. No unexpected API denials, all mobile target assertions pass.
- This is NOT a final114-test green suite. Compiled runner proof requires real sandbox/profile/fixture absent from basic seed. The remaining unchanged specs and new backend image require final aggregate rerun.

## Patched aggregates and restore

- Frontend: lint0errors/1existing warning (14.728s), TypeScript36.781s, unit570passed/122files (176.591s captured), mocked browser72passed112.311s. All captured child exits0; mocked API is not tenant/runner proof.
- Backend clean archive ca8bdf0b: F821 and empty upgrade pass. Full suite **3622passed,691skipped,1failed,21errors**,296.28s tests/297.468s captured. All21 setup errors rejected a DB name without required `test`; the one failure saw the outer network guard before the child guard. Both harness causes were subsequently corrected/rechecked, as below. No full-suite green claim.
- Restore: `/private/tmp/localos-readiness-restore-72f33d10b62d43cb86c6900dbcfab506/evidence.json`; custom archive1,009,542bytes, SHA256 `513cef196f14274f77e13778b8a9689e5ce1c2576691cae85f00f6c94520f278`;3.781s. Source read-only exported snapshot and target cluster identity verified. All288 public tables' counts/content, logical columns, constraints and Alembic revision match. Independent review confirms these limits: indexes/triggers/views/functions/sequences/grants were NOT fingerprinted. Target/archive retained privately, cleanup not performed.
- Both data candidates reproduced and fixed:28019df1 draft row lock,3fadbabd per-row finance savepoint. Independent review required portablefixtures and stronger service lock-wait proof; root combined11passed12.78s. No production deployment.
- Correctly named DB rerun43passed5.04s confirms prior21setup failures were guard configuration, not product failures. Nestedguard assertion9aa140f0 normal/outerguard5pass each. New final3fadbabd run failed on Docker/PG filesystem I/O; see incident.
- ARM64 browser-enabled ca8 Docker build296.953s and network-none/read-only/nonroot Chromium smoke3.811s passed. Real standalone compiled sandbox proof83.641s passed. New3fadbabd image build and Trivy scan failed on Docker I/O/EOF, not green. AMD64/app-integrated compiled proof remain absent.

## Security / operations remaining

Current tracked-baseline Gitleaks94 candidates triaged:83verified integrity hashes +11fixtures/docs/semantic IDs, no confirmed credential in that archive. Historical704 candidates include confirmed privileged Supabase service-role and Wordstat token exposure; revocation unknown, owner asked. No live key testing, rotation or history rewrite. Final current files, Docker layers/logs and resolved Python package scan still required.

No confirmed current P0 at this checkpoint; audit incomplete. Remaining P1s/gaps: historical revocation, safe restore tooling, reproducible/immutable release, full compiled runtime proof, data/race/role/SSRF/ambiguous-send candidates that require reproduction. P2: readiness/CI/test-harness, scope candidates, measurements and observability. No new P3 cosmetic expansion.

Production read-only follow-up confirmed eight services and9.6GB free, unchanged PostgreSQL revision/head and restart time. Telegram had two polling-stall restarts and transport errors; no root-cause repair, no production mutation during audit.

## Next step

Finish pure local harness reviews/commits and preserve evidence. Shared Docker recovery needs user approval and adequate disk headroom; then revalidate local storage before final image/backend/real-browser reruns. Continue remaining data/role/SSRF/retry coverage, five-flow measurements, scans/reports/demo and final independent audit. Goal remains ACTIVE; proof overallFAIL, final verdictUNKNOWN.
