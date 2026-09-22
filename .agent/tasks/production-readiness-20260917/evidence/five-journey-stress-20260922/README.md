# Five-journey native stress/resource evidence

## Terminal v2 result

**PASS for this bounded profile:** 42/42 runs, 630/630 requests and 126/126
invariants, no invalid sample. Outer capture 242,315.327 ms, exit 0; controller
242.104 seconds, driver 221.380 seconds. Each reference contributes exactly
one serial and twenty stress runs, 315 requests and 63 invariants.

| Observation across 21 children/reference | Baseline | Current |
| --- | ---: | ---: |
| Highest sampled process-tree RSS, bytes | 269,680,640 | 311,050,240 |
| Mean sampled maximum live-tree CPU, seconds | 3.104 | 3.217 |
| Highest sampled live-tree CPU, seconds | 3.638 | 3.722 |
| Mean whole-child duration, seconds | 9.906 | 10.148 |

These include setup/migrations and the single serial smoke. Current sampled RSS
is higher; this observation is retained, not called an optimization or a proven
regression. Baseline/current execution order and the sampling limitations below
prevent a causal interpretation. Existing serial request quantiles are separate.

All 42 generated databases are absent; final catalog contains only postgres,
template0 and template1. The owned PostgreSQL was identity-checked and stopped
intentionally. Its registry and the driver's 120 observed process identities
are clean: no forced signals, remaining members or errors. Guard controls,
source manifests and exact input/policy hashes pass. Driver stdout/stderr are
empty, without truncation. A separate OS process check confirms postmaster58370
and driver58395 are absent; the completed tmux session is gone.

Raw result SHA-256:
`28678a775a6184e401a2c581e5f7da800ca0bebfbcc8403bf9ccffd1ece61ac2`.
Driver result SHA-256:
`6cd34264ec252bfee98d0ee11e8a3c055abf3b96c5f2ea1fc5d3cd70a5cb631c`.

Independent terminal review: **bounded PASS**. The reviewer recomputed all756
samples, exact per-phase indices, unique database identities, actual provenance,
source/guard/input hashes and clean child/driver/postmaster registries. A read-only
OS check over every recorded owned PID returned no remaining processes. This
acceptance does not certify unmeasured scopes listed below.

## Profile and scope

Fixed profile: baseline `272794a439a76204536480f158e79276ccd7b318`, current
`a38720ce3530783caf59f6515a00baa1c532ce01`; zero warmups, one serial smoke and
20 stress runs per reference, concurrency two. Exactly 42 valid runs would
contain 630 request results and 126 invariant results. Counts must be derived
from actual samples, not inferred from the requested arguments.

The five journeys are authentication/tenant access, service compression,
finance import, content and Operator approval/replay. Each child creates and
removes its own UUID-named synthetic PostgreSQL database. The same existing
benchmark is explicitly overlaid on clean Git archives of both versions;
original and runtime source manifests are distinguished. No dirty or untracked
workspace source, production database, retained Docker container or real
provider is used.

Only private supervision changed: immediate birth-pinned ownership, bounded
streams and deadlines, actual harness provenance validation, cleanup on error,
and sampled process-tree CPU/RSS. No test assertion or product code changed.
The runner requires an externally hash-bound reviewed-input manifest. The
policy denies external network, user-home reads and writes outside the owned
runtime, and additionally protects source, guard and input files.

## Preparation and preserved nonpass

- Initial adapter drafts failed root review before any execution; they did not
  become workload evidence. Final adapter validates provenance from actual
  output, not values copied from its expectations.
- Pure v1: 22 passed, 620.847 ms. Pure v2: 22 passed, 376.066 ms.
- Independent review found manifest read/hash TOCTOU and a false-PASS path if
  PostgreSQL exited before final cleanup. Both were corrected. Pure v3:
  31 passed, 558.679 ms. Targeted Ruff passes after removal of one unused import
  and formatting fixes; the initial lint attempt had 15 findings.
- Native v1: 19,978.820 ms, exit 1, **zero workload runs**. An inherited working
  directory under denied `/Users` broke a Python import in the OS denial probe.
  Fresh PostgreSQL stopped intentionally; exact system-only catalog and empty,
  unsignalled process registry were verified. This is a launcher prerequisite
  failure, not a product failure. The executed v1 controller and raw result are
  retained.
- The only v2 controller correction is `os.chdir(new_owned_runtime_root)` plus
  its import, before helper/probe calls. Same OS policy. Isolated cwd probe:
  38.510 ms, exit 0, off-port denial confirmed. Independent correction review
  accepted the v2 input hashes before launch.

## Interpretation limits

Stress runs execute baseline first, then current; this is not a randomized or
interleaved causal A/B performance comparison. The single serial smoke per
reference is not a latency distribution. Existing larger serial measurements
remain separate evidence and were not repeated or merged here.

Child durations and resource observations include cold startup, synthetic
schema/migrations and fixture setup, not just request handling. RSS sums sampled
live process-tree values and may double-count shared pages; CPU is the maximum
observed sum of live-process cumulative CPU seconds, not total CPU consumed or
CPU percentage. Sampling can miss peaks and short-lived descendants. These are
bounded observations, not proof of capacity, production throughput, absence of
memory leaks, real-provider latency or complete readiness.

The original full readiness goal remains open, including image/security,
current clean Docker/CI integration, broader browser/demo and final whole-diff
review. This test is not a production deployment or an aggregate-suite pass.
