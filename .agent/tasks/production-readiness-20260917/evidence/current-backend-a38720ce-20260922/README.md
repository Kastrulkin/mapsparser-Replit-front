# Full committed-source backend diagnostic — a38720ce

## Verdict: NONPASS

Exact source commit `a38720ce3530783caf59f6515a00baa1c532ce01`, no dirty-file
overlays. One completed full run: outer104,458.056ms/exit1, helper104.344s,
test child101.322s; no timeout, disk-floor abort or truncated stream.

| Outcome | Nodes |
| --- | ---: |
| Passed call | 4,391 |
| Failed call | 8 |
| Failed setup | 4 |
| Skipped call | 29 |
| Skipped setup | 1,090 |
| Total | 5,522 |

All5,522 teardowns pass. Setup has4,428 passes, and exactly4,428 calls occur.
The1,094 absent calls are completely explained by failed/skipped setup, not
missing telemetry. There are no duplicate/extra stages, collection errors,
xfails or node-ID drift. Fourteen additional subtests pass; they are NOT added
to the5,522-node total. No pytest warning categories were recorded by the new
category/count-only callback; arbitrary warning text is not retained.

The strict runner correctly reports `process_nonpass`,
`missing_duplicate_or_unknown_stage` and `failed_skipped_or_xfail`. Its all-stage
criterion intentionally does not treat setup skips/failures as successful calls.
Independent recomputation verifies the actual accounting, not a green suite.

## Changes since the preceding exact-commit aggregate

Previous d0ef result:4,347passed/53failed/1,116skipped across5,516 nodes.
All41 formerly failing node IDs removed from the failed set now have three
passing phases in this run. The12 remaining failed IDs are a subset of the old
53; no new failing node ID appears. The net increase of six tests comprises the two diagnostic
guard tests, pure Sheets adapter test and three PostgreSQL cursor tests; the
three PG additions skip in this offline profile. The literal node-set difference
is16added/10removed: ten media parameter IDs changed to stable explicit IDs,
plus the six genuinely added tests. No test body was removed. Earlier causal fixes and their
small runs remain separately documented; no scoped counts were added here.

Generated ZIP IDs are now stable: collection and execution match exactly without
normalization. The runtime increase from69.402s to104.458s is suite execution
time, not an application latency regression/optimization measurement; many
previously hook-blocked subprocess scenarios now execute normally.

## Remaining failures, traced to their actual prerequisites

| Family | Count | Exact failure boundary |
| --- | ---: | --- |
| Ingress proxy | 5 call | `tests/test_audit_ingress_proxy.py:24`, loopback HTTP-server bind denied by offline policy |
| Compiled runtime/load | 3 setup | `docker/compiled-script-runner/server.py:163`, server bind denied |
| Compiled source execution | 2 call | Same server module:71, explicit temporary output in `/tmp` denied outside the owned writable root; not a bind failure |
| Browser/Vite | 1 setup +1 call | `tests/e2e/vite_harness.py:31`, absent archived `frontend/node_modules/.bin/vite` prerequisite |

The ten permission failures have errno1. These twelve results are environment/
capability nonpasses, not new demonstrated application defects. Do not widen
this policy, remove assertions, skip them selectively or change production
temporary-file behavior just to make this offline aggregate green. Earlier
isolated Linux/browser runs are separate evidence and need exact source-context
continuity before reuse; they do not change this result's counts or verdict.

## Provenance and isolation

Profile: `/private/tmp/localos-current-full-a387-0iwMmh/`. The completed handles
are `audit-a387-freeze`, `audit-a387-control`, `audit-a387-full`; do not restart
these exclusive outputs. Runner056c47fc differs from accepted v10 only by
root/ref/hash/output binding and safe warning-category counters. Policy70285c3c
only rebinds the new owned roots; process helper4f16b6c3 is unchanged.

Independent review recreated the exact Git archive, SHA54aa4944, and verified
6,469 extracted files/126,524,264 bytes with zero content differences or missing/
extra files. There are no unsafe/traversal/symlink archive entries. Tar modes
6,364×0664 and105×0775 become0644/0755 under umask: content and Git executable
bits match, but full tar Unix-mode equality is explicitly not claimed. Freeze
pins these extracted modes; its source manifest remains unchanged after full
execution and independent recomputation.

Freeze13,166.664ms/exit0 and control3,025.704ms/exit0 passed eight OS probes
and nine pure accounting controls. Full repeats them. Network, Docker, user
reads, source writes and symlink escapes are denied; owned temporary writes are
allowed. Start5GiB/live2GiB floors,900s full timeout and16MiB stream caps remain.
Full process registry observes112 birth-pinned identities, signals none, and
ends with0 remaining/0 errors. Both stdout and stderr are fully accounted by
counts/digests; safe structured failure frames are retained, not raw captures.

Independent pre-execution, freeze/control and final runtime reviews accept this
bounded diagnostic evidence. The suite itself and whole-goal readiness remain
NONPASS. No production, provider, Docker build, existing database, push or
deployment was touched. The restricted untracked related-OAuth file was absent
from the Git archive and neither read nor executed. All foreign edits remain.

## Next execution lane

Services/content55 still needs a fresh synthetic fully migrated PostgreSQL DB,
not the empty PG51 fixture. Current read-only recon confirms nativePG15 has the
required vector/pgcrypto installation metadata; actual migration/run proof is
still required. Preserve strict loopback35418, generated `readiness_full_test_*`
identity, pinned first-loaded guard and12 real public tables before55/165 checks.
Image206, broader integration, load/browser/CI/demo and final independent
whole-diff/requirement audit remain open.

`SHA256SUMS` binds14 exact archived artifacts, including the preceding fixture
commit/scan captures. PREPARED.md is the historical pre-execution description;
the actual commands use ARM64 Python `-B -I` and are in the three command JSONs.
Two auxiliary unified-diff reports remain private, unchanged, under the profile
and its `uncommitted-diff-archive/`. Their valid single-space blank context lines
triggered the staged whitespace check; keeping exact executed sources makes
those reports unnecessary in Git. No raw result or detector rule was changed.
