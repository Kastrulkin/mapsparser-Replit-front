#!/usr/bin/env bash

set -euo pipefail
cd "$(dirname "$0")/.."

retention_days="${DEBUG_RETENTION_DAYS:-30}"
apply=0
if [[ "${1:-}" == "--apply" ]]; then
  apply=1
elif [[ $# -gt 0 ]]; then
  echo "Usage: $0 [--apply]" >&2
  exit 2
fi

deleted=0
reclaimed_bytes=0
while IFS= read -r -d '' directory; do
  directory_bytes="$(du -sb "${directory}" | awk '{print $1}')"
  reclaimed_bytes=$((reclaimed_bytes + directory_bytes))
  if [[ "${apply}" -eq 1 ]]; then
    rm -rf -- "${directory}"
    echo "DELETED ${directory}"
    deleted=$((deleted + 1))
  else
    echo "WOULD_DELETE ${directory}"
  fi
done < <(
  find debug_data -mindepth 1 -maxdepth 1 -type d -mtime "+${retention_days}" \
    ! -name media_uploads \
    ! -name sales_room_uploads \
    ! -exec test -e '{}/.keep' \; \
    -print0 2>/dev/null
)

echo "deleted=${deleted} reclaimed_bytes=${reclaimed_bytes} retention_days=${retention_days} apply=${apply}"
