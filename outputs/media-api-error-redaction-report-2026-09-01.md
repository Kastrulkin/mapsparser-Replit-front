# Bug Reproducer

## ✅ FIX_PROVEN — Bug reproduced and fix proven

> Three authenticated media endpoints changed from deterministic exception disclosure failures to the shared redacted API contract; all 22 focused media tests pass.

**Project:** LocalOS
**Bug:** Three media endpoints exposed internal exception text
**Environment:** LocalOS ARM64 Python 3.11 test environment; synthetic Flask fixtures; no production, database or provider calls
**Generated:** 2026-09-01

## Discovery scope

- Media intelligence settings GET and POST error paths
- Media intelligence photo list error path
- Existing media upload, file storage and safe API response tests

## Ranked and tested candidates

| # | Candidate | Contract evidence | Trigger | Location | Confidence | Outcome |
|---:|---|---|---|---|---|---|
| 1 | Media settings GET exposes exception text | Unexpected API failures return code=internal_error, a safe message and request_id. | Authorized settings request while capability lookup raises an internal exception. | /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/api/media_intelligence_api.py:113 | high | REPRODUCED |
| 2 | Media settings POST exposes exception text | Unexpected API failures return code=internal_error, a safe message and request_id. | Authorized settings update while capability persistence raises an internal exception. | /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/api/media_intelligence_api.py:144 | high | REPRODUCED |
| 3 | Media photo list exposes exception text | Unexpected API failures return code=internal_error, a safe message and request_id. | Authorized photo list request while asset lookup raises an internal exception. | /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/api/media_intelligence_api.py:170 | high | REPRODUCED |

## Original report

The continuing security audit identified three reachable authenticated media handlers that serialized unexpected exception text instead of using the shared safe API error contract.

| Contract | Expected | Actual |
|---|---|---|
| Observed behavior | Each unexpected 500 response contains only code=internal_error, a safe user message and request_id. | Each route returned the injected internal exception text in its JSON response before the approved fix. |

## Minimal reproduction

Three focused Flask tests inject deterministic internal failures after authorization and tenant checks into the real route handlers.

**Confirming signal:** The exact suite first produced three new disclosure failures while the earlier three tests stayed green, then passed all six after the patch.

### Reproduction files approved at Gate 1

- [test_remaining_api_error_redaction.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/tests/test_remaining_api_error_redaction.py:116>) — Three media redaction regressions approved at Gate 1.

## Red to green evidence

| Evidence | Before fix | After fix |
|---|---:|---:|
| Exit code | 1 | 0 |
| Timed out | False | False |
| Duration | 270 ms | 420 ms |
| Same command | — | True |
| Broader suite | — | passed |

### Before — failing evidence

```text
..FFF. [100%]
The three newly approved media responses contained the injected internal exception text (test value redacted).
3 failed, 3 passed in 0.27s
```

### After — fixed evidence

```text
...... [100%]
6 passed in 0.42s
```

## Root cause

The three generic exception branches serialized sys.exc_info directly instead of delegating to core.api_errors.internal_error_response.

## Approved fix

Changed only the three unexpected HTTP 500 branches to use internal_error_response with endpoint-specific safe Russian messages.

**Why this is causal:** The changed response branches are the direct output path reached by each deterministic failure; the same assertions now receive the required redacted envelope.

### Production files approved at Gate 2

- [media_intelligence_api.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/api/media_intelligence_api.py:113>) — Three generic media 500 responses now use the shared safe error contract.

## Verification

| Check | Status | Evidence |
|---|---|---|
| Exact reproducer | ✅ passed | 3 failed and 3 passed before; all 6 passed after. |
| Focused media suite | ✅ passed | 22 passed, including upload signature and file storage tests. |
| Syntax and diff validation | ✅ passed | py_compile and git diff --check completed successfully. |

## Reproduce

```bash
arch -arm64 venv/bin/python -m pytest -q tests/test_remaining_api_error_redaction.py
```
```bash
arch -arm64 venv/bin/python -m pytest -q tests/test_remaining_api_error_redaction.py tests/test_media_upload_signature_security.py tests/test_media_file_storage.py
```

## Limitations

- The fixtures prove response redaction, rollback and connection cleanup without a live database or provider.

## Residual risks

- Other raw-exception response candidates in the media module and other APIs remain unproven and require separate scoped Gate 1 tests.

## Notes

- No dependencies, schemas, production data or provider integrations changed.
- Production deployment requires separate authorization.

---

Generated by `$bug-reproducer`. A fix is proven only by the same red-to-green reproducer plus relevant broader checks.
