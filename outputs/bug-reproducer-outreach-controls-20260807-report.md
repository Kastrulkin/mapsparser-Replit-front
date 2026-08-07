# Bug Reproducer

## ✅ FIX_PROVEN — Bug reproduced and fix proven

> Both approved outreach-control defects changed from deterministic contract failures to passes; all 193 directly related broader tests pass. One adjacent history-payload fake-cursor test remains independently stale against an unchanged API query.

**Project:** LocalOS
**Bug:** Outreach composite-source validation and stale research state
**Environment:** Python 3.11 in an ephemeral Docker Compose app container with current source trees mounted read-only
**Generated:** 2026-08-07

## Discovery scope

- Outreach signal hypothesis provenance
- Campaign personalization and deterministic quality gate
- Native research existing-row upsert and dependent generation state

## Ranked and tested candidates

| # | Candidate | Contract evidence | Trigger | Location | Confidence | Outcome |
|---:|---|---|---|---|---|---|
| 1 | Composite multi-source observation is approved with only one exposed URL | Every material outreach fact must remain bound to public evidence and a source URL. | Official Telegram plus official website plus an incomplete map profile are combined into one observation. | /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/services/outreach_signal_hypothesis_service.py:171 | high | REPRODUCED |
| 2 | Fresh research upsert retains stale downstream readiness, personalization, and decision | A changed research report must invalidate generation artifacts derived from the previous facts. | An existing research row with ready/write_now state receives a payload with a different report hash. | /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/services/contact_intelligence_service.py:1385 | high | REPRODUCED |

## Original report

Verify that every material clause in a composite outreach observation has its own source and that refreshed research cannot retain a stale ready/write_now decision.

| Contract | Expected | Actual |
|---|---|---|
| Observed behavior | Incomplete composite provenance is rejected with SOURCE_MISMATCH, while changed research clears stale downstream state before regeneration. | The quality gate approved the three-clause observation using one URL, and all four downstream fields survived a changed research hash. |

## Minimal reproduction

Two focused pytest nodes exercise the real signal derivation and quality gate plus the real existing-row upsert through a deterministic fake cursor.

**Confirming signal:** Before the fix both nodes failed for their predicted assertions; after the fix the identical nodes passed.

### Reproduction files approved at Gate 1

- [test_founder_outreach_campaigns.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/tests/test_founder_outreach_campaigns.py:188>) — Composite provenance regression test approved at Gate 1.
- [test_contact_intelligence.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/tests/test_contact_intelligence.py:754>) — Stale downstream state regression test approved at Gate 1.

## Red to green evidence

| Evidence | Before fix | After fix |
|---|---:|---:|
| Exit code | 1 | 0 |
| Timed out | False | False |
| Duration | 520 ms | 510 ms |
| Same command | — | True |
| Broader suite | — | 193 related tests passed; adjacent four-file run had 200 passed and 1 pre-existing out-of-scope fake-cursor failure |

### Before — failing evidence

```text
FF [100%]
Composite claim: expected quality gate rejection, received passed=True.
Research refresh: stale message_readiness_json, personalization_candidates_json, selected_personalization_id, and outreach_decision_json all survived.
2 failed in 0.52s
```

### After — fixed evidence

```text
.. [100%]
2 passed in 0.51s
```

## Root cause

Composite signal construction collapsed provenance to its first URL and candidate construction discarded underlying evidence IDs; the gate only required any URL. Separately, the existing-row research UPDATE omitted four fields derived from prior facts.

## Approved fix

Preserve every composite evidence source, forward it into candidates, require complete multi-evidence source alignment, and conditionally clear dependent generation state when report_hash changes.

**Why this is causal:** The gate now evaluates the exact missing source-to-evidence relationship, and the same atomic UPDATE that installs changed facts invalidates artifacts computed from the previous hash.

### Production files approved at Gate 2

- [outreach_signal_hypothesis_service.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/services/outreach_signal_hypothesis_service.py:171>) — Preserves per-evidence provenance for composite hypotheses.
- [outreach_campaign_service.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/services/outreach_campaign_service.py:1828>) — Forwards composite provenance and rejects incomplete source alignment.
- [contact_intelligence_service.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/services/contact_intelligence_service.py:1385>) — Invalidates dependent generation state only when the report hash changes.

## Verification

| Check | Status | Evidence |
|---|---|---|
| Exact regression nodes | ✅ passed | Same two nodes changed from 2 failed to 2 passed. |
| Directly related broader suites | ✅ passed | 193 passed across signal hypotheses, founder outreach campaigns, and contact intelligence. |
| Adjacent campaign history payload suite | ⚠️ warning | Four-file run: 200 passed, 1 unrelated fake-cursor failure. The exact node fails identically on clean HEAD 4c5c250, proving it is pre-existing. |
| Syntax and diff integrity | ✅ passed | py_compile and git diff --check passed. |

## Reproduce

```bash
python -m pytest -q tests/test_founder_outreach_campaigns.py::test_multisource_composite_claim_requires_source_for_each_material_clause tests/test_contact_intelligence.py::test_native_research_refresh_clears_stale_downstream_generation_state
```
```bash
python -m pytest -q tests/test_outreach_signal_hypotheses.py tests/test_founder_outreach_campaigns.py tests/test_contact_intelligence.py
```

## Limitations

- The upsert regression uses the repository's deterministic fake-cursor convention rather than a live PostgreSQL row.
- No production data, campaign, queue, send, API, migration, frontend, commit, push, or deployment was exercised.

## Residual risks

- Previously generated composite candidates without per-source provenance will be rejected until regenerated.
- A research hash change intentionally moves stale ready/write_now artifacts back to regeneration and review.
- The adjacent campaign-history fake cursor should be repaired separately because clean HEAD proves it does not model the current committed API query.

## Notes

- No commit, push, or deployment was performed.
- The standard bug-reproducer output names were preserved because they belong to other tasks.

---

Generated by `$bug-reproducer`. A fix is proven only by the same red-to-green reproducer plus relevant broader checks.
