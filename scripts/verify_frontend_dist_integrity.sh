#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "${repo_root}" || "$(pwd -P)" != "$(cd "${repo_root}" && pwd -P)" ]]; then
  echo "Run from project root (/opt/seo-app or local workspace root)"
  exit 1
fi

dist_dir="${1:-frontend/dist}"
index_file="${2:-${dist_dir}/index.html}"

if [[ ! -f "${index_file}" && -f "${dist_dir}/public-audit/index.html" ]]; then
  index_file="${dist_dir}/public-audit/index.html"
fi

if [[ ! -f "${index_file}" ]]; then
  echo "Missing ${index_file}"
  exit 1
fi

js_asset="$(grep -oE 'src="/[^"]*index-[^"]+\.js"' "${index_file}" | head -n 1 | cut -d'"' -f2 || true)"
css_asset="$(grep -oE 'href="/[^"]*index-[^"]+\.css"' "${index_file}" | head -n 1 | cut -d'"' -f2 || true)"

if [[ -z "${js_asset}" ]]; then
  echo "Missing JS asset reference in ${index_file}"
  exit 1
fi
if [[ -z "${css_asset}" ]]; then
  echo "Missing CSS asset reference in ${index_file}"
  exit 1
fi

resolve_asset_file() {
  local asset_path="$1"
  local normalized_path="${asset_path#/}"
  local candidate="${dist_dir}/${normalized_path}"
  if [[ -f "${candidate}" ]]; then
    echo "${candidate}"
    return 0
  fi

  local trimmed_after_prefix="${normalized_path#*/}"
  candidate="${dist_dir}/${trimmed_after_prefix}"
  if [[ -f "${candidate}" ]]; then
    echo "${candidate}"
    return 0
  fi

  echo "${dist_dir}/${normalized_path}"
}

js_file="$(resolve_asset_file "${js_asset}")"
css_file="$(resolve_asset_file "${css_asset}")"

if [[ ! -f "${js_file}" ]]; then
  echo "Referenced JS asset not found: ${js_file}"
  exit 1
fi
if [[ ! -f "${css_file}" ]]; then
  echo "Referenced CSS asset not found: ${css_file}"
  exit 1
fi

missing_assets=0
while IFS= read -r asset_path; do
  [[ -z "${asset_path}" ]] && continue
  asset_file="$(resolve_asset_file "${asset_path}")"
  if [[ ! -f "${asset_file}" ]]; then
    echo "Referenced asset not found: ${asset_file}"
    missing_assets=1
  fi
done < <(grep -oE '(src|href)="/[^"]+\.(js|css|png|jpg|jpeg|gif|ico|svg|webp)"' "${index_file}" | cut -d'"' -f2 | sort -u)

if [[ "${missing_assets}" -ne 0 ]]; then
  exit 1
fi

python3 - "${dist_dir}" "${js_file}" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path


dist_dir = Path(sys.argv[1]).resolve()
entry_file = Path(sys.argv[2]).resolve()
asset_reference_pattern = re.compile(
    r'''["']((?:\.{1,2}/|/|assets/)[^"'?#]+\.(?:js|css|png|jpe?g|gif|ico|svg|webp|woff2?|ttf))["']'''
)
pending = [entry_file]
visited: set[Path] = set()
missing: set[Path] = set()


def resolve_reference(source_file: Path, reference: str) -> Path:
    if reference.startswith("/"):
        return (dist_dir / reference.removeprefix("/")).resolve()
    if reference.startswith("assets/"):
        return (dist_dir / reference).resolve()
    return (source_file.parent / reference).resolve()


while pending:
    source_file = pending.pop()
    if source_file in visited:
        continue
    visited.add(source_file)
    if not source_file.is_file():
        missing.add(source_file)
        continue

    try:
        source_text = source_file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue

    for reference in asset_reference_pattern.findall(source_text):
        referenced_file = resolve_reference(source_file, reference)
        try:
            referenced_file.relative_to(dist_dir)
        except ValueError:
            missing.add(referenced_file)
            continue
        if not referenced_file.is_file():
            missing.add(referenced_file)
            continue
        if referenced_file.suffix == ".js":
            pending.append(referenced_file)

if missing:
    for missing_file in sorted(missing):
        print(f"Referenced dynamic asset not found: {missing_file}", file=sys.stderr)
    raise SystemExit(1)

print(f"Reachable dynamic assets checked: {len(visited)} JS files")
PY

echo "OK: frontend/dist integrity check passed"
echo "JS: ${js_asset}"
echo "CSS: ${css_asset}"
