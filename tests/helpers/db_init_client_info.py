"""
Минимальный набор таблиц для gate-тестов /api/client-info.
Все имена таблиц и колонок в lowercase, placeholders %s.
"""
from __future__ import annotations

import re
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import sql


def _safe_schema(schema_name: str) -> str:
    """Допустимы только test_ + 32 hex-символа."""
    if not re.match(r"^test_[a-f0-9]{32}$", schema_name):
        raise ValueError("schema_name must match test_[a-f0-9]{32}")
    return schema_name


def create_schema(conn, schema_name: str) -> None:
    """Создать схему test_<uuid>."""
    schema_name = _safe_schema(schema_name)
    with conn.cursor() as cur:
        cur.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema_name)))
        conn.commit()


def create_client_info_tables(conn, schema_name: str) -> None:
    """
    Создать в схеме schema_name минимальные таблицы для client-info:
    users, businesses, parsequeue, businessmaplinks, userservices, businessprofiles.
    """
    schema_name = _safe_schema(schema_name)

    def q(table: str):
        return sql.SQL("{}.{}").format(sql.Identifier(schema_name), sql.Identifier(table))

    with conn.cursor() as cur:
        cur.execute(sql.SQL("CREATE TABLE IF NOT EXISTS {} (id TEXT PRIMARY KEY, email TEXT, name TEXT, phone TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)").format(q("users")))
        cur.execute(sql.SQL("CREATE TABLE IF NOT EXISTS {} (id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, name TEXT, business_type TEXT, address TEXT, working_hours TEXT, is_active BOOLEAN DEFAULT TRUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)").format(q("businesses")))
        cur.execute(sql.SQL("CREATE TABLE IF NOT EXISTS {} (id TEXT PRIMARY KEY, url TEXT, user_id TEXT NOT NULL, business_id TEXT, status TEXT NOT NULL DEFAULT 'pending', task_type TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)").format(q("parsequeue")))
        cur.execute(sql.SQL("CREATE TABLE IF NOT EXISTS {} (id TEXT PRIMARY KEY, user_id TEXT, business_id TEXT, url TEXT, map_type TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)").format(q("businessmaplinks")))
        cur.execute(sql.SQL("CREATE TABLE IF NOT EXISTS {} (id TEXT PRIMARY KEY, business_id TEXT, name TEXT, description TEXT, category TEXT, price TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)").format(q("userservices")))
        cur.execute(sql.SQL("CREATE TABLE IF NOT EXISTS {} (business_id TEXT PRIMARY KEY, contact_name TEXT, contact_phone TEXT, contact_email TEXT)").format(q("businessprofiles")))
        conn.commit()


def insert_test_data(
    conn,
    schema_name: str,
    *,
    user_id: str,
    business_id: str,
    map_links: list[dict] | None = None,
) -> None:
    """Вставить одного user, один business и опционально строки в businessmaplinks."""
    schema_name = _safe_schema(schema_name)
    qual = lambda t: sql.SQL("{}.{}").format(sql.Identifier(schema_name), sql.Identifier(t))

    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("INSERT INTO {} (id, email, name, phone) VALUES (%s, %s, %s, %s) ON CONFLICT (id) DO NOTHING").format(qual("users")),
            (user_id, "test@test.local", "Test User", None),
        )
        cur.execute(
            sql.SQL("INSERT INTO {} (id, owner_id, name, business_type, address, working_hours, is_active) VALUES (%s, %s, %s, %s, %s, %s, TRUE) ON CONFLICT (id) DO NOTHING").format(qual("businesses")),
            (business_id, user_id, "Test Business", "salon", "Address", None),
        )
        for link in map_links or []:
            lid = link.get("id") or str(uuid.uuid4())
            cur.execute(
                sql.SQL("INSERT INTO {} (id, user_id, business_id, url, map_type) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING").format(qual("businessmaplinks")),
                (lid, user_id, business_id, link.get("url", ""), link.get("map_type", "yandex")),
            )
        conn.commit()


def get_connection_with_search_path(dsn: str, schema_name: str):
    """Вернуть соединение psycopg2 с search_path = schema_name."""
    schema_name = _safe_schema(schema_name)
    conn = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    with conn.cursor() as cur:
        cur.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema_name)))
    conn.commit()
    return conn
