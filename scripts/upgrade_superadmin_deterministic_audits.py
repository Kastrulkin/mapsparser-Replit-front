#!/usr/bin/env python3
import json
import os
from typing import Any

import psycopg2
from psycopg2.extras import Json
from psycopg2.extras import RealDictCursor

from api.admin_prospecting import _build_admin_lead_offer_payload
from api.admin_prospecting import _build_deterministic_dense_audit_enrichment
from api.admin_prospecting import _drop_mismatched_explicit_business_link
from api.admin_prospecting import _normalize_lead_for_display
from api.admin_prospecting import _sync_lead_business_link_from_parse_history
from api.admin_prospecting import _sync_lead_contacts_from_parsed_data
from api.admin_prospecting import _to_json_compatible
from core.card_audit import build_lead_card_preview_snapshot


def _connect():
    return psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=RealDictCursor)


def _pick_superadmin_user_id(cur) -> str | None:
    cur.execute(
        """
        SELECT id
        FROM users
        WHERE COALESCE(is_superadmin, FALSE) = TRUE
        ORDER BY created_at ASC NULLS LAST, id ASC
        LIMIT 1
        """
    )
    row = cur.fetchone()
    return str(row["id"]) if row and row.get("id") else None


def _load_target_leads(cur) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT l.*, o.slug
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
        WHERE COALESCE(l.intent, 'client_outreach') = 'client_outreach'
          AND COALESCE(o.page_json->'audit'->'ai_enrichment'->>'source', o.page_json->>'prompt_source', '') = 'deterministic'
          AND COALESCE(d.learning_note_json->>'prompt_version', '') = 'deterministic_v1'
        ORDER BY l.updated_at DESC NULLS LAST, l.created_at DESC NULLS LAST, l.id DESC
        """
    )
    return [dict(row) for row in cur.fetchall()]


def _upsert_offer(cur, lead_id: str, slug: str, page_json: dict[str, Any], created_by: str | None) -> None:
    cur.execute(
        """
        INSERT INTO adminprospectingleadpublicoffers (
            lead_id, slug, page_json, is_active, created_by, created_at, updated_at
        ) VALUES (%s, %s, %s, TRUE, %s, NOW(), NOW())
        ON CONFLICT (lead_id) DO UPDATE
        SET slug = EXCLUDED.slug,
            page_json = EXCLUDED.page_json,
            is_active = TRUE,
            updated_at = NOW()
        """,
        (lead_id, slug, Json(page_json), created_by),
    )


def main() -> None:
    conn = _connect()
    try:
        cur = conn.cursor()
        user_id = _pick_superadmin_user_id(cur)
        leads = _load_target_leads(cur)
        print(json.dumps({"total": len(leads)}, ensure_ascii=False), flush=True)

        processed = 0
        errors = 0
        quality_failures = 0

        for raw_lead in leads:
            lead_id = str(raw_lead.get("id") or "")
            slug = str(raw_lead.get("slug") or "").strip()
            try:
                lead = _drop_mismatched_explicit_business_link(dict(raw_lead))
                lead = _sync_lead_business_link_from_parse_history(dict(lead))
                lead = _sync_lead_contacts_from_parsed_data(dict(lead))
                lead["preferred_language"] = "ru"
                lead["enabled_languages"] = ["ru"]

                display_lead = _normalize_lead_for_display(dict(lead))
                if not display_lead:
                    raise ValueError("display_lead_unavailable")

                display_lead["preferred_language"] = "ru"
                display_lead["enabled_languages"] = ["ru"]
                preview = build_lead_card_preview_snapshot(display_lead)
                page_json = _to_json_compatible(
                    _build_admin_lead_offer_payload(
                        lead=display_lead,
                        preview=preview,
                        preferred_language="ru",
                        enabled_languages=["ru"],
                    )
                )
                dense_audit = _build_deterministic_dense_audit_enrichment(display_lead, preview, "ru")
                audit_payload = page_json.get("audit") if isinstance(page_json.get("audit"), dict) else {}
                if audit_payload:
                    enriched_summary = str(dense_audit.get("summary_text") or "").strip()
                    enriched_actions = dense_audit.get("recommended_actions") if isinstance(dense_audit.get("recommended_actions"), list) else []
                    why_now = str(dense_audit.get("why_now") or "").strip()
                    if enriched_summary:
                        audit_payload["summary_text"] = enriched_summary
                    if enriched_actions:
                        audit_payload["recommended_actions"] = enriched_actions
                    if why_now:
                        audit_payload["why_now"] = why_now
                audit_payload["ai_enrichment"] = dense_audit.get("meta") if isinstance(dense_audit.get("meta"), dict) else {}
                page_json["audit"] = audit_payload
                page_json["preferred_language"] = "ru"
                page_json["primary_language"] = "ru"
                page_json["enabled_languages"] = ["ru"]
                page_json["ai_enrichment"] = dense_audit.get("meta") if isinstance(dense_audit.get("meta"), dict) else {}

                _upsert_offer(cur, lead_id, slug, page_json, user_id)
                cur.execute(
                    """
                    UPDATE prospectingleads
                    SET preferred_language = 'ru',
                        enabled_languages = '["ru"]'::jsonb,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (lead_id,),
                )

                issues: list[str] = []
                summary_text = str(audit_payload.get("summary_text") or "").strip()
                why_now = str(audit_payload.get("why_now") or "").strip()
                actions = audit_payload.get("recommended_actions") if isinstance(audit_payload.get("recommended_actions"), list) else []
                if not summary_text:
                    issues.append("missing_summary")
                if not why_now:
                    issues.append("missing_why_now")
                if len(actions) == 0:
                    issues.append("missing_actions")
                if len(actions) > 3:
                    issues.append("too_many_actions")
                if issues:
                    quality_failures += 1

                conn.commit()
                processed += 1
                print(
                    json.dumps(
                        {
                            "lead_id": lead_id,
                            "name": str(display_lead.get("name") or ""),
                            "slug": slug,
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
                            "slug": slug,
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
