# Current-image runtime and worker shutdown — 22 September 2026

## Baseline: reproduced idle shutdown defect

Parent `9c3fa1b3540aa0fae92432e835f9f67a1eb87154`; its executable source is
unchanged from the clean33c image source. Immutable ARM64 image
`sha256:f5f8970b270d7b74b96e2b188cbfd471477a5a5655d9eb57bf007d45c96f59d6`.
This test has no dirty-source overlay. Controller SHA
`7f21f12c13d5048df68657d164a74f215af82abdda973a69c0f4ff4b817da253`,
independently reviewed before execution; eight pure controls pass.

Fresh owner-labelled internal network, PG16 volume, Redis tmpfs and containers;
no published host ports, host bind mounts or provider credentials. External
dispatch flags are false. Resource limits and disk/time guards remain enforced.
The staging YAML's SHA is checked before execution and at finalization; actual
command journal stores environment-value hashes/blank markers, not values.

Actual capture172.984048s/exit1, controller172.718s/NONPASS. Passing checks:

- Dedicated migration and schema-check containers exit0 without OOM.
- PostgreSQL16.10; exact Alembic head20260907_001; pgcrypto1.3/vector0.8.0.
- Zero users/businesses/parsequeue before and after workers.
- Gunicorn serves health/ready/root/about with HTTP200 under nonroot UID10001.
- Stop only the owned PG: health200, ready503/not_ready. Restart: ready200.
- Gunicorn stops cleanly with exit0 and no traceback.

Failing acceptance: all five canonical roles initialize and survive at least
one12-second observation after the ready marker, but each ignores normal
stopping until Docker forces termination. OOMKilled=false in every case:

| Role | Baseline stop seconds | Exit |
| --- | ---: | ---: |
| parser | 15.312 | 137 |
| agent | 15.317 | 137 |
| operator | 15.277 | 137 |
| dispatcher | 15.342 | 137 |
| maintenance | 15.435 | 137 |

All12 created resources removed (10containers/1volume/1network); exact original
23containers/20volumes/23networks inventory restored, independently rechecked.
This is WORKER-SHUTDOWN-01, not an OOM or startup failure.

The first pure-controller test attempt had one undersized mock-clock iterator;
its StopIteration is retained alongside the corrected seven-test and final
eight-test results. It is a test-harness failure, not a product regression.

## Correction and boundaries

Correction controller SHA
`9a35a5511a37bc0e84be0da74979ec97268b2826880c3c78a9b864889734048e`,
worker source SHA
`11a13e9c5ae310d7089efb0144ad374a97429e12530fe76969077e027d6ec3ea`.
Independent code/pre-execution and terminal runtime review PASS. Twelve pure
controller tests plus Ruff pass (9.301333s capture). Actual runtime
96.581747s/exit0, controller96.323s/PASS. All five roles exit0/noOOM after normal
stop: parser0.499s, agent0.551s, operator0.523s, dispatcher0.549s,
maintenance0.513s. All original migration/schema/HTTP/PG-degradation recovery
checks pass. Every copied original worker hashes b1104b54 and applied file
hashes11a13e9c; all12 created resources removed, original inventory unchanged.
Fresh owner-label absence checks were independently repeated after cleanup.

The focused worker correction handles TERM/INT through a lock-free boolean
request, finishes the current top-level polling callback, skips later callbacks
and checks idle waiting in at most100ms intervals. Handler code takes no lock
and performs no logging/DB/provider I/O. Callback order and existing cycle-error
handling are preserved. The targeted old-source regression fails because the
new lifecycle contract is absent; the actual causal baseline is the five-role
Docker failure above, not merely the missing new Python functions.

The new correction profile changes only `/app/src/worker.py` in newly created
stopped workers of the same immutable base image. Original and applied copies
are hash-verified per worker. This is source-overlay proof, not a rebuilt-image
certification or a deployment. Full source is kept in its canonical tracked
file, rather than duplicated in this evidence bundle.

Whole-file Ruff is not green: both the original clean worker and corrected
worker have the exact same64 diagnostics (code/message/line/column), with zero
in the changed region. `unit/ruff-baseline-comparison.json` records this bounded
comparison. Existing lint debt is preserved, not counted as a passing lint gate.

Final source-bound v5 mocked regression executes11 explicit modules:111 passed
plus4passing subtests in6.61s, capture7.195864s/exit0, no warnings/truncation.
v4's earlier111pass is retained; v5 follows restoration of the cadence test's
unchanged future-annotations directive. Source11a13e9c, shutdown test6f5d21bc,
cadence test25d8502d. Unit tests use the current local checkout, including its
preserved foreign edits; do not call this a clean-export full-suite result.
The supplied sandbox denies all network activity and writes outside the private
proof directory; a shim disables dotenv loading, and child environment is an
explicit allowlist. No PG-dependent captcha/resume/expired fixtures ran in this
unit slice. It is not a full backend aggregate. Source tests remain canonical
in `tests/test_worker_shutdown.py` and `tests/test_worker_outreach_cadence.py`.

Preserved prior unit/harness results: old-source8 missing-contract failures;
initial focused12pass; broader v1 shell-quoting exit127, v2 temporary-directory
setup failure, v3 actual108pass/1failed/4subtests. The v3 failure was the old
cadence test assuming the main loop's previous AST location. Its replacement
executes the real dispatcher branch and preserves both required ordering
assertions; it is not skipped or relaxed. v3's two denied-cache-write warnings
are eliminated in v4 by disabling pytest's cache provider, not by granting
repository write access. Independent final test review PASS.

Long-running active callback cancellation/draining, per-job inner-loop admission,
operator disk-import/maintenance background-thread shutdown, pre-ready signal
windows, real provider traffic and queue idempotency are not proved here. The
full audit, current rebuilt-image/CI, security, browser/demo and final review
gates remain open. No production, external sends, push or deploy occurred.
