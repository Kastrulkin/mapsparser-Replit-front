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

## Initial deployment gate

The initial code commit was not deployed. No retroactive October 11 delivery
is authorized by the regular scenario.

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

## Production verification, October 11

The guarded partial rollout completed. Backup:
`/opt/seo-app/backups/content-network-20261011T111547`. Thirteen backend files
and the compatible frontend distribution were installed. App, worker and
operator-worker were restarted; runner, Telegram bot and other services were
not restarted. HTTP returned 200, the authenticated agents page loaded and the
smart menu remained present. Config allowlists contain only this blueprint
and the two specified branches. Schedule dispatch remains disabled.

Paused network candidate v4 was saved using the existing version store with a
restricted backup of prior pilot records. The real browser compiled candidate
v5 (`c3bde055-24d7-429d-9f47-9b47a3b3502b`), previewed real photos and four
branch/recipient contexts, and approved the version-bound program conditions.
No Telegram request was dispatched. The preview correctly excluded the
unapproved post variants. Final regression suite: 93 passed (including
PostgreSQL), no skips. Frontend and Today checks: 34 passed.

**Remaining operational gate:** the current Eng plan ends on October 11 and
its last packet missed the day-before window. The Dol plan contains future
posts (next October 14), but its platform variants are still `needs_review`.
Compiled approval does not approve posts. Do not backdate sends, mark a missed
last packet delivered, or emit successful plan-completion events without both
recipients' receipts. A real approved future kit and a decision on the ended
Eng plan are required before enabling the recurring schedule. The UI safety
review also blocked proceeding toward activation before that delivery test;
no indirect activation workaround was used.

The final frontend asset is `index-BiB20kVl.js` (the current Today stylesheet
is unchanged). Matching current frontend source files were guarded by their
preimage hashes and saved on the server, so subsequent builds retain this
content panel. Approved-program preview is read-only: it rechecks branch rights
and leaves approved evidence/state unchanged. Its production API was patched
individually with a preimage check. Final runtime commit: `1117cca07` plus the
preceding scoped commits on `codex/network-content-release`; push succeeded.
The final test-only correction distinguishes a row lock (`SELECT FOR UPDATE`)
from mutations when checking that approval evidence is untouched.

An actual dispatcher check in the worker returned zero dispatched jobs and
both Riderra IDs skipped as `outside_schedule_allowlist`; their active version
IDs remain unchanged. Candidate v5 is approved, blueprint remains draft,
global dispatch is false. No success claim is made for live Telegram delivery,
fresh provider collection, generation of a successor or scheduled completion;
these still require the operational gate described above.
