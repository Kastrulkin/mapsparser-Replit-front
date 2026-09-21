# Native runtime checkpoint — 21 September

Scoped results only. Frozen application source is99849935; no product code,
production, existing database, external provider, push or deployment changed.
Historical whole-goal FAIL remains and Testcontainers startup stays disabled.

## Proven

- Guard v3: ten exact denial probes pass without emitting prohibited IO;
  a genuinely stripped-env child loads the same path/hash, has its own PID,
  and preserves bytecode/user-site exclusions; one owned PostgreSQL read-only
  identity SELECT passes after immediate pinned Docker preflight.
- Full safe collection:5481tests in13.22s (15.504s capture), exit0, stderr empty.
  No test bodies run. Terminal collection hooks forbid libpq connections,
  sockets and subprocess spawning.31514SOURCE-file inventory is unchanged;
  all5720tracked blobs/modes and the guard hash match after collection.
- Fully internal PostgreSQL relay: one native read-only identity/SELECT1
  succeeds with no published container port and no external network attachment.
  v4 exits docker-exec0/gracefully with empty stderr; total14.123s. The exact
  disposable tmpfs container is stopped and reverified; network retained.

## Causal findings and retained failures

Default tmux inheritance launched the universal Python binary in Intel mode,
but psycopg2's extension is ARM64. Guard v1 failed closed with exit78 before
any probe action. Diagnostic v2 preserved enforcement and recorded only the
exception class/frame coordinates; the independent relay import exposed the
architecture mismatch. Explicit `/usr/bin/arch -arm64` lets the same v2 guard
and unchanged probe pass in v3. Do not rebuild dependencies to mask this.

The first v3 launcher attempt stopped below5GiB before creating artifacts.
A later fresh capacity check passed the unchanged floor. Resource fluctuations
are not attributed to these tiny test files or to earlier cache cleanup.

Relay v1 failed before connection because of the architecture mismatch. v2
accepted one client but exceeded3s. In v3, the first upstream bytes arrive
3.108084s after client bytes; allowing15s lets the same protocol flow pass.
v3's exec255 did not establish clean closure. v4 adds a4s natural-exit grace
and requires exit0/graceful; it passes. Earlier artifacts remain immutable.
These are harness findings, not reproduced application defects.

## Evidence

- `native-guard-hflypi-20260921/manifest.json`:15raw/source/log entries,
  including failed v1/v2, capacity abort, exact guardv1/v2 and probev1 bytes.
- `native-collection-hflypi-v3.json`:712976bytes, full688526-byte stdout;
  SHA256`de5bdffd3c61191c9395032b9a927afe75a60d1713a995fcd8917e822a7753b4`.
- `native-internal-pg-relay-probe-hflypi-v1.json` throughv4 retain architecture,
  timing, exit modes and exact identity/teardown observations.
- Installed guard SHA256:
  `07d3e2dc19cbb0f9e542a6d0835ea17b5efcc5713391c152a833e6efefd61150`.

Independent read-only reviewer accepted actual guard v3, collection and relay
v4 scoped results; verified all15archive manifest hashes and the collection
copy hash. v3's earlier review accepted only wire feasibility, not clean exit.
The reviewer did not rerun tests or Docker operations. Raw evidence, not this
prose, owns the result. Final root read-only postcheck sees the probe exited0,
the existing Riderra/SEO PostgreSQL and Redis containers still running, and
the separate base audit PostgreSQL healthy. Mac free space:6173544KiB (~5.89GiB).

## Next boundary

Do not replay completed cache cleanup, builds, migrations, restore, frontend
prep, guard setup or collection. Prepare a reviewed Testcontainers adapter
with labelled owned resources and verified per-child relay capabilities; first
prove a migration subprocess plus a native transaction, then execute the full
suite. Multi-connection handling, Testcontainers lifecycle and full backend
results are still UNKNOWN. This standard-Python guard is for trusted frozen
tests, not an adversarial sandbox against arbitrary native code.
See `native-testcontainers-next-slice-hflypi-20260921.md`:19modules/94nodes
consume the shared PostgreSQL fixture; start with the one card-growth schema
test before expanding that family. The entire5481suite remains unexecuted.
