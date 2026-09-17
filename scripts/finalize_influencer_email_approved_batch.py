#!/usr/bin/env python3
"""Promote an approved batch only when every exact validator record passed."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--records-dir", type=Path, required=True)
    parser.add_argument("--receipts-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    batch = json.loads(arguments.batch.read_text(encoding="utf-8"))
    by_profile = {item["creator_profile_id"]: item for item in batch["records"]}
    checked: list[dict[str, Any]] = []
    for record_path in sorted(arguments.records_dir.glob("*.json")):
        receipt_path = arguments.receipts_dir / record_path.name
        if not receipt_path.exists():
            raise RuntimeError(f"validation receipt missing: {record_path.name}")
        record_bytes = record_path.read_bytes()
        record = json.loads(record_bytes)
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt.get("valid") is not True:
            raise RuntimeError(f"validation failed: {record_path.name}")
        if receipt.get("record_sha256") != hashlib.sha256(record_bytes).hexdigest():
            raise RuntimeError(f"validation receipt hash mismatch: {record_path.name}")
        item = by_profile.get(record["lead_id"])
        if not item:
            raise RuntimeError(f"batch recipient missing: {record['lead_id']}")
        touch = record["touches"][0]
        contact = record["contacts"][0]
        if contact["value"].lower() != item["email"].lower():
            raise RuntimeError(f"email mismatch: {record['lead_id']}")
        if touch.get("subject") != item["subject"] or touch.get("body") != item["body"]:
            raise RuntimeError(f"rendered message mismatch: {record['lead_id']}")
        checked.append({
            "lead_id": record["lead_id"],
            "record_sha256": receipt["record_sha256"],
            "validator_version": receipt["validator_version"],
        })
    if len(checked) != int(batch["recipient_count"]) or len(checked) != len(by_profile):
        raise RuntimeError("validated recipient count mismatch")
    finalized = dict(batch)
    finalized["status"] = "approved_validated_in_progress"
    finalized["validation"] = {
        "valid": True,
        "validated_count": len(checked),
        "invalid_count": 0,
        "finalized_at": datetime.now(timezone.utc).isoformat(),
        "records": checked,
    }
    arguments.output.write_text(json.dumps(finalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "batch_id": finalized["batch_id"],
        "status": finalized["status"],
        "validated_count": len(checked),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
