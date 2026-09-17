# Readiness decisions

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

## D-007 — Data-preserving downgrade instead of silent no-op or CASCADE

For the broken work-review rollback, compared: (1) reverse only an empty feature schema, with transaction-held writer locks and guards for every lossy field; (2) permanently forward-only migrations plus backup/restore; (3) force the older parent DROP with CASCADE. Chosen (1) repairs the documented disposable downgrade contract at limited blast radius; (2) remains the required recovery alternative for populated feature data; (3) is rejected because it conceals dependency ownership and can destroy unrelated data. Upgrade behavior is unchanged. Never infer that a successful empty rollback proves populated production rollback safety. The creator-portal obstruction is a separate revision/package and must receive the same independent data-safety analysis.
