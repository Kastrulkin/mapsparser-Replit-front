#!/usr/bin/env python3
"""Compare every tracked blob in commit 99849935 with the frozen hfLYPi archive."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys


COMMIT = "99849935de26e2932613f2a73cf515dff49104a1"
REPOSITORY = Path("/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре")
SOURCE = Path("/private/tmp/localos-readiness-20260921.hfLYPi/source")
EVIDENCE = Path("/private/tmp/localos-readiness-20260921.hfLYPi/native/evidence")
OUTPUT = EVIDENCE / "frozen-source-identity-postunit-v6.json"


def git_blob_sha1(payload: bytes) -> str:
    prefix = f"blob {len(payload)}\0".encode()
    return hashlib.sha1(prefix + payload).hexdigest()


def file_payload(path: Path, mode: str) -> bytes:
    if mode == "120000":
        if not path.is_symlink():
            raise RuntimeError("expected symlink")
        return os.fsencode(os.readlink(path))
    if not path.is_file() or path.is_symlink():
        raise RuntimeError("expected regular file")
    return path.read_bytes()


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError("identity evidence already exists")
    revision = subprocess.run(
        ["git", "-C", str(REPOSITORY), "rev-parse", COMMIT],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    if revision.stdout.strip() != COMMIT:
        raise RuntimeError("resolved commit does not match frozen-source commit")
    completed = subprocess.run(
        ["git", "-C", str(REPOSITORY), "ls-tree", "-rz", "-r", COMMIT],
        text=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    mismatches = []
    checked = 0
    symlink_blobs = 0
    for record in completed.stdout.split(b"\0"):
        if not record:
            continue
        header, raw_path = record.split(b"\t", 1)
        mode_raw, object_type_raw, sha_raw = header.split(b" ", 2)
        mode = mode_raw.decode()
        object_type = object_type_raw.decode()
        relative = Path(os.fsdecode(raw_path))
        if object_type != "blob":
            mismatches.append({"path": str(relative), "reason": f"unexpected tree object type {object_type}"})
            continue
        if mode == "120000":
            symlink_blobs += 1
        target = SOURCE / relative
        try:
            payload = file_payload(target, mode)
            observed_sha = git_blob_sha1(payload)
            observed_mode = "120000" if mode == "120000" and target.is_symlink() else format(stat.S_IMODE(target.lstat().st_mode), "06o")
            expected_mode = "000755" if mode == "100755" else "000644" if mode == "100644" else mode.zfill(6)
            if observed_sha != sha_raw.decode() or observed_mode != expected_mode:
                mismatches.append({
                    "path": str(relative),
                    "expected_blob_sha1": sha_raw.decode(),
                    "observed_blob_sha1": observed_sha,
                    "expected_mode": expected_mode,
                    "observed_mode": observed_mode,
                })
        except RuntimeError:
            mismatches.append({"path": str(relative), "reason": str(sys.exception())})
        checked += 1
    payload = {
        "commit": COMMIT,
        "resolved_commit": revision.stdout.strip(),
        "source": str(SOURCE),
        "checked_tracked_blobs": checked,
        "tracked_symlink_blobs": symlink_blobs,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "scope": "Tracked commit blobs and executable/symlink modes only. Untracked archive extras such as node_modules and private caches are outside comparison.",
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not mismatches else 1


if __name__ == "__main__":
    raise SystemExit(main())
