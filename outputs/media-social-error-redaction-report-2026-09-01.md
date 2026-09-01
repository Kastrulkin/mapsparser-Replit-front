# Media and social API error-redaction report

Status: `FIX_PROVEN`

## Scope

Three generic server-error paths returned internal exception text to an authenticated client:

- media photo file retrieval;
- preparation of one social publication;
- bulk preparation of social publications.

The fixes replace only those generic `500` responses with the shared safe error contract: `code`, a user-safe `message`, and `request_id`. Validation, permission, authentication, tenant checks, rate limits, and manual approval/publication boundaries were not changed.

## Red-to-green evidence

The focused reproducer initially produced `3 failed, 12 passed`. Each failure contained the injected private marker in the HTTP response.

After the fixes, the identical command passed with `15 passed`:

```text
venv/bin/python -m pytest -q tests/test_remaining_api_error_redaction.py
```

The broader media, social-post, SSRF, upload-signature, storage, and accumulated error-redaction suite passed with `247 passed`. The three changed Python files also passed compilation.

## Exact-image staging

Commit `9bda6a53` was rebuilt from a clean detached worktree. Staging used isolated PostgreSQL and Redis, synthetic fixtures, disabled provider credentials, a non-root runtime, and read-only source. The app returned HTTP 200, the five-flow smoke passed, and both changed source hashes inside the container matched the commit.

Two full Playwright runs each completed with `101 passed` and one unrelated `page.goto(..., waitUntil='load')` timeout before business logic. The failed test was different in each run, and both passed immediately when repeated after fixture reseeding. Therefore all 102 scenarios have functional passing evidence, but the stricter single-run `102/102` reliability gate is still open.

## Release state

The fixes are locally and staging-verified. Production was not changed by this package. Production rollout remains a separate approval and is `NO-GO` while the single-run Playwright reliability gate and credential-rotation gates remain open.
