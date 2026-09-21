# Next native integration slice

Read-only fixture map, frozen99849935 and fresh5481-node collection. These
counts describe dependencies, not passing tests or executed fixtures.

- `tests/conftest.py:53` defines module-scoped `postgres_container`; line65
  creates `PostgresContainer("pgvector/pgvector:0.8.0-pg16-trixie")`.
- `tests/conftest.py:31` and69 contain the Flask migration child and its fixture.
-19test modules /94collected nodes consume PostgreSQL Testcontainers;12modules
  also use `run_migrations`. `test_capabilities_api_phase1.py` contributes57.
- Installed `testcontainers.postgres` is a compatibility import of the
  community PostgresContainer. It exposes5432 and constructs DSNs using
  `get_container_host_ip()` plus `get_exposed_port()`.

Smallest next real test:
`tests/test_card_growth_migration_pg.py::test_card_growth_schema_is_available_after_migrations`.
It requires one owned container lifecycle, one Flask/Alembic subprocess and
a native psycopg transaction/schema assertion. Do not alter this test to match
the harness or claim its current success; it has not run in this lane.

The installed guard still deliberately rejects Testcontainers starts. Its
original internal-network/published-port model cannot work here (observed
empty host binding). Standalone relay v4 proves only one read-only connection
and clean teardown, not this integration path.

Before enabling the named test, implement and independently review only the
necessary adapter: internal-only PG, fixed approved image, exact owner/nonce/
library-session labels, no existing mounts, owned host relay with multiple
connections, parent+Flask-child capability validation, per-admission fresh
image/label/network identity, and exact owned-resource cleanup. Substitute
only Testcontainers-reported host/port. Prove denial of foreign endpoints and
stale/mismatched capabilities before migration/transaction acceptance.

Do not enable the broader94-node family or full5481suite from the standalone
relay proof alone. Preserve the remaining5387tests as unexecuted, not skipped
or implicitly green. Production/existing databases/providers remain excluded.
