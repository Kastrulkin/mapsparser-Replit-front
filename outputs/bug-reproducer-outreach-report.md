# Bug Reproducer

## ✅ FIX_PROVEN — Bug reproduced and fix proven

> All three approved outreach regressions changed from deterministic failures to passes, and the relevant 194-test suite passed.

**Project:** LocalOS

**Bug:** Stale map-service facts survive research refresh and remain sendable

**Environment:** Python 3.11 in disposable Docker Compose app container; production database not used

**Generated:** 2026-08-07

## Original report

Four manually checked beauty leads had incorrect service-price signals: current priced services were reported as incomplete, and one clinic previously received invented services. Existing outreach chains could retain those stale facts.

| Contract | Expected | Actual |
|---|---|---|
| Observed behavior | Fresh map and social facts replace stale observations, changed facts invalidate saved chains, all current evidence is considered, and missing owner verification remains unknown. | A higher historical score pinned fit_only and stale 27/3 facts; campaigns checked prompt versions but not source facts; evidence_json shadowed signals_json; missing owner verification became false. |

## Minimal reproduction

Three focused tests exercise the real native research upsert path, saved-campaign payload freshness, evidence merging, and owner-state SQL contract.

**Confirming signal:** Three deterministic assertions failed for the predicted stale-state, missing-fingerprint, evidence-shadowing, and unknown-owner causes.

### Reproduction files approved at Gate 1

- [test_contact_intelligence.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/tests/test_contact_intelligence.py:647>) — Fresh lower-score research replaces stale high-score map facts.
- [test_founder_outreach_campaigns.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/tests/test_founder_outreach_campaigns.py:510>) — Changed source facts invalidate a saved campaign.
- [test_outreach_signal_hypotheses.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/tests/test_outreach_signal_hypotheses.py:107>) — Evidence and signals merge while unknown owner remains unknown.

## Red to green evidence

| Evidence | Before fix | After fix |
|---|---:|---:|
| Exit code | 1 | 0 |
| Timed out | False | False |
| Duration | 560 ms | 510 ms |
| Same command | — | True |
| Broader suite | — | passed |

### Before — failing evidence

```text
FFF [100%]
1) expected reason_to_check, received fit_only; 2) campaign payload did not query current lead_workstream_research; 3) ledger omitted fresh-social-signal and unknown owner was coerced to false.
3 failed in 0.56s
```

### After — fixed evidence

```text
... [100%]
3 passed in 0.51s
```

## Root cause

Current-state research was merged append-only and gated by the historical maximum score; campaign generation validity had no current-fact fingerprint; evidence selection used boolean OR; SQL defaulted an absent owner flag to false.

## Approved fix

Replace current-state research fields with the fresh payload while preserving approved proof and sources; fingerprint current research facts through preview, persistence, read, approval, and dispatch; merge and deduplicate evidence plus signals; preserve a NULL owner state.

**Why this is causal:** Each changed condition is the direct branch proven by its focused failing assertion, and the unchanged tests pass after those branches are corrected.

### Production files approved at Gate 2

- [contact_intelligence_service.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/services/contact_intelligence_service.py:1353>) — Refreshes current research without retaining contradictory observations.
- [outreach_campaign_service.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/services/outreach_campaign_service.py:1290>) — Preserves unknown owner, merges evidence, stores fingerprints, and blocks stale approval.
- [outreach_campaign_api.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/api/outreach_campaign_api.py:234>) — Marks saved campaigns stale when current facts differ.
- [outreach_safety_service.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/services/outreach_safety_service.py:69>) — Defines stable fact fingerprints and blocks stale dispatch.

## Verification

| Check | Status | Evidence |
|---|---|---|
| Exact three-test reproducer | ✅ passed | 3 failed before the fix; 3 passed in 0.51s after it. |
| Relevant broader suite | ✅ passed | 194 passed in 1.22s after mounting frontend read-only. |
| Syntax and diff validation | ✅ passed | py_compile and git diff --check succeeded. |

## Reproduce

```bash
python -m pytest -q -p no:cacheprovider tests/test_contact_intelligence.py::test_native_research_refresh_replaces_stale_high_score_signal tests/test_founder_outreach_campaigns.py::test_changed_research_fact_fingerprint_invalidates_saved_campaign tests/test_outreach_signal_hypotheses.py::test_research_evidence_merges_with_signals_and_unknown_owner_stays_unknown
```

```bash
python -m pytest -q -p no:cacheprovider tests/test_contact_intelligence.py tests/test_founder_outreach_campaigns.py tests/test_outreach_signal_hypotheses.py tests/test_full_services_payload.py
```

## Limitations

- No production data was reprocessed and no existing campaign was modified.
- The focused campaign test covers read-time invalidation; approval and dispatch use the same fingerprint contract and are covered by the broader source-contract suite.

## Residual risks

- Legacy campaigns without a fingerprint will require regeneration after deployment.
- A new public observation date intentionally changes the fingerprint and may require review even when wording is similar.
- Fresh production chains still require a separately authorized reparse and regeneration step.

## Notes

- No production database, deployment, commit, push, or existing campaign was touched.
- The first broad Docker run omitted the frontend mount and produced 49 FileNotFoundError harness failures; rerunning with frontend mounted read-only produced 194 passes.

---

Generated by `$bug-reproducer`. A fix is proven only by the same red-to-green reproducer plus relevant broader checks.
