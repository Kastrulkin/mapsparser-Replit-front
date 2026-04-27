#!/usr/bin/env python3
import json
import os
from typing import Any

import psycopg2
from psycopg2.extras import Json
from psycopg2.extras import RealDictCursor

from api.admin_prospecting import DRAFT_GENERATED
from api.admin_prospecting import _attach_admin_prospecting_public_offer_metadata
from api.admin_prospecting import _drop_mismatched_explicit_business_link
from api.admin_prospecting import _generate_superadmin_deterministic_first_message
from api.admin_prospecting import _normalize_lead_for_display
from api.admin_prospecting import _sync_lead_business_link_from_parse_history
from api.admin_prospecting import _sync_lead_contacts_from_parsed_data
from core.card_audit import build_lead_card_preview_snapshot


def _connect():
    return psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=RealDictCursor)


def _load_target_leads(cur) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT l.*
        FROM prospectingleads l
        JOIN adminprospectingleadpublicoffers o
          ON o.lead_id = l.id
         AND o.is_active = TRUE
        LEFT JOIN LATERAL (
            SELECT *
            FROM outreachmessagedrafts d
            WHERE d.lead_id = l.id
            ORDER BY d.updated_at DESC NULLS LAST, d.created_at DESC NULLS LAST
            LIMIT 1
        ) d ON TRUE
        WHERE COALESCE(o.page_json->'audit'->'ai_enrichment'->>'source', o.page_json->>'prompt_source', '') = 'deterministic'
          AND COALESCE(d.learning_note_json->>'prompt_version', '') = 'deterministic_v1'
        ORDER BY l.updated_at DESC NULLS LAST, l.created_at DESC NULLS LAST, l.id DESC
        """
    )
    return [dict(row) for row in cur.fetchall()]


def main() -> None:
    conn = _connect()
    try:
        cur = conn.cursor()
        leads = _load_target_leads(cur)
        print(json.dumps({"total": len(leads)}, ensure_ascii=False), flush=True)

        processed = 0
        errors = 0
        quality_failures = 0

        for raw_lead in leads:
            lead_id = str(raw_lead.get("id") or "")
            try:
                lead = _drop_mismatched_explicit_business_link(dict(raw_lead))
                lead = _sync_lead_business_link_from_parse_history(dict(lead))
                lead = _sync_lead_contacts_from_parsed_data(dict(lead))
                lead["preferred_language"] = "ru"
                lead["enabled_languages"] = ["ru"]

                display_lead = _normalize_lead_for_display(dict(lead))
                if not display_lead:
                    raise ValueError("display_lead_unavailable")

                preview = build_lead_card_preview_snapshot(display_lead)
                enriched_lead = _attach_admin_prospecting_public_offer_metadata(conn, dict(display_lead))
                draft_payload = _generate_superadmin_deterministic_first_message(enriched_lead, preview)

                cur.execute(
                    """
                    SELECT id
                    FROM outreachmessagedrafts
                    WHERE lead_id = %s
                    ORDER BY updated_at DESC NULLS LAST, created_at DESC
                    LIMIT 1
                    """,
                    (lead_id,),
                )
                existing_draft = cur.fetchone()
                if not existing_draft or not existing_draft.get("id"):
                    raise ValueError("draft_not_found")

                learning_note = {
                    "source": draft_payload.get("prompt_source") or "deterministic",
                    "prompt_key": draft_payload.get("prompt_key"),
                    "prompt_version": draft_payload.get("prompt_version"),
                }

                cur.execute(
                    """
                    UPDATE outreachmessagedrafts
                    SET channel = %s,
                        angle_type = %s,
                        tone = %s,
                        status = %s,
                        generated_text = %s,
                        edited_text = %s,
                        approved_text = NULL,
                        learning_note_json = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (
                        "email",
                        draft_payload["angle_type"],
                        draft_payload["tone"],
                        DRAFT_GENERATED,
                        draft_payload["generated_text"],
                        draft_payload["generated_text"],
                        Json(learning_note),
                        str(existing_draft["id"]),
                    ),
                )

                issues: list[str] = []
                draft_text = str(draft_payload.get("generated_text") or "").strip()
                company_name = str(display_lead.get("name") or "").strip()
                if company_name and company_name not in draft_text:
                    issues.append("missing_company_name")
                if "Например, " not in draft_text:
                    issues.append("missing_reason_line")
                if "https://localos.pro/" not in draft_text:
                    issues.append("missing_audit_link")
                if "настрою всё, до результата" not in draft_text:
                    issues.append("missing_new_cta")
                if issues:
                    quality_failures += 1

                conn.commit()
                processed += 1
                print(
                    json.dumps(
                        {
                            "lead_id": lead_id,
                            "name": company_name,
                            "issues": issues,
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
                            "name": str(raw_lead.get("name") or ""),
                            "error": str(exc),
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )

        print(
            json.dumps(
                {
                    "processed": processed,
                    "errors": errors,
                    "quality_failures": quality_failures,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
