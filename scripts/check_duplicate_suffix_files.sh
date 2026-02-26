#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

pattern=' \([0-9]+\)(\.[^/]+)?$'
failed=0

echo "[dup-check] scanning tracked files..."
tracked="$(git ls-files | grep -E "${pattern}" || true)"
if [[ -n "${tracked}" ]]; then
  echo "[dup-check] ERROR: duplicate-suffix files are tracked in git:"
  echo "${tracked}"
  failed=1
fi

echo "[dup-check] scanning untracked workspace files..."
untracked="$(git ls-files --others --exclude-standard | grep -E "${pattern}" || true)"
if [[ -n "${untracked}" ]]; then
  echo "[dup-check] ERROR: duplicate-suffix files exist in workspace:"
  echo "${untracked}"
  failed=1
fi

if [[ "${failed}" -ne 0 ]]; then
  cat <<'EOF'
[dup-check] Fix guidance:
  1) Rename canonical file:
     git mv "Dockerfile (2)" Dockerfile
  2) Remove duplicate files from git:
     git rm "Dockerfile (3)" ...
  3) Keep cleanup backups out of git.
EOF
  exit 1
fi

echo "[dup-check] OK"

