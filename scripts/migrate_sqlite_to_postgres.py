#!/usr/bin/env python3
"""
Одноразовый перенос данных SQLite → PostgreSQL.
Идемпотентен: ON CONFLICT (id) DO NOTHING. Порядок по FK: users → businesses → остальные.
Источники: SQLITE_PATH или SQLITE_URL (SQLite), DATABASE_URL (Postgres).

Пример запуска в Docker:
  docker compose exec -e SQLITE_PATH=/app/legacy.sqlite app python scripts/migrate_sqlite_to_postgres.py

Локально:
  SQLITE_PATH=./src/reports.db DATABASE_URL=postgresql://user:pass@localhost/db python scripts/migrate_sqlite_to_postgres.py

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
    "businesses",
    "parsequeue",
    "businessmaplinks",
    "userservices",
    "financialtransactions",
    "financialmetrics",
    "cards",
    "screenshot_analyses",
]

# SQLite имя (как в sqlite_master) → Postgres имя
SQLITE_TO_PG = {
    "Users": "users",
    "Businesses": "businesses",
    "ParseQueue": "parsequeue",
    "BusinessMapLinks": "businessmaplinks",
    "UserServices": "userservices",
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


def get_sqlite_path() -> str:
    path = os.getenv("SQLITE_PATH") or os.getenv("SQLITE_URL")
    if path:
        if path.startswith("file:"):
            path = re.sub(r"^file:(?://)?", "", path)
        return path.strip()
    return str(SRC_DIR / "reports.db")


def get_sqlite_connection():
    import sqlite3
    path = get_sqlite_path()
    if not os.path.isfile(path):
        raise FileNotFoundError(f"SQLite DB not found: {path}")
    conn = sqlite3.connect(path)
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


def pg_existing_ids(conn, table: str, id_column: str = "id") -> set:
    cur = conn.cursor()
    cur.execute(f'SELECT "{id_column}" FROM "{table}"')
    return {r[id_column] for r in cur.fetchall()}


def pg_user_id_by_email(conn) -> dict[str, str]:
    """Возвращает { email: id } для существующих users в Postgres."""
    cur = conn.cursor()
    cur.execute("SELECT id, email FROM users WHERE email IS NOT NULL AND email != ''")
    return {r["email"]: r["id"] for r in cur.fetchall()}


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
            pg_type = pg_col_types.get(col, "text")
            if col in bool_cols:
                val = normalize_bool(val)
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
    sqlite_path = get_sqlite_path()
    print(f"SQLite: {sqlite_path}")
    print(f"Postgres: from DATABASE_URL")

    try:
        sqlite_conn = get_sqlite_connection()
        sqlite_conn.execute("SELECT 1")
        print("✅ SQLite connection OK")
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

    sqlite_tables = sqlite_table_list(sqlite_conn)
    sqlite_lower = {t.lower(): t for t in sqlite_tables}
    pg_tables_in_order = [t for t in MIGRATION_ORDER if (tables_filter is None or t in tables_filter)]

    reverse_map = {}
    for sqlite_name, pg_name in SQLITE_TO_PG.items():
        if sqlite_name in sqlite_tables or sqlite_name.lower() in sqlite_lower:
            reverse_map[pg_name] = sqlite_lower.get(sqlite_name.lower()) or sqlite_name

    if not reverse_map and not sqlite_tables:
        print("⚠️ No tables in SQLite")
        sqlite_conn.close()
        pg_conn.close()
        return

    email_to_pg_id = pg_user_id_by_email(pg_conn)
    pg_user_ids = pg_existing_ids(pg_conn, "users")
    pg_business_ids = set()
    owner_id_map = {}

    for pg_table in pg_tables_in_order:
        sqlite_table = reverse_map.get(pg_table)
        if not sqlite_table:
            for sq_name, pg_name in SQLITE_TO_PG.items():
                if pg_name == pg_table and (sq_name in sqlite_tables or sq_name.lower() in sqlite_lower):
                    sqlite_table = sqlite_lower.get(sq_name.lower()) or sq_name
                    break
        if not sqlite_table:
            print(f"  {pg_table}: — (no source in SQLite)")
            continue

        if pg_table == "businesses":
            pg_business_ids = pg_existing_ids(pg_conn, "businesses")

        found, inserted, skipped, json_fixed, null_fixed = migrate_table(
            sqlite_conn,
            pg_conn,
            sqlite_table,
            pg_table,
            dry_run=args.dry_run,
            owner_id_map=owner_id_map if pg_table == "businesses" else None,
            pg_business_ids=pg_business_ids if pg_table not in ("users", "businesses") else None,
            pg_user_ids=pg_user_ids,
        )
        line = f"  {pg_table}: found={found}, inserted={inserted}, skipped={skipped}"
        if json_fixed or null_fixed:
            line += f" | json_fixed={json_fixed}, null_fixed={null_fixed}"
        print(line)

        if pg_table == "users" and not args.dry_run:
            pg_user_ids = pg_existing_ids(pg_conn, "users")
            cur = sqlite_conn.cursor()
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
    sqlite_conn.close()
    pg_conn.close()


if __name__ == "__main__":
    main()
