#!/usr/bin/env python3
import os
from typing import Any

import psycopg2
from psycopg2.extras import Json
from psycopg2.extras import RealDictCursor

from api.admin_prospecting import _attach_admin_prospecting_public_offer_metadata
from api.admin_prospecting import _build_admin_lead_offer_payload
from api.admin_prospecting import _build_offer_slug
from api.admin_prospecting import _drop_mismatched_explicit_business_link
from api.admin_prospecting import _ensure_admin_prospecting_public_offers_table
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


def _load_in_work_leads(cur) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT *
        FROM prospectingleads
        WHERE intent = %s
          AND status IN (%s, %s)
        ORDER BY updated_at DESC NULLS LAST, created_at DESC
        """,
        ("client_outreach", "channel_selected", "selected_for_outreach"),
    )
    return [dict(row) for row in cur.fetchall()]


def _load_existing_offer(cur, lead_id: str) -> dict[str, Any] | None:
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


def _choose_languages(display_lead: dict[str, Any], existing_offer: dict[str, Any] | None) -> tuple[str, list[str]]:
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


def _ensure_slug(cur, display_lead: dict[str, Any], lead_id: str, existing_offer: dict[str, Any] | None) -> str:
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
        _ensure_admin_prospecting_public_offers_table(conn)
        cur = conn.cursor()
        user_id = _pick_superadmin_user_id(cur)
        leads = _load_in_work_leads(cur)
        results: list[dict[str, Any]] = []

        for raw_lead in leads:
            try:
                lead = _drop_mismatched_explicit_business_link(dict(raw_lead))
                lead = _sync_lead_business_link_from_parse_history(dict(lead))
                lead = _sync_lead_contacts_from_parsed_data(dict(lead))
                display_lead = _normalize_lead_for_display(dict(lead))
                if not display_lead:
                    result = {
                        "lead_id": str(raw_lead.get("id") or ""),
                        "name": str(raw_lead.get("name") or ""),
                        "error": "display_lead_unavailable",
                    }
                    results.append(result)
                    print(result, flush=True)
                    conn.commit()
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

                slug = _ensure_slug(cur, display_lead, str(display_lead["id"]), existing_offer)
                _upsert_offer(cur, str(display_lead["id"]), slug, page_json, user_id)
                display_lead = _attach_admin_prospecting_public_offer_metadata(conn, display_lead)

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

                revenue = page_json.get("audit", {}).get("revenue_potential") if isinstance(page_json.get("audit"), dict) else {}
                result = {
                    "lead_id": str(display_lead["id"]),
                    "name": str(display_lead.get("name") or ""),
                    "slug": slug,
                    "public_audit_url": str(display_lead.get("public_audit_url") or ""),
                    "audit_source": ai_enrichment.get("meta", {}).get("source"),
                    "revenue_total_min": revenue.get("total_min") if isinstance(revenue, dict) else None,
                    "revenue_total_max": revenue.get("total_max") if isinstance(revenue, dict) else None,
                }
                results.append(result)
                conn.commit()
                print(result, flush=True)
            except Exception as exc:
                conn.rollback()
                result = {
                    "lead_id": str(raw_lead.get("id") or ""),
                    "name": str(raw_lead.get("name") or ""),
                    "error": str(exc),
                }
                results.append(result)
                print(result, flush=True)
        print({"total": len(leads), "processed": len(results)})
        for item in results:
            print(item)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
