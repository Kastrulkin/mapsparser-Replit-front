#!/usr/bin/env python3
"""Repeat the same three guard probes with an explicitly ARM64 parent."""

from __future__ import annotations

import json
from pathlib import Path
import platform
import runpy
import shutil


SUPPORT = Path(__file__).resolve().parent
BASE = Path("/private/tmp/localos-readiness-20260921.hfLYPi")
NATIVE = BASE / "native"
EVIDENCE = NATIVE / "evidence"


def main() -> int:
    if platform.machine() != "arm64":
        raise RuntimeError("native probes require /usr/bin/arch -arm64 Python")
    if shutil.disk_usage(BASE).free < 5 * 1024**3:
        raise RuntimeError("native probes require at least 5 GiB free")
    launcher = runpy.run_path(str(SUPPORT / "native_guard_checks_hflypi.py"))
    launcher["verify_endpoints"]()
    labels = ("negative", "child", "own-postgres")
    for path in (EVIDENCE / "native-guard-metadata-v3.json", *(EVIDENCE / f"native-guard-{label}-v3.json" for label in labels)):
        if path.exists() or path.is_symlink():
            raise RuntimeError("ARM64 guard evidence already exists")
    previous = json.loads((EVIDENCE / "native-guard-metadata-v2.json").read_text())
    previous_probe = json.loads((EVIDENCE / "native-guard-negative-v2.json").read_text())
    if previous_probe["exit_code"] != 78:
        raise RuntimeError("expected preserved v2 initialization failure")
    guard_hash = launcher["sha256"](BASE / "source/src/sitecustomize.py")
    probe_hash = launcher["sha256"](NATIVE / "native_hflypi_probe_v1.py")
    if guard_hash != previous["guard_sha256"] or guard_hash != launcher["sha256"](SUPPORT / "native_hflypi_sitecustomize.py"):
        raise RuntimeError("installed guard differs from reviewed v2")
    if probe_hash != previous["probe_sha256"] or probe_hash != launcher["sha256"](SUPPORT / "native_hflypi_probe.py"):
        raise RuntimeError("installed probe differs from reviewed source")
    tracked = launcher["verify_frozen_source"]()
    docker = launcher["verify_docker_owner"]()
    launcher["write_exclusive"](EVIDENCE / "native-guard-metadata-v3.json", json.dumps({
        "guard_sha256": guard_hash,
        "probe_sha256": probe_hash,
        "tracked_files": tracked,
        "parent_machine": platform.machine(),
        "docker": docker,
        "scope": "Same v2 guard and v1 probe; ARM64 parent invocation only.",
    }, indent=2, sort_keys=True))
    for label in labels:
        current_docker = launcher["verify_docker_owner"]() if label == "own-postgres" else None
        launcher["capture"](label, [str(NATIVE / "venv/bin/python"), "-B", str(NATIVE / "native_hflypi_probe_v1.py"), label], launcher["environment"](guard_hash), current_docker, attempt="v3")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
