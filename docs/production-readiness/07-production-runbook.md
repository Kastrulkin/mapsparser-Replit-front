# Production operator runbook

This is a conservative Docker/PostgreSQL runbook for LocalOS. It describes
confirmed repository controls, not an authorization to deploy, alter data,
send provider traffic, rotate credentials, or delete anything. Runtime state
must be observed afresh; the 17 September maintenance record is historical.

## Before any server action

Local-only parser debug-file change (21 September): keep
`PARSER_DEBUG_BUNDLES_ENABLED` disabled unless diagnostics are explicitly needed.
The pending revision writes bounded value-free shapes, URL categories and HTML
placeholders, without screenshots. `payload.json` and the URL text files are
diagnostic metadata, not replay inputs. Existing files are not rewritten by this
change and may contain private data: do not paste legacy bundles or run the
page.html-printing support helper on them in shared logs. Retention/removal and
access decisions need separate authority. This is not deployment permission.

Local-only pending change AI-APPROVAL-DRAFT-IDENTITY-04 (20 September): after an
authorized future rollout, versionless/stale draft approvals intentionally fail
closed. Do not backfill consent or bulk-approve old decisions. The user should
reject the stale decision, prepare again and inspect every new text/destination.
This needs no schema migration. Local313mocked/16UI passes do not certify native
locking or the later external-dispatch boundary; no rollout is authorized here.

Obtain explicit authority for the proposed production action. Publication,
external send, payment, destructive/bulk change, credential rotation and
database data/schema changes each require their own approval. Use a named tmux
session for long work. Every server command starts in `/opt/seo-app`:

```sh
cd /opt/seo-app
tmux new -s deploy
```

Do not run broad `git pull`, `docker compose down -v`, global Docker prune,
volume deletion, ad-hoc SQL, migration stamping, reset, or a backup script not
reviewed for the incident. SQLite is legacy-only; PostgreSQL is runtime.

## First response and health check

Follow the required order before deciding on a restart or deployment:

```sh
cd /opt/seo-app
docker compose ps
docker compose logs --since 10m app
curl -I http://localhost:8000
```

Then run the smallest changed-feature endpoint check. For a frontend runtime
failure, inspect browser console and app logs first. Check restart/OOM state in
`docker compose ps`/inspect before treating a transient as application code.
Provider transport errors are not proof of a LocalOS regression: record them,
avoid blind retries or re-sends, and preserve approval/idempotency state.

Current source also exposes `/ready`: generic200 only when PostgreSQL connects,
the Alembic revision is accepted and the existing content-learning columns/
indexes are present; otherwise generic503. It uses bounded read-only queries,
not migrations. `/health` remains process liveness. After an explicitly
approved release containing this endpoint, add `curl --fail --max-time 15
http://localhost:8000/ready` to dependency checks; do not assume the older
production snapshot already has it. This is not a provider or full-schema check.

## Interrupted callback delivery — local correction, not yet deployed

The audited source quarantines `sending` claims whose lock is at least one
hour old into the existing `dlq`, with
`callback_delivery_uncertain_after_interrupted_claim`. This age is a conservative
abandonment heuristic, not evidence that the receiver did nothing. The worker
does not automatically replay such rows. Metrics expose `stuck_sending` and
`uncertain_delivery` beyond the recent-created window, with corresponding
alerts. Missing lock timestamps are not recovered by this bounded rule.

For an authorized incident, inspect the tenant's callback outbox and attempt
ledger, then reconcile the receiver's receipt using the unchanged event/dedupe
identity. Do not re-execute the original business action to repair a callback.
If the outcome is still unknown, retain quarantine and escalate. Explicit
replay is a separate approved operation through the existing owner/superadmin
or authorized M2M endpoint; it resets attempts but preserves event/dedupe IDs.
Its `limit` selects the oldest tenant DLQ rows, not one requested event ID, so
review the complete affected batch. Do not invoke broad replay as diagnosis.

The local `openclaw_ops_smoke_recover.sh` correction removes its implicit
alert-triggered replay/dispatch loop. Remaining alerts preserve strict exit2;
manual reconciliation is now reported. This does **not** make the entire
deployment/smoke chain read-only: its capability and outbox sub-smokes still
create test actions and dispatch ordinary pending/retry notifications. Running
that chain against production still requires explicit authorization.

Rollback of this source-only change needs no schema downgrade: preserve DLQ
and attempt records. Returning to older source would remove recovery/visibility
and would re-enable the old unsafe smoke behavior; it is not data recovery.
Local tests use mocked transport and synthetic PostgreSQL only. Receiver
dedupe/ack behavior must be verified separately before an approved release;
see [receiver contract](../OPENCLAW_PHASE2_RECEIVER_SPEC.md).

## Telegram ingress release gate — SEC-WH-02

The new branded-business bot ingress is intentionally not backward compatible:
it requires `business_id` and the derived secret header; the raw-token URL
returns `410`. Owner-bot polling is a different runtime and does not prove this
ingress works. Local tests prove fail-closed admission, not provider registration.
Do not approve a release containing this change without a coordinated cutover
plan for every active branded bot:

- An explicitly authorized operator inventories affected bindings, without
  copying bot tokens or callback secrets into logs, commands, or this repository.
- Approve the exact runtime revision, maintenance window, provider rebind and
  post-cutover controlled receipt. Rebinding against old code can also interrupt
  ingress; neither code-first nor provider-first alone is a zero-downtime plan.
- In that approved window, use the trusted-environment procedure in
  [AI_AGENT_WEBHOOKS_SETUP.md](../../AI_AGENT_WEBHOOKS_SETUP.md). Do not drop pending
  updates or restore unauthenticated/token-in-URL admission as a workaround.
- Check provider URL and a controlled callback accepted by the new runtime.
  `getWebhookInfo` reports URL, pending-update count and recent error fields,
  not the configured secret; a
  matching URL alone is insufficient proof. Provider retries do not guarantee
  zero lost updates during a broken cutover. See the
  [Telegram provider contract](https://core.telegram.org/bots/api#setwebhook).
- Record only business UUID, revision, timestamp and redacted registration/
  URL-match/receipt outcomes. Keep the gate open for any unverified binding;
  reconcile pending or uncertain events before any replay. Do not log headers,
  tokens, message bodies or raw legacy URLs.

No production inventory, token access, provider call, rebind or live receipt
was performed in this audit. The existing security setup is a procedure,
not evidence that a real bot has been migrated.

## Partial deployment

Prefer the smallest affected update. Frontend-only changes are built locally
and deployed with [`scripts/deploy_frontend_dist.sh`](../../scripts/deploy_frontend_dist.sh),
which transfers both `frontend/dist` and `frontend/public-dist` and performs
asset checks. Inspect [`scripts/deploy_backend_src.sh`](../../scripts/deploy_backend_src.sh)
before selecting it: it synchronizes the **whole** `src/` and migration trees
with deletion, also updates entrypoint/runtime scripts, and by default recreates
then restarts app/worker. It is not a file-scoped hotfix command. Use it only
when that complete bundle and restart/migration implications are explicitly
approved; do not upload a dirty worktree or overwrite unrelated server fixes.
For a narrow hotfix, prepare and approve an exact file allowlist and verify
live container files. Do not copy runtime Python files into `/opt/seo-app`
unless they exist at repository root. Verify the live `/app/src/...` file.

The standard narrow service restart is:

```sh
cd /opt/seo-app
docker compose restart app worker
```

Use a full image rebuild or a wider service set only with explicit scope and
disk headroom. Re-run the health order above afterwards.

## Schema and migration gate

Before every production schema change, create and validate a PostgreSQL backup
under an approved production procedure; this runbook does **not** prove that a
production backup can be restored. Schema changes live only in
[`alembic_migrations/versions`](../../alembic_migrations/versions).

[`entrypoint.sh`](../../entrypoint.sh) accepts `startup`, `migrate-only`, and
`schema-check-only`. The migrator uses PostgreSQL advisory lock `883741`, runs
Alembic upgrade with limited retry for a missing revision race, and then checks
the database revision against the graph; see [`scripts/localos_migrator.py`](../../scripts/localos_migrator.py).
`schema-check-only` performs no DDL. There is no general automatic rollback:
review each migration's downgrade and restore plan before upgrade.

## Restore and disk incidents

[`scripts/postgres-restore-latest.sh`](../../scripts/postgres-restore-latest.sh)
is deliberately restricted to a trusted explicit `.sql.gz`, a fresh
`localos_restore_*`/`localos_readiness_restore_*` target, local Unix Docker
context, an owned Compose-labelled PostgreSQL container and loopback port. It
is for **local synthetic rehearsal only**, not production recovery. The local
2026-09-18 proof passed full schema/data/ACL/sequence comparison; its evidence
is [`restore-helper-full-schema-20260918.json`](../../.agent/tasks/production-readiness-20260917/raw/restore-helper-full-schema-20260918.json).
That does not transfer to production backups, AMD64 images, production locks,
or a live recovery decision.

If disk is low or Docker reports storage/I/O errors: stop heavy builds/scans,
record `docker compose ps`, logs and disk state, and ask for scoped approval.
Never clear shared volumes, images or caches blindly. If PostgreSQL is down,
do not apply migrations or restore over it; preserve evidence and escalate.

## Known current limits

The historical runtime-snapshot maintenance used `schema-check-only` and did
not rehearse a production restore or clean canonical image rollout. It reported
revision `20260907_001` and healthy checks at that observation, but also
unresolved Telegram transport instability. See
[`docs/RUNTIME_RELEASE_20260917.md`](../RUNTIME_RELEASE_20260917.md) and the
current [`HANDOFF.md`](HANDOFF.md). Production backup recoverability, current
disk capacity, AMD64 image behavior and live advisory-lock contention remain
unproven until separately measured.

Sources: [`AGENTS.md`](../../AGENTS.md), [`README.md`](../../README.md),
[`entrypoint.sh`](../../entrypoint.sh), [`scripts/localos_migrator.py`](../../scripts/localos_migrator.py),
[`scripts/postgres-restore-latest.sh`](../../scripts/postgres-restore-latest.sh).
