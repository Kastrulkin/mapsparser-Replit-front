# Bounded migration and rollback review — 2026-09-06

Scope: the new Alembic chain `20260906_001` through `20260906_012`, the
runtime callers whose DDL was removed in this package, and the prepared
forward/rollback startup path. This is a source and schema review; it does
not authorize or perform a production write.

## Verdict

**Release-compatible after the focused 011 correction below.** I found no
remaining migration-chain blocker in the reviewed scope. The release remains
a partial architecture release: it deliberately keeps the legacy runtime DDL
callers and the generic provider transaction boundary for later R3/R6 work.
Those exclusions must not be presented as completed DDL-rights separation.

## Blocking issue found and corrected

`20260906_move_prospecting_runtime_ddl.py` originally mapped legacy
`status = 'delivered'` to `pipeline_status = 'contacted'`. This contradicted
the already-owned manual CRM migration
`20260421_add_manual_first_crm_flow.py`, where delivery maps to
`waiting_reply`. The reconciliation only changes blank statuses or
`unprocessed` rows with a non-`new` legacy status, but it would still have
given affected legacy deliveries the wrong next-work state.

The migration now maps `sent` to `contacted` and `delivered` to
`waiting_reply`. The focused PostgreSQL regression creates the relevant
legacy rows and verifies sent, delivered, second-message, converted, and
an explicit manual `postponed` status. It was red before the correction
(`1 failed, 1 passed`) and green afterwards (`2 passed`):

- red evidence: `raw/review-migrations-pg-red.txt`
- green evidence: `raw/review-migrations-pg.txt`
- changed files: `alembic_migrations/versions/20260906_move_prospecting_runtime_ddl.py`, `tests/test_prospecting_runtime_schema_pg.py`

Read-only production inspection found 87 rows eligible for reconciliation,
all `imported` (81) or `shortlisted` (6); there were no currently eligible
`delivered` rows. The correction is still required for safe replay and
future legacy rows.

## Chain and data review

- `001`, `002`, `003`, `007`, `008`: additive fields/tables and durable
  evidence only. Their intentionally empty downgrades preserve run,
  snapshot, learning, approval, and admission evidence. This is compatible
  with the documented rollback strategy of restoring old code against the
  expanded schema, rather than running destructive Alembic downgrade.
- `004`, `005`, `006`, `009`, `010`: SQL matches the retired runtime
  bootstrap shapes. Existing-table compatibility is handled with
  `IF NOT EXISTS` / additive columns. The booking-agent and business-type
  seeds use conflict-safe keys and do not overwrite existing administrator
  edits. The actual production outbox has 26 non-null dedupe keys and no
  duplicate key groups, so `uq_action_callback_outbox_dedupe_key` can be
  created without a data conflict.
- `011`: `partnershipleadartifacts` has the same primary-key/FK shape as the
  retired helper. Production already has that table and a primary-key
  constraint, so `CREATE TABLE IF NOT EXISTS` cannot leave this installation
  with the known weak pre-existing shape.
- `012`: correctly contains no schema mutation. The sales-room tables and
  compatibility columns are owned by preceding named migrations; the new
  runtime helper checks required columns rather than recreating them.

## Startup and rollback compatibility

`scripts/localos_migrator.py` serializes upgrade with advisory lock 883741
and validates the expected Alembic head. `entrypoint.sh` has a
`schema-check-only` mode, which makes app/worker startup fail visibly if the
head is wrong without trying DDL. The independent isolated proof reported by
the parent package starts backend `ffc54c19` against head `20260906_012`
with the new entrypoint/migrator/checker and returns health, login, and Today
successfully. That supports the stated rollback: restore old application
artifacts while retaining the new migration directory and startup scripts;
do not downgrade or automatically restore the database.

The server release runbook must apply `schema-check-only` only to containers
that execute this entrypoint. The Telegram container does not use it, so it
must be started only after the migration/head check rather than being given
an ineffective environment claim.

## Deliberately deferred, not release blockers for this package

Source still contains runtime DDL outside this bounded removal, including
`src/legacy_routes/public_requests.py`, `src/core/agent_api_security.py`,
`src/telegram_reviews_bot.py`, `src/ai_agent_tools.py`, and related legacy
paths. Also, generic provider execution still has the R3 transaction issue.
The package keeps the existing database role and worker `all`, and leaves
new compiled execution/personalization flags off in production. Therefore
the release should not revoke runtime DDL rights or enable those paths.

## Required release guardrails

1. Re-read production head immediately before release; the reviewed head was
   `20260905_004` and target is `20260906_012`.
2. Take and validate a fresh database and artifact backup before migration.
3. Apply only from the reviewed source manifest, run one migrator, then run
   its read-only schema check before app/worker restart.
4. Preserve the new migration/startup files during rollback and never run a
   blind downgrade.
