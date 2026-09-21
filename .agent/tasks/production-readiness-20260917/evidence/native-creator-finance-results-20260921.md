# Creator rollback and finance/content tests — 21 September

Parent `eb59fc2f`; application snapshot `99849935` remains unchanged. This is
test-environment and evidence work, not an application/schema fix or release.

## Executed checks

| Exact frozen scope | Passed | Pytest | Captured process | Wrapper |
| --- | ---: | ---: | ---: | ---: |
| Creator Portal rollback, v1 | 4/4 | 26.72 s | 27.164 s | 30.328 s |
| Creator Offer Distribution rollback, v1 | 11/11 | 64.68 s | 65.138 s | 68.374 s |
| Work-review rollback, v2 regression | 7/7 | 42.50 s | 42.952 s | 46.446 s |
| Finance/services/reviews/content, 21 modules, v1 | 92/92 | 2.89 s | 3.577 s | 5.307 s |

Every selected node ran, with zero failures/skips/xfails/subtests and exit0.
All stderr is empty. Each PG run retains one deprecated Testcontainers import
warning in stdout; pure92 is warning-free. The seven-file control/Ruff/diff
capture passed in218.098 ms. No assertions, migrations or application fixtures
were changed to obtain these results.

The rollback tests exercise empty-schema reversal, refusal to destroy populated
data, existing-data preservation and concurrent writer exclusion. The pure
slice covers import limits/normalization, KPI edge cases, business-scoped ROI,
review currentness, service grouping and content export/access contracts. These
are focused tests, not a full browser or real-provider proof.

## Isolation and lifecycle

The new profiles admit only `postgres` and their own exact generated database
prefix plus32 lowercase hex characters. Cross-profile/malformed names and legacy
scope widening are rejected by controls. Parent DATABASE_URL binding remains
limited to its old client/capabilities profiles, never these rollback profiles.

| PG profile | Relay connections | Parent admin | Parent generated DB | Distinct migration children |
| --- | ---: | ---: | ---: | ---: |
| Creator Portal | 54 | 2 | 44 | 8 |
| Creator Offer | 159 | 2 | 136 | 21 |
| Work-review regression | 75 | 2 | 59 | 14 |

Only named rollback profiles get512 lifetime connections; legacy/default32,
capabilities1024, concurrent8, connection120 s, relay600 s and runner300 s remain
unchanged. Every relay exec closes gracefully with exit0/empty stderr; no active,
rejected or failed connection remains. Ten IO-denial checks, child-guard
propagation and eight capability-denial controls pass for each PG run.

Each fixture creates and removes one owned synthetic DB. A read-only query in
that exact container confirms zero matching databases before container removal;
DSN admission alone is not DDL proof. Only owned tmpfs containers65e0a7b1...,
a66f56f6... and8cd8989a... were removed. Their synthetic contents are discarded;
no existing volume or application data was removed. Retained23 container
identities/states match before/after. Internal network/capabilities are empty,
temporary adapter/relay files removed and default guard07d3...1150 restored.
All5,720 frozen tracked blobs/modes match before/after every run.

Pure92 uses the unchanged default network/DB guard, not the PG adapter. Its
fixed passwordless metadata URI points to guard-denied127.0.0.1:1; it grants no
database connection or provider access. Exact module/node counts match runtime.

## Accounting and limits

New coverage is92+4+11=107 distinct nodes. Work-review v2 is an adjacent regression
after the shared profile mapping changed; never count its7 nodes again. Accepted
complete slices are2,794/5,481 across118 module slices, leaving2,687 unclosed.
Shared-conftest PG inventory is87/104 accepted,17 pending in13 modules. The new
`native-pg-shared-fixture-status-hflypi-20260921.json` reconciles exact nodeids
against runtime captures; the historical65/39 inventory remains unmodified.

No new product defect was demonstrated. Security, historical frontend flake,
browser failure observations, current-source aggregate, five-flow performance,
CI/demo and final whole-goal review remain open. Whole readiness remains FAIL.
The retained13 foreign dirty paths are unchanged. No production, provider,
push or deployment operation occurred; completed Docker cleanup was not replayed.

Seventeen raw/control captures, seven support hashes and the reconciled inventory
are recorded by25 SHA-256 entries in
`native-creator-finance-hflypi-20260921/manifest.json`. Independent pre-execution,
all four runtime results and final live resource/guard checks PASS. Live Docker
sets match23 containers/4 images/20 volumes/23 networks, with all three owned
test IDs absent. Final package review is a separate commit gate.
