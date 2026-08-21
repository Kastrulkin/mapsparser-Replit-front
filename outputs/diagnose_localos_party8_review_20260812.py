#!/usr/bin/env python3
"""Read-only diagnostic for Party 8 review candidate failures."""

from __future__ import annotations

import importlib.util
import json
import os
from collections import Counter
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor


SELECTION = Path("/app/debug_data/localos-party8-selection-20260811.json")
BUILDER = Path("/app/debug_data/build_localos_party3_review_20260811.py")
OUTPUT = Path("/app/debug_data/localos-party8-review-diagnostic-20260812.json")


def load_builder():
    os.environ["LOCALOS_PARTY_NUMBER"] = "8"
    spec = importlib.util.spec_from_file_location("party8_builder", BUILDER)
    if spec is None or spec.loader is None:
        raise RuntimeError("builder_import_failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    source = json.loads(SELECTION.read_text(encoding="utf-8"))
    candidates = list(source["selected"]) + [
        item
        for item in source.get("eligible_not_selected") or []
        if not item.get("selection_skip_reason")
    ]
    builder = load_builder()
    connection = psycopg2.connect(
        os.environ["DATABASE_URL"], cursor_factory=RealDictCursor
    )
    connection.set_session(readonly=True, autocommit=False)
    cursor = connection.cursor()
    cursor.execute("SET TRANSACTION READ ONLY")
    passed = []
    failed = []
    used_routes: set[str] = set()
    try:
        for target in candidates:
            route_keys = set(target.get("verified_route_keys") or [])
            if route_keys.intersection(used_routes):
                failed.append(
                    {
                        "lead_id": target["lead_id"],
                        "name": target["name"],
                        "reason": "PARTY8_RECIPIENT_ROUTE_OVERLAP",
                    }
                )
                continue
            result, failure = builder.review_candidate(cursor, target)
            if result is not None:
                passed.append(result)
                used_routes.update(route_keys)
            else:
                failed.append(
                    {
                        "lead_id": target["lead_id"],
                        "name": target["name"],
                        **(failure or {"reason": "UNKNOWN_FAILURE"}),
                    }
                )
    finally:
        connection.rollback()
        connection.close()
    counts = Counter(str(item.get("reason") or "UNKNOWN") for item in failed)
    payload = {
        "read_only": True,
        "candidate_count": len(candidates),
        "passed_count": len(passed),
        "failed_count": len(failed),
        "failure_counts": dict(counts),
        "passed": passed,
        "failed": failed,
    }
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "candidate_count": len(candidates),
                "passed_count": len(passed),
                "failed_count": len(failed),
                "failure_counts": dict(counts),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
