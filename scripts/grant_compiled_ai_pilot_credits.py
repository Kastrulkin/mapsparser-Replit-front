#!/usr/bin/env python3
"""Dry-run-first, ledger-backed credit grant for the Compiled AI pilot."""

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from database_manager import DatabaseManager
from services.compiled_ai_pilot_credit_grant import grant_compiled_ai_pilot_credits


APPLY_CONFIRMATION = "APPLY_COMPILED_AI_PILOT_CREDITS"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Preview or apply an auditable Compiled AI pilot credit grant."
    )
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--credits", required=True, type=int)
    parser.add_argument(
        "--external-id",
        required=True,
        help="Stable idempotency key starting with compiled-ai-pilot:",
    )
    parser.add_argument("--apply", action="store_true", help="Commit the grant")
    parser.add_argument(
        "--confirm",
        default="",
        help=f"Required with --apply: {APPLY_CONFIRMATION}",
    )
    args = parser.parse_args()
    if args.apply and args.confirm != APPLY_CONFIRMATION:
        parser.error(f"--apply requires --confirm {APPLY_CONFIRMATION}")

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        result = grant_compiled_ai_pilot_credits(
            cursor,
            user_id=args.user_id,
            credits=args.credits,
            external_id=args.external_id,
            apply=args.apply,
        )
        if args.apply:
            db.conn.commit()
        else:
            db.conn.rollback()
        print(json.dumps({"success": True, "dry_run": not args.apply, **result}, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        db.conn.rollback()
        print(
            json.dumps(
                {
                    "success": False,
                    "dry_run": not args.apply,
                    "error": str(exc),
                    "error_type": exc.__class__.__name__,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
