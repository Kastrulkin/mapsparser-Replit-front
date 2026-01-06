#!/usr/bin/env python3
"""
Скрипт для проверки, какие таблицы существуют локально, но могут отсутствовать на сервере.
Сравнивает список таблиц с миграциями.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import sqlite3
from safe_db_utils import get_db_path

def get_all_tables():
    """Получить список всех таблиц в БД"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    return tables

def get_tables_from_migrations():
    """Получить список таблиц, которые должны быть созданы миграциями"""
    migration_tables = set()
    
    # Таблицы из migrate_external_sources.py
    migration_tables.update(['ExternalBusinessAccounts', 'ExternalBusinessReviews', 'ExternalBusinessStats'])
    
    # Таблицы из migrate_external_posts_photos.py
    migration_tables.update(['ExternalBusinessPosts', 'ExternalBusinessPhotos'])
    
    # Таблицы из других миграций (можно расширить)
    # ...
    
    return migration_tables

def main():
    print("=" * 60)
    print("🔍 Проверка таблиц в базе данных")
    print("=" * 60)
    
    db_path = get_db_path()
    print(f"📁 База данных: {db_path}")
    
    # Получаем все таблицы
    all_tables = get_all_tables()
    print(f"\n📊 Всего таблиц в БД: {len(all_tables)}")
    print("\n📋 Список всех таблиц:")
    for i, table in enumerate(all_tables, 1):
        print(f"  {i:2d}. {table}")
    
    # Таблицы из миграций
    migration_tables = get_tables_from_migrations()
    print(f"\n🔄 Таблицы из миграций (должны быть):")
    for table in sorted(migration_tables):
        exists = "✅" if table in all_tables else "❌"
        print(f"  {exists} {table}")
    
    # Проверяем, какие таблицы из миграций отсутствуют
    missing = migration_tables - set(all_tables)
    if missing:
        print(f"\n⚠️  Отсутствующие таблицы (нужно применить миграции):")
        for table in sorted(missing):
            print(f"  ❌ {table}")
    else:
        print(f"\n✅ Все таблицы из миграций присутствуют!")
    
    print("\n" + "=" * 60)
    print("📝 Команды для применения миграций на сервере:")
    print("=" * 60)
    if missing:
        if 'ExternalBusinessAccounts' in missing or 'ExternalBusinessReviews' in missing or 'ExternalBusinessStats' in missing:
            print("python migrations/migrate_external_sources.py")
        if 'ExternalBusinessPosts' in missing or 'ExternalBusinessPhotos' in missing:
            print("python migrations/migrate_external_posts_photos.py")
    else:
        print("Все миграции применены!")

if __name__ == "__main__":
    main()

