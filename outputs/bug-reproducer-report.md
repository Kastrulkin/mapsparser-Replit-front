# Bug Reproducer

## ✅ FIX_PROVEN — Bug reproduced and fix proven

> The unpaid Mini App navigation exposed five paid modules before the fix; the same regression test now passes and the production scope check returns read_only for the unpaid location and available for the paid location.

**Project:** LocalOS
**Bug:** Unpaid Mini App scope exposes paid modules
**Environment:** Local Python 3 with pytest 9; Vite/Vitest frontend; production Docker Compose and PostgreSQL
**Generated:** 2026-08-11

## Discovery scope

- Telegram binding and Mini App bootstrap
- network member scope resolution
- business subscription state
- Mini App navigation and payment-gate behavior

## Ranked and tested candidates

| # | Candidate | Contract evidence | Trigger | Location | Confidence | Outcome |
|---:|---|---|---|---|---|---|
| 1 | Mini App does not apply the selected location subscription gate | Only Engels is paid; the web dashboard already gates paid sections for inactive subscriptions. | Open the Mini App in the network scope or select the inactive Dolgoozernaya location. | /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/api/operator_api.py:95 | high | REPRODUCED |

## Original report

Verify that Elena can use the Telegram Mini App for Vesyolaya Raschyoska while only the Engels location is paid and the remaining scope stays behind payment gates.

| Contract | Expected | Actual |
|---|---|---|
| Observed behavior | Paid Mini App modules are read-only for the network and Dolgoozernaya, while Engels remains available. | Content, Finance, Operator, Partnerships and Progress were all marked available for the inactive Dolgoozernaya subscription. |

## Minimal reproduction

A focused unit test passes an inactive trial business scope to the real Mini App navigation builder and checks the paid module statuses.

**Confirming signal:** The test listed content, finance, operator, partnerships and progress as exposed.

### Reproduction files approved at Gate 1

- [test_operator_miniapp_subscription_access.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/tests/test_operator_miniapp_subscription_access.py:1>) — Focused red-to-green subscription regression test approved at Gate 1.

## Red to green evidence

| Evidence | Before fix | After fix |
|---|---:|---:|
| Exit code | 1 | 0 |
| Timed out | False | False |
| Duration | 800 ms | 1,600 ms |
| Same command | — | True |
| Broader suite | — | passed |

### Before — failing evidence

```text
FAILED tests/test_operator_miniapp_subscription_access.py::test_unpaid_business_does_not_expose_paid_miniapp_modules - AssertionError: Unpaid Mini App scope exposes paid modules: content, finance, operator, partnerships, progress
```

### After — fixed evidence

```text
9 passed in 0.77s for the focused subscription and Telegram scope tests. Broader related suite: 29 passed in 0.40s. Frontend GrowthNavigation tests: 2 passed. Production build exited 0.
```

## Root cause

Mini App navigation was derived only from scope kind and feature flags. It never evaluated the selected businesses' subscription tier, status or end date, and the frontend treated read-only navigation entries as openable.

## Approved fix

Added server-side subscription evaluation for business and network scopes, converted paid navigation entries to read-only with a billing reason, blocked paid Mini App routes and actions, and added a mobile payment sheet instead of opening locked modules.

**Why this is causal:** The subscription decision now directly controls both the navigation status and server route access for the same selected scope.

### Production files approved at Gate 2

- [operator_api.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/api/operator_api.py:95>) — Scope-aware subscription check and server payment gates.
- [TelegramControlPage.tsx](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/src/pages/TelegramControlPage.tsx:312>) — Mini App payment sheet and guarded navigation.
- [GrowthNavigation.tsx](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/src/components/telegram/GrowthNavigation.tsx:25>) — Routes locked outcome cards to the payment sheet.

## Verification

| Check | Status | Evidence |
|---|---|---|
| Same regression test | ✅ passed | Red before and green after. |
| Related backend suite | ✅ passed | 29 tests passed. |
| Frontend interaction test | ✅ passed | 2 GrowthNavigation tests passed. |
| Production build | ✅ passed | Vite build completed with exit code 0. |
| Production scope verification | ✅ passed | Engels available; network and Dolgoozernaya read-only for paid modules. |

## Reproduce

```bash
python3 -m pytest -q tests/test_operator_miniapp_subscription_access.py
```
```bash
python3 -m pytest -q tests/test_network_member_access.py tests/test_operator_mobile_today.py tests/test_operator_miniapp_subscription_access.py tests/test_telegram_control_scope.py
```

## Limitations

- Elena has not yet consumed her one-time Telegram link, so her real Telegram initData was not used during verification.

## Residual risks

- The final real-device check can only be completed after Elena opens the personal link in her Telegram account.

## Notes

- The personal binding token was not consumed during testing.
- Production app and Telegram Mini App page both returned HTTP 200 after deployment.

---

Generated by `$bug-reproducer`. A fix is proven only by the same red-to-green reproducer plus relevant broader checks.
