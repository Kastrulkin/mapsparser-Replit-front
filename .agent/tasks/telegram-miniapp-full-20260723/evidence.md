# Evidence Bundle: telegram-miniapp-full-20260723

## Summary
- Overall status: PASS
- Release commit: `d2731712`
- Production revision: `20260723_002`
- Verified: 2026-07-23

## Acceptance criteria evidence

### AC1 — PASS
- Every mobile route calls `resolve_control_scope`; object lists derive targets from the resolved scope.
- Action confirmation re-resolves scope and rejects changed/forbidden targets.
- Production role smoke found zero escaped business IDs for platform, network and single-business roles.

### AC2 — PASS
- Today/Tasks/Reviews/Operator use shared summary, inbox, review and conversation services.
- Background parse jobs expose typed status, progress and an honest unavailable reason where paid retry still needs preview.

### AC3 — PASS
- Review counts/list share the same SQL filters and support cursor pagination, location/source/rating/status filters.
- Persisted preview, confirm, expiry and idempotency tests pass; draft edit/copy/manual publication are wired.

### AC4–AC7 — PASS
- Cards, Content, Services, Finance, Partnerships and AI Employees render real scope-filtered rows.
- Unsupported writes remain explicitly read-only; no provider write is simulated.
- Notification settings persist independently by scope.
- Diagnostics is reachable only through a server-resolved platform scope.

### AC8–AC9 — PASS
- Manifest exposes only `available` and meaningful `read_only` modules; hidden deep links cannot open.
- Module/review deep links are checked against the manifest and all scope/object parameters are revalidated server-side.
- Existing Telegram short start, MenuButton and safe message edit implementation remain intact.

### AC10 — PASS
- Mobile shell uses safe-area padding, 44px+ controls, Telegram BackButton, skeleton/slow-loading feedback and reduced-motion fallbacks.
- Prior 360x800 browser pass confirmed no horizontal overflow; final build passes without TypeScript errors.

### AC11 — PASS
- Targeted tests: 13 passed.
- Operator/Telegram/review regression: 159 passed.
- Role smoke covered superadmin, a 4-point network owner and a single owner against production PostgreSQL.

### AC12 — PASS
- Commit pushed to GitHub and GitVerse on `codex/agents-production-beta`.
- Partial deployment updated only three backend modules and `frontend/dist`; app/worker restarted healthy.
- Host/container hashes match; `/` and `/telegram-control?preview=1` return 200; protected mobile workspace returns 401 without auth.

## Commands and artifacts
- `raw/test-unit-final.txt`
- `raw/test-regression.txt`
- `raw/build-final.txt`
- `raw/production-role-smoke.txt`
- `raw/production-owner-smoke.txt`
- `raw/deploy.txt`

## Known limitations (intentional safety boundary)
- External publication, outreach sends, payments and provider mutations are not exposed without a real adapter and governed confirmation.
- Paid refresh retry is displayed as unavailable until it is added to the shared persisted preview executor; the UI does not bypass billing approval.
