
import sqlite3
import sys
import os

# Добавляем корневую директорию в sys.path для импорта модулей
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.safe_db_utils import safe_migrate

def migrate_add_step_column(cursor):
    """Добавляет колонку step в таблицу BusinessOptimizationWizard"""
    
    # 1. Проверяем существование таблицы
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='BusinessOptimizationWizard'")
    if not cursor.fetchone():
        print("⚠️ Таблица BusinessOptimizationWizard не найдена. Создаю новую...")
        # Если таблицы нет, init_database_schema создаст её с правильной структурой,
        # но на всякий случай можно и тут, но лучше довериться init_schema.
        # В данном контексте мы предполагаем что таблица есть, но старая.
        return 

    # 2. Проверяем существование колонки
    cursor.execute("PRAGMA table_info(BusinessOptimizationWizard)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'step' not in columns:
        print("🔄 Добавление колонки step...")
        cursor.execute("ALTER TABLE BusinessOptimizationWizard ADD COLUMN step INTEGER DEFAULT 1")
        print("✅ Колонка step добавлена")
    else:
        print("✅ Колонка step уже существует")

    if 'completed' not in columns:
        print("🔄 Добавление колонки completed...")
        cursor.execute("ALTER TABLE BusinessOptimizationWizard ADD COLUMN completed INTEGER DEFAULT 0")
        print("✅ Колонка completed добавлена")
    else:
        print("✅ Колонка completed уже существует")

if __name__ == "__main__":
    safe_migrate(migrate_add_step_column, "Add step column to BusinessOptimizationWizard")
