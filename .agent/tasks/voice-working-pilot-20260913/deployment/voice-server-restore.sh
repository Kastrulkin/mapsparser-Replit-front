#!/bin/bash
set -euo pipefail
cd /opt/seo-app
proof=backups/voice-pilot-20260913
exec > "$proof/restore-server.log" 2>&1
printf 'validating retained backups\n'
docker exec -i seo-app-postgres-1 pg_restore --list < "$proof/database.dump" > /dev/null
docker exec -i seo-app-postgres-1 pg_restore --list < backups/voice-20260911/database.dump > /dev/null
nice -n 15 gzip -t data/backups/postgres/local_20260912_104901.sql.gz
python3 - <<'PY'
from pathlib import Path
paths=['releases/20260905-today-134536/backup/database.dump','releases/20260906-plan-a4deb61e-181955/backup/database.dump','.release-backups/localos-creator-incident-20260908T134559Z/postgres-before.sql.gz','data/backups/postgres/local_20260909_125052.sql.gz']
for name in paths:
 p=Path(name)
 if p.is_file() and not p.is_symlink():
  print('retired backup',name,p.stat().st_size,flush=True)
  p.unlink()
PY
df -h /
docker run -d --name voice-restore-20260913 --memory=512m --memory-swap=512m --cpus=0.6 --network=none -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_DB=voice_restore -v voice_restore_20260913:/var/lib/postgresql/data pgvector/pgvector:0.8.0-pg16-trixie postgres -c shared_buffers=64MB -c maintenance_work_mem=64MB -c work_mem=4MB -c max_connections=10 -c max_wal_senders=0 -c wal_level=minimal -c max_wal_size=128MB -c min_wal_size=32MB -c fsync=off -c synchronous_commit=off -c full_page_writes=off
for n in $(seq 1 60); do docker exec voice-restore-20260913 pg_isready -U postgres && break; sleep 1; done
( docker exec -i voice-restore-20260913 pg_restore -U postgres -d voice_restore --no-owner --no-acl --exit-on-error --single-transaction < "$proof/database.dump"; printf '%s\n' "$?" > "$proof/restore-server.exit" ) &
restore_pid=$!
while kill -0 "$restore_pid" 2>/dev/null; do
 available=$(df -Pm / | awk 'NR==2 {print $4}')
 if [ "$available" -lt 1200 ]; then
  docker stop -t 3 voice-restore-20260913
  printf 'reserve reached\n' > "$proof/restore-server.blocked"
  wait "$restore_pid" || true
  exit 2
 fi
 sleep 5
done
wait "$restore_pid"
docker exec voice-restore-20260913 psql -U postgres -d voice_restore -Atc "SELECT pg_size_pretty(pg_database_size(current_database())); SELECT count(*) FROM pg_index WHERE NOT indisvalid; SELECT version_num FROM alembic_version;" > "$proof/restore-server-checks.txt"
printf 'restore complete\n'
