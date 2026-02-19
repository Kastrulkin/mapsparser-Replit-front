#!/usr/bin/env python3
"""
Показать последний debug bundle для business_id.

Ищет директории в DEBUG_DIR (или ./debug_data), имя которых содержит business_id,
берёт самую свежую по mtime и выводит:
- путь
- первые 20 строк page.html
"""

import os
import sys
from pathlib import Path
from typing import List, Optional


def find_last_bundle(base_dir: Path, business_id: str) -> Optional[Path]:
    if not base_dir.exists():
        return None
    candidates: List[Path] = []
    for p in base_dir.iterdir():
        if not p.is_dir():
            continue
        if business_id in p.name:
            candidates.append(p)
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def head_lines(path: Path, n: int = 20) -> List[str]:
    if not path.exists():
        return [f"(no such file: {path})"]
    out: List[str] = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            if i >= n:
                break
            out.append(line.rstrip("\n"))
    return out


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: scripts/show_last_debug_bundle.py <BUSINESS_ID>", file=sys.stderr)
        return 1

    business_id = sys.argv[1].strip()
    if not business_id:
        print("Empty business_id", file=sys.stderr)
        return 1

    base_dir_str = os.getenv("DEBUG_DIR", "./debug_data")
    base_dir = Path(base_dir_str)

    bundle = find_last_bundle(base_dir, business_id)
    if not bundle:
        print(f"No bundles found in {base_dir} for business_id containing '{business_id}'")
        return 0

    print("=== Debug bundle ===")
    print(f"path: {bundle}")

    html_path = bundle / "page.html"
    print("\n=== page.html (head) ===")
    for line in head_lines(html_path, 20):
        print(line)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

