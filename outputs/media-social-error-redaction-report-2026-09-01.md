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

## Release state

The changes are verified locally. Production was not changed by this package. Exact-image staging rebuild and end-to-end verification remain release gates before any production deployment.
