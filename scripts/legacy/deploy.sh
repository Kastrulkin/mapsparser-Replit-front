#!/usr/bin/env bash
set -euo pipefail

echo "DEPRECATED: scripts/legacy/deploy.sh"
echo "Этот non-Docker deploy больше не поддерживается."
echo "Текущий runtime проекта: Docker Compose + PostgreSQL."
echo ""
echo "Используйте вместо него:"
echo "  cd /opt/seo-app"
echo "  docker compose up -d --force-recreate app"
echo "  bash scripts/deploy_frontend_dist.sh --build"
exit 1
