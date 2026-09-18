# LocalOS threat model — current audit evidence

Status: incomplete security assessment, not a production approval. Baseline `30262a5b`; local fixes and evidence are recorded in [the change log](06-change-log.md) and [backlog](02-audit-backlog.md). The deployed runtime is a separate artifact described in [the maintenance record](../RUNTIME_RELEASE_20260917.md). A locally fixed boundary is not presumed fixed in production.

## Assets and adversaries

Assets are business/network membership, sessions, provider credentials, private customer communications, finance records, uploaded documents/audio, private knowledge, drafts, approvals, billing limits and the integrity of execution history. Availability of the app, database and workers is also an asset. PostgreSQL is the durable business source of truth; browser state, Redis and provider acknowledgements are not substitutes for committed business history.

Relevant actors include an anonymous API caller, a valid user attempting a foreign-tenant or higher-role action, a former/revoked member, an attacker controlling a retrieved website or uploaded document, a compromised provider credential, and a mistaken operator targeting the wrong deployment or database. No historical exploitation is asserted by this model.

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

1. Revoked or viewer user replays a previously valid mutation. Denial must occur before SQL writes, billed generation or provider effects. Test direct and network membership, mixed roles, foreign objects and revocation, not just UI visibility.
2. An authenticated caller supplies business A to a guard and an object from business B to a handler. Check stored object ownership as well as the request selector. A successful tenant lookup is insufficient evidence for every later statement.
3. A signed callback is delivered concurrently or after a timeout. Signatures prove possession of a secret, not novelty. Record durable admission before side effects; distinguish completed from uncertain processing and preserve evidence for reconciliation.
4. A public hostname changes DNS answers, redirects privately, or serves oversized/malformed content. Validate the actual connection destination and each redirect, bound reads and handle rejection as a safe per-page failure. The completed contact-GET patch is not a platform-wide SSRF certification.
5. A document or model response asks to publish, send, pay, reveal private context or switch tenants. Identity and approval must originate outside attacker-controlled text. Required tests include wrong business IDs, forged approval references, cancelled/stale approvals and provider timeout; this matrix remains unfinished.
6. A provider accepts a request, but the client sees a timeout or cannot commit its result. Blind retry can duplicate a message or publication. Preserve unknown outcomes and reconcile using provider evidence; passing a mocked happy path cannot prove this boundary.
7. A backup/configuration is accidentally included in an image or a restore command targets live data. Exclude sensitive build paths and require explicit validated restore targets. A readable dump is not a successful restore rehearsal.

## Secret and dependency findings

Offline historical scanning confirmed former privileged credential material; revocation is unknown. Values are intentionally absent from tracked reports. Current f0cc tracked-source scan has98candidates versus94baseline: all4new candidates are inspected report prose, not credentials. Post-remediation28commit history delta has1prose false positive. This does not establish absence from image layers, resolved dependencies or logs; those final scans remain incomplete. No key was tested against a provider, rotated, or removed from history by this audit.

## Exact-image Python inventory — 18 September

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
