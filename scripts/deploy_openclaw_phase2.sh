#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f docker-compose.yml ]]; then
  echo "ERROR: docker-compose.yml not found. Run from /opt/seo-app." >&2
  exit 1
fi

if [[ "${PWD}" != "/opt/seo-app" ]]; then
  echo "ERROR: run this script from /opt/seo-app." >&2
  exit 1
fi

TENANT_ID="${TENANT_ID:-${OPENCLAW_DEFAULT_TENANT_ID:-}}"
OPENCLAW_TOKEN="${OPENCLAW_TOKEN:-${OPENCLAW_LOCALOS_TOKEN:-}}"
SKIP_BUILD="${SKIP_BUILD:-0}"

if [[ -z "${TENANT_ID}" ]]; then
  echo "ERROR: TENANT_ID is required (or set OPENCLAW_DEFAULT_TENANT_ID in env)." >&2
  exit 1
fi

if [[ -z "${OPENCLAW_TOKEN}" ]]; then
  echo "ERROR: OPENCLAW_TOKEN is required (or set OPENCLAW_LOCALOS_TOKEN in env)." >&2
  exit 1
fi

echo "[deploy] root=$ROOT_DIR"
echo "[deploy] tenant=$TENANT_ID"

if [[ "$SKIP_BUILD" != "1" ]]; then
  echo "[deploy] build app"
  ./scripts/docker-compose-build.sh build app
  echo "[deploy] build worker"
  ./scripts/docker-compose-build.sh build worker
else
  echo "[deploy] SKIP_BUILD=1, build skipped"
fi

echo "[deploy] restart app worker"
docker compose up -d app worker

echo "[verify] docker compose ps"
docker compose ps

echo "[verify] app logs"
docker compose logs --since 5m app | tail -n 200

echo "[verify] health check"
curl -fsSI http://localhost:8000 | head -n 1

echo "[verify] openclaw ops smoke/recovery"
OPENCLAW_TOKEN="$OPENCLAW_TOKEN" TENANT_ID="$TENANT_ID" ./scripts/openclaw_ops_smoke_recover.sh

echo "[verify] openclaw reconciliation smoke"
OPENCLAW_TOKEN="$OPENCLAW_TOKEN" TENANT_ID="$TENANT_ID" ./scripts/smoke_openclaw_m2m_reconciliation.sh

echo "[deploy] OK"
