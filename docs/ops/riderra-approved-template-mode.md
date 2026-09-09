# Riderra: approved buyer email template

## Current release — 9 September 2026

The setting is inside the existing authenticated dashboard:
`/dashboard/settings` → email outreach → agreed Riderra template.
There is no standalone public administration page and no new dispatcher.

The backend, settings component, shared-worker fairness and outreach-first
cadence have been deployed. Author invitations retain their own grant, sender,
template, history checks and daily limit. Static frontend deployment preserves
the running app container with `--no-recreate`; it must not reset its command.

**The audit-schema failure is fixed and the template grant is active.** The user
separately approved the production schema change on 9 September. Migration
`20260909_001` adds only `provider_snapshot_verified` to the existing CHECK.
It was applied through the canonical Alembic migrator at 12:57 MSK after a full
server-local backup, with bounded lock/statement timeouts. The validated
constraint has the former seven values plus the new event; the audit row count
was 96,780 immediately before and after migration. No contact or conversation
rows were changed by the migration and no service restart was needed.

Backup: `/opt/seo-app/data/backups/postgres/local_20260909_125052.sql.gz`
(1,717,562,435 bytes, gzip integrity and SHA-256 checked). Its standard filename
is covered by the existing rotation; no backup pruning was performed.

The original failing POST returned 200 in the authenticated settings screen.
The normal manifest challenge and final PATCH completed, creating grant
`17860474-0842-4c32-bb7b-ab4dd86aae41` for the exact three-record selection.
The unauthenticated grant endpoint still returns 401.

Native rollback-only preparation and then commit both succeeded for three
campaigns. This is **not yet proof of sending**: one first dispatch paused with
`riderra_reply_preflight_unverified`; the exact reply-receipt gap is being
investigated. Do not clear it manually, create replacement campaigns, run a
parallel sync/dispatcher, or weaken freshness checks.

## Existing execution path

1. Use the existing authenticated superadmin settings screen to select the
   verified 005 snapshot and exact recipient records. Read the message previews.
2. Persist the source attestation and exact manifest approval through the
   protected APIs. Account and business scope remain checked server-side.
3. Use `scripts/ops/riderra_buyer_template.py --records-sha256 <live hash>` for
   a rollback-only native preview. `--commit` persists native campaigns/queue;
   this command never grants authority or sends mail itself.
4. The existing native worker owns dispatch and general reply synchronization.
   The operator verifies provider Sent, replies, canonical CRM and next actions.

The approved limit is 150 new unique buyer companies per Moscow day, including
sent, queued, reserved and uncertain attempts. It is not 150 extra recipients
per batch. Use the approved offer and exact 005 route, currency, price, class
and capacity; missing evidence excludes only that candidate.

The initial three-record selection has no existing-campaign conflict. Do not
run the five-record alternative unchanged: two additional records have legacy
draft/paused campaigns, and the preparation command uses one transaction.
Resolve those conflicts through the supported campaign lifecycle, not SQL.

## Verification

- Backend suite: 347 passed, two isolated PostgreSQL tests skipped because a
  local Docker test database was unavailable.
- New audit-event regression suite: 356 passed, three isolated PostgreSQL tests
  skipped because a local Docker test database was unavailable. Four focused
  migration/loader tests were independently rerun: four passed.
- The original production failure was reproduced before migration and passed
  afterward (pricebook POST 200, final grant PATCH 200, active grant readback).
  This proves the audit-schema fix, not end-to-end delivery.
- Settings: ten focused tests, scoped TypeScript and ESLint, independent review,
  production build and deployed asset-integrity checks passed.
- Full-project TypeScript still has five pre-existing AdminLeadRegistry errors.
- The settings screen, sender and all three message previews were checked in
  the authenticated browser. Existing frontend index hash stayed unchanged and
  app/worker remained running; HTTP localhost returned 200. Provider Sent and
  CRM reconciliation must still be verified for the new queue.
