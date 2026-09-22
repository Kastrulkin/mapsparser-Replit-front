# Native callback recovery regression — 22 September 2026

Status: **14/14 PASS** in a fresh disposable migrated PostgreSQL database.
This revalidates a previously tested callback family in the current guarded
native profile; it does not establish that the whole backend or release passes.

## Provenance

Local parent `fb55739a`. Runtime uses the existing frozen archive of
`99849935de26e2932613f2a73cf515dff49104a1`, with all 5720 tracked blobs checked
before and after and no product/test overlays. Callback-relevant sources are
byte-identical to current committed code:

- test module: `de36b69ae6d42a772fd7b641b3dc0b3f8ab1aca8c4d120b342489665e76ecc9b`;
- ActionOrchestrator: `6d9bc1131f467a8e55095010761bad3f60e4d3dcc59768dd89f6469c468f5638`;
- worker: `b1104b5437e62a845dd48f3a206f56fc6699628e0a01ea072479ad17e457e9b1`;
- conftest: `893fef47376fdf4cd1bc1b8029b0f7bdaaf46a0385d3c7f91f94cecef669b1c0`;
- Alembic tree in both revisions: `4084974e0e5dc1035a2cc3f8d0a96cc0d25ee450`.

Only parser_config/yandex_maps_scraper differ under src between that frozen
revision and ef6d3e1e. Those parser changes are not certified by this profile.
Do not describe this as execution of the whole current dirty worktree.

## Scope and actual results

Whole `tests/test_action_orchestrator_callback_recovery_pg.py`: 14 exact nodes,
including 13 schema-isolated PostgreSQL cases and one pure worker control.
Assertions cover interrupted sending claims, bounded quarantine without resend,
foreign tenant retention, owner-scoped replay, 503 retry/attempt ledger, stale
metrics, late-finalizer fencing, cached-batch fencing and fair worker scans.
External transport and notifications remain deterministic test doubles.

v2: exit 0; 14 passed / 0 failed / 0 skipped / 0 xfailed. Pytest 10.06 s,
test subprocess 17.836 s, entire wrapper 21.043 s. One existing Testcontainers
import deprecation warning; no timeout. No product code or assertion changed.

New literal support profile creates one generated `readiness_full_test_*` DB
inside an owned internal PostgreSQL container, with no published host ports or
mounted user data. It runs canonical `FLASK_APP=src.main:app` Alembic upgrade,
checks the three required tables, and preserves the test's pinned guard-first
and logical loopback:35418 admission. Guarded psycopg2 rewrites that logical DSN
only to the verified private relay; direct host:35418 is denied.

Final executed support hashes (files committed with this report):

- launcher: `0b417442f3d25159e3a1a645ee3a4434bcded5a90fac9d7b2a998a93d60c3447`;
- adapter: `f9dd6ccd82b41926d9118967e7106edf47f6646d3f51287fdef5475cb145be4f`;
- guard: `a704e06f572da3d3ff99419ac771b3ef7450f8604411568a982b019172952f1f`;
- relay: `59151d2501d4ab459764a725e91cbe2c3d5e061e76e898ea2db0ad6b3b19c4e1`;
- pure legacy/callback wrapper control: `93aec5f8d5cc80be84320c3208939cff734c115aeb16b4ffee455a97b2d09fb0`.

102 relay connections within a 512 connection cap; 102 graceful successful exec
records, no relay failures/rejections. Journal proves migration, zero remaining
callback schemas, generated DB dropped and verified absent, then owned container
removed. Both internal-network postchecks are empty. All 23 pre-existing Docker
container IDs/states match before/after; guard and frozen archive were restored.
This profile has no volume mounts; no broad live volume-integrity claim is made.

Independent pre-execution and terminal reviews: bounded PASS. Root's independent
10-case pure controls use actual extracted guard/adapter definitions and real
psycopg2 DSN parser, intercepting connect/capability. Final v3 passes in119.718ms;
logical URL/keyword rewrite, child physical DSN, override/foreign/option rejection
and no direct35418 admission are checked. This is adjacency, not extra PG tests.

## Preserved failure

v1: FAIL in5.713s, before migration/pytest, zero test nodes. Its libpq interception
incorrectly rejected a standard driver factory keyword. Pre-create cleanup also
attempted checks for a DB that had not been created. The owned container was
nevertheless removed, 23 pre-existing containers retained and 5720 blobs restored.
v2 validates the exact physical DSN while allowing non-transport factory keywords,
and verifies DB absence without schema queries/DROP when creation never occurred.
Both raw attempts and probes/journals are archived, not relabelled as green.

## Remaining scope

No production/existing DB/provider effects, image build/pull, push/deployment or
repeat Docker cleanup. This does not reclassify the historical full-suite NONPASS,
prove live callback delivery, certify current application images, or close broad
security/performance/CI/demo/final-review gates.
