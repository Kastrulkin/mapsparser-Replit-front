#!/usr/bin/env python3
import argparse
import json
import time
import uuid
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup
from psycopg2.extras import Json

from api.prospecting.lead_parsing import _enqueue_parse_task_for_business
from auth_system import create_password_setup_token
from core.email_delivery import build_password_setup_link, send_password_setup_email
from pg_db_utils import get_db_connection


NETWORK_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, "localos:network:color-chicks-spb"))
OWNER_EMAIL = "info@rechcenter.ru"
OWNER_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, f"localos:user:{OWNER_EMAIL}"))
COMPANY_ID = "dda25988-aa1c-4ba8-b3d6-067bf8d69a5f"
CHAIN_ID = "82325561646"
CHAIN_URL = "https://yandex.com/maps/2/saint-petersburg/chain/raznocvetnye_cypljata/82325561646/"
TRIAL_DAYS = 14


LOCATIONS = [
    ("125173393729", "Кирочная улица, 31к2", 5.0, 181),
    ("41309209660", "Республиканская улица, 24к1", 5.0, 53),
    ("147841898763", "улица Дыбенко, 5к1", 4.7, 28),
    ("16266854357", "Малодетскосельский проспект, 31", 5.0, 82),
    ("86297910682", "Сестрорецкая улица, 2", 5.0, 58),
    ("3555192770", "Большой проспект В.О., 63/17", 5.0, 41),
    ("178216735997", "Лыжный переулок, 8к1", 5.0, 43),
    ("15560408052", "проспект Большевиков, 7к3", 5.0, 32),
    ("203364188120", "Ленинский проспект, 88", 5.0, 78),
    ("90353348231", "Всеволожск, Октябрьский проспект, 74", 4.7, 17),
    ("203495636164", "улица Ивана Куликова, 12", 5.0, 36),
    ("119651054096", "улица Ушинского, 3к2", 5.0, 85),
    ("231854016121", "проспект Королёва, 73", 4.7, 11),
    ("90493830301", "улица Александра Матросова, 20к2", 5.0, 76),
    ("57120436673", "проспект Просвещения, 15", 5.0, 41),
    ("58506346839", "проспект Ветеранов, 181", None, 30),
    ("1315866281", "Балканская площадь, 5Д", 5.0, 117),
    ("85469176919", "Комендантский проспект, 9", 5.0, 62),
    ("98896561061", "улица Морской Пехоты, 10к2", 5.0, 44),
    ("91911137164", "Мурино, Охтинская аллея, 12", 5.0, 69),
]


def _id(kind, key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"localos:color-chicks:{kind}:{key}"))


def _chain_coordinates():
    try:
        response = requests.get(CHAIN_URL, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
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


def _load_yandex_payload(url):
    response = requests.get(
        url,
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    node = soup.find("script", {"type": "application/json"})
    if not node or not node.string:
        raise RuntimeError("Yandex page does not contain public business data")
    payload = json.loads(node.string)
    return payload["stack"][0]["results"]["items"][0]


def _fetch_public_snapshot(org_id):
    base_url = f"https://yandex.com/maps/org/{org_id}/reviews/"
    first = _load_yandex_payload(base_url)
    review_results = first.get("reviewResults") or {}
    reviews = list(review_results.get("reviews") or [])
    total_pages = int((review_results.get("params") or {}).get("totalPages") or 1)
    for page in range(2, total_pages + 1):
        time.sleep(0.2)
        item = _load_yandex_payload(f"{base_url}?page={page}")
        reviews.extend((item.get("reviewResults") or {}).get("reviews") or [])
    rating_data = first.get("ratingData") or {}
    return {
        "rating": rating_data.get("ratingValue"),
        "reviews_count": rating_data.get("reviewCount"),
        "news_count": int((first.get("eventsPreviews") or {}).get("count") or 0),
        "reviews": reviews,
    }


def direct_refresh():
    conn = get_db_connection()
    cursor = conn.cursor()
    refreshed = []
    failures = []
    try:
        for org_id, _, _, _ in LOCATIONS:
            business_id = _id("business", org_id)
            location_id = _id("company-location", org_id)
            profile_id = _id("external-profile", org_id)
            try:
                snapshot = _fetch_public_snapshot(org_id)
                cursor.execute(
                    """
                    UPDATE businesses
                    SET rating = COALESCE(%s, rating),
                        reviews_count = COALESCE(%s, reviews_count),
                        external_ids = COALESCE(external_ids, '{}'::jsonb) || jsonb_build_object(
                            'yandex_org_id', %s,
                            'yandex_chain_id', %s,
                            'yandex_news_count', %s,
                            'yandex_public_refreshed_at', NOW()
                        ),
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (
                        snapshot["rating"],
                        snapshot["reviews_count"],
                        org_id,
                        CHAIN_ID,
                        snapshot["news_count"],
                        business_id,
                    ),
                )
                cursor.execute(
                    "UPDATE externalbusinessreviews SET is_current = FALSE WHERE business_id = %s AND source = 'yandex_maps'",
                    (business_id,),
                )
                for review in snapshot["reviews"]:
                    review_id = str(review.get("reviewId") or "").strip()
                    if not review_id:
                        continue
                    comment = review.get("businessComment") or {}
                    author = review.get("author") or {}
                    cursor.execute(
                        """
                        INSERT INTO externalbusinessreviews (
                            id, business_id, source, external_review_id, rating,
                            author_name, author_profile_url, text, response_text,
                            response_at, published_at, lang, raw_payload,
                            company_location_id, external_profile_id, is_current,
                            last_seen_at, created_at, updated_at
                        ) VALUES (
                            %s, %s, 'yandex_maps', %s, %s,
                            %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s, TRUE, NOW(), NOW(), NOW()
                        )
                        ON CONFLICT (id) DO UPDATE SET
                            rating = EXCLUDED.rating,
                            author_name = EXCLUDED.author_name,
                            text = EXCLUDED.text,
                            response_text = EXCLUDED.response_text,
                            response_at = EXCLUDED.response_at,
                            published_at = EXCLUDED.published_at,
                            raw_payload = EXCLUDED.raw_payload,
                            company_location_id = EXCLUDED.company_location_id,
                            external_profile_id = EXCLUDED.external_profile_id,
                            is_current = TRUE,
                            last_seen_at = NOW(),
                            updated_at = NOW()
                        """,
                        (
                            _id("review", review_id),
                            business_id,
                            review_id,
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
                        ),
                    )
                conn.commit()
                refreshed.append({
                    "org_id": org_id,
                    "news_count": snapshot["news_count"],
                    "reviews_loaded": len(snapshot["reviews"]),
                })
            except Exception as exc:
                conn.rollback()
                failures.append({"org_id": org_id, "error": str(exc)})
        return {"refreshed": refreshed, "failures": failures}
    finally:
        conn.close()


def _ensure_owner(cursor):
    cursor.execute("SELECT id FROM users WHERE LOWER(email) = %s", (OWNER_EMAIL,))
    row = cursor.fetchone()
    if row:
        return str(row["id"])
    cursor.execute(
        """
        INSERT INTO users (id, email, name, created_at, updated_at, is_active, is_verified)
        VALUES (%s, %s, %s, NOW(), NOW(), TRUE, FALSE)
        """,
        (OWNER_ID, OWNER_EMAIL, "Команда «Разноцветных цыплят»"),
    )
    return OWNER_ID


def _ensure_network(cursor, owner_id, trial_until):
    cursor.execute(
        """
        INSERT INTO networks (id, owner_id, name, description, entity_group, created_at, updated_at)
        VALUES (%s, %s, %s, %s, 'client', NOW(), NOW())
        ON CONFLICT (id) DO UPDATE SET owner_id = EXCLUDED.owner_id, updated_at = NOW()
        """,
        (
            NETWORK_ID,
            owner_id,
            "Разноцветные цыплята",
            "Пробный сетевой кабинет: карта филиалов, рейтинги, отзывы и новости.",
        ),
    )
    cursor.execute(
        """
        INSERT INTO businesses (
            id, owner_id, name, network_id, description, address, is_active,
            subscription_tier, subscription_status, subscription_ends_at,
            ai_agent_language, entity_group, created_at, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, TRUE, 'promo', 'active', %s, 'ru', 'client', NOW(), NOW())
        ON CONFLICT (id) DO UPDATE SET
            owner_id = EXCLUDED.owner_id,
            network_id = EXCLUDED.network_id,
            subscription_tier = 'promo',
            subscription_status = 'active',
            subscription_ends_at = EXCLUDED.subscription_ends_at,
            updated_at = NOW()
        """,
        (
            NETWORK_ID,
            owner_id,
            "Разноцветные цыплята",
            NETWORK_ID,
            "Материнский экран сети.",
            "Все точки сети",
            trial_until,
        ),
    )
    cursor.execute(
        """
        INSERT INTO network_members (id, network_id, user_id, role, status, created_by_user_id, created_at, updated_at)
        VALUES (%s, %s, %s, 'manager', 'active', %s, NOW(), NOW())
        ON CONFLICT (network_id, user_id) DO UPDATE SET role = 'manager', status = 'active', updated_at = NOW()
        """,
        (_id("membership", owner_id), NETWORK_ID, owner_id, "a453a8b3-3b26-4c4e-81e3-1b973d4b8755"),
    )


def _ensure_location(cursor, owner_id, trial_until, record, coordinates):
    org_id, address, rating, reviews_count = record
    business_id = _id("business", org_id)
    location_id = _id("company-location", org_id)
    profile_id = _id("external-profile", org_id)
    source_url = f"https://yandex.com/maps/org/raznotsvetnyye_tsyplyata/{org_id}"
    lon = coordinates[0] if coordinates and len(coordinates) > 1 else None
    lat = coordinates[1] if coordinates and len(coordinates) > 1 else None
    city = "Всеволожск" if address.startswith("Всеволожск") else "Мурино" if address.startswith("Мурино") else "Санкт-Петербург"
    display_address = address if address.startswith(("Всеволожск", "Мурино")) else f"Санкт-Петербург, {address}"

    cursor.execute(
        """
        INSERT INTO company_locations (
            id, company_id, display_name, address, city, region, country,
            latitude, longitude, timezone, is_primary, status, metadata_json,
            created_at, updated_at
        ) VALUES (%s, %s, %s, %s, %s, 'Санкт-Петербург и Ленинградская область', 'RU', %s, %s,
                  'Europe/Moscow', FALSE, 'active', %s, NOW(), NOW())
        ON CONFLICT (id) DO UPDATE SET
            address = EXCLUDED.address,
            latitude = COALESCE(EXCLUDED.latitude, company_locations.latitude),
            longitude = COALESCE(EXCLUDED.longitude, company_locations.longitude),
            metadata_json = company_locations.metadata_json || EXCLUDED.metadata_json,
            updated_at = NOW()
        """,
        (
            location_id,
            COMPANY_ID,
            f"Разноцветные цыплята — {address}",
            display_address,
            city,
            lat,
            lon,
            Json({"yandex_chain_id": CHAIN_ID, "yandex_org_id": org_id}),
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
            (profile_id, location_id, org_id, source_url, Json({"yandex_chain_id": CHAIN_ID})),
        )

    cursor.execute(
        """
        INSERT INTO businesses (
            id, owner_id, name, business_type, address, is_active, network_id,
            description, industry, website, rating, reviews_count, categories,
            geo_lat, geo_lon, city, country, yandex_url, external_ids,
            subscription_tier, subscription_status, subscription_ends_at,
            ai_agent_language, entity_group, created_at, updated_at
        ) VALUES (
            %s, %s, %s, 'children_education', %s, TRUE, %s,
            %s, 'Детское развитие и коррекция речи', 'https://color-chicks.ru/', %s, %s, %s,
            %s, %s, %s, 'RU', %s, %s,
            'promo', 'active', %s, 'ru', 'client', NOW(), NOW()
        )
        ON CONFLICT (id) DO UPDATE SET
            owner_id = EXCLUDED.owner_id,
            network_id = EXCLUDED.network_id,
            address = EXCLUDED.address,
            rating = EXCLUDED.rating,
            reviews_count = EXCLUDED.reviews_count,
            geo_lat = COALESCE(EXCLUDED.geo_lat, businesses.geo_lat),
            geo_lon = COALESCE(EXCLUDED.geo_lon, businesses.geo_lon),
            yandex_url = EXCLUDED.yandex_url,
            external_ids = EXCLUDED.external_ids,
            subscription_tier = 'promo',
            subscription_status = 'active',
            subscription_ends_at = EXCLUDED.subscription_ends_at,
            entity_group = 'client',
            updated_at = NOW()
        """,
        (
            business_id,
            owner_id,
            f"Разноцветные цыплята — {address}",
            display_address,
            NETWORK_ID,
            "Точка сети «Разноцветные цыплята».",
            rating,
            reviews_count,
            Json(["Логопеды", "Дефектологи", "Центр развития ребёнка"]),
            lat,
            lon,
            city,
            source_url,
            Json({"yandex_org_id": org_id, "yandex_chain_id": CHAIN_ID, "company_location_id": location_id}),
            trial_until,
        ),
    )
    return {
        "business_id": business_id,
        "company_location_id": location_id,
        "external_profile_id": profile_id,
        "source_url": source_url,
        "address": display_address,
    }


def apply(send_invite):
    coordinates = _chain_coordinates()
    conn = get_db_connection()
    cursor = conn.cursor()
    trial_until = datetime.now(timezone.utc) + timedelta(days=TRIAL_DAYS)
    try:
        owner_id = _ensure_owner(cursor)
        _ensure_network(cursor, owner_id, trial_until)
        created = [_ensure_location(cursor, owner_id, trial_until, record, coordinates.get(record[0])) for record in LOCATIONS]
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    tasks = []
    for location in created:
        task = _enqueue_parse_task_for_business(location["business_id"], owner_id, location["source_url"])
        task_id = str(task.get("id") or "").strip()
        if task_id:
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
                (
                    location["company_location_id"],
                    location["external_profile_id"],
                    NETWORK_ID,
                    task_id,
                ),
            )
            task_conn.commit()
            task_conn.close()
        tasks.append({"business_id": location["business_id"], "task": task})

    setup_url = None
    email_sent = False
    if send_invite:
        setup_result = create_password_setup_token(owner_id)
        if not setup_result.get("error"):
            setup_url = build_password_setup_link(OWNER_EMAIL, setup_result["verification_token"])
            email_sent = bool(send_password_setup_email(OWNER_EMAIL, "команда «Разноцветных цыплят»", setup_result["verification_token"]))

    return {
        "network_id": NETWORK_ID,
        "owner_id": owner_id,
        "owner_email": OWNER_EMAIL,
        "trial_until": trial_until.isoformat(),
        "locations_count": len(created),
        "queued_tasks": sum(1 for item in tasks if item["task"]),
        "email_sent": email_sent,
        "setup_url": setup_url,
    }


def inspect():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT b.id, b.name, b.address, b.rating, b.reviews_count, b.yandex_url,
               b.subscription_tier, b.subscription_status, b.subscription_ends_at,
               COALESCE(
                   NULLIF(b.external_ids->>'yandex_news_count', '')::integer,
                   jsonb_array_length(
                       CASE WHEN jsonb_typeof(COALESCE(card.news::jsonb, '[]'::jsonb)) = 'array'
                            THEN COALESCE(card.news::jsonb, '[]'::jsonb) ELSE '[]'::jsonb END
                   ),
                   0
               ) AS news_count,
               COALESCE(reviews.unanswered, 0) AS unanswered_reviews_count
        FROM businesses b
        LEFT JOIN LATERAL (
            SELECT news FROM cards WHERE business_id = b.id
            ORDER BY is_latest DESC NULLS LAST, created_at DESC LIMIT 1
        ) card ON TRUE
        LEFT JOIN LATERAL (
            SELECT COUNT(*) FILTER (
                WHERE COALESCE(NULLIF(TRIM(response_text), ''), '') IN ('', '—')
                  AND COALESCE(is_current, TRUE) IS TRUE
            ) AS unanswered
            FROM externalbusinessreviews WHERE business_id = b.id
        ) reviews ON TRUE
        WHERE b.network_id = %s AND b.id <> %s
        ORDER BY b.address
        """,
        (NETWORK_ID, NETWORK_ID),
    )
    locations = [dict(row) for row in cursor.fetchall()]
    cursor.execute(
        """
        SELECT status, COUNT(*) AS count
        FROM parsequeue
        WHERE business_id = ANY(%s::text[])
        GROUP BY status ORDER BY status
        """,
        ([item["id"] for item in locations],),
    )
    queue = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {"network_id": NETWORK_ID, "locations": locations, "queue": queue}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--send-invite", action="store_true")
    parser.add_argument("--direct-refresh", action="store_true")
    args = parser.parse_args()
    if args.direct_refresh:
        result = direct_refresh()
    else:
        result = apply(args.send_invite) if args.apply else inspect()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
