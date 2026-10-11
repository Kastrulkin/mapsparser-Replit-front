# Network content release — 2026-10-11

## Scope

Extends the existing content handoff contract, isolated compiled runtime,
registered sender, per-recipient receipts, operator queue and notification
outbox. No new scheduler, sender, schema or external publication mechanism.

Version 1 remains compatible. Version 2 binds selected businesses, recipients,
connected plan IDs, schedule and renewal reviewer to standing consent. Every
recipient must have access to every selected branch. Runtime output is only
validated post/revision requests; provider refresh and generation remain outside
the sandbox.

Successors use actual last item dates and median existing cadence, never past
dates. Both recipients must have successful receipts for every final variant.
Completion notifications and queue jobs use durable idempotency keys. New
plans remain disconnected until the selected reviewer explicitly approves them.
Renewal refresh records provider availability, observation dates, cached-data
warnings, service changes and actual generation example IDs/voice versions.

## Verification

Targeted suite uses a separate PostgreSQL 16 on loopback port 55439; no
production database is used. Includes old single-target regression tests,
two-branch/two-recipient contract, rights/consent/fence, partial/uncertain
results, shifted final dates, completion deduplication, reviewed successor
lineage, cached source dates and service changes. Frontend production build
passed. These tests do not prove production browser or live provider behavior.

## Deployment gate — not activated

No production changes, network candidate creation, schedule activation or
Telegram sends have been performed for this release. In particular, no
retroactive October 11 delivery is authorized by the regular scenario.

Before deploying:

1. Apply only this release's backend diff to current production files; retain
   the existing editorial industry filter and finance/partnership features.
2. Integrate the UI change into the actual current frontend source. The old
   content release's full frontend build is not a safe replacement for current
   production. A concurrent Today UI release must not be overwritten.
3. Back up changed files/configuration and inspect restart scope. Preserve
   unrelated dirty sources, schedules and delivery receipts.
4. Extend the existing compiled pilot allowlist to the two selected branches
   and this blueprint only; do not enable other existing schedules.
5. Create a version-2 candidate with explicit current plan IDs and both saved
   Telegram user bindings. Compile, preview actual materials and record the
   reviewed consent before enabling the one 10:00 Europe/Moscow schedule.
6. Verify browser menu/chat, real provider refresh, quality/photo preparation,
   and actual recipient-specific receipts. Other businesses remain unchanged.

The release is not considered operational until these deployment and
end-to-end checks pass.

## Compatibility checks and rollout package

The October 11 frontend is built from the current Today UI source at local
revision b41611733, not from the older content release. Only the content
scenario panel and its two type fields are added. The baseline deployed asset
is index-BJLPiouM.js; the compatible build is index-CPNgTZaj.js, retaining the
same index-wEAxYSCo.css. Today and content UI checks: 33 passed. Backend checks:
75 passed, including PostgreSQL integration tests, with no skipped tests.

The backend is ported to current production preimages (13 individual files),
preserving its finance, partnership and editorial industry-filter changes.
The installer aborts if any preimage has changed and backs up each replaced
file. The dispatcher has a blueprint-ID allowlist applied before evaluating
any schedule, including canary checks; its empty-value behavior is compatible.
The two old Riderra schedules are outside this allowlist. The rollout leaves
dispatch disabled until a reviewed network version is approved and activated.
