#!/usr/bin/env python3
import os
import uuid

import psycopg2
from psycopg2.extras import Json
from psycopg2.extras import RealDictCursor

from api.admin_prospecting import CHANNEL_SELECTED
from api.admin_prospecting import DRAFT_GENERATED
from api.admin_prospecting import _attach_admin_prospecting_public_offer_metadata
from api.admin_prospecting import _build_admin_lead_offer_payload
from api.admin_prospecting import _build_offer_slug
from api.admin_prospecting import _drop_mismatched_explicit_business_link
from api.admin_prospecting import _ensure_admin_prospecting_public_offers_table
from api.admin_prospecting import _generate_audit_first_message_draft
from api.admin_prospecting import _generate_lead_audit_enrichment
from api.admin_prospecting import _normalize_lead_for_display
from api.admin_prospecting import _normalize_public_audit_languages
from api.admin_prospecting import _normalize_recommended_actions
from api.admin_prospecting import _resolve_outreach_language
from api.admin_prospecting import _sync_lead_business_link_from_parse_history
from api.admin_prospecting import _sync_lead_contacts_from_parsed_data
from api.admin_prospecting import _to_json_compatible
from api.admin_prospecting import record_ai_learning_event
from core.card_audit import build_lead_card_preview_snapshot


def _connect():
    dsn = os.environ["DATABASE_URL"]
    return psycopg2.connect(dsn, cursor_factory=RealDictCursor)


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


def _load_first_ten(cur) -> list[dict]:
    cur.execute(
        """
        SELECT *
        FROM prospectingleads
        WHERE intent = %s
          AND status = %s
        ORDER BY updated_at DESC NULLS LAST, created_at DESC
        LIMIT 10
        """,
        ("client_outreach", CHANNEL_SELECTED),
    )
    return [dict(row) for row in cur.fetchall()]


def _load_existing_offer(cur, lead_id: str) -> dict | None:
    cur.execute(
        """
        SELECT lead_id, slug, page_json
        FROM adminprospectingleadpublicoffers
        WHERE lead_id = %s
        LIMIT 1
        """,
        (lead_id,),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def _choose_languages(display_lead: dict, existing_offer: dict | None) -> tuple[str, list[str]]:
    page_json = existing_offer.get("page_json") if existing_offer else None
    explicit_language = str(display_lead.get("preferred_language") or "").strip().lower()
    requested_language = explicit_language
    requested_languages = None
    if isinstance(page_json, dict) and not requested_language:
        requested_language = str(
            page_json.get("primary_language")
            or page_json.get("language")
            or ""
        ).strip().lower()
        requested_languages = page_json.get("enabled_languages")

    if not requested_language:
        requested_language = _resolve_outreach_language(display_lead)

    if explicit_language:
        requested_languages = [explicit_language]

    return _normalize_public_audit_languages(requested_language, requested_languages)


def _build_or_keep_slug(cur, display_lead: dict, lead_id: str, existing_offer: dict | None) -> str:
    if existing_offer and str(existing_offer.get("slug") or "").strip():
        return str(existing_offer["slug"]).strip()

    base_slug = _build_offer_slug(
        str(display_lead.get("name") or "lead"),
        str(display_lead.get("city") or ""),
        str(display_lead.get("address") or ""),
    )
    slug = base_slug
    suffix = 1
    while True:
        cur.execute(
            """
            SELECT lead_id
            FROM adminprospectingleadpublicoffers
            WHERE slug = %s
            LIMIT 1
            """,
            (slug,),
        )
        row = cur.fetchone()
        if not row:
            return slug
        if str(row.get("lead_id") or "") == lead_id:
            return slug
        suffix += 1
        slug = f"{base_slug}-{suffix}"


def _upsert_offer(cur, lead_id: str, slug: str, page_json: dict, created_by: str | None) -> None:
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


def _update_or_create_draft(
    cur,
    lead_id: str,
    channel: str,
    draft_payload: dict,
    created_by: str | None,
) -> str:
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
    row = cur.fetchone()
    learning_note = {
        "source": draft_payload.get("prompt_source") or "local_fallback",
        "prompt_key": draft_payload.get("prompt_key"),
        "prompt_version": draft_payload.get("prompt_version"),
    }
    if row and row.get("id"):
        draft_id = str(row["id"])
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
                channel,
                draft_payload["angle_type"],
                draft_payload["tone"],
                DRAFT_GENERATED,
                draft_payload["generated_text"],
                draft_payload["generated_text"],
                Json(learning_note),
                draft_id,
            ),
        )
        return draft_id

    draft_id = str(uuid.uuid4())
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
            draft_id,
            lead_id,
            channel,
            draft_payload["angle_type"],
            draft_payload["tone"],
            DRAFT_GENERATED,
            draft_payload["generated_text"],
            draft_payload["generated_text"],
            Json(learning_note),
            created_by,
        ),
    )
    return draft_id


def main() -> None:
    conn = _connect()
    try:
        _ensure_admin_prospecting_public_offers_table(conn)
        cur = conn.cursor()
        user_id = _pick_superadmin_user_id(cur)
        leads = _load_first_ten(cur)
        results: list[dict] = []

        for raw_lead in leads:
            lead = _drop_mismatched_explicit_business_link(dict(raw_lead))
            lead = _sync_lead_business_link_from_parse_history(dict(lead))
            lead = _sync_lead_contacts_from_parsed_data(dict(lead))
            display_lead = _normalize_lead_for_display(dict(lead))
            if not display_lead:
                results.append(
                    {
                        "lead_id": str(raw_lead.get("id") or ""),
                        "name": str(raw_lead.get("name") or ""),
                        "error": "display_lead_unavailable",
                    }
                )
                continue

            existing_offer = _load_existing_offer(cur, str(display_lead["id"]))
            primary_language, enabled_languages = _choose_languages(display_lead, existing_offer)

            preview = build_lead_card_preview_snapshot(display_lead)
            page_json = _to_json_compatible(
                _build_admin_lead_offer_payload(
                    lead=display_lead,
                    preview=preview,
                    preferred_language=primary_language,
                    enabled_languages=enabled_languages,
                )
            )
            ai_enrichment = _generate_lead_audit_enrichment(display_lead, preview, primary_language)
            audit_payload = page_json.get("audit") if isinstance(page_json.get("audit"), dict) else {}
            if audit_payload:
                enriched_summary = str(ai_enrichment.get("summary_text") or "").strip()
                enriched_actions = _normalize_recommended_actions(ai_enrichment.get("recommended_actions"))
                why_now = str(ai_enrichment.get("why_now") or "").strip()
                if enriched_summary:
                    audit_payload["summary_text"] = enriched_summary
                if enriched_actions:
                    audit_payload["recommended_actions"] = enriched_actions
                if why_now:
                    audit_payload["why_now"] = why_now
                audit_payload["ai_enrichment"] = ai_enrichment.get("meta") if isinstance(ai_enrichment.get("meta"), dict) else {}
                page_json["audit"] = audit_payload
            page_json["ai_enrichment"] = ai_enrichment.get("meta") if isinstance(ai_enrichment.get("meta"), dict) else {}

            slug = _build_or_keep_slug(cur, display_lead, str(display_lead["id"]), existing_offer)
            _upsert_offer(cur, str(display_lead["id"]), slug, page_json, user_id)
            display_lead = _attach_admin_prospecting_public_offer_metadata(conn, display_lead)

            channel = str(display_lead.get("selected_channel") or "email").strip().lower() or "email"
            draft_payload = _generate_audit_first_message_draft(display_lead, preview, channel)
            draft_id = _update_or_create_draft(cur, str(display_lead["id"]), channel, draft_payload, user_id)

            record_ai_learning_event(
                capability="lead.audit_enrichment",
                event_type="generated",
                intent="client_outreach",
                user_id=user_id,
                prompt_key=str(ai_enrichment.get("meta", {}).get("prompt_key") or ""),
                prompt_version=str(ai_enrichment.get("meta", {}).get("prompt_version") or ""),
                final_text=str(page_json.get("audit", {}).get("summary_text") or "")[:3000],
                metadata={
                    "lead_id": str(display_lead["id"]),
                    "source": ai_enrichment.get("meta", {}).get("source"),
                    "slug": slug,
                },
                conn=conn,
            )
            record_ai_learning_event(
                capability="outreach.draft_first_message",
                event_type="generated",
                intent="client_outreach",
                user_id=user_id,
                prompt_key=str(draft_payload.get("prompt_key") or ""),
                prompt_version=str(draft_payload.get("prompt_version") or ""),
                final_text=str(draft_payload.get("generated_text") or "")[:3000],
                metadata={
                    "lead_id": str(display_lead["id"]),
                    "draft_id": draft_id,
                    "channel": channel,
                    "source": draft_payload.get("prompt_source"),
                },
                conn=conn,
            )

            revenue = page_json.get("audit", {}).get("revenue_potential") if isinstance(page_json.get("audit"), dict) else {}
            total_min = revenue.get("total_min") if isinstance(revenue, dict) else None
            total_max = revenue.get("total_max") if isinstance(revenue, dict) else None
            results.append(
                {
                    "lead_id": str(display_lead["id"]),
                    "name": str(display_lead.get("name") or ""),
                    "slug": slug,
                    "public_audit_url": str(display_lead.get("public_audit_url") or ""),
                    "audit_source": ai_enrichment.get("meta", {}).get("source"),
                    "draft_source": draft_payload.get("prompt_source"),
                    "revenue_total_min": total_min,
                    "revenue_total_max": total_max,
                    "draft_id": draft_id,
                    "draft_preview": str(draft_payload.get("generated_text") or "")[:220],
                }
            )

        conn.commit()
        for item in results:
            print(item)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
