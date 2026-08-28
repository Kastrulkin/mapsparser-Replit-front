# Bug Reproducer

## ✅ FIX_PROVEN — Bug reproduced and fix proven

> The same reproducer changed from failing to passing and broader checks passed.

**Project:** LocalOS
**Bug:** Lead registry appears to hang after the 504 fix
**Environment:** LocalOS production and Python 3.11 regression tests on Darwin arm64
**Generated:** 2026-08-26

## Original report

The production lead registry loads but appears to hang at https://localos.pro/dashboard/bazich?tab=prospecting.

| Contract | Expected | Actual |
|---|---|---|
| Observed behavior | The first 50 lead cards appear promptly without a 504 or a long blocking spinner. | The first page took about 6.2 seconds after the original 504 was removed. |

## Minimal reproduction

A focused test converts a nested ten-lead payload through the real compatibility wrapper and counts namespace bindings.

**Confirming signal:** The old wrapper rebound the namespace 72 times instead of once.

### Reproduction files approved at Gate 1

- [test_lead_registry_projection.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/tests/test_lead_registry_projection.py:73>) — Approved regression test counts compatibility namespace bindings.
- [test_lead_workstream_contracts.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/tests/test_lead_workstream_contracts.py:61>) — Approved contract test prevents the lead tab from blocking on the admin directory.

## Red to green evidence

| Evidence | Before fix | After fix |
|---|---:|---:|
| Exit code | 1 | 0 |
| Timed out | False | False |
| Duration | 675.728 ms | 672.795 ms |
| Same command | — | True |
| Broader suite | — | passed |

### Before — failing evidence

```text
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_registry_json_projection_does_not_rebind_for_every_nested_value _____

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x10483cbd0>

    def test_registry_json_projection_does_not_rebind_for_every_nested_value(monkeypatch):
        from api import admin_prospecting

        bind_calls = 0

        def count_bind_calls():
            nonlocal bind_calls
            bind_calls += 1

        monkeypatch.setattr(admin_prospecting, "_bind_runtime_namespace", count_bind_calls)
        payload = {
            "leads": [
                {
                    "id": str(index),
                    "name": f"Lead {index}",
                    "workstreams": [{"id": f"workstream-{index}", "state": "ready"}],
                }
                for index in range(10)
            ]
        }

        admin_prospecting._to_json_compatible(payload)

>       assert bind_calls == 1
E       assert 72 == 1

/tmp/localos-lead-registry-report.0tPZ6Q/test_registry_bind.py:24: AssertionError
=========================== short test summary info ============================
FAILED ../../../tmp/localos-lead-registry-report.0tPZ6Q/test_registry_bind.py::test_registry_json_projection_does_not_rebind_for_every_nested_value
1 failed in 0.34s
```

### After — fixed evidence

```text
.                                                                        [100%]
1 passed in 0.33s
```

## Root cause

Every nested compatibility-wrapper call repeated a full runtime namespace copy; the lead registry JSON walk amplified this into 14,510 wrapper calls and about 3.2 seconds of avoidable CPU time. The admin page also blocked the lead tab on an unrelated 4.1 MB user/business directory response.

## Approved fix

Skip the unrelated admin directory on the prospecting tab and track compatibility call depth so only the outer wrapper binds the runtime namespace.

**Why this is causal:** The first change removes the blocking 4.1 MB request from the lead route. The second removes the measured repeated namespace copies while preserving one bind for every top-level compatibility call.

### Production files approved at Gate 2

- [admin_prospecting.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/api/admin_prospecting.py:289>) — Context-local depth prevents nested runtime namespace rebinding.
- [AdminPage.tsx](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/src/pages/dashboard/AdminPage.tsx:663>) — The prospecting tab no longer waits for the full admin directory.

## Verification

| Check | Status | Evidence |
|---|---|---|
| Exact compatibility reproducer | ✅ passed | Same command changed from exit 1 to exit 0. |
| Relevant Python suites | ✅ passed | 185 tests passed. |
| Frontend registry tests and build | ✅ passed | 2 tests passed and Vite production build succeeded. |
| Production endpoint profile | ✅ passed | cProfile improved from 5.46 seconds to 2.30 seconds. |
| Production browser | ✅ passed | 50 of 2,468 cards appeared in 2.77 seconds; page 2 opened in 0.87 seconds; no 504. |

## Reproduce

```bash
venv/bin/pytest -q tests/test_lead_registry_projection.py
```
```bash
venv/bin/pytest -q tests/test_lead_workstream_contracts.py tests/test_admin_prospecting_lead_deduplication.py tests/test_founder_outreach_campaigns.py
```

## Limitations

- The production browser includes extension-injected DOM changes, so the measured 2.77 seconds includes browser and network overhead.

## Residual risks

- The endpoint still scans all 2,539 compact lead rows to calculate totals and category counts; further sub-second work would require a separate query-contract change.

## Notes

- Both approval gates were explicitly granted for both fixes.
- Commits b6a7c3e6 and 7ff24339 were pushed to GitHub and GitVerse and deployed to LocalOS production.
- Existing generic bug-reproducer report files were preserved because they document another bug.

---

Generated by `$bug-reproducer`. A fix is proven only by the same red-to-green reproducer plus relevant broader checks.
