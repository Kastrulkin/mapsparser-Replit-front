#!/usr/bin/env bash
set -euo pipefail

if [[ "$(pwd)" != "/opt/seo-app" && "$(pwd)" != *"SEO с Реплит на Курсоре" ]]; then
  echo "Run from project root (/opt/seo-app or local workspace root)"
  exit 1
fi

dist_dir="${1:-frontend/dist}"
index_file="${dist_dir}/index.html"

if [[ ! -f "${index_file}" ]]; then
  echo "Missing ${index_file}"
  exit 1
fi

extract_asset() {
  local pattern="$1"
  grep -oE "${pattern}" "${index_file}" | head -n 1 | cut -d'"' -f2 || true
}

js_asset="$(extract_asset 'src="/assets/index-[^"]+\.js"')"
css_asset="$(extract_asset 'href="/assets/index-[^"]+\.css"')"

if [[ -z "${js_asset}" ]]; then
  echo "Missing JS asset reference in ${index_file}"
  exit 1
fi
if [[ -z "${css_asset}" ]]; then
  echo "Missing CSS asset reference in ${index_file}"
  exit 1
fi

js_file="${dist_dir}${js_asset}"
css_file="${dist_dir}${css_asset}"

if [[ ! -f "${js_file}" ]]; then
  echo "Referenced JS asset not found: ${js_file}"
  exit 1
fi
if [[ ! -f "${css_file}" ]]; then
  echo "Referenced CSS asset not found: ${css_file}"
  exit 1
fi

echo "OK: frontend/dist integrity check passed"
echo "JS: ${js_asset}"
echo "CSS: ${css_asset}"
