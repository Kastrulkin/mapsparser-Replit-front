#!/usr/bin/env python3
"""Versioned fail-closed startup diagnostic; negative probe only."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil


SUPPORT = Path(__file__).resolve().parent
BASE = Path("/private/tmp/localos-readiness-20260921.hfLYPi")
NATIVE = BASE / "native"
GUARD = BASE / "source/src/sitecustomize.py"
EVIDENCE = NATIVE / "evidence"
BACKUP = NATIVE / "native_hflypi_sitecustomize_v1.py"
STAGING = GUARD.with_name(".sitecustomize-v2-reviewed")
METADATA = EVIDENCE / "native-guard-metadata-v2.json"


def main() -> int:
    launcher = runpy.run_path(str(SUPPORT / "native_guard_checks_hflypi.py"))
    launcher["verify_endpoints"]()
    if shutil.disk_usage(BASE).free < 5 * 1024**3:
        raise RuntimeError("diagnostic requires at least 5 GiB free")
    for target in (BACKUP, STAGING, METADATA, EVIDENCE / "native-guard-negative-v2.json"):
        if target.exists() or target.is_symlink():
            raise RuntimeError("diagnostic target already exists")
    old = GUARD.read_bytes()
    previous = json.loads((EVIDENCE / "native-guard-metadata-v1.json").read_text())
    failure = json.loads((EVIDENCE / "native-guard-negative-v1.json").read_text())
    old_hash = hashlib.sha256(old).hexdigest()
    if old_hash != previous["guard_sha256"] or failure["exit_code"] != 78:
        raise RuntimeError("diagnostic requires the unchanged v1 startup failure")
    probe_hash = launcher["sha256"](NATIVE / "native_hflypi_probe_v1.py")
    if probe_hash != previous["probe_sha256"] or probe_hash != launcher["sha256"](SUPPORT / "native_hflypi_probe.py"):
        raise RuntimeError("copied probe differs from reviewed source")
    tracked = launcher["verify_frozen_source"]()
    launcher["write_exclusive"](BACKUP, old.decode())
    new_hash = launcher["install_exclusive"](SUPPORT / "native_hflypi_sitecustomize.py", STAGING)
    if launcher["sha256"](GUARD) != old_hash:
        raise RuntimeError("guard changed before versioned replacement")
    os.replace(STAGING, GUARD)
    launcher["write_exclusive"](METADATA, json.dumps({
        "guard_sha256": new_hash,
        "previous_guard_sha256": old_hash,
        "previous_guard_backup": str(BACKUP),
        "probe_sha256": probe_hash,
        "tracked_files": tracked,
        "scope": "Diagnostic reporting only; same enforcement; negative probe only.",
    }, indent=2, sort_keys=True))
    launcher["capture"]("negative", [str(NATIVE / "venv/bin/python"), "-B", str(NATIVE / "native_hflypi_probe_v1.py"), "negative"], launcher["environment"](new_hash), attempt="v2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
