#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import random
import secrets
import string
import sys
import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
for candidate in (os.getenv("APP_SRC_DIR"), "/app/src", str(repo_root / "src")):
    if candidate and candidate not in sys.path:
        sys.path.insert(0, candidate)

from auth_system import hash_password
from pg_db_utils import get_db_connection
from psycopg2.extras import Json


DEMO_EMAIL = "demo+groom@localos.pro"
DEMO_USER_NAME = "Иван Иванов"
DEMO_PHONE = "+79999999999"
DEMO_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://localos.pro/demo/grooming-network")
NETWORK_ID = str(uuid.uuid5(DEMO_NAMESPACE, "network"))
USER_ID = str(uuid.uuid5(DEMO_NAMESPACE, "user"))
NETWORK_NAME = "Рога и копыта"
DEMO_SOURCE = "demo_grooming_network"
CONSENT_VERSION = "localos-personal-data-v1-2026-05-11"


LOCATIONS = [
    {
        "key": "krasivykh-partizan",
        "name": "Рога и копыта — Красивых партизан",
        "address": "Санкт-Петербург, ул. Красивых Молдавских партизан, 12",
        "phone": "+79999999999",
        "rating": 4.8,
        "reviews": 286,
        "reviews_30d": 21,
        "photos": 64,
        "news": 7,
        "services": 22,
        "unanswered": 3,
        "revenue_share": 0.26,
        "lat": 59.9343,
        "lon": 30.3351,
    },
    {
        "key": "petrogradskaya",
        "name": "Рога и копыта — Петроградская",
        "address": "Санкт-Петербург, Большой проспект П.С., 45",
        "phone": "+79999999998",
        "rating": 4.6,
        "reviews": 198,
        "reviews_30d": 13,
        "photos": 39,
        "news": 4,
        "services": 20,
        "unanswered": 8,
        "revenue_share": 0.21,
        "lat": 59.9662,
        "lon": 30.3115,
    },
    {
        "key": "moskovskaya",
        "name": "Рога и копыта — Московская",
        "address": "Санкт-Петербург, Московский проспект, 193",
        "phone": "+79999999997",
        "rating": 4.3,
        "reviews": 146,
        "reviews_30d": 9,
        "photos": 24,
        "news": 1,
        "services": 18,
        "unanswered": 17,
        "revenue_share": 0.18,
        "lat": 59.8527,
        "lon": 30.3226,
    },
    {
        "key": "ozerki",
        "name": "Рога и копыта — Озерки",
        "address": "Санкт-Петербург, проспект Энгельса, 124",
        "phone": "+79999999996",
        "rating": 4.9,
        "reviews": 342,
        "reviews_30d": 28,
        "photos": 78,
        "news": 9,
        "services": 22,
        "unanswered": 1,
        "revenue_share": 0.23,
        "lat": 60.0374,
        "lon": 30.3211,
    },
    {
        "key": "kupchino",
        "name": "Рога и копыта — Купчино",
        "address": "Санкт-Петербург, Бухарестская улица, 144",
        "phone": "+79999999995",
        "rating": 3.9,
        "reviews": 91,
        "reviews_30d": 5,
        "photos": 14,
        "news": 0,
        "services": 16,
        "unanswered": 24,
        "revenue_share": 0.12,
        "lat": 59.8335,
        "lon": 30.3792,
    },
]


SERVICES = [
    ("Комплексный груминг собак мелких пород в СПб", "Груминг собак", "Мытьё, сушка, стрижка, когти, уши и аккуратная укладка для собак до 10 кг.", 3200, ["груминг собак спб", "стрижка собак мелких пород"]),
    ("Комплексный груминг собак средних пород", "Груминг собак", "Полный уход для собак 10-25 кг: шерсть, когти, уши, лапы и финальный вид.", 4300, ["груминг собак средних пород", "салон для собак спб"]),
    ("Комплексный груминг собак крупных пород", "Груминг собак", "Глубокое мытьё, вычёсывание, стрижка и уход для крупных пород.", 5900, ["груминг крупных собак", "стрижка больших собак"]),
    ("Гигиеническая стрижка собак", "Стрижка", "Уход за лапами, животом, мордой и зоной под хвостом без полной модельной стрижки.", 2100, ["гигиеническая стрижка собак", "стрижка собак спб"]),
    ("Модельная стрижка собак по породе", "Стрижка", "Форма по породному стандарту или пожеланию владельца с учётом типа шерсти.", 3900, ["модельная стрижка собак", "стрижка собак по породе"]),
    ("Тримминг жесткошёрстных собак", "Тримминг", "Ручной тримминг для терьеров, шнауцеров и других жесткошёрстных пород.", 4800, ["тримминг собак спб", "тримминг терьера"]),
    ("Экспресс-линька для собак", "Линька", "Вычесывание подшёрстка, мытьё и сушка для снижения шерсти дома.", 3600, ["экспресс линька собак", "вычесывание собак"]),
    ("Вычесывание кошек без наркоза", "Кошки", "Бережное удаление лишней шерсти и подшёрстка для кошек без стресса.", 2900, ["вычесывание кошек спб", "груминг кошек"]),
    ("Гигиеническая стрижка кошек", "Кошки", "Аккуратная стрижка колтунов и гигиенических зон для кошек.", 3300, ["стрижка кошек спб", "гигиеническая стрижка кошек"]),
    ("Стрижка когтей собак и кошек", "Быстрые услуги", "Безопасная стрижка когтей с проверкой подушечек лап.", 600, ["стрижка когтей собак", "стрижка когтей кошек"]),
    ("Чистка ушей питомца", "Быстрые услуги", "Мягкая гигиена ушей с осмотром состояния кожи.", 500, ["чистка ушей собак", "уход за ушами питомца"]),
    ("Уход за глазами и мордочкой", "Быстрые услуги", "Очищение зоны вокруг глаз и морды для аккуратного вида.", 650, ["уход за глазами собак", "уход за мордой собаки"]),
    ("SPA-маска для шерсти", "SPA", "Питательная маска для блеска, мягкости и восстановления шерсти.", 1200, ["spa для собак", "маска для шерсти"]),
    ("Уход за лапами и подушечками", "SPA", "Очищение, подравнивание шерсти и защитный бальзам для лап.", 900, ["уход за лапами собак", "бальзам для лап"]),
    ("Puppy grooming — первый груминг щенка", "Щенки", "Мягкое знакомство щенка с салоном: мытьё, сушка, когти и адаптация.", 2600, ["первый груминг щенка", "puppy grooming спб"]),
    ("Выставочный груминг собак", "Выставочный уход", "Подготовка внешнего вида собаки к выставке, фотосессии или событию.", 6900, ["выставочный груминг", "подготовка собаки к выставке"]),
    ("Антиколтун для собак и кошек", "Колтуны", "Разбор или безопасное удаление колтунов с сохранением комфорта питомца.", 1800, ["удаление колтунов", "разбор колтунов кошка собака"]),
    ("Мытьё профессиональной косметикой", "Мытьё", "Подбор шампуня и кондиционера под тип шерсти и чувствительность кожи.", 1900, ["мытье собак", "профессиональная косметика для собак"]),
    ("Фото питомца после груминга", "Сервис", "Мини-фото после процедуры для соцсетей и семейного архива.", 700, ["фото питомца", "фото собаки после груминга"]),
    ("Домашняя памятка по уходу за шерстью", "Консультация", "Рекомендации грумера по расчёскам, частоте мытья и уходу между визитами.", 500, ["уход за шерстью дома", "консультация грумера"]),
]


NETWORK_MONTH_REVENUE = {
    "2026-01": 2400000,
    "2026-02": 2580000,
    "2026-03": 2860000,
    "2026-04": 3120000,
    "2026-05": 3380000,
    "2026-06": 3600000,
}


CLIENT_NAMES = [
    "Анна Смирнова", "Мария Петрова", "Ольга Кузнецова", "Екатерина Волкова", "Ирина Соколова",
    "Алексей Иванов", "Дмитрий Орлов", "Наталья Морозова", "Сергей Новиков", "Полина Фёдорова",
    "Юлия Павлова", "Ксения Белова", "Виктория Захарова", "Михаил Егоров", "Дарья Никитина",
]
PET_NAMES = ["Бублик", "Марс", "Луна", "Тиша", "Ричи", "Молли", "Персик", "Граф", "Чарли", "Буся", "Рокки", "Соня"]
MASTERS = ["Алина Грумер", "Марина Шерсть", "Кирилл Тримминг", "Софья Коготок"]


PARTNERS = [
    ("Ветклиника Мокрый нос", "Ветеринарная клиника", "selected_for_outreach", "draft_ready"),
    ("ХвостМаркет", "Зоомагазин", "channel_selected", "approved"),
    ("Команда рядом", "Кинологический центр", "sent", "sent"),
    ("Лапа в кадре", "Фотостудия животных", "replied", "positive_reply"),
    ("Домик хвоста", "Отель для животных", "converted", "partner"),
    ("Пёс и Пирог", "Dog-friendly кафе", "new", "found"),
    ("Сидеть Лежать", "Школа дрессировки", "selected_for_outreach", "draft_ready"),
    ("Пушистый маршрут", "Зоотакси", "channel_selected", "approved"),
    ("Северная лапа", "Питомник", "postponed", "later"),
    ("Поводок & Ко", "Магазин амуниции", "rejected", "not_relevant"),
]


def stable_id(part):
    return str(uuid.uuid5(DEMO_NAMESPACE, str(part)))


def demo_password():
    alphabet = string.ascii_letters + string.digits
    token = "".join(secrets.choice(alphabet) for _ in range(14))
    return f"Demo-{token}-Aa1"


def json_default(value):
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def table_exists(cursor, table_name):
    cursor.execute("SELECT to_regclass(%s) AS name", (f"public.{table_name.lower()}",))
    row = cursor.fetchone() or {}
    return bool(row.get("name"))


def table_columns(cursor, table_name):
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        """,
        (table_name.lower(),),
    )
    return {str(row.get("column_name") or "").lower() for row in cursor.fetchall() or []}


def column_types(cursor, table_name):
    cursor.execute(
        """
        SELECT column_name, data_type, udt_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        """,
        (table_name.lower(),),
    )
    result = {}
    for row in cursor.fetchall() or []:
        name = str(row.get("column_name") or "").lower()
        if name:
            result[name] = {
                "data_type": str(row.get("data_type") or "").lower(),
                "udt_name": str(row.get("udt_name") or "").lower(),
            }
    return result


def adapt_value(value, column_info=None):
    column_info = column_info or {}
    if isinstance(value, (dict, list)):
        data_type = str(column_info.get("data_type") or "")
        udt_name = str(column_info.get("udt_name") or "")
        if data_type in {"text", "character varying", "character"} or udt_name in {"text", "varchar", "bpchar"}:
            return json.dumps(value, ensure_ascii=False)
        return Json(value)
    return value


def upsert_row(cursor, table_name, row, conflict_key="id"):
    columns = table_columns(cursor, table_name)
    types = column_types(cursor, table_name)
    clean = {}
    for key, value in row.items():
        if key.lower() in columns:
            clean[key.lower()] = value
    if not clean:
        return
    names = list(clean.keys())
    values = [adapt_value(clean[name], types.get(name)) for name in names]
    placeholders = ", ".join(["%s"] * len(names))
    insert_cols = ", ".join(names)
    conflict_key = conflict_key.lower()
    update_cols = [name for name in names if name != conflict_key]
    if update_cols:
        update_sql = ", ".join([f"{name} = EXCLUDED.{name}" for name in update_cols])
    else:
        update_sql = f"{conflict_key} = EXCLUDED.{conflict_key}"
    cursor.execute(
        f"""
        INSERT INTO {table_name} ({insert_cols})
        VALUES ({placeholders})
        ON CONFLICT ({conflict_key}) DO UPDATE SET {update_sql}
        """,
        tuple(values),
    )


def insert_row(cursor, table_name, row):
    columns = table_columns(cursor, table_name)
    types = column_types(cursor, table_name)
    clean = {}
    for key, value in row.items():
        if key.lower() in columns:
            clean[key.lower()] = value
    if not clean:
        return
    names = list(clean.keys())
    placeholders = ", ".join(["%s"] * len(names))
    cursor.execute(
        f"INSERT INTO {table_name} ({', '.join(names)}) VALUES ({placeholders})",
        tuple(adapt_value(clean[name], types.get(name)) for name in names),
    )


def ensure_average_ticket_tables(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS averageticketmatrices (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            status TEXT NOT NULL DEFAULT 'draft',
            source_services_hash TEXT,
            matrix_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            generated_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS averageticketevents (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            matrix_id TEXT REFERENCES averageticketmatrices(id) ON DELETE SET NULL,
            link_id TEXT,
            package_id TEXT,
            booking_id TEXT,
            main_service_id TEXT REFERENCES userservices(id) ON DELETE SET NULL,
            addon_service_id TEXT REFERENCES userservices(id) ON DELETE SET NULL,
            event_type TEXT NOT NULL,
            event_date DATE DEFAULT CURRENT_DATE,
            amount NUMERIC(12, 2),
            master_id TEXT,
            client_name TEXT,
            notes TEXT,
            created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS averageticketpackages (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            service_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
            service_names JSONB NOT NULL DEFAULT '[]'::jsonb,
            base_total NUMERIC(12, 2) DEFAULT 0,
            package_price NUMERIC(12, 2),
            bonus_text TEXT,
            positioning TEXT,
            script TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def ensure_bookings_table(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS bookings (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            client_phone TEXT,
            client_name TEXT,
            client_email TEXT,
            service_id TEXT REFERENCES userservices(id) ON DELETE SET NULL,
            service_name TEXT,
            booking_date DATE,
            booking_time TIME,
            booking_time_local TIMESTAMP,
            source TEXT,
            status TEXT DEFAULT 'pending',
            notes TEXT,
            conversation_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def planned_counts():
    location_count = len(LOCATIONS)
    service_count = len(SERVICES) * location_count
    finance_entry_count = len(NETWORK_MONTH_REVENUE) * location_count * 11
    income_tx_count = len(NETWORK_MONTH_REVENUE) * location_count * 18
    booking_count = location_count * 36
    return {
        "users": 1,
        "networks": 1,
        "parent_business": 1,
        "location_businesses": location_count,
        "services": service_count,
        "finance_entries": finance_entry_count,
        "financialtransactions": income_tx_count,
        "bookings": booking_count,
        "average_ticket_matrices": location_count,
        "average_ticket_packages": location_count * 5,
        "partnership_leads": len(PARTNERS),
    }


def fetch_all(cursor, table_name, where_sql, params):
    if not table_exists(cursor, table_name):
        return []
    cursor.execute(f"SELECT * FROM {table_name} WHERE {where_sql}", tuple(params))
    return [dict(row) for row in cursor.fetchall() or []]


def collect_demo_ids(cursor):
    business_ids = [NETWORK_ID] + [stable_id(f"business:{item['key']}") for item in LOCATIONS]
    cursor.execute("SELECT id FROM businesses WHERE owner_id = %s AND (network_id = %s OR id = %s)", (USER_ID, NETWORK_ID, NETWORK_ID))
    for row in cursor.fetchall() or []:
        value = row.get("id")
        if value and value not in business_ids:
            business_ids.append(value)
    lead_ids = []
    if table_exists(cursor, "prospectingleads"):
        columns = table_columns(cursor, "prospectingleads")
        filters = []
        params = []
        if "business_id" in columns:
            filters.append("business_id = ANY(%s)")
            params.append(business_ids)
        if "source" in columns:
            filters.append("source = %s")
            params.append(DEMO_SOURCE)
        if "source_external_id" in columns:
            filters.append("source_external_id LIKE %s")
            params.append("demo-grooming:%")
        if filters:
            cursor.execute(f"SELECT id FROM prospectingleads WHERE {' OR '.join(filters)}", tuple(params))
            lead_ids = [row.get("id") for row in cursor.fetchall() or [] if row.get("id")]
    return business_ids, lead_ids


def write_backup(cursor, backup_dir):
    business_ids, lead_ids = collect_demo_ids(cursor)
    backup = {
        "created_at": datetime.utcnow().isoformat(),
        "demo_email": DEMO_EMAIL,
        "network_id": NETWORK_ID,
        "business_ids": business_ids,
        "lead_ids": lead_ids,
        "tables": {},
    }
    table_specs = [
        ("users", "id = %s", [USER_ID]),
        ("networks", "id = %s", [NETWORK_ID]),
        ("businesses", "id = ANY(%s)", [business_ids]),
        ("userservices", "business_id = ANY(%s)", [business_ids]),
        ("finance_entries", "business_id = ANY(%s)", [business_ids]),
        ("financialtransactions", "business_id = ANY(%s)", [business_ids]),
        ("bookings", "business_id = ANY(%s)", [business_ids]),
        ("cards", "business_id = ANY(%s)", [business_ids]),
        ("mapparseresults", "business_id = ANY(%s)", [business_ids]),
        ("externalbusinessstats", "business_id = ANY(%s)", [business_ids]),
        ("externalbusinessreviews", "business_id = ANY(%s)", [business_ids]),
        ("businessmaplinks", "business_id = ANY(%s)", [business_ids]),
        ("masters", "business_id = ANY(%s)", [business_ids]),
        ("averageticketmatrices", "business_id = ANY(%s)", [business_ids]),
        ("averageticketevents", "business_id = ANY(%s)", [business_ids]),
        ("averageticketpackages", "business_id = ANY(%s)", [business_ids]),
        ("prospectingleads", "id = ANY(%s)", [lead_ids]),
        ("outreachmessagedrafts", "lead_id = ANY(%s)", [lead_ids]),
        ("partnershipleadartifacts", "lead_id = ANY(%s)", [lead_ids]),
    ]
    for table_name, where_sql, params in table_specs:
        if params and isinstance(params[0], list) and not params[0]:
            backup["tables"][table_name] = []
            continue
        backup["tables"][table_name] = fetch_all(cursor, table_name, where_sql, params)
    backup_dir.mkdir(parents=True, exist_ok=True)
    path = backup_dir / f"demo_grooming_network_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(backup, ensure_ascii=False, indent=2, default=json_default), encoding="utf-8")
    return path


def delete_if_exists(cursor, table_name, where_sql, params):
    if not table_exists(cursor, table_name):
        return
    columns = table_columns(cursor, table_name)
    lower_where = where_sql.lower()
    if "business_id" in lower_where and "business_id" not in columns:
        return
    if "lead_id" in lower_where and "lead_id" not in columns:
        return
    if " id " in f" {lower_where} " and "id" not in columns:
        return
    cursor.execute(f"DELETE FROM {table_name} WHERE {where_sql}", tuple(params))


def refresh_demo_area(cursor):
    business_ids, lead_ids = collect_demo_ids(cursor)
    if lead_ids:
        delete_if_exists(cursor, "outreachreactions", "lead_id = ANY(%s)", [lead_ids])
        delete_if_exists(cursor, "outreachsendqueue", "lead_id = ANY(%s)", [lead_ids])
        delete_if_exists(cursor, "outreachmessagedrafts", "lead_id = ANY(%s)", [lead_ids])
        delete_if_exists(cursor, "partnershipleadartifacts", "lead_id = ANY(%s)", [lead_ids])
        delete_if_exists(cursor, "prospectingleads", "id = ANY(%s)", [lead_ids])
    for table_name in [
        "averageticketevents",
        "averageticketpackages",
        "averageticketmatrices",
        "bookings",
        "finance_entries",
        "financialtransactions",
        "financialmetrics",
        "roidata",
        "masters",
        "externalbusinessreviews",
        "externalbusinessstats",
        "externalbusinessposts",
        "externalbusinessphotos",
        "cards",
        "mapparseresults",
        "businessmaplinks",
        "userservices",
    ]:
        delete_if_exists(cursor, table_name, "business_id = ANY(%s)", [business_ids])
    delete_if_exists(cursor, "businesses", "owner_id = %s AND (network_id = %s OR id = %s)", [USER_ID, NETWORK_ID, NETWORK_ID])
    delete_if_exists(cursor, "networks", "id = %s", [NETWORK_ID])


def seed_user_network_businesses(cursor, password):
    now = datetime.utcnow().isoformat()
    upsert_row(
        cursor,
        "users",
        {
            "id": USER_ID,
            "email": DEMO_EMAIL,
            "password_hash": hash_password(password),
            "name": DEMO_USER_NAME,
            "phone": DEMO_PHONE,
            "is_active": True,
            "is_verified": True,
            "email_verified_at": now,
            "personal_data_consent_at": now,
            "personal_data_consent_version": CONSENT_VERSION,
            "privacy_accepted_at": now,
            "terms_accepted_at": now,
            "credits_balance": 100000,
            "created_at": now,
            "updated_at": now,
        },
    )
    upsert_row(
        cursor,
        "networks",
        {
            "id": NETWORK_ID,
            "name": NETWORK_NAME,
            "owner_id": USER_ID,
            "description": "DEMO: сеть груминговых салонов для демонстрации сетевого функционала LocalOS.",
            "created_at": now,
            "updated_at": now,
        },
    )
    parent_row = {
        "id": NETWORK_ID,
        "name": NETWORK_NAME,
        "description": "DEMO: материнская карточка сети. Используется для обзора точек, партнёрств и сетевых сценариев.",
        "industry": "pet_services",
        "business_type": "grooming_salon_network",
        "address": "Материнская точка сети",
        "working_hours": "Ежедневно 10:00-21:00",
        "phone": DEMO_PHONE,
        "email": DEMO_EMAIL,
        "website": "https://localos.pro",
        "owner_id": USER_ID,
        "network_id": NETWORK_ID,
        "is_active": True,
        "subscription_tier": "promo",
        "subscription_status": "active",
        "city": "Санкт-Петербург",
        "country": "Россия",
        "timezone": "Europe/Moscow",
        "created_at": now,
        "updated_at": now,
    }
    upsert_row(cursor, "businesses", parent_row)
    for item in LOCATIONS:
        upsert_row(
            cursor,
            "businesses",
            {
                "id": stable_id(f"business:{item['key']}"),
                "name": item["name"],
                "description": f"DEMO: точка сети груминговых салонов {NETWORK_NAME}.",
                "industry": "pet_services",
                "business_type": "grooming_salon",
                "address": item["address"],
                "working_hours": "Ежедневно 10:00-21:00",
                "phone": item["phone"],
                "email": DEMO_EMAIL,
                "website": "https://localos.pro",
                "owner_id": USER_ID,
                "network_id": NETWORK_ID,
                "is_active": True,
                "subscription_tier": "promo",
                "subscription_status": "active",
                "city": "Санкт-Петербург",
                "country": "Россия",
                "timezone": "Europe/Moscow",
                "latitude": item["lat"],
                "longitude": item["lon"],
                "rating": item["rating"],
                "reviews_count": item["reviews"],
                "categories": ["Груминг", "Зоосалон", "Уход за животными"],
                "yandex_rating": item["rating"],
                "yandex_reviews_total": item["reviews"],
                "yandex_reviews_30d": item["reviews_30d"],
                "yandex_last_sync": now,
                "created_at": now,
                "updated_at": now,
            },
        )


def business_ids():
    return [stable_id(f"business:{item['key']}") for item in LOCATIONS]


def seed_services(cursor):
    service_map = {}
    for location in LOCATIONS:
        business_id = stable_id(f"business:{location['key']}")
        service_map[business_id] = {}
        for index, item in enumerate(SERVICES):
            name, category, description, price, keywords = item
            service_id = stable_id(f"service:{location['key']}:{index}")
            service_map[business_id][name] = service_id
            upsert_row(
                cursor,
                "userservices",
                {
                    "id": service_id,
                    "user_id": USER_ID,
                    "business_id": business_id,
                    "category": category,
                    "name": name,
                    "optimized_name": name,
                    "description": description,
                    "optimized_description": f"{description} DEMO-услуга для показа SEO-прайса грумингового салона.",
                    "keywords": keywords,
                    "price": str(price),
                    "is_active": True,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                },
            )
    return service_map


def seed_masters(cursor):
    master_map = {}
    for location in LOCATIONS:
        business_id = stable_id(f"business:{location['key']}")
        master_map[business_id] = []
        for name in MASTERS:
            master_id = stable_id(f"master:{location['key']}:{name}")
            master_map[business_id].append(master_id)
            upsert_row(
                cursor,
                "masters",
                {
                    "id": master_id,
                    "business_id": business_id,
                    "name": name,
                    "specialization": "Грумер универсал",
                    "created_at": datetime.utcnow(),
                },
            )
    return master_map


def month_dates(month_key):
    year, month = [int(part) for part in month_key.split("-")]
    days = []
    current = date(year, month, 1)
    while current.month == month:
        days.append(current)
        current = current + timedelta(days=1)
    return days


def seed_finance(cursor, service_map, master_map):
    income_categories = [
        ("grooming", 0.68),
        ("addons", 0.16),
        ("retail", 0.09),
        ("packages", 0.07),
    ]
    expense_categories = [
        ("rent", 0.13),
        ("payroll", 0.31),
        ("materials", 0.09),
        ("ads", 0.06),
        ("utilities", 0.035),
        ("software", 0.015),
        ("other", 0.03),
    ]
    rng = random.Random(42)
    for location in LOCATIONS:
        business_id = stable_id(f"business:{location['key']}")
        service_names = list(service_map[business_id].keys())
        for month_key, network_revenue in NETWORK_MONTH_REVENUE.items():
            location_revenue = round(network_revenue * location["revenue_share"], 2)
            for category, share in income_categories:
                amount = round(location_revenue * share, 2)
                upsert_row(
                    cursor,
                    "finance_entries",
                    {
                        "id": stable_id(f"finance-entry:{business_id}:{month_key}:revenue:{category}"),
                        "business_id": business_id,
                        "date": f"{month_key}-28",
                        "type": "revenue",
                        "category": category,
                        "amount": amount,
                        "source": DEMO_SOURCE,
                        "comment": f"DEMO: выручка точки {location['name']} за {month_key}, категория {category}.",
                        "external_id": f"demo:{business_id}:{month_key}:revenue:{category}",
                        "duplicate_key": stable_id(f"dup:{business_id}:{month_key}:revenue:{category}"),
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                    },
                )
            for category, share in expense_categories:
                amount = round(location_revenue * share, 2)
                upsert_row(
                    cursor,
                    "finance_entries",
                    {
                        "id": stable_id(f"finance-entry:{business_id}:{month_key}:expense:{category}"),
                        "business_id": business_id,
                        "date": f"{month_key}-28",
                        "type": "expense",
                        "category": category,
                        "amount": amount,
                        "source": DEMO_SOURCE,
                        "comment": f"DEMO: расход точки {location['name']} за {month_key}, категория {category}.",
                        "external_id": f"demo:{business_id}:{month_key}:expense:{category}",
                        "duplicate_key": stable_id(f"dup:{business_id}:{month_key}:expense:{category}"),
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                    },
                )
            days = month_dates(month_key)
            for tx_index in range(18):
                tx_date = days[(tx_index * 3 + len(location["key"])) % len(days)]
                services = rng.sample(service_names, 2)
                amount = round(location_revenue / 18 * rng.uniform(0.78, 1.24), 2)
                insert_row(
                    cursor,
                    "financialtransactions",
                    {
                        "id": stable_id(f"financial-tx:{business_id}:{month_key}:{tx_index}"),
                        "user_id": USER_ID,
                        "business_id": business_id,
                        "transaction_date": tx_date.isoformat(),
                        "amount": amount,
                        "description": f"DEMO: оплата услуг груминга, {location['name']}",
                        "transaction_type": "income",
                        "client_type": "returning" if tx_index % 3 else "new",
                        "services": json.dumps(services, ensure_ascii=False),
                        "notes": "DEMO: транзакция для сетевого финансового дашборда",
                        "master_id": master_map[business_id][tx_index % len(master_map[business_id])],
                        "created_at": datetime.utcnow(),
                    },
                )


def seed_map_metrics(cursor):
    for location in LOCATIONS:
        business_id = stable_id(f"business:{location['key']}")
        url = f"https://yandex.ru/maps/org/demo_{location['key']}"
        upsert_row(
            cursor,
            "businessmaplinks",
            {
                "id": stable_id(f"maplink:{business_id}"),
                "user_id": USER_ID,
                "business_id": business_id,
                "url": url,
                "map_type": "yandex_maps",
                "created_at": datetime.utcnow(),
            },
        )
        upsert_row(
            cursor,
            "mapparseresults",
            {
                "id": stable_id(f"mapparse:{business_id}"),
                "business_id": business_id,
                "url": url,
                "map_type": "yandex_maps",
                "rating": str(location["rating"]),
                "reviews_count": location["reviews"],
                "unanswered_reviews_count": location["unanswered"],
                "news_count": location["news"],
                "photos_count": location["photos"],
                "services_count": location["services"],
                "analysis_json": {
                    "demo": True,
                    "summary": f"Точка с рейтингом {location['rating']} и разным уровнем заполнения карточки.",
                },
                "products": "Груминг собак, стрижка когтей, вычёсывание кошек, SPA-уход",
                "title": location["name"],
                "address": location["address"],
                "is_verified": True,
                "phone": location["phone"],
                "website": "https://localos.pro",
                "posts_count": location["news"],
                "profile_completeness": 80 if location["rating"] >= 4.6 else 58,
                "created_at": datetime.utcnow(),
            },
        )
        upsert_row(
            cursor,
            "cards",
            {
                "id": stable_id(f"card:{business_id}"),
                "business_id": business_id,
                "user_id": USER_ID,
                "url": url,
                "title": location["name"],
                "address": location["address"],
                "phone": location["phone"],
                "site": "https://localos.pro",
                "rating": location["rating"],
                "reviews_count": location["reviews"],
                "categories": "Груминг, зоосалон, уход за животными",
                "overview": "DEMO: карточка точки сети груминговых салонов.",
                "products": "Груминг собак; стрижка собак; вычёсывание кошек; SPA-уход",
                "news": f"Свежих публикаций: {location['news']}",
                "photos": f"Фото в карточке: {location['photos']}",
                "seo_score": 86 if location["rating"] >= 4.6 else 62,
                "ai_analysis": {"demo": True, "rating": location["rating"], "reviews": location["reviews"]},
                "recommendations": [
                    "Добавить фото входа и ресепшена",
                    "Публиковать новости по сезонным услугам",
                    "Отвечать на отзывы с упоминанием услуг",
                ],
                "version": 1,
                "is_latest": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            },
        )
        for offset in range(6):
            stat_date = date(2026, 1 + offset, 28)
            upsert_row(
                cursor,
                "externalbusinessstats",
                {
                    "id": stable_id(f"external-stat:{business_id}:{stat_date.isoformat()}"),
                    "business_id": business_id,
                    "source": "yandex_business",
                    "date": stat_date.isoformat(),
                    "views_total": int(4200 + location["reviews"] * 4 + offset * 230),
                    "clicks_total": int(360 + location["reviews"] * 0.8 + offset * 28),
                    "actions_total": int(120 + location["reviews"] * 0.35 + offset * 12),
                    "rating": location["rating"],
                    "reviews_total": location["reviews"] + offset * 3,
                    "photos_count": location["photos"],
                    "news_count": location["news"],
                    "unanswered_reviews_count": location["unanswered"],
                    "raw_payload": json.dumps({"demo": True}, ensure_ascii=False),
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                },
            )
        for review_index in range(8):
            rating = 5 if review_index < 5 else 4 if location["rating"] >= 4.3 else 3
            response_text = "" if review_index < min(location["unanswered"], 5) else "Спасибо за отзыв! Будем рады видеть вас снова."
            upsert_row(
                cursor,
                "externalbusinessreviews",
                {
                    "id": stable_id(f"review:{business_id}:{review_index}"),
                    "business_id": business_id,
                    "source": "yandex_business",
                    "external_review_id": f"demo-{location['key']}-{review_index}",
                    "rating": rating,
                    "author_name": CLIENT_NAMES[(review_index + len(location["key"])) % len(CLIENT_NAMES)],
                    "text": "DEMO: отзыв о груминге, аккуратности мастера и удобстве записи.",
                    "published_at": datetime(2026, 6, max(1, 20 - review_index)),
                    "response_text": response_text,
                    "response_at": datetime(2026, 6, 22) if response_text else None,
                    "raw_payload": json.dumps({"demo": True}, ensure_ascii=False),
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                },
            )


def seed_bookings(cursor, service_map, master_map):
    rng = random.Random(7)
    statuses = ["completed", "completed", "completed", "confirmed", "pending", "cancelled"]
    today = date.today()
    for location in LOCATIONS:
        business_id = stable_id(f"business:{location['key']}")
        services = list(service_map[business_id].items())
        for index in range(36):
            if index < 3:
                booking_date = today
                status = "confirmed"
            elif index < 8:
                booking_date = today + timedelta(days=index - 2)
                status = "pending"
            else:
                booking_date = date(2026, 1 + ((index - 8) % 6), 1 + ((index * 3) % 24))
                status = statuses[index % len(statuses)]
            service_name, service_id = services[index % len(services)]
            hour = 10 + (index % 9)
            minute = 0 if index % 2 == 0 else 30
            booking_dt = datetime.combine(booking_date, time(hour, minute))
            client = CLIENT_NAMES[(index + len(location["key"])) % len(CLIENT_NAMES)]
            pet = PET_NAMES[(index * 2 + len(location["key"])) % len(PET_NAMES)]
            insert_row(
                cursor,
                "bookings",
                {
                    "id": stable_id(f"booking:{business_id}:{index}"),
                    "business_id": business_id,
                    "client_phone": f"+7999{rng.randint(1000000, 9999999)}",
                    "client_name": client,
                    "client_email": f"demo-client-{index}@example.invalid",
                    "service_id": service_id,
                    "service_name": service_name,
                    "booking_date": booking_date.isoformat(),
                    "booking_time": booking_dt,
                    "booking_time_local": booking_dt,
                    "source": DEMO_SOURCE,
                    "status": status,
                    "notes": f"DEMO: питомец {pet}. Показательная запись для демо.",
                    "conversation_id": stable_id(f"conversation:{business_id}:{index}"),
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                    "master_id": master_map[business_id][index % len(master_map[business_id])],
                },
            )


def service_price_by_id(business_id, service_map):
    prices = {}
    for name, service_id in service_map[business_id].items():
        for service in SERVICES:
            if service[0] == name:
                prices[service_id] = service[3]
                break
    return prices


def build_matrix(location, service_map):
    business_id = stable_id(f"business:{location['key']}")
    ids_by_name = service_map[business_id]
    pairs = [
        ("Комплексный груминг собак мелких пород в СПб", "SPA-маска для шерсти", "После мытья легче усилить блеск шерсти и вау-эффект.", "during_visit"),
        ("Комплексный груминг собак средних пород", "Уход за лапами и подушечками", "После груминга логично закрыть лапы и подушечки.", "during_visit"),
        ("Комплексный груминг собак крупных пород", "Экспресс-линька для собак", "Крупным породам часто нужен контроль подшёрстка.", "before_visit"),
        ("Гигиеническая стрижка собак", "Стрижка когтей собак и кошек", "Короткая услуга легко добавляется в тот же визит.", "during_visit"),
        ("Модельная стрижка собак по породе", "Фото питомца после груминга", "После модельной стрижки клиенту приятно получить фото.", "checkout"),
        ("Тримминг жесткошёрстных собак", "Домашняя памятка по уходу за шерстью", "После тримминга важно объяснить уход между визитами.", "checkout"),
        ("Экспресс-линька для собак", "Мытьё профессиональной косметикой", "Вычесывание лучше работает вместе с подходящей косметикой.", "before_visit"),
        ("Вычесывание кошек без наркоза", "Антиколтун для собак и кошек", "При вычесывании часто находятся зоны риска по колтунам.", "during_visit"),
        ("Гигиеническая стрижка кошек", "Уход за глазами и мордочкой", "После стрижки можно аккуратно завершить образ мордочки.", "during_visit"),
        ("Стрижка когтей собак и кошек", "Уход за лапами и подушечками", "После когтей удобно предложить защитный уход за лапами.", "during_visit"),
        ("Puppy grooming — первый груминг щенка", "Домашняя памятка по уходу за шерстью", "Владельцам щенка нужны простые рекомендации домой.", "checkout"),
        ("Выставочный груминг собак", "Фото питомца после груминга", "Выставочный образ хорошо фиксируется фото.", "checkout"),
        ("Антиколтун для собак и кошек", "SPA-маска для шерсти", "После разбора колтунов шерсти нужен мягкий восстановительный уход.", "next_visit"),
        ("Мытьё профессиональной косметикой", "Экспресс-линька для собак", "Если есть подшёрсток, линьку стоит предложить до мытья.", "before_visit"),
        ("Уход за лапами и подушечками", "Стрижка когтей собак и кошек", "Лапы и когти воспринимаются клиентом как один понятный блок.", "during_visit"),
    ]
    rows = {}
    for index, pair in enumerate(pairs):
        main_name, addon_name, reason, timing = pair
        if main_name not in ids_by_name or addon_name not in ids_by_name:
            continue
        rows.setdefault(
            main_name,
            {
                "main_service_id": ids_by_name[main_name],
                "main_service": main_name,
                "main_category": "Допродажи",
                "recommended_addons": [],
            },
        )
        rows[main_name]["recommended_addons"].append(
            {
                "id": stable_id(f"avg-link:{business_id}:{index}"),
                "service_id": ids_by_name[addon_name],
                "service": addon_name,
                "category": "Допродажа",
                "price": "",
                "offer_timing": timing,
                "priority": "high" if index < 8 else "medium",
                "compatibility": "same_visit" if timing != "next_visit" else "next_visit",
                "reason": reason,
                "admin_script": f"К этой записи хорошо подходит «{addon_name}». Предложить клиенту добавить к визиту?",
                "master_script": f"После основной услуги можно мягко рекомендовать «{addon_name}»: это усилит результат и уход дома.",
                "expected_effect": "add_on" if timing != "next_visit" else "rebooking",
                "status": "active",
            }
        )
    return {
        "upsell_matrix": list(rows.values()),
        "cross_sell_pairs": [
            {"from_category": "Груминг собак", "to_category": "SPA", "reason": "SPA усиливает визуальный результат после груминга.", "status": "active"},
            {"from_category": "Быстрые услуги", "to_category": "SPA", "reason": "Короткие услуги удобно расширять до ухода за лапами.", "status": "active"},
            {"from_category": "Кошки", "to_category": "Колтуны", "reason": "Для кошек важно отдельно подсвечивать профилактику колтунов.", "status": "active"},
        ],
        "packages": [],
        "risks": ["Не предлагать услуги, если питомцу нужен ветеринарный осмотр.", "Фиксировать отказ без давления на клиента."],
        "implementation_priorities": ["Утвердить активные связки на администраторах.", "Проверять конверсию предложили → купили каждую неделю.", "Сравнивать точки сети по add-on rate."],
        "generation_mode": "demo_seed",
    }


def seed_average_ticket(cursor, service_map):
    ensure_average_ticket_tables(cursor)
    package_templates = [
        ("Щенок первый груминг", ["Puppy grooming — первый груминг щенка", "Стрижка когтей собак и кошек", "Домашняя памятка по уходу за шерстью"], 3200),
        ("Перед выставкой", ["Выставочный груминг собак", "Фото питомца после груминга", "SPA-маска для шерсти"], 7600),
        ("Линька под контроль", ["Экспресс-линька для собак", "Мытьё профессиональной косметикой", "Уход за лапами и подушечками"], 5100),
        ("Кошка без колтунов", ["Вычесывание кошек без наркоза", "Антиколтун для собак и кошек", "Гигиеническая стрижка кошек"], 5900),
        ("Лапы и когти", ["Стрижка когтей собак и кошек", "Уход за лапами и подушечками", "Чистка ушей питомца"], 1700),
    ]
    for location in LOCATIONS:
        business_id = stable_id(f"business:{location['key']}")
        matrix = build_matrix(location, service_map)
        matrix_id = stable_id(f"avg-matrix:{business_id}")
        upsert_row(
            cursor,
            "averageticketmatrices",
            {
                "id": matrix_id,
                "business_id": business_id,
                "status": "active",
                "source_services_hash": stable_id(f"services-hash:{business_id}"),
                "matrix_json": matrix,
                "generated_by": USER_ID,
                "generated_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            },
        )
        prices = service_price_by_id(business_id, service_map)
        for package_index, template in enumerate(package_templates):
            name, service_names, package_price = template
            service_ids = [service_map[business_id][item] for item in service_names if item in service_map[business_id]]
            base_total = sum(prices.get(item, 0) for item in service_ids)
            upsert_row(
                cursor,
                "averageticketpackages",
                {
                    "id": stable_id(f"avg-package:{business_id}:{package_index}"),
                    "business_id": business_id,
                    "name": name,
                    "service_ids": service_ids,
                    "service_names": service_names,
                    "base_total": base_total,
                    "package_price": package_price,
                    "bonus_text": "DEMO: пакетная цена и понятная выгода для клиента.",
                    "positioning": f"{name}: готовое предложение для владельца питомца.",
                    "script": f"У нас есть пакет «{name}»: несколько услуг вместе дешевле и удобнее, чем записываться отдельно.",
                    "status": "active",
                    "created_by": USER_ID,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                },
            )
        links = []
        for row in matrix["upsell_matrix"]:
            links.extend(row["recommended_addons"])
        for event_index in range(18):
            link = links[event_index % len(links)]
            event_type = "bought" if event_index % 3 == 0 else "offered" if event_index % 3 == 1 else "declined"
            upsert_row(
                cursor,
                "averageticketevents",
                {
                    "id": stable_id(f"avg-event:{business_id}:{event_index}"),
                    "business_id": business_id,
                    "matrix_id": matrix_id,
                    "link_id": link["id"],
                    "booking_id": stable_id(f"booking:{business_id}:{event_index}"),
                    "main_service_id": matrix["upsell_matrix"][event_index % len(matrix["upsell_matrix"])]["main_service_id"],
                    "addon_service_id": link["service_id"],
                    "event_type": event_type,
                    "event_date": (date.today() - timedelta(days=event_index % 30)).isoformat(),
                    "amount": 1200 if event_type == "bought" else None,
                    "client_name": CLIENT_NAMES[event_index % len(CLIENT_NAMES)],
                    "notes": "DEMO: событие допродажи",
                    "created_by": USER_ID,
                    "created_at": datetime.utcnow(),
                },
            )


def seed_partners(cursor):
    parent_business_id = NETWORK_ID
    for index, partner in enumerate(PARTNERS):
        name, category, status, stage = partner
        lead_id = stable_id(f"partner:{index}:{name}")
        upsert_row(
            cursor,
            "prospectingleads",
            {
                "id": lead_id,
                "name": name,
                "address": f"Санкт-Петербург, демо-адрес партнёра, {index + 1}",
                "city": "Санкт-Петербург",
                "phone": f"+7812{1000000 + index}",
                "website": f"https://example.invalid/partner-{index}",
                "email": f"partner-{index}@example.invalid",
                "rating": round(4.1 + (index % 5) * 0.15, 1),
                "reviews_count": 40 + index * 17,
                "source_url": f"https://yandex.ru/maps/org/demo_partner_{index}",
                "source": DEMO_SOURCE,
                "source_external_id": f"demo-grooming:partner:{index}",
                "category": category,
                "status": status,
                "pipeline_status": status,
                "selected_channel": "email",
                "business_id": parent_business_id,
                "intent": "partnership_outreach",
                "partnership_stage": stage,
                "description": "DEMO: выдуманный партнёр для показа воронки партнёрств.",
                "services_json": [
                    {"name": category, "price": ""},
                    {"name": "Партнёрское предложение", "price": ""},
                ],
                "raw_payload_json": {"demo": True},
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            },
        )
        draft_text = (
            f"Здравствуйте!\n\n"
            f"Мы — сеть груминговых салонов «{NETWORK_NAME}» в Санкт-Петербурге. "
            f"Подумали, что у нас может быть общая аудитория: владельцы домашних животных рядом с вашими клиентами.\n\n"
            f"Можно протестировать простое партнёрское предложение: уход за питомцем у нас и услуга направления «{category}» у вас.\n\n"
            f"Для удобства подготовили цифровую комнату и можем обсудить формат, который не требует сложной интеграции.\n\n"
            f"С кем можно обсудить такой вариант?"
        )
        upsert_row(
            cursor,
            "outreachmessagedrafts",
            {
                "id": stable_id(f"partner-draft:{lead_id}"),
                "lead_id": lead_id,
                "channel": "email",
                "angle_type": "partnership_first_note",
                "tone": "friendly",
                "status": "approved" if stage in {"approved", "sent", "positive_reply", "partner"} else "generated",
                "generated_text": draft_text,
                "edited_text": draft_text,
                "approved_text": draft_text if stage in {"approved", "sent", "positive_reply", "partner"} else None,
                "learning_note_json": {"demo": True, "pattern": "grooming_pet_services"},
                "created_by": USER_ID,
                "approved_by": USER_ID if stage in {"approved", "sent", "positive_reply", "partner"} else None,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            },
        )
        upsert_row(
            cursor,
            "partnershipleadartifacts",
            {
                "lead_id": lead_id,
                "audit_json": {"demo": True, "fit": "owner_pet_audience", "category": category},
                "match_json": {"score": 78 + index, "reason": "Пересечение по аудитории владельцев животных."},
                "offer_draft_json": {"draft_text": draft_text, "type": "first_note"},
                "updated_at": datetime.utcnow(),
            },
            conflict_key="lead_id",
        )


def apply_seed(args):
    password = demo_password()
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        ensure_bookings_table(cursor)
        ensure_average_ticket_tables(cursor)
        backup_path = write_backup(cursor, Path(args.backup_dir))
        refresh_demo_area(cursor)
        seed_user_network_businesses(cursor, password)
        service_map = seed_services(cursor)
        master_map = seed_masters(cursor)
        seed_finance(cursor, service_map, master_map)
        seed_map_metrics(cursor)
        seed_bookings(cursor, service_map, master_map)
        seed_average_ticket(cursor, service_map)
        seed_partners(cursor)
        conn.commit()
        print("DEMO_GROOMING_NETWORK_APPLIED")
        print(f"email={DEMO_EMAIL}")
        print(f"password={password}")
        print(f"user_id={USER_ID}")
        print(f"network_id={NETWORK_ID}")
        print(f"backup={backup_path}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def dry_run():
    print("DEMO_GROOMING_NETWORK_DRY_RUN")
    print(json.dumps(planned_counts(), ensure_ascii=False, indent=2))
    print(f"email={DEMO_EMAIL}")
    print(f"user_id={USER_ID}")
    print(f"network_id={NETWORK_ID}")
    print("No database writes were performed.")


def parse_args():
    parser = argparse.ArgumentParser(description="Seed LocalOS demo grooming network account.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Print planned data without database writes.")
    mode.add_argument("--apply", action="store_true", help="Apply seed data to DATABASE_URL.")
    parser.add_argument("--backup-dir", default=str(repo_root / "debug_data"), help="Directory for JSON backups before refresh.")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.dry_run:
        dry_run()
        return
    apply_seed(args)


if __name__ == "__main__":
    main()
