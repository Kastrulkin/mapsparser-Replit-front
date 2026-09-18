# Readiness decisions

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
