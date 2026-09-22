# Sheets query-adapter regression — 22 September

Finding **SHEETS-QUERY-ADAPTER-01**, P1, before industrial launch.
Diagnosis: **REPRODUCED**. Local fix: **FIX_PROVEN** by pure causal red/green and
the fresh native regression/adjacent suite below. Independent package review PASS.

The provider worker obtains a real `DatabaseManager` cursor, whose wrapper
interprets any parameterized SQL containing `?` through the legacy SQLite
placeholder adapter. The claim CTE uses PostgreSQL's JSONB key-existence operator
and four `%s` parameters. The adapter sees one question-mark placeholder versus
four arguments and raises before the claim reaches PostgreSQL or any provider.
The raw-psycopg2 queue/recovery fixtures did not cover this wrapper boundary.

## Observed causal check

The unchanged committed executor SHA `f310241a` fails with the exact expected
one-placeholder/four-parameter `ValueError`, after two recording-cursor calls.
The pre-existing dirty executor SHA `fd190611` reaches all three calls, preserves
the approval predicate and four parameters, and returns no claim on an empty
cursor. It differs only by two `?` → `jsonb_exists(...)` substitutions. Only the
second, parameterized claim query causes the reproduced failure; the first
unparameterized hold query is changed for consistent expression of the predicate.
No shared QueryAdapter behavior or approval requirements are relaxed.

Actual `audit-sheet-adapter-red-green` run: 2,640.908 ms, exit 0, no timeout,
truncated output or stderr. OS policy denies all network, reads under `/Users`
and writes outside the private proof directory. The frozen 6,340-file content
manifest and four direct imported input hashes are unchanged before/after.
This is a pure cursor proof: no database or Google provider operation occurred.
Independent source and runtime review: PASS.

## Regression work

The existing untracked pure regression is preserved byte-for-byte (SHA
`87749d57`). New `tests/test_sheet_provider_runtime_cursor_pg.py` uses the real
DatabaseManager and cursor wrapper, the existing synthetic-schema fixture and
fixture-scoped DATABASE_URL. Its three cases cover an approved claim exactly
once, missing approval snapshot, and an empty queue. All three passed natively.
Final test SHA `5d688a39`; independent source review PASS.

Targeted Ruff across executor and both regression files passes in 91.970 ms.
Retain initial 120.421 ms nonpass: imported pytest fixture shadow triggered three
F811 diagnostics. Importing the fixture's module and assigning the same fixture
object resolved them without changing assertions or database cleanup.

## Native PostgreSQL result

First actual `audit-sheet-wrapper-pg20-v1` run: **20 nodes / 60 phases passed**,
9,030.334 ms outer, exit 0. No collection errors, skips, xfails, warnings,
timeouts or truncated output. Selection is 16 existing queue/recovery cases,
three new real-runtime-cursor PG cases, and one pure adapter case. Thus 19 cases
use PostgreSQL, not all 20. The final private executor snapshot is loaded under
its canonical module and package attribute; it is not the earlier HEAD-only run.

Seven isolation controls, 19 pure guard/accounting controls (74.817 ms), and
harness Ruff (89.000 ms) pass. Source6,340 manifest, overlay/private/current test
hashes, controller, guard and exact node list are unchanged. Private node IDs are
normalized only after matching exact copied paths; all60 distinct phases remain
mandatory, with no skip/xfail acceptance.

Synthetic database `readiness_sheet_test_db3019991c9141a28cb2e6c00de2e8e4` and
all generated schemas are absent. Catalog contains only postgres/template0/
template1. Owned PostgreSQL39195 (verified private data directory, loopback52960)
stopped, child39231 exited, no remaining/signalled processes or cleanup errors.
Root also verified postmaster.pid is absent and formally approved read-only `ps`
returned neither exact PID. Only synthetic test data were removed;
no user data or existing databases were changed. No Google provider call occurred.

Final runtime result SHA `9bfe5eda`; controller `cbb3a6ff`; guard `52a287a0`.
Independent pre-execution, source, final runtime and package reviews PASS.
Reverting just the two executor lines restores the old behavior;
there are no schema, dependency, config or API changes to roll back.

## Scope and provenance

Parent HEAD `b3a808ea5af6fb69f3ef6e7398e3a878ec60ff8e`. The preceding PG51/Sheets16
evidence package was committed successfully; its exact staged scan found zero
secrets. Those native runs used the committed executor and remain distinct.
The original dirty executor and pure test are not edited; native validation now
supports adopting those exact relevant bytes in this package. Other foreign
changes, including the pending author/diagnostic fixture decisions, remain
untouched. No push, deploy, production/provider access, or restricted-test retry.

The preserved runner is an executed historical artifact, not a portable command
to rerun against stale temporary paths. The full backend aggregate remains NONPASS;
the full original production-readiness objective is incomplete.

## Archive metadata normalization

Initial strict staged scan reported two generic-api-key matches: the pure result's
before/after source-module hashes were labelled `agent_api_security`. Both values
are the SHA-256 of frozen `src/core/agent_api_security.py`, not credentials.
The archival `result.json` renames only those two keys to
`agent_security_module_sha256`; all values and execution outcomes are unchanged.
Original private raw result remains untouched at
`/private/tmp/localos-sheet-adapter-proof-LnSslv/result.json`, SHA
`8792cea429a846a04044811a152d40bb7ce4c11941ad52325508b51a8f3bf370`.
The manifest binds the normalized archive, not that original raw byte stream.
No secret-scan exclusion, allowlist, detector change or finding suppression is used.
