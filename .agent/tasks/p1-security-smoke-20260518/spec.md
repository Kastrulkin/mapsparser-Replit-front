# Task Spec: p1-security-smoke-20260518

## Metadata
- Task ID: p1-security-smoke-20260518
- Created: 2026-05-18T17:26:29+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
P1 autonomous security smoke: verify rate limiting behavior, CORS whitelist behavior, and production EXTERNAL_AUTH_SECRET_KEY guard; implement focused fixes if smoke reveals gaps; verify locally and on live runtime.

## Acceptance criteria
- AC1: Docker runtime passes security env needed by the code: `ALLOWED_ORIGINS`, `RATE_LIMITING_ENABLED`, `RATE_LIMIT_STORAGE_URI`, and `EXTERNAL_AUTH_SECRET_KEY`.
- AC2: CORS live smoke allows `https://localos.pro` and does not allow an unrelated origin.
- AC3: Rate limiting live smoke proves `/api/auth/login` returns `429` after repeated bad attempts, while adjacent normal auth checks do not produce false `429`.
- AC4: Production secret guard behavior raises when `APP_ENV=production` and `EXTERNAL_AUTH_SECRET_KEY` is missing.
- AC5: Live production secret is present and non-weak.

## Constraints
- Do not modify production data.
- Do not rotate or invent `EXTERNAL_AUTH_SECRET_KEY` if existing encrypted external accounts may depend on the current key.
- Server commands must run from `/opt/seo-app`.

## Non-goals
- Do not tune endpoint-specific rate limits unless smoke proves a false positive.
- Do not change application auth/session behavior.
- Do not rotate existing external integration credentials.

## Verification plan
- Build: `python3 -m py_compile ...` and `bash -n scripts/smoke_security_runtime.sh`.
- Unit tests: `PYTHONPATH=src python3 -m pytest -q tests/test_security_runtime_config.py tests/test_query_adapter.py`.
- Integration tests: import `main` and confirm limiter is initialized.
- Live checks: recreate `app worker`, run CORS/rate/security smoke, run runtime smoke, inspect env presence without printing secrets.
