#!/usr/bin/env python3
import argparse
import json
import time
import uuid
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup
from psycopg2.extras import Json, RealDictCursor

from api.prospecting.lead_parsing import _enqueue_parse_task_for_business
from auth_system import create_password_setup_token
from core.email_delivery import build_password_setup_link, send_password_setup_email
from pg_db_utils import get_db_connection


LEAD_ID = "c2e6f5d5-1dd0-4dd3-9cdc-d0e67603a8cf"
COMPANY_ID = "d2e37653-6403-49da-ac8f-493c580fd39e"
EXISTING_TIPANOVA_BUSINESS_ID = "7f02e09c-5cd0-4fd3-a5c2-f67fa2c427c1"
EXISTING_TIPANOVA_LOCATION_ID = "cbfef8f2-206e-421a-94dd-84557c95f800"
NETWORK_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, "localos:network:extra-spa-spb"))
OWNER_EMAIL = "ExtraSpaSPB@yandex.ru"
OWNER_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, f"localos:user:{OWNER_EMAIL.lower()}"))
TRIAL_DAYS = 14
SEARCH_URL = "https://yandex.com/maps/2/saint-petersburg/search/Extra%20SPA/"


LOCATIONS = [
    ("139975593400", "Большая Пушкарская улица, 20"),
    ("235073734555", "4-я линия Васильевского острова, 5"),
    ("214079371845", "проспект Культуры, 1"),
    ("211181504259", "улица Типанова, 21"),
    ("187089605373", "проспект Энгельса, 154"),
    ("197949670549", "Планерная улица, 59"),
]


def _id(kind, key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"localos:extra-spa:{kind}:{key}"))


def _business_id(org_id):
    return EXISTING_TIPANOVA_BUSINESS_ID if org_id == "211181504259" else _id("business", org_id)


def _location_id(org_id):
    return EXISTING_TIPANOVA_LOCATION_ID if org_id == "211181504259" else _id("company-location", org_id)


def _load_yandex_item(url):
    response = requests.get(
        url,
        timeout=40,
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    node = soup.find("script", {"type": "application/json"})
    if not node or not node.string:
        raise RuntimeError("Yandex page does not contain public business data")
    payload = json.loads(node.string)
    return payload["stack"][0]["results"]["items"][0]


def _search_coordinates():
    try:
        response = requests.get(SEARCH_URL, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        payload = json.loads(soup.find("script", {"type": "application/json"}).string)
        items = payload["stack"][0]["results"]["items"]
        return {
            str(item.get("id")): item.get("coordinates")
            for item in items
            if item.get("id") and item.get("coordinates")
        }
    except Exception:
        return {}


def _fetch_public_snapshot(org_id):
    base_url = f"https://yandex.com/maps/org/{org_id}/reviews/"
    first = _load_yandex_item(base_url)
    review_results = first.get("reviewResults") or {}
    reviews = list(review_results.get("reviews") or [])
    total_pages = int((review_results.get("params") or {}).get("totalPages") or 1)
    for page in range(2, total_pages + 1):
        time.sleep(0.15)
        item = _load_yandex_item(f"{base_url}?page={page}")
        reviews.extend((item.get("reviewResults") or {}).get("reviews") or [])
    rating_data = first.get("ratingData") or {}
    return {
        "org_id": org_id,
        "rating": rating_data.get("ratingValue"),
        "reviews_count": rating_data.get("reviewCount"),
        "news_count": int((first.get("eventsPreviews") or {}).get("count") or 0),
        "reviews": reviews,
    }


def collect_public_snapshots():
    snapshots = []
    failures = []
    for org_id, address in LOCATIONS:
        try:
            snapshot = _fetch_public_snapshot(org_id)
            snapshot["address"] = address
            snapshots.append(snapshot)
        except Exception as exc:
            failures.append({"org_id": org_id, "address": address, "error": str(exc)})
    return snapshots, failures


def _ensure_owner(cursor):
    cursor.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(%s)", (OWNER_EMAIL,))
    row = cursor.fetchone()
    if row:
        return str(row["id"])
    cursor.execute(
        """
        INSERT INTO users (id, email, name, created_at, updated_at, is_active, is_verified)
        VALUES (%s, %s, %s, NOW(), NOW(), TRUE, FALSE)
        """,
        (OWNER_ID, OWNER_EMAIL, "Команда Extra СПА"),
    )
    return OWNER_ID


def _ensure_network(cursor, owner_id, trial_until):
    cursor.execute(
        """
        INSERT INTO networks (id, owner_id, name, description, entity_group, created_at, updated_at)
        VALUES (%s, %s, 'Extra СПА', %s, 'client', NOW(), NOW())
        ON CONFLICT (id) DO UPDATE SET owner_id = EXCLUDED.owner_id, description = EXCLUDED.description, updated_at = NOW()
        """,
        (NETWORK_ID, owner_id, "Пробный сетевой кабинет: шесть филиалов, отзывы, новости и различия между точками."),
    )
    cursor.execute(
        """
        INSERT INTO businesses (
            id, owner_id, name, network_id, description, address, is_active,
            subscription_tier, subscription_status, subscription_ends_at,
            ai_agent_language, entity_group, created_at, updated_at
        ) VALUES (%s, %s, 'Extra СПА', %s, %s, 'Все точки сети', TRUE,
                  'promo', 'active', %s, 'ru', 'client', NOW(), NOW())
        ON CONFLICT (id) DO UPDATE SET
            owner_id = EXCLUDED.owner_id,
            network_id = EXCLUDED.network_id,
            description = EXCLUDED.description,
            subscription_tier = 'promo',
            subscription_status = 'active',
            subscription_ends_at = EXCLUDED.subscription_ends_at,
            entity_group = 'client',
            updated_at = NOW()
        """,
        (NETWORK_ID, owner_id, NETWORK_ID, "Материнский экран сети Extra СПА.", trial_until),
    )
    cursor.execute(
        """
        INSERT INTO network_members (id, network_id, user_id, role, status, created_by_user_id, created_at, updated_at)
        VALUES (%s, %s, %s, 'manager', 'active', %s, NOW(), NOW())
        ON CONFLICT (network_id, user_id) DO UPDATE SET role = 'manager', status = 'active', updated_at = NOW()
        """,
        (_id("membership", owner_id), NETWORK_ID, owner_id, "a453a8b3-3b26-4c4e-81e3-1b973d4b8755"),
    )


def _ensure_location(cursor, owner_id, trial_until, snapshot, coordinates):
    org_id = snapshot["org_id"]
    address = snapshot["address"]
    business_id = _business_id(org_id)
    location_id = _location_id(org_id)
    profile_id = _id("external-profile", org_id)
    source_url = f"https://yandex.com/maps/org/extra_spa/{org_id}"
    lon = coordinates[0] if coordinates and len(coordinates) > 1 else None
    lat = coordinates[1] if coordinates and len(coordinates) > 1 else None
    display_address = f"Санкт-Петербург, {address}"

    cursor.execute(
        """
        INSERT INTO company_locations (
            id, company_id, display_name, address, city, region, country,
            latitude, longitude, timezone, is_primary, status, metadata_json,
            created_at, updated_at
        ) VALUES (%s, %s, %s, %s, 'Санкт-Петербург', 'Санкт-Петербург', 'RU', %s, %s,
                  'Europe/Moscow', %s, 'active', %s, NOW(), NOW())
        ON CONFLICT (id) DO UPDATE SET
            company_id = EXCLUDED.company_id,
            display_name = EXCLUDED.display_name,
            address = EXCLUDED.address,
            latitude = COALESCE(EXCLUDED.latitude, company_locations.latitude),
            longitude = COALESCE(EXCLUDED.longitude, company_locations.longitude),
            timezone = COALESCE(company_locations.timezone, EXCLUDED.timezone),
            metadata_json = COALESCE(company_locations.metadata_json, '{}'::jsonb) || EXCLUDED.metadata_json,
            updated_at = NOW()
        """,
        (
            location_id,
            COMPANY_ID,
            f"Extra СПА — {address}",
            display_address,
            lat,
            lon,
            org_id == "211181504259",
            Json({"yandex_org_id": org_id, "network_name": "Extra СПА"}),
        ),
    )

    cursor.execute("SELECT id FROM company_external_profiles WHERE provider = 'yandex_maps' AND external_id = %s", (org_id,))
    existing_profile = cursor.fetchone()
    if existing_profile:
        profile_id = str(existing_profile["id"])
        cursor.execute(
            """
            UPDATE company_external_profiles
            SET company_location_id = %s, canonical_url = %s, status = 'active', updated_at = NOW()
            WHERE id = %s
            """,
            (location_id, source_url, profile_id),
        )
    else:
        cursor.execute(
            """
            INSERT INTO company_external_profiles (
                id, company_location_id, provider, external_id, canonical_url,
                status, sync_status, metadata_json, created_at, updated_at
            ) VALUES (%s, %s, 'yandex_maps', %s, %s, 'active', 'idle', %s, NOW(), NOW())
            """,
            (profile_id, location_id, org_id, source_url, Json({"network_name": "Extra СПА"})),
        )

    cursor.execute(
        """
        INSERT INTO businesses (
            id, owner_id, name, business_type, address, is_active, network_id,
            description, industry, phone, email, website, rating, reviews_count, categories,
            geo_lat, geo_lon, city, country, yandex_url, external_ids,
            subscription_tier, subscription_status, subscription_ends_at,
            ai_agent_language, entity_group, created_at, updated_at
        ) VALUES (
            %s, %s, %s, 'spa_wellness', %s, TRUE, %s,
            'Филиал сети Extra СПА.', 'СПА, массаж и косметология',
            '+7 (923) 899-02-30', %s, 'https://экстраспа.рф/', %s, %s, %s,
            %s, %s, 'Санкт-Петербург', 'RU', %s, %s,
            'promo', 'active', %s, 'ru', 'client', NOW(), NOW()
        )
        ON CONFLICT (id) DO UPDATE SET
            owner_id = EXCLUDED.owner_id,
            name = EXCLUDED.name,
            business_type = EXCLUDED.business_type,
            address = EXCLUDED.address,
            network_id = EXCLUDED.network_id,
            description = EXCLUDED.description,
            industry = EXCLUDED.industry,
            email = EXCLUDED.email,
            website = EXCLUDED.website,
            rating = EXCLUDED.rating,
            reviews_count = EXCLUDED.reviews_count,
            categories = EXCLUDED.categories,
            geo_lat = COALESCE(EXCLUDED.geo_lat, businesses.geo_lat),
            geo_lon = COALESCE(EXCLUDED.geo_lon, businesses.geo_lon),
            yandex_url = EXCLUDED.yandex_url,
            external_ids = COALESCE(businesses.external_ids, '{}'::jsonb) || EXCLUDED.external_ids,
            subscription_tier = 'promo',
            subscription_status = 'active',
            subscription_ends_at = EXCLUDED.subscription_ends_at,
            entity_group = 'client',
            updated_at = NOW()
        """,
        (
            business_id,
            owner_id,
            f"Extra СПА — {address}",
            display_address,
            NETWORK_ID,
            OWNER_EMAIL,
            snapshot.get("rating"),
            snapshot.get("reviews_count"),
            Json(["СПА-салон", "Массажный салон", "Косметология"]),
            lat,
            lon,
            source_url,
            Json({
                "yandex_org_id": org_id,
                "company_location_id": location_id,
                "yandex_news_count": snapshot.get("news_count", 0),
                "review_appeals_interest": True,
            }),
            trial_until,
        ),
    )
    cursor.execute(
        """
        INSERT INTO business_company_links (
            id, business_id, company_id, company_location_id, relation_role,
            is_primary, created_at, updated_at
        ) VALUES (%s, %s, %s, %s, 'owner', TRUE, NOW(), NOW())
        ON CONFLICT (business_id, company_id, company_location_id)
        WHERE company_location_id IS NOT NULL
        DO UPDATE SET
            relation_role = 'owner',
            is_primary = TRUE,
            updated_at = NOW()
        """,
        (_id("business-company-link", org_id), business_id, COMPANY_ID, location_id),
    )
    return {
        "business_id": business_id,
        "company_location_id": location_id,
        "external_profile_id": profile_id,
        "source_url": source_url,
        "address": display_address,
    }


def _upsert_reviews(cursor, snapshot):
    org_id = snapshot["org_id"]
    business_id = _business_id(org_id)
    location_id = _location_id(org_id)
    profile_id = _id("external-profile", org_id)
    cursor.execute("SELECT id FROM company_external_profiles WHERE provider = 'yandex_maps' AND external_id = %s", (org_id,))
    profile = cursor.fetchone()
    if profile:
        profile_id = str(profile["id"])
    snapshot_id = _id("review-snapshot", f"{org_id}:2026-08-18")
    cursor.execute(
        "UPDATE externalbusinessreviews SET is_current = FALSE WHERE business_id = %s AND source = 'yandex_maps'",
        (business_id,),
    )
    inserted = 0
    for review in snapshot.get("reviews") or []:
        review_external_id = str(review.get("reviewId") or "").strip()
        if not review_external_id:
            continue
        cursor.execute(
            """
            SELECT id FROM externalbusinessreviews
            WHERE business_id = %s AND source = 'yandex_maps' AND external_review_id = %s
            LIMIT 1
            """,
            (business_id, review_external_id),
        )
        existing = cursor.fetchone()
        review_id = str(existing["id"]) if existing else _id("review", f"{org_id}:{review_external_id}")
        comment = review.get("businessComment") or {}
        author = review.get("author") or {}
        cursor.execute(
            """
            INSERT INTO externalbusinessreviews (
                id, business_id, source, external_review_id, rating,
                author_name, author_profile_url, text, response_text,
                response_at, published_at, lang, raw_payload,
                company_location_id, external_profile_id, is_current,
                last_seen_at, last_complete_snapshot_id, created_at, updated_at
            ) VALUES (
                %s, %s, 'yandex_maps', %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, TRUE, NOW(), %s, NOW(), NOW()
            )
            ON CONFLICT (id) DO UPDATE SET
                rating = EXCLUDED.rating,
                author_name = EXCLUDED.author_name,
                author_profile_url = EXCLUDED.author_profile_url,
                text = EXCLUDED.text,
                response_text = EXCLUDED.response_text,
                response_at = EXCLUDED.response_at,
                published_at = EXCLUDED.published_at,
                lang = EXCLUDED.lang,
                raw_payload = EXCLUDED.raw_payload,
                company_location_id = EXCLUDED.company_location_id,
                external_profile_id = EXCLUDED.external_profile_id,
                is_current = TRUE,
                last_seen_at = NOW(),
                last_complete_snapshot_id = EXCLUDED.last_complete_snapshot_id,
                updated_at = NOW()
            """,
            (
                review_id,
                business_id,
                review_external_id,
                review.get("rating"),
                author.get("name"),
                author.get("publicId"),
                review.get("text"),
                comment.get("text"),
                comment.get("updatedTime"),
                review.get("updatedTime"),
                review.get("textLanguage"),
                json.dumps(review, ensure_ascii=False),
                location_id,
                profile_id,
                snapshot_id,
            ),
        )
        inserted += 1
    cursor.execute(
        """
        UPDATE company_external_profiles
        SET last_collected_at = NOW(),
            sync_status = 'completed',
            last_sync_error = NULL,
            metadata_json = COALESCE(metadata_json, '{}'::jsonb) || %s,
            updated_at = NOW()
        WHERE id = %s
        """,
        (
            Json(
                {
                    "reviews_baseline_date": "2026-08-18",
                    "reviews_snapshot_id": snapshot_id,
                    "reviews_loaded": inserted,
                    "reviews_public_count": snapshot.get("reviews_count"),
                    "news_count": snapshot.get("news_count", 0),
                }
            ),
            profile_id,
        ),
    )
    return inserted


def apply(send_invite, input_json=None):
    if input_json:
        with open(input_json, "r", encoding="utf-8") as source:
            payload = json.load(source)
        snapshots = payload.get("snapshots") or []
        failures = payload.get("failures") or []
    else:
        snapshots, failures = collect_public_snapshots()
    if failures or len(snapshots) != len(LOCATIONS):
        raise RuntimeError(f"Could not load all six public locations: {failures}")
    coordinates_by_org = _search_coordinates()
    trial_until = datetime.now(timezone.utc) + timedelta(days=TRIAL_DAYS)
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    created = []
    imported_reviews = 0
    try:
        owner_id = _ensure_owner(cursor)
        _ensure_network(cursor, owner_id, trial_until)
        for snapshot in snapshots:
            created.append(_ensure_location(cursor, owner_id, trial_until, snapshot, coordinates_by_org.get(snapshot["org_id"])))
        for snapshot in snapshots:
            imported_reviews += _upsert_reviews(cursor, snapshot)
        cursor.execute(
            """
            UPDATE prospectingleads
            SET business_id = %s,
                company_id = %s,
                company_location_id = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (NETWORK_ID, COMPANY_ID, EXISTING_TIPANOVA_LOCATION_ID, LEAD_ID),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    queued = 0
    for location in created:
        task = _enqueue_parse_task_for_business(location["business_id"], owner_id, location["source_url"])
        task_id = str((task or {}).get("id") or "").strip()
        if not task_id:
            continue
        task_conn = get_db_connection()
        task_cursor = task_conn.cursor()
        task_cursor.execute(
            """
            UPDATE parsequeue
            SET company_location_id = %s,
                external_profile_id = %s,
                requested_by_business_id = %s,
                force_refresh = TRUE,
                updated_at = NOW()
            WHERE id = %s
            """,
            (location["company_location_id"], location["external_profile_id"], NETWORK_ID, task_id),
        )
        task_conn.commit()
        task_conn.close()
        queued += 1

    setup_url = None
    email_sent = False
    if send_invite:
        setup_result = create_password_setup_token(owner_id)
        if not setup_result.get("error"):
            setup_url = build_password_setup_link(OWNER_EMAIL, setup_result["verification_token"])
            email_sent = bool(send_password_setup_email(OWNER_EMAIL, "команда Extra СПА", setup_result["verification_token"]))

    return {
        "network_id": NETWORK_ID,
        "owner_id": owner_id,
        "owner_email": OWNER_EMAIL,
        "trial_until": trial_until.isoformat(),
        "locations_count": len(created),
        "reviews_imported": imported_reviews,
        "queued_tasks": queued,
        "email_sent": email_sent,
        "setup_url": setup_url,
        "snapshots": [
            {
                "org_id": item["org_id"],
                "address": item["address"],
                "rating": item.get("rating"),
                "reviews_count": item.get("reviews_count"),
                "reviews_loaded": len(item.get("reviews") or []),
                "news_count": item.get("news_count"),
            }
            for item in snapshots
        ],
    }


def inspect():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        """
        SELECT b.id, b.name, b.address, b.rating, b.reviews_count, b.yandex_url,
               b.subscription_status, b.subscription_ends_at,
               COALESCE(NULLIF(b.external_ids->>'yandex_news_count', '')::integer, 0) AS news_count,
               COALESCE(review_stats.total, 0) AS imported_reviews,
               COALESCE(review_stats.unanswered, 0) AS unanswered_reviews
        FROM businesses b
        LEFT JOIN LATERAL (
            SELECT COUNT(*) FILTER (WHERE COALESCE(is_current, TRUE)) AS total,
                   COUNT(*) FILTER (
                       WHERE COALESCE(is_current, TRUE)
                         AND COALESCE(NULLIF(TRIM(response_text), ''), '') IN ('', '—')
                   ) AS unanswered
            FROM externalbusinessreviews
            WHERE business_id = b.id AND source = 'yandex_maps'
        ) review_stats ON TRUE
        WHERE b.network_id = %s AND b.id <> %s
        ORDER BY b.address
        """,
        (NETWORK_ID, NETWORK_ID),
    )
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {"network_id": NETWORK_ID, "locations": rows}


def send_invite_only():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(%s)", (OWNER_EMAIL,))
        owner = cursor.fetchone()
    finally:
        conn.close()
    if not owner:
        raise RuntimeError("Extra СПА owner account has not been created")
    setup_result = create_password_setup_token(str(owner["id"]))
    if setup_result.get("error"):
        raise RuntimeError(setup_result["error"])
    setup_url = build_password_setup_link(OWNER_EMAIL, setup_result["verification_token"])
    email_sent = bool(
        send_password_setup_email(
            OWNER_EMAIL,
            "команда Extra СПА",
            setup_result["verification_token"],
        )
    )
    return {
        "owner_email": OWNER_EMAIL,
        "email_sent": email_sent,
        "setup_url": setup_url,
    }


def refresh_review_baseline(input_json):
    if not input_json:
        raise RuntimeError("--input-json is required for baseline refresh")
    with open(input_json, "r", encoding="utf-8") as source:
        snapshots = (json.load(source) or {}).get("snapshots") or []
    if len(snapshots) != len(LOCATIONS):
        raise RuntimeError(f"Expected six snapshots, got {len(snapshots)}")
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        imported_reviews = sum(_upsert_reviews(cursor, snapshot) for snapshot in snapshots)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {
        "locations_count": len(snapshots),
        "reviews_imported": imported_reviews,
        "baseline_date": "2026-08-18",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--send-invite", action="store_true")
    parser.add_argument("--collect-json")
    parser.add_argument("--input-json")
    parser.add_argument("--send-invite-only", action="store_true")
    parser.add_argument("--refresh-review-baseline", action="store_true")
    args = parser.parse_args()
    if args.refresh_review_baseline:
        result = refresh_review_baseline(args.input_json)
    elif args.send_invite_only:
        result = send_invite_only()
    elif args.collect_json:
        snapshots, failures = collect_public_snapshots()
        with open(args.collect_json, "w", encoding="utf-8") as output:
            json.dump({"snapshots": snapshots, "failures": failures}, output, ensure_ascii=False, indent=2)
        result = {
            "locations": len(snapshots),
            "reviews": sum(len(item.get("reviews") or []) for item in snapshots),
            "failures": failures,
            "path": args.collect_json,
        }
    else:
        result = apply(args.send_invite, args.input_json) if args.apply else inspect()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
