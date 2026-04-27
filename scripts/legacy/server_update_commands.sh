#!/usr/bin/env bash
set -euo pipefail

echo "DEPRECATED: scripts/legacy/server_update_commands.sh"
echo "Этот сценарий больше не использует legacy web-root и старый non-Docker project root."
echo "Канонический путь для frontend dist: /opt/seo-app/frontend/dist"
echo "Канонический deploy-командой: cd /opt/seo-app && bash scripts/deploy_frontend_dist.sh --build"
echo ""

if [[ "$(pwd)" != "/opt/seo-app" ]]; then
  echo "Перехожу в /opt/seo-app"
  cd /opt/seo-app
fi

bash scripts/deploy_frontend_dist.sh --build
