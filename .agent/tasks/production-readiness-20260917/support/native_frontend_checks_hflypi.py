#!/usr/bin/env python3
"""Run bounded static frontend checks against the frozen hfLYPi source only."""

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
import argparse


BASE = Path("/private/tmp/localos-readiness-20260921.hfLYPi")
FRONTEND = BASE / "source" / "frontend"
NATIVE = BASE / "native"
EVIDENCE = NATIVE / "evidence"
NODE = Path("/usr/local/opt/node@22/bin/node")
NPM = Path("/usr/local/opt/node@22/bin/npm")
NPM_USERCONFIG = NATIVE / "npm-userconfig-v3.npmrc"
MIN_START_BYTES = 5 * 1024**3
MIN_LIVE_BYTES = 2 * 1024**3
ATTEMPT = "v3"
UNIT_ATTEMPT = "v6"
UNIT_GUARD = NATIVE / "unit_network_guard_v5.cjs"


def free_bytes() -> int:
    return shutil.disk_usage(BASE).free


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def environment() -> dict[str, str]:
    return {
        "NO_COLOR": "1",
        "NPM_CONFIG_AUDIT": "false",
        "NPM_CONFIG_CACHE": str(NATIVE / "npm-cache"),
        "NPM_CONFIG_FUND": "false",
        "NPM_CONFIG_UPDATE_NOTIFIER": "false",
        "NPM_CONFIG_USERCONFIG": str(NPM_USERCONFIG),
        "PATH": "/usr/local/opt/node@22/bin:/usr/local/bin:/usr/bin:/bin",
        "PYTHON_DOTENV_DISABLED": "1",
        "TMPDIR": str(NATIVE / "tmp"),
    }


def capture(label: str, command: list[str], env: dict[str, str]) -> None:
    destination = EVIDENCE / f"{label}.json"
    if destination.exists():
        raise RuntimeError(f"refusing to overwrite {destination}")
    started = time.monotonic()
    process = subprocess.Popen(command, cwd=FRONTEND, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
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
        "environment_keys": sorted(env),
    }
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True))
    if process.returncode or stopped_reason:
        raise RuntimeError(f"{label} failed with exit code {process.returncode}: {stopped_reason}")


def run_unit(targeted: bool, workers_two: bool) -> int:
    if free_bytes() < MIN_START_BYTES:
        raise RuntimeError("insufficient free disk for frontend unit checks")
    if not FRONTEND.is_dir() or not (FRONTEND / "node_modules").is_dir() or not NPM_USERCONFIG.is_file():
        raise RuntimeError("frozen frontend dependencies are absent")
    if not UNIT_GUARD.is_file():
        raise RuntimeError("approved private unit network guard is absent")
    guard_copy = EVIDENCE / f"unit_network_guard_{UNIT_ATTEMPT}.cjs"
    guard_metadata = EVIDENCE / f"native-frontend-unit-guard-source-{UNIT_ATTEMPT}.json"
    if guard_copy.exists() != guard_metadata.exists():
        raise RuntimeError("incomplete unit guard evidence")
    if not guard_copy.exists():
        shutil.copyfile(UNIT_GUARD, guard_copy)
        guard_metadata.write_text(json.dumps({
            "guard_path": str(UNIT_GUARD),
            "copied_guard_path": str(guard_copy),
            "guard_sha256": sha256(UNIT_GUARD),
            "scope": "Standard Node API no-network guard for trusted frozen unit tests; not an adversarial sandbox.",
        }, indent=2, sort_keys=True))
    elif sha256(guard_copy) != sha256(UNIT_GUARD):
        raise RuntimeError("unit guard evidence differs from active guard")
    env = environment()
    env["NODE_OPTIONS"] = "--require " + str(UNIT_GUARD)
    guard_check = (
        "const dgram=require('node:dgram'); const dns=require('node:dns'); const http=require('node:http'); "
        "const https=require('node:https'); const net=require('node:net'); const tls=require('node:tls'); "
        "const run=async()=>{const callbackResult=await new Promise((resolve,reject)=>dns.lookup('localhost',{all:true,family:4},(error,result)=>error?reject(error):resolve(result))); "
        "if(!Array.isArray(callbackResult)||callbackResult[0].address!=='127.0.0.1'||callbackResult[0].family!==4)throw new Error('localhost callback guard mismatch'); "
        "const local=await dns.promises.lookup('localhost',6); if(local.address!=='::1'||local.family!==6)throw new Error('localhost promise guard mismatch'); "
        "let fetchResult; try { fetchResult=fetch('https://example.invalid'); } catch (error) { throw new Error('fetch threw synchronously: '+error.message); } "
        "if(!fetchResult||typeof fetchResult.then!=='function')throw new Error('fetch did not return a Promise'); let fetchRejected=false; "
        "try { await fetchResult; } catch (error) { if(!String(error.message).includes('hfLYPi unit network guard denied'))throw error; fetchRejected=true; } "
        "if(!fetchRejected)throw new Error('fetch denial resolved unexpectedly'); "
        "const checks=[['net',()=>net.connect(1,'198.51.100.1')],['http',()=>http.request('http://198.51.100.1')], "
        "['https',()=>https.request('https://198.51.100.1')],['tls',()=>tls.connect(1,'198.51.100.1')], "
        "['dns',()=>new Promise((resolve,reject)=>dns.lookup('example.invalid',(error,result)=>error?reject(error):resolve(result)))],['dgram',()=>{const socket=dgram.createSocket('udp4'); try { socket.send('x',53,'198.51.100.1'); } finally { socket.close(); }}], "
        "['dns-promises',()=>dns.promises.resolve('example.invalid')]]; for (const [name,check] of checks) { try { await check(); } "
        "catch (error) { if (!String(error.message).includes('hfLYPi unit network guard denied')) throw error; continue; } "
        "throw new Error('guard did not deny '+name); } console.log('network-guard-active');}; run().catch(error=>{console.error(error);process.exit(1);});"
    )
    guard_capture = EVIDENCE / f"native-frontend-unit-guard-{UNIT_ATTEMPT}.json"
    if not guard_capture.exists():
        capture(f"native-frontend-unit-guard-{UNIT_ATTEMPT}", [str(NODE), "-e", guard_check], env)
    worker_arguments = ["--maxWorkers=2"] if workers_two else []
    if targeted:
        capture(
            f"native-frontend-unit-targeted-flaky-{UNIT_ATTEMPT}",
            [str(NPM), "test", "--", *worker_arguments, "src/components/SEOKeywordsTab.i18n.test.tsx", "src/pages/dashboard/ContentPage.i18n.test.tsx"],
            env,
        )
    else:
        capture(f"native-frontend-unit-{UNIT_ATTEMPT}", [str(NPM), "test", "--", *worker_arguments], env)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unit", action="store_true")
    parser.add_argument("--targeted-flaky", action="store_true")
    parser.add_argument("--unit-workers2", action="store_true")
    arguments = parser.parse_args()
    if arguments.unit and arguments.targeted_flaky:
        raise RuntimeError("select either full or targeted unit checks")
    if arguments.unit:
        return run_unit(False, arguments.unit_workers2)
    if arguments.targeted_flaky:
        return run_unit(True, True)
    if free_bytes() < MIN_START_BYTES:
        raise RuntimeError("insufficient free disk for static frontend checks")
    package = FRONTEND / "package.json"
    lock = FRONTEND / "package-lock.json"
    if not FRONTEND.is_dir() or not (FRONTEND / "node_modules").is_dir() or not NPM_USERCONFIG.is_file():
        raise RuntimeError("frozen frontend dependencies are absent")
    if not NODE.is_file() or not NPM.is_file():
        raise RuntimeError("Node 22 executable is absent")
    before = {"package_json_sha256": sha256(package), "package_lock_sha256": sha256(lock)}
    preflight = EVIDENCE / f"native-frontend-static-preflight-{ATTEMPT}.json"
    if preflight.exists():
        raise RuntimeError("static frontend check evidence already exists")
    preflight.write_text(json.dumps({
        "initial_free_bytes": free_bytes(),
        "minimum_start_bytes": MIN_START_BYTES,
        "minimum_live_bytes": MIN_LIVE_BYTES,
        **before,
        "scope": "Frozen source frontend static checks only; unit tests intentionally excluded pending an explicit no-network harness review.",
    }, indent=2, sort_keys=True))
    env = environment()
    capture(f"native-frontend-node-version-{ATTEMPT}", [str(NODE), "--version"], env)
    capture(f"native-frontend-types-{ATTEMPT}", [str(NPM), "run", "typecheck"], env)
    capture(f"native-frontend-lint-{ATTEMPT}", [str(NPM), "run", "lint"], env)
    after = {"package_json_sha256": sha256(package), "package_lock_sha256": sha256(lock)}
    payload = {
        "package_manifests_unchanged": before == after,
        "final_free_bytes": free_bytes(),
        "minimum_live_bytes": MIN_LIVE_BYTES,
        "unit_test_status": "not run: no-network preload requires root review",
    }
    (EVIDENCE / f"native-frontend-static-final-{ATTEMPT}.json").write_text(json.dumps(payload, indent=2, sort_keys=True))
    if before != after:
        raise RuntimeError("static checks changed frozen frontend manifests")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        if EVIDENCE.is_dir():
            failure_attempt = UNIT_ATTEMPT if "--unit" in sys.argv or "--targeted-flaky" in sys.argv else ATTEMPT
            failure = EVIDENCE / ("native-frontend-failure-" + failure_attempt + "-" + str(time.time_ns()) + ".json")
            failure.write_text(json.dumps({"error": str(sys.exception())}, indent=2, sort_keys=True))
        raise
