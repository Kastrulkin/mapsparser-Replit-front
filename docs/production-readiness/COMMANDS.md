# Verified commands and evidence

## TEST-E2E-04 — pure collector regression, 18 September 16:54 UTC

Completed named tmux sessions readiness-runtime-errors-{red,green,quality}.
`/private/tmp/localos-readiness-runtime-errors-check.sh` invokes the existing
capture helper in env-i with the pinned Python guard, no dotenv/bytecode and
Node22. Temporary `localos-readiness-runtime-errors.vitest.config.mjs` explicitly
sets envDir:false, node environment, one thread, no app setup and only the new
`src/test/stagingRuntimeErrors.test.ts`. No browser/DB/provider/app import.
Actual captured child:

```sh
node frontend/node_modules/vitest/vitest.mjs run --config /private/tmp/localos-readiness-runtime-errors.vitest.config.mjs
```

RED raw/staging-runtime-errors-red.json:8failed/7passed, exit1/3000.805ms.
GREEN raw/staging-runtime-errors-green.json:21passed, exit0/2273.639ms.
Both no timeout/truncation; red failures are assertion mismatches, not setup.
The extracted red collector preserves the original event handlers; green adds
origin parsing plus six unknown-source/configuration edge cases without
weakening the original fifteen assertions.

Scoped quality capture raw/staging-runtime-errors-quality.json:exit0/4169.954ms,
empty stdout/stderr, no timeout/truncation. From frontend, with the same empty
environment, `/private/tmp/localos-readiness-runtime-errors-quality.sh` uses
set-e to run both commands:

```sh
node node_modules/typescript/bin/tsc --noEmit --strict --target ES2022 --module ESNext --moduleResolution bundler --skipLibCheck --types node e2e/staging/runtimeErrors.ts e2e/staging/owner-reviews-finance.spec.ts src/test/stagingRuntimeErrors.test.ts
node node_modules/eslint/bin/eslint.js --max-warnings 0 e2e/staging/runtimeErrors.ts e2e/staging/owner-reviews-finance.spec.ts src/test/stagingRuntimeErrors.test.ts
```

Independent source/evidence reviewPASS. This is not a full frontend rerun or
real-browser console proof. The three original raw paths must not be overwritten.

## Read-only inventory reconciliation — 18 September 16:41 UTC

No tests/services were started. `git status/log`, `df -k .`, tracked-file and
source inspection covered Compose variants, worker ownership, three ops timers,
four workflows, canonical auth/membership helpers and provider entrypoints.
`jq` inspected exit/duration/truncation metadata from every `raw/baseline-*.json`.
`ls` on `/tmp/localos-readiness-scans.nqz3lr/trivy-source.json` and
`/tmp/localos-readiness-staging-smoke.log` returned absent for both. The command
capture for Trivy survives but does not contain its external detailed report.
The full Stage0 checklist in01-system-map preserves these distinctions.
No `.env` was loaded or environment-expanded Compose configuration printed;
no live provider/production access or daemon mutation occurred.

## Disk-stop continuation — prepared, NOT executed (18 September 16:29 UTC)

Mac free1,032,540KiB: no new process/browser/DB/build launches. Read-only
Docker info29.2.0 and project-filtered ps show own app/ingress/runner running,
Postgres/Redis healthy. No resources changed. The task guard thresholds remain.

After free space is reliably above2GiB, verify the two v8 hashes in HANDOFF,
then run the following from the repository in a NEW named tmux session. It is
a future process-only proof, not a completed test or authority for Docker build.
Require a fresh output path; never overwrite previous evidence.

```sh
env -i PATH=/usr/bin:/bin:/usr/sbin:/sbin PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/localos-readiness-resume-pg.anwDNv /usr/bin/arch -arm64 venv/bin/python /Users/alexdemyanov/.codex/skills/bug-reproducer/scripts/capture_command.py --label supervisor-v8-process-only --timeout 30 --max-output 16000 --output .agent/tasks/production-readiness-20260917/raw/supervisor-v8-process-only.json -- /usr/bin/arch -arm64 venv/bin/python /private/tmp/localos-readiness-process-supervisor-v8-proof.py --execute
```

Inspect actual child exit_code, timed_out, truncation and all ten proof rows;
capture helper exit0 alone is not success. Check no proof-owned children remain.
Only after passing proof/review may NEW guarded benchmark/demo wrappers use
the controller. Neither those wrappers nor a full comparison/rehearsal exist yet.

## Docker base-pin source checks — 18 September 16:22 UTC

Root executed the existing bug-reproducer capture helper with an empty
environment, ARM64 venv Python, PYTHON_DOTENV_DISABLED=1 and the pinned
native-loopback guard first on PYTHONPATH. Child command:

```sh
venv/bin/python -m pytest -q tests/test_docker_base_pins.py tests/test_docker_packaging_tools.py tests/test_docker_frontend_artifacts.py tests/test_docker_browser_permissions.py tests/test_docker_build_context_contract.py tests/test_release_constraints.py tests/test_staging_compiled_build_contract.py::test_canonical_image_accepts_opt_in_without_enabling_it_by_default
```

Actual capture `raw/docker-base-pins-root-20260918.json`:14passed0.19s,
exit0/557.788ms, no timeout/truncation, empty stderr. No DB, Docker daemon or
network used. Agent raw `docker-base-pins-static-20260918-captured.json` is a
separate actual8-test capture; its earlier handwritten `...static-20260918.json`
is only a note, not authoritative timing evidence. Public manifest proof is
`raw/docker-base-manifest-platforms-20260918.json`; metadata only, no layer pull.

## Later failed probes — 18 September 16:08 UTC

Demo one-shot outer `/private/tmp/localos-readiness-demo-272-root-capture.py
--execute` in tmux `readiness-demo-272` completed exit1/154.773944s with no
timeout/disk abort/truncation/page errors. Exact pins outer22354a8b,
shellc9a740c0,helperf1c4aeb2. First context captured loading; reviews confirmed
synthetic draft/manual boundary; content expected seed theme was not selected.
`demo-272{,-command}.json` remains FAIL, not a10–15min rehearsal. Targeted
process checks find no leftovers. Read-only exact synthetic DB check establishes
newer reconciliation plan selection, original seed still exists; no productbug,
reseed, deletion or provider effect. Separate retry package is only prepared.

Supplemental earlier-working-reference benchmark outer
`/private/tmp/localos-readiness-journey-measure-postfix-272794a4-root-capture.py
--execute`, SHA8c7a101a, launchere153907a, ran in tmux
`readiness-journey-postfix-272`. It failed at16:05:23 with PermissionError/errno1
before final inner output. Outer `-command.json` is invalid, not latency proof.
Partial archive/samples and residual syntheticDBOID5999213 are retained; target
process/session checks find none running. Supervisor failure cause is unknown;
do not replay or ignore permission errors. Headroom~1.90GiB blocks further
native/browser/Docker starts under unchanged guards.

## Browser performance retry — completed 18 September 15:30 UTC

Named tmux `readiness-frontend-perf-272-retry` ran ARM64 workspace Python with
sanitized environment and the one-shot command
`/private/tmp/localos-readiness-frontend-perf-272-retry-root-capture.py --execute`.
Frozen outer SHA256 `0e0528e17bdf599881e364b26a195d97f5227b2a292d540a13b9c1f5444b05b7`,
shell `94690117024e52d33f653f9cb481d7554d08ee8e154c4963ad4059252bf9cc1e`,
helper `0d6407af96750beea19e15a5768584cd206e95f95891ed0972743a75a1e1ea41`.
Raw/frontend-perf-272-retry.json and its -command.json are valid/exit0,
48.980093s/no timeout/disk abort/truncation. Independent count/quantile review
accepts60/60 samples; root viewed all six screenshots. Pinned historicalf0cc
backend, unchanged204frontend, existing ingress127.0.0.1:38019; no restart,
reseed or external effects. Only fixed synthetic login may POST.

First frontend-perf-272 attempt (without retry) remains exit1/4.144076s/zero
samples: HTML hash assumption ignored Flask SEO injection. Retry pins original
container index and compares all eight referenced served JS/CSS assets bytewise.
Report04 records limitations. Do not replay either completed wrapper.

## Sustained localhost reads — completed 18 September 15:18 UTC

Named tmux `readiness-http-sustained-272` ran ARM64 workspace Python with
`/private/tmp/localos-readiness-http-sustained-272794a4-root-capture.py --execute`.
Frozen outer SHA256 `e4826e78d47ee3ad7ec38e5624334cb585768b5ad414221b894706869356441d`,
shell `df7aa3c8537c6104fd9f9873cb2bfa1f4ca58e35541ccb4a49cef61022e73830`,
helper `5ca74c29f4655d65fd104439016f341bdd4af780808512c29cd4a6ddc409297b`.
Current272clean archive, four synthetic tenants,30waves/240semantic reads,
64.280315s timed/73.497287s captured, exit0/no timeout/truncation. Independent
counts/quantiles match;10periodic ps snapshots. Gunicorn reaped and owned DB
OID5775953 independently absent. This is bounded local load, not capacity/SLO
or memory optimization. Raw/http-sustained-272794a4{,-command}.json; do not replay.

## Native browser retry — completed 18 September 15:16 UTC

`readiness-native117-272-retry` completed one-shot outer
`/private/tmp/localos-readiness-native-real-api-117-retry-capture.py --execute`,
SHA86151240272cceb85ed758ca3dd4383c4fcb9b46853473c80a7befb457d8ff3d;
inner406e7b91, preview-config7e63822e. Canonical maps source added with APIFY
stillfalse; Vite preview root/outDir corrected before runtime. Full unchanged
117-case suite passes3.8min/capture261.027621s exit0/no timeout/truncation.
Initial curl connection refusal occurred during startup polling; readiness
later passed. No Vite development transform warnings in retry. DB5768975
removed/reaped, root catalog confirms absence. Firstfailed DB/raw preserved.
This is not a compiled-runner/current-image or clean-console guarantee.

## Native current-backend browser — first attempt, 18 September 15:06 UTC

Completed tmux `readiness-native117-272`; root ran hash-pinned
`/private/tmp/localos-readiness-native-real-api-117-capture.py --execute`
using ARM64 workspace Python. Outer SHA df96df88993a1f23af56fe93b8f23846e3cacb5d6c582ee2745be30b8818d18f;
inner d0cd5e32. Raw/native-real-api-117-272794a4.json:114passed/3maps failures,
exit1/293.833473s/no timeout. Failure is missing canonical yandex_maps source
in isolated environment (APIFY remains disabled), not demonstrated productbug.
Fresh failed DB OID5761996 preserved; Gunicorn reaped. Vite dev additionally
transformed built JS and warned about dependency scanning; static preview is
required for retry. Do not replay original one-shot wrapper or overwrite raw.

## Exact272794a4 aggregate / static checks — completed 18 September 14:46 UTC

Full suite PASS:4728passed/7explicit live-provider skips/6warnings656.63s,
capture669.910516s,exit0/no timeout/truncation. New DBOID5025701 removed after
normal success; independent catalog check confirms absence. Named tmux
readiness-backend-272794a4 invoked (completed; do not replay)
`/private/tmp/localos-readiness-backend-272794a4-capture.sh`, pinning reviewed
v4 launcher bd3be8ff and exact272794a439a76204536480f158e79276ccd7b318.
Fresh nonce DB and clean archive;1800s test bound/2400s outer capture; preserved
2GiB archive and1.5GiB runtime disk guards. Oldb43 app supplies only pypdf6.16.1,
not a current image. Destination raw/full-backend-272794a4.json is single-use.

`python-f821-272794a4.json`:exit0/0.208327s, standard scoped gate/exclusions,
tracked source matched HEAD and no untrackedsrc before the read-only check.
`secret-delta-346-to-272794a4.json`:strict Gitleaks --ignore-gitleaks-allow,
100%redaction,4commits/91659bytes,zero findings,exit0/2.550695s. No provider
validity test; historical credential revocation and finalimage/log scans remain.

## Stored mobile-action and subscription boundary — 18 September 14:26 UTC

Completed tmux `readiness-mobile-confirm-green`, paired one-shot wrapper
`/private/tmp/localos-readiness-mobile-confirm-green-capture-3dca5fda.sh`
SHA `51b17c465d95e0f84987777876e1454ccd1d5171945201ef1be5df6e6a11d307`.
Launcher `78bc1f2b81c031fd0223597ad3099be299cfcc5add3dd2b55ae6e62759b1e4fe`
creates clean3d archive plus explicit pinned source/test overlay. This overlay
is now exactly committed272794a4; raw filename retains base revision by design.
`operator-mobile-confirm-green-3dca5fda.json`:104passed156.03s,160.365553s
capture,exit0/untruncated. All disposable fixture DBs absent afterward.
Do not replay completed wrapper. Earlier corrected RED4fail/6pass and
capability RED2fail/2pass are in their separate immutable raw captures.

## CI contract check — 18 September 14:17 UTC

Completed one-shot tmux `readiness-ci-contract-root`, root wrapper
`/private/tmp/localos-readiness-ci-contract-root-capture.sh`; source script
`/private/tmp/localos-readiness-ci-contract-root.sh` hash
`f7980d46d7b3717d65dcaa1b360d7b2f06b64ab7a752aa82fe94822a0a0e93bd`.
It pins copies of only the workflow, launcher and contract test in a clean
temporary source with sanitized env/no-egress guard. No real Docker/browser
command is invoked. `raw/ci-real-api-contract-root.json`: 11 passed in 17.08s,
18.168537s capture, exit 0, no timeout/truncation. Committed as 3ac13d87.
Do not replay one-shot wrappers or treat this as a hosted runtime result.

## Release-profile and review-role checks — 18 September 13:52 UTC

- `release-profile-contract-root.json`: actual daemon-free Compose config plus
  migration startup contracts, 13 passed in 3.68s; capture 4.301181s, exit 0,
  no skips/timeout/truncation. Exact plugin supplied through
  `LOCALOS_COMPOSE_BINARY`; `env -i`, dotenv disabled, synthetic required DB
  inputs, `--env-file /dev/null`, no configuration/credential dump. The tested
  sources are committed in a00ac558. This is not a release startup or rollback.
- `operator-review-reply-viewer-full-red-3dca5fda.json`: 10 failed / 27 passed,
  104.57s; capture 109.002213s exit 1/untruncated. Both stored viewer types can
  mutate through five routes. Synthetic state diagnostics show the effects.
- `operator-review-reply-viewer-green-3dca5fda.json`: exact 3d archive plus
  fd70ef… API and 63cf2d… regression overlays passes 70 tests in 106.93s;
  capture 110.904479s exit 0/untruncated. New 37-case matrix plus 33 adjacent
  checks, not a whole-project aggregate. Fixture DB absence independently
  confirmed. Normal Telegram mobile-action confirmation is a separate pending
  causal check; no full feature-security closure is claimed yet.

Named tmux wrappers are one-shot and refuse an existing output/task directory.
Do not replay completed wrappers or overwrite earlier RED/failed captures.

## Historical command checkpoints

`operator-review-reply-viewer-red-3dca5fda.json`: first causal2case run,
1failed/1passed8.25s,exit1/11.165518s,no timeout/truncation. Stored direct viewer
webmanual route200vs403; owner persists intended manual status/review reply.
Before/after values are not in the first denial failure text; fullmatrix with
explicit synthetic state context is next. No new product fix or global RBAC claim.

HTTP corrected command/proof: `http-gunicorn-3dca5fda-retry-command.json`
exit0/13.170562s/no timeout/truncation; helper proofvalidtrue/40semantic successes
(4tenants×5rounds×2routes),timedwall2.557582s. New DB OID3967105 removed after
cleanGunicornSIGTERM/rc0/reap; independent catalog/quantile reconciliationPASS.
Helper597948... sets explicitFlaskapp; original capture/DB remain intact.
Report04 records20samples/route and diagnosticps snapshots without capacity,
SLO,mean/peakCPU/RSS or speedup claims. No source or production changes.

HTTP initial command/proof: `http-gunicorn-3dca5fda-command.json` exit1/3.080768s,
no timeout/truncation; `http-gunicorn-3dca5fda.json` validfalse,0requests,
Gunicornnotstarted, fresh synthetic DBOID3967104 preserved after setup error.
No latency/resource/capacity result. Child migration lacks explicit Flask app
configuration; exact diagnosis/correction remains in progress. Do not replay
the first wrapper or overwrite either raw destination.

## Full backend checkpoint — 18 September 13:11 UTC

`full-backend-3dca5fda-retry.json`:4655passed,7explicit live-provider skips,
6warnings,481.71s pytest/494.328144s capture;exit0/no timeout/truncation.
Migration/tests rc0,stagecompletevalidtrue,database_policy=dropped_after_normal_success.
Fresh database readiness_full_test_3dca5fda_acc3e129b8c0/OID3585990 owned by
readiness_test_owner removed only after exact identity validation and absence
confirmed. Failed first capture/DB remain separate. This is one full aggregate,
not a sum of causal/scoped results; nativePG15 plus cachedDockerPG16 groups.

## Historical frozen-source checks — 18 September 13:07 UTC

- `backend-causal10-3dca5fda.json`: exact10former failures pass20.23s,
 capture22.197591s,exit0,no timeout/truncation; no DB/migration/provider work.
- `full-backend-3dca5fda-retry.json`: RUNNING since13:02UTC, own tmux/fresh3d
 archive/nonce DB; reviewed v3 launcher9e02baec... pins plugin/cache locations.
 Original failed full capture and its DB remain untouched. Runtime verdict pending.
- `python-f821-3dca5fda.json`: canonical script on exact3d archive,exit0,
 0.532675s, no timeout/truncation. Script's declared fragment exclusions remain.
- `frontend-aggregate-3dca5fda.json`: exit1/562.759479s after successful lint
 (0errors/1warning),fullTS,591units/126files,72mockbrowser,bothbuilds12.60s/9.03s.
 Sole final failure is wrong helper assertion public-dist/public-audit/assets.
- `frontend-artifact-proof-3dca5fda.json`: separate read-only exit0/13.475289s,
 verifies699tracked3dfrontend blobs,257artifact files,11+3existing HTML refs.
 Manifest9e7fa5450d245b6b6aecb990955b2cde08b6529cab541ee53bf0c0db21a557e8.
 Source/build mtimes and original capture link this to the completed builds.
 Independent review PASS for two-capture stage evidence, not original aggregate.
- `secret-delta-24e-to-34618037.json`:4commits/50047bytes,zero findings,
 exit0/2.391691s; fully redacted strict delta, not final image/log/revocation proof.

## Frozen backend result — 18 September 12:47 UTC

`full-backend-3dca5fda.json`:10failed4645passed7live-provider skips6warnings,
502.58s pytest/515.906761s capture,exit1,no timeout/truncation. Migration exit0;
final stage=tests,valid=false,database_policy=preserved_on_failed_or_cancelled_test.
Fresh DB readiness_full_test_3dca5fda_c57379241521/OID3204881/ownerreadiness_test_owner
is intentionally retained. Independent diagnosis:8Compose CLI discovery and
2Python browser-cache lookup failures under clean HOME, before product assertions.
Retry needs exact child-environment preflight; no aggregate PASS claim.

Frontend RUNNING12:50UTC: `/private/tmp/localos-readiness-docker-resume.NsmVen/capture-frontend-3dca5fda.sh`
in tmux readiness-frontend-3dca5fda. Outer capture1350s; root process-group wrapper
1200s/1.5GiB runtime disk guard; reviewed launcher6d94679e... with pinned config
02d165a5... creates separate frontend-only3d archive. Existing dependencies,
explicit Chromium1234 cache, lint/fullTS/units/72mocked/bothbuilds, no real API.
Destination `frontend-aggregate-3dca5fda.json` remains pending until child result.

## Frozen full-backend run — 18 September 12:35 UTC

`strict-fresh-native-viewer-guard.json`:9pure tests pass0.33s/capture0.732428s,
no DB, exact env/sink URL. Reviewed guard-only commit3dca5fda accepts old exact
DB or only the strict fresh8hex_12hex name, not arbitrary readiness suffixes.
Full backend started from clean3dca5fdab9cfd5617ed3bbbc8dee099feeb1fcbc archive
using reviewed temporary launcher8e138cf8... and new owned native DB. Result
pending: `full-backend-3dca5fda.json`. Do not count this as a pass before its
child exit0/no timeout/no truncation/stagecomplete/validtrue and confirmed
exact fresh-DB cleanup. Source/environment/commands are captured there.

## Latest scoped checks — 18 September 12:31 UTC

- `finance-upload-admission-worker-red.json`: sentinel shows unbounded read,
 1fail0.28s/capture0.672627s. Worker31green is not the final sanitized-env proof.
- `finance-upload-admission-root.json`:30pass/1fixtureconfiguration failure,
 1.25s/capture1.838182s; correctly disabled dotenv left route-registration DBURL
 unset. `finance-upload-admission-root-retry.json`: explicit nonconnecting
 loopback:1 sink DBURL, pinned no-egress guard, disabled dotenv;31pass1.48s,
 exit0/2.156451s/untruncated. Commit015b4ebc independently reviewed.
- `aborted-build-2e-exact-cache-cleanup.json`: exit1/4.274283s before mutation,
 installed Buildx boolean filters returned no selected records.
 `aborted-build-2e-exact-cache-cleanup-retry.json`: exact anchored-ID fallback
 with unchanged per-record gates, exit0/12.286372s;12records removed, all other
 cache IDs and10images/16containers/18volumes/states preserved. Immediate host
 free delta -172032bytes; `post-cleanup-disk-during-backend.json` captured later
 at12:42UTC records3000356KiB (~2.86GiB) during backend, not immediate cleanup
 bytes. Cache is rebuildable;
 no image/volume/data deletion. [Docker selector documentation](https://docs.docker.com/reference/cli/docker/buildx/prune/).

## Latest Docker build — 18 September 12:13 UTC

Exact2e121912 credential-free archive started successfully; build stopped
at its own unchanged1.5GiB disk threshold during Chromium download.
`/private/tmp/localos-readiness-image-2e121912.abQZFx/build-capture.json`:
exit75/264.590877s/no timeout/no truncation, free1420404KiB. This is a safe
resource abort, not a compiler/test verdict or completed image. No smoke or
installed-map comparison ran; no user container/volume/image was removed.
Retain capture and source; retry requires restored>=4GiB after archive.
Byte-identical durable copy: `raw/docker-build-2e121912-disk-abort.json`.

`secret-delta-f0cc-to-24e.json`: Gitleaks f0cc182a..24e0d4cd checks11commits,
270636bytes, no findings, exit0/3.104201s (scanner2.04s), no timeout/truncation.
Full redaction and ignore-gitleaks-allow keep this a strict local delta scan;
the private JSON report is empty. Historical revocation/image/log scans remain.

## Current local checks — 18 September 12:07 UTC

- `agent-finance-untrusted-rows-root.json`: exact guarded nativePG runner→
  policy→finance→approval apply proof,1passed0.79s, exit0/2.743835s, untruncated.
  Root wrapper derives PYTHONPATH from the actual CWD, pins guardSHA534a36...
  and SHOW data_directory before pytest. Final file SHA d3014cad... was saved
  before capture start. Independently reviewed, test-only commit24e0d4cd.
  Initial missing-table diagnostics and worker PYTHONPATH typo are retained;
  no product defect is inferred from those fixture errors.
- `release-constraints-static-rerun.json`:11passed0.14s, exit0/0.428670s,
  no timeout/truncation. Source/static review PASS; commit2e121912.
  101application pins plus3Docker packaging pins project104distributions.
  The image build and exact installed-map comparison are pending, not passed.

## Verified reversible source-copy transfer — 18 September 11:50 UTC

`completed-snapshot-transfer-20260918.json`: exit0/100.868564s, no timeout or
truncation. Exact9completed source directories replaced by verified archives,
not image/container/volume/user data removal. SHA256-pinned manifest:
`/private/tmp/localos-readiness-completed-snapshots-20260918/manifest.json`,
`0c95fb50bc89335cdd162e6ceee94584a41e740e13a586991c059e06060f14d7`.
Net savings includingmanifest660267008bytes; free4500156KiB after transfer.
Every archive was extracted and full file hashes/modes/symlinks compared,
then its SHA and original manifest were rechecked before exact duplicate
removal. Active paths, nativePG, current/restore images and raw repo evidence
were excluded. Earlier below-estimate failure retained;4GiB build guard stays.

Old raw source paths are historical, not currently extracted directories.
Example recovery of one retained snapshot (only if original path is absent):

```sh
test ! -e /private/tmp/localos-readiness-query-20431224.wJNhxf
tar -xzpf /private/tmp/localos-readiness-completed-snapshots-20260918/localos-readiness-query-20431224.wJNhxf.tar.gz -C /private/tmp
```

Verify its recorded archive SHA against the manifest first. Do not replay old
startup/deploy scripts just because their source snapshot has been restored.

## Current local checks — 18 September 11:45 UTC

- `social-approval-binding-green5.json`: all8social modules,252passed/
  9viewer skips60.62s, exit0/61.291018s/no timeout/truncation. Skips caused by
  absent explicit viewer DSN, not deliberate external-provider exclusions.
  `social-approval-binding-viewer-green.json` separately pins migrated
  readiness_full_test_reviewed_20260918/35418 and guardSHA534a36...;9passed
  0skips2.43s. Source independently reviewed/committed13c1f36a. No261aggregate.
- `social-approval-binding-green4-failed.json`:1failed/251passed/9skipped
  63.04s; unbound text queue incorrectly returned needs_manual_publish.
  Source corrected to preserve approvable/queueable but non-sendable text.
  Initial13/38/9skip integration log and two collection errors remain retained.
- `completed-snapshot-compression-20260918.json`:9source snapshots archived,
  extracted and SHA/mode/symlink verified; exit1/143.631204s because measured
  projectedgain673988608bytes was below initial700MiB estimate. All originals
  retained, no removal. Explicit verified continuation is pending at this time.

## Current local checks — 18 September 11:25 UTC

- `readiness-native-routes-schema-archive-813609cc-final-20260918.json`:
  clean813609cc archive + exact four files now52292e6e; guarded localPG15;
  24passed/1Alembic warning9.25s, exit0/10.005698s,no timeout/truncation.
  Earlier dirty-worktree run23pass/1unrelated binding ratchet failure retained.
  `readiness-transaction-readonly-diagnostic-20260918.json`: actual transaction
  read-only=on, exit0/0.236915s; NO_BUG_PROVEN for implicit-BEGIN concern.
- `image-dependencies-f0cc182a.json`: exactb43 read-only/nonroot/no-network
  disposable image probe,104Python packages, exit0/2.924219s, container removed.
  `image-python-advisories-f0cc182a.json`: exact pins, strict PyPI audit with
  --no-deps --disable-pip, no application env/installation,104checked/0skips;
  exit1/9.582056s from12records/6unique pip24.0 advisories, not a scan failure.
- `dep-engine-static-root-retry-20260918.json`: four packaging/context/browser
  contract suites,8passed0.11s,exit0/0.428798s. The earlier root capture exit4
  names a nonexistent test file and ran no tests; it is retained, not product
  RED. Reviewed Docker pin26.2 committed65ca8836, image confirmation pending.

## Current local checks — 18 September 10:58 UTC

- `social-posts-viewer-rbac-expanded-green-20260918.json`:254passed0skipped,
  42.39s pytest/42.756374s capture,exit0/no timeout/untruncated. NativeDSNs
  both pin reviewed fulltestDB; guard-first env-i; nine selected suites include
  all13uncertain/concurrent/manual real-PG cases. Independently reviewed813609cc.
- `query-proof-20431224.sh`:clean204archive,exactguard/data_directory,newUUIDDB;
  validtrue,exit0/7.933036s. Auth4reads/business9reads0DDL, three tinyplans.
  Cleanuptrue and separatecatalog0; raw stale route_note explicitly corrected
  only for future captures, not retroactively rewritten.
- `social-approval-binding-causal-red.json`:real approval/claim/resolver/adapter/
  finalizer, fakeTelegram transport;7failed/1positive control passed20.22s,
  exit1/20.689397s,no timeout,stdouttruncated. Changed recipients reached
  transport, including postclaim interleaving. Source/visiblefailure limits
  are recorded; no product fix or real send in this capture.
- `trivy-vulnerability-db.json`:preflightexit1/0.354383s before download:
  free3.82GiB below4GiB guard. No scanner was spawned, no clean scan claimed.
- `query-note-tests.json`:12pure tests pass0.10s/0.584456s capture,exit0;
  only harness docstring/static route_note changed, not counting/SQL behavior.

## Current local checks — 18 September 10:45 UTC

- `build-content-focus.sh`: clean2d875357 archive plus three SHA-pinned files
  now committed20431224; fullTS,focusedlint,22units,bothbuilds pass84.349914s.
- `sync-mobile-layout.cjs --focus`: exact localapp/socket/image and previous
  indexSHA preflight; backup previousdist, replace only staticfrontend, compare
  servedindex and preserve all five container IDs/starttimes. Exit0/1.185817s.
  IndexSHA3141022cc76c0882855a4b88886e5a72a34583bfe231bd71e305b5fdbb252061;
  prior artifact `/private/tmp/localos-readiness-content-focus.S3o4Mi/previous-dist`.
- `content-focus-targeted.json`: six realAPI browser cases across3viewports,
  exit0/25.178298s. Full `content-focus-browser.json`:120passed,exit0/no timeout/
  untruncated,227.301080s. Node22,oneworker,closedexternalproxy,exact archive
  `/private/tmp/localos-readiness-content-focus.S3o4Mi/frontend`, existing
  synthetic fixture/compiled blueprint. Independent scoped review PASS.
- Earlier `mobile-content-layout-browser.json` finished117pass/3newfocusfail,
  exit1/248.788269s. This failed capture remains preserved, not renamed green.

## Current local checks — 18 September10:19UTC

- `business-data-preauth-causal-red3.json`: guarded native PostgreSQL,
 7failed/8passed22.08s (22.707s capture); actual registered-handler SQL is
 recorded, including forbidden DDL before403. Earlier collection/fixture and
 empty-spy captures remain invalid for DDL proof. After reviewed2d875357,
 `business-data-preauth-green.json`:15passed22.26s, exit0/no timeout.
- `inspect-mobile-content.cjs`: read-only DOM geometry and ordinary click on
 localstaging. `mobile-content-geometry.json` exit0 is diagnostic completion,
 NOT behavioral pass: normalClickFAIL and393→762/437px layout expansion.
 Separate CSS-only hypothesis restores393px and normalClickPASS4.005s.
- Canonical new mobile regression against oldimage: `mobile-content-layout-red.json`
 exit1/13.578s, actual369px overflow. `build-mobile-layout.sh` builds clean
2d875357 archive plus two exacthash-checked frontend files; focusedlint,
fullTS,19ContentPageunit tests and both builds pass81.932s. No dotenv files.
- `sync-mobile-layout.cjs`: exactlocal Docker socket/appID/image, olddist
backup, indexSHA comparison and unchanged fivecontainer IDs/starttimes.
Exit0/2.235s; servedindexSHA
`be591d38c15db6c75d2e8a61703c3ec88b92c31d2d230c5ebe7d18b8cd387e07`.
Onlylocalfrontendstatic files changed; backend remainsf0cc. Olddist in
`/private/tmp/localos-readiness-mobile-layout.wffmE5/previous-dist`.
- Full120browser run uses this isolatedfrontend archive, samebackend/DB,
oneworker/closedexternalproxy and fixedcompiledblueprint; raw
`mobile-content-layout-browser.json` pending at this timestamp.

## Current local checks — 18September09:57UTC

- browser-f0cc182a.sh:117realAPI exit1/259.528434s,114pass/3fail. Causes/traces
  inHANDOFF;2f fixes onlytestcontract. browser-2f224f05.sh pretestabort1.368715s
  hasemptylogs; archive/link exist, lockfilematches, laterdiskbelow2GiB.
  browser-2f224f05-retry.sh recordsstages/specSHA/disk andrunsfocusedESLint+
  117realcasesagainstunchangedf0cc runtime; retrypending.
- query-proof-f0cc182a.sh:cleanarchive/env-i/exactguard+PGdatadir, ownedUUID
  migrate/seed→routecounts+3representativeplans→cleanup. Raw
  query-proof-f0cc182a{,-command}.json validtrue/exit0/10.308584s,
  childcompleted/DBremoved. Auth4reads, business12=9reads+3DDL; nocapacityclaim.
- clear-completed-audit-cache.js:32explicitimmutable/private/reclaimableIDs
  validated;22pruned3.842GB/exit0/9.813535s. Raw
  completed-audit-cache-cleanup-retry.json preserves10images/16containers/
  18volumes andcontainerstatus/starttimes. Initial4.262s abortbeforeprune
  matchedstaletmux/zshlaunchertext; correctedactualexecutableguard.
  No processkills/image/volume/userdata removal. Hostfree1.8→5.4GiB.

## Current local checks — 18September09:35UTC

- `build-f0cc182a.sh` first failed6.111s because sanitizedPATH lacked Docker
  credential helper; immutable archive retained. `build-f0cc182a-retry.sh`
  reuses that exactsource with fullDockerbinPATH, same4GiB/1.5GiB guards.
  `docker-build-f0cc182a-retry.json`:exit0/55.385755s, bothfrontend builds,
  Node22 engine warning absent; imageb43efb29/1070645450bytes.
- `smoke-f0cc182a.sh`:actual exactimage, nonroot/networknone/read-only,
  bundledChromium153.0.8010.12/pypdf6.16.1/pipcheck/app+public artifacts PASS,
  exit0/3.721313s. Pip disables unwritable cache; not a dependency failure.
- `clear-node20-ancestor-cache.js`:8exactreclaimable/nonshared/immutableIDs,
  descriptions and17September21:06creation validated;312.8MBreclaimed2.409s.
  No images/containers/volumes removed; buildcache is rebuildable.
- Current ownedapp-only update: `update-compiled-f0cc.js`; fixedlocal socket,
  project/oldimage/network/appenv/head preflight, exactnewimage and untouched
  PG/Redis/runner/ingress IDs/starttimes assertions. Completed
  `compiled-update-f0cc182a.json`:exit0/4.533123s; subsequent HTTP200/health green.
  No production operation.117realAPIbrowser started09:34:57UTC, still pending.

## Current local checks — 18September09:10UTC

- `clear-node20-audit-cache.js` validates exact local socket and11anchored
  cacheIDs/private/reclaimable/types/descriptions immediately before pruning
  onlythoseIDs. Independent safety review PASS; raw
  `node20-audit-cache-cleanup.json` exit0/4.509s/Dockerreclaim1.168GB. No volumes,
  containers or images removed. Initial hostfree3.3GiB→eventually4.3GiB.
- `prepared-load-e3f42dbf.sh` cleanarchive first fails safely before timing,
  ModuleNotFoundError/cleanuptrue. Root regression captures
  `load-parent-import-{red,green}.json`:1causalred→45combinedgreen after94de718c.
- `prepared-load-94de718c.sh`: cleanarchive under tasktemp, exactguardSHA+
  datadircheck, env-i,8users/5cycles/childtimeout60s;10.172s/exit1 from
  same-IP5/minloginlimit (5HTTP200/3HTTP429), not a productfailure.
- `prepared-load-four-94de718c.sh`: identicalguard/source,4users/2concurrent/
  5cycles,9.249s captured/exit0;44/44semantic requests, createdDBremoved.
  Exactraw results and limitations in report04; no providers or production.
- `frontend-aggregate-6c96192c.sh` runs in namedtmux
  `readiness-frontend-aggregate`, archivefrontendunder853parentdirectory,
  unchanged tracked6c source plus temporary boundedPlaywrightconfig. Node22,
  same-lockfiledeps, lint/typecheck/fullunit maxWorkers1 and mockedroot-level
  browser specs workers1 with closedexternalproxy. Capture now complete:
  exit0/495.06755s,588unit/126files,72mockbrowser,TS PASS,lint0errors/1warning.

08:51UTC result: `full-backend-6c96192c.json` now records exit0/no timeout,
**4538passed/7skipped/5warnings in395.49s**,403.727s captured. The7skips are
six explicitly gated ChatGPT live-HTTP cases and one live Yandex connection;
all native/Docker synthetic groups ran. Warnings are upstream SWIG deprecations.
The one-shot script/archive/database below remain retained and must not be
created again. Later builder/read-load commits require their own runtime proof.

## Latest rerun — 18 September08:44UTC

- `social-extraction-tests.sh`: exact guard SHA/native data-directory check,
  six social suites plus size ratchet/benchmark/measure suites. Authoritative
  `social-extraction-root.json`:272passed38.43s, exit0,41.023s captured.
- `full-backend-d3ca8b1e.json` is a completed **failed** aggregate:
  3failed/3722passed/809skipped/1error,298.19s tests/306.617s captured.
  Root setup omitted frontend dependencies and four native test DSN keys;
  actual size-ratchet/empty-path regressions fixed in01446148/853bdc5d.
- Historical launch: named tmux `readiness-full-backend-reviewed` ran one-shot
  `/private/tmp/localos-readiness-docker-resume.NsmVen/full-backend-reviewed.sh 6c96192c`.
  Sanitized env-i, Node22, explicit local Docker socket; clean tracked archive
  under `/private/tmp/localos-readiness-final-853bdc5d.MjouFu/source`, same-lockfile
  node_modules link and verified pypdf6.16.1 private overlay. Fresh native DB
  `readiness_full_test_reviewed_20260918`; DATABASE_URL plus
  LOCALOS_READINESS_JOURNEY_DATABASE_URL, OPERATOR_VOICE_TEST_DSN,
  LOCALOS_TEST_DATABASE_URL, LOCALOS_RBAC_TEST_DATABASE_URL and
  WHATSAPP_ADMISSION_TEST_DSN all target that exact owned DB. Guard SHA and
  data_directory verified before create; archive-only sitecustomize link keeps
  guard in subprocesses which replace PYTHONPATH. No providers/dispatch enabled.
  Completed result `raw/full-backend-6c96192c.json`:4538pass/7skip/5warnings,
  exit0/403.726503s captured. This is the same checkpoint described above.

## Latest committed publication package and measurements — 18 September

- `d3ca8b1e` is the independently reviewed local SEND-AMB package, not a
  deployment. Script `social-publish-root-final.sh` in the retained taskdir
  checks native PG data_directory and guard SHA, then runs six social/API
  test modules with env-i, literal loopback DSNs and no providers. First raw
  `social-publish-root-final.json`:234pass/3legacy fake-cursor failures. After
  exact fixture correction, `social-publish-root-green.json`:237pass35.65s,
 37.569s captured, exit0. No red capture overwritten.
- `publication-ui-tests.sh`:19tests, focused ESLint and full app+Node TypeScript
  pass52.179s (`social-publication-ui-final.json`). Independent36-test backend
  output preserved via `send-amb-independent-pane-20260918.json`; the worker
  `send-amb-01-native-pg-lifecycle-final.json` is summary-derived, not a raw run.
- `measure-serial-8ebec5ca.sh`: reviewed driver with baseline30262a5b/current8eb,
 5warmups/50serial samples perref/no load. Captured543.315s, expected exit1
  for50baseline business HTTP500; current750/750requests+150/150invariants.
  Independently recomputed tables in report04; p99 exploratory/cold process.
  Post-run catalog check in `journey-measure-cleanup-check-20260918.json`.
- Historical launch: `full-backend-d3ca8b1e.sh` ran in named tmux
  `readiness-full-backend-d3ca8b1e`: clean tracked-source archive in
  `/private/tmp/localos-readiness-final-d3ca8b1e.Liqulf/source`, no .env, fresh
  `readiness_full_test_d3ca8b1e` on owned native35418; guard symlink added only
  to the test archive so subprocesses that replace PYTHONPATH keep the hook.
  Pure-Python pypdf6.16.1 copied from the verified local4a8 image into a private
  dependency overlay, shared venv unchanged. Docker socket is explicit, PG16
  testcontainers enabled, exact synthetic creator integration flag enabled,
  real providers/dispatch disabled. Output `full-backend-d3ca8b1e.json` records
  the failed result described above. This one-shot create/archive script is not
  replayable against retained directories/databases.

## Current image and compiled execution — 18 September07:15UTC

- Exact scripts under `/private/tmp/localos-readiness-docker-resume.NsmVen/`; all run through sanitized `env -i` in named tmux, explicit local Docker socket. `build-4a8e33b8.sh` uses clean archive, all8staging Viteflags, browser enabled; preflight4GiB/abort1.2GiB; raw `docker-4a8e33b8-build.json` exit0,61.615s. `smoke-4a8e33b8.sh` pins exact image ID, networknone/read-only/nonroot; raw smoke exit0,3.682s.
- `compiled-start.sh` first rejects existing project containers, uses reviewed five-fragment Compose chain plus resource/image-only `compiled-runtime.yml`, no pull/build/.env; creates exactly synthetic postgres,redis,app then seeds, enables exact UUID cohort and starts app/runner/ingress. Raw `compiled-4a8e33b8-start.json` exit0,25.671s. **Do not replay this one-shot script** against retained project resources.
- Clean archive `scripts/test_compiled_table_staging.py --base-url http://127.0.0.1:38019 --container localos-readiness-compiled-20260918-app-1 --ingress-container localos-readiness-compiled-20260918-audit-ingress-1 --compose-project localos-readiness-compiled-20260918 --app-environment staging --postgres-database localos_staging` ran with Python egress guard/explicitlocalsocket; raw `compiled-4a8e33b8-proof.json` exit0,11.760s.10previews+5realruns/replay, no fakecompletedrows.
- `browser-4a8e33b8.sh` currently executes all114existing stagedbrowser cases, Node22, identical locked dependency tree, temporary config only adds closed external proxy/outputdir, exact appimage/container and proofblueprint. Check actual raw result before claiming completion.
- `restore-helper-full-schema-20260918.json` records explicit trustedarchive/target/helper and independently rechecked fullschema/data proof. Source/target retained. Original `restore_compare.sh` alone is not authoritative (weak pipeline failure handling and a failed sequence query); final provenance distinguishes direct sequence/checkedpg_dump comparisons. No user DB restore.

## Resumed local Docker — 18 September06:15UTC

- `creator-native-test.sh`: first verifies the exact owned native data_directory on127.0.0.1:35418, creates NEW `readiness_creator_promotion_test_20260918`, applies canonical Alembic in cleana025archive, then enables only `CREATOR_PROMOTION_INTEGRATION=1` for one test with guard/env-i/dispatchdisabled. `raw/creator-promotion-native-integration.json`, exit0,4.440s total;1passed0.34s. DB retained, not a replayable one-shot createdb script. Seven live-provider cases intentionally unrun.

- Final a025 build capture exit0,276.824s; actual image sha256fd14a7bb7d7c1951139d392a72f079e238b1becaec0722e37ade72358675b50f. Smoke `raw/docker-a0253199-smoke-green.json` exit0,3.039s (UID10001, networknone, readonlyroot, pypdf6.16.1, pipcheck, Chromium). First smoke misnamed public entrypoint; preserved `docker-a0253199-smoke.json` is exit1/harnessmistake.
- `clear-old-audit-cache.sh` removed only ten validated unused private cache IDs of obsoleteca8 image; rawcleanup exit0,3.043GB. Old taskimage9a3 was untagged first after zero-container reference check. No system/image/volume globalprune; cache allowlist is retained. Hostfree eventually3.1GiB.
- `pg16-resumed-tests.sh` in namedtmux `readiness-pg16-resumed`:21files identified from Docker-related skips in the full5e capture; clean a025archive, explicitlocalsocket, sanitized env/provider guard, disposable PG16 testcontainers. Capture `raw/pg16-resumed-skipped-groups.json`:264passed177.72s/178.657s wall, exit0/no skips. This selection is not another fullbackend aggregate.

Earlier temp paths below are historical: archives, scripts, traces, dumps and scanner reports disappeared across host interruption/cleanup. Repository raw captures and commits survived. Explicit user permission now covers local Docker startup without reset; no user volumes/container data were removed.

- Fresh nativePG15 loopback35418 / `readiness_operator_test`, task-owned directory/guard in current HANDOFF. Actual Operator chat suite22passed1.15s; independent expanded44passed1.70s and adjacent24passed0.56s. Local commita0253199.
- Recovered durable clean5e1ebe79 capture: `raw/native-full-backend-5e1ebe79.json`, **4319passed117skipped5warnings**,296.79s tests/298.170s wall, exit0. The preceding clean91797c74 soleROI fake-cursor failure was corrected in5e1ebe79; no need to repeat that completed checkpoint.
- `open -a /Applications/Docker.app` executed after explicit permission. All Docker calls select `DOCKER_HOST=unix:///Users/alexdemyanov/.docker/run/docker.sock`. Read-only user-container status only; no user DB queries.
- Namedtmux `readiness-docker-probe` ran `/private/tmp/localos-readiness-docker-resume.NsmVen/storage-probe.sh`; new labeled internal network/volume/PG16container,10k synthetic rows, checkpoint/restart/customdump/newDBrestore/digest/pg_amcheck. `raw/docker-resume-storage-probe.json`, exit0,35.107s. No host port published by internal network; do not treat45418 as a reachable DSN. Dump SHA256 in HANDOFF.
- Namedtmux `readiness-image-a0253199` runs `build-current.sh` in that same taskdir: clean `git archive a0253199` under `/private/tmp/localos-readiness-image-a0253199.Oac4Vw`, no `.env`, canonical browser-enabled Dockerfile plus the seven staging Vite flags. Image `localos-readiness-20260918-app:a0253199`; capture `raw/docker-a0253199-build.json` must be checked for actual exit. Preflight free8.2GiB, heavyjobs serial. No scanner download/load alongside build.

## Native full-schema/browser phase — 17 September23:48UTC

- Task-owned native PG restarted with the exact validated data directory/loopback35417 from HANDOFF, not via initdb. `native-runtime.sh create/migrate/seed/serve` under `/private/tmp/localos-readiness-native-pg.QAg5UY/`: new `localos_staging_readiness_test_20260918`, b9a146aa tracked archive, no `.env`, synthetic seed, existing patched frontend artifacts, gunicorn127.0.0.1:38018. Full schema288tables/head20260907_001; no provider processes. Temp script is task-specific, not a new production runbook.
- `browser-tests.sh`: credential-free native Playwright on all114staging scenarios,3viewports/one worker/closed external Chromium proxy. First capture `raw/native-pg-real-api-browser.json`36pass78fixturefail153.249s; corrected `raw/native-pg-real-api-browser-unset.json`111pass3fail200.079s. Only remaining failures: no approved real compiled runner fixture, one perviewport. Separate artifact dirs `browser-results` and `browser-results-unset`; no old evidence overwritten.
- Old cleanb9a archive `/private/tmp/localos-readiness-security-final.YKHSLW` now has exactly the618native-helper delta, untracked native Playwright config and dependency/venv symlinks; backend tracked code stayedb9a during browser run. Do not call this entire directory pristineb9a any longer. Gunicorn was stopped by Ctrl-C in its ownedtmux; PG remains up for tests.
- `blueprint-root-tests.sh`: new agent role suite + finance/network/contracts54pass4.17s (captured4.965s). `whatsapp-root-tests.sh`: replay/auth47pass0.50s (captured0.838s). Both explicit own-native DSNs/guard/env-i; raw JSON records child exits0/no timeout. Reviewed scoped runs:118agent tests; frontend typecheck+scoped ESLint;7fixture units.
- `full-backend-tests.sh` extracts fresh committed91797c74 into `/private/tmp/localos-readiness-native-full.txtdq5`, selects new `readiness_full_test_20260918`, and forces DOCKER_HOST to a nonexistent task socket. Canonical empty upgrade passed3.318s; whole pytest currently running. It is not safely replayable against existing createdb/archive targets; use new names or inspect/resume the exact phase.
- Resolved Python audit: `arch -arm64 venv/bin/python -m pip list --format=json --disable-pip-version-check` →121pins in private task requirements. `trivy filesystem --cache-dir /Users/alexdemyanov/Library/Caches/trivy --skip-db-update --offline-scan --disable-telemetry --skip-version-check --parallel 2 --scanners vuln --pkg-types library --format json` recognized that one manifest and reported48findings. Raw `/private/tmp/localos-readiness-scans.nqz3lr/native-python-resolved-pins.json`; earlier direct site-packages report recognized0files and is not a scan pass.
- Trivy public database metadata was updated2026-09-17T19:08:59Z/downloaded21:14:59Z. At23:45UTC localfree~200MiB, verified exact regular cache files/noopenhandles, then removed ONLY `/Users/alexdemyanov/Library/Caches/trivy/db/trivy.db` and `metadata.json` (1.3GiB). Reports/pins retained; future offlineTrivy calls will require downloading the cache again. No Docker/DB/backup deletion. Laterfree2.6GiB after browser stopped.

## Native PostgreSQL/security phase — 17 September 23:22 UTC

- Fresh nativePG15.15 cluster identity and restart/stop boundary: HANDOFF. `/private/tmp/localos-readiness-native-pg.QAg5UY/start.sh` was run once in `readiness_native_pg`; do not replay initdb against retained data. No shared Docker command. Pure proof scripts use sanitized env, `PYTHON_DOTENV_DISABLED=1`, explicit synthetic DSNs, inherited no-egress hook and `arch -arm64` Python.
- `operator-tests.sh`: fixed3fadbabd archive,22files,704pass4fail54.71s; failures are missing journal network fixture tables. `journal-tests.sh`: current patched3files,79pass10.32s. `operator-tests-green.sh`: same original archive with only committed f128 fixture copied by apply_patch,713pass52.89s. All captured under `raw/native-pg-*` with non-overwritten red evidence.
- `security-final-tests.sh`: clean git archive **b9a146aa**,28files (22native families + RBAC/network/finance-route + contact/SSRF/outbound),826pass5warnings54.58s, captured55.518s/exit0/no timeout. Archive `/private/tmp/localos-readiness-security-final.YKHSLW`; raw `native-pg-security-final-b9a146aa.json`. It is not the entire backend suite or PG16 parity evidence. Script extracts into a task directory; use a new verified archive location for a future revision rather than overwriting this evidence.
- Root contact suite:76pass1.32s, `raw/ssrf-pinned-get-root-green.json`. Initial sanitized run omitted DATABASE_URL and failed one route-import test; original capture retained. Corrected explicit native test DSN, no application workaround.
- Finance native true red: `/tmp/sec_rbac_head_red.log` shows pre-fix viewerROI200 vs expected403; `/tmp/sec_rbac_target_red.log` shows requested-A/target-B mutation200. Final37pass1.80s `/tmp/sec_rbac_head_guard_final.log`; included in root826 aggregate. Missing-new-helper ImportError is not counted as a reproduced bug.
- Delta Gitleaks: `gitleaks git --log-opts=30262a5bf7b468e0a6f5a0e3d8262dbef119e075..0fdd3dce --ignore-gitleaks-allow --redact=100 --no-banner --no-color --report-format=json --report-path=/tmp/localos-readiness-scans.nqz3lr/audit-commits-through-0fdd.json .`.26commits/383.70KB/1.38s scanner, exit1 for3generic-key findings. Inspected exact88ad2437 source lines: SECURITY.md15, evidence.md18, system-map62 are ordinary prose, not credentials. No allowlist or history rewrite; later b9a/current-worktree not covered by this delta scan.
- After final tests: verified owned data_directory and zero other client connections, then named `readiness_native_pg_stop` ran `/usr/local/bin/pg_ctl -D /private/tmp/localos-readiness-native-pg.QAg5UY/data -m fast -w stop`; subsequent status reports no server running. Data/archive/evidence retained. User PostgreSQL/Docker resources untouched.

Latest server reconciliation (23:00–23:02 UTC) used read-only SSH commands, each starting `cd /opt/seo-app`: `df -h`, `docker compose ps`, counted recent app log error markers, local HTTP HEAD, local/public health, anonymous auth, limited `docker inspect` state/image fields, read-only PostgreSQL revision/start-time SELECTs, live Alembic `ScriptDirectory.get_heads()`, and backup file metadata. Results are recorded in `docs/RUNTIME_RELEASE_20260917.md`; no build/restart/upgrade was rerun. With streamed SSH scripts, prevent `docker compose exec -T` from consuming the script's remaining stdin; the migration graph/backup checks were completed in a separate `ssh -n` invocation.

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
