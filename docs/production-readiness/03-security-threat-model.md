# LocalOS threat model — current audit evidence

Status: incomplete security assessment, not a production approval. Baseline `30262a5b`; local fixes and evidence are recorded in [the change log](06-change-log.md) and [backlog](02-audit-backlog.md). The deployed runtime is a separate artifact described in [the maintenance record](../RUNTIME_RELEASE_20260917.md). A locally fixed boundary is not presumed fixed in production.

## Assets and adversaries

Assets are business/network membership, sessions, provider credentials, private customer communications, finance records, uploaded documents/audio, private knowledge, drafts, approvals, billing limits and the integrity of execution history. Availability of the app, database and workers is also an asset. PostgreSQL is the durable business source of truth; browser state, Redis and provider acknowledgements are not substitutes for committed business history.

Relevant actors include an anonymous API caller, a valid user attempting a foreign-tenant or higher-role action, a former/revoked member, an attacker controlling a retrieved website or uploaded document, a compromised provider credential, and a mistaken operator targeting the wrong deployment or database. No historical exploitation is asserted by this model.

## Trust boundaries and acceptance evidence

| Boundary | Required invariant | Current evidence and limitation |
| --- | --- | --- |
| Browser/bot identity → API session | Missing, expired or inactive identities cannot reach effects; demo sessions remain scope-restricted | SEC-AUTH-01 local denial tests and patch. Complete route/session-kind coverage is not established. |
| Authenticated API → tenant object | Requested IDs, stored object tenant and action permissions agree | Shared `core/auth_helpers.py` checks business/network membership; membership alone does not establish write permission. SEC-RBAC-01 finance write/transaction-target patch is reviewed and locally committed; generic Operator/agent writes and the complete object-derived tenant matrix remain open. |
| Provider callback → processing | Verify source before effects; repeated delivery cannot repeat unsafe actions | SEC-WH-01/02 local signature/secret fixes; Telegram admission handling SEC-WH-03. WhatsApp event IDs are not yet durable admission keys; replay remains open. Provider rebind is a rollout prerequisite. |
| Public website → outbound connection | Every connection uses a validated globally routable destination, including redirects | SEC-SSRF-01 pins contact-page GETs to validated numeric IPs, preserving TLS hostname checks. 76 no-network tests and independent review pass. Unrelated outbound clients are not covered. |
| Untrusted input/retrieval/model output → tool executor | Model text cannot grant tenant identity, approve actions, select unrestricted tools or bypass billing | Product/architecture contract requires external policy, approval and audit. The complete adversarial prompt/output/tool matrix has not yet been executed; do not infer protection from prompt wording alone. |
| Approval/job → local commit/provider effect | Durable identity and replay state prevent duplicate local effects; uncertain provider effects require reconciliation | Same-draft service apply row lock and finance savepoint fixes have real PostgreSQL evidence. Remote publish/send uncertainty is still a candidate needing a deterministic accept-then-fail reproduction. No exactly-once claim. |
| Source/config → image → live service | Tested artifact identity, secrets exclusion, minimal privileges and rollback remain true at runtime | Current build-context exclusion and public-artifact fixes are tested. Production code bind mounts, floating dependencies/base tags, final image scanning and canonical hardened rollout remain gaps. |
| Backup archive → restored database | Explicit trusted archive and isolated target; verify recovery before claiming it | Restore-helper guards are reviewed. Separate local rehearsal compared 288 tables' data/columns/constraints. Full schema/grants and production recovery have not been proven. |

## Representative abuse and failure cases

1. Revoked or viewer user replays a previously valid mutation. Denial must occur before SQL writes, billed generation or provider effects. Test direct and network membership, mixed roles, foreign objects and revocation, not just UI visibility.
2. An authenticated caller supplies business A to a guard and an object from business B to a handler. Check stored object ownership as well as the request selector. A successful tenant lookup is insufficient evidence for every later statement.
3. A signed callback is delivered concurrently or after a timeout. Signatures prove possession of a secret, not novelty. Record durable admission before side effects; distinguish completed from uncertain processing and preserve evidence for reconciliation.
4. A public hostname changes DNS answers, redirects privately, or serves oversized/malformed content. Validate the actual connection destination and each redirect, bound reads and handle rejection as a safe per-page failure. The completed contact-GET patch is not a platform-wide SSRF certification.
5. A document or model response asks to publish, send, pay, reveal private context or switch tenants. Identity and approval must originate outside attacker-controlled text. Required tests include wrong business IDs, forged approval references, cancelled/stale approvals and provider timeout; this matrix remains unfinished.
6. A provider accepts a request, but the client sees a timeout or cannot commit its result. Blind retry can duplicate a message or publication. Preserve unknown outcomes and reconcile using provider evidence; passing a mocked happy path cannot prove this boundary.
7. A backup/configuration is accidentally included in an image or a restore command targets live data. Exclude sensitive build paths and require explicit validated restore targets. A readable dump is not a successful restore rehearsal.

## Secret and dependency findings

Offline historical scanning confirmed former privileged credential material; revocation is unknown. Values are intentionally absent from tracked reports. The tracked baseline scan's candidates were triaged without a confirmed current credential, but that does not establish absence from later files, image layers, resolved dependencies or logs. Those scans remain incomplete. No key was tested against a provider, rotated, or removed from history by this audit.

## Test boundaries and residual acceptance

All security reproductions use synthetic users/tenants and mocked providers; native PostgreSQL tests use a fresh loopback-only cluster and explicit disposable targets. The native version is 15.15, not production's 16. Docker/EXT4 errors invalidated later local image/full-suite results; those failures are retained, not reported as green.

Before security sign-off, finish the endpoint role/object matrix, WhatsApp replay and uncertain-send tests, AI adversarial/tool boundaries, upload/archive limits, current-source/image/log/dependency scans and independent whole-diff review. Confirm historical credential revocation through the owner/provider process. Severity and safe testing follow [SECURITY.md](../../SECURITY.md); exact finding acceptance tests remain in the backlog rather than being weakened to match available evidence.
