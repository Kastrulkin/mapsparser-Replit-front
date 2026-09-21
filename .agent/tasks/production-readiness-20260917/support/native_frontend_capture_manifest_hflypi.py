#!/usr/bin/env python3
"""Archive selected immutable hfLYPi frontend captures with a hash manifest."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil


SOURCE = Path("/private/tmp/localos-readiness-20260921.hfLYPi/native/evidence")
TARGET = Path(".agent/tasks/production-readiness-20260917/evidence/native-frontend-checks-hflypi-20260921")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selected(path: Path) -> bool:
    return path.is_file() and (
        path.name.startswith("native-frontend")
        or path.name.startswith("unit_network_guard_v")
        or path.name.startswith("frozen-source-identity")
    )


def main() -> int:
    if TARGET.exists():
        raise RuntimeError("frontend capture archive already exists")
    TARGET.mkdir(parents=True)
    entries = []
    for path in sorted(item for item in SOURCE.iterdir() if selected(item)):
        destination = TARGET / path.name
        shutil.copyfile(path, destination)
        entries.append({"name": path.name, "sha256": sha256(destination), "bytes": destination.stat().st_size})
    manifest = {
        "scope": "Raw clean hfLYPi frontend static/unit captures, private no-network guard copies, and frozen-source identity checks. Earlier browser/dependency-preparation evidence is archived separately.",
        "entry_count": len(entries),
        "entries": entries,
    }
    (TARGET / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
