#!/usr/bin/env python3
"""
Миграция: Добавление версионирования для таблицы cards
Добавляет поля version и is_latest, создаёт индексы для быстрого доступа
"""
import sys
from pathlib import Path
from dotenv import load_dotenv

# Загружаем .env
load_dotenv()

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent))

from pg_db_utils import get_db_connection


def migrate():
    """Добавить версионирование в таблицу cards"""
    print("🔄 Запуск миграции: добавление версионирования для cards...")
    
    conn = None
    cursor = None
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Проверяем, существует ли таблица cards
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = 'cards'
            ) as exists
        """)
        row = cursor.fetchone()
        table_exists = row.get('exists') if isinstance(row, dict) else (row[0] if row else False)
        
        if not table_exists:
            print("⚠️  Таблица cards не существует. Создаём таблицу с версионированием...")
            # Создаём таблицу с полями версионирования
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cards (
                    id TEXT PRIMARY KEY,
                    business_id TEXT,
                    user_id TEXT,
                    url TEXT,
                    title TEXT,
                    address TEXT,
                    phone TEXT,
                    site TEXT,
                    rating REAL,
                    reviews_count INTEGER,
                    categories TEXT,
                    overview TEXT,
                    products TEXT,
                    news TEXT,
                    photos TEXT,
                    features_full TEXT,
                    competitors TEXT,
                    hours TEXT,
                    hours_full TEXT,
                    report_path TEXT,
                    seo_score INTEGER,
                    ai_analysis TEXT,
                    recommendations TEXT,
                    version INTEGER NOT NULL DEFAULT 1,
                    is_latest BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("✅ Таблица cards создана с полями версионирования")
            conn.commit()  # Коммитим создание таблицы
        else:
            # Проверяем существующие колонки
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = 'public' AND table_name = 'cards'
            """)
            existing_columns = set()
            for row in cursor.fetchall():
                col_name = row.get('column_name') if isinstance(row, dict) else row[0]
                existing_columns.add(col_name)
            
            # Добавляем version, если нет
            if 'version' not in existing_columns:
                print("➕ Добавление колонки version...")
                try:
                    cursor.execute("""
                        ALTER TABLE cards 
                        ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1
                    """)
                    # Обновляем существующие записи: устанавливаем version = 1 для всех
                    cursor.execute("UPDATE cards SET version = 1 WHERE version IS NULL")
                    # Делаем NOT NULL после заполнения данных
                    cursor.execute("""
                        ALTER TABLE cards 
                        ALTER COLUMN version SET NOT NULL,
                        ALTER COLUMN version SET DEFAULT 1
                    """)
                    print("✅ Колонка version добавлена")
                except Exception as e:
                    print(f"⚠️  Ошибка при добавлении version: {e}")
                    print("   Продолжаем...")
            else:
                print("✓ Колонка version уже существует")
            
            # Добавляем is_latest, если нет
            if 'is_latest' not in existing_columns:
                print("➕ Добавление колонки is_latest...")
                try:
                    cursor.execute("""
                        ALTER TABLE cards 
                        ADD COLUMN IF NOT EXISTS is_latest BOOLEAN DEFAULT TRUE
                    """)
                    # Обновляем существующие записи: устанавливаем is_latest = TRUE для всех
                    cursor.execute("UPDATE cards SET is_latest = TRUE WHERE is_latest IS NULL")
                    # Делаем NOT NULL после заполнения данных
                    cursor.execute("""
                        ALTER TABLE cards 
                        ALTER COLUMN is_latest SET NOT NULL,
                        ALTER COLUMN is_latest SET DEFAULT TRUE
                    """)
                    print("✅ Колонка is_latest добавлена")
                except Exception as e:
                    print(f"⚠️  Ошибка при добавлении is_latest: {e}")
                    print("   Продолжаем...")
            else:
                print("✓ Колонка is_latest уже существует")
            
            # Нормализуем данные: для каждого business_id оставляем только одну is_latest = TRUE
            # (берем самую новую по created_at)
            print("🔧 Нормализация данных: оставляем только одну is_latest = TRUE на business_id...")
            cursor.execute("""
                UPDATE cards c1
                SET is_latest = FALSE
                WHERE EXISTS (
                    SELECT 1 FROM cards c2
                    WHERE c2.business_id = c1.business_id
                    AND c2.business_id IS NOT NULL
                    AND c2.created_at > c1.created_at
                    AND c1.is_latest = TRUE
                )
            """)
            normalized_count = cursor.rowcount
            print(f"✅ Нормализовано записей: {normalized_count}")
            conn.commit()  # Коммитим изменения колонок
        
        # Создаём индекс для быстрого доступа к актуальной версии
        print("➕ Создание индекса idx_cards_business_latest...")
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_cards_business_latest
                ON cards (business_id)
                WHERE is_latest = TRUE
            """)
            conn.commit()  # Коммитим индекс отдельно
            print("✅ Индекс idx_cards_business_latest создан")
        except Exception as e:
            print(f"⚠️  Не удалось создать индекс idx_cards_business_latest: {e}")
            print("   Продолжаем без индекса...")
            conn.rollback()  # Откатываем только индекс
        
        # Создаём уникальный индекс для гарантии одной is_latest = TRUE на business_id
        print("➕ Создание уникального индекса uniq_cards_latest_per_business...")
        try:
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS uniq_cards_latest_per_business
                ON cards (business_id)
                WHERE is_latest = TRUE AND business_id IS NOT NULL
            """)
            conn.commit()  # Коммитим индекс отдельно
            print("✅ Уникальный индекс uniq_cards_latest_per_business создан")
        except Exception as e:
            print(f"⚠️  Не удалось создать уникальный индекс (возможно, есть дубликаты или недостаточно прав): {e}")
            print("   Продолжаем без уникального индекса...")
            conn.rollback()  # Откатываем только индекс
        print("✅ Миграция успешно завершена")
        
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        import traceback
        traceback.print_exc()
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


if __name__ == "__main__":
    migrate()
