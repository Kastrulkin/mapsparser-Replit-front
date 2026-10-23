# Prepared partner messages: acceptance, 22 October 2026

Prepared copy is saved as native `outreach_campaigns` / `outreach_campaign_touches` drafts. No second delivery queue or campaign model is introduced. A human reviews the exact body, recipient, sender and current version; scheduling and delivery approval remain separate native operations.

## Changes

- Preserve a supplied message body; a negated instruction such as «не отправляй» does not route to sending.
- Reuse the connected Telegram/email adapters to check prior conversations. Missing or incomplete history is an error, never an empty history result.
- Run slow provider reads and draft preparation in the existing durable `operator_async_jobs` queue. Repeated admission uses the same idempotency key; restarts recheck account and business access.
- Separate exact email-subject validation from Telegram messages, which have no subject.
- Show current prepared messages, recipients, sender labels and all touches in the shared web/Telegram/MAX component. Keep prior versions and older candidates.
- Bind explicit content review to the saved message digest and latest campaign version. Do not waive non-copy errors, business access or native delivery preflight.
- State clearly that the final native scheduling approval puts messages into the send queue. Do not describe this action as draft-only.

## Verification

- 69 focused Python checks passed: prepared copy, access revocation, stale review, duplicate protection, worker contracts and sender scope.
- 6 component checks passed: exact copy, explicit review, no send/approve calls during preparation, failed background work, business/unmount races and the exact partner/campaign scheduling link.
- Production frontend build passed using the existing production source baseline plus these changes.
- Seven scoped live prepared sequences / 28 exact messages passed text/subject/sender checks and the native review-to-approval preflight inside transactions that were fully rolled back. The actual records remain unapproved drafts; their delivery queues remain empty.
- Live UI checked with current authenticated LocalOS session at a narrow viewport. MAX uses the shared component; this is not a claim of a live MAX provider/device test.

The broader founder-outreach suite has three pre-existing failures in source-string assertions for unchanged worker/editor behavior. It was not reported as entirely green. Private recipient lists, message bodies, provider receipts and screenshots are stored outside this commit.

## Deployment compatibility

Production has additional uncommitted changes from other work. Partial deployment preserved those files' runtime baseline; this commit changes only the relevant API/job contracts and shared components. Do not deploy an older full checkout over production. No schema migration, customer access grant, delivery, AI generation or global limit change was needed.
