#!/usr/bin/env python3
import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
for candidate in (str(REPO_ROOT), str(SRC_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from main import _run_public_report_pipeline
from database_manager import get_db_connection


def _load_slugs(limit: int | None, slug: str | None, include_errors: bool) -> list[str]:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        statuses = ("ready", "completed", "done", "error") if include_errors else ("ready", "completed", "done")
        sql = """
            SELECT slug
            FROM publicreportrequests
            WHERE status = ANY(%s)
              AND (%s IS NULL OR slug = %s)
            ORDER BY updated_at DESC NULLS LAST, created_at DESC
        """
        params: list[object] = [list(statuses), slug, slug]
        if limit and limit > 0:
            sql += " LIMIT %s"
            params.append(limit)
        cur.execute(sql, params)
        rows = cur.fetchall() or []
        return [str((dict(row) if hasattr(row, "keys") else {"slug": row[0]}).get("slug") or "").strip() for row in rows]
    finally:
        conn.close()


def _load_status(slug: str) -> tuple[str, str]:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT status, COALESCE(error_text, '')
            FROM publicreportrequests
            WHERE slug = %s
            LIMIT 1
            """,
            (slug,),
        )
        row = cur.fetchone()
        if not row:
            return "missing", ""
        payload = dict(row) if hasattr(row, "keys") else {"status": row[0], "error_text": row[1]}
        return str(payload.get("status") or ""), str(payload.get("error_text") or "")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--slug", type=str, default="")
    parser.add_argument("--include-errors", action="store_true")
    args = parser.parse_args()

    target_slug = str(args.slug or "").strip() or None
    slugs = [item for item in _load_slugs(args.limit if args.limit > 0 else None, target_slug, args.include_errors) if item]
    print(json.dumps({"total": len(slugs)}, ensure_ascii=False), flush=True)

    processed = 0
    errors = 0
    for slug in slugs:
        try:
            _run_public_report_pipeline(slug)
            final_status, error_text = _load_status(slug)
            if final_status == "completed":
                processed += 1
            else:
                errors += 1
            print(
                json.dumps(
                    {
                        "slug": slug,
                        "status": final_status,
                        "error": error_text[:500] if final_status == "error" else "",
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
        except Exception as exc:
            errors += 1
            print(json.dumps({"slug": slug, "error": str(exc)}, ensure_ascii=False), flush=True)
    print(json.dumps({"processed": processed, "errors": errors}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    if not os.environ.get("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required")
    main()
