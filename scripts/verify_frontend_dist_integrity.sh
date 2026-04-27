#!/usr/bin/env bash
set -euo pipefail

if [[ "$(pwd)" != "/opt/seo-app" && "$(pwd)" != *"SEO с Реплит на Курсоре" ]]; then
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

echo "OK: frontend/dist integrity check passed"
echo "JS: ${js_asset}"
echo "CSS: ${css_asset}"
