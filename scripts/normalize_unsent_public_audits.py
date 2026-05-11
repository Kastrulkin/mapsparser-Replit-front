#!/usr/bin/env python3
import argparse
import copy
import json
import os
import sys
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import Json
from psycopg2.extras import RealDictCursor

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
for candidate in (str(REPO_ROOT), str(SRC_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from api.admin_prospecting import _ensure_admin_prospecting_public_offers_table
from core.audit_editorial import normalize_audit_text
from core.public_audit_editor import normalize_public_audit_page_json


SENT_STATUSES = ("sent", "delivered")


def _connect():
    return psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=RealDictCursor)


def _normalize_editor_text(value: Any, audit_profile: str = "") -> Any:
    if isinstance(value, str):
        return normalize_audit_text(value, audit_profile=audit_profile)
    if isinstance(value, list):
        return [_normalize_editor_text(item, audit_profile=audit_profile) for item in value]
    if isinstance(value, dict):
        return {
            key: _normalize_editor_text(item, audit_profile=audit_profile)
            for key, item in value.items()
        }
    return value


def _json_changed(before: Any, after: Any) -> bool:
    return json.dumps(before, ensure_ascii=False, sort_keys=True, default=str) != json.dumps(
        after,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


def _normalize_page(value: Any, slug: str) -> dict[str, Any] | None:
    if not isinstance(value, dict) or not value:
        return None
    return normalize_public_audit_page_json(value, slug=slug)


def _audit_profile_from(*values: Any) -> str:
    for value in values:
        if not isinstance(value, dict):
            continue
        audit = value.get("audit") if isinstance(value.get("audit"), dict) else {}
        profile = str(audit.get("audit_profile") or "").strip()
        if profile:
            return profile
    return ""


def _load_target_rows(cur, limit: int | None, lead_id: str | None) -> list[dict[str, Any]]:
    params: list[Any] = []
    lead_filter = ""
    if lead_id:
        lead_filter = "AND o.lead_id = %s"
        params.append(lead_id)
    limit_sql = ""
    if limit and limit > 0:
        limit_sql = "LIMIT %s"
        params.append(limit)

    cur.execute(
        f"""
        SELECT
            o.lead_id,
            o.slug,
            o.page_json,
            o.generated_json,
            o.edited_json,
            o.published_json,
            o.edit_status,
            o.updated_at,
            l.name,
            l.status AS lead_status,
            l.partnership_stage
        FROM adminprospectingleadpublicoffers o
        JOIN prospectingleads l
          ON l.id = o.lead_id
        WHERE o.is_active = TRUE
          {lead_filter}
          AND COALESCE(l.status, '') NOT IN %s
          AND COALESCE(l.partnership_stage, '') NOT IN %s
          AND NOT EXISTS (
              SELECT 1
              FROM outreachsendqueue q
              WHERE q.lead_id = o.lead_id
                AND COALESCE(q.delivery_status, '') IN %s
              LIMIT 1
          )
        ORDER BY o.updated_at ASC NULLS FIRST, o.created_at ASC NULLS FIRST
        {limit_sql}
        """,
        tuple(params + [SENT_STATUSES, SENT_STATUSES, SENT_STATUSES])
        if not limit_sql
        else tuple(params[:-1] + [SENT_STATUSES, SENT_STATUSES, SENT_STATUSES, params[-1]]),
    )
    return [dict(row) for row in cur.fetchall() or []]


def _normalize_row(row: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    slug = str(row.get("slug") or "").strip()
    page_before = row.get("page_json") if isinstance(row.get("page_json"), dict) else {}
    generated_before = row.get("generated_json") if isinstance(row.get("generated_json"), dict) else {}
    published_before = row.get("published_json") if isinstance(row.get("published_json"), dict) else {}
    edited_before = row.get("edited_json") if isinstance(row.get("edited_json"), dict) else None

    page_after = _normalize_page(page_before, slug) or copy.deepcopy(page_before)
    generated_after = _normalize_page(generated_before, slug) or copy.deepcopy(generated_before)
    published_after = _normalize_page(published_before, slug) or copy.deepcopy(published_before)

    audit_profile = _audit_profile_from(page_after, generated_after, published_after)
    edited_after = _normalize_editor_text(edited_before, audit_profile=audit_profile) if edited_before else None

    changes = {
        "page_json": _json_changed(page_before, page_after),
        "generated_json": _json_changed(generated_before, generated_after),
        "published_json": _json_changed(published_before, published_after),
        "edited_json": _json_changed(edited_before, edited_after),
    }
    return (
        {
            "page_json": page_after,
            "generated_json": generated_after or None,
            "published_json": published_after or None,
            "edited_json": edited_after,
        },
        changes,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize unsent public audits to the current public audit copy format.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--lead-id", type=str, default="")
    args = parser.parse_args()

    conn = _connect()
    try:
        _ensure_admin_prospecting_public_offers_table(conn)
        cur = conn.cursor()
        target_rows = _load_target_rows(
            cur,
            args.limit if args.limit > 0 else None,
            str(args.lead_id or "").strip() or None,
        )
        print(json.dumps({"target_total": len(target_rows), "dry_run": bool(args.dry_run)}, ensure_ascii=False), flush=True)

        processed = 0
        changed = 0
        skipped = 0
        errors = 0

        for row in target_rows:
            lead_id = str(row.get("lead_id") or "")
            try:
                normalized, changes = _normalize_row(row)
                has_changes = any(bool(value) for value in changes.values())
                if not has_changes:
                    skipped += 1
                    print(
                        json.dumps(
                            {
                                "lead_id": lead_id,
                                "slug": row.get("slug"),
                                "name": row.get("name"),
                                "changed": False,
                            },
                            ensure_ascii=False,
                        ),
                        flush=True,
                    )
                    continue

                if not args.dry_run:
                    cur.execute(
                        """
                        UPDATE adminprospectingleadpublicoffers
                        SET page_json = %s,
                            generated_json = %s,
                            edited_json = %s,
                            published_json = %s,
                            updated_at = NOW()
                        WHERE lead_id = %s
                        """,
                        (
                            Json(normalized["page_json"]),
                            Json(normalized["generated_json"]) if normalized["generated_json"] else None,
                            Json(normalized["edited_json"]) if normalized["edited_json"] else None,
                            Json(normalized["published_json"]) if normalized["published_json"] else None,
                            lead_id,
                        ),
                    )
                    conn.commit()
                changed += 1
                processed += 1
                print(
                    json.dumps(
                        {
                            "lead_id": lead_id,
                            "slug": row.get("slug"),
                            "name": row.get("name"),
                            "changed": True,
                            "changes": changes,
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
            except Exception as exc:
                conn.rollback()
                errors += 1
                print(
                    json.dumps(
                        {
                            "lead_id": lead_id,
                            "slug": row.get("slug"),
                            "name": row.get("name"),
                            "error": str(exc),
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )

        print(
            json.dumps(
                {
                    "target_total": len(target_rows),
                    "processed": processed,
                    "changed": changed,
                    "skipped": skipped,
                    "errors": errors,
                    "dry_run": bool(args.dry_run),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
