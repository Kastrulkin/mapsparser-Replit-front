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
