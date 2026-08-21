#!/usr/bin/env python3
import argparse
import copy
import json
import uuid
from datetime import datetime, timezone

from psycopg2 import sql
from psycopg2.extras import Json, RealDictCursor

from pg_db_utils import get_db_connection


POINT_LEAD_ID = "c2e6f5d5-1dd0-4dd3-9cdc-d0e67603a8cf"
NETWORK_LEAD_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, "localos:prospecting-lead:extra-spa-network-audit"))
NETWORK_ID = "e22f911c-6ed8-5313-b1f5-8081df5f5649"
NETWORK_SLUG = "extra-spa-network-saint-petersburg"
NETWORK_PUBLIC_URL = f"https://localos.pro/{NETWORK_SLUG}"


JSON_FIELDS = {"page_json", "generated_json", "edited_json", "published_json"}
LEAD_JSON_FIELDS = {
    "messenger_links_json",
    "location",
    "search_payload_json",
    "enrich_payload_json",
    "matched_sources_json",
    "photos_json",
    "services_json",
    "reviews_json",
    "raw_payload_json",
    "enabled_languages",
}
BOOLEAN_FIELDS = {"is_active"}


def _restore_value(field, value):
    if field in JSON_FIELDS and value is not None:
        return Json(value)
    if field in BOOLEAN_FIELDS and isinstance(value, str):
        return value.lower() in {"t", "true", "1"}
    return value


def _network_page(page):
    result = copy.deepcopy(page or {})
    result["slug"] = NETWORK_SLUG
    result["public_url"] = NETWORK_PUBLIC_URL
    result["lead_id"] = NETWORK_LEAD_ID
    audit = result.get("audit") if isinstance(result.get("audit"), dict) else {}
    audit["lead_id"] = NETWORK_LEAD_ID
    audit["audit_slug"] = NETWORK_SLUG
    result["audit"] = audit
    signup = result.get("signup_context") if isinstance(result.get("signup_context"), dict) else {}
    signup["lead_id"] = NETWORK_LEAD_ID
    result["signup_context"] = signup
    return result


def _clone_network_lead(cursor):
    cursor.execute("SELECT * FROM prospectingleads WHERE id = %s", (POINT_LEAD_ID,))
    source = cursor.fetchone()
    if not source:
        raise RuntimeError("Extra СПА point lead not found")
    clone = dict(source)
    clone.update(
        {
            "id": NETWORK_LEAD_ID,
            "name": "Extra СПА — сеть",
            "address": "Санкт-Петербург, 6 филиалов",
            "source_url": "https://экстраспа.рф/",
            "source_external_id": "extra-spa-network-saint-petersburg",
            "google_id": None,
            "external_place_id": None,
            "external_source_id": None,
            "dedupe_key": "network:extra-spa:saint-petersburg",
            "lat": None,
            "lon": None,
            "business_id": NETWORK_ID,
            "parse_business_id": NETWORK_ID,
            "company_location_id": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    )
    columns = list(clone.keys())
    values = [
        Json(clone[column]) if column in LEAD_JSON_FIELDS and clone[column] is not None else clone[column]
        for column in columns
    ]
    assignments = [
        sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(column), sql.Identifier(column))
        for column in columns
        if column not in {"id", "created_at", "updated_at"}
    ]
    cursor.execute(
        sql.SQL(
            "INSERT INTO prospectingleads ({columns}) VALUES ({values}) "
            "ON CONFLICT (id) DO UPDATE SET {assignments}, updated_at = NOW()"
        ).format(
            columns=sql.SQL(", ").join(sql.Identifier(column) for column in columns),
            values=sql.SQL(", ").join(sql.Placeholder() for _ in columns),
            assignments=sql.SQL(", ").join(assignments),
        ),
        values,
    )


def apply(restore_path):
    with open(restore_path, "r", encoding="utf-8") as source:
        point_backup = json.load(source)
    if point_backup.get("lead_id") != POINT_LEAD_ID:
        raise RuntimeError("Point audit backup belongs to another lead")

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            "SELECT * FROM adminprospectingleadpublicoffers WHERE lead_id = %s FOR UPDATE",
            (POINT_LEAD_ID,),
        )
        network_offer = cursor.fetchone()
        if not network_offer:
            raise RuntimeError("Current network audit was not found")

        _clone_network_lead(cursor)

        network_row = dict(network_offer)
        network_row["lead_id"] = NETWORK_LEAD_ID
        network_row["slug"] = NETWORK_SLUG
        network_row["business_id"] = NETWORK_ID
        network_row["company_location_id"] = None
        network_row["context_business_id"] = NETWORK_ID
        for field in JSON_FIELDS:
            network_row[field] = _network_page(network_row.get(field)) if network_row.get(field) else None

        columns = list(network_row.keys())
        cursor.execute(
            sql.SQL(
                "INSERT INTO adminprospectingleadpublicoffers ({columns}) VALUES ({values}) "
                "ON CONFLICT (lead_id) DO UPDATE SET {assignments}, updated_at = NOW()"
            ).format(
                columns=sql.SQL(", ").join(sql.Identifier(column) for column in columns),
                values=sql.SQL(", ").join(sql.Placeholder() for _ in columns),
                assignments=sql.SQL(", ").join(
                    sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(column), sql.Identifier(column))
                    for column in columns
                    if column not in {"lead_id", "created_at", "updated_at"}
                ),
            ),
            [_restore_value(column, network_row[column]) for column in columns],
        )

        restore_columns = [column for column in point_backup.keys() if column != "lead_id"]
        cursor.execute(
            sql.SQL("UPDATE adminprospectingleadpublicoffers SET {assignments} WHERE lead_id = %s").format(
                assignments=sql.SQL(", ").join(
                    sql.SQL("{} = {}").format(sql.Identifier(column), sql.Placeholder())
                    for column in restore_columns
                )
            ),
            [_restore_value(column, point_backup[column]) for column in restore_columns] + [POINT_LEAD_ID],
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {
        "point_url": f"https://localos.pro/{point_backup['slug']}",
        "network_url": NETWORK_PUBLIC_URL,
        "network_lead_id": NETWORK_LEAD_ID,
    }


def inspect():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        """
        SELECT lead_id, slug, business_profile, page_json->>'name' AS name,
               page_json->>'address' AS address, page_json->'audit'->>'audit_profile' AS audit_profile
        FROM adminprospectingleadpublicoffers
        WHERE lead_id IN (%s, %s)
        ORDER BY slug
        """,
        (POINT_LEAD_ID, NETWORK_LEAD_ID),
    )
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--restore-json")
    args = parser.parse_args()
    result = apply(args.restore_json) if args.apply else inspect()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
