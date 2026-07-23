#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from scripts.prune_postgres_backups import parse_timestamp
except ModuleNotFoundError:
    from prune_postgres_backups import parse_timestamp


DEFAULT_DIRECTORIES = ("backups", "db_backups", "data/backups/postgres")
BACKUP_SUFFIXES = (".dump", ".sql.gz")


def is_named_backup(path: Path) -> bool:
    if path.name == "latest.sql.gz":
        return False
    parent_parts = path.parent.parts
    is_standard_directory = parent_parts[-3:] == ("data", "backups", "postgres")
    if is_standard_directory and parse_timestamp(path) is not None:
        return False
    return path.name.endswith(BACKUP_SUFFIXES)


def is_protected(path: Path) -> bool:
    return Path(f"{path}.keep").exists() or (path.parent / ".keep").exists()


def unique_candidates(directories: list[Path]) -> list[Path]:
    candidates: list[Path] = []
    seen_inodes: set[tuple[int, int]] = set()
    for directory in directories:
        if not directory.exists():
            continue
        for path in directory.rglob("*"):
            if not path.is_file() or not is_named_backup(path):
                continue
            stat = path.stat()
            inode = (stat.st_dev, stat.st_ino)
            if inode in seen_inodes:
                continue
            seen_inodes.add(inode)
            candidates.append(path)
    return sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)


def removal_plan(
    candidates: list[Path],
    *,
    keep_latest: int,
    retention_days: int,
    max_total_bytes: int,
    now: datetime,
) -> list[Path]:
    protected = {path for path in candidates if is_protected(path)}
    protected.update(candidates[:keep_latest])
    cutoff = now - timedelta(days=retention_days)
    remove = {
        path
        for path in candidates
        if path not in protected
        and datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) < cutoff
    }

    remaining = [path for path in candidates if path not in remove]
    remaining_bytes = sum(path.stat().st_size for path in remaining)
    for path in reversed(remaining):
        if remaining_bytes <= max_total_bytes:
            break
        if path in protected:
            continue
        remove.add(path)
        remaining_bytes -= path.stat().st_size
    return sorted(remove, key=lambda path: path.stat().st_mtime)


def main() -> int:
    parser = argparse.ArgumentParser(description="Rotate named and pre-migration database backups.")
    parser.add_argument("--directory", action="append", dest="directories")
    parser.add_argument("--keep-latest", type=int, default=int(os.getenv("NAMED_BACKUP_KEEP_LATEST", "2")))
    parser.add_argument("--retention-days", type=int, default=int(os.getenv("NAMED_BACKUP_RETENTION_DAYS", "7")))
    parser.add_argument(
        "--max-total-bytes",
        type=int,
        default=int(os.getenv("NAMED_BACKUP_MAX_BYTES", str(4 * 1024**3))),
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if min(args.keep_latest, args.retention_days, args.max_total_bytes) < 0:
        parser.error("retention values must be non-negative")

    directories = [Path(value) for value in (args.directories or DEFAULT_DIRECTORIES)]
    candidates = unique_candidates(directories)
    remove = removal_plan(
        candidates,
        keep_latest=args.keep_latest,
        retention_days=args.retention_days,
        max_total_bytes=args.max_total_bytes,
        now=datetime.now(timezone.utc),
    )
    reclaimed = sum(path.stat().st_size for path in remove)
    remove_set = set(remove)

    for path in candidates:
        if path in remove_set:
            print(f"{'DELETE' if args.apply else 'WOULD_DELETE'} {path}")
            if args.apply:
                path.unlink()
        else:
            marker = "KEEP_PROTECTED" if is_protected(path) else "KEEP"
            print(f"{marker} {path}")

    print(
        f"kept={len(candidates) - len(remove)} removed={len(remove)} "
        f"reclaimed_bytes={reclaimed} max_total_bytes={args.max_total_bytes} apply={args.apply}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
