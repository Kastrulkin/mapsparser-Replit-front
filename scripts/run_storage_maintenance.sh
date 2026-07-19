#!/usr/bin/env bash

set -euo pipefail
cd "$(dirname "$0")/.."

bash scripts/compress_sql_backups.sh --apply
python3 scripts/prune_postgres_backups.py --apply
bash scripts/prune_debug_data.sh --apply
