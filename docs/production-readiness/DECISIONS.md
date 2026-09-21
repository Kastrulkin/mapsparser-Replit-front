# Readiness decisions

## D-081 — Pin provider-issued upload destinations without truncating VK JSON

Treat the returned upload URL as untrusted. Use a dedicated bounded HTTPS POST
with validated public-IP pinning, original TLS identity and explicit proxy
CONNECT. Keep fixed VK API routing and existing callback/media transports.

Options: URL validation alone leaves a second-resolution race; reusing callback
POST truncates valid upload JSON at1,000 characters and loses explicit proxy
routing; a bounded dedicated helper preserves those contracts (selected).
No new dependency or business-policy change. Compatibility risk remains for
real TLS/proxy behavior, not proven by mocked construction tests. A verified
provider-host allowlist is a separate decision; public pinning cannot prevent
transfer to a malicious public host. No allowlist was guessed.

## D-080 — Separate proxy diagnostic text from health-policy input

SEC-PROXY-DIAGNOSTICS-01 uses a finite projection for all preflight-derived
map/review diagnostics and a fixed code for proxy-stat write exceptions.
Keep the original raw preflight reason only in the internal health-policy path:
its fatal-token checks and SQL/counter/cleanup behavior are unchanged.

Options: regex redaction alone misses arbitrary private text; projecting the
preflight return itself could change the circuit breaker; projecting at the
actual diagnostic sinks preserves policy while removing untrusted outward text.
The selected helper retains known statuses, bounded HTTP codes and known
request class names, otherwise a generic failure. The tradeoff is less free-form
diagnostic detail. This is not a sanitizer for every worker error producer.

## D-079 — Project parser failure reasons at the persistence boundary

An error result may contain provider-controlled code/message text. Its raw
content is needed transiently for legacy retry classification, but it need not
be stored or logged as the terminal validator reason. Project error-result
reasons through the local finite taxonomy and use the same finite projection in
normal terminal/retry diagnostics; retain the raw value in memory only for the
existing retry alias/legacy classification path. Preserve controlled reason
codes, retry caps, billing and parser-result behavior.

Three options were compared: regex redaction (misses arbitrary PII); terminal
projection only (leaves retry/native-fallback diagnostic leakage); and finite
validator plus retry projection (selected). This is not a universal worker
sanitizer. Proxy/direct-DLQ/CAPTCHA/handler/warning writers and existing rows
remain separately scoped, as do deployed and historical artifacts.

## D-078 — Keep functional Apify result transport private and nonblocking

`apify_result.json` was functional child transport, not expendable diagnostics:
redacting it would risk result, billing and validation behavior. A raw Queue
payload can instead deadlock a large child result when the parent joins before
draining it. Use an anonymous POSIX temporary file for the private result and a
small Queue readiness marker; reject legacy path spoofing and retain controlled
timeout/empty-transport errors. Preserve parser result, retry, card and
provider-cost contracts.

Compared three options: retain raw Queue delivery (no named persistence but the
reproduced join deadlock); use a private0700 named temporary directory (larger
path/retention/cleanup contract); inherit an anonymous TemporaryFile through
the existing POSIX fork (selected, no durable path and small queue marker).
No new dependency, schema or process-start architecture is introduced.

This reduces named durable raw IPC retention and fixes the demonstrated local
Queue/join deadlock. It does not promise that terminate/kill always ends an OS
child, cancel a remote actor, securely erase filesystem blocks, or remove old
artifacts. FD0600 and bounded cleanup belong to the parent implementation;
quality/precommit and original release gates remain separate.

## D-077 — Bind selected reads to identity and request order

An approval button must consume details belonging to the employee currently
shown. Clearing state when selection changes is insufficient: older requests
can still resolve later. Guard both primary detail/review state and per-employee
cache with request identity/order; reject mismatched detail payload identity.
Use a monotonic business-scope generation so resetting revision maps cannot
make an old response current again. Keep synchronous select-plus-load callers
and functional run-tracking setters compatible; reselecting the current employee
must remain a no-op. Registry-derived fallback selection must clear old review.

Keep this patch local to selected reads, not a refactor of every async action.
Ten final request cases distinguish seven parent failures from three positive
compatibility controls; five existing schedule tests stay green and the stale
schedule test now also requires the correct detail identity. Real approval
handler routing is tested only against a mock POST. No server authorization
bypass, cross-tenant disclosure or deployed correction is inferred.

## D-076 — Hydrate the selected schedule without erasing in-flight edits

Scenario and Settings must read the same candidate-or-active version. A candidate
without schedule must not silently borrow the active version's schedule; use the
backend-compatible legacy fallback. Match business and blueprint identity before
applying details, and distinguish server hydration from user edits per field.
Save completion may clear dirty markers only for the same hydration object and
unchanged edit revisions, including A→B→A selection changes. This does not change
approval or active-version behavior.

When final regression bytes change, preserve previous captures and rerun against
immutable parent bytes through a narrow verified load hook, not a working-tree
reversal. Authenticated production observations are not proof of the local build.

## D-075 — Preserve diagnostic consumers without retaining provider content

Trace hardening must inspect readers as well as writers. The Apify stage trace
feeds one legacy status-message helper; version2 must preserve stage identity
and actionable localization without falling back to raw technical errors.
Keep old-version behavior compatible and identify the remaining absent/corrupt
trace path separately. Do not change provider execution or billing data.

On append, reproject previous entries to fixed event and validated timestamp
metadata so raw history is not reserialized. Only the newest event retains a
bounded payload shape; the timeline is intentionally not capped by this patch.
This trades forensic detail for privacy, not a general retention policy.
No existing artifact cleanup, deployment or production action is implied.

Test inventories must cover the actual changed sinks and use semantic anchors,
not source line numbers. Preserve representative parser return values as well
as proving marker omission; disclose any gaps caught during review.

## D-074 — Separate diagnostic storage from functional parser transport

A file in a debug directory is not necessarily expendable diagnostics.
`apify_result.json` carries the actual subprocess result and cost metadata;
preserve its protocol/data while separately auditing storage access/retention.
Shape only diagnostics-only copies, never the in-memory payload used for
billing or validation. Version the changed diagnostic JSON format, use the
existing bounded shape helper, and keep writer failures value-free too.

Preserve immutable causal evidence while correcting harness selectors/scaffolds.
Bind the baseline to parent bytes and final test bytes; do not hide initial
harness errors or call fixed-event tests a real browser/integration proof.
Four legacy orchestration sinks do not certify its numerous leaf extractors.

## D-073 — Bind positive classification and regression evidence to exact bytes

Missing historical artifacts are UNKNOWN, not safe digests. A successful empty
literal/full-tree Git listing establishes absence; other Git errors fail the
proof. Do not emit unbounded historical JSON keys as reference paths. Clear
only exact file-digest equality, explicit placeholders or bound record identity
semantics; retain unsupported fixture/pack/credential examples as UNKNOWN.

Replace worker console interpolation with fixed events, retaining parser data
and retry/persistence contracts. This limited privacy patch does not sanitize
all worker diagnostic files, queue reasons or legacy dependencies. Compare the
non-diagnostic AST, force retry success/failure with synthetic inputs, and bind
source hashes to final captures. Never promote an intermediate green after the
source changes. When interim evidence was overwritten, disclose the loss and
produce a fresh parent-AST/current-source pair without reverting shared files;
do not reconstruct purported original capture bytes.

## D-072 — Replace raw log values at each parser diagnostic sink

Historical secret triage must bind argument positions, not only callee names:
an environment variable name and its default are different security contracts.
Keep failed classification evidence and UNKNOWN when exact semantics do not
prove a value nonsecret. A singleton candidate can additionally be checked
against the whole report Match after replacing only the redacted scalar.

Runtime console messages are a separate boundary from opt-in debug files.
Use explicit static events, counts, presence flags and fixed URL categories;
do not introduce a global print override or a best-effort secret-name regex.
Raw exception messages and arbitrary provider keys are not safe diagnostics.
Retain typed errors and application results; reduced forensic detail is an
intentional privacy tradeoff. Debug event location still identifies the phase.

Require causal privacy tests, preserved result assertions, adjacent units and
independent source review. A normalized AST comparison supports the narrow
diagnostic scope but cannot prove external helper, worker or live log safety.
No blanket claim about old files/logs, provider dependencies or deployed code.

## D-071 — Keep provider diagnostics useful without persisting raw content

Field names do not prove that arbitrary provider values are safe. Classify
historical findings conservatively and keep owner/provider lifecycle gates open.
For new parser debug files, retain a bounded schema, lengths/counts and fixed
route/state categories instead of raw values, arbitrary keys, URLs, HTML or
screenshots. This intentionally reduces forensic detail; the core parsing
result remains unchanged. Do not silently enable a raw-content override.

Existing bundles, console logs and deployed images are separate boundaries.
Do not call a file-write regression pass a global log/data confidentiality proof.
Preserve initial failed checks and require independent source/evidence review.

## D-070 — Classify resource URLs by their contract; fence packaging separately

An image contentUri can carry access even when it is not an API key. Preserve
that distinction; documented default expiry is not proof of actual expiry or
revocation. Verify suspected digests against historical source bytes and import
identifiers against the corresponding historical callee. Leave uncertain rows
UNKNOWN. Do not change raw scan outcomes or use counts to imply security clearance.

Git ignore and Docker context are separate boundaries. Exclude the confirmed
provider-response artifact family from Docker without deleting user files.
Static contract tests establish the configuration correction only; image/layer
absence requires a later permitted build/inspection. Keep failed/truncated
diagnostics and exact successful successors distinct.

## D-069 — Separate frozen-ref scanning from security clearance

Use immutable commit IDs plus mapped tree-only blobs; no fetch, historical code
execution or raw matches in tracked evidence. Disable replacement refs and Git
text/filter commands; private raw files, full redaction, scanner exit1 retained.
Selected and processed commit counts are distinct: reconcile or keep coverage
incomplete. Decoded roles never prove signature/validity/revocation or safe RLS.
Preserve unreviewed rows instead of declaring generic matches false positives.

## D-068 — Treat copied Git onboarding commands as a security boundary

Do not recommend plaintext token persistence or credential-bearing command URLs.
Prefer already-configured secure authentication; never inspect saved credentials
or mutate global Git settings to validate documentation. Scope staging and review
the complete index before commit; publication stays a separately approved action.
Verify examples as text and shell syntax only. A documentation fix does not
establish that existing credentials are safe or historically revoked.

## D-067 — Share the review condition between warning and confirmation

An incomplete draft snapshot must not show a recovery warning while offering an
enabled confirmation. Reuse the existing frontend condition in the summary and
both controls; keep rejection available and preserve loading/generic approvals.
Do not duplicate backend freshness/identity validation or reinterpret a disabled
UI control as a security boundary. Preserve exact causal RED and later checks.
Source-only review findings require contract adjudication: the network-parent
candidate was withdrawn because the supported writer deliberately shares IDs.

## D-066 — Separate scanned matches, source proof and release certification

Scan a Git-frozen snapshot, validate every blob against its commit, and retain
raw scanner exit codes. A redacted Authorization-shaped match is not proof of a
credential: inspect a value-free exact-source predicate before classification.
Do not suppress false positives globally or conflate current snapshot/branch
delta with other refs, runtime logs/images or historical credential revocation.

License declarations may be inventoried from frozen lock, same-version installed
metadata and exact-version/integrity public registry metadata; preserve each
source and installed metadata hash. This is not legal compliance or artifact
provenance. Never install/update solely to populate a metadata report. Historical
performance samples retain revision scope: source changes to a timed path require
new authorized paired measurements, not a static claim of unchanged latency.

## D-065 — Keep detail requests and navigation bound to the current URL intent

Key only the selected-action panel by business/action ID; keep workspace children
outside it. Each panel lifetime sequences its GETs, ignoring obsolete completion,
error and finally handlers. Current401/403/404 clears focus;404 means unavailable,
not necessarily deleted. Network/5xx preserves same-intent edits with Retry.
Consume authoritative command next_action once in the destination panel while
canonical GET refreshes; never reuse that seed on revisit. Command navigation
must clone latest committed query parameters, not its dispatch-time snapshot.
Invalidate pending GET before handoff; do not cancel/roll back started commands.
No transport/API/schema or whole-workspace remount is introduced.

## D-064 — Bind action form and asynchronous continuation to business/action ID

Use a keyed inner form for `[businessId, action.id]`, not version, payload,
surface or locale. Supported server paths can merge payload on the same ID
without incrementing version; version is optimistic concurrency, not draft
identity. Same-action refresh keeps in-progress edits and retry identity.
New-action handoff initializes fresh fields, even for the same content entity.
Each layout-effect setup has a distinct lifetime, invalidated on cleanup;
command success/error/finally, upgrade navigation and clipboard continuation
must not affect a later form after unmount. Do not cancel or claim rollback of
an already-started command. Parent detail-load ordering is a separate boundary
and is not repaired by this card change. No transport/API/approval redesign.

## D-063 — Localize action chrome, not business content or command values

The shared JourneyActionCard must read the existing language context for system
controls, instructions, placeholders, generic failure and date formatting. Keep
raw action title/description/CTA, incoming drafts/result text and server Error
messages unchanged; do not infer translation keys from their bytes. Command and
outcome/use-case enum values, approval and retry keys remain language-independent.
Use a typed ten-language copy module, existing primitives and layout. A fresh
empty automation expected-result default may follow locale until edited; preserve
incoming, edited and intentionally empty values across locale changes.

## D-062 — Maton route change is not proven approval account drift

Reject the proposed AI-APPROVAL-BINDING-03 Maton reproduction: the authorized
route-selection writer changes route/integration metadata, but runtime resolves
handler.external_account_id before route.external_account_id. Existing handler A
therefore wins over a changed route B. The traced handler constructor is used
when creating a new blueprint; no supported in-place handler writer was found.
Root checked this precedence and the independent tracer corrected its initial
claim to NO_BUG_PROVEN. Generic binding03 remains an unproven candidate, not a
confirmed bypass or closed security finding. Do not fabricate raw DB mutation
or change approval contracts without a reachable causal case.

## D-061 — Consent requires the displayed saved campaign snapshot

Transient previews and local text/schedule/sender changes are not a review of
the currently selected saved campaign. Block approval/pilot start/resume while
they are present. Save/apply-learning POST returns metadata only: reload the
campaign list and locate that exact returned ID before showing saved content
and enabling consent. Failed/missing reload remains blocked. Explicit discard
or version selection may rebind to the saved snapshot. Do not change API,
backend authorization/preflight, pilot confirmation or safe pause/cancel/reply
controls. Bounded source and targeted evidence review PASS after191488ba;
final wider checks are reconciled in COMMANDS, not production proof.

## D-060 — Campaign UI state belongs to one scope lifetime

Use a keyed private editor for the existing workstream/business/segment inputs,
plus a distinct token for each layout-effect lifetime. A key clears stale
controls immediately; a token additionally suppresses obsolete follow-up
requests and parent callbacks, including StrictMode setup reuse. Check after
every await and before catch/finally writes. An unchanged key preserves drafts.
No new dependency, API payload, consent policy or server-side cancellation.
This fixes cross-scope responses, not ordering of concurrent same-scope requests.
Keep the unsaved-preview versus saved-campaign consent candidate separate.

## D-059 — Show the exact campaign recipient before consent

The owner reviews each message and destination together. Add server recipient
projection to saved and preview touches, using the selected contact UUID and
normalized value; do not infer a different address in the browser. Missing
legacy contacts remain visible with an explicit warning. Preserve the existing
screen, approval, dispatch and schema contracts. Plain React text needs no
new abstraction or HTML rendering. This display fix is separate from a contact
snapshot migration and from the late-request/workstream race candidate.

## D-058 — Reject unsupported security hypotheses before changing contracts

The same-ID contact-value mutation hypothesis is NO_BUG_PROVEN for supported
writers: a new normalized address receives a new UUID; conflict updates never
replace normalized identity. Sender capability truthiness likewise lacks a
supported non-boolean writer. Retain arbitrary-DB/future-writer hardening only
as defense-in-depth debt, not a reproduced approval bypass. Exact source traces
are in evidence/recipient-review-notes.md. No speculative hash/schema/capability
rewrite follows. Native races and the separate broad binding03 remain open.

## D-057 — Dispatch the hash-covered campaign body, not mutable draft copies

Reconcile the preceding ca0c3d36 package: generic campaign preflight must bind
queue/draft/touch identity and all body copies to the approved generated text,
then pass freshly validated provider arguments to dispatch. Keep existing
template, manual-channel and AI-provenance boundaries. Mismatched legacy rows
fail closed rather than silently gaining fresh consent. Pure tests do not prove
native concurrent revocation or actual provider delivery.

## D-056 — Consent belongs to the reviewed draft snapshot

Use the stored approval payload, not current editable rows or the newest run
artifact, to identify the reviewed batch. Validate exact business, IDs, lead,
channel, effective text and recipient before any decision write; lock the
approval/draft/lead rows through application. Preserve a new explicit consent
to an already-approved draft, but do not let the older grant bypass a new
snapshot check. Recheck snapshot/IDs at runner capability admission.

Versionless pending approvals fail closed rather than being silently upgraded.
The UI displays every reviewed message before the real controls and gives a
reject/reprepare recovery instruction. No schema or production data rewrite.
SQL locks are source-reviewed, not native concurrency proof; the separate queue
transaction and later provider dispatch remain a distinct unclosed boundary.
This scoped fix does not promote generic AI-APPROVAL-BINDING-03 or whole DoD.

## D-055 — Translate managed-card system messages by semantic codes

20 September, parent2fac7241. The owner's Progress task is to understand the
listing state, select a goal and see the next correction and measurement. The
layout, destinations, priorities and approval/write boundaries stay unchanged.
Russian action/evidence/measurement copy from card_growth_service is generated
system text, not business-authored content. Add optional copy_code/copy_params,
evidence_code and disclaimer/decision codes while retaining legacy raw text.
Do not parse action IDs, match Russian strings or translate business names,
provider brands, source identities or factual values. Old measurement JSON is
normalized on read without a migration or mutation of the input object.

This package owns ManagedCardGrowthPanel, the direct managed-focus renderer and
provider audit details. Shared JourneyActionCard and other unkeyed API text
remain a separate multilingual contract; the package is not whole-page locale
completion. Ten-locale coverage is not native-speaker linguistic certification.
Missing/future codes use a localized safe fallback outside RU; the legacy RU
fallback remains readable. Unknown keys must not access inherited properties.

## D-054 — Scan the exact installed set without conflating it with the release image

Revalidate the installed133-package map before a strict advisory query, then
compare the audited normalized name/version map to the same inventory. Do not
silently skip unknown packages, install new versions, treat zero findings as
absence of all vulnerabilities, or transfer macOS results to Linux/AMD64 images.
License declarations are an inventory, not legal compliance or evidence of a
commercial license. Preserve PyMuPDF and historical credential owner decisions.

The unused auth_system.update_user defect is dormant debt, not a demonstrated
profile outage: the live route uses different correct SQL. Prioritize the
reachable untranslated Progress branch over rewriting that unused helper.
Codex Security has no callable tool in the current tool inventory; its optional
scan/deep-scan branch was not run or represented by pip-audit.

## D-053 — Reset is one recovery transaction; unsafe evidence cannot be laundered

Use the actual main DB wrapper and SELECT projection before judging row types.
Native TIMESTAMP handling is the reproduced defect; a plain-dict KeyError from
an inaccurate fake is not. Consume the reset token, update the hash and revoke
that user's existing sessions together; normal password helpers stay unchanged.
The explicit account-recovery hardening follows OWASP Forgot Password guidance
to invalidate sessions, without claiming a successful native-baseline exploit.

Discard preliminary unguarded runs as acceptance evidence and keep possible
effects INCONCLUSIVE. A sanitized env alone is insufficient when main loads
dotenv. Root-owned final pure checks disable dotenv and real DB/network, pin
handler/import provenance and retain all harness failures. Prevent urllib3's
irrelevant IPv6 import probe in the fixture instead of allowing socket access.
Fakes do not establish native lock/concurrent-login safety, full application
health or production readiness. Do not retry denied aggregate/restore work.

## D-052 — Reuse the configured Telegram route without weakening delivery fences

The colleague sender must honor the same application proxy precedence as the
adjacent voice/bot transports. Add the existing helper at the HTTP boundary;
do not introduce a new global proxy, retries, destination selection or client.
The durable attempted state remains committed before the provider call, and
uncertain outcomes remain non-retryable pending reconciliation. A mocked request
without explicit proxy kwargs proves preservation of Requests defaults, not
that an inherited global proxy would be ignored. No live routing claim follows.

## D-051 — Approval and post-claim authorization are revalidated at the effect boundary

Legacy blueprint metadata cannot weaken the canonical capability or
payload-dependent approval policy. Resolve the public input first, evaluate the
canonical policy, require the matching run approval, and pass only that verified
result into the trusted orchestrator boundary. A literal approval override is
forbidden and guarded statically. This does not create a claim that a run/type
approval cryptographically binds a particular target or payload: that separate
AI-APPROVAL-BINDING-03 question remains a candidate until a scoped contract and
tamper regression exist.

A durable social publish claim does not grant permanent write authority. Repeat
canonical write admission immediately before the provider adapter. Do not add
the new write gate to the post-send finalizer: once an external effect may have
been issued, the existing receipt/uncertainty reconciliation contract takes
precedence over a later role check. This narrows the demotion interval without
claiming transaction-level fencing against concurrent revocation.

Pure fakes prove these local ordering and no-adapter boundaries only. They do
not prove native PostgreSQL concurrency, provider delivery, billing, production
authorization, or deployment. The standalone lifecycle chunk's dynamic helper
injection retains a pre-existing F821 static-analysis limitation; do not hide it
with aliases or waive it as a global lint pass.

## D-050 — OAuth state is identity, not a frozen authorization grant

Keep the existing Google owner-or-superadmin contract; signed, purpose-bound
600-second state does not preserve a revoked role or a blocked account. Check
current DB identity before exchanging the code, end that read transaction, then
check again under shared actor/business row locks before persisting credentials
or rebinding Sheets integrations. Do not hold row locks during provider I/O.
The inactive flag follows `verify_session`, including its legacy NULL handling.
Failure rolls back before `DatabaseManager.close`, which otherwise commits.

This does not change callback URLs, OAuth scopes, state format, schema, member
rights or provider publication approval. Pure callback tests prove ordered
admission and synthetic effects; native PostgreSQL lock scheduling, live OAuth,
related-account concurrency and deployed behavior remain separate evidence.

## D-049 — Localize explicit system copy, not arbitrary API text

Today work items carry backwards-compatible `action.label_code=today.open`.
Only the seven existing automation sheet descriptions receive finite
`today.automation.<status>` message codes. Keep raw labels/descriptions for
older web clients and Telegram; no locale query, schema or shared state change.
The web dictionary is keyed by these explicit codes for ten declared locales.
Unknown/missing codes retain the existing fallback behavior; never infer a code
from a business name, draft, campaign title or free-text Russian sentence.
Pending and uncertain provider effects remain pending and uncertain, never
localized into completion or a recommendation to retry a write blindly.

This bounded vertical slice establishes the contract without a large builder
rewrite. Other focus/system copy and deployed-browser proof remain separate.
Language coverage tests prove dictionary completeness, not native-speaker review.

## D-048 — Acceptance is revision-scoped; historical verdicts stay immutable

The machine-readable evidence ledger must follow current verified source and
capture scope, not inherit an old PASS indefinitely. Preserve historical passes,
failures and reviewer verdicts with their revisions; record current gaps separately.
Cross-capture corrective coverage is not a single green aggregate. A successful
structural proof-bundle validation cannot certify the facts or close release gates.

## D-047 — Isolated aggregate uses actual owned network and native verification

Run the frozen aggregate only after dependency parity, a native preflight and
an owned PG16 target have passed. Bind every test DSN to the nonce-scoped
loopback database, preserve the private volume, and use the dedicated internal
network plus an outbound-capable host bridge for the synthetic PG target rather
than any foreign Docker resource. Testcontainers may create fixture-owned
containers. Keep 5 GiB start and 2 GiB live floors; image work remains separately
gated at 10 GiB.

This verifies actual local Docker/network and native database boundaries, not
production, provider behavior, file-picker access or release deployment. The
Python guard is not an OS sandbox. Retain failed harness attempts as evidence;
the terminal full suite remains red. Separately passing frontend/browser,
Compose-plugin, legacy guard-message and local creator checks establish corrected
coverage, not a replacement green result for the original aggregate.

Corrective browser/Compose/guard slices can close their stated environment gaps
without rewriting the terminal aggregate capture. A wrapper may preserve the
original guard policy while adding only the legacy expected denial text; it does
not broaden network permission. Recover generated bytecode by moving it to
private retained proof, not deletion, then recheck frozen tracked bytes. Separate
authorization is required before any restore preparation creates a file. One
fresh clean aggregate, image-capacity, real-API/browser/demo and original release
gates remain distinct from these corrections. Process postcheck after normal
completion does not prove forced-crash cleanup. Post-native catalog observations
made without `--fresh` must not be represented as new freshness assertions.

After the v2 preparation-script write was policy-denied under a prior read-only
constraint, stop that lane and request explicit preparation/test permission.
Do not recreate the rejected script through root, another worker or a shell.
The two already-created, statically reviewed guard/probe files remain evidence
of preparation only, not executable-run or permission proof.

## D-046 — Separate clean dependency preparation from application proof

Do not mutate the shared developer venv to satisfy aggregate tests. Freeze
the committed runtime/test/constraint manifests, create a private native arm64
Python3.11.7 venv and bootstrap the Dockerfile's pinned packaging tools first.
Wheel-only resolution exposed sdist-only googlemaps/pyaes. Review exact official
archives, build only those exceptions without index/dependency/build-isolation
resolution, and then install the full selected artifact set with SHA256 hashes.
Satisfy googlemaps legacy setup_requires with constrained requests beforehand.
Keep the failed initial resolver and failed supervisor probe as harness evidence.

The final 133-package metadata equality plus pip check closes this environment's
missing-package/version-preparation gap. It does not prove runtime imports,
native tests, provider behavior, Linux/AMD64 parity or a reproducible image.
httpx/httpcore used by test PTB and runtime httpx2/httpcore2 are distinct packages;
do not replace valid constraints merely because their names differ. Keep current
test-tool versions in the captured lock and verify them in the actual suite.
No application source or dependency manifest was changed by this preparation.

## D-045 — Media approval is not network or write-role admission

An approved post may still reference a hostile stored URL. Reuse canonical
public-IP-pinned GET for each of at most five requests per remote asset; read
at most10,000,001 bytes per response and reject an asset above the decimal
10,000,000-byte accepted cap. A publication can contain up to10 assets under
the existing limit; this adds no separate publication-wide budget or deadline. Keep
existing local-storage priority and fail-closed empty-media behavior. This
external-download cap is intentionally distinct from the existing10MiB upload
cap. The canonical direct transport does not use the ambient generic proxy;
proxy-only sources may fail closed. Twenty-second per-hop timeouts and DNS
checks do not prove a strict whole-download deadline or real provider transport.

Select the existing write-role helper for six POST mutations only. Default
GET/HEAD read scope stays unchanged; no new role model, schema, automatic
approval or publication behavior. Real canonical helpers run with synthetic
role rows/DNS/pools. A causal mocked RED remains useful but is not a no-egress
certificate: root repeats final279 tests with verified environment and guard.
Keep native database/grants/concurrent role changes and deployed proof separate.

## D-044 — Preserve native async contracts in isolated frontend verification

Network denial must preserve fetch's rejected-Promise behavior; a synchronous
throw created a false ProgressPage passive-effect failure. Preserve the original
641/1 raw result, correct only the private shim, and rerun the entire unchanged
suite (642 pass). Vite's literal localhost lookup receives a synthetic loopback
answer; this does not allow sockets or external DNS. Use the canonical bundle
loader in a private dependency view because the canonical config uses __dirname.
Independently verify shared caches remain unchanged. No test is weakened.

This proves the frozen frontend with reused exact dependencies, not a clean
install, real API/browser, new backend package or release image. Docker startup
approval does not authorize mutation of resumed user databases. Telegram rebind
remains a coordinated, separately authorized release gate; URL inspection alone
does not establish secret-header configuration or successful callback receipt.

## D-043 — Reuse pinned public transport for optional website context

Stored business website is untrusted input even when its setter requires owner
access. Content generation must not connect to private addresses or follow a
redirect without fresh admission. Reuse `core.outbound_network.public_pinned_get`
instead of another URL validator/client. Preserve bare-host compatibility,
HTTP charset precedence and HTML meta/BOM decoding; unsupported/private/failed,
oversized or over-budget pages yield the existing empty optional context.

Five requests and five-second per-hop timeout are not a strict total deadline;
OS DNS latency and first-public-IP availability remain residuals. Current proof
uses real policy/pinning code with fake DNS/pools, not real network transport.
Capacity recovery20September permits renewed preflight, not lowered guards or
automatic production actions. Recreate vanished temporary runners safely.

## D-042 — Separate shared voice-profile writes from permitted reads/examples

SEC-RBAC-10 uses canonical write admission only at `update_content_voice`'s
existing write connection. Keep keyword-only `require_write=False` on the shared
helper so GET, rule/history reads and user-owned examples retain their current
read scope. The initial profile read is legitimate for viewers; authorizing it
does not grant permission to UPSERT the shared business profile later. Recheck
the effective role at that mutation boundary, before advisory lock and effects.
Trust the verifier boolean even if owner_id isNULL; any active non-viewer direct
or network role retains existing write behavior. Preserve demo scope in both
checks. No role model, transport contract, schema or provider change.

Local432f64a0 is proven by causal pure tests plus92overlapping adjacent checks
and independent review. Separate connections and later membership changes are
not transaction-fenced; the simulated downgrade test is not a live concurrency
proof. Explicit commit spies do not model native durability or close-time commits.

## D-041 — Alembic owns news schema; generation only verifies it

Canonical migrations `20260420_add_business_card_automation.py` and
`20260906_move_content_learning_runtime_ddl.py` already own UserNews and the
ten columns used by generation. After write admission, use the existing
read-only `assert_schema_columns` before private context/provider work. Remove
request-time CREATE/ALTER and the compatibility INSERT without business_id.
Do not silently repair production schema or spend provider credits before a
known schema failure. Local `3ee2279a` has causal pure proof and independent
review; actual PostgreSQL grants/catalog behavior remains a separate gate.

## D-040 — Fix the news crash together with its latent admission boundaries

The original unbound local prevents the downstream path from running. Its
16-failure causal RED proves that crash, not successful cross-tenant exploitation.
Before enabling generation, authorize the single resolved business and bind
service/finance inputs and draft/event identity to it. Apply deterministic text
fallbacks before final content rules; failure paths roll back and redact raw
provider output. Business managers may use owner-created records in their
authorized business; creator identity alone is not the tenant boundary.

Keep own `userexamples.business_id IS NULL` entries: canonical content-voice
reads already define them as personal global examples, and legacy creation uses
that representation. Exclude other businesses and other users. Reassignment or
provenance migration is not inferred from this repair. Local `72fd27a9` is
independently proven in pure handler tests, not native persistence or deployment.

## D-039 — Write admission at the mixed-capability Telegram chat boundary

Causal SEC-RBAC-09 tests prove that direct and network viewers reached
`process_chat`, where commands can reserve credits and mutate business data.
Require canonical write admission before entering that mixed-capability path,
consistent with the existing web chat boundary. This denies viewers even when
their text might eventually classify as a read-only request. Supporting viewer
chat later requires a separately constrained read-only path, not removing the
guard or trusting an input label.

Keep `authorize_actor` read behavior as the default for its other audio/read
consumers; the new option is keyword-only and only Telegram chat opts in.
Local commit 78102124 has 12 focused and 101 overlapping adjacent pure passes
and independent review. Native PostgreSQL, live Telegram transport and actual
provider/billing behavior are not certified by these synthetic admission tests.

## D-038 — Keep localized static copy separate from API text and resource gates

Today UI/source trace plus three local REDs justify a dictionary-only fix for
decision, preference and empty-mission copy. Preserve API-provided titles,
scope, priority ordering and request/navigation behavior; dynamic operational
translation needs a separate semantic contract. Local7c374f1f is independently
accepted for93focused/adjacent tests/TS/lint, not all Today localization.

Free host space fell below the existing2GiB floor while system swap allocation
grew10→11GiB. Build/full-unit launch remains withheld; no lowering guards, deleting
swap/proof/DB files, stopping unrelated apps or asserting a successful build.
Human-controlled capacity recovery is needed before resource-heavy gates.

## D-037 — Authorize effective content targets, not only the root selector

Native stored-role tests reproduce viewer generation, mobile denial status400,
and cross-location generation/read-context access even after a root-only write
guard. Do not close SEC-RBAC-07 from the initial10green cases. Resolve effective
scope against stored network structure, require existing read rights for context
and write rights for root plus every generation target before private content
inputs/provider/effects, and
retain legitimate viewer reads and network writer/owner/admin behavior. No new
roles, partial silent target filtering for writes, schema changes or provider calls.
The targeted fix is independently reviewed and committed locallybe1b1a95:
164native/adjacent tests pass. Structural sibling ID/name/city/address lookup
occurs internally after root admission, before target checks; only read-authorized
options reach the response. This is accepted structural lookup, not proof that
all DB reads follow target admission. Concurrent membership/topology changes
after checks remain unfenced; no race-safety claim.

Separately, keep localized sheet labels caller-scoped: optional primitive input
preserves other screens' defaults. The frontend package67169692 has component,
full-unit, type/lint/build proof, not a new browser or deployment proof. User
reported logging into production in IAB; root verified the current Today screen
without clicks. That authorizes no test writes there and does not resolve the
isolated demo's file-picker restriction. Mixed-locale Today copy is separate debt.

## D-036 — Own preview finalization; preserve tool and feature boundaries

The installed Vite's combined default signal/HTTP-close pattern causally
reproduces SIGTERM143 before final evidence. The tested fix owns shutdown,
removes only newly registered Vite SIGTERM/stdin-end listeners and uses its
public close method. Both changes form one tested fix. Do not patch the
dependency or suppress pre-existing signal handlers. Clear close timeout timers.
Actual v2 smoke and subsequent UI stop now preserve their final reports.

Sequence admission must happen synchronously after multipart validation;
failed reads must not release an in-flight mutation. This is bounded harness
hardening, not an application concurrency finding or broad security certificate.

Browser/native permission denial is a boundary, not a reason to switch to
undocumented control. Ask for an allowed browser/manual picker; do not count
unperformed finance operations as a complete demo. Distinguish proxy403 from
upstream403: disabled disk import is a retained-stage feature boundary, not
permission to enable providers. Keep exact IDs/queries and deny write counterparts.
No full-demo/readiness score promotion from the successful lifecycle regression.

## D-035 — Separate fixture proof, UI observation and harness lifecycle

The retained fixture correction may insert only the missing exact synthetic
artifact after container/DB/owner/status checks, never replay the full seed.
SQL/native and actual drawer evidence now prove that bounded correction.
They do not close the complete presenter rehearsal.

A managed file chooser stalled for24190.3679s; a short observation timeout is
not an application failure or permission to restart a possibly live job.
Check the exact handles/captures first. Here the first preview actually reached
its deadline; no finance mutation occurred. Preserve that failed result.
Use a supported native picker for a later run instead of repeating the same
stalled managed operation. Proxy-denied read paths are harness defects until
the original application is tested without that interference. Expand only
source-verified exact synthetic reads, not a broad GET pass-through: some other
GET endpoints can call providers or change state. SELECT followed by commit
alone is not evidence of a write.

The separate drawer check rendered the expected text, but its SIGTERM exit143
left an empty reserved result. Do not call that a clean helper lifecycle.
Manual root postchecks can prove their own artifact/identity/process invariants,
not fabricate the missing self-report. Preserve concurrent worktree changes
that appeared during the long tool stall; the frozen suite is not their proof.
Installed Vite source independently registers a SIGTERM callback that closes
its server and calls process.exit, a plausible preemption of the helper's
async finalization. Trace evidence is absent; test a minimal sole-owner signal
fix before the next browser run rather than extending another supervisor.

## D-034 — Preserve retained fixtures and distinguish a hypothesis from a result

The missing partnership overlap is a seed/UI storage-contract mismatch, not a
failure of matching logic. Store only an explicitly synthetic, unconfirmed
`needs_evidence` artifact using the current drawer fields. `ON CONFLICT DO
NOTHING` must preserve an existing artifact instead of replacing audit/offer
evidence. SQL-recording tests establish the emitted contract, not actual DB
idempotence or a completed browser demo. Do not replay the full seed against
retained staging: its older statements update other fixture fields. A later
runtime correction must target only the identity-verified missing artifact.

The current backend aggregate uses an immutable6eec archive and reuses the
owned native test DB without launcher reset/migration. Normal suite-owned
temporary PostgreSQL migrations are distinct. Resolve Compose through a
task-local shim that executes the actual installed plugin; do not repurpose
HOME or change the user's Docker profile. Keep all source/evidence boundaries,
2GiB floor and failed-launch evidence explicit.

## D-033 — Pin actual synthetic cohort; never reconfigure it for a UI proof

The review browser preflight expected all compiled flagsfalse but retained
staging was intentionally compiled-enabled for the exact synthetic business.
That failed before login/browser and is a harness-assumption error, not a
product defect. Do not change container flags or reseed. A reviewed narrow
retry may pin true/true/exactcohort while preserving false async/scheduler/
provider dispatch, exact identity, browser GET/HEAD-only routing and post-run
identity checks. Only explicit synthetic login writes are authorized; copy is
local clipboard behavior. This cannot certify current backend/image or imply
that the historical stage is wholly disabled. Keep original failed evidence.

## D-032 — bounded rotating alerts, without a new durable scheduler

The native101-tenant reproduction proves repeated lexical-prefix starvation.
Use a process-local last-tenant cursor and a single SQL-limited wrap selection;
do not fetch the full tenant list into application memory or increase the
per-scan metrics budget. Advance after successful selection independently of
individual metric failures, retain cursor on empty/query error and preserve
disabled/interval gates. This is continuous-worker fairness, not a durable
or shared multi-worker checkpoint. Persistent scheduling/schema work is not
needed to fix this reproduced defect and has not been silently introduced.

## D-031 — Recovery smoke must not authorize callback replay

Independent call-chain review found the deployment smoke automatically replays
all DLQ/retry on any alert. That would also replay the new uncertainty marker.
Checking metrics immediately before replay cannot close the concurrent-row
race. Remove implicit replay from smoke and report the manual reconciliation
requirement; keep the existing explicitly invoked, tenant-authorized replay
operation. This changes no callback schema or HTTP contract and does not treat
a deployment request as approval to resend ambiguous notifications. Existing
normal retry remains the documented receiver-idempotency contract. Verify the
real shell control flow with fake commands, never a live deployment/send.

## D-030 — Follow causal failure evidence, preserve callback delivery contract

The v8 process-only reproducer confirms a nested orchestration limitation,
not an application bug. Remove redundant orchestration; keep one reviewed
lifecycle owner, fail closed on unknown identities and preserve old evidence.
Do not weaken checks or certify arbitrary detached process trees from a small
proof. Prepared wrappers are not executions; generated helpers/paths/pins must
be tested, not merely compiled.

Managed-browser finance actually exercised preview/apply/duplicate history.
Its missing partnership fixture expectation and mixed-language copy stay open;
a long file-picker delay is not a10–15minute presenter rehearsal. Preserve
existing synthetic records instead of reseeding merely to make screenshots pass.

Callback interrupted-claim RED proves permanent `sending` non-recovery. Keep
the receiver's explicit dedupe/idempotent-ack at-least-once delivery contract;
do not misclassify ordinary timeout retry as proven repeated business effects.
The scoped fix uses existing DLQ/manual reconciliation for stale ambiguous
claims and preserves fresh/foreign claims, normal503retry and stable event IDs.
Late-worker finalization must not overwrite a quarantined or newer claim.
One-hour abandonment is a conservative heuristic, not proof of non-delivery;
no automatic replay, new schema or unilateral provider action is authorized.

## D-029 — Resume native proof without treating recovered space as unlimited

Safe approved cleanup recovered enough space for guarded native measurements.
Execute the previously prepared process-only controller proof before using it
in new one-shot wrappers. The actual ten-case pass and independent leftover
check permit integration; they do not explain the original EPERM or retroactively
validate its partial measurements. Keep that failed capture unchanged.

Use measured peak storage, not only a start-floor check, for Docker readiness:
the historical browser build consumed~6.8GiB of headroom. Current~5.86GiB does
not cover that plus reserve. Continue independent native/demo work serially
instead of either launching an unsafe build or calling the whole goal blocked.

The ten-case process proof and successful paired measurement do not certify
every nested process tree. A later native6 wrapper fails before tests with
`group_membership_or_identity_invalid`; preserve the raw failure and investigate
the controller rather than lowering identity checks or counting unrun cases.


## D-028 — Test-origin assertions follow the configured runtime

A dynamic-port browser run cannot use a fixed18000 console allowlist. Extract
the actual two-journey collector, reproduce its missed first-party events,
then compare URL origins against Playwright's configured baseURL. Preserve
uncaught page errors and unknown-source errors; exclude only known foreign
origins. This is bounded test-harness repair, not a product change or evidence
that already-completed browser runs were console-clean. Pure Node event tests
with env files/app setup disabled are small enough for low-disk verification;
they do not bypass the existing browser/DB/build/process-proof start guards.

After the bounded fix and independent reconciliation, preserve a resource-
blocked handoff: the same ~1GiB Mac constraint has persisted across at least
three goal turns and the next required execution needs recovered headroom.
Do not repeatedly rewrite status documents or invent unproven product edits.
This does not close unchecked Stage1 scope or turn the overall FAIL into PASS.

## D-027 — Reconcile inventory without promoting missing execution evidence

A coarse runtime diagram cannot stand in for all checked-in execution surfaces.
List exact manifests, optional worker roles, migrator/runner, timers and CI, then
map auth, organization and provider boundaries to source. Separate declarations
from enabled/deployed state: the base manifest and placeholder Nginx config do
not reconstruct the eight-service production topology recorded in maintenance.
Likewise, a successful scanner command whose detailed temporary report is lost
cannot establish clean dependencies/licenses. Preserve missing baseline records
and unchecked audit areas as explicit gaps; later successful tests do not backfill
historical proof. AC1 remainsFAIL until its actual remaining evidence is obtained.

## D-026 — Stop launches below local disk guards

At16:29UTC the Mac has~0.985GiB free, despite the separately enlarged server
disk. Preserve completed results and the failed comparison's partial archive/
synthetic DB; do not lower guards, reset Docker or delete unknown user resources.
The v8 process-only proof is independently static-approved but remains unrun.
Require recovered headroom, bounded execution and observed child cleanup before
integrating it into fresh one-shot benchmark/demo wrappers. Prepared code and
successful py_compile do not prove runtime cleanup or explain the priorEPERM.

## D-025 — Preserve failed probes and pin observed Docker bases

An interrupted comparison is not a partial performance PASS. Preserve the first
demo and benchmark captures, unknown failure cause and residual synthetic DB;
fix only the test controller/selection before any separate retry. Review of the
prepared process controller rejected stale identity overwrites, unreaped leaders
and unverified process-group ownership before it was executed.

The two application Docker base images can be pinned to the exact public OCI
indexes already resolved by the historical f0cc build. Registry metadata on
18 September verifies response SHA256, registry digest header and linux/amd64
plus linux/arm64 descriptors; no image layers were downloaded. This avoids
tag drift without a speculative base-version upgrade. It does not freeze apt,
prove dependency artifact hashes, pin Telegram's application parent or establish
a new successful build. Those gates remain separate.

## D-024 — Separate measured local behavior from release and capacity claims

Keep the exact272native117 browser suite,240-read paced HTTP profile and
historicalf0ccbackend/unchangedfrontend60-load browser profile separately
identified. They answer different questions; combining counts cannot create a
current immutable-image or production-capacity result. Preserve failed harness
captures and correct only the harness assumption: Flask injects SEO into HTML,
so ingress identity requires referenced asset byte matching, not HTML equality.
Visible-control timings and sampled ps observations do not imply Web Vitals,
true peak memory, a memory leak test or general speedup. Acceptance follows the
written criterion, with production capacity separately retained as a risk.

## D-022 — Reauthorize stored mobile-action targets before any executor

Direct endpoint gates alone do not protect the normal Telegram preview/confirm
flow. Prefer one required target-authorizer at the existing common confirmation
boundary over nineteen scattered executor checks or a new authorization layer.
Validate the complete stored target set first, using current canonical write
roles; no partial batch effects may precede denial. Preserve read-only preview
and the already-completed result replay, which must not execute again.
Capability admission independently uses the real `review_replies.` prefix and
retains the old `reviews.` alias. Native causal RED and final GREEN are required;
static review or a model stub alone is not evidence of real provider behavior.

## D-023 — Keep synthetic CI separate from production and local Docker

Select a fresh hosted-runner job rather than silently broadening every PR gate
or accepting arbitrary developer targets. Unique numeric run identity, empty
inventory preflight, exact labels/names and cleaned child environments constrain
resource ownership. Fake-command tests verify the contract including refusal
and cancellation; actual GitHub execution remains a separate acceptance gate.
Browser install and execution must share the same explicit cache path. Local
commit is not authority to push, schedule or dispatch the remote workflow.

## D-021 — Prove an opt-in release contract without changing deployment

Changing the base Compose defaults would alter an existing deployment before
runtime/data-transfer rehearsal; retaining only a written runbook would not
test the merged configuration. Selected a separate base+release override in
a00ac558: digest-pinned application images, no code binds/builds, check-only
runtime roles and one explicit migrator. The actual merged-config/startup
contract passes 13 tests. It is not activated and must not be applied to live
data without backup and approved transfer into the new named runtime volumes.
Other Compose fragments, tagged infrastructure images, image startup/rollback
and operational credentials remain separate gates. A Compose configuration
pass neither starts a service nor proves its runtime behavior.

## D-020 — Constrain the observed app closure without claiming a universal lock

2e121912 projects101application versions from the audited104-distribution
ARM64 image. Three packaging tools remain separately pinned in Dockerfile;
only pip changes24.0→26.2. Existing requirements intent and indexes remain.
The source pins-text SHA and normalized-map SHA are distinct provenance
values. Static tests verify projection, count and Docker consumption; a new
image must independently match the projected104-package map and pass audit.
This is not a hash-locked/offline/AMD64/Telegram dependency closure; base tags,
artifact bytes and bot-only dependencies remain separate verification gaps.

## D-017 — Ambiguous publication is a durable hold, not a retry

18 September: commit a compare-and-set publication intent before provider I/O.
Only the caller that freshly claimed it may send. An uncertain result or failed
final commit remains `publishing`; no automatic retry or timer resets it.
Manual reconciliation requires a per-post receipt and explicit confirmation;
the bulk endpoint cannot resolve several uncertain posts with one receipt.

The provider connection uses autocommit before its first query, with one
nonblocking session advisory lock per post held through the separate finalizer.
Manual reconciliation requests the same key as a transaction advisory lock;
if busy, it fails closed. After acquiring the lock, provider code rechecks
status, attempt state/ID, approval and the content/business fingerprint before
sending. Do not replace this with a timeout lease: process pauses and partial
network progress do not establish a safe time to assume the provider stopped.

This deliberately retains one connection and one application mutex during I/O,
but no open SQL transaction. Session locks survive transaction rollback and are
released explicitly or on connection termination; same-key transaction locks
conflict with them. The current connection is direct, not transaction pooled.
Any future pooling change must revisit this contract. See the official
[PostgreSQL advisory-lock semantics](https://www.postgresql.org/docs/16/explicit-locking.html#ADVISORY-LOCKS)
and [Psycopg autocommit contract](https://www.psycopg.org/docs/connection.html#connection.autocommit).
Source changes and causal concurrency tests passed independent review and the
237-test root aggregate in d3ca8b1e. This is not exactly-once delivery or a
production rollout; new browser integration and final whole-revision gates remain.

## D-019 — Engine alignment and disk headroom are verification prerequisites

18 September: align Docker frontend builder with existing Node22 CI and locked
jest-dom7 contract; no broad dependency upgrade. Keep failed sanitized-PATH
build capture separate from product failures. Remove only exact validated
reclaimable/nonshared old audit build-cache IDs, not images/containers/volumes.
Build requires over4GiB free and cancels its own process at1.5GiB. Cache is
rebuildable, not database maintenance. Passing aggregates retain original
revisions instead of silently proving later changes.

## D-018 — Preserve failed baseline samples and separate transport claims

18 September: the 50-sample baseline business-data HTTP500 remains an error,
never a fast successful request. Quantiles use only successful requests, and
whole-journey request-work totals require all steps successful. Cold clean
processes, synthetic data and stubbed providers are explicit limitations.
Prepared-target in-process Flask concurrency is a useful bounded application/SQL
stress check, but cannot establish HTTP/Gunicorn capacity or production p99.
Migrations, fixture setup and invariant reads stay outside latency windows.
Keep source/guard hashes, raw errors and exact cleanup evidence with each run.

## D-012 — Native SQL proof is useful, but is not Docker/PG16 parity

Use a freshly created, loopback-only native PostgreSQL cluster with synthetic data to continue actual transaction/role checks while shared Docker is unavailable. Retain exact server version, data_directory, named test databases, archive commit and no-egress environment; stop only the owned cluster after checks. PG15 results can confirm SQL defects and fixes without pretending to satisfy PG16, image, compiled-runner or full production recovery requirements. Do not replace the original acceptance criteria with easier native-only checks.

## D-016 — Resume from durable evidence and verify new Docker storage

18 September: explicit permission covers starting local Docker without reset, not deleting volumes or certifying old storage. Fresh task-owned PG16 passed synthetic write/checkpoint/restart/dump-restore/pg_amcheck; old stopped audit volumes remain unused. Earlier temp archives/traces/dependency reports disappeared across host interruption. Preserve durable raw captures, record unavailable artifacts honestly, rebuild only what the next acceptance gate needs. Native full4319-pass evidence is already complete and need not be repeated just because its temporary runner is gone. Heavy build/scan/load jobs run serially with headroom checks.

## D-015 — WhatsApp admission is not exactly-once external delivery

Use existing durable agent_trigger_events unique admission before processing/sends. Completed duplicates return safely; active duplicates do not rewrite the original row. Failure or ambiguous send is visible as needs_reconciliation; crash-after-admission may remain processing. A superadmin-only bounded projection exposes status/reason/IDs/timestamps without message/phone/payload secrets and without replay controls. Mixed batches continue eligible later messages. Do not automatically retry a possibly delivered send.

## D-014 — Dependency advisory mitigation must retain compatibility proof

pypdf6.16.1 is pinned after reachable untrusted PDF ingestion and upstream advisory review, with valid-text/encrypted/malformed compatibility coverage. No exploit or denial-of-service was reproduced. The host121-package scan is not the production image inventory. Fresh final-image resolution/scanning remains necessary; avoid claiming all dependency findings fixed from one pin.

## D-013 — Role proof must reach real stored data and actual effects

A fake role label unused by a cursor, or ImportError for a not-yet-added helper, does not prove an authorization defect. Require actual membership rows, the real guard, a reachable API request and an effect/no-effect assertion. Authorize the stored object tenant, not only the caller-selected business. Preserve documented read/preview/HEAD behavior and existing non-viewer/legacy NULL-business semantics while recording the remaining platform role matrix separately.

## D-011 — Reconcile repeated maintenance requests before repeating downtime

The latest user request permits the previously deferred server Docker/database maintenance. Live evidence confirms that exact runtime-snapshot release and DB restart already occurred and no deployed migration is pending. Do not repeat downtime or apply the separate unfinished audit checkout merely to perform an action. Clean canonical-image hardening is still a distinct unfinished release; server capacity does not establish local Docker Desktop integrity or approve its shared restart.

## D-001 — Preserve the full goal, stage the evidence

The new whole-project audit starts from `30262a5b`; previous release results are historical context, not fresh proof. Separate local fixes from deployment approval. Baseline tests run from a clean archive to avoid silently importing local credentials or dirty state.

## D-002 — Evidence and severity

Use `CANDIDATE`, `REPRODUCED`, `FIX_UNVERIFIED`, `FIX_PROVEN` and explicit limitations. P0 requires a supported critical consequence/reachability; do not inflate every inspection concern to P0. Review code paths and independently test user-visible failure. A passing mocked UI suite does not prove authorization, database integrity or provider behavior.

## D-003 — Revoked users fail closed centrally

Normal `verify_session` callers must not accept inactive accounts. A keyword-only diagnostic opt-in is allowed only at `/api/auth/me`, which immediately returns its established `403 account_blocked` response. Other protected routes use their existing 401 denial. This avoids scattered inconsistent route guards while preserving the browser contract. No schema change or data mutation.

## D-004 — Authenticate webhook bytes before processing

WhatsApp verification has no public fallback token. POST authentication uses the explicitly configured app secret and HMAC over the raw body, before JSON parsing, business lookup, AI or sends. A valid signature does not by itself solve replay/deduplication; that remains a separate acceptance item. Deployment must configure matching provider secrets first and is not performed in this local audit.

## D-005 — Avoid structural rewrites without evidence

Keep Flask/PostgreSQL/React and existing policy/execution boundaries. First reproduce transaction, identity and concurrency failures. Add indexes only after real query-plan evidence. No large module splitting or new lead table merely for aesthetics.

## D-006 — Telegram per-business ingress without schema migration

Compared three options:

| Option | Security / compatibility | Cost / performance / residual debt |
| --- | --- | --- |
| Global header secret + existing token lookup | Quick auth hardening, but shared secret blast radius and raw credentials remain in transport | Small patch; existing all-business decrypt scan remains; rejects legitimate callbacks until registration fixed |
| Business-ID route/query + domain-separated HMAC secret derived from stored bot token | Selected: tenant identity is fixed by indexed DB lookup, header verified before payload processing; no bot token in webhook URL | No schema/data migration, O(1) indexed lookup; requires deliberate rebind; secret rotation follows bot-token rotation; replay still separate |
| Random opaque binding + separately rotatable secret hash | Best independent credential lifecycle, supports future binding management | New table/column, provisioning UI, migration and rollback; higher rollout cost; defer until binding lifecycle is a demonstrated requirement |

Selected the bounded second option for local implementation. Telegram's documented `setWebhook.secret_token` creates the `X-Telegram-Bot-Api-Secret-Token` callback header; a custom header on the registration request does not configure callbacks. [Provider contract](https://core.telegram.org/bots/api#setwebhook), checked 2026-09-17 UTC. Unauthenticated and retired raw-token URLs must fail closed. This authenticates source possession, not replay prevention or approval of arbitrary AI actions. No webhook is registered or production configuration changed by the audit.

## Pending decisions

- Immutable production artifacts vs current bind mounts: prepare/test local release profile before proposing production rollout.
- Dependency locks: capture currently working resolution and audit compatibility before incremental upgrades; no blind wholesale update.

## D-008 — Test safety remains a contract, not a failing-test bypass

The patched full backend run rejected a new isolated DB name without the required `test` substring. Correct the dedicated test target, never remove the guard. Nested outbound guards may reject a request earlier than an inner guard; prove the inner hook explicitly with a non-network audit event and require the actual socket attempt to be denied by a known guard. New PostgreSQL regressions use the portable project testcontainer fixture, not a developer's fixed local port/container/credentials. Preserve inherited no-egress hooks across migration subprocesses.

## D-009 — Restore evidence has explicit scope

The local rehearsal ties dump and source verification to one exported REPEATABLE READ snapshot, restores into a fresh UUID database and verifies cluster identity first. Equal data/counts, logical columns, constraints and Alembic revision across 288 public tables prove that limited recovery contract. They do not prove indexes/triggers/views/functions/sequences/grants or real-production backup recovery. Keep the archive and target until the audit retention/cleanup decision; do not invoke the unsafe legacy restore helper to extend coverage.

## D-010 — Resource incidents are not application test verdicts

Local Docker/EXT4 and PostgreSQL I/O failures during image scan/build and full tests invalidate a green-ready claim; retain failures as infrastructure evidence, not random product fixes. Shared Docker recovery affects unrelated user containers and needs explicit authorization. No factory reset, global prune or user-volume deletion. Free only exact proven disposable cache copies; run future heavy operations serially with adequate headroom and explicit shared scanner cache. Historical successes remain historical, and local volume/image integrity must be rechecked after recovery.

## D-007 — Data-preserving downgrade instead of silent no-op or CASCADE

For the broken work-review rollback, compared: (1) reverse only an empty feature schema, with transaction-held writer locks and guards for every lossy field; (2) permanently forward-only migrations plus backup/restore; (3) force the older parent DROP with CASCADE. Chosen (1) repairs the documented disposable downgrade contract at limited blast radius; (2) remains the required recovery alternative for populated feature data; (3) is rejected because it conceals dependency ownership and can destroy unrelated data. Upgrade behavior is unchanged. Never infer that a successful empty rollback proves populated production rollback safety. The creator-portal obstruction is a separate revision/package and must receive the same independent data-safety analysis.
