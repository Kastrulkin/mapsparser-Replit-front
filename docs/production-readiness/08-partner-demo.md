# Synthetic partner demo: 10–15 minutes

Status: **partially exercised in the managed browser; not yet demo-ready**.
Local fixture correction `1e955718` now seeds the actual drawer's `match_json`
with a clearly synthetic, unconfirmed local-audience hypothesis (`needs_evidence`).
Two SQL-contract tests and44overlapping adjacent tests pass with independent
review. It has NOT been applied to the retained stage or browser-rehearsed.
Apply only the exact missing synthetic artifact after checking its identity;
do not replay the whole seed, which updates unrelated retained fixture fields.
Review-copy localization now has3/3actual browser checks across RUdesktop,
ENlaptop and ELmobile (5.950617s), exact clipboardtext and no observed runtime
errors. This narrow newfrontend/historicalsyntheticbackend check is not a
complete presenter rehearsal; see05 for build-configuration failures retained.
On 19 September Moscow, login/maps/review/content and real synthetic finance
preview → apply → duplicate retry were exercised. Both finance attempts skipped
two existing duplicates and retained both earlier history entries. The retained
partnership fixture instead showed `[E2E] Partnership Journey` without the
expected audience-overlap reason. Reconcile that fixture without resetting
existing data before the complete presenter rehearsal. A file-picker tool delay
also prevents treating the elapsed session as a paced10–15minute demo.
Evidence: task raw `managed-browser-demo-20260919.md`; no provider/customer run.

18 September observed preparation issue: a view-only rehearsal probe stopped
after154.774seconds at Content; it is not a completed10–15minute rehearsal.
The retained synthetic staging had a newer publication-reconciliation test
plan, so `/dashboard/content` selected that plan rather than the original seed.
Read-only database checks confirm the original planned item still exists.
Select the intended demo plan explicitly via the supported `plan_id` URL
parameter; never clear the other plan or reseed an existing environment merely
to make a demo pass. Also wait for the named business/map data, not just the
card-page heading: the first screenshot captured a loading state.
Seeded reviews and manual-publication text were observed successfully.

Use only an already-running, release-owner-verified isolated LocalOS staging
project and the deterministic accounts from
[`scripts/seed_journey_staging.py`](../../scripts/seed_journey_staging.py):
`owner@localos-e2e.invalid`, `[E2E] Салон Север`, and the synthetic admin when
the internal compiled pilot is shown. Never enter a real customer, provider
credential, customer contact, or production URL.

[`COMMANDS.md`](COMMANDS.md) records historical one-shot startup evidence and
must not be replayed. The durable isolation contract is
[`docker/audit-ingress/README.md`](../../docker/audit-ingress/README.md); it is
for the release owner to prepare the project, not an instruction to start one
during this demo.

## Story and presenter boundary

The owner’s job is to turn a visible local-business opportunity into a reviewed
LocalOS action, then see the result recorded. The demo must say explicitly:
LocalOS prepares drafts, previews and internal proposals; publishing, outreach,
payments and provider writes remain manual/approved boundaries.

If a provider-dependent screen is unavailable, use the seeded synthetic result
or the visible disabled/fallback state. Do not retry an external send or claim
that a draft was delivered.

## Six-step route

1. **Business and map context — 2 min.** Sign in as the synthetic owner,
   explicitly select `[E2E] Салон Север` (fresh login was observed selecting
   `[E2E] Салон Центр`), then show the seeded Yandex map link
   and business context. Do not promise a visible opportunity, task, queue item
   or next action from the basic seed: those require an additional journey
   claim/preparation that this walkthrough does not perform. The basic seed does not prove a
   claimed `/dashboard/progress?journey_action` route: do not claim an action
   or navigate to that route during the demo. Say that any refresh result is
   synthetic/recorded for this demo.

2. **Reviews — 2 min.** Open the unanswered review queue and open the seeded
   reply draft. Expected: draft text plus a clear review/manual-publication
   boundary. Do not click a provider publication control.

3. **Content — 2 min.** Open the seeded planned content item. Expected: its
   theme and date; the observed UI labels its backend `planned` state
   `Черновик`, not a confirmed scheduled publication. Its `draft_text` is intentionally
   empty, so do not present an editable content draft, saved news item or a
   posted Telegram/VK message.

4. **Finance — 2 min.** Use the exact synthetic CSV exercised by
   [`owner-reviews-finance.spec.ts`](../../frontend/e2e/staging/owner-reviews-finance.spec.ts):

   ```csv
   record_type,date,type,category,amount,comment,external_id
   entry,2026-08-29,revenue,sales,5000,E2E,e2e-income
   entry,2026-08-29,expense,materials,1000,E2E,e2e-expense

   ```

   Expected: preview first, an explicit internal apply decision, then recorded
   import/history. Do not present it as a CRM connection or real financial data.
   If this exact CSV was already applied during tests/rehearsal, duplicate rows
   should be skipped; demonstrate that outcome instead of clearing data during
   the demo or promising two newly imported records.

5. **Partnership — 2 min.** Open the seeded nearby-business/workstream card.
   Expected after the scoped fixture update: an explicitly synthetic hypothesis
   under `Общие направления`, `Что нужно для проверки совместимости` and
   `Пока не подтверждена`, plus the Candidate/manual-selection state. This is
   not a confirmed partner assessment or a specific backend next-action label.
   The basic seed creates neither a message draft nor an
   approval; do not present either, or a reply/external send, as simulated.

6. **Agents / compiled table — 3 min, optional.** Use only the separately
   prepared, already-running and release-owner-verified compiled fixture. Its
   historical evidence in [`COMMANDS.md`](COMMANDS.md) has ten previews and five
   actual sandbox runs with a report/CSV. Expected: rules, example, preview,
   approval and recorded table report. This is an admin-only internal JSON
   pilot, not a finished nontechnical editor; model generation and provider
   writes are not being demonstrated. Never substitute seeded “completed” rows
   for runner execution.

## Fallbacks and close

For maps, provider refresh, external accounts, outreach and publication,
provider-disabled staging is the expected safe fallback: show the seeded
status, stored result or explanation rather than diagnosing the live provider.
For the compiled step, skip it if the real approved fixture was not prepared;
do not fabricate completion.

Close by returning to the owner outcome: LocalOS keeps the task, review point
and result visible, while the business keeps control over external actions.
The current browser evidence covers synthetic staging flows; it does not prove
a partner-facing live demo, production performance, or external delivery.
