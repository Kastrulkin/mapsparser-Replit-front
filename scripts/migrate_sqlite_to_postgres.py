#!/usr/bin/env python3
"""
Одноразовый перенос данных SQLite → PostgreSQL.
Идемпотентен: ON CONFLICT (id) DO NOTHING. Порядок по FK: users → businesses → остальные.

Источники (два варианта):

1) Один файл — всё в одном:
   SQLITE_PATH=/path/to/db  (users, businesses, MapParseResults и т.д.)

2) Два файла — пользователи/бизнесы отдельно от парсингов:
   SQLITE_PATH_MAIN=/path/to/main.db     — Users, Businesses, Networks, ParseQueue, BusinessMapLinks, UserServices
   SQLITE_PATH_PARSING=/path/to/parsing.db — MapParseResults → cards

   Если задан только SQLITE_PATH — используется для всех таблиц.

Пример запуска в Docker (всё из одного файла):
  docker compose run --rm -v "$(pwd)/scripts:/app/scripts" -v "$(pwd)/src:/app/src" \\
    -e SQLITE_PATH=/app/server_reports.db app python scripts/migrate_sqlite_to_postgres.py

Пример с двумя источниками (users/businesses из main, парсинги из parsing):
  docker compose run --rm -v "$(pwd)/scripts:/app/scripts" -v "$(pwd)/src:/app/src" -v "$(pwd)/data:/app/data" \\
    -e SQLITE_PATH_MAIN=/app/data/server_reports.db -e SQLITE_PATH_PARSING=/app/data/legacy.sqlite \\
    app python scripts/migrate_sqlite_to_postgres.py

Режимы:
  --dry-run          только счётчики, без INSERT
  --tables a,b,c     мигрировать только указанные таблицы (имена в Postgres: users, businesses, ...)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Порядок таблиц по FK (Postgres lowercase). Только те, что есть в Alembic/архитектуре.
MIGRATION_ORDER = [
    "users",
    "usersessions",
    "networks",
    "businesses",
    "businessprofiles",
    "parsequeue",
    "businessmaplinks",
    "userservices",
    "externalbusinessaccounts",
    "externalbusinessreviews",
    "externalbusinessstats",
    "financialtransactions",
    "financialmetrics",
    "cards",
    "screenshot_analyses",
]

# SQLite имя (как в sqlite_master) → Postgres имя
SQLITE_TO_PG = {
    "Users": "users",
    "UserSessions": "usersessions",
    "Networks": "networks",
    "Businesses": "businesses",
    "BusinessProfiles": "businessprofiles",
    "ParseQueue": "parsequeue",
    "BusinessMapLinks": "businessmaplinks",
    "UserServices": "userservices",
    "ExternalBusinessAccounts": "externalbusinessaccounts",
    "ExternalBusinessReviews": "externalbusinessreviews",
    "ExternalBusinessStats": "externalbusinessstats",
    "FinancialTransactions": "financialtransactions",
    "FinancialMetrics": "financialmetrics",
    "Cards": "cards",
    "ScreenshotAnalyses": "screenshot_analyses",
    "MapParseResults": "cards",
}

# Колонки SQLite → PG (если имена различаются)
COLUMN_ALIASES = {
    "financialtransactions": {"date": "transaction_date"},
}

# Значения по умолчанию для NULL (Postgres NOT NULL без default)
DEFAULT_NULL_VALUES = {
    ("users", "is_verified"): True,
    ("users", "is_superadmin"): False,
}


def _normalize_path(path: str) -> str:
    if path.startswith("file:"):
        path = re.sub(r"^file:(?://)?", "", path)
    return path.strip()


def get_sqlite_path_main() -> str:
    """Путь к основной БД: Users, Businesses, Networks, ParseQueue, BusinessMapLinks, UserServices."""
    path = os.getenv("SQLITE_PATH_MAIN") or os.getenv("SQLITE_PATH") or os.getenv("SQLITE_URL")
    if path:
        return _normalize_path(path)
    return str(SRC_DIR / "reports.db")


def get_sqlite_path_parsing() -> str:
    """Путь к БД с парсингами: MapParseResults → cards."""
    path = os.getenv("SQLITE_PATH_PARSING") or os.getenv("SQLITE_PATH_MAIN") or os.getenv("SQLITE_PATH") or os.getenv("SQLITE_URL")
    if path:
        return _normalize_path(path)
    return str(SRC_DIR / "reports.db")


def get_sqlite_connection(path: str | None = None):
    import sqlite3
    p = path or get_sqlite_path_main()
    if not os.path.isfile(p):
        raise FileNotFoundError(f"SQLite DB not found: {p}")
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    return conn


def get_pg_connection():
    import psycopg2
    from psycopg2.extras import RealDictCursor
    url = os.getenv("DATABASE_URL")
    if not url:
        raise ValueError("DATABASE_URL is not set")
    return psycopg2.connect(url, cursor_factory=RealDictCursor)


def sqlite_table_list(conn) -> list[str]:
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    return [r[0] for r in cur.fetchall()]


def sqlite_columns(conn, table: str) -> list[tuple[str, str]]:
    cur = conn.cursor()
    cur.execute(f'PRAGMA table_info("{table}")')
    if not cur.description:
        return []
    rows = cur.fetchall()
    return [(r[1], (r[2] or "").upper()) for r in rows]


def pg_table_exists(conn, table: str) -> bool:
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = %s",
        (table,),
    )
    return cur.fetchone() is not None


def pg_columns(conn, table: str) -> list[str]:
    cur = conn.cursor()
    cur.execute(
        """SELECT column_name FROM information_schema.columns
           WHERE table_schema = 'public' AND table_name = %s ORDER BY ordinal_position""",
        (table,),
    )
    return [r["column_name"] for r in cur.fetchall()]


def pg_column_types(conn, table: str) -> dict[str, str]:
    """Возвращает { column_name: data_type } для целевой таблицы Postgres (jsonb, real, integer, boolean и т.д.)."""
    cur = conn.cursor()
    cur.execute(
        """SELECT column_name, data_type, udt_name
           FROM information_schema.columns
           WHERE table_schema = 'public' AND table_name = %s ORDER BY ordinal_position""",
        (table,),
    )
    out = {}
    for r in cur.fetchall():
        name = r["column_name"]
        data_type = (r["data_type"] or "").lower()
        udt = (r.get("udt_name") or "").lower()
        if data_type in ("json", "jsonb"):
            out[name] = "json"
        elif data_type in ("real", "double precision") or udt == "float4" or udt == "float8":
            out[name] = "real"
        elif data_type in ("numeric", "decimal"):
            out[name] = "numeric"
        elif data_type in ("smallint", "integer", "bigint") or "int" in data_type:
            out[name] = "integer"
        elif data_type == "boolean":
            out[name] = "boolean"
        elif data_type in ("timestamp without time zone", "timestamp with time zone", "date", "time"):
            out[name] = "timestamp"
        else:
            out[name] = data_type or "text"
    return out


def pg_existing_ids(conn, table: str, id_column: str = "id") -> set[str]:
    """Возвращает множество ID как строк для корректного сравнения с SQLite (UUID vs string)."""
    cur = conn.cursor()
    cur.execute(f'SELECT "{id_column}" FROM "{table}"')
    out = set()
    for r in cur.fetchall():
        v = r[id_column]
        if v is not None:
            s = str(v).strip()
            if s:
                out.add(s)
    return out


def pg_user_id_by_email(conn) -> dict[str, str]:
    """Возвращает { email: id } для существующих users в Postgres (id как строка)."""
    cur = conn.cursor()
    cur.execute("SELECT id, email FROM users WHERE email IS NOT NULL AND email != ''")
    return {r["email"]: str(r["id"]) for r in cur.fetchall()}


def _normalize_json_for_pg(val) -> tuple[object, bool]:
    """
    Нормализация значения для колонки json/jsonb.
    Возвращает (значение для вставки — строка JSON или None, json_fixed).
    Для psycopg2 jsonb можно передать строку с валидным JSON или объект (будет сериализован).
    """
    if val is None:
        return None, False
    if isinstance(val, (dict, list)):
        return json.dumps(val, ensure_ascii=False), False
    s = str(val).strip()
    if s == "":
        return None, False
    # Уже валидный JSON
    if (s.startswith("{") or s.startswith("[")) and len(s) > 1:
        try:
            json.loads(s)
            return s, False
        except (json.JSONDecodeError, TypeError):
            pass
    # Список через запятую → JSON-массив
    if "," in s and not s.startswith("{"):
        parts = [p.strip() for p in s.split(",") if p.strip()]
        return json.dumps(parts, ensure_ascii=False), True
    # Иначе — одна строка как JSON-значение
    return json.dumps(s, ensure_ascii=False), True


def _normalize_numeric_for_pg(val, pg_type: str) -> tuple[object, bool]:
    """Пустая строка или пробелы → NULL для real/numeric/integer. Возвращает (value, null_fixed)."""
    if val is None:
        return None, False
    if isinstance(val, str):
        if val.strip() == "":
            return None, True
        try:
            if pg_type == "integer":
                return int(float(val)), False
            if pg_type == "real":
                return float(val), False
            if pg_type == "numeric":
                return float(val), False
        except (ValueError, TypeError):
            return None, True
    if isinstance(val, (int, float)):
        if pg_type == "integer":
            return int(val), False
        if pg_type in ("real", "numeric"):
            return float(val), False
    return val, False


def coerce_value(val, col_type: str, bool_columns: set) -> object:
    if val is None:
        return None
    if col_type and "INT" in col_type and isinstance(val, (bool, float)):
        if isinstance(val, bool):
            return 1 if val else 0
        return int(val) if val == int(val) else val
    if col_type and "INT" in col_type and isinstance(val, str) and val.strip() == "":
        return None
    if col_type and "REAL" in col_type and isinstance(val, str) and val.strip() == "":
        return None
    return val


def normalize_bool(val) -> bool | None:
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    if isinstance(val, int):
        return bool(val)
    if isinstance(val, str):
        return val.strip().lower() in ("1", "true", "yes", "on")
    return bool(val)


def _row_dict_with_aliases(row_dict: dict, pg_table: str) -> dict:
    """Применить COLUMN_ALIASES: подставить значение под именем колонки PG."""
    aliases = COLUMN_ALIASES.get(pg_table, {})
    out = dict(row_dict)
    for sqlite_col, pg_col in aliases.items():
        if sqlite_col in out and pg_col not in out:
            out[pg_col] = out[sqlite_col]
    return out


def migrate_table(
    sqlite_conn,
    pg_conn,
    sqlite_table: str,
    pg_table: str,
    dry_run: bool,
    owner_id_map: dict | None,
    pg_business_ids: set | None,
    pg_user_ids: set | None,
    pg_network_ids: set | None = None,
) -> tuple[int, int, int, int, int]:
    """
    Возвращает (found, inserted, skipped, json_fixed_count, null_fixed_count).
    owner_id_map: sqlite user id -> pg user id (для строк, пропущенных из-за дубликата email); только для businesses.
    """
    found = 0
    inserted = 0
    skipped = 0
    json_fixed_count = 0
    null_fixed_count = 0

    try:
        cur_sqlite = sqlite_conn.cursor()
        cur_sqlite.execute(f'SELECT * FROM "{sqlite_table}"')
        rows = cur_sqlite.fetchall()
    except Exception as e:
        print(f"   ⚠️ SQLite read error: {e}")
        return 0, 0, 0, 0, 0

    if not rows:
        return 0, 0, 0, 0, 0

    found = len(rows)
    sqlite_cols = [d[0] for d in cur_sqlite.description]
    sqlite_col_types = {d[0]: (d[1] or "").upper() for d in cur_sqlite.description}

    if not pg_table_exists(pg_conn, pg_table):
        print(f"   ⚠️ Table {pg_table} not found in Postgres, skip")
        return found, 0, found, 0, 0

    pg_cols = pg_columns(pg_conn, pg_table)
    if not pg_cols:
        return found, 0, found, 0, 0

    pg_col_types = pg_column_types(pg_conn, pg_table)
    aliases = COLUMN_ALIASES.get(pg_table, {})
    pg_to_sqlite_col = {c: c for c in pg_cols if c in sqlite_cols or c.lower() in {x.lower() for x in sqlite_cols}}
    for sq, pg in aliases.items():
        pg_to_sqlite_col[pg] = sq
    pg_common = [c for c in pg_cols if c.lower() in {x.lower() for x in sqlite_cols} or c in aliases.values()]
    # cards: is_latest может отсутствовать в SQLite — добавляем явно (DEFAULT TRUE даёт нарушение uq)
    if pg_table == "cards" and "is_latest" in pg_cols and "is_latest" not in [c.lower() for c in pg_common]:
        pg_common = list(pg_common) + ["is_latest"]
    if not pg_common or "id" not in [c.lower() for c in pg_common]:
        return found, 0, found, 0, 0

    bool_cols = set()
    for c in pg_common:
        src = pg_to_sqlite_col.get(c, c)
        ti = sqlite_col_types.get(src) or ""
        if "BOOL" in ti or c.lower() in ("is_active", "is_latest", "is_superadmin", "is_verified", "captcha_required", "resume_requested"):
            bool_cols.add(c)

    existing_pg_ids = set() if dry_run else pg_existing_ids(pg_conn, pg_table)
    to_insert = []

    latest_card_ids = set()
    if pg_table == "cards":
        pg_latest_business_ids = set()
        try:
            cur = pg_conn.cursor()
            cur.execute('SELECT business_id FROM cards WHERE is_latest IS TRUE')
            pg_latest_business_ids = {str(r.get("business_id") or "") for r in cur.fetchall() if r.get("business_id")}
        except Exception:
            pass
        latest_per_business = {}
        for row in rows:
            d = dict(row)
            bid = str(d.get("business_id") or d.get("business_Id") or "")
            if bid in pg_latest_business_ids:
                continue
            created = str(d.get("created_at") or d.get("id") or "")
            cid = str(d.get("id") or d.get("ID") or "")
            if bid and (bid not in latest_per_business or created > latest_per_business[bid][0]):
                latest_per_business[bid] = (created, cid)
        latest_card_ids = {v[1] for v in latest_per_business.values()}

    for row in rows:
        row_dict = _row_dict_with_aliases(dict(row), pg_table)
        pk_val = row_dict.get("id") or row_dict.get("ID")
        if pk_val is None:
            skipped += 1
            continue
        pk_str = str(pk_val).strip()
        if not pk_str:
            skipped += 1
            continue

        if pg_table == "businesses" and pg_business_ids is not None and pk_str in pg_business_ids:
            skipped += 1
            continue
        if pg_table == "users" and pg_user_ids is not None and pk_str in pg_user_ids:
            skipped += 1
            continue
        if pk_str in existing_pg_ids:
            skipped += 1
            continue

        owner_id = row_dict.get("owner_id") or row_dict.get("owner_Id")
        business_id = row_dict.get("business_id") or row_dict.get("business_Id")
        owner_str = str(owner_id).strip() if owner_id is not None else ""
        if pg_table == "businesses" and owner_str and pg_user_ids is not None:
            if owner_str not in pg_user_ids and owner_id_map and owner_str in owner_id_map:
                row_dict = dict(row_dict)
                row_dict["owner_id"] = owner_id_map[owner_str]

        if pg_table == "businesses" and pg_network_ids is not None:
            nid = row_dict.get("network_id") or row_dict.get("network_Id")
            if nid is not None and str(nid).strip() not in pg_network_ids:
                row_dict = dict(row_dict)
                row_dict["network_id"] = None

        # cards: всегда вставляем с is_latest=false, потом UPDATE для latest (избегаем uq_cards_latest_per_business)
        if pg_table == "cards":
            row_dict = dict(row_dict)
            row_dict["is_latest"] = False

        if pg_table != "users" and pg_table != "businesses":
            if business_id is not None and pg_business_ids is not None:
                if str(business_id).strip() not in pg_business_ids:
                    skipped += 1
                    continue
            if pg_table in ("parsequeue", "businessmaplinks", "userservices") and business_id is not None and pg_business_ids is not None:
                if str(business_id).strip() not in pg_business_ids:
                    skipped += 1
                    continue
            if owner_id is not None and pg_user_ids is not None:
                effective_owner = owner_id_map.get(owner_str, owner_str) if owner_id_map else owner_str
                if effective_owner not in pg_user_ids:
                    skipped += 1
                    continue
            if pg_table == "businesses" and owner_str and pg_user_ids is not None:
                effective_owner = row_dict.get("owner_id") or owner_str
                if effective_owner not in pg_user_ids:
                    skipped += 1
                    continue

        values = []
        row_json_fixed = 0
        row_null_fixed = 0
        for col in pg_common:
            val = row_dict.get(col) or row_dict.get(col.replace("_", ""))
            # cards: принудительно is_latest=false при вставке (UPDATE — после)
            if pg_table == "cards" and col == "is_latest":
                val = False
            pg_type = pg_col_types.get(col, "text")
            if col in bool_cols:
                val = normalize_bool(val)
                if val is None and (pg_table, col) in DEFAULT_NULL_VALUES:
                    val = DEFAULT_NULL_VALUES[(pg_table, col)]
            elif pg_type == "json":
                val, jf = _normalize_json_for_pg(val)
                if jf:
                    row_json_fixed += 1
            elif pg_type in ("real", "numeric", "integer"):
                val, nf = _normalize_numeric_for_pg(val, pg_type)
                if nf:
                    row_null_fixed += 1
            else:
                src_col = pg_to_sqlite_col.get(col, col)
                val = coerce_value(val, sqlite_col_types.get(src_col, ""), bool_cols)
                if val is not None and isinstance(val, str) and val.strip() == "" and pg_type in ("real", "numeric", "integer"):
                    val = None
                    row_null_fixed += 1
            if isinstance(val, (bytes, bytearray)):
                val = val.decode("utf-8", errors="replace")
            values.append(val)
        json_fixed_count += row_json_fixed
        null_fixed_count += row_null_fixed

        to_insert.append((pk_str, tuple(values)))
        existing_pg_ids.add(pk_str)
        inserted += 1

    if dry_run or not to_insert:
        return found, inserted, skipped, json_fixed_count, null_fixed_count

    cols_str = ", ".join(f'"{c}"' for c in pg_common)
    placeholders = ", ".join("%s" for _ in pg_common)
    sql = f'INSERT INTO "{pg_table}" ({cols_str}) VALUES ({placeholders}) ON CONFLICT (id) DO NOTHING'
    cur_pg = pg_conn.cursor()
    insert_ok = 0
    insert_fail = 0
    for pk_str, v in to_insert:
        try:
            cur_pg.execute("SAVEPOINT sp_row")
            cur_pg.execute(sql, v)
            cur_pg.execute("RELEASE SAVEPOINT sp_row")
            insert_ok += 1
        except Exception as e:
            cur_pg.execute("ROLLBACK TO SAVEPOINT sp_row")
            try:
                cur_pg.execute("RELEASE SAVEPOINT sp_row")
            except Exception:
                pass
            insert_fail += 1
            err_msg = str(e).split("\n")[0]
            print(f"   ⚠️ Row insert error table={pg_table} id={pk_str}: {err_msg}")
    # cards: после вставки всех с is_latest=false — обновить latest на true
    if pg_table == "cards" and latest_card_ids and not dry_run:
        try:
            cur = pg_conn.cursor()
            cur.execute(
                "UPDATE cards SET is_latest = TRUE WHERE id IN %s",
                (tuple(latest_card_ids),),
            )
            pg_conn.commit()
        except Exception as e:
            pg_conn.rollback()
            print(f"   ⚠️ Cards is_latest UPDATE error: {e}")
    else:
        pg_conn.commit()
    if insert_fail:
        print(f"   ℹ️ {pg_table}: inserted={insert_ok}, failed={insert_fail} (errors isolated by SAVEPOINT)")
    return found, insert_ok, skipped + insert_fail, json_fixed_count, null_fixed_count


def main():
    parser = argparse.ArgumentParser(description="Migrate SQLite data to PostgreSQL")
    parser.add_argument("--dry-run", action="store_true", help="Only count, no INSERT")
    parser.add_argument("--tables", type=str, default="", help="Comma-separated list of Postgres table names to migrate")
    args = parser.parse_args()

    raw_tables = [t.strip().lower() for t in args.tables.split(",") if t.strip()] if args.tables else None
    tables_filter = None
    if raw_tables:
        tables_filter = set(raw_tables)
        if "services" in tables_filter:
            tables_filter.add("userservices")

    print("=" * 60)
    print("SQLite → PostgreSQL migration")
    print("=" * 60)
    main_path = get_sqlite_path_main()
    parsing_path = get_sqlite_path_parsing()
    if main_path == parsing_path:
        print(f"SQLite: {main_path} (один источник)")
    else:
        print(f"SQLite main (users/businesses): {main_path}")
        print(f"SQLite parsing (cards): {parsing_path}")
    print("Postgres: from DATABASE_URL")

    try:
        main_conn = get_sqlite_connection(main_path)
        main_conn.execute("SELECT 1")
        parsing_conn = get_sqlite_connection(parsing_path) if parsing_path != main_path else main_conn
        if parsing_conn is not main_conn:
            parsing_conn.execute("SELECT 1")
        print("✅ SQLite connection(s) OK")
    except Exception as e:
        print(f"❌ SQLite: {e}")
        sys.exit(1)

    try:
        pg_conn = get_pg_connection()
        pg_conn.cursor().execute("SELECT 1")
        print("✅ Postgres connection OK")
    except Exception as e:
        print(f"❌ Postgres: {e}")
        sys.exit(1)

    main_tables = sqlite_table_list(main_conn)
    parsing_tables = sqlite_table_list(parsing_conn) if parsing_conn is not main_conn else main_tables
    main_lower = {t.lower(): t for t in main_tables}
    parsing_lower = {t.lower(): t for t in parsing_tables}
    pg_tables_in_order = [t for t in MIGRATION_ORDER if (tables_filter is None or t in tables_filter)]

    reverse_map = {}
    for sqlite_name, pg_name in SQLITE_TO_PG.items():
        tables = parsing_tables if pg_name == "cards" else main_tables
        lower = parsing_lower if pg_name == "cards" else main_lower
        if sqlite_name in tables or sqlite_name.lower() in lower:
            reverse_map[pg_name] = lower.get(sqlite_name.lower()) or sqlite_name

    if not reverse_map and not main_tables and not parsing_tables:
        print("⚠️ No tables in SQLite")
        main_conn.close()
        if parsing_conn is not main_conn:
            parsing_conn.close()
        pg_conn.close()
        return

    def conn_for_table(pg_t: str):
        return parsing_conn if pg_t == "cards" else main_conn

    email_to_pg_id = pg_user_id_by_email(pg_conn)
    pg_user_ids = pg_existing_ids(pg_conn, "users")
    pg_business_ids = set()
    owner_id_map = {}

    for pg_table in pg_tables_in_order:
        sqlite_table = reverse_map.get(pg_table)
        if not sqlite_table:
            tbl, low = (parsing_tables, parsing_lower) if pg_table == "cards" else (main_tables, main_lower)
            for sq_name, pg_name in SQLITE_TO_PG.items():
                if pg_name == pg_table and (sq_name in tbl or sq_name.lower() in low):
                    sqlite_table = low.get(sq_name.lower()) or sq_name
                    break
        if not sqlite_table:
            print(f"  {pg_table}: — (no source in SQLite)")
            continue

        if pg_table == "businesses":
            pg_business_ids = pg_existing_ids(pg_conn, "businesses")

        pg_network_ids = None
        if pg_table == "businesses" and pg_table_exists(pg_conn, "networks"):
            pg_network_ids = pg_existing_ids(pg_conn, "networks")

        found, inserted, skipped, json_fixed, null_fixed = migrate_table(
            conn_for_table(pg_table),
            pg_conn,
            sqlite_table,
            pg_table,
            dry_run=args.dry_run,
            owner_id_map=owner_id_map if pg_table == "businesses" else None,
            pg_business_ids=pg_business_ids if pg_table not in ("users", "businesses") else None,
            pg_user_ids=pg_user_ids,
            pg_network_ids=pg_network_ids,
        )
        line = f"  {pg_table}: found={found}, inserted={inserted}, skipped={skipped}"
        if json_fixed or null_fixed:
            line += f" | json_fixed={json_fixed}, null_fixed={null_fixed}"
        print(line)

        if pg_table == "users" and not args.dry_run:
            pg_user_ids = pg_existing_ids(pg_conn, "users")
            cur = main_conn.cursor()
            try:
                cur.execute(f'SELECT id, email FROM "{sqlite_table}"')
                for r in cur.fetchall():
                    sid, email = (r[0], (r[1] or "").strip()) if hasattr(r, "keys") else (r[0], (r[1] or "").strip())
                    if email and email in email_to_pg_id:
                        owner_id_map[str(sid)] = email_to_pg_id[email]
            except Exception:
                pass
        if pg_table == "businesses" and not args.dry_run:
            pg_business_ids = pg_existing_ids(pg_conn, "businesses")

    print("=" * 60)
    print("Done." if not args.dry_run else "Dry-run done (no data written).")
    main_conn.close()
    if parsing_conn is not main_conn:
        parsing_conn.close()
    pg_conn.close()


if __name__ == "__main__":
    main()
