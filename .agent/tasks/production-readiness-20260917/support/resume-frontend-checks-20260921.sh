#!/bin/bash
set -eu
task_root=$(git rev-parse --show-toplevel)
cd "$task_root/frontend"
export PATH="/usr/local/opt/node@22/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
capture=/Users/alexdemyanov/.codex/skills/bug-reproducer/scripts/capture_command.py
evidence="$task_root/.agent/tasks/production-readiness-20260917/evidence"
build_root="$task_root/outputs/audit-resume-20260921"
capture_failures=0
run_check() {
  local label=$1
  shift
  if [ -e "$evidence/$label.json" ]; then
    echo "Refusing to overwrite completed evidence: $label" >&2
    exit 2
  fi
  /usr/local/bin/python3 "$capture" --label "$label" --cwd "$PWD" --timeout 1200 --max-output 500000 --output "$evidence/$label.json" -- "$@"
  if ! /usr/local/bin/python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if d["exit_code"] == 0 and not d["timed_out"] else 1)' "$evidence/$label.json"; then
    capture_failures=1
  fi
}
if [ "${1:-}" = "final" ]; then
  run_check resume-frontend-final-lint-20260921 npm run lint
  run_check resume-frontend-final-types-20260921 npm run typecheck
  run_check resume-frontend-final-unit-20260921 npm test
  exit "$capture_failures"
fi
run_check resume-frontend-lint-20260921 npm run lint
run_check resume-frontend-types-20260921 npm run typecheck
run_check resume-frontend-unit-20260921 npm test
run_check resume-frontend-build-20260921 npm run build -- --outDir "$build_root/dist"
run_check resume-frontend-public-build-20260921 npm run build:public -- --outDir "$build_root/public-dist"
exit "$capture_failures"
