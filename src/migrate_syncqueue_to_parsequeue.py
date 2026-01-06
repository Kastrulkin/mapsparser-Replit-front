#!/usr/bin/env python3
"""
Миграция: Объединение SyncQueue в ParseQueue

Эта миграция:
1. Добавляет недостающие поля в ParseQueue (task_type, account_id, source, error_message, updated_at)
2. Переносит данные из SyncQueue в ParseQueue
3. Проверяет количество перенесенных записей
4. НЕ удаляет SyncQueue (удаление будет после тестирования)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from safe_db_utils import get_db_connection, safe_migrate
import sqlite3

def column_exists(cursor, table_name, column_name):
    """Проверяет наличие колонки в таблице"""
    # PRAGMA не поддерживает параметризованные запросы, используем f-string с проверкой
    ALLOWED_TABLES = {'ParseQueue', 'SyncQueue'}
    if table_name not in ALLOWED_TABLES:
        raise ValueError(f"Неразрешенная таблица: {table_name}")
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns

def table_exists(cursor, table_name):
    """Проверяет наличие таблицы"""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    return cursor.fetchone() is not None

def migrate_syncqueue_to_parsequeue():
    """Основная функция миграции"""
    
    def migration_logic(cursor, conn):
        print("=" * 60)
        print("МИГРАЦИЯ: Объединение SyncQueue в ParseQueue")
        print("=" * 60)
        
        # ШАГ 1: Проверяем наличие таблиц
        if not table_exists(cursor, "ParseQueue"):
            print("❌ Таблица ParseQueue не найдена!")
            print("⚠️ Сначала запустите init_database_schema.py")
            return False
        
        syncqueue_exists = table_exists(cursor, "SyncQueue")
        if not syncqueue_exists:
            print("⚠️ Таблица SyncQueue не найдена. Возможно, миграция уже выполнена.")
            print("📝 Продолжаю добавление полей в ParseQueue...")
        
        # ШАГ 2: Добавляем недостающие поля в ParseQueue
        print("\n📝 ШАГ 1: Добавление полей в ParseQueue...")
        
        fields_to_add = [
            ("task_type", "TEXT DEFAULT 'parse_card'"),
            ("account_id", "TEXT"),
            ("source", "TEXT"),
            ("error_message", "TEXT"),
            ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        ]
        
        added_count = 0
        for field_name, field_type in fields_to_add:
            if not column_exists(cursor, "ParseQueue", field_name):
                try:
                    cursor.execute(f"ALTER TABLE ParseQueue ADD COLUMN {field_name} {field_type}")
                    print(f"✅ Добавлено поле: {field_name}")
                    added_count += 1
                except Exception as e:
                    print(f"⚠️ Ошибка при добавлении поля {field_name}: {e}")
            else:
                print(f"ℹ️  Поле {field_name} уже существует")
        
        conn.commit()
        print(f"✅ Добавлено полей: {added_count}")
        
        # ШАГ 3: Миграция данных из SyncQueue в ParseQueue
        if not syncqueue_exists:
            print("\n⚠️ Таблица SyncQueue не найдена. Пропускаю миграцию данных.")
            return True
        
        print("\n📝 ШАГ 2: Миграция данных из SyncQueue в ParseQueue...")
        
        # Проверяем количество записей в SyncQueue
        cursor.execute("SELECT COUNT(*) FROM SyncQueue")
        syncqueue_count = cursor.fetchone()[0]
        print(f"📊 Записей в SyncQueue: {syncqueue_count}")
        
        if syncqueue_count == 0:
            print("ℹ️  SyncQueue пуста. Миграция данных не требуется.")
            return True
        
        # Проверяем количество записей в ParseQueue до миграции
        cursor.execute("SELECT COUNT(*) FROM ParseQueue")
        parsequeue_count_before = cursor.fetchone()[0]
        print(f"📊 Записей в ParseQueue до миграции: {parsequeue_count_before}")
        
        # Миграция данных
        cursor.execute("""
            INSERT INTO ParseQueue (
                id, business_id, account_id, task_type, source, 
                status, error_message, created_at, updated_at, user_id, url
            )
            SELECT 
                SyncQueue.id,
                SyncQueue.business_id,
                SyncQueue.account_id,
                CASE 
                    WHEN SyncQueue.source = 'yandex_business' THEN 'sync_yandex_business'
                    WHEN SyncQueue.source = 'google_business' THEN 'sync_google_business'
                    WHEN SyncQueue.source = '2gis' THEN 'sync_2gis'
                    ELSE 'sync_unknown'
                END as task_type,
                SyncQueue.source,
                SyncQueue.status,
                SyncQueue.error_message,
                SyncQueue.created_at,
                SyncQueue.updated_at,
                COALESCE(
                    (SELECT owner_id FROM Businesses WHERE Businesses.id = SyncQueue.business_id LIMIT 1),
                    ''  -- fallback, если бизнес не найден
                ) as user_id,
                '' as url  -- для sync задач url не нужен
            FROM SyncQueue
            WHERE NOT EXISTS (
                SELECT 1 FROM ParseQueue WHERE ParseQueue.id = SyncQueue.id
            )
        """)
        
        migrated_count = cursor.rowcount
        conn.commit()
        print(f"✅ Перенесено записей: {migrated_count}")
        
        # Проверяем количество записей в ParseQueue после миграции
        cursor.execute("SELECT COUNT(*) FROM ParseQueue")
        parsequeue_count_after = cursor.fetchone()[0]
        print(f"📊 Записей в ParseQueue после миграции: {parsequeue_count_after}")
        
        # Проверяем задачи синхронизации
        cursor.execute("SELECT COUNT(*) FROM ParseQueue WHERE task_type LIKE 'sync_%'")
        sync_tasks_count = cursor.fetchone()[0]
        print(f"📊 Задач синхронизации в ParseQueue: {sync_tasks_count}")
        
        # Проверка
        if migrated_count != syncqueue_count:
            print(f"⚠️ ВНИМАНИЕ: Перенесено {migrated_count} записей, но в SyncQueue было {syncqueue_count}")
            print("⚠️ Возможно, некоторые записи уже существовали в ParseQueue")
        
        if sync_tasks_count != migrated_count:
            print(f"⚠️ ВНИМАНИЕ: Найдено {sync_tasks_count} задач синхронизации, но перенесено {migrated_count}")
        
        print("\n✅ Миграция данных завершена!")
        print("⚠️ ВАЖНО: Таблица SyncQueue НЕ удалена. Удаление будет после тестирования.")
        
        return True
    
    # Используем safe_migrate для автоматического бэкапа
    return safe_migrate(migrate_syncqueue_to_parsequeue.__name__, migration_logic)

if __name__ == "__main__":
    print("Запуск миграции объединения очередей...")
    success = migrate_syncqueue_to_parsequeue()
    if success:
        print("\n✅ Миграция успешно завершена!")
        sys.exit(0)
    else:
        print("\n❌ Миграция завершилась с ошибками!")
        sys.exit(1)

