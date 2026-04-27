#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import time
from typing import Any

import psycopg2
from psycopg2.extras import Json
from psycopg2.extras import RealDictCursor

from api.admin_prospecting import _build_admin_lead_offer_payload
from api.admin_prospecting import _build_deterministic_dense_audit_enrichment
from api.admin_prospecting import _build_offer_slug
from api.admin_prospecting import _drop_mismatched_explicit_business_link
from api.admin_prospecting import _ensure_admin_prospecting_public_offers_table
from api.admin_prospecting import _normalize_lead_for_display
from api.admin_prospecting import _normalize_public_audit_languages
from api.admin_prospecting import _normalize_recommended_actions
from api.admin_prospecting import _resolve_outreach_language
from api.admin_prospecting import _sync_lead_business_link_from_parse_history
from api.admin_prospecting import _sync_lead_contacts_from_parsed_data
from api.admin_prospecting import _to_json_compatible
from core.card_audit import build_lead_card_preview_snapshot
from services.prospecting_service import ProspectingService


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
    preview_only_only: bool,
    lead_id: str | None,
) -> list[dict[str, Any]]:
    sql = """
        SELECT
            l.*,
            o.slug AS offer_slug,
            o.page_json AS offer_page_json,
            CASE
                WHEN l.search_payload_json->'menu_full' IS NULL
                 AND COALESCE(l.search_payload_json->>'services_total_count', '') = ''
                THEN TRUE
                ELSE FALSE
            END AS preview_only_30
        FROM prospectingleads l
        LEFT JOIN adminprospectingleadpublicoffers o
          ON o.lead_id = l.id
         AND o.is_active = TRUE
        WHERE l.services_json IS NOT NULL
          AND jsonb_typeof(l.services_json) = 'array'
          AND jsonb_array_length(l.services_json) = 30
          AND (%s IS NULL OR l.id = %s)
          AND (
                NOT %s
                OR (
                    l.search_payload_json->'menu_full' IS NULL
                    AND COALESCE(l.search_payload_json->>'services_total_count', '') = ''
                )
              )
        ORDER BY l.updated_at DESC NULLS LAST, l.created_at DESC, l.id DESC
    """
    normalized_lead_id = str(lead_id or "").strip() or None
    params: list[Any] = [normalized_lead_id, normalized_lead_id, preview_only_only]
    if limit and limit > 0:
        sql += " LIMIT %s"
        params.append(limit)
    cur.execute(sql, params)
    return [dict(row) for row in cur.fetchall() or []]


def _choose_languages(display_lead: dict[str, Any], existing_page_json: dict[str, Any] | None) -> tuple[str, list[str]]:
    explicit_language = str(display_lead.get("preferred_language") or "").strip().lower()
    requested_language = explicit_language
    requested_languages = None
    if isinstance(existing_page_json, dict) and not requested_language:
        requested_language = str(
            existing_page_json.get("primary_language")
            or existing_page_json.get("language")
            or ""
        ).strip().lower()
        requested_languages = existing_page_json.get("enabled_languages")
    if not requested_language:
        requested_language = _resolve_outreach_language(display_lead)
    if explicit_language:
        requested_languages = [explicit_language]
    return _normalize_public_audit_languages(requested_language, requested_languages)


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


def _pick_slug(existing_slug: str | None, display_lead: dict[str, Any]) -> str:
    if str(existing_slug or "").strip():
        return str(existing_slug).strip()
    return _build_offer_slug(
        str(display_lead.get("name") or "lead"),
        str(display_lead.get("city") or ""),
        str(display_lead.get("address") or ""),
    )


def _poll_run(service: ProspectingService, run_id: str, dataset_id: str, timeout_sec: int) -> str:
    started_at = dt.datetime.utcnow()
    status = "RUNNING"
    while status in {"READY", "RUNNING", "TIMING-OUT", "ABORTING"}:
        elapsed = (dt.datetime.utcnow() - started_at).total_seconds()
        if elapsed > max(30, int(timeout_sec or 300)):
            raise TimeoutError(f"Apify run did not finish within {int(timeout_sec or 300)} seconds")
        time.sleep(4)
        run_data = service.get_run(run_id)
        status = str(run_data.get("status") or "").strip().upper() or status
        dataset_id = str(run_data.get("defaultDatasetId") or dataset_id or "").strip()
    if status != "SUCCEEDED":
        raise RuntimeError(f"Apify run finished with status={status}")
    return dataset_id


def _fetch_map_business_without_identity_filter(service: ProspectingService, source_url: str, city: str) -> dict[str, Any] | None:
    run_input = service._build_run_input_for_map_url(source_url, limit=1, city=city)
    run_meta = service._start_run_with_input(service._strip_none_values(run_input))
    run_id = str(run_meta.get("run_id") or "").strip()
    dataset_id = str(run_meta.get("dataset_id") or "").strip()
    if not run_id:
        raise RuntimeError("Apify run did not start")
    dataset_id = _poll_run(service, run_id, dataset_id, timeout_sec=320)
    items = service.fetch_dataset_items(dataset_id)
    for item in items:
        if isinstance(item, dict):
            return item
    return None


def _refresh_preview_only_lead(cur, service: ProspectingService, lead: dict[str, Any]) -> bool:
    source_url = str(lead.get("source_url") or "").strip()
    if not source_url:
        raise RuntimeError("missing_source_url")
    city = str(lead.get("city") or "").strip()
    refreshed = _fetch_map_business_without_identity_filter(service, source_url, city)
    if not refreshed:
        raise RuntimeError("parser_returned_empty")

    current_name = str(lead.get("name") or "").strip()
    new_name = str(refreshed.get("name") or "").strip()
    if current_name and current_name.lower() not in {"новый партнёр", "партнёр", "компания"}:
        name_value = current_name
    else:
        name_value = new_name or current_name

    geo_payload = None
    if refreshed.get("geo_lat") is not None and refreshed.get("geo_lon") is not None:
        geo_payload = {"lat": refreshed.get("geo_lat"), "lon": refreshed.get("geo_lon")}

    cur.execute(
        """
        UPDATE prospectingleads
        SET name = %s,
            address = %s,
            city = %s,
            phone = %s,
            website = %s,
            email = %s,
            telegram_url = %s,
            whatsapp_url = %s,
            messenger_links_json = %s,
            rating = %s,
            reviews_count = %s,
            source_url = %s,
            source_external_id = %s,
            google_id = %s,
            category = %s,
            location = %s,
            search_payload_json = %s,
            photos_json = %s,
            services_json = %s,
            reviews_json = %s,
            raw_payload_json = %s,
            logo_url = %s,
            description = %s,
            updated_at = NOW()
        WHERE id = %s
        """,
        (
            name_value or None,
            refreshed.get("address"),
            refreshed.get("city") or lead.get("city"),
            refreshed.get("phone"),
            refreshed.get("website"),
            refreshed.get("email"),
            refreshed.get("telegram_url"),
            refreshed.get("whatsapp_url"),
            Json(refreshed.get("messenger_links") or []),
            refreshed.get("rating"),
            refreshed.get("reviews_count"),
            refreshed.get("source_url") or source_url,
            refreshed.get("source_external_id") or lead.get("source_external_id"),
            refreshed.get("google_id") or lead.get("google_id"),
            refreshed.get("category"),
            Json(geo_payload) if geo_payload is not None else None,
            Json(refreshed.get("search_payload_json") or {}),
            Json(refreshed.get("photos_json") or []),
            Json(refreshed.get("services_json") or []),
            Json(refreshed.get("reviews_json") or []),
            Json(refreshed.get("raw_payload_json") or {}),
            refreshed.get("logo_url"),
            refreshed.get("description"),
            str(lead["id"]),
        ),
    )
    return True


def _regenerate_offer_if_needed(cur, lead: dict[str, Any], user_id: str | None, create_missing_offers: bool) -> tuple[bool, str]:
    lead = _drop_mismatched_explicit_business_link(dict(lead))
    lead = _sync_lead_business_link_from_parse_history(dict(lead))
    lead = _sync_lead_contacts_from_parsed_data(dict(lead))
    display_lead = _normalize_lead_for_display(dict(lead))
    if not display_lead:
        raise RuntimeError("display_lead_unavailable")

    existing_page_json = lead.get("offer_page_json") if isinstance(lead.get("offer_page_json"), dict) else None
    has_offer = bool(str(lead.get("offer_slug") or "").strip())
    if not has_offer and not create_missing_offers:
        return False, ""

    primary_language, enabled_languages = _choose_languages(display_lead, existing_page_json)
    preview = build_lead_card_preview_snapshot(display_lead)
    page_json = _to_json_compatible(
        _build_admin_lead_offer_payload(
            lead=display_lead,
            preview=preview,
            preferred_language=primary_language,
            enabled_languages=enabled_languages,
        )
    )
    dense_audit = _build_deterministic_dense_audit_enrichment(display_lead, preview, primary_language)
    audit_payload = page_json.get("audit") if isinstance(page_json.get("audit"), dict) else {}
    if audit_payload:
        enriched_summary = str(dense_audit.get("summary_text") or "").strip()
        enriched_actions = _normalize_recommended_actions(dense_audit.get("recommended_actions"))
        why_now = str(dense_audit.get("why_now") or "").strip()
        if enriched_summary:
            audit_payload["summary_text"] = enriched_summary
        if enriched_actions:
            audit_payload["recommended_actions"] = enriched_actions
        if why_now:
            audit_payload["why_now"] = why_now
        audit_payload["ai_enrichment"] = dense_audit.get("meta") if isinstance(dense_audit.get("meta"), dict) else {}
        page_json["audit"] = audit_payload
    page_json["ai_enrichment"] = dense_audit.get("meta") if isinstance(dense_audit.get("meta"), dict) else {}

    slug = _pick_slug(str(lead.get("offer_slug") or "").strip() or None, display_lead)
    _upsert_offer(cur, str(display_lead["id"]), slug, page_json, user_id)
    return True, slug


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--create-missing-offers", action="store_true")
    parser.add_argument("--skip-reparse", action="store_true")
    parser.add_argument("--preview-only-only", action="store_true")
    parser.add_argument("--lead-id", type=str, default="")
    args = parser.parse_args()

    conn = _connect()
    try:
        _ensure_admin_prospecting_public_offers_table(conn)
        cur = conn.cursor()
        user_id = _pick_superadmin_user_id(cur)
        targets = _load_target_leads(
            cur,
            args.limit if args.limit > 0 else None,
            args.preview_only_only,
            args.lead_id,
        )
        service = ProspectingService(source="apify_yandex")

        stats = {
            "total": len(targets),
            "preview_only_targets": 0,
            "refreshed_preview_only": 0,
            "regenerated_offers": 0,
            "created_offers": 0,
            "skipped_without_offer": 0,
            "errors": 0,
        }
        errors: list[dict[str, Any]] = []

        for index, raw_lead in enumerate(targets, start=1):
            lead_id = str(raw_lead.get("id") or "")
            try:
                if bool(raw_lead.get("preview_only_30")):
                    stats["preview_only_targets"] += 1
                    if not args.skip_reparse:
                        _refresh_preview_only_lead(cur, service, raw_lead)
                        stats["refreshed_preview_only"] += 1
                        conn.commit()
                        cur.execute("SELECT l.*, o.slug AS offer_slug, o.page_json AS offer_page_json FROM prospectingleads l LEFT JOIN adminprospectingleadpublicoffers o ON o.lead_id = l.id AND o.is_active = TRUE WHERE l.id = %s", (lead_id,))
                        fresh_row = cur.fetchone()
                        raw_lead = dict(fresh_row) if fresh_row else raw_lead

                had_offer = bool(str(raw_lead.get("offer_slug") or "").strip())
                regenerated, slug = _regenerate_offer_if_needed(cur, raw_lead, user_id, args.create_missing_offers)
                if regenerated:
                    stats["regenerated_offers"] += 1
                    if not had_offer:
                        stats["created_offers"] += 1
                else:
                    stats["skipped_without_offer"] += 1
                conn.commit()
                print(
                    json.dumps(
                        {
                            "idx": index,
                            "lead_id": lead_id,
                            "name": str(raw_lead.get("name") or ""),
                            "preview_only_30": bool(raw_lead.get("preview_only_30")),
                            "offer_regenerated": regenerated,
                            "slug": slug,
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
            except Exception as exc:
                conn.rollback()
                stats["errors"] += 1
                error_row = {
                    "lead_id": lead_id,
                    "name": str(raw_lead.get("name") or ""),
                    "error": str(exc),
                }
                errors.append(error_row)
                print(json.dumps(error_row, ensure_ascii=False), flush=True)

        print(json.dumps({"stats": stats, "errors_sample": errors[:20]}, ensure_ascii=False), flush=True)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
