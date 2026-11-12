# Independent verification gaps

Overall: UNKNOWN. Final code review findings were corrected and independently retested; integration/publication/live evidence is incomplete.

## AC6: UNKNOWN

Fresh check and saved “show replies” remain distinct in menu and chat. The result reports checked, partial or no_sources truthfully, with channel/source freshness; an error retains the previous successful timestamp and saved replies. Retry creates no duplicate inbound events/notifications and a received reply stops applicable follow-ups through existing logic. Public job status stays within the existing queue lifecycle.

Why not proven: Real PostgreSQL inbound deduplication, notification behavior and stopping applicable follow-ups after scoped sync have not been exercised end to end. Unit tests and source inspection do not fully close this criterion.

Minimal reproduction: Run the scoped reply pipeline against a positively disposable PostgreSQL database using only mocked providers, replay the same receipt twice, and verify one inbound/notification plus applicable follow-up stop.

Expected: durable inbound dedup and follow-up behavior proven. Actual: provider/cursor unit coverage only.

Affected files/artifacts: src/services/operator_platform_outreach.py, tests/test_operator_business_outreach_postgres.py

Smallest safe fix / corrective hint: Finish the real-DB integration scenario; retain existing receipt and notification services.

## AC10: UNKNOWN

MAX/Web/Telegram use existing authenticated headers and shared operation semantics. Narrow-screen UI remains usable; double actions are guarded. Scope change, unmount and access loss prevent late private responses from reappearing and clear private state. Transient refresh failure retains saved data with stale/retry feedback. Reopening restores durable history/jobs/results without repeating search/send.

Why not proven: Auth/scope/version/access-loss behavior has component coverage, but actual narrow viewport/MAX device interaction and durable reopen through real runtime remain unverified because browser/runtime access is blocked.

Minimal reproduction: Open candidate UI at 360px and 430px widths in an allowed browser, change business during in-flight requests, expire access and reopen MAX.

Expected: usable touch controls and restored durable history without rerun. Actual: component checks pass; real browser/device proof unavailable.

Affected files/artifacts: frontend/src/components/telegram/PlatformOutreach.tsx, frontend/src/pages/telegram/TelegramControlWorkspace.tsx

Smallest safe fix / corrective hint: Use the same build and persist device/runtime evidence; do not replace component tests with claims of live success.

## AC11: UNKNOWN

Targeted unit/component tests and real Flask-route + disposable PostgreSQL integration cover AC2–AC10 with two businesses, current ordinary-user permissions and real process_chat/approval/queue; only external providers are substituted. The local end-to-end scenario records preview→confirm→worker→company→prepared/campaign queue→mocked delivery→inbound→follow-up stop→reopen. Build passes and changed code introduces no TypeScript diagnostics; baseline failures are separately evidenced. Local mocks/screenshots are never represented as production/provider proof.

Why not proven: Build/static/unit/component evidence is available; real PostgreSQL tests skip (host shmget denied). Complete local real-DB search→approval→worker→queue→mocked delivery→inbound→follow-up stop→reopen has not run.

Minimal reproduction: Start disposable local PostgreSQL, set LOCALOS_TEST_DATABASE_URL to localhost/localos_test*, run opt-in tests and a complete real-route native-approval pipeline.

Expected: real SQL/transactions and whole local work loop pass. Actual: PostgreSQL initialization denied by shmget and integration tests skip; full loop unexecuted.

Affected files/artifacts: tests/test_operator_business_outreach_postgres.py, raw/test-integration.txt, raw/postgres-initdb.log

Smallest safe fix / corrective hint: Complete the integration harness and run it once runtime IPC is available; do not point it at production.

## AC12: UNKNOWN

A concrete tested commit and minimal manifest are created, pushed without force to GitHub and GitVerse, and the same remote SHA is independently checked on both. Any inaccessible remote is explicitly BLOCKED with the actual attempt/output, never inferred from a local commit or another remote.

Why not proven: At verification time candidate changes are not yet committed/pushed; dual remote SHA cannot be attested. GitVerse configured credential preflight failed. Parent publication may follow this review but is not inferred here.

Minimal reproduction: Commit final reviewed manifest; push the same branch to GitHub and GitVerse without force; compare both remote refs.

Expected: identical concrete SHA on both remotes. Actual: publication pending at verification time and GitVerse credential preflight cannot obtain username.

Affected files/artifacts: raw/gitverse-preflight.json, raw/release-manifest.json

Smallest safe fix / corrective hint: Use existing configured authentication; record exact push/ref outputs in publication artifact.

## AC13: UNKNOWN

Before deployment, inspect current /opt/seo-app runtime and preserve newer unrelated functionality, prior artifacts and affected env. Deploy only the verified manifest/dist; recreate affected services if env changed. Check Compose/logs/HTTP/targeted routes, executing container files and loaded frontend bundle against candidate SHA; document rollback. Network/SSH denial keeps deployment/live acceptance BLOCKED, without weakening the user goal or preventing local implementation.

Why not proven: SSH preflight returns Operation not permitted before remote execution, so deployed base, containers, environment, dist and HTTP behavior were not inspected or changed.

Minimal reproduction: Run configured SSH preflight from /opt/seo-app, compare current running versions to manifest, perform narrow deployment and verify containers/bundle/HTTP.

Expected: matching live candidate and rollback evidence. Actual: local SSH connection rejected before remote execution.

Affected files/artifacts: raw/ssh-preflight.json, docs/releases/2026-11-12-miniapp-outreach.md

Smallest safe fix / corrective hint: Resume legitimate server access and perform mandatory preflight before applying changes; no blanket source overwrite.

## AC14: UNKNOWN

On that deployed SHA, authorized MAX Riderra discovers existing riderracs@gmail.com sender, performs a fresh check, executes one concretely approved bounded search and native approved control send, records provider message ID, receives one real control reply, stops applicable follow-ups and restores history after reopen. Verify an ordinary client and two-business isolation too. Evidence includes timestamps and job/campaign/queue/provider/inbound IDs without secrets. Actual recipient, search cost and send terms must be covered by existing applicable authorization; otherwise only that live step is blocked. Gmail access in this development chat and mocked tests do not satisfy this criterion.

Why not proven: No real MAX Riderra or ordinary-client search/send/control-reply/reopen pilot on the candidate deployed SHA exists; deployment and applicable concrete external action conditions remain gates.

Minimal reproduction: On verified deployed candidate perform an authorized bounded Riderra search, native approved control send, actual reply, follow-up stop and reopen; repeat ordinary-client isolation.

Expected: real provider/job/campaign/queue/inbound IDs and timestamps. Actual: no candidate live pilot has run.

Affected files/artifacts: docs/RIDERRA_MINIAPP_OUTREACH_ACCEPTANCE_20261112.md, raw/ssh-preflight.json

Smallest safe fix / corrective hint: Execute only concrete approved recipients/cost conditions and capture real IDs after deployment gate closes.

## Resolved code findings

- Foreign-owned sender metadata leaked via campaign-touch EXISTS: Shared EXISTS branch restricted to platform-scoped sender; source hashes and final tests reviewed.
- Job result reads discarded demo/impersonation session context: Authenticated actor_context threaded through list/load/active bootstrap and restricted outreach results guarded; retry/cancel do not return private results either.
- Platform chat fresh-inbox path discarded session flags and request_id: Current session guard precedes reads/queue and native idempotency key is forwarded.
- Native group/prepared mutations allowed restricted sessions and cached platform sender privilege: Session mutation guard before SQL; service helper reloads current actor, write/capability rights and current superadmin for platform sender.

## Proof-template artifact limitation

The validator unconditionally requires raw/screenshot-1.png and therefore reports valid:false with that one missing file and errors:[]. No dummy image was created. A real browser screenshot remains blocked with AC10/AC11; this is distinct from a source/test regression.
