# Operator editorial PostgreSQL profile — 22 September 2026

This package preserves raw evidence for the bounded
`operator-editorial-pg-v1` run against frozen source
`99849935de26e2932613f2a73cf515dff49104a1`. Independent verifier review
accepted the runtime, live PostgreSQL evidence and byte-preserved package.
It is not a full PostgreSQL, current-source, aggregate collection,
or image-proof claim.

## Captured result

The four literal whole-module targets collected 63 node IDs: 27 from
`test_operator_editorial_pg.py`, 13 from `test_operator_post_rewrite_pg.py`,
7 from `test_operator_plan_revision_pg.py`, and 16 from
`test_operator_followups_pg.py`. The callback evidence records 63 passed, 0
failed, 0 skipped, 0 xfailed, and zero setup/call failures. Of the 63 nodes,
62 use the real `pg` fixture; the remaining plan-revision schedule parsing
node is fixtureless.

Pytest reported `63 passed in 10.47s`. The captured test child took 13.065
seconds and the wrapper took 16.498 seconds. Its bootstrap import emitted one
upstream `testcontainers.postgres` deprecation warning on stderr; this report
does not call stderr empty.

The relay recorded 62 connections against the declared profile bound of 128,
with zero active connections afterward, zero rejections, zero failures, and
62 graceful relay exec results. The journal records no Flask child admission,
one temporary `OPERATOR_VOICE_TEST_DSN` bind/unbind pair, and one owned
read-only `pg_namespace` cleanup observation with zero matching
`^voice_[0-9a-f]{32}$` schemas before container removal. This is
zero-leftover-schema evidence, not a count of DDL operations.

The copied control capture records successful pure profile checks, focused
Ruff undefined-name checks, and `git diff --check`. The raw child and negative
probe captures provide the guard propagation and denied network/DSN evidence.
No product, production database, provider, external write, or image proof is
claimed by this package.

## Frozen-collection reconciliation

The canonical collection inventory is
`/private/tmp/localos-readiness-20260921.hfLYPi/native/evidence/native-fixture-inventory-v4.json`
(SHA-256 `e49b7a637b77af2c437d7fc2a7f9190c81f81c82da2d1a22fbcab13ed1dedb52`).
All 63 unique callback node IDs are in its 5,481 unique IDs; none is missing.
Independent review confirmed the 63-node set is disjoint from earlier accepted
runtime nodes. Callback order differs from the inventory ordering, so this is
a set reconciliation rather than an order assertion. The accepted frozen
collection accounting is therefore 3,256/5,481 nodes, with 2,225 open.

## Canonical package contents

`native-operator-editorial-hflypi-20260922/` contains six byte-preserved raw
artifacts: wrapper/callback result, child probe, negative probe, relay journal,
event journal, and controls capture. `SHA256SUMS` binds these six artifacts and
the five frozen support-file bytes used for this run.
