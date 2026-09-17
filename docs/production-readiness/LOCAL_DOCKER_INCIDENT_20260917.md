# Local Docker audit interruption — 17 September 2026 UTC

This is a local Mac/Docker Desktop incident, not a production deployment or a demonstrated application regression. No production command, restart or database mutation was performed in this phase.

## Observed evidence

- At22:30UTC the host had9.2GiB free; after the browser image build, scan and next backend run, free space fell to1.3GiB. Docker's sparse VM disk occupied15GiB. Low host space and concurrent operations are observations, not a proven exhaustive root cause.
- Browser-enabled ARM64 image `localos-readiness-20260917-app:browser-ca8bdf0b` had already built successfully in296.953s; nonroot/network-none/read-only Chromium153.0.8010.12 smoke passed3.811s. Image ID `sha256:9a3c66082118fef9d7f21c2854ebb91d928a78c2bee104295f8be5d75fd8101d`. This image excludes later data fixes.
- The next3fadbabd build failed2.979s at containerd `meta.db` with `input/output error`, not a compiler/build-source error. Capture `raw/docker-data-3fadbabd-build.json`.
- Trivy downloaded its public database but image analysis failed53.039s with `unexpected EOF` while reading an image layer. `raw/browser-ca8-image-audit.json`. No successful image vulnerability/secret verdict exists. Because the script stopped, the subsequent new-commit Gitleaks scan did not run.
- Full3fadbabd suite: **3565passed,691skipped,4failed,79errors**,165.63s tests/166.905s captured. Docker testcontainer create/remove failed on containerd I/O; the four assertion-test failures were actual PostgreSQL connection failures reading `global/pg_filenode.map` with I/O error. This is not a green test run or proof of four new product defects. Capture `raw/backend-final-full-tests.json` is bounded/truncated, but retains these failures and summary.
- Docker VM console at22:38UTC reports EXT4 extent-conversion failures with possible data loss. Container status/health observations became inconsistent, and a later direct inspect returned local app `exited`, exit255. Do not treat stale `docker ps` rows as a healthy runtime or assume local volumes are intact.

## Safe actions taken

All audit Docker builds/scans/tests ended; no retry, global prune, Docker reset, volume removal, daemon restart or repair was attempted. Unrelated LocalOS/SEO and Riderra containers share this Docker Desktop instance and must be preserved.

The audit's sanitized scan invocation had created `/private/tmp/trivy/db/trivy.db` (1,405,173,760bytes) plus its150-byte metadata. Its public vulnerability DB was byte-compared equal to the pre-existing `/Users/alexdemyanov/Library/Caches/trivy/db/trivy.db`. Only the new duplicate file and metadata were removed; the original cache, reports, archives and all databases remain. Free space rose to2.6GiB. Cache content is regenerable and the identical original is retained.

User approval was requested for a **local Docker Desktop restart**, explicitly noting it interrupts local LocalOS and Riderra containers. No approval received at this checkpoint. Restart may not repair filesystem damage; do not promise automatic recovery. Do not rebuild heavy images with only2.6GiB headroom.

## Resume requirements

1. Obtain authority for the shared local Docker interruption/recovery; no factory reset or volume deletion is included.
2. Establish sufficient host headroom using verified disposable caches/artifacts only, or user-provided capacity. Reuse the existing Trivy cache explicitly to avoid a duplicate1.3GiB download. Run heavyweight builds/scans serially with disk preflight.
3. After approved recovery, inspect Docker/VM errors and each scoped test resource before writing. Check PostgreSQL readability and available test-backup recovery; do not touch user databases. Retain the successful synthetic dump/evidence outside Docker.
4. Rerun failed final build, image scan and complete backend suite from their recorded commits on a newly verified disposable database. Re-run causal regressions; prior successful checks do not prove a recovered Docker image/DB is intact.
5. The691 skips are fully classified by `-r s`:668missing `OPERATOR_VOICE_TEST_DSN`,13missing disposable PostgreSQL,1missing isolated migrated PostgreSQL,2missing disposable PostgreSQL DSN,6explicit live ChatGPT integration and1live Yandex smoke. Configure the safe synthetic DB groups after inspecting their guards; do not enable live providers merely to reduce skip counts.

The whole production-readiness goal remains active/incomplete. No production-ready sign-off, new push or deployment.
