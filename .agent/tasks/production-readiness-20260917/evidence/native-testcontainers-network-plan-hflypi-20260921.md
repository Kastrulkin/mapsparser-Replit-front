# Native Testcontainers network plan — hfLYPi

Status: read-only design note. No Docker, database, network, installation,
guard import, child process, or test execution was performed for this note.

## Frozen inputs

- Frozen source: `/private/tmp/localos-readiness-20260921.hfLYPi/source`.
- Frozen revision/image identity: `99849935` / `localos-audit-20260921:99849935-hflypi`, captured in
  `evidence/isolated-hflypi-20260921/compose.audit.yaml:30`.
- The only shared Testcontainers starter is
  `/private/tmp/localos-readiness-20260921.hfLYPi/source/tests/conftest.py:53-66`:
  module-scoped `PostgresContainer("pgvector/pgvector:0.8.0-pg16-trixie")`.
  `run_migrations` consumes it at lines 69-78. Twenty frozen test files refer
  to `postgres_container` or `run_migrations`; no separate container fixture
  was found in that scan.
- Installed library behavior:
  `/private/tmp/localos-readiness-20260921.hfLYPi/native/venv/lib/python3.11/site-packages/testcontainers/community/postgres/__init__.py:48-71`
  gives this fixture one exposed port, `5432`, with default test credentials;
  `core/generic.py:79-84` connects from the host after startup;
  `core/container.py:263-278` forwards ports, network and `_kwargs` to Docker;
  `core/docker_client.py:283-310` accepts a `(host_ip, host_port)` port tuple;
  `core/labels.py:24-35` adds the actual Testcontainers session label.

## Existing hfLYPi topology

`compose.audit.yaml:15-21,94-103` puts the restored synthetic PostgreSQL on
both `localos-readiness-hflypi_internal` and the non-internal
`localos-readiness-hflypi_pg_ingress`, with `127.0.0.1:35418:5432`. Captured
restore evidence (`evidence/synthetic-restore-hflypi.json:19-20,33-44`)
confirms that `internal` is internal and `pg_ingress` is not.

Do not attach a Testcontainers PostgreSQL instance to the existing
`pg_ingress`: it would share a Docker network with the restored synthetic
database. Adding both existing networks would not supply egress containment,
because an attachment to non-internal `pg_ingress` retains egress.

## Smallest proposed profile

Create one fresh, aggregate-owned, labelled Testcontainers-only bridge. It
must have no base PostgreSQL, app, worker, or prior-run endpoint. Start only
the pinned pgvector image on that bridge, publish only
`127.0.0.1:<ephemeral>:5432`, and allow only `labels`, optional string
`platform`, and that exact network in container startup options. Continue to
deny mounts, volumes, devices, capabilities, privileged mode, host/PID/IPC
network modes and arbitrary images. Retain the host Python guard's provider,
tenant and loopback restrictions.

Before an aggregate, inspect and record the container and network identity:
exact owner/nonce and actual Testcontainers session labels, pinned image,
the single intended bridge endpoint, no other endpoints, and the loopback-only
published binding. Cleanup must target only that run's exact labels and the
dedicated network.

## Egress boundary and first proof

A dedicated non-internal bridge is enough for host-to-PostgreSQL connectivity,
but it does not prove container egress is absent. It is therefore not a full
egress-isolation claim, even with the pinned image and restrictive Docker
options.

The first bounded runtime proof should instead create one dedicated **internal**
Testcontainers-only bridge with the same loopback port mapping, start one
pinned PostgreSQL container, and verify host connectivity plus the inspect
criteria above. Current evidence does not establish that Docker Desktop permits
host reachability to a published port on an internal bridge. If that proof
fails, do not silently fall back to a non-internal network: require explicit
risk acceptance or a Docker-level egress firewall before using it.
