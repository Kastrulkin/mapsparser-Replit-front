"""Regenerate exactly the 50 template-review audits, dry-run by default."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor

from api.admin_prospecting import _create_admin_public_audit_for_lead
from core.audit_editorial import audit_quality_gate
from services.outreach_human_language import SLOP_PATTERNS


SOURCE = Path("/app/debug_data/localos-template-review-v8-20260811.json")
BACKUP_DIR = Path("/app/debug_data/template-group-audit-backup-v12-20260811")


def _number(value):
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def _json_bytes(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str).encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    review = json.loads(SOURCE.read_text(encoding="utf-8"))
    lead_ids = [
        item["lead_id"]
        for item in review["results"]
        if item["classification"] == "content_ready"
    ]
    if len(lead_ids) != 50 or len(set(lead_ids)) != 50:
        raise RuntimeError(f"expected_50_unique_leads_got_{len(lead_ids)}")

    connection = psycopg2.connect(
        os.environ["DATABASE_URL"], cursor_factory=RealDictCursor
    )
    connection.autocommit = False
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT *
        FROM adminprospectingleadpublicoffers
        WHERE lead_id = ANY(%s)
        ORDER BY lead_id
        FOR UPDATE
        """,
        (lead_ids,),
    )
    before = [dict(row) for row in cursor.fetchall()]
    if len(before) != 50:
        connection.rollback()
        raise RuntimeError(f"expected_50_existing_audits_got_{len(before)}")
    if any(row.get("edited_json") is not None for row in before):
        connection.rollback()
        raise RuntimeError("manual_edits_present")

    backup_payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "apply" if args.apply else "dry_run",
        "lead_ids": lead_ids,
        "rows": before,
    }
    backup_bytes = _json_bytes(backup_payload)
    backup_sha = hashlib.sha256(backup_bytes).hexdigest()
    backup_path = BACKUP_DIR / (
        "prewrite.json" if args.apply else "dry-run-prewrite.json"
    )
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path.write_bytes(backup_bytes)
    backup_path.with_suffix(".sha256").write_text(
        f"{backup_sha}  {backup_path.name}\n", encoding="utf-8"
    )

    existing_by_lead = {str(row["lead_id"]): row for row in before}
    results = []
    for lead_id in lead_ids:
        cursor.execute("SELECT * FROM prospectingleads WHERE id = %s", (lead_id,))
        lead = dict(cursor.fetchone() or {})
        if not lead:
            raise RuntimeError(f"lead_missing:{lead_id}")
        existing = existing_by_lead[lead_id]
        user_id = str(existing.get("published_by") or existing.get("created_by") or "")
        source_type = str(existing.get("source_type") or "admin_prospecting_public_audit")
        slug, public_url, page = _create_admin_public_audit_for_lead(
            cursor,
            lead=lead,
            user_id=user_id,
            source_type=source_type,
        )
        audit = page.get("audit") if isinstance(page.get("audit"), dict) else {}
        audit_text = json.dumps(audit, ensure_ascii=False)
        slop = [label for label, pattern in SLOP_PATTERNS if pattern.search(audit_text)]
        long_dashes = audit_text.count("—") + audit_text.count("–")
        current = audit.get("current_state") if isinstance(audit.get("current_state"), dict) else {}
        rating_match = _number(current.get("rating")) == _number(lead.get("rating"))
        reviews_match = _number(current.get("reviews_count")) == _number(lead.get("reviews_count"))
        is_yandex = "yandex." in str(lead.get("source_url") or "").lower()
        description_ok = not is_yandex or (
            current.get("description_applicable") is False
            and current.get("description_present") is None
            and "positioning_description_gap" not in audit_text
            and "добавить описание" not in audit_text.lower()
            and "понятного описания" not in audit_text.lower()
            and "показать в описании" not in audit_text.lower()
        )
        gate = audit_quality_gate(audit)
        passed = (
            gate.get("status") == "pass"
            and not slop
            and long_dashes == 0
            and rating_match
            and reviews_match
            and description_ok
        )
        results.append(
            {
                "lead_id": lead_id,
                "name": lead.get("name"),
                "slug": slug,
                "public_url": public_url,
                "rating": lead.get("rating"),
                "reviews_count": lead.get("reviews_count"),
                "rating_match": rating_match,
                "reviews_match": reviews_match,
                "description_ok": description_ok,
                "editorial_status": gate.get("status"),
                "slop": slop,
                "long_dashes": long_dashes,
                "passed": passed,
            }
        )

    failed = [item for item in results if not item["passed"]]
    if failed:
        connection.rollback()
        print(json.dumps({"status": "FAIL", "failed": failed}, ensure_ascii=False, indent=2, default=str))
        raise SystemExit(1)

    if args.apply:
        connection.commit()
        status = "APPLIED"
    else:
        connection.rollback()
        status = "DRY_RUN_ROLLED_BACK"
    connection.close()

    result = {
        "status": status,
        "audits": len(results),
        "passed": len(results),
        "failed": 0,
        "backup_path": str(backup_path),
        "backup_sha256": backup_sha,
        "result_sha256": hashlib.sha256(_json_bytes(results)).hexdigest(),
        "items": results,
    }
    result_path = BACKUP_DIR / (
        "apply-result.json" if args.apply else "dry-run-result.json"
    )
    result_path.write_bytes(_json_bytes(result))
    print(json.dumps({key: value for key, value in result.items() if key != "items"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
