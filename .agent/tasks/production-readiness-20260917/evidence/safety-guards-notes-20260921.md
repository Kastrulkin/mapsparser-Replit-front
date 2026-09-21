# Safety test guards — 21 September 2026

Parent: `386a16867782430f68177a926425a44d0722de24`.
Local FIX_PROVEN for three P2 test/auditor gaps:
TEST-APPROVAL-AUDIT-01, TEST-HEALTH-DB-GUARD-01 and the protected-branch part of
TEST-README-GIT-GUARD-01. These are assurance defects, not demonstrated current
production bypasses. No application runtime or native-DB behavior changed.

## Cause, change and acceptance

- The approval scanner rejected literalTrue only. Marker text survived
  unconditional or unverified expressions and expanded keyword arguments.
  Six source mutations demonstrated the gap. The scanner now accepts the
  explicit local `approval_verified` name or literalFalse, retains the True
  finding, and rejects other expressions/expanded kwargs. Omission at an
  individual call retains the orchestrator's safe False default. This is a
  runner call-shape fence, not taint analysis or proof of variable provenance.
  The orchestrator's separate controlled approved-resume path is untouched.
- The health test stub returnedFalse without recording calls, so injected
  readiness access in /health escaped the claimed DB-free check. It now checks
  zero probe calls after /health and exactly one after /ready. The regression
  test AST-loads only the actual health/ready routes into an isolated in-process
  Flask test app and runs the actual test body, with and without one injected
  probe call. It does not import the project application or PostgreSQL.
- The README test checked bare main/master tokens and missed valid destination
  refspecs. It now excludes the first repository positional and normalizes
  subsequent explicit refspec destinations. Four unsafe refspec controls,
  two feature-destination controls and two SCP/SSH remote-path controls are
  retained. Scope is the documented push form, not a general Git/shell parser.
  README, actual Git configuration and repository remotes were not changed.

Business effect: future regressions in approval admission, DB-independent health
and safe onboarding instructions are less likely to evade their stated checks.
Effort/blast radius are small (one auditor and four test files); compatibility
risk is low and fenced by valid controls. High confidence for reproduced inputs,
not universal scanner completeness. Required before relying on these CI gates.
Rollback: review/revert this local package, which would restore the weak checks;
no runtime/data migration or automatic deployment is part of rollback.

The credential-helper equals-sign candidate was withdrawn: local read-only Git
reported `invalid key: credential.helper=store`. It is not a valid setter or
proven bypass; no speculative credential-scanner change was made.

## Verified results and limits

Captures below are in this directory, suffix `-20260921.json`; they retain
exact commands and timings. The manifest binds31 source hashes and7 captures.

| Capture | Actual result | Captured ms |
| --- | --- | ---: |
| safety-guards-initial-red |20 tests,11 assertion failures including4 subtest failures;0 errors |1774.562|
| safety-guards-initial-green |20 tests pass before new remote compatibility control |1718.136|
| safety-guards-review-red |21 tests,2 remote-path false-positive subtest failures in intermediate fix |1705.030|
| safety-guards-final21-baseline |Same final21 on immutable parent checker bodies:11 assertion failures including4 subtests;0 errors |1617.667|
| safety-guards-final21-green |All21 current tests pass |2112.823|
| safety-guards-broad55 |55 pass:21 guards+25 VK+8 existing fake-readiness tests+complete read-only approval audit |2408.267|
| safety-guards-quality |Full Ruff for5 owned files, unaffected AST/diff checks,13foreign/3historical hashes preserved |385.841|

No capture timed out or truncated output. Intermediate regression was corrected
after independent review, not hidden or relabeled as a baseline product defect.
Final parent comparison reads immutable Git blobs without reversing working
files. Final harness and test bytes are the same, replacing only parent auditor,
parent README guard class and parent readiness-test body. Source hashes are
verified before/after final and broad runs.

Test execution denies socket operations, app/PG/Docker imports, env-file reads,
SQLite connect and child processes after guard installation. Native readiness
tests are not imported/executed; only the8 exact fake-connector tests are
selected for broad checks. Quality uses local Git/Ruff subprocesses. The full
read-only approval audit reads code/Compose/smoke source, never executes them.

Independent `cumulative_frontend_review_20260921` accepted the call-shape
contract, found the intermediate remote-path false positive, then accepted
the final five-file diff. Runtime admission, native PG/concurrency, real
provider/TLS/proxy, Docker/image, production and whole readiness remain unproven.

Fresh disk check on21September:3,036,432KiB available, below10GiB image floor.
Native aggregate/restore preparation denial remains; it was not retried.
No production/DB/schema, provider side effect, cleanup, push or deploy.
