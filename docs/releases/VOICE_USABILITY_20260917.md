# Voice usability release — 2026-09-17

Status: implementation tested; deployment verification recorded below after release.

## Delivered behavior

- Telegram persists voice receipt before download. Existing async jobs perform download, recognition and Operator execution. Delivery retries do not execute the business command again.
- Versioned content rules live in content_voice_profiles, with content_rule_history audit. Owners and active managers may edit their permitted locations; employees submit journal proposals. Network-wide changes require existing Operator approval and recheck every location before atomic apply.
- Rules guard Operator posts/news, content-plan drafts, legacy news generation, card automation, news approval and social publication. One repair is allowed; unavailable or failed verification blocks the new result. Previously approved cartoon restriction is migrated by its exact source ID.
- Selected draft corrections, date changes and undo preserve history and reject stale versions. Rule undo restores its previous version. Relative periods require the business timezone only when needed.
- Web/Mini App share the Profile and business rule editor, dates and history. Pending voice jobs restore after reopening; late responses from another business are ignored. No new-command/listen buttons or speech error notices.
- Telegram receiver restarts after five minutes without a successful poll even if failed network attempts continue; pending updates are not dropped.

## Verification

- 495 backend tests passed, including native PostgreSQL isolated schemas and the durable receive → STT → execution pipeline without Telegram delivery.
- 93 adjacent tests passed: card automation, news scope, content planning, Telegram polling.
- 9 frontend component tests passed; frontend build passed (existing large-chunk warning).
- 6 Playwright cases passed: web and Mini App at desktop, 360px and 393px widths. Providers/API mocked; these are browser emulations, not physical-device proof.
- Database backup completed; pg_restore archive listing succeeded. Full restore was not performed.

## Pilot restrictions and unverified items

Elena's Telegram account is not bound; her business subscription is expired. No subscription override or impersonation is part of this release. A seven-day test-access question remains pending. Her five-task physical-device pilot cannot be marked passed until binding/access are resolved and she performs the tasks. iOS/Android and real incoming voice delivery remain separate acceptance gates.

Telegram send acknowledgment is not proof the person read the message. A transport crash after Telegram accepts a new message but before local delivery recording can repeat a notification; business-command idempotency still protects actions and billing.

## Rollback

Keep the additive migration and profile rules/history. Roll back transport/UI independently if necessary. Do not restore generation/publishing code that ignores already confirmed rules: keep the rule verification boundary or suspend affected generation/publication. Do not delete jobs, journal entries, drafts or history.
