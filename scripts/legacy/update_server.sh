#!/usr/bin/env bash
set -euo pipefail

echo "DEPRECATED: legacy server updater"
echo "Старый путь через legacy web-root отключён."
echo "Используйте единый source of truth:"
echo "  cd /opt/seo-app && bash scripts/deploy_frontend_dist.sh --build"
echo ""

if [[ "$(pwd)" != "/opt/seo-app" ]]; then
  echo "Перехожу в /opt/seo-app"
  cd /opt/seo-app
fi

bash scripts/deploy_frontend_dist.sh --build
