#!/usr/bin/env python3
"""
Простой коннектор к PostgreSQL для runtime-кода (backend, worker, auth).

Жёсткие гарантии:
- Runtime НИКОГДА не подключается к SQLite.
- Если DATABASE_URL не задан — сразу бросаем RuntimeError.
- Все соединения создаются через psycopg2 с RealDictCursor.
"""

from __future__ import annotations

import os
from typing import Optional

import psycopg2
from psycopg2.extras import RealDictCursor


def _get_required_dsn() -> str:
    """
    Получить DSN из DATABASE_URL.

    Если переменная не установлена — немедленный фатальный отказ,
    чтобы runtime не смог \"случайно\" переключиться на SQLite.
    """
    dsn: Optional[str] = os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError(
            "DATABASE_URL is not set. Runtime requires PostgreSQL. "
            "Example: export DATABASE_URL='postgresql://user:pass@localhost:5432/beautybot_local'"
        )
    return dsn


def get_db_connection() -> "psycopg2.extensions.connection":
    """Получить соединение с PostgreSQL по DATABASE_URL."""
    dsn = _get_required_dsn()
    conn = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    return conn


def log_connection_info(prefix: str = "DB") -> None:
    """Одноразовый лог информации о подключении (БД, пользователь, адрес/порт)."""
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT current_database() AS db, current_user AS user")
        db_row = cur.fetchone() or {}
        cur.execute("SELECT inet_server_addr()::text AS addr, inet_server_port() AS port")
        net_row = cur.fetchone() or {}
        print(
            f"[{prefix}] PostgreSQL connected: db={db_row.get('db')}, "
            f"user={db_row.get('user')}, addr={net_row.get('addr')}:{net_row.get('port')}"
        )
    except Exception as e:
        print(f"[{prefix}] Failed to log PostgreSQL connection info: {e}")
    finally:
        try:
            if cur:
                cur.close()
        except Exception:
            pass
        try:
            if conn:
                conn.close()
        except Exception:
            pass

