# Verified commands and evidence

## Generic campaign dispatch identity — 20 September, parent7b41e8a9

Captures: existing task evidence/manual-campaign-dispatch-*.json. Named
localos-campaign-identity-* tmux launches; private arm64 Python3.11.7/env-i/-I/-B,
explicit support/manual_campaign_dispatch_pure_check.py, no conftest/plugin
autoload/cache, pre-import DB/socket/dotenv/child-process guards. Both actual
snapshot hashing and preflight/binder run; SQL and unrelated gates are fake.

| Suffix | Outcome | Duration ms |
| --- | --- | ---: |
| red | causal5fail/1pass,0.15s; zero recorded forbidden attempts |513.364|
| green | initial109pass,1.26s; zero recorded forbidden attempts |1787.738|
| final | expanded138pass,1.27s; zero recorded forbidden attempts |1795.702|
| quality | five files, Ruff F821/F822/F823 no-cache; pass |79.648|
| manifest | five tested source/test/bootstrap SHA-256 records |39.974|
| precommit | five hashes match; staged diff and Gitleaks pass |1393.913|

All listed captures exit as expected, without truncation/timeouts; test stderr
is empty. Native PG, provider dispatch, OS isolation and full backend aggregate
are not claimed. The author/Riderra adjacent selection excludes native tests and
the subprocess runner-help case. No frontend code changed or build/deploy ran.
Browser observations and residual original-contact-value/concurrency limits are
recorded in manual-campaign-dispatch-notes.md. Overall acceptance stays FAIL.
Independent bounded source/evidence review PASS is in manual-campaign-dispatch-
review.md. Gitleaks scanned the staged package (~62493bytes), not history,
images or logs; final documentation only adds these observed metadata results.

## Exact draft approval snapshot — 20 September, parent79d7b227

Captures for this package are in the existing task's `evidence/` directory
(not its older `raw/` directory), with prefix `draft-approval-`. All launches
use named `localos-draft-approval-*` tmux sessions. Private arm64 Python3.11.7,
env-i, -I -B, plugin autoload disabled and explicit support/draft_approval_pure_check.py
selection prohibit DB/network/dotenv/child processes before app imports. Only
fake cursor/effect boundaries run; final recorded forbidden-attempt counters0.
Node22 frontend checks use the existing GtHPOV/no-egress-compatible.cjs chain,
envDir:false and frontend child cwd. This is not an OS/native isolation proof.

| Capture suffix | Result | Duration ms |
| --- | --- | ---: |
| red | x86_64/arm64 psycopg2 import mismatch before tests; NOT causal |443.404|
| red2 | actual arm64 runner4fail/1pass, zero guard attempts |1093.250|
| green | intermediate307pass |2169.596|
| green2 | intermediate311pass |2185.514|
| backend-final | final313pass/1.66s; all guard counters0 |2149.401|
| ui | earlier11pass before actual main-panel integrations |8236.820|
| ui-final | final16pass/3files/14.49s, both controls with spy callbacks |16316.089|
| quality | earlier TS/lint pass before final UI integration |59272.045|
| quality-final | app/node TS and full lint pass;0errors/1existing warning |68514.283|
| ruff | four Python files, F821/F822/F823, no cache;pass |87.732|
| build | local canonical-config app build;pass |28499.077|
| integrity |199reachable JS assets;pass |289.258|
| full-ui |684pass/132files, but source changed during run; nonfinal |335145.413|
| full-final | frozen684pass/132files/308.62s;exit0/untruncated |309982.748|
| source-manifest |15 SHA-256 records: sources/tests/guards/index |38.494|
| precommit |15hashes match; staged diff/FAIL ledger/Gitleaks pass |1417.411|

Frozen full-final is one complete current frontend run, not a union. It retains
expected negative-test/jsdom diagnostics in stderr, not an empty-stderr claim.
No failed suites or unhandled-error result was reported. Complete command,
stdout/stderr, timeouts and truncation flags are retained in every JSON capture.
Build artifact: `/private/tmp/localos-draft-approval-build-20260920.nGsezM/dist`,
entry `index-CGcZxJQ5.js`, CSS `index-BM6vOqzw.css`. No dist or production sync.
Expected upstream Yandex PURE comments and external-outDir warning are retained.
New build has no native-browser proof. Independent bounded review PASS is in
evidence/draft-approval-review.md; whole-project acceptance remains FAIL.
Precommit secret check covered the staged package (~253229bytes), not history,
images, logs or revocation of historical credentials. The final documentation
adds these observed results; no application/test source changed afterward.

## Managed Progress display contract — 20 September, parent2fac7241

All operations use named readiness-card-copy/readiness-managed tmux sessions.
Backend: env -i, private arm64 Python3.11.7, -I -B, disabled plugin autoload,
support/card_growth_pure_check.py explicitly selects two files with no conftest
or cache. Its process-local bootstrap rejects DB connections, socket operations,
dotenv reads and child processes before imports. Final recorded counters all0.
Frontend: Node22, env -i, no dotenv (support/managed_growth_vitest.config.mjs
envDir:false), mocked request boundary, one worker. Final2 targeted/full/types
runs additionally preload the existing GtHPOV/no-egress-compatible.cjs chain;
this is a JS guard, not an OS/native isolation proof. No backend server starts.

| Raw capture suffix (20260920.json) | Result | Duration ms |
| --- | --- | ---: |
| card-growth-copy-red |27failed/12passed; missing additive metadata|516.225|
| card-growth-copy-reviewed |212passed/0.16s; zero recorded guard attempts|487.598|
| card-growth-copy-quality |scoped Ruff F821/F822/F823;exit0|96.959|
| managed-progress-ui-red |causal Spanish rendering1failed/4passed|9003.237|
| managed-progress-ui-final2 |15passed/3files/9.62s;empty stderr|11084.613|
| managed-growth-types-lint-final2 |app/node TS and lint pass;1existing warning|57763.466|
| managed-growth-build-reviewed |app build19.80s;exit0|21438.911|
| managed-growth-build-integrity |199reachable JS assets;exit0|410.232|
| managed-growth-frontend-full |665passed/7failed plus1suite error;cwd ENOENT only|310913.613|
| managed-growth-frontend-full2 |676passed/131files/305.19s;exit0|306719.104|
| managed-growth-precommit-quality |20manifest entries match;staged diff/ledger and Gitleaks pass|1877.860|

Full2 is one complete frontend aggregate, not a union of partial runs. Its child
first changes cwd to frontend, because static tests use process.cwd/readFileSync;
Vite root alone does not change those paths. Same frozen source/config/guard,
no exclusions or assertion weakening. All final captures are untruncated and
not timed out. Full2 stderr retains expected negative-test diagnostics, not
an empty-stderr claim; the Vitest result has no failed suites or unhandled errors.
The precommit checksum reader reports one extra blank input line from jq -r;
all20actual entries match. Staged Gitleaks finds no leaks (~543470bytes), not a
whole-history/image/log or historical credential-revocation certification.
The checked app artifact is /private/tmp/localos-managed-growth-build-20260920.uLLxel/final-dist;
no production/dist sync. Build child cwd is frontend, imports the canonical
Vite config with envDir:false, VITE_COOKIE_SESSION_AUTH=true, and a fresh
external outDir. Existing Yandex PURE-annotation warnings and the explicit
external-outDir no-empty notice are preserved. Public build is not rerun by
this package. Source/test/guard/artifact hashes are in managed-growth-source-
manifest; exact commands, complete outputs and timing are in each raw capture.

Intermediate failures are retained, not counted: first backend green used a
wrong duplicate fixture key; first types had two incomplete locale records;
first build used wrong cwd; UI green/reviewed/final have ambiguous selectors,
LanguageProvider timing or missing jsdom scrollIntoView. Final2 restores a
scoped scrolling stub and checks real audit-region focus with deterministic
RAF; native smooth-scroll behavior is not proved. No product scroll code changed.
Independent source review PASS is scoped to managed panel/direct-focus/audit;
shared JourneyActionCard and whole-product UX remain unresolved. No native DB,
new-build browser, current image, deployment or whole-goal PASS claim.

## Current native Python advisory scan — 20 September, parentaf351060

Private interpreter /private/tmp/localos-backend-deps-v2-20260920.xYc0jK/venv/bin/python,
arm64 Python3.11.7, pip-audit2.10.1. The advisory command ran once in named tmux
readiness-native-audit-20260920 with env -i, NETRC/PIP_CONFIG_FILE=/dev/null,
no bytecode/user site, safe import path, and isolated cache. Exact child:
`python -I -B -m pip_audit --local --strict --vulnerability-service pypi --format json --desc off --aliases on --progress-spinner off --timeout 15 --cache-dir /private/tmp/localos-native-advisory-20260920.LYhCkc/cache`.
Only public package names/versions were queried; no --fix, app import, DB,
Docker, installation, dependency update, production or provider operation.

| Raw current-native capture | Result | Duration ms |
| --- | --- | ---: |
| dependency-parity |133/133 exact installed/artifact map;3current manifests unchanged;exit0|206.481|
| python-advisories |133checked,0skips,0advisories,0fixes;exit0|15948.290|
| license-metadata |133entries,56License-Expression fields;artifact parity true;exit0|172.238|
| advisory-evidence-validation |complete captures and exact audited/installed maps;exit0|10.696|

All four outputs are complete and not timed out. Scanner stderr is only
`No known vulnerabilities found`; other stderr is empty. An initial verifier
attempt named nonexistent /usr/local/bin/jq and failed before execution/capture;
the corrected verifier uses the observed /usr/bin/jq. Its durable result, not
the failed wrapper, proves map/count equality. Independent scoped review PASS.
Metadata parsing imports no application or installed package modules; it uses
the known process-local guard and exact private prefix. No legal compliance,
Docker/Linux, native embedded library, bot/AMD64 or whole-goal claim follows.

## Guarded reset regression — 20 September, parentcf36cbb0

Root-owned named tmux runs used env -i, private arm64 Python3.11.7, disabled
bytecode/plugin-autoload/dotenv, unchanged XoKy4o guard plus the stricter scoped
support/password_reset_pure_check.py. Modes baseline/current/adjacent accept
only the seven reset cases or those plus three auth-security/six cookie cases.
The synthetic URI satisfies engine initialization only; all psycopg2 connects,
socket operations, dotenv reads and unexpected children remain denied.

Raw password-reset-guarded-red:6fail/1pass0.44s,2765.219ms,exit1. Same current
green:7pass0.43s,2386.050ms,exit0. Adjacent:16pass0.53s,2586.098ms,exit0.
All three final captures are untruncated/no timeout/empty stderr and every
recorded denied-operation counter is zero. A separate quality capture exits0
in536.396ms: source AST syntax, test/support Ruff F821/F822/F823, diff check,
nine file hashes and structural proof-bundle validation. Git emits a benign
confstr temp-directory warning; this is not an all-repository lint assertion.

Do not count preliminary unguarded worker runs, config-error baseline, or
exit79 bootstrap-bind diagnostic as acceptance. Their correction and limits
are recorded in raw/password-reset-evidence-notes-20260920.md. The final
fixture prevents urllib3's unrelated IPv6 bind probe without allowing any
network access. Baseline replaces only the byte-pinned historical handler,
not the whole application or rate-limiter wrapper. Final independent PASS is
scoped to source/fake regression evidence, not native SQL or full-goal readiness.

## Colleague Telegram routing — 20 September, parent a231abb8

Named tmux, private arm64 Python3.11.7, `env -i`, unchanged guard before `src`,
no DSN, bytecode or plugin autoload. Explicit pure files only; native
`test_operator_workday.py` was deliberately not run. Raw namespace
`operator-colleague-transport-*-20260920.json`:

- `red`: initial fake delivery state was recreated; retain as harness evidence.
- `red2`:4failed/3passed,0.18s/477.956ms, causal missing configured proxy kwargs.
- `green`:9passed,0.19s/500.412ms, focused plus outbound-helper tests.
- `final`:3failed/29passed; new positive-replay assertion incorrectly expected
  `delivery_state` instead of the existing receipt-only replay response.
- `final2`:32passed,0.90s/1406.815ms; includes pure voice queue/autosubmit/followup
  and userbot proxy adjacency. No timeout/truncation/stderr. A stub verifies
  committed attempt before effect and no second request for success/unknown.

These are process-local fake DB/HTTP checks, not a real proxy, delivery, SQL,
concurrency, full backend suite or production result. Real role SQL is not
exercised by the mocked authorization-denial control.

## Execution-admission and social re-admission — 20 September, parent381de671

All pure pytest captures use the private arm64 Python3.11.7 environment, `arch -arm64`,
`env -i`, no bytecode, disabled pytest plugin autoload and the unchanged
`XoKy4o/guard` before `src`; no DSN, Docker, provider or production endpoint.

- `legacy-approval-policy-red`:29failed/1passed,0.37s pytest,700.311ms capture;
  legacy `requires_approval=false` reached the trusted orchestrator. Hardened
  `red2`:40failed/22passed,0.41s/791.144ms. Focused GREEN:62passed,0.32s/
  652.091ms. These causal runs are untruncated and retain their exact failures.
- `social-role-readmission-red2`:1failed/1passed,0.24s/559.229ms; a viewer
  after durable claim did not raise and could reach the adapter. Focused green
  with `test_social_post_service.py`:164passed,0.75s/1086.359ms.
- Final `execution-admission-final`:467passed in3.45s,4083.48ms capture,
  exit0 with no timeout/truncation/stderr. It is a pure, overlapping scoped
  suite, not a backend aggregate, native DB or provider proof.
- Preserve intermediate failures: first adjacent3failed/292passed exposed two
  preview regressions and the old static-audit contract; `adjacent2` is
  4failed/299passed and stdout-truncated, with three preview fixture failures
  and the remaining Maton literal override. The preview fixture SQL-spacing fix
  and verified boolean propagation are covered by the final suite; neither artifact
  is silently promoted to green.

Static quality is intentionally split. Initial `execution-admission-quality`
is exit1/33F821/148.839ms with truncated stdout. Baseline and current isolated
`publication_lifecycle.py` checks both report the same33F821 dynamic-namespace
names (baseline142.165ms; current64.532ms), exit1 and untruncated. The sole
source replacement only changes read→write at that runtime-injected boundary.
`social_post_service.py:164–185` supplies names using
`_bind_runtime_namespace`; this is a tracked static-analysis limitation, not a
new product regression. `execution-admission-quality-scoped` checks the other
nine files plus `git diff --check`: exit0/102.632ms, untruncated. Do not state a
global Ruff PASS.

`execution-admission-secrets-20260920.json` scans the scoped staged source/raw
delta: exit0, zero findings,272,974bytes,1708.863ms capture. Proof-ledger
validation also passes; neither result is an image/history/production scan or
whole-goal acceptance.

## Callback current-access checks — 20 September, parent 8612efac

`raw/google-oauth-current-access-{red,green,expanded}-20260920.json`
record exact commands and output. Named tmux sessions use private Python3.11.7
arm64, `arch -arm64`, `env -i`, `PYTHONDONTWRITEBYTECODE=1`, disabled pytest
plugin autoload and the unchanged `XoKy4o/guard` before `src` in PYTHONPATH.
No DSN, real provider, Docker, production or denied aggregate/restore runner.

- RED: 18 failed / 18 passed, 0.50s pytest / 779.106ms capture. Actual signed-state
  callbacks exchange the fake code or persist fake credentials after revocation.
- Same original36 GREEN: 36 passed, 0.43s / 774.431ms capture.
- Expanded: 103 passed, 0.77s / 1177.268ms, covering42 callback cases plus Google
  auth recovery, performance details, Sheets auth/preconditions and blueprint
  runtime connections. This includes fake rollback/close and query-lock ordering.
- All three exit as expected without timeout/truncation; no stderr. Independent
  static review PASS. Native SQL/lock contention and live OAuth are not exercised.

The focused36 and expanded103 overlap; do not add them. Workspace source and
existing dependencies are reused, not a clean archive or a whole-project verdict.

CRM raw captures use `crm-request-rbac-*-20260920.json`. The first RED is an
incomplete-fixture500, not proof of an unauthorized insert. Corrected `red2`
has a genuine viewer201 failure plus a test-only required-query assertion;
`red2-causal` retains the actual201-vs403 failure with writer201/viewerGET200
positive controls passing: 1failed/2passed, 498.621ms. The query assertion was
added back for the patched source. Network viewer/member/manager controls and
normalized network SQL predicate are included in final `green5`:13pass0.18s,
496.265ms. All intermediate failures/greens remain exact, not relabelled.

Final root `access-boundaries-final-20260920.json` combines the six Google files
above with `tests/test_crm_integration_requests_api.py`:116passed0.84s,
1208.816ms, exit0, no timeout/truncation/stderr. This is a scoped pure suite,
not the rejected full aggregate. `access-boundaries-quality-20260920.json`
checks four changed source/test files with Ruff F821/F822/F823: exit0,
1251.303ms. Unchanged frontend was not rerun for this backend-only patch.

`access-boundaries-source-manifest` records the four source/test SHA256s,
canonical role helper and unchanged original guard, exit0/32.842ms. Structural
proof-ledger validation passes97.168ms; this is not acceptance sufficiency.
The initial staged secret scan exits1 with three generic-key candidates. Fully
redacted detailed findings locate all three in OAuth RED's synthetic SQL failure
display: pytest truncates a column list into the suffix of a randomly generated
test UUID. Provider/DB are fake and the encrypted value is the explicit
`synthetic-encrypted` literal. These are not real credentials. Preserve the
original exit1 and redacted findings; do not weaken the scanner or rewrite RED.
Independent read-only triage confirms all three as false positives.
Separate `access-boundaries-code-secret-scan` covers all four changed code/test
files: exit0/201.127ms, 24,782bytes, zero findings. This is not a full history,
image or production-secret assessment.

## Today display-code regression — 20 September, parent 625a5d15

Unique `raw/today-copy-*-20260920.json` captures contain exact commands, cwd,
duration and output. No existing runner destinations were replayed. Focused
tests use workspace source, mock data and reused dependencies (not clean install
or whole-worktree acceptance). The nine foreign paths are outside the patch.

- Backend: private Python3.11.7 arm64 at
  `/private/tmp/localos-backend-deps-v2-20260920.xYc0jK/venv/bin/python`,
  `env -i`, `PYTHONDONTWRITEBYTECODE=1`, pytest plugin autoload disabled,
  original `XoKy4o/guard` before `src` in PYTHONPATH. Run via `arch -arm64`
  inside tmux: its x86_64 default failed psycopg2 guard initialization before
  the first two test attempts. Guard was retained, not weakened. RED 8fail/4pass
  in0.06s (396.964ms capture); GREEN 42pass in0.64s (1004.953ms capture):
  `tests/test_today_work_copy.py tests/test_operator_today_api.py tests/test_operator_mobile_today.py`.
- Frontend: Node22, `env -i`, existing `GtHPOV/no-egress-compatible.cjs`
  preload, `vitest run --no-cache --maxWorkers=1`, named tmux jobs.
  RED1fail/30pass (5216.686ms capture); GREEN109pass/8files in24.42s
  (26003.966ms capture). No native DB or outbound requests.
- Initial typecheck exit2 (37607.789ms): unsupported test query `exact`
  option. Retain this failure; it prevented the chained lint command from running.
- Both builds PASS (24729.552ms capture), outputs only in new
  `/private/tmp/localos-today-copy-build-20260920.crNWEm/{app,public}`.
  Existing vendor PURE-annotation warnings remain. Build output was not deployed.

Final captures:

- `today-copy-frontend-full`:667pass/130files,291.66s; exit0,
  292952.671ms capture, no timeout/truncation. Negative-path auth/scope/context
  tests emit expected stderr; no test failure. Application source stayed fixed.
- After full completion, removed only the unsupported test-query option:
  `today-copy-final-page`:31pass4.30s,5496.727ms capture.
- `today-copy-final-types-lint`: app/node TypeScript and full lint exit0,
  48431.044ms, zero errors/one existing `auth_new.ts` any warning.
- `today-copy-build-integrity`: exit0,243.398ms,199app+12public reachable JS.
- `today-copy-source-manifest`: six final code/test SHA256s plus inherited
  Python/Node guards; exit0,37.385ms.
- `today-copy-staged-secret-scan`: redacted Gitleaks staged delta only,
  exit0,1319.864ms,229323bytes, zero findings. This is not a history/image scan.

No final capture has a timeout or output truncation. Final31 and full667 overlap;
do not add them. Full667 precedes the test-only type correction, not an app edit.
This workflow is not the rejected general backend aggregate-v2 or restore runner;
neither denied preparation lane was retried.

## Current proof-ledger validation

`PYTHON_BIN=/usr/local/bin/python3.11 scripts/proof_loop.sh validate production-readiness-20260917`
passes after the current evidence reconciliation: no missing files or JSON-schema
errors. This checks package structure only, not factual sufficiency or readiness.
Durable capture: `raw/evidence-ledger-validation-20260920.json`, exit 0,
81.026ms, no timeout or output truncation; independent factual reconciliation PASS.
`status` also reads the retained historical `verdict.json`; use the current
`evidence.json` checkpoint and raw captures for present acceptance scope.

## Isolated backend aggregate — 20 September, full RED / corrective slices PASS

Frozen application source is `5cc7c0cd`; evidence commit is `e82e0b55`. Private final
runner SHA256 `dc5e3d12989263eda16d48ac5d722401d116ade33bd64666ef7cd0fd883c46b3`,
guard SHA256 `93e4d9d7c99e9653a8e95e2735a369c3ab986e02c2afcb6d206aa63d05a9b590`
and probe SHA256 `30208c1400cc807d5198183d60223a444aa6989615ef13f825b83d61716bd678`
executed against root-owned base container `e550…6e14`, target nonce
`a2f974eb33e8`, loopback 35418 and volume `localos-backend-full-5cc-a2f974eb33e8`.
Its networks are `localos-backend-full-5cc-a2f974eb33e8` (ID `9483e233…`) and
outbound-capable suffix `-host` bridge (ID `ab08e571…`); testcontainers may make
fixture-owned PostgreSQL containers. Foreign Docker resources and native PG15 were
not reused.

| Phase | Result | Evidence |
| --- | --- | --- |
| Native preflight | Fifth attempt PASS | `backend-full-v1-native-preflight5-20260920.json`; earlier attempts retained separately |
| Dependency parity before migration | 147 checks PASS | `backend-full-v1-dependency-parity-migrate-20260920.json` |
| Migration | PASS, 13.325643s | `backend-full-v1-migrate-20260920.json` |
| Collection | PASS, 4,910 tests; 10.85s pytest / 11.769505s capture | `backend-full-v1-collect-20260920.json` |
| Full pytest | Exit 1: 4,886 pass / 9 fail / 1 error / 14 skip / 7 warnings; 822.96s pytest, 824329.093ms capture | `backend-full-v1-full-20260920.json` |

The full process `localos-backend-full-a2f974eb33e8` is terminal; its capture has
`abort_reason=completed`, no timeout/truncation and no residual owned group, but
is not a PASS. Retain initial native failure and bridge/no-port, restart and
inet-mask harness-failure captures. Disk is 6,100,560 KiB (~5.82 GiB): 5 GiB start and 2 GiB
live floors apply; the independent 10 GiB image gate is not met. No application,
provider, production, push, deploy or file-picker action occurred.

Non-passing outcomes are infrastructure/contracts: two E2E cases stop because
the frozen source lacks `frontend/node_modules`; one legacy safety assertion
expects a prior guard-message prefix; seven release-compose contracts cannot find
the Docker Compose plugin. Skips are six ChatGPT live-provider, one Yandex live,
six unavailable TypeScript/npm, and one local native creator opt-in. FFmpeg's
three cases ran and passed; `.webm` was slowest at 17.78s. The corrective checks
below resolve these environment gaps; no application defect was established by
the initial failures.

Corrective evidence, without changing application/test source or replacing the
baseline full capture:

| Corrective phase | Result | Evidence |
| --- | --- | --- |
| Compose + creator | 9 passed, 1.07s pytest / 1411.542ms capture | `backend-full-v1-corrective-compose-creator-20260920.json` |
| Chromium install | PASS, 11.185866s; private headless 1243 tree `b315fb…2fd22` | `backend-full-v1-mixed-frontend-install-20260920.json` |
| Mixed probe/collect/test/post | PASS: 974.13ms / exact 8 / 8 passed 46.52s (47658.88ms capture) / 702.742ms | `backend-full-v1-mixed-frontend-{probe,collect,test,post}-20260920.json` |
| Guard compatibility | 5 passed, 9.56s pytest / 9869.911ms capture; TCP/DNS 96.377ms | `backend-full-v1-{compatibility-guard-probe,corrective-guard-contract}-20260920.json` |
| Native/source postcheck | `fresh_assertions=false` (no `--fresh`): observed 288 tables, `postgres` + owned DB, `readiness_test_owner`, zero sessions; 551 `.pyc` moved recoverably | `backend-full-v1-post-full-native-20260920.json`, `backend-full-post-source-audit-20260920.json` |
| Process postcheck | Normal completion only, not forced-crash proof: no owned mixed processes; foreign Vite PID 22862/4173 preserved; zero stopped | `backend-full-post-process-20260920.json` |

The Compose correction uses explicit `LOCALOS_COMPOSE_BINARY` vendor SHA `372d…`.
Compatibility wrapper SHA256 `05c81f4a5b194a8b24d641567e31e6a724ed4eebc6abf9ffa85c32c95b0b6843`
pins the original guard `93e4…9b590` and adds only the legacy expected denial
message. Shared dependency caches are unchanged; no Bm3ckx/GtHPOV Vite/Chromium
orphan remains. Source audit moved, rather than deleted, 15,676,938 generated
`.pyc` bytes to private retained proof; strict frozen-tree verification passed.
Independent compiled-staging-packaging reconciliation supports union coverage of
4,903 unique non-provider cases with the full baseline; this is not one clean
aggregate green run. Seven intentional live-provider skips remain. Current free
space 6,100,560 KiB (~5.82 GiB), below the separate 10 GiB image gate. Restore
preparation was denied before a file was created and requires separate asynchronous
approval.

Staged documentation + 27 raw captures passed redacted Gitleaks: exit 0,
4727.728ms, 855,780 bytes scanned, no findings, timeout or truncation;
`backend-full-staged-secret-scan-20260920.json`. This is staged-delta coverage,
not a scan of Git history, Docker layers, private dependencies or foreign edits.

V2 is **not runnable**. Only a new guard/probe was statically reviewed in
`/private/tmp/localos-backend-full-v2-20260920.Ik5q93`; no probe/test executed.
Creation of the remaining scripts was policy-denied under the earlier read-only
constraint. Await the new explicit preparation/test permission before writing
or executing them; there is no approved resume command to copy. Existing v1
destinations remain terminal and must not be replayed. See HANDOFF for pins.

## Fresh backend dependency environment — 20 September, source 5cc7c0cd

Private root `/private/tmp/localos-backend-deps-v2-20260920.xYc0jK/`.
Named tmux jobs `localos-deps-v2-20260920` and `localos-deps-install-20260920`
are terminal. All destinations are exclusive; **do not replay** their scripts.
Commands/clean environment keys/output/duration/status are captured in
`.agent/tasks/production-readiness-20260917/raw/backend-deps-v2-*-20260920.json`.

Actual outcomes (milliseconds from capture):

| Phase | Exit | Duration | Result |
| --- | --- | --- | --- |
| bootstrap | 0 | 3264.764 | pip26.2, setuptools84.0.0, wheel0.48.0 |
| wheel-resolution | 1 | 4406.968 | googlemaps4.10.0 lacks a wheel; preparation stop |
| googlemaps-build-dependencies | 0 | 1852.872 | constrained requests2.34.2 satisfies legacy setup_requires |
| build-pyaes | 0 | 461.328 | reviewed pure wheel |
| build-googlemaps | 0 | 460.516 | reviewed pure wheel |
| resolve-reviewed-wheels | 0 | 24570.043 | 133 exact versions including packaging tools |
| install-locked | 0 | 32667.579 | wheel-only, force-reinstall, SHA256 hashes required |
| pip-check-final | 0 | 396.050 | no broken requirements |
| inventory-parity | 0 | 127.945 | 133 equal distributions, direct requirements/all101 constraints pass |
| source-freeze | 0 | 2337.051 | clean git archive5cc7c0cd, no dirty overlays |

Final phases have no timeout, output truncation or residual owned process group.
`supervisor-probe` is a retained harness failure (transient EPERM), not a product
failure. `supervisor-probe2` intentionally times out after an exited leader leaves
a TERM-resistant descendant; exit0 leader, timeout=true, group absent,3098.475ms.
It proves cleanup, not a successful application command.

Final supervisor SHA `a93ca3fbff74eaa6524aa2294ca958116beef3de2b7c32b91ddab050cc2e7607`;
resume SHA `382e65f7039bb50db3721ff186291ba3db4d9a23145942171c17868b695af63d`;
metadata verifier SHA `e0df68ec9ee10c9965ee4a7eca88b8bb4405fddf708795efe267c2b45fccd80b`.
Earlier bootstrap captures correctly record pre-probe helper `e293903b…`.
Explicit arm64 Python3.11.7, env-i children, NETRC/PIP_CONFIG_FILE=/dev/null,
no user site/dotenv/bytecode, disabled keyring/cache and explicit public PyPI.
Dependency fetching permits public index HTTPS; it is not the no-egress test guard.

Reviewed official sdist hashes:

- pyaes1.6.1: `02c1b1405c38d3c370b085fb952dd8bea3fadcee6411ad99f312cc129c536d8f`.
- googlemaps4.10.0: `3055fcbb1aa262a9159b589b5e6af762b10e80634ae11c59495bd44867e47d88`.

Both builds use `--no-index --no-deps --no-build-isolation`; compatible pinned
requests/setuptools are present before googlemaps setup_requires executes.
Raw `backend-deps-v2-reviewed-wheels-20260920.json` ties each source hash to its
built wheel. `backend-deps-v2-artifact-lock-20260920.json` preserves all133 selected
artifact identities/URLs/hashes and the original full report SHA. Full private
`resolved.json` SHA is `fbf32a6f02890c3090c00493c4965c539aa4e2f0f6dccad2246c9898df75f0f5`.
The complete upstream report remains private/untracked: its embedded package
README examples triggered two staged Gitleaks patterns (API hash/JWT). The
redacted initial scans are retained; the commit contains only relevant artifact
metadata, not those third-party README bodies. No scanner allowlist was added.
Final staged-only Gitleaks: raw `backend-deps-v2-staged-secret-scan-final-20260920.json`,
exit0,1318.840ms,225504bytes,zero findings. This is not history/image/venv/foreign
dirty-file coverage; the two earlier redacted scanner failures are retained.
`backend-deps-v2-resolved-hashes-20260920.txt` SHA is
`e0d42ce31cf155d5d65224f199784af8aa859472dade74a49e9b5129903ff90e`.
These capture one macOS arm64 resolution, not a universal repository/image lock
or independent supply-chain certification. No runtime import/native test implied.
Fresh test-tool versions include pytest9.1.1, testcontainers4.15.0, docker7.2.0;
the forthcoming aggregate must establish their compatibility.

Source archive at `/private/tmp/localos-backend-full-20260920.XoKy4o/source.tar`
SHA `7c9fdf2d11ff6a4cce3f2045d1a53aa8631b116531697cba3ad6737c06bc3eb1`.
Only guard preparation is underway there; no aggregate collection/test/DB run.

## Media fetch and write admission — source5cc7c0cd, 20 September

Exact SHA256 pins:

- `src/services/social_posts/media_delivery.py`: `a1c452d32802254522d7a8dcc74c2d2b23b3acd86245b59c10608241b3eeb264`.
- `src/api/media_intelligence_api.py`: `36f2b34bffb910c971ac77f1344ae9d88b8e5b0687ba6823472ebd8c29d60afd`.
- `tests/test_social_media_delivery_ssrf.py`: `6b433eca7abbad585ef1d3a2c57aaa810efef351fa81da2f20b4504ce0798f49`.
- `tests/test_media_intelligence_api.py`: `420e01a8163e6d89080a7a11a3e11c0b05c0bdc8de9dbfd856d5df6c8e1bbf32`.

Retain all raw files; do not relabel worker isolation:

- `social-media-ssrf-red-20260920.json` is an initial fixture/setup failure,
  not the causal verdict. Corrected `social-media-ssrf-red2-20260920.json`
  is3failed/2passed,0.35s,capture874.646ms: generic private URL body accepted,
  missing pinned redirect/size contract, and viewer photo-create200. These use
  mocks/env-i but had no custom no-egress hook or dotenv-disable flag.
- Hardened worker `social-media-ssrf-final2-20260920.json`:35passed/4deselected,
  0.48s,capture843.915ms. Broader worker set242passed0.79s. These earlier runs
  do not establish the stronger root environment boundary; new hardening cases
  are GREEN-only, not additional pre-fix reproductions.
- Root `social-media-root-guard-probe-20260920.json`:exit0,282.700ms. Verified
  exact source/test hashes, env flags and actual DNS/TCP/psycopg2/subprocess
  denials before the selected pure test run.
- Root `social-media-root-guarded-20260920.json`:**279passed**, zero skips,
  0.89s,capture1172.216ms,exit0,empty stderr,no timeout/truncation. Exact command
  contains11 test files, no `-k`, and `-p no:cacheprovider`. Do not sum overlapping
  worker and root sets. Independent final source/guard/raw review PASS.

Private root `/private/tmp/localos-media-root-20260920.EKReQ6/`; named tmux
`readiness-media-root-20260920` is terminal. `run.sh` uses env-i with guard-first
PYTHONPATH, dotenv/plugin autoload/bytecode disabled. GuardSHA256
`aed4499900a678ff6429cbd6f9f451b7374cff569ec4ee0de7c0390850e2bc12` blocks selected
Python network/child effects and psycopg2.connect; this is not a host firewall.
Root posthashes match; own process/session absent. Test-file Ruff, API scoped
E9/F63/F7/F821, media AST syntax and diff check PASS. Media runtime fragment is
already excluded by the canonical standalone F821 gate; no whole-file lint claim.
This selected pure set ran from the worktree with four explicit file pins, not
a clean full-backend archive. It does not certify the other dirty files or a
whole-revision aggregate; the next backend run must freeze committed5cc7c0cd.

Offline Gitleaks delta54bc55e6..5cc7c0cd, named tmux
`readiness-media-scan-20260920`:raw `social-media-secret-delta-20260920.json`,
exit0,1852.025ms,no timeout/truncation;2commits/36,291bytes/zero findings;
`social-media-secret-delta-report-20260920.json` is[]. Not whole-history/image/
log/foreign-dirty proof. No DB/provider/image/deploy claim follows from this package.

## Frozen frontend terminal verification — 20 September

Source4e33587d/frontend tree0af96cd4614e0a1c5b658339b0a73d1a7bec9e46, no dirty
overlays. ArchiveSHA256 `a0e57816d776ddaab0a555be1fedfff893620aa7c757e4a0f362491944a127b0`;
lockSHA256 `a4e1362910fe02f286e950840fd79141fd411533b7743aa79f8c1a450ddece8b`.
Node22.22.0 and 528 exactly matching installed package tuples; no npm install.
All raw files below are in `.agent/tasks/production-readiness-20260917/raw/`.

| Raw filename (`frontend-current-…-20260920.json`) | Terminal result | Capture duration |
| --- | --- | --- |
| preflight | exit0; archive, helper and package pins valid | 8.023454s |
| lint | exit0; zero errors, existing `auth_new.ts:115:82` any warning | 16.052490s |
| typecheck | exit0; app and node configs | 40.082434s |
| unit | exit1 before tests; Vitest4 does not accept `--minWorkers` | 2.016826s |
| unit-resume | exit1 before tests; runner loader lacks canonical `__dirname` | 2.013067s |
| bundle-view | exit0; isolated dependency view prepared | 6.039259s |
| unit-bundle | exit1 before tests; guard blocked Vite localhost DNS lookup | 2.014569s |
| unit-local | exit1; 641 pass / 1 fail; synchronous fetch guard, not app regression | 315.253710s |
| unit-compatible | exit0; **642 pass / 129 files**, Vitest311.97s | 314.940551s |
| build-compatible | exit0; app + public bundle, known Rollup PURE warnings | 26.099014s |
| integrity | exit0; 199 app + 12 public JS, 528 tuples, 257 artifact files | 12.068793s |

All captures are complete, without timeout/truncation. Full unit stderr includes
expected negative-test messages; it is not empty-console/browser proof. Private
helpers under `/private/tmp/localos-frontend-current-20260920.GtHPOV/` use env-i,
envDir:false, no provider env, network-denying Node preload, one worker and
owned-process-group cleanup. Literal loopback DNS is synthesized, not resolved;
fetch rejects asynchronously like native fetch while sockets remain blocked.
This is selected-tool supervision, not a hostile-code OS sandbox.

RunnerSHA256 `ef08aae1bfdfa483a53c60b598492a3763f7a8d6c0a1d1cf7a750a39e784a4db`;
compatible preloadSHA256 `2af789a00689ae774f5f42ba5f9774432f6d4308420ff6b351718e3889107500`.
The final launch was named tmux `frontend-current-compatible-20260920` invoking
`/usr/bin/python3 /private/tmp/localos-frontend-current-20260920.GtHPOV/resume-compatible.py`.
Do not replay it or overwrite captures. Canonical archived integrity script
verified both entries, including `public-dist/public-audit/index.html`.
Manifest `output.sha256` has257 lines,42,128bytes, SHA256
`143fe37cab65be0882b15011bcf7e580ad18d5cbf101efa24ca4884a33677cbc`.
Independent review recomputed unchanged shared caches and empty private
`.vite-temp`; `postcheck.json` records7,417,796KiB free. Root process check finds
own session/processes absent; unrelated Vite4173 is left untouched.

No frontend source/test changes, clean-install, browser/API, backend, current
image or production claim. Subsequent backend worktree changes are excluded.

Backend dependency preflight is recorded separately in
`raw/backend-current-dependency-preflight-20260920.md` (manual reconciliation,
not a test capture). Shared venv requirement gaps remain explicit. Read-only
copy from a stopped historical app container restored the private pure-Python
pypdf6.16.1 overlay with its exact prior 58-file hash; no image/app/DB was started
or changed. This is preparation, not full runtime or requirement-parity proof.

## Frontend resumption preparation — 20 September, NOT RUN

New helper directory `/private/tmp/localos-frontend-current-20260920.GtHPOV/`
targets frozen4e33587d/frontend tree0af96cd4614e0a1c5b658339b0a73d1a7bec9e46.
V1 failed root/independent static review before any archive, unit or build
launch; revised helpers require fresh review. No new app-test failure or PASS
can be inferred. Do not execute unreviewed helpers or overwrite existing raw.
Separate workspace frontend tmux job is active; backend job has ended but is
not our certified result. Heavy checks must remain serialized. This preparation
does not replace the historical test evidence or certify Docker/native DB.

## Content-plan website SSRF — 20 September commit4e33587d

SourceSHA256 `a46fa9edd35c6d6c73fca879997942fdd378605f2280a436ebaba342ea45e0a7`;
testSHA256 `b9e8d1c958fde09b953211d6d61ca94d573c48f8d02fb9088db41f03c66ea6f1`.
Raw under `.agent/tasks/production-readiness-20260917/raw/`:

- `content-site-ssrf-red-20260919.json`:16failed0.32s,capture1895.583ms,exit1.
  Old direct-client and compatibility/pinning contracts fail; not16bugs or a
  real private-network exploit.
- `content-site-ssrf-green-20260919.json`:16passed0.53s,3271.917ms,exit0.
- `content-site-ssrf-green-final-20260919.json`:25passed0.47s,2605.469ms,exit0.
  Predates the final lint-driven request-count assertion; not exact final testSHA.
- `content-site-ssrf-adjacent-final-20260919.json`:149passed0.50s,954.791ms,exit0,
  at the exact hashes above. Includes all25 current focused cases plus contact
  SSRF, content-plan generation, generation-v2 and content-rules tests.

All captures have empty stderr, no timeout/truncation. Scoped source/test
Ruff E9,F63,F7,F821, default new-test Ruff and diff checkPASS; independent final
reviewPASS20September. These pure tests call real validation/pinning and facts
helpers with DNS/urllib3 pools faked; setter/caller provenance is source-traced.
No live HTTP, native DB, current-image or deployed proof. Overlapping test sets
must not be added into unique totals. Historical private runner and guard paths
are now absent; raw evidence remains, so do not rerun just to replace history.

Fresh named tmux `readiness-content-site-scan-20260920` is terminal. Helper
`/private/tmp/localos-readiness-resume-20260920.PTMOqH/scan.sh` uses env-i,
Gitleaks8.30.1 offline/redacted git delta70c0bf60..4e33587d. Raw
`content-site-secret-delta-20260920.json`:exit0,970.979ms,no timeout/truncation;
one commit12,960bytes, zero findings; `content-site-secret-delta-report-20260920.json`
is[]. This is not a whole-history, dirty-tree, image or log scan. Existing outputs
are guarded against overwrite. Capacity check `df -k /`:17044920KiB free; no cleanup.

## Business voice-profile write admission — 19 September, 432f64a0

Private `capture.sh` / `run-pure.sh` under
`/private/tmp/localos-content-voice-readiness.tYjGSQ/`; named tmux
`readiness-content-voice-{red,green,final,adjacent}-20260919`. Python arm64,
env-i, dotenv/plugin autoload/bytecode/pytest cache disabled. Reuses guardSHA
`c49c42a8e83a9a216aad150e2f94226b796a7b86fd55a5df93151f652e873ab5`, blocking Python
sockets and psycopg2 connections. No native database, Docker or providers.

Raw `content-voice-write-<phase>-20260919.json`:

- red:8failed/6passed0.21s, capture1712.237ms, exit1. Three unauthorized200s
  (direct/network viewer and simulated downgrade), five missing role queries.
- green:14passed0.18s, capture574.148ms, exit0; same initial cases.
- green-final:19passed0.22s, capture738.499ms, exit0; five additional hardening
  cases have no separate baselineRED. OriginalRED is retained unchanged.
- adjacent:92passed0.91s, capture1306.485ms, exit0. Files: content_voice_write_access,
  content_voice_api_security, runtime_schema_contracts, content_rules,
  content_generation_v2, legacy_news_generation_readiness (all `tests/test_*.py`).

All captures have empty stderr and no timeout/truncation. Default Ruff with
`--no-cache` on the two changed files, separateF821 and `git diff --check` pass.
Independent source/test/raw reviewPASS. Tests exercise the actual Flask route,
service and canonical helpers with fake SQL; counters prove explicit call
boundaries, not PostgreSQL grants, transactions or concurrent revocation.
SourceSHA256 `c9cff4de814b883501a36e27704f9acd74f69f6556da841088e6dc591a370815`;
test `8c0991bfbdb1f7067f9e73ee038e7102d9f18288b274d5c6ed636debaa876459`.

Offline redacted Gitleaks8.30.1 delta `0a79bf9c..432f64a0`: one commit,
14,230 bytes, zero findings; capture1786.474ms, exit0, findings`[]`, no
timeout/truncation; normal summarystderr. Raw
`content-voice-write-secret-delta-20260919.json` and `-report.json`. This is not
foreign-dirty, whole-history, layer/log or credential-revocation proof.

## Legacy news generation and schema follow-up — 19 September

Source commits `72fd27a9` and `3ee2279a`. Same env-i pure launcher/guard as the
Telegram section below, no native DB, network or external provider. AST-load the
actual decorated handler with fresh Flask; import the real authorization and
schema helpers. SQL rows, transaction counters and provider/rule/event calls are
controlled fakes/spies. No actual PostgreSQL role/grant or persistence claim.

Raw `news-paths-legacy-<phase>-20260919.json`:

- red: 16 failed, 0.51s, capture1023.813ms, exit1. All fail from the original
  unbound local; later source-scope risks were latent behind that crash.
- green: 21 passed, 0.46s, capture2015.284ms, exit0.
- adjacent: 71 passed, 0.90s, capture2533.432ms, exit0.
- schema-red: 2 failed / 21 passed, 0.66s, capture1110.719ms, exit1. At committed
  72fd27a9, denied-DDL fake fails and missing-column fake still generates.
- schema-green: 23 passed, 0.92s, capture1443.465ms, exit0.
- schema-adjacent: 73 passed, 0.95s, capture2653.832ms, exit0.

Adjacent files: test_legacy_news_generation_readiness, test_content_rules,
test_operator_news_generation, test_operator_news_write_access and
test_telegram_operator_write_access (all `.py`). Sets overlap; do not add them
into a unique count. All captures have empty stderr and no timeout/truncation;
RED tracebacks are retained in stdout. Ruff E9,F63,F7 on both files, F821 on
the new test and diff check pass. Full F821 on the dynamic legacy module was
not asserted. Independent source/evidence reviews PASS for both packages.

At 72fd27a9 source SHA256 `a99249b5cdaf77f223078d8e19b2513b4ad7b29936abe1e0b6b4372ac2658182`;
test `50db3be12e4f6ab76ded5851e06deddfd9587ee8a1466dfb938acf8273fe886e`.
At 3ee2279a source `7258313c53b83adf1d1428b13585acfa259e852d63b55565e4ed5ab26b777bd9`;
test `447c40999fc3fb0fa6e3d6295a5eb782e8bce1cb65d9a277ed9eacc15205a987`.

Offline redacted Gitleaks8.30.1 scans only `4ba2be56..3ee2279a`: three commits,
38,298 bytes, zero findings; capture1065.739ms, exit0, report `[]`, no timeout
or truncation. Raw `news-paths-secret-delta-20260919.json` and its `-report.json`;
normal scan summary is in stderr. This does not scan foreign dirty files,
whole history, images or logs, or establish historical credential revocation.

## Telegram command write admission — 19 September, 78102124

Private launcher `/private/tmp/localos-news-paths.5715VM/` verifies and reuses
guard SHA `c49c42a8e83a9a216aad150e2f94226b796a7b86fd55a5df93151f652e873ab5`.
Env-i, no dotenv/plugins/bytecode/cache; Python network and psycopg2.connect
disabled. This is pure testing, not a relaxed native/build resource gate.
Named `readiness-news-paths-telegram-{red,green,adjacent}-20260919` jobs completed.

Raw `news-paths-telegram-<phase>-20260919.json`:

- red: exit 1, 6 failed / 6 passed, 0.33s, capture 1928.147ms. Two viewers
  reach process_chat; four allowed non-owner writers skip canonical role queries.
- green: exit 0, 12 passed, 0.34s, capture 1961.238ms.
- adjacent: exit 0, 101 passed, 20.33s, capture 22220.165ms. Exact files:
  test_telegram_operator_write_access, test_telegram_dashboard_copy,
  test_operator_voice, test_operator_voice_queue, test_content_rules,
  test_operator_news_write_access, test_operator_news_generation (all `.py`).

All captures: empty stderr, no timeout/truncation. Four-file Ruff F821 and diff
check pass. Independent source/focused/adjacent evidence review PASS. Source
SHA256: operator_audio `3f993077726d9b95d716e79b7059effbd6d1075987a8d6866999ab8611d046e8`;
telegram_dashboard `56f1541216f0287ceb66f61e314c0fd5037c7c2c8d816719f32aa2619be3baca`;
new test `a871bf1130c4a810b355578d608252eadb766586172fe048070d922d2c0d0c8a`;
dashboard test `85d08d35e00359016e7273345139e5e39fb7a22d277f2e84f38e8b0fafc0d743`.

## Direct Operator news write admission — 19 September, e3e8fbff

Private `run-pure.sh` and `capture.sh` in
`/private/tmp/localos-news-readiness.jXg1zx/`; named tmux jobs
`readiness-news-admission-{red,red-verified,green,adjacent}-20260919` are terminal.
Python arm64, env-i, dotenv/plugin autoload/bytecode/pytest cache disabled.
Guard blocks Python network operations and psycopg2.connect; no native DB,
Docker, provider or app server involved. This bounded pure check does not lower
the native/build disk guards.

Raw `news-write-admission-operator-<phase>-20260919.json`:

- red: exit 1, 7 failed / 7 passed, 0.65s; capture 1546.159ms. Includes one
  incorrect test expectation (demo mismatch correctly performs zero SQL reads).
- red-verified: exit 1, 6 failed / 8 passed, 0.55s; capture 970.405ms. Two
  viewer cases return 200 instead of 403; four legitimate non-owner writer
  cases expose omitted canonical role queries. Test fixture corrected only.
- green: exit 0, 14 passed, 0.64s; capture 1039.628ms.
- adjacent: exit 0, 20 passed, 0.55s; capture 1255.096ms. Runs the new route
  tests plus existing `test_operator_news_generation.py` (fake DB/provider).

All four captures have empty stderr and no timeout/truncation. Ruff F821 with
`--no-cache` on the two changed files and `git diff --check` pass. Independent
review PASS for route admission only, not real billing/persistence or deployment.
Source SHA256: operator_api `3105b0b30870c3a4f7c2acb49e8650aaab2103aa23ad936652d8c47845171a7f`;
test `4574ceaf61a64927f7b714c3c96bb623b4d59a5e14955dec57aab4b414891d3f`;
guard `c49c42a8e83a9a216aad150e2f94226b796a7b86fd55a5df93151f652e873ab5`.

Offline redacted Gitleaks 8.30.1 delta `73a24aae..e3e8fbff`: one commit,
6948 bytes, zero findings; capture 1177.740ms, exit 0, report `[]`, no
timeout/truncation. Raw `news-write-admission-secret-delta-20260919.json`
retains normal stderr scan summaries. This is not a whole-history/image scan.

## Today static operational copy — 19 September, 7c374f1f

Named tmux `readiness-today-locale-red-20260919` and `...quality...` are terminal.
Node22, env-i, envDir:false Vitest overlay, one worker; all API data mocked.
Raw/today-locale-<phase>-20260919.json:

- red: TodayPage.test only,3fail24pass7.67s/capture10621.106ms,exit1.
- green: TodayPage.test + todayPageCopy.test + DemoLanguageCoverage.test,
 93pass8.82s/capture10561.150ms,exit0/empty stderr.
- types: npm run typecheck,exit0/46430.031ms/empty stderr.
- lint: npm run lint,exit0/15553.081ms,0errors/1existing auth_new.ts:115warning.
- build-preflight: explicit read-only guard recheck,exit1/22.091ms;
 1801168KiB free versus2097152KiB floor; swap11264MiB allocated/9749.62MiB used.
 It confirms planned build directory and build/integrity/full-unit raw outputs
 are absent. No build/full-unit test ran; guard failure is not an application failure.

All captures no timeout/truncation. No browser or deployment proof. The prepared
Vite overlay disables env files; it has not produced an artifact. The previous
620-unit/publication-build result is for67169692, not this new Today source.
Redacted committed-source Gitleaks617a3b90..7c374f1f also passes1commit/20730bytes,
0findings,2519.886ms,exit0/no timeout/truncation; findings[]. Capture
secret-delta-today-20260919.json; not history/image/log/foreign-dirty coverage.

## Content generation role/scope package — 19 September, be1b1a95

Actual native launch was the private `localos-readiness-content-generation-native-20260919.sh`
in named tmux sessions, through capture_command.py with180s timeout. The launcher
uses env-i, disabled dotenv/providers, pinned no-egress guard and the exact owned
native PostgreSQL database OID1935406. Both pre/post checks require its expected
owner/datadir and zero custom schemas/other sessions. No production DB was used.
Captures `raw/content-generation-role-<phase>-20260919.json` are immutable:

| Phase | Result | Captured ms | Interpretation |
| --- | --- | ---: | --- |
| red | 2fail4pass/1.69s | 5765.495 | Actual viewer/network-viewer generation accepted before fix |
| green | 10pass/2.12s | 3653.068 | Initial root-only fix; not scope closure |
| adjacent | exit4/no tests | 936.772 | Incorrect nonexistent test filename, corrected later |
| mobile-red | 2fail8pass/2.08s | 6564.104 | Permission denial incorrectly maps400 instead of403 |
| scope-red | 5fail6pass/2.03s | 3201.280 | Four unauthorized network writes and one context read accepted |
| final | 2fail162pass/8.71s | 12746.148 | Wrong test message and permitted-target expectations; not product regressions |
| final-green | 164pass/7.91s | 9122.281 | Corrected assertions, root+all-target guards and persisted item/audit checks |

All captures are terminal, not timed out/truncated; stderr is empty. Final phase
`adjacent` runs eight files: services_content_viewer_readiness, its guard,
content_plan_generation, employee_content_plan_access, operator_plan_continuation_pg,
content_plan_network_visibility, content_plan_direction, operator_plan_continuation.
The continuation DSN explicitly points to the same owned database; no skips.
Ruff F821 on all four changed files and git diff --check pass. Route functions
use Flask test_request_context with real stored roles/service/SQL, not complete
HTTP middleware or browser proof; context/model inputs are deterministic mocks.
Structural network labels are looked up internally before target admission;
unauthorized options never leave the filtered response. Mid-generation concurrent
membership/topology changes are not fenced or proven by these checks.

Additional terminal captures: `demo-v3-policy-20260919.json` has5pure helper tests,
739.323ms/capture2149.063ms/exit0; no v3 server/browser. Redacted Gitleaks delta
`105954d6..67169692` has1commit/0findings/2878.404ms/exit0, report[]; not whole-history,
image/log/foreign-dirty coverage. No secrets were tested, revoked or rotated.
The subsequent committed backend delta `67169692..be1b1a95` also passes:
raw/secret-delta-content-security-20260919.json,1commit/30339bytes,0findings,
1826.499ms/exit0/no timeout/truncation; findings[]. Same limits apply.

## Content sheet locale package — 19 September, 67169692

Named tmux sessions `readiness-content-sheet-{red,quality,quality-final,
quality-typed,units}-20260919` ran the private correspondingly named launchers.
All are terminal. Captures use bug-reproducer/capture_command.py and Node22;
raw files are `content-sheet-locale-<phase>-20260919.json`:

- red: Vitest ContentPage.dom-mutation filtered to invoker focus/localized sheet,
 5fail/16deselected,5.42s/capture7605.205ms/exit1.
- green: full ContentPage.dom-mutation + DemoLanguageCoverage + sheet.test,
 49pass2fail/9.03s/capture11944.798ms; mock history included prior generate action.
- green-final: same51pass8.63s/capture11366.675ms, before role-query type correction.
- types: `npm run typecheck`, exit2/42053.586ms; three unsupported `exact` options.
- green-typed: exact final same51pass8.83s/capture11069.804ms; default exact string
 role-name matching retained. `types-final`: exit0/46851.108ms.
- lint: `npm run lint`, exit0/17999.153ms,0errors/1existing auth_new.ts warning.
- build: `node node_modules/vite/bin/vite.js build --outDir
 /private/tmp/localos-readiness-content-sheet-dist-20260919` with cookie flagtrue,
 standard config; exit0/20550.229ms, third-party PURE/outDir warnings retained.
- integrity: `bash ../scripts/verify_frontend_dist_integrity.sh` with that outDir,
 199reachable JS pass/287.737ms; local confstr temp-directory warning retained.
- units: `node node_modules/vitest/vitest.mjs run --config
 /private/tmp/localos-readiness-locale-vitest-20260919.mjs --reporter=dot`,
 env-i/envDirfalse/maxWorkers1;620pass/129files354.85s/capture356870.512ms/exit0.

All captures have no timeout/truncation; full units retain expected negative
fixture/jsdom stderr. The new build is NOT the older envDir:false demo artifact.
Index SHA2569c98c81d3e34a03fd8b99db9db3dba04afde42e2619f3cff16448cb5de0533aa.
No native browser, Docker build or production operation was run for this package.

## Preview lifecycle and v2 walkthrough — 19 September

Completed one-shot captures in the existing task raw directory; do not replay
their fixed result paths. Node22 `/usr/local/opt/node@22/bin/node` and the
bug-reproducer capture_command.py were used; all long operations ran in tmux.

- `node /private/tmp/localos-readiness-preview-lifecycle-20260919.cjs legacy`
  -> preview-signal-red:1fail2pass/exit1/4572.479ms.
- Same script with `owned` -> preview-signal-green:3pass/exit0/3971.846ms.
  Test SHA2569f6a2db7ce373abba06d8767bbf85b75fd94388ec85e26af1b93b30d22e4e9fc.
- `node --test /private/tmp/localos-readiness-demo-preview-v2-test-20260919.cjs`
  -> demo-v2-policy:5pass/exit0/1262.987ms.
- `node /private/tmp/localos-readiness-demo-v2-signal-smoke-20260919.cjs`
  -> demo-v2-signal:exit0/2347.837ms; actual helper lifecycle/223file identity/
  ports pass; exact login rejected403 and zero forwarded mutations.
- `node /private/tmp/localos-readiness-demo-preview-v2-20260919.cjs --execute`
  -> demo-v2-rehearsal:exit1/320867.914ms, lifecycleValidtrue but financefalse.
  SIGTERM cleanly finalizes; login1,preview0,import0,48reads. No complete demo.

All five captures above have no timeout/truncation/stderr. Helper SHA256
757da7d48d7922245a1f9fb7f6df1e6bf16f3b0f3b47a93242dc1c5e35608335;
policy test SHAd3e6b85043bb7f9d581de4f930b5c28816751dbe592e3ce7526ebca85ed7b9fa.
Rehearsal result `/private/tmp/localos-readiness-demo-preview-v2-rehearsal-20260919-result.json`
SHAa46ea68d95991d70190544d086fce356c0a78f1229c191fbb8b426d65ea5cf74.
Fixture pre/post read-only captures398.875/351.961ms pass; root SQL preserves
finance2/batches4/artifact1 and all prior digests. Native picker fallback is
tool-denied; no bypass/finance action. Detailed UI/denial distinctions and exact
next read routes: raw/demo-v2-rehearsal-20260919.md.

## Retained demo artifact and current UI — 19 September

Completed exact helper commands, NOT full seed replay:
`python3 /private/tmp/localos-readiness-demo-artifact-20260919.py --expected-database-oid 16384`
and the same with `--apply`, captured with bug-reproducer's capture_command.
Final helper SHA2569e7c250bf40ce8def73c49d3ae858875a2b570f4f8b00dfb380c0ee4c1a78fcb.
Raw demo-artifact-{inspect,apply,repeat,final-inspect}-20260919.json:
466.474/663.349/359.476/610.647ms, all exit0/untruncated/no timeout/stderr.
Repeat preserves existing row, not a full seed re-execution. Exact artifact
whole-row digestdff7ad2af86369ced7dce0b35ff30051 stayed unchanged.

Both one-shot Node22 previews ran in named tmux sessions and are now terminal:

- demo-current-ui-server-20260919.json: exit1/1812384.731ms, deadline;
  login1,preview0,import0,32allowedreads,7deniedGETs and1deniedproduct-eventsPOST.
  Helper cleanup/stage/manifest passed, but finance/demo did not run.
- partnership-ui-server-20260919.json: exit143/107152.023ms, empty private
  result. Manual CUA drawer text observed; no helper-finalization PASS.

Neither outer capture timed out or truncated output; stderr empty. Private
helper/result pins, exact stage identity, UI provenance, SQL digests and
resource postchecks are in raw/demo-rehearsal-current-ui-20260919.md. Do not
replay those completed paths or treat old tmux handles as live. Root separately
confirmed no owned processes/listeners and223unchanged frontend files.
The managed file chooser took24190.3679s despite timeouts; this is not benchmark
or rehearsal time. Existing2finance entries/4batches were preserved unchanged.

## Frozen6eec backend aggregate and demo seed — 19 September

One-shot private capture `/private/tmp/localos-readiness-backend-6eec7e5e-capture-20260919.sh`
uses the approved PDF tree pin
`a2baea11803095e5488c98533a8001edbe2c5e167c4367644e5ebe16ca7fc67e`.
Do not replay it: retrytmuxreadiness-backend-6eec-retry-20260919 is completed.
It runs `pytest -q -rs --durations=25` in the immutable6eec archive with the
owned native DSN, callback aliases/guard and cached testcontainer images.
NativeDB is retained without launcher migration/reset; suite-owned ephemeral
PostgreSQL instances still run their ordinary migrations. Pinned launcher
SHA59378af8501f0911c967044dfc3dc5d7d8ff9f3e0b62f490724091b702430c27,
capturec3b7cc6aab8dfe27cb8ac49195d058bef11239b53cf422279a326f89f13467bb,
Docker-to-real-Compose shim43128cef1eedae674c8ed24158f3e0d3657447c3b04332c7c31ff01a2f248ba8.
The first launch's65-character hash-pattern failure happened before capture;
its wrapper is preserved. Corrected validator accepts64 and rejects63/65/nonhex.
Raw/full-backend-6eec7e5e-20260919.json:4751passed/7live-provider skips/6warnings
652.30s, capture659.230650s/exit0/no timeout/truncation, controllervalidtrue.
Warnings:5PyMuPDF/SWIG plus1Alembic path_separator; shutdown SWIG stderr retained.
Root postcheck confirms unchanged nativeDB1935406/owner/datadir,0custom schemas
and other sessions, no testcontainers/known PID group leftovers; no DB drop.
Independent raw/result scope reviewPASS; root owns DB/Docker postcheck evidence.
See raw/backend-6eec7e5e-preflight-20260919.md for failed-launch/provenance detail.

Completed demo proof uses env-i/guard-first/no dotenv, no actual DB connection:
private `localos-readiness-demo-seed-proof-20260919.sh` archives only the old
seed and copies the same new tests for causalRED, then tests current source.
Raw demo-seed-red:2failed0.20s/capture0.546771s; green:2passed0.05s/0.239399s.
`localos-readiness-demo-seed-adjacent-20260919.sh` runs new seed contract plus
lead_journey service/API/content+automation migration contracts:44passed0.70s/
1.094591s; overlapping counts, empty stderr/no truncation/timeout. RuffF821 and
`git diff --check` pass. These are SQL-recording contracts, not real DB or UI.
Committed1e955718 after independent review; excluded from the6eec aggregate.

Strict offline Gitleaks delta6eec..1e955718 passes1commit/0findings in3.252838s,
raw/secret-delta-6eec-to-1e955718-20260919.json and private report[] retained.
Git `confstr`/stderr warning retained; no historic-key revocation claim.

## Password-reset console disclosure — 19 September, source39aeeff9

Private `localos-readiness-password-logging-capture-20260919.sh` records source
hashes and enforces2GiBfree before each command; env-i/Node22/envDirfalse.
RED: newSetPassword.logging.test +AuthRecovery.brand-buttons,1fail2pass4.71s,
capture7.595154s. Product fix removes only2logs. FirstGREEN includes4adjacent
files:27pass1newtest timeout from fake timers/userEvent, capture17.769319s.
Preserve both failures. FireEvent/act with fake-clock cleanup keeps identical
resetPOST/success/no-console-credentials assertions; final28pass11.15s,
capture12.628319s. Expected authnegative-fixture stderr is retained.

Namedtmuxreadiness-password-logging-quality-retry-20260919 subsequently passes
typecheck39.757401s, lint15.610447s(0errors1existingany), cookiebuild15.46s/
capture17.366236s,199reachableJS integrity0.346085s. The full unit run is now
terminal616passed/128files309.65s, capture310.950615s/exit0. All captures are untruncated
and not timed out. Source39aeeff9 committed after independent scopedPASS.
Separate asset-proof0.501916s compares old993cookie SetPassword chunk with
new39chunk: both log literals disappear; resetendpoint remains. This uses local
synthetic/build evidence, not a production token/request/log test.

Strict offline scan: one-shotlocalos-readiness-secret-delta-72-to-39aeeff9-
20260919.sh uses exact72f588081d93774dad455627adf818d6e25970fe..39aeeff95e49991f7b13d0b8b661c92b02677766,
`--ignore-gitleaks-allow --redact=100`, report[]. Rawcapture2.249284s/exit0,
4commits/0findings/no timeout/truncation. Later docs and historical credentials
remain outside that delta; no rotation or provider validity probe occurred.

## Review-copy frontend checks — 19 September

Completed one-shot tmux launchers are in/private/tmp; do not replay them over
existing output. `localos-readiness-locale-quality-final-20260919.sh` produced
raw/review-locale-units-final-20260919.json:615passed/127files307.53s,
capture309.618819s/exit0/no timeout or truncation. Its next TypeScript capture
failsTS1117 in4locale files, exit2/37.740933s. The previous wrong-jq launch and
failed new test selectors remain separate preserved failures.

After removing only duplicate identical `copy` values,
`localos-readiness-locale-quality-dedup-20260919.sh` ran the same typecheck
(40.163984s), focused4tests(3.79s/capture5.355626s), lint(14.842858s,
0errors/1existing auth-boundary-any warning), app/public builds
(15.37s/7.26s; captures16.788649s/8.344871s), and canonical dist integrity
(199/12reachableJS;0.433251s/0.143498s). All terminalexit0/untruncated.
The full615run precedes duplicate removal; no second full run is claimed.
App build retains vendorPURE-comment warnings/private-output notice.

Default artifacts are/private/tmp/localos-readiness-locale-dist-20260919 and
public-dist-20260919. Cookie-mode staging requires the explicit documented
`VITE_BROWSER_COOKIE_AUTH_ENABLED=true` fromdocker-compose.staging.yml; default
env-clean build does not enable it. A distinct
`localos-readiness-locale-cookie-build-20260919.sh` runs that exact flag in the
captured command with envDirfalse, no dotenv and no application-source change.
Cookie build15.73s/capture17.371317s;199asset integrity0.284999s, bothPASS.
Cookie artifact/private/tmp/localos-readiness-locale-cookie-dist-20260919;
indexSHAa85e564ba551dfa3e441ead6be5f951bf23b8bfb0864bad01682987bb9d8cba0.

Browser first preflight raw/review-locale-browser-20260919.json exits1 in
1.382478s before login/browser on wrongly assumed disabledcompiledflag.
Pinning actual historical true/true/exactcohort allows the retry to navigate,
but raw/review-locale-browser-retry-20260919.json fails the reviewheading wait
in13.470579s; browser/server cleanup passes, browser mutations/directstage/
external counts0. It is not accepted browser proof. Preserve both results;
its diagnostic follow-up below retains the same timeout and selectors.

Completed diagnostic capture/review-locale-browser-diagnostic-20260919.json:
exit1/12.932163s, sameartifact now records actual/login with no browserAPI calls
or console/page errors. Stage and artifact failurepostchecksPASS. The separate
cookie-enabled artifact changes only documented build configuration. Final
one-shot localos-readiness-review-locale-browser-cookie-capture-20260919.sh
pins harnessff118be830f032c5e484f6a4e31f6d24bba9c70188db9ff5f609616cf9de0519
and cookieindexa85e564b above; env-i, literal localDOCKER_HOST, no HOME override.
Raw/review-locale-browser-cookie-20260919.json is exit0/5.950617s/untruncated/
notimedout; privatecookie-resultvalidtrue with3scenarios, exactclipboardall3,
no console/page errors or browsermutation/directstage/external requests.
Explicit synthetic loginPOST occurs once per context,3total. Pinned historical
stage identity/flags and artifact manifests match after the scenarios.
Browser and previewserver closes fulfilled; rootlsof18017 and matchingharness/
Playwrightprofile process check find none. Three screenshots viewed byroot.
No current backend/image, all-locale, whole-suite or production claim.

## Callback fairness — committed7bb9f996, 19 September

Completed named tmux RED and GREEN used
`/bin/sh /private/tmp/localos-readiness-fairness-capture-20260919.sh` with
`red tests/test_action_orchestrator_callback_recovery_pg.py -k worker_callback_alert_scan`
and `green tests/test_action_orchestrator_callback_recovery_pg.py tests/test_action_orchestrator_callback_ssrf.py tests/test_outbound_network.py tests/test_openclaw_smoke_recovery_safety.py`.
The helper pins the native guard, literal DSN/cluster/OID1935406/owner,
requires2GiB free, records source hashes and runs compile/RuffF821 before
exec'ing pytest. It uses env-i with no dotenv/provider credentials.

Actual raw/callback-fairness-red-20260919.json:exit1,1fail/1pass0.63s,
capture1430.475ms, missing only fair-callback-tenant-100 in the union.
Actual raw/callback-fairness-green-20260919.json:exit0,29pass12.04s,
capture12858.612ms, no timeout/truncation/stderr. Root native schema count0;
independent current hash/source/evidence reviewPASS. Do not replay completed
one-shot labels. These targeted checks do not recertify the entire backend.

## Callback final package — committed4f333aa7, 19 September

Offline Gitleaks delta `5b9b9247..4f333aa7` also completed in named tmux:
`/bin/sh /private/tmp/localos-readiness-secret-delta-5b9-to-4f333aa7-20260919.sh`.
Actual raw/secret-delta-5b9-to-4f333aa7-20260919.json:exit0/2151.259ms,
2commits/62274bytes/0findings, no timeout/truncation, full redaction and inline
allow suppression disabled. Private JSON report is `[]`. This closes only
that committed-source delta, not historical revocation or image/log scanning.

Completed tmux `readiness-callback-adjacent-20260919`:
`/bin/sh /private/tmp/localos-readiness-callback-adjacent-capture-20260919.sh`.
It pins reviewed launcherdef442432…, archives641 plus four exact WIP files,
preserves guard loading even when migrations reset PYTHONPATH, and uses cached
local pgvector/Ryuk images without a build. Exact literal native DB preflight
and source hashes are in `raw/callback-adjacent-20260919.json`.
Actual73passed23.75s/capture28171.585ms, exit0/no timeout/truncation/stderr;
60 capability API +3schema +10native cases. No-cache RuffF821 precedes pytest.
Independent postcheck finds no callback/schema-test nonce schemas or temporary
roles. One exited historical Testcontainers resource predates the run; preserved.

Shell RED captures (all commands use fake executables, no network):

- `raw/callback-smoke-recovery-red-20260919.json`:2failed/1passed6.99s,
  capture7361.078ms, exact unexpected management replay. Original fixed scratch
  path is remapped only inside the temporary test copy, not a shared /tmp file.
- Initial fix `raw/callback-smoke-recovery-green-20260919.json`:5passed8.32s,
  capture8716.023ms. Later review narrows wording/test names to recovery-only.
- `raw/callback-snapshot-red-20260919.json`:1failed/5passed9.67s,
  capture10124.981ms; exactJSONDecodeError from heredoc consuming JSON stdin.

Final tmux `readiness-callback-final-20260919`:
`/bin/sh /private/tmp/localos-readiness-callback-final-capture-20260919.sh`.
Guarded literal DB/OID/owner/data-directory check, six source hashes, compile,
RuffF821 and bash-n precede the four selected pytest modules. Actual
`raw/callback-final-20260919.json`:25passed11.41s/capture12293.402ms,
exit0/no timeout/truncation/empty stderr; independent final reviewPASS.
Root final native postcheck0callback schemas/0schema-test schemas/0test roles.
The25and73sets overlap; this is not98unique cases or current whole-project proof.
All outputs are completed evidence; never replay these one-shot output paths.

## Callback interrupted-claim RED and managed browser — 19 September

Completed tmuxreadiness-callback-red-20260919:
`/bin/sh /private/tmp/localos-readiness-callback-red-capture-20260919.sh`.
Env-i/guarded ARM64 Python preflight verifies the literal localDSN, native
data_directory, DBname/OID1935406/owner and canonical reference tables, then:

```sh
venv/bin/python -m pytest -q tests/test_action_orchestrator_callback_recovery_pg.py
```

Actual raw/callback-recovery-red-20260919.json:exit1,1103.264ms,no timeout or
truncation;1failed1passed0.48s. Failure is exact stale-sending non-recovery,
not setup. Normal503→retry→sent passes. Root read-only catalogpostcheck0schemas.
Do not reuse the RED output path for GREEN or claim pending code is fixed.

Completed GREEN: tmux `readiness-callback-green-20260919` ran
`/bin/sh /private/tmp/localos-readiness-callback-green-capture-20260919.sh`.
Same literal DB identity preflight and pinned guard; `os.execv` hands the
single process to pytest with no nested timeout child. Actual command:

```sh
venv/bin/python -m pytest -q -p no:cacheprovider tests/test_action_orchestrator_callback_recovery_pg.py tests/test_action_orchestrator_callback_ssrf.py tests/test_outbound_network.py
```

`raw/callback-recovery-green-20260919.json`:19passed1.82s, capture2479.817ms,
exit0/no timeout/truncation/empty stderr. Ten native cases plus nine adjacent
SSRF/redirect/transport tests. Source hashes captured and independently matched;
root read-only catalogpostcheck0 callback_recovery schemas. Bounded local
FIX_PROVEN, not whole release or deployed behavior. Do not replay output paths.

Managed-browser actions, fixture/source limitations and finance two-batch
result are in raw/managed-browser-demo-20260919.md. They are direct UI
observations, not fabricated command JSON or the automated collector run.

Minimal process proof raw/supervisor-v8-nested-reparent-repro2.json:
exit0/175.259ms/no timeout/truncation; pinned middle exits after spawning an
unobserved same-group child; nextrefresh reproduces the error. Owned child
identity-checked cleanup succeeded. Original failed first fixture stays retained.

Completed native6 launch used a separate one-shot direct supervisor:
`/bin/sh /private/tmp/localos-readiness-native-six-direct-v8-launch-20260919.sh`,
tmuxreadiness-native-six-direct-20260919. WrapperSHA6d5cf8bd… independently
reviewed. Actual raw/native-six-direct-v8-641ec5e3.json:validtrue/exit0,
48938.396ms capture,6passed22.0s (two owner review/finance flows × three
viewports). Fresh synthetic DB dropped; independent DB and six-PGID absence
checks PASS. Initial readiness curl refusal and optional popular-queries
warning remain, not blanket empty-stderr evidence. Keep raw private: fixture
JSON contains synthetic credential/token fields missed by its redaction flag.
Never replay completed or failed native6 captures. This archives641 and does
not include subsequent callback WIP or constitute a117-case/image run.

## Native six-case attempt — FAILED before tests, 19 September

Named tmux `readiness-native-six-20260919` completed the one-shot
`/private/tmp/localos-readiness-native-six-capture-20260919.sh`, pinning wrapper
2ca728048707b30bd2d904ac4bffc70d4ab6985f486bce746b75e298d4b45d0a.
Actual raw/native-runtime-errors-5b9b9247-command.json:exit1/8500.341ms,
no timeout/truncation. Traceback is v8.refresh:
`group_membership_or_identity_invalid`. Inner capture raw/native-runtime-errors-5b9b9247.json
exit1/8264.378ms, missing inner summary and empty stdout/stderr. No browser
count or successful collector evidence exists. Exact task root has only
prepared components/admin-home; no archive was created. Fresh tmux/pgrep checks
find no matching live session/process. Keep failure and root, do not overwrite
or rerun this wrapper. Diagnosis is pending; no product failure is established.

## Completed paired measurement and compiled-claim regression — 19 September

`readiness-journey-v8-20260919` completed
`/private/tmp/localos-readiness-journey-measure-v8-root-capture-20260919.sh`.
The wrapper pins launcher SHA
`cccbf00ccbe95c6701f103049fc158d7f73afef1363817012bfe258bdb4dbaef`,
uses env-i/ARM64 Python/guard-first imports and captures the actual
`/private/tmp/localos-readiness-journey-measure-v8-2d875357-272794a4.py --execute`
with1900s outer/1800s inner bounds. The exact driver invocation is preserved
in raw `journey-measure-v8-2d875357-272794a4.json`: distinct pinned refs,
5warmups/50serial/0load. Command capture exit0/552856.456ms, no timeout or
truncation. Independent counts/quantiles/provenance/110DB absence/process
cleanup review PASS for this bounded comparison. Do not replay completed paths.

`readiness-compiled-membership-20260919` then ran
`/private/tmp/localos-readiness-compiled-membership-capture-20260919.sh`, which
verifies the literal-loopback reference DB identity and data_directory before:

```sh
venv/bin/python -m pytest -q tests/test_compiled_run_claim_pg.py tests/test_compiled_script_artifact.py tests/test_compiled_runtime_errors.py
```

Actual raw `compiled-membership-20260919.json`:18passed4.78s,
childexit0/5387.119ms/no timeout/truncation. Root postcheck on the same local
cluster found0remaining `test_compiled_claim_%` schemas. Only nonce schemas
inside the task-owned test DB were used; no production/provider operations.

## Strict committed-source delta — 19 September Moscow

Completed tmux `readiness-secret-delta-20260919`, wrapper
`/private/tmp/localos-readiness-secret-delta-272-to-5b9-20260919.sh`.
Gitleaks8.30.1 with `git --log-opts=272794a439a76204536480f158e79276ccd7b318..5b9b9247b54f5768cd0dc4c8870998e0e964212f
--ignore-gitleaks-allow --redact=100 --no-banner --no-color --report-format=json`
scanned7commits/149,093bytes. Raw/secret-delta-272-to-5b9-20260919.json:
childexit0/1546.069ms/no timeout/truncation, private report
`/private/tmp/localos-readiness-secret-delta-272-to-5b9-20260919.json` is `[]`.
No external provider calls or credential testing; historical/image/log gates
are separate. Do not replay this completed evidence path.

## Executed v8 process proof — 19 September Moscow

Completed named tmux session `readiness-supervisor-v8-20260919`, executing the
exact env-i command under the historical prepared section below through
`/private/tmp/localos-readiness-supervisor-v8-root-capture-20260919.sh`.
Both helper hashes matched HANDOFF before launch. Actual capture
`raw/supervisor-v8-process-only.json`: childexit0, duration3590.517ms,
timed_out=false, no truncation, empty stderr; parsed stdout valid=true and all
ten expected proof rows. Injected denial/identity changes correctly return
invalid cleanup with zero unintended signals; these are expected negative cases.
Independent scoped review PASS and targeted ps verified no proof-owned
processes remain. No Docker/DB/browser/provider operation in this proof.
The output path is now completed evidence and must not be reused.

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
