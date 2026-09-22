# RBAC PostgreSQL proof — 22 September 2026

This bundle preserves the first actual PG51 run, its immutable controller/guard,
literal test selection and pure-control/lint captures. See the sibling
`rbac-pg51-results-20260922.md` for scope, accounting and review history.

Source files are archived as `.py.txt` to preserve the exact executed bytes,
not to introduce a general-purpose runner. The controller is bound to historical
HEAD `3ce90e4a`, an existing private source archive and private dependency paths;
it is not a reusable command after the next commit. Do not rerun its completed
tmux session or mutate the archived result to fit later source.

`result.json` records 51 nodes / 153 passed setup-call-teardown phases and seven
isolation controls. The generated database was removed and the owned PostgreSQL
process stopped. Only the system-database files remain in its private stopped
cluster directory. No production, existing Docker volume or provider was used.

The independent reviewer accepted the earlier controller `80551986`, identical
apart from the final before/after node-list hash bookkeeping. Root reviewed that
small addition and the runtime result. After a fresh account-state check allowed
the same reviewer to resume, independent final/runtime/package review passed.
The usage-limit interruption remains historical. This is not a whole-project
readiness verdict.
