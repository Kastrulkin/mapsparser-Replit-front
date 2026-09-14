# Voice control and work observations — Riderra pilot

Status: beta; production activation and seven-day pilot evidence are tracked below. Physical iOS/Android verification is not substituted by browser emulation.

## Execution boundary

The model proposes a tool and arguments. Server code authorizes the actor/business, resolves request-local references, computes publication dates, validates topic allocations and checks versions. Existing Action Orchestrator approvals govern owner grants and policy changes. Existing Operator confirmation governs atomic content-plan replacement; published records are preserved and superseded drafts retain their history.

`operator_tool_plan` disables provider reasoning explicitly, starts at 1,200 output tokens and permits one recovery, capped at 2,400 for truncation. Provider finish reason and reasoning-token counts are recorded without reasoning content. Content-plan generation uses up to 6,000 output tokens per batch and at most ten posts per batch; total allocation is checked before saving. Known weekly counts are resolved by code. Other requests retain the model route.

Large revision previews use `operator_async_jobs` (`content_plan_revision`). The job stores full plan/conversation references; transient short aliases are rebuilt on a new request. Completed preview messages and pending actions are replayed without generation or a second approval. Applying requires a matching plan/item version. The prior erroneous Riderra plan is not changed by rollout or dry-run probes.

## Work journal

`business_work_journal` remains the observation store; `business_work_history` stores review decisions, grants and task-result history. `business_work_links` links existing `journey_actions`; a task can link to multiple observations. No second audio or task store is introduced.

Owners can review; active managers require `business_work_reviewers` grants. Grants use existing `work.policy.apply` confirmation. Staff receive their own observations and permitted statuses, without management decisions; this protection remains after disabling the review flag. Corrections reopen review. A reported operational result does not create a sale.

Review decisions: new, clarification, observing, in_progress, rejected, completed. Rejection/closure require an explanation. Internal tasks carry an assignee and optional supplied deadline. Post text is stored in existing `usernews` when available. Customer messages, card/work-rule changes and bonus proposals are supervised manual tasks unless an existing supported execution path is explicitly chosen. This release does not add a customer messaging integration or promise a bonus. Manual completion is labelled `manual_report`, not provider-verified delivery.

HTTP additions retain existing authentication and confirmation endpoints:

- `GET /api/work-journal/review`
- `POST /api/work-journal/<id>/decision`
- `GET/POST /api/work-journal/<id>/actions`
- `POST /api/work-journal/<id>/actions/complete`
- `GET/POST /api/work-journal/digest-settings`

The shared WorkJournal component exposes “На разбор”, management decisions, linked tasks, rights preview and digest time in web/Mini App. Voice enters the same tools directly. Listen buttons and TTS-error messages are not restored.

## Notifications and flags

`OPERATOR_WORK_REVIEW_BUSINESS_IDS` enables new review mutations and digests; `OPERATOR_PLAN_REVISION_ASYNC_BUSINESS_IDS` enables plan revision tools and background previews. Initial allowlist: Riderra only. Existing `OPERATOR_WORK_JOURNAL_BUSINESS_IDS` still controls observation input.

Review delivery uses the existing journey notification outbox. It does not enable unrelated journey notifications when their global flag is off. The default daily cutoff is 18:00 in the business timezone, only for new records. Without a timezone there is no daily digest. Explicit “срочно” creates a separate notification; “не срочно” does not. Recipients are reauthorized when collecting delivery. First activation considers the previous day, not the entire archive.

## Verification evidence

- PostgreSQL regression run: 585 passed in the final isolated release snapshot.
- Frontend: 26 tests passed across journal, voice and Mini App.
- Chromium browser: review → assign → accept, keyboard focus and 390px layout passed. Mocked API; not a physical device or live Telegram test.
- Real provider probe on Riderra, no plan writes: 1,848 input tokens before reading; 3,949 after reading, zero reasoning tokens. It exposed redundant clarification, so the explicit weekly-count scenario now selects its tool in code.
- Real generation preview: four weekly posts, two Thailand, one China, one Tanzania; nine old unpublished entries proposed for archival, none actually changed.
- Production backup: custom PostgreSQL archive, fully read by pg_restore to verify archive integrity; no claim of a full restore test.
- Repository baseline TypeScript errors in AdminLeadRegistry and InfluencersPage are outside this change. No errors reported in changed files; production build is checked separately.

Release logs and screenshots: `/tmp/localos-voice-journal-release/` on the implementation host. Production staging: `/opt/seo-app/.deploy/voice-journal-20260914/`.

## Remaining pilot gates

Run actual iOS/Android voice inputs, test the client-specific external/manual route with a chosen recipient, and observe seven days of real use. Compare token usage, latency, completion and clarification rates. These gates are not reported as passed by unit tests, a dry-run preview or browser emulation. Broader rollout requires them.

Rollback: empty the two new allowlists and recreate only app/worker/operator-worker/telegram-bot to apply environment changes. Cancel queued revision jobs using the existing job cancellation API. Keep the migration, journal/history, tasks and confirmed results. Existing text paths remain available; journal privacy must not be weakened by rollback.

Migration compatibility: the already deployed `20260914_riderra_runs` migration is preserved verbatim as the predecessor of `20260914_work_review`; its existing production table is not recreated or modified by this release.

## Production activation — 14 September 2026

Deployed at 13:20 UTC with both new allowlists restricted to Riderra. Alembic is at `20260914_work_review`. App, worker, operator-worker and Telegram bot restarted; other services preserved. All 23 backend/migration live hashes matched the release manifest. HTTP and HTTPS returned 200; anonymous review read returned 403. Owner review access and live journal inbox succeeded. The pre-existing plan still has 13 entries. Daily notifications use the resolved business timezone Europe/Tallinn, default 18:00.

Live authenticated browser: journal and review filters loaded with no console errors. Added a discoverable journal link under More → Business. Final production frontend build passed. No test observations or customer messages were inserted into Riderra.

Backup: `/Users/alexdemyanov/Backups/LocalOS/20260914-voice-journal/database.dump` (private permissions, SHA256 and full archive-read verification beside it). Targeted daily pilot checks scheduled in the current Codex task through 21 September; automation `riderra-2`. Physical-device and seven-day gates remain outstanding.
