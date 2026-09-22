# Native schema/security PostgreSQL proof — 22 September 2026

## Result

Seven previously setup-skipped tests now pass against a fresh disposable
PostgreSQL15.15 cluster: **7 nodes,21 passed setup/call/teardown stages**, no
collection errors, skips or xfails. The complete outer run exits0 in8.540894s,
without timeout or truncated capture. No application or test assertion changed.

- Three ActionOrchestrator schema tests prove migration idempotence, retention
  of a legacy callback outbox row, expected indexes, DML-only ledger operation,
  denied runtime DDL and a clear missing-column error.
- Four Agent API security tests prove repeated migration application, ten
  indexes, client/discovery/ledger operations under a DML-only role, caller
  transaction rollback, and clear missing-table/missing-column failures.

These are local schema/transaction contracts, not live providers, the full
Alembic upgrade chain, deployment or general authorization certification.

## Exact source and runtime

The source is the immutable d0ef archive at
`/private/tmp/localos-current-full-v10.BYwJr6/source`, not the dirty workspace.
Both tests, shared conftest, two actual migrations and three relevant core
modules are byte-identical to current HEAD202b9c95. Their eight explicit hashes
are retained in `result.json`; the6340-file source manifest is unchanged before
and after. No foreign/restricted test overlay was included.

The exact executed controller has SHA256
`c56d5c94008df1933d5a65e43bb8b37f368317d710475074796d18445bbd1787`;
guard `b09437305887a33aa7b2470f7886f0c573c4cef3aeda6c75d928285f315d821e`.
Both pre/post bindings match. The controller reuses pinned existing lifecycle
and birth-pinned process helpers. Actual native executable paths are PostgreSQL
15.15_1 under `/usr/local/Cellar/postgresql@15/` and the ARM64 Python3.11.7
environment at `/private/tmp/localos-readiness-20260921.hfLYPi/native/venv/`.

Named tmux `audit-schema-pg7-v1` is terminal. Exact invocation:

```text
/usr/bin/arch -arm64 /private/tmp/localos-readiness-20260921.hfLYPi/native/venv/bin/python -B -I /private/tmp/localos-schema-pg7-20260922/run_schema_pg7.py --execute
```

The capture helper's complete argv and outcome are in `command.json`. Sources
copied as `.py.txt` preserve the executed temporary controller, not a portable
replacement project runner. Do not rerun this historical command after HEAD
changes; its preflight intentionally binds the reviewed commit.

## Isolation and cleanup actually verified

Seven pre-test runtime controls pass: wrong database, wrong port, caller libpq
options and inherited PG environment denied; native libpq off-port access denied
by OS; guard writes and user-directory reads denied. The runtime environment is
cleared, dotenv/plugin autoload disabled, and only the generated database is
admitted. Synthetic-only roles and data stay inside the owned loopback cluster.

The exact generated database was
`readiness_schema_test_` plus a random UUID, on port62956. Before stopping:

- Generated test schemas:0; generated NOLOGIN roles:0.
- Exact generated database:absent; catalog contains only
  `postgres`, `template0`, `template1`.
- Owned postmaster PID23208, creation identity and private data directory were
  verified and the process stopped. No tracked process remains.
- Pytest child registry:1 observed identity,0signalled,0remaining,0errors.
- Current foreign eight-file diff hash remains
  `40afa0141e5fe1b9fe9d18ee651ba61e19a27367158d71984f5a90a4d2a4c6d1`.

The stopped temporary cluster files are retained as evidence; the generated test
database is absent. No broad filesystem cleanup occurred. Existing databases, Docker and production were not
used. Trust is limited to these reviewed tests: this is not a hostile-code
containment claim. Test stdout is represented by hash/byte count, not arbitrary
captured content. Therefore no pytest-warning count or text is inferred.

## Preparation and evidence boundaries

Initial controller drafts failed static review (wrong catalog database,
startup/process cleanup, output bounds and premature PASS). They were corrected
before any PostgreSQL execution. The first actual runtime attempt passed.
Fifteen pure accounting/DSN controls passed65.756ms before launch; these are
helper checks, not additional application tests. Independent pre-execution
review accepted only the final frozen controller. Runtime acceptance is separate:
a read-only reviewer recomputed all21phase outcomes, exact7-node identity,
source/guard/helper hashes,6340-file manifest and cleanup evidence, and accepted
this bounded proof. A sandbox-denied separate host `ps` snapshot is not claimed;
the retained birth-pinned shutdown and absent PID file are the process evidence.
A post-run Ruff check reports one unused `os` import in the archived controller.
Its executed bytes are preserved rather than edited afterward; the `.py.txt`
artifact is not a new production module or a lint-gate pass.

All ten copied raw/source artifacts are bound by
`schema-security-pg7-20260922/SHA256SUMS`. Original runtime directory:
`/private/tmp/localos-schema-pg7.c72qakfx/`. The historical full offline aggregate
remains NONPASS; scoped successes must not be arithmetically added to it. The
restricted secondary OAuth and native finance picker stay unrun. No push,
deploy, production/provider mutation or image-cleanliness claim.
