# Approved old Docker-resource cleanup — 21 September

User explicitly approved disposal of completed Sep17–18 synthetic test
containers/images, keeping every volume, current hfLYPi and LocalOS/Riderra.
No global prune, volume deletion, application source or production operation.

## Verified execution

The literal six-container/six-image allowlist was refreshed against local
desktop-linux and its exact Unix socket. Targets were stopped, task-labelled,
had no volume mounts, and had only the two reviewed read-only ingress binds.
Each identity/status/mount/reference was checked again before removal.
`container rm` used neither force nor `-v`; `image rm --no-prune` used exact IDs.

Post-inventory exactly matches the approved delta:29→23containers,10→4images;
all20volumes and23networks retained. Remaining container states, image IDs and
mounts match the recorded pre-inventory. Independent pre-execution/runtime
review PASS. Old synthetic container writable layers cannot be restored by
undo; their images/cache can be rebuilt. Historical audit evidence is retained.

After image removal, exactly21old Sep17 BuildKit records were unshared and
reclaimable. v1 returned successful prune commands but removed only3leaves;
its exact-inventory acceptance correctly FAILED. Preserve that raw result.
Remaining parent references required child-first order, not broader cleanup.
The corrected wrapper embeds the literal18remaining IDs and the helper plans
the complete graph before any deletion. It rejects external retained children,
cycles, missing/duplicate IDs; each target must still be unshared/reclaimable.

v2 removes exactly18, adds zero IDs, leaves all image/container/volume IDs
unchanged. v1+v2 removed set equals the original21IDs. Six graph controls
(one positive, five negative) plus the actual18record graph pass; scoped Ruff
and diff checks pass. Independent pre-execution review caught an unnecessarily
dynamic allowlist in the draft wrapper; fixed to literal18before execution.
Independent runtime/live inspection also PASS:24BuildKit records remain,
original21all absent; only40.96kB across four recent Sep20/21records is
reclaimable, deliberately retained. Live23containers/4images/20volumes/
23networks match the reviewed retained baseline.

Host free samples, not guaranteed attributable reclaimed bytes:

- Container/image operation:12,141,121,536→13,486,268,416bytes (+1.25GiB).
- Cache v2:17,138,380,800→18,580,643,840bytes (+1.34GiB).
- Subsequent df sample:18,561,604KiB free (~17.70GiB).

Concurrent host free-space changes are not attributed to cleanup. Rounded
Docker sizes for the21cache records total about1.87GB, not a host delta.
Current free capacity exceeds10GiB full-build floor, but recheck before builds.

## OPS-CACHE-DEPENDENCIES-01 — P2, audit executor, locally FIX_PROVEN

Root cause: successful per-ID prune exit does not mean a referenced parent
cache record was removed. Effect: incomplete cleanup and misleading capacity
claims if callers trust exit alone; exact post-inventory rejected this run.
Observed18retained parents out of21targets; high confidence, local-only scope,
small effort/blast radius, no application defect or production frequency claim.
Fix: full child-first plan plus literal resume allowlist, fresh gates and exact
set-delta acceptance. Risk: dependency metadata may change concurrently; fail
closed on missing/retained-child graph or changed reclaimability, and require
postcheck. Acceptance: original21absent, no extra removals/additions, resources
unchanged. Controls and actual v2 establish this bounded result. Required before
claiming approved cleanup complete; no readiness score or release claim follows.

Raw captures/helper hashes are in `old-audit-docker-manifest-20260921.json`.
Do not rerun one-shot cleanup or reuse the historical29container invariant:
the current retained baseline is23containers/4images/20volumes/23networks.
Current test stand, frozen/native lane and13foreign dirty paths remain retained.
