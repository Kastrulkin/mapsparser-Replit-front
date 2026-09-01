# Bug Reproducer

## ✅ FIX_PROVEN — Bug reproduced and fix proven

> Three reachable API handlers changed from deterministic disclosure failures to the shared redacted error contract; all 37 focused regression tests pass.

**Project:** LocalOS
**Bug:** Three API routes exposed internal exception text
**Environment:** LocalOS ARM64 Python 3.11 test environment; synthetic Flask fixtures; no production, database or provider calls
**Generated:** 2026-09-01

## Discovery scope

- Finance import preview error path
- Media photo upload error path
- Telegram Opportunity Radar ingest error path
- Shared core.api_errors response contract and focused adjacent tests

## Ranked and tested candidates

| # | Candidate | Contract evidence | Trigger | Location | Confidence | Outcome |
|---:|---|---|---|---|---|---|
| 1 | Finance import preview exposes exception text | Unexpected API failures return code=internal_error, a safe message and request_id. | Authenticated import preview while payload parsing raises an internal exception. | /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/api/finance_api.py:1425 | high | REPRODUCED |
| 2 | Media photo upload exposes exception text | Unexpected API failures return code=internal_error, a safe message and request_id. | Authorized upload while asset persistence raises an internal exception. | /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/api/media_intelligence_api.py:258 | high | REPRODUCED |
| 3 | Telegram Opportunity Radar ingest exposes exception text | Unexpected API failures return code=internal_error, a safe message and request_id. | Correctly signed ingest while opportunity persistence raises an internal exception. | /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/api/telegram_opportunity_radar_api.py:160 | high | REPRODUCED |

## Original report

The staged security audit identified three reachable handlers that serialized unexpected exception text into HTTP 500 responses instead of using the shared safe error contract.

| Contract | Expected | Actual |
|---|---|---|
| Observed behavior | Each unexpected 500 response contains only code=internal_error, a safe user message and request_id. | Each route returned the injected internal exception text in its JSON response before the fix. |

## Minimal reproduction

Three focused Flask tests inject deterministic internal failures into the real route handlers and assert the shared safe response contract.

**Confirming signal:** The exact suite first failed 3/3 because each JSON response contained the injected internal string, then passed 3/3 after the approved patch.

### Reproduction files approved at Gate 1

- [test_remaining_api_error_redaction.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/tests/test_remaining_api_error_redaction.py:1>) — Three deterministic redaction regressions approved at Gate 1.

## Red to green evidence

| Evidence | Before fix | After fix |
|---|---:|---:|
| Exit code | 1 | 0 |
| Timed out | False | False |
| Duration | 370 ms | 250 ms |
| Same command | — | True |
| Broader suite | — | passed |

### Before — failing evidence

```text
FFF [100%]
Finance import preview, media photo upload and Telegram radar ingest each returned the injected internal exception in the JSON response (test values redacted).
3 failed in 0.37s
```

### After — fixed evidence

```text
... [100%]
3 passed in 0.25s
```

## Root cause

The generic exception branches serialized str(exception) directly instead of delegating to core.api_errors.internal_error_response.

## Approved fix

Replaced only the three generic HTTP 500 responses with internal_error_response and endpoint-specific safe Russian messages; validation branches and status codes were preserved.

**Why this is causal:** The changed branches are the only response construction points reached by the deterministic injected failures, and the same tests now receive the required redacted envelope.

### Production files approved at Gate 2

- [finance_api.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/api/finance_api.py:1425>) — Finance import preview now uses the shared safe 500 response.
- [media_intelligence_api.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/api/media_intelligence_api.py:258>) — Media upload now rolls back and uses the shared safe 500 response.
- [telegram_opportunity_radar_api.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/api/telegram_opportunity_radar_api.py:160>) — Radar ingest now rolls back and uses the shared safe 500 response.

## Verification

| Check | Status | Evidence |
|---|---|---|
| Exact reproducer | ✅ passed | 3 failed before the patch; 3 passed after it. |
| Focused finance/media/radar suite | ✅ passed | 37 passed in 0.91s, including the three new regressions. |
| Syntax and diff validation | ✅ passed | py_compile and git diff --check completed successfully. |

## Reproduce

```bash
arch -arm64 venv/bin/python -m pytest -q tests/test_remaining_api_error_redaction.py
```
```bash
arch -arm64 venv/bin/python -m pytest -q tests/test_remaining_api_error_redaction.py tests/test_finance_imports.py tests/test_media_upload_signature_security.py tests/test_media_file_storage.py tests/test_telegram_opportunity_radar.py
```

## Limitations

- The fixtures prove response redaction and rollback/close behavior for these three handlers without a live database or provider.

## Residual risks

- Other raw-exception response candidates discovered elsewhere remain unproven and require separate scoped Gate 1 tests.

## Notes

- No dependencies, schemas, production data or provider integrations changed.
- Unrelated working-tree changes were preserved and excluded from this patch.

---

Generated by `$bug-reproducer`. A fix is proven only by the same red-to-green reproducer plus relevant broader checks.
