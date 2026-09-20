# Performance — working measurements, not a capacity claim

20 September draft-snapshot tests/build timings are correctness-tool durations
only (COMMANDS.md), not API latency or contention benchmarks. Added approval/
draft/lead locks have no representative PostgreSQL contention measurement yet.
No performance score or capacity claim changes with this package.

Updated 18 September 2026. Cold-request distributions, one bounded prepared
dashboard profile and tiny-fixture SQL plans are measured; capacity remains open.
Build/test wall times are engineering feedback measurements, not user latency.
All measurements are local/synthetic; none describe production capacity.

## Completed working-reference comparison — 19 September Moscow

The separately reviewed v8 launcher completed the previously missing paired
comparison: working reference `2d875357` versus application checkpoint
`272794a4`, five warmups and50 serial samples per reference, interleaved ABBA.
Actual capture `journey-measure-v8-2d875357-272794a4-command.json` reports
exit0/552.856456seconds, no timeout/truncation, empty stderr; inner result is
valid with no invalid reasons. Per reference, all750 measured requests and
150 invariants pass; all75 warmup requests and15 warmup invariants pass.
These counts must not be added to overlapping historical suites as unique tests.

Independent review recomputed all15step distributions and all five journey
distributions from the raw samples. Exact110unique owned database names are
absent from the verified local cluster; no supervised process remains and the
new source archive was cleaned. The old interrupted archive remains preserved.
The scoped comparison passes; overall AC7 still needs its broader reconciliation.

The following quantiles are recomputed from each successful run's sum of timed
request durations for that journey, not sums of per-request percentiles.

| Journey | Working reference p50 / p95 / p99, ms | Current p50 / p95 / p99, ms |
| --- | ---: | ---: |
| Authentication and tenant |148.8 /192.1 /245.3|148.1 /193.3 /249.0|
| Service menu |303.6 /402.1 /467.8|310.2 /374.4 /430.8|
| Finance import |250.8 /308.5 /365.9|248.4 /338.7 /395.6|
| Content |472.9 /564.1 /584.0|467.8 /528.6 /555.6|
| Operator |139.6 /165.2 /181.1|138.4 /202.9 /259.6|

Medians are close and tail changes are mixed. Finance and Operator p95/p99
increased in this sample; do not hide those observations or attribute them to
a cause without a controlled follow-up. No overall speedup is established.
p99 remains exploratory at50samples. Native cold Flask dispatch/real SQL with
deterministic provider seams excludes network, browser, migrations/setup and
human think time; these are not full user journey wall times or production SLOs.
This supplement does not replace the original302baseline's recorded failures,
the earlier interrupted comparison, bounded HTTP load or browser observations.


## Supplemental comparison interrupted — 18 September 16:05 UTC

The original302 auth baseline fails50/50, leaving successful auth quantiles
null. A separate paired comparison of working post-correctness2d875357 and
272794a4 was attempted (five warmups and50 serial samples per reference).
Its outer wrapper failed with PermissionError/errno1 before the final inner
result. Raw `journey-measure-postfix-272794a4-command.json` is invalid;
31 completed child files are diagnostic partial data, not an accepted comparison.
The process controller loses failure phase/traceback, so stale process-group
reuse is only a hypothesis, not a proven cause. No speedup or successful
before/after result follows. Source copies, partial samples and the interrupted
synthetic DB are preserved; no matching benchmark process/session remains.

## Browser observations — 18 September 15:30 UTC

Two routes × three viewports × ten fresh browser contexts: **60/60 samples**,
zero page errors and zero horizontal document overflow. The measured gate is
the visible email field on `/login` or the visible `Проверить файл` control on
`/dashboard/finance?tab=import`; visible does not mean above the viewport fold.
Synthetic login is outside finance timing. Request interception disables HTTP
cache, blocks external origins and browser mutations; no CPU/network throttling.
Navigation, first paint and resource observations are retained in the raw file.

| Viewport | Route | p50 / p95 / p99 ready time, ms |
| --- | --- | ---: |
| Desktop | Login |372.250 /1110.769 /1539.851|
| Desktop | Finance import |354.108 /709.685 /930.429|
| Laptop | Login |356.948 /372.533 /378.554|
| Laptop | Finance import |354.007 /376.659 /383.456|
| Mobile | Login |324.730 /441.329 /469.528|
| Mobile | Finance import |349.054 /382.444 /399.238|

Independent review recomputed counts and quantiles and accepted the bounded
capture. Root inspected all six initial-viewport screenshots: login controls
and finance empty-state layout are readable, without observed overlap. The
finance import control is below the initial fold; these screenshots are not a
complete-page accessibility or import-interaction audit.

Scope: already-running **historical f0cc backend** and `20431224` built frontend
(frontend Git tree unchanged through `272794a4`). Eight referenced JS/CSS assets
were byte-matched between ingress and the pinned container. This is not current
272 backend/image, Web Vitals, SLO, capacity, a before/after comparison or a
speedup claim; ten samples per group make tail quantiles exploratory. Desktop
outliers remain in the data, without an invented causal explanation.

Raw `frontend-perf-272-retry.json` and `frontend-perf-272-retry-command.json`:
valid true, exit 0, 48.980093 seconds, no timeout/disk abort/truncation. Helper
`0d6407af`, shell `94690117`, outer `0e0528e1` are frozen. The first capture
(`frontend-perf-272*.json`, without `retry`) remains exit 1 in 4.144076 seconds,
zero browser samples: an incorrect harness HTML-hash comparison ignored Flask's
SEO injection. The retry compares exact served assets, not transformed HTML.
No application code changed, and the first failure is not a product defect.

## Bounded sustained localhost reads — 18 September 15:18 UTC

Exact272794a4 clean archive, nativePG15 and Gunicorn one worker/two threads:
four synthetic tenants,30waves, two sequential reads per client, at most four
clients concurrently. Two seconds after each completed wave; not a strict
4requests/second arrival cap. **240/240 semantic reads pass**, timed wall
64.280315s (including pacing), command73.497287s,exit0/no timeout/truncation.
Login/migrations/setup are outside the timed phase. This is current-only,
not a before/after, production-capacity, queue-load, proxy or SLO result.

| Route | Successful samples | p50 / p95 / p99, ms |
| --- | ---: | ---: |
| `/api/auth/me` |120/120|78.638 /118.355 /134.497|
| `/api/business/<id>/data` |120/120|80.003 /104.552 /117.980|

Quantiles use linear interpolation of observed successful samples. Ten periodic
`ps` snapshots supplement before/after observations; sampled total Gunicorn RSS
ranges62,640–208,368KiB (before208,304,after69,616). This is not true peak usage,
instantaneous CPU, a leak test or evidence of memory optimization. OS/process
memory accounting can change under pressure; no causal explanation is claimed.
Gunicorn exits0 onSIGTERM and is reaped; fresh synthetic DB OID5775953 is
removed after identity verification; root and independent reviewer confirmed
catalog absence. Independent review recomputed counts and quantiles and accepted
the bounded result. Raw: `http-sustained-272794a4.json` and its
`-command.json`; reviewed helper5ca74c29,outere4826e78. No production writes.

## Bounded localhost HTTP checkpoint — 18 September 13:18 UTC

Exact3dca5fda clean source, native PostgreSQL15 and a local Gunicorn child
(one worker/two threads): four synthetic tenants log in sequentially outside
timing, then five rounds of two authenticated read routes, concurrency at most
two and150ms between waves. All40timed reads pass status and expected
user/business/service identity checks; timed wall2.557582s includes pacing.
This is a current checkpoint only, not a before/after comparison, Docker/proxy
measurement, sustained-load test, SLO, production-capacity or speedup claim.

| Route | Successful samples | p50 / p95 / max, ms |
| --- | ---: | ---: |
| `/api/auth/me` |20/20|66.979 /102.234 /104.456|
| `/api/business/<id>/data` |20/20|41.897 /64.486 /64.594|

Quantiles are linearly interpolated and exploratory at20samples per route;
no p99 or throughput extrapolation. Two `ps` snapshots report total Gunicorn
RSS193728→184448KiB and %CPU57.4→7.5. These are diagnostic snapshots, not peak
RSS, timed-phase mean CPU or evidence of a memory improvement. The raw method
identifier includes `instant`, but no stronger CPU sampling semantics are
claimed here. Gunicorn terminated with SIGTERM/exit0 and was reaped; exact
new DB OID3967105 was removed and its absence independently confirmed.

Proof: `raw/http-gunicorn-3dca5fda-retry.json` plus command capture exit0,
13.170562s/no timeout/truncation; independent review recomputed all counts and
quantiles. First attempt exit1/3.080768s stopped before Gunicorn/requests because
its migration command omitted explicit Flask app configuration. Its raw files
and fresh DB OID3967104 remain preserved; it supplies no latency measurement.
Only the temporary launcher changed; application source remained3dca5fda.

## Measured storage improvement

The reviewed Docker change6eb2d185 removes `/ms-playwright` only from the final
recursive ownership change. Installed binaries remain root-owned and readable;
runtime writable directories retain the nonroot user's ownership.

| Same Docker inspection field | Before (a0253199) | After (4a8e33b8) |
| --- | ---: | ---: |
| Image `.Size`, bytes |1,376,269,248|1,070,569,043|
| Change | |−305,700,205bytes /−22.2%|

Both images contain Chromium and both frontend artifacts. Exact image IDs and
commands are in task raw `docker-a0253199-build.json`,
`docker-4a8e33b8-build.json` and `docker-4a8e33b8-smoke.json`.
Actual after-image smoke passed with UID10001, read-only root, network disabled,
Chromium153.0.8010.12, pypdf6.16.1 and dependency compatibility check. Docker's
reported image size is not the same as filesystem space immediately reclaimed.
The build also changes source/frontend flags; it is not a byte-for-byte
controlled single-variable image experiment. The redundant ownership layer's
removal is directly visible in Docker history.

Build wall time changed276.824s→61.615s, but cache state differed; **do not call
that a build-speed optimization**. Backend native suite296.79s, resumed PG16
selection177.72s, and browser215.298s also cover different environments/scopes.

## Five critical user journeys

The source of scope is [01-system-map.md](01-system-map.md).

| Journey | Timed request steps | Current evidence |
| --- | --- | --- |
| Authentication and tenant |login, me, business data|50 current successes; baseline business request fails 50/50|
| Service menu |draft, review, apply, replay|50 samples per ref; real SQL/approval/replay|
| Finance import |preview, apply|50 samples per ref; real import plus duplicate-data invariant|
| Content draft |plan, draft, internal news|50 samples per ref; text generation explicitly stubbed|
| Operator action |proposal, confirmation, replay|50 samples per ref; planner stubbed, real scoped confirmation/SQL|

`readiness_journey_benchmark.py` checks15requests and3untimed invariants in one
fresh owned database. Its first accepted sample is a correctness proof, not a
latency distribution. `readiness_journey_measure.py` compares peeled distinct
Git commits using clean archives, identical injected harness/fixtures/provider
seams and guard hashes. Serial samples are interleaved ABBA. Setup/migrations
are outside each request timer, but processes and databases are cold: these
are **not warmed production-service latency measurements**. Failed requests
remain failures, not successful fast samples; missing/duplicate required steps
invalidate the run. p99 with fewer than100 successes is exploratory.

Concurrent mode is explicitly **full-harness stress**, including migration and
fixture activity. It reports correctness only; concurrent request latency/load
capacity needs a separately prepared-target/barrier method. This limit is not
closed by relabeling the stress result.

## Measurement safety and pilot

Run only against the known task-owned literal-loopback/high-port PostgreSQL,
with the reviewed no-egress `sitecustomize.py` first, no dotenv/provider
credentials and no libpq overrides. Every child has a timeout/process group
and a fresh UUID database; a pre-existing name is never reused/deleted.
Record exact code/harness/guard IDs, environment, sample count, errors and raw
results. Host resource pressure is material: run builds/scans/browser/load
serially and stop before disk exhaustion.

The first real driver pilot619760b4 stopped before database creation because
macOS `/tmp` and `/private/tmp` aliases were compared lexically. The failure is
retained in `raw/journey-measure-pilot-619760b4-command.json`. Canonical-path
containment and real symlink regressions were independently verified (32 tests)
and committed as `fa4e15b8`.

The corrected pilot compares baseline `30262a5b` with `5c1af983`, one cold
sample per revision, no warmups/load. It completed in18.466s and deliberately
returned exit1/valid=false: baseline business-data request returned HTTP500
(14/15 successful requests), whereas current returned15/15 successful requests.
Both revisions passed3/3 untimed invariants. This is the already-fixed legacy
transaction-date/row-mapping defect, not a reason to discard the baseline error.
Both task-owned child databases were absent after cleanup. Raw
`journey-measure-pilot-fa4e15b8.json` and its command capture retain results,
import origins, source/guard hashes and error details. A single sample does not
support any latency improvement claim; failed-operation quantiles are null.

## Repeated cold-request results

Raw `journey-measure-serial-8ebec5ca.json` and its command capture record
543.315 seconds wall time, 5 excluded warmups and 50 measured samples per
revision. Baseline is `30262a5bf7b468e0a6f5a0e3d8262dbef119e075`, current is
`8ebec5ca822db1171e05a690377255b3c2205655`. This does not include the later
committed publication-reconciliation package. Native PostgreSQL 15.15 runs
in the owned cluster on literal loopback port 35418; no production data or
provider traffic is involved.

Both revisions completed all 55 harness processes. In measured samples,
baseline passed 700/750 requests and 150/150 invariants; current passed
750/750 requests and 150/150 invariants. All baseline failures are the same
business-data HTTP500 (`column "date" does not exist`), already fixed in
43578807. Warmups independently show the same failure pattern. The driver
correctly retains `valid=false` / exit 1 for the broken baseline; this is not
a fully passing comparison. Per-success latency statistics remain descriptive.
Every run records its database absent after the child; a subsequent catalog
check found no `localos_readiness_measure_%` database (captured in
`journey-measure-cleanup-check-20260918.json`). An independent reviewer
recomputed every request and journey quantile, count and cleanup record and
confirmed the tables below; that review does not close the remaining load gate.

The table below sums the timed request durations **within each successful
journey sample**, then computes linearly interpolated quantiles across its
50 totals. It does not sum request quantiles. Setup, inter-request fixture
work, invariants, browser rendering and human think time are excluded: these
are request-work totals, not end-to-end user journey wall times.

| Journey | Baseline p50 / p95 / p99, ms | Current p50 / p95 / p99, ms | Failed journeys, before → after |
| --- | ---: | ---: | ---: |
| Authentication and tenant | unavailable | 145.7 / 163.9 / 176.2 | 50 → 0 |
| Service menu | 302.9 / 362.2 / 384.7 | 302.9 / 353.5 / 366.3 | 0 → 0 |
| Finance import | 248.8 / 276.2 / 283.0 | 248.8 / 293.7 / 342.2 | 0 → 0 |
| Content draft | 465.5 / 529.4 / 565.2 | 465.6 / 520.0 / 530.1 | 0 → 0 |
| Operator action | 141.4 / 176.5 / 195.6 | 141.2 / 161.0 / 189.0 | 0 → 0 |

Individual request results (each 50 measured requests per revision) provide
the narrower API view. All pairs below have zero errors except business data,
whose baseline has no successful latency sample.

| Request step | Baseline p50 / p95 / p99, ms | Current p50 / p95 / p99, ms |
| --- | ---: | ---: |
| Login | 71.9 / 78.0 / 84.6 | 72.5 / 83.3 / 86.3 |
| Current user | 36.1 / 42.9 / 54.0 | 35.8 / 40.7 / 58.4 |
| Business data | unavailable | 37.4 / 43.8 / 47.3 |
| Service draft | 84.2 / 100.9 / 114.1 | 82.7 / 91.0 / 122.1 |
| Service review | 72.4 / 90.8 / 105.0 | 72.4 / 83.5 / 99.3 |
| Service apply | 74.4 / 90.1 / 140.2 | 74.2 / 87.4 / 98.5 |
| Service apply replay | 69.5 / 86.6 / 107.3 | 69.9 / 93.7 / 112.7 |
| Finance preview | 112.6 / 124.8 / 133.3 | 112.0 / 139.0 / 169.9 |
| Finance apply | 135.4 / 154.9 / 158.7 | 135.6 / 159.2 / 202.6 |
| Content plan | 240.2 / 287.5 / 308.0 | 239.4 / 280.8 / 296.2 |
| Content draft | 113.3 / 131.9 / 151.7 | 113.4 / 137.8 / 150.0 |
| Internal news | 108.6 / 121.6 / 134.6 | 109.4 / 129.7 / 140.1 |
| Operator proposal | 75.5 / 91.6 / 109.9 | 75.0 / 87.7 / 109.4 |
| Operator confirmation | 37.4 / 45.3 / 68.5 | 37.5 / 44.9 / 57.1 |
| Operator replay | 26.7 / 37.6 / 51.3 | 26.7 / 30.0 / 31.8 |

Interpretation: the observed improvement is correctness of business data, not
a demonstrated general speedup. The four comparable journey medians are nearly
unchanged. Finance tails are higher in this run; this is visible follow-up
evidence, not concealed by an average. With only 50 samples, shared-host
resource pressure, cold processes and stubbed external services, p99 is
exploratory and neither a production SLO nor proof of a causal regression.
No cache/index/refactor optimization is justified by these results alone.

## Prepared dashboard profile and admission boundary

Reviewed read-load harness e3f42dbf initially failed before timing because its
parent seed import depended on pytest's source path. Raw
`prepared-load-e3f42dbf{,-command}.json` records ModuleNotFoundError/exit1 and
successful cleanup. A fresh-process regression reproduced the exact import
failure;94de718c fixes canonical source resolution (45combined harness tests,
independent review). Failed evidence was not overwritten.

Clean94de718c with8prepared users and two concurrent clients per wave sent
8logins from the same test-client IP:5returned200,3returned429, matching the
unchanged login limiter5/minute. Their dependent reads were unauthorized, so
the run correctly reports valid=false/exit1. This is an admission-boundary
observation, not a product failure or a passing load result. Raw
`prepared-load-94de718c{,-command}.json` retains all88request attempts.

The same committed harness was then run with4prepared users, two concurrent
clients per wave and5read repetitions per user, without disabling the limiter.
Setup/migration/seeding precede timing. All44semantic checks pass:4real logins,
20current-user reads and20business-data reads; each response matches its own
tenant/service identity. Captured wall time9.249s includes setup/cleanup and
must not be used as a throughput denominator. Both actual measurement DBs were
removed; raw `prepared-load-four-94de718c{,-command}.json` records exact names.
An independent reviewer recomputed counts and quantiles.

| Prepared request | Successes | p50 / p95 / p99, ms |
| --- | ---: | ---: |
| Login |4/4|74.609 /77.663 /77.734|
| Current user |20/20|38.187 /110.875 /113.004|
| Business data |20/20|39.562 /43.186 /44.100|

Measured child CPU deltas are0.145952user+0.038735system seconds. Its maximum
RSS high-water rises164,593,664→166,084,608bytes (1,490,944bytes); this is not a
heap measurement, memory-growth rate or steady-state allocation claim.

Scope is in-process Flask test-client request dispatch on nativePG15, not HTTP
server throughput, sustained load, worker-queue capacity or provider execution.
All quantiles, especially p99 at n4/n20, are descriptive/exploratory. The legacy
business-data GET also performs compatibility DDL internally, so this is
dashboard-read traffic, not a database read-only workload. No general speedup
or production capacity acceptance follows from this one profile.

## Actual query counts and representative plans

Clean f0cc182a harness ran on18September against one newly created UUID-owned
nativePG15 database after canonical migrations and a tiny synthetic seed.
`query-proof-f0cc182a{,-command}.json`:exit0/10.308584s, validtrue, childcompleted,
no invalid reasons, exactownedDBremoved (independent catalog check confirms).
Guard origin/SHA, exactPGdata_directory and env-i were checked before execution.
No production data or providers. Capture duration includes setup/cleanup,
not request latency or query throughput.

| Actual API route | Instrumented statements | Read | DDL/write |
| --- | ---: | ---: | ---: |
| `/api/auth/me` |4|4|0|
| `/api/business/<id>/data` |12|9|3|

Instrumentation counts `DatabaseManager.DBCursorWrapper.execute`, not every
possible PostgreSQL driver call. The3compatibility statements are legacy
CREATE TABLE IF NOT EXISTS forFinancialTransactions/BusinessProfiles and
ALTER UserServices ADD COLUMN business_id. On the migrated fixture theALTER
fails and is swallowed; its followingNULL-business backfill is not reached.
Alembic owns these objects in20250207_002/20250207_009, with finance evolution
20260224_003. Runtime fallback definitions differ from canonical migrations.
Removing them needs supported-upgrade/legacy regression coverage, not an
index/cache guess. Statement count alone does not prove a latency bottleneck.

Three bounded parameterized EXPLAIN ANALYZE BUFFERS plans were captured:
representative business-access join0.562ms execution, active services0.023ms,
cards0.018ms. The first omits dynamic moderation/parser filters; it is not the
exact full route query. Fixture has onebusiness/oneservice/zerocards.
Services/cards use existingbusiness_id indexes; access includes a smalltable
sequential scan plus membership/network indexes. These single tinyfixture
samples are query-shape evidence, not index need, production timing or capacity.

## Schema-free GET follow-up — 20431224

The same isolated harness after reviewed GET correction2d875357 passes in
7.933036s (`query-proof-20431224{,-command}.json`), validtrue/no invalid reasons.
`/api/auth/me` still executes4read statements. Business data now executes
**9read statements and0DDL/write**, versus9reads+3DDL in the priorf0cc run.
This demonstrates removal of request-time schema maintenance, not a measured
end-user latency improvement. The new representative plans execute in
0.551/0.032/0.018ms on the same tiny fixture shape; these single samples do not
justify index changes or capacity claims. Exact ownedUUIDdatabase was removed;
root's separate catalog check returned0. Source archive retained at
`/private/tmp/localos-readiness-query-20431224.wJNhxf`. The raw harness's static
route_note still describes legacy DDL, which is stale prose, not measured
behavior; the counted statements above are authoritative. The note is corrected
for subsequent runs without rewriting this captured artifact.

## Still required

Complete the supplemental paired five-flow comparison after fixing the process
controller and restoring local disk headroom. Sustained localhost HTTP and
bounded frontend observations are now recorded above; production/large-data/
queue capacity remains unmeasured. Do not add speculative indexes, caches or
structural rewrites before measurements identify a reachable bottleneck.
