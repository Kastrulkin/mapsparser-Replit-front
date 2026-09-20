# Production-readiness change log

## UX-LOCALE-07 — additive Today system-display codes, 20 September

Parent625a5d15: one backend adapter emits an Open label code and allowlisted
sheet-write message codes while retaining Russian legacy text. Today maps those
codes using typed ten-language copy, without changing user titles, state,
approvals, requests or deep links. Tests preserve unknown-code fallback and
queued/unknown-provider semantics. Pure backend42 and frontend adjacent109 pass;
independent static review PASS. Both builds/integrity and667full frontend units
pass. A test-only query option type fix afterward passes31TodayPage tests and
app/node TypeScript/lint; original type failure is retained. No DB/provider/production
mutation, deployment, new dependency or wider builder refactor.

## SEC-SSRF-03 / SEC-RBAC-11 — media security, 5cc7c0cd

Only two production files and two tests: replace generic unbounded asset GET
with canonical per-hop public pinning, cap five requests/10,000,000 accepted
bytes per remote asset, and require canonical write access for all six media mutations. Existing
reads, legitimate writers, local-storage priority and publication approvals stay.

Causal mocked RED3fail/2pass; hardened worker35pass and adjacent242pass are
overlapping and did not carry the root no-egress/dotenv guard. Exact root final
guarded set279pass0.89s, zero skips, with actual guard probes and independent
source/evidence review PASS. Two-commit secret delta finds zero leaks. No real
network, native DB, current image or production proof; proxy-only source
compatibility, decimal cap and non-global timeout limits are explicit in D-045.

## Frozen frontend evidence and Telegram rollout documentation — 20 September

No frontend source change: recreated isolated verification, corrected only
private runner compatibility, and retained all initial failures. Exact frozen
4e33587d passes642 units/129 files, TypeScript/lint, app/public builds and
199+12 reachable-JS integrity. Artifact has257 files; installed528 dependency
tuples and shared caches remain unchanged. Independent evidence review PASS.
Not clean-install, browser/API, backend, image or production proof.

Telegram runbook now spells out the already-required coordinated approved
code/provider cutover, secret-proof limitation and per-bot receipt evidence.
Setup documentation separates branded webhook ingress from owner-bot polling
and aligns owner runtime with canonical Compose. No provider or server command
was executed; the release gate remains open.

## SEC-SSRF-02 — pinned content-plan website context, 4e33587d

Replace automatic-redirect `requests.get` with the existing canonical public
pinned transport. Check each redirect, cap five requests/one-million-byte HTML,
preserve bare host/port and HTTP-over-meta charset behavior, and retain the
existing empty-context fallback on failure. No setter, schema or provider change.

RED16 fails on the original direct-client/contract gaps, not16independent
vulnerabilities. Hardened25 focused cases are included in exact149 adjacent
passes0.50s. Independent final reviewPASS; source/test scoped Ruff and diffPASS.
Offline one-commit redacted secret scan finds zero leaks. DNS/pools are faked;
no real-network, native DB, image or production validation is implied.

## SEC-RBAC-10 — business voice-profile write admission, 432f64a0

The shared content-voice helper now accepts keyword-only `require_write=False`.
Only the existing `update_content_voice` write gate enables it, selecting the
canonical write verifier before advisory lock/profile merge/UPSERT/explicit
commit. Authorized initial reads remain allowed; default GET, user-owned
examples and rules/history read behavior is unchanged. No API/schema/provider
change. Legitimate nullable-owner managers and mixed direct/network roles pass.

Actual route/service RED8fail/6pass becomes14pass after the minimal fix;
hardening adds five passing cases for19final; six-file adjacency92passes.
Protected existing rules survive attempted overwrite, demo boundaries remain,
and a simulated role downgrade is denied at the write connection. Ruff/diff and
independent source/test/evidence reviewPASS. No live race, native persistence,
current-image, production or full-platform authorization certificate is implied.

## OPS-NEWS-SCHEMA-01 — read-only news schema admission, 3ee2279a

Remove UserNews CREATE/ALTER from `news_generate` and its optional tenantless
INSERT. The existing read-only schema helper checks ten required columns after
write authorization and before private context/provider work. Canonical Alembic
migrations own all ten columns; no migration was changed or executed.

Causal RED: DML-only fake returns500 instead of200, and missing business_id
incorrectly reaches provider/200 (2 failed / 21 passed). GREEN23 and adjacent73
pass, with independent review and scoped Ruff/diff checks. Native PostgreSQL
catalog/grants are not tested; other legacy endpoints' DDL is not removed here.

## BUG-NEWS-01 — legacy generation and tenant input repair, 72fd27a9

Reproduce `generated_text` read before assignment (16 failed). Resolve one
business and require canonical write access before private context/provider
work. Scope selected/fallback service and finance queries by business; preserve
valid owner-created records for managers and personal global examples (D-040).
Enforce content rules after deterministic text fallbacks, before draft/events;
preserve the same business ID throughout. Roll back provider/rule failures,
remove raw model-result debug output and redact provider errors/exceptions.
Prompt-template debug output elsewhere is not covered by this privacy proof.

GREEN21 / adjacent71 pure tests pass; independent review required nullable-owner
manager compatibility and provider-exception privacy before acceptance. These
are strict fake-SQL/spy tests of the real decorated handler, not native commit,
billing or production proof. Downstream authorization risks were latent behind
the crash; the baseline RED does not demonstrate an independent tenant exploit.
The subsequent separate schema package removes the preserved compatibility DDL.

## SEC-RBAC-09 — Telegram command write admission, 78102124

`authorize_actor` adds keyword-only `require_write=False`, preserving existing
read/audio behavior and positional subscription arguments. The generic Telegram
Operator chat alone passes `True`, using the canonical write verifier after
loading user/account state and before subscription lookup or `process_chat`.
This is a writer-only boundary for the whole mixed-capability chat, not just
news intents; see D-039. No bot sends, provider configuration or schema change.

Twelve new strict fake-SQL regression cases: owner/direct/network/mixed-role/
network-owner/superadmin positives, viewer and outsider denials, inactive and
missing accounts, and default read-helper preservation. Existing dashboard
mock gains keyword compatibility. Causal RED: 6 failures / 6 passes in 0.33s;
GREEN: 12 passes in 0.34s; seven-file adjacency: 101 passes in 20.33s.
Captures 1928.147 / 1961.238 / 22220.165ms; no stderr, timeout or truncation.
Ruff F821, diff checks and independent review PASS. Bounded local FIX_PROVEN,
not native DB, real credit effects, live Telegram, image or production proof.

## SEC-RBAC-08 — direct Operator news write admission, e3e8fbff

One production-source line uses the existing write verifier instead of the read
verifier before news generation. No role model, schema, provider, service logic
or external publication behavior changed. New route tests register the real
Flask blueprint and retain both actual canonical helpers. Strict fake SQL
checks target/user parameters; downstream generation/audit are counted spies.

Verified RED: 6 failures / 8 passes in 0.55s (two viewer 200s, four omitted role
queries); GREEN: 14 passes in 0.64s; adjacent: 20 passes in 0.55s. The initial
7/7 run also contained a demo-query-count fixture error and is preserved.
Ruff F821/diff checks and independent review PASS. Env-i/private guard blocks
Python network and PostgreSQL. This is bounded local FIX_PROVEN, not native
DB/credits, other-channel, current-image, full backend or production proof.
Telegram admission and the legacy handler's crash/latent authorization remain
separate open findings. No push/deploy or modification of seven foreign paths.

## UX-LOCALE-07 — static Today copy subset, 7c374f1f

Reproduced three static Spanish failures (decision section, preference settings,
empty preferred content). Four-file copy-only change moves these existing
RU/English branches into the same i18n module's typed ten-language operational
dictionary. Existing RU/EN text, priority ordering, scope, APIs and routes are
unchanged; dynamic API action text is intentionally not rewritten.

RED3fail24pass7.67s; GREEN93focused/adjacent pass8.82s, full TypeScript and lint
0errors/1existing warning pass; independent source/evidence reviewPASS. Spanish
checks preserve exact scoped GET/noPOST, API Russian text and content navigation.
Build/integrity/full-unit follow-up is not run: explicit disk preflight fails at
1801168KiB free, with11GiB system swap allocated. No current artifact, complete
Today translation, production or release-ready claim. Seven foreign files kept.

## SEC-RBAC-07 — content root/target admission, be1b1a95

Four files only: content_plan_service resolves canonical scope from the root's
stored network, checks root admission first and every effective target with the
existing read/write verifier, filters returned scope options, and persists the
same scope identity. Single-business cannot persist a supplied foreign target;
blank network-location cannot select an arbitrary sibling. Mobile generation
maps PermissionError to403 and retains ValueError400. No new roles/schema/API enum.

Causal native REDs: viewer/network-viewer2fail4pass; mobile400vs4032fail8pass;
network generation/context5fail6pass. The initial root-only10green was rejected
by independent review; root+target and reverse-role cases were added. An adjacent
command selected a nonexistent file (exit4/no tests); the next full run had
162pass2test-expectation failures, preserved unchanged. Final164pass7.91s,
capture9122.281ms, no skips/stderr/timeout/truncation; exact nativeDB identity and
zero schemas/sessions before/after. Tests check whole-row no-effect snapshots,
stored superadmin, allowed viewer reads, filtered options, two network-item target
IDs, root audit identity, and actual continuation callers. Ruff F821/diff check
pass; independent final review verified source/test hashes and raw proof: PASS.

Limit: synthetic native roles and actual service/route-function calls, not full
HTTP middleware/current image/production. Deterministic context/LLM inputs are
mocked. Structural labels are read internally before target admission but never
returned unauthorized. Concurrent membership/topology revocation during generation
is not transaction-fenced. No provider calls, production writes, push or deploy.

## UX-LOCALE-06 — scoped publication-sheet labels, 67169692

Five frontend files only: SheetContent accepts optional `closeLabel`, consumed
before DOM props and defaulting to its prior English text; ContentPage passes
current calendar locale and replaces the hardcoded preview caption. Ten complete
copy records and regression tests preserve default/custom accessible controls,
Escape/button closing, invoker focus and no current-scenario API writes.

Causal RED5fail5.42s; first GREEN49pass2fail is mock-history contamination, not
an application write. Clearing prior mock calls retains the no-write assertion.
First TypeScript run then rejects unsupported `exact` role-query options;
removing those options preserves exact string-name matching. Final focused51pass
8.83s, TS46.851108s, lint17.999153s(0errors/1knownwarning), build20.550229s and
199asset-integrity287.737ms pass. Full frontend620/129files354.85s,
capture356.870512s/exit0/no timeout or truncation; expected negative-fixture and
jsdom stderr is preserved. Two independent scoped reviews pass. No browser,
production, current backend/image or full-sheet localization certification.

## TEST-DEMO-02 — preview signal finalization and bounded read compatibility

Private test instrumentation only; no application/dependency source changed.
Installed-Vite legacy reproduction fails only SIGTERM (exit143, missing report),
while SIGINT/deadline pass. New owned listener/close pattern passes3/3; actual
guarded helper smoke independently passes, preserves final JSON and223artifact
files, rejects login in smoke mode and closes both ports. Source review also
hardens async multipart admission and prevents read errors unlocking writes;
five policy/multipart tests pass, without a racing-request integration claim.

V2 current UI observes map/review/content/photo guidance, financial summary and
old history, partnership hypothesis and unsaved campaign panel. The native
picker is tool-denied, so no financial preview/import happens. Clean SIGTERM
produces lifecycleValidtrue but overallfalse/exit1 after320867.914ms. All finance
and partnership baseline digests stay unchanged. Two exact read additions and
an allowed picker route remain; disk-video upstream403 is feature-disabled on
the retained stage. No full demo, deployment or readiness score change.
Raw detail: demo-v2-rehearsal-20260919.md; COMMANDS records hashes and captures.

## TEST-DEMO-01 — persist an explicitly unconfirmed partnership demo hypothesis

Commit `1e955718` changes only `scripts/seed_journey_staging.py` and its new
SQL-contract tests. The journey preview contained the local-audience narrative,
but the actual Partnerships drawer reads a separate `match_json` artifact,
which the seed never inserted. The new insert uses the deterministic fixture
lead and `ON CONFLICT (lead_id) DO NOTHING`, with `needs_evidence`, overlap,
an explicitly synthetic explanation and a manual fact-check next action.
It adds no confirmed score, contact, offer, approval or send.

Root-captured RED against archived6eec seed:2failed0.20s (capture0.546771s).
Same test against the fix:2passed0.05s (capture0.239399s). Five-file adjacent
suite:44passed0.70s (capture1.094591s); counts overlap. All captures are
untruncated, not timed out, with empty stderr. RuffF821 and diff checks pass;
independent source/schema/drawer reviewPASS. Source SHA-256
`70b99674d87f99de0964798a51f808840711fddf1ac07a40b61fe992e07e7ff0`;
test SHA-256 `737dcc21f4b1132e0962c6ed0aaa42bcee171faa9eebbf02f1505615f524b6ae`.
The tests record SQL, not a real PostgreSQL preservation or browser result.
At that source-fix checkpoint no retained stage was changed. Full-seed replay is unsafe for that purpose:
pre-existing seed statements update other fixture fields. Next runtime work
must be an exact scoped synthetic artifact update, followed by the actual drawer
and complete presenter rehearsal. The separate fullbackend6eec run excludes
this later seed/test commit and is not proof for this delta.

19 September runtime follow-up: an independently reviewed identity-checked
helper inserted only the missing synthetic artifact (663.349ms/exit0); repeat
preserved it (359.476ms/exit0), with unchanged whole-row digest and zero protected
outreach counts. Current frontend39aeeff9 over historicalf0cc stage visibly
renders the intended synthetic overlap, unconfirmed score and manual next
action in the actual drawer. Final read-only inspect610.647ms passes.
This closes the scoped fixture/render defect, not the complete presenter demo.

The full walkthrough stopped before finance preview/import: managed chooser
stalled24190.3679s and the preview reached its1800s deadline. Two entries and
four prior batches stayed unchanged. Seven GET403s came from an incomplete
positive proxy allowlist, not application defects. A separate drawer-only
run rendered the fix but ended143/107152.023ms with empty helper result; root
independently checked resource cleanup,223artifact files and stage flags.
No helper lifecycle PASS, full demo, production, new image or wider dirty-tree
coverage is inferred. See task raw/demo-rehearsal-current-ui-20260919.md.

## UX-LOCALE-05 — localized manual review-draft copy

The review draft card had a hardcoded English `Quick Generator`, raw `draft`,
Russian manual-publication instruction and Russian Copy/Copied feedback. The
first locale RED is3failed/1passed7.35s; a selector-only GREEN failure and a
Copy RED2failed/2passed are retained. The minimal component change reuses the
existing generate/proposal labels and adds manual-publication plus Copy/Copied
keys in all ten supported locale files; it does not alter API, clipboard payload
or manual-publication behavior. Focused RU/EN/EL regression passes4/4 in3.79s
(capture5.355626s) after a separate TS1117 RED found four identical `copy` keys.
Deduplicated typecheck, lint, both builds and199app/12public artifact integrity
pass. The615-unit pass predates that deduplication; the private browser attempt
failed preflight before login because its flag assumption mismatched the retained
compiled fixture. The preserved failures also include the retry heading locator
RED13.470579s and its diagnostic RED12.932163s (login proved; no API result).
After correcting the harness-only cookie-auth build setting,
`review-locale-browser-cookie-20260919.json` passes3/3 current-built-frontend
scenarios in5.950617s: desktop RU, laptop EN and mobile EL. It verifies exact
clipboard text, records zero captured page/console errors and zero browser
mutations/direct-stage/external requests, preserves the artifact manifest and
cleans up browser/Vite resources. Three synthetic-login POSTs are explicitly
in scope, so it is not a no-database-write claim. This is not all-locale,
whole-workflow, current-backend/image or deployment evidence.

## SEC-LOG-01 — remove password-reset URL credential logging

`SetPassword` read URL `email` and `token` values on mount and logged both raw
values. The `/reset-password` route forwards that token to the reset-confirmation
endpoint, where it is checked as an expiring reset token. Causal synthetic RED
`password-logging-red-20260919.json` fails1/3 in4.71s (capture7.595154s): after
the exact mocked reset POST and success state, the console capture contains both
synthetic email and token. No real credential was read or used.

The two raw `console.log` calls were removed without changing the reset request
or success behavior. The first post-fix suite is retained as a fixture failure:
27passed but the fake-timer plus `userEvent` test timed out at5s
(capture17.769319s). The corrected `fireEvent`/`act` test keeps the exact payload
and success assertions, captures log/warn/error, and passes28/28 in11.15s
(capture12.628319s). Typecheck passes39.757401s; lint passes with0errors and one
existing warning in15.610447s; app build passes15.46s (capture17.366236s), and
199-asset integrity passes0.346085s. Local artifact proof finds both credential
log literals before and neither after while retaining the reset endpoint
(0.501916s). Committed39aeeff9 after independent scoped review. Full frontend
units subsequently pass616/128files309.65s (capture310.950615s) on identical
source. This is local FIX_PROVEN only: no real reset, production runtime or
target-image claim.

## OPS-CALLBACK-02 — rotate alert coverage beyond the first100 tenants

Local commit7bb9f996. A native PostgreSQL101-tenant regression fails because
two scans select the same100tenants, never the last one. SQL now orders the
disjoint after-cursor and wrap segments, returns at most the configured batch,
and advances the cursor after successful nonempty selection. Query failure
retains it; one tenant's metric exception/failure does not block later tenants.

RED1failed/1passed0.63s, capture1.430475s. GREEN29passed12.04s,
capture12.858612s, Python compilation/RuffF821PASS, no timeout/truncation/stderr.
Independent source/hash/evidence reviewPASS; root confirms0residual test
schemas. This29-test set overlaps the earlier25and73sets, not29additional
unique cases. No migration/API/publication change or production action.
The process-local cursor resets on restart; no durable multi-worker fairness
or query-performance improvement is claimed.

## OPS-CALLBACK-01 — interrupted callback claims become actionable

A process interruption after durable `pending → sending` left the notification
outside both dispatch and replay forever. Real-PG RED reproduces that exact
state (1 failed / 1 passed), not an inferred production incident.

Dispatch now quarantines tenant-scoped claims at least one hour old into the
existing DLQ with `callback_delivery_uncertain_after_interrupted_claim`.
It neither sends them again nor fabricates attempts. Cached batch rows are
rechecked before HTTP; finalization requires the exact current lock identity,
and status plus attempt insert commit together. Additive metrics and the worker
scan retain visibility after the original creation-time window has expired.
Normal retry, signatures, event/dedupe IDs and authorized replay are preserved.

Independent static/evidence review accepts bounded local FIX_PROVEN: 19 tests
pass in1.82s, including10 real-PG interruption, batch-bound, tenant, replay,
late-result and old-row alert cases. Root postcheck found0 residual schemas.
Separate adjacent verification passes73tests23.75s:60 capability API,3 schema,
10 native recovery; preceding RuffF821 passes. Native nonce schemas/roles are
absent. One historical exited Testcontainers resource predates the run and was
preserved, not incorrectly attributed to it.

Independent call-chain review then found the deployment smoke automatically
replayed all DLQ/retry after an alert. Causal fake-command RED2fail/1pass
demonstrates that path. Its implicit replay/dispatch loop is removed; manual
reconciliation and strict exit2 remain. Normal capability/outbox sub-smokes
still create actions/dispatch eligible ordinary callbacks and are explicitly
disclosed, not mocked away in a claimed read-only guarantee.

OPS-SNAPSHOT-02: the helper's Python heredoc consumed stdin, discarding piped
outbox JSON. Additional RED1fail/5pass reproduces JSONDecodeError; passing source
through `python3 -c` restores the exact before/after incident snapshot calls.
Final combined25tests pass11.41s/capture12.293402s, with Python compilation,
RuffF821 and bash syntax passing. The73and25sets overlap; do not sum them.
No new migration, external notification, production action or full aggregate/
image claim. The separate sorted100-tenant fairness follow-up is now fixed
locally by OPS-CALLBACK-02 above.

## TEST-E2E-04 — observe console errors at the configured staging origin

Both owner reviews/finance specs now pass Playwright's baseURL to a shared
test-only collector instead of silently accepting only port18000 sources.
URL-origin comparison handles dynamic ports, IPv6, relative/blob URLs and
default HTTPS ports. Page errors and unknown-source console errors remain
visible; known foreign-origin errors and non-error console levels remain
outside this assertion. Invalid base configuration fails before listeners.

The actual extracted old collector fails8of15 pure event regressions. The
fixed collector passes21/21; scoped strict TypeScript and zero-warning lint
pass, independent reviewPASS. Command captures are documented in COMMANDS.
No app code or dependency changes. After space recovery, the direct supervised
browser follow-up at archived641 passes6/6 in22.0s, capture48.938396s; its fresh
synthetic DB and recorded processes were independently confirmed absent.
Earlier117real-API results are not retroactively promoted to clean-console
proof; this covers only the two selected flows across three viewports.

## DEP-LOCK-01 — pin the already-observed Docker base indexes

Two FROM references now use the exact Node22/Python3.11 OCI indexes resolved
by historical f0cc BuildKit. Public Registry-v2 metadata verifies response hash,
digest header and ARM64/AMD64 descriptors. No layer download or version upgrade.
The new pin contract fails against floating refs; directly affected packaging
and frontend assertions now include digest syntax. Independent review passes.
Root guarded aggregate: **14passed0.19s**, capture557.788ms,exit0,no timeout or
truncation (`raw/docker-base-pins-root-20260918.json`). Application/frontend/
migrations are unchanged. This is static pinning proof, not a current image,
AMD64 execution, apt/hash lock or closed DEP-LOCK-01 finding. Build remains
blocked by local Mac disk headroom; no production deployment.

## SEC-RBAC-06 / SUB-MOBILE-01 — stored role and subscription admission

Reviewed `272794a4` uses canonical write access on five review mutation routes
while preserving read-only preview. Common stored-action confirmation validates
the complete target list and requires current write permission for every target
before entering any of nineteen mutation executors. Missing/malformed/duplicate
targets fail closed. Completed cached results remain idempotent and do not
execute again. Actual `review_replies.` actions now use existing `maps.reviews`
subscription admission at both preview and confirm; the old alias remains.

Native PostgreSQL RED proves10direct-route viewer failures, four common-confirm
failures (including mixed targets and real synthetic finance deletion), and two
subscription failures. Corrected initial pending-state fixture expectation is
recorded separately; no denied-action assertion was weakened. Combined root
GREEN passes **104 tests in156.03s**, capture160.365553s exit0/untruncated, with
51native role/subscription cases,36adjacent action/review and17subscription
checks. Independent final review/hash and fixture-catalog checks pass. No real
model/provider call or production action. Later current272full aggregate4728
and native117browser pass; current immutable image remains separate. UI does
not yet hide every read-only-only control.

## TEST-E2E-01 — isolated real-API CI job, execution not yet proven

Reviewed `3ac13d87` adds a separate GitHub-hosted scheduled/manual job for
three existing real-API journey specs, unique synthetic Compose resources,
credential-free child environments, exact owned fixture target and fail-closed
cleanup. Existing default/nightly gates are unchanged. Signals leave the
current phase through cleanup; the outer workflow timeout still owns hard
process termination. No broad prune or local developer target is accepted.

Root source-frozen fake-command contracts pass **11 tests in 17.08s**, capture
18.168537s, exit 0, no timeout/truncation (`ci-real-api-contract-root.json`).
Review corrected signal continuation and mismatched Chromium install/run
paths before commit. This proves script contracts, not a GitHub Docker build,
migration, browser journey or real resource cleanup. No workflow was pushed,
activated or manually dispatched by this audit.

## OPS-IMAGE-01 / OPS-MIG-01 — opt-in application release profile

Reviewed `a00ac558` adds `docker-compose.release.yml` without changing the
default deployment. App/worker/operator-worker and the separate Telegram image
use explicit repository+digest references, inherited builds/code bind mounts
are removed, and application data uses named volumes. Ordinary app workers
check schema only; one profile-gated migrator owns upgrades with explicit
required DB inputs and Flask configuration. PostgreSQL/Redis image tags are
unchanged and are not covered by the application immutability claim.

The first draft's missing migrator configuration and host-only test discovery
were rejected in review and corrected before commit. Root's actual daemon-free
Compose rendering plus existing migration startup contracts pass **13 tests in
3.68s** (capture 4.301181s, exit 0, no skips/timeout/truncation), independently
reconciled. Raw: `release-profile-contract-root.json`. No container, image,
database or production changes occurred. Fresh image startup, migration/rollback,
data transfer into initially empty volumes and release rollout remain unproven.
Only the base+release merge is covered; other Compose fragments need review.

## FIN-UPLOAD-01 — bounded finance file admission

Reviewed015b4ebc adds a10MiB in-process stream/parser limit and dedicated413
responses in finance preview/import-file. Existing other error and apply
contracts are unchanged. Deterministic bounded-read sentinel fails before
the fix; no huge fixture or production outage was created. Exact64-byte
acceptance/65-byte CSV+XLSX rejection tests use a reduced test constant and
verify zero parser/normalizer/DB effects on rejection. Root authoritative
31tests pass1.48s/2.156451s. Worker dotenv flag mistake and root missing-DBURL
30/1 failure remain explicit; final root run disables dotenv and uses a
nonconnecting sink DBURL. This closes byte admission only: multipart spooling,
proxy limits, row counts, decompressed XLSX and CPU budgets are separate.

## AC6 proof — retrieved finance data cannot supply execution authority

Test-only24e0d4cd exercises real Runner→ActionOrchestrator→policy/handler and
post-approval finance apply with isolated synthetic PostgreSQL rows. Attacker
business/tenant/capability/approval fields remain nested data: no stored
approval blocks all action/finance effects; approved execution retains trusted
run business and pinned capability. Foreign apply403 changes nothing; owner
apply creates exactly one target entry/batch, zero foreign entries/batches.
Provider/model seams have zero calls; SQL error observer stays empty. Root
capture1passed0.79s/2.743835s and independent final review PASS. Initial500s
were omitted canonical fixture tables, not product bugs. One scenario is not
the entire AI/tool security matrix; no real provider or production effect.

## DEP-LOCK-01 partial mitigation — constrain the observed app resolution

Reviewed2e121912 adds101application version constraints and Docker COPY/-c
consumption; three packaging tools retain their separate Docker pins. Exact
source104map versus projected104map differs only in pip24.0→26.2. Requirements
intent is unchanged. Eleven static tests pass0.14s/0.428670s. Clean image build,
installed map comparison and advisory refresh remain pending. Version pins are
not artifact hashes or a universal architecture/bot/offline lock.

## SEC-APPROVAL-06 — publication approvals bind the actual target and media

Reviewed13c1f36a stores a nonsecret v1 descriptor of approval/business/platform/
mode/text hash, provider recipient/sender/account and ordered media IDs/version/
hash/storage/public URL/MIME. Queue/claim validate it; durable intent freezes
it for the actual adapter. Missing/malformed/stale authority moves to review;
postclaim configuration cannot redirect the payload to a newly chosen target.
Telegram bot identity uses its numeric ID, not persisted credentials; provider
account refresh retains the approved identity. Manual channels are unchanged.
Unconfigured API text remains approvable/queueable per current UI, but cannot
send; a later connection requires fresh approval. SEND-AMB lock/CAS/uncertainty
and stored write-role boundaries remain tested. Media DB descriptors are
bound, not an assertion that arbitrary remote URL/object bytes are immutable.

CausalRED7fail/1positive20.22s and its truncated output are retained. Initial
integration failed13/38pass/9skip; two missing-facade collection errors and
green4 unbound-queue failure1/251pass/9skip63.04s are also retained. Corrections
restore compatibility names and exact prior queue behavior; fixtures create
real approved snapshots/valid-format synthetic bot identity. No assertion is
removed to conceal a product failure. Finalmain capture252pass/9viewer skips
60.62s, then separately configured viewer9pass/0skip2.43s. Independent final
review PASS and36pure/ratchet checks pass0.38s. This is not a combined261-test
aggregate, live provider run or final whole-source release proof.

## DEP-PIP-02 — pin the image installer before dependency resolution

Commit65ca8836 pins pip26.2 in the app Dockerfile before requirements, retaining
the Python3.11 base and existing indexes. Telegram inherits that image. Exact
b43 inventory audit checked104packages/0skips and reports12records/6unique
advisories only in pip24.0. Independent source review and root8static tests
pass; first root command typo/no-tests result is retained. No exploit claim,
host install or image-level FIX_PROVEN: rebuild/version/re-audit remain.

## OPS-READY-03 — bounded database-aware readiness without mutation

Commit52292e6e adds `/ready` while leaving DB-free `/health` unchanged. A fresh
connection has connect_timeout2s and transaction-local statement1500ms/lock
250ms limits. Read-only SELECTs validate connectivity, expected/compatible
Alembic head and existing content-learning schema columns/indexes. Response
is generic200ready/503not_ready; no cached DB result, credentials or revision
disclosure, provider access, migration or discovery telemetry write.
The standalone schema checker shares its predicate and keeps direct CLI use.
Clean archive24tests pass9.25s/10.005698s captured, including real nativePG
read-only/schema invariants and registered routes. Independent scoped PASS;
root implicit-BEGIN suspicion is NO_BUG_PROVEN from actual transaction mode.
No Compose default, live image or production change. Image proof remains.

## SEC-RBAC-05 — social publication writes require a stored write role

Commit `813609cc` adds a canonical write-role boundary for preparing, approving,
editing, queuing, publishing and reconciling social posts, attribution/metrics,
scoped dispatch and future-plan recommendations. Read/list/rehearsal access is
unchanged. Manual reconciliation rejects a viewer before its advisory lock.
Only admission is newly write-gated; already claimed provider/finalizer paths
retain durable attempt/CAS handling so later revocation does not lose receipts.

Real PostgreSQL RED2 showed direct/network viewers could prepare posts (200,
not403), while six allowed/read controls passed. The full negative matrix now
checks unchanged post/plan/item/count snapshots and zero downstream calls.
Owner/member/manager/network-owner/superadmin controls remain allowed.
Independent review PASS: **254passed,0skipped,42.39s** (42.756s capture),
including13real-PG uncertain/concurrent/manual lifecycle cases and size limits.
`social-posts-viewer-rbac-expanded-green-20260918.json` is authoritative.
The earlier233pass/21legacy-fake failures remain; only pre-authorized unit
doubles were adapted, with explicit dispatch-before-preflight assertions.
No production/provider action; approval recipient/media binding stays separate.

## OPS-GET-DDL-01 — schema-free, membership-aware business reads

Commit `2d875357` removes request-time CREATE/ALTER/global backfill/commit
from GET business data. Canonical Alembic owns that schema. Existing404 stays;
canonical read access permits active direct/network members and viewers,
without granting write access. Causal RED3 captures actual DDL attempts even
for denied403 requests and rejects three legitimate readers. Earlier import,
fixture and empty-recorder failures are retained and not causal DDL proof.
Independent review PASS; new+adjacent real-PG tests **15passed22.26s** under
the pinned native guard (`business-data-preauth-green.json`). Local only;
current staging backend still runs f0cc until the next frozen image.

## UX-CALENDAR-03 / A11Y-CONTENT-04 — bounded layout and focus return

Actual mobile geometry has393px client width but762px Month layout /437px
List layout; visual-viewport offsets misdirect the normal sheet click to the
date label. CSS-only hypothesis restores393px and normal click passes.
Canonical regression fails before correction with369px horizontal overflow.
The two-class fix adds wrap/max-width to section navigation and min-width0
to the calendar grid child. Independent source review passes. Isolated build
passes lint/fullTS/19ContentPage tests and bothbuilds81.932s. Only frontend
dist copied to ownedlocal app, olddist retained; all5containerIDs/starttimes
unchanged, noDB/restart. Expanded120run passes original117 but exposes
3newfocus-return failures (248.788s). This was not a fully green aggregate.

Reviewedcommit20431224 additionally remembers the actual calendar/List/nearest
button and restores it on Sheetclose only while connected and enabled, then
clears it. Deep-link opens retain default behavior. Three focused unit cases
added; clean snapshot passes fullTS/lint/22units/bothbuilds84.350s. Fresh
served-artifact6/6browser proof25.178s covers all3viewports, unchanged normal
pointer/focus assertions and actual receipt/double-confirmation/DB outcomes.
Full120rerun also passes: exit0/no timeout/untruncated,227.301080s captured,
`content-focus-browser.json`. Independent reviewer confirms all three
viewports, unchanged receipt/DB assertions and no prior scenario regression.
This is not a final immutable image or deployment.

## Current image/runtime checkpoint — f0cc182a

Clean tracked archive built bothfrontends with Node22 and browser-enabled
backend in55.385755seconds. Exact ARM64 image
`sha256:b43efb29cbd176d75c97cfa769adbebe7e7e20a1d467cd1c0a561538305cc93d`,
1070645450bytes. Real offline/read-only smoke passes3.721313s:UID10001,
Chromium153.0.8010.12, pypdf6.16.1, pipcheck, bothentrypoints present.
Initial6.111s build failed because sanitizedPATH omittedDockercredentialhelper;
raw failure retained, not a product defect. FourBuildKit secret warnings name
booleanfeature flags only; independently inspected, not secret material.
Onlyownedcompiledstagingapp recreated4.533s, other4services IDs/starttimes
preserved. No new migration in4a8..f0cc, no database restart/reseed. Current
117realbrowser retry completed116/117; mobile issue/follow-up above. Exact
captures inCOMMANDS.md. The app now has the separately recorded local frontend
artifact, so image identity alone no longer identifies served frontend bytes.

## SEC-RBAC-04 — services and content respect stored read-only roles

Commit125900b2 follows real nativePG red cases: direct/network viewers returned
200 from service add/compression draft and content item editing. Earlier three
setup failures and the incomplete JSON fixture red remain explicitly separate
from causal proof. Clean e3archive with corrected fixture reproduces service
denials missing, while allowed controls work. Authoritative captures are
`services-content-viewer-rbac-service-red-e3f42dbf.json` and content red4.

Existing canonical write-role verifier now guards service add/compression
mutations, problematic enrichment/regeneration, and enrich/update/delete of
stored services, including services historically created by a current viewer.
Stored business role is checked before provider work or SQL effects; legacy
NULL-business own-user/superadmin behavior is retained. Content item update
uses its stored plan business for the same write guard; read/list/audit and
content-plan reads retain the existing read-access helper.

Independent review PASS;27native/adjacent tests pass3.35s in
`services-content-viewer-rbac-final.json`. Tests inspect service/request/source
active snapshots, content text, provider seam calls and regeneration-job count;
direct/network viewers and revoked/foreign actors cannot write, owner/member
controls remain. Existing employee fixture now models the distinct write seam
without weakening assertions; independent7fake checks pass0.33s. This is not
platform-wide RBAC closure or deployment; final whole-source suite is pending.

## DEP-ENGINE-01 — align the frontend image builder contract

Commitba891be4 changes Node20-slim toNode22-slim only; all three CI workflows
already useNode22, and locked jest-dom7 requires>=22. Three contract tests and
independent review pass. No dependency/lockfile changes. Actual cleanf0cc
Node22 image/bothfrontend build and nonroot/offline smoke now pass; exact
identity/durations are in this document's current image checkpoint.

## TEST-PERF-02 — guarded prepared dashboard profile

Commite3f42dbf adds bounded pairwise Flask-dispatch measurement with strict
database/guard identity, child watchdog, exact response/coverage checks and
owned cleanup. Real first run caught a parent seed import omitted from clean
processes;94de718c fixes it with fresh-process red/45combinedgreen. The8-user
profile retains expected5/min login admission failures; unchanged4-user profile
passes44/44semantic requests with independently recomputed resource/latency
values. Details and limitations in report04; no HTTP capacity/speed claim.

## Social module size ratchet and browser fixture follow-through

01446148 mechanically extracts unchanged media transport and publication
lifecycle functions; independent AST/facade checks and272combined tests pass,
ratchets decrease to1895/1977 rather than allowing growth.853bdc5d prevents
empty PYTHONPATH entries from falsely identifying a CWD guard.6c96192c adds
strictly guarded social reconciliation fixtures and canonical discovery of
117staged browser cases. The clean6c backend aggregate passes4538tests with
only7intentional live-provider skips; new staged browser runtime is pending.

## UX-CONTRAST-02 — actual attention heading verified in the browser

Commit8ebec5ca changes only EmployeeWorkspaceSection title opacity60→80 and adds
two rendered tests (attention and normal state). Trace identifies the observed
heading `Готовность процесса`; it is not the nested workflow graph caption.
Independent Vitest/ESLint/TypeScript review passed. Clean frontend build27.414s
was copied only into the isolated local4a8 backend; full real-API browser suite
then passed114/114 in215.263s across desktop/laptop/mobile.

The earlier graph change5c1af983 was an adjacent readability change, not the
causal fix: its rebuilt browser suite still failed3/114. Both failed captures
remain intact. Raw `frontend-employee-8ebec5ca-build.json` and
`browser-employee-8ebec5ca-full.json` establish the accepted local checkpoint.
This does not certify later uncommitted publication protection or production.

## SEND-AMB-01 — durable publication hold and explicit reconciliation

A real isolated PostgreSQL transaction and fake Telegram transport reproduce an
accepted post whose final DB commit fails: rollback restores `approved`, and a
retry sends twice. The original one-test reproduction asserts that buggy
behavior and is not a green protection test. Reviewed commit `d3ca8b1e` now
commits intent before provider I/O; only the successful fresh claimant sends.
Published replay returns the existing receipt. Uncertain/exception/final-commit
failures keep a durable `publishing` hold and expose reconciliation, not retry.
Provider outcomes distinguish accepted, rejected, not attempted and uncertain;
success requires an actual receipt. Telegram partial media success is not resent.

A per-post session advisory mutex on an autocommit connection excludes manual
confirmation while the provider/finalizer is active, without an open SQL
transaction across network I/O. Manual confirmation uses the matching
transaction mutex and requires one receipt plus explicit confirmation; the
bulk endpoint cannot apply one receipt to uncertain posts. State/attempt CAS
protects against stale editing, approval, queue, preflight, upsert and deletion.
The UI offers the safe reconciliation action, blocks resending and ignores
stale callbacks; double submission stays disabled until saving settles.

Independent core/provider review: 36 real-PG/adapter tests passed in32.31s
(retained pane capture `send-amb-independent-pane-20260918.json`). Root's full
six-file adjacent run first had234pass/3fail because the legacy manual cursor
fixture lacked the new advisory SELECT. The exact fixture response was added,
without weakening semantic assertions; rerun **237passed35.65s**, captured
37.569s/exit0 in `social-publish-root-green.json`. Original failure remains in
`social-publish-root-final.json`. UI **19passed**, focused ESLint/full app+Node
TypeScript passed52.179s (`social-publication-ui-final.json`), reviewed.

`send-amb-01-native-pg-lifecycle-final.json` is a worker-authored summary, not
an authoritative command capture; its earlier contents were overwritten.
Use root captures and the independent pane for the final evidence. Original
red/green commit-failure captures remain separate.

No schema change, production write or real provider call is involved. This is
duplicate-send protection, not exactly-once delivery. Fingerprint binds
business/platform/text, not actual recipient/media; provider target binding is
not claimed. Explicit browser/API reconciliation and final whole-revision
verification remain pending.

## TEST-COMPILED-03 — durable isolated profile and real execution

Committed4a8e33b8 after independent19-test review. Tracked bounded fixed-upstream proxy replaces the lost temporary proxy; canonical hash/read-only mount and explicit local Docker context are checked. Staging execution/advanced gates default off with empty cohort; all bot/worker variants are profile-disabled. The deliberate ingress host-access network exception is documented; app/PG/runner remain internal. No production rollout.

Actual clean4a image starts a new synthetic PG16/head20260907_001 staging project in25.671s. Guarded proof then passes11.760s:10previews,5real runner executions, compile/run replay, persisted reports, runtime_ai_calls0. Nothing is pre-marked completed. Raw `compiled-4a8e33b8-{start,proof}.json`; actual browser suite remains a separate gate. Runner pinned to inspected cached local image ID for integration, not a production registry manifest; model generation/live-user pilot untested.

## OPS-RESTORE-01 — actual full synthetic restoration verified

Committed restore helper ran against a fresh explicitly named, Compose-labelled, loopback-only PG16 target. Trusted80896-byte synthetic SQL archive SHA6dc039e4341960441c0b5e0256b9d122c2edf9829ab63cfea03ae263ddc48718. Independent read-only rechecks prove exact schema after removing only random pg_dump restrict tokens, data in288tables with duplicate-preserving sorted INSERT statements,844indexes/19triggers/3views/160functions/2sequences, owners/grants/defaultACL and sequence1,false states. Alembic20260907_001 matches. `raw/restore-helper-full-schema-20260918.json` records full provenance.

The first temporary comparison script had weak pipeline-error handling and an invalid suppressed sequence query; its empty sequence hashes are explicitly non-authoritative. Independent checked dumps/direct queries close that evidence gap. This proves controlled synthetic restoration, not any production backup's validity or a destructive production rollback.

## TEST-PERF-01 — correctness harness before measurements

Committed0f221803 after independent review; 15 real request checks and3untimed invariants pass on canonical migrated synthetic data with only two explicit provider/model seams. Raw `journey-benchmark-one-sample-final-guarded.json` and wrapper capture preserve provenance. This one sample is not p50/p95/p99/load evidence. Repeated-ref driver is uncommitted: review identified import contamination, missing process/time/status/ownership guarantees and migration-contaminated concurrent timing. Those must be closed before any performance claim.

## DATA-LEGACY-01 — align legacy business data with migrated PostgreSQL

Committed43578807 after independent review. Actual login→GET `/api/business/<id>/data` on a fresh migrated schema returned500 because the read queried nonexistent financialtransactions.date; canonical column is transaction_date. Correcting that exposed dict-like row iteration returning column names instead of service/transaction/metric values. Read methods now preserve dict-row values with tuple fallback, sort canonical dates, and retain the external legacy `date` response key. No migration/DDL workaround or tenant widening. Self-contained real-PG regression seeds actual service/two ordered transactions/metric and checks login, values/order and foreign403. Guarded fixture rejects inherited libpq overrides and URL query/hash before creating only its UUID database. Independent8tests5.59s pass. Not deployed.

## OPS-IMAGE-02 — avoid duplicating installed Chromium binaries

18September runtime closure: clean4a8e33b8 image builds61.615s; actual offline/read-only/nonroot Chromium153 launch passes3.682s. `.Size`1376269248→1070569043bytes,22.2% smaller than a025; ownership layer now45.1kB. Both frontend artifacts/pypdf6.16.1/pipcheck pass. This supersedes the pending runtime condition in the original source-review note below. AMD64 and image vulnerability scan remain unverified. Build records Node20/jest-dom7 engine warning and third-party PURE annotation warnings; boolean featureflag Docker secret-name warnings are not secret values.

Committed6eb2d185. Docker cache inspection measured a999MB browser-install layer followed by a999.1MB recursive ownership layer. Removing only `/ms-playwright` from the final recursive chown avoids this redundant writable copy; data/cache directories remain localos-owned. Canonical Docker workers do not use the legacy host-venv install wrapper. Existing binary modes755/data644 permit nonroot reads/execution, but the previously built a025 image still had old ownership: **new image and actual Chromium launch remain required before runtime proof/size claim**. Source reviewer conditionally approves; root3contract+Compose tests0.57s pass. No recursive chmod or browser download removal.

## TEST-COMPILED-02 — propagate frontend preview flag through canonical build

Committed44d597af, independent approval. Canonical Dockerfile omitted VITE_COMPILED_SCRIPT_PREVIEW_ENABLED even though the browser fixture requires compiled UI. Two contract tests failed against old Dockerfile/renderedstaging. Added ARG defaultfalse/ENV before frontend build; staging explicitly opts true. No production-default enabling, backend cohort still required. Focused+adjacent13tests pass0.79s; independent13pass1.44s. The a025 image built before this change cannot establish compiled UI proof; durable proxy/profile and real runner tests are separate ongoing work.

## SEC-RBAC-03 — Operator chat denies read-only memberships before effects

Committeda0253199, independent review PASS. Native stored direct/network viewers reproduced200 instead of403 (two failures, six allowed controls). POST `/api/operator/chat` now uses the separate write-role guard before capability checks, audit, processing, result writes or commit. Other routes remain unchanged. New cases cover revoked memberships, owner/network-owner/superadmin and read-only current-conversation GET. Existing fallback fixture mocks the separately verified write helper; assertions were not weakened. Agent22pass1.15s (`raw/operator-chat-rbac-green.json`); reviewer22pass1.08s, expanded44pass1.70s and adjacent24pass0.56s. This is PG15/local chat proof, not platform-wide mutation closure or deployment.

## DEP-PDF-01 — pin the PDF parser with compatibility coverage

Committedee777f59, independently reviewed. Host pypdf6.13.2 advisory matches and reachable uploaded PDFs motivated pinning6.16.1. New valid-text/encrypted/malformed PDF compatibility test and adjacent ingestion tests passed58cases with isolated target install and pipcheck. No shared-venv upgrade or denial-of-service exploit; this is advisory-based mitigation. The later full native suite asserted isolated6.16.1 and passed4319tests. Final image version/audit remain separate gates; temporary dependency target was lost across host interruption.

## TEST-FIXTURE-03 — finance ROI read/write seam in the full suite

Committed5e1ebe79, reviewed. First native aggregate91797c74 had4315pass117skip1failure because the ROI fake cursor stubbed only read authorization after production writes acquired a separate guard. Fixture now models both seams without weakening tenant queries. Added allowed read/denied write and foreign-business controls;26focused tests pass. Fresh clean5e aggregate:4319pass117skip5warnings296.79s, raw `native-full-backend-5e1ebe79.json` exit0. Skips still include safe Docker tests and seven intentionally disabled live-provider cases; this is not final PG16 image verification.

## SEC-RBAC-02 — agent blueprint viewer mutation boundary

Committed206c06ab, independently reviewed. Real native-PG Flask red: direct/network stored viewer creates a blueprint (201, one inserted row) instead of403/no row. Agent blueprint access now selects the existing write-role helper for mutating HTTP methods; only the exact non-persistent `/preflight` POST retains read access. Compiled/custom-process previews persist state and therefore require write authority. GET/HEAD remain read paths; stored blueprint/run business controls authorization, not just a request selector.

Native17tests include actual insertion denial, member/manager/owner/network-owner/superadmin controls, revoked/foreign denial, run/approval denial before runner effects, preflight200 with fail-fast write-verifier spy and unchanged counts, custom/compiled previews denied before effects. Scoped adjacent118passed2.80s; root independent finance+network+blueprint54passed4.17s (`raw/blueprint-viewer-root.json`). This does not close generic Operator mutations or every API's role matrix.

## SEC-WH-05 — WhatsApp replay admission and visible uncertainty

Committed91797c74, independently reviewed. Signed identical callback red reached AI processing and send twice. Existing canonical partial unique event key now durably admits `processing` before effects; completed duplicates skip, processing duplicates do not mutate the first operation. Process failures/malformed results and false/raised provider sends require fixed-reason reconciliation. No automatic replay or exactly-once claim: a process crash after admission remains `processing` and needs investigation.

Handler validates string/opaque provider identifiers without rejecting padded IDs. Per-message failures accumulate a batch response while remaining messages are processed; an early duplicate cannot starve later fresh messages. New superadmin-only GET `/api/webhooks/whatsapp/events` lists bounded attention state without payload, phone, provider key or text. It is an API/support view, not a completed operator UI or automatic provider-history reconciliation.

Independent review caught active-duplicate status corruption, batch starvation, missing send-exception tests, and unsafe test DSN/schema assumptions; all corrected before commit. Native test uses explicit loopback/test-named DSN, rejects libpq host overrides, UUID schema/finally cleanup and two real connections. Root47passed0.50s (`raw/whatsapp-replay-root.json`), including auth/identifier/batch/reconciliation/immutability/concurrency/tenant cases. Provider calls are stubs; no production schema change, send or deployment.

## TEST-E2E-03 — fail-closed native fixture subprocess

Committed618b00b6, reviewed. Native test helper previously accepted an arbitrary DSN, overwrote the caller's Python egress-guard path and could load ambient dotenv. It now requires a literal loopback, test-named staging DB with no URL query/hash; preserves guard-first PYTHONPATH, disables dotenv and removes inherited libpq service/hostaddr/options. Docker branches are unchanged. Red7cases; unit green7, typecheck/scoped lint pass and actual native CLI verified with hostile synthetic inherited service/hostaddr.

The first attempted fix blanked libpq variables; actual browser run exposed78fixture failures (`service file "" not found`) while36nonfixture scenarios passed. Those variables must be absent, not empty. Failed evidence remains; after correction the complete114-case run is111pass/3missing-runner-fixture failures. This helper hardens its subprocess, not the entire machine or arbitrary Python/C-library network access.

## SEC-RBAC-01 — finance viewer and stored-transaction write boundaries

Real native PostgreSQL HTTP reproduction against the pre-fix HEAD archive returned200 for a stored viewer's ROI write where403 was required (`/tmp/sec_rbac_head_red.log`, one failed test). A second reproduction showed that authorizing requested business A was insufficient: the same actor could mutate its own transaction belonging to B, where its role was viewer (`/tmp/sec_rbac_target_red.log`, actual200). An earlier missing-helper ImportError was a test-construction failure, not authorization evidence, and is not used for the verdict.

The read/tenant helper stays unchanged. A separate write helper checks active direct/network roles and preserves business owner, network owner, superadmin and existing non-viewer access. Finance mutations use it; GET/HEAD and the genuinely non-persistent import-preview POST retain read access. CRM preview remains write-gated because it persists status. Transaction PUT/DELETE recheck the stored row's business before mutation. Legacy NULL-business, user-owned transaction behavior is explicitly retained; this is not a redesign of legacy finance storage.

Independent review approved the package and final HEAD/libpq-guard corrections. **37 tests passed in1.80s** (`/tmp/sec_rbac_head_guard_final.log`): real SQL role/tenant/revocation matrix, real Flask ROI and transaction effects, preview/HEAD controls and adjacent routes. Native fixtures require a dedicated explicit loopback test DSN, reject host overrides and clean only their UUID schemas. Generic Operator/agent mutation roles and the entire platform endpoint matrix remain unfinished. No production access, data or provider configuration changed.

## SEC-SSRF-01 — pin contact-page connections to validated public addresses

The old collector validated DNS, then fetched by hostname through `requests.get`, permitting a new resolution at connection time. A synthetic pre-fix run reached the forbidden hostname-request sentinel (`/tmp/secssrf01-red-final.log`, exit1); no private host or provider was contacted. The collector now uses a bounded GET primitive that validates every resolved address and connects to a selected numeric public IP, retaining Host/SNI/certificate checks. Redirect destinations pass admission again. Other outbound clients are not covered by this change.

Independent review caught and required fixes for revalidation exceptions, declared HTML charset and literal IPv6 Host formatting. Final tests cover private/mixed/rebound DNS, second-resolution failure, HTTPS pinning/SNI, private redirects, charset fallback and size/resource-release behavior. **76 tests passed in 1.32s**, root capture exit0 in1.936s (`raw/ssrf-pinned-get-root-green.json`), after independent source approval. The first root run had75passes/one main-import configuration failure because its sanitized environment omitted DATABASE_URL; that failed capture is retained and was corrected by explicitly selecting the synthetic local test DB, not by changing application behavior. No Internet/provider/production request or deployment was performed.

## TEST-COMPILED-01 — explicit local profile and run-scoped admission

Removed historical localhost/container defaults and generic queue claim from the synthetic compiled-table proof. Explicit app/ingress/project/environment/DB arguments are checked against a local Docker endpoint, running labels, exact loopback port, shared inspected internal network and the selected app's `app` alias. Read-only fixed proxy source hash/entrypoint ties this audit profile to its app:8000 route; this is local configuration validation, not hardware/cryptographic endpoint attestation. Docker calls are bounded. Admission UPDATE targets only the created run/blueprint/business in queued state and keeps normal lease/attempt fields; actual runner execution is still required. Independent review and9purefake tests pass, including happy path and negative identity/proxy/network cases. Combined root restore+compiled20tests passed. Real app-integrated execution remains unverified because Docker storage failed; the temp audit proxy/profile also needs a durable reproducible runbook before general developer use.

## OPS-RESTORE-01 — fail-closed local disposable restore helper

Removed ambient `.env` loading, implicit latest-archive selection, default live DB and automatic Compose startup. The helper now requires an explicit trusted `.sql.gz` archive, exact new target/confirmation, local Unix Docker context, container/project/user; verifies running PostgreSQL service labels and every loopback binding; refuses an existing DB, then creates a fresh disposable one. `docker exec -i` is used only for the SQL stream, with `ON_ERROR_STOP`. Plain SQL remains trusted executable input, not a sandbox; the helper intentionally cannot restore production. Failed restore leaves only its newly created disposable DB for deliberate inspection, no automatic destructive cleanup. Independent review caught missing target/context guarantees, invalid `docker exec -T` and weak tests before acceptance. Final independent11fake tests pass; no real helper restore was run during local Docker failure. The earlier separate consistent-snapshot rehearsal is not evidence of this helper's execution.

## DATA-FIN-01 — contain per-row import SQL failure

Real PostgreSQL reproduction: duplicate pre-check sees no row, another transaction commits the same unique key, then the first import hits UniqueViolation and its next valid row fails InFailedSqlTransaction (red1failed0.36s). Each existing item insert now has a savepoint; failed items roll back that savepoint and re-raise to the existing row-error collector. Following valid rows and the batch outcome can commit. File/CRM callers and response/error semantics remain unchanged. Test uses standard isolated testcontainers and a UUID database with finally cleanup, not a fixed developer port. Independent review required and approved that portability/safety correction. Final root combined regression suite11passed12.78s (`raw/data-concurrency-root-green.json`). Entry-path concurrent conflict is proven; other item types share the wrapper but were not independently raced. No external CRM/provider operation or production data change.

## DATA-SVC-01 — serialize compression-draft apply

Two concurrent applies read the same unclaimed draft and created two active replacement services (real PostgreSQL red:1failed4.12s, `/tmp/datasvc01-red.log`). Apply now locks only the draft row before reading status or mutating services; the second request waits, then returns the existing idempotent result. Other draft reads are unchanged. Final portable testcontainer test holds the first real lock, observes the second PostgreSQL session waiting, then asserts two HTTP200s, exactly one `already_applied`, and one active replacement. Independent review rejected the initial host-specific fixture/weak green barrier; both were corrected before commit. Final builder1passed26.76s; main combined data+finance11passed12.78s (`raw/data-concurrency-root-green.json`,13.285s captured), with inherited no-egress guard preserved. Scope is same-draft concurrency; distinct drafts sharing services remain a separate contract question.

## TEST-SAFE-01 follow-up — nested no-egress guards

The ca8bdf0b whole-backend rerun exposed a test assertion error, not an escaped network request: the inherited read-only audit guard denied port8000 before the child guard could emit its own message. The test now independently proves the child's audit hook with an explicit `sys.audit` event (no connection), while the actual socket attempt must fail with one of the two exact approved guard messages. Arbitrary subprocess failure is not accepted. Normal and outer-guarded runs each passed5tests (2.89s/2.45s), `/tmp/localos-safe01-causal-fix.log`; main independently reviewed the diff. No runtime or guard was weakened.

## SEC-AUTH-01 — Inactive session revocation

Status: **FIX_PROVEN locally**, independent review passed. Not deployed in this audit.

- Central `verify_session` rejects inactive users by default before a protected route can mutate state.
- `/api/auth/me` uses a narrow diagnostic opt-in and retains `403 account_blocked`; normal guards retain their 401 denial. Login's blocked-account contract is preserved.
- Normalize boolean/legacy `False`, `0`, `"0"` once for both guard and returned payload. Independent review caught a first-patch inconsistency for text `"0"`; a real `/auth/me` regression test reproduced it before correction.
- No schema, password, session row or production data mutation. Active-session behavior stays covered.

Evidence:

- Initial red builder reproduction: 2 failed / 12 passed, inactive bearer could execute a protected mutation.
- Review regression red: 1 failed / 2 passed (`legacy_inactive_values`), then 3 passed after normalization. JSON evidence in task `raw/sec-auth-01-legacy-zero-{red,green}.json`.
- Root rerun: `venv/bin/python -m pytest -q tests/test_auth_email_case_insensitive.py tests/test_auth_user_routes.py tests/test_browser_session_security.py tests/test_network_member_access.py` → **42 passed in 5.21 s** (7.391 s captured command wall time).
- Independent reviewer: three principal files, **40 passed**, previous finding closed, no additional blocker in the scoped package.
- Focused Ruff F821 and `git diff --check` pass.

Limits: full backend/PostgreSQL suite and deployed behavior not yet verified. This fix does not close the separate role/tenant audit. Source rollback is possible but would reopen revoked-session access and therefore is not a recommended security mitigation.

## CI-TS-01 — Real app and tooling typecheck in both CI entrypoints

Status: **FIX_PROVEN locally**, independent review passed; no CI deployment or remote change.

Both fast/nightly scripts now invoke the canonical `npm --prefix frontend run typecheck`. Their former root `tsc --noEmit` command exited zero without checking referenced app/Node projects.

Regression tests use actual locked TypeScript, tiny isolated referenced projects, real npm and the current package.json typecheck script. They inject errors separately into app and Node code, prove the former bare invocation misses them, and verify both gates fail; healthy fixtures pass. Non-typecheck gate phases are stubbed, so this is not an execution of the entire nightly job.

- Red baseline: six failing contract cases (healthy invocation contract plus swallowed app/Node errors).
- Initial green / independent rerun: 6 passed in 73.34 s / 70.03 s.
- Independent review recommended exercising the real package script instead of reproducing it inside the stub. Implemented; strengthened suite **6 passed in 84.02 s**. Root inspected the revised fixture and bounded subprocesses.
- `bash -n` and `git diff --check` pass. Canonical actual frontend typecheck separately passed the clean baseline and the finance patch check.

No application behavior, schema or provider effects changed.

## SEC-WH-01/02 — Authenticate WhatsApp and business Telegram callbacks

Status: **FIX_PROVEN locally**, independent scoped review passed. Not deployed or registered with providers.

- WhatsApp requires explicit verify token and raw-body HMAC-SHA256 using `WHATSAPP_APP_SECRET`, before parsing or side effects. Invalid/malformed/Unicode signatures fail closed; missing challenge returns400. Compose forwards the secret to app; staging blanks it and the isolation validator rejects leaked values.
- Telegram uses canonical business UUID plus a domain-separated per-business secret derived from the stored bot token. Indexed tenant lookup precedes constant-time authentication; JSON, transport ledger, workflow dispatch and legacy processing happen only afterwards. Retired raw-token URLs return410; raw token header/query/body authentication is no longer accepted.
- Deployment requires an approved provider rebind with the documented secret header, and matching WhatsApp configuration. Bot-token rotation requires rebind. No provider configuration was changed here; this is an explicit rollout prerequisite, not a backward-compatible automatic production rollout.
- Red evidence reproduced unsigned WhatsApp/Telegram callbacks reaching mocked processing/send and the insecure default verification token. Additional malformed-input cases failed before correction.
- Root final regression/adjacent/config suite: **83 passed in 0.63 s**, 1.078 s captured wall time (`raw/webhook-security-config-final.json`). Independent reviewer reran the same set plus two Docker tests: **85 passed in 0.74 s**; staging-isolation check passed. No scoped blocker.

Residual work remains separate: replay/deduplication, legacy WhatsApp PII logging and token-bearing exception logging need their own reproduction and patch. Authentication alone does not prove idempotency or approval enforcement of every downstream action.

## UX-FIN-01 — Finance import follows the selected business

Status: **FIX_PROVEN locally**, fresh independent scoped review passed. Not deployed.

File, mapping, preview, confirmation, history and status are cleared on a business change. Preview/import/history requests capture their business/version, and stale success, error, finally and parent-refresh completions cannot populate the newly selected scope. Successful import and scope changes also clear the native file input, allowing the same file to be selected again.

- Deterministic deferred-preview and completed-preview/history tests reproduce the original cross-business stale state. Independent review of the first patch found the remaining native file input; its regression was red **2 failed / 2 passed**, then green **4 passed** after the input reset.
- Fresh independent run: `npm --prefix frontend test -- --run src/components/FinanceImportPanel.test.tsx` → **4 passed**, 4.31 s test-command duration. Worker app/Node typecheck and lint pass, with the pre-existing `auth_new.ts:115` warning.
- No backend write contract, money calculation or product layout changes. Other content/services/operator scope candidates are not closed by this fix. Final aggregate frontend and real-API scope checks remain required.

## DOCKER-PUBLIC-01 — Include both frontend builds in clean images

Status: **FIX_PROVEN locally**, independent scoped review passed. No production rollout.

The canonical Dockerfile now builds `build:all` and copies `frontend/public-dist` alongside the main `dist`. Both host artifact directories are excluded from Docker context, so a stale local public build cannot hide this failure.

- Baseline clean image lacked `/app/frontend/public-dist/public-audit/index.html`; the real public entrypoint returned404. New static regression was red2, then green with the existing context tests (4 passed).
- Fix built from a separate clean baseline archive containing only this packaging patch: **39.493 s** with cached dependencies, image `sha256:3dc995eb73758128a56c4c1e42e43f3ca61c9c6725c70b3f12329958b12276f7` (ARM64). Both image HTML entrypoints are nonempty, runtime UID10001, source nonwritable, debug directory writable.
- Isolated app returns **HTTP200** for public audit; synthetic seed and five-flow API smoke pass. Capture: task `raw/docker-public-{build,runtime}-green.json`; smoke log `/tmp/localos-readiness-staging-smoke.log`, exit0.
- Fresh reviewer passed both Docker contract tests and inspected independent runtime evidence. This does not claim final whole-product patched-image proof, AMD64 compatibility, browser-worker packaging or dependency upgrades; those remain separate gates.

## TEST-FIXTURE-01a — Restore PostgreSQL test preconditions

Status: **FIX_PROVEN for these fixture groups**, independently reviewed. Runtime code unchanged.

- Client-info's test-only schema now contains the business projection/access columns and membership tables actually read by the route. Seven baseline failures were setup drift, not seven product defects.
- CAPTCHA/expiry/resume tests use their own migrated PostgreSQL testcontainers instead of arbitrary environment DSNs/minimal shadow queue tables; they seed valid users and required `parsequeue.user_id`. The successful resume fixture satisfies the current parsed-card validator. Expected `delayed_auto` and final `completed` states were checked against the actual worker branches, not broadened into an allowed-status list. Test name now describes automatic CAPTCHA retry accurately.
- Sheets recovery tests reconnect using the same explicit `LOCALOS_TEST_DATABASE_URL` used by their isolated schema fixture. `connection.dsn` omits its password and caused five authentication failures before the provider-boundary assertions.
- Client-info/worker combined: **11 passed in 35.44s**. Independent worker rerun: **3 passed in 30.31s**, raw `worker-fixture-review.json`. Sheets recovery/queue: **16 passed in 2.68s**, raw `sheet-provider-fixture-green.json`; reviewer approved DSN/schema isolation.
- No application validation/permissions/schema changes, new skips, provider writes or production access. Remaining baseline hook/Telegram/browser/migration failures and final full-suite rerun are still open.

## DB-MIG-02a — Safely reverse the empty work-review schema

Status: **FIX_PROVEN for work-review revision rollback**, independently reviewed. The complete rollback chain is still failing on a separate creator-portal dependency; no production downgrade is authorized or performed.

The former no-op downgrade left `business_work_links.action_id` referencing `journey_actions`, preventing an older revision from dropping its table. The corrected downgrade acquires `SHARE ROW EXCLUSIVE` locks in a stable order before inspecting data, refuses to discard review/link/settings data, non-default review fields or work-journal actions, and only then removes this revision's empty objects/columns and restores its predecessor's flow constraint. No CASCADE. Populated installations require a reviewed recovery/compensation plan, not a forced downgrade.

- Existing full-chain migration test reproduced the retained FK. New real-PG tests verify empty upgrade/downgrade, five independent data guards and row preservation, using a UUID-named disposable database inside its own testcontainer.
- Root review identified a check/drop race in the initial patch. A deterministic concurrent INSERT immediately after the guard was red without locks: **1 failed in 12.30s**, `/tmp/localos-db-mig02-red.log`. With locks the writer blocks and cannot commit into the removed table.
- Final suite: **7 passed in 35.28s**, `/tmp/localos-db-mig02-locks-green.log`. Fresh reviewer checked transaction/lock lifetime, all lossy fields, exact predecessor constraint and scoped cleanup. Compilation/diff checks pass.
- Existing `test_web_tracking_postgres.py` now passes the original journey-actions obstruction but fails later at `DROP creator_collaborations`, whose newer creator-portal downgrade is also no-op. This is tracked next, not hidden by weakening the test.

## SEC-WH-03/04 — Respect replay admission and keep ingress logs secret-free

Status: **FIX_PROVEN locally**, independent scoped review passed. Not deployed.

- Telegram already had durable per-business event admission. The route ignored its `duplicate` / `legacy_reply_should_continue=False` result when `matched_count=0`, allowing a repeated callback to reach legacy AI/send. It now honors all three admission outcomes; genuinely unmatched new messages keep the existing fallback. No new inbox/table or migration.
- Webhook/send logs use fixed event names and exception class only; no provider URL, exception value/traceback, message body, phone or chat ID. Both outer handlers return constant failure JSON. This is a module-level fix, not a claim that all application logs are clean.
- Before patch: **3 failed / 25 passed** in `ingress_hardening_red`; duplicate reached legacy processing, HTTPError exposed synthetic token/PII, and outer traceback exposed secret text.
- Fresh independent current suite: **89 passed in 0.73s**, `/tmp/localos-secwh0304-review.log`, exit0. Reviewer identified a test-observation gap: capsys alone does not capture logging records. Root strengthened tests with INFO-level `caplog`, individual sentinel absence and fixed event/type assertions; final **89 passed in 0.62s**, 1.016s capture (`raw/webhook-replay-log-final.json`).
- Remaining scope: complete WhatsApp replay/idempotency and malformed event-ID behavior are not established by this Telegram route fix; downstream approval and whole-system logging audit remain open.

## DB-MIG-03 — Safely reverse an empty creator portal

Status: **FIX_PROVEN locally**, independent scoped review approved. No production migration.

The former no-op downgrade retained creator-portal foreign keys into older collaboration tables. The replacement locks all affected tables in a stable order, refuses rollback if any portal table or non-default collaboration review field contains evidence, and removes only this revision's empty objects in dependency order. Populated portal rollback requires backup/restore planning; no CASCADE or silent history deletion.

- Real PostgreSQL: empty rollback, retained relationship data, retained review evidence, and a writer racing between the guard and DROP. Root final run **4 passed in 19.35s** (19.936s captured wall), `raw/creator-portal-rollback-final.json`.
- Independent reviewer checked all eight new-table guards, all four lossy collaboration fields, predecessor constraint ownership, lock lifetime, trigger/function removal order and UUID-test-database cleanup. No blocker; broader guard-branch test parametrization remains a nonblocking coverage opportunity.
- This package fixes one dependency layer. The separately edited offer-distribution downgrade is required for the complete historical chain and is not signed off by this commit.

## UX-SCOPE-01 — Clear revoked dashboard context

Status: **FIX_PROVEN locally**, independently reviewed; not deployed.

Membership refresh now replaces a removed selected business with an accessible one, or clears current business/control scope and mode-specific storage on empty access / the existing API 403 contract. Route-private state remounts on business or network scope identity changes. Transient errors preserve the current context with a visible retry action; revision fencing rejects obsolete and overlapping refresh responses.

- Five tests cover A→B/private-state reset, empty membership, 403, transient failure/retry and late refresh after manual switch. Worker final **5 passed in 2.79s**; independent rerun **5 passed in 3.04s**. Corrected independent ESLint invocation exit0 (`/tmp/localos-ux-scope-01-lint.log`); its first combined command had a wrong lint working directory, not a test failure.
- Root aggregate app/Node typecheck exit0 in **39.149s** (`raw/frontend-scope-typecheck.json`); focused root lint exit0. Reviewer checked network→business fallback and backend response contract.
- Backend authorization remains authoritative; this does not replace server tenant/role checks or establish every child callback's safety.

## UX-JOURNEY-01 — Keep registration navigation stable

Status: **FIX_PROVEN in deterministic component tests**, independently reviewed; original real-API browser rerun is next. Not deployed.

React Router's search setter changed identity after query updates, causing the journey loader effect to run repeatedly. Late load/preparation responses could then rewrite the new route's URL. Use the existing stable-callback helper, cancel obsolete load completions, version pending preparation, and key content by journey token so another journey cannot inherit the previous result.

- Real-API baseline showed registration navigation returning to the start route. Corrected unit reproduction **2 failed / 7 passed**: four GETs instead of one, plus a late response changing `/login` query (`raw/journey-navigation-red-corrected.json`). Earlier attempts contained corrected test-selector mistakes and are not the causal evidence.
- Final **11 passed** (6.183s captured command), including late preparation and old-token response; independent combined journey/influencer run **13 passed in 3.92s**, with full app/Node typecheck exit0. Root focused lint passes.
- Registration parameters and approval behavior unchanged. Remaining browser failures include a stale success-copy assertion and separate compiled-staging prerequisites; neither is hidden by this runtime fix.

## UX-TOUCH-01 — Restore minimum influencer action targets

Status: source regression green and independently reviewed; real mobile geometry rerun remains. Not deployed.

The isolated mobile browser measured the influencer table's platform link / shortlist / reject controls at 36 / 36 / 32px tall, below DESIGN's 40px minimum. Their existing Tailwind minimum-height utilities are now `min-h-10`; layout, labels and mutations are unchanged.

- Targeted red **1 failed / 1 passed**, green **2 passed in 3.36s**; focused lint clean. Independent combined run **13 passed** and app/Node typecheck exit0.
- This is a narrow three-control fix, not a claim of whole-site accessibility compliance.

## TEST-E2E-02 — Align real-API browser harness with its contracts

Status: independently reviewed harness correction; full browser rerun pending.

- Browser fixtures/assertions describe Russian workflows; explicitly set `ru-RU` rather than relying on the default English browser locale.
- Registration previously expected obsolete success copy even when the screen showed successful creation and email confirmation instructions. Assert the actual POST is successful with `success:true`, then require the visible resend-verification action. Token continuity, email verification, action route and cookie checks are unchanged.
- Remove the compiled spec's independent hardcoded port18006. All staging specs inherit one base URL, with precedence `JOURNEY_STAGING_BASE_URL`, legacy `LOCALOS_STAGING_BASE_URL`, then localhost18000.
- Baseline corrected-locale run: **95 passed / 19 failed**, 330.392s; 15 registration failures include runtime navigation races and stale copy assertions, one mobile hit-area failure, three wrong-port compiled failures. Do not classify all 19 as product defects or claim they are all resolved by these harness changes.
- Compiled test still requires an actual approved sandbox runner result. Its fixture is not created by the basic staging seed; no skip or fabricated result added. The standalone old-port compiled script is separate follow-up work.

## DB-MIG-04 — Reverse empty offer distribution without losing history

Status: **FIX_PROVEN locally**, independently reviewed; no production downgrade.

The final no-op dependency layer now locks its affected tables and refuses to discard preference/run/recipient data, campaign review fields, recipient-linked child records or messages that cannot satisfy the predecessor's NOT NULL collaboration constraint. Empty schema reverses in dependency order without CASCADE; compatible pre-existing portal messages survive.

- Scoped final **11passed in30.69s**: four independent new-table guards, three campaign-field guards, standalone NULL-collaboration preservation, compatible predecessor-message preservation, empty reverse and concurrent writer.
- Root aggregate work-review + portal + distribution + existing web-tracking contract: **23passed in69.89s**,70.415s captured wall, `raw/migration-rollback-chain-final.json`. The original upgrade→downgrade→upgrade obstruction is now green on disposable PostgreSQL.
- Independent reviewer checked lossiness completeness, FK/DDL order, transaction lock lifetime and both extra message tests. Populated feature schemas intentionally fail closed; this is not permission to downgrade production or proof of restoring the real production backup.

## TEST-FIXTURE-01b — Preserve outreach and audience test invariants

Status: **FIX_PROVEN for these fixture groups**, independently reviewed. Test-only changes.

Founder outreach's source assertion now locates the actual `restoreTouchEdits` effect boundary after the earlier callback extraction; all persisted-vs-unsaved text and storage assertions remain. Telegram shared-audience fixtures now explicitly subscribe both synthetic businesses to `community_pulse`, satisfying the current visibility contract while still asserting A's decision does not appear for B.

- Red2failed7.25s (obsolete delimiter / ineligible empty result) →green2passed7.65s. Both full files **198passed in7.82s** in named tmux with local PostgreSQL and outbound network guard.
- Reviewer verified current service eligibility and tenant decision join, and that no runtime permission/behavior or assertion was weakened. Aggregate backend rerun and browser harness preconditions remain separate.

## Browser verification checkpoint after the frontend fixes

Both committed frontend assets rebuilt without .env (32.856s) and copied only into the verified isolated local staging app. **33real-API browser checks passed in94.759s** across desktop, laptop and mobile:15registration/email/action-continuity and18authenticated-page quality cases. This closes the original navigation and mobile geometry reproductions for this local build. Other staging specs, compiled runner fixture and final backend-inclusive image still need final aggregate verification.

## TEST-SAFE-01 — Quarantine the retired live API script

Status: **FIX_PROVEN locally**, independently reviewed. No application change or test-network effects.

Default pytest discovery explicitly excludes `tests/legacy`. The archived print-only API script no longer contacts an arbitrary localhost application for registration/login: both direct invocation and calling its old entry point fail closed with guidance toward isolated API tests. This intentionally retires an unsafe manual script; it does not turn a real failing assertion into a skip/pass.

- Four regression checks prove default exclusion, direct-entry refusal, in-process refusal and a no-egress sentinel. **4passed in3.14s**, `/tmp/testsafe01_hardened.log`.
- Root review identified that the first regression subprocess would itself call localhost if old source were restored. Child audit hooks now block connections before collection/runpy, and in-process tests block imports/socket calls before evaluating legacy source. Independent reviewer approved the strengthened boundary.
- Explicit pytest invocation of the retired file fails intentionally; the observed1failure is the expected fail-closed contract, not a pre-patch red reproduction. Remaining archived files are not counted as validated tests.

## Frontend aggregate checkpoint

Fresh committed frontend source, reused locked install: **570unit tests /122files passed**,176.591s captured wall; lint0errors/1existing warning14.728s; app+Node typecheck36.781s. Captures `raw/frontend-patched-{unit,lint,typecheck}.json`. Existing intentional error-boundary/jsdom console diagnostics remain; no unit failures. This aggregate plus both builds and33real-API checks is not a whole-project readiness sign-off.

## TEST-E2E-HARNESS — Isolate Python browser-test startup and requests

Status: **FIX_PROVEN locally**, independently reviewed; test infrastructure only.

Two browser regressions now require installed frontend dependencies explicitly, own a high loopback Vite port with strict binding, bound startup/diagnostics, and clean up only their process group on success or failure. Exact-origin browser interception fulfills only own-origin API and the frontend's canonical DEV `http://localhost:8000/api/*` without any network forwarding; all other origins/ports/protocols are blocked. UI/error-recovery assertions are unchanged.

- Red under outbound guard:1failed+1error17.47s, fixed old ports blocked as unrelated local services. The original clean archive also lacked frontend dependencies; missing preconditions were not product defects.
- Review found overbroad loopback mocking and orphaned Vite on failed startup. Both corrected; eight deterministic harness checks now cover allowed/denied routes and mocked failed-start cleanup, plus the two actual browser flows. Final **10passed34.24s**, `/tmp/e2e_harness_lifecycle.log`.
- README now lists the actual Node/frontend/Chromium prerequisites and intentional legacy-script quarantine. No auto-install, runtime feature changes or real localhost API writes.
- Separately, the full72 mocked frontend browser scenarios pass after the application fixes,112.311s captured wall, `raw/frontend-patched-mocked-e2e.json`. Their temporary audit config uses a dedicated strict port and refuses server reuse; API behavior remains mocked, not production proof.

## TEST-FIXTURE-02 — Exercise the real network-membership fallback

An isolated native PostgreSQL 15.15 cluster (loopback-only, fresh synthetic databases) enabled previously skipped Operator/finance/journal tests without touching the broken Docker store. The fixed `3fadbabd` archive ran 22 files: **704 passed, 4 failed in 54.71s** (`raw/native-pg-operator-previously-skipped.json`). All four failures were missing network schema in the journal fixture, reached after direct membership revocation; they are fixture defects, not demonstrated production authorization defects.

The journal fixture now applies canonical network/business-link and network-membership migrations. Five additional real-SQL cases check active manager/member, viewer, revoked membership and a different network; denied writes create no journal record. Existing PermissionError/HTTP403 assertions are unchanged. Independent review approved the test-only patch. The three affected files reran: **79 passed, 5 third-party deprecation warnings in 10.32s**, capture exit0 in10.958s (`raw/native-pg-journal-network-green.json`). This is PG15 evidence, not a replacement for production PG16 or the still-incomplete full backend run.

The complete same 22-file selection then reran from the same fixed archive with only the committed journal fixture replaced: **713 passed, 5 warnings in 52.89s**, capture exit0 in53.629s (`raw/native-pg-operator-fixture-green.json`). This isolates the causal test-schema correction; it does not include the subsequent finance-RBAC runtime changes.
# 19 September continuation: measured comparison and access regression coverage

- No application/runtime code changed. Existing approved cleanup restored
  native-test headroom; current Docker image remains blocked by measured peak
  disk requirements, not merely an arbitrary start guard.
- Executed the previously prepared v8 controller proof (10cases), then the
  actual paired five-flow comparison (750requests+150invariants per revision,
  all passing;552.856456s). Mixed tail changes are retained in report04;
  no general speedup or production-capacity claim.
- Added direct/network queued-actor membership revocation/deletion coverage in
  `tests/test_compiled_run_claim_pg.py`. Existing implementation correctly denies
  access; this is a regression-coverage gap, not a newly fixed vulnerability.
  Independently reviewed;18targeted/adjacent checks pass, no leftover test schemas.
- Strict secret delta272..5b9:7commits, zero findings,1.546069s. Historical
  revocation, image-layer and log checks remain separate.
- The later native6 browser attempt failed in process supervision before any
  test/archive/DB phase. Its8.500341s capture is retained, not counted as six
  passed tests. No product-code fix or source defect is inferred from this.
