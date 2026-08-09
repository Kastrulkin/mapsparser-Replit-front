# Critical Mini App audit — 2026-08-09

## User tasks checked

| Task | Evidence | Result |
|---|---|---|
| Understand what matters today | One focus card is first and matches the Progress focus | Passed |
| See fresh Telegram community updates | Production has messages from the last 24 hours; the default feed now excludes salon/customer promotions and unclassified sources | Passed after fix |
| Understand the next growth step | Native Progress shows the same focus plus completed steps, obstacles and next actions | Passed |
| Add statistics for one day | Finance → Внести now has an explicit date and a single save action | Passed after fix |
| Load data from CRM | Finance → Импорт contains YCLIENTS/Altegio connection, period preview and one confirmation | Passed after fix; production currently has no configured connections |
| Resume work on mobile | Scope, active work and operator history are server-backed | Passed |

## UX validation

- Checked at 393×852 and 360×800.
- No horizontal document overflow at 360 px.
- Today, Progress and Finance remain native; no desktop redirect in the checked flow.
- The primary action remains visually dominant on each checked screen.
- Hit targets are at least 44 px in the changed Finance flow.
- Application console had no runtime errors. Local preview emitted only Telegram-version and React Router upgrade warnings.

## Technical changes from the audit

- Today refreshes every 20 seconds while work is running and every 5 minutes otherwise, so new reviews and community updates can appear without reopening the Mini App.
- Default community sources are limited to professional communities, experts and vendors. Administrators can still explicitly curate another source.
- CRM import is a separate mobile component instead of a dead link to notification settings.
- Daily finance entry writes the selected day as both period boundaries instead of silently attaching data to the current dashboard period.
- Finance capability manifest now declares CRM connection and sync targets.

## Remaining architectural debt

- `TelegramControlPage` still contains several large inline modules. Continue extracting Finance, Content, Services, Tasks, Reviews and Operator behind the existing mobile data client.
- CRM has a server-side preview token, expiry, changed-data check and one confirmation, but it still uses the canonical Finance preview/sync endpoints rather than `operatoractions`. Move the execution step to the unified action registry before adding scheduled or bulk CRM sync.
- A real connected YCLIENTS/Altegio account is required for provider contract E2E. Production currently has no CRM connections.
- Browser validation used local preview data. Repeat the same viewport pass after release with an authenticated Telegram session.
