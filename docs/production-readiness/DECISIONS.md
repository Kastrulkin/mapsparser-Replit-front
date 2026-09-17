# Readiness decisions

## D-012 — Native SQL proof is useful, but is not Docker/PG16 parity

Use a freshly created, loopback-only native PostgreSQL cluster with synthetic data to continue actual transaction/role checks while shared Docker is unavailable. Retain exact server version, data_directory, named test databases, archive commit and no-egress environment; stop only the owned cluster after checks. PG15 results can confirm SQL defects and fixes without pretending to satisfy PG16, image, compiled-runner or full production recovery requirements. Do not replace the original acceptance criteria with easier native-only checks.

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
