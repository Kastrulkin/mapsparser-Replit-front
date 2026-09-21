# Isolated Docker, migration and restore result — 21 September 2026

## Verdict and scope

PASS for the newly authorized **local ARM64 image / fresh synthetic schema /
backup-and-restore / canonical Gunicorn startup and graceful shutdown** lane.
This is not whole-project acceptance, a production deployment, or an AMD64 test.
Current full native/backend/browser aggregate remains incomplete.

Frozen Git source: `99849935de26e2932613f2a73cf515dff49104a1`. Independent
read-only review compared 5,720 archive entries with that revision and found
zero missing, extra or mismatching entries before native harness preparation.
No dirty-worktree overlay, developer `.env`, or shared dependency installation
was copied. Thirteen foreign workspace paths remain outside this package.

Detailed raw captures are in `isolated-hflypi-20260921/`; its `manifest.json`
records the archived files and SHA-256 hashes. The failed preparation attempts
are retained alongside successful proof, not silently replaced.

## Verified results

| Check | Observed result |
| --- | --- |
| Canonical Dockerfile, Chromium enabled | exit 0, 405.959 seconds; linux/arm64 |
| Runtime dependencies | `pip check` exit 0 |
| Nonroot runtime/browser/assets | UID 10001; writable runtime directories; actual Chromium static DOM; both asset entrypoints; private-dist integrity pass |
| Fresh PostgreSQL 16 migration | head `20260907_001`, 288 public application tables |
| Repeated upgrade and source/restored schema-check | all exit 0 |
| Trusted synthetic restore | 289 tables including dedicated probe; complete logical data/schema/sequence comparison passes |
| Gunicorn runtime | `/health`, `/ready`, `/`, `/about` all HTTP 200 inside owned container |
| Gunicorn SIGTERM | exit 0, no OOM, stopped in 2.661 seconds; worker/master shutdown logged |
| Fresh native Python dependencies | 133 installed distributions; all 101 release constraints match; `pip check` exit 0 |

Image identity:
`sha256:9d6edac8b6948e239c0bab54564f92f829e5b9dfc93f3ca0626060ffb4e60853`.
Tag `localos-audit-20260921:99849935-hflypi` is retained. Build used ordinary
layer cache and `--pull`; it is not claimed to be `--no-cache` or reproducible
across different architectures. The log identifies cached/executed steps.

## Recovery evidence

Owned cluster: `localos-readiness-hflypi-postgres-1`, volume
`localos-readiness-hflypi-pgdata`, loopback `127.0.0.1:35418` only. Source
`readiness_hflypi` and restored `localos_readiness_restore_hflypi` contain only
synthetic migrations/fixtures. The application/migration containers have only
the dedicated internal network and no host/Docker-socket mounts. PostgreSQL
also has a dedicated ingress bridge to support local native clients; that
bridge is not an egress-denial sandbox.

Restore verification covers 289 tables, 1,173 indexes, 1,047 constraints,
160 functions, 11 triggers, 3 views, 3 sequences and 3 extensions. Full rows
are compared as sorted `row_to_json` multisets with `UNION ALL`, preserving
duplicates, nulls and scalar types. Sequence last values and `is_called`
match. The probe retains two identical payload rows and sequence `2|true`.
Independent review inspected and accepted the captured comparison, comparator
code and results. Root ran the two comparator tests with seven negative subtests
(missing/extra duplicate, null/type, sequence value/state and object inventory
changes); this is not an independent rerun claim.

An initial restore comparison failed because plain `pg_dump` TABLE DATA
sections were ordered differently after restore. Read-only diagnosis found
434 changed diff lines caused by section ordering. The completed restore
was verified in place using logical multisets; it was not overwritten or
rerun to conceal the first result. An earlier wrapper attempt failed before
Docker execution because its PATH omitted Docker.

The trusted 75,875-byte SQL gzip backup is retained outside Git at
`/private/tmp/localos-readiness-20260921.hfLYPi/synthetic-restore-hflypi-source.sql.gz`.
SHA-256: `1eeee953d28d5769bc40458a6a6efbb103dd27830e06258b46b59d7f8570daf1`.
This is a synthetic rehearsal, not validation of a real production backup,
RPO/RTO, external storage, or every production database role/grant.

## Findings and unsuccessful preparation

1. Running the image's bare `python src/main.py` command served all four HTTP
   routes but required SIGKILL after the 10-second SIGTERM deadline (exit 137,
   OOM false). Production Compose overrides it with Gunicorn; that exact command
   passed graceful shutdown. No production shutdown defect is inferred from the
   development-command observation; the default-image behavior remains recorded.
2. Direct Mac access to a port published on the internal-only app network was
   refused. Internal HTTP passed. This is not evidence about the unrelated
   production TLS timeout or a successful host/browser ingress journey.
3. Native frontend preparation first stopped below its 6-GiB start floor. A
   later attempt failed before npm installation because both npm config paths
   were `/dev/null`. The v3 support script was revised to avoid that conflict,
   preserve old evidence and avoid overriding HOME. v3 installation has not
   run. No fresh native Chromium or frontend node_modules is ready in this lane.
4. Native egress/DSN guard and propagation probes are separate audit-harness
   preparation, not production changes. Independent static review rejected
   execution: some suite subprocesses use stripped environments and cannot
   reliably initialize/propagate this guard. Minimal DSN, loopback-binding and
   child-probe corrections are drafted, but a reviewed launcher propagation
   policy is still required. Both support files are explicitly DRAFT/UNEXECUTED;
   neither was installed in the frozen archive. No probes, fresh collection or
   native project tests ran. Old aggregate counts are not current proof.

## Resource boundary and retained state

Archived prune logs directly account for approximately 4.66 GB of unused
BuildKit records; preparation notes report a further 1.028 GB exact context
record, whose successful raw output is not archived (the retained earlier
context-prune attempt removed zero). Total reported cleanup is approximately
5.69 GB under the user's earlier cache-cleanup authorization, with that evidence
qualification. These are regenerable cache, not
runtime images, source, containers or database volumes. Docker's reported
reclaimed amount is not equated with macOS free space. The final postcheck
reading was 4,921,581,568 bytes (~4.58 GiB), below the 6-GiB native frontend prep floor
and 5-GiB full aggregate start floor. Heavy operations were not started below
their floors. Existing local containers and volumes were not deleted by this lane.

Both owned web test containers are stopped and retained with logs. The new
synthetic PostgreSQL is healthy and retained for further authorized tests,
including fresh native base DB `readiness_full_test_hflypi` and the dedicated
hex-named viewer fixture. This lane used only owned local resources; no command
targets the existing Riderra/SEO DBs or production. No push, deployment,
production migration/restart, credential rotation or provider action was made
by this work. Original historical spec/verdict/problems and the
paused goal controller remain unchanged.

`isolated-hflypi-postcheck-20260921.json` records the final
read-only resource check: all 42 archived capture hashes match, all 11 owned
containers have the expected owner, only PostgreSQL is running and healthy,
its port/volume/internal-network identities match, the backup hash matches,
the draft guard is not installed, and both comparator tests pass again.

Remaining whole-project gates include current full integration/browser tests,
security/credential-owner closure, paired performance, real-API demo/recovery,
hosted CI, platform parity where needed, and final evidence reconciliation.

## Packaging review

Independent final wording review accepted the corrected scope/attribution.
All 42 archived capture hashes were also verified against the Git index;
62 staged paths are limited to this audit's evidence/support and four readiness
documents. Support Python AST and shell syntax checks pass. Raw `.log` files
retain original carriage returns/trailing whitespace so their hashes remain
byte-exact; whitespace checks pass for code/docs/JSON. The initial 426,745-byte
staged diff passed Gitleaks default rules with allow-comments/ignore files
disabled and output redacted. Draft native guard files are explicitly unrun.
