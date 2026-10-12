#!/usr/bin/env bash
# Run from the repository on the deployment host after approving this release.
set -euo pipefail

if [[ ! -f docker-compose.yml ]]; then
  echo 'Run from the project directory with docker-compose.yml.' >&2
  exit 1
fi
knowledge_uid="$(docker compose exec -T app id -u | tr -d '\r')"
knowledge_gid="$(docker compose exec -T app id -g | tr -d '\r')"
if [[ ! "${knowledge_uid}" =~ ^[0-9]+$ || ! "${knowledge_gid}" =~ ^[0-9]+$ ]]; then
  echo 'Could not determine the application user.' >&2
  exit 1
fi
mkdir -p data/business_knowledge
chown "${knowledge_uid}:${knowledge_gid}" data/business_knowledge
chmod 700 data/business_knowledge
echo 'Private document directory prepared. Containers still need the reviewed volume configuration.'
