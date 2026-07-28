#!/usr/bin/env python3
"""Geocode canonical company locations from their public postal addresses.

Preview is the default and performs no network calls. ``--lookup`` runs a
read-only canary. ``--apply`` requires an explicit production approval gate.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from database_manager import DatabaseManager
from services.company_geocoding_service import (
    NOMINATIM_ATTRIBUTION,
    NominatimGeocoder,
    build_geocoding_queries,
    choose_candidate,
)


DEFAULT_CACHE_PATH = ROOT / "data" / "geocoding" / "company_registry_nominatim_cache.json"


def _missing_locations(cursor, limit: int) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT location.id, location.company_id, company.canonical_name,
               location.address, location.city, location.region, location.country
        FROM company_locations location
        JOIN companies company ON company.id = location.company_id
        WHERE company.status IN ('observed', 'active')
          AND location.status = 'active'
          AND location.latitude IS NULL
          AND location.longitude IS NULL
          AND NULLIF(BTRIM(location.address), '') IS NOT NULL
        ORDER BY location.created_at, location.id
        LIMIT %s
        """,
        (limit,),
    )
    return [dict(row) for row in cursor.fetchall()]


def _mapped_count(cursor) -> int:
    cursor.execute(
        """
        SELECT COUNT(DISTINCT company.id) AS value
        FROM companies company
        JOIN company_locations location ON location.company_id = company.id
        WHERE company.status IN ('observed', 'active')
          AND location.status = 'active'
          AND location.latitude IS NOT NULL
          AND location.longitude IS NOT NULL
        """
    )
    row = cursor.fetchone() or {}
    return int(row.get("value") or 0)


def _update_location(cursor, location: dict[str, Any], query: str, result: dict[str, Any]) -> bool:
    observed_at = datetime.now(timezone.utc).isoformat()
    metadata = {
        "coordinates_source": "nominatim_openstreetmap",
        "coordinates_attribution": NOMINATIM_ATTRIBUTION,
        "coordinates_observed_at": observed_at,
        "geocoding_query": query,
        "geocoding_formatted_address": result["formatted_address"],
        "geocoding_confidence": result["confidence"],
        "geocoding_confidence_reasons": result["confidence_reasons"],
        "geocoding_address_type": result["address_type"],
        "geocoding_osm_type": result["osm_type"],
        "geocoding_osm_id": result["osm_id"],
    }
    cursor.execute(
        """
        UPDATE company_locations
        SET latitude = %s,
            longitude = %s,
            metadata_json = COALESCE(metadata_json, '{}'::jsonb) || %s::jsonb,
            updated_at = NOW()
        WHERE id = %s
          AND latitude IS NULL
          AND longitude IS NULL
        """,
        (
            result["latitude"],
            result["longitude"],
            json.dumps(metadata, ensure_ascii=False),
            location["id"],
        ),
    )
    return cursor.rowcount == 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lookup", action="store_true", help="perform read-only provider lookups")
    parser.add_argument("--apply", action="store_true", help="persist accepted coordinates")
    parser.add_argument("--limit", type=int, default=100000)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE_PATH)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--minimum-confidence", type=float, default=0.75)
    args = parser.parse_args()
    if args.apply and os.getenv("COMPANY_REGISTRY_GEOCODING_APPROVED") != "true":
        print(json.dumps({
            "status": "blocked",
            "reason": "set COMPANY_REGISTRY_GEOCODING_APPROVED=true after production backup",
        }, ensure_ascii=False))
        return 2

    network_enabled = args.lookup or args.apply
    safe_limit = max(1, min(args.limit, 200000))
    db = DatabaseManager()
    cursor = db.conn.cursor()
    report: dict[str, Any] = {
        "mode": "apply" if args.apply else "lookup" if args.lookup else "preview",
        "provider": "nominatim_openstreetmap",
        "attribution": NOMINATIM_ATTRIBUTION,
        "mapped_before": 0,
        "locations_checked": 0,
        "unique_queries": 0,
        "provider_requests": 0,
        "cache_hits": 0,
        "accepted": 0,
        "updated_locations": 0,
        "not_found_or_ambiguous": 0,
        "errors": [],
        "samples": [],
    }
    geocoder = NominatimGeocoder(args.cache) if network_enabled else None
    try:
        report["mapped_before"] = _mapped_count(cursor)
        locations = _missing_locations(cursor, safe_limit)
        report["locations_checked"] = len(locations)
        query_results: dict[tuple[str, str], dict[str, Any] | None] = {}
        provider_queries: set[str] = set()
        for location in locations:
            queries = build_geocoding_queries(location)
            if not queries:
                continue
            expected_city = str(location.get("city") or "")
            query = queries[0]
            result = None
            for candidate_query in queries:
                result_key = (candidate_query, expected_city)
                if result_key not in query_results:
                    if not geocoder:
                        query_results[result_key] = None
                        continue
                    try:
                        candidates, from_cache = geocoder.lookup(candidate_query)
                        provider_queries.add(candidate_query)
                        report["cache_hits" if from_cache else "provider_requests"] += 1
                        query_results[result_key] = choose_candidate(
                            candidate_query,
                            expected_city,
                            candidates,
                            minimum_confidence=max(0.0, min(args.minimum_confidence, 1.0)),
                        )
                    except Exception as exc:
                        query_results[result_key] = None
                        report["errors"].append({"query": candidate_query, "error": str(exc)})
                result = query_results[result_key]
                if result is not None:
                    query = candidate_query
                    break
            if not network_enabled:
                continue
            if result is None:
                report["not_found_or_ambiguous"] += 1
                if len(report["samples"]) < 20:
                    report["samples"].append({
                        "company": location["canonical_name"],
                        "query": query,
                        "status": "skipped",
                    })
                continue
            report["accepted"] += 1
            if len(report["samples"]) < 20:
                report["samples"].append({
                    "company": location["canonical_name"],
                    "query": query,
                    "status": "accepted",
                    "confidence": result["confidence"],
                    "formatted_address": result["formatted_address"],
                })
            if args.apply and _update_location(cursor, location, query, result):
                report["updated_locations"] += 1
                db.conn.commit()

        report["unique_queries"] = len(provider_queries) if network_enabled else len(query_results)
        report["mapped_after"] = _mapped_count(cursor) if args.apply else report["mapped_before"]
        if not args.apply:
            db.conn.rollback()
        output = json.dumps(report, ensure_ascii=False, default=str, indent=2)
        print(output)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(output + "\n", encoding="utf-8")
        return 0 if not report["errors"] else 1
    finally:
        cursor.close()
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
