# Evidence Bundle: production-readiness-20260917

Status: **FAIL / incomplete whole-goal evidence**, updated 2026-09-18 UTC. This is a progress checkpoint, not final independent sign-off.

Latest10:58UTC evidence supersedes historical checkpoints below: clean6c96192c
backend **4538passed/7live-provider skips/5warnings**,395.49s, exit0; frontend
588unit/126files,72mockbrowser,fullTS,lint0errors/1warning PASS495.068s.
Reviewed125900b2 service/content viewer fix has27focusedpasses; finalaggregate
after that change remains. Cleanf0cc182a Node22 image builds bothfrontends
55.386s and passes real nonroot/read-only/offlineChromium+pypdf+pipcheck smoke
3.721s. First build's missingcredentialhelper failure is retained separately.
Ownedstagingapp-onlyupdate passed4.533s, other4service IDs/starttimes unchanged.
Current20431224 frontend passes120/120real-API browser cases227.301s,exit0/no
timeout, independently reviewed. Prior116/117 failure reproduced369px mobile
overflow; the two-class correction then exposed3newfocus failures in120cases.
The reviewed invoker-focus fix passes22units/fullTS/lint/bothbuilds84.350s and
the unchanged full120suite. Failed captures are retained. Onlyownedlocalapp
frontend/dist was replaced, olddist preserved; fivecontainer IDs/starttimes
unchanged. Backend/image remainsf0cc; servedfrontend has separate identity,
not a final immutable combined-image claim.
Prepared94de dashboard profile passes44/44requests; failed8target login-limit
boundary is separate. Actualf0cc queryproof passes10.309s: auth4reads,
business9reads+3DDL and tiny representative plans; ownedDBremoval verified.
CausalGET tests then reproduce request-timeDDL for403 and denied valid readers.
Reviewedcommit2d875357 removes legacyDDL and uses canonical read access;
15new/adjacentreal-PG checks pass22.26s. Final aggregate remains pending.
Genuine fresh whole-diff review30262a5b..2f224f05 completedFAILacrossAC1–AC11,
including social-viewer mutation then causally reproduced on nativePG.
Reviewed813609cc passes254tests/0skips42.39s; earlier233/21legacy-fixture failures
are retained. Post-GET SQL proof204passes7.933s with9reads0DDL. Approval-binding
RED7fail/1positive pass20.22s actually sends to changed fake recipient before/
after claim; stdouttruncation retained. Frozen-descriptor fix is starting.
Trivy DB download refused low startingheadroom before spawn; no scan. Final scans,
demo, approval-binding, wider role/tool coverage and corrected-revision re-review remain.
No production changes, user-volume reset or real provider send. Current
resources/authority are in HANDOFF's newest section, not obsolete paths below.

Historical interruption: full3fadbabd rerun3565passed691skipped4failed79errors
and image build/scan failed on local Docker/EXT4/PG I/O. Approved no-reset
restart and fresh PG16 storage/restart/restore/amcheck subsequently passed.
See `docs/production-readiness/LOCAL_DOCKER_INCIDENT_20260917.md`; historical
failures were never converted to green or used to certify old user volumes.

## Source and acceptance

The original complete request and AC1–AC11 remain in spec.md. evidence.json maps all11criteria to captured evidence and explicit gaps. verdict.json records the genuine fresh review's FAIL snapshot at2f224f05; subsequent scoped fixes do not retrospectively change that verdict. Per-package independent reviews are recorded in the change log.

## Historical verified evidence groups (exact checkpoints, not current state)

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

Use named tmux and credential-free archives. Old Docker app18017/PG15417
resources are not current targets; do not replay historical startup scripts.
Current owned nativePG15 port35418 and DockerPG16/compiled staging resources
are in HANDOFF. Do not load local .env, hit arbitrary development apps,
send providers or mutate production.

## Unproven requirements

Residual whole-goal gaps are mapped in evidence.json/problems.md: final
same-revision aggregate after remaining role/approval patches, immutable-image
browser proof, complete role/AI/tool boundaries, dependency/image/log scans,
AMD64 image, query/server/queue performance, operational closure, demo
rehearsal and fresh independent whole-diff review. Full synthetic restore,
compiled runtime, working00–10reports and prior aggregate checkpoints exist;
they are not substitutes for those remaining gates.

The scaffold raw/build.txt, test-unit.txt, test-integration.txt, lint.txt and screenshot-1.png are placeholders, NOT evidence. Structural proof-loop validation does not mean readiness or passing acceptance.
