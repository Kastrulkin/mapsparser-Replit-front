#!/bin/bash
set -euo pipefail
cd /opt/seo-app
proof=backups/voice-pilot-20260913
exec > "$proof/migration-test.log" 2>&1
test "$(cat "$proof/restore-server.exit")" = 0
test -f "$proof/restore-server-checks.txt"
docker network disconnect none voice-restore-20260913
docker network connect seo-app_default voice-restore-20260913
docker run --rm --memory=320m --memory-swap=320m --cpus=0.5 --network seo-app_default --entrypoint python -e DATABASE_URL=postgresql://postgres@voice-restore-20260913/voice_restore -e VOICE_MIGRATION_DIR=/release/migration-test -v /opt/seo-app/.deploy/voice-deb0f637:/release:ro seo-app-app:partner-results-20260911 /release/migrate.py
docker exec voice-restore-20260913 psql -U postgres -d voice_restore -Atc "SELECT version_num FROM alembic_version; SELECT count(*) FROM pg_index WHERE NOT indisvalid;" > "$proof/migration-test-checks.txt"
printf '0\n' > "$proof/migration-test.exit"
