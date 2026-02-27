#!/usr/bin/env bash
set -euo pipefail

# Backward-compat wrapper. Canonical gate is ci_gate_openclaw_phase2.sh.
"$(cd "$(dirname "$0")" && pwd)/ci_gate_openclaw_phase2.sh" "$@"
