#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path
from typing import Any


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def _norm_url(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    clean = value.strip()
    if not clean:
        return ""
    clean = clean.split("?")[0].rstrip("/")
    clean = re.sub(r"^https?://", "", clean, flags=re.IGNORECASE)
    return clean.lower()


def _dedup_key(item: dict[str, Any]) -> str:
    business_id = str(item.get("businessId") or "").strip()
    if business_id:
        return f"bid:{business_id}"

    norm_url = _norm_url(item.get("url"))
    if norm_url:
        return f"url:{norm_url}"

    name = str(item.get("title") or item.get("shortTitle") or "").strip().lower()
    address = str(item.get("address") or "").strip().lower()
    return f"na:{name}|{address}"


def _merge_values(current: Any, new_value: Any) -> Any:
    if _is_empty(current):
        return new_value
    if _is_empty(new_value):
        return current

    if isinstance(current, str) and isinstance(new_value, str):
        return new_value if len(new_value.strip()) > len(current.strip()) else current

    if isinstance(current, list) and isinstance(new_value, list):
        return new_value if len(new_value) > len(current) else current

    if isinstance(current, dict) and isinstance(new_value, dict):
        merged = dict(current)
        for key, value in new_value.items():
            merged[key] = _merge_values(merged.get(key), value)
        return merged

    return current


def _merge_item(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for key, value in incoming.items():
        merged[key] = _merge_values(merged.get(key), value)
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge and deduplicate Apify Yandex dataset files.")
    parser.add_argument("inputs", nargs="+", help="Input JSON files (each file is expected to contain a list).")
    parser.add_argument("--output", required=True, help="Output JSON file with unique merged records.")
    args = parser.parse_args()

    seen: dict[str, dict[str, Any]] = {}
    total_rows = 0

    for input_path in args.inputs:
        path = Path(input_path)
        rows = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            raise ValueError(f"{path} must contain a JSON array")
        for row in rows:
            if not isinstance(row, dict):
                continue
            total_rows += 1
            key = _dedup_key(row)
            if key in seen:
                seen[key] = _merge_item(seen[key], row)
            else:
                seen[key] = row

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    unique_rows = list(seen.values())
    output_path.write_text(json.dumps(unique_rows, ensure_ascii=False, indent=2), encoding="utf-8")

    duplicates = total_rows - len(unique_rows)
    print(f"total_rows={total_rows}")
    print(f"unique_rows={len(unique_rows)}")
    print(f"duplicates_removed={duplicates}")
    print(f"output={output_path}")


if __name__ == "__main__":
    main()
