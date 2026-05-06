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
from core.public_audit_editor import apply_editor_blocks_to_page_json
from core.public_audit_editor import normalize_editor_blocks
from core.public_audit_editor import normalize_public_audit_page_json
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


def _load_target_leads(
    cur,
    limit: int | None,
    lead_id: str | None,
    group_id: str | None,
    group_name: str | None,
) -> list[dict[str, Any]]:
    sql = """
        SELECT
            l.*,
            o.slug AS offer_slug,
            o.page_json AS offer_page_json,
            o.generated_json AS offer_generated_json,
            o.edited_json AS offer_edited_json,
            o.published_json AS offer_published_json,
            o.edit_status AS offer_edit_status,
            o.business_id AS offer_business_id,
            o.business_profile AS offer_business_profile,
            o.source_type AS offer_source_type,
            o.published_by AS offer_published_by,
            o.published_at AS offer_published_at
        FROM adminprospectingleadpublicoffers o
        JOIN prospectingleads l
          ON l.id = o.lead_id
        LEFT JOIN lead_group_items gi
          ON gi.lead_id = l.id
        LEFT JOIN lead_groups g
          ON g.id = gi.group_id
        WHERE o.is_active = TRUE
          AND (%s IS NULL OR l.id = %s)
          AND (%s IS NULL OR g.id = %s)
          AND (%s IS NULL OR LOWER(g.name) LIKE %s)
        ORDER BY o.updated_at DESC NULLS LAST, l.updated_at DESC NULLS LAST, l.created_at DESC
    """
    normalized_lead_id = str(lead_id or "").strip() or None
    normalized_group_id = str(group_id or "").strip() or None
    normalized_group_name = str(group_name or "").strip().lower() or None
    group_name_pattern = f"%{normalized_group_name}%" if normalized_group_name else None
    params: list[Any] = [
        normalized_lead_id,
        normalized_lead_id,
        normalized_group_id,
        normalized_group_id,
        normalized_group_name,
        group_name_pattern,
    ]
    if limit and limit > 0:
        sql += " LIMIT %s"
        params.append(limit)
    cur.execute(sql, params)
    return [dict(row) for row in cur.fetchall() or []]


def _choose_languages(display_lead: dict[str, Any], existing_offer: dict[str, Any] | None) -> tuple[str, list[str]]:
    page_json = existing_offer.get("offer_page_json") if existing_offer else None
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


def _ensure_slug(cur, display_lead: dict[str, Any], lead_id: str, existing_slug: str | None) -> str:
    if str(existing_slug or "").strip():
        return str(existing_slug).strip()

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


def _build_published_layers(
    page_json: dict[str, Any],
    existing_offer: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str, str | None, Any]:
    generated_json = copy.deepcopy(page_json)
    edited_json = existing_offer.get("offer_edited_json") if isinstance(existing_offer.get("offer_edited_json"), dict) else None
    existing_status = str(existing_offer.get("offer_edit_status") or "").strip() or "generated"
    published_by = existing_offer.get("offer_published_by")
    published_at = existing_offer.get("offer_published_at")
    next_published_json = copy.deepcopy(generated_json)
    next_page_json = copy.deepcopy(generated_json)
    next_status = "generated"
    if edited_json:
        editor_blocks = normalize_editor_blocks(edited_json.get("blocks"))
        if existing_status == "published":
            next_published_json = apply_editor_blocks_to_page_json(generated_json, editor_blocks)
            next_page_json = copy.deepcopy(next_published_json)
            next_status = "published"
        else:
            existing_published_json = existing_offer.get("offer_published_json")
            if isinstance(existing_published_json, dict) and existing_published_json:
                next_published_json = normalize_public_audit_page_json(existing_published_json)
                next_page_json = copy.deepcopy(next_published_json)
            next_status = "draft_edited"
    return generated_json, next_page_json, next_published_json, next_status, published_by, published_at


def _upsert_offer(
    cur,
    lead_id: str,
    slug: str,
    page_json: dict[str, Any],
    created_by: str | None,
    existing_offer: dict[str, Any],
) -> None:
    generated_json, next_page_json, next_published_json, next_status, published_by, published_at = _build_published_layers(page_json, existing_offer)
    audit_payload = generated_json.get("audit") if isinstance(generated_json.get("audit"), dict) else {}
    business_profile = str(audit_payload.get("audit_profile") or existing_offer.get("offer_business_profile") or "").strip() or None
    business_id = str(existing_offer.get("offer_business_id") or "").strip() or None
    source_type = str(existing_offer.get("offer_source_type") or "admin_prospecting_public_audit").strip() or "admin_prospecting_public_audit"
    cur.execute(
        """
        INSERT INTO adminprospectingleadpublicoffers (
            lead_id, business_id, business_profile, source_type,
            slug, page_json, generated_json, edited_json, published_json,
            edit_status, is_active, created_by, published_by, published_at, created_at, updated_at
        ) VALUES (%s, NULLIF(%s, '')::uuid, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, NULLIF(%s, '')::uuid, NULLIF(%s, '')::uuid, %s, NOW(), NOW())
        ON CONFLICT (lead_id) DO UPDATE
        SET slug = EXCLUDED.slug,
            page_json = EXCLUDED.page_json,
            business_id = EXCLUDED.business_id,
            business_profile = EXCLUDED.business_profile,
            source_type = EXCLUDED.source_type,
            generated_json = EXCLUDED.generated_json,
            edited_json = COALESCE(adminprospectingleadpublicoffers.edited_json, EXCLUDED.edited_json),
            published_json = EXCLUDED.published_json,
            edit_status = EXCLUDED.edit_status,
            is_active = TRUE,
            published_by = EXCLUDED.published_by,
            published_at = EXCLUDED.published_at,
            updated_at = NOW()
        """,
        (
            lead_id,
            business_id or "",
            business_profile,
            source_type,
            slug,
            Json(next_page_json),
            Json(generated_json),
            Json(existing_offer.get("offer_edited_json")) if isinstance(existing_offer.get("offer_edited_json"), dict) else None,
            Json(next_published_json),
            next_status,
            created_by or "",
            str(published_by or created_by or ""),
            published_at,
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--lead-id", type=str, default="")
    parser.add_argument("--group-id", type=str, default="")
    parser.add_argument("--group-name", type=str, default="")
    parser.add_argument("--skip-ai-enrichment", action="store_true")
    args = parser.parse_args()

    conn = _connect()
    try:
        _ensure_admin_prospecting_public_offers_table(conn)
        cur = conn.cursor()
        user_id = _pick_superadmin_user_id(cur)
        leads = _load_target_leads(
            cur,
            args.limit if args.limit > 0 else None,
            args.lead_id,
            args.group_id,
            args.group_name,
        )
        print(json.dumps({"total": len(leads)}, ensure_ascii=False), flush=True)

        processed = 0
        errors = 0
        for raw_lead in leads:
            lead_id = str(raw_lead.get("id") or "")
            try:
                lead = _drop_mismatched_explicit_business_link(dict(raw_lead))
                lead = _sync_lead_business_link_from_parse_history(dict(lead))
                lead = _sync_lead_contacts_from_parsed_data(dict(lead))
                display_lead = _normalize_lead_for_display(dict(lead))
                if not display_lead:
                    raise ValueError("display_lead_unavailable")

                primary_language, enabled_languages = _choose_languages(display_lead, raw_lead)
                preview = build_lead_card_preview_snapshot(display_lead)
                page_json = _to_json_compatible(
                    _build_admin_lead_offer_payload(
                        lead=display_lead,
                        preview=preview,
                        preferred_language=primary_language,
                        enabled_languages=enabled_languages,
                    )
                )

                ai_enrichment: dict[str, Any] = {}
                audit_payload = page_json.get("audit") if isinstance(page_json.get("audit"), dict) else {}
                if not args.skip_ai_enrichment:
                    ai_enrichment = _generate_lead_audit_enrichment(display_lead, preview, primary_language)
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

                page_json = normalize_public_audit_page_json(page_json)
                slug = _ensure_slug(cur, display_lead, lead_id, str(raw_lead.get("offer_slug") or "").strip() or None)
                _upsert_offer(cur, lead_id, slug, page_json, user_id, raw_lead)
                display_lead = _attach_admin_prospecting_public_offer_metadata(conn, display_lead)
                conn.commit()
                processed += 1
                print(
                    json.dumps(
                        {
                            "lead_id": lead_id,
                            "name": str(display_lead.get("name") or ""),
                            "slug": slug,
                            "public_audit_url": str(display_lead.get("public_audit_url") or ""),
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

        print(json.dumps({"processed": processed, "errors": errors}, ensure_ascii=False), flush=True)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
