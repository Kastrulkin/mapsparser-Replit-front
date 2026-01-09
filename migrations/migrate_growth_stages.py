#!/usr/bin/env python3
"""
Миграция для создания таблиц этапов роста бизнеса
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from safe_db_utils import safe_migrate, get_db_connection
import sqlite3

def migrate_growth_stages(cursor):
    """Создание таблиц BusinessTypes, GrowthStages, GrowthTasks"""
    
    print("🔄 Создание таблицы BusinessTypes...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS BusinessTypes (
            id TEXT PRIMARY KEY,
            type_key TEXT UNIQUE NOT NULL,
            label TEXT NOT NULL,
            description TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("  ✅ Таблица BusinessTypes создана/проверена")
    
    print("🔄 Создание таблицы GrowthStages...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS GrowthStages (
            id TEXT PRIMARY KEY,
            business_type_id TEXT NOT NULL,
            stage_number INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            goal TEXT,
            expected_result TEXT,
            duration TEXT,
            is_permanent INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (business_type_id) REFERENCES BusinessTypes(id) ON DELETE CASCADE,
            UNIQUE(business_type_id, stage_number)
        )
    """)
    print("  ✅ Таблица GrowthStages создана/проверена")
    
    print("🔄 Создание таблицы GrowthTasks...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS GrowthTasks (
            id TEXT PRIMARY KEY,
            stage_id TEXT NOT NULL,
            task_number INTEGER NOT NULL,
            task_text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (stage_id) REFERENCES GrowthStages(id) ON DELETE CASCADE,
            UNIQUE(stage_id, task_number)
        )
    """)
    print("  ✅ Таблица GrowthTasks создана/проверена")
    
    # Инициализируем дефолтные типы бизнеса, если их нет
    default_business_types = [
        ('beauty_salon', 'Салон красоты', 'Салон красоты с полным спектром услуг'),
        ('barbershop', 'Барбершоп', 'Мужской барбершоп'),
        ('spa', 'SPA/Wellness', 'SPA и wellness центр'),
        ('nail_studio', 'Ногтевая студия', 'Студия маникюра и педикюра'),
        ('cosmetology', 'Косметология', 'Косметологический кабинет'),
        ('massage', 'Массаж', 'Массажный салон'),
        ('brows_lashes', 'Брови и ресницы', 'Студия бровей и ресниц'),
        ('makeup', 'Макияж', 'Студия макияжа'),
        ('tanning', 'Солярий', 'Студия загара'),
        ('other', 'Другое', 'Другой тип бизнеса')
    ]
    
    print("🔄 Заполнение BusinessTypes...")
    for type_key, label, description in default_business_types:
        cursor.execute("""
            INSERT OR IGNORE INTO BusinessTypes (id, type_key, label, description)
            VALUES (?, ?, ?, ?)
        """, (f"bt_{type_key}", type_key, label, description))
    
    print("  ✅ Дефолтные типы бизнеса инициализированы")

def main():
    """Главная функция миграции"""
    print("=" * 60)
    print("🚀 Миграция: Создание таблиц этапов роста")
    print("=" * 60)
    
    success = safe_migrate(
        migrate_growth_stages,
        "Создание таблиц BusinessTypes, GrowthStages, GrowthTasks"
    )
    
    if success:
        print("\n✅ Миграция завершена успешно!")
    else:
        print("\n❌ Миграция завершена с ошибками!")
        return 1
    
    return 0

if __name__ == '__main__':
    exit(main())
