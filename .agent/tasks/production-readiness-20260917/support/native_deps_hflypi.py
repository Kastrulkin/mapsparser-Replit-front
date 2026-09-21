#!/usr/bin/env python3
"""Create a clean, bounded native dependency environment for hfLYPi.

This helper deliberately prepares dependencies only.  It never imports LocalOS,
opens Docker, starts a database, loads dotenv, or runs application tests.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import argparse
import zipfile
import re


NONCE = "hfLYPi"
BASE = Path("/private/tmp/localos-readiness-20260921.hfLYPi")
SOURCE = BASE / "source"
NATIVE = BASE / "native"
VENV = NATIVE / "venv"
MANIFEST = NATIVE / "manifest"
WHEELS = NATIVE / "reviewed-wheels"
EVIDENCE = NATIVE / "evidence"
TMP = NATIVE / "tmp"
PYTHON = Path("/usr/local/bin/python3")
ARCH = Path("/usr/bin/arch")
MIN_START_BYTES = 5 * 1024**3
MIN_LIVE_BYTES = 2 * 1024**3
SDISTS = {
    "googlemaps": {
        "filename": "googlemaps-4.10.0.tar.gz",
        "url": "https://files.pythonhosted.org/packages/source/g/googlemaps/googlemaps-4.10.0.tar.gz",
        "sha256": "3055fcbb1aa262a9159b589b5e6af762b10e80634ae11c59495bd44867e47d88",
        "requires_dist": ["requests<3.0,>=2.20.0"],
    },
    "pyaes": {
        "filename": "pyaes-1.6.1.tar.gz",
        "url": "https://files.pythonhosted.org/packages/source/p/pyaes/pyaes-1.6.1.tar.gz",
        "sha256": "02c1b1405c38d3c370b085fb952dd8bea3fadcee6411ad99f312cc129c536d8f",
        "requires_dist": [],
    },
}


def free_bytes() -> int:
    return shutil.disk_usage(BASE).free


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean_environment() -> dict[str, str]:
    return {
        "NETRC": os.devnull,
        "NO_COLOR": "1",
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "PIP_CONFIG_FILE": os.devnull,
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "PYTHON_DOTENV_DISABLED": "1",
        "TMPDIR": str(TMP),
        "XDG_CACHE_HOME": str(NATIVE / "cache"),
    }


def capture(label: str, command: list[str], environment: dict[str, str]) -> None:
    started = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=NATIVE,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=900,
        check=False,
    )
    payload = {
        "label": label,
        "command": command,
        "exit_code": completed.returncode,
        "duration_ms": round((time.monotonic() - started) * 1000, 3),
        "stdout": completed.stdout[-60000:],
        "stderr": completed.stderr[-60000:],
        "stdout_truncated": len(completed.stdout) > 60000,
        "stderr_truncated": len(completed.stderr) > 60000,
        "free_bytes_after": free_bytes(),
        "environment_keys": sorted(environment),
    }
    (EVIDENCE / f"{label}.json").write_text(json.dumps(payload, indent=2, sort_keys=True))
    if completed.returncode:
        raise RuntimeError(f"{label} failed with exit code {completed.returncode}")


def download_sdist(package: str, environment: dict[str, str]) -> Path:
    item = SDISTS[package]
    destination = TMP / item["filename"]
    capture(
        f"download-{package}",
        [
            "/usr/bin/curl", "--fail", "--location", "--proto", "=https",
            "--tlsv1.2", "--connect-timeout", "15", "--max-time", "120",
            "--silent", "--show-error", "--output", str(destination), item["url"],
        ],
        environment,
    )
    observed = sha256(destination)
    if observed != item["sha256"]:
        raise RuntimeError(f"{package} sdist hash mismatch: {observed}")
    (EVIDENCE / f"download-{package}.json").write_text(json.dumps({
        "package": package,
        "url": item["url"],
        "filename": item["filename"],
        "sha256": observed,
    }, indent=2, sort_keys=True))
    return destination


def wheel_metadata(package: str, wheel: Path) -> dict[str, object]:
    archive = zipfile.ZipFile(wheel)
    try:
        metadata_names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise RuntimeError(f"expected one metadata member in {wheel.name}")
        lines = archive.read(metadata_names[0]).decode("utf-8").splitlines()
    finally:
        archive.close()
    requires_dist = [line.removeprefix("Requires-Dist: ") for line in lines if line.startswith("Requires-Dist: ")]
    if requires_dist != SDISTS[package]["requires_dist"]:
        raise RuntimeError(f"{package} wheel metadata dependencies differ: {requires_dist}")
    return {"wheel": wheel.name, "wheel_sha256": sha256(wheel), "requires_dist": requires_dist}


def normalized_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def verify_existing() -> int:
    if not VENV.is_dir() or not (EVIDENCE / "resolved-distributions.json").is_file():
        raise RuntimeError("completed native preparation is required for verification")
    for filename in ("requirements.txt", "requirements.test.txt", "requirements.release.constraints.txt", "Dockerfile"):
        if sha256(SOURCE / filename) != sha256(MANIFEST / filename):
            raise RuntimeError(f"frozen manifest changed before verification: {filename}")
    environment = clean_environment()
    python = [str(ARCH), "-arm64", str(VENV / "bin/python")]
    completed = subprocess.run(python + ["-m", "pip", "list", "--format=json"], cwd=NATIVE, env=environment, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, check=True)
    current = {normalized_name(item["name"]): item["version"] for item in json.loads(completed.stdout)}
    expected_payload = json.loads((EVIDENCE / "resolved-distributions.json").read_text())
    expected = {normalized_name(item["name"]): item["version"] for item in expected_payload["distributions"]}
    pinned = {}
    for line in (MANIFEST / "requirements.release.constraints.txt").read_text().splitlines():
        if "==" in line and not line.lstrip().startswith("#"):
            name, version = line.split("==", 1)
            pinned[normalized_name(name.strip())] = version.strip()
    mismatched_pins = {name: {"expected": version, "observed": current.get(name)} for name, version in pinned.items() if current.get(name) != version}
    payload = {
        "resolved_metadata_equal": current == expected,
        "resolved_distribution_count": len(current),
        "pinned_constraint_count": len(pinned),
        "mismatched_pins": mismatched_pins,
        "scope": "Metadata equality and pinned-constraint parity only; no package or LocalOS import.",
    }
    (EVIDENCE / "metadata-parity.json").write_text(json.dumps(payload, indent=2, sort_keys=True))
    if current != expected or mismatched_pins:
        raise RuntimeError("native dependency metadata parity failed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--verify", action="store_true")
    arguments = parser.parse_args()
    if arguments.resume and arguments.verify:
        raise RuntimeError("resume and verify are mutually exclusive")
    if not BASE.is_dir() or not SOURCE.is_dir():
        raise RuntimeError("expected frozen hfLYPi source archive is absent")
    if arguments.verify:
        return verify_existing()
    if NATIVE.exists() and not arguments.resume:
        raise RuntimeError("native preparation directory already exists; refusing overwrite")
    if arguments.resume and (not VENV.is_dir() or (EVIDENCE / "resolved-distributions.json").exists()):
        raise RuntimeError("native preparation is not safely resumable")
    if not PYTHON.is_file() or not ARCH.is_file():
        raise RuntimeError("required native arm64 Python launcher is unavailable")
    if free_bytes() < MIN_START_BYTES:
        raise RuntimeError("insufficient free disk for native preparation start")

    if not arguments.resume:
        NATIVE.mkdir()
        MANIFEST.mkdir()
        WHEELS.mkdir()
        EVIDENCE.mkdir()
        TMP.mkdir()
    source_files = [
        "requirements.txt",
        "requirements.test.txt",
        "requirements.release.constraints.txt",
        "Dockerfile",
    ]
    source_hashes: dict[str, str] = {}
    for filename in source_files:
        original = SOURCE / filename
        target = MANIFEST / filename
        if not original.is_file():
            raise RuntimeError(f"missing frozen manifest: {filename}")
        if arguments.resume:
            if not target.is_file() or sha256(original) != sha256(target):
                raise RuntimeError(f"frozen manifest changed during resume: {filename}")
        else:
            shutil.copyfile(original, target)
        source_hashes[filename] = sha256(target)

    environment = clean_environment()
    source_metadata = {
        "nonce": NONCE,
        "source_path": str(SOURCE),
        "source_hashes": source_hashes,
        "initial_free_bytes": free_bytes(),
        "minimum_start_bytes": MIN_START_BYTES,
        "minimum_live_bytes": MIN_LIVE_BYTES,
        "python_launcher": str(PYTHON),
        "architecture_launcher": str(ARCH),
        "scope": "Dependency preparation only; no LocalOS imports, Docker, database, dotenv, provider credential, or test execution.",
    }
    if not arguments.resume:
        (EVIDENCE / "source-and-capacity.json").write_text(json.dumps(source_metadata, indent=2, sort_keys=True))
        capture("venv", [str(ARCH), "-arm64", str(PYTHON), "-m", "venv", str(VENV)], environment)
    python = [str(ARCH), "-arm64", str(VENV / "bin/python")]
    pip = python + ["-m", "pip", "--isolated", "--disable-pip-version-check", "--no-input", "--no-cache-dir", "--keyring-provider", "disabled"]
    index = ["--index-url", "https://pypi.org/simple", "--timeout", "30", "--retries", "2"]
    constraints = str(MANIFEST / "requirements.release.constraints.txt")
    if not arguments.resume:
        capture("bootstrap", pip + ["install"] + index + ["pip==26.2", "setuptools==84.0.0", "wheel==0.48.0"], environment)
        capture("googlemaps-build-prerequisite", pip + ["install"] + index + ["--only-binary=:all:", "-c", constraints, "requests==2.34.2"], environment)

    built_wheels: dict[str, dict[str, object]] = {}
    for package in ("pyaes", "googlemaps"):
        sdist = download_sdist(package, environment)
        matches = sorted(WHEELS.glob(f"{package}-*.whl"))
        if not matches:
            capture(f"build-{package}", pip + ["wheel", "--no-index", "--no-deps", "--no-build-isolation", "--wheel-dir", str(WHEELS), str(sdist)], environment)
            matches = sorted(WHEELS.glob(f"{package}-*.whl"))
        if len(matches) != 1:
            raise RuntimeError(f"expected exactly one {package} wheel")
        built_wheels[package] = wheel_metadata(package, matches[0])

    if free_bytes() < MIN_LIVE_BYTES:
        raise RuntimeError("insufficient live disk remaining before dependency install")
    capture(
        "install-current-manifests",
        pip + [
            "install",
            *index,
            "--only-binary=:all:",
            "--find-links", str(WHEELS),
            "-c", constraints,
            "-r", str(MANIFEST / "requirements.txt"),
            "-r", str(MANIFEST / "requirements.test.txt"),
        ],
        environment,
    )
    capture("pip-check", pip + ["check"], environment)
    completed = subprocess.run(python + ["-m", "pip", "list", "--format=json"], cwd=NATIVE, env=environment, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, check=True)
    distributions = json.loads(completed.stdout)
    payload = {
        "distribution_count": len(distributions),
        "distributions": sorted(distributions, key=lambda item: item["name"].lower()),
        "built_wheel_sha256": built_wheels,
        "final_free_bytes": free_bytes(),
        "minimum_live_bytes": MIN_LIVE_BYTES,
    }
    (EVIDENCE / "resolved-distributions.json").write_text(json.dumps(payload, indent=2, sort_keys=True))
    if free_bytes() < MIN_LIVE_BYTES:
        raise RuntimeError("native preparation ended below live disk floor")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        if EVIDENCE.is_dir():
            (EVIDENCE / "failure.json").write_text(json.dumps({"error": str(sys.exception())}, indent=2, sort_keys=True))
        raise
