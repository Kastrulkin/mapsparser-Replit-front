#!/usr/bin/env python3
"""
Миграция: Переименование поля workflow_json в workflow
Workflow хранится как YAML текст, а не JSON, поэтому название должно быть workflow
"""
import sys
import os
import sqlite3
from safe_db_utils import safe_migrate, get_db_path

def migrate_rename_workflow_json(cursor):
    """Переименование поля workflow_json в workflow"""
    print("🔄 Переименование поля workflow_json в workflow...")
    try:
        # SQLite не поддерживает ALTER TABLE RENAME COLUMN напрямую в старых версиях
        # Используем стандартный подход: создаём новую таблицу, копируем данные, удаляем старую
        
        # Проверяем, существует ли поле workflow_json
        cursor.execute("PRAGMA table_info(AIAgents)")
        columns = cursor.fetchall()
        has_workflow_json = any(col[1] == 'workflow_json' for col in columns)
        has_workflow = any(col[1] == 'workflow' for col in columns)
        
        if not has_workflow_json:
            print("  ℹ️  Поле workflow_json не найдено, возможно уже переименовано")
            return
        
        if has_workflow:
            print("  ℹ️  Поле workflow уже существует, копируем данные из workflow_json")
            # Копируем данные из workflow_json в workflow
            cursor.execute("""
                UPDATE AIAgents 
                SET workflow = workflow_json 
                WHERE workflow_json IS NOT NULL AND workflow_json != ''
            """)
            print("  ✅ Данные скопированы из workflow_json в workflow")
            # Удаляем старое поле (через пересоздание таблицы)
            print("  🔄 Удаление поля workflow_json...")
        else:
            # Переименовываем поле через пересоздание таблицы
            print("  🔄 Пересоздание таблицы AIAgents...")
        
        # Получаем структуру таблицы
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='AIAgents'")
        create_sql = cursor.fetchone()
        if not create_sql:
            print("  ⚠️  Таблица AIAgents не найдена")
            return
        
        # Создаём временную таблицу с правильной структурой
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS AIAgents_new (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                description TEXT,
                personality TEXT,
                workflow TEXT,
                task TEXT,
                identity TEXT,
                speech_style TEXT,
                restrictions_json TEXT,
                variables_json TEXT,
                is_active INTEGER DEFAULT 1,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Копируем данные, заменяя workflow_json на workflow
        cursor.execute("""
            INSERT INTO AIAgents_new 
            (id, name, type, description, personality, workflow, task, identity, speech_style, 
             restrictions_json, variables_json, is_active, created_by, created_at, updated_at)
            SELECT 
                id, name, type, description, personality, 
                COALESCE(workflow_json, '') as workflow,
                task, identity, speech_style, 
                restrictions_json, variables_json, is_active, created_by, created_at, updated_at
            FROM AIAgents
        """)
        
        # Удаляем старую таблицу
        cursor.execute("DROP TABLE AIAgents")
        
        # Переименовываем новую таблицу
        cursor.execute("ALTER TABLE AIAgents_new RENAME TO AIAgents")
        
        # Восстанавливаем индексы
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_agents_type ON AIAgents(type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_agents_is_active ON AIAgents(is_active)")
        
        print("  ✅ Поле workflow_json переименовано в workflow")
        
    except sqlite3.OperationalError as e:
        if 'duplicate column' in str(e).lower():
            print("  ℹ️  Поле workflow уже существует")
        else:
            print(f"  ⚠️  Ошибка при переименовании: {e}")
            raise
    except Exception as e:
        print(f"  ⚠️  Ошибка: {e}")
        raise

def main():
    print("=" * 60)
    print("🚀 Миграция: Переименование workflow_json в workflow")
    print("=" * 60)
    
    db_path = get_db_path()
    print(f"📁 Используем базу данных: {db_path}")

    success = safe_migrate(
        migrate_rename_workflow_json,
        "Переименование поля workflow_json в workflow (YAML текст)"
    )
    
    if success:
        print("\n✅ Миграция завершена успешно!")
        print("📝 Все существующие данные сохранены!")
        print("💾 Бэкап создан автоматически в db_backups/")
    else:
        print("\n❌ Миграция не удалась.")
        print("💾 База данных восстановлена из бэкапа")
        sys.exit(1)

if __name__ == "__main__":
    main()


