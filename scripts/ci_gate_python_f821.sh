#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [ -z "${PYTHON_BIN:-}" ]; then
  if [ -x "venv/bin/python" ]; then
    PYTHON_BIN="venv/bin/python"
  elif [ -x ".venv/bin/python" ]; then
    PYTHON_BIN=".venv/bin/python"
  else
    PYTHON_BIN="python3"
  fi
fi

python_command=("${PYTHON_BIN}")
if [ "$(uname -s)" = "Darwin" ]; then
  python_command=(/usr/bin/arch -arm64 "${PYTHON_BIN}")
fi

# These directories are source fragments assembled into a shared runtime
# namespace, legacy route includes, or one-off migrations/scripts. They need a
# separate import-boundary refactor before standalone undefined-name linting is
# meaningful. Every ordinary importable runtime module is checked here.
"${python_command[@]}" -m ruff check src \
  --select F821 \
  --exclude 'src/api/prospecting/**' \
  --exclude 'src/api/admin_prospecting.py' \
  --exclude 'src/legacy_routes/**' \
  --exclude 'src/services/social_posts/**' \
  --exclude 'src/migrations/**' \
  --exclude 'src/scripts/**'
