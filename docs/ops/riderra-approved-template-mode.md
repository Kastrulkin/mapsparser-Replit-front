# Riderra: approved buyer email template

## Current release — 9 September 2026

The setting is inside the existing authenticated dashboard:
`/dashboard/settings` → email outreach → agreed Riderra template.
There is no standalone public administration page and no new dispatcher.

The backend, settings component, shared-worker fairness and outreach-first
cadence have been deployed. Author invitations retain their own grant, sender,
template, history checks and daily limit. Static frontend deployment preserves
the running app container with `--no-recreate`; it must not reset its command.

**Activation is not complete.** The first live pricebook-attestation request
failed because `ck_outreach_sender_account_event_type` only permits seven legacy
event types. The new `provider_snapshot_verified` event is not yet permitted.
No Riderra template grant or new send queue was created by that failed request.

The remaining change is an explicitly approved additive schema migration for
that audit event. Do not relabel tariff verification as a successful SMTP
preflight, remove the CHECK, delete audit rows, or bypass this failure with
direct SMTP or fabricated approvals.

## Intended execution after the migration

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
- Three native SQL shapes were EXPLAINed against production read-only, without
  ANALYZE. This did not validate the new INSERT event-type constraint; the live
  failure above is the required missing regression.
- Settings: ten focused tests, scoped TypeScript and ESLint, independent review,
  production build and deployed asset-integrity checks passed.
- Full-project TypeScript still has five pre-existing AdminLeadRegistry errors.
- The settings screen, sender and all three message previews were checked in
  the authenticated browser. End-to-end activation remains failing until the
  schema migration is approved, tested and deployed.
