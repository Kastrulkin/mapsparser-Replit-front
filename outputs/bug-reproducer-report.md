# Bug Reproducer

## ✅ FIX_PROVEN — Bug reproduced and fix proven

> The approved regression cases failed on the reported Operator path before the fix, the same focused suite passes after the fix, and the broader Operator suite passes.

**Project:** LocalOS
**Bug:** Operator loses today's content-plan result and charges a credit after planner failure
**Environment:** LocalOS production trace plus Python 3.11.7 regression tests on Darwin arm64
**Generated:** 2026-08-25

## Original report

For Весёлая Расчёска, the request ‘Покажи мне сегодняшние посты из контент плана’ returned a blocked response and charged one credit even though today's content-plan post existed and the read-only content.list_items tool completed successfully.

| Contract | Expected | Actual |
|---|---|---|
| Observed behavior | Operator returns the available post for 25 August and does not charge for a technical planner failure. | The successful tool result was replaced with a blocked response after DEEPSEEK_EMPTY_RESPONSE, and one credit was charged. |

## Minimal reproduction

Two focused tests simulate a successful content.list_items call followed by DEEPSEEK_EMPTY_RESPONSE and verify both preserved output and released billing reservation.

**Confirming signal:** Before the fix, 2 of 16 focused tests failed: the tool result was lost and the reservation was charged.

### Reproduction files approved at Gate 1

- [test_operator_tool_loop.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/tests/test_operator_tool_loop.py:322>) — Approved regression for preserving today's content result after an empty planner response.
- [test_operator_tool_billing.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/tests/test_operator_tool_billing.py:78>) — Approved regression for releasing the credit reservation on DEEPSEEK_EMPTY_RESPONSE.

## Red to green evidence

| Evidence | Before fix | After fix |
|---|---:|---:|
| Exit code | 1 | 0 |
| Timed out | False | False |
| Duration | — ms | 376.803 ms |
| Same command | — | True |
| Broader suite | — | passed: 238 Operator tests |

### Before — failing evidence

```text
14 passed, 2 failed. test_tool_loop_preserves_successful_read_when_final_planner_response_is_empty: the successful content.list_items observation was replaced by a blocked planner response after DEEPSEEK_EMPTY_RESPONSE. test_paid_tool_loop_releases_reservation_for_deepseek_empty_response: the reservation was charged instead of released because the provider error code was not normalized or classified as a technical planner failure.
```

### After — fixed evidence

```text
................                                                         [100%]
16 passed in 0.10s
```

## Root cause

The tool loop treated any final planner error as authoritative even after a successful safe read-only tool call. The billing guard compared a small case-sensitive set of error codes, so DEEPSEEK_EMPTY_RESPONSE was not recognized as a technical failure.

## Approved fix

Preserve the last successful read-only observation when final summarization fails, provide a deterministic content-list fallback, mark planner failure metadata, and normalize technical planner failure codes so billing releases the reservation.

**Why this is causal:** The changed branches are exactly where the successful observation was discarded and where the reservation finalization mode was selected.

### Production files approved at Gate 2

- [operator_tool_loop.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/services/operator_tool_loop.py:299>) — Preserves safe read-only results and renders a deterministic fallback.
- [operator_tool_billing.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/services/operator_tool_billing.py:15>) — Normalizes technical planner failures and releases their reservations.

## Verification

| Check | Status | Evidence |
|---|---|---|
| Focused red-to-green suite | ✅ passed | 2 failures before; 16 passed after with the same command. |
| Broader Operator suite | ✅ passed | 238 tests passed. |
| Production deployment smoke | ✅ passed | App and worker run the deployed hashes; HTTP returned 200 and the deterministic in-container fallback smoke passed. |
| Billing correction | ✅ passed | The exact erroneous charge received one idempotent compensating +1 ledger entry; balance returned from 48 to 49. |

## Reproduce

```bash
./venv/bin/python -m pytest -q tests/test_operator_tool_loop.py tests/test_operator_tool_billing.py
```
```bash
./venv/bin/python -m pytest -q tests/test_operator*.py
```

## Limitations

- The paid production request was not repeated because doing so could create another charge.
- The fallback is intentionally limited to successful safe read-only observations; write and approval flows keep their existing boundaries.

## Residual risks

- A different read-only capability without a dedicated formatter may return the generic preserved-result message rather than a capability-specific summary.
- Live provider behavior remains externally variable even though an empty final response no longer destroys the successful tool result or charges the user.

## Notes

- Gate 1 and Gate 2 were explicitly approved by the user.
- No publication, external send, or provider write was performed during diagnosis, verification, deployment, or refund.

---

Generated by `$bug-reproducer`. A fix is proven only by the same red-to-green reproducer plus relevant broader checks.
