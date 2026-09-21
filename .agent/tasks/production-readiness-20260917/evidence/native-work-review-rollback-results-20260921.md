# Work-review rollback on frozen PostgreSQL — 21 September

Parent checkpoint `7981ba84`; application archive `99849935` remains unchanged.
This package adds one audit-only profile and evidence, not a product/schema fix.

## Actual runtime

All seven unchanged tests pass, with zero skipped/failed/xfail/subtests:
empty rollback; refusal and data retention for five populated cases; concurrent
writer exclusion between the data guard and destructive DDL. Pytest 43.32 s,
captured process 43.876 s, wrapper 47.916 s, exit 0. Stderr is empty; stdout
retains one deprecated `testcontainers.postgres` import warning, not a clean
warning-free claim. The source tests and migration assertions were not changed.

The new literal profile admits only `postgres` and
`work_review_rollback_[0-9a-f]{32}` through the already owned relay. Other
profiles keep their previous test-only DB boundary. The parent DATABASE_URL
is not bound. Exactly one generated DB, two parent admin admissions and
14 migration-child connections are required; admissions alone are not DDL
proof. The real fixture creates/drops its DB, and a read-only query inside
the owned container observes zero matching databases before removal.

There are 75 clean relay connections, all graceful/exit 0/empty stderr, no
active connections, rejection or failure. Only this profile gets the bounded
512 total limit; 8 concurrent, 120 s connection, 600 s relay and 300 s runner
remain unchanged. Ten IO denials, child guard propagation and eight capability
denials pass. Profile controls, scoped Ruff and diff check pass in 185.672 ms.

Owned container `808ff16c2c0151d7a839e1aab92a59f63b758961908fdd9b3aa9492842a49200`
was removed, discarding only its synthetic tmpfs data. The retained 23-container
inventory is identical, internal network/capabilities empty, default guard
`07d3...1150` restored and temporary adapter/relay removed. All 5,720 tracked
frozen blobs match before/after. No existing volumes/DBs, production, provider,
push or deployment operation occurred.

## Accounting and continuation

Accepted complete slices are now 2,687/5,481 across 95 module slices, leaving
2,794 nodes; this is not an aggregate/current-source or production-ready claim.
Shared-conftest PG104 now has 72 accepted and 32 pending in 15 modules. The
earlier literal inventory is historical; its seven work-review IDs are closed
by this run, not silently dropped from the map.

Next rollback candidates: Creator Portal four nodes (generated prefix
`creator_portal_rollback_`, eight migration calls) and Creator Offer eleven
(prefix `creator_offer_rollback_`, 21 migration calls). Both need separate
reviewed profiles, not a global database-name allowance. Neither is run here.
Default-full frontend flake diagnosis, security, browser, performance,
current-source aggregate, CI/demo and final whole-goal review remain open.

Six raw/control captures plus 11 hashes are retained in
`native-work-review-rollback-hflypi-20260921/`. Independent pre-execution and
runtime reviews PASS, including live retained resources, empty network and
guard restoration. Exactly14 distinct migration-child PIDs were observed;
59 parent generated-DB admissions plus2 admin complete the75 connections.
