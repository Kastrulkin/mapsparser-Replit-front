#!/bin/bash
PYTHONPATH=src venv/bin/python -m pytest -q tests/test_operator_platform_outreach.py tests/test_operator_platform_context.py tests/test_operator_platform_entrypoints.py tests/test_outreach_continuation.py tests/test_operator_async_jobs.py tests/test_telegram_control_scope.py > .agent/tasks/localos-miniapp-outreach-20261112/raw/baseline-backend.log 2>&1
result=$?
printf "%s" "$result" > .agent/tasks/localos-miniapp-outreach-20261112/raw/baseline-backend.exit
