# Bug Reproducer

## ✅ FIX_PROVEN — Bug reproduced and fix proven

> Six remaining employee read paths rejected active network members before the change and passed after using the canonical business access check.

**Project:** LocalOS<br>
**Bug:** Remaining owner-only reads reject network employees<br>
**Environment:** Python 3.11 local tests; Docker Compose production at localos.pro<br>
**Generated:** 2026-08-06

## Original report

After sign-in was repaired, Irina from the Vesyolaya Raschyoska network still received payment and access errors while using the Grand Canyon location on Engels Avenue.

| Contract | Expected | Actual |
|---|---|---|
| Observed behavior | An active network member can read operational data for an active location in that network without becoming its owner or superadmin. | Six read paths rejected the employee because they compared only the subscription user or business owner. |

## Minimal reproduction

Six focused tests use a non-owner with active network membership against the real Flask routes and service helpers.

**Confirming signal:** HTTP 403 responses, PermissionError, and a false billing-access result instead of successful reads.

### Reproduction files approved at Gate 1

- [test_employee_remaining_read_access.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/tests/test_employee_remaining_read_access.py:65>) — Six active-network-member regressions approved at Gate 1.

## Red to green evidence

| Evidence | Before fix | After fix |
|---|---:|---:|
| Exit code | 1 | 0 |
| Timed out | False | False |
| Duration | 1,800 ms | 1,290 ms |
| Same command | — | True |
| Broader suite | — | 45 focused authentication, membership, billing, content-plan, and external-account tests passed; five changed modules compiled |

### Before — failing evidence

```text
FFFFFF [100%]
6 failed: content plans, billing status, parse status, manual competitors, external summary, and external posts rejected an active network member
```

### After — fixed evidence

```text
...... [100%]
6 passed in 1.29s
```

## Root cause

The affected legacy reads implemented owner-only authorization instead of verify_business_access, which already includes active network and direct business memberships.

## Approved fix

Replaced only the six observed owner-only read decisions with verify_business_access while preserving 404 and unauthorized behavior.

**Why this is causal:** The helper queries the same active network membership that grants Irina access to the Engels location, so the read decisions now match login and business selection.

### Production files approved at Gate 2

- [content_plan_service.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/services/content_plan_service.py:1542>) — Content-plan listing accepts canonical employee access.
- [yookassa_integration.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/yookassa_integration.py:571>) — Billing-status reads accept canonical access to the subscription business.
- [parsing_networks.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/legacy_routes/parsing_networks.py:946>) — Parse status accepts active business or network membership.
- [core_public.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/legacy_routes/core_public.py:1044>) — Manual competitor reads accept canonical employee access.
- [external_accounts_api.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/api/external_accounts_api.py:2056>) — External summary and posts reads accept canonical employee access.

## Verification

| Check | Status | Evidence |
|---|---|---|
| Regression test | ✅ passed | The same six scenarios changed from red to green. |
| Focused suite | ✅ passed | 45 relevant tests passed and all five changed modules compiled. |
| Production smoke | ✅ passed | The app container is healthy, localhost returns HTTP 200, and the live membership check grants Irina access to the Engels location. |

## Reproduce

```bash
python3 -m pytest -q tests/test_employee_remaining_read_access.py
```
```bash
python3 -m pytest -q tests/test_employee_remaining_read_access.py tests/test_employee_business_access.py tests/test_network_member_access.py tests/test_login_business_access.py tests/test_auth_email_case_insensitive.py tests/test_content_plan_policy.py tests/test_checkout_payment_providers.py tests/test_external_accounts_routes_contract.py
```

## Limitations

- No user session token or password was accessed, so production endpoints were not called by impersonating Irina.

## Residual risks

- Legacy owner-only endpoints not present in the observed production request set remain outside this patch.

## Notes

- Payment and subscription records were not changed.
- Irina remains a network member, not a business owner or superadmin.
- An existing unrelated production change in content_plan_service.py was preserved by applying a minimal patch.

---

Generated by `$bug-reproducer`. A fix is proven only by the same red-to-green reproducer plus relevant broader checks.
