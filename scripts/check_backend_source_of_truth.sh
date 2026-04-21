#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

git_safe=(git -c safe.directory="${repo_root}")

untracked_runtime_files="$(
  "${git_safe[@]}" ls-files --others --exclude-standard -- \
    'src/**/*.py' \
    'src/**/*.json' \
    'src/**/*.html' \
    'alembic_migrations/versions/*.py'
)"

if [[ -z "${untracked_runtime_files}" ]]; then
  echo "OK: backend runtime source-of-truth is clean"
  exit 0
fi

echo "WARNING: untracked backend runtime files detected"
printf '%s\n' "${untracked_runtime_files}"
exit 1
