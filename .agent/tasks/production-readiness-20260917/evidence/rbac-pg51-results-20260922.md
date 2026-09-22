# Operator and finance RBAC PostgreSQL results — 22 September 2026

## Result and scope

The first actual native PG51 run passed **51 tests / 153 lifecycle phases**
on a new disposable PostgreSQL 15.15 cluster. Outer capture: **12,366.546 ms,
exit 0**, no timeout or truncation, empty stderr. The callback has no collection
errors, skipped/failed phases, xfails or recorded warnings. This closes a scoped
execution gap; no new application defect or application-source change is claimed.

| Existing module | Nodes | Previously skipped PG setup | Previously passing pure tests |
| --- | ---: | ---: | ---: |
| `test_operator_viewer_readiness.py` | 17 | 16 | 1 |
| `test_operator_chat_viewer_readiness.py` | 12 | 12 | 0 |
| `test_viewer_mutation_readiness.py` | 22 | 14 | 8 |
| Total | 51 | 42 | 9 |

The prior counts come from the exact d0ef full-backend callback; they are not
added to the historical aggregate to manufacture a new aggregate pass. Each
selected node now has exactly one passing setup, call and teardown report.

The tests exercise stored direct/network roles, owner/admin controls, revoked
membership, unrelated tenants, denial before blueprint/chat effects, finance
writes and read-only routing. PostgreSQL queries and synthetic fixture writes
are real. Session identities, subscription/capability gates and external
runner/provider effects are explicitly doubled. This is not complete session
authentication, live-provider, full migration-chain, HTTP-server or browser proof.

## Isolation and provenance

- Parent HEAD: `3ce90e4a42aff8975a6462d39c0f64cdc63faf20`.
- Executed source: existing clean d0ef archive
  `/private/tmp/localos-current-full-v10.BYwJr6/source`, with no foreign overlays
  and no restricted OAuth test. Its 6,340-file manifest stayed
  `48af8ec2a135fbb7858a859bdf59c680eb8076b5ff9c1d6b3a12d42ea5892067`.
- Ten explicit test/runtime files match the current working copies. Git reports
  no committed changes in `src` or `tests/conftest.py` from d0ef to this parent;
  the three selected test files also match. This is not execution of the dirty tree.
- Executed controller `bc587d82`, guard `be5b92ac` and node-list `8d8323fa`
  hashes were unchanged before/after. Full hashes and bytes are in the bundle.
- Only `LOCALOS_RBAC_TEST_DATABASE_URL` is set for these fixtures, to the exact
  generated loopback database. Environment is cleared; dotenv and automatic
  pytest plugin loading are disabled. No Docker, existing application or provider
  endpoint is used. Native Python is 3.11.7 ARM64; PostgreSQL is 15.15 x86_64.
- Seven runtime negative controls passed: wrong database, wrong port, caller
  libpq options, inherited libpq environment, native off-port OS denial,
  denied guard writes and denied user-home reads. OS network policy allows only
  the generated PostgreSQL port; write policy allows only the owned run directory.
  These controls isolate trusted tests, not arbitrary hostile code.
- Start/live disk floors remain 5/2 GiB, streams capped at 4 MiB, controller
  deadline 300 s and outer capture deadline 420 s. About 9.3 GiB was free at start.

## Cleanup and terminal evidence

Runtime directory: `/private/tmp/localos-rbac-pg51.iz76jsb2/`.
Generated DB: `readiness_rbac_test_94362054c3994f5eafd021587ba4463a`, port 65243.
All three test schema prefixes have zero leftovers. The exact generated DB is
absent and the post-drop catalog contains only `postgres`, `template0`, `template1`.
Owned PostgreSQL PID 30998, birth 1790092998.460655, verified private data directory,
is stopped. Test child PID 31032, birth 1790093001.014366, exited cleanly; its
process registry has zero signalled/remaining processes or cleanup errors.
The cluster tracker also ends with no remaining processes.

The tmux handle is terminal/missing and its capture exists. A subsequent exact-PID
`ps` observation required read-only escalation after the ordinary sandbox denied
it; the approved check returned neither PID. No restart was attempted. The private
stopped cluster still contains system-database files; it is not described as empty.

Foreign eight-file tracked diff remains
`40afa0141e5fe1b9fe9d18ee651ba61e19a27367158d71984f5a90a4d2a4c6d1`.
No production data, existing containers/volumes, foreign source, push or deploy
was changed by this run.

## Controls and review boundary

Pure profile accounting/DSN checks: 19 passed, final capture 72.827 ms / exit 0.
They reject wrong endpoints, skips, xfails, wrong/duplicate/missing phases,
incomplete node sets and missing controls, without app/DB/network execution.
Earlier pure capture (150.463 ms) is retained, but its running file version was
not independently pinned; use the final controller-bound capture for this claim.
Ruff on all three preparation Python files: exit 0, 96.810 ms, no findings.
Redacted Gitleaks scan of the initial artifact bundle: 113,483 bytes, zero
findings, 990.710 ms / exit 0, no timeout/truncation. Its command/report are
retained too; those later captures and the readiness-doc diff are not retroactively
included in that directory-scan scope. A final owned-diff scan remains due.

Independent fixture/node/source review and pre-execution review passed for
controller `80551986`, guard `be5b92ac` and node list `8d8323fa`. The builder then
added only before/after node-list hash bookkeeping, producing executed `bc587d82`.
Root checked that delta, reran pure controls, and recomputed runtime counts and
cleanup. Independent rebind/runtime/package review initially hit a Codex usage
limit. A fresh account-state read subsequently reported ordinary usage allowed;
the same reviewer resumed and independently verified all hashes, 51/153 outcomes,
controls, cleanup and scope. **Scoped independent review PASS.** No account/model
switch or credit redemption occurred. This is not whole-project readiness.

## Services/content reconciliation — not a new run

The other 55 selected services/content nodes were not run in PG51. Their fixture
requires a pinned guard, logical loopback port 35418, a tightly named owned DB
and twelve fully migrated public tables. An empty-cluster profile is not adequate;
neither fixture guards nor schema expectations were weakened to force a pass.

Read-only reconciliation found prior real-PG evidence, correcting the earlier
recon statement that none existed: `raw/content-generation-role-final-green-20260919.json`
(SHA `ad118dbe69dc7561308f620a9a425138ba828e3ddcb8baf2b6c48f02f248994f`)
records 164 adjacent tests passing in 7.91 s (outer 9,122.281 ms), exit 0 with no
timeout/truncation. `COMMANDS.md` records all eight modules in that run, including
the services/content viewer module. Its private launcher is no longer present.

The test and direct services/content-plan API modules are byte-identical from
`be1b1a95` to current parent. The changed Operator news endpoint is not this test's
mobile content-plan endpoint; the content-plan service changes concern website
fetching, excluded by the synthetic fixture inputs. This supports continued
relevance of the historical role contract, but is **not a new 55-node run**, a
new 165-phase callback or a new 164-test current aggregate. Current migrated-profile
execution and final aggregate verification remain separate work.

## Remaining original objective

Remaining migrated integration families; pending dirty-fixture adoption and fresh
whole-backend aggregate; 206 unresolved
image scanner candidates and credential/owner decisions; current load/browser
performance, CI/demo and final whole-diff review. Restricted secondary OAuth and
native finance-picker scenarios remain unrun. Overall goal remains ACTIVE and
readiness is not established.

Raw evidence and executed sources: [PG51 bundle](rbac-pg51-20260922/README.md).
