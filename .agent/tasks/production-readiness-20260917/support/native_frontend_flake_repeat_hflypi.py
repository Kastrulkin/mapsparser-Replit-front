#!/usr/bin/env python3
"""Repeat two frozen frontend tests under the default Vitest worker configuration."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import sys
import time


BASE = Path("/private/tmp/localos-readiness-20260921.hfLYPi")
SOURCE = BASE / "source"
FRONTEND = SOURCE / "frontend"
NATIVE = BASE / "native"
NODE = Path("/usr/local/opt/node@22/bin/node")
NPM = Path("/usr/local/opt/node@22/bin/npm")
GUARD = NATIVE / "unit_network_guard_v5.cjs"
ARCHIVED_GUARD = Path(
    "/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/"
    "Всякое/SEO с Реплит на Курсоре/.agent/tasks/production-readiness-20260917/"
    "evidence/native-frontend-checks-hflypi-20260921/unit_network_guard_v6.cjs"
)
ARCHIVED_VITEST = Path(
    "/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/"
    "Всякое/SEO с Реплит на Курсоре/.agent/tasks/production-readiness-20260917/"
    "evidence/native-frontend-checks-hflypi-20260921/frozen-source-identity-postunit-v6.json"
)
EVIDENCE = Path(
    "/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/"
    "Всякое/SEO с Реплит на Курсоре/.agent/tasks/production-readiness-20260917/"
    "evidence/frontend-flake-repeat-hflypi-20260921"
)
COMMIT = "99849935de26e2932613f2a73cf515dff49104a1"
REPOSITORY = Path(
    "/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/"
    "Всякое/SEO с Реплит на Курсоре"
)
MIN_START_BYTES = 5 * 1024**3
MIN_LIVE_BYTES = 2 * 1024**3
TIMEOUT_SECONDS = 120
REPEATS = 5
TRACKED_BLOBS = 5720
TARGETS = [
    "src/components/SEOKeywordsTab.i18n.test.tsx",
    "src/pages/dashboard/ContentPage.i18n.test.tsx",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def free_bytes() -> int:
    return shutil.disk_usage(BASE).free


def write_json_exclusive(path: Path, payload: object) -> None:
    encoded = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False).encode()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        output = os.fdopen(descriptor, "wb")
        try:
            output.write(encoded)
            output.write(b"\n")
        finally:
            output.close()
    except BaseException:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def clean_environment() -> dict[str, str]:
    return {
        "NODE_OPTIONS": "--require " + str(GUARD),
        "NO_COLOR": "1",
        "NPM_CONFIG_AUDIT": "false",
        "NPM_CONFIG_CACHE": str(NATIVE / "npm-cache"),
        "NPM_CONFIG_FUND": "false",
        "NPM_CONFIG_UPDATE_NOTIFIER": "false",
        "NPM_CONFIG_USERCONFIG": str(NATIVE / "npm-userconfig-v3.npmrc"),
        "PATH": "/usr/local/opt/node@22/bin:/usr/local/bin:/usr/bin:/bin",
        "PYTHON_DOTENV_DISABLED": "1",
        "TMPDIR": str(NATIVE / "tmp"),
    }


def git_blob_sha1(payload: bytes) -> str:
    return hashlib.sha1(f"blob {len(payload)}\0".encode() + payload).hexdigest()


def verify_source_identity() -> dict[str, object]:
    revision = subprocess.run(
        ["git", "-C", str(REPOSITORY), "rev-parse", COMMIT],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if revision.stdout.strip() != COMMIT:
        raise RuntimeError("frozen source commit did not resolve")
    listing = subprocess.run(
        ["git", "-C", str(REPOSITORY), "ls-tree", "-rz", "-r", COMMIT],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    mismatches: list[dict[str, str]] = []
    checked = 0
    symlinks = 0
    for record in listing.stdout.split(b"\0"):
        if not record:
            continue
        header, raw_path = record.split(b"\t", 1)
        mode_raw, object_type_raw, expected_raw = header.split(b" ", 2)
        mode = mode_raw.decode()
        if object_type_raw != b"blob":
            mismatches.append({"path": os.fsdecode(raw_path), "reason": "non-blob tree entry"})
            continue
        path = SOURCE / os.fsdecode(raw_path)
        if mode == "120000":
            symlinks += 1
            if not path.is_symlink():
                mismatches.append({"path": str(path.relative_to(SOURCE)), "reason": "expected symlink"})
                checked += 1
                continue
            payload = os.fsencode(os.readlink(path))
            observed_mode = "120000"
        else:
            if not path.is_file() or path.is_symlink():
                mismatches.append({"path": str(path.relative_to(SOURCE)), "reason": "expected regular file"})
                checked += 1
                continue
            payload = path.read_bytes()
            observed_mode = format(stat.S_IMODE(path.lstat().st_mode), "06o")
        expected_mode = "000755" if mode == "100755" else "000644" if mode == "100644" else mode.zfill(6)
        observed_blob = git_blob_sha1(payload)
        if observed_blob != expected_raw.decode() or observed_mode != expected_mode:
            mismatches.append({
                "path": str(path.relative_to(SOURCE)),
                "expected_blob_sha1": expected_raw.decode(),
                "observed_blob_sha1": observed_blob,
                "expected_mode": expected_mode,
                "observed_mode": observed_mode,
            })
        checked += 1
    return {
        "commit": COMMIT,
        "checked_tracked_blobs": checked,
        "tracked_symlink_blobs": symlinks,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
    }


def exact_test_success(result: dict[str, object]) -> bool:
    stdout = result.get("stdout")
    return (
        result.get("exit_code") == 0
        and result.get("stopped_reason") is None
        and isinstance(stdout, str)
        and "Test Files  2 passed (2)" in stdout
        and "Tests  3 passed (3)" in stdout
    )


def classification(
    results: list[dict[str, object]],
    config_hashes_unchanged: bool,
    identity: dict[str, object],
) -> str:
    if (
        len(results) == REPEATS
        and all(exact_test_success(result) for result in results)
        and config_hashes_unchanged
        and identity.get("checked_tracked_blobs") == TRACKED_BLOBS
        and identity.get("mismatch_count") == 0
    ):
        return "NOT_REPRODUCED"
    return "INCONCLUSIVE"


def terminate_owned_process(process: subprocess.Popen[str]) -> tuple[str, str, str]:
    if process.poll() is not None:
        stdout, stderr = process.communicate(timeout=1)
        return "already_exited", stdout, stderr
    os.killpg(process.pid, signal.SIGTERM)
    try:
        stdout, stderr = process.communicate(timeout=10)
        return "term", stdout, stderr
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate(timeout=10)
        return "kill", stdout, stderr


def run_repeat(number: int, environment: dict[str, str]) -> dict[str, object]:
    started = time.monotonic()
    command = [str(NPM), "test", "--", *TARGETS]
    process = subprocess.Popen(
        command,
        cwd=FRONTEND,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    stopped_reason = None
    cleanup_mode = "normal"
    stdout = ""
    stderr = ""
    try:
        while True:
            try:
                stdout, stderr = process.communicate(timeout=2)
                break
            except subprocess.TimeoutExpired:
                if free_bytes() >= MIN_LIVE_BYTES and time.monotonic() - started < TIMEOUT_SECONDS:
                    continue
                stopped_reason = "disk_floor" if free_bytes() < MIN_LIVE_BYTES else "timeout"
                cleanup_mode, stdout, stderr = terminate_owned_process(process)
                break
    finally:
        if process.poll() is None:
            cleanup_mode, stdout, stderr = terminate_owned_process(process)
    return {
        "repeat": number,
        "command": command,
        "exit_code": process.returncode,
        "stopped_reason": stopped_reason,
        "cleanup_mode": cleanup_mode,
        "duration_ms": round((time.monotonic() - started) * 1000, 3),
        "stdout": stdout,
        "stderr": stderr,
        "free_bytes_after": free_bytes(),
        "environment_keys": sorted(environment),
    }


def main() -> int:
    if EVIDENCE.exists():
        raise RuntimeError("refusing to overwrite flake repeat evidence directory")
    if free_bytes() < MIN_START_BYTES:
        raise RuntimeError("insufficient free disk before repeat start")
    if not (FRONTEND / "node_modules").is_dir() or not NODE.is_file() or not NPM.is_file():
        raise RuntimeError("frozen frontend dependencies are unavailable")
    if not GUARD.is_file() or not ARCHIVED_GUARD.is_file():
        raise RuntimeError("active or archived network guard is unavailable")
    if sha256(GUARD) != sha256(ARCHIVED_GUARD):
        raise RuntimeError("active network guard bytes differ from archived v6 guard")
    archived_identity = json.loads(ARCHIVED_VITEST.read_text())
    if archived_identity.get("commit") != COMMIT or archived_identity.get("mismatch_count") != 0:
        raise RuntimeError("archived v6 identity evidence is not the expected clean frozen source")
    EVIDENCE.mkdir(mode=0o700)
    environment = clean_environment()
    package_hashes = {
        "package_json_sha256": sha256(FRONTEND / "package.json"),
        "package_lock_sha256": sha256(FRONTEND / "package-lock.json"),
        "vitest_config_sha256": sha256(FRONTEND / "vitest.config.ts"),
    }
    pre_identity = verify_source_identity()
    write_json_exclusive(EVIDENCE / "pre-source-identity.json", pre_identity)
    if pre_identity["mismatch_count"] != 0:
        raise RuntimeError("frozen source identity differs before repeat run")
    write_json_exclusive(EVIDENCE / "preflight.json", {
        "initial_free_bytes": free_bytes(),
        "minimum_start_bytes": MIN_START_BYTES,
        "minimum_live_bytes": MIN_LIVE_BYTES,
        "timeout_seconds_per_repeat": TIMEOUT_SECONDS,
        "repeat_limit": REPEATS,
        "default_worker_configuration": True,
        "guard_path": str(GUARD),
        "guard_sha256": sha256(GUARD),
        "archived_guard_path": str(ARCHIVED_GUARD),
        "archived_guard_sha256": sha256(ARCHIVED_GUARD),
        "targets": TARGETS,
        "environment_keys": sorted(environment),
        "pre_identity_checked_tracked_blobs": pre_identity["checked_tracked_blobs"],
        "pre_identity_mismatch_count": pre_identity["mismatch_count"],
        **package_hashes,
    })
    results: list[dict[str, object]] = []
    run_error = None
    after_hashes = package_hashes
    identity: dict[str, object] = {}
    try:
        for number in range(1, REPEATS + 1):
            if free_bytes() < MIN_LIVE_BYTES:
                results.append({"repeat": number, "not_started_reason": "disk_floor"})
                break
            result = run_repeat(number, environment)
            write_json_exclusive(EVIDENCE / f"repeat-{number}.json", result)
            results.append(result)
            if result["stopped_reason"]:
                break
    except BaseException:
        run_error = str(sys.exception())
    finally:
        after_hashes = {
            "package_json_sha256": sha256(FRONTEND / "package.json"),
            "package_lock_sha256": sha256(FRONTEND / "package-lock.json"),
            "vitest_config_sha256": sha256(FRONTEND / "vitest.config.ts"),
        }
        identity = verify_source_identity()
        write_json_exclusive(EVIDENCE / "post-source-identity.json", identity)
        config_hashes_unchanged = package_hashes == after_hashes
        status = classification(results, config_hashes_unchanged, identity)
        write_json_exclusive(EVIDENCE / "summary.json", {
            "results": [{
                "repeat": result.get("repeat"),
                "exit_code": result.get("exit_code"),
                "stopped_reason": result.get("stopped_reason"),
                "duration_ms": result.get("duration_ms"),
                "exact_test_success": exact_test_success(result),
            } for result in results],
            "attempted_repeats": len(results),
            "tests_expected_per_repeat": 3,
            "classification": status,
            "config_hashes_unchanged": config_hashes_unchanged,
            "pre_hashes": package_hashes,
            "post_hashes": after_hashes,
            "post_identity_checked_tracked_blobs": identity.get("checked_tracked_blobs"),
            "post_identity_mismatch_count": identity.get("mismatch_count"),
            "run_error": run_error,
            "final_free_bytes": free_bytes(),
        })
    if run_error:
        raise RuntimeError(run_error)
    return 0 if classification(results, package_hashes == after_hashes, identity) == "NOT_REPRODUCED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
