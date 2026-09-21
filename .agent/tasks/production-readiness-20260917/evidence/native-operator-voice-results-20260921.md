# Operator voice PostgreSQL profile — 21 September 2026

This package preserves the bounded `operator-voice-pg-v1` runtime evidence
from frozen source `99849935de26e2932613f2a73cf515dff49104a1`. It is not a
current-source result, aggregate collection result, performance claim, or a
claim that the whole PostgreSQL suite has passed. Independent pre-execution,
runtime, live-resource and evidence-package verification passed on 21 September.

## Result

The literal module target `tests/test_operator_voice_pg.py` collected and
passed 382/382 node IDs: 382 passed, 0 failed, 0 skipped, 0 xfailed, and no
setup or call failures. Pytest reported `382 passed in 61.88s`; the captured
test child took 64.668 seconds and the complete wrapper took 68.397 seconds.
The captured test child stderr contains one upstream
`testcontainers.postgres` import `DeprecationWarning`; this report does not
describe stderr as empty.

The relay recorded 393 connections with a declared profile budget of 512,
zero active connections after the run, zero rejections, zero failures, and
393 graceful relay exec results. The profile permits no Flask child DSN
admissions; its journal contains exactly one temporary
`OPERATOR_VOICE_TEST_DSN` bind and unbind. The owned-container read-only
`pg_namespace` check recorded one
`operator_voice_schema_cleanup_checked` event with `remaining: 0` for
`^voice_[0-9a-f]{32}$` before container removal. This is zero-leftover-schema
evidence; it does not establish or claim a count of DDL operations.

The static-control capture passed the pure profile checks, focused Ruff
undefined-name checks, and `git diff --check` in 180.743 ms. The runtime
negative probe denied all ten guarded cases; the child guard probe succeeded.
The wrapper preserved 5,720 frozen blobs before and after, left the retained
internal network empty, and recorded only the owned container cleanup. No
product, production database, provider, or external write is asserted by this
package.

Independent live checks matched the exact retained Docker ID sets: 23
containers, 4 images, all 20 volumes and 23 networks. The owned test container
was absent and the internal network empty; default guard and source matched.

## Node reconciliation

`native-fixture-inventory-v4.json` is the canonical collection source: it has
5,481 unique accepted node IDs. The 382 unique node IDs captured here all
occur in that v4 inventory (382 intersection; 0 missing). A prefix scan of
the prior accepted runtime artifacts found no earlier accepted target from
`tests/test_operator_voice_pg.py`; historical inventory/terminal-failure
metadata is not treated as a prior accepted run. This bounded module therefore
adds 382 disjoint accepted frozen nodes to the preceding 2,811, yielding
3,193/5,481 accepted nodes and 2,288 not yet accepted.

## Canonical evidence

The six byte-preserved raw artifacts are in
`native-operator-voice-hflypi-20260921/`:

- `native-tc-operator-voice-pg-v1.json` — wrapper, pytest callbacks and
  source/guard/container accounting.
- `native-tc-operator-voice-pg-v1-child.json` — child guard probe.
- `native-tc-operator-voice-pg-v1-negative.json` — negative network/DSN
  guard probe.
- `native-tc-operator-voice-pg-v1-relay.json` — relay totals and executions.
- `native-tc-operator-voice-pg-v1-events.jsonl` — DSN lifecycle and schema
  cleanup evidence.
- `operator-voice-pg-controls-v1.json` — static-control capture.

`SHA256SUMS` binds these six artifacts and the five frozen support-file bytes
used by the runtime. The v4 inventory itself remains canonical at
`/private/tmp/localos-readiness-20260921.hfLYPi/native/evidence/native-fixture-inventory-v4.json`
with SHA-256
`e49b7a637b77af2c437d7fc2a7f9190c81f81c82da2d1a22fbcab13ed1dedb52`.
