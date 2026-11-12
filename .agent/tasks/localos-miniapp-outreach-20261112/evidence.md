# Evidence Bundle: localos-miniapp-outreach-20261112

Overall status: **UNKNOWN**. Local changes are implemented and tested; whole-goal acceptance remains open. This is builder evidence, not independent sign-off.

Updated: 2026-11-12T12:34:09.893643+00:00

## Recorded checks

| Check | Actual result | Proof |
|---|---|---|
| Backend focused suite | 267 passed, 4 skipped; exit 0 | raw/backend-final.log |
| Native send/preparation + regressions | 109 passed; exit 0 | raw/native-send-session-fix.log |
| Frontend focused suite | 73 passed, 8 files; exit 0 | raw/frontend-final.log |
| Production build | exit 0 | raw/build.txt |
| TypeScript | 57 baseline = 57 candidate; no new diagnostics | raw/typescript-comparison.json |
| Focused lint | exit 0, one hook warning | raw/lint.txt |
| Core/connection suite | 31 passed, 2 failures; same 2 fail on baseline with 19 pass | raw/core-final.log / raw/core-baseline.log |
| Existing worker suite | baseline 1 failure / 7 pass because DATABASE_URL absent | raw/worker-baseline.log |
| PostgreSQL integration | BLOCKED; bootstrap shmget denied, 4 tests skip | raw/test-integration.txt |
| Browser | BLOCKED by host MachPort permissions; no screenshot | raw/environment.json |
| GitVerse / SSH | auth preflight / host network denied | raw/gitverse-preflight.json / raw/ssh-preflight.json |

## Verifier findings corrected

- Business workspace no longer exposes another business sender metadata or global sync watermark via a shared sender.
- Outreach job list/load/retry/cancel and active-job discovery preserve authenticated session restrictions. Demo/impersonated sessions cannot read real outreach results through those routes.
- Platform inbox chat forwards session context and stable request_id to the same shared guard/queue before reading or refreshing real data.
- Retained native group launch and prepared-message mutations reject restricted sessions. Shared sender preparation revalidates actual DB admin/write/capability rights before enqueuing, preserving the native queue and existing approval.

These corrections are covered by the current 267-pass backend run. No verifier verdict was edited.

## Acceptance evidence

### AC1: PASS

Release is implemented on verified f23a30e, preserving its platform GET/POST workspace, durable sync, approved web search, worker routing and existing sending/group launch. A file manifest records the delta; the original dirty checkout is untouched. Existing implementations are reused rather than rebuilt.

Proof: raw/baseline.json; raw/change-manifest.json; src/api/operator_platform_outreach_api.py; frontend/src/components/telegram/PartnershipsMobileModule.tsx

Limits: Only the isolated release checkout was edited; baseline f23 is still HEAD pending publication. Live server baseline is gated separately by AC13.

### AC2: PASS

Shared scope resolution uses current active DB actor and current business/network memberships for every workspace read, job enqueue, action confirmation, job/result read and provider execution. Owner/editor with applicable capability can operate their business without superadmin; viewer may read only; revoked/inactive actor, foreign IDs, stale admin JWT, demo and impersonation cannot start sync/search/send. Platform access requires current superadmin and active LocalOS system business. Explicit Riderra targeting resolves an authorized target while retaining the platform history anchor where applicable.

Proof: src/services/operator_platform_outreach.py:require_outreach_scope; src/services/operator_async_jobs.py:_outreach_job_readable; src/services/outreach_continuation.py:confirm_task_start; tests/test_operator_business_outreach.py; raw/backend-final.log; tests/test_operator_outreach_job_sessions.py; src/api/operator_api.py:operator_mobile_jobs/operator_mobile_job_status/operator_mobile_job_retry/operator_mobile_job_cancel; raw/platform-session-fix.log; src/services/partnership_group_launch.py:authorize; src/services/partnership_prepared_campaigns.py:_authorize_mutation; src/api/prospecting/outreach_routes.py:partnership_prepared_messages; tests/test_partnership_mutation_sessions.py; raw/native-send-session-fix.log

Limits: Current DB rights are executed by real helper code under cursor fixtures. Real PostgreSQL evidence is gated by AC11. Verifier-found session-context bypasses are fixed: list/load/retry/cancel and active-job discovery preserve actor_context; platform chat forwards actor/request_id before any real read or enqueue. Actual Flask endpoint regressions deny demo/impersonation, while standard sessions keep access and unrelated job kinds preserve behavior. Retained native sending/preparation session bypass is fixed: group authorization rejects demo/impersonation before SQL; prepared POST rejects before opening DB; prepare/review_copy/enqueue_preparation check current active DB actor, business write rights and partnership capability. Shared sender preparation checks current DB superadmin instead of a cached token flag. Native suite is 109 pass (81 preserved + 28 regression cases); no external send was performed.

### AC3: PASS

Saved inbox, sender state, searches and job pointers are scoped to the authorized actor/business. Campaign/workstream canonical ownership permits workstream-only replies and excludes ambiguous conflicting ownership; legacy lead intent never widens scope. Stable pagination returns no duplicates or foreign cursor data. A read creates no job/provider request, and active-job discovery never exposes another user's private job/result.

Proof: src/services/operator_platform_outreach.py:inbox_page/workspace; tests/test_operator_business_outreach.py:test_business_workspace_filters_every_private_list_and_does_not_start_work; tests/test_operator_business_outreach.py:test_foreign_cursor_does_not_advance_business_inbox; tests/test_operator_business_outreach_postgres.py; raw/backend-final.log; raw/sender-isolation-fix.log; tests/test_operator_business_outreach_postgres.py

Limits: Canonical campaign/workstream SQL and foreign cursor boundary are inspected and unit-tested; opt-in SQL integration is not executed locally. Verifier-found full sender metadata/watermark exposure was corrected in workspace scoping. Regression suite is 38 pass/4 PostgreSQL skips; optional SQL test covers two-business shared sender isolation.

### AC4: PASS

Connection detection reads both existing external accounts and outreach_sender_accounts, matches business/name/email without equating an empty or truncated filtered result with absence, and exposes saved connection, authentication/sending readiness, last successful sync and safe error states separately. Existing Riderra sender is discovered without creating/reconnecting it. No credential/token/raw private provider error is returned; client detection stays in its scope.

Proof: src/services/operator_connection_status.py; src/services/operator_core.py:_read_connections; tests/test_operator_connection_status.py; raw/connections-core.log; raw/core-baseline.log; raw/core-final.log

Limits: Saved-connection discovery is tested; actual riderracs@gmail.com existence/auth state on current production is UNKNOWN (AC14). Two unrelated core failures reproduce on unchanged f23 baseline.

### AC5: PASS

Client and platform “check replies” enqueue the existing outreach_inbox_sync and commit before provider reads. Duplicate HTTP request_id/clicks and concurrent identical actor/scope/source requests produce one active job; a new check after completion can run again. Workers revalidate rights before external reads and private results. Client collectors receive verified sender plus campaign/batch restrictions; a shared sender cannot collect another business's replies. Existing lease/retry/dedup/kill switch apply; sync never dispatches outreach.

Proof: src/services/operator_platform_outreach.py:enqueue_reply_sync/_authorize_job/sync_reply_channels; src/services/outreach_reply_scope_guard.py; src/api/prospecting/audit_generation.py:_load_telegram_reply_sync_candidates; src/services/outreach_email_reply_service.py; tests/test_operator_business_outreach.py; raw/backend-final.log

Limits: Native queue, transaction advisory lock, same-user/scope idempotency and reauthorization preserved. Shared email/social peer collisions fail closed before provider reads. True concurrent PostgreSQL execution is still gated by AC11.

### AC6: UNKNOWN

Fresh check and saved “show replies” remain distinct in menu and chat. The result reports checked, partial or no_sources truthfully, with channel/source freshness; an error retains the previous successful timestamp and saved replies. Retry creates no duplicate inbound events/notifications and a received reply stops applicable follow-ups through existing logic. Public job status stays within the existing queue lifecycle.

Proof: src/services/operator_platform_outreach.py:business_read_request/process_reply_sync/workspace; src/services/outreach_email_reply_service.py; src/services/outreach_vk_reply_service.py; raw/backend-final.log

Limits: checked/partial/no_sources, source receipt timestamps, scoped mailbox boundaries, last_check restoration, and preservation of full-sender watermarks are unit-tested. Full durable inbound dedup/notification/follow-up-stop after scoped refresh has not been proved through real PostgreSQL end to end.

### AC7: PASS

Ordinary-business menu search and platform targeted search call the actual existing process_chat → operator_task(preview) → prepare_new_task_approval path and return its real action_id. Preview displays audience/geography/count/source/cost conditions and creates no search job/provider request/charge. Existing confirm validates actor, target, terms/revision/credit policy and starts one find_only job; replay cannot start a duplicate. Default remains existing web search, Maps explicit, paid Yandex explicit; no silent paid or Maps fallback. Results use Company Registry and existing ownership/dedup/source persistence.

Proof: src/api/operator_platform_outreach_api.py:search_preview; tests/test_operator_business_outreach.py:test_business_search_uses_actual_chat_approval_and_current_actor; tests/test_operator_platform_outreach.py:test_real_chat_transaction_persists_the_platform_search_approval; src/services/outreach_continuation.py; raw/backend-final.log

Limits: Real process_chat executes against persistence fixtures and emits native action_id; no provider/search before confirm. Targeted platform form uses the target business native action/history for correct ownership while platform workspace aggregates work; no fabricated platform approval. Full PostgreSQL/provider run remains AC11/AC14.

### AC8: PASS

Business miniapp exposes the missing web-search and fresh-reply actions while retaining PreparedPartnershipMessages, PartnershipCollections and PartnershipGroupLaunch for review/send. Review retains correct sender, recipients, full message, digest/schedule and existing approval. Confirmation uses the native queue; queued and provider-accepted/sent states stay distinct. Existing delivery/receipt/reply/follow-up behavior is preserved and cross-business launch is denied.

Proof: frontend/src/components/telegram/PartnershipsMobileModule.tsx; frontend/src/components/telegram/PlatformOutreach.tsx; frontend/src/components/prospecting/PreparedPartnershipMessages.tsx; frontend/src/components/prospecting/PartnershipGroupLaunch.tsx; raw/frontend-final.log; src/services/partnership_group_launch.py:authorize; src/services/partnership_prepared_campaigns.py:_authorize_mutation; src/api/prospecting/outreach_routes.py:partnership_prepared_messages; tests/test_partnership_mutation_sessions.py; raw/native-send-session-fix.log

Limits: Existing native send/group UI and server queue are retained; component tests verify business entry and existing review actions. No real external send occurred. Retained native sending/preparation session bypass is fixed: group authorization rejects demo/impersonation before SQL; prepared POST rejects before opening DB; prepare/review_copy/enqueue_preparation check current active DB actor, business write rights and partnership capability. Shared sender preparation checks current DB superadmin instead of a cached token flag. Native suite is 109 pass (81 preserved + 28 regression cases); no external send was performed.

### AC9: PASS

Chat submit immediately shows one user bubble and an explicit sending/received state; one response/task item is updated through progress/result. Retry uses a stable request_id without duplicate bubbles; a next draft survives completion of the previous request. Accepted messages remain accepted if later polling fails. Background jobs use a compact status rather than an unsolicited blocking global modal. “Check result” has a concrete reachable result/approval destination; approval terms remain fully readable, while long completed answers and voice/files can be expanded.

Proof: frontend/src/pages/telegram/TelegramControlWorkspace.tsx; frontend/src/components/operator/OperatorMessageText.tsx; frontend/src/components/operator/OperatorVoice.logic.ts; frontend/src/pages/TelegramControlPage.test.tsx; raw/frontend-final.log

Limits: Immediate sending/received, stable retry id, one updated reply bubble, next draft preservation, accepted-then-poll-failure semantics, compact restored job and concrete result navigation covered by components. No screenshot exists.

### AC10: UNKNOWN

MAX/Web/Telegram use existing authenticated headers and shared operation semantics. Narrow-screen UI remains usable; double actions are guarded. Scope change, unmount and access loss prevent late private responses from reappearing and clear private state. Transient refresh failure retains saved data with stale/retry feedback. Reopening restores durable history/jobs/results without repeating search/send.

Proof: frontend/src/components/telegram/PlatformOutreach.tsx; frontend/src/pages/telegram/TelegramControlWorkspace.tsx; raw/frontend-final.log; raw/environment.json

Limits: Scope/unmount/access-loss guards and transient snapshot retention are component-tested. Headless Chromium is blocked by host MachPort permission, so actual narrow viewport/device interaction and real MAX reopen are not verified.

### AC11: UNKNOWN

Targeted unit/component tests and real Flask-route + disposable PostgreSQL integration cover AC2–AC10 with two businesses, current ordinary-user permissions and real process_chat/approval/queue; only external providers are substituted. The local end-to-end scenario records preview→confirm→worker→company→prepared/campaign queue→mocked delivery→inbound→follow-up stop→reopen. Build passes and changed code introduces no TypeScript diagnostics; baseline failures are separately evidenced. Local mocks/screenshots are never represented as production/provider proof.

Proof: raw/backend-final.log; raw/frontend-final.log; raw/build.txt; raw/typescript-comparison.json; raw/test-integration.txt; tests/test_operator_business_outreach_postgres.py; raw/job-session-fix.log; raw/platform-session-fix.log; raw/sender-isolation-fix.log; raw/core-final.log; raw/native-send-session-fix.log

Limits: 267 backend tests pass; 4 explicit PostgreSQL tests skip. 73 frontend tests pass across 8 files. Production build exits 0; TypeScript has the same 57 baseline diagnostics with no new diagnostics. Focused lint exits 0 with one existing hook warning. Two existing core failures and one unchanged worker test requiring DATABASE_URL are independently recorded. Real PostgreSQL and complete local search-to-send-to-reply scenario are BLOCKED/unexecuted, so unit tests do not close this AC.

### AC12: UNKNOWN

A concrete tested commit and minimal manifest are created, pushed without force to GitHub and GitVerse, and the same remote SHA is independently checked on both. Any inaccessible remote is explicitly BLOCKED with the actual attempt/output, never inferred from a local commit or another remote.

Proof: raw/gitverse-preflight.json; raw/change-manifest.json

Limits: Publication pending parent commit/push. GitVerse RO preflight failed: terminal prompts disabled and no username returned by configured credentials. Neither GitHub nor GitVerse push is claimed by this evidence snapshot.

### AC13: UNKNOWN

Before deployment, inspect current /opt/seo-app runtime and preserve newer unrelated functionality, prior artifacts and affected env. Deploy only the verified manifest/dist; recreate affected services if env changed. Check Compose/logs/HTTP/targeted routes, executing container files and loaded frontend bundle against candidate SHA; document rollback. Network/SSH denial keeps deployment/live acceptance BLOCKED, without weakening the user goal or preventing local implementation.

Proof: raw/ssh-preflight.json; raw/environment.json

Limits: BLOCKED: SSH to the configured VPS returns Operation not permitted before remote execution. No runtime comparison, deployment, container/bundle/health verification or live rollback preparation was performed. Automatic sandbox escalation is disabled; no access settings were changed.

### AC14: UNKNOWN

On that deployed SHA, authorized MAX Riderra discovers existing riderracs@gmail.com sender, performs a fresh check, executes one concretely approved bounded search and native approved control send, records provider message ID, receives one real control reply, stops applicable follow-ups and restores history after reopen. Verify an ordinary client and two-business isolation too. Evidence includes timestamps and job/campaign/queue/provider/inbound IDs without secrets. Actual recipient, search cost and send terms must be covered by existing applicable authorization; otherwise only that live step is blocked. Gmail access in this development chat and mocked tests do not satisfy this criterion.

Proof: docs/RIDERRA_MINIAPP_OUTREACH_ACCEPTANCE_20261112.md; raw/ssh-preflight.json; raw/environment.json

Limits: BLOCKED by AC13 and missing completed real MAX pilot on candidate SHA. No real bounded paid search, provider send, control reply, provider IDs or production business isolation is claimed. Existing mailbox is not recreated.

## Fresh verification commands

Run from the isolated release root. Unit fixtures are not production/provider proof.

```sh
PYTHONPATH=src venv/bin/python -m pytest -q tests/test_operator_outreach_job_sessions.py tests/test_operator_mobile_active_job.py tests/test_operator_mobile_jobs.py tests/test_operator_business_outreach.py tests/test_operator_platform_outreach.py tests/test_operator_platform_context.py tests/test_operator_platform_entrypoints.py tests/test_outreach_continuation.py tests/test_operator_async_jobs.py tests/test_telegram_control_scope.py tests/test_outreach_email_reply_receipt.py tests/test_operator_business_outreach_postgres.py tests/test_outreach_reply_tracking.py tests/test_partnership_group_launch.py tests/test_partnership_group_launch_api.py tests/test_partnership_prepared_campaigns.py tests/test_partnership_mutation_sessions.py
```

```sh
npm --prefix frontend test -- src/components/telegram/PlatformOutreach.test.tsx src/components/telegram/PartnershipsMobileModule.test.tsx src/components/prospecting/PreparedPartnershipMessages.test.tsx src/components/prospecting/PartnershipGroupLaunch.test.tsx src/pages/TelegramControlPage.test.tsx src/components/operator/OperatorMessageText.test.tsx src/components/operator/OperatorVoice.logic.test.ts src/components/telegram/JobProgressSheet.test.tsx
```

```sh
PYTHONPATH=src venv/bin/python -m pytest -q tests/test_operator_connection_status.py tests/test_operator_core.py
```

```sh
npm --prefix frontend run build
```

```sh
git diff --check
```

```sh
venv/bin/python agents/skills/repo-task-proof-loop/scripts/task_loop.py validate --task-id localos-miniapp-outreach-20261112
```

## Release manifest

raw/change-manifest.json hashes the current product/test/doc delta from f23. Deployment must first inspect the actual live baseline; this delta alone is not permission to overwrite newer unrelated server work.

## Raw artifacts

raw/build.txt, raw/test-unit.txt, raw/test-integration.txt, raw/lint.txt and referenced JSON/logs preserve actual outputs. No screenshot file is supplied because browser launch did not succeed.

## Known gaps

- AC6: checked/partial/no_sources, source receipt timestamps, scoped mailbox boundaries, last_check restoration, and preservation of full-sender watermarks are unit-tested. Full durable inbound dedup/notification/follow-up-stop after scoped refresh has not been proved through real PostgreSQL end to end.
- AC10: Scope/unmount/access-loss guards and transient snapshot retention are component-tested. Headless Chromium is blocked by host MachPort permission, so actual narrow viewport/device interaction and real MAX reopen are not verified.
- AC11: 267 backend tests pass; 4 explicit PostgreSQL tests skip. 73 frontend tests pass across 8 files. Production build exits 0; TypeScript has the same 57 baseline diagnostics with no new diagnostics. Focused lint exits 0 with one existing hook warning. Two existing core failures and one unchanged worker test requiring DATABASE_URL are independently recorded. Real PostgreSQL and complete local search-to-send-to-reply scenario are BLOCKED/unexecuted, so unit tests do not close this AC.
- AC12: Publication pending parent commit/push. GitVerse RO preflight failed: terminal prompts disabled and no username returned by configured credentials. Neither GitHub nor GitVerse push is claimed by this evidence snapshot.
- AC13: BLOCKED: SSH to the configured VPS returns Operation not permitted before remote execution. No runtime comparison, deployment, container/bundle/health verification or live rollback preparation was performed. Automatic sandbox escalation is disabled; no access settings were changed.
- AC14: BLOCKED by AC13 and missing completed real MAX pilot on candidate SHA. No real bounded paid search, provider send, control reply, provider IDs or production business isolation is claimed. Existing mailbox is not recreated.
