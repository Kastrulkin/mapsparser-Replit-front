# Local content performance comparison — 22 September 2026

## Result

The completed local serial comparison is valid: 50 measured runs per ref, 5 warmups per ref, 0 failed request steps, and 0 failed invariants. It compares baseline `272794a439a76204536480f158e79276ccd7b318` with current `dc1a6b76821683effe2d949cfcd4a9f3c1e15cef`.

It is a bounded deterministic regression check, not a production capacity or end-to-end user-speed claim. There is no supported overall speedup or causal conclusion.

## Method and validity

- ABBA ordering, 5 warmups and 50 serial runs for each ref (110 ref-runs total); warmups are excluded from percentiles.
- Each ref made 75 warmup and 750 serial requests (15 steps/run), with 15 and 150 successful invariants respectively. All 1,650 requests and 330 invariants passed.
- PostgreSQL 15.15 ran locally as an owned temporary cluster on `127.0.0.1:64052` (x86_64 under Rosetta); the harness process was Python 3.11.7 arm64. This mixed-architecture local environment limits generalization.
- Fresh owned synthetic databases were created per run and removed; no production, retained database, Docker container, provider account, or browser was used.
- Deterministic seams replaced `content_text_generation` and `operator_planner`. The content-plan draft path patches `content_plan_service.analyze_text_with_gigachat`; no real LLM/provider call occurs. `internal_news` is an internal database write under a seed with no content rules or price claims, so it does not call a social provider.
- The synthetic seed has no site/website, so no website-fetch path was exercised. Load samples: 0. No concurrent-load, browser, external network, provider delivery, or production claim follows.

## Five-journey serial latency (ms)

`p99` is exploratory at n=50. It must not be read as an SLO or tail-capacity result.

| Journey | Baseline p50 | Current p50 | Baseline p95 | Current p95 | Baseline p99* | Current p99* |
|---|---:|---:|---:|---:|---:|---:|
| auth_tenant | 148.793 | 148.202 | 159.650 | 155.400 | 174.649 | 159.481 |
| content | 478.622 | 482.938 | 525.094 | 519.408 | 541.526 | 533.073 |
| finance_import | 253.617 | 254.293 | 282.243 | 280.425 | 316.935 | 316.454 |
| operator | 141.746 | 141.846 | 155.091 | 154.520 | 185.958 | 170.311 |
| service_compression | 312.364 | 312.254 | 329.894 | 333.498 | 353.838 | 341.271 |

## Content path detail (ms)

| Step | Baseline p50 | Current p50 | Baseline p95 | Current p95 | Baseline p99* | Current p99* |
|---|---:|---:|---:|---:|---:|---:|
| plan | 245.928 | 252.183 | 272.632 | 273.882 | 300.813 | 281.288 |
| draft | 116.492 | 115.850 | 142.334 | 139.002 | 167.039 | 154.493 |
| internal_news | 112.046 | 112.929 | 125.420 | 120.711 | 138.578 | 138.657 |
| content total† | 478.622 | 482.938 | 525.094 | 519.408 | 541.526 | 533.073 |

† For each serial run, `content total` is the sum of its three content request durations; percentiles are then computed over 50 such sums. It is not a sum of independently calculated percentiles.

For this deterministic fixture, content total differs by +4.316 ms at p50, -5.686 ms at p95, and -8.453 ms at exploratory p99. `plan` has a +6.255 ms (about 2.5%) median difference; other content values and tails are mixed. This does not establish a material regression, bottleneck, speedup, or cause.

## Evidence and reproducibility

- Harness: `scripts/readiness_journey_benchmark.py`, SHA-256 `28308a23ce8ac3e04f4c60e0438076ce60b15e5fc506667acb4ef93eb65d8a26`.
- Driver: `scripts/readiness_journey_measure.py`, SHA-256 `5fd78e2770cfd4e0d325ec04748be3572027ce75ce7eeb6336fab3ca0ac403e1`.
- Guard: `/private/tmp/localos-content-perf.cuey0qa9/guard/sitecustomize.py`, SHA-256 `9b1dedef6d1277d225a400edc42325689b5162c296343af7f941fcdabc6badfb`.
- Raw driver: `/private/tmp/localos-content-perf.cuey0qa9/driver-output.json`, SHA-256 `ffd51f58179b21ff4265f71fa924a27df8c2a1104a48b64826cbf0fa5411f60e`.
- Wrapper: `/private/tmp/localos-content-perf.cuey0qa9/wrapper-result.json`, SHA-256 `24ded53812b5417d9e7bb362cfffe38c9294aec0a97a38dfe41a29f94001bb04`.
- Terminal capture: `/private/tmp/localos-content-perf-deps.7zNvCi/full-v1-command.json`, SHA-256 `66a3dc449053c6fa3efe7ccf729d01ba40ccb536ba3f6573319141519238b884`; exit 0, duration 607.027 s. Exact command:
  ```text
  /usr/bin/arch -arm64 /private/tmp/localos-readiness-20260921.hfLYPi/native/venv/bin/python -B .agent/tasks/production-readiness-20260917/support/content_performance_native_20260922.py --execute
  ```
- Independent verifier: `content-performance-20260922/independent-recompute-v2.py`, SHA-256 `305645456f4dff944a4eabd1c46ad7cf1894482680f4a39a196e936015879e0e`; result `content-performance-20260922/independent-recompute.json`, SHA-256 `3c8b9e4583b956509def0803fc6f622fdf3bd5c99b095e2665631eab5e150207`. It independently recomputes inclusive percentiles from successful serial raw data, validates ABBA/ref counts and all 15 steps per run. V2 removes an unnecessary numeric conversion to respect project rules; its output is byte-identical to the retained original temporary result. It does not rerun the benchmark. The frozen verifier paths point to the historical temporary input/output, not a portable launcher.

## Durable artifacts and acceptance

The original full captures were copied byte-for-byte to the sibling
`content-performance-20260922/` directory as `full-v1-{command,wrapper,driver,
driver-capture,initdb,probes,context}.json`. The independent result includes all
15 step distributions and five journey distributions, not only the tables above.
`SHA256SUMS` binds the copied artifacts and six support sources. Original
temporary paths remain in captures for provenance; they are not live services.

Wrapper source SHA256 `0cafe7e3828d950db73b5fb88b6dc3177e329aee5eba10f98b10b59b9a43b6ba`;
process ownership helper `4f16b6c343223717dcf3b5bdbf86ff9159594b33fa92d744527891188c4c227b`.
The process registry observed 261 child identities, signalled none and ended
with no remaining process or error. All 110 unique generated database names
were verified absent; final catalog contained only postgres/template0/template1.
Only the owned PostgreSQL PID95496 was stopped. Private stopped cluster files
remain; no additional filesystem/Docker cleanup happened in this package.

Two independent reviews accepted (1) runtime identity, controls, source/dirty
preservation and cleanup; (2) raw counts/ordering and percentile recomputation.
Root inspected terminal captures, copied hashes and unchanged foreign diff.
These scoped acceptances do not replace a final whole-project review.

The trusted-code runtime uses guard-first exact host/port/role/database admission,
cleared environment, bounded connections/statements, and OS network/write denial
outside the owned root/loopback port. Guard/context writes are denied. Six
negative probes pass, including an actual native libpq off-port EPERM. Reads are
not universally denied and process polling does not establish hostile-code
containment; do not present this harness as an arbitrary-code sandbox.

## Fixture attempts and controls retained

- Pilot v1: exit1, 4.352774s, no driver. macOS rejects numeric-host notation in
  the sandbox address filter. Owned PostgreSQL94293 stopped. Separate
  `probe-diagnostic-v2.json` records supported syntax; no v1 negative-probe
  artifact is claimed. The final guard/PG connector still uses exact127.0.0.1.
- Corrected standalone six probes: exit0, 522.024ms; no PostgreSQL started.
- Pilot v2: exit1, 14.338398s; both revisions fail migrations before request
  rows because C-locale initdb defaulted to ASCII. Driver reports its two DBs
  absent; PG94645 stopped. This old attempt did not reach the independent final
  catalog query, so that extra cleanup proof is not claimed for v2.
- Pilot v3: exit0, 20.276493s, driver17.590s after explicit initdbUTF8 and live
  encoding checks. Each ref passes15requests+3invariants, both DB names absent,
  system-only catalog, PG94888 stopped. This is smoke, not distribution evidence.
- Final helper controls: guard11/11 (`guard-controls-v2.json`,346.4ms), wrapper7/7
  (`wrapper-controls-final.json`,123.720ms), process5/5 (`process-controls.json`,
  38.3ms). Pure fake-process controls are separate from actual lifecycle evidence.
  Earlier captures are retained, not overwritten. These are23 helper controls,
  not additional application test coverage.

No application change was needed for these setup failures. Following the
bug-reproducer workflow, they remain environment/fixture findings, not product
bugs. psutil7.0.0 was installed only into a private helper target; its239KB wheel
SHA256 is `39db632f6bb862eeccf56660871433e111b6ea58f2caea825571951d4b6aa3da`.
The retained Python environment and project dependencies were not modified.

The secondary OAuth-related-refresh candidate is separately platform-restricted,
unrun and uncommitted. No production, provider, push or deployment occurred.
The measured-current content gap is closed only at the fixture scope. Current
full aggregate, broader performance, security/image/owner decisions, CI/demo and
final whole-diff review remain incomplete.

## Prior package scan provenance

Four `previous-package-*` captures preserve the dc1a6b76 package outcome:
strict staged Gitleaks exited1 with10 generic-key matches, not zero findings.
The first triage retained3 unclassified; final triage identifies all10 as exact
source-hash false positives,0unclassified (no suppression). Commit exited0 in
285.307ms. These are previous-package records, not the current package scan.
