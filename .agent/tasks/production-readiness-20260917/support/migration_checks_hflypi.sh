#!/usr/bin/env bash
set -euo pipefail
export PATH=/Applications/Docker.app/Contents/Resources/bin:/usr/local/bin:/usr/bin:/bin
audit_pg=localos-readiness-hflypi-postgres-1
audit_compose=/private/tmp/localos-readiness-20260921.hfLYPi/compose.audit.yaml
audit_identity=$(docker --context desktop-linux inspect "$audit_pg" --format '{{.State.Running}} {{index .Config.Labels "localos.audit.owner"}}')
test "$audit_identity" = 'true production-readiness-20260917-hfLYPi'
docker --context desktop-linux compose --env-file /dev/null -f "$audit_compose" -p localos-readiness-hflypi run --no-deps --name localos-readiness-hflypi-migrate-repeat migrate
docker --context desktop-linux compose --env-file /dev/null -f "$audit_compose" -p localos-readiness-hflypi run --no-deps --name localos-readiness-hflypi-check-source -e LOCALOS_MIGRATION_MODE=schema-check-only migrate
docker --context desktop-linux compose --env-file /dev/null -f "$audit_compose" -p localos-readiness-hflypi run --no-deps --name localos-readiness-hflypi-check-restored -e LOCALOS_MIGRATION_MODE=schema-check-only -e DATABASE_URL=postgresql://audit_owner:hflypi-local-only@postgres:5432/localos_readiness_restore_hflypi -e POSTGRES_DB=localos_readiness_restore_hflypi migrate
# CREATE DATABASE refuses any collision. Only this newly owned cluster is used.
docker --context desktop-linux exec "$audit_pg" psql -v ON_ERROR_STOP=1 -U audit_owner -d postgres -c 'CREATE DATABASE readiness_full_test_hflypi'
docker --context desktop-linux compose --env-file /dev/null -f "$audit_compose" -p localos-readiness-hflypi run --no-deps --name localos-readiness-hflypi-migrate-native -e DATABASE_URL=postgresql://audit_owner:hflypi-local-only@postgres:5432/readiness_full_test_hflypi -e POSTGRES_DB=readiness_full_test_hflypi migrate
docker --context desktop-linux exec "$audit_pg" psql -v ON_ERROR_STOP=1 -U audit_owner -d readiness_full_test_hflypi -Atqc 'SELECT version_num FROM alembic_version'
# This separate admission fixture requires the documented fixed hex name shape.
docker --context desktop-linux exec "$audit_pg" psql -v ON_ERROR_STOP=1 -U audit_owner -d postgres -c 'CREATE DATABASE readiness_full_test_a1b2c3d4_0f1e2d3c4b5a TEMPLATE readiness_full_test_hflypi'
