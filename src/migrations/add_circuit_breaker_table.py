#!/usr/bin/env python3
"""
Миграция: Создание таблицы CircuitBreakerState для хранения состояния Circuit Breaker
Используется для защиты API от бана в многопоточном окружении
"""
import sys
import os

# Добавляем путь к src для импорта
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from safe_db_utils import get_db_connection, safe_migrate

def migrate():
    """Создать таблицу CircuitBreakerState"""
    
    def apply_migration(cursor):
        # Определяем тип БД
        is_sqlite = False
        try:
            cursor.execute("SELECT sqlite_version()")
            cursor.fetchone()
            is_sqlite = True
        except Exception:
            is_sqlite = False
        
        db_type = os.getenv('DB_TYPE', 'sqlite').lower()
        if db_type in ('postgres', 'postgresql'):
            is_sqlite = False
        
        print("📋 Создание таблицы CircuitBreakerState...")
        
        # Проверяем, существует ли таблица
        if is_sqlite:
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='CircuitBreakerState'
            """)
            table_exists = cursor.fetchone() is not None
        else:
            # PostgreSQL
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'circuitbreakerstate'
                )
            """)
            table_exists = cursor.fetchone()[0]
        
        if table_exists:
            print("   ✅ Таблица CircuitBreakerState уже существует")
            return
        
        # Создаем таблицу
        if is_sqlite:
            cursor.execute("""
                CREATE TABLE CircuitBreakerState (
                    api_name TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    failure_count INTEGER DEFAULT 0,
                    success_count INTEGER DEFAULT 0,
                    last_failure_time TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        else:
            # PostgreSQL
            cursor.execute("""
                CREATE TABLE CircuitBreakerState (
                    api_name VARCHAR(50) PRIMARY KEY,
                    state VARCHAR(20) NOT NULL,
                    failure_count INTEGER DEFAULT 0,
                    success_count INTEGER DEFAULT 0,
                    last_failure_time TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        
        print("   ✅ Таблица CircuitBreakerState создана")
    
    safe_migrate(apply_migration, "add_circuit_breaker_table")

if __name__ == "__main__":
    migrate()
