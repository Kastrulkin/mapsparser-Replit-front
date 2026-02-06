#!/usr/bin/env python3
"""
Единая точка подключения к PostgreSQL базе данных
PostgreSQL-only: SQLite больше не поддерживается в runtime
"""
import os


def get_db_connection():
    """
    Получить соединение с PostgreSQL базой данных
    
    Читает переменные окружения:
    - DATABASE_URL (приоритет) - полный URL подключения
    - Или отдельные: PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD
    
    По умолчанию подключается к beautybot_local на localhost
    """
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError as e:
        raise ImportError(
            f"psycopg2-binary не установлен. Установите: pip install psycopg2-binary\n"
            f"Ошибка: {e}"
        )
    
    # Приоритет: DATABASE_URL
    database_url = os.getenv('DATABASE_URL')
    
    if database_url:
        try:
            conn = psycopg2.connect(database_url)
            conn.cursor_factory = RealDictCursor
            # Проверяем подключение
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                version = cur.fetchone()
            print(f"✅ Подключено к PostgreSQL: {database_url.split('@')[1] if '@' in database_url else 'local'}")
            return conn
        except Exception as e:
            raise ConnectionError(f"PostgreSQL connect failed (DATABASE_URL): {e}")
    
    # Fallback: отдельные переменные окружения
    pg_host = os.getenv('PGHOST', 'localhost')
    pg_port = os.getenv('PGPORT', '5432')
    pg_database = os.getenv('PGDATABASE', 'beautybot_local')
    pg_user = os.getenv('PGUSER', 'beautybot_user')
    pg_password = os.getenv('PGPASSWORD', '')
    
    try:
        conn = psycopg2.connect(
            host=pg_host,
            port=pg_port,
            database=pg_database,
            user=pg_user,
            password=pg_password
        )
        conn.cursor_factory = RealDictCursor
        # Проверяем подключение
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            version = cur.fetchone()
        print(f"✅ Подключено к PostgreSQL: {pg_database}@{pg_host}:{pg_port}")
        return conn
    except Exception as e:
        raise ConnectionError(
            f"PostgreSQL connect failed ({pg_database}@{pg_host}:{pg_port}): {e}\n"
            f"Убедитесь, что PostgreSQL запущен и переменные окружения настроены."
        )
