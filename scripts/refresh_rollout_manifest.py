#!/usr/bin/env python3
"""Refresh hashes for the reviewed rollout allowlist and current frontend dist."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPOSITORY_ROOT / "outputs" / "localos-rollout-manifest-2026-08-31.tsv"
FRONTEND_DIST = REPOSITORY_ROOT / "frontend" / "dist"
FIELDNAMES = ("package", "sha256", "path")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    return parser.parse_args()


def _relative_path(path: Path) -> str:
    return path.resolve().relative_to(REPOSITORY_ROOT).as_posix()


def main() -> int:
    manifest = _arguments().manifest.resolve()
    with manifest.open(encoding="utf-8", newline="") as source:
        existing_rows = list(csv.DictReader(source, delimiter="\t"))

    rows: list[dict[str, str]] = []
    for row in existing_rows:
        package = str(row.get("package") or "")
        if package == "frontend_dist":
            continue
        relative_path = str(row.get("path") or "")
        target = REPOSITORY_ROOT / relative_path
        if not target.is_file():
            raise FileNotFoundError(f"Allowlisted rollout file is missing: {relative_path}")
        rows.append({
            "package": package,
            "sha256": _sha256(target),
            "path": relative_path,
        })

    if not FRONTEND_DIST.is_dir():
        raise FileNotFoundError(f"Frontend dist is missing: {FRONTEND_DIST}")
    for target in sorted(path for path in FRONTEND_DIST.rglob("*") if path.is_file()):
        rows.append({
            "package": "frontend_dist",
            "sha256": _sha256(target),
            "path": _relative_path(target),
        })

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        dir=manifest.parent,
        prefix=f".{manifest.name}.",
        delete=False,
    ) as destination:
        writer = csv.DictWriter(destination, fieldnames=FIELDNAMES, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        temporary_manifest = Path(destination.name)
    temporary_manifest.replace(manifest)

    counts = Counter(row["package"] for row in rows)
    print(json.dumps({
        "ok": True,
        "manifest": _relative_path(manifest),
        "sha256": _sha256(manifest),
        "rows": len(rows),
        "packages": dict(sorted(counts.items())),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
