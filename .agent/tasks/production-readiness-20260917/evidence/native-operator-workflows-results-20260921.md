# Operator PostgreSQL and governed workflows — 21 September

Parent checkpoint: `0ef33e3a`. Previous turn was verified progress: reviewed
capabilities/governed results were committed without changing the application.
This checkpoint also changes audit support, evidence and documentation only.
Frozen application `99849935` and its 5,720 tracked blobs remain unchanged.
No production, existing database, provider, push or deploy operation occurred.

## Imported-fixture gap resolved with real PostgreSQL

The prior governed-v1 attempt had 21 skips because the imported `pg` fixture
requires `OPERATOR_VOICE_TEST_DSN`. That raw failed acceptance remains preserved;
its seven adjacent pure passes were not counted toward a complete slice.

The new named profile runs the entire unchanged 28-node service-creation module.
Its runner bootstraps one approved Testcontainers PostgreSQL before collection,
then binds the initially absent voice DSN only after owned relay capability
validation. It does not bind `DATABASE_URL` or require a Flask migration child:
this fixture runs the voice/service Alembic upgrades against its own cursor.
Each of the 21 DB cases creates/drops a unique synthetic schema. The assertions,
fixtures, migrations and product code are unchanged. Google and identity/provider
boundaries use the original test doubles, not real external effects.

Actual result: **28 collected / 28 passed**, zero skip, failure, xfail or subtest.
Pytest 4.34 s, captured process 6.926 s, wrapper 10.465 s, exit 0. Stderr retains
one `testcontainers.postgres` deprecation warning from bootstrap; it is not
claimed empty or fixed. Scenarios include six channel/voice inputs, duplicate
prevention, invalid prices, foreign businesses, stale/expired approvals,
existing-service price updates and notification preference/membership checks.

Exactly 21 real relay connections fit the unchanged 32 lifetime / 8 concurrent
limit. Runtime gates require every exec to finish gracefully with exit 0 and
empty stderr, no active connection, rejection or relay failure. Ten IO denials,
the separate guarded-child probe and eight capability-denial cases pass.
Exactly one voice DSN bind/unbind is recorded; no parent Flask-DSN binding.

Owned container `d28e3a66e5274d9a95ffab5e45526c6329c9c6eccdad515424590c8c7a52d5ff`
was removed, discarding only its synthetic tmpfs data. The existing 23-container
identity/running-state inventory is unchanged; the owned network is empty and
capability removed. The default `07d3...1150` guard was restored and temporary
runtime adapter/relay files removed. The named profile adds no volume access.

## Additional unchanged pure/mock coverage

`governed-workflows-pure-v1` passes **670 / 670** across 35 literal modules, no
skip/failure/xfail/subtest. Pytest 8.26 s, capture 9.175 s, wrapper 11.085 s,
exit 0 and empty stderr. Exact module counts and unique node inventory match.
Default guard and 5,720 frozen blobs are unchanged before/after. No bootstrap,
connectable DB, provider credential or external-network admission is enabled.
The fixed port-1 metadata URI only supports Flask metadata construction.

Independent pure pre-execution/runtime review PASS. A suggested bootstrap
`StartError` masking concern was withdrawn after a synthetic control-flow
check: exceptions propagate after `finally`; no unsupported fix was made.
PG independent pre-execution and runtime acceptance reviews PASS, including
live inspection of the retained containers, empty network and restored guard.
The only post-review guard edit was its experiment-list docstring, now accurate.
Final profile/subtest controls, Ruff on seven support files and diff-check pass
in 398.982 ms, exit 0 / empty stderr. Earlier 435.179 ms capture is retained.

## Scope, inventory correction and next work

Accepted complete slices: **1,982 + 28 + 670 = 2,680 of 5,481**, across 94 module
slices; 2,801 nodes are not yet closed by this measure. This is not an aggregate
run or proof for later changed source. The imported-fixture finding is locally
resolved by the full 28/no-skip run, not by excluding it from the pure profile.

The separate shared-conftest fixture inventory was rechecked: **104 PG-dependent
nodes in 19 modules**, of which 65 are accepted (card 1, client 7, capabilities
57) and **39 remain in 16 modules**. Client's eighth node is pure; capabilities
has three other pure nodes. Operator's 28 belong to its separate DSN fixture.
The historical 94/28 shared-fixture counts were incorrect and are superseded;
no historical rollback pass count is silently treated as current frozen proof.
The literal remaining39 node map is preserved in
`native-pg-shared-fixture-inventory-hflypi-20260921.json`; root independently
verified all39 unique IDs occur in the frozen collection and65+39=104.

Next high-risk PG slice: all seven work-review rollback tests. Their fixture
creates a strictly named disposable database and needs a dedicated reviewed
DSN/lifecycle profile; the present test-only database permission must not be
broadened blindly. The default-worker frontend flake also remains unproven;
isolated repeats do not replace a full-suite causal observation.
Security/privacy, browser/CAPTCHA, performance, current-source aggregate, hosted
CI, demo and final whole-goal gates remain open. Historical FAIL/spec/problems
and 13 foreign dirty paths are retained. Eight raw/static captures and the
16-file hash manifest are in `native-operator-workflows-hflypi-20260921/`.
