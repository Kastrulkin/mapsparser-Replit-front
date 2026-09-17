# Voice usability release — 2026-09-17

Status: deployed to production on 2026-09-17. Runtime commit: aff55997, branch codex/voice-usability-20260917 (pushed to GitVerse).

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

## Production verification

- Additive migration head: `20260917_content_rules`. Backup: `/opt/seo-app/.deploy/voice-usability-20260917/before.dump` (1.7 GB); archive listing verified, no full restore.
- Partial release of app/worker/operator-worker/telegram-bot and tested frontend. Existing hashed frontend assets retained for open tabs. Runtime source and frontend entrypoint hashes matched all 22 release artifacts; subsequent polling/startup fixes were deployed separately.
- HTTP 200, anonymous rules API 401, schema health check passed. Live Profile UI showed the migrated restriction and its history at the Engelsa 154 pilot location; the network parent is a different business and intentionally has no copied rule.
- Real model rejected the prohibited cartoon claim. First repair failed safely; after passing concrete violations to the repair request, a new repair passed validation. Real check/repair run: 9.5 seconds. No post was saved or published by these probes.
- Real SpeechKit synthesis → asynchronous STT passed with synthetic test speech: 2.9 seconds. This is provider integration, not a physical-device test.
- GigaChat primary returned HTTP 402; the existing configured DeepSeek fallback completed the checks. Primary-provider funding remains an operational issue.
- Intermittent Telegram proxy errors exposed two startup defects: retries reused a closed event loop, and an abandoned pre-poll transport could retain a restart watchdog. Both fixed; final polling tests: 9 passed; startup reconnect delay capped at 30 seconds. Network errors remain possible; saved voice work is independent of delivery.

## Remaining infrastructure blocker

After transient successful polling, the configured Telegram proxy (`192.168.0.177:10809`) again failed connections and the receiver reported unhealthy. Direct Telegram connectivity from the server timed out. The restart/retry fixes cannot guarantee receipt while the only egress route is unavailable. Stable Telegram ingress is therefore **not accepted**, and the pilot must not be described as ready. No proxy credentials, TLS checks or network protections were changed.

## Pilot restrictions and unverified items

Elena's Telegram account is not bound; her business subscription is expired. No subscription override or impersonation is part of this release. A seven-day test-access question remains pending. Her five-task physical-device pilot cannot be marked passed until binding/access are resolved and she performs the tasks. iOS/Android and real incoming voice delivery remain separate acceptance gates.

Telegram send acknowledgment is not proof the person read the message. A transport crash after Telegram accepts a new message but before local delivery recording can repeat a notification; business-command idempotency still protects actions and billing.

## Rollback

Keep the additive migration and profile rules/history. Roll back transport/UI independently if necessary. Do not restore generation/publishing code that ignores already confirmed rules: keep the rule verification boundary or suspend affected generation/publication. Do not delete jobs, journal entries, drafts or history.
