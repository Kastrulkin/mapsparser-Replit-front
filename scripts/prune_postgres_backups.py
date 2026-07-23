#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import re
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime
from pathlib import Path


AUTOMATED_BACKUP_PATTERN = re.compile(r"^[A-Za-z0-9-]+_(\d{8})_(\d{6})\.sql\.gz$")


def parse_timestamp(path: Path) -> datetime | None:
    match = AUTOMATED_BACKUP_PATTERN.fullmatch(path.name)
    if not match:
        return None
    return datetime.strptime("".join(match.groups()), "%Y%m%d%H%M%S")


def newest_by_key(
    items: list[tuple[Path, datetime]],
    key_function: Callable[[datetime], object],
    limit: int,
) -> set[Path]:
    grouped: dict[object, list[tuple[Path, datetime]]] = defaultdict(list)
    for item in items:
        grouped[key_function(item[1])].append(item)
    ordered_keys = sorted(grouped, reverse=True)[:limit]
    kept: set[Path] = set()
    for key in ordered_keys:
        kept.add(max(grouped[key], key=lambda item: item[1])[0])
    return kept


def retained_paths(
    items: list[tuple[Path, datetime]],
    *,
    daily: int,
    weekly: int,
    monthly: int,
) -> set[Path]:
    keep: set[Path] = set()
    keep.update(newest_by_key(items, lambda value: value.date(), daily))
    keep.update(newest_by_key(items, lambda value: value.isocalendar()[:2], weekly))
    keep.update(newest_by_key(items, lambda value: (value.year, value.month), monthly))
    return keep


def main() -> int:
    parser = argparse.ArgumentParser(description="Rotate standard PostgreSQL backups.")
    parser.add_argument("--directory", default="data/backups/postgres")
    parser.add_argument("--daily", type=int, default=int(os.getenv("POSTGRES_BACKUP_DAILY_RETENTION", "3")))
    parser.add_argument("--weekly", type=int, default=int(os.getenv("POSTGRES_BACKUP_WEEKLY_RETENTION", "2")))
    parser.add_argument("--monthly", type=int, default=int(os.getenv("POSTGRES_BACKUP_MONTHLY_RETENTION", "2")))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if min(args.daily, args.weekly, args.monthly) < 0:
        parser.error("retention counts must be non-negative")

    backup_dir = Path(args.directory)
    candidates: list[tuple[Path, datetime]] = []
    unparsed: list[Path] = []
    for path in sorted(backup_dir.glob("*.sql.gz")):
        if path.name == "latest.sql.gz":
            continue
        timestamp = parse_timestamp(path)
        if timestamp is None:
            unparsed.append(path)
            continue
        candidates.append((path, timestamp))

    keep = retained_paths(
        candidates,
        daily=args.daily,
        weekly=args.weekly,
        monthly=args.monthly,
    )
    remove = [path for path, _timestamp in candidates if path not in keep]
    reclaimed = sum(path.stat().st_size for path in remove)

    for path in sorted(keep):
        print(f"KEEP {path}")
    for path in unparsed:
        print(f"KEEP_UNPARSED {path}")
    for path in remove:
        print(f"{'DELETE' if args.apply else 'WOULD_DELETE'} {path}")
        if args.apply:
            path.unlink()

    remaining = [path for path, _timestamp in candidates if path in keep]
    if remaining:
        newest = max(remaining, key=lambda path: path.stat().st_mtime)
        latest = backup_dir / "latest.sql.gz"
        if args.apply:
            temporary = backup_dir / ".latest.sql.gz.tmp"
            temporary.unlink(missing_ok=True)
            os.link(newest, temporary)
            temporary.replace(latest)
        print(f"{'LINKED' if args.apply else 'WOULD_LINK'} {latest} -> {newest.name}")

    print(
        f"kept={len(keep) + len(unparsed)} removed={len(remove)} "
        f"reclaimed_bytes={reclaimed} daily={args.daily} weekly={args.weekly} "
        f"monthly={args.monthly} apply={args.apply}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
