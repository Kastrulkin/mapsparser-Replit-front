# LocalOS threat model — current audit evidence

## Latest diagnostic-boundary update — 21 September, parent5ef5ba7e

SEC-WORKER-ARTIFACT-02 locally corrects five diagnostic file writers plus related
error/normalization logs; SEC-LEGACY-ORCHESTRATION-LOG-01 corrects four legacy
orchestration prints. Final49pure passes, causal parent failures and independent
reviews support only these boundaries. Functional raw IPC, other service-level
debug files, legacy leaf logs/raw invalid-input errors, persisted proxy/queue
reasons, old artifacts and deployed code remain separate open boundaries.
No historical credential clearance, release promotion or production change.

Status: incomplete security assessment, not a production approval. Baseline `30262a5b`; local fixes and evidence are recorded in [the change log](06-change-log.md) and [backlog](02-audit-backlog.md). The deployed runtime is a separate artifact described in [the maintenance record](../RUNTIME_RELEASE_20260917.md). A locally fixed boundary is not presumed fixed in production.

## Assets and adversaries

21 September, parentfdbabac4: SEC-WORKER-PARSER-LOG-01 corrects six direct/retry/
subprocess console sinks. Immutable-parent AST RED5 and final34pure passes,
source-hash reconciliation and independent review prove this limited boundary.
Queue/proxy error persistence, worker normalization/debug files, legacy parser
diagnostics and deployed/retained logs remain separate unresolved boundaries.

The additional110 frozen-history bindings prove70nonsecret values (59file
digests,8explicit placeholders,3record UUID identifiers), retaining40UNKNOWN.
Reconciled history totals are74nonsecret/592access-material locations not
cleared/45UNKNOWN; tree retains31nonsecret/10access components/1UNKNOWN.
The latest unknown queue is46, not the risk count. Original scan exit1,
credential-lifecycle gates and overall FAIL remain unchanged.

21 September, parent074ee5a0: SEC-PARSER-LOG-01 is reproduced by six synthetic
diagnostic cases, corrected locally and checked by29 pure cases plus source
review. URL components, provider fields/keys and exception details no longer
flow directly through this parser's runtime print expressions. Core data stays
intact. Console sinks in dependencies/worker, intentional CLI result output,
raw returned error URLs, historical logs and deployed revisions retain separate
boundaries; this is not universal logging or credential-lifecycle clearance.

Six frozen historical runtime rows have exact object/whole-redacted-Match/AST
proof: four are static content-key identifiers; an os.getenv default and a
constructor credential argument remain UNKNOWN. The initial default-as-name
classification failed hardened verification and is withdrawn.115history+tree11
=116 remain unclassified/UNKNOWN; classified access material remains a risk.

21 September follow-up, parent bf277dbf: 572 frozen debug-directory scanner
rows bind to provider fields (510 hittoken, 26 aesKey, 8 clientKey, 28 ordToken;
249 distinct values). This classifies storage context only. Purpose, privilege,
validity and revocation remain unknown; 119 history rows plus tree11 are still
unclassified. The separate current producer candidate SEC-DEBUG-BUNDLE-01 was
reproduced with a synthetic response callback and corrected at its debug-file
boundary. New diagnostics omit raw values/HTML/URLs/screenshots. Existing logs,
bundles, deployed images and full browser-session behavior retain separate gates.

21 September tree follow-up at 08c383e1: 42 rows adjudicated conservatively as
31 non-secret source digests, fixtures and identifiers; 10 Google Docs image-access
URI components (one repeated query value); one UNKNOWN. Another 691 history rows
remain unreviewed: 692 total unresolved. No resource URL was requested; expiry,
revocation and access scope remain untested. The current ignored provider-response
file matches the historical blob and was not excluded from Docker's broad COPY.
SEC-BUILD-CONTEXT-02 adds only that family exclusion with 14 static checks;
current and previous image layers remain unverified. Graph count 3117 and scanner
count 3095 are different metrics; exact 22-member difference remains open.
See git-tree-triage-notes for source predicates, retained failures and limits.

21 September local-ref checkpoint at7cf0cd24:89refs/3117reachable commits and
938extra tree blobs. Redacted scans report711+42matches, both exit1.20priority
locations corroborate2occurrences of one service-role JWT,1opaque Wordstat token
and17anon-role occurrences; signature/validity/revocation/RLS unproven.733other
matches remain unreviewed;3117selected/3095scanner count not yet reconciled.
Archive/binary/LFS/reflog/remote/dirty/runtime/image/log exclusions remain. This
improves evidence, not AC6. See task evidence/git-all-refs-notes-20260921.md.

21 September supply-chain checkpoint at `334c9d4b`: a strict full committed-source
scan produced 101 matches, all classified non-secret after source predicates
and independent review. The 131-commit branch delta has seven synthetic/prose
matches; it does not re-scan all refs or establish historical revocation. The
frozen frontend lock audit reports zero advisories across 528 dependency entries.
All 528 license declarations now have recorded provenance: 215 lock entries,
305 matching-version installed manifests and eight registry version/integrity
matches. This is metadata, not legal compliance or release-artifact integrity.
Initial failed/truncated captures are retained and explicitly excluded from
success claims. Current image/layer/log/OS/native scans and owner decisions
remain open; AC6 remains FAIL. See
[the bounded review](../../.agent/tasks/production-readiness-20260917/evidence/current-source-supplychain-review-20260921.md).

20 September source adjudication afterca0c3d36: supported contact writers never
change normalized identity under the same UUID, and supported sender writers
produce boolean capabilities. Both proposed bypasses are NO_BUG_PROVEN, not
new security fixes. Raw DB tampering/future writer changes are defense-in-depth
considerations. See D-058 and recipient-review-notes.md for exact traces.
The separate recipient visibility fix improves operator review only; it is not
new approval/hash/dispatch enforcement or native concurrency proof.

20 September OUTREACH-DISPATCH-IDENTITY-01 closes a bounded generic campaign
body-binding gap locally: draft.approved_text could change while the approved
touch hash stayed unchanged, and the dispatcher used that mutable copy. Real
hash/preflight/bind causal5fail/1pass and final138pure passes support linked
queue/draft/touch validation and fresh provider inputs. No actual endpoint edit,
DB/provider send or production exploit was executed. The original approval hash
still binds contact ID, not a value snapshot (adjudicated above); post-preflight native races and
generic non-outreach approval identity remain open.

20 September AI-APPROVAL-DRAFT-IDENTITY-04 is locally reproduced and corrected:
an editable draft or newer artifact could replace what a pending decision
represented. The stored versioned snapshot now binds tenant, IDs, lead/channel,
effective text and contact; pre-write locked comparison and capability recheck
use only those IDs. Final313mocked tests and16targeted UI checks pass. This is
pre-decision/capability-admission proof, not native concurrency or the separate
later queue/provider transaction; broad generic binding03 remains a candidate.

20 September SEC-SSRF-02 is locally FIX_PROVEN4e33587d. Owner-set business
website reaches content-plan generation; owner authorization is not network
destination authorization. The reader now reuses canonical public-IP-pinned
transport at every redirect, with response/redirect limits and safe empty
optional-context fallback. Causal16 contract failures and exact149 adjacent
passes (including25 focused cases) plus independent review support this bounded
claim. DNS and connection pools are faked; setter/caller provenance is traced
in source, not a live HTTP/route integration exploit. Other outbound readers
and production remain outside this proof.

19 September SEC-RBAC-10 is locally FIX_PROVEN432f64a0: business voice-profile
PATCH's role-blind mutation gate is reproduced (8failed/6passed) and replaced
with optional canonical write admission at the existing write connection.
Permitted initial profile reads, GET and user-owned examples keep read semantics.
Final19focused/92overlapping adjacent pure checks and independent review pass,
including nullable-owner managers, mixed roles, demo scope and a simulated
read-to-write downgrade. Five hardening cases were added after the baselineRED.
SQL/commit counters do not prove native grants/durability or close-time commits;
no live role-change race, image or production certification follows.

19 September SEC-RBAC-08: the direct Operator news endpoint's read-only role
bypass is reproduced with actual canonical helpers and synthetic SQL rows.
Local e3e8fbff changes its single guard to write admission: 14 route tests and
20 overlapping adjacent pure tests pass, independently reviewed. Database,
generator and audit boundaries are controlled in this proof; no native billing,
production or other-channel certification follows.

SEC-RBAC-09 is now causally reproduced and locally fixed in78102124: canonical
write admission before generic Telegram `process_chat`; 12 focused and101
overlapping adjacent pure passes with independent review. The entire mixed
chat is writer-only, even potentially read-only intents; other read/audio
consumers keep their default behavior. Legacy BUG-NEWS-01 is now locally fixed
in72fd27a9: crash RED16fail, GREEN21/adjacent71. Its tenant/source issues were
latent behind the crash, not independently exploited baseline paths. One target
is authorized before private inputs/provider; final rewritten text is enforced
before effects; failures roll back and raw provider output is redacted.
Own NULL-business examples retain their canonical personal-global semantics.
Follow-up3ee2279a removes news request-time DDL and requires the migrated tenant
column before generation (23focused/73adjacent pure passes, independent PASS).
No production exploit, native persistence/grant, real provider or image proof
is claimed for these new packages; other legacy endpoints remain outside scope.

19 September SEC-RBAC-07: native causal tests reproduce read-only content-plan
generation plus selected-network-target/context admission gaps. The independently
reviewed localbe1b1a95 patch passes164focused/adjacent tests7.91s, capture9.122281s,
including stored superadmin, viewer read access, reverse root/target roles,
foreign scopes, persisted item/audit tenant identity and continuation. Root
permission is checked before scope resolution; selected targets before private
content inputs, generation and writes. Structural labels are read internally
while resolving scope and filtered before response. This does not fence
concurrent membership/topology changes during generation, cover every content
mutation, or prove production/image behavior. No schema changes or provider calls.

Assets are business/network membership, sessions, provider credentials, private customer communications, finance records, uploaded documents/audio, private knowledge, drafts, approvals, billing limits and the integrity of execution history. Availability of the app, database and workers is also an asset. PostgreSQL is the durable business source of truth; browser state, Redis and provider acknowledgements are not substitutes for committed business history.

Relevant actors include an anonymous API caller, a valid user attempting a foreign-tenant or higher-role action, a former/revoked member, an attacker controlling a retrieved website or uploaded document, a compromised provider credential, and a mistaken operator targeting the wrong deployment or database. No historical exploitation is asserted by this model.

Latest scoped checkpoint272794a4 adds canonical write permission to review
mutations and to every stored target before common mobile-action execution.
Native tests cover direct/network viewers, mixed targets, membership revocation,
legitimate writers, completed replay and inactive subscription at preview or
confirm. Combined104checks pass156.03s with independent review. This corrects
the reproduced authorization/capability admission failures, not all platform
objects or actual model/provider behavior. All audit patches remain local.

## Trust boundaries and acceptance evidence

| Boundary | Required invariant | Current evidence and limitation |
| --- | --- | --- |
| Browser/bot identity → API session | Missing, expired or inactive identities cannot reach effects; demo sessions remain scope-restricted | SEC-AUTH-01 local denial tests and patch. Complete route/session-kind coverage is not established. |
| Authenticated API → tenant object | Requested IDs, stored object tenant and action permissions agree | Shared `core/auth_helpers.py` checks membership, not automatically writes. Finance/stored-transaction, blueprint, Operator chat and now services/content125900b2 patches are reviewed and locally committed with stored-role negative tests (latest27focusedpass). Complete platform mutation/object-derived tenant matrix remains open. |
| Provider callback → processing | Verify source before effects; repeated delivery cannot repeat unsafe actions | SEC-WH-01/02 local signature/secret fixes; Telegram admission handling SEC-WH-03. SEC-WH-05 now uses existing durable WhatsApp admission keys and exposes uncertain outcomes without blind replay. Crash/uncertainty still requires reconciliation; not exactly-once delivery. Provider rebind is a rollout prerequisite. |
| Public website → outbound connection | Every connection uses a validated globally routable destination, including redirects | SEC-SSRF-01 pins contact-page GETs to validated numeric IPs, preserving TLS hostname checks. 76 no-network tests and independent review pass. Unrelated outbound clients are not covered. |
| Untrusted input/retrieval/model output → tool executor | Model text cannot grant tenant identity, approve actions, select unrestricted tools or bypass billing | Real runner/policy/finance proof24e0d4cd passes one hostile-row scenario with stored approval, trusted business/capability and actual tenant-scoped writes. Complete adversarial prompt/output/tool matrix remains; prompt wording alone is not protection. |
| Approval/job → local commit/provider effect | Durable identity and replay state prevent duplicate local effects; uncertain provider effects require reconciliation | SEND-AMB durable intent/advisory/CAS/receipt fixes have realPG proof; scoped120browser checkpoint includes reconciliation. Reviewed13c1f36a binds recipient/account/media descriptor,252main passes plus separate9viewer passes. Final same-image proof and external object-byte immutability remain. No exactly-once claim. |
| Source/config → image → live service | Tested artifact identity, secrets exclusion, minimal privileges and rollback remain true at runtime | Build-context/public-artifact fixes pass. Reviewed2e121912 constrains101app versions plus3Docker pins; actual rebuilt map/audit pending. Production bind mounts, base/artifact digests, bot/AMD64 closure and hardened rollout remain gaps. |
| Backup archive → restored database | Explicit trusted archive and isolated target; verify recovery before claiming it | Reviewed helper ran against a fresh synthetic PG16 target; independent comparison covers288tables/all data,844indexes,19triggers,3views,160functions,2sequences and owners/grants/defaultACL. This closes local full-schema proof, not production-backup recovery. |

## Representative abuse and failure cases

### Narrow compiled identity trace and revocation regression — 19 September

Source trace distinguishes the pure compiled transform from the legacy
capability runner. `agent_blueprints_api.py` resolves the blueprint/version and
input snapshot in the authenticated actor's business scope; `agent_run_admission.py`
re-reads those identities; `agent_run_queue.py:compiled_run_claim` rechecks the
stored actor, admission audit, current membership, approved version and artifact.
The sandbox receives source/manifest/fixtures/input, not a DB handle or trusted
tenant/approval authority. Its result is stored under the existing run lease;
there is no compiled-result-to-capability dispatcher in this traced path.
Compiled version approval is not the legacy provider action's per-run approval.
This is a bounded source trace, not a complete adversarial/model-output audit.

The trace found an untested existing protection, not a reproduced bypass.
`tests/test_compiled_run_claim_pg.py` now exercises both direct and network
membership: revoke status or delete membership after a valid queued claim,
require `compiled_actor_access_revoked` before artifact validation, then restore
access and require validation/success again. Account/session denials and the
transaction-release check remain. The test-only change was independently
reviewed. Real PostgreSQL plus adjacent artifact/runtime tests:18passed4.78s,
capture5.387119s,exit0/no timeout/truncation. Root confirmed zero remaining
`test_compiled_claim_%` schemas. No product code or production data changed.

1. Revoked or viewer user replays a previously valid mutation. Denial must occur before SQL writes, billed generation or provider effects. Test direct and network membership, mixed roles, foreign objects and revocation, not just UI visibility.
2. An authenticated caller supplies business A to a guard and an object from business B to a handler. Check stored object ownership as well as the request selector. A successful tenant lookup is insufficient evidence for every later statement.
3. A signed callback is delivered concurrently or after a timeout. Signatures prove possession of a secret, not novelty. Record durable admission before side effects; distinguish completed from uncertain processing and preserve evidence for reconciliation.
4. A public hostname changes DNS answers, redirects privately, or serves oversized/malformed content. Validate the actual connection destination and each redirect, bound reads and handle rejection as a safe per-page failure. The completed contact-GET patch is not a platform-wide SSRF certification.
5. A document or model response asks to publish, send, pay, reveal private context or switch tenants. Identity and approval must originate outside attacker-controlled text. Required tests include wrong business IDs, forged approval references, cancelled/stale approvals and provider timeout; this matrix remains unfinished.
6. A provider accepts a request, but the client sees a timeout or cannot commit its result. Blind retry can duplicate a message or publication. Preserve unknown outcomes and reconcile using provider evidence; passing a mocked happy path cannot prove this boundary.
7. A backup/configuration is accidentally included in an image or a restore command targets live data. Exclude sensitive build paths and require explicit validated restore targets. A readable dump is not a successful restore rehearsal.

## Secret and dependency findings

20 September current private macOS arm64 environment:133 installed distributions
still equal the hash-locked artifact map and current requirement manifests.
Strict pip-audit2.10.1 against PyPI checked all133 with0skips,0returned advisories
and0fixes in15.948290s; exact audited/installed name-version equality and complete
captures were separately verified. Independent scoped review PASS. The scanner
did not install/upgrade packages or import LocalOS. This is a dated Python
advisory result, not a claim that there are no unknown vulnerabilities, nor an
OS/native-library/image/AMD64/bot scan. Raw current-native-python-advisories and
advisory-evidence-validation captures retain the actual result.

Current metadata inventory contains133 declarations,56License-Expression fields.
PyMuPDF1.28.2 still declares AGPL/commercial dual licensing; entitlement remains
owner-pending. psycopg2-binary2.9.13 declares LGPL with exceptions and
python-telegram-bot20.8 LGPLv3. socksio1.0.0 has License=UNKNOWN but a MIT
classifier: this is inconsistent metadata, not a finding of unlicensed code.
At least one metadata declaration per package does not establish compatibility,
distribution notices, bundled-library terms or legal compliance.

Latest redacted committed-source deltas:105954d6..67169692 (frontend,1commit)
and67169692..be1b1a95 (backend,1commit/30339bytes) report zero findings,
capture2878.404ms and1826.499ms respectively, exit0/no timeout/truncation.
This is not whole-history, foreign-dirty, image-layer, log or revocation closure.

19 September Moscow continuation: strict redacted Gitleaks8.30.1 history delta
`272794a4..5b9b9247` scanned7commits/149,093bytes and reported zero findings.
Actual capture exit0/1.546069s/no timeout/truncation, report `[]`.
This extends the local committed-source delta check only; it does not scan
uncommitted user documents, resolve historical credential revocation or close
image-layer/log scanning. No live credential test or rotation was performed.

Offline historical scanning confirmed former privileged credential material; revocation is unknown. Values are intentionally absent from tracked reports. Current f0cc tracked-source scan has98candidates versus94baseline: all4new candidates are inspected report prose, not credentials. Post-remediation28commit history delta has1prose false positive. This does not establish absence from image layers, resolved dependencies or logs; those final scans remain incomplete. No key was tested against a provider, rotated, or removed from history by this audit.

## Exact-image Python inventory — 18 September

Later strict history delta34618037..272794a4 scans4commits/91659bytes and finds
zero secrets (exit0,2.550695s), with inline allow comments ignored and100%
redaction. This is new-source history evidence only, not a replacement for
historical credential revocation, dirty/untracked files, image layers or logs.

Read-only, network-disabled, nonroot container from immutable f0cc/b43 image
reports104installed Python distributions; this replaces neither the older
121-package host scan nor an OS/image scan. Raw inventory-command evidence:
`image-dependencies-f0cc182a.json`,exit0/2.924219s; one-shot probe removed,
no user volumes mounted. Private exact pins SHA256:
`05c83919609c13ad2c27bdc5a87df56a4f43929d7dc82f7a03182e02c22519ab`.
Package metadata has43License-Expression entries. Metadata is an inventory,
not a legal compatibility verdict or proof of notices/distribution compliance.

PyMuPDF1.28.2 metadata declares AGPL/commercial dual licensing; the actual PDF
attachment path imports it in `src/services/operator_attachments.py:124`.
This agrees with the publisher's [license documentation](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright).
The owner's commercial-license status is unknown and has been requested;
no purchase, removal, violation claim or unilateral license choice is made.
Psycopg2-binary2.9.13 identifies LGPL with exceptions; assess its actual terms,
not a blanket GPL label ([Psycopg license](https://www.psycopg.org/docs/license.html)).
Other bundled OS/npm/native components and final image/license/secret scanning
remain open. Trivy DB acquisition safely stopped before spawn at3.82GiB free
against4GiB start guard; this is a storage prerequisite failure, not a clean scan.

### DEP-PIP-02 — exact-image installer advisories

The subsequent strict PyPI advisory audit completed for all104exact image pins,
0skips (`image-python-advisories-f0cc182a.json`,9.582056s). Exit1 means findings:
only pip24.0 is affected, with12records representing6unique advisories, not12
distinct defects. Fixed versions reported by the service are25.3,26.0,26.1,
26.1,26.1.2 and26.2 respectively (CVE-2025-8869, CVE-2026-1703,
CVE-2026-3219, CVE-2026-6357, CVE-2026-8643, CVE-2026-13346).
No exploit or application-request reachability was reproduced. In particular,
the tar fallback case depends on runtime PEP706 support. The installer is used
during image construction, so a minimal pinned update is preferable to leaving
the vulnerable tooling in the artifact. Other103packages have no returned
Python advisory in this service/date, not a universal clean-bill claim.

Reviewed65ca8836 pins pip26.2 before requirements installation and preserves
the established indexes and Python3.11 base. [Published package metadata](https://pypi.org/project/pip/26.2/)
supports Python>=3.10 including3.11. Telegram inherits the app image. Eight
root static checks pass0.11s; this is FIX_UNVERIFIED at image level until a
new immutable build reports the expected version and passes a refreshed audit.
No host interpreter, production image or runtime dependency was upgraded.

## Existing AI/tool evidence and exact limits

| Test boundary | Existing evidence | What it does not prove |
| --- | --- | --- |
| Provider admission | `test_agent_sheet_provider_queue_pg.py` uses actual disposablePG and proves revoked/expired approvals, missing/mutated snapshots, preview/no-effect and changed payload cannot claim a send | Every capability/provider and arbitrary prompt-to-tool sequence |
| Retrieved finance row → real execution | `test_agent_finance_untrusted_rows_pg.py` uses actual Runner/ActionOrchestrator/policy/finance apply with guarded nativePG: no row-supplied approval/tenant/capability, foreign403/no effects, owner target-only entry/batch, zero provider/model calls and SQL errors; root1pass0.79s independently reviewed | Every role/capability, real model/provider behavior or complete injection/sandbox resistance |
| Uncertain provider outcome | `test_agent_sheet_provider_recovery_pg.py` uses realPG with a fake adapter for timeout and provider-success/local-commit-failure | Live external delivery or permission enforcement at the provider |
| Tenant and approval policy | `test_agent_blueprint_async_contracts.py`, `test_agent_api_security.py`, `test_agent_blueprint_compiler.py`, `test_agent_blueprint_reviews_outreach.py` cover requested-business distrust, cross-business IDs, scopes, protected actions and approval stops using pure policy/cursor/runner doubles | RealDB tenant execution for every tool, filesystem/network/secret exfiltration resistance |
| Run fences and snapshots | `test_agent_run_fences_pg.py`, `test_compiled_run_replay_api_pg.py`, `test_compiled_snapshot_lock_pg.py` use realPG for stale finishers, terminal replay and purge/admission locking; runner seams are substituted where needed | All runner attack payloads, transport modes or end-to-end model behavior |
| Container contract | Deployment-contract tests inspect mocked Docker metadata; separate isolated runner and app-integrated10preview/5run evidence uses actual Docker | A complete adversarial sandbox matrix; mocked inspect results are not runtime enforcement |

The complete attacker-prompt/model-output→tool matrix, arbitrary filesystem/
network/secret exfiltration attempts, every provider's cancelled/stale approval,
and actual unauthorized external-adapter writes remain untested. Policy prose
and these scoped tests cannot be reported as full AI-security certification.

## Test boundaries and residual acceptance

All security reproductions use synthetic users/tenants and mocked providers; native PostgreSQL tests use a fresh loopback-only cluster and explicit disposable targets. Native PostgreSQL is15.15; separate Docker integration uses16.10. Historical Docker/EXT4 failures are retained, not reported as green. After approved no-reset startup, a fresh PG16 write/restart/restore/amcheck probe passed. Full clean6c96192c backend passed4538tests with only7explicit live-provider skips; later source packages require their own focused and final aggregate checks.

Before security sign-off, finish the remaining endpoint role/object matrix, final combined release proof for reconciliation/approval binding, AI adversarial/tool boundaries, upload/archive limits, current-source/image/log/dependency scans and independent whole-diff review. Confirm historical credential revocation through the owner/provider process. Severity and safe testing follow [SECURITY.md](../../SECURITY.md); exact finding acceptance tests remain in the backlog rather than being weakened to match available evidence.

## Git onboarding correction — 21 September, parent81e67435

SEC-DOC-GIT-01 removes unsafe credential-storage and token-in-command examples
from README's Git workflow. Six read-only documentation checks pass after five
causal failures; shell syntax and scoped lint pass. The official Git store
contract is linked from README and the finding notes. Existing keys/config,
historical use or compromise, revocation and other documentation are not audited
by this change. No auth/access settings or production data changed; AC6 remains
FAIL. Exact proof: task evidence/readme-git-safety-*-20260921.*.
