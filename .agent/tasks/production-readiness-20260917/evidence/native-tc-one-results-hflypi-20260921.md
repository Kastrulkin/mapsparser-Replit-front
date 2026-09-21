# Native Testcontainers migration slice — scoped PASS

21 September 2026. Application source remains frozen at
`99849935de26e2932613f2a73cf515dff49104a1`; parent audit checkpoint `a244aa10`.
No application code, fixture, migration, assertion or test timeout was changed.
No production, provider, existing database, push or deployment action.

## Actual result

The unchanged node
`tests/test_card_growth_migration_pg.py::test_card_growth_schema_is_available_after_migrations`
passed: collected 1, passed 1, no skips/xfails/errors, pytest exit 0 and empty
stderr. Pytest reports 8.66 seconds; command capture 9.123 seconds; complete
preflight/probes/test/cleanup/restore 13.992 seconds. The only warning is the
existing deprecated `testcontainers.postgres` import in the fixture.

This is real Testcontainers creation/start/stop, real Flask/Alembic upgrade in
a child process and a native psycopg schema assertion. The adapter changes
only the test infrastructure: immutable local PG16 image, one retained
internal-only network, new synthetic `test` database on 512-MiB tmpfs, no
published Docker ports, and a bounded loopback-to-Docker-exec byte relay.
Image pulls, other container types, existing mounts and additional starts are
denied. Existing runtime resources were not reused for test writes.

Evidence directory: `native-tc-one-hflypi-20260921/`, seven captured files plus
SHA-256 manifest. Main capture SHA-256:
`249c3672e8a719eb27748215ebb13647f599f6a09d11f94964ee51e0340fd1aa`.

- Guard negative probes: all ten attempts denied before network/libpq IO.
- A real PATH-only child inherited the pinned guard and had a distinct PID.
- Eight capability negatives asserted their specific denial causes: stale
  expiry, wrong nonce/session/container/port, unsafe mode, foreign path and
  symlink. The original valid capability was positively checked first.
- Exactly two relay connections: Flask child PID 49800 and test parent PID
  49797, same synthetic container and relay port. Both Docker exec processes
  exited 0, graceful, empty stderr; zero rejection/failure/active connections.
- Created container
  `3463cd0148fb795926ba0126a4a98159de7655211bd2c09dd7bdb6d1af0e6953`
  was removed; fresh lookup confirmed absence. Its tmpfs synthetic data is
  intentionally discarded. No existing volumes were removed.
- Retained internal network `6fc9dbcb68ce40e46030cec829ed4613840327eda4109cd09de4ada422a4a0b4`
  is empty after test and cleanup. Capability directory is empty. All 29
  pre-existing Docker identities/running states match before and after.
- Frozen source: 5720 tracked blobs/modes verified before and after. Original
  installed guard `07d3e2dc19cbb0f9e542a6d0835ea17b5efcc5713391c152a833e6efefd61150`
  restored; temporary adapter/relay copies removed after their exact hashes
  were checked. A private pre-install guard backup is retained.

## Review and harness corrections

Independent static review accepted execution only after exact parent-to-child
mode/session inheritance, identity-bound capability checks, single-owner relay
finalization and scoped abnormal-exit cleanup were implemented. Negative cases
assert the intended reason, not merely any denial from an invalid filename.
Subprocess-group termination, disk/deadline checks and exact inventory-delta
cleanup cover the gap between container creation and event capture. These
were pre-execution harness issues, not reproduced product defects.

Independent read-only runtime review accepted this limited result and matched
all recorded support hashes, raw outputs, connection results and restored
files. Final helper checks, Ruff on five support files and `git diff --check`
pass (200.3 ms capture). Abnormal termination/cleanup branches have static
review but no forced-crash runtime proof in this slice; do not overstate it.

## Boundaries and next step

Fresh backend state is **1 passed / 5481 collected**, not a full-suite result.
Of the 94 shared PostgreSQL fixture nodes, 93 remain unexecuted; the other
5387 nodes also remain unexecuted in this fresh lane. Default frontend
parallel timing failures and the remaining security/performance/real-API/
hosted-CI/whole-goal gates are unchanged.

The default installed guard still denies Testcontainers. Current support has
a separately opt-in one-node mode; do not enable the full suite with it.
Next is a reviewed multi-test, single-container fixture module, followed by
the remaining PostgreSQL family and full aggregate. Do not repeat completed
cache cleanup, build, backup/restore, collection or this one-node proof.
Use ARM64 tmux launchers and the unchanged 5-GiB start / 2-GiB live disk floors.
Free space after the slice was 6,354,505,728 bytes (~5.92 GiB), a point-in-time
observation rather than newly reclaimed space.
