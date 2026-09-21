# Residual risks — working register

Latest 21 September, parent 6ac6dc: SEC-PARSEQUEUE-REASON-01 is locally corrected
only at the validator normal-terminal/retry reason boundary. Final 13-case
immutable comparison is 8 assertion failures / 5 passes to 13 passes; final broad
128 passes + 4 subtests and independent review do not establish all worker-error,
queue-retention, database, image or deployed confidentiality. Raw retry input
is intentionally in-memory only for legacy classification; proxy/direct-DLQ/
CAPTCHA/handler/warning writers, historical rows/artifacts and cleanup remain
open. Disk 4114304 KiB is below 10 GiB and native aggregate/restore preparation
remains denied. Whole readiness FAIL and AC1–9/11 FAIL/AC10 PASS are unchanged.

Latest21September, parentd8631fec: SEC-APIFY-IPC-01 and REL-APIFY-IPC-01 are
locally FIX_PROVEN for named raw IPC avoidance and the synthetic ~680KB
Queue/join timeout. Final immutable-parent4fail/current11pass plus guarded
broad93pass +4subtests support only this transport boundary. Anonymous temporary
files do not guarantee OS-child death, remote actor cancellation, secure erase,
or removal of old artifacts. Existing raw artifacts remain outside scope.

The next concrete source-only candidate is `_validate_parsing_result` reason
text persisted into `parsequeue.error_message`, then shown to scoped Operator
and superadmin readers. It is not reproduced or fixed. Whole readiness remains
FAIL: AC1–9/11 FAIL and AC10 PASS. Native aggregate/restore remains denied and
disk is below the10GiB image floor; no browser login overrides those constraints.

Latest21September, parentb9cb7dea: UX-AGENT-REQUEST-SCOPE-01 is locally
FIX_PROVEN for selected detail/review request identity/order and the ten-case
contract. Final824frontend tests/139files and bounded independent review pass.
This supersedes the previous checkpoint's specific primary-detail/review race,
not every async path. Registry list refresh, separate prefetch/cache reads,
integration/source loaders and mutation/run-completion races remain outside
this correction. Complete real-view/API/business-switch/create/save matrices
and deployed behavior are not certified.

One existing lint warning and fixture/build diagnostics remain. Raw functional
Apify IPC persistence in a debug bundle and normal validation-message queue
persistence are source-only follow-up candidates; no new causal proof or fix
for them is included here. Original backend/native/restore/image/real-API/demo/
CI/secret-lifecycle and whole-readiness gates remain unchanged.

Disk4176000KiB after validation is below10GiB Docker floor. Read-only inventory
does not prove the cause of fluctuation or authorize deleting dependencies,
evidence, volumes or Docker.raw. Native aggregate/restore prep remains denied
pending renewed scoped authority. Browser login does not override these gates.

Latest21September, parentbd487501: UX-AGENT-SCHEDULE-01 locally FIX_PROVEN for
the five-case schedule hydration contract; full frontend814/138 and bounded
review pass. Live browser observation was read-only on three routes, with unknown
deployed revision; the fix is not deployed. Pending-save, business-switch,
create-wizard and empty/partial contract matrices lack comprehensive dynamic
coverage. Existing broader detail-loader races are not claimed fixed.
One existing lint warning and fixture/build diagnostics remain. No new current
backend/native/restore/image/real-API/demo/CI or whole-readiness acceptance.
Production mutation and denied native prep authority are not granted by login.

Latest21September, parentc587b20f:39legacy leaf value-bearing console sinks and
the Apify trace writer/actor-error print are now locally corrected with86pure
passes and bounded review. V2 status-reader compatibility is included. This
supersedes the particular service/leaf items left open by the previous package.

Remaining P1/privacy boundaries: other worker logs and persisted queue/proxy
errors; functional raw IPC storage/access/retention; raw invalid-input/returned
errors; legacy or absent/corrupt-trace status fallback; untouched old artifacts
and deployed code. V2 preserves stage timeline but only latest payload shape;
the timeline remains uncapped. Fixed selectors and numeric parser metadata stay
observable intentionally. No secret-lifecycle clearance:46history/treeUNKNOWN
and592classified access-material locations unchanged. Disk6264568KiB below10GiB;
native aggregate/restore permission pending after denial. Whole readiness FAIL.

Latest21September, parent5ef5ba7e: five worker diagnostic file writers and
related error/normalization prints, plus four legacy orchestration prints,
are locally corrected with49pure passes and bounded independent review.
This supersedes the specific open sinks in the older checkpoint below.

Still open: service-level Apify debug files; raw functional IPC storage/access/
retention (cannot simply redact the actual result); legacy leaf logs and raw
invalid-input errors; other worker coverage/errors and persisted proxy reasons;
old artifacts, deployed image and historical credential lifecycle. History
queue46UNKNOWN/592classified access-material locations unchanged. Disk6282956KiB
below10GiB; native aggregate/restore authority pending after denial. No data,
production, Docker, cleanup, push or deployment action; all-project FAIL remains.

Latest21September, parentfdbabac4: remaining unknown queue is45history+tree11=46.
Seventy additional exact nonsecret proofs do not clear592historical provider/
access-material locations or10tree access components. Validity, privilege,
expiry/revocation and exact22commit counter membership remain unresolved.

SEC-WORKER-PARSER-LOG-01 locally fixes six console sinks, with immutable-parent
RED5/current34passes and independent review. Raw persisted proxy error reasons,
normalization logs, worker debug writers, legacy scraper diagnostics and old
files/logs remain open; no global confidentiality or deployed-fix claim. The
supported legacy parser source candidate is the next reproduction target.
Fresh disk6278596KiB (~5.99GiB) is below10GiB build floor. Native aggregate/restore
prep still needs renewed authority after denial. No DB/provider/production,
Docker/cleanup/push/deploy action occurred; original whole-project FAIL remains.

21 September, parent074ee5a0: the previously open raw console interpolation
within `parser_interception.py` is now locally corrected (SEC-PARSER-LOG-01).
Final29 pure checks and source review do not certify BrowserSession, worker,
HTML-scraper dependencies, CLI raw result output, raw error return data,
historical logs/files, full browser flow or production. Diagnostic details are
intentionally reduced; static events and counters retain phase visibility.
No native aggregate/restore, image, hosted CI or complete demo gate is promoted.

At that checkpoint the history queue was115history+tree11=116unclassified/UNKNOWN. Only four
static content identifiers were cleared in this package. Rows684/686 remain
unknown credential/default material; no live validation, rotation or expiry/
revocation proof. Their current blobs differ, which does not prove the matched
values are absent elsewhere. Earlier dated counts below remain historical.

21 September, parent bf277dbf: 572 historical debug findings are now bound to
four provider fields (249 distinct values), not declared non-secret or revoked.
120 history/tree findings remain unclassified/UNKNOWN. All previously confirmed
privileged/provider access lifecycle gates remain open.

SEC-DEBUG-BUNDLE-01 locally minimizes new parser file artifacts; its opt-in is
still disabled by default. This does not erase old bundles, prove filesystem
ACLs/retention or sanitize all existing console messages (raw URL/title/address
and exception diagnostics need a separate pass). Full parser/browser/image and
deployed revision proof remain absent. Whole readiness stays FAIL.

21 September, parent08c383e1: tree sidecar leaves692unresolved=691history+1tree;
ten additional historical Google Docs resource-access URI components are not
classified safe by default expiry.31tree rows are verified non-secret. New
SEC-BUILD-CONTEXT-02 fixes a source-config gap admitting ignored provider-response
artifacts into Docker context;14static checks do not establish fresh/existing
image-layer absence. No provider URL/key was tested or revoked and no artifact
was deleted. Graph/scanner counter semantics are known; exact22membership is not.
Native aggregate/restore authority,10GiB image floor (~6.06GiB available), owner
credential decisions, prior unsafe-reset INCONCLUSIVE effects and wholeFAIL persist.

21 September, parent7cf0cd24: frozen local-ref scans completed with711history+
42tree candidates, not clean.20priority locations corroborate known service-role/
Wordstat material and distinguish anon claims; revocation unknown.733matches and
3117selected/3095scanner reconciliation stay open. No automatic false-positive
clearance, key testing, history cleanup or release approval. Existing operational,
permission/image/unsafe-reset risks and wholeFAIL persist. Exact scope: all-refs notes.

21 September, parent `7fd95caa`: the locally reproduced incomplete draft-review
confirmation mismatch is corrected, with 26 targeted checks and quality/build
proof. Current prop completeness is not backend identity/freshness or deployed
proof. Cumulative source review reports retain explicit coverage/limits and a
withdrawn network-parent false positive; they do not close final all-DoD review.
Native aggregate/restore preparation permission remains pending after prior
denials. Current Mac free space 6,654,180 KiB (~6.35 GiB) remains below the 10 GiB
image floor. Full backend, current image/browser/demo/performance and historical
unsafe-reset INCONCLUSIVE effects remain unchanged. Whole-project FAIL persists.

21 September source/dependency checkpoint at `334c9d4b`: 101 committed-source
matches and seven branch-delta matches are classified non-secret, not ignored.
Zero current npm advisories and complete license declarations do not clear
historical credential revocation, legal entitlement or release-image/OS/native/
layer/log gates. AC7 now needs a paired measurement of the changed content
path; old timings remain revision-bound. Aggregate/restore preparation still
await separate permission replies, disk remains below the 10 GiB image floor,
and prior unsafe-reset effects remain INCONCLUSIVE. Overall FAIL is unchanged.

21September afterd72475e3: UX-JOURNEY-DETAIL-LOAD-09 is no longer source-only.
Expanded8causal failures are corrected;104targeted checks, types/lint/build and
199JS integrity pass. Only current URL intent can update focus; loss of access
clears it while same-intent transient errors keep edits. No native browser,
real-API or cross-tenant-write proof. Final full check is recorded in COMMANDS.
The older candidate wording below is historical. Real LanguageProvider remount,
image/full-backend/browser/demo/original DoD gates remain; wholeFAIL, existing
denials and prior unsafe-reset INCONCLUSIVE effects are unchanged.

21September after544fbe96: UX-JOURNEY-ACTION-SCOPE-08 has causal local proof and
a bounded correction, superseding the source-only status below.105focused/
adjacent checks pass; new-action form and late command/clipboard continuations
are isolated. Same-id refresh preserves edits. This neither cancels a started
backend action nor establishes native browser/provider/production behavior.

UX-JOURNEY-DETAIL-LOAD-09 remains a source-only P2: the Focus parent can accept
an obsolete same-business action GET after the query selects another action,
or keep the old card clickable while the next one loads. Its request-generation
and retry tests are the next step, not part of the card fix. Dashboard business
switches remount Outlet; no cross-tenant write/leak established. The separate
real LanguageProvider loading/remount gap also persists. Full771frontend tests pass;
original wholeFAIL, aggregate/restore denials and unsafe-reset INCONCLUSIVE effects
unchanged. Last disk6,893,116KiB (~6.57GiB) is below10GiB image-build floor.

21September after7c080d11: shared JourneyActionCard Russian chrome is locally
corrected for ten languages;91focused/adjacent tests pass. UX-LOCALE-07 remains
partial across the product: raw API/business copy is deliberately not translated,
other unkeyed strings/native browser/RTL/mobile are not certified. Direct test
context updates do not cover real LanguageProvider loading/remount and draft
persistence across it. UX-JOURNEY-ACTION-SCOPE-08 is a separate source-only
candidate: an unkeyed supported next-action/content-cycle transition may retain
old form state; no cross-business/entity write or causal test proven yet.
Original wholeFAIL/denials/prior unsafe-reset INCONCLUSIVE effects persist.

20September after191488ba: UX-CAMPAIGN-CONSENT-03 now has causal UI proof and a
local correction, superseding its source-only status below. Forty targeted UI
and288guarded backend checks pass; canonical saved review is required before
consent. This does not establish native provider effects, new-build browser/
mobile accessibility or production rollout. Same-lifetime request ordering and
edits during pending requests are not globally certified. Original readiness
gates, aggregate/restore denials and unsafe-reset INCONCLUSIVE effects persist.
Latest measured disk6,851,904KiB (~6.53GiB) remains below10GiB image floor.

20September after03ef38f6: UX-CAMPAIGN-SCOPE-02 is locally corrected with causal
old-response/busy evidence and26 focused passes. This supersedes the older
source-only scope note below, not its historical capture. Requests already
started can still complete on the server; same-lifetime request ordering and
new-build browser/current image evidence are not covered. Separate candidate
UX-CAMPAIGN-CONSENT-03: unsaved preview B can be shown while approval targets
saved A; source-traced, not causally tested or fixed yet. Temporary operator
practice: save and review the selected saved version before approving. No
claim of automatic provider send or backend consent bypass from that trace.

20 September adjudication afterca0c3d36: the prior paragraph's same-contact-ID
value-mutation concern is NOT a reproduced supported-flow defect. Normal
contact writers create a new UUID for a changed normalized address and never
update that field on conflict. Arbitrary DB/future-writer drift is only
defense-in-depth debt. Likewise, non-boolean capability bypass has no supported
writer; no speculative policy/schema hardening was added. Detailed source
traces: evidence/recipient-review-notes.md. Native race fencing and broad
AI-APPROVAL-BINDING-03 remain separate open scopes.

UX-CAMPAIGN-RECIPIENT-01 now has local projection/display proof:288pure backend
and6targeted UI passes, independent bounded review PASS. New-artifact browser,
native JOIN and late-response UI race are not certified. Late old-workstream
campaign/preview responses remain a separate source-only candidate; they do not
automatically issue a send. Current disk4,853,324KiB (~4.63GiB), below10GiB
image floor. WholeFAIL, nine foreign paths, aggregate/restore denials and prior
unguarded-reset INCONCLUSIVE effects remain; no push/deploy/cleanup.

20 September generic campaign dispatch checkpoint (parent7b41e8a9):
OUTREACH-DISPATCH-IDENTITY-01 has causal5fail/1pass and final138pure passes.
It binds approved body copies and current preflight provider arguments, but
does not snapshot a contact row's value at original human approval. That
historical concern is adjudicated above, not a supported mutation bug.
Native transaction/race fencing, broad binding03 and
production rollout remain open. No readiness score or whole-goal promotion.

20 September draft-identity correction (parent79d7b227): exact reviewed draft
content/contact/IDs now have bounded313mocked backend and16targeted UI proof.
Native locking/concurrency, the later separate queue/dispatch mutation window
and broader finance/tool approval identity remain open. Versionless pending
draft approvals intentionally require rejection/repreparation; do not migrate
or auto-approve them. No production rollout occurred. Latest local disk is
4,881,460KiB (~4.66GiB), below10GiB image floor. OverallFAIL remains unchanged.

20 September later dependency checkpoint: the current private macOS133-package
set has now passed a strict PyPI advisory scan with0skips/0returned advisories,
not parity alone. Exact installed/audited maps match. License declarations are
inventoried, but owner entitlement/compatibility remains unverified. This closes
that local advisory-evidence gap only. Current Linux image/OS/native/AMD64/bot,
layer/log scans and historical credential revocation remain open. No readiness
score changes. The preceding reset packageaf351060 has16guarded pure passes;
its earlier unguarded worker runs still have INCONCLUSIVE possible effects.

Latest checkpoint supersedes stale capacity/dependency holds below. Private clean
Python parity covers 133 distributions; `5cc7c0cd` migrated and 4,910 tests
collected. The initial full aggregate remains not green (4,886 pass / 9 fail /
1 error / 14 skip); corrective evidence supports 4,903 unique non-provider cases
across runs, not a single green aggregate. Seven live-provider skips remain
intentional. Later Today frontend evidence is 667/130, followed by a test-only
query correction and 31 focused passes, TypeScript/lint, builds and integrity.
Source `a231abb8` also has separate reviewed 116- and 467-test pure access/admission
suites; no later full backend aggregate exists. Free space is ~5.7 GiB, below
the 10 GiB image floor. V2 has
not executed: its first script write was safety-rejected; root's guard/probe are
static-PASS only. New asynchronous permission is pending for preparation and an
isolated full test, not restore/deploy/deletion; restore approval remains separate. See
[COMMANDS.md](COMMANDS.md) and [HANDOFF.md](HANDOFF.md); older details are
historical and do not promote readiness.

Current local security fixes do not prove native concurrent revocation,
provider delivery or full tool/role coverage. Run/type approval matching is not
immutable target/payload binding; AI-APPROVAL-BINDING-03 remains a static candidate,
not a reproduced normal-flow bypass. The serial runner stops at each pending
approval. Keep manual approval and existing provider snapshot gates; further
binding changes require a supported lifecycle contract and causal proof.
Standalone lifecycle lint retains 33 existing F821 findings from dynamic helper
injection (same count before/after); runtime regressions do not eliminate this
maintainability/static-analysis limitation. No suppression was added.

Fresh independent whole-diff review remains NOT READY overall. Its new media
findings are now locally FIX_PROVEN5cc7c0cd with279 guarded pure passes and
independent review, not native DB/provider/deployment proof. Canonical direct
transport bypasses the ambient proxy; proxy-only assets can fail closed. The
decimal10,000,000-byte remote cap differs from10MiB uploads; five20s per-hop
timeouts and the byte/request caps apply per remote asset, with up to10 assets
under the existing publication limit. There is no separate publication-wide
budget or strict global deadline. Image format
validation and native role-change races are outside this bounded package.
Telegram SEC-WH-02 is an existing
intentional breaking release gate. The runbook now requires coordinated code/
provider cutover and controlled receipt, with explicit approval. No real bot
inventory, token access, rebind or receipt proof has been performed.

20 September update: SEC-SSRF-02 locally fixed4e33587d, independently accepted
with exact149 adjacent passes including25 focused cases. Website fetches now
pin public destinations and revalidate redirects; five per-hop timeouts are
not a strict wall-clock deadline, DNS latency is not certified, and only the
first validated public IP is attempted. Setter-to-reader provenance is source
traced, not an authenticated native-route or real-network proof.

The historical 16.26 GiB capacity observation below is not current. Current
headroom is about 5.7 GiB, so the 10 GiB image floor remains unmet. No production
changes follow from the user's browser login; authenticated Today still shows
mixed locale.

Newest source432f64a0 locally fixes SEC-RBAC-10 with19focused/92overlapping
adjacent pure passes and independent review. Business-profile PATCH now checks
write roles at its write connection, preserving permitted initial reads and
personal examples. These fakes do not establish native persistence/grants or
live concurrent role-revocation safety. Membership changes after the check or
before the post-commit response read remain outside this bounded proof.

Prior source3ee2279a adds three independently reviewed local packages:
Telegram chat write admission78102124 (12focused/101adjacent), legacy generation
72fd27a9 (21/71) and Alembic-owned news schema3ee2279a (23/73). These overlapping
pure tests use real handlers/helpers with controlled SQL/provider boundaries.
They do not prove native PostgreSQL grants/catalog, durable rollback/commit,
actual billing, live Telegram, current image or production. The full mixed
Telegram chat is now writer-only (D-039), a deliberate compatibility change.
User-owned NULL-business examples remain personal/global, not reassigned data.
Other legacy endpoints may still execute DDL; prompt-template debug output is
not covered by the raw-provider-output privacy fix. No platform-wide closure claim.

Historical19September disk observation was1,819,548KiB (~1.74GiB); that hold is
superseded by the20September update above. No cleanup or apps stopped. Prior
direct Operator gatee3e8fbff retains its14/20pure proof. Current-source aggregate
and current image still need validation; the Today build/full-unit hold was
subsequently resolved as recorded above.

Newest7c374f1f locally fixes only the static UX-LOCALE-07 subset, with93focused
tests/TS/lint/independent review. API-origin Russian operational text remains.
At that historical checkpoint, Today build/integrity/full units had not run:
preflight1801168KiB free failed the2097152KiB floor and swap allocation rose10→11GiB.
No automated memory cleanup, app shutdown, production action or delete occurred.

Latest19September checkpoint: SEC-RBAC-07 is locally FIX_PROVEN inbe1b1a95,
164native/adjacent passes plus independent review. The current-image/production
boundary is still unverified; concurrent role/topology changes during generation
are not transaction-fenced or proven safe. Frontend67169692
has620unit/51focused/TS/lint/build evidence, no new browser or release-image proof.
The two exact demo GET gaps now have a reviewed v3 pure-policy fix (5pass);
it has not run a browser/server and still pins the older39frontend artifact.
Read-only production Today observation confirms separate UX-LOCALE-07 mixed copy;
the review/publication locale fixes do not close that Today/API contract debt.

Updated19September2026. These are remaining risks or verification gaps, not
newly demonstrated exploits. Fixed local findings and their evidence remain in
[02-audit-backlog.md](02-audit-backlog.md) and [06-change-log.md](06-change-log.md).
The audit branch has not been deployed; local proof is not production proof.
Committed backend application source has a frozen6eec aggregate PASS:
4751passed/7intentional live-provider skips/6warnings652.30s, capture659.230650s,
no timeout/truncation; owned resources checked after completion. Later seed-only
commit1e955718 has separate2focused/44overlapping adjacent passes and independent
review. The exact missing retained synthetic artifact is now applied and its
current-frontend drawer text observed; full presenter rehearsal remains open.
The earlier managed-picker stall/deadline and drawer exit143 remain historical
failures. TEST-DEMO-02 now fixes the preview lifecycle with causal/actual-helper
proof, and v2 current-UI stop finalizes cleanly. Finance still never reaches
preview/apply: native fallback is tool-denied. Two exact read gaps remain;
disk-video upstream403 is feature-disabled, not a proxy miss. Root verifies
unchanged finance/artifact digests and closed resources. Concurrent source/test edits appeared
during the stall and are not certified by the frozen aggregate; see HANDOFF.
Frontend39aeeff9 now has616/128files unitPASS309.65s, checked types/lint/build,
and local reset-token-log regression/asset proof. The locale browser checkpoint
uses the preceding993artifact and historical synthetic backend; no current
wholeimage or all-page browser claim follows from the newer unit result.

Latest backend source is7bb9f996: independently reviewed callback alert rotation
passes29focused tests in12.04s, with no residual native test schemas. This does
not itself recertify the full backend/image; the separate6eec full backend run
above now covers this source, while image proof remains open. Review-locale frontend work is locally
focused FIX_PROVEN and has a narrow three-viewport RU/EN/EL browser result against
historical synthetic staging, but does not establish all-locale or whole-workflow
runtime coverage. Previous runtime source is4f333aa7, the callback package.
Its final25focused tests and separate73API/schema/native tests pass; the sets
overlap. They do not re-certify the full backend,117browser cases or image.
Earlier additions are locally reviewed272794a4 (104stored-role/subscription
checks),3ac13d87 (11fake-command CI contracts), and a00ac558 (13actual Compose
render/startup contracts). These respectively strengthen mutation admission,
isolated CI definition and opt-in migration/image ownership. Full272backend
passes4728/7intentional provider skips/6warnings656.63s with independentAC4PASS;
that source's native browser passes117/117 and bounded HTTP240/240 plus frontend
60/60 observations have independent scoped PASS. Final image and hosted CI
execution are not proven. Do not treat these packages as a closed release gate.

TEST-E2E-04 removes a two-journey console-filter blind spot with21pure
regressions, scoped strictTS/lint and independent review. Local space is now
about4.52GiB at the latest check after approved cleanup and bounded verification; the first native6 retry failed in its
process controller before tests. A minimal process-only reproduction confirms
the nested topology limitation. The reviewed sole-owner retry now passes6/6
in22.0s, capture48.938396s, with independent DB/process cleanup verification.
Historical117results retain their original limitation. Docker peak-plus-reserve remains
unmet. No production, image or readiness score is promoted.

New scoped evidence: partial managed-browser demo verifies synthetic finance
preview/apply/duplicate history but not the intended partnership reason or a
paced complete rehearsal. OPS-CALLBACK-01 has causal real-PG RED and reviewed
local finalGREEN25/25, including10 native recovery/race/tenant cases and6shell
cases for no implicit recovery plus incident snapshots. Its remaining
release/image proof is separate; no production callback is claimed recovered.
UX-LOCALE-05 is locally fixed with focused RU/EN/EL proof and all-ten-locale
source keys. Its browser confirmation now passes3/3 only against the historical
synthetic backend/current built frontend; full workflow, all locales, current
backend/image and deployment remain separate. See backlog02.

| Risk / evidence | Priority and impact | Likelihood / temporary protection | Required next step |
| --- | --- | --- | --- |
| Alert scan rotation is process-local |P2 operational limit under frequent restarts; progress is not durable/shared|Lexical-prefix starvation is causally fixed in7bb9f996 and verified by101-tenant test; every worker restart resets its own cursor|Current-image verification, then assess durable/shared scheduling only if restart/topology evidence warrants it; no live incident or global-fairness claim |
| Deployment smoke still has ordinary mutating phases |P2 operational scope; calling it is not a read-only diagnostic|Implicit alert-triggered replay removed and tested; nested capability/outbox smoke still creates actions/dispatches normal pending/retry|Use specific read-only metrics for diagnosis; require separate authority for full smoke, manual replay and deployment |
| Historical privileged credential exposure; offline scan confirmed old provider keys, revocation unconfirmed |P1 before production; former credentials might still authorize access|Current validity unknown. Do not use/test/publish old values; owner confirmation requested|Authorized owner/provider revocation evidence and separately approved history policy; no unilateral rotation/rewrite|
| Intended release artifact still needs the reset-log fix verified |P2 before production; older cookie-build asset contains raw reset email/token log literals|Local source regression and rebuilt local artifact are fixed; synthetic tests do not demonstrate a real-secret event or bearer-token exposure|Verify the exact release image/artifact has neither raw log literal; do not probe real tokens|
| Reviewed auth/webhook/role/SSRF patches remain local |P1 release gate; intended protections are not certified live|Deployment deliberately not authorized by this audit; retain explicit boundary|Approve an exact release, provider webhook rebind/configuration where required, then verify live flow; no broad dirty-tree sync|
| App version constraints and base pins lack final image proof; apt/artifact hashes and bot/target-runtime closure remain |P1 before production; supply-chain/build drift or untriaged advisories|Exactb43 audit104packages/0skips finds only pip24.0;26.2pin and app101constraints plus3tools. Node/Python base indexes now pinned with ARM64/AMD64 metadata and14static contracts|Build/version/re-audit and OS/native/image/log scan; index availability is not an AMD64 build. PyMuPDF license basis awaits owner confirmation, not a violation claim|
| Production backup recoverability not rehearsed |P1 before production changes; possible recovery failure|Independent local synthetic full-schema/data restore passes; production datasets/backup transport/permissions differ|Under separate authority, verify an actual backup in an isolated restore target before schema change; never overwrite live DB|
| Wider mutation-role coverage incomplete |P1 investigation; potential unauthorized mutation|Several finance/blueprint/Operator chat boundaries reproduced and fixed; remaining candidates are not confirmed bugs|Finish targeted real-DB negative matrices; preserve tenant and stored-role checks|
| SEND-AMB and approval binding are locally fixed but final release proof remains |P1 release gate; deployed old approval can still be insufficiently bound|Reviewed13c1f36a main252pass plus separateviewer9pass cover frozen target/account/media, drift and uncertainty; receipt reconciliation has scoped120browser proof|Final combined image/aggregate, then separately approved rollout. External object/URL byte immutability is not established; no exactly-once claim or blind retry|
| WhatsApp uncertain outcomes need reconciliation |P1 integration limit; admission is not exactly-once delivery|Durable duplicate admission and ambiguous-state visibility fixed locally|Explicit operator reconciliation/provider evidence; do not reset ambiguous admissions to force a resend|
| Local Docker had filesystem I/O incident; old volumes not certified |P2 audit infrastructure; old verification invalid or local state damaged|Approved no-reset restart and fresh PG16 storage/restart/restore/checks pass; old volumes not reused|Do not erase/repair user volumes. Maintain headroom, preserve dumps and stop heavy work on I/O errors|
| Node engine mismatch is fixed locally; broader supply-chain gap remains |FormerP2 reproducibility finding|ba891be4 and cleanf0cc Node22 bothfrontend image builds pass55.386s; actual nonroot/offline smoke passes3.721s|Final image/dependency scan is separate; no broad upgrade or production claim|
| Readiness integration pending; migration startup ownership still coupled |P2 operations; unhealthy app may accept traffic or restart implies DDL|Reviewed52292e6e adds bounded read-only `/ready`,24native/route/CLI/schema tests pass; `/health` unchanged, no image/deployment proof yet|Verify endpoint in frozen image, then separately authorized rollout; preserve deliberate migrator/run modes|
| Final combined image and whole-diff closure incomplete |P2 release gate; selected green evidence may miss integration regression|Frozen6eec full backend4751pass/7live-provider skips; earlier272native117browser pass; frontend591units/72mockbrowser/TS/lint/build stages plus artifact proof pass without relabeling original exit1. Historical120includes compiled runtime. Fresh272whole-diff review found no additional reproduced P0/P1 in bounded coverage; original verdict remains FAIL|Final combined image/compiled-runtime proof, remaining scoped coverage and independent closure; do not sum overlapping suites|
| Production-capacity evidence incomplete |P2 capacity; bounded synthetic latency is not capacity|50-sample before/after distributions retain baseline errors; current272HTTP240/240 over64.28s includes10resource snapshots. Frontend60/60 observations use historicalf0ccbackend/unchangedfrontend. All have scoped review;8user earlier run retains login429 failures|Realistic server/queue capacity remains; low-load/tiny fixtures and10browser samples per group cannot establish production limits or speedup|
| Demo and broader error/large-data/slow-network accessibility coverage not rehearsed |P2 demo; presentation may encounter unsupported/incomplete paths|Seed1e955718 has scoped stage insert/repeat-preservation and drawer proof. Historical exit143 is fixed with causal/actual v2 lifecycle proof. v3 exact GET policy passes5tests but has no server/browser run; file input remains unexercised|Use a permitted picker and explicitly pinned current artifact, then complete the10–15min rehearsal; keep scope/confidentiality boundaries and do not repeat the denied/stalled tool route|
| Large workspaces and remaining structural debt |P3 after correctness; maintainability cost|Scoped fixes preserve existing modules; no architectural rewrite without benefit|Use measured churn/runtime evidence to select the next small module extraction, with existing regression coverage|

The controlling release decision is the original task's Definition of Done,
not the existence of these reports. A documented gap is not automatically an
external blocker or an acceptance-criteria pass.
