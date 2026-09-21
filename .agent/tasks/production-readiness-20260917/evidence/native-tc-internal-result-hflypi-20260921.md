# Dedicated internal PostgreSQL probe — bounded failure

The independently reviewed support/native_tc_internal_probe_hflypi.py ran in
named tmux `audit-tc-internal-hflypi-20260921`. Exact local Docker context/socket,
immutable ARM64 image, resource names, ownership labels and the internal bridge
were verified. No image pull/build or existing database/resource modification.

Result: **FAIL, 4.056s**, before readiness or native SELECT. The new container's
requested host binding was `127.0.0.1` with an ephemeral port, but actual
`NetworkSettings.Ports["5432/tcp"]` was `[]`. A separate postcheck confirmed the
container was running, attached only to the internal bridge, with no Docker
mounts/volumes or privileged mode and only the intended PGDATA tmpfs. This is
observed Docker Desktop topology behavior, not a LocalOS product test failure.
No non-internal fallback or attempted connection to another database occurred.

Raw evidence: `native-tc-internal-probe-hflypi.json` and
`native-tc-internal-postcheck-hflypi.json`. Exact newly created resources:

- container `localos-readiness-hflypi-tc-postgres-1`,
  ID `423858f43fb80952016d98749da9dab11841403b8a76450ce7d6f46f3b2ca318`;
- network `localos-readiness-hflypi-tc-internal`,
  ID `6fc9dbcb68ce40e46030cec829ed4613840327eda4109cd09de4ada422a4a0b4`.

After rechecking exact labels/name/image, root stopped only that new container;
Docker returned exit0. Its disposable tmpfs PostgreSQL data is consequently
discarded; the stopped container and network remain for inspection. Do not
replay the creation script against retained names. Existing hfLYPi base DB and
the pre-existing LocalOS/Riderra PostgreSQL/Redis containers were not stopped.

Next: choose and independently review an owned host-connectivity profile that
preserves the required egress boundary, or explicitly accept a narrower PG-only
non-internal-network risk. Current evidence does not authorize that fallback.
Native guard installation/child probes and fresh backend collection remain
unexecuted. This failed proof does not invalidate the separately completed
image, synthetic migration/restore or clean frontend results.
