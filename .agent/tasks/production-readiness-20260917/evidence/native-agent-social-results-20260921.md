# Agent/social native batch — 21 September

Frozen application source99849935; no application, test assertion, migration,
provider permission or runtime guard edits. Goal remains active and incomplete.

## Actual results

v1 collected524 parents:522 passed,2 failed,2 subtests passed (pytest5.00s).
Both failures were `import main` route-registration checks in
`test_agent_blueprint_contracts_migrations.py`: installed Flask-SQLAlchemy
requires a database URI to construct its metadata engine. No database query
was intended; this was missing test environment, not a proven product defect.

The reviewed profile-only overlay sets a fixed passwordless PostgreSQL URI on
127.0.0.1:1; the unchanged psycopg/socket guard denies this destination before
connection. It refuses inherited DATABASE_URL and retains the clean environment,
dotenv-disabled setting, default guard and absence of Testcontainers mode.
No real database or provider credential was supplied. Old unit profiles do not
receive the URI. Route registration here is not an API/DB integration test.

v2 passes **524 collected parent tests +2 subtests**, no failures/skips/xfails,
exit0, empty stderr. Pytest5.59s, capture6.542s, complete pre/post wrapper8.763s.
All13 exact per-module counts match the reviewed inventory;524 nodeids unique.
5720 frozen tracked blobs/modes and guard07d3... match before/after both runs.
Independent source/fixture/pre-execution and raw-result review PASS.

Modules cover social post service162 and twelve agent/approval modules362:
generic runs56, compiler54, capabilities49, connections47, builder sessions32,
async30, draft approval identity25, reviews/outreach18, contracts/migrations15,
builder scenarios15, runtime policy13, fake approval ordering8. Exact paths
and actual callback inventory are in the archived raw captures and manifest.

Fresh cumulative backend:1097distinct passed/5481collected in20 module slices;
4384remain (85 mapped PG-group +4299 other nodes). v1 successes are not counted
again; subtests are not distinct collected parent nodes. Not a full aggregate
or a claim about later changed source / deployed production.

## TEST-HARNESS-SUBTEST-01 — P2, local FIX_PROVEN

Category: audit evidence correctness. The v1 hook counted every pytest call
report, including two SubtestReport records, as a collected parent result:
its passed counter was524 although only522 parents passed. The failed count
and pytest exit1 still rejected v1; no false full PASS is claimed.

Root cause: the harness did not distinguish installed pytest's parent report
type from its builtin SubtestReport subtype. Effect: misleading pass totals
and rejection of otherwise successful batches with extra successful subtests.
Confidence high and reproduced locally; no user-facing runtime failure or
production frequency claimed. Small effort/blast radius: shared audit callback
and result controls only; no product source or test expectations changed.

Same actual-report regression fails before (151.0ms), passes after (164.5ms).
It executes the generated callback with real installed TestReport/SubtestReport
objects. Separate subtest counters retain pass/fail/skip/xfail information;
acceptance rejects nonpassing subtests and still requires all unique expected
parents, exit0, no skips/xfails/setup failures. Existing TC and pure profile
positive/negative controls and Ruff5files/diff check pass (256.7ms capture).
Fix risk: callback API depends on the pinned installed pytest report class;
runtime v2 and actual-report controls verify that version, not future versions.
Required before accepting this test batch; not a production release by itself.

Raw v1/v2 and controls remain immutable. Only the launcher introductory
docstring was clarified after v2; the manifest binds executed/current hashes
and does not claim the later bytes were rerun. Independent in-memory
reconstruction replacing only the module docstring with the4328a91a version
reproduces executed707ab7... exactly, proving that document-only delta.
Frontend default-full flake,
remaining backend/PG aggregate, security, browser, performance, CI and final
readiness gates remain open. No push/deploy/production change.
