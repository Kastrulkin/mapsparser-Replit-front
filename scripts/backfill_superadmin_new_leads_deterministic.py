#!/usr/bin/env python3
import json
import os
import uuid
from typing import Any

import psycopg2
from psycopg2.extras import Json
from psycopg2.extras import RealDictCursor

from api.admin_prospecting import DRAFT_GENERATED
from api.admin_prospecting import _attach_admin_prospecting_public_offer_metadata
from api.admin_prospecting import _build_admin_lead_offer_payload
from api.admin_prospecting import _build_deterministic_dense_audit_enrichment
from api.admin_prospecting import _build_offer_slug
from api.admin_prospecting import _drop_mismatched_explicit_business_link
from api.admin_prospecting import _generate_superadmin_deterministic_first_message
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


def _canonicalize_superadmin_scope(cur) -> dict[str, int]:
    cur.execute(
        """
        UPDATE prospectingleads
        SET intent = 'client_outreach',
            business_id = NULL,
            updated_at = NOW()
        WHERE COALESCE(intent, 'client_outreach') IN ('client_outreach', 'partnership_outreach')
          AND (
              COALESCE(intent, 'client_outreach') = 'partnership_outreach'
              OR business_id IS NOT NULL
          )
        RETURNING id
        """
    )
    updated = cur.fetchall() or []
    return {"canonicalized_count": len(updated)}


def _load_target_leads(cur) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT *
        FROM prospectingleads
        WHERE COALESCE(intent, 'client_outreach') = 'client_outreach'
          AND COALESCE(status, '') = 'new'
        ORDER BY created_at DESC NULLS LAST, updated_at DESC NULLS LAST, id DESC
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
        canonical = _canonicalize_superadmin_scope(cur)
        conn.commit()
        leads = _load_target_leads(cur)
        print(json.dumps({"canonicalized": canonical["canonicalized_count"], "target_total": len(leads)}, ensure_ascii=False), flush=True)

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
                lead["intent"] = "client_outreach"
                lead["business_id"] = None

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

                cur.execute(
                    "SELECT slug FROM adminprospectingleadpublicoffers WHERE lead_id = %s LIMIT 1",
                    (lead_id,),
                )
                existing_offer = cur.fetchone()
                slug = (
                    str(existing_offer["slug"]).strip()
                    if existing_offer and existing_offer.get("slug")
                    else _build_offer_slug(
                        str(display_lead.get("name") or "lead"),
                        str(display_lead.get("city") or ""),
                        str(display_lead.get("address") or ""),
                    )
                )

                _upsert_offer(cur, lead_id, slug, page_json, user_id)
                cur.execute(
                    """
                    UPDATE prospectingleads
                    SET intent = 'client_outreach',
                        business_id = NULL,
                        status = 'selected_for_outreach',
                        preferred_language = 'ru',
                        enabled_languages = '["ru"]'::jsonb,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (lead_id,),
                )

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
                learning_note = {
                    "source": draft_payload.get("prompt_source") or "deterministic",
                    "prompt_key": draft_payload.get("prompt_key"),
                    "prompt_version": draft_payload.get("prompt_version"),
                }
                if existing_draft and existing_draft.get("id"):
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
                else:
                    cur.execute(
                        """
                        INSERT INTO outreachmessagedrafts (
                            id, lead_id, channel, angle_type, tone, status,
                            generated_text, edited_text, learning_note_json, created_by
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                        """,
                        (
                            str(uuid.uuid4()),
                            lead_id,
                            "email",
                            draft_payload["angle_type"],
                            draft_payload["tone"],
                            DRAFT_GENERATED,
                            draft_payload["generated_text"],
                            draft_payload["generated_text"],
                            Json(learning_note),
                            user_id,
                        ),
                    )

                issues: list[str] = []
                if not str(enriched_lead.get("public_audit_url") or "").strip():
                    issues.append("missing_public_audit_url")
                if not str(page_json.get("audit", {}).get("summary_text") or "").strip():
                    issues.append("missing_summary")
                if len(page_json.get("audit", {}).get("recommended_actions") or []) == 0:
                    issues.append("missing_actions")
                draft_text = str(draft_payload.get("generated_text") or "").strip()
                if "https://localos.pro/" not in draft_text:
                    issues.append("missing_audit_link_in_draft")
                if "+30-80%" not in draft_text:
                    issues.append("missing_growth_hint")
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
