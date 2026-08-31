# Bug Reproducer

## ✅ FIX_PROVEN — Bug reproduced and fix proven

> The second three-endpoint batch changed from 3 failed and 3 passed to all 6 passed; both approved batches and the full focused Wordstat suite are green.

**Project:** LocalOS

**Bug:** Six Wordstat API routes exposed internal exception text

**Environment:** LocalOS ARM64 Python 3.11 test environment; no database, provider or production calls

**Generated:** 2026-08-31

## Discovery scope

- src/api/wordstat_api.py error paths
- src/core/api_errors.py safe response contract
- existing API security regression tests

## Ranked and tested candidates

| # | Candidate | Contract evidence | Trigger | Location | Confidence | Outcome |
|---:|---|---|---|---|---|---|
| 1 | GET /api/wordstat/keywords exposes exception text | Internal failures return code, safe message and request_id without exception text. | Authenticated request while keyword collection raises an internal exception. | /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/api/wordstat_api.py:779 | high | REPRODUCED |
| 2 | GET /api/wordstat/search exposes exception text | Internal failures return code, safe message and request_id without exception text. | Authenticated request while search preparation raises an internal exception. | /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/api/wordstat_api.py:952 | high | REPRODUCED |
| 3 | GET /api/wordstat/metadata exposes exception text | Internal failures return code, safe message and request_id without exception text. | Metadata file read raises an internal exception. | /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/api/wordstat_api.py:1137 | high | REPRODUCED |
| 4 | POST /api/wordstat/update exposes exception text | Internal failures return code, safe message and request_id without exception text. | Authenticated refresh request while domain refresh raises an internal exception. | /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/api/wordstat_api.py:1019 | high | REPRODUCED |
| 5 | DELETE /api/wordstat/keywords exposes exception text | Internal failures return code, safe message and request_id without exception text. | Authenticated exclusion request while persistence raises an internal exception. | /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/api/wordstat_api.py:1065 | high | REPRODUCED |
| 6 | POST /api/wordstat/keywords/custom exposes exception text | Internal failures return code, safe message and request_id without exception text. | Authenticated custom-keyword request while persistence raises an internal exception. | /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/api/wordstat_api.py:1115 | high | REPRODUCED |

## Original report

Completion audit found two approved batches of reachable Wordstat API exception handlers returning str(exception), contrary to the standardized safe API error contract.

| Contract | Expected | Actual |
|---|---|---|
| Observed behavior | Each 500 response contains only code=internal_error, a safe user message and request_id. | All six endpoints returned the full injected internal exception text in their JSON responses before their approved batch fix. |

## Minimal reproduction

Focused Flask tests inject a deterministic internal error into the real route handler and assert the shared safe error contract.

**Confirming signal:** Batch one changed from 3 failed to 3 passed. Batch two changed from 3 failed plus 3 passed to all 6 passed.

### Reproduction files approved at Gate 1

- [test_wordstat_api_error_redaction.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/tests/test_wordstat_api_error_redaction.py:1>) — Three endpoint regressions approved at Gate 1.

## Red to green evidence

| Evidence | Before fix | After fix |
|---|---:|---:|
| Exit code | 1 | 0 |
| Timed out | False | False |
| Duration | 700 ms | 310 ms |
| Same command | — | True |
| Broader suite | — | passed |

### Before — failing evidence

```text
...FFF [100%]
The three newly approved mutation responses contained the injected internal exception text (test secret redacted).
3 failed, 3 passed in 0.70s
```

### After — fixed evidence

```text
...... [100%]
6 passed in 0.31s
```

## Root cause

Six catch-all handlers serialized str(exception) directly into client-facing JSON instead of using core.api_errors.internal_error_response.

## Approved fix

Imported internal_error_response and replaced only the six proven 500 responses with route-specific safe messages in two approved batches.

**Why this is causal:** The changed statements are the only response construction points reached by the deterministic failing branches; success, validation, authorization and cleanup paths are unchanged.

### Production files approved at Gate 2

- [wordstat_api.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/api/wordstat_api.py:14>) — Safe shared error response applied to the three approved branches at Gate 2.

## Verification

| Check | Status | Evidence |
|---|---|---|
| Exact reproducer | ✅ passed | Batch one: 3 failed to 3 passed. Batch two: 3 failed plus 3 passed to 6 passed. |
| Focused Wordstat suite | ✅ passed | 13 passed. |
| Rollout manifest | ✅ passed | 246 files verified without mismatch. |

## Reproduce

```bash
PYTHONPATH=src /usr/bin/arch -arm64 venv/bin/python -m pytest -q tests/test_wordstat_api_error_redaction.py
```
```bash
PYTHONPATH=src /usr/bin/arch -arm64 venv/bin/python -m pytest -q tests/test_wordstat_cloud_client.py tests/test_wordstat_api_error_redaction.py
```

## Limitations

- This package covers the six approved Wordstat routes only; other legacy API modules require separate candidate batches and approval gates.

## Residual risks

- Production deployment and live smoke remain separately gated.
- Provider credential rotation remains separately gated.

## Notes

- No provider API, production service or production data was used or changed.
- Success responses, authorization, tenant checks, rollback and connection close behavior remain unchanged.

---

Generated by `$bug-reproducer`. A fix is proven only by the same red-to-green reproducer plus relevant broader checks.
