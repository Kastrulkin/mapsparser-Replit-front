#!/bin/bash
set -euo pipefail
cd /opt/seo-app
exec > backups/voice-pilot-20260913/audit-lock-hotfix.log 2>&1
cp -p src/core/agent_api_security.py backups/voice-pilot-20260913/rollback/agent_api_security.py
cp .deploy/voice-deb0f637/agent_api_security.py src/core/agent_api_security.py
docker compose restart app operator-worker worker telegram-bot
sleep 10
docker compose ps
curl --retry 10 --retry-connrefused --retry-delay 2 -fsSI http://localhost:8000
