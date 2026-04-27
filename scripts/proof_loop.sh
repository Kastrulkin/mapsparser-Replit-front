#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL_PATH="${ROOT_DIR}/agents/skills/repo-task-proof-loop"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [[ ! -f "${SKILL_PATH}/scripts/task_loop.py" ]]; then
  echo "Skill not found: ${SKILL_PATH}/scripts/task_loop.py" >&2
  exit 1
fi

usage() {
  cat <<'EOF'
Usage:
  scripts/proof_loop.sh init <TASK_ID> "<TASK_TEXT>"
  scripts/proof_loop.sh init-file <TASK_ID> <TASK_FILE_PATH>
  scripts/proof_loop.sh validate <TASK_ID>
  scripts/proof_loop.sh status <TASK_ID>

Notes:
  - Safe defaults: --guides none --install-subagents codex
  - Artifacts will be created under .agent/tasks/<TASK_ID>/
EOF
}

cmd="${1:-}"
if [[ -z "${cmd}" ]]; then
  usage
  exit 1
fi
shift

case "${cmd}" in
  init)
    task_id="${1:-}"
    task_text="${2:-}"
    if [[ -z "${task_id}" || -z "${task_text}" ]]; then
      usage
      exit 1
    fi
    "${PYTHON_BIN}" "${SKILL_PATH}/scripts/task_loop.py" init \
      --task-id "${task_id}" \
      --task-text "${task_text}" \
      --guides none \
      --install-subagents codex
    ;;
  init-file)
    task_id="${1:-}"
    task_file="${2:-}"
    if [[ -z "${task_id}" || -z "${task_file}" ]]; then
      usage
      exit 1
    fi
    "${PYTHON_BIN}" "${SKILL_PATH}/scripts/task_loop.py" init \
      --task-id "${task_id}" \
      --task-file "${task_file}" \
      --guides none \
      --install-subagents codex
    ;;
  validate)
    task_id="${1:-}"
    if [[ -z "${task_id}" ]]; then
      usage
      exit 1
    fi
    "${PYTHON_BIN}" "${SKILL_PATH}/scripts/task_loop.py" validate --task-id "${task_id}"
    ;;
  status)
    task_id="${1:-}"
    if [[ -z "${task_id}" ]]; then
      usage
      exit 1
    fi
    "${PYTHON_BIN}" "${SKILL_PATH}/scripts/task_loop.py" status --task-id "${task_id}"
    ;;
  *)
    usage
    exit 1
    ;;
esac
