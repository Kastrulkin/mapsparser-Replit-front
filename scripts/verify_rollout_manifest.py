#!/usr/bin/env python3
"""Verify that rollout package files still match the reviewed SHA-256 manifest."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPOSITORY_ROOT / "outputs" / "localos-rollout-manifest-2026-08-31.tsv"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--package",
        action="append",
        dest="packages",
        help="Verify only this package. Repeat for more than one package.",
    )
    return parser.parse_args()


def main() -> int:
    arguments = _arguments()
    manifest = arguments.manifest.resolve()
    selected = set(arguments.packages or [])
    failures: list[dict[str, str]] = []
    checked = 0

    with manifest.open(encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            package = str(row.get("package") or "")
            if selected and package not in selected:
                continue
            relative_path = str(row.get("path") or "")
            expected = str(row.get("sha256") or "")
            target = REPOSITORY_ROOT / relative_path
            checked += 1
            if not target.is_file():
                failures.append({"package": package, "path": relative_path, "reason": "missing"})
                continue
            actual = _sha256(target)
            if actual != expected:
                failures.append(
                    {
                        "package": package,
                        "path": relative_path,
                        "reason": "sha256_mismatch",
                    }
                )

    result = {
        "ok": not failures,
        "checked": checked,
        "packages": sorted(selected) if selected else "all",
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
