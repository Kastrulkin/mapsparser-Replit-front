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
campaigns. Their initial dispatch attempts stopped before SMTP with
`riderra_reply_preflight_unverified`: the complete recipient-scope query admitted
authors only, so Riderra received an incomplete legacy receipt. The fix admits
only the canonical Riderra sender, business, buyer workstream, sender mode and
approved-template policy. Author matching is preserved. Recent Riderra sent
messages use the same Message-ID-first reply matcher; messages older than
45 days remain in the legacy path.

The one-file reply-service fix was deployed with a guarded idle-worker stop and
restart of the same app/worker containers. Runtime configuration, image, mounts,
dispatch limits and frontend index were verified unchanged. No replacement
campaign, parallel sync/dispatcher or manually fabricated receipt was used.
All three paused campaigns were resumed through the existing authenticated UI.

The first post-fix native dispatch is proven for Malaca Instituto: a v2 complete
receipt was recorded at 10:38:27.373598 UTC, preflight passed, and the existing
queue became sent at 10:38:28.404769 UTC with a provider message ID. The bounded
history check covered 5,926 UIDs in about 10.6 seconds and found no matching
history. Proyecto Español Alicante subsequently reached sent as well. Exact
Gmail Sent and CRM reconciliation is owned by the Riderra operator; database
send state is not represented as an independently observed Gmail message.

Non-blocking tracking debt: the completed campaign can retain the previous
`needs_attention_reason` although its queue/touch are sent. Do not use that
stale display value as a reason to resend or clear data manually.

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
- Reply-scope fix: 143 focused/adjacent tests passed, five Docker-dependent
  PostgreSQL tests skipped. Independent review reran 123 relevant tests with
  three PostgreSQL skips. All six staged SQL queries passed read-only EXPLAIN
  against the actual production schema; no ANALYZE or DML was used.
- Runtime source SHA-256:
  `c3291dfa594a2e1978da0a372f87555db7ccb6342afbbfc5cea2d6a547ccfaa6`.
  One-file rollback copy:
  `/opt/seo-app/.release-backups/riderra-reply-scope-20260909.OX5cea`.
  App/worker IDs and frontend index were preserved; all services remained
  running after restart, local HTTP was 200 and startup logs had no traceback.
- Settings: ten focused tests, scoped TypeScript and ESLint, independent review,
  production build and deployed asset-integrity checks passed.
- Full-project TypeScript still has five pre-existing AdminLeadRegistry errors.
- The settings screen, sender and all three message previews were checked in
  the authenticated browser. Existing frontend index hash stayed unchanged and
  app/worker remained running; HTTP localhost returned 200. The native send
  records above and the operator's independent provider evidence are tracked
  separately.

## Buyer qualification clarification (2026-09-09)

A prospective passenger-transport buyer does not need public evidence that it already offers or purchases airport transfers. Qualify by buyer type, relevant Riderra geography, confirmed organization identity, and a working organization contact. Never present potential demand as a confirmed order, volume, or interest. The exact airport route and current 005 price in the approved template are an example offer. Do not reinstate `direct official airport-transfer/pickup evidence` as a mandatory filter.

## Queue state after the qualification change (2026-09-09)

The first revised intake created 97 buyer workstreams: 32 Helsinki travel agencies/DMCs, the six released FEDELE schools, 46 accepted members from the 50-row Finland import, and 13 additional exact-city FEDELE schools. Four Finland rows were skipped by the native importer. The new workstreams are enrichment inputs only; they are not approved recipients and do not count as queued outbound until a native template commit creates campaign and queue rows.

At the last read-only check, all 97 enrichment jobs were still `queued`, with no selected contact, native research, campaign, or send-queue row. Do not manufacture these bindings or bypass enrichment. Worker logs show repeated GigaChat HTTP 402 failures while draining the older contact-intelligence backlog. Resume template preparation only for records that later have a `confirmed_source` selected contact, fresh research, exact 005 attestation, and a successful database binding check.

After one more native worker cycle, the Moscow-day outbound footprint was 19 unique companies: 13 `sent` and 6 `queued`, with no uncertain state. Recount it immediately before every grant-backed commit; the maximum remains 150 unique companies for the whole Moscow day.

## Minimal recipient check (2026-09-09)

Per the owner's direct instruction, qualify a new recipient from only three recipient facts: city, occupation/organization type, and a working organization email. Reuse consistent stored values and restore only missing or clearly incorrect values. Do not require separate public proof of transfer orders, transport volume, purchasing authority, personalization, or a detailed dossier.

005 validates the approved message's exact route, currency, price, class, and capacity; it is not recipient-demand evidence. Contact history, duplicates, refusal/suppression, Moscow-day remaining allowance, and native permissions remain independent automatic send checks. Do not convert technical CRM binding fields into added public research or bypass the native grant, manifest, rollback preview, or database binding.

On 2026-09-09 the live partnership batch endpoint was repaired by restoring flat timestamp serialization. Contact intelligence was also changed so a terminal GigaChat draft-provider error does not roll back already verified contacts and research. The job finishes as `needs_evidence`, with no generic draft or outbound queue row. This is operational resilience only: Riderra still requires the exact authenticated grant, current 005 attestation, database binding, suppression/history checks, and the approved template renderer.

The resulting new Riderra intake contains 131 workstreams with current research. Of these, 113 have a selected `confirmed_source` email and can enter a future email manifest; 5 have only `valid_format` email and 13 selected contacts are non-email, so they stay out. One existing recipient, Debla, replied with a price-based refusal and is confirmed as refused in LocalOS.
