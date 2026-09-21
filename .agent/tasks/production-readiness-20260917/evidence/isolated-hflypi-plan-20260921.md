# Authorized isolated audit lane — hfLYPi

The user explicitly approved creating new isolated test Docker containers and
volumes, migrations, and backup/restore of synthetic data on 21 September 2026.
This resolves the previous preparation/restore authority gate for this lane;
it does not authorize changes to production or pre-existing local databases,
containers, volumes, credentials, provider actions, push or deployment.

Frozen source: `99849935de26e2932613f2a73cf515dff49104a1`, extracted by Git archive
to `/private/tmp/localos-readiness-20260921.hfLYPi/source` (101 MB on disk).
The source has no `.env` or `local.env`, no Git directory, no dirty-worktree
overlay and no copied developer dependency installation. Thirteen foreign
workspace paths remain outside this lane. New helper files are audit support,
not modifications to the frozen application source.

## Owned resources and bounds

- Local Docker context `desktop-linux`, Unix socket; Docker 29.2.0 linux/arm64.
- New image tag `localos-audit-20260921:99849935-hflypi`, canonical Dockerfile
  with Chromium enabled. Fresh Git export; ordinary layer cache is allowed,
  and executed/cached steps are explicit in the BuildKit log.
- Compose project `localos-readiness-hflypi`, container
  `localos-readiness-hflypi-postgres-1`, new volume
  `localos-readiness-hflypi-pgdata`; owner label
  `localos.audit.owner=production-readiness-20260917-hfLYPi`.
- PG16 publishes only `127.0.0.1:35418`. Its exact networks are the dedicated
  internal network and a dedicated host-ingress bridge. Application migration
  containers use only the internal network, no host mounts or Docker socket.
- Source DB `readiness_hflypi`; native suite DB
  `readiness_full_test_hflypi`; fresh restore target
  `localos_readiness_restore_hflypi`. All data is synthetic.
- Docker image start floor 10 GiB; aggregate start floor 5 GiB; live floor
  2 GiB. Builds/tests/installations use named tmux sessions with bounded runs.
- Private evidence directory:
  `/private/tmp/localos-readiness-20260921.hfLYPi/evidence`.

## Narrow cache cleanup

The user's earlier authorization covered obsolete Docker cache cleanup.
Before the new image build, one old unused source-context cache record
`d8muz3gmec0d5p3vuuwokwbot` was removed (Docker reported 1.028 GB). The earlier
combined Boolean-filter attempt removed zero bytes and is not counted.
An obsolete COPY chain was then removed by exact IDs, leaf to parent:
`7l3iv4botutojl4obnuitl88d` (90.55 kB),
`urrk3vr9f2kzthrihclywxj6c` (12.32 kB),
`k9mwwewfg1r6en0kn0oubykbb` (11.32 MB),
`43if6bd86suu47emzcppy0jk4` (21.05 MB),
`07i9d0xu4h6m344x6pq1aze9q` (1.966 GB).
Total reported reclaimed build-cache content is approximately 3.03 GB.
These are regenerable build records, not source files, runtime images,
containers or database volumes. Host free-space change is not assumed equal
to Docker's reclaimed bytes because the VM and macOS accounting differ.

## Required proof (pending until captured)

1. Canonical image result, pip check, nonroot/browser/asset smoke.
2. Fresh Alembic migration plus repeated same-head upgrade and schema check.
3. Trusted synthetic plain-SQL backup, guarded restore into absent target,
   exact schema/data comparison, duplicate-row and sequence verification.
4. Fresh constrained native dependencies and guard probes, current collection,
   then full backend/native aggregate with explicit skip reasons.
5. Read-only ownership/resource postcheck; do not delete pre-existing resources.

The approved isolated lane does not itself close the original whole-project
acceptance criteria or resume the paused Codex goal controller. Preserve the
historical spec/verdict/problems; record current results additively.
