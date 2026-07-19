#!/usr/bin/env bash

set -euo pipefail
cd "$(dirname "$0")/.."

apply=0
if [[ "${1:-}" == "--apply" ]]; then
  apply=1
elif [[ $# -gt 0 ]]; then
  echo "Usage: $0 [--apply]" >&2
  exit 2
fi

compressed=0
skipped=0

while IFS= read -r -d '' source; do
  destination="${source}.gz"
  if [[ -e "${destination}" ]]; then
    echo "SKIP existing destination: ${destination}"
    skipped=$((skipped + 1))
    continue
  fi
  if [[ "${apply}" -ne 1 ]]; then
    echo "WOULD_COMPRESS ${source}"
    continue
  fi

  temporary="${destination}.tmp"
  rm -f "${temporary}"
  source_sha="$(sha256sum "${source}" | awk '{print $1}')"
  gzip -c "${source}" > "${temporary}"
  gzip -t "${temporary}"
  restored_sha="$(gzip -dc "${temporary}" | sha256sum | awk '{print $1}')"
  if [[ "${source_sha}" != "${restored_sha}" ]]; then
    rm -f "${temporary}"
    echo "ERROR checksum mismatch: ${source}" >&2
    exit 1
  fi
  mv "${temporary}" "${destination}"
  rm -f "${source}"
  compressed=$((compressed + 1))
  echo "COMPRESSED ${source} -> ${destination}"
done < <(find backups data/backups -type f -name '*.sql' -print0 2>/dev/null)

echo "compressed=${compressed} skipped=${skipped} apply=${apply}"
