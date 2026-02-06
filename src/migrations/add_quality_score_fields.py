#!/usr/bin/env python3
"""
Миграция: Добавление полей Quality Score для отслеживания качества данных
- data_source: источник данных (api/html/meta)
- quality_score: оценка качества (0-100)
- raw_snapshot: сырые данные для плохих записей (quality_score < 50)
"""
import sys
import os

# Добавляем путь к src для импорта
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from safe_db_utils import safe_migrate

def migrate():
    """Добавить поля Quality Score"""
    
    def apply_migration(cursor):
        # Определяем тип БД (SQLite или PostgreSQL)
        # Проверяем через попытку выполнить SQLite-специфичную команду
        is_sqlite = False
        try:
            cursor.execute("SELECT sqlite_version()")
            cursor.fetchone()
            is_sqlite = True
        except Exception:
            # Если команда не сработала - это PostgreSQL
            is_sqlite = False
        
        # Альтернативный способ: проверка через DB_TYPE env
        db_type = os.getenv('DB_TYPE', 'sqlite').lower()
        if db_type in ('postgres', 'postgresql'):
            is_sqlite = False
        
        # 1. ExternalBusinessReviews
        print("📋 Добавление полей Quality Score в ExternalBusinessReviews...")
        
        # Проверяем существование таблицы и колонок
        existing_columns = []
        table_exists = False
        
        try:
            if is_sqlite:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ExternalBusinessReviews'")
                table_exists = cursor.fetchone() is not None
                if table_exists:
                    cursor.execute("PRAGMA table_info(ExternalBusinessReviews)")
                    existing_columns = [row[1] for row in cursor.fetchall()]
            else:
                # PostgreSQL - проверяем существование таблицы
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' AND table_name = 'externalbusinessreviews'
                    )
                """)
                result = cursor.fetchone()
                table_exists = result[0] if isinstance(result, dict) else result[0] if result else False
                
                if table_exists:
                    cursor.execute("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_schema = 'public' AND table_name = 'externalbusinessreviews'
                    """)
                    rows = cursor.fetchall()
                    existing_columns = [row['column_name'] if isinstance(row, dict) else row[0] for row in rows]
        except Exception as e:
            # Ошибка при проверке - считаем что таблицы нет
            print(f"   ℹ️  Таблица ExternalBusinessReviews еще не создана или ошибка проверки: {e}")
            table_exists = False
            existing_columns = []
        
        if not table_exists:
            print("   ⚠️  Таблица ExternalBusinessReviews не существует - пропускаем миграцию (схема будет применена через schema_postgres.sql)")
            return
        
        if 'data_source' not in existing_columns:
            cursor.execute("ALTER TABLE ExternalBusinessReviews ADD COLUMN data_source VARCHAR(20) DEFAULT 'unknown'")
            print("   ✅ Добавлена колонка data_source")
        else:
            print("   ✅ Колонка data_source уже существует")
        
        if 'quality_score' not in existing_columns:
            cursor.execute("ALTER TABLE ExternalBusinessReviews ADD COLUMN quality_score INTEGER DEFAULT 0")
            print("   ✅ Добавлена колонка quality_score")
        else:
            print("   ✅ Колонка quality_score уже существует")
        
        if 'raw_snapshot' not in existing_columns:
            # Для SQLite используем TEXT, для PostgreSQL - JSONB
            if is_sqlite:
                cursor.execute("ALTER TABLE ExternalBusinessReviews ADD COLUMN raw_snapshot TEXT")
            else:
                # PostgreSQL - используем JSONB
                cursor.execute("ALTER TABLE ExternalBusinessReviews ADD COLUMN raw_snapshot JSONB")
            print("   ✅ Добавлена колонка raw_snapshot")
        else:
            print("   ✅ Колонка raw_snapshot уже существует")
        
        # 2. MapParseResults
        print("\n📋 Добавление полей Quality Score в MapParseResults...")
        
        existing_columns = []
        table_exists = False
        
        try:
            if is_sqlite:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='MapParseResults'")
                table_exists = cursor.fetchone() is not None
                if table_exists:
                    cursor.execute("PRAGMA table_info(MapParseResults)")
                    existing_columns = [row[1] for row in cursor.fetchall()]
            else:
                # PostgreSQL - проверяем существование таблицы
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' AND table_name = 'mapparseresults'
                    )
                """)
                result = cursor.fetchone()
                table_exists = result[0] if isinstance(result, dict) else result[0] if result else False
                
                if table_exists:
                    cursor.execute("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_schema = 'public' AND table_name = 'mapparseresults'
                    """)
                    rows = cursor.fetchall()
                    existing_columns = [row['column_name'] if isinstance(row, dict) else row[0] for row in rows]
        except Exception as e:
            # Ошибка при проверке - считаем что таблицы нет
            print(f"   ℹ️  Таблица MapParseResults еще не создана или ошибка проверки: {e}")
            table_exists = False
            existing_columns = []
        
        if not table_exists:
            print("   ⚠️  Таблица MapParseResults не существует - пропускаем миграцию (схема будет применена через schema_postgres.sql)")
            return
        
        if 'data_source' not in existing_columns:
            cursor.execute("ALTER TABLE MapParseResults ADD COLUMN data_source VARCHAR(20) DEFAULT 'unknown'")
            print("   ✅ Добавлена колонка data_source")
        else:
            print("   ✅ Колонка data_source уже существует")
        
        if 'quality_score' not in existing_columns:
            cursor.execute("ALTER TABLE MapParseResults ADD COLUMN quality_score INTEGER DEFAULT 0")
            print("   ✅ Добавлена колонка quality_score")
        else:
            print("   ✅ Колонка quality_score уже существует")
        
        if 'parse_metadata' not in existing_columns:
            # Для SQLite используем TEXT (JSON строка), для PostgreSQL - JSONB
            if is_sqlite:
                cursor.execute("ALTER TABLE MapParseResults ADD COLUMN parse_metadata TEXT")
            else:
                cursor.execute("ALTER TABLE MapParseResults ADD COLUMN parse_metadata JSONB")
            print("   ✅ Добавлена колонка parse_metadata")
        else:
            print("   ✅ Колонка parse_metadata уже существует")
        
        # 3. Индексы для быстрого поиска "плохих" данных
        print("\n📋 Создание индексов для quality_score...")
        
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_reviews_quality_score 
                ON ExternalBusinessReviews(quality_score) 
                WHERE quality_score < 50
            """)
            print("   ✅ Индекс idx_reviews_quality_score создан")
        except Exception as e:
            print(f"   ⚠️ Ошибка создания индекса idx_reviews_quality_score: {e}")
        
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_map_parse_quality_score 
                ON MapParseResults(quality_score) 
                WHERE quality_score < 50
            """)
            print("   ✅ Индекс idx_map_parse_quality_score создан")
        except Exception as e:
            print(f"   ⚠️ Ошибка создания индекса idx_map_parse_quality_score: {e}")
        
        # 4. Обновляем существующие записи: устанавливаем quality_score = 100 для существующих данных
        print("\n📋 Обновление существующих записей...")
        
        cursor.execute("""
            UPDATE ExternalBusinessReviews 
            SET quality_score = 100, data_source = 'legacy'
            WHERE quality_score = 0 OR quality_score IS NULL
        """)
        updated_reviews = cursor.rowcount
        print(f"   ✅ Обновлено {updated_reviews} записей в ExternalBusinessReviews")
        
        cursor.execute("""
            UPDATE MapParseResults 
            SET quality_score = 100, data_source = 'legacy'
            WHERE quality_score = 0 OR quality_score IS NULL
        """)
        updated_parse = cursor.rowcount
        print(f"   ✅ Обновлено {updated_parse} записей в MapParseResults")
        
        print("\n✅ Миграция Quality Score завершена успешно!")
    
    safe_migrate(apply_migration, "add_quality_score_fields")

if __name__ == "__main__":
    migrate()
