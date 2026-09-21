#!/usr/bin/env python3
"""Prepare only frozen frontend dependencies and a private Playwright shell."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time


BASE = Path("/private/tmp/localos-readiness-20260921.hfLYPi")
SOURCE_FRONTEND = BASE / "source" / "frontend"
NATIVE = BASE / "native"
VENV = NATIVE / "venv"
EVIDENCE = NATIVE / "evidence"
NODE = Path("/usr/local/opt/node@22/bin/node")
NPM = Path("/usr/local/opt/node@22/bin/npm")
ARCH = Path("/usr/bin/arch")
MIN_START_BYTES = 6 * 1024**3
MIN_LIVE_BYTES = 2 * 1024**3
MIN_FINAL_BYTES = 5 * 1024**3
ATTEMPT = "v3"
NPM_USERCONFIG = NATIVE / "npm-userconfig-v3.npmrc"


def free_bytes() -> int:
    return shutil.disk_usage(BASE).free


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture(label: str, command: list[str], environment: dict[str, str], cwd: Path) -> None:
    destination = EVIDENCE / f"{label}.json"
    if destination.exists():
        raise RuntimeError("refusing to overwrite " + str(destination))
    if free_bytes() < MIN_LIVE_BYTES:
        raise RuntimeError("insufficient free disk before " + label)
    started = time.monotonic()
    process = subprocess.Popen(command, cwd=cwd, env=environment, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    stopped_reason = None
    while True:
        try:
            stdout, stderr = process.communicate(timeout=5)
            break
        except subprocess.TimeoutExpired:
            if free_bytes() < MIN_LIVE_BYTES or time.monotonic() - started > 900:
                stopped_reason = "disk_floor_or_timeout"
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    stdout, stderr = process.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    stdout, stderr = process.communicate(timeout=10)
                break
    payload = {
        "label": label,
        "command": command,
        "exit_code": process.returncode,
        "stopped_reason": stopped_reason,
        "duration_ms": round((time.monotonic() - started) * 1000, 3),
        "stdout": stdout[-60000:],
        "stderr": stderr[-60000:],
        "stdout_truncated": len(stdout) > 60000,
        "stderr_truncated": len(stderr) > 60000,
        "free_bytes_after": free_bytes(),
        "environment_keys": sorted(environment),
    }
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True))
    if process.returncode or stopped_reason:
        raise RuntimeError(f"{label} failed with exit code {process.returncode}: {stopped_reason}")


def node_environment() -> dict[str, str]:
    return {
        "NO_COLOR": "1",
        "NPM_CONFIG_AUDIT": "false",
        "NPM_CONFIG_CACHE": str(NATIVE / "npm-cache"),
        "NPM_CONFIG_FUND": "false",
        "NPM_CONFIG_UPDATE_NOTIFIER": "false",
        "NPM_CONFIG_USERCONFIG": str(NPM_USERCONFIG),
        "TMPDIR": str(NATIVE / "tmp"),
        "PATH": "/usr/local/opt/node@22/bin:/usr/local/bin:/usr/bin:/bin",
        "PYTHON_DOTENV_DISABLED": "1",
    }


def python_environment() -> dict[str, str]:
    return {
        "NO_COLOR": "1",
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "PIP_CONFIG_FILE": os.devnull,
        "PLAYWRIGHT_BROWSERS_PATH": str(NATIVE / "ms-playwright"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "PYTHON_DOTENV_DISABLED": "1",
        "XDG_CACHE_HOME": str(NATIVE / "playwright-cache"),
        "TMPDIR": str(NATIVE / "tmp"),
    }


def main() -> int:
    if free_bytes() < MIN_START_BYTES:
        raise RuntimeError("insufficient free disk for frontend/browser preparation start")
    if not SOURCE_FRONTEND.is_dir() or not VENV.is_dir() or not EVIDENCE.is_dir():
        raise RuntimeError("frozen frontend or native dependency environment is absent")
    if not NODE.is_file() or not NPM.is_file() or not ARCH.is_file():
        raise RuntimeError("Node 22 or native launcher is absent")
    package = SOURCE_FRONTEND / "package.json"
    lock = SOURCE_FRONTEND / "package-lock.json"
    node_modules = SOURCE_FRONTEND / "node_modules"
    if node_modules.exists():
        raise RuntimeError("frozen frontend already has node_modules; refusing shared state")
    if NPM_USERCONFIG.exists():
        raise RuntimeError("private npm user configuration already exists; refusing overwrite")
    NPM_USERCONFIG.write_text("")
    before = {"package_json_sha256": sha256(package), "package_lock_sha256": sha256(lock)}
    (EVIDENCE / f"frontend-browser-preflight-{ATTEMPT}.json").write_text(json.dumps({
        "initial_free_bytes": free_bytes(),
        "minimum_start_bytes": MIN_START_BYTES,
        "minimum_live_bytes": MIN_LIVE_BYTES,
        "minimum_final_bytes": MIN_FINAL_BYTES,
        **before,
        "scope": "Frozen source/frontend node_modules and private native caches/browser only; no application run or project test.",
    }, indent=2, sort_keys=True))
    node_env = node_environment()
    capture(f"frontend-node-version-{ATTEMPT}", [str(NODE), "--version"], node_env, SOURCE_FRONTEND)
    capture(f"frontend-npm-ci-{ATTEMPT}", [str(NPM), "ci", "--legacy-peer-deps", "--no-audit", "--no-fund"], node_env, SOURCE_FRONTEND)
    after = {"package_json_sha256": sha256(package), "package_lock_sha256": sha256(lock)}
    if before != after:
        raise RuntimeError("npm changed frozen frontend manifests")
    python = [str(ARCH), "-arm64", str(VENV / "bin/python")]
    python_env = python_environment()
    capture(f"playwright-browser-shell-{ATTEMPT}", python + ["-m", "playwright", "install", "chromium", "--only-shell"], python_env, NATIVE)
    launch_source = (
        "from playwright.sync_api import sync_playwright; "
        "runtime=sync_playwright().start(); "
        "browser=runtime.chromium.launch(headless=True); "
        "page=browser.new_page(); page.goto('data:text/html,ready'); "
        "assert page.title() == ''; browser.close(); runtime.stop(); print('headless-shell-ok')"
    )
    capture(f"playwright-headless-shell-{ATTEMPT}", python + ["-c", launch_source], python_env, NATIVE)
    final_payload = {
        "package_manifests_unchanged": before == after,
        "final_free_bytes": free_bytes(),
        "minimum_final_bytes": MIN_FINAL_BYTES,
        "node_modules_path": str(node_modules),
        "npm_cache_path": str(NATIVE / "npm-cache"),
        "browser_path": str(NATIVE / "ms-playwright"),
    }
    (EVIDENCE / f"frontend-browser-final-{ATTEMPT}.json").write_text(json.dumps(final_payload, indent=2, sort_keys=True))
    if free_bytes() < MIN_FINAL_BYTES:
        raise RuntimeError("frontend/browser preparation ended below aggregate disk floor")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        if EVIDENCE.is_dir():
            failure = EVIDENCE / ("frontend-browser-failure-" + ATTEMPT + "-" + str(time.time_ns()) + ".json")
            failure.write_text(json.dumps({"error": str(sys.exception())}, indent=2, sort_keys=True))
        raise
