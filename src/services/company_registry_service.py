from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from psycopg2.extras import Json, RealDictCursor


ROLE_LABELS = {
    "client": "Клиент",
    "localos_lead": "Лид LocalOS",
    "partner": "Партнёр",
    "competitor": "Конкурент",
    "observed": "Без роли",
}


def sync_company_registry_for_lead(conn, lead_id: str, lead: dict[str, Any] | None = None, *, source: str = "lead_intake") -> dict[str, str] | None:
    enabled = str(os.getenv("COMPANY_REGISTRY_ENABLED", "false")).strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return None
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'prospectingleads' AND column_name = 'company_id'
        """
    )
    available = bool(cursor.fetchone())
    if not available:
        cursor.close()
        return None
    payload = dict(lead or {})
    if not payload:
        cursor.execute("SELECT * FROM prospectingleads WHERE id = %s", (lead_id,))
        row = cursor.fetchone()
        payload = dict(row) if row else {}
    cursor.close()
    if not payload:
        return None
    return ensure_company_for_lead(conn, lead_id, payload, source=source)


def normalize_url(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"https://{raw}"
    parsed = urlsplit(raw)
    host = (parsed.hostname or "").lower()
    path = re.sub(r"/+$", "", parsed.path or "")
    return urlunsplit((parsed.scheme.lower() or "https", host, path, "", ""))


def normalize_identity_url(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"https://{raw}"
    parsed = urlsplit(raw)
    host = (parsed.hostname or "").lower()
    path = re.sub(r"/+$", "", parsed.path or "")
    query = "&".join(sorted(part for part in (parsed.query or "").split("&") if part))
    return urlunsplit((parsed.scheme.lower() or "https", host, path, query, ""))


def normalize_phone(value: Any) -> str:
    digits = re.sub(r"\D+", "", str(value or ""))
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    return digits


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _coordinate_value(value: Any, *, latitude: bool) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        number = float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None
    lower, upper = (-90.0, 90.0) if latitude else (-180.0, 180.0)
    return number if lower <= number <= upper else None


def resolve_company_coordinates(payload: dict[str, Any] | None) -> tuple[float | None, float | None]:
    """Read coordinates from canonical, legacy and parser payload shapes."""
    source = payload if isinstance(payload, dict) else {}
    candidates: list[dict[str, Any]] = [source]
    for key in ("geo", "location", "coordinates", "geometry"):
        nested = source.get(key)
        if isinstance(nested, dict):
            candidates.append(nested)
            nested_location = nested.get("location")
            if isinstance(nested_location, dict):
                candidates.append(nested_location)
    for key in ("raw_payload_json", "search_payload_json", "enrich_payload_json"):
        nested = source.get(key)
        if isinstance(nested, dict):
            candidates.append(nested)
            for nested_key in ("geo", "location", "coordinates", "geometry"):
                nested_value = nested.get(nested_key)
                if isinstance(nested_value, dict):
                    candidates.append(nested_value)
                    nested_location = nested_value.get("location")
                    if isinstance(nested_location, dict):
                        candidates.append(nested_location)
    latitude_keys = ("latitude", "lat", "geo_lat", "geoLat")
    longitude_keys = ("longitude", "lon", "lng", "geo_lon", "geoLon")
    for candidate in candidates:
        latitude_value = next((candidate.get(key) for key in latitude_keys if candidate.get(key) not in (None, "")), None)
        longitude_value = next((candidate.get(key) for key in longitude_keys if candidate.get(key) not in (None, "")), None)
        resolved_latitude = _coordinate_value(latitude_value, latitude=True)
        resolved_longitude = _coordinate_value(longitude_value, latitude=False)
        if resolved_latitude is not None and resolved_longitude is not None:
            return resolved_latitude, resolved_longitude
    return None, None


def _sync_location_coordinates(
    cursor,
    *,
    location_id: str,
    latitude: float | None,
    longitude: float | None,
    source: str,
) -> None:
    if not location_id or latitude is None or longitude is None:
        return
    cursor.execute(
        """
        UPDATE company_locations
        SET latitude = COALESCE(latitude, %s),
            longitude = COALESCE(longitude, %s),
            metadata_json = COALESCE(metadata_json, '{}'::jsonb) || jsonb_build_object(
                'coordinates_source', %s,
                'coordinates_synced_at', NOW()
            ),
            updated_at = NOW()
        WHERE id = %s
          AND (latitude IS NULL OR longitude IS NULL)
        """,
        (latitude, longitude, source, location_id),
    )


def _roles(row: dict[str, Any]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for key in ("client", "localos_lead", "partner", "competitor"):
        if row.get(f"is_{key}"):
            result.append({"key": key, "label": ROLE_LABELS[key]})
    if not result:
        result.append({"key": "observed", "label": ROLE_LABELS["observed"]})
    return result


def _accessible_business_sql() -> str:
    return """
        SELECT b.id
        FROM businesses b
        LEFT JOIN networks n ON n.id = b.network_id
        WHERE b.owner_id = %(user_id)s OR n.owner_id = %(user_id)s
    """


def _access_sql(is_superadmin: bool) -> str:
    if is_superadmin:
        return "TRUE"
    return f"""
        (
            EXISTS (
                SELECT 1 FROM business_company_links access_link
                WHERE access_link.company_id = c.id
                  AND access_link.business_id IN ({_accessible_business_sql()})
            )
            OR EXISTS (
                SELECT 1
                FROM prospectingleads access_lead
                JOIN lead_workstreams access_ws ON access_ws.lead_id = access_lead.id
                WHERE access_lead.company_id = c.id
                  AND access_ws.client_business_id IN ({_accessible_business_sql()})
            )
            OR EXISTS (
                SELECT 1 FROM company_relationships access_rel
                WHERE (access_rel.subject_company_id = c.id OR access_rel.object_company_id = c.id)
                  AND access_rel.context_business_id IN ({_accessible_business_sql()})
            )
        )
    """


def list_companies(
    conn,
    *,
    user_id: str,
    is_superadmin: bool,
    search: str = "",
    role: str = "",
    category: str = "",
    city: str = "",
    status: str = "",
    cursor_value: int = 0,
    limit: int = 30,
) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit), 100))
    offset = max(0, int(cursor_value))
    filters = [_access_sql(is_superadmin)]
    params: dict[str, Any] = {"user_id": user_id, "limit": safe_limit + 1, "offset": offset}
    query = normalize_text(search)
    if query:
        filters.append(
            """
            (
                LOWER(c.canonical_name) LIKE %(query)s
                OR EXISTS (SELECT 1 FROM company_locations ql WHERE ql.company_id = c.id AND LOWER(COALESCE(ql.address, '') || ' ' || COALESCE(ql.city, '')) LIKE %(query)s)
                OR EXISTS (SELECT 1 FROM company_contact_points qc WHERE qc.company_id = c.id AND LOWER(qc.value) LIKE %(query)s AND qc.invalidated_at IS NULL)
                OR EXISTS (SELECT 1 FROM company_external_profiles qp JOIN company_locations qpl ON qpl.id = qp.company_location_id WHERE qpl.company_id = c.id AND LOWER(COALESCE(qp.canonical_url, '')) LIKE %(query)s)
            )
            """
        )
        params["query"] = f"%{query}%"
    if city:
        filters.append("EXISTS (SELECT 1 FROM company_locations cl_city WHERE cl_city.company_id = c.id AND LOWER(COALESCE(cl_city.city, '')) = %(city)s)")
        params["city"] = normalize_text(city)
    if status:
        filters.append("c.status = %(status)s")
        params["status"] = status
    else:
        filters.append("c.status IN ('observed', 'active')")
    role_filter = str(role or "").strip().lower()
    role_sql = {
        "client": "EXISTS (SELECT 1 FROM business_company_links rf WHERE rf.company_id = c.id)",
        "localos_lead": "EXISTS (SELECT 1 FROM prospectingleads rl JOIN lead_workstreams rw ON rw.lead_id = rl.id WHERE rl.company_id = c.id AND rw.workstream_type = 'localos_sales')",
        "partner": "EXISTS (SELECT 1 FROM prospectingleads rl JOIN lead_workstreams rw ON rw.lead_id = rl.id WHERE rl.company_id = c.id AND rw.workstream_type = 'client_partnership')",
        "competitor": "EXISTS (SELECT 1 FROM company_relationships rr WHERE (rr.subject_company_id = c.id OR rr.object_company_id = c.id) AND rr.relationship_type = 'competitor')",
        "unassigned": "NOT EXISTS (SELECT 1 FROM business_company_links rf WHERE rf.company_id = c.id) AND NOT EXISTS (SELECT 1 FROM prospectingleads rl WHERE rl.company_id = c.id)",
    }.get(role_filter)
    if role_sql:
        filters.append(role_sql)
    if category:
        filters.append("LOWER(COALESCE(c.primary_category, '')) = %(category)s")
        params["category"] = normalize_text(category)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        f"""
        SELECT c.id, c.canonical_name AS name, c.primary_category, c.status,
               c.first_seen_source, c.created_at, c.updated_at,
               loc.id AS primary_location_id, loc.address, loc.city, loc.country,
               (SELECT COUNT(*) FROM company_locations lc WHERE lc.company_id = c.id AND lc.status = 'active') AS locations_count,
               EXISTS (SELECT 1 FROM business_company_links bl WHERE bl.company_id = c.id) AS is_client,
               EXISTS (SELECT 1 FROM prospectingleads ll JOIN lead_workstreams lw ON lw.lead_id = ll.id WHERE ll.company_id = c.id AND lw.workstream_type = 'localos_sales') AS is_localos_lead,
               EXISTS (SELECT 1 FROM prospectingleads pl JOIN lead_workstreams pw ON pw.lead_id = pl.id WHERE pl.company_id = c.id AND pw.workstream_type = 'client_partnership') AS is_partner,
               EXISTS (SELECT 1 FROM company_relationships cr WHERE (cr.subject_company_id = c.id OR cr.object_company_id = c.id) AND cr.relationship_type = 'competitor') AS is_competitor,
               profile.last_collected_at,
               profile.provider AS freshest_provider
        FROM companies c
        LEFT JOIN LATERAL (
            SELECT * FROM company_locations l
            WHERE l.company_id = c.id AND l.status = 'active'
            ORDER BY l.is_primary DESC, l.created_at ASC LIMIT 1
        ) loc ON TRUE
        LEFT JOIN LATERAL (
            SELECT p.provider, p.last_collected_at
            FROM company_external_profiles p
            JOIN company_locations pl ON pl.id = p.company_location_id
            WHERE pl.company_id = c.id AND p.status = 'active'
            ORDER BY p.last_collected_at DESC NULLS LAST LIMIT 1
        ) profile ON TRUE
        WHERE {' AND '.join(filters)}
        ORDER BY c.updated_at DESC, c.id
        LIMIT %(limit)s OFFSET %(offset)s
        """,
        params,
    )
    rows = [dict(row) for row in cursor.fetchall()]
    cursor.close()
    has_more = len(rows) > safe_limit
    rows = rows[:safe_limit]
    now = datetime.now(timezone.utc)
    for row in rows:
        row["roles"] = _roles(row)
        collected = row.get("last_collected_at")
        age_days = (now - collected).days if collected else None
        row["freshness"] = {
            "status": "fresh" if age_days is not None and age_days <= 7 else "stale" if collected else "missing",
            "updated_at": collected,
            "source": row.get("freshest_provider"),
        }
        completeness = sum(bool(row.get(key)) for key in ("name", "address", "city", "freshest_provider"))
        row["data_quality"] = int(completeness / 4 * 100)
        row["next_action"] = {
            "key": "refresh_maps" if not collected or (age_days is not None and age_days > 7) else "open_company",
            "label": "Обновить данные карт" if not collected or (age_days is not None and age_days > 7) else "Открыть компанию",
        }
    return {"items": rows, "cursor": str(offset + safe_limit) if has_more else None, "as_of": now.isoformat()}


def list_company_map_points(
    conn,
    *,
    user_id: str,
    is_superadmin: bool,
    search: str = "",
    role: str = "",
    category: str = "",
    status: str = "",
    limit: int = 5000,
    include_points: bool = True,
) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit), 5000))
    base_filters = [_access_sql(is_superadmin)]
    params: dict[str, Any] = {"user_id": user_id, "limit": safe_limit}
    query = normalize_text(search)
    if query:
        base_filters.append(
            """
            (
                LOWER(c.canonical_name) LIKE %(query)s
                OR EXISTS (
                    SELECT 1 FROM company_locations ql
                    WHERE ql.company_id = c.id
                      AND LOWER(COALESCE(ql.address, '') || ' ' || COALESCE(ql.city, '')) LIKE %(query)s
                )
            )
            """
        )
        params["query"] = f"%{query}%"
    if status:
        base_filters.append("c.status = %(status)s")
    else:
        base_filters.append("c.status IN ('observed', 'active')")
    role_filter = str(role or "").strip().lower()
    role_sql = {
        "client": "EXISTS (SELECT 1 FROM business_company_links rf WHERE rf.company_id = c.id)",
        "localos_lead": "EXISTS (SELECT 1 FROM prospectingleads rl JOIN lead_workstreams rw ON rw.lead_id = rl.id WHERE rl.company_id = c.id AND rw.workstream_type = 'localos_sales')",
        "partner": "EXISTS (SELECT 1 FROM prospectingleads rl JOIN lead_workstreams rw ON rw.lead_id = rl.id WHERE rl.company_id = c.id AND rw.workstream_type = 'client_partnership')",
        "competitor": "EXISTS (SELECT 1 FROM company_relationships rr WHERE (rr.subject_company_id = c.id OR rr.object_company_id = c.id) AND rr.relationship_type = 'competitor')",
        "unassigned": "NOT EXISTS (SELECT 1 FROM business_company_links rf WHERE rf.company_id = c.id) AND NOT EXISTS (SELECT 1 FROM prospectingleads rl WHERE rl.company_id = c.id)",
    }.get(role_filter)
    if role_sql:
        base_filters.append(role_sql)

    selected_filters = list(base_filters)
    if category:
        selected_filters.append("LOWER(COALESCE(c.primary_category, '')) = %(category)s")
        params["category"] = normalize_text(category)

    client_sql = "EXISTS (SELECT 1 FROM business_company_links bl WHERE bl.company_id = c.id)"
    lead_sql = "EXISTS (SELECT 1 FROM prospectingleads ll JOIN lead_workstreams lw ON lw.lead_id = ll.id WHERE ll.company_id = c.id AND lw.workstream_type = 'localos_sales')"
    partner_sql = "EXISTS (SELECT 1 FROM prospectingleads pl JOIN lead_workstreams pw ON pw.lead_id = pl.id WHERE pl.company_id = c.id AND pw.workstream_type = 'client_partnership')"
    competitor_sql = "EXISTS (SELECT 1 FROM company_relationships cr WHERE (cr.subject_company_id = c.id OR cr.object_company_id = c.id) AND cr.relationship_type = 'competitor')"
    mapped_sql = "EXISTS (SELECT 1 FROM company_locations ml WHERE ml.company_id = c.id AND ml.status = 'active' AND ml.latitude IS NOT NULL AND ml.longitude IS NOT NULL)"

    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        f"""
        SELECT COUNT(*) AS matching_count,
               COUNT(*) FILTER (WHERE {mapped_sql}) AS mapped_count,
               COUNT(*) FILTER (WHERE {client_sql}) AS client_count,
               COUNT(*) FILTER (WHERE {lead_sql}) AS lead_count,
               COUNT(*) FILTER (WHERE {partner_sql}) AS partner_count,
               COUNT(*) FILTER (WHERE {competitor_sql}) AS competitor_count
        FROM companies c
        WHERE {' AND '.join(selected_filters)}
        """,
        params,
    )
    counts = dict(cursor.fetchone() or {})
    rows: list[dict[str, Any]] = []
    if include_points:
        cursor.execute(
            f"""
            SELECT c.id, c.canonical_name AS name, c.primary_category, c.status,
                   loc.id AS primary_location_id, loc.address, loc.city,
                   loc.latitude, loc.longitude,
                   {client_sql} AS is_client,
                   {lead_sql} AS is_localos_lead,
                   {partner_sql} AS is_partner,
                   {competitor_sql} AS is_competitor
            FROM companies c
            JOIN LATERAL (
                SELECT l.id, l.address, l.city, l.latitude, l.longitude
                FROM company_locations l
                WHERE l.company_id = c.id
                  AND l.status = 'active'
                  AND l.latitude IS NOT NULL
                  AND l.longitude IS NOT NULL
                ORDER BY l.is_primary DESC, l.created_at ASC
                LIMIT 1
            ) loc ON TRUE
            WHERE {' AND '.join(selected_filters)}
            ORDER BY c.canonical_name, c.id
            LIMIT %(limit)s
            """,
            params,
        )
        rows = [dict(row) for row in cursor.fetchall()]
    cursor.execute(
        f"""
        SELECT c.primary_category AS value, COUNT(*) AS count
        FROM companies c
        WHERE {' AND '.join(base_filters)}
          AND NULLIF(TRIM(c.primary_category), '') IS NOT NULL
        GROUP BY c.primary_category
        ORDER BY COUNT(*) DESC, c.primary_category
        LIMIT 200
        """,
        params,
    )
    categories = [dict(row) for row in cursor.fetchall()]
    cursor.close()

    for row in rows:
        row["roles"] = _roles(row)
        row["latitude"] = float(row["latitude"])
        row["longitude"] = float(row["longitude"])

    mapped_count = int(counts.get("mapped_count") or 0)
    role_counts = {
        "client": int(counts.get("client_count") or 0),
        "localos_lead": int(counts.get("lead_count") or 0),
        "partner": int(counts.get("partner_count") or 0),
        "competitor": int(counts.get("competitor_count") or 0),
    }
    return {
        "items": rows,
        "counts": {
            "matching": int(counts.get("matching_count") or 0),
            "mapped": mapped_count,
            "without_coordinates": max(0, int(counts.get("matching_count") or 0) - mapped_count),
            "roles": role_counts,
        },
        "filters": {
            "categories": [
                {"value": str(item.get("value") or ""), "label": str(item.get("value") or ""), "count": int(item.get("count") or 0)}
                for item in categories
                if item.get("value")
            ]
        },
        "truncated": mapped_count > safe_limit,
        "as_of": datetime.now(timezone.utc).isoformat(),
    }


def get_company_detail(conn, *, company_id: str, user_id: str, is_superadmin: bool) -> dict[str, Any] | None:
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        f"""
        SELECT c.*,
               EXISTS (SELECT 1 FROM business_company_links bl WHERE bl.company_id = c.id) AS is_client,
               EXISTS (SELECT 1 FROM prospectingleads ll JOIN lead_workstreams lw ON lw.lead_id = ll.id WHERE ll.company_id = c.id AND lw.workstream_type = 'localos_sales') AS is_localos_lead,
               EXISTS (SELECT 1 FROM prospectingleads pl JOIN lead_workstreams pw ON pw.lead_id = pl.id WHERE pl.company_id = c.id AND pw.workstream_type = 'client_partnership') AS is_partner,
               EXISTS (SELECT 1 FROM company_relationships cr WHERE (cr.subject_company_id = c.id OR cr.object_company_id = c.id) AND cr.relationship_type = 'competitor') AS is_competitor
        FROM companies c
        WHERE c.id = %(company_id)s AND {_access_sql(is_superadmin)}
        """,
        {"company_id": company_id, "user_id": user_id},
    )
    company_row = cursor.fetchone()
    if not company_row:
        cursor.close()
        return None
    company = dict(company_row)
    if company.get("status") == "merged" and company.get("merged_into_company_id"):
        cursor.close()
        return get_company_detail(conn, company_id=str(company["merged_into_company_id"]), user_id=user_id, is_superadmin=is_superadmin)
    cursor.execute("SELECT * FROM company_locations WHERE company_id = %s ORDER BY is_primary DESC, created_at", (company_id,))
    locations = [dict(row) for row in cursor.fetchall()]
    location_ids = [row["id"] for row in locations]
    profiles: list[dict[str, Any]] = []
    public_services: list[dict[str, Any]] = []
    if location_ids:
        cursor.execute("SELECT * FROM company_external_profiles WHERE company_location_id = ANY(%s::uuid[]) ORDER BY last_collected_at DESC NULLS LAST", (location_ids,))
        profiles = [dict(row) for row in cursor.fetchall()]
        cursor.execute(
            """
            SELECT * FROM company_public_services
            WHERE company_location_id = ANY(%s::uuid[]) AND invalidated_at IS NULL
            ORDER BY observed_at DESC, name
            LIMIT 500
            """,
            (location_ids,),
        )
        public_services = [dict(row) for row in cursor.fetchall()]
    cursor.execute("SELECT * FROM company_contact_points WHERE company_id = %s AND invalidated_at IS NULL ORDER BY verification_status DESC, observed_at DESC", (company_id,))
    contacts = [dict(row) for row in cursor.fetchall()]
    cursor.execute("SELECT * FROM company_observations WHERE company_id = %s AND invalidated_at IS NULL ORDER BY observed_at DESC LIMIT 100", (company_id,))
    observations = [dict(row) for row in cursor.fetchall()]
    cursor.execute(
        """
        SELECT link.*, source.title, source.canonical_url, source.source_role, source.last_collected_at
        FROM company_social_source_links link
        JOIN knowledge_sources source ON source.id = link.source_id
        WHERE link.company_id = %s ORDER BY link.verification_status DESC, source.title
        """,
        (company_id,),
    )
    social_sources = [dict(row) for row in cursor.fetchall()]
    cursor.execute(
        """
        SELECT rel.*, subject.canonical_name AS subject_name, object.canonical_name AS object_name
        FROM company_relationships rel
        JOIN companies subject ON subject.id = rel.subject_company_id
        JOIN companies object ON object.id = rel.object_company_id
        WHERE rel.subject_company_id = %s OR rel.object_company_id = %s
        ORDER BY rel.updated_at DESC
        """,
        (company_id, company_id),
    )
    relationships = [dict(row) for row in cursor.fetchall()]
    cursor.execute(
        """
        SELECT ('lead-audit:' || audit.lead_id) AS id, 'public_audit' AS kind,
               audit.edit_status AS status, audit.slug, NULL::text AS public_url,
               audit.audit_context, audit.context_business_id, audit.updated_at
        FROM adminprospectingleadpublicoffers audit
        LEFT JOIN prospectingleads lead ON lead.id = audit.lead_id
        WHERE COALESCE(audit.company_id, lead.company_id) = %s
        UNION ALL
        SELECT audit.id::text AS id, 'sales_room_audit' AS kind,
               audit.status, audit.prepared_audit_slug AS slug, audit.prepared_audit_url AS public_url,
               audit.audit_context, audit.context_business_id, audit.updated_at
        FROM sales_room_audit_offers audit
        LEFT JOIN prospectingleads lead ON lead.id = audit.lead_id
        WHERE COALESCE(audit.company_id, lead.company_id) = %s
        ORDER BY updated_at DESC
        LIMIT 100
        """,
        (company_id, company_id),
    )
    audits = [dict(row) for row in cursor.fetchall()]
    cursor.execute(
        """
        SELECT * FROM (
            SELECT observation.id::text AS id, 'observation' AS event_type,
                   observation.predicate AS title, observation.source_type AS source,
                   observation.observed_at AS occurred_at, observation.status,
                   observation.value_json AS payload
            FROM company_observations observation
            WHERE observation.company_id = %s
            UNION ALL
            SELECT queue.id::text AS id, 'map_refresh' AS event_type,
                   'Обновление данных карт' AS title, queue.source,
                   queue.updated_at AS occurred_at, queue.status,
                   JSONB_BUILD_OBJECT('url', queue.url, 'error', queue.error_message) AS payload
            FROM parsequeue queue
            JOIN company_locations location ON location.id = queue.company_location_id
            WHERE location.company_id = %s
            UNION ALL
            SELECT merge.id::text AS id, 'merge' AS event_type,
                   'Объединение компаний' AS title, 'company_registry' AS source,
                   COALESCE(merge.confirmed_at, merge.created_at) AS occurred_at, merge.status,
                   merge.result_json AS payload
            FROM company_merge_events merge
            WHERE merge.source_company_id = %s OR merge.target_company_id = %s
        ) timeline_event
        ORDER BY occurred_at DESC
        LIMIT 100
        """,
        (company_id, company_id, company_id, company_id),
    )
    timeline = [dict(row) for row in cursor.fetchall()]
    cursor.close()
    company["name"] = company.get("canonical_name")
    company["roles"] = _roles(company)
    latest = max((p.get("last_collected_at") for p in profiles if p.get("last_collected_at")), default=None)
    return {
        "company": company,
        "locations": locations,
        "external_profiles": profiles,
        "public_services": public_services,
        "contacts": contacts,
        "social_sources": social_sources,
        "observations": observations,
        "relationships": relationships,
        "audits": audits,
        "timeline": timeline,
        "freshness": {"updated_at": latest, "status": "fresh" if latest and latest >= datetime.now(timezone.utc) - timedelta(days=7) else "stale" if latest else "missing"},
        "data_warnings": [] if locations else ["У компании пока нет подтверждённой локации"],
        "available_actions": ["open_company"] + (["refresh_maps", "merge"] if is_superadmin else ["refresh_maps"]),
        "access": {"can_edit_identity": is_superadmin, "can_merge": is_superadmin, "can_refresh": True},
    }


def ensure_company_for_business(conn, business: dict[str, Any], *, source: str = "business_backfill") -> dict[str, str]:
    business_id = str(business.get("id") or "").strip()
    if not business_id:
        raise ValueError("business_id_required")
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        """
        SELECT c.id AS company_id, l.company_location_id
        FROM business_company_links l JOIN companies c ON c.id = l.company_id
        WHERE l.business_id = %s ORDER BY l.is_primary DESC LIMIT 1
        """,
        (business_id,),
    )
    existing = cursor.fetchone()
    if existing:
        latitude, longitude = resolve_company_coordinates(business)
        _sync_location_coordinates(
            cursor,
            location_id=str(existing.get("company_location_id") or ""),
            latitude=latitude,
            longitude=longitude,
            source=source,
        )
        cursor.close()
        return {"company_id": str(existing["company_id"]), "company_location_id": str(existing.get("company_location_id") or "")}
    cursor.execute("SELECT url, map_type FROM businessmaplinks WHERE business_id = %s AND COALESCE(BTRIM(url), '') <> '' ORDER BY created_at", (business_id,))
    map_links = [dict(row) for row in cursor.fetchall()]
    address = normalize_text(business.get("address"))
    city = normalize_text(business.get("city"))
    phone = normalize_phone(business.get("phone"))
    website = normalize_url(business.get("site") or business.get("website"))
    identities: list[tuple[str, str, float]] = [("map_url", normalize_identity_url(item.get("url")), 1.0) for item in map_links if normalize_identity_url(item.get("url"))]
    if phone and address:
        identities.append(("phone_address", f"{phone}|{address}", 0.99))
    if website and city:
        identities.append(("domain_geo", f"{urlsplit(website).hostname or ''}|{city}", 0.98))

    company_id = ""
    location_id = ""
    latitude, longitude = resolve_company_coordinates(business)
    for key_type, value, _confidence in identities:
        cursor.execute(
            """
            SELECT key.company_id, COALESCE(key.company_location_id, location.id) AS company_location_id
            FROM company_identity_keys key
            LEFT JOIN LATERAL (
                SELECT id FROM company_locations WHERE company_id = key.company_id AND status = 'active'
                ORDER BY is_primary DESC, created_at LIMIT 1
            ) location ON TRUE
            JOIN companies company ON company.id = key.company_id AND company.status IN ('observed', 'active')
            WHERE key.key_type = %s AND key.normalized_value = %s AND key.verification_status = 'verified'
            ORDER BY key.confidence DESC LIMIT 1
            """,
            (key_type, value),
        )
        match = cursor.fetchone()
        if match:
            company_id = str(match["company_id"])
            location_id = str(match.get("company_location_id") or "")
            cursor.execute("UPDATE companies SET status = 'active', updated_at = NOW() WHERE id = %s", (company_id,))
            break
    if not company_id:
        company_id = str(uuid.uuid4())
        location_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO companies (id, canonical_name, primary_category, status, first_seen_source, metadata_json)
            VALUES (%s, %s, %s, 'active', %s, %s)
            """,
            (company_id, str(business.get("name") or "Компания"), business.get("industry") or business.get("business_type"), source, Json({"legacy_business_id": business_id})),
        )
        cursor.execute(
            """
            INSERT INTO company_locations (id, company_id, display_name, address, city, country, latitude, longitude, timezone, is_primary)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
            """,
            (location_id, company_id, business.get("name"), business.get("address"), business.get("city"), business.get("country"), latitude, longitude, business.get("timezone")),
        )
    elif not location_id:
        location_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO company_locations (
                id, company_id, display_name, address, city, country,
                latitude, longitude, timezone, is_primary
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s,
                NOT EXISTS (SELECT 1 FROM company_locations WHERE company_id = %s AND status = 'active')
            )
            """,
            (
                location_id, company_id, business.get("name"), business.get("address"),
                business.get("city"), business.get("country"), latitude,
                longitude, business.get("timezone"), company_id,
            ),
        )
    else:
        _sync_location_coordinates(
            cursor,
            location_id=location_id,
            latitude=latitude,
            longitude=longitude,
            source=source,
        )
    cursor.execute(
        """
        INSERT INTO business_company_links (business_id, company_id, company_location_id, relation_role, is_primary)
        VALUES (%s, %s, %s, 'owner', TRUE)
        """,
        (business_id, company_id, location_id),
    )
    for key_type, value, confidence in identities:
        cursor.execute(
            """
            INSERT INTO company_identity_keys (company_id, company_location_id, key_type, normalized_value, confidence, verification_status)
            SELECT %s, %s, %s, %s, %s,
                   CASE WHEN EXISTS (
                       SELECT 1 FROM company_identity_keys conflict
                       WHERE conflict.key_type = %s AND conflict.normalized_value = %s
                         AND conflict.verification_status = 'verified' AND conflict.company_id <> %s
                   ) THEN 'observed' ELSE 'verified' END
            WHERE NOT EXISTS (
                SELECT 1 FROM company_identity_keys WHERE company_id = %s AND key_type = %s AND normalized_value = %s
            )
            """,
            (company_id, location_id, key_type, value, confidence, key_type, value, company_id, company_id, key_type, value),
        )
    for map_link in map_links:
        provider = normalize_text(map_link.get("map_type") or "maps").replace(" ", "_")
        canonical_url = normalize_identity_url(map_link.get("url"))
        cursor.execute(
            """
            INSERT INTO company_external_profiles (company_location_id, provider, canonical_url, status, sync_status)
            VALUES (%s, %s, %s, 'active', 'idle')
            ON CONFLICT DO NOTHING
            """,
            (location_id, provider, canonical_url),
        )
    for contact_type, field in (("phone", "phone"), ("email", "email"), ("website", "site")):
        value = business.get(field) or (business.get("website") if contact_type == "website" else None)
        normalized = normalize_phone(value) if contact_type == "phone" else normalize_url(value) if contact_type == "website" else normalize_text(value)
        if normalized:
            cursor.execute(
                """
                INSERT INTO company_contact_points (company_id, company_location_id, contact_type, value, normalized_value, confidence, verification_status)
                SELECT %s, %s, %s, %s, %s, 1, 'verified'
                WHERE NOT EXISTS (
                    SELECT 1 FROM company_contact_points
                    WHERE company_id = %s AND contact_type = %s AND normalized_value = %s AND invalidated_at IS NULL
                )
                """,
                (company_id, location_id, contact_type, str(value), normalized, company_id, contact_type, normalized),
            )
    cursor.close()
    return {"company_id": company_id, "company_location_id": location_id}


def ensure_company_for_lead(
    conn,
    lead_id: str,
    lead: dict[str, Any],
    *,
    source: str = "lead_intake",
    link_lead: bool = True,
) -> dict[str, str]:
    """Resolve only strong identities; a name by itself never merges companies."""
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    if link_lead:
        cursor.execute("SELECT company_id, company_location_id FROM prospectingleads WHERE id = %s", (lead_id,))
        linked = cursor.fetchone()
        if linked and linked.get("company_id"):
            latitude, longitude = resolve_company_coordinates(lead)
            _sync_location_coordinates(
                cursor,
                location_id=str(linked.get("company_location_id") or ""),
                latitude=latitude,
                longitude=longitude,
                source=source,
            )
            cursor.close()
            return {"company_id": str(linked["company_id"]), "company_location_id": str(linked.get("company_location_id") or "")}

    address = normalize_text(lead.get("address"))
    city = normalize_text(lead.get("city"))
    phone = normalize_phone(lead.get("phone"))
    website = normalize_url(lead.get("website"))
    source_url = normalize_identity_url(lead.get("source_url"))
    external_id = str(
        lead.get("external_source_id")
        or lead.get("source_external_id")
        or lead.get("google_id")
        or ""
    ).strip().lower()
    provider = normalize_text(lead.get("source") or "unknown").replace(" ", "_")
    authoritative_identity_candidates: list[tuple[str, str, float]] = []
    if external_id:
        authoritative_identity_candidates.append((f"provider_id:{provider}", external_id, 1.0))
    if source_url:
        authoritative_identity_candidates.append(("map_url", source_url, 1.0))
    weak_identity_candidates: list[tuple[str, str, float]] = []
    if phone and address:
        weak_identity_candidates.append(("phone_address", f"{phone}|{address}", 0.99))
    if website and city:
        weak_identity_candidates.append(("domain_geo", f"{urlsplit(website).hostname or ''}|{city}", 0.98))
    identity_candidates = authoritative_identity_candidates + weak_identity_candidates
    resolution_candidates = authoritative_identity_candidates or weak_identity_candidates

    company_id = ""
    location_id = ""
    latitude, longitude = resolve_company_coordinates(lead)
    for key_type, value, _confidence in resolution_candidates:
        cursor.execute(
            """
            SELECT key.company_id, COALESCE(key.company_location_id, location.id) AS company_location_id
            FROM company_identity_keys key
            LEFT JOIN LATERAL (
                SELECT id FROM company_locations
                WHERE company_id = key.company_id AND status = 'active'
                ORDER BY is_primary DESC, created_at LIMIT 1
            ) location ON TRUE
            JOIN companies company ON company.id = key.company_id AND company.status IN ('observed', 'active')
            WHERE key.key_type = %s AND key.normalized_value = %s
              AND key.verification_status = 'verified'
            ORDER BY key.confidence DESC LIMIT 1
            """,
            (key_type, value),
        )
        match = cursor.fetchone()
        if match:
            company_id = str(match["company_id"])
            location_id = str(match.get("company_location_id") or "")
            break

    if not company_id:
        company_id = str(uuid.uuid4())
        location_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO companies (id, canonical_name, primary_category, status, first_seen_source, metadata_json)
            VALUES (%s, %s, %s, 'observed', %s, %s)
            """,
            (
                company_id,
                str(lead.get("name") or "Компания"),
                lead.get("category"),
                source,
                Json({"first_lead_id": lead_id} if link_lead else {"first_observation_id": lead_id}),
            ),
        )
        cursor.execute(
            """
            INSERT INTO company_locations (id, company_id, display_name, address, city, latitude, longitude, is_primary)
            VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
            """,
            (location_id, company_id, lead.get("name"), lead.get("address"), lead.get("city"), latitude, longitude),
        )
    elif not location_id:
        location_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO company_locations (id, company_id, display_name, address, city, is_primary)
            VALUES (%s, %s, %s, %s, %s, NOT EXISTS (SELECT 1 FROM company_locations WHERE company_id = %s))
            """,
            (location_id, company_id, lead.get("name"), lead.get("address"), lead.get("city"), company_id),
        )
    else:
        _sync_location_coordinates(
            cursor,
            location_id=location_id,
            latitude=latitude,
            longitude=longitude,
            source=source,
        )

    for key_type, value, confidence in identity_candidates:
        cursor.execute(
            """
            INSERT INTO company_identity_keys (
                company_id, company_location_id, key_type, normalized_value, confidence, verification_status, source_url
            ) SELECT %s, %s, %s, %s, %s,
                     CASE WHEN EXISTS (
                         SELECT 1 FROM company_identity_keys conflict
                         WHERE conflict.key_type = %s AND conflict.normalized_value = %s
                           AND conflict.verification_status = 'verified' AND conflict.company_id <> %s
                     ) THEN 'observed' ELSE 'verified' END,
                     %s
            WHERE NOT EXISTS (
                SELECT 1 FROM company_identity_keys
                WHERE key_type = %s AND normalized_value = %s AND company_id = %s
            )
            """,
            (
                company_id, location_id, key_type, value, confidence,
                key_type, value, company_id, lead.get("source_url"),
                key_type, value, company_id,
            ),
        )
    if source_url:
        cursor.execute(
            """
            INSERT INTO company_external_profiles (
                company_location_id, provider, external_id, canonical_url, status, sync_status
            ) VALUES (%s, %s, %s, %s, 'active', 'idle')
            ON CONFLICT DO NOTHING
            """,
            (location_id, provider, external_id or None, source_url),
        )
    if link_lead:
        cursor.execute(
            "UPDATE prospectingleads SET company_id = %s, company_location_id = %s, updated_at = NOW() WHERE id = %s",
            (company_id, location_id, lead_id),
        )
    cursor.close()
    return {"company_id": company_id, "company_location_id": location_id}


def observe_company_candidate(conn, candidate: dict[str, Any], *, source: str = "company_discovery") -> dict[str, str]:
    observation_id = str(candidate.get("observation_id") or candidate.get("source_external_id") or candidate.get("source_url") or uuid.uuid4())
    return ensure_company_for_lead(conn, observation_id, candidate, source=source, link_lead=False)
