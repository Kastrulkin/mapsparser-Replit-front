# Evidence Bundle: p1-security-smoke-20260518

## Summary
- Overall status: FAIL
- Last updated: 2026-05-18T17:34:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `docker-compose.yml` now passes `ALLOWED_ORIGINS`, `RATE_LIMITING_ENABLED`, `RATE_LIMIT_STORAGE_URI`, and `EXTERNAL_AUTH_SECRET_KEY` to both `app` and `worker`.
  - `.agent/tasks/p1-security-smoke-20260518/raw/live-container-env-presence.txt`
- Gaps:
  - Live `.env` still lacks `EXTERNAL_AUTH_SECRET_KEY`.

### AC2
- Status: PASS
- Proof:
  - `.agent/tasks/p1-security-smoke-20260518/raw/live-security-smoke-after-auth-guard.txt`
  - Allowed origin `https://localos.pro` receives `Access-Control-Allow-Origin`.
  - Blocked origin `https://evil.example` does not receive a matching allow-origin header.
- Gaps:
  - None.

### AC3
- Status: PASS
- Proof:
  - `.agent/tasks/p1-security-smoke-20260518/raw/live-security-smoke-after-auth-guard.txt`
  - `/api/auth/login` returned `429` on attempt 6.
  - `.agent/tasks/p1-security-smoke-20260518/raw/live-no-false-429-smoke.txt`
  - `/api/auth/me` returned `401`, not `429`, across repeated checks.
- Gaps:
  - None.

### AC4
- Status: PASS
- Proof:
  - `.agent/tasks/p1-security-smoke-20260518/raw/live-secret-guard-behavior.txt`
  - With `APP_ENV=production` and empty secret, `_get_encryption_key()` raises `RuntimeError`.
- Gaps:
  - None.

### AC5
- Status: FAIL
- Proof:
  - `.agent/tasks/p1-security-smoke-20260518/raw/live-container-env-presence.txt`
  - `.agent/tasks/p1-security-smoke-20260518/raw/live-security-smoke-after-auth-guard.txt`
  - `.agent/tasks/p1-security-smoke-20260518/raw/live-encrypted-auth-count.txt`
- Gaps:
  - `EXTERNAL_AUTH_SECRET_KEY` is missing on live.
  - Live DB contains encrypted external account auth data, so blindly setting a new secret may break decryption.

## Commands run
- `python3 -m py_compile src/main.py src/auth_encryption.py tests/test_security_runtime_config.py`
- `bash -n scripts/smoke_security_runtime.sh`
- `PYTHONPATH=src python3 -m pytest -q tests/test_security_runtime_config.py tests/test_query_adapter.py`
- server `.env` presence checks without printing secret values
- server encrypted external account count check
- `docker compose up -d app worker`
- `scripts/smoke_security_runtime.sh server`
- `scripts/smoke_runtime.sh server`
- production secret guard smoke with `APP_ENV=production EXTERNAL_AUTH_SECRET_KEY=`

## Raw artifacts
- .agent/tasks/p1-security-smoke-20260518/raw/build.txt
- .agent/tasks/p1-security-smoke-20260518/raw/test-unit.txt
- .agent/tasks/p1-security-smoke-20260518/raw/test-integration.txt
- .agent/tasks/p1-security-smoke-20260518/raw/lint.txt
- .agent/tasks/p1-security-smoke-20260518/raw/screenshot-1.png

## Known gaps
- Live `EXTERNAL_AUTH_SECRET_KEY` is missing.
- There are 3 encrypted external account records; rotating/creating a new secret requires user decision and likely re-saving external auth credentials.
