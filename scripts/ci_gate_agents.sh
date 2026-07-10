#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_dir}"

scripts/test_agent_blueprints.sh
scripts/ci_gate_product_ui.sh
npm --prefix frontend run build
