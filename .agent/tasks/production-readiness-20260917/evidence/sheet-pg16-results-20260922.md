# Sheets queue and recovery PostgreSQL proof — 22 September 2026

## Result

**16 nodes / 48 setup-call-teardown phases passed**, outer 9,875.424 ms / exit 0,
no timeout or truncation, stderr empty. Callback has no collection errors, failed
or skipped phases, xfails or recorded warnings. Eleven queue nodes and five
recovery nodes were selected literally from the d0ef full-backend collection;
all 16 had been skipped at setup in that run. The admission inventory's fixture
use count of 16 already includes the five recovery tests: the total is not 21.

Covered contracts: one claimed request, revoked/missing/mutated approvals held,
preview/no-effects requests denied, expiry and uncertain outcomes held for
reconciliation, no open DB transaction during a fake provider call, no automatic
repeat after timeout or local commit failure, retained approval evidence, and
one finalization on resumed runs. Tests use real PostgreSQL and fake providers;
no Google service, real message, payment or publication was contacted.

This is validation of existing committed behavior, not a new product fix. A
historical 16-test pass exists, but the blueprint runner and capability handler
changed since that baseline, so a fresh current-parent proof was appropriate.

## Source boundary and test fidelity

Parent HEAD is `3ce90e4a`. The 6,340-file d0ef archive manifest is unchanged:
`48af8ec2a135fbb7858a859bdf59c680eb8076b5ff9c1d6b3a12d42ea5892067`.
Eight direct inputs match their current worktree files. The ninth, executor
`src/services/agent_sheet_provider_executor.py`, deliberately matches **committed
HEAD only**, SHA `f310241af7d9febbf3eeae1974b4abce94ecd4b865be0a1a81e1bc1164c4b9ba`.
Its pre-existing working copy SHA
`fd190611c27d1663e38f125c3d5ac79699776b2da46e078cc82b98635bbb7763` is recorded as
excluded; its two SQL edits were neither adopted nor overwritten.

The fixtures directly use psycopg2 or substitute schema-scoped DatabaseManager
connections. Therefore this pass is **not proof of the production query adapter's
placeholder conversion**, and not a test of that dirty executor version. That
separate correctness question is being investigated without changing the file.

The root-reviewed controller adapts the PG51 lifecycle only for test selection,
schema/name/DSN aliases and explicit source bridges. Executed controller
`a700e6c8`, guard `52a287a0` and node list `2b75e957` are unchanged before/after.
Full hashes and exact executed sources are in the 12-artifact bundle. Nineteen
pure controls pass (79.113 ms); helper Ruff passes (108.886 ms). Those two checks
preceded a comment-only wording correction from "unrelated" to "pre-existing";
no executable code changed afterward.

## Runtime isolation and cleanup

Fresh native PostgreSQL 15.15 / Python 3.11.7 ARM64; runtime directory
`/private/tmp/localos-sheet-pg16.mknhb6m_/`, port 50721, DB
`readiness_sheet_test_ac0756b5844146f3a4f4141627183288`. Environment is cleared,
dotenv/autoload disabled; both DSN aliases resolve to this exact owned DB. The
unchanged seven negative controls prove foreign database/port/libpq option/env
denials, native off-port OS denial, protected guard writes and user-home reads.
Only that loopback port and the run directory are admitted by OS policy.
Start/live disk floors 5/2 GiB, 4 MiB stream cap, 300 s controller deadline and
420 s outer capture remain; no Docker or existing database was used.

No `test_sheet_provider_<uuid>` schemas remain. The generated DB is absent;
post-drop catalog is exactly `postgres`, `template0`, `template1`. PostgreSQL
PID 34240 / birth 1790093789.479058 was verified against its private data directory
and stopped. Test child PID 34273 / birth 1790093791.701232 exited cleanly; both
process registries are empty, no processes were signalled by child cleanup and
no cleanup errors were recorded. System-database files remain in the stopped
private cluster. The original eight-file foreign diff hash remains unchanged.

## Review and remaining work

Independent source/runtime/cleanup review **PASS**: exact selectors, all 48 stages,
controls, stable source hashes, cleanup and the HEAD-only executor boundary were
verified. The preceding reviewer usage-limit error was not treated as a permanent
state: a fresh Codex account-state read reported ordinary usage allowed, so the
same review lanes resumed without changing model/account or buying credits.

The whole-backend aggregate remains historically failed. Current dirty-tree
adoption, migrated integration families, image 206 candidates, bounded load/
browser performance, CI/demo and final whole-diff review remain. Restricted
OAuth and native finance-picker cases remain unrun. No push/deploy/production
change was performed.

Evidence: [executed PG16 bundle](sheet-pg16-20260922/README.md).
