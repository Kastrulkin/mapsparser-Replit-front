#!/usr/bin/env python3
"""Research public contact routes for the strict SPb personal-author cohort."""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from psycopg2.extras import RealDictCursor

from database_manager import DatabaseManager
from enrich_creator_catalog_contacts import research_profile


def load_profiles(cursor: Any, limit: int) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT profile.id, profile.display_name, profile.description,
               commercial.preferred_contact,
               commercial.metadata_json->>'contact_source_url' AS contact_source_url,
               COALESCE(JSONB_AGG(JSONB_BUILD_OBJECT(
                   'id', channel.id,
                   'platform', channel.platform,
                   'canonical_url', channel.canonical_url,
                   'username', channel.username,
                   'metadata_json', channel.metadata_json
               ) ORDER BY channel.platform) FILTER (WHERE channel.id IS NOT NULL), '[]'::jsonb) AS channels_json
        FROM creator_profiles profile
        JOIN creator_profile_taxonomy taxonomy ON taxonomy.creator_profile_id = profile.id
        JOIN creator_channels channel
          ON channel.creator_profile_id = profile.id
         AND channel.verification_status = 'verified'
        LEFT JOIN creator_commercial_profiles commercial ON commercial.creator_profile_id = profile.id
        WHERE profile.metadata_json->>'import_source' = 'spb_active_people_core_20260827'
          AND profile.brand_safety_status <> 'blocked'
          AND profile.metadata_json#>>'{research,people_focus,profile_kind}' = 'personal_author'
          AND profile.metadata_json#>>'{research,people_focus,activity_level}' IN ('frequent', 'regular')
          AND taxonomy.audience_size_band IN ('nano', 'micro')
        GROUP BY profile.id, commercial.creator_profile_id,
                 commercial.preferred_contact, commercial.metadata_json
        ORDER BY
            CASE profile.metadata_json#>>'{research,people_focus,activity_level}'
                WHEN 'frequent' THEN 0 ELSE 1
            END,
            COALESCE(NULLIF(profile.metadata_json#>>'{research,people_focus,recent_visible_uploads}', '')::integer, 0) DESC,
            profile.id
        LIMIT %s
        """,
        (limit,),
    )
    return [dict(row) for row in cursor.fetchall()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument("--workers", type=int, default=48)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/strict-spb-creator-contact-research-20260901.json"),
    )
    arguments = parser.parse_args()
    database = DatabaseManager()
    cursor = database.conn.cursor(cursor_factory=RealDictCursor)
    try:
        profiles = load_profiles(cursor, max(1, min(arguments.limit, 5000)))
        results: list[dict[str, Any]] = []
        executor = ThreadPoolExecutor(max_workers=max(1, min(arguments.workers, 64)))
        try:
            futures = [executor.submit(research_profile, profile) for profile in profiles]
            for future in as_completed(futures):
                results.append(future.result())
        finally:
            executor.shutdown(wait=True)
        results.sort(key=lambda item: (item["state"], item["display_name"].lower()))
        summary = {
            "schema_version": "1.0",
            "status": "strict_spb_public_contact_research_no_messages_sent",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "profile_count": len(results),
            "with_route": sum(bool(item["preferred_contact"]) for item in results),
            "explicit_public_contact": sum(item["state"] == "public_explicit" for item in results),
            "manual_route_needs_confirmation": sum(item["state"] == "manual_route_needs_confirmation" for item in results),
            "no_public_route_found": sum(item["state"] == "no_public_route_found" for item in results),
            "results": results,
        }
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        database.conn.rollback()
        print(json.dumps({key: value for key, value in summary.items() if key != "results"}, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception:
        database.conn.rollback()
        raise
    finally:
        database.close()


if __name__ == "__main__":
    raise SystemExit(main())
