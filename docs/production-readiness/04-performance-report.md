# Performance — working measurements, not a capacity claim

Updated 18 September 2026, 08:15 UTC. Cold-request distributions are measured;
prepared-target load and query-plan acceptance remain open.
Build/test wall times are engineering feedback measurements, not user latency.
All measurements are local/synthetic; none describe production capacity.

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
uncommitted publication-reconciliation package. Native PostgreSQL 15.15 runs
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

## Still required

Prepared-target bounded request load, representative query counts/EXPLAIN
plans, and CPU/memory/queue
observations. Do not add speculative indexes, caches or structural rewrites
before those measurements identify a reachable bottleneck.
