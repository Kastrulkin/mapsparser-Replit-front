#!/bin/bash
set -euo pipefail
cd /opt/seo-app
proof=backups/voice-pilot-20260913
stage=.deploy/voice-deb0f637
exec > "$proof/deploy.log" 2>&1
trap 'printf "failed at line %s\n" "$LINENO" > backups/voice-pilot-20260913/deploy.failed' ERR
test "$(cat "$proof/restore-server.exit")" = 0
test "$(cat "$proof/migration-test.exit")" = 0
python3 - <<'PY'
import json,hashlib
from pathlib import Path
for name,expected in json.loads(Path('.deploy/voice-deb0f637/live-hashes.json').read_text()).items():
 p=Path(name);actual=hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
 if actual!=expected:raise SystemExit('server changed: '+name)
print('live hashes match')
PY
mkdir -p "$proof/rollback"
cp -p .env "$proof/rollback/env"
chmod 600 "$proof/rollback/env"
python3 - <<'PY'
from pathlib import Path
import json,shutil
root=Path('backups/voice-pilot-20260913/rollback')
for name in json.loads(Path('.deploy/voice-deb0f637/live-hashes.json').read_text()):
 p=Path(name)
 if p.exists():
  q=root/name;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
for name in ['frontend/dist','frontend/public-dist']:shutil.copytree(name,root/name,dirs_exist_ok=True)
PY
# Apply migrations from the staged tree before changing the running application.
docker cp "$stage/migrate.py" seo-app-app-1:/tmp/voice-migrate.py
docker cp "$stage/migration-test" seo-app-app-1:/tmp/voice-migrations
docker exec -e VOICE_MIGRATION_DIR=/tmp/voice-migrations seo-app-app-1 python /tmp/voice-migrate.py
docker compose stop -t 45 operator-worker worker telegram-bot app
python3 - <<'PY'
from pathlib import Path
import json,shutil
stage=Path('.deploy/voice-deb0f637')
for name in json.loads((stage/'live-hashes.json').read_text()):
 p=Path(name);p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(stage/name,p)
p=Path('.env');lines=p.read_text().splitlines();riderra='edbd961a-273f-4f15-836e-33aacc0aa0e3'
settings={'OPERATOR_REQUEST_AUDIT_BUSINESS_IDS':riderra,'OPERATOR_WORK_JOURNAL_BUSINESS_IDS':riderra}
for key,value in settings.items():
 indices=[i for i,line in enumerate(lines) if line.startswith(key+'=')]
 if indices:
  for i in indices:lines[i]=key+'='+value
 else:lines.append(key+'='+value)
p.write_text('\n'.join(lines)+'\n')
# Preserve older lazy-loaded assets for already-open browser tabs.
for name in ['frontend/dist','frontend/public-dist']:shutil.copytree(stage/name,name,dirs_exist_ok=True)
PY
docker compose config -q
docker compose up -d --no-deps --no-build app worker operator-worker telegram-bot
printf 'checking services\n'
docker compose ps
sleep 12
docker compose logs --since 2m app | tail -n 100
curl --retry 10 --retry-connrefused --retry-delay 3 -fsSI http://localhost:8000
python3 - <<'PY'
import json,hashlib
from pathlib import Path
stage=Path('.deploy/voice-deb0f637')
for name in json.loads((stage/'live-hashes.json').read_text()):
 if Path(name).read_bytes()!=(stage/name).read_bytes():raise SystemExit('file mismatch '+name)
print('deployed files match reviewed merge')
PY
docker exec seo-app-app-1 python scripts/localos_migrator.py check
printf '0\n' > "$proof/deploy.exit"
