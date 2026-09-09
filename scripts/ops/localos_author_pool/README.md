# Existing creator catalog → approved invitations

These are bounded operational entrypoints, not a new outreach policy or a new
source of contact data. Run inside the configured LocalOS app environment. All
selection files, message IDs, recipient data and detailed results stay server-side.
Do not export the production contact list. Logs intentionally contain only counts,
reason codes and artifact hashes.

The existing revocable authorization must approve the exact name-only v2 template
and `localosgo@gmail.com`. The normal shared daily cap, history, reply-sync,
suppression, duplicate and immutable-message checks remain in force.

## Inputs and preparation

Use an immutable reviewed server-local JSON with `records`: creator profile ID,
current `display_name`, exact saved email, `verified_first_name`, `name_proof`,
verified `channel.id`, existing `evidence.id`, and `name_policy` from the neutral
formal-name review. Never treat an arbitrary first word of a channel title or an
affectionate nickname as a formal first-contact name. Never infer a full name.

The required name-policy fields are `style=neutral_formal_first_contact`,
`formal_first_name_verified=true`, and `informal_form_not_expanded_or_guessed=true`.
Those flags are outputs of evidence-backed selection, not substitutes for it.

`author_pool_wave.py --selection /tmp/selection.json --limit 20 --output /tmp/preview.json`
performs batched, all-time provider address searches and a preparation transaction
that is rolled back by default. Add `--commit` only for an authorized reviewed
selection. Use a distinct output path for each run; never overwrite a committed
wave while another process is dispatching it. Prepared records are not sent.

Saved source reuse is explicit: the email must match the current `public_explicit`
public contact and its actual verified channel. A missing evidence-row binding can
be normalized from that channel's saved identity and original timestamps. It is
not a new source inspection: no network research, no `manual_public_source`, no
new observation time, no profile/channel overwrite. Missing or expired original
observations remain blocked. Evidence reuse is keyed by exact canonical URL, not
merely platform/domain.

## Dispatch and verification

The default production owner is the existing worker (`OUTREACH_DISPATCH_ENABLED`
with the approved business cohort). Preparation adds queued records; the worker
checks replies and dispatches them. Do not launch a separate manual mailbox-sync
or dispatcher while that worker is running. The reply-sync service currently has
no cross-process per-sender lock: concurrent checks can overwrite a successful
receipt with a transport failure. That failure must continue to block sends.

Keep production dispatch batches short: `OUTREACH_DISPATCH_BATCH_SIZE=2`,
`OUTREACH_DISPATCH_INTERVAL_SEC=60`, `OUTREACH_REPLY_SYNC_INTERVAL_SEC=60`.
The former default of 20 serial sends could age the same reply receipt beyond
its unchanged 120-second freshness gate. Two is an internal dispatch chunk, not
the daily author allowance. A 60-second dispatch interval also avoids a boundary
burst between chunks. Provider limits, the live grant and daily budget still win.
The shared dispatcher serves other configured campaigns too; check all senders
for in-flight work before recreating it. Never raise receipt age to hide a failure.

`dispatch_author_pool_wave.py --wave /tmp/committed-wave.json --output /tmp/dispatch.json`
is a standalone maintenance entrypoint, **not** a second production worker. Use
it only when the native worker is not processing this sender. It processes only
that wave through the normal dispatcher, refreshes real incoming mail receipts
and preserves configured pacing. Do not use `force_ready`, direct SMTP or another
account to bypass a blocked gate. Stop on failed/uncertain provider outcomes and
reconcile first. A receipt-only pause is resumed through the normal campaign
service after verifying the exact row is still unsent, the grant is live and no
reply/stop has arrived; do not clear pause fields directly.

`verify_author_pool_wave.py --wave /tmp/committed-wave.json --output /tmp/proof.json --commit`
verifies exact Sent sender, recipient, subject, body and Message-ID before writing
canonical creator contact events and next reply-check state. It never resends.
An integration failure after SMTP success is a tracking-recovery action, not a new
send. YouGile's current room-dependent adapter can return zero projections; do
not mistake that for a missing send or fabricate a room just for tracking.

## Regression

`python scripts/ops/localos_author_pool/test_saved_snapshot_reuse.py` covers exact
channel-URL isolation, stable-key reuse and refusal to manufacture fresh evidence
when original observation time is absent. Existing author authorization, shared
daily-budget, SMTP/IMAP and reply-sync suites remain required.
