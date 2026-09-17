# Production-readiness change log

## SEC-AUTH-01 — Inactive session revocation

Status: **FIX_PROVEN locally**, independent review passed. Not deployed in this audit.

- Central `verify_session` rejects inactive users by default before a protected route can mutate state.
- `/api/auth/me` uses a narrow diagnostic opt-in and retains `403 account_blocked`; normal guards retain their 401 denial. Login's blocked-account contract is preserved.
- Normalize boolean/legacy `False`, `0`, `"0"` once for both guard and returned payload. Independent review caught a first-patch inconsistency for text `"0"`; a real `/auth/me` regression test reproduced it before correction.
- No schema, password, session row or production data mutation. Active-session behavior stays covered.

Evidence:

- Initial red builder reproduction: 2 failed / 12 passed, inactive bearer could execute a protected mutation.
- Review regression red: 1 failed / 2 passed (`legacy_inactive_values`), then 3 passed after normalization. JSON evidence in task `raw/sec-auth-01-legacy-zero-{red,green}.json`.
- Root rerun: `venv/bin/python -m pytest -q tests/test_auth_email_case_insensitive.py tests/test_auth_user_routes.py tests/test_browser_session_security.py tests/test_network_member_access.py` → **42 passed in 5.21 s** (7.391 s captured command wall time).
- Independent reviewer: three principal files, **40 passed**, previous finding closed, no additional blocker in the scoped package.
- Focused Ruff F821 and `git diff --check` pass.

Limits: full backend/PostgreSQL suite and deployed behavior not yet verified. This fix does not close the separate role/tenant audit. Source rollback is possible but would reopen revoked-session access and therefore is not a recommended security mitigation.

## CI-TS-01 — Real app and tooling typecheck in both CI entrypoints

Status: **FIX_PROVEN locally**, independent review passed; no CI deployment or remote change.

Both fast/nightly scripts now invoke the canonical `npm --prefix frontend run typecheck`. Their former root `tsc --noEmit` command exited zero without checking referenced app/Node projects.

Regression tests use actual locked TypeScript, tiny isolated referenced projects, real npm and the current package.json typecheck script. They inject errors separately into app and Node code, prove the former bare invocation misses them, and verify both gates fail; healthy fixtures pass. Non-typecheck gate phases are stubbed, so this is not an execution of the entire nightly job.

- Red baseline: six failing contract cases (healthy invocation contract plus swallowed app/Node errors).
- Initial green / independent rerun: 6 passed in 73.34 s / 70.03 s.
- Independent review recommended exercising the real package script instead of reproducing it inside the stub. Implemented; strengthened suite **6 passed in 84.02 s**. Root inspected the revised fixture and bounded subprocesses.
- `bash -n` and `git diff --check` pass. Canonical actual frontend typecheck separately passed the clean baseline and the finance patch check.

No application behavior, schema or provider effects changed.

## SEC-WH-01/02 — Authenticate WhatsApp and business Telegram callbacks

Status: **FIX_PROVEN locally**, independent scoped review passed. Not deployed or registered with providers.

- WhatsApp requires explicit verify token and raw-body HMAC-SHA256 using `WHATSAPP_APP_SECRET`, before parsing or side effects. Invalid/malformed/Unicode signatures fail closed; missing challenge returns400. Compose forwards the secret to app; staging blanks it and the isolation validator rejects leaked values.
- Telegram uses canonical business UUID plus a domain-separated per-business secret derived from the stored bot token. Indexed tenant lookup precedes constant-time authentication; JSON, transport ledger, workflow dispatch and legacy processing happen only afterwards. Retired raw-token URLs return410; raw token header/query/body authentication is no longer accepted.
- Deployment requires an approved provider rebind with the documented secret header, and matching WhatsApp configuration. Bot-token rotation requires rebind. No provider configuration was changed here; this is an explicit rollout prerequisite, not a backward-compatible automatic production rollout.
- Red evidence reproduced unsigned WhatsApp/Telegram callbacks reaching mocked processing/send and the insecure default verification token. Additional malformed-input cases failed before correction.
- Root final regression/adjacent/config suite: **83 passed in 0.63 s**, 1.078 s captured wall time (`raw/webhook-security-config-final.json`). Independent reviewer reran the same set plus two Docker tests: **85 passed in 0.74 s**; staging-isolation check passed. No scoped blocker.

Residual work remains separate: replay/deduplication, legacy WhatsApp PII logging and token-bearing exception logging need their own reproduction and patch. Authentication alone does not prove idempotency or approval enforcement of every downstream action.

## UX-FIN-01 — Finance import follows the selected business

Status: **FIX_PROVEN locally**, fresh independent scoped review passed. Not deployed.

File, mapping, preview, confirmation, history and status are cleared on a business change. Preview/import/history requests capture their business/version, and stale success, error, finally and parent-refresh completions cannot populate the newly selected scope. Successful import and scope changes also clear the native file input, allowing the same file to be selected again.

- Deterministic deferred-preview and completed-preview/history tests reproduce the original cross-business stale state. Independent review of the first patch found the remaining native file input; its regression was red **2 failed / 2 passed**, then green **4 passed** after the input reset.
- Fresh independent run: `npm --prefix frontend test -- --run src/components/FinanceImportPanel.test.tsx` → **4 passed**, 4.31 s test-command duration. Worker app/Node typecheck and lint pass, with the pre-existing `auth_new.ts:115` warning.
- No backend write contract, money calculation or product layout changes. Other content/services/operator scope candidates are not closed by this fix. Final aggregate frontend and real-API scope checks remain required.

## DOCKER-PUBLIC-01 — Include both frontend builds in clean images

Status: **FIX_PROVEN locally**, independent scoped review passed. No production rollout.

The canonical Dockerfile now builds `build:all` and copies `frontend/public-dist` alongside the main `dist`. Both host artifact directories are excluded from Docker context, so a stale local public build cannot hide this failure.

- Baseline clean image lacked `/app/frontend/public-dist/public-audit/index.html`; the real public entrypoint returned404. New static regression was red2, then green with the existing context tests (4 passed).
- Fix built from a separate clean baseline archive containing only this packaging patch: **39.493 s** with cached dependencies, image `sha256:3dc995eb73758128a56c4c1e42e43f3ca61c9c6725c70b3f12329958b12276f7` (ARM64). Both image HTML entrypoints are nonempty, runtime UID10001, source nonwritable, debug directory writable.
- Isolated app returns **HTTP200** for public audit; synthetic seed and five-flow API smoke pass. Capture: task `raw/docker-public-{build,runtime}-green.json`; smoke log `/tmp/localos-readiness-staging-smoke.log`, exit0.
- Fresh reviewer passed both Docker contract tests and inspected independent runtime evidence. This does not claim final whole-product patched-image proof, AMD64 compatibility, browser-worker packaging or dependency upgrades; those remain separate gates.

## TEST-FIXTURE-01a — Restore PostgreSQL test preconditions

Status: **FIX_PROVEN for these fixture groups**, independently reviewed. Runtime code unchanged.

- Client-info's test-only schema now contains the business projection/access columns and membership tables actually read by the route. Seven baseline failures were setup drift, not seven product defects.
- CAPTCHA/expiry/resume tests use their own migrated PostgreSQL testcontainers instead of arbitrary environment DSNs/minimal shadow queue tables; they seed valid users and required `parsequeue.user_id`. The successful resume fixture satisfies the current parsed-card validator. Expected `delayed_auto` and final `completed` states were checked against the actual worker branches, not broadened into an allowed-status list. Test name now describes automatic CAPTCHA retry accurately.
- Sheets recovery tests reconnect using the same explicit `LOCALOS_TEST_DATABASE_URL` used by their isolated schema fixture. `connection.dsn` omits its password and caused five authentication failures before the provider-boundary assertions.
- Client-info/worker combined: **11 passed in 35.44s**. Independent worker rerun: **3 passed in 30.31s**, raw `worker-fixture-review.json`. Sheets recovery/queue: **16 passed in 2.68s**, raw `sheet-provider-fixture-green.json`; reviewer approved DSN/schema isolation.
- No application validation/permissions/schema changes, new skips, provider writes or production access. Remaining baseline hook/Telegram/browser/migration failures and final full-suite rerun are still open.

## DB-MIG-02a — Safely reverse the empty work-review schema

Status: **FIX_PROVEN for work-review revision rollback**, independently reviewed. The complete rollback chain is still failing on a separate creator-portal dependency; no production downgrade is authorized or performed.

The former no-op downgrade left `business_work_links.action_id` referencing `journey_actions`, preventing an older revision from dropping its table. The corrected downgrade acquires `SHARE ROW EXCLUSIVE` locks in a stable order before inspecting data, refuses to discard review/link/settings data, non-default review fields or work-journal actions, and only then removes this revision's empty objects/columns and restores its predecessor's flow constraint. No CASCADE. Populated installations require a reviewed recovery/compensation plan, not a forced downgrade.

- Existing full-chain migration test reproduced the retained FK. New real-PG tests verify empty upgrade/downgrade, five independent data guards and row preservation, using a UUID-named disposable database inside its own testcontainer.
- Root review identified a check/drop race in the initial patch. A deterministic concurrent INSERT immediately after the guard was red without locks: **1 failed in 12.30s**, `/tmp/localos-db-mig02-red.log`. With locks the writer blocks and cannot commit into the removed table.
- Final suite: **7 passed in 35.28s**, `/tmp/localos-db-mig02-locks-green.log`. Fresh reviewer checked transaction/lock lifetime, all lossy fields, exact predecessor constraint and scoped cleanup. Compilation/diff checks pass.
- Existing `test_web_tracking_postgres.py` now passes the original journey-actions obstruction but fails later at `DROP creator_collaborations`, whose newer creator-portal downgrade is also no-op. This is tracked next, not hidden by weakening the test.
