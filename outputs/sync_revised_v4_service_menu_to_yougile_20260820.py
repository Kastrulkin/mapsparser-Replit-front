#!/usr/bin/env python3
"""Mirror the verified revised-v4 sends to LocalOS CRM deal cards only."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


BASE_PATH = Path(__file__).with_name("sync_v4_email_sends_to_yougile_20260820.py")
SPEC = importlib.util.spec_from_file_location("sync_v4_email_sends", BASE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)

MODULE.REMOTE_LOG = "debug_data/localos-revised-send-20260820.log"
MODULE.REMOTE_SESSION = "localos-revised-send"
MODULE.STATE_PATH = MODULE.PROJECT_ROOT / "outputs/yougile-revised-v4-service-menu-sync-state-20260820.json"
MODULE.LOG_PATH = MODULE.PROJECT_ROOT / "outputs/yougile-revised-v4-service-menu-sync-20260820.jsonl"

SSL_WRAPPER = (
    "import ssl,certifi,runpy;"
    "ssl._create_default_https_context=lambda:ssl.create_default_context(cafile=certifi.where());"
    f"runpy.run_path({str(MODULE.YOUGILE)!r},run_name='__main__')"
)


def certified_yougile(method, path, payload=None):
    command = [sys.executable, "-c", SSL_WRAPPER, "request", method, path]
    if payload is not None:
        command.extend(["--apply", "--data", json.dumps(payload, ensure_ascii=False)])
    result = subprocess.run(
        command,
        cwd=MODULE.PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


MODULE.yougile = certified_yougile


if __name__ == "__main__":
    MODULE.main()
